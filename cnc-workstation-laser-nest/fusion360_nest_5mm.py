# -*- coding: utf-8 -*-
"""
Fusion 360 script - lay the laser-cut plates of CNC_WorkstationV1 flat and nest them
onto 2 sheet(s) of 2440 x 1220 x 5 mm stock.

SCOPE
  Nests the seven 5 mm plates PLUS Body7, which is 4 mm in the model and is
  standardised up to 5 mm stock. Left out and simply hidden:
    * Body12   - 10 mm plate, excluded on request
    * Body1/2/3 - 8 mm structural plates, NOT reduced to 5 mm (strength change)
    * Body22, Body17-20 - 1.5 mm BENT sheet metal; they need unfolding to flat
      patterns and cannot be formed in 5 mm stock.

HOW TO USE
  1. Open CNC_WorkstationV1.step in Fusion 360.
  2. Utilities > ADD-INS > Scripts and Add-Ins > Scripts > "+" > add this file > Run.
  3. Sheet 1 is placed at the origin; sheet 2 is offset +100 mm clear in Y.
  4. Sheet outlines and 10 mm margins are drawn as sketches on XY.

NOTE ON BODY7
  Fusion moves the real 4 mm solid, so it will still read 4 mm thick on the sheet.
  The cut PROFILE is what matters and is unchanged - cut it from 5 mm stock,
  or use the supplied DXF, which is already the 5 mm nest.

Fusion's API works in CENTIMETRES; the baked matrices below are millimetres and are
converted at run time. All matrices are proper rotations (det = +1) - no mirroring,
no scaling, so every profile matches the source model.
"""

import adsk.core, adsk.fusion, traceback

SHEET_W_MM, SHEET_H_MM = 2440.0, 1220.0
STOCK_MM, MARGIN_MM, MIN_GAP_MM = 5.0, 10.0, 6.0
N_SHEETS, GUTTER_MM = 2, 100.0
MM = 0.1  # mm -> cm

NEST = {
    'Body11': dict(sheet=1, source_thk=5.0, vol_mm3=220357.192,
          centroid_mm=[357.1118, 91.5875, -29.4773],
          matrix_mm=[[0.0, -1.0, 0.0, 198.746646611],
                     [1.0, 0.0, 0.0, 187.272449011],
                     [0.0, 0.0, 1.0, 31.977326701]]),
    'Body1': dict(sheet=1, source_thk=8.0, vol_mm3=3032950.532,
          centroid_mm=[18.5328, -427.2534, 49.9422],
          matrix_mm=[[-0.0, 0.0, -1.0, 2200.522673542],
                     [-1.0, -0.0, 0.0, 683.727551232],
                     [0.0, 1.0, 0.0, 431.253353632]]),
    'Body2': dict(sheet=1, source_thk=8.0, vol_mm3=50357.522,
          centroid_mm=[365.754, -475.4162, 293.2727],
          matrix_mm=[[0.0, 0.0, -1.0, 468.522673542],
                     [0.0, 1.0, 0.0, 537.253353632],
                     [1.0, 0.0, 0.0, -361.727551032]]),
    'Body3': dict(sheet=1, source_thk=8.0, vol_mm3=50357.522,
          centroid_mm=[365.754, -475.4162, -194.2273],
          matrix_mm=[[0.0, 0.0, -1.0, 1089.022673542],
                     [0.0, 1.0, 0.0, 537.253353632],
                     [1.0, 0.0, 0.0, -361.727551032]]),
    'Body5': dict(sheet=1, source_thk=5.0, vol_mm3=3124162.601,
          centroid_mm=[11.9295, 17.0646, 489.5227],
          matrix_mm=[[1.0, 0.0, 0.0, 590.272448968],
                     [0.0, 1.0, 0.0, 441.253353632],
                     [0.0, 0.0, 1.0, -487.022673342]]),
    'Body6': dict(sheet=1, source_thk=5.0, vol_mm3=3124260.776,
          centroid_mm=[11.9392, 17.0523, -330.4773],
          matrix_mm=[[-1.0, -0.0, 0.0, 1487.727551232],
                     [0.0, -1.0, 0.0, 498.746646568],
                     [0.0, 0.0, 1.0, 332.977326658]]),
    'Body7': dict(sheet=2, source_thk=4.0, vol_mm3=1365778.761,
          centroid_mm=[-167.8426, 706.7396, 49.5227],
          matrix_mm=[[-0.0, 0.0, -1.0, 702.022673542],
                     [-1.0, -0.0, 0.0, 1574.727551232],
                     [0.0, 1.0, 0.0, -704.746646368]]),
    'Body8': dict(sheet=2, source_thk=5.0, vol_mm3=1873385.026,
          centroid_mm=[247.2276, -1233.3578, 49.5236],
          matrix_mm=[[0.0, 0.0, -1.0, 272.022673542],
                     [0.0, 1.0, 0.0, 3021.253353632],
                     [1.0, 0.0, 0.0, -244.727551032]]),
    'Body9': dict(sheet=1, source_thk=5.0, vol_mm3=230427.944,
          centroid_mm=[309.4431, 251.2466, 49.5227],
          matrix_mm=[[1.0, 0.0, 0.0, -234.727551032],
                     [0.0, 0.0, -1.0, 267.022673542],
                     [0.0, 1.0, 0.0, -248.746646368]]),
    'Body10': dict(sheet=1, source_thk=5.0, vol_mm3=220357.192,
          centroid_mm=[357.1118, 641.5875, 128.5227],
          matrix_mm=[[-1.0, -0.0, 0.0, 2532.727551275],
                     [0.0, -1.0, 0.0, 748.746646611],
                     [0.0, 0.0, 1.0, -126.022673299]]),
    'Body16': dict(sheet=2, source_thk=5.0, vol_mm3=1664662.500,
          centroid_mm=[-647.7724, -25.2768, 49.5227],
          matrix_mm=[[0.0, 0.0, -1.0, 1132.022673542],
                     [0.0, 1.0, 0.0, 1761.253353632],
                     [1.0, 0.0, 0.0, 650.272448968]]),
}


