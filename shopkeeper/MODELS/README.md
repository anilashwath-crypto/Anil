# MODELS — every part, ready to use

Everything needed to make this cabinet, in one place. **Start with `STL/`.**

| folder | format | use it for |
|---|---|---|
| **`STL/`** | STL, mm | 3D printing, and 3D CAM. **Start here.** |
| `OBJ/` | OBJ, mm | importing into almost any 3D tool |
| `PLATES-3MF/` | 3MF | slicer-ready plates — orientation and arrangement already set |
| `DXF/` | DXF, mm, R2010 | flat profiles for laser, waterjet or 2D profile cutting |

Same geometry in every folder. One generator, one export — nothing is a
hand-edited copy.

## The parts

| file | size, mm | what it is |
|---|---|---|
| `case_lower` | 92 × 74 × 46 | base — servo wells, electronics bay |
| `case_upper` | 92 × 74 × 24 | lid — drawer mouths, display window, LED holes |
| `deck` | 87.4 × 69.4 × 2.5 | plate the drawers ride on, bored for the gears |
| `drawer` | 38.8 × 59 × 31.2 | ×2 — bin with its drive teeth printed on |
| `pinion` | 14.5 × 14 × 9.7 | ×2 — m1.25, 10 teeth, 14.5° |
| `servo_shim` | 22.9 × 12.3 × 4.6 | ×2 — sets servo height, so gear height |
| `logo_inlay` | 14.7 × 11.5 × 1.6 | pressed into the lid |
| `spline_gauge` | 71 × 13 × 5.6 | test piece for servo spline fit |
| `knob` | 11 × 11 × 13 | optional pull |
| `rack` | 16.5 × 53 × 15 | superseded — the drawer carries its own teeth now |

Whole machine: **140 g of PLA over two plates**, no filament changes.

## If you are printing

Use `PLATES-3MF/plate_1_case.3mf` and `plate_2_mechanism.3mf`. Print
orientation is already set — `case_upper` is flipped and printed top-face-down
so the debossed mark forms against the bed, and `pinion` prints gear-face-down.

`plate_ALL.3mf` is for looking at, not printing: it declares materials, so a
slicer will stop and ask you to map filaments.

## If you are machining

The DXF profiles are exact — a section through the mesh is a real polygon.

**There is no STEP file.** STEP is a boundary representation with true surfaces
and exact arcs; this geometry is a triangle mesh, authored for a printer.
Converting one to the other does not recover what was never there — you get a
solid built from thousands of facets that imports cleanly and machines badly,
because every cylinder is really a polygon.

For proper B-rep, rebuild from `../cad/nano.py`: every dimension is a named
entry in the `P` dict at the top of that file and each part function reads as a
recipe. Half a day for a CAD operator. The quick alternative is importing the
STL into Fusion or FreeCAD and converting to solid — faceted, but fine for a
one-off.

## Regenerating

```sh
.venv/bin/python cad/nano.py         # the parts themselves
.venv/bin/python cad/export_cam.py   # this folder
```

Units are millimetres throughout.
