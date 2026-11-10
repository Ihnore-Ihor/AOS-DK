"""AOS-DK | LARS dock arm: setup + PIE test of the Shell-1 launch / recovery sequence (UE 5.7.4).

Usage (MCP execute_python):
    g = {"LARS_MODE": "<mode>"}; exec(open(r"<proj>/Tools/setup_lars_dock_sequence.py", encoding="utf-8").read(), g); result = g["result"]
Modes
    setup  - ABP_LARS_RoboticArm (parent ULARSArmAnimInstance), place ALARSDockArm on the pier pedestal facing the berth,
             bind Shell <-> arm <-> BP_ShellDock, put the Shell in the cradle pose (in the air), save the level.
    start  - PIE test driver (state machine on the Slate post-tick):
               hold   : Shell clamped in the air, hull keel above the wave crest, pistons coaxial
               board  : Admin on the pier, real IA_Interact press -> dock -> possess -> arm lowers -> jaws open
                        -> retract -> 6DOF + HUD (real IA_Sub_Move thrust injected, Shell moves)
               dock   : pilot surfaces near the berth, real [F] -> align -> capture -> clamp -> lift -> Admin on foot
    poll   - progress / partial results
    stop   - ends PIE, writes Saved/LARS_PIE.json
    (PIE v2: collision sweeps + walk-into-arm, LaunchCam blends, cockpit-entry vs HUD frame, recovery cinematic)
"""
import json, math, os
import unreal

MODE = globals().get("LARS_MODE", "poll")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
ARM_SK = "/Game/AOS_DK_Game/Environment/CustomHero/SK_LARS_RoboticArm"
ABP_DIR, ABP_NAME = "/Game/AOS_DK_Game/Environment/CustomHero", "ABP_LARS_RoboticArm"
STEEL = "/Game/AOS_DK_Game/Environment/CustomHero/M_LARS_SteelWorn"
ARM_LABEL = "LARS_DockArm"

# Berth layout (world cm). Solved offline against the stroke-safe envelope (shoulder -12..60, elbow -105..18,
# cylinder overlap >= 25): reach 990..1040 keeps hold 420 / release -300 / retract / stow all reachable.
BERTH_XY = (-1000.0, 820.0)     # Shell-1 berth centre (unchanged from the level)
BERTH_HEADING = -90.0           # nose toward the pier slab / transit station A
MOUNT_Y = 50.0                  # pier (Floor2) centre line
REACH = 1020.0
PEDESTAL = 30.0
HOLD_Z, RELEASE_Z, STOW_Z = 500.0, -300.0, 500.0   # keel 420: 1 m over the analytic crest bound (A sum 320)
DOCK_TRIGGER_EXTENT = (400.0, 400.0, 400.0)
LAUNCH_CAM_POS, LAUNCH_CAM_LOOK = (-400.0, -500.0, 950.0), (-1250.0, 500.0, 150.0)   # deeper trigger: [F] docking works down to the release depth

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))
def vl(v, n=1): return [round(v.x, n), round(v.y, n), round(v.z, n)]
def eas(): return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
def by_label(label):
    for a in eas().get_all_level_actors():
        if a.get_actor_label() == label: return a
    return None
def of_class(cls):
    return [a for a in eas().get_all_level_actors() if isinstance(a, cls)]

# ------------------------------------------------------------------------------------------------ setup
def make_abp():
    path = ABP_DIR + "/" + ABP_NAME
    abp = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if not abp:
        sk = unreal.load_asset(ARM_SK)
        f = unreal.AnimBlueprintFactory()
        f.set_editor_property("target_skeleton", sk.skeleton)
        f.set_editor_property("parent_class", unreal.LARSArmAnimInstance)
        f.set_editor_property("preview_skeletal_mesh", sk)
        abp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(ABP_NAME, ABP_DIR, unreal.AnimBlueprint, f)
    unreal.BlueprintEditorLibrary.compile_blueprint(abp)
    unreal.EditorAssetLibrary.save_loaded_asset(abp)
    return abp

