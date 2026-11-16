# =============================================================================
# AOS-DK | Macro kit "Monoliths" (Tower A, Stage 2) | 3ds Max 2027 (pymxs) -> FBX -> UE 5.7.4
# Tower A Spatial Bible §1.3 (zoning), §1.4 (plan layout, monolith rules), §1.6 (depth rings), §4.3 (cluster C-01).
# Same pipeline as Tools/max_build_SpireA0_Kit.py: welded closed solids, chamfered, convex UCX hulls (<= 32 verts),
# box UVW 400 cm, one FBX per asset, spec JSON (mesh stats + assembly table) as the single source for the UE script.
#
#   SM_SectorBed_Tile        24 000 x 24 000 x 2 000 bed plate: 4 coffered pads, 1 200 x 400 trenches     pivot: centre, bed level
#   SM_TowerA3_Hull          Tower A-3 envelope around C-01: podium (quay + arena terrace), shaft, east   pivot: cluster origin B
#                            bay, roof parapet; through-cuts for the SomaLock portal and the R6 north slot
#   SM_Monolith_Square_Seg   8 000 x 8 000 x 10 000 shaft module, depth-ring recess 3 000 above its base   pivot: top centre
#   SM_Monolith_Octagon_Seg  AF 10 000 x 10 000 octagonal shaft module, same ring recess                  pivot: top centre
#   SM_Monolith_Crown        6 000 x 6 000 x 17 200 stepped crown, ring recess at 8 000 (= Z -10 000)     pivot: bottom centre
#
# Material slots (fixed order): MS_Concrete, MS_DepthRing (strip 120 cm on the 100 m mark), MS_DepthRing2 (second strip,
# lit only on the 500 m marks: the "double Cyan" of §1.6).
# Units: cm, Z-up. Everything except the hull is mirror-symmetric in Y; the hull is authored in UE-local coordinates and
# mirrored (y -> -y) for Max, so the Max RH -> UE LH import (x, -y, z) lands it un-mirrored.
#
# Run in Max:  ns = {}; exec(open(r"<proj>\Tools\max_build_Monoliths_Kit.py").read(), ns); ns["MONO_RESULT"]
#              then ns["max_export"]() and ns["max_save"]()
# Offline self-test (no Max, needs numpy + scipy):  python max_build_Monoliths_Kit.py
# =============================================================================
import math, json, os

try:
    from pymxs import runtime as rt
    IN_MAX = True
except Exception:
    rt = None
    IN_MAX = False

PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
FBX_DIR = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "Macro", "Monoliths")
SPEC_PATH = os.path.join(PROJ, "Tools", "Monoliths_Kit_spec.json")
MAX_PATH = os.path.join(PROJ, "SourceArt", "Macro", "Monoliths_Kit.max")
SLOTS = ["MS_Concrete", "MS_DepthRing", "MS_DepthRing2"]
M_CON, M_RING, M_RING2 = 1, 2, 3

# ---------------------------------------------------------------- bible metrics (cm)
Z_SLAB_TOP, Z_SLAB_BOT, Z_BED = -18000.0, -23000.0, -160000.0     # §2.3 / §1.3
TILE, SLAB_R = 24000.0, 300000.0                                  # slab / bed tile grid, slab disc radius
RING_STEP = 10000.0                                               # §1.6: depth ring every 100 m
SEG_H, SEG_RING = 10000.0, 3000.0                                 # shaft module height; ring centre above the module base
SQ_A, OCT_A = 4000.0, 5000.0                                      # base apothems: square 8 000, octagon AF 10 000
SQ_KAP, OCT_KAP = 0.10, 0.06                                      # corner chamfer / apothem
CROWN_A, CROWN_H, CROWN_RING = 3000.0, 17200.0, 8000.0            # crown 6 000 x 6 000, roof steps -3 500 / -2 000 / -800
BED_T, BED_TR, BED_TD = 2000.0, 600.0, 400.0                      # bed plate thickness, trench half-width, trench depth
T8 = math.tan(math.radians(22.5))
SHELL_R = math.sqrt(200.0 ** 2 + 100.0 ** 2 + 100.0 ** 2)         # Shell-1 any-orientation sphere R 245

# ---------------------------------------------------------------- Tower A-3 / cluster C-01 (world cm, measured in Lvl_FirstPerson)
A3_B = (-48000.0, 22000.0, -9800.0)                               # §4.3 cluster origin B = hull pivot
ROOMS = {                                                         # outer shells of the SHELL_* actors (x0, x1, y0, y1, z0, z1)
    "R1": (-53600, -51000, 20500, 23900, -9900, -8350), "K1": (-51000, -48600, 20500, 21570, -9900, -9060),
    "R4": (-48600, -46800, 20500, 23100, -9900, -8800), "DS": (-48900, -48600, 22240, 22760, -9900, -9380),
    "R2": (-51100, -48900, 21900, 24100, -9900, -5200), "R3": (-52100, -47900, 24000, 27000, -9000, -7450),
    "R5": (-49000, -45600, 21500, 24100, -6300, -5200), "R6": (-47900, -45700, 24100, 25400, -6300, -5500)}
ROOM_WALL = 100.0
KEEP = {                                                          # volumes the hull must stay out of (world)
    "SomaLock bounds": (-54621, -53477, 20693, 22638, -9750, -8540),
    "TP-B portal frame": (-57434, -56290, 21762, 23707, -9750, -8540),
    "TP-B transit shaft": (-59822, -57422, 21906, 22817, -9605, -8694),
    "TP-B entrance trigger": (-56291, -55791, 21900, 22500, -9450, -8850),
    "TP-B exit lane (ExitPoint -> lock Nav_In, Shell + swarm)": (-55800, -54600, 21600, 22500, -9300, -8950),
    "Reaper NavMeshBoundsVolume": (-45700, -41300, 19800, 24200, -9950, -9000),
    "Reaper arena column (floor -> open water)": (-45500, -41500, 20000, 24000, -9900, 0)}
# hull massing
POD = (-60400.0, -40900.0, 19300.0, 28200.0)                      # podium x0, x1, y0, y1: west quay under TP-B, east terrace under the arena
POD_C, POD_TOP = 600.0, -9960.0                                   # corner chamfer; terrace 10 cm below the Reaper nav bounds (-9 950)
SH = (-54700.0, -45800.0, 19700.0, 27800.0)                       # shaft x0, x1, y0, y1 (east face 100 clear of the nav bounds)
SH_C = 300.0
Z_REV = (-7550.0, -7400.0, -7200.0, -7050.0)                      # shaft shadow reveal
Z_ROOF, Z_PAR = -5000.0, -4800.0                                  # roof deck (200 over the C-01 ceilings at -5 200), parapet top
PORTAL = (20600.0, 23800.0, -9800.0, -8450.0)                     # y0, y1, z0, z1 = R1 interior section: whole R1 west wall + lock exposed
PORTAL_CH = 150.0
SLOT = (-47800.0, -46300.0, -6200.0, -5600.0)                     # x0, x1, z0, z1 on the R6 north wall (future DispatchWindow)
SLOT_CH = 100.0
BAY_X, BAY_Y, BAY_Z = -45500.0, (20900.0, 26000.0), (-6900.0, -6600.0, -5050.0)   # east bay over R5 / R6 (flush with the arena floor edge)
BAY_DRAFT = 100.0
CAV_M = 10.0                                                      # cavity clearance around the room shells

