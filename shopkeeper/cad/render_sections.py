#!/usr/bin/env python3
"""
Slice the REAL generated meshes and emit an animated page from them.

Every outline on the page is a cross-section of the actual STL that goes to
the printer — not a diagram. If the fin misses the slot or the pinion does not
reach the rack, it will be visible here.
"""
import os, math
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
MINI = os.path.join(HERE, "..", "mini")
CONT = ("/Users/piyushmishra/Desktop/toolcell/.superpowers/brainstorm/"
        "25158-1786171087/content")

# geometry constants, mirroring cad/mini.py
WL, SC, DECK, FINH = 2.5, 1.6, 30.0, 9.0
CW, CD, CH = 120.0, 90.0, 80.0
DR_D, TRAVEL = 77.5, 33.0
M, N = 1.5, 14
R_P = M * N / 2
FIN_X = (CW - 2*WL - 2*SC) * 0.42
FIN_T, TOOTH_H = 3.5, 2.25*M
FIN_SPAN = FIN_T + TOOTH_H
PIN_X = FIN_X - FIN_T/2 + (FIN_SPAN - M) + R_P
PIN_Y = 28.0

case = trimesh.load(os.path.join(MINI, "case.stl"))
draw = trimesh.load(os.path.join(MINI, "drawer.stl"))
pin  = trimesh.load(os.path.join(MINI, "pinion.stl"))

y_closed = (CD - WL - 1.5) - draw.extents[1]
DX, DY, DZ = WL + SC, y_closed, DECK - FINH + 0.2

def polys(mesh, origin, normal, dx=0.0, dy=0.0):
    """Cross-section -> list of 2D point lists, in the section's own plane."""
    # deliberately NOT wrapped in try/except: a swallowed exception here
    # renders a silently blank page, which is worse than a crash
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        raise RuntimeError(f"no section at {origin} / {normal}")
    p2d, to3 = sec.to_planar()
    out = []
    for d in p2d.discrete:
        pts = np.asarray(d, dtype=float)
        # map back to world so every section shares one coordinate frame
        h = np.column_stack([pts, np.zeros(len(pts)), np.ones(len(pts))])
        w = (to3 @ h.T).T[:, :3]
        if abs(normal[2]) > 0.5:          # plan view -> x,y
            out.append([(p[0] + dx, p[1] + dy) for p in w])
        else:                             # side view -> y,z
            out.append([(p[1] + dy, p[2] + dx) for p in w])
    return out

def path(polylist, scale, ox, oy, flipy=True, H=0.0):
    d = []
    for pl in polylist:
        if len(pl) < 2:
            continue
        pts = [(ox + a*scale, (oy + (H - b)*scale) if flipy else (oy + b*scale))
               for a, b in pl]
        d.append("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z")
    return " ".join(d)

S = 3.2                                    # px per mm

# ── PLAN at the fin/pinion height ──────────────────────────────────────
zc = DECK - FINH/2 + 0.2                   # mid-fin
case_plan = polys(case, [0, 0, zc], [0, 0, 1])
draw_plan = polys(draw, [0, 0, zc - DZ], [0, 0, 1], dx=DX, dy=DY)
pin_plan  = polys(pin,  [0, 0, 3.0], [0, 0, 1])

# ── SIDE at the pinion x ───────────────────────────────────────────────
xs = WL + SC + PIN_X
case_side = polys(case, [xs, 0, 0], [1, 0, 0])
draw_side = polys(draw, [xs - DX, 0, 0], [1, 0, 0], dx=DZ, dy=DY)

PW, PH = CW*S + 60, CD*S + 60
SW, SH = CD*S + 60, CH*S + 60

pin_cx = (WL + SC + PIN_X)*S + 30
pin_cy = (CD - (WL + PIN_Y))*S + 30