def setup():
    w = unreal.EditorLevelLibrary.get_editor_world()
    shell, dock = by_label("BP_Shell"), by_label("BP_ShellDock")
    if not shell or not dock: raise RuntimeError("BP_Shell / BP_ShellDock not found")
    abp = make_abp()
    gen = abp.generated_class()

    bx, by = BERTH_XY
    dx = math.sqrt(REACH ** 2 - (by - MOUNT_Y) ** 2)
    mx, my = bx - dx, MOUNT_Y
    yaw = math.degrees(math.atan2(by - my, bx - mx))
    hit = unreal.SystemLibrary.line_trace_single(w, V(mx, my, 2000), V(mx, my, -500), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                 False, [shell] + of_class(unreal.LARSDockArm), unreal.DrawDebugTrace.NONE, True)
    t = hit.to_tuple() if hit else None
    deck_z = t[4].z if t else 80.0
    deck = t[9].get_actor_label() if t and t[9] else None

    arm = by_label(ARM_LABEL)
    if not arm:
        arm = eas().spawn_actor_from_class(unreal.LARSDockArm, V(mx, my, deck_z), unreal.Rotator(0, 0, yaw))
        arm.set_actor_label(ARM_LABEL)
    arm.set_actor_location_and_rotation(V(mx, my, deck_z), unreal.Rotator(0.0, 0.0, yaw), False, True)
    arm.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), True)
    for k, v in (("pedestal_height", PEDESTAL), ("berth_reach", REACH), ("berth_heading", BERTH_HEADING),
                 ("hold_world_z", HOLD_Z), ("release_world_z", RELEASE_Z), ("stow_world_z", STOW_Z), ("shell", shell), ("start_holding_shell", True),
                 ("water_surface_z", 40.0)):
        arm.set_editor_property(k, v)
    mesh = arm.get_editor_property("arm_mesh")
    mesh.set_editor_property("anim_class", gen)
    ped = arm.get_editor_property("pedestal")
    steel = unreal.load_asset(STEEL)
    if steel: ped.set_material(0, steel)

    # Shell in the cradle pose (the arm re-clamps it exactly at BeginPlay; this is the editor/parking pose).
    hold = arm.get_hold_transform()
    shell.set_actor_location_and_rotation(hold.translation, hold.rotation.rotator(), False, True)
    dock.set_editor_property("lars_arm", arm)
    dock.set_editor_property("linked_submarine", shell)
    trig = dock.get_editor_property("dock_trigger")
    trig.set_box_extent(V(*DOCK_TRIGGER_EXTENT), True)
    # Cinematic LaunchCam: on the mast above the east pier block, frames turret, boom, forearm and the berth water.
    cam = arm.get_editor_property("launch_cam")
    cam.set_world_location(V(*LAUNCH_CAM_POS), False, True)
    cam.set_world_rotation(unreal.MathLibrary.find_look_at_rotation(V(*LAUNCH_CAM_POS), V(*LAUNCH_CAM_LOOK)), False, True)
    # Disembark facing the cradle (pilot steps out looking at the Shell hanging in the jaws).
    dp = dock.get_editor_property("disembark_point")
    dpl = dp.get_world_location()
    dp.set_world_rotation(unreal.Rotator(0.0, 0.0, math.degrees(math.atan2(by - dpl.y, bx - dpl.x))), False, True)

    pose = unreal.LARSArmJointPose()
    tgt = unreal.LARSArmTarget()
    poses = {}
    for name, (r, z, jaw) in {"hold": (REACH, HOLD_Z, -9), "release": (REACH, RELEASE_Z, 30),
                              "retract": (REACH - 80, RELEASE_Z + 300, 30), "stow": (REACH - 60, STOW_Z, 10)}.items():
        tgt.reach, tgt.world_z, tgt.jaw_open = r, z, jaw
        p = arm.solve_arm_ik(tgt)   # Python drops the bool return; check the envelope here
        ok = -12.0 <= p.shoulder_pitch <= 60.0 and -105.0 <= p.elbow_pitch <= 18.0
        poses[name] = {"in_envelope": bool(ok), "shoulder": round(p.shoulder_pitch, 2), "elbow": round(p.elbow_pitch, 2),
                       "wrist": round(p.wrist_pitch, 2), "roll": round(p.wrist_roll, 2)}
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    return {"abp": abp.get_path_name(), "mount": [round(mx, 1), round(my, 1), round(deck_z, 1)], "deck": deck, "yaw": round(yaw, 2),
            "arm_mesh_z": round(mesh.get_world_location().z, 1), "hold": vl(hold.translation), "capture": vl(arm.get_capture_transform().translation),
            "poses": poses}

