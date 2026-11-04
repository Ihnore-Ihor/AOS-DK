# -*- coding: utf-8 -*-
"""
AOS_DK :: SubDrone_Attacker procedural geometry generator (3ds Max 2027 / pymxs)

Builds (all pivots at world origin, +X = nose = UE forward, Z-up, centimetres):
  SM_SubDrone_Attacker_HullFront  - front hull section (x > 0), MatIDs: 1 Hull, 2 SpiralGlow
  SM_SubDrone_Attacker_HullRear   - rear hull section  (x < 0), mirrored -> opposite helix handedness
  SM_SubDrone_Attacker_Core       - induction generator stator in the central groove, MatIDs: 1 CoreBody, 2 CoreCoils
  SM_MicroTorpedo                 - 11 cm needle projectile with flat cavitator, MatIDs: 1 TorpedoBody, 2 TorpedoGlow

Both hull halves share the drone's longitudinal axis (X) as pivot, so in UE each section
is spun independently with SetRelativeRotation(FRotator(0,0,Roll)).
The torpedo ring is NOT modelled: UE builds it procedurally (ISM) at r = RING_RADIUS_HINT.

Re-run safe: deletes previously generated nodes with the same names.
"""
import math
from pymxs import runtime as rt

# ----------------------------------------------------------------------------- parameters
HALF_LEN    = 62.0    # groove centre -> nose tip
R_MAX       = 19.5    # max hull radius (right next to the groove: "smooth widening to centre")
GAP_HALF    = 6.5     # half width of the groove at the lip
BOWL_DEPTH  = 7.0     # how deep the concave dish goes into each half
R_RIM       = 15.5    # inner rim radius of the dish
R_AXLE      = 5.0     # dish bottom / spindle socket radius
LIP_BEVEL_X = 1.6     # V-notch bevel length
SEG         = 64      # radial segments (hull)
SKIN_SAMPLES= 44

N_STRIPS    = 4       # helical glow ribbons per half
TURNS       = 1.15
RIB_WIDTH   = 0.9
RIB_LIFT    = 0.06
RIB_SAMPLES = 96
RIB_U0, RIB_U1 = 0.035, 0.86   # ribbon span along the skin (0 = lip, 1 = nose)

RING_RADIUS_HINT = 13.5  # where UE places torpedoes (documented here for clearance checks)

TORP_HALF   = 5.5     # 11 cm total
TORP_SEG    = 16

NAMES = ["SM_SubDrone_Attacker_HullFront", "SM_SubDrone_Attacker_HullRear",
         "SM_SubDrone_Attacker_Core", "SM_MicroTorpedo"]

# ----------------------------------------------------------------------------- helpers
def skin_point(u):
    """Outer skin of the front half: u=0 at lip, u=1 at nose tip. Bionic egg taper."""
    x0 = GAP_HALF + LIP_BEVEL_X + 0.6
    x = x0 + u * (HALF_LEN - x0)
    r = R_MAX * max(0.0, 1.0 - u ** 2.3) ** 0.6
    return x, r

def hull_profile():
    """(x, r, matid) list ordered: dish cap centre -> dish -> rim -> V-bevel -> skin -> nose."""
    p = []
    xb = GAP_HALF + BOWL_DEPTH
    p.append((xb, 0.0, 1))
    n = 12
    for i in range(n + 1):                         # concave dish, flat bottom, steep rim
        s = i / n
        p.append((GAP_HALF + BOWL_DEPTH * math.cos(s * math.pi / 2),
                  R_AXLE + (R_RIM - R_AXLE) * math.sin(s * math.pi / 2), 1))
    p.append((GAP_HALF + LIP_BEVEL_X * 0.55, R_MAX * 0.93, 1))   # V-notch bevel
    p.append((GAP_HALF + LIP_BEVEL_X, R_MAX * 0.975, 1))
    for i in range(SKIN_SAMPLES + 1):              # sin-distribution: dense near the nose
        t = i / SKIN_SAMPLES
        u = math.sin(t * math.pi / 2)
        x, r = skin_point(u)
        p.append((x, r, 1))
    return p

