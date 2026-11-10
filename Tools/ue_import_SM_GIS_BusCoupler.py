# AOS-DK | SM_GIS_BusCoupler | UE 5.7.4 import + materials + sockets + verification (run via execute_python)
# Reads Tools/SM_GIS_BusCoupler_spec.json written by max_build_SM_GIS_BusCoupler.py.
# Max RH -> UE LH: (x, y, z) -> (x, -y, z). Re-runnable (replace_existing, sockets re-authored).
# MODE: "import" = import + author; "verify" = checks + simple-collision sweeps; "all" = both.
# Run: g={"GISB_MODE":"all"}; exec(open(<proj>/Tools/ue_import_SM_GIS_BusCoupler.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math
MODE = globals().get("GISB_MODE", "all")
ASSET = "SM_GIS_BusCoupler"
DST = "/Game/AOS_DK_Game/Environment/CustomHero"
MAT_DIR = DST + "/Materials"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/CustomHero/%s.fbx" % ASSET)
SPEC = json.load(open(os.path.join(PROJ, "Tools/%s_spec.json" % ASSET), encoding="utf-8"))
ue = lambda v: unreal.Vector(v[0], -v[1], v[2])
EAL = unreal.EditorAssetLibrary

# slot -> (MI name, base colour, metallic, roughness, emissive colour, emissive intensity)
MATS = {
    "MS_CastAluminum": ("MI_GIS_CastAluminum",     (0.42, 0.43, 0.45), 1.0, 0.45, (0, 0, 0), 0.0),
    "MS_Conductor":    ("MI_GIS_Conductor_Copper", (0.95, 0.64, 0.54), 1.0, 0.15, (0, 0, 0), 0.0),
    "MS_Insulator":    ("MI_GIS_Insulator_Epoxy",  (0.55, 0.50, 0.38), 0.0, 0.35, (0, 0, 0), 0.0),
    "MS_Status":       ("MI_GIS_Status_Live",      (0.0, 0.0, 0.0),    0.0, 0.40, (0.0, 0.85, 1.0), 6.0),  # Live: Cyan, I 6
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
    mis = material_instances(); slots = []
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name")); slots.append(sn)
        if sn in mis: sm.set_material(i, mis[sn])
    for name in SPEC["sockets"]:
        old = sm.find_socket(name)
        if old: sm.remove_socket(old)
    for name, sd in SPEC["sockets"].items():
        s = unreal.StaticMeshSocket(sm)
        s.set_editor_property("socket_name", name)
        s.set_editor_property("relative_location", ue(sd["pos"]))
        s.set_editor_property("relative_rotation", unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])))
        sm.add_socket(s)
    bs = sm.get_editor_property("body_setup")      # simple (UCX) for simple queries, never complex-as-simple
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_DEFAULT)
    ns = sm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", True)
    try: unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(sm, ns, True)
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
    return {"loc": [round(v.x - L.x, 1), round(v.y - L.y, 1), round(v.z - L.z, 1)], "elem": t[14]}

