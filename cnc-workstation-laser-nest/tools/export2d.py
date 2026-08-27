import math, json, os
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopAbs import TopAbs_WIRE
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS
from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Circle
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

OUT="out"; cfg=json.load(open('layout_profile.json'))
SW,SH=cfg['sheet']; layout={l['id']:l for l in cfg['layout']}
solids=load_solids()

def norm_to_origin(s):
    xmin,ymin,zmin,_,_,_=bbox(s); t=gp_Trsf(); t.SetTranslation(gp_Vec(-xmin,-ymin,-zmin)); return transform(s,t)

placed={}
for i,s in enumerate(solids):
    if i not in layout: continue
    L=layout[i]
    f=norm_to_origin(transform(s, lay_flat_trsf(plate_axis(s)[2])))
    rot=L.get('rot', 0)
    if rot:
        r=gp_Trsf(); r.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)), math.radians(rot))
        f=norm_to_origin(transform(f,r))
    t=gp_Trsf(); t.SetTranslation(gp_Vec(L['x'],L['y'],0.0)); placed[i]=transform(f,t)

def bottom_face(s):
    """Largest planar face whose normal is +/-Z and which lies on the part's lowest Z plane."""
    cands=[]
    fe=TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane:
            pl=ad.Plane(); n=pl.Axis().Direction()
            if abs(abs(n.Z())-1)<1e-6:
                g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g)
                cands.append((pl.Location().Z(), g.Mass(), f))
        fe.Next()
    assert cands, "no planar +/-Z face found"
    zmin=min(c[0] for c in cands)
    low=[c for c in cands if abs(c[0]-zmin)<1e-4]
    return max(low, key=lambda c: c[1])[2]

def wires(face):
    out=[]
    we=TopExp_Explorer(face, TopAbs_WIRE)
    outer=BRepTools.OuterWire_s(face)
    while we.More():
        w=TopoDS.Wire_s(we.Current()); out.append((w.IsSame(outer), w)); we.Next()
    return out

def edges_of(w):
    out=[]
    ee=TopExp_Explorer(w, TopAbs_EDGE)
    while ee.More(): out.append(TopoDS.Edge_s(ee.Current())); ee.Next()
    return out

# ---------------- DXF (R12: LINE / ARC / CIRCLE / POLYLINE) ----------------
def dxf_entities(edge, ents):
    c=BRepAdaptor_Curve(edge); t0,t1=c.FirstParameter(), c.LastParameter()
    p0,p1=c.Value(t0), c.Value(t1)
    if c.GetType()==GeomAbs_Line:
        ents.append(("LINE", p0.X(),p0.Y(), p1.X(),p1.Y()))
    elif c.GetType()==GeomAbs_Circle:
        ci=c.Circle(); ctr=ci.Location(); R=ci.Radius(); az=ci.Axis().Direction().Z()
        if abs(t1-t0) >= 2*math.pi-1e-7:
            ents.append(("CIRCLE", ctr.X(), ctr.Y(), R))
        else:
            a0=math.degrees(math.atan2(p0.Y()-ctr.Y(), p0.X()-ctr.X()))%360
            a1=math.degrees(math.atan2(p1.Y()-ctr.Y(), p1.X()-ctr.X()))%360
            if az < 0: a0,a1 = a1,a0          # DXF arcs are CCW in XY
            ents.append(("ARC", ctr.X(), ctr.Y(), R, a0, a1))
    else:
        d=GCPnts_QuasiUniformDeflection(c, 0.05)
        pts=[c.Value(t0)] if not d.IsDone() else [d.Value(i) for i in range(1,d.NbPoints()+1)]
        ents.append(("POLYLINE", [(p.X(),p.Y()) for p in pts]))

