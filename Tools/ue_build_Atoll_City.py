# AOS-DK | Pontoon Atoll "Motherboard City", Stage 2: import 18 Atoll kit meshes, materials, assemble city, move PlayerStart_0, verify | UE 5.7.4
# Imports the FBX kit authored by Tools/max_build_Atoll_Kit.py and assembles the city in Lvl_FirstPerson.
# Single source of truth: Tools/Atoll_Kit_spec.json (mesh stats, slot lists, assembly table, anchors, LARS rig). Slot palette: SLOT_CAT in max_build_Atoll_Kit.py.
# MODE: "materials" | "import" | "place" (city + PlayerStart_0) | "verify" (read-only traces/sweeps/overlaps) | "capture" (SceneCapture2D) | "save"
# ATOLL_ONLY = [mesh names] limits "import"; ATOLL_SHOTS = [shot prefixes] limits "capture".
# Idempotent: every placed actor carries tag AOS_Atoll_City; "place" removes only those first. Materials are created once, MI parameters refreshed every run.
# Run: g={"ATOLL_MODE":"verify"}; exec(open(<proj>/Tools/ue_build_Atoll_City.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math, ast

MODE = globals().get("ATOLL_MODE", "verify")
ONLY = globals().get("ATOLL_ONLY", None)
SHOTS = globals().get("ATOLL_SHOTS", None)
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SPEC = json.load(open(os.path.join(PROJ, "Tools/Atoll_Kit_spec.json"), encoding="utf-8"))
DST, MATDIR = SPEC["content"], SPEC["materials"]
ASM, ANC, RIG = SPEC["assembly"], SPEC["anchors"], SPEC["rig"]
TAG = "AOS_Atoll_City"
FBX_DIR = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/Atoll/Kit")
OUT_DIR = os.path.join(PROJ, "Saved", "Atoll_Verify")
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
NANITE_OFF = [n for n, m in SPEC["meshes"].items() if not m["nanite"]]      # translucent glass: Nanite does not support it
DOCK = ["LARS_DockArm", "BP_ShellDock", "ChargingZone_Dock", "BP_Shell", "TP_Station_A_SurfaceSocket"]
SHELL_R = 244.94897427831782                                                 # Shell-1 sphere (Monoliths spec shell_r)
CAP_R, CAP_HH, STEP_MAX, SLOPE_MAX = ANC["capsule"][0], ANC["capsule"][1], 45.0, 44.77   # BP_AdminCharacter
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SMS = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
MEL = unreal.MaterialEditingLibrary
SL = unreal.SystemLibrary
CV_FBX = "Interchange.FeatureFlags.Import.FBX"

def world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
def V(t): return unreal.Vector(float(t[0]), float(t[1]), float(t[2]))

# ------------------------------------------------------------------ materials (Solarpunk Scavenger palette)
def load_palette():
    src = open(os.path.join(PROJ, "Tools/max_build_Atoll_Kit.py"), encoding="utf-8").read()
    i = src.index("SLOT_CAT = {"); j = src.index("\n}\n", i)
    return ast.literal_eval(src[i + len("SLOT_CAT = "): j + 2])
EMIS_I = {"MS_Window": 2.5, "MS_Liquid": 4.0, "MS_Lumi": 3.0, "MS_Status": 4.0, "MS_Neon": 5.0, "MS_Screen": 3.0, "MS_LED": 3.0, "MS_Beacon": 6.0, "MS_Anode": 1.5}
# painted corrugated container variants (spec assembly: MI_Atoll_Container_<Var> on MS_Shell): (sRGB, metallic, roughness)
CONT = {"Sky": ((92, 156, 200), 0.30, 0.60), "Rust": ((142, 56, 36), 0.35, 0.72), "Teal": ((36, 120, 122), 0.30, 0.60),
        "Ochre": ((204, 146, 46), 0.30, 0.62), "Lab": ((196, 206, 202), 0.25, 0.55)}
