# =============================================================================
# AOS-DK | Lab 6 / Chat D | SK_Agro_WindGen  (3ds Max 2027, pymxs) -> FBX -> UE 5.7.4
# Spec: Docs/AOS_Lab6_Animations_Specification_EN.md  §4.1 (T3-DCC).
# Geometry: same primitives / proportions / material slots as b_wind_gen() in Tools/max_build_Atoll_Kit.py (M-15), split
# into rigid elements and skinned 1 bone / vertex to 9 bones:
#   WG_Root -> WG_Tower -> WG_Nacelle_Yaw (Z) -> { WG_TailVane (Z), WG_Light_Obstr, WG_Rotor_Hub (X) -> WG_Blade_0/1/2 (radial pitch) }
# Takes (30 fps, authored on the Max timeline, baked per FBX):
#   A_WindGen_Spin  0-90   linear 360 deg roll of the hub (keys every 30 f, linear tangents, blades at the 8 deg bind pitch)
#   A_WindGen_Hunt  0-240  +-10 deg nacelle yaw sine, tail vane +-15 deg lagging 20 f
#   A_WindGen_Furl  0-60   blades 8 -> 88 deg, nacelle +55 deg yaw, tail vane -35 deg, ease in/out
# Meshes are authored in UE-local space and mirrored (y -> -y, winding reversed) into Max, like the Atoll kit, so the Max RH ->
# UE LH import (x, -y, z) lands them un-mirrored.  All animation angles below are the DESIRED UE-space angles; UE_SIGN converts
# them to Max-space key values (a mirror reverses every rotation sense).
# Run in Max:  ns = {}; exec(open(r"<proj>\Tools\max_build_SK_WindGen.py", encoding="utf-8").read(), ns)
#              ns["build"]()  ->  geometry + bones + skin + 3 takes on the timeline, saves SourceArt/Atoll/SK_Agro_WindGen.max
#              ns["export"]() ->  SK_Agro_WindGen.fbx + A_WindGen_{Spin,Hunt,Furl}.fbx in Content/.../Environment/Atoll/WindGen
# =============================================================================
import math, json, os
from pymxs import runtime as rt

PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
KIT_PY = os.path.join(PROJ, "Tools", "max_build_Atoll_Kit.py")
MAX_PATH = os.path.join(PROJ, "SourceArt", "Atoll", "SK_Agro_WindGen.max")
FBX_DIR = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "Atoll", "WindGen")
RIG_JSON = os.path.join(PROJ, "Tools", "SK_Agro_WindGen_rig.json")
BACKUP_DIR = os.path.join(PROJ, "Saved", "ClaudeBackup_Lab6_D")
ASSET = "SK_Agro_WindGen"
FPS = 30
UE_SIGN = -1.0          # Max key angle = UE_SIGN * desired UE angle (mirror y -> -y reverses rotation sense)

# ---- reuse the Atoll kit primitives (closed chamfered solids, hull3d/chull, lathe, material slot catalogue, phys_mat, Max helpers)
K = {"__name__": "atoll_kit_ref"}
exec(compile(open(KIT_PY, encoding="utf-8").read(), KIT_PY, "exec"), K)
Kit, cbox, bar, cyl, lathe, chull, axis_fr, I = K["Kit"], K["cbox"], K["bar"], K["cyl"], K["lathe"], K["chull"], K["axis_fr"], K["I"]
SLOT_CAT, phys_mat, rad = K["SLOT_CAT"], K["phys_mat"], K["rad"]
def P3(p): return rt.Point3(float(p[0]), float(p[1]), float(p[2]))

# ---------------------------------------------------------------- rig layout (UE-local; y = 0 for every pivot except the blades)
HUB = (50.0, 0.0, 905.0)
BLADE_X = 51.0                                    # axial centre line of the blade sections
BLADE_A = [90.0, 210.0, 330.0]                    # blade azimuth about +X (UE-local), as b_wind_gen()
R_ROOT, R_TIP = 12.0, 90.0                        # blade root / tip radius (spec: root 12, length 78 -> D180)
CHORD = (14.0, 6.0); THICK = (3.2, 1.6)
PITCH_BIND, TWIST = 8.0, (12.0, 2.0)              # bind pitch 8 deg; aerodynamic twist 12 -> 2 deg along the span (mean 7)
BLADE_ST = [R_ROOT + (R_TIP - R_ROOT) * i / 4.0 for i in range(5)]
def blade_dir(i):
    a = rad(BLADE_A[i]); return (0.0, math.cos(a), math.sin(a))      # UE-local radial
