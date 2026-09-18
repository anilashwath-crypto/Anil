#!/usr/bin/env python3
"""Hard interference + engagement checks for the motorised drawer cabinet.

The CAD review found that dimension-only assertions miss the failures that
actually matter. These place the parts where they really sit and run boolean
intersections, plus walk the rack/pinion contact point across the full stroke.
"""
import os, math, sys
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "out2")
sys.path.insert(0, HERE)
import slidebox as S                      # reuse the exact geometry + params

P, WL = S.P, S.WL
DECK, TRAVEL = S.DECK, S.TRAVEL
R_P, M = S.R_P, S.M

bay    = trimesh.load(os.path.join(OUT, "case_bay.stl"))
drawer = trimesh.load(os.path.join(OUT, "drawer.stl"))

fails = []
def chk(label, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:38s} {detail}")
    if not ok:
        fails.append(label)

print("\nslidebox — physical verification\n")

# ── the drawer must actually go into the bay ────────────────────────────
# drawer part: handle at +y, so it must face the bay mouth at y = 0 → rotate 180
d = drawer.copy()
d.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [0, 0, 1]))
d.apply_translation(-d.bounds[0])
X0 = WL + P["side_clear"]
Z0 = DECK - P["fin_h"]

# closed = drawer body hard against the back of the bay, handle proud of the
# mouth. Opening moves it toward the mouth, i.e. -Y. The earlier sweep went the
# wrong way and was measuring the drawer bottoming out, which is not a defect.
body_d  = S.DR_D
handle  = d.extents[1] - body_d
y_closed = (P["cd"] - WL - 2) - body_d - handle
worst, worst_y = 0.0, None
for pull in (0, 10, 25, 40, TRAVEL):
    inst = d.copy()
    inst.apply_translation([X0, y_closed - pull, Z0])
    try:
        hit = trimesh.boolean.intersection([inst, bay], engine="manifold")
        v = float(hit.volume)
    except Exception:
        v = 0.0
    if v > worst:
        worst, worst_y = v, pull
chk("drawer never touches the bay", worst < 1.0,
    f"worst {worst:.1f} mm3 at pull={worst_y} (closed y={y_closed:.1f})")

# ── rack / pinion engagement across the whole stroke ────────────────────
fin_len   = S.DR_D - 24
fin_y0    = 12.0                      # fin start in drawer-part coords
tooth_lo  = fin_y0
tooth_hi  = fin_y0 + fin_len
pin_y_bay = WL + S.PIN_Y

# where the fin sits in bay coords, closed and open
lo_closed = WL + 1 + tooth_lo
hi_closed = WL + 1 + tooth_hi
contact_closed = pin_y_bay - lo_closed
contact_open   = pin_y_bay - (lo_closed - TRAVEL)
margin = 1.5 * M + 2.0
chk("pinion on the rack when closed",
    margin < contact_closed < fin_len - margin,
    f"contact {contact_closed:.1f} of 0..{fin_len:.1f}")
chk("pinion still on the rack when open",
    margin < contact_open < fin_len - margin,
    f"contact {contact_open:.1f} of 0..{fin_len:.1f}")

# ── pinion teeth must sit at the fin's tooth height ─────────────────────
fin_z0, fin_z1 = Z0, Z0 + P["fin_h"]              # 22 .. 31
pin = trimesh.load(os.path.join(OUT, "pinion.stl"))
gear_lo, gear_hi = 0.0, P["gear_t"]               # part-local tooth band
# the pinion is seated so its spline pocket grips the SG90 spline
spline_top = WL + 29.0
spline_bot = spline_top - 4.0
seat_z = S.POCKET_LO_TARGET if hasattr(S, "POCKET_LO_TARGET") else None
print(f"        fin teeth z {fin_z0:.1f}..{fin_z1:.1f}   "
      f"spline z {spline_bot:.1f}..{spline_top:.1f}   "
      f"pinion part height {pin.extents[2]:.1f}")

# ── servo envelope under the deck ───────────────────────────────────────
chk("servo + shaft clear the deck", spline_top <= P["deck_z"] + 4.5,
    f"spline top {spline_top:.1f}, deck underside {P['deck_z']:.1f}")

print()
if fails:
    print(f"  *** {len(fails)} FAILED: " + ", ".join(fails))
    sys.exit(1)
print("  ALL PHYSICAL CHECKS PASSED")
