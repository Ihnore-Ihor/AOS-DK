# =============================================================================
# AOS-DK | Hero Asset #4 | SM_Cargo_Pod_Phys  (3ds Max 2027, pymxs)
# Pressurized Heavy Salvage Cargo Pod - primary movable physics actor (Master Overview 7.2,
# Req #2 4th custom model + Req #3 pushable / buoyant cargo container).
# Units: cm. Max space: +X = pod long axis (FRONT = +X), +Z up. Pivot = hull axis centre (0,0,0).
# UE import maps (x, y, z) -> (x, -y, z).  Azimuth th in YZ from +Y toward +Z.
# Envelope ~400 x 180 x 210 (Shell-1 class footprint 400 x 200 x 200).
# Collision: exactly ONE convex hull UCX_SM_Cargo_Pod_Phys_01, 32 verts:
#   full chassis profile (octagon apothem 90 top + skid feet to Z -118) at X +-172,
#   sharp octagon apothem 88 at X +-200 (tapered bumper noses). Pad-eyes / shackles / valve stay OUTSIDE.
# Re-runnable: removes previous CPOD_* / SM_Cargo_Pod_Phys / UCX_SM_Cargo_Pod_Phys_* objects first.
# Saves the scene to SourceArt/CustomHero/SM_Cargo_Pod_Phys.max and clears the dirty flag.
# Run (build + save):          ns={}; exec(...)
# Run (build + export + save): ns={"CPOD_EXPORT": True}; exec(...)
# Run: ns={}; exec(open(r"<proj>\Tools\max_build_SM_Cargo_Pod_Phys.py", encoding="utf-8").read(), ns); ns["CPOD_RESULT"]
# =============================================================================
from pymxs import runtime as rt
import math, json, os

ASSET = "SM_Cargo_Pod_Phys"
PFX = "CPOD_"
UCX_NAME = "UCX_%s_01" % ASSET
PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
JSON_PATH = os.path.join(PROJ, "Tools", ASSET + "_spec.json")
MAX_PATH = os.path.join(PROJ, "SourceArt", "CustomHero", ASSET + ".max")
FBX_PATH = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "CustomHero", ASSET + ".fbx")
PAINT, CHROME, RUBBER, STATUS = 1, 2, 3, 4
SLOTS = ["MS_PaintSteel_Worn", "MS_HydraulicChrome", "MS_RubberSkid", "MS_StatusEmissive"]

# ---------------------------------------------------------------- layout (cm)
HULL_A, HULL_BEV, HULL_X = 82.0, 4.0, 165.0           # octagonal pressure hull, across flats 164
RIB_A, RIB_XS, RIB_HW = 89.0, [-128.0, -45.0, 45.0, 128.0], 8.0   # chamfered ribs, 7 proud, 16 wide
CAP = [(164.0, 81.5), (170.0, 76.0), (174.0, 60.0), (176.5, 30.0)]  # faceted end dome (|x|, apothem)
FRAME = (176.0, 190.0, 86.0, 64.0)                    # steel bumper frame (x0, x1, apothem out, in)
BUMP = (190.0, 200.0, 80.0, 66.0)                     # rubber impact bumper ring
SADDLE_XS, SADDLE_HW, SADDLE_Y, SADDLE_Z0 = [-105.0, 105.0], 12.0, 74.0, -100.0
RUN_Y, RUN_HW = 62.0, 11.0                            # skid runners Y 51..73
RUN_XZ = [(-148.0, -112.0), (148.0, -112.0), (172.0, -100.0), (172.0, -94.0), (-172.0, -94.0), (-172.0, -100.0)]
PAD = (-140.0, 140.0, 53.0, 71.0, -118.0, -112.0)     # rubber skid pads x0,x1,y0,y1,z0,z1
EYE_X = 152.0                                         # pad-eyes on the upper diagonal faces
HATCH_X, HATCH_R, HATCH_RI = -87.0, 30.0, 23.0        # recessed valve inspection hatch (+Y face)
STATUS_X = 87.0                                       # status emissive plate (-Y face)
TOW_X = 194.0                                         # tow clevis pin axis
# collision (single convex hull)
UCX_A_TOP, UCX_FOOT_Y, UCX_BOT_Z, UCX_X_FULL, UCX_X_END, UCX_A_END = 90.0, 73.0, -118.0, 172.0, 200.0, 88.0
RHO_SW = 1.025                                        # seawater g/cm3
C45 = math.sqrt(0.5)

