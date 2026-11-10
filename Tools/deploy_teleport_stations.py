"""AOS-DK Lab 4 - Evacuation Transit Shafts: assets, BP_TeleportStation and deployment into Lvl_FirstPerson.
Usage (MCP execute_python):
    g = {"TS_MODE": "assets" | "blueprint" | "deploy" | "verify" | "save" | "all"}
    exec(open(r"<proj>/Tools/deploy_teleport_stations.py", encoding="utf-8").read(), g); result = g["result"]
assets    : imports SourceArt/Teleport (Tools/gen_teleport_assets.py): SM_AOS_TransitShaft + 2 sounds; MIs (Dracula Cyan)
blueprint : BP_TeleportStation (parent AOSTeleportStation): SomaLock frame + shaft, materials, sounds
deploy    : removes previous AOS_Teleport actors, spawns Station A (rapid-test socket 25 m ahead of the Shell's berth,
            horizontal mouth facing the parked Shell) and B (on the axis of C-01's SM_Breach_SomaLock, mouth facing the lock),
            links A <-> B, folder Environment/Teleport, tags. Positions / yaw are auto-oriented from the level
            (BP_Shell berth, PRT_SomaLock_Main) - see resolve_stations().
verify    : link / layout / collision read-back, Shell-1 clearance sweeps + controls -> Saved/Teleport_verify.json
save      : saves the level (OFPA external actor packages included)
Idempotent."""
import json, math, os
import unreal

MODE = globals().get("TS_MODE", "all")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SRC = os.path.join(PROJ, "SourceArt", "Teleport")
ROOT = "/Game/AOS_DK_Game/Gameplay/Teleport"
D_MESH, D_MAT, D_AUD = ROOT + "/Meshes", ROOT + "/Materials", ROOT + "/Audio"
BP_PATH = ROOT + "/BP_TeleportStation"
EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
HERO = "/Game/AOS_DK_Game/Environment/CustomHero/Materials/M_AOS_HeroSurface"
KIT = "/Game/AOS_DK_Game/Environment/ModularKit/Materials/"
SOMALOCK = "/Game/AOS_DK_Game/Environment/CustomHero/SM_Breach_SomaLock"
FOLDER = "Environment/Teleport"
TAG = "AOS_Teleport"
OT_STATIC = unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1   # WorldStatic
OT_PHYS = unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY4     # PhysicsBody
SHELL_HALF = unreal.Vector(200, 100, 100)               # Shell-1 box 400 x 200 x 200
SHELL_R = 245.0

# Stations. origin = lens centre of the portal frame. Layout (C++ defaults): mouth face 711 from the origin,
# trigger 500 deep in front of the mouth, ExitPoint 300 beyond the trigger -> exit = origin - 1511 * entry axis.
# Both stations are horizontal (EAOSTransitDirection::Forward): entry axis = actor forward, the mouth faces -forward,
# the exit hands the Shell over level, facing out of the mouth, pushed outward at ExitSpeed (500 cm/s, coasts ~3.3 m).
FRAME_FRONT, TRIGGER_DEPTH, EXIT_CLEAR = 711.0, 500.0, 300.0
EXIT_OFFSET = FRAME_FRONT + TRIGGER_DEPTH + EXIT_CLEAR          # 1511
A_RANGE = 2200.0      # lens centre 22 m ahead of the parked Shell (trigger face ~8 m from its nose: < 5 s from the berth)
A_LENS_Z = -450.0     # frame rim breaks the surface (visible marker), shaft tube stays submerged
A_TRIGGER_HALF = 450.0  # trigger box reaches the waterline: a Shell cruising at the surface enters it without diving
B_EXIT_GAP = 870.0    # B exit point -> SomaLock entry face (the arriving Shell coasts to ~4 m from the leaf)
SOMA_LABEL, SOMA_ENTRY_FACE = "PRT_SomaLock_Main", 711.0        # SM_Breach_SomaLock: entry face at local -X 711
SHELL_LABEL = "BP_Shell"
# Shaft <-> gate alignment (SM_Breach_SomaLock, frame-local cm), all MEASURED on the assets by deploy (no hard offsets):
#  - the physical opening is the round tunnel BORE (traced: centre (Y 0, Z 0), R 410). The navigable lens (bore minus the
#    jammed leaf, inscribed circle) is off-centre at +162 Y: the actor origin / entry trigger stay on the lens, the tube does not.
#  - the shaft continues the bore: axis on the bore centre, frame rotation, mouth flush on the exit face (X 420; bolt heads 432),
#    outer wall (R 370) scaled radially to the bore radius so the mouth meets the opening edge with no ring gap.
LENS_Y, LENS_Z = 162.0, 0.0                # FrameLensOffset (lens centre of the frame mesh; traversal axis)
FRAME_EXIT_FACE_DEFAULT = 420.0
SHAFT_INNER_R, SHAFT_OUTER_R, SHAFT_LEN = 330.0, 370.0, 2400.0   # SM_AOS_TransitShaft, unscaled
SHELL_HALF_DIAG = 141.0                    # Shell-1 section half-diagonal (traversal clearance probe)
ALIGN_TOL_CM, ALIGN_TOL_DEG = 0.5, 0.01
STATIONS = {
    "A": dict(label="TP_Station_A_SurfaceSocket", name="Surface Socket [ETS-A]", dir="FORWARD",
              origin=(-1000.0, -1680.0, A_LENS_Z), yaw=-90.0, zone="Berth_TestSocket", anchor="ANC_Shell_Berth",
              trigger_half_width=A_TRIGGER_HALF),
    "B": dict(label="TP_Station_B_TowerA_C01", name="Tower A C-01 SomaLock [ETS-B]", dir="FORWARD",
              origin=(-57000.0, 22200.0, -9150.0), yaw=180.0, zone="C01_Outside_SomaLock", anchor="ANC_A3_home_a03"),
}

