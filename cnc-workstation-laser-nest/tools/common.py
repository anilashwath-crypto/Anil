import math
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_REVERSED, TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence
from OCP.gp import gp_Trsf, gp_Ax3, gp_Pnt, gp_Dir, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

STEPFILE="/root/.claude/uploads/0e09e0c2-1227-5643-b121-27ab532564bc/df5481a8-CNC_WorkstationV1.step.step"

def load_solids():
    doc = TDocStd_Document(TCollection_ExtendedString("d"))
    r = STEPCAFControl_Reader(); r.SetNameMode(True)
    assert r.ReadFile(STEPFILE) == IFSelect_RetDone
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labs = TDF_LabelSequence(); st.GetFreeShapes(labs)
    shape = st.GetShape_s(labs.Value(1))
    out=[]
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        out.append(TopoDS.Solid_s(ex.Current())); ex.Next()
    return out

def plate_axis(s):
    """Return (thickness, area, normal_dir_tuple) of dominant opposite planar face pair."""
    planes=[]
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            pl=ad.Plane(); n=pl.Axis().Direction()
            if f.Orientation()==TopAbs_REVERSED: n=n.Reversed()
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g)
            d=(n.X(),n.Y(),n.Z())
            L=pl.Location()
            planes.append((g.Mass(), d, L.X()*d[0]+L.Y()*d[1]+L.Z()*d[2]))
        fe.Next()
    best=None
    for a_,da,oa in planes:
        for b_,db,ob in planes:
            if da[0]*db[0]+da[1]*db[1]+da[2]*db[2] < -0.9999:
                t=oa+ob
                if t<=0.01: continue
                pa=min(a_,b_)
                if best is None or pa>best[1]: best=(t,pa,da)
    return best

def transform(s, trsf):
    return BRepBuilderAPI_Transform(s, trsf, True).Shape()

def lay_flat_trsf(normal):
    """gp_Trsf rotating `normal` onto +Z about origin."""
    n=gp_Dir(*normal)
    t=gp_Trsf()
    if n.IsEqual(gp_Dir(0,0,1), 1e-7): return t
    if n.IsOpposite(gp_Dir(0,0,1), 1e-7):
        t.SetRotation(gp_Ax1_X(), math.pi); return t
    ax = gp_Vec(n.X(),n.Y(),n.Z()).Crossed(gp_Vec(0,0,1))
    from OCP.gp import gp_Ax1
    t.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(ax)), gp_Vec(n.X(),n.Y(),n.Z()).Angle(gp_Vec(0,0,1)))
    return t

def gp_Ax1_X():
    from OCP.gp import gp_Ax1
    return gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1,0,0))

def outline_points(s, tol=0.2):
    """All edge points of solid, as 3D tuples."""
    pts=[]
    ee=TopExp_Explorer(s, TopAbs_EDGE)
    while ee.More():
        c=BRepAdaptor_Curve(TopoDS.Edge_s(ee.Current()))
        d=GCPnts_QuasiUniformDeflection(c, tol)
        if d.IsDone():
            for i in range(1, d.NbPoints()+1):
                p=d.Value(i); pts.append((p.X(),p.Y(),p.Z()))
        ee.Next()
    return pts

def hull2d(pts):
    pts=sorted(set((round(x,4),round(y,4)) for x,y in pts))
    if len(pts)<3: return pts
    def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[]
    for p in pts:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0: lo.pop()
        lo.append(p)
    up=[]
    for p in reversed(pts):
        while len(up)>=2 and cross(up[-2],up[-1],p)<=0: up.pop()
        up.append(p)
    return lo[:-1]+up[:-1]

def min_area_rect(hull):
    """Return (angle_rad, w, h) of minimum-area bounding rectangle."""
    best=None
    n=len(hull)
    for i in range(n):
        x1,y1=hull[i]; x2,y2=hull[(i+1)%n]
        a=math.atan2(y2-y1, x2-x1)
        ca,sa=math.cos(-a), math.sin(-a)
        xs=[p[0]*ca-p[1]*sa for p in hull]; ys=[p[0]*sa+p[1]*ca for p in hull]
        w=max(xs)-min(xs); h=max(ys)-min(ys)
        if best is None or w*h<best[1]*best[2]: best=(a,w,h)
    return best

def bbox(s):
    b=Bnd_Box(); BRepBndLib.Add_s(s,b,True); return b.Get()
