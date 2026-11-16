# =============================================================================
# AOS-DK | Macro kit "Spire A-0" | 3ds Max 2027 (pymxs) -> FBX -> UE 5.7.4
# Tower A Spatial Bible §2.1 (A-0 down), §2.2 (A-0 up), §2.3 (Kikutake Slab), §2.4 (S4 ring bus / D-1), §2.6 (IC-M).
#
# 8 clean, closed, chamfered modular meshes (NO cube matrices). Each one is a single watertight solid
# (the junction chamber carries 3 extra closed conductor shells) with convex UCX hulls (<= 32 verts each):
#   SM_Kikutake_Slab_Tile   24 000 x 24 000 x 5 000 waffle tile, round through-oculus Ø4 000      pivot: centre, underside
#   SM_Spire_Capital        octagonal flare AF 26 000 -> 18 000, h 6 000                           pivot: top centre
#   SM_Spire_Octagon_Seg    self-similar octagonal frustum (stack with uniform scale q^i)          pivot: top centre
#   SM_Spire_Collar_ICM     collar Ø16 000 x 2 500 incl. IC-M disc 1 200 (used twice, flipped)     pivot: root centre
#   SM_Spire_Pylon_Seg      self-similar round pylon frustum + 2 reinforcement rings               pivot: bottom centre
#   SM_Spire_Plinth         stepped plinth Ø30 000 x 3 000 (+500 embedded in the bed)              pivot: centre at bed level
#   SM_S4_RingBus_Seg       16.5° arc of the ring bus (r 20 000, OD 8 000, flanges OD 8 800)        pivot: ring centre
#   SM_S4_Junction_Chamber  concrete tee housing, bore ID 7 700 = D-1 ID, copper tee inside        pivot: D-1 port face centre, +X to D-1
#
# Units: cm, Z-up. Every mesh is mirror-symmetric in Y, so the Max RH -> UE LH (x, -y, z) flip is a no-op.
# Linear taper from ONE mesh: a frustum scaled uniformly by q per step stacks into an exact linear taper when the
# segment heights form a geometric series  (q = (w_end / w_start)^(1/N),  H0 = L (1 - q) / (1 - q^N)).
#
# Run in Max:  ns = {}; exec(open(r"<proj>\Tools\max_build_SpireA0_Kit.py").read(), ns); ns["SPIRE_RESULT"]
# Offline self-test (no Max):  python max_build_SpireA0_Kit.py
# =============================================================================
import math, json, os

try:
    from pymxs import runtime as rt
    IN_MAX = True
except Exception:
    rt = None
    IN_MAX = False

PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
FBX_DIR = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "Macro", "Spire_A0")
SPEC_PATH = os.path.join(PROJ, "Tools", "SpireA0_Kit_spec.json")

# ---------------------------------------------------------------- bible metrics (cm)
Z_SLAB_TOP, Z_SLAB_BOT = -18000.0, -23000.0          # §2.3
Z_CAP_BOT = -29000.0                                 # §2.1 capital flare h 6 000
Z_OCT_BOT = -86000.0                                 # §2.1 shaft end / collar top
Z_DISC_DN, Z_DISC_UP = -88500.0, -91500.0            # §1.3 / §2.6 IC-M gap 3 000
Z_RING = -90000.0                                    # §2.4 ring bus + D-1 axis plane
Z_PYL_TOP, Z_PYL_BOT, Z_BED = -94000.0, -157000.0, -160000.0   # §2.2
D1_PORT = (24000.0, 0.0, Z_RING)                     # existing D-1 front snap (SOCKET_Snap_Front of D1_Seg_01)

NSEG = 96                                            # round sections (3.75° facets)
T8 = math.tan(math.radians(22.5))

# A-0 down: octagon, AF 18 000 @ -29 000 -> AF 12 000 @ -86 000
OCT_N, OCT_A0, OCT_A1 = 9, 9000.0, 6000.0
OCT_Q = (OCT_A1 / OCT_A0) ** (1.0 / OCT_N)
OCT_H = (Z_CAP_BOT - Z_OCT_BOT) * (1.0 - OCT_Q) / (1.0 - OCT_Q ** OCT_N)
OCT_KAP = 0.06                                       # corner chamfer length / apothem
OCT_DEL = 150.0 / 9000.0                             # joint reveal depth / apothem
CAP_A = 13000.0                                      # capital AF 26 000

# A-0 up: taper anchored Ø22 000 @ -160 000 -> Ø14 000 @ -94 000 (gives the bible check value Ø18 970 @ -135 000)
PYL_N = 9
def pyl_r_world(z): return 11000.0 - 4000.0 * (z - Z_BED) / (Z_PYL_TOP - Z_BED)
PYL_R0, PYL_R1 = pyl_r_world(Z_PYL_BOT), 7000.0
PYL_Q = (PYL_R1 / PYL_R0) ** (1.0 / PYL_N)
PYL_H = (Z_PYL_TOP - Z_PYL_BOT) * (1.0 - PYL_Q) / (1.0 - PYL_Q ** PYL_N)