# ---------------------------------------------------------------- math
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vlen(a): return math.sqrt(a[0]**2 + a[1]**2 + a[2]**2)
def vnorm(a):
    l = vlen(a); return (a[0]/l, a[1]/l, a[2]/l)
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def vdot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def P(a): return rt.Point3(float(a[0]), float(a[1]), float(a[2]))
def mtx(x, y, z, p): return rt.Matrix3(P(x), P(y), P(z), P(p))
def U(th): a = math.radians(th); return (0.0, math.cos(a), math.sin(a))
def T(th): a = math.radians(th); return (0.0, -math.sin(a), math.cos(a))
def at(x, r, th): u = U(th); return (x, r*u[1], r*u[2])

def frame_z(zdir, yhint=(0.0, 1.0, 0.0)):
    z = vnorm(zdir)
    if abs(vdot(z, yhint)) > 0.99: yhint = (0.0, 0.0, 1.0)
    x = vnorm(vcross(yhint, z)); y = vcross(z, x)
    return x, y, z

def mtx_zx(zdir, xdir, p):
    z = vnorm(zdir); x = vnorm(vsub(xdir, vmul(z, vdot(xdir, z)))); y = vcross(z, x)
    return mtx(x, y, z, p)

def oct_poly(a, b=0.0):
    """Octagon (flats at 0/45/../315 deg, top flat at z=a) in YZ, CCW; b = corner bevel length."""
    R = a / math.cos(math.radians(22.5)); side = 2.0 * a * math.tan(math.radians(22.5))
    V = [(R*math.cos(math.radians(22.5 + 45*k)), R*math.sin(math.radians(22.5 + 45*k))) for k in range(8)]
    if b <= 0: return V
    out = []
    for k in range(8):
        v, pv, nv = V[k], V[k-1], V[(k+1) % 8]
        out.append((v[0] + b*(pv[0]-v[0])/side, v[1] + b*(pv[1]-v[1])/side))
        out.append((v[0] + b*(nv[0]-v[0])/side, v[1] + b*(nv[1]-v[1])/side))
    return out

# ---------------------------------------------------------------- primitives
PARTS = []          # (node, core)  core = must be inside the UCX hull
def _finish(n, mat, core):
    n.name = PFX + "%04d" % len(PARTS)
    rt.convertToPoly(n)
    rt.polyop.setFaceMatID(n, rt.Name("all"), mat)
    PARTS.append((n, core))
    return n

def mk_mesh(mat, verts, faces, hints, core=True):
    fs = []
    for f, h in zip(faces, hints):
        a, b, c = verts[f[0]], verts[f[1]], verts[f[2]]
        if vdot(vcross(vsub(b, a), vsub(c, a)), h) < 0: f = (f[0], f[2], f[1])
        fs.append(rt.Point3(f[0]+1, f[1]+1, f[2]+1))
    m = rt.mesh(vertices=[P(v) for v in verts], faces=fs)
    n = _finish(m, mat, core)
    # faceted industrial read: every octagon flat / 45-deg chamfer / bevel (22.5 deg) stays a hard edge
    rt.execute('(local m = getNodeByName "%s"; m.autoSmoothThreshold = 15.0; polyop.setFaceSelection m #all; m.EditablePoly.autosmooth(); polyop.setFaceSelection m #{})' % n.name)
    return n

def convex_rings(mat, rings, core=True):
    """Closed convex solid from N-point rings (same N, consistent order)."""
    n = len(rings[0]); verts = [p for r in rings for p in r]
    cen = vmul(tuple(map(sum, zip(*verts))), 1.0/len(verts))
    faces = []
    for i in range(1, n-1): faces.append((0, i, i+1))
    L = (len(rings)-1)*n
    for i in range(1, n-1): faces.append((L, L+i, L+i+1))
    for r in range(len(rings)-1):
        for i in range(n):
            a, b = r*n + i, r*n + (i+1) % n
            faces += [(a, b, b+n), (a, b+n, a+n)]
    hints = [vsub(vmul(vadd(vadd(verts[f[0]], verts[f[1]]), verts[f[2]]), 1/3.0), cen) for f in faces]
    return mk_mesh(mat, verts, faces, hints, core)

