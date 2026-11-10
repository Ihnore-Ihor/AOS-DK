"""AOS-DK Lab 3 - Interactables suite: asset authoring (UE 5.7.4, editor Python via MCP execute_python).
Usage:  g = {"AI_MODE": "import" | "materials" | "blueprints" | "verify" | "all"}
        exec(open(r"<proj>/Tools/author_interactables.py", encoding="utf-8").read(), g); result = g["result"]
Sources: SourceArt/Interactables (Tools/gen_interactable_assets.py). Native bases: Source/AOS_DK/Gameplay/Interactables.
Idempotent: re-running replaces meshes/sounds in place and re-applies every Blueprint default."""
import os
import unreal

MODE = globals().get("AI_MODE", "all")
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SRC = os.path.join(PROJ, "SourceArt", "Interactables")
ROOT = "/Game/AOS_DK_Game/Gameplay/Interactables"
D_MESH, D_MAT, D_AUD, D_PHYS = ROOT + "/Meshes", ROOT + "/Materials", ROOT + "/Audio", ROOT + "/Physics"
EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
HERO = "/Game/AOS_DK_Game/Environment/CustomHero/Materials/M_AOS_HeroSurface"
KIT = "/Game/AOS_DK_Game/Environment/ModularKit/Materials/"
DRUM = "/Game/Scene_UnfinishedBuilding/Assets/Megascans/3D_Assets/Ind_Fac_Container_Drum_Metal_Worn_02/SM_Ind_Fac_Container_Drum_Metal_Worn_02"
POD = "/Game/AOS_DK_Game/Environment/CustomHero/SM_Cargo_Pod_Phys"
FX_BUBBLES = "/Game/AOS_DK_Game/Submarine/Subdrones/Attacker/FX/NS_DroneBubbles"
FX_HIT = "/Game/AOS_DK_Game/Submarine/Subdrones/Attacker/FX/NS_TorpedoHit"

def srgb(h):
    c = unreal.LinearColor(); r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    f = lambda x: x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return unreal.LinearColor(f(r), f(g), f(b), 1.0)

DRACULA = {"Yellow": "F1FA8C", "Green": "50FA7B", "Pink": "FF79C6", "Purple": "BD93F9", "Orange": "FFB86C"}
MI_SPECS = {  # name: (base rgb linear, metallic, roughness, emissive hex or None, emissive intensity)
    "MI_Pickup_Glow_Yellow": ((0, 0, 0), 0.0, 0.35, "Yellow", 9.0),
    "MI_Pickup_Glow_Green": ((0, 0, 0), 0.0, 0.35, "Green", 8.0),
    "MI_Pickup_Glow_Pink": ((0, 0, 0), 0.0, 0.35, "Pink", 9.0),
    "MI_Pickup_Glow_Purple": ((0, 0, 0), 0.0, 0.35, "Purple", 8.0),
    "MI_Bulkhead_Status_Orange": ((0, 0, 0), 0.0, 0.4, "Orange", 5.0),
    "MI_Cable_Sheath": ((0.016, 0.018, 0.014), 0.0, 0.78, None, 0.0),
    "MI_Cable_FiberCore": ((0, 0, 0), 0.0, 0.4, "Purple", 3.0),
}
MESH_SLOTS = {  # obj usemtl group -> material
    "SM_AOS_EnergyCell": {"Body": KIT + "MI_Kit_DarkSteel", "GlowA": D_MAT + "/MI_Pickup_Glow_Yellow", "GlowB": D_MAT + "/MI_Pickup_Glow_Green"},
    "SM_AOS_TorpedoCanister": {"Body": KIT + "MI_Kit_DarkSteel", "GlowA": D_MAT + "/MI_Pickup_Glow_Pink", "GlowB": D_MAT + "/MI_Pickup_Glow_Purple"},
    "SM_AOS_BulkheadSlab": {"Steel": KIT + "MI_Kit_DarkSteel", "Frame": KIT + "MI_Kit_Galvanized", "Status": D_MAT + "/MI_Bulkhead_Status_Orange"},
    "SM_AOS_CableTangle": {"Sheath": D_MAT + "/MI_Cable_Sheath", "Core": D_MAT + "/MI_Cable_FiberCore"},
}
MESH_COLLISION = {"SM_AOS_EnergyCell": None, "SM_AOS_TorpedoCanister": None,
                  "SM_AOS_BulkheadSlab": "BOX", "SM_AOS_CableTangle": "BOX"}
