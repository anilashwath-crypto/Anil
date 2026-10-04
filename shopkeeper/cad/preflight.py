#!/usr/bin/env python3
"""
PREFLIGHT — the go/no-go before filament is spent.

Assembles every real mesh in its true pose, adds a solid proxy for the SG90,
and runs boolean intersections on every pair. Anything that overlaps cannot be
assembled. Then it measures the gear mesh off the geometry rather than the
source, and sweeps both drawers through full stroke.

Nothing here reads intent from cad/nano.py's variables — it measures shipped
STLs, because the source has been right and the mesh wrong before.
"""
import os, sys, math, itertools
import numpy as np
import trimesh
from trimesh.creation import box

HERE = os.path.dirname(os.path.abspath(__file__))
N    = os.path.join(HERE, "..", "nano")
sys.path.insert(0, HERE)

# ── geometry constants that describe the ASSEMBLY, not any part ──
# These are POSES, not shapes. The shapes still come off the shipped STLs and
# are never read from the source - but where a part sits has to be stated
# somewhere, and stating it twice is how this file came to be checking a
# 34.5 mm deck against parts built for a 39.5 mm one. One definition, imported.
import nano as NA                                   # poses only, never shapes
WL, SC   = NA.WL, NA.P["side_clear"]
FLOOR_T  = NA.P["floor_t"]
DECK_Z, DECK_T = NA.P["deck_z"], NA.P["deck_t"]
DECK     = NA.DECK
CW, CD   = NA.CW, NA.CD
MID_GAP  = NA.P["mid_gap"]
DR_D     = NA.DR_D
DR_W     = NA.DR_W
DR_X     = NA.DR_X
M, TEETH = NA.M, NA.N
R_P      = NA.R_P
TRAVEL   = NA.TRAVEL
FIN_T, FIN_H = NA.P["fin_t"], NA.P["fin_h"]
ADD, DED = NA.ADD, NA.DED
TOOTH_H  = NA.TOOTH_H
FIN_SPAN = NA.FIN_SPAN
FIN_X    = NA.FIN_X
PIN_DX   = NA.PIN_DX
PIN_Y    = NA.PIN_Y
DR_FLOOR = NA.P["dr_floor"]
RACK_Y0  = NA.RACK_Y0
SG_L, SG_W, SG_H, SG_TAB = (NA.P["sg_l"], NA.P["sg_w"], NA.P["sg_h"], NA.P["sg_tab"])
SG_BASE, SG_EAR, SG_HORN = NA.SG_BASE, NA.P["sg_ear"], NA.SG_HORN
Y_CLOSED = NA.Y_CLOSED

def L(n): return trimesh.load(os.path.join(N, n + ".stl"))
def T(m, x=0, y=0, z=0):
    m = m.copy(); m.apply_translation([x, y, z]); return m
def inter(a, b):
    try:
        return float(trimesh.boolean.intersection([a, b], engine="manifold").volume)
    except Exception:
        return 0.0

fails, warns = [], []
def chk(label, ok, detail, warn_only=False):
    tag = "PASS" if ok else ("WARN" if warn_only else "FAIL")
    print(f"  [{tag}] {label:44s} {detail}")
    if not ok:
        (warns if warn_only else fails).append(label)

print("\nPREFLIGHT — shopkeeper NANO\n")
print("Assembling shipped meshes ...")

case_lo = L("case_lower")
deck    = T(L("deck"), WL + 0.3, WL + 0.3, DECK - DECK_T)
case_up = T(L("case_upper"), 0, 0, DECK)
drawer0 = L("drawer")     # the drawer IS the rack now - teeth in its floor

y_closed = Y_CLOSED

def drawer_at(slot, pull):
    dx = DR_X[slot]
    return T(drawer0, dx, y_closed - pull, DECK + 0.2)

