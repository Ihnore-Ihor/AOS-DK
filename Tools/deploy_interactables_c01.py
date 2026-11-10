"""AOS-DK Lab 3 - deploy the Interactables suite into Lvl_FirstPerson (Cluster C-01 + D-1 conduit + Socket rim).
Usage (MCP execute_python):
    g = {"DI_MODE": "deploy" | "verify" | "save" | "all"}
    exec(open(r"<proj>/Tools/deploy_interactables_c01.py", encoding="utf-8").read(), g); result = g["result"]
deploy : removes the legacy TowerA_Wall (transform/mesh backed up to Saved/TowerA_Wall_removed.json),
         clears previous AOS_Interactable actors, spawns the suite with floor traces, folder Environment/Interactables.
verify : config read-back, static interpenetration, Shell-1 route sweeps + controls -> Saved/Interactables_verify.json
save   : saves the level (OFPA external actor packages included)."""
import json, math, os
import unreal

MODE = globals().get("DI_MODE", "all")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
BP = "/Game/AOS_DK_Game/Gameplay/Interactables/"
FOLDER = "Environment/Interactables"
TAG = "AOS_Interactable"
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WORLD = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
OT_STATIC = unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1      # WorldStatic
OT_PHYS = unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY4        # PhysicsBody
SHELL_HALF = unreal.Vector(200, 100, 100)                  # Shell-1 box 400 x 200 x 200
SHELL_R = 245.0                                            # bounding sphere (C-01 report)

# label, blueprint, (x, y), z-mode, z value, yaw, room / zone
#  z-mode "floor": z = traced floor top + value (value = pivot height above the floor)
#  z-mode "abs"  : z = value
PLACEMENTS = [
    ("IA_CargoPod_R4",         "BP_Phys_CargoPod",          (-47450, 22050), "floor", 120,  90, "A03_R4", (-47450, 22050, -9200)),
    ("IA_CargoPod_D1_A",       "BP_Phys_CargoPod",          ( 24700,  -300), "floor", 120,   0, "D1_Seg_01", (24700, -300, -92200)),
    ("IA_CargoPod_D1_B",       "BP_Phys_CargoPod",          ( 25350,   320), "floor", 120,   7, "D1_Seg_01", (25350, 320, -92200)),
    ("IA_Drum_R3_A",           "BP_Phys_BuoyantDrum",       (-51300, 25700), "abs",  -8600,  0, "A03_R3", None),
    ("IA_Drum_R3_B",           "BP_Phys_BuoyantDrum",       (-50500, 26300), "abs",  -8450, 35, "A03_R3", None),
    ("IA_Drum_Socket_A",       "BP_Phys_BuoyantDrum",       (-59300,   700), "abs",    -25,  0, "Socket_Rim", None),
    ("IA_Drum_Socket_B",       "BP_Phys_BuoyantDrum",       (-59650,  -450), "abs",    -25, 50, "Socket_Rim", None),
    ("IA_Drum_Socket_C",       "BP_Phys_BuoyantDrum",       (-58900,  -100), "abs",    -25, 80, "Socket_Rim", None),
    ("IA_Bulkhead_R1",         "BP_Obstacle_Bulkhead",      (-52350, 22350), "floor",    0,  0, "A03_R1", (-52350, 22350, -8600)),
    ("IA_CableTangle_K1",      "BP_Obstacle_CableTangle",   (-50200, 21035), "floor",  300,  0, "A03_K1", (-50200, 21035, -9300)),
    ("IA_EnergyCell_R5_A",     "BP_Pickup_EnergyCell",      (-48050, 22250), "floor",  260,  0, "A03_R5", (-48050, 22250, -5400)),
    ("IA_EnergyCell_R5_B",     "BP_Pickup_EnergyCell",      (-46350, 22150), "floor",  260,  0, "A03_R5", (-46350, 22150, -5400)),
    ("IA_TorpedoMag_R6",       "BP_Pickup_TorpedoMagazine", (-46150, 24850), "floor",  220, 90, "A03_R6", (-46150, 24850, -5700)),
    ("IA_EnergyCell_R6",       "BP_Pickup_EnergyCell",      (-47400, 24900), "floor",  220,  0, "A03_R6", (-47400, 24900, -5700)),
]

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v): return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]

