#!/usr/bin/env python3
"""Assemble the publishable page: spec-sheet shell + the generated viewer."""
import pathlib, re

FRAG = pathlib.Path("/Users/piyushmishra/Desktop/toolcell/.superpowers/brainstorm/"
                    "25158-1786171087/content/viewer3d.html").read_text(encoding="utf-8")
OUT  = pathlib.Path("/private/tmp/claude-501/-Users-piyushmishra/"
                    "2a15a654-3fdb-4209-8c96-2ef1e796f18d/scratchpad/shopkeeper.html")

SHELL = r"""<title>shopkeeper NANO — motorised tool drawer</title>
<style>
/* ── tokens ───────────────────────────────────────────────────────────────
   Palette taken from the shop floor, not from a swatch library: machine-tool
   enamel (that specific green-grey), the signal yellow of the actual filament
   on the plate, and Dykem layout-dye blue — the stuff you paint on steel
   before you scribe it. Neutrals carry the enamel's green bias so they read
   as chosen rather than inherited.                                          */
:root {
  --ink:        #12140F;
  --paper:      #F3F3EE;
  --enamel:     #38423B;
  --signal:     #F2B705;
  --dye:        #1B4FA0;

  --bg-primary:   var(--paper);
  --bg-secondary: #FBFBF8;
  --bg-tertiary:  #E9E9E2;
  --text-primary:   #14170F;
  --text-secondary: #5C6459;
  --text-tertiary:  #8D9489;
  --border: rgba(20,23,15,.14);
  --rule:   rgba(20,23,15,.10);
  --accent: var(--dye);
  --gold:   var(--signal);
  --good:   #2F6B41;
  --was:    #9A3412;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary:   var(--ink);
    --bg-secondary: #191C16;
    --bg-tertiary:  #23271F;
    --text-primary:   #EFEFE8;
    --text-secondary: #9CA396;
    --text-tertiary:  #6C7367;
    --border: rgba(239,239,232,.16);
    --rule:   rgba(239,239,232,.11);
    --accent: #6E9BE8;
    --good:   #6FBF87;
    --was:    #E08A5F;
  }
}
:root[data-theme="dark"] {
  --bg-primary:   var(--ink);
  --bg-secondary: #191C16;
  --bg-tertiary:  #23271F;
  --text-primary:   #EFEFE8;
  --text-secondary: #9CA396;
  --text-tertiary:  #6C7367;
  --border: rgba(239,239,232,.16);
  --rule:   rgba(239,239,232,.11);
  --accent: #6E9BE8;
  --good:   #6FBF87;
  --was:    #E08A5F;
}
:root[data-theme="light"] {
  --bg-primary:   var(--paper);
  --bg-secondary: #FBFBF8;
  --bg-tertiary:  #E9E9E2;
  --text-primary:   #14170F;
  --text-secondary: #5C6459;
  --text-tertiary:  #8D9489;
  --border: rgba(20,23,15,.14);
  --rule:   rgba(20,23,15,.10);
  --accent: var(--dye);
  --good:   #2F6B41;
  --was:    #9A3412;
}

* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg-primary); color: var(--text-primary);
  font: 15.5px/1.62 -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter,
        system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1140px; margin: 0 auto; padding: 40px 24px 80px; }
@media (max-width: 620px) { .wrap { padding: 26px 16px 54px; } }

/* drafting lettering: the closest a system stack gets to the single-stroke
   gothic on an engineering drawing. Used only for labels and figures. */
.mono, .k-lab, .led th, .led td.n, .plate-n, .stat b {
  font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
.k-lab {
  font-size: .655rem; letter-spacing: .16em; text-transform: uppercase;
  color: var(--text-tertiary);
}

/* ── header: a dimension callout ────────────────────────────────────────── */
.hd { display: flex; flex-direction: column; gap: 18px; margin-bottom: 30px; }
.dim { display: flex; align-items: center; gap: 12px; }
.dim .ln { flex: 1; height: 1px; background: var(--rule); position: relative; }
.dim .ln::before, .dim .ln::after {
  content: ""; position: absolute; top: -3px; width: 1px; height: 7px;
  background: var(--text-tertiary);
}
.dim .ln::before { left: 0; } .dim .ln::after { right: 0; }
h1 {
  margin: 0; font-size: clamp(1.85rem, 5.2vw, 2.9rem); line-height: 1.06;
  letter-spacing: -.022em; font-weight: 620; text-wrap: balance;
}
h1 em { font-style: normal; color: var(--text-tertiary); font-weight: 420; }
.sub { margin: 0; max-width: 63ch; color: var(--text-secondary); font-size: 1.02rem; }
.sub b { color: var(--text-primary); font-weight: 600; }

.stats { display: flex; flex-wrap: wrap; gap: 10px; }
.stat {
  border: 1px solid var(--border); border-radius: 3px; padding: 9px 13px;
  background: var(--bg-secondary); display: flex; flex-direction: column; gap: 2px;
}
.stat b { font-size: 1.02rem; font-weight: 600; letter-spacing: -.01em; }
.stat span { font-size: .655rem; letter-spacing: .13em; text-transform: uppercase;
             color: var(--text-tertiary); }

/* ── the viewer sits in its own frame ───────────────────────────────────── */
.viewer-frame { margin: 34px 0 12px; }
.cap { display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap;
       margin-top: 10px; font-size: .8rem; color: var(--text-tertiary); }

/* ── section furniture ──────────────────────────────────────────────────── */
section { margin-top: 46px; }
h2 { margin: 0 0 4px; font-size: 1.16rem; font-weight: 620; letter-spacing: -.012em; }
.lede { margin: 0 0 18px; color: var(--text-secondary); max-width: 66ch; font-size: .95rem; }

/* ── verification ledger ────────────────────────────────────────────────── */
.led-scroll { overflow-x: auto; border: 1px solid var(--border); border-radius: 3px; }
.led { width: 100%; border-collapse: collapse; font-size: .85rem; min-width: 560px; }
.led th {
  text-align: left; font-weight: 500; font-size: .625rem; letter-spacing: .14em;
  text-transform: uppercase; color: var(--text-tertiary);
  padding: 10px 14px; background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border); white-space: nowrap;
}
.led td { padding: 10px 14px; border-bottom: 1px solid var(--rule);
          vertical-align: baseline; }
.led tr:last-child td { border-bottom: 0; }
.led td.n { white-space: nowrap; font-size: .82rem; }
.led .was { color: var(--was); }
.led .now { color: var(--good); font-weight: 600; }
.led td.w { color: var(--text-secondary); }

/* ── plates ─────────────────────────────────────────────────────────────── */
.plates { display: grid; grid-template-columns: repeat(auto-fit, minmax(248px, 1fr));
          gap: 12px; }
.plate { border: 1px solid var(--border); border-radius: 3px; padding: 16px 17px;
         background: var(--bg-secondary); display: flex; flex-direction: column; gap: 9px; }
.plate-n { font-size: .68rem; letter-spacing: .14em; text-transform: uppercase;
           color: var(--text-tertiary); display: flex; justify-content: space-between; }
.plate h3 { margin: 0; font-size: 1rem; font-weight: 600; }
.plate p { margin: 0; font-size: .855rem; color: var(--text-secondary); }
.swatch { width: 100%; height: 3px; border-radius: 2px; }

/* ── open items ─────────────────────────────────────────────────────────── */
.open { display: flex; flex-direction: column; gap: 0; border: 1px solid var(--border);
        border-radius: 3px; overflow: hidden; }
.open div { padding: 13px 16px; border-bottom: 1px solid var(--rule);
            display: grid; grid-template-columns: 128px 1fr; gap: 14px; font-size: .885rem; }
.open div:last-child { border-bottom: 0; }
.open dt { color: var(--text-tertiary); font-family: ui-monospace, Menlo, monospace;
           font-size: .7rem; letter-spacing: .1em; text-transform: uppercase;
           padding-top: 2px; }
.open dd { margin: 0; color: var(--text-secondary); }
.open dd b { color: var(--text-primary); font-weight: 600; }
@media (max-width: 560px) { .open div { grid-template-columns: 1fr; gap: 4px; } }

.foot { margin-top: 46px; padding-top: 18px; border-top: 1px solid var(--rule);
        font-size: .79rem; color: var(--text-tertiary); }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>

<div class="wrap">

  <header class="hd">
    <div class="dim">
      <span class="k-lab">92 &times; 74 &times; 66 mm</span>
      <span class="ln"></span>
      <span class="k-lab">145 g PLA &middot; ~124 g sliced</span>
    </div>
    <h1>shopkeeper <em>NANO</em></h1>
    <p class="sub">A two-drawer motorised tool cabinet, driven by rack and pinion off
    two SG90 servos. Built as a sales demonstrator against the industrial smart
    tool cabinets that sell into Indian machine shops at roughly
    <b>&#8377;20 lakh a cabinet</b>. Everything below is measured off the meshes that
    go to the printer &mdash; not computed from the drawing.</p>
    <div class="stats">
      <div class="stat"><b>2</b><span>drawers</span></div>
      <div class="stat"><b>31.4 mm</b><span>full travel</span></div>
      <div class="stat"><b>m1.25 &times; 16T</b><span>involute pinion</span></div>
      <div class="stat"><b>0.489 mm</b><span>gear clearance</span></div>
      <div class="stat"><b>9 parts</b><span>unique &middot; 12 printed</span></div>
    </div>
  </header>

  <div class="viewer-frame">
    __VIEWER__
    <div class="cap">
      <span>Drag to orbit &middot; scroll to zoom &middot; the slider drives the real rack-and-pinion kinematics</span>
      <span class="mono">13,343 triangles &middot; 17,119 drawn per frame &middot; no external assets</span>
    </div>
  </div>

  <section>
    <h2>What the audit found, and what it measures now</h2>
    <p class="lede">An independent design review returned <b>NO-GO</b> on the first
    mechanism. Six blockers, every one confirmed against the shipped geometry before
    anything was changed. These are the same numbers the check scripts print.</p>
    <div class="led-scroll">
      <table class="led">
        <thead><tr><th>Check</th><th>Was</th><th>Now</th><th>Why it mattered</th></tr></thead>
        <tbody>
          <tr><td>Rack inside its own drawer</td>
              <td class="n was">154.89 mm&sup3;</td><td class="n now">0.00 mm&sup3;</td>
              <td class="w">The flange was bigger than the bin it drops into, in both axes. Unassemblable.</td></tr>
          <tr><td>Drawer wall beside the peg hole</td>
              <td class="n was">0.33 mm</td><td class="n now">14.34 mm</td>
              <td class="w">Under one extrusion width &mdash; the slicer deletes it and opens the drawer's side.</td></tr>
          <tr><td>Narrowest neck, deck</td>
              <td class="n was">0.60 mm</td><td class="n now">2.80 mm</td>
              <td class="w">The whole left bearing finger hung on it. Snaps on bed removal.</td></tr>
          <tr><td>Gear clearance at +0.10 mm print growth</td>
              <td class="n was">jams</td><td class="n now">0.289 mm</td>
              <td class="w">The pinion was a trapezoid &mdash; correct for a rack, wrong for a pinion. Now a true involute.</td></tr>
          <tr><td>Rack blade over the electronics</td>
              <td class="n was">0.60 mm</td><td class="n now">2.60 mm</td>
              <td class="w">Both blades swept the breadboard for the full stroke. One dupont lead would have caught.</td></tr>
          <tr><td>Nose droop, drawer fully out</td>
              <td class="n was">5.14 mm</td><td class="n now">0.91 mm</td>
              <td class="w">Enough to walk a tooth out of mesh. The rear wall now catches the bay ceiling.</td></tr>
          <tr><td>Fits that will not work</td>
              <td class="n was">2</td><td class="n now">0</td>
              <td class="w">Judged as-printed, not nominal: a peg grows and its hole shrinks, and both go against the clearance.</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Two plates, one colour each</h2>
    <p class="lede">A single-nozzle machine purges a tower at every colour change.
    Splitting by colour rather than by assembly costs nothing and wastes nothing
    &mdash; swap the spool between prints.</p>
    <div class="plates">
      <div class="plate">
        <div class="swatch" style="background:#EDEDF2"></div>
        <div class="plate-n"><span>Plate 1</span><span>89.2 g</span></div>
        <h3>Case, white</h3>
        <p>Lower body and lid. The lid prints top-face-down so the Ommi Forge mark
        forms against the bed &mdash; the crispest surface the machine makes.</p>
      </div>
      <div class="plate">
        <div class="swatch" style="background:#F2B705"></div>
        <div class="plate-n"><span>Plate 2</span><span>56.1 g</span></div>
        <h3>Mechanism, yellow</h3>
        <p>Deck, two drawers, two racks, two pinions, two servo shims and the logo
        inlay. Ten separately selectable objects.</p>
      </div>
    </div>
  </section>

  <section>
    <h2>Still open</h2>
    <p class="lede">Stated rather than buried. None of it blocks printing.</p>
    <div class="open">
      <div><dt>Servo height</dt><dd>The SG90's horn face is taken as <b>26.5 mm</b>
        from a datasheet, not measured. It sets the pinion height &mdash; so it lives in
        a <b>1.6 g shim</b>, not in the 89 g case. Wrong number, reprint the shim.</dd></div>
      <div><dt>Servo sweep</dt><dd>Full travel needs <b>180.0&deg;</b> of an SG90's
        nominal 180&deg;. Clones give 160&ndash;175&deg;, so the shipped firmware commands
        650&ndash;2350 &micro;s &mdash; <b>153&deg;</b> &mdash; and takes <b>26.7 mm</b> of the
        31.4 available, leaving <b>4.72 mm</b> in reserve. Firmware, not geometry.</dd></div>
      <div><dt>Case fasteners</dt><dd>The halves are held by <b>three pins</b> and
        nothing else. Fine on a desk; a transport lock or four M3 would be better in a bag.</dd></div>
      <div><dt>Servo endpoints</dt><dd>The firmware is written and runs on the bench
        board &mdash; PIN gate, append-only log, live calibration &mdash; but the
        <b>650&ndash;2350 &micro;s</b> endpoints are a deliberately conservative default,
        not a measurement. They get set by eye against the printed drawer.</dd></div>
    </div>
  </section>

  <p class="foot">Geometry generated parametrically and verified by boolean interference
  sweep, ray-cast overhang analysis, first-layer neck erosion, as-printed fit measurement,
  and a conjugate-motion gear simulation that reproduces the original profile's jam.
  Model shown is the shipped STL set.</p>

</div>
"""

page = SHELL.replace("__VIEWER__", FRAG)
OUT.write_text(page, encoding="utf-8")

# guard: the CSP blocks every external host, so prove there are none
bad = [t for t in ("http://", "https://", "//cdn", "@import", "fetch(",
                   "XMLHttpRequest", "<link", "importScripts") if t in page]
assert "__VIEWER__" not in page, "viewer not substituted"
assert not bad, f"external references: {bad}"
assert page.count("<title>") == 1
print(f"wrote {OUT}  ({len(page)/1024:.0f} KiB)")
print(f"external references: none")
