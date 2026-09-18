#!/usr/bin/env sh
# Flash the whole firmware onto the ESP32-S3 and reset it.
#
#   sh firmware/flash.sh                 # auto-detects the port
#   sh firmware/flash.sh /dev/ttyACM0    # or name it
#
# Copies every .py the board runs plus both pages under www/, then resets so
# main.py starts fresh. Calibration and stroke timing saved on the board in
# /data survive this: only code is replaced. secrets.py is copied if you have
# made one (it is gitignored) so the AP password comes along.
set -e
cd "$(dirname "$0")"

if ! command -v mpremote >/dev/null 2>&1; then
  echo "mpremote not found: pip install mpremote" >&2; exit 1
fi

PORT="$1"
if [ -z "$PORT" ]; then
  for p in /dev/cu.usbmodem* /dev/ttyACM* /dev/ttyUSB*; do
    [ -e "$p" ] && PORT="$p" && break
  done
fi
[ -n "$PORT" ] || { echo "no board found: pass the port, e.g. sh flash.sh /dev/ttyACM0" >&2; exit 1; }
echo "board: $PORT"

M="mpremote connect $PORT"
$M mkdir :www 2>/dev/null || true
for f in config.py servo.py store.py server.py main.py sh1106.py hud.py; do
  echo "  $f"; $M cp "$f" ":$f"
done
[ -f secrets.py ] && { echo "  secrets.py"; $M cp secrets.py :secrets.py; }
for f in www/index.html www/control.html; do
  echo "  $f"; $M cp "$f" ":$f"
done
echo "reset"
$M reset
echo "done: join shopkeeper-NANO and open http://192.168.4.1/control"