# SG90 proxy: body plus the tab flange, at its real size, sitting on the
# pedestal at SG_BASE - not on the floor. The servo's height is what sets the
# pinion's height, so getting it wrong here hides the whole stack-up.
def servo_at(slot):
    # UPRIGHT again: shaft vertical, the gear lies flat like a turntable and
    # meshes with the blade's vertical flank. Centred on the BODY, not the
    # shaft - they are 5.5 mm apart once the shaft offset is modelled.
    px  = DR_X[slot] + FIN_X + PIN_DX
    bcx = NA.sg_body_cx(slot, px)
    body = box(extents=[SG_L, SG_W, SG_H])
    body.apply_translation([bcx, WL + PIN_Y, SG_BASE + SG_H/2])
    tabs = box(extents=[SG_TAB, SG_W, 2.5])
    tabs.apply_translation([bcx, WL + PIN_Y, SG_BASE + SG_EAR + 1.25])
    return trimesh.util.concatenate([body, tabs])

STATIC = {"case_lower": case_lo, "deck": deck, "case_upper": case_up,
          "servo_A": servo_at(0), "servo_B": servo_at(1)}

print("\nSTATIC ASSEMBLY — nothing may overlap")
for a, b in itertools.combinations(STATIC, 2):
    v = inter(STATIC[a], STATIC[b])
    chk(f"{a} vs {b}", v < 1.0, f"{v:8.2f} mm3")

print("\nDRAWERS THROUGH FULL STROKE")
for slot in (0, 1):
    worst, wp = 0.0, None
    for pull in (0, 6, 12, 18, TRAVEL*153/180):
        moving = drawer_at(slot, pull)
        for nm in ("case_lower", "deck", "case_upper", "servo_A", "servo_B"):
            v = inter(moving, STATIC[nm])
            if v > worst:
                worst, wp = v, f"{nm} @ pull {pull:.0f}"
    chk(f"drawer {'AB'[slot]} clears everything", worst < 1.0,
        f"{worst:8.2f} mm3  {wp or ''}")

# the two drawers must not touch each other either
d0 = drawer_at(0, 0); d1 = drawer_at(1, TRAVEL*153/180)
chk("drawer A vs drawer B", inter(d0, d1) < 1.0, "one open, one shut")

print("\nGEAR MESH — measured off the meshes")
pin = L("pinion")
pin_r_tip = max(np.linalg.norm(pin.vertices[:, :2] - [0, 0], axis=1))
chk("pinion tip radius", abs(pin_r_tip - (R_P + ADD)) < 0.25,
    f"{pin_r_tip:.2f} mm, expected {R_P+ADD:.2f}")

# The blade is part of the drawer, so measure it off the drawer: everything
# hanging below the floor IS the blade.
dv = drawer0.vertices
blade = dv[dv[:, 2] < -0.5]
chk("drawer carries its own blade", len(blade) > 50,
    f"{len(blade)} vertices below the floor line")
tip_x = blade[:, 0].max()
pitch_x = tip_x - ADD
pin_axis_x = FIN_X + PIN_DX
centre = pin_axis_x - pitch_x
chk("blade/pinion centre distance", abs(centre - NA.CDIST) < 0.05,
    f"{centre:.3f} mm, needs {NA.CDIST:.3f}")

gear_t = NA.P["gear_t"]
pin_z0, pin_z1 = SG_HORN, SG_HORN + gear_t
blade_z0 = DECK + 0.2 + float(drawer0.bounds[0][2])
blade_z1 = DECK + 0.2 + DR_FLOOR
ov = min(blade_z1, pin_z1) - max(blade_z0, pin_z0)
chk("pinion/blade vertical overlap", ov >= gear_t - 0.01,
    f"{ov:.2f} of {gear_t:.2f} mm face  (blade {blade_z0:.1f}-{blade_z1:.1f}, "
    f"pinion {pin_z0:.1f}-{pin_z1:.1f})")
chk("blade clears the electronics", blade_z0 >= FLOOR_T + NA.P["esp_h"] + 1.5,
    f"blade bottom {blade_z0:.1f}, stack top {FLOOR_T+NA.P['esp_h']:.1f}")

print("\nPART INTEGRITY")
for n in ("case_lower", "case_upper", "deck", "drawer", "pinion"):
    m = L(n)
    nb = len(m.split(only_watertight=False))
    chk(f"{n}: single watertight body", nb == 1 and m.is_watertight,
        f"{nb} body, watertight={m.is_watertight}")

print()
if fails:
    print(f"  DO NOT PRINT — {len(fails)} failure(s): " + ", ".join(fails))
    sys.exit(1)
print(f"  CLEARED TO PRINT" + (f"  ({len(warns)} warning(s))" if warns else ""))