def lathe(profile, seg, mirror=False, v_scale=1.0):
    """Revolve (x, r, matid) profile around X. Returns verts, faces, mats, tverts, tfaces."""
    verts, faces, mats, tverts, tfaces = [], [], [], [], []
    ring_idx, ring_tv = [], []
    # cumulative arc length for V
    acc = [0.0]
    for i in range(1, len(profile)):
        acc.append(acc[-1] + math.hypot(profile[i][0] - profile[i-1][0], profile[i][1] - profile[i-1][1]))
    total = max(acc[-1], 1e-6)
    sx = -1.0 if mirror else 1.0
    for i, (x, r, _) in enumerate(profile):
        if r < 1e-5:
            verts.append((sx * x, 0.0, 0.0)); ring_idx.append([len(verts)] * seg)
        else:
            row = []
            for j in range(seg):
                a = 2 * math.pi * j / seg
                verts.append((sx * x, r * math.cos(a), r * math.sin(a))); row.append(len(verts))
            ring_idx.append(row)
        trow = []
        for j in range(seg + 1):                   # seam column duplicated in UV space
            tverts.append((j / seg, acc[i] / total * v_scale, 0.0)); trow.append(len(tverts))
        ring_tv.append(trow)
    for i in range(len(profile) - 1):
        mid = profile[i + 1][2] if profile[i][2] == profile[i + 1][2] else max(profile[i][2], profile[i + 1][2])
        A, B = ring_idx[i], ring_idx[i + 1]
        TA, TB = ring_tv[i], ring_tv[i + 1]
        pole_a, pole_b = profile[i][1] < 1e-5, profile[i + 1][1] < 1e-5
        for j in range(seg):
            j1 = (j + 1) % seg
            tri = []
            if not pole_b:
                if not pole_a:
                    tri.append(((A[j], A[j1], B[j]), (TA[j], TA[j + 1], TB[j])))
                tri.append(((A[j1], B[j1], B[j]), (TA[j + 1], TB[j + 1], TB[j])))
            else:
                tri.append(((A[j], A[j1], B[j]), (TA[j], TA[j + 1], TB[j])))
            for f, tf in tri:
                if mirror:                         # mirroring flips handedness -> flip winding
                    f = (f[0], f[2], f[1]); tf = (tf[0], tf[2], tf[1])
                faces.append(f); tfaces.append(tf); mats.append(mid)
    return verts, faces, mats, tverts, tfaces

def _sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def _mul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _norm(a):
    l = math.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]) or 1.0
    return (a[0]/l, a[1]/l, a[2]/l)

def helix_ribbons(mirror=False):
    """Luminous helical strips conforming to the skin (MatID 2). Front: right-hand helix.
    The rear half is the mirror image, i.e. automatically the opposite handedness."""
    verts, faces, mats, tverts, tfaces = [], [], [], [], []
    sx = -1.0 if mirror else 1.0
    du = 1e-3
    for k in range(N_STRIPS):
        th0 = 2 * math.pi * k / N_STRIPS
        base = len(verts)
        for s in range(RIB_SAMPLES + 1):
            t = s / RIB_SAMPLES
            u = RIB_U0 + (RIB_U1 - RIB_U0) * t
            th = th0 + 2 * math.pi * TURNS * t
            def P(uu, tt):
                x, r = skin_point(uu)
                return (x, r * math.cos(tt), r * math.sin(tt))
            x, r = skin_point(u)
            x2, r2 = skin_point(min(u + du, 1.0))
            n2d = _norm((-(r2 - r), (x2 - x), 0.0))          # outward profile normal (x, r)
            N = _norm((n2d[0], n2d[1] * math.cos(th), n2d[1] * math.sin(th)))
            H = P(u, th)
            dth = 2 * math.pi * TURNS / (RIB_U1 - RIB_U0)   # d(theta)/du
            T = _norm(_sub(P(u + du, th + dth * du), H))
            Bv = _norm(_cross(N, T))
            fade = min(1.0, t / 0.035, (1.0 - t) / 0.035)     # short taper at ribbon ends
            fade = fade * fade * (3 - 2 * fade)
            w = 0.5 * RIB_WIDTH * max(fade, 0.3)
            Hl = _add(H, _mul(N, RIB_LIFT))
            for side in (-1.0, 1.0):
                v = _add(Hl, _mul(Bv, side * w))
                verts.append((sx * v[0], v[1], v[2]))
                tverts.append((t, 0.0 if side < 0 else 1.0, float(k) / N_STRIPS))
        for s in range(RIB_SAMPLES):
            a, b = base + 2 * s + 1, base + 2 * s + 2      # 1-based
            c, d = base + 2 * s + 3, base + 2 * s + 4
            f1, f2 = (a, c, b), (b, c, d)
            if mirror:
                f1, f2 = (a, b, c), (b, d, c)
            faces += [f1, f2]; tfaces += [f1, f2]; mats += [2, 2]
    return verts, faces, mats, tverts, tfaces

def merge(*parts):
    V, F, M, TV, TF = [], [], [], [], []
    for v, f, m, tv, tf in parts:
        ov, otv = len(V), len(TV)
        V += v; TV += tv; M += m
        F += [(a + ov, b + ov, c + ov) for a, b, c in f]
        TF += [(a + otv, b + otv, c + otv) for a, b, c in tf]
    return V, F, M, TV, TF

def fix_ribbon_winding(verts, faces):
    """Ensure ribbon faces point away from the drone axis (robust against helix direction)."""
    out = []
    for f in faces:
        p0, p1, p2 = (verts[i - 1] for i in f)
        n = _cross(_sub(p1, p0), _sub(p2, p0))
        c = _mul(_add(_add(p0, p1), p2), 1.0 / 3.0)
        radial = (0.0, c[1], c[2])
        out.append(f if (n[1] * radial[1] + n[2] * radial[2]) >= 0 else (f[0], f[2], f[1]))
    return out

