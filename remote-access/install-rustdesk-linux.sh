#!/usr/bin/env bash
# RustDesk unattended install for Debian / Ubuntu / Raspberry Pi OS (64-bit)
#
#   sudo ./install-rustdesk-linux.sh 'Choose-A-Strong-One'
#   sudo ./install-rustdesk-linux.sh 'pw' farm.example.in 'PUBLIC_KEY'   # own server
#
# Needs a desktop session (X11). On Wayland, switch the login to "Xorg";
# on a headless Pi gateway, use SSH instead of RustDesk.
set -euo pipefail

PASSWORD="${1:-}"
ID_SERVER="${2:-}"
KEY="${3:-}"

[[ $EUID -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }
[[ ${#PASSWORD} -ge 8 ]] || { echo "Usage: sudo $0 PASSWORD(min 8 chars) [ID_SERVER] [KEY]" >&2; exit 1; }

case "$(uname -m)" in
  x86_64)  ARCH=x86_64 ;;
  aarch64) ARCH=aarch64 ;;
  *) echo "Unsupported CPU $(uname -m) - use a 64-bit OS." >&2; exit 1 ;;
esac

if ! command -v rustdesk >/dev/null; then
  apt-get update -qq
  apt-get install -y -qq curl ca-certificates python3 >/dev/null
  echo "Looking up latest RustDesk release..."
  URL=$(curl -fsSL -H 'User-Agent: rustdesk-setup' \
          https://api.github.com/repos/rustdesk/rustdesk/releases/latest |
        python3 -c "
import json, re, sys
for a in json.load(sys.stdin)['assets']:
    if re.fullmatch(r'rustdesk-[0-9.]+-$ARCH\.deb', a['name']):
        print(a['browser_download_url']); break")
  [[ -n "$URL" ]] || { echo "No $ARCH .deb in latest release." >&2; exit 1; }

  TMP=$(mktemp -d)
  echo "Downloading ${URL##*/}..."
  curl -fsSL -o "$TMP/rustdesk.deb" "$URL"
  apt-get install -y "$TMP/rustdesk.deb"
  rm -rf "$TMP"
else
  echo "RustDesk already installed - configuring only."
fi

systemctl enable --now rustdesk
sleep 3

if [[ -n "$ID_SERVER" ]]; then
  systemctl stop rustdesk
  for d in /root/.config/rustdesk ${SUDO_USER:+/home/$SUDO_USER/.config/rustdesk}; do
    mkdir -p "$d"
    cat > "$d/RustDesk2.toml" <<EOF
rendezvous_server = '${ID_SERVER}:21116'
nat_type = 1
serial = 0

[options]
custom-rendezvous-server = '${ID_SERVER}'
relay-server = '${ID_SERVER}'
key = '${KEY}'
EOF
    if [[ -n "${SUDO_USER:-}" && "$d" == /home/* ]]; then chown -R "$SUDO_USER:" "$d"; fi
  done
  systemctl start rustdesk
  sleep 3
fi

rustdesk --password "$PASSWORD" >/dev/null
sleep 2
ID=$(rustdesk --get-id)

cat <<EOF

=======================================
 RustDesk ID : $ID
 Password   : (the one you passed in)
${ID_SERVER:+ ID server  : $ID_SERVER
}=======================================
Connect from the RustDesk app on your phone/laptop using this ID.
EOF
