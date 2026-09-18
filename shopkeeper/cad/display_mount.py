#!/usr/bin/env python3
"""
shopkeeper NANO — DISPLAY MOUNT v0.3

A 1.3" SH1106 and two status lamps, on a pod that sits on case_upper.

    THE LID DOES NOT CHANGE. Not one cut.
    NO SUPPORTS. Both parts print flat on their own faces.
    NO LATCH. Two spigots in two holes, the way the lid itself is located.
    FULL WIDTH. The pod is 92 mm, flush with the case sides.

The pod registers on three features the top face already has, verified against
nano/case_upper.stl rather than trusted from the source:

    dia 5.00 hole   (20.00, 45.88)  ]  registration
    26 x 10 window  (46.00, 45.88)  ]  wire pass
    dia 5.00 hole   (72.00, 45.88)  ]

WHY THE LAMPS ARE ON THE POD AND NOT IN THE LID
The lid's two dia 5 holes were drawn as provision and never checked against
the bay. A 5 mm LED body is 8.6 mm long; pushed up from below with its dome
flush it hangs from z 64 down to z 55.9 - through the drawer top at z 60 and
through the anti-tip rib whose crown is at z 62. A 3 mm LED still fouls the
rib. Nothing may protrude past the ceiling at x 20 or x 72 at all, so the
spigots are exactly PLATE_T tall and stop flush.

HOW THE SCREEN MOUNTS
Through its own four dia 3.00 corner holes, on four printed pegs, behind ONE
opening cut straight through the face wall. No PCB pocket, no glass relief, no
bezel stack, no retainer, no screws: the board's own front face seats on the
wall's inner surface, which overlaps it by 4.90 mm top and bottom, and the
pegs locate it. That deleted most of v0.2.

WHY TWO PARTS
    base   prints SPIGOT-SIDE UP, flat on the bed. Every downward feature
           becomes an upward one.
    body   prints FACE-DOWN. The bezel forms against the bed - the same trick
           case_upper uses for the logo - the mating face becomes an UP-facing
           slope, and the pegs and lamp bores point straight up off it.

    A one-piece pod has no such orientation: face-down puts the lid-mating
    surface at TILT to the bed as a stepped slope, and base-down stands the
    whole plate on two 2 mm spigots.

WHAT IS STILL BROKEN, AND IT IS NOT IN THIS FILE
There is no route from the pod to the ESP32. `deck()` in nano.py is a solid
plate; ray-casting 1800 points down through the wire slot, NOT ONE reaches
past it in the only drawer-free band (x 42-49). The 210 rays that do get
through the deck elsewhere all land in drawer 2's drive-fin slot, where the
rack sweeps 31.4 mm. Until deck() gets a cable hole at x 43-49, this display
cannot be connected to anything. The check at the bottom of this file fails on
purpose and should keep failing until that is fixed.
"""
import os, math
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from mf3 import write_3mf, verify

HERE = os.path.dirname(os.path.abspath(__file__))
NANO = os.path.normpath(os.path.join(HERE, "..", "nano"))
OUT  = os.path.join(NANO, "mount")
POSE = os.path.join(OUT, "printpose")
for d in (OUT, POSE):
    os.makedirs(d, exist_ok=True)

# ── THE LID, AS BUILT ──────────────────────────────────────────────────────
# case_upper local coords: z 0 is the deck-mating rim, z 24 is the top face.
# Pod coords share x and y with the case and put z 0 AT THE TOP FACE, so a
# negative z is inside the lid.
CASE_W, CASE_D = 92.0, 74.0
LID_H     = 24.0
PLATE_T   = 2.0                   # top plate -> ceiling at pod z -2.0
HOLE_D    = 5.00
HOLE_X    = (20.00, 72.00)
DATUM_Y   = 45.88                 # all three features sit on this line
WIN       = (33.00, 59.00, 40.88, 50.88)     # x0, x1, y0, y1
# Both of these are 0.2 mm lower than nano.py's DR_TOP implies, because the
# drawer is ASSEMBLED at DECK+0.2, not at DECK. Verified off drawer.stl.
DRAWER_Z  = -5.80                 # drawer top         (assembly z 60.20)
RIB_Z     = -3.80                 # anti-tip rib crown (assembly z 62.20)
CEIL_Z    = -PLATE_T              # bay ceiling        (assembly z 64.00)
NO_DRAWER = (42.00, 49.00)        # the only x band no drawer ever crosses
# deck.stl is exported translated to its own origin; put it back in case coords
WL_DECK_X, WL_DECK_Y = 2.3, 2.3
LOGO_Y1   = 14.5                  # rear edge of the debossed mark
VENT_Y0   = 72.0                  # rear vent windows start here

# ── THE MODULE: 1.3" SH1106 ────────────────────────────────────────────────
# From the MANUFACTURER'S DIMENSIONED DRAWING (Zhengzhou Zhongjingyuan), which
# LCDWIKI's drawing and Pololu's - the latter drawn independently off a
# physical unit - agree with to the hundredth of a millimetre. Every chain in
# it closes exactly, which is why it is believed over a caliper reading:
#     inset 2.50 all round:  35.40 - 5.00 = 30.40,  33.50 - 5.00 = 28.50
#     active area vertical:   7.35 + 14.70 + 11.45 = 33.50
#     glass:                  5.25 + 23.00 +  5.25 = 33.50
#
# TWO CALIPER READINGS TURNED OUT WRONG, and both would have cost the print:
#   - the holes are dia 3.00 (M3), NOT 4.0. The 4.0-4.5 reading is the COPPER
#     ANNULUS around the hole. A 3.9 peg would not have entered at all.
#   - the board is 35.40 wide, not 35.0. (The 33.50 reading was exact.)
PCB_W, PCB_H, PCB_T      = 35.40, 33.50, 1.20
MOD_HOLE_D               = 3.00   # M3 clearance, on a dia 4.50 copper ring
MOD_PITCH_X, MOD_PITCH_Y = 30.40, 28.50
GLASS_W, GLASS_H, GLASS_T = 34.50, 23.00, 1.50   # glass stands 1.4-1.5 proud
ACT_W, ACT_H              = 29.42, 14.70
# THE ACTIVE AREA IS NOT CENTRED ON THE BOARD. It sits 7.35 from the header
# edge and 11.45 from the other, i.e. 2.05 mm toward the header. The glass IS
# centred - the offset is inside the panel, where the driver IC and the FPC
# bond eat the bottom 6.20 mm. A symmetric window clips the picture, and it
# clips it at the top, which is where the status line goes.
ACT_OFF                   = 2.05  # toward the header edge = UP the slope
# The FPC wraps around the edge OPPOSITE the header and folds behind the
# board: a 14 mm band at the centre of that edge, reaching 4 mm in from the
# edge and standing ~1.5 mm off the back. FPC_D was declared as a hard
# clearance and then used by nothing; it is now a face of module_solid().
FPC_W, FPC_D, FPC_T       = 14.0, 4.0, 1.5
# The header: 4 pins on 2.54, centred, row 2.00 mm in from the header edge.
# A Dupont housing on those pins reaches 11.30 mm from the GLASS FACE, which
# is the number that decides how deep the pod has to be behind the screen.
HDR_W, HDR_T              = 12.5, 3.2
HDR_TIP_FROM_GLASS        = 11.30
# A STRAIGHT DUPONT DOES NOT FIT AND CANNOT BE MADE TO. Measured behind an
# up-slope header there is 4.80 mm to the shell, 7.40 mm a millimetre in. A
# 4-way Dupont is ~14.7 mm; even a bare 0.1" male header is ~8.5 mm. Making the
# pod swallow it needs either a deeper pod or a hole out of the back, and the
# hole is what it had - the connector protruded 0.52 mm through the notch.
# So the module is wired one of the two ways that measurably DO fit:
#     wires soldered to the pads          - clear to ~4 mm behind the board
#     right-angle header, exiting down-slope - clear for 20+ mm
# CONN_BACK models the first, which is the tighter of the two.
CONN_BACK                 = 5.0   # soldered leads plus a bend radius
# One definition serves both the cut and the check - writing the number twice
# is how the two drift apart.
GLASS_CLR_U, GLASS_CLR_V  = 0.6, 0.6

