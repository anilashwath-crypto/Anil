#!/usr/bin/env python3
"""
shopkeeper SIMPLE — one drawer, two gears, built to print fast.

Written from scratch rather than patched into nano.py, which by now carries
six generations of decisions that argue with each other. Everything here is
built around ONE fixed constraint:

    THE GEARS ALREADY EXIST. They are m1.25 x 10T, pitch radius 6.25, mounted
    flat on vertical servo shafts. Nothing in this file may change them.

From that single given, everything else follows:
  - a flat gear's teeth face sideways, so the rack's teeth must be on a
    VERTICAL face. Teeth in a floor face downward at a gear that never looks
    that way, which is why that version could never have driven anything.
  - the rack therefore hangs BELOW the drawer as a toothed blade, 10 mm of
    tooth, meeting the gear edge-on.
  - one drawer, no partition: both gears drive the same blade pair, so there
    is nothing to keep in sync and twice the force.

Print policy: speed over elegance. Vented walls, a perforated floor, no
lightening geometry that costs more time than it saves. The drawer prints
floor-down with supports under the body only - its blade teeth are on
vertical faces, so no support ever touches a tooth flank.
"""
import os, math, sys
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from mf3 import write_3mf, verify

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.normpath(os.path.join(HERE, "..", "nano", "simple"))
os.makedirs(OUT, exist_ok=True)

# ── THE GIVEN: gears already on the servos ────────────────────────────────
MODULE, TEETH = 1.25, 10
R_P     = MODULE*TEETH/2                 # 6.25
ADD, DED = 0.8*MODULE, 1.25*MODULE       # stub addendum, as printed
PITCH   = math.pi*MODULE                 # 3.927
PRESS   = math.radians(14.5)
BACKLASH = 0.50
CDIST   = R_P + 0.15                     # +0.15 bias for servo pocket play
# MEASURED off nano/pinion.stl, the gear that is already on the servos:
# a 3.70 mm boss hangs BELOW the tooth band and swallows the output shaft, so
# the teeth do not start at the servo's top face - they start 3.70 above it.
# Missing that put the deck 7.5 mm too low and the gear band 5.8 mm clear of
# the blade entirely: the drawer would have sat there while the servos turned.
GEAR_T   = 6.0                           # tooth band, z 0.00 .. 6.00
GEAR_BOSS = 3.70                         # boss below the band, z -3.70 .. 0
TRAVEL  = math.pi*R_P                    # 19.63 full, 180 deg
CMD     = TRAVEL*153/180                 # 16.69 as the firmware commands it

# ── case ──────────────────────────────────────────────────────────────────
SG_H = 22.7                              # SG90 case height, base to top face
CW, CD, CH = 92.0, 74.0, 57.0
WALL, FLOOR = 2.0, 1.6
DECK_Z, DECK_T = 33.5, 2.5
DECK = DECK_Z + DECK_T                   # 28.5, drawer rides on this

# ── drawer: ONE, spanning the case ────────────────────────────────────────
SIDE_CLR = 0.8
DR_W  = CW - 2*WALL - 2*SIDE_CLR         # 86.4
DR_D  = 58.0
DR_H  = 17.0
DR_WALL, DR_FLOOR = 1.6, 1.6
DR_X  = WALL + SIDE_CLR

# ── the blades: 10 mm of tooth, hanging below the drawer ──────────────────
BLADE_T   = 3.0                          # blade thickness
TOOTH_H   = ADD + DED                    # 2.56 tooth depth, radial
BLADE_DROP = 10.0                        # <- 10 mm of tooth, as asked
BLADE_X   = (18.0, 64.0)                 # blade near face, case coords
# The blade has to reach the gear when the drawer is SHUT and still be inside
# the case when it is fully OPEN. With the gear 14 mm behind the mouth those
# two demands contradict each other and the blade drove 13.3 mm through the
# front wall at full pull. The gear has to sit back far enough that a whole
# stroke fits in front of it: RACK_Y0 > CMD, and the axis at least one tooth
# pitch inside the blade at both ends of the travel.
RACK_Y0, RACK_L = 17.0, 40.0

# gear axis sits CDIST out from the blade's pitch line
PIN_X = tuple(bx + BLADE_T + TOOTH_H - ADD + CDIST for bx in BLADE_X)
PIN_Y = 31.0
GEAR_Z0 = FLOOR + SG_H + GEAR_BOSS       # 28.0: where the teeth actually are
SERVO_TOP = FLOOR + SG_H                 # 24.3
SG_DIR  = (+1, -1)                       # body direction from each shaft