if MODE == "setup":
    result = setup()


# ------------------------------------------------------------------------------------------------ PIE test (v2)
SHOTDIR = os.path.join(PROJ, "Saved", "Screenshots", "WindowsEditor")
ONFOOT_POS = V(-1330, 560, 190)          # Admin on the Floor3 finger, inside the dock trigger
WALK_START = V(-2120, 50, 180)           # Floor2 deck, 4.5 m west of the turret yaw axis
PARTS = ["collar_collision", "turret_collision", "clevis_collision", "boom_collision", "forearm_collision", "tail_lever_collision",
         "shoulder_cyl_collision", "elbow_cyl_collision", "gripper_collision", "jaw_l_collision", "jaw_r_collision"]
NEAR = 2.0                               # cm: "the camera is at" tolerance

def gw(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
def input_subsystem(imc):
    for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem):
        if s.get_outer().get_class().get_name() != "Package" and s.has_mapping_context(imc) is not None:
            return s
    return None
def phase_name(p): return str(p).split(".")[-1].split(":")[0].strip("<> ").title()
def vis(w): return str(w.get_visibility()).split(".")[-1].split(":")[0] if w else None
def shots():
    try: return set(f for f in os.listdir(SHOTDIR) if f.lower().endswith(".png"))
    except Exception: return set()
def hit_tuple(r):
    h = r[1] if isinstance(r, tuple) else r
    return h.to_tuple() if h else None
def in_frame_deg(cam_loc, cam_rot, target):
    d = (target - cam_loc); d.normalize()
    return math.degrees(math.acos(max(-1.0, min(1.0, cam_rot.get_forward_vector().dot(d)))))
def smoothness(path):
    """path = [(t, loc)]: peak camera speed / mean speed (frame-time normalised) and max per-frame step share (no pops)."""
    if len(path) < 3: return None
    steps = [((path[i + 1][1] - path[i][1]).length(), max(path[i + 1][0] - path[i][0], 1e-4)) for i in range(len(path) - 1)]
    total = (path[-1][1] - path[0][1]).length() or 1.0
    dur = max(path[-1][0] - path[0][0], 1e-3)
    peak = max(d / t for d, t in steps)
    return {"frames": len(path), "seconds": round(dur, 2), "total_cm": round(total, 1), "max_step_cm": round(max(d for d, _ in steps), 1),
            "peak_over_mean_speed": round(peak / (sum(d for d, _ in steps) / dur), 2), "max_step_share": round(max(d for d, _ in steps) / total, 3)}

def state(S, t):
    sh, arm, w = S["shell"], S["arm"], S["w"]
    pc = S["pc"]; pcm = pc.player_camera_manager
    pawn = pc.get_controlled_pawn(); vt = pc.get_view_target()
    par = sh.get_attach_parent_actor()
    return {"t": round(t, 2), "frame": S["frame"], "phase": phase_name(arm.get_phase()), "shell": vl(sh.get_actor_location()),
            "sim": S["root"].is_simulating_physics(), "attached_to": par.get_actor_label() if par else None,
            "pawn": pawn.get_class().get_name() if pawn else None, "view_target": vt.get_actor_label() if vt else None,
            "cam": vl(pcm.get_camera_location()), "blocked": sh.are_controls_blocked(), "hud": vis(sh.get_cockpit_hud()),
            "jaw_gap": round(arm.get_jaw_gap(), 1), "admin": vl(S["admin"].get_actor_location())}