def loft_x(mat, stations, core=True):
    return convex_rings(mat, [[(x, y, z) for (y, z) in poly] for (x, poly) in stations], core)

def prism_x(mat, poly_yz, x0, x1, core=True): return loft_x(mat, [(x0, poly_yz), (x1, poly_yz)], core)
def prism_y(mat, poly_xz, y0, y1, core=True):
    return convex_rings(mat, [[(x, y0, z) for (x, z) in poly_xz], [(x, y1, z) for (x, z) in poly_xz]], core)

def tube_x(mat, x0, x1, pout, pin, core=True):
    n = len(pout)
    verts = [(x0, y, z) for (y, z) in pout] + [(x1, y, z) for (y, z) in pout] + \
            [(x0, y, z) for (y, z) in pin] + [(x1, y, z) for (y, z) in pin]
    faces, hints = [], []
    sx = 1.0 if x1 > x0 else -1.0
    for i in range(n):
        j = (i+1) % n
        o0, o1, i0, i1 = i, n+i, 2*n+i, 3*n+i
        p0, p1, q0, q1 = j, n+j, 2*n+j, 3*n+j
        rad = (0.0, verts[o0][1] + verts[p0][1], verts[o0][2] + verts[p0][2])
        faces += [(o0, p0, p1), (o0, p1, o1)]; hints += [rad, rad]
        faces += [(i0, q0, q1), (i0, q1, i1)]; hints += [vmul(rad, -1), vmul(rad, -1)]
        faces += [(o0, p0, q0), (o0, q0, i0)]; hints += [(-sx, 0, 0)]*2
        faces += [(o1, p1, q1), (o1, q1, i1)]; hints += [(sx, 0, 0)]*2
    return mk_mesh(mat, verts, faces, hints, core)

def obox(mat, p0, p1, wn, ws, nvec=(1.0, 0.0, 0.0), fil=1.0, seg=1, core=True):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(wn, ws, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false"
                   % (wn, ws, h, f, seg))
    n.transform = mtx_zx(d, nvec, p0)
    return _finish(n, mat, core)

