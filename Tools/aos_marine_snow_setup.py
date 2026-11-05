"""
AOS_DK - Marine snow (organic detritus) for Lvl_FirstPerson (UE 5.7.4).

Builds M_MarineSnow_AOS and places one AOS_MarineSnowField actor (C++ AAOSMarineSnowField).
Idempotent: re-running rebuilds the material graph and updates the existing actor.

Optics ("UE5 Ocean Optics and Rendering"):
  * scattering by suspended particles is strongly forward-peaked -> two-term Henyey-Greenstein,
    g1 = 0.92 (particles), g2 = -0.35 (molecular back-scatter), alpha = 0.98;
  * sun light below the surface follows Beer-Lambert with Kd_PAR(Jerlov II) = 0.0725 1/m;
  * headlight cones are evaluated analytically (no lit translucency, no shadows, no Lumen).

Run in the editor:  py "<Project>/Tools/aos_marine_snow_setup.py"
"""
import unreal

SAVE = True
WATER_DIR = "/Game/AOS_DK_Game/Environment/Water"
MAT_NAME = "M_MarineSnow_AOS"
ACTOR_CLASS = "/Script/AOS_DK.AOSMarineSnowField"
ACTOR_LABEL = "AOS_MarineSnowField"

KPAR_CM = 0.0725 * 0.01
PHASE_TTHG = (0.92, -0.35, 0.98)

mel = unreal.MaterialEditingLibrary
eas = unreal.EditorAssetLibrary
E = unreal
log = []

# ------------------------------------------------------------------ HLSL
VS_CODE = r"""
// Wrap the world-fixed seed into a Box centred on the camera (infinite field, true parallax).
float3 c = Cam + (frac((P0 + Drift * T - Cam) / Box) - 0.5) * Box;
float ph = Seed.g * 6.2831853;
c += float3(sin(T * 0.37 + ph), cos(T * 0.29 + ph * 1.7), sin(T * 0.23 + ph * 2.3)) * (3.0 * Seed.a);

// Flakes are passive tracers of the swell: Gerstner orbital displacement decaying as e^(k z)
// (same 16 waves and clock as the water mesh / Shell buoyancy). Local surface = WaveP.x + sum(A cos).
float4 GA[16] = { GW0A, GW1A, GW2A, GW3A, GW4A, GW5A, GW6A, GW7A, GW8A, GW9A, GW10A, GW11A, GW12A, GW13A, GW14A, GW15A };
float4 GB[16] = { GW0B, GW1B, GW2B, GW3B, GW4B, GW5B, GW6B, GW7B, GW8B, GW9B, GW10B, GW11B, GW12B, GW13B, GW14B, GW15B };
float d0 = max(WaveP.x - c.z, 0.0);
float3 orb = 0;
float elev = 0;
[unroll] for (int w = 0; w < 16; ++w)
{
    float th = dot(c.xy, GA[w].xy) - GA[w].z * WaveT;
    float sn, cs;
    sincos(th, sn, cs);
    float dec = exp(-GB[w].w * d0);
    orb.xy += -GB[w].z * sn * GB[w].xy * dec;
    orb.z += GA[w].w * cs * dec;
    elev += GA[w].w * cs;
}
c += orb;
float below = (WaveP.x + elev) - c.z;                   // depth under the local wave surface, cm
float keep = step(WaveP.y, below);                      // never in air / in the crest
float dens = lerp(WaveP.z, 1.0, saturate(below / WaveP.w));
keep *= step(frac(Seed.a * 7.31 + Seed.g * 3.17), dens); // thinner wave-mixed surface layer

float3 toC = c - Cam;
float dist = length(toC);
float3 camR = normalize(mul(float3(1, 0, 0), (float3x3)ResolvedView.ViewToTranslatedWorld));
float3 camU = normalize(mul(float3(0, 1, 0), (float3x3)ResolvedView.ViewToTranslatedWorld));
float3 camF = normalize(cross(camR, camU));

// Motion streak: stretch along the particle velocity relative to the camera, perpendicular to the
// ray towards that particle (= its true screen motion, radial when the Shell moves forward).
float3 dirP = toC / max(dist, 1e-3);
float3 v = -CamVel;
float3 vp = v - dot(v, dirP) * dirP;
float sp = length(vp);
float3 A = sp > 1.0 ? vp / sp : camR;
float3 B = normalize(cross(dirP, A));

float size = lerp(SizeP.x, SizeP.y, Seed.r);
size = max(size, dist * SizeP.z);                       // >= ~1 px, no sub-pixel shimmer
float fade = smoothstep(FadeP.x * 0.5, FadeP.x, dist) * (1.0 - smoothstep(FadeP.y, Box * 0.5, dist));
size *= step(0.01, fade) * keep;                        // collapse invisible quads -> no pixel cost
float len = size + min(sp * SizeP.w, 40.0);

float2 q = UV * 2.0 - 1.0;
return c + A * (q.x * len) + B * (q.y * size) - Base;
"""

