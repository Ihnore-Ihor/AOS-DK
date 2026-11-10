# =============================================================================
# AOS-DK | Hero Asset #1 | SK_LARS_RoboticArm  (3ds Max 2027, pymxs)
# Procedural hard-surface build + bone chain + rigid skin + UV ch1 + 3 mat slots.
# Units: cm. Max space: +X forward (reach), +Z up, +Y = UE LEFT (UE flips Y).
# Bind pose: arm fully extended horizontally along +X, jaws CLOSED.
# Main joints are WORLD-ALIGNED (identity rotation) in bind pose:
#   Base_Yaw  -> rotate local Z      Shoulder/Elbow/Wrist_Pitch -> local Y
#   Wrist_Roll -> local X            Jaw_L / Jaw_R -> local Z (open: L +Z, R -Z)
# Piston bones: local +X points along the cylinder axis at the opposite anchor
#   (drive with Aim: Barrel aims at Rod, Rod aims at Barrel).
# Re-runnable: deletes previous LARS objects first.
# =============================================================================
from pymxs import runtime as rt
import math, json, os

ASSET = "SK_LARS_RoboticArm"
PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
STEEL, CHROME, HAZARD = 1, 2, 3

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
def ys(s, a, b): return (min(s*a, s*b), max(s*a, s*b))

def frame_z(zdir, yhint=(0.0, 1.0, 0.0)):
    z = vnorm(zdir)
    if abs(vdot(z, yhint)) > 0.99: yhint = (0.0, 0.0, 1.0)
    x = vnorm(vcross(yhint, z)); y = vcross(z, x)
    return x, y, z

def frame_x(xdir):          # X along xdir (XZ plane), Y = world Y, Z = X x Y
    x = vnorm(xdir); y = (0.0, 1.0, 0.0); z = vcross(x, y)
    return x, y, z

def mtx(x, y, z, p): return rt.Matrix3(P(x), P(y), P(z), P(p))

# ---------------------------------------------------------------- rig layout
J = {
    "Root_Bone":                (0, 0, 0),
    "Base_Yaw_Bone":            (0, 0, 60),
    "Shoulder_Pitch_Bone":      (50, 0, 250),
    "Elbow_Pitch_Bone":         (670, 0, 250),
    "Wrist_Pitch_Bone":         (1190, 0, 250),
    "Wrist_Roll_Bone":          (1250, 0, 250),
    "Jaw_L_Bone":               (1325, 132, 250),
    "Jaw_R_Bone":               (1325, -132, 250),
    "Shoulder_Cyl_Barrel_Bone": (120, 0, 110),
    "Shoulder_Cyl_Rod_Bone":    (360, 0, 175),
    "Elbow_Cyl_Barrel_Bone":    (390, 0, 324),
    "Elbow_Cyl_Rod_Bone":       (640, 0, 340),
}
PARENT = {
    "Root_Bone": None, "Base_Yaw_Bone": "Root_Bone",
    "Shoulder_Pitch_Bone": "Base_Yaw_Bone", "Elbow_Pitch_Bone": "Shoulder_Pitch_Bone",
    "Wrist_Pitch_Bone": "Elbow_Pitch_Bone", "Wrist_Roll_Bone": "Wrist_Pitch_Bone",
    "Jaw_L_Bone": "Wrist_Roll_Bone", "Jaw_R_Bone": "Wrist_Roll_Bone",
    "Shoulder_Cyl_Barrel_Bone": "Base_Yaw_Bone", "Shoulder_Cyl_Rod_Bone": "Shoulder_Pitch_Bone",
    "Elbow_Cyl_Barrel_Bone": "Shoulder_Pitch_Bone", "Elbow_Cyl_Rod_Bone": "Elbow_Pitch_Bone",
}
ORDER = list(J.keys())
DISP_LEN = {"Root_Bone": 40, "Base_Yaw_Bone": 50, "Shoulder_Pitch_Bone": 620,
            "Elbow_Pitch_Bone": 520, "Wrist_Pitch_Bone": 60, "Wrist_Roll_Bone": 75,
            "Jaw_L_Bone": 170, "Jaw_R_Bone": 170, "Shoulder_Cyl_Barrel_Bone": 120,
            "Shoulder_Cyl_Rod_Bone": 120, "Elbow_Cyl_Barrel_Bone": 120, "Elbow_Cyl_Rod_Bone": 120}
