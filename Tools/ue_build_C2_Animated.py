"""AOS-DK Lab 6 / Batch C2 - UE-native animated scene objects: 3 Breakwater gate beacons + harbour skiff on a looping Level Sequence.
Usage (MCP execute_python):
    g = {"C2_MODE": "<mode>"}; exec(open(r"<proj>/Tools/ue_build_C2_Animated.py", encoding="utf-8").read(), g); result = g["result"]
Modes:
    beacon_bp     create /Game/AOS_DK_Game/Environment/Atoll/Animations/BP_AOS_GateBeacon (parent AAOSGateBeacon), materials + light scale on the CDO
    place_beacons spawn 3 beacons on the gate-side marker masts of BW_Hulls_Short (folder Environment/Atoll/Animated, modify())
    skiff_bp      create BP_AOS_HarbourSkiff (kitbash of Atoll/Kit + engine shapes, NoCollision)
    sequence      create LS_Atoll_HarbourSkiff (120 s closed loop circle r 9700 around C, additive bob / roll / pitch section)
    place_skiff   spawn BP_AOS_HarbourSkiff + ALevelSequenceActor (AutoPlay, loop infinitely), bind, folder Environment/Atoll/Animated
    status        read back what exists
"""
import math
import unreal

MODE = globals().get("C2_MODE", "status")
ANIM_DIR = "/Game/AOS_DK_Game/Environment/Atoll/Animations"
MAT_DIR = "/Game/AOS_DK_Game/Environment/Atoll/Materials"
FOLDER = "Environment/Atoll/Animated"
TAG = "AOS_Atoll_Animated"
CENTER = (-1000.0, 700.0)
WATER_Z = 40.0
SKIFF_R = 9700.0
LOOP_S = 120.0
FPS = 30

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
at = unreal.AssetToolsHelpers.get_asset_tools()
result = {}


def mi(name):
    return unreal.load_asset("%s/%s.%s" % (MAT_DIR, name, name))


def get_or_create_bp(name, parent):
    path = "%s/%s" % (ANIM_DIR, name)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.load_asset(path), False
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", parent)
    return at.create_asset(name, ANIM_DIR, unreal.Blueprint, fac), True


def find_labels(prefix):
    return [a for a in eas.get_all_level_actors() if a.get_actor_label().startswith(prefix)]


# --------------------------------------------------------------------------------------------------------------------------------
if MODE == "beacon_bp":
    bp, created = get_or_create_bp("BP_AOS_GateBeacon", unreal.AOSGateBeacon)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property("housing_material", mi("MI_Atoll_Trim"))
    cdo.set_editor_property("lens_material", mi("MI_Atoll_Beacon"))
    cdo.set_editor_property("spot_intensity_max", float(globals().get("C2_SPOT_CD", 4000.0)))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    result = {"bp": bp.get_path_name(), "created": created, "spot_cd": cdo.get_editor_property("spot_intensity_max")}

# --------------------------------------------------------------------------------------------------------------------------------
elif MODE == "place_beacons":
    cls = unreal.EditorAssetLibrary.load_blueprint_class("%s/BP_AOS_GateBeacon" % ANIM_DIR)
    shorts = [a for a in eas.get_all_level_actors() if a.get_actor_label() == "BW_Hulls_Short"][0]
    ism = shorts.get_component_by_class(unreal.InstancedStaticMeshComponent)
    mesh_top = ism.static_mesh.get_bounds().origin.z + ism.static_mesh.get_bounds().box_extent.z   # mast beacon stub top (local Z)
    gates = [("Gate1_W", (-13000.0, 700.0)), ("Gate2_NE", (5000.0, 11092.0)), ("Gate3_SE", (5000.0, -9692.0))]
    masts = []                                                                                        # (world x, y, z, hull yaw)
    for i in range(ism.get_instance_count()):
        t = ism.get_instance_transform(i, True)
        yaw = math.radians(t.rotation.rotator().yaw)
        for lx in (-745.0, 745.0):
            ly = 610.0
            wx = t.translation.x + lx * math.cos(yaw) - ly * math.sin(yaw)
            wy = t.translation.y + lx * math.sin(yaw) + ly * math.cos(yaw)
            masts.append((wx, wy, t.translation.z + mesh_top, t.rotation.rotator().yaw))
    placed = []
    existing = {a.get_actor_label(): a for a in eas.get_all_level_actors() if a.get_actor_label().startswith("GateBeacon_")}
    for k, (nm, gm) in enumerate(gates):
        ranked = sorted(masts, key=lambda m: (m[0] - gm[0]) ** 2 + (m[1] - gm[1]) ** 2)
        gate_side = ranked[:2]                                           # the two masts flanking this gate
        m = sorted(gate_side, key=lambda q: (q[0], q[1]))[0]             # deterministic pick of one
        label = "GateBeacon_" + nm
        if label in existing:
            a = existing[label]
            a.set_actor_location(unreal.Vector(m[0], m[1], m[2]), False, False)
        else:
            a = eas.spawn_actor_from_class(cls, unreal.Vector(m[0], m[1], m[2]), unreal.Rotator(0, 0, m[3]))
            a.set_actor_label(label)
        a.modify()
        a.set_folder_path(FOLDER)
        a.tags = [TAG]
        a.set_editor_property("phase_offset_sec", [0.0, 1.33, 2.67][k])
        placed.append({"label": label, "loc": [round(m[0], 1), round(m[1], 1), round(m[2], 1)], "gate_mid": gm,
                       "dist_to_gate_mid": round(math.hypot(m[0] - gm[0], m[1] - gm[1]), 1), "other_gate_mast": [round(v, 1) for v in gate_side[1][:3]] if gate_side[0] is m else [round(v, 1) for v in gate_side[0][:3]]})
    result = {"mesh_top_z": mesh_top, "placed": placed}

