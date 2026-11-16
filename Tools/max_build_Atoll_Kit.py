# =============================================================================
# AOS-DK | Surface Pontoon Atoll "Motherboard City", Stage 1 | 3ds Max 2027 (pymxs) -> FBX -> UE 5.7.4
# AOS_PontoonHub_Urban_Bible §1 (zoning), §3 (LARS), §4 (pedestrian graph), §5 (module catalogue M-01 .. M-15).
# Same pipeline as Tools/max_build_Monoliths_Kit.py / max_build_DeficitKit.py: closed chamfered solids, convex UCX hulls
# (<= 32 verts), box UVW (1 UV = 200 cm), one FBX per asset, and a spec JSON (mesh stats + assembly table) that is the
# single source for Tools/ue_build_Atoll_City.py.  No geometry is generated in Unreal.
#
# The test level has no Socket shaft: the dock is the robotic ALARSDockArm at (-1669, 50, 80) that lowers Shell-1 at
# (-1000, 820) and the Shell swims south to TP_Station_A.  The Bible plan is therefore re-anchored on the live actors:
#   hex grid (pointy-top, 1 000 across flats):  X = -1000 + 1000 (q + r/2),  Y = 820 + 866.03 r,  cell (0, 0) = Moonpool
#   lane to Station A = strip X -1500 .. -500 south of the pool, kept free of every pontoon and submerged part.
#
# Meshes are authored in UE-local coordinates and mirrored (y -> -y, winding reversed) for Max, so the Max RH -> UE LH
# import (x, -y, z) lands them un-mirrored.
#
# Run in Max:  ns = {}; exec(open(r"<proj>\Tools\max_build_Atoll_Kit.py", encoding="utf-8").read(), ns)
#              ns["build"]()  -> per-asset stats, writes Tools/Atoll_Kit_spec.json, saves SourceArt/Atoll/Atoll_Kit.max
#              ns["export"]() -> one FBX per asset in Content/AOS_DK_Game/Environment/Atoll/Kit
# Offline preview / stats helpers: Claude outputs/Atoll_Stage1_WIP/*.py
# STATUS 2026-11-15: WORK IN PROGRESS, saved on request before any DCC / engine run. All 18 builders and the layout run
# headless (0 open edges, spec JSON builds). NOT yet run in 3ds Max, no FBX exported, nothing imported or placed in Unreal.
# Still to write: the offline self-test block and Tools/ue_build_Atoll_City.py. Notes: Claude outputs/Atoll_Stage1_WIP/NOTES.md
# =============================================================================
import math, json, os, random

try:
    from pymxs import runtime as rt
except Exception:
    rt = None

PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
FBX_DIR = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "Atoll", "Kit")
SPEC_PATH = os.path.join(PROJ, "Tools", "Atoll_Kit_spec.json")
MAX_PATH = os.path.join(PROJ, "SourceArt", "Atoll", "Atoll_Kit.max")
TILE = 200.0
UCX_MAX = 32

# ---------------------------------------------------------------- live level anchors (world cm, read from Lvl_FirstPerson)
ARM = (-1669.0, 50.0, 80.0); ARM_YAW = 49.017                    # LARS_DockArm (ALARSDockArm)
DISEMBARK = (-1360.0, 420.0)                                      # BP_ShellDock.DisembarkPoint (XY)
BERTH = (-1000.0, 820.0)                                          # Shell-1 drop zone, heading -90
LAUNCH_CAM = (-238.4, -133.08, 950.0)
STATION_A = (-1000.0, -1380.0, -450.0)
A_TRIGGER = (-1450.0, -550.0, -669.0, -169.0, -900.0, 0.0)        # TP_Station_A EntranceTrigger (x0, x1, y0, y1, z0, z1)
A_FRAME = (-2560.0, -540.0, -1880.0, -640.0)                      # PortalFrame plan bounds + 50 (ring top Z +150, door pocket)
A_SHAFT = (-1680.0, -640.0, -4300.0, -1800.0)                     # ShaftMesh plan bounds + 60 (top Z +5)
PILLARS = [(-2660.0, 1910.0), (-2640.0, -1560.0), (3261.0, 1874.0), (3371.0, -1526.0)]   # Tower A peak pillars, top Z -369
WATER_Z = 40.0
Z_D1, Z_D2 = 80.0, 120.0                                          # pontoon deck / arterial deck (Bible 1.3)
LANE = (-1500.0, -500.0)                                          # swim corridor (X)
CX, CY = BERTH
HA = 500.0                                                        # hex apothem
HR = HA / math.cos(math.radians(30.0))                            # 577.35 vertex radius
ROW = 1.5 * HR                                                    # 866.03 row pitch
CAPSULE = (34.0, 96.0)                                            # BP_AdminCharacter (radius, half-height); MaxStepHeight 45

# slot catalogue: Max preview colour, metalness, roughness, emission colour
SLOT_CAT = {
    "MS_Deck": ((104, 82, 66), 0.6, 0.65, None), "MS_Corten": ((150, 78, 40), 0.5, 0.80, None),
    "MS_Floaters": ((28, 84, 170), 0.0, 0.45, None), "MS_Biorock": ((214, 208, 190), 0.0, 0.90, None),
    "MS_Anode": ((40, 70, 80), 0.8, 0.40, (139, 233, 253)), "MS_Sand": ((206, 184, 140), 0.0, 0.95, None),
    "MS_Lumi": ((60, 60, 20), 0.0, 0.50, (241, 250, 140)), "MS_Tin": ((132, 138, 128), 0.7, 0.55, None),
    "MS_Pipe": ((150, 152, 155), 1.0, 0.40, None), "MS_Plank": ((126, 96, 62), 0.0, 0.85, None),
    "MS_Rope": ((170, 150, 110), 0.0, 0.95, None), "MS_Shell": ((36, 120, 122), 0.3, 0.60, None),
    "MS_Window": ((40, 30, 10), 0.0, 0.30, (255, 184, 108)), "MS_Door": ((120, 44, 36), 0.3, 0.65, None),
    "MS_Trim": ((44, 46, 50), 0.6, 0.50, None), "MS_Stair": ((90, 94, 98), 0.9, 0.50, None),
    "MS_Canopy": ((226, 150, 70), 0.0, 0.70, None), "MS_Liquid": ((10, 60, 60), 0.0, 0.20, (80, 240, 230)),
    "MS_Chassis": ((58, 64, 74), 0.5, 0.50, None), "MS_PCB": ((20, 90, 50), 0.1, 0.45, None),
    "MS_Screen": ((6, 20, 16), 0.0, 0.15, (80, 250, 123)), "MS_LED": ((4, 20, 8), 0.0, 0.30, (80, 250, 123)),
    "MS_Brass": ((150, 120, 60), 0.9, 0.45, None), "MS_Neon": ((30, 10, 40), 0.0, 0.30, (189, 147, 249)),
    "MS_Rotor": ((140, 100, 50), 0.9, 0.40, None), "MS_Hazard": ((222, 170, 20), 0.1, 0.55, None),
    "MS_Fender": ((18, 18, 20), 0.0, 0.85, None), "MS_Status": ((4, 20, 24), 0.0, 0.40, (139, 233, 253)),
    "MS_Yellow": ((214, 160, 24), 0.2, 0.55, None), "MS_Beacon": ((40, 6, 6), 0.0, 0.40, (255, 85, 85)),
    "MS_Glass": ((170, 220, 226), 0.0, 0.05, None),
}

# ---------------------------------------------------------------- vector math
def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vdot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def vlen(a): return math.sqrt(vdot(a, a))
def vnorm(a):
    l = vlen(a); return (a[0]/l, a[1]/l, a[2]/l)
def vmid(pts):
    n = float(len(pts)); return (sum(p[0] for p in pts)/n, sum(p[1] for p in pts)/n, sum(p[2] for p in pts)/n)
def rad(d): return math.radians(d)

class Fr(object):
    """Local frame: p(u, v, w) = o + u*x + v*y + w*z."""
    def __init__(s, o=(0.0, 0.0, 0.0), x=(1.0, 0.0, 0.0), y=(0.0, 1.0, 0.0), z=(0.0, 0.0, 1.0)):
        s.o, s.x, s.y, s.z = tuple(map(float, o)), x, y, z
    def p(s, u, v=0.0, w=0.0):
        return (s.o[0]+u*s.x[0]+v*s.y[0]+w*s.z[0], s.o[1]+u*s.x[1]+v*s.y[1]+w*s.z[1], s.o[2]+u*s.x[2]+v*s.y[2]+w*s.z[2])
    def d(s, a):
        return (a[0]*s.x[0]+a[1]*s.y[0]+a[2]*s.z[0], a[0]*s.x[1]+a[1]*s.y[1]+a[2]*s.z[1], a[0]*s.x[2]+a[1]*s.y[2]+a[2]*s.z[2])

I = Fr()
def zfr(o=(0.0, 0.0, 0.0)):
    """Frame whose x runs up: lathe / ring / cprism built in it stand on Z; p(w, u, v) = o + (u, v, w)."""
    return Fr(o, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
def yawfr(o, yaw):
    c, s = math.cos(rad(yaw)), math.sin(rad(yaw))
    return Fr(o, (c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0))
def axis_fr(o, xdir, zhint=(0.0, 0.0, 1.0)):
    x = vnorm(xdir)
    if abs(vdot(x, zhint)) > 0.99: zhint = (0.0, 1.0, 0.0) if abs(x[1]) < 0.9 else (1.0, 0.0, 0.0)
    y = vnorm(vcross(zhint, x)); z = vcross(x, y)
    return Fr(o, x, y, z)

def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i+1) % len(pts)]
        n[0] += (a[1]-b[1])*(a[2]+b[2]); n[1] += (a[2]-b[2])*(a[0]+b[0]); n[2] += (a[0]-b[0])*(a[1]+b[1])
    return tuple(n)
def ccw(poly): return list(poly) if area2(poly) > 0 else list(poly)[::-1]
def area2(poly):
    return 0.5*sum(poly[i][0]*poly[(i+1) % len(poly)][1]-poly[(i+1) % len(poly)][0]*poly[i][1] for i in range(len(poly)))

# ---------------------------------------------------------------- mesh builder (one closed solid per primitive, as in the Deficit kit)
class MB(object):
    def __init__(s):
        s.v, s.f = [], []        # f: (idx list, slot, sg)
        s._b, s.flips, s.prims, s.spans = 0, 0, 0, []
    def av(s, p):
        s.v.append((float(p[0]), float(p[1]), float(p[2]))); return len(s.v)-1
    def poly(s, idx, mat, sg=0, hint=None):
        u = []
        for i in idx:
            if not u or u[-1] != i: u.append(i)
        if len(u) > 1 and u[0] == u[-1]: u.pop()
        if len(u) < 3: return
        if hint is not None and vdot(newell([s.v[i] for i in u]), hint) < 0: u = u[::-1]
        s.f.append((u, mat, sg))
    def cpoly(s, idx, mat, sg, ref):
        s.poly(idx, mat, sg, vsub(vmid([s.v[i] for i in idx]), ref))
    def begin(s): s._b = len(s.f)
    def end(s):
        vol = 0.0
        for (idx, m, g) in s.f[s._b:]:
            p0 = s.v[idx[0]]
            for k in range(1, len(idx)-1): vol += vdot(p0, vcross(s.v[idx[k]], s.v[idx[k+1]]))
        if vol < 0:
            s.flips += 1
            s.f[s._b:] = [(idx[::-1], m, g) for (idx, m, g) in s.f[s._b:]]
        s.prims += 1; s.spans.append((s._b, len(s.f)))
    def tris(s):
        out = []
        for (idx, m, g) in s.f:
            n = len(idx)
            for k in range(1, n-1):
                ev = 2 | (1 if k == 1 else 0) | (4 if k == n-2 else 0)
                out.append(((idx[0], idx[k], idx[k+1]), m, g, ev))
        return out
    def area(s):
        a = 0.0
        for (t, m, g, e) in s.tris():
            a += 0.5*vlen(vcross(vsub(s.v[t[1]], s.v[t[0]]), vsub(s.v[t[2]], s.v[t[0]])))
        return a
    def bbox(s):
        return [min(p[i] for p in s.v) for i in range(3)], [max(p[i] for p in s.v) for i in range(3)]
    def open_edges(s):
        """Every primitive must be a closed 2-manifold with consistent winding: each directed edge once, its reverse once."""
        bad = 0
        for (b0, b1) in s.spans:
            d = {}
            for (idx, m, g) in s.f[b0:b1]:
                for k in range(len(idx)):
                    e = (idx[k], idx[(k+1) % len(idx)]); d[e] = d.get(e, 0) + 1
            bad += sum(1 for (a, b), c in d.items() if c != 1 or d.get((b, a), 0) != 1)
        return bad

# ---------------------------------------------------------------- primitives
def cbox(mb, mat, fr, x0, x1, y0, y1, z0, z1, c=0.5):
    lo = (min(x0, x1), min(y0, y1), min(z0, z1)); hi = (max(x0, x1), max(y0, y1), max(z0, z1))
    ext = [hi[i]-lo[i] for i in range(3)]
    if min(ext) <= 1e-6: return
    c = min(c, 0.45*min(ext))
    cen = fr.p(*[(lo[i]+hi[i])/2.0 for i in range(3)])
    mb.begin()
    corners = [(a, b, d) for a in (0, 1) for b in (0, 1) for d in (0, 1)]
    if c <= 0.01:
        V = {k: mb.av(fr.p(*[hi[i] if k[i] else lo[i] for i in range(3)])) for k in corners}
        for a in range(3):
            b, d = (a+1) % 3, (a+2) % 3
            for sgn in (0, 1):
                loop = []
                for (tb, td) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    k = [0, 0, 0]; k[a], k[b], k[d] = sgn, tb, td; loop.append(V[tuple(k)])
                mb.cpoly(loop, mat, 0, cen)
        mb.end(); return
    V = {}
    for a in range(3):
        for k in corners:
            pt = [0.0, 0.0, 0.0]
            for i in range(3):
                if i == a: pt[i] = hi[i] if k[i] else lo[i]
                else: pt[i] = (hi[i]-c) if k[i] else (lo[i]+c)
            V[(a, k)] = mb.av(fr.p(*pt))
    for a in range(3):
        b, d = (a+1) % 3, (a+2) % 3
        for sgn in (0, 1):
            loop = []
            for (tb, td) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                k = [0, 0, 0]; k[a], k[b], k[d] = sgn, tb, td; loop.append(V[(a, tuple(k))])
            mb.cpoly(loop, mat, 0, cen)
    for a in range(3):
        for b in range(a+1, 3):
            t = 3-a-b
            for sa in (0, 1):
                for sb in (0, 1):
                    k0 = [0, 0, 0]; k0[a], k0[b], k0[t] = sa, sb, 0
                    k1 = list(k0); k1[t] = 1
                    mb.cpoly([V[(a, tuple(k0))], V[(a, tuple(k1))], V[(b, tuple(k1))], V[(b, tuple(k0))]], mat, 0, cen)
    for k in corners:
        mb.cpoly([V[(0, k)], V[(1, k)], V[(2, k)]], mat, 0, cen)
    mb.end()

def bar(mb, mat, p0, p1, w, h, up=(0.0, 0.0, 1.0), c=0.3):
    """Chamfered box from p0 to p1 (length axis), w across (horizontal), h along 'up'."""
    fr = axis_fr(p0, vsub(p1, p0), up)
    cbox(mb, mat, fr, 0.0, vlen(vsub(p1, p0)), -w/2.0, w/2.0, -h/2.0, h/2.0, c)

def lathe(mb, mat, fr, prof, sides, smooth=True, phase=0.0):
    """Revolve closed (t, r) profile about fr.x. r = 0 points become poles."""
    n = len(prof); ar = area2(prof)
    ang = [2*math.pi*k/sides+phase for k in range(sides)]
    rings = []
    for (t, r) in prof:
        if r < 1e-6:
            i = mb.av(fr.p(t, 0.0, 0.0)); rings.append([i]*sides)
        else:
            rings.append([mb.av(fr.p(t, r*math.cos(a), r*math.sin(a))) for a in ang])
    mb.begin()
    for i in range(n):
        j = (i+1) % n
        dt, dr = prof[j][0]-prof[i][0], prof[j][1]-prof[i][1]
        if abs(dt) < 1e-9 and abs(dr) < 1e-9: continue
        nt, nr = (dr, -dt) if ar > 0 else (-dr, dt)
        sg = 0 if (not smooth or abs(dt) < 1e-6) else (1 << (i % 6))
        for k in range(sides):
            k2 = (k+1) % sides; am = 2*math.pi*(k+0.5)/sides+phase
            hint = fr.d((nt, nr*math.cos(am), nr*math.sin(am)))
            mb.poly([rings[i][k], rings[i][k2], rings[j][k2], rings[j][k]], mat, sg, hint)
    mb.end()

def cyl(mb, mat, p0, p1, r, sides=16, c=0.4, smooth=True, phase=0.0):
    L = vlen(vsub(p1, p0)); c = min(c, 0.4*min(r, L))
    fr = axis_fr(p0, vsub(p1, p0))
    if c > 0.01: prof = [(0.0, 0.0), (0.0, r-c), (c, r), (L-c, r), (L, r-c), (L, 0.0)]
    else: prof = [(0.0, 0.0), (0.0, r), (L, r), (L, 0.0)]
    lathe(mb, mat, fr, prof, sides, smooth, phase)

