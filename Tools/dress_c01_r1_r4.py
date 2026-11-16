"""
AOS-DK: dress Cluster C-01 rooms A03_R1 (Lobby), A03_R2 (Capsules Atrium), A03_R3 (Rec Hall), A03_R4 (Canteen) in Lvl_FirstPerson,
+ mobility fix (KikutakeSlab_Tiles / S4_RingBus -> Static).
Run inside UE 5.7 (execute_python):
    ns = {"__name__": "__main__", "DRESS_MODE": "all", "DRESS_ROOMS": ["R1","R2","R3","R4"]}
    exec(compile(open(PATH).read(), PATH, "exec"), ns)
DRESS_MODE: mobility | clear | build | verify | save | all   (idempotent: every spawned actor carries TAG (+room tag) and is wiped first)

Method: props are batched into one ISM actor per (mesh, material, room) (draw-call budget); every candidate is tested BEFORE placement against
  room bounds, Shell-1 corridors (XY-inflated polylines r=340 = 245 sphere + 95 margin, capped at door-top Z), R2 central 1700x1700 core,
  IA_* AABBs (+150), SHELL_*/PRT_* AABBs. Rejected candidates are simply not placed (so doors get natural gaps).
Geometry (world cm, floor faces): R1 X-53500..-51100 Y20600..23800 Z-9800..-8450 | R2 X-51000..-49000 Y22000..24000 Z-9800..-5300
  R3 X-52000..-48000 Y24100..26900 Z-8900..-7550 | R4 X-48500..-46900 Y20600..23000 Z-9800..-8900
"""
import unreal, math, json

MODE = globals().get("DRESS_MODE", "all")
ROOMS = globals().get("DRESS_ROOMS", ["R1", "R2", "R3", "R4"])
TAG = "AOS_DressR1R4"
FOLDER = "Environment/Clusters/C01_Home_A03/Props_R1_R4"
KIT = "/Game/AOS_DK_Game/Environment/ModularKit/"
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
RESULT = {"mode": MODE}
V = lambda t: unreal.Vector(*t)

BOUNDS = {
    "R1": (-53500.0, 20600.0, -9800.0, -51100.0, 23800.0, -8450.0),
    "R2": (-51000.0, 22000.0, -9800.0, -49000.0, 24000.0, -5300.0),
    "R3": (-52000.0, 24100.0, -8900.0, -48000.0, 26900.0, -7550.0),
    "R4": (-48500.0, 20600.0, -9800.0, -46900.0, 23000.0, -8900.0),
}
R2_CORE = (-50850.0, 22150.0, -9800.0, -49150.0, 23850.0, -5300.0)   # 1700x1700 Shell-1 vertical core (to R5)
# Shell-1 corridors: (XY polyline, radius, Z cap = door-top / lane top; None = full height)
CORR = {
    "R1": [([(-53500, 22038), (-52000, 22038)], 340, -8700),
           ([(-52000, 22038), (-52000, 23000), (-51000, 23000)], 340, -8700),
           ([(-52000, 22038), (-52000, 21035), (-50900, 21035)], 340, -8700)],
    "R2": [([(-51000, 23000), (-50850, 23000)], 340, -8350),     # D-M west (R1)
           ([(-50000, 23850), (-50000, 24000)], 340, -8312),    # D-T north (R3)
           ([(-49150, 23000), (-49000, 23000)], 340, -5402),    # D-M east (R5)
           ([(-49150, 22500), (-49000, 22500)], 260, -9480)],   # D-S east (R4)
    "R3": [([(-50000, 24100), (-50000, 26300)], 340, None),
           ([(-51000, 25500), (-49000, 25500)], 340, None)],
    "R4": [([(-48500, 21035), (-47500, 21035), (-47445, 21600)], 340, None),
           ([(-48500, 22500), (-47900, 22500)], 260, None)],
}
MESH = {
    "conduit": KIT + "SM_CableTray_ConduitRun_Straight", "tray": KIT + "SM_CableTray_Straight",
    "cw": KIT + "SM_Catwalk_Grating_Module", "p20": KIT + "SM_Pipe_Straight_D20", "p40": KIT + "SM_Pipe_Straight_D40",
    "p80": KIT + "SM_Pipe_Straight_D80", "duct": KIT + "SM_Vent_Duct_Straight", "ib300": KIT + "SM_Steel_IBeam_300",
    "ib600": KIT + "SM_Steel_IBeam_600", "cube": "/Engine/BasicShapes/Cube", "cyl": "/Engine/BasicShapes/Cylinder"}
