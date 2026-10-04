#!/usr/bin/env python3
"""
Does cutting holes in the drawer make it print faster?

The intuition is that less material means less time. On this part that is not
obvious, because at the demo settings the run is already 38.8% outer wall and
only 28.6% infill: a hole DELETES a little infill and ADDS a perimeter around
itself, and perimeter is the expensive thing here. So the answer could go
either way and is worth measuring rather than arguing about.

The locked mesh is never modified - variants are written elsewhere and the
lock file's sha256 is re-checked at the end.

Cutouts stay off the floor's working features: the rack channel at x 10.65-16.71
and the two peg slots at x 18.68-22.13 are what the drawer is driven by.
"""
import hashlib, json, os, re, shutil, subprocess, sys
import numpy as np
import trimesh
from trimesh.creation import box, cylinder

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC  = os.path.join(ROOT, "nano/prev/drawer_single.stl")
SC   = ("/private/tmp/claude-501/-Users-piyushmishra/"
        "5f7839e0-775c-4226-90ac-774bd91f5419/scratchpad/cutout")
BS   = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
PROF = "/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"
MACH = f"{PROF}/machine/Bambu Lab P2S 0.4 nozzle.json"
FIL  = f"{PROF}/filament/Generic PLA @BBL P2S.json"
DEMO = os.path.join(ROOT, "print_profiles/shopkeeper DEMO 0.30.json")
AREA, DENS = 3.14159265 * (1.75/2)**2, 1.24

W, D, H = 39.8, 59.0, 21.0
WALL, FLOOR, FRONT = 1.8, 1.8, 3.0
CHAN = (10.65, 16.71)          # rack channel - never cut into
PEGS = (18.68, 22.13)          # peg slots   - never cut into


def blk(x0, x1, y0, y1, z0, z1):
    m = box(extents=[x1-x0, y1-y0, z1-z0])
    m.apply_translation([(x0+x1)/2, (y0+y1)/2, (z0+z1)/2]); return m


def cut(mesh, tools):
    return trimesh.boolean.difference([mesh] + tools, engine="manifold")


def side_vents(m):
    """Slots through BOTH long walls at once - the interior is already void, so
    a box spanning the full width only removes wall."""
    t = []
    for y0 in (7, 17, 27, 37, 47):
        t.append(blk(-1, W+1, y0, y0+6, 5.0, 18.0))
    return cut(m, t)


def rear_vents(m):
    return cut(m, [blk(x0, x0+8, D-WALL-1, D+1, 5.0, 18.0)
                   for x0 in (6, 16, 26)])


def floor_holes(m):
    """Only in the two strips clear of the channel and the peg slots."""
    t = []
    for xs in ((3.5, CHAN[0]-1.5), (PEGS[1]+1.5, W-WALL-1.5)):
        xs_ = np.arange(xs[0]+2.5, xs[1]-2.0, 6.5)
        for x in xs_:
            for y in np.arange(FRONT+4.0, D-WALL-4.0, 6.5):
                c = cylinder(radius=2.4, height=FLOOR+2, sections=16)
                c.apply_translation([x, y, FLOOR/2])
                t.append(c)
    return cut(m, t)


VARIANTS = {
    "locked (no cutouts)":       lambda m: m,
    "side vents":                side_vents,
    "side + rear vents":         lambda m: rear_vents(side_vents(m)),
    "floor holes":               floor_holes,
    "everything cut":            lambda m: floor_holes(rear_vents(side_vents(m))),
}


def slice_it(path, tag):
    d = os.path.join(SC, tag)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    r = subprocess.run([BS, "--load-settings", f"{MACH};{DEMO}",
                        "--load-filaments", FIL, "--slice", "0",
                        "--outputdir", d, path],
                       capture_output=True, text=True, timeout=900)
    g = os.path.join(d, "plate_1.gcode")
    if not os.path.exists(g):
        e = [l for l in (r.stdout+r.stderr).splitlines() if "rror" in l.lower()]
        return None, (e[-1][:110] if e else "no gcode")
    h = open(g, "rb").read(400_000).decode("utf8", "ignore")
    t = re.search(r"; model printing time: ([^;\n]+)", h)
    L = re.search(r"; total filament length \[mm\] : ([\d.]+)", h)
    secs = sum(int(v)*{"d":86400,"h":3600,"m":60,"s":1}[u]
               for v, u in re.findall(r"(\d+)([dhms])", t.group(1)))
    return {"time": t.group(1).strip(), "s": secs,
            "g": float(L.group(1))*AREA/1000.0*DENS}, None


os.makedirs(SC, exist_ok=True)
src = trimesh.load(SRC)
print(f"\nCUTOUT TEST — does removing material print faster?")
print(f"sliced at shopkeeper DEMO 0.30\n")
print(f"  {'variant':24s} {'time':>8s} {'PLA':>8s} {'vs locked':>18s}  mesh")
base = None
rows = []
for name, fn in VARIANTS.items():
    m = fn(src.copy())
    tag = re.sub(r"[^a-z0-9]+", "_", name.lower())
    p = os.path.join(SC, tag + ".stl")
    m.export(p)
    res, err = slice_it(p, tag)
    if err:
        print(f"  {name:24s} FAILED: {err}"); continue
    if base is None: base = res
    dt = (res["s"]-base["s"])/base["s"]*100
    dg = (res["g"]-base["g"])/base["g"]*100
    ok = m.is_watertight and len(m.split(only_watertight=False)) == 1
    print(f"  {name:24s} {res['time']:>8s} {res['g']:6.2f}g  "
          f"{dt:+6.1f}% {dg:+6.1f}%   {m.volume/1000*1.27:5.2f}g solid"
          f"{'' if ok else '  NOT WATERTIGHT'}")
    rows.append(dict(name=name, **res, dt=dt, dg=dg))

h = hashlib.sha256(open(SRC, "rb").read()).hexdigest()
lock = json.load(open(os.path.join(ROOT, "nano/prev/drawer_single.LOCK.json")))
print(f"\n  locked mesh untouched: {h == lock['sha256']}")
json.dump(rows, open(os.path.join(SC, "cutout.json"), "w"), indent=1)
