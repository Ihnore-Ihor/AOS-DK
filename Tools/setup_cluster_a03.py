# AOS-DK | Cluster C-01 /home/a03 (Tower A-3 crown) + legacy style swap | UE 5.7.4 (run via execute_python)
# Sources of truth: AOS_TowerA_Spatial_Bible_EN.md §3.0.1 (Shell-1 / classes), §3.0.4 (BlockAll), §4.1 (openings),
#                   §4.2 (room types), §4.3 (C-01 rooms + link graph); claude/AOS_SomaLock_Spec_EN.md (pivot, lens, sockets);
#                   claude/AOS_DeficitKit_Build_Report_2026-11-10.md (kit pivots: openings = floor centre, passage +X).
# Idempotent: generated actors carry "AOS_C01" + "AOS_C01ID=<id>" and are reconciled by id (stale ids are removed;
# only actors carrying AOS_C01 are ever destroyed). Legacy swaps change the mesh IN PLACE and record the original
# mesh + transform in tags (AOS_LegacyMesh=, AOS_LegacyXform=) so they can be reverted.
# MODE: "assets" | "swap" | "build" | "verify" | "save" | "all" (= assets + swap + build + verify + save)
# Run:  g={"C01_MODE":"all"}; exec(open(<proj>/Tools/setup_cluster_a03.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, math, itertools

MODE = globals().get("C01_MODE", "all")
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
ANCHOR_LABEL, ANCHOR_SPEC = "ANC_A3_home_a03", (-48000.0, 22000.0, -9800.0)   # §4.3 origin B
# Plan offset of the room layout from B (Z = 0, so every floor height stays B + §4.3 value). The legacy TowerA_Wall
# (generated 16-gon tube, BlockAll complex, inner face r ~49 000, outer face r ~50 100, wall ~1 040 thick) passes 3 km
# east of B and would cut R4/R5/R6. -3000 in X puts the whole cluster outside it with >= 500 cm to its outer face
# (binding corner: R5 SE, B-frame (2400, -500) vs outer face x 2925).
PLAN_OFFSET = (-3000.0, 0.0, 0.0)
ROOT = "Environment/Clusters/C01_Home_A03"
F_ROOMS, F_PORTALS, F_VOLS = ROOT + "/Rooms", ROOT + "/Portals", ROOT + "/Volumes"
TAG_ALL, TAG_ID = "AOS_C01", "AOS_C01ID="

KIT = "/Game/AOS_DK_Game/Environment/ModularKit/"
M_ARCH, M_STAIRS = KIT + "SM_Concrete_Arch_Brutalist", KIT + "SM_Stairs_Concrete_Brutalist"
M_BULK, M_BEAM = KIT + "SM_Bulkhead_Frame_Door", KIT + "SM_Steel_IBeam_600"
M_SOMA = "/Game/AOS_DK_Game/Environment/CustomHero/SM_Breach_SomaLock"
SHARED = "/Game/AOS_DK_Game/Environment/Clusters/Shared"
M_BOX, M_BOX_SRC = SHARED + "/SM_AOS_ShellBox", "/Game/LevelPrototyping/Meshes/SM_Cube"   # 0..100 cube, 1 convex
MAT_BOX = SHARED + "/M_AOS_Concrete_BoxMap"
SRF = "/Game/Scene_UnfinishedBuilding/Assets/Megascans/Surfaces/"
MIS = {  # role -> (MI name, Megascans set). Textures are VT (sampler types below).
    "wall":    ("MI_A03_Concrete_Wall",    SRF + "Wall_Concrete_Rough_01/T_Wall_Concrete_Rough_01"),
    "floor":   ("MI_A03_Concrete_Floor",   SRF + "Floor_Concrete_Dusty_01/T_Floor_Concrete_Dusty_01"),
    "ceiling": ("MI_A03_Concrete_Ceiling", SRF + "Ceiling_Concrete_Raw_01/T_Ceiling_Concrete_Raw_01"),
}
TILE_CM = 200.0                 # 1 UV = 200 cm (kit UV standard)
CPD0 = 10                       # CPD 10..15 = piece offset from B (xyz) + scale (xyz); 0..9 stay reserved for MF_AOS_ArchSignal
LEGACY = {"Brick_Ruin_Door_Arch": M_ARCH, "Castle_Stairs": M_STAIRS}

# ---- §4.3 rooms (LOCAL cm from B; interior = clear air box x0,x1,y0,y1,z0,z1) -----------------------------------------
T = 100.0                       # wall / slab thickness
ROOMS = [  # id, path, interior, (W, D, H) spec, floor offset spec
    ("A03_R1", "/home/a03/lobby",    (-2500, -100, -1400, 1800,    0, 1350), (2400, 3200, 1350),    0),
    ("A03_R2", "/home/a03/capsules", (    0, 2000,     0, 2000,    0, 4500), (2000, 2000, 4500),    0),
    ("A03_R3", "/home/a03/rec",      (-1000, 3000,  2100, 4900,  900, 2250), (4000, 2800, 1350),  900),
    ("A03_R4", "/var/a03/canteen",   ( 2500, 4100, -1400, 1000,    0,  900), (2400, 1600,  900),    0),  # rotated 90°
    ("A03_R5", "/sys/a03/node",      ( 2100, 5300,  -400, 2000, 3600, 4500), (3200, 2400,  900), 3600),
    ("A03_R6", "/sys/a03/dispatch",  ( 3200, 5200,  2100, 3300, 3600, 4200), (2000, 1200,  600), 3600),
]
# Links (§4.3 graph). Each opening = an AIR box cut through the shared walls.
K1 = (0, 2400, -1400, -530, 0, 640)          # K-1 shell interior 870 x 640; ribs (30) leave 810 x 610 (spec 800 x 600 + tolerance)
DS = (2000, 2500, 340, 660, 0, 320)          # D-S 320 x 320 (spec 300 x 300 + tolerance) through R2 E wall + K01-5/storeroom gap + R4 W wall
SOMA_PIVOT = (-2910.0, 38.0, 650.0)          # exit frame face (+420) 10 cm proud of R1 west wall inner face (-2500)
AIRS = [
    ("SomaLock",  (-2600, -2500, -382, 458, 230, 1070)),      # 840² square inside the Ø1200 frame (covers bore Ø820)
    ("R1_R2_DM",  (-100, 0, 640, 1360, 0, 797.5)),            # arch ×1.75 clear 700 w, crown 787.5 (+10 tuck)
    ("R2_R5_DM",  (2000, 2100, 640, 1360, 3600, 4397.5)),
    ("R2_R3_DT",  (690, 1310, 2000, 2100, 917.5, 1487.5)),    # bulkhead ×(2.5, 6, 2.75) clear 600 x 550
    ("R5_R6_DT",  (3940, 4460, 2000, 2100, 3600, 4110)),      # 520 x 510 (spec 500 x 500 + tolerance), I-beam frame both faces
    ("R1_R4_K1",  (K1[0] - T, K1[1] + T) + K1[2:]),
    ("R2_R4_DS",  DS),
]

