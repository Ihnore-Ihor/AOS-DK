"""AOS-DK Lab 6 / Task 4 (Batch B) - PIE test for the environment core: day/night cycle, weather director, ocean-controller sync.
Usage (MCP execute_python):
    g = {"RT_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_lab6_env_core.py", encoding="utf-8").read(), g)
start: begins PIE and runs the scenario.  poll: {state, passed, failed}.  stop: ends PIE, writes Saved/Lab6_Verify/Lab6_EnvCore_PIE.json
Checks (every one is {id, ok, detail}):
  B.boot            DayNightCycle, WeatherDirector, DL_Moon (atmosphere index 1), sun (index 0) and OceanDepthController exist in PIE
  B.sun_pick        OceanDepthController.Sun is the index-0 light, not DL_Moon
  B.noon            aos.env.TimeOfDay 12: NightFactor(MPC) ~0, sun on, moon ~0
  B.az_15           aos.env.TimeOfDay 15: sun yaw equals the authored -10.3 deg (Ocean Optics regression)
  B.dusk            TimeOfDay 18: 0 < NightFactor < 1, sun intensity between noon and night
  B.night           TimeOfDay 0: NightFactor(MPC) ~1, sun hidden / intensity 0, sky ~0.12 x noon, moon on, moon antipodal to the sun
  B.sun_single      light intensity written only by the controller: sun intensity = noon * SunScale (moves with the revision, no direct writes)
  B.clock           clock advances at 24 h / 12 min and pauses with aos.env.Pause 1
  B.storm_build     aos.env.Storm 1: Building -> Raining, StormAlpha(MPC) -> ~1, Wind01 > 0.85
  B.storm_light     storm dims the sun to ~0.25 x and sky to ~0.6 x (controller re-applied on Revision change); air fog density x4
  B.storm_clouds    VolumetricCloud MID: Cloud_GlobalCoverage -> 0.3 (full overcast; >0.5 thins to an empty sky), StormClouds stays 0 (>0 swaps to isolated cells), Cloud_GlobalDensity ~1.5 x base (EnvPolish fix)
  B.storm_wet       Wetness rises to ~1 (+1/25 s) while it rains; NightFactor(MPC) >= 0.5 x storm at noon
  B.clear           aos.env.Storm 0: Clearing -> Clear, StormAlpha/Wind back down, rain stops, Wetness dries slowly, sun back to noon value
  B.auto            aos.env.Storm auto: random FSM resumes (state Clear)
"""
import json, os
import unreal

