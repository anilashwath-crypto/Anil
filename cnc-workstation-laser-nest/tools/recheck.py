"""Robust thickness: for every planar-face normal, measure the solid's extent along it
and test whether the solid is a prism in that direction (vol == projected area x extent)."""
import math
from common import *
from OCP.TopAbs import TopAbs_VERTEX
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

solids = load_solids()

def verts(s):
    out=[]
    ex=TopExp_Explorer(s, TopAbs_VERTEX)
    while ex.More():
        p=BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current())); out.append((p.X(),p.Y(),p.Z())); ex.Next()
    return out

def planar_normals(s):
    """unique planar-face normals (as +/- canonical dirs) with total face area per direction"""
    acc={}
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            n=ad.Plane().Axis().Direction(); d=(n.X(),n.Y(),n.Z())
            if d[0]<-1e-9 or (abs(d[0])<1e-9 and (d[1]<-1e-9 or (abs(d[1])<1e-9 and d[2]<0))):
                d=(-d[0],-d[1],-d[2])                       # canonical hemisphere
            key=tuple(round(v,6) for v in d)
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g)
            acc[key]=acc.get(key,0.0)+g.Mass()
        fe.Next()
    return acc

print(f"{'id':>3} {'name':<8} {'true thk':>9} {'proj area cm2':>14} {'prismatic':>10}   note")
rows=[]
import json
names=json.load(open('bodies.json'))
for i,s in enumerate(solids):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); vol=g.Mass()
    V=verts(s); best=None
    for d,area in planar_normals(s).items():
        proj=[v[0]*d[0]+v[1]*d[1]+v[2]*d[2] for v in V]
        t=max(proj)-min(proj)
        if t < 0.05: continue
        # a prism along d has vol == (face area on one side) * t; face area per side ~= area/2 only
        # if the two end caps dominate -- so test directly against vol/t
        A = vol/t
        # the end-cap area in this direction must be >= A (equality when prismatic)
        err = abs(area/2 - A)/A          # area/2 ~ one end cap when caps dominate planar area
        if best is None or t < best[0]:
            best=(t, A, err, d)
    t,A,err,d = best
    prism = err < 0.10
    note = ""
    if abs(t-5.0)<0.05: note="<-- 5 mm PLATE"
    rows.append((i, names[str(i)]['name'], t, A/100, prism, d, vol))
    print(f"{i:>3} {names[str(i)]['name']:<8} {t:>9.2f} {A/100:>14.1f} {str(prism):>10}   {note}")

five=[r for r in rows if abs(r[2]-5.0)<0.05]
print(f"\nbodies whose SMALLEST extent is 5.00 mm: {len(five)} -> {[r[1] for r in five]}")
