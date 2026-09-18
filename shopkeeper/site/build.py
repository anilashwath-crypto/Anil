#!/usr/bin/env python3
"""
Build the shopkeeper NANO page — DOCUMENT OF RECORD.

One self-contained file, no framework, no npm, no network request of any kind.
The 3D viewer is spliced in by MARKER, never by line number, so regenerating
nano/viewer/index.html cannot silently break the page.

Every figure here is either measured from the repo at build time or carried in
CANON below, which was measured this session. Nothing on this page is typed
from memory - that is the whole premise of the design and it has to be true.
"""
import os, re, sys, html, pathlib, json

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
DIST = HERE / "dist"
VIEWER = REPO / "nano" / "viewer" / "index.html"

# ── canonical figures, measured ────────────────────────────────────────────
C = dict(
    w=92, d=74, h=66,
    teeth=16, module=1.25, rp=10.0,
    full=31.42, cmd=26.70, deg=153, reserve=4.72,
    plate1=89.2, plate2=56.1, total=145.3, sliced=124,
    unique=9, objects=12, plates=2,
    gap=0.489, growth=0.20, tip=0.748,
    droop=0.91, neck=2.80, interference=154.89,
    bin_len=51.2, reach=23.7, on_deck=27.6,
    incumbent="20 lakh",
)


def viewer_fragment():
    """Splice by marker. An assert here is cheaper than a broken hero."""
    src = VIEWER.read_text(encoding="utf-8")
    # The FRAGMENT's style block, not the standalone page's <head> theme block.
    # Slicing from the first <style> swallowed </head><body><main> and injected
    # a whole document shell into the middle of this one.
    a = src.rindex("<style>", 0, src.index(".v3d {"))
    b = src.rindex("</script>") + len("</script>")
    frag = src[a:b]
    assert "</head>" not in frag and "<body" not in frag, \
        "viewer slice picked up the page shell"
    assert "16T" in frag, "viewer says the wrong tooth count - run cad/viewer3d.py"
    assert "12T" not in frag, "viewer still contains a stale 12T"
    assert "http://" not in frag and "https://" not in frag, "viewer got a network call"
    return frag


def elevation():
    """Static front elevation. 2.4 KB, zero JS, and it IS the LCP element -
    the canvas mounts afterwards so the fold never waits on it."""
    s = 3.05
    w, h = C["w"] * s, C["h"] * s
    ox, oy = 34, 26
    return f'''<svg class="elev" viewBox="0 0 {w+150:.0f} {h+92:.0f}" role="img"
  aria-label="Front elevation, {C["w"]} by {C["h"]} millimetres, two drawers">
  <g fill="none" stroke="var(--t4)" stroke-width="1">
    <line x1="{ox-16}" y1="{oy+h:.0f}" x2="{ox+w+112:.0f}" y2="{oy+h:.0f}"/>
  </g>
  <rect x="{ox}" y="{oy}" width="{w:.0f}" height="{h:.0f}"
        fill="none" stroke="var(--t2)" stroke-width="1.6"/>
  <g fill="none" stroke="var(--ember)" stroke-width="1" stroke-dasharray="5 4" opacity=".85">
    <line x1="{ox}" y1="{oy+h*0.36:.0f}" x2="{ox+w:.0f}" y2="{oy+h*0.36:.0f}"/>
  </g>
  <g fill="var(--t5)" stroke="var(--t3)" stroke-width="1.2">
    <rect x="{ox+11:.0f}" y="{oy+h*0.46:.0f}" width="{w*0.43:.0f}" height="{h*0.30:.0f}"/>
    <rect x="{ox+w*0.55:.0f}" y="{oy+h*0.46:.0f}" width="{w*0.43:.0f}" height="{h*0.30:.0f}"/>
  </g>
  <g stroke="var(--t4)" stroke-width="1" fill="none">
    <line x1="{ox}" y1="{oy+h+18:.0f}" x2="{ox}" y2="{oy+h+30:.0f}"/>
    <line x1="{ox+w:.0f}" y1="{oy+h+18:.0f}" x2="{ox+w:.0f}" y2="{oy+h+30:.0f}"/>
    <line x1="{ox}" y1="{oy+h+24:.0f}" x2="{ox+w:.0f}" y2="{oy+h+24:.0f}"/>
    <line x1="{ox+w+22:.0f}" y1="{oy}" x2="{ox+w+34:.0f}" y2="{oy}"/>
    <line x1="{ox+w+22:.0f}" y1="{oy+h:.0f}" x2="{ox+w+34:.0f}" y2="{oy+h:.0f}"/>
    <line x1="{ox+w+28:.0f}" y1="{oy}" x2="{ox+w+28:.0f}" y2="{oy+h:.0f}"/>
  </g>
  <text x="{ox+w/2:.0f}" y="{oy+h+40:.0f}" class="dim" text-anchor="middle">{C["w"]}</text>
  <text x="{ox+w+40:.0f}" y="{oy+h/2:.0f}" class="dim">{C["h"]}</text>
  <text x="{ox}" y="{oy-12:.0f}" class="stamp-svg">ELEVATION A-A · MILLIMETRES</text>
</svg>'''


