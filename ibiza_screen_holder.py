"""
Seat Ibiza 6J / 6P facelift (2015-2017) centre-vent screen holder
for the Antika 10.26" wireless CarPlay / Android Auto screen (ASIN B0DTDL3L7K).

Concept (v2)
------------
* Two flanged PLUGS go into the round centre-vent housings (vent nozzles removed).
* The BODY is a wedge-shaped air box bolted to both plugs. Its front face (the
  cradle) is tilted `screen_tilt` degrees towards the cabin relative to the vent
  face, so the box gets deeper towards the top where the air leaves.
* A separate LID closes the box. Its top face is level with the ground (needs
  the real `dash_angle`) and never higher than the screen's top edge. Angled
  vanes in the lid blow the air up and BACKWARDS towards the cabin, over the
  screen.
* The screen stands on a ledge with a front lip and is clamped at its two top
  corners by SIDE CLAMPS that grip the side edges (nothing above the screen).
  The screen slides in from above.
* Cables come out of the vent duct through a plug into the air box and leave
  through slots in the side walls right behind the screen's side edges, at the
  height of the screen's side ports.

Frames (all mm / degrees)
-------------------------
  local  : X right (seen from the seats), Y up along the vent face (0 = vent centre
           line), Z out of the vent face towards the cabin (0 = vent bezel face)
  screen : rotated +screen_tilt about X;  s = up along the screen (0 = screen
           bottom edge), n = screen normal (0 = cradle face)
  world  : rotated +dash_angle about X;   h = height (level ground), w = horizontal
           towards the cabin

Run
---
  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd ibiza_screen_holder.py
Edit params.json (any key from DEFAULTS) and re-run.  NO_RENDER=1 skips previews.
"""
import os
import sys
import json
import math

import FreeCAD as App
import Part
import MeshPart
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT = os.path.join(HERE, "out")
BIG = 3000.0

DEFAULTS = {
    # ---------------- CAR: please measure ----------------
    "vent_spacing": 130.0,   # centre-to-centre distance of the two centre vents (horizontal)
    "vent_id": 76.0,         # inner diameter of the vent housing with the nozzle removed
    "housing_od": 92.0,      # outer diameter of the round vent bezel at its front face
    "dash_angle": 20.0,      # how far the vent bezel faces lean back from vertical (phone level app)
    "plug_depth": 18.0,      # how deep the plug goes into the housing (must be < free depth)
    "plug_clear": 0.6,       # diametral clearance plug body vs vent_id (fingers + bumps grip)
    "plug_bump": 0.5,        # radial height of the snap bumps on the plug fingers
    "plug_wall": 2.0,
    # ---------------- SCREEN: Antika 10.26" (please measure yours) ----------------
    "scr_w": 245.0,
    "scr_h": 100.0,
    "scr_t": 20.0,           # thickness at the edges (front glass to flat back)
    "spine_w": 46.0,         # channel width for the rear camera spine / mount socket
    "spine_d": 16.0,         # channel depth
    "cam_w": 44.0,           # lid cut-out behind the channel for the dash-cam head
    "cam_d": 30.0,           # ... how far behind the screen back it reaches
    "scr_bottom": -46.0,     # screen bottom edge (at the cradle) relative to vent centre line
    "port_s0": 24.0,         # side ports start this far below the screen top edge
    "port_s1": 80.0,         # ... and end this far below the top edge
    # ---------------- HOLDER ----------------
    "screen_tilt": 10.0,     # screen top tilted this much towards the cabin vs the vent face
    "outlet_angle": 45.0,    # air leaves the lid this far from vertical, towards the cabin
    "wall": 3.0,
    "t_back": 3.0,
    "t_front": 3.0,
    "air_gap": 16.0,         # free depth of the air box at the screen's bottom edge
    "t_flange": 4.0,
    "side_margin": 2.0,      # body extends this far beyond the vent bezels left/right
    "lid_t": 3.0,
    "vane_depth": 8.0,       # how far the lid vanes hang into the box
    "vane_slot": 4.5,        # slot width between vanes (horizontal)
    "vane_pitch": 7.0,
    "ledge_t": 4.0,
    "lip_h": 5.0,
    "lip_t": 3.0,
    "pad": 1.0,              # felt pad allowance (behind / under / beside the screen)
    "clamp_len": 20.0,       # length of the side clamps along the screen edge
    "clamp_gap": 1.0,        # clamp-to-body gap = clamping travel when the screws are tightened
    "cable_side": "both",    # cable exit slot(s): left / right / both  (seen from the seats)
    "cable_slot_w": 12.0,
    "cable_slot_len": 36.0,  # slot length along the screen edge, centred on the port zone
}