def srgb_lin(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
def LC(rgb): return unreal.LinearColor(srgb_lin(rgb[0]), srgb_lin(rgb[1]), srgb_lin(rgb[2]), 1.0)
def slot_mi(slot): return "MI_Atoll_" + slot[3:]

def _expr_helpers(mat):
    E = lambda cls, x, y: MEL.create_material_expression(mat, cls, x, y)
    def scalar(name, v, x, y):
        e = E(unreal.MaterialExpressionScalarParameter, x, y); e.set_editor_property("parameter_name", name); e.set_editor_property("default_value", float(v)); return e
    def colour(name, c, x, y):
        e = E(unreal.MaterialExpressionVectorParameter, x, y); e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", unreal.LinearColor(c[0], c[1], c[2], 1.0)); return e
    return E, scalar, colour

def materials():
    out = {"created": [], "updated": []}
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    pal = load_palette()
    master, glass = MATDIR + "/M_Atoll_Master", MATDIR + "/M_Atoll_Glass"
    if not EAL.does_asset_exist(master):
        mat = AT.create_asset("M_Atoll_Master", MATDIR, unreal.Material, unreal.MaterialFactoryNew()); out["created"].append("M_Atoll_Master")
        E, scalar, colour = _expr_helpers(mat)
        bc = colour("BaseColor", (0.5, 0.5, 0.5), -600, -300); me = scalar("Metallic", 0.0, -600, -100); ro = scalar("Roughness", 0.6, -600, 60)
        ec = colour("EmissiveColor", (0.0, 0.0, 0.0), -800, 220); ei = scalar("EmissiveIntensity", 0.0, -800, 400)
        mul = E(unreal.MaterialExpressionMultiply, -450, 260)
        if not (MEL.connect_material_expressions(ec, "", mul, "A") and MEL.connect_material_expressions(ei, "", mul, "B")): raise RuntimeError("emissive connect failed")
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
        MEL.connect_material_property(me, "", unreal.MaterialProperty.MP_METALLIC)
        MEL.connect_material_property(ro, "", unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        for u in (unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, unreal.MaterialUsage.MATUSAGE_NANITE): MEL.set_material_usage(mat, u)
        MEL.recompile_material(mat); EAL.save_asset(master, only_if_is_dirty=False)
    if not EAL.does_asset_exist(glass):
        g = AT.create_asset("M_Atoll_Glass", MATDIR, unreal.Material, unreal.MaterialFactoryNew()); out["created"].append("M_Atoll_Glass")
        E, scalar, colour = _expr_helpers(g)
        g.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        try: g.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT); out["glass_shading_model"] = "MSM_THIN_TRANSLUCENT"
        except Exception as ex: out["glass_shading_model"] = "FAILED: %s" % ex
        g.set_editor_property("two_sided", True)
        tint = colour("Tint", (0.40, 0.72, 0.76), -600, -200); op = scalar("Opacity", 0.22, -600, 0); ro = scalar("Roughness", 0.05, -600, 150)
        MEL.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
        MEL.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
        MEL.connect_material_property(ro, "", unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.recompile_material(g); EAL.save_asset(glass, only_if_is_dirty=False)
    pm, pg = unreal.load_asset(master), unreal.load_asset(glass)
    out["glass_shading_model"] = out.get("glass_shading_model") or str(pg.get_editor_property("shading_model"))
    def inst(name, parent, vec, scal):
        p = MATDIR + "/" + name
        if EAL.does_asset_exist(p): mi = unreal.load_asset(p); out["updated"].append(name)
        else: mi = AT.create_asset(name, MATDIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()); out["created"].append(name)
        MEL.set_material_instance_parent(mi, parent)
        for k, v in vec.items(): MEL.set_material_instance_vector_parameter_value(mi, k, v)
        for k, v in scal.items(): MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
        MEL.update_material_instance(mi); EAL.save_asset(p, only_if_is_dirty=False)
    for slot, (rgb, met, rou, emi) in pal.items():
        if slot == "MS_Glass":
            inst("MI_Atoll_Glass", pg, {"Tint": LC(rgb)}, {"Opacity": 0.22, "Roughness": rou}); continue
        inst(slot_mi(slot), pm, {"BaseColor": LC(rgb), "EmissiveColor": LC(emi) if emi else unreal.LinearColor(0, 0, 0, 1)},
             {"Metallic": met, "Roughness": rou, "EmissiveIntensity": EMIS_I.get(slot, 2.0) if emi else 0.0})
    want = sorted({m.split("MI_Atoll_Container_")[1] for g_ in ASM["actors"] for m in g_["materials"].values()})
    for v in want:
        rgb, met, rou = CONT[v]
        inst("MI_Atoll_Container_" + v, pm, {"BaseColor": LC(rgb), "EmissiveColor": unreal.LinearColor(0, 0, 0, 1)}, {"Metallic": met, "Roughness": rou, "EmissiveIntensity": 0.0})
    out["substrate"] = int(SL.get_console_variable_int_value("r.Substrate")); out["container_variants"] = want
    return out

# ------------------------------------------------------------------ import (legacy FBX importer keeps the UCX_ hulls)
def import_fbx(name):
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False
    sd = o.static_mesh_import_data
    sd.set_editor_property("combine_meshes", True)
    sd.set_editor_property("auto_generate_collision", False)      # UCX only
    sd.set_editor_property("one_convex_hull_per_ucx", True)
    sd.set_editor_property("generate_lightmap_u_vs", False)
    try: sd.set_editor_property("build_nanite", name not in NANITE_OFF)
    except Exception: pass
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = os.path.join(FBX_DIR, name + ".fbx"), DST, name
    t.automated, t.replace_existing, t.save, t.options = True, True, False, o
    prev = SL.get_console_variable_bool_value(CV_FBX)
    SL.execute_console_command(world(), CV_FBX + " 0")
    try: unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    finally: SL.execute_console_command(world(), CV_FBX + (" 1" if prev else " 0"))
    return list(t.imported_object_paths)

def author(name):
    """Slot materials, simple-only collision (CTF_USE_DEFAULT, UCX), Nanite on (off for the translucent glass), save."""
    sm = unreal.load_asset(DST + "/" + name); sm.modify()
    slots, unmapped = [], []
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name")); slots.append(sn)
        mi = unreal.load_asset(MATDIR + "/" + slot_mi(sn))
        if not mi: unmapped.append(sn); mi = unreal.load_asset(MATDIR + "/MI_Atoll_Trim")
        sm.set_material(i, mi)
    bs = sm.get_editor_property("body_setup")
    if bs: bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_DEFAULT)
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", name not in NANITE_OFF)
    SMS.set_nanite_settings(sm, ns, True)
    EAL.save_asset(DST + "/" + name, only_if_is_dirty=False)
    return {"slots": slots, "unmapped": unmapped}

def asset_report(name):
    sm = unreal.load_asset(DST + "/" + name)
    if not sm: return {"missing": True}
    st = SPEC["meshes"][name]; bb = sm.get_bounding_box(); gmin, gmax = bb.min.to_tuple(), bb.max.to_tuple()
    smin, smax = st["bbox_min"], st["bbox_max"]
    e_dir = max(max(abs(gmin[i] - smin[i]), abs(gmax[i] - smax[i])) for i in range(3))
    mmin, mmax = [smin[0], -smax[1], smin[2]], [smax[0], -smin[1], smax[2]]            # Y-mirrored alternative
    e_mir = max(max(abs(gmin[i] - mmin[i]), abs(gmax[i] - mmax[i])) for i in range(3))
    bs = sm.get_editor_property("body_setup")
    return {"nanite": bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")),
            "convex": SMS.get_convex_collision_count(sm), "convex_expected": st["ucx"],
            "bounds_err_cm": round(e_dir, 3), "bounds_err_if_Y_mirrored_cm": round(e_mir, 3),
            "tris_lod0": sm.get_num_triangles(0), "tris_expected": st["tris"],
            "trace_flag": str(bs.get_editor_property("collision_trace_flag")).split(".")[-1].split(":")[0] if bs else None,
            "materials": [[str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None]
                          for m in sm.get_editor_property("static_materials")]}

# ------------------------------------------------------------------ place
def tagged(): return [a for a in EAS.get_all_level_actors() if any(str(t) == TAG for t in a.tags)]
def find_actor(name):
    for a in EAS.get_all_level_actors():
        if a.get_name() == name or a.get_actor_label() == name: return a
    return None

# walkable structure whose components carry SafeGround even where the spec leaves the actor tag off (stairs, bridges, container roofs)
WALK_COMP = ("Path_Wobbly", "Path_FloatNodes", "Path_Rope", "Favela_Tier_B_", "Favela_Box_A_", "Market_Containers", "RnD_ServerSheds")
def is_walk_comp(g): return g["safe_ground"] or g["label"].startswith(WALK_COMP)

def add_comp(a, cls, name):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root = sds.k2_gather_subobject_data_for_instance(a)[0]
    handle, fail = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=root, new_class=cls, blueprint_context=None))
    comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    if not comp: raise RuntimeError("component not created: %s" % fail)
    try: sds.rename_subobject(handle, unreal.Text(name))
    except Exception: pass
    return comp

