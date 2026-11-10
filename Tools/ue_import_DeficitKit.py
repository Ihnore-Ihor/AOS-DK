# AOS-DK | Deficit Kit | UE 5.7.4 import + materials + sockets + collision/Nanite authoring + verification
# Reads Tools/DeficitKit_spec.json written by max_build_DeficitKit.py. Max RH -> UE LH: (x, y, z) -> (x, -y, z).
# MODE: "import" = import + author; "verify" = checks + line-trace probes; "all" = both. ONLY = optional asset subset.
# Run: g={"DK_MODE":"all"}; exec(open(<proj>/Tools/ue_import_DeficitKit.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os
MODE = globals().get("DK_MODE", "all")
ONLY = globals().get("DK_ONLY", None)
DST = "/Game/AOS_DK_Game/Environment/ModularKit"
MAT_DIR = DST + "/Materials"
PARENT = "/Game/AOS_DK_Game/Environment/CustomHero/Materials/M_AOS_HeroSurface"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX_DIR = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/ModularKit")
SPEC = json.load(open(os.path.join(PROJ, "Tools/DeficitKit_spec.json"), encoding="utf-8"))
NAMES = [n for n in SPEC["assets"] if (ONLY is None or n in ONLY)]
ue = lambda v: unreal.Vector(v[0], -v[1], v[2])
EAL = unreal.EditorAssetLibrary

# slot -> (MI name, base colour (linear), metallic, roughness, emissive colour, emissive intensity) | (path, None) = reuse
MATS = {
    "MS_PipePaint":   ("MI_Kit_PipePaint", (0.030, 0.105, 0.095), 0.20, 0.50, (0, 0, 0), 0.0),
    "MS_DarkSteel":   ("MI_Kit_DarkSteel", (0.022, 0.025, 0.028), 0.60, 0.45, (0, 0, 0), 0.0),
    "MS_Galvanized":  ("MI_Kit_Galvanized", (0.300, 0.310, 0.320), 1.00, 0.40, (0, 0, 0), 0.0),
    "MS_SafetyPaint": ("MI_Kit_SafetyPaint", (0.720, 0.350, 0.007), 0.10, 0.55, (0, 0, 0), 0.0),
    "MS_Status":      ("MI_Kit_Status", (0.0, 0.0, 0.0), 0.0, 0.40, (0.26, 0.82, 0.98), 6.0),     # Cyan (arch signal)
    "MS_Rubber":      ("/Game/AOS_DK_Game/Environment/CustomHero/Materials/MI_Rubber_Seal", None),
    "MS_Concrete":    ("/Game/Scene_UnfinishedBuilding/Assets/Megascans/Surfaces/Wall_Concrete_Rough_01/MI_Wall_Concrete_Rough_01_D", None),
}

def import_all():
    tasks = []
    for n in NAMES:
        o = unreal.FbxImportUI()
        o.import_mesh = True; o.import_as_skeletal = False
        o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        o.import_animations = False; o.import_materials = False; o.import_textures = False
        sd = o.static_mesh_import_data
        sd.set_editor_property("combine_meshes", True)
        sd.set_editor_property("auto_generate_collision", False)       # UCX only
        sd.set_editor_property("one_convex_hull_per_ucx", True)        # UCX_<Mesh>_NN -> exactly one convex element each
        sd.set_editor_property("generate_lightmap_u_vs", False)         # Lumen, no lightmaps
        sd.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        try: sd.set_editor_property("build_nanite", True)
        except Exception: pass
        t = unreal.AssetImportTask()
        t.filename, t.destination_path, t.destination_name = os.path.join(FBX_DIR, n + ".fbx"), DST, n
        t.automated, t.replace_existing, t.save, t.options = True, True, False, o
        tasks.append(t)
    # UE 5.7 routes FBX through Interchange, which ignores FbxImportUI and drops UCX_ hulls.
    # Force the legacy FBX importer for these tasks only, then restore the cvar.
    CV = "Interchange.FeatureFlags.Import.FBX"
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    prev = unreal.SystemLibrary.get_console_variable_bool_value(CV)
    unreal.SystemLibrary.execute_console_command(world, CV + " 0")
    try:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    finally:
        unreal.SystemLibrary.execute_console_command(world, CV + (" 1" if prev else " 0"))
    return {t.destination_name: list(t.imported_object_paths) for t in tasks}, prev

def material_instances():
    MEL = unreal.MaterialEditingLibrary
    parent = unreal.load_asset(PARENT); out = {}
    if not EAL.does_directory_exist(MAT_DIR): EAL.make_directory(MAT_DIR)
    for slot, spec in MATS.items():
        if spec[1] is None:
            out[slot] = unreal.load_asset(spec[0]); continue           # shared project material: load only
        name, bc, mt, rg, ec, ei = spec; path = MAT_DIR + "/" + name
        mi = unreal.load_asset(path) if EAL.does_asset_exist(path) else \
            unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parent)
        MEL.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(bc[0], bc[1], bc[2], 1))
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", mt)
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", rg)
        MEL.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(ec[0], ec[1], ec[2], 1))
        MEL.set_material_instance_scalar_parameter_value(mi, "EmissiveIntensity", ei)
        EAL.save_loaded_asset(mi); out[slot] = mi
    return out