html = f"""<style>
.rs {{ --ln:#8a8a8a; --gold:#f2b705; --grn:#3fa87a; --blu:#5f9fd0; }}
.rs svg {{ display:block; width:100%; height:auto; background:rgba(138,138,138,.05);
          border:1px solid rgba(138,138,138,.3); border-radius:8px; }}
.rs .case {{ fill:rgba(138,138,138,.22); stroke:#8a8a8a; stroke-width:1.2; fill-rule:evenodd; }}
.rs .draw {{ fill:rgba(242,183,5,.45); stroke:#f2b705; stroke-width:1.4; fill-rule:evenodd; }}
.rs .pin  {{ fill:rgba(63,168,122,.55); stroke:#3fa87a; stroke-width:1.2; fill-rule:evenodd; }}
.rs .slide {{ animation:sl 9s infinite ease-in-out; }}
@keyframes sl {{ 0%,14%{{transform:translateY(0)}} 30%,52%{{transform:translateY({TRAVEL*S:.1f}px)}}
                 70%,100%{{transform:translateY(0)}} }}
.rs .spin {{ transform-box:view-box; transform-origin:{pin_cx:.1f}px {pin_cy:.1f}px;
             animation:sp 9s infinite ease-in-out; }}
@keyframes sp {{ 0%,14%{{transform:rotate(0)}} 30%,52%{{transform:rotate(180deg)}}
                 70%,100%{{transform:rotate(0)}} }}
.rs .slideS {{ animation:slS 9s infinite ease-in-out; }}
@keyframes slS {{ 0%,14%{{transform:translateX(0)}} 30%,52%{{transform:translateX(-{TRAVEL*S:.1f}px)}}
                  70%,100%{{transform:translateX(0)}} }}
.rs-box {{ border:1px solid rgba(138,138,138,.35); border-radius:10px; padding:18px; margin-bottom:20px; }}
.rs-note {{ font-size:12.5px; opacity:.75; line-height:1.6; margin-top:8px; }}
</style>

<div class="rs">
<h2>Sections through the real STLs</h2>
<p class="subtitle">Everything below is cut from the actual mesh that goes to the printer &mdash; grey is <code>case.stl</code>, yellow is <code>drawer.stl</code>, green is <code>pinion.stl</code>. If the fin missed the slot or the pinion could not reach the rack, you would see it here.</p>

<div class="rs-box">
  <h3 style="margin-top:0">Plan, cut at the fin height (z = {zc:.1f} mm)</h3>
  <svg viewBox="0 0 {PW:.0f} {PH:.0f}">
    <path class="case" d="{path(case_plan, S, 30, 30, H=CD)}"/>
    <g class="slide"><path class="draw" d="{path(draw_plan, S, 30, 30, H=CD)}"/></g>
    <g class="spin"><path class="pin" d="{path([[(x+WL+SC+PIN_X, y+WL+PIN_Y) for x,y in pl] for pl in pin_plan], S, 30, 30, H=CD)}"/></g>
  </svg>
  <p class="rs-note">The yellow blade running front-to-back is the drive fin, <strong>with its teeth</strong>. The grey gap it sits in is the deck slot. Green is the pinion, turning 180&deg;. Watch that the teeth stay meshed and the fin never touches grey.</p>
</div>

<div class="rs-box">
  <h3 style="margin-top:0">Side section, cut through the pinion (x = {xs:.1f} mm)</h3>
  <svg viewBox="0 0 {SW:.0f} {SH:.0f}">
    <path class="case" d="{path(case_side, S, 30, 30, H=CH)}"/>
    <g class="slideS"><path class="draw" d="{path(draw_side, S, 30, 30, H=CH)}"/></g>
  </svg>
  <p class="rs-note">Front of the case is on the left. The drawer rides on the deck and drives out {TRAVEL:.0f} mm. Below the deck is the servo and pinion cavity; above it, the OLED window and the keypad aperture in the top.</p>
</div>

<div class="rs-box">
  <h3 style="margin-top:0">One drive per drawer &mdash; nothing is shared</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <tr><th style="text-align:left;padding:6px 10px;border:1px solid rgba(138,138,138,.3)"></th>
        <th style="text-align:left;padding:6px 10px;border:1px solid rgba(138,138,138,.3)">MINI</th>
        <th style="text-align:left;padding:6px 10px;border:1px solid rgba(138,138,138,.3)">Full cabinet</th></tr>
    <tr><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">Drawers</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">1</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">2</td></tr>
    <tr><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">Servos</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">1</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)"><b>2 &mdash; one per bay</b></td></tr>
    <tr><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">Pinions</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">1 + 1 spare</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)"><b>2 &mdash; one per bay</b></td></tr>
    <tr><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">Bay part</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)">the case itself</td><td style="padding:6px 10px;border:1px solid rgba(138,138,138,.3)"><code>case_bay</code> printed twice</td></tr>
  </table>
  <p class="rs-note">A single pinion could never drive two drawers &mdash; they need independent positions. Each bay is a self-contained unit: its own servo well, its own pinion pocket, its own closed-switch mount, on its own GPIO pair.</p>
</div>
</div>
"""

out = os.path.join(CONT, "real-sections.html")
open(out, "w").write(html)
print(f"plan outlines: case {len(case_plan)}, drawer {len(draw_plan)}, pinion {len(pin_plan)}")
print(f"side outlines: case {len(case_side)}, drawer {len(draw_side)}")
assert case_plan and draw_plan and pin_plan, "empty plan section"
assert case_side and draw_side, "empty side section"
print(f"wrote {out}")