def collision_sweeps(S):
    """Sweep the Admin's own capsule (Pawn) from 3.2 m out straight at each arm part: the part must stop it."""
    arm, admin, out = S["arm"], S["admin"], {}
    S["shell"].set_actor_enable_collision(False)     # the hanging hull would shadow the gripper / jaws
    deck_clear = arm.get_actor_location().z + 100.0   # Admin capsule (half height ~96) standing on the pier deck
    for name in PARTS:
        comp = arm.get_editor_property(name)
        c = comp.get_world_location()
        if c.z < deck_clear: c = V(c.x, c.y, deck_clear)   # low collar: sweep at standing height
        res = None
        for axis in ("right", "left", "fwd", "back"):
            if axis in ("right", "left"):
                d = comp.get_right_vector() * (1.0 if axis == "right" else -1.0)
            else:
                d = comp.get_forward_vector() * (1.0 if axis == "fwd" else -1.0)
            d = V(d.x, d.y, 0.0)
            if d.length() < 0.2: continue
            d.normalize()
            if name == "jaw_l_collision": d = comp.get_right_vector() * -1.0
            if name == "jaw_r_collision": d = comp.get_right_vector()
            start = c + d * 320.0
            admin.set_actor_location(start, False, True)
            ht = hit_tuple(admin.set_actor_location(c, True, False))
            if not ht or ht[1]: continue      # no hit / started overlapping something: try another side
            hc = ht[10]
            fin = admin.get_actor_location()
            res = {"side": axis, "blocked": bool(ht[0]), "hit_actor": ht[9].get_actor_label() if ht[9] else None,
                   "hit_comp": hc.get_name() if hc else None, "stopped_cm_from_center": round((fin - c).length(), 1),
                   "travel_cm": round((fin - start).length(), 1)}
            break
        if res is None:
            # Gripper / jaws hang inside BlockingVolume8 (the berth water is fenced off for the on-foot character), so
            # the Admin capsule cannot start there: sweep an Admin-sized capsule with the Pawn profile instead.
            ign = [a for a in unreal.GameplayStatics.get_all_actors_of_class(S["w"], unreal.BlockingVolume)] + [admin, S["shell"]]
            cap = admin.get_editor_property("capsule_component")
            r, hh = cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height()
            for axis in ("right", "left"):
                d = comp.get_right_vector() * (1.0 if axis == "right" else -1.0)
                if name == "jaw_l_collision": d = comp.get_right_vector() * -1.0
                if name == "jaw_r_collision": d = comp.get_right_vector()
                d = V(d.x, d.y, 0.0); d.normalize()
                start = c + d * 320.0
                h = unreal.SystemLibrary.capsule_trace_single_by_profile(S["w"], start, c, r, hh, "Pawn", False, ign,
                                                                       unreal.DrawDebugTrace.NONE, True)
                ht = h.to_tuple() if h else None
                if not ht or ht[1]: continue
                res = {"side": axis + " (Pawn-profile capsule trace)", "blocked": bool(ht[0]), "hit_actor": ht[9].get_actor_label() if ht[9] else None,
                       "hit_comp": ht[10].get_name() if ht[10] else None, "stopped_cm_from_center": round((ht[4] - c).length(), 1),
                       "travel_cm": round((ht[4] - start).length(), 1)}
                break
        out[name] = res
    S["shell"].set_actor_enable_collision(True)
    return out