# ----------------------------------------------------------------------------
# helpers / frames
# ----------------------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cylz(cx, cy, r, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(cx, cy, z0), V(0, 0, 1))


def prism_x(poly_yz, x0, x1):
    pts = [V(x0, y, z) for (y, z) in poly_yz]
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(x1 - x0, 0, 0))


def prism_z(poly_xy, z0, z1):
    pts = [V(x, y, z0) for (x, y) in poly_xy]
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, z1 - z0))


def fuse_all(shapes):
    return shapes[0] if len(shapes) == 1 else shapes[0].multiFuse(shapes[1:])


def rotx(shape, deg):
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(1, 0, 0), deg)
    return s


class Frames:
    def __init__(self, P, D):
        self.a = math.radians(P["dash_angle"])
        self.b = math.radians(P["screen_tilt"])
        self.Oy, self.Oz = D["Os_y"], D["Os_z"]
        self.ad, self.bd = P["dash_angle"], P["screen_tilt"]

    # point conversions (y, z only; x is shared)
    def s2l(self, s, n):
        cb, sb = math.cos(self.b), math.sin(self.b)
        return self.Oy + s * cb - n * sb, self.Oz + s * sb + n * cb

    def l2s(self, y, z):
        cb, sb = math.cos(self.b), math.sin(self.b)
        dy, dz = y - self.Oy, z - self.Oz
        return dy * cb + dz * sb, -dy * sb + dz * cb

    def h(self, y, z):
        return y * math.cos(self.a) + z * math.sin(self.a)

    def w(self, y, z):
        return -y * math.sin(self.a) + z * math.cos(self.a)

    def w2l(self, h, w):
        ca, sa = math.cos(self.a), math.sin(self.a)
        return h * ca - w * sa, h * sa + w * ca

    def s_at_h(self, n, h):
        """screen-frame s where the line n = const reaches world height h"""
        cb, sb = math.cos(self.b), math.sin(self.b)
        ca, sa = math.cos(self.a), math.sin(self.a)
        A = (self.Oy - n * sb) * ca + (self.Oz + n * cb) * sa
        return (h - A) / math.cos(self.a - self.b)

    # shape conversions
    def S(self, shape):          # built in screen frame (x, y=s, z=n) -> local
        s = rotx(shape, self.bd)
        s.translate(V(0, self.Oy, self.Oz))
        return s

    def Wd(self, shape):         # built in world frame (x, y=h, z=w) -> local
        return rotx(shape, self.ad)

    def to_world(self, shape):   # local -> world (y = up, z = towards cabin)
        return rotx(shape, -self.ad)

    def sbox(self, x0, x1, s0, s1, n0, n1):
        return self.S(box(x0, x1, s0, s1, n0, n1))

    def wbox(self, x0, x1, h0, h1, w0, w1):
        return self.Wd(box(x0, x1, h0, h1, w0, w1))


def load_params():
    P = dict(DEFAULTS)
    pj = os.path.join(HERE, "params.json")
    if os.path.exists(pj):
        with open(pj) as f:
            user = json.load(f)
        unknown = [k for k in user if k not in DEFAULTS and not k.startswith("_")]
        if unknown:
            print("WARNING: unknown keys in params.json ignored:", unknown)
        P.update({k: v for k, v in user.items() if k in DEFAULTS})
    return P


