#!/usr/bin/env python3
"""
shopkeeper — motorised drawer cabinet.

Each drawer is driven OUT by its own SG90 through a rack and pinion. Type a
PIN and the drawer you are cleared for slides itself open. the commercial equivalent
tier only *releases* a drawer and you pull it; this one opens.

    head            45   4x4 keypad, 0.91" OLED, tablet cradle
    drawer bay A    76   motorised drawer
    drawer bay B    76   motorised drawer
    electronics     50   ESP32-S3, 5 V supply, terminal blocks
    feet            12
                   ---
                   259 mm tall, 216 x 136 footprint

DRIVE
    A toothed fin hangs from the drawer's underside through a slot in the bay
    deck. A vertical-shaft SG90 sits under the deck with a 24-tooth pinion on
    it. 180 deg of servo = 56.5 mm of drawer travel.

    Nothing rises above the cabinet and the drawer cannot escape - at full
    travel 69 mm of a 126 mm drawer is still captured by the bay.
"""
import os, math
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, extrude_polygon
from shapely.geometry import Polygon
from mf3 import write_3mf, verify

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "out2")
os.makedirs(OUT, exist_ok=True)

P = dict(
    cw=216.0, cd=136.0, wall=3.0,
    h_base=50.0, h_bay=81.0, h_head=45.0, h_foot=12.0,
    lip=3.0,
    deck_z=28.0, deck_t=3.0,          # deck the drawer rides on
    dr_wall=2.5, dr_h=45.0, dr_floor=2.5,
    side_clear=2.0, front=5.0,
    module=1.5, teeth=24, press=math.radians(20.0),
    gear_t=6.0, backlash=0.35,
    fin_t=4.0, fin_h=9.0,
    sg_l=22.8, sg_w=12.2, sg_h=22.7, sg_tab=32.2, sg_spline=4.8,
    clear=0.30,
)
M, N = P["module"], P["teeth"]
R_P, PITCH = M*N/2, math.pi*M
R_TIP, R_ROOT = R_P+M, R_P-1.25*M
TRAVEL = math.pi*R_P

CW, CD, WL = P["cw"], P["cd"], P["wall"]
BAY_W, BAY_D = CW-2*WL, CD-WL
DR_W = BAY_W-2*P["side_clear"]
DR_D = BAY_D-7.0
DECK = P["deck_z"]+P["deck_t"]           # top of deck = drawer underside
FIN_X = 100.0                            # fin centre in drawer coords
PIN_X = FIN_X + P["fin_t"]/2 + R_P       # pinion centre
PIN_Y = 42.0
PIN_Z = DECK - P["fin_h"] + 1.0          # pinion bottom

def T(m,x=0,y=0,z=0): m.apply_translation([x,y,z]); return m
def blk(x0,x1,y0,y1,z0,z1):
    x0,x1=sorted((x0,x1)); y0,y1=sorted((y0,y1)); z0,z1=sorted((z0,z1))
    assert x1>x0 and y1>y0 and z1>z0, f"degenerate {x0,x1,y0,y1,z0,z1}"
    return T(box(extents=[x1-x0,y1-y0,z1-z0]),(x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
def cyl_z(d,z0,z1,x,y,s=64): return T(cylinder(radius=d/2,height=z1-z0,sections=s),x,y,(z0+z1)/2)
def cyl_y(d,y0,y1,x,z,s=48):
    c=cylinder(radius=d/2,height=y1-y0,sections=s)
    c.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2,[1,0,0]))
    return T(c,x,(y0+y1)/2,z)
def diff(a,b): return trimesh.boolean.difference([a,b],engine="manifold")
def union(p): return trimesh.boolean.union(p,engine="manifold")

def chamfer(m,c=4.0):
    s=c*math.sqrt(2); cuts=[]
    for (x,y) in ((0,0),(CW,0),(0,CD),(CW,CD)):
        b=box(extents=[s,s,900])
        b.apply_transform(trimesh.transformations.rotation_matrix(math.pi/4,[0,0,1]))
        cuts.append(T(b,x,y,0))
    return diff(m,union(cuts))