MESH_NANITE = {"SM_AOS_CableTangle": True}
SOUNDS = ["SW_Pickup_EnergyChime", "SW_Pickup_TorpedoLatch", "SW_Tangle_Snag", "SW_Tangle_Sever"]
log = []

def ensure_dirs():
    for d in (ROOT, D_MESH, D_MAT, D_AUD, D_PHYS):
        if not EAL.does_directory_exist(d):
            EAL.make_directory(d)

def import_file(path, dest, name):
    t = unreal.AssetImportTask()
    t.filename = path; t.destination_path = dest; t.destination_name = name
    t.automated = True; t.replace_existing = True; t.save = False
    AT.import_asset_tasks([t])
    return list(t.imported_object_paths)

def do_import():
    ensure_dirs()
    for name in MESH_SLOTS:
        before = set(EAL.list_assets(D_MESH, recursive=True, include_folder=False))
        paths = import_file(os.path.join(SRC, name + ".obj"), D_MESH, name)
        after = set(EAL.list_assets(D_MESH, recursive=True, include_folder=False))
        # Interchange creates placeholder materials/textures for the OBJ groups: drop them, slots are reassigned below.
        for extra in sorted(after - before):
            a = EAL.find_asset_data(extra)
            if str(a.asset_class_path.asset_name) not in ("StaticMesh",):
                EAL.delete_asset(extra)
        log.append(("import", name, paths))
    for s in SOUNDS:
        paths = import_file(os.path.join(SRC, s + ".wav"), D_AUD, s)
        log.append(("import", s, paths))

def do_materials():
    ensure_dirs()
    parent = EAL.load_asset(HERO)
    mel = unreal.MaterialEditingLibrary
    for name, (base, met, rough, emi, inten) in MI_SPECS.items():
        path = D_MAT + "/" + name
        mi = EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name, D_MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, parent)
        mel.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(base[0], base[1], base[2], 1))
        mel.set_material_instance_vector_parameter_value(mi, "EmissiveColor", srgb(DRACULA[emi]) if emi else unreal.LinearColor(0, 0, 0, 1))
        mel.set_material_instance_scalar_parameter_value(mi, "Metallic", met)
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        mel.set_material_instance_scalar_parameter_value(mi, "EmissiveIntensity", inten)
        mel.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
    # physical material for the cargo pod skids (low friction so Shell-1 can shove 1.5 t smoothly)
    pm_path = D_PHYS + "/PM_AOS_CargoSkid"
    pm = EAL.load_asset(pm_path) if EAL.does_asset_exist(pm_path) else AT.create_asset("PM_AOS_CargoSkid", D_PHYS, unreal.PhysicalMaterial, unreal.PhysicalMaterialFactoryNew())
    pm.set_editor_property("friction", 0.3)
    pm.set_editor_property("static_friction", 0.35)
    pm.set_editor_property("restitution", 0.05)
    pm.set_editor_property("override_friction_combine_mode", True)
    pm.set_editor_property("friction_combine_mode", unreal.FrictionCombineMode.MIN)
    EAL.save_loaded_asset(pm)
    # mesh slots + collision + nanite
    sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for name, slots in MESH_SLOTS.items():
        mesh = EAL.load_asset(D_MESH + "/" + name)
        if not mesh:
            log.append(("missing mesh", name)); continue
        mats = list(mesh.static_materials)
        for i, sm in enumerate(mats):
            slot = str(sm.material_slot_name)
            key = next((k for k in slots if slot == k or slot.startswith(k) or slot.endswith(k)), None)
            if key:
                mesh.set_material(i, EAL.load_asset(slots[key]))
            log.append(("slot", name, i, slot, key))
        sms.remove_collisions(mesh)
        if MESH_COLLISION[name] == "BOX":
            sms.add_simple_collisions(mesh, unreal.ScriptingCollisionShapeType.BOX)
        ns = mesh.get_editor_property("nanite_settings")
        ns.enabled = bool(MESH_NANITE.get(name, False))
        mesh.set_editor_property("nanite_settings", ns)
        EAL.save_loaded_asset(mesh)
    for s in SOUNDS:
        sw = EAL.load_asset(D_AUD + "/" + s)
        if sw:
            EAL.save_loaded_asset(sw)

