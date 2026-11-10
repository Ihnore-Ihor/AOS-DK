# AOS-DK | SM_Breach_SomaLock | UE 5.7.4 import + materials + sockets + verification (run via execute_python)
# Reads Tools/SM_Breach_SomaLock_spec.json written by max_build_SM_Breach_SomaLock.py.
# Max RH -> UE LH: (x, y, z) -> (x, -y, z). Re-runnable (replace_existing, sockets re-authored).
# MODE: "import" = import + author; "verify" = checks + simple-collision sweeps; "all" = both.
import unreal, json, os, math
MODE = globals().get("SOMA_MODE", "all")
ASSET = "SM_Breach_SomaLock"
DST = "/Game/AOS_DK_Game/Environment/CustomHero"
MAT_DIR = DST + "/Materials"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/CustomHero/%s.fbx" % ASSET)
SPEC = json.load(open(os.path.join(PROJ, "Tools/%s_spec.json" % ASSET)))
ue = lambda v: unreal.Vector(v[0], -v[1], v[2])
EAL = unreal.EditorAssetLibrary

# slot -> (MI name, base colour, metallic, roughness, emissive colour, emissive intensity)
MATS = {
    "MS_Armor":     ("MI_Titanium_Armor_Worn", (0.18, 0.19, 0.20), 1.0, 0.52, (0, 0, 0), 0.0),
    "MS_Hydraulic": ("MI_Hydraulic_Chrome",    (0.80, 0.81, 0.82), 1.0, 0.08, (0, 0, 0), 0.0),
    "MS_Seal":      ("MI_Rubber_Seal",         (0.012, 0.012, 0.014), 0.0, 0.85, (0, 0, 0), 0.0),
    "MS_Status":    ("MI_Lock_Status",         (0.0, 0.0, 0.0), 0.0, 0.4, (1.0, 0.02, 0.01), 6.0),  # Jammed: Red, I 6
}

def import_fbx():
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False
    sd = o.static_mesh_import_data
    sd.set_editor_property("combine_meshes", True)
    sd.set_editor_property("auto_generate_collision", False)      # UCX only
    sd.set_editor_property("one_convex_hull_per_ucx", True)
    sd.set_editor_property("generate_lightmap_u_vs", False)
    try: sd.set_editor_property("build_nanite", True)
    except Exception: pass
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = FBX, DST, ASSET
    t.automated, t.replace_existing, t.save, t.options = True, True, False, o
    # UE 5.7 routes FBX through Interchange by default, which ignores FbxImportUI and dropped the
    # UCX_ hulls in testing. Force the legacy FBX importer for this task only, then restore the cvar.
    CV = "Interchange.FeatureFlags.Import.FBX"
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    prev = unreal.SystemLibrary.get_console_variable_bool_value(CV)
    unreal.SystemLibrary.execute_console_command(world, CV + " 0")
    try:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    finally:
        unreal.SystemLibrary.execute_console_command(world, CV + (" 1" if prev else " 0"))
    return list(t.imported_object_paths)

def master_material():
    path = MAT_DIR + "/M_AOS_HeroSurface"
    if EAL.does_asset_exist(path): return unreal.load_asset(path)
    MEL = unreal.MaterialEditingLibrary
    m = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_AOS_HeroSurface", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    def vp(name, x, y, val):
        n = MEL.create_material_expression(m, unreal.MaterialExpressionVectorParameter, x, y)
        n.set_editor_property("parameter_name", name); n.set_editor_property("default_value", unreal.LinearColor(*val)); return n
    def sp(name, x, y, val):
        n = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y)
        n.set_editor_property("parameter_name", name); n.set_editor_property("default_value", val); return n
    bc = vp("BaseColor", -600, -200, (0.5, 0.5, 0.5, 1)); MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mt = sp("Metallic", -600, 0, 0.0); MEL.connect_material_property(mt, "", unreal.MaterialProperty.MP_METALLIC)
    rg = sp("Roughness", -600, 100, 0.5); MEL.connect_material_property(rg, "", unreal.MaterialProperty.MP_ROUGHNESS)
    ec = vp("EmissiveColor", -800, 250, (0, 0, 0, 1)); ei = sp("EmissiveIntensity", -800, 450, 0.0)
    mul = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -400, 300)
    MEL.connect_material_expressions(ec, "", mul, "A"); MEL.connect_material_expressions(ei, "", mul, "B")
    MEL.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m); EAL.save_loaded_asset(m)
    return m

