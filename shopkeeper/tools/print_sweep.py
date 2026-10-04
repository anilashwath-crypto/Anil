#!/usr/bin/env python3
"""
What can be saved on the LOCKED drawer without touching its geometry.

Every figure here comes from Bambu Studio's own slicer run headless, not from
a rule of thumb. The design is frozen: only process settings vary, so anything
this finds can be applied by picking a profile, and the part that comes off the
plate is dimensionally the same part.

Baseline is what the user actually has selected: P2S 0.4 nozzle, 0.20mm
Standard, Generic PLA.
"""
import json, os, re, subprocess, sys, shutil

BS   = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
PROF = "/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"
MACH = f"{PROF}/machine/Bambu Lab P2S 0.4 nozzle.json"
FIL  = f"{PROF}/filament/Generic PLA @BBL P2S.json"
SC   = ("/private/tmp/claude-501/-Users-piyushmishra/"
        "5f7839e0-775c-4226-90ac-774bd91f5419/scratchpad/sweep")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "nano/prev/drawer_single.stl"

AREA = 3.14159265 * (1.75/2)**2      # mm2 of 1.75 filament
DENS = 1.24                          # g/cm3, generic PLA

# (label, base process preset, overrides, what it costs you)
CASES = [
    ("baseline 0.20 Standard", "0.20mm Standard", {}, "what you have now"),
    # The shipped "0.24mm Standard @BBL P2S" preset does NOT carry a
    # layer_height of its own - it inherits 0.20 from fdm_process_single_0.20,
    # so loading it by name slices at 0.20 and reports a meaningless +0.3%.
    # Set the height explicitly or the row is a lie.
    ("0.24 layer", "0.20mm Standard", {"layer_height": "0.24"}, "coarser layers"),
    ("0.28 layer", "0.20mm Standard", {"layer_height": "0.28"}, "70% of nozzle"),
    ("0.20 + lightning 8%", "0.20mm Standard",
     {"sparse_infill_density": "8%", "sparse_infill_pattern": "lightning"},
     "infill change alone, layers untouched"),
    ("0.24 + lightning + 2 shells", "0.20mm Standard",
     {"layer_height": "0.24", "sparse_infill_density": "8%",
      "sparse_infill_pattern": "lightning", "top_shell_layers": "2",
      "bottom_shell_layers": "2"}, "SAFE prototype"),
    ("0.28 + lightning + 2 shells", "0.20mm Standard",
     {"layer_height": "0.28", "sparse_infill_density": "8%",
      "sparse_infill_pattern": "lightning", "top_shell_layers": "2",
      "bottom_shell_layers": "2"}, "FAST prototype"),
    ("FAST + outer wall 300", "0.20mm Standard",
     {"layer_height": "0.28", "sparse_infill_density": "8%",
      "sparse_infill_pattern": "lightning", "top_shell_layers": "2",
      "bottom_shell_layers": "2", "outer_wall_speed": "300",
      "inner_wall_speed": "400"}, "speed on top of the rest"),
    ("FAST + 1 wall", "0.20mm Standard",
     {"layer_height": "0.28", "wall_loops": "1", "sparse_infill_density": "8%",
      "sparse_infill_pattern": "lightning", "top_shell_layers": "2",
      "bottom_shell_layers": "2"}, "fragile: one 0.42 wall per side"),
]


def slice_once(label, base, over):
    d = os.path.join(SC, re.sub(r"[^a-z0-9]+", "_", label.lower()))
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    proc = f"{PROF}/process/{base} @BBL P2S.json"
    if over:
        cfg = json.load(open(proc))
        cfg.update(over)
        cfg["name"] = f"proto {label}"
        proc = os.path.join(d, "process.json")
        json.dump(cfg, open(proc, "w"))
    r = subprocess.run(
        [BS, "--load-settings", f"{MACH};{proc}", "--load-filaments", FIL,
         "--slice", "0", "--outputdir", d, MODEL],
        capture_output=True, text=True, timeout=900)
    g = os.path.join(d, "plate_1.gcode")
    if not os.path.exists(g):
        err = [l for l in (r.stdout + r.stderr).splitlines() if "rror" in l]
        return None, (err[-1] if err else "no gcode produced")
    head = open(g, "rb").read(500_000).decode("utf8", "ignore")
    t = re.search(r"; model printing time: ([^;\n]+)", head)
    L = re.search(r"; total filament length \[mm\] : ([\d.]+)", head)
    if not (t and L):
        return None, "could not read gcode header"
    secs = 0
    for v, u in re.findall(r"(\d+)([dhms])", t.group(1)):
        secs += int(v) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u]
    mm = float(L.group(1))
    return {"label": label, "time_s": secs, "time": t.group(1).strip(),
            "mm": mm, "g": mm * AREA / 1000.0 * DENS}, None


os.makedirs(SC, exist_ok=True)
rows, base = [], None
print(f"\nPRINT SWEEP — {MODEL}")
print("design frozen; process settings only\n")
for label, bp, over, note in CASES:
    res, err = slice_once(label, bp, over)
    if err:
        print(f"  {label:30s} FAILED: {err}"); continue
    if base is None: base = res
    res["note"] = note
    res["dt"] = (res["time_s"] - base["time_s"]) / base["time_s"] * 100
    res["dg"] = (res["g"] - base["g"]) / base["g"] * 100
    rows.append(res)
    print(f"  {label:30s} {res['time']:>10s}  {res['g']:5.2f} g   "
          f"{res['dt']:+6.1f}% time  {res['dg']:+6.1f}% PLA")

json.dump(rows, open(os.path.join(SC, "sweep.json"), "w"), indent=1)
print(f"\n  -> {os.path.join(SC, 'sweep.json')}")