def ccyl(mat, p0, p1, r, sides=24, fil=0.8, seg=1, core=True):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(r, h))
    n = rt.execute("ChamferCyl radius:%f height:%f fillet:%f Fillet_Segments:%d sides:%d Height_Segments:1 Cap_Segments:1 smoothOn:true mapcoords:false"
                   % (r, h, f, seg, sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, mat, core)

def tube(mat, r_in, r_out, p0, p1, sides=32, core=True):
    d = vsub(p1, p0)
    n = rt.execute("Tube radius1:%f radius2:%f height:%f sides:%d heightsegs:1 capsegs:1 smooth:true mapcoords:false"
                   % (r_out, r_in, vlen(d), sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, mat, core)

def torus(mat, c, axis, r1, r2, segs=24, sides=16, core=False):
    n = rt.execute("Torus radius1:%f radius2:%f segs:%d sides:%d smooth:2 mapcoords:false" % (r1, r2, segs, sides))
    x, y, z = frame_z(axis); n.transform = mtx(x, y, z, c)
    return _finish(n, mat, core)

# ---------------------------------------------------------------- geometry
SOCK = {}
def build_geometry():
    hp = oct_poly(HULL_A, HULL_BEV)
    # ---- pressure hull + faceted end domes
    loft_x(PAINT, [(-HULL_X, hp), (HULL_X, hp)])
    for sx in (-1.0, 1.0):
        loft_x(PAINT, [(sx*x, oct_poly(a, min(HULL_BEV, 0.3*a*math.tan(math.radians(22.5))*2))) for (x, a) in CAP])
    # ---- chamfered structural ribs (7 proud, 45-deg chamfers)
    for xr in RIB_XS:
        loft_x(PAINT, [(xr - RIB_HW, oct_poly(HULL_A - 1.0, HULL_BEV)), (xr - RIB_HW + 3.0, oct_poly(RIB_A, HULL_BEV)),
                       (xr + RIB_HW - 3.0, oct_poly(RIB_A, HULL_BEV)), (xr + RIB_HW, oct_poly(HULL_A - 1.0, HULL_BEV))])
    # ---- end assemblies: gussets, steel bumper frame + cross, rubber impact ring, tow clevis
    for sx in (-1.0, 1.0):
        for th in (45.0, 135.0, 225.0, 315.0):
            obox(PAINT, at(sx*166.0, 66.0, th), at(sx*(FRAME[0] + 2.0), 66.0, th), 8.0, 14.0, T(th), fil=1.0)
        tube_x(PAINT, sx*FRAME[0], sx*FRAME[1], oct_poly(FRAME[2], 4.0), oct_poly(FRAME[3], 3.0))
        tube_x(RUBBER, sx*BUMP[0], sx*BUMP[1], oct_poly(BUMP[2], 5.0), oct_poly(BUMP[3], 3.0))
        xm = sx*183.0
        obox(PAINT, (xm, -65.0, 0), (xm, 65.0, 0), 10.0, 14.0, (1, 0, 0), fil=1.5)      # horizontal bar
        obox(PAINT, (xm, 0, -65.0), (xm, 0, 65.0), 10.0, 14.0, (1, 0, 0), fil=1.5)      # vertical bar
        obox(PAINT, (sx*177.0, 0, 0), (sx*188.0, 0, 0), 30.0, 30.0, (0, 1, 0), fil=2.0)  # hitch block
        for sz in (-1.0, 1.0):
            obox(CHROME, (sx*186.0, 0, sz*9.5), (sx*198.0, 0, sz*9.5), 18.0, 5.0, (0, 1, 0), fil=1.0)   # clevis cheek
            ccyl(CHROME, (sx*TOW_X, 0, sz*12.0), (sx*TOW_X, 0, sz*14.0), 5.5, sides=16)              # pin heads
        ccyl(CHROME, (sx*TOW_X, 0, -13.0), (sx*TOW_X, 0, 13.0), 3.5, sides=16)                      # tow pin
    SOCK["SOCKET_Tow_Front"] = {"pos": (TOW_X, 0, 0), "x": (1, 0, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_Tow_Rear"] = {"pos": (-TOW_X, 0, 0), "x": (-1, 0, 0), "z": (0, 0, 1)}

    # ---- cradle saddles (follow the lower octagon) + skid runners + rubber skid pads
    s = HULL_A * math.tan(math.radians(22.5))                       # half flat 33.97
    zd = lambda y: abs(y) - (HULL_A + s)                            # lower diagonal face z(y)
    for xs in SADDLE_XS:
        x0, x1 = xs - SADDLE_HW, xs + SADDLE_HW
        prism_x(PAINT, [(-s, SADDLE_Z0), (s, SADDLE_Z0), (s, -HULL_A + 1.0), (-s, -HULL_A + 1.0)], x0, x1)
        for sy in (-1.0, 1.0):
            w = [(sy*SADDLE_Y, SADDLE_Z0), (sy*s, SADDLE_Z0), (sy*s, -HULL_A + 1.0), (sy*SADDLE_Y, zd(SADDLE_Y) + 1.0)]
            if sy < 0: w = w[::-1]
            prism_x(PAINT, w, x0, x1)
    for sy in (-1.0, 1.0):
        prism_y(PAINT, RUN_XZ, sy*(RUN_Y - RUN_HW), sy*(RUN_Y + RUN_HW))
        y0, y1 = sy*PAD[2], sy*PAD[3]
        prism_x(RUBBER, [(min(y0, y1), PAD[4]), (max(y0, y1), PAD[4]), (max(y0, y1), PAD[5] + 0.5), (min(y0, y1), PAD[5] + 0.5)], PAD[0], PAD[1])

    # ---- 4 heavy pad-eyes + tow shackles on the upper diagonal faces (VISUAL ONLY, outside UCX)
    lifts = []
    for sx in (1.0, -1.0):
        for sy in (1.0, -1.0):
            n = (0.0, sy*C45, C45); t = (0.0, C45, -sy*C45)
            p = vmul(n, HULL_A); p = (sx*EYE_X, p[1], p[2])
            obox(PAINT, vadd(p, vmul(n, -1.0)), vadd(p, vmul(n, 3.0)), 26.0, 30.0, (1, 0, 0), fil=1.0)   # doubler (core)
            obox(PAINT, vadd(p, vmul(n, 3.0)), vadd(p, vmul(n, 14.0)), 22.0, 7.0, (1, 0, 0), fil=1.5, core=False)  # lug cheek
            ce = vadd(p, vmul(n, 20.0))
            torus(PAINT, ce, t, 9.0, 3.5)                                         # forged eye
            torus(CHROME, vadd(p, vmul(n, 28.0)), (1, 0, 0), 8.0, 2.2)            # D-shackle bow
            for k in (-1.0, 1.0):                                                 # shackle pin bosses
                ccyl(CHROME, vadd(vadd(p, vmul(n, 22.0)), vmul(t, k*7.0)), vadd(vadd(p, vmul(n, 22.0)), vmul(t, k*10.5)), 3.0, sides=12, core=False)
            tag = ("F" if sx > 0 else "R") + ("L" if sy > 0 else "R")
            SOCK["SOCKET_Lift_" + tag] = {"pos": ce, "x": n, "z": (1, 0, 0)}

    # ---- recessed valve inspection hatch (+Y face) with pressure-relief valve
    hx, fy = HATCH_X, HULL_A
    tube(PAINT, HATCH_RI, HATCH_R, (hx, fy - 1.0, 0), (hx, fy + 6.0, 0), sides=32)          # coaming
    ccyl(PAINT, (hx, fy - 1.0, 0), (hx, fy + 1.5, 0), HATCH_RI, sides=32, fil=0.5)          # recessed cover
    tube(RUBBER, HATCH_RI - 1.5, HATCH_RI + 0.2, (hx, fy + 1.5, 0), (hx, fy + 2.5, 0), sides=32)  # seal
    for k in range(12):
        a = math.radians(k * 30.0 + 15.0)
        b = (hx + 26.5*math.cos(a), fy + 6.0, 26.5*math.sin(a))
        ccyl(CHROME, b, vadd(b, (0, 1.8, 0)), 1.6, sides=6, fil=0.3)
    vb = (hx, fy + 1.5, 0)
    ccyl(CHROME, vb, (hx, fy + 10.0, 0), 5.5, sides=16, core=False)                          # valve body
    ccyl(CHROME, (hx, fy + 10.0, 0), (hx, fy + 13.0, 0), 3.5, sides=16, core=False)          # bonnet
    ccyl(CHROME, (hx, fy + 13.0, 0), (hx, fy + 16.0, 0), 1.2, sides=8, core=False)           # stem
    torus(CHROME, (hx, fy + 15.5, 0), (0, 1, 0), 8.0, 1.3, sides=12)                         # handwheel
    obox(CHROME, (hx - 8.0, fy + 15.5, 0), (hx + 8.0, fy + 15.5, 0), 1.6, 1.6, (0, 1, 0), fil=0.3, core=False)
    obox(CHROME, (hx, fy + 15.5, -8.0), (hx, fy + 15.5, 8.0), 1.6, 1.6, (0, 1, 0), fil=0.3, core=False)
    ccyl(CHROME, (hx, fy + 7.0, 0), (hx, fy + 7.0, 13.0), 2.4, sides=12, core=False)        # relief outlet pipe
    ccyl(CHROME, (hx, fy + 7.0, 13.0), (hx, fy + 7.0, 17.0), 3.2, sides=12, core=False)     # relief nozzle
    SOCK["SOCKET_VFX_Leak_00"] = {"pos": (hx, fy + 7.0, 17.0), "x": (0, 0, 1), "z": (0, 1, 0)}

    # ---- magnetic latching plate (top flat, salvage retrieval) with status strips
    obox(PAINT, (0, 0, HULL_A - 1.0), (0, 0, HULL_A + 2.0), 64.0, 52.0, (1, 0, 0), fil=1.0)
    obox(CHROME, (0, 0, HULL_A + 2.0), (0, 0, HULL_A + 4.0), 56.0, 40.0, (1, 0, 0), fil=0.5)
    for sy in (-1.0, 1.0):
        obox(STATUS, (0, sy*23.0, HULL_A + 2.0), (0, sy*23.0, HULL_A + 3.0), 56.0, 2.5, (1, 0, 0), fil=0.3)
    SOCK["SOCKET_MagLatch"] = {"pos": (0, 0, HULL_A + 4.0), "x": (0, 0, 1), "z": (1, 0, 0)}

    # ---- status emissive plate (-Y face)
    obox(PAINT, (STATUS_X, -HULL_A + 1.0, 0), (STATUS_X, -HULL_A - 3.0, 0), 50.0, 30.0, (1, 0, 0), fil=1.0)
    obox(STATUS, (STATUS_X, -HULL_A - 3.0, 0), (STATUS_X, -HULL_A - 4.0, 0), 42.0, 22.0, (1, 0, 0), fil=0.3)
    for (ox, oz) in ((-22, -12), (22, -12), (-22, 12), (22, 12)):
        ccyl(CHROME, (STATUS_X + ox, -HULL_A - 3.0, oz), (STATUS_X + ox, -HULL_A - 4.2, oz), 1.4, sides=6, fil=0.2)

# ---------------------------------------------------------------- collision: single convex hull
def full_profile():
    R = UCX_A_TOP / math.cos(math.radians(22.5))
    up = [(R*math.cos(math.radians(a)), R*math.sin(math.radians(a))) for a in (-22.5, 22.5, 67.5, 112.5, 157.5, 202.5)]
    return [(UCX_FOOT_Y, UCX_BOT_Z)] + up + [(-UCX_FOOT_Y, UCX_BOT_Z)]

def hull3d(pts, eps=1e-3):
    n = len(pts); planes = []
    for i in range(n):
        for j in range(i+1, n):
            for k in range(j+1, n):
                nv = vcross(vsub(pts[j], pts[i]), vsub(pts[k], pts[i])); l = vlen(nv)
                if l < 1e-6: continue
                nv = vmul(nv, 1.0/l); d = vdot(nv, pts[i])
                sd = [vdot(nv, p) - d for p in pts]
                if max(sd) <= eps: pass
                elif min(sd) >= -eps: nv, d = vmul(nv, -1.0), -d
                else: continue
                if any(vdot(nv, q[0]) > 0.99999 and abs(d - q[1]) < 1e-2 for q in planes): continue
                planes.append((nv, d))
    faces = []
    for (nv, d) in planes:
        idx = [i for i, p in enumerate(pts) if abs(vdot(nv, p) - d) < 1e-2]
        c = vmul(tuple(map(sum, zip(*[pts[i] for i in idx]))), 1.0/len(idx))
        u = vnorm(vsub(pts[idx[0]], c)); w = vcross(nv, u)
        idx.sort(key=lambda i: math.atan2(vdot(vsub(pts[i], c), w), vdot(vsub(pts[i], c), u)))
        for m in range(1, len(idx)-1): faces.append((idx[0], idx[m], idx[m+1]))
    return planes, faces

def build_collision():
    fp, ep = full_profile(), oct_poly(UCX_A_END)
    pts = [(-UCX_X_END, y, z) for (y, z) in ep] + [(-UCX_X_FULL, y, z) for (y, z) in fp] + \
          [(UCX_X_FULL, y, z) for (y, z) in fp] + [(UCX_X_END, y, z) for (y, z) in ep]
    planes, faces = hull3d(pts)
    m = rt.mesh(vertices=[P(p) for p in pts], faces=[rt.Point3(f[0]+1, f[1]+1, f[2]+1) for f in faces])
    m.name = UCX_NAME; m.wirecolor = rt.Color(255, 60, 60)
    vol = sum(vdot(pts[f[0]], vcross(pts[f[1]], pts[f[2]])) for f in faces) / 6.0
    return m, pts, planes, faces, vol

# ---------------------------------------------------------------- MaxScript helpers
MXS = r'''
global cpod_uv
fn cpod_uv m = (
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
    ov
)
'''

def settle_ui():
    """Leave the Modify panel (the UV step opened it) and flush posted UI messages BEFORE saving;
    otherwise the deferred panel refresh re-flags the scene as modified after the call returns."""
    rt.execute("max create mode")
    rt.windows.processPostedMessages()
    rt.completeRedraw()
    rt.windows.processPostedMessages()

def merge(nodes):
    lvl = list(nodes)
    while len(lvl) > 1:
        nxt = []
        for i in range(0, len(lvl), 24):
            base = lvl[i]
            for p in lvl[i+1:i+24]: rt.polyop.attach(base, p)
            nxt.append(base)
        lvl = nxt
    return lvl[0]

def own(o):
    nm = str(o.name)
    return nm.startswith(PFX) or nm == ASSET or nm.startswith("UCX_" + ASSET)

def prepare_scene():
    if str(rt.units.SystemType) != "centimeters" or abs(float(rt.units.SystemScale) - 1.0) > 1e-6:
        rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    cur = os.path.join(str(rt.maxFilePath), str(rt.maxFileName))
    foreign = [o for o in rt.objects if not own(o)]
    if foreign and os.path.normcase(cur) != os.path.normcase(MAX_PATH):
        if rt.getSaveRequired():
            raise RuntimeError("Scene has unsaved foreign content (%s) - save it first; build aborted." % cur)
        rt.resetMaxFile(rt.Name("noPrompt"))
    for o in [o for o in rt.objects if own(o)]:
        try: rt.delete(o)
        except Exception: pass

# ---------------------------------------------------------------- build
def build():
    del PARTS[:]; SOCK.clear()
    prepare_scene()
    rt.execute(MXS)
    out = {"max_units": str(rt.units.SystemType)}
    MM = rt.execute('''(
        local mm = MultiMaterial numsubs:4 name:"MM_Cargo_Pod_Phys"
        mm.materialList[1] = PhysicalMaterial name:"MS_PaintSteel_Worn" base_color:(color 232 148 28) metalness:0.15 roughness:0.62
        mm.materialList[2] = PhysicalMaterial name:"MS_HydraulicChrome" base_color:(color 204 207 209) metalness:1.0 roughness:0.08
        mm.materialList[3] = PhysicalMaterial name:"MS_RubberSkid" base_color:(color 18 18 20) metalness:0.0 roughness:0.85
        mm.materialList[4] = PhysicalMaterial name:"MS_StatusEmissive" base_color:(color 0 0 0) emit_color:(color 80 250 123) emission:6.0
        mm.names = #("MS_PaintSteel_Worn", "MS_HydraulicChrome", "MS_RubberSkid", "MS_StatusEmissive")
        mm )''')
    build_geometry()
    ucx, upts, planes, ufaces, vol = build_collision()

    # ---- per-part coverage: core parts must be inside the single hull, details are reported
    def inside(v, tol=0.5): return all(vdot(n, v) - d <= tol for (n, d) in planes)
    core_out, det_out, det_tot, samples = 0, 0, 0, []
    cmin, cmax = [1e9]*3, [-1e9]*3
    for (node, core) in PARTS:
        nv = int(rt.polyop.getNumVerts(node))
        for i in range(1, nv + 1):
            pv = rt.polyop.getVert(node, i); v = (float(pv.x), float(pv.y), float(pv.z))
            if core:
                for a in range(3): cmin[a] = min(cmin[a], v[a]); cmax[a] = max(cmax[a], v[a])
                if not inside(v):
                    core_out += 1
                    if len(samples) < 6: samples.append([str(node.name)] + [round(c, 1) for c in v])
            else:
                det_tot += 1
                if not inside(v): det_out += 1
    nparts = len(PARTS); ncore = sum(1 for p in PARTS if p[1])
    grp = merge([p[0] for p in PARTS])
    final = rt.Editable_Mesh(); final.name = ASSET
    rt.convertToPoly(final)
    rt.polyop.attach(final, grp)
    final.material = MM                      # smoothing: per part (custom solids 15 deg, primitives keep their own)
    out["uv_overlapping_faces"] = int(rt.cpod_uv(final))
    lay = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay.addnode(final); lay.addnode(ucx)

    # ---- socket reference helpers (NOT exported; UE step reads the JSON)
    rl = rt.LayerManager.getLayerFromName("CPOD_Ref_Sockets") or rt.LayerManager.newLayerFromName("CPOD_Ref_Sockets")
    for k, sd in SOCK.items():
        x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
        pt = rt.Point(name=PFX + "REF_" + k, size=20, box=True, cross=True, axistripod=True)
        pt.transform = mtx(x, y, z, sd["pos"]); pt.wirecolor = rt.Color(255, 40, 160)
        rl.addnode(pt)

    tm = rt.snapshotAsMesh(final)
    mat_ids = sorted(set(int(rt.getFaceMatID(tm, i)) for i in range(1, int(tm.numfaces) + 1)))
    ux = [p[0] for p in upts]; uy = [p[1] for p in upts]; uz = [p[2] for p in upts]
    fp = full_profile()
    area = 0.5*abs(sum(fp[i][0]*fp[(i+1) % len(fp)][1] - fp[(i+1) % len(fp)][0]*fp[i][1] for i in range(len(fp))))
    out.update({
        "parts": nparts, "core_parts": ncore, "verts": int(tm.numverts), "tris": int(tm.numfaces), "mat_ids": mat_ids,
        "bbox_min": [round(float(final.min.x), 1), round(float(final.min.y), 1), round(float(final.min.z), 1)],
        "bbox_max": [round(float(final.max.x), 1), round(float(final.max.y), 1), round(float(final.max.z), 1)],
        "core_bbox_min": [round(c, 1) for c in cmin], "core_bbox_max": [round(c, 1) for c in cmax],
        "ucx_name": UCX_NAME, "ucx_count": 1, "ucx_verts": int(rt.getNumVerts(ucx)), "ucx_tris": len(ufaces), "ucx_planes": len(planes),
        "ucx_bbox_min": [min(ux), min(uy), min(uz)], "ucx_bbox_max": [max(ux), max(uy), max(uz)],
        "ucx_volume_m3": round(vol / 1e6, 4), "ucx_full_section_m2": round(area / 1e4, 4),
        "displaced_mass_kg": round(vol * RHO_SW / 1000.0, 1),
        "core_verts_outside_ucx": core_out, "core_outside_samples": samples,
        "detail_verts_total": det_tot, "detail_verts_outside_ucx": det_out,
        "sockets": sorted(SOCK.keys()),
    })
    spec = {"asset": ASSET, "units": "cm",
            "space": "3ds Max RH Z-up, +X = pod front; UE import maps (x, y, z) -> (x, -y, z)",
            "slots": SLOTS, "ucx_name": UCX_NAME,
            "ucx_points": [[round(c, 3) for c in p] for p in upts],
            "sockets": {k: {"pos": [round(c, 3) for c in v["pos"]], "x": [round(c, 6) for c in v["x"]], "z": list(v["z"])} for k, v in SOCK.items()},
            "stats": out}
    with open(JSON_PATH, "w") as f: json.dump(spec, f, indent=2)

    # ---- explicit scene save + clear dirty flag
    rt.select(final); rt.selectMore(ucx)
    settle_ui()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)
    out["max_saved"] = MAX_PATH if os.path.exists(MAX_PATH) else None
    out["dirty_after_save"] = bool(rt.getSaveRequired())
    return out                                     # selection left = render mesh + UCX (ready for export_fbx)

def export_and_resave():
    """Optional in-script FBX export (AOS preset: cm, Z-up, smoothing groups, no anim, binary).
    The FBX exporter flags the scene dirty, so the .max is saved again and the flag cleared."""
    rt.select(rt.getNodeByName(ASSET)); rt.selectMore(rt.getNodeByName(UCX_NAME))
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
    ok = rt.exportFile(FBX_PATH, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
    settle_ui()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)
    return {"fbx": FBX_PATH if ok and os.path.exists(FBX_PATH) else None,
            "fbx_bytes": os.path.getsize(FBX_PATH) if os.path.exists(FBX_PATH) else 0,
            "dirty_after_export_save": bool(rt.getSaveRequired())}

GUARD_MXS = r'''
global cpod_guard_timer
fn cpod_guard_tick s e = (
    s.Stop()
    if (maxFilePath + maxFileName) == @"%s" and getSaveRequired() do
        saveMaxFile (maxFilePath + maxFileName) clearNeedSaveFlag:true useNewFile:true quiet:true
    setSaveRequired false
    dotNet.removeAllEventHandlers s
)
cpod_guard_timer = dotNetObject "System.Windows.Forms.Timer"
cpod_guard_timer.Interval = 1500
dotNet.addEventHandler cpod_guard_timer "Tick" cpod_guard_tick
cpod_guard_timer.Start()
''' % MAX_PATH

def arm_dirty_guard():
    """3ds Max 2027 re-flags the freshly built scene as modified once its UI idles after the call returns
    (deferred panel / scene-explorer refresh). A one-shot UI-thread timer re-saves the unchanged scene
    and clears the flag 1.5 s later, so the session ends clean."""
    rt.execute(GUARD_MXS)

CPOD_RESULT = build()
if globals().get("CPOD_EXPORT", False):        # ns={"CPOD_EXPORT": True} -> build + export + re-save in one call
    CPOD_RESULT["export"] = export_and_resave()
arm_dirty_guard()