# ───────── gears ─────────
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
    hub=cyl_z(11.0,P["gear_t"],P["gear_t"]+7,0,0)
    m=union([g,hub])
    m=diff(m,cyl_z(P["sg_spline"]+0.35,-1,P["gear_t"]+4,0,0))
    m=diff(m,cyl_z(2.6,P["gear_t"]+4,P["gear_t"]+8,0,0))
    return m

def rack_fin(length):
    """Vertical fin, teeth on its +X face, hanging under the drawer."""
    h=P["fin_h"]; t=P["fin_t"]
    base=blk(0,t,0,length,0,h)
    tt=[]
    for i in range(int(length/PITCH)):
        yc=(i+0.5)*PITCH
        top=(PITCH/2-P["backlash"])/2
        bot=top+(M+1.25*M)*math.tan(P["press"])
        poly=Polygon([(t,yc-bot),(t+M+1.25*M,yc-top),
                      (t+M+1.25*M,yc+top),(t,yc+bot)])
        e=extrude_polygon(poly,h); tt.append(e)
    return union([base]+tt)

# ───────── shells ─────────
def shell(h,floor=True,top=False,lip_top=True,recess=True):
    m=diff(blk(0,CW,0,CD,0,h),
           blk(WL,CW-WL,WL,CD+1,WL if floor else -1,h-(WL if top else 0)+(0 if top else 1)))
    if lip_top: m=union([m,blk(WL+0.6,CW-WL-0.6,WL+0.6,CD-0.6,h,h+P["lip"])])
    if recess:  m=diff(m,blk(WL+0.3,CW-WL-0.3,WL+0.3,CD-0.3,-1,P["lip"]+0.3))
    return m

def case_bay():
    """Drawer bay: deck the drawer rides on, slot for the fin, servo well below."""
    m=shell(P["h_bay"])
    m=diff(m,blk(WL,CW-WL,-1,WL+1,WL,P["h_bay"]))                 # drawer mouth
    # deck
    m=union([m,blk(WL,CW-WL,WL,CD-WL,P["deck_z"],DECK)])
    # fin slot, front to back
    sx=WL+P["side_clear"]+P["dr_wall"]+FIN_X
    m=diff(m,blk(sx-P["fin_t"]/2-1.2,sx+P["fin_t"]/2+1.2,-1,CD-WL-6,P["deck_z"]-1,DECK+1))
    # pinion pocket + servo well under the deck
    px=WL+P["side_clear"]+P["dr_wall"]+PIN_X
    m=diff(m,cyl_z(2*R_TIP+3,WL,DECK+1,px,WL+PIN_Y))
    m=diff(m,blk(px-P["sg_l"]/2-P["clear"],px+P["sg_l"]/2+P["clear"],
                 WL+PIN_Y-P["sg_w"]/2-P["clear"],WL+PIN_Y+P["sg_w"]/2+P["clear"],
                 -1,P["deck_z"]))
    for tx in (-P["sg_tab"]/2+2.2,P["sg_tab"]/2-2.2):
        m=diff(m,cyl_z(1.7,4,P["deck_z"],px+tx,WL+PIN_Y))
    # drawer-closed switch: UNDER the deck, tripped by the rear of the fin.
    # It must not enter the drawer envelope - a boss in the bay interior blocks
    # the drawer from ever going in, which is exactly what the review caught.
    swy=CD-WL-26
    m=union([m,blk(sx-19,sx-5,swy,swy+14,WL,WL+16)])
    for dy in (4,10):
        m=diff(m,cyl_z(1.7,WL+3,WL+17,sx-12,swy+dy))
    # cable riser + side vents
    m=diff(m,blk(CW-34,CW-14,CD-WL-4,CD+1,-1,P["h_bay"]+4))
    for i in range(4):
        z=DECK+8+i*9
        if z+3<P["h_bay"]-8:
            for x in (-1,CW-WL-1):
                m=diff(m,blk(x,x+WL+2,CD*0.32,CD*0.70,z,z+3.2))
    return chamfer(m)