def driver(dt):
    S = unreal._lars
    try:
        w = gw()
        if not w: return
        t = unreal.GameplayStatics.get_time_seconds(w)
        S["frame"] = S.get("frame", 0) + 1
        if S.get("pending_shot"):
            tag, before = S["pending_shot"]; new = shots() - before
            if new: S["shots"][tag] = sorted(new)[-1]; S["pending_shot"] = None
        st = S["state"]; el = t - S.get("t_state", 0.0)
        def go(n): S["state"] = n; S["t_state"] = t
        def shot(tag):
            if S.get("pending_shot") or tag in S["shots"]: return
            S["pending_shot"] = (tag, shots()); unreal.SystemLibrary.execute_console_command(w, "shot showui")
        def log(tag, extra=None):
            if tag in S["log"]: return
            d = state(S, t)
            if extra: d.update(extra)
            S["log"][tag] = d
        def press(sub, ia): sub.inject_input_vector_for_action(ia, V(1, 0, 0), [], [])

        if st == "boot":
            pc = unreal.GameplayStatics.get_player_controller(w, 0)
            if not pc or t < 1.5: return
            arms = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.LARSDockArm)
            shells = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ShellPawn)
            admin = pc.get_controlled_pawn()
            if not (arms and shells and admin): S["error"] = "actors missing"; go("error"); return
            sh = shells[0]
            S.update(w=w, pc=pc, arm=arms[0], shell=sh, admin=admin, root=sh.get_editor_property("box_root"),
                     launch_cam=arms[0].get_editor_property("launch_cam"), fp_cam=sh.get_editor_property("fp_camera"),
                     admin_cam=admin.get_editor_property("camera_component"),
                     sub_admin=input_subsystem(admin.get_editor_property("default_mapping_context")),
                     ia_admin=admin.get_editor_property("interact_action"), ia_walk=admin.get_editor_property("move_action"),
                     ia_shell=sh.get_editor_property("interact_action"), move=sh.get_editor_property("move_action"),
                     phases=[], worst={"coax": 0.0, "min_overlap": 1e9}, cam={})
            go("hold"); return

        arm, sh, pc, admin = S["arm"], S["shell"], S["pc"], S["admin"]
        ph = phase_name(arm.get_phase())
        if not S["phases"] or S["phases"][-1][0] != ph:
            S["phases"].append([ph, round(t, 2)])
        for p in arm.get_piston_states():
            S["worst"]["coax"] = max(S["worst"]["coax"], p.coaxial_error_deg, p.barrel_axis_error_deg, p.rod_axis_error_deg)
            S["worst"]["min_overlap"] = min(S["worst"]["min_overlap"], p.overlap)
        pcm = pc.player_camera_manager
        cam_loc, cam_rot = pcm.get_camera_location(), pcm.get_camera_rotation()
        C = S["cam"]

        # ---------------- 0) hold + collision
        if st == "hold" and el > 1.0:
            log("hold"); go("sweeps")
        elif st == "sweeps":
            S["log"]["sweeps"] = collision_sweeps(S)
            admin.set_actor_location_and_rotation(WALK_START, unreal.Rotator(0, 0, 0), False, True)
            pc.set_control_rotation(unreal.Rotator(0.0, 0.0, 0.0))     # +X = straight at the turret yaw axis
            S["walk_min"] = 1e9; go("walk_settle")
        elif st == "walk_settle" and el > 0.8:
            S["walk_x0"] = admin.get_actor_location().x; go("walk")
        elif st == "walk":
            ax = arm.get_actor_location()
            a = admin.get_actor_location()
            S["walk_min"] = min(S["walk_min"], math.hypot(a.x - ax.x, a.y - ax.y))
            if el < 3.5:
                # keep pushing straight at the yaw axis (no sliding around the round collar): the steel must hold
                pc.set_control_rotation(unreal.Rotator(0.0, 0.0, math.degrees(math.atan2(ax.y - a.y, ax.x - a.x))))
                S["sub_admin"].inject_input_vector_for_action(S["ia_walk"], V(0, 1, 0), [], [])
                if el > 2.8: shot("0_walk_into_turret_blocked")
                return
            vel = admin.get_velocity()
            S["log"]["walk"] = {"start": vl(WALK_START), "end": vl(a), "min_dist_to_yaw_axis_cm": round(S["walk_min"], 1),
                                "end_speed": round(math.hypot(vel.x, vel.y), 1), "passed_axis": a.x > ax.x}
            admin.set_actor_location_and_rotation(ONFOOT_POS, unreal.Rotator(0, 0, 0), False, True)
            pc.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(ONFOOT_POS + V(0, 0, 60), sh.get_actor_location()))
            go("hold_view")
        elif st == "hold_view" and el > 1.2:
            log("hold_view"); shot("1_hold_onfoot"); go("board_press")
        # ---------------- 1) boarding -> LaunchCam cinematic -> cockpit + HUD
        elif st == "board_press" and el > 0.8:
            press(S["sub_admin"], S["ia_admin"])
            C["launch_in"] = [(t, cam_loc)]; C["f_press"] = S["frame"]; S["t_press"] = t
            go("launch")
        elif st == "launch":
            lc = S["launch_cam"].get_world_location(); fpc = S["fp_cam"].get_world_location()
            at_lc = (cam_loc - lc).length() < NEAR
            if "cin_arrive" not in C:
                C["launch_in"].append((t, cam_loc))
                if at_lc:
                    C["cin_arrive"] = S["frame"]; log("cinematic_arrived", {"dt_from_press": round(t - S["t_press"], 2)})
            elif "cockpit_leave" not in C:
                if ph == "Lowering":
                    C["lower_frames"] = C.get("lower_frames", 0) + 1
                    C["lower_at_cam"] = C.get("lower_at_cam", 0) + (1 if at_lc else 0)
                    C["lower_vt_arm"] = C.get("lower_vt_arm", 0) + (1 if pc.get_view_target() == arm else 0)
                    C["lower_hud_hidden"] = C.get("lower_hud_hidden", 0) + (1 if vis(sh.get_cockpit_hud()) in (None, "COLLAPSED") else 0)
                    C["max_offaxis_deg"] = max(C.get("max_offaxis_deg", 0.0), in_frame_deg(cam_loc, cam_rot, sh.get_actor_location()))
                    if sh.get_actor_location().z < 60.0:
                        log("lower_waterline", {"shell_offaxis_deg": round(in_frame_deg(cam_loc, cam_rot, sh.get_actor_location()), 1)})
                        shot("2_launch_cinematic_lowering")
                if ph == "Releasing" and S["root"].is_simulating_physics():
                    log("released"); shot("3_release_jaws_open")
                if not at_lc:
                    C["cockpit_leave"] = S["frame"]; C["to_cockpit"] = [(t, cam_loc)]
                    log("cockpit_blend_start")
            elif "cockpit_arrive" not in C:
                C["to_cockpit"].append((t, cam_loc))
                if (cam_loc - fpc).length() < 0.05:   # blend fully landed (ease-in-out leaves ~1 cm one frame earlier)
                    C["cockpit_arrive"] = S["frame"]; log("cockpit_arrived")
            if "hud_on" not in C and vis(sh.get_cockpit_hud()) in ("HIT_TEST_INVISIBLE", "SELF_HIT_TEST_INVISIBLE", "VISIBLE"):
                C["hud_on"] = S["frame"]; log("hud_on")
            if "cockpit_arrive" in C and "hud_on" in C:
                if S["frame"] - max(C["cockpit_arrive"], C["hud_on"]) >= 3:
                    shot("4_cockpit_hud_live"); log("cockpit_live"); S["p0"] = sh.get_actor_location(); go("fly")
            elif el > 40.0: S["error"] = "launch timeout"; go("error")
        elif st == "fly":
            if el < 1.6:
                sub = input_subsystem(sh.get_editor_property("sub_mapping_context"))
                if sub: sub.inject_input_vector_for_action(S["move"], V(-1, 0, 0), [], [])
                return
            S["log"]["after_thrust"] = {"moved_cm": round((sh.get_actor_location() - S["p0"]).length(), 1)}
            go("stow_wait")
        elif st == "stow_wait":
            if ph == "Stowed": go("dock_place")
            elif el > 15.0: S["error"] = "stow timeout"; go("error")
        # ---------------- 2) docking -> cinematic recovery -> on foot
        elif st == "dock_place":
            sh.set_actor_location_and_rotation(V(-930, 960, -60), unreal.Rotator(0, 0, -70), False, True)
            S["root"].set_physics_linear_velocity(V(0, 0, 0)); S["root"].set_physics_angular_velocity_in_degrees(V(0, 0, 0))
            go("dock_focus")
        elif st == "dock_focus":
            # the teleported hull needs the controller's 10 Hz overlap scan + the 30 Hz reticle query to see the berth
            fo = sh.get_interact_focus()
            if fo is not None and fo.get_actor_label() == "BP_ShellDock":
                S["log"]["dock_focus_after_s"] = round(el, 2); go("dock_press")
            elif el > 8.0: S["error"] = "dock never in focus"; go("error")
        elif st == "dock_press" and el > 0.3:
            S["dock_presses"] = S.get("dock_presses", 0) + 1
            pr = sh.get_focus_prompt(); fo = sh.get_interact_focus()
            S["log"].setdefault("dock_prompt", {"prompt": [str(pr[0]), bool(pr[1])] if pr else None, "focus": fo.get_actor_label() if fo else None})
            sub = input_subsystem(sh.get_editor_property("sub_mapping_context"))
            press(sub, S["ia_shell"]); C["f_dock"] = S["frame"]; C["rec_in"] = [(t, cam_loc)]; S["t_dock"] = t
            go("dock_confirm")
        elif st == "dock_confirm":
            if ph == "Aligning": S["log"]["dock_presses"] = S["dock_presses"]; go("recover")
            elif el > 0.5:
                if S["dock_presses"] >= 3: S["error"] = "dock [F] ignored x3"; go("error")
                else: go("dock_press")   # (re-press only if the first one was ignored: flagged by dock_single_press)
        elif st == "recover":
            lc = S["launch_cam"].get_world_location()
            at_lc = (cam_loc - lc).length() < NEAR
            if "rec_hud_off" not in C and vis(sh.get_cockpit_hud()) in (None, "COLLAPSED"):
                C["rec_hud_off"] = S["frame"]
            if "rec_arrive" not in C:
                C["rec_in"].append((t, cam_loc))
                if at_lc: C["rec_arrive"] = S["frame"]; log("rec_cinematic_arrived", {"dt_from_press": round(t - S["t_dock"], 2)})
            if ph in ("Approaching", "Engaging", "Clamping", "Lifting"):
                C["rec_frames"] = C.get("rec_frames", 0) + 1
                C["rec_at_cam"] = C.get("rec_at_cam", 0) + (1 if at_lc else 0)
                C["rec_offaxis"] = max(C.get("rec_offaxis", 0.0), in_frame_deg(cam_loc, cam_rot, sh.get_actor_location()))
            if ph == "Clamping": log("clamp"); shot("5_recovery_cinematic_clamp")
            if ph == "Lifting" and sh.get_actor_location().z > 60.0: log("lift_waterline"); shot("6_recovery_cinematic_lift")
            if ph == "Holding" and "recovered" not in S["log"]:
                log("recovered"); C["to_admin"] = []
            if "recovered" in S["log"]:
                C["to_admin"].append((t, cam_loc))
                acam = S["admin_cam"].get_world_location()
                if "admin_arrive" not in C and (cam_loc - acam).length() < NEAR and pc.get_controlled_pawn() == admin:
                    C["admin_arrive"] = S["frame"]
                    mm = admin.get_editor_property("character_movement").movement_mode
                    log("on_foot", {"admin": vl(admin.get_actor_location()), "admin_move": str(mm).split(".")[-1].split(":")[0]})
                if "admin_arrive" in C and S["frame"] - C["admin_arrive"] > 20:
                    shot("7_back_on_foot"); go("panic_board")
            if el > 60.0: S["error"] = "recovery timeout"; go("error")
        # ---------------- 3) second launch + Kernel Panic -> snap back into the cradle
        elif st == "panic_board" and el > 1.5:
            press(S["sub_admin"], S["ia_admin"]); go("panic_wait")
        elif st == "panic_wait":
            if ph in ("Stowing", "Stowed") and not sh.are_controls_blocked():
                sh.get_energy().apply_energy_damage(100.0, sh.get_actor_location(), None); go("panic_recover")
            elif el > 40.0: S["error"] = "relaunch timeout"; go("error")
        elif st == "panic_recover" and el > 8.0:
            log("after_panic"); go("done")
    except Exception as e:
        S["error"] = repr(e); S["state"] = "error"
    if S["state"] in ("done", "error"):
        unreal.unregister_slate_post_tick_callback(S["handle"])