LEN = {"conduit": 300.0, "tray": 300.0, "p20": 400.0, "p40": 400.0, "p80": 400.0, "duct": 200.0, "ib300": 300.0, "ib600": 600.0}
MAT = {None: None, "steel": KIT + "Materials/MI_Kit_DarkSteel", "galv": KIT + "Materials/MI_Kit_Galvanized",
       "paint": KIT + "Materials/MI_Kit_PipePaint", "safety": KIT + "Materials/MI_Kit_SafetyPaint",
       "g_cyan": KIT + "Materials/MI_Kit_Glow_Cyan", "g_warm": KIT + "Materials/MI_Kit_Glow_Warm", "g_green": KIT + "Materials/MI_Kit_Glow_Green"}
GLOW = {"g_cyan", "g_warm", "g_green"}
CYAN, WARM, GREEN = (139, 233, 253), (255, 184, 108), (80, 250, 123)   # Dracula Cyan / Orange / Green


def tags_of(a): return [str(t) for t in a.tags]


def clear(rooms):
    n = 0
    for a in eas.get_all_level_actors():
        t = tags_of(a)
        if TAG in t and any((TAG + "_" + r) in t for r in rooms):
            eas.destroy_actor(a); n += 1
    return n


def ensure_glow():
    at = unreal.AssetToolsHelpers.get_asset_tools(); lib = unreal.MaterialEditingLibrary
    parent = unreal.load_asset("/Game/AOS_DK_Game/Environment/CustomHero/Materials/M_AOS_HeroSurface")
    defs = {"MI_Kit_Glow_Cyan": ((0.2582, 0.8148, 0.9823), 4.0), "MI_Kit_Glow_Warm": ((1.0, 0.4793, 0.15), 3.5),
            "MI_Kit_Glow_Green": ((0.0802, 0.9560, 0.1981), 5.0)}
    made = []
    for name, (c, inten) in defs.items():
        path = KIT + "Materials/" + name
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            continue
        mi = at.create_asset(name, KIT + "Materials", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", parent)
        lib.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        lib.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(c[0], c[1], c[2], 1.0))
        lib.set_material_instance_scalar_parameter_value(mi, "EmissiveIntensity", inten)
        lib.set_material_instance_scalar_parameter_value(mi, "Roughness", 0.4)
        unreal.EditorAssetLibrary.save_asset(path)
        made.append(name)
    return made


_assets = {}
def asset(p):
    if p not in _assets:
        _assets[p] = unreal.load_asset(p); assert _assets[p] is not None, "missing asset " + p
    return _assets[p]


_bounds = {}
def mbounds(k):
    if k not in _bounds:
        b = asset(MESH[k]).get_bounds()
        _bounds[k] = ((b.origin.x, b.origin.y, b.origin.z), (b.box_extent.x, b.box_extent.y, b.box_extent.z))
    return _bounds[k]


def aabb_of(k, loc, yaw, pitch, scale):
    o, e = mbounds(k)
    t = unreal.Transform(location=V(loc), rotation=unreal.Rotator(roll=0, pitch=pitch, yaw=yaw), scale=V(scale))
    lo = [1e18] * 3; hi = [-1e18] * 3
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = t.transform_location(unreal.Vector(o[0] + sx * e[0], o[1] + sy * e[1], o[2] + sz * e[2]))
                for i, v in enumerate((p.x, p.y, p.z)):
                    lo[i] = min(lo[i], v); hi[i] = max(hi[i], v)
    return lo + hi


def aabb_actor(a):
    o, e = a.get_actor_bounds(False)
    return (o.x - e.x, o.y - e.y, o.z - e.z, o.x + e.x, o.y + e.y, o.z + e.z)


def box_overlap(A, B, tol=0.5):
    return all(A[i] < B[i + 3] - tol and A[i + 3] > B[i] + tol for i in range(3))


def inside(A, B, tol=1.0):
    return all(A[i] >= B[i] - tol and A[i + 3] <= B[i + 3] + tol for i in range(3))