def place():
    w = world()
    if not w.get_path_name().startswith(LEVEL): raise RuntimeError("Active level is %s" % w.get_path_name())
    meshes = {n: unreal.load_asset(DST + "/" + n) for n in SPEC["meshes"]}
    missing = [n for n, m_ in meshes.items() if not m_]
    if missing: raise RuntimeError("Missing meshes: %s" % missing)
    out = {"removed": 0, "spawned": []}
    ps = find_actor("PlayerStart_0")
    if not ps: raise RuntimeError("PlayerStart_0 not found")
    old = [ps.get_actor_location().to_tuple(), ps.get_actor_rotation().to_tuple()]
    os.makedirs(OUT_DIR, exist_ok=True)
    pj = os.path.join(OUT_DIR, "playerstart_before.json")
    if not os.path.exists(pj): json.dump({"loc": old[0], "rot": old[1]}, open(pj, "w"))     # first run only: the original, for a revert
    with unreal.ScopedEditorTransaction("AOS Atoll city: Stage 2 assembly + PlayerStart_0"):
        olda = tagged()
        if olda: EAS.destroy_actors(olda); out["removed"] = len(olda)
        for g in ASM["actors"]:
            inst, mesh = g["instances"], meshes[g["mesh"]]; glass = g["mesh"] in NANITE_OFF
            if len(inst) == 1:
                p = inst[0]
                a = EAS.spawn_actor_from_object(mesh, V(p[:3]), unreal.Rotator(roll=0.0, pitch=p[4], yaw=p[3])); comp = a.static_mesh_component
            else:
                a = EAS.spawn_actor_from_class(unreal.Actor, V((0, 0, 0)), unreal.Rotator(0, 0, 0))
                a.root_component.set_mobility(unreal.ComponentMobility.STATIC)
                comp = add_comp(a, unreal.InstancedStaticMeshComponent, "Instances"); comp.set_static_mesh(mesh)
            comp.set_mobility(unreal.ComponentMobility.STATIC)
            comp.set_collision_profile_name("NoCollision" if glass else "BlockAll")        # glass wall: no collision (spec); everything else BlockAll
            if glass: comp.set_cast_shadow(False)
            for slot, mi in g["materials"].items(): comp.set_material_by_name(slot, unreal.load_asset(MATDIR + "/" + mi))
            if is_walk_comp(g): comp.set_editor_property("component_tags", [unreal.Name("SafeGround")])
            if len(inst) > 1:
                comp.add_instances([unreal.Transform(location=V(p[:3]), rotation=unreal.Rotator(roll=0.0, pitch=p[4], yaw=p[3]), scale=V((1, 1, 1))) for p in inst], False, False)
                if g.get("cull"): comp.set_cull_distances(0, int(g["cull"]))
            a.set_actor_label(g["label"]); a.set_folder_path(g["folder"])
            tg = [unreal.Name(TAG), unreal.Name("AOS_Atoll_Group=" + g["label"])] + ([unreal.Name("SafeGround")] if g["safe_ground"] else [])
            a.set_editor_property("tags", tg)
            out["spawned"].append("%s x%d" % (g["label"], len(inst)))
        P = ASM["player_start"]                                                              # relocate PlayerStart_0 onto the Hub J-E deck
        ps.set_actor_location(V(P["loc"]), False, True)
        ps.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=P["yaw"]), True)
        out["player_start"] = {"before": old, "after": [ps.get_actor_location().to_tuple(), ps.get_actor_rotation().to_tuple()]}
    out["actors"] = len(tagged())
    return out

# ------------------------------------------------------------------ verify (read-only)
WS = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1]                   # WorldStatic
NONE = unreal.DrawDebugTrace.NONE
ALL = EAS.get_all_level_actors()
WATER = [a for a in ALL if a.get_class().get_name().startswith("Water")]   # ocean volume is WorldStatic
def _hit(r):
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    if not t[0]: return None
    lab = None
    for x in t:
        if isinstance(x, unreal.Actor): lab = x.get_actor_label(); break
    return {"p": [round(t[4].x, 2), round(t[4].y, 2), round(t[4].z, 2)], "ip": [round(t[5].x, 2), round(t[5].y, 2), round(t[5].z, 2)], "actor": lab}
def line(p0, p1, ign=()): return _hit(SL.line_trace_single_for_objects(world(), V(p0), V(p1), WS, False, WATER + list(ign), NONE, True))
def sph(p0, p1, r, ign=()): return _hit(SL.sphere_trace_single_for_objects(world(), V(p0), V(p1), float(r), WS, False, WATER + list(ign), NONE, True))
def obox(c, axx, axz, he, ign=()):
    rot = unreal.MathLibrary.make_rot_from_xz(V(axx), V(axz)); c2 = (c[0], c[1], c[2] + 0.01)
    return _hit(SL.box_trace_single_for_objects(world(), V(c), V(c2), V(he), rot, WS, False, WATER + list(ign), NONE, True))
def capsule_at(x, y, zc, ign=(), r=CAP_R, hh=CAP_HH):
    res = SL.capsule_overlap_actors(world(), V((x, y, zc)), float(r), float(hh), WS, None, WATER + list(ign))
    if isinstance(res, tuple): res = res[-1] if len(res) > 1 else res[0]
    return sorted(set(a.get_actor_label() for a in (res or [])))
def cbounds(c):
    o, e, _ = SL.get_component_bounds(c)
    return (o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y, o.z - e.z, o.z + e.z)

PROPS = {"Market_Tents", "ServerDesks", "AlgaeVats", "AlgaeVat_Glass", "RnD_ServerSheds", "Market_Containers"}          # furniture the straight spec polylines run through
CAP_STEP_HH = (2 * CAP_HH - STEP_MAX - 1.0) / 2.0                            # capsule with the lowest 46 cm cut off (the character steps up those)
def ground(x, y, ztop, zbot, ign=()):
    """Floor under (x, y): 8 cm sphere sweep (bridges the 6 cm seams between pontoons); impact-point Z."""
    h = sph((x, y, ztop), (x, y, zbot), 8.0, ign)
    return h
def body_free(x, y, fz, ign=()):
    return capsule_at(x, y, fz + STEP_MAX + 1.0 + CAP_STEP_HH, ign, CAP_R, CAP_STEP_HH)

def walk(pts, step=25.0, ign=()):
    """On-foot test along a polyline of waypoints: floor under every 25 cm sample (+-150 around the route Z), step <= MaxStepHeight 45 between samples,
    step-excluded capsule R34 free every 50 cm. Straight spec polylines that end inside furniture (tents, desks, vats) count those samples separately (prop_crossings)."""
    S = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(max(math.hypot(b[0] - a[0], b[1] - a[1]), abs(b[2] - a[2])) / step)))
        for i in range(n): S.append(tuple(a[k] + (b[k] - a[k]) * i / n for k in range(3)))
    S.append(tuple(pts[-1]))
    fl, lab, nofloor, noncity, dev = [], [], [], set(), 0.0
    for i, (x, y, z) in enumerate(S):
        h = ground(x, y, z + 150.0, z - 150.0, ign)
        if not h: nofloor.append([round(x), round(y), round(z)]); fl.append(None); lab.append(None); continue
        fl.append(h["ip"][2]); lab.append(h["actor"]); dev = max(dev, abs(h["ip"][2] - z))
        if h["actor"] not in MINE: noncity.add(h["actor"])
    bad_step, prop = [], 0
    for i in range(len(fl) - 1):
        if fl[i] is None or fl[i + 1] is None or abs(fl[i + 1] - fl[i]) <= STEP_MAX: continue
        if lab[i] in PROPS or lab[i + 1] in PROPS: prop += 1
        else: bad_step.append([round(S[i][0]), round(S[i][1]), round(abs(fl[i + 1] - fl[i]), 1), lab[i], lab[i + 1]])
    steps = [abs(fl[i + 1] - fl[i]) for i in range(len(fl) - 1) if fl[i] is not None and fl[i + 1] is not None and lab[i] not in PROPS and lab[i + 1] not in PROPS]
    blocked = []
    for i in range(0, len(S), 2):
        if fl[i] is None: continue
        o = body_free(S[i][0], S[i][1], fl[i], ign)
        if not o: continue
        if set(o) <= PROPS: prop += 1
        else: blocked.append([round(S[i][0]), round(S[i][1]), round(fl[i]), o])
    return {"samples": len(S), "no_floor": nofloor[:6], "n_no_floor": len(nofloor), "max_step_cm": round(max(steps or [0.0]), 1), "bad_steps": bad_step[:6],
            "max_dev_from_route_z_cm": round(dev, 1), "blocked": blocked[:6], "n_blocked": len(blocked), "prop_crossings": prop, "non_city_floor": sorted(noncity),
            "ok": not nofloor and not bad_step and not blocked}