def resolve_stations():
    """Auto-orientation from the level: A on the parked Shell's heading, B on the SomaLock lens axis facing the lock."""
    notes = {}
    shell = find_label(SHELL_LABEL)
    if shell:
        p, f = shell.get_actor_location(), shell.get_actor_forward_vector()
        f = unreal.Vector(f.x, f.y, 0.0); f.normalize()
        yaw = math.degrees(math.atan2(f.y, f.x))
        STATIONS["A"].update(origin=(round(p.x + f.x * A_RANGE, 1), round(p.y + f.y * A_RANGE, 1), A_LENS_Z), yaw=round(yaw, 3))
        notes["A_from"] = [SHELL_LABEL, vl(p), round(yaw, 1)]
    lock = find_label(SOMA_LABEL)
    if lock:
        frame = next((c for c in lock.get_components_by_class(unreal.StaticMeshComponent)), None)
        xf = frame.get_world_transform() if frame else lock.get_actor_transform()
        lens = xf.transform_location(V(0.0, 162.0, 0.0))                     # lens centre (mesh +Y 162)
        out = (frame.get_forward_vector() if frame else lock.get_actor_forward_vector()) * -1.0  # entry side (outside)
        face = lens + out * SOMA_ENTRY_FACE
        origin = face + out * (B_EXIT_GAP + EXIT_OFFSET)                       # exit = origin - EXIT_OFFSET * entry
        entry = out                                                             # swim away from the lock into B
        STATIONS["B"].update(origin=(round(origin.x, 1), round(origin.y, 1), round(origin.z, 1)),
                             yaw=round(math.degrees(math.atan2(entry.y, entry.x)), 3))
        notes["B_from"] = [SOMA_LABEL, vl(lens), vl(face)]
    return notes

def srgb(h):
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    f = lambda x: x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return unreal.LinearColor(f(r), f(g), f(b), 1.0)

MI_SPECS = {  # name: (base linear, metallic, roughness, emissive hex, intensity)
    "MI_Transit_Status_Cyan": ((0, 0, 0), 0.0, 0.35, "8BE9FD", 7.0),
    "MI_Transit_Guide_Cyan": ((0, 0, 0), 0.0, 0.4, "8BE9FD", 4.0),
}
SHAFT_SLOTS = {"Steel": KIT + "MI_Kit_DarkSteel", "Frame": KIT + "MI_Kit_Galvanized", "Seal": KIT + "MI_Kit_DarkSteel",
               "Guide": D_MAT + "/MI_Transit_Guide_Cyan"}
SOUNDS = ["SW_Transit_Departure", "SW_Transit_Arrival"]
log = []

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v): return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]
def world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

def ensure_dirs():
    for d in (ROOT, D_MESH, D_MAT, D_AUD):
        if not EAL.does_directory_exist(d):
            EAL.make_directory(d)

def import_file(path, dest, name):
    t = unreal.AssetImportTask()
    t.filename = path; t.destination_path = dest; t.destination_name = name
    t.automated = True; t.replace_existing = True; t.save = False
    AT.import_asset_tasks([t])
    return list(t.imported_object_paths)

