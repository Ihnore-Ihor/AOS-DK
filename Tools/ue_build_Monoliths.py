# AOS-DK | Tower A Stage 2: sector bed, Tower A-3 envelope, 24 background monoliths | UE 5.7.4 (run via execute_python)
# Imports the 5 FBX kit meshes authored by Tools/max_build_Monoliths_Kit.py (3ds Max 2027) and deploys them in Lvl_FirstPerson.
# Single source of truth: Tools/Monoliths_Kit_spec.json (mesh stats + assembly table written by the Max script).
# MODE: "materials" (M_AOS_DepthRing + MI) | "import" (FBX -> Nanite static meshes, UCX kept, materials) | "place" (26 actors)
#       | "verify" (read-only traces / sweeps / overlaps) | "capture" (SceneCapture2D screenshots) | "save" (dirty packages).
# MONO_ONLY = [mesh names] limits "import"; MONO_SHOTS = [shot id prefixes] limits "capture".
# Idempotent: every placed actor carries the tag AOS_Monoliths_Kit; "place" removes only actors with that tag first.
# Run: g={"MONO_MODE":"verify"}; exec(open(<proj>/Tools/ue_build_Monoliths.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math

MODE = globals().get("MONO_MODE", "verify")
ONLY = globals().get("MONO_ONLY", None)
SHOTS = globals().get("MONO_SHOTS", None)
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SPEC = json.load(open(os.path.join(PROJ, "Tools/Monoliths_Kit_spec.json"), encoding="utf-8"))
DST = SPEC["content"]; FOLDER = SPEC["folder"]; TAG = "AOS_Monoliths_Kit"
FBX_DIR = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/Macro/Monoliths")
OUT_DIR = os.path.join(PROJ, "Saved", "Monoliths_Verify")
MAT_CONCRETE = "/Game/AOS_DK_Game/Environment/Clusters/Shared/M_AOS_Concrete_BoxMap"
MAT_RING, MAT_RING2 = DST + "/M_AOS_DepthRing", DST + "/MI_AOS_DepthRing_Second"
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
F_BED, F_A3 = "Environment/Macro/SectorBed", "Environment/Macro/Tower_A3"
BOXMAP_K = 0.25                                                    # 800 cm concrete tiles, as on Spire A-0
GREEN, CYAN = (0.0802, 0.9560, 0.1981), (0.2582, 0.8148, 0.9823)   # Dracula, linear (bible §3.0.3)
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SMS = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
MEL = unreal.MaterialEditingLibrary
SL = unreal.SystemLibrary
M = SPEC["marks"]; A3 = SPEC["a3"]; ASM = SPEC["assembly"]

def world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
def V(t): return unreal.Vector(float(t[0]), float(t[1]), float(t[2]))

