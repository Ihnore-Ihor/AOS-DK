"""AOS-DK Surface Fall Recovery - PIE test (slate post-tick state machine).
Usage (MCP execute_python):
    g = {"FR_PIE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_fall_recovery.py", encoding="utf-8").read(), g); print(g["result"])
start : picks a walking heading on the deck that ends at a pontoon edge, starts PIE and registers the driver.
poll  : state + checks so far.   stop: ends PIE, writes Saved/FallRecovery_PIE.json.
Scenario: AAdminCharacter walks along the heading (AddMovementInput) -> SafeGround poses are recorded in the ring ->
the character walks off the pontoon edge into the water -> volume overlap -> lock + fade out -> teleport to the newest
SafeGround pose -> fade in -> control restored. Then the ring is cleared and the character is dropped into the water again:
the fallback must be PlayerStart_0. Checks: poses are on SafeGround, return time <= 1.0 s, fade peak ~1, move/look input ignored
during the recovery and restored after it, no sinking.
"""
import json, math, os
import unreal

MODE = globals().get("FR_PIE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SL = unreal.SystemLibrary


def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=1): return [round(v.x, n), round(v.y, n), round(v.z, n)]
def game_world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def editor_world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def trace_down(world, x, y, z0, z1):
    h = SL.line_trace_single(world, V(x, y, z0), V(x, y, z1), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], unreal.DrawDebugTrace.NONE, True)
    if h is None:
        return None
    t = h.to_tuple()
    return t if t[0] else None


def floor_info(world, x, y, z):
    t = trace_down(world, x, y, z + 60, z - 200)
    if not t or t[9] is None:
        return {"hit": False}
    tags = set(str(a) for a in t[9].tags) | (set(str(a) for a in t[10].component_tags) if t[10] else set())
    return {"hit": True, "z": round(t[4].z, 1), "actor": t[9].get_actor_label(), "safe": "SafeGround" in tags}


def pick_heading(sx, sy):
    """First direction (15 deg steps) with a clean walkable run to an edge 300..1500 cm away. Returns (yaw_deg, edge_dist)."""
    w = editor_world()
    def sz(x, y):
        t = trace_down(w, x, y, 500, -500)
        return t[4].z if t else None
    for k in range(24):
        a = math.radians(k * 15)
        dx, dy = math.cos(a), math.sin(a)
        prev = sz(sx, sy)
        for dist in range(20, 1600, 20):
            z = sz(sx + dx * dist, sy + dy * dist)
            if z is None or z < 0:
                if 300 <= dist <= 1500:
                    return k * 15, dist
                break
            if abs(z - prev) > 40:
                break
            prev = z
    return None, None


