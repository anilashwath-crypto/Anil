#!/usr/bin/env python3
"""
viewer3d.py — build a fully self-contained interactive 3D viewer for shopkeeper NANO.

Loads the real STLs out of ../nano, decimates only where it is safe to do so
(volume must be preserved, or the lightening holes in case_lower collapse into
solid slabs), quantises the vertices to 0.01 mm integers, and writes a single
HTML *fragment* containing a hand-rolled canvas-2D painter's-algorithm renderer.

No CDN, no external script, no font, no network call of any kind: the whole
thing is one <style> + one <div> + one <script>.

The assembly poses are the ones nano.py itself uses for its boolean
interference sweep (see the block around "assembly pose: drawer floor on the
deck"), re-derived here from the same parameter dict and then ASSERTED against
the bounds of the exported STLs, so what is drawn is what was verified.
"""
import os, sys, math, json
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
STL  = os.path.normpath(os.path.join(HERE, "..", "nano"))
OUT  = os.path.normpath(os.path.join(
    HERE, "..", ".superpowers", "brainstorm", "25158-1786171087",
    "content", "viewer3d.html"))

# ────────────────────────────────────────────────────────────────────────────
# 1.  Parameters — lifted live out of cad/nano.py
#
# nano.py is a script, not a module: importing it would re-run every boolean
# and re-export every STL. So instead we slice out its parameter block (the
# `P = dict(...)` through `PIN_Y`, plus the rack constants) and exec just that.
# Nothing is duplicated here, so the viewer cannot drift out of step with the
# geometry when someone edits deck_z or ch.
# ────────────────────────────────────────────────────────────────────────────
print("shopkeeper NANO — 3D viewer\n")
NANO = os.path.join(HERE, "nano.py")
_src = open(NANO, encoding="utf-8").read().splitlines()

def _slice(first_prefix, last_prefix):
    a = next(i for i, l in enumerate(_src) if l.startswith(first_prefix))
    b = next(i for i, l in enumerate(_src) if i > a and l.startswith(last_prefix))
    return "\n".join(_src[a:b + 1])

# ANTITIP..PEG_X now spans the rib constants, the rack flange constants and the
# post-band helpers, so take the whole run rather than three separate slices.
_blk = (_slice("P = dict(", "PIN_Y ") + "\n"
        + _slice("ANTITIP ", "PEG_X "))
_ns = {"math": math}
exec(compile(_blk, NANO, "exec"), _ns)
for _k in ("P", "M", "N", "R_P", "R_TIP", "R_ROOT", "PITCH", "TRAVEL", "TOOTH_H",
           "FIN_SPAN", "CW", "CD", "CH", "WL", "DECK", "DR_D", "DR_TOP", "INNER",
           "DR_W", "DR_X", "FIN_X", "PIN_DX", "PIN_Y", "RACK_L", "RACK_Y0", "PEG_D",
           "ANTITIP", "RK_X0", "RK_X1", "PEG_X", "CDIST"):
    assert _k in _ns, f"nano.py no longer defines {_k}"
    globals()[_k] = _ns[_k]

DENSITY = 1.27                                    # g/cm3, same figure nano.py prints
print(f"  from nano.py:  case {CW:.0f} x {CD:.0f} x {CH:.0f}   deck top {DECK:.1f}   "
      f"travel {TRAVEL:.2f}   drawers 2 x ({DR_W:.1f} x {DR_D:.1f} x {P['dr_h']:.1f})")

# rack.stl was exported from rack(assembly=False) — print pose. These are the
# analytic bounds of rack(assembly=True), the pose used in the sweep.
# The flange moved inboard (it used to run through the drawer's own walls)
# and the blade grew, so this is (-4, 0, -13) now, not (-6, -3, -9.8).
RACK_ASM_MIN = np.array([RK_X0, 0.0, -(P["fin_h"] + P["dr_floor"])])

# The pinion's Z is no longer free-floating: it sits on the servo horn, and
# the servo's height is set by the shim. Same number nano.py checks.
SG_BASE = P["sg_base"]
SG_HORN = SG_BASE + P["sg_horn"]                  # horn face = pinion underside
PIN_Z   = SG_HORN                                 # 32.5

# ────────────────────────────────────────────────────────────────────────────
# 2.  Load, sanity-check, decimate
# ────────────────────────────────────────────────────────────────────────────
NAMES = ["case_lower", "case_upper", "deck", "drawer", "rack", "pinion",
         "servo_shim", "knob"]
# Bought parts. Drawn so the render shows the machine, not just the plastic -
# but kept out of the BOM totals, because you do not print an SG90.
EXTRA = ["servo", "servo_m", "esp"]
# keep = leave the mesh alone; the STLs are already low-poly.
# case_lower is the part you look at most and the one carrying the honeycomb
# floor, so it gets a higher budget now that the rig makes detail legible.
TARGET = {"case_lower": 2600}

raw = {}
for n in NAMES:
    m = trimesh.load(os.path.join(STL, n + ".stl"), process=True)
    assert isinstance(m, trimesh.Trimesh), n
    assert m.volume > 0, f"{n}: winding is inside-out"
    raw[n] = m

def close(a, b, tol=1e-6):
    return abs(a - b) <= tol

# assert the derived assembly numbers against the real exported geometry
e = raw["drawer"].extents
# dr_h + ANTITIP: the rear wall stands 3 mm proud as the anti-tip catch
assert np.allclose(e, [DR_W, DR_D, P["dr_h"]+ANTITIP], atol=1e-6), f"drawer {e}"
e = raw["deck"].extents
assert np.allclose(e, [CW-2*WL-0.6, CD-2*WL-0.6, P["deck_t"]], atol=1e-6), f"deck {e}"
e = raw["case_lower"].extents
pass  # case_lower height varies with the alignment pins
e = raw["case_upper"].extents
assert np.allclose(e, [CW, CD, CH-DECK], atol=1e-6), f"case_upper {e}"
e = raw["rack"].extents
assert np.allclose(e, [RK_X1-RK_X0, RACK_L, P["fin_h"]+P["dr_floor"]+2.0],
                   atol=1e-6), f"rack {e}"

# nano.py: Y_CLOSED = 0.0 — the drawer face is FLUSH with the case face now
Y_CLOSED = 0.0

def decimate(m, target, tol=0.03):
    """Decimate, but only accept a result that still encloses the same volume.
    fast_simplification will happily weld the lightening holes shut; that shows
    up as a volume jump, so we back the target off until it stops happening."""
    nf = len(m.faces)
    if target is None or nf <= target:
        return m, nf, False
    t = float(target)
    while t <= nf:
        try:
            s = m.simplify_quadric_decimation(face_count=int(t))
        except Exception as ex:                       # no fast_simplification
            print(f"    ! decimation unavailable ({ex}) — keeping {nf} faces")
            return m, nf, False
        ok = (s.volume > 0
              and abs(s.volume - m.volume) / m.volume < tol
              and np.allclose(s.extents, m.extents, atol=0.6))
        if ok:
            return s, len(s.faces), True
        t = t * 1.15 + 40
    return m, nf, False

def quantise(m):
    """0.01 mm integer vertices, welded, degenerate faces dropped."""
    V = np.rint(np.asarray(m.vertices) * 100.0).astype(np.int64)
    uniq, inv = np.unique(V, axis=0, return_inverse=True)
    inv = np.asarray(inv).ravel()
    F = inv[np.asarray(m.faces)]
    a, b, c = uniq[F[:, 0]], uniq[F[:, 1]], uniq[F[:, 2]]
    nrm = np.cross(b - a, c - a)
    F = F[(nrm ** 2).sum(1) > 0]
    # signed volume of the quantised shell must stay positive => outward winding
    a, b, c = uniq[F[:, 0]] / 100.0, uniq[F[:, 1]] / 100.0, uniq[F[:, 2]] / 100.0
    vol = float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)
    assert vol > 0, "quantised mesh has inverted winding"
    return uniq, F, vol