MODE = globals().get("RT_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT_DIR = os.path.join(PROJ, "Saved", "Lab6_Verify")
GS = unreal.GameplayStatics
MPC_PATH = "/Game/AOS_DK_Game/Environment/Water/MPC_AOS_Atoll"
AUTHORED_SUN_YAW = -10.3086


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def rnd(x, n=3):
    return None if x is None else round(float(x), n)


def near(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def scenario(S):
    R = S["results"]

    def chk(i, ok, detail):
        R.append({"id": i, "ok": bool(ok), "detail": detail})

    now = lambda: GS.get_time_seconds(gw())
    mpc = unreal.load_asset(MPC_PATH)

    def wait(sec):
        end = now() + sec
        while now() < end:
            yield

    def cmd(c):
        unreal.SystemLibrary.execute_console_command(gw(), c)

    def mp(name):
        return unreal.MaterialLibrary.get_scalar_parameter_value(gw(), mpc, name)

    def find(cls):
        a = GS.get_all_actors_of_class(gw(), cls)
        return a[0] if a else None

    # ---- boot --------------------------------------------------------------------------------------------------------------
    end = now() + 30
    while not (GS.get_player_controller(gw(), 0) and find(unreal.AOSDayNightCycle) and now() > 1.5):
        if now() > end:
            break
        yield
    dn, wd, ctrl = find(unreal.AOSDayNightCycle), find(unreal.AOSWeatherDirector), find(unreal.AOSOceanDepthController)
    lights = {}
    for l in GS.get_all_actors_of_class(gw(), unreal.DirectionalLight):
        c = l.get_component_by_class(unreal.DirectionalLightComponent)
        lights[int(c.get_editor_property("atmosphere_sun_light_index"))] = l
    sun, moon = lights.get(0), lights.get(1)
    sky = find(unreal.SkyLight)
    fog = find(unreal.ExponentialHeightFog)
    cloud_actor = find(unreal.VolumetricCloud)
    sun_c = sun.get_component_by_class(unreal.DirectionalLightComponent)
    moon_c = moon.get_component_by_class(unreal.DirectionalLightComponent)
    sky_c = sky.get_component_by_class(unreal.SkyLightComponent)
    fog_c = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    cloud_c = cloud_actor.get_component_by_class(unreal.VolumetricCloudComponent)
    chk("B.boot", all([dn, wd, ctrl, sun, moon, sky]), {"dn": bool(dn), "wd": bool(wd), "ctrl": bool(ctrl), "sun": bool(sun), "moon": bool(moon), "sky": bool(sky)})
    chk("B.sun_pick", ctrl.get_editor_property("sun") == sun, {"ctrl_sun": ctrl.get_editor_property("sun").get_name(), "atmo0": sun.get_name()})

    def snap(tag):
        return {"tag": tag, "t": rnd(now(), 2), "tod": rnd(dn.get_time_of_day(), 3), "night_mpc": rnd(mp("NightFactor")),
                "storm_mpc": rnd(mp("StormAlpha")), "wind_mpc": rnd(mp("Wind01")), "wet_mpc": rnd(mp("Wetness")),
                "sun_i": rnd(sun_c.get_editor_property("intensity"), 4), "sun_vis": bool(sun_c.is_visible()),
                "sky_i": rnd(sky_c.get_editor_property("intensity"), 4), "moon_i": rnd(moon_c.get_editor_property("intensity"), 4),
                "sun_pitch": rnd(sun.get_actor_rotation().pitch, 2), "sun_yaw": rnd(sun.get_actor_rotation().yaw, 2),
                "moon_pitch": rnd(moon.get_actor_rotation().pitch, 2), "fog_density": rnd(fog_c.get_editor_property("fog_density"), 5),
                "underwater": bool(ctrl.is_camera_underwater()), "weather": wd.get_weather_state().name}

    S["snaps"] = []

    def go(hour, tag):
        cmd(f"aos.env.TimeOfDay {hour}")
        yield from wait(0.6)           # >= 2 publish periods (10 Hz) + controller Tick
        s = snap(tag)
        S["snaps"].append(s)
        return s
    # generator-returning helper: use  s = yield from go(..)

    # clear weather, freeze the clock
    cmd("aos.env.Storm 0")
    cmd("aos.env.Pause 1")
    yield from wait(0.5)

    noon = yield from go(12, "noon")
    chk("B.noon", near(noon["night_mpc"], 0.0, 0.02) and noon["sun_vis"] and noon["moon_i"] < 0.01 and noon["sun_i"] > 0.5,
        {k: noon[k] for k in ("night_mpc", "sun_i", "sun_vis", "moon_i", "sun_pitch", "underwater")})

    s15 = yield from go(15, "15h")
    chk("B.az_15", near(s15["sun_yaw"], AUTHORED_SUN_YAW, 0.6), {"sun_yaw": s15["sun_yaw"], "authored": AUTHORED_SUN_YAW, "sun_pitch": s15["sun_pitch"], "sun_i": s15["sun_i"]})

    dusk = yield from go(18, "18h")
    night = yield from go(0, "0h")
    chk("B.dusk", 0.05 < dusk["night_mpc"] < 0.95 and night["sun_i"] <= dusk["sun_i"] <= noon["sun_i"],
        {"night_mpc": dusk["night_mpc"], "sun_i": dusk["sun_i"], "noon_sun_i": noon["sun_i"]})
    sky_ratio = (night["sky_i"] / noon["sky_i"]) if noon["sky_i"] else None
    chk("B.night", near(night["night_mpc"], 1.0, 0.02) and night["sun_i"] < 0.01 and not night["sun_vis"] and near(sky_ratio, 0.12, 0.03)
        and night["moon_i"] > 0.05 and near(night["moon_pitch"], -night["sun_pitch"], 0.5),
        {"night_mpc": night["night_mpc"], "sun_i": night["sun_i"], "sun_vis": night["sun_vis"], "sky_ratio": rnd(sky_ratio), "moon_i": night["moon_i"],
         "moon_pitch": night["moon_pitch"], "sun_pitch": night["sun_pitch"]})

    # single-writer: noon sun intensity is the cached base (6.0) x 1 when above water and the clear day scale is 1
    back = yield from go(12, "noon_again")
    chk("B.sun_single", near(back["sun_i"], noon["sun_i"], 0.02) and night["sun_i"] < noon["sun_i"],
        {"noon": noon["sun_i"], "after_cycle": back["sun_i"], "night": night["sun_i"], "note": "restored to base after a full dim/restore: no stale writer"})

    # clock
    t0 = dn.get_time_of_day()
    cmd("aos.env.Pause 1"); yield from wait(1.0)
    frozen = near(dn.get_time_of_day(), t0, 1e-3)
    cmd("aos.env.Pause 0"); yield from wait(3.0)
    adv = dn.get_time_of_day() - t0
    chk("B.clock", frozen and near(adv, 3.0 * 24.0 / 720.0, 0.03), {"frozen": frozen, "advanced_h_in_3s": rnd(adv, 4), "expected": rnd(3.0 * 24.0 / 720.0, 4)})
    cmd("aos.env.TimeOfDay 12"); cmd("aos.env.Pause 1"); yield from wait(0.6)
    day0 = snap("storm_baseline")
    S["snaps"].append(day0)

    # ---- storm ---------------------------------------------------------------------------------------------------------------------
    base_mid = cloud_c.get_editor_property("material")
    base_cov = base_mid.get_scalar_parameter_value("Cloud_GlobalCoverage")
    base_dens = base_mid.get_scalar_parameter_value("Cloud_GlobalDensity")
    cmd("aos.env.Storm 1")
    seen, t_start = [], now()
    wet_ok_at = None
    while now() - t_start < 60:
        st = wd.get_weather_state().name
        if not seen or seen[-1] != st:
            seen.append(st)
        if wet_ok_at is None and wd.get_wetness() >= 0.98:
            wet_ok_at = now() - t_start
        if wet_ok_at is not None:
            break
        yield
    yield from wait(0.5)
    st1 = snap("storm_peak")
    S["snaps"].append(st1)
    chk("B.storm_build", seen[:2] == ["BUILDING", "RAINING"] and st1["storm_mpc"] > 0.97 and st1["wind_mpc"] > 0.85,
        {"seen": seen, "storm_mpc": st1["storm_mpc"], "wind_mpc": st1["wind_mpc"]})
    sun_ratio = st1["sun_i"] / day0["sun_i"] if day0["sun_i"] else None
    sky_r = st1["sky_i"] / day0["sky_i"] if day0["sky_i"] else None
    fog_ok = True
    fog_detail = "skipped (camera underwater)"
    if not st1["underwater"] and not day0["underwater"]:
        fog_r = st1["fog_density"] / day0["fog_density"]
        fog_ok = near(fog_r, 4.0, 0.2)
        fog_detail = rnd(fog_r)
    chk("B.storm_light", near(sun_ratio, 0.25, 0.03) and near(sky_r, 0.6, 0.03) and fog_ok,
        {"sun_ratio": rnd(sun_ratio), "sky_ratio": rnd(sky_r), "fog_ratio": fog_detail})

    mid = cloud_c.get_editor_property("material")
    cov = mid.get_scalar_parameter_value("Cloud_GlobalCoverage")
    dens = mid.get_scalar_parameter_value("Cloud_GlobalDensity")
    storm_c = mid.get_scalar_parameter_value("StormClouds")
    S["cloud"] = {"base_coverage": rnd(base_cov), "base_density": rnd(base_dens, 5), "coverage": rnd(cov), "density": rnd(dens, 5), "density_ratio": rnd(dens / base_dens if base_dens else None), "storm": rnd(storm_c), "material": mid.get_name()}
    chk("B.storm_clouds", near(cov, 0.3, 0.03) and near(storm_c, 0.0, 0.03) and base_dens and near(dens / base_dens, 1.5, 0.1) and "MaterialInstanceDynamic" in mid.get_class().get_name(), S["cloud"])
    chk("B.storm_wet", wet_ok_at is not None and st1["night_mpc"] >= 0.49, {"wet_reached_s": rnd(wet_ok_at, 1), "wetness": st1["wet_mpc"], "night_mpc_in_storm": st1["night_mpc"],
                                                                                 "rain_rate": rnd(wd.get_rain_rate01())})
    wet_peak = st1["wet_mpc"]

    # ---- clear ---------------------------------------------------------------------------------------------------------------------
    cmd("aos.env.Storm 0")
    seen2, t_start = [], now()
    while now() - t_start < 40:
        st = wd.get_weather_state().name
        if not seen2 or seen2[-1] != st:
            seen2.append(st)
        if st == "CLEAR":
            break
        yield
    yield from wait(5.0)
    cl = snap("cleared")
    S["snaps"].append(cl)
    cl_sun_ok = near(cl["sun_i"], day0["sun_i"], 0.03)
    chk("B.clear", seen2[:2] == ["CLEARING", "CLEAR"] and cl["storm_mpc"] < 0.01 and cl["wind_mpc"] < 0.45 and wd.get_rain_rate01() == 0.0
        and 0.0 < cl["wet_mpc"] < wet_peak and cl_sun_ok,
        {"seen": seen2, "storm_mpc": cl["storm_mpc"], "wind_mpc": cl["wind_mpc"], "wetness_peak": wet_peak, "wetness_now": cl["wet_mpc"], "sun_i": cl["sun_i"], "noon_sun": day0["sun_i"]})

    cmd("aos.env.Storm auto")
    yield from wait(1.0)
    chk("B.auto", wd.get_weather_state().name == "CLEAR", {"state": wd.get_weather_state().name})
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
        S["error"] = traceback.format_exc()[-1500:]
        S["state"] = "error"
    if S["state"] in ("done", "error"):
        try:
            unreal.unregister_slate_post_tick_callback(S["handle"])
        except Exception:
            pass


def summary(S):
    R = S["results"]
    return {"state": S["state"], "error": S.get("error"), "n": len(R), "passed": sum(1 for x in R if x["ok"]),
            "failed": [x["id"] for x in R if not x["ok"]]}


if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._rt = {"state": "boot", "gen": None, "results": [], "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
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
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property(
        "bThrottleCPUWhenNotForeground", S["throttle_was"])
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {**summary(S), "results": S["results"], "snapshots": S.get("snaps"), "cloud": S.get("cloud")}
    with open(os.path.join(OUT_DIR, "Lab6_EnvCore_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Lab6_Verify/Lab6_EnvCore_PIE.json"}
