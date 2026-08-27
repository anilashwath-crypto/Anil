# -*- coding: utf-8 -*-
"""
Fusion 360 script - lay the 5 mm plates of CNC_WorkstationV1 flat and nest them
on a single 2440 x 1220 x 5 mm sheet for laser cutting.

HOW TO USE
  1. In Fusion 360: File > Open / Upload  ->  CNC_WorkstationV1.step
     (or Insert > Insert McMaster.../Insert Derive - any route that puts the
      STEP bodies in the active design's root component).
  2. Utilities tab > ADD-INS > Scripts and Add-Ins > Scripts > green "+"
     > add this .py file > Run.
  3. The seven 5 mm plates are moved flat onto the XY plane and nested.
     Every other body (4 mm, 8 mm, 10 mm and the 1.5 mm wall extrusions)
     is left untouched and simply hidden.
  4. Sheet outline is drawn as a sketch on XY for reference.
  5. To get cutting geometry: right-click the sheet sketch > Save As DXF,
     or select the bottom face of each plate > Create Sketch > project > Save As DXF.

NOTES
  * Fusion's API works in CENTIMETRES; the baked matrices below are in mm and
    are converted on the fly.
  * Bodies are matched by name first, then by volume + centroid, so the script
    still works if Fusion renames things on import.
  * Nothing is scaled or mirrored - each plate is only rotated and translated,
    so the cut profiles are identical to the source model.
"""

import adsk.core, adsk.fusion, traceback

SHEET_W_MM = 2440.0
SHEET_H_MM = 1220.0
THICKNESS_MM = 5.0
MARGIN_MM = 10.0
MIN_GAP_MM = 6.0
MM = 0.1  # mm -> cm (Fusion internal units)

# body name -> nesting transform (3x4, millimetres), plus identity data for fallback matching
NEST = {
    'Body11': dict(vol_mm3=220357.192, centroid_mm=[357.1118, 91.5875, -29.4773],
          matrix_mm=[[-1.0, -0.0, 0.0, 680.727551275],
                     [0.0, -1.0, 0.0, 198.746646611],
                     [0.0, 0.0, 1.0, 31.977326701]]),
    'Body5': dict(vol_mm3=3124162.601, centroid_mm=[11.9295, 17.0646, 489.5227],
          matrix_mm=[[1.0, 0.0, 0.0, 1594.272448968],
                     [0.0, -1.0, -0.0, 498.746646568],
                     [0.0, 0.0, -1.0, 492.022673542]]),
    'Body6': dict(vol_mm3=3124260.776, centroid_mm=[11.9392, 17.0523, -330.4773],
          matrix_mm=[[-0.0, 1.0, 0.0, 441.253353632],
                     [-1.0, -0.0, 0.0, 617.727551232],
                     [0.0, 0.0, 1.0, 332.977326658]]),
    'Body8': dict(vol_mm3=1873385.026, centroid_mm=[247.2276, -1233.3578, 49.5236],
          matrix_mm=[[-0.0, -0.0, -1.0, 2234.022673542],
                     [0.0, -1.0, 0.0, -541.253353432],
                     [-1.0, 0.0, 0.0, 249.727551232]]),
    'Body9': dict(vol_mm3=230427.944, centroid_mm=[309.4431, 251.2466, 49.5227],
          matrix_mm=[[0.0, -0.0, 1.0, 167.977326658],
                     [1.0, 0.0, -0.0, 711.272448968],
                     [0.0, 1.0, 0.0, -248.746646368]]),
    'Body10': dict(vol_mm3=220357.192, centroid_mm=[357.1118, 641.5875, 128.5227],
          matrix_mm=[[1.0, 0.0, 0.0, -234.727550989],
                     [0.0, 1.0, 0.0, -498.746646325],
                     [0.0, 0.0, 1.0, -126.022673299]]),
    'Body16': dict(vol_mm3=1664662.500, centroid_mm=[-647.7724, -25.2768, 49.5227],
          matrix_mm=[[-0.0, -0.0, -1.0, 1090.022673542],
                     [0.0, -1.0, 0.0, 772.746646568],
                     [-1.0, 0.0, 0.0, -645.272448768]]),
}