BONES = [  # name, parent, pivot (UE-local), display length
    ("WG_Root", None, (0.0, 0.0, 0.0), 30.0), ("WG_Tower", "WG_Root", (0.0, 0.0, 0.0), 40.0),
    ("WG_Nacelle_Yaw", "WG_Tower", (0.0, 0.0, 880.0), 40.0), ("WG_TailVane", "WG_Nacelle_Yaw", (-95.0, 0.0, 895.0), 30.0),
    ("WG_Light_Obstr", "WG_Nacelle_Yaw", (0.0, 0.0, 932.0), 12.0), ("WG_Rotor_Hub", "WG_Nacelle_Yaw", HUB, 20.0)]
for _i in range(3):
    _u = blade_dir(_i)
    BONES.append(("WG_Blade_%d" % _i, "WG_Rotor_Hub", (BLADE_X, R_ROOT * _u[1], HUB[2] + R_ROOT * _u[2]), 78.0))
BONE_ORDER = [b[0] for b in BONES]
SOCKETS = {"SOCKET_Mount_C": {"bone": "WG_Root", "pos": (0.0, 0.0, 0.0)},
           "SOCKET_Light_Obstr": {"bone": "WG_Light_Obstr", "pos": (0.0, 0.0, 932.0)},
           "SOCKET_Rotor": {"bone": "WG_Rotor_Hub", "pos": HUB}}

# ---------------------------------------------------------------- geometry (UE-local)
def blade_hulls(mb, i):
    u = blade_dir(i); w = (0.0, -u[2], u[1]); xh = (1.0, 0.0, 0.0)
    secs = []
    for r in BLADE_ST:
        s = (r - R_ROOT) / (R_TIP - R_ROOT)
        c = CHORD[0] + (CHORD[1] - CHORD[0]) * s; th = THICK[0] + (THICK[1] - THICK[0]) * s
        tw = TWIST[0] + (TWIST[1] - TWIST[0]) * s
        phi = rad(PITCH_BIND + (tw - 0.5 * (TWIST[0] + TWIST[1])))       # section angle in the bind pose (mean = 8 deg)
        ch = tuple(math.cos(phi) * w[k] + math.sin(phi) * xh[k] for k in range(3))        # chord direction
        nm = tuple(-math.sin(phi) * w[k] + math.cos(phi) * xh[k] for k in range(3))       # thickness direction
        cen = (BLADE_X, r * u[1], HUB[2] + r * u[2])
        secs.append([tuple(cen[k] + a * 0.5 * c * ch[k] + b * 0.5 * th * nm[k] for k in range(3)) for a in (-1, 1) for b in (-1, 1)])
    for k in range(len(secs) - 1):
        chull(mb, "MS_Rotor", secs[k] + secs[k + 1])