def shell(rid, b):
    x0, x1, y0, y1, z0, z1 = b
    return [(rid + "_Floor", "floor",   (x0 - T, x1 + T, y0 - T, y1 + T, z0 - T, z0)),
            (rid + "_Ceil",  "ceiling", (x0 - T, x1 + T, y0 - T, y1 + T, z1, z1 + T)),
            (rid + "_WallW", "wall",    (x0 - T, x0, y0 - T, y1 + T, z0, z1)),
            (rid + "_WallE", "wall",    (x1, x1 + T, y0 - T, y1 + T, z0, z1)),
            (rid + "_WallS", "wall",    (x0, x1, y0 - T, y0, z0, z1)),
            (rid + "_WallN", "wall",    (x0, x1, y1, y1 + T, z0, z1))]

def structure():
    s = []
    for rid, _, b, _, _ in ROOMS: s += shell(rid[4:], b)
    x0, x1, y0, y1, z0, z1 = K1
    s += [("K1_Floor", "floor", (x0, x1, y0 - T, y1 + T, z0 - T, z0)), ("K1_Ceil", "ceiling", (x0, x1, y0 - T, y1 + T, z1, z1 + T)),
          ("K1_WallS", "wall", (x0, x1, y0 - T, y0, z0, z1)), ("K1_WallN", "wall", (x0, x1, y1, y1 + T, z0, z1))]
    s += [("DS_Floor", "floor", (2100, 2400, 240, 760, -100, 0)), ("DS_Ceil", "ceiling", (2100, 2400, 240, 760, 320, 420)),
          ("DS_WallS", "wall", (2100, 2400, 240, 340, 0, 320)), ("DS_WallN", "wall", (2100, 2400, 660, 760, 0, 320))]
    return s

def air_boxes():
    return [b for _, _, b, _, _ in ROOMS] + [K1, DS] + [b for _, b in AIRS]

EPS = 0.5
def _ov(a, c): return all(a[2*i] < c[2*i+1] - EPS and c[2*i] < a[2*i+1] - EPS for i in range(3))
def _sub(a, c):
    if not _ov(a, c): return [a]
    b, out = list(a), []
    for i in range(3):                                    # x first, then y, then z: walls split into columns, sill/lintel
        if c[2*i] > b[2*i]:
            p = list(b); p[2*i+1] = c[2*i]; out.append(tuple(p)); b[2*i] = c[2*i]
        if c[2*i+1] < b[2*i+1]:
            p = list(b); p[2*i] = c[2*i+1]; out.append(tuple(p)); b[2*i+1] = c[2*i+1]
    return out

def pieces():
    """Structure minus air minus already-placed solids -> disjoint boxes (no coplanar duplicate faces)."""
    placed, res = [], []
    airs = air_boxes()
    for sid, role, box in structure():
        parts = [box]
        for c in airs + placed:
            parts = [q for p in parts for q in _sub(p, c)]
        parts = [p for p in parts if all(p[2*i+1] - p[2*i] >= 1.0 for i in range(3))]
        parts.sort(key=lambda p: (p[4], p[2], p[0]))
        for k, p in enumerate(parts):
            res.append(("SHELL_" + sid + "_%02d" % k, role, p))
        placed += parts
    return res

