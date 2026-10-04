"""Minimal, correct 3MF writer.

trimesh 5.0's exporter writes objects into <resources> but leaves <build>
empty, so slicers open a plate with nothing on it. It also discards names.
This writes both, and keeps the names.
"""
import zipfile

CT = ('<?xml version="1.0" encoding="UTF-8"?>\n'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
      '</Types>')

RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>')


def write_3mf(path, items, materials=None, extruder=1):
    """items: (name, mesh, x, y) or (name, mesh, x, y, material_index).
    materials: list of (name, "#RRGGBBAA"). Mesh must already sit at z=0."""
    res, build = [], []
    mat = ""
    if materials:
        bases = "".join(f'<base name="{n}" displaycolor="{c}"/>' for n, c in materials)
        mat = f'<basematerials id="100">{bases}</basematerials>'
    for i, it in enumerate(items, start=1):
        name, m, tx, ty = it[0], it[1], it[2], it[3]
        pa = f' pid="100" pindex="{it[4]}"' if (materials and len(it) > 4) else ""
        v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>'
                    for a, b, c in m.vertices)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                    for a, b, c in m.faces)
        res.append(f'<object id="{i}" type="model" name="{name}"{pa}>'
                   f'<mesh><vertices>{v}</vertices>'
                   f'<triangles>{t}</triangles></mesh></object>')
        build.append(f'<item objectid="{i}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {tx:.4f} {ty:.4f} 0"/>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
           '<metadata name="Application">ToolCell generator</metadata>'
           f'<resources>{mat}{"".join(res)}</resources>'
           f'<build>{"".join(build)}</build></model>')
    # Bambu will not slice objects whose filament is unstated - it asks for a
    # mapping it has nothing to map. Assign every object to filament 1
    # explicitly. This is single-filament: no basematerials, one extruder.
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for i, it in enumerate(items, start=1):
        cfg.append(f'<object id="{i}">'
                   f'<metadata key="name" value="{it[0]}"/>'
                   f'<metadata key="extruder" value="{extruder}"/>'
                   f'<part id="{i}" subtype="normal_part">'
                   f'<metadata key="name" value="{it[0]}"/>'
                   f'<metadata key="extruder" value="{extruder}"/>'
                   f'</part></object>')
    cfg.append("</config>")
    ct = CT.replace('</Types>',
                    '<Default Extension="config" ContentType="application/xml"/>'
                    '</Types>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", xml)
        z.writestr("Metadata/model_settings.config", "".join(cfg))
    return len(items)


def verify(path):
    """Returns (objects, build_items). They must be equal."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("3D/3dmodel.model").decode()
    return xml.count("<object id="), xml.count("<item objectid=")


PLATE_STRIDE = 266.0        # Bambu lays plates side by side in one global scene


def write_3mf_plates(path, plates, materials=None):
    """One file, several Bambu plates.

    plates: list of (plate_name, [(obj_name, mesh, x, y, material_index), ...])
    Objects are offset by PLATE_STRIDE per plate so they land on their own bed,
    and Metadata/model_settings.config assigns each to its plater_id.
    """
    res, build, cfg_obj, cfg_plate = [], [], [], []
    oid = 0
    mat = ""
    if materials:
        bases = "".join(f'<base name="{n}" displaycolor="{c}"/>' for n, c in materials)
        mat = f'<basematerials id="100">{bases}</basematerials>'
    for pi, (pname, items) in enumerate(plates):
        ids = []
        for it in items:
            oid += 1
            ids.append(oid)
            name, m, tx, ty = it[0], it[1], it[2], it[3]
            pa = f' pid="100" pindex="{it[4]}"' if (materials and len(it) > 4) else ""
            v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>'
                        for a, b, c in m.vertices)
            t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                        for a, b, c in m.faces)
            res.append(f'<object id="{oid}" type="model" name="{name}"{pa}>'
                       f'<mesh><vertices>{v}</vertices>'
                       f'<triangles>{t}</triangles></mesh></object>')
            build.append(f'<item objectid="{oid}" transform="1 0 0 0 1 0 0 0 1 '
                         f'{tx + pi*PLATE_STRIDE:.4f} {ty:.4f} 0"/>')
            cfg_obj.append(
                f'<object id="{oid}"><metadata key="name" value="{name}"/>'
                f'<metadata key="extruder" value="1"/>'
                f'<part id="{oid}" subtype="normal_part">'
                f'<metadata key="name" value="{name}"/></part></object>')
        inst = "".join(
            f'<model_instance><metadata key="object_id" value="{i}"/>'
            f'<metadata key="instance_id" value="0"/></model_instance>' for i in ids)
        cfg_plate.append(
            f'<plate><metadata key="plater_id" value="{pi+1}"/>'
            f'<metadata key="plater_name" value="{pname}"/>'
            f'<metadata key="locked" value="false"/>{inst}</plate>')

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
           '<metadata name="Application">ToolCell generator</metadata>'
           f'<resources>{mat}{"".join(res)}</resources>'
           f'<build>{"".join(build)}</build></model>')
    cfg = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
           + "".join(cfg_obj) + "".join(cfg_plate) + '</config>')
    ct = CT.replace('</Types>',
                    '<Default Extension="config" ContentType="application/xml"/>'
                    '</Types>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", xml)
        z.writestr("Metadata/model_settings.config", cfg)
    return oid
