# AOS-DK | Spire A-0 megastructure | UE 5.7.4 (run via execute_python)
# Imports the 8 FBX kit meshes authored by Tools/max_build_SpireA0_Kit.py (3ds Max 2027) and stacks them on the (0, 0) axis.
# Single source of truth: Tools/SpireA0_Kit_spec.json (mesh stats + assembly table written by the Max script).
# MODE: "import" (FBX -> Nanite static meshes, UCX kept, material) | "place" (25 actors) | "verify" (read-only traces)
#       | "save" (dirty packages) .  SPIRE_ONLY = [mesh names] limits "import" to a subset (Nanite builds vs. RC timeout).
# Idempotent: every placed actor carries the tag AOS_SpireA0_Kit; "place" removes only actors with that tag first.
# Run: g={"SPIRE_MODE":"verify"}; exec(open(<proj>/Tools/ue_build_SpireA0_Megastructure.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, json, os, math

MODE = globals().get("SPIRE_MODE", "verify")
ONLY = globals().get("SPIRE_ONLY", None)
PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SPEC = json.load(open(os.path.join(PROJ, "Tools/SpireA0_Kit_spec.json"), encoding="utf-8"))
DST = SPEC["content"]; FOLDER = SPEC["folder"]; TAG = "AOS_SpireA0_Kit"
FBX_DIR = os.path.join(PROJ, "Content/AOS_DK_Game/Environment/Macro/Spire_A0")
MAT_CONCRETE = "/Game/AOS_DK_Game/Environment/Clusters/Shared/M_AOS_Concrete_BoxMap"
MAT_COPPER = "/Game/AOS_DK_Game/Environment/CustomHero/Materials/MI_GIS_Conductor_Copper"
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
BOXMAP_K = 0.25
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SMS = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
SL = unreal.SystemLibrary
M = SPEC["marks"]

def world(): return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
def V(t): return unreal.Vector(float(t[0]), float(t[1]), float(t[2]))

# ------------------------------------------------------------------ import
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
    mats = {"MS_Concrete": unreal.load_asset(MAT_CONCRETE), "MS_Conductor": unreal.load_asset(MAT_COPPER)}
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
    st = SPEC["meshes"][name]; bb = sm.get_bounding_box()
    exp_min = [st["bbox_min"][0], -st["bbox_max"][1], st["bbox_min"][2]]; exp_max = [st["bbox_max"][0], -st["bbox_min"][1], st["bbox_max"][2]]
    gmin, gmax = bb.min.to_tuple(), bb.max.to_tuple()
    bs = sm.get_editor_property("body_setup")
    return {"nanite": bool(sm.get_editor_property("nanite_settings").get_editor_property("enabled")),
            "convex": SMS.get_convex_collision_count(sm), "convex_expected": st["ucx"],
            "bounds_err_cm": round(max(max(abs(gmin[i] - exp_min[i]), abs(gmax[i] - exp_max[i])) for i in range(3)), 3),
            "tris_lod0": sm.get_num_triangles(0), "tris_expected": st["tris"],
            "trace_flag": str(bs.get_editor_property("collision_trace_flag")).split(".")[-1].split(":")[0],
            "materials": [(str(m.get_editor_property("material_slot_name")), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None)
                          for m in sm.get_editor_property("static_materials")]}

# ------------------------------------------------------------------ place
def tagged(): return [a for a in EAS.get_all_level_actors() if any(str(t) == TAG for t in a.tags)]

def finish(a, label, comp, scale=1.0):
    a.set_actor_label(label); a.set_folder_path(FOLDER)
    a.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("AOS_SpireA0_Part=" + label)])
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    comp.set_collision_profile_name("BlockAll")                    # bible §3.0.4: never BlockAllDynamic on architecture
    # M_AOS_Concrete_BoxMap reads CPD 10-12 (offset) and 13-15 (local -> texture scale); with no CPD the scale is 0 (flat colour).
    # Megastructure texel density: TileCM 200 / BOXMAP_K -> 800 cm tiles; uniform actor scale folded in so every segment matches.
    k = scale * BOXMAP_K
    for i, v in ((10, 0.0), (11, 0.0), (12, 0.0), (13, k), (14, k), (15, k)):
        comp.set_default_custom_primitive_data_float(i, v)