WORLD = {}
def init_world():
    ia, solid = [], []
    for a in eas.get_all_level_actors():
        l = a.get_actor_label()
        if l.startswith("IA_"):
            b = aabb_actor(a); ia.append((l, (b[0] - 150, b[1] - 150, b[2] - 150, b[3] + 150, b[4] + 150, b[5] + 150)))
        elif l.startswith("SHELL_") or l.startswith("PRT_"):
            solid.append((l, aabb_actor(a)))
    WORLD["ia"], WORLD["solid"] = ia, solid


def corridor_hit(room, A):
    for pts, r, zcap in CORR.get(room, []):
        if zcap is not None and A[2] >= zcap - 0.5:
            continue
        for (p, q) in zip(pts[:-1], pts[1:]):
            L = math.hypot(q[0] - p[0], q[1] - p[1]); n = max(1, int(L / 20.0))
            for s in range(n + 1):
                px = p[0] + (q[0] - p[0]) * s / n; py = p[1] + (q[1] - p[1]) * s / n
                dx = max(A[0] - px, 0.0, px - A[3]); dy = max(A[1] - py, 0.0, py - A[4])
                if dx * dx + dy * dy < r * r:
                    return True
    return False


def reject(room, A):
    if not inside(A, BOUNDS[room]): return "room"
    if room == "R2" and box_overlap(A, R2_CORE): return "core"
    if corridor_hit(room, A): return "corridor"
    for l, B in WORLD["ia"]:
        if box_overlap(A, B): return "IA"
    for l, B in WORLD["solid"]:
        if box_overlap(A, B): return "solid"
    return None


GROUPS, REC, STAT, LIGHTS = {}, {}, {}, {}


def put(room, label, k, loc, yaw=0.0, pitch=0.0, scale=(1, 1, 1), mat=None):
    A = aabb_of(k, loc, yaw, pitch, scale)
    why = reject(room, A); st = STAT[room]
    if why:
        st["rej"][why] = st["rej"].get(why, 0) + 1; return False
    GROUPS[room].setdefault((k, mat), []).append((loc, yaw, pitch, scale))
    REC[room].append({"l": label, "m": k, "mat": mat, "aabb": [round(v, 1) for v in A]})
    st["placed"] += 1
    return True


def box(room, label, c, size, mat, yaw=0.0):
    return put(room, label, "cube", c, yaw, 0.0, (size[0] / 100.0, size[1] / 100.0, size[2] / 100.0), mat)


def cyl(room, label, c, dia, h, mat):
    return put(room, label, "cyl", c, 0.0, 0.0, (dia / 100.0, dia / 100.0, h / 100.0), mat)


def run(room, label, k, a0, a1, fixed, z, axis, mat=None, cross=(1, 1)):
    seg = LEN[k]; total = abs(a1 - a0); n = max(1, int(round(total / seg))); piece = total / n; sc = piece / seg
    for i in range(n):
        p = a0 + i * piece
        if axis == "x": put(room, "%s_%02d" % (label, i), k, (p, fixed, z), 0.0, 0.0, (sc, cross[0], cross[1]), mat)
        else: put(room, "%s_%02d" % (label, i), k, (fixed, p, z), 90.0, 0.0, (sc, cross[0], cross[1]), mat)


def vrun(room, label, k, x, y, z0, z1, mat=None, cross=(1, 1)):
    seg = LEN[k]; total = z1 - z0; n = max(1, int(round(total / seg))); piece = total / n; sc = piece / seg
    for i in range(n):
        put(room, "%s_%02d" % (label, i), k, (x, y, z0 + i * piece), 0.0, 90.0, (sc, cross[0], cross[1]), mat)


def light(room, label, loc, color, lumens, radius, shadow, src_r=8.0):
    LIGHTS[room].append((label, loc, color, lumens, radius, shadow, src_r))


