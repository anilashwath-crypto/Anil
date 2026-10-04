"""Build + exactly verify + export the standardised-5 mm nest from layout_all.json."""
import math, json, os
from common import *
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Line, GeomAbs_Circle
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_WIRE, TopAbs_VERTEX
from OCP.BRep import BRep_Tool, BRep_Builder
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static

OUT="out2"; os.makedirs(OUT, exist_ok=True)
cfg=json.load(open('layout_all.json')); SW,SH=cfg['sheet']; MARGIN=cfg['margin']; GAP=cfg['gap']; STOCK=cfg['stock']
layout={l['id']:l for l in cfg['layout']}
solids=load_solids(); names=json.load(open('bodies.json'))

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
    return best
def bottom_face(s):
    c=[]; fe=TopExp_Explorer(s,TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face_s(fe.Current()); ad=BRepAdaptor_Surface(f)
        if ad.GetType()==GeomAbs_Plane and abs(abs(ad.Plane().Axis().Direction().Z())-1)<1e-6:
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(f,g); c.append((ad.Plane().Location().Z(),g.Mass(),f))
        fe.Next()
    zl=min(x[0] for x in c)
    return max([x for x in c if abs(x[0]-zl)<1e-4], key=lambda x:x[1])[2]

placed={}; src_thk={}
for i in sorted(layout):
    t,d = plate_dir(solids[i]); src_thk[i]=t
    flat=norm(transform(solids[i], lay_flat_trsf(d)))
    blank=norm(BRepPrimAPI_MakePrism(bottom_face(flat), gp_Vec(0,0,STOCK)).Shape())
    rot=layout[i]['rot']
    if rot:
        r=gp_Trsf(); r.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)), math.radians(rot)); blank=norm(transform(blank,r))
    tr=gp_Trsf(); tr.SetTranslation(gp_Vec(layout[i]['x'], layout[i]['y'], 0.0))
    placed[i]=transform(blank,tr)

print("=== exact verification ===")
faces={i:bottom_face(s) for i,s in placed.items()}
ok=True
for i,s in sorted(placed.items()):
    xmin,ymin,zmin,xmax,ymax,zmax=bbox(s); th=zmax-zmin; L=layout[i]
    inside = xmin>=MARGIN-1e-3 and ymin>=MARGIN-1e-3 and xmax<=SW-MARGIN+1e-3 and ymax<=SH-MARGIN+1e-3
    flat = abs(th-STOCK)<1e-3 and abs(zmin)<1e-3
    if not(inside and flat): ok=False
    note = "" if abs(src_thk[i]-STOCK)<0.05 else f"  (was {src_thk[i]:.0f} mm -> 5 mm)"
    print(f" {names[str(i)]['name']:<8} sheet {L['sheet']+1}  x[{xmin:7.1f},{xmax:7.1f}] y[{ymin:6.1f},{ymax:6.1f}] "
          f"thk {th:.3f} {'ok' if inside and flat else 'FAIL'}{note}")
worst=1e9
for si in sorted({l['sheet'] for l in layout.values()}):
    ids=[i for i in placed if layout[i]['sheet']==si]
    for a in range(len(ids)):
        for b in range(a+1,len(ids)):
            i,j=ids[a],ids[b]
            cm=BRepAlgoAPI_Common(faces[i],faces[j]); cm.Build()
            g=GProp_GProps(); BRepGProp.SurfaceProperties_s(cm.Shape(),g)
            d=BRepExtrema_DistShapeShape(BRepTools.OuterWire_s(faces[i]), BRepTools.OuterWire_s(faces[j])); d.Perform()
            if g.Mass()>1e-6 or d.Value()<GAP-1e-3:
                ok=False; print(f"   FAIL {i} vs {j}: overlap {g.Mass():.4f} mm2, clearance {d.Value():.3f}")
            worst=min(worst,d.Value())
print(f"\n min clearance {worst:.3f} mm (need {GAP:.0f})   RESULT: {'PASS' if ok else 'FAIL'}")
assert ok

def write_step(shapes,path,name):
    Interface_Static.SetCVal_s("write.step.product.name",name)
    w=STEPControl_Writer(); b=BRep_Builder(); c=TopoDS_Compound(); b.MakeCompound(c)
    for s in shapes: b.Add(c,s)
    w.Transfer(c,STEPControl_AsIs); assert w.Write(path)==IFSelect_RetDone
    print(f"  wrote {path} ({len(shapes)} bodies, {os.path.getsize(path)/1024:.0f} KB)")

nsh=cfg['n_sheets']
print()
for si in range(nsh):
    ids=[i for i in placed if layout[i]['sheet']==si]
    sfx=f"_Sheet{si+1}" if nsh>1 else ""
    write_step([placed[i] for i in ids], f"{OUT}/CNC_Workstation_5mm_NEST{sfx}.step", f"5mm nest{sfx}")
allsh=[]
for si in range(nsh):
    for i in [k for k in placed if layout[k]['sheet']==si]:
        t=gp_Trsf(); t.SetTranslation(gp_Vec(0.0, si*(SH+100.0), 0.0)); allsh.append(transform(placed[i],t))
if nsh>1: write_step(allsh, f"{OUT}/CNC_Workstation_5mm_NEST_AllSheets.step", "5mm nest all sheets")

# ---- DXF + SVG ----
def edges_of(w):
    o=[]; e=TopExp_Explorer(w,TopAbs_EDGE)
    while e.More(): o.append(TopoDS.Edge_s(e.Current())); e.Next()
    return o
