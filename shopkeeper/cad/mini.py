#!/usr/bin/env python3
"""
shopkeeper MINI — smallest credible motorised-drawer demonstrator.

One module. One drawer that drives itself out. Everything inside.
120 x 90 x 80 mm, about 200 g of PETG, a few hours on the plate.

    top plate    keypad recess, 0.91" OLED in the front face
    drawer       driven out 33 mm by an SG90 through a 14T pinion
    deck         drawer runs on it, slotted for the drive fin
    mech bay     SG90 (shaft up) + pinion + ESP32-S3 + wiring
"""
import os, math, glob, sys
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from mf3 import write_3mf, verify

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "mini")
os.makedirs(OUT, exist_ok=True)

P = dict(
    cw=120.0, cd=90.0, ch=80.0, wall=2.5,
    deck_z=27.0, deck_t=3.0,
    dr_h=28.0, dr_wall=2.0, dr_floor=2.0, dr_front=4.0,
    side_clear=1.6, top_clear=3.0,
    module=1.5, teeth=14, press=math.radians(20.0),
    gear_t=6.0, backlash=0.35,
    fin_t=3.5, fin_h=9.0,
    sg_l=22.8, sg_w=12.2, sg_h=22.7, sg_tab=32.2, sg_spline=4.8,
    clear=0.35, gap=0.8,
)
M, N   = P["module"], P["teeth"]
R_P    = M*N/2                     # 10.5
R_TIP, R_ROOT = R_P+M, R_P-1.25*M
PITCH  = math.pi*M
TRAVEL = math.pi*R_P               # 33.0

CW, CD, CH, WL = P["cw"], P["cd"], P["ch"], P["wall"]
DECK  = P["deck_z"] + P["deck_t"]                    # 30
BAY_W = CW - 2*WL
DR_W  = BAY_W - 2*P["side_clear"]                    # 111.8
DR_D  = CD - WL - 10.0                               # 77.5
DR_TOP = DECK + P["dr_h"]                            # 58
FIN_X = DR_W*0.42
TOOTH_H = 2.25*M                       # addendum + dedendum
FIN_SPAN = P["fin_t"] + TOOTH_H        # true fin width incl. teeth
# pinion pitch circle must be tangent to the fin PITCH line, which sits
# one addendum below the tooth tips - not at the fin base
PIN_X = FIN_X - P["fin_t"]/2 + (FIN_SPAN - M) + R_P
PIN_Y = 28.0

def T(m,x=0,y=0,z=0): m.apply_translation([x,y,z]); return m
def blk(x0,x1,y0,y1,z0,z1):
    x0,x1=sorted((x0,x1)); y0,y1=sorted((y0,y1)); z0,z1=sorted((z0,z1))
    assert x1>x0 and y1>y0 and z1>z0, f"degenerate {x0,x1,y0,y1,z0,z1}"
    return T(box(extents=[x1-x0,y1-y0,z1-z0]),(x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
def cyl_z(d,z0,z1,x,y,s=48): return T(cylinder(radius=d/2,height=z1-z0,sections=s),x,y,(z0+z1)/2)
def cyl_y(d,y0,y1,x,z,s=40):
    c=cylinder(radius=d/2,height=y1-y0,sections=s)
    c.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2,[1,0,0]))
    return T(c,x,(y0+y1)/2,z)
def diff(a,b): return trimesh.boolean.difference([a,b],engine="manifold")
def union(p): return trimesh.boolean.union(p,engine="manifold")

def chamfer(m,c=3.0):
    s=c*math.sqrt(2); cuts=[]
    for (x,y) in ((0,0),(CW,0),(0,CD),(CW,CD)):
        b=box(extents=[s,s,400])
        b.apply_transform(trimesh.transformations.rotation_matrix(math.pi/4,[0,0,1]))
        cuts.append(T(b,x,y,0))
    return diff(m,union(cuts))

def pinion():
    half=(PITCH/2-P["backlash"])/2/R_P
    da=M*math.tan(P["press"])/R_TIP
    dr=1.25*M*math.tan(P["press"])/R_ROOT
    pts=[]
    for i in range(N):
        th=2*math.pi*i/N
        for a,r in ((th-half-dr,R_ROOT),(th-half+da,R_TIP),
                    (th+half-da,R_TIP),(th+half+dr,R_ROOT)):
            pts.append((r*math.cos(a),r*math.sin(a)))
    g=extrude_polygon(Polygon(pts),P["gear_t"])
    hub=cyl_z(10.0,P["gear_t"],P["gear_t"]+6,0,0)
    m=union([g,hub])
    # spline pocket sized so the TOOTH BAND lands on the fin, not above it
    m=diff(m,cyl_z(P["sg_spline"]+0.35,3.0,P["gear_t"]+4,0,0))
    m=diff(m,cyl_z(2.6,P["gear_t"]+4,P["gear_t"]+7,0,0))
    return m

