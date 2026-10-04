#!/usr/bin/env python3
"""
Trace the Ommi Forge mark from a bitmap into a 2D polygon for debossing.

Pixel runs -> shapely boxes -> one unary_union -> simplify. Doing the union in
2D and extruding once is far cheaper than booleaning hundreds of little prisms
in 3D, and it keeps the mesh small.
"""
import glob, os
import numpy as np
from PIL import Image
from shapely.geometry import box
from shapely.ops import unary_union

SRC_GLOB = os.path.expanduser("~/Desktop/Screenshot*5.37*.png")


def trace(width_px=190, thresh=140, src=None):
    """Return a shapely geometry of the dark ink, normalised to a 1.0-wide box."""
    path = src or sorted(glob.glob(SRC_GLOB))[-1]
    im = Image.open(path).convert("L")
    w0, h0 = im.size
    h_px = max(1, round(width_px * h0 / w0))
    im = im.resize((width_px, h_px), Image.LANCZOS)
    a = np.asarray(im)
    ink = a < thresh                       # dark pixels are the mark

    # trim to the ink's bounding box so the mark fills its frame
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    ink = ink[rows.min():rows.max()+1, cols.min():cols.max()+1]
    H, W = ink.shape

    # run-length per row -> one box each
    boxes = []
    for r in range(H):
        row = ink[r]
        c = 0
        while c < W:
            if row[c]:
                c0 = c
                while c < W and row[c]:
                    c += 1
                # +0.02 overlap so adjacent rows weld instead of leaving seams
                boxes.append(box(c0, H - r - 1, c, H - r + 0.02))
            else:
                c += 1
    geom = unary_union(boxes).buffer(0.01).buffer(-0.01)
    geom = geom.simplify(0.35, preserve_topology=True)

    # normalise: longest side -> 1.0, centred on the origin
    minx, miny, maxx, maxy = geom.bounds
    s = 1.0 / max(maxx - minx, maxy - miny)
    from shapely.affinity import scale, translate
    geom = translate(geom, -(minx + maxx) / 2, -(miny + maxy) / 2)
    geom = scale(geom, s, s, origin=(0, 0))
    return geom, path


if __name__ == "__main__":
    g, p = trace()
    print(f"  source   {os.path.basename(p)}")
    print(f"  polygons {len(g.geoms) if hasattr(g,'geoms') else 1}")
    print(f"  bounds   {tuple(round(v,3) for v in g.bounds)}")
    print(f"  vertices {len(g.exterior.coords) if g.geom_type=='Polygon' else sum(len(x.exterior.coords) for x in g.geoms)}")
    print(f"  area     {g.area:.4f}  (of a 1.0 x 1.0 frame)")
