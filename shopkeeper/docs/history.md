# Design lineage

The shipping machine is the **NANO** (`cad/nano.py` → `nano/*.stl`). It is the fifth generator in
this repo, and the four before it are still here, still runnable, and still described below.

They are kept deliberately. The pitch this project makes is a provenance argument — *we know why
every number is what it is* — and half of that evidence is the record of the numbers that were
wrong. Each generation was killed by something specific, and the thing that killed it is the
reason the next one is shaped the way it is.

| Generation | Script | Envelope | Mechanism | Killed by |
|---|---|---|---|---|
| ToolCell insert | `cad/toolcell.py` | fits a 172.6 × 91 × 52 mm drawer | hinged flap on the servo horn | depended on somebody else's toolbox |
| ToolCell cabinet | `cad/cabinet.py` | 216 × 136 × 169 mm | m1.5 × 24T, sliding **lids**, 56.5 mm | a lid that opens half a bin is not a drawer |
| slidebox | `cad/slidebox.py` | 216 × 136 × 269 mm | m1.5 × 24T, sliding **drawers**, 56.5 mm | too big to carry to a meeting |
| shopkeeper MINI | `cad/mini.py` | 120 × 90 × 80 mm | m1.5 × 14T, 33.0 mm | one drawer cannot demonstrate access *control* |
| **shopkeeper NANO** | `cad/nano.py` | **92 × 74 × 66 mm** | **m1.25 × 16T, 31.42 mm** | — current |

---

## 1. ToolCell insert — `cad/toolcell.py`

A parametric generator for parts that drop into the large drawer of a **Ryobi Mini Desktop
Toolbox**. Frame of reference was drawer-local: 172.6 mm across, 91 mm deep, 52 mm of height to
play with, with 1.0 mm of total side-to-side slack so the carrier could be dropped in.

Four compartments in one carrier, two of them live, each closed by a hinged flap driven straight
off an SG90 horn.

It went because the whole proposition rests on the machine being *ours*. A demonstrator built
inside a retail toolbox invites the question of what happens when that toolbox is discontinued,
and it caps every dimension at somebody else's mould.

## 2. ToolCell cabinet — `cad/cabinet.py`

The first purpose-built enclosure. Nothing in it depends on the Ryobi model; every dimension is
derived from the mechanism outward, so the parts are guaranteed to fit each other.

A three-module stack, 216 × 136 mm on the floor, printable on a 256 mm bed:

```
   control head    42 mm   4×4 keypad on top, 0.91" OLED in front, tablet cradle
   drawer bay      60 mm   the live drawer — two bins, two servos
   electronics bay 55 mm   ESP32-S3, 5 V supply, terminal blocks
   feet            12 mm
                  ------
                  169 mm
```

Each bin is **99 × 75 × 32 mm** and closed by a lid that **slides** on a rack driven by an SG90
through a printed 24-tooth pinion. 180° of servo gives 56.5 mm of travel, opening 57% of the bin.

An ESP32-S3 runs its own WiFi access point and serves the operator kiosk to any phone or tablet —
no router, no internet, no laptop. That decision survived into the NANO unchanged.

### Why sliding lids, not hinged flaps

This is the argument that killed generation 1, and it is worth keeping in full because it is the
first time measurement beat intuition on this project.

The first design used a hinged flap driven straight off the servo. It worked on paper and was
wrong in practice: a flap that opens 66° rises **76 mm above the drawer**, so the drawer had to be
pulled its full 105 mm out every single time. Anything less and the servo drives the flap into the
underside of the bay above and strips its nylon gears.

Sliding needs **zero vertical clearance**. Drawer position stops mattering, the servo can never
stall against an obstruction, and the interlock switch and limit stop both disappear from the BOM.

It also gives something for free: the two lids ride at different heights and slide over one
another, so **only one bin can be open at a time** — which is exactly what the commercial cabinets
enforce.

