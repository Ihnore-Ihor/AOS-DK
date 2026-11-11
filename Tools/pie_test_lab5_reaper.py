"""AOS-DK Lab 5 - PIE test suite for RPR-6 "OOM Reaper" (generator state machine on the slate post-tick).
Usage (MCP execute_python):
    g = {"RT_MODE": "start" | "poll" | "stop"}; exec(open(r"<proj>/Tools/pie_test_lab5_reaper.py", encoding="utf-8").read(), g)
start: begins PIE and the scenario.  poll: {state, done, results so far}.  stop: ends PIE, writes Saved/Lab5_Reaper_PIE.json.
Sections: R1 (assets/coexistence), R3 (brine), R2.1 (patrol/survey, sprint), R2.2 (melee = 5 % energy), R2.3 (dodge law, skitter,
decoy, retarget, A/B ForceDodge). Every check is {id, ok, detail}. Arena anchor + labels come from Tools/deploy_lab5_arena.py."""
import json, os, re, math, glob
import unreal

MODE = globals().get("RT_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
CX, CY, FLOOR = -43500.0, 22000.0, -9800.0
POOL = (CX, CY - 1300.0)                       # brine pool centre (box +-500 x 400)
RX = re.compile(r"oom_reaper\[(\d+)\] evade: D=([\d.]+)m P=([\d.]+) u=([\d.]+) charges=(\d+) -> (DODGE|hold)")
GS = unreal.GameplayStatics

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def d3(a, b): return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
def sp2(v): return math.hypot(v.x, v.y)
def rnd(x, n=2): return None if x is None else round(float(x), n)

def log_path():
    fs = [f for f in glob.glob(os.path.join(PROJ, "Saved", "Logs", "*.log")) if "-backup-" not in f]
    return max(fs, key=os.path.getmtime) if fs else None

class Ctx:
    pass

def scenario(S):
    C = S["ctx"] = Ctx()
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
    def con(cmd): unreal.SystemLibrary.execute_console_command(gw(), cmd)
    lp = log_path(); S["log_pos"] = os.path.getsize(lp) if lp else 0
    def log_new():
        try: unreal.SystemLibrary.execute_console_command(gw(), "FlushLog")
        except Exception: pass
        p = log_path(); out = ""
        if not p: return out
        with open(p, "rb") as f:
            f.seek(S["log_pos"]); raw = f.read()
        cut = raw.rfind(b"\n") + 1            # never consume a half-written last line
        S["log_pos"] += cut
        return raw[:cut].decode("utf-8", "ignore")
    # ---- boot -------------------------------------------------------------------------------------------------------------------
    yield from until(lambda: GS.get_player_controller(gw(), 0) and GS.get_all_actors_of_class(gw(), unreal.ShellPawn)
                     and GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter) and now() > 1.5, 30)
    pc = GS.get_player_controller(gw(), 0); sh = GS.get_all_actors_of_class(gw(), unreal.ShellPawn)[0]
    rs = GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter); r = rs[0]
    ctl = r.get_controller(); root = sh.get_editor_property("box_root"); bay = sh.drone_bay
    pc.possess(sh); yield from wait(0.3)
    if sh.is_in_lars_cradle(): sh.leave_lars_cradle()
    root.set_simulate_physics(False)
    bay.deploy_all_drones()
    C.pc, C.sh, C.r, C.ctl, C.root, C.bay = pc, sh, r, ctl, root, bay
    att = bay.get_drone(0)
    yield from until(lambda: att.is_deployed() and att.get_deploy_blend() > 0.99, 10)
    def brain(on):
        b = ctl.get_editor_property("brain_component")
        if b: (b.restart_logic() if on else b.stop_logic("test"))
    def put_reaper(x, y, yaw=0.0):
        r.set_actor_location_and_rotation(V(x, y, FLOOR + 145.0), unreal.Rotator(0, yaw, 0), False, True)
        r.character_movement.set_editor_property("velocity", V(0, 0, 0))
    def put_shell(loc, look=None):
        rot = unreal.MathLibrary.find_look_at_rotation(loc, look) if look is not None else sh.get_actor_rotation()
        if look is not None: rot = unreal.Rotator(0, rot.yaw, 0) if False else rot
        S["lock"] = (loc, rot); sh.set_actor_location_and_rotation(loc, rot, False, True); pc.set_control_rotation(rot)
    def hp(): return r.get_health()
    # ---- R1 ---------------------------------------------------------------------------------------------------------------------
    mesh = r.mesh; sk = mesh.get_editor_property("skeletal_mesh_asset")
    chk("R1.mesh", sk and sk.get_name() == "SK_OOMReaper", sk.get_name() if sk else None)
    chk("R1.anim", mesh.get_anim_instance() and isinstance(mesh.get_anim_instance(), unreal.AOS_ReaperAnimInstance), str(type(mesh.get_anim_instance()).__name__))
    w = r.get_editor_property("weapon")
    wd = {}
    if w:
        wd["actor"] = w.get_class().get_name(); wd["socket"] = str(w.root_component.get_attach_socket_name()) if w.root_component else None
        wd["parent"] = w.root_component.get_attach_parent().get_name() if w.root_component and w.root_component.get_attach_parent() else None
        sms = [c.get_editor_property("static_mesh") for c in w.get_components_by_class(unreal.StaticMeshComponent)]
        wd["meshes"] = [m.get_name() for m in sms if m]
    chk("R1.pike_on_dorsal_socket", w and wd.get("socket") == "SOCKET_Weapon_Dorsal" and "SM_WPN_SigkillPike" in wd.get("meshes", []), wd)
    chk("R1.controller", isinstance(ctl, unreal.AOS_AIController), type(ctl).__name__)
    dae = GS.get_all_actors_of_class(gw(), unreal.AOS_EnemyDaemon)
    chk("R1.daemons_coexist", len(dae) > 0 and not r.is_dead(), {"daemons": len(dae), "reapers": len(rs), "reaper_alive": not r.is_dead()})
    pm = r.page_map
    C.pm = pm
    pm_info = {"cls": type(pm).__name__, "parent": pm.get_attach_parent().get_name() if pm.get_attach_parent() else None,
               "rel_loc": [rnd(v, 1) for v in pm.relative_location.to_tuple()], "visible": pm.is_visible()}
    # ---- R3 brine (Reaper) -----------------------------------------------------------------------------------------------------
    brain(False); put_shell(V(CX + 6000, CY, FLOOR + 600), V(CX, CY, FLOOR)); put_reaper(CX + 1000, CY + 1300, 0)
    yield from wait(1.0)
    def sight_r():
        cfg = ctl.get_editor_property("perception_comp").get_editor_property("senses_config")[0]
        return cfg.get_editor_property("sight_radius")
    base_speed = r.character_movement.max_walk_speed; base_sight = sight_r()
    put_reaper(POOL[0], POOL[1], 0); yield from wait(1.0)
    in_h = r.is_in_hazard(); sp_in = r.character_movement.max_walk_speed; si_in = sight_r()
    put_reaper(CX + 1000, CY + 1300, 0); t_out = now()
    yield from until(lambda: abs(r.character_movement.max_walk_speed - base_speed) < 1 and abs(sight_r() - base_sight) < 1, 6)
    sp_out = r.character_movement.max_walk_speed; si_out = sight_r(); t_rest = now() - t_out
    chk("R3.reaper_in_hazard", in_h, in_h)
    chk("R3.speed_minus_60pct", abs(sp_in / base_speed - 0.4) < 0.02, {"base": base_speed, "in_brine": sp_in, "ratio": rnd(sp_in / base_speed, 3)})
    chk("R3.sight_halved", abs(si_in / base_sight - 0.5) < 0.02, {"base": base_sight, "in_brine": si_in})
    chk("R3.restored_after_exit", abs(sp_out - base_speed) < 1 and abs(si_out - base_sight) < 1, {"speed": sp_out, "sight": si_out, "restore_time_s": rnd(t_rest, 2)})
    # Shell immunity: park the Shell hull inside the pool; the trigger must not affect it, the Reaper stays out of hazard
    pool = GS.get_all_actors_of_class(gw(), unreal.AOS_AIObstacleTrigger)[0]
    damp0 = (root.get_linear_damping(), root.get_angular_damping()); e0 = sh.energy.get_energy()
    put_shell(V(POOL[0], POOL[1], FLOOR + 60)); yield from wait(1.2)
    ov = pool.is_overlapping_actor(sh)
    bo, be = sh.get_actor_bounds(False)
    geo = abs(bo.x - POOL[0]) < 500 + be.x and abs(bo.y - POOL[1]) < 400 + be.y and abs(bo.z - FLOOR) < 120 + be.z
    damp1 = (root.get_linear_damping(), root.get_angular_damping()); e1 = sh.energy.get_energy()
    chk("R3.shell_immune", (ov or geo) and damp0 == damp1 and not r.is_in_hazard() and abs(e1 - e0) < 3.0,
        {"shell_overlaps_pool_event": ov, "shell_bounds_inside_pool_box": geo, "damping_before": damp0, "damping_inside": damp1, "reaper_in_hazard": r.is_in_hazard(), "energy_delta": rnd(e1 - e0, 2)})
    # ---- R2.1 patrol / survey ---------------------------------------------------------------------------------------------------
    put_shell(V(CX + 6000, CY, FLOOR + 600), V(CX, CY, FLOOR)); put_reaper(CX - 1300, CY + 1300, -90)
    brain(True); S["ph"] = {"seen": set(), "survey_speed": [], "patrol_speed": []}
    S["sampling_phase"] = True
    ok = yield from until(lambda: {"PATROL", "SURVEY"} <= S["ph"]["seen"] and len(S["ph"]["survey_speed"]) > 8, 70)
    S["sampling_phase"] = False
    ps, ss = S["ph"]["patrol_speed"], S["ph"]["survey_speed"]
    chk("R2.1.patrol_and_survey_halts", ok and ps and ss and max(ps) > 100 and max(ss) < 15,
        {"phases": sorted(S["ph"]["seen"]), "patrol_speed_max": rnd(max(ps) if ps else None, 0), "survey_speed_max": rnd(max(ss) if ss else None, 1),
         "walk_speed": r.get_editor_property("walk_speed")})
    # ---- R2.1 sprint on sight + R2.2 melee ----------------------------------------------------------------------------------------
    brain(False); put_reaper(CX - 1300, CY + 1300, 0); yield from wait(0.5); brain(True)
    yield from until(lambda: r.get_phase().name in ("PATROL", "SURVEY") and ctl.get_threat_level().name != "HOSTILE", 8)
    yield from wait(0.3)
    sc = r.get_editor_property("scuttle_speed")
    rp = r.get_actor_location(); fwd = r.get_actor_forward_vector()
    S["sprint"] = {"t_place": now(), "hostile": None, "mws": None, "v90": None, "vmax": 0.0, "scuttle": sc}
    S["energy_trace"] = []; S["e_last"] = sh.energy.get_energy(); S["sampling_energy"] = True; S["sampling_sprint"] = True
    put_shell(V(rp.x + fwd.x * 1100, rp.y + fwd.y * 1100, rp.z + 265), rp)    # chest height: above the 10 deg floor of the arm envelope
    yield from until(lambda: S["sprint"]["v90"] is not None, 5)
    sp = S["sprint"]
    L = lambda k: None if sp[k] is None or sp["hostile"] is None else sp[k] - sp["hostile"]
    chk("R2.1.sprint_620_on_sight", sp["vmax"] >= 0.9 * sc and sp["mws"] is not None,
        {"scuttle_speed": sc, "v_max": rnd(sp["vmax"], 0), "max_walk_speed_switch_after_HOSTILE_s": rnd(L("mws"), 3), "v>=90%_after_HOSTILE_s": rnd(L("v90"), 3),
         "hostile_after_placement_s": rnd(None if sp["hostile"] is None else sp["hostile"] - sp["t_place"], 3)})
    chk("R2.1.instant_speed_switch_le_0.2s", L("mws") is not None and L("mws") <= 0.2, {"switch_latency_s": rnd(L("mws"), 3)})
    S["sampling_sprint"] = False
    yield from until(lambda: len([e for e in S["energy_trace"] if e["drop"]]) >= 2, 14)
    S["sampling_energy"] = False
    drops = [e for e in S["energy_trace"] if e["drop"]]
    d = drops[0] if drops else None
    chk("R2.2.melee_5pct_energy", d is not None and all(abs(e["frac_of_max"] - 0.05) < 0.006 for e in drops),
        {"drops_pct_of_max": [rnd(e["frac_of_max"] * 100, 2) for e in drops], "phases": [e["phase"] for e in drops], "emax": sh.energy.get_max_energy(),
         "spacing_s": rnd(drops[1]["t"] - drops[0]["t"], 2) if len(drops) > 1 else None})
    # ---- R2.3 evasion --------------------------------------------------------------------------------------------------------------
    brain(False); put_reaper(CX - 1700, CY + 100, 180); yield from wait(1.5)
    con("aos.ai.ForceDodge -1")
    att = bay.get_drone(0)
    def volley(D, miss, hold=0.10, tries=3):
        if att.get_ring_ammo() < 8:
            bay.request_reload(); yield from until(lambda: att.get_ring_ammo() >= 30, 10)
        for k in range(tries):
            rp = r.get_actor_location()
            loc = V(rp.x + D, rp.y, rp.z)
            tgt = V(rp.x, rp.y + 300.0, FLOOR) if miss else rp
            put_shell(loc, tgt)
            yield from wait(3.5 if k == 0 else 1.0); log_new()          # the Attacker flies ~800 cm ahead of the Shell: let it settle
            ring0 = att.get_ring_ammo()
            bay.set_primary_action_held(True)
            yield from until(lambda: att.get_ring_ammo() < ring0, 4.0)
            yield from wait(hold); bay.set_primary_action_held(False)
            fired = att.get_ring_ammo() < ring0
            txt = ""
            for _ in range(12):                      # the log file is written lazily: flush + poll up to ~6 s
                yield from wait(0.5); txt += log_new()
                if RX.search(txt): break
            ls = RX.findall(txt)
            if ls or fired: return ls              # a salvo did leave the ring: never fire a second one (it would only add damage)
            yield from wait(0.5)
        return []
    laws = []
    con("aos.ai.ForceDodge 0")                # P is logged for every salvo; 0 = never dodge, so the sample stays independent of the PID seed
    for D in (1900.0, 3300.0):
        put_reaper(CX - 1700, CY + 100, 180); yield from wait(0.8)
        h0 = hp(); ls = yield from volley(D, True)
        laws.append({"shell_dist_cm": D, "log": ls[:1], "hp_delta": rnd(hp() - h0, 1)})
        yield from wait(4.0)
    parsed = [(float(l["log"][0][1]), float(l["log"][0][2]), l["log"][0][5]) for l in laws if l["log"]]
    base = lambda dm: unreal.AOS_EvasionComponent.compute_base_probability(dm * 100.0)
    # P = base(D) x awareness (1.0 LOS / 0.5 heard <= 3 s / 0.2 else); fatigue = 1 for the first dodge of the window
    law_ok = len(parsed) == 2 and all(any(abs(p - base(dm) * a) <= 0.006 for a in (0.2, 0.5, 1.0)) for dm, p, _ in parsed) and base(parsed[1][0]) > base(parsed[0][0])
    chk("R2.3.dodge_probability_law", law_ok, {"salvos": laws, "analytic_base": {"6m": rnd(base(6), 4), "10m": rnd(base(10), 4), "15m": rnd(base(15), 4), "25m": rnd(base(25), 4), "30m": rnd(base(30), 4)}})
    # A: ForceDodge 1 - skitter, decoy, retarget
    yield from wait(3.0)
    con("aos.ai.ForceDodge 1"); put_reaper(CX - 1700, CY + 100, 180); yield from wait(1.0)
    rp0 = r.get_actor_location()
    S["track"] = {"p0": [rp0.x, rp0.y, rp0.z], "maxlat": 0.0, "decoy": None, "decoy_t0": None, "decoy_t1": None, "tmin_decoy": 1e9, "decoy_off": None}
    h0 = hp(); ls = yield from volley(1900.0, False)
    yield from wait(2.0)
    T = S["track"]; S["track"] = None
    rp1 = r.get_actor_location()
    chk("R2.3.forced_dodge_logged", bool(ls) and ls[0][5] == "DODGE", ls[:1])
    chk("R2.3.skitter_340cm", 300 <= T["maxlat"] <= 380, {"max_lateral_cm": rnd(T["maxlat"], 0), "end_disp_cm": rnd(d3(rp0, rp1), 0)})
    dl = None if T["decoy_t1"] is None or T["decoy_t0"] is None else T["decoy_t1"] - T["decoy_t0"]
    chk("R2.3.cavitation_decoy", T["decoy"] is not None and dl is not None and 1.0 <= dl <= 1.6 and T["decoy_off"] is not None and 40 <= T["decoy_off"] <= 130,
        {"spawned": T["decoy"] is not None, "lifetime_s": rnd(dl, 2), "offset_from_old_pos_cm": rnd(T["decoy_off"], 0)})
    chk("R2.3.torpedoes_retarget_decoy", T["decoy"] is not None and T["tmin_decoy"] < 250 and abs(hp() - h0) < 0.5,
        {"min_torpedo_to_decoy_cm": rnd(T["tmin_decoy"], 0), "reaper_hp_delta": rnd(hp() - h0, 1)})
    # B: ForceDodge 0 - the same salvo lands
    yield from wait(2.0)
    con("aos.ai.ForceDodge 0"); put_reaper(CX - 1700, CY + 100, 180); yield from wait(1.0)   # the skitter moved it behind an occluder: back onto the clear firing line
    h1 = hp(); ls = yield from volley(1900.0, False)
    yield from until(lambda: hp() < h1, 4.0)
    chk("R2.3.forced_hold_hits", bool(ls) and ls[0][5] == "hold" and hp() < h1, {"log": ls[:1], "hp_before": rnd(h1, 1), "hp_after": rnd(hp(), 1)})
    # Root-cause diagnostic (PIE-only, nothing saved): the WaterBodyOcean collision box (WorldStatic = Block, spans z -2000..+0.4 km) makes the
    # ECC_WorldStatic capsule sweep in UAOS_EvasionComponent::TrySkitter start inside a blocking overlap -> "evade: blocked" always.
    oc = [c for a in GS.get_all_actors_of_class(gw(), unreal.WaterBodyOcean) for c in a.get_components_by_class(unreal.PrimitiveComponent)
          if c.get_class().get_name() == "OceanBoxCollisionComponent"]
    for c in oc: c.set_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_STATIC, unreal.CollisionResponseType.ECR_IGNORE)
    yield from wait(8.0)
    con("aos.ai.ForceDodge 1"); put_reaper(CX - 1700, CY + 100, 180); yield from wait(1.0)
    rp0 = r.get_actor_location()
    S["track"] = {"p0": [rp0.x, rp0.y, rp0.z], "maxlat": 0.0, "decoy": None, "decoy_t0": None, "decoy_t1": None, "tmin_decoy": 1e9, "decoy_off": None}
    h0 = hp(); ls = yield from volley(1900.0, False); yield from wait(2.0)
    T2 = S["track"]; S["track"] = None
    chk("R2.3.skitter_340cm_ocean_box_ignored(PIE-only diagnostic)", bool(ls) and ls[0][5] == "DODGE" and 300 <= T2["maxlat"] <= 380, {"log": ls[:1], "max_lateral_cm": rnd(T2["maxlat"], 0)})
    chk("R2.3.torpedoes_retarget_decoy_with_skitter(diagnostic)", T2["decoy"] is not None and T2["tmin_decoy"] < 250 and abs(hp() - h0) < 0.5,
        {"min_torpedo_to_decoy_cm": rnd(T2["tmin_decoy"], 0), "reaper_hp_delta": rnd(hp() - h0, 1), "decoy_lifetime_s": rnd(None if T2["decoy_t1"] is None else T2["decoy_t1"] - T2["decoy_t0"], 2)})
    for c in oc: c.set_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_STATIC, unreal.CollisionResponseType.ECR_BLOCK)
    con("aos.ai.ForceDodge -1")
    # R3: dodge suppression in brine (x0.25) - same range, aim beside the Reaper
    yield from wait(7.0)
    pr = {}
    con("aos.ai.ForceDodge 0")
    for tag, (x, y) in (("brine", (CX - 350, POOL[1])), ("dry", (CX - 350, CY + 100))):
        put_reaper(x, y, 180); yield from wait(1.2)
        ls = yield from volley(1850.0, True); pr[tag] = [(float(a[1]), float(a[2]), a[5]) for a in ls[:1]]
        yield from wait(7.0)
    pb, pd = (pr["brine"][0][1] if pr["brine"] else None), (pr["dry"][0][1] if pr["dry"] else None)
    def fits(pv, dm, hz):   # P = base(D) x awareness{0.2,0.5,1} x hazard(0.25 in brine) (fatigue = 1 for the first salvo after the cooldown)
        return pv is not None and any(abs(pv - base(dm) * hz * a) <= 0.006 for a in (0.2, 0.5, 1.0))
    bD = pr["brine"][0][0] if pr["brine"] else None; dD = pr["dry"][0][0] if pr["dry"] else None
    chk("R3.dodge_suppressed_x0.25", pb is not None and pd is not None and pb < pd and fits(pb, bD, 0.25) and fits(pd, dD, 1.0) and not fits(pb, bD, 1.0) ,
        {"brine": pr["brine"], "dry": pr["dry"], "note": "same Shell range; brine also halves sight (1300 cm), so awareness can drop 1.0 -> 0.2 on top of the x0.25 dodge factor"})
    # Monte-Carlo of the base law (console)
    log_new(); con("aos.ai.DodgeMonteCarlo 20000"); mc = ""
    for _ in range(12):                      # the editor flushes the log lazily
        yield from wait(0.5); mc += log_new()
        if "DodgeMonteCarlo: " in mc: break
    S["mc"] = [l[-140:] for l in mc.splitlines() if "DodgeMonteCarlo" in l or "empirical" in l][:12]
    chk("R2.3.monte_carlo_PASS", any("DodgeMonteCarlo: PASS" in l for l in mc.splitlines()), S["mc"][-3:])
    chk("R1.page_map_info", True, {**pm_info, "sampled_during_hostile": S.get("pm")})
    con("aos.ai.ForceDodge -1")
    S["lock"] = None
    S["state"] = "done"

