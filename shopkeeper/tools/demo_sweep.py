#!/usr/bin/env python3
"""
Maximum speed on the LOCKED drawer. Demo part - no load, no strength budget.

Nothing here touches a dimension. Every saving is interior: infill, shell
counts, wall count. The mesh is byte-identical across all rows, so the part
that comes off the plate measures the same as the one already fitted.

The one thing that CANNOT be given away is the floor. It is 1.8 mm thick and
it carries the rack channel and the two peg slots - that is what makes it a
drawer rather than a box. Drop infill to zero and thin the shells too far and
the floor becomes a lid over a void: the peg slots lose their walls and the
channel sags. So every row is checked by measuring extrusion per layer in the
gcode and confirming the floor layers are actually solid, rather than trusting
that 2 shells at 0.28 add up to 1.8 mm. They do not - they add up to 1.12.
"""
import json, os, re, shutil, subprocess, sys
from collections import defaultdict

BS   = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
PROF = "/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"
MACH = f"{PROF}/machine/Bambu Lab P2S 0.4 nozzle.json"
FIL  = f"{PROF}/filament/Generic PLA @BBL P2S.json"
SYS  = f"{PROF}/process/0.20mm Standard @BBL P2S.json"
SC   = ("/private/tmp/claude-501/-Users-piyushmishra/"
        "5f7839e0-775c-4226-90ac-774bd91f5419/scratchpad/demo")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "nano/prev/drawer_single.stl"

FLOOR_T = 1.80          # the drawer's floor, measured off the mesh
AREA = 3.14159265 * (1.75/2)**2
DENS = 1.24

DEMO = {"sparse_infill_density": "0%", "wall_loops": "1",
        "bottom_shell_thickness": "0.8", "top_shell_thickness": "0.8",
        "skirt_loops": "0", "brim_width": "0"}

B = dict(DEMO, layer_height="0.30")
CASES = [
    ("baseline 0.20 Standard", {}),
    ("DEMO 0.30 / 1 wall / 0% infill", B),
    # With one wall there is no inner wall left: every perimeter is now an
    # OUTER wall and runs at the slow outer-wall speed, which is why outer-wall
    # time went UP (272s -> 316s) even though the part lost 35 layers. At two
    # walls raising this changed nothing at all. It may not be true any more.
    ("+ outer wall 300", dict(B, outer_wall_speed="300")),
    ("+ outer wall 400", dict(B, outer_wall_speed="400")),
    # The solid floor is 28.6% of the run. Baseline leaves sparse infill inside
    # its floor and that drawer works, so the floor does not have to be solid.
    ("+ thin shells 0.4", dict(B, bottom_shell_thickness="0.4",
                               top_shell_thickness="0.4")),
    ("+ thin shells + 10% infill",
     dict(B, bottom_shell_thickness="0.4", top_shell_thickness="0.4",
          sparse_infill_density="10%", sparse_infill_pattern="grid")),
    ("EVERYTHING", dict(B, outer_wall_speed="400", bottom_shell_thickness="0.4",
                        top_shell_thickness="0.4", sparse_infill_density="10%",
                        sparse_infill_pattern="grid")),
]


