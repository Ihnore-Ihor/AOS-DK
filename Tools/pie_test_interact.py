"""AOS-DK - PIE test of the [F] reticle interaction (pickups salvaged on IA_Interact, prompt under the crosshair).
Usage (MCP execute_python):
    g = {"PI_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_interact.py", encoding="utf-8").read(), g)
The Shell is placed (physics off, so it holds still) 5 m from each pickup with a clear sight line, the pickup in the reticle;
[F] is pressed through Enhanced Input injection of the Shell's InteractAction (the real HandleInteract path).
  E1 energy cell, core 60 %  -> prompt "SALVAGE ENERGY (+25%)" available -> [F] -> collected, core 85 %
  E2 energy cell, core 100 % -> prompt "FULL" unavailable -> [F] -> stays, core 100 %
  T  torpedo canister, reserve full -> "FULL"; reserve capacity +2 rings (test hook) -> "SALVAGE AMMO (+32)" -> [F] -> +32
  E3 energy cell, core 50 %, Shell parked INSIDE its sphere looking away, no [F] for 1.5 s -> not collected (no overlap pickup)
stop: ends PIE, writes Saved/Interact_PIE.json."""
import json, os, math
import unreal

MODE = globals().get("PI_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SHOTDIR = os.path.join(PROJ, "Saved", "Screenshots", "WindowsEditor")
E1, E2, TM, E3 = "IA_EnergyCell_R5_A", "IA_EnergyCell_R5_B", "IA_TorpedoMag_R6", "IA_EnergyCell_R6"
CAM_FWD = 299.0   # FPCamera ahead of the Shell origin

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=0): return [round(v.x, n), round(v.y, n), round(v.z, n)]
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def shots():
    try: return set(f for f in os.listdir(SHOTDIR) if f.lower().endswith(".png"))
    except Exception: return set()
def input_subsystem(imc):
    for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem):
        if s.get_outer().get_class().get_name() != "Package" and s.has_mapping_context(imc) is not None:
            return s
    return None
def by_label(w, label):
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.AOSPickupBase):
        if a.get_actor_label() == label: return a
    return None

