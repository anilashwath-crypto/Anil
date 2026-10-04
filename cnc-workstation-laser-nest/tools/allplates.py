"""Take EVERY flat plate except the 10 mm one, re-cut its profile in 5 mm stock, nest it."""
import math, json, numpy as np
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism

EXCLUDE_10MM = 11          # Body12, excluded on request
BENT = {1, 13, 14, 15, 16} # 1.5 mm bent sheet - cannot be made from 5 mm stock
STOCK = 5.0

solids = load_solids(); names = json.load(open('bodies.json'))

def plate_dir(s):
    """normal of the prismatic axis, choosing the direction of SMALLEST extent."""
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.BRep import BRep_Tool
    V=[]
    ex=TopExp_Explorer(s, TopAbs_VERTEX)
    while ex.More():
        p=BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current())); V.append((p.X(),p.Y(),p.Z())); ex.Next()
    dirs={}
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            n=ad.Plane().Axis().Direction(); d=(n.X(),n.Y(),n.Z())
            if d[0]<-1e-9 or (abs(d[0])<1e-9 and (d[1]<-1e-9 or (abs(d[1])<1e-9 and d[2]<0))):
                d=(-d[0],-d[1],-d[2])
            dirs[tuple(round(v,6) for v in d)]=1
        fe.Next()
    best=None
    for d in dirs:
        pr=[v[0]*d[0]+v[1]*d[1]+v[2]*d[2] for v in V]
        t=max(pr)-min(pr)
        if t>0.05 and (best is None or t<best[0]): best=(t,d)
    return best

sel=[i for i in range(len(solids)) if i!=EXCLUDE_10MM and i not in BENT]
print("plates to nest:", [(i, names[str(i)]['name']) for i in sel])

def norm(s):
    xmin,ymin,zmin,*_=bbox(s); t=gp_Trsf(); t.SetTranslation(gp_Vec(-xmin,-ymin,-zmin)); return transform(s,t)

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

blanks={}
print(f"\n{'body':<8} {'source thk':>11} {'stock thk':>10} {'profile':>18} {'note'}")
for i in sel:
    t,d = plate_dir(solids[i])
    flat = norm(transform(solids[i], lay_flat_trsf(d)))
    face = bottom_face(flat)
    solid = BRepPrimAPI_MakePrism(face, gp_Vec(0,0,STOCK)).Shape()   # re-cut in 5 mm stock
    solid = norm(solid)
    blanks[i]=solid
    xmin,ymin,_,xmax,ymax,_=bbox(solid)
    note = "" if abs(t-STOCK)<0.05 else f"RE-THICKNESSED {t:.0f} -> {STOCK:.0f} mm"
    print(f"{names[str(i)]['name']:<8} {t:>10.1f}m {STOCK:>9.1f}m {xmax-xmin:>8.0f} x {ymax-ymin:<7.0f} {note}")

tot=0
for i,s in blanks.items():
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); tot += g.Mass()/STOCK
print(f"\ntotal net cut area: {tot/1e6:.3f} m2   (one 2440x1220 sheet = 2.977 m2)")
import pickle; pickle.dump(sel, open('sel.pkl','wb'))