# ------------------------------------------------------------------ materials
def materials():
    """M_AOS_DepthRing: emissive strip driven by world Z only (no per-instance data): Green 6.0 on every 100 m mark,
    Cyan on the 500 m marks; with StripB = 1 (second strip) the strip is lit on the 500 m marks only."""
    out = {}
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    if EAL.does_asset_exist(MAT_RING) and EAL.does_asset_exist(MAT_RING2):
        return {"material": "exists", "instance": "exists", "expressions": MEL.get_num_material_expressions(unreal.load_asset(MAT_RING))}
    mat = AT.create_asset("M_AOS_DepthRing", DST, unreal.Material, unreal.MaterialFactoryNew()); out["material"] = "created"
    E = lambda cls, x, y: MEL.create_material_expression(mat, cls, x, y)
    def C(a_, ao, b_, bi):
        if not MEL.connect_material_expressions(a_, ao, b_, bi): raise RuntimeError("connect failed: %s -> %s.%s" % (a_.get_name(), b_.get_name(), bi))
    def const(v, x, y):
        e = E(unreal.MaterialExpressionConstant, x, y); e.set_editor_property("r", float(v)); return e
    def scalar(name, v, x, y):
        e = E(unreal.MaterialExpressionScalarParameter, x, y); e.set_editor_property("parameter_name", name); e.set_editor_property("default_value", float(v)); return e
    def colour(name, c, x, y):
        e = E(unreal.MaterialExpressionVectorParameter, x, y); e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", unreal.LinearColor(c[0], c[1], c[2], 1.0)); return e
    wp = E(unreal.MaterialExpressionWorldPosition, -1700, 0)
    mz = E(unreal.MaterialExpressionComponentMask, -1500, 0)
    for ch, on in (("r", False), ("g", False), ("b", True), ("a", False)): mz.set_editor_property(ch, on)
    C(wp, "", mz, "")
    hm = E(unreal.MaterialExpressionMultiply, -1300, 0); C(mz, "", hm, "A"); hm.set_editor_property("const_b", -1.0 / M["ring_step"])   # hundreds of metres
    n = E(unreal.MaterialExpressionRound, -1150, 0); C(hm, "", n, "")
    f5 = E(unreal.MaterialExpressionMultiply, -1000, 0); C(n, "", f5, "A"); f5.set_editor_property("const_b", 0.2)
    ad = E(unreal.MaterialExpressionAdd, -850, 0); C(f5, "", ad, "A"); ad.set_editor_property("const_b", 0.1)
    fr = E(unreal.MaterialExpressionFrac, -700, 0); C(ad, "", fr, "")
    five = E(unreal.MaterialExpressionIf, -500, 0)                                       # 1 on the 500 m marks
    C(fr, "", five, "A"); C(const(0.2, -700, 120), "", five, "B")
    zero, one = const(0.0, -700, 200), const(1.0, -700, 280)
    C(zero, "", five, "A > B"); C(zero, "", five, "A == B"); C(one, "", five, "A < B")
    col = E(unreal.MaterialExpressionLinearInterpolate, -250, -200)
    C(colour("ColorMark100", GREEN, -500, -400), "", col, "A"); C(colour("ColorMark500", CYAN, -500, -200), "", col, "B"); C(five, "", col, "Alpha")
    on = E(unreal.MaterialExpressionLinearInterpolate, -250, 150)
    C(one, "", on, "A"); C(five, "", on, "B"); C(scalar("StripB", 0.0, -500, 300), "", on, "Alpha")
    m1 = E(unreal.MaterialExpressionMultiply, -50, 0); C(col, "", m1, "A"); C(on, "", m1, "B")
    m2 = E(unreal.MaterialExpressionMultiply, 100, 0); C(m1, "", m2, "A"); C(scalar("Intensity", 6.0, -50, 200), "", m2, "B")
    MEL.connect_material_property(m2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(const(0.015, 100, -200), "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(const(0.7, 100, 300), "", unreal.MaterialProperty.MP_ROUGHNESS)
    for u in (unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, unreal.MaterialUsage.MATUSAGE_NANITE):
        MEL.set_material_usage(mat, u)
    MEL.recompile_material(mat); EAL.save_asset(MAT_RING, only_if_is_dirty=False)
    mi = AT.create_asset("MI_AOS_DepthRing_Second", DST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()); out["instance"] = "created"
    MEL.set_material_instance_parent(mi, mat); MEL.set_material_instance_scalar_parameter_value(mi, "StripB", 1.0)
    MEL.update_material_instance(mi); EAL.save_asset(MAT_RING2, only_if_is_dirty=False)
    out["expressions"] = MEL.get_num_material_expressions(mat)
    return out

# ------------------------------------------------------------------ import (same as the Spire kit)
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
    try: sd.set_editor_property("build_nanite", True)
    except Exception: pass
    t = unreal.AssetImportTask()
    t.filename, t.destination_path, t.destination_name = os.path.join(FBX_DIR, name + ".fbx"), DST, name
    t.automated, t.replace_existing, t.save, t.options = True, True, False, o
    # UE 5.7 routes FBX through Interchange, which ignores FbxImportUI and drops UCX_ hulls: force the legacy importer.
    CV = "Interchange.FeatureFlags.Import.FBX"
    prev = SL.get_console_variable_bool_value(CV)
    SL.execute_console_command(world(), CV + " 0")
    try:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    finally:
        SL.execute_console_command(world(), CV + (" 1" if prev else " 0"))
    return list(t.imported_object_paths)

def author(name):
    sm = unreal.load_asset(DST + "/" + name); sm.modify()
    mats = {"MS_Concrete": unreal.load_asset(MAT_CONCRETE), "MS_DepthRing": unreal.load_asset(MAT_RING), "MS_DepthRing2": unreal.load_asset(MAT_RING2)}
    slots = []
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name")); slots.append(sn)
        sm.set_material(i, mats.get(sn, mats["MS_Concrete"]))
    bs = sm.get_editor_property("body_setup")                      # bible §3.0.2: Use Simple Collision As Complex
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    lb = SMS.get_lod_build_settings(sm, 0)                          # bible §3.0.4: modules > 6 400 -> DF resolution scale 2.0
    lb.set_editor_property("distance_field_resolution_scale", 2.0)
    SMS.set_lod_build_settings(sm, 0, lb)
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    try: ns.set_editor_property("fallback_relative_error", 1.0)    # bible §3.0.2
    except Exception: pass
    SMS.set_nanite_settings(sm, ns, True)
    EAL.save_asset(DST + "/" + name, only_if_is_dirty=False)
    return slots

def asset_report(name):
    sm = unreal.load_asset(DST + "/" + name)
    if not sm: return {"missing": True}
    st = SPEC["meshes"][name]; bb = sm.get_bounding_box(); gmin, gmax = bb.min.to_tuple(), bb.max.to_tuple()
    bs = sm.get_editor_property("body_setup")
    return {"nanite": bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")),
            "convex": SMS.get_convex_collision_count(sm), "convex_expected": st["ucx"],
            "bounds_err_cm": round(max(max(abs(gmin[i] - st["ue_bbox_min"][i]), abs(gmax[i] - st["ue_bbox_max"][i])) for i in range(3)), 3),
            "tris_lod0": sm.get_num_triangles(0), "tris_expected": st["tris"],
            "trace_flag": str(bs.get_editor_property("collision_trace_flag")).split(".")[-1].split(":")[0],
            "materials": [[str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None]
                          for m in sm.get_editor_property("static_materials")]}

# ------------------------------------------------------------------ place
def tagged(): return [a for a in EAS.get_all_level_actors() if any(str(t) == TAG for t in a.tags)]

def dress(comp, scale=(1.0, 1.0, 1.0)):
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    comp.set_collision_profile_name("BlockAll")                    # bible §3.0.4: never BlockAllDynamic on architecture
    # M_AOS_Concrete_BoxMap: CPD 10-12 offset, 13-15 local -> texture scale (0 = flat colour). Scale folded in per axis.
    for i, v in ((10, 0.0), (11, 0.0), (12, 0.0), (13, BOXMAP_K * scale[0]), (14, BOXMAP_K * scale[1]), (15, BOXMAP_K * scale[2])):
        comp.set_default_custom_primitive_data_float(i, v)

def finish(a, label, folder, part):
    a.set_actor_label(label); a.set_folder_path(folder)
    a.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("AOS_Stage2_Part=" + part)])

def bare_actor(loc):
    a = EAS.spawn_actor_from_class(unreal.Actor, V(loc), unreal.Rotator(0, 0, 0))
    a.root_component.set_mobility(unreal.ComponentMobility.STATIC)   # DefaultSceneRoot is Movable by default and would force its children Movable
    return a

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
    with unreal.ScopedEditorTransaction("AOS Tower A stage 2: bed, A-3 hull, monoliths"):
        old = tagged()
        if old: EAS.destroy_actors(old); out["removed"] = len(old)
        # --- sector bed: one ISM actor on the slab grid
        e = ASM["bed"]
        a = bare_actor(e["loc"])
        c = add_comp(a, unreal.InstancedStaticMeshComponent, "Tiles"); c.set_static_mesh(meshes[e["mesh"]])
        dress(c); finish(a, e["label"], F_BED, "SectorBed")
        c.add_instances([unreal.Transform(location=unreal.Vector(p[0], p[1], p[2])) for p in e["instances_xyz"]], False, False)
        out["spawned"].append("%s x%d" % (e["label"], c.get_instance_count()))
        # --- Tower A-3 hull: one static mesh actor on cluster origin B
        e = ASM["hull"]
        a = EAS.spawn_actor_from_object(meshes[e["mesh"]], V(e["loc"]), unreal.Rotator(0, 0, 0))
        dress(a.static_mesh_component); finish(a, e["label"], F_A3, "TowerA3_Hull"); out["spawned"].append(e["label"])
        # --- 24 monolith axes: one actor per axis = crown + instanced stalactite + instanced stalagmite
        for e in ASM["monoliths"]:
            org = (e["xy"][0], e["xy"][1], 0.0)
            a = bare_actor(org)
            cr = add_comp(a, unreal.StaticMeshComponent, "Crown"); cr.set_static_mesh(meshes[e["crown"]["mesh"]])
            cr.set_relative_location(unreal.Vector(0, 0, e["crown"]["z"]), False, False); cr.set_relative_scale3d(V(e["crown"]["scale"])); dress(cr, e["crown"]["scale"])
            n = 1
            for key in ("stalactite", "stalagmite"):
                p = e[key]
                c = add_comp(a, unreal.InstancedStaticMeshComponent, key.capitalize()); c.set_static_mesh(meshes[p["mesh"]]); dress(c, p["scale"])
                c.add_instances([unreal.Transform(location=unreal.Vector(0, 0, z), rotation=unreal.Rotator(roll=p["roll"], pitch=0, yaw=0), scale=V(p["scale"])) for z in p["z"]], False, False)
                n += c.get_instance_count()
            finish(a, e["id"], FOLDER + "/" + e["ring"], e["id"]); out["spawned"].append("%s x%d" % (e["id"], n))
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
    return {"p": [round(t[4].x, 2), round(t[4].y, 2), round(t[4].z, 2)], "actor": lab}
