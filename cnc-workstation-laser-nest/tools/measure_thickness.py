import math
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.gp import gp_Dir

F="/root/.claude/uploads/0e09e0c2-1227-5643-b121-27ab532564bc/df5481a8-CNC_WorkstationV1.step.step"
doc = TDocStd_Document(TCollection_ExtendedString("d"))
r = STEPCAFControl_Reader(); r.SetNameMode(True)
assert r.ReadFile(F) == IFSelect_RetDone
r.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
labs = TDF_LabelSequence(); st.GetFreeShapes(labs)
shape = st.GetShape_s(labs.Value(1))

solids=[]
ex = TopExp_Explorer(shape, TopAbs_SOLID)
while ex.More():
    solids.append(TopoDS.Solid_s(ex.Current())); ex.Next()

print(f"{'id':>3} {'thk':>7} {'faceArea_cm2':>12} {'vol_cm3':>9} {'plate?':>7}  {'normal(dir)':<24} {'flatWxL':>16}")
info=[]
for i,s in enumerate(solids):
    # collect planar faces with outward normal + area
    planes=[]
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current())
        ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            pl=ad.Plane()
            n=pl.Axis().Direction()
            if f.Orientation()==TopAbs_REVERSED: n=n.Reversed()
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g)
            d=(n.X(),n.Y(),n.Z())
            off=pl.Location().X()*d[0]+pl.Location().Y()*d[1]+pl.Location().Z()*d[2]
            planes.append((g.Mass(), d, off))
        fe.Next()
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); vol=g.Mass()
    # group parallel faces by axis, find dominant opposite pair
    best=None
    for a_,da,oa in planes:
        for b_,db,ob in planes:
            dot=da[0]*db[0]+da[1]*db[1]+da[2]*db[2]
            if dot < -0.9999:   # opposite normals
                t = oa+ob       # separation
                if t<=0.01: continue
                pair_area=min(a_,b_)
                if best is None or pair_area>best[0]:
                    best=(pair_area,t,da)
    if best:
        area,t,d = best
        plate = abs(vol - area*t)/vol < 0.06
        print(f"{i:>3} {t:>7.2f} {area/100:>12.1f} {vol/1000:>9.1f} {str(plate):>7}  ({d[0]:+.3f},{d[1]:+.3f},{d[2]:+.3f})")
        info.append((i,t,area,vol,d,plate))
    else:
        print(f"{i:>3} {'-':>7}")