def hit_info(h):
    if h is None:
        return None
    t = h.to_tuple()
    # FHitResult tuple: (blocking, initial_overlap, time, distance, location, impact_point, normal, impact_normal, phys_mat, hit_actor, hit_component, ...)
    return {"actor": t[9].get_actor_label() if t[9] else None, "loc": vl(t[4]), "start_pen": bool(t[1])}

_WATER = None
def water():
    """Water body / zone actors are WorldStatic query volumes that overlap everything: excluded from every query."""
    global _WATER
    if _WATER is None:
        _WATER = [a for a in EAS.get_all_level_actors() if a.get_class().get_name() in ("WaterBodyOcean", "WaterBodyLake", "WaterBodyRiver", "WaterBodyCustom", "WaterZone")]
    return _WATER

def floor_z(start, depth=3000.0, ignore=()):
    s = V(*start); e = V(start[0], start[1], start[2] - depth)
    h = unreal.SystemLibrary.line_trace_single_for_objects(WORLD, s, e, [OT_STATIC], False, list(ignore) + water(), unreal.DrawDebugTrace.NONE, True)
    hi = hit_info(h)
    return (hi["loc"][2], hi["actor"]) if hi else (None, None)

def sweep_box(a, b, ignore=(), yaw=None, types=(OT_STATIC, OT_PHYS)):
    a, b = V(*a), V(*b)
    if yaw is None:
        d = b - a; yaw = math.degrees(math.atan2(d.y, d.x))
    h = unreal.SystemLibrary.box_trace_single_for_objects(WORLD, a, b, SHELL_HALF, unreal.Rotator(roll=0, pitch=0, yaw=yaw),
                                                          list(types), False, list(ignore) + water(), unreal.DrawDebugTrace.NONE, True)
    return hit_info(h)

def sweep_sphere(a, b, r=SHELL_R, ignore=(), types=(OT_STATIC, OT_PHYS)):
    h = unreal.SystemLibrary.sphere_trace_single_for_objects(WORLD, V(*a), V(*b), r, list(types), False, list(ignore) + water(), unreal.DrawDebugTrace.NONE, True)
    return hit_info(h)

def actors():
    return EAS.get_all_level_actors()

def find_label(label):
    return [a for a in actors() if a.get_actor_label() == label]

def interactables():
    return [a for a in actors() if any(str(t) == TAG for t in a.tags)]

# Route from the world centre side to C-01 (south of the cluster, then up the west side to the SomaLock).
ROUTE_TOWER = [(-40000, 16000, -9150), (-56500, 18500, -9150), (-56500, 22038, -9150)]

