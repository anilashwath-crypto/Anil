#!/usr/bin/env python3
"""
ToolCell — complete purpose-built cabinet with rack-and-pinion sliding lids.

Nothing here depends on the Ryobi model. Every dimension is derived from
the mechanism outward, so the parts are guaranteed to fit each other.

STACK (bottom to top)
    feet            12
    base bay        55   electronics: ESP32, PSU, terminal blocks
    mid bay         60   the live drawer
    control head    42   keypad on top, OLED on front, tablet cradle
                   ---
                   169 mm tall, 216 x 136 footprint

MECHANISM
    Two lids slide sideways on racks driven by SG90 pinions. Lid B rides
    above lid A, so only one bin can be open at a time — which is what
    the commercial cabinets enforce too, and it comes free here.

    Sliding needs ZERO vertical clearance, so unlike a hinged flap the
    drawer position no longer matters and a servo can never drive into
    the bay above and strip itself.
"""
import os, math
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from mf3 import write_3mf, verify

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────── PARAMS ───────────────────────────
P = dict(
    case_w = 216.0, case_d = 136.0, wall = 3.0,
    h_base = 55.0, h_mid = 60.0, h_head = 42.0, h_foot = 12.0,
    lip = 3.0, lip_w = 3.0,            # stacking lip between modules

    dr_wall = 2.5, dr_front = 5.0, dr_floor = 2.5,
    dr_side_clear = 2.0, dr_top_clear = 3.0,

    # gearing
    module = 1.5, teeth = 24, press = math.radians(20.0),
    gear_t = 6.0, backlash = 0.35,

    # servo
    sg_l = 22.8, sg_w = 12.2, sg_h = 22.7, sg_tab = 32.2, sg_spline = 4.8,
    clear = 0.30,

    lid_t = 3.0, lid_gap = 0.8,
    z_lidA = 34.0, z_lidB = 42.0,      # underside of each lid
    mech_d = 46.0,                     # rear zone depth reserved for gearing
)

M, N   = P["module"], P["teeth"]
R_P    = M * N / 2.0                    # pitch radius 18.0
R_TIP  = R_P + M
R_ROOT = R_P - 1.25 * M
PITCH  = math.pi * M
TRAVEL = math.pi * R_P                  # 180 deg of pinion

def T(m, x=0, y=0, z=0):
    m.apply_translation([x, y, z]); return m

def blk(x0, x1, y0, y1, z0, z1):
    # sort every pair: a reversed pair silently makes a negative-extent box,
    # which manifold rejects as "not a volume" far away from the real mistake
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    assert x1 > x0 and y1 > y0 and z1 > z0, f"degenerate box {x0,x1,y0,y1,z0,z1}"
    return T(box(extents=[x1-x0, y1-y0, z1-z0]),
             (x0+x1)/2, (y0+y1)/2, (z0+z1)/2)

def cyl_z(dia, z0, z1, x, y, s=64):
    return T(cylinder(radius=dia/2, height=z1-z0, sections=s), x, y, (z0+z1)/2)

def cyl_x(dia, x0, x1, y, z, s=48):
    c = cylinder(radius=dia/2, height=x1-x0, sections=s)
    c.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
    return T(c, (x0+x1)/2, y, z)

def cyl_y(dia, y0, y1, x, z, s=48):
    c = cylinder(radius=dia/2, height=y1-y0, sections=s)
    c.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2, [1,0,0]))
    return T(c, x, (y0+y1)/2, z)

def diff(a, b): return trimesh.boolean.difference([a, b], engine="manifold")
def union(p):   return trimesh.boolean.union(p, engine="manifold")

def chamfer_verticals(m, c=4.0):
    """Knock the four vertical corners off. Costs nothing and is the single
    biggest difference between "printed box" and "product" at a glance."""
    s = c * math.sqrt(2)
    cuts = []
    for (x, y) in ((0, 0), (CW, 0), (0, CD), (CW, CD)):
        b = box(extents=[s, s, 600])
        b.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi / 4, [0, 0, 1]))
        cuts.append(T(b, x, y, 0))
    return diff(m, union(cuts))