def write_dxf(path, per_part, sheet_rect):
    L=[]
    def g(code,val): L.append(str(code)); L.append(str(val))
    g(0,"SECTION"); g(2,"ENTITIES")
    def emit(e, layer):
        k=e[0]
        if k=="LINE":
            g(0,"LINE"); g(8,layer); g(10,f"{e[1]:.5f}"); g(20,f"{e[2]:.5f}"); g(30,"0.0")
            g(11,f"{e[3]:.5f}"); g(21,f"{e[4]:.5f}"); g(31,"0.0")
        elif k=="CIRCLE":
            g(0,"CIRCLE"); g(8,layer); g(10,f"{e[1]:.5f}"); g(20,f"{e[2]:.5f}"); g(30,"0.0"); g(40,f"{e[3]:.5f}")
        elif k=="ARC":
            g(0,"ARC"); g(8,layer); g(10,f"{e[1]:.5f}"); g(20,f"{e[2]:.5f}"); g(30,"0.0")
            g(40,f"{e[3]:.5f}"); g(50,f"{e[4]:.5f}"); g(51,f"{e[5]:.5f}")
        elif k=="POLYLINE":
            g(0,"POLYLINE"); g(8,layer); g(66,1); g(70,0)
            for x,y in e[1]:
                g(0,"VERTEX"); g(8,layer); g(10,f"{x:.5f}"); g(20,f"{y:.5f}"); g(30,"0.0")
            g(0,"SEQEND"); g(8,layer)
    for x0,y0,x1,y1 in sheet_rect: emit(("LINE",x0,y0,x1,y1), "SHEET")
    for pid, outer, inner in per_part:
        for e in outer: emit(e, f"CUT_OUTER")
        for e in inner: emit(e, f"CUT_INNER")
    g(0,"ENDSEC"); g(0,"EOF")
    open(path,"w").write("\n".join(L)+"\n")

# ---------------- SVG preview ----------------
def wire_pts(w):
    pts=[]
    for e in edges_of(w):
        c=BRepAdaptor_Curve(e); d=GCPnts_QuasiUniformDeflection(c, 0.3)
        if d.IsDone():
            seg=[(d.Value(i).X(), d.Value(i).Y()) for i in range(1,d.NbPoints()+1)]
            if pts and math.dist(pts[-1],seg[0]) > math.dist(pts[-1],seg[-1]): seg.reverse()
            pts += seg
    return pts

stats=[]
for si in range(cfg['n_sheets']):
    ids=sorted(i for i in placed if layout[i]['sheet']==si)
    per_part=[]; svg=[]; nholes=0
    for i in ids:
        bf=bottom_face(placed[i]); outer=[]; inner=[]
        for is_outer, w in wires(bf):
            ents=[]
            for e in edges_of(w): dxf_entities(e, ents)
            (outer if is_outer else inner).extend(ents)
            if not is_outer: nholes+=1
            p=wire_pts(w)
            if len(p)>2:
                svg.append('<polygon points="'+" ".join(f"{x:.2f},{SH-y:.2f}" for x,y in p)+'" '
                           f'fill="{"#cfe3f7" if is_outer else "#ffffff"}" stroke="#123" stroke-width="1.2"/>')
        per_part.append((i, outer, inner))
        xmin,ymin,_,xmax,ymax,_ = bbox(placed[i])
        svg.append(f'<text x="{(xmin+xmax)/2:.1f}" y="{SH-(ymin+ymax)/2:.1f}" font-size="40" '
                   f'text-anchor="middle" fill="#b0002a" font-family="sans-serif" font-weight="bold">B{i}</text>')
    rect=[(0,0,SW,0),(SW,0,SW,SH),(SW,SH,0,SH),(0,SH,0,0)]
    write_dxf(f"{OUT}/CNC_Workstation_5mm_NEST.dxf", per_part, rect)
    open(f"{OUT}/CNC_Workstation_5mm_NEST.svg","w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -20 {SW+40} {SH+40}" width="1400">'
        f'<rect x="0" y="0" width="{SW}" height="{SH}" fill="#f7f7f4" stroke="#888" stroke-width="2"/>'
        f'<rect x="{cfg["margin"]}" y="{cfg["margin"]}" width="{SW-2*cfg["margin"]}" height="{SH-2*cfg["margin"]}" '
        f'fill="none" stroke="#bbb" stroke-dasharray="12 8" stroke-width="1.5"/>'
        + "".join(svg) +
        f'<text x="10" y="-4" font-size="30" font-family="sans-serif">Sheet {si+1} — 2440 x 1220 x 5 mm</text></svg>')
    stats.append((si+1, len(ids), nholes))
    print(f"sheet {si+1}: {len(ids)} parts, {nholes} internal cut-outs -> DXF + SVG")