SC_DIR = vnorm(vsub(J["Shoulder_Cyl_Rod_Bone"], J["Shoulder_Cyl_Barrel_Bone"]))
EC_DIR = vnorm(vsub(J["Elbow_Cyl_Rod_Bone"], J["Elbow_Cyl_Barrel_Bone"]))
AXES = {n: frame_x((1, 0, 0)) for n in ORDER}
AXES["Shoulder_Cyl_Barrel_Bone"] = frame_x(SC_DIR)
AXES["Shoulder_Cyl_Rod_Bone"] = frame_x(vmul(SC_DIR, -1))
AXES["Elbow_Cyl_Barrel_Bone"] = frame_x(EC_DIR)
AXES["Elbow_Cyl_Rod_Bone"] = frame_x(vmul(EC_DIR, -1))

LEAK_POS = vadd(J["Elbow_Cyl_Barrel_Bone"], vmul(EC_DIR, 211.0))   # barrel gland face
SOCKETS = {
    # Shell-1 centre: pad face (X 1345) + 100 (Shell top -> centre). Between closed jaw pads.
    # Socket X = Shell forward (bind +Z), socket Z = Shell up (points back at the palm, -X).
    "SOCKET_Submarine_Mount": {"bone": "Wrist_Roll_Bone", "pos": (1445, 0, 250), "x": (0, 0, 1), "z": (-1, 0, 0)},
    # Umbilical gland on the turret deck behind the shoulder; X = cable exit (up).
    "SOCKET_Cable_Feed": {"bone": "Base_Yaw_Bone", "pos": (-55, 0, 232), "x": (0, 0, 1), "z": (-1, 0, 0)},
    # Elbow-cylinder rod-gland seal; X = spray direction along the rod.
    "SOCKET_Hydraulic_Leak": {"bone": "Elbow_Cyl_Barrel_Bone", "pos": LEAK_POS, "x": EC_DIR, "z": vcross(EC_DIR, (0, 1, 0))},
}

PARTS = {n: [] for n in ORDER}

# ---------------------------------------------------------------- primitives
def _finish(node, bone, mat):
    node.name = "LARS_%s_%03d" % (bone.replace("_Bone", ""), len(PARTS[bone]))
    rt.convertToPoly(node)
    rt.polyop.setFaceMatID(node, rt.Name("all"), mat)
    PARTS[bone].append(node)
    return node

def cbox(bone, mat, x0, x1, y0, y1, z0, z1, fil=3.0, seg=2):
    w, l, h = x1-x0, y1-y0, z1-z0
    f = min(fil, 0.4*min(w, l, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false pos:[%f,%f,%f]"
                   % (w, l, h, f, seg, (x0+x1)/2.0, (y0+y1)/2.0, z0))
    return _finish(n, bone, mat)

def ccyl(bone, mat, p0, p1, r, sides=24, fil=1.5, seg=2):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(r, h))
    n = rt.execute("ChamferCyl radius:%f height:%f fillet:%f Fillet_Segments:%d sides:%d Height_Segments:1 Cap_Segments:1 smoothOn:true mapcoords:false"
                   % (r, h, f, seg, sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, bone, mat)

def cbeam(bone, mat, p0, p1, wx, wy, fil=2.0, seg=2):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(wx, wy, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false"
                   % (wx, wy, h, f, seg))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, bone, mat)

def tube(bone, mat, r1, r2, z0, h, sides=48):
    n = rt.execute("Tube radius1:%f radius2:%f height:%f sides:%d height_segs:1 cap_segs:1 smooth:true mapcoords:false pos:[0,0,%f]" % (r1, r2, h, sides, z0))
    return _finish(n, bone, mat)