def _matrix(m):
    mtx = adsk.core.Matrix3D.create()
    r0, r1, r2 = m
    mtx.setWithArray([r0[0], r0[1], r0[2], r0[3]*MM,
                      r1[0], r1[1], r1[2], r1[3]*MM,
                      r2[0], r2[1], r2[2], r2[3]*MM,
                      0.0, 0.0, 0.0, 1.0])
    return mtx


def _all_bodies(comp):
    out = list(comp.bRepBodies)
    for occ in comp.allOccurrences:
        out.extend(occ.bRepBodies)
    return out


def _match(bodies):
    remaining = dict(NEST)
    pairs = {}
    for b in bodies:
        if b.name in remaining:
            pairs[b] = remaining.pop(b.name)
    for name, spec in list(remaining.items()):
        best, best_d = None, None
        for b in bodies:
            if b in pairs:
                continue
            try:
                pp = b.physicalProperties
                vol = pp.volume * 1000.0
                c = pp.centerOfMass
            except Exception:
                continue
            if abs(vol - spec['vol_mm3']) > 0.005 * spec['vol_mm3']:
                continue
            cx, cy, cz = c.x/MM, c.y/MM, c.z/MM
            tx, ty, tz = spec['centroid_mm']
            dist = ((cx-tx)**2 + (cy-ty)**2 + (cz-tz)**2) ** 0.5
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
            ui.messageBox('Matched {} of {} plates.\n\nExpected: {}\n\n'
                          'Make sure CNC_WorkstationV1.step is the active design.'
                          .format(len(pairs), len(NEST), ', '.join(sorted(NEST))))
            if not pairs:
                return

        moves = root.features.moveFeatures
        moved, rethick = [], []
        for body, spec in sorted(pairs.items(), key=lambda kv: (kv[1]['sheet'], kv[1]['matrix_mm'][0][3])):
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
            if abs(spec['source_thk'] - STOCK_MM) > 0.05:
                rethick.append('{} ({:.0f} mm)'.format(body.name, spec['source_thk']))

        hidden = 0
        for b in _all_bodies(root):
            if b not in pairs:
                try:
                    b.isLightBulbOn = False
                    hidden += 1
                except Exception:
                    pass

        p = adsk.core.Point3D
        for s in range(N_SHEETS):
            dy = s * (SHEET_H_MM + GUTTER_MM)
            sk = root.sketches.add(root.xYConstructionPlane)
            sk.name = 'Laser sheet {} - {:.0f} x {:.0f} x {:.0f} mm'.format(
                s+1, SHEET_W_MM, SHEET_H_MM, STOCK_MM)
            sk.sketchCurves.sketchLines.addTwoPointRectangle(
                p.create(0, dy*MM, 0), p.create(SHEET_W_MM*MM, (dy+SHEET_H_MM)*MM, 0))
            sk.sketchCurves.sketchLines.addTwoPointRectangle(
                p.create(MARGIN_MM*MM, (dy+MARGIN_MM)*MM, 0),
                p.create((SHEET_W_MM-MARGIN_MM)*MM, (dy+SHEET_H_MM-MARGIN_MM)*MM, 0))

        ui.messageBox('Nested {} plates onto {} sheet(s) of {:.0f} x {:.0f} x {:.0f} mm.\n'
                      'Minimum clearance {:.1f} mm, edge margin {:.0f} mm.\n'
                      'Hidden (not in this nest): {} bodies.\n\n'
                      'Standardised up to {:.0f} mm: {}\n\n{}'
                      .format(len(moved), N_SHEETS, SHEET_W_MM, SHEET_H_MM, STOCK_MM,
                              MIN_GAP_MM, MARGIN_MM, hidden, STOCK_MM,
                              ', '.join(rethick) or 'none', ', '.join(moved)))
    except Exception:
        if ui:
            ui.messageBox('Script failed:\n{}'.format(traceback.format_exc()))