# ============================================================================ rooms
def build_R1():
    R, F = "R1", -9800.0
    run(R, "Conduit_N", "conduit", -53480, -51120, 23765, -8700, "x")
    run(R, "Conduit_S", "conduit", -53480, -51120, 20635, -8700, "x")
    run(R, "Conduit_W1", "conduit", 20630, 21590, -53465, -8700, "y")
    run(R, "Conduit_W2", "conduit", 22490, 23730, -53465, -8700, "y")
    run(R, "Conduit_E", "conduit", 21500, 22440, -51140, -8700, "y")
    run(R, "Pipe_N", "p40", -53480, -51120, 23760, -8560, "x", "paint")
    run(R, "Pipe_W", "p40", 20620, 23780, -53440, -8560, "y", "paint")
    # catwalk gallery edges (z=-9100 deck) N / W / S
    for i in range(12): put(R, "CW_N_%02d" % i, "cw", (-53400 + 200 * i, 23740, -9100), 0)
    for j in range(5): put(R, "CW_W_%02d" % j, "cw", (-53445, 22650 + 200 * j, -9100), 90)
    for i in range(8): put(R, "CW_S_%02d" % i, "cw", (-53400 + 200 * i, 20650, -9100), 0)
    for x in (-53300, -52900, -52500, -52100, -51700, -51300):
        box(R, "Post_N", (x, 23780, -9450), (15, 15, 700), "steel")
    for x in (-53300, -52700, -52100):
        box(R, "Post_S", (x, 20610, -9450), (15, 15, 700), "steel")
    for y in (22700, 23300):
        box(R, "Post_W", (-53485, y, -9450), (15, 15, 700), "steel")
    # SomaLock entry framing (opening Y 21618..22458, Z -9570..-8730)
    vrun(R, "Frame_JambS", "ib300", -53380, 21590, F, -8700, "safety", (3, 3))
    vrun(R, "Frame_JambN", "ib300", -53380, 22486, F, -8700, "safety", (3, 3))
    run(R, "Frame_Lintel", "ib600", 21514, 22534, -53380, -8690, "y", "safety", (3, 3))
    # Dracula accents
    box(R, "Acc_Cyan_N", (-52300, 23796, -8520), (2360, 4, 4), "g_cyan")
    box(R, "Acc_Cyan_S", (-52300, 20604, -8520), (2360, 4, 4), "g_cyan")
    box(R, "Acc_Warm_Gal", (-52300, 23688, -9110), (2300, 3, 3), "g_warm")
    box(R, "Acc_Warm_SomaS", (-53470, 21600, -9150), (4, 4, 840), "g_warm")
    box(R, "Acc_Warm_SomaN", (-53470, 22476, -9150), (4, 4, 840), "g_warm")
    # benches on the solid east wall segment
    for y in (21770, 22150):
        box(R, "Bench_Seat", (-51120, y, F + 45), (40, 300, 8), "steel")
        box(R, "Bench_LegA", (-51120, y - 130, F + 21), (30, 10, 42), "steel")
        box(R, "Bench_LegB", (-51120, y + 130, F + 21), (30, 10, 42), "steel")
    light(R, "Light_00", (-53300, 22038, -8650), WARM, 900, 800, False)
    light(R, "Light_01", (-52000, 21200, -8650), CYAN, 900, 800, False)
    light(R, "Light_02", (-52000, 23300, -8650), CYAN, 800, 800, True)
    light(R, "Light_03", (-52700, 23700, -9000), WARM, 700, 600, False)
    light(R, "Light_04", (-51250, 22040, -8700), CYAN, 700, 650, False)
    light(R, "Light_05", (-52700, 20700, -9000), CYAN, 600, 600, False)