# --------------------------------------------------------------------------------------------- assets
def do_assets():
    ensure_dirs()
    before = set(EAL.list_assets(D_MESH, recursive=True, include_folder=False))
    log.append(("import", import_file(os.path.join(SRC, "SM_AOS_TransitShaft.obj"), D_MESH, "SM_AOS_TransitShaft")))
    for extra in sorted(set(EAL.list_assets(D_MESH, recursive=True, include_folder=False)) - before):
        if str(EAL.find_asset_data(extra).asset_class_path.asset_name) != "StaticMesh":
            EAL.delete_asset(extra)   # Interchange placeholder materials: slots are reassigned below
    for s in SOUNDS:
        log.append(("import", import_file(os.path.join(SRC, s + ".wav"), D_AUD, s)))
    parent = EAL.load_asset(HERO); mel = unreal.MaterialEditingLibrary
    for name, (base, met, rough, emi, inten) in MI_SPECS.items():
        path = D_MAT + "/" + name
        mi = EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name, D_MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, parent)
        mel.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(base[0], base[1], base[2], 1))
        mel.set_material_instance_vector_parameter_value(mi, "EmissiveColor", srgb(emi))
        mel.set_material_instance_scalar_parameter_value(mi, "Metallic", met)
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        mel.set_material_instance_scalar_parameter_value(mi, "EmissiveIntensity", inten)
        mel.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
    mesh = EAL.load_asset(D_MESH + "/SM_AOS_TransitShaft")
    for i, sm in enumerate(list(mesh.static_materials)):
        slot = str(sm.material_slot_name)
        key = next((k for k in SHAFT_SLOTS if slot == k or slot.startswith(k) or slot.endswith(k)), None)
        if key:
            mesh.set_material(i, EAL.load_asset(SHAFT_SLOTS[key]))
        log.append(("slot", i, slot, key))
    sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    sms.remove_collisions(mesh)
    bs = mesh.get_editor_property("body_setup")
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)  # hollow tube, static only
    ns = mesh.get_editor_property("nanite_settings"); ns.enabled = False; mesh.set_editor_property("nanite_settings", ns)
    EAL.save_loaded_asset(mesh)
    for s in SOUNDS:
        sw = EAL.load_asset(D_AUD + "/" + s)
        if sw: EAL.save_loaded_asset(sw)
    b = mesh.get_bounding_box()
    return {"shaft_bounds": [vl(b.min), vl(b.max)], "slots": [str(m.material_slot_name) for m in mesh.static_materials], "log": log}

# --------------------------------------------------------------------------------------------- blueprint
def station_class():
    return unreal.load_class(None, "/Script/AOS_DK.AOSTeleportStation")

def do_blueprint():
    ensure_dirs()
    parent = station_class()
    if not parent:
        return {"error": "native class AOSTeleportStation not loaded (build the module first)"}
    if EAL.does_asset_exist(BP_PATH):
        bp = EAL.load_asset(BP_PATH)
    else:
        f = unreal.BlueprintFactory(); f.set_editor_property("parent_class", parent)
        bp = AT.create_asset("BP_TeleportStation", ROOT, unreal.Blueprint, f)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = unreal.get_default_object(EAL.load_blueprint_class(BP_PATH))
    frame = cdo.get_editor_property("portal_frame")
    lock = EAL.load_asset(SOMALOCK)
    frame.set_editor_property("static_mesh", lock)
    ov = [None] * len(lock.static_materials)
    for i, m in enumerate(lock.static_materials):
        if "Status" in str(m.material_slot_name):
            ov[i] = EAL.load_asset(D_MAT + "/MI_Transit_Status_Cyan")
    frame.set_editor_property("override_materials", ov)
    cdo.get_editor_property("shaft_mesh").set_editor_property("static_mesh", EAL.load_asset(D_MESH + "/SM_AOS_TransitShaft"))
    cdo.set_editor_property("departure_sound", EAL.load_asset(D_AUD + "/SW_Transit_Departure"))
    cdo.set_editor_property("arrival_sound", EAL.load_asset(D_AUD + "/SW_Transit_Arrival"))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)
    return {"bp": bp.get_path_name(), "frame": frame.static_mesh.get_path_name(),
            "overrides": [o.get_path_name() if o else None for o in frame.get_editor_property("override_materials")]}

# --------------------------------------------------------------------------------------------- deploy
def find_label(label):
    return next((a for a in EAS.get_all_level_actors() if a.get_actor_label() == label), None)

