"""AOS-DK - PIE check of the Pontoon Atoll calm-lagoon mask (Stage 2B).
Usage (MCP execute_python):  g = {"AL_PIE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_atoll_lagoon.py", encoding="utf-8").read(), g); result = g["result"]
start: place temp actors, begin PIE + slate post-tick driver. poll: state. stop: end PIE, write Saved/Atoll2B_Verify/atoll_lagoon_pie.json. cleanup (after PIE has ended): remove the temp editor actors.
Spawns BP_Phys_BuoyantDrum inside the harbour and beyond the breakwater, samples for SAMPLE_S seconds: drum heave / tilt, fluid-component
surface height, water-plugin surface Z (TryQuery IncludeWaves via AAOSDampingPerimeter), Shell heave. Then SceneCapture2D shots in the PIE world.
"""
import json, math, os
import unreal

MODE = globals().get("AL_PIE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT = os.path.join(PROJ, "Saved", "Atoll2B_Verify")
C = (-1000.0, 700.0); WATER_Z = 40.0
SETTLE_S, SAMPLE_S = 8.0, 30.0
def P(r, az, z=WATER_Z): return unreal.Vector(C[0] + r * math.cos(math.radians(az)), C[1] + r * math.sin(math.radians(az)), z)
DRUMS = {"in_harbour_r8500_az90": (8500, 90), "in_harbour_r9500_az200": (9500, 200), "in_lagoon_r2000_az135": (2000, 135),
         "out_r16500_az120": (16500, 120), "out_r18000_az0": (18000, 0)}
QUERY = {"centre": (0, 0), "city_r5000_az20": (5000, 20), "harbour_r9300_az270": (9300, 270), "gate180_r12120": (12120, 180),
         "out_r16000_az0": (16000, 0), "out_r16000_az135": (16000, 135)}
SHOTS = globals().get("AL_SHOTS", ["02", "03", "04", "05", "06", "07", "08", "09", "10"])
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()

TAG = "TMP_Atoll2B_PIE"
EAS = lambda: unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def spawn_editor(cls, loc, rot, label):
    """Temp actors are placed in the editor world (PIE duplicates them); never saved, removed by 'stop'."""
    a = EAS().spawn_actor_from_class(cls, loc, rot or unreal.Rotator(0, 0, 0))
    a.set_actor_label(label); a.tags = [TAG, label]
    a.set_editor_property("is_spatially_loaded", False)
    return a

def tagged(w, cls):
    return {str(a.tags[1]): a for a in unreal.GameplayStatics.get_all_actors_of_class(w, cls) if len(a.tags) > 1 and str(a.tags[0]) == TAG}

def setup_editor(drum_cls):
    ns = {"MODE": "none"}
    p = os.path.join(PROJ, "Tools", "ue_build_AtollLagoon.py")
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
    V = lambda t: unreal.Vector(float(t[0]), float(t[1]), float(t[2]))
    for k, (r, az) in DRUMS.items():
        spawn_editor(drum_cls, P(r, az, WATER_Z + 30.0), None, "drum:" + k)
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    rts = {}
    for name, v in ns["VIEWS"].items():
        if not any(name.startswith(x) for x in SHOTS): continue
        rt = unreal.RenderingLibrary.create_render_target2d(w, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        cam, look = V(v["cam"]), V(v["at"])
        cap = spawn_editor(unreal.SceneCapture2D, cam, unreal.MathLibrary.find_look_at_rotation(cam, look), "cap:" + name)
        cc = cap.capture_component2d
        cc.texture_target = rt; cc.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
        cc.set_editor_property("capture_every_frame", False); cc.set_editor_property("capture_on_movement", False)
        off = ("Fog", "VolumetricFog", "Cloud") + (() if v["cam"][2] < 0 else ("PostProcessMaterial",))
        cc.set_editor_property("show_flag_settings", [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in off])
        pp = unreal.PostProcessSettings()
        for k_, v_ in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL), ("override_auto_exposure_bias", True),
                       ("auto_exposure_bias", float(v.get("ev", 0.0))), ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", False)):
            pp.set_editor_property(k_, v_)
        cc.set_editor_property("post_process_settings", pp); cc.set_editor_property("post_process_blend_weight", 1.0); cc.set_editor_property("fov_angle", float(v["fov"]))
        rts[name] = rt
    return rts

def cleanup_editor():
    n = 0
    for a in EAS().get_all_level_actors():
        if len(a.tags) > 0 and str(a.tags[0]) == TAG:
            EAS().destroy_actor(a); n += 1
    return n

def rng(S, key, v):
    r = S["ranges"].setdefault(key, [v, v]); r[0] = min(r[0], v); r[1] = max(r[1], v)

def capture(w, S):
    done = []
    for label, cap in tagged(w, unreal.SceneCapture2D).items():
        name = label.split(":", 1)[1]
        cc = cap.capture_component2d
        rt = cc.texture_target
        cc.capture_scene(); cc.capture_scene()
        f = os.path.join(OUT, "pie_" + name + ".png")
        if os.path.exists(f): os.remove(f)
        unreal.RenderingLibrary.export_render_target(w, rt, OUT, "pie_" + name + ".png"); done.append(name)
    S["shots"] = sorted(done)

def tick(dt):
    S = unreal._al
    if S.get("busy") or S["state"] == "done": return
    try:
        w = gw()
        if w is None: return
        S["t"] += dt
        if S["state"] == "wait":
            if S["t"] > 4.0:
                per = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.AOSDampingPerimeter)
                S["per"] = per[0] if per else None
                S["drums"] = {k.split(":", 1)[1]: a for k, a in tagged(w, unreal.Actor).items() if k.startswith("drum:")}
                shells = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Pawn) if "Shell" in a.get_class().get_name()]
                S["shell"] = shells[0] if shells else None
                d0 = list(S["drums"].values())[0]
                fc = d0.get_component_by_class(unreal.AOSFluidPhysicsComponent)
                S["drum_info"] = {"class": d0.get_class().get_name(), "mass_kg": round(fc.get_effective_mass(), 1), "coupling": round(fc.get_wave_coupling(), 3),
                                  "ocean_z": fc.get_ocean_surface_z(), "mask_on": fc.get_editor_property("apply_atoll_wave_mask")}
                S["state"] = "settle"; S["t0"] = S["t"]
        elif S["state"] == "settle":
            if S["t"] - S["t0"] > SETTLE_S: S["state"] = "sample"; S["t0"] = S["t"]; S["frames"] = 0
        elif S["state"] == "sample":
            S["frames"] += 1
            for k, d in S["drums"].items():
                L = d.get_actor_location(); up = d.get_actor_up_vector()
                rng(S, "drum_z:" + k, L.z)
                rng(S, "drum_tilt_deg:" + k, math.degrees(math.acos(max(-1.0, min(1.0, up.z)))))
                rng(S, "drum_xy_drift:" + k, math.hypot(L.x - P(*DRUMS[k]).x, L.y - P(*DRUMS[k]).y))
                fc = d.get_component_by_class(unreal.AOSFluidPhysicsComponent)
                rng(S, "fluid_surface_dz:" + k, fc.get_wave_height_at(L) - fc.get_ocean_surface_z())
            if S["per"]:
                for k, (r, az) in QUERY.items():
                    rng(S, "water_query_dz:" + k, S["per"].query_water_surface_z(P(r, az)) - WATER_Z)
            if S["shell"]:
                L = S["shell"].get_actor_location(); rng(S, "shell_z", L.z)
                fc = S["shell"].get_component_by_class(unreal.AOSFluidPhysicsComponent)
                if fc: rng(S, "shell_fluid_surface_dz", fc.get_wave_height_at(L) - fc.get_ocean_surface_z())
            if S["t"] - S["t0"] > SAMPLE_S:
                S["busy"] = True
                try: capture(w, S)
                finally: S["busy"] = False
                S["state"] = "done"
    except Exception as e:
        import traceback
        S["error"] = traceback.format_exc()[-700:]; S["state"] = "done"