# ── POD ────────────────────────────────────────────────────────────────────
TILT      = math.radians(30.0)
WALL      = 2.5
BEZEL     = 1.4                   # face wall left over the glass
BASE_T    = 3.0                   # 2.4 left an M2 head standing 0.6 proud of
                                  # the lid-mating face, so the pod rocked on
                                  # two screw heads
CHAM      = 2.5                   # echoes case_upper's corner chamfer

# ── THE SHOP RULE, WRITTEN DOWN ONCE ───────────────────────────────────────
# A modelled hole comes out about this much small; a modelled peg about this
# much large. gauge_spigot's docstring established this and then nothing
# applied it to the base<->body pins, which came out at -0.10 INTERFERENCE on
# two pins 68 mm apart. Every peg-in-hole on this part now derives from here.
HOLE_SHRINK, PEG_GROW = 0.25, 0.15
def slip(peg_d, want=0.15):
    """Modelled hole diameter giving `want` of real clearance on `peg_d`."""
    return peg_d + PEG_GROW + HOLE_SHRINK + want
def real_clearance(peg_d, hole_d):
    return (hole_d - HOLE_SHRINK) - (peg_d + PEG_GROW)
def bore(part_d, want=0.15):
    """Modelled bore for a BOUGHT part - no PEG_GROW, the part isn't printed."""
    return part_d + HOLE_SHRINK + want

SCREW_HEAD_D, SCREW_HEAD_H = 4.0, 1.6      # M2 pan head, DIN 7985
SCREW_RECESS_D, SCREW_RECESS_H = 4.4, 1.8

# ── ONE screen opening ─────────────────────────────────────────────────────
# Asked for 36 wide x 30 tall. 36 is fine; 30 IS NOT POSSIBLE with peg
# mounting, and the arithmetic is short: the corner holes are on a 28.50 pitch,
# so the peg's inner edge sits at v 12.85. A 30 mm opening reaches v 15.00 and
# swallows all four peg positions - they would have no face left to root in.
# The largest opening that keeps 1.00 mm of face at each peg is 23.70, and that
# turns out to be the right number anyway: the glass is 23.00, so 23.70 shows
# ALL of it with 0.35 a side, and still leaves 4.90 mm of board overlapping the
# face top and bottom as the shoulder the module seats against.
# One opening, no bezel stack: the module's own face IS the datum.
# 35.0, not the 36.0 asked for: at 36.0 the opening is WIDER THAN THE BOARD
# (35.40), so instead of seating all round it leaves a 0.30 x 23.7 mm slot each
# side, straight into the interior. 35.0 still clears the 34.50 glass by 0.25 a
# side and closes the slot. One millimetre, and the aperture stops showing the
# wiring.
SCREEN_OPEN_W, SCREEN_OPEN_H = 35.0, 23.7
MOD_FRONT = WALL                  # the module's front face sits at the wall's
                                  # inner surface, so the glass - 1.5 proud -
                                  # ends up recessed 1.0 below the outer face

# Depth from the outer face to the back of the PCB. This is the number that
# makes a face-parallel feature lean: a box at depth w lands at
#     y = FC_Y + v*cos(TILT) - w*sin(TILT)
# so the module's REARMOST corner is its deep one and its FOREMOST is its
# shallow one. Balancing on the deep corner alone - the obvious mistake, and
# the one I made in v0.2 - left the front margin at 0.25 mm.
MOD_BACK  = MOD_FRONT + PCB_T                # 3.7
MOD_ENV_H = PCB_H + 1.0                      # PCB plus a little air
MOD_MARGIN = 2.0
MOD_V     = -(MOD_BACK + MOD_FRONT) * math.tan(TILT) / 2
BODY_D    = 2*(MOD_MARGIN + WALL + MOD_ENV_H*math.cos(TILT)/2
               - MOD_V*math.cos(TILT) - MOD_FRONT*math.sin(TILT))

# Where the connector actually reaches. The glass face sits at w = GLASS_T
# - MOD_FRONT; the pin tips are HDR_TIP_FROM_GLASS beyond that, and the wires
# need somewhere to turn after them.
HDR_V     = MOD_V + PCB_H/2 - 2.00
HDR_L     = CONN_BACK
HDR_END   = MOD_BACK + HDR_L
# What a straight Dupont WOULD need, kept so the check can report the gap
HDR_STRAIGHT = MOD_FRONT - GLASS_T + HDR_TIP_FROM_GLASS - MOD_BACK

BASE_X    = (0.0, CASE_W)         # FULL WIDTH: flush with the case sides
BODY_X    = (2.0, CASE_W - 2.0)   # 2 mm reveal, so a 0.2 mm print error on
                                  # either part does not read as a mismatch
BODY_Y    = (26.5, 26.5 + BODY_D)
BASE_Y    = (BODY_Y[0] - 1.5, BODY_Y[1] + 1.5)

BODY_FR   = 3.0                   # front lip height above the baseplate
BODY_H    = BODY_FR + BODY_D * math.tan(TILT)
SLOPE_L   = BODY_D / math.cos(TILT)

SPIG_D    = 4.55                  # see the note in gauge_spigot
SPIG_CH   = 0.4
WIRE      = (34.0, 58.0, 41.9, 49.9)   # wire pass, inside the window all round

# ── FACE LAYOUT ────────────────────────────────────────────────────────────
# Three lamps in a column on the left, screen offset right to balance it. A
# row of lamps under the screen would need another 12 mm of slope, which is
# 7 mm of machine height, for no gain.
# Back on the case centreline. With three lamps the screen had to shift right
# to make room for a column; with two it does not, and the layout goes
# symmetric: a lamp each side, each one directly above its own spigot.
SCREEN_CX = CASE_W / 2
PEG_D     = 2.80                  # into a dia 3.00 hole: prints ~2.95
PEG_PROUD = 1.6                   # stands this far past the PCB, so you can
                                  # see at a glance that it is seated
