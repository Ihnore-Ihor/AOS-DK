"""
AOS_DK - Ocean optics / underwater lighting setup for Lvl_FirstPerson (UE 5.7.4).

Constants come from the project references:
  * "UE5 Ocean Optics and Rendering"  (Jerlov II, SingleLayerWater, Fresnel, Snell window,
    Volumetric Fog, Light Function caustics, DF contact foam)
  * "Фізика хвиль океану та плавучості в UE5" (WaterBodyOcean, deep-water assumptions)

Run inside the editor (level Lvl_FirstPerson open):
  Tools -> Execute Python Script...  or  Cmd console:  py "<Project>/Tools/aos_ocean_setup.py"

Flags:
  DRY_RUN = True  -> only prints "old -> new", changes nothing.
  SAVE    = True  -> saves touched assets and the level (World Partition external actors).

Idempotent: re-running rebuilds the light-function graph and re-applies the same values.

Units: 1 UU = 1 cm. Oceanographic coefficients are in 1/m and are scaled by 1e-2 (C_UE = C_phys * 0.01).
Parameter semantics were read from the engine graphs (UE 5.7 Water plugin):
  Water_Material:  AbsorptionCoefficients = 1 / (Absorption.rgb * Absorption.a)       [1/cm]
                   ScatteringCoefficients = Scattering.rgb * Scattering.a / 1000       [1/cm]
  M_UnderWater_PostProcess_Volume:
                   T_rgb = exp(-min(SceneDepth, MaxDepth) * Absorption.rgb / Absorption.a)
                   Fog   = exp(-min(SceneDepth, MaxDepth) * Fog)
                   Out   = lerp(FogAmbient.rgb*a + FogScatter.rgb*a*Phase, SceneColor*T_rgb, Fog)
"""

import math
import unreal

DRY_RUN = False
SAVE = True

# ----------------------------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------------------------
WATER_DIR = "/Game/AOS_DK_Game/Environment/Water"
MI_WATER = WATER_DIR + "/MI_Water_Ocean_AOS"
MI_UWPP = WATER_DIR + "/MI_UnderwaterPostProcess_AOS"          # the one assigned to WaterBodyOcean
LF_MAT_NAME = "M_LF_OceanCaustics_AOS"
LF_MI_NAME = "MI_LF_OceanCaustics_AOS"
CAUSTIC_TEX = "/Water/Textures/Caustics/Caustics_Tiling_01_HDR"
CONTROLLER_CLASS = "/Script/AOS_DK.AOSOceanDepthController"

# ----------------------------------------------------------------------------------------------
# Physical constants (PDF "UE5 Ocean Optics and Rendering")
# ----------------------------------------------------------------------------------------------
N_SEAWATER = 1.333
F0 = ((N_SEAWATER - 1.0) / (N_SEAWATER + 1.0)) ** 2            # 0.0204
SPECULAR = round(F0 / 0.08, 3)                                  # 0.255
ROUGHNESS = 0.02                                                # 0.01-0.03
CRITICAL_ANGLE_DEG = math.degrees(math.asin(1.0 / N_SEAWATER))  # 48.6 deg (Snell window 97 deg)
CRITICAL_ANGLE_DOT = round(math.cos(math.radians(CRITICAL_ANGLE_DEG)), 3)  # 0.661 = dot(N, V) at TIR

# Jerlov II (temperate open ocean), UE vectors in 1/cm (table "Параметризація оптичних констант")
JII_ABS_CM = (0.00390, 0.00080, 0.00065)
JII_SCAT_CM = (0.00012, 0.00028, 0.00035)
JII_PHASE_G = 0.70
# Jerlov II diffuse attenuation Kd, 1/m (R=650, G=525, B=460 nm)
JII_KD_M = (0.390, 0.080, 0.065)
KPAR_M = 0.5 * (JII_KD_M[1] + JII_KD_M[2])                       # 0.0725 1/m -> 1 % light at ~63 m