# ---------------------------------------------------------------- 24 monolith axes (§1.4): id, ring, azimuth°, r, stalactite shape,
# stalactite AF, stalactite modules, stalagmite AF, stalagmite top, crown X, crown Y.  Axes are snapped to the 12 000 lattice of
# tile corners / edge mid-points (never an oculus centre).  Junction of a paired axis: tip at -93 000 / -83 000 over a stalagmite
# top at -97 000 / -87 000 (4 000 between raw shaft ends = room for two IC-P collars 1 400 + the 1 200 gap of §2.6).
MONO = [
    ("M-01", "R1",  22,  64000, "sq",  7500, 7, 11000, -97000, 6000, 5000),
    ("M-02", "R1", 344,  66000, "oct", 7000, 4,  8000, -87000, 5000, 5000),
    ("M-03", "R1", 100,  58000, "sq",  9000, 6, 12000, -87000, 8000, 6000),
    ("M-04", "R1", 203,  56000, "oct", 7000, 7, 10000, -97000, 4000, 4000),
    ("M-05", "R1", 283,  60000, "sq",  6000, 3,  9000, -97000, 6000, 4000),
    ("M-06", "R2",   0, 118000, "oct", 9000, 7, 15000, -97000, 8000, 6000),
    ("M-07", "R2",  32,  98000, "sq",  8000, 5, 12000, -87000, 6000, 6000),
    ("M-08", "R2",  60, 124000, "sq",  9000, 6, 14000, -87000, 8000, 5000),
    ("M-09", "R2",  91, 104000, "oct", 7000, 7, 11000, -97000, 5000, 4000),
    ("M-10", "R2", 120, 116000, "sq",  8000, 6, 13000, -87000, 7000, 6000),
    ("M-11", "R2", 148,  96000, "oct", 8000, 3, 12000, -87000, 6000, 5000),
    ("M-12", "R2", 188, 128000, "sq",  9000, 7, 15000, -97000, 8000, 6000),
    ("M-13", "R2", 212, 102000, "sq",  7000, 4, 10000, -97000, 5000, 5000),
    ("M-14", "R2", 240, 120000, "oct", 9000, 6, 14000, -87000, 7000, 5000),
    ("M-15", "R2", 268,  94000, "sq",  8000, 7, 12000, -97000, 6000, 6000),
    ("M-16", "R2", 300, 126000, "sq",  9000, 5, 13000, -87000, 8000, 6000),
    ("M-17", "R2", 329, 106000, "oct", 8000, 6, 12000, -87000, 6000, 4000),
    ("M-18", "R3",  14, 190000, "sq",  9000, 7, 15000, -97000, 8000, 6000),
    ("M-19", "R3",  65, 235000, "oct", 9000, 6, 14000, -87000, 7000, 6000),
    ("M-20", "R3", 117, 175000, "sq",  8000, 4, 13000, -87000, 6000, 6000),
    ("M-21", "R3", 168, 250000, "sq",  9000, 7, 15000, -97000, 8000, 6000),
    ("M-22", "R3", 220, 205000, "oct", 8000, 6, 13000, -87000, 6000, 5000),
    ("M-23", "R3", 271, 240000, "sq",  9000, 5, 14000, -97000, 8000, 5000),
    ("M-24", "R3", 322, 180000, "oct", 9000, 7, 15000, -97000, 7000, 6000),
]
RINGS = {"R1": (40000.0, 70000.0), "R2": (90000.0, 150000.0), "R3": (150000.0, 300000.0)}
EXPLORABLE = {"S-2": (35000.0, -30000.0), "S-5": (20000.0, 40000.0), "X-4": (-20000.0, -55000.0)}   # assumed half-size 4 500
SOCKET = (-60000.0, 0.0, 3000.0)                                  # dock shaft Ø 6 000
D1_BOX = (24000.0, 60000.0, -4400.0, 4400.0)                      # D-1 run (flange OD 8 800)
BND_APOTHEM, BND_T = 150000.0, 2000.0                             # containment 24-gon (setup_macro_topology.py)

# ---------------------------------------------------------------- vector helpers
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vdot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def vlen(a): return math.sqrt(vdot(a, a))
def vunit(a): l = vlen(a); return (a[0]/l, a[1]/l, a[2]/l)

# ---------------------------------------------------------------- mesh builder (welded, closed, auto-oriented) — as in the Spire kit
class MB(object):
    def __init__(self, name):
        self.name = name; self.v = []; self.idx = {}; self.f = []      # f: [a, b, c, mat, sg, (vis ab, bc, ca)]
    def vert(self, p):
        k = (round(p[0], 3) + 0.0, round(p[1], 3) + 0.0, round(p[2], 3) + 0.0)
        i = self.idx.get(k)
        if i is None:
            i = len(self.v); self.idx[k] = i; self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return i
    def _tri(self, ia, ib, ic, mat, sg, vis):
        if ia == ib or ib == ic or ia == ic: return
        self.f.append([ia, ib, ic, mat, sg, tuple(vis)])
    def tri(self, a, b, c, mat=1, sg=0, vis=(1, 1, 1)):
        self._tri(self.vert(a), self.vert(b), self.vert(c), mat, sg, vis)
    def poly(self, pts, mat=1, sg=0):
        ids = []
        for p in pts:
            i = self.vert(p)
            if not ids or ids[-1] != i: ids.append(i)
        if len(ids) > 1 and ids[0] == ids[-1]: ids.pop()
        n = len(ids)
        for i in range(1, n - 1):
            self._tri(ids[0], ids[i], ids[i+1], mat, sg, (1 if i == 1 else 0, 1, 1 if i == n - 2 else 0))
    def quad(self, a, b, c, d, mat=1, sg=0): self.poly([a, b, c, d], mat, sg)
    def loft(self, r0, r1, mat=1, sg=0, closed=True):
        n = len(r0)
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            self.quad(r0[i], r0[j], r1[j], r1[i], mat, sg)
    def mirror_y(self):
        self.v = [(p[0], -p[1], p[2]) for p in self.v]; self.idx = {}
    def translate(self, t):
        self.v = [(p[0]+t[0], p[1]+t[1], p[2]+t[2]) for p in self.v]; self.idx = {}

    # ---- validation + orientation
    def finalize(self):
        F = self.f; emap = {}
        for fi, f in enumerate(F):
            for e in range(3):
                a, b = f[e], f[(e+1) % 3]
                emap.setdefault((min(a, b), max(a, b)), []).append(fi)
        bad = [e for e, l in emap.items() if len(l) != 2]
        if bad:
            raise ValueError("%s: %d non-manifold edges, e.g. %s" % (self.name, len(bad), [(self.v[a], self.v[b]) for a, b in bad[:4]]))
        def has_dir(f, a, b): return (f[0] == a and f[1] == b) or (f[1] == a and f[2] == b) or (f[2] == a and f[0] == b)
        def flip(f): f[1], f[2] = f[2], f[1]; f[5] = (f[5][2], f[5][1], f[5][0])
        seen = [False] * len(F); shells = 0; vol_total = 0.0
        for s in range(len(F)):
            if seen[s]: continue
            comp = [s]; seen[s] = True; q = [s]
            while q:
                fi = q.pop(); f = F[fi]
                for e in range(3):
                    a, b = f[e], f[(e+1) % 3]
                    for g in emap[(min(a, b), max(a, b))]:
                        if g == fi or seen[g]: continue
                        if has_dir(F[g], a, b): flip(F[g])
                        seen[g] = True; comp.append(g); q.append(g)
            vol = 0.0
            for fi in comp:
                f = F[fi]; vol += vdot(self.v[f[0]], vcross(self.v[f[1]], self.v[f[2]])) / 6.0
            if vol < 0:
                for fi in comp: flip(F[fi])
                vol = -vol
            shells += 1; vol_total += vol
        dirs = {}
        for f in F:
            for e in range(3):
                k = (f[e], f[(e+1) % 3]); dirs[k] = dirs.get(k, 0) + 1
        if any(c != 1 for c in dirs.values()): raise ValueError(self.name + ": inconsistent winding")
        xs = [p[0] for p in self.v]; ys = [p[1] for p in self.v]; zs = [p[2] for p in self.v]
        self.stats = {"verts": len(self.v), "tris": len(F), "shells": shells, "volume_m3": round(vol_total / 1e6, 1),
                      "bbox_min": [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3)],
                      "bbox_max": [round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)],
                      "mat_ids": sorted(set(f[3] for f in F))}
        return self.stats

class Kit(object):
    def __init__(self, name, note, slots=None):
        self.mb = MB(name); self.name = name; self.note = note; self.ucx = []; self.slots = slots or ["MS_Concrete"]
    def hull(self, bot, top, label=""):
        assert len(bot) == len(top) and len(bot) >= 3 and 2*len(bot) <= 32, (self.name, label, len(bot))
        self.ucx.append((list(bot), list(top), label))
    def box(self, x0, x1, y0, y1, z0, z1, label=""):
        self.hull([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], label)
    def prism(self, poly2, z0, z1, label=""):
        self.hull([(x, y, z0) for x, y in poly2], [(x, y, z1) for x, y in poly2], label)
    def transform(self, t, mirror):
        """World -> pivot-local, optional Max mirror (y -> -y)."""
        s = -1.0 if mirror else 1.0
        self.mb.v = [(p[0]-t[0], s*(p[1]-t[1]), p[2]-t[2]) for p in self.mb.v]; self.mb.idx = {}
        self.ucx = [([(p[0]-t[0], s*(p[1]-t[1]), p[2]-t[2]) for p in b], [(p[0]-t[0], s*(p[1]-t[1]), p[2]-t[2]) for p in tp], l) for b, tp, l in self.ucx]

