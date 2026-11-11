# AOS-DK | Lab 5 | Task 2: submerged walking terrace "RPR_Arena" + NavMesh + Navigation Runtime Generation (idempotent)
#   Arena: 40 x 40 m concrete terrace, top surface Z = -9800 cm, east of Cluster C-01 A-3 (X -45500..-41500, Y 20000..24000),
#   built from SM_AOS_ShellBox (same slab asset / material family as the C-01 build) with a 120 cm parapet and 5 occluders.
#   NavMesh: one NavMeshBoundsVolume over the arena; RecastNavMesh tuned to the Reaper (agent R 140 / H 280, step 60, slope 35),
#   Runtime Generation = Dynamic Modifiers Only (spec 3.1) so UAOS_NavArea_Brine from the brine pool is honoured.
# Run: g={}; exec(open(<proj>/Tools/setup_lab5_arena.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, os

CX, CY, FLOOR_TOP = -43500.0, 22000.0, -9800.0
HALF = 2000.0                                   # 40 x 40 m
FOLDER = "Environment/Enemies/Reaper/Arena"
BOX = "/Game/AOS_DK_Game/Environment/Clusters/Shared/SM_AOS_ShellBox"       # 100 cm cube, pivot at the min corner
MAT_FLOOR = "/Game/AOS_DK_Game/Environment/Clusters/Shared/MI_A03_Concrete_Floor"

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
EAL = unreal.EditorAssetLibrary
log = []
by_label = {a.get_actor_label(): a for a in eas.get_all_level_actors()}

def box(label, min_xyz, size_xyz):
    """Axis-aligned slab/block of SM_AOS_ShellBox, idempotent by label."""
    a = by_label.get(label)
    if a is None:
        a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*min_xyz), unreal.Rotator(0, 0, 0))
        a.set_actor_label(label)
        c = a.static_mesh_component
        c.set_editor_property("static_mesh", EAL.load_asset(BOX))
        c.set_material(0, EAL.load_asset(MAT_FLOOR))
        log.append("spawn " + label)
        by_label[label] = a
    a.set_actor_location(unreal.Vector(*min_xyz), False, False)
    a.set_actor_scale3d(unreal.Vector(size_xyz[0] / 100.0, size_xyz[1] / 100.0, size_xyz[2] / 100.0))
    a.set_folder_path(FOLDER)
    return a

# ---- terrace floor (top at -9800, like the C-01 floors) + parapet + occluders ------------------------------------------
box("RPR_Arena_Floor", (CX - HALF, CY - HALF, FLOOR_TOP - 100), (2 * HALF, 2 * HALF, 100))
P, H = 100.0, 120.0                               # parapet thickness / height (stops the walker from skittering off the edge)
box("RPR_Arena_Parapet_S", (CX - HALF, CY - HALF, FLOOR_TOP), (2 * HALF, P, H))
box("RPR_Arena_Parapet_N", (CX - HALF, CY + HALF - P, FLOOR_TOP), (2 * HALF, P, H))
box("RPR_Arena_Parapet_W", (CX - HALF, CY - HALF + P, FLOOR_TOP), (P, 2 * HALF - 2 * P, H))
box("RPR_Arena_Parapet_E", (CX + HALF - P, CY - HALF + P, FLOOR_TOP), (P, 2 * HALF - 2 * P, H))
OCC = [  # label, centre offset (dx, dy), footprint (sx, sy), height
    ("RPR_Arena_Occluder_HVAC_01", (-700, 500), (300, 300), 300),
    ("RPR_Arena_Occluder_HVAC_02", (700, 500), (300, 300), 300),
    ("RPR_Arena_Occluder_Pillar_01", (-1000, -200), (120, 120), 500),
    ("RPR_Arena_Occluder_Pillar_02", (1000, -200), (120, 120), 500),
    ("RPR_Arena_Occluder_Tank_01", (0, 1200), (400, 250), 200),
]
for label, (dx, dy), (sx, sy), h in OCC:
    box(label, (CX + dx - sx / 2, CY + dy - sy / 2, FLOOR_TOP), (sx, sy, h))

# ---- NavMeshBoundsVolume ----------------------------------------------------------------------------------------------------
NAV_SIZE = (2 * HALF + 400.0, 2 * HALF + 400.0, 950.0)                       # X, Y, Z cm
NAV_CENTER = (CX, CY, FLOOR_TOP - 150.0 + NAV_SIZE[2] / 2.0)                 # Z -9950 .. -9000
vol = by_label.get("RPR_Arena_NavBounds")
if vol is None:
    vol = eas.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(*NAV_CENTER), unreal.Rotator(0, 0, 0))
    vol.set_actor_label("RPR_Arena_NavBounds")
    log.append("spawn RPR_Arena_NavBounds")
vol.set_actor_scale3d(unreal.Vector(1, 1, 1))
vol.set_actor_location(unreal.Vector(*NAV_CENTER), False, False)
_, e0 = vol.get_actor_bounds(False)
if e0.x < 1 or e0.y < 1 or e0.z < 1:
    raise RuntimeError(f"NavMeshBoundsVolume brush is empty (extent {e0}); cannot scale")
vol.set_actor_scale3d(unreal.Vector(NAV_SIZE[0] / 2.0 / e0.x, NAV_SIZE[1] / 2.0 / e0.y, NAV_SIZE[2] / 2.0 / e0.z))
vol.set_folder_path(FOLDER)

