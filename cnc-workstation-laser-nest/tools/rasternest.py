"""True-profile nesting: rasterise each 5 mm plate outline, place with FFT collision test."""
import math, json, os, numpy as np
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopAbs import TopAbs_WIRE
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

SW, SH = 2440.0, 1220.0
MARGIN, GAP, RES = 10.0, 6.0, 2.0          # mm, mm, mm/cell
GW, GH = int(SW/RES), int(SH/RES)

solids = load_solids()
plates = []
for i, s in enumerate(solids):
    t, a, d = plate_axis(s)
    if abs(t-5.0) < 0.01: plates.append((i, s, d))
print("5 mm plates:", [p[0] for p in plates])

def norm(s):
    xmin,ymin,zmin,*_ = bbox(s); t=gp_Trsf(); t.SetTranslation(gp_Vec(-xmin,-ymin,-zmin)); return transform(s,t)

def bottom_face(s):
    c=[]
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            pl=ad.Plane()
            if abs(abs(pl.Axis().Direction().Z())-1)<1e-6:
                g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g); c.append((pl.Location().Z(), g.Mass(), f))
        fe.Next()
    zl=min(x[0] for x in c)
    return max([x for x in c if abs(x[0]-zl)<1e-4], key=lambda x:x[1])[2]

def outer_poly(s):
    """Outer boundary polyline of the flat plate, in mm, origin at its bbox min."""
    f=bottom_face(s); ow=BRepTools.OuterWire_s(f); pts=[]
    ee=TopExp_Explorer(ow, TopAbs_EDGE)
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    while ee.More():
        c=BRepAdaptor_Curve(TopoDS.Edge_s(ee.Current()))
        d=GCPnts_QuasiUniformDeflection(c, 0.4)
        if d.IsDone():
            seg=[(d.Value(k).X(), d.Value(k).Y()) for k in range(1, d.NbPoints()+1)]
            if pts and math.dist(pts[-1],seg[0]) > math.dist(pts[-1],seg[-1]): seg.reverse()
            pts += seg
        ee.Next()
    return pts

def rasterise(poly, res=RES):
    """Filled mask of polygon via even-odd scanline; conservative (any touched cell set)."""
    xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    w=int(math.ceil(max(xs)/res))+2; h=int(math.ceil(max(ys)/res))+2
    m=np.zeros((h,w), bool)
    n=len(poly)
    for row in range(h):
        yc=(row+0.5)*res; xhit=[]
        for k in range(n):
            x1,y1=poly[k]; x2,y2=poly[(k+1)%n]
            if (y1<=yc<y2) or (y2<=yc<y1):
                xhit.append(x1+(yc-y1)*(x2-x1)/(y2-y1))
        xhit.sort()
        for k in range(0,len(xhit)-1,2):
            c0=int(math.floor(xhit[k]/res)); c1=int(math.ceil(xhit[k+1]/res))
            m[row, max(0,c0):min(w,c1+1)] = True
    # also stamp the boundary so thin features never vanish
    for k in range(n):
        x1,y1=poly[k]; x2,y2=poly[(k+1)%n]
        L=max(1,int(math.dist((x1,y1),(x2,y2))/(res*0.5)))
        for t in range(L+1):
            xx=x1+(x2-x1)*t/L; yy=y1+(y2-y1)*t/L
            m[min(h-1,int(yy/res)), min(w-1,int(xx/res))] = True
    return m

def dilate(mask, cells):
    out=mask.copy()
    for _ in range(cells):
        o=out.copy()
        o[1:,:] |= out[:-1,:]; o[:-1,:] |= out[1:,:]
        o[:,1:] |= out[:,:-1]; o[:,:-1] |= out[:,1:]
        out=o
    return out