def floor_solid(gcode):
    """Extrusion per layer across the floor, plus which features appear there.

    Bambu's gcode marks layers with "; Z_HEIGHT:" and "; CHANGE_LAYER", not the
    ";Z:" this first looked for - so the first version of this check found zero
    floor layers and reported nothing at all rather than failing loudly.

    A solid floor layer lays down about as much filament as its neighbours; a
    layer roofing a void lays down a fraction. Sparse infill appearing inside
    the floor band is the same fault seen from the other side."""
    per, feat = defaultdict(float), defaultdict(set)
    z, e_prev, cur = 0.0, 0.0, None
    for ln in open(gcode, "rb").read().decode("utf8", "ignore").splitlines():
        if ln.startswith("; Z_HEIGHT:"):
            try: cur = round(float(ln.split(":", 1)[1]), 3)
            except ValueError: pass
        elif ln.startswith("; FEATURE:") and cur is not None:
            feat[cur].add(ln.split(":", 1)[1].strip())
        elif ln.startswith("G1 ") and " E" in ln and cur is not None:
            m = re.search(r" E(-?[\d.]+)", ln)
            if m:
                e = float(m.group(1))
                if e > e_prev: per[cur] += e - e_prev
                e_prev = e
        elif ln.startswith("G92") and " E0" in ln:
            e_prev = 0.0
    fl = sorted(k for k in per if 0 < k <= FLOOR_T + 0.01)
    if len(fl) < 2:
        return None, None, len(fl), set()
    vals = [per[k] for k in fl]
    peak = max(vals)
    worst = min(vals[1:]) / peak if peak else 0.0
    sparse = {f for k in fl for f in feat[k] if "parse" in f}
    return (worst >= 0.55 and not sparse), worst, len(fl), sparse


def run(label, over):
    d = os.path.join(SC, re.sub(r"[^a-z0-9]+", "_", label.lower()))
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    proc = SYS
    if over:
        cfg = json.load(open(SYS)); cfg.update(over); cfg["name"] = label
        proc = os.path.join(d, "p.json"); json.dump(cfg, open(proc, "w"))
    r = subprocess.run([BS, "--load-settings", f"{MACH};{proc}",
                        "--load-filaments", FIL, "--slice", "0",
                        "--outputdir", d, MODEL],
                       capture_output=True, text=True, timeout=900)
    g = os.path.join(d, "plate_1.gcode")
    if not os.path.exists(g):
        err = [l for l in (r.stdout + r.stderr).splitlines() if "rror" in l.lower()]
        return None, (err[-1][:110] if err else "no gcode")
    h = open(g, "rb").read(400_000).decode("utf8", "ignore")
    t = re.search(r"; model printing time: ([^;\n]+)", h)
    L = re.search(r"; total filament length \[mm\] : ([\d.]+)", h)
    if not (t and L): return None, "unreadable header"
    secs = sum(int(v) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u]
               for v, u in re.findall(r"(\d+)([dhms])", t.group(1)))
    ok, worst, nfl, sp = floor_solid(g)
    return {"label": label, "time": t.group(1).strip(), "s": secs,
            "g": float(L.group(1)) * AREA / 1000.0 * DENS,
            "floor_ok": ok, "floor_worst": worst, "floor_layers": nfl,
            "floor_sparse": sorted(sp)}, None


os.makedirs(SC, exist_ok=True)
print(f"\nDEMO SWEEP — {MODEL}\nouter dimensions frozen; interior only\n")
print(f"  {'config':34s} {'time':>8s} {'PLA':>7s}  {'vs base':>15s}  floor")
rows, base = [], None
for label, over in CASES:
    res, err = run(label, over)
    if err:
        print(f"  {label:34s} FAILED: {err}"); continue
    if base is None: base = res
    dt = (res["s"] - base["s"]) / base["s"] * 100
    dg = (res["g"] - base["g"]) / base["g"] * 100
    fl = "?" if res["floor_ok"] is None else ("SOLID" if res["floor_ok"] else "HOLLOW")
    det = "" if res["floor_worst"] is None else \
        f"({res['floor_worst']:.2f} thinnest, {res['floor_layers']} layers" + \
        (", sparse in floor!" if res["floor_sparse"] else "") + ")"
    print(f"  {label:34s} {res['time']:>8s} {res['g']:6.2f}g  "
          f"{dt:+6.1f}% {dg:+6.1f}%  {fl} {det}")
    res.update(dt=dt, dg=dg); rows.append(res)
json.dump(rows, open(os.path.join(SC, "demo.json"), "w"), indent=1)
print(f"\n  -> {os.path.join(SC,'demo.json')}")
