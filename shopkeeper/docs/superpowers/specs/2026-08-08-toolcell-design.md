# ToolCell — Smart Tool Compartment

**Design spec, rev A — 2026-08-08**

A working two-compartment demonstrator of controlled-access tool storage, built to win a pilot
against the industrial smart tool cabinets.

---

## 1. Why this exists

the incumbents sell the the commercial cabinet, a smart cutting-tool cabinet, for roughly ₹20 lakh landed in
India. Research into their published brochure and product pages establishes what that money buys:

| | the incumbent the commercial cabinet |
|---|---|
| Footprint | 800 × 790 mm |
| Cabinet heights | 875 / 1175 / 1500 mm |
| Drawer heights | 50–300 mm, nine sizes |
| Load per drawer | 80 kg standard, 160 kg optional |
| Compartments per drawer | 4, 8, 12, 16, 24 or 48 |
| Compartment sizes | 275 × 241 mm down to 91 × 29 × 35 mm |
| Cabinets per controller | up to 9 daisy-chained |

They sell **three lock tiers**, and this is the commercially important part:

1. **Mechanical central lock** — one key, anti-tip interlock, only one drawer opens at a time.
2. **Electronic drawer lock** — software releases one drawer; every compartment inside it is then
   freely accessible.
3. **»smartCompartment«** — a separate plastic flap above *each* compartment, electronically
   released one at a time. This is their premium tier and the only one giving per-item traceability.

### The finding that shapes this project

**their inventory is trust-based. There are no sensors.** No load cells, no cameras, no RFID on
the tools. The system knows stock only because it locked everything except the one box it told you
to open, and then assumed you took the quantity the software displayed. A manual "stock adjustment"
function exists precisely because reality drifts. Minimum/maximum levels drive reordering.

The moat is therefore **mechanical access control + a good database + a 3D UI** — not sensing.

The software stack is a central tool database (central tool database) → `TMS Tool Management Solutions` (cost
centres, user groups, per-group quantity limits, reorder triggers) → `the pick client` (the shopfloor
kiosk that drives the LEDs and locks).

### The opportunity

The cabinet is the cheap half. TMS is what commands the price. But these systems are priced for German
tier-1 automotive suppliers, and most Indian job shops will never buy at ₹20 lakh. A ₹4–5 lakh
system doing 80% of the job addresses a real, unserved market.

**This spec covers the door-opener: a demonstrator that gets you into the room.** The software is
the actual business and is out of scope here.

---

## 2. Scope

### In scope

A self-contained, portable, mains-or-powerbank-powered demonstrator:

- Four printed compartments in one drawer-like frame.
- **Two live compartments**, each with a servo-driven self-opening flap.
- **Two dummy compartments**, printed shells only, for grid context.
- PIN authentication on a physical 4×4 keypad.
- A web kiosk served by the ESP32 over its own WiFi access point, usable from any phone or tablet.
- Per-user permissions and per-pick quantity limits.
- Flap-closed detection and transaction logging to onboard flash.

### Explicitly out of scope

- Any form of automatic counting or weighing.
- A real database, server, or ERP integration.
- 3D graphical rendering of the drawer (the commercial pick client does this; v1 uses a clear 2D plan view).
- RFID. PIN was chosen deliberately for zero additional hardware. RFID is a ₹150 drop-in later.
- A steel enclosure. v1 is fully 3D-printed.

### The honest limitation

**This is not a lock.** With a servo mounted directly on the hinge and no bolt, the servo gearbox is
the only thing resisting a pull. A shopfloor yank is roughly 60 kg·cm against the SG90's 1.8 kg·cm.
The demonstrator therefore *guides* access; it does not *enforce* it.

This was a deliberate decision to keep the build to one moving part per cell. It is acceptable for a
sales demonstrator provided nobody is invited to test it by force. **A production unit needs the
sliding-bolt variant** (servo drives a bolt sideways through a keeper loop on the flap, so pull
loads land in the printed guide walls and never reach the servo). That path is documented in §9.

---

## 3. Physical design

### 3.1 Host body

v1 is built into an existing MakerWorld model — *Ryobi Mini Desktop Toolbox* (model 1105895, a remix
of a DeWALT chest) — rather than a bespoke frame. It gives the multi-drawer cabinet silhouette that
makes the pitch legible: *"this is one drawer of a cabinet, the others work the same way."*

**Geometry measured directly from the supplied STLs**, not from the listing:

