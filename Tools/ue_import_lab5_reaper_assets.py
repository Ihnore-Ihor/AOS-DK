# AOS-DK | Lab 5 | SK_OOMReaper + SM_WPN_SigkillPike | UE 5.7.4 import + socket authoring + verification (run via execute_python)
# Reads Tools/SK_OOMReaper_rig.json and Tools/SM_WPN_SigkillPike_spec.json written by the two max_build_*.py scripts.
# FBX sources: Content/AOS_DK_Game/Enemies/Reaper/*.fbx   ->  UE assets: /Game/AOS_DK_Game/Enemies/Reaper/Meshes
# UE 5.7 routes FBX through Interchange, which ignores FbxImportUI and drops UCX_ hulls -> the legacy FBX importer is forced
#   (Interchange.FeatureFlags.Import.FBX 0) for the duration of each import task and the cvar is restored afterwards.
# Max RH -> UE LH: (x, y, z) -> (x, -y, z).  Re-runnable (replace_existing, sockets re-authored).
# MODE: "import" | "verify" | "all".
# Run: g={"LAB5_MODE":"all"}; exec(open(<proj>/Tools/ue_import_lab5_reaper_assets.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math
MODE = globals().get("LAB5_MODE", "all")
DST = "/Game/AOS_DK_Game/Enemies/Reaper/Meshes"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX_DIR = os.path.join(PROJ, "Content/AOS_DK_Game/Enemies/Reaper")
SK_NAME, SM_NAME = "SK_OOMReaper", "SM_WPN_SigkillPike"
RIG = json.load(open(os.path.join(PROJ, "Tools/SK_OOMReaper_rig.json"), encoding="utf-8"))
SPEC = json.load(open(os.path.join(PROJ, "Tools/SM_WPN_SigkillPike_spec.json"), encoding="utf-8"))
ue = lambda v: unreal.Vector(v[0], -v[1], v[2])
EAL = unreal.EditorAssetLibrary
CV = "Interchange.FeatureFlags.Import.FBX"

def _legacy_import(task):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    prev = unreal.SystemLibrary.get_console_variable_bool_value(CV)
    unreal.SystemLibrary.execute_console_command(world, CV + " 0")
    try:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    finally:
        unreal.SystemLibrary.execute_console_command(world, CV + (" 1" if prev else " 0"))
    return list(task.imported_object_paths), prev

# ------------------------------------------------------------------ SK_OOMReaper
def import_skeletal():
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = True
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False
    o.set_editor_property("create_physics_asset", True)
    sd = o.skeletal_mesh_import_data
    sd.set_editor_property("use_t0_as_ref_pose", False)
    sd.set_editor_property("import_morph_targets", False)
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = os.path.join(FBX_DIR, SK_NAME + ".fbx"), DST, SK_NAME
    t.automated, t.replace_existing, t.save, t.options = True, True, False, o
    paths, prev = _legacy_import(t)
    # spec naming: SKEL_OOMReaper / PA_OOMReaper
    for old, new in ((SK_NAME + "_Skeleton", "SKEL_OOMReaper"), (SK_NAME + "_PhysicsAsset", "PA_OOMReaper")):
        if EAL.does_asset_exist(DST + "/" + old) and not EAL.does_asset_exist(DST + "/" + new):
            EAL.rename_asset(DST + "/" + old, DST + "/" + new)
    return paths, prev

def author_skel_sockets():
    skm = unreal.load_asset(DST + "/" + SK_NAME)
    pose = unreal.AnimPoseExtensions.get_reference_pose(skm.get_editor_property("skeleton"))
    skm.modify()
    for name, sd in RIG["sockets"].items():
        s = skm.find_socket(name)
        if s is None:
            if skm.find_socket("Socket") is None:
                skm.add_socket(unreal.new_object(unreal.SkeletalMeshSocket, outer=skm), False)
            skm.rename_socket("Socket", name); s = skm.find_socket(name)
        bone_w = unreal.AnimPoseExtensions.get_bone_pose(pose, sd["bone"], unreal.AnimPoseSpaces.WORLD)
        sock_w = unreal.Transform(ue(sd["pos"]), unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])), unreal.Vector(1, 1, 1))
        s.set_socket_parent(skm, sd["bone"])
        s.set_socket_local_transform(sock_w.make_relative(bone_w))
    EAL.save_asset(DST + "/" + SK_NAME, only_if_is_dirty=False)
    return sorted(str(skm.get_socket_by_index(i).socket_name) for i in range(skm.num_sockets()))

# ------------------------------------------------------------------ SM_WPN_SigkillPike
def import_static():
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False
    sd = o.static_mesh_import_data
    sd.set_editor_property("combine_meshes", True)
    sd.set_editor_property("auto_generate_collision", False)      # UCX only
    sd.set_editor_property("one_convex_hull_per_ucx", True)       # each UCX_ -> exactly one convex element
    sd.set_editor_property("generate_lightmap_u_vs", False)
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = os.path.join(FBX_DIR, SM_NAME + ".fbx"), DST, SM_NAME
    t.automated, t.replace_existing, t.save, t.options = True, True, False, o
    return _legacy_import(t)

