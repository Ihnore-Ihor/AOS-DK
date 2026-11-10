"""AOS-DK - PIE test of the rapid-test transit layout (Station A at the Shell berth, Station B at the C-01 SomaLock).
Usage (MCP execute_python):
    g = {"PR_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_teleport_rapid.py", encoding="utf-8").read(), g)
Scenario (real pilot input through Enhanced Input injection, no teleporting the hull):
  possess Shell-1 at its berth -> shot of the start view -> a simple "pilot": full forward thrust (IA_Sub_Move), yaw onto
  the mouth (IA_Sub_Rotate, P-control) and hold the lens depth (IA_Sub_Ballast, P-control) -> time until
  Station A's intake starts (must be < 5 s) -> A->B transit -> arrival in front of the SomaLock (shot, distance, heading)
  -> after B's cooldown the Shell is placed 6 m outside B's mouth facing it and swims in -> B->A -> arrival at the berth.
stop: ends PIE, writes Saved/TeleportRapid_PIE.json."""
import json, os, math
import unreal

MODE = globals().get("PR_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
LA, LB, LOCK = "TP_Station_A_SurfaceSocket", "TP_Station_B_TowerA_C01", "PRT_SomaLock_Main"
DIVE_S = float(globals().get("PR_DIVE_S", 1.0))
SHOTDIR = os.path.join(PROJ, "Saved", "Screenshots", "WindowsEditor")

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=0): return [round(v.x, n), round(v.y, n), round(v.z, n)]
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def find(w, label, cls):
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, cls):
        if a.get_actor_label() == label: return a
    return None
def input_subsystem(imc):
    """EnhancedInputLocalPlayerSubsystem of the PIE local player that has the Shell's IMC applied
    (USubsystemBlueprintLibrary is not exposed to Python; stale LocalPlayers of earlier PIE sessions linger)."""
    for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem):
        if s.get_outer().get_class().get_name() != "Package" and s.has_mapping_context(imc) is not None:
            return s
    return None
def shots():
    try: return set(f for f in os.listdir(SHOTDIR) if f.lower().endswith(".png"))
    except Exception: return set()
def shot(S, w, tag):
    S["pending_shot"] = (tag, shots()); unreal.SystemLibrary.execute_console_command(w, "shot")

def pilot(S, sh, aim, depth_z, clear_z=None):
    """W + mouse + Space/Shift: yaw onto the aim point, ballast to the lens depth, and - leaving the berth - creep until
    the hull is below the pier slab (Floor2, bottom at ~-20 cm, 3 m ahead of the berth), then full thrust."""
    sub = S["sub"]; p = sh.get_actor_location(); r = sh.get_actor_rotation()
    want = math.degrees(math.atan2(aim.y - p.y, aim.x - p.x))
    err = (want - r.yaw + 540.0) % 360.0 - 180.0
    thrust = 1.0 if clear_z is None or p.z < clear_z else 0.0
    sub.inject_input_vector_for_action(S["move"], V(thrust, 0, 0), [], [])
    # Rotate = (roll, pitch, yaw) torques; +pitch torque about +Y dips the nose, so rawY = +pitch keeps the nose level.
    w = S["root"].get_physics_angular_velocity_in_degrees() if S["root"].is_simulating_physics() else V(0, 0, 0)
    yaw_cmd = S.get("yaw_sign", 1.0) * max(-1.0, min(1.0, err / 25.0 - w.z / 45.0))   # PD on heading, sign from the calibration
    sub.inject_input_vector_for_action(S["rotate"], V(0, max(-1.0, min(1.0, r.pitch / 8.0)), yaw_cmd), [], [])
    dz = depth_z - p.z
    if abs(dz) > 40.0: sub.inject_input_vector_for_action(S["ballast"], V(max(-1.0, min(1.0, dz / 150.0)), 0, 0), [], [])

