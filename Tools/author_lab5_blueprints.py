# AOS-DK | Lab 5 | Task 1: Blueprint assets for the RPR-6 "OOM Reaper" (idempotent, run via execute_python)
#   Content/AOS_DK_Game/Enemies/Reaper/Blueprints/{BP_AIWeapon_SigkillPike, BP_OOMReaper, BP_AIObstacle_BrinePool}
# Config-only Blueprints (0 logic nodes): every behaviour lives in C++ (spec 3.3 / 3.7).
# Run: g={}; exec(open(<proj>/Tools/author_lab5_blueprints.py, encoding="utf-8").read(), g); result=g["result"]
import unreal

DST = "/Game/AOS_DK_Game/Enemies/Reaper/Blueprints"
MESH_DIR = "/Game/AOS_DK_Game/Enemies/Reaper/Meshes"
EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
log = []

def ensure_bp(name, parent):
    path = f"{DST}/{name}"
    if EAL.does_asset_exist(path):
        log.append(f"reuse {name}")
        return EAL.load_asset(path)
    f = unreal.BlueprintFactory()
    f.set_editor_property("parent_class", parent)
    bp = AT.create_asset(name, DST, unreal.Blueprint, f)
    log.append(f"create {name}")
    return bp

def cdo_of(bp):
    return unreal.get_default_object(EAL.load_blueprint_class(f"{DST}/{bp.get_name()}"))

def finish(bp):
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_asset(f"{DST}/{bp.get_name()}", only_if_is_dirty=False)

if not EAL.does_directory_exist(DST):
    EAL.make_directory(DST)

sk = unreal.load_asset(f"{MESH_DIR}/SK_OOMReaper")
pike = unreal.load_asset(f"{MESH_DIR}/SM_WPN_SigkillPike")
assert sk and pike, "Reaper meshes missing"

# ---- BP_AIWeapon_SigkillPike : AAOS_AIWeapon with SM_WPN_SigkillPike --------------------------------------------------
bp_w = ensure_bp("BP_AIWeapon_SigkillPike", unreal.AOS_AIWeapon)
w = cdo_of(bp_w)
w.get_editor_property("pike_mesh").set_editor_property("static_mesh", pike)
w.set_editor_property("strike_damage_percent", 5.0)
w.set_editor_property("mount_socket", "SOCKET_Mount_Base")
w.set_editor_property("trace_start_socket", "SOCKET_Strike_Trace_Start")
w.set_editor_property("trace_end_socket", "SOCKET_Strike_Trace_End")
finish(bp_w)

# ---- BP_OOMReaper : AAOS_AIEnemyCharacter ---------------------------------------------------------------------------------
bp_r = ensure_bp("BP_OOMReaper", unreal.AOS_AIEnemyCharacter)
r = cdo_of(bp_r)
mesh = r.get_editor_property("mesh")
mesh.set_editor_property("skeletal_mesh_asset", sk)
mesh.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_BLUEPRINT)
mesh.set_editor_property("anim_class", unreal.AOS_ReaperAnimInstance.static_class())
# The whole-body HitVolume (420 x 380 x 200, blocks Pawn) is nav-relevant by default and bakes a hole into the NavMesh exactly where the
# Reaper stands (start point off the mesh -> every MoveTo fails -> endless survey). Combat queries (torpedoes / crosshair) are unaffected.
r.get_editor_property("hit_volume").set_editor_property("can_ever_affect_navigation", False)
r.set_editor_property("ai_controller_class", unreal.AOS_AIController.static_class())
r.set_editor_property("auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
r.set_editor_property("weapon_class", EAL.load_blueprint_class(f"{DST}/BP_AIWeapon_SigkillPike"))
r.set_editor_property("weapon_socket_name", "SOCKET_Weapon_Dorsal")
finish(bp_r)

# ---- BP_AIObstacle_BrinePool : AAOS_AIObstacleTrigger -------------------------------------------------------------------
bp_b = ensure_bp("BP_AIObstacle_BrinePool", unreal.AOS_AIObstacleTrigger)
b = cdo_of(bp_b)
b.get_editor_property("trigger_volume").set_editor_property("box_extent", unreal.Vector(500.0, 400.0, 120.0))
b.set_editor_property("surface_tint", unreal.Color(r=0xBD, g=0x93, b=0xF9, a=255))   # Dracula Purple #BD93F9
b.set_editor_property("surface_height", 2.0)
hz = b.get_editor_property("hazard_data")
hz.set_editor_property("speed_scale", 0.40)          # -60 % speed
hz.set_editor_property("sight_radius_scale", 0.5)    # sight halved
hz.set_editor_property("dodge_scale", 0.25)
hz.set_editor_property("block_decoy_regen", True)
b.set_editor_property("hazard_data", hz)
finish(bp_b)

def parent_name(bp):
    # the CDO's native base: first C++ class in the generated class chain (Blueprint.parent_class is not exposed to Python)
    c = cdo_of(bp)
    for n in ("AOS_AIEnemyCharacter", "AOS_AIObstacleTrigger", "AOS_AIWeapon"):
        if isinstance(c, getattr(unreal, n)):
            return n
    return "?"

# ---- read-back verification -----------------------------------------------------------------------------------------------
r = cdo_of(bp_r); b = cdo_of(bp_b); w = cdo_of(bp_w)
chk = {
    "BP_OOMReaper.parent": parent_name(bp_r),
    "BP_OOMReaper.mesh": r.get_editor_property("mesh").get_editor_property("skeletal_mesh_asset").get_name(),
    "BP_OOMReaper.anim_class": r.get_editor_property("mesh").get_editor_property("anim_class").get_name(),
    "BP_OOMReaper.ai_controller": r.get_editor_property("ai_controller_class").get_name(),
    "BP_OOMReaper.weapon_class": r.get_editor_property("weapon_class").get_name(),
    "BP_OOMReaper.hitvolume_affects_nav": r.get_editor_property("hit_volume").get_editor_property("can_ever_affect_navigation"),
    "BP_OOMReaper.weapon_socket": str(r.get_editor_property("weapon_socket_name")),
    "BP_AIWeapon.pike_mesh": w.get_editor_property("pike_mesh").get_editor_property("static_mesh").get_name(),
    "BP_AIObstacle.parent": parent_name(bp_b),
    "BP_AIObstacle.extent": str(b.get_editor_property("trigger_volume").get_editor_property("box_extent")),
    "BP_AIObstacle.tint": str(b.get_editor_property("surface_tint")),
}
result = {"log": log, "check": chk}
