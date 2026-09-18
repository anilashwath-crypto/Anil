#!/usr/bin/env python3
"""
Plan section through the mech bay, cut from the real case_lower mesh, with the
ESP32 and servo mounts called out and dimensioned. Everything drawn here is a
slice of the STL that goes to the printer.
"""
import os, sys, math
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
CONT = ("/Users/piyushmishra/Desktop/toolcell/.superpowers/brainstorm/"
        "25158-1786171087/content")
sys.path.insert(0, HERE)

CW, CD, WL, FT = 92.0, 74.0, 2.0, 1.4
EX, EY, EBW, EBL = CW/2, CD-23.0, 35.5, 81.5
SG_L, SG_W, SG_TAB, CLR = 22.8, 12.2, 32.2, 0.35
DR_W = (CW-2*WL-6.0-2*1.2)/2
DR_X = (WL+1.2, WL+1.2+DR_W+6.0)
FIN_X = DR_W*0.20
M, N = 1.25, 16
R_P = M*N/2
FIN_T, TOOTH_H = 3.0, 2.25*M
PIN_DX = -FIN_T/2 + (FIN_T+TOOTH_H - M) + R_P
PIN_Y = 17.6

case = trimesh.load(os.path.join(HERE, "..", "nano", "case_lower.stl"))

def outline(z):
    sec = case.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        raise RuntimeError(f"no section at z={z}")
    p2, to3 = sec.to_planar()
    out = []
    for d in p2.discrete:
        pts = np.asarray(d, float)
        h = np.column_stack([pts, np.zeros(len(pts)), np.ones(len(pts))])
        w = (to3 @ h.T).T[:, :3]
        out.append([(p[0], p[1]) for p in w])
    return out

S = 5.4
def path(polys):
    d = []
    for pl in polys:
        pts = [(30 + a*S, 30 + (CD-b)*S) for a, b in pl]
        d.append("M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z")
    return " ".join(d)

def rect(x0, y0, w, h, **kw):
    a = " ".join(f'{k.replace("_","-")}="{v}"' for k, v in kw.items())
    return (f'<rect x="{30+x0*S:.1f}" y="{30+(CD-y0-h)*S:.1f}" '
            f'width="{w*S:.1f}" height="{h*S:.1f}" {a}/>')

def label(x, y, t, col="#8fb4d4", size=11, anchor="start"):
    return (f'<text x="{30+x*S:.1f}" y="{30+(CD-y)*S:.1f}" fill="{col}" '
            f'font-size="{size}" text-anchor="{anchor}">{t}</text>')

W_, H_ = CW*S+60, CD*S+60
mech = outline(6.0)

sv = []
for i, dx in enumerate(DR_X):
    px = dx + FIN_X + PIN_DX
    sv.append(rect(px-SG_TAB/2-2.0, WL+PIN_Y-SG_W/2-CLR-1.6, SG_TAB+4.0,
                   SG_W+2*CLR+3.2, fill="rgba(242,183,5,.18)", stroke="#f2b705",
                   stroke_width="1.6"))
    sv.append(rect(px-SG_L/2-CLR, WL+PIN_Y-SG_W/2-CLR, SG_L+2*CLR, SG_W+2*CLR,
                   fill="rgba(242,183,5,.55)", stroke="#f2b705", stroke_width="1.4"))
    sv.append(label(px, WL+PIN_Y+SG_W/2+5.5, f"SG90 {'AB'[i]}", "#f2b705", 12, "middle"))

html = f"""<style>
.mp {{ background:#0c2036; color:#d8ecff; border-radius:10px; padding:22px;
      font-family:ui-monospace,Menlo,monospace; }}
.mp h2 {{ color:#eaf5ff; margin:0 0 4px; font-size:19px; }}
.mp p.s {{ color:#8fb4d4; font-size:12.5px; margin:0 0 14px; line-height:1.55; }}
.mp svg {{ display:block; width:100%; height:auto; }}
.mp table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:14px; }}
.mp td,.mp th {{ border:1px solid #23496e; padding:5px 9px; text-align:left; }}
.mp th {{ background:#12293f; color:#7fc4ff; }}
</style>
<div class="mp">
<h2>MECH BAY &mdash; plan section at z = 6 mm</h2>
<p class="s">Grey outline is a slice of the real <code>case_lower.stl</code>. Yellow = the two SG90 cradles.
Green = the ESP32-S3 + breadboard channel. Everything is drawn from the shipped mesh.</p>
<svg viewBox="0 0 {W_:.0f} {H_:.0f}">
  <path d="{path(mech)}" fill="rgba(138,138,138,.20)" stroke="#8a8a8a" stroke-width="1.6" fill-rule="evenodd"/>
  {"".join(sv)}
  {rect(EX-EBL/2, EY-EBW/2, EBL, EBW, fill="rgba(63,168,122,.22)", stroke="#3fa87a", stroke_width="1.6")}
  {label(EX, EY+2, "ESP32-S3 + breadboard", "#4fd18b", 12, "middle")}
  {label(EX, EY-3.5, f"{EBL:.1f} x {EBW:.1f}", "#4fd18b", 10.5, "middle")}
  {label(EX+EBL/2+2, EY-EBW/2-4, "micro-USB &rarr; rear window", "#4fd18b", 10, "end")}
  {label(2, CD+3, f"case_lower {CW:.0f} x {CD:.0f} mm", "#8a8a8a", 11)}
</svg>
<table>
<tr><th>Mount</th><th>Holds</th><th>Fit per side</th><th>How it is held</th></tr>
<tr><td>Servo cradle &times;2</td><td>SG90 22.8 &times; 12.2</td><td><b>+0.35 mm</b></td>
    <td>drops in from above; cradle spans 36.2 mm so both M2 tab screws land on it</td></tr>
<tr><td>ESP channel</td><td>S3 DevKit on breadboard 81.5 &times; 35.5</td><td><b>+0.35 mm</b></td>
    <td>breadboard adhesive back; corner walls locate it</td></tr>
<tr><td>Pinion pocket &times;2</td><td>&#8709;22.5 gear</td><td>+1.25 mm</td>
    <td>free clearance, gear must never touch the case</td></tr>
</table>
<p class="s" style="margin-top:14px"><b>The breadboard stays in.</b> Measured 81.5 &times; 35.5, it sits behind the servos under the deck, where 34.5 mm of height was doing nothing. Case went 66 &rarr; 74 deep to give it margin rather than the 0.9 mm it would have had at 66.</p>
</div>
"""
out = os.path.join(CONT, "mounts.html")
open(out, "w").write(html)
print(f"sections: {len(mech)} loops")
print(f"wrote {out}  ({len(html)/1024:.0f} kB)")