# ---------------------------------------------------------------- geometry
def build_geometry():
    R, B, S, E = "Root_Bone", "Base_Yaw_Bone", "Shoulder_Pitch_Bone", "Elbow_Pitch_Bone"
    WP, WR = "Wrist_Pitch_Bone", "Wrist_Roll_Bone"
    SB, SR = "Shoulder_Cyl_Barrel_Bone", "Shoulder_Cyl_Rod_Bone"
    EB, ER = "Elbow_Cyl_Barrel_Bone", "Elbow_Cyl_Rod_Bone"

    # ---- Root: heavy mounting collar, Ø250, bolted to the dock pedestal (static)
    ccyl(R, STEEL, (0, 0, 0), (0, 0, 20), 125, sides=48, fil=3)
    ccyl(R, STEEL, (0, 0, 20), (0, 0, 60), 108, sides=48, fil=2)
    for i in range(24):
        a = math.radians(i*15 + 7.5); cx, cy = 117*math.cos(a), 117*math.sin(a)
        ccyl(R, STEEL, (cx, cy, 20), (cx, cy, 28), 5, sides=6, fil=0.6, seg=1)
    tube(R, HAZARD, 110.5, 107, 34, 12)

    # ---- Base_Yaw: slew deck, turret, counterweight, shoulder clevis, cable gland
    ccyl(B, STEEL, (0, 0, 60), (0, 0, 90), 100, sides=48, fil=3)
    cbox(B, STEEL, -100, 70, -75, 75, 90, 190, fil=6, seg=3)
    cbox(B, STEEL, -95, 65, -70, 70, 190, 196, fil=2)
    cbox(B, STEEL, -175, -100, -80, 80, 95, 185, fil=5, seg=3)
    cbox(B, HAZARD, -178, -174, -70, 70, 110, 170, fil=0.8, seg=1)
    cbox(B, STEEL, -80, 20, 75, 97, 100, 170, fil=3)            # hydraulic power unit
    cbox(B, STEEL, -80, 0, -97, -75, 100, 175, fil=3)           # electrical cabinet
    cbox(B, HAZARD, -75, -5, -98.5, -96, 160, 170, fil=0.5, seg=1)
    for s in (1, -1):
        cbox(B, STEEL, -20, 120, *ys(s, 42, 60), 175, 250, fil=4)
        ccyl(B, STEEL, (50, s*42, 250), (50, s*60, 250), 70, sides=40, fil=3)
        ccyl(B, STEEL, (50, s*60, 250), (50, s*68, 250), 30, sides=24, fil=1.5)
        for k in range(6):
            a = math.radians(k*60 + 30)
            px, pz = 50 + 22*math.cos(a), 250 + 22*math.sin(a)
            ccyl(B, STEEL, (px, s*68, pz), (px, s*71, pz), 3, sides=6, fil=0.4, seg=1)
        cbox(B, STEEL, 60, 140, *ys(s, 16, 26), 88, 132, fil=2)  # shoulder-cyl clevis
        ccyl(B, STEEL, (120, s*16, 110), (120, s*26, 110), 22, sides=24)
    ccyl(B, CHROME, (50, -72, 250), (50, 72, 250), 20, sides=24, fil=1)
    ccyl(B, CHROME, (120, -30, 110), (120, 30, 110), 8, sides=16, fil=0.8)
    cbox(B, STEEL, -80, -30, -25, 25, 196, 200, fil=1)
    ccyl(B, STEEL, (-55, 0, 196), (-55, 0, 226), 14, sides=20)
    ccyl(B, STEEL, (-55, 0, 226), (-55, 0, 232), 18, sides=6, fil=0.8, seg=1)

    # ---- Shoulder hydraulic cylinder (barrel on turret, rod on boom)
    A, d = J[SB], SC_DIR
    ccyl(SB, STEEL, (A[0], -14, A[2]), (A[0], 14, A[2]), 15, sides=20)
    ccyl(SB, STEEL, vadd(A, vmul(d, 8)), vadd(A, vmul(d, 18)), 19.5)
    ccyl(SB, STEEL, vadd(A, vmul(d, 10)), vadd(A, vmul(d, 210)), 17)
    ccyl(SB, STEEL, vadd(A, vmul(d, 205)), vadd(A, vmul(d, 220)), 19.5)
    Bp, nd = J[SR], vmul(SC_DIR, -1)
    ccyl(SR, CHROME, vadd(Bp, vmul(nd, 10)), vadd(Bp, vmul(nd, 195)), 9, sides=20)
    ccyl(SR, STEEL, (Bp[0], -12, Bp[2]), (Bp[0], 12, Bp[2]), 13, sides=20)
    ccyl(SR, STEEL, vadd(Bp, vmul(nd, 8)), vadd(Bp, vmul(nd, 16)), 11)

    # ---- Shoulder_Pitch: main boom (box girder 620 pivot-to-pivot)
    ccyl(S, STEEL, (50, -40, 250), (50, 40, 250), 46, sides=32, fil=3)
    cbox(S, STEEL, 85, 640, -40, 40, 200, 300, fil=5, seg=3)
    cbox(S, STEEL, 95, 630, -44, 44, 296, 304, fil=1.5)
    cbox(S, STEEL, 95, 630, -44, 44, 196, 204, fil=1.5)
    for x in (150, 230, 310, 390, 470, 550):
        for s in (1, -1):
            cbox(S, STEEL, x, x+8, *ys(s, 40, 45), 205, 295, fil=1, seg=1)
    for s in (1, -1):
        cbox(S, STEEL, 620, 700, *ys(s, 30, 46), 205, 295, fil=3)
        ccyl(S, STEEL, (670, s*30, 250), (670, s*46, 250), 45, sides=32, fil=2)
        ccyl(S, STEEL, (670, s*46, 250), (670, s*53, 250), 26)
        cbox(S, STEEL, 338, 382, *ys(s, 14, 24), 158, 200, fil=1.5)
        ccyl(S, STEEL, (360, s*14, 175), (360, s*24, 175), 20, sides=20)
        cbox(S, STEEL, 368, 412, *ys(s, 14, 24), 300, 324, fil=1.5)
        ccyl(S, STEEL, (390, s*14, 324), (390, s*24, 324), 20, sides=20)
        for z in (288, 276):
            ccyl(S, STEEL, (95, s*49, z), (640, s*49, z), 3.5, sides=12, fil=0.5, seg=1)
        for x in (200, 400, 580):
            cbox(S, STEEL, x, x+6, *ys(s, 45, 54), 270, 294, fil=1, seg=1)
    ccyl(S, CHROME, (670, -56, 250), (670, 56, 250), 18, sides=24)
    ccyl(S, CHROME, (360, -28, 175), (360, 28, 175), 7, sides=16, fil=0.6)
    ccyl(S, CHROME, (390, -28, 324), (390, 28, 324), 7, sides=16, fil=0.6)
    cbox(S, HAZARD, 560, 615, -36, 36, 304, 306, fil=0.5, seg=1)

    # ---- Elbow hydraulic cylinder (barrel on boom top, rod on forearm tail lever)
    C, d = J[EB], EC_DIR
    ccyl(EB, STEEL, (C[0], -12, C[2]), (C[0], 12, C[2]), 13, sides=20)
    ccyl(EB, STEEL, vadd(C, vmul(d, 8)), vadd(C, vmul(d, 18)), 18.5)
    ccyl(EB, STEEL, vadd(C, vmul(d, 10)), vadd(C, vmul(d, 210)), 16)
    ccyl(EB, STEEL, vadd(C, vmul(d, 198)), vadd(C, vmul(d, 211)), 18.5)
    D, nd = J[ER], vmul(EC_DIR, -1)
    ccyl(ER, CHROME, vadd(D, vmul(nd, 10)), vadd(D, vmul(nd, 205)), 8.5, sides=20)
    ccyl(ER, STEEL, (D[0], -12, D[2]), (D[0], 12, D[2]), 12, sides=20)
    ccyl(ER, STEEL, vadd(D, vmul(nd, 8)), vadd(D, vmul(nd, 16)), 10.5)

    # ---- Elbow_Pitch: forearm (520 pivot-to-pivot) + tail lever + wrist rotary actuators
    ccyl(E, STEEL, (670, -29, 250), (670, 29, 250), 38, sides=32, fil=2)
    for s in (1, -1):
        cbeam(E, STEEL, (670, s*21, 250), (D[0], s*21, D[2]), 40, 14, fil=2)
        ccyl(E, STEEL, (D[0], s*14, D[2]), (D[0], s*28, D[2]), 20, sides=20)
    ccyl(E, CHROME, (D[0], -30, D[2]), (D[0], 30, D[2]), 7, sides=16, fil=0.6)
    cbox(E, STEEL, 690, 1150, -30, 30, 215, 285, fil=4, seg=3)
    cbox(E, STEEL, 700, 1140, -33, 33, 281, 287, fil=1.2)
    cbox(E, STEEL, 700, 1140, -33, 33, 213, 219, fil=1.2)
    for x in (770, 870, 970, 1070):
        for s in (1, -1):
            cbox(E, STEEL, x, x+7, *ys(s, 30, 34), 220, 280, fil=1, seg=1)
    for s in (1, -1):
        cbox(E, STEEL, 1130, 1205, *ys(s, 22, 36), 212, 288, fil=3)
        ccyl(E, STEEL, (1190, s*22, 250), (1190, s*36, 250), 38, sides=32)
        ccyl(E, CHROME, (1190, s*36, 250), (1190, s*56, 250), 32, sides=32, fil=2)
        ccyl(E, STEEL, (1190, s*56, 250), (1190, s*62, 250), 26)
        ccyl(E, STEEL, (700, s*37, 268), (1150, s*37, 268), 3, sides=12, fil=0.5, seg=1)
        for x in (800, 1000):
            cbox(E, STEEL, x, x+6, *ys(s, 33, 41), 260, 276, fil=1, seg=1)
    cbox(E, HAZARD, 1080, 1125, -26, 26, 287, 289, fil=0.5, seg=1)

    # ---- Wrist_Pitch: knuckle + roll bearing flange
    ccyl(WP, STEEL, (1190, -22, 250), (1190, 22, 250), 28, sides=32, fil=2)
    cbox(WP, STEEL, 1190, 1232, -22, 22, 224, 276, fil=3)
    ccyl(WP, CHROME, (1190, -66, 250), (1190, 66, 250), 12, sides=20, fil=1)
    ccyl(WP, STEEL, (1228, 0, 250), (1250, 0, 250), 36, sides=32, fil=1.5)

    # ---- Wrist_Roll: rotator disk + gripper palm + hinge ears
    ccyl(WR, STEEL, (1250, 0, 250), (1268, 0, 250), 42, sides=32, fil=2)
    for i in range(8):
        a = math.radians(i*45 + 22.5); py, pz = 39*math.cos(a), 250 + 39*math.sin(a)
        ccyl(WR, STEEL, (1250, py, pz), (1246, py, pz), 2.5, sides=6, fil=0.3, seg=1)
    cbox(WR, STEEL, 1268, 1335, -112, 112, 188, 312, fil=6, seg=3)
    cbox(WR, STEEL, 1335, 1345, -80, 80, 205, 295, fil=2)                # capture pad
    cbox(WR, HAZARD, 1275, 1328, -100, 100, 312, 314, fil=0.5, seg=1)
    cbox(WR, HAZARD, 1275, 1328, -100, 100, 186, 188, fil=0.5, seg=1)
    for s in (1, -1):
        for (z0, z1) in ((312, 324), (176, 188)):
            cbox(WR, STEEL, 1300, 1350, *ys(s, 100, 150), z0, z1, fil=2)
            ccyl(WR, STEEL, (1325, s*132, z0), (1325, s*132, z1), 20, sides=24)
        ccyl(WR, CHROME, (1325, s*132, 170), (1325, s*132, 330), 7, sides=16, fil=0.6)

    # ---- Jaws (closed in bind pose; inner pads at |Y| = 104 -> 208 clear for 200-wide hull)
    for s, Jb in ((1, "Jaw_L_Bone"), (-1, "Jaw_R_Bone")):
        ccyl(Jb, STEEL, (1325, s*132, 189), (1325, s*132, 311), 16, sides=24)
        cbox(Jb, STEEL, 1338, 1356, *ys(s, 112, 136), 190, 310, fil=3)
        cbox(Jb, STEEL, 1354, 1480, *ys(s, 112, 136), 180, 320, fil=4, seg=3)
        cbox(Jb, STEEL, 1360, 1470, *ys(s, 104, 112.5), 195, 305, fil=2)   # grip pad
        cbox(Jb, STEEL, 1470, 1505, *ys(s, 92, 136), 180, 320, fil=6, seg=3)  # claw lip
        for (z0, z1) in ((300, 318), (182, 200)):
            cbox(Jb, STEEL, 1356, 1490, *ys(s, 135, 146), z0, z1, fil=2)
        cbox(Jb, HAZARD, 1370, 1465, *ys(s, 135.5, 138), 202, 298, fil=0.6, seg=1)