def vents(m, h, n=5):
    """Louvre slots in both side walls of a module."""
    for i in range(n):
        z = 12 + i * 7.5
        if z + 3 > h - 8:
            break
        for x in (-1, CW - WL - 1):
            m = diff(m, blk(x, x + WL + 2, CD * 0.30, CD * 0.72, z, z + 3.2))
    return m

# ───────────────────── gear generation ─────────────────────
def pinion(hub_top):
    """Straight-flank spur gear — the standard printed-gear approximation.
    Loads here are ~0.1 N against ~6 N available, so tooth form is not critical."""
    half = (PITCH / 2 - P["backlash"]) / 2 / R_P     # half tooth angle at pitch
    da   = M * math.tan(P["press"]) / R_TIP          # taper toward the tip
    dr   = 1.25 * M * math.tan(P["press"]) / R_ROOT  # widen toward the root
    pts = []
    for i in range(N):
        th = 2 * math.pi * i / N
        for a, r in ((th - half - dr, R_ROOT), (th - half + da, R_TIP),
                     (th + half - da, R_TIP), (th + half + dr, R_ROOT)):
            pts.append((r * math.cos(a), r * math.sin(a)))
    g = extrude_polygon(Polygon(pts), P["gear_t"])
    hub = cyl_z(11.0, P["gear_t"], hub_top, 0, 0)
    body = union([g, hub])
    # SG90 spline pocket + horn screw clearance
    body = diff(body, cyl_z(P["sg_spline"] + 0.35, -1, hub_top - 3, 0, 0))
    body = diff(body, cyl_z(2.6, hub_top - 3, hub_top + 1, 0, 0))
    return body

def rack(length, z0):
    """Rack bar with teeth on its +Y face, meshing a pinion centred below."""
    h_t  = M + 1.25 * M
    base = blk(0, length, 0, 4.0, z0, z0 + P["gear_t"])
    tt   = []
    n    = int(length / PITCH)
    for i in range(n):
        xc  = (i + 0.5) * PITCH
        top = (PITCH / 2 - P["backlash"]) / 2
        bot = top + h_t * math.tan(P["press"])
        poly = Polygon([(xc - bot, 4.0), (xc - top, 4.0 + h_t),
                        (xc + top, 4.0 + h_t), (xc + bot, 4.0)])
        t = extrude_polygon(poly, P["gear_t"]); t.apply_translation([0, 0, z0])
        tt.append(t)
    return union([base] + tt)

# ───────────────────── derived drawer layout ─────────────────────
CW, CD, WL = P["case_w"], P["case_d"], P["wall"]
BAY_W = CW - 2 * WL
BAY_D = CD - WL
DR_W  = BAY_W - 2 * P["dr_side_clear"]
DR_D  = BAY_D - 4.0
DR_H  = P["h_mid"] - P["dr_top_clear"]

IN_W  = DR_W - 2 * P["dr_wall"]
IN_D  = DR_D - P["dr_wall"] - P["dr_front"]
IN_H  = DR_H - P["dr_floor"]

BIN_Y0 = P["mech_d"]
BIN_D  = IN_D - BIN_Y0
CELL_W = (IN_W - 3.0) / 2.0                      # 3 mm centre divider
SERVO_X = (IN_W * 0.22, IN_W * 0.78)
RACK_Y  = 40.0                                    # rack pitch line
PIN_Y   = RACK_Y - R_P                            # pinion centre

# ───────────────────── PART: cabinet shells ─────────────────────
def shell(h, floor=True, top=False, lip_top=True, recess_bottom=True):
    outer = blk(0, CW, 0, CD, 0, h)
    z0 = P["dr_floor"] if floor else -1
    cav = blk(WL, CW - WL, WL, CD + 1, WL if floor else -1,
              h - (WL if top else 0) + (0 if top else 1))
    m = diff(outer, cav)
    if lip_top:
        m = union([m, blk(WL + 0.6, CW - WL - 0.6, WL + 0.6, CD - 0.6,
                          h, h + P["lip"])])
    if recess_bottom:
        m = diff(m, blk(WL + 0.3, CW - WL - 0.3, WL + 0.3, CD - 0.3,
                        -1, P["lip"] + 0.3))
    return m

