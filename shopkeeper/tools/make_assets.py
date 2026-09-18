#!/usr/bin/env python3
"""
Every image and animation in the README, generated from the shipped meshes.

Nothing is drawn by hand and nothing is faked. The mechanism animation turns
the pinion by theta and slides the drawer by R_P*theta - the same relation the
firmware commands - so if the geometry is wrong the animation shows it wrong.
"""
import os, sys, math
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "cad")); sys.path.insert(0, HERE)
import nano as NA
from render import (render, obj, moved, spun, GRAPHITE, STEEL, SIGNAL,
                    DECKC, EMBER, BRASS)

OUT = os.path.join(ROOT, "docs/img")
os.makedirs(OUT, exist_ok=True)
L = lambda n: trimesh.load(os.path.join(ROOT, "nano", n + ".stl"))

CL, DK, CU = L("case_lower"), L("deck"), L("case_upper")
DR, PN, KN = L("drawer"), L("pinion"), L("knob")
DECK_T = NA.P["deck_t"]
DZ = NA.DECK - DECK_T
CENTRE = (NA.CW/2, NA.CD/2, NA.CH/2)

MAT_CASE = dict(gloss=40, spec=0.30, rim=(0.26, 0.30, 0.38))
MAT_DR   = dict(gloss=22, spec=0.42, rim=(0.42, 0.24, 0.10))
MAT_MECH = dict(gloss=70, spec=0.85, rim=(0.45, 0.50, 0.58))


def servo(px, sgn):
    """Solid proxy for the SG90, at its real size and real pose."""
    bcx = NA.sg_body_cx(0, px) if hasattr(NA, "sg_body_cx") else px
    b = trimesh.creation.box(extents=[22.8, 12.2, 22.7])
    b.apply_translation([bcx, NA.WL + NA.PIN_Y, NA.SG_BASE + 22.7/2])
    t = trimesh.creation.box(extents=[32.2, 12.2, 2.5])
    t.apply_translation([bcx, NA.WL + NA.PIN_Y, NA.SG_BASE + 15.9 + 1.25])
    return trimesh.util.concatenate([b, t])


def pin_x(slot):
    return NA.DR_X[slot] + NA.FIN_X + NA.PIN_DX


def cabinet(pull=(0.0, 0.0), show_case=True, show_mech=True, sep=0.0):
    """The whole assembly. sep>0 explodes it along z."""
    o = []
    if show_case:
        o.append(obj(moved(CL, 0, 0, -sep*0.55), GRAPHITE, **MAT_CASE))
        o.append(obj(moved(DK, NA.WL+0.3, NA.WL+0.3, DZ + sep*1.05), DECKC, **MAT_CASE))
        # 2.2 was not enough: at sep 26 the lid's underside sat at 99.2 while
        # the drawers reached 101.8 and the two interpenetrated
        o.append(obj(moved(CU, 0, 0, NA.DECK + sep*3.25), GRAPHITE, **MAT_CASE))
    for s in (0, 1):
        o.append(obj(moved(DR, NA.DR_X[s], -pull[s], NA.DECK + 0.2 + sep*1.95),
                     SIGNAL, **MAT_DR))
    if show_mech:
        for s in (0, 1):
            th = pull[s] / NA.R_P
            o.append(obj(moved(spun(PN, math.degrees(th)),
                               pin_x(s), NA.WL + NA.PIN_Y,
                               NA.SG_HORN + sep*0.62),
                         STEEL, **MAT_MECH))
            o.append(obj(moved(servo(pin_x(s), 1), 0, 0, sep*0.15),
                         (0x1B, 0x3A, 0x8F), gloss=18, spec=0.25))
    return o


def save(img, name):
    p = os.path.join(OUT, name)
    Image.fromarray(img).save(p, optimize=True)
    print(f"  {name:22s} {img.shape[1]}x{img.shape[0]}  "
          f"{os.path.getsize(p)/1024:.0f} KB")


def gif(frames, name, ms=70):
    p = os.path.join(OUT, name)
    ims = [Image.fromarray(f).convert("P", palette=Image.ADAPTIVE, colors=128)
           for f in frames]
    ims[0].save(p, save_all=True, append_images=ims[1:], duration=ms,
                loop=0, optimize=True, disposal=2)
    print(f"  {name:22s} {len(frames)} frames  "
          f"{os.path.getsize(p)/1024:.0f} KB")


def ease(t):
    return t*t*(3 - 2*t)


# ── 1. hero ───────────────────────────────────────────────────────────────
def hero():
    """Banner. Shot from high three-quarter, which is the angle that reads
    best here: from lower down you see straight through the gap between the
    two drawer mouths into the bay, because case_lower's front wall stops at
    the deck line and the mullion above it is thin."""
    cmd = NA.TRAVEL*153/180
    o = cabinet(pull=(cmd, cmd*0.30))
    img = render(o, eye=(120, -152, 178), target=(46, 28, 26),
                 W=1600, H=620, fov=26, ss=3,
                 lights=((0.50, -0.80, 0.80, 1.20),
                         (-0.90, -0.30, 0.30, 0.44),
                         (0.05, 0.85, 0.45, 0.28)))
    save(img, "hero.png")


# ── 2. exploded ───────────────────────────────────────────────────────────
def exploded_still():
    o = cabinet(pull=(0, 0), sep=26.0)
    img = render(o, eye=(210, -250, 190), target=(46, 34, 78),
                 W=1200, H=1000, fov=27, ss=3)
    save(img, "exploded.png")


