#!/usr/bin/env bash
#
# setup-simmachine.sh — bring up the FAIRINO SimMachine virtual controller in Docker.
#
#   Usage:  ./setup-simmachine.sh "/path/to/FAIRINO SimMachine Docker_v3.9.8.zip"
#           ./setup-simmachine.sh /path/to/already-unzipped-folder
#
# The script discovers the image name from the tarball rather than hard-coding it,
# so it works even though the exact tag inside the Fairino package is unknown up front.
#
# Everything it does is idempotent: re-running it recreates the container cleanly.

set -euo pipefail

# ---------------------------------------------------------------- configuration
NET_NAME="${NET_NAME:-fairino_net}"
SUBNET="${SUBNET:-192.168.58.0/24}"
GATEWAY="${GATEWAY:-192.168.58.1}"
ROBOT_IP="${ROBOT_IP:-192.168.58.2}"     # real FR cobots ship on this address;
                                          # matching it lets SDK code run unchanged
CONTAINER="${CONTAINER:-simmachine}"

# Ports the controller serves. Published to localhost so the container is also
# reachable on Docker Desktop (macOS/Windows), where the bridge IP is not routable.
# Cross-check this list against the doc bundled in the zip and adjust if needed.
PUBLISH_PORTS="${PUBLISH_PORTS:-80 8080 8083 8084 20003}"

WORKDIR="${WORKDIR:-$HOME/fairino-simmachine}"

# ---------------------------------------------------------------------- helpers
c_ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
c_info() { printf '\033[36m→\033[0m %s\n' "$*"; }
c_warn() { printf '\033[33m!\033[0m %s\n' "$*"; }
c_err()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; }
die()    { c_err "$*"; exit 1; }

[ $# -ge 1 ] || die "usage: $0 <path-to-simmachine-zip-or-folder>"
SRC="$1"
[ -e "$SRC" ] || die "no such file or directory: $SRC"

command -v docker >/dev/null 2>&1 || die "docker is not installed or not on PATH"
docker info >/dev/null 2>&1 || die "cannot reach the Docker daemon — is Docker running?"
c_ok "Docker daemon reachable ($(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?'))"

# ------------------------------------------------------------ 1. unpack payload
mkdir -p "$WORKDIR"
if [ -d "$SRC" ]; then
  PKG_DIR="$SRC"
  c_ok "Using existing folder: $PKG_DIR"
else
  case "$SRC" in
    *.zip)
      command -v unzip >/dev/null 2>&1 || die "unzip not found — install it (apt install unzip / brew install unzip)"
      PKG_DIR="$WORKDIR/package"
      rm -rf "$PKG_DIR"; mkdir -p "$PKG_DIR"
      c_info "Extracting $(basename "$SRC") … (this is a ~613 MB archive, give it a minute)"
      unzip -q -o "$SRC" -d "$PKG_DIR"
      c_ok "Extracted to $PKG_DIR"
      ;;
    *) die "expected a .zip or a directory, got: $SRC" ;;
  esac
fi

echo
c_info "Package contents:"
find "$PKG_DIR" -maxdepth 3 -type f -printf '    %-70p  %10s bytes\n' 2>/dev/null \
  || find "$PKG_DIR" -maxdepth 3 -type f -exec ls -lh {} \; | awk '{printf "    %-70s %s\n", $NF, $5}'
echo

# Surface any vendor instructions / compose file instead of silently ignoring them.
DOCS=$(find "$PKG_DIR" -maxdepth 3 -type f \
        \( -iname '*.pdf' -o -iname '*.md' -o -iname '*.txt' -o -iname '*.doc*' \) 2>/dev/null || true)
if [ -n "$DOCS" ]; then
  c_warn "The package ships its own instructions — read these, they win over this script's defaults:"
  echo "$DOCS" | sed 's/^/    /'
  echo
fi

COMPOSE=$(find "$PKG_DIR" -maxdepth 3 -type f \
           \( -iname 'docker-compose*.y*ml' -o -iname 'compose.y*ml' \) 2>/dev/null | head -1 || true)
if [ -n "$COMPOSE" ]; then
  c_warn "Found a compose file: $COMPOSE"
  c_warn "Prefer it over this script:  docker compose -f \"$COMPOSE\" up -d"
  echo
fi