def ring(mb, mat, fr, t0, t1, r0, r1, sides, c=0.0, smooth=True, phase=0.0):
    c = min(c, 0.4*(t1-t0), 0.4*(r1-r0))
    if c > 0.01: prof = [(t0, r0), (t0, r1-c), (t0+c, r1), (t1-c, r1), (t1, r1-c), (t1, r0)]
    else: prof = [(t0, r0), (t0, r1), (t1, r1), (t1, r0)]
    lathe(mb, mat, fr, prof, sides, smooth, phase)

def inset_convex(poly, c):
    n = len(poly); lines = []
    for i in range(n):
        a, b = poly[i], poly[(i+1) % n]
        d = (b[0]-a[0], b[1]-a[1]); L = math.hypot(*d); d = (d[0]/L, d[1]/L)
        nin = (-d[1], d[0])
        lines.append(((a[0]+nin[0]*c, a[1]+nin[1]*c), d))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i-1], lines[i]
        den = d1[0]*d2[1]-d1[1]*d2[0]
        if abs(den) < 1e-9: out.append(p2); continue
        t = ((p2[0]-p1[0])*d2[1]-(p2[1]-p1[1])*d2[0])/den
        out.append((p1[0]+d1[0]*t, p1[1]+d1[1]*t))
    return out

def cprism(mb, mat, fr, poly, w0, w1, c=0.0):
    """Chamfered extrusion of a convex 2D polygon (u, v) along fr.x (w0..w1)."""
    if area2(poly) < 0: poly = poly[::-1]
    if w0 > w1: w0, w1 = w1, w0
    n = len(poly); c = min(c, 0.4*abs(w1-w0))
    if c > 0.01:
        ins = inset_convex(poly, c)
        rings = [(ins, w0), (poly, w0+c), (poly, w1-c), (ins, w1)]
    else:
        rings = [(poly, w0), (poly, w1)]
    R = [[mb.av(fr.p(w, u, v)) for (u, v) in pl] for (pl, w) in rings]
    cen = fr.p((w0+w1)/2.0, sum(p[0] for p in poly)/n, sum(p[1] for p in poly)/n)
    mb.begin()
    for s in range(len(rings)-1):
        for k in range(n):
            k2 = (k+1) % n
            mb.cpoly([R[s][k], R[s][k2], R[s+1][k2], R[s+1][k]], mat, 0, cen)
    mb.cpoly(R[0], mat, 0, cen); mb.cpoly(R[-1], mat, 0, cen)
    mb.end()

def prism(mb, mat, poly, z0, z1, c=0.0, o=(0.0, 0.0, 0.0)):
    """Vertical extrusion of a convex plan polygon (x, y)."""
    cprism(mb, mat, zfr(o), poly, z0, z1, c)

def hull3d(pts, eps=1e-3):
    n = len(pts); planes = []
    for i in range(n):
        for j in range(i+1, n):
            for k in range(j+1, n):
                nv = vcross(vsub(pts[j], pts[i]), vsub(pts[k], pts[i])); l = vlen(nv)
                if l < 1e-6: continue
                nv = vmul(nv, 1.0/l); d = vdot(nv, pts[i])
                sd = [vdot(nv, p)-d for p in pts]
                if max(sd) <= eps: pass
                elif min(sd) >= -eps: nv, d = vmul(nv, -1.0), -d
                else: continue
                if any(vdot(nv, q[0]) > 0.99999 and abs(d-q[1]) < 1e-2 for q in planes): continue
                planes.append((nv, d))
    faces, used = [], set()
    for (nv, d) in planes:
        idx = [i for i, p in enumerate(pts) if abs(vdot(nv, p)-d) < 1e-2]
        c = vmid([pts[i] for i in idx])
        u = vnorm(vsub(pts[idx[0]], c)); w = vcross(nv, u)
        idx.sort(key=lambda i: math.atan2(vdot(vsub(pts[i], c), w), vdot(vsub(pts[i], c), u)))
        faces.append(idx); used.update(idx)
    remap = {o: k for k, o in enumerate(sorted(used))}
    return [pts[o] for o in sorted(used)], [[remap[i] for i in f] for f in faces], planes

def chull(mb, mat, pts, sg=0):
    """Convex solid through pts (wedges, brackets, rocks)."""
    hp, hf, pl = hull3d([tuple(map(float, p)) for p in pts])
    ids = [mb.av(p) for p in hp]; cen = vmid(hp)
    mb.begin()
    for f in hf: mb.cpoly([ids[i] for i in f], mat, sg, cen)
    mb.end()

def strip(mb, mat, O, I_, z0, z1):
    """Wall solid between two plan polylines O (outer) and I_ (inner), same vertex count, z0..z1."""
    n = len(O)
    o0 = [mb.av((p[0], p[1], z0)) for p in O]; o1 = [mb.av((p[0], p[1], z1)) for p in O]
    i0 = [mb.av((p[0], p[1], z0)) for p in I_]; i1 = [mb.av((p[0], p[1], z1)) for p in I_]
    mb.begin()
    for k in range(n-1):
        mb.poly([o0[k], o1[k], o1[k+1], o0[k+1]], mat, 0)
        mb.poly([i0[k], i0[k+1], i1[k+1], i1[k]], mat, 0)
        mb.poly([o1[k], i1[k], i1[k+1], o1[k+1]], mat, 0)
        mb.poly([o0[k], o0[k+1], i0[k+1], i0[k]], mat, 0)
    mb.poly([o0[0], i0[0], i1[0], o1[0]], mat, 0)
    mb.poly([o0[n-1], o1[n-1], i1[n-1], i0[n-1]], mat, 0)
    mb.end()

def corr_wall(mb, mat, a, b, nrm, z0, z1, t=18.0, depth=4.0, pitch=30.0):
    """Corrugated container wall on the plan line a -> b: ridges on the reference plane, valleys 'depth' behind it,
    flat inner face 't' behind it. nrm = outward unit normal (plan)."""
    L = math.hypot(b[0]-a[0], b[1]-a[1]); d = ((b[0]-a[0])/L, (b[1]-a[1])/L)
    m = max(1, int(round(L/pitch))); p = L/m; ss, hh = [], []
    for k in range(m):
        s0 = k*p
        ss += [s0, s0+0.30*p, s0+0.45*p, s0+0.85*p]; hh += [0.0, 0.0, -depth, -depth]
    ss.append(L); hh.append(0.0)
    O = [(a[0]+d[0]*s+nrm[0]*h, a[1]+d[1]*s+nrm[1]*h) for s, h in zip(ss, hh)]
    I_ = [(a[0]+d[0]*s-nrm[0]*t, a[1]+d[1]*s-nrm[1]*t) for s in ss]
    strip(mb, mat, O, I_, z0, z1)

def sheet(mb, mat, top, th):
    """Thin closed sheet under a grid of points (canopies)."""
    n, m = len(top), len(top[0])
    T = [[mb.av(p) for p in row] for row in top]; B = [[mb.av((p[0], p[1], p[2]-th)) for p in row] for row in top]
    mb.begin()
    for i in range(n-1):
        for j in range(m-1):
            mb.poly([T[i][j], T[i+1][j], T[i+1][j+1], T[i][j+1]], mat, 1)
            mb.poly([B[i][j], B[i][j+1], B[i+1][j+1], B[i+1][j]], mat, 2)
    for i in range(n-1):
        mb.poly([T[i][0], B[i][0], B[i+1][0], T[i+1][0]], mat, 0)
        mb.poly([T[i][m-1], T[i+1][m-1], B[i+1][m-1], B[i][m-1]], mat, 0)
    for j in range(m-1):
        mb.poly([T[0][j], T[0][j+1], B[0][j+1], B[0][j]], mat, 0)
        mb.poly([T[n-1][j], B[n-1][j], B[n-1][j+1], T[n-1][j+1]], mat, 0)
    mb.end()

def drum(mb, mat, p0, p1, r, sides=12):
    """Float drum with two rolling hoops and a bung."""
    L = vlen(vsub(p1, p0)); fr = axis_fr(p0, vsub(p1, p0))
    prof = [(0.0, 0.0), (0.0, r-7), (7.0, r), (0.32*L-4, r), (0.32*L, r+3), (0.32*L+4, r), (0.68*L-4, r), (0.68*L, r+3),
            (0.68*L+4, r), (L-7, r), (L, r-7), (L, 0.0)]
    lathe(mb, mat, fr, prof, sides)
    cyl(mb, mat, fr.p(L-0.5, 0.0, 0.55*r), fr.p(L+4.0, 0.0, 0.55*r), 4.5, 8, c=0.8)

def handrail(mb, mat, p0, p1, h=110.0, step=130.0, post=5.0):
    """Stanchions + top and mid rail between two points (the rail follows the slope p0 -> p1)."""
    L = vlen(vsub(p1, p0)); n = max(1, int(math.ceil(L/step)))
    for i in range(n+1):
        q = vadd(p0, vmul(vsub(p1, p0), i/float(n)))
        cbox(mb, mat, I, q[0]-post/2, q[0]+post/2, q[1]-post/2, q[1]+post/2, q[2], q[2]+h, 0.5)
    for (dz, w) in ((h-2.5, 5.5), (0.5*h, 3.5)):
        bar(mb, mat, vadd(p0, (0, 0, dz)), vadd(p1, (0, 0, dz)), w, w, c=0.6)

def hexpoly(a=HA, inset=0.0, o=(0.0, 0.0)):
    """Pointy-top hexagon (flats on +/-X), CCW."""
    a2 = a-inset; r = a2/math.cos(rad(30.0))
    return [(o[0]+a2, o[1]-r/2), (o[0]+a2, o[1]+r/2), (o[0], o[1]+r), (o[0]-a2, o[1]+r/2), (o[0]-a2, o[1]-r/2), (o[0], o[1]-r)]