geo, tris, grams, posed_raw = {}, {}, {}, {}
for n in NAMES:
    m = raw[n]
    grams[n] = m.volume / 1000.0 * DENSITY
    if n == "knob":
        # the knob plugs into the drawer FACE, so stand its axis along +Y
        m = m.copy()
        m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2, [1, 0, 0]))
        m.apply_translation([0, -m.bounds[0][1], 0])
    if n == "rack":
        # print pose -> assembly pose: flip about X, land on the analytic min
        m = m.copy()
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
        m.apply_translation(-m.bounds[0] + RACK_ASM_MIN)
        assert np.allclose(m.bounds[0], RACK_ASM_MIN, atol=1e-6), m.bounds
        assert np.allclose(m.bounds[1], [RK_X1, RACK_L, 2.0], atol=1e-6), m.bounds
    posed_raw[n] = m                      # full-precision, in assembly pose
    s, nf, did = decimate(m, TARGET.get(n))
    V, F, vol = quantise(s)
    geo[n] = {"v": V.reshape(-1).tolist(), "f": F.reshape(-1).tolist()}
    tris[n] = int(len(F))
    print(f"  {n:11s} {len(m.faces):5d} -> {tris[n]:5d} tri   {len(V):5d} vtx   "
          f"{grams[n]:5.2f} g   {'decimated' if did else 'as printed'}")

# ────────────────────────────────────────────────────────────────────────────
# 2b. The bought parts: one SG90 and the ESP32 on its breadboard.
#
# These are the only things in the picture that are not printed, and leaving
# them out made the render look like a box of plastic rather than a machine.
# Every dimension is the one the case was built around, so if the render shows
# them fitting, they fit - and if it shows them clashing, that is a real clash.
# ────────────────────────────────────────────────────────────────────────────
def _box(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=[x1-x0, y1-y0, z1-z0])
    b.apply_translation([(x0+x1)/2, (y0+y1)/2, (z0+z1)/2])
    return b

def _cyl(d, z0, z1, x=0.0, y=0.0, n=20):
    c = trimesh.creation.cylinder(radius=d/2, height=z1-z0, sections=n)
    c.apply_translation([x, y, (z0+z1)/2])
    return c

def build_servo():
    """SG90, modelled about its OUTPUT SHAFT at the origin, sitting on the shim.

    x is measured from the shaft because that is what the case locates: the
    shaft is the pinion axis. The body hangs sg_shaft one side and the rest the
    other, which is why the cradle is not symmetric."""
    sl, sw, sh = P["sg_l"], P["sg_w"], P["sg_h"]
    x0, x1 = -P["sg_shaft"], -P["sg_shaft"] + sl
    parts = [_box(x0, x1, -sw/2, sw/2, SG_BASE, SG_BASE + sh)]          # body
    bc = (x0 + x1) / 2                       # ears centre on the BODY
    parts.append(_box(bc - P["sg_tab"]/2, bc + P["sg_tab"]/2, -sw/2, sw/2,
                      SG_BASE + P["sg_ear"], SG_BASE + P["sg_ear"] + 2.5))
    parts.append(_cyl(11.5, SG_BASE + sh, SG_BASE + sh + 3.0))          # gear boss
    parts.append(_cyl(4.8, SG_BASE + sh + 3.0, SG_HORN))                # spline
    return trimesh.util.concatenate(parts)

def build_esp():
    """ESP32-S3 DevKit plugged into a half breadboard, as measured: 81.5 long,
    35.5 across, 27.0 tall to the top of a plugged dupont lead."""
    EBL, EBW = 81.5, 35.5
    bb_h = 8.5                                    # breadboard body
    z0 = P["floor_t"]
    parts = [_box(-EBL/2, EBL/2, -EBW/2, EBW/2, z0, z0 + bb_h)]
    # the DevKit straddles the centre channel
    parts.append(_box(-EBL/2 + 9, -EBL/2 + 9 + 63.0, -12.7, 12.7,
                      z0 + bb_h, z0 + bb_h + 1.6))
    # the RF can, the one part with a recognisable silhouette
    parts.append(_box(-EBL/2 + 12, -EBL/2 + 12 + 18.0, -8.0, 8.0,
                      z0 + bb_h + 1.6, z0 + bb_h + 4.0))
    # plugged leads: this is what makes the stack 27 mm, not the board
    for lx in (-EBL/2 + 14, -EBL/2 + 30, -EBL/2 + 46, -EBL/2 + 62):
        for ly in (-15.5, 15.5):
            parts.append(_box(lx-1.2, lx+1.2, ly-1.2, ly+1.2,
                              z0 + bb_h, z0 + P["esp_h"]))
    return trimesh.util.concatenate(parts)

_sv = build_servo()
_svm = _sv.copy(); _svm.apply_transform(np.diag([-1.0, 1.0, 1.0, 1.0]))
# no .invert() here: trimesh already flips the winding itself when the
# transform has a negative determinant, so doing it again turns the mesh
# inside out and every face gets back-face culled
extra_raw = {"servo": _sv, "servo_m": _svm, "esp": build_esp()}
for n in EXTRA:
    m = extra_raw[n]
    grams[n] = 0.0                                # bought, not printed
    V, F, vol = quantise(m)
    geo[n] = {"v": V.reshape(-1).tolist(), "f": F.reshape(-1).tolist()}
    tris[n] = int(len(F))
    print(f"  {n:11s} {len(m.faces):5d} -> {tris[n]:5d} tri   {len(V):5d} vtx"
          f"          bought part")

# the ESP stack must not foul the rack blades - the render would show it, but
# say so numerically too
assert P["floor_t"] + P["esp_h"] < DECK + 0.2 - P["fin_h"], "ESP fouls the blades"

# ────────────────────────────────────────────────────────────────────────────
# 3.  Assembly + exploded transforms
# ────────────────────────────────────────────────────────────────────────────
# base pose at pull = 0, exactly as nano.py's sweep builds it
KNOB_Y = 0.2      # neck butts the drawer face, 4.1 mm stem enters at the face

# Tooth PHASE of the pinion at pull = 0.
#
# Rolling gives the right rotation RATE (theta = pull / R_P) but not the right
# starting angle: pinion tooth 0 is modelled at angle 0, and rack tooth 0 at
# y = PITCH/2, so the two are only in mesh for one particular offset. The rack
# tooth index and the pinion tooth index at the contact point sum to a constant,
# so the condition is simply that the pinion be advanced by the contact point's
# offset along the rack, taken modulo one circular pitch.
#
# Verified by boolean sweep: at this value the rack/pinion overlap is 0.0000 mm3
# across the whole stroke; one angular pitch away it is ~21 mm3 of solid clash.
PIN_PHASE = (((WL + PIN_Y) - (RACK_Y0 + Y_CLOSED)) % PITCH) / R_P
print(f"  pinion tooth phase {math.degrees(PIN_PHASE):.2f} deg "
      f"({PIN_PHASE:.5f} rad) at pull = 0")

INST = []
def add(part, t, ex, pull=0, spin=0, ph=0.0, lab=None, ly=0, show=0):
    INST.append({"p": part, "t": [round(v, 4) for v in t],
                 "ex": [round(v, 4) for v in ex],
                 "pull": pull, "spin": spin, "ph": round(ph, 6),
                 "lab": lab, "ly": ly, "show": show})

add("case_lower", (0, 0, 0),                              (0, 0, 0),      lab="case_lower", ly=64)
add("deck",       (WL+0.3, WL+0.3, DECK-P["deck_t"]),     (0, 0, 40),     lab="deck",       ly=0)
add("case_upper", (0, 0, DECK),                           (0, 0, 92),     lab="case_upper", ly=-46)

for i, dx in enumerate(DR_X):
    side = -1 if i == 0 else 1
    add("drawer", (dx,               Y_CLOSED,       DECK + 0.2),
        (side*18, -62, 68), pull=1, lab=("drawer" if i == 0 else None), ly=-30)
    add("rack",   (dx + FIN_X - P["fin_t"]/2, RACK_Y0 + Y_CLOSED, DECK + P["dr_floor"] + 0.2),
        (side*18, -62, 44), pull=1, lab=("rack" if i == 0 else None), ly=0)
    add("pinion", (dx + FIN_X + PIN_DX, WL + PIN_Y,     PIN_Z),
        (side*18, -62, 22), spin=1, ph=PIN_PHASE,
        lab=("pinion" if i == 0 else None), ly=26)
    # The servo, under its own pinion. Slot 1 is MIRRORED: the shaft is 5.9 mm
    # from one end of the body, so pointing both the same way puts slot 1's
    # mounting ear through the right-hand wall.
    add("servo" if i == 0 else "servo_m", (dx + FIN_X + PIN_DX, WL + PIN_Y, 0),
        (side*18, -62, -18), lab=("SG90" if i == 0 else None), ly=14)
    add("servo_shim", (dx + FIN_X + PIN_DX - (P["sg_l"]+2*P["clear"]-0.6)/2,
                       WL + PIN_Y - (P["sg_w"]+2*P["clear"]-0.6)/2, P["floor_t"]),
        (side*18, -62, -40), lab=("shim" if i == 0 else None), ly=0)

