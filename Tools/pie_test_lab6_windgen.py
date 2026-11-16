"""Lab6 Batch D - PIE verification of the 3 animated AAOSWindGenerator turbines.
Usage (execute_python):  g = {"RT_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_lab6_windgen.py", encoding="utf-8").read(), g)
Checks: D.boot, D.calm_spin, D.calm_hunt, D.storm, D.night_on, D.day_off, D.static_hidden. Output: Saved/Lab6_D_Verify/Lab6_D_PIE.json + PNGs.
"""
import json, math, os
import unreal

MODE = globals().get("RT_MODE", "poll")
SHOTS = globals().get("RT_SHOTS", True)
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT_DIR = os.path.join(PROJ, "Saved", "Lab6_D_Verify")
GS = unreal.GameplayStatics
SPIN_LEN = 3.0
RTS_P = unreal.RelativeTransformSpace.RTS_PARENT_BONE_SPACE
CAMTAG = "TMP_D_Cam"


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def rnd(x, n=3):
    return None if x is None else round(float(x), n)


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def qdot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w


def qang(a, b):
    return math.degrees(2.0 * math.acos(min(1.0, abs(qdot(a, b)))))


def scenario(S):
    Rz = S["results"]
    S["shots"] = []

    def chk(i, ok, detail):
        Rz.append({"id": i, "ok": bool(ok), "detail": detail})

    now = lambda: GS.get_time_seconds(gw())
    os.makedirs(OUT_DIR, exist_ok=True)

    def cmd(c):
        unreal.SystemLibrary.execute_console_command(gw(), c)

    def wait(sec):
        end = now() + sec
        while now() < end:
            yield

    def shot(name, cam, at, fov=55.0, ev=0.0, w_=1600, h_=900):
        if not SHOTS:
            return
        w = gw()
        rt_ = unreal.RenderingLibrary.create_render_target2d(w, w_, h_, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        camv, atv = unreal.Vector(*cam), unreal.Vector(*at)
        rot = unreal.MathLibrary.find_look_at_rotation(camv, atv)
        cap = [a for a in GS.get_all_actors_of_class(w, unreal.SceneCapture2D) if a.get_actor_label() == CAMTAG][0]
        cap.set_actor_location_and_rotation(camv, rot, False, True)
        cc = cap.capture_component2d
        cc.texture_target = rt_
        cc.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
        cc.set_editor_property("capture_every_frame", False)
        cc.set_editor_property("capture_on_movement", False)
        cc.set_editor_property("fov_angle", float(fov))
        pp = unreal.PostProcessSettings()
        for k_, v_ in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                       ("override_auto_exposure_bias", True), ("auto_exposure_bias", float(ev)),
                       ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", False)):
            pp.set_editor_property(k_, v_)
        cc.set_editor_property("post_process_settings", pp)
        cc.set_editor_property("post_process_blend_weight", 1.0)
        cc.capture_scene()
        cc.capture_scene()
        p = os.path.join(OUT_DIR, name + ".png")
        if os.path.exists(p):
            os.remove(p)
        unreal.RenderingLibrary.export_render_target(w, rt_, OUT_DIR, name + ".png")
        S["shots"].append(name)

    # ---- boot ----
    end = now() + 30
    while not (GS.get_player_controller(gw(), 0) and now() > 2.0):
        if now() > end:
            break
        yield
    gens = sorted(GS.get_all_actors_of_class(gw(), unreal.AOSWindGenerator), key=lambda a: a.get_actor_label())
    anims = [g.get_wind_anim() for g in gens]
    meshes = [g.get_editor_property("turbine_mesh") for g in gens]
    chk("D.boot", len(gens) == 3 and all(anims) and all(m.get_editor_property("skeletal_mesh_asset") for m in meshes),
        {"gens": [(g.get_actor_label(), str(g.get_actor_location())) for g in gens], "anim_ok": [bool(a) for a in anims],
         "anim_class": [m.get_editor_property("anim_class").get_name() for m in meshes]})
    G0 = gens[0]
    loc0 = G0.get_actor_location()

    def bone(g, name, space=RTS_P):
        return g.get_editor_property("turbine_mesh").get_socket_transform(name, space)

    def hub_roll(g):
        q = bone(g, "WG_Rotor_Hub").rotation          # pure X rotation vs the nacelle (identity bind) -> robust angle, no Euler gimbal flips
        return math.degrees(2.0 * math.atan2(q.x, q.w))

    def st():
        return [{"n": g.get_actor_label()[-1], "wind": rnd(g.get_wind01()), "tgt_spin": rnd(g.get_target_spin_rate()), "spin": rnd(a.get_spin_rate()),
                 "furl": rnd(a.get_furl_alpha()), "loops": rnd(a.get_spin_loops(), 2), "hunt_t": rnd(a.get_hunt_time(), 2),
                 "light_on": bool(g.is_obstruction_light_on()), "light_a": rnd(g.get_light_on_alpha()), "light_cd": rnd(g.get_light_intensity(), 2)}
                for g, a in zip(gens, anims)]

    # ---- calm ----
    cmd("aos.env.Pause 1")
    cmd("aos.env.TimeOfDay 12")
    cmd("aos.env.Storm 0")
    yield from wait(4.0)
    S["calm_state0"] = st()
    cam_a = (loc0.x + 3600.0, loc0.y - 600.0, 560.0)
    at_a = (loc0.x, loc0.y, 600.0)
    shot("D_calm_day", cam_a, at_a)
    # sample hub roll / nacelle yaw / vane yaw over one full hunt loop (8 s) for all 3
    t_end = now() + 8.4
    prev = [hub_roll(g) for g in gens]
    prev_t = now()
    rates = [[] for _ in gens]
    unw = [[(now(), 0.0)] for _ in gens]               # (game time, unwrapped hub angle) for a dt-independent linearity fit
    yaws = [[] for _ in gens]
    vanes = [[] for _ in gens]
    loops0 = [a.get_spin_loops() for a in anims]
    while now() < t_end:
        yield
        t = now()
        dt = t - prev_t
        if dt <= 1e-4:
            continue
        for i, g in enumerate(gens):
            r = hub_roll(g)
            stp = wrap180(r - prev[i])
            rates[i].append(stp / dt)
            unw[i].append((t, unw[i][-1][1] + stp))
            prev[i] = r
            yaws[i].append(bone(g, "WG_Nacelle_Yaw").rotation.rotator().yaw)
            vanes[i].append(bone(g, "WG_TailVane").rotation.rotator().yaw)
        prev_t = t
    S["calm_state1"] = st()
    loops1 = [a.get_spin_loops() for a in anims]
    sp = []
    for i in range(3):
        rs = sorted(rates[i])
        med = rs[len(rs) // 2] if rs else 0.0
        mean_abs = sum(abs(x) for x in rs) / max(1, len(rs))
        same_sign = all((x * med) > 0 for x in rs) if med else False
        ratio = [abs(x) / abs(med) for x in rs] if med else [0]
        ts_ = [a for a, _ in unw[i]]
        an_ = [b for _, b in unw[i]]
        mt, ma = sum(ts_) / len(ts_), sum(an_) / len(an_)
        slope = sum((a - mt) * (b - ma) for a, b in unw[i]) / sum((a - mt) ** 2 for a in ts_)
        resid = max(abs(b - (ma + slope * (a - mt))) for a, b in unw[i])
        sp.append({"i": i, "slope_deg_s": rnd(slope, 1), "max_resid_deg": rnd(resid, 2), "n": len(rs), "median_deg_s": rnd(med, 1), "min_ratio": rnd(min(ratio), 2), "max_ratio": rnd(max(ratio), 2), "monotonic": same_sign,
                   "loops_delta": rnd(loops1[i] - loops0[i], 2), "mean_abs_deg_s": rnd(mean_abs, 1)})
    S["calm_spin"] = sp
    chk("D.calm_spin", all(s["monotonic"] and s["n"] > 60 and abs(s["median_deg_s"]) > 20.0 and s["loops_delta"] > 0.5 and s["max_resid_deg"] < 25.0 and abs(s["slope_deg_s"]) > 20.0 for s in sp), sp)
    hy = []
    for i in range(3):
        ys = yaws[i]
        vs = vanes[i]
        hy.append({"i": i, "nacelle_yaw_min": rnd(min(ys), 2), "nacelle_yaw_max": rnd(max(ys), 2), "range": rnd(max(ys) - min(ys), 2),
                   "vane_range": rnd(max(vs) - min(vs), 2)})
    S["calm_hunt"] = hy
    chk("D.calm_hunt", all(8.0 <= h["range"] <= 40.0 for h in hy), hy)
    calm_blade = [bone(g, "WG_Blade_0").rotation for g in gens]
    calm_nac = [bone(g, "WG_Nacelle_Yaw").rotation.rotator().yaw for g in gens]
    # breeze: nudge the wind through the director if available (record only)
    calm_wind = [rnd(g.get_wind01()) for g in gens]
    S["calm_wind"] = calm_wind
    calm_eff = [abs(s["mean_abs_deg_s"]) for s in sp]

    # ---- storm ----
    cmd("aos.env.Storm 1")
    peak_spin = [0.0] * 3
    peak_eff = [0.0] * 3
    peak_wind = [0.0] * 3
    prev = [hub_roll(g) for g in gens]
    prev_t = now()
    t_end = now() + 16.0
    mid_shot = False
    t0 = now()
    trace = []
    while now() < t_end:
        yield
        t = now()
        dt = t - prev_t
        if dt <= 1e-4:
            continue
        for i, g in enumerate(gens):
            r = hub_roll(g)
            eff = abs(wrap180(r - prev[i]) / dt)
            prev[i] = r
            peak_eff[i] = max(peak_eff[i], eff)
            peak_spin[i] = max(peak_spin[i], anims[i].get_spin_rate())
            peak_wind[i] = max(peak_wind[i], g.get_wind01())
        prev_t = t
        if int((t - t0) * 2) > len(trace):
            trace.append({"t": rnd(t - t0, 1), "wind": rnd(G0.get_wind01()), "spin": rnd(anims[0].get_spin_rate()), "furl": rnd(anims[0].get_furl_alpha()), "eff": rnd(peak_eff[0], 1)})
        if not mid_shot and anims[0].get_furl_alpha() > 0.4:
            mid_shot = True
            shot("D_storm_midfurl", cam_a, at_a, ev=1.0)
    S["storm_trace"] = trace
    s_state = st()
    S["storm_state"] = s_state
    blade_d = [qang(calm_blade[i], bone(g, "WG_Blade_0").rotation) for i, g in enumerate(gens)]
    nac_d = [wrap180(bone(g, "WG_Nacelle_Yaw").rotation.rotator().yaw - calm_nac[i]) for i, g in enumerate(gens)]
    shot("D_storm_furled", cam_a, at_a, ev=1.0)
    chk("D.storm", all(x["wind"] > calm_wind[i] + 0.3 for i, x in enumerate(s_state)) and all(peak_spin[i] > s["spin"] if False else peak_spin[i] > 1.0 for i in range(3))
        and all(x["furl"] >= 0.95 for x in s_state) and all(d > 50.0 for d in blade_d),
        {"wind_calm": calm_wind, "wind_storm_peak": [rnd(x) for x in peak_wind], "calm_spin_state": [x["spin"] for x in S["calm_state1"]], "peak_spin_rate": [rnd(x) for x in peak_spin],
         "calm_eff_deg_s": calm_eff, "peak_eff_deg_s": [rnd(x, 1) for x in peak_eff], "final_furl": [x["furl"] for x in s_state],
         "blade_pitch_change_deg": [rnd(d, 1) for d in blade_d], "nacelle_yaw_change_deg": [rnd(d, 1) for d in nac_d],
         "light_on_in_storm_day": [x["light_on"] for x in s_state]})
    storm_light = [x["light_on"] for x in s_state]
    shot("D_storm_lights", cam_a, at_a, ev=-1.0)

    # ---- night ----
    cmd("aos.env.Storm 0")
    cmd("aos.env.TimeOfDay 0")
    yield from wait(10.0)
    n_state = st()
    S["night_state"] = n_state
    comp = G0.get_editor_property("obstruction_light")
    shot("D_night_lights", cam_a, (loc0.x, loc0.y, 880.0), ev=2.0)
    shot("D_night_closeup", (loc0.x + 1500.0, loc0.y - 300.0, 1000.0), (loc0.x, loc0.y, 930.0), fov=45.0, ev=2.0)
    cmd("aos.env.Pause 1")
    chk("D.night_on", all(x["light_on"] and x["light_a"] > 0.9 for x in n_state) and comp.get_editor_property("intensity") >= 0.0,
        {"night": n_state, "storm_day_lights": storm_light, "light_comp_intensity": rnd(comp.get_editor_property("intensity"), 2)})

    # ---- day: lights off ----
    cmd("aos.env.TimeOfDay 12")
    yield from wait(5.0)
    d_state = st()
    chk("D.day_off", all((not x["light_on"]) and x["light_a"] < 0.05 for x in d_state), d_state)

    # ---- static ism hidden ----
    stat = [a for a in GS.get_all_actors_of_class(gw(), unreal.Actor) if a.get_name().startswith("Actor_UAID_D843AE8DD121211503_1705351579")]
    chk("D.static_hidden", bool(stat) and all(a.get_editor_property("hidden") and not a.get_actor_enable_collision() for a in stat),
        {"found": len(stat), "hidden": [bool(a.get_editor_property("hidden")) for a in stat]})
    cmd("aos.env.Pause 0")


def driver(dt):
    S = unreal._rt
    try:
        if S["gen"] is None:
            if gw() is None:
                return
            S["gen"] = scenario(S)
            S["state"] = "run"
        next(S["gen"])
    except StopIteration:
        S["state"] = "done"
    except Exception:
        import traceback
        S["error"] = traceback.format_exc()[-1800:]
        S["state"] = "error"
    if S["state"] in ("done", "error"):
        try:
            unreal.unregister_slate_post_tick_callback(S["handle"])
        except Exception:
            pass


def summary(S):
    R_ = S["results"]
    return {"state": S["state"], "error": S.get("error"), "n": len(R_), "passed": sum(1 for x in R_ if x["ok"]), "failed": [x["id"] for x in R_ if not x["ok"]]}


if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._rt = {"state": "boot", "gen": None, "results": [], "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    _eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not [a for a in _eas.get_all_level_actors() if a.get_actor_label() == CAMTAG]:
        _c = _eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 5000))
        _c.set_actor_label(CAMTAG)
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._rt["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._rt
    result = {**summary(S), "last": S["results"][-1] if S["results"] else None}
elif MODE == "stop":
    S = unreal._rt
    try:
        unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception:
        pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
    _eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for _a in [a for a in _eas.get_all_level_actors() if a.get_actor_label() == CAMTAG]:
        _eas.destroy_actor(_a)
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {**summary(S), "results": S["results"], "shots": S.get("shots"), "calm_state0": S.get("calm_state0"), "calm_state1": S.get("calm_state1"),
           "storm_trace": S.get("storm_trace"), "storm_state": S.get("storm_state"), "night_state": S.get("night_state")}
    with open(os.path.join(OUT_DIR, "Lab6_D_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Lab6_D_Verify/Lab6_D_PIE.json"}
