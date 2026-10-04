from common import *
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
import re, json
# order of MANIFOLD_SOLID_BREP in the file
txt=open(STEPFILE, errors='ignore').read()
file_names=re.findall(r"MANIFOLD_SOLID_BREP\('([^']*)'", txt)
solids=load_solids()
print("names in file:", len(file_names), " solids traversed:", len(solids))
out={}
for i,s in enumerate(solids):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); c=g.CentreOfMass()
    t=plate_axis(s)
    out[i]=dict(name=file_names[i] if i<len(file_names) else f"Solid{i}",
                vol_mm3=g.Mass(), cx=c.X(), cy=c.Y(), cz=c.Z(),
                thk=round(t[0],3) if t else None)
    print(f"{i:>3} {out[i]['name']:<9} thk={out[i]['thk']:>7} vol={g.Mass()/1000:>8.1f} cm3  centroid=({c.X():8.1f},{c.Y():8.1f},{c.Z():8.1f})")
json.dump(out, open('bodies.json','w'), indent=1)
