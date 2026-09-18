#!/usr/bin/env python3
"""
Plate up the COMPLETE two-level ToolCell build.

Stock Ryobi chest parts are pulled straight from the user's 3MF and are
NOT modified. Our generated parts come from out/. Everything is dropped
to z=0 and shelf-packed onto 256 mm plates, one 3MF per plate.

Run cad/toolcell.py first so out/*.stl exist.
"""
import os, sys
import trimesh
from mf3 import write_3mf, verify

HERE  = os.path.dirname(os.path.abspath(__file__))
OUT   = os.path.join(HERE, "..", "out")
PLATE = os.path.join(OUT, "plates")
SRC   = "/Users/piyushmishra/Downloads/Ryobi_Mini_Desktop_Toolbox.3mf"
BED   = 256.0
GAP   = 6.0
os.makedirs(PLATE, exist_ok=True)
import glob as _g
for _f in _g.glob(os.path.join(PLATE, "plate_*.3mf")):
    os.remove(_f)   # stale plates from an earlier layout must not linger


import numpy as np

def landscape(m):
    """Drop to z=0, corner to origin, long axis along X.

    Rails come out of the source 3MF running along Y at 200 mm, which
    overflows the bed the moment anything shares the plate."""
    m = m.copy()
    m.apply_translation(-m.bounds[0])
    if m.extents[1] > m.extents[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(
            np.pi / 2, [0, 0, 1]))
        m.apply_translation(-m.bounds[0])
    return m

# object id in the source 3MF -> what it actually is
STOCK = {
    "19":   "large_bay",       # 189.6 x 119.5 x 55
    "27":   "small_bay",       # 189.6 x 119.5 x 30
    "11_1": "large_drawer",    # 189.6 x 105 x 55
    "7_1":  "drawer_front",    # 189.6 x 18.8 x 52.2
    "33_3": "handle_cover",
    "21":   "side_rail",
    "31_3": "foot",
}

print("loading stock chest ...")
scene = trimesh.load(SRC)
raw = scene.geometry
stock = {}
for k, name in STOCK.items():
    if k not in raw:
        sys.exit(f"object {k} ({name}) not found in source 3MF")
    m = landscape(raw[k].copy())
    stock[name] = m
    e = m.extents
    print(f"  {name:16s} {e[0]:7.2f} x {e[1]:7.2f} x {e[2]:6.2f}")

print("\nloading generated parts ...")
ours = {}
for n in ("hinge_carrier", "flap", "bin_divider", "servo_retainer"):
    p = os.path.join(OUT, n + ".stl")
    if not os.path.exists(p):
        sys.exit(f"missing {p} — run cad/toolcell.py first")
    m = landscape(trimesh.load(p))
    ours[n] = m
    e = m.extents
    print(f"  {n:16s} {e[0]:7.2f} x {e[1]:7.2f} x {e[2]:6.2f}")

# ── plate contents: (label, mesh, quantity) ──
PLATES = [
    ("1_mechanism", [
        ("hinge_carrier",  ours["hinge_carrier"],  1),
        ("flap",           ours["flap"],           2),
        ("bin_divider",    ours["bin_divider"],    1),
        ("servo_retainer", ours["servo_retainer"], 2),
    ]),
    # One bay per plate on purpose. Each is ~245 g and hours long; sharing a
    # plate means one failure costs both.
    ("2_bay_electronics", [("large_bay", stock["large_bay"], 1)]),
    ("3_bay_drawer",      [("large_bay", stock["large_bay"], 1)]),
    ("4_head_and_trim", [
        ("small_bay",    stock["small_bay"],    1),   # control head
        ("drawer_front", stock["drawer_front"], 1),
        ("handle_cover", stock["handle_cover"], 1),
    ]),
    ("5_drawer",  [("large_drawer", stock["large_drawer"], 1)]),
    ("6_rails_and_feet", [
        ("side_rail", stock["side_rail"], 4),
        ("foot",      stock["foot"],      4),
    ]),
]

def shelf_pack(items, bed=BED, gap=GAP):
    """Left-to-right, wrap to a new row when the width runs out."""
    placed, x, y, row_h, w_max = [], gap, gap, 0.0, 0.0
    for name, mesh, qty in items:
        for i in range(qty):
            w, d = mesh.extents[0], mesh.extents[1]
            if x + w > bed - gap:
                x = gap; y += row_h + gap; row_h = 0.0
            label = name if qty == 1 else f"{name}_{i+1}"
            placed.append((label, mesh, x, y))
            x += w + gap
            row_h = max(row_h, d)
            w_max = max(w_max, x)
    return placed, w_max, y + row_h + gap

print("\n" + "=" * 68)
total_g = 0.0
allok = True
for label, items in PLATES:
    placed, w, d = shelf_pack(items)
    fits = w <= BED and d <= BED
    allok &= fits
    grams = sum(m.volume / 1000 * 1.27 for _, m, _, _ in placed)
    total_g += grams
    path = os.path.join(PLATE, f"plate_{label}.3mf")
    write_3mf(path, placed)
    o, b = verify(path)
    print(f"\nPLATE {label}")
    for nm, m, x, y in placed:
        print(f"    {nm:20s} at ({x:6.1f},{y:6.1f})  "
              f"{m.extents[0]:6.1f} x {m.extents[1]:6.1f} x {m.extents[2]:5.1f}")
    print(f"    {len(placed)} objects, {w:.0f} x {d:.0f} mm, ~{grams:.0f} g solid"
          f"   fits={fits}  objects==items:{o == b}")
    if not fits:
        print(f"    *** EXCEEDS {BED:.0f} mm BED ***")

print("\n" + "=" * 68)
print(f"{len(PLATES)} plates, ~{total_g:.0f} g solid volume "
      f"(sliced with infill will run 10-20% under)")
print(f"written to {os.path.normpath(PLATE)}")
print("ALL PLATES FIT" if allok else "*** SOME PLATES DO NOT FIT ***")