def do_deploy():
    notes = resolve_stations()
    removed = []
    for a in EAS.get_all_level_actors():
        if a.actor_has_tag(TAG):
            removed.append(a.get_actor_label()); EAS.destroy_actor(a)
    cls = EAL.load_blueprint_class(BP_PATH)
    spawned = {}
    for key, s in STATIONS.items():
        a = EAS.spawn_actor_from_class(cls, V(*s["origin"]), unreal.Rotator(0.0, 0.0, s["yaw"]))  # (roll, pitch, yaw)
        a.set_actor_label(s["label"])
        a.set_folder_path(FOLDER)
        a.set_editor_property("station_name", s["name"])
        a.set_editor_property("entry_direction", getattr(unreal.AOSTransitDirection, s["dir"]))
        if "trigger_half_width" in s:
            a.set_editor_property("trigger_half_width", s["trigger_half_width"])
        # exact shaft alignment: lens offset of the frame + measured exit face -> ApplyLayout puts the shaft mouth there
        a.set_editor_property("auto_layout", True)
        a.set_editor_property("frame_lens_offset", V(0.0, LENS_Y, LENS_Z))
        by, bz, br = measure_bore(a)
        a.set_editor_property("frame_bore_center", V(0.0, by, bz))
        a.set_editor_property("frame_bore_radius", br)
        a.set_editor_property("shaft_outer_radius", measure_shaft_outer(a))
        a.set_editor_property("frame_back_face", measure_exit_face(a, by, bz, br))
        a.tags = [unreal.Name(TAG), unreal.Name("AOS_StationID=ETS-" + key), unreal.Name("AOS_Zone=" + s["zone"]),
                  unreal.Name("AOS_Anchor=" + s["anchor"]), unreal.Name("AOS_Lab=4")]
        spawned[key] = a
    spawned["A"].set_editor_property("linked_station", spawned["B"])
    spawned["B"].set_editor_property("linked_station", spawned["A"])
    for key, a in spawned.items():   # re-run construction with the final properties
        a.set_actor_location(V(*STATIONS[key]["origin"]), False, False)
        a.rerun_construction_scripts() if hasattr(a, "rerun_construction_scripts") else None
    return {"removed": removed, "auto_orient": notes,
            "spawned": {k: [a.get_path_name(), STATIONS[k]["origin"], STATIONS[k]["yaw"]] for k, a in spawned.items()}}

def measure_bore(a):
    """Round tunnel bore of the portal frame (frame-local Y, Z centre and radius): 16 radial traces from the mesh axis against
    the frame collision at four depths inside the tunnel, averaged. This is the opening the player sees."""
    fr = comp_by_name(a, "PortalFrame")
    if not fr: return 0.0, 0.0, 410.0
    xf = fr.get_world_transform()
    pts = []
    for X in (-300.0, 0.0, 200.0, 380.0):
        for k in range(16):
            t = math.radians(k * 22.5 + 11.25)          # mid-stave (apothem) directions
            h = fr.line_trace_component(xf.transform_location(V(X, 0, 0)), xf.transform_location(V(X, 900 * math.cos(t), 900 * math.sin(t))), False, False, False)
            if h:
                p = xf.inverse_transform_location(h[0]); pts.append((p.y, p.z))
    if len(pts) < 12: return 0.0, 0.0, 410.0
    cy = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
    r = sorted(math.hypot(p[0] - cy, p[1] - cz) for p in pts)[0]          # apothem = clear radius of the bore
    return round(cy, 1), round(cz, 1), round(r, 1)

def measure_shaft_outer(a):
    """Outer wall radius of the ShaftMesh at the mouth, unscaled (traced on the mesh, divided by the current radial scale)."""
    sh = comp_by_name(a, "ShaftMesh")
    xf = sh.get_world_transform(); s = sh.get_editor_property("relative_scale3d").y or 1.0
    h = sh.line_trace_component(xf.transform_location(V(5, 0, 1000)), xf.transform_location(V(5, 0, 0)), True, False, False)
    return round(abs(xf.inverse_transform_location(h[0]).z), 1) if h else SHAFT_OUTER_R

def measure_exit_face(a, by=0.0, bz=0.0, br=410.0):
    """Exit (rear) face of the portal frame, frame-local X: traces parallel to the axis on the flange ring just outside the
    bore (R br+20 / br+60 around the bore centre) against the frame collision; the most common hit X wins."""
    fr = comp_by_name(a, "PortalFrame")
    if not fr: return FRAME_EXIT_FACE_DEFAULT
    xf = fr.get_world_transform()
    hits = []
    for R in (br + 20.0, br + 60.0):
        for k in range(12):
            t = math.radians(k * 30.0 + 15.0)
            y, z = by + R * math.cos(t), bz + R * math.sin(t)
            h = fr.line_trace_component(xf.transform_location(V(900, y, z)), xf.transform_location(V(0, y, z)), False, False, False)
            if h: hits.append(round(xf.inverse_transform_location(h[0]).x, 1))
    return max(set(hits), key=hits.count) if hits else FRAME_EXIT_FACE_DEFAULT