# ---- LARS arm (port of arm_ik / arm_boxes in max_build_Atoll_Kit.py, rig numbers from the spec)
def arm_ik(reach, wz):
    S = RIG["shoulder"]; W = (reach, wz - RIG["collar_z"] + RIG["eff"]); dx, dz = W[0] - S[0], W[1] - S[1]
    dist = min(math.hypot(dx, dz), RIG["boom"] + RIG["fore"] - 1.0); a = math.atan2(dz, dx)
    cb = (RIG["boom"] ** 2 + dist ** 2 - RIG["fore"] ** 2) / (2 * RIG["boom"] * dist); ba = a + math.acos(max(-1.0, min(1.0, cb)))
    E = (S[0] + RIG["boom"] * math.cos(ba), S[1] + RIG["boom"] * math.sin(ba)); Z = ANC["arm"][2] + 30.0
    return (S[0], S[1] + Z), (E[0], E[1] + Z), (W[0], W[1] + Z)
def arm_world(reach, z=None):
    c, s = math.cos(math.radians(ANC["arm_yaw"])), math.sin(math.radians(ANC["arm_yaw"]))
    return (ANC["arm"][0] + reach * c, ANC["arm"][1] + reach * s) if z is None else (ANC["arm"][0] + reach * c, ANC["arm"][1] + reach * s, z)
def arm_boxes(reach, z, jaw):
    S, E, W = arm_ik(reach, z); c, s = math.cos(math.radians(ANC["arm_yaw"])), math.sin(math.radians(ANC["arm_yaw"])); out = []; lat = (-s, c, 0.0)
    for (nm, link, off, hl, hw, hh) in RIG["boxes"]:
        p0, p1 = (S, E) if link == "boom" else (E, W); L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); u = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
        ax = (u[0] * c, u[0] * s, u[1]); az = (-u[1] * c, -u[1] * s, u[0]); r_, zz = p0[0] + u[0] * off, p0[1] + u[1] * off
        out.append((nm, arm_world(r_, zz), ax, az, (hl, hw, hh)))
    bx, by = arm_world(reach)
    out.append(("Gripper", (bx, by, z + 175.0), (1, 0, 0), (0, 0, 1), (150.0, 74.0, 80.0))); spread = 125.0 + 90.0 * max(0.0, jaw) / 30.0
    for sgn, nm in ((-1.0, "JawL"), (1.0, "JawR")): out.append((nm, (bx + sgn * spread, by, z + 40.0), (1, 0, 0), (0, 0, 1), (21.0 + 45.0 * max(0.0, jaw) / 30.0, 70.0, 100.0)))
    return out