# --------------------------------------------------------------------------------------------------------------------------------
elif MODE == "skiff_bp":
    KIT = "/Game/AOS_DK_Game/Environment/Atoll/Kit/"
    path = ANIM_DIR + "/BP_AOS_HarbourSkiff"
    if globals().get("C2_RECREATE") and unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    bp, created = get_or_create_bp("BP_AOS_HarbourSkiff", unreal.Actor)
    if not created:
        result = {"bp": bp.get_path_name(), "created": False, "note": "exists; pass C2_RECREATE=True to rebuild"}
    else:
        sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        _hs = sub.k2_gather_subobject_data_for_blueprint(bp)
        root_h = [h for h in _hs if isinstance(unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sub.k2_find_subobject_data_from_handle(h), False), unreal.SceneComponent)][0]
        shapes = {n: unreal.load_asset("/Engine/BasicShapes/%s.%s" % (n, n)) for n in ("Cylinder", "Cube", "Sphere")}
        node_mesh = unreal.load_asset(KIT + "SM_Path_FloatNode.SM_Path_FloatNode")
        made = []

        def add(cls, name, parent=None, loc=(0, 0, 0), rpy=(0, 0, 0), scale=(1, 1, 1)):
            p = unreal.AddNewSubobjectParams(parent_handle=parent or root_h, new_class=cls, blueprint_context=bp)
            h, fail = sub.add_new_subobject(p)
            if not unreal.SubobjectDataBlueprintFunctionLibrary.is_valid(sub.k2_find_subobject_data_from_handle(h)):
                raise RuntimeError("add_new_subobject failed: %s" % fail)
            sub.rename_subobject(h, unreal.Text(name))
            obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sub.k2_find_subobject_data_from_handle(h), False)
            obj.set_editor_property("relative_location", unreal.Vector(*loc))
            obj.set_editor_property("relative_rotation", unreal.Rotator(roll=rpy[0], pitch=rpy[1], yaw=rpy[2]))
            obj.set_editor_property("relative_scale3d", unreal.Vector(*scale))
            obj.set_mobility(unreal.ComponentMobility.MOVABLE)
            made.append(name)
            return h, obj

        def mesh(name, sm, mat, **kw):
            h, o = add(unreal.StaticMeshComponent, name, **kw)
            o.set_static_mesh(sm)
            if mat:
                o.set_material(0, mi(mat))
            o.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            o.set_cast_shadow(True)
            return h, o

        # root: scene, movable (the Level Sequence drives the actor transform; origin = waterline at hull centre)
        root_obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sub.k2_find_subobject_data_from_handle(root_h), False)
        root_obj.set_mobility(unreal.ComponentMobility.MOVABLE)
        DECK = 60.0
        # hull: 3 x 2 floating nodes (200 x 202 each, mesh spans Z -119..0) -> raft 600 x 404, draft 59, freeboard 60
        for ix, x in enumerate((-200.0, 0.0, 200.0)):
            for iy, y in enumerate((-101.0, 101.0)):
                mesh("Hull_%d%d" % (ix, iy), node_mesh, None, loc=(x, y, DECK))
        # railing: posts + top rails (engine cylinder, MI_Atoll_Trim)
        for s, side in ((-1, "P"), (1, "S")):
            for ix, x in enumerate((-280.0, -100.0, 100.0, 280.0)):
                mesh("RailPost_%s%d" % (side, ix), shapes["Cylinder"], "MI_Atoll_Trim", loc=(x, s * 190.0, DECK + 45.0), scale=(0.06, 0.06, 0.9))
            mesh("RailTop_%s" % side, shapes["Cylinder"], "MI_Atoll_Trim", loc=(0.0, s * 190.0, DECK + 88.0), rpy=(0, 90, 0), scale=(0.05, 0.05, 5.6))
        mesh("RailTop_Stern", shapes["Cylinder"], "MI_Atoll_Trim", loc=(-280.0, 0.0, DECK + 88.0), rpy=(90, 0, 0), scale=(0.05, 0.05, 3.8))
        # wheelhouse + roof
        mesh("Wheelhouse", shapes["Cube"], "MI_Atoll_Container_Teal", loc=(-190.0, 0.0, DECK + 45.0), scale=(1.4, 1.6, 0.9))
        mesh("WheelhouseRoof", shapes["Cube"], "MI_Atoll_Tin", loc=(-190.0, 0.0, DECK + 93.0), scale=(1.6, 1.8, 0.06))
        # mast, crossbar, lantern
        mesh("Mast", shapes["Cylinder"], "MI_Atoll_Pipe", loc=(60.0, 0.0, DECK + 150.0), scale=(0.08, 0.08, 3.0))
        mesh("MastBar", shapes["Cylinder"], "MI_Atoll_Pipe", loc=(60.0, 0.0, DECK + 250.0), rpy=(90, 0, 0), scale=(0.05, 0.05, 1.2))
        lh, lamp = mesh("Lantern", shapes["Sphere"], "MI_Atoll_Lumi", loc=(60.0, 0.0, DECK + 312.0), scale=(0.22, 0.22, 0.22))
        lh2, light = add(unreal.PointLightComponent, "RunningLight", parent=lh, loc=(0, 0, 0))
        light.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        light.set_editor_property("intensity", 90.0)
        light.set_editor_property("attenuation_radius", 1600.0)
        light.set_editor_property("light_color", unreal.Color(255, 190, 110, 255))
        light.set_editor_property("cast_shadows", False)
        # tyre fenders (no SM_Fender_Tyre in the project: engine cylinders, MI_Atoll_Fender), 2 per side
        for s, side in ((-1, "P"), (1, "S")):
            for ix, x in enumerate((-150.0, 150.0)):
                mesh("Fender_%s%d" % (side, ix), shapes["Cylinder"], "MI_Atoll_Fender", loc=(x, s * 214.0, DECK - 25.0), rpy=(90, 0, 0), scale=(0.5, 0.5, 0.22))
        # salvage on the bow deck
        mesh("Crate_A", shapes["Cube"], "MI_Atoll_Container_Rust", loc=(195.0, 70.0, DECK + 25.0), scale=(0.8, 0.8, 0.5))
        mesh("Crate_B", shapes["Cube"], "MI_Atoll_Container_Ochre", loc=(215.0, -60.0, DECK + 18.0), rpy=(0, 0, 25), scale=(0.6, 0.7, 0.36))
        mesh("Drum", shapes["Cylinder"], "MI_Atoll_Chassis", loc=(110.0, -120.0, DECK + 30.0), scale=(0.45, 0.45, 0.6))
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        unreal.EditorAssetLibrary.save_loaded_asset(bp)
        result = {"bp": bp.get_path_name(), "created": True, "components": made}

