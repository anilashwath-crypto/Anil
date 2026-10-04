#!/usr/bin/env python3
"""
FITCHECK — every mating fit, MEASURED off the shipped meshes.

cad/tolerances.py computes fits from the parameters. That is worth having, but
it can only ever tell you what the design INTENDED: it read a private copy of
the parameters that had frozen two revisions back and printed a clean audit of
a case that no longer existed. And the parameters have been right while the
mesh was wrong more than once in this project - the rack's flange was correct
in the source and 155 mm3 inside the drawer in the STL.

So this file measures. It ray-casts through the actual STLs, finds the real
hole and slot widths, and compares them to the real peg and blade widths.

BANDS ARE FOR PLA, not PETG. The difference matters in one direction
especially: PETG is tough and takes an interference fit by deforming, PLA is
brittle and takes it by snapping. A 3.0 pin in a 3.35 socket is a normal PETG
press fit and a broken PLA pin.
"""
import os, sys, math
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
N    = os.path.join(HERE, "..", "nano")
sys.path.insert(0, HERE)
import nano as NA

P = NA.P

# ── PLA bands, per side unless stated ──────────────────────────────────
BANDS = {
    "press":    (-0.06,  0.00),   # PLA snaps rather than yields; almost no bite
    "location": ( 0.08,  0.25),   # drops in by hand, stays put, glue or peg
    "running":  ( 0.25,  0.60),   # slides without binding
    "free":     ( 0.60, 99.00),   # must never touch
    # A bought part gets its own band. An SG90 clone's body varies about
    # 0.3 mm between batches, so a pocket held to the printed-part location
    # band would refuse a fat one - and refusing to accept the servo is a
    # worse failure than a little play, now that the centre distance is
    # biased to absorb exactly this.
    "dropin":   ( 0.15,  0.45),   # bought component into a printed pocket
    "thread":   ( 1.60,  1.75),   # M2 self-tap pilot DIAMETER
}

rows, bad, warn = [], 0, 0


def _runs(mesh, origin, direction, span=200.0):
    """Solid intervals along a ray, as distances from origin."""
    o = np.array(origin, float); d = np.array(direction, float)
    d = d/np.linalg.norm(d)
    rmi = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)
    locs, _, _ = rmi.intersects_location([o - d*span], [d])
    if len(locs) == 0:
        return []
    t = np.sort(np.dot(locs - (o - d*span), d))
    # weld hits that land on a shared edge
    keep = [t[0]]
    for v in t[1:]:
        if v - keep[-1] > 1e-6:
            keep.append(v)
    t = np.array(keep) - span
    if len(t) % 2:
        return []
    return [(t[i], t[i+1]) for i in range(0, len(t), 2)]


def void(mesh, origin, direction, span=200.0):
    """Width of the void CONTAINING the origin point.

    Not "the first void along the ray" - that reads the case's own hollow
    interior instead of the servo pocket, and a fin slot instead of a pin hole.
    The ray has to be told which feature is meant, and the origin is what says
    so: t=0 is the point aimed at."""
    r = _runs(mesh, origin, direction, span)
    if len(r) < 2:
        return None
    for (a0, a1), (b0, b1) in zip(r, r[1:]):
        if a1 <= 0.0 <= b0:
            return b0 - a1
    return None


def solid(mesh, origin, direction, span=200.0):
    """Width of the solid run CONTAINING the origin point."""
    r = _runs(mesh, origin, direction, span)
    for a, b in r:
        if a <= 0.0 <= b:
            return b - a
    return None


# What the machine adds to what the model says. An FDM printer lays its walls
# slightly proud, so a peg comes out over size and a hole comes out under size,
# and the two errors ADD in the same direction - against the clearance. These
# are ordinary generic-PLA figures for a 0.4 nozzle.
GROW_EXT = 0.05      # per side, printed external feature (peg, blade, tooth)
SHRINK_INT = 0.05    # per side, printed internal feature (hole, slot, pocket)


def fit(name, male, female, kind, note="", male_printed=True):
    """Judged on AS-PRINTED size, not nominal.

    A fit is not a number in the model, it is what comes off the plate. Judging
    the model number passes joints that seize and fails joints that are fine -
    the pins are drawn deliberately loose precisely so they land in band once
    the machine has had its say. male_printed=False for a bought part (the
    servo does not grow; only the pocket around it shrinks)."""
    global bad, warn
    if male is None or female is None:
        rows.append((name, "?", "?", "?", kind, "NO READ", note)); bad += 1; return
    nom = (female - male)/2.0
    asp = nom - SHRINK_INT - (GROW_EXT if male_printed else 0.0)
    lo, hi = BANDS[kind]
    if asp < lo - 1e-9:
        v, sev = "TIGHT", 2
    elif asp > hi + 1e-9:
        v, sev = "LOOSE", 1
    else:
        v, sev = "ok", 0
    bad += (sev == 2); warn += (sev == 1)
    rows.append((name, f"{male:.3f}", f"{female:.3f}",
                 f"{nom:+.3f} -> {asp:+.3f}", f"{kind} {lo:.2f}..{hi:.2f}", v, note))