def line(p0, p1, ign=()): return _hit(SL.line_trace_single_for_objects(world(), V(p0), V(p1), WS, False, WATER + list(ign), NONE, True))
def sph(p0, p1, r, ign=()): return _hit(SL.sphere_trace_single_for_objects(world(), V(p0), V(p1), float(r), WS, False, WATER + list(ign), NONE, True))
def box(p0, p1, he, rot=None, ign=()):
    return _hit(SL.box_trace_single_for_objects(world(), V(p0), V(p1), V(he), rot or unreal.Rotator(0, 0, 0), WS, False, WATER + list(ign), NONE, True))
def overlaps(b, ign=(), shrink=1.0):
    """Labels of WorldStatic actors whose collision overlaps the box b = (x0, x1, y0, y1, z0, z1), shrunk by 1 cm."""
    c = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2); h = ((b[1] - b[0]) / 2 - shrink, (b[3] - b[2]) / 2 - shrink, (b[5] - b[4]) / 2 - shrink)
    r = SL.box_overlap_actors(world(), V(c), V(h), WS, None, WATER + list(ign))
    if isinstance(r, tuple): r = r[0] if isinstance(r[0], (list, unreal.Array)) else r[-1]
    return sorted(set(a.get_actor_label() for a in (r or [])))
def cbounds(c):
    o, e, _ = SL.get_component_bounds(c)
    return (o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y, o.z - e.z, o.z + e.z)

