# =============================================================================
# AOS-DK | Deficit Kit (Asset Audit 2026-11-10 §5, items 1-13) | 3ds Max 2027, pymxs
# Procedural modular kit: pipes, server racks, cable trays, catwalks, bulkhead, valve, I-beams,
# vent ducts, brutalist concrete arch + stairs.
# Conventions (Spatial Bible 3.0.2): cm, Z-up, UCX_<Mesh>_NN (<= 32 verts), SOCKET_<Name> (X = emission),
# MS_<Slot> material slots in fixed order, Nanite on, chamfered edges, UV ch1 = non-overlapping flatten
# unwrap rescaled to a uniform real-world density (1 UV = TILE cm).
# Pivots sit on the 50/100 grid: pipes/ducts/trays/beams = end-A face centre (pipe: flange face),
# racks/catwalk/stairs = bottom (deck-top) centre, openings = floor centre of the opening on the outer
# wall plane with +X = passage (Bible 3.0.2), movable children = their hinge / rotation axis.
# Max RH -> UE LH on import: (x, y, z) -> (x, -y, z).
# Usage (persisting namespace):
#   ns = {}; exec(open(r"<proj>\Tools\max_build_DeficitKit.py", encoding="utf-8").read(), ns)
#   ns["build"](["SM_Pipe_Straight_D20", ...])  or ns["build"]()  (all)   -> per-asset stats, saves .max
#   ns["export"]()                                                       -> FBX per asset, re-saves .max
# The geometry core (MB + primitives + builders) does not touch pymxs, so it can be unit-tested headless.
# =============================================================================
import math, json, os

try:
    from pymxs import runtime as rt
except Exception:          # headless test
    rt = None

PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
MAX_PATH = os.path.join(PROJ, "SourceArt", "CustomHero", "DeficitKit.max")
FBX_DIR = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "ModularKit")
SPEC_PATH = os.path.join(PROJ, "Tools", "DeficitKit_spec.json")
REF_PFX = "DKREF_"
TILE = 200.0
UCX_MAX = 32

# slot catalogue (Max preview only; UE MIs are authored by ue_import_DeficitKit.py)
SLOT_CAT = {
    "MS_PipePaint":   ((38, 92, 88), 0.2, 0.50, None),
    "MS_DarkSteel":   ((40, 43, 46), 0.6, 0.45, None),
    "MS_Galvanized":  ((150, 152, 155), 1.0, 0.40, None),
    "MS_SafetyPaint": ((222, 160, 20), 0.1, 0.55, None),
    "MS_Rubber":      ((18, 18, 20), 0.0, 0.85, None),
    "MS_Status":      ((0, 0, 0), 0.0, 0.40, (139, 233, 253)),
    "MS_Concrete":    ((128, 126, 120), 0.0, 0.90, None),
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
def axis_fr(o, xdir, zhint=(0.0, 0.0, 1.0)):
    x = vnorm(xdir)
    if abs(vdot(x, zhint)) > 0.99: zhint = (0.0, 1.0, 0.0) if abs(x[1]) < 0.9 else (1.0, 0.0, 0.0)
    y = vnorm(vcross(zhint, x)); z = vcross(x, y)
    return Fr(o, x, y, z)
def shift_fr(off): return Fr(off)

def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i+1) % len(pts)]
        n[0] += (a[1]-b[1])*(a[2]+b[2]); n[1] += (a[2]-b[2])*(a[0]+b[0]); n[2] += (a[0]-b[0])*(a[1]+b[1])
    return tuple(n)

def area2(poly):
    return 0.5*sum(poly[i][0]*poly[(i+1) % len(poly)][1]-poly[(i+1) % len(poly)][0]*poly[i][1] for i in range(len(poly)))

def circ(r, n, phase=0.0):
    return [(r*math.cos(2*math.pi*k/n+phase), r*math.sin(2*math.pi*k/n+phase)) for k in range(n)]
def square(h): return [(h, -h), (h, h), (-h, h), (-h, -h)]          # CCW in (y, z)

# ---------------------------------------------------------------- mesh builder
class MB(object):
    def __init__(s):
        s.v, s.f = [], []        # f: (idx list, slot, sg)
        s._b, s.flips, s.prims = 0, 0, 0
    def av(s, p):
        s.v.append((float(p[0]), float(p[1]), float(p[2]))); return len(s.v)-1
    def poly(s, idx, mat, sg=0, hint=None):
        idx = list(idx)
        u = []
        for i in idx:                                  # drop consecutive duplicates (poles)
            if not u or u[-1] != i: u.append(i)
        if len(u) > 1 and u[0] == u[-1]: u.pop()
        if len(u) < 3: return
        if hint is not None and vdot(newell([s.v[i] for i in u]), hint) < 0: u = u[::-1]
        s.f.append((u, mat, sg))
    def cpoly(s, idx, mat, sg, ref):
        s.poly(idx, mat, sg, vsub(vmid([s.v[i] for i in idx]), ref))
    def begin(s): s._b = len(s.f)
    def end(s):
        """Primitive closed-solid check: negative signed volume => whole primitive inverted -> flip."""
        vol = 0.0
        for (idx, m, g) in s.f[s._b:]:
            p0 = s.v[idx[0]]
            for k in range(1, len(idx)-1):
                vol += vdot(p0, vcross(s.v[idx[k]], s.v[idx[k+1]]))
        if vol < 0:
            s.flips += 1
            s.f[s._b:] = [(idx[::-1], m, g) for (idx, m, g) in s.f[s._b:]]
        s.prims += 1
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
    for a in range(3):                                         # 6 main faces
        b, d = (a+1) % 3, (a+2) % 3
        for sgn in (0, 1):
            loop = []
            for (tb, td) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                k = [0, 0, 0]; k[a], k[b], k[d] = sgn, tb, td; loop.append(V[(a, tuple(k))])
            mb.cpoly(loop, mat, 0, cen)
    for a in range(3):                                         # 12 edge chamfers
        for b in range(a+1, 3):
            t = 3-a-b
            for sa in (0, 1):
                for sb in (0, 1):
                    k0 = [0, 0, 0]; k0[a], k0[b], k0[t] = sa, sb, 0
                    k1 = list(k0); k1[t] = 1
                    mb.cpoly([V[(a, tuple(k0))], V[(a, tuple(k1))], V[(b, tuple(k1))], V[(b, tuple(k0))]], mat, 0, cen)
    for k in corners:                                          # 8 corner triangles
        mb.cpoly([V[(0, k)], V[(1, k)], V[(2, k)]], mat, 0, cen)
    mb.end()

def bar(mb, mat, p0, p1, w, h, up=(0.0, 0.0, 1.0), c=0.3):
    """Chamfered box from p0 to p1 (length axis), w across, h along 'up'."""
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

def ring(mb, mat, fr, t0, t1, r0, r1, sides, c=0.0, smooth=True):
    """Annular ring (tube segment) along fr.x between t0..t1, radii r0 < r1, optional outer chamfer."""
    c = min(c, 0.4*(t1-t0), 0.4*(r1-r0))
    if c > 0.01: prof = [(t0, r0), (t0, r1-c), (t0+c, r1), (t1-c, r1), (t1, r1-c), (t1, r0)]
    else: prof = [(t0, r0), (t0, r1), (t1, r1), (t1, r0)]
    lathe(mb, mat, fr, prof, sides, smooth)

def sweep(mb, mat, frames, outer, inner=None, sg_o=None, sg_i=None, starts_o=None, starts_i=None):
    """Sweep 2D loops (y, z) (CCW, centred on the path) through frames. sg_* : per-edge smoothing (int list or
    single int). starts_*: optional per-vertex x-offset for the FIRST ring (saddle joins)."""
    m = len(outer)
    sgo = sg_o if isinstance(sg_o, list) else [sg_o if sg_o is not None else 1]*m
    def mkring(fr, loop, st):
        return [mb.av(fr.p(st[k] if st else 0.0, loop[k][0], loop[k][1])) for k in range(len(loop))]
    O = [mkring(fr, outer, starts_o if s == 0 else None) for s, fr in enumerate(frames)]
    mb.begin()
    for s in range(len(frames)-1):
        fm = frames[s]
        for k in range(m):
            k2 = (k+1) % m
            hint = fm.d((0.0, (outer[k][0]+outer[k2][0])/2.0, (outer[k][1]+outer[k2][1])/2.0))
            mb.poly([O[s][k], O[s][k2], O[s+1][k2], O[s+1][k]], mat, sgo[k], hint)
    f0, f1 = frames[0], frames[-1]
    if inner:
        mi = len(inner)
        sgi = sg_i if isinstance(sg_i, list) else [sg_i if sg_i is not None else 2]*mi
        Ii = [mkring(fr, inner, starts_i if s == 0 else None) for s, fr in enumerate(frames)]
        for s in range(len(frames)-1):
            fm = frames[s]
            for k in range(mi):
                k2 = (k+1) % mi
                hint = fm.d((0.0, -(inner[k][0]+inner[k2][0])/2.0, -(inner[k][1]+inner[k2][1])/2.0))
                mb.poly([Ii[s][k], Ii[s][k2], Ii[s+1][k2], Ii[s+1][k]], mat, sgi[k], hint)
        assert mi == m
        for k in range(m):
            k2 = (k+1) % m
            mb.poly([O[0][k], O[0][k2], Ii[0][k2], Ii[0][k]], mat, 0, vmul(f0.x, -1.0))
            mb.poly([O[-1][k], O[-1][k2], Ii[-1][k2], Ii[-1][k]], mat, 0, f1.x)
    else:
        mb.poly(O[0], mat, 0, vmul(f0.x, -1.0)); mb.poly(O[-1], mat, 0, f1.x)
    mb.end()

def inset_convex(poly, c):
    """Inset a CCW convex polygon by c (offset edge lines inward, intersect neighbours)."""
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

def cprism(mb, mat, fr, poly, w0, w1, c=0.0, curved=None):
    """Chamfered extrusion of a convex 2D polygon (u, v) along fr.x (w0..w1). curved[i]: edge i is curved."""
    if area2(poly) < 0:
        poly = poly[::-1]
        if curved: curved = (curved[::-1][1:] + curved[::-1][:1])
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
        side = (len(rings) == 2) or s == 1
        for k in range(n):
            k2 = (k+1) % n
            cv = bool(curved and curved[k])
            sg = (1 << 1 if side else 1 << 2) if cv else 0
            mb.cpoly([R[s][k], R[s][k2], R[s+1][k2], R[s+1][k]], mat, sg, cen)
    mb.cpoly(R[0], mat, 0, cen); mb.cpoly(R[-1], mat, 0, cen)
    mb.end()