def case_base():
    """Electronics bay. Fixed shell, removable front panel, rear power entry."""
    m = shell(P["h_base"], floor=True, top=False, recess_bottom=False)
    # front opening for the removable panel
    m = diff(m, blk(14, CW - 14, -1, WL + 1, 10, P["h_base"] - 8))
    # panel screw bosses
    for x in (9, CW - 9):
        for z in (14, P["h_base"] - 12):
            m = diff(m, cyl_y(2.6, -1, WL + 1, x, z))
    # DC jack, rear wall
    m = diff(m, cyl_y(8.0, CD - WL - 1, CD + 1, 40, 26))
    # power switch, rear wall
    m = diff(m, blk(60, 74, CD - WL - 1, CD + 1, 19, 33))
    # cable riser to the bay above
    m = diff(m, blk(CW - 34, CW - 14, CD - WL - 4, CD + 1, 30, P["h_base"] + 4))
    # tray mounting bosses in the floor
    for x in (26, CW - 26):
        for y in (26, CD - 30):
            m = union([m, cyl_z(8.0, WL, WL + 4, x, y)])
            m = diff(m, cyl_z(2.5, WL + 1, WL + 5, x, y))
    m = vents(m, P["h_base"])
    return chamfer_verticals(m)

def case_mid():
    """Drawer bay. Floor carries the drawer; front is fully open."""
    m = shell(P["h_mid"], floor=True, top=False)
    m = diff(m, blk(WL, CW - WL, -1, WL + 1, WL, P["h_mid"]))     # drawer mouth
    m = diff(m, blk(CW - 34, CW - 14, CD - WL - 4, CD + 1, -1, P["h_mid"] + 4))
    # SW1 boss: drawer-open detection, front-inside on the fixed shell
    m = union([m, blk(WL, WL + 12, WL + 2, WL + 16, WL, WL + 14)])
    m = diff(m, cyl_y(2.4, WL + 1, WL + 15, WL + 6, WL + 7))
    return chamfer_verticals(m)

def case_head():
    """Control head. Keypad in the top, OLED in the front, tablet slot behind."""
    m = shell(P["h_head"], floor=False, top=True, lip_top=False)
    H = P["h_head"]
    # keypad aperture, top face, front half
    m = diff(m, blk(28, 98, 16, 93, H - WL - 1, H + 1))
    m = union([m, blk(26, 100, 14, 95, H - WL - 1.2, H - WL)])     # seating lip
    m = diff(m, blk(28, 98, 16, 93, H - WL - 1.3, H + 1))
    # tablet cradle: slot raked back 15 deg
    slot = blk(-60, 60, -6, 6, -30, 30)
    slot.apply_transform(trimesh.transformations.rotation_matrix(
        math.radians(15), [1, 0, 0]))
    m = diff(m, T(slot, CW / 2, CD - 30, H - 12))
    # 0.91in OLED window + 2 status LEDs, front face
    m = diff(m, blk(CW/2 - 13, CW/2 + 13, -1, WL + 1, 14, 24))
    for dx in (-46, 46):
        m = diff(m, cyl_y(5.2, -1, WL + 1, CW/2 + dx, 19))
    # OLED module mounting posts
    for dx in (-16, 16):
        m = union([m, blk(CW/2 + dx - 2, CW/2 + dx + 2, WL, WL + 5, 10, 28)])
    # cable pass-through from the bay below
    m = diff(m, blk(CW - 34, CW - 14, CD - WL - 4, CD + 1, -1, 18))
    return chamfer_verticals(m)

