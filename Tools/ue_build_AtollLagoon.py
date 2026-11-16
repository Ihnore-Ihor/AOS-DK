"""
AOS_DK - Pontoon Atoll Stage 2B: calm-lagoon wave mask (GPU side), Taylor curtains, level hook-up (UE 5.7.4).
Run in the editor with MODE preset in globals:  MODE in ("gpu", "fx", "place", "save").
Values mirror UAOSAtollSettings (C++ defaults); AAOSDampingPerimeter warns if MPC defaults drift.
"""
import math
import re
import unreal

W = "/Game/AOS_DK_Game/Environment/Water"
FXD = "/Game/AOS_DK_Game/Environment/Atoll/FX"
CENTER = (-1000.0, 700.0)
WATER_Z = 40.0
R_CALM, R_FULL, RING_R, RING_W = 11200.0, 15200.0, 11000.0, 120.0
GATES = (180.0, 60.0, 300.0)
GATE_HALF, GATE_R, GATE_W, GATE_K = 0.0667, 12120.0, 400.0, 0.9
FOAM_ROUGHNESS = 0.8

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
fx = unreal.AOSDKFxAuthoringLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
E = unreal
log = []

MASK_CODE = r"""
struct FAOSAtollNoise
{
    float H(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }
    float N(float2 p)
    {
        float2 i = floor(p); float2 f = frac(p); f = f * f * (3.0 - 2.0 * f);
        return lerp(lerp(H(i), H(i + float2(1, 0)), f.x), lerp(H(i + float2(0, 1)), H(i + float2(1, 1)), f.x), f.y);
    }
};
FAOSAtollNoise Nz;
float d = length(Rel);
float A = smoothstep(Radii.x, Radii.y, d);                       // Bible 2.3: 0 lagoon .. 1 open ocean
float n1 = Nz.N(Rel / 250.0 + T * float2(0.25, 0.1));
float n2 = Nz.N(Rel / 90.0 - T * float2(0.4, 0.3));
float ring = (1.0 - smoothstep(0.0, Radii.w, abs(d - Radii.z))) * saturate(1.4 * n1 - 0.2) * 0.55;   // Bible 2.4
float2 dir = Rel / max(d, 1.0);
float band = 1.0 - smoothstep(0.0, GF.y, abs(d - GF.x));
float4 G[3] = { G0, G1, G2 };
float gate = 0.0;
[unroll] for (int i = 0; i < 3; ++i)
{
    float dphi = abs(atan2(dir.y * G[i].x - dir.x * G[i].y, dot(dir, G[i].xy)));
    gate = max(gate, (1.0 - smoothstep(0.7 * G[i].z, G[i].z, dphi)) * band * G[i].w);
}
gate *= 0.75 + 0.25 * n2;
return float2(A, max(ring, gate));
"""


def lc(*v):
    return unreal.LinearColor(*v)


def gate_vec(az):
    r = math.radians(az)
    return lc(math.cos(r), math.sin(r), GATE_HALF, GATE_K)