# ----------------------------------------------------------------------------
# derived geometry
# ----------------------------------------------------------------------------
def derive(P):
    D = {}
    S = P["vent_spacing"]
    D["vx"] = (-S / 2.0, S / 2.0)
    D["W"] = S + P["housing_od"] + 2 * P["side_margin"]
    D["plug_od"] = P["vent_id"] - P["plug_clear"]
    D["plug_id"] = D["plug_od"] - 2 * P["plug_wall"]
    D["rc"] = D["plug_od"] / 2.0 + 5.5
    D["flange_r"] = D["rc"] + 5.0
    D["col_r"] = 4.6
    D["z_b0"] = P["t_flange"]
    D["z_b1"] = D["z_b0"] + P["t_back"]
    D["Os_y"] = P["scr_bottom"]
    D["Os_z"] = D["z_b1"] + P["air_gap"] + P["t_front"]
    F = Frames(P, D)
    D["F"] = F
    pad = P["pad"]
    D["s_top"] = pad + P["scr_h"]                          # screen top edge
    D["n_lip0"] = pad + P["scr_t"] + 0.5
    D["n_lip1"] = D["n_lip0"] + P["lip_t"]
    # heights: lid top a hair below the screen's top/back corner (lowest top point of the screen)
    D["h_top"] = F.h(*F.s2l(D["s_top"], pad)) - 0.5
    D["h_rim"] = D["h_top"] - P["lid_t"]
    yl, _ = F.s2l(-P["ledge_t"], D["n_lip1"])
    D["Yb"] = min(yl, -D["flange_r"] - 1.5)
    # plug bolts (90/210/330 deg around each vent)
    D["screws"] = [(cx + D["rc"] * math.cos(math.radians(a)), D["rc"] * math.sin(math.radians(a)))
                   for cx in D["vx"] for a in (90, 210, 330)]

    def zc_at(y):   # local Z of the cradle face at local height y
        s = (y - F.Oy) / math.cos(F.b)
        return F.Oz + s * math.sin(F.b)
    D["zc_at"] = zc_at
    zmin = min(zc_at(y) for (_, y) in D["screws"])
    L = 12
    for L in (30, 25, 20, 16, 12):
        if 0.5 + L <= zmin - 3.3:
            break
    D["screw_len"] = L
    D["cb_z"] = 0.5 + L
    # end blocks (lid screws + clamp screws), 45 deg underside
    D["blk_w"] = 16.0
    D["x_blk"] = D["W"] / 2.0 - P["wall"] - D["blk_w"]
    s_fr = F.s_at_h(-P["t_front"], D["h_rim"])
    D["y_rim_front"] = F.s2l(s_fr, -P["t_front"])[0]
    D["y_blk"] = D["y_rim_front"] - 16.0
    # lid screws: vertical (world), near the back of the end blocks
    zb = D["z_b1"] + 5.0
    yb_ = (D["h_rim"] - zb * math.sin(F.a)) / math.cos(F.a)
    D["lid_screw_w"] = F.w(yb_, zb)
    D["lid_screw_x"] = D["W"] / 2.0 - P["wall"] - 7.0
    # side clamps (screen frame)
    D["clamp_s1"] = D["s_top"] - 2.0
    D["clamp_s0"] = D["clamp_s1"] - P["clamp_len"]
    D["clamp_xin"] = P["scr_w"] / 2.0 + pad - 0.3
    D["clamp_xo"] = D["clamp_xin"] + 3.0
    D["clamp_screws_s"] = (D["clamp_s0"] + 5.0, D["clamp_s1"] - 5.0)
    D["clamp_screw_n"] = -7.0
    reach = D["clamp_xo"] - (D["W"] / 2.0 - P["wall"])      # length outside the box
    L2 = 16
    for L2 in (16, 20, 25, 30):
        if L2 - reach >= 6.0:
            break
    D["clamp_screw_len"] = L2
    # lid outlet panels
    xa = P["spine_w"] / 2.0 + P["wall"] + 2.0
    xb = D["x_blk"] - 1.0
    D["panels"] = [(xa, xb), (-xb, -xa)]
    # cable slots: centred on the screen's port zone, right behind the screen edge
    s_mid = D["s_top"] - (P["port_s0"] + P["port_s1"]) / 2.0
    D["cable_s0"] = s_mid - P["cable_slot_len"] / 2.0
    D["cable_s1"] = s_mid + P["cable_slot_len"] / 2.0
    return D