def build_mesh(name, data, mat, smooth_deg=32.0):
    V, F, M, TV, TF = data
    m = rt.mesh(vertices=[rt.Point3(*v) for v in V],
                faces=[rt.Point3(*f) for f in F],
                materialIDs=M,
                tverts=[rt.Point3(*t) for t in TV])
    rt.buildTVFaces(m)
    for i, tf in enumerate(TF):
        rt.setTVFace(m, i + 1, rt.Point3(*tf))
    rt.meshop.autoSmooth(m, rt.execute("#{1..%d}" % len(F)), smooth_deg)
    m.name = name
    m.material = mat
    m.pivot = rt.Point3(0, 0, 0)
    rt.update(m)
    return m

def multimat(name, sub_names, colors):
    mm = rt.Multimaterial(numsubs=len(sub_names))
    mm.name = name
    for i, (n, c) in enumerate(zip(sub_names, colors)):
        sm = rt.PhysicalMaterial()
        sm.name = n
        sm.base_color = rt.Color(*c)
        mm.materialList[i] = sm
        mm.names[i] = n
    return mm

# ----------------------------------------------------------------------------- build
for n in NAMES:
    node = rt.getNodeByName(n)
    if node is not None:
        rt.delete(node)

hull_mat  = multimat("MM_SubDrone_Attacker_Hull", ["Hull", "SpiralGlow"], [(38, 52, 64), (90, 220, 255)])
core_mat  = multimat("MM_SubDrone_Attacker_Core", ["CoreBody", "CoreCoils"], [(30, 34, 40), (120, 200, 255)])
torp_mat  = multimat("MM_MicroTorpedo", ["TorpedoBody", "TorpedoGlow"], [(150, 160, 170), (120, 230, 255)])

prof = hull_profile()
front_hull = lathe(prof, SEG, mirror=False)
rear_hull  = lathe(prof, SEG, mirror=True)
rf = helix_ribbons(mirror=False); rf = (rf[0], fix_ribbon_winding(rf[0], rf[1]), rf[2], rf[3], rf[4])
rr = helix_ribbons(mirror=True);  rr = (rr[0], fix_ribbon_winding(rr[0], rr[1]), rr[2], rr[3], rr[4])

front = build_mesh(NAMES[0], merge(front_hull, rf), hull_mat)
rear  = build_mesh(NAMES[1], merge(rear_hull, rr), hull_mat)

# ---- generator core (stator): spindle + hub with coil windings (MatID 2 on coil crowns)
xs = GAP_HALF + BOWL_DEPTH + 0.4
core_prof = [(-xs, 0.0, 1), (-xs, 4.4, 1), (-4.8, 4.4, 1), (-4.8, 7.4, 1)]
n_coils = 7
x_a, x_b = -4.2, 4.2
for k in range(n_coils):
    c0 = x_a + (x_b - x_a) * k / n_coils
    c1 = x_a + (x_b - x_a) * (k + 1) / n_coils
    w = c1 - c0
    core_prof += [(c0 + 0.12 * w, 7.6, 1), (c0 + 0.22 * w, 8.7, 2), (c0 + 0.78 * w, 8.7, 2), (c0 + 0.88 * w, 7.6, 1)]
core_prof += [(4.8, 7.4, 1), (4.8, 4.4, 1), (xs, 4.4, 1), (xs, 0.0, 1)]
core = build_mesh(NAMES[2], lathe(core_prof, 48), core_mat, smooth_deg=40.0)

# ---- micro-torpedo: needle with flat cavitator disc (nose +X), glowing band + nozzle
T = TORP_HALF
torp_prof = [(T, 0.0, 1), (T, 0.17, 1), (T - 0.15, 0.21, 1),
             (T - 0.9, 0.26, 1), (T - 1.9, 0.34, 1), (T - 2.9, 0.42, 1), (T - 3.7, 0.47, 1), (T - 4.5, 0.50, 1),
             (-3.2, 0.50, 1), (-3.25, 0.53, 2), (-4.05, 0.53, 2), (-4.1, 0.50, 1),
             (-4.8, 0.42, 1), (-5.3, 0.33, 1), (-T, 0.29, 1), (-T, 0.0, 2)]
torp = build_mesh(NAMES[3], lathe(torp_prof, TORP_SEG), torp_mat, smooth_deg=40.0)

def bbox(o):
    a, b = o.min, o.max
    return [round(a.x, 2), round(a.y, 2), round(a.z, 2), round(b.x, 2), round(b.y, 2), round(b.z, 2)]

report = {}
for o in (front, rear, core, torp):
    report[o.name] = {"verts": int(o.numverts), "tris": int(o.numfaces), "bbox_cm": bbox(o),
                      "pivot": [o.pivot.x, o.pivot.y, o.pivot.z]}
result = report