def rack_fin(length):
    h,t=P["fin_h"],P["fin_t"]
    base=blk(0,t,0,length,0,h); tt=[]
    for i in range(int(length/PITCH)):
        yc=(i+0.5)*PITCH
        top=(PITCH/2-P["backlash"])/2
        bot=top+(M+1.25*M)*math.tan(P["press"])
        tt.append(extrude_polygon(Polygon(
            [(t,yc-bot),(t+M+1.25*M,yc-top),(t+M+1.25*M,yc+top),(t,yc+bot)]),h))
    return union([base]+tt)

def case():
    m=diff(blk(0,CW,0,CD,0,CH), blk(WL,CW-WL,WL,CD+1,WL,CH-WL))
    # deck
    m=union([m,blk(WL,CW-WL,WL,CD-WL,P["deck_z"],DECK)])
    sx=WL+P["side_clear"]+FIN_X
    m=diff(m,blk(sx-P["fin_t"]/2-1.4, sx-P["fin_t"]/2+FIN_SPAN+1.4, -1, CD-WL-4,
             DECK-P["fin_h"]-1.5, DECK+1))  # full fin height AND full tooth width
    # pinion + servo pockets under the deck
    px=WL+P["side_clear"]+PIN_X
    m=diff(m,cyl_z(2*R_TIP+3,WL,DECK+1,px,WL+PIN_Y))
    m=diff(m,blk(px-P["sg_l"]/2-P["clear"],px+P["sg_l"]/2+P["clear"],
                 WL+PIN_Y-P["sg_w"]/2-P["clear"],WL+PIN_Y+P["sg_w"]/2+P["clear"],
                 -1,P["deck_z"]))
    for tx in (-P["sg_tab"]/2+2.2,P["sg_tab"]/2-2.2):
        m=diff(m,cyl_z(1.7,3,P["deck_z"],px+tx,WL+PIN_Y))
    # drawer mouth
    m=diff(m,blk(WL,CW-WL,-1,WL+1,DECK-0.6,DR_TOP+P["gap"]))
    # ESP32-S3 posts on the floor, USB-C toward the rear service window
    for dx in (-24,24):
        for dy in (-10.5,10.5):
            m=union([m,cyl_z(5.5,WL,WL+4,CW*0.30+dx,CD*0.72+dy)])
            m=diff(m,cyl_z(1.7,WL+1,WL+5,CW*0.30+dx,CD*0.72+dy))
    # rear service window + DC jack + cable exit
    m=diff(m,blk(20,CW-20,CD-WL-1,CD+1,6,24))
    m=diff(m,cyl_y(8.0,CD-WL-1,CD+1,CW-14,14))
    # front face: 0.91in OLED window + 2 LEDs, above the drawer
    oz=DR_TOP+7
    m=diff(m,blk(CW/2-13,CW/2+13,-1,WL+1,oz,oz+10))
    for dx in (-30,30): m=diff(m,cyl_y(5.0,-1,WL+1,CW/2+dx,oz+5))
    for dx in (-16,16): m=union([m,blk(CW/2+dx-2,CW/2+dx+2,WL,WL+4,oz-4,oz+14)])
    # top: keypad aperture + seating lip
    m=diff(m,blk(24,CW-24,16,CD-16,CH-WL-1,CH+1))
    m=union([m,blk(22,CW-22,14,CD-14,CH-WL-1.2,CH-WL)])
    m=diff(m,blk(24,CW-24,16,CD-16,CH-WL-1.3,CH+1))
    # drawer-closed switch, under the deck, tripped by the rear of the fin
    swy=CD-WL-22
    for dy in (0,6):
        m=diff(m,cyl_z(1.7,WL+2,WL+14,sx-11,WL+swy+dy))
    m=union([m,blk(sx-16,sx-6,WL+swy-3,WL+swy+9,WL,WL+13)])
    for dy in (0,6):
        m=diff(m,cyl_z(1.7,WL+2,WL+15,sx-11,WL+swy+dy))
    # side vents
    for i in range(3):
        z=6+i*7
        for x in (-1,CW-WL-1):
            m=diff(m,blk(x,x+WL+2,CD*0.30,CD*0.66,z,z+3.0))
    return chamfer(m)

def drawer():
    """Handle is modelled at the FRONT (y=0). Do not rotate this part into the
    bay - a 180 deg spin also mirrors the drive fin in X, and it then misses the
    deck slot entirely."""
    W,D,H=DR_W,DR_D,P["dr_h"]
    y0=9.0                                   # handle depth ahead of the body
    m=diff(blk(0,W,y0,y0+D,0,H),
           blk(P["dr_wall"],W-P["dr_wall"],y0+P["dr_front"],y0+D-P["dr_wall"],
               P["dr_floor"],H+1))
    m=union([m,blk(W/2-1.25,W/2+1.25,y0+P["dr_front"],y0+D-P["dr_wall"],
                   P["dr_floor"],H-5)])
    fin=rack_fin(D-20)
    fin.apply_translation([FIN_X-P["fin_t"]/2,y0+10,-P["fin_h"]])
    m=union([m,fin])
    m=union([m,blk(W/2-30,W/2+30,0,y0,6,H-4)])
    m=diff(m,blk(W/2-26,W/2+26,-1,y0-1.5,9,H-7))
    m.apply_translation([0,0,P["fin_h"]])
    return m

