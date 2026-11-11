"""AOS-DK Lab 5 - evasion regression: real Attacker fire (primary action held) at a live, thinking RPR-6 Reaper at 12-20 m.
Usage (MCP execute_python, PIE already running or not):
    g = {"EV_MODE": "start" | "poll" | "stop", "EV_TRIALS": 8}; exec(open(r"<proj>/Tools/pie_test_evasion_regression.py", encoding="utf-8").read(), g)
Checks: ForceDodge CVar is -1, brain runs, every salvo rolls with P>0, DODGE happens, skitter ~340 cm, decoy spawned, torpedoes divert."""
import json, os, re, math, glob
import unreal

MODE = globals().get("EV_MODE", "poll")
TRIALS = int(globals().get("EV_TRIALS", 8))
# Arena anchors (Lvl_FirstPerson, Lab 5 arena): Reaper on the floor, Shell 24 m away over the water -> the Attacker (flies ~8 m ahead) fires from ~14-16 m.
REAPER_POS = globals().get("EV_REAPER", (-44958.0, 22308.0, -9663.0))
SHELL_POS = globals().get("EV_SHELL", (-44697.0, 19915.0, -9378.0))
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
GS = unreal.GameplayStatics
RX = re.compile(r"oom_reaper\[(\d+)\] evade: D=([\d.]+)m P=([\d.]+) u=([\d.]+) charges=(\d+)(?: force=(-?\d+))? -> (DODGE|hold)")

def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def d3(a, b): return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
def rnd(x, n=2): return None if x is None else round(float(x), n)
def log_path():
    fs = [f for f in glob.glob(os.path.join(PROJ, "Saved", "Logs", "*.log")) if "-backup-" not in f]
    return max(fs, key=os.path.getmtime) if fs else None

def scenario(S):
    R = S["results"]; S["trials"] = []
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
    lp = log_path(); S["log_pos"] = os.path.getsize(lp) if lp else 0
    def log_new():
        try: unreal.SystemLibrary.execute_console_command(gw(), "FlushLog")
        except Exception: pass
        p = log_path(); out = ""
        if not p: return out
        with open(p, "rb") as f:
            f.seek(S["log_pos"]); raw = f.read()
        cut = raw.rfind(b"\n") + 1
        S["log_pos"] += cut
        return raw[:cut].decode("utf-8", "ignore")
    yield from until(lambda: GS.get_player_controller(gw(), 0) and GS.get_all_actors_of_class(gw(), unreal.ShellPawn)
                     and GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter) and now() > 1.5, 30)
    pc = GS.get_player_controller(gw(), 0); sh = GS.get_all_actors_of_class(gw(), unreal.ShellPawn)[0]
    r = GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter)[0]
    ctl = r.get_controller(); bay = sh.drone_bay; root = sh.get_editor_property("box_root")
    pc.possess(sh); yield from wait(0.3)
    if sh.is_in_lars_cradle(): sh.leave_lars_cradle()
    root.set_simulate_physics(False)
    bay.deploy_all_drones()
    att = bay.get_drone(0)
    yield from until(lambda: att.is_deployed() and att.get_deploy_blend() > 0.99, 10)
    S["ctx"] = (r, sh)
    home_loc = unreal.Vector(*REAPER_POS)
    sloc = unreal.Vector(*SHELL_POS)
    home_rot = unreal.Rotator(0, unreal.MathLibrary.find_look_at_rotation(home_loc, sloc).yaw, 0)
    srot = unreal.MathLibrary.find_look_at_rotation(sloc, home_loc)
    sh.set_actor_location_and_rotation(sloc, srot, False, True); pc.set_control_rotation(srot)
    S["lock"] = (sloc, srot)
    r.set_actor_location_and_rotation(home_loc, home_rot, False, True)
    yield from wait(4.0)               # the Attacker follows the Shell with a lag: let it settle on the new station
    brain = ctl.get_editor_property("brain_component")
    force = unreal.SystemLibrary.get_console_variable_int_value("aos.ai.ForceDodge")
    chk("E0.force_dodge_cvar_is_model(-1)", force == -1, {"aos.ai.ForceDodge": force})
    chk("E0.brain_running_not_paused", brain is not None and brain.is_running() and not brain.is_paused(), {"running": brain.is_running() if brain else None, "paused": brain.is_paused() if brain else None})
    ev = [c for c in r.get_components_by_class(unreal.ActorComponent) if c.get_class().get_name() == "AOS_EvasionComponent"][0]
    chk("E0.evasion_component_present", True, {"max_charges": ev.get_editor_property("max_charges"), "cooldown": ev.get_editor_property("dodge_cooldown"), "skitter_cm": ev.get_editor_property("skitter_distance")})
    for k in range(TRIALS):
        if att.get_ring_ammo() < 8:
            bay.request_reload(); yield from until(lambda: att.get_ring_ammo() >= 30, 10)
        if r.get_health() <= 30:
            yield from wait(8.0)           # let the auto-respawn or regen settle
            r = GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter)[0]; S["ctx"] = (r, sh)
        r.set_actor_location_and_rotation(home_loc, home_rot, False, True)
        r.character_movement.set_editor_property("velocity", unreal.Vector(0, 0, 0))
        yield from wait(1.0); log_new()
        sd = d3(sh.get_actor_location(), r.get_actor_location())
        thr = ctl.get_threat_level().name if ctl else None
        p0 = r.get_actor_location(); h0 = r.get_health()
        S["track"] = {"p0": p0, "maxdisp": 0.0, "decoy": None, "decoy_t0": None, "decoy_t1": None, "tmin_decoy": 1e9}
        ring0 = att.get_ring_ammo()
        bay.set_primary_action_held(True)
        yield from until(lambda: att.get_ring_ammo() < ring0, 4.0)
        yield from wait(0.10); bay.set_primary_action_held(False)
        fired = att.get_ring_ammo() < ring0
        txt = ""
        for _ in range(12):
            yield from wait(0.5); txt += log_new()
            if RX.search(txt): break
        yield from wait(2.5); txt += log_new()
        T = S["track"]; S["track"] = None
        ls = RX.findall(txt)
        S["trials"].append({"k": k, "shell_dist_cm": rnd(sd, 0), "threat": thr, "fired": fired, "log": ls[:2], "maxdisp_cm": rnd(T["maxdisp"], 0), "decoy": T["decoy"],
                            "decoy_life_s": rnd(None if T["decoy_t1"] is None else T["decoy_t1"] - T["decoy_t0"], 2), "tmin_decoy_cm": rnd(T["tmin_decoy"], 0) if T["decoy"] else None,
                            "hp_delta": rnd(r.get_health() - h0, 1), "decoy_launched_log": "decoy launched" in txt})
        yield from wait(7.0)
    tr = S["trials"]
    rolled = [t for t in tr if t["log"]]
    dod = [t for t in rolled if t["log"][0][6] == "DODGE"]
    chk("E1.every_volley_rolled", len(rolled) == len(tr), {"trials": len(tr), "rolled": len(rolled)})
    chk("E1.P_positive_at_12-20m", all(float(t["log"][0][2]) > 0 for t in rolled), [t["log"][0] for t in rolled])
    chk("E2.dodges_happen", len(dod) >= 1, {"dodges": len(dod), "of": len(rolled), "mean_P": rnd(sum(float(t["log"][0][2]) for t in rolled) / max(1, len(rolled)), 3)})
    chk("E3.skitter_340cm", all(300 <= t["maxdisp_cm"] <= 400 for t in dod) and bool(dod), [t["maxdisp_cm"] for t in dod])
    chk("E3.decoy_spawned_1.0-1.6s", all(t["decoy"] and t["decoy_life_s"] and 1.0 <= t["decoy_life_s"] <= 1.7 for t in dod) and bool(dod), [(t["decoy"], t["decoy_life_s"]) for t in dod])
    chk("E3.torpedoes_divert_to_decoy_no_hp_loss", all(t["tmin_decoy_cm"] is not None and t["tmin_decoy_cm"] < 250 and abs(t["hp_delta"]) < 0.5 for t in dod) and bool(dod), [(t["tmin_decoy_cm"], t["hp_delta"]) for t in dod])
    S["state"] = "done"