def driver(dt):
    S = unreal._rt
    try:
        w = gw()
        if not w: return
        if S["gen"] is None:
            S["gen"] = scenario(S); S["state"] = "running"
        t = GS.get_time_seconds(w)
        ctx = S.get("ctx")
        if ctx and hasattr(ctx, "r"):
            r, sh = ctx.r, ctx.sh
            lk = S.get("lock")
            if lk: sh.set_actor_location_and_rotation(lk[0], lk[1], False, True)
            ph = r.get_phase().name
            v = sp2(r.get_velocity())
            if S.get("sampling_phase"):
                S["ph"]["seen"].add(ph)
                if ph == "SURVEY": S["ph"]["survey_speed"].append(v)
                if ph == "PATROL": S["ph"]["patrol_speed"].append(v)
            if S.get("sampling_sprint"):
                sp = S["sprint"]
                if sp["hostile"] is None and ctx.ctl.get_threat_level().name == "HOSTILE": sp["hostile"] = t
                sp["vmax"] = max(sp["vmax"], v)
                if sp["hostile"] is not None:
                    if sp["mws"] is None and r.character_movement.max_walk_speed >= 0.99 * sp["scuttle"]: sp["mws"] = t
                    if sp["v90"] is None and v >= 0.9 * sp["scuttle"]: sp["v90"] = t
                    if "pm" not in S and ctx.pm:
                        S["pm"] = {"visible": ctx.pm.is_visible(), "world_z": rnd(ctx.pm.get_world_location().z, 1), "reaper_z": rnd(r.get_actor_location().z, 1), "phase": ph}
            if S.get("sampling_energy"):
                e = sh.energy.get_energy(); last = S.get("e_last", e)
                if last - e > 0.02 * sh.energy.get_max_energy():
                    S["energy_trace"].append({"t": t, "drop": True, "frac_of_max": (last - e) / sh.energy.get_max_energy(), "phase": ph})
                S["e_last"] = e
            T = S.get("track")
            if not T: S["tprev"] = {}
            if T:
                p = r.get_actor_location(); p0 = T["p0"]
                T["maxlat"] = max(T["maxlat"], abs(p.y - p0[1]))
                dec = GS.get_all_actors_of_class(w, unreal.AOS_CavitationDecoy)
                if dec:
                    dl = dec[0].get_actor_location()
                    if T["decoy"] is None:
                        T["decoy"] = dec[0].get_name(); T["decoy_t0"] = t
                        T["decoy_off"] = math.sqrt((dl.x - p0[0]) ** 2 + (dl.y - p0[1]) ** 2 + (dl.z - p0[2]) ** 2)
                    T["decoy_t1"] = t
                    prev = S.setdefault("tprev", {})
                    for tp in GS.get_all_actors_of_class(w, unreal.MicroTorpedo):
                        pl = tp.get_actor_location(); k = tp.get_name(); pp = prev.get(k); prev[k] = (pl.x, pl.y, pl.z)
                        if pp is not None and abs(pl.x - pp[0]) + abs(pl.y - pp[1]) + abs(pl.z - pp[2]) > 15:
                            T["tmin_decoy"] = min(T["tmin_decoy"], d3(pl, dl))
        try:
            next(S["gen"])
        except StopIteration:
            S["state"] = "done"
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
    out = {**summary(S), "results": S["results"], "monte_carlo": S.get("mc")}
    with open(os.path.join(PROJ, "Saved", "Lab5_Reaper_PIE.json"), "w", encoding="utf-8") as f: json.dump(out, f, indent=1, default=str)
    result = {**summary(S), "written": "Saved/Lab5_Reaper_PIE.json"}