def clear_view(w, shell, target, dist=500.0):
    """First horizontal bearing with a free sight line camera->pickup and room for the hull behind the camera."""
    ign = [shell] + [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
                     if a.get_class().get_name().startswith("Water") or a.get_class().get_name() in ("TriggerBox", "BlockingVolume")]
    tp = target.get_actor_location()
    for k in range(16):
        ang = math.radians(k * 22.5)
        d = V(math.cos(ang), math.sin(ang), 0.0)
        cam = tp + d * dist
        los = unreal.SystemLibrary.sphere_trace_single_for_objects(w, cam, tp + d * 60.0, 20.0,
              [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, ign, unreal.DrawDebugTrace.NONE, True)
        body = unreal.SystemLibrary.box_overlap_actors(w, cam + d * CAM_FWD, V(230, 130, 120),
              [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1], None, ign)
        if not los and not body:
            return cam + d * CAM_FWD, unreal.MathLibrary.make_rot_from_x(d * -1.0)
    return None, None

def place(S, loc, rot):
    S["root"].set_simulate_physics(False)
    S["shell"].set_actor_location_and_rotation(loc, rot, False, True)

def prompt(sh):
    r = sh.get_focus_prompt()
    # Python: (bool return dropped) -> (OutAction, bOutAvailable) or None
    if r is None: return None
    return [str(r[0]), bool(r[1])]

def driver(dt):
    S = unreal._pi
    try:
        w = gw()
        if not w: return
        t = unreal.GameplayStatics.get_time_seconds(w)
        if S.get("pending_shot"):
            tag, before = S["pending_shot"]; new = shots() - before
            if new: S["shots"][tag] = sorted(new)[-1]; S["pending_shot"] = None
        st = S["state"]; el = t - S.get("t_state", 0.0)
        def go(n): S["state"] = n; S["t_state"] = t
        def snap(tag, extra=None):
            sh = S["shell"]; f = sh.get_interact_focus()
            d = {"t": round(t, 2), "focus": f.get_actor_label() if f else None, "prompt": prompt(sh),
                 "energy": round(S["energy"].get_energy_fraction() * 100.0, 1), "reserve": S["att"].get_reserve_ammo() if S["att"] else None}
            if extra: d.update(extra)
            S["log"][tag] = d
        def shot(tag):
            S["pending_shot"] = (tag, shots()); unreal.SystemLibrary.execute_console_command(w, "shot showui")
        def press():
            S["sub"].inject_input_vector_for_action(S["ia"], V(1, 0, 0), [], [])
        if st == "boot":
            pc = unreal.GameplayStatics.get_player_controller(w, 0)
            shells = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ShellPawn)
            if not (pc and shells) or t < 1.0: return
            sh = shells[0]; pc.possess(sh)
            sub = input_subsystem(sh.get_editor_property("sub_mapping_context"))
            if not sub: return
            atts = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SubDrone_Attacker)   # the Shell's Attacker module
            att = atts[0] if atts else None
            S.update(shell=sh, sub=sub, ia=sh.get_editor_property("interact_action"), root=sh.get_editor_property("box_root"),
                     energy=sh.get_energy(), att=att, pk={n: by_label(w, n) for n in (E1, E2, TM, E3)})
            go("E1_place"); return
        sh, pk = S["shell"], S["pk"]
        if st == "E1_place" and el > 0.5:
            loc, rot = clear_view(w, sh, pk[E1])
            if not loc: S["error"] = "no clear view of " + E1; go("error"); return
            place(S, loc, rot); S["energy"].try_consume_energy(40.0, "pie_test")
            go("E1_aim")
        elif st == "E1_aim" and el > 0.8:
            snap("E1_before"); shot("E1_prompt"); go("E1_press")
        elif st == "E1_press" and el > 0.4:
            press(); go("E1_after")
        elif st == "E1_after" and el > 0.5:
            snap("E1_after", {"collected": (not unreal.SystemLibrary.is_valid(pk[E1])) or pk[E1].is_collected()}); go("E2_place")
        elif st == "E2_place":
            S["energy"].restore_energy(1.0)
            loc, rot = clear_view(w, sh, pk[E2])
            if not loc: S["error"] = "no clear view of " + E2; go("error"); return
            place(S, loc, rot); go("E2_aim")
        elif st == "E2_aim" and el > 0.8:
            snap("E2_before"); shot("E2_full"); go("E2_press")
        elif st == "E2_press" and el > 0.4:
            press(); go("E2_after")
        elif st == "E2_after" and el > 0.5:
            snap("E2_after", {"collected": (not unreal.SystemLibrary.is_valid(pk[E2])) or pk[E2].is_collected()}); go("T_place")
        elif st == "T_place":
            loc, rot = clear_view(w, sh, pk[TM])
            if not loc: S["error"] = "no clear view of " + TM; go("error"); return
            place(S, loc, rot); go("T_aim_full")
        elif st == "T_aim_full" and el > 0.8:
            snap("T_full"); shot("T_full")
            if S["att"]:
                S["att"].set_editor_property("reserve_magazines", S["att"].get_editor_property("reserve_magazines") + 2)   # test hook: +2 rings
            go("T_aim")
        elif st == "T_aim" and el > 0.6:
            snap("T_before"); shot("T_prompt"); go("T_press")
        elif st == "T_press" and el > 0.4:
            press(); go("T_after")
        elif st == "T_after" and el > 0.5:
            snap("T_after", {"collected": (not unreal.SystemLibrary.is_valid(pk[TM])) or pk[TM].is_collected()}); go("E3_place")
        elif st == "E3_place":
            S["energy"].try_consume_energy(50.0, "pie_test")
            p = pk[E3].get_actor_location()
            place(S, p, unreal.Rotator(0.0, 0.0, 0.0))     # hull right through the pickup sphere
            go("E3_wait")
        elif st == "E3_wait" and el > 1.5:
            snap("E3_overlap_no_press", {"collected": (not unreal.SystemLibrary.is_valid(pk[E3])) or pk[E3].is_collected()}); go("done")
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error"):
        unreal.unregister_slate_post_tick_callback(S["handle"])

def checks(S):
    L = S["log"]; c = {}
    g = lambda k: L.get(k, {})
    c["E1_prompt_ok"] = g("E1_before").get("prompt") == ["SALVAGE ENERGY (+25%)", True] and g("E1_before").get("focus") == E1
    c["E1_collected_+25"] = bool(g("E1_after").get("collected")) and abs((g("E1_after").get("energy", 0) - g("E1_before").get("energy", 0)) - 25.0) < 0.6
    c["E2_full_prompt"] = g("E2_before").get("prompt") == ["FULL", False]
    c["E2_refused"] = g("E2_after").get("collected") is False and g("E2_after").get("energy") == 100.0
    c["T_full_prompt"] = g("T_full").get("prompt") == ["FULL", False]
    c["T_prompt_ok"] = g("T_before").get("prompt") == ["SALVAGE AMMO (+32)", True]
    c["T_collected_+32"] = bool(g("T_after").get("collected")) and (g("T_after").get("reserve") or 0) - (g("T_before").get("reserve") or 0) == 32
    c["E3_no_overlap_pickup"] = g("E3_overlap_no_press").get("collected") is False
    return c

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._pi = {"state": "boot", "log": {}, "shots": {}, "pending_shot": None, "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._pi["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._pi
    result = {"state": S["state"], "error": S.get("error"), "log": S["log"], "shots": S["shots"], "checks": checks(S)}
elif MODE == "stop":
    S = unreal._pi
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property("bThrottleCPUWhenNotForeground", S["throttle_was"])
    out = {"state": S["state"], "error": S.get("error"), "log": S["log"], "shots": S["shots"], "checks": checks(S)}
    with open(os.path.join(PROJ, "Saved", "Interact_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    result = out
