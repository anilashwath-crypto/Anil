#!/usr/bin/env python3
"""
Find floating regions the way a slicer does.

For every downward-facing face above the bed, cast a ray straight down. If it
hits nothing, that face prints into thin air. Reports total unsupported area
and where it is, so the fix can be geometric rather than "enable supports".
"""
import os, sys
import numpy as np
import trimesh

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "nano")

def land(m):
    m = m.copy(); m.apply_translation(-m.bounds[0])
    if m.extents[1] > m.extents[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0,0,1]))
        m.apply_translation(-m.bounds[0])
    return m

FLIP = {"case_upper.stl",      # printed top-face-down; score it that way
        "pinion.stl"}          # gear face down, horn pocket up - scored the
                               # other way it reports the pocket roof as a
                               # 111 mm2 overhang that does not exist in the
                               # pose it actually prints in

# 45 deg is the accepted self-supporting limit and has normal_z = -0.7071,
# so a -0.70 threshold flags every deliberate 45 deg chamfer. -0.75 leaves
# 45 deg passing and still catches anything flatter.
def analyse(path, cos_limit=-0.75, min_h=0.6):
    m = trimesh.load(path)
    if os.path.basename(path) in FLIP:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1,0,0]))
    m = land(m)
    n  = m.face_normals[:, 2]
    zc = m.triangles_center[:, 2]
    sel = np.where((n < cos_limit) & (zc > m.bounds[0][2] + min_h))[0]
    if not len(sel):
        return m, 0.0, []
    org = m.triangles_center[sel] + np.array([0, 0, -0.05])
    dirs = np.tile([0, 0, -1.0], (len(sel), 1))
    # A ray that hits something 20 mm below is NOT supported - the slicer still
    # has to bridge that gap. Only material within GAP mm counts as support.
    GAP = 0.6
    loc, idx_ray, _ = m.ray.intersects_location(ray_origins=org,
                                                ray_directions=dirs)
    near = np.zeros(len(sel), dtype=bool)
    if len(idx_ray):
        d = org[idx_ray][:, 2] - loc[:, 2]
        for r, dist in zip(idx_ray, d):
            if dist <= GAP:
                near[r] = True
    free = sel[~near]
    area = float(m.area_faces[free].sum())
    groups = []
    if len(free):
        c = m.triangles_center[free]
        # cluster by height band so the report is readable
        for lo in np.arange(0, m.bounds[1][2] + 2, 2.0):
            k = (c[:, 2] >= lo) & (c[:, 2] < lo + 2.0)
            if k.sum() == 0:
                continue
            a = float(m.area_faces[free[k]].sum())
            if a < 1.0:
                continue
            b = c[k]
            groups.append((lo, a, b[:, 0].min(), b[:, 0].max(),
                           b[:, 1].min(), b[:, 1].max()))
    return m, area, groups

print("\nFLOATING-REGION ANALYSIS  (ray cast down from every overhang)\n")
worst = 0.0
for f in sorted(os.listdir(OUT)):
    if not f.endswith(".stl"):
        continue
    m, area, groups = analyse(os.path.join(OUT, f))
    fp = m.extents[0] * m.extents[1]
    pct = 100 * area / fp
    worst = max(worst, area)
    flag = "OK" if area < 15 else ("MARGINAL" if area < 80 else "*** NEEDS FIXING ***")
    print(f"  {f:14s} {m.extents[0]:6.1f} x {m.extents[1]:6.1f} x {m.extents[2]:5.1f}"
          f"   unsupported {area:8.1f} mm2 ({pct:5.1f}% of footprint)   {flag}")
    for lo, a, x0, x1, y0, y1 in sorted(groups, key=lambda g: -g[1])[:4]:
        print(f"        z {lo:5.1f}-{lo+2:.1f}  {a:7.1f} mm2   "
              f"x {x0:5.1f}..{x1:5.1f}  y {y0:5.1f}..{y1:5.1f}")
print()