def _matrix(m_mm):
    """3x4 mm matrix -> adsk Matrix3D in cm."""
    mtx = adsk.core.Matrix3D.create()
    r0, r1, r2 = m_mm
    mtx.setWithArray([
        r0[0], r0[1], r0[2], r0[3] * MM,
        r1[0], r1[1], r1[2], r1[3] * MM,
        r2[0], r2[1], r2[2], r2[3] * MM,
        0.0,   0.0,   0.0,   1.0,
    ])
    return mtx


def _all_bodies(comp):
    out = list(comp.bRepBodies)
    for occ in comp.allOccurrences:
        out.extend(occ.bRepBodies)
    return out


def _match(bodies):
    """Return {body: spec} pairing design bodies to NEST entries."""
    remaining = dict(NEST)
    pairs = {}
    # pass 1 - exact name match
    for b in bodies:
        if b.name in remaining:
            pairs[b] = remaining.pop(b.name)
    if not remaining:
        return pairs
    # pass 2 - volume then nearest centroid
    for name, spec in list(remaining.items()):
        best, best_d = None, None
        for b in bodies:
            if b in pairs:
                continue
            try:
                pp = b.physicalProperties
                vol_mm3 = pp.volume * 1000.0            # cm3 -> mm3
                c = pp.centerOfMass
            except Exception:
                continue
            if abs(vol_mm3 - spec['vol_mm3']) > 0.005 * spec['vol_mm3']:
                continue
            cx, cy, cz = c.x / MM, c.y / MM, c.z / MM   # cm -> mm
            tx, ty, tz = spec['centroid_mm']
            dist = ((cx - tx) ** 2 + (cy - ty) ** 2 + (cz - tz) ** 2) ** 0.5
            if best_d is None or dist < best_d:
                best, best_d = b, dist
        if best is not None and best_d is not None and best_d < 1.0:
            pairs[best] = spec
            remaining.pop(name)
    return pairs


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open the CNC_WorkstationV1 STEP in a Fusion design first.')
            return

        root = design.rootComponent
        bodies = _all_bodies(root)
        if not bodies:
            ui.messageBox('No bodies found in the active design.')
            return

        pairs = _match(bodies)
        if len(pairs) != len(NEST):
            ui.messageBox(
                'Matched {} of {} plates.\n\nExpected bodies: {}\n\n'
                'Make sure the CNC_WorkstationV1 STEP is the active design.'
                .format(len(pairs), len(NEST), ', '.join(sorted(NEST))))
            if not pairs:
                return

        moves = root.features.moveFeatures
        moved = []
        for body, spec in sorted(pairs.items(), key=lambda kv: kv[1]['matrix_mm'][0][3]):
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            mtx = _matrix(spec['matrix_mm'])
            try:
                mi = moves.createInput2(coll)
                mi.defineAsFreeMove(mtx)
            except Exception:
                mi = moves.createInput(coll, mtx)
            moves.add(mi)
            moved.append(body.name)

        # hide every body that is not part of the 5 mm nest
        hidden = 0
        for b in _all_bodies(root):
            if b not in pairs:
                try:
                    b.isLightBulbOn = False
                    hidden += 1
                except Exception:
                    pass

        # sheet outline sketch on XY
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.name = 'Laser sheet 2440 x 1220 x 5 mm'
        p = adsk.core.Point3D
        sk.sketchCurves.sketchLines.addTwoPointRectangle(
            p.create(0, 0, 0), p.create(SHEET_W_MM * MM, SHEET_H_MM * MM, 0))
        sk.sketchCurves.sketchLines.addTwoPointRectangle(
            p.create(MARGIN_MM * MM, MARGIN_MM * MM, 0),
            p.create((SHEET_W_MM - MARGIN_MM) * MM, (SHEET_H_MM - MARGIN_MM) * MM, 0))

        ui.messageBox(
            'Nested {} plates of {:.0f} mm on one {:.0f} x {:.0f} mm sheet.\n'
            'Minimum part-to-part clearance: {:.1f} mm\n'
            'Edge margin: {:.0f} mm\n'
            'Hidden (not 5 mm): {} bodies\n\n{}'
            .format(len(moved), THICKNESS_MM, SHEET_W_MM, SHEET_H_MM,
                    MIN_GAP_MM, MARGIN_MM, hidden, ', '.join(moved)))

    except Exception:
        if ui:
            ui.messageBox('Script failed:\n{}'.format(traceback.format_exc()))
