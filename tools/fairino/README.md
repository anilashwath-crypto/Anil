# FAIRINO SimMachine (Docker) setup

Unrelated to the farm dashboard — parked here so it isn't lost.

`setup-simmachine.sh` brings up the FAIRINO SimMachine virtual robot controller
from the vendor's Docker package.

```sh
./setup-simmachine.sh "~/Downloads/FAIRINO SimMachine Docker_v3.9.8.zip"
```

It extracts the package, finds the Docker image tarball (by looking for
`manifest.json` inside it, so the image name doesn't need to be known up front),
loads it, creates a `192.168.58.0/24` bridge network, and starts the container
pinned to **192.168.58.2** — the address real FR-series cobots ship with, so SDK
code runs unchanged against the simulator.

Ports are also published to `127.0.0.1` so the container is reachable on Docker
Desktop (macOS/Windows), where bridge subnets are not routable from the host.

Tunable via environment variables: `NET_NAME`, `SUBNET`, `GATEWAY`, `ROBOT_IP`,
`CONTAINER`, `PUBLISH_PORTS`, `WORKDIR`.

## Architecture

The controller is built for x86-64. The script compares the image's architecture
against the host and, on a mismatch (e.g. Apple Silicon), passes `--platform` and
warns that emulation is slow and may destabilise the real-time motion loop. If the
binaries cannot execute at all it fails with the exact fix for that platform rather
than reporting a false success.

## Caveats

- The port list (`80 8080 8083 8084 20003`) is a best guess; 8083 (status
  feedback) and the XML-RPC port are confirmed from Fairino docs, the rest
  should be checked against the doc bundled in the zip.
- If the package ships its own `docker-compose.yml` or install guide, the script
  says so and you should prefer those.
- Validated end-to-end against a stand-in image, not against the real Fairino
  package — the vendor's download hosts were unreachable at the time of writing.