def sanity(P, D):
    F = D["F"]
    msgs = []
    W2 = D["W"] / 2.0
    for (x, y) in D["screws"]:
        if abs(x) + D["col_r"] > W2 - P["wall"] + 0.01:
            msgs.append("plug bolt column at x=%.1f hits the side wall" % x)
        zc = D["zc_at"](y)
        if D["cb_z"] + 3.0 > zc:
            msgs.append("plug bolt head at y=%.1f sticks out of the cradle face" % y)
    if D["flange_r"] * 2 > P["vent_spacing"] - 2:
        msgs.append("plug flanges overlap -> reduce plug_wall or increase vent_spacing")
    sl_y0 = F.s2l(D["cable_s0"], -P["t_front"] - 0.8 - P["cable_slot_w"])[0]
    for (x, y) in D["screws"]:
        if abs(x) + D["col_r"] > D["x_blk"] - 1 and y + D["col_r"] > sl_y0 - 1 and y < sl_y0 + P["cable_slot_len"]:
            msgs.append("cable slot runs into the plug bolt column at y=%.1f -> shorten cable_slot_len" % y)
    if P["port_s0"] < P["clamp_len"] + 3:
        msgs.append("side clamps (%.0f mm) reach into the port zone (starts %.0f mm below top)"
                    % (P["clamp_len"] + 2, P["port_s0"]))
    for s in D["clamp_screws_s"]:
        y, z = F.s2l(s, D["clamp_screw_n"])
        if y < D["y_blk"] - (W2 - P["wall"] - D["x_blk"]) + 3:
            msgs.append("clamp screw at s=%.0f is below the end block" % s)
        if F.h(y, z) > D["h_rim"] - 2.5:
            msgs.append("clamp screw at s=%.0f too close to the rim" % s)
    tilt_world = P["dash_angle"] - P["screen_tilt"]
    msgs.append("info: screen leans back %.1f deg from vertical (dash %.1f - tilt %.1f)"
                % (tilt_world, P["dash_angle"], P["screen_tilt"]))
    if D["W"] > 250:
        msgs.append("body is %.0f mm wide: needs a >=256 mm bed or diagonal placement" % D["W"])
    return msgs


# ----------------------------------------------------------------------------
# regions
# ----------------------------------------------------------------------------
def outer_region(P, D, top=True):
    F = D["F"]
    W2 = D["W"] / 2.0
    r = box(-W2, W2, D["Yb"], BIG, D["z_b0"], BIG).common(F.sbox(-BIG, BIG, -BIG, BIG, -BIG, 0.0))
    if top:
        r = r.common(F.wbox(-BIG, BIG, -BIG, D["h_rim"], -BIG, BIG))
    return r


def cavity_region(P, D, inset=0.0):
    F = D["F"]
    W2 = D["W"] / 2.0
    t = P["wall"] + inset
    return box(-W2 + t, W2 - t, D["Yb"] + t, BIG, D["z_b1"] + inset, BIG).common(
        F.sbox(-BIG, BIG, -BIG, BIG, -BIG, -P["t_front"] - inset))


def keepouts(P, D, grow=0.0):
    F = D["F"]
    t = P["wall"]
    W2 = D["W"] / 2.0
    k = []
    # wall around the spine channel (screen frame, full height)
    k.append(F.sbox(-(P["spine_w"] / 2 + t + grow), P["spine_w"] / 2 + t + grow, -BIG, BIG,
                    -P["spine_d"] - t - grow, 5.0))
    # plug bolt columns
    for (x, y) in D["screws"]:
        k.append(cylz(x, y, D["col_r"] + grow, D["z_b1"] - 0.5, 200.0))
    # end blocks with 45 deg underside (print-friendly when standing on the bottom)
    for s in (-1, 1):
        xi = W2 - t + 0.5
        xo = D["x_blk"] - grow
        poly = [(xi, D["y_blk"] - (xi - xo)), (xi, BIG / 4), (xo, BIG / 4), (xo, D["y_blk"])]
        k.append(prism_z([(s * x, y) for (x, y) in poly], D["z_b1"] - 0.5, 200.0))
    return k