# Caustics (PDF): period of gravity waves 200-400 cm, extinction depth 1000-1200 cm,
# brief: caustics gone by 12-15 m.
CAUSTIC_PERIOD_CM = 300.0
CAUSTIC_D_EXTINCT_CM = 1100.0
CAUSTIC_CUT_START_CM = 1200.0
CAUSTIC_CUT_END_CM = 1500.0
SURFACE_TRANSITION_CM = 50.0

# ----------------------------------------------------------------------------------------------
# Gameplay-balanced underwater post process
#   Goal: Dracula orange/pink keep >= 55 % of red inside the 20 m headlight cone,
#   then the blue-black abyss takes over (fog transmittance 67 % @20 m, 37 % @50 m, 13 % @100 m).
#   Red:  -ln(0.55)/20 m = 0.030 1/m ;  G,B: Jerlov II Kd * 0.115 (keeps the physical G:B ratio).
#   With Absorption.a = 100 the RGB values read directly in 1/m.
# ----------------------------------------------------------------------------------------------
PP_ABS_M = (0.030, round(JII_KD_M[1] * 0.115, 4), round(JII_KD_M[2] * 0.115, 4))  # (0.030, 0.0092, 0.0075)
PP_FOG_CM = 0.0002
PP_FOG_AMBIENT = (0.01, 0.08, 0.18, 0.35)         # PDF fog colour; a=0.35 tuned by capture tests (a=1 washes markers)
PP_FOG_SCATTER = (0.05, 0.35, 0.65, 0.6)          # sun-phase in-scatter, 490-500 nm window
PP_SCATTER_ANISO = JII_PHASE_G
PP_WHITE_TEMP = 5000.0                             # PDF: 4500-5000 K (upper bound keeps markers warm)
PP_EV100_MIN, PP_EV100_MAX = 0.0, 6.0             # exposure clamp -> abyss stays black

# Exponential Height Fog (underwater medium); PDF: density 0.03-0.08, g 0.65-0.82, extinction 1.2-2.2
FOG_DENSITY = 0.05
FOG_HEIGHT_FALLOFF = 0.001                         # ~uniform over 1.6 km (0.2 gave e^32 at -1600 m)
FOG_INSCATTER = (0.01, 0.08, 0.18)
FOG_MAX_OPACITY = 1.0
VFOG_DISTRIBUTION = 0.75
VFOG_EXTINCTION = 2.0
VFOG_DISTANCE = 6000.0
# Single-scattering albedo b/(a+b) of Jerlov II normalised: (0.086, 0.74, 1.0) linear -> sRGB
VFOG_ALBEDO_SRGB = (82, 223, 255)

# Directional light
SUN_VOL_SCATTER = 5.0                              # PDF 4.0-7.0
SUN_LF_FADE_DISTANCE = 160000.0                    # covers the 1x1 km map diagonal and 1.6 km depth
SKY_VOL_SCATTER = 1.0

# Surface foam / DF contact foam around the tower
FOAM_ROUGHNESS = 0.80                              # PDF 0.7-0.85
FOAM_DF_WIDTH_CM = 200.0                           # saturate(1 - d / Width)

# ----------------------------------------------------------------------------------------------
mel = unreal.MaterialEditingLibrary
eas = unreal.EditorAssetLibrary
log_lines = []
touched_assets = set()


def log(msg):
    log_lines.append(msg)
    unreal.log("[AOS_Ocean] " + msg)


def lc(t):
    return unreal.LinearColor(t[0], t[1], t[2], t[3] if len(t) > 3 else 1.0)


def fmt(v):
    if isinstance(v, unreal.LinearColor):
        return "(%.5g, %.5g, %.5g, %.5g)" % (v.r, v.g, v.b, v.a)
    if isinstance(v, float):
        return "%.5g" % v
    return str(v)


# ---------------------------------------------------------------- material instance helpers
def mi_scalar(mi, name, value):
    old = mel.get_material_instance_scalar_parameter_value(mi, name)
    log("%s.%s : %s -> %s" % (mi.get_name(), name, fmt(old), fmt(value)))
    if not DRY_RUN:
        mel.set_material_instance_scalar_parameter_value(mi, name, value)
        touched_assets.add(mi.get_path_name())


