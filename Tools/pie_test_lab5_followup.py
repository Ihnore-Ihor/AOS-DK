"""AOS-DK Lab 5 follow-up PIE tests: F1 feet on the floor, F2 chase straight through the brine (calm = detour), F3 auto-respawn (6 s).
Usage: g = {"FT_MODE": "start"|"poll"|"stop"}; exec(open(r"<proj>/Tools/pie_test_lab5_followup.py", encoding="utf-8").read(), g)
Writes Saved/Lab5_Followup_PIE.json on stop."""
import json, os, math, re
import unreal

MODE = globals().get("FT_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
CX, CY, FLOOR = -43500.0, 22000.0, -9800.0
POOL = (CX, CY - 1300.0, 500.0, 400.0)                  # centre x/y, half extents
GS = unreal.GameplayStatics
def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def rnd(x, n=2): return None if x is None else round(float(x), n)
def in_pool(p, m=0.0): return abs(p[0] - POOL[0]) <= POOL[2] + m and abs(p[1] - POOL[1]) <= POOL[3] + m
def alive(): return [a for a in GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter) if not a.is_dead()]

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
    yield from until(lambda: GS.get_player_controller(gw(), 0) and GS.get_all_actors_of_class(gw(), unreal.ShellPawn) and alive() and now() > 1.5, 30)
    pc = GS.get_player_controller(gw(), 0); sh = GS.get_all_actors_of_class(gw(), unreal.ShellPawn)[0]
    r0 = alive()[0]; root = sh.get_editor_property("box_root")
    spawn0 = r0.get_actor_location()
    S["spawn0"] = [spawn0.x, spawn0.y, spawn0.z]
    pc.possess(sh); yield from wait(0.3)
    if sh.is_in_lars_cradle(): sh.leave_lars_cradle()
    root.set_simulate_physics(False)
    def put_shell(loc):
        S["lock"] = (loc, unreal.Rotator(0, 0, 0)); sh.set_actor_location_and_rotation(loc, unreal.Rotator(0, 0, 0), False, True)
    put_shell(V(CX + 6000, CY, FLOOR + 600))
    # ---- F1 feet ------------------------------------------------------------------------------------------------------------------
    S["feet"] = []; S["sample_feet"] = True
    yield from wait(14.0)
    S["sample_feet"] = False
    fr = S["feet"]
    planted3 = sum(1 for x in fr if sum(1 for g in x if g <= 1.5) >= 3)
    all6 = sum(1 for x in fr if max(x) <= 1.5)
    chk("F1.feet_planted_on_floor", len(fr) > 20 and planted3 == len(fr) and all6 > 0 and min(min(x) for x in fr) >= -1.5,
        {"samples": len(fr), "frames_with_>=3_pads_within_1.5cm": planted3, "frames_all_6_pads_within_1.5cm": all6,
         "min_pad_gap_cm": rnd(min(min(x) for x in fr), 2), "max_gap_of_the_3_lowest_pads_cm": rnd(max(sorted(x)[2] for x in fr), 2),
         "before_fix_gap_cm": "152-172 (log of earlier PIE: pad Z -9648 vs floor -9800)"})
    # ---- F2 chase through brine ---------------------------------------------------------------------------------------------------
    NS = unreal.NavigationSystemV1
    a, b = V(CX - 1300, CY - 1300, FLOOR + 10), V(CX + 1100, CY - 1300, FLOOR + 10)   # both ends outside the (agent-inflated) brine area
    def path(filt):
        p = NS.find_path_to_location_synchronously(gw(), a, b, r0, filt)
        pts = [(q.x, q.y, q.z) for q in p.path_points] if p and p.is_valid() else []
        return pts, (p.get_path_length() if p and p.is_valid() else None)
    calm_pts, calm_len = path(None)
    chase_pts, chase_len = path(unreal.AOS_NavFilter_ReaperChase.static_class())
    # sample the polylines for pool intersections
    def hits_pool(pts):
        for i in range(len(pts) - 1):
            for k in range(21):
                t = k / 20.0
                q = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
                if in_pool(q): return True
        return False
    chk("F2.calm_path_detours_pool", len(calm_pts) > 1 and not hits_pool(calm_pts), {"len_cm": rnd(calm_len, 0), "points": len(calm_pts), "crosses_pool": hits_pool(calm_pts)})
    chk("F2.chase_path_goes_through_pool", len(chase_pts) > 1 and hits_pool(chase_pts) and chase_len < (calm_len or 1e9), {"len_cm": rnd(chase_len, 0), "points": len(chase_pts), "crosses_pool": hits_pool(chase_pts)})
    # live chase: Reaper west of the pool, Shell east of it (2400 cm, inside the 2600 sight; headlights are on)
    r = alive()[0]; ctl = r.get_controller(); brain = ctl.get_editor_property("brain_component")
    brain.stop_logic("t"); r.set_actor_location_and_rotation(V(CX - 1300, CY - 1300, FLOOR + 145), unreal.Rotator(0, 0, 0), False, True)
    put_shell(V(CX + 6000, CY, FLOOR + 600)); yield from wait(1.0)
    S["chase"] = {"max_x": -1e9, "hazard": False, "in_pool_t": 0.0, "min_dy": 1e9, "samples": []}
    brain.restart_logic(); yield from wait(1.0)
    S["track_chase"] = True
    rp = r.get_actor_location()
    put_shell(V(CX + 1100, CY - 1300, rp.z))
    yield from until(lambda: S["chase"]["max_x"] > CX + 300 or r.is_dead(), 30)
    yield from wait(0.5)
    S["track_chase"] = False
    ch = S["chase"]
    chk("F2.chase_enters_brine_and_crosses", ch["hazard"] and ch["max_x"] > CX + 300 and ch["min_dy"] < 300, {"entered_hazard": ch["hazard"], "max_x_rel_pool_centre": rnd(ch["max_x"] - CX, 0), "closest_to_pool_axis_cm": rnd(ch["min_dy"], 0), "time_in_hazard_s": rnd(ch["in_pool_t"], 2), "note": "Reaper stops at strike standoff ~690 cm before the Shell, i.e. past the pool centre"})
    # live calm patrol: never enters the pool during the SW->SE leg
    put_shell(V(CX + 6000, CY, FLOOR + 600)); brain.stop_logic("t")
    nodes = [a for a in unreal.EditorLevelLibrary.get_all_level_actors() if False] if False else []
    r.set_actor_location_and_rotation(V(CX - 1300, CY - 1300, FLOOR + 145), unreal.Rotator(0, 0, 0), False, True); yield from wait(1.0)
    brain.restart_logic()
    S["patrol"] = {"hazard": False, "max_x": -1e9, "t": 0.0}; S["track_patrol"] = True
    yield from until(lambda: S["patrol"]["max_x"] > CX + 600, 70)
    S["track_patrol"] = False
    pt = S["patrol"]
    chk("F2.patrol_routes_around_brine", pt["max_x"] > CX + 600 and not pt["hazard"], {"entered_hazard": pt["hazard"], "reached_east_of_pool": pt["max_x"] > CX + 600, "max_x_rel_pool_centre": rnd(pt["max_x"] - CX, 0)})
    # ---- F3 respawn ---------------------------------------------------------------------------------------------------------------
    put_shell(V(CX + 6000, CY, FLOOR + 600))
    rounds = []
    for k in range(2):
        cur = alive()[0]; pid_before = cur.get_pid()
        t0 = now()
        GS.apply_damage(cur, 100000.0, None, None, unreal.DamageType.static_class())
        yield from until(lambda: cur.is_dead(), 2)
        dead_ok = cur.is_dead()
        S["t_dead"] = now()
        ok = yield from until(lambda: len(alive()) == 1 and alive()[0].get_pid() != pid_before, 12)
        t1 = now() - t0
        yield from wait(1.5)
        n = alive()
        new = n[0] if n else None
        loc = new.get_actor_location() if new else None
        sp = S["spawn0"]
        rounds.append({"killed_pid": pid_before, "dead_flag": dead_ok, "respawned": ok, "delay_s": rnd(t1, 2), "new_pid": new.get_pid() if new else None,
                       "hp": new.get_health() if new else None, "max_hp": new.get_max_health() if new else None, "charges": new.evasion.get_charges() if new else None,
                       "dist_to_spawn_cm": rnd(math.hypot(loc.x - sp[0], loc.y - sp[1]), 0) if loc else None, "phase": new.get_phase().name if new else None,
                       "alive_count": len(n), "has_controller": bool(new and new.get_controller()), "weapon": bool(new and new.get_editor_property("weapon"))})
    good = all(x["dead_flag"] and x["respawned"] and 5.5 <= x["delay_s"] <= 6.6 and x["hp"] == 168.0 and x["charges"] == 3 and x["dist_to_spawn_cm"] is not None and x["dist_to_spawn_cm"] < 80
               and x["alive_count"] == 1 and x["has_controller"] and x["weapon"] for x in rounds)
    chk("F3.auto_respawn_6s_full_hp_3_charges", good, rounds)
    S["lock"] = None
    S["state"] = "done"

