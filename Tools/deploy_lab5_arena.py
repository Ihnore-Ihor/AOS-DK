# AOS-DK | Lab 5 | Task 3: idempotent deployment of the OOM Reaper encounter onto the submerged arena (run via execute_python)
#   * BP_OOMReaper  "RPR_A"            on the terrace (floor Z -9800 + capsule half height)
#   * BP_AIObstacle_BrinePool "RPR_BrinePool_01" across the SW->SE patrol leg (patrol filter detours, chase goes through)
#   * 4 patrol markers (ATargetPoint) RPR_Node_00..03, wired into the Reaper's PatrolNodes
#   * Lab 3 Daemons / spawners are only READ (fingerprinted before and after) - never touched
#   * Outliner folder  Environment/Enemies/Reaper
# Re-running updates the existing actors in place (matched by label); nothing is duplicated or deleted.
# Run: g={}; exec(open(<proj>/Tools/deploy_lab5_arena.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, os

PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
BP_DIR = "/Game/AOS_DK_Game/Enemies/Reaper/Blueprints"
FOLDER = "Environment/Enemies/Reaper"
CX, CY, FLOOR_TOP = -43500.0, 22000.0, -9800.0
CAPSULE_HH = 135.0
EAL = unreal.EditorAssetLibrary
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
log = []

def labels():
    return {a.get_actor_label(): a for a in eas.get_all_level_actors()}

def fingerprint(actors):
    out = {}
    for a in actors:
        l, r, sc = a.get_actor_location(), a.get_actor_rotation(), a.get_actor_scale3d()   # plain numbers (Struct repr carries addresses)
        out[a.get_path_name()] = (a.get_class().get_name(), tuple(round(v, 3) for v in (l.x, l.y, l.z, r.pitch, r.yaw, r.roll, sc.x, sc.y, sc.z)))
    return out

def lab3_actors():
    return [a for a in eas.get_all_level_actors() if a.get_class().get_name() in ("AOS_EnemyDaemon",) or "EnemyDaemon" in a.get_class().get_name() or "EnemySpawner" in a.get_class().get_name()]

# ---- 0. preconditions: arena + navmesh (Task 2) ------------------------------------------------------------------------------
cur = labels()
if "RPR_Arena_Floor" not in cur or "RPR_Arena_NavBounds" not in cur:
    g2 = {}
    exec(open(os.path.join(PROJ, "Tools/setup_lab5_arena.py"), encoding="utf-8").read(), g2)
    log.append("arena was missing -> ran setup_lab5_arena.py")
    cur = labels()

before = fingerprint(lab3_actors())

def get_or_spawn(label, cls, loc, rot=unreal.Rotator(0, 0, 0)):
    a = cur.get(label)
    if a is None:
        a = eas.spawn_actor_from_class(cls, loc, rot)
        a.set_actor_label(label)
        log.append("spawn " + label)
        cur[label] = a
    else:
        log.append("update " + label)
    a.set_actor_location_and_rotation(loc, rot, False, False)
    a.set_folder_path(FOLDER)
    return a

# ---- 1. patrol markers ---------------------------------------------------------------------------------------------------------
# SW -> SE crosses the brine pool, SE -> NE -> NW -> SW go round the occluders; every leg >= 26 m.
NODE_OFFSETS = [(-1300, -1300), (1300, -1300), (1300, 1300), (-1300, 1300)]
nodes = []
for i, (dx, dy) in enumerate(NODE_OFFSETS):
    n = get_or_spawn(f"RPR_Node_{i:02d}", unreal.TargetPoint, unreal.Vector(CX + dx, CY + dy, FLOOR_TOP + 10.0))
    nodes.append(n)

# ---- 2. brine pool ---------------------------------------------------------------------------------------------------------------
pool_cls = EAL.load_blueprint_class(f"{BP_DIR}/BP_AIObstacle_BrinePool")
pool = get_or_spawn("RPR_BrinePool_01", pool_cls, unreal.Vector(CX, CY - 1300.0, FLOOR_TOP))   # origin at floor level, box +-120

# ---- 3. the Reaper ---------------------------------------------------------------------------------------------------------------
reaper_cls = EAL.load_blueprint_class(f"{BP_DIR}/BP_OOMReaper")
reaper = get_or_spawn("RPR_A", reaper_cls, unreal.Vector(CX - 1300.0, CY + 1300.0, FLOOR_TOP + CAPSULE_HH + 5.0), unreal.Rotator(0, -90, 0))
reaper.set_editor_property("patrol_nodes", nodes)
# The BP default already switches the whole-body HitVolume off for navigation; mirror it on the placed instance so the NavMesh never gets a hole under the Reaper.
reaper.get_editor_property("hit_volume").set_editor_property("can_ever_affect_navigation", False)
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), "RebuildNavigation")

# ---- 4. Lab 3 coexistence: read-only confirmation -------------------------------------------------------------------------------
after = fingerprint(lab3_actors())
daemons = [a for a in lab3_actors() if "EnemyDaemon" in a.get_class().get_name() and "Spawner" not in a.get_class().get_name()]
spawners = [a for a in lab3_actors() if "EnemySpawner" in a.get_class().get_name()]
def dist_xy(a):
    l = a.get_actor_location(); return round(((l.x - CX) ** 2 + (l.y - CY) ** 2) ** 0.5 / 100.0, 1)

# ---- 5. verification ----------------------------------------------------------------------------------------------------------
all_actors = eas.get_all_level_actors()
def count(label): return sum(1 for a in all_actors if a.get_actor_label() == label)
fol = {l: cur[l].get_folder_path() for l in ["RPR_A", "RPR_BrinePool_01"] + [f"RPR_Node_{i:02d}" for i in range(4)]}
pn = reaper.get_editor_property("patrol_nodes")
result = {
    "log": log,
    "reaper": {"label": "RPR_A", "class": reaper.get_class().get_name(), "loc": [round(v) for v in reaper.get_actor_location().to_tuple()],
               "patrol_nodes": [n.get_actor_label() for n in pn], "count": count("RPR_A")},
    "brine_pool": {"class": pool.get_class().get_name(), "loc": [round(v) for v in pool.get_actor_location().to_tuple()], "count": count("RPR_BrinePool_01")},
    "markers": {n.get_actor_label(): [round(v) for v in n.get_actor_location().to_tuple()] for n in nodes},
    "outliner_folders": fol,
    "all_in_folder": all(v == FOLDER for v in fol.values()),
    "lab3": {"placed_daemons_in_editor": len(daemons), "spawners": [(s.get_actor_label(), dist_xy(s)) for s in spawners],
             "spawner_to_arena_m": [dist_xy(s) for s in spawners], "untouched": before == after, "n_fingerprinted": len(before)},
}