# ── entries ────────────────────────────────────────────────────────────────
# stamp / verb / detail / note. The verb is what the entry DOES to the argument.
ENTRIES = [
    dict(n="00", verb="OPENING", title="A tool cabinet that costs a few lakhs, "
         "against one that costs twenty.",
         note="d datasheet · c claim · e estimate · unmarked = printed by a script here",
         body="""<p class="lede">Industrial smart tool cabinets sell into Indian
         machine shops at roughly <b>&#8377;{incumbent} a cabinet</b>.<sup class="src">c</sup>
         This is a working demonstrator of the same idea, built from
         {total} g of PLA, two hobby servos and a &#8377;600 microcontroller.</p>
         <p>Every number on this page was printed by a script in the repository
         it links to. Where a figure came from a datasheet rather than a
         measurement, it is marked. Where the design failed an audit, the
         failure is on the page.</p>""",
         elev=True),

    dict(n="01", verb="THE OBJECT", title="This is the machine, not a render.",
         note="drag to orbit · the slider drives the real rack-and-pinion kinematics",
         body="""<p>Assembled from the same STLs that go to the printer. The
         drawer stroke is the mechanism's own: one half turn of the
         m{module}&thinsp;&times;&thinsp;{teeth} pinion is
         <b>&pi; &times; {rp} = {full} mm</b>.</p>
         <p class="prov">If both servos die, the drawers pull out by hand. There
         is no solenoid holding them shut.</p>""",
         viewer=True),

    dict(n="02", verb="THE CLAIM", title="The expensive cabinet does not sense "
         "anything either.",
         note="the argument the whole product rests on",
         body="""<p>No load cells. No cameras. No RFID. Inventory in the
         commercial cabinets is <b>trust-based</b><sup class="src">c</sup>
         &mdash; the cabinet records that a drawer opened, not what left it.</p>
         <p>What a shop is buying is <b>controlled access and a record of who
         opened what</b>. That is a lock, a database and a screen. It is not
         twenty lakhs of sensing, because there is no sensing.</p>
         <p class="prov">This page will not claim the demonstrator senses
         anything either. It does not.</p>"""),

    dict(n="03", verb="MECHANISM", title="Rack and pinion, straight off a servo horn.",
         note="cad/nano.py",
         body="""<p>Each drawer carries a toothed blade through a slot in the
         deck. A {teeth}-tooth involute pinion on the servo horn drives it. No
         leadscrew, no belt, no bearings &mdash; two moving parts per drawer.</p>""",
         table=[("Full travel", "{full} mm", "&pi; &times; {rp} mm pitch radius"),
                ("Commanded", "{cmd} mm", "650&ndash;2350 &micro;s = {deg}&deg;"),
                ("Reserve", "{reserve} mm", "never asked for, so it never stalls"),
                ("Gear clearance", "{gap} mm", "tightest gap through a full tooth cycle"),
                ("Still on deck", "{on_deck} mm", "of a 59 mm drawer, fully out")]),

    dict(n="04", verb="THE FINDING", title="An independent audit returned NO-GO.",
         note="six blockers · every one measured before it was believed",
         body="""<p>The first mechanism could not be assembled. Not "needed
         refinement" &mdash; the rack was physically larger than the drawer it
         bolts into. Every blocker below was confirmed against the shipped
         geometry before anything was changed.</p>""",
         ledger=[("Rack inside its own drawer", "{interference} mm&sup3;", "0.00 mm&sup3;",
                  "the flange was bigger than the bin, in both axes"),
                 ("Drawer wall at the peg hole", "0.33 mm", "14.34 mm",
                  "under one extrusion &mdash; the slicer deletes it"),
                 ("Narrowest neck, deck", "0.60 mm", "{neck} mm",
                  "the whole bearing finger hung on it"),
                 ("Gear at +0.10 mm growth", "jams", "0.289 mm",
                  "a trapezoid is a rack profile, not a pinion profile"),
                 ("Blade over the electronics", "0.60 mm", "2.60 mm",
                  "both blades swept the breadboard, full stroke"),
                 ("Nose droop, fully out", "5.14 mm", "{droop} mm",
                  "enough to walk a tooth out of mesh"),
                 ("Fits that will not work", "2", "0",
                  "judged as-printed: a peg grows, its hole shrinks")]),

    dict(n="05", verb="THE GEAR", title="The pinion was the wrong shape, and a "
         "simulation proved it.",
         note="cad/meshsim.py",
         body="""<p>Straight-sided teeth are correct for a rack and wrong for a
         pinion &mdash; 0.26 mm of excess material per flank. The pair met with
         effectively zero clearance and seized at the growth generic PLA
         actually prints at.</p>
         <p>The fix is a true involute flank. The simulation reproduces the old
         profile's jam, which is the only reason to trust it about the new
         one.</p>""",
         table=[("Old profile, nominal", "0.047 mm", "effectively zero"),
                ("Old profile, +0.05 mm", "JAMS", "inside normal PLA growth"),
                ("New profile, nominal", "{gap} mm", "true involute, stub addendum"),
                ("New profile, +0.20 mm", "0.089 mm", "still turning"),
                ("Tooth tip", "{tip} mm", "printable at 0.4 mm nozzle")]),

    dict(n="06", verb="THE TERMINAL", title="The screen is the product.",
         note="firmware/www/index.html · MicroPython on an ESP32-S3",
         body="""<p>PIN-gated access, a live section drawing per bay, a tool
         register and an append-only event ledger. Every open, close, unlock and
         rejected PIN is recorded. A wrong PIN returns
         <b>403 &mdash; denied, logged</b>.</p>
         <p class="prov">The register says SECURED or ACCESSIBLE. It never says
         "present", because nothing here senses presence.</p>"""),

    dict(n="07", verb="LIMITS", title="What this does not do.",
         warn=True,
         note="stated because a buyer will find it in ninety seconds",
         body="""<ul class="lim">
         <li><b>It reaches {reach} mm of a {bin_len} mm bin.</b> A half turn at a
         {rp} mm pitch radius is {full} mm and there is no more. A larger gear
         would cantilever the drawer off its own deck.</li>
         <li><b>It counts nothing.</b> No sensing of any kind. Neither does the
         cabinet it is pitched against, but that is an argument, not a feature.</li>
         <li><b>Two drawers.</b> This is a demonstrator at {w}&thinsp;&times;&thinsp;{d}&thinsp;&times;&thinsp;{h} mm,
         not a shop-floor unit.</li>
         <li><b>Hobby servos.</b> SG90s reach 160&ndash;175&deg; of a nominal 180,
         so the firmware commands {deg}&deg; and keeps {reserve} mm in hand.</li>
         </ul>"""),

    dict(n="08", verb="THE PARTS", title="Two plates. One colour each.",
         note="{unique} unique parts · {objects} printed objects · {plates} plates",
         body="""<p>A single-nozzle machine purges a tower at every colour change,
         so the split is by colour, not by assembly. Swap the spool between
         prints and waste nothing.</p>""",
         table=[("Plate 1 &mdash; case, white", "{plate1} g", "lower body and lid"),
                ("Plate 2 &mdash; mechanism, yellow", "{plate2} g",
                 "deck, drawers, racks, pinions, shims, inlay"),
                ("Total", "{total} g solid", "~{sliced} g sliced")]),

    dict(n="09", verb="PROVENANCE", title="The repository is the evidence.",
         note="MIT licensed",
         body="""<p>Parametric source, the verification scripts, the audit that
         returned NO-GO and every commit that answered it. Run the scripts and
         you will get the numbers on this page, or you will have caught us.</p>
         <p class="prov">The overhang checker still prints <b>NEEDS FIXING</b> on
         both case halves. Those are bridges, and they print. It is on the page
         because softening a script's own verdict is how a document of record
         stops being one.</p>"""),
]


