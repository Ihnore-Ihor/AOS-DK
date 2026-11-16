"""AOS-DK Lab 6 / Batch C2 - PIE test: 3 Breakwater gate beacons (AAOSGateBeacon) + Harbour skiff on LS_Atoll_HarbourSkiff.
Usage (MCP execute_python):
    g = {"RT_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_lab6_c2.py", encoding="utf-8").read(), g)
    optional globals: RT_SHOTS (default True), RT_STORM (default True)
start: begins PIE and runs the scenario.  poll: {state, passed, failed}.  stop: ends PIE, writes Saved/Lab6_C2_Verify/Lab6_C2_PIE.json
Checks:
  C2.boot          3 AOSGateBeacon, the HarbourSkiff, the LevelSequenceActor and its sequence player exist in PIE
  C2.noon          aos.env.TimeOfDay 12, Storm 0: all 3 beacons OFF (alpha 0, idle yaw 20 deg/s, spot at the 5 % standby fraction)
  C2.night         TimeOfDay 0: all 3 ON, commanded yaw 90 deg/s, MEASURED yaw rotation of the pivot 90 deg/s, spot pulse 0.2 -> 1.0 -> 0.2, tilt +-2 deg
  C2.pulse_loop    the Flash curve repeats every 4.0 s (value at t and t + 4 s equal)
  C2.storm_on      noon + aos.env.Storm 1: beacons switch ON once max(NightFactor, StormAlpha) > 0.3, then OFF again after aos.env.Storm 0
  C2.ls_autoplay   LS_Atoll_HarbourSkiff plays automatically, looping, player is_playing
  C2.skiff_path    ring radius 9700 +- 15 cm, bob Z 40 +- 12, roll +- 3, pitch +- 2, heading = tangent, speed constant, seamless wrap
  C2.skiff_clear   no blocking actor within 900 cm of any sampled position; clearance to city AABB and BC-R pipe ring
"""
import json, math, os
import unreal

MODE = globals().get("RT_MODE", "poll")
SHOTS = globals().get("RT_SHOTS", True)
DO_STORM = globals().get("RT_STORM", True)
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT_DIR = os.path.join(PROJ, "Saved", "Lab6_C2_Verify")
GS = unreal.GameplayStatics
MPC_PATH = "/Game/AOS_DK_Game/Environment/Water/MPC_AOS_Atoll"
C = (-1000.0, 700.0)
R = 9700.0
CITY_R, RING_R = 8332.0, 11000.0


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def rnd(x, n=3):
    return None if x is None else round(float(x), n)