def material_instances():
    MEL = unreal.MaterialEditingLibrary
    parent = master_material(); out = {}
    for slot, (name, bc, mt, rg, ec, ei) in MATS.items():
        path = MAT_DIR + "/" + name
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

def author(sm):
    sm.modify()
    # materials by slot name
    mis = material_instances(); slots = []
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name")); slots.append(sn)
        if sn in mis: sm.set_material(i, mis[sn])
    # sockets (re-authored from JSON)
    for name in SPEC["sockets"]:
        old = sm.find_socket(name)
        if old: sm.remove_socket(old)
    for name, sd in SPEC["sockets"].items():
        s = unreal.StaticMeshSocket(sm)
        s.set_editor_property("socket_name", name)
        s.set_editor_property("relative_location", ue(sd["pos"]))
        s.set_editor_property("relative_rotation", unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])))
        sm.add_socket(s)
    # collision: simple (UCX) for simple queries, never complex-as-simple
    bs = sm.get_editor_property("body_setup")
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_DEFAULT)
    # Nanite
    ns = sm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", True)
    sme_sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    try: sme_sub.set_nanite_settings(sm, ns, True)
    except Exception: sm.set_editor_property("nanite_settings", ns)
    EAL.save_asset(DST + "/" + ASSET, only_if_is_dirty=False)
    return slots

# ------------------------------------------------------------------ verification
L = unreal.Vector(400000.0, 400000.0, 150000.0)     # temp test actor location (far from level content)
def _hit(r):
    """HitResult -> dict in ACTOR-LOCAL UE coords (or None). to_tuple(): 0 blocking, 4 location, 14 element index."""
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    if not t[0]: return None
    v = t[4]
    return {"loc": [round(v.x - L.x, 1), round(v.y - L.y, 1), round(v.z - L.z, 1)], "convex_elem": t[14]}