PEG_LEAD  = 0.4                   # stepped pilot on the tip
# THE HEADER EDGE FACES UP THE SLOPE. Not arbitrary: the 4-pin header points
# straight back into the pod and a Dupont housing needs ~11.3 mm from the glass
# face. At the module's rear edge there is 19.7 mm to the rear wall; at the
# front edge there is 8.0. Mounted the other way round the connector does not
# fit, and ACT_OFF would point the wrong way and clip the picture.
HEADER_UPSLOPE = True
# TWO lamps, one each side, each sitting directly above a registration spigot
# at x 20 and x 72 - the positions the lid's own holes already establish. This
# replaces a left-hand column of three, which forced the screen off-centre and
# put a bore where the joint boss lived.
LAMP_POS  = ((HOLE_X[0], 0.0), (HOLE_X[1], 0.0))   # (u, v) on the face
# A PLAIN THROUGH-BORE. The counterbore and its 45 deg lead-in are gone, and
# both were wrong:
#   - the bore was sized NOMINAL against this file's own shrink rule. A dia 6.0
#     counterbore prints ~5.75 against a dia 5.8 flange, so the flange could
#     not enter at all; a dia 5.2 barrel prints ~4.95 against a 4.9-5.1 body.
#   - a cone is not a seat. The flange wedges wherever its own diameter meets
#     the taper, so three LEDs off three reels stand at three heights.
# Now: one bore, and the flange seats flat on the wall's inner face - a real
# datum. The LED stands ~6 mm proud, which it did anyway, and which is what an
# indicator lamp on a machine panel looks like.
LAMP_D    = bore(5.0, 0.30)       # dia 5 LED body, press fit after shrink
# A BORE NORMAL TO A TILTED FACE TRAVELS SIDEWAYS. At 30 deg it gains 0.5 mm of
# y for every 1 mm of depth, so the 30 mm-deep barrel I drew first came out
# through the REAR WALL at y 66.98, z 3.62 - a round bore through a flat wall
# at an angle, i.e. the ellipse that showed up in the render. The lower two
# bored out through the bottom. A lamp only needs to get through the shell.
LAMP_DEPTH = WALL + 0.5           # the bore only has to get through the shell

# Cable cutout in the rear wall, behind the screen. The module's 4-pin header
# points straight back into the pod and a Dupont housing is ~14 mm long; this
# is where it goes, and where the harness leaves.
# 15.0, not 10.0. At 10.0 the connector's up-slope flank cleared the notch roof
# by -1.96 mm - i.e. it fouled the wall, and the module could not be plugged in
# once the body was printed. Caught by boolean, not by arithmetic.
CABLE_W, CABLE_H = 22.0, 12.0

# Pins and bosses have to GROW OUT OF A WALL. Standing them in the middle of a
# hollow body left them floating - separate solids in one STL, which the
# watertight check caught and a slicer would not have.
JOINT_PINS   = ((12.0, BODY_Y[0] + 8.0), (80.0, BODY_Y[0] + 8.0))
JOINT_SCREWS = ((12.0, BODY_Y[1] - 3.5), (80.0, BODY_Y[1] - 3.5))
JOINT_D      = 3.0
JOINT_HOLE   = slip(JOINT_D)      # was JOINT_D + 0.3, which printed as an
                                  # INTERFERENCE fit on two pins 68 mm apart
# NOTHING ON THIS PART MAY TAPER TO NOTHING. Two extrusions at 0.4 is the
# floor; below it the slicer emits nothing and the edge comes out ragged.
PAD_MIN      = 0.8


def T(m, x=0, y=0, z=0): m.apply_translation([x, y, z]); return m
def blk(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    assert x1 > x0 and y1 > y0 and z1 > z0, f"degenerate {x0,x1,y0,y1,z0,z1}"
    return T(box(extents=[x1-x0, y1-y0, z1-z0]),
             (x0+x1)/2, (y0+y1)/2, (z0+z1)/2)
def cylz(d, z0, z1, x, y, s=48):
    return T(cylinder(radius=d/2, height=z1-z0, sections=s), x, y, (z0+z1)/2)
def frustum(d0, d1, h, s=48):
    """Truncated cone, d0 at z 0 -> d1 at z h. Built by hand: trimesh's revolve
    does not close this into a volume and manifold then refuses the boolean."""
    ang = np.linspace(0, 2*np.pi, s, endpoint=False)
    bot = np.column_stack([np.cos(ang)*d0/2, np.sin(ang)*d0/2, np.zeros(s)])
    top = np.column_stack([np.cos(ang)*d1/2, np.sin(ang)*d1/2, np.full(s, h)])
    V = np.vstack([bot, top, [[0, 0, 0.0]], [[0, 0, h]]])
    cb, ct, F = 2*s, 2*s + 1, []
    for i in range(s):
        j = (i + 1) % s
        F += [[i, j, s+j], [i, s+j, s+i], [cb, j, i], [ct, s+i, s+j]]
    m = trimesh.Trimesh(vertices=V, faces=np.array(F), process=True)
    trimesh.repair.fix_normals(m)
    return m

def diff(a, b): return trimesh.boolean.difference([a, b], engine="manifold")
def union(p): return trimesh.boolean.union(p, engine="manifold")
def inter(p): return trimesh.boolean.intersection(p, engine="manifold")

def prism_x(pts_yz, x0, x1):
    """Profile in (y, z), extruded along x. Lifted verbatim from nano.py - the
    rotation order is not obvious, and getting it wrong builds the part 121 mm
    from where it belongs."""
    m = extrude_polygon(Polygon(pts_yz), x1 - x0)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0, 0, 1]))
    m.apply_translation([x0, 0, 0]); return m

def chamfer_corners(m, x0, x1, y0, y1, c=CHAM):
    s = c * math.sqrt(2); cuts = []
    for (x, y) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        b = box(extents=[s, s, 300])
        b.apply_transform(trimesh.transformations.rotation_matrix(math.pi/4, [0, 0, 1]))
        cuts.append(T(b, x, y, 0))
    return diff(m, union(cuts))


# ── the sloped face gets its own frame ─────────────────────────────────────
FC_Y = (BODY_Y[0] + BODY_Y[1]) / 2
FC_Z = BODY_FR + (FC_Y - BODY_Y[0]) * math.tan(TILT)

def face_xf():
    """Face-local -> part. u across, v up the slope, w out of the face."""
    R = trimesh.transformations.rotation_matrix(TILT, [1, 0, 0])
    M = trimesh.transformations.translation_matrix([0.0, FC_Y, FC_Z])
    return M @ R

def face_box(w_, h_, d_, u=0.0, v=0.0, w=0.0):
    m = box(extents=[w_, h_, d_]); m.apply_translation([u, v, w])
    m.apply_transform(face_xf()); return m

def face_cyl(d_, w0, w1, u=0.0, v=0.0, s=48):
    m = cylinder(radius=d_/2, height=w1-w0, sections=s)
    m.apply_translation([u, v, (w0+w1)/2])
    m.apply_transform(face_xf()); return m

def walls_box():
    """The vertical envelope every internal cut is bounded by."""
    return blk(BODY_X[0]+WALL, BODY_X[1]-WALL,
               BODY_Y[0]+WALL, BODY_Y[1]-WALL, -50.0, 50.0)

def inside_walls(cut):
    return inter([cut, walls_box()])


def peg_uv():
    """The four screen pegs, in face-local (u, v)."""
    return [(SCREEN_CX + su*MOD_PITCH_X/2, MOD_V + sv*MOD_PITCH_Y/2)
            for su in (-1, 1) for sv in (-1, 1)]

