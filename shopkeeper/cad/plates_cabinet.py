#!/usr/bin/env python3
"""Shelf-pack the shopkeeper cabinet onto 256 mm plates, one 3MF each."""
import os, glob
import numpy as np
import trimesh
from mf3 import write_3mf, verify

HERE  = os.path.dirname(os.path.abspath(__file__))
OUT   = os.path.join(HERE, "..", "out")
PLATE = os.path.join(OUT, "plates")
BED, GAP = 256.0, 6.0
os.makedirs(PLATE, exist_ok=True)
for f in glob.glob(os.path.join(PLATE, "*.3mf")):
    os.remove(f)

def landscape(m):
    m = m.copy(); m.apply_translation(-m.bounds[0])
    if m.extents[1] > m.extents[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0,0,1]))
        m.apply_translation(-m.bounds[0])
    return m

parts = {}
for p in glob.glob(os.path.join(OUT, "*.stl")):
    parts[os.path.splitext(os.path.basename(p))[0]] = landscape(trimesh.load(p))

PLATES = [
    ("1_case_base",  [("case_base", 1)]),
    ("2_case_mid",   [("case_mid",  1)]),
    ("3_case_head",  [("case_head", 1)]),
    ("4_drawer",     [("drawer",    1)]),
    ("5_lids_gears", [("lid_A", 1), ("lid_B", 1), ("pinion", 2)]),
    ("6_tray_trim",  [("elec_tray", 1), ("elec_panel", 1), ("foot", 4)]),
]

def pack(items):
    placed, x, y, row, wmax = [], GAP, GAP, 0.0, 0.0
    for name, qty in items:
        m = parts[name]
        for i in range(qty):
            w, d = m.extents[0], m.extents[1]
            if x + w > BED - GAP:
                x = GAP; y += row + GAP; row = 0.0
            placed.append((name if qty == 1 else f"{name}_{i+1}", m, x, y))
            x += w + GAP; row = max(row, d); wmax = max(wmax, x)
    return placed, wmax, y + row + GAP

print("shopkeeper — print plates\n")
tot, ok = 0.0, True
for label, items in PLATES:
    placed, w, d = pack(items)
    fits = w <= BED and d <= BED
    ok &= fits
    g = sum(m.volume/1000*1.27 for _, m, _, _ in placed)
    tot += g
    path = os.path.join(PLATE, f"plate_{label}.3mf")
    write_3mf(path, placed)
    o, b = verify(path)
    names = ", ".join(n for n, _, _, _ in placed)
    print(f"  plate_{label:14s} {w:5.0f} x {d:5.0f} mm  {g:6.1f} g  "
          f"fits={fits} objs={o}=={b}")
    print(f"      {names}")
    if not fits:
        print("      *** EXCEEDS BED ***")

print(f"\n  {len(PLATES)} plates, {tot:.0f} g solid "
      f"(~{tot*0.85:.0f} g sliced)")
print("  " + ("ALL PLATES FIT" if ok else "*** SOME PLATES DO NOT FIT ***"))
print(f"  {os.path.normpath(PLATE)}")