def verify(sm):
    rep = {}
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    ns = sm.get_editor_property("nanite_settings")
    bb = sm.get_bounding_box(); st = SPEC["stats"]
    exp_min = [st["bbox_min"][0], -st["bbox_max"][1], st["bbox_min"][2]]
    exp_max = [st["bbox_max"][0], -st["bbox_min"][1], st["bbox_max"][2]]
    got_min = [round(c, 1) for c in bb.min.to_tuple()]; got_max = [round(c, 1) for c in bb.max.to_tuple()]
    bs = sm.get_editor_property("body_setup"); ag = bs.get_editor_property("agg_geom")
    socks = sorted(n for n in SPEC["sockets"] if sm.find_socket(n))
    rep.update({
        "valid": sm is not None and sm.get_num_lods() > 0, "lods": sm.get_num_lods(),
        "verts_lod0": sub.get_number_verts(sm, 0), "nanite_enabled": bool(ns.get_editor_property("enabled")),
        "bounds_min": got_min, "bounds_max": got_max,
        "bounds_size": [round(got_max[i] - got_min[i], 1) for i in range(3)],
        "bounds_match_cm": max(max(abs(got_min[i] - exp_min[i]), abs(got_max[i] - exp_max[i])) for i in range(3)),
        "convex_count": sub.get_convex_collision_count(sm), "convex_expected": SPEC["stats"]["ucx_count"],
        "simple_box/sphere/capsule": [len(ag.get_editor_property("box_elems")), len(ag.get_editor_property("sphere_elems")), len(ag.get_editor_property("sphyl_elems"))],
        "collision_trace_flag": str(bs.get_editor_property("collision_trace_flag")),
        "material_slots": [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None)
                           for m in sm.get_editor_property("static_materials")],
        "sockets_registered": len(socks), "sockets_expected": len(SPEC["sockets"]),
        "sockets_missing": sorted(set(SPEC["sockets"]) - set(socks)),
    })
    nav_in = sm.find_socket("SOCKET_Nav_Conduit_In"); nav_out = sm.find_socket("SOCKET_Nav_Conduit_Out")
    rep["nav_in_loc"] = [round(c, 1) for c in nav_in.get_editor_property("relative_location").to_tuple()]
    rep["nav_out_loc"] = [round(c, 1) for c in nav_out.get_editor_property("relative_location").to_tuple()]

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_object(sm, L, unreal.Rotator(0, 0, 0))
    a.set_actor_label("TMP_GISBusCoupler_SweepTest")
    SL, VIS, NONE = unreal.SystemLibrary, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, unreal.DrawDebugTrace.NONE
    W = lambda x, y, z: unreal.Vector(L.x + x, L.y + y, L.z + z)
    XA, XB = -4500.0, 4500.0
    def box(y, z, rot, he=(200, 100, 100)):
        return _hit(SL.box_trace_single(world, W(XA, y, z), W(XB, y, z), unreal.Vector(*he), rot, VIS, False, [], NONE, True))
    def sph(p0, p1, r):
        return _hit(SL.sphere_trace_single(world, W(*p0), W(*p1), r, VIS, False, [], NONE, True))
    def line(p0, p1, cplx=False):
        return _hit(SL.line_trace_single(world, W(*p0), W(*p1), VIS, cplx, [], NONE, True))
    R_SH = SPEC["shell_r"]
    try:
        sw = {}
        rots = [unreal.Rotator(roll=0, pitch=0, yaw=0), unreal.Rotator(roll=90, pitch=0, yaw=0), unreal.Rotator(roll=45, pitch=0, yaw=0)]
        lanes = []
        for ln in SPEC["lanes"]:
            y, z = -ln["centre_yz"][0], ln["centre_yz"][1]           # UE space
            rec = {"az": ln["az"], "ue_yz": [round(y, 1), round(z, 1)], "analytic_r": ln["radius"]}
            rec["shell1_box_hits"] = sum(1 for r in rots if box(y, z, r))
            rec["sphere_R245_hit"] = bool(sph((XA, y, z), (XB, y, z), R_SH))
            rec["ring36_lines_hits"] = sum(1 for k in range(36) if line(
                (XA, y + (ln["radius"] - 2)*math.cos(math.radians(k*10)), z + (ln["radius"] - 2)*math.sin(math.radians(k*10))),
                (XB, y + (ln["radius"] - 2)*math.cos(math.radians(k*10)), z + (ln["radius"] - 2)*math.sin(math.radians(k*10)))))
            lo, hi = R_SH, ln["radius"] + 60.0                       # measured clear radius: sphere-sweep bisection
            for _ in range(14):
                mid = (lo + hi) / 2.0
                if sph((XA, y, z), (XB, y, z), mid): hi = mid
                else: lo = mid
            rec["measured_clear_r"] = round(lo, 1)
            rec["complex_line_hit"] = bool(line((XA, y, z), (XB, y, z), True))
            lanes.append(rec)
        sw["lanes"] = lanes
        rb = SPEC["ring_band"]; xs = (rb["x_insulator_band"][0] - R_SH - 700.0, rb["x_insulator_band"][1] + R_SH + 700.0)
        ring_hits = {}
        for xr in xs:                                                # circumferential sphere sweeps (6DOF ring channel)
            for rr in (rb["r_inner"] + R_SH + 5.0, (rb["r_inner"] + rb["r_outer"]) / 2.0, rb["r_outer"] - R_SH - 5.0):
                n = 0
                for k in range(72):
                    a0, a1 = math.radians(k*5.0), math.radians((k + 1)*5.0)
                    if sph((xr, rr*math.cos(a0), rr*math.sin(a0)), (xr, rr*math.cos(a1), rr*math.sin(a1)), R_SH): n += 1
                ring_hits["x%d_r%d" % (xr, rr)] = n
        sw["ring_channel_sphere_sweeps_hits"] = ring_hits
        # measured ring band: radial line traces at both ring stations
        rin, rout = 0.0, 1e9
        for xr in xs:
            for k in range(36):
                d = (math.cos(math.radians(k*10 + 5)), math.sin(math.radians(k*10 + 5)))
                ho = line((xr, 2600*d[0], 2600*d[1]), (xr, 5000*d[0], 5000*d[1]))
                hi_ = line((xr, 2600*d[0], 2600*d[1]), (xr, 0.0, 0.0))
                if ho: rout = min(rout, math.hypot(ho["loc"][1], ho["loc"][2]))
                if hi_: rin = max(rin, math.hypot(hi_["loc"][1], hi_["loc"][2]))
        sw["measured_ring_band_r"] = [round(rin, 1), round(rout, 1)]
        ctrl = {}
        l0 = SPEC["lanes"][1]; y0, z0 = -l0["centre_yz"][0], l0["centre_yz"][1]
        ctrl["sphere_lane_r+15 (expect hit)"] = sph((XA, y0, z0), (XB, y0, z0), l0["radius"] + 15.0)
        ctrl["line_spoke_az0_r2600 (expect hit)"] = line((XA, -2600.0, 0.0), (XB, -2600.0, 0.0))
        ctrl["line_axis (expect hit conductor)"] = line((XA, 0.0, 0.0), (XB, 0.0, 0.0))
        ctrl["line_r3820_12oclock (expect hit stave)"] = line((XA, 0.0, 3820.0), (XB, 0.0, 3820.0))
        ctrl["shell1_box_on_spoke_az60 (expect hit)"] = box(-2600*math.cos(math.radians(60)), 2600*math.sin(math.radians(60)), rots[0])
        sw["controls"] = ctrl
        rep["sweeps"] = sw
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