# ----------------------------------------------------------------------------
# parts
# ----------------------------------------------------------------------------
def make_body(P, D):
    F = D["F"]
    W2 = D["W"] / 2.0
    t = P["wall"]
    outer = outer_region(P, D)
    cav = cavity_region(P, D).cut(fuse_all(keepouts(P, D)))
    body = outer.cut(cav)

    cuts = []
    for cx in D["vx"]:                                                     # air inlets
        cuts.append(cylz(cx, 0, D["plug_id"] / 2.0, D["z_b0"] - 1, D["z_b1"] + 1))
    cuts.append(F.sbox(-P["spine_w"] / 2, P["spine_w"] / 2, -BIG, BIG, -P["spine_d"], 5.0))   # spine channel
    for (x, y) in D["screws"]:                                             # plug bolts
        cuts.append(cylz(x, y, 1.7, D["z_b0"] - 1, 200.0))
        cuts.append(cylz(x, y, 3.3, D["cb_z"], 200.0))
    for sx in (-1, 1):
        # lid screw pilots (vertical in the world frame)
        cuts.append(F.Wd(Part.makeCylinder(1.3, 14.0, V(sx * D["lid_screw_x"], D["h_rim"] - 13.0,
                                                         D["lid_screw_w"]), V(0, 1, 0))))
        # clamp screw pilots (along X)
        for s in D["clamp_screws_s"]:
            y, z = F.s2l(s, D["clamp_screw_n"])
            x0 = W2 + 1.0 if sx > 0 else -W2 - 1.0
            ln = t + D["blk_w"] - 2.0 + 1.0
            cuts.append(Part.makeCylinder(1.3, ln, V(x0, y, z), V(-sx, 0, 0)))
    # cable slots: stadium in the side wall, right behind the cradle, along the port zone
    sides = {"left": [-1], "right": [1], "both": [-1, 1]}[P["cable_side"]]
    r = P["cable_slot_w"] / 2.0
    n_c = -P["t_front"] - 0.8 - r
    ln = t + D["blk_w"] + 2.0          # through the wall and (if needed) through the end block
    for sx in sides:
        x0 = D["x_blk"] - 1.0 if sx > 0 else -W2 - 1.0
        sl = box(x0, x0 + ln, D["cable_s0"] + r, D["cable_s1"] - r, n_c - r, n_c + r)
        for ss in (D["cable_s0"] + r, D["cable_s1"] - r):
            sl = sl.fuse(Part.makeCylinder(r, ln, V(x0, ss, n_c), V(1, 0, 0)))
        cuts.append(F.S(sl))
    body = body.cut(fuse_all(cuts))

    # ledge + front lip (screen frame), extended down to the flat bottom
    Wl = D["W"] - 2.0
    floor = box(-BIG, BIG, D["Yb"], BIG, -BIG, BIG)
    ledge = F.sbox(-Wl / 2, Wl / 2, -BIG / 8, 0.0, -0.5, D["n_lip1"]).common(floor)
    lip = F.sbox(-Wl / 2, Wl / 2, -BIG / 8, P["lip_h"], D["n_lip0"], D["n_lip1"]).common(floor)
    body = body.fuse(ledge.fuse(lip)).removeSplitter()
    return body


def make_lid(P, D):
    F = D["F"]
    W2 = D["W"] / 2.0
    plate = outer_region(P, D, top=False).common(F.wbox(-BIG, BIG, D["h_rim"], D["h_top"], -BIG, BIG))
    # vanes hanging into the box (only inside the cavity, clear of columns/blocks/channel wall)
    slab = F.wbox(-BIG, BIG, D["h_rim"] - P["vane_depth"], D["h_rim"] + 0.01, -BIG, BIG)
    pan = fuse_all([box(xa, xb, -BIG, BIG, -BIG, BIG) for (xa, xb) in D["panels"]])
    vb = slab.common(pan).common(cavity_region(P, D, inset=0.5)).cut(fuse_all(keepouts(P, D, grow=0.6)))
    lid = plate.fuse(vb)

    # slots tilted towards the cabin
    g = math.radians(P["outlet_angle"])
    tg = math.tan(g)
    h_lo = D["h_rim"] - P["vane_depth"] - 1.0
    h_hi = D["h_top"] + 1.0

    def w_back_in(h):     # world w of the back plate's inner face at height h
        z = D["z_b1"]
        y = (h - z * math.sin(F.a)) / math.cos(F.a)
        return F.w(y, z)

    def w_front_in(h):    # world w of the cradle wall's inner face at height h
        s = F.s_at_h(-P["t_front"], h)
        return F.w(*F.s2l(s, -P["t_front"]))

    def w_front_out(h):
        s = F.s_at_h(0.0, h)
        return F.w(*F.s2l(s, 0.0))

    sw, pitch = P["vane_slot"], P["vane_pitch"]
    lo = w_back_in(D["h_rim"]) + 1.0
    slots = []
    w_rim = lo
    while True:
        wt = w_rim + (D["h_rim"] - D["h_rim"]) * tg            # opening at the rim
        w_top = w_rim + (D["h_top"] - D["h_rim"]) * tg         # opening at the top face
        if w_rim + sw > w_front_in(D["h_rim"]) - 1.0 or w_top + sw > w_front_out(D["h_top"]) - 1.5:
            break
        poly = [(h_lo, w_rim - (D["h_rim"] - h_lo) * tg), (h_lo, w_rim - (D["h_rim"] - h_lo) * tg + sw),
                (h_hi, w_rim + (h_hi - D["h_rim"]) * tg + sw), (h_hi, w_rim + (h_hi - D["h_rim"]) * tg)]
        for (xa, xb) in D["panels"]:
            slots.append(F.Wd(prism_x(poly, xa, xb)))
        w_rim += pitch
    D["n_slots"] = len(slots) // 2
    cuts = list(slots)
    # spine channel + dash-cam clearance
    cuts.append(F.sbox(-P["spine_w"] / 2, P["spine_w"] / 2, -BIG, BIG, -P["spine_d"], 5.0))
    cuts.append(F.sbox(-P["cam_w"] / 2, P["cam_w"] / 2, -BIG, BIG, -P["cam_d"], 5.0))
    # countersunk M3 screws
    for sx in (-1, 1):
        x = sx * D["lid_screw_x"]
        cuts.append(F.Wd(Part.makeCylinder(1.7, 20.0, V(x, D["h_rim"] - 10.0, D["lid_screw_w"]), V(0, 1, 0))))
        cuts.append(F.Wd(Part.makeCone(1.7, 3.4, 1.7, V(x, D["h_top"] - 1.7, D["lid_screw_w"]), V(0, 1, 0))))
        cuts.append(F.Wd(Part.makeCylinder(3.4, 2.0, V(x, D["h_top"] - 0.01, D["lid_screw_w"]), V(0, 1, 0))))
    lid = lid.cut(fuse_all(cuts)).removeSplitter()
    return lid


