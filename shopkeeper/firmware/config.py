"""
shopkeeper NANO — configuration.

Everything a given unit needs to differ on lives here, so no other file has to
be edited per build. Calibration written from the web UI is persisted to
/data/cal.json and overrides the defaults below at boot.
"""
import math


# ── network ────────────────────────────────────────────────────────────────
# AP is the default on purpose. A demonstrator has to work on a shop floor and
# in a meeting room with no guest wifi, so the cabinet brings its own network
# and the salesperson's phone joins it. Set JOIN to a (ssid, password) tuple to
# also try an existing network first.
AP_SSID     = "shopkeeper-NANO"
# Joining the house network first means the cabinet is reachable from a laptop
# that is also on the internet. Falls back to its own AP if the join fails, so
# the meeting-room case still works.
#
# CREDENTIALS DO NOT LIVE IN THIS FILE. This is a public repository and a real
# SSID and password were committed here once already. secrets.py is gitignored;
# copy secrets_example.py to secrets.py and put them there.
# The AP password lives there too: a default printed in a public repo is the
# same password on every cabinet ever flashed from it.
try:
    import secrets as _secrets
except ImportError:
    _secrets = None
JOIN        = getattr(_secrets, "JOIN", None)         # None -> AP mode only
AP_PASSWORD = getattr(_secrets, "AP_PASSWORD", None)  # >= 8 chars; main.py refuses to start the AP without it
JOIN_TIMEOUT_S = 12

# ── servos ─────────────────────────────────────────────────────────────────
# Pulse widths, microseconds. An SG90 nominally spans 500..2500 us for 180 deg,
# but clones reach 160-175 before they stall against their own end stop and
# start cooking, so the defaults deliberately ask for less than the mechanism
# can do.
#
#   span_us / 2000 * 180 = degrees,  degrees / 180 * TRAVEL_MM = mm of drawer
#   650..2350  ->  1700 us  ->  153 deg  ->  16.69 mm of the 19.63 available
#
# (An earlier comment here claimed 700..2300 was 160 deg. It is 144. The
# arithmetic is written out above so the next person can check it.)
#
# The web UI writes these live, so calibrate against the real drawer rather
# than trusting the numbers here.
# ── the gear, in ONE place ─────────────────────────────────────────────────
# This number was written out by hand in servo.py, again in mock_server.py, and
# a third time as a tooth count in www/index.html. When cad/nano.py went from
# 16 teeth to 10 none of the three moved, so the firmware reported a 26.7 mm
# stroke for a drawer that travels 16.69 and the terminal's footer advertised a
# gear the machine does not have. Derived once here; everything else imports it.
MODULE   = 1.25
TEETH    = 10
PITCH_R  = MODULE * TEETH / 2.0          # 6.25 mm
TRAVEL_MM = math.pi * PITCH_R            # 19.63 mm for a full 180 deg

SERVO_FREQ_HZ = 50
DRAWERS = [
    {"id": 0, "name": "Drawer A", "pin": 5,  "closed_us": 650, "open_us": 2350},
    {"id": 1, "name": "Drawer B", "pin": 6,  "closed_us": 650, "open_us": 2350},
]

# How long a full open or close takes. The mechanism does not need easing to
# survive - 17.6 N against a 0.06 N load - but a drawer that glides reads as a
# product and a drawer that snaps reads as a toy.
TRAVEL_MS = 1100

# An SG90 hunts audibly when it is holding position and gets warm doing it. The
# rack and pinion is not backdriveable enough to matter over a demo, so cut the
# signal once the move has settled.
DETACH_AFTER_MS = 200

# ── scripted demo ──────────────────────────────────────────────────────────
# An unattended performance for a table: hold a card, open one bay, open the
# other, secure both, then hand back to the attract loop. Runs itself at boot
# so the cabinet does something the moment it is powered, and can be re-armed
# from the terminal with POST /api/demo.
DEMO          = True
DEMO_HOLD_S   = 15      # the card sits this long before anything moves
DEMO_DWELL_S  = 3       # pause with a bay open, so the eye catches up
DEMO_LOOP     = True    # run again after finishing
DEMO_GAP_S    = 25      # attract loop gets this long between performances

