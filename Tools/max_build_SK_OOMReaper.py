# =============================================================================
# AOS-DK | Lab 5 | SK_OOMReaper  (3ds Max 2027, pymxs)  -- RPR-6 hexapod benthic walker
# Spec: Docs/AOS_Lab5_AI_Bots_Specification_EN.md  Section 2.1  (+ task-brief overrides, see DEVIATIONS)
# Units: cm. Max space: +X = forward (prow), +Z up, +Y = LEFT of the walker (UE import flips Y). Facing +X, scale 1.0.
# Overall (stance, bind pose):  L 420 (prow jaws X+210 .. tail drum X-210) | W 280 (outer pad edge to outer pad edge)
#                               H 180 (floor Z0 .. sensor-mast top)
# Skeleton (36 bones):  Root_Bone > Body_Bone > { Mast_Yaw > Mast_Pitch > Mast_Head,
#                                                 Arm_Yaw > Arm_Pitch1 > Arm_Pitch2 > Arm_Wrist,
#                                                 Jaw_L, Jaw_R, Tail_Drum,
#                                                 Leg_<L|R><1|2|3>_Coxa > _Femur > _Tibia > _Foot  (x6) }
#   Main bones (Root/Body/Mast/Arm/Jaw/Tail_Drum) are WORLD-ALIGNED (identity rotation) in the bind pose.
#   Leg bones: +X along the segment toward its child, Z = up in the leg's vertical plane (coxa yaw = local Z),
#   Y = horizontal leg-plane normal (femur/tibia pitch = local Y), as in the spec's axis convention.
# Rigid skinning: every vertex has exactly ONE bone influence (verified in-script).
# Sockets (helpers linked to bones, not exported; UE step authors them from Tools/SK_OOMReaper_rig.json):
#   SOCKET_Weapon_Dorsal, SOCKET_UI_Health, SOCKET_Decoy_Launcher, SOCKET_Foot_<L|R><1|2|3>
# DEVIATIONS from the spec text (task brief wins): name SK_OOMReaper, bone/socket names, 4.2 x 2.8 x 1.8 m envelope,
#   3 extra bones (Jaw_L, Jaw_R, Tail_Drum) to reach 36 with the brief's 33-bone chain, dorsal arm mounted on the LEFT
#   of the back (Y+42) so the stowed arm clears the centre mast. Leg proportions rescaled to the new envelope.
# Re-runnable: removes previous RPR_* / SK_OOMReaper / bones / SOCKET_* objects first.
# Run (build + save + FBX):  ns={}; exec(open(r"<proj>\Tools\max_build_SK_OOMReaper.py", encoding="utf-8").read(), ns); ns["RPR_RESULT"]
#   build only:  ns={"RPR_EXPORT": False}
# =============================================================================
from pymxs import runtime as rt
import math, json, os

ASSET = "SK_OOMReaper"
PFX = "RPR_"
PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
JSON_PATH = os.path.join(PROJ, "Tools", "SK_OOMReaper_rig.json")
MAX_PATH = os.path.join(PROJ, "SourceArt", "Enemies", ASSET + ".max")
FBX_PATH = os.path.join(PROJ, "Content", "AOS_DK_Game", "Enemies", "Reaper", ASSET + ".fbx")
METAL, RUBBER, HAZARD, EMIS = 1, 2, 3, 4
SLOTS = ["MS_CastMetal", "MS_RubberSeal", "MS_HazardPaint", "MS_StatusEmissive"]

# ---------------------------------------------------------------- layout (cm)
Z_BOT, Z_TOP = 55.0, 125.0                  # carapace underside / top
BODY_P = (0.0, 0.0, 85.0)
HIP_X = {1: 90.0, 2: 0.0, 3: -90.0}
HIP_Y = {1: 56.0, 2: 71.0, 3: 56.0}
FOOT_X = {1: 125.0, 2: 0.0, 3: -125.0}
FOOT_Y = 122.0                              # pad centre; pad r15 -> 137
KNEE_OUT = 4.0                              # knee lies this far beyond the foot (horizontally from the hip)
HIP_Z, COXA_L, KNEE_Z, ANKLE_Z = 85.0, 24.0, 150.0, 12.0
AY = 42.0                                   # dorsal arm lateral offset (left of the centre mast)
MAST_X, MAST_TOP = 100.0, 180.0

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

IDENT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

# ---------------------------------------------------------------- rig layout
J, PARENT, AXES, DISP = {}, {}, {}, {}
ORDER = []
LEG = {}                                    # per-leg geometry data