# ---------------------------------------------------------------- MaxScript helpers
MXS = r'''
global lars_uv, lars_skin, lars_check
fn lars_uv m = (
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
fn lars_skin m bonesArr rangesArr = (
    max modify mode
    select m
    local sk = Skin()
    addModifier m sk
    modPanel.setCurrentObject sk
    sk.bone_Limit = 4
    for i = 1 to bonesArr.count do skinOps.addBone sk bonesArr[i] (if i == bonesArr.count then 1 else 0)
    local ids = #()
    for i = 1 to bonesArr.count do
        for j = 1 to (skinOps.GetNumberBones sk) do
            if (skinOps.GetBoneName sk j 1) == bonesArr[i].name do ids[i] = j
    for i = 1 to bonesArr.count do (
        local r = rangesArr[i]
        for v = r[1] to r[2] do skinOps.ReplaceVertexWeights sk v ids[i] 1.0
    )
    skinOps.RemoveZeroWeights sk   -- strip 0.0 envelope residue -> exactly 1 influence/vert
    ids
)
fn lars_check m bonesArr rangesArr = (
    local sk = m.modifiers[#Skin]
    local bad = 0
    for v = 1 to (skinOps.GetNumberVertices sk) do
        if (skinOps.GetVertexWeightCount sk v) != 1 do bad += 1
    local base = snapshotAsMesh m
    local res = #()
    for i = 1 to bonesArr.count do (
        local b = bonesArr[i]
        local r = rangesArr[i]
        local vi = (r[1] + r[2]) / 2
        local saved = b.transform
        in coordsys local rotate b (eulerangles 0 15 0)
        local sm = snapshotAsMesh m
        local own = distance (getVert sm vi) (getVert base vi)
        local col = distance (getVert sm 1) (getVert base 1)
        b.transform = saved
        append res ((b.name) + "|" + (own as string) + "|" + (col as string))
    )
    #(bad, res)
)
'''