def spawn_ism(label, mesh, loc):
    a = EAS.spawn_actor_from_class(unreal.Actor, V(loc), unreal.Rotator(0, 0, 0))
    a.root_component.set_mobility(unreal.ComponentMobility.STATIC)   # Static ISM under the default Movable root loses its attachment on level reload (world (0,0,0))
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root = sds.k2_gather_subobject_data_for_instance(a)[0]
    params = unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.InstancedStaticMeshComponent, blueprint_context=None)
    handle, fail = sds.add_new_subobject(params)
    comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    if not comp: raise RuntimeError("ISM component not created: %s" % fail)
    comp.set_static_mesh(mesh)
    a.set_actor_location(V(loc), False, True)
    return a, comp

def place():
    w = world()
    if not w.get_path_name().startswith(LEVEL): raise RuntimeError("Active level is %s" % w.get_path_name())
    meshes = {n: unreal.load_asset(DST + "/" + n) for n in SPEC["meshes"]}
    missing = [n for n, m_ in meshes.items() if not m_]
    if missing: raise RuntimeError("Missing meshes: %s" % missing)
    out = {"removed": 0, "spawned": []}
    with unreal.ScopedEditorTransaction("AOS Spire A-0 megastructure"):
        old = tagged()
        if old: EAS.destroy_actors(old); out["removed"] = len(old)
        for e in SPEC["assembly"]["actors"]:
            r = e["rot_rpy"]
            a = EAS.spawn_actor_from_object(meshes[e["mesh"]], V(e["loc"]), unreal.Rotator(roll=r[0], pitch=r[1], yaw=r[2]))
            a.set_actor_scale3d(unreal.Vector(e["scale"], e["scale"], e["scale"]))
            finish(a, e["label"], a.static_mesh_component, e["scale"]); out["spawned"].append(e["label"])
        for e in SPEC["assembly"]["ism"]:
            a, c = spawn_ism(e["label"], meshes[e["mesh"]], e["loc"])
            finish(a, e["label"], c)
            if "instances_xyz" in e:
                xf = [unreal.Transform(location=unreal.Vector(p[0], p[1], p[2])) for p in e["instances_xyz"]]
            else:
                xf = [unreal.Transform(location=unreal.Vector(0, 0, 0), rotation=unreal.Rotator(roll=0, pitch=0, yaw=y)) for y in e["instances_yaw"]]
            c.add_instances(xf, False, False)
            out["spawned"].append("%s x%d" % (e["label"], c.get_instance_count()))
    out["actors"] = len(tagged())
    return out

# ------------------------------------------------------------------ verify (read-only)
WS = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1]                   # WorldStatic
NONE = unreal.DrawDebugTrace.NONE
IGN = [a for a in EAS.get_all_level_actors() if a.get_class().get_name().startswith("Water")]   # ocean volume is WorldStatic
def _hit(r):
    if isinstance(r, tuple): r = r[-1] if len(r) > 1 else r[0]
    if r is None: return None
    t = r.to_tuple()
    if not t[0]: return None
    a = t[9] if len(t) > 9 else None
    lab = None
    for x in t:
        if isinstance(x, unreal.Actor): lab = x.get_actor_label(); break
    return {"p": [round(t[4].x, 2), round(t[4].y, 2), round(t[4].z, 2)], "actor": lab}
def line(p0, p1): return _hit(SL.line_trace_single_for_objects(world(), V(p0), V(p1), WS, False, IGN, NONE, True))
def sph(p0, p1, r): return _hit(SL.sphere_trace_single_for_objects(world(), V(p0), V(p1), float(r), WS, False, IGN, NONE, True))
def box(p0, p1, he, rot=None):
    return _hit(SL.box_trace_single_for_objects(world(), V(p0), V(p1), V(he), rot or unreal.Rotator(0, 0, 0), WS, False, IGN, NONE, True))

