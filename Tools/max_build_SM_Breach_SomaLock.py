# =============================================================================
# AOS-DK | Hero Asset #2 | SM_Breach_SomaLock  (3ds Max 2027, pymxs)
# Deformed SOMA-type armoured lock, Breach Type 2 (Tower A Spatial Bible §3.2).
# Units: cm. Max space: +X = traversal axis (Shell forward, entry at -X), +Z up,
#   +Y = door slide direction (pocket side). UE import maps (x, y, z) -> (x, -y, z).
# Leaf: Ø860 x 80 titanium disc JAMMED at 60 % travel (offset 516 along +Y).
# Free lens (YZ): bore circle R410 minus leaf circle R430 @ y=516
#   -> inscribed circle Ø496 centred at y = -162  (class C1, Shell-1 200x200 section).
# Collision: UCX convex hulls only (<= 32 verts each); the lens prism (infinite along X)
#   is verified analytically to be free of every hull projection.
# Re-runnable: deletes previous SOMA_/UCX_/socket helper objects first.
# Run: exec(open(r"<proj>\Tools\max_build_SM_Breach_SomaLock.py").read(), ns); ns["SOMA_RESULT"]
# =============================================================================
from pymxs import runtime as rt
import math, json, os

ASSET = "SM_Breach_SomaLock"
PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
JSON_PATH = os.path.join(PROJ, "Tools", "SM_Breach_SomaLock_spec.json")
ARMOR, HYD, SEAL, STATUS = 1, 2, 3, 4
SLOTS = ["MS_Armor", "MS_Hydraulic", "MS_Seal", "MS_Status"]

# ---------------------------------------------------------------- layout (cm)
R_BORE, R_FRAME = 410.0, 600.0          # frames: OD 1200, bore Ø820
X_IN, X_OUT, FRAME_T = -420.0, 420.0, 120.0
R_CH_IN, R_CH_OUT = 415.0, 480.0        # chamber shell (recessed 5 behind the bore)
R_LEAF, LEAF_OFF = 430.0, 516.0         # leaf Ø860, jammed at 60 % travel
X_LF0, X_LF1 = -510.0, -430.0           # leaf slab (80) in front of entry frame (+10 seal gap)
LEAF_C = (LEAF_OFF, 0.0)                # leaf centre in YZ
PK_X0, PK_X1, PK_Y0, PK_Y1, PK_Z = -545.0, -420.0, 440.0, 1320.0, 450.0
LENS_Y = ((LEAF_OFF - R_LEAF) - R_BORE) / 2.0      # -162
LENS_R = ((LEAF_OFF - R_LEAF) + R_BORE) / 2.0      # 248  (Ø496)
CYL_X = -600.0                          # hydraulic actuator axis plane
CYL_R, ROD_R = 22.5, 11.0               # Ø45 / Ø22 (bible)
LUG_Y = 370.0
NAV_X_IN, NAV_X_OUT = -900.0, 700.0
SHELL = (400.0, 200.0, 200.0)

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

def frame_z(zdir, yhint=(0.0, 1.0, 0.0)):
    z = vnorm(zdir)
    if abs(vdot(z, yhint)) > 0.99: yhint = (0.0, 0.0, 1.0)
    x = vnorm(vcross(yhint, z)); y = vcross(z, x)
    return x, y, z

def mtx_zx(zdir, xdir, p):              # local Z along zdir, local X ~ xdir (orthogonalised)
    z = vnorm(zdir); x = vnorm(vsub(xdir, vmul(z, vdot(xdir, z)))); y = vcross(z, x)
    return mtx(x, y, z, p)

def ring(r, deg, c=(0.0, 0.0)):         # YZ point, angle from +Y toward +Z
    a = math.radians(deg); return (c[0] + r*math.cos(a), c[1] + r*math.sin(a))

def X3(x, yz): return (x, yz[0], yz[1])