The cost is that a lid opens about half its bin rather than swinging fully clear. That cost is what
eventually retired this design: a lid that slides halfway off a fixed box reads, in a room, as a
box with a broken lid. Nobody watching it says *that machine just gave me a tool*.

## 3. slidebox — `cad/slidebox.py`

The idea that fixed it: stop moving the lid and **move the drawer**.

A toothed fin hangs from the drawer's underside through a slot in the bay deck. A vertical-shaft
SG90 sits under the deck with a 24-tooth pinion on it, and 180° of servo becomes 56.5 mm of drawer
travel. Nothing rises above the cabinet and the drawer cannot escape — at full travel, 69 mm of a
126 mm drawer is still captured by the bay.

```
   head            45   4×4 keypad, 0.91" OLED, tablet cradle
   drawer bay A    81   motorised drawer
   drawer bay B    81   motorised drawer
   electronics     50   ESP32-S3, 5 V supply, terminal blocks
   feet            12
                  ---
                  269 mm tall, 216 × 136 footprint
```

The drive scheme is the one the NANO still uses. The enclosure was the problem: `case_base` alone
generates at 279 g, the whole build is over a kilogram of filament and the better part of two days
on the plate, and a demonstrator that cannot be carried into a meeting under one arm does not get
demonstrated.

## 4. shopkeeper MINI — `cad/mini.py`

Smallest credible motorised-drawer demonstrator. One module, one drawer that drives itself out,
everything inside. 120 × 90 × 80 mm.

```
   top plate    keypad recess, 0.91" OLED in the front face
   drawer       driven out 33 mm by an SG90 through a 14T pinion
   deck         drawer runs on it, slotted for the drive fin
   mech bay     SG90 (shaft up) + pinion + ESP32-S3 + wiring
```

m1.5 × 14 teeth, pitch radius 10.5, so half a turn is 33.0 mm. The drawer is 111.8 × 77.5 × 28 mm.
As generated, `case` + `drawer` + `pinion` come to 217 g.

Meshes are still in `mini/`, including a plate.

It went for a reason that is commercial rather than mechanical. **One drawer cannot demonstrate
access control.** The entire pitch is *the one drawer you are cleared for opens and the other one
does not* — and with a single drawer there is no other one. A machine with two drawers makes the
argument by itself, without a slide.

## 5. shopkeeper NANO — `cad/nano.py`

Current. See the [README](../README.md).

Two drawers **side by side** rather than stacked, so one mechanism deck serves both. Stacking would
have doubled the height, because a vertical SG90 costs 26 mm of dead space under every deck.

Gearing dropped from m1.5 × 14T to m1.25 × 16T — a smaller module for a smaller case, more teeth to
hold the pitch radius near 10 mm and keep half a turn worth 31.42 mm of travel. That change forced
**stub teeth** (0.8 module addendum instead of 1.0): a full-depth involute at m1.25 comes to a
0.45 mm tip, which is under one extrusion width, so the machine rounds it off and the contact it
was supposed to make never happens.

---

## What each generation taught the next

- **Insert → cabinet.** Own the enclosure, or the product is a fixture on someone else's part.
- **Cabinet → slidebox.** Move the drawer, not the lid. A machine that hands you a tool is a
  different object from a box whose lid slid halfway open.
- **Slidebox → MINI.** Portable beats impressive. The unit has to be carried into the room.
- **MINI → NANO.** Two drawers, because the product being sold is *which one opens*.
- **All of them → the checkers.** `cad/preflight.py`, `cad/meshsim.py`, `cad/fitcheck.py` and
  `cad/overhangs.py` exist because on every one of these generations the source was right and the
  mesh was wrong at least once. They measure the shipped STLs rather than reading intent out of the
  parameters. `cad/tolerances.py` used to keep its own copy of the parameters "so it is readable on
  its own"; that copy silently froze two revisions back and printed a clean audit of a case that no
  longer existed.