def verify():
    C = []; R = SPEC["shell_r"]
    def chk(name, ok, value): C.append({"check": name, "pass": bool(ok), "value": value})
    acts = {a.get_actor_label(): a for a in tagged()}
    exp = [e["label"] for e in SPEC["assembly"]["actors"]] + [e["label"] for e in SPEC["assembly"]["ism"]]
    chk("actor count (tag %s)" % TAG, len(acts) == len(exp) and all(l in acts for l in exp), "%d / %d" % (len(acts), len(exp)))
    chk("Outliner folder " + FOLDER, all(str(a.get_folder_path()) == FOLDER for a in acts.values()), sorted(set(str(a.get_folder_path()) for a in acts.values())))
    on_axis = [l for l, a in acts.items() if not l.startswith("S4_Junction") and (abs(a.get_actor_location().x) > 0 or abs(a.get_actor_location().y) > 0)]
    chk("all stack actors exactly on X = 0, Y = 0", not on_axis, on_axis)
    ar = {n: asset_report(n) for n in SPEC["meshes"]}
    chk("8 meshes: Nanite on, UCX count, bounds, material", all(v.get("nanite") and v["convex"] == v["convex_expected"] and v["bounds_err_cm"] < 0.1 and v["materials"][0][1] == "M_AOS_Concrete_BoxMap" for v in ar.values()),
        {n: [v.get("convex"), v.get("bounds_err_cm"), v.get("trace_flag")] for n, v in ar.items()})
    inst = {}
    for e in SPEC["assembly"]["ism"]:
        a = acts.get(e["label"]); c = a.get_component_by_class(unreal.InstancedStaticMeshComponent) if a else None
        inst[e["label"]] = c.get_instance_count() if c else -1
    chk("ISM instances (slab tiles / ring bus segments)", inst.get("KikutakeSlab_Tiles") == len(SPEC["assembly"]["ism"][0]["instances_xyz"]) and inst.get("S4_RingBus") == len(SPEC["assembly"]["ism"][1]["instances_yaw"]), inst)
    # --- stack continuity from actor bounds (float32 mesh data -> report in cm)
    def zb(label):
        o, e = acts[label].get_actor_bounds(False); return o.z - e.z, o.z + e.z
    def chain(labels):
        gaps = []
        for hi, lo in zip(labels, labels[1:]): gaps.append(round(zb(hi)[0] - zb(lo)[1], 3))
        return gaps
    down = ["A0_Down_Capital"] + ["A0_Down_Seg_%02d" % (i + 1) for i in range(SPEC["params"]["oct_n"])] + ["A0_Down_Collar_ICM"]
    up = ["A0_Up_Collar_ICM"] + ["A0_Up_Seg_%02d" % i for i in range(SPEC["params"]["pyl_n"], 0, -1)]
    gd = chain(down); gu = chain(up)
    chk("A-0 down stack capital -> 9 segments -> collar: max joint gap (cm)", max(abs(g) for g in gd) < 0.02, max(abs(g) for g in gd))
    chk("A-0 up stack collar -> 9 segments: max joint gap (cm)", max(abs(g) for g in gu) < 0.02, max(abs(g) for g in gu))
    # --- upper spire hangs from the slab
    slab_under = line((13500, 5000, M["slab_bot"] - 800), (13500, 5000, M["slab_bot"] + 800))
    slab_top = line((0, 0, M["slab_top"] + 800), (0, 0, M["slab_top"] - 800))
    cap_top = zb("A0_Down_Capital")[1]
    chk("slab underside (trace up beside the capital) = -23 000", slab_under and abs(slab_under["p"][2] - M["slab_bot"]) < 0.05 and slab_under["actor"] == "KikutakeSlab_Tiles", slab_under)
    chk("slab top on the axis (trace down) = -18 000", slab_top and abs(slab_top["p"][2] - M["slab_top"]) < 0.05, slab_top)
    chk("capital top = slab underside (offset cm)", abs(cap_top - M["slab_bot"]) < 0.02, round(cap_top - M["slab_bot"], 3))
    cap_side = line((20000, 0, M["slab_bot"] - 1000), (0, 0, M["slab_bot"] - 1000))
    chk("capital abacus face AF 26 000 (trace to the axis hits x = 13 000)", cap_side and abs(cap_side["p"][0] - 13000) < 0.5 and cap_side["actor"] == "A0_Down_Capital", cap_side)
    fac = []
    for e in SPEC["assembly"]["actors"]:
        if e["mesh"] not in ("SM_Spire_Octagon_Seg", "SM_Spire_Pylon_Seg"): continue
        zmid = (e["z_min"] + e["z_max"]) / 2 + (0.0 if e["mesh"] == "SM_Spire_Octagon_Seg" else 0.2 * (e["z_max"] - e["z_min"]))
        h = line((30000, 0, zmid), (0, 0, zmid))
        if e["mesh"] == "SM_Spire_Octagon_Seg": want = 9000.0 - 3000.0 * (M["cap_bot"] - zmid) / (M["cap_bot"] - M["oct_bot"])
        else: want = 11000.0 - 4000.0 * (zmid - M["bed"]) / (M["pyl_top"] - M["bed"])
        fac.append([e["label"], round(h["p"][0] - want, 2) if h else None, h["actor"] if h else None])
    chk("facade collision on the bible taper line, every segment (hit - expected, cm)", all(f[1] is not None and abs(f[1]) < 6.0 and f[2] == f[0] for f in fac), [[f[0], f[1]] for f in fac])
    # --- lower spire roots into the bed
    bed = line((16000, 0, M["bed"] + 2000), (16000, 0, M["bed"] - 2000))
    pl_top = line((14000, 0, M["bed"] + 5000), (14000, 0, M["bed"] - 1000))
    pz = zb("A0_Up_Plinth")
    chk("bed top beside the plinth (trace down) = -160 000", bed and abs(bed["p"][2] - M["bed"]) < 0.05, bed)
    chk("plinth roots into the bed: plinth bottom below bed top (cm embedded)", pz[0] < M["bed"] - 1.0 and abs(pz[1] - M["pyl_bot"]) < 0.02, [round(M["bed"] - pz[0], 2), round(pz[1], 2)])
    chk("plinth tier 1 top (trace down at r 14 000) = -158 200", pl_top and abs(pl_top["p"][2] - (M["bed"] + 1800)) < 0.05 and pl_top["actor"] == "A0_Up_Plinth", pl_top)
    seg1 = zb("A0_Up_Seg_01")
    chk("pylon base on plinth top = -157 000 (offset cm)", abs(seg1[0] - M["pyl_bot"]) < 0.02, round(seg1[0] - M["pyl_bot"], 3))
    # --- S4 gap
    zc = M["ring"]
    dn = line((0, 0, zc), (0, 0, zc - 5000)); upp = line((0, 0, zc), (0, 0, zc + 5000))
    gap = (upp["p"][2] - dn["p"][2]) if dn and upp else None
    chk("S4 gap between IC-M discs (trace up/down on the axis) = 3 000", gap is not None and abs(gap - 3000) < 0.05 and dn["actor"] == "A0_Up_Collar_ICM" and upp["actor"] == "A0_Down_Collar_ICM", [upp, dn])
    sw = []
    for az in range(0, 360, 45):
        c, s = math.cos(math.radians(az)), math.sin(math.radians(az))
        rr = 12000.0
        p_hi = (rr*c, rr*s, zc + 9000); p_in = (rr*c, rr*s, zc); p_out = (-rr*c, -rr*s, zc)
        h1 = sph(p_hi, p_in, R); h2 = sph(p_in, p_out, R)
        h3 = box(p_in, p_out, (200, 100, 100), unreal.Rotator(roll=0, pitch=0, yaw=az)); h4 = sph(p_in, p_out, 1450.0)
        if h1 or h2 or h3 or h4: sw.append([az, h1, h2, h3, h4])
    chk("S4 gap open for Shell-1: descend inside the ring bus (r 12 000) then cross the gap, 8 azimuths (sphere R245, box 400x200x200, sphere R1450)", not sw, sw)
    ctrl = sph((12000, 0, zc), (-12000, 0, zc), 1520.0)
    chk("control: sphere R1520 does NOT fit the 3 000 gap (expect hit)", ctrl is not None, ctrl)
    # --- ring bus <-> D-1
    j = acts.get("S4_Junction_Chamber_D1"); d1 = [a for a in EAS.get_all_level_actors() if a.get_actor_label() == "D1_Seg_01"]
    if j and d1:
        f = d1[0].static_mesh_component.get_socket_location("SOCKET_Snap_Front"); jl = j.get_actor_location()
        off = math.sqrt((f.x - jl.x)**2 + (f.y - jl.y)**2 + (f.z - jl.z)**2)
        chk("junction port face centre = D-1 SOCKET_Snap_Front (offset cm)", off == 0.0, {"offset": off, "port": [jl.x, jl.y, jl.z], "d1_front": [f.x, f.y, f.z]})
        o, e = j.get_actor_bounds(False)
        chk("junction port face plane = D-1 flange face x 24 000 (cm)", abs((o.x + e.x) - 24000.0) < 0.02, round(o.x + e.x - 24000.0, 3))
        rad = []
        for nm, x in (("D-1 side x 24 300", 24300.0), ("chamber side x 23 700", 23700.0)):
            rs = []
            for k in range(8):
                a_ = math.radians(22.5 + 45*k); d = (math.cos(a_), math.sin(a_))
                h = line((x, 2600*d[0], zc + 2600*d[1]), (x, 6000*d[0], zc + 6000*d[1]))
                rs.append(round(math.hypot(h["p"][1], h["p"][2] - zc), 1) if h else None)
            rad.append([nm, min(rs), max(rs)])
        chk("bore radius continuous across the joint (line traces, both sides)", all(r[1] is not None for r in rad) and abs(rad[0][1] - rad[1][1]) < 80.0, rad)
        lane = sph((27000, 0, zc + 2784), (14500, 0, zc + 2784), R)
        chk("D-1 12 o'clock lane -> junction chamber: Shell sphere runs clear to the bore end wall (hit x ~ 15 745)", lane and abs(lane["p"][0] - 15745) < 60 and lane["actor"] == "S4_Junction_Chamber_D1", lane)
        ringhit = line((20000 * math.cos(math.radians(90)), 20000 * math.sin(math.radians(90)), zc + 9000), (0, 20000, zc))
        chk("ring bus collision present (trace down at az 90 hits top of tube ~ -85 600..-86 000)", ringhit and ringhit["actor"] == "S4_RingBus" and -86100 < ringhit["p"][2] < -85500, ringhit)
        endin = sph((19319, 5176, zc + 9000), (19319, 5176, zc + 4000), 50.0)
        chk("ring bus ends are buried in the junction housing (trace down at az 15 hits the housing top -84 800)", endin and endin["actor"] == "S4_Junction_Chamber_D1" and abs(endin["p"][2] - (zc + 5200 + 50)) < 1.0, endin)
    else:
        chk("junction + D-1 present", False, None)
    # --- oculus pass-through
    oc = (12000.0, 12000.0)
    o1 = sph((oc[0], oc[1], M["slab_top"] + 1500), (oc[0], oc[1], M["slab_bot"] - 1500), R)
    o2 = sph((oc[0], oc[1], M["slab_top"] + 3000), (oc[0], oc[1], M["slab_bot"] - 3000), 1950.0)
    o3 = sph((oc[0], oc[1], M["slab_top"] + 3000), (oc[0], oc[1], M["slab_bot"] - 3000), 2060.0)
    chk("oculus (12 000, 12 000) is a through passage: Shell sphere and R1950 sphere pass, R2060 is stopped", o1 is None and o2 is None and o3 is not None, [o1, o2, o3["p"] if o3 else None])
    cof = line((12000 + 4800, 12000, M["slab_bot"] - 500), (12000 + 4800, 12000, M["slab_bot"] + 2000))
    chk("coffer ceiling 800 above the slab underside (trace up into a coffer) = -22 200", cof and abs(cof["p"][2] - (M["slab_bot"] + 800)) < 0.05, cof)
    return {"ok": all(c["pass"] for c in C), "passed": sum(1 for c in C if c["pass"]), "total": len(C), "checks": C, "assets": ar}

def save():
    U = unreal.EditorLoadingAndSavingUtils
    n_map = len(U.get_dirty_map_packages()); n_content = [p.get_name() for p in U.get_dirty_content_packages()]
    ok = U.save_dirty_packages(True, True)
    return {"saved": bool(ok), "map_packages": n_map, "content_packages": n_content,
            "dirty_after": len(U.get_dirty_map_packages()) + len(U.get_dirty_content_packages())}

if MODE == "import":
    out = {}
    for n in (ONLY or list(SPEC["meshes"])):
        out[n] = {"imported": import_fbx(n), "slots": author(n), "report": asset_report(n)}
    result = out
elif MODE == "place": result = place()
elif MODE == "verify": result = verify()
elif MODE == "save": result = save()
else: result = {"error": "unknown mode " + str(MODE)}