PS_CODE = r"""
float2 q = UV * 2.0 - 1.0;
float disc = saturate(1.0 - dot(q, q));
float3 toCam = Cam - W;
float dist = length(toCam);
float3 V = toCam / max(dist, 1e-3);
float fade = smoothstep(FadeP.x * 0.5, FadeP.x, dist) * (1.0 - smoothstep(FadeP.y, Box * 0.5, dist));

float g1 = Phase.x, g2 = Phase.y, a = Phase.z;
float3 L = 0;
[unroll] for (int i = 0; i < 2; ++i)
{
    float4 P = (i == 0) ? HL0P : HL1P;
    float4 D = (i == 0) ? HL0D : HL1D;
    float3 C = (i == 0) ? HL0C : HL1C;
    float3 d = W - P.xyz;
    float dl = max(length(d), 1.0);
    float3 ld = d / dl;
    float cone = smoothstep(D.w, max(P.w, D.w + 1e-3), dot(ld, D.xyz));
    float r = saturate(1.0 - pow(dl / Range, 4.0));
    float att = r * r / (1.0 + dl * dl * 1e-4);          // inverse square in metres
    float ct = dot(ld, V);                               // propagation vs. direction to the eye
    float h1 = (1.0 - g1 * g1) / (12.566371 * pow(1.0 + g1 * g1 - 2.0 * g1 * ct, 1.5));
    float h2 = (1.0 - g2 * g2) / (12.566371 * pow(1.0 + g2 * g2 - 2.0 * g2 * ct, 1.5));
    L += C * cone * att * min(a * h1 + (1.0 - a) * h2, 4.0);
}
float depth = max(WaterZ - W.z, 0.0);
float sunT = exp(-Kd * depth);                           // Beer-Lambert, Jerlov II PAR
float cs = dot(SunDir, V);
float s1 = (1.0 - g1 * g1) / (12.566371 * pow(1.0 + g1 * g1 - 2.0 * g1 * cs, 1.5));
float s2 = (1.0 - g2 * g2) / (12.566371 * pow(1.0 + g2 * g2 - 2.0 * g2 * cs, 1.5));
L += SunC * sunT * min(a * s1 + (1.0 - a) * s2, 4.0) + Amb * sunT;

float3 e = L * Gain * (0.5 + Seed.b) * fade;
return float4(e, disc * step(0.01, fade));
"""


def expr(mat, cls, x, y, **props):
    e = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def c(a, b, b_in="", a_out=""):
    ok = mel.connect_material_expressions(a, a_out, b, b_in)
    if not ok:
        raise RuntimeError("connect failed: %s.%s -> %s.%s" % (a.get_name(), a_out, b.get_name(), b_in))