def mi_vector(mi, name, value):
    old = mel.get_material_instance_vector_parameter_value(mi, name)
    log("%s.%s : %s -> %s" % (mi.get_name(), name, fmt(old), fmt(lc(value))))
    if not DRY_RUN:
        mel.set_material_instance_vector_parameter_value(mi, name, lc(value))
        touched_assets.add(mi.get_path_name())


def mi_switch(mi, name, value):
    old = mel.get_material_instance_static_switch_parameter_value(mi, name)
    log("%s.%s (static) : %s -> %s" % (mi.get_name(), name, old, value))
    if not DRY_RUN:
        mel.set_material_instance_static_switch_parameter_value(mi, name, value)
        touched_assets.add(mi.get_path_name())


def prop(obj, name, value, label=None):
    try:
        old = obj.get_editor_property(name)
    except Exception:
        old = "?"
    log("%s.%s : %s -> %s" % (label or obj.get_name(), name, fmt(old), fmt(value)))
    if not DRY_RUN:
        obj.set_editor_property(name, value)


# ================================================================== 1. Water surface (SLW)
def setup_water_material():
    mi = unreal.load_asset(MI_WATER)
    # Jerlov II, UE units 1/cm -> Absorption param stores the absorption length (1/coeff), a = 1
    mi_vector(mi, "Absorption", (1.0 / JII_ABS_CM[0], 1.0 / JII_ABS_CM[1], 1.0 / JII_ABS_CM[2], 1.0))
    mi_vector(mi, "Scattering", (JII_SCAT_CM[0] * 1000.0, JII_SCAT_CM[1] * 1000.0, JII_SCAT_CM[2] * 1000.0, 1.0))
    mi_scalar(mi, "Anisotropy", JII_PHASE_G)                      # PhaseG
    # PBR / Fresnel (F0 = 0.0204 -> Specular 0.255)
    mi_scalar(mi, "Water Specular", SPECULAR)
    mi_scalar(mi, "Water Fresnel Specular", SPECULAR)
    mi_scalar(mi, "Water Roughness", ROUGHNESS)
    mi_scalar(mi, "Water Fresnel Roughness", ROUGHNESS)
    mi_scalar(mi, "Refraction", N_SEAWATER)
    # Snell window from below: TIR when dot(N, V) < cos(48.6 deg)
    mi_scalar(mi, "Critical Angle Dot", CRITICAL_ANGLE_DOT)
    mi_scalar(mi, "Critical Angle Width", 0.03)
    # Foam (whitecaps + DF contact foam at the tower walls, BeachFoam: 1 - saturate(DF / Foam Distance))
    mi_scalar(mi, "Foam Roughness", FOAM_ROUGHNESS)
    mi_scalar(mi, "Foam Distance", FOAM_DF_WIDTH_CM)
    mi_scalar(mi, "Depth for DF Foam", 64.0)
    # Colour Scale Behind Water caustics for the view from the deck (PDF method #4)
    mi_switch(mi, "Caustics", True)
    if not DRY_RUN:
        mel.update_material_instance(mi)


# ================================================================== 2. Light Function caustics
def _expr(mat, cls, x, y, **props):
    e = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def _scalar(mat, name, value, x, y, group="AOS Caustics"):
    return _expr(mat, unreal.MaterialExpressionScalarParameter, x, y,
                 parameter_name=name, default_value=value, group=group)


def _c(a, b, b_in="", a_out=""):
    mel.connect_material_expressions(a, a_out, b, b_in)


