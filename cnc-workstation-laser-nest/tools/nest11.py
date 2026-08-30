import math, json, time, random, numpy as np
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_WIRE, TopAbs_VERTEX
from OCP.BRep import BRep_Tool

SW,SH,MARGIN,GAP,RES,STOCK = 2440.0,1220.0,10.0,6.0,2.0,5.0
GW,GH = int(SW/RES), int(SH/RES); M=int(MARGIN/RES); Gc=int(math.ceil(GAP/RES))
EXCLUDE_10MM=11; BENT={1,13,14,15,16}
EIGHT_MM=set()   # 8 mm structural plates now standardised to 5 mm on request
solids=load_solids(); names=json.load(open('bodies.json'))
sel=[i for i in range(len(solids)) if i!=EXCLUDE_10MM and i not in BENT and i not in EIGHT_MM]

def norm(s):
    xmin,ymin,zmin,*_=bbox(s); t=gp_Trsf(); t.SetTranslation(gp_Vec(-xmin,-ymin,-zmin)); return transform(s,t)
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
    return best[1]
def bottom_face(s):
    c=[]; fe=TopExp_Explorer(s,TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane and abs(abs(ad.Plane().Axis().Direction().Z())-1)<1e-6:
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g); c.append((ad.Plane().Location().Z(),g.Mass(),f))
        fe.Next()
    zl=min(x[0] for x in c)
    return max([x for x in c if abs(x[0]-zl)<1e-4], key=lambda x:x[1])[2]

blanks={}
for i in sel:
    flat=norm(transform(solids[i], lay_flat_trsf(plate_dir(solids[i]))))
    blanks[i]=norm(BRepPrimAPI_MakePrism(bottom_face(flat), gp_Vec(0,0,STOCK)).Shape())

def outer_poly(s):
    f=bottom_face(s); ow=BRepTools.OuterWire_s(f); pts=[]
    ee=TopExp_Explorer(ow, TopAbs_EDGE)
    while ee.More():
        c=BRepAdaptor_Curve(TopoDS.Edge_s(ee.Current())); d=GCPnts_QuasiUniformDeflection(c,0.4)
        if d.IsDone():
            seg=[(d.Value(k).X(),d.Value(k).Y()) for k in range(1,d.NbPoints()+1)]
            if pts and math.dist(pts[-1],seg[0])>math.dist(pts[-1],seg[-1]): seg.reverse()
            pts+=seg
        ee.Next()
    return pts
def rasterise(poly,res=RES):
    xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    w=int(math.ceil(max(xs)/res))+2; h=int(math.ceil(max(ys)/res))+2
    m=np.zeros((h,w),bool); n=len(poly)
    for row in range(h):
        yc=(row+0.5)*res; xh=[]
        for k in range(n):
            x1,y1=poly[k]; x2,y2=poly[(k+1)%n]
            if (y1<=yc<y2) or (y2<=yc<y1): xh.append(x1+(yc-y1)*(x2-x1)/(y2-y1))
        xh.sort()
        for k in range(0,len(xh)-1,2):
            m[row, max(0,int(math.floor(xh[k]/res))):min(w,int(math.ceil(xh[k+1]/res))+1)]=True
    for k in range(n):
        x1,y1=poly[k]; x2,y2=poly[(k+1)%n]
        L=max(1,int(math.dist((x1,y1),(x2,y2))/(res*0.5)))
        for t in range(L+1):
            m[min(h-1,int((y1+(y2-y1)*t/L)/res)), min(w-1,int((x1+(x2-x1)*t/L)/res))]=True
    return m
_DISK=None
def dilate(mask,c):
    """Euclidean-disk dilation by c cells. A diamond (repeated 4-neighbour) dilation only
    guarantees c*RES along the axes and c*RES/sqrt(2) diagonally, which under-spaces parts."""
    global _DISK
    if _DISK is None or _DISK[0]!=c:
        offs=[(dx,dy) for dx in range(-c,c+1) for dy in range(-c,c+1) if dx*dx+dy*dy <= c*c]
        _DISK=(c,offs)
    out=mask.copy(); H,W=mask.shape
    for dx,dy in _DISK[1]:
        if dx==0 and dy==0: continue
        ys0,ys1 = max(0,dy), min(H,H+dy)
        xs0,xs1 = max(0,dx), min(W,W+dx)
        out[ys0:ys1, xs0:xs1] |= mask[ys0-dy:ys1-dy, xs0-dx:xs1-dx]
    return out