def driver(dt):
    S = unreal._fr
    try:
        gw = game_world()
        if not gw:
            return
        t = unreal.GameplayStatics.get_time_seconds(gw)
        st = S["state"]
        if st == "boot":
            pc = unreal.GameplayStatics.get_player_controller(gw, 0)
            pawn = unreal.GameplayStatics.get_player_pawn(gw, 0)
            if not pawn or t < 1.0:
                return
            if not isinstance(pawn, unreal.AdminCharacter):
                S["error"] = "pawn is " + pawn.get_class().get_name(); S["state"] = "error"
                return
            S.update(pc=pc, pawn=pawn, tracker=pawn.get_safe_ground_tracker(), move=pawn.get_component_by_class(unreal.CharacterMovementComponent))
            S["start_loc"] = vl(pawn.get_actor_location())
            S["state"] = "walk"; S["t_state"] = t
            return
        pawn, pc, tr, mv = S["pawn"], S["pc"], S["tracker"], S["move"]
        loc = pawn.get_actor_location()
        cam = pc.player_camera_manager
        fade = round(float(unreal.AOSTeleportStation.get_local_player_fade_amount(gw)), 3)
        rec = bool(tr.is_recovering())
        smp = {"t": round(t, 3), "st": st, "loc": vl(loc), "v": vl(mv.get_editor_property("velocity")), "mode": str(mv.get_editor_property("movement_mode")).split(".")[-1],
               "rec": rec, "n": tr.get_num_safe_transforms(), "fade": fade, "imi": bool(pc.is_move_input_ignored()), "ili": bool(pc.is_look_input_ignored())}
        S["samples"].append(smp)
        S["min_z"] = min(S["min_z"], loc.z)
        el = t - S["t_state"]
        if st == "walk":
            h = math.radians(S["yaw"])
            pawn.add_movement_input(V(math.cos(h), math.sin(h), 0), 1.0, False)
            if "ring_snap" not in S and el > 2.5 and smp["n"] >= 4:
                poses = tr.get_safe_transforms_newest_first()
                S["ring_snap"] = [{"loc": vl(p.translation), "yaw": round(p.rotation.rotator().yaw, 1), "floor": floor_info(gw, p.translation.x, p.translation.y, p.translation.z - 96)} for p in poses]
                S["ring_snap_t"] = t
            if rec:
                S["marks"]["recovery_begin"] = t; S["fall_loc"] = vl(loc)
                S["last_ring"] = [vl(p.translation) for p in tr.get_safe_transforms_newest_first()]
                S["state"] = "recovering"; S["t_state"] = t
            elif el > 25:
                S["state"] = "fail_no_fall"
        elif st == "recovering":
            if not rec:
                S["marks"]["recovery_end"] = t
                S["state"] = "settle"; S["t_state"] = t
        elif st == "settle" and el > 1.5:
            S["final"] = {"loc": vl(loc), "v": smp["v"], "mode": smp["mode"], "floor": floor_info(gw, loc.x, loc.y, loc.z - 96), "fade": fade,
                          "imi": smp["imi"], "ili": smp["ili"]}
            # scenario 2: empty ring -> fallback to PlayerStart_0
            tr.clear_safe_transforms()
            S["fb_empty"] = tr.get_num_safe_transforms()
            pawn.set_actor_location(V(2661.5, 1265.2, 60.0), False, True)
            S["state"] = "fb_wait_begin"; S["t_state"] = t
        elif st == "fb_wait_begin":
            if rec:
                S["marks"]["fb_begin"] = t; S["state"] = "fb_recovering"; S["t_state"] = t
            elif el > 5:
                S["state"] = "fail_fallback"
        elif st == "fb_recovering":
            if not rec:
                S["marks"]["fb_end"] = t; S["state"] = "fb_settle"; S["t_state"] = t
        elif st == "fb_settle" and el > 1.5:
            S["fb_final"] = {"loc": vl(loc), "mode": smp["mode"], "floor": floor_info(gw, loc.x, loc.y, loc.z - 96), "imi": smp["imi"], "ili": smp["ili"]}
            starts = unreal.GameplayStatics.get_all_actors_of_class(gw, unreal.PlayerStart)
            S["fb_start"] = vl(starts[0].get_actor_location()) if starts else None
            S["state"] = "done"
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error", "fail_no_fall", "fail_fallback"):
        unreal.unregister_slate_post_tick_callback(S["handle"])


