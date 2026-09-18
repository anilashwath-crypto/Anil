#!/usr/bin/env sh
# Flash the whole firmware onto the ESP32-S3 and reset it.
#
#   sh firmware/flash.sh                 # auto-detects the port
#   sh firmware/flash.sh /dev/ttyACM0    # or name it
#   sh firmware/flash.sh --wipe          # DELETE everything on the board first
#   sh firmware/flash.sh --micropython ESP32_GENERIC_S3-xxxxxxxx-v1.28.0.bin
#                                        # erase the chip, reinstall MicroPython,
#                                        # then install this firmware on it
#
# Copies every .py the board runs plus both pages under www/, then resets so
# main.py starts fresh. Without --wipe, calibration, stroke timing and the log
# saved on the board in /data survive: only code is replaced. With --wipe the
# board's whole filesystem is emptied first (old code, /data, stray files), so
# what runs afterwards is exactly this folder and nothing else. secrets.py is
# copied if you have made one (it is gitignored) so the AP password comes
# along. MicroPython itself is not touched by either of those.
#
# --micropython <image.bin> is the deepest reset there is: esptool erases the
# whole chip (MicroPython, every file, the wifi calibration partition) and
# writes a fresh MicroPython, then the firmware is installed onto it. Get the
# image for the ESP32-S3 from https://micropython.org/download/ESP32_GENERIC_S3/
# (the board in hand runs 1.28.0). Needs esptool: pip install esptool.
set -e
cd "$(dirname "$0")"

WIPE=""; IMAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --wipe) WIPE=1 ;;
    --micropython) shift; IMAGE="$1" ;;
    *) PORT="$1" ;;
  esac
  shift
done
if [ -n "$IMAGE" ] && [ ! -f "$IMAGE" ]; then
  echo "MicroPython image not found: $IMAGE" >&2; exit 1
fi

# The tools may be on PATH, or only reachable as python modules (a plain
# "pip install --user" on macOS often lands them outside PATH). Take either.
if command -v mpremote >/dev/null 2>&1; then MPR=mpremote
elif python3 -m mpremote --help >/dev/null 2>&1; then MPR="python3 -m mpremote"
else echo "mpremote not found: python3 -m pip install mpremote" >&2; exit 1; fi

if [ -z "$PORT" ]; then
  for p in /dev/cu.usbmodem* /dev/ttyACM* /dev/ttyUSB*; do
    [ -e "$p" ] && PORT="$p" && break
  done
fi
[ -n "$PORT" ] || { echo "no board found: pass the port, e.g. sh flash.sh /dev/ttyACM0" >&2; exit 1; }
echo "board: $PORT"

M="$MPR connect $PORT"

if [ -n "$IMAGE" ]; then
  if command -v esptool.py >/dev/null 2>&1; then ESPTOOL=esptool.py
  elif command -v esptool >/dev/null 2>&1; then ESPTOOL=esptool
  elif python3 -m esptool --help >/dev/null 2>&1; then ESPTOOL="python3 -m esptool"
  else echo "esptool not found: python3 -m pip install esptool" >&2; exit 1; fi
  echo "erasing the whole chip"
  $ESPTOOL --chip esp32s3 --port "$PORT" erase_flash
  echo "writing MicroPython: $IMAGE"
  # the S3 image is a complete flash image (bootloader + partitions + app), so
  # it goes at 0x0, unlike the original ESP32 which flashes at 0x1000
  $ESPTOOL --chip esp32s3 --port "$PORT" --baud 460800 write_flash -z 0x0 "$IMAGE"
  echo "waiting for MicroPython to boot and format its filesystem"
  sleep 6
  $M exec "import sys; print('MicroPython', sys.version)"
  WIPE=""                     # nothing left on the board to wipe
fi

if [ -n "$WIPE" ]; then
  echo "wiping the board's filesystem (everything except boot.py)"
  $M exec "
import os
def rm(p):
    for n, t, *_ in os.ilistdir(p):
        q = p.rstrip('/') + '/' + n
        if t == 0x4000:
            rm(q); os.rmdir(q)
        elif q != '/boot.py':
            os.remove(q)
rm('/')
print('wiped:', os.listdir('/'))
"
fi

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
echo "      watch it boot with: $MPR connect $PORT repl"