def verify():
    C = []; R = SPEC["shell_r"]
    def chk(name, ok, value): C.append({"check": name, "pass": bool(ok), "value": value})
    acts = {a.get_actor_label(): a for a in tagged()}; mine = set(acts)
    by = {a.get_actor_label(): a for a in ALL}
    mono = ASM["monoliths"]
    exp = [ASM["bed"]["label"], ASM["hull"]["label"]] + [m["id"] for m in mono]
    chk("actor count (tag %s) = 26: bed 1 + hull 1 + monoliths 24" % TAG, len(acts) == len(exp) == 26 and all(l in acts for l in exp), "%d / %d" % (len(acts), len(exp)))
    fo = {l: str(a.get_folder_path()) for l, a in acts.items()}
    chk("Outliner folders (SectorBed, Tower_A3, Monoliths/R1..R3)", fo.get("SectorBed_Tiles") == F_BED and fo.get("TowerA3_Hull") == F_A3 and all(fo.get(m["id"]) == FOLDER + "/" + m["ring"] for m in mono),
        {r: sum(1 for m in mono if m["ring"] == r and fo.get(m["id"]) == FOLDER + "/" + r) for r in ("R1", "R2", "R3")})
    ar = {n: asset_report(n) for n in SPEC["meshes"]}
    want = {"MS_Concrete": "M_AOS_Concrete_BoxMap", "MS_DepthRing": "M_AOS_DepthRing", "MS_DepthRing2": "MI_AOS_DepthRing_Second"}
    chk("5 meshes: Nanite on, UCX count, bounds vs. spec, simple-as-complex, slot materials",
        all(v.get("nanite") and v["convex"] == v["convex_expected"] and v["bounds_err_cm"] < 0.1 and v["trace_flag"] == "CTF_USE_SIMPLE_AS_COMPLEX"
            and all(want.get(s) == mn for s, mn in v["materials"]) for v in ar.values()),
        {n: [v.get("convex"), v.get("bounds_err_cm"), [s for s, _ in v.get("materials", [])]] for n, v in ar.items()})
    stage2 = list(acts.values())
    profs = set(); ncomp = 0
    for a in stage2:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            profs.add((str(c.get_collision_profile_name()), str(c.mobility).split(".")[-1].split(":")[0], str(a.root_component.mobility).split(".")[-1].split(":")[0])); ncomp += 1
    chk("all 74 Stage 2 mesh components: BlockAll, Static, under a Static root", profs == {("BlockAll", "STATIC", "STATIC")} and ncomp == 74, [ncomp, sorted(profs)])

    # ============ 1. sector bed
    bed = acts.get("SectorBed_Tiles"); bc = bed.get_component_by_class(unreal.InstancedStaticMeshComponent) if bed else None
    chk("sector bed: 440 tile instances on the slab grid", bc and bc.get_instance_count() == len(ASM["bed"]["instances_xyz"]) == 440, bc.get_instance_count() if bc else None)
    bnd = [a for a in ALL if a.get_actor_label() == "BND_Floor"]
    pad = line((13500, 13500, M["bed"] + 3000), (13500, 13500, M["bed"] - 3000), bnd)
    cof = line((18000, 18000, M["bed"] + 3000), (18000, 18000, M["bed"] - 3000), bnd)
    tre = line((12000, 18000, M["bed"] + 3000), (12000, 18000, M["bed"] - 3000), bnd)
    chk("bed tile collision (BND_Floor ignored): pad top -160 000, coffer floor -160 200, trench floor -160 400",
        all(h and h["actor"] == "SectorBed_Tiles" for h in (pad, cof, tre)) and abs(pad["p"][2] - M["bed"]) < 0.05 and abs(cof["p"][2] - (M["bed"] - 200)) < 0.05 and abs(tre["p"][2] - (M["bed"] - 400)) < 0.05,
        [pad, cof, tre])
    b0 = line((16500, 4000, M["bed"] + 3000), (16500, 4000, M["bed"] - 3000))
    chk("bed top beside the A-0 plinth (trace down at r 17 000) = -160 000", b0 and abs(b0["p"][2] - M["bed"]) < 0.05, b0)
    pl = by.get("A0_Up_Plinth"); pb = cbounds(pl.static_mesh_component) if pl else None
    und = [[x, y, (lambda h: h["p"][2] if h else None)(line((x, y, M["bed"] + 100), (x, y, M["bed"] - 3000), bnd + ([pl] if pl else [])))] for x, y in ((0, 0), (9000, 9000), (12000, 3000), (-6000, 12000), (14000, 0))]
    chk("A-0 plinth (bottom -160 500) is seated in the bed: tile surface under it at -160 000 / -160 400, never below the plinth bottom",
        pb and abs(pb[4] - (M["bed"] - 500)) < 0.05 and all(u[2] is not None and u[2] >= M["bed"] - 400.05 for u in und), {"plinth_z": [pb[4], pb[5]] if pb else None, "under": und})
    far = line((252000, 12000, M["bed"] + 3000), (252000, 12000, M["bed"] - 3000))
    chk("bed continues outside the containment (BND_Floor ends at 152 000): tile hit at r 252 000", far and far["actor"] == "SectorBed_Tiles" and far["p"][2] <= M["bed"] + 0.05, far)

    # ============ 2. Tower A-3 hull
    hull = acts.get("TowerA3_Hull"); hc = hull.static_mesh_component if hull else None
    hb = cbounds(hc) if hc else None
    wantb = (A3["podium"][0], A3["podium"][1], A3["podium"][2], A3["podium"][3], M["slab_top"], A3["parapet"])
    chk("hull bounds = podium footprint x (-18 000 .. -4 800), pivot on cluster origin B", hb and max(abs(hb[i] - wantb[i]) for i in range(6)) < 0.1 and
        hull.get_actor_location().to_tuple() == tuple(A3["origin_b"]), [round(x, 1) for x in hb] if hb else None)
    slabtop = line((-50000, 23000, M["slab_top"] + 50), (-50000, 23000, M["slab_top"] - 800), [hull])
    chk("hull stands on the Kikutake slab: slab top under the podium = -18 000 = hull bottom", slabtop and slabtop["actor"] == "KikutakeSlab_Tiles" and abs(slabtop["p"][2] - hb[4]) < 0.05, slabtop)
    # --- keep-out volumes: no hull collision inside (box overlap against the hull's UCX bodies)
    keep = dict(A3["keep"])
    for n, b in A3["rooms"].items(): keep["room %s interior" % n] = (b[0] + 100, b[1] - 100, b[2] + 100, b[3] - 100, b[4] + 100, b[5] - 100)
    keep["portal void (R1 west wall -> 20 m outside)"] = (A3["shaft"][0] - 2000, A3["rooms"]["R1"][0], A3["portal_yz"][0], A3["portal_yz"][1], A3["portal_yz"][2], A3["portal_yz"][3])
    keep["slot void (R6 north wall -> 20 m outside)"] = (A3["slot_xz"][0], A3["slot_xz"][1], A3["rooms"]["R6"][3], A3["shaft"][3] + 2000, A3["slot_xz"][2], A3["slot_xz"][3])
    bad = {n: True for n, b in keep.items() if "TowerA3_Hull" in overlaps(b)}
    chk("hull collision is absent from %d keep-out volumes (8 room interiors, SomaLock, TP-B parts + exit lane, Reaper nav bounds + arena column, both cuts)" % len(keep), not bad, sorted(bad) or "0 overlaps")
    ctrl = overlaps((A3["shaft"][0], A3["shaft"][0] + 400, 24500, 26000, -9000, -8000))
    chk("control: the same overlap test does see the hull inside its west wall", "TowerA3_Hull" in ctrl, ctrl)
    # --- C-01 SomaLock entry
    lock = by.get("PRT_SomaLock_Main"); tp = by.get("TP_Station_B_TowerA_C01")
    lc = lock.static_mesh_component; nin = lc.get_socket_location("SOCKET_Nav_In"); nout = lc.get_socket_location("SOCKET_Nav_Out")
    ex = [c for c in tp.get_components_by_class(unreal.SceneComponent) if c.get_name() == "ExitPoint"][0].get_world_location()
    p_ex, p_in, p_out = (ex.x, ex.y, ex.z), (nin.x, nin.y, nin.z), (nout.x, nout.y, nout.z)
    s1 = [sph(p_ex, p_in, R), box(p_ex, p_in, (200, 100, 100)), sph(p_ex, p_in, 400.0)]
    chk("TP-B ExitPoint -> SomaLock SOCKET_Nav_In: Shell sphere R245, Shell box 400x200x200 and swarm sphere R400 all clear", not any(s1), s1)
    s2 = [sph(p_in, p_out, R), box(p_in, p_out, (200, 100, 100))]; s2i = [sph(p_in, p_out, R, [hull]), box(p_in, p_out, (200, 100, 100), None, [hull])]
    chk("SomaLock SOCKET_Nav_In -> SOCKET_Nav_Out (through the lens into R1): result identical with and without the hull, hull never hit",
        s2 == s2i and not any(h and h["actor"] == "TowerA3_Hull" for h in s2), {"with_hull": s2, "hull_ignored": s2i})
    fwd = line((ex.x - 1500, ex.y, ex.z), (ex.x + 6000, ex.y, ex.z)); side = line((ex.x, A3["portal_yz"][1] - 300, ex.z), (ex.x + 3000, A3["portal_yz"][1] - 300, ex.z))
    chk("line of sight east from the station: on the lens axis it runs through the lock into R1; 300 inside the portal's north jamb it lands on the R1 west wall (X -53 600), never on the hull",
        fwd and fwd["actor"] not in mine and fwd["p"][0] > A3["rooms"]["R1"][0] and side and side["actor"].startswith("SHELL_R1_WallW") and abs(side["p"][0] - A3["rooms"]["R1"][0]) < 0.5, [fwd, side])
    rim = []
    for y in (A3["portal_yz"][0] + 260, A3["portal_yz"][1] - 260):
        for z in (A3["portal_yz"][2] + 260, A3["portal_yz"][3] - 260):
            rim.append(sph((A3["shaft"][0] - 1200, y, z), (A3["rooms"]["R1"][0] - 260, y, z), R))
    chk("portal 3 200 x 1 350 is open over its whole section: Shell sphere along all 4 corners, 0 hull hits (N corners reach the R1 wall plane, S corners stop on the lock's own door pocket)",
        not any(h and h["actor"] in mine for h in rim) and rim[2] is None and rim[3] is None and all(h is None or h["actor"] == "PRT_SomaLock_Main" for h in rim[:2]), rim)
    # --- teleport station B
    tb = {c.get_name(): cbounds(c) for c in tp.get_components_by_class(unreal.PrimitiveComponent) if c.get_name() in ("PortalFrame", "ShaftMesh", "EntranceTrigger")}
    tov = {n: overlaps(b) for n, b in tb.items()}
    quay = line((ex.x, ex.y, ex.z), (ex.x, ex.y, ex.z - 3000)); under = line((-58600, 22362, -9605), (-58600, 22362, -12000))
    chk("TP_Station_B: PortalFrame / ShaftMesh / EntranceTrigger volumes free of Stage 2 collision", all(not (set(v) & mine) for v in tov.values()) and len(tb) == 3, tov)
    chk("TP_Station_B hovers over the west quay: deck -9 960 is 810 below the ExitPoint and 355 below the transit shaft", quay and quay["actor"] == "TowerA3_Hull" and abs(quay["p"][2] - A3["podium_top"]) < 0.05
        and under and abs(under["p"][2] - A3["podium_top"]) < 0.05, [quay, under])
    appr = [sph((ex.x - 1000, ex.y, ex.z + 3000), (ex.x - 1000, ex.y, ex.z), R), sph((-62500, 22362, -9150), (-59900, 22362, -9150), R), sph((ex.x, 16500, ex.z), (ex.x, 21300, ex.z), R), sph((ex.x, 30500, ex.z), (ex.x, 23000, ex.z), R)]
    chk("station approaches open: from above, from the west along the shaft axis, from the south and north over the quay (Shell sphere, no Stage 2 hit)", not any(h and h["actor"] in mine for h in appr), appr)
    # --- R6 north exit
    sx = (A3["slot_xz"][0] + A3["slot_xz"][1]) / 2; sz = (A3["slot_xz"][2] + A3["slot_xz"][3]) / 2; y6 = A3["rooms"]["R6"][3]; yn = A3["shaft"][3]
    s3 = [sph((sx, yn + 2500, sz), (sx, y6 + R + 5, sz), R), box((sx, yn + 2500, sz), (sx, y6 + 205, sz), (200, 100, 100), unreal.Rotator(roll=0, pitch=0, yaw=90)),
          box((sx, yn + 2500, sz), (sx, y6 + 105, sz), (700, 100, 250))]
    wall6 = line((sx, yn + 2500, sz), (sx, y6 - 300, sz))
    chk("R6 north exit: slot 1 500 x 600 clear from open water to the R6 wall (Shell sphere, Shell box, 1 400 x 500 gauge)", not any(s3), s3)
    chk("the slot ends exactly on the north wall of A03_R6 (Y 25 400), i.e. a DispatchWindow cut there opens to the outside", wall6 and wall6["actor"] == "SHELL_R6_WallN_00" and abs(wall6["p"][1] - y6) < 0.5, wall6)
    c6 = [sph((sx, yn + 800, sz), (sx + 1400, yn + 800, sz - 900), R), line((A3["slot_xz"][0] - 300, yn + 500, sz), (A3["slot_xz"][0] - 300, yn - 500, sz))]
    chk("control: hull blocks beside the slot (line 300 west of it hits the north face Y 27 800)", c6[1] and c6[1]["actor"] == "TowerA3_Hull" and abs(c6[1]["p"][1] - yn) < 0.05, c6[1])
    # --- route through the cluster stays as it was (hull ignored vs. present)
    Bx, By, Bz = A3["origin_b"]
    route = [(p_out, (-52800, 21876, -9150)), ((-52800, 21876, -9150), (-52300, 23000, -9300)), ((-50000, 23000, -9300), (-50000, 23000, -5800)), ((-48700, 23000, -5800), (-46800, 23000, -5800)),
             ((-46800, 24300, -5900), (-46800, 25000, -5900))]
    rr = [[sph(a, b, R), sph(a, b, R, [hull])] for a, b in route]
    chk("inside C-01 (R1, R2 atrium, R5, R6): 5 Shell sweeps give the same result with the hull present and ignored", all(a == b and not (a and a["actor"] == "TowerA3_Hull") for a, b in rr), [a for a, b in rr])
    # --- Reaper arena + NavMesh
    nb = by.get("RPR_Arena_NavBounds"); nbb = cbounds(nb.get_component_by_class(unreal.BrushComponent)) if nb else None
    fl = by.get("RPR_Arena_Floor"); flb = cbounds(fl.static_mesh_component) if fl else None
    col = (flb[0], flb[1], flb[2], flb[3], flb[5], 0.0) if flb else None
    ov = {"nav bounds": [l for l in overlaps(nbb) if l in mine], "arena column to the surface": [l for l in overlaps(col) if l in mine]}
    chk("Reaper arena: no Stage 2 collision in the NavMeshBoundsVolume or in the column above the floor", nbb and col and not ov["nav bounds"] and not ov["arena column to the surface"],
        {"nav_bounds": [round(x) for x in nbb] if nbb else None, "overlaps": ov})
    gaps = {"hull east face -> nav bounds (X)": round(nbb[0] - A3["shaft"][1], 1), "terrace top -> nav bounds bottom (Z)": round(nbb[4] - A3["podium_top"], 1), "bay face -> arena floor edge (X)": round(flb[0] - A3["bay_x"], 1)}
    chk("clearances: east face 100 west of the nav bounds, terrace 10 below them, bay face flush with the floor edge (0, no overhang)", gaps["hull east face -> nav bounds (X)"] >= 100 and gaps["terrace top -> nav bounds bottom (Z)"] >= 10 and gaps["bay face -> arena floor edge (X)"] >= 0, gaps)
    sw = []
    for y in (20300, 21200, 22000, 22900, 23700):
        for z in (-9500, -9100, -7000, -5600):
            h = sph((flb[0] + 260, y, z), (flb[1] - 260, y, z), R)
            if h and h["actor"] in mine: sw.append([y, z, h])
    for x in (-45200, -44000, -43500, -42500, -41800):
        for y in (20300, 22000, 23700):
            h = sph((x, y, -1500), (x, y, -9300), R)
            if h and h["actor"] in mine: sw.append([x, y, h])
    for a, b in (((-38000, 22000, -9400), (-41800, 22000, -9400)), ((-43500, 16500, -9400), (-43500, 20400, -9400)), ((-43500, 30000, -9400), (-43500, 23600, -9400)), ((-43500, 22000, 0), (-43500, 22000, -9300))):
        h = sph(a, b, R)
        if h and h["actor"] in mine: sw.append([a, b, h])
    chk("Reaper arena open to the water: 20 crossings W-E at 4 heights, 15 descents from -15 m, entries from E / S / N / above (Shell sphere, 0 Stage 2 hits)", not sw, sw or "0 hits")
    under_a = line((-43500, 22000, -9905), (-43500, 22000, -12000)); wface = line((-45300, 22000, -9000), (-47000, 22000, -9000))
    chk("arena sits over the east terrace (-9 960, 60 under the floor slab) and beside the east face X -45 800", under_a and under_a["actor"] == "TowerA3_Hull" and abs(under_a["p"][2] - A3["podium_top"]) < 0.05
        and wface and wface["actor"] == "TowerA3_Hull" and abs(wface["p"][0] - A3["shaft"][1]) < 0.05, [under_a, wface])
    nav = None
    try:
        base = json.load(open(os.path.join(OUT_DIR, "navmesh_baseline.json")))
        rn = [a for a in ALL if a.get_class().get_name() == "RecastNavMesh"][0]; rows = []; zs = set()
        for i in range(len(base["rows"])):
            row = ""
            for j in range(len(base["rows"][0])):
                p = unreal.NavigationSystemV1.project_point_to_navigation(world(), unreal.Vector(base["x0"] + base["step"] * i, base["y0"] + base["step"] * j, base["z"]), rn, None, unreal.Vector(5, 5, 400))
                row += "1" if p is not None else "0"
                if p is not None: zs.add(round(p.z, 1))
            rows.append(row)
        nav = {"baseline_points_on_navmesh": base["on"], "now": sum(r.count("1") for r in rows), "cells_changed": sum(1 for a, b in zip(rows, base["rows"]) for x, y in zip(a, b) if x != y), "z": sorted(zs), "baseline_z": base["zs"]}
    except Exception as ex_: nav = {"error": str(ex_)}
    chk("Reaper NavMesh identical to the pre-build baseline (2 401 sample points, 100 cm grid)", nav.get("cells_changed") == 0 and nav.get("now") == nav.get("baseline_points_on_navmesh") and nav.get("z") == nav.get("baseline_z"), nav)

    # ============ 3. monoliths
    comp = {}
    for m in mono:
        a = acts.get(m["id"])
        if not a: continue
        d = {}
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            nm = c.static_mesh.get_name()
            key = "crown" if nm == "SM_Monolith_Crown" else ("stalagmite" if any(abs(c.get_instance_transform(0, True).rotation.rotator().roll) > 90 for _ in [0]) else "stalactite")
            d[key] = c
        comp[m["id"]] = d
    okc = []; okz = []; okx = []
    for m in mono:
        d = comp.get(m["id"], {}); a = acts.get(m["id"])
        if len(d) != 3: okc.append(m["id"]); continue
        if d["stalactite"].get_instance_count() != len(m["stalactite"]["z"]) or d["stalagmite"].get_instance_count() != len(m["stalagmite"]["z"]): okc.append(m["id"])
        if d["stalactite"].static_mesh.get_name() != m["stalactite"]["mesh"] or d["stalagmite"].static_mesh.get_name() != m["stalagmite"]["mesh"]: okc.append(m["id"])
        cb, tb_, gb = cbounds(d["crown"]), cbounds(d["stalactite"]), cbounds(d["stalagmite"])
        z = [cb[4] - M["slab_top"], cb[5] - m["crown"]["roof"], tb_[5] - M["slab_bot"], tb_[4] - m["stalactite"]["tip"], gb[5] - m["stalagmite"]["top"], gb[4] - m["stalagmite"]["base"]]
        if max(abs(v) for v in z) > 0.05: okz.append([m["id"], [round(v, 2) for v in z]])
        l = a.get_actor_location()
        sz = [cb[1] - cb[0] - m["crown"]["size"][0] * 6500.0 / 6000.0, cb[3] - cb[2] - m["crown"]["size"][1] * 6500.0 / 6000.0, tb_[1] - tb_[0] - m["stalactite"]["af"], gb[1] - gb[0] - m["stalagmite"]["af"]]
        if abs(l.x - m["xy"][0]) > 0.01 or abs(l.y - m["xy"][1]) > 0.01 or max(abs(v) for v in sz) > 0.5 or any(abs((b_[0] + b_[1]) / 2 - l.x) > 0.05 or abs((b_[2] + b_[3]) / 2 - l.y) > 0.05 for b_ in (cb, tb_, gb)):
            okx.append([m["id"], [round(v, 2) for v in sz]])
    ni = {k: sum(comp[m["id"]][k].get_instance_count() for m in mono if k in comp.get(m["id"], {})) for k in ("stalactite", "stalagmite")}
    chk("24 axes x (crown + instanced stalactite + instanced stalagmite): meshes and instance counts per the assembly table", not okc and len(comp) == 24, {"bad": okc, "instances": ni, "crowns": len(comp)})
    chk("monolith Z marks: crown -18 000 .. -800, stalactite -23 000 .. tip, stalagmite top .. base (max error 0.05 cm)", not okz, okz or "24 / 24")
    chk("monolith axes on their lattice points, parts concentric, plan sizes = table (crown plinth, stalactite AF, stalagmite AF)", not okx, okx or "24 / 24")
    rk = {r: sorted(m["id"] for m in mono if m["ring"] == r) for r in ("R1", "R2", "R3")}
    rad = [m["id"] for m in mono if not ({"R1": 40000, "R2": 90000, "R3": 150000}[m["ring"]] <= math.hypot(*m["xy"]) <= {"R1": 70000, "R2": 150000, "R3": 300000}[m["ring"]])]
    chk("rings per bible 1.4: R1 = M-01..05 (r 40-70 k), R2 = M-06..17 (r 90-150 k), R3 = M-18..24 (r 150-300 k)", not rad and [len(rk[r]) for r in ("R1", "R2", "R3")] == [5, 12, 7], {r: len(v) for r, v in rk.items()})
    tipz = [m["id"] for m in mono if not (-98000 <= m["stalactite"]["tip"] <= -50000 and -98000 <= m["stalagmite"]["top"] <= -82000 and m["junction_gap"] > 0)]
    chk("stalactite tips in -50 000 .. -98 000, stalagmite tops in the junction band -82 000 .. -98 000, tip above top", not tipz, {"paired (gap 4 000)": sum(1 for m in mono if m["junction_gap"] == 4000), "short stalactite": sum(1 for m in mono if m["junction_gap"] > 4000)})
    rz = [z for m in mono for z in m["rings_z"]]
    chk("depth rings: every ring recess sits on a 100 m mark (342 rings; double Cyan at -500 / -1 000 / -1 500 m)", all(abs(z / M["ring_step"] - round(z / M["ring_step"])) < 1e-9 for z in rz) and len(rz) == 342,
        {"rings": len(rz), "cyan_double": sum(1 for z in rz if round(-z / M["ring_step"]) % 5 == 0), "green": sum(1 for z in rz if round(-z / M["ring_step"]) % 5 != 0)})
    # ring geometry + collision on one square and one octagonal axis
    fac = []
    for mid in ("M-01", "M-06"):
        m = [x for x in mono if x["id"] == mid][0]; x0, y0 = m["xy"]
        for key in ("stalactite", "stalagmite"):
            p = m[key]; zc = (p["z"][0] - 5000) if key == "stalactite" else (p["z"][0] + 5000)
            h = line((x0 + 20000, y0, zc), (x0, y0, zc)); fac.append([mid, key, round(h["p"][0] - x0 - p["af"] / 2, 2) if h else None, h["actor"] if h else None])
        h = line((x0 + 20000, y0, -10000), (x0, y0, -10000)); fac.append([mid, "crown", round(h["p"][0] - x0 - m["crown"]["size"][0] / 2, 2) if h else None, h["actor"] if h else None])
    chk("facade collision at the expected half-width (trace to the axis): M-01 (square) and M-06 (octagon), stalactite / stalagmite / crown", all(f[2] is not None and abs(f[2]) < 0.05 and f[3] == f[0] for f in fac), fac)
    m1 = [x for x in mono if x["id"] == "M-01"][0]; jx = m1["xy"][0] + 9000; jy = m1["xy"][1]; zj = (m1["stalactite"]["tip"] + m1["stalagmite"]["top"]) / 2
    jg = [sph((jx, jy, zj), (m1["xy"][0] - 9000, jy, zj), R), sph((jx, jy, zj), (m1["xy"][0] - 9000, jy, zj), 1950.0), sph((jx, jy, zj), (m1["xy"][0] - 9000, jy, zj), 2050.0)]
    chk("junction gap of a paired axis (M-01, -93 000 / -97 000): Shell and R1950 sphere cross, R2050 does not", jg[0] is None and jg[1] is None and jg[2] is not None, jg)
    # contact with slab and bed
    con = []
    for m in mono:
        x0, y0 = m["xy"]; d = comp[m["id"]]
        o1 = [l for l in overlaps(cbounds(d["crown"])) if l not in mine]; o2 = [l for l in overlaps(cbounds(d["stalactite"])) if l not in mine]
        o3 = [l for l in overlaps(cbounds(d["stalagmite"])) if l not in mine and l != "BND_Floor"]
        up = line((x0, y0, M["slab_bot"] - 200), (x0, y0, M["slab_bot"] + 2000), [acts[m["id"]]]); dn = line((x0, y0, M["slab_top"] + 200), (x0, y0, M["slab_top"] - 2000), [acts[m["id"]]])
        okk = up and dn and up["actor"] == "KikutakeSlab_Tiles" and dn["actor"] == "KikutakeSlab_Tiles" and abs(dn["p"][2] - M["slab_top"]) < 0.05 and up["p"][2] <= M["slab_bot"] + 800.05
        if o1 or o2 or o3 or not okk: con.append([m["id"], o1, o2, o3, up, dn])
    chk("every axis: crown seated on the slab top, stalactite hung from solid slab (no oculus), 1 cm-shrunk part bounds overlap no pre-existing actor (stalagmite: only the bed volume)", not con, con or "24 / 24")
    # pairwise + rules
    def half(m): return max(m["stalagmite"]["af"] / 2 / math.cos(math.pi / 8), m["stalactite"]["af"] / 2 * (math.sqrt(2) if "Square" in m["stalactite"]["mesh"] else 1 / math.cos(math.pi / 8)), math.hypot(*m["crown"]["size"]) / 2 * 6500.0 / 6000.0)
    gmin = min(math.hypot(a["xy"][0] - b["xy"][0], a["xy"][1] - b["xy"][1]) - half(a) - half(b) for i, a in enumerate(mono) for b in mono[i + 1:])
    pod = A3["podium"]
    ga3 = min(math.hypot(max(pod[0] - m["xy"][0], 0, m["xy"][0] - pod[1]), max(pod[2] - m["xy"][1], 0, m["xy"][1] - pod[3])) - half(m) for m in mono)
    ggu = min((abs(m["xy"][1]) if m["xy"][0] < 0 else math.hypot(*m["xy"])) - half(m) for m in mono)
    chk("placement rules: surface gap monolith-monolith >= 15 000, monolith - Tower A-3 >= 15 000, >= 6 000 from the az 180 guardian radial", gmin >= 15000 and ga3 >= 15000 and ggu >= 6000,
        {"min monolith-monolith": round(gmin), "min monolith - A-3 podium": round(ga3), "min to az 180 radial": round(ggu)})

    # ============ 4. zero overlap with Spire A-0, slab, D-1 and everything else that was already in the level
    pre = {}
    for a in ALL:
        f = str(a.get_folder_path())
        if a.get_actor_label() in mine: continue
        if f.startswith("Environment/Macro/Spire_A0") or f.startswith("Environment/Macro/Conduits_D1"): pre[a.get_actor_label()] = a
    hit = {}
    for l, a in acts.items():
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            if l == "SectorBed_Tiles": continue
            for o in overlaps(cbounds(c)):
                if o in pre: hit.setdefault(l, set()).add(o)
    plb = overlaps((-15000, 15000, -15000, 15000, M["bed"] - 1990, M["bed"] - 410))            # bed plate volume under the plinth footprint
    chk("zero overlap: 25 Stage 2 actors vs. %d Spire A-0 / Kikutake slab / D-1 actors (1 cm-shrunk bounds against their collision)" % len(pre), not hit and len(pre) >= 31, {k: sorted(v) for k, v in hit.items()} or "0 overlaps")
    chk("sector bed vs. Spire A-0: only the plinth (designed to be embedded 500) touches the bed plate", [o for o in plb if o in pre] in ([], ["A0_Up_Plinth"]), [o for o in plb if o in pre])
    d1 = by.get("D1_Seg_06"); d1b = cbounds(d1.static_mesh_component) if d1 else None
    lane = sph((d1b[1] + 30000, 0, -90000 + 2784), (d1b[1] - 2500, 0, -90000 + 2784), R) if d1b else "missing"
    chk("D-1 terminus (X 60 000) stays open: Shell sphere from 300 m east along the 12 o'clock lane into the conduit, no Stage 2 hit", not (lane and lane != "missing" and lane["actor"] in mine),
        {"sweep": lane, "nearest_monolith_surface_to_D1_cm": round(min(math.hypot(max(24000 - m["xy"][0], 0, m["xy"][0] - 60000), max(abs(m["xy"][1]) - 4400, 0)) - half(m) for m in mono))})
    oth = {}
    skip = ("Environment/Macro/Spire_A0", "Environment/Macro/Conduits_D1", "Environment/Clusters/C01_Home_A03", "Environment/Enemies/Reaper", "Environment/Teleport")
    for l, a in acts.items():
        if l in ("SectorBed_Tiles", "TowerA3_Hull"): continue
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            for o in overlaps(cbounds(c)):
                if o in mine or o in pre or o == "BND_Floor": continue
                oth.setdefault(l, set()).add(o)
    chk("monoliths touch nothing else in the level (containment walls, surface set, anchors, interactables)", not oth, {k: sorted(v) for k, v in oth.items()} or "0 overlaps")
    return {"ok": all(c["pass"] for c in C), "passed": sum(1 for c in C if c["pass"]), "total": len(C), "checks": C, "assets": ar,
            "level_actors": len(ALL), "stage2_actors": len(acts)}

