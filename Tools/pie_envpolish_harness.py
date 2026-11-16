"""AOS-DK Lab 6 env-polish interactive PIE harness (diagnosis + verification).
Usage (MCP execute_python):
  g = {"EP_MODE": "start"|"run"|"poll"|"stop", "EP_CODE": "<python>"}; exec(open(r"<proj>/Tools/pie_envpolish_harness.py", encoding="utf-8").read(), g); result = g["result"]
start: PIE begins and a slate post-tick driver is registered.
run:   queues EP_CODE; it executes inside the tick. It may define a generator `gen` (use `yield` to wait a frame) and set `out`.
poll:  {state, out, error}.   stop: ends PIE.
Helpers available to EP_CODE: unreal, gw(), cmd(c), now(), wait(sec), find(cls), snap(name), mpc_get(name), json
"""
import json, os
import unreal

MODE = globals().get("EP_MODE", "poll")
CODE = globals().get("EP_CODE", "")
GS = unreal.GameplayStatics
MPC_PATH = "/Game/AOS_DK_Game/Environment/Water/MPC_AOS_Atoll"


def gw():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def cmd(c):
    unreal.SystemLibrary.execute_console_command(gw(), c)


def now():
    return GS.get_time_seconds(gw())


def wait(sec):
    end = now() + sec
    while now() < end:
        yield


def find(cls):
    a = GS.get_all_actors_of_class(gw(), cls)
    return a[0] if a else None


def mpc_get(name):
    return unreal.MaterialLibrary.get_scalar_parameter_value(gw(), unreal.load_asset(MPC_PATH), name)


def snap(name):
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, name)


def driver(dt):
    S = unreal._ep
    if S.get("busy"):
        return
    S["busy"] = True
    try:
        if gw() is None:
            return
        if S["gen"] is None and S["pending"]:
            code, S["pending"] = S["pending"], None
            G = dict(unreal=unreal, gw=gw, cmd=cmd, now=now, wait=wait, find=find, snap=snap, mpc_get=mpc_get, json=json, os=os, S=S, GS=GS, out=None, gen=None)
            exec(code, G)
            S["out"] = G.get("out")
            S["gen"] = G.get("gen")
            S["G"] = G
            S["state"] = "running" if S["gen"] else "idle"
        if S["gen"] is not None:
            try:
                next(S["gen"])
            except StopIteration:
                S["gen"] = None
                S["out"] = S["G"].get("out")
                S["state"] = "idle"
    except Exception:
        import traceback
        S["error"] = traceback.format_exc()[-1800:]
        S["gen"] = None
        S["state"] = "error"
    finally:
        S["busy"] = False


if MODE == "start":
    ps = unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings"))
    unreal._ep = {"state": "boot", "gen": None, "pending": None, "out": None, "error": None, "busy": False,
                  "throttle_was": ps.get_editor_property("bThrottleCPUWhenNotForeground")}
    ps.set_editor_property("bThrottleCPUWhenNotForeground", False)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal._ep["handle"] = unreal.register_slate_post_tick_callback(driver)
    result = {"started": True}
elif MODE == "run":
    S = unreal._ep
    S["error"] = None
    S["state"] = "queued"
    S["pending"] = CODE
    result = {"queued": True}
elif MODE == "poll":
    S = unreal._ep
    result = {"state": S["state"], "out": S["out"], "error": S["error"]}
elif MODE == "stop":
    S = unreal._ep
    try:
        unreal.unregister_slate_post_tick_callback(S["handle"])
    except Exception:
        pass
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
    unreal.get_default_object(unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")).set_editor_property(
        "bThrottleCPUWhenNotForeground", S["throttle_was"])
    result = {"stopped": True}