# ---------------------------------------------------------------- primitives
PARTS = []
def _finish(n, mat):
    n.name = "SOMA_%04d" % len(PARTS)
    rt.convertToPoly(n)
    rt.polyop.setFaceMatID(n, rt.Name("all"), mat)
    PARTS.append(n)
    return n

def cbox(mat, x0, x1, y0, y1, z0, z1, fil=2.0, seg=2):
    w, l, h = x1-x0, y1-y0, z1-z0
    f = min(fil, 0.4*min(w, l, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false pos:[%f,%f,%f]"
                   % (w, l, h, f, seg, (x0+x1)/2.0, (y0+y1)/2.0, z0))
    return _finish(n, mat)

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

def tube_x(mat, r_in, r_out, x0, x1, sides=64, c=(0.0, 0.0)):
    n = rt.execute("Tube radius1:%f radius2:%f height:%f sides:%d heightsegs:1 capsegs:1 smooth:true mapcoords:false"
                   % (r_out, r_in, x1-x0, sides))
    n.transform = mtx_zx((1, 0, 0), (0, 0, 1), (x0, c[0], c[1]))
    return _finish(n, mat)

def torus_x(mat, R, r, x, c=(0.0, 0.0), segs=72, sides=12):
    n = rt.execute("Torus radius1:%f radius2:%f segs:%d sides:%d smooth:2 mapcoords:false" % (R, r, segs, sides))
    n.transform = mtx_zx((1, 0, 0), (0, 0, 1), (x, c[0], c[1]))
    return _finish(n, mat)

def bolt(x_face, yz, dirx=-1.0, r=11.0, h=10.0):
    ccyl(ARMOR, (x_face, yz[0], yz[1]), (x_face + dirx*h, yz[0], yz[1]), r, sides=6, fil=0.8, seg=1)

def sheared_bolt(x_face, yz, dirx=-1.0, r=11.0):
    p0 = (x_face, yz[0], yz[1]); p1 = (x_face + dirx*4.0, yz[0] + 3.0, yz[1] - 2.0)
    ccyl(ARMOR, p0, p1, r*0.55, sides=8, fil=0.4, seg=1)

def hose(pts, r=4.5):
    n = rt.soma_hose([P(p) for p in pts], float(r))
    return _finish(n, SEAL)

# ---------------------------------------------------------------- occlusion for face bolts (YZ boxes)
OCC = [(-60-15, 405+15, 438-15, 470+15), (-60-15, 405+15, -470-15, -438+15),   # rails
       (400, 1400, -490, 490),                                                    # pocket housing + lip
       (-430, -300, -420, -310)]                                                  # terminal plate
def occluded(yz, door=False):
    y, z = yz
    for (y0, y1, z0, z1) in OCC:
        if y0 <= y <= y1 and z0 <= z <= z1: return True
    r = math.hypot(y, z); a = math.degrees(math.atan2(z, y)) % 360
    if 505 <= r <= 590 and 95 <= a <= 175: return True                           # light bar
    if door and math.hypot(y - LEAF_C[0], z - LEAF_C[1]) < R_LEAF + 15: return True
    return False

# ---------------------------------------------------------------- geometry
SOCK = {}
def build_geometry():
    # ---- frames (OD 1200, t 120, bore Ø820) + chamber shell (length 600)
    tube_x(ARMOR, R_BORE, R_FRAME, X_IN, X_IN + FRAME_T)
    tube_x(ARMOR, R_BORE, R_FRAME, X_OUT - FRAME_T, X_OUT)
    tube_x(ARMOR, R_CH_IN, R_CH_OUT, X_IN + FRAME_T, X_OUT - FRAME_T)
    for x in (-150.0, 0.0, 150.0):                                   # hoop stiffeners
        tube_x(ARMOR, R_CH_OUT, 530.0, x - 15, x + 15)
    for k in range(12):                                              # radial gussets frame-to-frame
        th = 15.0 + 30.0*k; t = (0.0, -math.sin(math.radians(th)), math.cos(math.radians(th)))
        rc = ring(540.0, th)
        if k == 2:   # hull-stress buckled gusset (two segments, kinked outward)
            mid = X3(0.0, ring(565.0, th + 4))
            obox(ARMOR, X3(-300.0, rc), mid, 20, 110, t)
            obox(ARMOR, mid, X3(300.0, rc), 20, 110, t)
        else:
            obox(ARMOR, X3(-300.0, rc), X3(300.0, rc), 20, 120, t)
    # interior seam seals (inner R411 > bore 410, recessed chamber at 415)
    tube_x(SEAL, 411.0, 418.0, X_IN + FRAME_T, X_IN + FRAME_T + 12)
    tube_x(SEAL, 411.0, 418.0, X_OUT - FRAME_T - 12, X_OUT - FRAME_T)
    # bore pressure seals on both frame faces (thick rubber, inner 413)
    torus_x(SEAL, 425.0, 12.0, X_IN)
    torus_x(SEAL, 425.0, 12.0, X_OUT)

    # ---- bolted flanges (entry face: some sheared)
    for k in range(36):
        yz = ring(565.0, k*10.0 + 5.0)
        bolt(X_OUT, yz, +1.0)
        if occluded(yz): continue
        (sheared_bolt if k % 7 == 3 else bolt)(X_IN, yz, -1.0)
    for k in range(24):
        yz = ring(470.0, k*15.0 + 7.5)
        if not occluded(yz, door=True): bolt(X_IN, yz, -1.0, r=9.0, h=8.0)
        bolt(X_OUT, yz, +1.0, r=9.0, h=8.0)

    # ---- titanium leaf, jammed at 60 % (offset 516)
    ccyl(ARMOR, (X_LF0, LEAF_C[0], 0.0), (X_LF1, LEAF_C[0], 0.0), R_LEAF, sides=72, fil=4.0, seg=2)
    torus_x(SEAL, 398.0, 8.0, X_LF0, LEAF_C)
    torus_x(SEAL, 398.0, 6.0, X_LF1, LEAF_C)
    for th in (140.0, 165.0, 195.0, 220.0):                         # radial ribs (visible sector)
        d0, d1 = ring(150.0, th, LEAF_C), ring(388.0, th, LEAF_C)
        t = (0.0, -math.sin(math.radians(th)), math.cos(math.radians(th)))
        obox(ARMOR, X3(X_LF0 - 6, d0), X3(X_LF0 - 6, d1), 12, 26, (1, 0, 0))
        obox(ARMOR, X3(X_LF1 + 4, d0), X3(X_LF1 + 4, d1), 8, 22, (1, 0, 0))
    for k in range(13):
        yz = ring(372.0, 120.0 + k*10.0, LEAF_C)
        if yz[0] < 400: bolt(X_LF0, yz, -1.0, r=8.0, h=7.0)
    # leading-edge armour band on the leaf face (stays inside the leaf circle)
    for th in (150.0, 180.0, 210.0):
        obox(ARMOR, X3(X_LF0 - 5, ring(405.0, th - 14, LEAF_C)), X3(X_LF0 - 5, ring(405.0, th + 14, LEAF_C)), 10, 30, (1, 0, 0))

    # ---- guide rails (top / bottom), bolted
    for s in (1.0, -1.0):
        z0, z1 = (438.0, 470.0) if s > 0 else (-470.0, -438.0)
        cbox(ARMOR, -535.0, -420.0, -60.0, 405.0, z0, z1, fil=3.0)
        for y in (-20.0, 120.0, 260.0, 380.0):
            bolt(-535.0, (y, s*454.0), -1.0, r=7.0, h=6.0)

    # ---- reinforced door pocket 900 x 900 (slot 100 + armour)
    cbox(ARMOR, PK_X0, PK_X1, PK_Y0, PK_Y1, -PK_Z, PK_Z, fil=6.0, seg=3)
    for y in (620.0, 860.0, 1100.0):                                 # vertical ribs
        cbox(ARMOR, -565.0, PK_X0, y - 15, y + 15, -PK_Z, PK_Z, fil=3.0)
    for s in (1.0, -1.0):                                            # top / bottom bolted flange bands
        z0, z1 = (PK_Z, PK_Z + 25) if s > 0 else (-PK_Z - 25, -PK_Z)
        cbox(ARMOR, -560.0, -420.0, PK_Y0, PK_Y1 + 25, z0, z1, fil=3.0)
        for y in range(480, 1320, 80):
            bolt(-560.0, (float(y), s*(PK_Z + 12.5)), -1.0, r=7.0, h=6.0)
    cbox(ARMOR, -560.0, -420.0, PK_Y1, PK_Y1 + 25, -PK_Z, PK_Z, fil=3.0)  # rear end plate
    # mouth: rubber wiper seals + lip; upper lip half BUCKLED into the leaf path (jam cause)
    cbox(SEAL, -522.0, -510.0, 426.0, 442.0, -415.0, 415.0, fil=4.0)
    cbox(SEAL, -430.0, -420.0, 426.0, 442.0, -415.0, 415.0, fil=3.0)
    cbox(ARMOR, -570.0, -522.0, 400.0, 440.0, -470.0, 0.0, fil=3.0)
    obox(ARMOR, (-546.0, 420.0, 0.0), (-552.0, 352.0, 465.0), 48, 40, (1, 0, 0), fil=3.0)
    obox(ARMOR, (-546.0, 420.0, -10.0), (-546.0, 418.0, 10.0), 50, 44, (1, 0, 0))   # crack weld knuckle
    # stencil plate + central hydraulic manifold on pocket face
    cbox(ARMOR, -575.0, -565.0, 900.0, 1060.0, -40.0, 40.0, fil=1.5)
    cbox(HYD, -590.0, -545.0, 1140.0, 1240.0, -70.0, 70.0, fil=4.0)

    # ---- hydraulic actuators (Ø45 cylinder, Ø22 rod) driving the leaf through door lugs
    for s in (1.0, -1.0):
        zc = s*300.0
        cbox(ARMOR, -625.0, X_LF0, LUG_Y - 25, LUG_Y + 25, zc - 20, zc + 20, fil=4.0)          # leaf lug
        ccyl(HYD, (CYL_X, LUG_Y, zc - 26), (CYL_X, LUG_Y, zc + 26), 9.0, sides=16)            # clevis pin
        cbox(ARMOR, -632.0, PK_X0, 1262.0, 1310.0, zc - 42, zc + 42, fil=4.0)                  # trunnion bracket
        ccyl(ARMOR, (CYL_X, 1260.0, zc), (CYL_X, 1290.0, zc), 30.0, sides=24, fil=3.0)         # end cap
        ccyl(HYD, (CYL_X - 33, 1286.0, zc), (CYL_X + 33, 1286.0, zc), 8.0, sides=12)           # trunnion pin

    # TOP (z+300): BENT / buckled from hull stress
    zc = 300.0
    kink = (CYL_X, 980.0, zc)
    fr = (-640.0, 700.0, zc + 18.0)
    ccyl(HYD, (CYL_X, 1260.0, zc), kink, CYL_R, sides=24)
    ccyl(ARMOR, (CYL_X, 995.0, zc), (CYL_X, 965.0, zc), CYL_R + 6, sides=24, fil=2)        # cracked collar
    ccyl(HYD, kink, fr, CYL_R, sides=24)
    gl = vadd(fr, vmul(vnorm(vsub(fr, kink)), 30.0))
    ccyl(ARMOR, fr, gl, CYL_R + 5, sides=24, fil=2)                                           # rod gland
    rk = (-668.0, 540.0, zc + 30.0)
    ccyl(HYD, gl, rk, ROD_R, sides=16)
    ccyl(HYD, rk, (CYL_X, LUG_Y, zc), ROD_R, sides=16)
    ccyl(HYD, vadd(rk, (0, 8, 0)), vadd(rk, (0, -8, 0)), ROD_R + 3, sides=16)              # buckle knuckle
    hose([(CYL_X, 1225.0, zc + 22), (CYL_X + 10, 1215.0, zc + 70), (-580.0, 1195.0, 150.0), (-585.0, 1200.0, 70.0)])
    hose([(CYL_X - 25, 730.0, zc + 34), (-650.0, 820.0, zc + 80), (-610.0, 1000.0, zc - 60), (-588.0, 1170.0, 60.0)])
    SOCK["SOCKET_VFX_Bubbles_01"] = {"pos": (CYL_X, 980.0, zc + CYL_R + 8), "x": (0, 0, 1), "z": (-1, 0, 0)}

    # BOTTOM (z-300): RUPTURED barrel, blown hoses
    zc = -300.0
    ccyl(HYD, (CYL_X, 1260.0, zc), (CYL_X, 920.0, zc), CYL_R, sides=24)
    ccyl(HYD, (CYL_X, 935.0, zc), (CYL_X, 900.0, zc), 18.0, sides=16)                     # exposed piston
    for k in range(9):                                                                    # torn barrel petals (rear)
        a = k*40.0 + 10.0
        dy, dz = math.cos(math.radians(a)), math.sin(math.radians(a))
        b0 = (CYL_X + CYL_R*dy, 922.0, zc + CYL_R*dz)
        b1 = (CYL_X + (CYL_R + 6 + (k % 3)*4)*dy, 900.0 - (k % 4)*6, zc + (CYL_R + 6 + (k % 3)*4)*dz)
        obox(HYD, b0, b1, 4, 9 + (k % 2)*4, (dy, 0, dz), fil=0.8, seg=1)
    f0, f1 = (CYL_X - 15, 860.0, zc - 22), (CYL_X - 8, 700.0, zc - 12)                      # displaced front barrel
    ccyl(HYD, f0, f1, CYL_R, sides=24)
    ccyl(ARMOR, f1, vadd(f1, vmul(vnorm(vsub(f1, f0)), 30.0)), CYL_R + 5, sides=24, fil=2)
    for k in range(7):                                                                    # torn petals (front piece)
        a = k*51.0
        dy, dz = math.cos(math.radians(a)), math.sin(math.radians(a))
        b0 = (f0[0] + CYL_R*dy, f0[1] - 2, f0[2] + CYL_R*dz)
        b1 = (f0[0] + (CYL_R + 5)*dy, f0[1] + 14 + (k % 3)*5, f0[2] + (CYL_R + 5)*dz)
        obox(HYD, b0, b1, 4, 10, (dy, 0, dz), fil=0.8, seg=1)
    ccyl(HYD, (CYL_X, 915.0, zc), (CYL_X, LUG_Y, zc), ROD_R, sides=16)
    hose([(CYL_X, 1225.0, zc - 22), (CYL_X + 10, 1215.0, zc - 70), (-580.0, 1195.0, -150.0), (-585.0, 1200.0, -70.0)])
    # blown hose #1: ripped from the barrel port, dangling
    e1 = (-702.0, 868.0, -472.0)
    ccyl(HYD, (CYL_X, 950.0, zc - 20), (CYL_X, 950.0, zc - 34), 7.0, sides=12)            # torn port
    hose([(CYL_X - 4, 948.0, zc - 34), (-640.0, 930.0, -380.0), (-690.0, 900.0, -440.0), e1])
    ccyl(HYD, e1, vadd(e1, (-3.0, -8.0, -10.0)), 6.5, sides=10, fil=0.5, seg=1)            # frayed ferrule
    SOCK["SOCKET_VFX_Spark_00"] = {"pos": vadd(e1, (-4.0, -10.0, -13.0)), "x": vnorm((-3.0, -8.0, -10.0)), "z": (0, 0, 1)}
    # blown hose #2: severed near the manifold, whipping loose
    e2 = (-694.0, 1032.0, -222.0)
    hose([(-585.0, 1160.0, -60.0), (-625.0, 1120.0, -130.0), (-665.0, 1075.0, -205.0), e2])
    ccyl(HYD, e2, vadd(e2, (-4.0, -10.0, -3.0)), 6.5, sides=10, fil=0.5, seg=1)
    SOCK["SOCKET_VFX_Spark_01"] = {"pos": vadd(e2, (-5.0, -12.0, -4.0)), "x": vnorm((-4.0, -10.0, -3.0)), "z": (0, 0, 1)}
    SOCK["SOCKET_VFX_Bubbles_00"] = {"pos": (CYL_X, 890.0, zc), "x": (0, 0, 1), "z": (-1, 0, 0)}

    # ---- emergency status light bar (arc on entry frame face, 6 lamps)
    LB_R, A0, A1 = 545.0, 102.0, 168.0
    pts = [ring(LB_R, A0 + (A1 - A0)*i/6.0) for i in range(7)]
    for i in range(6):
        obox(ARMOR, X3(-432.5, pts[i]), X3(-432.5, pts[i+1]), 25, 50, (1, 0, 0), fil=3.0)
    for p in pts:
        ccyl(ARMOR, X3(X_IN, p), X3(-448.0, p), 27.0, sides=16, fil=2)
    for i in range(6):
        th = A0 + (A1 - A0)*(i + 0.5)/6.0
        p = ring(LB_R, th)
        ccyl(ARMOR, X3(-445.0, p), X3(-456.0, p), 20.0, sides=20, fil=1.5)
        ccyl(STATUS, X3(-456.0, p), X3(-466.0, p), 15.0, sides=20, fil=2.5)
        hv = ring(LB_R + 22, th)
        obox(ARMOR, X3(-445.0, hv), X3(-474.0, hv), 38, 4, (0.0, -math.sin(math.radians(th)), math.cos(math.radians(th))), fil=0.8, seg=1)   # lamp hood
        SOCK["SOCKET_Light_Status_%02d" % i] = {"pos": X3(-468.0, p), "x": (-1, 0, 0), "z": (0, 0, 1)}

    # ---- terminal mounting plate (lower-left of entry frame) + conduit
    cbox(ARMOR, -430.0, X_IN, -414.0, -314.0, -404.0, -324.0, fil=1.5)
    for yz in ((-404.0, -394.0), (-324.0, -394.0), (-404.0, -334.0), (-324.0, -334.0)):
        bolt(-430.0, yz, -1.0, r=5.0, h=4.0)
    cbox(ARMOR, -440.0, -430.0, -384.0, -344.0, -384.0, -344.0, fil=1.5)
    cbox(STATUS, -442.0, -440.0, -360.0, -348.0, -342.0, -338.0, fil=0.5, seg=1)          # port LED
    cbox(ARMOR, -450.0, X_IN, -300.0, -250.0, -540.0, -490.0, fil=2.0)                    # junction box
    ccyl(ARMOR, (-436.0, -340.0, -404.0), (-436.0, -285.0, -490.0), 6.0, sides=12)
    SOCK["SOCKET_Terminal_Mount"] = {"pos": (-441.0, -364.0, -364.0), "x": (-1, 0, 0), "z": (0, 0, 1)}

    # ---- navigation alignment (lens centre)
    SOCK["SOCKET_Nav_In"] = {"pos": (NAV_X_IN, LENS_Y, 0.0), "x": (1, 0, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_Nav_Out"] = {"pos": (NAV_X_OUT, LENS_Y, 0.0), "x": (1, 0, 0), "z": (0, 0, 1)}

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
    UCX.append((m, label, pts))
    return m

def ucx_prism_x(poly_yz, x0, x1, label):
    return ucx_rings([(x0, y, z) for (y, z) in poly_yz], [(x1, y, z) for (y, z) in poly_yz], label)

def ucx_box(x0, x1, y0, y1, z0, z1, label):
    return ucx_prism_x([(y0, z0), (y1, z0), (y1, z1), (y0, z1)], x0, x1, label)

def build_collision():
    c15 = math.cos(math.radians(15.0))
    ri, ro = R_BORE/c15, R_FRAME/c15            # inner chord tangent to the bore, outer encloses OD
    for k in range(12):                          # 12 tunnel staves, every 30 deg, length 840
        th = k*30.0
        ucx_prism_x([ring(ri, th - 15), ring(ro, th - 15), ring(ro, th + 15), ring(ri, th + 15)],
                    X_IN, X_OUT, "tunnel_stave_%02d" % k)
    c = math.cos(math.radians(11.25)); rv = R_LEAF/c   # 16-gon circumscribing the leaf; edge mid at 180 deg
    ucx_prism_x([ring(rv, 11.25 + 22.5*i, LEAF_C) for i in range(16)], X_LF0, X_LF1, "leaf_disc16")
    ucx_box(-570.0, PK_X1, 345.0, PK_Y1 + 25, -PK_Z - 25, PK_Z + 25, "door_pocket")
    ucx_box(-535.0, -420.0, -60.0, 405.0, 438.0, 470.0, "rail_top")
    ucx_box(-535.0, -420.0, -60.0, 405.0, -470.0, -438.0, "rail_bottom")
    ucx_box(-682.0, -568.0, 345.0, 1312.0, 262.0, 352.0, "actuator_top_bent")
    ucx_box(-648.0, -568.0, 345.0, 1312.0, -362.0, -262.0, "actuator_bottom_ruptured")

# ---------------------------------------------------------------- analytic lens check
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

# ---------------------------------------------------------------- MaxScript helpers
MXS = r'''
global soma_uv, soma_hose
fn soma_uv m = (
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
fn soma_hose pts r = (
    local s = SplineShape pos:pts[1]
    addNewSpline s
    for p in pts do addKnot s 1 #smooth #curve p
    updateShape s
    s.steps = 8
    s.render_renderable = true
    s.render_displayRenderMesh = true
    s.render_useViewportSettings = false
    s.render_thickness = r * 2.0
    s.render_sides = 10
    s.render_viewport_thickness = r * 2.0
    s.render_viewport_sides = 10
    convertToPoly s
    s
)
'''

# ---------------------------------------------------------------- build
def clean_scene():
    dead = [o for o in rt.objects if str(o.name).startswith("SOMA_") or str(o.name) == ASSET
            or str(o.name).startswith("UCX_" + ASSET) or str(o.name).startswith("SOMA_REF_")]
    for o in dead:
        try: rt.delete(o)
        except Exception: pass

def build():
    del PARTS[:]; del UCX[:]; SOCK.clear()
    clean_scene()
    rt.execute(MXS)
    out = {"max_units": str(rt.units.SystemType), "max_scale": float(rt.units.SystemScale)}
    MM = rt.execute('''(
        local mm = MultiMaterial numsubs:4 name:"MM_SomaLock"
        mm.materialList[1] = PhysicalMaterial name:"MS_Armor" base_color:(color 118 122 126) metalness:1.0 roughness:0.5
        mm.materialList[2] = PhysicalMaterial name:"MS_Hydraulic" base_color:(color 232 234 236) metalness:1.0 roughness:0.08
        mm.materialList[3] = PhysicalMaterial name:"MS_Seal" base_color:(color 22 22 24) metalness:0.0 roughness:0.85
        mm.materialList[4] = PhysicalMaterial name:"MS_Status" base_color:(color 0 0 0) emit_color:(color 255 30 20) emission:6.0
        mm.names = #("MS_Armor", "MS_Hydraulic", "MS_Seal", "MS_Status")
        mm )''')

    build_geometry()
    final = rt.Editable_Mesh(); final.name = ASSET
    rt.convertToPoly(final)
    for part in PARTS: rt.polyop.attach(final, part)
    final.material = MM
    rt.execute('(local m = getNodeByName "%s"; m.autoSmoothThreshold = 45.0; polyop.setFaceSelection m #all; m.EditablePoly.autosmooth(); polyop.setFaceSelection m #{})' % ASSET)
    out["uv_overlapping_faces"] = int(rt.soma_uv(final))

    build_collision()
    lay = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay.addnode(final)
    for (m, _, _) in UCX: lay.addnode(m)

    # ---- render-mesh lens check (all verts, any X)
    tm = rt.snapshotAsMesh(final)
    nv = int(tm.numverts); mind, minv = 1e18, None
    for i in range(1, nv + 1):
        v = rt.getVert(tm, i)
        d = math.hypot(float(v.y) - LENS_Y, float(v.z))
        if d < mind: mind, minv = d, (round(float(v.x), 1), round(float(v.y), 1), round(float(v.z), 1))
    mat_ids = sorted(set(int(rt.getFaceMatID(tm, i)) for i in range(1, int(tm.numfaces) + 1)))

    # ---- UCX checks: vert budget + YZ projection vs lens circle
    ucx_rep = []
    for (m, label, pts) in UCX:
        poly = hull2d([(round(p[1], 4), round(p[2], 4)) for p in pts])
        ucx_rep.append({"name": str(m.name), "part": label, "verts": int(rt.getNumVerts(m)),
                        "lens_clearance_cm": round(dist_pt_poly((LENS_Y, 0.0), poly) - LENS_R, 2)})

    # ---- socket reference helpers (NOT exported; UE step reads JSON)
    rl = rt.LayerManager.getLayerFromName("SOMA_Ref_Sockets") or rt.LayerManager.newLayerFromName("SOMA_Ref_Sockets")
    for k, sd in SOCK.items():
        x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
        pt = rt.Point(name="SOMA_REF_" + k, size=25, box=True, cross=True, axistripod=True)
        pt.transform = mtx(x, y, z, sd["pos"]); pt.wirecolor = rt.Color(255, 40, 160)
        rl.addnode(pt)

    out.update({
        "parts": len(PARTS), "verts": nv, "tris": int(tm.numfaces), "mat_ids": mat_ids,
        "bbox_min": [round(float(final.min.x), 1), round(float(final.min.y), 1), round(float(final.min.z), 1)],
        "bbox_max": [round(float(final.max.x), 1), round(float(final.max.y), 1), round(float(final.max.z), 1)],
        "lens": {"centre_yz": [LENS_Y, 0.0], "radius": LENS_R, "diameter": 2*LENS_R,
                 "render_min_dist": round(mind, 2), "render_min_vert": minv,
                 "render_clearance_cm": round(mind - LENS_R, 2)},
        "ucx": ucx_rep, "ucx_count": len(UCX), "ucx_max_verts": max(u["verts"] for u in ucx_rep),
        "ucx_min_lens_clearance": min(u["lens_clearance_cm"] for u in ucx_rep),
        "shell_section_half_diag": round(math.hypot(SHELL[1]/2, SHELL[2]/2), 1),
    })
    spec = {"asset": ASSET, "units": "cm",
            "space": "3ds Max RH Z-up, +X traversal; UE import maps (x, y, z) -> (x, -y, z)",
            "slots": SLOTS,
            "sockets": {k: {"pos": [round(c, 3) for c in v["pos"]], "x": list(v["x"]), "z": list(v["z"])} for k, v in SOCK.items()},
            "lens": out["lens"], "stats": {k: v for k, v in out.items() if k not in ("lens",)}}
    with open(JSON_PATH, "w") as f: json.dump(spec, f, indent=2)

    rt.select(final)
    for (m, _, _) in UCX: rt.selectMore(m)
    return out

SOMA_RESULT = build()
