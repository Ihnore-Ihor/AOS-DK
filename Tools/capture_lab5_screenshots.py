"""AOS-DK Lab 5 - real screenshots for the report (Saved/Screenshots/Lab5/shot_NN_*.png).

Usage (MCP execute_python), every call is a separate invocation:
    g = {"CAP_MODE": "pike_setup" | "pike_shot" | "pike_cleanup" | "start" | "poll" | "stop"}
    exec(open(r"<proj>/Tools/capture_lab5_screenshots.py", encoding="utf-8").read(), g); result = g["result"]
pike_*  : editor viewport, shot_02 (SM_WPN_SigkillPike + 4 UCX hulls, ShowFlag.Collision).
start   : begins PIE and a generator state machine (slate post-tick) that shoots 03..09 with a spawned CameraActor
          (the Shell is parked out of the Reaper's sight, so the AI behaves naturally). poll: progress. stop: ends PIE.
Screenshots: AutomationLibrary.take_high_res_screenshot -> Saved/Screenshots/WindowsEditor/lab5_tmp_NN.png, then copied.
"""
import os, math, shutil, glob
import unreal

MODE = globals().get("CAP_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SRC = os.path.join(PROJ, "Saved", "Screenshots", "WindowsEditor")
DST = os.path.join(PROJ, "Saved", "Screenshots", "Lab5")
CX, CY, FLOOR = -43500.0, 22000.0, -9800.0
POOL = (CX, CY - 1300.0)
GS = unreal.GameplayStatics
RES = (1920, 1080)
NAMES = {2: "pike_ucx", 3: "page_map", 4: "arena_navmesh", 5: "patrol_survey", 6: "melee_strike",
         7: "evasion_decoy", 8: "brine_pool", 9: "daemon_reaper"}
PIKE_AT = unreal.Vector(-1000.0, 820.0, 6000.0)

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def ew(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
def sp2(v): return math.hypot(v.x, v.y)

def publish(n):
    os.makedirs(DST, exist_ok=True)
    src = os.path.join(SRC, f"lab5_tmp_{n:02d}.png")
    dst = os.path.join(DST, f"shot_{n:02d}_{NAMES[n]}.png")
    if os.path.isfile(src):
        shutil.copyfile(src, dst); return dst
    return None

# =====================================================================================================================
# shot 02: editor viewport (no PIE)
# =====================================================================================================================
if MODE in ("prep", "unprep"):
    # PIE has no generic spawn API in Python: place the camera and the two lights in the editor level first (PIE copies them)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if MODE == "prep":
        c = eas.spawn_actor_from_class(unreal.CameraActor, V(CX, CY, FLOOR + 800), unreal.Rotator(0, 0, 0)); c.set_actor_label("TMP_CapCam")
        for i in range(2):
            l = eas.spawn_actor_from_class(unreal.PointLight, V(CX, CY, FLOOR + 900), unreal.Rotator(0, 0, 0)); l.set_actor_label(f"TMP_CapLight{i}")
            lc = l.get_component_by_class(unreal.PointLightComponent)
            lc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
            lc.set_editor_property("intensity", 30000.0 if i == 0 else 10000.0)
            lc.set_editor_property("attenuation_radius", 6000.0)
            lc.set_editor_property("cast_shadows", i == 0)
            lc.set_light_color(unreal.LinearColor(0.78, 0.88, 1.0, 1.0) if i == 0 else unreal.LinearColor(1.0, 0.8, 0.9, 1.0))
        result = {"prepared": True}
    else:
        n = 0
        for a in eas.get_all_level_actors():
            if a.get_actor_label().startswith("TMP_Cap"):
                eas.destroy_actor(a); n += 1
        result = {"removed": n}

if MODE in ("pike_setup", "pike_shot", "pike_cleanup"):
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if MODE == "pike_setup":
        mesh = unreal.load_asset("/Game/AOS_DK_Game/Enemies/Reaper/Meshes/SM_WPN_SigkillPike")
        a = eas.spawn_actor_from_class(unreal.StaticMeshActor, PIKE_AT, unreal.Rotator(0, 0, 0))
        a.set_actor_label("TMP_PikeShot")
        a.static_mesh_component.set_static_mesh(mesh)
        a.static_mesh_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        cam = PIKE_AT + V(118, -185, -75)      # 1.85 m from the pike, looking slightly up at the sky: clean background
        ues.set_level_viewport_camera_info(cam, unreal.MathLibrary.find_look_at_rotation(cam, PIKE_AT + V(118, 0, 0)))
        for c in ("ShowFlag.Collision 1", "ShowFlag.Fog 0", "ShowFlag.VolumetricFog 0"):
            unreal.SystemLibrary.execute_console_command(ew(), c)
        result = {"spawned": a.get_name()}
    elif MODE == "pike_shot":
        unreal.AutomationLibrary.take_high_res_screenshot(RES[0], RES[1], "lab5_tmp_02.png")
        result = {"requested": True}
    else:
        for a in eas.get_all_level_actors():
            if a.get_actor_label() == "TMP_PikeShot":
                eas.destroy_actor(a)
        unreal.SystemLibrary.execute_console_command(ew(), "ShowFlag.Collision 0")
        result = {"published": publish(2)}

# =====================================================================================================================
# shots 03..09: PIE generator
# =====================================================================================================================
def scenario(S):
    now = lambda: GS.get_time_seconds(gw())
    def wait(sec):
        end = now() + sec
        while now() < end: yield
    def until(fn, timeout):
        end = now() + timeout
        while now() < end:
            if fn(): return True
            yield
        return bool(fn())
    def con(cmd): unreal.SystemLibrary.execute_console_command(gw(), cmd)

    yield from until(lambda: GS.get_player_controller(gw(), 0) and GS.get_all_actors_of_class(gw(), unreal.ShellPawn)
                     and GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter) and now() > 1.5, 30)
    pc = GS.get_player_controller(gw(), 0); sh = GS.get_all_actors_of_class(gw(), unreal.ShellPawn)[0]
    r = GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter)[0]
    ctl = r.get_controller(); root = sh.get_editor_property("box_root"); bay = sh.drone_bay
    pc.possess(sh); yield from wait(0.3)
    if sh.is_in_lars_cradle(): sh.leave_lars_cradle()
    root.set_simulate_physics(False)
    bay.deploy_all_drones()
    att = bay.get_drone(0)
    yield from until(lambda: att.is_deployed() and att.get_deploy_blend() > 0.99, 10)
    S["ctx"] = (sh, r)

    for c in ("ShowFlag.EyeAdaptation 0", "r.EyeAdaptationQuality 0", "ShowFlag.Fog 0", "ShowFlag.VolumetricFog 0", "r.Streaming.PoolSize 4000"):
        con(c)

    # ---- helpers --------------------------------------------------------------------------------------------------------------
    def brain(on):
        b = ctl.get_editor_property("brain_component")
        if b: (b.restart_logic() if on else b.stop_logic("cap"))
    def put_reaper(x, y, yaw=0.0):
        r.set_actor_location_and_rotation(V(x, y, FLOOR + 145.0), unreal.Rotator(0, yaw, 0), False, True)
        r.character_movement.set_editor_property("velocity", V(0, 0, 0))
    def put_shell(loc, look=None):
        rot = unreal.MathLibrary.find_look_at_rotation(loc, look) if look is not None else sh.get_actor_rotation()
        S["lock"] = (loc, rot); sh.set_actor_location_and_rotation(loc, rot, False, True); pc.set_control_rotation(rot)
    def park_shell():
        put_shell(V(CX + 6000, CY, FLOOR + 600), V(CX, CY, FLOOR))   # out of the 26 m sight radius: the Reaper stays calm
    # camera + light actors (placed in the editor level by MODE "prep")
    by = {x.get_actor_label(): x for x in GS.get_all_actors_of_class(gw(), unreal.Actor) if x.get_actor_label().startswith("TMP_Cap")}
    cam = by["TMP_CapCam"]
    lights = [by["TMP_CapLight0"], by["TMP_CapLight1"]]
    def aim(loc, look, fov=75.0, light_at=None):
        cam.set_actor_location_and_rotation(loc, unreal.MathLibrary.find_look_at_rotation(loc, look), False, True)
        cam.camera_component.set_editor_property("field_of_view", float(fov))
        pc.set_view_target_with_blend(cam, 0.0)
        la = light_at if light_at is not None else look
        lights[0].set_actor_location(V(la.x - 500, la.y - 500, la.z + 1400), False, True)
        lights[1].set_actor_location(V(loc.x, loc.y, loc.z + 300), False, True)
    def snap(n):
        unreal.AutomationLibrary.take_high_res_screenshot(RES[0], RES[1], f"lab5_tmp_{n:02d}.png")
        S["requested"].append(n)
    def ph(): return r.get_phase().name

    # ---- 04: arena + NavMesh overlay ----------------------------------------------------------------------------------------------
    try:
        brain(False); park_shell(); put_reaper(CX + 600, CY + 700, 200)
        con("show navigation")
        aim(V(CX - 2300, CY - 2500, FLOOR + 2300), V(CX, CY, FLOOR), 80, V(CX, CY, FLOOR))
        lights[0].get_component_by_class(unreal.PointLightComponent).set_editor_property("attenuation_radius", 9000.0)
        lights[0].get_component_by_class(unreal.PointLightComponent).set_editor_property("intensity", 40000.0)
        yield from wait(2.0); snap(4); yield from wait(2.0)
        con("show navigation")
    except Exception as e:
        S["errors"].append(("04", repr(e)))

    # ---- 03: RSS Page Map over the Reaper ---------------------------------------------------------------------------------------
    try:
        pm = r.page_map
        pm.set_editor_property("always_visible", True)
        pm.set_health(112.0, 168.0)                  # 4 of 16 pages freed: the grid visibly "drains"
        brain(False); put_reaper(CX, CY + 300, 200); r.set_actor_rotation(unreal.Rotator(0, 200, 0), False)
        rp = r.get_actor_location()
        aim(rp + V(-480, -380, 380), rp + V(0, 0, 330), 60, rp + V(0, 0, 200))
        yield from wait(2.5); snap(3); yield from wait(2.0)
    except Exception as e:
        S["errors"].append(("03", repr(e)))

    # ---- 08: Heap Brine Pool with the Reaper wading ---------------------------------------------------------------------------------
    try:
        pm.set_editor_property("always_visible", False)
        brain(False); put_reaper(POOL[0] + 120, POOL[1] + 60, 90)
        yield from wait(1.5)
        aim(V(POOL[0] + 1450, POOL[1] - 1100, FLOOR + 650), V(POOL[0], POOL[1], FLOOR + 90), 70, V(POOL[0], POOL[1], FLOOR))
        yield from wait(2.0); snap(8); yield from wait(2.0)
    except Exception as e:
        S["errors"].append(("08", repr(e)))

    # ---- 09: Lab 3 Daemon + Reaper in one frame ----------------------------------------------------------------------------------------
    try:
        dae = GS.get_all_actors_of_class(gw(), unreal.AOS_EnemyDaemon)
        put_reaper(CX - 400, CY + 1500, 0); yield from wait(1.0)
        rp = r.get_actor_location()
        if dae:
            dae[0].set_actor_location(V(rp.x + 700, rp.y + 250, FLOOR + 520), False, True)
        yield from wait(0.6)
        aim(V(rp.x - 450, rp.y - 1350, FLOOR + 520), V(rp.x + 350, rp.y + 100, FLOOR + 300), 75, V(rp.x + 350, rp.y + 100, FLOOR + 200))
        yield from wait(1.2); snap(9); yield from wait(2.0)
        S["daemons"] = len(dae)
    except Exception as e:
        S["errors"].append(("09", repr(e)))

    # ---- 05: patrol / survey --------------------------------------------------------------------------------------------------------
    try:
        park_shell(); put_reaper(CX - 1300, CY + 1300, -90); brain(True)
        yield from until(lambda: ph() == "SURVEY", 70)
        rp = r.get_actor_location()
        aim(rp + V(900, -900, 380), rp + V(0, 0, 150), 65, rp + V(0, 0, 100))
        yield from wait(1.0)
        if ph() != "SURVEY":
            yield from until(lambda: ph() == "SURVEY", 40)
            rp = r.get_actor_location(); aim(rp + V(900, -900, 380), rp + V(0, 0, 150), 65, rp + V(0, 0, 100))
        yield from wait(0.6); snap(5); yield from wait(2.0)
        S["phase05"] = ph()
    except Exception as e:
        S["errors"].append(("05", repr(e)))

    # ---- 06: melee strike (slow motion, shot on the thrust) --------------------------------------------------------------------------
    try:
        brain(False); put_reaper(CX - 1300, CY + 1300, 0); yield from wait(0.5); brain(True)
        yield from until(lambda: ph() in ("PATROL", "SURVEY") and ctl.get_threat_level().name != "HOSTILE", 8)
        rp = r.get_actor_location(); fwd = r.get_actor_forward_vector()
        right = r.get_actor_right_vector()
        shell_loc = V(rp.x + fwd.x * 650, rp.y + fwd.y * 650, rp.z + 265)
        put_shell(shell_loc, rp)
        con("slomo 0.25")
        got = yield from until(lambda: ph() in ("STRIKE_WINDUP", "STRIKE_THRUST"), 15)
        yield from until(lambda: ph() == "STRIKE_THRUST", 3)
        rp = r.get_actor_location(); fwd = r.get_actor_forward_vector(); right = r.get_actor_right_vector()
        aim(rp + V(right.x * 1050, right.y * 1050, 300) + V(fwd.x * 250, fwd.y * 250, 0), rp + V(fwd.x * 300, fwd.y * 300, 170), 65, rp + V(fwd.x * 300, fwd.y * 300, 150))
        snap(6)
        yield from wait(0.6)
        con("slomo 1"); S["phase06"] = ph()
        yield from wait(2.0)
    except Exception as e:
        con("slomo 1"); S["errors"].append(("06", repr(e)))

    # ---- 07: evasion - skitter + cavitation decoy ----------------------------------------------------------------------------------------
    try:
        brain(False); put_reaper(CX - 1700, CY + 100, 180); yield from wait(1.5)
        con("aos.ai.ForceDodge 1")
        if att.get_ring_ammo() < 8:
            bay.request_reload(); yield from until(lambda: att.get_ring_ammo() >= 30, 10)
        rp = r.get_actor_location()
        put_shell(V(rp.x + 1900.0, rp.y, rp.z), rp)
        yield from wait(3.5)
        aim(rp + V(900, -1000, 380), rp + V(250, 120, 150), 70, rp + V(250, 0, 120))
        ring0 = att.get_ring_ammo()
        con("slomo 0.3")
        bay.set_primary_action_held(True)
        yield from until(lambda: att.get_ring_ammo() < ring0, 4.0)
        yield from wait(0.10); bay.set_primary_action_held(False)
        got = yield from until(lambda: len(GS.get_all_actors_of_class(gw(), unreal.AOS_CavitationDecoy)) > 0, 4.0)
        yield from wait(0.35)
        aim(rp + V(900, -1000, 380), rp + V(250, 120, 150), 70, rp + V(250, 0, 120))
        snap(7)
        yield from wait(0.5); con("slomo 1"); con("aos.ai.ForceDodge -1")
        S["decoy07"] = bool(got)
        yield from wait(2.0)
    except Exception as e:
        con("slomo 1"); con("aos.ai.ForceDodge -1"); S["errors"].append(("07", repr(e)))

    S["lock"] = None
    for n in (3, 4, 5, 6, 7, 8, 9):
        S["published"][n] = publish(n)
    S["state"] = "done"