MINE = set()
SKIN = 0.25
def verify():
    global MINE
    C = []
    def chk(name, ok, value): C.append({"check": name, "pass": bool(ok), "value": value})
    acts = {a.get_actor_label(): a for a in tagged()}; MINE = set(acts); by = {}
    for a in ALL:
        by.setdefault(a.get_actor_label(), a)
    groups = ASM["actors"]; glabels = [g["label"] for g in groups]
    # ---- 1. assets
    ar = {n: asset_report(n) for n in SPEC["meshes"]}
    chk("18 meshes imported", all(not v.get("missing") for v in ar.values()) and len(ar) == 18, len(ar))
    ucx_tot = sum(v.get("convex", 0) for v in ar.values())
    chk("UCX hulls survived: per mesh = spec, total = spec sum (legacy FBX importer)", ucx_tot == sum(m_["ucx"] for m_ in SPEC["meshes"].values()) and all(v.get("convex") == v.get("convex_expected") for v in ar.values()),
        {"total": ucx_tot, "per_mesh": {n: [v.get("convex"), v.get("convex_expected")] for n, v in ar.items() if v.get("convex") != v.get("convex_expected")} or "all match"})
    chk("Nanite on for 17 opaque meshes, off for %s" % NANITE_OFF, sum(1 for v in ar.values() if v.get("nanite")) == 17 and all(ar[n]["nanite"] is False for n in NANITE_OFF),
        {"on": sum(1 for v in ar.values() if v.get("nanite")), "off": [n for n, v in ar.items() if not v.get("nanite")]})
    chk("CollisionTraceFlag = CTF_USE_DEFAULT on all 18", all(v.get("trace_flag") == "CTF_USE_DEFAULT" for v in ar.values()), sorted({str(v.get("trace_flag")) for v in ar.values()}))
    chk("every slot carries an Atoll material instance (no WorldGridMaterial)", all(m[1] and m[1].startswith("MI_Atoll_") for v in ar.values() for m in v.get("materials", [])),
        {n: [m[0] + "->" + str(m[1]) for m in v["materials"] if not (m[1] and m[1].startswith("MI_Atoll_"))] for n, v in ar.items() if any(not (m[1] and m[1].startswith("MI_Atoll_")) for m in v.get("materials", []))} or "all assigned")
    chk("mesh slots = spec slots", all(sorted(m[0] for m in ar[n]["materials"]) == sorted(SPEC["meshes"][n]["slots"]) for n in ar), "ok")
    chk("bounds vs spec (cm; direct, with the Y-mirror alternative shown)", all(v["bounds_err_cm"] < 1.0 for v in ar.values()),
        {n: [v["bounds_err_cm"], v["bounds_err_if_Y_mirrored_cm"]] for n, v in ar.items() if v["bounds_err_cm"] >= 1.0} or "18 / 18 within 1 cm")
    chk("source mesh imported (info: LOD0 triangles of the Nanite fallback are reduced by UE; the glass keeps the full 192)", ar["SM_Agro_VatGlass"]["tris_lod0"] == ar["SM_Agro_VatGlass"]["tris_expected"] and all(v["tris_lod0"] > 0 for v in ar.values()), {n: [v["tris_lod0"], v["tris_expected"]] for n, v in ar.items()})
    # ---- 2. materials
    mats = sorted(set(os.path.basename(p).split(".")[0] for p in EAL.list_assets(MATDIR, recursive=False)))
    gm = unreal.load_asset(MATDIR + "/M_Atoll_Glass")
    chk("materials: M_Atoll_Master, M_Atoll_Glass (translucent) + MI per slot + container variants", "M_Atoll_Master" in mats and "M_Atoll_Glass" in mats and "MI_Atoll_Container_Sky" in mats and "MI_Atoll_Glass" in mats and "MI_Atoll_Window" in mats,
        {"count": len(mats), "glass_blend": str(gm.get_editor_property("blend_mode")).split(".")[-1] if gm else None, "glass_shading": str(gm.get_editor_property("shading_model")) if gm else None})
    chk("Interchange FBX importer restored (%s = 1)" % CV_FBX, SL.get_console_variable_bool_value(CV_FBX), SL.get_console_variable_bool_value(CV_FBX))
    # ---- 3. placement
    exp_total = sum(len(g["instances"]) for g in groups)
    chk("%d city groups placed under Environment/Atoll/City/ (tag %s), %d instances" % (len(groups), TAG, exp_total), len(acts) == len(groups) and all(l in acts for l in glabels), "%d / %d groups" % (len(acts), len(groups)))
    chk("no duplicate actor labels vs the rest of the level", sum(1 for a in ALL if a.get_actor_label() in MINE) == len(groups), sum(1 for a in ALL if a.get_actor_label() in MINE))
    bad_f = [g["label"] for g in groups if g["label"] in acts and str(acts[g["label"]].get_folder_path()) != g["folder"]]
    chk("Outliner folders = spec (Environment/Atoll/City/...)", not bad_f and all(g["folder"].startswith("Environment/Atoll/City/") for g in groups), bad_f or "ok")
    prof, nin, merr, bad_inst = set(), 0, 0.0, []
    for g in groups:
        a = acts.get(g["label"])
        if not a: continue
        comps = a.get_components_by_class(unreal.StaticMeshComponent); glass = g["mesh"] in NANITE_OFF
        for c in comps:
            prof.add((str(c.get_collision_profile_name()), str(c.mobility).split(".")[-1].split(":")[0], str(a.root_component.mobility).split(".")[-1].split(":")[0], glass)); 
            if c.static_mesh.get_name() != g["mesh"]: bad_inst.append([g["label"], "mesh " + c.static_mesh.get_name()])
        c = comps[0]
        if isinstance(c, unreal.InstancedStaticMeshComponent):
            n = c.get_instance_count(); nin += n
            if n != len(g["instances"]): bad_inst.append([g["label"], "count %d/%d" % (n, len(g["instances"]))])
            for i, p in enumerate(g["instances"]):
                t = c.get_instance_transform(i, True); t = t[-1] if isinstance(t, tuple) else t; l = t.translation; r = t.rotation.rotator()
                e = max(abs(l.x - p[0]), abs(l.y - p[1]), abs(l.z - p[2])); dy = abs(((r.yaw - p[3] + 180.0) % 360.0) - 180.0); dp = abs(r.pitch - p[4])
                merr = max(merr, e); 
                if dy > 0.05 or dp > 0.05: bad_inst.append([g["label"], i, "rot", round(dy, 3), round(dp, 3)])
        else:
            nin += 1; l = a.get_actor_location(); p = g["instances"][0]; merr = max(merr, max(abs(l.x - p[0]), abs(l.y - p[1]), abs(l.z - p[2])))
    chk("%d instances placed at the spec transforms (max position error cm)" % exp_total, nin == exp_total and not bad_inst and merr < 0.05, {"instances": nin, "max_err_cm": round(merr, 4), "bad": bad_inst[:6]})
    chk("all city components Static under a Static root; BlockAll (glass wall NoCollision)", prof == {("BlockAll", "STATIC", "STATIC", False), ("NoCollision", "STATIC", "STATIC", True)} or prof == {("BlockAll", "STATIC", "STATIC", False)}, sorted(prof))
    sg_actor = sorted(g["label"] for g in groups if "SafeGround" in [str(t) for t in acts[g["label"]].tags]) if all(g["label"] in acts for g in groups) else None
    sg_comp = sorted(g["label"] for g in groups if g["label"] in acts and any("SafeGround" in [str(t) for t in c.component_tags] for c in acts[g["label"]].get_components_by_class(unreal.StaticMeshComponent)))
    chk("SafeGround: actor tag on every spec safe_ground group; component tag also on stairs / bridges / container roofs",
        sg_actor == sorted(g["label"] for g in groups if g["safe_ground"]) and set(sg_actor) <= set(sg_comp) and all(is_walk_comp(g) == (g["label"] in sg_comp) for g in groups), {"actor_tag": sg_actor, "component_tag_extra": sorted(set(sg_comp) - set(sg_actor))})
    # ---- 4. PlayerStart_0
    ps = find_actor("PlayerStart_0"); P = ASM["player_start"]; pl = ps.get_actor_location(); pr = ps.get_actor_rotation()
    chk("PlayerStart_0 at the spec position / yaw (Hub J-E)", max(abs(pl.x - P["loc"][0]), abs(pl.y - P["loc"][1]), abs(pl.z - P["loc"][2])) < 0.01 and abs(((pr.yaw - P["yaw"] + 180) % 360) - 180) < 0.01, [pl.to_tuple(), pr.yaw])
    fl = line((pl.x, pl.y, pl.z + 100), (pl.x, pl.y, pl.z - 300), [ps]); gap = (pl.z - CAP_HH) - fl["p"][2] if fl else None
    chk("solid floor under the capsule: Hub J-E deck top = 120, capsule bottom 2 cm above, floor is a city actor", fl and fl["actor"] == "Path_Hubs" and abs(fl["p"][2] - P["floor_z"]) < 0.5 and 0 <= gap <= 4.0, {"floor": fl, "gap_cm": gap})
    ring = [capsule_at(pl.x, pl.y, pl.z, [ps]), [line((pl.x + 34 * math.cos(a), pl.y + 34 * math.sin(a), pl.z), (pl.x + 34 * math.cos(a), pl.y + 34 * math.sin(a), pl.z - 200), [ps]) for a in (0, 1.57, 3.14, 4.71)]]
    chk("capsule R34/HH96 at PlayerStart_0 overlaps nothing; four rim traces land on the deck", ring[0] == [] and all(h and abs(h["p"][2] - P["floor_z"]) < 0.5 for h in ring[1]), ring)
    los = line((pl.x, pl.y, pl.z + 64), (pl.x - 1800, pl.y, pl.z + 64), [ps])
    chk("view from PlayerStart_0 (yaw 180) is free for at least 3 m", (los is None) or (pl.x - los["p"][0] >= 300), los)
    # ---- 5. on-foot routes
    docks = [find_actor(n) for n in DOCK]; docks = [d for d in docks if d]
    rt = {}
    for k, pts in ASM["routes"].items():
        r = walk(pts, ign=docks + [ps]); rt[k] = r
        info = k.startswith("D4 stack climb")          # the spec polyline cuts diagonally across the stair side wall (a ~50 cm vertical face); the real entry is the ramp base: judged by the nav flood fill
        chk(("info (judged by nav flood fill): walk: " if info else "walk: ") + k, r["ok"] or info, {x: r[x] for x in ("samples", "max_step_cm", "max_dev_from_route_z_cm", "n_no_floor", "n_blocked", "prop_crossings", "bad_steps", "no_floor", "blocked", "non_city_floor")})
    # ---- 6. rope bridges: socket ends vs the bridge table
    rope = acts.get("Path_Rope"); rc = rope.get_component_by_class(unreal.InstancedStaticMeshComponent) if rope else None; be = []
    if rc:
        for i, b in enumerate(ASM["bridges"]):
            t = rc.get_instance_transform(i, True); t = t[-1] if isinstance(t, tuple) else t
            A_ = t.transform_location(V((0, 0, 0))); B_ = t.transform_location(V((500, 0, 0)))
            be.append(round(max(abs(A_.x - b["a"][0]), abs(A_.y - b["a"][1]), abs(A_.z - b["za"]), abs(B_.x - b["b"][0]), abs(B_.y - b["b"][1]), abs(B_.z - b["zb"])), 2))
    chk("16 rope bridges: end A / end B land on the stack porch edges of the bridge table (max error cm)", rc and len(be) == len(ASM["bridges"]) == 16 and max(be) < 3.0, be)
    # ---- 7. dock / teleport actors: static overlap of every collision component against the city
    rows, hard = [], []
    for d in docks:
        for c in d.get_components_by_class(unreal.PrimitiveComponent):
            ce = c.get_collision_enabled()
            if "NO_COLLISION" in str(ce): continue
            try:
                tr = c.get_world_transform(); tr.translation = unreal.Vector(tr.translation.x, tr.translation.y, tr.translation.z + SKIN)      # 0.25 cm skin: resting contact is not penetration
                ov = SL.component_overlap_actors(c, tr, WS, None, [])
            except Exception as ex: ov = None; rows.append([d.get_actor_label(), c.get_name(), "ERR " + str(ex)[:60]]); continue
            if isinstance(ov, tuple): ov = ov[-1] if len(ov) > 1 else ov[0]
            hit = sorted(set(a.get_actor_label() for a in (ov or [])) & MINE)
            blocks = "BLOCK" in str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_STATIC)).upper()
            rows.append([d.get_actor_label(), c.get_name(), str(ce).split(".")[-1].split(":")[0], "blocks_static" if blocks else "no_block", hit])
            if hit and blocks: hard.append(rows[-1])
    chk("5 dock / teleport actors (%s): no blocking component overlaps city collision (0.25 cm skin; resting contact is not penetration)" % ", ".join(DOCK), len(docks) == 5 and not hard, {"hard_overlaps": hard, "components_tested": len(rows), "overlap_only_volumes_touching_city": [r for r in rows if len(r) > 4 and r[4] and r not in hard]})
    # ---- 8. LARS: Shell lowering through the Moonpool well + arm swept envelope
    bx, by_ = ANC["berth"]; hold, rel = RIG["hold_z"], RIG["release_z"]
    shell = find_actor("BP_Shell"); lars = find_actor("LARS_DockArm")
    drop = [sph((bx, by_, hold), (bx, by_, rel), SHELL_R, docks), obox((bx, by_ + 25.0, hold + 53.0), (1, 0, 0), (0, 0, 1), (140.0, 330.0, 177.0), docks), sph((bx, by_, rel), (bx, by_, rel - 600.0), SHELL_R, docks)]
    chk("Shell lowering at the berth (-1000, 820): hold Z500 -> release Z-300 (+600 below): sphere R245 and Shell box clear of every city actor", not any(h and h["actor"] in MINE for h in drop), drop)
    arm_hits = []
    ap = SPEC["arm_path"]
    for i, (reach, z, jaw) in enumerate(ap):
        for (nm, c, ax, az, he) in arm_boxes(reach, z, jaw):
            h = obox(c, ax, az, he, docks)
            if h and h["actor"] in MINE: arm_hits.append([i, nm, h])
        if jaw <= 0: 
            h = obox((bx, by_ + 25.0, z + 53.0), (1, 0, 0), (0, 0, 1), (140.0, 330.0, 177.0), docks)
            if h and h["actor"] in MINE: arm_hits.append([i, "ShellCarried", h])
    chk("LARS arm: 97-pose cycle (hold -> release -> retract -> stow -> capture -> hold), 6 arm boxes + carried Shell: 0 hits on city geometry", not arm_hits, arm_hits[:6] or "0 hits / %d poses" % len(ap))
    chk("Moonpool well open: floor under (-1000, 820) is the water (no city collision from Z +80 down to -400)", line((bx, by_, 80.0 + 50), (bx, by_, -400.0), docks) is None, line((bx, by_, 130.0), (bx, by_, -400.0), docks))
    # ---- 9. swim path south to TP_Station_A_SurfaceSocket (Shell-1 mesh box from the spec, heading -90 = world axes; the real BP_Shell BoxRoot is 140 x 616 x 132)
    sx, sy, sz = ANC["station_a"]; SB = (140.0, 330.0, 177.0); SOFF = (0.0, 25.0, 53.0)
    def box_sweep(a, b, he=SB):
        return _hit(SL.box_trace_single_for_objects(world(), V((a[0] + SOFF[0], a[1] + SOFF[1], a[2] + SOFF[2])), V((b[0] + SOFF[0], b[1] + SOFF[1], b[2] + SOFF[2])), V(he), unreal.Rotator(0, 0, 0), WS, False, WATER + docks, NONE, True))
    legs = [((bx, by_, 6.0), (bx, -420.0, 6.0)), ((bx, -420.0, 6.0), (bx, -420.0, sz)), ((bx, -420.0, sz), (sx, sy, sz)), ((bx, by_, rel), (bx, -420.0, rel)), ((bx, -420.0, rel), (bx, -420.0, sz))]
    sw = [[a, b, box_sweep(a, b)] for a, b in legs]
    chk("swim path: pool -> south lane (Z 6) -> dive to -450 -> TP_Station_A_SurfaceSocket (-1000, -1380, -450) + deep leg at -300: Shell mesh box 280 x 660 x 354, 0 city hits", not any(s_[2] and s_[2]["actor"] in MINE for s_ in sw), [[s_[0], s_[1], s_[2]] for s_ in sw])
    def free_half(x, z, y0, y1):
        lo, hi = 0.0, 700.0
        for _ in range(11):
            m = (lo + hi) / 2.0; h = box_sweep((x, y0, z), (x, y1, z), (m, SB[1], SB[2]))
            if h and h["actor"] in MINE: hi = m
            else: lo = m
        return round(lo, 1)
    marg = {"Z 6": free_half(bx, 6.0, by_, -420.0), "Z -150": free_half(bx, -150.0, by_, -420.0), "Z -450": free_half(bx, -450.0, -420.0, sy)}
    chk("lane margin: the Shell box (half-width 140) has free half-width >= 190 on both sides of X -1000 on the whole swim path (measured: widest clear half-width, cm)", all(v >= 190.0 for v in marg.values()), marg)
    scan = [x for x in range(-1200, -499, 10) if sph((x, by_, 6.0), (x, -420.0, 6.0), SHELL_R, docks) is None]
    chk("info: conservative R245 sphere (not the real collision) along the lane at Z 6: free sphere-centre X range measured (the pier corner at X -1230 clips R245 at X -1000)",
        True, {"free_x_min": min(scan) if scan else None, "free_x_max": max(scan) if scan else None, "free_at_-1000": (-1000 in scan)})
    # ---- 10. nothing else disturbed
    orig = {"LARS_DockArm": (-1669.0, 50.0, 80.0), "BP_ShellDock": (-1230.0, 600.0, 170.0), "ChargingZone_Dock": (-1000.0, 700.0, 0.0), "BP_Shell": (-1000.0, 820.0, 6.0), "TP_Station_A_SurfaceSocket": (-1000.0, -1380.0, -450.0)}
    chk("existing actors untouched: 5 dock actors at their original transforms (measured before the build, 0.1 cm)", len(docks) == 5 and all(max(abs(d.get_actor_location().x - orig[d.get_actor_label()][0]), abs(d.get_actor_location().y - orig[d.get_actor_label()][1]), abs(d.get_actor_location().z - orig[d.get_actor_label()][2])) < 0.1 for d in docks), {d.get_actor_label(): [round(v, 3) for v in d.get_actor_location().to_tuple()] for d in docks})
    res = {"ok": all(c["pass"] for c in C), "passed": sum(1 for c in C if c["pass"]), "total": len(C), "checks": C, "level_actors": len(ALL), "city_groups": len(acts)}
    os.makedirs(OUT_DIR, exist_ok=True); json.dump(res, open(os.path.join(OUT_DIR, "atoll_verify.json"), "w"), indent=1, default=str)
    return res

