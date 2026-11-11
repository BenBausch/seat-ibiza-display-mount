"""Preview images for ibiza_screen_holder.py (runs inside FreeCAD's python).

Small numpy z-buffer rasterizer (flat shading + feature/silhouette edges),
plus a 2D side section with the air path.
"""
import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.path import Path  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from FreeCAD import Vector as V  # noqa: E402

COL = {
    "body": (0.22, 0.47, 0.82),
    "plug": (0.96, 0.58, 0.12),
    "clip": (0.18, 0.72, 0.38),
    "screen": (0.13, 0.13, 0.15),
    "glass": (0.22, 0.30, 0.44),
    "dash": (0.66, 0.66, 0.68),
    "housings": (0.80, 0.80, 0.82),
    "media": (0.30, 0.30, 0.33),
    "gauge": (0.85, 0.30, 0.30),
    "lid": (0.55, 0.38, 0.80),
}


def tris(shape, tol=0.35):
    pts, fac = shape.tessellate(tol)
    if not fac:
        return np.zeros((0, 3, 3))
    P = np.array([[p.x, p.y, p.z] for p in pts])
    return P[np.array(fac)]


def moved(s, dx=0, dy=0, dz=0):
    c = s.copy()
    c.translate(V(dx, dy, dz))
    return c


def render(items, eye_dir, size=(1500, 950), ss=2, fov=28.0, title=None, up=(0, 1, 0)):
    """items: list of (shape, colour key). eye_dir: direction from target to camera (model coords)."""
    T_all, C_all, ID_all = [], [], []
    for i, (shape, key) in enumerate(items):
        T = tris(shape)
        if len(T) == 0:
            continue
        T_all.append(T)
        C_all.append(np.repeat(np.array(COL[key])[None, :], len(T), 0))
        ID_all.append(np.full(len(T), i + 1))
    T = np.concatenate(T_all)
    C = np.concatenate(C_all)
    IDs = np.concatenate(ID_all)

    # camera
    pts = T.reshape(-1, 3)
    center = (pts.min(0) + pts.max(0)) / 2.0
    radius = np.linalg.norm(pts.max(0) - pts.min(0)) / 2.0
    f = -np.asarray(eye_dir, float)
    f /= np.linalg.norm(f)
    u = np.asarray(up, float)
    r = np.cross(f, u)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    dist = radius / np.tan(np.radians(fov / 2.0)) * 1.05
    eye = center - f * dist

    W, H = size[0] * ss, size[1] * ss
    rel = T - eye
    xc = rel @ r
    yc = rel @ u
    zc = rel @ f                        # depth (positive in front)
    foc = (min(W, H) / 2.0) / np.tan(np.radians(fov / 2.0))
    sx = W / 2.0 + foc * xc / zc
    sy = H / 2.0 - foc * yc / zc

    # flat shading (two-sided), light from upper-left-front of the camera
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
    L = -f * 0.8 + u * 0.55 - r * 0.35
    L /= np.linalg.norm(L)
    k = 0.30 + 0.70 * np.abs(n @ L)
    spec = np.clip(np.abs(n @ L), 0, 1) ** 24 * 0.18
    shade = np.clip(C * k[:, None] + spec[:, None], 0, 1)

    zbuf = np.full((H, W), np.inf)
    img = np.ones((H, W, 3))
    nbuf = np.zeros((H, W, 3))
    ibuf = np.zeros((H, W), dtype=np.int32)

    for t in range(len(T)):
        x0, x1, x2 = sx[t]
        y0, y1, y2 = sy[t]
        xmin = int(max(np.floor(min(x0, x1, x2)), 0))
        xmax = int(min(np.ceil(max(x0, x1, x2)), W - 1))
        ymin = int(max(np.floor(min(y0, y1, y2)), 0))
        ymax = int(min(np.ceil(max(y0, y1, y2)), H - 1))
        if xmax < xmin or ymax < ymin:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            continue
        X, Y = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
        a = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        b = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        c = 1.0 - a - b
        m = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
        if not m.any():
            continue
        iz = a / zc[t, 0] + b / zc[t, 1] + c / zc[t, 2]
        z = 1.0 / iz
        sub = zbuf[ymin:ymax + 1, xmin:xmax + 1]
        w = m & (z < sub)
        if not w.any():
            continue
        sub[w] = z[w]
        img[ymin:ymax + 1, xmin:xmax + 1][w] = shade[t]
        nbuf[ymin:ymax + 1, xmin:xmax + 1][w] = n[t] * (1 if (n[t] @ f) < 0 else -1)
        ibuf[ymin:ymax + 1, xmin:xmax + 1][w] = IDs[t]

    # edges: part id change, depth jump, normal crease
    edge = np.zeros((H, W), bool)
    zf = np.where(np.isinf(zbuf), 1e9, zbuf)
    for dy, dx in ((0, 1), (1, 0)):
        a_id, b_id = ibuf[:H - dy, :W - dx], ibuf[dy:, dx:]
        za, zb = zf[:H - dy, :W - dx], zf[dy:, dx:]
        na, nb = nbuf[:H - dy, :W - dx], nbuf[dy:, dx:]
        both = (a_id > 0) & (b_id > 0)
        e = (a_id != b_id) | (both & (np.abs(za - zb) > 0.012 * np.minimum(za, zb))) | \
            (both & ((na * nb).sum(-1) < 0.80))
        edge[:H - dy, :W - dx] |= e
    img[edge] *= 0.25
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize(size, Image.LANCZOS)
    if title:
        d = ImageDraw.Draw(im)
        d.text((14, 10), title, fill=(30, 30, 30))
    return im