def checks(S):
    L, C = S["log"], S.get("cam", {}); g = lambda k: L.get(k, {}); c = {}
    sw = L.get("sweeps", {})
    for k, v in sw.items():
        c["blocks_pawn_" + k.replace("_collision", "")] = bool(v) and v["blocked"] and v["hit_actor"] == ARM_LABEL and v["stopped_cm_from_center"] > 20
    wk = L.get("walk", {})
    c["walk_into_turret_stopped"] = bool(wk) and not wk["passed_axis"] and wk["min_dist_to_yaw_axis_cm"] > 140 and wk["end_speed"] < 10
    c["dock_single_press"] = L.get("dock_presses") == 1
    c["hold_in_air"] = g("hold").get("attached_to") == ARM_LABEL and abs((g("hold").get("shell") or [0, 0, 0])[2] - HOLD_Z) < 1
    sm = smoothness(C.get("launch_in", []))
    c["launch_blend_smooth"] = bool(sm) and sm["max_step_share"] < 0.1 and sm["peak_over_mean_speed"] < 2.5
    c["launchcam_reached_after_blend"] = 1.3 < g("cinematic_arrived").get("dt_from_press", 0) < 2.0
    c["lowering_on_launchcam"] = C.get("lower_frames", 0) > 30 and C.get("lower_at_cam") == C.get("lower_frames") == C.get("lower_vt_arm")
    c["shell_framed_while_lowering"] = 0 < C.get("max_offaxis_deg", 99) < 30
    c["hud_hidden_during_cinematic"] = C.get("lower_hud_hidden") == C.get("lower_frames")
    cb = g("cockpit_blend_start")
    c["cockpit_blend_at_jaws_open_retract"] = cb.get("phase") == "Retracting" and cb.get("sim") is True and cb.get("jaw_gap", 0) > 400
    sm2 = smoothness(C.get("to_cockpit", []))
    c["cockpit_blend_smooth"] = bool(sm2) and sm2["max_step_share"] < 0.15 and sm2["peak_over_mean_speed"] < 2.5
    c["hud_same_frame_as_cockpit"] = "hud_on" in C and "cockpit_arrive" in C and 0 <= C["cockpit_arrive"] - C["hud_on"] <= 1
    c["hud_at_cockpit_blend_end"] = abs((g("hud_on").get("t", 0) - g("cockpit_blend_start").get("t", 0)) - 1.4) < 0.05
    c["6dof_live_in_cockpit"] = g("cockpit_live").get("blocked") is False and L.get("after_thrust", {}).get("moved_cm", 0) > 100
    c["recovery_hud_off_with_camera"] = "rec_hud_off" in C and C["rec_hud_off"] - C.get("f_dock", 0) <= 2
    sm3 = smoothness(C.get("rec_in", []))
    c["recovery_blend_smooth"] = bool(sm3) and sm3["max_step_share"] < 0.1 and sm3["peak_over_mean_speed"] < 2.5
    c["recovery_on_launchcam"] = C.get("rec_frames", 0) > 30 and C.get("rec_at_cam") == C.get("rec_frames") and 0 < C.get("rec_offaxis", 99) < 30
    c["recovered_in_air"] = g("recovered").get("attached_to") == ARM_LABEL and abs((g("recovered").get("shell") or [0, 0, 0])[2] - HOLD_Z) < 1
    sm4 = smoothness(C.get("to_admin", []))
    c["back_to_admin_smooth"] = bool(sm4) and sm4["max_step_share"] < 0.15 and sm4["peak_over_mean_speed"] < 2.5 and g("on_foot").get("admin_move") == "MOVE_WALKING"
    c["panic_snaps_to_cradle"] = g("after_panic").get("phase") == "Holding" and g("after_panic").get("attached_to") == ARM_LABEL
    c["pistons_coaxial_whole_run"] = S["worst"]["coax"] < 0.5 and S["worst"]["min_overlap"] >= 25
    return c

def report(S):
    C = S.get("cam", {})
    cam = {k: v for k, v in C.items() if not isinstance(v, list)}
    cam["smooth_launch_in"] = smoothness(C.get("launch_in", [])); cam["smooth_to_cockpit"] = smoothness(C.get("to_cockpit", []))
    cam["smooth_recovery_in"] = smoothness(C.get("rec_in", [])); cam["smooth_to_admin"] = smoothness(C.get("to_admin", []))
    return {"state": S["state"], "error": S.get("error"), "phases": S.get("phases"), "worst_piston": S.get("worst"), "camera": cam,
            "log": S["log"], "shots": S["shots"], "checks": checks(S)}

if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._lars = {"state": "boot", "log": {}, "shots": {}, "pending_shot": None, "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._lars["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "poll":
    S = unreal._lars
    result = {"state": S["state"], "error": S.get("error"), "phases": S.get("phases"), "keys": list(S["log"].keys()), "shots": S["shots"]}
elif MODE == "stop":
    S = unreal._lars
    try: unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception: pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor(): les.editor_request_end_play()
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    ps.set_editor_property("bThrottleCPUWhenNotForeground", True)
    out = report(S)
    with open(os.path.join(PROJ, "Saved", "LARS_PIE.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    result = out