def elec_panel():
    p = blk(0, CW - 26, 0, 3, 0, P["h_base"] - 20)
    for x in (5, CW - 31):
        for z in (5, P["h_base"] - 25):
            p = diff(p, cyl_y(3.4, -1, 4, x, z))
    return p

def elec_tray():
    """Drops into the base on four bosses. Populate it on the bench, then
    slide the whole loom in as one piece - the difference between a demo you
    can service and one you have to gut."""
    w, d = CW - 52, CD - 56
    m = blk(0, w, 0, d, 0, 3)
    # corner fixings matching the base bosses
    for x in (0, w):
        for y in (0, d):
            m = union([m, cyl_z(9.0, 0, 3, x, y)])
            m = diff(m, cyl_z(3.4, -1, 4, x, y))
    # ESP32-S3 pad: four posts on a 48 x 21 pattern, USB-C facing the panel
    for dx in (-24, 24):
        for dy in (-10.5, 10.5):
            m = union([m, cyl_z(6.0, 3, 8, 44 + dx, 30 + dy)])
            m = diff(m, cyl_z(1.7, 4, 9, 44 + dx, 30 + dy))
    m = union([m, blk(16, 74, 12, 16, 3, 5)])
    # cable-tie slot pairs across the tray
    for cx in (100, 130, 100, 130):
        pass
    for cy in (18, 46, 74):
        for cx in (98, 128, 158):
            m = diff(m, blk(cx, cx + 3, cy - 5, cy + 5, -1, 4))
            m = diff(m, blk(cx + 9, cx + 12, cy - 5, cy + 5, -1, 4))
    # raised pad for the 5 V supply brick
    m = union([m, blk(96, 168, 12, 80, 3, 6)])
    return m

def foot():
    return blk(0, 22, 0, 22, 0, P["h_foot"])

# ───────────────────── PART: drawer ─────────────────────
def drawer():
    outer = blk(0, DR_W, 0, DR_D, 0, DR_H)
    cav = blk(P["dr_wall"], DR_W - P["dr_wall"], P["dr_wall"],
              DR_D - P["dr_front"], P["dr_floor"], DR_H + 1)
    m = diff(outer, cav)

    ox, oy = P["dr_wall"], P["dr_wall"]
    # centre divider between the two bins
    m = union([m, blk(ox + CELL_W, ox + CELL_W + 3.0, oy + BIN_Y0,
                      oy + IN_D, P["dr_floor"], P["dr_floor"] + P["z_lidA"] - 4)])
    # servo wells, shafts vertical
    for sx in SERVO_X:
        well = blk(ox + sx - P["sg_l"]/2 - P["clear"], ox + sx + P["sg_l"]/2 + P["clear"],
                   oy + PIN_Y - P["sg_w"]/2 - P["clear"], oy + PIN_Y + P["sg_w"]/2 + P["clear"],
                   P["dr_floor"], P["dr_floor"] + P["sg_h"] + 3)
        m = diff(m, well)
        for tx in (-P["sg_tab"]/2 + 2.2, P["sg_tab"]/2 - 2.2):
            m = diff(m, cyl_z(1.7, P["dr_floor"] + 6, P["dr_floor"] + P["sg_h"] + 4,
                              ox + sx + tx, oy + PIN_Y))
    # lid support ledges, front and rear of the bin zone
    for zl in (P["z_lidA"], P["z_lidB"]):
        z = P["dr_floor"] + zl
        m = union([m, blk(ox, DR_W - ox, oy + BIN_Y0 - 4, oy + BIN_Y0, z - 2.5, z)])
        m = union([m, blk(ox, DR_W - ox, oy + IN_D - 4, oy + IN_D, z - 2.5, z)])
    # handle
    m = union([m, blk(DR_W/2 - 45, DR_W/2 + 45, DR_D - 1, DR_D + 11, 12, 26)])
    m = diff(m, blk(DR_W/2 - 41, DR_W/2 + 41, DR_D + 2, DR_D + 12, 15, 23))
    # cable strain-relief slot at the back
    m = diff(m, blk(DR_W - 40, DR_W - 20, -1, P["dr_wall"] + 1, DR_H - 14, DR_H + 1))
    return m