def free_pos(occ,part):
    ph,pw=part.shape; H,W=occ.shape
    if ph>H or pw>W: return None
    A=np.fft.rfft2(occ.astype(np.float32),s=(H,W)); B=np.fft.rfft2(part[::-1,::-1].astype(np.float32),s=(H,W))
    return np.fft.irfft2(A*B,s=(H,W))[ph-1:H, pw-1:W] < 0.5

variants={}
for i in sel:
    poly=outer_poly(blanks[i]); vs=[]
    for rot in (0,90,180,270):
        a=math.radians(rot); ca,sa=math.cos(a),math.sin(a)
        rp=[(x*ca-y*sa, x*sa+y*ca) for x,y in poly]
        mx=min(p[0] for p in rp); my=min(p[1] for p in rp)
        vs.append((rot, rasterise([(x-mx,y-my) for x,y in rp])))
    variants[i]=vs
def blank_sheet():
    o=np.zeros((GH,GW),bool); o[:M,:]=True; o[-M:,:]=True; o[:,:M]=True; o[:,-M:]=True; return o
def run(order):
    sheets=[]; place=[]
    for pid in order:
        done=False
        for si in range(len(sheets)):
            occ,dil=sheets[si]; best=None
            for rot,m in variants[pid]:
                fp=free_pos(dil,m)
                if fp is None or not fp.any(): continue
                ys,xs=np.nonzero(fp); k=np.lexsort((xs,ys))[0]
                if best is None or (ys[k],xs[k])<best[0]: best=((int(ys[k]),int(xs[k])),rot,m)
            if best:
                (y,x),rot,m=best; ph,pw=m.shape
                occ[y:y+ph,x:x+pw]|=m
                dil|=dilate(np.pad(m,((y,GH-y-ph),(x,GW-x-pw))),Gc)
                place.append((pid,si,rot,x*RES,y*RES)); done=True; break
        if not done:
            occ=blank_sheet(); dil=occ.copy(); sheets.append([occ,dil]); si=len(sheets)-1
            for rot,m in variants[pid]:
                fp=free_pos(dil,m)
                if fp is None or not fp.any(): continue
                ys,xs=np.nonzero(fp); k=np.lexsort((xs,ys))[0]; y,x=int(ys[k]),int(xs[k]); ph,pw=m.shape
                occ[y:y+ph,x:x+pw]|=m
                dil|=dilate(np.pad(m,((y,GH-y-ph),(x,GW-x-pw))),Gc)
                place.append((pid,si,rot,x*RES,y*RES)); break
    last=sheets[-1][0]; cols=np.nonzero(last[:,M:GW-M].any(axis=0))[0]
    return len(sheets), ((cols.max()+1)*RES if len(cols) else 0), place

t0=time.time(); best=None; rnd=random.Random(11); tried=0
cands=[sorted(sel,key=lambda i:-variants[i][0][1].sum()),
       sorted(sel,key=lambda i:-max(variants[i][0][1].shape)),
       sorted(sel,key=lambda i:-variants[i][0][1].shape[1])]
while time.time()-t0 < 600:
    o=cands.pop(0) if cands else rnd.sample(sel,len(sel))
    n,ext,pl=run(o); tried+=1
    if best is None or (n,ext)<best[0]:
        best=((n,ext),pl); print(f"  [{tried:>3}] {n} sheet(s), last-sheet extent {ext:.0f} mm", flush=True)
print(f"\ntried {tried} orders in {time.time()-t0:.0f}s -> {best[0][0]} sheets, last used to x={best[0][1]:.0f} mm")
json.dump(dict(sheet=[SW,SH],margin=MARGIN,gap=GAP,res=RES,n_sheets=best[0][0],stock=STOCK,
               layout=[dict(id=p,sheet=s,rot=r,x=x,y=y) for p,s,r,x,y in best[1]]),
          open('layout_all.json','w'), indent=1)
for p,s,r,x,y in sorted(best[1],key=lambda t:(t[1],t[0])):
    print(f"  {names[str(p)]['name']:<8} sheet {s+1}  ({x:7.1f},{y:7.1f})  rot {r:>3}")
