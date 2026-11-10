# AOS-DK | SM_Cargo_Pod_Phys | UE 5.7.4 import + materials + sockets + verification (run via execute_python)
# Reads Tools/SM_Cargo_Pod_Phys_spec.json written by max_build_SM_Cargo_Pod_Phys.py.
# Max RH -> UE LH: (x, y, z) -> (x, -y, z). Re-runnable (replace_existing, sockets re-authored).
# MODE: "import" = import + author; "verify" = checks + trace / sweep probes; "all" = both.
# Run: g={"CPOD_MODE":"all"}; exec(open(<proj>/Tools/ue_import_SM_Cargo_Pod_Phys.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math
MODE = globals().get("CPOD_MODE", "all")
ASSET = "SM_Cargo_Pod_Phys"
DST = "/Game/AOS_DK_Game/Environment/CustomHero"
MAT_DIR = DST + "/Materials"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/CustomHero/%s.fbx" % ASSET)
SPEC = json.load(open(os.path.join(PROJ, "Tools/%s_spec.json" % ASSET), encoding="utf-8"))
ue = lambda v: unreal.Vector(v[0], -v[1], v[2])
EAL = unreal.EditorAssetLibrary

# slot -> (MI name, base colour (linear), metallic, roughness, emissive colour, emissive intensity) | None = reuse as-is
MATS = {
    "MS_PaintSteel_Worn": ("MI_CargoPod_PaintSteel_Worn", (0.80, 0.30, 0.015), 0.15, 0.62, (0, 0, 0), 0.0),  # safety orange-yellow, worn
    "MS_HydraulicChrome": ("MI_Hydraulic_Chrome", None),                                                    # shared hero library MI (read-only)
    "MS_RubberSkid":      ("MI_Rubber_Seal", None),                                                         # shared hero library MI (read-only)
    "MS_StatusEmissive":  ("MI_CargoPod_Status", (0.0, 0.0, 0.0), 0.0, 0.40, (0.08, 0.955, 0.198), 6.0),   # Dracula Green, I 6
}

def import_fbx():
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False
    sd = o.static_mesh_import_data
    sd.set_editor_property("combine_meshes", True)
    sd.set_editor_property("auto_generate_collision", False)      # UCX only
    sd.set_editor_property("one_convex_hull_per_ucx", True)       # UCX_..._01 -> exactly one convex element
    sd.set_editor_property("generate_lightmap_u_vs", False)
    try: sd.set_editor_property("build_nanite", True)
    except Exception: pass
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = FBX, DST, ASSET
    t.automated, t.replace_existing, t.save, t.options = True, True, False, o
    # UE 5.7 routes FBX through Interchange, which ignores FbxImportUI and drops UCX_ hulls.
    # Force the legacy FBX importer for this task only, then restore the cvar.
    CV = "Interchange.FeatureFlags.Import.FBX"
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    prev = unreal.SystemLibrary.get_console_variable_bool_value(CV)
    unreal.SystemLibrary.execute_console_command(world, CV + " 0")
    try:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    finally:
        unreal.SystemLibrary.execute_console_command(world, CV + (" 1" if prev else " 0"))
    return list(t.imported_object_paths), prev

def material_instances():
    MEL = unreal.MaterialEditingLibrary
    parent = unreal.load_asset(MAT_DIR + "/M_AOS_HeroSurface"); out = {}
    for slot, spec in MATS.items():
        name = spec[0]; path = MAT_DIR + "/" + name
        if spec[1] is None:                                      # shared MI: load only, never modify
            out[slot] = unreal.load_asset(path); continue
        _, bc, mt, rg, ec, ei = spec
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
    mis = material_instances(); slots = []
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name")); slots.append(sn)
        if sn in mis and mis[sn]: sm.set_material(i, mis[sn])
    for name in SPEC["sockets"]:
        old = sm.find_socket(name)
        if old: sm.remove_socket(old)
    for name, sd in SPEC["sockets"].items():
        s = unreal.StaticMeshSocket(sm)
        s.set_editor_property("socket_name", name)
        s.set_editor_property("relative_location", ue(sd["pos"]))
        s.set_editor_property("relative_rotation", unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])))
        sm.add_socket(s)
    bs = sm.get_editor_property("body_setup")      # simple (single UCX) for simple queries + Chaos sim
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_DEFAULT)
    ns = sm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", True)
    try: unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(sm, ns, True)
    except Exception: sm.set_editor_property("nanite_settings", ns)
    EAL.save_asset(DST + "/" + ASSET, only_if_is_dirty=False)
    return slots