def build_R2():
    R, F = "R2", -9800.0
    levels = [-8900.0, -8000.0, -7100.0, -6200.0]
    for lv, z in enumerate(levels):
        for j in range(7):
            put(R, "CW_W_L%d_%02d" % (lv, j), "cw", (-50945, 22350 + 200 * j, z), 90)
            put(R, "CW_E_L%d_%02d" % (lv, j), "cw", (-49055, 22350 + 200 * j, z), 90)
            put(R, "CW_S_L%d_%02d" % (lv, j), "cw", (-50650 + 200 * j, 22055, z), 0)
            put(R, "CW_N_L%d_%02d" % (lv, j), "cw", (-50650 + 200 * j, 23945, z), 0)
        # capsule window glow panels (ambient), pattern: cyan / warm / dead
        for j in range(5):
            pat = (lv * 3 + j) % 5
            mat = "g_cyan" if pat in (0, 3) else ("g_warm" if pat in (1, 4) else "steel")
            zc = z + 210.0
            box(R, "Win_W_L%d_%d" % (lv, j), (-50997, 22400 + 300 * j, zc), (6, 110, 70), mat)
            mat = "g_warm" if pat in (0, 3) else ("g_cyan" if pat in (1, 4) else "steel")
            box(R, "Win_E_L%d_%d" % (lv, j), (-49003, 22400 + 300 * j, zc), (6, 110, 70), mat)
            mat = "g_cyan" if pat in (1, 2) else ("g_warm" if pat in (0, 4) else "steel")
            box(R, "Win_S_L%d_%d" % (lv, j), (-50600 + 300 * j, 22003, zc), (110, 6, 70), mat)
            mat = "g_warm" if pat in (1, 2) else ("g_cyan" if pat in (0, 4) else "steel")
            box(R, "Win_N_L%d_%d" % (lv, j), (-50600 + 300 * j, 23997, zc), (110, 6, 70), mat)
    # structural vertical pipes in the four corners (D80 + two D40 each), floor -> ceiling
    for (cx, cy, sx, sy) in ((-50945, 22055, 1, 1), (-49055, 22055, -1, 1), (-50945, 23945, 1, -1), (-49055, 23945, -1, -1)):
        vrun(R, "VPipe80", "p80", cx, cy, F, -5300.0, "paint")
        vrun(R, "VPipe40a", "p40", cx, cy + sy * 105, F, -5300.0, "paint")
        vrun(R, "VPipe40b", "p40", cx + sx * 105, cy, F, -5300.0, "paint")
    light(R, "Light_00", (-50880, 22180, -9300), CYAN, 900, 1000, False)
    light(R, "Light_01", (-49120, 23820, -8300), WARM, 900, 1000, False)
    light(R, "Light_02", (-50880, 23820, -7400), CYAN, 900, 1000, True)
    light(R, "Light_03", (-49120, 22180, -6500), WARM, 900, 1000, False)
    light(R, "Light_04", (-50880, 22180, -5800), CYAN, 800, 1000, False)
    light(R, "Light_05", (-50000, 23000, -5450), CYAN, 700, 900, False)


def build_R3():
    R, F = "R3", -8900.0
    # hydroponic racks (east): 2 rows x 4, each 120 x 600 x 400 with algae glow shelves
    for rx in (-48100.0, -48400.0):
        for ry in (24400.0, 25100.0, 25800.0, 26500.0):
            for sx in (-57, 57):
                for sy in (-297, 297):
                    box(R, "Rack_Post", (rx + sx, ry + sy, F + 200), (6, 6, 400), "steel")
            for zh in (70, 190, 310):
                box(R, "Rack_Shelf", (rx, ry, F + zh), (120, 600, 4), "steel")
                box(R, "Rack_Algae", (rx, ry, F + zh + 4), (100, 560, 3), "g_green")
    # bleacher stands (west wall), 4 rows x 90
    for yc in (24750.0, 26200.0):
        for (x, h) in ((-51955.0, 160.0), (-51865.0, 120.0), (-51775.0, 80.0), (-51685.0, 40.0)):
            box(R, "Stand", (x, yc, F + h / 2.0), (90, 1200, h), "steel")
        box(R, "Stand_Edge", (-51640.0, yc, F + 41), (3, 1180, 3), "g_cyan")
    # algae glow strips along the base of the north wall + south wall (segmented, door gaps are automatic)
    for i in range(8):
        box(R, "Algae_N_%d" % i, (-51750 + 500 * i, 26893, F + 4), (480, 4, 4), "g_green")
        box(R, "Algae_S_%d" % i, (-51750 + 500 * i, 24107, F + 4), (480, 4, 4), "g_green")
    # wall pipes + ceiling ducts
    run(R, "Pipe_N80", "p80", -51990, -48010, 26840, -7650, "x", "paint")
    run(R, "Pipe_S40", "p40", -51990, -48010, 24150, -7650, "x", "paint")
    run(R, "Pipe_W40", "p40", 24120, 26880, -51940, -7650, "y", "paint")
    run(R, "Pipe_E40", "p40", 24120, 26880, -48060, -7650, "y", "paint")
    run(R, "Duct_A", "duct", 24120, 26880, -49200, -7595, "y", "galv")
    run(R, "Duct_B", "duct", 24120, 26880, -50800, -7595, "y", "galv")
    light(R, "Light_00", (-48300, 24400, -8000), GREEN, 900, 900, False)
    light(R, "Light_01", (-48300, 25300, -8000), GREEN, 900, 900, False)
    light(R, "Light_02", (-48300, 26300, -8000), GREEN, 900, 900, False)
    light(R, "Light_03", (-49500, 25500, -7900), CYAN, 1100, 1000, True)
    light(R, "Light_04", (-51600, 25000, -8000), WARM, 700, 800, False)
    light(R, "Light_05", (-51600, 26400, -8000), CYAN, 600, 800, False)