def driver(dt):
    S = unreal._cap
    try:
        w = gw()
        if not w: return
        if S["gen"] is None:
            S["gen"] = scenario(S); S["state"] = "running"
        if S.get("ctx") and S.get("lock"):
            sh = S["ctx"][0]; lk = S["lock"]
            sh.set_actor_location_and_rotation(lk[0], lk[1], False, True)
        if S.get("busy"): return            # take_high_res_screenshot pumps the slate tick: no re-entry into the generator
        S["busy"] = True
        try: next(S["gen"])
        except StopIteration: S["state"] = "done"
        finally: S["busy"] = False
    except Exception:
        import traceback
        S["error"] = traceback.format_exc()[-900:]; S["state"] = "error"
    if S["state"] in ("done", "error"):
        try: unreal.unregister_slate_post_tick_callback(S["handle"])
        except Exception: pass

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._cap = {"state": "boot", "gen": None, "requested": [], "published": {}, "errors": [],
                   "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._cap["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._cap
    result = {k: S.get(k) for k in ("state", "error", "requested", "published", "errors", "phase05", "phase06", "decoy07", "daemons")}
elif MODE == "stop":
    S = unreal._cap
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property(
        "bThrottleCPUWhenNotForeground", S["throttle_was"])
    result = {"stopped": True, "published": {n: publish(n) for n in (3, 4, 5, 6, 7, 8, 9)}}
