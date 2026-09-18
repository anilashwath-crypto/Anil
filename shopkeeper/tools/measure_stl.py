#!/usr/bin/env python3
"""Measure STL bounding boxes and internal cavities via ray casting."""
import struct, sys, os, glob

def load(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:5] == b'solid' and b'facet' in data[:2000]:
        raise SystemExit("ASCII stl not handled: " + path)
    n = struct.unpack('<I', data[80:84])[0]
    tris = []
    off = 84
    for i in range(n):
        vals = struct.unpack('<12f', data[off:off+48])
        tris.append((vals[3:6], vals[6:9], vals[9:12]))
        off += 50
    return tris

def bbox(tris):
    lo = [1e18]*3; hi = [-1e18]*3
    for t in tris:
        for v in t:
            for k in range(3):
                if v[k] < lo[k]: lo[k] = v[k]
                if v[k] > hi[k]: hi[k] = v[k]
    return lo, hi

def ray_hits(tris, orig, d):
    """Moller-Trumbore. Returns sorted list of t values along direction d."""
    hits = []
    EPS = 1e-9
    for (v0, v1, v2) in tris:
        e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
        e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
        p = (d[1]*e2[2]-d[2]*e2[1], d[2]*e2[0]-d[0]*e2[2], d[0]*e2[1]-d[1]*e2[0])
        det = e1[0]*p[0] + e1[1]*p[1] + e1[2]*p[2]
        if -EPS < det < EPS:
            continue
        inv = 1.0/det
        tv = (orig[0]-v0[0], orig[1]-v0[1], orig[2]-v0[2])
        u = (tv[0]*p[0] + tv[1]*p[1] + tv[2]*p[2]) * inv
        if u < -1e-7 or u > 1+1e-7:
            continue
        q = (tv[1]*e1[2]-tv[2]*e1[1], tv[2]*e1[0]-tv[0]*e1[2], tv[0]*e1[1]-tv[1]*e1[0])
        v = (d[0]*q[0] + d[1]*q[1] + d[2]*q[2]) * inv
        if v < -1e-7 or u+v > 1+1e-7:
            continue
        t = (e2[0]*q[0] + e2[1]*q[1] + e2[2]*q[2]) * inv
        hits.append(t)
    hits.sort()
    # dedupe near-identical crossings (shared edges)
    out = []
    for h in hits:
        if not out or abs(h-out[-1]) > 0.05:
            out.append(h)
    return out

def probe(path, zfracs=(0.35, 0.55), yfrac=0.5, xfrac=0.5):
    tris = load(path)
    lo, hi = bbox(tris)
    size = [hi[k]-lo[k] for k in range(3)]
    print(f"\n=== {os.path.basename(path)}")
    print(f"    triangles {len(tris)}")
    print(f"    BBOX  X {size[0]:8.2f}   Y {size[1]:8.2f}   Z {size[2]:8.2f}  mm")
    for zf in zfracs:
        z = lo[2] + size[2]*zf
        oy = lo[1] + size[1]*yfrac
        ox = lo[0] + size[0]*xfrac
        hx = ray_hits(tris, (lo[0]-10, oy, z), (1,0,0))
        hy = ray_hits(tris, (ox, lo[1]-10, z), (0,1,0))
        fx = [round(h-10, 2) for h in hx]
        fy = [round(h-10, 2) for h in hy]
        print(f"    z={zf*100:4.0f}%  X-crossings {fx}")
        print(f"             Y-crossings {fy}")
        if len(fx) >= 4:
            print(f"             -> inner X span {fx[1]:.2f} .. {fx[-2]:.2f} = {fx[-2]-fx[1]:.2f} mm"
                  f"   wall {fx[1]-fx[0]:.2f}")
        if len(fy) >= 4:
            print(f"             -> inner Y span {fy[1]:.2f} .. {fy[-2]:.2f} = {fy[-2]-fy[1]:.2f} mm"
                  f"   wall {fy[1]-fy[0]:.2f}")

D = "/Users/piyushmishra/Downloads/Ryobi+Mini+Desktop+Toolbox_stls"

print("#################  OVERALL  #################")
for f in ["obj_2_Assembly.stl"]:
    tris = load(os.path.join(D, f)); lo, hi = bbox(tris)
    print(f"{f}:  {hi[0]-lo[0]:.2f} x {hi[1]-lo[1]:.2f} x {hi[2]-lo[2]:.2f} mm")

print("\n#################  DRAWERS  #################")
for f in ["obj_25_Large Drawer with Split Front.stl",
          "obj_26_Small Drawer with Split Front.stl"]:
    probe(os.path.join(D, f))

print("\n#################  CABINET SHELLS  #################")
for f in ["obj_11_cabinet-big-drawer-tabs-removed.stl",
          "obj_15_cabinet-small-drawer-tabs-removed.stl",
          "obj_12_Mini tool box side rails.stl_1.stl"]:
    tris = load(os.path.join(D, f)); lo, hi = bbox(tris)
    print(f"{f:58s}  {hi[0]-lo[0]:7.2f} x {hi[1]-lo[1]:7.2f} x {hi[2]-lo[2]:7.2f}")

print("\n#################  ALL PARTS BBOX  #################")
for p in sorted(glob.glob(os.path.join(D, "*.stl"))):
    tris = load(p); lo, hi = bbox(tris)
    print(f"{os.path.basename(p):58s}  {hi[0]-lo[0]:7.2f} x {hi[1]-lo[1]:7.2f} x {hi[2]-lo[2]:7.2f}")