def holed_plate(mb, mat, fr, rays, closed, T, c, cin=None, cout=None):
    """Plate with an opening, built from rays (O, Op, Ip, I) in 2D (u, v); thickness along fr.x (0..T).
    O outer boundary, Op outer inset by c, Ip opening offset by c (into the solid), I opening boundary."""
    P = lambda uv, w: mb.av(fr.p(w, uv[0], uv[1]))
    ids = []
    for (O, Op, Ip, I_) in rays:
        if c <= 1e-6:
            a, b, e, f = P(O, 0.0), P(O, T), P(I_, 0.0), P(I_, T)
            ids.append(dict(Oa=a, Ob=b, Opa=a, Opb=b, Ipa=e, Ipb=f, Ia=e, Ib=f))
        else:
            ids.append(dict(Oa=P(O, c), Ob=P(O, T-c), Opa=P(Op, 0.0), Opb=P(Op, T), Ipa=P(Ip, 0.0), Ipb=P(Ip, T), Ia=P(I_, c), Ib=P(I_, T-c)))
    nr = len(rays)
    mb.begin()
    for i in (range(nr) if closed else range(nr-1)):
        j = (i+1) % nr; A, B = ids[i], ids[j]
        mu = ((rays[i][1][0]+rays[i][2][0]+rays[j][1][0]+rays[j][2][0])/4.0, (rays[i][1][1]+rays[i][2][1]+rays[j][1][1]+rays[j][2][1])/4.0)
        ref = fr.p(T/2.0, mu[0], mu[1])
        co = bool(cout and cout[i]); ci = bool(cin and cin[i])
        for (q, sg) in (((A['Opa'], B['Opa'], B['Ipa'], A['Ipa']), 0),
                        ((A['Opb'], B['Opb'], B['Ipb'], A['Ipb']), 0),
                        ((A['Oa'], B['Oa'], B['Ob'], A['Ob']), (1 << 1) if co else 0),
                        ((A['Ia'], B['Ia'], B['Ib'], A['Ib']), (1 << 2) if ci else 0),
                        ((A['Oa'], B['Oa'], B['Opa'], A['Opa']), (1 << 3) if co else 0),
                        ((A['Ob'], B['Ob'], B['Opb'], A['Opb']), (1 << 3) if co else 0),
                        ((A['Ia'], B['Ia'], B['Ipa'], A['Ipa']), (1 << 4) if ci else 0),
                        ((A['Ib'], B['Ib'], B['Ipb'], A['Ipb']), (1 << 4) if ci else 0)):
            if len(set(q)) < 4: continue
            mb.cpoly(list(q), mat, sg, ref)
    if not closed:
        for (k, nb) in ((0, 1), (nr-1, nr-2)):
            A = ids[k]
            loop = [A['Oa'], A['Opa'], A['Ipa'], A['Ia'], A['Ib'], A['Ipb'], A['Opb'], A['Ob']]
            loop = [x for i, x in enumerate(loop) if x != loop[i-1]]
            here = vmid([mb.v[i] for i in loop]); there = vmid([mb.v[i] for i in ids[nb].values()])
            mb.poly(loop, mat, 0, vsub(here, there))
    mb.end()

# ---- 2D shape ray casting (convex shapes around a common centre)
def rr_inside(p, u0, u1, v0, v1, r):
    if p[0] < u0 or p[0] > u1 or p[1] < v0 or p[1] > v1: return False
    if r <= 1e-6: return True
    du = max(u0+r-p[0], p[0]-(u1-r), 0.0); dv = max(v0+r-p[1], p[1]-(v1-r), 0.0)
    return du*du+dv*dv <= r*r

def rcast(inside, cen, a, rmax=5000.0):
    d = (math.cos(a), math.sin(a)); lo, hi = 0.0, rmax
    for _ in range(60):
        m = (lo+hi)/2.0
        if inside((cen[0]+d[0]*m, cen[1]+d[1]*m)): lo = m
        else: hi = m
    return (cen[0]+d[0]*lo, cen[1]+d[1]*lo)

def rr_rays(cen, outer, outer_in, inner_in, inner, corner_seg=6):
    """outer/inner: (u0, u1, v0, v1, r) rounded rects; *_in: chamfer-offset versions. Returns rays + flags."""
    angs = set()
    for (u0, u1, v0, v1, r) in (outer, inner):
        for (cu, cv, a0) in ((u1-r, v1-r, 0.0), (u0+r, v1-r, 90.0), (u0+r, v0+r, 180.0), (u1-r, v0+r, 270.0)):
            for k in range(corner_seg+1 if r > 1e-6 else 1):
                a = rad(a0+90.0*k/corner_seg) if r > 1e-6 else None
                pt = (cu+r*math.cos(a), cv+r*math.sin(a)) if r > 1e-6 else (cu, cv)
                angs.add(round(math.atan2(pt[1]-cen[1], pt[0]-cen[0]) % (2*math.pi), 9))
    angs = sorted(a for a in angs if a < 2*math.pi-1e-7)
    f = lambda sh: (lambda p: rr_inside(p, *sh))
    rays = [(rcast(f(outer), cen, a), rcast(f(outer_in), cen, a), rcast(f(inner_in), cen, a), rcast(f(inner), cen, a)) for a in angs]
    def curved(sh, p):
        u0, u1, v0, v1, r = sh
        return r > 1e-6 and (p[0] < u0+r-1e-6 or p[0] > u1-r+1e-6) and (p[1] < v0+r-1e-6 or p[1] > v1-r+1e-6)
    cin, cout = [], []
    for i in range(len(angs)):
        a = (angs[i]+(angs[(i+1) % len(angs)]+(2*math.pi if i == len(angs)-1 else 0)))/2.0
        cin.append(curved(inner, rcast(f(inner), cen, a))); cout.append(curved(outer, rcast(f(outer), cen, a)))
    return rays, cin, cout

def rr_poly(u0, u1, v0, v1, r, seg=6):
    """Rounded rect as CCW polygon + per-edge curved flags."""
    pts, cv = [], []
    for (cu, cvv, a0) in ((u1-r, v0+r, 270.0), (u1-r, v1-r, 0.0), (u0+r, v1-r, 90.0), (u0+r, v0+r, 180.0)):
        for k in range(seg+1):
            a = rad(a0+90.0*k/seg); pts.append((cu+r*math.cos(a), cvv+r*math.sin(a))); cv.append(k < seg)
    return pts, cv

# ---------------------------------------------------------------- collision
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
        for m in range(1, len(idx)-1): faces.append((idx[0], idx[m], idx[m+1]))
        used.update(idx)
    remap = {o: k for k, o in enumerate(sorted(used))}
    return [pts[o] for o in sorted(used)], [(remap[a], remap[b], remap[c]) for (a, b, c) in faces], planes