def build_mpc():
    path = W + "/MPC_AOS_Atoll"
    mpc = unreal.load_asset(path) if eal.does_asset_exist(path) else at.create_asset(
        "MPC_AOS_Atoll", W, unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    want = [("AtollCenter", lc(CENTER[0], CENTER[1], WATER_Z, 0.0)), ("Radii", lc(R_CALM, R_FULL, RING_R, RING_W)),
            ("GateFoam", lc(GATE_R, GATE_W, 0.0, 0.0))]
    want += [("Gate%d" % i, gate_vec(a)) for i, a in enumerate(GATES)]
    want += [("PlayerPos", lc(0.0, 0.0, 0.0, 0.0))]
    old = {str(p.get_editor_property("parameter_name")): p for p in mpc.get_editor_property("vector_parameters")}
    params = []
    for name, val in want:
        p = old.get(name) or unreal.CollectionVectorParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", val)
        params.append(p)
    mpc.set_editor_property("vector_parameters", params)
    if not mpc.get_editor_property("scalar_parameters"):
        s = unreal.CollectionScalarParameter()
        s.set_editor_property("parameter_name", "NightFactor")
        s.set_editor_property("default_value", 0.0)
        mpc.set_editor_property("scalar_parameters", [s])
    eal.save_loaded_asset(mpc, False)
    ids = fx.get_property_as_text(mpc, "VectorParameters")
    guids = set(re.findall(r"Id=([0-9A-F]{32})", ids))
    log.append("MPC_AOS_Atoll: %d vector params, %d unique ids" % (len(params), len(guids)))
    return mpc


def fe(mf, cls, x, y, **props):
    e = mel.create_material_expression_in_function(mf, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def me(mat, cls, x, y, **props):
    e = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def con(a, a_out, b, b_in):
    if not mel.connect_material_expressions(a, a_out, b, b_in):
        raise RuntimeError("connect failed %s.%s -> %s.%s" % (a.get_name(), a_out, b.get_name(), b_in))


def build_mf(mpc):
    path = W + "/MF_AOS_AtollWaveMask"
    if eal.does_asset_exist(path):
        mf = unreal.load_asset(path)
        mel.delete_all_material_expressions_in_function(mf)
    else:
        mf = at.create_asset("MF_AOS_AtollWaveMask", W, unreal.MaterialFunction, unreal.MaterialFunctionFactoryNew())
    mf.set_editor_property("description", "Pontoon Atoll calm-lagoon mask: WaveScale (0 lagoon .. 1 ocean) and FoamAdd (BC-R ring + gate foam). Bible 2.3/2.4.")
    wp = fe(mf, E.MaterialExpressionWorldPosition, -1500, 0,
            world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    cp = lambda n, y: fe(mf, E.MaterialExpressionCollectionParameter, -1500, y, collection=mpc, parameter_name=n)
    center = cp("AtollCenter", 120)
    c3 = fe(mf, E.MaterialExpressionComponentMask, -1250, 120, r=True, g=True, b=True, a=False)
    con(center, "", c3, "")
    sub = fe(mf, E.MaterialExpressionSubtract, -1050, 40)      # LWC absolute position - centre -> float relative
    con(wp, "", sub, "A"); con(c3, "", sub, "B")
    rel = fe(mf, E.MaterialExpressionComponentMask, -880, 40, r=True, g=True, b=False, a=False)
    con(sub, "", rel, "")
    time = fe(mf, E.MaterialExpressionTime, -1050, 700)
    srcs = [("Rel", rel), ("Radii", cp("Radii", 240)), ("G0", cp("Gate0", 340)), ("G1", cp("Gate1", 440)),
            ("G2", cp("Gate2", 540)), ("GF", cp("GateFoam", 640)), ("T", time)]
    cu = fe(mf, E.MaterialExpressionCustom, -600, 200, code=MASK_CODE, description="AOS Atoll wave mask",
            output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    ins = []
    for n, _ in srcs:
        ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
    cu.set_editor_property("inputs", ins)
    for n, s in srcs:
        con(s, "", cu, n)
    for i, (name, ch) in enumerate((("WaveScale", "r"), ("FoamAdd", "g"))):
        m = fe(mf, E.MaterialExpressionComponentMask, -250, 150 + 150 * i, r=ch == "r", g=ch == "g", b=False, a=False)
        con(cu, "", m, "")
        o = fe(mf, E.MaterialExpressionFunctionOutput, 0, 150 + 150 * i, output_name=name, sort_priority=i)
        con(m, "", o, "")
    mel.update_material_function(mf)
    eal.save_loaded_asset(mf, False)
    log.append("MF_AOS_AtollWaveMask built")
    return mf


def eod_exprs(path):
    name = path.split("/")[-1]
    unreal.load_asset(path)
    o = unreal.find_object(None, "%s.%s:%sEditorOnlyData" % (path, name, name))
    return {e.get_name().replace("MaterialExpression", ""): e for e in fx.get_object_array(o, "ExpressionCollection.Expressions")}


def guid(hex32):
    g = unreal.GuidLibrary.parse_string_to_guid(hex32)
    g, ok = (g if isinstance(g, tuple) else (g, True))
    if not ok:
        raise RuntimeError("bad guid " + hex32)
    return g


def set_types(node, prop, hexes, names):
    """Get/SetMaterialAttributes: a scripted array edit asserts in 5.7.4 (pins are only added on ArrayAdd), so the
    pin array is sized through reflection first, then the attribute GUIDs are imported."""
    if prop == "attribute_set_types":
        pins = "(()," + ",".join('(InputName="%s")' % n for n in names) + ")"
        ok = fx.set_property_from_text(node, "Inputs", pins) and fx.set_property_from_text(node, "AttributeSetTypes", "(" + ",".join(hexes) + ")")
    else:
        pins = '((OutputName="MaterialAttributes"),' + ",".join('(OutputName="%s")' % n for n in names) + ")"
        ok = fx.set_property_from_text(node, "Outputs", pins) and fx.set_property_from_text(node, "AttributeGetTypes", "(" + ",".join(hexes) + ")")
    if not ok:
        raise RuntimeError("set_types failed on " + node.get_name())


def build_water_material(mf):
    path = W + "/M_Water_Ocean_AOS"
    src = "/Water/Materials/WaterSurface/Water_Material"
    bf = eod_exprs("/Water/Materials/Layers/BeachFoam")
    g = re.findall(r"[0-9A-F]{32}", fx.get_property_as_text(bf["GetMaterialAttributes_0"], "AttributeGetTypes"))
    G_ROUGH, G_OPAC = g[1], g[2]
    G_BASE = "69B8D33616ED4D499AA497292F050F7A"   # FMaterialAttributeDefinitionMap: MP_BaseColor
    fresh = not eal.does_asset_exist(path)
    if fresh and not eal.duplicate_asset(src, path):
        raise RuntimeError("duplicate failed")
    mat = unreal.load_asset(path)
    ex = eod_exprs(path)
    stock = set(eod_exprs(src).keys())
    gw = ex["MaterialFunctionCall_1"]
    assert "ComputeGerstnerWaves" in fx.get_property_as_text(gw, "MaterialFunction")
    r8, r3, river, div5, add2, mul3 = ex["Reroute_8"], ex["Reroute_3"], ex["StaticSwitchParameter_0"], ex["Divide_5"], ex["Add_2"], ex["Multiply_3"]
    if not fresh:
        # Rebuild: drop every node that is not part of the plugin graph and restore the three stock links.
        for name, e in ex.items():
            if name not in stock:
                mel.delete_material_expression(mat, e)
        con(gw, "Wave Attributes", r8, ""); con(river, "", r3, ""); con(add2, "", div5, "A")
    g2 = re.findall(r"[0-9A-F]{32}", fx.get_property_as_text(ex["SetMaterialAttributes_0"], "AttributeSetTypes"))
    G_NORMAL, G_WPO = g2[0], g2[1]

    mask = me(mat, E.MaterialExpressionMaterialFunctionCall, -1600, -420)
    mask.set_editor_property("material_function", mf)

    # --- waves: WPO * A, normal = normalize(lerp(up, N, A)) ------------------------------------
    up = me(mat, E.MaterialExpressionConstant3Vector, -1500, -300, constant=lc(0, 0, 1, 0))
    lerp = me(mat, E.MaterialExpressionLinearInterpolate, -1380, -260)
    con(up, "", lerp, "A"); con(gw, "Normal", lerp, "B"); con(mask, "WaveScale", lerp, "Alpha")
    nrm = me(mat, E.MaterialExpressionNormalize, -1380, -200)
    con(lerp, "", nrm, "VectorInput")
    wpo = me(mat, E.MaterialExpressionMultiply, -1380, -140)
    con(gw, "WPO", wpo, "A"); con(mask, "WaveScale", wpo, "B")
    setw = me(mat, E.MaterialExpressionSetMaterialAttributes, -1360, -90)
    set_types(setw, "attribute_set_types", [G_NORMAL, G_WPO], ["Normal", "World Position Offset"])
    log.append("set waves inputs: " + fx.get_property_as_text(setw, "Inputs")[:160])
    con(gw, "Wave Attributes", setw, "MaterialAttributes")
    con(nrm, "", setw, "Normal"); con(wpo, "", setw, "World Position Offset")
    con(setw, "", r8, "")

    # --- foam: opacity + roughness (plugin BeachFoam convention) + foam scattering ------------------
    getf = me(mat, E.MaterialExpressionGetMaterialAttributes, 1800, -420)
    set_types(getf, "attribute_get_types", [G_ROUGH, G_OPAC, G_BASE], ["Roughness", "Opacity", "BaseColor"])
    con(river, "", getf, "")
    rl = me(mat, E.MaterialExpressionLinearInterpolate, 2000, -420, const_b=FOAM_ROUGHNESS)
    con(getf, "Roughness", rl, "A"); con(mask, "FoamAdd", rl, "Alpha")
    oa = me(mat, E.MaterialExpressionAdd, 2000, -340)
    con(getf, "Opacity", oa, "A"); con(mask, "FoamAdd", oa, "B")
    osat = me(mat, E.MaterialExpressionSaturate, 2100, -340)
    con(oa, "", osat, "")
    white = me(mat, E.MaterialExpressionConstant3Vector, 1900, -260, constant=lc(0.82, 0.88, 0.9, 0))
    bl = me(mat, E.MaterialExpressionLinearInterpolate, 2000, -260)
    con(getf, "BaseColor", bl, "A"); con(white, "", bl, "B"); con(mask, "FoamAdd", bl, "Alpha")
    setf = me(mat, E.MaterialExpressionSetMaterialAttributes, 2200, -420)
    set_types(setf, "attribute_set_types", [G_ROUGH, G_OPAC, G_BASE], ["Roughness", "Opacity", "BaseColor"])
    # Pins wired through reflection: pin display names depend on the shading model (no reliable name match).
    ref = lambda e: "Expression=\"%s'%s'\"" % (e.get_class().get_path_name(), e.get_path_name())
    if not fx.set_property_from_text(setf, "Inputs", '((%s),(%s,InputName="Roughness"),(%s,InputName="Opacity"),(%s,InputName="BaseColor"))' % (ref(river), ref(rl), ref(osat), ref(bl))):
        raise RuntimeError("foam pins")
    con(setf, "", r3, "")
    fs = me(mat, E.MaterialExpressionMultiply, 3900, 600)
    con(mul3, "", fs, "A"); con(mask, "FoamAdd", fs, "B")
    fa = me(mat, E.MaterialExpressionAdd, 4000, 600)
    con(add2, "", fa, "A"); con(fs, "", fa, "B")
    con(fa, "", div5, "A")

    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, False)
    log.append("M_Water_Ocean_AOS built")
    return mat


def reparent_chain(mat):
    inst = W + "/MI_Water_Material_Inst_AOS"
    ocean = W + "/MI_Water_Material_Ocean_AOS"
    if not eal.does_asset_exist(inst):
        eal.duplicate_asset("/Water/Materials/WaterSurface/Water_Material_Inst", inst)
    if not eal.does_asset_exist(ocean):
        eal.duplicate_asset("/Water/Materials/WaterSurface/Water_Material_Ocean", ocean)
    mi_inst, mi_ocean, mi = unreal.load_asset(inst), unreal.load_asset(ocean), unreal.load_asset(W + "/MI_Water_Ocean_AOS")
    mel.set_material_instance_parent(mi_inst, mat)
    mel.set_material_instance_parent(mi_ocean, mi_inst)
    mel.set_material_instance_parent(mi, mi_ocean)
    for a in (mi_inst, mi_ocean, mi):
        mel.update_material_instance(a)
        eal.save_loaded_asset(a, False)
    chain, m = [], mi
    while m:
        chain.append(m.get_name())
        m = m.get_editor_property("parent") if isinstance(m, unreal.MaterialInstance) else None
    log.append("chain: " + " -> ".join(chain))


def rebuild_snow():
    import os
    p = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Tools", "aos_marine_snow_setup.py")
    src = open(p, encoding="utf-8").read().replace("result = main()", "")
    ns = {}
    exec(compile(src, p, "exec"), ns)
    ns["build_material"]()
    eal.save_asset(W + "/M_MarineSnow_AOS", False)
    log.extend(ns["log"])


def mode_gpu():
    mpc = build_mpc()
    mf = build_mf(mpc)
    mat = build_water_material(mf)
    reparent_chain(mat)
    if globals().get("SNOW", True):
        rebuild_snow()


def find_actors(cls):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return [x for x in sub.get_all_level_actors() if isinstance(x, cls)]


def mode_place():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    ocean = find_actors(unreal.WaterBodyOcean)[0]
    da = unreal.load_asset(W + "/DA_OceanWaves_AOS")
    cur = ocean.get_editor_property("water_waves")
    if not isinstance(cur, unreal.AOSAtollGerstnerWaves):
        waves = unreal.new_object(unreal.AOSAtollGerstnerWaves, outer=ocean)
        waves.set_water_waves_asset(da)
        ocean.set_water_waves(waves)
        log.append("ocean waves: %s -> AOSAtollGerstnerWaves(DA_OceanWaves_AOS)" % (cur.get_class().get_name() if cur else None))
    else:
        cur.set_water_waves_asset(da)
        log.append("ocean waves already masked")
    cls = unreal.AOSDampingPerimeter
    actors = find_actors(cls)
    actor = actors[0] if actors else sub.spawn_actor_from_class(cls, unreal.Vector(CENTER[0], CENTER[1], ocean.get_actor_location().z))
    actor.set_actor_label("AOS_DampingPerimeter")
    actor.set_folder_path("Environment/Atoll/Breakwater")
    actor.set_actor_location(unreal.Vector(CENTER[0], CENTER[1], ocean.get_actor_location().z), False, False)
    actor.set_editor_property("is_spatially_loaded", False)
    actor.set_editor_property("atoll_collection", unreal.load_asset(W + "/MPC_AOS_Atoll"))
    for prop, name in (("gate_curtain_system", "NS_AOS_TaylorCurtain_Gate"), ("ring_curtain_system", "NS_AOS_TaylorCurtain_Ring"),
                       ("ring_near_system", "NS_AOS_TaylorCurtain_RingNear")):
        if eal.does_asset_exist(FXD + "/" + name):
            actor.set_editor_property(prop, unreal.load_asset(FXD + "/" + name))
    actor.layout_curtains()
    actor.push_mask_parameters()
    actor.modify()
    log.append("perimeter: %s spatially_loaded=%s" % (actor.get_actor_label(), actor.get_editor_property("is_spatially_loaded")))


def pol(r, az, z):
    return (CENTER[0] + r * math.cos(math.radians(az)), CENTER[1] + r * math.sin(math.radians(az)), z)


VIEWS = {
    "01_top_overview": {"cam": (CENTER[0], CENTER[1] - 200.0, 42000.0), "at": (CENTER[0], CENTER[1], 0.0), "fov": 60},
    "02_gate180_inside": {"cam": pol(9600, 180, 420), "at": pol(12600, 180, 0), "fov": 60},
    "03_gate060_inside": {"cam": pol(9600, 60, 420), "at": pol(12600, 60, 0), "fov": 60},
    "04_gate300_inside": {"cam": pol(9600, 300, 420), "at": pol(12600, 300, 0), "fov": 60},
    "05_gate180_outside": {"cam": pol(15800, 172, 900), "at": pol(12120, 180, 0), "fov": 55},
    "06_gate180_top": {"cam": pol(12120, 180, 3800), "at": pol(12140, 180, 0), "fov": 70},
    "07_wall_outside_az120": {"cam": pol(17500, 120, 700), "at": pol(12500, 128, 300), "fov": 60},
    "08_lagoon_decks": {"cam": pol(2600, 200, 330), "at": pol(5200, 20, 60), "fov": 75},
    "09_ring_bcr": {"cam": pol(9800, 100, 500), "at": pol(11000, 112, 0), "fov": 65},
    "10_gate180_underwater": {"cam": pol(11300, 177, -700), "at": pol(12120, 180, -900), "fov": 75},
}


def mode_capture(shots, out_dir):
    import os
    os.makedirs(out_dir, exist_ok=True)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    tmp, out = [], []
    V = lambda t: unreal.Vector(float(t[0]), float(t[1]), float(t[2]))
    for i, (pitch, yaw, lux) in enumerate(((-38, -125, 10.0), (-18, 70, 4.0))):
        sun = sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 0), unreal.Rotator(roll=0, pitch=pitch, yaw=yaw))
        sun.set_actor_label("TMP_Atoll2B_Light%d" % i)
        c = sun.get_component_by_class(unreal.DirectionalLightComponent)
        c.set_mobility(unreal.ComponentMobility.MOVABLE); c.set_intensity(lux); c.set_cast_shadows(False)
        tmp.append(sun)
    try:
        for name, v in VIEWS.items():
            if shots and not any(name.startswith(x) for x in shots):
                continue
            rt = unreal.RenderingLibrary.create_render_target2d(w, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8)
            cam, look = V(v["cam"]), V(v["at"])
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam, unreal.MathLibrary.find_look_at_rotation(cam, look))
            cap.set_actor_label("TMP_Atoll2B_Cam"); tmp.append(cap)
            cc = cap.capture_component2d
            cc.texture_target = rt
            cc.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
            cc.set_editor_property("capture_every_frame", False); cc.set_editor_property("capture_on_movement", False)
            off = ("Fog", "VolumetricFog", "Cloud") + (() if v["cam"][2] < 0 else ("PostProcessMaterial",))
            cc.set_editor_property("show_flag_settings", [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in off])
            pp = unreal.PostProcessSettings()
            for k_, v_ in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                           ("override_auto_exposure_bias", True), ("auto_exposure_bias", float(v.get("ev", 0.0))),
                           ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", False)):
                pp.set_editor_property(k_, v_)
            cc.set_editor_property("post_process_settings", pp); cc.set_editor_property("post_process_blend_weight", 1.0)
            cc.set_editor_property("fov_angle", float(v["fov"]))
            cc.capture_scene(); cc.capture_scene()
            f = os.path.join(out_dir, name + ".png")
            if os.path.exists(f):
                os.remove(f)
            unreal.RenderingLibrary.export_render_target(w, rt, out_dir, name + ".png")
            out.append(name)
    finally:
        for t in tmp:
            sub.destroy_actor(t)
    log.append("shots: " + ", ".join(out))