| | Large drawer | Small drawer |
|---|---|---|
| Bay shell | 189.6 × 119.5 × **55** | 189.6 × 119.5 × **30** |
| Drawer body | 105 × 189.6 × 55 | 105 × 189.6 × 30 |
| **Internal cavity** | **172.6 W × 91 D × ~52 H** | **172.6 W × 91 D × ~27 H** |
| Side wall | 3.0 mm | 3.0 mm |
| Front face | 8.0 mm | 8.5 mm |

Full assembly is 200 × 208 × 110 mm. The chest is **modular stacked bays**, so a partial build is
possible: 2 × large bay + 2 × small bay + 4 side rails (200 × 10 × 10) + 4 feet + 4 handle covers.

**The 52 mm large-drawer cavity is the deciding measurement.** The SG90 needs 32.6 mm across its
tabs, so it stands upright as specced in §3.2 with room to spare. An earlier working assumption of a
36 mm drawer would have forced the servo onto its side; that is not required and is superseded.

### 3.2 Cell layout

Both live cells go in **one large drawer**. The small drawers become dummies — 27 mm is too shallow
for an upright servo.

**Servos sit at the two outer ends, with a single idler post in the middle.**

A shared central spine was tried first and rejected. Two SG90s placed back-to-back in the middle
overlap along the shaft axis, so they must be offset front-to-back — which puts their two shafts
13.5 mm apart in Y. The flaps would then hinge on two different axes at two different depths and
would not line up. Servos at the outer ends keeps **both shafts on one axis**, and as a bonus the
carrier only needs to be 18 mm deep instead of 32.

```
| SG90 |<-- flap A -->| post |<-- flap B -->| SG90 |    171.6 mm
  23.3      45.4        10        45.4        23.3
```

Both flaps' stub axles enter the **same through-bore** in the post from opposite sides, with a
2.2 mm gap between their tips.

| | |
|---|---|
| Bin clear volume | **45.4 × 72.4 × 37.5 mm** |
| Flap | 45.4 × 72.4 × 3 mm |
| Flap mass | **15 g** (computed from the mesh) |
| Hinge axis | z = 39 mm above the drawer floor, y = 9 mm from the back wall |
| Live cells | A1, A2 — one large drawer |
| Dummy cells | 2 small drawers, empty shells |
| Material | PETG, 4 perimeters, 40% infill |
| Colour | dark grey or black body, yellow flaps on live cells |

A 45.4 × 72.4 bin takes a standard 40 × 40 mm insert box with 5 mm to spare, and two of them
front-to-back.

Yellow flaps on the live cells are intentional: they read as a designed accent, reinforce the
pick-to-light idea, and stop the object looking like a 3D-printing experiment.

### 3.3 Branding

`obj_1_Ryobi badge.stl` is a **separate part — do not print it.** The front has a plain cutout
without it. Check whether the top bay carries an etched wordmark; if so, delete or sand it. Shipping
a demonstrator carrying another manufacturer's marks is both a taste problem in front of a buyer and
a trademark problem if this is ever sold.

### 3.4 Hinge carrier — the critical part

Because both cells sit side by side, **both flaps share one hinge axis** running the full width of
the drawer along its back edge. That allows the whole hinge assembly to be **a single printed part**:
a carrier bar 172.6 mm long × ~35 mm deep × ~34 mm tall, dropped in against the drawer's back wall,
with the hinge axis at z ≈ 44 mm above the drawer floor.

Printing it as one part is not a preference — it is what guarantees all four bearing features come
off the same print and stay collinear.

**Outer ends — the servos.** Two SG90s stand **upright**, tabs vertical, in open-topped pockets
(23.3 × 12.8, floor at z = 17.1) so the part prints without supports and a servo can be swapped in
seconds. Shafts point **inward** along the hinge axis. Each is trapped by a printed retainer bar on
two M2 screws rather than through its own tab holes — the tabs sit mid-body along the shaft axis and
are awkward to reach, and the bar is both easier to model and faster to service.

**Centre — the idler post.** A 10 mm post carrying a single Ø4.7 bore straight through. Both flaps'
Ø3.85 stub axles enter it from opposite sides, 2.5 mm each, leaving a 2.2 mm gap. The servo drives
one end of each flap; the post carries the other.

**Profile.** The carrier is 52 mm tall only at the three housings (two servos, one post) and drops
to a 20 mm web in between, so the flaps swing clear over it.

**Coupling.** The single-arm horn from the servo bag mounts on the spline and screws to a 3 mm
printed drive arm on the flap, using the horn holes at r = 11 mm and r = 16 mm with 2 × M2×6.

### 3.5 SG90 reference dimensions

