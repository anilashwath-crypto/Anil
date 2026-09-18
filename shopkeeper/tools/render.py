#!/usr/bin/env python3
"""
A small software renderer, because there is no GPU path here.

pyrender and pyglet both want an OpenGL context this environment does not
have, so this rasterises in numpy: perspective camera, z-buffer, three-point
lighting, fresnel rim, and a planar projected shadow blurred into the
background. Supersampled and box-filtered down, which is where most of the
apparent quality comes from.

Everything is driven off the real meshes and the real kinematics - the
mechanism animation turns the pinion by theta and translates the rack by
-R_P*theta, which is the same relation the firmware commands.
"""
import numpy as np
from scipy.ndimage import gaussian_filter

# ── palette ───────────────────────────────────────────────────────────────
BG_TOP, BG_BOT = (0x12, 0x14, 0x17), (0x08, 0x09, 0x0B)
GRAPHITE = (0x30, 0x34, 0x3A)
STEEL    = (0x9A, 0xA3, 0xAD)
SIGNAL   = (0xFF, 0x6B, 0x1A)
EMBER    = (0xC2, 0x38, 0x1C)
DECKC    = (0x23, 0x26, 0x2A)
BRASS    = (0xD9, 0xA5, 0x4B)


def look_at(eye, target, up=(0, 0, 1)):
    eye, target = np.array(eye, float), np.array(target, float)
    f = target - eye; f /= np.linalg.norm(f)
    r = np.cross(f, np.array(up, float)); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, np.stack([r, u, f])


def _bg(H, W):
    t = np.linspace(0, 1, H)[:, None, None]
    return (np.array(BG_TOP) * (1 - t) + np.array(BG_BOT) * t) \
        .repeat(W, 1).astype(np.float64)


def _project(V, eye, B, f, W, H):
    c = (V - eye) @ B.T                      # camera space, +z forward
    z = np.maximum(c[:, 2], 1e-6)
    return np.stack([W/2 + f * c[:, 0] / z,
                     H/2 - f * c[:, 1] / z], 1), c[:, 2]


def _raster(tris_s, tris_z, shade, W, H, zbuf, cbuf):
    """tris_s (n,3,2) screen, tris_z (n,3) depth, shade (n,3) rgb 0..1."""
    for s, zs, col in zip(tris_s, tris_z, shade):
        if (zs <= 1e-4).any():
            continue
        x0 = max(int(np.floor(s[:, 0].min())), 0)
        x1 = min(int(np.ceil(s[:, 0].max())) + 1, W)
        y0 = max(int(np.floor(s[:, 1].min())), 0)
        y1 = min(int(np.ceil(s[:, 1].max())) + 1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        xs = np.arange(x0, x1) + 0.5
        ys = np.arange(y0, y1) + 0.5
        px, py = np.meshgrid(xs, ys)
        ax, ay = s[0]; bx, by = s[1]; cx, cy = s[2]
        d = (by - cy)*(ax - cx) + (cx - bx)*(ay - cy)
        if abs(d) < 1e-12:
            continue
        w0 = ((by - cy)*(px - cx) + (cx - bx)*(py - cy)) / d
        w1 = ((cy - ay)*(px - cx) + (ax - cx)*(py - cy)) / d
        w2 = 1.0 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any():
            continue
        # perspective-correct depth: 1/z is linear in screen space
        iz = w0/zs[0] + w1/zs[1] + w2/zs[2]
        z = np.where(iz > 0, 1.0/np.maximum(iz, 1e-12), 1e9)
        sub = zbuf[y0:y1, x0:x1]
        hit = m & (z < sub)
        if not hit.any():
            continue
        sub[hit] = z[hit]
        cbuf[y0:y1, x0:x1][hit] = col


def render(objs, eye, target, W=1200, H=780, fov=32.0, ss=2,
           lights=((0.55, -0.75, 0.95, 1.00),
                   (-0.85, -0.35, 0.35, 0.34),
                   (0.10, 0.90, 0.30, 0.22)),
           shadow=True, ground=None, up=(0, 0, 1)):
    """objs: list of (vertices, faces, rgb, opts). Returns HxWx3 uint8."""
    Wi, Hi = W*ss, H*ss
    eye, B = look_at(eye, target, up)
    f = (Hi/2) / np.tan(np.radians(fov)/2)
    cbuf = _bg(Hi, Wi)
    zbuf = np.full((Hi, Wi), 1e9)

    if shadow:
        z0 = ground if ground is not None else min(
            v[:, 2].min() for v, _, _, _ in objs)
        L = np.array([0.45, -0.55, 1.0]); L /= np.linalg.norm(L)
        # 3-channel because _raster writes an rgb triple per pixel; a flat
        # (H,W) buffer makes the boolean assignment fail on the first triangle
        mask = np.zeros((Hi, Wi, 3))
        mz = np.full((Hi, Wi), 1e9)
        for V, F, _, _ in objs:
            P = V.copy()
            t = (P[:, 2] - z0) / L[2]
            P = P - L[None, :] * t[:, None]
            P[:, 2] = z0
            s, zc = _project(P, eye, B, f, Wi, Hi)
            _raster(s[F], zc[F], np.ones((len(F), 3)), Wi, Hi, mz, mask)
        mask = gaussian_filter(mask[:, :, 0], sigma=9*ss)
        mask = np.clip(mask*1.9, 0, 1)[:, :, None]
        cbuf *= (1.0 - 0.72*mask)

    for V, F, rgb, opt in objs:
        n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.maximum(ln, 1e-12)
        cen = V[F].mean(1)
        view = eye - cen
        view /= np.linalg.norm(view, axis=1, keepdims=True)
        n = np.where((n*view).sum(1, keepdims=True) < 0, -n, n)   # face camera

        base = np.array(rgb, float)/255.0
        lit = np.full(len(F), 0.13)                                # ambient
        spec = np.zeros(len(F))
        for lx, ly, lz, amp in lights:
            L = np.array([lx, ly, lz]); L /= np.linalg.norm(L)
            d = np.maximum((n*L).sum(1), 0)
            lit += amp * d
            Hh = L + view; Hh /= np.linalg.norm(Hh, axis=1, keepdims=True)
            spec += amp * np.maximum((n*Hh).sum(1), 0)**opt.get("gloss", 26)
        rim = (1 - np.maximum((n*view).sum(1), 0))**3
        col = base[None, :]*lit[:, None] \
            + spec[:, None]*opt.get("spec", 0.35) \
            + rim[:, None]*np.array(opt.get("rim", (0.30, 0.34, 0.40)))
        col = np.clip(col, 0, 1)*255.0

        s, zc = _project(V, eye, B, f, Wi, Hi)
        order = np.argsort(-zc[F].mean(1))     # far to near helps coplanar ties
        _raster(s[F][order], zc[F][order], col[order], Wi, Hi, zbuf, cbuf)

    img = cbuf.reshape(H, ss, W, ss, 3).mean((1, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def obj(mesh, rgb, **opt):
    return (np.asarray(mesh.vertices, float),
            np.asarray(mesh.faces, np.int64), rgb, opt)


def moved(mesh, dx=0.0, dy=0.0, dz=0.0):
    m = mesh.copy(); m.apply_translation([dx, dy, dz]); return m


def spun(mesh, deg, about=(0, 0)):
    import trimesh
    m = mesh.copy()
    m.apply_translation([-about[0], -about[1], 0])
    m.apply_transform(trimesh.transformations.rotation_matrix(
        np.radians(deg), [0, 0, 1]))
    m.apply_translation([about[0], about[1], 0])
    return m