def add_bone(name, parent, pos, axes=IDENT, disp=30.0):
    ORDER.append(name); J[name] = tuple(pos); PARENT[name] = parent; AXES[name] = axes; DISP[name] = disp

def layout_rig():
    add_bone("Root_Bone", None, (0, 0, 0), disp=30)
    add_bone("Body_Bone", "Root_Bone", BODY_P, disp=60)
    add_bone("Mast_Yaw_Bone", "Body_Bone", (MAST_X, 0, Z_TOP), disp=40)
    add_bone("Mast_Pitch_Bone", "Mast_Yaw_Bone", (MAST_X, 0, 165.0), disp=14)
    add_bone("Mast_Head_Bone", "Mast_Pitch_Bone", (108.0, 0, 169.0), disp=24)
    add_bone("Arm_Yaw_Bone", "Body_Bone", (-40.0, AY, Z_TOP), disp=22)
    add_bone("Arm_Pitch1_Bone", "Arm_Yaw_Bone", (-40.0, AY, 148.0), disp=90)
    add_bone("Arm_Pitch2_Bone", "Arm_Pitch1_Bone", (50.0, AY, 148.0), disp=80)
    add_bone("Arm_Wrist_Bone", "Arm_Pitch2_Bone", (130.0, AY, 148.0), disp=30)
    add_bone("Jaw_L_Bone", "Body_Bone", (165.0, 32.0, 72.0), disp=45)
    add_bone("Jaw_R_Bone", "Body_Bone", (165.0, -32.0, 72.0), disp=45)
    add_bone("Tail_Drum_Bone", "Body_Bone", (-172.0, 0.0, 90.0), disp=38)
    for side, s in (("L", 1.0), ("R", -1.0)):
        for i in (1, 2, 3):
            hip = (HIP_X[i], s*HIP_Y[i], HIP_Z)
            G = (FOOT_X[i], s*FOOT_Y, 0.0)
            dh = vnorm((G[0]-hip[0], G[1]-hip[1], 0.0))
            hd = math.hypot(G[0]-hip[0], G[1]-hip[1])
            F = (hip[0]+dh[0]*COXA_L, hip[1]+dh[1]*COXA_L, HIP_Z)
            K = (hip[0]+dh[0]*(hd+KNEE_OUT), hip[1]+dh[1]*(hd+KNEE_OUT), KNEE_Z)
            A = (G[0], G[1], ANKLE_Z)
            zc = (0.0, 0.0, 1.0); yc = vcross(zc, dh)
            xc = dh; ax_c = (xc, yc, vcross(xc, yc))
            xf = vnorm(vsub(K, F)); ax_f = (xf, yc, vcross(xf, yc))
            xt = vnorm(vsub(A, K)); ax_t = (xt, yc, vcross(xt, yc))
            xo = (0.0, 0.0, -1.0); ax_o = (xo, yc, vcross(xo, yc))
            tag = "%s%d" % (side, i); pre = "Leg_%s_" % tag
            LEG[tag] = {"side": s, "hip": hip, "F": F, "K": K, "A": A, "G": G, "dh": dh, "yc": yc,
                        "bones": (pre+"Coxa", pre+"Femur", pre+"Tibia", pre+"Foot")}
            add_bone(pre+"Coxa", "Body_Bone", hip, ax_c, COXA_L)
            add_bone(pre+"Femur", pre+"Coxa", F, ax_f, vlen(vsub(K, F)))
            add_bone(pre+"Tibia", pre+"Femur", K, ax_t, vlen(vsub(A, K)))
            add_bone(pre+"Foot", pre+"Tibia", A, ax_o, ANKLE_Z)