# ---------------------------------------------------------------- section helpers
def ngon_ring(nf, a, z, kap, sx=1.0, sy=1.0):
    """Chamfered regular nf-gon (2 nf verts, CCW), flats on +X first; apothem a; optional XY stretch."""
    w = a * (math.tan(math.pi / nf) - kap); pts = []
    for k in range(nf):
        ph = 2.0 * math.pi * k / nf; h = (math.cos(ph), math.sin(ph)); t = (-math.sin(ph), math.cos(ph))
        pts.append(((a*h[0] - w*t[0]) * sx, (a*h[1] - w*t[1]) * sy, z)); pts.append(((a*h[0] + w*t[0]) * sx, (a*h[1] + w*t[1]) * sy, z))
    return pts

def rect8(r, c, z, inset=0.0):
    """Chamfered rectangle loop (8 verts, CCW from +Z). Edges: 0 E, 1 NE, 2 N, 3 NW, 4 W, 5 SW, 6 S, 7 SE."""
    x0, x1, y0, y1 = r[0] + inset, r[1] - inset, r[2] + inset, r[3] - inset
    return [(x1, y0+c, z), (x1, y1-c, z), (x1-c, y1, z), (x0+c, y1, z), (x0, y1-c, z), (x0, y0+c, z), (x0+c, y0, z), (x1-c, y0, z)]

def clip(poly, f):
    """Sutherland-Hodgman: keep the part of a convex 2D polygon where f(p) >= 0."""
    out = []; n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i+1) % n]; fp, fq = f(p), f(q)
        if fp >= 0: out.append(p)
        if (fp > 0 and fq < 0) or (fp < 0 and fq > 0):
            t = fp / (fp - fq); out.append((p[0] + t*(q[0]-p[0]), p[1] + t*(q[1]-p[1])))
    res = []
    for p in out:
        if not res or math.hypot(p[0]-res[-1][0], p[1]-res[-1][1]) > 1e-6: res.append(p)
    if len(res) > 1 and math.hypot(res[0][0]-res[-1][0], res[0][1]-res[-1][1]) < 1e-6: res.pop()
    return res

def clip_to(rect, conv):
    """Rectangle (x0, x1, y0, y1) clipped to a CCW convex polygon."""
    p = [(rect[0], rect[2]), (rect[1], rect[2]), (rect[1], rect[3]), (rect[0], rect[3])]
    n = len(conv)
    for i in range(n):
        a, b = conv[i], conv[(i+1) % n]
        p = clip(p, lambda q, a=a, b=b: (b[0]-a[0])*(q[1]-a[1]) - (b[1]-a[1])*(q[0]-a[0]))
        if len(p) < 3: return []
    return p

def panel(mb, Q, centre, mh, mv, D, mat=1):
    """Chamfered recessed panel in a planar quad Q = [a, b, c, d] (a->b bottom edge, d above a): 45° reveal, depth D."""
    a = Q[0]; W = vlen(vsub(Q[1], Q[0])); Hh = vlen(vsub(Q[3], Q[0]))
    u = vunit(vsub(Q[1], Q[0])); v = vunit(vsub(Q[3], Q[0])); n = vunit(vcross(u, v))
    if vdot(n, vsub(a, centre)) < 0: n = vmul(n, -1.0)
    def pt(s, t, d): return vadd(vadd(vadd(a, vmul(u, s)), vmul(v, t)), vmul(n, -d))
    O = [pt(mh, mv, 0), pt(W - mh, mv, 0), pt(W - mh, Hh - mv, 0), pt(mh, Hh - mv, 0)]
    I = [pt(mh + D, mv + D, D), pt(W - mh - D, mv + D, D), pt(W - mh - D, Hh - mv - D, D), pt(mh + D, Hh - mv - D, D)]
    for e in range(4):
        g = (e + 1) % 4
        mb.quad(Q[e], Q[g], O[g], O[e], mat); mb.quad(O[e], O[g], I[g], I[e], mat)
    mb.poly(I, mat)

def frame_rect(mb, Q, inner, mat=1):
    """Planar quad Q = [a, b, c, d] with a rectangular hole whose rim 'inner' may carry extra collinear vertices:
    four trapezoids, each fanned from its outer corner (no T-junctions, no slivers across the hole)."""
    a = Q[0]; u = vunit(vsub(Q[1], Q[0])); v = vunit(vsub(Q[3], Q[0]))
    uv = lambda p: (vdot(vsub(p, a), u), vdot(vsub(p, a), v))
    inner = list(inner); P = [uv(p) for p in inner]; n = len(inner)
    if sum(P[i][0]*P[(i+1) % n][1] - P[(i+1) % n][0]*P[i][1] for i in range(n)) < 0:
        inner.reverse(); P.reverse()
    us = [p[0] for p in P]; vs = [p[1] for p in P]
    corners = [(min(us), min(vs)), (max(us), min(vs)), (max(us), max(vs)), (min(us), max(vs))]
    cidx = [min(range(n), key=lambda i, c=c: (P[i][0]-c[0])**2 + (P[i][1]-c[1])**2) for c in corners]
    area = 0.0
    def tri(p, q, r_, vis):
        nonlocal area
        (u0, v0), (u1, v1), (u2, v2) = uv(p), uv(q), uv(r_); t = ((u1-u0)*(v2-v0) - (u2-u0)*(v1-v0)) / 2.0
        assert t > 1e-6, "frame_rect: flipped or degenerate triangle"
        area += t; mb.tri(p, q, r_, mat, 0, vis)
    for k in range(4):
        i0, i1 = cidx[k], cidx[(k+1) % 4]
        chain = [inner[(i0 + m) % n] for m in range(((i1 - i0) % n) + 1)]
        for m in range(len(chain) - 1): tri(Q[k], chain[m+1], chain[m], (0, 1, 0))
        tri(Q[k], Q[(k+1) % 4], chain[-1], (1, 0, 0))
    W = vlen(vsub(Q[1], Q[0])); Hh = vlen(vsub(Q[3], Q[0]))
    assert abs(area - (W * Hh - (max(us) - min(us)) * (max(vs) - min(vs)))) < 1.0, "frame_rect: area mismatch"

def grid_shell(mb, xs, ys, zs, empty, mouths, mat=1):
    """Boundary of a rectilinear void (union of boxes on a non-uniform grid) as grid-aligned quads. Faces on a mouth
    plane (axis, coord) are left open; returns the ordered rim loop of every mouth."""
    ax = [xs, ys, zs]; n = [len(xs) - 1, len(ys) - 1, len(zs) - 1]
    def emp(i):
        if min(i) < 0 or i[0] >= n[0] or i[1] >= n[1] or i[2] >= n[2]: return None
        return bool(empty((xs[i[0]] + xs[i[0]+1]) / 2, (ys[i[1]] + ys[i[1]+1]) / 2, (zs[i[2]] + zs[i[2]+1]) / 2))
    f0 = len(mb.f)
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                c = (i, j, k)
                if not emp(c): continue
                for a in range(3):
                    for side in (0, 1):
                        nb = list(c); nb[a] += 1 if side else -1; e = emp(nb)
                        if e: continue
                        co = ax[a][c[a] + side]
                        if e is None and any(m[0] == a and abs(m[1] - co) < 1e-6 for m in mouths): continue
                        b1, b2 = (a + 1) % 3, (a + 2) % 3
                        def P(s, t):
                            p = [0.0, 0.0, 0.0]; p[a] = co; p[b1] = ax[b1][c[b1] + s]; p[b2] = ax[b2][c[b2] + t]; return tuple(p)
                        mb.quad(P(0, 0), P(1, 0), P(1, 1), P(0, 1), mat)
    cnt = {}
    for f in mb.f[f0:]:
        for e in range(3):
            k = (min(f[e], f[(e+1) % 3]), max(f[e], f[(e+1) % 3])); cnt[k] = cnt.get(k, 0) + 1
    rims = {}
    for (a, co) in mouths:
        adj = {}
        for (p, q), c_ in cnt.items():
            if c_ == 1 and abs(mb.v[p][a] - co) < 1e-6 and abs(mb.v[q][a] - co) < 1e-6:
                adj.setdefault(p, []).append(q); adj.setdefault(q, []).append(p)
        assert adj and all(len(l) == 2 for l in adj.values()), ("mouth rim", a, co)
        start = min(adj); loop = [start]; prev = None; cur = start
        while True:
            nxt = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
            if nxt == start: break
            loop.append(nxt); prev, cur = cur, nxt
        assert len(loop) == len(adj), ("mouth rim not a single loop", a, co)
        rims[(a, co)] = [mb.v[i] for i in loop]
    return rims