def exploded_labelled(n=40):
    """Exploded, with each part named as it separates. The unlabelled version
    shows that it comes apart; this one says what the pieces are, which is what
    somebody being handed the repo actually needs."""
    from PIL import ImageDraw
    ROWS = (("CASE UPPER", 0.86), ("DRAWER x2", 0.62),
            ("DECK", 0.44), ("PINION x2", 0.30),
            ("SG90 x2", 0.18), ("CASE LOWER", 0.05))
    fr = []
    for i in range(n):
        t = ease(min(i / (n * 0.55), 1.0))          # out, then hold
        img = render(cabinet(pull=(0, 0), sep=32.0*t),
                     eye=(200, -240, 175 + 40*t), target=(46, 34, 40 + 44*t),
                     W=620, H=560, fov=28, ss=2)
        im = Image.fromarray(img)
        dr = ImageDraw.Draw(im)
        for k, (label, y) in enumerate(ROWS):
            a = max(0.0, min(1.0, (t - 0.25 - k*0.06) / 0.35))
            if a <= 0.02:
                continue
            yy = int(560 * (1.0 - y))
            g = int(150 + 105*a)
            dr.line((16, yy, 40, yy), fill=(g, g, g), width=1)
            dr.text((46, yy - 5), label, fill=(g, g, g))
        fr.append(np.array(im))
    gif(fr, "exploded_labelled.gif", ms=90)


def exploded_gif(n=28):
    fr = []
    for i in range(n):
        t = ease(abs(1 - 2*i/(n-1)))          # out and back
        o = cabinet(pull=(0, 0), sep=32.0*t)
        fr.append(render(o, eye=(200, -240, 175 + 40*t),
                         target=(46, 34, 40 + 44*t),
                         W=560, H=520, fov=28, ss=2))
    gif(fr, "exploded.gif", ms=80)


# ── 3. the mechanism, driven by its own kinematics ────────────────────────
def blade_only():
    """Just what hangs below the drawer floor - that is the rack.

    Cut to z <= -0.15, not z <= 0: slicing exactly on the floor's underside
    keeps a zero-thickness lamina of the whole 38.8 x 59 footprint, which
    renders as a big orange slab and hides the entire mechanism."""
    b = trimesh.creation.box(extents=[90, 90, 11.15])
    b.apply_translation([20, 29.5, -11.20/2 - 0.125])
    return trimesh.boolean.intersection([DR, b], engine="manifold")


BLADE = blade_only()
MESH_X = NA.DR_X[0] + NA.FIN_X + NA.P["fin_t"]/2


def mechanism_gif(n=30):
    """Pinion and rack alone, from outside the case. The drawer body is left
    out because it sits directly over the mesh and hides it completely."""
    fr, cmd = [], NA.TRAVEL*153/180
    tx, ty, tz = (MESH_X + pin_x(0))/2, NA.WL + NA.PIN_Y, NA.SG_HORN + 3.0
    for i in range(n):
        t = ease(abs(1 - 2*i/(n-1)))
        pull = cmd * t
        o = [obj(moved(BLADE, NA.DR_X[0], -pull, NA.DECK+0.2), SIGNAL,
                 gloss=26, spec=0.50),
             obj(moved(spun(PN, math.degrees(pull/NA.R_P)), pin_x(0),
                       NA.WL+NA.PIN_Y, NA.SG_HORN), STEEL, **MAT_MECH)]
        fr.append(render(o, eye=(tx+24, ty-42, tz+26), target=(tx, ty, tz),
                         W=560, H=430, fov=26, ss=2, shadow=False))
    gif(fr, "mechanism.gif", ms=70)


def mechanism_still():
    pull = NA.TRAVEL*153/180*0.45
    tx, ty, tz = (MESH_X + pin_x(0))/2, NA.WL + NA.PIN_Y, NA.SG_HORN + 3.0
    o = [obj(moved(BLADE, NA.DR_X[0], -pull, NA.DECK+0.2), SIGNAL,
             gloss=26, spec=0.50),
         obj(moved(spun(PN, math.degrees(pull/NA.R_P)), pin_x(0),
                   NA.WL+NA.PIN_Y, NA.SG_HORN), STEEL, **MAT_MECH)]
    save(render(o, eye=(tx+26, ty-46, tz+30), target=(tx, ty, tz),
                W=1100, H=760, fov=26, ss=3, shadow=False), "mechanism.png")


# ── 4. a full open/close cycle ────────────────────────────────────────────
def cycle_gif(n=30):
    fr, cmd = [], NA.TRAVEL*153/180
    for i in range(n):
        t = ease(abs(1 - 2*i/(n-1)))
        fr.append(render(cabinet(pull=(cmd*t, 0)),
                         eye=(186, -214, 142), target=(44, 30, 30),
                         W=560, H=430, fov=28, ss=2))
    gif(fr, "cycle.gif", ms=70)


# ── 5. turntable ──────────────────────────────────────────────────────────
def turntable_gif(n=36):
    fr, R = [], 300.0
    for i in range(n):
        a = 2*math.pi*i/n
        fr.append(render(cabinet(pull=(NA.TRAVEL*153/180*0.55, 0)),
                         eye=(46 + R*math.cos(a), 34 + R*math.sin(a), 150),
                         target=(46, 34, 30), W=520, H=430, fov=24, ss=2))
    gif(fr, "turntable.gif", ms=65)


if __name__ == "__main__":
    which = sys.argv[1:] or ["hero", "exploded", "mech", "cycle", "turn"]
    print("\nrendering README assets\n")
    if "hero" in which: hero()
    if "exploded" in which: exploded_still(); exploded_gif()
    if "mech" in which: mechanism_still(); mechanism_gif()
    if "cycle" in which: cycle_gif()
    if "turn" in which: turntable_gif()
    print(f"\n  -> {OUT}")