COL_R, COL_H, DISC_T = 8000.0, 2500.0, 1200.0        # collar Ø16 000, IC-M disc 1 200
PLINTH_R, PLINTH_H, PLINTH_EMBED = 15000.0, 3000.0, 500.0

TILE, SLAB_T, SLAB_R = 24000.0, 5000.0, 300000.0     # oculus grid 24 000, slab 5 000, disc r <= 300 000
OC_R, OC_CH = 2000.0, 100.0                          # oculus Ø4 000, rim chamfer
TILE_CH = 150.0                                      # perimeter chamfer (V-joint between tiles)
COF_PITCH, COF_HALF, COF_D, COF_CH = 4800.0, 1900.0, 800.0, 60.0   # coffers: 5 x 5, opening 3 800, depth = lower chord 800
CORE_HALF = 2900.0                                   # solid block around the oculus

RB_R, RB_TUBE, RB_FL, RB_RIB = 20000.0, 4000.0, 4400.0, 4250.0     # §2.4 torus r 20 000, OD 8 000, flange OD 8 800
RB_SEG_DEG, RB_COUNT, RB_GAP_HALF = 16.5, 20, 15.0   # 20 x 16.5° = 330°; ±15° is inside the junction chamber
RB_NT = 48

J_X0, J_HY, J_HZ, J_CH = -10000.0, 7000.0, 5200.0, 400.0           # junction housing (local, port face at x = 0)
J_BORE_R, J_BORE_X = 3850.0, -8500.0                 # bore ID 7 700 (= D-1 enclosure ID), blind at world r 15 500
J_COND_R = 1415.0                                    # conductor Ø2 830 = ID / e (matches D-1)
J_AXIS_X = -D1_PORT[0]                               # world Z axis in junction-local x
J_HUB = (RB_R + J_AXIS_X, 0.0, 0.0)                  # tee centre on the ring centreline (local x = -4 000)

SHELL_R = math.sqrt(200.0 ** 2 + 100.0 ** 2 + 100.0 ** 2)          # Shell-1 any-orientation sphere R 245

# ---------------------------------------------------------------- vector helpers
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vdot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

# ---------------------------------------------------------------- mesh builder (welded, closed, auto-oriented)
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
    def tri(self, a, b, c, mat=1, sg=0):
        self._tri(self.vert(a), self.vert(b), self.vert(c), mat, sg, (1, 1, 1))
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
    def fan(self, c, ring, mat=1, sg=0):
        n = len(ring)
        for i in range(n): self.tri(c, ring[i], ring[(i+1) % n], mat, sg)
    def bridge(self, outer, inner, c, u, v, mat=1, sg=0):
        """Triangulate the planar region between two star-shaped closed loops (angle merge around c)."""
        def ccw(loop):
            n = len(loop)
            a = [math.atan2(vdot(vsub(p, c), v), vdot(vsub(p, c), u)) for p in loop]
            tot = sum(((a[(i+1) % n] - a[i] + math.pi) % (2*math.pi)) - math.pi for i in range(n))
            return loop[::-1] if tot < 0 else loop
        def d2(p, q): w = vsub(p, q); return vdot(w, w)
        O = ccw(list(outer)); I = ccw(list(inner)); m, n = len(O), len(I)
        s = min(range(n), key=lambda i: d2(I[i], O[0])); I = I[s:] + I[:s]
        i = j = 0
        while i < m or j < n:                                             # greedy shortest diagonal
            if j >= n or (i < m and d2(O[(i+1) % m], I[j % n]) <= d2(O[i % m], I[(j+1) % n])):
                self.tri(O[i % m], O[(i+1) % m], I[j % n], mat, sg); i += 1
            else:
                self.tri(O[i % m], I[(j+1) % n], I[j % n], mat, sg); j += 1

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
        # consistency re-check: every edge used once in each direction
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

# ---------------------------------------------------------------- section helpers
def circle(r, z, n=NSEG, c=(0.0, 0.0)):
    return [(c[0] + r*math.cos(2*math.pi*i/n), c[1] + r*math.sin(2*math.pi*i/n), z) for i in range(n)]
def circle_x(r, x, n=NSEG):
    return [(x, r*math.cos(2*math.pi*i/n), r*math.sin(2*math.pi*i/n)) for i in range(n)]
def tube_ring(theta_deg, r, R, c=(0.0, 0.0, 0.0), n=RB_NT):
    th = math.radians(theta_deg); er = (math.cos(th), math.sin(th), 0.0)
    C = (c[0] + R*er[0], c[1] + R*er[1], c[2])
    return [(C[0] + r*math.cos(2*math.pi*i/n)*er[0], C[1] + r*math.cos(2*math.pi*i/n)*er[1], C[2] + r*math.sin(2*math.pi*i/n)) for i in range(n)]
def oct_ring(a, z):
    """Chamfered octagon (16-gon), flats on ±X / ±Y / diagonals; apothem a; CCW."""
    w = a * (T8 - OCT_KAP); pts = []
    for k in range(8):
        ph = math.radians(45.0 * k); h = (math.cos(ph), math.sin(ph)); t = (-math.sin(ph), math.cos(ph))
        pts.append((a*h[0] - w*t[0], a*h[1] - w*t[1], z)); pts.append((a*h[0] + w*t[0], a*h[1] + w*t[1], z))
    return pts