def verify(sm):
    rep = {}
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    ns = sm.get_editor_property("nanite_settings")
    bb = sm.get_bounding_box()
    st = SPEC["stats"]
    exp_min = [st["bbox_min"][0], -st["bbox_max"][1], st["bbox_min"][2]]
    exp_max = [st["bbox_max"][0], -st["bbox_min"][1], st["bbox_max"][2]]
    got_min = [round(c, 1) for c in bb.min.to_tuple()]; got_max = [round(c, 1) for c in bb.max.to_tuple()]
    bs = sm.get_editor_property("body_setup"); ag = bs.get_editor_property("agg_geom")
    conv = ag.get_editor_property("convex_elems")
    rep.update({
        "valid": sm is not None and sm.get_num_lods() > 0,
        "lods": sm.get_num_lods(), "verts_lod0": sub.get_number_verts(sm, 0),
        "nanite_enabled": bool(ns.get_editor_property("enabled")),
        "bounds_min": got_min, "bounds_max": got_max, "bounds_expected_min": exp_min, "bounds_expected_max": exp_max,
        "bounds_size": [round(got_max[i] - got_min[i], 1) for i in range(3)],
        "bounds_match_cm": max(max(abs(got_min[i] - exp_min[i]), abs(got_max[i] - exp_max[i])) for i in range(3)),
        "convex_count": sub.get_convex_collision_count(sm),
        "simple_box/sphere/capsule": [len(ag.get_editor_property("box_elems")), len(ag.get_editor_property("sphyl_elems")), len(ag.get_editor_property("sphere_elems"))],
        "collision_trace_flag": str(bs.get_editor_property("collision_trace_flag")),
        "material_slots": [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None)
                           for m in sm.get_editor_property("static_materials")],
        "sockets": sorted(str(sm.get_socket_by_index(i).get_editor_property("socket_name")) for i in range(sm.get_num_sockets())) if hasattr(sm, "get_num_sockets") else None,
    })
    if rep["sockets"] is None:
        rep["sockets"] = sorted(n for n in SPEC["sockets"] if sm.find_socket(n))
    rep["sockets_missing"] = sorted(set(SPEC["sockets"]) - set(rep["sockets"]))

    # ---- simple-collision sweeps on a temporary actor far from level content
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_object(sm, L, unreal.Rotator(0, 0, 0))
    a.set_actor_label("TMP_SomaLock_SweepTest")
    SL, VIS, NONE = unreal.SystemLibrary, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, unreal.DrawDebugTrace.NONE
    lens_y = -SPEC["lens"]["centre_yz"][0]; lens_r = SPEC["lens"]["radius"]
    W = lambda x, y, z: unreal.Vector(L.x + x, L.y + y, L.z + z)
    def box(y, z, he=(200, 100, 100), x0=-1500, x1=1300):
        return _hit(SL.box_trace_single(world, W(x0, y, z), W(x1, y, z), unreal.Vector(*he), unreal.Rotator(0, 0, 0), VIS, False, [], NONE, True))
    def sph(y, z, r, x0=-1500, x1=1300):
        return _hit(SL.sphere_trace_single(world, W(x0, y, z), W(x1, y, z), r, VIS, False, [], NONE, True))
    def line(p0, p1):
        return _hit(SL.line_trace_single(world, W(*p0), W(*p1), VIS, False, [], NONE, True))
    try:
        sw = {}
        sw["shell1_box_400x200x200_through_lens"] = box(lens_y, 0)
        sw["sphere_R240_through_lens"] = sph(lens_y, 0, 240.0)
        ring_hits = 0
        for k in range(72):
            a_ = math.radians(k*5.0)
            if line((-1500, lens_y + 245*math.cos(a_), 245*math.sin(a_)), (1300, lens_y + 245*math.cos(a_), 245*math.sin(a_))): ring_hits += 1
        sw["ring72_lines_R245_hits"] = ring_hits
        sw["CONTROL_sphere_R256_through_lens (expect hit: lens is Ø496)"] = sph(lens_y, 0, 256.0)
        sw["CONTROL_shell1_box_at_leaf (expect hit)"] = box(-250.0, 0)
        sw["CONTROL_line_through_frame (expect hit)"] = line((-1500, 0, 500), (1300, 0, 500))
        sw["CONTROL_complex_trace_lens_line"] = _hit(SL.line_trace_single(world, W(-1500, lens_y, 0), W(1300, lens_y, 0), VIS, True, [], NONE, True))
        # measured clear radius around the lens centre (radial line traces in the leaf plane and mid-tunnel)
        for xp, tag in ((-470.0, "leaf_plane"), (0.0, "mid_tunnel")):
            dmin = 1e9
            for k in range(72):
                a_ = math.radians(k*5.0); d = (math.cos(a_), math.sin(a_))
                h = SL.line_trace_single(world, W(xp, lens_y, 0), W(xp, lens_y + 900*d[0], 900*d[1]), VIS, False, [], NONE, True)
                hh = _hit(h)
                if hh:
                    dmin = min(dmin, math.hypot(hh["loc"][1] - lens_y, hh["loc"][2]))
            sw["measured_clear_radius_" + tag] = round(dmin, 1)
        rep["sweeps"] = sw
    finally:
        eas.destroy_actor(a)
    return rep

out = {}
if MODE in ("import", "all"):
    out["imported"] = import_fbx()
    smx = unreal.load_asset(DST + "/" + ASSET)
    out["slots"] = author(smx)
if MODE in ("verify", "all"):
    out["verify"] = verify(unreal.load_asset(DST + "/" + ASSET))
result = out