class Kit(object):
    """Per-asset result container."""
    def __init__(s, note, nanite=True):
        s.mb = MB(); s.ucx = []; s.sock = {}; s.note = note; s.nanite = nanite; s.walk = []
    def ucx_pts(s, pts):
        hp, hf, pl = hull3d([tuple(map(float, p)) for p in pts])
        assert len(hp) <= UCX_MAX, "UCX > %d verts (%d)" % (UCX_MAX, len(hp))
        tri = []
        for f in hf:
            for m in range(1, len(f)-1): tri.append((f[0], f[m], f[m+1]))
        s.ucx.append((hp, tri))
    def ucx_box(s, x0, x1, y0, y1, z0, z1, fr=I):
        s.ucx_pts([fr.p(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    def ucx_prism(s, poly, z0, z1, o=(0.0, 0.0)):
        s.ucx_pts([(o[0]+x, o[1]+y, z) for (x, y) in poly for z in (z0, z1)])
    def socket(s, name, pos, x=(1, 0, 0), z=(0, 0, 1)):
        s.sock[name] = {"pos": [round(c, 3) for c in pos], "x": [round(c, 6) for c in vnorm(x)], "z": [round(c, 6) for c in vnorm(z)]}
    def mirror_y(s):
        """UE-local -> Max (y -> -y); winding reversed so the solids stay outward."""
        m = s.mb; m.v = [(p[0], -p[1], p[2]) for p in m.v]; m.f = [(idx[::-1], mt, g) for (idx, mt, g) in m.f]
        s.ucx = [([(p[0], -p[1], p[2]) for p in pts], [(a, c, b) for (a, b, c) in tri]) for (pts, tri) in s.ucx]

# ================================================================= builders (UE-local cm)
def pontoon_core(k, drums=True):
    """M-01 body: deck plate, Corten ring frame, blue float drums. Pivot = centre of the deck top."""
    mb = k.mb
    prism(mb, "MS_Deck", hexpoly(HA, 3.0), -12.0, 0.0, 1.5)
    P = hexpoly(HA, 16.0)
    for i in range(6):
        a, b = P[i], P[(i+1) % 6]
        bar(mb, "MS_Corten", (a[0], a[1], -36.0), (b[0], b[1], -36.0), 18.0, 48.0, c=1.0)
    for y in (-300.0, 0.0, 300.0):
        hw = HA-30.0 if abs(y) < 1 else 440.0
        bar(mb, "MS_Corten", (-hw, y, -34.0), (hw, y, -34.0), 12.0, 40.0, c=0.8)
    for x in (-250.0, 250.0):
        bar(mb, "MS_Corten", (x, -400.0, -34.0), (x, 400.0, -34.0), 10.0, 36.0, c=0.8)
    if drums:
        for y in (-225.0, -75.0, 75.0, 225.0):
            for x0 in (-462.0, 22.0):
                drum(mb, "MS_Floaters", (x0, y, -130.0), (x0+440.0, y, -130.0), 68.0)
        for y in (-375.0, 375.0):
            drum(mb, "MS_Floaters", (-200.0, y, -130.0), (200.0, y, -130.0), 68.0)
    k.socket("SOCKET_Mount_C", (0, 0, 0))
    for i in range(6):
        a = rad(60.0*i); k.socket("SOCKET_Snap_E%d" % i, (HA*math.cos(a), HA*math.sin(a), 0.0), (math.cos(a), math.sin(a), 0.0))

def b_pontoon_hex_a():
    k = Kit("M-01 hex pontoon 1 000 x 1 155 x 200: steel deck plate, Corten ring frame, 10 blue float drums")
    pontoon_core(k)
    k.ucx_prism(hexpoly(), -200.0, 0.0); k.walk.append((0.0, 0.0, 0.0))
    return k

def rock(mb, mat, cen, r, seed, zlim=None, n=16):
    rnd = random.Random(seed); pts = []
    for i in range(n):
        u = rnd.uniform(-1, 1); a = rnd.uniform(0, 2*math.pi); s = math.sqrt(1-u*u); q = rnd.uniform(0.72, 1.0)
        p = (cen[0]+r[0]*q*s*math.cos(a), cen[1]+r[1]*q*s*math.sin(a), cen[2]+r[2]*q*u)
        if zlim: p = (p[0], p[1], min(max(p[2], zlim[0]), zlim[1]))
        pts.append(p)
    chull(mb, mat, pts)
    return pts

def b_pontoon_biorock():
    k = Kit("M-02 perimeter pontoon 1 000 x 1 155 x 500: M-01 body + rebar cage with three Biorock reef blocks and Ti anodes")
    pontoon_core(k); mb = k.mb
    P = hexpoly(430.0)
    for (x, y) in P: bar(mb, "MS_Corten", (x, y, -198.0), (x, y, -490.0), 8.0, 8.0, up=(1, 0, 0), c=0.6)
    for z in (-345.0, -486.0):
        for i in range(6):
            a, b = P[i], P[(i+1) % 6]; bar(mb, "MS_Corten", (a[0], a[1], z), (b[0], b[1], z), 7.0, 7.0, c=0.5)
    k.ucx_prism(hexpoly(), -200.0, 0.0)
    for i, (c, r) in enumerate((((-190.0, -150.0, -360.0), (190.0, 170.0, 150.0)), ((205.0, -50.0, -372.0), (175.0, 200.0, 135.0)),
                                ((-15.0, 235.0, -352.0), (210.0, 160.0, 150.0)))):
        k.ucx_pts(rock(mb, "MS_Biorock", c, r, 4100+i, (-500.0, -204.0)))
    for i, (x, y, yaw) in enumerate(((10.0, 20.0, 20.0), (-300.0, 190.0, 80.0), (330.0, 210.0, -40.0))):
        cbox(mb, "MS_Anode", yawfr((x, y, -430.0), yaw), -34.0, 34.0, -2.0, 2.0, -60.0, 60.0, 0.6)
        k.socket("SOCKET_Anode_%02d" % i, (x, y, -430.0))
    k.walk.append((0.0, 0.0, 0.0))
    return k

BEACH_DROP = 60.0
def beach_z(x): return -BEACH_DROP*(x+HA)/(2*HA)

def b_agro_beach():
    k = Kit("M-11 beach pontoon 1 000 x 1 155 x 300: sand deck sloping 0 -> -60 toward +X (3.4 deg), Corten hull")
    mb = k.mb
    S = hexpoly(HA, 2.0)
    chull(mb, "MS_Sand", [(x, y, beach_z(x)) for (x, y) in S] + [(x, y, beach_z(x)-36.0) for (x, y) in S])
    Hh = hexpoly(HA, 12.0)
    chull(mb, "MS_Corten", [(x, y, beach_z(x)-34.0) for (x, y) in Hh] + [(x, y, -300.0) for (x, y) in Hh])
    for i, (x, y, r) in enumerate(((330.0, -150.0, 22.0), (360.0, 120.0, 30.0), (240.0, 260.0, 18.0), (-60.0, -330.0, 15.0))):
        rock(mb, "MS_Biorock", (x, y, beach_z(x)+0.3*r), (r, 0.8*r, 0.6*r), 5200+i, n=10)
    k.ucx_pts([(x, y, beach_z(x)) for (x, y) in hexpoly()] + [(x, y, -300.0) for (x, y) in hexpoly()])
    k.socket("SOCKET_Mount_C", (0, 0, beach_z(0.0)))
    k.walk.append((0.0, 0.0, beach_z(0.0)))
    return k

# ----------------------------------------------------------------- D0: LARS pier + Moonpool deck (authored in world cm)
def hexw(q, r): return (CX+2*HA*(q+r/2.0), CY+ROW*r)
P_W = hexpoly(o=hexw(-1, 0)); P_SW = hexpoly(o=hexw(0, -1))
PIER_EDGE_X = -1230.0                                             # boarding edge: DisembarkPoint 130 inside, Shell hull 105 clear
def _pier_points():
    H_, I_, J, P = P_SW[3], P_SW[4], P_SW[5], P_W[0]              # S vertex of W, SW / S vertices of SW, shared vertex W-SW-pool
    sl = (HR/2)/HA                                                # hex edge slope 0.5774
    A = (PIER_EDGE_X, J[1]+sl*(PIER_EDGE_X-J[0])); B = (PIER_EDGE_X, 600.0)
    Cq = (P[0], B[1]+sl*(PIER_EDGE_X-P[0]))
    x = (B[1]-P[1]+sl*(PIER_EDGE_X+P[0]))/(2*sl)                  # line H-P extended meets the stage edge B-C
    Q = (x, P[1]+sl*(x-P[0]))
    return dict(H=H_, I=I_, J=J, A=A, B=B, Q=Q, C=Cq, P=P)
PIER = _pier_points()
PIER_OUTLINE = [PIER[n] for n in ("A", "B", "C")] + [P_W[1], P_W[2], P_W[3], P_W[4]] + [PIER[n] for n in ("H", "I", "J")]
PIER_PLATES = {"W": P_W, "K1": [PIER[n] for n in ("H", "I", "J", "P")], "K2": [PIER[n] for n in ("J", "A", "B", "Q", "P")],
               "K3": [PIER[n] for n in ("P", "Q", "C")]}
PIER_T = 240.0; CANT_T = 30.0                                     # caisson depth; cantilever depth (underside +50 > water +40)

def b_lars_base_deck():
    k = Kit("LARS pier (M-08 base): W cell + SW cell clipped at X -1 230 so the lane stays clear; deck top = arm mount Z (+80), "
            "caissons only west of X -1 500, cantilevered boarding edge, doubler plate under the arm pedestal, console, HPU, rails")
    mb = k.mb
    L = lambda p: (p[0]-ARM[0], p[1]-ARM[1])
    for nm, poly in PIER_PLATES.items():
        prism(mb, "MS_Deck", [L(p) for p in poly], -14.0, 0.0, 1.2)
    for nm in ("W", "K1"):
        prism(mb, "MS_Corten", inset_convex(ccw([L(p) for p in PIER_PLATES[nm]]), 20.0), -PIER_T, -13.0, 2.0)
        k.ucx_prism([L(p) for p in PIER_PLATES[nm]], -PIER_T, 0.0)
    for nm in ("K2", "K3"):
        k.ucx_prism([L(p) for p in PIER_PLATES[nm]], -CANT_T, 0.0)
    ex = PIER_EDGE_X-ARM[0]; xr = -1500.0-ARM[0]
    A, B, Q, Cq, J, I_ = [L(PIER[n]) for n in ("A", "B", "Q", "C", "J", "I")]
    bar(mb, "MS_Corten", (ex-8.0, A[1]+6.0, -22.0), (ex-8.0, B[1]-4.0, -22.0), 14.0, 16.0, c=0.8)             # edge beam
    for yw in (-380.0, -200.0, -20.0, 160.0, 340.0, 500.0):                                                    # knee brackets (above water)
        y = yw-ARM[1]
        chull(mb, "MS_Corten", [(xr-22.0, y+s, -14.0) for s in (-4, 4)] + [(xr-22.0, y+s, -40.0) for s in (-4, 4)] + [(ex-16.0, y+s, -14.0) for s in (-4, 4)])
    for yw in range(-400, 600, 220):                                                                           # rubber fenders
        cbox(mb, "MS_Fender", I, ex-1.0, ex+12.0, yw-ARM[1]-55.0, yw-ARM[1]+55.0, -28.0, -2.0, 3.0)
    cbox(mb, "MS_Hazard", I, ex-34.0, ex-8.0, A[1]+20.0, B[1]-10.0, -0.2, 0.7, 0.2)                           # boarding-edge marking
    prism(mb, "MS_Yellow", [(190.0/math.cos(rad(22.5))*math.cos(rad(22.5+45*i)), 190.0/math.cos(rad(22.5))*math.sin(rad(22.5+45*i))) for i in range(8)], -0.2, 0.8, 0.3)
    for i in range(8):
        a = rad(45.0*i); cyl(mb, "MS_Pipe", (172.0*math.cos(a), 172.0*math.sin(a), 0.6), (172.0*math.cos(a), 172.0*math.sin(a), 4.0), 4.0, 6, c=0.6, smooth=False)
    # control console (T-LARS mount) and hydraulic power unit
    cf = yawfr((-1820.0-ARM[0], 380.0-ARM[1], 0.0), 30.0)
    cbox(mb, "MS_Yellow", cf, -30.0, 30.0, -20.0, 20.0, 0.0, 96.0, 1.5)
    chull(mb, "MS_Trim", [cf.p(x, y, z) for (x, y, z) in ((-30, -20, 96), (30, -20, 96), (30, 20, 96), (-30, 20, 96), (-30, 20, 118), (30, 20, 118), (-30, -14, 100), (30, -14, 100))])
    chull(mb, "MS_Status", [cf.p(x, y, z) for (x, y, z) in ((-24, -11.6, 101.6), (24, -11.6, 101.6), (24, 17.6, 117.2), (-24, 17.6, 117.2), (-24, -12, 102.3), (24, -12, 102.3), (24, 17.2, 117.9), (-24, 17.2, 117.9))])
    k.ucx_pts([cf.p(x, y, z) for x in (-30, 30) for y in (-20, 20) for z in (0, 118)])
    k.socket("SOCKET_Terminal_Mount", cf.p(0, -20, 100), cf.d((0, -1, 0)))
    hf = yawfr((-1880.0-ARM[0], -200.0-ARM[1], 0.0), -30.0)
    cbox(mb, "MS_Yellow", hf, -60.0, 60.0, -35.0, 35.0, 6.0, 90.0, 2.0)
    for sx in (-48.0, 48.0): cbox(mb, "MS_Trim", hf, sx-6.0, sx+6.0, -32.0, 32.0, 0.0, 6.0, 0.6)
    cyl(mb, "MS_Pipe", hf.p(-30.0, 0.0, 90.0), hf.p(-30.0, 0.0, 118.0), 14.0, 12, c=1.5)
    cyl(mb, "MS_Trim", hf.p(25.0, 0.0, 90.0), hf.p(25.0, 0.0, 104.0), 20.0, 12, c=2.0)
    for sy in (-14.0, 14.0):                                                                                    # hydraulic lines to the plinth
        p0 = hf.p(60.0, sy, 20.0); p1 = (148.0*math.cos(rad(230.0+0.5*sy)), 148.0*math.sin(rad(230.0+0.5*sy)), 20.0)
        cyl(mb, "MS_Trim", p0, p1, 3.0, 6, c=0.5)
    k.ucx_pts([hf.p(x, y, z) for x in (-60, 60) for y in (-35, 35) for z in (0, 90)])
    # handrails on the two edges that face the open channel mouth
    for (a, b) in ((I_, J), (J, A)):
        d = (b[0]-a[0], b[1]-a[1]); Ld = math.hypot(*d); d = (d[0]/Ld, d[1]/Ld); n = (-d[1], d[0])       # inward (CCW outline)
        p0 = (a[0]+d[0]*14+n[0]*10, a[1]+d[1]*14+n[1]*10, 0.0); p1 = (b[0]-d[0]*14+n[0]*10, b[1]-d[1]*14+n[1]*10, 0.0)
        handrail(mb, "MS_Yellow", p0, p1)
        fr = axis_fr(p0, vsub(p1, p0)); k.ucx_pts([fr.p(x, y, z) for x in (0.0, vlen(vsub(p1, p0))) for y in (-3.0, 3.0) for z in (0.0, 110.0)])
    for yw in (-390.0, 250.0):                                                                                  # mooring bitts
        for s in (-12.0, 12.0): cyl(mb, "MS_Trim", (ex-70.0, yw-ARM[1]+s, 0.0), (ex-70.0, yw-ARM[1]+s, 24.0), 7.0, 10, c=1.2)
        cbox(mb, "MS_Trim", I, ex-76.0, ex-64.0, yw-ARM[1]-22.0, yw-ARM[1]+22.0, 13.0, 19.0, 1.0)
    k.socket("SOCKET_ArmMount", (0, 0, 0)); k.socket("SOCKET_Disembark", (DISEMBARK[0]-ARM[0], DISEMBARK[1]-ARM[1], 0.0), (math.cos(rad(48)), math.sin(rad(48)), 0))
    k.walk += [(0.0, 230.0, 0.0), (DISEMBARK[0]-ARM[0], DISEMBARK[1]-ARM[1], 0.0), (-331.0, 770.0, 0.0)]
    return k

MOON_CELLS = [(-1, 1), (0, 1), (1, 0)]
MOON_T = 240.0
def b_lars_moonpool():
    k = Kit("M-09 Moonpool deck: three welded hex cells (NW, NE, E) around the open hexagonal pool of cell (0, 0); the pool stays "
            "open to the south (lane) and west (LARS pier). Status strip, hazard band, fenders, ladder, signal mast")
    mb = k.mb
    for (q, r) in MOON_CELLS:
        c = (hexw(q, r)[0]-CX, hexw(q, r)[1]-CY)
        prism(mb, "MS_Deck", hexpoly(HA, 1.5, c), -16.0, 0.0, 1.2)
        prism(mb, "MS_Corten", hexpoly(HA, 6.0, c), -MOON_T, -15.0, 2.0)
        k.ucx_prism(hexpoly(o=c), -MOON_T, 0.0); k.walk.append((c[0], c[1], 0.0))
    C = hexpoly()                                                 # pool outline; edges NW (3->2), NE (2->1), E (1->0)
    for (a, b) in ((C[3], C[2]), (C[2], C[1]), (C[1], C[0])):
        d = (b[0]-a[0], b[1]-a[1]); Ld = math.hypot(*d); d = (d[0]/Ld, d[1]/Ld); n = (d[1], -d[0])           # outward from the pool
        if n[0]*(a[0]+b[0])+n[1]*(a[1]+b[1]) < 0: n = (-n[0], -n[1])
        q0 = lambda off, s: (a[0]+d[0]*s+n[0]*off, a[1]+d[1]*s+n[1]*off)
        p0, p1 = q0(30.0, 30.0), q0(30.0, Ld-30.0); bar(mb, "MS_Status", (p0[0], p0[1], 0.3), (p1[0], p1[1], 0.3), 8.0, 1.4, c=0.3)
        p0, p1 = q0(54.0, 36.0), q0(54.0, Ld-36.0); bar(mb, "MS_Hazard", (p0[0], p0[1], 0.15), (p1[0], p1[1], 0.15), 26.0, 0.9, c=0.2)
        for s in (0.2, 0.5, 0.8):
            p0, p1 = q0(-1.0, s*Ld-55.0), q0(-1.0, s*Ld+55.0); bar(mb, "MS_Fender", (p0[0], p0[1], -30.0), (p1[0], p1[1], -30.0), 14.0, 44.0, c=3.0)
    for sy in (-220.0, -180.0):                                   # boarding ladder on the east wall of the pool
        cyl(mb, "MS_Pipe", (HA-6.0, sy, -190.0), (HA-6.0, sy, 92.0), 2.5, 8, c=0.5)
        cyl(mb, "MS_Pipe", (HA-6.0, sy, 92.0), (HA+34.0, sy, 92.0), 2.5, 8, c=0.5)
        cyl(mb, "MS_Pipe", (HA+34.0, sy, 92.0), (HA+34.0, sy, 0.0), 2.5, 8, c=0.5)
    for z in range(-170, 0, 30): cyl(mb, "MS_Pipe", (HA-6.0, -220.0, z), (HA-6.0, -180.0, z), 1.8, 6, c=0.3)
    mx, my = 0.0, HR+70.0                                         # signal mast behind the north tip of the pool
    cyl(mb, "MS_Trim", (mx, my, 0.0), (mx, my, 290.0), 5.0, 10, c=0.8)
    cbox(mb, "MS_Trim", I, mx-14.0, mx+14.0, my-14.0, my+14.0, 0.0, 4.0, 0.8)
    cyl(mb, "MS_Status", (mx, my, 290.0), (mx, my, 312.0), 9.0, 10, c=2.0)
    k.ucx_box(mx-6.0, mx+6.0, my-6.0, my+6.0, 0.0, 300.0)
    k.socket("SOCKET_Well_Center", (0, 0, 0)); k.socket("SOCKET_Release", (0, 0, -380.0)); k.socket("SOCKET_Light_Well_00", (mx, my, 301.0))
    return k

# ----------------------------------------------------------------- pedestrian network
PATH_W, PATH_L, PATH_T = 400.0, 1200.0, 40.0
HUB_A = 400.0
def b_path_main():
    k = Kit("M-03 arterial deck A400: 400 x 1 200 x 100 (deck 40 on two girders), edge chamfer, luminous edge strips. Long axis = X")
    mb = k.mb
    sec = [(-200.0, -PATH_T), (200.0, -PATH_T), (200.0, -20.0), (180.0, 0.0), (-180.0, 0.0), (-200.0, -20.0)]
    for i in range(3):
        cprism(mb, "MS_Deck", I, sec, -600.0+400.0*i+0.8, -200.0+400.0*i-0.8, 1.5)
    for sy in (-1.0, 1.0):
        cbox(mb, "MS_Lumi", I, -588.0, 588.0, sy*150.0-4.0, sy*150.0+4.0, -0.4, 0.9, 0.3)
        cbox(mb, "MS_Corten", I, -500.0, 500.0, sy*120.0-6.0, sy*120.0+6.0, -100.0, -PATH_T+1.0, 1.0)
    for x in (-400.0, 0.0, 400.0): cbox(mb, "MS_Corten", I, x-5.0, x+5.0, -114.0, 114.0, -92.0, -52.0, 0.8)
    k.ucx_box(-600.0, 600.0, -200.0, 200.0, -PATH_T, 0.0)
    k.socket("SOCKET_Snap_N", (600, 0, 0)); k.socket("SOCKET_Snap_S", (-600, 0, 0), (-1, 0, 0)); k.walk.append((0.0, 0.0, 0.0))
    return k

def b_path_hub():
    k = Kit("M-03 junction plate: hexagon 800 across flats x 40, six A400 decks butt against its sides; luminous hex trace + centre via")
    mb = k.mb
    prism(mb, "MS_Deck", hexpoly(HUB_A), -PATH_T, 0.0, 2.0)
    P = hexpoly(300.0)
    for i in range(6):
        a, b = P[i], P[(i+1) % 6]; bar(mb, "MS_Lumi", (a[0], a[1], 0.3), (b[0], b[1], 0.3), 8.0, 1.4, c=0.3)
    prism(mb, "MS_Yellow", hexpoly(110.0), -0.2, 0.9, 0.3)
    prism(mb, "MS_Trim", hexpoly(60.0), 0.2, 1.5, 0.3)
    k.ucx_prism(hexpoly(HUB_A), -PATH_T, 0.0); k.socket("SOCKET_Mount_C", (0, 0, 0)); k.walk.append((0.0, 0.0, 0.0))
    return k

def b_path_wobbly():
    k = Kit("M-04 scrap bridge 150 x 600 x 30: four patchwork tin sheets on two galvanized pipes. Long axis = X")
    mb = k.mb
    for i, (x0, x1, dy, dz, yaw) in enumerate(((-300.0, -146.0, 3.0, 0.0, 1.5), (-152.0, 2.0, -4.0, -3.2, -2.0), (-4.0, 152.0, 2.0, 0.0, 2.5), (146.0, 300.0, -3.0, -3.2, -1.0))):
        fr = yawfr(((x0+x1)/2, dy, dz), yaw); h = (x1-x0)/2
        cbox(mb, "MS_Tin", fr, -h, h, -72.0, 72.0, -3.0, 0.0, 0.5)
    for sy in (-52.0, 52.0): cyl(mb, "MS_Pipe", (-300.0, sy, -12.0), (300.0, sy, -12.0), 5.5, 8, c=0.8)
    for x in (-210.0, 0.0, 210.0): cyl(mb, "MS_Pipe", (x, -68.0, -23.0), (x, 68.0, -23.0), 4.5, 8, c=0.8)
    k.ucx_box(-300.0, 300.0, -75.0, 75.0, -10.0, 0.0)
    k.socket("SOCKET_Snap_N", (300, 0, 0)); k.socket("SOCKET_Snap_S", (-300, 0, 0), (-1, 0, 0)); k.walk.append((0.0, 0.0, 0.0))
    return k

def b_path_floatnode():
    k = Kit("Floating node 200 x 200 x 120 for the M-04 crossings: tin plate on a pipe frame over two blue drums")
    mb = k.mb
    cbox(mb, "MS_Tin", I, -100.0, 100.0, -100.0, 100.0, -4.0, 0.0, 0.6)
    for s in (-88.0, 88.0):
        cbox(mb, "MS_Corten", I, -96.0, 96.0, s-4.0, s+4.0, -12.0, -4.0, 0.5); cbox(mb, "MS_Corten", I, s-4.0, s+4.0, -96.0, 96.0, -12.0, -4.0, 0.5)
    for sy in (-48.0, 48.0): drum(mb, "MS_Floaters", (-95.0, sy, -66.0), (95.0, sy, -66.0), 50.0)
    k.ucx_box(-100.0, 100.0, -100.0, 100.0, -120.0, 0.0); k.socket("SOCKET_Float_Mid", (0, 0, 0)); k.walk.append((0.0, 0.0, 0.0))
    return k

ROPE_L, ROPE_SAG = 500.0, 30.0
def rope_z(x): u = x/ROPE_L; return -4.0*ROPE_SAG*u*(1.0-u)
def b_path_rope():
    k = Kit("M-07 suspended bridge 140 x 500 x 200, sag 30: 12 planks on rope stringers, rope handrails 110. End A at the pivot, runs +X")
    mb = k.mb; n = 12
    xs = [ROPE_L*(i+0.5)/n for i in range(n)]
    for i, x in enumerate(xs):
        sl = math.degrees(math.atan((rope_z(x+1)-rope_z(x-1))/2.0))
        fr = Fr((x, 0.0, rope_z(x)), (math.cos(rad(sl)), 0.0, math.sin(rad(sl))), (0.0, 1.0, 0.0), (-math.sin(rad(sl)), 0.0, math.cos(rad(sl))))
        cbox(mb, "MS_Plank", fr, -18.5, 18.5, -60.0+(2.0 if i % 3 == 0 else 0.0), 60.0-(3.0 if i % 4 == 1 else 0.0), -4.0, 0.0, 0.5)
    node = [0.0] + xs + [ROPE_L]
    for sy in (-48.0, 48.0):
        for a, b in zip(node[:-1], node[1:]): cyl(mb, "MS_Rope", (a, sy, rope_z(a)-5.5), (b, sy, rope_z(b)-5.5), 2.6, 6, c=0.0)
    for sy in (-66.0, 66.0):
        for a, b in zip(node[:-1], node[1:]): cyl(mb, "MS_Rope", (a, sy, rope_z(a)+110.0), (b, sy, rope_z(b)+110.0), 2.2, 6, c=0.0)
        for x in xs[1::2]: cyl(mb, "MS_Rope", (x, sy, rope_z(x)-4.0), (x, sy, rope_z(x)+110.0), 1.3, 5, c=0.0)
        for x in (5.0, ROPE_L-5.0): cbox(mb, "MS_Plank", I, x-5.0, x+5.0, sy-5.0, sy+5.0, -12.0, 124.0, 0.8)
        k.ucx_box(0.0, ROPE_L, sy-2.5, sy+2.5, -ROPE_SAG, 118.0)
    h = ROPE_L/2
    k.ucx_pts([(0, y, z) for y in (-70, 70) for z in (0, -10)] + [(h, y, z) for y in (-70, 70) for z in (-ROPE_SAG, -ROPE_SAG-10)])
    k.ucx_pts([(h, y, z) for y in (-70, 70) for z in (-ROPE_SAG, -ROPE_SAG-10)] + [(ROPE_L, y, z) for y in (-70, 70) for z in (0, -10)])
    k.socket("SOCKET_Snap_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Snap_B", (ROPE_L, 0, 0)); k.socket("SOCKET_Lantern_00", (h, 66, 80))
    k.walk.append((h, 0.0, -ROPE_SAG))
    return k

# ----------------------------------------------------------------- Flotsam Favelas
def window(mb, axis, face, c0, c1, z0, z1):
    """Warm emissive window, 3.5 proud of a wall plane (axis 0: plane x = face, spans y; axis 1: plane y = face, spans x)."""
    s = 1.0 if face > 0 else -1.0
    def B(mat, d0, d1, a0, a1, zz0, zz1, c):
        lo, hi = min(face+s*d0, face+s*d1), max(face+s*d0, face+s*d1)
        if axis == 0: cbox(mb, mat, I, lo, hi, a0, a1, zz0, zz1, c)
        else: cbox(mb, mat, I, a0, a1, lo, hi, zz0, zz1, c)
    B("MS_Window", -1.0, 3.5, c0, c1, z0, z1, 0.4)
    for (a, b, za, zb) in ((c0-4, c1+4, z0-4, z0), (c0-4, c1+4, z1, z1+4), (c0-4, c0, z0, z1), (c1, c1+4, z0, z1), ((c0+c1)/2-1.5, (c0+c1)/2+1.5, z0, z1)):
        B("MS_Trim", 3.0, 5.5, a, b, za, zb, 0.4)

def door_west(mb, k, xw, t, zt, zl):
    """West wall x = xw (outward -X) with a 90 x 200 door at y = 0: two corrugated panels, lintel, frame, leaf folded back."""
    corr_wall(mb, "MS_Shell", (xw+3.0, 184.0), (xw+3.0, 45.0), (-1.0, 0.0), 22.0, zt, t)
    corr_wall(mb, "MS_Shell", (xw+3.0, -45.0), (xw+3.0, -184.0), (-1.0, 0.0), 22.0, zt, t)
    cbox(mb, "MS_Shell", I, xw, xw+t, -45.0, 45.0, zl, zt, 0.6)
    for (y0, y1, z0, z1) in ((45.0, 49.0, 10.0, zl), (-49.0, -45.0, 10.0, zl), (-49.0, 49.0, zl-4.0, zl)):
        cbox(mb, "MS_Trim", I, xw-1.0, xw+t+2.0, y0, y1, z0, z1, 0.5)
    lf = yawfr((xw-2.0, -47.0, 0.0), 260.0)                      # hinge on the south jamb, leaf swung 170 deg back onto the wall
    cbox(mb, "MS_Door", lf, 0.0, 88.0, -2.0, 2.0, 12.0, zl-5.0, 0.6)
    cbox(mb, "MS_Trim", lf, 70.0, 78.0, -4.5, 4.5, 100.0, 108.0, 0.8)
    k.ucx_box(xw, xw+t, 45.0, 200.0, 0.0, zt+12.0); k.ucx_box(xw, xw+t, -200.0, -45.0, 0.0, zt+12.0); k.ucx_box(xw, xw+t, -45.0, 45.0, zl, zt+12.0)
    k.socket("SOCKET_Door_00", (xw, 0.0, 10.0), (-1, 0, 0))

def frame_box(mb, x0, x1, zb, zt):
    """Container frame: four corner posts, bottom and top rails (y = +/-200)."""
    for x in (x0+8.0, x1-8.0):
        for y in (-192.0, 192.0): cbox(mb, "MS_Trim", I, x-8.0, x+8.0, y-8.0, y+8.0, zb, zt, 1.0)
    for (z0, z1) in ((zb, zb+12.0), (zt-12.0, zt)):
        for y in (-193.0, 193.0): cbox(mb, "MS_Trim", I, x0+16.0, x1-16.0, y-7.0, y+7.0, z0, z1, 0.8)
        for x in (x0+7.0, x1-7.0): cbox(mb, "MS_Trim", I, x-7.0, x+7.0, -184.0, 184.0, z0, z1, 0.8)

BOX = (300.0, 400.0, 300.0)
def b_favela_box_a():
    k = Kit("M-05 container module 300 x 400 x 300: steel frame, corrugated walls 18, door 90 x 200 on -X, two warm windows, walkable roof")
    mb = k.mb; t = 18.0
    cbox(mb, "MS_Trim", I, -150.0, 150.0, -200.0, 200.0, 0.0, 10.0, 0.8)
    frame_box(mb, -150.0, 150.0, 10.0, 280.0)
    corr_wall(mb, "MS_Shell", (147.0, -184.0), (147.0, 184.0), (1.0, 0.0), 22.0, 268.0, t)
    corr_wall(mb, "MS_Shell", (134.0, 197.0), (-134.0, 197.0), (0.0, 1.0), 22.0, 268.0, t)
    corr_wall(mb, "MS_Shell", (-134.0, -197.0), (134.0, -197.0), (0.0, -1.0), 22.0, 268.0, t)
    door_west(mb, k, -150.0, t, 268.0, 210.0)
    cbox(mb, "MS_Shell", I, -150.0, 150.0, -200.0, 200.0, 280.0, 300.0, 1.0)
    window(mb, 0, 147.0, -60.0, 60.0, 140.0, 215.0); window(mb, 1, -197.0, -60.0, 40.0, 150.0, 215.0)
    k.ucx_box(-150, 150, -200, 200, 0, 10); k.ucx_box(-150, 150, -200, 200, 280, 300)
    k.ucx_box(132, 150, -200, 200, 0, 280); k.ucx_box(-150, 150, 182, 200, 0, 280); k.ucx_box(-150, 150, -200, -182, 0, 280)
    k.socket("SOCKET_Stack_Top", (0, 0, 300)); k.socket("SOCKET_Stack_Bottom", (0, 0, 0), (1, 0, 0), (0, 0, 1))
    k.socket("SOCKET_Light_Window_00", (150, 0, 178)); k.socket("SOCKET_Light_Window_01", (0, -200, 182), (0, -1, 0))
    k.walk.append((0.0, 0.0, 300.0))
    return k

TIER = (400.0, 600.0, 350.0)
# ---- M-06 stair + landings (UE-local, stair strip y -300 .. -200). Spiral chain: the stair TOP (landing + roof tab) of a tier is on the same side as the PORCH of the tier above
#      (stack yaw 180), and that porch ends at the entry APRON of the upper stair: landing -> tab -> deck -> porch (north, 100 wide) -> apron -> flight. Z 0 of each tier = roof of the tier below.
ST_KERB = 12.0                                    # entry apron top above the floor: one kerb step (<= 25)
ST_N = 14                                         # treads
ST_APRON = (-200.0, -120.0)                       # flush entry apron 80 deep: open to the porch (north) and to the front (west)
ST_X0, ST_X1 = -120.0, 250.0                      # flight x range (370 long)
ST_LAND = (250.0, 320.0)                          # top landing 70 deep, flush with the roof deck (Z 350)
ST_TAB = (200.0, 320.0, -200.0, -100.0)           # roof tab (x0, x1, y0, y1): cantilevered deck that joins the landing to the roof deck
ST_RISE = (TIER[2]-ST_KERB)/ST_N                  # 24.14 per tread (<= 25)
ST_RUN = (ST_X1-ST_X0)/ST_N                       # 26.43
ST_M = ST_RISE/ST_RUN                             # slope 0.9135 = 42.4 deg (walkable floor angle 44.765)
ST_XR0 = ST_X0-ST_RUN/2.0                         # ramp foot: meets the apron top (z = KERB)
ST_XR1 = ST_X0+ST_RUN*(ST_N-0.5)                  # ramp reaches the deck level (z = 350) here, flat to ST_X1
RAIL_H = 106.0
def st_valley(x): return ST_KERB+ST_M*(x-ST_X0)                    # line through the tread inside corners
def st_floor(x):
    """Collision ramp height: mid line between tread valley and tread nose; the apron top before the flight, deck level after it."""
    if x <= ST_XR0: return ST_KERB
    return min(TIER[2], st_valley(x)+ST_RISE/2.0)

def b_favela_tier_b():
    k = Kit("M-06 stacked unit 400 x 600 x 350 (+120 on +X): room 300 x 400 with a covered porch on -X, exterior stair on the -Y strip: flush entry apron (kerb 12), "
            "14 treads (rise 24.1, 42.4 deg), flat top landing 70 deep flush with the roof (Z 350) + roof tab onto the deck, solid parapets on the open sides; "
            "roof + balcony strip on +Y with handrail. Stack the next tier rotated 180 deg")
    mb = k.mb; t = 18.0; H = TIER[2]
    cbox(mb, "MS_Trim", I, -100.0, 200.0, -200.0, 200.0, 0.0, 10.0, 0.8)
    frame_box(mb, -100.0, 200.0, 10.0, 330.0)
    corr_wall(mb, "MS_Shell", (197.0, -184.0), (197.0, 184.0), (1.0, 0.0), 22.0, 318.0, t)
    corr_wall(mb, "MS_Shell", (184.0, 197.0), (-84.0, 197.0), (0.0, 1.0), 22.0, 318.0, t)
    corr_wall(mb, "MS_Shell", (-84.0, -197.0), (184.0, -197.0), (0.0, -1.0), 22.0, 318.0, t)
    door_west(mb, k, -100.0, t, 318.0, 210.0)
    window(mb, 0, 197.0, -70.0, 70.0, 150.0, 230.0); window(mb, 1, 197.0, 20.0, 130.0, 150.0, 230.0)
    cbox(mb, "MS_Deck", I, -200.0, 200.0, -200.0, 300.0, 330.0, H, 1.2)                                   # roof + balcony slab
    for y in (-192.0, 192.0): cbox(mb, "MS_Trim", I, -197.0, -189.0, y-4.0, y+4.0, 0.0, 330.0, 0.8)        # porch posts
    for x in (-150.0, 20.0, 170.0):                                                                           # balcony brackets
        chull(mb, "MS_Trim", [(x+s, 200.0, 330.0) for s in (-3, 3)] + [(x+s, 294.0, 330.0) for s in (-3, 3)] + [(x+s, 200.0, 250.0) for s in (-3, 3)])
    handrail(mb, "MS_Trim", (-196.0, 296.0, H), (196.0, 296.0, H), step=100.0, post=4.0)
    # ---- stair: entry apron, 14 treads on two stringers, top landing, roof tab, parapets
    ya, yb = -300.0, -200.0
    cbox(mb, "MS_Deck", I, ST_APRON[0], ST_APRON[1], ya, yb, 0.0, ST_KERB, 1.5)                            # flush entry apron (one 12 cm kerb from the floor)
    for y in (-296.0, -204.0):                                                                                # stringers: foot under the first tread, end inside the landing slab
        bar(mb, "MS_Stair", (ST_X0-6.0, y, st_valley(ST_X0-6.0)-14.0), (ST_LAND[0]+8.0, y, st_valley(ST_X1)-14.0), 4.0, 22.0, c=0.6)
    for i in range(ST_N):
        x0 = ST_X0+ST_RUN*i; zt = ST_KERB+ST_RISE*(i+1)
        cbox(mb, "MS_Stair", I, x0, x0+ST_RUN+(1.5 if i < ST_N-1 else 0.0), -294.0, -206.0, zt-4.0, zt, 0.6)
    cbox(mb, "MS_Deck", I, ST_LAND[0], ST_LAND[1], ya, yb, 330.0, H, 1.2)                                  # top landing slab (top = deck level)
    cbox(mb, "MS_Deck", I, ST_TAB[0], ST_TAB[1], ST_TAB[2], ST_TAB[3], 330.0, H, 1.2)                      # roof tab: landing -> deck, no step
    for y in (-185.0, -115.0):                                                                                # tab brackets back to the east wall
        chull(mb, "MS_Trim", [(198.0, y+s, 262.0) for s in (-3, 3)] + [(198.0, y+s, 330.0) for s in (-3, 3)] + [(ST_TAB[1]-14.0, y+s, 330.0) for s in (-3, 3)])
    for y in (-290.0, -210.0):                                                                                # landing brackets down to the flight stringers
        chull(mb, "MS_Trim", [(ST_LAND[1]-8.0, y+s, 330.0) for s in (-3, 3)] + [(ST_X1-30.0, y+s, 296.0) for s in (-3, 3)] + [(ST_LAND[0]+4.0, y+s, 330.0) for s in (-3, 3)])
    xr = ST_LAND[1]-3.0; yo = ya+2.5; yn = ST_TAB[3]-2.5
    cbox(mb, "MS_Trim", I, ST_LAND[1]-5.0, ST_LAND[1], ya, ST_TAB[3], H, H+56.0, 0.6)                      # solid end parapet (x = 320), 56 high
    cbox(mb, "MS_Trim", I, ST_TAB[0], ST_LAND[1]-5.0, ST_TAB[3]-5.0, ST_TAB[3], H, H+56.0, 0.6)             # solid north parapet of the tab
    cbox(mb, "MS_Trim", I, ST_LAND[0], ST_LAND[1]-5.0, ya, ya+5.0, H, H+56.0, 0.6)                          # solid outer parapet of the landing
    handrail(mb, "MS_Trim", (ST_XR0, ya+2.5, st_floor(ST_XR0)), (ST_XR1, ya+2.5, H), h=105.0, step=100.0, post=4.0)          # flight outer rail follows the ramp
    handrail(mb, "MS_Trim", (ST_XR1, yo, H), (xr, yo, H), h=105.0, step=100.0, post=4.0)
    handrail(mb, "MS_Trim", (xr, yo, H), (xr, yn, H), h=105.0, step=100.0, post=4.0)
    handrail(mb, "MS_Trim", (xr, yn, H), (ST_TAB[0]+4.0, yn, H), h=105.0, step=100.0, post=4.0)
    # ---- collision (UCX <= 32 verts): base, apron, continuous ramp, deck, tab, landing, walls, balcony rail, four stair rails
    k.ucx_box(-100, 200, -200, 200, 0, 10)
    k.ucx_box(ST_APRON[0], ST_APRON[1], ya, yb, 0.0, ST_KERB)
    zs2 = st_floor(200.0)                                                                                     # ramp surface at the old tier edge (x = 200)
    k.ucx_pts([(x, y, z) for y in (ya, yb) for (x, z) in ((ST_XR0, 0.0), (ST_XR0, ST_KERB), (200.0, zs2), (200.0, 0.0))])                      # ramp wedge up to the tier edge (ground footprint unchanged), 8 verts
    k.ucx_pts([(x, y, z) for y in (ya, yb) for (x, z) in ((200.0, zs2), (ST_XR1, H), (ST_X1, H), (ST_X1, H-24.0), (200.0, zs2-24.0))])        # thin ramp plate over the overhang (x 200..250): nothing solid down to the floor, 10 verts
    k.ucx_box(-200, 200, -200, 300, 330, H)
    k.ucx_box(ST_TAB[0], ST_TAB[1], ST_TAB[2], ST_TAB[3], 330.0, H)
    k.ucx_box(ST_LAND[0], ST_LAND[1], ya, yb, 330.0, H)
    k.ucx_box(182, 200, -200, 200, 0, 330); k.ucx_box(-100, 200, 182, 200, 0, 330); k.ucx_box(-100, 200, -200, -182, 0, 330)
    k.ucx_box(-200, 200, 293, 299, H, H+110)
    k.ucx_pts([(x, y, z) for y in (ya, ya+5.0) for (x, z) in ((ST_XR0, ST_KERB), (ST_XR0, ST_KERB+RAIL_H), (ST_XR1, H+RAIL_H), (ST_XR1, H))])  # flight outer rail (sloped wall)
    k.ucx_box(ST_XR1, ST_LAND[1], ya, ya+5.0, H, H+RAIL_H)                                                  # landing outer rail
    k.ucx_box(ST_LAND[1]-5.0, ST_LAND[1], ya, ST_TAB[3], H, H+RAIL_H)                                       # end rail (x = 320): nothing walks off the east end
    k.ucx_box(ST_TAB[0], ST_LAND[1], ST_TAB[3]-5.0, ST_TAB[3], H, H+RAIL_H)                                 # tab north rail
    k.socket("SOCKET_Stack_Top", (0, 0, H)); k.socket("SOCKET_Stair_Base", (-160.0, -250.0, ST_KERB), (-1, 0, 0)); k.socket("SOCKET_Stair_Top", (285.0, -250.0, H), (1, 0, 0))
    k.socket("SOCKET_Roof_Tab", (260.0, -150.0, H), (0, 1, 0))
    k.socket("SOCKET_Bridge_W", (-200, BR_Y, H), (-1, 0, 0)); k.socket("SOCKET_Bridge_E", (200, BR_Y, H))
    k.socket("SOCKET_Light_Window_00", (200, 0, 190)); k.socket("SOCKET_Light_Window_01", (75, 200, 190), (0, 1, 0))
    k.walk += [(0.0, 0.0, H), (0.0, 250.0, H), (-160.0, -250.0, ST_KERB), (50.0, -250.0, st_floor(50.0)), (266.0, -250.0, H), (262.0, -165.0, H)]
    return k

def b_market_tent():
    k = Kit("M-13 market stall 400 x 400 x 300: four poles, tie bars, peaked parachute-silk canopy (static), pallet counter 300 x 60 x 100, lantern")
    mb = k.mb; e = 232.0
    for sx in (-185.0, 185.0):
        for sy in (-185.0, 185.0):
            cyl(mb, "MS_Pipe", (sx, sy, 0.0), (sx, sy, e+2.0), 3.5, 8, c=0.6)
            cbox(mb, "MS_Corten", I, sx-9.0, sx+9.0, sy-9.0, sy+9.0, 0.0, 2.5, 0.5); k.ucx_box(sx-4.0, sx+4.0, sy-4.0, sy+4.0, 0.0, e)
    for s in (-185.0, 185.0):
        cyl(mb, "MS_Pipe", (-185.0, s, e-4.0), (185.0, s, e-4.0), 2.5, 6, c=0.0); cyl(mb, "MS_Pipe", (s, -185.0, e-4.0), (s, 185.0, e-4.0), 2.5, 6, c=0.0)
    cyl(mb, "MS_Pipe", (0.0, 0.0, e-4.0), (0.0, 0.0, 296.0), 2.5, 6, c=0.0)
    cyl(mb, "MS_Pipe", (-185.0, 0.0, e-4.0), (185.0, 0.0, e-4.0), 2.0, 6, c=0.0)
    g = [-200.0, -150.0, -100.0, -50.0, 0.0, 50.0, 100.0, 150.0, 200.0]
    def zc(x, y):
        m = max(abs(x), abs(y))/200.0
        return e+2.0+66.0*(1.0-m)**1.25 - 9.0*math.sin(math.pi*m)*(1.0-0.5*abs(abs(x)-abs(y))/200.0)
    sheet(mb, "MS_Canopy", [[(x, y, zc(x, y)) for y in g] for x in g], 1.5)
    cbox(mb, "MS_Plank", I, -150.0, 150.0, 120.0, 180.0, 92.0, 100.0, 0.8)                                 # counter top
    for x0 in (-150.0, -48.0, 54.0):
        cbox(mb, "MS_Plank", I, x0, x0+96.0, 126.0, 174.0, 0.0, 12.0, 0.6); cbox(mb, "MS_Plank", I, x0, x0+96.0, 126.0, 174.0, 78.0, 92.0, 0.6)
        for xx in (x0+2.0, x0+44.0, x0+84.0): cbox(mb, "MS_Plank", I, xx, xx+10.0, 128.0, 172.0, 12.0, 78.0, 0.5)
    cbox(mb, "MS_Plank", I, -170.0, -110.0, -170.0, -120.0, 0.0, 42.0, 0.8); cbox(mb, "MS_Corten", I, -100.0, -52.0, -168.0, -124.0, 0.0, 34.0, 0.8)
    cyl(mb, "MS_Trim", (0.0, 60.0, e-4.0), (0.0, 60.0, 214.0), 0.8, 5, c=0.0)
    cbox(mb, "MS_Trim", I, -7.0, 7.0, 53.0, 67.0, 211.0, 214.0, 0.5); cbox(mb, "MS_Window", I, -5.5, 5.5, 54.5, 65.5, 196.0, 211.0, 1.0)
    k.ucx_box(-150, 150, 120, 180, 0, 100)
    k.socket("SOCKET_Mount_C", (0, 0, 0)); k.socket("SOCKET_Vendor", (0, 60, 0), (0, 1, 0)); k.socket("SOCKET_Light_Lantern_00", (0, 60, 203))
    return k

# ----------------------------------------------------------------- landmarks and infrastructure
VAT_R = 250.0
def b_algae_vat():
    k = Kit("M-10 algae vat D500 x 150: Corten base ring, 8 posts, rim and hoop, opaque luminous liquid (glass wall = SM_Agro_VatGlass)")
    mb = k.mb; Z = zfr()
    ring(mb, "MS_Corten", Z, 0.0, 12.0, 200.0, VAT_R, 24, c=1.0)
    cyl(mb, "MS_Corten", (0, 0, 6.0), (0, 0, 14.0), 242.0, 24, c=0.6)
    lathe(mb, "MS_Liquid", Z, [(14.0, 0.0), (14.0, 235.0), (130.0, 235.0), (133.0, 228.0), (134.5, 0.0)], 24)
    for i in range(8):
        a = rad(45.0*i+22.5); fr = yawfr((244.0*math.cos(a), 244.0*math.sin(a), 0.0), math.degrees(a))
        cbox(mb, "MS_Corten", fr, -4.0, 4.0, -5.0, 5.0, 10.0, 150.0, 0.8)
    ring(mb, "MS_Corten", Z, 138.0, 150.0, 236.0, VAT_R, 24, c=1.0)
    ring(mb, "MS_Corten", Z, 70.0, 76.0, 243.0, VAT_R, 24, c=0.6)
    for a, nm in ((0.0, "In"), (180.0, "Out")):
        d = (math.cos(rad(a)), math.sin(rad(a)), 0.0)
        cyl(mb, "MS_Pipe", vmul(d, 240.0)[:2]+(32.0,), vmul(d, 284.0)[:2]+(32.0,), 9.0, 10, c=0.8)
        cyl(mb, "MS_Pipe", vmul(d, 280.0)[:2]+(32.0,), vmul(d, 286.0)[:2]+(32.0,), 14.0, 10, c=0.8)
        k.socket("SOCKET_Pipe_"+nm, (286.0*d[0], 286.0*d[1], 32.0), d)
    R = VAT_R/math.cos(math.pi/16)
    k.ucx_pts([(R*math.cos(2*math.pi*i/16), R*math.sin(2*math.pi*i/16), z) for i in range(16) for z in (0.0, 150.0)])
    k.socket("SOCKET_Mount_C", (0, 0, 0)); k.socket("SOCKET_Light_00", (0, 0, 140))
    return k

def b_vat_glass():
    k = Kit("M-10 glass wall D486 x 126 (thin translucent, non-Nanite, no collision)", nanite=False)
    ring(k.mb, "MS_Glass", zfr(), 12.0, 138.0, 238.0, 243.0, 24)
    return k

def b_server_desk():
    k = Kit("M-12 salvaged server desk 200 x 100 x 200: rack tower with LED rows and an exposed PCB side, tabletop, CRT terminal")
    mb = k.mb
    cbox(mb, "MS_Chassis", I, -100.0, -28.0, -46.0, 46.0, 0.0, 200.0, 1.5)
    cbox(mb, "MS_Trim", I, -96.0, -32.0, -48.0, -45.0, 8.0, 192.0, 0.6)
    for i in range(12):
        z = 20.0+14.0*i
        cbox(mb, "MS_LED", I, -92.0, -62.0, -48.8, -47.5, z, z+3.0, 0.3)
        if i % 3 != 1: cbox(mb, "MS_LED", I, -52.0, -38.0, -48.8, -47.5, z, z+3.0, 0.3)
    cbox(mb, "MS_PCB", I, -27.8, -27.0, -38.0, 38.0, 90.0, 190.0, 0.2)
    for (y, z, w, h) in ((-22.0, 150.0, 22.0, 22.0), (14.0, 120.0, 30.0, 16.0), (-10.0, 104.0, 14.0, 10.0)):
        cbox(mb, "MS_Trim", I, -27.2, -24.5, y-w/2, y+w/2, z-h/2, z+h/2, 0.5)
    cbox(mb, "MS_Plank", I, -28.0, 100.0, -50.0, 50.0, 72.0, 78.0, 0.8)
    for (x, y) in ((92.0, -42.0), (92.0, 42.0)): cbox(mb, "MS_Trim", I, x-4.0, x+4.0, y-4.0, y+4.0, 0.0, 72.0, 0.6)
    cbox(mb, "MS_Trim", I, -28.0, 96.0, 38.0, 42.0, 30.0, 72.0, 0.6)
    cbox(mb, "MS_Chassis", I, 8.0, 72.0, -6.0, 44.0, 78.0, 130.0, 2.5)                                    # CRT
    cbox(mb, "MS_Screen", I, 14.0, 66.0, -7.0, -5.0, 86.0, 124.0, 0.6)
    cbox(mb, "MS_Chassis", I, 14.0, 66.0, -40.0, -18.0, 78.0, 81.5, 0.8)                                   # keyboard
    cbox(mb, "MS_LED", I, 76.0, 92.0, -30.0, -28.0, 78.0, 80.0, 0.4)
    k.ucx_box(-100, -28, -46, 46, 0, 200); k.ucx_box(-28, 100, -50, 50, 0, 78)
    k.socket("SOCKET_Mount_C", (0, 0, 0)); k.socket("SOCKET_Terminal_Mount", (40, -6, 105), (0, -1, 0)); k.socket("SOCKET_NPC_Stand", (40, -110, 0), (0, -1, 0))
    return k

MAST = (260.0, 400.0)
def b_pneumo_mast():
    k = Kit("M-14 pneumatic-post mast 260 x 260 x 400: octagonal brass shaft with stacking flanges, three neon status rings, hatch on +X")
    mb = k.mb; Z = zfr(); ph = math.pi/8; f = 1.0/math.cos(math.pi/8)
    lathe(mb, "MS_Brass", Z, [(0.0, 0.0), (0.0, 130.0*f), (10.0, 130.0*f), (16.0, 100.0*f), (384.0, 100.0*f), (390.0, 118.0*f), (400.0, 118.0*f), (400.0, 0.0)], 8, smooth=False, phase=ph)
    for z in (88.0, 200.0, 312.0):
        ring(mb, "MS_Neon", Z, z, z+9.0, 96.0*f, 105.0*f, 8, c=0.0, smooth=False, phase=ph)
        for dz in (-5.0, 9.0): ring(mb, "MS_Brass", Z, z+dz, z+dz+5.0, 97.0*f, 108.0*f, 8, c=0.8, smooth=False, phase=ph)
    cbox(mb, "MS_Trim", I, 97.0, 108.0, -36.0, 36.0, 110.0, 186.0, 2.0)
    cyl(mb, "MS_Brass", (107.0, 0.0, 148.0), (112.0, 0.0, 148.0), 26.0, 12, c=1.0)
    cyl(mb, "MS_Neon", (111.0, 0.0, 148.0), (113.5, 0.0, 148.0), 16.0, 12, c=0.4)
    for i in range(8):
        a = rad(45.0*i); cyl(mb, "MS_Pipe", (119.0*math.cos(a), 119.0*math.sin(a), 9.0), (119.0*math.cos(a), 119.0*math.sin(a), 14.0), 4.0, 6, c=0.6, smooth=False)
    k.ucx_pts([(118.0*f*math.cos(ph+2*math.pi*i/8), 118.0*f*math.sin(ph+2*math.pi*i/8), z) for i in range(8) for z in (0.0, 400.0)])
    k.socket("SOCKET_Stack_Top", (0, 0, 400)); k.socket("SOCKET_Hatch", (113, 0, 148)); k.socket("SOCKET_Light_Ring", (0, 0, 204)); k.socket("SOCKET_Landmark_Top", (0, 0, 400))
    return k

def b_wind_gen():
    k = Kit("M-15 wind generator 200 x 200 x 1 000: base plate, tapering Corten lattice tower, nacelle with a fixed three-blade rotor D180, tail vane, obstruction light")
    mb = k.mb; zt = 860.0; b0, b1 = 82.0, 20.0
    cbox(mb, "MS_Corten", I, -100.0, 100.0, -100.0, 100.0, 0.0, 8.0, 1.5)
    leg = lambda sx, sy, z: (sx*(b0+(b1-b0)*(z-8.0)/(zt-8.0)), sy*(b0+(b1-b0)*(z-8.0)/(zt-8.0)), z)
    C4 = ((1, 1), (-1, 1), (-1, -1), (1, -1))
    for (sx, sy) in C4: bar(mb, "MS_Corten", leg(sx, sy, 8.0), leg(sx, sy, zt), 8.0, 8.0, up=(1, 0, 0), c=0.8)
    lv = [8.0, 190.0, 360.0, 520.0, 660.0, 780.0, zt]
    for i, z in enumerate(lv[1:]):
        for j in range(4):
            a, b = C4[j], C4[(j+1) % 4]
            bar(mb, "MS_Corten", leg(a[0], a[1], z), leg(b[0], b[1], z), 5.0, 5.0, c=0.5)
            bar(mb, "MS_Corten", leg(a[0], a[1], lv[i]), leg(b[0], b[1], z), 4.0, 4.0, c=0.4)
    cyl(mb, "MS_Pipe", (0, 0, zt-30.0), (0, 0, 898.0), 9.0, 10, c=1.0)
    cbox(mb, "MS_Trim", I, -34.0, 40.0, -13.0, 13.0, 890.0, 920.0, 3.0)
    cyl(mb, "MS_Rotor", (40.0, 0.0, 905.0), (60.0, 0.0, 905.0), 10.0, 10, c=2.0)
    lathe(mb, "MS_Rotor", axis_fr((60.0, 0.0, 905.0), (1, 0, 0)), [(0.0, 0.0), (0.0, 10.0), (12.0, 4.0), (16.0, 0.0)], 10)
    for i in range(3):
        a = rad(90.0+120.0*i); u = (0.0, math.cos(a), math.sin(a)); w = (0.0, -math.sin(a), math.cos(a))
        P = lambda r, s, x: (50.0+x, r*u[1]+s*w[1], 905.0+r*u[2]+s*w[2])
        chull(mb, "MS_Rotor", [P(6.0, -8.0, -1.5), P(6.0, 8.0, 3.0), P(6.0, -8.0, 1.0), P(6.0, 8.0, 5.5), P(88.0, -3.5, 0.5), P(88.0, 3.5, 1.5), P(88.0, -3.5, 2.0), P(88.0, 3.5, 3.0)])
    cbox(mb, "MS_Tin", I, -84.0, -34.0, -1.0, 1.0, 884.0, 930.0, 0.4)
    cyl(mb, "MS_Beacon", (0.0, 0.0, 920.0), (0.0, 0.0, 932.0), 5.0, 8, c=1.5)
    k.ucx_box(-100, 100, -100, 100, 0, 30)
    k.ucx_pts([(sx*(b0+5.0), sy*(b0+5.0), 8.0) for (sx, sy) in C4] + [(sx*(b1+5.0), sy*(b1+5.0), zt) for (sx, sy) in C4])
    k.socket("SOCKET_Mount_C", (0, 0, 0)); k.socket("SOCKET_Rotor", (50, 0, 905)); k.socket("SOCKET_Light_Obstr", (0, 0, 932))
    return k

# name, Bible id, builder, position in the Max source scene
ASSETS = [
    ("SM_LARS_Moonpool", "M-09", b_lars_moonpool, (0, 0, 0)), ("SM_LARS_Base_Deck", "M-08", b_lars_base_deck, (-669, 770, 0)),
    ("SM_Pontoon_Hex_A", "M-01", b_pontoon_hex_a, (3500, 0, 0)), ("SM_Pontoon_Hex_Biorock", "M-02", b_pontoon_biorock, (4800, 0, 0)),
    ("SM_Agro_Beach", "M-11", b_agro_beach, (6100, 0, 0)),
    ("SM_Path_Main", "M-03", b_path_main, (3500, 1600, 0)), ("SM_Path_Hub", "M-03", b_path_hub, (4800, 1600, 0)),
    ("SM_Path_Wobbly", "M-04", b_path_wobbly, (5800, 1600, 0)), ("SM_Path_FloatNode", "M-04", b_path_floatnode, (6400, 1600, 0)),
    ("SM_Path_Rope", "M-07", b_path_rope, (6800, 1600, 0)),
    ("SM_Favela_Box_A", "M-05", b_favela_box_a, (3500, 2800, 0)), ("SM_Favela_Tier_B", "M-06", b_favela_tier_b, (4300, 2800, 0)),
    ("SM_Market_Tent", "M-13", b_market_tent, (5200, 2800, 0)),
    ("SM_Agro_AlgaeVat", "M-10", b_algae_vat, (3500, 3900, 0)), ("SM_Agro_VatGlass", "M-10", b_vat_glass, (4200, 3900, 0)),
    ("SM_RnD_ServerDesk", "M-12", b_server_desk, (4800, 3900, 0)), ("SM_Pneumo_Mast", "M-14", b_pneumo_mast, (5300, 3900, 0)),
    ("SM_Agro_WindGen", "M-15", b_wind_gen, (5900, 3900, 0)),
]
ASSET_IDX = {a[0]: a for a in ASSETS}

# ================================================================= layout (UE world cm) — single source for the UE script
def cell_xy(q, r): return hexw(q, r)
def hdist(q, r): return max(abs(q), abs(r), abs(q+r))
NB6 = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))        # E, NE, NW, W, SW, SE
def in_hex(px, py, c, a=HA, m=0.0):
    dx, dy = abs(px-c[0]), abs(py-c[1]); a2 = a+m; r2 = a2/math.cos(rad(30.0))
    return dx <= a2+1e-6 and dy <= r2-(r2/2)*dx/a2+1e-6
def hex_hits_rect(c, rc):
    x0, x1, y0, y1 = rc
    if c[0]+HA <= x0 or c[0]-HA >= x1 or c[1]+HR <= y0 or c[1]-HR >= y1: return False
    pts = hexpoly(o=c)+[c]
    for i in range(6):
        a, b = pts[i], pts[(i+1) % 6]
        pts += [(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])) for t in (0.25, 0.5, 0.75)]
    if any(x0 < p[0] < x1 and y0 < p[1] < y1 for p in pts): return True
    return any(in_hex(px, py, c, m=-1e-3) for px in (x0, x1) for py in (y0, y1))