add("esp", (CW/2, CD - 23.0, 0), (0, 66, -30), lab="ESP32-S3", ly=0)

# the knob is only ever shown exploded (P["pull"] == "cut" means it is not
# fitted), so it gets its own clear spot well in front of everything
add("knob", (DR_X[1] + DR_W/2, KNOB_Y, DECK + 0.2 + P["dr_h"]*0.55),
    (34, -96, 6), lab="knob", ly=0, show=1)

# camera fit for both states, with the drawers at full stroke so nothing
# swings out of frame when they open
def fit(explode):
    lo = np.array([1e9]*3); hi = np.array([-1e9]*3)
    for d in INST:
        if d["show"] == 1 and not explode:
            continue
        V = np.array(geo[d["p"]]["v"], dtype=np.float64).reshape(-1, 3) / 100.0
        if d["spin"]:
            th = TRAVEL / R_P + d["ph"]
            c, s = math.cos(th), math.sin(th)
            V = np.column_stack([c*V[:, 0] - s*V[:, 1], s*V[:, 0] + c*V[:, 1], V[:, 2]])
        T = np.array(d["t"], dtype=np.float64)
        if d["pull"]:
            T = T + np.array([0.0, -TRAVEL, 0.0])
        if explode:
            T = T + np.array(d["ex"], dtype=np.float64)
        W = V + T
        lo = np.minimum(lo, W.min(0)); hi = np.maximum(hi, W.max(0))
    c = (lo + hi) / 2.0
    r = float(np.linalg.norm(hi - lo) / 2.0)
    return [round(float(x), 3) for x in c], round(r, 3)

fitA_c, fitA_r = fit(False)
fitE_c, fitE_r = fit(True)
print(f"\n  fit assembled  c={fitA_c} r={fitA_r}")
print(f"  fit exploded   c={fitE_c} r={fitE_r}")

MAT = {"case_lower": "shellB", "case_upper": "shellA", "deck": "gold",
       "drawer": "gold", "rack": "gold", "pinion": "gold", "knob": "gold",
       "servo_shim": "gold", "servo": "blue", "servo_m": "blue",
       "esp": "board"}
COL = {"shellA": "#EDEDF2", "shellB": "#D8D8DF", "gold": "#F2B705",
       "blue": "#2F6FE4", "board": "#1F7A4D"}

QTY  = {"case_lower": 1, "case_upper": 1, "deck": 1,
        "drawer": 2, "rack": 2, "pinion": 2, "servo_shim": 2, "knob": 2,
        "servo": 1, "servo_m": 1, "esp": 1}
BLURB = {
 "case_lower": "mech bay, open top &mdash; servos, pinions, ESP32",
 "case_upper": "drawer bay + top face, printed upside down",
 "deck":       "2.5 mm plate the drawers ride on, slotted for both fins",
 "drawer":     "%.1f &times; %.0f &times; %.0f bin, scalloped finger pull"
               % (DR_W, DR_D, P["dr_h"]),
 "rack":       "toothed blade, pegs through the drawer floor",
 # module and tooth count are templated out of nano.py's P dict, never typed:
 # this row read "m1.25 &times; 12T" for a pinion that has had 16 teeth for as
 # long as the STLs have existed.
 "pinion":     "m__MODULE__ &times; __TEETH__T, bolts to the SG90 horn",
 "servo_shim": "sets the servo height &mdash; reprint this, not the case",
 "knob":       "optional press-fit pull &mdash; unused with the scalloped cut",
 "servo":      "SG90, bought &mdash; drives one drawer through its pinion",
 "servo_m":    "SG90, mirrored &mdash; its shaft is 5.9 mm off the body centre",
 "esp":        "ESP32-S3 on a half breadboard, bought &mdash; no soldering",
}

TOTAL = sum(grams[n]*QTY[n] for n in NAMES if n != "knob")   # printed only

DATA = {
    "parts": geo,
    "inst":  INST,
    "mat":   {n: MAT[n] for n in NAMES + EXTRA},
    "col":   COL,
    "travel": round(TRAVEL, 4),
    "rp":    R_P,
    "cw":    CW, "cd": CD, "ch": CH,
    "fitA":  {"c": fitA_c, "r": fitA_r},
    "fitE":  {"c": fitE_c, "r": fitE_r},
    "bom":   {n: {"q": QTY[n], "g": round(grams[n], 2), "t": tris[n]}
              for n in NAMES + EXTRA},
}

# ────────────────────────────────────────────────────────────────────────────
# 4.  Emit
#
# Every number in the prose below is a template token filled from the geometry,
# never a literal. The copy used to say "m1.25 x 12T" and "one turn" for a
# 16-tooth pinion whose full stroke is half a turn; both were true of an early
# gear and neither had any way of noticing when the gear changed. Derive them
# and a gear change rewrites the sentence instead of quietly falsifying it.
# ────────────────────────────────────────────────────────────────────────────
# TRAVEL is a rack displacement; TRAVEL / R_P is the pinion angle that produces
# it. At m1.25 x 16T, R_P = 10.0 and pi * 10.0 = 31.42 mm = 180 deg exactly.
PIN_TURN_DEG = math.degrees(TRAVEL / R_P)
if abs(PIN_TURN_DEG - 180.0) < 0.5:
    PIN_TURN = "exactly half a turn"
elif abs(PIN_TURN_DEG - 360.0) < 0.5:
    PIN_TURN = "one full turn"
else:
    PIN_TURN = f"{PIN_TURN_DEG:.0f}&deg;"
print(f"  pinion m{M:g} x {N}T, pitch radius {R_P:.1f} -> full stroke "
      f"{TRAVEL:.2f} mm = {PIN_TURN_DEG:.1f} deg ({PIN_TURN})")

# Triangle budget, counted off the payload rather than written down. tris[] is
# per unique mesh; INST is what is actually drawn, and the knob is exploded-only
# (show == 1), so the assembled frame is the cheaper of the two counts.
TRI_UNIQUE = sum(tris.values())
TRI_FRAME  = sum(tris[i["p"]] for i in INST if i["show"] == 0)
TRI_EXPL   = sum(tris[i["p"]] for i in INST)

rows = []
for n in NAMES + EXTRA:
    rows.append(
        '<li class="v3d-row" data-part="{n}">'
        '<span class="v3d-sw" style="background:{c}"></span>'
        '<span class="v3d-nm">{n}<em>&times;{q}</em></span>'
        '<span class="v3d-gm">{gm}</span>'
        '<span class="v3d-bl">{b}</span>'
        '<span class="v3d-tr">{t} tri</span>'
        '</li>'.format(n=n, c=COL[MAT[n]], q=QTY[n],
                       gm=("bought" if n in EXTRA else f"{grams[n]:.1f} g"),
                       b=BLURB[n], t=tris[n]))
ROWS = "\n      ".join(rows)