def make_plug(P, D):
    ro, ri = D["plug_od"] / 2.0, D["plug_id"] / 2.0
    L, tf, b = P["plug_depth"], P["t_flange"], P["plug_bump"]
    p = cylz(0, 0, D["flange_r"], 0, tf).fuse(cylz(0, 0, ro, -L, 0.01))
    zt = -L
    bump = (Part.makeCone(ro - 0.01, ro + b, 2.0, V(0, 0, zt + 1.0))
            .fuse(cylz(0, 0, ro + b, zt + 3.0, zt + 5.0))
            .fuse(Part.makeCone(ro + b, ro - 0.01, 2.0, V(0, 0, zt + 5.0))))
    p = p.fuse(bump)
    tool = cylz(0, 0, ro + 5, -L - 1, -L + 1).cut(Part.makeCone(ro - 1.8, ro + 0.2, 2.0, V(0, 0, -L - 1)))
    p = p.cut(tool)
    p = p.cut(cylz(0, 0, ri, -L - 1, tf + 1))
    flen = 0.7 * L
    for k in range(6):
        s = box(-1.2, 1.2, ri - 1, ro + b + 1, -L - 1, -L + flen)
        s.rotate(V(0, 0, 0), V(0, 0, 1), 30 + 60 * k)
        p = p.cut(s)
    for a in (90, 210, 330):
        x, y = D["rc"] * math.cos(math.radians(a)), D["rc"] * math.sin(math.radians(a))
        p = p.cut(cylz(x, y, 1.7, -1, tf + 1))
        R = 5.75 / math.sqrt(3)
        hexp = [(x + R * math.cos(math.radians(a + 30 + 60 * k)), y + R * math.sin(math.radians(a + 30 + 60 * k)))
                for k in range(6)]
        p = p.cut(prism_z(hexp, tf - 2.6, tf + 1))
    return p.removeSplitter()


def make_clamp_sf(P, D, sx):
    """Side clamp in the screen frame (x, y=s, z=n)."""
    W2 = D["W"] / 2.0
    s0, s1 = D["clamp_s0"], D["clamp_s1"]
    xin, xo = D["clamp_xin"], D["clamp_xo"]
    nb = -14.0
    parts = [
        box(W2 + P["clamp_gap"], xo, s0, s1, nb, -0.5),                     # base beside the body wall
        box(xin, xo, s0, s1, nb, D["n_lip1"]),                               # arm along the screen edge
        box(P["scr_w"] / 2.0 - 4.0, xo, s0, s1, D["n_lip0"], D["n_lip1"]),   # lip over the front bezel
    ]
    c = fuse_all(parts)
    for s in D["clamp_screws_s"]:
        c = c.cut(Part.makeCylinder(1.7, xo - W2 + 2.0, V(W2 - 1.0, s, D["clamp_screw_n"]), V(1, 0, 0)))
    c = c.removeSplitter()
    if sx < 0:
        c = c.mirror(V(0, 0, 0), V(1, 0, 0))
    return c