def section(ax, P, D, shapes, x):
    """shapes: list of (world-frame shape, colour key, alpha, zorder). Plots w (towards cabin) vs h (up)."""
    for shape, key, alpha, z in shapes:
        ws = shape.slice(V(1, 0, 0), x)
        if not ws:
            continue
        verts, codes = [], []
        for w in ws:
            pts = [(p.z, p.y) for p in w.discretize(Distance=0.4)]
            verts.extend(pts)
            codes.extend([Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY])
        ax.add_patch(PathPatch(Path(verts, codes), facecolor=COL[key], edgecolor="k", lw=0.6,
                               alpha=alpha, zorder=z))
    F = D["F"]
    red = dict(color="tab:red", lw=2.5)
    # air path: from the duct, up the box, out of the lid towards the cabin
    yb, zb = F.s2l(30, -P["t_front"] - 8)
    p_mid = (F.w(yb, zb), F.h(yb, zb))
    p_in = (F.w(0, -25), F.h(0, -25))
    ax.annotate("", xy=p_mid, xytext=p_in,
                arrowprops=dict(arrowstyle="-|>", connectionstyle="arc3,rad=-0.3", **red), zorder=5)
    p_lid = (p_mid[0] + 2, D["h_top"] - 6)
    ax.annotate("", xy=p_lid, xytext=(p_mid[0], p_mid[1] + 6), arrowprops=dict(arrowstyle="-", **red), zorder=5)
    g = np.radians(P["outlet_angle"])
    ax.annotate("", xy=(p_lid[0] + 45 * np.sin(g), D["h_top"] + 45 * np.cos(g)), xytext=p_lid,
                arrowprops=dict(arrowstyle="-|>", **red), zorder=5)
    ax.text(p_lid[0] + 40 * np.sin(g) + 4, D["h_top"] + 36 * np.cos(g), "air %.0f° back\nfrom vertical"
            % P["outlet_angle"], color="tab:red", fontsize=9)
    ax.text(p_in[0] - 3, p_in[1] + 4, "air from\nvent duct", color="tab:red", fontsize=9, ha="right")
    # angles
    ax.axhline(D["h_top"], color="tab:green", lw=0.8, ls="--")
    ax.text(-38, D["h_top"] + 1.5, "lid top = level, %.1f mm below screen top" % 0.5, color="tab:green", fontsize=8)
    ys, zs = F.s2l(55, P["pad"] + P["scr_t"] + 4)
    ax.text(F.w(ys, zs) + 6, F.h(ys, zs), "screen leans back\n%.1f° from vertical"
            % (P["dash_angle"] - P["screen_tilt"]), fontsize=9)
    yd, zd = 70, -15
    ax.text(F.w(yd, zd) - 4, F.h(yd, zd), "dash %.0f°" % P["dash_angle"], fontsize=8, ha="right")
    ax.set_aspect("equal")
    ax.set_xlim(-60, 105)
    ax.set_ylim(D["Yb"] - 25, D["h_top"] + 45)
    ax.set_xlabel("horizontal, towards the cabin [mm]")
    ax.set_ylabel("height [mm]  (0 = vent centre)")
    ax.grid(alpha=0.3)
    ax.set_title("Side section as installed (x = %.0f mm, through one vent)" % x, fontsize=11)