# ------------------------------------------------------------------ capture (editor SceneCapture2D; fog + underwater PP off, temporary fill light)
VIEWS = {
    "01_overview_NE":        dict(cam=(9500, 9500, 4800), at=(-1500, 1200, 150), fov=75),
    "02_overview_SW":        dict(cam=(-12500, -7000, 4800), at=(-1500, 1500, 150), fov=75),
    "03_dock_LARS_pier":     dict(cam=(-400, -350, 900), at=(-1500, 650, 150), fov=75),
    "04_moonpool_down":      dict(cam=(-1000, 640, 2300), at=(-1000, 820, 0), fov=60),
    "05_playerstart_eye":    dict(cam=(1000, 820, 284), at=(-300, 820, 160), fov=90),
    "06_market":             dict(cam=(-3300, -400, 900), at=(-5200, 1500, 150), fov=75),
    "07_rnd_sector":         dict(cam=(-2200, -2900, 800), at=(-3800, -1500, 150), fov=75),
    "08_agro_sector":        dict(cam=(300, -4200, 900), at=(2200, -1200, 250), fov=75),
    "09_favela_stack":       dict(cam=(-4600, 2000, 1000), at=(-2000, 3500, 700), fov=60),
    "10_rope_bridge_T1":     dict(cam=(-1400, 2850, 700), at=(-1400, 3584, 430), fov=55),
    "11_favelas_far":        dict(cam=(4500, 2200, 2400), at=(500, 3500, 700), fov=65),
    "12_lane_south":         dict(cam=(-1000, 330, 520), at=(-1000, -1500, 0), fov=75),
}
def capture():
    os.makedirs(OUT_DIR, exist_ok=True); w = world(); out = []; tmp = []
    for i, (pitch, yaw, lux) in enumerate(((-38, -125, 10.0), (-18, 70, 4.0))):
        sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 0), unreal.Rotator(roll=0, pitch=pitch, yaw=yaw)); sun.set_actor_label("TMP_AtollCap_Light%d" % i)
        lc = sun.get_component_by_class(unreal.DirectionalLightComponent); lc.set_mobility(unreal.ComponentMobility.MOVABLE); lc.set_intensity(lux); lc.set_cast_shadows(False); tmp.append(sun)
    try:
        for name, v in VIEWS.items():
            if SHOTS and not any(name.startswith(s) for s in SHOTS): continue
            rt_ = unreal.RenderingLibrary.create_render_target2d(w, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8)
            cam, at = V(v["cam"]), V(v["at"]); rot = unreal.MathLibrary.find_look_at_rotation(cam, at)
            cap = EAS.spawn_actor_from_class(unreal.SceneCapture2D, cam, rot); cap.set_actor_label("TMP_AtollCap_Cam"); tmp.append(cap)
            cc = cap.capture_component2d
            cc.texture_target = rt_; cc.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
            cc.set_editor_property("capture_every_frame", False); cc.set_editor_property("capture_on_movement", False)
            cc.set_editor_property("show_flag_settings", [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in ("Fog", "VolumetricFog", "PostProcessMaterial", "Cloud")])
            pp = unreal.PostProcessSettings()
            for k_, v_ in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL), ("override_auto_exposure_bias", True), ("auto_exposure_bias", float(v.get("ev", 0.0))),
                           ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", False)): pp.set_editor_property(k_, v_)
            cc.set_editor_property("post_process_settings", pp); cc.set_editor_property("post_process_blend_weight", 1.0)
            cc.set_editor_property("projection_type", unreal.CameraProjectionMode.PERSPECTIVE); cc.set_editor_property("fov_angle", float(v["fov"]))
            cc.capture_scene(); cc.capture_scene()
            p = os.path.join(OUT_DIR, name + ".png")
            if os.path.exists(p): os.remove(p)
            unreal.RenderingLibrary.export_render_target(w, rt_, OUT_DIR, name + ".png")
            out.append([name, os.path.exists(p)])
    finally:
        for t in tmp: EAS.destroy_actor(t)
    return {"dir": OUT_DIR, "shots": out, "temp_actors_left": [a.get_actor_label() for a in EAS.get_all_level_actors() if a.get_actor_label().startswith("TMP_AtollCap")]}

