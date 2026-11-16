# AOS-DK | Pontoon Atoll Stage 2A: Outer Damping Breakwater Ring (BW): import 6 kit meshes, materials, assemble the ring, verify | UE 5.7.4
# Imports the FBX kit authored by Tools/max_build_Breakwater_Kit.py and assembles the perimeter in Lvl_FirstPerson.
# Single source of truth: Tools/Breakwater_Kit_spec.json (mesh stats, new slots, assembly table: ring, pipes, mooring lines, exclusion volumes).
# Standards = Tools/ue_build_Atoll_City.py: legacy FBX importer (Interchange.FeatureFlags.Import.FBX 0 during import, restored), UCX only,
# CTF_USE_DEFAULT, Nanite on, BlockAll, root component Static BEFORE the ISM component is attached.
# MODE: "materials" | "import" | "author" (re-apply slots / collision flag / Nanite settings without re-import) | "place" | "verify" (read-only traces / sweeps / overlaps) | "capture" (SceneCapture2D) | "save"
# Idempotent: every placed actor carries tag AOS_Atoll_Breakwater; "place" removes only those first. No C++, no water material edits.
# Run: g={"BW_MODE":"verify"}; exec(open(<proj>/Tools/ue_build_Breakwater.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math

MODE = globals().get("BW_MODE", "verify")
SHOTS = globals().get("BW_SHOTS", None)
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SPEC = json.load(open(os.path.join(PROJ, "Tools/Breakwater_Kit_spec.json"), encoding="utf-8"))
DST, MATDIR, ASM = SPEC["content"], SPEC["materials"], SPEC["assembly"]
TAG, CITY_TAG = "AOS_Atoll_Breakwater", "AOS_Atoll_City"
FBX_DIR = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/Atoll/Breakwater")
OUT_DIR = os.path.join(PROJ, "Saved", "Breakwater_Verify")
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
C = ASM["center"]; APO = ASM["apothem"]; Z = ASM["z"]
SHELL_R = 244.94897427831782                        # Shell-1 bounding sphere (Monoliths / Atoll spec)
SHELL_BOX = (330.0, 140.0, 177.0)                   # Shell-1 mesh box half extents, long axis = heading
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SMS = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
MEL = unreal.MaterialEditingLibrary
SL = unreal.SystemLibrary
CV_FBX = "Interchange.FeatureFlags.Import.FBX"

def world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
def V(t): return unreal.Vector(float(t[0]), float(t[1]), float(t[2]))
def pol(r, az, z=0.0): return (C[0] + r * math.cos(math.radians(az)), C[1] + r * math.sin(math.radians(az)), z)
def srgb_lin(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
def slot_mi(slot): return "MI_Atoll_" + slot[3:]

# ------------------------------------------------------------------ materials: 5 new instances of M_Atoll_Master (the Atoll palette MIs already exist)
def materials():
    out = {"created": [], "updated": []}
    AT = unreal.AssetToolsHelpers.get_asset_tools(); pm = unreal.load_asset(MATDIR + "/M_Atoll_Master")
    if not pm: raise RuntimeError("M_Atoll_Master missing: run ue_build_Atoll_City.py materials first")
    for slot, d in SPEC["new_slots"].items():
        name = slot_mi(slot); p = MATDIR + "/" + name
        if EAL.does_asset_exist(p): mi = unreal.load_asset(p); out["updated"].append(name)
        else: mi = AT.create_asset(name, MATDIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()); out["created"].append(name)
        MEL.set_material_instance_parent(mi, pm)
        MEL.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(srgb_lin(d["rgb"][0]), srgb_lin(d["rgb"][1]), srgb_lin(d["rgb"][2]), 1.0))
        MEL.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(0, 0, 0, 1))
        for k, v in (("Metallic", d["metallic"]), ("Roughness", d["roughness"]), ("EmissiveIntensity", 0.0)): MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
        MEL.update_material_instance(mi); EAL.save_asset(p, only_if_is_dirty=False)
    return out