def native(cls_name):
    return unreal.load_class(None, "/Script/AOS_DK." + cls_name)

def make_bp(name, parent):
    path = ROOT + "/" + name
    if EAL.does_asset_exist(path):
        return EAL.load_asset(path)
    f = unreal.BlueprintFactory(); f.set_editor_property("parent_class", parent)
    return AT.create_asset(name, ROOT, unreal.Blueprint, f)

def cdo_of(bp):
    return unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(bp.get_path_name().split(".")[0]))

def comp(cdo, name):
    return cdo.get_editor_property(name)

BP_SPECS = {
    "BP_Phys_CargoPod": ("AOSPhysicsProp", {"mesh": POD, "mass": 1500.0, "buoy": 0.4, "contact": D_PHYS + "/PM_AOS_CargoSkid"}),
    "BP_Phys_BuoyantDrum": ("AOSPhysicsProp", {"mesh": DRUM, "mass": 45.0, "buoy": 3.5}),
    "BP_Obstacle_Bulkhead": ("AOSStaticObstacle", {"mesh": D_MESH + "/SM_AOS_BulkheadSlab"}),
    "BP_Obstacle_CableTangle": ("AOSCableTangle", {"mesh": D_MESH + "/SM_AOS_CableTangle", "snag": D_AUD + "/SW_Tangle_Snag", "sever": D_AUD + "/SW_Tangle_Sever", "fx": FX_HIT}),
    "BP_Pickup_EnergyCell": ("AOSPickup_EnergyCell", {"mesh": D_MESH + "/SM_AOS_EnergyCell", "sound": D_AUD + "/SW_Pickup_EnergyChime", "fx": FX_BUBBLES, "light": "Yellow"}),
    "BP_Pickup_TorpedoMagazine": ("AOSPickup_TorpedoMagazine", {"mesh": D_MESH + "/SM_AOS_TorpedoCanister", "sound": D_AUD + "/SW_Pickup_TorpedoLatch", "fx": FX_BUBBLES, "light": "Pink"}),
}

def do_blueprints():
    ensure_dirs()
    for name, (parent_name, spec) in BP_SPECS.items():
        parent = native(parent_name)
        if not parent:
            log.append(("missing native class", parent_name)); continue
        bp = make_bp(name, parent)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        cdo = cdo_of(bp)
        mesh_c = comp(cdo, "mesh")
        mesh_c.set_editor_property("static_mesh", EAL.load_asset(spec["mesh"]))
        if parent_name == "AOSPhysicsProp":
            fp = comp(cdo, "fluid_physics")
            fp.set_editor_property("mass_override_kg", spec["mass"])
            fp.set_editor_property("buoyancy_factor", spec["buoy"])
            fp.set_editor_property("ocean_surface_z", 0.0)
            bi = mesh_c.get_editor_property("body_instance")
            bi.set_editor_property("override_mass", True)
            bi.set_editor_property("mass_in_kg_override", spec["mass"])
            mesh_c.set_editor_property("body_instance", bi)
            if spec.get("contact"):
                cdo.set_editor_property("contact_material", EAL.load_asset(spec["contact"]))
        elif parent_name == "AOSCableTangle":
            cdo.set_editor_property("snag_sound", EAL.load_asset(spec["snag"]))
            cdo.set_editor_property("sever_sound", EAL.load_asset(spec["sever"]))
            cdo.set_editor_property("sever_fx", EAL.load_asset(spec["fx"]))
        elif parent_name.startswith("AOSPickup"):
            cdo.set_editor_property("collect_sound", EAL.load_asset(spec["sound"]))
            cdo.set_editor_property("collect_fx", EAL.load_asset(spec["fx"]))
            glow = comp(cdo, "glow")
            glow.set_editor_property("light_color", unreal.Color(*[int(spec_hex, 16) for spec_hex in (DRACULA[spec["light"]][0:2], DRACULA[spec["light"]][2:4], DRACULA[spec["light"]][4:6])], 255))
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        EAL.save_loaded_asset(bp)
        log.append(("bp", name))