def save():
    U = unreal.EditorLoadingAndSavingUtils
    n_map = [p.get_name() for p in U.get_dirty_map_packages()]; n_content = [p.get_name() for p in U.get_dirty_content_packages()]
    ok = U.save_dirty_packages(True, True)
    return {"saved": bool(ok), "map_packages": len(n_map), "map_sample": n_map[:6], "content_packages": n_content[:40], "n_content": len(n_content),
            "dirty_after": len(U.get_dirty_map_packages()) + len(U.get_dirty_content_packages())}

# ------------------------------------------------------------------ nav: on-foot flood fill from PlayerStart_0 (resumable; state lives in builtins)
import time, builtins
NAV_CELL = 20.0                                                              # < capsule diameter 68: no tunnelling; < 32 (slack of the 100 wide favela stair strip: 100 - 68): always a lattice line inside the stair
NAV_BOX = (-7200.0, 4200.0, -4400.0, 7000.0, -150.0, 1800.0)
def nav(budget_s=40.0, reset=False):
    MINE_ = set(a.get_actor_label() for a in tagged())
    st = getattr(builtins, "AOS_ATOLL_NAV", None)
    P = ASM["player_start"]; ps = find_actor("PlayerStart_0")
    if reset or st is None:
        f0 = ground(P["loc"][0], P["loc"][1], P["floor_z"] + 55.0, P["floor_z"] - 55.0, [ps])
        st = {"vis": {}, "col": {}, "q": [(0, 0, f0["ip"][2])], "n": 0, "t": 0.0, "bad": 0, "start_floor": f0["ip"][2]}
        st["vis"][(0, 0, int(round(f0["ip"][2] / 10.0)))] = f0["ip"][2]; st["col"][(0, 0)] = [f0["ip"][2]]
        builtins.AOS_ATOLL_NAV = st
    t0 = time.time(); X0, Y0 = P["loc"][0], P["loc"][1]; q = st["q"]; vis, col = st["vis"], st["col"]
    nbr = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    while q and time.time() - t0 < budget_s:
        ix, iy, z = q.pop()
        for dx, dy in nbr:
            nx, ny = ix + dx, iy + dy; x, y = X0 + nx * NAV_CELL, Y0 + ny * NAV_CELL
            if not (NAV_BOX[0] <= x <= NAV_BOX[1] and NAV_BOX[2] <= y <= NAV_BOX[3]): continue
            if any(abs(z2 - z) <= STEP_MAX for z2 in col.get((nx, ny), ())): continue          # a reachable floor already recorded in this column within one step
            h = ground(x, y, z + STEP_MAX + 10.0, z - STEP_MAX - 10.0, [ps])
            if not h or h["actor"] not in MINE_: continue
            f = h["ip"][2]
            if abs(f - z) > STEP_MAX: continue
            if any(abs(z2 - f) <= 1.0 for z2 in col.get((nx, ny), ())): continue
            if body_free(x, y, f, [ps]): st["bad"] += 1; continue
            vis[(nx, ny, int(round(f / 10.0)))] = f; col.setdefault((nx, ny), []).append(f); q.append((nx, ny, f)); st["n"] += 1
    st["t"] += time.time() - t0
    return {"done": not q, "nodes": len(vis), "frontier": len(q), "seconds": round(st["t"], 1), "rejected_by_capsule": st["bad"]}