def build_material():
    path = WATER_DIR + "/" + MAT_NAME
    if eas.does_asset_exist(path):
        mat = unreal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MAT_NAME, WATER_DIR, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("opacity_mask_clip_value", 0.2)

    y = [-1200]

    def sp(name, value):
        y[0] += 90
        return expr(mat, E.MaterialExpressionScalarParameter, -1800, y[0],
                    parameter_name=name, default_value=value, group="Marine Snow")

    def vp4(name, value):
        """Vector parameter as float4 (RGB + A)."""
        y[0] += 110
        p = expr(mat, E.MaterialExpressionVectorParameter, -1800, y[0], parameter_name=name,
                 default_value=unreal.LinearColor(*value), group="Marine Snow")
        ap = expr(mat, E.MaterialExpressionAppendVector, -1550, y[0])
        c(p, ap, "A", ""); c(p, ap, "B", "A")
        return ap

    def vp3(name, value):
        y[0] += 90
        return expr(mat, E.MaterialExpressionVectorParameter, -1800, y[0], parameter_name=name,
                    default_value=unreal.LinearColor(*value), group="Marine Snow")

    box = sp("BoxSize", 4000.0)
    water_z = sp("WaterZ", 40.0)
    kd = sp("Kd", KPAR_CM)
    gain = sp("Gain", 1500.0)
    rng = sp("LightRange", 5200.0)
    wave_t = sp("WaveTime", 0.0)
    wave_p = vp4("WaveP", (40.0, 20.0, 0.25, 2500.0))   # base Z, clearance, surface density, full-density depth
    gwa = [vp4("GW%dA" % i, (0.0, 0.0, 0.0, 0.0)) for i in range(16)]   # waveVector.xy, omega, amplitude
    gwb = [vp4("GW%dB" % i, (1.0, 0.0, 0.0, 0.0)) for i in range(16)]   # dir.xy, Q, k
    drift = vp3("Drift", (3.0, 1.5, -0.6, 0.0))
    cam_vel = vp3("CamVel", (0.0, 0.0, 0.0, 0.0))
    size_p = vp4("SizeP", (0.5, 2.4, 0.0012, 0.02))     # min r, max r (cm), px-clamp, streak time (s)
    fade_p = vp3("FadeP", (40.0, 1400.0, 0.0, 0.0))      # near fade (cm), far fade start (cm)
    phase = vp3("Phase", (PHASE_TTHG[0], PHASE_TTHG[1], PHASE_TTHG[2], 0.0))
    amb = vp3("Amb", (0.00002, 0.00008, 0.00012, 0.0))
    hl0p = vp4("HL0Pos", (0.0, 0.0, 0.0, 0.974))
    hl0d = vp4("HL0Dir", (1.0, 0.0, 0.0, 0.891))
    hl0c = vp3("HL0Color", (0.0, 0.0, 0.0, 0.0))
    hl1p = vp4("HL1Pos", (0.0, 0.0, 0.0, 0.974))
    hl1d = vp4("HL1Dir", (1.0, 0.0, 0.0, 0.891))
    hl1c = vp3("HL1Color", (0.0, 0.0, 0.0, 0.0))
    sun_d = vp3("SunDir", (0.0, 0.0, -1.0, 0.0))
    sun_c = vp3("SunColor", (0.0, 0.0, 0.0, 0.0))

    # shared nodes
    cam = expr(mat, E.MaterialExpressionCameraPositionWS, -1300, -600)
    uv = expr(mat, E.MaterialExpressionTextureCoordinate, -1300, -500)
    vc = expr(mat, E.MaterialExpressionVertexColor, -1500, -400)
    vc_rgb = expr(mat, E.MaterialExpressionComponentMask, -1350, -420, r=True, g=True, b=True, a=False)
    c(vc, vc_rgb)
    seed = expr(mat, E.MaterialExpressionAppendVector, -1200, -400)
    c(vc_rgb, seed, "A"); c(vc, seed, "B", "A")
    time = expr(mat, E.MaterialExpressionTime, -1300, -300)
    p0 = expr(mat, E.MaterialExpressionPreSkinnedPosition, -1300, -200)
    base = expr(mat, E.MaterialExpressionWorldPosition, -1300, -100,
                world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    wpos = expr(mat, E.MaterialExpressionWorldPosition, -1300, 0)

    def custom(code, out_type, names, x, y_):
        e = expr(mat, E.MaterialExpressionCustom, x, y_, code=code, output_type=out_type,
                 description="AOS marine snow")
        ins = []
        for n in names:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", n)
            ins.append(ci)
        e.set_editor_property("inputs", ins)
        return e

    vs_inputs = [("P0", p0), ("UV", uv), ("Seed", seed), ("Cam", cam), ("Base", base), ("T", time),
                 ("Box", box), ("Drift", drift), ("CamVel", cam_vel), ("SizeP", size_p), ("FadeP", fade_p),
                 ("WaveT", wave_t), ("WaveP", wave_p)]
    vs_inputs += [("GW%dA" % i, gwa[i]) for i in range(16)] + [("GW%dB" % i, gwb[i]) for i in range(16)]
    vs = custom(VS_CODE, unreal.CustomMaterialOutputType.CMOT_FLOAT3, [n for n, _ in vs_inputs], -700, -400)
    for n, src in vs_inputs:
        c(src, vs, n)
    mel.connect_material_property(vs, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)

    ps_inputs = [("W", wpos), ("Cam", cam), ("UV", uv), ("Seed", seed),
                 ("HL0P", hl0p), ("HL0D", hl0d), ("HL0C", hl0c), ("HL1P", hl1p), ("HL1D", hl1d), ("HL1C", hl1c),
                 ("Range", rng), ("SunDir", sun_d), ("SunC", sun_c), ("WaterZ", water_z), ("Kd", kd),
                 ("Gain", gain), ("Phase", phase), ("Amb", amb), ("FadeP", fade_p), ("Box", box)]
    ps = custom(PS_CODE, unreal.CustomMaterialOutputType.CMOT_FLOAT4, [n for n, _ in ps_inputs], -700, 200)
    for n, src in ps_inputs:
        c(src, ps, n)
    rgb = expr(mat, E.MaterialExpressionComponentMask, -400, 200, r=True, g=True, b=True, a=False)
    alpha = expr(mat, E.MaterialExpressionComponentMask, -400, 300, r=False, g=False, b=False, a=True)
    c(ps, rgb); c(ps, alpha)
    mel.connect_material_property(rgb, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY_MASK)

    mel.recompile_material(mat)
    st = mel.get_statistics(mat)
    log.append("%s: VS %d / PS %d instructions" % (MAT_NAME, st.num_vertex_shader_instructions,
                                                    st.num_pixel_shader_instructions))
    return mat


def place_actor(mat):
    cls = unreal.load_class(None, ACTOR_CLASS)
    if cls is None:
        log.append("AOSMarineSnowField class missing - build the C++ module first.")
        return
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = [a for a in sub.get_all_level_actors() if a.get_class() == cls]
    actor = actors[0] if actors else sub.spawn_actor_from_class(cls, unreal.Vector(0, 0, -1000))
    actor.set_actor_label(ACTOR_LABEL)
    actor.set_editor_property("snow_material", mat)
    actor.set_editor_property("particle_count", 20000)
    actor.set_editor_property("box_size", 4000.0)
    actor.set_editor_property("headlight_scale", 0.001)
    actor.set_editor_property("sun_scale", 0.0005)
    actor.set_editor_property("surface_density", 0.25)
    actor.set_editor_property("full_density_depth", 2500.0)
    actor.set_editor_property("surface_clearance", 20.0)
    for a in sub.get_all_level_actors():
        if isinstance(a, unreal.WaterBodyOcean):
            actor.set_editor_property("water_body", a)
        elif isinstance(a, unreal.DirectionalLight):
            actor.set_editor_property("sun", a)
    log.append("actor: " + actor.get_actor_label())


def main():
    with unreal.ScopedEditorTransaction("AOS marine snow"):
        mat = build_material()
        place_actor(mat)
    if SAVE:
        eas.save_asset(WATER_DIR + "/" + MAT_NAME, only_if_is_dirty=False)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log.append("saved")
    return log


result = main()