CSS = r"""
<style>
.v3d { --gold:#F2B705; --ln:rgba(138,138,148,.32); font-synthesis:none; }
.v3d h2 { margin:0 0 .35rem; font-size:1.35rem; letter-spacing:-.015em; }
.v3d .v3d-sub { color:var(--text-secondary,#86868b); font-size:.86rem;
                line-height:1.55; margin:0 0 1rem; max-width:70ch; }
.v3d .v3d-sub code { font-size:.82em; padding:.1em .35em; border-radius:4px;
                background:var(--bg-tertiary,#e5e5e7); }

.v3d-bar { display:flex; flex-wrap:wrap; align-items:center; gap:.6rem .9rem;
           margin-bottom:.75rem; }
.v3d-seg { display:inline-flex; border:1px solid var(--border,#d1d1d6);
           border-radius:8px; overflow:hidden; }
.v3d-seg button { appearance:none; border:0; background:transparent; cursor:pointer;
           font:inherit; font-size:.8rem; padding:.42rem .85rem;
           color:var(--text-secondary,#86868b); }
.v3d-seg button + button { border-left:1px solid var(--border,#d1d1d6); }
.v3d-seg button.on { background:var(--accent,#0071e3); color:#fff; }
.v3d-btn { appearance:none; font:inherit; font-size:.8rem; cursor:pointer;
           padding:.42rem .8rem; border-radius:8px;
           border:1px solid var(--border,#d1d1d6);
           background:var(--bg-secondary,#fff); color:var(--text-primary,#1d1d1f); }
.v3d-btn.on { background:var(--accent,#0071e3); border-color:var(--accent,#0071e3); color:#fff; }
.v3d-slide { display:inline-flex; align-items:center; gap:.5rem; font-size:.78rem;
             color:var(--text-secondary,#86868b); }
.v3d-slide input { width:150px; accent-color:var(--gold); }
.v3d-slide output { font-variant-numeric:tabular-nums; min-width:5.4em;
                    color:var(--text-primary,#1d1d1f); font-weight:600; }

.v3d-main { display:flex; gap:1rem; align-items:stretch; }
.v3d-stage { position:relative; flex:1 1 auto; min-width:0;
             height:clamp(340px,54vh,560px); border-radius:12px; overflow:hidden;
             border:1px solid var(--border,#d1d1d6); background:#111116; }
.v3d-stage canvas { display:block; width:100%; height:100%; touch-action:none;
                    cursor:grab; }
.v3d-stage canvas.drag { cursor:grabbing; }
.v3d-labels { position:absolute; inset:0; pointer-events:none; }
.v3d-lab { position:absolute; white-space:nowrap; font-size:.7rem; line-height:1.25;
           padding:.22rem .45rem; border-radius:6px; opacity:0;
           transition:opacity .18s linear;
           background:rgba(14,14,18,.82); color:#f4f4f6;
           border:1px solid rgba(255,255,255,.14);
           backdrop-filter:blur(3px); }
.v3d-lab b { font-weight:650; letter-spacing:.01em; }
.v3d-lab i { font-style:normal; opacity:.6; }
.v3d-lab u { text-decoration:none; color:var(--gold); font-variant-numeric:tabular-nums; }
.v3d-hint { position:absolute; left:10px; bottom:9px; font-size:.66rem;
            color:rgba(255,255,255,.42); pointer-events:none; letter-spacing:.02em; }
.v3d-scale { position:absolute; right:10px; bottom:9px; font-size:.66rem;
             color:rgba(255,255,255,.42); pointer-events:none; }

.v3d-side { flex:0 0 268px; }
.v3d-side h4 { margin:0 0 .5rem; font-size:.7rem; text-transform:uppercase;
               letter-spacing:.09em; color:var(--text-tertiary,#aeaeb2); }
.v3d-bom { list-style:none; margin:0; padding:0;
           border:1px solid var(--border,#d1d1d6); border-radius:10px; overflow:hidden; }
.v3d-row { display:grid; grid-template-columns:12px 1fr auto;
           gap:.15rem .5rem; padding:.45rem .6rem; cursor:default;
           border-top:1px solid var(--border,#d1d1d6); }
.v3d-row:first-child { border-top:0; }
.v3d-row:hover { background:var(--bg-tertiary,#e5e5e7); }
.v3d-sw { width:12px; height:12px; border-radius:3px; margin-top:2px;
          border:1px solid rgba(0,0,0,.22); }
.v3d-nm { font-size:.78rem; font-weight:600; }
.v3d-nm em { font-style:normal; font-weight:400; opacity:.5; margin-left:.35em; }
.v3d-gm { font-size:.78rem; font-variant-numeric:tabular-nums; font-weight:600;
          color:var(--gold); }
.v3d-bl { grid-column:2/4; font-size:.68rem; line-height:1.4;
          color:var(--text-secondary,#86868b); }
.v3d-tr { grid-column:2/4; font-size:.62rem; color:var(--text-tertiary,#aeaeb2);
          letter-spacing:.03em; }
.v3d-tot { margin-top:.55rem; font-size:.74rem; display:flex;
           justify-content:space-between; color:var(--text-secondary,#86868b); }
.v3d-tot b { color:var(--text-primary,#1d1d1f); font-variant-numeric:tabular-nums; }
.v3d-note { font-size:.68rem; line-height:1.55; margin:.7rem 0 0;
            color:var(--text-tertiary,#aeaeb2); }
.v3d-cap { font-size:.66rem; line-height:1.5; margin:.55rem 0 0;
           letter-spacing:.02em; color:var(--text-tertiary,#aeaeb2);
           font-variant-numeric:tabular-nums; }

@media (max-width:820px){
  .v3d-main { flex-direction:column; }
  .v3d-side { flex:1 1 auto; }
  .v3d-stage { height:clamp(300px,46vh,440px); }
}
</style>
"""

BODY = r"""
<div class="v3d" id="v3d-root">
  <h2>shopkeeper NANO &mdash; the real meshes, in 3D</h2>
  <p class="v3d-sub"><b>__DIMS__ mm</b>, two motorised drawers.
    Every triangle below comes out of the STLs in <code>nano/</code>.
    The poses are the ones <code>nano.py</code> uses for its boolean interference
    sweep, so what you are orbiting is exactly what was checked. Drag to orbit,
    scroll to zoom, and run the drawers out their full __TRAVEL__ mm of stroke &mdash;
    __PINTURN__ of a __TEETH__&#8209;tooth pinion.</p>

  <div class="v3d-bar">
    <div class="v3d-seg" id="v3d-seg">
      <button data-m="0" class="on">Assembled</button>
      <button data-m="1">Exploded</button>
    </div>
    <label class="v3d-slide">drawer travel
      <input type="range" id="v3d-pull" min="0" max="__TRAVEL__" step="0.01" value="0">
      <output id="v3d-pullv">0.00 mm</output>
    </label>
    <button class="v3d-btn on" id="v3d-play">&#9646;&#9646; drive</button>
    <button class="v3d-btn" id="v3d-reset">reset view</button>
  </div>

  <div class="v3d-main">
    <div class="v3d-stage" id="v3d-stage">
      <canvas id="v3d-cv"></canvas>
      <div class="v3d-labels" id="v3d-labels"></div>
      <div class="v3d-hint">drag &middot; orbit &nbsp;|&nbsp; scroll &middot; zoom &nbsp;|&nbsp; shift+drag &middot; pan</div>
      <div class="v3d-scale">grid 10 mm</div>
    </div>
    <aside class="v3d-side">
      <h4>Parts &amp; printed weight</h4>
      <ul class="v3d-bom" id="v3d-bom">
      __ROWS__
      </ul>
      <div class="v3d-tot"><span>build total, knobs excluded</span><b>__TOTAL__ g solid</b></div>
      <div class="v3d-tot"><span>&approx; sliced</span><b>__SLICED__ g</b></div>
      <p class="v3d-cap">__TRIU__ triangles unique &middot; __TRIF__ drawn per frame
        assembled, __TRIE__ exploded &middot; no external assets</p>
      <p class="v3d-note">White is plate 1, yellow plate 2 &mdash; one colour per plate,
        zero filament changes. Hover a row to isolate that part.
        Closed, the drawer face sits __YCLOSED__&nbsp;mm inside the mouth; open, it stands
        __TRAVEL__&nbsp;mm proud of that. <code>nano.py</code> does not place the pinion,
        so its height here is derived: gear body against the blade, hub flush under
        the drawer floor.</p>
    </aside>
  </div>
</div>
"""