def build_geometry():
    k = Kit("SK_Agro_WindGen: M-15 split into 9 rigid bones (tower, yawing nacelle, tail vane, obstruction light, hub, 3 pitching blades)", nanite=False)
    mb = k.mb; rng = {}
    zt = 860.0; b0, b1 = 82.0, 20.0
    C4 = ((1, 1), (-1, 1), (-1, -1), (1, -1))
    leg = lambda sx, sy, z: (sx * (b0 + (b1 - b0) * (z - 8.0) / (zt - 8.0)), sy * (b0 + (b1 - b0) * (z - 8.0) / (zt - 8.0)), z)
    def part(bone, fn):
        v0 = len(mb.v); fn(); rng[bone] = (v0 + 1, len(mb.v))
    def root():
        cbox(mb, "MS_Corten", I, -100.0, 100.0, -100.0, 100.0, 0.0, 8.0, 1.5)
    def tower():
        for (sx, sy) in C4: bar(mb, "MS_Corten", leg(sx, sy, 8.0), leg(sx, sy, zt), 8.0, 8.0, up=(1, 0, 0), c=0.8)
        lv = [8.0, 190.0, 360.0, 520.0, 660.0, 780.0, zt]
        for i, z in enumerate(lv[1:]):
            for j in range(4):
                a, b = C4[j], C4[(j + 1) % 4]
                bar(mb, "MS_Corten", leg(a[0], a[1], z), leg(b[0], b[1], z), 5.0, 5.0, c=0.5)
                bar(mb, "MS_Corten", leg(a[0], a[1], lv[i]), leg(b[0], b[1], z), 4.0, 4.0, c=0.4)
        cbox(mb, "MS_Trim", I, -26.0, 26.0, -26.0, 26.0, 858.0, 866.0, 1.5)          # yaw bearing seat
        cyl(mb, "MS_Pipe", (0, 0, zt - 30.0), (0, 0, 880.0), 9.0, 10, c=1.0)           # mast up to the yaw pivot
    def nacelle():
        cyl(mb, "MS_Pipe", (0, 0, 878.0), (0, 0, 892.0), 12.0, 12, c=1.0)             # turntable collar
        cbox(mb, "MS_Trim", I, -34.0, 40.0, -13.0, 13.0, 890.0, 920.0, 3.0)           # nacelle housing
        cyl(mb, "MS_Pipe", (-34.0, 0.0, 905.0), (-96.0, 0.0, 905.0), 3.0, 8, c=0.6)   # tail boom
    def vane():
        cyl(mb, "MS_Pipe", (-95.0, 0.0, 892.0), (-95.0, 0.0, 930.0), 2.2, 8, c=0.4)   # vertical axle
        cbox(mb, "MS_Tin", I, -128.0, -95.0, -1.0, 1.0, 884.0, 930.0, 0.4)            # fin
    def light():
        cyl(mb, "MS_Beacon", (0.0, 0.0, 920.0), (0.0, 0.0, 932.0), 5.0, 8, c=1.5)
    def hub():
        cyl(mb, "MS_Rotor", (38.0, 0.0, 905.0), (46.0, 0.0, 905.0), 8.0, 8, c=1.0)      # main shaft stub
        cyl(mb, "MS_Rotor", (44.0, 0.0, 905.0), (58.0, 0.0, 905.0), 14.0, 12, c=1.5)    # hub disc, blade roots (r 12) sink into it
        lathe(mb, "MS_Rotor", axis_fr((58.0, 0.0, 905.0), (1, 0, 0)), [(0.0, 0.0), (0.0, 13.0), (9.0, 7.0), (18.0, 0.0)], 12)   # spinner
    part("WG_Root", root); part("WG_Tower", tower); part("WG_Nacelle_Yaw", nacelle); part("WG_TailVane", vane)
    part("WG_Light_Obstr", light); part("WG_Rotor_Hub", hub)
    for i in range(3): part("WG_Blade_%d" % i, lambda i=i: blade_hulls(mb, i))
    k.slots = [s for s in SLOT_CAT if any(m == s for (_, m, _) in mb.f)]
    return k, rng

# ---------------------------------------------------------------- Max scene
MXS = r'''
global wg_skin, wg_check
fn wg_skin m bonesArr rangesArr = (
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
    max create mode
    ids
)
fn wg_check m = (
    local sk = m.modifiers[#Skin]
    local bad = 0
    for v = 1 to (skinOps.GetNumberVertices sk) do
        if (skinOps.GetVertexWeightCount sk v) != 1 do bad += 1
    bad
)
'''

def build_scene():
    """Fresh scene (a copy of whatever was open is backed up first), units cm, 30 fps."""
    if not os.path.isdir(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    cur = os.path.join(str(rt.maxFilePath), str(rt.maxFileName))
    if os.path.normcase(cur) != os.path.normcase(MAX_PATH) and len(list(rt.objects)) > 0:
        bk = os.path.join(BACKUP_DIR, "pre_windgen_%s" % (str(rt.maxFileName) or "untitled.max"))
        rt.saveMaxFile(bk, clearNeedSaveFlag=False, useNewFile=False, quiet=True)
    rt.resetMaxFile(rt.Name("noPrompt"))
    rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    rt.units.DisplayType = rt.Name("Metric"); rt.units.MetricType = rt.Name("centimeters")
    rt.frameRate = FPS
    rt.execute(K["MXS"]); rt.execute(MXS)

def mir(v): return (v[0], -v[1], v[2])
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def vdot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]

