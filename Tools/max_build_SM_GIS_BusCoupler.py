# =============================================================================
# AOS-DK | Hero Asset #3 | SM_GIS_BusCoupler  (3ds Max 2027, pymxs)
# Trunk GIS busduct segment D-1..D-6 (scaled IEC 62271-203), Tower A Spatial Bible §2.4.
# Units: cm. Max space: +X = busduct axis (traversal), +Z up. UE import maps (x, y, z) -> (x, -y, z).
# Azimuth θ is measured in YZ from +Y toward +Z:  u(θ) = (0, cosθ, sinθ),  t(θ) = (0, -sinθ, cosθ).
# Coaxial: enclosure OD 8000 / ID 7700 (wall 150), conductor Ø2830 = ID/e, annulus gap 2435 (class C3).
# Segment 6000 between flange faces (X ±3000). Conical support insulator at mid-segment:
#   6 epoxy spokes on a 26° cone + corona collar; 6 large windows (lanes) between the spokes.
# Collision: 16 UCX staves (22.5°) + 1 UCX 16-gon conductor prism + 6 UCX spoke hulls = 23, simple only.
# Re-runnable: deletes previous GISB_* / UCX_SM_GIS_BusCoupler_* / helper objects first.
# Run: ns={}; exec(open(r"<proj>\Tools\max_build_SM_GIS_BusCoupler.py").read(), ns); ns["GISB_RESULT"]
# =============================================================================
from pymxs import runtime as rt
import math, json, os

ASSET = "SM_GIS_BusCoupler"
PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
JSON_PATH = os.path.join(PROJ, "Tools", ASSET + "_spec.json")
CAST, COND, INS, STATUS = 1, 2, 3, 4
SLOTS = ["MS_CastAluminum", "MS_Conductor", "MS_Insulator", "MS_Status"]

# ---------------------------------------------------------------- layout (cm)
X0, X1 = -3000.0, 3000.0                 # flange mating faces (segment 6000)
R_OUT, R_IN = 4000.0, 3850.0             # enclosure OD 8000, wall 150, ID 7700
R_COND = 1415.0                          # conductor Ø2830 = 7700 / e
FL_R, FL_T = 4400.0, 120.0               # flange OD + 800, thickness 120
BOLT_N, BOLT_RC = 96, 4200.0             # 96 bolts Ø120 per flange
FIN_N, FIN_T, FIN_R0, FIN_R1, FIN_X = 64, 80.0, 3990.0, 4300.0, 2700.0   # fins 80 x 300, pitch ~393
X_HUB, X_FOOT = 600.0, -600.0            # cone: spoke axis at u=1400 -> X_HUB, at u=3870 -> X_FOOT
U_ROOT, U_TIP = 1400.0, 3870.0
SPOKE_AZ = [60.0*k for k in range(6)]
WIN_AZ = [30.0 + 60.0*k for k in range(6)]
SPOKE_W, SPOKE_T = 520.0, 180.0
HUB_R, HUB_L = 1470.0, 500.0             # corona collar (epoxy hub cast on the conductor)
SHIELD_R, SHIELD_L = 1455.0, 260.0       # conductor plug-in contact shields at both ends
HATCHES = [(0.0, -1400.0), (180.0, 1400.0)]      # (azimuth, x) — Ø300 hatches, 2 per segment
LAMP_X = 2400.0                          # interior lane beacons (x = ±2400, at window azimuths)
# collision
STAVE_OUT_A = 4480.0                     # outer apothem (encloses flange OD 4400, boss, hatches)
COND_A = 1475.0                          # conductor prism apothem (conductor + collar + shields)
SP_HW, SP_U0, SP_U1, SP_AX0, SP_AX1 = 400.0, 1350.0, 3920.0, 250.0, 330.0
SHELL = (400.0, 200.0, 200.0)
SHELL_R = math.sqrt((SHELL[0]/2)**2 + (SHELL[1]/2)**2 + (SHELL[2]/2)**2)   # 244.9: any orientation