def build_R4():
    R, F = "R4", -9800.0
    # kitchen islands along the east wall (240 x 120 x 95)
    for y in (21650.0, 21950.0, 22250.0, 22550.0):
        box(R, "Isl_Base", (-46975, y, F + 42.5), (120, 240, 85), "steel")
        box(R, "Isl_Top", (-46975, y, F + 90), (130, 250, 10), "galv")
        box(R, "Isl_Glow", (-47038, y, F + 70), (4, 220, 4), "g_warm")
    # laundry: 24 washing machines 60 x 60 x 85 along the north wall
    for i in range(24):
        box(R, "Wash", (-48409 + 62 * i, 22965, F + 42.5), (60, 60, 85), "galv")
    for g in range(3):
        box(R, "Wash_Glow", (-48100 + 496 * g, 22933, F + 82), (480, 3, 3), "g_cyan")
    # filtration tanks D200 x 450 + risers
    for ty in (20800.0, 21250.0):
        cyl(R, "Tank", (-47000, ty, F + 225), 200, 450, "paint")
        cyl(R, "Tank_Ring", (-47000, ty, F + 330), 206, 6, "g_cyan")
        vrun(R, "Riser", "p20", -47000, ty, F + 450, -8900.0, "paint")
    # overhead pipes / ducts
    run(R, "Pipe_E80", "p80", 20620, 22980, -46955, -9040, "y", "paint")
    run(R, "Pipe_N40", "p40", -48480, -46960, 22965, -9040, "x", "paint")
    run(R, "Pipe_S40", "p40", -48480, -46960, 20635, -9040, "x", "paint")
    run(R, "Duct", "duct", -48400, -47000, 22830, -8935, "x", "galv")
    light(R, "Light_00", (-48000, 21035, -9050), CYAN, 700, 700, False)
    light(R, "Light_01", (-47400, 22400, -9050), WARM, 900, 800, True)
    light(R, "Light_02", (-47000, 22000, -9050), WARM, 700, 700, False)
    light(R, "Light_03", (-47900, 22850, -9050), CYAN, 600, 650, False)
    light(R, "Light_04", (-47000, 21100, -9050), CYAN, 600, 650, False)


BUILD = {"R1": build_R1, "R2": build_R2, "R3": build_R3, "R4": build_R4}


def spawn_ism(room, label, k, mat, items):
    c0 = BOUNDS[room]; ctr = ((c0[0] + c0[3]) / 2, (c0[1] + c0[4]) / 2, (c0[2] + c0[5]) / 2)
    a = eas.spawn_actor_from_class(unreal.Actor, V(ctr), unreal.Rotator(roll=0, pitch=0, yaw=0))
    a.root_component.set_mobility(unreal.ComponentMobility.STATIC)   # Static ISM under the default Movable root loses its attachment on level reload (world (0,0,0))
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root = sds.k2_gather_subobject_data_for_instance(a)[0]
    params = unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.InstancedStaticMeshComponent, blueprint_context=None)
    handle, fail = sds.add_new_subobject(params)
    comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    if not comp: raise RuntimeError("ISM component not created: %s" % fail)
    comp.set_static_mesh(asset(MESH[k]))
    if MAT[mat] is not None: comp.set_material(0, asset(MAT[mat]))
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    comp.set_collision_profile_name("BlockAll")
    if mat in GLOW: comp.set_editor_property("cast_shadow", False)
    a.set_actor_location(V(ctr), False, True)
    xf = [unreal.Transform(location=unreal.Vector(l[0] - ctr[0], l[1] - ctr[1], l[2] - ctr[2]),
                           rotation=unreal.Rotator(roll=0, pitch=p, yaw=y), scale=V(s)) for (l, y, p, s) in items]
    comp.add_instances(xf, False, False)
    a.set_actor_label(label); a.set_folder_path(FOLDER)
    a.tags = [unreal.Name(TAG), unreal.Name(TAG + "_" + room)]
    return a