# districts: explicit cell lists (q, r). D0 = dock + ring quay, D1 market (W), D2 R&D (SW), D3 agro (E / SE), D4 favelas (N)
D0_QUAY = [(2, 0), (1, 1), (0, 2), (-1, 2), (-2, 2), (-2, 1), (-2, 0), (-1, -1), (2, -2), (2, -1)]
D1_MARKET = [(-3, 0), (-4, 0), (-3, 1), (-4, 1), (-5, 1), (-5, 0), (-5, 2)]
D2_RND = [(-2, -1), (-2, -2), (-3, -2), (-1, -3), (-2, -3), (0, -4), (-1, -4)]
D3_AGRO = [(3, 0), (4, 0), (3, -1), (4, -1), (3, -2), (4, -2), (3, -3), (4, -3), (3, -4), (4, -4), (5, -4), (4, -5), (5, -5)]
D3_BEACH = [(5, -1), (5, -2), (5, -3)]
D4_FAVELA = [(1, 2), (2, 2), (-4, 3), (-3, 3), (-2, 3), (-1, 3), (0, 3), (1, 3), (-4, 4), (-3, 4), (-2, 4), (-1, 4), (0, 4), (1, 4),
             (-4, 5), (-3, 5), (-2, 5), (-1, 5), (0, 5), (-3, 6), (-2, 6)]