def raw(name, value, lo, hi, note=""):
    global bad, warn
    if value is None:
        rows.append((name, "?", "?", "?", "-", "NO READ", note)); bad += 1; return
    if value < lo - 1e-9:   v, sev = "UNDER", 2
    elif value > hi + 1e-9: v, sev = "OVER", 1
    else:                   v, sev = "ok", 0
    bad += (sev == 2); warn += (sev == 1)
    rows.append((name, "-", f"{value:.3f}", "-", f"{lo:.2f}..{hi:.2f}", v, note))


L = lambda n: trimesh.load(os.path.join(N, n + ".stl"))
case_lo, case_up = L("case_lower"), L("case_upper")
deck, drawer, pinion = L("deck"), L("drawer"), L("pinion")


print("\nFITCHECK — measured off the shipped STLs, PLA bands\n")


# ── 1. ALIGNMENT PINS: case_lower -> deck -> case_upper ────────────────
H, zt = NA.DECK, NA.DECK - P["deck_t"]
for i, (hx, hy) in enumerate(NA.PIN_POS):
    # cast along Y for the pins: an X ray at a rear corner also crosses the
    # side wall, and at the front pin it crosses both fin slots
    d_pin  = solid(case_lo, [hx, hy, H + 2.0], [0, 1, 0])
    d_deck = void(deck, [hx - (NA.WL+0.3), hy - (NA.WL+0.3), 1.25], [0, 1, 0])
    d_sock = void(case_up, [hx, hy, 2.0], [0, 1, 0])
    tag = ["rear-L", "rear-R", "front"][i]
    fit(f"pin {tag} in deck hole", d_pin, d_deck, "location", "deck drops over the pins")
    fit(f"pin {tag} in upper socket", d_pin, d_sock, "location", "case halves register")

# ── 4. DRAWER -> CASE ──────────────────────────────────────────────────
dw = drawer.extents[0]
# Height AT THE FRONT, not overall. The anti-tip rib stands 3 mm proud of the
# rear wall and never passes through the mouth - taking the overall height
# reports a drawer that demonstrably sweeps the full stroke as 1.7 mm too tall.
dv = drawer.vertices
dh = float(dv[dv[:, 1] < NA.DR_D - P["dr_wall"] - 1.0][:, 2].max())
dh_rib = float(drawer.extents[2])
mouth_w = void(case_up, [NA.DR_X[0] + NA.DR_W/2, 1.0, 9.0], [1, 0, 0])
fit("drawer in its mouth, width", dw, mouth_w, "running", "left-right rattle")
# Vertical is not a symmetric fit: the drawer RESTS on the deck, so all the
# clearance is above it. Report the headroom, not a two-sided clearance.
mouth_top = NA.DR_TOP + P["gap"] - NA.DECK
raw("headroom above the drawer, at the mouth", mouth_top - (0.2 + dh), 0.30, 2.50,
    "drawer sits on the deck; all clearance is on top")
raw("headroom above the drawer, in the bay", (NA.CH - NA.DECK - NA.WL) - (0.2 + dh),
    0.30, 6.00, "body only")
raw("headroom above the ANTI-TIP RIB", (NA.CH - NA.DECK - NA.WL) - (0.2 + dh_rib),
    0.30, 1.50, "this is the number that limits nose droop - small is the point")

# ── 8. LOGO INLAY -> POCKET ────────────────────────────────────────────
inlay = L("logo_inlay")
raw("logo inlay proud of the case face", inlay.extents[2] - 1.4, 0.05, 0.40,
    "sits in a 1.4 pocket; must read as embossed, not sunken")

# ── 9. DECK -> CASE_LOWER LEDGE ────────────────────────────────────────
dk_x, dk_y = deck.extents[0], deck.extents[1]
raw("deck side clearance in the case", ((NA.CW - 2*NA.WL) - dk_x)/2, 0.15, 0.60,
    "must drop in without forcing")
raw("deck end clearance in the case", ((NA.CD - 2*NA.WL) - dk_y)/2, 0.15, 0.60)

# ── report ─────────────────────────────────────────────────────────────
w = [max(len(str(r[i])) for r in rows + [("fit", "male", "female",
                                          "nominal -> as printed",
                                          "band", "verdict", "note")])
     for i in range(7)]
hdr = ("fit", "male", "female", "nominal -> as printed", "band", "verdict", "note")
print("  " + "  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
print("  " + "-" * (sum(w) + 12))
for r in rows:
    print("  " + "  ".join(str(r[i]).ljust(w[i]) for i in range(7)))
print(f"\n  {bad} will not work, {warn} sloppy but will work\n")
sys.exit(1 if bad else 0)