def spawn_light(room, spec):
    label, loc, color, lumens, radius, shadow, src_r = spec
    a = eas.spawn_actor_from_class(unreal.PointLight, V(loc))
    c = a.get_component_by_class(unreal.PointLightComponent)
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    c.set_editor_property("intensity", lumens)
    c.set_editor_property("attenuation_radius", radius)
    c.set_editor_property("source_radius", src_r)
    c.set_editor_property("light_color", unreal.Color(*color, 255))
    c.set_editor_property("cast_shadows", shadow)
    c.set_editor_property("use_inverse_squared_falloff", True)
    a.set_actor_label("DR_%s_%s" % (room, label)); a.set_folder_path(FOLDER)
    a.tags = [unreal.Name(TAG), unreal.Name(TAG + "_" + room)]
    return a


REC_PATH = unreal.Paths.project_saved_dir() + "C01_dress_r1_r4_records.json"


def build(rooms):
    out = {"materials_created": ensure_glow()}
    init_world()
    allrec = {}
    try:
        allrec = json.load(open(REC_PATH))
    except Exception:
        pass
    for room in rooms:
        GROUPS[room], REC[room], STAT[room], LIGHTS[room] = {}, [], {"placed": 0, "rej": {}}, []
        BUILD[room]()
        n_ism = 0
        for (k, mat), items in GROUPS[room].items():
            spawn_ism(room, "DR_%s_ISM_%s_%s" % (room, k, mat or "default"), k, mat, items); n_ism += 1
        for spec in LIGHTS[room]: spawn_light(room, spec)
        out[room] = {"instances": STAT[room]["placed"], "ism_actors": n_ism, "rejected": STAT[room]["rej"], "lights": len(LIGHTS[room])}
        allrec[room] = REC[room]
    with open(REC_PATH, "w") as f: json.dump(allrec, f)
    return out


# ============================================================================ mobility fix
def fix_mobility():
    out = {}
    for a in eas.get_all_level_actors():
        l = a.get_actor_label()
        if l in ("KikutakeSlab_Tiles", "S4_RingBus"):
            root = a.root_component
            root.set_mobility(unreal.ComponentMobility.STATIC)
            for c in a.get_components_by_class(unreal.SceneComponent):
                c.set_mobility(unreal.ComponentMobility.STATIC)
            ism = a.get_component_by_class(unreal.InstancedStaticMeshComponent)
            out[l] = {"root": str(a.root_component.mobility), "ism": str(ism.mobility), "instances": ism.get_instance_count()}
    return out


# ============================================================================ verification
def hit_actor(h):
    for v in h.to_tuple():
        if isinstance(v, unreal.Actor): return v
    return None