CANALS = {"K-E": [(2, 1), (3, 1)], "K-NW": [(-3, 2), (-4, 2)], "K-SW": [(-3, -1)]}
HUBS = [(-2, 0), (-2, 2), (0, 2), (2, 0), (2, -2), (4, 0), (4, -2), (4, -4), (0, 4), (-4, 4), (-4, 0), (-2, -2)]
HUB_NAMES = {(-2, 0): "J-W", (-2, 2): "J-NW", (0, 2): "J-NE", (2, 0): "J-E", (2, -2): "J-SE", (4, 0): "N3-Agro", (4, -2): "Agro-S", (4, -4): "Agro-SW",
             (0, 4): "N4-Favela", (-4, 4): "Favela-W", (-4, 0): "N1-Market", (-2, -2): "N2-RnD"}
EDGES = [((2, -2), (2, 0), "MG-0"), ((2, 0), (0, 2), "MG-0"), ((0, 2), (-2, 2), "MG-0"), ((-2, 2), (-2, 0), "MG-0"),
         ((2, 0), (4, 0), "MG-3"), ((2, -2), (4, -2), "MG-3"), ((4, 0), (4, -2), "MG-3"), ((4, -2), (4, -4), "MG-3"),
         ((0, 2), (0, 4), "MG-4"), ((-2, 2), (-4, 4), "MG-4"),
         ((-2, 0), (-4, 0), "MG-1"), ((-2, 0), (-2, -2), "MG-2")]