# ---- portals / frames (LOCAL AABB targets; rotation given as forward/up world axes) -----------------------------------
X, Y, Z, NX, NY = (1, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0), (0, -1, 0)
def portals():
    p = []  # id, mesh, fwd, up, aabb | or explicit transform, tags
    p.append(dict(id="PRT_SomaLock_Main", mesh=M_SOMA, explicit=(SOMA_PIVOT, 0.0, 1.0),
                  tags=["AOS_Link=Outside>A03_R1", "AOS_Opening=SM_Breach_SomaLock", "AOS_Class=C1",
                        "AOS_DeviceID=/dev/lock_a03_main", "AOS_LinkedRooms=Outside,A03_R1", "AOS_State=jammed"]))
    p.append(dict(id="PRT_R1_R2_DM_Arch", mesh=M_ARCH, fwd=X, up=Z, aabb=(-120, 20, 475, 1525, 0, 875),
                  tags=["AOS_Link=A03_R1>A03_R2", "AOS_Opening=D-M", "AOS_Class=C1+", "AOS_Note=broken glass screen of the atrium"]))
    p.append(dict(id="PRT_R2_R5_DM_Arch", mesh=M_ARCH, fwd=X, up=Z, aabb=(1980, 2120, 475, 1525, 3600, 4475),
                  tags=["AOS_Link=A03_R2>A03_R5", "AOS_Opening=D-M", "AOS_Class=C1+", "AOS_DeviceID=/dev/door_a03_25",
                        "AOS_LinkedRooms=A03_R2,A03_R5", "AOS_Locked=true", "AOS_AtriumFloor=9"]))
    p.append(dict(id="PRT_R2_R3_DT_Bulkhead", mesh=M_BULK, fwd=Y, up=Z, aabb=(340, 1660, 1988.75, 2111.25, 900, 1615),
                  tags=["AOS_Link=A03_R2>A03_R3", "AOS_Opening=D-T", "AOS_Class=C1", "AOS_AtriumFloor=3",
                        "AOS_DeviceID=/dev/door_a03_23", "AOS_LinkedRooms=A03_R2,A03_R3"]))
    dt56 = ["AOS_Link=A03_R5>A03_R6", "AOS_Opening=D-T", "AOS_Class=C1", "AOS_DeviceID=/dev/door_a03_56",
            "AOS_LinkedRooms=A03_R5,A03_R6"]
    for side, (ya, yb) in (("R5", (1970, 2000)), ("R6", (2100, 2130))):
        p.append(dict(id="PRT_R5_R6_DT_Jamb_%s_W" % side, mesh=M_BEAM, fwd=Z, up=Y, aabb=(3910, 3940, ya, yb, 3600, 4110), tags=dt56))
        p.append(dict(id="PRT_R5_R6_DT_Jamb_%s_E" % side, mesh=M_BEAM, fwd=Z, up=Y, aabb=(4460, 4490, ya, yb, 3600, 4110), tags=dt56))
        p.append(dict(id="PRT_R5_R6_DT_Head_%s" % side, mesh=M_BEAM, fwd=X, up=Z, aabb=(3910, 4490, ya, yb, 4110, 4140), tags=dt56))
    k1 = ["AOS_Link=A03_R1>A03_R4", "AOS_Opening=K-1", "AOS_Class=C2", "AOS_Note=service corridor 2400, rib per 1200 section"]
    for i, xc in enumerate((400, 1200, 2000)):
        p.append(dict(id="PRT_K1_Rib%d_JambS" % i, mesh=M_BEAM, fwd=Z, up=X, aabb=(xc - 15, xc + 15, -1400, -1370, 0, 610), tags=k1))
        p.append(dict(id="PRT_K1_Rib%d_JambN" % i, mesh=M_BEAM, fwd=Z, up=X, aabb=(xc - 15, xc + 15, -560, -530, 0, 610), tags=k1))
        p.append(dict(id="PRT_K1_Rib%d_Head" % i, mesh=M_BEAM, fwd=Y, up=Z, aabb=(xc - 15, xc + 15, -1400, -530, 610, 640), tags=k1))
    return p

# ---- helpers --------------------------------------------------------------------------------------------------------
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
EAL, MEL, ML = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary, unreal.MathLibrary
V = lambda t: unreal.Vector(*[float(c) for c in t])
def world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

def base():
    o = origin(); return tuple(o[i] + PLAN_OFFSET[i] for i in range(3))

def origin():
    for a in EAS.get_all_level_actors():
        if a.get_actor_label() == ANCHOR_LABEL:
            l = a.get_actor_location(); return (l.x, l.y, l.z)
    return ANCHOR_SPEC

def _axes(rot):
    r = lambda v: tuple(int(round(c)) for c in (v.x, v.y, v.z))
    return r(ML.get_forward_vector(rot)), r(ML.get_right_vector(rot)), r(ML.get_up_vector(rot))

def rot_for(fwd, up):
    for r, pch, yw in itertools.product((0.0, 90.0, 180.0, -90.0), repeat=3):
        rot = unreal.Rotator(roll=r, pitch=pch, yaw=yw)
        f, _, u = _axes(rot)
        if f == tuple(fwd) and u == tuple(up): return rot
    raise RuntimeError("no rotator for fwd %s up %s" % (fwd, up))

def fit(mesh, rot, tmin, tmax):
    """Axis-aligned rotation + per-local-axis scale + location so the mesh AABB equals [tmin, tmax] (world)."""
    bb = mesh.get_bounding_box(); bmin, bmax = (bb.min.x, bb.min.y, bb.min.z), (bb.max.x, bb.max.y, bb.max.z)
    ax = _axes(rot); scale, loc = [1.0] * 3, [0.0] * 3
    for i in range(3):
        w = max(range(3), key=lambda k: abs(ax[i][k])); sg = ax[i][w]
        scale[i] = (tmax[w] - tmin[w]) / (bmax[i] - bmin[i])
        loc[w] = tmin[w] - min(sg * scale[i] * bmin[i], sg * scale[i] * bmax[i])
    return loc, scale

def index(tag_prefix=TAG_ID):
    idx = {}
    for a in EAS.get_all_level_actors():
        for t in a.tags:
            t = str(t)
            if t.startswith(tag_prefix): idx.setdefault(t[len(tag_prefix):], []).append(a)
    return idx

def _mesh(p):
    m = EAL.load_asset(p)
    if not m: raise RuntimeError("Missing asset " + p)
    return m

def _arch_component(c):
    c.set_mobility(unreal.ComponentMobility.STATIC)
    c.set_collision_profile_name("BlockAll")          # §3.0.4: WorldStatic BlockAll, never BlockAllDynamic
    c.set_editor_property("cast_shadow", True)