# ------------------------------------------------------- 2. locate + load image
# A docker-save archive always contains a top-level manifest.json — test for that
# rather than guessing from filename or size, so we never load the wrong tarball.
is_docker_image() {
  tar -tf "$1" 2>/dev/null | grep -qE '^(\./)?(manifest\.json|index\.json|oci-layout)$'
}

TARBALL=""
while IFS= read -r cand; do
  [ -n "$cand" ] || continue
  if is_docker_image "$cand"; then TARBALL="$cand"; break; fi
done < <(find "$PKG_DIR" -maxdepth 4 -type f \
          \( -iname '*.tar' -o -iname '*.tar.gz' -o -iname '*.tgz' \) 2>/dev/null \
          | sort -u)

[ -n "$TARBALL" ] || die "no Docker image tarball found under $PKG_DIR
       (looked for a .tar/.tar.gz containing manifest.json)
       Run:  find '$PKG_DIR' -type f | head -50
       and tell me what the package actually contains."
c_ok "Image tarball: $TARBALL ($(du -h "$TARBALL" | cut -f1))"

c_info "Loading image into Docker … (decompressing ~600 MB, be patient)"
LOAD_OUT=$(docker load -i "$TARBALL" 2>&1) || die "docker load failed:
$LOAD_OUT"
echo "$LOAD_OUT" | sed 's/^/    /'

# docker load prints either "Loaded image: repo:tag" or "Loaded image ID: sha256:..."
IMAGE=$(echo "$LOAD_OUT" | sed -n 's/^Loaded image: //p'      | head -1)
[ -n "$IMAGE" ] || IMAGE=$(echo "$LOAD_OUT" | sed -n 's/^Loaded image ID: //p' | head -1)
[ -n "$IMAGE" ] || die "could not determine the loaded image name from docker load output"
c_ok "Image: $IMAGE"

# ------------------------------------------------ 2b. architecture reconciliation
# The controller is built for a specific CPU architecture (x86-64 in practice).
# On an Apple Silicon Mac the host is arm64, so the image must run under emulation
# and needs an explicit --platform or Docker refuses / picks the wrong variant.
IMG_ARCH=$(docker image inspect "$IMAGE" --format '{{.Architecture}}' 2>/dev/null || echo "")
HOST_ARCH=$(docker info --format '{{.Architecture}}' 2>/dev/null || uname -m)
case "$HOST_ARCH" in x86_64) HOST_ARCH=amd64 ;; aarch64) HOST_ARCH=arm64 ;; esac

PLATFORM_ARGS=()
if [ -n "$IMG_ARCH" ] && [ "$IMG_ARCH" != "$HOST_ARCH" ]; then
  c_warn "Architecture mismatch: image is '$IMG_ARCH', this machine is '$HOST_ARCH'."
  c_warn "Running under emulation — expect it to be slow, and the controller's"
  c_warn "real-time motion loop may be unstable. A native x86-64 host is preferable."
  PLATFORM_ARGS=(--platform "linux/$IMG_ARCH")
  if [ "$HOST_ARCH" = "arm64" ] && [ "$IMG_ARCH" = "amd64" ]; then
    c_info "On Apple Silicon: enable Docker Desktop → Settings → General →"
    c_info "'Use Rosetta for x86/amd64 emulation' for a large speedup."
  fi
else
  c_ok "Architecture: $IMG_ARCH (native)"
fi

# ------------------------------------------------------------ 3. bridge network
if docker network inspect "$NET_NAME" >/dev/null 2>&1; then
  c_ok "Network '$NET_NAME' already exists"
else
  docker network create --driver=bridge --subnet="$SUBNET" --gateway="$GATEWAY" "$NET_NAME" >/dev/null
  c_ok "Created network '$NET_NAME' ($SUBNET, gw $GATEWAY)"
fi

# ------------------------------------------------------------- 4. run container
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  c_warn "Removing existing container '$CONTAINER'"
  docker rm -f "$CONTAINER" >/dev/null
fi

PORT_ARGS=()
for p in $PUBLISH_PORTS; do PORT_ARGS+=(-p "127.0.0.1:$p:$p"); done

