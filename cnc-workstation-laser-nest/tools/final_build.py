"""Build placed solids from a layout, verify exactly, export STEP + transforms."""
import math, json, os, sys
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRepTools import BRepTools
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static
from OCP.BRep import BRep_Builder

LAYOUT=sys.argv[1] if len(sys.argv)>1 else 'layout_profile.json'
TAG=sys.argv[2] if len(sys.argv)>2 else 'PROFILE'
OUT="out"; os.makedirs(OUT, exist_ok=True)
cfg=json.load(open(LAYOUT)); SW,SH=cfg['sheet']; MARGIN=cfg['margin']; GAP=cfg['gap']
layout={l['id']:l for l in cfg['layout']}
solids=load_solids(); bodies=json.load(open('bodies.json'))

def norm_trsf(s):
    xmin,ymin,zmin,*_=bbox(s); t=gp_Trsf(); t.SetTranslation(gp_Vec(-xmin,-ymin,-zmin)); return t

placed={}; comp_trsf={}
for i,s in enumerate(solids):
    if i not in layout: continue
    L=layout[i]
    T = lay_flat_trsf(L.get('normal') or plate_axis(s)[2])
    cur = transform(s, T)
    t2 = norm_trsf(cur); cur = transform(cur, t2); T = t2.Multiplied(T)
    rot = L.get('rot', 90 if L.get('rot90') else 0)
    if rot:
        r=gp_Trsf(); r.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), math.radians(rot))
        cur = transform(cur, r); T = r.Multiplied(T)
        t3 = norm_trsf(cur); cur = transform(cur, t3); T = t3.Multiplied(T)
    tr=gp_Trsf(); tr.SetTranslation(gp_Vec(L['x'], L['y'], 0.0))
    cur = transform(cur, tr); T = tr.Multiplied(T)
    placed[i]=cur; comp_trsf[i]=T

def bottom_face(s):
    c=[]
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane and abs(abs(ad.Plane().Axis().Direction().Z())-1)<1e-6:
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g)
            c.append((ad.Plane().Location().Z(), g.Mass(), f))
        fe.Next()
    zl=min(x[0] for x in c)
    return max([x for x in c if abs(x[0]-zl)<1e-4], key=lambda x:x[1])[2]

print(f"=== exact verification of {LAYOUT} ===")
faces={i:bottom_face(s) for i,s in placed.items()}
ok=True
# 1. flatness / thickness / sheet containment
for i,s in sorted(placed.items()):
    xmin,ymin,zmin,xmax,ymax,zmax=bbox(s); th=zmax-zmin
    inside = (xmin>=MARGIN-1e-3 and ymin>=MARGIN-1e-3 and
              xmax<=SW-MARGIN+1e-3 and ymax<=SH-MARGIN+1e-3)
    flat = abs(th-5.0)<1e-3 and abs(zmin)<1e-3
    if not (inside and flat): ok=False
    print(f" body {i:>2} ({bodies[str(i)]['name']:<7}) x[{xmin:7.1f},{xmax:7.1f}] y[{ymin:6.1f},{ymax:6.1f}] "
          f"thk {th:.3f}  {'in-sheet' if inside else 'OUT OF SHEET'}  {'flat' if flat else 'NOT FLAT'}")
# 2. pairwise overlap (boolean common of footprints) and clearance (wire distance)
print("\n pairwise checks (overlap area must be 0, clearance must be >= %.0f mm):" % GAP)
ids=sorted(placed); worst=1e9
for a in range(len(ids)):
    for b in range(a+1, len(ids)):
        i,j=ids[a],ids[b]
        cm=BRepAlgoAPI_Common(faces[i], faces[j]); cm.Build()
        g=GProp_GProps(); BRepGProp.SurfaceProperties_s(cm.Shape(), g); area=g.Mass()
        d=BRepExtrema_DistShapeShape(BRepTools.OuterWire_s(faces[i]), BRepTools.OuterWire_s(faces[j]))
        d.Perform(); dist=d.Value()
        worst=min(worst, dist)
        bad = area>1e-6 or dist<GAP-1e-3
        if bad: ok=False
        if bad or dist < GAP+2:
            print(f"   {i:>2} vs {j:<2}: overlap {area:.4f} mm2, clearance {dist:7.3f} mm  {'<-- FAIL' if bad else ''}")
print(f"\n minimum clearance anywhere on the sheet: {worst:.3f} mm")
print(" RESULT:", "PASS - layout is manufacturable" if ok else "FAIL")
if not ok: sys.exit(1)

def write_step(shapes, path, name):
    Interface_Static.SetCVal_s("write.step.product.name", name)
    w=STEPControl_Writer(); b=BRep_Builder(); c=TopoDS_Compound(); b.MakeCompound(c)
    for s in shapes: b.Add(c,s)
    w.Transfer(c, STEPControl_AsIs)
    assert w.Write(path)==IFSelect_RetDone
    print(f"  wrote {path} ({len(shapes)} bodies, {os.path.getsize(path)/1024:.0f} KB)")

print()
for si in range(cfg['n_sheets']):
    ids_s=[i for i in placed if layout[i]['sheet']==si]
    suffix = f"_Sheet{si+1}" if cfg['n_sheets']>1 else ""
    write_step([placed[i] for i in ids_s], f"{OUT}/CNC_Workstation_5mm_NEST{suffix}.step",
               f"5mm laser nest{suffix}")

# transforms for the Fusion 360 script (Fusion API works in cm)
tf={}
for i,T in comp_trsf.items():
    m=[[T.Value(r,c) for c in range(1,5)] for r in range(1,4)]
    tf[bodies[str(i)]['name']]=dict(
        body_index=i, sheet=layout[i]['sheet'],
        vol_mm3=bodies[str(i)]['vol_mm3'],
        centroid_mm=[bodies[str(i)]['cx'], bodies[str(i)]['cy'], bodies[str(i)]['cz']],
        matrix_mm=[m[0],m[1],m[2]])
json.dump(dict(sheet=[SW,SH], thickness=5.0, margin=MARGIN, gap=GAP,
               n_sheets=cfg['n_sheets'], transforms=tf), open(f'{OUT}/nest_transforms.json','w'), indent=1)
print(f"  wrote {OUT}/nest_transforms.json ({len(tf)} bodies)")
