# -*- coding: utf-8 -*-
"""
AOS-DK - Tools/build_spire_a0.py
Central A-0 assembly of Tower A (UE 5.7.4, Lvl_FirstPerson):
  * Kikutake void slab (S2)            Z -18 000 ... -23 000, r <= 300 000
  * A-0 (down) inverted megatower (S3) Z -23 000 ... -88 500
  * A-0 (up) rising Kikutake pylon (S5) Z -160 000 ... -91 500  (+ V-3 vent shaft)
  * S4 junction: IC-M discs, 3 000 gap, ring bus r 20 000 + D-1 junction chamber
Source of truth: AOS_TowerA_Spatial_Bible_EN.md 1.3, 2.1-2.4, 3.0.2, 3.0.4, 5.3.

Run inside the editor (UE MCP bridge, execute_python):
    g = {"SPIRE_MODE": "probe"}      # probe | assets | place | verify | save | all
    exec(open(r"<proj>/Tools/build_spire_a0.py", encoding="utf-8").read(), g)
    result = g["result"]
Options (globals): SPIRE_ONLY = ["SM_A0D_Capital", ...] (assets subset),
                   SPIRE_FORCE = True (rebuild meshes even if the geometry hash matches),
                   SPIRE_CPD = {"scale": [10,11,12], "offset": [13,14,15], "factor": 1.0}
                   (override the BoxMap CPD layout if auto-detection fails).
Every mode is idempotent: assets are rebuilt only when their geometry hash changes,
`place` deletes every actor tagged AOS_SpireA0 before spawning, `verify` is read-only.
The `assets` step runs longer than the bridge's 15 s timeout (Nanite build); the
editor keeps working - wait, then call `verify` (it also reports missing assets).

Offline (plain CPython, no editor):  python build_spire_a0.py --selftest
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time

try:
    import unreal  # noqa: F401
except ImportError:  # offline self-test
    unreal = None

# =============================================================================
# 1. CONFIG (Spatial Bible values, cm)
# =============================================================================
LEVEL_PATH = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
MESH_DIR = "/Game/AOS_DK_Game/Environment/Macro/Spire_A0"
FOLDER = "Environment/Macro/Spire_A0/Geometry"
ANCHOR_FOLDER = "Environment/Macro/Spire_A0"
D1_FOLDER = "Environment/Macro/Conduits_D1"
TAG = "AOS_SpireA0"
HASH_KEY = "AOS_SpireA0_Hash"
TEMPLATE_MESH = "/Engine/BasicShapes/Cube"

MATERIAL_NAMES = {            # key -> candidate asset names, first found wins
    "wall": ["MI_A03_Concrete_Wall", "M_AOS_Concrete_BoxMap"],
    "floor": ["MI_A03_Concrete_Floor", "MI_A03_Concrete_Wall", "M_AOS_Concrete_BoxMap"],
    "gis_al": ["MI_GIS_CastAluminum", "MI_A03_Concrete_Wall", "M_AOS_Concrete_BoxMap"],
    "gis_cu": ["MI_GIS_Conductor_Copper", "MI_GIS_CastAluminum", "M_AOS_Concrete_BoxMap"],
}
BOXMAP_MASTER = "M_AOS_Concrete_BoxMap"
CPD_ORIGIN = (0.0, 0.0, -90000.0)   # "cluster origin" of A-0 for the box-map CPD

# --- S2 Kikutake slab (2.3)
SLAB_TOP, SLAB_BOT = -18000.0, -23000.0
CHORD = 800.0                       # upper / lower chord
CELL = 2400.0                       # rib grid
RIB = 600.0                         # rib thickness (each cell owns a 300 half-rib per edge)
SLAB_R = 300000.0
BELT_W = 3600.0                     # solid retention belt at the rim (>= cell diagonal 3 394)
BELT_N = 320                        # belt segments (chord 5 890, sagitta 14.5)
OCULUS_PITCH = 24000.0
OCULUS_R = 2000.0                   # clear radius (Ø 4 000)
LINER = 300.0                       # oculus liner wall through the hollow core
OCULUS_ARC = 16                     # arc segments per quadrant
TILE = 48000.0                      # HISM tile (20 x 20 cells) -> World Partition friendly
# plan keep-outs: (name, x, y, r). Cells touching the circle are omitted (stepped well).
SLAB_KEEPOUTS = [("Socket", -60000.0, 0.0, 3000.0)]
# no oculus within r of these axes (crowns stand on / stalactites hang from the slab)
OCULUS_AXIS_CLEAR = [("A-0", 0.0, 0.0, 16500.0), ("A-3", -48000.0, 22000.0, 9000.0),
                     ("S-2", 35000.0, -30000.0, 9000.0), ("S-5", 20000.0, 40000.0, 9000.0),
                     ("X-4", -20000.0, -55000.0, 9000.0), ("Socket", -60000.0, 0.0, 9000.0)]

# --- S3 A-0 (down) (2.1)
A0D_CAP_Z = (-29000.0, -23000.0)    # capital flare
A0D_CAP_AF = (18000.0, 26000.0)     # across flats bottom / top
A0D_SHAFT_Z = (-86000.0, -29000.0)
A0D_SHAFT_AF = (12000.0, 18000.0)   # bottom / top
A0D_SEG_H = 6400.0
A0D_BORE_AF = 6000.0                # vertical bus shaft
A0D_COLLAR_Z = (-87300.0, -86000.0)  # collar body; disc below
DISC_R = 8000.0                     # Ø 16 000 collars and IC-M discs
DISC_T = 1200.0
A0D_DISC_Z0 = -88500.0              # disc bottom = S4 ceiling

# --- S5 A-0 (up) (2.2)
BED_Z = -160000.0
A0U_PLINTH_Z = (-160000.0, -157000.0)
A0U_PLINTH_R = 15000.0
A0U_TAPER = ((-160000.0, 11000.0), (-94000.0, 7000.0))  # linear: Ø 22 000 -> Ø 14 000
A0U_SEGS = [-157000, -150667, -144333, -138000, -132000, -125667, -119333,
            -113000, -106667, -100333, -94000]
A0U_COLLAR_Z = (-94000.0, -92700.0)
A0U_DISC_Z0 = -92700.0              # disc top = -91 500 = S4 floor
V3_BAND = (-138000.0, -132000.0)    # 6 000 x 6 000 entrance, centred on Z -135 000
V3_HALF = 3000.0
V3_BACK_X = -1000.0                 # entrance tunnel ends at the vertical shaft's far wall
V3_SHAFT_X = (-7000.0, -1000.0)     # vertical drop 6 000 x 6 000, -132 000 -> bed (-160 000)

# --- S4 ring bus (2.4) + junction
RING_R = 20000.0
RING_Z = -90000.0
ENC_RO, ENC_RI = 4000.0, 3850.0     # OD 8 000, wall 150
COND_R = 1415.0                     # Ø 2 830 = ID / e
FLANGE_RO = 4400.0                  # OD + 800
FLANGE_T = 120.0                    # 60 per module end
RING_SLOT = 11.25                   # degrees per module (32 slots, 2 taken by the junction)
RING_SIDES, COND_SIDES = 32, 16
D1_START = (24000.0, 0.0, -90000.0)  # expected D-1 start (flange mating face centre)
JCT_X_IN = 15000.0                  # junction chamber inner face
JCT_HALF_Z = 4400.0
JCT_WALL = 150.0

# --- shared
N_TOWER = 48                        # facets of the Ø 16 000 collars / discs / pylon
N_PLINTH = 64
FACADE_T = 600.0                    # thickness of the face-shell collision boxes
INPLANE_TOL = 25.0                  # max in-plane overshoot of a face box (cm)
MAX_SLICES = 32
VIS_TOL = 15.0                      # Bible 3.0.2: visual beyond collision <= 15 cm
SHELL_R = 245.0                     # Shell-1 bounding sphere
DF_SCALE_BIG = 2.0                  # Bible 3.0.4: meshes > 6 400 -> DF resolution scale 2.0

# =============================================================================
# 2. GEOMETRY KERNEL (pure Python)
# =============================================================================
def vadd(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def vsub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def vmul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def vdot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def vcross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def vlen(a): return math.sqrt(vdot(a, a))
def vnorm(a):
    l = vlen(a)
    return (a[0] / l, a[1] / l, a[2] / l)
def rad(d): return d * math.pi / 180.0


def poly_area2(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) * 0.5


def ccw(p):
    return list(p) if poly_area2(p) > 0 else list(reversed(p))


def ngon(n, r, first_deg):
    """n points on a circle of circumradius r, first vertex at first_deg, CCW."""
    return [(r * math.cos(rad(first_deg + 360.0 * k / n)), r * math.sin(rad(first_deg + 360.0 * k / n))) for k in range(n)]


def ngon_af(n, af, facet_deg=0.0):
    """Regular n-gon given across-flats, with a facet centred on facet_deg."""
    return ngon(n, (af * 0.5) / math.cos(math.pi / n), facet_deg + 180.0 / n)


def face_normal(pts):
    n = (0.0, 0.0, 0.0)
    for i in range(len(pts)):          # Newell
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n = vadd(n, ((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])))
    return vnorm(n)


def earclip(poly):
    """Triangulate a simple CCW polygon (2D). Returns index triples (CCW)."""
    idx = list(range(len(poly)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        return cross(a, b, p) >= -1e-9 and cross(b, c, p) >= -1e-9 and cross(c, a, p) >= -1e-9

    guard = 0
    while len(idx) > 3 and guard < 100000:
        guard += 1
        n = len(idx)
        best = None
        for k in range(n):
            i0, i1, i2 = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cr = cross(a, b, c)
            if cr <= 1e-9:
                continue
            if any(inside(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)
                   and poly[j] not in (a, b, c)):
                continue
            # prefer fat ears (better triangles)
            q = cr / max(1e-9, (math.dist(a, b) ** 2 + math.dist(b, c) ** 2 + math.dist(c, a) ** 2))
            if best is None or q > best[0]:
                best = (q, k)
        if best is None:
            raise RuntimeError("earclip failed (polygon not simple / not CCW)")
        k = best[1]
        tris.append((idx[(k - 1) % n], idx[k], idx[(k + 1) % n]))
        idx.pop(k)
    tris.append(tuple(idx))
    return tris


def ray_poly(c, ang, poly):
    """Intersection of the ray c + t(cos,sin), t>0 with a closed polygon (nearest)."""
    d = (math.cos(ang), math.sin(ang))
    best = None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        e = (b[0] - a[0], b[1] - a[1])
        den = d[0] * (-e[1]) - d[1] * (-e[0])
        if abs(den) < 1e-12:
            continue
        w = (a[0] - c[0], a[1] - c[1])
        t = (w[0] * (-e[1]) - w[1] * (-e[0])) / den
        s = (d[0] * w[1] - d[1] * w[0]) / den
        if t > 1e-9 and -1e-9 <= s <= 1 + 1e-9 and (best is None or t < best[0]):
            best = (t, (c[0] + t * d[0], c[1] + t * d[1]), i, s)
    return best


def densify_by_rays(outer, inner, c):
    """Insert into `outer` the points hit by rays from c through every inner vertex."""
    extra = {}
    for p in inner:
        hit = ray_poly(c, math.atan2(p[1] - c[1], p[0] - c[0]), outer)
        if hit and 1e-6 < hit[3] < 1 - 1e-6:
            extra.setdefault(hit[2], []).append((hit[3], hit[1]))
    res = []
    for i, p in enumerate(outer):
        res.append(p)
        for _, q in sorted(extra.get(i, [])):
            res.append(q)
    return res


def merge_ring(outer, inner, c):
    """Triangulate the region between two CCW polygons that are star-shaped about c.
    Returns triangles (CCW, i.e. +z facing) as point triples."""
    def ang(p):
        return math.atan2(p[1] - c[1], p[0] - c[0])
    a0 = ang(outer[0])
    rel = lambda p: (ang(p) - a0) % (2 * math.pi)
    j0 = min(range(len(inner)), key=lambda j: rel(inner[j]))
    I = inner[j0:] + inner[:j0]
    O = list(outer)
    aO = [rel(p) for p in O] + [2 * math.pi]
    aO[0] = 0.0
    aI = [rel(p) for p in I]
    for k in range(1, len(aI)):           # monotone unwrap
        while aI[k] < aI[k - 1]:
            aI[k] += 2 * math.pi
    aI.append(aI[0] + 2 * math.pi)
    n, m = len(O), len(I)
    i = j = 0
    tris = []
    while i < n or j < m:
        if j >= m or (i < n and aO[i + 1] <= aI[j + 1]):
            tris.append((O[i % n], O[(i + 1) % n], I[j % m]))
            i += 1
        else:
            tris.append((O[i % n], I[(j + 1) % m], I[j % m]))
            j += 1
    return tris


def offset_convex(poly, t):
    """Inset a CCW convex polygon by t (all edges)."""
    lines = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        d = (b[0] - a[0], b[1] - a[1])
        l = math.hypot(*d)
        nin = (-d[1] / l, d[0] / l)     # left = inside for CCW
        lines.append(((a[0] + nin[0] * t, a[1] + nin[1] * t), d))
    res = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        res.append((p1[0] + s * d1[0], p1[1] + s * d1[1]))
    return res


def clip_poly_2d(poly, axis, lo, hi):
    """Clip a convex 2D polygon to lo <= p[axis] <= hi."""
    def clip(pts, keep, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            ka, kb = keep(a), keep(b)
            if ka:
                out.append(a)
            if ka != kb:
                out.append(inter(a, b))
        return out

    def mk(val):
        def inter(a, b):
            t = (val - a[axis]) / (b[axis] - a[axis])
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        return inter
    p = clip(poly, lambda q: q[axis] >= lo - 1e-9, mk(lo))
    if not p:
        return p
    return clip(p, lambda q: q[axis] <= hi + 1e-9, mk(hi))


# ---------------------------------------------------------------- collision boxes
class Box:
    """Oriented box: centre, orthonormal right-handed axes (X, Y, Z), full sizes."""
    __slots__ = ("c", "ax", "size", "tag")

    def __init__(self, c, ax, size, tag=""):
        self.c, self.ax, self.size, self.tag = tuple(c), tuple(tuple(a) for a in ax), tuple(size), tag

    @staticmethod
    def aabb(lo, hi, tag=""):
        c = tuple((lo[i] + hi[i]) * 0.5 for i in range(3))
        return Box(c, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), tuple(hi[i] - lo[i] for i in range(3)), tag)

    def transformed(self, yaw_deg, t):
        cy, sy = math.cos(rad(yaw_deg)), math.sin(rad(yaw_deg))
        R = lambda v: (cy * v[0] - sy * v[1], sy * v[0] + cy * v[1], v[2])
        return Box(vadd(R(self.c), t), tuple(R(a) for a in self.ax), self.size, self.tag)

    def rotator(self):
        """(pitch, yaw, roll) in degrees, UE FMatrix::Rotator() convention."""
        X, Y, Z = self.ax
        pitch = math.degrees(math.atan2(X[2], math.hypot(X[0], X[1])))
        yaw = math.degrees(math.atan2(X[1], X[0]))
        y = rad(yaw)
        # Y axis of FRotationMatrix(pitch, yaw, 0)
        sy_axis = (-math.sin(y), math.cos(y), 0.0)
        roll = math.degrees(math.atan2(vdot(Z, sy_axis), vdot(Y, sy_axis)))
        return pitch, yaw, roll


def ue_rot_matrix(pitch, yaw, roll):
    """Rows = X, Y, Z axes for an FRotator (UE convention)."""
    SP, CP = math.sin(rad(pitch)), math.cos(rad(pitch))
    SY, CY = math.sin(rad(yaw)), math.cos(rad(yaw))
    SR, CR = math.sin(rad(roll)), math.cos(rad(roll))
    return ((CP * CY, CP * SY, SP),
            (SR * SP * CY - CR * SY, SR * SP * SY + CR * CY, -SR * CP),
            (-(CR * SP * CY + SR * SY), CY * SR - CR * SP * SY, CR * CP))


def face_boxes(pts, T, tol=INPLANE_TOL, kmax=MAX_SLICES, tag=""):
    """Face-shell collision: thin boxes whose outer face lies exactly in the face plane,
    extending T into the solid. Sliced along the face's slope axis so that the in-plane
    overshoot past slanted edges stays <= tol (or kmax slices)."""
    n = face_normal(pts)
    up = (0.0, 0.0, 1.0)
    s = vsub(up, vmul(n, vdot(up, n)))
    if vlen(s) < 0.2:                      # near-horizontal face: slice along the longest edge
        best = max(range(len(pts)), key=lambda i: vlen(vsub(pts[(i + 1) % len(pts)], pts[i])))
        s = vsub(pts[(best + 1) % len(pts)], pts[best])
    s = vnorm(s)
    u = vcross(s, n)
    p0 = pts[0]
    q = [(vdot(vsub(p, p0), u), vdot(vsub(p, p0), s)) for p in pts]
    smin, smax = min(v[1] for v in q), max(v[1] for v in q)

    def extents(a, b):
        c = clip_poly_2d(q, 1, a, b)
        return (min(v[0] for v in c), max(v[0] for v in c)) if c else None

    def overshoot(a, b):
        e = extents(a, b)
        ea, eb = clip_poly_2d(q, 1, a, a + 1e-3), clip_poly_2d(q, 1, b - 1e-3, b)
        lo = [min(v[0] for v in x) for x in (ea, eb) if x]
        hi = [max(v[0] for v in x) for x in (ea, eb) if x]
        return max(max(lo) - e[0], e[1] - min(hi)) if lo and hi else 0.0

    k = 1
    while k < kmax:
        h = (smax - smin) / k
        if max(overshoot(smin + i * h, smin + (i + 1) * h) for i in range(k)) <= tol:
            break
        k += 1
    h = (smax - smin) / k
    boxes = []
    for i in range(k):
        a, b = smin + i * h, smin + (i + 1) * h
        e = extents(a, b)
        if not e or e[1] - e[0] < 1e-3:
            continue
        c = vadd(p0, vadd(vmul(u, (e[0] + e[1]) * 0.5), vadd(vmul(s, (a + b) * 0.5), vmul(n, -T * 0.5))))
        boxes.append(Box(c, (u, s, n), (e[1] - e[0], b - a, T), tag))
    return boxes


# ---------------------------------------------------------------------- mesh
class Face:
    __slots__ = ("pts", "g", "internal", "T", "kmax")

    def __init__(self, pts, g, internal, T, kmax=MAX_SLICES):
        self.pts, self.g, self.internal, self.T, self.kmax = pts, g, internal, T, kmax


class Mesh:
    def __init__(self, name, slots, collision="simple", note=""):
        self.name = name
        self.slots = slots            # [(slot_name, material_key)]
        self.faces = []
        self.boxes = []
        self.collision = collision    # "simple" (boxes) | "complex" (use complex as simple)
        self.note = note
        self.meta = {}

    def face(self, pts, g=0, internal=False, T=None, kmax=MAX_SLICES):
        pts = tuple(tuple(float(c) for c in p) for p in pts)
        self.faces.append(Face(pts, g, internal, T, kmax))

    def finalize(self):
        if self.collision == "complex":       # trimesh collision; no simple shapes
            self.boxes = []
            return self
        for f in self.faces:
            if f.T:
                self.boxes.extend(face_boxes(f.pts, f.T, kmax=f.kmax, tag="face"))
        return self

    # ---- stats
    def bounds(self):
        xs = [p for f in self.faces for p in f.pts]
        return (tuple(min(p[i] for p in xs) for i in range(3)), tuple(max(p[i] for p in xs) for i in range(3)))

    def tri_count(self):
        return sum(len(f.pts) - 2 for f in self.faces)

    def signed_volume(self):
        v = 0.0
        for f in self.faces:
            p0 = f.pts[0]
            for i in range(1, len(f.pts) - 1):
                v += vdot(p0, vcross(f.pts[i], f.pts[i + 1])) / 6.0
        return v

    def geo_hash(self):
        h = hashlib.sha1()
        h.update(repr((self.slots, self.collision)).encode())
        for f in self.faces:
            h.update(repr((f.g, [tuple(round(c, 2) for c in p) for p in f.pts])).encode())
        for b in self.boxes:
            h.update(repr((tuple(round(c, 2) for c in b.c), tuple(round(c, 2) for c in b.size), tuple(round(x, 4) for a in b.ax for x in a))).encode())
        return h.hexdigest()[:16]


# ------------------------------------------------------------- solid builders
def P3(p2, z):
    return (p2[0], p2[1], z)


def add_loft(m, bot, top, z0, z1, g=0, side_T=None, hole=None, hole_T=None,
             cap_bot="internal", cap_top="internal", hole_center=None, cap_tris=None):
    """Closed prism/loft between two CCW plan polygons with equal vertex count.
    side_T: None | float | list per edge.  hole: (hole_bot, hole_top) CCW polygons (same count).
    cap_*: "internal" | "exposed" | None (omit).
    cap_tris: optional custom ([(tri, exposed), ...] bottom, [...] top), tris CCW seen from +z."""
    n = len(bot)
    for i in range(n):
        j = (i + 1) % n
        T = side_T[i] if isinstance(side_T, (list, tuple)) else side_T
        m.face([P3(bot[i], z0), P3(bot[j], z0), P3(top[j], z1), P3(top[i], z1)], g, False, T)
    if hole:
        hb, ht = hole
        for i in range(len(hb)):
            j = (i + 1) % len(hb)
            T = hole_T[i] if isinstance(hole_T, (list, tuple)) else hole_T
            m.face([P3(hb[j], z0), P3(hb[i], z0), P3(ht[i], z1), P3(ht[j], z1)], g, False, T)
    for which, poly, hpoly, z, up in (("bot", bot, hole[0] if hole else None, z0, False),
                                       ("top", top, hole[1] if hole else None, z1, True)):
        mode = cap_bot if which == "bot" else cap_top
        if mode is None:
            continue
        if cap_tris:
            for t, exposed in cap_tris[0 if which == "bot" else 1]:
                tt = t if up else (t[0], t[2], t[1])
                m.face([P3(p, z) for p in tt], g, not exposed, None)
            continue
        if hpoly:
            c = hole_center or (sum(p[0] for p in hpoly) / len(hpoly), sum(p[1] for p in hpoly) / len(hpoly))
            tris = merge_ring(poly, hpoly, c)
        else:
            tris = [(poly[a], poly[b], poly[c]) for a, b, c in earclip(poly)]
        for t in tris:
            tt = t if up else (t[0], t[2], t[1])
            exposed = mode(t) if callable(mode) else (mode == "exposed")
            m.face([P3(p, z) for p in tt], g, not exposed, None)


def add_box(m, lo, hi, g=0, internal_faces=(), collide=True, tag="part"):
    """Axis-aligned closed box + exact box collision."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    F = {
        "-x": [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
        "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        "+y": [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
        "-z": [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
        "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
    }
    for k, pts in F.items():
        m.face(pts, g, k in internal_faces, None)
    if collide:
        m.boxes.append(Box.aabb(lo, hi, tag))


def sweep_ring(m, stations, rho_out, rho_in, sides, g, R, bore_T=None, end_caps=("internal", "internal"),
               first_deg=None, outer_T=None, bore_internal=False):
    """Tube swept around the world Z axis (ring centre at local (-R, 0)). Mesh frame: origin at
    (R, 0) of azimuth 0, x radial, y tangential. stations: azimuths in degrees (ascending).
    rho_in None -> solid tube (end caps triangulated), else hollow (annular end caps)."""
    fd = (180.0 / sides) if first_deg is None else first_deg
    al = [rad(fd + 360.0 * k / sides) for k in range(sides)]

    def pt(beta, rho, a):
        r = R + rho * math.cos(a)
        return (r * math.cos(beta) - R, r * math.sin(beta), rho * math.sin(a))

    for si in range(len(stations) - 1):
        b0, b1 = rad(stations[si]), rad(stations[si + 1])
        for k in range(sides):
            a0, a1 = al[k], al[(k + 1) % sides]
            # outer: normal away from tube axis
            m.face([pt(b0, rho_out, a0), pt(b0, rho_out, a1), pt(b1, rho_out, a1), pt(b1, rho_out, a0)][::-1], g, False,
                   outer_T if rho_in is not None else rho_out * math.cos(math.pi / sides), kmax=1)
            if rho_in is not None:
                m.face([pt(b0, rho_in, a0), pt(b0, rho_in, a1), pt(b1, rho_in, a1), pt(b1, rho_in, a0)], g,
                       bore_internal, bore_T, kmax=1)
    for end, b, mode in ((0, rad(stations[0]), end_caps[0]), (1, rad(stations[-1]), end_caps[1])):
        if mode is None:
            continue
        outer = [pt(b, rho_out, a) for a in al]
        if rho_in is None:
            ring = outer if end == 0 else outer[::-1]   # alpha order -> normal -tangent
            for i in range(1, sides - 1):
                m.face([ring[0], ring[i], ring[i + 1]], g, mode == "internal", None)
        else:
            inner = [pt(b, rho_in, a) for a in al]
            for k in range(sides):
                q = [outer[k], outer[(k + 1) % sides], inner[(k + 1) % sides], inner[k]]
                m.face(q if end == 0 else q[::-1], g, mode == "internal", None)


# =============================================================================
# 3. PART BUILDERS  (each returns a finalized Mesh; local frames documented)
# =============================================================================
CON = [("MS_Concrete", "wall")]
CON_F = [("MS_Concrete", "floor")]
GIS = [("MS_CastAluminum", "gis_al"), ("MS_Conductor", "gis_cu")]


def _arc(c, r, a0, a1, n):
    return [(c[0] + r * math.cos(rad(a0 + (a1 - a0) * k / n)), c[1] + r * math.sin(rad(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


# ---------------------------------------------------------------- S2 slab
# Local frame: cell centred on (0,0); z 0 = slab bottom (-23 000), 5 000 = slab top.
H_SLAB = SLAB_TOP - SLAB_BOT          # 5 000
Z_CORE0, Z_CORE1 = CHORD, H_SLAB - CHORD


def build_slab_cell():
    m = Mesh("SM_A0_Slab_Cell", CON_F, note="2 400 module: chords 800 + 4 half-ribs 300, hollow core 1 800 x 1 800 x 3 400")
    h, hr = CELL / 2, RIB / 2
    side = ("-x", "+x", "-y", "+y")
    add_box(m, (-h, -h, 0), (h, h, Z_CORE0), internal_faces=side, tag="chord")
    add_box(m, (-h, -h, Z_CORE1), (h, h, H_SLAB), internal_faces=side, tag="chord")
    add_box(m, (-h, -h, Z_CORE0), (h, -h + hr, Z_CORE1), internal_faces=("-z", "+z", "-y", "-x", "+x"), tag="rib")
    add_box(m, (-h, h - hr, Z_CORE0), (h, h, Z_CORE1), internal_faces=("-z", "+z", "+y", "-x", "+x"), tag="rib")
    add_box(m, (-h, -h + hr, Z_CORE0), (-h + hr, h - hr, Z_CORE1), internal_faces=("-z", "+z", "-x", "-y", "+y"), tag="rib")
    add_box(m, (h - hr, -h + hr, Z_CORE0), (h, h - hr, Z_CORE1), internal_faces=("-z", "+z", "+x", "-y", "+y"), tag="rib")
    return m.finalize()


def _tangent_boxes(C, r, depth, half_len, z0, z1, a0=180.0, a1=270.0, n=7, tag="tan"):
    out = []
    for k in range(n):
        th = rad(a0 + (k + 0.5) * (a1 - a0) / n)
        d = (math.cos(th), math.sin(th), 0.0)
        t = (-math.sin(th), math.cos(th), 0.0)
        c = (C[0] + d[0] * (r + depth / 2), C[1] + d[1] * (r + depth / 2), (z0 + z1) / 2)
        out.append(Box(c, (d, t, (0.0, 0.0, 1.0)), (depth, 2 * half_len, z1 - z0), tag))
    return out


def build_slab_oculus():
    """Quadrant cell of a pass-through oculus (Ø 4 000). The oculus centre is the cell corner
    (+1 200, +1 200); place 4 instances at yaw 0/90/180/270 around each oculus point."""
    m = Mesh("SM_A0_Slab_CellOculus", CON_F, note="oculus quadrant: chords cut r 2 000, liner r 2 000-2 300 through the core")
    h, hr = CELL / 2, RIB / 2
    C = (h, h)
    arc = _arc(C, OCULUS_R, 270.0, 180.0, OCULUS_ARC)
    chord = ccw([(-h, -h), (h, -h)] + arc + [(-h, h)])
    for z0, z1, cb, ct in ((0.0, Z_CORE0, "exposed", "exposed"), (Z_CORE1, H_SLAB, "exposed", "exposed")):
        add_loft(m, chord, chord, z0, z1, cap_bot=cb, cap_top=ct)
        m.boxes.append(Box.aabb((-h, -h, z0), (h, h - OCULUS_R, z1), "chord"))
        m.boxes.append(Box.aabb((-h, h - OCULUS_R, z0), (h - OCULUS_R, h, z1), "chord"))
        m.boxes.extend(_tangent_boxes(C, OCULUS_R, 900.0, 400.0, z0, z1, tag="chord_tan"))
    rl = OCULUS_R + LINER
    liner = ccw(_arc(C, rl, 180.0, 270.0, OCULUS_ARC) + _arc(C, OCULUS_R, 270.0, 180.0, OCULUS_ARC))
    add_loft(m, liner, liner, Z_CORE0, Z_CORE1, cap_bot="internal", cap_top="internal")
    m.boxes.extend(_tangent_boxes(C, OCULUS_R, LINER, 330.0, Z_CORE0, Z_CORE1, tag="liner_tan"))
    # half-ribs on the two edges away from the oculus (the liner closes the other side)
    add_box(m, (-h, -h, Z_CORE0), (h, -h + hr, Z_CORE1), internal_faces=("-z", "+z", "-y", "-x", "+x"), tag="rib")
    add_box(m, (-h, -h + hr, Z_CORE0), (-h + hr, h, Z_CORE1), internal_faces=("-z", "+z", "-x", "-y", "+y"), tag="rib")
    return m.finalize()


def belt_frame():
    ri, ro = SLAB_R - BELT_W, SLAB_R
    return ri, ro, (ri + ro) / 2, 180.0 / BELT_N


def build_slab_belt():
    """Solid retention belt segment. Local origin at (Rm, 0) of azimuth 0."""
    m = Mesh("SM_A0_Slab_Belt", CON, note="rim belt r 296 400-300 000, 1.125 deg")
    ri, ro, rm, d = belt_frame()
    P = lambda r, a: (r * math.cos(rad(a)) - rm, r * math.sin(rad(a)))
    poly = ccw([P(ri, -d), P(ro, -d), P(ro, d), P(ri, d)])
    add_loft(m, poly, poly, 0.0, H_SLAB, cap_bot="exposed", cap_top="exposed")
    x0, x1 = ri * math.cos(rad(d)) - rm, ro * math.cos(rad(d)) - rm
    yh = ro * math.sin(rad(d))
    m.boxes.append(Box.aabb((x0, -yh, 0.0), (x1, yh, H_SLAB), "belt"))
    return m.finalize()


# ---------------------------------------------------------------- A-0 (down)
def a0d_af(z):
    (zb, zt), (ab, at) = A0D_SHAFT_Z, A0D_SHAFT_AF
    return ab + (at - ab) * (z - zb) / (zt - zb)


def a0d_segments():
    zs, z = [], A0D_SHAFT_Z[1]
    while z > A0D_SHAFT_Z[0] + 1e-6:
        zs.append((max(A0D_SHAFT_Z[0], z - A0D_SEG_H), z))
        z -= A0D_SEG_H
    return zs          # top -> bottom


def _octa(af):
    return ngon_af(8, af, 0.0)


def build_a0d_capital():
    """Local origin (0,0) at Z -29 000 (capital bottom)."""
    m = Mesh("SM_A0D_Capital", CON, note="capital flare AF 18 000 -> 26 000, bore AF 6 000")
    z0, z1 = A0D_CAP_Z
    bore = _octa(A0D_BORE_AF)
    add_loft(m, _octa(A0D_CAP_AF[0]), _octa(A0D_CAP_AF[1]), 0.0, z1 - z0, side_T=FACADE_T,
             hole=(bore, bore), hole_T=FACADE_T, cap_bot="internal", cap_top="internal", hole_center=(0, 0))
    return m.finalize()


def build_a0d_shaft(i, z0, z1):
    """Local origin (0,0) at segment bottom."""
    m = Mesh("SM_A0D_Shaft_S%02d" % (i + 1), CON, note="octagon AF %.0f -> %.0f, Z %.0f..%.0f" % (a0d_af(z0), a0d_af(z1), z0, z1))
    bore = _octa(A0D_BORE_AF)
    add_loft(m, _octa(a0d_af(z0)), _octa(a0d_af(z1)), 0.0, z1 - z0, side_T=FACADE_T,
             hole=(bore, bore), hole_T=FACADE_T, cap_bot="internal", cap_top="internal", hole_center=(0, 0))
    m.meta["z"] = (z0, z1)
    return m.finalize()


def _disc_poly():
    return ngon(N_TOWER, DISC_R, 180.0 / N_TOWER)


def build_a0d_collar():
    """Local origin (0,0) at Z -87 300 (top at -86 000). Bore continues down to the disc."""
    m = Mesh("SM_A0D_Collar", CON, note="collar Ø 16 000, Z -87 300..-86 000, holds IC-M below")
    z0, z1 = A0D_COLLAR_Z
    disc, bore = _disc_poly(), _octa(A0D_BORE_AF)
    apo = DISC_R * math.cos(math.pi / N_TOWER)
    foot = _octa(A0D_SHAFT_AF[0])
    top = [(t, True) for t in merge_ring(disc, foot, (0, 0))] + [(t, False) for t in merge_ring(foot, bore, (0, 0))]
    bot = [(t, False) for t in merge_ring(disc, bore, (0, 0))]
    add_loft(m, disc, disc, 0.0, z1 - z0, side_T=apo - (A0D_SHAFT_AF[0] / 2 - 100.0), hole=(bore, bore),
             hole_T=FACADE_T, cap_tris=(bot, top))
    return m.finalize()


def build_icm_disc():
    """IC-M inductive coupler disc Ø 16 000 x 1 200. Local origin at disc bottom centre."""
    m = Mesh("SM_A0_ICM_Disc", [("MS_CastAluminum", "gis_al")], note="IC-M main disc (2.6)")
    disc = _disc_poly()
    add_loft(m, disc, disc, 0.0, DISC_T, side_T=DISC_R * math.cos(math.pi / N_TOWER), cap_bot="exposed", cap_top="exposed")
    return m.finalize()


# ---------------------------------------------------------------- A-0 (up)
def a0u_r(z):
    (za, ra), (zb, rb) = A0U_TAPER
    return ra + (rb - ra) * (z - za) / (zb - za)


V3_SQUARE = [(V3_SHAFT_X[0], -V3_HALF), (V3_SHAFT_X[1], -V3_HALF), (V3_SHAFT_X[1], V3_HALF), (V3_SHAFT_X[0], V3_HALF)]
V3_C = ((V3_SHAFT_X[0] + V3_SHAFT_X[1]) / 2, 0.0)


def _pylon_poly(z):
    # vertex at 0 deg / 180 deg: keeps the y = +-3 000 cut of V-3 on one facet over the band height
    return ngon(N_TOWER, a0u_r(z), 0.0)


def build_a0u_plinth():
    """Local origin (0,0) at Z -160 000 (sector bed)."""
    m = Mesh("SM_A0U_Plinth", CON, note="plinth Ø 30 000 x 3 000, V-3 shaft 6 000 x 6 000 through")
    z0, z1 = A0U_PLINTH_Z
    poly = ngon(N_PLINTH, A0U_PLINTH_R, 180.0 / N_PLINTH)
    r_py = a0u_r(z1) * math.cos(math.pi / N_TOWER)
    foot = _pylon_poly(z1)
    top = [(t, True) for t in merge_ring(poly, foot, (0, 0))] + [(t, False) for t in merge_ring(foot, V3_SQUARE, V3_C)]
    bot = [(t, False) for t in merge_ring(poly, V3_SQUARE, V3_C)]
    add_loft(m, poly, poly, 0.0, z1 - z0, side_T=A0U_PLINTH_R - r_py + 400.0, hole=(V3_SQUARE, V3_SQUARE),
             hole_T=FACADE_T, cap_tris=(bot, top))
    return m.finalize()


def _c_poly(z):
    """Pylon cross-section minus the V-3 entrance strip {x <= V3_BACK_X, |y| <= V3_HALF}.
    Returns (polygon CCW, edge kinds) with kinds in facade | cutfacet | wall | back."""
    O = _pylon_poly(z)
    n = len(O)

    def cross_y(yv):
        for i in range(n):
            a, b = O[i], O[(i + 1) % n]
            if (a[1] - yv) * (b[1] - yv) < 0 and a[0] < 0 and b[0] < 0:
                t = (yv - a[1]) / (b[1] - a[1])
                return i, (a[0] + t * (b[0] - a[0]), yv)
        raise RuntimeError("no crossing")
    i_top, p_top = cross_y(V3_HALF)
    i_bot, p_bot = cross_y(-V3_HALF)
    poly, kinds = [p_bot], ["cutfacet"]
    k = (i_bot + 1) % n
    while True:
        poly.append(O[k])
        kinds.append("facade")
        if k == i_top:
            break
        k = (k + 1) % n
    kinds[-1] = "cutfacet"           # O[i_top] -> p_top
    poly += [p_top, (V3_BACK_X, V3_HALF), (V3_BACK_X, -V3_HALF)]
    kinds += ["wall", "back", "wall"]
    return poly, kinds, (i_top, i_bot)


def _safe_T(a, b, n_out, T, x_max):
    """Largest T <= T so that the inner footprint of the facade edge a-b stays out of the V-3 strip."""
    def bad(t):
        for p in (a, b):
            q = (p[0] - n_out[0] * t, p[1] - n_out[1] * t)
            if q[0] < x_max and abs(q[1]) < V3_HALF:
                return True
        return False
    if not bad(T):
        return T
    lo, hi = 0.0, T
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if not bad(mid) else (lo, mid)
    return max(20.0, lo - 5.0)


def _facade_box_strip(edge_pts_z, z_box, inward, depth, tag):
    """Horizontal slab box under/over the tunnel aligned with a facade edge (2D a,b at the cap z)."""
    (a, b) = edge_pts_z
    t = vnorm((b[0] - a[0], b[1] - a[1], 0.0))
    n_in = vnorm((t[1], -t[0], 0.0)) if inward is None else inward
    if vdot(n_in, (-(a[0] + b[0]) / 2, -(a[1] + b[1]) / 2, 0.0)) < 0:
        n_in = vmul(n_in, -1)
    tt = vcross((0.0, 0.0, 1.0), n_in)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    c = (mid[0] + n_in[0] * depth / 2, mid[1] + n_in[1] * depth / 2, (z_box[0] + z_box[1]) / 2)
    return Box(c, (n_in, tt, (0.0, 0.0, 1.0)), (depth, L, z_box[1] - z_box[0]), tag)


def _strip_edges(poly, x_max):
    """Facade edges of a full pylon polygon clipped to the V-3 strip (|y| <= V3_HALF, x < 0)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if a[0] >= 0 or b[0] >= 0:
            continue
        ya, yb = a[1], b[1]
        lo, hi = max(min(ya, yb), -V3_HALF), min(max(ya, yb), V3_HALF)
        if hi - lo < 1e-6:
            continue
        f = lambda yv: (a[0] + (yv - ya) / (yb - ya) * (b[0] - a[0]), yv)
        out.append((f(lo), f(hi)))
    return out


def _strip_poly(z, x_cut):
    """Part of the pylon cross-section inside the V-3 strip with x <= x_cut (CCW)."""
    O = _pylon_poly(z)
    c, kinds, (i_top, i_bot) = _c_poly(z)
    p_top, p_bot = c[len(c) - 3], c[0]
    poly = [p_top]
    k = (i_top + 1) % len(O)
    while True:
        poly.append(O[k])
        if k == i_bot:
            break
        k = (k + 1) % len(O)
    poly += [p_bot, (x_cut, -V3_HALF), (x_cut, V3_HALF)]
    return poly


def _ear(poly, exposed):
    return [((poly[a], poly[b], poly[c]), exposed) for a, b, c in earclip(poly)]


def build_a0u_shaft(i, z0, z1):
    """Local origin (0,0) at segment bottom. Segments below the V-3 band carry the 6 000 x 6 000
    vertical shaft; the band segment is C-shaped (entrance); the segments next to it carry the
    tunnel floor / ceiling (exposed cap regions + their collision)."""
    h = z1 - z0
    kind = "solid"
    if z1 <= V3_BAND[0] + 1e-6:
        kind = "shaft"
    elif abs(z0 - V3_BAND[0]) < 1e-6 and abs(z1 - V3_BAND[1]) < 1e-6:
        kind = "v3"
    m = Mesh("SM_A0U_Shaft_S%02d" % (i + 1), CON,
             note="pylon Ø %.0f -> %.0f, Z %.0f..%.0f (%s)" % (2 * a0u_r(z0), 2 * a0u_r(z1), z0, z1, kind))
    m.meta.update(z=(z0, z1), kind=kind)
    bot, top = _pylon_poly(z0), _pylon_poly(z1)
    below_band = abs(z1 - V3_BAND[0]) < 1e-6
    above_band = abs(z0 - V3_BAND[1]) < 1e-6
    if kind == "shaft":
        bt = [(t, False) for t in merge_ring(bot, V3_SQUARE, V3_C)]
        if below_band:      # top cap: C region (contact) + tunnel floor (exposed)
            tt = _ear(_c_poly(z1)[0], False) + _ear(_strip_poly(z1, V3_SHAFT_X[0]), True)
        else:
            tt = [(t, False) for t in merge_ring(top, V3_SQUARE, V3_C)]
        add_loft(m, bot, top, 0.0, h, side_T=FACADE_T, hole=(V3_SQUARE, V3_SQUARE), hole_T=FACADE_T, cap_tris=(bt, tt))
        if below_band:
            zb = (h - FACADE_T, h)
            for e in _strip_edges(top, V3_SHAFT_X[0]):
                m.boxes.append(_facade_box_strip(e, zb, None, 1000.0, "v3_floor"))
            x_least = max(p[0] for e in _strip_edges(top, 0) for p in e)
            m.boxes.append(Box.aabb((x_least, -V3_HALF, zb[0]), (V3_SHAFT_X[0], V3_HALF, zb[1]), "v3_floor"))
    elif kind == "v3":
        pb, kinds, ib = _c_poly(z0)
        pt_, kinds2, it = _c_poly(z1)
        assert ib == it and len(pb) == len(pt_), "V-3 cut changes facet between band bottom and top"
        T = []
        for e, kd in enumerate(kinds):
            if kd in ("facade", "cutfacet"):
                a, b = pb[e], pb[(e + 1) % len(pb)]
                d = vnorm((b[0] - a[0], b[1] - a[1], 0.0))
                n_out = (d[1], -d[0])
                a2, b2 = pt_[e], pt_[(e + 1) % len(pt_)]
                T.append(min(_safe_T(a, b, n_out, FACADE_T, V3_BACK_X), _safe_T(a2, b2, n_out, FACADE_T, V3_BACK_X)))
            elif kd == "back":
                T.append(FACADE_T)
            else:
                T.append(40.0)                    # tunnel side walls: thin sliced face boxes + main box below
        add_loft(m, pb, pt_, 0.0, h, side_T=T, cap_bot="internal", cap_top="internal")
        for sgn in (1.0, -1.0):
            yw0, yw1 = (V3_HALF, V3_HALF + FACADE_T) if sgn > 0 else (-V3_HALF - FACADE_T, -V3_HALF)
            x_deep = max(_x_on_facade(bot, sgn * (V3_HALF + FACADE_T)), _x_on_facade(top, sgn * (V3_HALF + FACADE_T)))
            m.boxes.append(Box.aabb((x_deep, yw0, 0.0), (V3_BACK_X, yw1, h), "v3_wall"))
    else:
        if above_band:      # bottom cap: C region (contact) + tunnel ceiling (exposed)
            bt = _ear(_c_poly(z0)[0], False) + _ear(_strip_poly(z0, V3_BACK_X), True)
        else:
            bt = _ear(bot, False)
        sT = FACADE_T
        if above_band:      # thinner facade boxes over the mouth: tilted inner corners stay out of the tunnel
            sT = []
            for e in range(len(bot)):
                a, b = bot[e], bot[(e + 1) % len(bot)]
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                sT.append(250.0 if (mx < 0 and abs(my) < V3_HALF + FACADE_T) else FACADE_T)
        add_loft(m, bot, top, 0.0, h, side_T=sT, cap_tris=(bt, _ear(top, False)))
        if above_band:
            zb = (0.0, FACADE_T)
            shrink = FACADE_T * (a0u_r(z0) - a0u_r(z1)) / h      # facade recedes while rising
            for e in _strip_edges(bot, V3_BACK_X):
                bx = _facade_box_strip(e, zb, None, 1000.0, "v3_ceiling")
                n_in = bx.ax[0]
                m.boxes.append(Box(vadd(bx.c, vmul(n_in, shrink / 2)), bx.ax, (bx.size[0] - shrink, bx.size[1], bx.size[2]), bx.tag))
            x_least = max(p[0] for e in _strip_edges(bot, 0) for p in e) + shrink
            m.boxes.append(Box.aabb((x_least, -V3_HALF, zb[0]), (V3_BACK_X, V3_HALF, zb[1]), "v3_ceiling"))
    return m.finalize()


def _x_on_facade(poly, yv):
    """x of the facade (left side, x<0) at y = yv."""
    best = None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if a[0] < 0 and b[0] < 0 and (a[1] - yv) * (b[1] - yv) <= 0 and abs(b[1] - a[1]) > 1e-9:
            x = a[0] + (yv - a[1]) / (b[1] - a[1]) * (b[0] - a[0])
            best = x if best is None else min(best, x)
    return best


def build_a0u_collar():
    """Local origin at Z -94 000 (bottom), top -92 700 under the IC-M disc. Solid."""
    m = Mesh("SM_A0U_Collar", CON, note="collar Ø 16 000, Z -94 000..-92 700")
    z0, z1 = A0U_COLLAR_Z
    disc = _disc_poly()
    add_loft(m, disc, disc, 0.0, z1 - z0, side_T=DISC_R * math.cos(math.pi / N_TOWER), cap_bot="exposed", cap_top="internal")
    return m.finalize()


# ---------------------------------------------------------------- S4 ring bus
# Local frame for ring pieces: origin = ring centreline point at azimuth 0 (world (R, 0, -90 000)),
# +x radial, +y tangential, +z up. Instances are placed at (R cos b, R sin b, -90 000), yaw b.
def build_ring_seg():
    m = Mesh("SM_A0_RingBus_Seg", GIS, note="ring bus module 11.25 deg: enclosure OD 8 000 / ID 7 700, conductor Ø 2 830, half flanges")
    hb = RING_SLOT / 2
    df = math.degrees((FLANGE_T / 2) / RING_R)
    st = [-hb, -hb + df, 0.0, hb - df, hb]
    apo_o = ENC_RO * math.cos(math.pi / RING_SIDES)
    apo_i = ENC_RI * math.cos(math.pi / RING_SIDES)
    # bore boxes reach the outer apothem; thin outer boxes close the 16 cm corner wedges
    sweep_ring(m, [-hb, 0.0, hb], ENC_RO, ENC_RI, RING_SIDES, 0, RING_R, bore_T=apo_o - apo_i, outer_T=30.0)
    fl_T = FLANGE_RO * math.cos(math.pi / RING_SIDES) - apo_i
    sweep_ring(m, st[:2], FLANGE_RO, ENC_RO, RING_SIDES, 0, RING_R, end_caps=("internal", "exposed"),
               outer_T=fl_T, bore_internal=True)
    sweep_ring(m, st[3:], FLANGE_RO, ENC_RO, RING_SIDES, 0, RING_R, end_caps=("exposed", "internal"),
               outer_T=fl_T, bore_internal=True)
    sweep_ring(m, [-hb, 0.0, hb], COND_R, None, COND_SIDES, 1, RING_R)
    return m.finalize()


def _add_holed_face(m, quad3, n_out, hole_c=None, hole_eh=None, rho=None, alphas=None, g=0):
    """Planar convex face (CCW about n_out) with an optional circular hole. Returns hole rim points."""
    v = (0.0, 0.0, 1.0) if abs(n_out[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = vnorm(vcross(v, n_out))
    v = vcross(n_out, u)
    o = hole_c if hole_c else quad3[0]
    to2 = lambda p: (vdot(vsub(p, o), u), vdot(vsub(p, o), v))
    to3 = lambda q: vadd(o, vadd(vmul(u, q[0]), vmul(v, q[1])))
    outer = ccw([to2(p) for p in quad3])
    if hole_c is None:
        m.face([to3(q) for q in outer], g)
        return None
    rim3 = [vadd(hole_c, vadd(vmul(hole_eh, rho * math.cos(a)), vmul((0.0, 0.0, 1.0), rho * math.sin(a)))) for a in alphas]
    rim2 = ccw([to2(p) for p in rim3])
    dense = densify_by_rays(outer, rim2, (0.0, 0.0))
    for t in merge_ring(dense, rim2, (0.0, 0.0)):
        m.face([to3(q) for q in t], g)
    return rim3


def build_ring_junction():
    """D-1 junction chamber: hollow trapezoid between the radial planes +-11.25 deg, x 15 000..24 000,
    z +-4 400, wall 150, with the two ring bores and the D-1 port (face x = 24 000) open.
    Same local frame as the ring modules. Collision: complex-as-simple (3 bores)."""
    m = Mesh("SM_A0_RingBus_Junction", GIS, collision="complex",
             note="ring/D-1 tee chamber; D-1 port face at world x 24 000 (r 24 000), bore Ø 7 700")
    phi = rad(RING_SLOT)
    tp = math.tan(phi)
    R = RING_R
    xo = D1_START[0]
    plan_w = ccw([(JCT_X_IN, -JCT_X_IN * tp), (xo, -xo * tp), (xo, xo * tp), (JCT_X_IN, JCT_X_IN * tp)])
    plan_in = offset_convex(plan_w, JCT_WALL)
    L = lambda p, z: (p[0] - R, p[1], z)
    al = [rad(180.0 / RING_SIDES + 360.0 * k / RING_SIDES) for k in range(RING_SIDES)]
    zh, zi = JCT_HALF_Z, JCT_HALF_Z - JCT_WALL
    holes = {}   # edge index -> (centre_world2d, e_h)
    for i in range(4):
        a, b = plan_w[i], plan_w[(i + 1) % 4]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if abs(a[0] - xo) < 1 and abs(b[0] - xo) < 1:
            holes[i] = ((xo, 0.0), (0.0, 1.0, 0.0))
        elif abs(a[0] - b[0]) > 1:      # radial side
            ang = math.atan2(mid[1], mid[0])
            holes[i] = ((R * math.cos(ang), R * math.sin(ang)), (math.cos(ang), math.sin(ang), 0.0))
    for shell, poly, z, sgn, t_off in (("outer", plan_w, zh, 1.0, 0.0), ("inner", plan_in, zi, -1.0, JCT_WALL)):
        # top / bottom
        top = [L(p, z) for p in poly]
        bot = [L(p, -z) for p in poly]
        m.face(top if sgn > 0 else top[::-1])
        m.face(bot[::-1] if sgn > 0 else bot)
        for i in range(4):
            a, b = poly[i], poly[(i + 1) % 4]
            d = vnorm((b[0] - a[0], b[1] - a[1], 0.0))
            n_out = (d[1], -d[0], 0.0)
            n_face = n_out if sgn > 0 else vmul(n_out, -1)
            quad = [L(a, -z), L(b, -z), L(b, z), L(a, z)]
            if sgn < 0:
                quad = quad[::-1]
            if i in holes:
                (c2, eh) = holes[i]
                c3 = (c2[0] - R - n_out[0] * t_off, c2[1] - n_out[1] * t_off, 0.0)
                rim = _add_holed_face(m, quad, n_face, c3, eh, ENC_RI, al)
                holes.setdefault(("rim", i), []).append(rim)
            else:
                _add_holed_face(m, quad, n_face)
    for i in list(k for k in holes if isinstance(k, int)):
        ro, ri_ = holes[("rim", i)]
        c2 = holes[i][0]
        for k in range(RING_SIDES):
            q = [ro[k], ro[(k + 1) % RING_SIDES], ri_[(k + 1) % RING_SIDES], ri_[k]]
            ctr = vmul(vadd(vadd(q[0], q[1]), vadd(q[2], q[3])), 0.25)
            axis_pt = (c2[0] - R, c2[1], 0.0)
            nrm = face_normal(q)
            to_axis = vsub(axis_pt, ctr)
            # remove the component along the hole axis (face normal of the wall)
            a, b = plan_w[i], plan_w[(i + 1) % 4]
            d = vnorm((b[0] - a[0], b[1] - a[1], 0.0))
            hax = (d[1], -d[0], 0.0)
            to_axis = vsub(to_axis, vmul(hax, vdot(to_axis, hax)))
            m.face(q if vdot(nrm, to_axis) > 0 else q[::-1], 0)
    # conductor: arc through the chamber + radial stub to the D-1 port
    sweep_ring(m, [-RING_SLOT, -RING_SLOT / 2, 0.0, RING_SLOT / 2, RING_SLOT], COND_R, None, COND_SIDES, 1, R)
    _add_cyl_x(m, 0.0, xo - R, COND_R, COND_SIDES, 1)
    return m.finalize()


def _add_cyl_x(m, x0, x1, r, sides, g):
    ring = [(r * math.cos(a), r * math.sin(a)) for a in (rad(180.0 / sides + 360.0 * k / sides) for k in range(sides))]
    P = lambda x, q: (x, q[0], q[1])          # (y, z) circle
    for k in range(sides):
        a, b = ring[k], ring[(k + 1) % sides]
        m.face([P(x0, a), P(x1, a), P(x1, b), P(x0, b)], g)
    for i in range(1, sides - 1):
        m.face([P(x1, ring[0]), P(x1, ring[i]), P(x1, ring[i + 1])], g, True)
        m.face([P(x0, ring[0]), P(x0, ring[i + 1]), P(x0, ring[i])], g, True)


# =============================================================================
# 4. LAYOUT
# =============================================================================
def build_all_meshes():
    ms = [build_slab_cell(), build_slab_oculus(), build_slab_belt(), build_a0d_capital()]
    segs = a0d_segments()                       # top -> bottom; S01 = top
    for i, (z0, z1) in enumerate(segs):
        ms.append(build_a0d_shaft(i, z0, z1))
    ms += [build_a0d_collar(), build_icm_disc(), build_a0u_plinth()]
    for i in range(len(A0U_SEGS) - 1):         # S01 = bottom
        ms.append(build_a0u_shaft(i, float(A0U_SEGS[i]), float(A0U_SEGS[i + 1])))
    ms += [build_a0u_collar(), build_ring_seg(), build_ring_junction()]
    return {m.name: m for m in ms}


def placements(d1_azimuth=0.0):
    """Unique-actor placements: (label, mesh, (x, y, z), yaw)."""
    P = [("A0D_Capital", "SM_A0D_Capital", (0.0, 0.0, A0D_CAP_Z[0]), 0.0)]
    for i, (z0, z1) in enumerate(a0d_segments()):
        P.append(("A0D_Shaft_S%02d" % (i + 1), "SM_A0D_Shaft_S%02d" % (i + 1), (0.0, 0.0, z0), 0.0))
    P.append(("A0D_Collar", "SM_A0D_Collar", (0.0, 0.0, A0D_COLLAR_Z[0]), 0.0))
    P.append(("A0D_ICM_Disc", "SM_A0_ICM_Disc", (0.0, 0.0, A0D_DISC_Z0), 0.0))
    P.append(("A0U_Plinth", "SM_A0U_Plinth", (0.0, 0.0, A0U_PLINTH_Z[0]), 0.0))
    for i in range(len(A0U_SEGS) - 1):
        P.append(("A0U_Shaft_S%02d" % (i + 1), "SM_A0U_Shaft_S%02d" % (i + 1), (0.0, 0.0, float(A0U_SEGS[i])), 0.0))
    P.append(("A0U_Collar", "SM_A0U_Collar", (0.0, 0.0, A0U_COLLAR_Z[0]), 0.0))
    P.append(("A0U_ICM_Disc", "SM_A0_ICM_Disc", (0.0, 0.0, A0U_DISC_Z0), 0.0))
    b0 = d1_azimuth
    P.append(("S4_RingBus_Junction_D1", "SM_A0_RingBus_Junction",
              (RING_R * math.cos(rad(b0)), RING_R * math.sin(rad(b0)), RING_Z), b0))
    for k in range(30):
        b = b0 + RING_SLOT * (k + 1.5)
        P.append(("S4_RingBus_Seg_%02d" % (k + 1), "SM_A0_RingBus_Seg",
                  (RING_R * math.cos(rad(b)), RING_R * math.sin(rad(b)), RING_Z), b))
    return P


def slab_layout():
    """Returns {tile_key: {"loc": (x,y,z), "inst": {mesh: [(dx,dy,dz,yaw), ...]}}}, stats."""
    rb_in = SLAB_R - BELT_W
    h = CELL / 2
    n = int(math.ceil(SLAB_R / CELL)) + 1

    def sq_min_dist(cx, cy, px, py):
        dx = max(abs(px - cx) - h, 0.0)
        dy = max(abs(py - cy) - h, 0.0)
        return math.hypot(dx, dy)

    cells = {}
    for i in range(-n, n):
        for j in range(-n, n):
            cx, cy = (i + 0.5) * CELL, (j + 0.5) * CELL
            if sq_min_dist(cx, cy, 0.0, 0.0) >= rb_in:
                continue
            if any(sq_min_dist(cx, cy, kx, ky) < kr for _, kx, ky, kr in SLAB_KEEPOUTS):
                continue
            cells[(i, j)] = ("SM_A0_Slab_Cell", 0.0)
    oculi = []
    step = int(round(OCULUS_PITCH / CELL))
    m = int(SLAB_R // OCULUS_PITCH) + 1
    for a in range(-m, m + 1):
        for b in range(-m, m + 1):
            gx, gy = a * OCULUS_PITCH, b * OCULUS_PITCH
            if math.hypot(abs(gx) + 2 * h, abs(gy) + 2 * h) > rb_in - 1000.0:
                continue
            if any(math.hypot(gx - ax, gy - ay) < ar for _, ax, ay, ar in OCULUS_AXIS_CLEAR):
                continue
            quad = {(a * step - 1, b * step - 1): 0.0, (a * step, b * step - 1): 90.0,
                    (a * step, b * step): 180.0, (a * step - 1, b * step): 270.0}
            if not all(k in cells for k in quad):
                continue
            for k, yaw in quad.items():
                cells[k] = ("SM_A0_Slab_CellOculus", yaw)
            oculi.append((gx, gy))
    tiles = {}

    def put(x, y, mesh, yaw):
        key = (int(math.floor(x / TILE)), int(math.floor(y / TILE)))
        t = tiles.setdefault(key, {"loc": ((key[0] + 0.5) * TILE, (key[1] + 0.5) * TILE, SLAB_BOT), "inst": {}})
        t["inst"].setdefault(mesh, []).append((x - t["loc"][0], y - t["loc"][1], 0.0, yaw))

    for (i, j), (mesh, yaw) in cells.items():
        put((i + 0.5) * CELL, (j + 0.5) * CELL, mesh, yaw)
    ri, ro, rm, d = belt_frame()
    for k in range(BELT_N):
        a = (k + 0.5) * 360.0 / BELT_N
        put(rm * math.cos(rad(a)), rm * math.sin(rad(a)), "SM_A0_Slab_Belt", a)
    stats = {"cells": sum(1 for v in cells.values() if v[0] == "SM_A0_Slab_Cell"),
             "oculus_cells": sum(1 for v in cells.values() if v[0] != "SM_A0_Slab_Cell"),
             "oculi": len(oculi), "belt": BELT_N, "tiles": len(tiles)}
    return tiles, stats, oculi


# =============================================================================
# 5. OFFLINE SELF-TEST (numpy; python build_spire_a0.py --selftest)
# =============================================================================
def _np():
    import numpy as np
    return np


def boxes_np(boxes):
    np = _np()
    C = np.array([b.c for b in boxes], float)
    A = np.array([b.ax for b in boxes], float)            # (n, 3 axes, 3)
    Hh = np.array([b.size for b in boxes], float) * 0.5
    return C, A, Hh


def dist_to_boxes(P, BX):
    """Min distance from points P (m,3) to the union of boxes (0 inside)."""
    np = _np()
    C, A, Hh = BX
    out = np.full(len(P), np.inf)
    for s in range(0, len(P), 2048):
        d = P[s:s + 2048, None, :] - C[None, :, :]                 # (m, n, 3)
        loc = np.einsum("mnk,njk->mnj", d, A)
        q = np.maximum(np.abs(loc) - Hh[None], 0.0)
        out[s:s + 2048] = np.sqrt((q * q).sum(-1)).min(1)
    return out


def _tri_arrays(m, xf=None):
    np = _np()
    T = []
    for f in m.faces:
        for i in range(1, len(f.pts) - 1):
            T.append((f.pts[0], f.pts[i], f.pts[i + 1]))
    T = np.array(T, float)
    if xf:
        T = xform_pts(T.reshape(-1, 3), *xf).reshape(-1, 3, 3)
    return T


def xform_pts(P, loc, yaw):
    np = _np()
    c, s = math.cos(rad(yaw)), math.sin(rad(yaw))
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return P @ R.T + np.array(loc)


def winding(P, T):
    """Generalised winding number of points P (m,3) w.r.t. triangle soup T (n,3,3)."""
    np = _np()
    w = np.zeros(len(P))
    for s in range(0, len(P), 512):
        a = T[None, :, 0, :] - P[s:s + 512, None, :]
        b = T[None, :, 1, :] - P[s:s + 512, None, :]
        c = T[None, :, 2, :] - P[s:s + 512, None, :]
        la, lb, lc = (np.linalg.norm(x, axis=-1) for x in (a, b, c))
        det = np.einsum("mnk,mnk->mn", a, np.cross(b, c))
        den = la * lb * lc + np.einsum("mnk,mnk->mn", a, b) * lc + np.einsum("mnk,mnk->mn", b, c) * la + np.einsum("mnk,mnk->mn", c, a) * lb
        w[s:s + 512] = (2 * np.arctan2(det, den)).sum(1) / (4 * math.pi)
    return w


def pt_tri_dist(P, T):
    """Min distance from points to triangles (vectorised, exact)."""
    np = _np()
    out = np.full(len(P), np.inf)
    A, B, Cc = T[:, 0], T[:, 1], T[:, 2]
    for s in range(0, len(P), 256):
        p = P[s:s + 256, None, :]
        ab, ac, ap = B - A, Cc - A, p - A
        n = np.cross(ab, ac)
        nn = np.maximum((n * n).sum(-1), 1e-12)
        # barycentric of projection
        v0, v1 = ab, ac
        d00, d01, d11 = (v0 * v0).sum(-1), (v0 * v1).sum(-1), (v1 * v1).sum(-1)
        d20, d21 = (ap * v0).sum(-1), (ap * v1).sum(-1)
        den = np.maximum(d00 * d11 - d01 * d01, 1e-12)
        v = (d11 * d20 - d01 * d21) / den
        w = (d00 * d21 - d01 * d20) / den
        u = 1 - v - w
        inside = (u >= 0) & (v >= 0) & (w >= 0)
        dplane = np.abs((ap * n).sum(-1)) / np.sqrt(nn)

        def seg(a, b):
            ab_ = b - a
            t = np.clip(((p - a) * ab_).sum(-1) / np.maximum((ab_ * ab_).sum(-1), 1e-12), 0, 1)
            q = a + t[..., None] * ab_
            return np.linalg.norm(p - q, axis=-1)
        de = np.minimum(np.minimum(seg(A, B), seg(B, Cc)), seg(Cc, A))
        out[s:s + 256] = np.where(inside, dplane, de).min(1)
    return out


def sample_faces(m, step=400.0, inset=0.5):
    np = _np()
    pts = []
    for f in m.faces:
        if f.internal:
            continue
        P = np.array(f.pts)
        c = P.mean(0)
        for i in range(1, len(P) - 1):           # barycentric grid on each fan triangle
            a, b, cc = P[0], P[i], P[i + 1]
            L = max(np.linalg.norm(b - a), np.linalg.norm(cc - a), np.linalg.norm(cc - b))
            k = max(1, int(L / step))
            for u in range(k + 1):
                for v in range(k + 1 - u):
                    q = a + (b - a) * u / k + (cc - a) * v / k
                    pts.append(q + (c - q) * (inset / max(np.linalg.norm(c - q), 1e-6)))
    return np.array(pts)


def sample_box_surface(b, step=300.0):
    np = _np()
    c, A, h = np.array(b.c), np.array(b.ax), np.array(b.size) / 2
    pts = []
    for ax in range(3):
        o = [i for i in range(3) if i != ax]
        n1, n2 = max(2, int(2 * h[o[0]] / step) + 1), max(2, int(2 * h[o[1]] / step) + 1)
        for sgn in (-1, 1):
            for s1 in np.linspace(-h[o[0]], h[o[0]], n1):
                for s2 in np.linspace(-h[o[1]], h[o[1]], n2):
                    loc = np.zeros(3)
                    loc[ax], loc[o[0]], loc[o[1]] = sgn * h[ax], s1, s2
                    pts.append(c + loc @ A)
    return np.array(pts)


def selftest(verbose=True):
    np = _np()
    rep = {"checks": [], "meshes": {}}

    def check(name, ok, val=""):
        rep["checks"].append((name, bool(ok), val))
        if verbose:
            print(("PASS " if ok else "FAIL ") + name + ("  [" + str(val) + "]" if val != "" else ""))

    # --- rotator convention round trip
    import random
    rnd = random.Random(7)
    worst = 0.0
    for _ in range(200):
        X = vnorm((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        Y = vnorm(vcross((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)), X))
        Z = vcross(X, Y)
        b = Box((0, 0, 0), (X, Y, Z), (1, 1, 1))
        M = ue_rot_matrix(*b.rotator())
        worst = max(worst, max(abs(M[i][j] - (X, Y, Z)[i][j]) for i in range(3) for j in range(3)))
    check("Box -> FRotator round trip (UE FRotationMatrix convention)", worst < 1e-9, "%.1e" % worst)

    ms = build_all_meshes()
    # --- per-mesh: closed, positive volume, DF/LOD size rule, coverage
    for name, m in ms.items():
        lo, hi = m.bounds()
        ext = tuple(hi[i] - lo[i] for i in range(3))
        T = _tri_arrays(m)
        r = {"tris": len(T), "boxes": len(m.boxes), "size": [round(e, 1) for e in ext], "collision": m.collision}
        o1 = m.signed_volume()
        # origin-independence of the divergence volume == closed surface (tolerates T-junctions)
        sh = (12345.0, -6789.0, 4321.0)
        o2 = sum(vdot(vsub(f.pts[0], sh), vcross(vsub(f.pts[i], sh), vsub(f.pts[i + 1], sh))) / 6.0
                 for f in m.faces for i in range(1, len(f.pts) - 1))
        r["closed"] = abs(o1 - o2) < 1e-6 * abs(o1) + 1.0
        r["volume_m3"] = round(o1 / 1e6, 1)
        # GIS pieces are exempt: their OD 8 000 / flange 8 800 is fixed by Bible 2.4 (like SM_GIS_BusCoupler)
        r["height_ok"] = ext[2] <= 6400.0 + 1e-6 or name.startswith("SM_A0_RingBus")
        if m.collision == "simple" and m.boxes:
            P = sample_faces(m)
            d = dist_to_boxes(P, boxes_np(m.boxes))
            r["vis_beyond_collision_max"] = round(float(d.max()), 2)
        rep["meshes"][name] = r
    check("all meshes closed (divergence volume origin-independent)", all(r["closed"] for r in rep["meshes"].values()),
          [n for n, r in rep["meshes"].items() if not r["closed"]])
    check("all meshes positive volume (outward normals)", all(r["volume_m3"] > 0 for r in rep["meshes"].values()))
    check("module height <= 6 400 (DF / LOD rule; GIS ring OD exempt)", all(r["height_ok"] for r in rep["meshes"].values()),
          [n for n, r in rep["meshes"].items() if not r["height_ok"]])
    vb = {n: r["vis_beyond_collision_max"] for n, r in rep["meshes"].items() if "vis_beyond_collision_max" in r}
    check("visual surface covered by collision within %.0f cm (Bible 3.0.2)" % VIS_TOL, max(vb.values()) <= VIS_TOL,
          "worst %s = %.1f" % max(vb.items(), key=lambda kv: kv[1]))

    # --- world assembly
    P = placements()
    world_boxes, world_tris = [], []
    zr = {}
    for label, mesh, loc, yaw in P:
        m = ms[mesh]
        world_boxes += [b.transformed(yaw, loc) for b in m.boxes]
        if m.collision == "complex":
            world_tris.append(_tri_arrays(m, (loc, yaw)))
        lo, hi = m.bounds()
        zr[label] = (lo[2] + loc[2], hi[2] + loc[2])
    BX = boxes_np(world_boxes)
    JT = np.concatenate(world_tris) if world_tris else np.zeros((0, 3, 3))

    def clear(path, n=400):
        pts = []
        for a, b in zip(path[:-1], path[1:]):
            for t in np.linspace(0, 1, n):
                pts.append(np.array(a) * (1 - t) + np.array(b) * t)
        pts = np.array(pts)
        d = dist_to_boxes(pts, BX)
        if len(JT):
            d = np.minimum(d, pt_tri_dist(pts, JT))
        return float(d.min())

    # stack continuity
    def chain(labels):
        gaps = [abs(zr[labels[i]][1] - zr[labels[i + 1]][0]) for i in range(len(labels) - 1)]
        return max(gaps)
    down = ["A0D_ICM_Disc", "A0D_Collar"] + ["A0D_Shaft_S%02d" % k for k in range(len(a0d_segments()), 0, -1)] + ["A0D_Capital"]
    up = ["A0U_Plinth"] + ["A0U_Shaft_S%02d" % k for k in range(1, len(A0U_SEGS))] + ["A0U_Collar", "A0U_ICM_Disc"]
    check("A-0 down: continuous stack disc -> capital (max joint gap)", chain(down) < 1e-6, "%.3f cm" % chain(down))
    check("A-0 down hangs from the slab: capital top = slab bottom", abs(zr["A0D_Capital"][1] - SLAB_BOT) < 1e-6,
          "%.1f vs %.1f" % (zr["A0D_Capital"][1], SLAB_BOT))
    check("A-0 down length slab -> disc bottom = 65 500", abs(SLAB_BOT - zr["A0D_ICM_Disc"][0] - 65500) < 1e-6,
          SLAB_BOT - zr["A0D_ICM_Disc"][0])
    check("A-0 up: continuous stack bed -> disc", chain(up) < 1e-6, "%.3f cm" % chain(up))
    check("A-0 up roots at the bed Z -160 000; height 68 500", abs(zr["A0U_Plinth"][0] - BED_Z) < 1e-6 and
          abs(zr["A0U_ICM_Disc"][1] - BED_Z - 68500) < 1e-6, (zr["A0U_Plinth"][0], zr["A0U_ICM_Disc"][1] - BED_Z))
    gap = zr["A0D_ICM_Disc"][0] - zr["A0U_ICM_Disc"][1]
    check("S4 gap between IC-M discs = 3 000 (Z -91 500 .. -88 500)", abs(gap - 3000) < 1e-6, gap)
    check("pylon Ø at Z -135 000 = 18 970 (Bible 2.2)", abs(2 * a0u_r(-135000) - 18970) < 1.0, round(2 * a0u_r(-135000), 1))

    # S4 gap clearance (Shell sphere R 245) on the mid plane under the discs
    g = [(x, y) for x in range(-10000, 10001, 500) for y in range(-10000, 10001, 500) if math.hypot(x, y) <= 10000]
    pts = np.array([(x, y, RING_Z) for x, y in g])
    dmin = float(dist_to_boxes(pts, BX).min())
    check("S4 gap: clearance on the Z -90 000 plane under the discs (r <= 10 000) = 1 500", abs(dmin - 1500) < 1e-3,
          "min clearance %.1f" % dmin)
    for az in range(0, 360, 45):
        c, s_ = math.cos(rad(az)), math.sin(rad(az))
        path = [(30000 * c, 30000 * s_, -84000.0), (12000 * c, 12000 * s_, -84000.0),
                (12000 * c, 12000 * s_, RING_Z), (0.0, 0.0, RING_Z)]
        cl = clear(path, 200)
        if cl < SHELL_R:
            break
    check("S4 gap reachable: over the ring bus, down inside it, into the gap (8 azimuths)", cl >= SHELL_R,
          "min clearance %.1f" % cl)
    # discs bound the gap
    check("S4 gap bounded: disc A-0 down bottom -88 500 / A-0 up top -91 500",
          abs(zr["A0D_ICM_Disc"][0] + 88500) < 1e-6 and abs(zr["A0U_ICM_Disc"][1] + 91500) < 1e-6)

    # ring lane (12 o'clock, rho 2 700) all the way round + through the junction into the D-1 port
    lane = 2700.0
    arc = [(RING_R * math.cos(rad(b)), RING_R * math.sin(rad(b)), RING_Z + lane) for b in np.linspace(-345, 0, 700)]
    path = arc + [(D1_START[0] + 10.0, 0.0, RING_Z + lane)]
    cl = clear(path, 6)
    check("ring bus lane (12 o'clock) -> junction -> D-1 port: Shell sphere clear", cl >= SHELL_R, "min clearance %.1f" % cl)
    cl_c = clear([(RING_R * math.cos(rad(b)), RING_R * math.sin(rad(b)), RING_Z) for b in (20.0, 21.0)], 10)
    check("control: ring centreline hits the conductor", cl_c < 1e-6, cl_c)
    # port alignment
    jx = [p for p in P if p[1] == "SM_A0_RingBus_Junction"][0]
    port = xform_pts(np.array([[D1_START[0] - RING_R, 0.0, 0.0]]), jx[2], jx[3])[0]
    off = float(np.linalg.norm(port - np.array(D1_START)))
    check("junction D-1 port face centre = D-1 start (24 000, 0, -90 000)", off < 1e-6, "%.3f cm" % off)
    # port face x = 24 000: a Shell sphere fits anywhere in the annulus between conductor and bore
    pts = np.array([(D1_START[0], rr * math.cos(a), RING_Z + rr * math.sin(a))
                    for rr in (COND_R + SHELL_R + 30, ENC_RI - SHELL_R - 30) for a in np.linspace(0, 2 * math.pi, 96)])
    cp = float(pt_tri_dist(pts, JT).min())
    check("D-1 port annulus open (conductor r 1 415 .. bore r 3 850) for the Shell sphere", cp >= SHELL_R, "min %.1f" % cp)

    # V-3: entrance tunnel + vertical drop
    v3 = [(-16000.0, 0.0, -135000.0), (-4000.0, 0.0, -135000.0), (-4000.0, 0.0, -159700.0)]
    cl = clear(v3, 300)
    check("V-3 entrance (az 180, Z -135 000) + 6 000 x 6 000 drop to the bed: Shell sphere clear", cl >= SHELL_R,
          "min clearance %.1f" % cl)
    cl = clear([(-4000.0, 0.0, -135000.0), (-4000.0, 0.0, -130000.0)], 50)
    check("control: V-3 ceiling blocks above Z -132 000", cl < 1e-6, cl)
    cl = clear([(-1500.0, 0.0, -150000.0), (500.0, 0.0, -150000.0)], 50)
    check("control: V-3 shaft wall at x -1 000 blocks", cl < 1e-6, cl)
    # A-0 down bore, sealed by the slab on top and the disc below
    cl = clear([(0.0, 0.0, SLAB_BOT - 300.0), (0.0, 0.0, A0D_COLLAR_Z[0] + 300.0)], 2000)
    check("A-0 down bus shaft (bore AF 6 000) clear slab -> disc", cl >= SHELL_R, "min clearance %.1f" % cl)

    # facade accuracy: horizontal rays toward the axis hit collision at the visual surface
    errs = []
    for label, mesh, loc, yaw in P:
        if not label.startswith(("A0D_Shaft", "A0U_Shaft", "A0D_Capital")):
            continue
        z0, z1 = zr[label]
        for zf in (0.1, 0.5, 0.9):
            zz = z0 + (z1 - z0) * zf
            for az in (0, 22.5, 45, 67.5, 90, 135, 270, 300):
                if label.startswith("A0U") and 160 < az < 200:
                    continue
                d = (math.cos(rad(az)), math.sin(rad(az)))
                vis = _ray_hit_mesh(ms[mesh], loc, d, zz)
                col = _ray_hit_boxes(world_boxes, d, zz)
                if vis is not None and col is not None:
                    errs.append(vis - col)
    check("facade collision radius vs visual radius (rays to the axis)", max(abs(e) for e in errs) <= VIS_TOL + 20,
          "max |dr| %.1f cm over %d rays" % (max(abs(e) for e in errs), len(errs)))

    # --- slab layout
    tiles, st, oculi = slab_layout()
    rep["slab"] = st
    check("slab layout: cells %(cells)d, oculus cells %(oculus_cells)d (%(oculi)d oculi), belt %(belt)d, tiles %(tiles)d" % st,
          st["oculus_cells"] == 4 * st["oculi"] and st["tiles"] > 0)
    # oculus pass-through + socket well + control
    sl = []
    for t in tiles.values():
        for mesh, L in t["inst"].items():
            for dx, dy, dz, yw in L:
                x, y = t["loc"][0] + dx, t["loc"][1] + dy
                if min(math.hypot(x - 24000, y), math.hypot(x + 60000, y), math.hypot(x - 1200, y - 1200)) < 6000:
                    sl += [b.transformed(yw, (x, y, SLAB_BOT)) for b in ms[mesh].boxes]
    SB = boxes_np(sl)
    pa = np.array([(24000.0, 0.0, z) for z in np.linspace(SLAB_TOP + 1000, SLAB_BOT - 1000, 300)])
    c_oc = float(dist_to_boxes(pa, SB).min())
    check("oculus (24 000, 0) pass-through: Shell sphere clear", c_oc >= SHELL_R, "min clearance %.1f (r 2 000)" % c_oc)
    ps = np.array([(-60000.0, 0.0, z) for z in np.linspace(SLAB_TOP + 1000, SLAB_BOT - 1000, 300)])
    c_so = float(dist_to_boxes(ps, SB).min())
    check("Socket shaft well (-60 000, 0) open through the slab, clear r >= 3 000", c_so >= 3000 - 1e-6, "clear r %.1f" % c_so)
    pc = np.array([(1200.0 + 1200, 1200.0 + 1200, z) for z in (SLAB_TOP + 10, SLAB_BOT - 10)])
    check("control: solid cell above the capital blocks", float(dist_to_boxes(pc, SB).min()) <= 10.0 + 1e-6)

    # --- collision protrusion beyond the visual assembly (invisible lips), world level
    pieces = []          # (label, world boxes, world tris, aabb)
    for label, mesh, loc, yaw in P:
        m = ms[mesh]
        T_w = _tri_arrays(m, (loc, yaw))
        pieces.append((label, [b.transformed(yaw, loc) for b in m.boxes], T_w, (T_w.reshape(-1, 3).min(0), T_w.reshape(-1, 3).max(0))))
    for t in tiles.values():
        for mesh, L in t["inst"].items():
            for k, (dx, dy, dz, yw) in enumerate(L):
                x, y = t["loc"][0] + dx, t["loc"][1] + dy
                near = math.hypot(x - 24000, y) < 6000 or math.hypot(x, y) < 18000 or \
                       (mesh == "SM_A0_Slab_Belt" and abs(math.atan2(y, x)) < rad(3)) or \
                       (math.hypot(x, y) > SLAB_R - 9000 and abs(math.atan2(y, x)) < rad(1.5))
                if near:
                    m = ms[mesh]
                    T_w = _tri_arrays(m, ((x, y, SLAB_BOT), yw))
                    pieces.append(("%s@%.0f,%.0f" % (mesh, x, y), [b.transformed(yw, (x, y, SLAB_BOT)) for b in m.boxes],
                                   T_w, (T_w.reshape(-1, 3).min(0), T_w.reshape(-1, 3).max(0))))
    test = [p for p in pieces if p[1] and not (p[0].startswith("S4_RingBus_Seg") and p[0] not in ("S4_RingBus_Seg_01", "S4_RingBus_Seg_15"))
            and not (p[0].startswith("SM_A0_Slab_Cell@") and math.hypot(*map(float, p[0].split("@")[1].split(","))) < 18000)
            and not (p[0].startswith("SM_A0_Slab_Belt@") and abs(math.atan2(*reversed(list(map(float, p[0].split("@")[1].split(",")))))) > rad(1.5))]
    worst = {}
    rng = np.random.default_rng(3)
    for label, bxs, T_w, (lo, hi) in test:
        Bp = np.concatenate([sample_box_surface(b, 400.0) for b in bxs])
        if len(Bp) > 6000:
            Bp = Bp[rng.choice(len(Bp), 6000, replace=False)]
        nb = [q[2] for q in pieces if np.all(q[3][0] <= hi + 1500) and np.all(q[3][1] >= lo - 1500)]
        TU = np.concatenate(nb)
        w = winding(Bp, TU)
        out = Bp[w < 0.5]
        worst[label] = round(float(pt_tri_dist(out, TU).max()), 1) if len(out) else 0.0
    rep["collision_beyond_visual"] = worst
    wk = max(worst.items(), key=lambda kv: kv[1])
    check("collision beyond visual assembly (invisible lips) <= 40 cm", wk[1] <= 40.0, "worst %s = %.1f" % wk)
    return rep


def _ray_hit_boxes(boxes, d, z, r0=40000.0):
    """Distance from the axis at which a horizontal ray from r0 toward the axis first enters a box."""
    best = None
    o = (d[0] * r0, d[1] * r0, z)
    dirv = (-d[0], -d[1], 0.0)
    for b in boxes:
        tmin, tmax = -1e18, 1e18
        ok = True
        for i in range(3):
            a = b.ax[i]
            e = vdot(vsub(o, b.c), a)
            f = vdot(dirv, a)
            h = b.size[i] / 2
            if abs(f) < 1e-12:
                if abs(e) > h:
                    ok = False
                    break
                continue
            t1, t2 = (-h - e) / f, (h - e) / f
            tmin, tmax = max(tmin, min(t1, t2)), min(tmax, max(t1, t2))
        if ok and tmin <= tmax and tmax > 0:
            t = max(tmin, 0)
            best = t if best is None else min(best, t)
    return None if best is None else r0 - best


def _ray_hit_mesh(m, loc, d, z, r0=40000.0):
    """Same for the visual mesh (first face hit)."""
    best = None
    o = (d[0] * r0 - loc[0], d[1] * r0 - loc[1], z - loc[2])
    dirv = (-d[0], -d[1], 0.0)
    for f in m.faces:
        n = face_normal(f.pts)
        den = vdot(n, dirv)
        if abs(den) < 1e-12:
            continue
        t = vdot(vsub(f.pts[0], o), n) / den
        if t <= 0:
            continue
        p = vadd(o, vmul(dirv, t))
        inside = True
        for i in range(len(f.pts)):
            a, b = f.pts[i], f.pts[(i + 1) % len(f.pts)]
            if vdot(vcross(vsub(b, a), vsub(p, a)), n) < -1e-6:
                inside = False
                break
        if inside:
            best = t if best is None else min(best, t)
    return None if best is None else r0 - best


# =============================================================================
# 6. UNREAL EDITOR SIDE
# =============================================================================
_LOG = []


def _log(*a):
    msg = " ".join(str(x) for x in a)
    _LOG.append(msg)
    if unreal:
        unreal.log("[SpireA0] " + msg)


def _eas():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _smes():
    return unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def _world():
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:
        return unreal.EditorLevelLibrary.get_editor_world()


def _write_json(name, data):
    try:
        path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, default=str)
        return path
    except Exception as e:  # noqa: BLE001
        _log("could not write", name, e)
        return None


def _tags(a):
    try:
        return [str(t) for t in a.get_editor_property("tags")]
    except Exception:
        return []


def _ours(a):
    return TAG in _tags(a)


def _folder(a):
    try:
        return str(a.get_folder_path())
    except Exception:
        return ""


_ASSET_INDEX = None


def _find_asset(name):
    global _ASSET_INDEX
    if _ASSET_INDEX is None:
        _ASSET_INDEX = {}
        for p in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False):
            base = p.rsplit("/", 1)[-1].split(".")[0]
            _ASSET_INDEX.setdefault(base, p.split(".")[0])
    return _ASSET_INDEX.get(name)


def ue_materials():
    out, paths = {}, {}
    for key, names in MATERIAL_NAMES.items():
        for n in names:
            p = _find_asset(n)
            if p:
                out[key] = unreal.EditorAssetLibrary.load_asset(p)
                paths[key] = p
                break
        if key not in out:
            out[key] = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
            paths[key] = "FALLBACK /Engine/BasicShapes/BasicShapeMaterial"
    return out, paths


def _mat_chain(mi):
    names, cur = [], mi
    for _ in range(10):
        if not cur:
            break
        names.append(cur.get_name())
        cur = cur.get_editor_property("parent") if isinstance(cur, unreal.MaterialInstance) else None
    return names


def _cpd_data(comp):
    try:
        return [float(x) for x in comp.get_editor_property("custom_primitive_data").get_editor_property("data")]
    except Exception:
        return None


def ue_infer_cpd():
    """Learn how M_AOS_Concrete_BoxMap is fed (CPD 10-15) from components that already use it."""
    ov = globals().get("SPIRE_CPD")
    if ov:
        return dict(ov, source="SPIRE_CPD override")
    samples = []
    for a in _eas().get_all_level_actors():
        if _ours(a):
            continue
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            try:
                mats = c.get_materials()
            except Exception:
                continue
            if not any(m and BOXMAP_MASTER in _mat_chain(m) for m in mats):
                continue
            d = _cpd_data(c)
            if d and len(d) >= 16:
                s, l = c.get_world_scale(), c.get_world_location()
                samples.append((d, (s.x, s.y, s.z), (l.x, l.y, l.z)))
        if len(samples) >= 16:
            break
    res = {"samples": len(samples)}
    for sc, of in (([10, 11, 12], [13, 14, 15]), ([13, 14, 15], [10, 11, 12])):
        if len(samples) < 2:
            break
        fs = [samples[k][0][sc[i]] / samples[k][1][i] for k in range(len(samples)) for i in range(3) if abs(samples[k][1][i]) > 1e-6]
        if not fs:
            continue
        f = sorted(fs)[len(fs) // 2]
        if max(abs(x - f) for x in fs) > 1e-3 * max(1.0, abs(f)):
            continue
        offs = [[samples[k][0][of[i]] for i in range(3)] for k in range(len(samples))]
        Bs = [[samples[k][2][i] - offs[k][i] for i in range(3)] for k in range(len(samples))]
        spreadB = max(max(b[i] for b in Bs) - min(b[i] for b in Bs) for i in range(3))
        spreadO = max(max(o[i] for o in offs) - min(o[i] for o in offs) for i in range(3))
        if spreadB < 1.0:
            res.update(scale=sc, offset=of, factor=f, mode="offset", origin_seen=Bs[0], base=samples[0][0][:10])
            break
        if spreadO < 1.0:
            res.update(scale=sc, offset=of, factor=f, mode="origin", origin_seen=offs[0], base=samples[0][0][:10])
            break
    if "mode" not in res:
        res.update(scale=[10, 11, 12], offset=[13, 14, 15], factor=1.0, mode="offset", base=[0.0] * 10,
                   warning="CPD layout not detected from level samples; using fallback (scale 10-12, offset 13-15)")
    res["source"] = "level samples"
    return res


def _apply_cpd(comp, cpd, comp_loc):
    try:
        base = list(cpd.get("base") or [0.0] * 10)
        for i, v in enumerate(base[:10]):
            comp.set_default_custom_primitive_data_float(i, float(v))
        for i, idx in enumerate(cpd["scale"]):
            comp.set_default_custom_primitive_data_float(idx, float(cpd["factor"]))
        vals = [comp_loc[i] - CPD_ORIGIN[i] for i in range(3)] if cpd["mode"] == "offset" else list(CPD_ORIGIN)
        for i, idx in enumerate(cpd["offset"]):
            comp.set_default_custom_primitive_data_float(idx, float(vals[i]))
        return True
    except Exception as e:  # noqa: BLE001
        _log("CPD failed", e)
        return False


def ue_probe():
    r = {"engine": unreal.SystemLibrary.get_engine_version(), "world": _world().get_path_name()}
    r["level_ok"] = "Lvl_FirstPerson" in r["world"]
    api = {}
    api["StaticMesh.create_static_mesh_description"] = hasattr(unreal.StaticMesh, "create_static_mesh_description")
    api["StaticMesh.build_from_static_mesh_descriptions"] = hasattr(unreal.StaticMesh, "build_from_static_mesh_descriptions")
    for f in ("create_vertex", "set_vertex_position", "create_vertex_instance", "set_vertex_instance_uv",
              "create_polygon_group", "set_polygon_group_material_slot_name", "create_polygon"):
        api["StaticMeshDescription." + f] = hasattr(unreal.StaticMeshDescription, f)
    for n in ("KBoxElem", "SubobjectDataSubsystem", "AddNewSubobjectParams", "SubobjectDataBlueprintFunctionLibrary",
              "InstancedStaticMeshComponent", "StaticMeshEditorSubsystem"):
        api[n] = hasattr(unreal, n)
    r["api"] = api
    r["api_ok"] = all(api.values())
    _, r["materials"] = ue_materials()
    r["cpd"] = ue_infer_cpd()
    r["d1"] = ue_find_d1()
    r["anchors"] = ue_anchors()
    ms = build_all_meshes()
    st = {}
    for name, m in ms.items():
        p = MESH_DIR + "/" + name
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            sm = unreal.EditorAssetLibrary.load_asset(p)
            st[name] = "current" if unreal.EditorAssetLibrary.get_metadata_tag(sm, HASH_KEY) == m.geo_hash() else "stale"
        else:
            st[name] = "missing"
    r["meshes"] = st
    r["placed"] = sum(1 for a in _eas().get_all_level_actors() if _ours(a))
    return r


# ------------------------------------------------------------------ assets
def _uv(p, n):
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 2:
        return p[0] / 200.0, p[1] / 200.0
    if ax == 0:
        return p[1] / 200.0, -p[2] / 200.0
    return p[0] / 200.0, -p[2] / 200.0


def ue_build_mesh(m, mats, force=False):
    EAL = unreal.EditorAssetLibrary
    path = MESH_DIR + "/" + m.name
    h = m.geo_hash()
    if EAL.does_asset_exist(path) and not force:
        sm = EAL.load_asset(path)
        if EAL.get_metadata_tag(sm, HASH_KEY) == h:
            return "skip"
    if not EAL.does_asset_exist(path):
        if not EAL.duplicate_asset(TEMPLATE_MESH, path):
            raise RuntimeError("duplicate_asset failed for " + path)
    sm = EAL.load_asset(path)
    sms = _smes()
    lo, hi = m.bounds()
    big = max(hi[i] - lo[i] for i in range(3)) > 6400.0
    # material slots (names must match the polygon groups)
    sm.set_editor_property("static_materials", [
        unreal.StaticMaterial(material_interface=mats[key], material_slot_name=unreal.Name(slot),
                              imported_material_slot_name=unreal.Name(slot)) for slot, key in m.slots])
    # build settings: Lumen only (no lightmap UVs), normals from split (faceted) vertices
    bs = sms.get_lod_build_settings(sm, 0)
    for k, v in (("recompute_normals", True), ("recompute_tangents", True), ("generate_lightmap_u_vs", False),
                 ("remove_degenerates", True), ("distance_field_resolution_scale", DF_SCALE_BIG if big else 1.0)):
        try:
            bs.set_editor_property(k, v)
        except Exception as e:  # noqa: BLE001
            _log(m.name, "build setting", k, e)
    sms.set_lod_build_settings(sm, 0, bs)
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    ns.set_editor_property("fallback_relative_error", 1.0)
    sm.set_editor_property("nanite_settings", ns)
    # simple collision (before the geometry build so the bodies are created once)
    sms.remove_collisions(sm)
    body = sm.get_editor_property("body_setup")
    if m.collision == "simple":
        agg = body.get_editor_property("agg_geom")
        elems = []
        for b in m.boxes:
            e = unreal.KBoxElem()
            p, y, r = b.rotator()
            e.set_editor_property("center", unreal.Vector(*b.c))
            e.set_editor_property("rotation", unreal.Rotator(roll=r, pitch=p, yaw=y))
            e.set_editor_property("x", float(b.size[0]))
            e.set_editor_property("y", float(b.size[1]))
            e.set_editor_property("z", float(b.size[2]))
            elems.append(e)
        agg.set_editor_property("box_elems", elems)
        agg.set_editor_property("convex_elems", [])
        body.set_editor_property("agg_geom", agg)
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    else:
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    # geometry
    desc = unreal.StaticMesh.create_static_mesh_description(sm)
    groups = []
    for slot, _ in m.slots:
        g = desc.create_polygon_group()
        desc.set_polygon_group_material_slot_name(g, unreal.Name(slot))
        groups.append(g)
    for f in m.faces:
        n = face_normal(f.pts)
        vis = []
        for p in f.pts:
            vid = desc.create_vertex()
            desc.set_vertex_position(vid, unreal.Vector(*p))
            vi = desc.create_vertex_instance(vid)
            desc.set_vertex_instance_uv(vi, unreal.Vector2D(*_uv(p, n)), 0)
            vis.append(vi)
        desc.create_polygon(groups[f.g], vis)
    sm.build_from_static_mesh_descriptions([desc], False, False)
    # re-assert materials by slot name (the build may append slots)
    sl = list(sm.get_editor_property("static_materials"))
    want = {slot: mats[key] for slot, key in m.slots}
    for i, smat in enumerate(sl):
        nm = str(smat.get_editor_property("material_slot_name"))
        if nm in want:
            smat.set_editor_property("material_interface", want[nm])
            sl[i] = smat
    sm.set_editor_property("static_materials", sl)
    for k, v in (("SpireA0_Note", m.note), ("SpireA0_Collision", "%s, %d boxes" % (m.collision, len(m.boxes)))):
        EAL.set_metadata_tag(sm, k, v)
    EAL.set_metadata_tag(sm, HASH_KEY, h)
    EAL.save_loaded_asset(sm, False)
    return "built"


def ue_assets():
    mats, mpaths = ue_materials()
    only = globals().get("SPIRE_ONLY")
    force = bool(globals().get("SPIRE_FORCE", False))
    ms = build_all_meshes()
    res = {"materials": mpaths, "meshes": {}}
    prog = {"started": time.strftime("%H:%M:%S"), "done": []}
    for name, m in ms.items():
        if only and name not in only:
            continue
        t = time.time()
        try:
            st = ue_build_mesh(m, mats, force)
        except Exception as e:  # noqa: BLE001
            st = "ERROR " + repr(e)
        res["meshes"][name] = {"status": st, "s": round(time.time() - t, 1), "tris": m.tri_count(), "boxes": len(m.boxes)}
        prog["done"].append(name)
        _write_json("SpireA0_assets_progress.json", prog)
        _log(name, st)
    res["ok"] = all(not v["status"].startswith("ERROR") for v in res["meshes"].values())
    return res


# ------------------------------------------------------------------ placement
def _add_ism(actor, name):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = sds.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.InstancedStaticMeshComponent,
                                          blueprint_context=None)
    out = sds.add_new_subobject(params)
    handle, fail = (out if isinstance(out, tuple) else (out, None))
    if fail is not None and str(fail):
        raise RuntimeError("add_new_subobject: " + str(fail))
    try:
        sds.rename_subobject(handle, unreal.Text(name))
    except Exception:
        pass
    data = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
    return unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)


def ue_delete_ours():
    acts = [a for a in _eas().get_all_level_actors() if _ours(a)]
    if acts:
        _eas().destroy_actors(acts)
    return len(acts)


def _spawn(label, loc, yaw, part):
    a = _eas().spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*loc), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    a.set_actor_label(label)
    a.set_folder_path(FOLDER)
    a.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("AOS_SpireA0_Part=" + part)])
    root = a.get_editor_property("static_mesh_component")
    root.set_mobility(unreal.ComponentMobility.STATIC)
    return a, root


def ue_place():
    world = _world().get_path_name()
    if "Lvl_FirstPerson" not in world:
        raise RuntimeError("open %s first (current: %s)" % (LEVEL_PATH, world))
    EAL = unreal.EditorAssetLibrary
    ms = build_all_meshes()
    missing = [n for n in ms if not EAL.does_asset_exist(MESH_DIR + "/" + n)]
    if missing:
        raise RuntimeError("run SPIRE_MODE='assets' first; missing: %s" % missing)
    sm = {n: EAL.load_asset(MESH_DIR + "/" + n) for n in ms}
    cpd = ue_infer_cpd()
    d1 = ue_find_d1()
    az = d1.get("azimuth", 0.0) if d1.get("usable") else 0.0
    removed = ue_delete_ours()
    res = {"removed": removed, "cpd": cpd, "d1": d1, "ring_azimuth": az, "actors": 0, "instances": {}}
    with unreal.ScopedSlowTask(1, "Spire A-0 placement") as _:
        for label, mesh, loc, yaw in placements(az):
            a, c = _spawn(label, loc, yaw, mesh)
            c.set_static_mesh(sm[mesh])
            c.set_collision_profile_name("BlockAll")
            _apply_cpd(c, cpd, loc)
            res["actors"] += 1
        tiles, stats, _ = slab_layout()
        res["slab"] = stats
        for key, t in sorted(tiles.items()):
            label = "A0_Slab_Tile_%+03d_%+03d" % key
            a, root = _spawn(label, t["loc"], 0.0, "SlabTile")
            root.set_collision_profile_name("NoCollision")
            res["actors"] += 1
            for mesh, L in t["inst"].items():
                comp = _add_ism(a, "ISM_" + mesh.replace("SM_A0_Slab_", ""))
                comp.set_static_mesh(sm[mesh])
                comp.set_mobility(unreal.ComponentMobility.STATIC)
                comp.set_collision_profile_name("BlockAll")
                xfs = [unreal.Transform(location=unreal.Vector(dx, dy, dz), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yw),
                                        scale=unreal.Vector(1.0, 1.0, 1.0)) for dx, dy, dz, yw in L]
                comp.add_instances(xfs, False, False)
                _apply_cpd(comp, cpd, t["loc"])
                res["instances"][mesh] = res["instances"].get(mesh, 0) + len(L)
    res["ok"] = res["instances"].get("SM_A0_Slab_Cell", 0) == stats["cells"]
    return res


# ------------------------------------------------------------------ context
def ue_anchors():
    out = []
    for a in _eas().get_all_level_actors():
        f = _folder(a)
        if f == ANCHOR_FOLDER or (f.startswith(ANCHOR_FOLDER + "/") and not f.startswith(FOLDER)):
            if _ours(a):
                continue
            l = a.get_actor_location()
            out.append({"label": a.get_actor_label(), "x": round(l.x, 1), "y": round(l.y, 1), "z": round(l.z, 1),
                        "on_axis": abs(l.x) < 1.0 and abs(l.y) < 1.0})
    return sorted(out, key=lambda d: -d["z"])


def ue_find_d1():
    """Start of the D-1 run: the snap socket (or bounds face) nearest the A-0 axis."""
    cands = []
    acts = [a for a in _eas().get_all_level_actors() if _folder(a).startswith(D1_FOLDER)]
    for a in acts:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            mesh = c.get_editor_property("static_mesh")
            if not mesh:
                continue
            names = []
            try:
                names = [str(s.get_editor_property("socket_name")) for s in (mesh.get_editor_property("sockets") or [])]
            except Exception:
                pass
            snaps = [n for n in names if "Snap" in n] or []
            for n in snaps:
                p = c.get_socket_location(n)
                fwd = c.get_socket_rotation(n).get_forward_vector()
                cands.append((math.hypot(p.x, p.y), (p.x, p.y, p.z), n, a.get_actor_label(), (fwd.x, fwd.y, fwd.z)))
            if not snaps:
                o, e = a.get_actor_bounds(False)
                # bounds face closest to the axis along the radial direction of the bounds centre
                rr = math.hypot(o.x, o.y) or 1.0
                ux, uy = o.x / rr, o.y / rr
                half = abs(ux) * e.x + abs(uy) * e.y
                p = (o.x - ux * half, o.y - uy * half, o.z)
                cands.append((math.hypot(p[0], p[1]), p, "bounds", a.get_actor_label(), (ux, uy, 0.0)))
    if not cands:
        return {"found": False, "usable": False, "actors": len(acts)}
    r, p, how, label, fwd = min(cands, key=lambda c: c[0])
    off = math.dist(p, D1_START)
    az = math.degrees(math.atan2(p[1], p[0]))
    usable = abs(r - D1_START[0]) < 1.0 and abs(p[2] - D1_START[2]) < 1.0
    return {"found": True, "actors": len(acts), "start": [round(v, 3) for v in p], "radius": round(r, 3), "azimuth": az,
            "via": how, "actor": label, "axis": [round(v, 4) for v in fwd], "offset_to_expected_cm": round(off, 3),
            "usable": usable}


# ------------------------------------------------------------------ verification
def _hit(h):
    if h is None:
        return None
    try:
        t = h.to_tuple()
    except Exception:
        t = unreal.GameplayStatics.break_hit_result(h)
    # (blocking, initial_overlap, time, distance, location, impact_point, normal, impact_normal, phys_mat, actor, comp, ...)
    actor = t[9]
    return {"blocking": bool(t[0]), "start_pen": bool(t[1]), "dist": float(t[3]),
            "loc": (t[4].x, t[4].y, t[4].z), "impact": (t[5].x, t[5].y, t[5].z),
            "actor": actor.get_actor_label() if actor else None}


def _objtypes():
    return [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1]   # WorldStatic


def _ignore(include_d1=False):
    ign = []
    for a in _eas().get_all_level_actors():
        if _ours(a):
            continue
        if include_d1 and _folder(a).startswith(D1_FOLDER):
            continue
        ign.append(a)
    return ign


def _line(a, b, ign):
    return _hit(unreal.SystemLibrary.line_trace_single_for_objects(
        _world(), unreal.Vector(*a), unreal.Vector(*b), _objtypes(), False, ign, unreal.DrawDebugTrace.NONE, True))


def _sphere(a, b, r, ign):
    return _hit(unreal.SystemLibrary.sphere_trace_single_for_objects(
        _world(), unreal.Vector(*a), unreal.Vector(*b), r, _objtypes(), False, ign, unreal.DrawDebugTrace.NONE, True))


def _boxsweep(a, b, half, yaw, ign):
    return _hit(unreal.SystemLibrary.box_trace_single_for_objects(
        _world(), unreal.Vector(*a), unreal.Vector(*b), unreal.Vector(*half), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw),
        _objtypes(), False, ign, unreal.DrawDebugTrace.NONE, True))


def ue_verify():
    EAL = unreal.EditorAssetLibrary
    ms = build_all_meshes()
    R = {"checks": [], "assets": {}, "warnings": []}

    def chk(name, ok, val=""):
        R["checks"].append({"check": name, "pass": bool(ok), "value": val})

    # assets
    for name, m in ms.items():
        p = MESH_DIR + "/" + name
        if not EAL.does_asset_exist(p):
            R["assets"][name] = "MISSING"
            continue
        sm = EAL.load_asset(p)
        info = {"hash": EAL.get_metadata_tag(sm, HASH_KEY) == m.geo_hash()}
        info["nanite"] = bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled"))
        body = sm.get_editor_property("body_setup")
        info["boxes"] = len(body.get_editor_property("agg_geom").get_editor_property("box_elems"))
        info["boxes_expected"] = len(m.boxes)
        info["trace_flag"] = str(body.get_editor_property("collision_trace_flag"))
        bb = sm.get_bounding_box()
        lo, hi = m.bounds()
        info["bounds_err_cm"] = round(max(abs(bb.min.x - lo[0]), abs(bb.min.y - lo[1]), abs(bb.min.z - lo[2]),
                                          abs(bb.max.x - hi[0]), abs(bb.max.y - hi[1]), abs(bb.max.z - hi[2])), 3)
        info["slots"] = [str(s.get_editor_property("material_slot_name")) + "=" +
                         (s.get_editor_property("material_interface").get_name() if s.get_editor_property("material_interface") else "NONE")
                         for s in sm.get_editor_property("static_materials")]
        try:
            info["tris"] = sm.get_num_triangles(0)
        except Exception:
            pass
        R["assets"][name] = info
    ok_assets = [n for n, i in R["assets"].items() if isinstance(i, dict) and i["nanite"] and i["boxes"] == i["boxes_expected"]
                 and i["bounds_err_cm"] < 0.5 and i["hash"]]
    chk("assets: %d meshes, Nanite on, collision count, bounds, hash" % len(ms), len(ok_assets) == len(ms),
        "%d/%d" % (len(ok_assets), len(ms)))

    # actors
    ours = [a for a in _eas().get_all_level_actors() if _ours(a)]
    by = {a.get_actor_label(): a for a in ours}
    want = placements(0.0)
    tiles, stats, oculi = slab_layout()
    chk("actors placed (unique pieces + slab tiles)", len(ours) == len(want) + len(tiles),
        "%d / %d" % (len(ours), len(want) + len(tiles)))
    chk("all in Outliner folder " + FOLDER, all(_folder(a) == FOLDER for a in ours))
    nin = {}
    for a in ours:
        for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
            mesh = c.get_editor_property("static_mesh")
            nin[mesh.get_name() if mesh else "?"] = nin.get(mesh.get_name() if mesh else "?", 0) + c.get_instance_count()
    chk("slab instances (cells / oculus cells / belt)", nin.get("SM_A0_Slab_Cell") == stats["cells"] and
        nin.get("SM_A0_Slab_CellOculus") == stats["oculus_cells"] and nin.get("SM_A0_Slab_Belt") == BELT_N, nin)

    # stacks from actor bounds
    def zr(label):
        a = by.get(label)
        if not a:
            return None
        o, e = a.get_actor_bounds(False)
        return (o.z - e.z, o.z + e.z)
    down = ["A0D_ICM_Disc", "A0D_Collar"] + ["A0D_Shaft_S%02d" % k for k in range(len(a0d_segments()), 0, -1)] + ["A0D_Capital"]
    up = ["A0U_Plinth"] + ["A0U_Shaft_S%02d" % k for k in range(1, len(A0U_SEGS))] + ["A0U_Collar", "A0U_ICM_Disc"]
    for nm, chain in (("A-0 down", down), ("A-0 up", up)):
        z = [zr(l) for l in chain]
        if None in z:
            chk(nm + " stack complete", False, "missing actors")
            continue
        g = max(abs(z[i][1] - z[i + 1][0]) for i in range(len(z) - 1))
        chk(nm + " stack continuous (max joint gap)", g < 0.5, "%.2f cm" % g)
    ign = _ignore()
    # A-0 down hangs from the slab: up the bus shaft from the disc to the slab underside
    h = _line((300, 300, A0D_COLLAR_Z[0] + 100), (300, 300, SLAB_TOP + 1000), ign)
    chk("A-0 down hangs from the slab: bus shaft open from the disc up to the slab underside Z -23 000",
        h is not None and abs(h["impact"][2] - SLAB_BOT) < 1.0, h)
    h = _line((300, 300, SLAB_BOT - 100), (300, 300, RING_Z), ign)
    chk("bus shaft floor = IC-M disc top Z -87 300", h is not None and abs(h["impact"][2] - A0D_COLLAR_Z[0]) < 1.0, h)
    # facades: horizontal rays toward the axis vs the analytic surface
    errs = []
    for label, mesh, loc, yaw in want:
        if not label.startswith(("A0D_Shaft", "A0U_Shaft", "A0D_Capital", "A0U_Plinth", "A0D_Collar", "A0U_Collar")):
            continue
        lo, hi = ms[mesh].bounds()
        for zf in (0.25, 0.75):
            zz = loc[2] + lo[2] + (hi[2] - lo[2]) * zf
            for az in (0.0, 30.0, 60.0, 90.0, 270.0):
                d = (math.cos(rad(az)), math.sin(rad(az)))
                exp = _ray_hit_mesh(ms[mesh], loc, d, zz)
                hh = _line((d[0] * 40000, d[1] * 40000, zz), (0, 0, zz), ign)
                if exp is not None and hh:
                    errs.append(abs(math.hypot(hh["impact"][0], hh["impact"][1]) - exp))
    chk("facade collision = visual surface (rays to the axis)", errs and max(errs) <= VIS_TOL + 5,
        "max %.1f cm over %d rays" % (max(errs) if errs else -1, len(errs)))
    # lower spire roots into the bed
    h = _line((A0U_PLINTH_R - 2000, 0, A0U_PLINTH_Z[1] + 2000), (A0U_PLINTH_R - 2000, 0, BED_Z - 1000), ign)
    chk("A-0 up plinth top at Z -157 000", h is not None and abs(h["impact"][2] - A0U_PLINTH_Z[1]) < 1.0, h)
    bed = _line((A0U_PLINTH_R + 3000, 0, BED_Z + 1000), (A0U_PLINTH_R + 3000, 0, BED_Z - 10000),
                [a for a in _eas().get_all_level_actors() if _ours(a)])
    R["bed_probe"] = bed
    if bed is None or abs(bed["impact"][2] - BED_Z) > 50:
        R["warnings"].append("no sector-bed geometry found at Z -160 000 next to the plinth (probe hit: %s)" % bed)
    # S4 gap
    hu = _line((3000, 0, RING_Z), (3000, 0, RING_Z + 5000), ign)
    hd = _line((3000, 0, RING_Z), (3000, 0, RING_Z - 5000), ign)
    gap = (hu["impact"][2] - hd["impact"][2]) if hu and hd else None
    chk("S4 gap measured between the IC-M discs = 3 000", gap is not None and abs(gap - 3000) < 1.0, gap)
    bad = []
    for az in range(0, 180, 30):
        c, s_ = math.cos(rad(az)), math.sin(rad(az))
        a, b = (-10000 * c, -10000 * s_, RING_Z), (10000 * c, 10000 * s_, RING_Z)
        if _sphere(a, b, SHELL_R, ign) or _boxsweep(a, b, (200, 100, 100), az, ign):
            bad.append(az)
        path = [(30000 * c, 30000 * s_, -84000.0), (12000 * c, 12000 * s_, -84000.0), (12000 * c, 12000 * s_, RING_Z), (0.0, 0.0, RING_Z)]
        for p, q in zip(path[:-1], path[1:]):
            if _sphere(p, q, SHELL_R, ign):
                bad.append(("entry", az))
    chk("S4 gap clear: Shell sphere + box sweeps across the gap and in over the ring (6 azimuths)", not bad, bad)
    # ring bus <-> D-1
    d1 = ue_find_d1()
    R["d1"] = d1
    jx = by.get("S4_RingBus_Junction_D1")
    if jx and d1.get("found"):
        L = jx.get_actor_location()
        yaw = jx.get_actor_rotation().yaw
        port = (L.x + (D1_START[0] - RING_R) * math.cos(rad(yaw)), L.y + (D1_START[0] - RING_R) * math.sin(rad(yaw)), L.z)
        off = math.dist(port, d1["start"])
        ang = math.degrees(math.acos(max(-1.0, min(1.0, abs(d1["axis"][0] * math.cos(rad(yaw)) + d1["axis"][1] * math.sin(rad(yaw)))))))
        chk("ring bus junction port = D-1 start (offset)", off < 0.05, "%.3f cm, axis angle %.3f deg" % (off, ang))
        ign_d1 = _ignore(include_d1=True)
        lane = 2700.0
        pts = [(RING_R * math.cos(rad(yaw + b)), RING_R * math.sin(rad(yaw + b)), RING_Z + lane) for b in [x * -2.5 for x in range(-138, 1)]]
        pts.append((port[0] + 2500 * math.cos(rad(yaw)), port[1] + 2500 * math.sin(rad(yaw)), RING_Z + lane))
        hits = [(i, h) for i, (p, q) in enumerate(zip(pts[:-1], pts[1:])) for h in [_sphere(p, q, SHELL_R, ign_d1)] if h]
        chk("ring bus lane (12 o'clock) -> junction -> 2 500 into D-1: Shell sphere clear", not hits, hits[:3])
        h = _sphere((RING_R, 0, RING_Z), (RING_R, 0, RING_Z + 10), 50.0, ign_d1)
        chk("control: ring centreline is inside the conductor", h is not None)
    else:
        chk("ring bus junction port = D-1 start (offset)", False, "junction or D-1 run not found: %s" % d1)
    # V-3
    v3 = [(-16000.0, 0.0, -135000.0), (-4000.0, 0.0, -135000.0), (-4000.0, 0.0, BED_Z + 300.0)]
    hv = [h for p, q in zip(v3[:-1], v3[1:]) for h in [_sphere(p, q, SHELL_R, ign)] if h]
    chk("V-3 entrance (az 180, Z -135 000) and drop to the bed clear", not hv, hv)
    chk("control: V-3 ceiling at Z -132 000", (lambda h: h is not None and abs(h["impact"][2] - V3_BAND[1]) < 1.0)(
        _line((-4000, 0, -135000), (-4000, 0, -125000), ign)))
    # slab
    ho = _sphere((24000, 0, SLAB_TOP + 1000), (24000, 0, SLAB_BOT - 1000), SHELL_R, ign)
    chk("oculus (24 000, 0) pass-through clear", ho is None, ho)
    hs = _sphere((-60000, 0, SLAB_TOP + 1000), (-60000, 0, SLAB_BOT - 1000), 2900.0, ign)
    chk("Socket shaft well (-60 000, 0) open (sphere r 2 900)", hs is None, hs)
    hc = _line((2400, 2400, SLAB_TOP + 1000), (2400, 2400, SLAB_BOT - 1000), ign)
    chk("control: slab top at Z -18 000", hc is not None and abs(hc["impact"][2] - SLAB_TOP) < 1.0, hc)
    # foreign geometry intersecting the new volumes
    vols = [("slab", (-SLAB_R, -SLAB_R, SLAB_BOT), (SLAB_R, SLAB_R, SLAB_TOP)),
            ("A-0 down", (-13100, -13100, A0D_DISC_Z0), (13100, 13100, SLAB_BOT)),
            ("S4 ring", (-24500, -24500, RING_Z - 4500), (24500, 24500, RING_Z + 4500)),
            ("A-0 up", (-15000, -15000, BED_Z), (15000, 15000, A0U_DISC_Z0 + DISC_T))]
    hitlist = []
    for a in _eas().get_all_level_actors():
        if _ours(a) or _folder(a).startswith(D1_FOLDER):
            continue
        cls = a.get_class().get_name()
        if any(k in cls for k in ("Volume", "Water", "Light", "Fog", "Sky", "Info", "Camera", "PlayerStart", "Brush")):
            continue
        try:
            o, e = a.get_actor_bounds(True)
        except Exception:
            continue
        if e.x == 0 and e.y == 0 and e.z == 0:
            continue
        for vn, lo, hi in vols:
            if all(o_ - e_ < h_ and o_ + e_ > l_ for o_, e_, l_, h_ in zip((o.x, o.y, o.z), (e.x, e.y, e.z), lo, hi)):
                if vn == "slab" and math.hypot(o.x, o.y) - math.hypot(e.x, e.y) > SLAB_R:
                    continue
                hitlist.append({"actor": a.get_actor_label(), "class": cls, "folder": _folder(a), "volume": vn,
                                "bounds_z": (round(o.z - e.z), round(o.z + e.z))})
    R["foreign_intersections"] = hitlist
    if hitlist:
        R["warnings"].append("%d foreign actors overlap the new volumes (see foreign_intersections)" % len(hitlist))
    R["anchors"] = ue_anchors()
    R["pass"] = sum(1 for c in R["checks"] if c["pass"])
    R["fail"] = sum(1 for c in R["checks"] if not c["pass"])
    return R


def ue_save():
    unreal.EditorAssetLibrary.save_directory(MESH_DIR, only_if_is_dirty=True, recursive=True)
    ok = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    return {"saved": bool(ok), "world": _world().get_path_name()}


# =============================================================================
# 7. ENTRY
# =============================================================================
def run(mode):
    if unreal is None:
        raise RuntimeError("run inside the Unreal Editor (or use --selftest)")
    t0 = time.time()
    del _LOG[:]
    if mode == "probe":
        r = ue_probe()
    elif mode == "assets":
        r = ue_assets()
    elif mode == "place":
        r = ue_place()
    elif mode == "verify":
        r = ue_verify()
    elif mode == "save":
        r = ue_save()
    elif mode == "all":
        r = {"assets": ue_assets()}
        r["place"] = ue_place()
        r["verify"] = ue_verify()
        r["save"] = ue_save()
    else:
        raise ValueError("SPIRE_MODE must be probe|assets|place|verify|save|all")
    r["mode"], r["seconds"], r["log"] = mode, round(time.time() - t0, 1), list(_LOG)
    r["report_file"] = _write_json("SpireA0_%s.json" % mode, r)
    return r


if unreal is not None and "SPIRE_MODE" in globals():
    result = run(globals()["SPIRE_MODE"])

if __name__ == "__main__" and "--selftest" in sys.argv:
    _rep = selftest()
    _fails = [c for c in _rep["checks"] if not c[1]]
    print("\nSELFTEST: %d checks, %d failed" % (len(_rep["checks"]), len(_fails)))
    sys.exit(1 if _fails else 0)