# ---- assets: shell box mesh + box-mapped concrete material ------------------------------------------------------------
def _ensure_material():
    if EAL.does_asset_exist(MAT_BOX): return EAL.load_asset(MAT_BOX), False
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    m = AT.create_asset("M_AOS_Concrete_BoxMap", SHARED, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("used_with_nanite", True)
    E = lambda cls, x, y: MEL.create_material_expression(m, cls, x, y)
    lp = E(unreal.MaterialExpressionLocalPosition, -1600, -200)
    nw = E(unreal.MaterialExpressionVertexNormalWS, -1600, -100)     # pieces are unrotated: world normal == local normal
    tile = E(unreal.MaterialExpressionScalarParameter, -1600, 0)
    tile.set_editor_property("parameter_name", "TileCM"); tile.set_editor_property("default_value", TILE_CM)
    names = ["OffX", "OffY", "OffZ", "ScaleX", "ScaleY", "ScaleZ"]; cp = []
    for k, n in enumerate(names):
        s = E(unreal.MaterialExpressionScalarParameter, -1600, 100 + 80 * k)
        s.set_editor_property("parameter_name", n)
        s.set_editor_property("default_value", 1.0 if k >= 3 else 0.0)
        s.set_editor_property("use_custom_primitive_data", True)
        s.set_editor_property("primitive_data_index", CPD0 + k)
        cp.append(s)
    cu = E(unreal.MaterialExpressionCustom, -1200, 0)
    cu.set_editor_property("description", "AOS BoxMap UV (cluster-local cm)")
    cu.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    cu.set_editor_property("code",
        "float3 Q = float3(OX, OY, OZ) + P * float3(SX, SY, SZ);\n"
        "float3 n = abs(N);\n"
        "float2 uv = (n.x >= n.y && n.x >= n.z) ? float2(Q.y, -Q.z) : ((n.y >= n.z) ? float2(Q.x, -Q.z) : float2(Q.x, Q.y));\n"
        "return uv / max(Tile, 1.0);")
    pins = ["P", "N", "Tile", "OX", "OY", "OZ", "SX", "SY", "SZ"]
    ins = []
    for n in pins:
        ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
    cu.set_editor_property("inputs", ins)
    for src, pin in zip([lp, nw, tile] + cp, pins): MEL.connect_material_expressions(src, "", cu, pin)
    def tex(name, suffix, st, y):
        t = E(unreal.MaterialExpressionTextureSampleParameter2D, -800, y)
        t.set_editor_property("parameter_name", name)
        t.set_editor_property("texture", EAL.load_asset(MIS["wall"][1] + suffix))
        t.set_editor_property("sampler_type", st)
        MEL.connect_material_expressions(cu, "", t, "UVs")
        return t
    ST = unreal.MaterialSamplerType
    ta = tex("Albedo", "_D", ST.SAMPLERTYPE_VIRTUAL_COLOR, -300)
    tn = tex("Normal", "_N", ST.SAMPLERTYPE_VIRTUAL_NORMAL, 0)
    tr = tex("ARD", "_ORDp", ST.SAMPLERTYPE_VIRTUAL_MASKS, 300)
    tint = E(unreal.MaterialExpressionVectorParameter, -500, -450)
    tint.set_editor_property("parameter_name", "AlbedoTint"); tint.set_editor_property("default_value", unreal.LinearColor(1, 1, 1, 1))
    mul = E(unreal.MaterialExpressionMultiply, -300, -300)
    MEL.connect_material_expressions(ta, "RGB", mul, "A"); MEL.connect_material_expressions(tint, "", mul, "B")
    flat = E(unreal.MaterialExpressionConstant3Vector, -500, 120); flat.set_editor_property("constant", unreal.LinearColor(0, 0, 1, 0))
    ns = E(unreal.MaterialExpressionScalarParameter, -500, 200)       # tangent basis of the cube != box-map UVs: soften normal
    ns.set_editor_property("parameter_name", "NormalStrength"); ns.set_editor_property("default_value", 0.6)
    lerp = E(unreal.MaterialExpressionLinearInterpolate, -300, 50)
    MEL.connect_material_expressions(flat, "", lerp, "A"); MEL.connect_material_expressions(tn, "RGB", lerp, "B")
    MEL.connect_material_expressions(ns, "", lerp, "Alpha")
    MP = unreal.MaterialProperty
    MEL.connect_material_property(mul, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(lerp, "", MP.MP_NORMAL)
    MEL.connect_material_property(tr, "G", MP.MP_ROUGHNESS)
    MEL.connect_material_property(tr, "R", MP.MP_AMBIENT_OCCLUSION)
    MEL.recompile_material(m)
    EAL.save_asset(MAT_BOX, only_if_is_dirty=False)
    return m, True

def _ensure_mi(role, parent):
    name, base = MIS[role]; path = SHARED + "/" + name
    mi = EAL.load_asset(path) if EAL.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, SHARED, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    for p, sfx in (("Albedo", "_D"), ("Normal", "_N"), ("ARD", "_ORDp")):
        MEL.set_material_instance_texture_parameter_value(mi, p, EAL.load_asset(base + sfx))
    MEL.set_material_instance_scalar_parameter_value(mi, "TileCM", TILE_CM)
    MEL.update_material_instance(mi)
    EAL.save_asset(path, only_if_is_dirty=False)
    return mi

def assets():
    rep = {}
    mat, created = _ensure_material(); rep["material"] = dict(path=MAT_BOX, created=created)
    try: rep["material"]["ps_instructions"] = MEL.get_statistics(mat).num_pixel_shader_instructions
    except Exception as e: rep["material"]["stats_err"] = str(e)[:80]
    mis = {r: _ensure_mi(r, mat) for r in MIS}
    if not EAL.does_asset_exist(M_BOX):
        EAL.duplicate_asset(M_BOX_SRC, M_BOX); rep["shellbox_created"] = True
    sm = EAL.load_asset(M_BOX)
    bs = sm.get_editor_property("body_setup"); bs.modify()
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    ns = sm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", True)
    ns.set_editor_property("fallback_relative_error", 1.0)
    try: unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(sm, ns, True)
    except Exception: sm.set_editor_property("nanite_settings", ns)
    sm.set_material(0, mis["wall"])
    EAL.set_metadata_tag(sm, "AOS_Kit", "ClusterShell")
    EAL.save_asset(M_BOX, only_if_is_dirty=False)
    rep["shellbox"] = dict(path=M_BOX, nanite=bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")),
                           convex=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_convex_collision_count(sm))
    rep["mis"] = sorted(MIS[r][0] for r in MIS)
    return rep

# ---- legacy swap -------------------------------------------------------------------------------------------------------
def _profile(a, o, e, axis):
    w, prof = world(), []
    for t in (-0.6, 0.6):
        x = o.x + (t * e.x if axis == 0 else 0.0); y = o.y + (t * e.y if axis == 1 else 0.0)
        hs = unreal.SystemLibrary.line_trace_multi(w, V((x, y, o.z + e.z + 30)), V((x, y, o.z - e.z - 30)),
                                                   unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE, True)
        z = None
        for h in hs or []:
            tt = h.to_tuple()
            if tt[9] == a: z = tt[4].z; break
        prof.append(z)
    return prof

def swap():
    done, already = [], []
    with unreal.ScopedEditorTransaction("AOS C01 legacy swap"):
        for a in EAS.get_all_level_actors():
            if not isinstance(a, unreal.StaticMeshActor): continue
            c = a.static_mesh_component; m = c.static_mesh
            if any(str(t).startswith("AOS_LegacyMesh=") for t in a.tags): already.append(a.get_actor_label()); continue
            if not m: continue
            key = next((k for k in LEGACY if k in m.get_path_name()), None)
            if not key: continue
            new = _mesh(LEGACY[key]); rot0 = a.get_actor_rotation(); f0, r0, u0 = _axes(rot0)
            o, e = a.get_actor_bounds(False)
            if key == "Castle_Stairs":                       # rise direction from top-down traces on the old flight
                best = None
                for ax in (0, 1):
                    p = _profile(a, o, e, ax)
                    if None in p: continue
                    d = p[1] - p[0]
                    if best is None or abs(d) > abs(best[1]): best = (ax, d)
                fwd = [0, 0, 0]; fwd[best[0]] = 1 if best[1] > 0 else -1; up = (0, 0, 1)
                note = "rise %+.0f cm along %s%s" % (best[1], "+" if best[1] > 0 else "-", "XY"[best[0]])
            else:                                             # arch: width = old X, height = old Z, thickness = old Y
                fwd = tuple(-c_ for c_ in r0); up = u0; note = "width<-old X, height<-old Z"
            rot = rot_for(tuple(fwd), tuple(up))
            loc, sc = fit(new, rot, (o.x - e.x, o.y - e.y, o.z - e.z), (o.x + e.x, o.y + e.y, o.z + e.z))
            l0, s0 = a.get_actor_location(), a.get_actor_scale3d()
            a.modify()
            a.set_editor_property("tags", list(a.tags) + [unreal.Name("AOS_LegacyMesh=" + m.get_path_name()),
                                  unreal.Name("AOS_LegacyXform=%.2f,%.2f,%.2f|%.4f,%.4f,%.4f|%.4f,%.4f,%.4f" % (
                                      l0.x, l0.y, l0.z, rot0.roll, rot0.pitch, rot0.yaw, s0.x, s0.y, s0.z))])
            c.set_static_mesh(new)
            c.set_editor_property("override_materials", [])
            c.set_collision_profile_name("BlockAll")
            a.set_actor_location_and_rotation(V(loc), rot, False, True)
            a.set_actor_scale3d(V(sc))
            old_label = a.get_actor_label()
            a.set_actor_label(new.get_name() + "__" + old_label)
            o2, e2 = a.get_actor_bounds(False)
            done.append(dict(actor=old_label, old=m.get_name(), new=new.get_name(), folder=str(a.get_folder_path()), note=note,
                             rot=[round(rot.roll), round(rot.pitch), round(rot.yaw)], scale=[round(s, 4) for s in sc],
                             aabb_err_cm=round(max(abs(o2.x - o.x), abs(o2.y - o.y), abs(o2.z - o.z),
                                                   abs(e2.x - e.x), abs(e2.y - e.y), abs(e2.z - e.z)), 2)))
    remaining = [a.get_actor_label() for a in EAS.get_all_level_actors()
                 for cc in a.get_components_by_class(unreal.StaticMeshComponent)
                 if cc.static_mesh and any(k in cc.static_mesh.get_path_name() for k in LEGACY)]
    return dict(swapped=done, already_swapped=already, legacy_remaining=remaining)

# ---- build ---------------------------------------------------------------------------------------------------------------
def spec():
    B = base(); W = lambda p: tuple(p[i] + B[i] for i in range(3))
    s = []
    box = _mesh(M_BOX); rot0 = unreal.Rotator(0, 0, 0)
    for pid, role, p in pieces():
        loc, sc = fit(box, rot0, W((p[0], p[2], p[4])), W((p[1], p[3], p[5])))
        s.append(dict(id=pid, kind="shell", role=role, folder=F_ROOMS, mesh=M_BOX, loc=loc, rot=rot0, scale=sc,
                      cpd=[p[0], p[2], p[4]] + sc, tags=["AOS_Role=" + role]))
    for e in portals():
        mesh = _mesh(e["mesh"])
        if "explicit" in e:
            (pl, yaw, us) = e["explicit"]; loc, rot, sc = list(W(pl)), unreal.Rotator(0, 0, yaw), [us] * 3
        else:
            rot = rot_for(e["fwd"], e["up"]); a = e["aabb"]
            loc, sc = fit(mesh, rot, W((a[0], a[2], a[4])), W((a[1], a[3], a[5])))
        s.append(dict(id=e["id"], kind="portal", folder=F_PORTALS, mesh=e["mesh"], loc=loc, rot=rot, scale=sc, tags=e["tags"]))
    for rid, path, b, _, _ in ROOMS:
        c = W(((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2))
        s.append(dict(id="VOL_" + rid, kind="volume", folder=F_VOLS, loc=list(c), rot=rot0, scale=[1, 1, 1],
                      extent=((b[1] - b[0]) / 2, (b[3] - b[2]) / 2, (b[5] - b[4]) / 2),
                      tags=["AOS_RoomVolume", "AOS_RoomID=" + rid, "AOS_DirectoryPath=" + path, "AOS_Cluster=C-01"]))
    return s

def _spawn(e):
    if e["kind"] == "volume":
        a = EAS.spawn_actor_from_class(unreal.TriggerBox, V(e["loc"]), e["rot"])
    else:
        a = EAS.spawn_actor_from_object(_mesh(e["mesh"]), V(e["loc"]), e["rot"])
    return a

def _reconcile(a, e, mis):
    a.modify()
    a.set_editor_property("tags", [unreal.Name(TAG_ALL), unreal.Name(TAG_ID + e["id"])] + [unreal.Name(t) for t in e["tags"]])
    a.set_actor_label(e["id"]); a.set_folder_path(e["folder"])
    a.set_actor_location_and_rotation(V(e["loc"]), e["rot"], False, True)
    a.set_actor_scale3d(V(e["scale"]))
    if e["kind"] == "volume":
        bc = a.get_component_by_class(unreal.BoxComponent)
        bc.set_box_extent(V(e["extent"]), False)
        return
    c = a.static_mesh_component
    m = _mesh(e["mesh"])
    if c.static_mesh != m: c.set_static_mesh(m)
    _arch_component(c)
    if e["kind"] == "shell":
        c.set_material(0, mis[e["role"]])
        for k, v in enumerate(e["cpd"]): c.set_default_custom_primitive_data_float(CPD0 + k, float(v))

def build():
    w = world()
    if not w.get_path_name().startswith(LEVEL): raise RuntimeError("Active level is %s, expected %s" % (w.get_path_name(), LEVEL))
    mis = {r: _mesh(SHARED + "/" + MIS[r][0]) for r in MIS}
    sp = spec(); ids = set(e["id"] for e in sp); idx = index()
    spawned, updated, removed, dupes = 0, 0, [], []
    with unreal.ScopedEditorTransaction("AOS C01 /home/a03 build"):
        for k, acts in list(idx.items()):
            if k not in ids or len(acts) > 1:
                for a in (acts if k not in ids else acts[1:]):
                    if TAG_ALL in [str(t) for t in a.tags]: removed.append(k); EAS.destroy_actor(a)
        idx = index()
        for e in sp:
            found = idx.get(e["id"], [])
            a = found[0] if found else _spawn(e)
            if found: updated += 1
            else: spawned += 1
            _reconcile(a, e, mis)
    kinds = {}
    for e in sp: kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    return dict(origin_B=origin(), spawned=spawned, reconciled=updated, removed_stale=removed, counts=kinds)

# ---- verify -------------------------------------------------------------------------------------------------------------
SHELL_HALF = (200.0, 100.0, 100.0)      # Shell-1 box 400 x 200 x 200 (§3.0.1)
R_C1 = 245.0                            # half-diagonal sphere, any orientation
ROUTE = [  # LOCAL waypoints: outside -> SomaLock -> R1 -> R2 (rise to floor 9) -> R5 -> R6
    ("Outside", (-4110, 200, 650)), ("R1", (-1300, 200, 650)), ("R1", (-1300, 1000, 300)), ("R2", (1000, 1000, 300)),
    ("R2_floor9", (1000, 1000, 3850)), ("R5", (4200, 1000, 3850)), ("R6", (4200, 2700, 3850))]
EXTRA = [  # other links, same Shell-1 box
    ("R1>R4 K-1 corridor (C2)", (-1300, -965, 305), (3300, -965, 305)),
    ("R2>R3 D-T atrium floor 3 (C1)", (1000, 1000, 1202.5), (1000, 3500, 1202.5)),
    ("R2>R4 D-S secret (C0, Shell straight)", (1000, 500, 160), (3300, 500, 160)),
]
CONTROLS = [  # expect HIT
    ("sphere R256 through SomaLock lens", "sph", (-4110, 200, 650), (-1300, 200, 650), 256.0),
    ("box R1>R2 offset into arch pier (y 1500)", "box", (-1300, 1500, 300), (1000, 1500, 300), None),
    ("box R1>R2 through solid wall (y 200, z 300)", "box", (-1300, 200, 300), (1000, 200, 300), None),
    ("box R5>R6 above D-T lintel (z 4050)", "box", (4200, 1000, 4050), (4200, 2700, 4050), None),
    ("box K-1 offset into rib jamb (y -1280)", "box", (-1300, -1280, 300), (3300, -1280, 300), None),
]
OT = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1]          # WorldStatic (Bible 3.0.1: sweep on WorldStatic)
# Object queries hit every WorldStatic object regardless of response. The ocean's query volumes (WaterBodyCollision,
# Overlap for Pawn) enclose the whole cluster, so they are always excluded: they are water, not architecture.
# Two tiers: "cluster" also excludes legacy pre-Bible level bounds (LEGACY_BOUNDS) and judges the cluster's own build;
# "context" keeps them and reports what the current level would still block.
LEGACY_BOUNDS = ("TowerA_Wall", "Map_Border")
IGN_W, IGN_C = [], []
def _ignore():
    del IGN_W[:]; del IGN_C[:]
    for a in EAS.get_all_level_actors():
        cn = a.get_class().get_name()
        if cn.startswith("WaterBody") or cn == "WaterZone": IGN_W.append(a); IGN_C.append(a)
        elif a.get_actor_label() in LEGACY_BOUNDS: IGN_C.append(a)
    return dict(always=sorted(a.get_actor_label() for a in IGN_W),
                cluster_tier_only=sorted(a.get_actor_label() for a in IGN_C if a not in IGN_W))

def _h(r, B):
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    if not t[0]: return None
    a = t[9]
    return dict(actor=a.get_actor_label() if a else None, at=[round(t[4].x - B[0]), round(t[4].y - B[1]), round(t[4].z - B[2])],
                start_penetrating=bool(t[1]))

def _sweep(kind, p0, p1, B, r=None, ign=None):
    w, SL, NONE = world(), unreal.SystemLibrary, unreal.DrawDebugTrace.NONE
    ign = IGN_C if ign is None else ign
    a, b = V([p0[i] + B[i] for i in range(3)]), V([p1[i] + B[i] for i in range(3)])
    d = (p1[0] - p0[0], p1[1] - p0[1]); yaw = math.degrees(math.atan2(d[1], d[0])) if abs(d[0]) + abs(d[1]) > 1 else 0.0
    if kind == "box":
        return _h(SL.box_trace_single_for_objects(w, a, b, V(SHELL_HALF), unreal.Rotator(0, 0, yaw), OT, False, ign, NONE, True), B)
    return _h(SL.sphere_trace_single_for_objects(w, a, b, r or R_C1, OT, False, ign, NONE, True), B)

def _line_free(B, p, q):
    w = world()
    r = unreal.SystemLibrary.line_trace_single_for_objects(w, V([p[i] + B[i] for i in range(3)]), V([q[i] + B[i] for i in range(3)]),
                                                         OT, False, IGN_C, unreal.DrawDebugTrace.NONE, True)
    return _h(r, B) is None

def _clear(B, c, pas, u, v, depth, reach=800.0, step=10.0):
    """Clear section through a portal: largest offsets along +-u / +-v at which a line PARALLEL to the passage axis
    (c +- depth) stays free (binary search, 0.5 cm). Measures the true envelope across frame + wall depth."""
    out = []
    for ax in (u, v):
        span = 0.0
        for sg in (-1, 1):
            def free(d):
                p = list(c); p[ax] += sg * d; q = list(p); p[pas] -= depth; q[pas] += depth
                return _line_free(B, p, q)
            if not free(0.0): return "centre blocked"
            lo, hi = 0.0, None
            d = step
            while d <= reach:
                if not free(d): hi = d; break
                lo = d; d += step
            if hi is None: span += reach; continue
            while hi - lo > 0.5:
                mid = (lo + hi) / 2
                if free(mid): lo = mid
                else: hi = mid
            span += lo
        out.append(round(span))
    return out

PORTALS_MEASURE = [  # name, centre (local), passage axis, section axes (u = width, v = height), half-depth, spec (W, H)
    ("D-M R1>R2", (-50, 1000, 300), 0, 1, 2, 120, (600, 600)),
    ("D-M R2>R5", (2050, 1000, 3900), 0, 1, 2, 120, (600, 600)),
    ("D-T R2>R3", (1000, 2050, 1202.5), 1, 0, 2, 120, (500, 500)),
    ("D-T R5>R6", (4200, 2050, 3855), 1, 0, 2, 120, (500, 500)),
    ("K-1 R1>R4 (rib section)", (1200, -965, 305), 0, 1, 2, 60, (800, 600)),
    ("D-S R2>R4", (2250, 500, 160), 0, 1, 2, 260, (300, 300)),
]

def verify():
    O = origin(); B = base()
    rep = {"origin_B": [round(c) for c in O], "anchor_matches_spec": all(abs(O[i] - ANCHOR_SPEC[i]) < 0.01 for i in range(3)),
           "plan_offset": list(PLAN_OFFSET), "note": "all *_local coordinates below are relative to B + plan_offset"}
    rep["sweep_ignored_actors"] = _ignore()
    route = []
    for (n0, p0), (n1, p1) in zip(ROUTE, ROUTE[1:]):
        route.append(dict(leg="%s>%s" % (n0, n1), box_400x200x200=_sweep("box", p0, p1, B), sphere_R245=_sweep("sph", p0, p1, B),
                          context_box=_sweep("box", p0, p1, B, ign=IGN_W)))
    rep["route_SomaLock_R1_R2_R5_R6"] = route
    rep["extra_links"] = [dict(leg=n, box_400x200x200=_sweep("box", p0, p1, B), context_box=_sweep("box", p0, p1, B, ign=IGN_W))
                          for n, p0, p1 in EXTRA]
    rep["controls_expect_hit"] = [dict(name=n, hit=_sweep(k, p0, p1, B, r)) for n, k, p0, p1, r in CONTROLS]
    idx = index(); sl = idx.get("PRT_SomaLock_Main", [None])[0]
    if sl:
        c = sl.static_mesh_component
        ni, no = c.get_socket_location("SOCKET_Nav_In"), c.get_socket_location("SOCKET_Nav_Out")
        loc = lambda v: (v.x - B[0], v.y - B[1], v.z - B[2])
        rep["somalock_nav_sockets_local"] = [[round(x) for x in loc(ni)], [round(x) for x in loc(no)]]
        rep["somalock_socket_sweep_box"] = _sweep("box", loc(ni), loc(no), B)
        rep["somalock_socket_sweep_sphere_R245"] = _sweep("sph", loc(ni), loc(no), B)
    rep["clear_sections_cm"] = {n: dict(measured_WxH=_clear(B, c, pas, u, v, dp), spec_WxH=list(s)) for n, c, pas, u, v, dp, s in PORTALS_MEASURE}
    rows, fails, warns = [], [], []
    w = world()
    for rid, path, b, whd, fz in ROOMS:
        dims = sorted([b[1] - b[0], b[3] - b[2]]); ok = dims == sorted(whd[:2]) and b[5] - b[4] == whd[2] and b[4] == fz
        v = idx.get("VOL_" + rid, [None])[0]
        tags = [str(t) for t in v.tags] if v else []
        okv = v is not None and ("AOS_RoomID=" + rid) in tags and ("AOS_DirectoryPath=" + path) in tags
        if okv:
            ext = v.get_component_by_class(unreal.BoxComponent).get_unscaled_box_extent()
            okv = abs(ext.x * 2 - (b[1] - b[0])) < 0.5 and abs(ext.y * 2 - (b[3] - b[2])) < 0.5 and abs(ext.z * 2 - (b[5] - b[4])) < 0.5
        cen = V(((b[0] + b[1]) / 2 + B[0], (b[2] + b[3]) / 2 + B[1], (b[4] + b[5]) / 2 + B[2]))
        ov = unreal.SystemLibrary.box_overlap_actors(w, cen, V(((b[1] - b[0]) / 2 - 5, (b[3] - b[2]) / 2 - 5, (b[5] - b[4]) / 2 - 5)), OT, None, IGN_W)
        ov = ov[1] if isinstance(ov, tuple) else ov
        foreign = sorted(set(a.get_actor_label() for a in (ov or []) if TAG_ALL not in [str(t) for t in a.tags]))
        rows.append(dict(room=rid, path=path, interior="%d x %d x %d" % (b[1] - b[0], b[3] - b[2], b[5] - b[4]), floor="B+%d" % b[4],
                         spec_ok=ok, volume_ok=okv, foreign_static_in_room=foreign))
        if not (ok and okv): fails.append(rid)
        if foreign: warns.append("%s intruded by %s" % (rid, foreign))
    rep["rooms"] = rows
    clash = {}                                            # every generated mesh actor vs non-cluster WorldStatic geometry
    for a in EAS.get_all_level_actors():
        if TAG_ALL not in [str(t) for t in a.tags] or isinstance(a, unreal.TriggerBox): continue
        o, e = a.get_actor_bounds(False)
        ov = unreal.SystemLibrary.box_overlap_actors(w, o, V((max(e.x - 1, 0.5), max(e.y - 1, 0.5), max(e.z - 1, 0.5))), OT, None, IGN_W)
        ov = ov[1] if isinstance(ov, tuple) else ov
        f = sorted(set(x.get_actor_label() for x in (ov or []) if TAG_ALL not in [str(t) for t in x.tags]))
        if f: clash[a.get_actor_label()] = f
    rep["cluster_vs_foreign_static"] = clash
    if clash: warns.append("%d cluster actors touch foreign static geometry" % len(clash))
    folders = {}
    for a in EAS.get_all_level_actors():
        if TAG_ALL in [str(t) for t in a.tags]:
            f = str(a.get_folder_path()); folders[f] = folders.get(f, 0) + 1
    rep["folders"] = folders
    if set(folders) != {F_ROOMS, F_PORTALS, F_VOLS}: fails.append("folders %s" % sorted(folders))
    dup = [k for k, v in idx.items() if len(v) > 1]
    if dup: fails.append("duplicate ids %s" % dup)
    for leg in route:
        if leg["box_400x200x200"] or leg["sphere_R245"]: fails.append("route " + leg["leg"])
        if leg["context_box"]: warns.append("context: route %s blocked by %s" % (leg["leg"], leg["context_box"]["actor"]))
    for x in rep["extra_links"]:
        if x["box_400x200x200"]: fails.append("extra " + x["leg"])
        if x["context_box"]: warns.append("context: %s blocked by %s" % (x["leg"], x["context_box"]["actor"]))
    for x in rep["controls_expect_hit"]:
        if not x["hit"]: fails.append("control missed " + x["name"])
    if sl and (rep["somalock_socket_sweep_box"] or rep["somalock_socket_sweep_sphere_R245"]): fails.append("SomaLock socket sweep")
    for n, d in rep["clear_sections_cm"].items():
        m = d["measured_WxH"]
        if not isinstance(m, list) or m[0] < d["spec_WxH"][0] - 0.5 or m[1] < d["spec_WxH"][1] - 0.5: fails.append("clear section " + n)
    rep["legacy_remaining"] = [a.get_actor_label() for a in EAS.get_all_level_actors()
                               for cc in a.get_components_by_class(unreal.StaticMeshComponent)
                               if cc.static_mesh and any(k in cc.static_mesh.get_path_name() for k in LEGACY)]
    if rep["legacy_remaining"]: fails.append("legacy meshes remain")
    rep["fails"] = fails; rep["warnings"] = warns; rep["PASS"] = not fails; rep["context_clear"] = not warns
    return rep

def save():
    U = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_name() for p in U.get_dirty_map_packages()]
    ok = U.save_dirty_packages(True, True)
    return dict(saved=ok, map_packages=len(dirty))

if MODE == "assets": result = assets()
elif MODE == "swap": result = swap()
elif MODE == "build": result = build()
elif MODE == "verify": result = verify()
elif MODE == "save": result = save()
else:
    result = dict(assets=assets(), swap=swap(), build=build())
    result["verify"] = verify()
    result["save"] = save()
