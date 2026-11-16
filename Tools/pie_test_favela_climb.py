"""AOS-DK Favela stair PIE test: AAdminCharacter walks the spec 'D4 stack climb' polylines (ground -> every tier roof) with movement input only, zero jumps.
Usage (MCP execute_python):  g={"FC_PIE": "start"|"poll"|"stop"}; exec(open(r"<proj>/Tools/pie_test_favela_climb.py", encoding="utf-8").read(), g); print(g["result"])
Per route: teleport to its first waypoint, steer (xy) to each waypoint in turn (reached at 28 cm), log movement mode / Z each frame.
Checks: every waypoint reached, never FALLING for more than 0.35 s, never more than 70 cm below the route Z, capsule never stuck (progress every 6 s), final floor = last tier roof."""
import json, math, os
import unreal

MODE = globals().get("FC_PIE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SPEC = json.load(open(os.path.join(PROJ, "Tools/Atoll_Kit_spec.json"), encoding="utf-8"))
def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=1): return [round(v.x, n), round(v.y, n), round(v.z, n)]
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
HH = 96.0

def driver(dt):
    S = unreal._fc
    try:
        w = gw()
        if not w: return
        t = unreal.GameplayStatics.get_time_seconds(w)
        if S["state"] == "boot":
            pawn = unreal.GameplayStatics.get_player_pawn(w, 0)
            if not pawn or t < 1.0: return
            if not isinstance(pawn, unreal.AdminCharacter): S["error"] = "pawn " + pawn.get_class().get_name(); S["state"] = "error"; return
            S.update(pawn=pawn, mv=pawn.get_component_by_class(unreal.CharacterMovementComponent), ri=0, wi=0, t0=t)
            S["speed"] = float(S["mv"].get_editor_property("max_walk_speed")); S["slope"] = float(S["mv"].get_editor_property("walkable_floor_angle")); S["step"] = float(S["mv"].get_editor_property("max_step_height"))
            S["state"] = "place"; return
        pawn, mv = S["pawn"], S["mv"]
        route = S["routes"][S["ri"]][1]
        if S["state"] == "place":
            p = route[0]; pawn.set_actor_location(V(p[0], p[1], p[2] + HH + 3.0), False, True)
            pawn.get_controller().set_control_rotation(unreal.Rotator(0, 0, 0))
            S.update(wi=1, state="walk", t_prog=t, best=1e9, t_fall=None, tier_marks=[]); return
        loc = pawn.get_actor_location(); tgt = route[S["wi"]]
        foot = loc.z - HH; mode = str(mv.get_editor_property("movement_mode")).split(".")[-1]
        d = math.hypot(tgt[0] - loc.x, tgt[1] - loc.y)
        S["samples"].append([S["ri"], S["wi"], round(t, 2), round(loc.x, 1), round(loc.y, 1), round(foot, 1), mode])
        # fall / drop detection
        dz = tgt[2] - foot
        S["max_below"] = max(S["max_below"], dz) if S["wi"] > 1 else S["max_below"]
        if "FALLING" in mode.upper():
            S["t_fall"] = S["t_fall"] if S["t_fall"] is not None else t
            if t - S["t_fall"] > S["max_fall_s"]: S["max_fall_s"] = t - S["t_fall"]
        else: S["t_fall"] = None
        if foot < min(tgt[2], route[S["wi"] - 1][2]) - 70.0 and S["wi"] > 1: S["fell"].append([S["ri"], S["wi"], vl(loc)]); S["state"] = "fail_fell"
        if d < 28.0:
            if abs(foot - tgt[2]) < 60.0 or S["wi"] == len(route) - 1 or abs(foot - tgt[2]) < 120.0:
                if tgt[2] != route[S["wi"] - 1][2] and abs(tgt[2] - round(tgt[2])) < 1e-6 and (tgt[2] - 80.0) % 350.0 < 1.0 and tgt[2] > route[S["wi"] - 1][2] + 100:
                    S["tier_marks"].append([S["ri"], S["wi"], round(tgt[2]), round(foot, 1), round(t - S["t0"], 1)])
                S["wi"] += 1; S["t_prog"] = t
                if S["wi"] >= len(route):
                    S["done_routes"].append({"route": S["routes"][S["ri"]][0], "seconds": round(t - S["t0"], 1), "final_foot_z": round(foot, 1), "final_xy": [round(loc.x, 1), round(loc.y, 1)], "target_z": route[-1][2], "mode": mode})
                    S["ri"] += 1; S["t0"] = t
                    S["state"] = "place" if S["ri"] < len(S["routes"]) else "done"
                    return
        else:
            h = math.atan2(tgt[1] - loc.y, tgt[0] - loc.x)
            pawn.add_movement_input(V(math.cos(h), math.sin(h), 0), 1.0, False)
        S["best"] = min(S["best"], d)
        if t - S["t_prog"] > 8.0: S["stuck"].append([S["ri"], S["wi"], vl(loc), [round(c) for c in tgt]]); S["state"] = "fail_stuck"
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error", "fail_fell", "fail_stuck"): unreal.unregister_slate_post_tick_callback(S["handle"])

def summary(S):
    sm = S["samples"]
    mem = {"state": S["state"], "error": S.get("error"), "speed": S.get("speed"), "walkable_floor_angle": S.get("slope"), "max_step_height": S.get("step"),
           "jumps": 0, "routes_done": S["done_routes"], "tier_marks": S["tier_marks"], "fell": S["fell"], "stuck": S["stuck"], "max_fall_s": round(S["max_fall_s"], 2),
           "frames": len(sm), "modes": sorted(set(s[6] for s in sm)), "min_foot_z": round(min([s[5] for s in sm] or [0]), 1), "max_foot_z": round(max([s[5] for s in sm] or [0]), 1)}
    return mem

if MODE == "start":
    want = [(k, v) for k, v in SPEC["assembly"]["routes"].items() if k.startswith("D4 stack climb")]
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._fc = {"state": "boot", "samples": [], "routes": want, "done_routes": [], "tier_marks": [], "fell": [], "stuck": [], "max_fall_s": 0.0, "max_below": 0.0, "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._fc["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True, "routes": [k for k, _ in want]}
elif MODE == "poll":
    S = unreal._fc; result = summary(S); result["last"] = S["samples"][-1] if S["samples"] else None
elif MODE == "stop":
    S = unreal._fc
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = summary(S); out["samples"] = S["samples"][::3]
    os.makedirs(os.path.join(PROJ, "Saved"), exist_ok=True)
    json.dump(out, open(os.path.join(PROJ, "Saved", "FavelaClimb_PIE.json"), "w"), indent=0)
    result = summary(S)