def do_verify():
    out = {}
    for name, (parent_name, spec) in BP_SPECS.items():
        path = ROOT + "/" + name
        if not EAL.does_asset_exist(path):
            out[name] = "MISSING"; continue
        cdo = cdo_of(EAL.load_asset(path))
        m = comp(cdo, "mesh")
        d = {"parent": parent_name, "mesh": m.static_mesh.get_name() if m.static_mesh else None,
             "profile": str(m.get_collision_profile_name()), "mobility": str(m.mobility),
             "sim": m.is_simulating_physics() if hasattr(m, "is_simulating_physics") else None,
             "sim_flag": m.get_editor_property("body_instance").get_editor_property("simulate_physics")}
        if parent_name == "AOSPhysicsProp":
            fp = comp(cdo, "fluid_physics")
            d.update(mass=fp.get_editor_property("mass_override_kg"), B=fp.get_editor_property("buoyancy_factor"),
                     immune=fp.get_editor_property("wave_immune_mass_kg"), ref=fp.get_editor_property("wave_reference_mass_kg"),
                     contact=(cdo.get_editor_property("contact_material").get_name() if cdo.get_editor_property("contact_material") else None))
        if parent_name == "AOSCableTangle":
            d.update(tags=[str(t) for t in cdo.tags], damping=cdo.get_editor_property("velocity_damping"),
                     dur=cdo.get_editor_property("entangle_duration"), hp=cdo.get_editor_property("max_integrity"),
                     overlaps=m.get_editor_property("generate_overlap_events"))
        if parent_name.startswith("AOSPickup"):
            trig = comp(cdo, "trigger")
            d.update(trigger=str(trig.get_collision_profile_name()), r=trig.get_editor_property("sphere_radius"),
                     sound=cdo.get_editor_property("collect_sound").get_name() if cdo.get_editor_property("collect_sound") else None,
                     amount=(cdo.get_editor_property("energy_amount") if parent_name.endswith("EnergyCell") else cdo.get_editor_property("torpedo_count")))
        out[name] = d
    for name in MESH_SLOTS:
        mesh = EAL.load_asset(D_MESH + "/" + name)
        if not mesh:
            out[name] = "MISSING"; continue
        b = mesh.get_bounding_box()
        bs = mesh.get_editor_property("body_setup")
        agg = bs.get_editor_property("agg_geom") if bs else None
        out[name] = {"min": [round(b.min.x), round(b.min.y), round(b.min.z)], "max": [round(b.max.x), round(b.max.y), round(b.max.z)],
                     "slots": [str(s.material_slot_name) + "=" + (s.material_interface.get_name() if s.material_interface else "None") for s in mesh.static_materials],
                     "boxes": len(agg.get_editor_property("box_elems")) if agg else 0,
                     "nanite": mesh.get_editor_property("nanite_settings").enabled}
    return out

if MODE in ("import", "all"): do_import()
if MODE in ("materials", "all"): do_materials()
if MODE in ("blueprints", "all"): do_blueprints()
result = {"log": [str(x) for x in log]}
if MODE in ("verify", "all"): result["verify"] = do_verify()