def bone_frame(name):
    """Max-space bone frame. Everything is world-aligned except the blades: x = radial, y = +X (hub axis), z = x cross y."""
    if name.startswith("WG_Blade_"):
        u = mir(blade_dir(int(name[-1]))); x = u; y = (1.0, 0.0, 0.0); z = vcross(x, y)
        return x, y, z
    return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)

def make_bones():
    out = {}
    for (n, par, piv, ln) in BONES:
        x, y, z = bone_frame(n); p = mir(piv)
        b = rt.BoneSys.createBone(P3(p), P3((p[0]+x[0]*ln, p[1]+x[1]*ln, p[2]+x[2]*ln)), P3(z))
        b.name = n
        b.transform = rt.Matrix3(P3(x), P3(y), P3(z), P3(p))
        for prop, val in (("width", 6.0), ("height", 6.0)):
            try: setattr(b, prop, val)
            except Exception: pass
        try: b.boneAutoAlign = False
        except Exception: pass
        try: b.boneFreezeLength = True
        except Exception: pass
        b.wirecolor = rt.Color(40, 200, 255) if "Blade" not in n else rt.Color(255, 140, 0)
        if par: b.parent = out[par]
        out[n] = b
    return out

def build_mesh(k, rng):
    sid = {s: i + 1 for i, s in enumerate(k.slots)}; tris = k.mb.tris()
    node = rt.ak_make([P3(p) for p in k.mb.v], [rt.Point3(t[0]+1, t[1]+1, t[2]+1) for (t, m, g, e) in tris], [sid[m] for (t, m, g, e) in tris],
                      [g for (t, m, g, e) in tris], [e for (t, m, g, e) in tris], ASSET)
    node = rt.ak_uv(node, K["TILE"])
    node.material = rt.ak_mm("MM_" + ASSET, [phys_mat(s) for s in k.slots], list(k.slots))
    return node

def save_scene():
    d = os.path.dirname(MAX_PATH)
    if not os.path.isdir(d): os.makedirs(d)
    rt.execute("max create mode"); rt.windows.processPostedMessages(); rt.completeRedraw(); rt.windows.processPostedMessages()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)

GUARD = r'''
global wg_guard_timer
fn wg_guard_tick s e = (
    s.Stop()
    if (maxFilePath + maxFileName) == @"%s" and getSaveRequired() do
        saveMaxFile (maxFilePath + maxFileName) clearNeedSaveFlag:true useNewFile:true quiet:true
    setSaveRequired false
    dotNet.removeAllEventHandlers s
)
wg_guard_timer = dotNetObject "System.Windows.Forms.Timer"
wg_guard_timer.Interval = 1500
dotNet.addEventHandler wg_guard_timer "Tick" wg_guard_tick
wg_guard_timer.Start()
''' % MAX_PATH

# ---------------------------------------------------------------- animation
ANIM_MXS = r'''
global wg_clear, wg_setkey, wg_tang, wg_world, wg_hold
fn wg_clear b = ( deleteKeys b #allKeys )
fn wg_world b t = ( at time t ( b.transform ) )
fn wg_hold b t = (   -- stacked source layout: freeze each channel on its last key before a take starts (no drift between takes)
    local rc = b.rotation.controller
    for c in #(rc.X_Rotation.controller, rc.Y_Rotation.controller, rc.Z_Rotation.controller) do
        if c != undefined do (
            local best = undefined
            for k in c.keys do if k.time < t and (best == undefined or k.time > best.time) do best = k
            if best != undefined do best.outTangentType = #step
        )
)
fn wg_setkey b chan val t = (
    with animate on (
        at time t (
            local rc = b.rotation.controller
            case chan of ( 1: rc.X_Rotation = val; 2: rc.Y_Rotation = val; 3: rc.Z_Rotation = val )
        )
    )
)
fn wg_tang b typ t0 t1 = (
    local rc = b.rotation.controller
    for c in #(rc.X_Rotation.controller, rc.Y_Rotation.controller, rc.Z_Rotation.controller) do
        if c != undefined do for k in c.keys do
            if k.time >= t0 and k.time <= t1 do ( k.inTangentType = typ; k.outTangentType = typ )
)
'''
BIND_LOCAL = {}                                    # name -> Matrix3 (local bind TM relative to the parent), captured before any key
BIND_WORLD = {}
def smoothstep(x):
    x = max(0.0, min(1.0, x)); return x * x * (3.0 - 2.0 * x)