# ------------------------------------------------------------------ import (legacy FBX importer keeps the UCX_ hulls)
def import_fbx(name):
    o = unreal.FbxImportUI()
    o.import_mesh = True; o.import_as_skeletal = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    o.import_animations = False; o.import_materials = False; o.import_textures = False
    sd = o.static_mesh_import_data
    sd.set_editor_property("combine_meshes", True)
    sd.set_editor_property("auto_generate_collision", False)
    sd.set_editor_property("one_convex_hull_per_ucx", True)
    sd.set_editor_property("generate_lightmap_u_vs", False)
    try: sd.set_editor_property("build_nanite", True)
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
    sm = unreal.load_asset(DST + "/" + name); sm.modify()
    slots, unmapped = [], []
    for i, sme in enumerate(sm.get_editor_property("static_materials")):
        sn = str(sme.get_editor_property("material_slot_name")); slots.append(sn)
        mi = unreal.load_asset(MATDIR + "/" + slot_mi(sn))
        if not mi: unmapped.append(sn); mi = unreal.load_asset(MATDIR + "/MI_Atoll_Trim")
        sm.set_material(i, mi)
    bs = sm.get_editor_property("body_setup")
    if bs: bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_DEFAULT)
    ns = sm.get_editor_property("nanite_settings"); ns.set_editor_property("enabled", True)
    # exact fallback mesh: the default auto fallback (relative error 1.0) decimates the thin plates (hatch lids, strakes, slats) into wedges wherever the fallback is drawn
    # (SceneCapture2D verification shots, hardware ray tracing, non-Nanite platforms). The kit is 576 .. 5 036 triangles per mesh, so the full mesh is kept.
    ns.set_editor_property("fallback_target", unreal.NaniteFallbackTarget.RELATIVE_ERROR); ns.set_editor_property("fallback_relative_error", 0.0)
    SMS.set_nanite_settings(sm, ns, True)
    EAL.save_asset(DST + "/" + name, only_if_is_dirty=False)
    return {"slots": slots, "unmapped": unmapped}

def asset_report(name):
    sm = unreal.load_asset(DST + "/" + name)
    if not sm: return {"missing": True}
    st = SPEC["meshes"][name]; bb = sm.get_bounding_box(); gmin, gmax = bb.min.to_tuple(), bb.max.to_tuple()
    e_dir = max(max(abs(gmin[i] - st["bbox_min"][i]), abs(gmax[i] - st["bbox_max"][i])) for i in range(3))
    bs = sm.get_editor_property("body_setup")
    return {"nanite": bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")), "convex": SMS.get_convex_collision_count(sm), "convex_expected": st["ucx"],
            "bounds_err_cm": round(e_dir, 3), "tris_lod0": sm.get_num_triangles(0), "tris_expected": st["tris"],
            "trace_flag": str(bs.get_editor_property("collision_trace_flag")).split(".")[-1].split(":")[0] if bs else None,
            "materials": [[str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None]
                          for m in sm.get_editor_property("static_materials")]}

# ------------------------------------------------------------------ place
def tagged(tag=TAG): return [a for a in EAS.get_all_level_actors() if any(str(t) == tag for t in a.tags)]
def find_actor(name):
    for a in EAS.get_all_level_actors():
        if a.get_actor_label() == name or a.get_name() == name: return a
    return None
def add_comp(a, cls, name):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root = sds.k2_gather_subobject_data_for_instance(a)[0]
    handle, fail = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=root, new_class=cls, blueprint_context=None))
    comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    if not comp: raise RuntimeError("component not created: %s" % fail)
    try: sds.rename_subobject(handle, unreal.Text(name))
    except Exception: pass
    return comp
def xf(p):
    s = p[5] if len(p) > 5 else 1.0
    return unreal.Transform(location=V(p[:3]), rotation=unreal.Rotator(roll=0.0, pitch=p[4], yaw=p[3]), scale=V((s, 1, 1)))