def make_gauge(P, D, body):
    W2 = D["W"] / 2.0
    th = 1.6
    y1 = body.BoundBox.YMax
    frame = box(-W2, W2, D["Yb"], y1, 0, th).cut(box(-W2 + 4, W2 - 4, D["Yb"] + 4, y1 - 4, -1, th + 1))
    parts = [frame, box(-W2 + 2, W2 - 2, -3, 3, 0, th)]
    ro = D["plug_od"] / 2.0
    for cx in D["vx"]:
        parts.append(box(cx - 3, cx + 3, 0, y1 - 2, 0, th))
        parts.append(box(cx - 3, cx + 3, D["Yb"] + 2, 0, 0, th))
        parts.append(cylz(cx, 0, ro + 3.0, 0, th))
        parts.append(cylz(cx, 0, D["flange_r"], 0, th).cut(cylz(cx, 0, D["flange_r"] - 3, -1, th + 1)))
    g = fuse_all(parts)
    for cx in D["vx"]:
        g = g.cut(cylz(cx, 0, ro - 1.6, -1, th + 1))
        g = g.fuse(cylz(cx, 0, ro, -8.0, 0.01).cut(cylz(cx, 0, ro - 1.6, -9, 1)))
    return g.removeSplitter()


def make_dummies(P, D):
    F = D["F"]
    dash = box(-200, 200, D["Yb"] - 70, 110, -16, -14)
    housings = fuse_all([cylz(cx, 0, P["housing_od"] / 2.0, -14.01, 0).cut(cylz(cx, 0, P["vent_id"] / 2.0, -20, 1))
                         for cx in D["vx"]])
    media = box(-105, 105, D["Yb"] - 68, D["Yb"] - 12, -14.5, -10)
    pad, sw2 = P["pad"], P["scr_w"] / 2.0
    n0, n1 = pad, pad + P["scr_t"]
    scr = box(-sw2, sw2, pad, D["s_top"], n0, n1)
    spine = box(-20, 20, pad + 25, D["s_top"], n0 - 12, n0)
    cam = box(-18, 18, D["s_top"], D["s_top"] + 30, n0 - 14, n0 + 4)
    glass = box(-sw2 + 6, sw2 - 6, pad + 7, D["s_top"] - 7, n1, n1 + 0.4)
    return {"dash": dash, "housings": housings, "media": media,
            "screen": F.S(scr.fuse(spine).fuse(cam)), "glass": F.S(glass)}


# ----------------------------------------------------------------------------
# export
# ----------------------------------------------------------------------------
def on_bed(s):
    bb = s.BoundBox
    s.translate(V(-bb.Center.x, -bb.Center.y, -bb.ZMin))
    return s


def write_stl(shape, path):
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.03, AngularDeflection=0.15, Relative=False)
    m.write(path)


def fc_view(shape, F):
    """local -> world -> FreeCAD convention (Z up, -Y = towards the cabin)"""
    return rotx(F.to_world(shape), 90)