def lathe(mb, prof, n=NSEG, mat=1, c=(0.0, 0.0)):
    rings = [circle(r, z, n, c) for r, z in prof]
    for i in range(len(prof) - 1): mb.loft(rings[i], rings[i+1], mat, 1 << (i % 3))
    mb.fan((c[0], c[1], prof[0][1]), rings[0], mat, 8); mb.fan((c[0], c[1], prof[-1][1]), rings[-1], mat, 16)
def rect(cx, cy, h, z): return [(cx-h, cy-h, z), (cx+h, cy-h, z), (cx+h, cy+h, z), (cx-h, cy+h, z)]
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

# ---------------------------------------------------------------- collision: generalised prisms (two convex rings, equal count)
class Kit(object):
    def __init__(self, name, note):
        self.mb = MB(name); self.name = name; self.note = note; self.ucx = []; self.slots = ["MS_Concrete"]
    def hull(self, bot, top, label=""):
        assert len(bot) == len(top) and len(bot) >= 3 and 2*len(bot) <= 32, (self.name, label, len(bot))
        self.ucx.append((list(bot), list(top), label))
    def box(self, x0, x1, y0, y1, z0, z1, label=""):
        self.hull([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], label)
    def wedges(self, r0, z0, r1, z1, label, n_w=8, c=(0.0, 0.0)):
        """Solid of revolution band as n_w pie wedges; arc points land on the 96-gon facets of the visual."""
        per = NSEG // n_w
        for k in range(n_w):
            def ring(r, z):
                pts = [(c[0], c[1], z)]
                for i in range(per + 1):
                    a = 2*math.pi*(k*per + i)/NSEG; pts.append((c[0] + r*math.cos(a), c[1] + r*math.sin(a), z))
                return pts
            self.hull(ring(r0, z0), ring(r1, z1), "%s w%d" % (label, k))

# ================================================================= builders
def build_tile():
    k = Kit("SM_Kikutake_Slab_Tile", "Kikutake void-slab tile 24 000 x 24 000 x 5 000, coffered underside, through-oculus Ø4 000")
    mb = k.mb; L = TILE/2; T = SLAB_T; C = TILE_CH
    lat = [-L + C, -7200.0, -2400.0, 2400.0, 7200.0, L - C]; latN = [-L, -7200.0, -2400.0, 2400.0, 7200.0, L]
    per = [(i, 0) for i in range(6)] + [(5, j) for j in range(1, 6)] + [(i, 5) for i in range(4, -1, -1)] + [(0, j) for j in range(4, 0, -1)]
    loopA = lambda z: [(lat[i], lat[j], z) for i, j in per]
    loopB = lambda z: [(latN[i], latN[j], z) for i, j in per]
    for i in range(5):
        for j in range(5):
            S = lambda z: [(lat[i], lat[j], z), (lat[i+1], lat[j], z), (lat[i+1], lat[j+1], z), (lat[i], lat[j+1], z)]
            if i == 2 and j == 2:
                mb.bridge(S(T), circle(OC_R + OC_CH, T), (0, 0, T), (1, 0, 0), (0, 1, 0))
                mb.bridge(S(0.0), circle(OC_R + OC_CH, 0.0), (0, 0, 0), (1, 0, 0), (0, 1, 0))
                continue
            mb.poly(S(T))
            cx, cy = -9600.0 + COF_PITCH*i, -9600.0 + COF_PITCH*j
            M0 = rect(cx, cy, COF_HALF + COF_CH, 0.0); M1 = rect(cx, cy, COF_HALF, COF_CH); M2 = rect(cx, cy, COF_HALF, COF_D)
            mb.loft(S(0.0), M0); mb.loft(M0, M1); mb.loft(M1, M2); mb.poly(M2)
    mb.loft(loopA(T), loopB(T - C)); mb.loft(loopB(T - C), loopB(C)); mb.loft(loopB(C), loopA(0.0))
    mb.loft(circle(OC_R + OC_CH, T), circle(OC_R, T - OC_CH), 1, 2)
    mb.loft(circle(OC_R, T - OC_CH), circle(OC_R, OC_CH), 1, 1)
    mb.loft(circle(OC_R, OC_CH), circle(OC_R + OC_CH, 0.0), 1, 4)
    # --- collision: upper chord + core as 4 boxes, ribs as 16 boxes, solid core as 32 sectors circumscribing the oculus
    H = CORE_HALF
    k.box(-L, -H, -L, L, COF_D, T, "chord W"); k.box(H, L, -L, L, COF_D, T, "chord E")
    k.box(-H, H, H, L, COF_D, T, "chord N"); k.box(-H, H, -L, -H, COF_D, T, "chord S")
    bands = [(-L, -11500.0), (-7700.0, -6700.0), (-H, -COF_HALF), (COF_HALF, H), (6700.0, 7700.0), (11500.0, L)]
    for a, b in bands:
        if abs(a) < 3000 and abs(b) < 3000:
            k.box(-L, -H, a, b, 0.0, COF_D, "rib X"); k.box(H, L, a, b, 0.0, COF_D, "rib X")
            k.box(a, b, -L, -H, 0.0, COF_D, "rib Y"); k.box(a, b, H, L, 0.0, COF_D, "rib Y")
        else:
            k.box(-L, L, a, b, 0.0, COF_D, "rib X"); k.box(a, b, -L, L, 0.0, COF_D, "rib Y")
    NS = 32; rc = OC_R / math.cos(math.pi / NS)
    for s in range(NS):
        a0, a1 = 2*math.pi*s/NS, 2*math.pi*(s+1)/NS
        def pt(a, inner):
            r = rc if inner else H / max(abs(math.cos(a)), abs(math.sin(a)))
            return (r*math.cos(a), r*math.sin(a))
        q = [pt(a0, True), pt(a0, False), pt(a1, False), pt(a1, True)]
        k.hull([(x, y, 0.0) for x, y in q], [(x, y, T) for x, y in q], "core s%d" % s)
    return k