# ================================================================= builders
def ring_recess(zc, a, flip=1.0):
    """Profile rows (z, apothem, material of the band that ENDS at this row) of the chamfered depth-ring recess.
    Strip 1 (MS_DepthRing) is centred on zc; strip 2 (MS_DepthRing2) sits 240 above it; recess depth 120."""
    d = 120.0
    return [(zc - 360.0, a, M_CON), (zc - 240.0, a - d, M_CON), (zc - 60.0, a - d, M_CON), (zc + 60.0, a - d, M_RING),
            (zc + 180.0, a - d, M_CON), (zc + 300.0, a - d, M_RING2), (zc + 480.0, a - d, M_CON), (zc + 600.0, a, M_CON)]

def build_segment(name, nf, a, kap, note):
    """Shaft module 10 000 tall, pivot top centre: reveal joints top/bottom, one recessed panel per face above and below the
    depth-ring recess. Hanging (stalactite) or rolled 180° (stalagmite: the pivot becomes the bottom centre)."""
    k = Kit(name, note, SLOTS); mb = k.mb; H = SEG_H; dl = 150.0
    R = lambda z, aa: ngon_ring(nf, aa, z, kap)
    zr = -H + SEG_RING
    rec = ring_recess(zr, a)                                              # rows bottom -> top
    top = [(0.0, a - dl), (-200.0, a - dl), (-350.0, a)]
    bot = [(-H + 350.0, a), (-H + 200.0, a - dl), (-H, a - dl)]
    for rows in (top, bot):
        for i in range(len(rows) - 1): mb.loft(R(*rows[i]), R(*rows[i+1]))
    mb.poly(R(*top[0])); mb.poly(R(*bot[-1]))
    for i in range(len(rec) - 1): mb.loft(R(rec[i][0], rec[i][1]), R(rec[i+1][0], rec[i+1][1]), rec[i+1][2])
    w = a * (math.tan(math.pi / nf) - kap)
    for (z0, z1) in ((bot[0][0], rec[0][0]), (rec[-1][0], top[-1][0])):   # two panel bands (lower, upper)
        R0, R1 = R(z0, a), R(z1, a)
        for f in range(nf):
            i1, i2 = 2*f + 1, (2*f + 2) % (2*nf)
            mb.quad(R0[i1], R0[i2], R1[i2], R1[i1])                       # corner chamfer
            Q = [R0[2*f], R0[2*f+1], R1[2*f+1], R1[2*f]]
            panel(mb, Q, (0.0, 0.0, (z0 + z1) / 2), 0.2 * w, 400.0, 240.0)
    k.hull(R(-H, a), R(0.0, a), "shaft")
    return k

def build_square(): return build_segment("SM_Monolith_Square_Seg", 4, SQ_A, SQ_KAP, "Monolith shaft module, square 8 000 x 8 000 x 10 000, depth-ring recess 3 000 above the base")
def build_octagon(): return build_segment("SM_Monolith_Octagon_Seg", 8, OCT_A, OCT_KAP, "Monolith shaft module, octagon AF 10 000 x 10 000, depth-ring recess 3 000 above the base")

def build_crown():
    k = Kit("SM_Monolith_Crown", "Monolith crown 6 000 x 6 000 x 17 200: plinth, shaft with depth-ring recess at 8 000, cornice, two roof setbacks", SLOTS)
    mb = k.mb; A = CROWN_A; kap = 0.10
    R = lambda z, aa: ngon_ring(4, aa, z, kap)
    a2, a3 = 0.72 * A, 0.40 * A
    rec = ring_recess(CROWN_RING, A)
    low = [(0.0, A + 250.0), (500.0, A + 250.0), (750.0, A)]
    upp = [(13700.0, A), (13900.0, A + 200.0), (14500.0, A + 200.0), (14500.0, a2), (15850.0, a2), (16000.0, a2 - 150.0),
           (16000.0, a3), (17050.0, a3), (17200.0, a3 - 150.0)]
    for rows in (low, upp):
        for i in range(len(rows) - 1): mb.loft(R(*rows[i]), R(*rows[i+1]))
    mb.poly(R(*low[0])); mb.poly(R(*upp[-1]))
    for i in range(len(rec) - 1): mb.loft(R(rec[i][0], rec[i][1]), R(rec[i+1][0], rec[i+1][1]), rec[i+1][2])
    w = A * (1.0 - kap)
    for (z0, z1) in ((low[-1][0], rec[0][0]), (rec[-1][0], upp[0][0])):
        R0, R1 = R(z0, A), R(z1, A)
        for f in range(4):
            i1, i2 = 2*f + 1, (2*f + 2) % 8
            mb.quad(R0[i1], R0[i2], R1[i2], R1[i1])
            panel(mb, [R0[2*f], R0[2*f+1], R1[2*f+1], R1[2*f]], (0.0, 0.0, (z0 + z1) / 2), 0.2 * w, 450.0, 200.0)
    k.hull(R(0.0, A + 250.0), R(500.0, A + 250.0), "plinth"); k.hull(R(500.0, A + 250.0), R(750.0, A), "plinth chamfer")
    k.hull(R(750.0, A), R(13700.0, A), "shaft"); k.hull(R(13700.0, A), R(13900.0, A + 200.0), "cornice chamfer")
    k.hull(R(13900.0, A + 200.0), R(14500.0, A + 200.0), "cornice")
    k.hull(R(14500.0, a2), R(15850.0, a2), "setback 1"); k.hull(R(15850.0, a2), R(16000.0, a2 - 150.0), "setback 1 chamfer")
    k.hull(R(16000.0, a3), R(17050.0, a3), "setback 2"); k.hull(R(17050.0, a3), R(17200.0, a3 - 150.0), "setback 2 chamfer")
    return k

def build_bed():
    k = Kit("SM_SectorBed_Tile", "Sector bed plate 24 000 x 24 000 x 2 000: four coffered pads, trenches 1 200 x 400 on the 12 000 grid")
    mb = k.mb; L = TILE / 2; g = [-L, -(L - BED_TR), -BED_TR, BED_TR, L - BED_TR, L]; zt = -BED_TD
    pads = [(1, 1), (1, 3), (3, 1), (3, 3)]
    for i in range(5):                                                    # trench floor = 5 x 5 grid minus the four pad cells
        for j in range(5):
            if (i, j) in pads: continue
            mb.quad((g[i], g[j], zt), (g[i+1], g[j], zt), (g[i+1], g[j+1], zt), (g[i], g[j+1], zt))
    for s in range(4):                                                    # sides (top edge carries the grid vertices)
        if s == 0: top = [(L, y, zt) for y in g]; b0, b1 = (L, -L, -BED_T), (L, L, -BED_T)
        elif s == 1: top = [(-L, y, zt) for y in g]; b0, b1 = (-L, -L, -BED_T), (-L, L, -BED_T)
        elif s == 2: top = [(x, L, zt) for x in g]; b0, b1 = (-L, L, -BED_T), (L, L, -BED_T)
        else: top = [(x, -L, zt) for x in g]; b0, b1 = (-L, -L, -BED_T), (L, -L, -BED_T)
        mb.poly([b0, b1] + top[::-1])
    mb.quad((-L, -L, -BED_T), (L, -L, -BED_T), (L, L, -BED_T), (-L, L, -BED_T))
    ch, cof_h, cof_d = 100.0, 3600.0, 200.0
    for (i, j) in pads:
        x0, x1, y0, y1 = g[i], g[i+1], g[j], g[j+1]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rc = lambda ins, z: [(x0 + ins, y0 + ins, z), (x1 - ins, y0 + ins, z), (x1 - ins, y1 - ins, z), (x0 + ins, y1 - ins, z)]
        sq = lambda h, z: [(cx - h, cy - h, z), (cx + h, cy - h, z), (cx + h, cy + h, z), (cx - h, cy + h, z)]
        mb.loft(rc(0.0, zt), rc(0.0, -ch)); mb.loft(rc(0.0, -ch), rc(ch, 0.0))
        T, C0, C1 = rc(ch, 0.0), sq(cof_h + cof_d, 0.0), sq(cof_h, -cof_d)
        mb.loft(T, C0); mb.loft(C0, C1); mb.poly(C1)
        k.box(x0, x1, y0, y1, zt, -cof_d, "pad base")
        O = rc(0.0, 0.0)
        for e in range(4):
            f = (e + 1) % 4
            k.hull([(O[e][0], O[e][1], -cof_d), (O[f][0], O[f][1], -cof_d), C1[f], C1[e]], [O[e], O[f], C0[f], C0[e]], "pad frame %d" % e)
    k.box(-L, L, -L, L, -BED_T, zt, "plate")
    return k