c_info "Starting container '$CONTAINER' at $ROBOT_IP …"
if ! RUN_ERR=$(docker run -d \
  --name "$CONTAINER" \
  --network "$NET_NAME" \
  --ip "$ROBOT_IP" \
  --privileged \
  --restart unless-stopped \
  "${PLATFORM_ARGS[@]}" \
  "${PORT_ARGS[@]}" \
  "$IMAGE" 2>&1); then
  c_err "docker run failed:"
  echo "$RUN_ERR" | sed 's/^/    /'
  echo
  # Translate the two failures people actually hit into something actionable.
  case "$RUN_ERR" in
    *"port is already allocated"*|*"address already in use"*)
      die "A port in PUBLISH_PORTS is taken — often a previous SimMachine container,
       or something else on port 80. Check with:  docker ps
       Then either stop the other container, or re-run with a different set, e.g.
         PUBLISH_PORTS='8080 8083 20003' $0 '$SRC'" ;;
    *"exec format error"*|*"no matching manifest"*|*"cannot be used on this platform"*)
      die "This machine cannot execute the image's architecture ($IMG_ARCH).
       On Apple Silicon, enable Docker Desktop → Settings → General →
       'Use Rosetta for x86/amd64 emulation', or run SimMachine on an x86-64 host." ;;
    *"Address already in use"*|*"cannot assign requested address"*)
      die "IP $ROBOT_IP is unavailable on network '$NET_NAME'.
       Re-run with a different address, e.g.  ROBOT_IP=192.168.58.3 $0 '$SRC'" ;;
    *) die "See the error above; the bundled Fairino doc may list extra required flags." ;;
  esac
fi

# Settle before judging. `--restart unless-stopped` means a crash-looping container
# can report Running=true when sampled between restarts, so check the status string
# and the restart count, not just the boolean.
c_info "Waiting for the controller to settle …"
sleep 8
STATE=$(docker inspect -f '{{.State.Status}}'  "$CONTAINER" 2>/dev/null || echo unknown)
RESTARTS=$(docker inspect -f '{{.RestartCount}}' "$CONTAINER" 2>/dev/null || echo 0)
LOGS=$(docker logs "$CONTAINER" 2>&1 | tail -40)

if [ "$STATE" != "running" ] || [ "${RESTARTS:-0}" -gt 0 ]; then
  c_err "Container is not healthy (state=$STATE, restarts=$RESTARTS). Logs:"
  echo "$LOGS" | sed 's/^/    /'
  echo
  case "$LOGS" in
    *"exec format error"*)
      die "The image's binaries cannot run on this CPU: image is '$IMG_ARCH', host is '$HOST_ARCH'.
       Emulation is not available or not working here.
       On Apple Silicon: Docker Desktop → Settings → General →
         enable 'Use Rosetta for x86/amd64 emulation', then re-run.
       On Linux: install qemu-user-static binfmt handlers, e.g.
         docker run --privileged --rm tonistiigi/binfmt --install all
       Otherwise run SimMachine on a native x86-64 machine." ;;
    *"permission denied"*|*"Operation not permitted"*)
      die "The controller was blocked by the sandbox. It already runs --privileged;
       the bundled Fairino doc may require extra capabilities or a host mount." ;;
    *)
      die "The controller is crash-looping. Check the logs above against the
       bundled Fairino doc — the image may need an explicit command or extra flags." ;;
  esac
fi
c_ok "Container running (state=$STATE, restarts=$RESTARTS)"

# ------------------------------------------------------------------ 5. tell me
echo
c_info "Listening ports inside the container:"
docker exec "$CONTAINER" sh -c '(netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null)' \
  | sed 's/^/    /' || c_warn "    (no netstat/ss in the image — skipped)"

cat <<EOF

────────────────────────────────────────────────────────────────
 SimMachine is up.

   Web UI      http://$ROBOT_IP        (Linux hosts — direct bridge access)
               http://127.0.0.1        (macOS / Windows — via published ports)

   SDK target  Robot IP = $ROBOT_IP    on Linux
               Robot IP = 127.0.0.1    on Docker Desktop

   Logs        docker logs -f $CONTAINER
   Shell       docker exec -it $CONTAINER bash
   Stop/start  docker stop $CONTAINER  /  docker start $CONTAINER
   Tear down   docker rm -f $CONTAINER && docker network rm $NET_NAME
────────────────────────────────────────────────────────────────
EOF