| Feature | Value |
|---|---|
| Body | 22.8 × 12.2 × 22.7 mm |
| Overall length across tabs | 32.2 mm |
| Mounting hole pitch | 27.8 mm, 2 × Ø2.0 |
| Tab height from base | 15.9 mm |
| Shaft centre from body end | 5.9 mm |
| Height to shaft top | 29.0 mm |
| Spline | Ø4.8, 20 tooth |
| Stall torque | 1.8 kg·cm @ 4.8 V |
| Stall current | ~700 mA |

### 3.6 Print tolerances

| Feature | Nominal | Model at | Reason |
|---|---|---|---|
| Servo pocket L × W | 22.8 × 12.2 | **23.1 × 12.5** | 0.15/side — snug, no rattle, hand-fittable |
| Pocket depth across tabs | 32.2 | **32.6** | tabs must seat flat or the shaft skews |
| M2 pilot boss | — | **Ø1.6** | self-tappers cut their own thread in PETG |
| Shaft boss clearance | Ø9 | **Ø10.0** | boss must never rub the printed wall |
| Stub axle / bore | Ø4 | **4.0 / 4.35** | loose running fit; a tight one binds the servo |
| Flap-to-wall gap | — | **0.6 all round** | printed flaps warp slightly |

### 3.7 Load check

Flap is 69 × 88 × 3 mm PETG ≈ 16 g, ≈ 18 g with the drive arm and screws. Centre of mass ≈ 44 mm
from the hinge. Required torque ≈ 0.018 kg × 4.4 cm ≈ **0.08 kg·cm**; call it **0.15 kg·cm** with
hardware and friction. Against 1.8 kg·cm available that is a **12× margin** — comfortably enough to
drive the flap slowly and silently, and enough headroom that a warped flap rubbing slightly will
still open rather than stall.

### 3.8 The failure mode to design against

If a servo shaft axis and its Ø4.2 idler bore are not collinear, that flap binds and the SG90 stalls
at 700 mA until something gives.

**Acceptance test:** with the servo unplugged and the horn detached, each flap must fall closed under
its own weight. If it does not, ream the bore before applying power.

### 3.9 Servo travel and the open-drawer interlock

**70° only.** Do not command the full 0–180° range. Software must clamp travel.

**The drawer must be fully extended before any flap opens.** The flap swings up and back over the
hinge carrier; with the drawer pushed in, the bay above it is in the way. This is not a defect —
the commercial cabinets work the same way, releasing one drawer at a time and committing the transaction
on drawer close.

For v1 the kiosk simply instructs the operator to pull the drawer out first, and the flap will not
release until they confirm. **A drawer-position switch is the correct fix and is a ₹30 part**; add it
before any customer touches the unit, because an operator who opens a flap into a closed bay will
strip a servo on the first try.

---

## 4. Electronics

### 4.1 Bill of materials

Everything except filament and fasteners is already on hand.

| Item | Qty | Status |
|---|---|---|
| ESP32-S3 dev board | 1 | on hand |
| TowerPro SG90 servo | 2 | on hand |
| 4×4 matrix keypad | 1 | on hand |
| 16×2 LCD + I2C backpack | 1 | on hand |
| IR obstacle board | 2 | on hand |
| LED + 220 Ω resistor | 2 | on hand |
| 5 V 3 A supply | 1 | on hand |
| 1000 µF electrolytic | 1 | on hand |
| M2×8 self-tap, M2×6 machine screws | 4 + 8 | buy, ~₹100 |
| Microswitch, drawer-position interlock | 1 | buy, ~₹30 |
| PETG filament, full chest | ~700 g | ~₹550 |
| MG90S metal-gear servos (spares) | 4 | buy, ~₹1,000 |

**Out-of-pocket cost of the demonstrator: about ₹1,700, most of it spare servos and filament.**
Phase 2 alone needs only ~250 g of filament.

### 4.2 Pin assignment (ESP32-S3)

| Function | GPIO |
|---|---|
| Servo A1 / A2 | 4 / 5 |
| IR flap sensor A1 / A2 | 6 / 7 |
| Status LED A1 / A2 | 15 / 16 |
| Keypad rows | 8, 9, 10, 11 |
| Keypad columns | 12, 13, 14, 21 |
| I²C SDA / SCL (LCD) | 17 / 18 |
| Drawer-position switch | 3 (input, pull-up) |

Avoid GPIO 19–20 (USB) and 26–37 (flash/PSRAM on S3 modules).

### 4.3 Power