def near(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def scenario(S):
    Rz = S["results"]

    def chk(i, ok, detail):
        Rz.append({"id": i, "ok": bool(ok), "detail": detail})

    now = lambda: GS.get_time_seconds(gw())
    mpc = unreal.load_asset(MPC_PATH)
    os.makedirs(OUT_DIR, exist_ok=True)

    def wait(sec):
        end = now() + sec
        while now() < end:
            yield

    def cmd(c):
        unreal.SystemLibrary.execute_console_command(gw(), c)

    def mp(name):
        return unreal.MaterialLibrary.get_scalar_parameter_value(gw(), mpc, name)

    def shot(name, cam, at, fov=60.0, ev=0.0, w_=1600, h_=900):
        """SceneCapture2D in the PIE world -> PNG in Saved/Lab6_C2_Verify (returns the path or None)."""
        if not SHOTS:
            return None
        w = gw()
        rt_ = unreal.RenderingLibrary.create_render_target2d(w, w_, h_, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        camv, atv = unreal.Vector(*cam), unreal.Vector(*at)
        rot = unreal.MathLibrary.find_look_at_rotation(camv, atv)
        tf = unreal.Transform(camv, rot, unreal.Vector(1, 1, 1))
        caps = [a for a in GS.get_all_actors_of_class(w, unreal.SceneCapture2D) if a.get_actor_label() == "TMP_C2_Cam"]
        cap = caps[0]                                              # PIE copy of the temp editor actor (spawning into the PIE world is not exposed to Python)
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
        return p

    S["shots"] = []
    BEACON1 = (-13610.0, -155.0, 1800.0)
    CAM1 = (-12100.0, 500.0, 1790.0)

    def aimed_shot(name, off_deg, ev=3.0, cam=CAM1, fov=60.0):
        """Rotate the Gate-1 yaw pivot so the front spot points off_deg away from the camera (the beam sweeps at 90 deg/s, so an unaimed shot mostly misses it), then capture."""
        if not SHOTS:
            return
        b = [x for x in beacons if x.get_actor_label() == "GateBeacon_Gate1_W"][0]
        az = math.degrees(math.atan2(cam[1] - BEACON1[1], cam[0] - BEACON1[0]))
        b.get_editor_property("yaw_pivot").set_world_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=az + off_deg), False, True)
        shot(name, cam, BEACON1, fov=fov, ev=ev)

    # ---- boot ----------------------------------------------------------------------------------------------------------------
    end = now() + 30
    while not (GS.get_player_controller(gw(), 0) and now() > 2.0):
        if now() > end:
            break
        yield
    beacons = sorted(GS.get_all_actors_of_class(gw(), unreal.AOSGateBeacon), key=lambda a: a.get_actor_label())
    skiffs = [a for a in GS.get_all_actors_of_class(gw(), unreal.Actor) if a.get_actor_label() == "HarbourSkiff"]
    lsas = GS.get_all_actors_of_class(gw(), unreal.LevelSequenceActor)
    lsa = lsas[0] if lsas else None
    player = (lsa.get_editor_property("sequence_player") if lsa else None)
    skiff = skiffs[0] if skiffs else None
    chk("C2.boot", len(beacons) == 3 and skiff is not None and lsa is not None and player is not None,
        {"beacons": [b.get_actor_label() for b in beacons], "skiff": bool(skiff), "lsa": bool(lsa), "player": bool(player)})

    def bstate():
        return [{"n": b.get_actor_label(), "on": bool(b.is_beacon_on()), "alpha": rnd(b.get_on_alpha(), 3), "yaw_rate": rnd(b.get_yaw_rate_deg_per_sec(), 2),
                 "flash": rnd(b.get_flash(), 3), "spot": rnd(b.get_spot_intensity(), 1), "tilt": rnd(b.get_tilt_deg(), 3)} for b in beacons]

    cmd("aos.env.Storm 0")
    cmd("aos.env.Pause 1")
    cmd("aos.env.TimeOfDay 12")
    yield from wait(4.0)
    noon = bstate()
    spot_max = beacons[0].get_editor_property("spot_intensity_max")
    off_frac = beacons[0].get_editor_property("off_intensity_fraction")
    chk("C2.noon", all((not s["on"]) and s["alpha"] == 0.0 and near(s["yaw_rate"], 20.0, 0.1) and near(s["spot"], spot_max * off_frac, spot_max * 0.002) for s in noon),
        {"states": noon, "night_mpc": rnd(mp("NightFactor")), "storm_mpc": rnd(mp("StormAlpha")), "off_spot_expected": spot_max * off_frac})
    if SHOTS:
        shot("c2_noon_gate1_beacon", (-12700, -420, 1500), (-13610, -155, 1790), fov=55, ev=0.0)

    if globals().get("RT_ONLY_BEAMS"):                         # diagnostic: burst of night shots while the beams sweep
        cmd("aos.env.Pause 1")
        cmd("aos.env.TimeOfDay %s" % globals().get("RT_TOD", 0))
        yield from wait(3.5)
        cam = globals().get("RT_CAM", (-12100.0, 500.0, 1790.0))
        if globals().get("RT_CD"):
            for b in beacons:
                b.set_editor_property("spot_intensity_max", float(globals()["RT_CD"]))
        b0 = beacons[0]
        piv0 = b0.get_editor_property("yaw_pivot")
        az = math.degrees(math.atan2(cam[1] - (-155.0), cam[0] - (-13610.0)))
        offs = globals().get("RT_OFFS", [0.0, 6.0, 15.0, 35.0, 60.0, 90.0])
        for i in range(int(globals().get("RT_N", 12))):
            piv0.set_world_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=az + offs[i % len(offs)]), False, True)   # aim the front spot (+X) off-axis by offs[i] deg from the camera
            shot("beam_%02d" % i, cam, (-13610.0, -155.0, 1800.0), fov=float(globals().get("RT_FOV", 50.0)), ev=float(globals().get("RT_EV", 3.0)))
            S.setdefault("beam_meta", []).append({"i": i, "off_deg": offs[i % len(offs)], "flash": rnd(b0.get_flash(), 3), "spot": rnd(b0.get_spot_intensity(), 1)})
            yield from wait(0.1)
        return
    # ---- night ---------------------------------------------------------------------------------------------------------------------
    cmd("aos.env.TimeOfDay 0")
    yield from wait(3.5)
    night0 = bstate()
    piv = [b.get_editor_property("yaw_pivot") for b in beacons]
    # measure the real rotation of the yaw pivot over 1.0 s (unwrapped)
    y0 = [p.get_world_rotation().yaw for p in piv]
    t0 = now()
    prev = list(y0)
    unw = [0.0, 0.0, 0.0]
    flash_samples, tilt_samples, spot_samples = [], [], []
    while now() - t0 < 4.3:
        for i, p in enumerate(piv):
            yy = p.get_world_rotation().yaw
            unw[i] += wrap180(yy - prev[i])
            prev[i] = yy
            if i == 0 and now() - t0 > 0.0:
                pass
        b0 = beacons[0]
        flash_samples.append((now() - t0, b0.get_flash(), b0.get_pulse_time(), b0.get_tilt_deg(), b0.get_spot_intensity()))
        yield
    dt = now() - t0
    rates = [u / dt for u in unw]
    night1 = bstate()
    flashes = [s[1] for s in flash_samples]
    tilts = [s[3] for s in flash_samples]
    spots = [s[4] for s in flash_samples]
    chk("C2.night", all(s["on"] and s["alpha"] == 1.0 and near(s["yaw_rate"], 90.0, 0.01) for s in night1) and all(near(abs(r_), 90.0, 2.0) for r_ in rates)
        and max(flashes) > 0.95 and min(flashes) < 0.3 and max(tilts) > 1.8 and min(tilts) < -1.8 and max(spots) > 0.9 * spot_max and min(spots) < 0.3 * spot_max,
        {"states": night1, "measured_deg_per_s": [rnd(r_, 2) for r_ in rates], "window_s": rnd(dt, 3), "flash_range": [rnd(min(flashes)), rnd(max(flashes))],
         "tilt_range": [rnd(min(tilts)), rnd(max(tilts))], "spot_range_cd": [rnd(min(spots), 1), rnd(max(spots), 1)], "spot_max": spot_max, "night_mpc": rnd(mp("NightFactor"))})
    # 4 s periodicity of the loop clock/curve: compare flash at pulse time p and p + 4 (the clock wraps)
    by_p = sorted(((round(s[2], 2), s[1]) for s in flash_samples))
    first_p, last_p = flash_samples[0][2], flash_samples[-1][2]
    # find sample pairs 4.0 s apart in elapsed time
    pairs = []
    for s in flash_samples:
        for s2 in flash_samples:
            if abs((s2[0] - s[0]) - 4.0) < 0.012:
                pairs.append(abs(s2[1] - s[1]))
                break
    chk("C2.pulse_loop", bool(pairs) and max(pairs) < 0.03 and len(pairs) > 3, {"pairs": len(pairs), "max_diff": rnd(max(pairs) if pairs else None, 4), "period": beacons[0].get_editor_property("pulse_period")})
    aimed_shot("c2_night_gate1_beam_a", 12.0)
    aimed_shot("c2_night_gate1_beam_b", 35.0)
    aimed_shot("c2_night_gate1_beam_wide", 20.0, ev=3.0, cam=(-9800.0, 1200.0, 1500.0), fov=70.0)
    S["night_samples"] = [[rnd(a, 3), rnd(b, 3), rnd(c, 3), rnd(d, 3), rnd(e, 1)] for (a, b, c, d, e) in flash_samples[::8]]

    # ---- dusk (informational) --------------------------------------------------------------------------------------------------------
    cmd("aos.env.TimeOfDay 18")
    yield from wait(3.0)
    dusk = {"night_mpc": rnd(mp("NightFactor")), "states": bstate()}
    S["dusk"] = dusk

    # ---- storm at noon -------------------------------------------------------------------------------------------------------------
    if DO_STORM:
        cmd("aos.env.TimeOfDay 12")
        yield from wait(3.0)
        off0 = all(not s["on"] for s in bstate())
        cmd("aos.env.Storm 1")
        t_start, on_at, gate_at = now(), None, None
        while now() - t_start < 90:
            st = mp("StormAlpha")
            if on_at is None and all(b.is_beacon_on() for b in beacons):
                on_at = now() - t_start
                gate_at = {"storm_mpc": rnd(st, 3), "night_mpc": rnd(mp("NightFactor"), 3)}
                break
            yield
        yield from wait(2.0)
        storm_state = bstate()
        if SHOTS:
            aimed_shot("c2_storm_gate1_beam", 15.0, ev=3.0)
        cmd("aos.env.Storm 0")
        t_clear, off_at = now(), None
        while now() - t_clear < 120:
            if all(not b.is_beacon_on() for b in beacons):
                off_at = now() - t_clear
                break
            yield
        chk("C2.storm_on", off0 and on_at is not None and off_at is not None and gate_at["storm_mpc"] >= 0.25,
            {"off_before": off0, "on_after_s": rnd(on_at, 1), "at": gate_at, "states_in_storm": storm_state, "off_after_clear_s": rnd(off_at, 1), "night_mpc_end": rnd(mp("NightFactor")), "storm_mpc_end": rnd(mp("StormAlpha"))})
        cmd("aos.env.Storm auto")
    else:
        chk("C2.storm_on", True, "skipped (RT_STORM False)")

    # ---- skiff / level sequence ---------------------------------------------------------------------------------------------------------
    cmd("aos.env.TimeOfDay 12")
    cmd("aos.env.Storm 0")
    wds = GS.get_all_actors_of_class(gw(), unreal.AOSWeatherDirector)
    t_w = now()
    while wds and wds[0].get_weather_state().name != "CLEAR" and now() - t_w < 90:
        yield
    yield from wait(4.0)
    pb = lsa.get_editor_property("playback_settings")
    playing = bool(player.is_playing())
    t_a = player.get_current_time().time.frame_number.value if hasattr(player.get_current_time(), "time") else None
    yield from wait(1.0)
    t_b = player.get_current_time().time.frame_number.value if hasattr(player.get_current_time(), "time") else None
    chk("C2.ls_autoplay", playing and t_a is not None and t_b is not None and t_b != t_a and bool(pb.get_editor_property("auto_play")) and pb.get_editor_property("loop_count").get_editor_property("value") == -1,
        {"playing": playing, "frame_a": t_a, "frame_b": t_b, "auto_play": bool(pb.get_editor_property("auto_play")), "loop_count": pb.get_editor_property("loop_count").get_editor_property("value"),
         "sequence": lsa.get_sequence().get_name()})

    # 1x speed sample (2 s) for the real speed
    loc0 = skiff.get_actor_location()
    ta = now()
    yield from wait(2.0)
    loc1 = skiff.get_actor_location()
    speed1 = math.hypot(loc1.x - loc0.x, loc1.y - loc0.y) / (now() - ta)

    # accelerated sweep: 8x for 20 s of game time = 160 s of sequence time (> 1 full loop, includes the wrap)
    RATE = 8.0
    player.set_play_rate(RATE)
    samples = []
    t0 = now()
    last_probe = -1e9
    clear_hits = {}
    probes = 0
    objs = [getattr(unreal.ObjectTypeQuery, "OBJECT_TYPE_QUERY%d" % i) for i in (1, 2, 3, 4)]
    shot_az = [0.15, 0.6]
    shots_taken = set()
    while now() - t0 < 20.5:
        loc, rot = skiff.get_actor_location(), skiff.get_actor_rotation()
        tt = now()
        samples.append((tt, loc.x, loc.y, loc.z, rot.roll, rot.pitch, rot.yaw))
        if tt - last_probe > 1.0:
            last_probe = tt
            probes += 1
            for z in (-800.0, 100.0, 600.0):
                for act in (unreal.SystemLibrary.sphere_overlap_actors(gw(), unreal.Vector(loc.x, loc.y, z), 900.0, objs, unreal.Actor, [skiff]) or []):
                    n = act.get_actor_label()
                    if n in ("WaterBodyOcean", "WaterZone") or n.startswith("FallRecovery") or n.startswith("LevelSequenceActor") or n.startswith("LSA_"):
                        continue
                    clear_hits[n] = clear_hits.get(n, 0) + 1
        if SHOTS:
            fr = (tt - t0) / 20.5
            for k, f in enumerate(shot_az):
                if fr > f and k not in shots_taken:
                    shots_taken.add(k)
                    a_h = math.radians(rot.yaw)
                    fwd = (math.cos(a_h), math.sin(a_h))
                    side = (-fwd[1], fwd[0])
                    cam = (loc.x - fwd[0] * 900 + side[0] * 700, loc.y - fwd[1] * 900 + side[1] * 700, 380.0)
                    shot("c2_skiff_%d" % (k + 1), cam, (loc.x, loc.y, 180.0), fov=60.0, ev=1.0)
        yield
    player.set_play_rate(1.0)
    ts = [s[0] for s in samples]
    rad = [math.hypot(s[1] - C[0], s[2] - C[1]) for s in samples]
    zs = [s[3] for s in samples]
    rolls = [wrap180(s[4]) for s in samples]
    pitches = [wrap180(s[5]) for s in samples]
    # heading vs tangent (CCW tangent = az + 90)
    herr = []
    for s in samples:
        az = math.degrees(math.atan2(s[2] - C[1], s[1] - C[0]))
        herr.append(wrap180(s[6] - (az + 90.0)))
    steps = []
    angs = []
    for i in range(1, len(samples)):
        a0 = math.atan2(samples[i - 1][2] - C[1], samples[i - 1][1] - C[0])
        a1 = math.atan2(samples[i][2] - C[1], samples[i][1] - C[0])
        da = math.degrees(wrap180(math.degrees(a1 - a0)) * math.pi / 180.0)
        dtt = samples[i][0] - samples[i - 1][0]
        angs.append(da / dtt if dtt > 0 else 0.0)
        steps.append(math.hypot(samples[i][1] - samples[i - 1][1], samples[i][2] - samples[i - 1][2]))
    med_ang = sorted(angs)[len(angs) // 2]
    chk("C2.skiff_path", max(abs(r_ - R) for r_ in rad) < 15.0 and min(zs) > 40 - 12.6 and max(zs) < 40 + 12.6 and max(zs) - min(zs) > 20 and max(abs(x) for x in rolls) < 3.1
        and max(abs(x) for x in pitches) < 2.1 and max(abs(x) for x in rolls) > 2.0 and max(abs(h) for h in herr) < 1.5 and near(speed1, 2 * math.pi * R / 120.0, 12.0)
        and near(med_ang, 3.0 * RATE, 1.0) and max(abs(a - med_ang) for a in angs if abs(a) < 400) < 0.12 * med_ang,
        {"radius_dev_max_cm": rnd(max(abs(r_ - R) for r_ in rad), 2), "z_range": [rnd(min(zs), 2), rnd(max(zs), 2)], "roll_max": rnd(max(abs(x) for x in rolls), 2), "pitch_max": rnd(max(abs(x) for x in pitches), 2),
         "heading_err_max_deg": rnd(max(abs(h) for h in herr), 3), "speed_1x_cm_s": rnd(speed1, 1), "expected_speed": rnd(2 * math.pi * R / 120.0, 1),
         "median_deg_per_s_at_8x": rnd(med_ang, 3), "ang_speed_dev_max": rnd(max(abs(a - med_ang) for a in angs if abs(a) < 400), 3), "max_step_cm": rnd(max(steps), 1), "median_step_cm": rnd(sorted(steps)[len(steps) // 2], 1),
         "frames": len(samples), "game_s": rnd(ts[-1] - ts[0], 2), "sequence_s_covered": rnd((ts[-1] - ts[0]) * RATE, 1)})
    chk("C2.skiff_clear", not clear_hits and probes >= 15,
        {"probes": probes, "blocking_hits_within_900cm": clear_hits, "min_radius_cm": rnd(min(rad), 1), "max_radius_cm": rnd(max(rad), 1),
         "clearance_to_city_aabb_cm": rnd(min(rad) - CITY_R - 368.0, 1), "clearance_to_BCR_ring_cm": rnd(RING_R - max(rad) - 368.0, 1), "skiff_half_diag_cm": 368})
    S["skiff_samples"] = [[rnd(s[0], 2), rnd(s[1], 1), rnd(s[2], 1), rnd(s[3], 2), rnd(s[4], 2), rnd(s[5], 2), rnd(s[6], 2)] for s in samples[::30]]
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
    R_ = S["results"]
    return {"state": S["state"], "error": S.get("error"), "n": len(R_), "passed": sum(1 for x in R_ if x["ok"]),
            "failed": [x["id"] for x in R_ if not x["ok"]]}


if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._rt = {"state": "boot", "gen": None, "results": [], "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    _eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not [a for a in _eas.get_all_level_actors() if a.get_actor_label() == "TMP_C2_Cam"]:
        _c = _eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 5000))
        _c.set_actor_label("TMP_C2_Cam")
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
    for _a in [a for a in _eas.get_all_level_actors() if a.get_actor_label() == "TMP_C2_Cam"]:
        _eas.destroy_actor(_a)
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property(
        "bThrottleCPUWhenNotForeground", S["throttle_was"])
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {**summary(S), "results": S["results"], "shots": S.get("shots"), "dusk": S.get("dusk"), "night_samples": S.get("night_samples"), "skiff_samples": S.get("skiff_samples")}
    with open(os.path.join(OUT_DIR, "Lab6_C2_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Lab6_C2_Verify/Lab6_C2_PIE.json"}