def capture_bind(bones):
    BIND_LOCAL.clear(); BIND_WORLD.clear()
    for n in BONE_ORDER:
        b = bones[n]; BIND_WORLD[n] = b.transform
        BIND_LOCAL[n] = b.transform * rt.inverse(b.parent.transform) if b.parent else b.transform

def restore_bind(bones):
    for n in BONE_ORDER:
        bones[n].transform = BIND_WORLD[n]

def clear_anim(bones):
    for n in BONE_ORDER: rt.wg_clear(bones[n])
    restore_bind(bones)

def blade_pitch_sign(i):
    """+1 when a positive Max rotation about the blade bone's local X (radial) turns the chord from tangent toward +X (pitch up)."""
    u = mir(blade_dir(i)); w = mir((0.0, -blade_dir(i)[2], blade_dir(i)[1])); c = vcross(u, w)
    return 1.0 if vdot(c, (1.0, 0.0, 0.0)) > 0 else -1.0

def euler_of(n, axis, ang_deg):
    """Euler XYZ (deg) of  rotate(ang about the bone's local axis) * bindLocal."""
    rm = (rt.rotateXMatrix, rt.rotateYMatrix, rt.rotateZMatrix)[axis](ang_deg)
    q = (rm * BIND_LOCAL[n]).rotationpart
    e = rt.quatToEuler(q)
    return float(e.x), float(e.y), float(e.z)

def key_delta(bones, n, axis, ang_deg, f, direct=False):
    """Key bone n at frame f with a local rotation `ang_deg` (Max sign) about its bind-frame axis (0 X, 1 Y, 2 Z).
    direct=True (bind rotation = identity): write the angle straight into that Euler channel, so multi-turn values never wrap
    (quatToEuler would fold 240 -> -120 and the linear segment would run backwards). Blades go through the matrix path (|angle| <= 80)."""
    t = rt.execute("%df" % int(f))
    if direct:
        rt.wg_setkey(bones[n], axis + 1, float(ang_deg), t); return
    ex, ey, ez = euler_of(n, axis, ang_deg)
    for ch, v in ((1, ex), (2, ey), (3, ez)): rt.wg_setkey(bones[n], ch, v, t)

def finish(bones, names, typ, f0, f1):
    t0, t1 = rt.execute("%df" % int(f0)), rt.execute("%df" % int(f1))
    for n in names: rt.wg_tang(bones[n], rt.Name(typ), t0, t1)

def take_spin(bones, f0=0, clear=True):
    if clear: clear_anim(bones)
    for i in range(4): key_delta(bones, "WG_Rotor_Hub", 0, UE_SIGN * 360.0 * i / 3.0, f0 + 30 * i, True)       # 0 / 120 / 240 / 360 UE roll, clockwise from upwind
    for i in range(3): key_delta(bones, "WG_Blade_%d" % i, 0, 0.0, f0); key_delta(bones, "WG_Blade_%d" % i, 0, 0.0, f0 + 90)   # blades hold the 8 deg bind pitch
    finish(bones, BONE_ORDER[5:], "linear", f0, f0 + 90); return (f0, f0 + 90)

def take_hunt(bones, f0=0, clear=True):
    if clear: clear_anim(bones)
    for f in range(0, 241, 20):
        key_delta(bones, "WG_Nacelle_Yaw", 2, UE_SIGN * 10.0 * math.sin(2 * math.pi * f / 240.0), f0 + f, True)
        key_delta(bones, "WG_TailVane", 2, UE_SIGN * 15.0 * math.sin(2 * math.pi * (f - 20.0) / 240.0), f0 + f, True)   # 20 f lag
    finish(bones, ["WG_Nacelle_Yaw", "WG_TailVane"], "smooth", f0, f0 + 240); return (f0, f0 + 240)