# ---- Navigation: Runtime Generation = Dynamic Modifiers Only ------------------------------------------------------------
# (a) persistent project setting: Config/DefaultEngine.ini [/Script/NavigationSystem.RecastNavMesh]
ini = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_config_dir()), "DefaultEngine.ini")
want = {"RuntimeGeneration": "DynamicModifiersOnly", "AgentRadius": "140.0", "AgentHeight": "280.0",
        "AgentMaxStepHeight": "60.0", "AgentMaxSlope": "35.0", "CellSize": "20.0", "CellHeight": "10.0"}
text = open(ini, encoding="utf-8").read()
header = "[/Script/NavigationSystem.RecastNavMesh]"
if header not in text:
    text = text.rstrip("\n") + "\n\n" + header + "\n" + "\n".join(f"{k}={v}" for k, v in want.items()) + "\n"
    open(ini, "w", encoding="utf-8").write(text)
    log.append("ini: added " + header)
else:
    lines = text.split("\n"); out = []; i = 0; in_sec = False; seen = set()
    for ln in lines:
        if ln.strip().startswith("["):
            if in_sec:   # leaving the section: append whatever is missing
                out += [f"{k}={v}" for k, v in want.items() if k not in seen]
            in_sec = ln.strip() == header
        elif in_sec and "=" in ln and ln.split("=", 1)[0].strip() in want:
            k = ln.split("=", 1)[0].strip(); ln = f"{k}={want[k]}"; seen.add(k)
        out.append(ln)
    if in_sec:
        out += [f"{k}={v}" for k, v in want.items() if k not in seen]
    new = "\n".join(out)
    if new != text:
        open(ini, "w", encoding="utf-8").write(new); log.append("ini: updated " + header)

# (a2) Supported Agent "Reaper": the walker's capsule (R 120) must not be pathed on a NavMesh baked for the default 35 cm agent.
SA_HEADER = "[/Script/NavigationSystem.NavigationSystemV1]"
SA_LINE = ('+SupportedAgents=(Name="Reaper",Color=(B=0,G=255,R=140,A=164),DefaultQueryExtent=(X=50.000000,Y=50.000000,Z=250.000000),'
           'NavDataClass=/Script/NavigationSystem.RecastNavMesh,AgentRadius=140.000000,AgentHeight=280.000000,AgentStepHeight=-1.000000,'
           'NavWalkingSearchHeightScale=0.500000)')
text = open(ini, encoding="utf-8").read()
if "Name=\"Reaper\"" not in text:
    if SA_HEADER in text:
        text = text.replace(SA_HEADER, SA_HEADER + "\n" + SA_LINE, 1)
    else:
        text = text.rstrip("\n") + "\n\n" + SA_HEADER + "\n" + SA_LINE + "\n"
    open(ini, "w", encoding="utf-8").write(text)
    log.append("ini: added SupportedAgents Reaper")

# (b) live CDO (so the running editor agrees without a restart) and the level's RecastNavMesh actor
RG = unreal.RuntimeGenerationType.DYNAMIC_MODIFIERS_ONLY
rcls = unreal.load_class(None, "/Script/NavigationSystem.RecastNavMesh")
def tune(n):
    n.set_editor_property("runtime_generation", RG)
    n.set_editor_property("agent_radius", 140.0)
    n.set_editor_property("agent_height", 280.0)
    n.set_editor_property("agent_max_slope", 35.0)
tune(unreal.get_default_object(rcls))
def reaper_agent():
    c = unreal.NavDataConfig()
    c.set_editor_property("name", "Reaper")
    c.set_editor_property("agent_radius", 140.0)
    c.set_editor_property("agent_height", 280.0)
    c.set_editor_property("nav_data_class", rcls)
    return c
_nsys = unreal.get_default_object(unreal.load_class(None, "/Script/NavigationSystem.NavigationSystemV1"))
_nsys.set_editor_property("supported_agents", [reaper_agent()])
_world_nav = unreal.NavigationSystemV1.get_navigation_system(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world())
if _world_nav is not None:
    _world_nav.set_editor_property("supported_agents", [reaper_agent()])
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
navs = [a for a in eas.get_all_level_actors() if a.get_class().get_name() == "RecastNavMesh"]
if not navs:
    unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")   # the volume makes the nav system spawn RecastNavMesh-Default
    navs = [a for a in eas.get_all_level_actors() if a.get_class().get_name() == "RecastNavMesh"]
for n in navs:
    tune(n)
    n.set_folder_path(FOLDER)
unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")

result = {
    "log": log,
    "supported_agents": [(c.get_editor_property("name"), c.get_editor_property("agent_radius"), c.get_editor_property("agent_height")) for c in _nsys.get_editor_property("supported_agents")],
    "floor_top_z": FLOOR_TOP,
    "arena_bounds_xy": [[CX - HALF, CY - HALF], [CX + HALF, CY + HALF]],
    "nav_volume": {"center": list(NAV_CENTER), "size": list(NAV_SIZE), "bounds_extent": [round(v) for v in vol.get_actor_bounds(False)[1].to_tuple()] if hasattr(vol.get_actor_bounds(False)[1], "to_tuple") else str(vol.get_actor_bounds(False)[1])},
    "recast_actors": [(n.get_name(), str(n.get_editor_property("runtime_generation")), n.get_editor_property("agent_radius"), n.get_editor_property("agent_height")) for n in navs],
}
