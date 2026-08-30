import math, json, os
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopoDS import TopoDS
from OCP.TopAbs import TopAbs_VERTEX
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane

OUT="out2"
cfg=json.load(open('layout_all.json')); SW,SH=cfg['sheet']; STOCK=cfg['stock']
layout={l['id']:l for l in cfg['layout']}
solids=load_solids(); names=json.load(open('bodies.json'))

def norm_trsf(s):
    xmin,ymin,zmin,*_=bbox(s); t=gp_Trsf(); t.SetTranslation(gp_Vec(-xmin,-ymin,-zmin)); return t
def plate_dir(s):
    V=[]; ex=TopExp_Explorer(s,TopAbs_VERTEX)
    while ex.More(): p=BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current())); V.append((p.X(),p.Y(),p.Z())); ex.Next()
    dirs={}; fe=TopExp_Explorer(s,TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            n=ad.Plane().Axis().Direction(); d=(n.X(),n.Y(),n.Z())
            if d[0]<-1e-9 or (abs(d[0])<1e-9 and (d[1]<-1e-9 or (abs(d[1])<1e-9 and d[2]<0))): d=(-d[0],-d[1],-d[2])
            dirs[tuple(round(v,6) for v in d)]=1
        fe.Next()
    best=None
    for d in dirs:
        pr=[v[0]*d[0]+v[1]*d[1]+v[2]*d[2] for v in V]; t=max(pr)-min(pr)
        if t>0.05 and (best is None or t<best[0]): best=(t,d)
    return best

tf={}; print(f"{'body':<8} {'det':>7} {'placed x,y':>18} {'plan x,y':>18} {'dev':>9}")
ok=True
for i in sorted(layout):
    src_t, d = plate_dir(solids[i])
    T = lay_flat_trsf(d); cur = transform(solids[i], T)
    t2 = norm_trsf(cur); cur = transform(cur, t2); T = t2.Multiplied(T)
    rot = layout[i]['rot']
    if rot:
        r=gp_Trsf(); r.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), math.radians(rot))
        cur=transform(cur,r); T=r.Multiplied(T)
        t3=norm_trsf(cur); cur=transform(cur,t3); T=t3.Multiplied(T)
    tr=gp_Trsf(); tr.SetTranslation(gp_Vec(layout[i]['x'], layout[i]['y'], 0.0))
    cur=transform(cur,tr); T=tr.Multiplied(T)
    xmin,ymin,zmin,xmax,ymax,zmax=bbox(cur)
    m=[[T.Value(r_,c_) for c_ in range(1,5)] for r_ in range(1,4)]
    M=[[m[r_][c_] for c_ in range(3)] for r_ in range(3)]
    det=(M[0][0]*(M[1][1]*M[2][2]-M[1][2]*M[2][1])-M[0][1]*(M[1][0]*M[2][2]-M[1][2]*M[2][0])
        +M[0][2]*(M[1][0]*M[2][1]-M[1][1]*M[2][0]))
    dev=max(abs(xmin-layout[i]['x']), abs(ymin-layout[i]['y']), abs(zmin))
    if det<0.999 or dev>1e-6: ok=False
    print(f"{names[str(i)]['name']:<8} {det:>7.4f} {xmin:>9.2f},{ymin:<8.2f} {layout[i]['x']:>9.2f},{layout[i]['y']:<8.2f} {dev:>9.1e}")
    tf[names[str(i)]['name']]=dict(body_index=i, sheet=layout[i]['sheet'], source_thk_mm=round(src_t,3),
        vol_mm3=names[str(i)]['vol_mm3'], centroid_mm=[names[str(i)]['cx'],names[str(i)]['cy'],names[str(i)]['cz']],
        matrix_mm=[m[0],m[1],m[2]])
assert ok, "transform check failed"
print("\nall matrices are proper rotations and reproduce the plan exactly.")
json.dump(dict(sheet=[SW,SH], stock_thickness=STOCK, margin=cfg['margin'], gap=cfg['gap'],
               n_sheets=cfg['n_sheets'], transforms=tf), open(f'{OUT}/nest_transforms.json','w'), indent=1)
print(f"wrote {OUT}/nest_transforms.json")