def public(S):
    o = {k: v for k, v in S.items() if k in ("state", "t", "frames", "error", "shots", "drum_info", "removed_temp_actors")}
    o["ranges"] = {k: [round(v[0], 3), round(v[1], 3), round(v[1] - v[0], 3)] for k, v in sorted(S.get("ranges", {}).items())}
    return o

if MODE == "start":
    if hasattr(unreal, "_al") and unreal._al.get("handle") is not None:
        try: unreal.unregister_slate_post_tick_callback(unreal._al["handle"])
        except Exception: pass
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    bp = [str(a.package_name) for a in ar.get_assets_by_path("/Game/AOS_DK_Game", recursive=True) if str(a.asset_name) == "BP_Phys_BuoyantDrum"]
    unreal._al = {"state": "wait", "t": 0.0, "busy": False, "handle": None, "ranges": {}, "drum_bp": bp[0]}
    os.makedirs(OUT, exist_ok=True)
    cleanup_editor()
    unreal._al["rts"] = setup_editor(unreal.EditorAssetLibrary.load_blueprint_class(bp[0]))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._al["handle"] = unreal.register_slate_post_tick_callback(tick)
    result = {"started": True, "drum_bp": bp[0]}
elif MODE == "cleanup":
    result = {"removed_temp_actors": cleanup_editor()}
elif MODE == "poll":
    result = public(unreal._al)
else:
    S = unreal._al
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    S["removed_temp_actors"] = cleanup_editor()   # returns 0 while PIE is still shutting down: call "cleanup" afterwards
    out = public(S)
    json.dump(out, open(os.path.join(OUT, "atoll_lagoon_pie.json"), "w"), indent=1)
    result = out