JS = r"""
<script>
(function () {
"use strict";
var ROOT = document.getElementById('v3d-root');
if (!ROOT || ROOT.__v3d) return;
ROOT.__v3d = 1;

var D = __DATA__;

/* ── geometry ─────────────────────────────────────────────────────────── */
var PARTS = {};
Object.keys(D.parts).forEach(function (k) {
  var p = D.parts[k], nv = p.v.length, V = new Float32Array(nv), i;
  for (i = 0; i < nv; i++) V[i] = p.v[i] * 0.01;
  var F = (nv / 3 > 65535) ? new Uint32Array(p.f) : new Uint16Array(p.f);
  PARTS[k] = { V: V, F: F, nv: nv / 3, nf: F.length / 3 };
});

var INST = [], MAXT = 0;
D.inst.forEach(function (d) {
  var P = PARTS[d.p], n = P.nv;
  INST.push({
    d: d, P: P, part: d.p, mat: D.mat[d.p],
    wx: new Float32Array(n), wy: new Float32Array(n), wz: new Float32Array(n),
    sx: new Float32Array(n), sy: new Float32Array(n), vz: new Float32Array(n),
    ax: 0, ay: 0, seen: false, vis: true
  });
  MAXT += P.nf;
});

/* ── shading palettes ─────────────────────────────────────────────────── */
var LEV = 88, SMAX = 1.95;
function mkpal(hex) {
  var r = parseInt(hex.substr(1, 2), 16),
      g = parseInt(hex.substr(3, 2), 16),
      b = parseInt(hex.substr(5, 2), 16), a = new Array(LEV), i;
  for (i = 0; i < LEV; i++) {
    var s = i / (LEV - 1) * SMAX, R, G, B, k;
    if (s <= 1) { R = r * s; G = g * s; B = b * s; }
    else { k = Math.min(1, (s - 1) * 0.72); R = r + (255 - r) * k; G = g + (255 - g) * k; B = b + (255 - b) * k; }
    a[i] = 'rgb(' + (R | 0) + ',' + (G | 0) + ',' + (B | 0) + ')';
  }
  return a;
}
var PAL = {}, GH = mkpal('#7d7d88');
Object.keys(D.col).forEach(function (k) { PAL[k] = mkpal(D.col[k]); });
/* Finish per material. Printed PLA is semi-matte with a broad sheen from the
   layer lines; an SG90's case is glossy ABS; a PCB is matte solder mask. Giving
   all three the same specular was most of why everything read as one material. */
var FIN = {
  shellA: { ks: 0.26, sp: 22 }, shellB: { ks: 0.26, sp: 22 },
  gold:   { ks: 0.30, sp: 26 },
  blue:   { ks: 0.52, sp: 54 },
  board:  { ks: 0.07, sp: 11 }
};
function finOf(m) { return FIN[m] || FIN.gold; }

/* ── triangle buffers ─────────────────────────────────────────────────── */
var tI = new Int32Array(MAXT), tF = new Int32Array(MAXT),
    tS = new Uint8Array(MAXT), tD = new Float32Array(MAXT),
    ord = new Array(MAXT), nt = 0;

/* ── camera / state ───────────────────────────────────────────────────── */
var az = 0.62, el = 0.36, zoom = 1, panx = 0, pany = 0;
var mode = 0, exT = 0, exTarget = 0;
var pull = 0, playing = true, phase = 0.06;
var hi = null, dirty = true, last = 0;
var FOV = 30 * Math.PI / 180;
var TRAVEL = D.travel, RP = D.rp;
var DEF = { az: 0.62, el: 0.36, zoom: 1, panx: 0, pany: 0 };

var stage = document.getElementById('v3d-stage');
var cv = document.getElementById('v3d-cv');
var ctx = cv.getContext('2d', { alpha: false });
var labWrap = document.getElementById('v3d-labels');
var W = 0, H = 0, DPR = 1, DPR0 = 1, QUAL = 1, runFrames = 0;

/* ── labels ───────────────────────────────────────────────────────────── */
var LABS = [];
INST.forEach(function (I, i) {
  if (!I.d.lab) return;
  var b = D.bom[I.part];
  var e = document.createElement('div');
  e.className = 'v3d-lab';
  e.innerHTML = '<b>' + I.part + '</b> <i>&times;' + b.q + '</i> &middot; <u>' +
                b.g.toFixed(2) + ' g</u>';
  labWrap.appendChild(e);
  LABS.push({ i: i, el: e, ly: I.d.ly || 0, shown: false });
});

/* ── sizing ───────────────────────────────────────────────────────────── */
function resize() {
  var r = stage.getBoundingClientRect();
  /* Pixel fill is the single biggest per-frame cost, so drop resolution
     WHILE the view is moving and put it back the moment it settles. Nobody
     can see 40% fewer pixels on a spinning model; everybody feels the frame
     rate. */
  DPR0 = Math.min(2, window.devicePixelRatio || 1);
  DPR = DPR0 * QUAL;
  W = Math.max(2, Math.round(r.width));
  H = Math.max(2, Math.round(r.height));
  cv.width = Math.round(W * DPR);
  cv.height = Math.round(H * DPR);
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  dirty = true;
}
if (window.ResizeObserver) new ResizeObserver(resize).observe(stage);
window.addEventListener('resize', resize);

/* ── theme ────────────────────────────────────────────────────────────── */
var darkQ = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
/* data-theme wins over the OS preference in BOTH directions: the host page
   stamps it on <html> when the viewer's own theme toggle is used, and a canvas
   that only watched prefers-color-scheme would keep rendering the other
   theme's background behind a correctly themed page. */
function isDark() {
  var a = document.documentElement.getAttribute('data-theme');
  if (a === 'dark') return true;
  if (a === 'light') return false;
  return darkQ ? darkQ.matches : true;
}
if (darkQ && darkQ.addEventListener) darkQ.addEventListener('change', function () { dirty = true; });
if (window.MutationObserver) new MutationObserver(function () { dirty = true; })
  .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

/* ── math helpers ─────────────────────────────────────────────────────── */
function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
function lerp(a, b, t) { return a + (b - a) * t; }

/* ── main draw ────────────────────────────────────────────────────────── */
var GRID_N = 9, GRID_S = 20;   /* 9 cells of 20 mm each way, minor every 10 */
var FCW = D.cw, FCD = D.cd;    /* case footprint, straight from nano.py */

function draw() {
  if (!W) resize();
  var t = ease(exT);
  var cx = lerp(D.fitA.c[0], D.fitE.c[0], t) + panx,
      cy = lerp(D.fitA.c[1], D.fitE.c[1], t) + pany,
      cz = lerp(D.fitA.c[2], D.fitE.c[2], t),
      rad = lerp(D.fitA.r, D.fitE.r, t);

  var dist = rad / Math.sin(FOV / 2) * 1.04 * zoom;
  var ce = Math.cos(el), se = Math.sin(el);
  var eyeX = cx + dist * ce * Math.sin(az),
      eyeY = cy - dist * ce * Math.cos(az),
      eyeZ = cz + dist * se;

  var fx = cx - eyeX, fy = cy - eyeY, fz = cz - eyeZ;
  var fl = 1 / Math.sqrt(fx * fx + fy * fy + fz * fz); fx *= fl; fy *= fl; fz *= fl;
  var rx = fy, ry = -fx, rz = 0;
  var rl = 1 / Math.sqrt(rx * rx + ry * ry) || 1; rx *= rl; ry *= rl;
  var ux = ry * fz - rz * fy, uy = rz * fx - rx * fz, uz = rx * fy - ry * fx;

  var S = (H / 2) / Math.tan(FOV / 2), hw = W / 2, hh = H / 2, NEAR = 0.5;

  /* ── three-point rig, all of it orbiting with the camera ──────────────
     One key light and a weak sky term was the whole rig, which is why every
     surface facing away from it went flat and dead. Key models the form, fill
     opens the shadow side without flattening it, and a rim behind the subject
     separates the silhouette from a dark background - which matters more here
     than usual, because the parts are light plastic on a near-black ground. */
  var la = az - 0.85, lc = Math.cos(0.62), ls = Math.sin(0.62);
  var Lx = lc * Math.sin(la), Ly = -lc * Math.cos(la), Lz = ls;
  var Hx = Lx - fx, Hy = Ly - fy, Hz = Lz - fz;
  var hl = 1 / Math.sqrt(Hx * Hx + Hy * Hy + Hz * Hz); Hx *= hl; Hy *= hl; Hz *= hl;
  /* fill: opposite side, lower, no specular of its own */
  var fa = az + 1.95, fc = Math.cos(0.22), fs2 = Math.sin(0.22);
  var Fx = fc * Math.sin(fa), Fy = -fc * Math.cos(fa), Fz = fs2;
  /* rim: behind the subject, high, reads only at grazing angles */
  var ra = az + Math.PI - 0.35, rc = Math.cos(0.95), rs2 = Math.sin(0.95);
  var Rx = rc * Math.sin(ra), Ry = -rc * Math.cos(ra), Rz = rs2;

  /* background */
  var dark = isDark();
  var g = ctx.createLinearGradient(0, 0, 0, H);
  if (dark) { g.addColorStop(0, '#1b1b21'); g.addColorStop(0.55, '#141418'); g.addColorStop(1, '#0d0d10'); }
  else { g.addColorStop(0, '#2a2a31'); g.addColorStop(0.55, '#1e1e24'); g.addColorStop(1, '#141418'); }
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

  /* ── ground grid on z = 0 ───────────────────────────────────────────── */
  function proj(x, y, z, o) {
    var dx = x - eyeX, dy = y - eyeY, dz = z - eyeZ;
    var vz = dx * fx + dy * fy + dz * fz;
    if (vz <= NEAR) return false;
    var inv = S / vz;
    o[0] = hw + (dx * rx + dy * ry + dz * rz) * inv;
    o[1] = hh - (dx * ux + dy * uy + dz * uz) * inv;
    return true;
  }
  var pa = [0, 0], pb = [0, 0], i, j;
  var gx0 = FCW / 2 - GRID_N * GRID_S / 2, gy0 = FCD / 2 - GRID_N * GRID_S / 2;
  ctx.lineWidth = 1;
  ctx.strokeStyle = 'rgba(150,158,175,.13)';
  ctx.beginPath();
  for (i = 0; i <= GRID_N * 2; i++) {
    var q = i * GRID_S / 2;
    if (proj(gx0 + q, gy0, 0, pa) && proj(gx0 + q, gy0 + GRID_N * GRID_S, 0, pb)) {
      ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]);
    }
    if (proj(gx0, gy0 + q, 0, pa) && proj(gx0 + GRID_N * GRID_S, gy0 + q, 0, pb)) {
      ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]);
    }
  }
  ctx.stroke();
  /* the case footprint */
  ctx.strokeStyle = 'rgba(242,183,5,.30)';
  ctx.beginPath();
  var fp = [[0, 0], [FCW, 0], [FCW, FCD], [0, FCD], [0, 0]], ok = true, first = true;
  for (i = 0; i < fp.length; i++) {
    if (!proj(fp[i][0], fp[i][1], 0, pa)) { ok = false; break; }
    if (first) { ctx.moveTo(pa[0], pa[1]); first = false; } else ctx.lineTo(pa[0], pa[1]);
  }
  if (ok) ctx.stroke();

  /* ── contact shadow ─────────────────────────────────────────────────────
     Without it the assembly hangs in space above its own grid. It is a plain
     screen-space ellipse rather than a projected one: at these camera angles
     the difference is invisible, and a real shadow pass would cost a second
     sort over every triangle. */
  (function () {
    var cpt = [[0, 0], [FCW, 0], [FCW, FCD], [0, FCD]];
    var mnx = 1e9, mny = 1e9, mxx = -1e9, mxy = -1e9, q2;
    for (q2 = 0; q2 < 4; q2++) {
      if (!proj(cpt[q2][0], cpt[q2][1], 0, pa)) return;
      if (pa[0] < mnx) mnx = pa[0];  if (pa[0] > mxx) mxx = pa[0];
      if (pa[1] < mny) mny = pa[1];  if (pa[1] > mxy) mxy = pa[1];
    }
    var rw = (mxx - mnx) / 2 * 1.10, rh = (mxy - mny) / 2 * 1.30;
    if (!(rw > 0.5 && rh > 0.5)) return;
    ctx.save();
    ctx.globalAlpha = 1 - t * 0.55;          /* fades as the view explodes */
    ctx.translate((mnx + mxx) / 2, (mny + mxy) / 2);
    ctx.scale(1, rh / rw);
    var sg = ctx.createRadialGradient(0, 0, rw * 0.10, 0, 0, rw);
    sg.addColorStop(0.00, 'rgba(0,0,0,.50)');
    sg.addColorStop(0.48, 'rgba(0,0,0,.26)');
    sg.addColorStop(1.00, 'rgba(0,0,0,0)');
    ctx.fillStyle = sg;
    ctx.beginPath(); ctx.arc(0, 0, rw, 0, 6.2831853); ctx.fill();
    ctx.restore();
  })();

  /* ── transform + cull + shade ───────────────────────────────────────── */
  nt = 0;
  var AMB = 0.20, KD = 0.60, SKY = 0.11, FILL = 0.17, RIM = 0.30;
  /* Cheap ambient occlusion: everything below the deck is inside a closed box
     and should not be lit like the outside of one. A straight height ramp is
     crude, but it is the difference between a mech bay that reads as a cavity
     and one that reads as a lid photographed from underneath. */
  var AO_Z0 = 0.0, AO_Z1 = D.ch * 0.42, AO_MIN = 0.62;
  for (var ii = 0; ii < INST.length; ii++) {
    var I = INST[ii], d = I.d;
    I.vis = !(d.show === 1 && exT < 0.02);
    if (!I.vis) continue;
    var Tx = d.t[0], Ty = d.t[1], Tz = d.t[2], th = 0;
    if (d.pull) Ty -= pull;
    if (d.spin) th = pull / RP + d.ph;
    if (t > 0) { Tx += d.ex[0] * t; Ty += d.ex[1] * t; Tz += d.ex[2] * t; }

    var V = I.P.V, n = I.P.nv, wx = I.wx, wy = I.wy, wz = I.wz,
        sx = I.sx, sy = I.sy, vzA = I.vz;
    var _f = finOf(I.mat), fKS = _f.ks, fSP = _f.sp;
    var bx0 = 1e9, by0 = 1e9, bx1 = -1e9, by1 = -1e9, seen = false;
    var cth = Math.cos(th), sth = Math.sin(th);
    for (i = 0; i < n; i++) {
      var x = V[3 * i], y = V[3 * i + 1], z = V[3 * i + 2], X, Y, Z;
      if (th) { X = cth * x - sth * y + Tx; Y = sth * x + cth * y + Ty; }
      else { X = x + Tx; Y = y + Ty; }
      Z = z + Tz;
      wx[i] = X; wy[i] = Y; wz[i] = Z;
      var ex_ = X - eyeX, ey_ = Y - eyeY, ez_ = Z - eyeZ;
      var vz = ex_ * fx + ey_ * fy + ez_ * fz;
      vzA[i] = vz;
      if (vz > NEAR) {
        var inv = S / vz;
        var px = hw + (ex_ * rx + ey_ * ry + ez_ * rz) * inv;
        var py = hh - (ex_ * ux + ey_ * uy + ez_ * uz) * inv;
        sx[i] = px; sy[i] = py;
        if (px < bx0) bx0 = px; if (px > bx1) bx1 = px;
        if (py < by0) by0 = py; if (py > by1) by1 = py;
        seen = true;
      }
    }
    I.seen = seen;
    I.ax = seen ? (bx0 + bx1) / 2 : 0;
    I.ay = seen ? (by0 + by1) / 2 : 0;

    var F = I.P.F, nf = I.P.nf;
    for (j = 0; j < nf; j++) {
      var a = F[3 * j], b = F[3 * j + 1], c = F[3 * j + 2];
      var za = vzA[a], zb = vzA[b], zc = vzA[c];
      if (za <= NEAR || zb <= NEAR || zc <= NEAR) continue;
      var ax = wx[a], ay = wy[a], azz = wz[a];
      var e1x = wx[b] - ax, e1y = wy[b] - ay, e1z = wz[b] - azz;
      var e2x = wx[c] - ax, e2y = wy[c] - ay, e2z = wz[c] - azz;
      var nx = e1y * e2z - e1z * e2y,
          ny = e1z * e2x - e1x * e2z,
          nz = e1x * e2y - e1y * e2x;
      var vx = ax - eyeX, vy = ay - eyeY, vv = azz - eyeZ;
      if (nx * vx + ny * vy + nz * vv >= 0) continue;      /* back-facing */
      var nl = nx * nx + ny * ny + nz * nz;
      if (nl <= 0) continue;
      nl = 1 / Math.sqrt(nl); nx *= nl; ny *= nl; nz *= nl;
      var lam = nx * Lx + ny * Ly + nz * Lz; if (lam < 0) lam = 0;
      var lfi = nx * Fx + ny * Fy + nz * Fz; if (lfi < 0) lfi = 0;
      var sh = nx * Hx + ny * Hy + nz * Hz;
      var spec = sh > 0 ? Math.pow(sh, fSP) : 0;
      /* fresnel: 1 at grazing, 0 head-on. Gates the rim so it lands on edges
         rather than washing over broad faces. */
      var vlen = 1 / Math.sqrt(vx * vx + vy * vy + vv * vv);
      var ndv = -(nx * vx + ny * vy + nz * vv) * vlen; if (ndv < 0) ndv = 0;
      var fres = 1 - ndv; fres *= fres * fres;
      var rimd = nx * Rx + ny * Ry + nz * Rz; if (rimd < 0) rimd = 0;
      var ao = (azz - AO_Z0) / (AO_Z1 - AO_Z0); if (ao > 1) ao = 1; if (ao < 0) ao = 0;
      ao = AO_MIN + (1 - AO_MIN) * ao;
      var sv = (AMB + KD * lam + FILL * lfi + SKY * (nz * 0.5 + 0.5)) * ao
             + fKS * spec + RIM * fres * rimd;
      var si = (sv / SMAX * (LEV - 1)) | 0;
      if (si < 0) si = 0; else if (si > LEV - 1) si = LEV - 1;
      tI[nt] = ii; tF[nt] = j; tS[nt] = si;
      tD[nt] = za + zb + zc;
      nt++;      /* the counting sort fills ord; no identity pass needed */
    }
  }

  /* ── painter's algorithm ──────────────────────────────────────────────
     Counting sort, not Array.sort. A comparator call per comparison over
     ~17k triangles every frame was most of the frame budget; bucketing depth
     is O(n) and needs no calls at all. 4096 buckets over the actual depth
     range puts co-bucketed triangles within a fraction of a millimetre of
     each other, which is far finer than the average-depth approximation this
     algorithm rests on anyway. */
  var NB = 4096;
  if (!draw._cnt || draw._cnt.length !== NB + 1) {
    draw._cnt = new Int32Array(NB + 1);
    draw._ordS = new Int32Array(tD.length);
  }
  var cnt = draw._cnt, ordS = draw._ordS;
  if (ordS.length < nt) { ordS = draw._ordS = new Int32Array(tD.length); }
  var dmin = Infinity, dmax = -Infinity, kk;
  for (kk = 0; kk < nt; kk++) {
    var dv = tD[kk];
    if (dv < dmin) dmin = dv;
    if (dv > dmax) dmax = dv;
  }
  var span = dmax - dmin;
  if (!(span > 0)) span = 1;
  var scale = (NB - 1) / span;
  cnt.fill(0);
  var bidx = draw._b && draw._b.length >= nt ? draw._b
           : (draw._b = new Int32Array(tD.length));
  for (kk = 0; kk < nt; kk++) {
    /* far first: invert the bucket so index 0 is the DEEPEST */
    var bi = (NB - 1) - (((tD[kk] - dmin) * scale) | 0);
    if (bi < 0) bi = 0; else if (bi >= NB) bi = NB - 1;
    bidx[kk] = bi; cnt[bi + 1]++;
  }
  for (kk = 0; kk < NB; kk++) cnt[kk + 1] += cnt[kk];
  for (kk = 0; kk < nt; kk++) ordS[cnt[bidx[kk]]++] = kk;
  ord = ordS;

  ctx.lineJoin = 'round';
  ctx.lineWidth = 0.9;

  function pass(ghost) {
    var cur = null, open = false, k, id, I2, F2, f3, a2, b2, c2, col;
    for (k = 0; k < nt; k++) {
      id = ord[k];
      I2 = INST[tI[id]];
      if (hi !== null && ((I2.part === hi) === ghost)) continue;
      col = ghost ? GH[tS[id]] : PAL[I2.mat][tS[id]];
      if (col !== cur) {
        if (open) { ctx.fillStyle = cur; ctx.strokeStyle = cur; ctx.fill(); ctx.stroke(); }
        ctx.beginPath(); open = true; cur = col;
      }
      F2 = I2.P.F; f3 = tF[id] * 3;
      a2 = F2[f3]; b2 = F2[f3 + 1]; c2 = F2[f3 + 2];
      ctx.moveTo(I2.sx[a2], I2.sy[a2]);
      ctx.lineTo(I2.sx[b2], I2.sy[b2]);
      ctx.lineTo(I2.sx[c2], I2.sy[c2]);
      ctx.closePath();
    }
    if (open) { ctx.fillStyle = cur; ctx.strokeStyle = cur; ctx.fill(); ctx.stroke(); }
  }

  if (hi !== null) { ctx.globalAlpha = 0.16; pass(true); ctx.globalAlpha = 1; pass(false); }
  else { pass(false); }

  /* ── labels + leader lines ──────────────────────────────────────────── */
  var la_op = exT < 0.42 ? 0 : Math.min(1, (exT - 0.42) / 0.34);
  ctx.strokeStyle = 'rgba(255,255,255,.30)';
  ctx.lineWidth = 1;
  for (i = 0; i < LABS.length; i++) {
    var L = LABS[i], I3 = INST[L.i];
    if (la_op <= 0 || !I3.seen || !I3.vis) {
      if (L.shown) { L.el.style.opacity = 0; L.shown = false; }
      continue;
    }
    var ax2 = I3.ax, ay2 = I3.ay;
    var side = ax2 < W * 0.5 ? -1 : 1;
    var lx = ax2 + side * 62, ly2 = ay2 + L.ly;
    L.el.style.left = lx + 'px';
    L.el.style.top = ly2 + 'px';
    L.el.style.transform = side < 0 ? 'translate(-100%,-50%)' : 'translate(0,-50%)';
    L.el.style.opacity = la_op;
    L.shown = true;
    ctx.globalAlpha = la_op * 0.75;
    ctx.beginPath();
    ctx.moveTo(ax2, ay2); ctx.lineTo(lx - side * 4, ly2);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }
}

/* ── loop ─────────────────────────────────────────────────────────────── */
function tick(ts) {
  requestAnimationFrame(tick);
  if (document.hidden) return;
  var dt = last ? Math.min(0.05, (ts - last) / 1000) : 0.016;
  last = ts;

  if (exT !== exTarget) {
    var step = dt / 0.75;
    exT += Math.sign(exTarget - exT) * step;
    if (Math.abs(exTarget - exT) < step) exT = exTarget;
    dirty = true;
  }
  if (playing) {
    phase = (phase + dt / 6.2) % 1;
    var p = phase, f;
    if (p < 0.14) f = 0;
    else if (p < 0.44) f = ease((p - 0.14) / 0.30);
    else if (p < 0.60) f = 1;
    else if (p < 0.90) f = 1 - ease((p - 0.60) / 0.30);
    else f = 0;
    setPull(TRAVEL * f, false);
    dirty = true;
  }
  if (dirty) { dirty = false; draw(); runFrames++; } else { runFrames = 0; }
  /* three drawn frames back to back means the user is dragging or something is
     animating. One idle frame is enough to call it settled. */
  var wantQ = runFrames > 2 ? 0.62 : 1;
  if (wantQ !== QUAL) { QUAL = wantQ; resize(); }
}

/* ── controls ─────────────────────────────────────────────────────────── */
var slider = document.getElementById('v3d-pull');
var readout = document.getElementById('v3d-pullv');
function setPull(v, fromUser) {
  pull = Math.max(0, Math.min(TRAVEL, v));
  slider.value = pull;
  readout.textContent = pull.toFixed(2) + ' mm';
  if (fromUser) dirty = true;
}
slider.addEventListener('input', function () {
  if (playing) togglePlay();
  setPull(parseFloat(slider.value), true);
});

var playBtn = document.getElementById('v3d-play');
function togglePlay() {
  playing = !playing;
  playBtn.classList.toggle('on', playing);
  playBtn.innerHTML = playing ? '▮▮ drive' : '▶ drive';
  dirty = true;
}
playBtn.addEventListener('click', togglePlay);

document.getElementById('v3d-reset').addEventListener('click', function () {
  az = DEF.az; el = DEF.el; zoom = DEF.zoom; panx = DEF.panx; pany = DEF.pany;
  dirty = true;
});

var seg = document.getElementById('v3d-seg');
seg.addEventListener('click', function (ev) {
  var b = ev.target.closest ? ev.target.closest('button') : null;
  if (!b) return;
  mode = +b.getAttribute('data-m');
  exTarget = mode;
  Array.prototype.forEach.call(seg.children, function (c) { c.classList.remove('on'); });
  b.classList.add('on');
  dirty = true;
});

document.getElementById('v3d-bom').addEventListener('mouseover', function (ev) {
  var r = ev.target.closest ? ev.target.closest('.v3d-row') : null;
  var v = r ? r.getAttribute('data-part') : null;
  if (v !== hi) { hi = v; dirty = true; }
});
document.getElementById('v3d-bom').addEventListener('mouseleave', function () {
  if (hi !== null) { hi = null; dirty = true; }
});

/* orbit / pan / zoom */
var drag = null, ptrs = {}, pinch = 0;
cv.addEventListener('pointerdown', function (ev) {
  cv.setPointerCapture(ev.pointerId);
  ptrs[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
  if (Object.keys(ptrs).length === 1) {
    drag = { x: ev.clientX, y: ev.clientY, pan: ev.shiftKey || ev.button === 2 };
    cv.classList.add('drag');
  }
});
cv.addEventListener('pointermove', function (ev) {
  if (!ptrs[ev.pointerId]) return;
  var ks = Object.keys(ptrs);
  ptrs[ev.pointerId].x = ev.clientX; ptrs[ev.pointerId].y = ev.clientY;
  if (ks.length >= 2) {
    var a = ptrs[ks[0]], b = ptrs[ks[1]];
    var dd = Math.hypot(a.x - b.x, a.y - b.y);
    if (pinch) { zoom = Math.max(0.32, Math.min(3.4, zoom * pinch / dd)); dirty = true; }
    pinch = dd;
    return;
  }
  if (!drag) return;
  var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
  drag.x = ev.clientX; drag.y = ev.clientY;
  if (drag.pan) {
    var k = 0.34 * zoom;
    panx -= (dx * Math.cos(az) + dy * Math.sin(az) * Math.sin(el)) * k;
    pany -= (dx * Math.sin(az) - dy * Math.cos(az) * Math.sin(el)) * k;
  } else {
    az -= dx * 0.0075;
    el = Math.max(-1.45, Math.min(1.45, el + dy * 0.0075));
  }
  dirty = true;
});
function up(ev) {
  delete ptrs[ev.pointerId];
  if (!Object.keys(ptrs).length) { drag = null; pinch = 0; cv.classList.remove('drag'); }
}
cv.addEventListener('pointerup', up);
cv.addEventListener('pointercancel', up);
cv.addEventListener('contextmenu', function (e) { e.preventDefault(); });
cv.addEventListener('wheel', function (ev) {
  ev.preventDefault();
  zoom = Math.max(0.32, Math.min(3.4, zoom * Math.exp(ev.deltaY * 0.0012)));
  dirty = true;
}, { passive: false });

resize();
setPull(0, true);
requestAnimationFrame(tick);
})();
</script>
"""