def lamp_uv():
    """The lamp column, in face-local (u, v). Centred on the face."""
    return list(LAMP_POS)


def base():
    """Prints SPIGOT-SIDE UP: flat on the bed, no support anywhere."""
    m = blk(*BASE_X, *BASE_Y, 0, BASE_T)
    m = chamfer_corners(m, BASE_X[0], BASE_X[1], BASE_Y[0], BASE_Y[1])

    # Registration spigots - exactly PLATE_T, so they stop flush with the
    # ceiling and never reach the drawer. A stepped pilot on the tip, not a
    # chamfer: this spigot has to find a hole it cannot see, by feel, under a
    # 30 g part, and a 0.4 mm step prints as cleanly upward as a cone would.
    for hx in HOLE_X:
        m = union([m, cylz(SPIG_D, -PLATE_T + SPIG_CH, 0, hx, DATUM_Y),
                   cylz(SPIG_D - 2*SPIG_CH, -PLATE_T, -PLATE_T + SPIG_CH,
                        hx, DATUM_Y)])

    m = diff(m, blk(*WIRE, -1, BASE_T + 1))          # wire pass

    for (jx, jy) in JOINT_PINS:
        m = diff(m, cylz(JOINT_HOLE, -1, BASE_T + 1, jx, jy))
    for (sx, sy) in JOINT_SCREWS:
        m = diff(m, cylz(2.4, -1, BASE_T + 1, sx, sy))
        # The head must sink BELOW the lid-mating face, not nearly. This is the
        # surface top_face_flat() proves the lid side of; the pod side has to
        # be just as flat or the whole thing rocks on two screw heads.
        m = diff(m, cylz(SCREW_RECESS_D, -1, SCREW_RECESS_H, sx, sy))
    return m


def body():
    """Prints FACE-DOWN. A plain wedge: flat bottom, one planar tilted face,
    vertical sides. Nothing else."""
    m = prism_x([(BODY_Y[0], 0.0), (BODY_Y[1], 0.0),
                 (BODY_Y[1], BODY_H), (BODY_Y[0], BODY_FR)],
                BODY_X[0], BODY_X[1])
    m = chamfer_corners(m, BODY_X[0], BODY_X[1], BODY_Y[0], BODY_Y[1], c=2.0)
    env = prism_x([(BODY_Y[0], -BASE_T), (BODY_Y[1], -BASE_T),
                   (BODY_Y[1], BODY_H), (BODY_Y[0], BODY_FR)],
                  BODY_X[0], BODY_X[1])
    env = chamfer_corners(env, BODY_X[0], BODY_X[1], BODY_Y[0], BODY_Y[1], c=2.0)

    # EVERY internal cut is bounded by this. Face-parallel boxes lean backwards
    # as they go deeper - in v0.1 the one clearing space behind the module
    # reached y 68.7 by z 3 and took the whole rear wall with it. Walls are
    # vertical; the cuts that make them have to be too.
    inside = inside_walls

    # Hollow PARALLEL TO THE FACE, so the shell under it is a uniform WALL.
    # u IS PART X here - face_xf()'s origin is x 0 so that SCREEN_CX and
    # lamp positions can be written as absolute case coordinates. Leaving this cut
    # centred on u 0 hollowed x -41.5..41.5 instead of 4.5..87.5: half the body
    # stayed solid, which showed up as 686 mm2 of overhang rather than as
    # anything obviously wrong in the render.
    m = diff(m, inside(
        face_box(BODY_X[1]-BODY_X[0] - 2*WALL, SLOPE_L - 2*WALL, 80.0,
                 u=(BODY_X[0]+BODY_X[1])/2, w=-WALL - 40.0)))

    # ONE opening, straight through the face wall. No bezel stack, no glass
    # relief, no PCB pocket - the module's own face seats on the wall's inner
    # surface all the way round the hole, and the pegs do the rest.
    m = diff(m, face_box(SCREEN_OPEN_W, SCREEN_OPEN_H, 2*WALL + 6.0,
                         u=SCREEN_CX, v=MOD_V, w=1.0))

    # ── the four pegs, through the module's own corner holes ──
    # Rooted on the face's inner surface, which only exists because the opening
    # stops 1.0 mm short of them.
    # A stepped pilot on each tip. Four rigid pegs at 30.40 x 28.50 engage all
    # at once with ~0.03 mm of radial clearance; without a lead-in the board
    # has to arrive within about 4 degrees of face-parallel or it will not go
    # on. The step costs nothing and prints as cleanly upward as the spigots.
    for (u, v) in peg_uv():
        # The two cylinders OVERLAP by 0.2. Butting them exactly left a
        # coplanar boolean seam that read as 7.2 mm2 of down-facing area at the
        # step - an artefact, but one the support check cannot tell from a
        # real ledge, and a check you have to explain away is no check.
        m = union([m,
                   face_cyl(PEG_D, -MOD_BACK - PEG_PROUD + PEG_LEAD,
                            -MOD_FRONT + 0.1, u=u, v=v),
                   face_cyl(PEG_D - 2*PEG_LEAD, -MOD_BACK - PEG_PROUD,
                            -MOD_BACK - PEG_PROUD + PEG_LEAD + 0.2, u=u, v=v)])

    # ── lamps: dia 5 barrels normal to the face, dead vertical in the print ──
    # Both bores stop at LAMP_DEPTH and are bounded by the walls. See the note
    # on LAMP_DEPTH: an unbounded bore leaves the part through the back.
    # The counterbore's step is a 0.4 mm annular lip facing the bed. It would
    # bridge, but a 45 deg lead-in costs nothing, doubles as a chamfer that
    # helps the LED find the bore, and leaves the part with NO down-facing
    # geometry at all rather than an argument about how small is small enough.
    for (u, v) in lamp_uv():
        m = diff(m, inside(face_cyl(LAMP_D, -WALL - 0.5, 2.0, u=u, v=v)))

    # ── cable cutout: a notch in the rear wall, centred behind the screen ──
    # Its roof faces down in part coords, which maps to +0.87 in the print pose
    # - up-facing - so a plain rectangle needs no support here.
    m = diff(m, blk(SCREEN_CX - CABLE_W/2, SCREEN_CX + CABLE_W/2,
                    BODY_Y[1] - WALL - 1.0, BODY_Y[1] + 1.0, -1.0, CABLE_H))

    # Joint down onto the baseplate. A part surface with normal (0, ny, nz)
    # lands at print-z 0.5*ny - 0.866*nz once the body is rolled onto its face,
    # so a FLAT pad top (0,0,1) lands at -0.866: a down-facing ledge with
    # nothing under it. The pads are therefore wedges sloping down toward the
    # rear, and the pins stop inside them.
    for (jx, jy) in JOINT_PINS:
        near = BODY_X[0] if jx < CASE_W/2 else BODY_X[1]
        x0, x1 = sorted((near, jx + 3.0 * (1 if jx < CASE_W/2 else -1)))
        # A TRAPEZOID, NOT A TRIANGLE. Tapering the pad to zero left a 10.9 mm
        # knife edge ramping 0.28 -> 0.00 mm, which is most of a 0.4 nozzle's
        # width: the slicer simply would not emit it and the edge would come
        # out ragged. Ending at PAD_MIN keeps the sloped top that makes it
        # printable and gives the thin end something to be.
        m = union([m, prism_x([(jy - 3.5, 0.0), (jy - 3.5, 3.6),
                               (jy + 3.0, PAD_MIN), (jy + 3.0, 0.0)], x0, x1),
                   cylz(JOINT_D, -BASE_T, 0.6, jx, jy)])
    # Bosses run up into the shell rather than stopping in mid-air, so there is
    # no crown to overhang.
    for (sx, sy) in JOINT_SCREWS:
        top = BODY_FR + (sy - BODY_Y[0])*math.tan(TILT) - WALL/math.cos(TILT)
        m = union([m, cylz(5.5, 0, top + 0.5, sx, sy)])
        m = diff(m, cylz(1.6, -1, 6.0, sx, sy))

    return inter([m, env])