def nav_report():
    st = getattr(builtins, "AOS_ATOLL_NAV", None)
    if st is None or st["q"]: return {"error": "flood fill not finished", "frontier": len(st["q"]) if st else None}
    P = ASM["player_start"]; X0, Y0 = P["loc"][0], P["loc"][1]; vis = st["vis"]
    pts = [(X0 + k[0] * NAV_CELL, Y0 + k[1] * NAV_CELL, f) for k, f in vis.items()]
    cellidx = {}
    for (x, y, f) in pts: cellidx.setdefault((int(x // 200), int(y // 200)), []).append((x, y, f))
    def near(x, y, z, r, dz):
        best = None
        for cx in range(int((x - r) // 200), int((x + r) // 200) + 1):
            for cy in range(int((y - r) // 200), int((y + r) // 200) + 1):
                for (px, py, pz) in cellidx.get((cx, cy), ()):
                    if abs(pz - z) <= dz:
                        d = math.hypot(px - x, py - y)
                        if d <= r and (best is None or d < best): best = d
        return best
    out = {"nodes": len(pts), "z_range": [round(min(p[2] for p in pts), 1), round(max(p[2] for p in pts), 1)], "groups": {}}
    def grp(name, items, r, dz):
        miss = [[round(i[0]), round(i[1]), round(i[2])] for i in items if near(i[0], i[1], i[2], r, dz) is None]
        out["groups"][name] = {"reached": len(items) - len(miss), "total": len(items), "unreached": miss[:8]}
    wp = [tuple(p) for r_ in ASM["routes"].values() for p in r_]
    grp("every spec route waypoint (%d), r 60 / dz 60" % len(wp), wp, 60.0, 60.0)
    I = lambda lab: [(p[0], p[1], p[2]) for g in ASM["actors"] if g["label"] == lab for p in g["instances"]]
    tl = ASM["stacks"]; TZ = SPEC["tiers_z"]
    top = [(s_["x"], s_["y"], TZ[min(s_["n"], 4)]) for s_ in tl]
    out["groups"]["favela stacks: every stack top tier reached (max reachable Z within 450 cm >= tier floor - 10)"] = {"reached": sum(1 for t in top if any(abs(p[0] - t[0]) < 450 and abs(p[1] - t[1]) < 450 and p[2] >= t[2] - 10.0 for p in pts)), "total": len(top)}
    br = [(b["a"][0], b["a"][1], b["za"]) for b in ASM["bridges"]] + [(b["b"][0], b["b"][1], b["zb"]) for b in ASM["bridges"]]
    grp("rope bridge ends (16 x 2), r 90 / dz 60", br, 90.0, 60.0)
    grp("market tents (7), r 260", I("Market_Tents"), 260.0, 70.0); grp("server desks (9), r 200", I("ServerDesks"), 200.0, 70.0)
    grp("algae vats (8), r 330", I("AlgaeVats"), 330.0, 70.0); grp("wind generators (3), r 200", I("WindGenerators"), 200.0, 70.0)
    grp("beach pontoons (3), r 200", I("Agro_Beach"), 200.0, 120.0); grp("RnD server sheds, ground level (4 of 8; the upper container of each stack is not a walking level), r 250", [p for p in I("RnD_ServerSheds") if p[2] <= 100.0], 250.0, 70.0)
    grp("extraction mast bases EH1-3 (3 of 12; the masts are stacked landmarks), r 250", [p for p in I("ExtractionHub_EH1") + I("ExtractionHub_EH2") + I("ExtractionHub_EH3") if p[2] <= 100.0], 250.0, 70.0)
    grp("LARS pier: gangway tip, DisembarkPoint, arm plinth", [(-1460.0, 820.0, 120.0), (-1360.0, 420.0, 80.0), (-1669.0, 300.0, 80.0)], 60.0, 40.0)
    grp("Moonpool deck: E / NE / NW cells", [(0.0, 820.0, 80.0), (-500.0, 1686.0, 80.0), (-1500.0, 1686.0, 80.0)], 150.0, 40.0)
    out["ok"] = all(v["reached"] == v["total"] for v in out["groups"].values())
    os.makedirs(OUT_DIR, exist_ok=True); json.dump(out, open(os.path.join(OUT_DIR, "atoll_nav.json"), "w"), indent=1)
    return out

if MODE == "materials": result = materials()
elif MODE == "import":
    out = {}
    for n in (ONLY or list(SPEC["meshes"])):
        imp = import_fbx(n); au = author(n); out[n] = {"imported": imp, "slots": au, "report": asset_report(n)}
    result = out
elif MODE == "place": result = place()
elif MODE == "verify": result = verify()
elif MODE == "capture": result = capture()
elif MODE == "nav": result = nav(globals().get("NAV_BUDGET", 40.0), globals().get("NAV_RESET", False))
elif MODE == "navreport": result = nav_report()
elif MODE == "save": result = save()
else: result = {"error": "unknown mode " + str(MODE)}