elif MODE == "sequence":
    # skiff actor at the sequence start pose (azimuth 0, heading = az + 90 deg, Z = ocean level)
    skiff_cls = unreal.EditorAssetLibrary.load_blueprint_class(ANIM_DIR + "/BP_AOS_HarbourSkiff")
    start = unreal.Vector(CENTER[0] + SKIFF_R, CENTER[1], WATER_Z)
    skiffs = find_labels("HarbourSkiff")
    if skiffs:
        skiff = skiffs[0]
    else:
        skiff = eas.spawn_actor_from_class(skiff_cls, start, unreal.Rotator(0, 0, 90))
        skiff.set_actor_label("HarbourSkiff")
    skiff.modify()
    skiff.set_actor_location_and_rotation(start, unreal.Rotator(0, 0, 90), False, True)
    skiff.set_folder_path(FOLDER)
    skiff.tags = [TAG]

    seq_path = ANIM_DIR + "/LS_Atoll_HarbourSkiff"
    if unreal.EditorAssetLibrary.does_asset_exist(seq_path):
        ls = unreal.load_asset(seq_path)                 # never delete a loaded sequence (ensure + editor hang): clear its bindings instead
        for b in list(ls.get_bindings()):
            b.remove()
    else:
        ls = at.create_asset("LS_Atoll_HarbourSkiff", ANIM_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    ls.set_display_rate(unreal.FrameRate(FPS, 1))
    ls.set_playback_start_seconds(0.0)
    ls.set_playback_end_seconds(LOOP_S)

    binding = ls.add_possessable(skiff)
    binding.set_display_name("HarbourSkiff") if hasattr(binding, "set_display_name") else None
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    # The key range spans -5 .. LOOP+5 s so the cubic tangents at the loop seam come from real neighbours (az(t) is 120 s periodic).
    T0, T1 = -5.0, LOOP_S + 5.0

    def chmap(sec):
        return {str(c.channel_name): c for c in sec.get_all_channels()}

    interp = unreal.MovieSceneKeyInterpolation
    base = track.add_section()
    base.set_range_seconds(T0, T1)
    ch = chmap(base)
    names = sorted(ch.keys())
    k_circle = 2.5
    n = int(round((T1 - T0) / k_circle))
    for i in range(n + 1):
        t = T0 + i * k_circle
        f = unreal.FrameNumber(int(round(t * FPS)))
        az = 2.0 * math.pi * t / LOOP_S
        ch["Location.X"].add_key(f, CENTER[0] + SKIFF_R * math.cos(az), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.AUTO)
        ch["Location.Y"].add_key(f, CENTER[1] + SKIFF_R * math.sin(az), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.AUTO)
        ch["Rotation.Z"].add_key(f, math.degrees(az) + 90.0, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.LINEAR)
    for t in (T0, T1):
        ch["Location.Z"].add_key(unreal.FrameNumber(int(round(t * FPS))), WATER_Z, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.LINEAR)
        ch["Rotation.X"].add_key(unreal.FrameNumber(int(round(t * FPS))), 0.0, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.LINEAR)
        ch["Rotation.Y"].add_key(unreal.FrameNumber(int(round(t * FPS))), 0.0, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.LINEAR)

    # additive bob / roll / pitch: whole numbers of cycles per 120 s loop so the seam is seamless
    bob = track.add_section()
    bob.set_range_seconds(T0, T1)
    bob.set_row_index(1)
    bob.set_blend_type(unreal.MovieSceneBlendType.ADDITIVE)
    cb = chmap(bob)
    cycles = {"z": (37, 12.0), "roll": (25, 3.0), "pitch": (31, 2.0)}   # period 3.243 s / 4.8 s / 3.871 s
    step = 6                                                             # frames (0.2 s)
    f0, f1 = int(round(T0 * FPS)), int(round(T1 * FPS))
    for f in range(f0, f1 + 1, step):
        t = f / float(FPS)
        for key, chn, phase in (("z", "Location.Z", 0.0), ("roll", "Rotation.X", 1.3), ("pitch", "Rotation.Y", 2.6)):
            c, amp = cycles[key]
            v = amp * math.sin(2.0 * math.pi * c * t / LOOP_S + phase)
            cb[chn].add_key(unreal.FrameNumber(f), v, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, interp.AUTO)

    unreal.EditorAssetLibrary.save_loaded_asset(ls)

    lsas = find_labels("LSA_HarbourSkiff")
    lsa = lsas[0] if lsas else eas.spawn_actor_from_class(unreal.LevelSequenceActor, unreal.Vector(CENTER[0], CENTER[1], WATER_Z))
    lsa.set_actor_label("LSA_HarbourSkiff")
    lsa.modify()
    lsa.set_sequence(ls)
    ps = lsa.get_editor_property("playback_settings")
    ps.set_editor_property("auto_play", True)
    ps.set_editor_property("loop_count", unreal.MovieSceneSequenceLoopCount(value=-1))
    props = [p for p in dir(ps) if "restore" in p.lower()]
    for p in props:
        try:
            ps.set_editor_property(p, True)
        except Exception:
            pass
    lsa.set_editor_property("playback_settings", ps)
    lsa.set_folder_path(FOLDER)
    lsa.tags = [TAG]
    result = {"ls": ls.get_path_name(), "channels": names, "keys": {k: len(c.get_keys()) for k, c in chmap(base).items() if len(c.get_keys())},
              "bob_keys": {k: len(c.get_keys()) for k, c in chmap(bob).items() if len(c.get_keys())},
              "restore_props": props, "skiff": skiff.get_path_name(), "lsa": lsa.get_path_name(),
              "bindings": [str(b.get_name()) for b in ls.get_bindings()], "sequence_set": str(lsa.get_sequence())}

elif MODE == "status":
    result = {"bp_beacon": unreal.EditorAssetLibrary.does_asset_exist(ANIM_DIR + "/BP_AOS_GateBeacon"),
              "bp_skiff": unreal.EditorAssetLibrary.does_asset_exist(ANIM_DIR + "/BP_AOS_HarbourSkiff"),
              "ls": unreal.EditorAssetLibrary.does_asset_exist(ANIM_DIR + "/LS_Atoll_HarbourSkiff"),
              "actors": [(a.get_actor_label(), a.get_class().get_name(), str(a.get_actor_location())) for a in eas.get_all_level_actors()
                         if a.get_folder_path() == FOLDER or a.get_actor_label().startswith("GateBeacon_")]}
