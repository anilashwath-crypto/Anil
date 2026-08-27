"""Search placement orders/rotations for the tightest profile nest."""
import math, json, random, numpy as np, itertools, time
import rasternest as R          # reuse rasterisation (module runs its own greedy pass first)
np.seterr(all='ignore')

SW,SH,RES,MARGIN,GAP = R.SW,R.SH,R.RES,R.MARGIN,R.GAP
GW,GH,M,Gc = R.GW,R.GH,R.M,R.Gc
variants = R.variants
ids = sorted(variants)
areas = {i: variants[i][0][1].sum()*RES*RES for i in ids}

def blank():
    occ=np.zeros((GH,GW),bool)
    occ[:M,:]=True; occ[-M:,:]=True; occ[:,:M]=True; occ[:,-M:]=True
    return occ

def run(order, rots_allowed=(0,90,180,270), score='bl'):
    sheets=[]
    place=[]
    for pid in order:
        done=False
        for si in range(len(sheets)):
            occ,dil = sheets[si]
            best=None
            for rot,m,poly in variants[pid]:
                if rot not in rots_allowed: continue
                fp=R.free_positions(dil, m)
                if fp is None or not fp.any(): continue
                ys,xs=np.nonzero(fp)
                k=np.lexsort((xs,ys))[0] if score=='bl' else np.lexsort((ys,xs))[0]
                y,x=int(ys[k]),int(xs[k])
                key=(y,x) if score=='bl' else (x,y)
                if best is None or key<best[0]: best=(key,rot,m,x,y)
            if best:
                _,rot,m,x,y=best; ph,pw=m.shape
                occ[y:y+ph,x:x+pw] |= m
                dil |= R.dilate(np.pad(m,((y,GH-y-ph),(x,GW-x-pw))), Gc)
                place.append((pid,si,rot,x*RES,y*RES)); done=True; break
        if not done:
            occ=blank(); dil=occ.copy(); sheets.append([occ,dil])
            si=len(sheets)-1; ok=False
            for rot,m,poly in variants[pid]:
                if rot not in rots_allowed: continue
                fp=R.free_positions(dil,m)
                if fp is None or not fp.any(): continue
                ys,xs=np.nonzero(fp); k=np.lexsort((xs,ys))[0]
                y,x=int(ys[k]),int(xs[k]); ph,pw=m.shape
                occ[y:y+ph,x:x+pw] |= m
                dil |= R.dilate(np.pad(m,((y,GH-y-ph),(x,GW-x-pw))), Gc)
                place.append((pid,si,rot,x*RES,y*RES)); ok=True; break
            assert ok, pid
    # objective: fewest sheets, then smallest used extent on the last sheet
    last=sheets[-1][0]
    cols=np.nonzero(last[:, M:GW-M].any(axis=0))[0]
    extent = (cols.max()+1)*RES if len(cols) else 0
    return len(sheets), extent, place

t0=time.time(); best=None; tried=0
cands=[]
cands.append(sorted(ids, key=lambda i:-areas[i]))                       # largest area first
cands.append(sorted(ids, key=lambda i:-variants[i][0][1].shape[1]))     # widest first
cands.append(sorted(ids, key=lambda i:-max(variants[i][0][1].shape)))   # longest first
rnd=random.Random(7)
while time.time()-t0 < 240:
    o=cands.pop(0) if cands else rnd.sample(ids, len(ids))
    for sc in ('bl','lb'):
        n,ext,pl = run(o, score=sc); tried+=1
        key=(n, ext)
        if best is None or key<best[0]:
            best=(key, o, sc, pl)
            print(f"  [{tried:>3}] sheets={n} last-sheet extent={ext:.0f} mm  order={o} score={sc}")
        if n==1: break
    if best[0][0]==1: break

(n,ext), order, sc, pl = best
print(f"\ntried {tried} arrangements in {time.time()-t0:.0f}s -> best: {n} sheet(s), last sheet used to x={ext:.0f} mm")
json.dump(dict(sheet=[SW,SH], margin=MARGIN, gap=GAP, res=RES, n_sheets=n,
               layout=[dict(id=p, sheet=s, rot=r, x=x, y=y) for p,s,r,x,y in pl]),
          open('layout_profile.json','w'), indent=1)
for p,s,r,x,y in sorted(pl, key=lambda t:(t[1],t[0])):
    print(f"  body {p:>2}  sheet {s+1}  ({x:7.1f},{y:7.1f})  rot {r:>3}")