# __ROWS__ goes in FIRST: the part blurbs carry tokens of their own (the pinion
# row is templated on module and tooth count), and a token pasted in after its
# own substitution has run is a token that ships to the browser.
TOKENS = {
    "__ROWS__":   ROWS,
    "__TRAVEL__": f"{TRAVEL:.2f}",
    "__DIMS__":   f"{CW:.0f} &times; {CD:.0f} &times; {CH:.0f}",
    "__YCLOSED__": f"{Y_CLOSED:.1f}",
    "__TOTAL__":  f"{TOTAL:.0f}",
    "__SLICED__": f"{TOTAL*0.85:.0f}",
    "__MODULE__": f"{M:g}",
    "__TEETH__":  f"{N:d}",
    "__PINTURN__": PIN_TURN,
    "__TRIU__":   f"{TRI_UNIQUE:,}",
    "__TRIF__":   f"{TRI_FRAME:,}",
    "__TRIE__":   f"{TRI_EXPL:,}",
}
body = BODY
for _tok, _val in TOKENS.items():
    body = body.replace(_tok, _val)
left = [t for t in TOKENS if t in body]
assert not left, f"unsubstituted template tokens reached the page: {left}"

html = CSS + body + JS.replace("__DATA__", json.dumps(DATA, separators=(",", ":")))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(html)