# ---------------------------------------------------------------- build
def clean_scene():
    names = set(ORDER) | {ASSET} | set(SOCKETS.keys())
    dead = [o for o in rt.objects if (str(o.name).startswith("LARS_") or str(o.name) in names)]
    for o in dead:
        try: rt.delete(o)
        except Exception: pass

def build():
    clean_scene()
    rt.execute(MXS)
    out = {}

    MM = rt.execute('''(
        local mm = MultiMaterial numsubs:3 name:"MM_LARS_RoboticArm"
        mm.materialList[1] = PhysicalMaterial name:"M_LARS_SteelWorn" base_color:(color 96 100 102) metalness:1.0 roughness:0.55
        mm.materialList[2] = PhysicalMaterial name:"M_LARS_HydraulicChrome" base_color:(color 232 234 236) metalness:1.0 roughness:0.08
        mm.materialList[3] = PhysicalMaterial name:"M_LARS_HazardStripes" base_color:(color 230 170 20) metalness:0.0 roughness:0.6
        mm.names = #("SteelWorn", "HydraulicChrome", "HazardStripes")
        mm )''')

    # bones
    BONES = {}
    for n in ORDER:
        x, y, z = AXES[n]; p = J[n]
        b = rt.BoneSys.createBone(P(p), P(vadd(p, vmul(x, DISP_LEN[n]))), P(z))
        b.name = n
        b.transform = mtx(x, y, z, p)
        for prop, val in (("width", 8.0), ("height", 8.0), ("length", float(DISP_LEN[n]))):
            try: setattr(b, prop, val)
            except Exception: pass
        b.wirecolor = rt.Color(255, 140, 0) if "Cyl" in n else rt.Color(40, 200, 255)
        if PARENT[n]: b.parent = BONES[PARENT[n]]
        BONES[n] = b

    # geometry
    build_geometry()
    part_count = sum(len(v) for v in PARTS.values())

    # assemble one mesh, tracking vertex ranges per bone (attach appends verts)
    final = rt.Editable_Mesh()
    final.name = ASSET
    rt.convertToPoly(final)
    RANGES = {}
    for n in ORDER:
        s = rt.polyop.getNumVerts(final) + 1
        for part in PARTS[n]:
            rt.polyop.attach(final, part)
        RANGES[n] = (s, rt.polyop.getNumVerts(final))
    final.material = MM
    rt.execute('(local m = getNodeByName "%s"; m.autoSmoothThreshold = 50.0; polyop.setFaceSelection m #all; m.EditablePoly.autosmooth(); polyop.setFaceSelection m #{})' % ASSET)

    # UV channel 1: flatten (non-overlapping), then verify overlaps
    out["uv_overlapping_faces"] = int(rt.lars_uv(final))

    # skin (rigid: 1 bone / vertex)
    bones_arr = [BONES[n] for n in ORDER]
    ranges_arr = [[RANGES[n][0], RANGES[n][1]] for n in ORDER]
    rt.lars_skin(final, bones_arr, ranges_arr)
    chk = rt.lars_check(final, bones_arr, ranges_arr)
    out["verts_not_single_weight"] = int(chk[0])
    out["deform_test(bone|own_move|collar_move)"] = [str(s) for s in chk[1]]

    # socket reference helpers (NOT exported; consumed by the UE import step via JSON)
    lay = rt.LayerManager.getLayerFromName("SK_LARS_Ref_Sockets") or rt.LayerManager.newLayerFromName("SK_LARS_Ref_Sockets")
    for k, sd in SOCKETS.items():
        x = vnorm(sd["x"]); z = vnorm(sd["z"]); y = vcross(z, x)
        pt = rt.Point(name=k, size=25, box=True, cross=True, axistripod=True)
        pt.transform = mtx(x, y, z, sd["pos"])
        pt.parent = BONES[sd["bone"]]
        pt.wirecolor = rt.Color(255, 40, 160)
        lay.addnode(pt)
    lay_main = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay_main.addnode(final)
    for b in bones_arr: lay_main.addnode(b)

    # stats
    tm = rt.snapshotAsMesh(final)
    out.update({
        "parts": part_count,
        "verts": int(rt.polyop.getNumVerts(final)),
        "tris": int(tm.numfaces),
        "bbox_min": [round(float(final.min.x), 1), round(float(final.min.y), 1), round(float(final.min.z), 1)],
        "bbox_max": [round(float(final.max.x), 1), round(float(final.max.y), 1), round(float(final.max.z), 1)],
        "ranges": RANGES,
        "leak_pos": [round(c, 2) for c in LEAK_POS],
    })

    rig = {
        "asset": ASSET, "units": "cm",
        "space": "3ds Max RH Z-up; UE import maps (x, y, z) -> (x, -y, z)",
        "bind_pose": "arm extended along +X, jaws closed",
        "bones": [{"name": n, "parent": PARENT[n], "pos": list(J[n]),
                   "x": list(AXES[n][0]), "y": list(AXES[n][1]), "z": list(AXES[n][2])} for n in ORDER],
        "sockets": {k: {"bone": v["bone"], "pos": list(v["pos"]), "x": list(v["x"]), "z": list(v["z"])} for k, v in SOCKETS.items()},
        "stats": {k: v for k, v in out.items() if k != "ranges"},
    }
    with open(os.path.join(PROJ, "Tools", "SK_LARS_RoboticArm_rig.json"), "w") as f:
        json.dump(rig, f, indent=2)

    rt.select(final)
    for b in bones_arr: rt.selectMore(b)
    return out

LARS_RESULT = build()