def free_positions(occ_dil, part):
    """Boolean grid of valid bottom-left origins (part fully clear of dilated occupancy)."""
    ph,pw = part.shape
    H,W = occ_dil.shape
    if ph>H or pw>W: return None
    fh, fw = H, W
    A=np.fft.rfft2(occ_dil.astype(np.float32), s=(fh,fw))
    B=np.fft.rfft2(part[::-1,::-1].astype(np.float32), s=(fh,fw))
    corr=np.fft.irfft2(A*B, s=(fh,fw))
    # corr[y+ph-1, x+pw-1] == overlap count for origin (x,y)
    val=corr[ph-1:H, pw-1:W]
    return val < 0.5

M=int(MARGIN/RES); Gc=int(math.ceil(GAP/RES))
sheets=[]; results=[]

def new_sheet():
    occ=np.zeros((GH,GW), bool)
    occ[:M,:]=True; occ[-M:,:]=True; occ[:,:M]=True; occ[:,-M:]=True   # margin band
    return dict(occ=occ, dil=occ.copy(), items=[])

variants={}
for pid, s, d in plates:
    flat=norm(transform(s, lay_flat_trsf(d)))
    poly=outer_poly(flat)
    vs=[]
    for rot in (0,90,180,270):
        a=math.radians(rot); ca,sa=math.cos(a),math.sin(a)
        rp=[(x*ca-y*sa, x*sa+y*ca) for x,y in poly]
        mnx=min(p[0] for p in rp); mny=min(p[1] for p in rp)
        rp=[(x-mnx, y-mny) for x,y in rp]
        vs.append((rot, rasterise(rp), rp))
    variants[pid]=vs
    a0=vs[0][1]
    print(f"  body {pid}: raster {a0.shape[1]*RES:.0f} x {a0.shape[0]*RES:.0f} mm, fill {a0.mean()*100:.0f}%")

order=sorted(plates, key=lambda p: -variants[p[0]][0][1].sum())
for pid, s, d in order:
    best=None
    for si, sh in enumerate(sheets):
        for rot, m, poly in variants[pid]:
            fp=free_positions(sh['dil'], m)
            if fp is None or not fp.any(): continue
            ys,xs=np.nonzero(fp)
            k=np.lexsort((xs,ys))[0]          # bottom-most, then left-most
            y,x=int(ys[k]), int(xs[k])
            key=(si, y, x)
            if best is None or key<best[0]: best=(key, si, rot, m, x, y)
        if best and best[1]==si: break        # first sheet that fits wins
    if best is None:
        sheets.append(new_sheet()); si=len(sheets)-1; sh=sheets[si]
        for rot, m, poly in variants[pid]:
            fp=free_positions(sh['dil'], m)
            if fp is None or not fp.any(): continue
            ys,xs=np.nonzero(fp); k=np.lexsort((xs,ys))[0]
            best=((si,int(ys[k]),int(xs[k])), si, rot, m, int(xs[k]), int(ys[k])); break
        assert best, f"body {pid} will not fit an empty sheet"
    _, si, rot, m, x, y = best
    sh=sheets[si]; ph,pw=m.shape
    sh['occ'][y:y+ph, x:x+pw] |= m
    sh['dil'][y:y+ph, x:x+pw] |= m
    sh['dil'] |= dilate(np.pad(m, ((y,GH-y-ph),(x,GW-x-pw))), Gc)
    sh['items'].append(dict(id=pid, rot=rot, x=x*RES, y=y*RES, w=pw*RES, h=ph*RES))
    results.append((pid, si, rot, x*RES, y*RES))
    print(f"  placed body {pid:>2} on sheet {si+1} at ({x*RES:7.1f},{y*RES:7.1f}) rot {rot:>3}")

print(f"\n=== profile nest: {len(sheets)} sheet(s) ===")
for si,sh in enumerate(sheets):
    print(f" sheet {si+1}: bodies {[it['id'] for it in sh['items']]}  raster fill {sh['occ'].mean()*100:.1f}%")
json.dump(dict(sheet=[SW,SH], margin=MARGIN, gap=GAP, res=RES, n_sheets=len(sheets),
               layout=[dict(id=it['id'], sheet=si, rot=it['rot'], x=it['x'], y=it['y'])
                       for si,sh in enumerate(sheets) for it in sh['items']]),
          open('layout_profile.json','w'), indent=1)