class Kit(object):
    """Per-asset result container."""
    def __init__(s, slots):
        s.mb = MB(); s.slots = list(slots); s.ucx = []; s.sock = {}; s.probes = []; s.notes = []
    def ucx_pts(s, pts):
        hp, hf, pl = hull3d([tuple(map(float, p)) for p in pts])
        assert len(hp) <= UCX_MAX, "UCX > %d verts (%d)" % (UCX_MAX, len(hp))
        s.ucx.append((hp, hf))
    def ucx_box(s, fr, x0, x1, y0, y1, z0, z1):
        s.ucx_pts([fr.p(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    def ucx_cyl(s, fr, t0, t1, r, n=16):
        R = r/math.cos(math.pi/n)
        s.ucx_pts([fr.p(t, R*math.cos(2*math.pi*k/n), R*math.sin(2*math.pi*k/n)) for t in (t0, t1) for k in range(n)])
    def socket(s, name, pos, x=(1, 0, 0), z=(0, 0, 1)):
        s.sock[name] = {"pos": [round(c, 3) for c in pos], "x": [round(c, 6) for c in vnorm(x)], "z": [round(c, 6) for c in vnorm(z)]}
    def probe(s, name, p0, p1, hit):
        s.probes.append({"name": name, "start": list(p0), "end": list(p1), "expect_hit": hit})

# ---------------------------------------------------------------- 1-4 industrial pipe kit
PIPE = {
    20: dict(od=20.0, t=2.0, fod=34.0, ft=3.0, hub=3.0, hubt=1.0, nb=4, br=1.4, bh=1.2, sides=16),
    40: dict(od=40.0, t=3.0, fod=58.0, ft=4.0, hub=4.0, hubt=1.5, nb=8, br=1.9, bh=1.6, sides=24),
    80: dict(od=80.0, t=4.0, fod=104.0, ft=5.0, hub=6.0, hubt=2.0, nb=12, br=2.6, bh=2.0, sides=32),
}
def pipe_a(D): P = PIPE[D]; return P["ft"]+P["hub"]-0.5      # body starts inside the weld-neck hub

def flange(mb, D, o, inward):
    """Weld-neck flange: face at o (mating plane), body toward 'inward'. Bolts + studs on the back face."""
    P = PIPE[D]; ro = P["od"]/2.0; ri = ro-P["t"]; R = P["fod"]/2.0; ft = P["ft"]; ch = 0.6
    fr = axis_fr(o, inward)
    lathe(mb, "MS_PipePaint", fr, [(0.0, ri), (0.0, R-ch), (ch, R), (ft-ch, R), (ft, R-ch), (ft, ro+P["hubt"]),
                                   (ft+P["hub"], ro+0.15), (ft+P["hub"], ri)], P["sides"])
    rb = (ro+P["hubt"]+R)/2.0
    for k in range(P["nb"]):
        a = 2*math.pi*(k+0.5)/P["nb"]; cy, cz = rb*math.cos(a), rb*math.sin(a)
        cyl(mb, "MS_Galvanized", fr.p(ft-0.05, cy, cz), fr.p(ft+P["bh"], cy, cz), P["br"], 6, c=0.2, smooth=False)
        cyl(mb, "MS_Galvanized", fr.p(ft+P["bh"], cy, cz), fr.p(ft+1.7*P["bh"], cy, cz), 0.55*P["br"], 8, c=0.15)

def b_pipe_straight(D):
    k = Kit(["MS_PipePaint", "MS_Galvanized", "MS_SafetyPaint"]); mb = k.mb
    P = PIPE[D]; L = 400.0; ro = P["od"]/2.0; ri = ro-P["t"]; a = pipe_a(D)
    flange(mb, D, (0, 0, 0), (1, 0, 0)); flange(mb, D, (L, 0, 0), (-1, 0, 0))
    sweep(mb, "MS_PipePaint", [Fr((a, 0, 0)), Fr((L-a, 0, 0))], circ(ro, P["sides"]), circ(ri, P["sides"]))
    for x in (60.0, L-66.0):                                   # line-ID bands
        ring(mb, "MS_SafetyPaint", Fr((x, 0, 0)), 0.0, 6.0, ro-0.5, ro+0.12, P["sides"])
    k.ucx_cyl(I, 0.0, L, ro, 16)
    k.socket("SOCKET_Flange_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Flange_B", (L, 0, 0), (1, 0, 0))
    k.probe("top_hit", (200, 0, 150), (200, 0, -150), True)
    return k

def elbow_path(G, R, a, nseg):
    s = G-R; fr = [axis_fr((a, 0, 0), (1, 0, 0)), axis_fr((s, 0, 0), (1, 0, 0))]
    for i in range(1, nseg+1):
        p = rad(90.0*i/nseg); fr.append(axis_fr((s+R*math.sin(p), R-R*math.cos(p), 0), (math.cos(p), math.sin(p), 0)))
    fr.append(axis_fr((G, G-a, 0), (0, 1, 0)))
    return fr
def elbow_station(G, R, phi):
    s = G-R; p = rad(phi); return axis_fr((s+R*math.sin(p), R-R*math.cos(p), 0), (math.cos(p), math.sin(p), 0))

def b_pipe_elbow(D, G):
    k = Kit(["MS_PipePaint", "MS_Galvanized"]); mb = k.mb
    P = PIPE[D]; ro = P["od"]/2.0; ri = ro-P["t"]; R = 1.5*D; a = pipe_a(D)
    sweep(mb, "MS_PipePaint", elbow_path(G, R, a, 12 if D < 60 else 16), circ(ro, P["sides"]), circ(ri, P["sides"]))
    flange(mb, D, (0, 0, 0), (1, 0, 0)); flange(mb, D, (G, G, 0), (0, -1, 0))
    n = 8; Rc = ro/math.cos(math.pi/n)
    ringpts = lambda fr: [fr.p(0, Rc*math.cos(2*math.pi*j/n), Rc*math.sin(2*math.pi*j/n)) for j in range(n)]
    st1 = [axis_fr((0, 0, 0), (1, 0, 0)), elbow_station(G, R, 0.0), elbow_station(G, R, 22.5), elbow_station(G, R, 45.0)]
    st2 = [elbow_station(G, R, 45.0), elbow_station(G, R, 67.5), elbow_station(G, R, 90.0), axis_fr((G, G, 0), (0, 1, 0))]
    k.ucx_pts(sum([ringpts(f) for f in st1], [])); k.ucx_pts(sum([ringpts(f) for f in st2], []))
    k.socket("SOCKET_Flange_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Flange_B", (G, G, 0), (0, 1, 0))
    k.probe("stub_a_top", (G/4.0, 0, 200), (G/4.0, 0, -200), True)
    k.probe("inner_corner_clear", (G*0.15, G*0.85, 200), (G*0.15, G*0.85, -200), False)
    k.notes.append("R = 1.5 x D (%d cm) + tangent stubs %d cm so both flange faces land on the %d grid; 2 UCX (8-gon x 4 stations) instead of 1 to keep the bend's inner corner open" % (R, G-R, G))
    return k

def b_pipe_tee(D=40, G=100.0):
    k = Kit(["MS_PipePaint", "MS_Galvanized"]); mb = k.mb
    P = PIPE[D]; ro = P["od"]/2.0; ri = ro-P["t"]; a = pipe_a(D); n = P["sides"]; L = 2*G
    flange(mb, D, (0, 0, 0), (1, 0, 0)); flange(mb, D, (L, 0, 0), (-1, 0, 0)); flange(mb, D, (G, G, 0), (0, -1, 0))
    sweep(mb, "MS_PipePaint", [Fr((a, 0, 0)), Fr((L-a, 0, 0))], circ(ro, n), circ(ri, n))
    fb0 = axis_fr((G, 0, 0), (0, 1, 0)); fb1 = axis_fr((G, G-a, 0), (0, 1, 0))
    co, ci = circ(ro, n), circ(ri, n)
    st_o = [math.sqrt(max(ro*ro-(p[1])**2, 0.0))-0.3 for p in co]       # saddle on the run cylinder
    st_i = [math.sqrt(max(ro*ro-(p[1])**2, 0.0))-0.3 for p in ci]
    sweep(mb, "MS_PipePaint", [fb0, fb1], co, ci, starts_o=st_o, starts_i=st_i)
    k.ucx_cyl(I, 0.0, L, ro, 16); k.ucx_cyl(fb0, 0.0, G, ro, 16)
    k.socket("SOCKET_Flange_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Flange_B", (L, 0, 0), (1, 0, 0))
    k.socket("SOCKET_Flange_C", (G, G, 0), (0, 1, 0))
    k.probe("run_top", (G/2, 0, 200), (G/2, 0, -200), True); k.probe("branch_top", (G, G*0.7, 200), (G, G*0.7, -200), True)
    k.notes.append("Run 200 / branch face at Y 100 (grid) instead of the audit's ~160 x 80 envelope")
    return k

def b_pipe_reducer():
    k = Kit(["MS_PipePaint", "MS_Galvanized"]); mb = k.mb
    L = 150.0; A, B = PIPE[80], PIPE[40]; aA, aB = pipe_a(80), pipe_a(40)
    flange(mb, 80, (0, 0, 0), (1, 0, 0)); flange(mb, 40, (L, 0, 0), (-1, 0, 0))
    roA, riA, roB, riB = 40.0, 36.0, 20.0, 17.0
    lathe(mb, "MS_PipePaint", I, [(aA, riA), (aA, roA), (50.0, roA), (100.0, roB), (L-aB, roB), (L-aB, riB), (100.0, riB), (52.0, riA)], 32)
    n = 10; RA, RB = roA/math.cos(math.pi/n), roB/math.cos(math.pi/n)
    pts = [(t, R*math.cos(2*math.pi*j/n), R*math.sin(2*math.pi*j/n)) for (t, R) in ((0.0, RA), (50.0, RA), (L, RB)) for j in range(n)]
    k.ucx_pts(pts)
    k.socket("SOCKET_Flange_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Flange_B", (L, 0, 0), (1, 0, 0))
    k.probe("big_end_top", (25, 0, 150), (25, 0, -150), True)
    k.notes.append("Length 150 (grid) for the audit's ~160")
    return k

def b_clamp(D):
    k = Kit(["MS_Galvanized", "MS_Rubber"]); mb = k.mb
    sc = {20: (0.8, 4.0, 4.0, 1.2, 6.0, 0.6), 40: (1.0, 5.0, 5.0, 1.6, 7.0, 0.8), 80: (1.2, 6.0, 6.0, 2.0, 9.0, 1.0)}[D]
    tb, wb, le, rr, hp, bolt = sc
    rp = D/2.0; ro = rp+0.2; nside = PIPE[D]["sides"]+8
    fr = Fr((-wb/2.0, 0, 0))
    ring(mb, "MS_Rubber", fr, 0.3, wb-0.3, rp+0.02, ro+0.05, nside)                # liner
    ring(mb, "MS_Galvanized", fr, 0.0, wb, ro, ro+tb, nside, c=0.2)                 # band
    for sy in (-1.0, 1.0):                                                            # ears + bolts
        for sz in (-1.0, 1.0):
            cbox(mb, "MS_Galvanized", I, -wb/2, wb/2, sy*(ro+tb*0.5), sy*(ro+tb+le), sz*0.3, sz*(0.3+tb), 0.15)
        yb = sy*(ro+tb+le/2.0)
        cyl(mb, "MS_Galvanized", (0, yb, -(0.3+tb+1.6*bolt)), (0, yb, 0.3+tb+1.6*bolt), bolt*0.6, 8, c=0.1)
        for sz in (-1.0, 1.0):
            cyl(mb, "MS_Galvanized", (0, yb, sz*(0.3+tb)), (0, yb, sz*(0.3+tb+bolt*1.2)), bolt*1.25, 6, c=0.15, smooth=False)
    zt = ro+tb; zb = zt+2.0; rod = 15.0; ztop = zb+rod+1.0
    cbox(mb, "MS_Galvanized", I, -wb/2, wb/2, -1.8, 1.8, zt-0.6, zb, 0.2)              # welded boss
    cyl(mb, "MS_Galvanized", (0, 0, zb-0.5), (0, 0, ztop-0.5), rr/2.0, 12, c=0.1)       # threaded rod
    for z in (zb, ztop-1.0-rr*1.4):
        cyl(mb, "MS_Galvanized", (0, 0, z), (0, 0, z+rr*1.2), rr*1.0, 6, c=0.15, smooth=False)   # nuts
    cbox(mb, "MS_Galvanized", I, -hp, hp, -hp, hp, ztop-1.0, ztop, 0.25)                # ceiling / wall plate
    for sx in (-1.0, 1.0):
        cyl(mb, "MS_Galvanized", (sx*hp*0.6, sx*hp*0.6, ztop-1.0), (sx*hp*0.6, sx*hp*0.6, ztop-1.6), 0.8+0.1*bolt, 6, c=0.1, smooth=False)
    Y = ro+tb+le; Z = ro+tb
    k.ucx_pts([(x, y, z) for x in (-wb/2, wb/2) for y in (-Y, Y) for z in (-Z, Z)] + [(x, y, ztop) for x in (-hp, hp) for y in (-hp, hp)])
    k.socket("SOCKET_Mount", (0, 0, ztop), (0, 0, 1), (1, 0, 0))
    k.probe("plate_hit", (0, 0, ztop+50), (0, 0, 0), True)
    k.notes.append("Pivot on the pipe axis; plate at Z %.1f (ceiling). Rotate 90 deg about X for wall mounting. Pipe runs along X, so the 30 cm span is along Y" % ztop)
    return k

# ---------------------------------------------------------------- 5-6 server racks
U_H = 4.445
RACK_LAYOUT = [(2, "ups"), (4, "storage"), (4, "storage"), (1, "blank"), (4, "gpu"), (4, "gpu"), (2, "srv2"), (2, "srv2"),
               (2, "srv2"), (2, "srv2"), (2, "srv2"), (2, "blank"), (1, "srv1"), (1, "srv1"), (1, "srv1"), (1, "srv1"),
               (1, "blank"), (1, "switch"), (1, "switch"), (1, "patch"), (3, "blank")]

def rack_device(mb, kind, z0, h, rnd):
    D, G, S, R = "MS_DarkSteel", "MS_Galvanized", "MS_Status", "MS_Rubber"
    yf = -44.2
    cbox(mb, D, I, -21.8, 21.8, -43.0, 30.0, z0+0.2, z0+h-0.2, 0.2)                    # chassis
    cbox(mb, G if kind in ("blank", "patch") else D, I, -24.1, 24.1, yf, -43.0, z0+0.1, z0+h-0.1, 0.25)   # front plate + ears
    for sx in (-1.0, 1.0):                                                             # rack screws
        cyl(mb, G, (sx*23.0, yf, z0+h/2.0), (sx*23.0, yf-0.35, z0+h/2.0), 0.45, 8, c=0.08)
    def box(m, x0, x1, za, zb, d=0.5): cbox(mb, m, I, x0, x1, yf-d, yf, za, zb, 0.0)
    if kind == "srv1":
        for i in range(4): box(D if i % 2 else R, -20.0+i*7.2, -14.0+i*7.2, z0+0.8, z0+h-0.8, 0.6)
        box(S, 14.0, 15.0, z0+1.6, z0+2.6, 0.7); box(S, 16.5, 17.5, z0+1.6, z0+2.6, 0.7)
    elif kind in ("srv2", "storage"):
        rows = 1 if kind == "srv2" else 3; cols = 8 if kind == "srv2" else 12; wcad = 3.4
        hh = (h-1.2)/rows
        for r_ in range(rows):
            for c_ in range(cols):
                x0 = -20.5+c_*(wcad+0.25); za = z0+0.6+r_*hh
                box(R, x0, x0+wcad, za+0.15, za+hh-0.15, 0.5)
                if rnd() > 0.15: box(S, x0+0.4, x0+1.2, za+hh-1.3, za+hh-0.7, 0.62)
        if kind == "srv2":
            for i in range(6): box(D, 12.0, 21.0, z0+0.9+i*1.2, z0+1.5+i*1.2, 0.35)
            box(S, 21.6, 22.6, z0+h-2.0, z0+h-1.2, 0.6)
    elif kind == "gpu":
        for i in range(10): box(D, -19.0, 19.0, z0+1.2+i*1.5, z0+1.9+i*1.5, 0.45)
        for sx in (-1.0, 1.0): cbox(mb, G, I, sx*20.0-0.6, sx*20.0+0.6, yf-3.0, yf, z0+3.0, z0+h-3.0, 0.2)
        box(S, -19.0, 19.0, z0+h-1.4, z0+h-1.0, 0.5)
    elif kind in ("switch", "patch"):
        for r_ in range(2):
            for c_ in range(12):
                x0 = -19.0+c_*2.6 + (2.0 if c_ >= 6 else 0.0)
                box(R, x0, x0+1.6, z0+0.6+r_*1.75, z0+1.9+r_*1.75, 0.25)
                if kind == "switch" and rnd() > 0.3: box(S, x0+0.2, x0+0.6, z0+0.35+r_*3.2, z0+0.55+r_*3.2, 0.3)
        if kind == "switch": box(S, 17.5, 18.5, z0+1.6, z0+2.6, 0.5)
    elif kind == "ups":
        box(S, -18.0, -8.0, z0+3.0, z0+6.5, 0.4)
        for i in range(5): box(D, 0.0, 20.0, z0+1.0+i*1.4, z0+1.6+i*1.4, 0.4)

def lcg(seed):
    st = [seed]
    def r():
        st[0] = (1103515245*st[0]+12345) & 0x7fffffff; return st[0]/float(0x7fffffff)
    return r

def b_rack_cabinet():
    k = Kit(["MS_DarkSteel", "MS_Galvanized", "MS_Rubber", "MS_Status"]); mb = k.mb
    D, G, S = "MS_DarkSteel", "MS_Galvanized", "MS_Status"
    cbox(mb, D, I, -38, 38, -46, 48, 0, 8, 0.5)                                         # plinth
    cbox(mb, D, I, -40, 40, -50, 50, 212, 220, 0.8)                                     # top cap
    for sx in (-1.0, 1.0):
        cbox(mb, D, I, sx*38, sx*40, -50, 50, 8, 212, 0.4)                              # side panels
        cbox(mb, D, I, sx*34, sx*38, -50, -46, 8, 212, 0.3)                              # front stiles
        for (y0, y1) in ((-43.0, -41.0), (39.0, 41.0)):
            cbox(mb, G, I, sx*23.8, sx*25.8, y0, y1, 11, 199, 0.2)                      # 19" rails
    cbox(mb, D, I, -38, 38, 48, 50, 8, 212, 0.3)                                        # rear panel
    cbox(mb, D, I, -34, 34, -49.5, -46, 199, 212, 0.4)                                  # LED header
    cbox(mb, D, I, -34, 34, -50, -46, 8, 11, 0.3)                                       # bottom rail
    for i in range(6):
        x = -25.0+10.0*i; z = 205.5
        cyl(mb, D, (x, -49.5, z), (x, -49.9, z), 1.5, 12, c=0.15)
        cyl(mb, S, (x, -49.9, z), (x, -50.0, z), 0.9, 10, c=0.04)
        k.socket("SOCKET_Status_%02d" % i, (x, -50.0, z), (0, -1, 0), (0, 0, 1))
    rnd = lcg(42); z = 12.0
    for (u, kind) in RACK_LAYOUT:
        rack_device(mb, kind, z, u*U_H, rnd); z += u*U_H
    k.ucx_box(I, -40, 40, -50, 50, 0, 220)
    k.socket("SOCKET_Door_Hinge", (-40.0, -51.25, 0.0))
    k.probe("top_hit", (0, 0, 400), (0, 0, 0), True)
    k.notes.append("42U = %.1f cm of rail (Z 12-198.7); front faces Max -Y (= UE +Y); door is the separate SM_ServerRack_Cabinet_Door on SOCKET_Door_Hinge" % (42*U_H))
    return k

def b_rack_door():
    k = Kit(["MS_DarkSteel", "MS_Galvanized"]); mb = k.mb
    D, G = "MS_DarkSteel", "MS_Galvanized"
    F = shift_fr((40.0, 51.25, 0.0))                     # cabinet coords -> hinge-local
    yb0, yb1 = -52.5, -50.2
    cbox(mb, D, F, -39.5, -35.5, yb0, yb1, 9, 198, 0.3); cbox(mb, D, F, 35.5, 39.5, yb0, yb1, 9, 198, 0.3)
    cbox(mb, D, F, -35.5, 35.5, yb0, yb1, 194, 198, 0.3); cbox(mb, D, F, -35.5, 35.5, yb0, yb1, 9, 13, 0.3)
    x = -35.0
    while x < 35.0:                                       # perforated field (by geometry, no masked)
        cbox(mb, D, F, x, x+0.9, -51.8, -50.9, 13, 194, 0.0); x += 2.4
    z = 14.0
    while z < 194.0:
        cbox(mb, D, F, -35.5, 35.5, -52.1, -51.3, z, z+0.9, 0.0); z += 2.4
    cbox(mb, G, F, 36.0, 37.2, -55.0, yb0, 95, 125, 0.3)                                  # handle
    for zz in (93.0, 125.0): cbox(mb, G, F, 35.8, 37.4, -55.0, yb0, zz, zz+2.0, 0.3)
    for (z0, z1) in ((30.0, 40.0), (165.0, 175.0)):                                        # hinges
        cyl(mb, G, (0.0, 0.0, z0), (0.0, 0.0, z1), 1.2, 12, c=0.15)
        cbox(mb, G, F, -40.0, -37.0, -52.4, -50.3, z0+1.0, z1-1.0, 0.2)
    k.ucx_box(F, -40.5, 39.5, -55.0, -50.2, 9, 198)
    k.probe("leaf_hit", (40, -100, 100), (40, 100, 100), True)
    k.notes.append("Pivot = hinge axis (Z up); attach to SM_ServerRack_Cabinet:SOCKET_Door_Hinge with zero rotation")
    return k

def b_rack_mega():
    k = Kit(["MS_DarkSteel", "MS_Galvanized", "MS_PipePaint", "MS_Status"]); mb = k.mb
    D, G, P, S = "MS_DarkSteel", "MS_Galvanized", "MS_PipePaint", "MS_Status"
    cbox(mb, D, I, -198, 198, -56, 58, 0, 15, 0.8)                                      # plinth
    cbox(mb, D, I, -200, 200, -56, 60, 585, 600, 1.0)                                   # top cable trunk
    for sx in (-1.0, 1.0): cbox(mb, D, I, sx*198, sx*200, -60, 60, 0, 585, 0.6)         # end panels
    cbox(mb, D, I, -198, 198, 56, 60, 15, 585, 0.5)                                     # rear
    for zc in (589.5, 596.0):                                                           # coolant headers
        cyl(mb, P, (-197.0, -56.0, zc), (197.0, -56.0, zc), 3.0, 16, c=0.4)
    rnd = lcg(7)
    for b in range(5):
        bx = -160.0+80.0*b
        cbox(mb, D, I, bx-38, bx+38, -54, -52, 15, 585, 0.3)                             # dark backdrop
        if b > 0:
            xd = bx-40.0
            cbox(mb, D, I, xd-2.0, xd+2.0, -59.5, -52, 15, 585, 0.4)                     # divider post
            cbox(mb, S, I, xd-0.6, xd+0.6, -60.0, -59.5, 22, 578, 0.0)                    # light column
        for s in range(15):
            z0 = 15.0+38.0*s
            cbox(mb, G, I, bx-38, bx+38, -57.0, -54.0, z0, z0+1.2, 0.2)                  # shelf lip
            for i in range(10):
                x0 = bx-37.5+7.5*i+0.15; x1 = x0+7.2; zb, zt = z0+1.5, z0+38.0-0.3
                cbox(mb, D, I, x0, x1, -58.5, -54.0, zb, zt, 0.25)                        # sled bezel
                lz = zt-3.0-6.0*int(rnd()*3)
                cbox(mb, S, I, x0+2.8, x1-2.8, -58.7, -58.5, lz, lz+1.4, 0.0)            # sled LED
                cbox(mb, G, I, x0+2.0, x1-2.0, -60.0, -58.5, zb+2.5, zb+3.7, 0.0)        # pull handle
        k.socket("SOCKET_Light_%02d" % b, (bx, -60.0, 592.0), (0, -1, 0), (0, 0, 1))
    k.ucx_box(I, -200, 200, -60, 60, 0, 600)
    k.probe("front_hit", (0, -300, 300), (0, 0, 300), True)
    k.notes.append("5 bays x 15 chassis x 10 blade sleds (750 sleds, emissive LEDs on MS_Status); 1 UCX box")
    return k

# ---------------------------------------------------------------- 7 cable trays
def b_tray_straight():
    k = Kit(["MS_Galvanized"]); mb = k.mb; G = "MS_Galvanized"; L = 300.0
    for sy in (-1.0, 1.0):
        cbox(mb, G, I, 0, L, sy*18.0, sy*20.0, 0, 15, 0.3)                               # web
        cbox(mb, G, I, 0, L, sy*16.0, sy*18.0, 13.5, 15, 0.2)                            # top lip
        cbox(mb, G, I, 0, L, sy*15.0, sy*18.0, 0, 1.5, 0.2)                              # bottom lip
    for i in range(10):                                                                  # rungs
        x = 15.0+30.0*i
        cbox(mb, G, I, x-1.5, x+1.5, -18.0, 18.0, 1.5, 3.0, 0.2)
        cbox(mb, G, I, x-1.5, x-1.2, -18.0, 18.0, 1.5, 4.0, 0.0); cbox(mb, G, I, x+1.2, x+1.5, -18.0, 18.0, 1.5, 4.0, 0.0)
    for sy in (-1.0, 1.0):                                                               # splice bolts (inside web)
        for x in (4.0, 9.0, L-9.0, L-4.0):
            for z in (5.0, 10.0):
                cyl(mb, G, (x, sy*18.0, z), (x, sy*16.9, z), 0.7, 6, c=0.1, smooth=False)
    k.ucx_box(I, 0, L, -20, 20, 0, 15)
    k.socket("SOCKET_End_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_End_B", (L, 0, 0), (1, 0, 0))
    k.probe("rung_hit", (15, 0, 100), (15, 0, -50), True)
    k.notes.append("Ladder tray per audit (300 x 40 x 15). The imported SM_CableTray_Corner is a 6-conduit bundle (~57 x 34), so SM_CableTray_ConduitRun_Straight is the run that actually mates with it")
    return k

def b_conduit_straight():
    k = Kit(["MS_Rubber", "MS_DarkSteel"]); mb = k.mb; L = 300.0
    Rt = 8.5
    for yc in (-20.15, 0.0, 20.15):
        for zc in (10.05, 28.05):
            fr = Fr((0, yc, zc))
            lathe(mb, "MS_Rubber", fr, [(0.0, 0.0), (0.0, Rt), (L, Rt), (L, 0.0)], 8, True, rad(22.5))
    for x in (50.0, 150.0, 250.0):                                                       # strap clamps
        cbox(mb, "MS_DarkSteel", I, x-2.0, x+2.0, -29.5, 29.5, 36.2, 37.0, 0.15)
        cbox(mb, "MS_DarkSteel", I, x-2.0, x+2.0, -29.5, 29.5, 1.0, 1.9, 0.15)
        for sy in (-1.0, 1.0):
            cbox(mb, "MS_DarkSteel", I, x-2.0, x+2.0, sy*28.7, sy*29.5, 1.0, 37.0, 0.15)
            cyl(mb, "MS_DarkSteel", (x, sy*29.5, 34.0), (x, sy*30.3, 34.0), 0.8, 6, c=0.1, smooth=False)
    k.ucx_box(I, 0, L, -30.3, 30.3, 1.0, 37.0)
    k.socket("SOCKET_End_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_End_B", (L, 0, 0), (1, 0, 0))
    k.probe("bundle_hit", (100, 0, 100), (100, 0, -50), True)
    k.notes.append("Cross-section copied from SM_CableTray_Corner (6 x octagon R 8.5, Y +-20.15, Z 10.05/28.05). Corner arm ends: X-arm face at X 100 centred Y -70.2; Y-arm face at Y 100 centred X -71.1")
    return k

# ---------------------------------------------------------------- 8 catwalk
def catwalk_rail(mb, k, sy, x0=-100.0, x1=100.0):
    Y = "MS_SafetyPaint"
    for x in (-50.0, 50.0):
        cbox(mb, Y, I, x-2.0, x+2.0, sy*45.0, sy*49.0, 0.8, 106.0, 0.3)                  # post
        cbox(mb, "MS_Galvanized", I, x-4.0, x+4.0, sy*43.0, sy*50.0, 0.0, 0.8, 0.2)      # base plate
    cyl(mb, Y, (x0, sy*47.0, 107.9), (x1, sy*47.0, 107.9), 2.1, 16, c=0.3)               # top rail (top Z 110)
    cyl(mb, Y, (x0, sy*47.0, 55.0), (x1, sy*47.0, 55.0), 1.7, 16, c=0.3)                 # knee rail
    cbox(mb, Y, I, x0, x1, sy*48.4, sy*49.4, 0.0, 10.0, 0.2)                             # toe board
    k.ucx_box(I, x0, x1, sy*44.0, sy*50.0, 0.0, 110.0)

def b_catwalk(variant):
    k = Kit(["MS_Galvanized", "MS_DarkSteel", "MS_SafetyPaint"]); mb = k.mb
    G, D = "MS_Galvanized", "MS_DarkSteel"
    for sy in (-1.0, 1.0):
        cbox(mb, D, I, -100, 100, sy*46.0, sy*50.0, -8, 0, 0.3)                          # side channels
        cbox(mb, D, I, sy*96.0, sy*100.0, -46, 46, -8, 0, 0.3)                           # end channels
    cbox(mb, D, I, -2, 2, -46, 46, -8, -3, 0.2)                                          # mid cross member
    x = -95.0
    while x <= 95.01:                                                                    # bearing bars
        cbox(mb, G, I, x-0.25, x+0.25, -46, 46, -3, 0, 0.0); x += 3.3
    for y in range(-40, 41, 10):                                                         # cross rods
        cbox(mb, G, I, -96, 96, y-0.3, y+0.3, -1.0, -0.2, 0.0)
    k.ucx_box(I, -100, 100, -50, 50, -8, 0)
    sides = (-1.0, 1.0) if variant == "A" else (1.0,)
    for sy in sides: catwalk_rail(mb, k, sy)
    k.socket("SOCKET_Snap_A", (-100, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Snap_B", (100, 0, 0), (1, 0, 0))
    k.probe("deck_hit", (30, 0, 200), (30, 0, -50), True)
    k.probe("rail_plusY", (0, 0, 80), (0, 100, 80), True)
    k.probe("rail_minusY", (0, 0, 80), (0, -100, 80), variant == "A")
    k.notes.append("Pivot = deck-top centre; 200 x 100 grid; rails 110 high (UCX to 110, no step-up; set Can Character Step Up On = No on placed components)")
    if variant != "A": k.notes.append("Single rail on Max +Y (= UE -Y) for side-by-side widening")
    return k

def b_catwalk_stair():
    k = Kit(["MS_Galvanized", "MS_DarkSteel", "MS_SafetyPaint"]); mb = k.mb
    G, D, Y = "MS_Galvanized", "MS_DarkSteel", "MS_SafetyPaint"
    Fs = Fr((0, 0, 0), (0, 1, 0), (1, 0, 0), (0, 0, 1))                                  # w = Y, u = X, v = Z
    strg = [(0.0, 0.0), (7.5, 0.0), (300.0, 195.0), (300.0, 200.0), (262.5, 200.0), (0.0, 25.0)]
    for sy in (-1.0, 1.0):
        cprism(mb, D, Fs, strg, sy*46.0, sy*50.0, 0.4)
    for t in range(10):
        x0, zt = 30.0*t, 20.0*(t+1)
        cbox(mb, Y, I, x0, x0+3.0, -46, 46, zt-3.0, zt, 0.2)                               # nosing
        cbox(mb, D, I, x0+27.0, x0+30.0, -46, 46, zt-3.0, zt, 0.2)                         # back bar
        for sy in (-1.0, 1.0): cbox(mb, D, I, x0, x0+30.0, sy*44.5, sy*46.0, zt-4.0, zt, 0.2)
        xb = x0+5.0
        while xb < x0+26.0:
            cbox(mb, G, I, xb-0.25, xb+0.25, -44.5, 44.5, zt-3.0, zt, 0.0); xb += 2.6
        for y in (-20.0, 20.0): cbox(mb, G, I, x0+3.0, x0+27.0, y-0.3, y+0.3, zt-1.0, zt-0.2, 0.0)
    for sy in (-1.0, 1.0):
        for x in (2.5, 150.0, 297.5):
            zs = min(25.0+2.0*x/3.0, 200.0); zr = 110.0+2.0*x/3.0
            cbox(mb, Y, I, x-2.0, x+2.0, sy*46.5, sy*49.5, zs, zr-1.0, 0.3)
        cyl(mb, Y, (0.0, sy*48.0, 107.9), (300.0, sy*48.0, 307.9), 2.1, 16, c=0.3)
        cyl(mb, Y, (0.0, sy*48.0, 65.0), (300.0, sy*48.0, 265.0), 1.7, 16, c=0.3)
        k.ucx_pts([(x, y, z) for y in (sy*44.0, sy*50.0) for (x, z) in ((0.0, 20.0), (0.0, 110.0), (300.0, 310.0), (300.0, 220.0))])
    k.ucx_pts([(x, y, z) for y in (-50.0, 50.0) for (x, z) in ((0.0, 0.0), (0.0, 20.0), (270.0, 200.0), (300.0, 200.0), (300.0, 190.0), (15.0, 0.0))])
    k.socket("SOCKET_Snap_Bottom", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Snap_Top", (300, 0, 200), (1, 0, 0))
    k.probe("tread_ramp_hit", (150, 0, 400), (150, 0, -50), True)
    k.notes.append("10 risers x 20 / goings 30 (33.7 deg), rise 200 over 300; top tread at Z 200 meets a catwalk deck-top; ramp UCX through the nosings for smooth walking")
    return k

# ---------------------------------------------------------------- 9 bulkhead
OPEN = (-50.0, 50.0, 10.0, 210.0, 20.0)          # clear opening u0, u1, v0, v1, r  (u = Y, v = Z)
HINGE = (-4.0, -70.0)                            # leaf hinge axis (x, y)

def b_bulkhead_frame():
    k = Kit(["MS_DarkSteel", "MS_Galvanized", "MS_Status"]); mb = k.mb
    D, G, S = "MS_DarkSteel", "MS_Galvanized", "MS_Status"
    cen = (0.0, 110.0)
    c = 1.5                                                                           # wall plate x 8..32
    rays, cin, cout = rr_rays(cen, (-110, 110, 0, 260, 0.0), (-110+c, 110-c, c, 260-c, 0.0),
                              (-51-c, 51+c, 9-c, 211+c, 21+c), (-51, 51, 9, 211, 21))
    holed_plate(mb, D, Fr((8.0, 0, 0)), rays, True, 24.0, c, cin, cout)
    c = 1.0                                                                           # coaming x 0..40
    rays, cin, cout = rr_rays(cen, (-62, 62, 0, 222, 32), (-62+c, 62-c, c, 222-c, 32-c),
                              (-50-c, 50+c, 10-c, 210+c, 20+c), OPEN)
    holed_plate(mb, D, Fr((0.0, 0, 0)), rays, True, 40.0, c, cin, cout)
    for xf in (0.0, 40.0):                                                            # bolt ring
        sx = -1.0 if xf == 0.0 else 1.0
        pts, _ = rr_poly(-56, 56, 4, 216, 26, 3)
        for i, p in enumerate(pts):
            if i % 2: continue
            cyl(mb, G, (xf, p[0], p[1]), (xf+sx*1.0, p[0], p[1]), 1.1, 6, c=0.15, smooth=False)
    hx, hy = HINGE
    for (z0, z1) in ((40.0, 52.0), (168.0, 180.0)):                                   # hinge lugs + pin
        cbox(mb, D, I, -8.0, 0.0, hy-6.0, -62.0, z0, z1, 0.4)
    cyl(mb, G, (hx, hy, 38.0), (hx, hy, 194.0), 1.2, 12, c=0.2)
    cbox(mb, D, I, -3.0, 0.0, -9.0, 9.0, 232.0, 244.0, 0.4)                           # status lamp
    cbox(mb, S, I, -4.5, -3.0, -6.0, 6.0, 234.0, 242.0, 0.3)
    for z in (234.0, 238.0, 242.0): cbox(mb, G, I, -6.0, -4.5, -7.0, 7.0, z-0.4, z+0.4, 0.0)
    for (y0, y1, z0, z1) in ((-110, -62, 0, 260), (62, 110, 0, 260), (-62, 62, 222, 260)):
        k.ucx_box(I, 8.0, 32.0, y0, y1, z0, z1)
    for (y0, y1, z0, z1) in ((-62, -50, 0, 222), (50, 62, 0, 222), (-50, 50, 210, 222), (-50, 50, 0, 10)):
        k.ucx_box(I, 0.0, 40.0, y0, y1, z0, z1)
    k.ucx_box(I, -8.0, 0.0, hy-6.0, -62.0, 40.0, 180.0)
    k.socket("SOCKET_Leaf_Hinge", (hx, hy, 0.0))
    k.socket("SOCKET_Nav_In", (-60.0, 0.0, 110.0), (1, 0, 0)); k.socket("SOCKET_Nav_Out", (100.0, 0.0, 110.0), (1, 0, 0))
    k.socket("SOCKET_Light_Status", (-4.5, 0.0, 238.0), (-1, 0, 0))
    k.probe("opening_clear", (-80, 0, 110), (120, 0, 110), False)
    k.probe("jamb_hit", (-80, -85, 110), (120, -85, 110), True)
    k.notes.append("Passage +X (Bible 3.0.2) so the 220 x 40 x 260 envelope reads 40 (X) x 220 (Y) x 260 (Z); opening 100 x 200 (sill Z 10, r 20); pivot = floor centre of the opening on the outer plane; leaf mounts on SOCKET_Leaf_Hinge")
    return k

def b_bulkhead_leaf():
    k = Kit(["MS_DarkSteel", "MS_Galvanized", "MS_Rubber"]); mb = k.mb
    D, G, R = "MS_DarkSteel", "MS_Galvanized", "MS_Rubber"
    hx, hy = HINGE
    F = shift_fr((-hx, -hy, 0.0))                                                    # frame coords -> hinge-local
    Fy = Fr(F.p(-7.0, 0, 0))                                                         # leaf plate x -7..-1
    poly, cv = rr_poly(-56, 56, 4, 216, 26, 6)
    cprism(mb, D, Fy, poly, 0.0, 6.0, 0.8, cv)
    rays, cin, cout = rr_rays((0.0, 110.0), (-55, 55, 5, 215, 25), (-55, 55, 5, 215, 25), (-47, 47, 13, 207, 17), (-47, 47, 13, 207, 17))
    holed_plate(mb, R, Fr(F.p(-1.0, 0, 0)), rays, True, 1.0, 0.0, cin, cout)          # gasket x -1..0
    for z in (70.0, 150.0):                                                          # stiffeners
        cbox(mb, D, F, -10.0, -7.0, -50, 50, z-3.0, z+3.0, 0.4)
    cbox(mb, D, F, -10.0, -7.0, -3.0, 3.0, 12, 208, 0.4)
    for (y, z) in ((40.0, 40.0), (40.0, 180.0), (-40.0, 40.0), (-40.0, 180.0), (48.0, 110.0), (-48.0, 110.0)):   # dogs
        cyl(mb, G, F.p(-7.0, y, z), F.p(-10.5, y, z), 2.5, 12, c=0.3)
        tip = (y, z+7.0) if z < 110 else (y, z-7.0) if z > 110 else (y-math.copysign(7.0, y), z)
        bar(mb, G, F.p(-10.5, y, z), F.p(-10.5, tip[0], tip[1]), 1.6, 1.6, (1, 0, 0), 0.3)
    for (z0, z1) in ((54.0, 64.0), (182.0, 192.0)):                                  # knuckles + arms
        cyl(mb, G, F.p(hx, hy, z0), F.p(hx, hy, z1), 3.0, 16, c=0.4)
        cbox(mb, D, F, -7.0, -1.0, hy+2.0, -54.0, z0+1.0, z1-1.0, 0.4)
    k.ucx_box(F, -10.5, 0.0, -56.0, 56.0, 4.0, 216.0)
    k.ucx_box(F, -7.0, -1.0, hy-3.0, -56.0, 54.0, 192.0)
    k.probe("leaf_hit", (-100+0.0, 70.0, 110.0), (100.0, 70.0, 110.0), True)
    k.notes.append("Pivot = hinge axis (Z up); swing about Z (AOS_ArchMovable)")
    return k

# ---------------------------------------------------------------- 10 valve
def b_valve_wheel():
    k = Kit(["MS_SafetyPaint", "MS_Galvanized"]); mb = k.mb
    Y, G = "MS_SafetyPaint", "MS_Galvanized"
    rim = [(14.0+1.8*math.cos(a), 18.2+1.8*math.sin(a)) for a in [2*math.pi*j/8 for j in range(8)]]
    lathe(mb, Y, I, rim, 40)
    cyl(mb, G, (0, 0, 0), (20.0, 0, 0), 3.5, 16, c=0.6)                                 # hub
    cyl(mb, G, (20.0, 0, 0), (20.3, 0, 0), 1.8, 6, c=0.05, smooth=False)                 # hex cap nut (flush)
    for j in range(5):
        a = 2*math.pi*j/5+math.pi/2
        p0 = (11.0, 3.0*math.cos(a), 3.0*math.sin(a)); p1 = (14.0, 16.8*math.cos(a), 16.8*math.sin(a))
        cyl(mb, Y, p0, p1, 1.1, 8, c=0.15)
    n = 12; R = 20.0/math.cos(math.pi/n)
    k.ucx_pts([(t, R*math.cos(2*math.pi*j/n), R*math.sin(2*math.pi*j/n)) for t in (11.5, 16.5) for j in range(n)] +
              [(t, 3.6*y, 3.6*z) for t in (0.0, 20.0) for (y, z) in ((1, 0), (0, 1), (-1, 0), (0, -1))])
    k.socket("SOCKET_Grip", (14.0, 0.0, 20.0), (0, 0, 1), (1, 0, 0))
    k.probe("face_hit", (60.0, 0.0, 18.2), (-40.0, 0.0, 18.2), True)
    k.notes.append("Rotating child: pivot = hub back face, spin axis = local +X; attach to SM_Valve_Body_D20:SOCKET_Wheel")
    return k

def b_valve_body():
    k = Kit(["MS_PipePaint", "MS_Galvanized", "MS_DarkSteel"]); mb = k.mb
    P, G, D = "MS_PipePaint", "MS_Galvanized", "MS_DarkSteel"
    L = 50.0
    flange(mb, 20, (0, 0, 0), (1, 0, 0)); flange(mb, 20, (L, 0, 0), (-1, 0, 0))
    lathe(mb, P, I, [(5.5, 0.0), (5.5, 10.6), (10.0, 12.5), (18.0, 14.5), (32.0, 14.5), (40.0, 12.5), (44.5, 10.6), (44.5, 0.0)], 24)
    cyl(mb, P, (25.0, 0, 10.0), (25.0, 0, 21.0), 9.0, 24, c=0.6)                          # bonnet neck
    cyl(mb, P, (25.0, 0, 21.0), (25.0, 0, 24.0), 11.5, 24, c=0.5)                         # bonnet flange
    for j in range(6):
        a = 2*math.pi*j/6
        cyl(mb, G, (25.0+10.0*math.cos(a), 10.0*math.sin(a), 24.0), (25.0+10.0*math.cos(a), 10.0*math.sin(a), 25.4), 1.1, 6, c=0.1, smooth=False)
    for sy in (-1.0, 1.0): cbox(mb, D, I, 23.5, 26.5, sy*5.0, sy*7.0, 24.0, 42.0, 0.3)    # yoke legs
    cbox(mb, D, I, 22.0, 28.0, -7.0, 7.0, 40.0, 43.0, 0.4)                                # yoke bridge
    cyl(mb, G, (25.0, 0, 20.0), (25.0, 0, 52.0), 1.2, 12, c=0.15)                          # stem
    cyl(mb, G, (25.0, 0, 43.0), (25.0, 0, 45.0), 2.4, 6, c=0.2, smooth=False)              # gland nut
    k.ucx_box(I, 0.0, L, -17.0, 17.0, -17.0, 17.0); k.ucx_box(I, 16.0, 34.0, -11.5, 11.5, 17.0, 46.0)
    k.socket("SOCKET_Flange_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Flange_B", (L, 0, 0), (1, 0, 0))
    k.socket("SOCKET_Wheel", (25.0, 0.0, 46.0), (0, 0, 1), (1, 0, 0))
    k.probe("body_hit", (25, 0, 150), (25, 0, -50), True)
    k.notes.append("Inline gate valve for D20 runs (face-to-face 50); SOCKET_Wheel X = +Z (wheel spin axis)")
    return k

# ---------------------------------------------------------------- 11 I-beams
def b_ibeam(L):
    k = Kit(["MS_DarkSteel", "MS_Galvanized"]); mb = k.mb; D, G = "MS_DarkSteel", "MS_Galvanized"
    e = 1.5
    for (z0, z1) in ((0.0, 2.0), (28.0, 30.0)): cbox(mb, D, I, e, L-e, -15, 15, z0, z1, 0.3)
    cbox(mb, D, I, e, L-e, -0.6, 0.6, 2.0, 28.0, 0.1)
    Fx = Fr((e, 0, 0))
    for sy in (-1.0, 1.0):
        for (zb, sz) in ((2.0, 1.0), (28.0, -1.0)):
            cprism(mb, D, Fx, [(sy*0.6, zb), (sy*0.6, zb+sz*1.2), (sy*1.8, zb)], 0.0, L-2*e, 0.0)
    for x0 in (0.0, L-e): cbox(mb, D, I, x0, x0+e, -15, 15, 0, 30, 0.3)                   # end plates
    for (x0, sx) in ((e, 1.0), (L-e, -1.0)):
        for y in (-9.0, 9.0):
            for z in (7.0, 23.0):
                cyl(mb, G, (x0, y, z), (x0+sx*1.3, y, z), 1.3, 6, c=0.15, smooth=False)
    s = 150.0
    while s < L-1.0:                                                                    # web stiffeners
        for sy in (-1.0, 1.0): cbox(mb, D, I, s-0.6, s+0.6, sy*0.6, sy*14.0, 2.0, 28.0, 0.1)
        s += 150.0
    k.ucx_box(I, 0, L, -15, 15, 0, 2); k.ucx_box(I, 0, L, -0.6, 0.6, 2, 28); k.ucx_box(I, 0, L, -15, 15, 28, 30)
    k.socket("SOCKET_End_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_End_B", (L, 0, 0), (1, 0, 0))
    k.probe("top_hit", (L/3.0, 7.0, 100), (L/3.0, 7.0, -50), True)
    k.probe("web_side_hit", (L/3.0, -50.0, 15.0), (L/3.0, 50.0, 15.0), True)
    k.notes.append("Pivot = end A, bottom-flange centre; 30 x 30 section, 3 UCX (flanges + web)")
    return k

# ---------------------------------------------------------------- 12 vent ducts
DUCT_H, DUCT_T, DUCT_F, DUCT_FT = 30.0, 0.8, 34.0, 3.5
def duct_flange(mb, k, o, inward):
    fr = axis_fr(o, inward); fr1 = Fr(fr.p(DUCT_FT), fr.x, fr.y, fr.z)
    sweep(mb, "MS_Galvanized", [fr, fr1], square(DUCT_F), square(DUCT_H-DUCT_T), 0, 0)
    for (u, v) in [(sgn*32.0, t) for sgn in (-1, 1) for t in (-20.0, 0.0, 20.0)] + [(t, sgn*32.0) for sgn in (-1, 1) for t in (-20.0, 0.0, 20.0)]:
        cyl(mb, "MS_Galvanized", fr.p(DUCT_FT, u, v), fr.p(DUCT_FT+1.0, u, v), 0.9, 6, c=0.1, smooth=False)

def b_duct_straight():
    k = Kit(["MS_Galvanized"]); mb = k.mb; L = 200.0
    duct_flange(mb, k, (0, 0, 0), (1, 0, 0)); duct_flange(mb, k, (L, 0, 0), (-1, 0, 0))
    sweep(mb, "MS_Galvanized", [Fr((DUCT_FT, 0, 0)), Fr((L-DUCT_FT, 0, 0))], square(DUCT_H), square(DUCT_H-DUCT_T), 0, 0)
    for x in (50.0, 100.0, 150.0):
        sweep(mb, "MS_Galvanized", [Fr((x-0.6, 0, 0)), Fr((x+0.6, 0, 0))], square(DUCT_H+0.6), square(DUCT_H-0.2), 0, 0)
    k.ucx_box(I, 0, L, -DUCT_H, DUCT_H, -DUCT_H, DUCT_H)
    k.socket("SOCKET_Duct_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Duct_B", (L, 0, 0), (1, 0, 0))
    k.probe("top_hit", (100, 0, 150), (100, 0, -150), True)
    k.notes.append("60 x 60 galvanised duct, flanged ends (68 x 68), pivot = end-A face centre (duct axis)")
    return k

def b_duct_elbow(G=100.0, R=60.0):
    k = Kit(["MS_Galvanized"]); mb = k.mb
    duct_flange(mb, k, (0, 0, 0), (1, 0, 0)); duct_flange(mb, k, (G, G, 0), (0, -1, 0))
    sg = [1 << 1, 0, 1 << 2, 0]                         # square(): edges 0 (+y side), 1 (+z), 2 (-y), 3 (-z)
    sgi = [1 << 3, 0, 1 << 4, 0]
    sweep(mb, "MS_Galvanized", elbow_path(G, R, DUCT_FT, 12), square(DUCT_H), square(DUCT_H-DUCT_T), sg, sgi)
    sq = lambda fr: [fr.p(0, u, v) for (u, v) in square(DUCT_H)]
    st1 = [axis_fr((0, 0, 0), (1, 0, 0)), elbow_station(G, R, 0.0), elbow_station(G, R, 22.5), elbow_station(G, R, 45.0)]
    st2 = [elbow_station(G, R, 45.0), elbow_station(G, R, 67.5), elbow_station(G, R, 90.0), axis_fr((G, G, 0), (0, 1, 0))]
    k.ucx_pts(sum([sq(f) for f in st1], [])); k.ucx_pts(sum([sq(f) for f in st2], []))
    k.socket("SOCKET_Duct_A", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Duct_B", (G, G, 0), (0, 1, 0))
    k.probe("stub_top", (20, 0, 150), (20, 0, -150), True)
    k.probe("inner_corner_clear", (15, 85, 150), (15, 85, -150), False)
    k.notes.append("Centre-line R 60 + 40 stubs so both faces land on the 100 grid; 2 UCX")
    return k

# ---------------------------------------------------------------- 13 brutalist concrete
def b_arch():
    k = Kit(["MS_Concrete"]); mb = k.mb
    W2, H, a, zs, R, T, c = 300.0, 500.0, 200.0, 250.0, 200.0, 80.0, 3.0
    C = (0.0, zs)
    def outer(th, ins):
        d = (math.cos(th), math.sin(th)); w2, h = W2-ins, H-ins; ts = []
        if abs(d[0]) > 1e-9: ts.append(w2/abs(d[0]))
        if d[1] > 1e-9: ts.append((h-zs)/d[1])
        t = min(ts); return (C[0]+d[0]*t, C[1]+d[1]*t)
    thc = math.degrees(math.atan2(H-zs, W2))
    angs = sorted(set([180.0-180.0*i/24 for i in range(25)] + [180.0-thc, thc]), reverse=True)
    rays = [((-W2, 0.0), (-W2+c, 0.0), (-a-c, 0.0), (-a, 0.0))]
    for th in angs:
        t = rad(th); d = (math.cos(t), math.sin(t))
        O, Op = outer(t, 0.0), outer(t, c)
        if abs(th-(180.0-thc)) < 1e-9: Op = (-W2+c, H-c)
        if abs(th-thc) < 1e-9: Op = (W2-c, H-c)
        rays.append((O, Op, (C[0]+d[0]*(R+c), C[1]+d[1]*(R+c)), (C[0]+d[0]*R, C[1]+d[1]*R)))
    rays.append(((W2, 0.0), (W2-c, 0.0), (a+c, 0.0), (a, 0.0)))
    cin = [False] + [True]*(len(angs)-1) + [False]
    holed_plate(mb, "MS_Concrete", I, rays, False, T, c, cin, None)
    for sy in (-1.0, 1.0): k.ucx_box(I, 0, T, sy*a, sy*W2, 0, zs)
    bnd = [180.0, 160.1, 180.0-thc, 115.1, 90.0, 64.9, thc, 19.9, 0.0]
    for i in range(len(bnd)-1):
        a0, a1 = rad(bnd[i]), rad(bnd[i+1]); Rr = R/math.cos((a0-a1)/2.0)
        q = [(C[0]+Rr*math.cos(a0), C[1]+Rr*math.sin(a0)), outer(a0, 0.0), outer(a1, 0.0), (C[0]+Rr*math.cos(a1), C[1]+Rr*math.sin(a1))]
        k.ucx_pts([(x, u, v) for x in (0.0, T) for (u, v) in q])
    k.socket("SOCKET_Nav_In", (-60.0, 0.0, 225.0), (1, 0, 0)); k.socket("SOCKET_Nav_Out", (140.0, 0.0, 225.0), (1, 0, 0))
    k.probe("opening_clear", (-100, 0, 200), (180, 0, 200), False)
    k.probe("crown_clear_edge", (-100, 0, 440), (180, 0, 440), False)
    k.probe("pier_hit", (40, 250, 700), (40, 250, -50), True)
    k.notes.append("Passage +X: 600 x 80 x 500 envelope reads 80 (X) x 600 (Y) x 500 (Z); opening 400 wide, semicircular head R 200, crown Z 450; 3 cm chamfers; 10 UCX (2 piers + 8 tangent crown slices)")
    return k

def b_stairs_concrete():
    k = Kit(["MS_Concrete", "MS_Galvanized"]); mb = k.mb
    n, L, H, W2 = 9, 316.0, 150.0, 80.0; g, h = L/n, H/n
    for i in range(n):
        cbox(mb, "MS_Concrete", I, i*g, L, -W2, W2, i*h, (i+1)*h, 1.5)
        if i < n-1:
            cbox(mb, "MS_Galvanized", I, i*g+1.5, i*g+6.5, -W2+6.0, W2-6.0, (i+1)*h-0.2, (i+1)*h+0.3, 0.15)
    k.ucx_pts([(x, y, z) for y in (-W2, W2) for (x, z) in ((0.0, 0.0), (0.0, h), ((n-1)*g, H), (L, H), (L, 0.0))])
    k.socket("SOCKET_Snap_Bottom", (0, 0, 0), (-1, 0, 0)); k.socket("SOCKET_Snap_Top", (L, 0, H), (1, 0, 0))
    k.probe("ramp_hit", (L/2, 0, 400), (L/2, 0, -50), True)
    k.notes.append("9 risers x 16.7 / goings 35.1 cast-slab steps (board-joint grooves from the stacked chamfers) + galvanised nosing strips; pivot = foot centre, rises to +X; 1 ramp UCX")
    return k

# ---------------------------------------------------------------- asset table
# name: (audit item, builder, args, scene position, size note, attach-to (parent asset, socket) or None)
ASSETS = [
    ("SM_Pipe_Straight_D20", 1, b_pipe_straight, (20,), (0, 0, 0), None),
    ("SM_Pipe_Straight_D40", 1, b_pipe_straight, (40,), (0, 150, 0), None),
    ("SM_Pipe_Straight_D80", 1, b_pipe_straight, (80,), (0, 350, 0), None),
    ("SM_Pipe_Elbow90_D40", 2, b_pipe_elbow, (40, 100.0), (600, 0, 0), None),
    ("SM_Pipe_Elbow90_D80", 2, b_pipe_elbow, (80, 200.0), (600, 250, 0), None),
    ("SM_Pipe_Tee_D40", 3, b_pipe_tee, (40, 100.0), (1000, 0, 0), None),
    ("SM_Pipe_Reducer_D80_D40", 3, b_pipe_reducer, (), (1000, 300, 0), None),
    ("SM_Pipe_Hanger_Clamp", 4, b_clamp, (20,), (1400, 0, 0), None),
    ("SM_Pipe_Hanger_Clamp_D40", 4, b_clamp, (40,), (1400, 150, 0), None),
    ("SM_Pipe_Hanger_Clamp_D80", 4, b_clamp, (80,), (1400, 350, 0), None),
    ("SM_ServerRack_Cabinet", 5, b_rack_cabinet, (), (0, 1000, 0), None),
    ("SM_ServerRack_Cabinet_Door", 5, b_rack_door, (), None, ("SM_ServerRack_Cabinet", "SOCKET_Door_Hinge")),
    ("SM_ServerRack_Mega", 6, b_rack_mega, (), (400, 1000, 0), None),
    ("SM_CableTray_Straight", 7, b_tray_straight, (), (1000, 1000, 0), None),
    ("SM_CableTray_ConduitRun_Straight", 7, b_conduit_straight, (), (1000, 1150, 0), None),
    ("SM_Catwalk_Grating_Module", 8, b_catwalk, ("A",), (0, 2000, 0), None),
    ("SM_Catwalk_Grating_Module_OneRail", 8, b_catwalk, ("B",), (300, 2000, 0), None),
    ("SM_Catwalk_Stair_Module", 8, b_catwalk_stair, (), (600, 2000, 0), None),
    ("SM_Bulkhead_Frame_Door", 9, b_bulkhead_frame, (), (1100, 2000, 0), None),
    ("SM_Bulkhead_Door_Leaf", 9, b_bulkhead_leaf, (), None, ("SM_Bulkhead_Frame_Door", "SOCKET_Leaf_Hinge")),
    ("SM_Valve_Body_D20", 10, b_valve_body, (), (1400, 2000, 0), None),
    ("SM_Valve_Wheel", 10, b_valve_wheel, (), None, ("SM_Valve_Body_D20", "SOCKET_Wheel")),
    ("SM_Steel_IBeam_300", 11, b_ibeam, (300.0,), (0, 3000, 0), None),
    ("SM_Steel_IBeam_600", 11, b_ibeam, (600.0,), (0, 3100, 0), None),
    ("SM_Vent_Duct_Straight", 12, b_duct_straight, (), (800, 3000, 0), None),
    ("SM_Vent_Duct_Elbow", 12, b_duct_elbow, (), (1100, 3000, 0), None),
    ("SM_Concrete_Arch_Brutalist", 13, b_arch, (), (0, 4000, 0), None),
    ("SM_Stairs_Concrete_Brutalist", 13, b_stairs_concrete, (), (800, 4000, 0), None),
]
ASSET_IDX = {a[0]: a for a in ASSETS}

def cull_class(bmin, bmax):
    d = vlen(vsub(tuple(bmax), tuple(bmin)))
    for lim in (25, 60, 150, 400, 1000):
        if d <= lim: return lim
    return 0

def run_builder(name):
    item, fn, args = ASSET_IDX[name][1], ASSET_IDX[name][2], ASSET_IDX[name][3]
    k = fn(*args)
    used = set(m for (_, m, _) in k.mb.f)
    k.slots = [s for s in k.slots if s in used]
    assert used <= set(k.slots), (name, used)
    return item, k

def asset_record(name, item, k):
    bmin, bmax = k.mb.bbox(); tris = k.mb.tris()
    return {"item": item, "slots": k.slots, "verts": len(k.mb.v), "tris": len(tris), "polys": len(k.mb.f),
            "bbox_min": [round(c, 2) for c in bmin], "bbox_max": [round(c, 2) for c in bmax],
            "size": [round(bmax[i]-bmin[i], 2) for i in range(3)],
            "ucx": [{"name": "UCX_%s_%02d" % (name, i+1), "verts": len(h[0]), "tris": len(h[1]),
                     "centroid": [round(c, 2) for c in vmid(h[0])]} for i, h in enumerate(k.ucx)],
            "sockets": k.sock, "probes": k.probes, "notes": k.notes, "prim_flips": k.mb.flips, "prims": k.mb.prims,
            "cull_class": cull_class(bmin, bmax), "area_cm2": round(k.mb.area(), 1)}

# ================================================================ 3ds Max side
MXS = r'''
global dk_make, dk_uv
fn dk_make verts faces mids sgs evs nm = (
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
    convertToPoly m
    m
)
fn dk_uv m a3 tile = (
    max modify mode
    select m
    local uv = Unwrap_UVW()
    addModifier m uv
    modPanel.setCurrentObject uv
    uv.setMapChannel 1
    uv.flattenMap 45.0 #() 0.002 true 0 false true
    uv.selectOverlappedFaces()
    local ov = (uv.getSelectedFaces()).numberSet
    collapseStack m
    local auv = 0.0
    for f = 1 to (polyop.getNumFaces m) do (
        local mf = polyop.getMapFace m 1 f
        local p0 = polyop.getMapVert m 1 mf[1]
        for q = 2 to mf.count - 1 do (
            local p1 = polyop.getMapVert m 1 mf[q]
            local p2 = polyop.getMapVert m 1 mf[q+1]
            auv += (abs ((p1.x-p0.x)*(p2.y-p0.y) - (p2.x-p0.x)*(p1.y-p0.y))) * 0.5
        )
    )
    local k = (sqrt (a3 / auv)) / tile
    for i = 1 to (polyop.getNumMapVerts m 1) do (
        local p = polyop.getMapVert m 1 i
        polyop.setMapVert m 1 i [p.x*k, p.y*k, 0]
    )
    (ov as string) + "|" + (auv as string) + "|" + (k as string)
)
global dk_mm
fn dk_mm nm mats nms = (
    local mm = MultiMaterial numsubs:mats.count name:nm
    for i = 1 to mats.count do ( mm.materialList[i] = mats[i]; mm.names[i] = nms[i] )
    mm
)
'''

_MATS = {}
def phys_mat(slot):
    if slot in _MATS and rt.isValidObj(_MATS[slot]): return _MATS[slot]
    col, met, rough, emi = SLOT_CAT[slot]
    m = rt.PhysicalMaterial(name=slot)
    m.base_color = rt.Color(*col); m.metalness = met; m.roughness = rough
    if emi: m.emit_color = rt.Color(*emi); m.emission = 6.0
    _MATS[slot] = m; return m

def own_names(names):
    return set(names)

def is_owned(o, names):
    nm = str(o.name)
    if nm in names: return True
    for n in names:
        if nm.startswith("UCX_" + n + "_") or nm.startswith(REF_PFX + n + "__"): return True
    return False

def prepare_scene(names):
    if str(rt.units.SystemType) != "centimeters" or abs(float(rt.units.SystemScale)-1.0) > 1e-6:
        rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    cur = os.path.join(str(rt.maxFilePath), str(rt.maxFileName))
    if os.path.normcase(cur) != os.path.normcase(MAX_PATH):
        all_kit = set(a[0] for a in ASSETS)
        foreign = [o for o in rt.objects if not is_owned(o, all_kit)]
        if foreign:
            if rt.getSaveRequired():
                raise RuntimeError("Scene %s has unsaved foreign content - save it first; build aborted." % cur)
            rt.resetMaxFile(rt.Name("noPrompt"))
        if os.path.exists(MAX_PATH) and not list(rt.objects):
            rt.loadMaxFile(MAX_PATH, quiet=True)
    if str(rt.units.SystemType) != "centimeters":
        rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    for o in [o for o in rt.objects if is_owned(o, set(names))]:
        try: rt.delete(o)
        except Exception: pass

def P3(p): return rt.Point3(float(p[0]), float(p[1]), float(p[2]))

def node_tm(name, built):
    """World transform for an asset node (scene layout or attached to its parent's socket)."""
    rec = ASSET_IDX[name]
    if rec[4] is not None: return rt.transMatrix(P3(rec[4]))
    parent, sock = rec[5]
    ptm = node_tm(parent, built)
    sd = built[parent]["sockets"][sock]
    x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
    return rt.Matrix3(P3(x), P3(y), P3(z), P3(sd["pos"])) * ptm

def make_node(name, k):
    slots = k.slots; sid = {s: i+1 for i, s in enumerate(slots)}
    tris = k.mb.tris()
    verts = [P3(p) for p in k.mb.v]
    faces = [rt.Point3(t[0]+1, t[1]+1, t[2]+1) for (t, m, g, e) in tris]
    mids = [sid[m] for (t, m, g, e) in tris]
    sgs = [g for (t, m, g, e) in tris]; evs = [e for (t, m, g, e) in tris]
    node = rt.dk_make(verts, faces, mids, sgs, evs, name)
    if len(slots) == 1:
        node.material = phys_mat(slots[0])
    else:
        node.material = rt.dk_mm("MM_" + name, [phys_mat(s) for s in slots], list(slots))
    return node

def make_ucx(name, k):
    out = []
    for i, (pts, fcs) in enumerate(k.ucx):
        m = rt.mesh(vertices=[P3(p) for p in pts], faces=[rt.Point3(a+1, b+1, c+1) for (a, b, c) in fcs])
        m.name = "UCX_%s_%02d" % (name, i+1); m.wirecolor = rt.Color(255, 60, 60)
        out.append(m)
    return out

def settle_ui():
    rt.execute("max create mode")
    rt.windows.processPostedMessages(); rt.completeRedraw(); rt.windows.processPostedMessages()

def load_spec():
    if os.path.exists(SPEC_PATH):
        with open(SPEC_PATH, encoding="utf-8") as f: return json.load(f)
    return {"kit": "AOS_DK DeficitKit", "units": "cm", "space": "3ds Max RH Z-up; UE import maps (x, y, z) -> (x, -y, z)",
            "max_file": MAX_PATH, "fbx_dir": FBX_DIR, "uv_tile_cm": TILE, "assets": {}}

def save_scene():
    settle_ui()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)

def build(names=None):
    names = list(names) if names else [a[0] for a in ASSETS]
    prepare_scene(names)
    rt.execute(MXS)
    spec = load_spec(); out = {}
    for name in names:
        item, k = run_builder(name)
        rec = asset_record(name, item, k)
        node = make_node(name, k)
        uv = [x.strip().replace("d", "e") for x in str(rt.dk_uv(node, rec["area_cm2"], TILE)).split("|")]
        rec["uv_overlap_faces"] = int(float(uv[0])); rec["uv_scale"] = round(float(uv[2]), 6)
        ucx = make_ucx(name, k)
        spec["assets"][name] = rec
        tm = node_tm(name, spec["assets"])
        node.transform = tm
        for u in ucx: u.transform = tm
        lay = rt.LayerManager.getLayerFromName("DK_" + name) or rt.LayerManager.newLayerFromName("DK_" + name)
        lay.addnode(node)
        for u in ucx: lay.addnode(u)
        rl = rt.LayerManager.getLayerFromName("DK_Ref_Sockets") or rt.LayerManager.newLayerFromName("DK_Ref_Sockets")
        for sn, sd in k.sock.items():
            x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
            pt = rt.Point(name=REF_PFX + name + "__" + sn, size=8, box=True, cross=True, axistripod=True)
            pt.transform = rt.Matrix3(P3(x), P3(y), P3(z), P3(sd["pos"])) * tm; pt.wirecolor = rt.Color(255, 40, 160)
            rl.addnode(pt)
        out[name] = {"verts": int(rt.polyop.getNumVerts(node)), "polys": int(rt.polyop.getNumFaces(node)), "tris": rec["tris"],
                     "size": rec["size"], "ucx": [u["verts"] for u in rec["ucx"]], "slots": rec["slots"],
                     "uv_overlap": rec["uv_overlap_faces"], "flips": rec["prim_flips"]}
    with open(SPEC_PATH, "w", encoding="utf-8") as f: json.dump(spec, f, indent=1)
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
    spec = load_spec(); res = {}
    for name in names:
        node = rt.getNodeByName(name)
        ucx = [rt.getNodeByName(u["name"]) for u in spec["assets"][name]["ucx"]]
        nodes = [node] + ucx
        saved = [n.transform for n in nodes]
        for n in nodes: n.transform = rt.Matrix3(1)
        rt.clearSelection(); rt.select(nodes)
        path = os.path.join(FBX_DIR, name + ".fbx")
        ok = rt.exportFile(path, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
        for n, t in zip(nodes, saved): n.transform = t
        res[name] = {"ok": bool(ok), "bytes": os.path.getsize(path) if os.path.exists(path) else 0, "ucx_nodes": len(ucx)}
    rt.clearSelection()
    save_scene()
    res["_dirty"] = bool(rt.getSaveRequired())
    return res

GUARD_MXS = r'''
global dk_guard_timer
fn dk_guard_tick s e = (
    s.Stop()
    if (maxFilePath + maxFileName) == @"%s" and getSaveRequired() do
        saveMaxFile (maxFilePath + maxFileName) clearNeedSaveFlag:true useNewFile:true quiet:true
    setSaveRequired false
    dotNet.removeAllEventHandlers s
)
dk_guard_timer = dotNetObject "System.Windows.Forms.Timer"
dk_guard_timer.Interval = 1500
dotNet.addEventHandler dk_guard_timer "Tick" dk_guard_tick
dk_guard_timer.Start()
''' % MAX_PATH

def arm_dirty_guard():
    """Max 2027 re-flags a freshly built scene once its UI idles after the call returns; a one-shot UI timer
    re-saves the unchanged scene and clears the flag 1.5 s later."""
    rt.execute(GUARD_MXS)