def fmt(s):
    return s.format(**C)


def entry_html(e, i, total):
    cls = "entry" + (" warn" if e.get("warn") else "")
    parts = [f'<section class="{cls}" id="e{e["n"]}" data-n="{e["n"]}">',
             '<div class="rail"><i></i></div>',
             f'<div class="stamp"><span class="lbl">Entry</span><b>{e["n"]}</b>'
             f'<span class="of">/ {total}</span></div>',
             f'<div class="verb">{e["verb"]}</div>',
             '<div class="detail">',
             f'<h2 class="entry-title">{fmt(e["title"])}</h2>']
    if e.get("body"):
        parts.append(fmt(e["body"]))
    if e.get("elev"):
        parts.append(f'<div class="stage stage-elev">{elevation()}</div>')
    if e.get("viewer"):
        parts.append('<div class="stage" id="viewer-mount" '
                     'data-viewer="1"><div class="stage-ph">'
                     '<span class="lbl">3D assembly &mdash; loading</span></div></div>')
    if e.get("table"):
        rows = "".join(
            f'<tr><td class="k">{fmt(a)}</td><td class="v">{fmt(b)}</td>'
            f'<td class="c">{fmt(c)}</td></tr>' for a, b, c in e["table"])
        parts.append(f'<div class="tw"><table class="spec">{rows}</table></div>')
    if e.get("ledger"):
        rows = "".join(
            f'<tr><td class="k">{fmt(a)}</td><td class="was">{fmt(b)}</td>'
            f'<td class="now">{fmt(c)}</td><td class="c">{fmt(d)}</td></tr>'
            for a, b, c, d in e["ledger"])
        parts.append('<div class="tw"><table class="spec led"><thead><tr>'
                     '<th>Check</th><th>Was</th><th>Now</th><th>Why it mattered</th>'
                     f'</tr></thead><tbody>{rows}</tbody></table></div>')
    parts.append('</div>')
    parts.append(f'<div class="note">{fmt(e.get("note",""))}</div>')
    parts.append('</section>')
    return "\n".join(parts)


