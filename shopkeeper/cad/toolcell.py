#!/usr/bin/env python3
"""
ToolCell — parametric generator for the parts that drop into the
Ryobi Mini Desktop Toolbox large drawer.

Everything is driven from the PARAMS block. Change a number, re-run,
reprint. Outputs STL per part plus a combined 3MF.

Frame of reference (drawer-local, mm):
    X  across the drawer width   0 .. 172.6   (left to right)
    Y  drawer depth              0 .. 91      (0 = back wall)
    Z  height above drawer floor 0 .. 52
"""
import os, math
import numpy as np
import trimesh
from trimesh.creation import box, cylinder

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
os.makedirs(OUT, exist_ok=True)

# ───────────────────────── PARAMS ─────────────────────────
P = dict(
    # measured from the supplied STLs
    drawer_w      = 172.6,
    drawer_d      = 91.0,
    drawer_h      = 52.0,
    fit_clear     = 1.0,    # total side-to-side slack so the carrier drops in

    # SG90 envelope (TowerPro, plastic gear)
    sg_body_l     = 22.8,   # along its own long axis -> vertical here
    sg_body_w     = 12.2,   # -> drawer depth here
    sg_body_h     = 22.7,   # along the shaft -> drawer width here
    sg_tab_span   = 32.2,   # tab tip to tab tip
    sg_shaft_off  = 5.9,    # shaft centre from one end of body_l
    sg_boss_dia   = 9.0,

    clear         = 0.30,   # per-face print clearance in pockets

    # hinge geometry
    axis_z        = 39.0,   # hinge axis height above drawer floor
    carrier_d     = 18.0,   # carrier depth (eats into the bin)
    web_h         = 20.0,   # connecting web height between housings
    housing_h     = 52.0,

    # idler
    axle_dia      = 4.0,
    axle_len      = 2.5,
    boss_len      = 2.0,
    bore_extra    = 0.35,   # radius added to the bore -> running fit

    # flap
    flap_t        = 3.0,
    flap_gap      = 0.6,    # all-round clearance
    arm_t         = 3.0,
    arm_holes_r   = (11.0, 16.0),
    arm_hole_dia  = 1.8,

    post_w        = 10.0,    # central idler post, bored straight through
    end_wall      = 3.0,
    wall          = 2.6,
)

def T(m, x=0, y=0, z=0):
    m.apply_translation([x, y, z]); return m