- Servos run on their **own 5 V rail**, not the ESP32's 5 V pin. Two servos at 700 mA stall is
  1.4 A and will brown the board out.
- **Common ground** between the servo rail and the ESP32.
- **1000 µF across the servo rail** to absorb the inrush when a servo starts.
- **Detach the PWM signal after every move** (write 0 duty / `ledcDetach`). This stops jitter,
  eliminates holding current, and means the unit draws almost nothing sitting idle in a meeting.

### 4.4 Known electrical risk

The SG90 is specified for a 5 V logic signal; the ESP32-S3 drives 3.3 V. In practice most SG90s
accept 3.3 V PWM. **Verify on the bench in phase 1.** If a servo is unreliable, add a single-channel
level shifter or a 2N7000-based shifter — a ₹20 fix, but find out early rather than mid-build.

---

## 5. Firmware

### 5.1 Architecture

ESP32-S3 runs a WiFi **access point** named `TOOLCELL` and serves the kiosk itself. No router, no
internet, no laptop. The unit is fully self-contained and works in any meeting room.

### 5.2 State machine

```
IDLE ──PIN entered──▶ AUTH ──valid──▶ SELECT ──pick──▶ RELEASED
  ▲                     │                 │               │
  │                  invalid          timeout 20s    flap opens
  │                     │                 │               ▼
  └───────── COMMIT ◀── CLOSING ◀── OPEN ─┘         (servo → 70°)
```

- `IDLE` — both flaps shut, LEDs red, servos detached.
- `AUTH` — PIN entered on the keypad; LCD shows the operator's name or `ACCESS DENIED`.
- `SELECT` — kiosk lists only the tools this operator may draw. Others are shown greyed with the
  reason.
- `RELEASED` — target LED green, servo sweeps 0° → 70°, then detaches.
- `OPEN` — waiting for the IR sensor to report the flap shut.
- `CLOSING` — servo returns 70° → 0°, then detaches.
- `COMMIT` — transaction appended to the log, stock decremented, LED back to red.

**Timeout:** if the flap is not closed within 30 s, flash the LED, log an exception with
`result=TIMEOUT`, and return to `IDLE` without decrementing stock.

### 5.3 HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | kiosk HTML, CSS and JS (single file, gzipped in LittleFS) |
| `GET` | `/api/state` | cells, stock levels, current machine state |
| `POST` | `/api/auth` | `{pin}` → `{name, shift, allow[], limit}` |
| `POST` | `/api/pick` | `{cell, qty, session}` → releases the flap |
| `GET` | `/api/events` | server-sent events, pushes state to the kiosk live |
| `GET` | `/api/log` | full transaction log as CSV |

### 5.4 Data model

`/data/config.json` in LittleFS, editable without reflashing:

```json
{
  "cells": [
    { "id": "A1", "servo": 0, "tool": "CNMG 120408-PM 4325",
      "desc": "Turning insert, Sandvik", "qty": 8, "min": 4, "maxPerPick": 2 },
    { "id": "A2", "servo": 1, "tool": "R390-11 T3 08M-PM",
      "desc": "Milling insert, Sandvik", "qty": 12, "min": 6, "maxPerPick": 4 }
  ],
  "users": [
    { "pin": "4417", "name": "R. Kumar", "shift": "A", "allow": ["A1", "A2"], "limit": 4 },
    { "pin": "2290", "name": "S. Patil", "shift": "B", "allow": ["A2"],       "limit": 2 }
  ]
}
```

Note that **S. Patil cannot draw from A1.** This is deliberate — see §7.

### 5.5 Transaction log

Appended as CSV to `/log.csv` in LittleFS:

```
ts,pin,name,cell,tool,qty,stock_after,result
```

`result` is one of `OK`, `DENIED`, `TIMEOUT`, `BELOW_MIN`.

Timestamps come from `millis()` since boot plus a session start time set by the kiosk on first
connect — there is no RTC and no internet, and adding either is not worth it for a demo.

---

## 6. Kiosk UI

Single-page, served from flash, no external assets — it must work with no internet.

- **Lock screen.** Large keypad prompt. Mirrors what the operator types on the physical keypad.
- **Tool list.** Cards for each cell: tool code, description, stock on hand, minimum level, and a
  quantity stepper clamped to `min(maxPerPick, user.limit)`. Cells the operator may not draw are
  greyed with an explicit reason, never hidden.
- **Plan view.** A simple 2D top-down plan of the four compartments. The target cell pulses. This is
  the honest, legible answer to the commercial 3D view; a bad 3D view is worse than a good 2D one.
