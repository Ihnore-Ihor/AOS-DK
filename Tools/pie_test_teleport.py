"""AOS-DK Lab 4 - PIE traversal test for the Evacuation Transit Shafts (driven by a slate post-tick state machine).
Usage (MCP execute_python):
    g = {"PT_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_teleport.py", encoding="utf-8").read(), g)
start : starts PIE, registers the recorder/driver (samples every editor tick).
poll  : returns the driver state + checks so far.   stop: ends PIE, writes Saved/Teleport_PIE.json.
Scenario: possess Shell-1 -> swim down into A's trigger (v 1200 cm/s) -> A->B transit -> re-enter B's trigger inside the
3 s cooldown (must be refused) -> leave, swim up into B's trigger after the cooldown -> B->A transit -> settle."""
import json, os
import unreal

MODE = globals().get("PT_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
LA, LB = "TP_Station_A_SurfaceSocket", "TP_Station_B_TowerA_C01"

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=0): return [round(v.x, n), round(v.y, n), round(v.z, n)]

def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()

def find(gw, label):
    for a in unreal.GameplayStatics.get_all_actors_of_class(gw, unreal.AOSTeleportStation):
        if a.get_actor_label() == label: return a
    return None

def fade_of(gw):
    return round(unreal.AOSTeleportStation.get_local_player_fade_amount(gw), 3)

def driver(dt):
    S = unreal._tp
    try:
        gw = game_world()
        if not gw: return
        t = unreal.GameplayStatics.get_time_seconds(gw)
        if S["state"] == "boot":
            pc = unreal.GameplayStatics.get_player_controller(gw, 0)
            shells = unreal.GameplayStatics.get_all_actors_of_class(gw, unreal.ShellPawn)
            A, B = find(gw, LA), find(gw, LB)
            if not (pc and shells and A and B) or t < 1.0: return
            S.update(pc=pc, shell=shells[0], A=A, B=B, root=shells[0].get_editor_property("box_root"))
            pc.possess(shells[0])
            S["state"] = "possessed"; S["t_state"] = t
            return
        sh, root, A, B, pc = S["shell"], S["root"], S["A"], S["B"], S["pc"]
        cam = pc.player_camera_manager
        smp = {"t": round(t, 3), "st": S["state"], "loc": vl(sh.get_actor_location()), "pitch": round(sh.get_actor_rotation().pitch, 1),
               "v": vl(root.get_physics_linear_velocity()) if root.is_simulating_physics() else None,
               "sim": root.is_simulating_physics(), "blk": sh.are_controls_blocked(), "fade": fade_of(gw),
               "pa": str(A.get_phase()).split(".")[-1][:6], "pb": str(B.get_phase()).split(".")[-1][:6],
               "cda": round(A.get_cooldown_remaining(), 2), "cdb": round(B.get_cooldown_remaining(), 2),
               "dep": [A.departure_count, B.departure_count], "arr": [A.arrival_count, B.arrival_count], "rej": [A.cooldown_reject_count, B.cooldown_reject_count]}
        S["samples"].append(smp)
        el = t - S["t_state"]
        st = S["state"]
        if st == "possessed" and el > 0.5:
            sh.set_actor_location_and_rotation(V(-58200, 0, -900), unreal.Rotator(0, 0, 180), False, True)
            root.set_physics_linear_velocity(V(0, 0, -1200)); root.set_physics_angular_velocity_in_degrees(V(0, 0, 0))
            S["state"] = "dive_A"; S["t_state"] = t; S["marks"]["dive_A"] = t
        elif st == "dive_A":
            if A.get_phase() != unreal.AOSTransitPhase.IDLE and "intake_A" not in S["marks"]:
                S["marks"]["intake_A"] = t; S["snap"]["intake_A"] = smp
            if A.departure_count >= 1:
                S["marks"]["arrive_B"] = t; S["snap"]["arrive_B"] = smp
                S["state"] = "arrived_B"; S["t_state"] = t
            elif el > 15: S["state"] = "fail_A"
        elif st == "arrived_B" and el > 0.4:
            # anti-loop: shove the Shell straight into B's trigger inside the cooldown
            S["snap"]["B_before_reentry"] = smp
            sh.set_actor_location(V(-58000, 22038, -9000), False, True)
            root.set_physics_linear_velocity(V(0, 0, 0))
            S["state"] = "reentry_B"; S["t_state"] = t; S["marks"]["reentry_B"] = t
        elif st == "reentry_B" and el > 1.0:
            S["snap"]["reentry_B_after_1s"] = smp
            sh.set_actor_location(V(-58000, 22038, -10200), False, True)   # leave the trigger (below)
            root.set_physics_linear_velocity(V(0, 0, 0))
            S["state"] = "wait_cd"; S["t_state"] = t
        elif st == "wait_cd" and B.get_cooldown_remaining() <= 0.0 and el > 0.2:
            S["marks"]["cooldown_B_over"] = t
            sh.set_actor_location_and_rotation(V(-58000, 22038, -9800), unreal.Rotator(0, 0, 0), False, True)
            root.set_physics_linear_velocity(V(0, 0, 1400))
            S["state"] = "rise_B"; S["t_state"] = t; S["marks"]["rise_B"] = t
        elif st == "rise_B":
            if B.get_phase() != unreal.AOSTransitPhase.IDLE and "intake_B" not in S["marks"]:
                S["marks"]["intake_B"] = t; S["snap"]["intake_B"] = smp
            if B.departure_count >= 1:
                S["marks"]["arrive_A"] = t; S["snap"]["arrive_A"] = smp
                S["state"] = "arrived_A"; S["t_state"] = t
            elif el > 15: S["state"] = "fail_B"
        elif st == "arrived_A" and el > 1.6:
            S["snap"]["A_settled"] = smp
            S["state"] = "done"
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error", "fail_A", "fail_B"):
        unreal.unregister_slate_post_tick_callback(S["handle"])

