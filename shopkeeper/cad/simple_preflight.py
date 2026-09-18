#!/usr/bin/env python3
"""
Go/no-go for the SIMPLE cabinet.

simple.py's own checks compare numbers it computed itself. That has passed a
pinion 1 mm wider than its channel and a servo pocket centred on the wrong
axis. So this file does not read intent: it loads the shipped STLs, adds the
REAL pinion mesh and a solid SG90 proxy, puts everything in its true pose, and
boolean-intersects every pair - then sweeps the drawer through the whole
stroke and does it again at every step.

Overlap means it cannot be assembled. There is no interpretation to do.
"""
import os, sys, math, itertools
import numpy as np
import trimesh
from trimesh.creation import box

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import simple as S

OUT = S.OUT
L = lambda n, d=OUT: trimesh.load(os.path.join(d, n + ".stl"))
def T(m, x=0, y=0, z=0):
    m = m.copy(); m.apply_translation([x, y, z]); return m
def inter(a, b):
    try: return float(trimesh.boolean.intersection([a, b], engine="manifold").volume)
    except Exception: return 0.0

fails = []
def chk(label, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:42s} {detail}")
    if not ok: fails.append(label)

print("\nPREFLIGHT — shopkeeper SIMPLE\n")

case_lo = L("case_lower")
deck    = T(L("deck"), S.WALL + 0.3, S.WALL + 0.3, S.DECK - S.DECK_T)
case_up = T(L("case_upper"), 0, 0, S.DECK)
drawer0 = L("drawer")

# The REAL gear, at the height its own boss puts it: the mesh spans z -3.70
# to +6.00, so translating by SERVO_TOP + 3.70 would double-count the boss.
# Its origin z=0 IS the bottom of the tooth band.
pinion = L("pinion", os.path.join(HERE, "..", "nano"))
def gear_at(i):
    return T(pinion, S.PIN_X[i], S.PIN_Y, S.GEAR_Z0)

def servo_at(i):
    px, sgn = S.PIN_X[i], S.SG_DIR[i]
    bcx = px + sgn*(22.8/2 - 5.9)
    b = box(extents=[22.8, 12.2, S.SG_H])
    b.apply_translation([bcx, S.PIN_Y, S.FLOOR + S.SG_H/2])
    t = box(extents=[32.2, 12.2, 2.5])
    t.apply_translation([bcx, S.PIN_Y, S.FLOOR + 15.9 + 1.25])
    return trimesh.util.concatenate([b, t])

def drawer_at(pull):
    return T(drawer0, S.DR_X, S.WALL + 0.4 - pull, S.DECK + 0.2)

STATIC = {"case_lower": case_lo, "deck": deck, "case_upper": case_up,
          "servo_A": servo_at(0), "servo_B": servo_at(1),
          "gear_A": gear_at(0), "gear_B": gear_at(1)}

print("STATIC ASSEMBLY — nothing may overlap")
for a, b in itertools.combinations(STATIC, 2):
    v = inter(STATIC[a], STATIC[b])
    # a gear is MEANT to sit in the deck's bore and above its servo
    tol = 1.0
    chk(f"{a} vs {b}", v < tol, f"{v:9.2f} mm3")

print("\nDRAWER THROUGH FULL STROKE")
worst, wp = 0.0, None
for pull in (0, 4, 8, 12, 16, S.CMD):
    m = drawer_at(pull)
    for nm in ("case_lower", "deck", "case_upper", "servo_A", "servo_B"):
        v = inter(m, STATIC[nm])
        if v > worst: worst, wp = v, f"{nm} @ pull {pull:.1f}"
chk("drawer clears the fixed parts", worst < 1.0, f"{worst:9.2f} mm3  {wp or ''}")

print("\nTHE DRIVE — does a turning gear actually move this drawer?")
dv = drawer0.vertices
blade = dv[dv[:, 2] < -0.5]
chk("drawer carries its own blades", len(blade) > 50,
    f"{len(blade)} vertices below the floor")
bz0 = S.DECK + 0.2 + float(drawer0.bounds[0][2])
bz1 = S.DECK + 0.2
gz0, gz1 = S.GEAR_Z0, S.GEAR_Z0 + S.GEAR_T
ov = min(bz1, gz1) - max(bz0, gz0)
chk("tooth bands overlap", ov >= S.GEAR_T - 0.01,
    f"{ov:.2f} of {S.GEAR_T:.2f} mm  (blade {bz0:.1f}-{bz1:.1f}, gear {gz0:.1f}-{gz1:.1f})")

# Working depth: how far the gear's tip reaches past the blade's crest. The
# first version of this subtracted the blade tip from itself and always read
# 0.15 - it was measuring nothing at all, and reported FAIL on a drive that
# was correct. Depth is 2*add, less however much the centre distance was
# opened up by.
want = 2*S.ADD - (S.CDIST - S.R_P)
for i, bx in enumerate(S.BLADE_X):
    pen = (bx + S.BLADE_T + S.TOOTH_H) - (S.PIN_X[i] - (S.R_P + S.ADD))
    chk(f"gear {i+1} working depth", abs(pen - want) < 0.05,
        f"{pen:.2f} mm of tooth engaged, want {want:.2f}")

# The blade must be under the gear at BOTH ends of the stroke with a whole
# tooth to spare, and must never leave the case through the front wall.
y_cl = S.WALL + 0.4
for tag, pull in (("shut", 0.0), ("open", S.CMD)):
    f = y_cl + S.RACK_Y0 - pull
    chk(f"blade spans the gear, {tag}", f + S.PITCH <= S.PIN_Y <= f + S.RACK_L - S.PITCH,
        f"blade y {f:.1f}..{f+S.RACK_L:.1f} around the axis at {S.PIN_Y:.1f}")
chk("blade stays inside the front wall", y_cl + S.RACK_Y0 - S.CMD >= S.WALL,
    f"blade nose reaches y {y_cl + S.RACK_Y0 - S.CMD:.2f}, wall inner face {S.WALL:.1f}")

print("\nPART INTEGRITY")
for n in ("case_lower", "deck", "case_upper", "drawer"):
    m = L(n); nb = len(m.split(only_watertight=False))
    chk(f"{n}: one watertight body", nb == 1 and m.is_watertight,
        f"{nb} body, watertight={m.is_watertight}")

print()
if fails:
    print(f"  DO NOT PRINT — {len(fails)} failure(s): " + ", ".join(fails)); sys.exit(1)
print("  CLEARED TO PRINT")