def driver(dt):
    S = unreal._pr
    try:
        w = gw()
        if not w: return
        t = unreal.GameplayStatics.get_time_seconds(w)
        if S.get("pending_shot"):
            tag, before = S["pending_shot"]; new = shots() - before
            if new: S["shots"][tag] = sorted(new)[-1]; S["pending_shot"] = None
        if S["state"] == "boot":
            pc = unreal.GameplayStatics.get_player_controller(w, 0)
            shells = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ShellPawn)
            A, B = find(w, LA, unreal.AOSTeleportStation), find(w, LB, unreal.AOSTeleportStation)
            lock = find(w, LOCK, unreal.StaticMeshActor)
            if not (pc and shells and A and B) or t < 1.0: return
            sh = shells[0]
            pc.possess(sh)
            sub = input_subsystem(sh.get_editor_property("sub_mapping_context"))
            if not sub: return
            S.update(pc=pc, shell=sh, A=A, B=B, lock=lock, sub=sub, root=sh.get_editor_property("box_root"),
                     move=sh.get_editor_property("move_action"), ballast=sh.get_editor_property("ballast_action"),
                     rotate=sh.get_editor_property("rotate_action"))
            S["state"] = "settle"; S["t_state"] = t; S["start_loc"] = vl(sh.get_actor_location())
            return
        sh, A, B, sub = S["shell"], S["A"], S["B"], S["sub"]
        el = t - S["t_state"]; st = S["state"]
        smp = {"t": round(t, 3), "st": st, "loc": vl(sh.get_actor_location()), "yaw": round(sh.get_actor_rotation().yaw, 1),
               "pa": str(A.get_phase()).split(".")[-1][:6], "pb": str(B.get_phase()).split(".")[-1][:6], "blk": sh.are_controls_blocked(),
               "dep": [A.departure_count, B.departure_count]}
        S["samples"].append(smp)
        if st == "settle" and el > 1.5:
            shot(S, w, "start_view")
            S["yaw0"] = sh.get_actor_rotation().yaw
            S["state"] = "calib"; S["t_state"] = t
        elif st == "calib":
            # which way does +yaw input turn the hull? (one 0.3 s mouse flick, then let it settle)
            if el < 0.3: sub.inject_input_vector_for_action(S["rotate"], V(0, 0, 1), [], [])
            elif el > 0.6:
                d = (sh.get_actor_rotation().yaw - S["yaw0"] + 540.0) % 360.0 - 180.0
                S["yaw_sign"] = 1.0 if d >= 0 else -1.0; S["marks"]["yaw_calib_deg"] = round(d, 2)
                S["state"] = "drive_A"; S["t_state"] = t; S["t_drive"] = t
        elif st == "drive_A":
            if not sh.are_controls_blocked():
                pilot(S, sh, A.get_actor_location() - A.get_entry_vector() * 900.0, A.get_actor_location().z, clear_z=-200.0)
            if A.get_phase() != unreal.AOSTransitPhase.IDLE and "intake_A" not in S["marks"]:
                S["marks"]["intake_A"] = round(t - S["t_drive"], 2); S["snap"]["intake_A"] = smp
            if A.departure_count >= 1:
                S["marks"]["arrive_B"] = round(t - S["t_drive"], 2); S["snap"]["arrive_B"] = smp
                S["state"] = "at_B"; S["t_state"] = t
            elif el > 12: S["state"] = "fail_A"
        elif st == "at_B" and el > 2.0:
            S["snap"]["B_settled"] = smp
            if S["lock"]:
                face = S["lock"].get_actor_location().x - 711.0
                S["snap"]["B_settled"]["nose_to_lock_face_m"] = round((face - (sh.get_actor_location().x + 200.0)) / 100.0, 2)
                S["snap"]["B_settled"]["lateral_off_axis_cm"] = [round(sh.get_actor_location().y - 22200.0), round(sh.get_actor_location().z + 9150.0)]
            shot(S, w, "arrive_B_view")
            S["state"] = "wait_cd"; S["t_state"] = t
        elif st == "wait_cd" and B.get_cooldown_remaining() <= 0.0 and el > 0.5:
            mouth = B.get_actor_location() - B.get_entry_vector() * (711.0 + 500.0 + 600.0)
            sh.set_actor_location_and_rotation(mouth, unreal.MathLibrary.make_rot_from_x(B.get_entry_vector()), False, True)
            S["root"].set_physics_linear_velocity(V(0, 0, 0)); S["root"].set_physics_angular_velocity_in_degrees(V(0, 0, 0))
            S["state"] = "drive_B"; S["t_state"] = t
        elif st == "drive_B":
            if not sh.are_controls_blocked(): pilot(S, sh, B.get_actor_location(), B.get_actor_location().z)
            if B.departure_count >= 1:
                S["marks"]["B_to_A_after_s"] = round(el, 2); S["snap"]["arrive_A"] = smp
                S["state"] = "at_A"; S["t_state"] = t
            elif el > 12: S["state"] = "fail_B"
        elif st == "at_A" and el > 2.0:
            S["snap"]["A_settled"] = smp; shot(S, w, "arrive_A_view")
            S["state"] = "done_wait"; S["t_state"] = t
        elif st == "done_wait" and el > 1.0:
            S["state"] = "done"
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error", "fail_A", "fail_B"):
        unreal.unregister_slate_post_tick_callback(S["handle"])

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._pr = {"state": "boot", "t_state": 0.0, "samples": [], "marks": {}, "snap": {}, "shots": {}, "pending_shot": None,
                  "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._pr["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._pr
    result = {"state": S["state"], "error": S.get("error"), "marks": S["marks"], "snap": S["snap"], "shots": S["shots"],
              "last": S["samples"][-1] if S["samples"] else None}
elif MODE == "stop":
    S = unreal._pr
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = {"state": S["state"], "error": S.get("error"), "start_loc": S.get("start_loc"), "marks": S["marks"], "snap": S["snap"],
           "shots": S["shots"], "samples": S["samples"][::3]}
    with open(os.path.join(PROJ, "Saved", "TeleportRapid_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0)
    result = {"state": S["state"], "marks": S["marks"], "snap": S["snap"], "shots": S["shots"], "written": "Saved/TeleportRapid_PIE.json"}