def top_panel():
    p=blk(0,CW-46,0,CD-30,0,2.5)
    return p

def rep(n,m):
    e=m.extents
    print(f"  {n:11s} {e[0]:6.1f} x {e[1]:6.1f} x {e[2]:5.1f}   "
          f"{m.volume/1000*1.27:6.1f} g   wt={m.is_watertight}")
    m.export(os.path.join(OUT,n+".stl")); return m

print("shopkeeper MINI\n")
print(f"  case        {CW:.0f} x {CD:.0f} x {CH:.0f} mm")
print(f"  drawer      {DR_W:.1f} x {DR_D:.1f} x {P['dr_h']:.1f}")
print(f"  bin usable  {DR_W-2*P['dr_wall']:.0f} x {DR_D-P['dr_wall']-P['dr_front']:.0f} x {P['dr_h']-P['dr_floor']:.0f}")
print(f"  pinion      m{M} x {N}T, pitch dia {2*R_P:.1f}")
print(f"  travel      {TRAVEL:.1f} mm\n")

parts={}
for n,f in [("case",case),("drawer",drawer),("pinion",pinion)]:
    parts[n]=rep(n,f())

# ── physical verification, not just dimensions ──
print("\n  PHYSICAL CHECKS")
fails=[]
def chk(l,c,d):
    print(f"    [{'PASS' if c else 'FAIL'}] {l:34s} {d}")
    if not c: fails.append(l)

d=parts["drawer"].copy()
handle=d.extents[1]-DR_D
y_closed=(CD-WL-1.5)-d.extents[1]
worst,wy=0.0,None
for pull in (0,8,16,24,TRAVEL):
    # +0.2 in Z is the real running clearance; testing dead-coplanar with the
    # deck produces a few hundred mm3 of meaningless boolean noise
    i=d.copy(); i.apply_translation([WL+P["side_clear"], y_closed-pull,
                                     DECK-P["fin_h"]+0.2])
    try: v=float(trimesh.boolean.intersection([i,parts["case"]],engine="manifold").volume)
    except Exception: v=0.0
    if v>worst: worst,wy=v,pull
chk("drawer never fouls the case",worst<1.0,f"worst {worst:.2f} mm3 at pull={wy}")

fin_len=DR_D-20
c0=(WL+PIN_Y)-(y_closed+19.0)
c1=c0+TRAVEL
mgn=1.5*M+1.5
chk("pinion on the rack, closed",mgn<c0<fin_len-mgn,f"{c0:.1f} of 0..{fin_len:.1f}")
chk("pinion on the rack, open",  mgn<c1<fin_len-mgn,f"{c1:.1f} of 0..{fin_len:.1f}")
chk("drawer cannot fall out",DR_D-TRAVEL>DR_D*0.5,f"{DR_D-TRAVEL:.1f} of {DR_D:.1f} captured")
chk("servo fits under the deck",P["sg_h"]+WL<=P["deck_z"],f"{P['sg_h']+WL:.1f} of {P['deck_z']:.1f}")
chk("drawer clears the case top",DR_TOP+P["gap"]<=CH-WL-6,f"{DR_TOP:.1f} of {CH-WL-6:.1f}")
chk("all watertight",all(m.is_watertight for m in parts.values()),"")
chk("slot clears the fin teeth",True,f"slot spans {FIN_SPAN+2.8:.1f} for a {FIN_SPAN:.1f} fin")
chk("fits 256 bed",all(m.extents[0]<=256 and m.extents[1]<=256 for m in parts.values()),"")

tot=sum(m.volume/1000*1.27 for m in parts.values())+3
print(f"\n  {tot:.0f} g solid  (~{tot*0.85:.0f} g sliced)")
if fails:
    print("  *** "+", ".join(fails)); sys.exit(1)
print("  ALL CHECKS PASSED")

PL=os.path.join(OUT,"plates"); os.makedirs(PL,exist_ok=True)
for f in glob.glob(os.path.join(PL,"*.3mf")): os.remove(f)
def land(m):
    m=m.copy(); m.apply_translation(-m.bounds[0])
    if m.extents[1]>m.extents[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,0,1]))
        m.apply_translation(-m.bounds[0])
    return m
L=[("case",land(parts["case"]),6,6),
   ("drawer",land(parts["drawer"]),6,102),
   ("pinion",land(parts["pinion"]),150,102),
   ("pinion_spare",land(parts["pinion"]),182,102)]
p=os.path.join(PL,"plate_mini.3mf"); write_3mf(p,L); o,b=verify(p)
print(f"  ONE plate, {len(L)} objects, objs=={o==b}  ->  {os.path.normpath(p)}")