def render_all(P, D, body, lid, plugs, clamps, dm, gauge, out):
    F = D["F"]
    Wd = F.to_world
    b, l = Wd(body), Wd(lid)
    pl = [Wd(p) for p in plugs]
    cl = [Wd(c) for c in clamps]
    d = {k: Wd(v) for k, v in dm.items()}

    assembled = [(d["dash"], "dash"), (d["housings"], "housings"), (d["media"], "media"),
                 (b, "body"), (l, "lid"), (cl[0], "clip"), (cl[1], "clip"),
                 (d["screen"], "screen"), (d["glass"], "glass")]
    render(assembled, (-0.55, 0.35, 1.0), title="Assembled as installed: body (blue), lid (purple), side clamps (green)"
           ).save(os.path.join(out, "preview_assembled.png"))

    no_screen = [(d["dash"], "dash"), (d["housings"], "housings"), (d["media"], "media"),
                 (b, "body"), (l, "lid"), (cl[0], "clip"), (cl[1], "clip")]
    render(no_screen, (0.5, 0.45, 1.0), title="Without screen: cradle, cable slots, lid vanes"
           ).save(os.path.join(out, "preview_holder.png"))

    exploded = [(d["housings"], "housings"),
                (Wd(moved(plugs[0], dz=-40)), "plug"), (Wd(moved(plugs[1], dz=-40)), "plug"),
                (b, "body"), (moved(l, dy=45), "lid"),
                (moved(cl[0], dx=-30), "clip"), (moved(cl[1], dx=30), "clip"),
                (moved(d["screen"], dy=25, dz=75), "screen"), (moved(d["glass"], dy=25, dz=75), "glass")]
    render(exploded, (-0.75, 0.5, 1.0), title="Exploded: plugs -> body -> lid; screen slides in from above; side clamps"
           ).save(os.path.join(out, "preview_exploded.png"))

    back = [(b, "body"), (l, "lid"), (Wd(moved(plugs[0], dz=-30)), "plug"), (Wd(moved(plugs[1], dz=-30)), "plug")]
    render(back, (0.6, 0.35, -1.0), title="Back side: plugs bolt onto the air inlets"
           ).save(os.path.join(out, "preview_back.png"))

    tiles = [render([(pl[1], "plug")], (0.5, 0.6, -1.0), size=(560, 480), title="Vent plug (print 2x)"),
             render([(l, "lid")], (-0.3, 1.0, 0.6), size=(560, 480), title="Lid (vanes blow towards the cabin)"),
             render([(l, "lid")], (0.2, -0.8, 0.7), size=(560, 480), title="Lid from below"),
             render([(cl[1], "clip")], (1.0, 0.5, 0.8), size=(560, 480), title="Side clamp (L + R)"),
             render([(gauge, "gauge")], (-0.3, 0.9, 1.0), size=(560, 480), title="Fit gauge (print first)")]
    sheet = Image.new("RGB", (560 * 5, 480), "white")
    for i, tl in enumerate(tiles):
        sheet.paste(tl, (i * 560, 0))
    sheet.save(os.path.join(out, "preview_small_parts.png"))

    fig, ax = plt.subplots(figsize=(9, 9), dpi=120)
    sec = [(d["dash"], "dash", 0.8, 1), (d["housings"], "housings", 1, 1), (d["media"], "media", 0.9, 1),
           (d["screen"], "screen", 0.9, 1), (b, "body", 0.95, 2), (l, "lid", 0.95, 2)] + \
          [(p, "plug", 1, 3) for p in pl]
    section(ax, P, D, sec, D["vx"][1] - 12.0)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "preview_section.png"))
    plt.close(fig)