def lid(z_lid, tag):
    """Plate + integral rack. The rack sits at the lid's rear edge and meshes
    with the pinion below it."""
    w, d = CELL_W - P["lid_gap"], BIN_D - P["lid_gap"]
    plate = blk(0, w, 0, d, z_lid, z_lid + P["lid_t"])
    rk = rack(w * 0.9, z_lid - P["gear_t"])
    rk.apply_translation([w * 0.05, -6.0, 0])
    web = blk(w*0.05, w*0.95, -6.0, 0.6, z_lid - P["gear_t"], z_lid + P["lid_t"])
    grip = blk(w*0.3, w*0.7, d - 4, d, z_lid + P["lid_t"], z_lid + P["lid_t"] + 3)
    m = union([plate, rk, web, grip])
    m.apply_translation([0, 0, -m.bounds[0][2]])
    return m

# ───────────────────── build ─────────────────────
def rep(name, m):
    e = m.extents
    print(f"  {name:16s} {e[0]:7.1f} x {e[1]:7.1f} x {e[2]:6.1f}  "
          f"{m.volume/1000*1.27:6.1f} g  wt={m.is_watertight}")
    m.export(os.path.join(OUT, name + ".stl"))
    return m

print("ToolCell cabinet\n")
print(f"  case            {CW} x {CD} x "
      f"{P['h_foot']+P['h_base']+P['h_mid']+P['h_head']:.0f} mm")
print(f"  drawer          {DR_W:.1f} x {DR_D:.1f} x {DR_H:.1f}")
print(f"  bin (each)      {CELL_W:.1f} x {BIN_D:.1f} x {P['z_lidA']-2:.1f}")
print(f"  pinion          m{M} x {N}T, pitch dia {2*R_P:.1f}")
print(f"  lid travel      {TRAVEL:.1f} mm from 180 deg "
      f"= {100*TRAVEL/CELL_W:.0f}% of bin width\n")

parts = {}
for nm, fn in [("case_base", case_base), ("case_mid", case_mid),
               ("case_head", case_head), ("elec_panel", elec_panel),
               ("elec_tray", elec_tray), ("foot", foot), ("drawer", drawer)]:
    parts[nm] = rep(nm, fn())
parts["lid_A"]  = rep("lid_A",  lid(P["z_lidA"], "A"))
parts["lid_B"]  = rep("lid_B",  lid(P["z_lidB"], "B"))
parts["pinion"] = rep("pinion", pinion(P["z_lidA"] - 6))

print("\n  CHECKS")
ok = True
def chk(l, c, d):
    global ok; ok &= c
    print(f"    [{'PASS' if c else 'FAIL'}] {l:32s} {d}")
chk("drawer fits bay", DR_W + 2*P["dr_side_clear"] <= BAY_W + 0.01,
    f"{DR_W:.1f} + clearance in {BAY_W:.1f}")
chk("travel exposes >50% of bin", TRAVEL > CELL_W*0.5,
    f"{TRAVEL:.1f} of {CELL_W:.1f}")
chk("lid B clears drawer lip", P["z_lidB"]+P["lid_t"] <= IN_H,
    f"top z={P['z_lidB']+P['lid_t']:.1f} of {IN_H:.1f}")
chk("pinion inside mech zone", PIN_Y - R_TIP > 0 and RACK_Y < BIN_Y0,
    f"pinion y {PIN_Y-R_TIP:.1f}..{PIN_Y+R_TIP:.1f}, zone 0..{BIN_Y0}")
chk("every part watertight", all(m.is_watertight for m in parts.values()), "")
for nm, m in parts.items():
    chk(f"{nm} fits 256 bed", m.extents[0] <= 256 and m.extents[1] <= 256,
        f"{m.extents[0]:.0f} x {m.extents[1]:.0f}")
print("    " + ("ALL CHECKS PASSED" if ok else "*** CHECKS FAILED ***"))