def take_furl(bones, f0=0, clear=True):
    if clear: clear_anim(bones)
    for f in range(0, 61):
        s = smoothstep(f / 60.0)
        key_delta(bones, "WG_Nacelle_Yaw", 2, UE_SIGN * 55.0 * s, f0 + f, True)
        key_delta(bones, "WG_TailVane", 2, UE_SIGN * -35.0 * s, f0 + f, True)
        for i in range(3): key_delta(bones, "WG_Blade_%d" % i, 0, blade_pitch_sign(i) * 80.0 * s, f0 + f)     # pitch 8 -> 88
    finish(bones, ["WG_Nacelle_Yaw", "WG_TailVane", "WG_Blade_0", "WG_Blade_1", "WG_Blade_2"], "linear", f0, f0 + 60); return (f0, f0 + 60)

TAKES = [("A_WindGen_Spin", take_spin), ("A_WindGen_Hunt", take_hunt), ("A_WindGen_Furl", take_furl)]

# ---------------------------------------------------------------- probes (all angles reported in UE space)
def _rows(m): return [(float(r.x), float(r.y), float(r.z)) for r in (m.row1, m.row2, m.row3)]
def _tof(bones, n, f): return rt.wg_world(bones[n], rt.execute("%df" % int(f)))
def _ue(v): return (v[0], -v[1], v[2])
def _comb(c, rows): return tuple(sum(c[i] * rows[i][k] for i in range(3)) for k in range(3))

def chord_bind(i):
    """Bind chord direction (Max space) of the blade i mean section (pitch 8 deg)."""
    u = blade_dir(i); w = (0.0, -u[2], u[1]); phi = rad(PITCH_BIND)
    return mir(tuple(math.cos(phi) * w[k] + math.sin(phi) * (1.0, 0.0, 0.0)[k] for k in range(3)))

def probe(bones, frames):
    out = {}
    b0 = _rows(BIND_WORLD["WG_Blade_0"]) if False else None
    for f in frames:
        h = _rows(_tof(bones, "WG_Blade_0", f))
        rad0 = _ue(h[0]); roll = math.degrees(math.atan2(rad0[2], rad0[1]))
        nx = _ue(_rows(_tof(bones, "WG_Nacelle_Yaw", f))[0]); vx = _ue(_rows(_tof(bones, "WG_TailVane", f))[0])
        row = {"roll_ue": round(roll, 2), "nac_yaw_ue": round(math.degrees(math.atan2(nx[1], nx[0])), 2), "vane_yaw_ue": round(math.degrees(math.atan2(vx[1], vx[0])), 2)}
        ps = []
        for i in range(3):
            bw = _rows(BIND_WORLD["WG_Blade_%d" % i]); c0 = chord_bind(i)
            loc = tuple(sum(c0[k] * bw[a][k] for k in range(3)) for a in range(3))
            cn = _comb(loc, _rows(_tof(bones, "WG_Blade_%d" % i, f)))
            ps.append(round(math.degrees(math.asin(max(-1.0, min(1.0, cn[0])))), 1))   # chord axial angle = section pitch phi (UE +X is Max +X)
        row["blade_chord_axial_deg"] = ps
        out[f] = row
    return out


# ---------------------------------------------------------------- build / export
STACK = {"A_WindGen_Spin": 0, "A_WindGen_Hunt": 100, "A_WindGen_Furl": 350}      # take offsets on the saved .max timeline (export re-authors each at frame 0)
STATE = {}

def layout_takes(bones):
    clear_anim(bones)
    for i, (name, fn) in enumerate(TAKES):
        fn(bones, STACK[name], clear=False)
        if i > 0:
            t0 = rt.execute("%df" % STACK[name])
            for n in BONE_ORDER: rt.wg_hold(bones[n], t0)
    rt.animationRange = rt.Interval(0, 410); rt.execute("sliderTime = 0f")