def gauge_spigot():
    """Four pegs for the LID's dia 5 holes. ~3 g, six minutes.

    A printed peg going into a printed hole moves the wrong way twice: a
    modelled 5.00 hole comes out ~4.75 and a modelled peg comes out ~0.15 over,
    so the 4.85 spigot I drew first would have printed ~5.00 and simply not
    gone in. Try these in the PRINTED LID and put the winner in SPIG_D. Same
    method plate_0_bore_test used to settle the spline."""
    W, L, T_ = 20.0, 60.0, 2.0
    m = blk(0, W, 0, L, 0, T_)
    for i, d in enumerate((4.40, 4.55, 4.70, 4.85)):
        cy = 8.0 + i * 14.0
        m = union([m, cylz(d, T_, T_ + PLATE_T, W/2, cy)])
        for k in range(i + 1):
            m = diff(m, blk(-1, 2.0, cy - 4.8 + k*2.6, cy - 3.6 + k*2.6, -1, T_+1))
    return m


# The PITCH is now well attested by three agreeing drawings, so the gauge no
# longer hunts for it - all three tiles use it. What is left open is the PEG's
# press fit in a dia 3.00 hole, which is printer-specific and cannot be
# derived: see spl_press in nano.py, where the textbook allowance produced a
# part that would not go on at all. A module that seats on NONE of the three
# also tells you something - that the pitch is not what the drawings say.
PEG_CANDIDATES = (2.60, 2.80, 3.00)

def gauge_screen():
    """Three peg diameters at the drawing's pitch, plus a lamp bore. Drop the
    real module on each tile; take the one that seats fully without springing
    and does not fall off when inverted."""
    T_, TILE_W, TILE_L = 2.4, 46.0, 44.0
    total_L = len(PEG_CANDIDATES)*TILE_L + (len(PEG_CANDIDATES)-1)*4.0
    # A spine down the left edge, or the three tiles come out as three separate
    # solids in one file and the plate quietly prints them anyway.
    parts, cuts = [blk(0, 8.0, 0, total_L, 0, T_)], []
    for i, pd in enumerate(PEG_CANDIDATES):
        cy = TILE_L/2 + i * (TILE_L + 4.0)
        parts.append(blk(0, TILE_W, cy - TILE_L/2, cy + TILE_L/2, 0, T_))
        for su in (-1, 1):
            for sv in (-1, 1):
                parts.append(cylz(pd, T_, T_ + PCB_T + PEG_PROUD,
                                  TILE_W/2 + su*MOD_PITCH_X/2,
                                  cy + sv*MOD_PITCH_Y/2))
        cuts.append(cylz(LAMP_D, -1, T_ + 1, 5.0, cy))
        for k in range(i + 1):
            cuts.append(blk(TILE_W - 2.0, TILE_W + 1,
                            cy - 5 + k*3.2, cy - 3.4 + k*3.2, -1, T_ + 1))
    return diff(union(parts), union(cuts))


# ── print poses ────────────────────────────────────────────────────────────
# One definition, used by the plate, the STL export and the overhang check.
# Scoring a part in a pose it does not print in is how case_upper's logo once
# read as a 111 mm2 overhang that did not exist.
POSE_ROT = {"mount_base": 180.0,    # spigots UP
            "mount_body": 180.0 - math.degrees(TILT),   # face DOWN
            "gauge_spigot": 0.0,
            "gauge_screen": 0.0}

def posed(name):
    m = PARTS[name].copy()
    r = POSE_ROT[name]
    if r:
        m.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(r), [1, 0, 0]))
    m.apply_translation(-m.bounds[0])
    return m

def bed_contact(m, tol=0.05):
    n, zc = m.face_normals[:, 2], m.triangles_center[:, 2]
    return float(m.area_faces[(n < -0.99) & (zc < m.bounds[0][2] + tol)].sum())

def unsupported(m, cos_limit=-0.75, min_h=0.6, gap=0.6):
    """Downward faces with nothing under them. Same method as cad/overhangs.py:
    -0.75 lets a deliberate 45 deg chamfer pass and still catches anything
    flatter, and material more than 0.6 below is a bridge, not support."""
    n, zc = m.face_normals[:, 2], m.triangles_center[:, 2]
    sel = np.where((n < cos_limit) & (zc > m.bounds[0][2] + min_h))[0]
    if not len(sel):
        return 0.0
    org  = m.triangles_center[sel] + np.array([0, 0, -0.05])
    loc, idx, _ = m.ray.intersects_location(
        ray_origins=org, ray_directions=np.tile([0, 0, -1.0], (len(sel), 1)))
    near = np.zeros(len(sel), dtype=bool)
    for r, d in zip(idx, org[idx][:, 2] - loc[:, 2]):
        if d <= gap:
            near[r] = True
    return float(m.area_faces[sel[~near]].sum())


PARTS = {}
def rep(n, m):
    e = m.extents
    nb = len(m.split(only_watertight=False))
    print(f"  {n:13s} {e[0]:6.1f} x {e[1]:6.1f} x {e[2]:5.1f}   "
          f"{m.volume/1000*1.27:5.1f} g   wt={m.is_watertight} bodies={nb}")
    m.export(os.path.join(OUT, n + ".stl")); PARTS[n] = m; return m


def lid_features(lid):
    """Read the lid's real hole centres off the mesh. Hardcoding an interface is
    how two parts drift apart; this asserts ours has not."""
    s = lid.section(plane_origin=[0, 0, LID_H - PLATE_T/2], plane_normal=[0, 0, 1])
    p, _ = s.to_planar()
    poly = max(p.polygons_full, key=lambda q: q.area)
    ox, oy = poly.bounds[0], poly.bounds[1]
    out = []
    for r in poly.interiors:
        c = np.array(r.coords); lo, hi = c.min(0), c.max(0)
        out.append(((lo[0]+hi[0])/2 - ox, (lo[1]+hi[1])/2 - oy,
                    hi[0]-lo[0], hi[1]-lo[1]))
    return out