def checks(S):
    c = {}
    snap, sm = S["snap"], S["samples"]
    if "intake_A" in snap and "arrive_B" in snap:
        ta, tb = round(S["marks"]["intake_A"], 3), round(S["marks"]["arrive_B"], 3)
        c["A_to_B_duration_s"] = round(tb - ta, 2)
        c["arrive_B_loc"] = snap["arrive_B"]["loc"]; c["arrive_B_v"] = snap["arrive_B"]["v"]
        win = [s for s in sm if ta <= s["t"] < tb]
        c["A_controls_locked_whole_transit"] = all(s["blk"] for s in win)
        c["A_kinematic_whole_transit"] = all(not s["sim"] for s in win)
        c["A_fade_peak"] = max((s["fade"] or 0) for s in win) if win else None
        c["A_min_z_in_shaft"] = min(s["loc"][2] for s in win) if win else None
        c["blk_after_arrival_B"] = snap["arrive_B"]["blk"]
    if "B_before_reentry" in snap and "reentry_B_after_1s" in snap:
        c["B_cooldown_at_reentry_s"] = snap["B_before_reentry"]["cdb"]
        c["B_reentry_refused"] = snap["reentry_B_after_1s"]["pb"].startswith("IDLE") and snap["reentry_B_after_1s"]["dep"][1] == 0
        c["B_reject_count"] = snap["reentry_B_after_1s"]["rej"][1]
    if "intake_B" in snap and "arrive_A" in snap:
        ta, tb = round(S["marks"]["intake_B"], 3), round(S["marks"]["arrive_A"], 3)
        c["B_to_A_duration_s"] = round(tb - ta, 2)
        c["arrive_A_loc"] = snap["arrive_A"]["loc"]; c["arrive_A_v"] = snap["arrive_A"]["v"]
        win = [s for s in sm if ta <= s["t"] < tb]
        c["B_controls_locked_whole_transit"] = all(s["blk"] for s in win)
        c["B_fade_peak"] = max((s["fade"] or 0) for s in win) if win else None
        c["B_max_z_in_shaft"] = max(s["loc"][2] for s in win) if win else None
    if "A_settled" in snap:
        c["A_settled"] = snap["A_settled"]
    c["fps"] = round(len(sm) / max(0.01, sm[-1]["t"] - sm[0]["t"]), 1) if len(sm) > 1 else None
    return c

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._tp = {"state": "boot", "t_state": 0.0, "samples": [], "marks": {}, "snap": {},
                  "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)   # full frame rate while the editor is in the background
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._tp["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._tp
    result = {"state": S["state"], "error": S.get("error"), "n": len(S["samples"]), "last": S["samples"][-1] if S["samples"] else None,
              "marks": S["marks"], "checks": checks(S)}
elif MODE == "stop":
    S = unreal._tp
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = {"state": S["state"], "error": S.get("error"), "marks": S["marks"], "snap": S["snap"], "checks": checks(S),
           "samples": S["samples"][::2]}
    with open(os.path.join(PROJ, "Saved", "Teleport_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0)
    result = {"state": S["state"], "checks": out["checks"], "written": "Saved/Teleport_PIE.json"}