# ----------------------------------------------------------------- Tower A-3 hull (authored in world cm, moved to B at the end)
def cavity_empty(x, y, z):
    m = CAV_M; R = ROOMS
    x0, x1 = R["R1"][0] - m, R["R4"][1] + m                               # main prism: R1 west face .. R4 east face
    y0, y1, y2 = R["R1"][2] - m, R["R6"][3] + m, R["R3"][3] + m           # south faces / R6 north face / R3 north face
    z0, z1, z2, z3 = R["R1"][4] - m, R["R3"][5] + m, R["R5"][4] - m, R["R2"][5] + m   # floor / R3 roof / R5 floor / C-01 ceiling
    if x0 < x < x1 and z0 < z < z3 and (y0 < y < y1 or (y1 < y < y2 and z < z1)): return True          # L-prism (notch over R3, north of R6)
    if x1 <= x < R["R5"][1] + m and R["R5"][2] - m < y < y1 and z2 < z < z3: return True                # R5 / R6 east extension
    if SH[0] + PORTAL_CH < x <= x0 and PORTAL[0] < y < PORTAL[1] and PORTAL[2] < z < PORTAL[3]: return True   # SomaLock portal
    if SLOT[0] < x < SLOT[1] and y1 <= y < SH[3] - SLOT_CH and SLOT[2] < z < SLOT[3]: return True       # R6 north slot
    return False

def hull_loops():
    P = lambda z, i=0.0: rect8(POD, POD_C, z, i)
    S = lambda z, i=0.0: rect8(SH, SH_C, z, i)
    return P, S

def build_hull():
    k = Kit("SM_TowerA3_Hull", "Tower A-3 exterior envelope around cluster C-01 (/home/a03): podium -18 000 .. -9 960, shaft to the roof "
            "deck -5 000 (parapet -4 800), SomaLock portal 3 200 x 1 350 (west), R6 slot 1 500 x 600 (north), R5/R6 bay (east)")
    mb = k.mb; P, S = hull_loops(); m = CAV_M; R = ROOMS
    cz = lambda z: ((SH[0] + SH[1]) / 2, (SH[2] + SH[3]) / 2, z)
    def block(L0, L1, feat, centre):
        for e in range(8):
            g = (e + 1) % 8; Q = [L0[e], L0[g], L1[g], L1[e]]; f = feat.get(e)
            if f is None: mb.quad(*Q)
            elif f == "panel": panel(mb, Q, centre, 0.11 * vlen(vsub(Q[1], Q[0])), 0.13 * vlen(vsub(Q[3], Q[0])), 250.0)
            else: f(Q)
    # ---- podium: two panelled blocks split by a shadow reveal, chamfered terrace edge
    pan = {0: "panel", 2: "panel", 4: "panel", 6: "panel"}
    mb.poly(P(Z_SLAB_TOP)[::-1])
    block(P(Z_SLAB_TOP), P(-14150.0), pan, cz(-16000.0))
    for a_, b_ in ((P(-14150.0), P(-14000.0, 150.0)), (P(-14000.0, 150.0), P(-13800.0, 150.0)), (P(-13800.0, 150.0), P(-13650.0))): mb.loft(a_, b_)
    block(P(-13650.0), P(POD_TOP - 300.0), pan, cz(-12000.0))
    mb.loft(P(POD_TOP - 300.0), P(POD_TOP, 300.0)); mb.loft(P(POD_TOP, 300.0), S(POD_TOP))
    # ---- void: cavity around the room shells + the two through-cuts (rectilinear, hidden behind the room walls)
    xs = sorted(set([SH[0] + PORTAL_CH, R["R1"][0] - m, SLOT[0], R["R4"][1] + m, SLOT[1], R["R5"][1] + m]))
    ys = sorted(set([R["R1"][2] - m, PORTAL[0], R["R5"][2] - m, PORTAL[1], R["R6"][3] + m, R["R3"][3] + m, SH[3] - SLOT_CH]))
    zs = sorted(set([R["R1"][4] - m, PORTAL[2], PORTAL[3], R["R3"][5] + m, R["R5"][4] - m, SLOT[2], SLOT[3], R["R2"][5] + m]))
    mouth_w, mouth_n = (0, SH[0] + PORTAL_CH), (1, SH[3] - SLOT_CH)
    rims = grid_shell(mb, xs, ys, zs, cavity_empty, [mouth_w, mouth_n])
    def cut(Q, rim, axis, face, ch, lim):
        """Chamfered mouth: rim (at depth ch) -> splayed loop on the face plane -> frame in the face quad."""
        def off(p):
            q = list(p); q[axis] = face
            for b, (lo, hi) in lim.items():
                if abs(p[b] - lo) < 1e-6: q[b] = lo - ch
                elif abs(p[b] - hi) < 1e-6: q[b] = hi + ch
            return tuple(q)
        splay = [off(p) for p in rim]
        mb.loft(rim, splay); frame_rect(mb, Q, splay)
    def bay(Q):
        x = SH[1]; y0, y1 = BAY_Y; z0, z1, z2 = BAY_Z; d = BAY_DRAFT
        F = [(x, y0, z0), (x, y1, z0), (x, y1, z2), (x, y0, z2)]
        G = [(BAY_X, y0 + d, z1), (BAY_X, y1 - d, z1), (BAY_X, y1 - d, z2), (BAY_X, y0 + d, z2)]
        frame_rect(mb, Q, F); mb.loft(F, G); mb.poly(G)
    # ---- shaft: lower block (portal), reveal, upper block (bay, slot), parapet, roof deck
    block(S(POD_TOP), S(Z_REV[0]), {0: "panel", 2: "panel", 6: "panel",
          4: lambda Q: cut(Q, rims[mouth_w], 0, SH[0], PORTAL_CH, {1: (PORTAL[0], PORTAL[1]), 2: (PORTAL[2], PORTAL[3])})}, cz(-8700.0))
    for a_, b_ in ((S(Z_REV[0]), S(Z_REV[1], 150.0)), (S(Z_REV[1], 150.0), S(Z_REV[2], 150.0)), (S(Z_REV[2], 150.0), S(Z_REV[3]))): mb.loft(a_, b_)
    block(S(Z_REV[3]), S(Z_ROOF), {0: bay, 4: "panel", 6: "panel",
          2: lambda Q: cut(Q, rims[mouth_n], 1, SH[3], SLOT_CH, {0: (SLOT[0], SLOT[1]), 2: (SLOT[2], SLOT[3])})}, cz(-6000.0))
    mb.loft(S(Z_ROOF), S(Z_PAR, 200.0)); mb.loft(S(Z_PAR, 200.0), S(Z_PAR, 600.0)); mb.loft(S(Z_PAR, 600.0), S(Z_ROOF, 600.0))
    mb.poly(S(Z_ROOF, 600.0))
    # ---- collision (world): exact podium / roof prisms, wall slabs that stop at the room shells, open cuts
    xy = lambda loop: [(p[0], p[1]) for p in loop]
    k.hull(P(Z_SLAB_TOP), P(POD_TOP - 300.0), "podium"); k.hull(P(POD_TOP - 300.0), P(POD_TOP, 300.0), "podium terrace chamfer")
    S8 = xy(S(0.0)); zc = R["R2"][5]                                       # C-01 ceiling line -5 200
    def wall(x0, x1, y0, y1, z0, z1, label):
        p = clip_to((x0, x1, y0, y1), S8); assert len(p) >= 3, label
        k.prism(p, z0, z1, label)
    xw, xe = R["R1"][0], R["R4"][1] + ROOM_WALL                            # -53 600 / -46 700
    wall(SH[0], xw, SH[2], PORTAL[0], POD_TOP, zc, "W pier S"); wall(SH[0], xw, PORTAL[1], SH[3], POD_TOP, zc, "W pier N")
    wall(SH[0], xw, PORTAL[0], PORTAL[1], POD_TOP, PORTAL[2], "W portal sill"); wall(SH[0], xw, PORTAL[0], PORTAL[1], PORTAL[3], zc, "W portal lintel")
    wall(xw, SH[1], SH[2], R["R1"][2], POD_TOP, zc, "S wall")
    yn, y6 = R["R3"][3], R["R6"][3]                                        # 27 000 / 25 400
    wall(xw, SH[1], yn, SH[3], POD_TOP, R["R3"][5], "N wall")
    wall(xw, SH[1], y6, SH[3], R["R3"][5], SLOT[2], "N infill under the slot"); wall(xw, SH[1], y6, SH[3], SLOT[3], zc, "N infill over the slot")
    wall(xw, SLOT[0], y6, SH[3], SLOT[2], SLOT[3], "N infill W of the slot"); wall(SLOT[1], SH[1], y6, SH[3], SLOT[2], SLOT[3], "N infill E of the slot")
    wall(xe, SH[1], R["R1"][2], yn, POD_TOP, R["R5"][4], "E wall"); wall(xe, SH[1], R["R1"][2], R["R5"][2], R["R5"][4], zc, "E wall S of R5")
    x = SH[1]; y0, y1 = BAY_Y; z0, z1, z2 = BAY_Z; d = BAY_DRAFT; zf = R["R5"][4]; xs_ = R["R5"][1]      # R5 floor underside, R5 east face
    k.hull([(x, y0, z0), (x, y1, z0), (x, y1, zf), (x, y0, zf)], [(BAY_X, y0 + d, z1), (BAY_X, y1 - d, z1), (BAY_X, y1 - d, zf), (BAY_X, y0 + d, zf)], "bay corbel")
    k.box(xs_, BAY_X, R["R5"][2] - m, y6 + m, zf, z2, "bay skin")
    k.box(x, xs_, R["R5"][2] - m, y6 + m, zc, z2, "bay cap over the R5 ceiling line")
    k.hull([(x, y0, zf), (x, R["R5"][2] - m, zf), (BAY_X, R["R5"][2] - m, zf), (BAY_X, y0 + d, zf)],
           [(x, y0, z2), (x, R["R5"][2] - m, z2), (BAY_X, R["R5"][2] - m, z2), (BAY_X, y0 + d, z2)], "bay cheek S")
    k.hull([(x, y6 + m, zf), (x, y1, zf), (BAY_X, y1 - d, zf), (BAY_X, y6 + m, zf)],
           [(x, y6 + m, z2), (x, y1, z2), (BAY_X, y1 - d, z2), (BAY_X, y6 + m, z2)], "bay cheek N")
    k.prism(S8, zc, Z_ROOF, "roof slab")
    O0, O1, I0, I1 = S(Z_ROOF), S(Z_PAR, 200.0), S(Z_ROOF, 600.0), S(Z_PAR, 600.0)
    for e in range(8):
        g = (e + 1) % 8
        k.hull([O0[e], O0[g], I0[g], I0[e]], [O1[e], O1[g], I1[g], I1[e]], "parapet %d" % e)
    k.exterior_bbox_cavity = (R["R1"][0] - m, R["R5"][1] + m, R["R1"][2] - m, R["R3"][3] + m, R["R1"][4] - m, R["R2"][5] + m)
    k.world = Kit("world", ""); k.world.mb.v = list(mb.v); k.world.mb.f = [list(f) for f in mb.f]; k.world.ucx = list(k.ucx)
    k.transform(A3_B, True)
    return k