def place():
    w = world()
    if not w.get_path_name().startswith(LEVEL): raise RuntimeError("Active level is %s" % w.get_path_name())
    meshes = {n: unreal.load_asset(DST + "/" + n) for n in SPEC["meshes"]}
    if [n for n, m_ in meshes.items() if not m_]: raise RuntimeError("Missing meshes: %s" % [n for n, m_ in meshes.items() if not m_])
    ocean = [a for a in EAS.get_all_level_actors() if a.get_class().get_name() == "WaterBodyOcean"]
    if len(ocean) != 1: raise RuntimeError("expected exactly one WaterBodyOcean, found %d" % len(ocean))
    city = tagged(CITY_TAG); spatial = city[0].get_editor_property("is_spatially_loaded") if city else True
    out = {"removed": 0, "spawned": [], "spatially_loaded_like_city": bool(spatial)}
    with unreal.ScopedEditorTransaction("AOS Atoll: Stage 2A breakwater ring"):
        olda = tagged()
        if olda: EAS.destroy_actors(olda); out["removed"] = len(olda)
        for g in ASM["actors"]:
            a = EAS.spawn_actor_from_class(unreal.Actor, V((0, 0, 0)), unreal.Rotator(0, 0, 0)); a.modify()
            a.root_component.set_mobility(unreal.ComponentMobility.STATIC)                      # Static root BEFORE the ISM is attached
            comp = add_comp(a, unreal.InstancedStaticMeshComponent, "Instances"); comp.set_static_mesh(meshes[g["mesh"]])
            comp.set_mobility(unreal.ComponentMobility.STATIC); comp.set_collision_profile_name("BlockAll")
            comp.add_instances([xf(p) for p in g["instances"]], False, False)
            a.set_actor_label(g["label"]); a.set_folder_path(g["folder"])
            a.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("AOS_Atoll_Group=" + g["label"])])
            a.set_editor_property("is_spatially_loaded", spatial)
            out["spawned"].append("%s x%d" % (g["label"], len(g["instances"])))
        for e in ASM["exclusion_volumes"]:                                                      # dry holds: remove WaterBodyOcean from the hull interior (queries / buoyancy / underwater PP)
            ev = EAS.spawn_actor_from_class(unreal.WaterBodyExclusionVolume, V(e["loc"]), unreal.Rotator(roll=0.0, pitch=0.0, yaw=e["yaw"])); ev.modify()
            ev.set_actor_scale3d(V([s / 200.0 for s in e["size"]]))                             # default brush = 200 cube
            ev.set_editor_property("exclusion_mode", unreal.WaterExclusionMode.ADD_WATER_BODIES_LIST_TO_EXCLUSION)
            ev.set_editor_property("water_bodies", [ocean[0]])
            ev.set_actor_label(e["label"]); ev.set_folder_path(ASM["folder"] + "/ExclusionVolumes")
            ev.set_editor_property("tags", [unreal.Name(TAG)]); ev.set_editor_property("is_spatially_loaded", spatial)
        out["exclusion_volumes"] = len(ASM["exclusion_volumes"])
    out["actors"] = len(tagged())
    return out

# ------------------------------------------------------------------ verify (read-only)
OT = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY3, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY4]   # WorldStatic, WorldDynamic, Pawn, PhysicsBody
WSO = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1]
NONE = unreal.DrawDebugTrace.NONE
ALL = EAS.get_all_level_actors()
WATER = [a for a in ALL if a.get_class().get_name().startswith("Water")]      # ocean collision + exclusion volumes
TRIG = [a for a in ALL if a.get_class().get_name() == "AOSFallRecoveryVolume"]  # query-only character triggers (profile AOS_FallRecovery, Z -300 .. -20): they block nothing
SOFT = WATER + TRIG
def _h1(r):
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    if not t[0]: return None
    lab = None
    for x in t:
        if isinstance(x, unreal.Actor): lab = x.get_actor_label(); break
    return {"p": [round(t[4].x, 1), round(t[4].y, 1), round(t[4].z, 1)], "ip": [round(t[5].x, 1), round(t[5].y, 1), round(t[5].z, 1)], "actor": lab}
def line(p0, p1, ign=(), ot=WSO): return _h1(SL.line_trace_single_for_objects(world(), V(p0), V(p1), ot, False, SOFT + list(ign), NONE, True))
def sph(p0, p1, r, ign=(), ot=OT): return _h1(SL.sphere_trace_single_for_objects(world(), V(p0), V(p1), float(r), ot, False, SOFT + list(ign), NONE, True))
def boxsweep(p0, p1, he, yaw, ign=(), ot=OT): return _h1(SL.box_trace_single_for_objects(world(), V(p0), V(p1), V(he), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), ot, False, SOFT + list(ign), NONE, True))
def box_actors(c, he, rot, ign):
    """Labels of every actor (4 object types) touched by an oriented box at c."""
    r = SL.box_trace_multi_for_objects(world(), V(c), V((c[0], c[1], c[2] + 0.01)), V(he), rot, OT, False, WATER + list(ign), NONE, True)
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    labs = set()
    for h in (r or []):
        for x in h.to_tuple():
            if isinstance(x, unreal.Actor): labs.add(x.get_actor_label()); break
    return sorted(labs)
def abox(a):
    o, e = a.get_actor_bounds(False); return (o.x - e.x, o.y - e.y, o.z - e.z, o.x + e.x, o.y + e.y, o.z + e.z)
def seg_box_dist(p, q, b, n=24):
    """Min distance from segment pq to an AABB (sampled)."""
    best = 1e18
    for i in range(n + 1):
        t = i / n; x = [p[k] + (q[k] - p[k]) * t for k in range(3)]
        d = math.sqrt(sum(max(b[k] - x[k], 0.0, x[k] - b[k + 3]) ** 2 for k in range(3))); best = min(best, d)
    return best