def build_capital():
    k = Kit("SM_Spire_Capital", "A-0 down capital flare, AF 26 000 -> 18 000, h 6 000"); mb = k.mb
    prof = [(0.0, CAP_A - 200.0), (-250.0, CAP_A - 200.0), (-450.0, CAP_A), (-1500.0, CAP_A), (Z_CAP_BOT - Z_SLAB_BOT, OCT_A0)]
    rings = [oct_ring(a, z) for z, a in prof]
    for i in range(len(rings) - 1): mb.loft(rings[i], rings[i+1])
    mb.poly(rings[0]); mb.poly(rings[-1])
    k.hull(oct_ring(CAP_A, -1500.0), oct_ring(CAP_A, 0.0), "abacus")
    k.hull(oct_ring(OCT_A0, prof[-1][0]), oct_ring(CAP_A, -1500.0), "flare")
    return k

def build_octagon():
    k = Kit("SM_Spire_Octagon_Seg", "A-0 down shaft segment: self-similar octagonal frustum, top AF 18 000, scale q per step"); mb = k.mb
    H, q, a0 = OCT_H, OCT_Q, OCT_A0
    A = lambda z: a0 * (1.0 - (1.0 - q) * (-z) / H)
    top = [(0.0, 1 - OCT_DEL), (-200.0, 1 - OCT_DEL), (-350.0, 1.0)]
    bot = [(-H + 350.0*q, 1.0), (-H + 200.0*q, 1 - OCT_DEL), (-H, 1 - OCT_DEL)]
    rt_ = [oct_ring(A(z)*f, z) for z, f in top]; rb = [oct_ring(A(z)*f, z) for z, f in bot]
    for rr in (rt_, rb):
        for i in range(2): mb.loft(rr[i], rr[i+1])
    mb.poly(rt_[0]); mb.poly(rb[-1])
    zt, zb = top[-1][0], bot[0][0]; R0, R1 = rt_[-1], rb[0]
    D = 240.0 * (1 + q) / 2                                               # caisson depth (§2.1: 240)
    for f in range(8):
        i1, i2 = 2*f + 1, (2*f + 2) % 16
        mb.quad(R0[i1], R0[i2], R1[i2], R1[i1])                           # corner chamfer
        ph = math.radians(45.0 * f); h = (math.cos(ph), math.sin(ph)); t = (-math.sin(ph), math.cos(ph))
        def fp(z, sgn, margin, depth):
            a = A(z); w = a*(T8 - OCT_KAP) - margin*a/a0
            return ((a - depth)*h[0] + sgn*w*t[0], (a - depth)*h[1] + sgn*w*t[1], z)
        Fq = [R0[2*f], R0[2*f+1], R1[2*f+1], R1[2*f]]
        zo0, zo1 = zt - 600.0, zb + 600.0*q; zi0, zi1 = zo0 - 240.0, zo1 + 240.0*q
        O = [fp(zo0, -1, 900.0, 0.0), fp(zo0, 1, 900.0, 0.0), fp(zo1, 1, 900.0, 0.0), fp(zo1, -1, 900.0, 0.0)]
        I = [fp(zi0, -1, 1140.0, D), fp(zi0, 1, 1140.0, D), fp(zi1, 1, 1140.0, D), fp(zi1, -1, 1140.0, D)]
        for e in range(4):
            g = (e + 1) % 4
            mb.quad(Fq[e], Fq[g], O[g], O[e]); mb.quad(O[e], O[g], I[g], I[e])
        mb.poly(I)
    k.hull(oct_ring(A(-H), -H), oct_ring(a0, 0.0), "frustum")
    return k

