# shopkeeper NANO — firmware

MicroPython for the ESP32-S3. Brings up its own wifi, serves a control UI, and
drives the two drawer servos.

Tested on the board in hand: **ESP32-S3, MicroPython 1.28.0**, 2.0 MB free heap.

## What it does, and why that

The industrial smart tool cabinets this is pitched against — the ~₹20 lakh ones — do
not sense anything. No load cells, no cameras, no RFID. Inventory is
trust-based. What a machine shop is actually buying is **a locked drawer and a
record of who opened it**, so that is exactly what this implements:

- a PIN gate that re-locks itself after two minutes idle
- every open, close, unlock and rejected PIN written to an append-only log
- a per-drawer tool register

Nothing here claims to know whether a tool is physically present, and the UI
says so rather than implying a measurement it never takes.

## Layout

```
config.py   everything a unit differs on: wifi, pins, PIN, endpoints, tools
servo.py    SG90 driver — eased moves, calibrated endpoints, auto-detach
store.py    calibration + log persistence, with flash-wear rate limiting
server.py   asyncio HTTP server and the JSON API
main.py     boot: network, restore calibration, park closed, serve
www/        the UI, served straight off flash
```

## Flashing

One command copies everything and resets the board (auto-detects the port, or
pass it): `sh flash.sh` or `sh flash.sh /dev/ttyACM0`. Add `--wipe` to empty
the board's filesystem first, including saved calibration, timing and the log
under `/data`, for a clean install of exactly this folder. For the deepest
reset, `sh flash.sh --micropython ESP32_GENERIC_S3-xxxxxxxx-v1.28.0.bin` erases
the whole chip with esptool, writes that fresh MicroPython image (download it
from https://micropython.org/download/ESP32_GENERIC_S3/) and then installs the
firmware onto it. By hand:

```sh
PORT=/dev/cu.usbmodem5A790574951          # yours may differ; ls /dev/cu.*
mpremote connect $PORT mkdir :www
for f in config.py servo.py store.py server.py main.py; do
  mpremote connect $PORT cp $f :$f
done
mpremote connect $PORT cp www/index.html :www/index.html
mpremote connect $PORT cp www/control.html :www/control.html
mpremote connect $PORT reset
```

`main.py` runs automatically on power-up. To watch it boot:
`mpremote connect $PORT repl` then Ctrl-D.

## Using it

The cabinet brings up its own access point, because a demonstrator has to work
in a meeting room with no guest wifi:

| | |
|---|---|
| SSID | `shopkeeper-NANO` |
| Password | `AP_PASSWORD` from `secrets.py` |
| URL | **http://192.168.4.1/** |
| Control page | **http://192.168.4.1/control** |
| PIN | `2468` |

`/` is the operator terminal: PIN, tool register, access log. `/control` is the
bench page for driving the mechanism directly: open and close each bay, jog the
rack to any point of the stroke with a slider, edit the stroke timing (travel
and detach, saved to `/data/timing.json` and applied to the next move),
calibrate the pulse-width endpoints, and switch the scripted demo off while you
are driving.

Copy `secrets_example.py` to `secrets.py` (gitignored) and set `AP_PASSWORD`;
the firmware refuses to bring up the AP without one. Set `JOIN = ("ssid",
"password")` there too to join an existing network first and fall back to the AP.

## Wiring

| | |
|---|---|
| Drawer A servo signal | GPIO 5 |
| Drawer B servo signal | GPIO 6 |
| Servo V+ | **5 V, not the 3V3 rail** |
| Servo GND | common with the ESP32 GND |

Two SG90s stalling together pull well over an amp. Power them from the 5 V pin
or a separate supply — a USB port feeding the 3V3 regulator will brown the
board out mid-move and you will spend an afternoon blaming the code.

## Calibration

The endpoints in `config.py` are conservative on purpose:

```
span_us / 2000 * 180 = degrees      degrees / 180 * 31.42 = mm of drawer
650..2350  ->  1700 us  ->  153 deg  ->  26.7 mm of the 31.4 available
```

The mechanism can do 31.4 mm at a full 180°, but most SG90 clones stall against
their own end stop somewhere past 160° and cook themselves holding there. The
UI's **Calibrate** panel jogs each servo live while you watch the real drawer,
and writes the endpoints to `/data/cal.json` on release.

Set them by eye against the printed part, not from this table.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/state` | everything: lock state, drawers, tools, log |
| POST | `/api/unlock` | `{"pin":"2468"}` |
| POST | `/api/lock` | |
| POST | `/api/drawer` | `{"id":0,"open":true}` → 202, move runs async |
| POST | `/api/cal` | `{"id":0,"open_us":2350}` or `{"id":0,"jog_us":1500}` |
| POST | `/api/timing` | `{"travel_ms":1100,"detach_ms":200}` — clamped, persisted, live |
| POST | `/api/demo` | `{"on":false}` pauses the scripted demo; `true` re-arms it |
| DELETE | `/api/log` | |

Everything except `/api/state`, `/api/unlock` and `/api/lock` returns **403**
while the cabinet is locked.

## Notes for the next person

Two MicroPython differences bit during the build, both of which fail at *import*
time rather than where you'd look:

- `{**a, "b": 1}` — dict unpacking inside a display is a `SyntaxError`
- `str.ljust` does not exist

The servo is deliberately de-energised 200 ms after each move. A hobby servo
holds position by hunting, so it buzzes and warms up indefinitely otherwise,
and the rack and pinion is not backdriveable enough for a drawer to creep.
