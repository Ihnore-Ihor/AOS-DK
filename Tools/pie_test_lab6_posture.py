"""AOS-DK Lab 6 / Task 2 - PIE test for the OOM Reaper pike draw / stow posture FSM (generator on the slate post-tick).
Usage (MCP execute_python):
    g = {"LP_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_lab6_posture.py", encoding="utf-8").read(), g); result = g["result"]
start: begins PIE + the scenario.  poll: {state, passed, failed}.  stop: ends PIE, writes Saved/Lab6_Posture_PIE.json.
The Reaper is PINNED at a fixed spot/yaw every tick (zero velocity) so the range is exactly what the test dials; the real BT
(BTService_AOS_ReaperSense -> SetCombatRangeInfo -> UpdateWeaponPosture) and the real strike task stay running.
Scenario (Shell teleported along the Reaper's +X axis, centre distance in cm):
  P1 2500 : Stowed, s = 0                       P4 450 : strike lands only in Ready (never while Drawing/Stowing)
  P2 1200 : Stowed -> Drawing (~1.10 s) -> Ready  P5 2000 : hysteresis band (range 1500..1900), still Ready after 3 s
  P3 pose : s monotonic, pike tip continuous    P6 2500 : Stowing only after the 1.5 s grace, ~1.40 s, -> Stowed, s monotonic."""
import json, os, math
import unreal

MODE = globals().get("LP_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
CX, CY, FLOOR = -43500.0, 22000.0, -9800.0   # Lab 5 arena anchor (Tools/deploy_lab5_arena.py)
GS = unreal.GameplayStatics

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def rnd(x, n=2): return None if x is None else round(float(x), n)

def scenario(S):
    R = S["results"]
    def chk(i, ok, detail): R.append({"id": i, "ok": bool(ok), "detail": detail})
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
    yield from until(lambda: GS.get_player_controller(gw(), 0) and GS.get_all_actors_of_class(gw(), unreal.ShellPawn)
                     and GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter) and now() > 1.5, 30)
    pc = GS.get_player_controller(gw(), 0); sh = GS.get_all_actors_of_class(gw(), unreal.ShellPawn)[0]
    r = GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter)[0]
    ctl = r.get_controller(); root = sh.get_editor_property("box_root")
    pc.possess(sh); yield from wait(0.3)
    if sh.is_in_lars_cradle(): sh.leave_lars_cradle()
    root.set_simulate_physics(False)
    S["r"], S["sh"] = r, sh
    S["pin"] = (V(CX, CY, FLOOR + 145.0), unreal.Rotator(0, 0, 0))     # Reaper faces +X
    def put_shell(dist, dz=300.0):
        loc = V(CX + dist, CY, FLOOR + dz)
        rot = unreal.MathLibrary.find_look_at_rotation(loc, V(CX, CY, FLOOR + dz))
        S["lock"] = (loc, rot); sh.set_actor_location_and_rotation(loc, rot, False, True); pc.set_control_rotation(rot)
    def post(): return r.get_weapon_posture().name
    def brain(on):
        b = ctl.get_editor_property("brain_component")
        if b: (b.restart_logic() if on else b.stop_logic("test"))

    # ---- P0 setup: Shell far away, Reaper calm, then enable sampling -------------------------------------------------------------
    brain(False); put_shell(6000.0, 600.0); yield from wait(1.0); brain(True)
    chk("P0.starts_stowed", post() == "STOWED" and r.get_posture_s() == 0.0, {"posture": post(), "s": r.get_posture_s()})
    S["trace"] = []; S["sampling"] = True

    # ---- P1 stowed at > 20 m --------------------------------------------------------------------------------------------------------
    put_shell(2500.0); yield from wait(3.0)
    chk("P1.stowed_beyond_20m", post() == "STOWED" and r.get_posture_s() == 0.0 and ctl.get_threat_level().name != "NONE",
        {"posture": post(), "s": r.get_posture_s(), "threat": ctl.get_threat_level().name, "range_cm": rnd(r.get_range_cm(), 0)})

    # ---- P2 draw at <= 15 m ---------------------------------------------------------------------------------------------------------
    S["mark"] = len(S["trace"]); t0 = now(); put_shell(1200.0)
    ok_d = yield from until(lambda: post() == "DRAWING", 3.0); t_draw = now()
    ok_r = yield from until(lambda: post() == "READY", 3.0); t_ready = now()
    chk("P2.draw_starts_within_15m", ok_d, {"t_from_teleport_s": rnd(t_draw - t0), "range_cm": rnd(r.get_range_cm(), 0)})
    chk("P2.draw_takes_1p1s", ok_r and abs((t_ready - t_draw) - r.get_editor_property("draw_time")) < 0.30,
        {"draw_s": rnd(t_ready - t_draw), "draw_time": r.get_editor_property("draw_time")})
    seg = [x for x in S["trace"][S["mark"]:] if x["posture"] == "DRAWING"]
    sv = [x["s"] for x in seg]
    chk("P3.draw_progress_smooth_monotonic", len(sv) > 10 and all(b >= a - 1e-4 for a, b in zip(sv, sv[1:])) and sv[-1] > 0.9,
        {"samples": len(sv), "s_first": rnd(sv[0], 3) if sv else None, "s_last": rnd(sv[-1], 3) if sv else None})
    tips = [x["tip"] for x in S["trace"][S["mark"]:] if x["tip"]]
    jumps = [math.dist(a, b) / max(1e-3, (y["t"] - x["t"])) for (x, y, a, b) in
             [(p, q, p["tip"], q["tip"]) for p, q in zip(S["trace"][S["mark"]:], S["trace"][S["mark"] + 1:]) if p["tip"] and q["tip"] and q["t"] > p["t"]]]
    chk("P3.pike_tip_continuous", jumps and max(jumps) < 4500.0, {"max_tip_speed_cm_s": rnd(max(jumps) if jumps else None, 0), "n": len(jumps)})
    chk("P4a.no_strike_while_drawing", not any(x["posture"] in ("DRAWING", "STOWING", "STOWED") and x["phase"].startswith("STRIKE") for x in S["trace"]),
        {"offending": [x for x in S["trace"] if x["posture"] != "READY" and x["phase"].startswith("STRIKE")][:3]})

    # ---- P4 strike only in Ready ------------------------------------------------------------------------------------------------------
    put_shell(450.0)
    hit = yield from until(lambda: r.get_phase().name.startswith("STRIKE"), 8.0)
    chk("P4.strike_lands_in_ready", hit and post() == "READY", {"phase": r.get_phase().name, "posture": post()})
    yield from until(lambda: not r.get_phase().name.startswith("STRIKE"), 4.0)

    # ---- P5 hysteresis band -----------------------------------------------------------------------------------------------------------
    put_shell(2000.0); yield from wait(3.0)   # centre 2000 -> hull-point range ~1730: inside the 1500..1900 band
    rg = r.get_range_cm()
    chk("P5.hysteresis_hold_in_band", post() == "READY" and 1500.0 < rg < 1900.0, {"posture": post(), "range_cm": rnd(rg, 0)})

    # ---- P6 stow after > 19 m for 1.5 s ----------------------------------------------------------------------------------------------
    S["mark"] = len(S["trace"]); t0 = now(); put_shell(2500.0)
    ok_s = yield from until(lambda: post() == "STOWING", 5.0); t_stow = now()
    ok_z = yield from until(lambda: post() == "STOWED", 4.0); t_done = now()
    grace = r.get_editor_property("stow_grace_time")
    chk("P6.stow_after_grace", ok_s and (t_stow - t0) >= grace - 0.05 and (t_stow - t0) < grace + 1.0, {"t_to_stowing_s": rnd(t_stow - t0), "grace": grace})
    chk("P6.stow_takes_1p4s", ok_z and abs((t_done - t_stow) - r.get_editor_property("stow_time")) < 0.30, {"stow_s": rnd(t_done - t_stow), "stow_time": r.get_editor_property("stow_time")})
    sv = [x["s"] for x in S["trace"][S["mark"]:] if x["posture"] == "STOWING"]
    chk("P6.stow_progress_monotonic", len(sv) > 10 and all(b <= a + 1e-4 for a, b in zip(sv, sv[1:])) and r.get_posture_s() == 0.0,
        {"samples": len(sv), "s_first": rnd(sv[0], 3) if sv else None, "s_end": r.get_posture_s()})

    # ---- P7 re-draw works after a full stow (no stuck state) ------------------------------------------------------------------------
    put_shell(1200.0)
    ok = yield from until(lambda: post() == "READY", 4.0)
    chk("P7.redraw_after_stow", ok, {"posture": post()})

    S["sampling"] = False
    posts = [x["posture"] for x in S["trace"]]
    order = [p for i, p in enumerate(posts) if i == 0 or p != posts[i - 1]]
    chk("P8.state_sequence", order[:1] == ["STOWED"] and "DRAWING" in order and "READY" in order and "STOWING" in order, {"sequence": order})