def case_base():
    m=shell(P["h_base"],recess=False)
    m=diff(m,blk(14,CW-14,-1,WL+1,10,P["h_base"]-8))
    for x in (9,CW-9):
        for z in (14,P["h_base"]-12): m=diff(m,cyl_y(2.6,-1,WL+1,x,z))
    m=diff(m,cyl_y(8.0,CD-WL-1,CD+1,40,26))
    m=diff(m,blk(60,74,CD-WL-1,CD+1,19,33))
    m=diff(m,blk(CW-34,CW-14,CD-WL-4,CD+1,26,P["h_base"]+4))
    for x in (26,CW-26):
        for y in (26,CD-30):
            m=union([m,cyl_z(8.0,WL,WL+4,x,y)]); m=diff(m,cyl_z(2.5,WL+1,WL+5,x,y))
    return chamfer(m)

def case_head():
    H=P["h_head"]
    m=shell(H,floor=False,top=True,lip_top=False)
    m=diff(m,blk(28,98,16,93,H-WL-1,H+1))
    m=union([m,blk(26,100,14,95,H-WL-1.2,H-WL)])
    m=diff(m,blk(28,98,16,93,H-WL-1.3,H+1))
    slot=blk(-60,60,-6,6,-30,30)
    slot.apply_transform(trimesh.transformations.rotation_matrix(math.radians(15),[1,0,0]))
    m=diff(m,T(slot,CW/2,CD-30,H-13))
    m=diff(m,blk(CW/2-13,CW/2+13,-1,WL+1,14,24))
    for dx in (-46,46): m=diff(m,cyl_y(5.2,-1,WL+1,CW/2+dx,19))
    for dx in (-16,16): m=union([m,blk(CW/2+dx-2,CW/2+dx+2,WL,WL+5,10,28)])
    m=diff(m,blk(CW-34,CW-14,CD-WL-4,CD+1,-1,18))
    return chamfer(m)

def elec_tray():
    w,d=CW-52,CD-56
    m=blk(0,w,0,d,0,3)
    for x in (0,w):
        for y in (0,d):
            m=union([m,cyl_z(9.0,0,3,x,y)]); m=diff(m,cyl_z(3.4,-1,4,x,y))
    for dx in (-24,24):
        for dy in (-10.5,10.5):
            m=union([m,cyl_z(6.0,3,8,44+dx,30+dy)]); m=diff(m,cyl_z(1.7,4,9,44+dx,30+dy))
    for cy in (18,46,74):
        for cx in (98,128,158):
            m=diff(m,blk(cx,cx+3,cy-5,cy+5,-1,4))
            m=diff(m,blk(cx+9,cx+12,cy-5,cy+5,-1,4))
    m=union([m,blk(96,168,12,80,3,6)])
    return m

def elec_panel():
    p=blk(0,CW-26,0,3,0,P["h_base"]-20)
    for x in (5,CW-31):
        for z in (5,P["h_base"]-25): p=diff(p,cyl_y(3.4,-1,4,x,z))
    return p

def foot(): return blk(0,22,0,22,0,P["h_foot"])

def drawer():
    W,D,H=DR_W,DR_D,P["dr_h"]
    m=diff(blk(0,W,0,D,0,H),
           blk(P["dr_wall"],W-P["dr_wall"],P["dr_wall"],D-P["front"],P["dr_floor"],H+1))
    # divider
    m=union([m,blk(W/2-1.5,W/2+1.5,P["dr_wall"],D-P["front"],P["dr_floor"],H-8)])
    # drive fin under the floor
    fin=rack_fin(D-24)
    fin.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[0,0,1]))
    fin.apply_translation(-fin.bounds[0])
    fin.apply_translation([FIN_X-P["fin_t"]/2,12,-P["fin_h"]])
    m=union([m,fin])
    # No skids. They previously hung below the floor and cut into the deck;
    # the floor runs on the deck directly, which is one less thing to get wrong.
    # handle
    m=union([m,blk(W/2-48,W/2+48,D-1,D+11,10,26)])
    m=diff(m,blk(W/2-44,W/2+44,D+2,D+12,13,23))
    m.apply_translation([0,0,P["fin_h"]])
    return m

# ───────── build ─────────
def rep(n,m):
    e=m.extents
    print(f"  {n:12s} {e[0]:7.1f} x {e[1]:7.1f} x {e[2]:6.1f}  {m.volume/1000*1.27:6.1f} g  wt={m.is_watertight}")
    m.export(os.path.join(OUT,n+".stl")); return m