def check_alignment(a):
    """Shaft vs the gate's physical opening (frame-local): axis on the bore centre, 0 tilt, mouth flush, outer wall = bore radius,
    wall concentric with the bore along the tube; axial trace through the opening runs down the tube centre to the seal;
    the traversal (lens) axis with a Shell-sized probe clears the leaf, the frame and the tube walls."""
    fr, sh = comp_by_name(a, "PortalFrame"), comp_by_name(a, "ShaftMesh")
    fx = fr.get_world_transform()
    loc = lambda v: fx.inverse_transform_location(v)
    by, bz, br = measure_bore(a)
    face = measure_exit_face(a, by, bz, br)
    sp = loc(sh.get_world_location())
    rel_rot = unreal.MathLibrary.normalized_delta_rotator(sh.get_world_rotation(), fr.get_world_rotation())
    sc = sh.get_editor_property("relative_scale3d")
    inner = SHAFT_INNER_R * sc.y
    radii = {}
    for x in (face + 50.0, face + SHAFT_LEN * 0.5 + 25.0, face + SHAFT_LEN - 75.0):
        rr = []
        for k in range(8):
            t = math.radians(k * 45.0 + 7.5)          # mid-face, clear of the 4 guide strips
            h = None
            for dt in (0.0, 0.03, -0.03):              # a ray exactly on a triangle edge can slip through: nudge ~1.7 deg
                h = sh.line_trace_component(fx.transform_location(V(x, by, bz)), fx.transform_location(V(x, by + 900 * math.cos(t + dt), bz + 900 * math.sin(t + dt))), True, False, False)
                if h: break
            if h:
                p = loc(h[0]); rr.append(round(math.hypot(p.y - by, p.z - bz), 2))
            else:
                rr.append(None)
        radii["x%d" % round(x)] = rr
    outer = []
    for k in range(4):
        t = math.radians(k * 90.0 + 7.5)
        h = sh.line_trace_component(fx.transform_location(V(face + 5, by + 1200 * math.cos(t), bz + 1200 * math.sin(t))), fx.transform_location(V(face + 5, by, bz)), True, False, False)
        outer.append(round(math.hypot(loc(h[0]).y - by, loc(h[0]).z - bz), 2) if h else None)
    mouth = sh.line_trace_component(fx.transform_location(V(0, by + inner + 15, bz)), fx.transform_location(V(900, by + inner + 15, bz)), True, False, False)
    mouth_x = round(loc(mouth[0]).x, 2) if mouth else None
    def axis_trace(y, z):
        a0, a1 = fx.transform_location(V(-1500, y, z)), fx.transform_location(V(face + SHAFT_LEN + 200, y, z))
        h = unreal.SystemLibrary.line_trace_single_for_objects(world(), a0, a1, [OT_STATIC, OT_PHYS], True, water(), unreal.DrawDebugTrace.NONE, True)
        d = hit_info(h)
        if d: d["x_frame_local"] = round(loc(h.to_tuple()[4]).x, 1)
        return d
    def probe(y, z, r, x0, x1):
        return hit_info(unreal.SystemLibrary.sphere_trace_single_for_objects(world(), fx.transform_location(V(x0, y, z)), fx.transform_location(V(x1, y, z)),
                        r, [OT_STATIC, OT_PHYS], True, water(), unreal.DrawDebugTrace.NONE, True))
    rv = lambda r_: [round(v, 4) for v in (r_.pitch, r_.yaw, r_.roll)]
    vl = lambda v, n=2: [round(v.x, n), round(v.y, n), round(v.z, n)]
    r = {"bore_measured": {"centre_yz": [by, bz], "radius": br}, "frame_exit_face_x": face,
         "shaft_rel_to_frame": {"loc": [round(sp.x, 2), round(sp.y, 2), round(sp.z, 2)], "rot_pyr": rv(rel_rot), "scale": vl(sc, 4)},
         "shaft_rel_to_actor": {"loc": vl(sh.get_editor_property("relative_location"), 2), "rot_pyr": rv(sh.get_editor_property("relative_rotation")), "scale": vl(sc, 4)},
         "frame_rel_to_actor": {"loc": vl(fr.get_editor_property("relative_location"), 2), "rot_pyr": rv(fr.get_editor_property("relative_rotation"))},
         "tube_mouth_x": mouth_x, "mouth_gap_cm": round(mouth_x - face, 2) if mouth_x is not None else None,
         "tube_outer_r_at_mouth": outer, "tube_inner_r_about_bore_axis": radii, "tube_inner_r_expected": round(inner, 2),
         "bore_axis_trace_first_hit": axis_trace(by, bz),
         # fat probe from behind the jammed leaf (X -430) down the whole tube: frame tunnel + tube walls never touched
         "bore_axis_probe_hit": probe(by, bz, inner - 30.0, 0.0, face + SHAFT_LEN - inner - 60.0),
         "lens_axis_trace_first_hit": axis_trace(LENS_Y, LENS_Z),
         "lens_axis_shell_probe_hit": probe(LENS_Y, LENS_Z, SHELL_HALF_DIAG, -1500.0, face + SHAFT_LEN - SHELL_HALF_DIAG - 60.0)}
    fails = []
    if abs(sp.y - by) > ALIGN_TOL_CM or abs(sp.z - bz) > ALIGN_TOL_CM: fails.append("shaft axis off the bore centre")
    if abs(sp.x - face) > ALIGN_TOL_CM or r["mouth_gap_cm"] is None or abs(r["mouth_gap_cm"]) > ALIGN_TOL_CM: fails.append("mouth not flush")
    if max(abs(rel_rot.pitch), abs(rel_rot.yaw), abs(rel_rot.roll)) > ALIGN_TOL_DEG: fails.append("shaft tilted against the bore axis")
    if any(v is None or abs(v - br) > 1.0 for v in outer): fails.append("tube outer wall != bore radius")
    if any(v is None or abs(v - inner) > 1.0 for rr in radii.values() for v in rr): fails.append("tube not concentric with the bore")
    for key in ("bore_axis_trace_first_hit", "lens_axis_trace_first_hit"):
        h = r[key]
        if not h or h["comp"] != "ShaftMesh" or h["x_frame_local"] < face + SHAFT_LEN - 100: fails.append(key + ": clips before the seal")
    if r["bore_axis_probe_hit"]: fails.append("bore-axis probe touches the tube / frame")
    if r["lens_axis_shell_probe_hit"]: fails.append("traversal (lens) axis probe touches geometry")
    r["fails"] = fails
    return r