# ------------------------------------------------------------------ capture (editor SceneCapture2D; fog + underwater PP off, temporary fill light)
VIEWS = {
    "01_A3_west_portal_TPB":   dict(cam=(-63500, 14500, -6800), at=(-52000, 23500, -10200), fov=60),
    "02_A3_portal_closeup":    dict(cam=(-57600, 20300, -8700), at=(-53600, 22200, -9150), fov=60),
    "03_A3_east_arena_bay":    dict(cam=(-35500, 13000, -5600), at=(-46500, 23500, -9000), fov=60),
    "04_A3_north_slot":        dict(cam=(-44500, 33500, -4200), at=(-47500, 27800, -6400), fov=55),
    "05_A3_from_above_SW":     dict(cam=(-66000, 9000, -1200), at=(-50000, 23500, -10500), fov=60),
    "06_bed_plinth":           dict(cam=(52000, -38000, -146000), at=(0, 0, -158000), fov=60),
    "07_bed_trenches":         dict(cam=(30000, 9000, -157500), at=(0, 0, -159500), fov=70),
    "08_monolith_elevation_S": dict(cam=(0, -620000, -80000), at=(0, 0, -80000), fov=48),                   # whole 1.6 km column, long lens
    "09_down_from_under_slab": dict(cam=(30000, -30000, -24500), at=(30000, -29990, -160000), fov=110),       # R1 / R2 stalactites and stalagmites over the bed
    "10_junction_M01":         dict(cam=(92000, -6000, -90000), at=(60000, 24000, -95000), fov=50),
    "11_R1_from_A0_500m":      dict(cam=(9000, 5000, -50000), at=(60000, 0, -50000), fov=75),
    "12_stalactites_under_slab": dict(cam=(20000, -20000, -60000), at=(60000, 24000, -23000), fov=75),
    "13_crowns_over_slab":     dict(cam=(-20000, -30000, -2500), at=(-48000, 22000, -12000), fov=70),
    "14_M06_rings_closeup":    dict(cam=(140000, -22000, -44000), at=(120000, 0, -50000), fov=45),
    "15_M06_ring_500m_detail": dict(cam=(123500, -9500, -49300), at=(120000, -4500, -49850), fov=40),
}
def capture():
    """One fresh render target + SceneCapture2D per shot (a reused target is read back one capture late)."""
    os.makedirs(OUT_DIR, exist_ok=True); w = world(); out = []; tmp = []
    for i, (pitch, yaw, lux) in enumerate(((-38, -125, 10.0), (-18, 70, 4.0), (48, 160, 2.5))):          # key, fill, up-light for undersides; shadowless
        sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 0), unreal.Rotator(roll=0, pitch=pitch, yaw=yaw)); sun.set_actor_label("TMP_MonoCap_Light%d" % i)
        lc = sun.get_component_by_class(unreal.DirectionalLightComponent); lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        lc.set_intensity(lux); lc.set_cast_shadows(False); tmp.append(sun)
    try:
        for name, v in VIEWS.items():
            if SHOTS and not any(name.startswith(s) for s in SHOTS): continue
            rt_ = unreal.RenderingLibrary.create_render_target2d(w, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8)
            cam, at = V(v["cam"]), V(v["at"]); rot = unreal.MathLibrary.find_look_at_rotation(cam, at)
            cap = EAS.spawn_actor_from_class(unreal.SceneCapture2D, cam, rot); cap.set_actor_label("TMP_MonoCap_Cam"); tmp.append(cap)
            cc = cap.capture_component2d
            cc.texture_target = rt_; cc.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
            cc.set_editor_property("capture_every_frame", False); cc.set_editor_property("capture_on_movement", False)
            cc.set_editor_property("show_flag_settings", [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in ("Fog", "VolumetricFog", "PostProcessMaterial", "Atmosphere", "Cloud")])
            pp = unreal.PostProcessSettings()
            for k_, v_ in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL), ("override_auto_exposure_bias", True), ("auto_exposure_bias", float(v.get("ev", 0.0))),
                           ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", False)):
                pp.set_editor_property(k_, v_)
            cc.set_editor_property("post_process_settings", pp); cc.set_editor_property("post_process_blend_weight", 1.0)
            cc.set_editor_property("projection_type", unreal.CameraProjectionMode.PERSPECTIVE); cc.set_editor_property("fov_angle", float(v["fov"]))   # ortho captures come out black here
            cc.capture_scene(); cc.capture_scene()
            p = os.path.join(OUT_DIR, name + ".png")
            if os.path.exists(p): os.remove(p)
            unreal.RenderingLibrary.export_render_target(w, rt_, OUT_DIR, name + ".png")
            out.append([name, os.path.exists(p)])
    finally:
        for t in tmp: EAS.destroy_actor(t)
    return {"dir": OUT_DIR, "shots": out, "temp_actors_left": [a.get_actor_label() for a in EAS.get_all_level_actors() if a.get_actor_label().startswith("TMP_MonoCap")]}

def save():
    U = unreal.EditorLoadingAndSavingUtils
    n_map = [p.get_name() for p in U.get_dirty_map_packages()]; n_content = [p.get_name() for p in U.get_dirty_content_packages()]
    ok = U.save_dirty_packages(True, True)
    return {"saved": bool(ok), "map_packages": len(n_map), "map_sample": n_map[:6], "content_packages": n_content,
            "dirty_after": len(U.get_dirty_map_packages()) + len(U.get_dirty_content_packages())}

if MODE == "materials": result = materials()
elif MODE == "import":
    out = {}
    for n in (ONLY or list(SPEC["meshes"])):
        out[n] = {"imported": import_fbx(n), "slots": author(n), "report": asset_report(n)}
    result = out
elif MODE == "place": result = place()
elif MODE == "verify": result = verify()
elif MODE == "capture": result = capture()
elif MODE == "save": result = save()
else: result = {"error": "unknown mode " + str(MODE)}