GANGWAY = ((-2, 0), (-1, 0))                                      # J-W -> LARS pier: one deck over the pier's W cell, tip at the pool edge
SC = {"SC-E": ((3, 0), (2, 2)), "SC-NW": ((-3, 1), (-4, 3)), "SC-SW": ((-3, 0), (-3, -2))}   # M-04 crossings: from cell, to cell (through the canal)
SC_LIFT = 10.0                                                    # M-04 deck 10 above D1 (collision slab 10)
PLAYER_START = {"hub": (2, 0), "yaw": 180.0}

def layout():
    cells = {}
    def put(lst, kind, dist):
        for c in lst:
            assert c not in cells, c
            cells[c] = {"kind": kind, "district": dist, "xy": list(cell_xy(*c))}
    put([(0, 0)], "pool", "D0"); put([(-1, 0), (0, -1)], "pier", "D0"); put(MOON_CELLS, "moon", "D0")
    put(D0_QUAY, "M01", "D0"); put(D1_MARKET, "M01", "D1"); put(D2_RND, "M01", "D2"); put(D3_AGRO, "M01", "D3"); put(D3_BEACH, "M11", "D3"); put(D4_FAVELA, "M01", "D4")
    for nm, lst in CANALS.items(): put(lst, "canal", nm)
    built = {c for c, v in cells.items() if v["kind"] in ("M01", "M11", "pier", "moon")}
    # perimeter cells facing open water (not the pool, the lane mouth or a canal) become M-02 Biorock, except over a tower pillar
    for c in sorted(built):
        v = cells[c]
        if v["kind"] != "M01" or c in HUBS: continue
        ocean = [n for n in ((c[0]+d[0], c[1]+d[1]) for d in NB6) if n not in cells]
        lane_side = any(abs(cell_xy(*n)[0]-CX) <= HA+1 and n[1] < 0 for n in ocean) or any(hex_hits_rect(cell_xy(*n), A_FRAME) or hex_hits_rect(cell_xy(*n), A_SHAFT) for n in ocean)
        if len(ocean) >= 2 and not lane_side and hdist(*c) >= 4 and not any(in_hex(px, py, v["xy"], m=120.0) for (px, py) in PILLARS):
            v["kind"] = "M02"
    for c in D3_BEACH:                                           # beach slope faces the open side
        best = max(range(6), key=lambda i: (((c[0]+NB6[i][0], c[1]+NB6[i][1]) not in cells), math.cos(rad(60.0*i)-math.atan2(cells[c]["xy"][1]-CY, cells[c]["xy"][0]-CX))))
        cells[c]["yaw"] = 60.0*best
    return cells

def poly_has(poly, p):
    """Point in convex CCW polygon."""
    n = len(poly)
    return all((poly[(i+1) % n][0]-poly[i][0])*(p[1]-poly[i][1])-(poly[(i+1) % n][1]-poly[i][1])*(p[0]-poly[i][0]) >= -1e-6 for i in range(n))
def on_pier(p): return any(poly_has(ccw(pl), p) for pl in PIER_PLATES.values())

class Site(object):
    """Occupancy helper: where is deck, what is already standing on it."""
    def __init__(s, cells):
        s.cells = cells; s.obst = []                              # obstacles: ("c", x, y, r) or ("r", cx, cy, hx, hy, yaw)
        s.deck = [c for c, v in cells.items() if v["kind"] in ("M01", "M02", "moon")]
    def on_deck(s, p, dist=None, flat_only=True):
        for c in s.deck:
            if (dist is None or s.cells[c]["district"] in dist) and in_hex(p[0], p[1], s.cells[c]["xy"]): return True
        return dist is None and on_pier(p)
    def circ_on_deck(s, x, y, r, dist=None):
        return all(s.on_deck((x+r*math.cos(rad(a)), y+r*math.sin(rad(a))), dist) for a in range(0, 360, 20)) and s.on_deck((x, y), dist)
    def rect_pts(s, cx, cy, hx, hy, yaw, n=3):
        c_, s_ = math.cos(rad(yaw)), math.sin(rad(yaw)); out = []
        for i in range(-n, n+1):
            for j in range(-n, n+1):
                u, v = hx*i/n, hy*j/n; out.append((cx+u*c_-v*s_, cy+u*s_+v*c_))
        return out
    def clear(s, cx, cy, hx, hy, yaw=0.0, margin=0.0):
        P = s.rect_pts(cx, cy, hx+margin, hy+margin, yaw, 4)
        for o in s.obst:
            if o[0] == "c":
                if any(math.hypot(p[0]-o[1], p[1]-o[2]) < o[3] for p in P): return False
            else:
                c_, s_ = math.cos(rad(o[5])), math.sin(rad(o[5]))
                Q = s.rect_pts(o[1], o[2], o[3], o[4], o[5], 4)
                c2, s2 = math.cos(rad(yaw)), math.sin(rad(yaw))
                for p in P:
                    dx, dy = p[0]-o[1], p[1]-o[2]
                    if abs(dx*c_+dy*s_) < o[3] and abs(-dx*s_+dy*c_) < o[4]: return False
                for p in Q:
                    dx, dy = p[0]-cx, p[1]-cy
                    if abs(dx*c2+dy*s2) < hx+margin and abs(-dx*s2+dy*c2) < hy+margin: return False
        return True
    def add_rect(s, cx, cy, hx, hy, yaw=0.0): s.obst.append(("r", cx, cy, hx, hy, yaw))
    def add_circ(s, x, y, r): s.obst.append(("c", x, y, r))

BR_Y = 10.0                                       # M-07 bridge centre line (stack-relative y): rope spans -60..80, clear of the roof tab of a rotated tier (world y 100..200)
FAV_PITCH = (900.0, 800.0)                                        # stack 400 + light well 500; stack 600 + alley 200
T_Z = [Z_D1+TIER[2]*i for i in range(5)]                          # deck, T1 +430, T2 +780, T3 +1 130, T4 +1 480
SHELL_VARIANTS = ["Teal", "Ochre", "Rust", "Sky"]