def build():
    css = (HERE / "src" / "site.css").read_text(encoding="utf-8")
    js = (HERE / "src" / "site.js").read_text(encoding="utf-8")
    n = len(ENTRIES)
    entries = "\n".join(entry_html(e, i, f"{n:02d}") for i, e in enumerate(ENTRIES))
    page = (HERE / "src" / "index.tpl.html").read_text(encoding="utf-8")
    out = (page.replace("__CSS__", css)
               .replace("__ENTRIES__", entries)
               .replace("__VIEWER__", viewer_fragment())
               .replace("__JS__", js)
               .replace("__STROKE__", f'{C["cmd"]} mm / {C["deg"]}&deg;'))
    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(out, encoding="utf-8")

    bad = [t for t in ("http://", "https://", "//cdn", "@import", "<link",
                       "fetch(", "XMLHttpRequest") if t in out]
    assert not bad, f"external reference: {bad}"
    assert "__" not in re.sub(r"__[a-z]", "", out.replace("__DATA__", "")), "unsubstituted marker"
    acc = out.count("--acc")
    print(f"  dist/index.html   {len(out)/1024:.0f} KiB")
    print(f"  entries           {n}")
    print(f"  external refs     none")
    print(f"  accent uses       {acc}")
    return out


if __name__ == "__main__":
    build()
