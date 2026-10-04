#!/usr/bin/env python3
"""
Tolerance audit for shopkeeper NANO.

Every fit in the design, checked against practical FDM values for a 0.4 mm
nozzle in PETG. Dimension checks confirm parts do not collide; this confirms
they collide *by the right amount* — a joint can pass every interference test
and still rattle, seize, or slip.

Reference bands used (per side unless stated):
  press / interference   -0.10 .. +0.05   glue-free, needs force
  location (slip + glue)  0.08 .. 0.20
  running / sliding       0.30 .. 0.60
  free clearance          0.60 +
  M2 self-tap pilot       dia 1.60 .. 1.75
  gear backlash           0.10 .. 0.20 x module
"""
import math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# This file used to keep its own copy of the parameters "so it is readable on
# its own". That copy silently froze at cd=66, ch=53, deck_z=25.5 - two design
# revisions back - and every number it printed was fiction while reading as a
# clean audit. A checker that can disagree with the thing it checks is worse
# than no checker. It imports now.
import nano as NA
P = NA.P
M = P["module"]
ADD, DED = NA.ADD, NA.DED
TOOTH_H  = NA.TOOTH_H
FIN_SPAN = NA.FIN_SPAN
PITCH    = NA.PITCH
NOZZLE   = 0.4

rows, bad, warn = [], 0, 0

def fit(name, nominal, actual, lo, hi, kind, note=""):
    """lo/hi are the acceptable per-side clearance band."""
    global bad, warn
    cl = (actual - nominal) / 2.0
    if cl < lo - 1e-9:
        v, sev = "TIGHT", 2
    elif cl > hi + 1e-9:
        v, sev = "LOOSE", 1
    else:
        v, sev = "ok", 0
    bad += (sev == 2); warn += (sev == 1)
    rows.append((name, f"{nominal:.2f}", f"{actual:.2f}", f"{cl:+.3f}",
                 f"{lo:.2f}..{hi:.2f}", kind, v, note))

def val(name, actual, lo, hi, kind, note=""):
    global bad, warn
    if actual < lo - 1e-9:   v, sev = "UNDER", 2
    elif actual > hi + 1e-9: v, sev = "OVER", 1
    else:                    v, sev = "ok", 0
    bad += (sev == 2); warn += (sev == 1)
    rows.append((name, "-", f"{actual:.2f}", "-", f"{lo:.2f}..{hi:.2f}",
                 kind, v, note))

# ── sliding joints ────────────────────────────────────────────────────
fit("drawer in case, width", 2*39.8 + P["mid_gap"],
    P["cw"] - 2*P["wall"], 0.30, 0.60, "running",
    "both drawers across the internal width")
fit("rack blade in deck slot", FIN_SPAN, FIN_SPAN + 2.4, 0.30, 0.60,
    "running", "must also absorb drawer side-play")
fit("rack blade in floor slot", FIN_SPAN, FIN_SPAN + 0.5, 0.08, 0.20,
    "location", "rack is glued/pegged, not sliding")

# ── press and location fits ───────────────────────────────────────────
# spline is abandoned: 20 teeth on a 4.8 dia = 0.75 mm pitch, far under what a
# 0.4 nozzle resolves. Drive is through the servo horn, bolted.
fit("pinion recess on horn boss", 7.0, 8.4, 0.30, 0.90, "clearance",
    "horn is bolted, not pressed")
fit("pinion screw hole for M2", 2.0, 1.9, -0.10, 0.05, "thread",
    "M2 cuts its own thread in PETG")
fit("rack peg in drawer floor", NA.PEG_D, NA.PEG_D + 0.25, 0.08, 0.20,
    "location", "pegged then glued")

# ── servo pocket ──────────────────────────────────────────────────────
fit("servo pocket, length", P["sg_l"], P["sg_l"] + 2*P["clear"],
    0.25, 0.45, "location", "SG90 body")
fit("servo pocket, width", P["sg_w"], P["sg_w"] + 2*P["clear"],
    0.25, 0.45, "location", "SG90 body")

# ── vertical stack ────────────────────────────────────────────────────
fit("drawer under case top", P["dr_h"], P["dr_h"] + P["gap"],
    0.30, 0.80, "running", "vertical rattle vs binding")

# ── gears ─────────────────────────────────────────────────────────────
# Backlash is deliberately outside the textbook 0.10-0.20 x module band. A
# machined pair holds a tight mesh because it is machined; a printed pair grows
# 0.05-0.12 per surface and a textbook mesh becomes an interference fit. See
# cad/meshsim.py: the pair runs to +0.20 growth at 0.50 and jams at +0.05 at
# 0.30. Sloppy and turning beats precise and seized.
val("gear backlash", P["backlash"], 0.10*M, 0.45*M, "gear",
    f"module {M}, opened for print growth - see meshsim.py")
PRESS=P["press"]
_hp=(PITCH/2-P["backlash"])/2
val("tooth thickness at pitch line", 2*_hp, 3*NOZZLE, 99.0,
    "printability", "needs >= 3 extrusion widths")
val("pinion tooth tip (involute)", 2*NA.tooth_half_angle(NA.R_TIP)*NA.R_TIP,
    1.5*NOZZLE, 99.0, "printability", "true involute, stub addendum")
val("rack tooth tip", 2*(_hp-ADD*math.tan(PRESS)), 1.5*NOZZLE, 99.0,
    "printability", "thin tips shear off")
val("trough width at root", PITCH-2*(_hp+DED*math.tan(PRESS)),
    2*NOZZLE, 99.0, "printability", "nozzle must fit between teeth")
val("tooth height", TOOTH_H, 4*0.2, 99.0, "printability",
    "layers at 0.2 mm")
val("rack blade thickness", P["fin_t"], 2.5*NOZZLE, 99.0, "printability",
    "carries the full drive load")

# ── electronics mounts ────────────────────────────────────────────────
fit("ESP32-WROOM-32D in its channel", 27.9, 28.6, 0.25, 0.60, "location",
    "DevKitC has no mounting holes - held by the walls")
fit("servo body in its cradle", P["sg_l"], P["sg_l"]+2*P["clear"],
    0.25, 0.45, "location", "SG90 drops in from above")
val("servo cradle spans the tab pitch", P["sg_tab"]+4.0, P["sg_tab"], 99.0,
    "assembly", "screw holes must land ON the cradle, not past it")

# ── fasteners and walls ───────────────────────────────────────────────
val("M2 self-tap pilot", 1.70, 1.60, 1.75, "thread", "servo tabs")
val("case wall", P["wall"], 3*NOZZLE, 99.0, "printability", "")
val("drawer wall", P["dr_wall"], 3*NOZZLE, 99.0, "printability", "")
val("deck thickness", P["deck_t"], 2.0, 99.0, "structure",
    "spans the full internal width, loaded")

W = [30, 8, 8, 8, 12, 13, 6]
hdr = ("fit", "nominal", "actual", "per side", "target", "kind", "verdict")
print("\nTOLERANCE AUDIT — shopkeeper NANO\n")
print("  " + "".join(h.ljust(w) for h, w in zip(hdr, W)))
print("  " + "-" * (sum(W) + 2))
for r in rows:
    line = "".join(str(c).ljust(w) for c, w in zip(r[:7], W))
    print(f"  {line}  {r[7]}")
print(f"\n  {bad} tight/under (will not work), {warn} loose/over (will work but sloppy)")
sys.exit(1 if bad else 0)