SOCK = {}
def define_sockets():
    SOCK["SOCKET_Weapon_Dorsal"] = {"bone": "Arm_Wrist_Bone", "pos": (145.0, AY, 148.0), "x": (1, 0, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_UI_Health"] = {"bone": "Body_Bone", "pos": (40.0, 0.0, 250.0), "x": (1, 0, 0), "z": (0, 0, 1)}
    dd = vnorm((-math.cos(math.radians(35)), 0.0, math.sin(math.radians(35))))
    SOCK["SOCKET_Decoy_Launcher"] = {"bone": "Body_Bone", "pos": (-112.0, 0.0, 140.0), "x": dd, "z": (0.0, 1.0, 0.0)}
    for tag, L in LEG.items():
        SOCK["SOCKET_Foot_" + tag] = {"bone": L["bones"][3], "pos": (L["G"][0], L["G"][1], 0.0), "x": (0, 0, -1), "z": (1, 0, 0)}

PARTS = {}

# ---------------------------------------------------------------- primitives
def _finish(node, bone, mat):
    node.name = "%s%s_%03d" % (PFX, bone.replace("_Bone", ""), len(PARTS[bone]))
    rt.convertToPoly(node)
    rt.polyop.setFaceMatID(node, rt.Name("all"), mat)
    PARTS[bone].append(node)
    return node

def ccyl(bone, mat, p0, p1, r, sides=12, fil=0.8, seg=1):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(r, h))
    n = rt.execute("ChamferCyl radius:%f height:%f fillet:%f Fillet_Segments:%d sides:%d Height_Segments:1 Cap_Segments:1 smoothOn:true mapcoords:false"
                   % (r, h, f, seg, sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, bone, mat)

def cbox(bone, mat, x0, x1, y0, y1, z0, z1, fil=1.5, seg=1):
    w, l, h = x1-x0, y1-y0, z1-z0
    f = min(fil, 0.4*min(w, l, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false pos:[%f,%f,%f]"
                   % (w, l, h, f, seg, (x0+x1)/2.0, (y0+y1)/2.0, z0))
    return _finish(n, bone, mat)

def beam(bone, mat, p0, p1, xhint, wx, wy, fil=1.5, seg=1):
    """Box beam p0->p1; cross-section wx (along xhint, must be perpendicular to the beam) x wy."""
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(wx, wy, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false" % (wx, wy, h, f, seg))
    z = vnorm(d); x = vnorm(xhint); y = vcross(z, x); n.transform = mtx(x, y, z, p0)
    return _finish(n, bone, mat)

def cone(bone, mat, p0, p1, r0, r1, sides=12):
    d = vsub(p1, p0); h = vlen(d)
    n = rt.execute("Cone radius1:%f radius2:%f height:%f sides:%d heightsegments:1 capsegments:1 smooth:on mapcoords:false" % (r0, r1, h, sides))
    x, y, z = frame_z(d); n.transform = mtx(x, y, z, p0)
    return _finish(n, bone, mat)

def sph(bone, mat, c, r, segs=12):
    n = rt.execute("Sphere radius:%f segs:%d smooth:on mapcoords:false" % (r, segs))
    n.pos = P(c)
    return _finish(n, bone, mat)

def hexprism(bone, mat, z0, z1, R, ysc, fil=3.0, seg=2):
    n = rt.execute("ChamferCyl radius:%f height:%f fillet:%f Fillet_Segments:%d sides:6 Height_Segments:1 Cap_Segments:1 smoothOn:true mapcoords:false pos:[0,0,%f]"
                   % (R, z1-z0, fil, seg, z0))
    n.name = "%s_tmp_hex_%d" % (PFX, len(PARTS[bone]))
    n.scale = rt.Point3(1.0, ysc, 1.0)
    rt.execute('(local n = getNodeByName "%s"; resetXForm n; collapseStack n)' % str(n.name))
    return _finish(rt.getNodeByName(n.name), bone, mat)

def rbox(bone, mat, c, ang_deg, r_in, r_out, w, z0, h, fil=0.5):
    """Radial box on a vertical axis through c, at angle ang (XY plane): r_in..r_out along the radial, width w, height h from z0."""
    a = math.radians(ang_deg); ca, sa = math.cos(a), math.sin(a)
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:1 smooth:true mapcoords:false" % (r_out-r_in, w, h, min(fil, 0.4*min(r_out-r_in, w, h))))
    rm = 0.5*(r_in + r_out)
    n.transform = mtx((ca, sa, 0.0), (-sa, ca, 0.0), (0.0, 0.0, 1.0), (c[0]+rm*ca, c[1]+rm*sa, z0))
    return _finish(n, bone, mat)

def wbox(bone, mat, c, zdir, xdir, w, l, h, fil=0.5):
    """Box with base centre c, height along zdir, width along xdir."""
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:1 smooth:true mapcoords:false" % (w, l, h, min(fil, 0.4*min(w, l, h))))
    z = vnorm(zdir); x = vnorm(xdir); y = vcross(z, x)
    n.transform = mtx(x, y, z, c)
    return _finish(n, bone, mat)

# ---------------------------------------------------------------- geometry
def build_geometry():
    B = "Body_Bone"
    # ---- carapace: hexagonal chassis (plan vertices (+-150,0),(+-75,+-75)), dorsal plates, spine, belly
    hexprism(B, METAL, Z_BOT, 100.0, 150.0, 75.0/129.9, fil=3.0, seg=2)
    cbox(B, METAL, 22, 142, -52, 52, 98, 118, fil=3, seg=2)            # dorsal plate - front
    cbox(B, METAL, -62, 62, -70, 70, 100, 124, fil=3, seg=2)           # dorsal plate - mid
    cbox(B, METAL, -140, -58, -56, 56, 98, 118, fil=3, seg=2)          # dorsal plate - rear
    cbox(B, HAZARD, 24, 140, 51.5, 52.5, 100, 110, fil=0.3)            # plate edge paint
    cbox(B, HAZARD, 24, 140, -52.5, -51.5, 100, 110, fil=0.3)
    cbox(B, HAZARD, -60, 60, 69.5, 70.6, 104, 118, fil=0.3)
    cbox(B, HAZARD, -60, 60, -70.6, -69.5, 104, 118, fil=0.3)
    cbox(B, METAL, -130, 130, -4, 4, 123, 129, fil=1.2)                # spine ridge
    cbox(B, METAL, -120, 120, -65, 65, 47, 58, fil=2.0)                # belly pan
    for sy in (1, -1):
        cbox(B, METAL, -130, 130, *sorted((sy*40.0, sy*52.0)), 40, 49, fil=1.5)       # skid rails
        ccyl(B, METAL, (-80, sy*40.0, 46), (80, sy*40.0, 46), 18, sides=16, fil=2.0)  # ballast tank
        for xc in (-60.0, 0.0, 60.0):
            ccyl(B, RUBBER, (xc-3, sy*40.0, 46), (xc+3, sy*40.0, 46), 18.8, sides=16, fil=0.4)   # strap clamp
    # ---- prow intake + louvres
    cbox(B, METAL, 140, 178, -34, 34, 62, 106, fil=3, seg=2)
    for k in range(9):
        cbox(B, RUBBER, 178, 181, -30, 30, 66+4.0*k, 66+4.0*k+1.6, fil=0.3)
    # ---- tail: neck + decoy tubes (angled 35 up / 20 out) with emissive muzzle rings
    ccyl(B, METAL, (-150, 0, 90), (-172, 0, 90), 14, sides=16, fil=1.5)
    cbox(B, METAL, -135, -95, -34, 34, 123, 131, fil=1.5)                # decoy pad
    for sy in (1, -1):
        d = vnorm((-math.cos(math.radians(35))*math.cos(math.radians(20)), sy*math.cos(math.radians(35))*math.sin(math.radians(20)), math.sin(math.radians(35))))
        base = (-108.0, sy*26.0, 130.0)
        tip = vadd(base, vmul(d, 45.0))
        ccyl(B, METAL, base, tip, 6.0, sides=12, fil=0.6)
        ccyl(B, EMIS, vadd(base, vmul(d, 43.0)), vadd(base, vmul(d, 46.0)), 6.4, sides=12, fil=0.3)
        ccyl(B, METAL, vsub(base, vmul(d, 3.0)), vadd(base, vmul(d, 6.0)), 9.0, sides=12, fil=0.6)

    # ---- tail score drum (spins about X): shell, 10 emissive digit slots, hazard end cap
    D = "Tail_Drum_Bone"
    ccyl(D, METAL, (-172, 0, 90), (-207, 0, 90), 30, sides=24, fil=2.0, seg=1)
    ccyl(D, HAZARD, (-207, 0, 90), (-210, 0, 90), 26, sides=24, fil=0.4)
    for k in range(10):
        a = math.radians(k*36.0)
        c = (-188.0, 30.0*math.cos(a), 90.0 + 30.0*math.sin(a))
        wbox(D, EMIS, c, (0.0, math.cos(a), math.sin(a)), (1.0, 0.0, 0.0), 8.0, 7.0, 2.2, fil=0.3)

    # ---- mandibles
    for bone, sy in (("Jaw_L_Bone", 1), ("Jaw_R_Bone", -1)):
        cbox(bone, METAL, 168, 210, *sorted((sy*30.0, sy*34.0)), 66, 78, fil=1.0)
        cbox(bone, HAZARD, 190, 208, *sorted((sy*29.0, sy*30.0)), 68, 76, fil=0.3)
        ccyl(bone, METAL, (165, sy*30.0, 64), (165, sy*30.0, 80), 6, sides=12, fil=0.6)

    # ---- sensor mast
    M, MP, MH = "Mast_Yaw_Bone", "Mast_Pitch_Bone", "Mast_Head_Bone"
    ccyl(M, RUBBER, (MAST_X, 0, 125), (MAST_X, 0, 134), 13, sides=16, fil=1.0)
    ccyl(M, METAL, (MAST_X, 0, 128), (MAST_X, 0, 158), 8, sides=12, fil=0.8)
    for sy in (1, -1):
        ccyl(M, RUBBER, (MAST_X+7, sy*3, 132), (MAST_X+7, sy*3, 156), 1.5, sides=6, fil=0.2)
    ccyl(MP, METAL, (MAST_X, -8, 165), (MAST_X, 8, 165), 11, sides=16, fil=1.0)
    cbox(MH, METAL, 98, 130, -20, 20, 158, 180, fil=1.5, seg=2)                       # housing (top = mast top 180)
    ccyl(MH, EMIS, (130, 0, 169), (133, 0, 169), 6, sides=16, fil=0.3)                # central lens dia 12
    for sy in (1, -1):
        ccyl(MH, EMIS, (130, sy*12.0, 169), (132.5, sy*12.0, 169), 3.5, sides=12, fil=0.3)   # outboard lenses
        cbox(MH, METAL, 104, 126, *sorted((sy*20.0, sy*25.0)), 161, 176, fil=0.8)             # sonar fins

    # ---- dorsal weapon arm (left of the back, stowed forward; clamp grips the pike's 8 x 8 grip flats)
    Y, S, E, W = "Arm_Yaw_Bone", "Arm_Pitch1_Bone", "Arm_Pitch2_Bone", "Arm_Wrist_Bone"
    ccyl(Y, METAL, (-40, AY, 125), (-40, AY, 140), 26, sides=24, fil=1.5)
    for k in range(8):
        a = math.radians(k*45.0 + 22.5)
        ccyl(Y, METAL, (-40+21*math.cos(a), AY+21*math.sin(a), 140), (-40+21*math.cos(a), AY+21*math.sin(a), 143), 2.2, sides=6, fil=0.3)
    for sy in (1, -1):
        cbox(Y, METAL, -58, -22, *sorted((AY+sy*12.5, AY+sy*18.5)), 138, 162, fil=1.5)       # shoulder clevis
    ccyl(S, METAL, (-40, AY-11.5, 148), (-40, AY+11.5, 148), 14, sides=20, fil=1.0)          # shoulder pivot
    cbox(S, METAL, -34, 54, AY-11, AY+11, 135, 161, fil=2.5, seg=2)                            # upper boom
    for sy in (1, -1):
        cbox(S, HAZARD, 4, 44, *sorted((AY+sy*11.0, AY+sy*11.7)), 141, 155, fil=0.3)         # side bands
    ccyl(S, METAL, (-14, AY, 166), (44, AY, 166), 4.5, sides=12, fil=0.5)                    # top hydraulic cylinder
    cbox(S, METAL, -16, -10, AY-6, AY+6, 160, 168, fil=0.5)
    ccyl(S, METAL, (-25, AY+17, 150), (45, AY+17, 150), 4.5, sides=12, fil=0.5)               # actuator barrel (70)
    ccyl(E, METAL, (45, AY+17, 150), (105, AY+17, 150), 2.5, sides=10, fil=0.3)               # actuator rod (60)
    ccyl(E, METAL, (50, AY-11, 148), (50, AY+11, 148), 12, sides=20, fil=1.0)                  # elbow pivot
    cbox(E, METAL, 52, 127, AY-8, AY+8, 139, 157, fil=2.0, seg=2)                              # forearm
    ccyl(W, METAL, (130, AY-10, 148), (130, AY+10, 148), 10, sides=16, fil=0.8)                # wrist knuckle
    cbox(W, METAL, 133, 157, AY-11, AY+11, 156, 163, fil=1.0)                                   # clamp upper jaw
    cbox(W, METAL, 133, 157, AY-11, AY+11, 133, 140, fil=1.0)                                   # clamp lower jaw
    cbox(W, RUBBER, 134, 156, AY-9, AY+9, 152, 156, fil=0.3)                                    # jaw pads (inner face z 148+4)
    cbox(W, RUBBER, 134, 156, AY-9, AY+9, 140, 144, fil=0.3)
    for sy in (1, -1):
        cbox(W, METAL, 133, 157, *sorted((AY+sy*4.5, AY+sy*11.0)), 140, 156, fil=0.8)           # side plates (8 wide opening)
    # arm conduits (rigid: one bone each)
    for bone, p0, p1 in ((S, (-30, AY-9, 163), (50, AY-9, 163)), (E, (50, AY-9, 160), (126, AY-9, 160)), (Y, (-40, AY-24, 128), (-40, AY-24, 156))):
        ccyl(bone, RUBBER, p0, p1, 2.0, sides=8, fil=0.2)

    # ---- six legs
    for tag, L in LEG.items():
        c_b, f_b, t_b, o_b = L["bones"]; yc = L["yc"]; dh = L["dh"]; s = L["side"]
        hip, F, K, A, G = L["hip"], L["F"], L["K"], L["A"], L["G"]
        # coxa: hip servo drum + yoke
        ccyl(c_b, METAL, (hip[0], hip[1], hip[2]-10), (hip[0], hip[1], hip[2]+10), 13, sides=16, fil=1.0)
        beam(c_b, METAL, hip, F, yc, 14, 16, fil=1.5)
        # femur: strut, top hydraulic, knee servo, seal ring, hazard knee cap
        beam(f_b, METAL, F, K, yc, 14, 18, fil=1.5)
        xf = vnorm(vsub(K, F)); up = vcross(xf, yc)
        if up[2] < 0: up = vmul(up, -1.0)
        Lf = vlen(vsub(K, F))
        ccyl(f_b, METAL, vadd(vadd(F, vmul(xf, 0.18*Lf)), vmul(up, 12.0)), vadd(vadd(F, vmul(xf, 0.86*Lf)), vmul(up, 12.0)), 3.5, sides=10, fil=0.4)
        ccyl(f_b, METAL, vsub(K, vmul(yc, 8.0)), vadd(K, vmul(yc, 8.0)), 8.5, sides=16, fil=0.8)
        ccyl(f_b, RUBBER, vadd(K, vmul(yc, 7.0)), vadd(K, vmul(yc, 10.0)), 9.0, sides=16, fil=0.3)
        ccyl(f_b, HAZARD, vadd(K, vmul(yc, 10.0)), vadd(K, vmul(yc, 12.5)), 9.6, sides=16, fil=0.3)
        ccyl(f_b, HAZARD, vsub(K, vmul(yc, 12.5)), vsub(K, vmul(yc, 10.0)), 9.6, sides=16, fil=0.3)
        # tibia: tapered tube, 3 armour rings, 2 barnacle clusters
        cone(t_b, METAL, K, A, 7.0, 4.0, sides=12)
        xt = vnorm(vsub(A, K)); Lt = vlen(vsub(A, K))
        for fr, rr in ((0.22, 8.6), (0.50, 7.6), (0.78, 6.6)):
            p = vadd(K, vmul(xt, fr*Lt)); ccyl(t_b, METAL, vsub(p, vmul(xt, 2.0)), vadd(p, vmul(xt, 2.0)), rr, sides=12, fil=0.4)
        for fr, off in ((0.36, 1.0), (0.66, -1.0)):
            p = vadd(K, vmul(xt, fr*Lt)); q = vadd(p, vmul(dh, off*5.5))
            cone(t_b, METAL, q, vadd(q, vmul(dh, off*3.5)), 2.4, 0.6, sides=6)
        # foot: ballast spud (rubber tread, pad, 6 cleats, magnetic ballast weight + hazard band, ball joint)
        sph(o_b, METAL, A, 7.0, segs=12)
        ccyl(o_b, RUBBER, (G[0], G[1], 0.0), (G[0], G[1], 3.0), 15.2, sides=18, fil=0.6)
        ccyl(o_b, METAL, (G[0], G[1], 3.0), (G[0], G[1], 9.0), 15.0, sides=18, fil=0.8)
        for k in range(6):
            rbox(o_b, METAL, (G[0], G[1]), k*60.0, 10.0, 14.5, 3.0, 9.0, 2.2)
        ccyl(o_b, METAL, (G[0], G[1], 9.0), (G[0], G[1], 19.0), 9.5, sides=16, fil=0.8)
        ccyl(o_b, HAZARD, (G[0], G[1], 12.0), (G[0], G[1], 16.0), 9.9, sides=16, fil=0.3)

# ---------------------------------------------------------------- MaxScript helpers
MXS = r'''
global rpr_uv, rpr_skin, rpr_check
fn rpr_uv m = (
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
    channelInfo.CopyChannel m 3 1
    channelInfo.PasteChannel m 3 2          -- UV1 (bake / fouling mask) = same non-overlapping layout
    ov
)
fn rpr_skin m bonesArr rangesArr = (
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
    skinOps.RemoveZeroWeights sk
    ids
)
fn rpr_check m bonesArr rangesArr = (
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
        b.transform = saved
        append res ((b.name) + "|" + (own as string))
    )
    #(bad, res)
)
'''

def settle_ui():
    rt.execute("max create mode")
    rt.windows.processPostedMessages()
    rt.completeRedraw()
    rt.windows.processPostedMessages()

def own(o):
    nm = str(o.name)
    return nm.startswith(PFX) or nm == ASSET or nm.startswith("SOCKET_") or nm in J or nm.startswith("Leg_")

def prepare_scene():
    if str(rt.units.SystemType) != "centimeters" or abs(float(rt.units.SystemScale) - 1.0) > 1e-6:
        rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    cur = os.path.join(str(rt.maxFilePath), str(rt.maxFileName))
    foreign = [o for o in rt.objects if not own(o)]
    if foreign and os.path.normcase(cur) != os.path.normcase(MAX_PATH):
        if rt.getSaveRequired():
            raise RuntimeError("Scene has unsaved foreign content (%s) - save it first; build aborted." % cur)
        rt.resetMaxFile(rt.Name("noPrompt"))
        if str(rt.units.SystemType) != "centimeters":
            rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    for o in [o for o in rt.objects if own(o)]:
        try: rt.delete(o)
        except Exception: pass

# ---------------------------------------------------------------- build
def build():
    del ORDER[:]; J.clear(); PARENT.clear(); AXES.clear(); DISP.clear(); LEG.clear(); SOCK.clear()
    layout_rig(); define_sockets()
    PARTS.clear()
    for n in ORDER: PARTS[n] = []
    prepare_scene()
    rt.execute(MXS)
    out = {"max_units": str(rt.units.SystemType), "bone_count": len(ORDER)}
    MM = rt.execute('''(
        local mm = MultiMaterial numsubs:4 name:"MM_OOMReaper"
        mm.materialList[1] = PhysicalMaterial name:"MS_CastMetal" base_color:(color 58 61 70) metalness:1.0 roughness:0.6
        mm.materialList[2] = PhysicalMaterial name:"MS_RubberSeal" base_color:(color 28 28 32) metalness:0.0 roughness:0.85
        mm.materialList[3] = PhysicalMaterial name:"MS_HazardPaint" base_color:(color 241 250 140) metalness:0.0 roughness:0.6
        mm.materialList[4] = PhysicalMaterial name:"MS_StatusEmissive" base_color:(color 0 0 0) emit_color:(color 139 233 253) emission:4.0
        mm.names = #("MS_CastMetal", "MS_RubberSeal", "MS_HazardPaint", "MS_StatusEmissive")
        mm )''')

    # ---- bones
    BONES = {}
    for n in ORDER:
        x, y, z = AXES[n]; p = J[n]
        b = rt.BoneSys.createBone(P(p), P(vadd(p, vmul(x, DISP[n]))), P(z))
        b.name = n
        b.transform = mtx(x, y, z, p)
        for prop, val in (("width", 6.0), ("height", 6.0), ("length", float(DISP[n]))):
            try: setattr(b, prop, val)
            except Exception: pass
        b.wirecolor = rt.Color(255, 140, 0) if n.startswith("Leg_") else rt.Color(40, 200, 255)
        if PARENT[n]: b.parent = BONES[PARENT[n]]
        BONES[n] = b

    build_geometry()
    part_count = sum(len(v) for v in PARTS.values())

    final = rt.Editable_Mesh(); final.name = ASSET
    rt.convertToPoly(final)
    RANGES = {}
    for n in ORDER:
        s = rt.polyop.getNumVerts(final) + 1
        for part in PARTS[n]: rt.polyop.attach(final, part)
        RANGES[n] = (int(s), int(rt.polyop.getNumVerts(final)))
    final.material = MM
    rt.execute('(local m = getNodeByName "%s"; m.autoSmoothThreshold = 35.0; polyop.setFaceSelection m #all; m.EditablePoly.autosmooth(); polyop.setFaceSelection m #{})' % ASSET)
    out["uv_overlapping_faces"] = int(rt.rpr_uv(final))

    bones_arr = [BONES[n] for n in ORDER]
    ranges_arr = [[RANGES[n][0], RANGES[n][1]] for n in ORDER]
    rt.rpr_skin(final, bones_arr, ranges_arr)
    ne = [i for i, n in enumerate(ORDER) if RANGES[n][1] >= RANGES[n][0]]
    chk = rt.rpr_check(final, [bones_arr[i] for i in ne], [ranges_arr[i] for i in ne])
    out["verts_not_single_weight"] = int(chk[0])
    out["bones_without_geometry"] = [n for n in ORDER if RANGES[n][1] < RANGES[n][0]]
    out["deform_test_min_move_cm"] = round(min(float(str(s).split("|")[1]) for s in chk[1]), 2)

    # ---- socket helpers (linked to bones, NOT exported)
    rl = rt.LayerManager.getLayerFromName("RPR_Ref_Sockets") or rt.LayerManager.newLayerFromName("RPR_Ref_Sockets")
    for k, sd in SOCK.items():
        x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
        pt = rt.Point(name=k, size=10, box=True, cross=True, axistripod=True)
        pt.transform = mtx(x, y, z, sd["pos"]); pt.parent = BONES[sd["bone"]]; pt.wirecolor = rt.Color(255, 40, 160)
        rl.addnode(pt)
    lay = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay.addnode(final)
    for b in bones_arr: lay.addnode(b)

    # ---- stats
    tm = rt.snapshotAsMesh(final)
    bb_min = [round(float(final.min.x), 1), round(float(final.min.y), 1), round(float(final.min.z), 1)]
    bb_max = [round(float(final.max.x), 1), round(float(final.max.y), 1), round(float(final.max.z), 1)]
    mat_ids = sorted(set(int(rt.getFaceMatID(tm, i)) for i in range(1, int(tm.numfaces) + 1)))
    out.update({"parts": part_count, "verts": int(tm.numverts), "tris": int(tm.numfaces), "mat_ids": mat_ids,
                "bbox_min": bb_min, "bbox_max": bb_max,
                "length_cm": round(bb_max[0]-bb_min[0], 1), "width_cm": round(bb_max[1]-bb_min[1], 1), "height_cm": round(bb_max[2]-bb_min[2], 1),
                "sockets": sorted(SOCK.keys()), "ranges": RANGES})
    rig = {"asset": ASSET, "units": "cm",
           "space": "3ds Max RH Z-up, +X = forward, +Y = left; UE import maps (x, y, z) -> (x, -y, z)",
           "bind_pose": "stance: legs planted, mast vertical, arm stowed forward along the back, jaws closed",
           "slots": SLOTS,
           "bones": [{"name": n, "parent": PARENT[n], "pos": [round(c, 3) for c in J[n]],
                      "x": [round(c, 6) for c in AXES[n][0]], "y": [round(c, 6) for c in AXES[n][1]], "z": [round(c, 6) for c in AXES[n][2]]} for n in ORDER],
           "sockets": {k: {"bone": v["bone"], "pos": [round(c, 3) for c in v["pos"]], "x": [round(c, 6) for c in v["x"]], "z": [round(c, 6) for c in v["z"]]} for k, v in SOCK.items()},
           "stats": {k: v for k, v in out.items() if k != "ranges"}}
    with open(JSON_PATH, "w") as f: json.dump(rig, f, indent=2)

    rt.select(final)
    for b in bones_arr: rt.selectMore(b)
    settle_ui()
    os.makedirs(os.path.dirname(MAX_PATH), exist_ok=True)
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)
    out["max_saved"] = MAX_PATH if os.path.exists(MAX_PATH) else None
    return out

def export_and_resave():
    rt.select(rt.getNodeByName(ASSET))
    for n in ORDER: rt.selectMore(rt.getNodeByName(n))
    rt.execute('''(
        FBXExporterSetParam "ResetExport"
        FBXExporterSetParam "Skin" true
        FBXExporterSetParam "Shape" false
        FBXExporterSetParam "SmoothingGroups" true
        FBXExporterSetParam "TangentSpaceExport" true
        FBXExporterSetParam "Triangulate" false
        FBXExporterSetParam "Animation" false
        FBXExporterSetParam "Cameras" false
        FBXExporterSetParam "Lights" false
        FBXExporterSetParam "EmbedTextures" false
        FBXExporterSetParam "ConvertUnit" "cm"
        FBXExporterSetParam "UpAxis" "Z"
        FBXExporterSetParam "ASCII" false
    )''')
    os.makedirs(os.path.dirname(FBX_PATH), exist_ok=True)
    ok = rt.exportFile(FBX_PATH, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
    settle_ui()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)
    return {"fbx": FBX_PATH if ok and os.path.exists(FBX_PATH) else None,
            "fbx_bytes": os.path.getsize(FBX_PATH) if os.path.exists(FBX_PATH) else 0}

GUARD_MXS = r'''
global rpr_guard_timer
fn rpr_guard_tick s e = (
    s.Stop()
    if (maxFilePath + maxFileName) == @"%s" and getSaveRequired() do
        saveMaxFile (maxFilePath + maxFileName) clearNeedSaveFlag:true useNewFile:true quiet:true
    setSaveRequired false
    dotNet.removeAllEventHandlers s
)
rpr_guard_timer = dotNetObject "System.Windows.Forms.Timer"
rpr_guard_timer.Interval = 1500
dotNet.addEventHandler rpr_guard_timer "Tick" rpr_guard_tick
rpr_guard_timer.Start()
''' % MAX_PATH

RPR_RESULT = build()
if globals().get("RPR_EXPORT", True):
    RPR_RESULT["export"] = export_and_resave()
rt.execute(GUARD_MXS)
