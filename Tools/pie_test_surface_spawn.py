"""AOS-DK - PIE check that AAdminCharacter spawns on the open Atoll deck (no underwater geometry on the surface).
Usage (MCP execute_python):  g = {"SS_PIE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_surface_spawn.py", encoding="utf-8").read(), g); print(g["result"])
start: begin PIE + slate post-tick driver. poll: state + checks. stop: end PIE, write Saved/SurfaceSpawn_PIE.json.
Checks: pawn is AdminCharacter within 150 cm of PlayerStart_0, grounded (walking) on an Atoll floor, 8 horizontal probes (4 m) free, open sky
above (no hit up to +8000), a 2 s walk travels > 600 cm. Two high-res screenshots: Saved/Screenshots/WindowsEditor/surface_spawn_a.png / _b.png.
"""
import json, math, os, time
import unreal

MODE = globals().get("SS_PIE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SL = unreal.SystemLibrary
def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=1): return [round(v.x, n), round(v.y, n), round(v.z, n)]
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def ew(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
def tr(world, a, b, ign=()):
    h = SL.line_trace_single(world, a, b, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, list(ign), unreal.DrawDebugTrace.NONE, True)
    return None if h is None else h.to_tuple()

def tick(dt):
    S = unreal._ss
    if S.get("busy"): return
    try:
        w = gw()
        if w is None: return
        S["t"] += dt
        pawn = unreal.GameplayStatics.get_player_pawn(w, 0)
        if S["state"] == "wait_pawn":
            if pawn is not None and S["t"] > 1.0:
                S["spawn_loc"] = vl(pawn.get_actor_location()); S["pawn_class"] = pawn.get_class().get_name(); S["state"] = "settle"; S["t0"] = S["t"]
            elif S["t"] > 30: S["state"] = "done"; S["error"] = "no pawn spawned within 30 s"
        elif S["state"] == "settle":
            if S["t"] - S["t0"] > 2.0:
                L = pawn.get_actor_location(); S["settled_loc"] = vl(L)
                cm = pawn.get_component_by_class(unreal.CharacterMovementComponent)
                S["move_mode"] = str(cm.movement_mode)
                dn = tr(w, V(L.x, L.y, L.z), V(L.x, L.y, L.z - 400), [pawn])
                S["floor_actor"] = dn[9].get_name() if dn and dn[9] else None
                S["floor_z"] = round(dn[4].z, 1) if dn else None
                up = tr(w, V(L.x, L.y, L.z + 100), V(L.x, L.y, L.z + 8000), [pawn])
                S["sky_above_hit"] = (up[9].get_name() if up and up[9] else None) if up else None
                blocked = []
                for k in range(8):
                    a = math.radians(45 * k)
                    h = tr(w, V(L.x, L.y, L.z), V(L.x + 400 * math.cos(a), L.y + 400 * math.sin(a), L.z), [pawn])
                    if h: blocked.append((45 * k, round(math.hypot(h[4].x - L.x, h[4].y - L.y)), h[9].get_name() if h[9] else None))
                S["horizontal_probes_hit"] = blocked
                S["busy"] = True
                try: unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "surface_spawn_a.png")
                finally: S["busy"] = False
                S["start_walk_loc"] = vl(L); S["state"] = "walk"; S["t0"] = S["t"]
        elif S["state"] == "walk":
            pc = unreal.GameplayStatics.get_player_controller(w, 0)
            yaw = pc.get_control_rotation().yaw
            fwd = unreal.Rotator(0, yaw, 0).get_forward_vector() if hasattr(unreal.Rotator, "get_forward_vector") else V(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
            pawn.add_movement_input(fwd, 1.0, False)
            if S["t"] - S["t0"] > 2.0:
                L = pawn.get_actor_location(); S["end_walk_loc"] = vl(L)
                s = S["start_walk_loc"]; S["walk_distance_cm"] = round(math.hypot(L.x - s[0], L.y - s[1]), 1)
                S["busy"] = True
                try: unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "surface_spawn_b.png")
                finally: S["busy"] = False
                S["state"] = "done"
    except Exception as e:
        S["error"] = repr(e); S["state"] = "done"

def evaluate(S):
    ps = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_name() == "PlayerStart_0"][0].get_actor_location()
    d = math.hypot(S["spawn_loc"][0] - ps.x, S["spawn_loc"][1] - ps.y) if "spawn_loc" in S else None
    return {"pawn_is_AdminCharacter": "AdminCharacter" in S.get("pawn_class", ""), "spawn_xy_dist_to_PlayerStart_cm": None if d is None else round(d, 1),
            "grounded_walking": "WALKING" in S.get("move_mode", ""), "open_sky_above": S.get("sky_above_hit") is None, "horizontal_probes_free": not S.get("horizontal_probes_hit"),
            "walk_gt_600cm": S.get("walk_distance_cm", 0) > 600}

if MODE == "start":
    if hasattr(unreal, "_ss") and unreal._ss.get("handle") is not None:
        try: unreal.unregister_slate_post_tick_callback(unreal._ss["handle"])
        except Exception: pass
    unreal._ss = {"state": "wait_pawn", "t": 0.0, "busy": False, "handle": None}
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._ss["handle"] = unreal.register_slate_post_tick_callback(tick)
    result = {"started": True}
elif MODE == "poll":
    S = dict(unreal._ss); S.pop("handle", None); S["checks"] = evaluate(S) if S.get("state") == "done" else None; result = S
else:
    S = unreal._ss
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    out = {k: v for k, v in S.items() if k != "handle"}; out["checks"] = evaluate(S)
    json.dump(out, open(os.path.join(PROJ, "Saved", "SurfaceSpawn_PIE.json"), "w"), indent=1)
    result = out