def ents(edge,acc):
    c=BRepAdaptor_Curve(edge); t0,t1=c.FirstParameter(),c.LastParameter(); p0,p1=c.Value(t0),c.Value(t1)
    if c.GetType()==GeomAbs_Line: acc.append(("LINE",p0.X(),p0.Y(),p1.X(),p1.Y()))
    elif c.GetType()==GeomAbs_Circle:
        ci=c.Circle(); ctr=ci.Location(); R=ci.Radius(); az=ci.Axis().Direction().Z()
        if abs(t1-t0)>=2*math.pi-1e-7: acc.append(("CIRCLE",ctr.X(),ctr.Y(),R))
        else:
            a0=math.degrees(math.atan2(p0.Y()-ctr.Y(),p0.X()-ctr.X()))%360
            a1=math.degrees(math.atan2(p1.Y()-ctr.Y(),p1.X()-ctr.X()))%360
            if az<0: a0,a1=a1,a0
            acc.append(("ARC",ctr.X(),ctr.Y(),R,a0,a1))
    else:
        d=GCPnts_QuasiUniformDeflection(c,0.05)
        pts=[c.Value(t0)] if not d.IsDone() else [d.Value(k) for k in range(1,d.NbPoints()+1)]
        acc.append(("POLY",[(p.X(),p.Y()) for p in pts]))
def wire_pts(w):
    pts=[]
    for e in edges_of(w):
        c=BRepAdaptor_Curve(e); d=GCPnts_QuasiUniformDeflection(c,0.3)
        if d.IsDone():
            seg=[(d.Value(k).X(),d.Value(k).Y()) for k in range(1,d.NbPoints()+1)]
            if pts and math.dist(pts[-1],seg[0])>math.dist(pts[-1],seg[-1]): seg.reverse()
            pts+=seg
    return pts
for si in range(nsh):
    ids=sorted(i for i in placed if layout[i]['sheet']==si)
    L=[]; svg=[]
    def g(c,v): L.append(str(c)); L.append(str(v))
    g(0,"SECTION"); g(2,"ENTITIES")
    def emit(e,lay):
        k=e[0]
        if k=="LINE": g(0,"LINE"); g(8,lay); g(10,f"{e[1]:.5f}"); g(20,f"{e[2]:.5f}"); g(30,"0.0"); g(11,f"{e[3]:.5f}"); g(21,f"{e[4]:.5f}"); g(31,"0.0")
        elif k=="CIRCLE": g(0,"CIRCLE"); g(8,lay); g(10,f"{e[1]:.5f}"); g(20,f"{e[2]:.5f}"); g(30,"0.0"); g(40,f"{e[3]:.5f}")
        elif k=="ARC": g(0,"ARC"); g(8,lay); g(10,f"{e[1]:.5f}"); g(20,f"{e[2]:.5f}"); g(30,"0.0"); g(40,f"{e[3]:.5f}"); g(50,f"{e[4]:.5f}"); g(51,f"{e[5]:.5f}")
        else:
            g(0,"POLYLINE"); g(8,lay); g(66,1); g(70,0)
            for x,y in e[1]: g(0,"VERTEX"); g(8,lay); g(10,f"{x:.5f}"); g(20,f"{y:.5f}"); g(30,"0.0")
            g(0,"SEQEND"); g(8,lay)
    for x0,y0,x1,y1 in [(0,0,SW,0),(SW,0,SW,SH),(SW,SH,0,SH),(0,SH,0,0)]: emit(("LINE",x0,y0,x1,y1),"SHEET")
    for i in ids:
        bf=faces[i]; ow=BRepTools.OuterWire_s(bf)
        we=TopExp_Explorer(bf,TopAbs_WIRE)
        while we.More():
            w=TopoDS.Wire_s(we.Current()); is_out=w.IsSame(ow); acc=[]
            for e in edges_of(w): ents(e,acc)
            for e in acc: emit(e,"CUT_OUTER" if is_out else "CUT_INNER")
            p=wire_pts(w)
            if len(p)>2:
                svg.append('<polygon points="'+" ".join(f"{x:.2f},{SH-y:.2f}" for x,y in p)+
                           f'" fill="{"#cfe3f7" if is_out else "#fff"}" stroke="#123" stroke-width="1.2"/>')
            we.Next()
        xmin,ymin,_,xmax,ymax,_=bbox(placed[i])
        lbl=names[str(i)]['name'] + ("*" if abs(src_thk[i]-STOCK)>0.05 else "")
        svg.append(f'<text x="{(xmin+xmax)/2:.1f}" y="{SH-(ymin+ymax)/2:.1f}" font-size="38" text-anchor="middle" '
                   f'fill="#b0002a" font-family="sans-serif" font-weight="bold">{lbl}</text>')
    g(0,"ENDSEC"); g(0,"EOF")
    sfx=f"_Sheet{si+1}" if nsh>1 else ""
    open(f"{OUT}/CNC_Workstation_5mm_NEST{sfx}.dxf","w").write("\n".join(L)+"\n")
    open(f"{OUT}/CNC_Workstation_5mm_NEST{sfx}.svg","w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -50 {SW+40} {SH+70}" width="1500">'
        f'<rect x="0" y="0" width="{SW}" height="{SH}" fill="#f7f7f4" stroke="#888" stroke-width="2"/>'
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{SW-2*MARGIN}" height="{SH-2*MARGIN}" fill="none" '
        f'stroke="#bbb" stroke-dasharray="12 8" stroke-width="1.5"/>'+"".join(svg)+
        f'<text x="10" y="-14" font-size="34" font-family="sans-serif">Sheet {si+1} of {nsh}'
        f' &#8212; 2440 x 1220 x 5 mm  (* = re-thicknessed to 5 mm)</text></svg>')
    print(f"  wrote {OUT}/...{sfx}.dxf + .svg  ({len(ids)} parts)")