def build_collar():
    k = Kit("SM_Spire_Collar_ICM", "Collar Ø16 000 x 2 500 with IC-M disc 1 200 and 3 coil channels (0.35 / 0.60 / 0.85 R)"); mb = k.mb
    R = COL_R; zd = -(COL_H - DISC_T)
    prof = [(R - 150.0, 0.0), (R, -150.0), (R, zd + 120.0), (R - 120.0, zd), (R, zd - 120.0), (R, -COL_H + 100.0), (R - 100.0, -COL_H)]
    for fr in (0.85, 0.60, 0.35):
        rc = R * fr
        prof += [(rc + 200.0, -COL_H), (rc + 140.0, -COL_H + 60.0), (rc - 140.0, -COL_H + 60.0), (rc - 200.0, -COL_H)]
    lathe(mb, prof)
    k.wedges(R, -COL_H, R, 0.0, "collar")
    return k

def build_pylon():
    k = Kit("SM_Spire_Pylon_Seg", "A-0 up pylon segment: self-similar round frustum, base Ø21 636, 2 reinforcement rings, scale q per step"); mb = k.mb
    H, q, R0 = PYL_H, PYL_Q, PYL_R0
    R = lambda z: R0 * (1.0 - (1.0 - q) * z / H)
    zm = 0.55 * H
    offs = [(0.0, 150.0), (150.0, 300.0), (900.0, 300.0), (1050.0, 150.0), (1050.0, 0.0),
            (zm - 300.0, 0.0), (zm - 300.0, 100.0), (zm - 200.0, 200.0), (zm + 200.0, 200.0), (zm + 300.0, 100.0), (zm + 300.0, 0.0), (H, 0.0)]
    lathe(mb, [(R(z) + o, z) for z, o in offs])
    k.wedges(R(0.0), 0.0, R(H), H, "shaft")
    k.wedges(R(0.0) + 300.0, 0.0, R(1050.0) + 300.0, 1050.0, "base ring")
    k.wedges(R(zm - 300.0) + 200.0, zm - 300.0, R(zm + 300.0) + 200.0, zm + 300.0, "mid ring")
    return k

def build_plinth():
    k = Kit("SM_Spire_Plinth", "A-0 up plinth Ø30 000 x 3 000, two tiers, 500 embedded in the bed"); mb = k.mb
    R = PLINTH_R
    prof = [(R, -PLINTH_EMBED), (R, 1600.0), (R - 200.0, 1800.0), (R - 1800.0, 1800.0), (R - 1800.0, 2800.0), (R - 2000.0, PLINTH_H)]
    lathe(mb, prof)
    k.wedges(R, -PLINTH_EMBED, R, 1800.0, "tier 1"); k.wedges(R - 1800.0, 1800.0, R - 1800.0, PLINTH_H, "tier 2")
    return k

def build_ring_seg():
    k = Kit("SM_S4_RingBus_Seg", "S4 ring bus arc 16.5°: torus r 20 000, enclosure OD 8 000, end flanges OD 8 800"); mb = k.mb
    half = RB_SEG_DEG / 2; step = RB_SEG_DEG / 12
    dF = math.degrees(120.0 / RB_R); dR = math.degrees(100.0 / RB_R)
    st = [(-half, RB_FL), (-half + dF, RB_FL), (-half + dF, RB_TUBE)]
    for i in range(1, 12):
        th = -half + step*i
        st.append((th, RB_TUBE))                                          # plain enclosure between flanges (D-1 rhythm: flange pair every ~5 760)
    st += [(half - dF, RB_TUBE), (half - dF, RB_FL), (half, RB_FL)]
    rings = [tube_ring(th, r, RB_R) for th, r in st]
    for i in range(len(rings) - 1): mb.loft(rings[i], rings[i+1], 1, 1 << (i % 3))
    for th, ring, sg in ((-half, rings[0], 8), (half, rings[-1], 16)):
        a = math.radians(th); mb.fan((RB_R*math.cos(a), RB_R*math.sin(a), 0.0), ring, 1, sg)
    rv = RB_FL / math.cos(math.pi / 16)                                   # 16-gon circumscribing the flange (D-1 stave precedent)
    for s in range(6):
        k.hull(tube_ring(-half + s*RB_SEG_DEG/6, rv, RB_R, n=16), tube_ring(-half + (s+1)*RB_SEG_DEG/6, rv, RB_R, n=16), "arc %d" % s)
    return k