def driver(dt):
    S = unreal._rt
    try:
        w = gw()
        if not w: return
        if S["gen"] is None:
            S["gen"] = scenario(S); S["state"] = "running"
        r, sh = S.get("r"), S.get("sh")
        if r and sh:
            lk = S.get("lock")
            if lk: sh.set_actor_location_and_rotation(lk[0], lk[1], False, True)
            pin = S.get("pin")
            if pin and not r.is_dead():
                r.set_actor_location_and_rotation(pin[0], pin[1], False, True)
                r.character_movement.set_editor_property("velocity", V(0, 0, 0))
            if S.get("sampling"):
                wp = r.get_editor_property("weapon"); tip = None
                if wp:
                    l = wp.get_actor_location(); fw = wp.get_actor_forward_vector()
                    tip = (l.x + fw.x * 262.0, l.y + fw.y * 262.0, l.z + fw.z * 262.0)
                S["trace"].append({"t": GS.get_time_seconds(w), "posture": r.get_weapon_posture().name, "s": r.get_posture_s(),
                                   "phase": r.get_phase().name, "range": r.get_range_cm(), "tip": tip})
        try: next(S["gen"])
        except StopIteration: S["state"] = "done"
    except Exception:
        import traceback
        S["error"] = traceback.format_exc()[-900:]; S["state"] = "error"
    if S["state"] in ("done", "error"):
        try: unreal.unregister_slate_post_tick_callback(S["handle"])
        except Exception: pass

def summary(S):
    Rr = S["results"]
    return {"state": S["state"], "error": S.get("error"), "n": len(Rr), "passed": sum(1 for x in Rr if x["ok"]), "failed": [x["id"] for x in Rr if not x["ok"]]}

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._rt = {"state": "boot", "gen": None, "results": [], "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._rt["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._rt; result = {**summary(S), "last": S["results"][-1] if S["results"] else None}
elif MODE == "stop":
    S = unreal._rt
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = {**summary(S), "results": S["results"], "trace_tail": S.get("trace", [])[-40:]}
    with open(os.path.join(PROJ, "Saved", "Lab6_Posture_PIE.json"), "w", encoding="utf-8") as f: json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Lab6_Posture_PIE.json"}