BUILDERS = [build_bed, build_hull, build_square, build_octagon, build_crown]

# ================================================================= assembly (UE world, cm) — single source for the UE script
def snap_axis(x, y):
    """Nearest point of the 12 000 lattice that is a tile corner or an edge mid-point (not an oculus centre)."""
    best = None
    for i in range(int(math.floor(x / 12000.0)) - 1, int(math.floor(x / 12000.0)) + 3):
        for j in range(int(math.floor(y / 12000.0)) - 1, int(math.floor(y / 12000.0)) + 3):
            if i % 2 and j % 2: continue
            d = math.hypot(12000.0*i - x, 12000.0*j - y)
            if best is None or d < best[0]: best = (d, 12000.0*i, 12000.0*j)
    return best[1], best[2]

def tiles():
    out = []; n = int(SLAB_R // TILE) + 1
    for i in range(-n, n):
        for j in range(-n, n):
            cx, cy = TILE*(i + 0.5), TILE*(j + 0.5)
            if math.hypot(abs(cx) + TILE/2, abs(cy) + TILE/2) <= SLAB_R: out.append([cx, cy, 0.0])
    return out

def monoliths():
    out = []
    for (mid, ring, az, r, shape, af, n, saf, stop, cx, cy) in MONO:
        x, y = snap_axis(r * math.cos(math.radians(az)), r * math.sin(math.radians(az)))
        base = 2 * SQ_A if shape == "sq" else 2 * OCT_A
        s = af / base; ss = saf / (2 * OCT_A); ns = int(round((stop - (Z_BED - (SEG_H - SEG_RING))) / SEG_H))
        tip = Z_SLAB_BOT - SEG_H * n
        e = {"id": mid, "ring": ring, "xy": [x, y], "r": round(math.hypot(x, y), 1), "az": round(math.degrees(math.atan2(y, x)) % 360.0, 2),
             "crown": {"mesh": "SM_Monolith_Crown", "scale": [cx / (2*CROWN_A), cy / (2*CROWN_A), 1.0], "z": Z_SLAB_TOP, "size": [cx, cy], "roof": Z_SLAB_TOP + CROWN_H},
             "stalactite": {"mesh": "SM_Monolith_Square_Seg" if shape == "sq" else "SM_Monolith_Octagon_Seg", "scale": [s, s, 1.0], "roll": 0.0,
                            "z": [Z_SLAB_BOT - SEG_H * i for i in range(n)], "af": af, "top": Z_SLAB_BOT, "tip": tip},
             "stalagmite": {"mesh": "SM_Monolith_Octagon_Seg", "scale": [ss, ss, 1.0], "roll": 180.0,
                            "z": [stop - SEG_H * (i + 1) for i in range(ns)], "af": saf, "top": stop, "base": stop - SEG_H * ns},
             "junction_gap": tip - stop}
        e["rings_z"] = sorted([z - (SEG_H - SEG_RING) for z in e["stalactite"]["z"]] + [z + (SEG_H - SEG_RING) for z in e["stalagmite"]["z"]]
                              + [Z_SLAB_TOP + CROWN_RING], reverse=True)
        out.append(e)
    return out

def assembly():
    return {"bed": {"label": "SectorBed_Tiles", "mesh": "SM_SectorBed_Tile", "loc": [0.0, 0.0, Z_BED], "instances_xyz": tiles()},
            "hull": {"label": "TowerA3_Hull", "mesh": "SM_TowerA3_Hull", "loc": list(A3_B)},
            "monoliths": monoliths()}

def build_all():
    kits = [b() for b in BUILDERS]
    for k in kits: k.mb.finalize()
    return kits

def spec_dict(kits, extra=None):
    d = {"units": "cm", "space": "3ds Max RH Z-up; UE import (x, y, z) -> (x, -y, z); SM_TowerA3_Hull is authored mirrored in Max, the rest is Y-symmetric",
         "content": "/Game/AOS_DK_Game/Environment/Macro/Monoliths", "folder": "Environment/Macro/Monoliths",
         "material": "M_AOS_Concrete_BoxMap", "slots": SLOTS, "shell_r": SHELL_R,
         "marks": {"slab_top": Z_SLAB_TOP, "slab_bot": Z_SLAB_BOT, "bed": Z_BED, "ring_step": RING_STEP, "seg_h": SEG_H, "seg_ring": SEG_RING,
                   "crown_h": CROWN_H, "crown_ring": CROWN_RING},
         "a3": {"origin_b": list(A3_B), "podium": list(POD), "podium_top": POD_TOP, "shaft": list(SH), "roof_deck": Z_ROOF, "parapet": Z_PAR,
                "portal_yz": list(PORTAL), "portal_chamfer": PORTAL_CH, "slot_xz": list(SLOT), "slot_chamfer": SLOT_CH,
                "bay_x": BAY_X, "bay_y": list(BAY_Y), "bay_z": list(BAY_Z), "rooms": {n: list(b) for n, b in ROOMS.items()}, "keep": {n: list(b) for n, b in KEEP.items()}},
         "meshes": {k.name: dict(k.mb.stats, note=k.note, slots=k.slots, ucx=len(k.ucx), ucx_max_verts=max(2*len(u[0]) for u in k.ucx)) for k in kits},
         "assembly": assembly()}
    for k in kits:                                                       # UE bounds = Max bounds with Y negated
        st = d["meshes"][k.name]
        st["ue_bbox_min"] = [st["bbox_min"][0], -st["bbox_max"][1], st["bbox_min"][2]]; st["ue_bbox_max"] = [st["bbox_max"][0], -st["bbox_min"][1], st["bbox_max"][2]]
    if extra: d.update(extra)
    return d

# ================================================================= 3ds Max layer (same conventions as the Spire kit)
def P3(a): return rt.Point3(float(a[0]), float(a[1]), float(a[2]))

def max_clean(names):
    dead = [o for o in rt.objects if any(str(o.name) == n or str(o.name).startswith("UCX_" + n + "_") for n in names)]
    for o in dead:
        try: rt.delete(o)
        except Exception: pass

def max_material(slots):
    mm = rt.Multimaterial(numsubs=len(slots)); mm.name = "MM_Monoliths_%d" % len(slots)
    cols = {"MS_Concrete": rt.Color(128, 126, 120), "MS_DepthRing": rt.Color(80, 250, 123), "MS_DepthRing2": rt.Color(139, 233, 253)}
    for i, s in enumerate(slots):
        pm = rt.PhysicalMaterial(); pm.name = s; pm.base_color = cols.get(s, rt.Color(128, 128, 128)); pm.roughness = 0.85; pm.metalness = 0.0
        if s != "MS_Concrete":
            try: pm.emission = 1.0; pm.emit_color = cols[s]
            except Exception: pass
        mm.materialList[i] = pm; mm.names[i] = s
    return mm

def max_mesh(k, mm):
    mb = k.mb
    m = rt.mesh(vertices=[P3(p) for p in mb.v], faces=[rt.Point3(f[0]+1, f[1]+1, f[2]+1) for f in mb.f])
    for i, f in enumerate(mb.f):
        rt.setFaceMatID(m, i+1, f[3]); rt.setFaceSmoothGroup(m, i+1, f[4])
        for e in range(3): rt.setEdgeVis(m, i+1, e+1, bool(f[5][e]))
    rt.update(m)
    m.name = k.name; m.material = mm; m.wirecolor = rt.Color(150, 150, 150)
    uv = rt.Uvwmap(); rt.addModifier(m, uv); uv.maptype = 4; uv.length = 400.0; uv.width = 400.0; uv.height = 400.0
    rt.convertTo(m, rt.Editable_Poly)
    return m

def max_ucx(k):
    nodes = []
    for idx, (bot, top, label) in enumerate(k.ucx):
        n = len(bot); pts = list(bot) + list(top); faces = []
        for i in range(1, n-1): faces.append((1, i+2, i+1))
        for i in range(1, n-1): faces.append((n+1, n+i+1, n+i+2))
        for i in range(n):
            a, b = i+1, (i+1) % n + 1
            faces.append((a, b, n+b)); faces.append((a, n+b, n+a))
        c = [sum(p[i] for p in pts)/len(pts) for i in range(3)]
        vol = sum(vdot(vsub(pts[f[0]-1], c), vcross(vsub(pts[f[1]-1], c), vsub(pts[f[2]-1], c))) for f in faces)
        if vol < 0: faces = [(f[0], f[2], f[1]) for f in faces]
        u = rt.mesh(vertices=[P3(p) for p in pts], faces=[rt.Point3(*f) for f in faces])
        u.name = "UCX_%s_%02d" % (k.name, idx); u.wirecolor = rt.Color(255, 60, 60)
        nodes.append(u)
    return nodes

def max_build():
    out = {"max_units": str(rt.units.SystemType), "max_scale": float(rt.units.SystemScale)}
    if "centimeter" not in out["max_units"].lower() or abs(out["max_scale"] - 1.0) > 1e-9:
        raise RuntimeError("System units must be 1 unit = 1 cm, got %s x %s" % (out["max_units"], out["max_scale"]))
    kits = build_all()
    max_clean([k.name for k in kits])
    if not os.path.isdir(FBX_DIR): os.makedirs(FBX_DIR)
    mats = {}; rep = {}
    for k in kits:
        mm = mats.get(len(k.slots)) or max_material(k.slots); mats[len(k.slots)] = mm
        node = max_mesh(k, mm); ucx = max_ucx(k)
        lay = rt.LayerManager.getLayerFromName(k.name) or rt.LayerManager.newLayerFromName(k.name)
        lay.addnode(node)
        for u in ucx: lay.addnode(u)
        rep[k.name] = {"faces_poly": int(rt.polyop.getNumFaces(node)), "verts": int(rt.polyop.getNumVerts(node)), "ucx": len(ucx),
                       "open_edges": int(rt.polyop.getOpenEdges(node).numberSet), "pivot": [float(node.pos.x), float(node.pos.y), float(node.pos.z)],
                       "bbox_min": [round(float(c), 3) for c in (node.min.x, node.min.y, node.min.z)],
                       "bbox_max": [round(float(c), 3) for c in (node.max.x, node.max.y, node.max.z)]}
    out["nodes"] = rep
    with open(SPEC_PATH, "w") as f: json.dump(spec_dict(kits, {"max": out}), f, indent=1)
    return out

def max_export(names=None):
    """FBX per asset (render node + its UCX hulls); exporter params = the AOS_DK preset (cm, Z-up, smoothing groups, binary)."""
    done = {}
    for nm in (names or [b().name for b in BUILDERS]):
        node = rt.getNodeByName(nm)
        ucx = [o for o in rt.objects if str(o.name).startswith("UCX_" + nm + "_")]
        rt.select(node)
        for u in ucx: rt.selectMore(u)
        path = os.path.join(FBX_DIR, nm + ".fbx")
        ok = rt.exportFile(path, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
        done[nm] = {"ok": bool(ok), "ucx": len(ucx), "bytes": os.path.getsize(path) if os.path.exists(path) else 0}
    rt.clearSelection()
    return done

def max_save():
    d = os.path.dirname(MAX_PATH)
    if not os.path.isdir(d): os.makedirs(d)
    ok = rt.saveMaxFile(MAX_PATH, quiet=True)
    return {"saved": bool(ok), "path": MAX_PATH, "bytes": os.path.getsize(MAX_PATH) if os.path.exists(MAX_PATH) else 0}

# ================================================================= offline self-test
def selftest():
    import numpy as np
    from scipy.spatial import ConvexHull
    from scipy.optimize import linprog
    kits = build_all(); rep = {}; ok = True
    def fail(*a):
        nonlocal ok
        ok = False; print("FAIL", *a)
    def hull_eq(bot, top):
        pts = np.array(list(bot) + list(top)); h = ConvexHull(pts)
        d = max(float(np.max(h.equations[:, :3] @ p + h.equations[:, 3])) for p in pts)
        return pts, h, d
    def feasible(A, b):                                                   # is { x : A x <= b } non-empty (with 1 cm of slack inside)?
        r = linprog(np.zeros(A.shape[1]), A_ub=A, b_ub=b - 1.0, bounds=[(None, None)] * A.shape[1], method="highs")
        return r.status == 0
    def box_eq(bx):
        A = np.array([[-1, 0, 0], [1, 0, 0], [0, -1, 0], [0, 1, 0], [0, 0, -1], [0, 0, 1]], float)
        return A, np.array([-bx[0], bx[1], -bx[2], bx[3], -bx[4], bx[5]], float)
    for k in kits:
        V = np.array(k.mb.v); eqs = []
        for bot, top, label in k.ucx:
            pts, h, d = hull_eq(bot, top)
            if len(h.vertices) != len(pts):
                inner = [i for i in range(len(pts)) if i not in set(h.vertices)]
                dd = max(-float(np.max(h.equations[:, :3] @ pts[i] + h.equations[:, 3])) for i in inner)
                if dd > 0.05: fail("NON-CONVEX", k.name, label, len(h.vertices), len(pts), dd)
            eqs.append(h.equations)
        F = [f for f in k.mb.f]
        S = np.vstack([V, np.array([(V[f[0]] + V[f[1]] + V[f[2]]) / 3.0 for f in F])])
        if k.name == "SM_TowerA3_Hull":                                   # the hidden cavity is not part of the visible surface
            c = k.exterior_bbox_cavity; W = S + np.array([A3_B[0], 0, A3_B[2]]); W[:, 1] = -S[:, 1] + A3_B[1]
            inside = (W[:, 0] > c[0] - 1) & (W[:, 0] < c[1] + 1) & (W[:, 1] > c[2] - 1) & (W[:, 1] < c[3] + 1) & (W[:, 2] > c[4] - 1) & (W[:, 2] < c[5] + 1)
            S = S[~inside]
        best = np.full(len(S), 1e9)
        for E in eqs:
            best = np.minimum(best, np.max(S @ E[:, :3].T + E[:, 3], axis=1))
        rep[k.name] = dict(k.mb.stats, ucx=len(k.ucx), visual_beyond_collision_cm=round(float(max(0.0, best.max())), 2))
        if best.max() > 15.0: fail("visual beyond collision > 15 cm", k.name, float(best.max()))
        if k.name != "SM_TowerA3_Hull" and (abs(k.mb.stats["bbox_min"][1] + k.mb.stats["bbox_max"][1]) > 1e-6): fail("not Y-symmetric", k.name)
    # ---- hull vs. C-01, SomaLock, TP-B, Reaper arena (world space)
    hk = [k for k in kits if k.name == "SM_TowerA3_Hull"][0].world; V = np.array(hk.mb.v)
    keep = {("room " + n): (b[0] + ROOM_WALL, b[1] - ROOM_WALL, b[2] + ROOM_WALL, b[3] - ROOM_WALL, b[4] + ROOM_WALL, b[5] - ROOM_WALL) for n, b in ROOMS.items()}
    keep.update({("shell " + n): b for n, b in ROOMS.items()}); keep.update(KEEP)
    keep["portal void"] = (SH[0] - 2000, ROOMS["R1"][0], PORTAL[0], PORTAL[1], PORTAL[2], PORTAL[3])
    keep["slot void"] = (SLOT[0], SLOT[1], ROOMS["R6"][3], SH[3] + 2000, SLOT[2], SLOT[3])
    hits = {}
    for name, bx in keep.items():
        A, b = box_eq(bx); n_c = 0; n_v = 0
        solid_only = name.startswith("shell ")                             # room shells may touch collision slabs but no visible face may cut them
        if not solid_only:
            for bot, top, label in hk.ucx:
                pts, h, d = hull_eq(bot, top)
                if feasible(np.vstack([A, h.equations[:, :3]]), np.concatenate([b, -h.equations[:, 3]])): n_c += 1; fail("UCX in keep-out", name, label)
        for f in hk.mb.f:                                                  # triangle (barycentric l1, l2) inside the box?
            p0, e1, e2 = V[f[0]], V[f[1]] - V[f[0]], V[f[2]] - V[f[0]]
            if (np.minimum(np.minimum(V[f[0]], V[f[1]]), V[f[2]]) > np.array([bx[1], bx[3], bx[5]])).any() or \
               (np.maximum(np.maximum(V[f[0]], V[f[1]]), V[f[2]]) < np.array([bx[0], bx[2], bx[4]])).any(): continue
            M = np.column_stack([e1, e2]); At = np.vstack([A @ M, [[-1, 0], [0, -1], [1, 1]]]); bt = np.concatenate([b - A @ p0, [0, 0, 1]])
            r = linprog([0, 0], A_ub=At, b_ub=bt - np.concatenate([np.full(6, 1.0), np.zeros(3)]), bounds=[(None, None)] * 2, method="highs")
            if r.status == 0: n_v += 1
        hits[name] = [n_c, n_v]
        if n_v: fail("visible face in keep-out", name, n_v)
    # ---- monolith layout rules (§1.4)
    asm = assembly(); mono = asm["monoliths"]; lay = []
    def half(e): return max(e["stalagmite"]["af"] / 2 / math.cos(math.pi / 8), e["stalactite"]["af"] / 2 * (math.sqrt(2) if "Square" in e["stalactite"]["mesh"] else 1 / math.cos(math.pi / 8)),
                            math.hypot(e["crown"]["size"][0], e["crown"]["size"][1]) / 2)
    gmin = 1e9
    for i, a in enumerate(mono):
        lo, hi = RINGS[a["ring"]]
        if not (lo <= a["r"] <= hi): fail("ring radius", a["id"], a["r"])
        if (a["xy"][0] / 12000.0) % 2 == 1 and (a["xy"][1] / 12000.0) % 2 == 1: fail("on an oculus", a["id"])
        for b in mono[i+1:]:
            g = math.hypot(a["xy"][0] - b["xy"][0], a["xy"][1] - b["xy"][1]) - half(a) - half(b); gmin = min(gmin, g)
            if g < 15000.0: fail("surface gap < 15 000", a["id"], b["id"], g)
        px = max(POD[0] - a["xy"][0], 0.0, a["xy"][0] - POD[1]); py = max(POD[2] - a["xy"][1], 0.0, a["xy"][1] - POD[3])
        ga3 = math.hypot(px, py) - half(a)
        gex = min(math.hypot(a["xy"][0] - p[0], a["xy"][1] - p[1]) - half(a) - 4500.0 * math.sqrt(2) for p in EXPLORABLE.values())
        gso = math.hypot(a["xy"][0] - SOCKET[0], a["xy"][1] - SOCKET[1]) - half(a) - SOCKET[2]
        dx = max(D1_BOX[0] - a["xy"][0], 0.0, a["xy"][0] - D1_BOX[1]); dy = max(D1_BOX[2] - a["xy"][1], 0.0, a["xy"][1] - D1_BOX[3])
        gd1 = math.hypot(dx, dy) - half(a)
        ggu = (abs(a["xy"][1]) if a["xy"][0] < 0 else math.hypot(*a["xy"])) - half(a)          # guardian zone GS-02: the az 180° radial (D-4 / V-3)
        gsp = a["r"] - half(a) - 24400.0                                                      # A-0 + ring bus (r 20 000 + 4 400)
        apo = max(abs(a["xy"][0] * math.cos(math.radians(15 * q)) + a["xy"][1] * math.sin(math.radians(15 * q))) for q in range(24))
        gbn = (BND_APOTHEM - apo - half(a)) if a["ring"] != "R3" else (apo - half(a) - (BND_APOTHEM + BND_T))  # wholly inside / wholly outside the containment
        tl = set((t[0], t[1]) for t in asm["bed"]["instances_xyz"])
        cov = all((TILE * (math.floor((a["xy"][0] + sx * half(a)) / TILE) + 0.5), TILE * (math.floor((a["xy"][1] + sy * half(a)) / TILE) + 0.5)) in tl
                  for sx in (-1, 1) for sy in (-1, 1))
        for nm, g, lim in (("A-3 hull", ga3, 15000.0), ("explorable axis", gex, 15000.0), ("Socket", gso, 15000.0), ("D-1", gd1, 3000.0),
                           ("guardian az 180", ggu, 6000.0), ("A-0 / ring bus", gsp, 15000.0), ("containment wall", gbn, 0.0)):
            if g < lim: fail(nm, a["id"], round(g))
        if not cov: fail("no slab / bed tile under", a["id"])
        if not (-98000.0 <= a["stalactite"]["tip"] <= -50000.0): fail("tip", a["id"])
        if not (-98000.0 <= a["stalagmite"]["top"] <= -82000.0): fail("stalagmite top", a["id"])
        if a["junction_gap"] <= 0: fail("junction", a["id"])
        if any(abs(z / RING_STEP - round(z / RING_STEP)) > 1e-9 for z in a["rings_z"]): fail("ring not on a 100 m mark", a["id"])
        if not (-3500.0 <= Z_SLAB_TOP + 14500.0 <= -800.0 and -3500.0 <= a["crown"]["roof"] <= -800.0): fail("crown roof", a["id"])
        lay.append([a["id"], a["ring"], a["xy"], a["az"], a["r"], a["stalactite"]["mesh"][12:15], a["stalactite"]["af"], a["stalactite"]["tip"],
                    a["stalagmite"]["af"], a["stalagmite"]["top"], a["junction_gap"], a["crown"]["size"], len(a["rings_z"]),
                    {"a3": round(ga3), "expl": round(gex), "socket": round(gso), "d1": round(gd1), "guard": round(ggu), "bnd": round(gbn)}])
    checks = {"tiles": len(asm["bed"]["instances_xyz"]), "monoliths": len(mono), "min surface gap": round(gmin),
              "instances": {"stalactite": sum(len(m["stalactite"]["z"]) for m in mono), "stalagmite": sum(len(m["stalagmite"]["z"]) for m in mono), "crown": len(mono)},
              "depth rings": sum(len(m["rings_z"]) for m in mono), "keep-out [UCX, faces]": hits}
    print(json.dumps(rep, indent=1)); print(json.dumps(checks, indent=1))
    for l in lay: print(l)
    print("OK" if ok else "FAILED")
    return kits, rep, checks

if IN_MAX:
    MONO_RESULT = max_build()
elif __name__ == "__main__":
    selftest()