# --------------------------------------------------------------------------------------------- verify
_WATER = None
def water():
    """Actors the clearance sweeps ignore: water query volumes, character-only BlockingVolumes (ignore PhysicsBody,
    so they never stop the Shell) and the parked Shell itself (it sits in A's approach lane at the berth)."""
    global _WATER
    if _WATER is None:
        _WATER = []
        for a in EAS.get_all_level_actors():
            cn = a.get_class().get_name()
            if cn in ("WaterBodyOcean", "WaterBodyLake", "WaterBodyRiver", "WaterBodyCustom", "WaterZone") or a.get_actor_label() == SHELL_LABEL:
                _WATER.append(a)
            elif cn == "BlockingVolume":
                b = a.get_component_by_class(unreal.BrushComponent)
                if b and en(b.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY)) == "ECR_IGNORE":
                    _WATER.append(a)
    return _WATER

def hit_info(h):
    if h is None: return None
    t = h.to_tuple()
    if not t[0] and not t[1]: return None
    return {"actor": t[9].get_actor_label() if t[9] else None, "comp": t[10].get_name() if t[10] else None, "loc": vl(t[4]), "start_pen": bool(t[1])}

def sweep_box(a, b, rot, ignore=()):
    h = unreal.SystemLibrary.box_trace_single_for_objects(world(), a, b, SHELL_HALF, rot, [OT_STATIC, OT_PHYS], False,
                                                          list(ignore) + water(), unreal.DrawDebugTrace.NONE, True)
    return hit_info(h)

def sweep_sphere(a, b, r=SHELL_R, ignore=()):
    h = unreal.SystemLibrary.sphere_trace_single_for_objects(world(), a, b, r, [OT_STATIC, OT_PHYS], False,
                                                             list(ignore) + water(), unreal.DrawDebugTrace.NONE, True)
    return hit_info(h)

def en(x):
    """Enum value -> bare name (QUERY_ONLY, ECR_OVERLAP ...)."""
    n = getattr(x, "name", None)
    return n if isinstance(n, str) else str(x).split(".")[-1].split(":")[0].strip("<> ")

def comp_by_name(a, name):
    for c in a.get_components_by_class(unreal.SceneComponent):
        if c.get_name() == name: return c
    return None

def inside_box(box, p, margin=0.0):
    xf = box.get_world_transform()
    lp = xf.inverse_transform_location(p)
    e = box.get_scaled_box_extent()
    return abs(lp.x) <= e.x + margin and abs(lp.y) <= e.y + margin and abs(lp.z) <= e.z + margin

