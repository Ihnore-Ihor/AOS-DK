# AOS-DK | Lab 6 / Chat D | SK_Agro_WindGen UE 5.7.4 import (run via execute_python, editor open)
# Reads Tools/SK_Agro_WindGen_rig.json written by Tools/max_build_SK_WindGen.py.
# Imports SK_Agro_WindGen (+ SKEL_Agro_WindGen), assigns the existing MI_Atoll_* per slot, authors the 3 sockets and imports
# A_WindGen_Spin / A_WindGen_Hunt / A_WindGen_Furl (30 fps, exported time range) onto the skeleton.
import unreal, json, os
DST = "/Game/AOS_DK_Game/Environment/Atoll/WindGen"
MAT = "/Game/AOS_DK_Game/Environment/Atoll/Materials"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX = lambda n: os.path.join(PROJ, "Content/AOS_DK_Game/Environment/Atoll/WindGen/%s.fbx" % n)
TAKES = ("A_WindGen_Spin", "A_WindGen_Hunt", "A_WindGen_Furl")

def _task(fbx, name, opts, replace=True):
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = fbx, DST, name
    t.automated, t.replace_existing, t.save, t.options = True, replace, False, opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    return list(t.imported_object_paths)

def import_mesh(replace=True):
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = True; o.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False; o.create_physics_asset = False
    o.skeletal_mesh_import_data.set_editor_property("import_uniform_scale", 1.0)
    return _task(FBX("SK_Agro_WindGen"), "SK_Agro_WindGen", o, replace)

def finish_mesh():
    skm = unreal.load_asset(DST + "/SK_Agro_WindGen")
    skel = skm.get_editor_property("skeleton")
    if skel.get_name() != "SKEL_Agro_WindGen":
        unreal.EditorAssetLibrary.rename_asset(skel.get_path_name().split(".")[0], DST + "/SKEL_Agro_WindGen")
        skm = unreal.load_asset(DST + "/SK_Agro_WindGen"); skel = skm.get_editor_property("skeleton")
    # materials: slot MS_<X> -> MI_Atoll_<X>
    mats = []
    for sm in skm.get_editor_property("materials"):
        slot = str(sm.get_editor_property("material_slot_name"))
        mi = unreal.load_asset("%s/MI_Atoll_%s" % (MAT, slot.replace("MS_", "")))
        nm = unreal.SkeletalMaterial()
        nm.set_editor_property("material_interface", mi); nm.set_editor_property("material_slot_name", unreal.Name(slot))
        mats.append(nm)
    skm.modify(); skm.set_editor_property("materials", mats)
    # sockets from the rig json (Max y mirrored on import -> pos (x, y, z) is already UE-local)
    rig = json.load(open(os.path.join(PROJ, "Tools/SK_Agro_WindGen_rig.json")))
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
    for name, sd in rig["sockets"].items():
        s = skm.find_socket(name)
        if s is None:
            if skm.find_socket("Socket") is None:
                skm.add_socket(unreal.new_object(unreal.SkeletalMeshSocket, outer=skm), False)
            skm.rename_socket("Socket", name); s = skm.find_socket(name)
        bone_w = unreal.AnimPoseExtensions.get_bone_pose(pose, sd["bone"], unreal.AnimPoseSpaces.WORLD)
        sock_w = unreal.Transform(unreal.Vector(*sd["pos"]), unreal.Rotator(0, 0, 0), unreal.Vector(1, 1, 1))
        s.set_socket_parent(skm, sd["bone"]); s.set_socket_local_transform(sock_w.make_relative(bone_w))
    ns = skm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", False); skm.set_editor_property("nanite_settings", ns)
    unreal.EditorAssetLibrary.save_asset(DST + "/SK_Agro_WindGen", only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_asset(DST + "/SKEL_Agro_WindGen", only_if_is_dirty=False)
    return {"skeleton": skel.get_path_name(), "sockets": [str(skm.get_socket_by_index(i).socket_name) for i in range(skm.num_sockets())],
            "materials": [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name()) for m in skm.get_editor_property("materials")]}

def import_anims(replace=True):
    skel = unreal.load_asset(DST + "/SKEL_Agro_WindGen")
    out = {}
    for n in TAKES:
        o = unreal.FbxImportUI()
        o.import_mesh = False; o.import_as_skeletal = True; o.mesh_type_to_import = unreal.FBXImportType.FBXIT_ANIMATION
        o.import_animations = True; o.import_materials = False; o.import_textures = False; o.skeleton = skel
        d = o.anim_sequence_import_data
        d.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        d.set_editor_property("use_default_sample_rate", False); d.set_editor_property("custom_sample_rate", 30)
        d.set_editor_property("import_uniform_scale", 1.0); d.set_editor_property("remove_redundant_keys", False)
        d.set_editor_property("import_bone_tracks", True)
        out[n] = _task(FBX(n), n, o, replace)
        unreal.EditorAssetLibrary.save_asset(DST + "/" + n, only_if_is_dirty=False)
    return out

def anim_report():
    rep = {}
    for n in TAKES:
        a = unreal.load_asset(DST + "/" + n)
        rep[n] = {"length_s": round(a.get_play_length(), 4), "frames": unreal.AnimationLibrary.get_num_frames(a) if hasattr(unreal.AnimationLibrary, "get_num_frames") else None,
                  "rate": float(a.get_editor_property("target_frame_rate").numerator) / float(a.get_editor_property("target_frame_rate").denominator) if hasattr(a, "get_editor_property") else None,
                  "loop_hint": "loop" if n != "A_WindGen_Furl" else "one-shot"}
    return rep