def verify():
    out = {}
    init_world()
    allrec = json.load(open(REC_PATH))
    viol = {}
    cnt = {}
    for room, recs in allrec.items():
        cnt[room] = len(recs); bad = []
        for r in recs:
            A = r["aabb"]
            why = reject(room, A)
            if why: bad.append([r["l"], why])
        viol[room] = bad[:10]; cnt[room] = [len(recs), len(bad)]
    out["records_recheck(total,violations)"] = cnt
    out["recheck_violations"] = viol
    props = [a for a in eas.get_all_level_actors() if TAG in tags_of(a)]
    out["actors"] = len(props)
    out["folder_ok"] = all(str(a.get_folder_path()) == FOLDER for a in props)
    all_actors = eas.get_all_level_actors()

    def room_lights(room):
        R = BOUNDS[room]; n = sh = 0; mx = 0.0; names = []
        for a in all_actors:
            for c in a.get_components_by_class(unreal.LocalLightComponent):
                l = c.get_world_location()
                if R[0] <= l.x <= R[3] and R[1] <= l.y <= R[4] and R[2] - 50 <= l.z <= R[5] + 50:
                    n += 1; names.append(a.get_actor_label())
                    sh += 1 if bool(c.get_editor_property("cast_shadows")) else 0
                    mx = max(mx, float(c.get_editor_property("attenuation_radius")))
        return {"lights": n, "shadow": sh, "max_attenuation": mx}
    out["lights"] = {r: room_lights(r) for r in ROOMS_ALL}
    SL = unreal.SystemLibrary
    ign = [a for a in all_actors if isinstance(a, unreal.TriggerBox) or a.get_actor_label().startswith("IA_") or "WaterBody" in a.get_class().get_name()]
    ot = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2]

    def sweep(p0, p1, r=245.0):
        res = SL.sphere_trace_multi_for_objects(world, unreal.Vector(*p0), unreal.Vector(*p1), r, ot, False, ign, unreal.DrawDebugTrace.NONE, True)
        hits = res[1] if (isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], bool)) else res
        names = []
        for h in (hits or []):
            ac = hit_actor(h)
            if ac is not None: names.append(ac.get_actor_label())
        return sorted(set(names))
    legs = [
        ("R1: SomaLock -> hub (Z-9150)", (-53450, 22038, -9150), (-52000, 22038, -9150)),
        ("R1 hub -> D-M", (-52000, 22038, -9500), (-52000, 23000, -9500)),
        ("R1 -> D-M -> R2 core", (-52000, 23000, -9500), (-50000, 23000, -9500)),
        ("R2 vertical shaft R1 level -> R5 level", (-50000, 23000, -9500), (-50000, 23000, -5900)),
        ("R2 core -> D-M east -> R5", (-50000, 23000, -5900), (-48800, 23000, -5900)),
        ("R2 core -> D-T (Z-8600)", (-50000, 23000, -8600), (-50000, 24600, -8600)),
        ("R3 N-S lane", (-50000, 24600, -8600), (-50000, 26300, -8600)),
        ("R3 W-E lane", (-51000, 25500, -8600), (-49000, 25500, -8600)),
        ("R1 hub -> K-1 (Z-9500)", (-52000, 21035, -9500), (-50900, 21035, -9500)),
        ("K-1 -> R4 mouth", (-50900, 21035, -9500), (-48500, 21035, -9500)),
        ("R4 mouth -> CargoPod approach", (-48500, 21035, -9500), (-47500, 21035, -9500)),
        ("R4 pod approach", (-47500, 21035, -9500), (-47445, 21600, -9500)),
    ]
    sw = []
    for name, p0, p1 in legs:
        h = sweep(p0, p1); sw.append({"leg": name, "hits": h, "clear": len(h) == 0})
    out["sweep"] = sw; out["sweep_clear"] = all(s["clear"] for s in sw)
    ctrl = {
        "R1_bench": sweep((-51300, 21770, -9755), (-51110, 21770, -9755), 20.0),
        "R2_catwalk_W": sweep((-50870, 22350, -8850), (-50990, 22350, -8850), 20.0),
        "R3_rack": sweep((-48250, 24400, -8830), (-48100, 24400, -8830), 20.0),
        "R4_island": sweep((-47200, 21650, -9740), (-46980, 21650, -9740), 20.0),
    }
    out["controls"] = ctrl
    out["controls_ok"] = all(any(n.startswith("DR_" + k.split("_")[0]) for n in v) for k, v in ctrl.items())
    ok = out["sweep_clear"] and out["controls_ok"] and all(v[1] == 0 for v in cnt.values()) and \
        all(l["lights"] <= 8 and l["shadow"] <= 2 and l["max_attenuation"] <= 1500 for l in out["lights"].values())
    out["PASS"] = bool(ok)
    return out


ROOMS_ALL = ["R1", "R2", "R3", "R4"]


def save():
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(); return True
    except Exception as ex:
        return str(ex)


if MODE in ("mobility", "all"): RESULT["mobility"] = fix_mobility()
if MODE in ("clear", "build", "all"): RESULT["cleared"] = clear(ROOMS)
if MODE in ("build", "all"): RESULT["built"] = build(ROOMS)
if MODE in ("verify", "all"):
    RESULT["verify"] = verify()
    try:
        p = unreal.Paths.project_saved_dir() + "C01_dress_r1_r4_verify.json"
        with open(p, "w") as f: json.dump(RESULT["verify"], f, indent=1)
        RESULT["verify_file"] = p
    except Exception as ex:
        RESULT["verify_file_err"] = str(ex)
if MODE in ("save", "all"): RESULT["saved"] = save()