def assembly():
    cells = layout(); S = Site(cells)
    A = {}                                                        # actor label -> record
    def actor(label, folder, mesh, safe=False, mats=None, cull=0):
        if label not in A: A[label] = {"label": label, "folder": "Environment/Atoll/City/"+folder, "mesh": mesh, "safe_ground": safe, "materials": mats or {}, "instances": [], "cull": cull}
        return A[label]["instances"]
    def inst(lst, x, y, z, yaw=0.0, pitch=0.0): lst.append([round(x, 2), round(y, 2), round(z, 2), round(yaw % 360.0, 3), round(pitch, 3)])
    # ---- D0: dock
    inst(actor("LARS_Base_Deck", "D0_MainframeSocket", "SM_LARS_Base_Deck", True), ARM[0], ARM[1], Z_D1)
    inst(actor("LARS_Moonpool", "D0_MainframeSocket", "SM_LARS_Moonpool", True), CX, CY, Z_D1)
    # ---- foundations
    for c in sorted(cells):
        v = cells[c]; x, y = v["xy"]
        if v["kind"] == "M01": inst(actor("Pontoons_HexA", "Foundations", "SM_Pontoon_Hex_A", True), x, y, Z_D1)
        elif v["kind"] == "M02": inst(actor("Pontoons_Biorock", "Foundations", "SM_Pontoon_Hex_Biorock", True), x, y, Z_D1, 60.0*((c[0]*7+c[1]*3) % 6))
        elif v["kind"] == "M11": inst(actor("Agro_Beach", "D3_AgroSector", "SM_Agro_Beach", True), x, y, Z_D1, v["yaw"])
    # ---- arterials: hubs + one A400 deck between two hubs (2 cells apart), LARS gangway
    hubs = {h: cell_xy(*h) for h in HUBS}; strips = []
    for h, (x, y) in hubs.items():
        inst(actor("Path_Hubs", "Paths", "SM_Path_Hub", True), x, y, Z_D2); S.add_circ(x, y, HUB_A/math.cos(rad(30.0))+40.0)
    for (a, b, mg) in EDGES + [(GANGWAY[0], (GANGWAY[0][0]+2*(GANGWAY[1][0]-GANGWAY[0][0]), GANGWAY[0][1]+2*(GANGWAY[1][1]-GANGWAY[0][1])), "LARS")]:
        pa, pb = cell_xy(*a), cell_xy(*b); mx, my = (pa[0]+pb[0])/2, (pa[1]+pb[1])/2; yaw = math.degrees(math.atan2(pb[1]-pa[1], pb[0]-pa[0]))
        inst(actor("Path_Main", "Paths", "SM_Path_Main", True), mx, my, Z_D2, yaw); S.add_rect(mx, my, PATH_L/2+10.0, PATH_W/2+50.0, yaw)
        strips.append({"a": list(a), "b": list(b), "mid": [mx, my], "yaw": yaw, "class": mg})
    # ---- M-04 crossings: two decks + floating node through the canal
    sc = {}
    for nm, (a, b) in SC.items():
        pa, pb = cell_xy(*a), cell_xy(*b); mx, my = (pa[0]+pb[0])/2, (pa[1]+pb[1])/2; L = math.hypot(pb[0]-pa[0], pb[1]-pa[1]); d = ((pb[0]-pa[0])/L, (pb[1]-pa[1])/L)
        yaw = math.degrees(math.atan2(d[1], d[0]))
        for s in (-300.0, 300.0): inst(actor("Path_Wobbly", "Paths", "SM_Path_Wobbly"), mx+d[0]*s, my+d[1]*s, Z_D1+SC_LIFT, yaw)
        inst(actor("Path_FloatNodes", "Paths", "SM_Path_FloatNode"), mx, my, Z_D1+SC_LIFT-0.5, yaw)
        S.add_rect(mx, my, 600.0, 110.0, yaw)
        sc[nm] = {"from": list(a), "to": list(b), "mid": [mx, my], "yaw": yaw, "ends": [[mx-d[0]*600, my-d[1]*600], [mx+d[0]*600, my+d[1]*600]]}
    # ---- landmarks first (they claim their ground): extraction hubs = 4 stacked M-14
    towers = {"EH-1 Favelas": ((1, 3), (0.0, 0.0)), "EH-2 Market": ((-4, 1), (0.0, 330.0)), "EH-3 RnD": ((-2, -3), (0.0, -60.0))}
    lm = {}
    for nm, (c, off) in towers.items():
        x, y = cell_xy(*c); x += off[0]; y += off[1]
        fold = {"1": "D4_FlotsamFavelas", "2": "D1_SalvageMarket", "3": "D2_RnDSector"}[nm[3]]
        for i in range(4): inst(actor("ExtractionHub_"+nm[:4].replace("-", ""), fold, "SM_Pneumo_Mast"), x, y, Z_D1+MAST[1]*i, 45.0*i)
        S.add_circ(x, y, 190.0); lm[nm] = [x, y, Z_D1+4*MAST[1]]
    # ---- D4 favelas: stacks on a 900 x 800 lattice (light wells 500 wide between stacks, alleys 200 between rows)
    fav = {"D4"}; stacks = []
    fx = [c for c in cells if cells[c]["district"] == "D4"]
    xs = [cells[c]["xy"][0] for c in fx]; ys = [cells[c]["xy"][1] for c in fx]
    def lattice(x0, y0):
        out = []; j = 0; y = y0
        while y < max(ys)+HR:
            gi = 0; x = x0
            while x < max(xs)+HA:
                if all(S.on_deck(p, fav) for p in S.rect_pts(x, y, 200.0, 300.0, 0.0, 3)) and S.clear(x, y, 200.0, 300.0, 0.0, 30.0):
                    b = gi % 2; typ = "S1" if b else ("S1L" if (gi//2+j) % 2 == 0 else "L2")
                    out.append({"i": gi, "j": j, "x": x, "y": y, "b": b, "type": typ, "n": {"S1": 3, "S1L": 4, "L2": 2}[typ], "var": SHELL_VARIANTS[(gi*3+j*5) % 4]})
                x += FAV_PITCH[0]; gi += 1
            y += FAV_PITCH[1]; j += 1
        return out
    def score(st):
        ij = {(t["i"], t["j"]) for t in st}
        return len(st)+0.5*sum(1 for t in st if (t["i"]+1, t["j"]) in ij)
    best = None
    for ox in range(0, 900, 50):
        for oy in range(0, 800, 50):
            st = lattice(min(xs)-HA+ox, min(ys)-HR+oy)
            if best is None or score(st) > score(best): best = st
    stacks = best
    bridges = []
    by = {(s["i"], s["j"]): s for s in stacks}
    for s in stacks:
        S.add_rect(s["x"], s["y"], 200.0, 300.0)
        for m in range(1, s["n"]+1):
            inst(actor("Favela_Tier_B_"+s["var"], "D4_FlotsamFavelas", "SM_Favela_Tier_B", False, {"MS_Shell": "MI_Atoll_Container_"+s["var"]}), s["x"], s["y"], T_Z[m-1], 180.0*((s["b"]+m-1) % 2))
        if s["type"] == "S1":                                   # M-05 cap on the T3 roof, shifted off the porch margin (west for odd stacks), door to the porch
            inst(actor("Favela_Box_A_"+s["var"], "D4_FlotsamFavelas", "SM_Favela_Box_A", False, {"MS_Shell": "MI_Atoll_Container_"+s["var"]}), s["x"]+50.0, s["y"], T_Z[3], 0.0)
        e = by.get((s["i"]+1, s["j"]))
        if not e: continue
        for t in range(1, 5):                                    # free east edge of s / free west edge of e on level T_t
            if s["type"] == "S1" and t == 4: za = T_Z[3]+BOX[2]; fa = True
            else: za = T_Z[t] if t <= s["n"] else None; fa = za is not None and (t == s["n"] or (s["b"]+t) % 2 == 1)
            if e["type"] == "S1" and t == 4: zb = None; fb = False
            else: zb = T_Z[t] if t <= e["n"] else None; fb = zb is not None and (t == e["n"] or (e["b"]+t) % 2 == 0)
            if not (fa and fb) or abs(zb-za) > 50.0: continue
            if s["type"] == "S1" and t == s["n"]: continue        # the cap stands on the east part of that roof
            pitch = math.degrees(math.atan2(zb-za, ROPE_L))
            inst(actor("Path_Rope", "D4_FlotsamFavelas", "SM_Path_Rope"), s["x"]+200.0, s["y"]+BR_Y, za, 0.0, pitch)
            bridges.append({"from": [s["i"], s["j"]], "to": [e["i"], e["j"]], "tier": t, "za": za, "zb": zb, "a": [s["x"]+200.0, s["y"]+BR_Y], "b": [e["x"]-200.0, e["y"]+BR_Y]})
    # ---- single M-05 huts in the leftover favela corners
    huts = 0
    for c in fx:
        cx_, cy_ = cells[c]["xy"]
        for (dx, dy, yaw) in ((-250.0, -330.0, 90.0), (260.0, 330.0, 270.0), (300.0, -200.0, 180.0), (-310.0, 190.0, 0.0)):
            x, y = cx_+dx, cy_+dy; hx, hy = (150.0, 200.0) if yaw % 180 == 0 else (200.0, 150.0)
            if huts < 14 and all(S.on_deck(p, fav) for p in S.rect_pts(x, y, hx+30, hy+30, 0.0, 2)) and S.clear(x, y, hx, hy, 0.0, 110.0):
                var = SHELL_VARIANTS[(huts+1) % 4]
                inst(actor("Favela_Box_A_"+var, "D4_FlotsamFavelas", "SM_Favela_Box_A", False, {"MS_Shell": "MI_Atoll_Container_"+var}), x, y, Z_D1, yaw)
                S.add_rect(x, y, hx, hy); huts += 1
    # ---- D1 market: tents ringing N1 and lining MG-1
    nx, ny = hubs[(-4, 0)]; tents = 0
    cand = [(nx+830.0*math.cos(rad(a)), ny+830.0*math.sin(rad(a)), a+90.0) for a in (60.0, 120.0, 180.0, 240.0, 300.0)]
    for c in D1_MARKET:
        cx_, cy_ = cells[c]["xy"]
        cand += [(cx_-235.0, cy_, 0.0), (cx_+235.0, cy_, 180.0), (cx_, cy_+330.0, 0.0), (cx_, cy_-330.0, 180.0), (cx_, cy_+480.0, 0.0), (cx_-250.0, cy_+250.0, 0.0), (cx_+250.0, cy_-250.0, 180.0)]
    for (x, y, yaw) in cand:
        if tents < 12 and all(S.on_deck(p, {"D1"}) for p in S.rect_pts(x, y, 203.0, 203.0, yaw, 2)) and S.clear(x, y, 200.0, 200.0, yaw, 20.0):
            inst(actor("Market_Tents", "D1_SalvageMarket", "SM_Market_Tent", cull=25000), x, y, Z_D1, yaw); S.add_rect(x, y, 200.0, 200.0, yaw); tents += 1
    crates = 0
    for c in ((-5, 1), (-5, 0), (-3, 1)):
        cx_, cy_ = cells[c]["xy"]
        for (dx, dy, yaw) in ((0.0, 330.0, 90.0), (-300.0, 0.0, 0.0), (0.0, -350.0, 90.0)):
            x, y = cx_+dx, cy_+dy; hx, hy = (150.0, 200.0) if yaw % 180 == 0 else (200.0, 150.0)
            if crates < 4 and all(S.on_deck(p, {"D1"}) for p in S.rect_pts(x, y, hx+20, hy+20, 0.0, 2)) and S.clear(x, y, hx, hy, 0.0, 60.0):
                inst(actor("Market_Containers", "D1_SalvageMarket", "SM_Favela_Box_A", False, {"MS_Shell": "MI_Atoll_Container_Rust"}), x, y, Z_D1, yaw); S.add_rect(x, y, hx, hy); crates += 1
    # ---- D2 R&D: desks facing N2, desk rows, two-high server sheds
    rx, ry = hubs[(-2, -2)]; desks = 0
    cand = [(rx+640.0*math.cos(rad(a)), ry+640.0*math.sin(rad(a)), a-90.0) for a in (0.0, 120.0, 180.0, 240.0, 300.0)]
    for c in ((-3, -2), (-1, -3), (-2, -3), (-2, -1)):
        cx_, cy_ = cells[c]["xy"]
        cand += [(cx_+sx*150.0, cy_+sy*200.0+60.0, 90.0+90.0*sx) for sx in (-1, 1) for sy in (-1, 1)]
    for (x, y, yaw) in cand:
        if all(S.on_deck(p, {"D2"}) for p in S.rect_pts(x, y, 130.0, 150.0, yaw, 2)) and S.clear(x, y, 100.0, 60.0, yaw, 50.0):
            inst(actor("ServerDesks", "D2_RnDSector", "SM_RnD_ServerDesk", cull=25000), x, y, Z_D1, yaw); S.add_rect(x, y, 100.0, 120.0, yaw); desks += 1
    sheds = 0
    for c in ((0, -4), (-1, -4), (-3, -2)):
        cx_, cy_ = cells[c]["xy"]
        for (dx, dy, yaw) in ((-200.0, 150.0, 180.0), (220.0, -120.0, 0.0), (0.0, -340.0, 90.0)):
            x, y = cx_+dx, cy_+dy; hx, hy = (150.0, 200.0) if yaw % 180 == 0 else (200.0, 150.0)
            if sheds < 5 and all(S.on_deck(p, {"D2"}) for p in S.rect_pts(x, y, hx+20, hy+20, 0.0, 2)) and S.clear(x, y, hx, hy, 0.0, 70.0):
                for lv in range(2): inst(actor("RnD_ServerSheds", "D2_RnDSector", "SM_Favela_Box_A", False, {"MS_Shell": "MI_Atoll_Container_Lab"}), x, y, Z_D1+BOX[2]*lv, yaw)
                S.add_rect(x, y, hx, hy); sheds += 1
    # ---- D3 agro: wind generators on the outer side of the cells, then vat triads
    vats = 0; gens = 0; gpos = []
    for c in ((3, 0), (4, -1), (5, -4), (3, -4), (5, -5), (3, -2), (4, -3), (4, -5), (3, -1)):
        cx_, cy_ = cells[c]["xy"]; az = math.atan2(cy_-CY, cx_-CX)
        for (r_, da) in ((380.0, 0.0), (380.0, 60.0), (380.0, -60.0), (0.0, 0.0)):
            x, y = cx_+r_*math.cos(az+rad(da)), cy_+r_*math.sin(az+rad(da))
            if gens < 6 and S.circ_on_deck(x, y, 145.0, {"D3"}) and S.clear(x, y, 100.0, 100.0, 0.0, 45.0) and all(math.hypot(x-g[0], y-g[1]) > 1100.0 for g in gpos):
                inst(actor("WindGenerators", "D3_AgroSector", "SM_Agro_WindGen"), x, y, Z_D1, math.degrees(az)+145.0)
                S.add_circ(x, y, 150.0); gpos.append((x, y)); gens += 1; break
    for c in D3_AGRO:
        cx_, cy_ = cells[c]["xy"]
        if c in HUBS: continue
        for a in (90.0, 210.0, 330.0, 30.0, 150.0, 270.0):
            x, y = cx_+300.0*math.cos(rad(a)), cy_+300.0*math.sin(rad(a))
            if S.on_deck((x, y), {"D3"}) and S.circ_on_deck(x, y, 235.0) and S.clear(x, y, 215.0, 215.0, 0.0, 25.0):
                inst(actor("AlgaeVats", "D3_AgroSector", "SM_Agro_AlgaeVat", cull=25000), x, y, Z_D1, a); inst(actor("AlgaeVat_Glass", "D3_AgroSector", "SM_Agro_VatGlass", cull=25000), x, y, Z_D1, a)
                S.add_circ(x, y, 270.0); vats += 1
    # ---- verification routes (plan polylines; the UE script walks them with floor traces and capsule sweeps)
    H = lambda h: [hubs[h][0], hubs[h][1], Z_D2]
    def toward(a, b, d):
        L = math.hypot(b[0]-a[0], b[1]-a[1]); return [a[0]+(b[0]-a[0])*d/L, a[1]+(b[1]-a[1])*d/L]
    routes = {}
    tip = [cell_xy(-1, 0)[0]+PATH_L/2-60.0, CY, Z_D2]
    routes["main: PlayerStart -> MG-0 north -> J-W -> LARS gangway (boarding)"] = [H((2, 0)), H((0, 2)), H((-2, 2)), H((-2, 0)), tip]
    routes["dock: gangway -> pier deck -> DisembarkPoint -> arm plinth"] = [tip, [-1600.0, 560.0, Z_D1], [DISEMBARK[0], DISEMBARK[1], Z_D1], [-1470.0, 180.0, Z_D1], [-1669.0, 300.0, Z_D1]]
    routes["dock: PlayerStart -> Moonpool deck -> pool edge (E, NE, NW cells)"] = [H((2, 0)), [cell_xy(1, 0)[0]-380.0, CY, Z_D1], [cell_xy(0, 1)[0], cell_xy(0, 1)[1]-380.0, Z_D1], [cell_xy(-1, 1)[0]+200.0, cell_xy(-1, 1)[1]-200.0, Z_D1], H((-2, 2))]
    routes["D3 agro loop: J-E -> N3 -> Agro-S -> J-SE -> J-E, spur to Agro-SW"] = [H((2, 0)), H((4, 0)), H((4, -2)), H((2, -2)), H((2, 0))]
    routes["D3 agro spur + vats + beach"] = [H((4, -2)), H((4, -4)), cells[(5, -4)]["xy"]+[Z_D1], cells[(5, -3)]["xy"]+[Z_D1+beach_z(0.0)], [cells[(5, -3)]["xy"][0]+250.0, cells[(5, -3)]["xy"][1], Z_D1+beach_z(250.0)]]
    routes["D4 favelas: J-NE -> N4, J-NW -> Favela-W"] = [H((0, 4)), H((0, 2)), H((-2, 2)), H((-4, 4))]
    routes["D1 market: J-W -> N1 -> tents"] = [H((-2, 0)), H((-4, 0)), cells[(-5, 0)]["xy"]+[Z_D1], cells[(-5, 1)]["xy"]+[Z_D1], cells[(-4, 1)]["xy"]+[Z_D1], cells[(-3, 1)]["xy"]+[Z_D1]]
    routes["D2 R&D: J-W -> N2 -> desks -> sheds"] = [H((-2, 0)), H((-2, -2)), cells[(-1, -3)]["xy"]+[Z_D1], [cells[(0, -4)]["xy"][0]-380.0, cells[(0, -4)]["xy"][1]+250.0, Z_D1]]
    for nm, v in sc.items():
        a, b = cells[tuple(v["from"])]["xy"], cells[tuple(v["to"])]["xy"]
        routes["%s: M-04 crossing %s -> %s" % (nm, v["from"], v["to"])] = [a+[Z_D1], toward(v["mid"], a, 520.0)+[Z_D1+SC_LIFT], toward(v["mid"], b, 520.0)+[Z_D1+SC_LIFT], b+[Z_D1]]
    def climb(st):
        """Full on-foot ascent, tier by tier along the spiral chain: [front of the apron] -> apron -> flight -> landing -> roof tab -> deck -> porch of the next tier -> its apron -> ..."""
        pts = []
        for m_ in range(1, st["n"]+1):
            c_ = 1.0 if (st["b"]+m_-1) % 2 == 0 else -1.0                  # tier yaw 0 / 180
            z0 = T_Z[m_-1]; Hh = TIER[2]
            L = lambda u, v, dz: [st["x"]+c_*u, st["y"]+c_*v, z0+dz]
            if m_ == 1: pts += [L(-235.0, -250.0, 0.0), L(-190.0, -250.0, ST_KERB)]
            else: pts += [L(-155.0, -250.0, ST_KERB)]
            pts += [L(ST_XR0+6.0, -250.0, ST_KERB), L(-50.0, -250.0, st_floor(-50.0)), L(100.0, -250.0, st_floor(100.0)), L(215.0, -250.0, st_floor(215.0)),
                    L(ST_XR1, -250.0, Hh), L(266.0, -250.0, Hh), L(262.0, -165.0, Hh), L(150.0, -150.0, Hh)]       # landing centre x <= 281: the end rail starts at 315 (capsule R34)
            if m_ < st["n"]: pts += [L(152.0, 0.0, Hh), L(152.0, 150.0, Hh)]
        return pts
    tall = [t for t in stacks if t["type"] == "S1L"]
    if tall: routes["D4 stack climb: deck -> T1 .. T4 (stack %d,%d)" % (tall[0]["i"], tall[0]["j"])] = climb(tall[0])
    odd = [t for t in stacks if t["type"] == "S1"]
    if odd: routes["D4 stack climb: deck -> T1 .. T3 (stack %d,%d, mirrored)" % (odd[0]["i"], odd[0]["j"])] = climb(odd[0])
    for t in (1, 2, 4):
        br = [b for b in bridges if b["tier"] == t]
        if br:
            b = br[0]
            routes["D4 M-07 bridge, tier T%d: stack %s -> %s" % (t, b["from"], b["to"])] = [[b["a"][0]-35.0, b["a"][1], b["za"]], [b["b"][0]+35.0, b["b"][1], b["zb"]]]
    ps = cell_xy(*PLAYER_START["hub"])
    out = {"actors": list(A.values()),
           "player_start": {"loc": [ps[0], ps[1], Z_D2+98.0], "yaw": PLAYER_START["yaw"], "floor_z": Z_D2},
           "cells": {"%d,%d" % c: v for c, v in sorted(cells.items())},
           "hubs": {HUB_NAMES[h]: [hubs[h][0], hubs[h][1], Z_D2] for h in HUBS}, "strips": strips, "sc": sc,
           "stacks": stacks, "bridges": bridges, "landmarks": lm, "routes": routes,
           "counts": {"cells": {k: sum(1 for v in cells.values() if v["kind"] == k) for k in ("M01", "M02", "M11", "pier", "moon", "pool", "canal")},
                      "stacks": len(stacks), "bridges": len(bridges), "huts": huts, "tents": tents, "desks": desks, "sheds": sheds, "vats": vats, "windgens": gens,
                      "instances": {a["label"]: len(a["instances"]) for a in A.values()}}}
    return out

# ================================================================= LARS arm envelope (rig numbers: Tools/SK_LARS_RoboticArm_rig.json, ALARSDockArm.cpp)
RIG = {"collar_z": ARM[2]+30.0, "shoulder": (50.0, 250.0), "boom": 620.0, "fore": 520.0, "eff": 255.0, "berth_reach": 1020.0,
       "hold_z": 500.0, "release_z": -300.0, "retract": (-80.0, 300.0), "stow": (-60.0, 500.0), "pre_capture": 40.0}
# collision shapes on the bones: (name, link, offset along link, half-length, half-width (plan, across the arm), half-height)
ARM_BOXES = [("Boom", "boom", 342.5, 307.5, 54.0, 55.0), ("Forearm", "fore", 248.5, 286.5, 45.0, 38.0), ("TailLever", "fore", -10.0, 40.0, 30.0, 112.0)]
def arm_ik(reach, world_z):
    """Planar 2-link IK of ALARSDockArm::SolveArmIK (elbow up, wrist down): shoulder, elbow, wrist points as (reach, world Z)."""
    S = RIG["shoulder"]; W = (reach, world_z-RIG["collar_z"]+RIG["eff"])
    dx, dz = W[0]-S[0], W[1]-S[1]; dist = min(math.hypot(dx, dz), RIG["boom"]+RIG["fore"]-1.0)
    a = math.atan2(dz, dx); cb = (RIG["boom"]**2+dist**2-RIG["fore"]**2)/(2*RIG["boom"]*dist)
    ba = a+math.acos(max(-1.0, min(1.0, cb)))
    E = (S[0]+RIG["boom"]*math.cos(ba), S[1]+RIG["boom"]*math.sin(ba))
    Z = RIG["collar_z"]
    return (S[0], S[1]+Z), (E[0], E[1]+Z), (W[0], W[1]+Z)
def arm_world(reach, z=None):
    c, s = math.cos(rad(ARM_YAW)), math.sin(rad(ARM_YAW))
    return (ARM[0]+reach*c, ARM[1]+reach*s) if z is None else (ARM[0]+reach*c, ARM[1]+reach*s, z)
def arm_path(n=12):
    """(reach, socket Z, jaw open deg) samples: hold -> release -> retract -> stow, and stow -> pre-capture -> capture -> hold."""
    R = RIG; b = R["berth_reach"]
    key = [(b, R["hold_z"], -9.0), (b, R["release_z"], -9.0), (b, R["release_z"], 30.0), (b+R["retract"][0], R["release_z"]+R["retract"][1], 30.0),
           (b+R["stow"][0], R["stow"][1], 10.0), (b, R["release_z"]+R["pre_capture"], 30.0), (b, R["release_z"], 30.0), (b, R["release_z"], -9.0), (b, R["hold_z"], -9.0)]
    out = []
    for a, c in zip(key[:-1], key[1:]):
        for i in range(n): t = i/float(n); out.append(tuple(a[j]+(c[j]-a[j])*t for j in range(3)))
    out.append(key[-1]); return out
def arm_boxes(reach, z, jaw):
    """World-space boxes of the arm for one pose: (name, centre, x axis, y axis, z axis, half extents)."""
    S, E, W = arm_ik(reach, z); c, s = math.cos(rad(ARM_YAW)), math.sin(rad(ARM_YAW)); out = []
    lat = (-s, c, 0.0)
    for (nm, link, off, hl, hw, hh) in ARM_BOXES:
        p0, p1 = (S, E) if link == "boom" else (E, W)
        L = math.hypot(p1[0]-p0[0], p1[1]-p0[1]); u = ((p1[0]-p0[0])/L, (p1[1]-p0[1])/L)
        ax = (u[0]*c, u[0]*s, u[1]); az = (-u[1]*c, -u[1]*s, u[0])
        r_, zz = p0[0]+u[0]*off, p0[1]+u[1]*off
        out.append((nm, arm_world(r_, zz), ax, lat, az, (hl, hw, hh)))
    bx, by = arm_world(reach)                                     # wrist vertical, gripper turned to the berth heading (-90): jaws open along world X
    out.append(("Gripper", (bx, by, z+175.0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (150.0, 74.0, 80.0)))
    spread = 125.0+90.0*max(0.0, jaw)/30.0
    for sgn, nm in ((-1.0, "JawL"), (1.0, "JawR")):
        out.append((nm, (bx+sgn*spread, by, z+40.0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (21.0+45.0*max(0.0, jaw)/30.0, 70.0, 100.0)))
    return out
SHELL_BOX = ((0.0, 25.0, 53.0), (140.0, 330.0, 177.0))            # Shell-1 mesh bounds about the actor origin at heading -90 (centre offset, half extents)

# ================================================================= spec
def run_builder(name):
    k = ASSET_IDX[name][2]()
    k.slots = [s for s in SLOT_CAT if any(m == s for (_, m, _) in k.mb.f)]
    return k

def asset_record(name, k):
    """Stats in UE-local space (call before mirror_y)."""
    bmin, bmax = k.mb.bbox(); tris = k.mb.tris()
    return {"bible": ASSET_IDX[name][1], "note": k.note, "nanite": k.nanite, "slots": k.slots, "verts": len(k.mb.v), "tris": len(tris), "prims": k.mb.prims,
            "open_edges": k.mb.open_edges(), "bbox_min": [round(c, 2) for c in bmin], "bbox_max": [round(c, 2) for c in bmax],
            "size": [round(bmax[i]-bmin[i], 2) for i in range(3)], "ucx": len(k.ucx), "ucx_max_verts": max([len(h[0]) for h in k.ucx] or [0]),
            "ucx_bbox": [[round(min(p[i] for h in k.ucx for p in h[0]), 2) for i in range(3)], [round(max(p[i] for h in k.ucx for p in h[0]), 2) for i in range(3)]] if k.ucx else None,
            "sockets": k.sock, "walk": [list(w) for w in k.walk], "area_cm2": round(k.mb.area(), 1)}

def spec_dict(records, extra=None):
    d = {"kit": "AOS_DK Atoll Kit (Motherboard City, Stage 1)", "units": "cm",
         "space": "meshes authored in UE-local space; Max scene holds them mirrored in Y (FBX import maps (x, y, z) -> (x, -y, z))",
         "content": "/Game/AOS_DK_Game/Environment/Atoll/Kit", "materials": "/Game/AOS_DK_Game/Environment/Atoll/Materials", "folder": "Environment/Atoll/City",
         "max_file": MAX_PATH, "fbx_dir": FBX_DIR, "uv_tile_cm": TILE,
         "anchors": {"arm": list(ARM), "arm_yaw": ARM_YAW, "disembark": list(DISEMBARK), "berth": list(BERTH), "launch_cam": list(LAUNCH_CAM), "station_a": list(STATION_A),
                     "a_trigger": list(A_TRIGGER), "a_frame": list(A_FRAME), "a_shaft": list(A_SHAFT), "pillars": [list(p) for p in PILLARS], "water_z": WATER_Z,
                     "z_d1": Z_D1, "z_d2": Z_D2, "lane_x": list(LANE), "capsule": list(CAPSULE), "hex": {"origin": [CX, CY], "apothem": HA, "row": ROW}},
         "pier": {"outline": [list(p) for p in PIER_OUTLINE], "plates": {n: [list(p) for p in pl] for n, pl in PIER_PLATES.items()}, "edge_x": PIER_EDGE_X, "caisson_t": PIER_T, "cantilever_t": CANT_T},
         "rig": dict(RIG, boxes=[list(b) for b in ARM_BOXES], shell_box=[list(SHELL_BOX[0]), list(SHELL_BOX[1])]),
         "arm_path": [list(p) for p in arm_path()],
         "tiers_z": T_Z, "sc_lift": SC_LIFT, "meshes": records, "assembly": assembly()}
    if extra: d.update(extra)
    return d

# ================================================================= 3ds Max layer (as in the Deficit / Monoliths kits)
MXS = r'''
global ak_make, ak_uv, ak_mm
fn ak_make verts faces mids sgs evs nm = (
    local m = mesh vertices:verts faces:faces materialIDs:mids
    for i = 1 to faces.count do (
        setFaceSmoothGroup m i sgs[i]
        local e = evs[i]
        setEdgeVis m i 1 ((bit.and e 1) != 0)
        setEdgeVis m i 2 ((bit.and e 2) != 0)
        setEdgeVis m i 3 ((bit.and e 4) != 0)
    )
    update m
    m.name = nm
    m
)
fn ak_uv m tile = (
    local uv = Uvwmap()
    addModifier m uv
    uv.maptype = 4
    uv.length = tile; uv.width = tile; uv.height = tile
    convertTo m Editable_Poly
    m
)
fn ak_mm nm mats nms = (
    local mm = MultiMaterial numsubs:mats.count name:nm
    for i = 1 to mats.count do ( mm.materialList[i] = mats[i]; mm.names[i] = nms[i] )
    mm
)
'''
REF_PFX = "AKREF_"
_MATS = {}
def phys_mat(slot):
    if slot in _MATS and rt.isValidObj(_MATS[slot]): return _MATS[slot]
    col, met, rough, emi = SLOT_CAT[slot]
    m = rt.PhysicalMaterial(name=slot)
    m.base_color = rt.Color(*col); m.metalness = met; m.roughness = rough
    if emi: m.emit_color = rt.Color(*emi); m.emission = 4.0
    if slot == "MS_Glass": m.transparency = 0.8
    _MATS[slot] = m; return m

def is_owned(o, names):
    nm = str(o.name)
    if nm in names: return True
    return any(nm.startswith("UCX_"+n+"_") or nm.startswith(REF_PFX+n+"__") for n in names)

def prepare_scene(names):
    cur = os.path.join(str(rt.maxFilePath), str(rt.maxFileName))
    if os.path.normcase(cur) != os.path.normcase(MAX_PATH):
        allk = set(a[0] for a in ASSETS)
        if [o for o in rt.objects if not is_owned(o, allk)]:
            if rt.getSaveRequired(): raise RuntimeError("Scene %s has unsaved foreign content - save it first; build aborted." % cur)
            rt.resetMaxFile(rt.Name("noPrompt"))
        if os.path.exists(MAX_PATH) and not list(rt.objects): rt.loadMaxFile(MAX_PATH, quiet=True)
    if "centimeter" not in str(rt.units.SystemType).lower() or abs(float(rt.units.SystemScale)-1.0) > 1e-6:
        rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    for o in [o for o in rt.objects if is_owned(o, set(names))]:
        try: rt.delete(o)
        except Exception: pass

def P3(p): return rt.Point3(float(p[0]), float(p[1]), float(p[2]))

def make_node(name, k):
    sid = {s: i+1 for i, s in enumerate(k.slots)}; tris = k.mb.tris()
    node = rt.ak_make([P3(p) for p in k.mb.v], [rt.Point3(t[0]+1, t[1]+1, t[2]+1) for (t, m, g, e) in tris], [sid[m] for (t, m, g, e) in tris],
                      [g for (t, m, g, e) in tris], [e for (t, m, g, e) in tris], name)
    node = rt.ak_uv(node, TILE)
    node.material = phys_mat(k.slots[0]) if len(k.slots) == 1 else rt.ak_mm("MM_"+name, [phys_mat(s) for s in k.slots], list(k.slots))
    return node

def make_ucx(name, k):
    out = []
    for i, (pts, fcs) in enumerate(k.ucx):
        m = rt.mesh(vertices=[P3(p) for p in pts], faces=[rt.Point3(a+1, b+1, c+1) for (a, b, c) in fcs])
        m.name = "UCX_%s_%02d" % (name, i+1); m.wirecolor = rt.Color(255, 60, 60); out.append(m)
    return out

def settle_ui():
    rt.execute("max create mode")
    rt.windows.processPostedMessages(); rt.completeRedraw(); rt.windows.processPostedMessages()

def save_scene():
    d = os.path.dirname(MAX_PATH)
    if not os.path.isdir(d): os.makedirs(d)
    settle_ui()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)

def build(names=None):
    names = list(names) if names else [a[0] for a in ASSETS]
    prepare_scene(names); rt.execute(MXS)
    records = {}
    if os.path.exists(SPEC_PATH):
        try: records = json.load(open(SPEC_PATH, encoding="utf-8")).get("meshes", {})
        except Exception: records = {}
    out = {"max_units": str(rt.units.SystemType), "max_scale": float(rt.units.SystemScale)}
    for name in names:
        k = run_builder(name); rec = asset_record(name, k); k.mirror_y()
        node = make_node(name, k); ucx = make_ucx(name, k)
        for u in ucx:
            nv = int(rt.getNumVerts(u))
            if nv > UCX_MAX: raise RuntimeError("%s has %d verts (> %d)" % (u.name, nv, UCX_MAX))
        tm = rt.transMatrix(P3(ASSET_IDX[name][3])); node.transform = tm
        for u in ucx: u.transform = tm
        lay = rt.LayerManager.getLayerFromName("AK_"+name) or rt.LayerManager.newLayerFromName("AK_"+name)
        lay.addnode(node)
        for u in ucx: lay.addnode(u)
        rl = rt.LayerManager.getLayerFromName("AK_Ref_Sockets") or rt.LayerManager.newLayerFromName("AK_Ref_Sockets")
        for sn, sd in k.sock.items():
            pt = rt.Point(name=REF_PFX+name+"__"+sn, size=10, box=True, cross=True, axistripod=False)
            pt.pos = rt.Point3(sd["pos"][0]+ASSET_IDX[name][3][0], -sd["pos"][1]+ASSET_IDX[name][3][1], sd["pos"][2]+ASSET_IDX[name][3][2]); pt.wirecolor = rt.Color(255, 40, 160); rl.addnode(pt)
        rec["max"] = {"verts": int(rt.polyop.getNumVerts(node)), "polys": int(rt.polyop.getNumFaces(node)), "open_edges": int(rt.polyop.getOpenEdges(node).numberSet),
                      "ucx_nodes": len(ucx), "map_verts": int(rt.polyop.getNumMapVerts(node, 1))}
        records[name] = rec
        out[name] = {"tris": rec["tris"], "polys": rec["max"]["polys"], "open": rec["max"]["open_edges"], "ucx": len(ucx), "size": rec["size"], "slots": len(rec["slots"])}
    with open(SPEC_PATH, "w", encoding="utf-8") as f: json.dump(spec_dict(records, {"max": {"units": out["max_units"], "scale": out["max_scale"]}}), f, indent=1)
    save_scene()
    out["_max_saved"] = os.path.exists(MAX_PATH); out["_dirty"] = bool(rt.getSaveRequired())
    return out

def export(names=None):
    names = list(names) if names else [a[0] for a in ASSETS]
    if not os.path.isdir(FBX_DIR): os.makedirs(FBX_DIR)
    rt.execute('''(
        FBXExporterSetParam "ResetExport"
        FBXExporterSetParam "SmoothingGroups" true
        FBXExporterSetParam "Triangulate" false
        FBXExporterSetParam "Animation" false
        FBXExporterSetParam "Cameras" false
        FBXExporterSetParam "Lights" false
        FBXExporterSetParam "EmbedTextures" false
        FBXExporterSetParam "ConvertUnit" "cm"
        FBXExporterSetParam "UpAxis" "Z"
        FBXExporterSetParam "ASCII" false
    )''')
    res = {}
    for name in names:
        node = rt.getNodeByName(name)
        ucx = [o for o in rt.objects if str(o.name).startswith("UCX_"+name+"_")]
        nodes = [node]+ucx; saved = [n.transform for n in nodes]
        for n in nodes: n.transform = rt.Matrix3(1)
        rt.clearSelection(); rt.select(nodes)
        path = os.path.join(FBX_DIR, name+".fbx")
        ok = rt.exportFile(path, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
        for n, t in zip(nodes, saved): n.transform = t
        res[name] = {"ok": bool(ok), "bytes": os.path.getsize(path) if os.path.exists(path) else 0, "ucx_nodes": len(ucx)}
    rt.clearSelection(); save_scene()
    res["_dirty"] = bool(rt.getSaveRequired())
    return res

GUARD_MXS = r'''
global ak_guard_timer
fn ak_guard_tick s e = (
    s.Stop()
    if (maxFilePath + maxFileName) == @"%s" and getSaveRequired() do
        saveMaxFile (maxFilePath + maxFileName) clearNeedSaveFlag:true useNewFile:true quiet:true
    setSaveRequired false
    dotNet.removeAllEventHandlers s
)
ak_guard_timer = dotNetObject "System.Windows.Forms.Timer"
ak_guard_timer.Interval = 1500
dotNet.addEventHandler ak_guard_timer "Tick" ak_guard_tick
ak_guard_timer.Start()
''' % MAX_PATH
def arm_dirty_guard():
    """Max 2027 re-flags a freshly built scene once its UI idles; a one-shot UI timer re-saves the unchanged scene 1.5 s later."""
    rt.execute(GUARD_MXS)