- **Live state.** Driven by server-sent events, so the screen tracks the physical flap without
  polling.
- **Log view.** The last 20 transactions, in plain view. **This is the screen that sells the
  product** — it is the audit trail made visible.

Visual direction: dark UI, one accent colour matching the yellow flaps, large type readable at
arm's length in bad factory lighting.

---

## 7. The demo script

Ninety seconds. Rehearse it.

1. **"This is one drawer of a cabinet."** Point at the four bins. Two are live.
2. **Type 4417.** LCD reads `R. KUMAR / SHIFT A`. Tablet lists two tools.
3. **Tap the turning insert, quantity 2.** The A1 flap **opens itself**. Take two.
4. **Close it.** Stock updates 8 → 6 on the tablet.
5. **Type 2290.** LCD reads `S. PATIL / SHIFT B`. **Only one tool is listed now.**
6. **Tap the greyed-out one.** `NOT AUTHORISED — SHIFT B`. Nothing opens.
7. **Show the log screen.** Every pick, with a name and a timestamp against it.

Step 6 is the whole pitch. It is the moment the buyer understands they are buying accountability,
not a box. Steps 5–7 are only possible because there are two live cells — which is why both servos
are used rather than keeping one as a spare.

---

## 8. Build plan

| Phase | Work | Estimate |
|---|---|---|
| 1 | Bench rig: servo, keypad, LCD, IR on a breadboard. **Verify 3.3 V PWM drives the SG90.** | 1 evening |
| 2 | Print `obj_11` (one large bay), `obj_25` (large drawer), `obj_9` (its front), 4 rails, 4 feet. Fit the hinge carrier. Tune tolerances. Pass the falls-shut-unpowered test. | 2 evenings |
| 3 | Firmware: state machine, config loading, logging, HTTP API. | 1 weekend |
| 4 | Kiosk UI, served from LittleFS. | 1 weekend |
| 5 | Print the remaining bays and dummy drawers, cable management, final assembly. | 1 weekend |

Roughly **three weekends** to a demonstrable unit.

Phase 2 is the risk. Budget for three iterations of the hinge carrier; the collinearity is the hard
part and no amount of care in CAD substitutes for measuring the printed part. **Do not print the
remaining three bays until the mechanism works** — that is how a weekend disappears.

---

## 9. Path to a production unit

Not for v1, recorded so v1 does not paint us into a corner.

**Make it an actual lock.** Replace the hinge-mounted servo with a **sliding bolt**: the servo drives
a printed bolt 10 mm sideways through a keeper loop hanging from the flap's front edge. A pull on
the flap loads the loop *across* the bolt, so force goes into the printed guide channel and never
reaches the servo. Add a counterweight behind the hinge — roughly 40 g, two M8 nuts in a printed
pocket — and the flap still opens itself when the bolt clears, with no spring. This gives both
properties with one servo, at the cost of one more printed part.

**Mirror the incumbent price ladder.** Entry tier is one solenoid per *drawer* plus LEDs — ten actuators
for a whole cabinet, cheap, and adequate for most shops. Premium tier is a servo per *compartment*.
Quote the entry tier; demo the premium tier.

**Indicative cabinet economics** (10 drawers, ~120 compartments, premium tier):

| Item | Cost |
|---|---|
| Steel 10-drawer cabinet, local fabricator | ₹40–60k |
| 120 × (MG90S + printed parts + LED + wiring) @ ₹250 | ₹30k |
| 10 × (ESP32 + servo driver) | ₹9k |
| 5 V 20 A supply, harness, connectors | ₹6k |
| Tablet | ₹15k |
| Assembly labour | ₹30k |
| **Hardware total** | **≈ ₹1.4 lakh** |

Against the incumbent ~₹20 lakh, a ₹4–5 lakh sale price gives a 4–5× undercut with healthy margin.

**These figures are estimates and have not been quoted.** Get a real fabricator quote before any of
them appear in front of a customer.

**The real work is software.** Cost centres, reorder triggers, per-group budgets, CAM and presetter
integration — that is what the incumbents charge for and what a serious competitor has to build.

---

## 10. Open questions

1. **Which two tools go in the live cells?** The spec assumes Sandvik CNMG 120408 and R390 inserts
   because they are recognisable to any turning or milling shop. If there is a specific target
   customer, use tools they actually run.
2. **Is there a named prospect?** The demo script is sharper if step 5's second operator is a real
   shift pattern from a real shop.
3. **Fabricator quote for the steel cabinet** — required before the §9 economics can be quoted.