def checks(S):
    c = {}
    sm = S["samples"]
    if "ring_snap" in S:
        rs = S["ring_snap"]
        c["ring_entries_at_snapshot"] = len(rs)
        c["ring_all_on_SafeGround"] = all(r["floor"].get("safe") for r in rs)
        c["ring_floor_actors"] = sorted(set(r["floor"].get("actor") for r in rs))
    if "recovery_begin" in S["marks"]:
        c["fall_loc"] = S["fall_loc"]
        c["edge_pose_newest"] = S["last_ring"][0] if S.get("last_ring") else None
    if "recovery_end" in S["marks"]:
        dur = S["marks"]["recovery_end"] - S["marks"]["recovery_begin"]
        c["recovery_duration_s"] = round(dur, 3)
        c["return_within_1s"] = dur <= 1.0 + 0.1   # one frame of slack (timers fire on the next tick after the fade length)
        win = [s for s in sm if S["marks"]["recovery_begin"] <= s["t"] <= S["marks"]["recovery_end"]]
        c["fade_peak"] = max((s["fade"] or 0) for s in win) if win else None
        c["fade_returns_to_0"] = (S["final"]["fade"] == 0.0) if "final" in S else None
        c["input_ignored_during_recovery"] = all(s["imi"] and s["ili"] for s in win if s["t"] < S["marks"]["recovery_end"] - 0.06) if win else None
        c["movement_frozen_during_recovery(NONE)"] = all("NONE" in s["mode"] for s in win if S["marks"]["recovery_begin"] + 0.06 < s["t"] < S["marks"]["recovery_end"] - 0.06)
        c["modes_during_recovery"] = sorted(set(s["mode"] for s in win))
        c["fall_to_end_samples"] = len(win)
    if "final" in S:
        f, tgt = S["final"], (S.get("last_ring") or [None])[0]
        c["final"] = f
        if tgt:
            c["final_xy_distance_to_newest_pose"] = round(math.hypot(f["loc"][0] - tgt[0], f["loc"][1] - tgt[1]), 1)
            c["final_dz_to_newest_pose"] = round(f["loc"][2] - tgt[2], 1)
        c["final_on_SafeGround"] = bool(f["floor"].get("safe"))
        c["final_speed"] = round(math.sqrt(sum(x * x for x in f["v"])), 2)
        c["final_mode_walking"] = "WALKING" in f["mode"].upper()
        c["input_restored_after_recovery"] = (not f["imi"]) and (not f["ili"])
    if "fb_final" in S:
        f, st0 = S["fb_final"], S.get("fb_start")
        c["fallback_ring_was_empty"] = S.get("fb_empty") == 0
        c["fallback_final"] = f
        c["fallback_playerstart"] = st0
        if st0:
            c["fallback_xy_distance_to_PlayerStart"] = round(math.hypot(f["loc"][0] - st0[0], f["loc"][1] - st0[1]), 1)
        c["fallback_on_SafeGround"] = bool(f["floor"].get("safe"))
        c["fallback_duration_s"] = round(S["marks"]["fb_end"] - S["marks"]["fb_begin"], 3) if "fb_end" in S["marks"] else None
        c["fallback_input_restored"] = (not f["imi"]) and (not f["ili"])
    c["min_capsule_center_z"] = round(S["min_z"], 1)
    c["never_sank_into_abyss"] = S["min_z"] > -300.0
    c["fps"] = round(len(sm) / max(0.01, sm[-1]["t"] - sm[0]["t"]), 1) if len(sm) > 1 else None
    return c


if MODE == "start":
    yaw, dist = pick_heading(1000.0, 820.0)
    if yaw is None:
        result = {"started": False, "error": "no heading to an edge found"}
    else:
        ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
        unreal._fr = {"state": "boot", "t_state": 0.0, "samples": [], "marks": {}, "min_z": 1e9, "yaw": yaw, "edge_dist": dist,
                      "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
        ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
        unreal._fr["handle"] = unreal.register_slate_post_tick_callback(driver)
        result = {"started": True, "heading_yaw": yaw, "edge_distance_cm": dist}
elif MODE == "poll":
    S = unreal._fr
    result = {"state": S["state"], "error": S.get("error"), "n": len(S["samples"]), "last": S["samples"][-1] if S["samples"] else None,
              "marks": S["marks"], "checks": checks(S)}
elif MODE == "stop":
    S = unreal._fr
    try:
        unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception:
        pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = {"state": S["state"], "error": S.get("error"), "yaw": S["yaw"], "edge_dist": S["edge_dist"], "start_loc": S.get("start_loc"), "marks": S["marks"],
           "ring_snap": S.get("ring_snap"), "checks": checks(S), "samples": S["samples"][::2]}
    with open(os.path.join(PROJ, "Saved", "FallRecovery_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0)
    result = {"state": S["state"], "checks": out["checks"], "written": "Saved/FallRecovery_PIE.json"}