def build_junction():
    k = Kit("SM_S4_Junction_Chamber", "S4 ring bus / D-1 junction chamber: concrete tee housing, bore ID 7 700 flush with D-1, copper tee")
    k.slots = ["MS_Concrete", "MS_Conductor"]; mb = k.mb
    o2 = [(J_HY, -J_HZ + J_CH), (J_HY, J_HZ - J_CH), (J_HY - J_CH, J_HZ), (-J_HY + J_CH, J_HZ),
          (-J_HY, J_HZ - J_CH), (-J_HY, -J_HZ + J_CH), (-J_HY + J_CH, -J_HZ), (J_HY - J_CH, -J_HZ)]
    outline = lambda x: [(x, y, z) for y, z in o2]
    mb.bridge(outline(0.0), circle_x(J_BORE_R, 0.0), (0, 0, 0), (0, 1, 0), (0, 0, 1))
    mb.loft(circle_x(J_BORE_R, 0.0), circle_x(J_BORE_R, J_BORE_X), 1, 1)
    mb.fan((J_BORE_X, 0.0, 0.0), circle_x(J_BORE_R, J_BORE_X), 1, 2)
    mb.loft(outline(0.0), outline(J_X0)); mb.poly(outline(J_X0))
    # copper tee (closed shells, mat 2): D-1 stub, hub, ring-bus conductor crossing the bore
    n = 32; hx = J_HUB[0]
    mb.loft(circle_x(J_COND_R, 0.0, n), circle_x(J_COND_R, hx, n), 2, 1)
    mb.fan((0.0, 0.0, 0.0), circle_x(J_COND_R, 0.0, n), 2, 8); mb.fan((hx, 0.0, 0.0), circle_x(J_COND_R, hx, n), 2, 16)
    lathe(mb, [(1850.0, -1900.0), (2100.0, -1650.0), (2100.0, 1650.0), (1850.0, 1900.0)], 48, 2, (hx, 0.0))
    arc = [tube_ring(th, J_COND_R, RB_R, (J_AXIS_X, 0.0, 0.0), n) for th in range(-13, 14)]
    for i in range(len(arc) - 1): mb.loft(arc[i], arc[i+1], 2, 1)
    for th, ring, sg in ((-13, arc[0], 8), (13, arc[-1], 16)):
        a = math.radians(th); mb.fan((J_AXIS_X + RB_R*math.cos(a), RB_R*math.sin(a), 0.0), ring, 2, sg)
    # --- collision: 40 staves circumscribing the bore, back wall, conductor prisms
    NS = 40
    for s in range(NS):
        a0, a1 = 2*math.pi*s/NS, 2*math.pi*(s+1)/NS; am = (a0 + a1) / 2
        p = clip(o2, lambda p_: -math.sin(a0)*p_[0] + math.cos(a0)*p_[1])
        p = clip(p, lambda p_: math.sin(a1)*p_[0] - math.cos(a1)*p_[1])
        p = clip(p, lambda p_: math.cos(am)*p_[0] + math.sin(am)*p_[1] - J_BORE_R)
        k.hull([(J_BORE_X, y, z) for y, z in p], [(0.0, y, z) for y, z in p], "stave %d" % s)
    k.hull(outline(J_X0), outline(J_BORE_X), "back wall")
    rv = J_COND_R / math.cos(math.pi / 16)
    k.hull(circle_x(rv, hx, 16), circle_x(rv, 0.0, 16), "D-1 conductor stub")
    rh = 2100.0 / math.cos(math.pi / 16)
    k.hull(circle(rh, -1900.0, 16, (hx, 0.0)), circle(rh, 1900.0, 16, (hx, 0.0)), "tee hub")
    for s in range(8):
        k.hull(tube_ring(-13 + s*26/8.0, rv, RB_R, (J_AXIS_X, 0.0, 0.0), 16), tube_ring(-13 + (s+1)*26/8.0, rv, RB_R, (J_AXIS_X, 0.0, 0.0), 16), "ring conductor %d" % s)
    return k

BUILDERS = [build_tile, build_capital, build_octagon, build_collar, build_pylon, build_plinth, build_ring_seg, build_junction]