def verify():
    Cx = []
    def chk(name, ok, value): Cx.append({"check": name, "pass": bool(ok), "value": value})
    mine = tagged(); acts = {a.get_actor_label(): a for a in mine}; groups = ASM["actors"]
    comp = {l: a.get_component_by_class(unreal.InstancedStaticMeshComponent) for l, a in acts.items()}
    # ---- 1. assets
    ar = {n: asset_report(n) for n in SPEC["meshes"]}
    chk("6 meshes imported to %s" % DST, len(ar) == 6 and all(not v.get("missing") for v in ar.values()), sorted(ar))
    chk("UCX hulls survived (legacy FBX importer): per mesh = spec; every hull <= 32 verts in the source", all(v.get("convex") == v.get("convex_expected") for v in ar.values()) and all(m["ucx_max_verts"] <= 32 for m in SPEC["meshes"].values()),
        {n: [v.get("convex"), SPEC["meshes"][n]["ucx_max_verts"]] for n, v in ar.items()})
    chk("Nanite on, CollisionTraceFlag = CTF_USE_DEFAULT on all 6", all(v.get("nanite") and v.get("trace_flag") == "CTF_USE_DEFAULT" for v in ar.values()), {n: [v.get("nanite"), v.get("trace_flag")] for n, v in ar.items()})
    chk("every slot carries an MI_Atoll_* instance of M_Atoll_Master", all(m[1] and m[1].startswith("MI_Atoll_") for v in ar.values() for m in v.get("materials", [])), {n: [m[1] for m in v.get("materials", [])] for n, v in ar.items()})
    chk("Nanite fallback mesh = full source mesh (LOD0 triangles = spec; fallback relative error 0)", all(v.get("tris_lod0") == v.get("tris_expected") for v in ar.values()), {n: [v.get("tris_lod0"), v.get("tris_expected")] for n, v in ar.items()})
    chk("bounds vs spec within 1 cm (no Y mirror)", all(v.get("bounds_err_cm", 9) < 1.0 for v in ar.values()), {n: v.get("bounds_err_cm") for n, v in ar.items()})
    chk("Interchange FBX importer restored (%s = 1)" % CV_FBX, SL.get_console_variable_bool_value(CV_FBX), SL.get_console_variable_bool_value(CV_FBX))
    # ---- 2. placement
    cnt = {g["label"]: (comp[g["label"]].get_instance_count() if comp.get(g["label"]) else None) for g in groups}
    chk("8 instanced groups placed, instance counts = spec", all(cnt[g["label"]] == len(g["instances"]) for g in groups), cnt)
    chk("ring composition: 12 node caissons, 9 full hulls, 6 short hulls, 33 curtain modules, 6 gate pipes, 70 BC-R ring pipes, 12 x 64 chain segments",
        [cnt.get(k) for k in ("BW_Nodes", "BW_Hulls_A", "BW_Hulls_Short", "BW_PorousCurtains", "BW_TaylorPipes_Gates", "BW_TaylorPipes_RingBCR")] == [12, 9, 6, 33, 6, 70] and (cnt.get("BW_Mooring_Surface") or 0) + (cnt.get("BW_Mooring_Deep") or 0) == 768, cnt)
    prof = sorted({(str(c.get_collision_profile_name()), str(c.mobility).split(".")[-1].split(":")[0], str(acts[l].root_component.mobility).split(".")[-1].split(":")[0], c.get_attach_parent() == acts[l].root_component) for l, c in comp.items() if c})
    chk("all ISM components Static, attached to a Static root, BlockAll", prof == [("BlockAll", "STATIC", "STATIC", True)], prof)
    badf = [a.get_actor_label() for a in mine if not str(a.get_folder_path()).startswith(ASM["folder"] + "/")]
    chk("everything organised under %s/ (Perimeter, TaylorPipes, Mooring, ExclusionVolumes)" % ASM["folder"], not badf and len(mine) == len(groups) + len(ASM["exclusion_volumes"]), {"actors": len(mine), "folders": sorted({str(a.get_folder_path()) for a in mine}), "bad": badf})
    merr = 0.0
    for g in groups:
        c = comp.get(g["label"])
        if not c: continue
        for i, p in enumerate(g["instances"]):
            t = c.get_instance_transform(i, True); t = t[-1] if isinstance(t, tuple) else t; l = t.translation
            merr = max(merr, abs(l.x - p[0]), abs(l.y - p[1]), abs(l.z - p[2]))
    chk("instance positions = spec (max error cm)", merr < 0.05, round(merr, 4))
    # ---- 3. live anchors
    city = tagged(CITY_TAG); cb = [abox(a) for a in city]
    rmax = max(math.hypot(max(abs(b[0] - C[0]), abs(b[3] - C[0])), max(abs(b[1] - C[1]), abs(b[4] - C[1]))) for b in cb) if cb else None
    st = find_actor("TP_Station_A_SurfaceSocket"); sb = abox(st); r_st = math.hypot(max(abs(sb[0] - C[0]), abs(sb[3] - C[0])), max(abs(sb[1] - C[1]), abs(sb[4] - C[1])))
    inner = ASM["ring"]["r"] - 50.0
    chk("open outer harbour: farthest city AABB corner / TP_Station_A corner from the ring centre vs the innermost BW element (BC-R pipe ring, r 10 950)", cb and rmax < inner - 2000.0 and r_st < inner - 2000.0,
        {"center": C, "city_actors": len(cb), "city_r_max": round(rmax), "station_a_r_max": round(r_st), "ring_pipes_r": inner, "hull_inner_face_r": APO - 700.0, "free_harbour_width_min": round(inner - rmax)})
    slab = find_actor("KikutakeSlab_Tiles"); sl_hits = []
    for L in ASM["mooring"]:
        h = line((L["anchor"][0], L["anchor"][1], Z["slab_top"] + 1500.0), (L["anchor"][0], L["anchor"][1], Z["slab_top"] - 1500.0), mine); sl_hits.append([L["id"], h["p"][2] if h else None, h["actor"] if h else None])
    chk("12 mooring anchors land on KikutakeSlab_Tiles top (traced Z = -18 000 +- 1)", all(h[1] is not None and abs(h[1] - Z["slab_top"]) <= 1.0 and h[2] == "KikutakeSlab_Tiles" for h in sl_hits), sl_hits)
    # ---- 4. geometry of the wall
    hm = []
    for p in next(g for g in groups if g["label"] == "BW_Hulls_A")["instances"]:
        yaw = math.radians(p[3]); ly = (-math.sin(yaw), math.cos(yaw))                 # local +Y (seaward)
        d = line((p[0] - 450.0 * ly[0], p[1] - 450.0 * ly[1], 3000.0), (p[0] - 450.0 * ly[0], p[1] - 450.0 * ly[1], 0.0))
        k = line((p[0], p[1], -6000.0), (p[0], p[1], -3000.0)); u = line((p[0], p[1], -1000.0), (p[0], p[1], -1450.0))
        hm.append([d["p"][2] if d else None, k["p"][2] if k else None, k["actor"] if k else None])
    chk("9 full hulls: deck traced at Z +1 200, curtain bottom traced at Z -4 200 (clear water below)", all(h[0] is not None and abs(h[0] - Z["deck"]) < 0.5 and h[1] is not None and abs(h[1] - Z["curtain_bottom"]) < 0.5 and h[2] == "BW_PorousCurtains" for h in hm), hm)
    gw = []
    for G in ASM["gates"]:
        t = (-G["dir"][1], G["dir"][0]); row = [G["az"]]
        for zz in (6.0, -700.0, -3000.0):
            a_ = line((G["mid"][0], G["mid"][1], zz), (G["mid"][0] + 2500.0 * t[0], G["mid"][1] + 2500.0 * t[1], zz)); b_ = line((G["mid"][0], G["mid"][1], zz), (G["mid"][0] - 2500.0 * t[0], G["mid"][1] - 2500.0 * t[1], zz))
            row.append(round(math.hypot(a_["p"][0] - G["mid"][0], a_["p"][1] - G["mid"][1]) + math.hypot(b_["p"][0] - G["mid"][0], b_["p"][1] - G["mid"][1]), 1) if a_ and b_ else None)
        gw.append(row)
    chk("3 ocean gates at azimuths 180 / 60 / 300: traced clear width 1 600 at Z +6 (hulls), -700 (hulls), -3 000 (curtains)", sorted(g[0] for g in gw) == [60.0, 180.0, 300.0] and all(v is not None and abs(v - 1600.0) < 1.0 for g in gw for v in g[1:]), gw)
    # ---- 5. Shell-1 sails out through each gate (sphere R245 + Shell mesh box), harbour ring is connected
    sail = []
    for G in ASM["gates"]:
        az = G["az"]; hits = []
        for zz in (6.0, -400.0, -1200.0):
            h = sph(pol(9000.0, az, zz), pol(17000.0, az, zz), SHELL_R)
            if h: hits.append(["sphere", zz, h])
            h = boxsweep(pol(9000.0, az, zz), pol(17000.0, az, zz), SHELL_BOX, az)
            if h: hits.append(["box", zz, h])
        lo, hi = 0.0, 900.0                                                             # widest sphere that still passes at Z 6
        for _ in range(12):
            m = (lo + hi) / 2.0
            if sph(pol(11000.0, az, 6.0), pol(14000.0, az, 6.0), m): hi = m
            else: lo = m
        sail.append({"gate": az, "hits": hits, "max_free_sphere_radius": round(lo, 1)})
    chk("Shell-1 sails out through each of the 3 gates: sphere R245 and Shell box 660 x 280 x 354, r 9 000 -> 17 000 at Z +6 / -400 / -1 200: 0 hits; widest passing sphere ~800", all(not s["hits"] and s["max_free_sphere_radius"] >= 780.0 for s in sail), sail)
    ringh = []
    for i in range(72):
        h = sph(pol(9300.0, i * 5.0, 6.0), pol(9300.0, (i + 1) * 5.0, 6.0), SHELL_R)
        if h: ringh.append([i * 5, h])
    chk("outer harbour ring r 9 300 is open all the way round (72 sphere R245 chords at Z +6): any gate is reachable from any side of the city", not ringh, ringh[:4] or "0 hits")
    exitp = [sph((-1000.0, -1380.0, -450.0), (-1000.0, -4200.0, -450.0), SHELL_R, [st]), sph((-1000.0, -4200.0, -450.0), (-1000.0, -8600.0, -450.0), SHELL_R, [st])]
    chk("info: TP_Station_A (-1000, -1380, -450) -> straight south into the harbour ring at Z -450 (sphere R245; first leg may graze existing city / station geometry, not the BW)", all((h is None) or (h["actor"] not in acts) for h in exitp), exitp)
    # ---- 6. dive beneath the curtains (Z -4 200) on every side, blocked above
    under, ctrl = [], []
    for j in range(12):
        az = 30.0 * j
        for zz in (-4700.0, -6000.0):
            h = sph(pol(9500.0, az, zz), pol(16000.0, az, zz), SHELL_R)
            if h: under.append([az, zz, h])
        if az not in ASM["gate_azimuths"]:
            for zz in (-3000.0, -300.0):
                h = sph(pol(9500.0, az, zz), pol(16000.0, az, zz), SHELL_R); ctrl.append([az, zz, h["actor"] if h else None])
    for L in ASM["mooring"]:                                                            # under the node caissons too (the chains leave seaward)
        h = sph(pol(9500.0, L["az"], -4700.0), pol(12600.0, L["az"], -4700.0), SHELL_R)
        if h: under.append([L["az"], "node", h])
    chk("Shell-1 dives beneath the porous curtains: sphere R245 at Z -4 700 and -6 000 passes under all 12 sides (r 9 500 -> 16 000) and under the 12 nodes: 0 hits", not under, under[:4] or "0 hits")
    chk("control: the same sweep at Z -3 000 is stopped by BW_PorousCurtains and at Z -300 by BW_Hulls_A on all 9 closed sides", len(ctrl) == 18 and all((c[1] == -3000.0 and c[2] == "BW_PorousCurtains") or (c[1] == -300.0 and c[2] == "BW_Hulls_A") for c in ctrl), ctrl[:4])
    # ---- 7. overlaps with everything that is not the breakwater
    ov = {}
    for g in groups:
        if g["mesh"] == "SM_Mooring_Link": continue
        m = SPEC["meshes"][g["mesh"]]; cen = [(m["bbox_min"][i] + m["bbox_max"][i]) / 2.0 for i in range(3)]; he = [(m["bbox_max"][i] - m["bbox_min"][i]) / 2.0 for i in range(3)]
        for i, p in enumerate(g["instances"]):
            y = math.radians(p[3]); wc = (p[0] + cen[0] * math.cos(y) - cen[1] * math.sin(y), p[1] + cen[0] * math.sin(y) + cen[1] * math.cos(y), p[2] + cen[2])
            for lab in box_actors(wc, he, unreal.Rotator(roll=0.0, pitch=0.0, yaw=p[3]), mine): ov.setdefault(lab, []).append("%s[%d]" % (g["label"], i))
    trig_l = {a.get_actor_label() for a in TRIG}; hard = {k: v[:4] for k, v in ov.items() if k not in trig_l}; soft = {k: v[:4] for k, v in ov.items() if k in trig_l}
    chk("0 overlaps: oriented bounding box of every node / hull / curtain / pipe instance (142) vs every non-breakwater actor (WorldStatic, WorldDynamic, Pawn, PhysicsBody)", not hard, hard or "0 actors touched")
    chk("info: query-only AOSFallRecoveryVolume triggers whose corner reaches a breakwater bounding box (no collision, nothing to fix on the BW side)", True, soft or "none")
    chain_hits = []
    for L in ASM["mooring"]:
        P = L["pts"]
        for i in range(0, 60, 4):
            h = sph(P[i], P[i + 4], 40.0, mine)
            if h: chain_hits.append([L["id"], i, h])
    chk("12 mooring lines: sphere R40 swept along every line (fairlead -> 94 % of the length; the last 4 segments settle on the slab): 0 hits on anything", not chain_hits, chain_hits[:4] or "0 hits")
    named = {"TowerA3_Hull": [find_actor("TowerA3_Hull")], "TP_Station_B_TowerA_C01": [find_actor("TP_Station_B_TowerA_C01")], "TP_Station_A_SurfaceSocket": [st], "LARS_DockArm": [find_actor("LARS_DockArm")], "BP_ShellDock": [find_actor("BP_ShellDock")],
             "Cluster C-01 (Environment/Clusters/C01_Home_A03, %d actors)": [a for a in ALL if str(a.get_folder_path()).startswith("Environment/Clusters/C01_Home_A03")],
             "Reaper Arena (Environment/Enemies/Reaper/Arena, %d actors)": [a for a in ALL if str(a.get_folder_path()).startswith("Environment/Enemies/Reaper/Arena")],
             "Atoll city (%d actors)": city, "A0_Down_Capital": [find_actor("A0_Down_Capital")]}
    clr = {}
    for nm, al in named.items():
        al = [a for a in al if a]
        if not al: clr[nm] = None; continue
        bs_ = [abox(a) for a in al]; b = [min(x[k] for x in bs_) for k in range(3)] + [max(x[k + 3] for x in bs_) for k in range(3)]
        d_chain = min(seg_box_dist(L["pts"][i], L["pts"][i + 1], b, 4) for L in ASM["mooring"] for i in range(64))
        d_wall = min(seg_box_dist(pol(ASM["r_vertex"], 15.0 + 30.0 * k, zz), pol(ASM["r_vertex"], 45.0 + 30.0 * k, zz), b, 48) for k in range(12) for zz in (Z["deck"], Z["curtain_bottom"])) - 800.0
        clr[(nm % len(al)) if "%d" in nm else nm] = {"to_mooring_lines_cm": round(d_chain), "to_wall_cm": round(d_wall)}
    chk("clearances (AABB of the named actors -> chain centre lines / perimeter wall), all > 2 000 cm: Cluster C-01, Tower A-3, Reaper Arena, TP stations, LARS dock, city, Spire capital", all(v and v["to_mooring_lines_cm"] > 2000 and v["to_wall_cm"] > 2000 for v in clr.values()), clr)
    # ---- 8. exclusion volumes
    evs = [a for a in mine if a.get_class().get_name() == "WaterBodyExclusionVolume"]; evr = []
    for a in evs:
        wb = a.get_editor_property("water_bodies"); evr.append([a.get_actor_label(), str(a.get_editor_property("exclusion_mode")).split(".")[-1].split(":")[0], [x.get_actor_label() for x in wb], [round(v) for v in a.get_actor_scale3d().to_tuple()]])
    chk("15 AWaterBodyExclusionVolume in the dry holds (9 x 4 400 x 1 200 x 2 300, 6 x 1 300 x 1 200 x 2 300, Z -1 200 .. +1 100), mode ADD_WATER_BODIES_LIST_TO_EXCLUSION, list = [WaterBodyOcean]",
        len(evs) == 15 and all(e[1] == "ADD_WATER_BODIES_LIST_TO_EXCLUSION" and e[2] == ["WaterBodyOcean"] for e in evr), sorted(evr)[:3])
    # ---- 9. nothing else disturbed
    orig = {"LARS_DockArm": (-1669.0, 50.0, 80.0), "BP_ShellDock": (-1230.0, 600.0, 170.0), "ChargingZone_Dock": (-1000.0, 700.0, 0.0), "TP_Station_A_SurfaceSocket": (-1000.0, -1380.0, -450.0)}
    cur = {n: find_actor(n).get_actor_location().to_tuple() for n in orig}
    chk("existing dock / teleport actors at their transforms; city actor count unchanged (28)", all(max(abs(cur[n][i] - orig[n][i]) for i in range(3)) < 0.1 for n in orig) and len(city) == 28, {"city_actors": len(city), "moved": [n for n in orig if max(abs(cur[n][i] - orig[n][i]) for i in range(3)) >= 0.1]})
    res = {"ok": all(c["pass"] for c in Cx), "passed": sum(1 for c in Cx if c["pass"]), "total": len(Cx), "checks": Cx, "level_actors": len(ALL), "bw_actors": len(mine)}
    os.makedirs(OUT_DIR, exist_ok=True); json.dump(res, open(os.path.join(OUT_DIR, "breakwater_verify.json"), "w"), indent=1, default=str)
    return res