def do_verify():
    out = {"stations": {}, "sweeps": {}, "controls": {}, "fails": []}
    st = {k: find_label(s["label"]) for k, s in STATIONS.items()}
    for k, a in st.items():
        if not a: out["fails"].append("missing station " + k)
    if out["fails"]: return out
    for k, a in st.items():
        trig = comp_by_name(a, "EntranceTrigger"); ex = comp_by_name(a, "ExitPoint")
        frame = comp_by_name(a, "PortalFrame"); shaft = comp_by_name(a, "ShaftMesh")
        linked = a.get_linked_station()
        entry = a.get_entry_vector(); exit_v = a.get_exit_velocity()
        resp = {ch: en(trig.get_collision_response_to_channel(getattr(unreal.CollisionChannel, ch)))
                for ch in ("ECC_PAWN", "ECC_PHYSICS_BODY", "ECC_VEHICLE", "ECC_WORLD_STATIC", "ECC_VISIBILITY")}
        exit_loc = ex.get_world_location(); exit_rot = ex.get_world_rotation()
        d = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "folder": str(a.get_folder_path()),
             "name": a.get_station_name(), "origin": vl(a.get_actor_location()), "yaw": round(a.get_actor_rotation().yaw, 1),
             "entry_vector": vl(entry), "exit_velocity": vl(exit_v), "linked": linked.get_actor_label() if linked else None,
             "trigger": {"center": vl(trig.get_world_location()), "extent": vl(trig.get_scaled_box_extent()),
                         "enabled": en(trig.get_collision_enabled()), "object": en(trig.get_collision_object_type()),
                         "overlap_events": trig.get_editor_property("generate_overlap_events"), "resp": resp},
             "exit": {"loc": vl(exit_loc), "rot": [round(exit_rot.pitch, 1), round(exit_rot.yaw, 1), round(exit_rot.roll, 1)],
                      "outside_trigger_with_shell_margin": not inside_box(trig, exit_loc, margin=200.0)},
             "frame": {"mesh": frame.static_mesh.get_path_name() if frame.static_mesh else None, "loc": vl(frame.get_world_location()),
                       "rot": [round(frame.get_world_rotation().pitch, 1), round(frame.get_world_rotation().yaw, 1), round(frame.get_world_rotation().roll, 1)],
                       "lens_axis_through_origin": None},
             "shaft": {"mesh": shaft.static_mesh.get_path_name() if shaft.static_mesh else None, "loc": vl(shaft.get_world_location())},
             "tags": [str(t) for t in a.tags]}
        # lens axis check: SOCKET_Nav_In / Nav_Out of the frame must lie on the entry axis through the origin
        try:
            ni, no = frame.get_socket_location("SOCKET_Nav_In"), frame.get_socket_location("SOCKET_Nav_Out")
            o = a.get_actor_location()
            def off_axis(p):
                v = p - o; along = v.dot(entry); return (v - entry * along).length(), along
            d["frame"]["lens_axis_through_origin"] = {"nav_in": [round(x, 1) for x in off_axis(ni)], "nav_out": [round(x, 1) for x in off_axis(no)]}
            if max(off_axis(ni)[0], off_axis(no)[0]) > 2.0 or off_axis(no)[1] < off_axis(ni)[1]:
                out["fails"].append(k + " lens axis misaligned")
        except Exception as e:
            d["frame"]["lens_axis_through_origin"] = "n/a: %s" % e
        out["stations"][k] = d
        if not linked or linked != st["B" if k == "A" else "A"]: out["fails"].append(k + " link")
        if d["trigger"]["enabled"] != "QUERY_ONLY" or not d["trigger"]["overlap_events"]: out["fails"].append(k + " trigger collision")
        if any(resp[c] != "ECR_OVERLAP" for c in ("ECC_PAWN", "ECC_PHYSICS_BODY", "ECC_VEHICLE")): out["fails"].append(k + " trigger responses")
        if not d["exit"]["outside_trigger_with_shell_margin"]: out["fails"].append(k + " exit inside trigger")
        if abs(exit_v.length() - 500.0) > 1.0 or exit_v.dot(entry) >= 0: out["fails"].append(k + " exit velocity")
        if str(a.get_folder_path()) != FOLDER: out["fails"].append(k + " folder")
        # --- Shell-1 clearance (static + physics bodies, water excluded) -------------------------
        rot = exit_rot
        outward = entry * -1.0
        sw = {}
        sw["exit_spawn_box"] = sweep_box(exit_loc, exit_loc + V(0, 0, 0.1), rot)
        sw["exit_coast_box_400"] = sweep_box(exit_loc, exit_loc + outward * 400.0, rot)
        sw["exit_coast_sphere_400"] = sweep_sphere(exit_loc, exit_loc + outward * 400.0)
        # approach: from 15 m outside the mouth down the axis to the trigger centre
        tc = trig.get_world_location()
        sw["approach_axis_sphere"] = sweep_sphere(tc + outward * 1500.0, tc)
        out["sweeps"][k] = sw
        al = check_alignment(a)
        out.setdefault("alignment", {})[k] = al
        out["fails"] += ["%s %s" % (k, f) for f in al["fails"]]
        for n, h in sw.items():
            if h: out["fails"].append("%s %s blocked by %s" % (k, n, h["actor"]))
        # controls: a sphere pushed into the frame body must hit it; a sphere sweep along the axis through the lens must hit the shaft seal
        o = a.get_actor_location()
        side = frame.get_up_vector()          # the frame body spans +-600 along the frame's up, the lens is R 248
        ctrl1 = sweep_sphere(o + outward * 1600.0 + side * 450.0, o + side * 450.0, r=60.0)
        ctrl2 = sweep_sphere(o + outward * 1000.0, o + entry * 3500.0, r=60.0)
        out["controls"][k] = {"frame_side_hit": ctrl1, "axis_hits_shaft_seal": ctrl2}
        if not ctrl1 or ctrl1["actor"] != a.get_actor_label(): out["fails"].append(k + " control frame_side")
        if not ctrl2 or ctrl2["actor"] != a.get_actor_label() or ctrl2.get("comp") != "ShaftMesh": out["fails"].append(k + " control shaft_seal")
        # footprint: frame + shaft must not interpenetrate level geometry (WorldStatic, Shell-relevant only)
        hits = set()
        for comp in (frame, shaft):
            lo, hi = comp.get_local_bounds()
            xf = comp.get_world_transform()
            pts = [xf.transform_location(V(x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
            mn = V(min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))
            mx = V(max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))
            # world AABB shrunk 30 cm (bolts / seals touching a wall face are not an interpenetration)
            ext = V(max(1.0, (mx.x - mn.x) * 0.5 - 30), max(1.0, (mx.y - mn.y) * 0.5 - 30), max(1.0, (mx.z - mn.z) * 0.5 - 30))
            for h in unreal.SystemLibrary.box_overlap_actors(world(), (mn + mx) * 0.5, ext, [OT_STATIC], None, [a] + water()) or []:
                hits.add(h.get_actor_label())
        d["footprint_overlaps"] = sorted(hits)
        if hits: out["fails"].append("%s footprint overlaps %s" % (k, sorted(hits)))
    A, B = st["A"].get_actor_location(), st["B"].get_actor_location()
    ea, eb = comp_by_name(st["A"], "ExitPoint").get_world_location(), comp_by_name(st["B"], "ExitPoint").get_world_location()
    out["separation"] = {"origins_linear_m": round((A - B).length() / 100.0, 1), "origins_vertical_m": round(abs(A.z - B.z) / 100.0, 1),
                         "exits_linear_m": round((ea - eb).length() / 100.0, 1)}
    if (A - B).length() < 20000.0: out["fails"].append("separation < 200 m")
    # rapid-test reach: parked Shell -> A trigger face, and A in the start view
    shell = find_label(SHELL_LABEL)
    if shell:
        trA = comp_by_name(st["A"], "EntranceTrigger")
        sp, sf = shell.get_actor_location(), shell.get_actor_forward_vector()
        face = trA.get_world_location() - st["A"].get_entry_vector() * (TRIGGER_DEPTH * 0.5)
        cam = shell.get_editor_property("fp_camera").get_world_location()
        to_a = st["A"].get_actor_location() + V(0, 0, 450) - cam   # frame rim, 4.5 m above the lens
        to_a_n = unreal.Vector(to_a.x, to_a.y, to_a.z); to_a_n.normalize()
        out["rapid_test"] = {"nose_to_trigger_m": round(((face - sp).dot(sf) - 200.0) / 100.0, 1),
                             "trigger_lateral_offset_m": round(((face - sp) - sf * (face - sp).dot(sf)).length() / 100.0, 2),
                             "rim_angle_from_view_deg": round(math.degrees(math.acos(max(-1.0, min(1.0, to_a_n.dot(sf))))), 1),
                             "rim_line_of_sight": sweep_sphere(cam, cam + to_a * 0.97, r=5.0, ignore=[st["A"]])}
        if out["rapid_test"]["nose_to_trigger_m"] > 30.0: out["fails"].append("A too far from the berth")
        if out["rapid_test"]["rim_line_of_sight"]: out["fails"].append("A not visible from the berth")
    with open(os.path.join(PROJ, "Saved", "Teleport_verify.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return out

def do_save():
    ok = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    return {"saved": ok, "dirty_after": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}

result = {}
if MODE in ("assets", "all"): result["assets"] = do_assets()
if MODE in ("blueprint", "all"): result["blueprint"] = do_blueprint()
if MODE in ("deploy", "all"): result["deploy"] = do_deploy()
if MODE in ("verify", "all"): result["verify"] = do_verify()
if MODE in ("save", "all"): result["save"] = do_save()