def author(n, sm, mis):
    a = SPEC["assets"][n]
    sm.modify()
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name"))
        if sn in mis and mis[sn]: sm.set_material(i, mis[sn])
    for name in a["sockets"]:
        old = sm.find_socket(name)
        if old: sm.remove_socket(old)
    for name, sd in a["sockets"].items():
        s = unreal.StaticMeshSocket(sm)
        s.set_editor_property("socket_name", name)
        s.set_editor_property("relative_location", ue(sd["pos"]))
        s.set_editor_property("relative_rotation", unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])))
        sm.add_socket(s)
    bs = sm.get_editor_property("body_setup")                      # simple hulls answer complex queries too
    bs.modify()
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    ns.set_editor_property("fallback_relative_error", 1.0)
    try: unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(sm, ns, True)
    except Exception: sm.set_editor_property("nanite_settings", ns)
    for k, v in (("AOS_Kit", "DeficitKit"), ("AOS_AuditItem", str(a["item"])), ("AOS_CullClass", str(a["cull_class"]))):
        EAL.set_metadata_tag(sm, k, v)
    EAL.save_asset(DST + "/" + n, only_if_is_dirty=False)

# ------------------------------------------------------------------ verification
BASE = unreal.Vector(-420000.0, 420000.0, 150000.0)       # temp test actors, far from level content

def _hit(r):
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    return t[0]

def _hull_verts(c):
    """KConvexElem.VertexData is not reflected to Python in 5.7: count it from export_text()."""
    t = c.export_text(); i = t.find("VertexData=(")
    if i < 0: return -1
    i += len("VertexData="); d = 0
    for j in range(i, len(t)):
        d += (t[j] == "(") - (t[j] == ")")
        if d == 0: return t[i:j+1].count("(X=")
    return -1

def verify_one(n, sm, idx, world, eas):
    a = SPEC["assets"][n]; sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    ns = sm.get_editor_property("nanite_settings")
    bb = sm.get_bounding_box()
    exp_min = [a["bbox_min"][0], -a["bbox_max"][1], a["bbox_min"][2]]
    exp_max = [a["bbox_max"][0], -a["bbox_min"][1], a["bbox_max"][2]]
    gmin, gmax = list(bb.min.to_tuple()), list(bb.max.to_tuple())
    bs = sm.get_editor_property("body_setup"); ag = bs.get_editor_property("agg_geom")
    cx = ag.get_editor_property("convex_elems")
    cxv = [_hull_verts(c) for c in cx]
    socks = [s for s in a["sockets"] if sm.find_socket(s)]
    slots = [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None)
             for m in sm.get_editor_property("static_materials")]
    rep = {
        "valid": sm.get_num_lods() > 0, "verts_lod0": sub.get_number_verts(sm, 0),
        "nanite": bool(ns.get_editor_property("enabled")),
        "size": [round(gmax[i]-gmin[i], 1) for i in range(3)],
        "bounds_err_cm": round(max(max(abs(gmin[i]-exp_min[i]), abs(gmax[i]-exp_max[i])) for i in range(3)), 2),
        "convex": len(cx), "convex_expected": len(a["ucx"]), "convex_verts": cxv,
        "prims_box_sph_cap": len(ag.get_editor_property("box_elems")) + len(ag.get_editor_property("sphere_elems")) + len(ag.get_editor_property("sphyl_elems")),
        "trace_flag": str(bs.get_editor_property("collision_trace_flag")).split(".")[-1].split(":")[0],
        "slots": slots, "slots_unassigned": [s for s, m in slots if m is None or m == "WorldGridMaterial"],
        "sockets": "%d/%d" % (len(socks), len(a["sockets"])),
    }
    L = unreal.Vector(BASE.x + 2000.0*(idx % 7), BASE.y + 2000.0*(idx // 7), BASE.z)
    act = eas.spawn_actor_from_object(sm, L, unreal.Rotator(0, 0, 0))
    act.set_actor_label("TMP_DK_Probe_" + n)
    SL, VIS, NONE = unreal.SystemLibrary, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, unreal.DrawDebugTrace.NONE
    W = lambda p: unreal.Vector(L.x + p[0], L.y - p[1], L.z + p[2])        # Max-space probe -> world
    pr = {}
    try:
        for p in a["probes"]:
            hs = _hit(SL.line_trace_single(world, W(p["start"]), W(p["end"]), VIS, False, [], NONE, True))
            hc = _hit(SL.line_trace_single(world, W(p["start"]), W(p["end"]), VIS, True, [], NONE, True))
            pr[p["name"]] = {"simple": bool(hs), "complex": bool(hc), "pass": bool(hs) == p["expect_hit"] and bool(hc) == p["expect_hit"]}
    finally:
        eas.destroy_actor(act)
    rep["probes"] = pr
    rep["PASS"] = (rep["valid"] and rep["nanite"] and rep["bounds_err_cm"] <= 0.5 and rep["convex"] == rep["convex_expected"]
                   and all(0 < v <= 32 for v in cxv) and rep["prims_box_sph_cap"] == 0 and "SIMPLE_AS_COMPLEX" in rep["trace_flag"]
                   and not rep["slots_unassigned"] and len(socks) == len(a["sockets"]) and all(v["pass"] for v in pr.values()))
    return rep

def verify():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    out = {}
    for i, n in enumerate(NAMES):
        sm = unreal.load_asset(DST + "/" + n)
        out[n] = verify_one(n, sm, i, world, eas) if sm else {"PASS": False, "error": "missing asset"}
    return out

out = {}
if MODE in ("import", "all"):
    out["imported"], out["interchange_fbx_prev"] = import_all()
    out["interchange_fbx_now"] = unreal.SystemLibrary.get_console_variable_bool_value("Interchange.FeatureFlags.Import.FBX")
    mis = material_instances()
    for n in NAMES:
        sm = unreal.load_asset(DST + "/" + n)
        if sm: author(n, sm, mis)
if MODE in ("verify", "all"):
    out["verify"] = verify()
    out["pass_count"] = "%d/%d" % (sum(1 for v in out["verify"].values() if v.get("PASS")), len(NAMES))
result = out