def xc(uu): return X_HUB + (uu - U_ROOT) * (X_FOOT - X_HUB) / (U_TIP - U_ROOT)

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
def ring(r, deg): a = math.radians(deg); return (r*math.cos(a), r*math.sin(a))

def frame_z(zdir, yhint=(0.0, 1.0, 0.0)):
    z = vnorm(zdir)
    if abs(vdot(z, yhint)) > 0.99: yhint = (0.0, 0.0, 1.0)
    x = vnorm(vcross(yhint, z)); y = vcross(z, x)
    return x, y, z

def mtx_zx(zdir, xdir, p):
    z = vnorm(zdir); x = vnorm(vsub(xdir, vmul(z, vdot(xdir, z)))); y = vcross(z, x)
    return mtx(x, y, z, p)

# ---------------------------------------------------------------- primitives
PARTS = []
def _finish(n, mat):
    n.name = "GISB_%04d" % len(PARTS)
    rt.convertToPoly(n)
    rt.polyop.setFaceMatID(n, rt.Name("all"), mat)
    PARTS.append(n)
    return n

def obox(mat, p0, p1, wn, ws, nvec=(1.0, 0.0, 0.0), fil=2.0, seg=2):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(wn, ws, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false"
                   % (wn, ws, h, f, seg))
    n.transform = mtx_zx(d, nvec, p0)
    return _finish(n, mat)