# The above is a FRAGMENT (one <style>, one <div>, one <script>) because that is
# what the brainstorm page and the artifact host both want - they supply the
# document shell. Serving it on localhost needs a real document, so wrap the
# same bytes rather than generating a second, drifting copy.
STANDALONE = os.path.normpath(os.path.join(HERE, "..", "nano", "viewer", "index.html"))
os.makedirs(os.path.dirname(STANDALONE), exist_ok=True)
PAGE = ("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>shopkeeper NANO &mdash; assembly</title>
<style>
  :root { --bg-primary:#fbfbfd; --bg-secondary:#fff; --text-primary:#1d1d1f;
          --text-secondary:#86868b; --text-tertiary:#aeaeb2; --accent:#0071e3;
          --gold:#F2B705; --hair:rgba(0,0,0,.10); }
  @media (prefers-color-scheme: dark) {
    :root { --bg-primary:#0b0b0f; --bg-secondary:#15151b; --text-primary:#f4f4f6;
            --text-secondary:#a0a0aa; --text-tertiary:#6e6e78;
            --hair:rgba(255,255,255,.12); }
  }
  * { box-sizing:border-box; }
  body { margin:0; padding:24px; background:var(--bg-primary);
         color:var(--text-primary); font:15px/1.5 -apple-system,BlinkMacSystemFont,
         'SF Pro Text',Inter,system-ui,sans-serif; }
  main { max-width:1180px; margin:0 auto; }
</style></head><body><main>
""" + html + """
</main></body></html>""")
with open(STANDALONE, "w", encoding="utf-8") as fh:
    fh.write(PAGE)
print(f"  standalone {STANDALONE}  ({len(PAGE)/1024:.0f} KiB)")

# ────────────────────────────────────────────────────────────────────────────
# 5.  Verify
# ────────────────────────────────────────────────────────────────────────────
def remesh(name):
    """FULL-PRECISION mesh in assembly pose, not the display copy.

    The display copy is quantised to 0.01 mm, and the involute pinion has flank
    points closer together than that - so quantising welds them, drops the
    degenerate faces and leaves a shell that is no longer a volume. Booleans
    refuse it, and rightly. The phase and Z being checked here are properties
    of the real geometry, so check them against the real geometry."""
    return posed_raw[name].copy()

def posed(inst, pull):
    m = remesh(inst["p"])
    if inst["spin"]:
        m.apply_transform(trimesh.transformations.rotation_matrix(
            pull / R_P + inst["ph"], [0, 0, 1]))
    t = np.array(inst["t"], dtype=np.float64)
    if inst["pull"]:
        t = t + np.array([0.0, -pull, 0.0])
    m.apply_translation(t)
    return m

# The pinion's tooth phase and Z are derived, not taken from nano.py, so prove
# them the way nano.py proves everything else: with a boolean sweep. One angular
# pitch out of phase this reads ~21 mm3 of solid steel-through-steel.
rk = next(i for i in INST if i["p"] == "rack")
pn = next(i for i in INST if i["p"] == "pinion")
worst, wp = 0.0, None
for p_ in (0.0, TRAVEL*0.2, TRAVEL*0.4, TRAVEL*0.6, TRAVEL*0.8, TRAVEL):
    h = trimesh.boolean.intersection([posed(rk, p_), posed(pn, p_)], engine="manifold")
    v = float(h.volume) if h.volume == h.volume else 0.0
    if v > worst: worst, wp = v, p_
print(f"\n  rack/pinion mesh sweep: worst overlap {worst:.4f} mm3"
      + (f" at pull {wp:.1f}" if wp is not None else "") +
      f"   [{'PASS' if worst < 1.0 else 'FAIL'}]")
MESH_OK = worst < 1.0

sz = os.path.getsize(OUT)
txt = open(OUT, encoding="utf-8").read()
bad = [s for s in ("http://", "https://", "//cdn", "src=", "@import", "fetch(",
                   "XMLHttpRequest", "importScripts") if s in txt]
missing = [n for n in NAMES + EXTRA if f'"{n}"' not in txt]
# The prose has to agree with the geometry it is describing, so assert the
# rendered strings rather than trusting that the templating ran.
prose = [s for s in (f"m{M:g} &times; {N:d}T", f"{N:d}&#8209;tooth",
                     f"{TRI_UNIQUE:,} triangles unique", f"{TRI_FRAME:,} drawn per frame")
         if s not in txt]
print(f"\n  wrote {OUT}")
print(f"  {sz/1024:.1f} KiB ({sz} bytes)")
print(f"  external references: {bad if bad else 'none'}")
print(f"  parts missing from the payload: {missing if missing else 'none'}")
print(f"  prose out of step with the geometry: {prose if prose else 'none'}")
print(f"  triangles: " + ", ".join(f"{n}={tris[n]}" for n in NAMES + EXTRA)
      + f"   total unique={TRI_UNIQUE}")
print(f"  drawn per frame: {TRI_FRAME} assembled, {TRI_EXPL} exploded")
print(f"  build total {TOTAL:.1f} g solid")
if bad or missing or prose or sz < 40000 or not MESH_OK:
    sys.exit("VERIFY FAILED")
print("  OK")