H_TOT=P["h_foot"]+P["h_base"]+2*P["h_bay"]+P["h_head"]
print("shopkeeper — motorised drawer cabinet\n")
print(f"  cabinet     {CW:.0f} x {CD:.0f} x {H_TOT:.0f} mm")
print(f"  drawer      {DR_W:.1f} x {DR_D:.1f} x {P['dr_h']:.1f}  (x2)")
print(f"  travel      {TRAVEL:.1f} mm from 180 deg of SG90")
print(f"  captured    {DR_D-TRAVEL:.1f} mm of drawer still in the bay at full travel\n")

parts={}
for n,f in [("case_base",case_base),("case_bay",case_bay),("case_head",case_head),
            ("drawer",drawer),("pinion",pinion),("elec_tray",elec_tray),
            ("elec_panel",elec_panel),("foot",foot)]:
    parts[n]=rep(n,f())

print("\n  CHECKS"); ok=True
def chk(l,c,d):
    global ok; ok&=c; print(f"    [{'PASS' if c else 'FAIL'}] {l:34s} {d}")
chk("drawer fits bay width",DR_W+2*P["side_clear"]<=BAY_W+.01,f"{DR_W:.1f} in {BAY_W:.1f}")
chk("drawer cannot fall out",DR_D-TRAVEL>DR_D*0.45,f"{DR_D-TRAVEL:.1f} of {DR_D:.1f} captured")
chk("fin stays on the pinion",(DR_D-24)-TRAVEL>2*R_P*0.5,f"fin {DR_D-24:.0f} vs travel {TRAVEL:.1f}")
chk("drawer clears bay height",P["dr_h"]+DECK+2<=P["h_bay"],f"{P['dr_h']+DECK:.1f} of {P['h_bay']:.1f}")
chk("servo fits under deck",P["sg_h"]+WL<=P["deck_z"]+.01,f"{P['sg_h']+WL:.1f} of {P['deck_z']:.1f}")
chk("all watertight",all(m.is_watertight for m in parts.values()),"")
for n,m in parts.items():
    chk(f"{n} on 256 bed",m.extents[0]<=256 and m.extents[1]<=256,
        f"{m.extents[0]:.0f} x {m.extents[1]:.0f}")
print("    "+("ALL CHECKS PASSED" if ok else "*** CHECKS FAILED ***"))

# plates
PL=os.path.join(OUT,"plates"); os.makedirs(PL,exist_ok=True)
import glob
for f in glob.glob(os.path.join(PL,"*.3mf")): os.remove(f)
def land(m):
    m=m.copy(); m.apply_translation(-m.bounds[0])
    if m.extents[1]>m.extents[0]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,0,1]))
        m.apply_translation(-m.bounds[0])
    return m
L={k:land(v) for k,v in parts.items()}
SETS=[("1_bay_A",[("case_bay",1)]),("2_bay_B",[("case_bay",1)]),
      ("3_base",[("case_base",1)]),("4_head",[("case_head",1)]),
      ("5_drawers",[("drawer",2)]),
      ("6_gears_trim",[("pinion",2),("elec_tray",1),("elec_panel",1),("foot",4)])]
print("\n  PLATES"); tot=0
for lab,items in SETS:
    placed,x,y,row=[],6.,6.,0.
    for n,q in items:
        m=L[n]
        for i in range(q):
            w,d=m.extents[0],m.extents[1]
            if x+w>250: x=6.; y+=row+6.; row=0.
            placed.append((n if q==1 else f"{n}_{i+1}",m,x,y)); x+=w+6.; row=max(row,d)
    g=sum(m.volume/1000*1.27 for _,m,_,_ in placed); tot+=g
    p=os.path.join(PL,f"plate_{lab}.3mf"); write_3mf(p,placed); o,b=verify(p)
    print(f"    plate_{lab:13s} {len(placed)} obj  {g:6.1f} g  ok={o==b}")
print(f"\n  6 plates, {tot:.0f} g solid (~{tot*.85:.0f} g sliced)")
print(f"  {os.path.normpath(PL)}")