def build():
    build_scene()
    k, rng = build_geometry(); bones = make_bones()
    bmin, bmax = k.mb.bbox(); ue_tris = len(k.mb.tris()); ue_open = k.mb.open_edges()
    k.mirror_y(); node = build_mesh(k, rng)
    rt.wg_skin(node, [bones[n] for n in BONE_ORDER], [[rng[n][0], rng[n][1]] for n in BONE_ORDER])
    rt.execute(ANIM_MXS); capture_bind(bones)
    bad = int(rt.wg_check(node)); tm = rt.snapshotAsMesh(node)
    lay = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay.addnode(node)
    for b in bones.values(): lay.addnode(b)
    STATE.update({"node": node, "bones": bones, "rng": rng})
    layout_takes(bones)
    st = {"tris": int(tm.numfaces), "tris_ue_local": ue_tris, "verts": int(rt.polyop.getNumVerts(node)), "open_edges": int(rt.polyop.getOpenEdges(node).numberSet),
          "open_edges_builder": ue_open, "verts_not_single_weight": bad, "bones": len(bones), "slots": k.slots,
          "bbox_min": [round(c, 1) for c in bmin], "bbox_max": [round(c, 1) for c in bmax], "vertex_ranges": rng}
    rig = {"asset": ASSET, "units": "cm", "space": "authored UE-local, mirrored y->-y in Max; FBX import maps (x, y, z) -> (x, -y, z)", "fps": FPS,
           "bones": [{"name": n, "parent": par, "pos": list(piv)} for (n, par, piv, ln) in BONES],
           "sockets": {sn: {"bone": sd["bone"], "pos": list(sd["pos"])} for sn, sd in SOCKETS.items()},
           "takes": {"A_WindGen_Spin": [0, 90], "A_WindGen_Hunt": [0, 240], "A_WindGen_Furl": [0, 60]},
           "slots": k.slots, "stats": {a: b for a, b in st.items() if a != "vertex_ranges"}}
    with open(RIG_JSON, "w", encoding="utf-8") as f: json.dump(rig, f, indent=1)
    save_scene(); rt.execute(GUARD)
    st["_max_saved"] = os.path.exists(MAX_PATH); st["_dirty"] = bool(rt.getSaveRequired())
    return st

def _fbx_params(anim, f0=0, f1=0):
    rt.execute('''(
        FBXExporterSetParam "ResetExport"
        FBXExporterSetParam "Skin" true
        FBXExporterSetParam "Shape" false
        FBXExporterSetParam "SmoothingGroups" true
        FBXExporterSetParam "Triangulate" false
        FBXExporterSetParam "TangentSpaceExport" false
        FBXExporterSetParam "Cameras" false
        FBXExporterSetParam "Lights" false
        FBXExporterSetParam "EmbedTextures" false
        FBXExporterSetParam "ConvertUnit" "cm"
        FBXExporterSetParam "UpAxis" "Z"
        FBXExporterSetParam "ASCII" false
    )''')
    if anim:
        rt.execute('''(
            FBXExporterSetParam "Animation" true
            FBXExporterSetParam "BakeAnimation" true
            FBXExporterSetParam "BakeFrameStart" %d
            FBXExporterSetParam "BakeFrameEnd" %d
            FBXExporterSetParam "BakeFrameStep" 1
            FBXExporterSetParam "BakeResampleAnimation" true
        )''' % (f0, f1))
    else:
        rt.execute('FBXExporterSetParam "Animation" false')

def _export_selected(path):
    node, bones = STATE["node"], STATE["bones"]
    rt.clearSelection(); rt.select(node)
    for n in BONE_ORDER: rt.selectMore(bones[n])
    ok = rt.exportFile(path, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
    return {"ok": bool(ok), "bytes": os.path.getsize(path) if os.path.exists(path) else 0}

def export():
    if "node" not in STATE: raise RuntimeError("run build() first in this Max session")
    bones = STATE["bones"]
    if not os.path.isdir(FBX_DIR): os.makedirs(FBX_DIR)
    res = {}
    # 1) skeletal mesh: bind pose = frame 0 of the Spin take, no animation
    take_spin(bones, 0); rt.animationRange = rt.Interval(0, 90); rt.execute("sliderTime = 0f")
    _fbx_params(False); res[ASSET] = _export_selected(os.path.join(FBX_DIR, ASSET + ".fbx"))
    # 2) one baked 30 fps FBX per take, authored at frames 0..N
    for name, fn in TAKES:
        f0, f1 = fn(bones, 0); rt.animationRange = rt.Interval(f0, f1); rt.execute("sliderTime = 0f")
        _fbx_params(True, f0, f1); res[name] = _export_selected(os.path.join(FBX_DIR, name + ".fbx")); res[name]["frames"] = [f0, f1]
    # 3) back to the stacked source layout, save, clear the dirty flag
    layout_takes(bones); rt.clearSelection(); save_scene(); rt.execute(GUARD)
    res["_dirty"] = bool(rt.getSaveRequired())
    return res