# ================================================================= assembly (UE world, cm) — single source for the UE script
def assembly():
    A = []
    def add(label, mesh, loc, rot=(0.0, 0.0, 0.0), scale=1.0, zmin=None, zmax=None):
        A.append({"label": label, "mesh": mesh, "loc": [float(c) for c in loc], "rot_rpy": list(rot), "scale": scale, "z_min": zmin, "z_max": zmax})
    add("A0_Down_Capital", "SM_Spire_Capital", (0, 0, Z_SLAB_BOT), zmin=Z_CAP_BOT, zmax=Z_SLAB_BOT)
    z = Z_CAP_BOT
    for i in range(OCT_N):
        s = OCT_Q ** i; zb = z - OCT_H * s if i < OCT_N - 1 else Z_OCT_BOT
        add("A0_Down_Seg_%02d" % (i + 1), "SM_Spire_Octagon_Seg", (0, 0, z), scale=s, zmin=z - OCT_H * s, zmax=z); z = z - OCT_H * s
    add("A0_Down_Collar_ICM", "SM_Spire_Collar_ICM", (0, 0, Z_OCT_BOT), zmin=Z_DISC_DN, zmax=Z_OCT_BOT)
    add("A0_Up_Collar_ICM", "SM_Spire_Collar_ICM", (0, 0, Z_PYL_TOP), rot=(180.0, 0.0, 0.0), zmin=Z_PYL_TOP, zmax=Z_DISC_UP)
    z = Z_PYL_BOT; segs = []
    for i in range(PYL_N):
        s = PYL_Q ** i; segs.append((i, z, s)); z = z + PYL_H * s
    for i, zz, s in reversed(segs):
        add("A0_Up_Seg_%02d" % (i + 1), "SM_Spire_Pylon_Seg", (0, 0, zz), scale=s, zmin=zz, zmax=zz + PYL_H * s)
    add("A0_Up_Plinth", "SM_Spire_Plinth", (0, 0, Z_BED), zmin=Z_BED - PLINTH_EMBED, zmax=Z_PYL_BOT)
    add("S4_Junction_Chamber_D1", "SM_S4_Junction_Chamber", D1_PORT, zmin=Z_RING - J_HZ, zmax=Z_RING + J_HZ)
    tiles = []; n = int(SLAB_R // TILE) + 1
    for i in range(-n, n):
        for j in range(-n, n):
            cx, cy = TILE*(i + 0.5), TILE*(j + 0.5)
            if math.hypot(abs(cx) + TILE/2, abs(cy) + TILE/2) <= SLAB_R: tiles.append([cx, cy, 0.0])
    ring = [[0.0, 0.0, RB_GAP_HALF + RB_SEG_DEG*(i + 0.5)] for i in range(RB_COUNT)]      # x, y, yaw
    ism = [{"label": "KikutakeSlab_Tiles", "mesh": "SM_Kikutake_Slab_Tile", "loc": [0.0, 0.0, Z_SLAB_BOT], "instances_xyz": tiles},
           {"label": "S4_RingBus", "mesh": "SM_S4_RingBus_Seg", "loc": [0.0, 0.0, Z_RING], "instances_yaw": [r[2] for r in ring]}]
    return {"actors": A, "ism": ism}

def build_all():
    kits = [b() for b in BUILDERS]
    for k in kits: k.mb.finalize()
    return kits

def spec_dict(kits, extra=None):
    asm = assembly()
    d = {"units": "cm", "space": "3ds Max RH Z-up; UE import (x, y, z) -> (x, -y, z); all meshes mirror-symmetric in Y",
         "folder": "Environment/Macro/Spire_A0/Architecture", "content": "/Game/AOS_DK_Game/Environment/Macro/Spire_A0",
         "material": "M_AOS_Concrete_BoxMap", "shell_r": SHELL_R,
         "marks": {"slab_top": Z_SLAB_TOP, "slab_bot": Z_SLAB_BOT, "cap_bot": Z_CAP_BOT, "oct_bot": Z_OCT_BOT, "disc_dn": Z_DISC_DN,
                   "disc_up": Z_DISC_UP, "ring": Z_RING, "pyl_top": Z_PYL_TOP, "pyl_bot": Z_PYL_BOT, "bed": Z_BED, "d1_port": list(D1_PORT)},
         "params": {"oct_n": OCT_N, "oct_q": OCT_Q, "oct_h": OCT_H, "pyl_n": PYL_N, "pyl_q": PYL_Q, "pyl_h": PYL_H, "pyl_r0": PYL_R0,
                    "pyl_d_at_-135000": 2*pyl_r_world(-135000.0), "collar_r": COL_R, "tile": TILE, "oculus_r": OC_R,
                    "ring_r": RB_R, "ring_tube_r": RB_TUBE, "ring_flange_r": RB_FL, "bore_r": J_BORE_R, "bore_depth": -J_BORE_X,
                    "junction_half_yz": [J_HY, J_HZ], "junction_len": -J_X0},
         "meshes": {k.name: dict(k.mb.stats, note=k.note, slots=k.slots, ucx=len(k.ucx), ucx_max_verts=max(2*len(u[0]) for u in k.ucx)) for k in kits},
         "assembly": asm}
    if extra: d.update(extra)
    return d

# ================================================================= 3ds Max layer
def P(a): return rt.Point3(float(a[0]), float(a[1]), float(a[2]))

def max_clean(names):
    dead = [o for o in rt.objects if any(str(o.name) == n or str(o.name).startswith("UCX_" + n + "_") for n in names)]
    for o in dead:
        try: rt.delete(o)
        except Exception: pass

def max_material(slots):
    mm = rt.Multimaterial(numsubs=len(slots)); mm.name = "MM_SpireA0_%d" % len(slots)
    cols = {"MS_Concrete": rt.Color(128, 126, 120), "MS_Conductor": rt.Color(242, 163, 138)}
    for i, s in enumerate(slots):
        pm = rt.PhysicalMaterial(); pm.name = s; pm.base_color = cols.get(s, rt.Color(128, 128, 128))
        pm.roughness = 0.85 if s == "MS_Concrete" else 0.15; pm.metalness = 0.0 if s == "MS_Concrete" else 1.0
        mm.materialList[i] = pm; mm.names[i] = s
    return mm

def max_mesh(k, mm):
    mb = k.mb
    m = rt.mesh(vertices=[P(p) for p in mb.v], faces=[rt.Point3(f[0]+1, f[1]+1, f[2]+1) for f in mb.f])
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
        # outward winding: flip if signed volume is negative
        vol = sum(vdot(pts[f[0]-1], vcross(pts[f[1]-1], pts[f[2]-1])) for f in faces)
        c = [sum(p[i] for p in pts)/len(pts) for i in range(3)]
        vol = sum(vdot(vsub(pts[f[0]-1], c), vcross(vsub(pts[f[1]-1], c), vsub(pts[f[2]-1], c))) for f in faces)
        if vol < 0: faces = [(f[0], f[2], f[1]) for f in faces]
        u = rt.mesh(vertices=[P(p) for p in pts], faces=[rt.Point3(*f) for f in faces])
        u.name = "UCX_%s_%02d" % (k.name, idx); u.wirecolor = rt.Color(255, 60, 60)
        nodes.append(u)
    return nodes

def max_build(export=True):
    out = {"max_units": str(rt.units.SystemType), "max_scale": float(rt.units.SystemScale)}
    if "centimeter" not in out["max_units"].lower() or abs(out["max_scale"] - 1.0) > 1e-9:
        raise RuntimeError("System units must be 1 unit = 1 cm, got %s x %s" % (out["max_units"], out["max_scale"]))
    kits = build_all()
    max_clean([k.name for k in kits])
    if export and not os.path.isdir(FBX_DIR): os.makedirs(FBX_DIR)
    rep = {}
    for k in kits:
        mm = max_material(k.slots)
        node = max_mesh(k, mm); ucx = max_ucx(k)
        lay = rt.LayerManager.getLayerFromName(k.name) or rt.LayerManager.newLayerFromName(k.name)
        lay.addnode(node)
        for u in ucx: lay.addnode(u)
        r = {"faces_poly": int(rt.polyop.getNumFaces(node)), "verts": int(rt.polyop.getNumVerts(node)), "ucx": len(ucx),
             "open_edges": int(rt.polyop.getOpenEdges(node).numberSet), "pivot": [float(node.pos.x), float(node.pos.y), float(node.pos.z)],
             "bbox_min": [round(float(c), 3) for c in (node.min.x, node.min.y, node.min.z)],
             "bbox_max": [round(float(c), 3) for c in (node.max.x, node.max.y, node.max.z)]}
        rep[k.name] = r
    out["nodes"] = rep
    spec = spec_dict(kits, {"max": out})
    with open(SPEC_PATH, "w") as f: json.dump(spec, f, indent=1)
    return out

def max_export(names=None):
    """FBX per asset (render node + its UCX hulls). Exporter params are the AOS_DK preset (cm, Z-up, smoothing groups, binary)."""
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

# ================================================================= offline self-test
def selftest():
    import numpy as np
    from scipy.spatial import ConvexHull
    kits = build_all(); rep = {}; ok = True
    for k in kits:
        V = np.array(k.mb.v); eqs = []
        for bot, top, label in k.ucx:
            pts = np.array(list(bot) + list(top)); h = ConvexHull(pts)
            if len(h.vertices) != len(pts):
                # points strictly inside the hull would mean a non-convex ring
                d = max(0.0, -float(np.max([np.max(h.equations[:, :3] @ p + h.equations[:, 3]) for p in pts])))
                if d > 0.05: ok = False; print("NON-CONVEX", k.name, label, len(h.vertices), len(pts), d)
            eqs.append(h.equations)
        # visual surface beyond collision (bible §3.0.2: <= 15 cm): sample verts + face centroids
        S = np.vstack([V, np.array([(V[f[0]] + V[f[1]] + V[f[2]]) / 3.0 for f in k.mb.f])])
        best = np.full(len(S), 1e9)
        for E in eqs:
            d = np.max(S @ E[:, :3].T + E[:, 3], axis=1); best = np.minimum(best, d)
        rep[k.name] = dict(k.mb.stats, ucx=len(k.ucx), visual_beyond_collision_cm=round(float(max(0.0, best.max())), 2))
    asm = assembly(); A = asm["actors"]
    def gap(prefix, down):
        segs = [a for a in A if a["label"].startswith(prefix)]
        segs.sort(key=lambda a: -a["z_max"] if down else a["z_min"])
        return max(abs((segs[i]["z_min"] - segs[i+1]["z_max"]) if down else (segs[i]["z_max"] - segs[i+1]["z_min"])) for i in range(len(segs) - 1)), segs
    gd, sd = gap("A0_Down_Seg", True); gu, su = gap("A0_Up_Seg", False)
    checks = {
        "oct q / H0": [OCT_Q, OCT_H], "pyl q / H0 / R0": [PYL_Q, PYL_H, PYL_R0],
        "A-0 down joint gap max": gd, "A-0 down last bottom - (-86000)": sd[-1]["z_min"] - Z_OCT_BOT,
        "A-0 down AF at bottom": 2 * OCT_A0 * OCT_Q ** OCT_N,
        "A-0 up joint gap max": gu, "A-0 up last top - (-94000)": su[-1]["z_max"] - Z_PYL_TOP,
        "A-0 up D at top": 2 * PYL_R0 * PYL_Q ** PYL_N, "A-0 up D at -135000": 2 * pyl_r_world(-135000.0),
        "S4 gap": Z_DISC_DN - Z_DISC_UP, "tiles": len(asm["ism"][0]["instances_xyz"]), "ring segs": len(asm["ism"][1]["instances_yaw"]),
        "actors": len(A) + len(asm["ism"]),
    }
    print(json.dumps(rep, indent=1)); print(json.dumps(checks, indent=1)); print("OK" if ok else "FAILED")
    return kits, rep, checks

if IN_MAX:
    SPIRE_RESULT = max_build()
elif __name__ == "__main__":
    selftest()