def top_face_flat(lid, x0, x1, y0, y1, n=40):
    """Ray-cast down onto the lid over the baseplate's footprint. Every ray must
    land on the top face at z = LID_H or fall through one of the three known
    openings. Anything else is a bump the pod would rock on."""
    gx, gy = np.meshgrid(np.linspace(x0 + 0.6, x1 - 0.6, n),
                         np.linspace(y0 + 0.6, y1 - 0.6, n))
    org = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, LID_H + 20.0)])
    hit, idx, _ = lid.ray.intersects_location(
        ray_origins=org, ray_directions=np.tile([0, 0, -1.0], (len(org), 1)))
    top = {}
    for i, h in zip(idx, hit):
        top[i] = max(top.get(i, -1e9), h[2])
    bad = []
    for i in range(len(org)):
        x, y = org[i][0], org[i][1]
        known = ((WIN[0] < x < WIN[1] and WIN[2] < y < WIN[3])
                 or any((x-hx)**2 + (y-DATUM_Y)**2 < (HOLE_D/2)**2 for hx in HOLE_X))
        if i not in top:
            if not known:
                bad.append((round(x, 1), round(y, 1), None))
        elif abs(top[i] - LID_H) > 0.01:
            bad.append((round(x, 1), round(y, 1), round(top[i], 2)))
    return bad


def module_solid():
    """THE REAL MODULE, AS A SOLID, where it will actually sit.

    Every FACE LAYOUT check was arithmetic on constants - eleven of them, not
    one touching a mesh - and the three real risks (the connector fouling the
    rear wall, the FPC fold, the seating shoulder) were covered by none of
    them. This builds the board, its glass, its header and Dupont housing and
    its FPC wrap as one solid and hands the question to the boolean engine:
    if this intersects mount_body, the module does not go in. Full stop.

    The PCB carries its four dia 3.00 holes so the pegs are allowed through -
    everything else is a collision."""
    parts = []
    pcb = face_box(PCB_W, PCB_H, PCB_T, u=SCREEN_CX, v=MOD_V,
                   w=-MOD_FRONT - PCB_T/2)
    for (u, v) in peg_uv():
        pcb = diff(pcb, face_cyl(MOD_HOLE_D, -MOD_BACK - 5.0, -MOD_FRONT + 1.0,
                                 u=u, v=v))
    parts.append(pcb)
    # glass, standing proud of the board toward the face
    parts.append(face_box(GLASS_W, GLASS_H, GLASS_T, u=SCREEN_CX, v=MOD_V,
                          w=-MOD_FRONT + GLASS_T/2))
    # 4-pin header + Dupont housing, pointing straight back into the pod
    parts.append(face_box(HDR_W, HDR_T, HDR_L, u=SCREEN_CX, v=HDR_V,
                          w=-MOD_BACK - HDR_L/2))
    # FPC wrap on the edge opposite the header, folded behind the board
    parts.append(face_box(FPC_W, FPC_D, FPC_T, u=SCREEN_CX,
                          v=MOD_V - PCB_H/2 + FPC_D/2,
                          w=-MOD_BACK - FPC_T/2))
    return union(parts)


def rear_wall_holes(m, n=70):
    """Cast rays inward at the rear wall. Every one must land on it at
    y = BODY_Y[1], except inside the cable notch. This is the check that was
    missing when a lamp bore left through the back and only the render caught
    it - the part was still watertight, still one body, still support-free."""
    xs = np.linspace(BODY_X[0] + 3.0, BODY_X[1] - 3.0, n)
    zs = np.linspace(0.5, BODY_H - 1.0, n)
    gx, gz = np.meshgrid(xs, zs)
    org = np.column_stack([gx.ravel(),
                           np.full(gx.size, BODY_Y[1] + 20.0), gz.ravel()])
    hit, idx, _ = m.ray.intersects_location(
        ray_origins=org, ray_directions=np.tile([0, -1.0, 0], (len(org), 1)))
    first = {}
    for i, h in zip(idx, hit):
        first[i] = max(first.get(i, -1e9), h[1])
    bad = []
    for i in range(len(org)):
        x, z = org[i][0], org[i][2]
        # the wedge's rear face only exists below the sloped top at this y
        if z > BODY_FR + (BODY_Y[1] - BODY_Y[0])*math.tan(TILT) - 0.5:
            continue
        # Exclude the notch by its TRUE bounds plus a hair. Testing it a
        # half-millimetre small reported 36 phantom holes along its own roof.
        in_notch = (abs(x - SCREEN_CX) < CABLE_W/2 + 0.2) and (z < CABLE_H + 0.2)
        if in_notch:
            continue
        if i not in first or abs(first[i] - BODY_Y[1]) > 0.05:
            bad.append((round(x, 1), round(z, 1),
                        None if i not in first else round(first[i], 2)))
    return bad


def plate(path, items):
    placed, x = [], 12.0
    for n, m in items:
        placed.append((n, m, x + m.extents[0]/2, 12.0 + m.extents[1]/2))
        x += m.extents[0] + 6.0
    write_3mf(path, placed)
    return path