def T(m,x=0,y=0,z=0): m.apply_translation([x,y,z]); return m
def blk(x0,x1,y0,y1,z0,z1):
    x0,x1=sorted((x0,x1)); y0,y1=sorted((y0,y1)); z0,z1=sorted((z0,z1))
    return T(box(extents=[x1-x0,y1-y0,z1-z0]),(x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
def cylz(d,z0,z1,x,y,s=32): return T(cylinder(radius=d/2,height=z1-z0,sections=s),x,y,(z0+z1)/2)
def diff(a,b): return trimesh.boolean.difference([a,b],engine="manifold")
def union(p): return trimesh.boolean.union(p,engine="manifold")


def blade(length, drop):
    """Rack blade: teeth on the +X vertical face, pointing sideways at a gear
    that lies flat. Prongs run the full drop, so there is 10 mm of tooth to
    engage however the gear ends up sitting."""
    hp  = (PITCH/2 - BACKLASH)/2
    tip = hp - ADD*math.tan(PRESS)
    rt  = hp + DED*math.tan(PRESS)
    parts = [blk(0, BLADE_T, 0, length, 0, drop)]
    for i in range(int(length/PITCH)):
        yc = (i+0.5)*PITCH
        parts.append(extrude_polygon(Polygon(
            [(BLADE_T, yc-rt), (BLADE_T+TOOTH_H, yc-tip),
             (BLADE_T+TOOTH_H, yc+tip), (BLADE_T, yc+rt)]), drop))
    return union(parts)


def vent_wall(m, x0, x1, y, z0, z1, n=5, along="x"):
    """Louvres. Vertical slots print themselves and only the narrow tops
    bridge, so they cost nothing in time and give most of the wall back."""
    span = (x1-x0)/n
    for i in range(n):
        a = x0 + i*span + span*0.22
        b = x0 + (i+1)*span - span*0.22
        if b - a < 1.6: continue
        m = diff(m, blk(a, b, y-1, y+1, z0, z1) if along == "x"
                    else blk(y-1, y+1, a, b, z0, z1))
    return m


def drawer():
    """One drawer, both blades, vented. Prints floor-down; supports go under
    the body and never touch a tooth, because every tooth flank is vertical."""
    W, D, H = DR_W, DR_D, DR_H
    m = diff(blk(0, W, 0, D, 0, H),
             blk(DR_WALL, W-DR_WALL, DR_WALL, D-DR_WALL, DR_FLOOR, H+1))
    # perforated floor - the single biggest saving on a part this size
    for gx in np.arange(6.0, W-6.0, 9.0):
        for gy in np.arange(7.0, D-7.0, 9.0):
            if any(abs(gx-(bx-DR_X)) < 9.0 for bx in BLADE_X):
                continue                       # keep metal under the blades
            m = diff(m, cylz(6.0, -1, DR_FLOOR+1, gx, gy, s=6))
    # vented side and rear walls
    m = vent_wall(m, 8.0, W-8.0, D-DR_WALL/2, 4.0, H-2.5, n=7)
    for wy in (DR_WALL/2, ):
        pass
    # finger scoop, front
    m = diff(m, cylz(16.0, H-3.0, H+1, W/2, 0.0, s=32))
    # the two blades
    for bx in BLADE_X:
        b = blade(RACK_L, BLADE_DROP)
        b.apply_translation([bx - DR_X, RACK_Y0, -BLADE_DROP])
        m = union([m, b])
    return m


# ── slotted variant: the pre-one-piece style, widened ─────────────────────
# Slot sizes are MEASURED off nano/prev/drawer_slotted.stl (recovered from
# 5d19926^), so a rack cut to the old pattern still fits: a 6.06 channel for
# the rack foot and two 3.45 square peg slots 6.72 out from the channel centre.
# That part was 39.8 wide only because a mullion split the bay in two. With the
# partition gone there is one drawer and one bin, and the same slot group is
# repeated once per gear instead of once per drawer.
SLOT_CH_W, SLOT_PEG, SLOT_PEG_DX = 6.06, 3.45, 6.72
# Peg inset from each END OF THE RACK. Deriving the slot positions from the
# drawer's depth instead put the rear slot at y 48.5 while the rack's rear peg
# landed at 37.6 - the rack is 40 long in a 58-deep drawer, so the two only
# agree if both are measured off the same part. They are measured off the rack.
SLOT_PEG_INSET = 5.3
PEG_Y = (RACK_Y0 + SLOT_PEG_INSET, RACK_Y0 + RACK_L - SLOT_PEG_INSET)

def _slot_sets():
    """(channel centre x, peg centre x) per gear, in drawer coords."""
    out = []
    for px in PIN_X:
        pitch = px - CDIST - DR_X            # where the rack's pitch line must land
        # Work OUTWARD from the pitch line to the channel: the blade's tip is
        # one addendum past the pitch line, and the channel centre is half a
        # blade plus a tooth depth back from that tip. Writing it as
        # pitch - ADD - BLADE_T/2 lands the rack 0.56 mm off the gear - it
        # subtracts the addendum that should be added and drops TOOTH_H
        # entirely, and every printed rack would have meshed on one flank.
        ch = pitch + ADD - BLADE_T/2 - TOOTH_H
        out.append((ch, ch + SLOT_PEG_DX))
    return out


def drawer_slotted():
    """One drawer, no partition, rack bolted in rather than printed on."""
    W, D, H = DR_W, DR_D, DR_H
    m = diff(blk(0, W, 0, D, 0, H),
             blk(DR_WALL, W-DR_WALL, DR_WALL, D-DR_WALL, DR_FLOOR, H+1))
    for ch, pg in _slot_sets():
        m = diff(m, blk(ch-SLOT_CH_W/2, ch+SLOT_CH_W/2,
                        RACK_Y0-0.35, RACK_Y0+RACK_L+0.35, -1, DR_FLOOR+1))
        for y in PEG_Y:
            m = diff(m, blk(pg-SLOT_PEG/2, pg+SLOT_PEG/2,
                            y-SLOT_PEG/2, y+SLOT_PEG/2, -1, DR_FLOOR+1))
            # The peg is joined to the blade by a web, and cutting only the
            # channel and the peg leaves the floor between them intact - the
            # rack fouled by 30.63 mm3 and could not be seated. Relieve the
            # web too.
            m = diff(m, blk(ch, pg, y-1.9, y+1.9, -1, DR_FLOOR+1))
    for gx in np.arange(6.0, W-6.0, 9.0):
        for gy in np.arange(7.0, D-7.0, 9.0):
            if any(abs(gx-c) < 10.0 for c, _ in _slot_sets()): continue
            m = diff(m, cylz(6.0, -1, DR_FLOOR+1, gx, gy, s=6))
    m = vent_wall(m, 8.0, W-8.0, D-DR_WALL/2, 4.0, H-2.5, n=7)
    m = diff(m, cylz(16.0, H-3.0, H+1, W/2, 0.0, s=32))
    return m


def rack():
    """The separate rack the slotted drawer takes: foot in the channel, two
    pegs, and 10 mm of tooth below."""
    ch, pg = _slot_sets()[0]
    b = blade(RACK_L, BLADE_DROP)
    b.apply_translation([-BLADE_T/2, 0, 0])          # body centred on x=0
    # 0.70 off the slot, not 0.36: an FDM peg grows ~0.05/side and the slot
    # shrinks ~0.05/side, so 0.36 nominal arrives as 0.08/side - a press fit in
    # a material that takes press fits by snapping.
    foot = blk(-(SLOT_CH_W-0.70)/2, (SLOT_CH_W-0.70)/2, 0, RACK_L,
               BLADE_DROP, BLADE_DROP + DR_FLOOR - 0.2)
    parts = [b, foot]
    for y in (SLOT_PEG_INSET, RACK_L - SLOT_PEG_INSET):
        parts.append(blk(SLOT_PEG_DX-(SLOT_PEG-0.70)/2, SLOT_PEG_DX+(SLOT_PEG-0.70)/2,
                         y-(SLOT_PEG-0.70)/2, y+(SLOT_PEG-0.70)/2,
                         BLADE_DROP, BLADE_DROP + DR_FLOOR - 0.2))
        parts.append(blk(0, SLOT_PEG_DX, y-1.5, y+1.5,
                         BLADE_DROP, BLADE_DROP + DR_FLOOR - 0.2))
    return union(parts)


def case_lower():
    """Open-top tray. Servo wells at the fixed gear positions, everything else
    cut away."""
    H = DECK
    m = diff(blk(0, CW, 0, CD, 0, H), blk(WALL, CW-WALL, WALL, CD-WALL, FLOOR, H+1))
    # deck ledge, 45 deg so it prints itself
    zt = H - DECK_T
    m = union([m, blk(WALL, WALL+1.5, WALL, CD-WALL, zt-1.5, zt)])
    m = union([m, blk(CW-WALL-1.5, CW-WALL, WALL, CD-WALL, zt-1.5, zt)])
    m = union([m, blk(WALL, CW-WALL, CD-WALL-1.5, CD-WALL, zt-1.5, zt)])
    # Servo wells: body 22.8 x 12.2 with the shaft 5.9 in from one end, so the
    # body centre sits 5.5 mm off the axis. SG_DIR mirrors the right-hand one -
    # both pointing the same way ran the second well 6.2 mm out through the
    # case wall, and case_lower measured 98.2 in a 92 mm case.
    for px, sgn in zip(PIN_X, SG_DIR):
        bcx = px + sgn*(22.8/2 - 5.9)
        m = union([m, blk(bcx-18.45, bcx+18.45, PIN_Y-8.1,
                          PIN_Y+8.1, FLOOR, 20.5)])
        # Body pocket stops at the ear line so the mounting flange LANDS on the
        # rim - that shelf is what sets the servo's height, and its height is
        # what puts the gear inside the blade. Above it, a wider relief for the
        # flange itself: cutting only the body pocket buried 4.35 mm of each
        # tab in the wall, and the servo simply could not have gone in.
        m = diff(m, blk(bcx-11.75, bcx+11.75, PIN_Y-6.45, PIN_Y+6.45, FLOOR-0.1, FLOOR+15.9))
        m = diff(m, blk(bcx-16.45, bcx+16.45, PIN_Y-6.6, PIN_Y+6.6, FLOOR+15.9, 21.0))
    # vents everywhere else
    m = vent_wall(m, 12.0, CW-12.0, CD-WALL/2, 5.0, H-6.0, n=8)
    m = vent_wall(m, 30.0, CD-8.0, WALL/2, 5.0, H-6.0, n=4, along="y")
    m = vent_wall(m, 30.0, CD-8.0, CW-WALL/2, 5.0, H-6.0, n=4, along="y")
    # floor lightening, clear of the servo wells
    for gx in np.arange(10.0, CW-10.0, 11.0):
        for gy in np.arange(34.0, CD-10.0, 10.0):
            m = diff(m, cylz(8.0, -1, FLOOR+1, gx, gy, s=6))
    return m


def deck():
    """Flat plate the drawer rides on. Slotted for both blades, bored for both
    gears, perforated everywhere else."""
    m = blk(WALL+0.3, CW-WALL-0.3, WALL+0.3, CD-WALL-0.3, 0, DECK_T)
    for bx, px in zip(BLADE_X, PIN_X):
        m = diff(m, blk(bx-1.0, bx+BLADE_T+TOOTH_H+1.0, -1, CD-WALL-9.0,
                        -1, DECK_T+1))
        m = diff(m, cylz(2*(R_P+ADD)+2.0, -1, DECK_T+1, px, PIN_Y))
    for gx in np.arange(28.0, CW-10.0, 10.0):
        for gy in np.arange(34.0, CD-10.0, 9.0):
            m = diff(m, cylz(6.5, -1, DECK_T+1, gx, gy, s=6))
    m.apply_translation([-(WALL+0.3), -(WALL+0.3), 0])
    return m


def case_upper():
    """Lid with ONE mouth - no partition. Prints top-face-down."""
    H = CH - DECK
    m = diff(blk(0, CW, 0, CD, 0, H), blk(WALL, CW-WALL, WALL, CD-WALL, -1, H-WALL))
    mouth = DR_H + 1.2
    m = diff(m, blk(DR_X-0.6, DR_X+DR_W+0.6, -1, WALL+1, -1, mouth))
    # mesh the top face
    for gx in np.arange(12.0, CW-10.0, 10.0):
        for gy in np.arange(12.0, CD-10.0, 9.0):
            m = diff(m, cylz(7.0, H-WALL-1, H+1, gx, gy, s=6))
    m = vent_wall(m, 12.0, CW-12.0, CD-WALL/2, 3.0, H-WALL-2.0, n=8)
    return m


PARTS = {}
def rep(n, m):
    e = m.extents
    nb = len(m.split(only_watertight=False))
    print(f"  {n:11s} {e[0]:6.1f} x {e[1]:6.1f} x {e[2]:5.1f}   "
          f"{m.volume/1000*1.27:5.1f} g   wt={m.is_watertight} bodies={nb}")
    m.export(os.path.join(OUT, n + ".stl")); PARTS[n] = m; return m


# ── plating ───────────────────────────────────────────────────────────────
def plate(path, items):
    """Lay parts out on the bed, each already rotated to its print pose."""
    placed, x = [], 12.0
    for n, m, rot in items:
        m = m.copy()
        if rot:
            m.apply_transform(trimesh.transformations.rotation_matrix(
                math.radians(rot), [1, 0, 0]))
        m.apply_translation(-m.bounds[0])
        placed.append((n, m, x + m.extents[0]/2, 12.0 + m.extents[1]/2))
        x += m.extents[0] + 6.0
    write_3mf(path, placed)
    verify(path)
    return path


def make_plates():
    # case_upper prints top-face-DOWN: the lid becomes the first layer and the
    # mouth's overhang is then a bridge instead of a cliff.
    p = plate(os.path.join(OUT, "plate_simple.3mf"), [
        ("case_lower", PARTS["case_lower"], 0),
        ("deck",       PARTS["deck"],       0),
        ("case_upper", PARTS["case_upper"], 180),
        ("drawer",     PARTS["drawer"],     0),
    ])
    print(f"\n  plate -> {p}")
    return p


if __name__ == "__main__":
    print("\nshopkeeper SIMPLE\n")
    print(f"  case      {CW:.0f} x {CD:.0f} x {CH:.0f} mm")
    print(f"  drawer    ONE, {DR_W:.1f} x {DR_D:.0f} x {DR_H:.0f}  (no partition)")
    print(f"  gears     m{MODULE} x {TEETH}T, R_p {R_P:.2f}  — FIXED, already built")
    print(f"  blades    2, {BLADE_DROP:.0f} mm of tooth, at x {BLADE_X}")
    print(f"  travel    {TRAVEL:.2f} full / {CMD:.2f} commanded\n")
    rep("case_lower", case_lower())
    rep("deck", deck())
    rep("case_upper", case_upper())
    rep("drawer", drawer())
    rep("drawer_slotted", drawer_slotted())
    rep("rack", rack())

    print("\n  CHECKS")
    ok = True
    def chk(l, c, d):
        global ok
        print(f"    [{'PASS' if c else 'FAIL'}] {l:38s} {d}")
        ok = ok and c
    for n, m in PARTS.items():
        chk(f"{n} is one watertight body",
            m.is_watertight and len(m.split(only_watertight=False)) == 1,
            f"{len(m.split(only_watertight=False))} bodies")
    d = PARTS["drawer"]
    chk("blade drop is 10 mm of tooth", abs(-d.bounds[0][2] - BLADE_DROP) < 0.01,
        f"{-d.bounds[0][2]:.2f} mm below the floor")
    for i, (bx, px) in enumerate(zip(BLADE_X, PIN_X)):
        pitch_x = bx + BLADE_T + TOOTH_H - ADD
        chk(f"gear {i+1} centre distance", abs((px - pitch_x) - CDIST) < 0.01,
            f"{px-pitch_x:.3f} mm, needs {CDIST:.3f}")
    chk("gear band sits inside the teeth",
        GEAR_Z0 >= DECK - BLADE_DROP and GEAR_Z0 + GEAR_T <= DECK,
        f"gear {GEAR_Z0:.1f}-{GEAR_Z0+GEAR_T:.1f} in blade {DECK-BLADE_DROP:.1f}-{DECK:.1f}")
    chk("blade clears the servo case", DECK - BLADE_DROP >= SERVO_TOP + 0.8,
        f"blade bottom {DECK-BLADE_DROP:.1f}, servo top {SERVO_TOP:.1f}")
    chk("headroom over the drawer", CH - WALL - (DECK + DR_H) >= 0.8,
        f"{CH - WALL - (DECK + DR_H):.1f} mm under the lid")
    chk("drawer fits its mouth", DR_W + 2*SIDE_CLR <= CW - 2*WALL + 0.01,
        f"{DR_W:.1f} + clearance in {CW-2*WALL:.1f}")
    for n, m in PARTS.items():
        chk(f"{n} stays inside the case footprint",
            m.extents[0] <= CW + 0.01 and m.extents[1] <= CD + 0.01,
            f"{m.extents[0]:.1f} x {m.extents[1]:.1f} in {CW:.0f} x {CD:.0f}")
    _b = [(px + sg*(22.8/2-5.9) - 11.75, px + sg*(22.8/2-5.9) + 11.75)
          for px, sg in zip(PIN_X, SG_DIR)]
    chk("servo bodies do not clash", _b[1][0] > _b[0][1],
        f"A {_b[0][0]:.1f}..{_b[0][1]:.1f}  B {_b[1][0]:.1f}..{_b[1][1]:.1f}")
    tot = sum(m.volume for m in PARTS.values())/1000*1.27
    print(f"\n  {tot:.0f} g solid  (~{tot*0.85:.0f} g sliced)")
    if not ok:
        sys.exit(1)
    print("  ALL CHECKS PASSED")
    make_plates()