def driver(dt):
    S = unreal._ft
    try:
        w = gw()
        if not w: return
        if S["gen"] is None:
            S["gen"] = scenario(S); S["state"] = "running"
        t = GS.get_time_seconds(w)
        lk = S.get("lock")
        shs = GS.get_all_actors_of_class(w, unreal.ShellPawn)
        if lk and shs: shs[0].set_actor_location_and_rotation(lk[0], lk[1], False, True)
        al = alive()
        if al:
            r = al[0]
            if S.get("sample_feet"):
                S["feet"].append([round(r.mesh.get_socket_location("SOCKET_Foot_" + n).z - FLOOR, 2) for n in ("L1", "L2", "L3", "R1", "R2", "R3")])
            p = r.get_actor_location()
            if S.get("track_chase"):
                C = S["chase"]; C["max_x"] = max(C["max_x"], p.x); C["hazard"] = C["hazard"] or r.is_in_hazard()
                if r.is_in_hazard(): C["in_pool_t"] += dt
                C["min_dy"] = min(C["min_dy"], abs(p.y - POOL[1]) if abs(p.x - POOL[0]) < 200 else 1e9)
            if S.get("track_patrol"):
                P = S["patrol"]; P["max_x"] = max(P["max_x"], p.x); P["hazard"] = P["hazard"] or r.is_in_hazard()
        try: next(S["gen"])
        except StopIteration: S["state"] = "done"
    except Exception as e:
        import traceback
        S["error"] = traceback.format_exc()[-900:]; S["state"] = "error"
    if S["state"] in ("done", "error"):
        try: unreal.unregister_slate_post_tick_callback(S["handle"])
        except Exception: pass

def summary(S):
    R = S["results"]
    return {"state": S["state"], "error": S.get("error"), "n": len(R), "passed": sum(1 for x in R if x["ok"]), "failed": [x["id"] for x in R if not x["ok"]]}

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._ft = {"state": "boot", "gen": None, "results": [], "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.is_in_play_in_editor(): les.editor_request_begin_play()
    unreal._ft["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._ft; result = {**summary(S), "last": S["results"][-1] if S["results"] else None}
elif MODE == "stop":
    S = unreal._ft
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = {**summary(S), "results": S["results"]}
    with open(os.path.join(PROJ, "Saved", "Lab5_Followup_PIE.json"), "w", encoding="utf-8") as f: json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Lab5_Followup_PIE.json"}