def build_light_function(water_z):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    path = WATER_DIR + "/" + LF_MAT_NAME
    if eas.does_asset_exist(path):
        mat = unreal.load_asset(path)
        if not DRY_RUN:
            mel.delete_all_material_expressions(mat)
    else:
        if DRY_RUN:
            log("create " + path)
            return None
        mat = tools.create_asset(LF_MAT_NAME, WATER_DIR, unreal.Material, unreal.MaterialFactoryNew())
    log("build graph " + path)
    if DRY_RUN:
        return mat
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)

    E = unreal
    # --- parameters
    p_wz = _scalar(mat, "WaterZ", water_z, -2600, -200, "AOS Depth")
    p_kpar = _scalar(mat, "Kd_PAR_per_cm", KPAR_M * 0.01, -2600, -100, "AOS Depth")
    p_tw = _scalar(mat, "SurfaceTransitionWidth", SURFACE_TRANSITION_CM, -2600, 0, "AOS Depth")
    p_per = _scalar(mat, "CausticPeriod", CAUSTIC_PERIOD_CM, -2600, 200)
    p_disp = _scalar(mat, "ChromaticShift", 0.004, -2600, 300)
    p_dext = _scalar(mat, "CausticExtinctionDepth", CAUSTIC_D_EXTINCT_CM, -2600, 400)
    p_c0 = _scalar(mat, "CausticCutStart", CAUSTIC_CUT_START_CM, -2600, 500)
    p_c1 = _scalar(mat, "CausticCutEnd", CAUSTIC_CUT_END_CM, -2600, 600)
    p_str = _scalar(mat, "CausticStrength", 1.0, -2600, 700)
    p_min = _scalar(mat, "CausticFloor", 0.25, -2600, 800)
    p_gain = _scalar(mat, "CausticGain", 1.0, -2600, 900)

    # --- depth below the waterline, cm
    wp = _expr(mat, E.MaterialExpressionWorldPosition, -2300, -300)
    wz = _expr(mat, E.MaterialExpressionComponentMask, -2100, -300, r=False, g=False, b=True, a=False)
    _c(wp, wz)
    sub = _expr(mat, E.MaterialExpressionSubtract, -1900, -250)
    _c(p_wz, sub, "A"); _c(wz, sub, "B")
    depth = _expr(mat, E.MaterialExpressionMax, -1700, -250, const_b=0.0)
    _c(sub, depth, "A")

    # surface mask: saturate((z_water - z) / TransitionWidth)
    mdiv = _expr(mat, E.MaterialExpressionDivide, -1500, -400)
    _c(depth, mdiv, "A"); _c(p_tw, mdiv, "B")
    mask = _expr(mat, E.MaterialExpressionSaturate, -1300, -400)
    _c(mdiv, mask)

    # sunlight transmittance exp(-Kd_PAR * depth) (Beer-Lambert-Bouguer)
    kd = _expr(mat, E.MaterialExpressionMultiply, -1500, -200)
    _c(depth, kd, "A"); _c(p_kpar, kd, "B")
    kdn = _expr(mat, E.MaterialExpressionMultiply, -1300, -200, const_b=-1.0)
    _c(kd, kdn, "A")
    sun = _expr(mat, E.MaterialExpressionExponential, -1100, -200)
    _c(kdn, sun)

    # caustic fade exp(-depth / d_extinct) * (1 - smoothstep(cut0, cut1, depth)) * strength
    fd = _expr(mat, E.MaterialExpressionDivide, -1500, 0)
    _c(depth, fd, "A"); _c(p_dext, fd, "B")
    fdn = _expr(mat, E.MaterialExpressionMultiply, -1300, 0, const_b=-1.0)
    _c(fd, fdn, "A")
    fexp = _expr(mat, E.MaterialExpressionExponential, -1100, 0)
    _c(fdn, fexp)
    ss = _expr(mat, E.MaterialExpressionSmoothStep, -1500, 150)
    _c(p_c0, ss, "Min"); _c(p_c1, ss, "Max"); _c(depth, ss, "Value")
    ssi = _expr(mat, E.MaterialExpressionOneMinus, -1300, 150)
    _c(ss, ssi)
    f1 = _expr(mat, E.MaterialExpressionMultiply, -900, 50)
    _c(fexp, f1, "A"); _c(ssi, f1, "B")
    fade = _expr(mat, E.MaterialExpressionMultiply, -700, 50)
    _c(f1, fade, "A"); _c(p_str, fade, "B")

    # --- caustic pattern: two counter-moving pans of the plugin caustic texture
    xy = _expr(mat, E.MaterialExpressionComponentMask, -2100, 300, r=True, g=True, b=False, a=False)
    _c(wp, xy)
    uv = _expr(mat, E.MaterialExpressionDivide, -1900, 300)
    _c(xy, uv, "A"); _c(p_per, uv, "B")
    pan_a = _expr(mat, E.MaterialExpressionPanner, -1700, 300, speed_x=0.021, speed_y=0.013)
    _c(uv, pan_a, "Coordinate")
    uv_b = _expr(mat, E.MaterialExpressionMultiply, -1900, 500, const_b=0.73)
    _c(uv, uv_b, "A")
    pan_b = _expr(mat, E.MaterialExpressionPanner, -1700, 500, speed_x=-0.017, speed_y=-0.024)
    _c(uv_b, pan_b, "Coordinate")

    tex = unreal.load_asset(CAUSTIC_TEX)

    def sample(coord_expr, x, y):
        s = _expr(mat, E.MaterialExpressionTextureSample, x, y, texture=tex,
                  sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        _c(coord_expr, s, "UVs")
        return s

    # chromatic dispersion: R shifted forward, G centred, B shifted back -> MakeFloat3
    uv_r = _expr(mat, E.MaterialExpressionAdd, -1500, 250)
    _c(pan_a, uv_r, "A"); _c(p_disp, uv_r, "B")
    uv_bl = _expr(mat, E.MaterialExpressionSubtract, -1500, 350)
    _c(pan_a, uv_bl, "A"); _c(p_disp, uv_bl, "B")
    s_r = sample(uv_r, -1300, 220)
    s_g = sample(pan_a, -1300, 380)
    s_b = sample(uv_bl, -1300, 540)
    s_2 = sample(pan_b, -1300, 700)
    rg = _expr(mat, E.MaterialExpressionAppendVector, -1050, 300)
    _c(s_r, rg, "A", "R"); _c(s_g, rg, "B", "G")
    rgb = _expr(mat, E.MaterialExpressionAppendVector, -900, 350)
    _c(rg, rgb, "A"); _c(s_b, rgb, "B", "B")
    cmin = _expr(mat, E.MaterialExpressionMin, -750, 450)
    _c(rgb, cmin, "A"); _c(s_2, cmin, "B", "G")
    cg = _expr(mat, E.MaterialExpressionMultiply, -600, 450)
    _c(cmin, cg, "A"); _c(p_gain, cg, "B")
    cs = _expr(mat, E.MaterialExpressionSaturate, -450, 450)
    _c(cg, cs)
    cfl = _expr(mat, E.MaterialExpressionLinearInterpolate, -300, 450, const_b=1.0)
    _c(p_min, cfl, "A"); _c(cs, cfl, "Alpha")

    # under = sun * lerp(1, caustic, fade) ; out = lerp(1, under, mask)
    mod = _expr(mat, E.MaterialExpressionLinearInterpolate, -100, 200, const_a=1.0)
    _c(cfl, mod, "B"); _c(fade, mod, "Alpha")
    under = _expr(mat, E.MaterialExpressionMultiply, 100, 0)
    _c(sun, under, "A"); _c(mod, under, "B")
    out = _expr(mat, E.MaterialExpressionLinearInterpolate, 300, -200, const_a=1.0)
    _c(under, out, "B"); _c(mask, out, "Alpha")
    mel.connect_material_property(out, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.layout_material_expressions(mat)
    mel.recompile_material(mat)
    touched_assets.add(mat.get_path_name())

    # instance used by the light (tweak live without recompiling)
    mi_path = WATER_DIR + "/" + LF_MI_NAME
    if eas.does_asset_exist(mi_path):
        mi = unreal.load_asset(mi_path)
    else:
        mi = tools.create_asset(LF_MI_NAME, WATER_DIR, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, mat)
    mel.set_material_instance_scalar_parameter_value(mi, "WaterZ", water_z)
    mel.update_material_instance(mi)
    touched_assets.add(mi.get_path_name())
    stats = mel.get_statistics(mat)
    log("LF compiled: %d pixel instructions, %d samplers" %
        (stats.num_pixel_shader_instructions, stats.num_samplers))
    return mi


# ================================================================== 3. Underwater post process
def setup_underwater_pp():
    mi = unreal.load_asset(MI_UWPP)
    mi_vector(mi, "Absorption", (PP_ABS_M[0], PP_ABS_M[1], PP_ABS_M[2], 100.0))
    mi_scalar(mi, "Fog", PP_FOG_CM)
    mi_vector(mi, "Fog Ambient Color", PP_FOG_AMBIENT)
    mi_vector(mi, "Fog Scatter Color", PP_FOG_SCATTER)
    mi_scalar(mi, "Scattering Aniso", PP_SCATTER_ANISO)
    mi_scalar(mi, "Max Depth", 250000.0)
    if not DRY_RUN:
        mel.update_material_instance(mi)


# ================================================================== 4. Level actors
def find_actor(cls):
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if isinstance(a, cls):
            return a
    return None


def setup_actors(lf_mi):
    wb = find_actor(unreal.WaterBodyOcean)
    dl = find_actor(unreal.DirectionalLight)
    sl = find_actor(unreal.SkyLight)
    fog = find_actor(unreal.ExponentialHeightFog)

    # --- Directional light (sun): LF caustics + depth extinction, volumetric shafts
    dlc = dl.get_component_by_class(unreal.DirectionalLightComponent)
    if lf_mi is not None:
        log("DirectionalLight.light_function_material -> " + lf_mi.get_name())
        if not DRY_RUN:
            dlc.set_light_function_material(lf_mi)
    prop(dlc, "light_function_fade_distance", SUN_LF_FADE_DISTANCE, "DirectionalLight")
    prop(dlc, "disabled_brightness", 1.0, "DirectionalLight")
    prop(dlc, "volumetric_scattering_intensity", SUN_VOL_SCATTER, "DirectionalLight")
    prop(dlc, "cast_volumetric_shadow", True, "DirectionalLight")
    prop(dlc, "enable_light_shaft_occlusion", True, "DirectionalLight")
    prop(dlc, "enable_light_shaft_bloom", True, "DirectionalLight")

    slc = sl.get_component_by_class(unreal.SkyLightComponent)
    prop(slc, "volumetric_scattering_intensity", SKY_VOL_SCATTER, "SkyLight")

    # --- Exponential Height Fog = underwater medium (the controller swaps an air preset above water)
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    if wb and abs(fog.get_actor_location().z - wb.get_actor_location().z) > 1.0:
        loc = fog.get_actor_location(); loc.z = wb.get_actor_location().z
        log("ExponentialHeightFog.Z -> %.1f (waterline)" % loc.z)
        if not DRY_RUN:
            fog.set_actor_location(loc, False, False)
    prop(fc, "fog_density", FOG_DENSITY, "EHF")
    prop(fc, "fog_height_falloff", FOG_HEIGHT_FALLOFF, "EHF")
    prop(fc, "fog_inscattering_luminance", lc(FOG_INSCATTER), "EHF")
    prop(fc, "directional_inscattering_luminance", unreal.LinearColor(0, 0, 0, 1), "EHF")
    prop(fc, "fog_max_opacity", FOG_MAX_OPACITY, "EHF")
    prop(fc, "start_distance", 0.0, "EHF")
    prop(fc, "enable_volumetric_fog", True, "EHF")
    prop(fc, "volumetric_fog_scattering_distribution", VFOG_DISTRIBUTION, "EHF")
    prop(fc, "volumetric_fog_extinction_scale", VFOG_EXTINCTION, "EHF")
    prop(fc, "volumetric_fog_albedo", unreal.Color(r=VFOG_ALBEDO_SRGB[0], g=VFOG_ALBEDO_SRGB[1],
                                                   b=VFOG_ALBEDO_SRGB[2], a=255), "EHF")
    prop(fc, "volumetric_fog_emissive", unreal.LinearColor(0, 0, 0, 1), "EHF")
    prop(fc, "volumetric_fog_distance", VFOG_DISTANCE, "EHF")

    # --- WaterBodyOcean: underwater PP volume settings (white balance, exposure clamp)
    wbc = wb.get_component_by_class(unreal.WaterBodyComponent)
    ups = wbc.get_editor_property("underwater_post_process_settings")
    pps = ups.get_editor_property("post_process_settings")
    for name, value in [("override_white_temp", True), ("white_temp", PP_WHITE_TEMP),
                        ("override_auto_exposure_method", True),
                        ("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
                        ("override_auto_exposure_min_brightness", True),
                        ("auto_exposure_min_brightness", PP_EV100_MIN),
                        ("override_auto_exposure_max_brightness", True),
                        ("auto_exposure_max_brightness", PP_EV100_MAX)]:
        prop(pps, name, value, "WaterBody.UnderwaterPP")
    ups.set_editor_property("post_process_settings", pps)
    ups.set_editor_property("priority", 10.0)
    if not DRY_RUN:
        wbc.set_editor_property("underwater_post_process_settings", ups)
        wbc.set_editor_property("underwater_post_process_material", unreal.load_asset(MI_UWPP))

    # --- runtime stratification controller (C++), if compiled
    cls = unreal.load_class(None, CONTROLLER_CLASS)
    if cls is None:
        log("AOSOceanDepthController class not found - build the C++ module, then re-run the script.")
    else:
        existing = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                    if a.get_class() == cls]
        if existing:
            ctrl = existing[0]
            log("controller already in level: " + ctrl.get_actor_label())
        elif DRY_RUN:
            log("spawn AOSOceanDepthController")
            ctrl = None
        else:
            ctrl = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
                cls, unreal.Vector(0, 0, wb.get_actor_location().z + 500.0))
            ctrl.set_actor_label("AOS_OceanDepthController")
            log("spawned AOS_OceanDepthController")
        if ctrl is not None and not DRY_RUN:
            ctrl.set_editor_property("water_body", wb)
            ctrl.set_editor_property("sun", dl)
            ctrl.set_editor_property("sky_light", sl)
            ctrl.set_editor_property("height_fog", fog)
            ctrl.set_editor_property("pp_fog_ambient_intensity", PP_FOG_AMBIENT[3])
            ctrl.set_editor_property("pp_fog_scatter_intensity", PP_FOG_SCATTER[3])
            ctrl.set_editor_property("kd_par_per_meter", KPAR_M)
            ctrl.set_editor_property("sun_volumetric_scattering_underwater", SUN_VOL_SCATTER)


# ================================================================== main
def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    log("world: " + world.get_path_name() + ("  [DRY RUN]" if DRY_RUN else ""))
    wb = find_actor(unreal.WaterBodyOcean)
    water_z = wb.get_actor_location().z if wb else 0.0
    log("waterline Z = %.1f cm, F0 = %.4f, Specular = %.3f, critical angle = %.1f deg (dot %.3f)" %
        (water_z, F0, SPECULAR, CRITICAL_ANGLE_DEG, CRITICAL_ANGLE_DOT))

    with unreal.ScopedEditorTransaction("AOS ocean optics setup"):
        setup_water_material()
        lf_mi = build_light_function(water_z)
        setup_underwater_pp()
        setup_actors(lf_mi)

    if SAVE and not DRY_RUN:
        for p in sorted(touched_assets):
            eas.save_asset(p.split(".")[0], only_if_is_dirty=False)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("saved %d assets + dirty map/actor packages" % len(touched_assets))
    return log_lines


result = main()