# ------------------------------------------------------------------ Niagara: Taylor curtains (Bible 2.5)
TEMPLATE = "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight"
BUBBLE_MAT = "/Game/AOS_DK_Game/Submarine/Subdrones/Attacker/FX/Materials/M_FX_Bubble"
PATCH_CODE = """
float2 q = UV * 2.0 - 1.0;
float r = saturate(1.0 - dot(q, q));
float n = frac(sin(dot(floor(UV * 5.0 + Seed * 17.0), float2(127.1, 311.7))) * 43758.5453);
return r * r * (0.75 + 0.25 * n);
"""


def fx_material(name, depth_fade, emissive):
    path = FXD + "/" + name
    if eal.does_asset_exist(path):
        mat = unreal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = at.create_asset(name, FXD, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("used_with_niagara_sprites", True)
    pc = me(mat, E.MaterialExpressionParticleColor, -900, 0)
    uv = me(mat, E.MaterialExpressionTextureCoordinate, -900, 250)
    seed = me(mat, E.MaterialExpressionParticleRandom, -900, 350)
    cu = me(mat, E.MaterialExpressionCustom, -650, 250, code=PATCH_CODE, description="AOS foam patch alpha",
            output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    ins = []
    for n in ("UV", "Seed"):
        ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
    cu.set_editor_property("inputs", ins)
    con(uv, "", cu, "UV"); con(seed, "", cu, "Seed")
    al = me(mat, E.MaterialExpressionMultiply, -400, 200)
    con(pc, "A", al, "A"); con(cu, "", al, "B")
    out = al
    if depth_fade > 0:
        df = me(mat, E.MaterialExpressionDepthFade, -200, 200, fade_distance_default=depth_fade)
        con(al, "", df, "Opacity")
        out = df
    mel.connect_material_property(pc, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(out, "", unreal.MaterialProperty.MP_OPACITY)
    rough = me(mat, E.MaterialExpressionConstant, -200, 60, r=FOAM_ROUGHNESS)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    em = me(mat, E.MaterialExpressionMultiply, -400, -120, const_b=emissive)
    con(pc, "RGB", em, "A")
    mel.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, False)
    return mat


def ok(v, what):
    if not v:
        raise RuntimeError("failed: " + what)


def dist(o, path, mode, values):
    ok(fx.set_distribution(o, path, mode, [float(v) for v in values]), path)


def txt(o, path, value):
    ok(fx.set_property_from_text(o, path, value), path + "=" + value)


def mod(e, cls, enabled=True):
    for m in fx.get_object_array(e, "Modules"):
        if m and m.get_class().get_name() == "NiagaraStatelessModule_" + cls:
            fx.set_property_from_text(m, "bModuleEnabled", "True" if enabled else "False")
            return m
    raise RuntimeError("module not found " + cls)


def new_system(name, emitters):
    path = FXD + "/" + name
    if eal.does_asset_exist(path):
        s = unreal.load_asset(path)
    else:
        ok(eal.duplicate_asset(TEMPLATE, path), "duplicate " + name)
        s = unreal.load_asset(path)
        ok(fx.rename_emitter(s, "Fountain", emitters[0]), "rename")
        for n in emitters[1:]:
            ok(fx.duplicate_emitter(s, emitters[0], n), "duplicate emitter " + n)
    names = [h.split(" | ")[0] for h in fx.get_emitter_handle_info(s)]
    es = fx.get_stateless_emitters(s)
    return s, {n: es[names.index(n)] for n in emitters}


def emitter(e, mat, rate=None, burst=None, loop=(1.0,), life=(1.0, 2.0), color=(1, 1, 1, 1), size=(1.0, 2.0), box=None, ring=None,
            offset=(0, 0, 0), vel=None, gravity=False, drag=0.0, curl=None, grow=1.0, alpha=None, bounds=None):
    if burst:
        txt(e, "SpawnInfos[0].Type", "Burst"); txt(e, "SpawnInfos[0].SpawnTime", "0.0")
        dist(e, "SpawnInfos[0].Amount", "UniformConstant", [burst])
    else:
        txt(e, "SpawnInfos[0].Type", "Rate")
        dist(e, "SpawnInfos[0].Rate", "UniformConstant", [rate])
    dist(e, "EmitterState.LoopDuration", "UniformRange" if len(loop) == 2 else "UniformConstant", loop)
    i = mod(e, "InitializeParticle")
    dist(i, "LifetimeDistribution", "UniformRange", life)
    dist(i, "ColorDistribution", "NonUniformConstant", color)
    dist(i, "SpriteSizeDistribution", "UniformRange", size)
    dist(i, "SpriteRotationDistribution", "UniformRange", [0.0, 360.0])
    dist(i, "InitialPositionDistribution", "NonUniformConstant", offset)
    sh = mod(e, "ShapeLocation")
    if box:
        txt(sh, "ShapePrimitive", "Box")
        dist(sh, "BoxSize", "NonUniformConstant", box)
    else:
        txt(sh, "ShapePrimitive", "Ring")
        dist(sh, "RingRadius", "UniformConstant", [ring])
        dist(sh, "DiscCoverage", "UniformConstant", [0.0])
    v = mod(e, "AddVelocity", vel is not None)
    if vel is not None:
        txt(v, "VelocityType", "Linear")
        dist(v, "LinearVelocityDistribution", "NonUniformRange", vel)
    mod(e, "GravityForce", gravity)
    mod(e, "AccelerationForce", False)
    d = mod(e, "Drag", drag > 0)
    if drag > 0:
        dist(d, "DragDistribution", "UniformConstant", [drag])
    c = mod(e, "CurlNoiseForce", curl is not None)
    if curl:
        txt(c, "NoiseStrength", str(curl[0])); txt(c, "NoiseFrequency", str(curl[1]))
    sc = mod(e, "ScaleColor")
    dist(sc, "ScaleDistribution", "ColorGradient", alpha or [0.0, 1, 1, 1, 0.0, 0.15, 1, 1, 1, 1.0, 1.0, 1, 1, 1, 0.0])
    ss = mod(e, "ScaleSpriteSize")
    dist(ss, "ScaleDistribution", "NonUniformCurve", [0.0, 1.0, 1.0, 1.0, grow, grow])
    r = fx.get_object_array(e, "RendererProperties")[0]
    r.set_editor_property("material", mat)
    txt(e, "FixedBounds", "(Min=(X=%g,Y=%g,Z=%g),Max=(X=%g,Y=%g,Z=%g),IsValid=True)" % tuple(bounds))


def mode_fx():
    foam = fx_material("M_FX_FoamPatch_AOS", 30.0, 0.04)
    spray = fx_material("M_FX_Spray_AOS", 0.0, 0.04)
    bubble = unreal.load_asset(BUBBLE_MAT)
    fade_out = [0.0, 1, 1, 1, 0.0, 0.12, 1, 1, 1, 0.85, 1.0, 1, 1, 1, 0.0]

    # Gate: pivot on the gate line at the water level, local +X radially outward, pipes at Z -1800 (water Z 40 -> -1840 local).
    s, e = new_system("NS_AOS_TaylorCurtain_Gate", ["E_PlumeBubbles", "E_SurfaceBoil", "E_Spray"])
    gb = (-450, -1150, -1900, 450, 1150, 600)
    emitter(e["E_PlumeBubbles"], bubble, rate=520, life=(2.5, 3.8), color=(0.78, 0.93, 1.0, 0.6), size=(1.5, 6.0),
            box=(60, 1700, 1380), offset=(0, 0, -1150), vel=(-15, -15, 80, 15, 15, 110), curl=(20.0, 0.004), grow=1.8, bounds=gb)
    emitter(e["E_SurfaceBoil"], foam, rate=90, life=(3.5, 5.0), color=(0.86, 0.92, 0.94, 0.85), size=(80, 110),
            box=(150, 1700, 30), offset=(0, 0, 10), vel=(-70, -12, 0, 70, 12, 6), drag=0.3, grow=2.6, alpha=fade_out, bounds=gb)
    emitter(e["E_Spray"], spray, burst=30, loop=(1.4, 2.6), life=(0.6, 1.0), color=(0.9, 0.95, 0.97, 0.7), size=(10, 35),
            box=(120, 1500, 10), offset=(0, 0, 10), vel=(-60, -60, 250, 60, 60, 450), gravity=True, grow=1.6, alpha=fade_out, bounds=gb)
    log.append("gate: %s %s" % (fx.compile_system(s), list(fx.get_emitter_handle_info(s))))
    eal.save_loaded_asset(s, False)

    s, e = new_system("NS_AOS_TaylorCurtain_Ring", ["E_RingBoil"])
    emitter(e["E_RingBoil"], foam, rate=240, life=(3.6, 4.4), color=(0.86, 0.92, 0.94, 0.55), size=(60, 80),
            ring=RING_R, vel=(-30, -30, 0, 30, 30, 4), drag=0.3, grow=2.6, alpha=fade_out,
            bounds=(-RING_R - 400, -RING_R - 400, -150, RING_R + 400, RING_R + 400, 250))
    log.append("ring: %s %s" % (fx.compile_system(s), list(fx.get_emitter_handle_info(s))))
    eal.save_loaded_asset(s, False)

    # Near-ring underwater bubble wall: moved along the BC-R line by AAOSDampingPerimeter (pipes at Z -800).
    s, e = new_system("NS_AOS_TaylorCurtain_RingNear", ["E_RingBubblesNear"])
    emitter(e["E_RingBubblesNear"], bubble, rate=300, life=(2.4, 3.2), color=(0.78, 0.93, 1.0, 0.55), size=(1.5, 5.0),
            box=(60, 3000, 480), offset=(0, 0, -600), vel=(-12, -12, 80, 12, 12, 105), curl=(15.0, 0.004), grow=1.7,
            bounds=(-300, -1700, -900, 300, 1700, 80))
    log.append("near: %s %s" % (fx.compile_system(s), list(fx.get_emitter_handle_info(s))))
    eal.save_loaded_asset(s, False)


if MODE == "fx":
    mode_fx()
if MODE == "capture":
    mode_capture(globals().get("SHOTS"), globals().get("OUT_DIR"))
if MODE == "place":
    mode_place()
if MODE == "gpu":
    mode_gpu()
result = log
