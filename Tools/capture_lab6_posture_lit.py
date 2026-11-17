"""AOS-DK Lab 6 / Task 2 - lit documentation shots of the OOM Reaper pike postures (Stowed vs Ready).
The submerged Reaper arena (Lab 5 anchor) has no light, so the earlier posture shots were black. Temporary fill lights + a side camera are
placed in the EDITOR level (PIE has no Python spawn API; PIE copies them), the shots are taken in PIE, and the TMP_Cap* actors are removed again.
They must never be saved: run MODE "unprep" afterwards and confirm the level has 0 dirty packages.
Usage (MCP execute_python):
  g = {"LPL_MODE": "prep"|"unprep"}; exec(open(r"<proj>/Tools/capture_lab6_posture_lit.py", encoding="utf-8").read(), g); result = g["result"]
  "gen": the body of a generator for Tools/pie_envpolish_harness.py (EP_MODE "run", EP_CODE = 'LPL_MODE="gen"; exec(open(...).read(), globals())').
Output: Saved/Screenshots/WindowsEditor/lab6_posture_{stowed,ready}.png (copy to Saved/Lab6_Verify/reaper_posture_*.png)."""
import unreal

MODE = globals().get("LPL_MODE", "prep")
CX, CY, FLOOR = -43500.0, 22000.0, -9800.0          # Lab 5 arena anchor (Tools/deploy_lab5_arena.py)
RES = (1920, 1080)
GS = unreal.GameplayStatics
CAM_LOC = (CX - 60.0, CY + 800.0, FLOOR + 270.0)    # side view from the arm side (+Y)
CAM_LOOK = (CX - 60.0, CY, FLOOR + 190.0)
LIGHTS = [  # (location, intensity, radius, shadows, colour)
    ((CX - 300.0, CY + 450.0, FLOOR + 750.0), 70000.0, 4500.0, True, (0.80, 0.90, 1.0)),
    ((CX + 450.0, CY + 900.0, FLOOR + 350.0), 35000.0, 4500.0, False, (1.0, 0.85, 0.75)),
    ((CX - 700.0, CY - 450.0, FLOOR + 500.0), 35000.0, 4500.0, False, (0.60, 0.75, 1.0)),
]

def V(x, y, z): return unreal.Vector(float(x), float(y), float(z))

if MODE in ("prep", "unprep"):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if MODE == "prep":
        rot = unreal.MathLibrary.find_look_at_rotation(V(*CAM_LOC), V(*CAM_LOOK))
        c = eas.spawn_actor_from_class(unreal.CameraActor, V(*CAM_LOC), rot); c.set_actor_label("TMP_CapCam")
        c.camera_component.set_editor_property("field_of_view", 70.0)
        for i, (loc, inten, rad, shadows, col) in enumerate(LIGHTS):
            l = eas.spawn_actor_from_class(unreal.PointLight, V(*loc), unreal.Rotator(0, 0, 0)); l.set_actor_label(f"TMP_CapLight{i}")
            lc = l.get_component_by_class(unreal.PointLightComponent)
            lc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
            lc.set_editor_property("intensity", inten)
            lc.set_editor_property("attenuation_radius", rad)
            lc.set_editor_property("cast_shadows", shadows)
            lc.set_light_color(unreal.LinearColor(col[0], col[1], col[2], 1.0))
        result = {"prepared": True}
    else:
        n = 0
        for a in eas.get_all_level_actors():
            if a.get_actor_label().startswith("TMP_Cap"):
                eas.destroy_actor(a); n += 1
        result = {"removed": n}

elif MODE == "gen":
    def _gen():
        while not (GS.get_player_controller(gw(), 0) and GS.get_all_actors_of_class(gw(), unreal.ShellPawn)
                   and GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter) and now() > 1.5):
            yield
        pc = GS.get_player_controller(gw(), 0); sh = GS.get_all_actors_of_class(gw(), unreal.ShellPawn)[0]
        r = GS.get_all_actors_of_class(gw(), unreal.AOS_AIEnemyCharacter)[0]
        root = sh.get_editor_property("box_root")
        pc.possess(sh); yield from wait(0.3)
        if sh.is_in_lars_cradle(): sh.leave_lars_cradle()
        root.set_simulate_physics(False)
        by = {x.get_actor_label(): x for x in GS.get_all_actors_of_class(gw(), unreal.Actor) if x.get_actor_label().startswith("TMP_Cap")}
        cam = by["TMP_CapCam"]
        scale = float(globals().get("LPL_SCALE", 1.0))      # fill-light intensity scale for the PIE copies (underwater exposure is high)
        for i in range(len(LIGHTS)):
            lc = by[f"TMP_CapLight{i}"].get_component_by_class(unreal.PointLightComponent)
            lc.set_editor_property("intensity", LIGHTS[i][1] * scale)
        pin_loc, pin_rot = V(CX, CY, FLOOR + 145.0), unreal.Rotator(0, 0, 0)      # Reaper faces +X
        lock = [V(CX + 6000.0, CY, FLOOR + 600.0)]
        def hold():
            rot = unreal.MathLibrary.find_look_at_rotation(lock[0], V(CX, CY, FLOOR + 300.0))
            sh.set_actor_location_and_rotation(lock[0], rot, False, True)
            r.set_actor_location_and_rotation(pin_loc, pin_rot, False, True)
            r.character_movement.set_editor_property("velocity", V(0, 0, 0))
        def hwait(sec):
            end = now() + sec
            while now() < end:
                hold(); yield
        S["posture_log"] = []
        hold(); pc.set_view_target_with_blend(cam, 0.0)
        # STOWED: shell far away, the Reaper stays calm, pike slung aft
        yield from hwait(1.0)
        end = now() + 10.0
        while now() < end and not (r.get_weapon_posture().name == "STOWED" and r.get_posture_s() == 0.0):
            hold(); yield            # a re-run starts from Ready: wait out the 1.5 s grace + 1.4 s stow
        yield from hwait(1.0)
        S["posture_log"].append(("stowed", r.get_weapon_posture().name, round(r.get_posture_s(), 3)))
        unreal.AutomationLibrary.take_high_res_screenshot(RES[0], RES[1], "lab6_posture_stowed.png")
        yield from hwait(2.0)
        # READY: shell 12 m in front of the Reaper (inside DrawRange) -> Drawing -> Ready, pike raised forward
        lock[0] = V(CX + 1200.0, CY, FLOOR + 300.0)
        end = now() + 6.0
        while now() < end and r.get_weapon_posture().name != "READY":
            hold(); yield
        yield from hwait(1.5)
        S["posture_log"].append(("ready", r.get_weapon_posture().name, round(r.get_posture_s(), 3), r.get_phase().name))
        unreal.AutomationLibrary.take_high_res_screenshot(RES[0], RES[1], "lab6_posture_ready.png")
        yield from hwait(2.0)
        global out
        out = S["posture_log"]
    gen = _gen()
