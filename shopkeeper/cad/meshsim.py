#!/usr/bin/env python3
"""
MESH SIM — does the gear pair actually turn, at the size the machine prints?

Every other check in this repo asks whether parts OVERLAP where they sit. A
gear pair can pass all of those and still be unusable, because a gear is not a
static fit: the flanks have to slide across each other through the whole tooth
cycle without ever fouling. The pinion shipped as a straight-sided trapezoid,
which is the correct profile for a RACK and the wrong one for a pinion - it
carried 0.26 mm of excess material per flank at the tip, met the rack with zero
clearance at nominal size, and hard-jammed at the +0.05 mm per surface that
generic PLA actually prints at.

So: roll the pair through a full tooth cycle in 2D, at several print growths,
and report the tightest gap. Dilating a polygon by d is exactly what an FDM
machine does to a part - it lays its walls slightly proud - so growth is
modelled as a positive buffer on both profiles.
"""
import os, sys, math
import numpy as np
from shapely.geometry import Polygon
from shapely.affinity import rotate as _rot, translate as _tr
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nano as NA

R_P, ADD, DED = NA.R_P, NA.ADD, NA.DED
PITCH, M, N = NA.PITCH, NA.M, NA.N
FIN_T, FIN_SPAN, TOOTH_H = NA.P["fin_t"], NA.FIN_SPAN, NA.TOOTH_H
PRESS, BL = NA.P["press"], NA.P["backlash"]

PITCH_X = FIN_SPAN - ADD              # rack pitch line, rack-local x
# The BUILT centre distance, not the theoretical one. nano.py biases it out by
# cd_bias to absorb the servo's pocket play; simulating the textbook 10.000
# tests a pair that is not the one on the plate.
AXIS_X  = PITCH_X + NA.CDIST          # pinion axis, rack-local x


def pinion_2d():
    pts = []
    STEPS = 16
    for i in range(N):
        th = 2*math.pi*i/N
        rs = [NA.R_ROOT] + [NA.R_BASE + (NA.R_TIP-NA.R_BASE)*k/(STEPS-1)
                            for k in range(STEPS)]
        for r in rs:
            a = th - NA.tooth_half_angle(r)
            pts.append((r*math.cos(a), r*math.sin(a)))
        for r in reversed(rs):
            a = th + NA.tooth_half_angle(r)
            pts.append((r*math.cos(a), r*math.sin(a)))
    return _tr(Polygon(pts), AXIS_X, 0.0)


def rack_2d(n_teeth=9):
    """Rack profile in plan: the blade plus n teeth, centred on y=0."""
    hp  = (PITCH/2 - BL)/2
    tip = hp - ADD*math.tan(PRESS)
    rt  = hp + DED*math.tan(PRESS)
    span = n_teeth*PITCH
    body = Polygon([(0, -span), (FIN_T, -span), (FIN_T, span), (0, span)])
    tt = [body]
    for i in range(-n_teeth, n_teeth+1):
        yc = i*PITCH
        tt.append(Polygon([(FIN_T, yc-rt), (FIN_T+TOOTH_H, yc-tip),
                           (FIN_T+TOOTH_H, yc+tip), (FIN_T, yc+rt)]))
    return unary_union(tt)


def _roll(pin0, rk0, phi, phases):
    """Roll one tooth cycle at a FIXED assembly phase phi.

    Returns the tightest gap seen, or None if the pair fouls anywhere. phi is
    fixed for the whole roll because that is the physical situation: once the
    pinion is pressed onto the horn, the phase is set and every tooth after
    that has to clear at that phase."""
    mn = 1e9
    for k in range(phases):
        th = 2*math.pi/N * k/(phases-1)                 # one tooth of rotation
        pin = _rot(pin0, math.degrees(th), origin=(AXIS_X, 0.0))
        # CONJUGATE DIRECTION. The rack sits on the -x side of the axis, so the
        # pinion's surface at the pitch point moves in -y as it turns +theta:
        # v = w z_hat x (-R_P x_hat) = -w R_P y_hat. Driving the rack +R_P*theta
        # runs the teeth INTO each other and reports a sound gear as jammed.
        rk  = _tr(rk0, 0.0, -R_P*th + phi)
        if pin.intersects(rk) and pin.intersection(rk).area > 1e-9:
            return None
        mn = min(mn, pin.distance(rk))
    return mn


def best_phase(steps=97, phases=41):
    """The assembly phase that meshes. A tooth must land in a SPACE, which is
    half a pitch from tooth-on-tooth - so this has to be searched over a whole
    pitch. Searching only the backlash window finds nothing and reports a
    perfectly good gear as jammed."""
    pin0, rk0 = pinion_2d(), rack_2d()
    best, bphi = None, 0.0
    for j in range(steps):
        phi = PITCH * j/steps
        g = _roll(pin0, rk0, phi, phases)
        if g is not None and (best is None or g > best):
            best, bphi = g, phi
    return bphi, best


def sweep(phi, grow=0.0, phases=41, float_steps=9):
    """Tightest gap at growth `grow`, letting the rack float within backlash."""
    pin0 = pinion_2d().buffer(grow) if grow else pinion_2d()
    rk0  = rack_2d().buffer(grow)  if grow else rack_2d()
    best = None
    for j in range(float_steps):
        slack = (j/(float_steps-1) - 0.5) * 2*BL
        g = _roll(pin0, rk0, phi + slack, phases)
        if g is not None and (best is None or g > best):
            best = g
    return best


if __name__ == "__main__":
    print("\nMESH SIM — shopkeeper NANO")
    print(f"  m{M} x {N}T, pressure {math.degrees(PRESS):.1f} deg, "
          f"addendum {ADD/M:.2f}m, backlash {BL:.2f} per flank")
    print(f"  pitch radius {R_P:.2f}, centre distance {AXIS_X-PITCH_X:.3f} "
          f"(biased +{NA.P['cd_bias']:.2f} for servo pocket play)")
    print(f"  pinion tip thickness {2*NA.tooth_half_angle(NA.R_TIP)*NA.R_TIP:.3f} mm\n")
    phi, g0 = best_phase()
    if g0 is None:
        print("  *** no assembly phase meshes at all")
        sys.exit(1)
    print(f"  meshing phase {phi:.3f} mm, nominal gap {g0:.3f} mm\n")
    print(f"  {'print growth':>14s}  {'result':>28s}")
    bad = []
    for g in (0.0, 0.05, 0.10, 0.15, 0.20):
        gap = sweep(phi, g)
        if gap is None:
            print(f"  {g:>+13.2f}   {'JAMS':>28s}")
            bad.append(g)
        else:
            print(f"  {g:>+13.2f}   {'runs, min gap %.3f mm' % gap:>28s}")
    print()
    # generic PLA on a P2S runs +0.05 to +0.12 per external surface
    if any(g <= 0.12 for g in bad):
        print("  *** JAMS INSIDE THE RANGE GENERIC PLA ACTUALLY PRINTS AT")
        sys.exit(1)
    print("  MESHES THROUGH THE FULL PLA RANGE (+0.00 to +0.12 per surface)")
