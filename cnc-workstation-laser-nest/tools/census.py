import math, json
from common import *
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

solids=load_solids(); names=json.load(open('bodies.json'))

def wall(s):
    """separation of the dominant opposed parallel planar face pair (sheet thickness for bent parts)"""
    pl=[]
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            p=ad.Plane(); n=p.Axis().Direction()
            from OCP.TopAbs import TopAbs_REVERSED
            if f.Orientation()==TopAbs_REVERSED: n=n.Reversed()
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g)
            d=(n.X(),n.Y(),n.Z()); L=p.Location()
            pl.append((g.Mass(), d, L.X()*d[0]+L.Y()*d[1]+L.Z()*d[2]))
        fe.Next()
    best=None
    for a,da,oa in pl:
        for b,db,ob in pl:
            if da[0]*db[0]+da[1]*db[1]+da[2]*db[2] < -0.9999:
                t=oa+ob
                if t>0.01 and (best is None or min(a,b)>best[1]): best=(t,min(a,b))
    return best

def bends(s):
    """count cylindrical faces that look like sheet-metal bend radii"""
    n=0
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Cylinder and ad.Cylinder().Radius() < 25: n+=1
        fe.Next()
    return n

print(f"{'id':>3} {'name':<8} {'material':>9} {'kind':<22} {'flat size / developed':<26} {'bends':>5}")
FLAT5=[0,5,6,8,9,10,12]
for i,s in enumerate(solids):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); vol=g.Mass()
    xmin,ymin,zmin,xmax,ymax,zmax = bbox(s)
    dims=sorted([xmax-xmin, ymax-ymin, zmax-zmin])
    w=wall(s); t=w[0]
    if i in FLAT5:
        kind="flat plate"; size=f"{dims[2]:.0f} x {dims[1]:.0f} mm"; mat=f"{t:.1f} mm"
    else:
        # prismatic?
        prism = abs(vol - w[1]*t)/vol < 0.06
        nb=bends(s)
        if prism:
            kind="flat plate"; size=f"{dims[2]:.0f} x {dims[1]:.0f} mm"; mat=f"{t:.1f} mm"
        else:
            kind=f"BENT sheet ({nb} bend faces)"; size=f"~{vol/t/100:.0f} cm2 developed"; mat=f"{t:.1f} mm"
    mark = "  <-- IN THE NEST" if i in FLAT5 else ""
    print(f"{i:>3} {names[str(i)]['name']:<8} {mat:>9} {kind:<22} {size:<26} {'':>5}{mark}")

print()
from collections import Counter
c=Counter()
for i,s in enumerate(solids):
    c[round(wall(s)[0],1)] += 1
print("material thickness census:", dict(sorted(c.items())))