def main():
    os.makedirs(OUT, exist_ok=True)
    P = load_params()
    D = derive(P)
    F = D["F"]
    for m in sanity(P, D):
        print("CHECK:", m)

    body = make_body(P, D)
    lid = make_lid(P, D)
    plug0 = make_plug(P, D)
    plugs = []
    for cx in D["vx"]:
        p = plug0.copy()
        p.translate(V(cx, 0, 0))
        plugs.append(p)
    clamps_sf = [make_clamp_sf(P, D, -1), make_clamp_sf(P, D, 1)]
    clamps = [F.S(c) for c in clamps_sf]
    gauge = make_gauge(P, D, body)

    parts = {"body": body, "lid": lid, "plug": plug0, "clamp_L": clamps[0], "clamp_R": clamps[1], "gauge": gauge}
    for k, s in parts.items():
        print("%-8s valid=%s solids=%d volume=%.1f cm3" % (k, s.isValid(), len(s.Solids), s.Volume / 1000.0))
    print("lid outlet: %d slots per side" % D.get("n_slots", 0))

    # print-oriented STLs
    pr = {
        "body": on_bed(rotx(body, 90)),                                   # stands on its flat bottom
        "lid": on_bed(rotx(F.to_world(lid), 180 + 90)),                    # level top face on the bed
        "vent_plug_x2": on_bed(rotx(plug0, 180)),                          # flange down
        "side_clamp_L": on_bed(rotx(clamps_sf[0], 90)),                    # stands on its end face
        "side_clamp_R": on_bed(rotx(clamps_sf[1], 90)),
        "fit_gauge": on_bed(rotx(gauge, 180)),
    }
    for k, s in pr.items():
        write_stl(s, os.path.join(OUT, k + ".stl"))
        bb = s.BoundBox
        print("STL %-14s print size %.0f x %.0f x %.0f mm" % (k, bb.XLength, bb.YLength, bb.ZLength))
    for old in ("top_clip_L.stl", "top_clip_R.stl", "clip_L.step", "clip_R.step"):
        if os.path.exists(os.path.join(OUT, old)):
            os.remove(os.path.join(OUT, old))

    # STEP in installed position (FreeCAD convention: Z up, -Y towards the cabin)
    inst = [fc_view(s, F) for s in [body, lid] + plugs + clamps]
    Part.makeCompound(inst).exportStep(os.path.join(OUT, "assembly.step"))
    for k, s in parts.items():
        s.exportStep(os.path.join(OUT, k + ".step"))

    doc = App.newDocument("IbizaScreenHolder")
    dm = make_dummies(P, D)
    for name, s in [("Body", body), ("Lid", lid), ("Plug_L", plugs[0]), ("Plug_R", plugs[1]),
                    ("Clamp_L", clamps[0]), ("Clamp_R", clamps[1])] + \
                   [("Dummy_" + k, v) for k, v in dm.items()]:
        o = doc.addObject("Part::Feature", name)
        o.Shape = fc_view(s, F)
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "ibiza_screen_holder.FCStd"))
    for f in os.listdir(OUT):
        if f.endswith(".FCBak"):
            os.remove(os.path.join(OUT, f))

    with open(os.path.join(OUT, "dimensions.json"), "w") as f:
        json.dump({"params": P, "derived": {k: v for k, v in D.items()
                                            if isinstance(v, (int, float, tuple, list))}}, f, indent=2)

    # interference + height checks (screen dummy without the dash-cam)
    pad, sw2 = P["pad"], P["scr_w"] / 2.0
    scr = F.S(box(-sw2, sw2, pad, D["s_top"], pad, pad + P["scr_t"]))
    named = {"body": body, "lid": lid, "plug_L": plugs[0], "plug_R": plugs[1],
             "clamp_L": clamps[0], "clamp_R": clamps[1], "screen": scr}
    keys = list(named)
    worst = 0.0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            v = named[keys[i]].common(named[keys[j]]).Volume
            worst = max(worst, v)
            if v > 0.5:
                print("CHECK: %s and %s overlap by %.1f mm3" % (keys[i], keys[j], v))
    print("interference check: max overlap %.2f mm3" % worst)
    h_scr = F.to_world(scr).BoundBox.YMax
    for k in ("body", "lid", "clamp_L", "clamp_R"):
        hk = F.to_world(named[k]).BoundBox.YMax
        print("height check: %-8s top %.1f mm vs screen top %.1f mm -> %s"
              % (k, hk, h_scr, "OK" if hk <= h_scr + 0.01 else "HIGHER THAN SCREEN"))

    wb = F.to_world(body).BoundBox
    print("HARDWARE: 6x M3x%d socket head (DIN 912) + 6x M3 nut   (plugs -> body)" % D["screw_len"])
    print("          4x M3x%d socket head into 2.6 mm pilots       (side clamps -> body)" % D["clamp_screw_len"])
    print("          2x M3x12 countersunk into 2.6 mm pilots        (lid -> body)")
    print("SIZE (installed): %.0f wide x %.0f high x %.0f deep; screen leans back %.1f deg"
          % (wb.XLength, wb.YLength, wb.ZLength, P["dash_angle"] - P["screen_tilt"]))

    if os.environ.get("NO_RENDER") != "1":
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import render_preview
        render_preview.render_all(P, D, body, lid, plugs, clamps, dm, gauge, OUT)
    print("done ->", OUT)


main()