def do_deploy():
    out = {"removed": [], "spawned": [], "warnings": []}
    # --- Task 0: legacy TowerA_Wall --------------------------------------------------------
    walls = find_label("TowerA_Wall")
    if walls:
        out["tower_control_before"] = sweep_sphere(ROUTE_TOWER[0], ROUTE_TOWER[1], types=(OT_STATIC,))
    backup = []
    for w in walls:
        smc = w.static_mesh_component
        backup.append({"label": w.get_actor_label(), "folder": str(w.get_folder_path()), "class": w.get_class().get_path_name(),
                       "mesh": smc.static_mesh.get_path_name() if smc and smc.static_mesh else None,
                       "location": vl(w.get_actor_location()), "rotation": [w.get_actor_rotation().roll, w.get_actor_rotation().pitch, w.get_actor_rotation().yaw],
                       "scale": vl(w.get_actor_scale3d()), "profile": str(smc.get_collision_profile_name()) if smc else None})
        EAS.destroy_actor(w)
        out["removed"].append(backup[-1]["label"])
    if backup:
        with open(os.path.join(PROJ, "Saved", "TowerA_Wall_removed.json"), "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2)
    # --- idempotence ---------------------------------------------------------------------------
    for a in interactables():
        EAS.destroy_actor(a)
    # --- spawn -----------------------------------------------------------------------------------
    for (label, bp, (x, y), zmode, zval, yaw, zone, trace_from) in PLACEMENTS:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(BP + bp)
        if not cls:
            out["warnings"].append("missing class " + bp); continue
        if zmode == "floor":
            fz, factor = floor_z(trace_from)
            if fz is None:
                out["warnings"].append("no floor under " + label); continue
            z = fz + zval
        else:
            fz, factor = None, None
            z = zval
        a = EAS.spawn_actor_from_class(cls, V(x, y, z), unreal.Rotator(roll=0, pitch=0, yaw=yaw))
        a.set_actor_label(label)
        a.set_folder_path(FOLDER)
        tags = list(a.tags) + [unreal.Name(TAG), unreal.Name("AOS_InteractableID=" + label), unreal.Name("AOS_Zone=" + zone),
                               unreal.Name("AOS_Lab=3")]
        if zone.startswith("A03"):
            tags.append(unreal.Name("AOS_Cluster=C-01"))
        a.tags = tags
        out["spawned"].append({"label": label, "bp": bp, "loc": vl(a.get_actor_location()), "yaw": yaw, "floor": fz, "floor_actor": factor})
    return out

def do_verify():
    out = {"actors": {}, "interpenetration": {}, "routes": {}, "controls": {}, "fails": []}
    ia = {a.get_actor_label(): a for a in interactables()}
    out["count"] = len(ia)
    out["tower_wall_present"] = len(find_label("TowerA_Wall"))
    for label, a in sorted(ia.items()):
        root = a.root_component
        d = {"class": a.get_class().get_name(), "folder": str(a.get_folder_path()), "loc": vl(a.get_actor_location()),
             "profile": str(root.get_collision_profile_name()), "mobility": str(root.mobility).split(".")[-1].rstrip(">").split(":")[0]}
        bi = root.get_editor_property("body_instance") if isinstance(root, unreal.PrimitiveComponent) else None
        if bi:
            d["simulate"] = bi.get_editor_property("simulate_physics")
            d["collision"] = str(root.get_collision_enabled()).split(".")[-1].split(":")[0]
        for c in a.get_components_by_class(unreal.ActorComponent):
            if c.get_class().get_name() == "AOSFluidPhysicsComponent":
                m = c.get_editor_property("mass_override_kg"); immune = c.get_editor_property("wave_immune_mass_kg"); ref = c.get_editor_property("wave_reference_mass_kg")
                s = 0.0 if m >= immune else (1 - (lambda t: t * t * (3 - 2 * t))(max(0.0, min(1.0, (m - 0.5 * immune) / (0.5 * immune)))))
                d.update(mass=m, B=round(c.get_editor_property("buoyancy_factor"), 3), C_m=round(c.get_editor_property("wave_influence_scale") * min(1.0, ref / m) * s, 3),
                         submerged_share=(round(1.0 / c.get_editor_property("buoyancy_factor"), 3) if c.get_editor_property("buoyancy_factor") > 1 else "sinks"))
        out["actors"][label] = d
        # static interpenetration: shrink the actor bounds by 4 cm and look for WorldStatic overlaps
        o, e = a.get_actor_bounds(True)
        ext = V(max(e.x - 4, 1), max(e.y - 4, 1), max(e.z - 4, 1))
        hits = unreal.SystemLibrary.box_overlap_actors(WORLD, o, ext, [OT_STATIC], None, [a] + water())
        hits = [h.get_actor_label() for h in (hits or []) if not any(str(t) == TAG for t in h.tags)]
        if d["class"].startswith(("BP_Phys", "BP_Obstacle_Bulkhead")) and hits:
            # bounds-box test is conservative for the drum/pod (round/skid shapes) - confirm with a component sweep
            out["fails"].append("interpenetration " + label + ": " + ",".join(hits))
        out["interpenetration"][label] = hits
    ign = []
    # --- Shell-1 routes (box + sphere), static + physics bodies -----------------------------------
    R1_IN = (-53250, 22038, -9150)
    routes = {
        "towercentre_to_somalock_leg1": (ROUTE_TOWER[0], ROUTE_TOWER[1]),
        "towercentre_to_somalock_leg2": (ROUTE_TOWER[1], ROUTE_TOWER[2]),
        "R1_somalock_to_southgap": (R1_IN, (-52950, 21150, -9300)),
        "R1_southgap_through": ((-52950, 21150, -9300), (-51800, 21150, -9300)),
        "R1_southgap_to_archR2": ((-51800, 21150, -9300), (-51450, 23000, -9300)),
        "R1_southgap_to_K1": ((-51800, 21150, -9300), (-51400, 21035, -9450)),
        "R1_somalock_to_northgap": (R1_IN, (-52950, 23470, -9300)),
        "R1_northgap_through": ((-52950, 23470, -9300), (-51850, 23470, -9300)),
        "R1_northgap_to_archR2": ((-51850, 23470, -9300), (-51450, 23050, -9300)),
        "K1_full_length": ((-51300, 21035, -9450), (-48400, 21035, -9450)),
        "R4_K1_mouth_to_south": ((-48400, 21035, -9450), (-47300, 20950, -9450)),
        "R4_DS_mouth_to_east": ((-48200, 22300, -9450), (-47250, 22700, -9450)),
        "R2_to_R5_arch_to_R6_door": ((-48700, 23000, -5750), (-46800, 23650, -5946)),
        "R5_to_R6": ((-46800, 23650, -5946), (-46800, 24750, -5946)),
        "D1_top_lane": ((23500, 0, -87216), (30500, 0, -87216)),
    }
    for name, (a, b) in routes.items():
        hb = sweep_box(a, b); hs = sweep_sphere(a, b)
        out["routes"][name] = {"box": hb, "sphere": hs}
        if hb or hs:
            out["fails"].append("route " + name + " blocked by " + str((hb or hs)["actor"]))
    controls = {
        "R1_direct_somalock_to_archR2_hits_bulkhead": (R1_IN, (-51450, 23000, -9300), "IA_Bulkhead_R1"),
        "R1_over_bulkhead_hits": ((-52800, 22350, -8700), (-51900, 22350, -8700), "IA_Bulkhead_R1"),
        "R4_push_line_hits_pod": ((-48300, 22050, -9600), (-47000, 22050, -9600), "IA_CargoPod_R4"),
        "D1_floor_line_hits_pod": ((23500, -300, -93640), (25000, -300, -93640), "IA_CargoPod_D1_A"),
    }
    for name, (a, b, want) in controls.items():
        h = sweep_sphere(a, b, r=120.0) if "over" not in name else sweep_box(a, b)
        ok = bool(h) and h["actor"] == want
        out["controls"][name] = {"hit": h, "expected": want, "ok": ok}
        if not ok:
            out["fails"].append("control " + name)
    # soft obstacle and pickups must NOT block (WorldDynamic, query-only overlap)
    t = ia.get("IA_CableTangle_K1")
    if t:
        hits = unreal.SystemLibrary.box_overlap_actors(WORLD, V(-50200, 21035, -9450), SHELL_HALF, [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2], None, [])
        out["controls"]["K1_shell_box_overlaps_tangle"] = {"overlap": [h.get_actor_label() for h in (hits or [])], "ok": "IA_CableTangle_K1" in [h.get_actor_label() for h in (hits or [])]}
        if not out["controls"]["K1_shell_box_overlaps_tangle"]["ok"]:
            out["fails"].append("control K1_shell_box_overlaps_tangle")
    # TowerA_Wall control: re-create the removed wall as a temporary actor from the backup, sweep, delete it again.
    bk = os.path.join(PROJ, "Saved", "TowerA_Wall_removed.json")
    if os.path.exists(bk) and not find_label("TowerA_Wall"):
        w = json.load(open(bk, encoding="utf-8"))[0]
        tmp = EAS.spawn_actor_from_class(unreal.StaticMeshActor, V(*w["location"]), unreal.Rotator(roll=w["rotation"][0], pitch=w["rotation"][1], yaw=w["rotation"][2]))
        tmp.static_mesh_component.set_static_mesh(unreal.EditorAssetLibrary.load_asset(w["mesh"]))
        tmp.static_mesh_component.set_collision_profile_name(w["profile"])
        tmp.set_actor_scale3d(V(*w["scale"]))
        h = sweep_sphere(ROUTE_TOWER[0], ROUTE_TOWER[1])
        EAS.destroy_actor(tmp)
        ok = bool(h)
        out["controls"]["legacy_TowerA_Wall_would_block_route"] = {"hit": h, "ok": ok}
        if not ok:
            out["fails"].append("control legacy_TowerA_Wall_would_block_route")
    out["result"] = "PASS" if not out["fails"] else "FAIL"
    with open(os.path.join(PROJ, "Saved", "Interactables_verify.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out

def do_save():
    ok = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, False)
    return {"saved": ok, "dirty_after": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}

result = {}
if MODE in ("deploy", "all"): result["deploy"] = do_deploy()
if MODE in ("verify", "all"): result["verify"] = do_verify()
if MODE in ("save", "all"): result["save"] = do_save()