def driver(dt):
    S = unreal._ev
    try:
        w = gw()
        if not w: return
        if S["gen"] is None:
            S["gen"] = scenario(S); S["state"] = "running"
        t = GS.get_time_seconds(w); ctx = S.get("ctx")
        if ctx:
            r, sh = ctx
            lk = S.get("lock")
            if lk: sh.set_actor_location_and_rotation(lk[0], lk[1], False, True)
            T = S.get("track")
            if T:
                p = r.get_actor_location(); p0 = T["p0"]
                T["maxdisp"] = max(T["maxdisp"], math.hypot(p.x - p0.x, p.y - p0.y))
                dec = GS.get_all_actors_of_class(w, unreal.AOS_CavitationDecoy)
                if dec:
                    dl = dec[0].get_actor_location()
                    if T["decoy"] is None: T["decoy"] = dec[0].get_name(); T["decoy_t0"] = t
                    T["decoy_t1"] = t
                    prev = S.setdefault("tprev", {})
                    for tp in GS.get_all_actors_of_class(w, unreal.MicroTorpedo):
                        pl = tp.get_actor_location(); k = tp.get_name(); pp = prev.get(k); prev[k] = (pl.x, pl.y, pl.z)
                        if pp is not None and abs(pl.x - pp[0]) + abs(pl.y - pp[1]) + abs(pl.z - pp[2]) > 15:
                            T["tmin_decoy"] = min(T["tmin_decoy"], d3(pl, dl))
        try: next(S["gen"])
        except StopIteration: S["state"] = "done"
    except Exception:
        import traceback
        S["error"] = traceback.format_exc()[-900:]; S["state"] = "error"
    if S["state"] in ("done", "error"):
        try: unreal.unregister_slate_post_tick_callback(S["handle"])
        except Exception: pass

def summary(S):
    R = S["results"]
    return {"state": S["state"], "error": S.get("error"), "n": len(R), "passed": sum(1 for x in R if x["ok"]), "failed": [x["id"] for x in R if not x["ok"]], "trials_done": len(S.get("trials", []))}

if MODE == "start":
    unreal._ev = {"state": "boot", "gen": None, "results": []}
    if not gw(): unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._ev["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True, "pie_already_running": gw() is not None}
elif MODE == "poll":
    S = unreal._ev; result = {**summary(S), "results": S["results"], "trials": S.get("trials")}
elif MODE == "stop":
    S = unreal._ev
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    out = {**summary(S), "results": S["results"], "trials": S.get("trials")}
    with open(os.path.join(PROJ, "Saved", "Evasion_Regression_PIE.json"), "w", encoding="utf-8") as f: json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Evasion_Regression_PIE.json"}
