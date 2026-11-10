# AOS-DK | SK_LARS_RoboticArm | UE 5.7.4 import + socket authoring (run via execute_python)
# Reads Tools/SK_LARS_RoboticArm_rig.json written by max_build_SK_LARS_RoboticArm.py.
# Note 5.7: SkeletalMeshSocket.socket_name/bone_name are read-only from Python ->
#   add unnamed socket ("Socket"), rename_socket(), set_socket_parent(), set_socket_local_transform().
import unreal, json, os
DST = "/Game/AOS_DK_Game/Environment/CustomHero"
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
FBX = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/CustomHero/SK_LARS_RoboticArm.fbx")

def import_fbx(replace=False):
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = True
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    o.import_animations = False; o.import_materials = True; o.import_textures = False
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = FBX, DST, "SK_LARS_RoboticArm"
    t.automated, t.replace_existing, t.save, t.options = True, replace, False, o
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    return list(t.imported_object_paths)

def author_sockets():
    skm = unreal.load_asset(DST + "/SK_LARS_RoboticArm")
    pose = unreal.AnimPoseExtensions.get_reference_pose(skm.get_editor_property("skeleton"))
    rig = json.load(open(os.path.join(PROJ, "Tools/SK_LARS_RoboticArm_rig.json")))
    ue = lambda v: unreal.Vector(v[0], -v[1], v[2])          # Max RH -> UE LH
    skm.modify()
    for name, sd in rig["sockets"].items():
        s = skm.find_socket(name)
        if s is None:
            if skm.find_socket("Socket") is None:
                skm.add_socket(unreal.new_object(unreal.SkeletalMeshSocket, outer=skm), False)
            skm.rename_socket("Socket", name); s = skm.find_socket(name)
        bone_w = unreal.AnimPoseExtensions.get_bone_pose(pose, sd["bone"], unreal.AnimPoseSpaces.WORLD)
        sock_w = unreal.Transform(ue(sd["pos"]), unreal.MathLibrary.make_rot_from_xz(ue(sd["x"]), ue(sd["z"])), unreal.Vector(1, 1, 1))
        s.set_socket_parent(skm, sd["bone"])
        s.set_socket_local_transform(sock_w.make_relative(bone_w))
    ns = skm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", True)
    skm.set_editor_property("nanite_settings", ns)
    unreal.EditorAssetLibrary.save_asset(DST + "/SK_LARS_RoboticArm", only_if_is_dirty=False)
    return [str(skm.get_socket_by_index(i).socket_name) for i in range(skm.num_sockets())]

if __name__ == "__main__" or True:
    result = {"sockets": author_sockets()}