def ccyl(mat, p0, p1, r, sides=24, fil=1.5, seg=2):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(r, h))
    n = rt.execute("ChamferCyl radius:%f height:%f fillet:%f Fillet_Segments:%d sides:%d Height_Segments:1 Cap_Segments:1 smoothOn:true mapcoords:false"
                   % (r, h, f, seg, sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, mat)

def tube(mat, r_in, r_out, p0, p1, sides=64):
    d = vsub(p1, p0)
    n = rt.execute("Tube radius1:%f radius2:%f height:%f sides:%d heightsegs:1 capsegs:1 smooth:true mapcoords:false"
                   % (r_out, r_in, vlen(d), sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, mat)

def nut(p, axis, r=95.0, h=90.0, stud_r=60.0, stud_h=50.0):
    e = vadd(p, vmul(axis, h))
    ccyl(CAST, p, e, r, sides=6, fil=6.0, seg=1)
    ccyl(CAST, e, vadd(e, vmul(axis, stud_h)), stud_r, sides=8, fil=4.0, seg=1)

# ---------------------------------------------------------------- fins keep-out (az centre, half-angle, x0, x1)
KEEP = [(0.0, 8.0, -1800.0, -1000.0), (180.0, 8.0, 1000.0, 1800.0), (90.0, 19.0, -1300.0, 1300.0)]
def angdiff(a, b): return abs((a - b + 180.0) % 360.0 - 180.0)

# ---------------------------------------------------------------- geometry
SOCK = {}
def build_geometry():
    # ---- enclosure + flanges
    tube(CAST, R_IN, R_OUT, (X0 + FL_T, 0, 0), (X1 - FL_T, 0, 0), sides=128)
    tube(CAST, R_IN, FL_R, (X0, 0, 0), (X0 + FL_T, 0, 0), sides=128)
    tube(CAST, R_IN, FL_R, (X1 - FL_T, 0, 0), (X1, 0, 0), sides=128)
    for k in range(BOLT_N):                                   # nuts + stud ends on flange back faces
        th = (k + 0.5) * 360.0 / BOLT_N
        nut(at(X0 + FL_T, BOLT_RC, th), (1.0, 0, 0))
        nut(at(X1 - FL_T, BOLT_RC, th), (-1.0, 0, 0))

    # ---- longitudinal cooling fins (80 x 300), split around hatches and the RD boss
    nfin = 0
    for k in range(FIN_N):
        th = (k + 0.5) * 360.0 / FIN_N
        segs = [(-FIN_X, FIN_X)]
        for (ac, ha, xa, xb) in KEEP:
            if angdiff(th, ac) <= ha:
                nxt = []
                for (s0, s1) in segs:
                    if s1 <= xa or s0 >= xb: nxt.append((s0, s1)); continue
                    if s0 < xa: nxt.append((s0, xa))
                    if s1 > xb: nxt.append((xb, s1))
                segs = nxt
        rm = (FIN_R0 + FIN_R1) / 2.0
        for (s0, s1) in segs:
            if s1 - s0 < 200.0: continue
            obox(CAST, at(s0, rm, th), at(s1, rm, th), FIN_T, FIN_R1 - FIN_R0, T(th), fil=6.0, seg=1)
            nfin += 1

    # ---- conductor + contact shields
    ccyl(COND, (X0 + 5, 0, 0), (X1 - 5, 0, 0), R_COND, sides=96, fil=5.0, seg=1)
    ccyl(COND, (X0, 0, 0), (X0 + SHIELD_L, 0, 0), SHIELD_R, sides=96, fil=20.0, seg=3)
    ccyl(COND, (X1 - SHIELD_L, 0, 0), (X1, 0, 0), SHIELD_R, sides=96, fil=20.0, seg=3)

    # ---- conical support insulator: corona collar + 6 spokes (sheds, root boots, foot pads)
    ccyl(INS, (X_HUB - HUB_L/2, 0, 0), (X_HUB + HUB_L/2, 0, 0), HUB_R, sides=96, fil=45.0, seg=4)
    for th in SPOKE_AZ:
        t = T(th)
        p0, p1 = at(xc(U_ROOT), U_ROOT, th), at(xc(U_TIP), U_TIP, th)
        obox(INS, p0, p1, SPOKE_W, SPOKE_T, t, fil=25.0, seg=2)
        d = vnorm(vsub(p1, p0))
        for uu in (2000.0, 2600.0, 3200.0):                   # epoxy sheds
            c = at(xc(uu), uu, th)
            obox(INS, vsub(c, vmul(d, 20.0)), vadd(c, vmul(d, 20.0)), SPOKE_W + 120, SPOKE_T + 120, t, fil=8.0, seg=2)
        obox(INS, at(xc(1430.0), 1380.0, th), at(xc(1430.0), 1490.0, th), 760.0, 400.0, t, fil=20.0, seg=2)   # root boot
        xf = xc(3850.0)
        obox(CAST, at(xf, 3790.0, th), at(xf, 3880.0, th), 760.0, 520.0, t, fil=8.0, seg=1)                 # foot pad
        for (ot, ox) in ((-300, -180), (300, -180), (-300, 180), (300, 180)):
            b = vadd(at(xf + ox, 3790.0, th), vmul(t, ot))
            ccyl(CAST, b, vadd(b, vmul(U(th), -25.0)), 25.0, sides=6, fil=2.0, seg=1)

    # ---- inspection hatches Ø300 (2 per segment) + hatch status lamps
    for i, (th, hx) in enumerate(HATCHES):
        u, t = U(th), T(th)
        ccyl(CAST, at(hx, 3880.0, th), at(hx, 4180.0, th), 200.0, sides=32, fil=6.0)
        ccyl(CAST, at(hx, 4180.0, th), at(hx, 4230.0, th), 280.0, sides=32, fil=6.0)
        ccyl(CAST, at(hx, 4230.0, th), at(hx, 4265.0, th), 215.0, sides=32, fil=6.0)
        for k in range(12):
            a = math.radians(k * 30.0 + 15.0)
            b = vadd(at(hx + 248.0*math.cos(a), 4230.0, th), vmul(t, 248.0*math.sin(a)))
            ccyl(CAST, b, vadd(b, vmul(u, 25.0)), 14.0, sides=6, fil=1.5, seg=1)
        for s in (-90.0, 90.0):
            ccyl(CAST, at(hx + s, 4262.0, th), at(hx + s, 4300.0, th), 10.0, sides=8, fil=1.0, seg=1)
        ccyl(CAST, at(hx - 100.0, 4300.0, th), at(hx + 100.0, 4300.0, th), 11.0, sides=8, fil=1.0, seg=1)
        lx = hx + 320.0
        ccyl(CAST, at(lx, 3960.0, th), at(lx, 4090.0, th), 45.0, sides=16, fil=4.0)
        ccyl(STATUS, at(lx, 4090.0, th), at(lx, 4110.0, th), 35.0, sides=16, fil=4.0)
        SOCK["SOCKET_Inspection_Hatch_%02d" % i] = {"pos": at(hx, 4265.0, th), "x": u, "z": (1, 0, 0)}

    # ---- pressure-relief boss at 12 o'clock — RD-16 rupture disc interface (blind/intact variant)
    ccyl(CAST, (0, 0, 3870.0), (0, 0, 4250.0), 1000.0, sides=64, fil=10.0)
    ccyl(CAST, (0, 0, 4250.0), (0, 0, 4330.0), 1100.0, sides=64, fil=8.0)
    ccyl(CAST, (0, 0, 4325.0), (0, 0, 4342.0), 800.0, sides=64, fil=3.0)        # intact disc membrane
    tube(CAST, 800.0, 930.0, (0, 0, 4330.0), (0, 0, 4365.0), sides=64)          # retaining ring
    for k in range(24):
        b = (1010.0*math.cos(math.radians(k*15.0 + 7.5)), 1010.0*math.sin(math.radians(k*15.0 + 7.5)), 4330.0)
        ccyl(CAST, b, (b[0], b[1], 4365.0), 30.0, sides=6, fil=3.0, seg=1)
    for sy in (-1.0, 1.0):                                                       # side gussets
        obox(CAST, (0, sy*1090.0, 3780.0), (0, sy*1090.0, 4250.0), 60.0, 180.0, (1, 0, 0), fil=4.0)
    for sx in (-1.0, 1.0):                                                       # boss status lamps
        ccyl(CAST, (sx*995.0, 0, 4080.0), (sx*1065.0, 0, 4080.0), 60.0, sides=16, fil=4.0)
        ccyl(STATUS, (sx*1065.0, 0, 4080.0), (sx*1085.0, 0, 4080.0), 45.0, sides=16, fil=4.0)
    SOCK["SOCKET_RuptureDisc_Mount"] = {"pos": (0, 0, 4342.0), "x": (0, 0, 1), "z": (1, 0, 0)}

    # ---- interior lane beacons (status emissive), 6 per end, at window azimuths
    for x in (-LAMP_X, LAMP_X):
        for th in WIN_AZ:
            ccyl(CAST, at(x, 3880.0, th), at(x, 3830.0, th), 70.0, sides=16, fil=4.0)
            ccyl(STATUS, at(x, 3830.0, th), at(x, 3822.0, th), 55.0, sides=16, fil=2.0)

    # ---- arc electrodes: triple junction (conductor / epoxy collar / gas) on the collar front face,
    #      in the 4 diagonal windows (45/135/225/315). +X = radial outward (arc toward the enclosure).
    for i, th in enumerate((45.0, 135.0, 225.0, 315.0)):
        SOCK["SOCKET_Arc_Electrode_%02d" % (i + 1)] = {"pos": at(X_HUB - HUB_L/2 - 5.0, R_COND + 5.0, th), "x": U(th), "z": (1, 0, 0)}
    # ---- modular snapping (flange faces, +X outward)
    SOCK["SOCKET_Snap_Front"] = {"pos": (X0, 0, 0), "x": (-1, 0, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_Snap_Rear"] = {"pos": (X1, 0, 0), "x": (1, 0, 0), "z": (0, 0, 1)}
    return nfin

# ---------------------------------------------------------------- collision (UCX convex, <= 32 verts)
UCX = []
def ucx_rings(bot, top, label):
    n = len(bot); pts = list(bot) + list(top)
    faces = []
    for i in range(1, n-1): faces.append((1, i+2, i+1))
    for i in range(1, n-1): faces.append((n+1, n+i+1, n+i+2))
    for i in range(n):
        a, b = i+1, (i+1) % n + 1
        faces.append((a, b, n+b)); faces.append((a, n+b, n+a))
    m = rt.mesh(vertices=[P(p) for p in pts], faces=[rt.Point3(*f) for f in faces])
    m.name = "UCX_%s_%02d" % (ASSET, len(UCX))
    m.wirecolor = rt.Color(255, 60, 60)
    UCX.append((m, label, pts, faces))
    return m

def ucx_prism_x(poly_yz, x0, x1, label):
    return ucx_rings([(x0, y, z) for (y, z) in poly_yz], [(x1, y, z) for (y, z) in poly_yz], label)

def build_collision():
    h = 11.25; c = math.cos(math.radians(h))
    ro = STAVE_OUT_A / c
    for k in range(16):                        # staves centred at 22.5k: inner verts on the bore (R_IN)
        th = 22.5 * k
        ucx_prism_x([ring(R_IN, th - h), ring(ro, th - h), ring(ro, th + h), ring(R_IN, th + h)],
                    X0, X1, "enclosure_stave_%02d" % k)
    rv = COND_A / c
    ucx_prism_x([ring(rv, h + 22.5*i) for i in range(16)], X0, X1, "conductor_prism16")
    for j, th in enumerate(SPOKE_AZ):          # spoke hulls: root rect (u 1350) -> tip rect (u 3920)
        t = T(th)
        def rect(uu, ax):
            cc = at(xc(uu), uu, th)
            return [vadd(cc, (sx*ax, sy*SP_HW*t[1], sy*SP_HW*t[2])) for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        ucx_rings(rect(SP_U0, SP_AX0), rect(SP_U1, SP_AX1), "insulator_spoke_%02d" % j)

# ---------------------------------------------------------------- analytic helpers
def hull2d(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2: return pts
    def cr(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

def dist_pt_poly(q, poly):
    inside = True; best = 1e18; n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i+1) % n]
        ex, ey = b[0]-a[0], b[1]-a[1]
        if ex*(q[1]-a[1]) - ey*(q[0]-a[0]) < 0: inside = False
        t = max(0.0, min(1.0, ((q[0]-a[0])*ex + (q[1]-a[1])*ey) / (ex*ex + ey*ey)))
        best = min(best, math.hypot(a[0] + t*ex - q[0], a[1] + t*ey - q[1]))
    return 0.0 if inside else best

def planes(pts, faces):
    cen = vmul(tuple(map(sum, zip(*pts))), 1.0/len(pts)); out = []
    for f in faces:
        a, b, c = pts[f[0]-1], pts[f[1]-1], pts[f[2]-1]
        n = vcross(vsub(b, a), vsub(c, a)); l = vlen(n)
        if l < 1e-6: continue
        n = vmul(n, 1.0/l); d = vdot(n, a)
        if vdot(n, cen) - d > 0: n, d = vmul(n, -1.0), -d
        out.append((n, d))
    return out

# ---------------------------------------------------------------- MaxScript helpers
MXS = r'''
global gisb_uv
fn gisb_uv m = (
    max modify mode
    select m
    local uv = Unwrap_UVW()
    addModifier m uv
    modPanel.setCurrentObject uv
    uv.setMapChannel 1
    uv.flattenMap 50.0 #() 0.002 true 0 false true
    uv.selectOverlappedFaces()
    local ov = (uv.getSelectedFaces()).numberSet
    collapseStack m
    ov
)
'''

def merge(parts):
    lvl = list(parts)
    while len(lvl) > 1:
        nxt = []
        for i in range(0, len(lvl), 24):
            base = lvl[i]
            for p in lvl[i+1:i+24]: rt.polyop.attach(base, p)
            nxt.append(base)
        lvl = nxt
    return lvl[0]

def clean_scene():
    dead = [o for o in rt.objects if str(o.name).startswith("GISB_") or str(o.name) == ASSET
            or str(o.name).startswith("UCX_" + ASSET)]
    for o in dead:
        try: rt.delete(o)
        except Exception: pass

# ---------------------------------------------------------------- build
def build():
    del PARTS[:]; del UCX[:]; SOCK.clear()
    clean_scene()
    rt.execute(MXS)
    out = {"max_units": str(rt.units.SystemType), "max_scale": float(rt.units.SystemScale)}
    MM = rt.execute('''(
        local mm = MultiMaterial numsubs:4 name:"MM_GIS_BusCoupler"
        mm.materialList[1] = PhysicalMaterial name:"MS_CastAluminum" base_color:(color 150 154 158) metalness:1.0 roughness:0.45
        mm.materialList[2] = PhysicalMaterial name:"MS_Conductor" base_color:(color 242 163 138) metalness:1.0 roughness:0.15
        mm.materialList[3] = PhysicalMaterial name:"MS_Insulator" base_color:(color 196 186 160) metalness:0.0 roughness:0.35
        mm.materialList[4] = PhysicalMaterial name:"MS_Status" base_color:(color 0 0 0) emit_color:(color 20 230 255) emission:6.0
        mm.names = #("MS_CastAluminum", "MS_Conductor", "MS_Insulator", "MS_Status")
        mm )''')
    nfin = build_geometry()
    nparts = len(PARTS)
    grp = merge(PARTS)
    final = rt.Editable_Mesh(); final.name = ASSET
    rt.convertToPoly(final)
    rt.polyop.attach(final, grp)
    final.material = MM
    rt.execute('(local m = getNodeByName "%s"; m.autoSmoothThreshold = 45.0; polyop.setFaceSelection m #all; m.EditablePoly.autosmooth(); polyop.setFaceSelection m #{})' % ASSET)
    out["uv_overlapping_faces"] = int(rt.gisb_uv(final))
    build_collision()
    lay = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay.addnode(final)
    for u_ in UCX: lay.addnode(u_[0])

    # ---- lanes: largest circle inscribed in each window (YZ), against every UCX projection
    polys = [hull2d([(round(p[1], 4), round(p[2], 4)) for p in pts]) for (_, _, pts, _) in UCX]
    lanes = []
    for th in WIN_AZ:
        best = (0.0, 0.0)
        for i in range(0, 1201):
            rho = 1500.0 + i * 2.0
            q = ring(rho, th)
            d = min(dist_pt_poly(q, pg) for pg in polys)
            if d > best[0]: best = (d, rho)
        lanes.append({"az": th, "rho": best[1], "centre_yz": [round(v, 2) for v in ring(best[1], th)], "radius": round(best[0], 2)})
    LANE_R = min(l["radius"] for l in lanes)
    ucx_rep = []
    for k, (m, label, pts, _) in enumerate(UCX):
        clr = min(dist_pt_poly(tuple(l["centre_yz"]), polys[k]) - l["radius"] for l in lanes)
        ucx_rep.append({"name": str(m.name), "part": label, "verts": int(rt.getNumVerts(m)), "lane_clearance_cm": round(clr, 2)})
    sp_x = [p[0] for (_, lab, pts, _) in UCX if lab.startswith("insulator") for p in pts]
    ring_band = {"x_insulator_band": [round(min(sp_x), 1), round(max(sp_x), 1)],
                 "r_inner": round(COND_A / math.cos(math.radians(11.25)), 1),
                 "r_outer": round(R_IN * math.cos(math.radians(11.25)), 1)}
    ring_band["radial_width"] = round(ring_band["r_outer"] - ring_band["r_inner"], 1)

    # ---- render-vertex checks: lanes, ring band, simple-collision coverage
    hulls = []
    for (m, lab, pts, faces) in UCX:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
        hulls.append(((min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)), planes(pts, faces)))
    def covered(v, tol=0.5):
        for (bb, pl) in hulls:
            if not (bb[0]-tol <= v[0] <= bb[1]+tol and bb[2]-tol <= v[1] <= bb[3]+tol and bb[4]-tol <= v[2] <= bb[5]+tol): continue
            if all(vdot(n, v) - d <= tol for (n, d) in pl): return True
        return False
    tm = rt.snapshotAsMesh(final)
    nv = int(tm.numverts)
    in_lane = in_band = unc_in = unc_out = 0; unc_samples = []
    lane_c = [tuple(l["centre_yz"]) for l in lanes]
    for i in range(1, nv + 1):
        pv = rt.getVert(tm, i); v = (float(pv.x), float(pv.y), float(pv.z))
        r = math.hypot(v[1], v[2])
        if any(math.hypot(v[1]-c[0], v[2]-c[1]) < LANE_R - 0.5 for c in lane_c): in_lane += 1
        if (v[0] < ring_band["x_insulator_band"][0] or v[0] > ring_band["x_insulator_band"][1]) and ring_band["r_inner"] < r < ring_band["r_outer"]:
            in_band += 1
        if r < R_IN - 0.5 or r > R_OUT + 0.5:
            if not covered(v):
                if r < R_IN: unc_in += 1
                else: unc_out += 1
                if len(unc_samples) < 5: unc_samples.append([round(c, 1) for c in v])
    mat_ids = sorted(set(int(rt.getFaceMatID(tm, i)) for i in range(1, int(tm.numfaces) + 1)))

    # ---- socket reference helpers (NOT exported; UE step reads the JSON)
    rl = rt.LayerManager.getLayerFromName("GISB_Ref_Sockets") or rt.LayerManager.newLayerFromName("GISB_Ref_Sockets")
    SOCK["SOCKET_Nav_Conduit_In"] = {"pos": (X0, lane_c[1][0], lane_c[1][1]), "x": (1, 0, 0), "z": (0, 0, 1)}   # lane 1 = 12 o'clock
    SOCK["SOCKET_Nav_Conduit_Out"] = {"pos": (X1, lane_c[1][0], lane_c[1][1]), "x": (1, 0, 0), "z": (0, 0, 1)}
    for k, sd in SOCK.items():
        x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
        pt = rt.Point(name="GISB_REF_" + k, size=150, box=True, cross=True, axistripod=True)
        pt.transform = mtx(x, y, z, sd["pos"]); pt.wirecolor = rt.Color(255, 40, 160)
        rl.addnode(pt)

    out.update({
        "parts": nparts, "fins": nfin, "verts": nv, "tris": int(tm.numfaces), "mat_ids": mat_ids,
        "bbox_min": [round(float(final.min.x), 1), round(float(final.min.y), 1), round(float(final.min.z), 1)],
        "bbox_max": [round(float(final.max.x), 1), round(float(final.max.y), 1), round(float(final.max.z), 1)],
        "lanes": lanes, "lane_radius_min": LANE_R, "shell_bounding_sphere_r": round(SHELL_R, 1),
        "lane_margin_cm": round(LANE_R - SHELL_R, 1), "ring_band": ring_band,
        "render_verts_in_lanes": in_lane, "render_verts_in_ring_band": in_band,
        "render_verts_uncovered_interior": unc_in, "render_verts_uncovered_exterior": unc_out, "uncovered_samples": unc_samples,
        "ucx": ucx_rep, "ucx_count": len(UCX), "ucx_max_verts": max(u["verts"] for u in ucx_rep),
        "ucx_min_lane_clearance": min(u["lane_clearance_cm"] for u in ucx_rep),
    })
    spec = {"asset": ASSET, "units": "cm",
            "space": "3ds Max RH Z-up, +X busduct axis; UE import maps (x, y, z) -> (x, -y, z)",
            "slots": SLOTS, "shell": list(SHELL), "shell_r": SHELL_R,
            "sockets": {k: {"pos": [round(c, 3) for c in v["pos"]], "x": list(v["x"]), "z": list(v["z"])} for k, v in SOCK.items()},
            "lanes": lanes, "ring_band": ring_band, "spoke_az": SPOKE_AZ,
            "stats": {k: v for k, v in out.items() if k not in ("lanes", "ring_band")}}
    with open(JSON_PATH, "w") as f: json.dump(spec, f, indent=2)
    rt.select(final)
    for u_ in UCX: rt.selectMore(u_[0])
    return out

GISB_RESULT = build()