def blk(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box from corner to corner."""
    return T(box(extents=[x1-x0, y1-y0, z1-z0]),
             (x0+x1)/2, (y0+y1)/2, (z0+z1)/2)

def cyl_x(dia, x0, x1, y, z, sections=48):
    c = cylinder(radius=dia/2, height=x1-x0, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
    return T(c, (x0+x1)/2, y, z)

def diff(a, b):
    return trimesh.boolean.difference([a, b], engine="manifold")

def union(parts):
    return trimesh.boolean.union(parts, engine="manifold")

# ───────────────────── derived layout ─────────────────────
W     = P["drawer_w"] - P["fit_clear"]
D     = P["drawer_d"]
AZ    = P["axis_z"]
CD    = P["carrier_d"]
AY    = CD / 2                      # hinge axis sits on the carrier centreline

sg_l, sg_w, sg_h = P["sg_body_l"], P["sg_body_w"], P["sg_body_h"]
cl    = P["clear"]

# servo pocket footprint in X (shaft axis) and Y (depth)
POCK_X = sg_h + 2*cl                       # 23.3
POCK_Y = sg_w + 2*cl                       # 12.8
# vertical: tab span, with the body sitting shaft-high on the axis
tab_over = (P["sg_tab_span"] - sg_l) / 2   # 4.7 beyond the body each end
body_z0  = AZ - (sg_l - P["sg_shaft_off"]) # body bottom, shaft near the top
POCK_Z0  = body_z0 - tab_over - cl

# X layout: servo | flap | post | flap | servo
EW   = P["end_wall"]
sv_x0_L, sv_x1_L = EW, EW + POCK_X                     # left servo pocket
horn_L           = sv_x1_L + 5.5                       # shaft boss + horn
sv_x1_R, sv_x0_R = W - EW, W - EW - POCK_X             # right servo pocket
horn_R           = sv_x0_R - 5.5

POST_W  = P["post_w"]
post_x0 = W/2 - POST_W/2
post_x1 = W/2 + POST_W/2

# symmetric: take the tighter of the two sides so both flaps are identical
FLAP_W  = min(post_x0 - (horn_L + P["arm_t"]),
              (horn_R - P["arm_t"]) - post_x1) - P["flap_gap"]
FLAP_D  = D - CD - P["flap_gap"]
# where each flap's drive-arm face sits in drawer X
FLAP_A_X = horn_L + P["arm_t"]
FLAP_B_X = horn_R - P["arm_t"] - FLAP_W

# ───────────────────── PART 1: hinge carrier ─────────────────────
def hinge_carrier():
    web  = blk(0, W, 0, CD, 0, P["web_h"])
    hL   = blk(0, horn_L,  0, CD, 0, P["housing_h"])
    hR   = blk(horn_R, W,  0, CD, 0, P["housing_h"])
    post = blk(post_x0, post_x1, 0, CD, 0, P["housing_h"])
    body = union([web, hL, hR, post])

    voids = []
    # servo pockets, open to the top so they print without supports
    for x0 in (sv_x0_L, sv_x0_R):
        voids.append(blk(x0, x0+POCK_X, AY-POCK_Y/2, AY+POCK_Y/2,
                         POCK_Z0, P["housing_h"] + 5))
    # shaft boss clearance, bored through toward the flap side
    voids.append(cyl_x(P["sg_boss_dia"]+1.0, sv_x1_L-0.5, horn_L+1.0, AY, AZ))
    voids.append(cyl_x(P["sg_boss_dia"]+1.0, horn_R-1.0, sv_x0_R+0.5, AY, AZ))
    # idler: single bore straight through the central post, both axles enter it
    br = P["axle_dia"] + P["bore_extra"]*2
    voids.append(cyl_x(br, post_x0 - 1.0, post_x1 + 1.0, AY, AZ))
    # retainer-bar screw bosses (2 per servo, straddling the pocket)
    for x0 in (sv_x0_L, sv_x0_R):
        for xc in (x0 - 1.6, x0 + POCK_X + 1.6):
            voids.append(trimesh.creation.cylinder(radius=0.8, height=14,
                         sections=24, transform=trimesh.transformations
                         .translation_matrix([xc, AY, P["housing_h"]-6])))
    # cable channel along the back
    voids.append(blk(-1, W+1, 0.0, 4.0, P["web_h"]-6, P["web_h"]-1))
    return diff(body, union(voids))

# ───────────────────── PART 2: flap ─────────────────────
def flap():
    # The plate hangs BELOW the hinge axis, not centred on it, so every
    # feature shares one flat bottom face at z = AZ - flap_t. Without this
    # the drive arm reaches under the plate and the first layer prints in air.
    z0, z1 = AZ - P["flap_t"], AZ
    plate = blk(0, FLAP_W, AY, AY + FLAP_D, z0, z1)

    # drive arm: plate perpendicular to X at the servo end, rising above z1
    arm = blk(-P["arm_t"], 0, AY + 5, AY + 21, z0, AZ + 4.5)
    holes = [cyl_x(P["arm_hole_dia"], -P["arm_t"]-1, 1, AY + r, AZ)
             for r in P["arm_holes_r"]]

    # stub axle at the post end, embedded in a boss that also reaches z0
    bl = P["boss_len"]
    boss = blk(FLAP_W, FLAP_W + bl, AY - 3.5, AY + 8, z0, AZ + 3.5)
    axle = cyl_x(P["axle_dia"] - 0.15, FLAP_W + bl,
                 FLAP_W + bl + P["axle_len"], AY, AZ)

    # finger lip so it can be pushed shut without touching the contents
    lip = blk(FLAP_W*0.35, FLAP_W*0.65, AY + FLAP_D - 3, AY + FLAP_D, z1, z1 + 4)

    return diff(union([plate, arm, boss, axle, lip]), union(holes))

# ───────────────────── PART 3: bin divider ─────────────────────
def bin_divider():
    return blk(-1.5, 1.5, 0, FLAP_D + 2, 0, AZ - P["flap_t"] - 1.0)

# ───────────────────── PART 4: servo retainer bar ─────────────────────
def retainer():
    bar = blk(-POCK_X/2 - 5, POCK_X/2 + 5, AY - 7, AY + 7, 0, 3)
    holes = [trimesh.creation.cylinder(radius=1.1, height=10, sections=24,
             transform=trimesh.transformations.translation_matrix(
                 [xc, AY, 1.5])) for xc in (-POCK_X/2 - 1.6, POCK_X/2 + 1.6)]
    return diff(bar, union(holes))

# ───────────────────── build ─────────────────────
def report(name, m):
    e = m.extents
    print(f"  {name:22s} {e[0]:7.2f} x {e[1]:7.2f} x {e[2]:7.2f} mm   "
          f"vol {m.volume/1000:6.1f} cm3  {m.volume/1000*1.27:6.1f} g  "
          f"watertight={m.is_watertight}")
    m.export(os.path.join(OUT, name + ".stl"))
    return m

print("ToolCell part generation")
print(f"  hinge axis      z = {AZ}   y = {AY}")
print(f"  servo pocket    {POCK_X:.1f} x {POCK_Y:.1f} x {P['housing_h']-POCK_Z0:.1f}  (from z={POCK_Z0:.1f})")
print(f"  flap            {FLAP_W:.1f} x {FLAP_D:.1f}")
print(f"  bin usable      {FLAP_W:.1f} x {FLAP_D:.1f} x {AZ - P['flap_t']/2:.1f}")

# ── fit checks: these are the things that quietly ruin a print ──
print("\n  FIT CHECKS")
ok = True
def chk(label, cond, detail):
    global ok
    ok &= cond
    print(f"    [{'PASS' if cond else 'FAIL'}] {label:34s} {detail}")

chk("carrier fits drawer width",
    W + 0.2 <= P["drawer_w"], f"{W:.1f} in {P['drawer_w']:.1f}")

axA0 = FLAP_A_X + FLAP_W + P["boss_len"]
axA1 = axA0 + P["axle_len"]
axB1 = FLAP_B_X - P["boss_len"]
axB0 = axB1 - P["axle_len"]
chk("flap A axle inside post bore",
    post_x0 - 1.0 <= axA0 and axA1 <= post_x1 + 1.0,
    f"axle {axA0:.1f}-{axA1:.1f}  bore {post_x0-1:.1f}-{post_x1+1:.1f}")
chk("flap B axle inside post bore",
    post_x0 - 1.0 <= axB0 and axB1 <= post_x1 + 1.0,
    f"axle {axB0:.1f}-{axB1:.1f}  bore {post_x0-1:.1f}-{post_x1+1:.1f}")
chk("axles do not collide", axA1 + 0.5 <= axB0,
    f"gap {axB0-axA1:.2f} mm")
chk("flap clears drawer front",
    AY + FLAP_D + 1 <= D, f"front edge y={AY+FLAP_D:.1f} of {D}")
chk("servo tabs clear drawer lip",
    POCK_Z0 + P["sg_tab_span"] <= P["drawer_h"],
    f"tab top z={POCK_Z0+P['sg_tab_span']:.1f} of {P['drawer_h']}")

tip_z = AZ + FLAP_D * math.sin(math.radians(66))
print(f"    [INFO] flap tip at 66 deg reaches z={tip_z:.0f} mm "
      f"-> {tip_z - P['drawer_h']:.0f} mm above the drawer lip. "
      f"Drawer MUST be at full extension.")
print(f"    {'ALL CHECKS PASSED' if ok else '*** CHECKS FAILED ***'}\n")
def bed_area(m):
    """Area of downward-facing faces sitting on the lowest plane."""
    zmin = m.bounds[0][2]
    n = m.face_normals[:, 2]
    zc = m.triangles_center[:, 2]
    sel = (n < -0.9) & (zc < zmin + 0.15)
    return float(m.area_faces[sel].sum())

def to_bed(m):
    """Drop to z=0 and move the min corner to the origin — print coords."""
    m = m.copy()
    m.apply_translation(-m.bounds[0])
    return m

def place(m, x, y):
    m = m.copy(); m.apply_translation([x, y, 0]); return m

parts = {}
for name, fn in [("hinge_carrier", hinge_carrier), ("flap", flap),
                 ("bin_divider", bin_divider), ("servo_retainer", retainer)]:
    parts[name] = to_bed(report(name, fn()))

print("\n  BED CONTACT  (a part with almost none prints in mid-air)")
for name, m in parts.items():
    a  = bed_area(m)
    fp = m.extents[0] * m.extents[1]
    pc = 100 * a / fp if fp else 0
    flag = "ok" if pc >= 8 else "*** TOO LITTLE ***"
    print(f"    {name:16s} {a:7.1f} mm2  = {pc:5.1f}% of footprint   {flag}")

# combined 3MF, laid out flat on a 256 mm plate, everything at z = 0
LAYOUT = [("hinge_carrier", parts["hinge_carrier"],  10,  10),
          ("flap_A",        parts["flap"],           10,  45),
          ("flap_B",        parts["flap"],           70,  45),
          ("bin_divider",   parts["bin_divider"],   130,  45),
          ("retainer_A",    parts["servo_retainer"],145, 135),
          ("retainer_B",    parts["servo_retainer"],185, 135)]
CT = ('<?xml version="1.0" encoding="UTF-8"?>\n'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
      '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>')

def write_3mf(path, items):
    """Minimal, correct 3MF. trimesh 5.0 writes an empty <build> section,
    which makes every slicer show an empty plate."""
    import zipfile
    res, build = [], []
    for i, (name, m, tx, ty) in enumerate(items, start=1):
        v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>'
                    for a, b, c in m.vertices)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                    for a, b, c in m.faces)
        res.append(f'<object id="{i}" type="model" name="{name}">'
                   f'<mesh><vertices>{v}</vertices>'
                   f'<triangles>{t}</triangles></mesh></object>')
        build.append(f'<item objectid="{i}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {tx:.4f} {ty:.4f} 0"/>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
           '<metadata name="Application">ToolCell generator</metadata>'
           f'<resources>{"".join(res)}</resources>'
           f'<build>{"".join(build)}</build></model>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", xml)

x1 = max(x + m.extents[0] for _, m, x, y in LAYOUT)
y1 = max(y + m.extents[1] for _, m, x, y in LAYOUT)
z1 = max(m.extents[2] for _, m, _, _ in LAYOUT)
print(f"\n  plate envelope  {x1:.0f} x {y1:.0f} x {z1:.0f} mm  "
      f"({len(LAYOUT)} objects, all at z=0)")
p3 = os.path.join(OUT, "toolcell_parts.3mf")
write_3mf(p3, LAYOUT)
import zipfile as _z
with _z.ZipFile(p3) as z:
    xml = z.read("3D/3dmodel.model").decode()
print(f"  objects={xml.count('<object id=')}  build items={xml.count('<item objectid=')}"
      f"   {'OK' if xml.count('<object id=') == xml.count('<item objectid=') else '*** MISMATCH ***'}")
print(f"  wrote {p3}")
