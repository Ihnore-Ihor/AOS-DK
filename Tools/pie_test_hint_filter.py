"""AOS-DK - PIE test: the legacy top-left typing hint (W_InteractHint, AAdminPlayerController) is on-foot only.
Usage: g = {"PH_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_hint_filter.py", encoding="utf-8").read(), g)
Phases: on foot at the dock (hint must show) -> possess Shell-1 at its berth, overlapping the dock (hint collapsed, cockpit
reticle prompt only) -> explicit ShowHint() call while in the Shell (must stay collapsed) -> back on foot (hint returns)."""
import json, os
import unreal
MODE = globals().get("PH_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SHOTDIR = os.path.join(PROJ, "Saved", "Screenshots", "WindowsEditor")
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def shots():
    try: return set(f for f in os.listdir(SHOTDIR) if f.lower().endswith(".png"))
    except Exception: return set()
def state(S):
    pc = S["pc"]; w = pc.get_editor_property("cached_hint_widget")
    pawn = pc.get_controlled_pawn()
    cur = pc.get_current_interactable() if hasattr(pc, "get_current_interactable") else None
    d = {"pawn": pawn.get_class().get_name() if pawn else None, "on_foot": pc.is_on_foot(),
         "hint_widget": bool(w), "hint_in_viewport": w.is_in_viewport() if w else None,
         "hint_visibility": str(w.get_visibility()).split(".")[-1].split(":")[0] if w else None,
         "hint_rendered": (w.is_in_viewport() and w.get_visibility() in (unreal.SlateVisibility.VISIBLE, unreal.SlateVisibility.HIT_TEST_INVISIBLE, unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)) if w else False}
    sh = S.get("shell")
    if sh and pawn == sh:
        f = sh.get_interact_focus(); p = sh.get_focus_prompt()
        d["reticle_focus"] = f.get_actor_label() if f else None
        d["reticle_prompt"] = [str(p[0]), bool(p[1])] if p else None
    return d
def driver(dt):
    S = unreal._ph
    try:
        w = gw()
        if not w: return
        t = unreal.GameplayStatics.get_time_seconds(w); el = t - S.get("t0", 0.0); st = S["state"]
        if S.get("pending"):
            tag, before = S["pending"]; new = shots() - before
            if new: S["shots"][tag] = sorted(new)[-1]; S["pending"] = None
        def go(n): S["state"] = n; S["t0"] = t
        def shot(tag): S["pending"] = (tag, shots()); unreal.SystemLibrary.execute_console_command(w, "shot showui")
        if st == "boot":
            pc = unreal.GameplayStatics.get_player_controller(w, 0)
            shells = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ShellPawn)
            docks = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ShellDock)
            if not (pc and shells and docks and pc.get_controlled_pawn()) or t < 1.0: return
            S.update(pc=pc, shell=shells[0], dock=docks[0], admin=pc.get_controlled_pawn())
            # walk the pilot onto the dock deck, facing the berth (overlap / view trace finds the dock)
            d = docks[0].get_actor_location()
            S["admin"].set_actor_location_and_rotation(unreal.Vector(d.x + 150, d.y + 250, d.z + 150), unreal.Rotator(0.0, 0.0, -100.0), False, True)
            go("foot")
        elif st == "foot" and el > 2.0:
            S["log"]["1_on_foot_at_dock"] = state(S); shot("1_on_foot"); go("board")
        elif st == "board" and el > 0.6:
            S["pc"].possess(S["shell"]); go("in_shell")
        elif st == "in_shell" and el > 2.0:
            S["log"]["2_in_shell_at_berth"] = state(S); shot("2_in_shell")
            S["pc"].show_hint()                         # a Blueprint / dock flow calling ShowHint while piloting
            go("forced")
        elif st == "forced" and el > 1.0:
            S["log"]["3_in_shell_after_ShowHint_call"] = state(S); go("unboard")
        elif st == "unboard":
            S["pc"].possess(S["admin"]); go("foot2")
        elif st == "foot2" and el > 2.0:
            S["log"]["4_back_on_foot"] = state(S); shot("4_back_on_foot"); go("done")
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error"):
        unreal.unregister_slate_post_tick_callback(S["h"])
def checks(L):
    g = lambda k: L.get(k, {})
    return {"on_foot_hint_shown": bool(g("1_on_foot_at_dock").get("hint_rendered")),
            "in_shell_hint_hidden": g("2_in_shell_at_berth").get("hint_rendered") is False,
            "in_shell_forced_call_hidden": g("3_in_shell_after_ShowHint_call").get("hint_rendered") is False,
            "back_on_foot_hint_shown": bool(g("4_back_on_foot").get("hint_rendered"))}
if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._ph = {"state": "boot", "log": {}, "shots": {}, "pending": None, "throttle": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._ph["h"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._ph; result = {"state": S["state"], "error": S.get("error"), "log": S["log"], "shots": S["shots"], "checks": checks(S["log"])}
elif MODE == "stop":
    S = unreal._ph
    try: unreal.unregister_slate_post_tick_callback(S["h"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    out = {"state": S["state"], "error": S.get("error"), "log": S["log"], "shots": S["shots"], "checks": checks(S["log"])}
    with open(os.path.join(PROJ, "Saved", "HintFilter_PIE.json"), "w", encoding="utf-8") as f: json.dump(out, f, indent=1)
    result = out