# ------------------------------------------------------------------ verification
L = unreal.Vector(420000.0, 420000.0, 150000.0)     # temp test actor location (far from level content)
def _hit(r):
    """HitResult -> dict in ACTOR-LOCAL UE coords (or None). to_tuple(): 0 blocking, 4 location, 7 impact normal."""
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    if not t[0]: return None
    v, n = t[4], t[7]
    return {"loc": [round(v.x - L.x, 1), round(v.y - L.y, 1), round(v.z - L.z, 1)], "n": [round(n.x, 3), round(n.y, 3), round(n.z, 3)]}

def verify(sm):
    rep = {}
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    ns = sm.get_editor_property("nanite_settings")
    bb = sm.get_bounding_box(); st = SPEC["stats"]
    exp_min = [st["bbox_min"][0], -st["bbox_max"][1], st["bbox_min"][2]]
    exp_max = [st["bbox_max"][0], -st["bbox_min"][1], st["bbox_max"][2]]
    got_min = [round(c, 1) for c in bb.min.to_tuple()]; got_max = [round(c, 1) for c in bb.max.to_tuple()]
    bs = sm.get_editor_property("body_setup"); ag = bs.get_editor_property("agg_geom")
    cx = ag.get_editor_property("convex_elems")
    cx_verts = []
    for c in cx:
        try: cx_verts.append(len(c.get_editor_property("vertex_data")))
        except Exception: cx_verts.append(None)
    socks = sorted(n for n in SPEC["sockets"] if sm.find_socket(n))
    rep.update({
        "valid": sm is not None and sm.get_num_lods() > 0, "lods": sm.get_num_lods(),
        "verts_lod0": sub.get_number_verts(sm, 0), "nanite_enabled": bool(ns.get_editor_property("enabled")),
        "bounds_min": got_min, "bounds_max": got_max,
        "bounds_size": [round(got_max[i] - got_min[i], 1) for i in range(3)],
        "bounds_match_cm": max(max(abs(got_min[i] - exp_min[i]), abs(got_max[i] - exp_max[i])) for i in range(3)),
        "convex_count": sub.get_convex_collision_count(sm), "convex_elems": len(cx), "convex_vertex_data": cx_verts,
        "simple_box/sphere/capsule/tapered": [len(ag.get_editor_property("box_elems")), len(ag.get_editor_property("sphere_elems")),
                                              len(ag.get_editor_property("sphyl_elems")), len(ag.get_editor_property("tapered_capsule_elems"))],
        "collision_trace_flag": str(bs.get_editor_property("collision_trace_flag")),
        "material_slots": [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None)
                           for m in sm.get_editor_property("static_materials")],
        "sockets_registered": len(socks), "sockets_expected": len(SPEC["sockets"]),
        "sockets_missing": sorted(set(SPEC["sockets"]) - set(socks)),
        "socket_locs": {n: [round(c, 1) for c in sm.find_socket(n).get_editor_property("relative_location").to_tuple()] for n in socks},
    })
    if cx:
        try:
            vd = cx[0].get_editor_property("vertex_data")
            rep["convex_vertex_extent"] = [[round(min(getattr(v, a) for v in vd), 1) for a in "xyz"], [round(max(getattr(v, a) for v in vd), 1) for a in "xyz"]]
        except Exception as ex:
            rep["convex_vertex_extent"] = "n/a (%s)" % type(ex).__name__

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_object(sm, L, unreal.Rotator(0, 0, 0))
    a.set_actor_label("TMP_CargoPod_TraceTest")
    SL, VIS, NONE = unreal.SystemLibrary, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, unreal.DrawDebugTrace.NONE
    W = lambda x, y, z: unreal.Vector(L.x + x, L.y + y, L.z + z)
    def line(p0, p1, cplx=False): return _hit(SL.line_trace_single(world, W(*p0), W(*p1), VIS, cplx, [], NONE, True))
    def box(p0, p1, he): return _hit(SL.box_trace_single(world, W(*p0), W(*p1), unreal.Vector(*he), unreal.Rotator(0, 0, 0), VIS, False, [], NONE, True))
    try:
        pr = {}
        # resting / skid contact: upward traces from below hit the flat UCX underside at Z -118
        pr["skid_contact_z"] = [line((x, y, -400.0), (x, y, 0.0)) for (x, y) in ((0, 62), (0, -62), (140, 62), (-140, -62), (0, 0))]
        # pad-eyes: lines along X through the four eye centres -> simple misses, complex hits (visual only)
        eyes = [sd["pos"] for k, sd in SPEC["sockets"].items() if k.startswith("SOCKET_Lift_")]
        pe = []
        for e in eyes:
            y, z = -e[1], e[2]; sx = 1.0 if e[0] > 0 else -1.0
            pe.append({"eye_ue": [e[0], round(y, 1), round(z, 1)],
                       "simple": line((sx*400.0, y, z), (0.0, y, z)), "complex": line((sx*400.0, y, z), (0.0, y, z), True)})
        pr["padeye_lines"] = pe
        # pressure-relief valve handwheel (Max +Y -> UE -Y): simple miss, complex hit
        v = SPEC["sockets"]["SOCKET_VFX_Leak_00"]["pos"]
        pr["valve_line"] = {"simple": line((v[0], -95.5, -300.0), (v[0], -95.5, 300.0)), "complex": line((v[0], -95.5, -300.0), (v[0], -95.5, 300.0), True)}
        # Shell-1 push probes (box 400 x 200 x 200) - impact normal must be clean (+-X / +-Y / +Z)
        pr["shell_push_front"] = box((700.0, 0, 0), (0, 0, 0), (200, 100, 100))
        pr["shell_push_rear"] = box((-700.0, 0, 0), (0, 0, 0), (200, 100, 100))
        pr["shell_push_side"] = box((0, 600.0, 0), (0, 0, 0), (200, 100, 100))
        pr["shell_land_top"] = box((0, 0, 700.0), (0, 0, 0), (200, 100, 100))
        pr["shell_skim_low"] = box((700.0, 0, -60.0), (0, 0, -60.0), (200, 100, 30))      # low nudge onto tapered nose
        # controls
        pr["ctrl_axis_front (expect hit X 200)"] = line((400.0, 0, 0), (0, 0, 0))
        pr["ctrl_side_minusY (expect hit Y -90)"] = line((0, -400.0, 0), (0, 0, 0))
        rep["probes"] = pr
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        try: rep["body_mass_kg_default_density"] = round(smc.get_mass(), 1)
        except Exception as ex: rep["body_mass_kg_default_density"] = str(ex)
    finally:
        eas.destroy_actor(a)
    return rep

out = {}
if MODE in ("import", "all"):
    out["imported"], out["interchange_fbx_prev"] = import_fbx()
    out["interchange_fbx_now"] = unreal.SystemLibrary.get_console_variable_bool_value("Interchange.FeatureFlags.Import.FBX")
    out["slots"] = author(unreal.load_asset(DST + "/" + ASSET))
if MODE in ("verify", "all"):
    out["verify"] = verify(unreal.load_asset(DST + "/" + ASSET))
result = out