def assembly(path, lid):
    b = PARTS["mount_base"].copy(); b.apply_translation([0, 0, LID_H])
    d = PARTS["mount_body"].copy(); d.apply_translation([0, 0, LID_H + BASE_T])
    write_3mf(path, [("case_upper", lid, 60.0, 60.0),
                     ("mount_base", b, 60.0, 60.0),
                     ("mount_body", d, 60.0, 60.0)])
    return path


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    print("\nshopkeeper NANO — display mount v0.3   (full width, plain tilt)\n")
    print(f"  module    1.3\" SH1106  {PCB_W} x {PCB_H}, "
          f"dia {MOD_HOLE_D} holes at {MOD_PITCH_X} x {MOD_PITCH_Y}")
    print(f"            all from the manufacturer's drawing; peg press fit is "
          f"the one open number")
    print(f"  pod       {BASE_X[1]-BASE_X[0]:.0f} x {BASE_Y[1]-BASE_Y[0]:.1f}"
          f" x {BASE_T + BODY_H:.1f}   tilt {math.degrees(TILT):.0f} deg")
    print(f"  lamps     {len(LAMP_POS)} x dia 5 mm at x " + " and ".join(f"{u:.0f}" for (u, v) in LAMP_POS))
    print(f"  machine   66.0 -> {66.0 + BASE_T + BODY_H:.1f} mm tall\n")

    rep("mount_base", base())
    rep("mount_body", body())
    rep("gauge_spigot", gauge_spigot())
    rep("gauge_screen", gauge_screen())

    lid = trimesh.load(os.path.join(NANO, "case_upper.stl"))
    ok = True
    def chk(l, c, d):
        global ok
        print(f"    [{'PASS' if c else 'FAIL'}] {l:44s} {d}")
        ok = ok and c

    print("\n  GEOMETRY")
    for n, m in PARTS.items():
        nb = len(m.split(only_watertight=False))
        chk(f"{n} is one watertight body", m.is_watertight and nb == 1,
            f"{nb} bodies, watertight={m.is_watertight}")

    print("\n  DOES IT FIT THE CASE")
    found = lid_features(lid)
    holes = sorted(f for f in found
                   if abs(f[2]-HOLE_D) < 0.2 and abs(f[3]-HOLE_D) < 0.2)
    win = [f for f in found if abs(f[2]-26.0) < 0.2 and abs(f[3]-10.0) < 0.2]
    chk("lid has 2 dia 5 holes where we think", len(holes) == 2,
        ", ".join(f"({f[0]:.2f}, {f[1]:.2f})" for f in holes))
    chk("lid window is 26 x 10 where we think", len(win) == 1,
        f"({win[0][0]:.2f}, {win[0][1]:.2f})" if win else "not found")
    for f, hx in zip(holes, sorted(HOLE_X)):
        chk(f"spigot {hx:.0f} lands on its hole",
            abs(f[0]-hx) < 0.05 and abs(f[1]-DATUM_Y) < 0.05,
            f"mesh ({f[0]:.2f}, {f[1]:.2f}) vs model ({hx:.2f}, {DATUM_Y:.2f})")

    b_asm = PARTS["mount_base"].copy(); b_asm.apply_translation([0, 0, LID_H])
    d_asm = PARTS["mount_body"].copy(); d_asm.apply_translation([0, 0, LID_H+BASE_T])
    for nm, part in (("base", b_asm), ("body", d_asm)):
        v = inter([lid, part]).volume
        chk(f"{nm} does not interfere with the lid", v < 1.0, f"{v:.4f} mm3 overlap")
    chk("base and body do not interfere", inter([b_asm, d_asm]).volume < 1.0,
        f"{inter([b_asm, d_asm]).volume:.4f} mm3 overlap")

    bad = top_face_flat(lid, *BASE_X, *BASE_Y)
    chk("lid's top face is flat under the whole pod", not bad,
        "1600 rays, all land at z 24.00" if not bad else f"{len(bad)} bad: {bad[:3]}")
    chk("pod is exactly the case width", BASE_X == (0.0, CASE_W),
        f"{BASE_X[1]-BASE_X[0]:.0f} mm, flush both sides")
    chk("spigots stop flush with the ceiling",
        abs(PARTS["mount_base"].bounds[0][2] + PLATE_T) < 1e-6,
        f"deepest point z {PARTS['mount_base'].bounds[0][2]:.2f}")
    chk("nothing reaches the drawer or the rib",
        PARTS["mount_base"].bounds[0][2] > RIB_Z,
        f"z {PARTS['mount_base'].bounds[0][2]:.2f} vs rib crown {RIB_Z:.1f}")
    chk("wire pass sits inside the window",
        WIRE[0] > WIN[0] and WIRE[1] < WIN[1] and WIRE[2] > WIN[2] and WIRE[3] < WIN[3],
        f"{WIRE[1]-WIRE[0]:.0f} x {WIRE[3]-WIRE[2]:.0f} in 26 x 10")
    chk("clears the logo deboss", BASE_Y[0] > LOGO_Y1,
        f"front edge y {BASE_Y[0]:.1f}, {BASE_Y[0]-LOGO_Y1:.1f} mm clear")
    chk("clears the rear vents", BASE_Y[1] < VENT_Y0,
        f"rear edge y {BASE_Y[1]:.1f}, {VENT_Y0-BASE_Y[1]:.1f} mm clear")

    print("\n  DOES THE MODULE ACTUALLY GO IN")
    # ONE boolean replaces eleven arithmetic assertions. The module - board,
    # glass, header, Dupont housing, FPC wrap - is built as a solid and offered
    # to the part. Any overlap at all and it does not fit.
    mod = module_solid()
    ov = inter([PARTS["mount_body"], mod])
    v = ov.volume if ov is not None and len(ov.vertices) else 0.0
    chk("module + connector + FPC clear the body", v < 0.5,
        f"{v:.3f} mm3 of overlap"
        + ("" if v < 0.5 else f"  at {np.round(ov.bounds,2).tolist()}"))
    # and it must not clash with the baseplate underneath either
    mb = PARTS["mount_base"].copy(); mb.apply_translation([0, 0, -BASE_T])
    ov2 = inter([mb, mod])
    v2 = ov2.volume if ov2 is not None and len(ov2.vertices) else 0.0
    chk("module clears the baseplate below it", v2 < 0.5, f"{v2:.3f} mm3")
    # Clearing the body is not enough - the connector must also stay INSIDE it.
    # The boolean above is happy if the header pokes clean out through the
    # cable notch, which would put a Dupont housing hanging off the back.
    chk("nothing on the module pokes out of the pod",
        mod.bounds[1][1] < BODY_Y[1] - 0.5,
        f"module reaches y {mod.bounds[1][1]:.2f}, rear face at {BODY_Y[1]:.2f}")

    print("\n  CAN IT ACTUALLY BE WIRED")
    # The one that decides whether this feature works at all. The pod's harness
    # has to reach an ESP32 that sits BELOW the deck, and the deck is a solid
    # plate. Ray-cast straight down through the lid window and see what gets
    # past both the window and the deck without crossing a drawer.
    deck = trimesh.load(os.path.join(NANO, "deck.stl"))
    deck.apply_translation([WL_DECK_X, WL_DECK_Y, 0])
    xs = np.linspace(WIRE[0], WIRE[1], 60)
    ys = np.linspace(WIRE[2], WIRE[3], 30)
    gx, gy = np.meshgrid(xs, ys)
    org = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, 50.0)])
    hit, idx, _ = deck.ray.intersects_location(
        ray_origins=org, ray_directions=np.tile([0, 0, -1.0], (len(org), 1)))
    blocked = set(idx)
    through = [i for i in range(len(org)) if i not in blocked]
    free = [i for i in through
            if NO_DRAWER[0] < org[i][0] < NO_DRAWER[1]]      # and misses a drawer
    chk("harness can reach the ESP32 below the deck", len(free) > 0,
        f"{len(through)}/{len(org)} rays clear the deck, {len(free)} of those "
        f"in the drawer-free band x {NO_DRAWER[0]:.0f}-{NO_DRAWER[1]:.0f}"
        + ("" if free else "  <-- THE DECK NEEDS A CABLE HOLE AT x 43-49"))

    print("\n  FACE LAYOUT")
    chk("pegs are inside the PCB outline",
        MOD_PITCH_X + PEG_D < PCB_W and MOD_PITCH_Y + PEG_D < PCB_H,
        f"pitch {MOD_PITCH_X} x {MOD_PITCH_Y} + peg {PEG_D} in {PCB_W} x {PCB_H}")
    chk("opening is not wider than the board",
        SCREEN_OPEN_W <= PCB_W - 0.2,
        f"opening {SCREEN_OPEN_W:.1f} vs board {PCB_W:.2f} -> shoulder "
        f"{(PCB_W-SCREEN_OPEN_W)/2:+.2f} mm a side")
    chk("joint pin is a slip fit, per the shop rule",
        real_clearance(JOINT_D, JOINT_HOLE) > 0.10,
        f"{real_clearance(JOINT_D, JOINT_HOLE):.2f} mm real "
        f"(pin {JOINT_D:.2f} prints {JOINT_D+PEG_GROW:.2f}, "
        f"hole {JOINT_HOLE:.2f} prints {JOINT_HOLE-HOLE_SHRINK:.2f})")
    chk("screw head sinks below the lid-mating face",
        SCREW_RECESS_H >= SCREW_HEAD_H + 0.15 and BASE_T - SCREW_RECESS_H >= 0.8,
        f"recess {SCREW_RECESS_H:.1f} for a {SCREW_HEAD_H:.1f} head, "
        f"{BASE_T - SCREW_RECESS_H:.1f} mm of plate left")
    # The tightest thing on the part, and BOTH numbers in it are still nominal.
    peg_in = MOD_PITCH_Y/2 - PEG_D/2
    chk("opening leaves face for the peg roots",
        peg_in - SCREEN_OPEN_H/2 >= 1.0,
        f"{peg_in - SCREEN_OPEN_H/2:.2f} mm of face at each peg "
        f"(peg inner edge v {peg_in:.2f}, opening to {SCREEN_OPEN_H/2:.2f})")
    chk("opening shows the whole glass",
        SCREEN_OPEN_W >= GLASS_W + 0.3 and SCREEN_OPEN_H >= GLASS_H + 0.3,
        f"{SCREEN_OPEN_W:.1f} x {SCREEN_OPEN_H:.1f} over a "
        f"{GLASS_W:.1f} x {GLASS_H:.1f} glass")
    chk("module overlaps the opening as a shoulder",
        (PCB_H - SCREEN_OPEN_H)/2 >= 2.0,
        f"{(PCB_H - SCREEN_OPEN_H)/2:.2f} mm top and bottom")
    act_lo = ACT_OFF - ACT_H/2 + SCREEN_OPEN_H/2
    act_hi = SCREEN_OPEN_H/2 - (ACT_OFF + ACT_H/2)
    chk("active area is fully inside the opening", act_lo > 1.0 and act_hi > 1.0,
        f"{act_lo:.2f} mm below, {act_hi:.2f} mm above "
        f"(asymmetric because the A/A is offset {ACT_OFF:+.2f})")
    chk(f"peg is a press fit in a dia {MOD_HOLE_D} hole",
        0.0 < MOD_HOLE_D - PEG_D < 0.35,
        f"dia {PEG_D} modelled - prints ~{PEG_D+0.15:.2f}, confirm on gauge_screen")
    chk("window is offset for the real active area", abs(ACT_OFF) > 1.0,
        f"{ACT_OFF:+.2f} mm up the slope - the A/A is NOT centred on the board")
    chk("FPC wrap band is clear of the pegs",
        FPC_W/2 + 1.0 < MOD_PITCH_X/2 - PEG_D/2,
        f"FPC to u {FPC_W/2:.1f}, nearest peg edge at {MOD_PITCH_X/2 - PEG_D/2:.2f}")
    lampsu = [u for (u, v) in lamp_uv()]
    chk("lamps clear the screen",
        all(abs(u - SCREEN_CX) - LAMP_D/2 > PCB_W/2 + 1.0 for (u, v) in lamp_uv()),
        "gap "
        + ", ".join(f"{abs(u-SCREEN_CX) - LAMP_D/2 - PCB_W/2:.2f}"
                    for (u, v) in lamp_uv()) + " mm")
    chk("lamps clear the side walls",
        all(BODY_X[0] + WALL < u - LAMP_D/2 and u + LAMP_D/2 < BODY_X[1] - WALL
            for (u, v) in lamp_uv()),
        ", ".join(f"x {u-LAMP_D/2:.1f}..{u+LAMP_D/2:.1f}" for (u, v) in lamp_uv())
        + f"  inner walls {BODY_X[0]+WALL:.1f}..{BODY_X[1]-WALL:.1f}")
    chk("lamps sit above their own spigots",
        all(abs(u - hx) < 0.01 for (u, v), hx in zip(lamp_uv(), sorted(HOLE_X))),
        ", ".join(f"lamp x {u:.0f} over spigot x {hx:.0f}"
                  for (u, v), hx in zip(lamp_uv(), sorted(HOLE_X))))
    chk("lamps fit the slope",
        max(abs(v) for (u, v) in lamp_uv()) + LAMP_D/2
        < SLOPE_L/2 - WALL/math.cos(TILT),
        f"reach {max(abs(v) for (u, v) in lamp_uv()) + LAMP_D/2:.1f}, "
        f"slope half {SLOPE_L/2 - WALL/math.cos(TILT):.1f}")

    print("\n  NOTHING BORES OUT OF THE PART")
    # The BORE, not its axis. The end disc reaches r*cos(TILT) further in y and
    # r*sin(TILT) lower in z than the centreline - 2.60 and 1.50 mm here. The
    # axis-only version of this check was 2.6 mm optimistic about precisely the
    # failure it exists to catch.
    r = LAMP_D/2
    for i, (u, v) in enumerate(lamp_uv()):
        by = FC_Y + v*math.cos(TILT) + LAMP_DEPTH*math.sin(TILT) + r*math.cos(TILT)
        bz = FC_Z + v*math.sin(TILT) - LAMP_DEPTH*math.cos(TILT) - r*math.sin(TILT)
        chk(f"lamp {i+1} BORE (not its axis) stops inside",
            by < BODY_Y[1] - 0.5 and bz > 0.5,
            f"rim reaches y {by:.2f} (rear face {BODY_Y[1]:.2f}), z {bz:.2f}")
    # and no lamp may eat into a joint boss - lamp 3 took a 9.2 mm3 bite out of
    # the x=12 boss before the column moved to x 20
    for i, (u, v) in enumerate(lamp_uv()):
        bore = inside_walls(face_cyl(LAMP_D, -LAMP_DEPTH, 2.0, u=u, v=v))
        for (sx, sy) in JOINT_SCREWS:
            b = cylz(5.5, 0, 30.0, sx, sy)
            o = inter([bore, b])
            vv = o.volume if o is not None and len(o.vertices) else 0.0
            chk(f"lamp {i+1} misses the boss at x {sx:.0f}", vv < 0.01,
                f"{vv:.3f} mm3")
    holes = rear_wall_holes(PARTS["mount_body"])
    chk("rear wall is solid except the cable notch", not holes,
        "4900 rays, all land at y "
        f"{BODY_Y[1]:.2f}" if not holes else f"{len(holes)} bad: {holes[:4]}")
    for (sx, sy) in JOINT_SCREWS:
        chk(f"cable notch clears the boss at x {sx:.0f}",
            abs(sx - SCREEN_CX) > CABLE_W/2 + 5.5/2,
            f"{abs(sx - SCREEN_CX) - CABLE_W/2 - 5.5/2:.2f} mm clear")

    print("\n  CAN IT PRINT WITHOUT SUPPORT")
    for n in POSE_ROT:
        m = posed(n)
        m.export(os.path.join(POSE, n + ".stl"))
        area, contact = unsupported(m), bed_contact(m)
        chk(f"{n} needs no support", area < 5.0,
            f"{area:6.1f} mm2 unsupported, {contact:6.1f} mm2 on the bed")
        chk(f"{n} has real bed contact", contact > 100.0, f"{contact:.1f} mm2")

    p1 = plate(os.path.join(OUT, "plate_mount.3mf"),
               [(n, posed(n)) for n in ("mount_base", "mount_body")])
    p2 = plate(os.path.join(OUT, "plate_gauges.3mf"),
               [(n, posed(n)) for n in ("gauge_spigot", "gauge_screen")])
    p3 = assembly(os.path.join(OUT, "assembly_mount.3mf"), lid)
    print(f"\n  parts    -> {p1}   {verify(p1)}")
    print(f"  gauges   -> {p2}   {verify(p2)}")
    print(f"  assembly -> {p3}   {verify(p3)}")
    print("\n  " + ("ALL CHECKS PASS" if ok else "*** CHECKS FAILED ***") + "\n")