def author_static(sm):
    sm.modify()
    for name in SPEC["sockets"]:
        old = sm.find_socket(name)
        if old: sm.remove_socket(old)
    for name, sd in SPEC["sockets"].items():
        s = unreal.StaticMeshSocket(sm)
        s.set_editor_property("socket_name", name)
        s.set_editor_property("relative_location", ue(sd["pos"]))
        s.set_editor_property("relative_rotation", unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])))
        sm.add_socket(s)
    bs = sm.get_editor_property("body_setup")
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)   # spec 2.2.4
    ns = sm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", False)             # spec 2.2.2: Nanite off
    sm.set_editor_property("nanite_settings", ns)
    EAL.save_asset(DST + "/" + SM_NAME, only_if_is_dirty=False)

# ------------------------------------------------------------------ verification
def bone_names_of(skm):
    skel = skm.get_editor_property("skeleton")
    try:   # preferred: reference skeleton via the skeleton asset's bone tree
        return [str(b.get_editor_property("name")) for b in skel.get_editor_property("bone_tree")], "bone_tree"
    except Exception:
        pass
    try:
        return [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(unreal.AnimPoseExtensions.get_reference_pose(skel))], "pose"
    except Exception as ex:
        return None, repr(ex)

def verify():
    rep = {}
    skm = unreal.load_asset(DST + "/" + SK_NAME)
    names, how = bone_names_of(skm)
    exp = [b["name"] for b in RIG["bones"]]
    bb = skm.get_bounds()
    rep["SK"] = {
        "asset": skm.get_path_name(), "skeleton": skm.get_editor_property("skeleton").get_path_name(),
        "bone_source": how, "bone_count": None if names is None else len(names), "bones_expected": len(exp),
        "missing_bones": None if names is None else sorted(set(exp) - set(names)),
        "extra_bones": None if names is None else sorted(set(names) - set(exp)),
        "sockets": sorted(str(skm.get_socket_by_index(i).socket_name) for i in range(skm.num_sockets())),
        "sockets_expected": sorted(RIG["sockets"]),
        "bounds_size_cm": [round(c * 2, 1) for c in bb.box_extent.to_tuple()],
        "materials": [str(m.get_editor_property("material_slot_name")) for m in skm.get_editor_property("materials")],
        "physics_asset": str(skm.get_editor_property("physics_asset")),
        "lods": skm.get_num_lods() if hasattr(skm, "get_num_lods") else None,
    }
    sm = unreal.load_asset(DST + "/" + SM_NAME)
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    bs = sm.get_editor_property("body_setup"); ag = bs.get_editor_property("agg_geom")
    cx = ag.get_editor_property("convex_elems")
    cx_verts = []
    for c in cx:
        try: cx_verts.append(len(c.get_editor_property("vertex_data")))
        except Exception: cx_verts.append(None)
    sb = sm.get_bounding_box()
    socks = sorted(n for n in SPEC["sockets"] if sm.find_socket(n))      # StaticMesh.sockets is protected in Python
    try: n_socks = sm.get_num_sockets()
    except Exception: n_socks = None
    rep["SM"] = {
        "asset": sm.get_path_name(), "lods": sm.get_num_lods(), "verts_lod0": sub.get_number_verts(sm, 0),
        "bounds_size_cm": [round(sb.max.x - sb.min.x, 2), round(sb.max.y - sb.min.y, 2), round(sb.max.z - sb.min.z, 2)],
        "convex_count": sub.get_convex_collision_count(sm), "convex_elems": len(cx), "convex_vertex_counts": cx_verts,
        "collision_trace_flag": str(bs.get_editor_property("collision_trace_flag")),
        "nanite": bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")),
        "sockets": socks, "sockets_total": n_socks, "sockets_expected": sorted(SPEC["sockets"]),
        "socket_locs": {n: [round(c, 2) for c in sm.find_socket(n).get_editor_property("relative_location").to_tuple()] for n in socks},
        "materials": [str(m.get_editor_property("material_slot_name")) for m in sm.get_editor_property("static_materials")],
    }
    return rep

out = {}
if MODE in ("import", "all"):
    EAL.make_directory(DST)
    out["sk_imported"], out["interchange_fbx_prev"] = import_skeletal()
    out["sk_sockets"] = author_skel_sockets()
    out["sm_imported"], _ = import_static()
    author_static(unreal.load_asset(DST + "/" + SM_NAME))
    out["interchange_fbx_now"] = unreal.SystemLibrary.get_console_variable_bool_value(CV)
if MODE in ("verify", "all"):
    out["verify"] = verify()
result = out
