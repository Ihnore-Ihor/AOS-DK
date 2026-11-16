# Lab6 Batch D - create ABP_WindGen + BP_AOS_WindGen (idempotent)
import unreal
D = "/Game/AOS_DK_Game/Environment/Atoll/WindGen"
AT = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
R = {}

def ld(n): return unreal.load_asset(f"{D}/{n}")

sk = ld("SK_Agro_WindGen"); skel = ld("SKEL_Agro_WindGen")
R["sk"] = str(sk); R["skel"] = str(skel)

# --- ABP ---
if not EAL.does_asset_exist(f"{D}/ABP_WindGen"):
    f = unreal.AnimBlueprintFactory()
    f.set_editor_property("parent_class", unreal.load_class(None, "/Script/AOS_DK.AOSWindGenAnimInstance"))
    f.set_editor_property("target_skeleton", skel)
    abp = AT.create_asset("ABP_WindGen", D, unreal.AnimBlueprint, f)
else:
    abp = ld("ABP_WindGen")
try: abp.set_editor_property("preview_skeletal_mesh", sk)
except Exception as e: R["abp_preview_err"] = str(e)
unreal.BlueprintEditorLibrary.compile_blueprint(abp)
gc = abp.generated_class()
cdo = unreal.get_default_object(gc)
for p, n in (("spin_anim","A_WindGen_Spin"),("hunt_anim","A_WindGen_Hunt"),("furl_anim","A_WindGen_Furl")):
    cdo.set_editor_property(p, ld(n))
unreal.BlueprintEditorLibrary.compile_blueprint(abp)
EAL.save_asset(f"{D}/ABP_WindGen")
R["abp_class"] = str(gc)

# --- BP actor ---
if not EAL.does_asset_exist(f"{D}/BP_AOS_WindGen"):
    f = unreal.BlueprintFactory()
    f.set_editor_property("parent_class", unreal.load_class(None, "/Script/AOS_DK.AOSWindGenerator"))
    bp = AT.create_asset("BP_AOS_WindGen", D, unreal.Blueprint, f)
else:
    bp = ld("BP_AOS_WindGen")
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
bcdo = unreal.get_default_object(bp.generated_class())
R["props"] = [p for p in dir(bcdo) if "mesh" in p or "anim" in p][:20]
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
EAL.save_asset(f"{D}/BP_AOS_WindGen")
R["bp_class"] = str(bp.generated_class())
result = R