# ------------------------------------------------------------------ capture (editor SceneCapture2D; fog + underwater PP off, temporary fill lights)
def _v(az, r, z, dt=0.0): 
    p = pol(r, az, z); return (p[0] - dt * math.sin(math.radians(az)), p[1] + dt * math.cos(math.radians(az)), z)
VIEWS = {
    "01_overview_NE":          dict(cam=(C[0] + 15000, C[1] + 15000, 15000), at=(C[0], C[1], 0), fov=75),
    "02_overview_top":         dict(cam=(C[0], C[1] - 10, 30000), at=(C[0], C[1], 0), fov=58),
    "03_gate180_from_harbour": dict(cam=_v(180, 8200, 420), at=_v(180, 12000, 300), fov=70),
    "04_gate060_from_ocean":   dict(cam=_v(60, 16500, 1500, 2500), at=_v(60, 12000, 300), fov=60),
    "05_gate300_above":        dict(cam=_v(300, 10500, 5200, 600), at=_v(300, 12000, 0), fov=65),
    "06_hull_deck_hatches":    dict(cam=_v(0, 10800, 2700, 1900), at=_v(0, 12000, 1100, 600), fov=60),
    "07_node_caisson":         dict(cam=_v(15, 10300, 1900, -900), at=_v(15, 12423, 600), fov=55),
    "08_wall_from_city_edge":  dict(cam=(4300, 820, 1000), at=(11000, 700, 400), fov=70),     # above the unmasked swell (the wave mask is Part 2B)
    "14_hatch_compressor_bay": dict(cam=(10300, 2300, 1900), at=(11000, 1600, 1250), fov=50),
    "09_uw_curtain_harbour":   dict(cam=_v(30, 9800, -2600, 1800), at=_v(30, 12000, -2800), fov=70, ev=2.0),
    "10_uw_gate180_pipes":     dict(cam=_v(180, 10300, -1300, 900), at=_v(180, 12100, -1800), fov=70, ev=2.0),
    "11_uw_ring_pipes":        dict(cam=_v(92, 10600, -500, 0), at=_v(104, 11000, -800), fov=70, ev=2.0),
    "12_uw_mooring_fairlead":  dict(cam=_v(45, 14300, -900, 1300), at=_v(45, 13600, -1500), fov=65, ev=2.0),
    "13_uw_mooring_anchor":    dict(cam=_v(45, 22000, -16800, 1500), at=_v(45, 23600, -17700), fov=65, ev=3.0),
}
def capture():
    os.makedirs(OUT_DIR, exist_ok=True); w = world(); out = []; tmp = []
    for i, (pitch, yaw, lux) in enumerate(((-38, -125, 10.0), (-18, 70, 4.0))):
        sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 0), unreal.Rotator(roll=0, pitch=pitch, yaw=yaw)); sun.set_actor_label("TMP_BWCap_Light%d" % i)
        lc = sun.get_component_by_class(unreal.DirectionalLightComponent); lc.set_mobility(unreal.ComponentMobility.MOVABLE); lc.set_intensity(lux); lc.set_cast_shadows(False); tmp.append(sun)
    try:
        for name, v in VIEWS.items():
            if SHOTS and not any(name.startswith(s) for s in SHOTS): continue
            rt_ = unreal.RenderingLibrary.create_render_target2d(w, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8)
            cam, at = V(v["cam"]), V(v["at"]); cap = EAS.spawn_actor_from_class(unreal.SceneCapture2D, cam, unreal.MathLibrary.find_look_at_rotation(cam, at)); cap.set_actor_label("TMP_BWCap_Cam"); tmp.append(cap)
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
    return {"dir": OUT_DIR, "shots": out, "temp_actors_left": [a.get_actor_label() for a in EAS.get_all_level_actors() if a.get_actor_label().startswith("TMP_BWCap")]}

def save():
    for a in tagged(): a.modify()                                                       # mark the breakwater actors dirty explicitly
    U = unreal.EditorLoadingAndSavingUtils
    n_map = [p.get_name() for p in U.get_dirty_map_packages()]; n_content = [p.get_name() for p in U.get_dirty_content_packages()]
    ok = U.save_dirty_packages(True, True)
    return {"saved": bool(ok), "map_packages": len(n_map), "map_sample": n_map[:6], "content_packages": n_content[:40], "n_content": len(n_content),
            "dirty_after": len(U.get_dirty_map_packages()) + len(U.get_dirty_content_packages())}

if MODE == "materials": result = materials()
elif MODE == "author": result = {n: [author(n), asset_report(n)["tris_lod0"]] for n in list(SPEC["meshes"])}
elif MODE == "import":
    out = {}
    for n in list(SPEC["meshes"]):
        imp = import_fbx(n); au = author(n); out[n] = {"imported": imp, "slots": au, "report": asset_report(n)}
    result = out
elif MODE == "place": result = place()
elif MODE == "verify": result = verify()
elif MODE == "capture": result = capture()
elif MODE == "save": result = save()
else: result = {"error": "unknown mode " + str(MODE)}