# ── bench record ───────────────────────────────────────────────────────────
# What the VERIFIED screen shows. These are not aspirational: each number is
# the confirmed total from tools/bay2_endurance.py runs, whose JSON reports are
# the evidence. A cycle counts only if the harness polled until busy cleared
# AND the drawer's own open flag flipped - the API returns 202 the moment it
# accepts a job, so counting requests would prove nothing.
# Raise these when a run finishes, never before.
#   60  bay 2, sequential
#  100  bay 1  ) both bays driven SIMULTANEOUSLY, which is the worst case
#  100  bay 2  ) for supply sag - no brownout, no reboot, 0 failures
TEST_CYCLES   = 260
TEST_FAILURES = 0

# ── top-face display ───────────────────────────────────────────────────────
# 1.3" SH1106, not the 0.96" SSD1306 - see firmware/sh1106.py for the column
# offset and the write-before-you-light-it rule that this part demands.
# 400 kHz measures 32 ms a frame against 108 ms at 100 kHz, which is the
# difference between animation and a slideshow.
OLED          = True
OLED_SCL      = 2
OLED_SDA      = 1
OLED_ADDR     = 0x3C
OLED_FREQ     = 400000
OLED_CONTRAST = 0x95
OLED_DWELL    = 3.5        # seconds per attract screen. The count-up screens
                           # finish counting in roughly the first 1.4 s of the
                           # dwell, so the rest is the numeral sitting still and
                           # being read - which is the point of a big numeral.
                           # Ten screens makes a ~35 s loop.

# ── access ─────────────────────────────────────────────────────────────────
# This is the whole product thesis in four lines. The ~20 lakh cabinets do
# not weigh, photograph or RFID anything - inventory is trust-based, and what
# is actually sold is controlled access plus a record of who opened what. So
# that is what this implements.
# Set False to bypass the lock entirely while working on the bench. The access
# control IS the product - it is the whole argument of the pitch - so this is
# a development switch, not a feature. The terminal shows a loud BYPASSED chip
# whenever it is off, because demonstrating this cabinet with its lock disabled
# would undo the pitch in one sentence.
REQUIRE_PIN = False
PIN         = "2468"
PIN_TIMEOUT_S = 120        # re-lock after this long with no activity
LOG_MAX     = 60           # entries kept in RAM and mirrored to /data/log.json

# ── inventory ──────────────────────────────────────────────────────────────
# Slot list per drawer. Purely a register: nothing on this machine senses
# whether a tool is physically present, and the UI says so rather than
# implying a measurement it never takes.
TOOLS = {
    0: [
        {"slot": "A1", "tool": "END MILL 10mm 4FL",  "code": "EM-10-4F"},
        {"slot": "A2", "tool": "END MILL 6mm 3FL",   "code": "EM-06-3F"},
        {"slot": "A3", "tool": "DRILL HSS 8.5mm",    "code": "DR-085-H"},
        {"slot": "A4", "tool": "CHAMFER 90deg 12mm", "code": "CH-12-90"},
    ],
    1: [
        {"slot": "B1", "tool": "FACE MILL 40mm",     "code": "FM-40-5I"},
        {"slot": "B2", "tool": "BORING HEAD 20-50",  "code": "BH-2050"},
        {"slot": "B3", "tool": "TAP M8 x 1.25",      "code": "TP-M8-C"},
        {"slot": "B4", "tool": "REAMER 12H7",        "code": "RM-12H7"},
    ],
}

# ── identity ───────────────────────────────────────────────────────────────
# A cabinet on a shop floor has an asset tag, and the UI shows it. This is the
# difference between a demo and a machine somebody signs for.
UNIT     = "SK-N-0001"
FW       = "1.0.0"
SITE     = "OMMI FORGE / MALUR"

DATA_DIR = "/data"
