"""
AOS-DK: dress Cluster C-01 Server Node (A03_R5) and Dispatch Room (A03_R6) in Lvl_FirstPerson.
Run inside UE 5.7 (execute_python):
    ns = {"__name__": "__main__", "DRESS_MODE": "all"}
    exec(compile(open(PATH).read(), PATH, "exec"), ns)
DRESS_MODE: clear | build | verify | save | all   (idempotent: every spawned actor carries TAG and is wiped first)

Geometry (world cm, B = (-48000, 22000, -9800)):
  R5 interior X -48900..-45700, Y 21600..24000, floor Z -6200, ceiling Z -5300
  R6 interior X -47800..-45800, Y 24100..25300, floor Z -6200, ceiling Z -5600
  D-M (R2->R5): west wall of R5, centre Y 23000.  D-T (R5->R6): R5 north wall / R6 south wall, centre X -46800.
Shell-1 lanes kept clear (no props): R5 W-E lane Y 22700..23300 (all X) and N-S lane X -47100..-46500 (Y 22700..24000);
  R6 lane X -47100..-46500 (Y 24100..25300).
"""
import unreal, math, json

MODE = globals().get("DRESS_MODE", "all")
TAG = "AOS_DressR5R6"
FOLDER = "Environment/Clusters/C01_Home_A03/Props_R5_R6"
KIT = "/Game/AOS_DK_Game/Environment/ModularKit/"
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

FLOOR = -6200.0
R5 = dict(x0=-48900.0, x1=-45700.0, y0=21600.0, y1=24000.0, z0=-6200.0, z1=-5300.0)
R6 = dict(x0=-47800.0, x1=-45800.0, y0=24100.0, y1=25300.0, z0=-6200.0, z1=-5600.0)
RESULT = {"mode": MODE}


def tags_of(a):
    return [str(t) for t in a.tags]


def clear():
    n = 0
    for a in eas.get_all_level_actors():
        if TAG in tags_of(a):
            eas.destroy_actor(a)
            n += 1
    return n


_assets = {}


def asset(path):
    if path not in _assets:
        _assets[path] = unreal.load_asset(path)
        assert _assets[path] is not None, "missing asset " + path
    return _assets[path]


def kit(n):
    return asset(KIT + n)


def mi(n):
    return asset(KIT + "Materials/" + n)


spawned = []


def finish(a, label):
    a.set_actor_label(label)
    a.set_folder_path(FOLDER)
    a.tags = [unreal.Name(TAG)]
    spawned.append(a)
    return a


def mesh(label, m, loc, yaw=0.0, scale=(1, 1, 1), mat=None):
    a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*loc), unreal.Rotator(roll=0, pitch=0, yaw=yaw))
    c = a.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.STATIC)
    c.set_static_mesh(m)
    a.set_actor_scale3d(unreal.Vector(*scale))
    if mat is not None:
        c.set_material(0, mat)
    return finish(a, label)


def pipe_run(prefix, m, start, end, z, n, yaw_axis):
    """Chain n scaled copies of a pipe (pivot at start, 400 long along +X) from start to end along one axis."""
    (a0, a1) = (start, end)
    total = abs(a1 - a0)
    piece = total / n
    sc = piece / 400.0
    for i in range(n):
        p = a0 + i * piece
        if yaw_axis == "x":
            mesh("%s_%02d" % (prefix, i), m, (p, FIXED[prefix], z), 0.0, (sc, 1, 1))
        else:
            mesh("%s_%02d" % (prefix, i), m, (FIXED[prefix], p, z), 90.0, (sc, 1, 1))


FIXED = {}


def tray_run(prefix, y0, y1, x, z):
    """Cable tray along +Y (yaw 90), pieces <= 330 long (mesh is 300 long)."""
    m = kit("SM_CableTray_Straight")
    n = max(1, int(math.ceil((y1 - y0) / 330.0)))
    piece = (y1 - y0) / n
    for i in range(n):
        mesh("%s_%02d" % (prefix, i), m, (x, y0 + i * piece, z), 90.0, (piece / 300.0, 1, 1))


def light(label, loc, color, lumens, radius, shadow, src_r=8.0):
    a = eas.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*loc))
    c = a.get_component_by_class(unreal.PointLightComponent)
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    c.set_editor_property("intensity", lumens)
    c.set_editor_property("attenuation_radius", radius)
    c.set_editor_property("source_radius", src_r)
    c.set_editor_property("light_color", unreal.Color(*color, 255))
    c.set_editor_property("cast_shadows", shadow)
    c.set_editor_property("use_inverse_squared_falloff", True)
    return finish(a, label)


CYAN = (139, 233, 253)        # Dracula Cyan
BLUE = (98, 114, 164)         # Dracula Comment-blue
BLUE2 = (120, 150, 255)       # cooler status blue
COOL_WHITE = (220, 235, 255)


def build():
    # ---------------- R5: Server Node ----------------
    rack = kit("SM_ServerRack_Cabinet")  # 80(X) x 100(Y) x 220, pivot bottom-centre, front assumed +Y at yaw 0
    # 4 rows along Y; rack depth 100 along X (yaw +/-90), width 80 along Y.
    rows = [(-48550.0, 90.0), (-47850.0, -90.0), (-47150.0, 90.0), (-46100.0, -90.0)]
    # (centre X, yaw). rows 1/2 face aisle X -48500..-47900; row 3/4 face the N-S lane aisle X -47100..-46150.
    # yaw +90 -> front (+Y local) points -X ; yaw -90 -> front points +X
    # row1 (left of aisle1) must face +X -> yaw -90 ; row2 faces -X -> yaw 90 ; row3 faces +X -> -90 ; row4 faces -X -> 90
    rows = [(-48550.0, -90.0), (-47850.0, 90.0), (-47150.0, -90.0), (-46100.0, 90.0)]
    south_y = [21700.0 + 80.0 * k for k in range(8)]    # edges 21660..22300
    north_y = [23880.0 - 80.0 * k for k in range(4)]    # edges 23600..23920
    for ri, (rx, yaw) in enumerate(rows, start=1):
        for k, y in enumerate(south_y):
            mesh("DR_R5_Rack_R%d_S%02d" % (ri, k), rack, (rx, y, FLOOR), yaw)
        for k, y in enumerate(north_y):
            mesh("DR_R5_Rack_R%d_N%02d" % (ri, k), rack, (rx, y, FLOOR), yaw)
        # overhead cable trays sitting on the rack tops (z = rack top)
        tray_run("DR_R5_Tray_R%d_S" % ri, 21660.0, 22300.0, rx, FLOOR + 220.0)
        tray_run("DR_R5_Tray_R%d_N" % ri, 23600.0, 23920.0, rx, FLOOR + 220.0)
    # wall pipes (clear of lanes): south wall D80, east wall D40, north wall D40 (two runs, outside the D-T lane)
    FIXED["DR_R5_Pipe_S"] = 21660.0
    pipe_run("DR_R5_Pipe_S", kit("SM_Pipe_Straight_D80"), -48880.0, -45720.0, -5560.0, 8, "x")
    FIXED["DR_R5_Pipe_E"] = -45740.0
    pipe_run("DR_R5_Pipe_E", kit("SM_Pipe_Straight_D40"), 21700.0, 23900.0, -5600.0, 6, "y")
    FIXED["DR_R5_Pipe_NW"] = 23960.0
    pipe_run("DR_R5_Pipe_NW", kit("SM_Pipe_Straight_D40"), -48860.0, -47130.0, -5480.0, 4, "x")
    FIXED["DR_R5_Pipe_NE"] = 23960.0
    pipe_run("DR_R5_Pipe_NE", kit("SM_Pipe_Straight_D40"), -46470.0, -45770.0, -5480.0, 2, "x")
    FIXED["DR_R5_Conduit_S"] = 21720.0
    # status lights: 5 new + 2 pickup glows = 7 <= 8, 1 shadow caster
    light("DR_R5_Light_00", (-48200.0, 23000.0, -5480.0), CYAN, 900, 700, False)
    light("DR_R5_Light_01", (-47500.0, 22300.0, -5480.0), BLUE2, 700, 650, False)
    light("DR_R5_Light_02", (-46800.0, 23500.0, -5480.0), CYAN, 1100, 800, True)
    light("DR_R5_Light_03", (-46600.0, 22300.0, -5480.0), BLUE, 700, 650, False)
    light("DR_R5_Light_04", (-47500.0, 23700.0, -5480.0), BLUE2, 600, 600, False)

    # ---------------- R6: Dispatch ----------------
    cube = asset("/Engine/BasicShapes/Cube")
    steel = mi("MI_Kit_DarkSteel")
    status = mi("MI_Kit_Status")
    cols = [-47660.0, -47420.0, -46330.0, -46090.0]
    rws = [24300.0, 24540.0]
    di = 0
    for cx in cols:
        for cy in rws:
            p = "DR_R6_Desk_%02d" % di
            top_z = FLOOR + 75.0
            mesh(p + "_Top", cube, (cx, cy, top_z - 3.0), 0, (1.6, 0.8, 0.06), steel)
            mesh(p + "_SideL", cube, (cx - 77.5, cy, FLOOR + 36.0), 0, (0.05, 0.8, 0.72), steel)
            mesh(p + "_SideR", cube, (cx + 77.5, cy, FLOOR + 36.0), 0, (0.05, 0.8, 0.72), steel)
            mesh(p + "_Modesty", cube, (cx, cy - 36.0, FLOOR + 50.0), 0, (1.5, 0.03, 0.45), steel)
            mesh(p + "_Stand", cube, (cx, cy + 22.0, top_z + 6.0), 0, (0.08, 0.08, 0.12), steel)
            mesh(p + "_Screen", cube, (cx, cy + 22.0, top_z + 27.0), 0, (0.5, 0.03, 0.3), status)
            mesh(p + "_Keys", cube, (cx, cy - 10.0, top_z + 1.0), 0, (0.4, 0.15, 0.015), steel)
            di += 1
    # structural wall pipes (west D40, east D40), near the ceiling; north wall left free for the future breach window
    FIXED["DR_R6_Pipe_W"] = -47765.0
    pipe_run("DR_R6_Pipe_W", kit("SM_Pipe_Straight_D40"), 24130.0, 25270.0, -5640.0, 3, "y")
    FIXED["DR_R6_Pipe_E"] = -45835.0
    pipe_run("DR_R6_Pipe_E", kit("SM_Pipe_Straight_D40"), 24130.0, 25270.0, -5640.0, 3, "y")
    # work lighting: 4 new + 2 pickup glows = 6 <= 8, 1 shadow caster
    light("DR_R6_Light_00", (-47450.0, 24420.0, -5700.0), COOL_WHITE, 1300, 800, False)
    light("DR_R6_Light_01", (-46150.0, 24420.0, -5700.0), COOL_WHITE, 1300, 800, False)
    light("DR_R6_Light_02", (-46800.0, 25050.0, -5700.0), CYAN, 900, 700, False)
    light("DR_R6_Light_03", (-46800.0, 24650.0, -5700.0), COOL_WHITE, 1000, 800, True)
    return len(spawned)


# ---------------------------------------------------------------- verification
def aabb(a):
    o, e = a.get_actor_bounds(False)
    return (o.x - e.x, o.y - e.y, o.z - e.z, o.x + e.x, o.y + e.y, o.z + e.z)


def box_overlap(A, B, tol=0.5):
    return all(A[i] < B[i + 3] - tol and A[i + 3] > B[i] + tol for i in range(3))


def sphere_box(c, r, B):
    d = 0.0
    for i in range(3):
        v = c[i]
        if v < B[i]:
            d += (B[i] - v) ** 2
        elif v > B[i + 3]:
            d += (v - B[i + 3]) ** 2
    return d < r * r


def hit_actor(h):
    for v in h.to_tuple():
        if isinstance(v, unreal.Actor):
            return v
    return None


def verify():
    out = {}
    props = [a for a in eas.get_all_level_actors() if TAG in tags_of(a)]
    out["spawned"] = len(props)
    out["folder_ok"] = all(str(a.get_folder_path()) == FOLDER for a in props)
    all_actors = eas.get_all_level_actors()
    pickups = [a for a in all_actors if a.get_actor_label().startswith("IA_EnergyCell_R") or a.get_actor_label().startswith("IA_TorpedoMag_R")]
    pk = []
    for a in pickups:
        l = a.get_actor_location()
        pk.append((a.get_actor_label(), (l.x, l.y, l.z)))
    portals = [(a.get_actor_label(), aabb(a)) for a in all_actors if "/Portals" in str(a.get_folder_path()) and ("R5" in a.get_actor_label())]
    shells = [(a.get_actor_label(), aabb(a)) for a in all_actors if a.get_actor_label().startswith("SHELL_R5") or a.get_actor_label().startswith("SHELL_R6")]
    lanes = {
        "R5_WE": (-48900.0, 22700.0, -6200.0, -46500.0, 23300.0, -5300.0),
        "R5_DT": (-47100.0, 22700.0, -6200.0, -46500.0, 24000.0, -5300.0),
        "R6": (-47100.0, 24100.0, -6200.0, -46500.0, 25300.0, -5600.0),
    }
    bad = {"pickup": [], "portal": [], "shell": [], "lane": []}
    for a in props:
        B = aabb(a)
        lab = a.get_actor_label()
        for pl, c in pk:
            if sphere_box(c, 150.0, B):
                bad["pickup"].append([lab, pl])
        for pl, P in portals:
            if box_overlap(B, P):
                bad["portal"].append([lab, pl])
        for sl, S in shells:
            if not lab.startswith("DR_R5_Light") and not lab.startswith("DR_R6_Light") and box_overlap(B, S, 1.0):
                bad["shell"].append([lab, sl])
        if not lab.startswith("DR_R5_Light") and not lab.startswith("DR_R6_Light"):
            for ln, L in lanes.items():
                if box_overlap(B, L):
                    bad["lane"].append([lab, ln])
    out["overlaps"] = {k: v[:10] for k, v in bad.items()}
    out["overlap_counts"] = {k: len(v) for k, v in bad.items()}

    # lights per room (incl. pickup glows)
    def room_lights(R):
        n, sh, mx, names = 0, 0, 0.0, []
        for a in all_actors:
            for c in a.get_components_by_class(unreal.LocalLightComponent):
                l = c.get_world_location()
                if R["x0"] <= l.x <= R["x1"] and R["y0"] <= l.y <= R["y1"] and R["z0"] - 50 <= l.z <= R["z1"] + 50:
                    n += 1
                    cs = bool(c.get_editor_property("cast_shadows"))
                    sh += 1 if cs else 0
                    mx = max(mx, float(c.get_editor_property("attenuation_radius")))
                    names.append(a.get_actor_label())
        return {"lights": n, "shadow": sh, "max_attenuation": mx, "names": names}
    out["R5_lights"] = room_lights(R5)
    out["R6_lights"] = room_lights(R6)

    # Shell-1 sphere sweep R245
    SL = unreal.SystemLibrary
    ign = [a for a in all_actors if isinstance(a, unreal.TriggerBox) or a.get_actor_label().startswith("IA_") or "WaterBody" in a.get_class().get_name()]
    ot = [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2]

    def sweep(p0, p1, r=245.0):
        res = SL.sphere_trace_multi_for_objects(world, unreal.Vector(*p0), unreal.Vector(*p1), r, ot, False, ign,
                                                unreal.DrawDebugTrace.NONE, True)
        hits = res[1] if (isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], bool)) else res
        names = []
        for h in (hits or []):
            ac = hit_actor(h)
            if ac is not None:
                names.append(ac.get_actor_label())
        return sorted(set(names))

    Z = -5950.0
    legs = [
        ("D-M entry -> R5 centre", (-48900, 23000, Z), (-46800, 23000, Z)),
        ("R5 centre -> D-T", (-46800, 23000, Z), (-46800, 24000, Z)),
        ("D-T -> R6 deep", (-46800, 24000, Z), (-46800, 24950, Z)),
        ("R5 W-E lane high z -5800", (-48700, 23000, -5800), (-46800, 23000, -5800)),
        ("R5 W-E lane high z -5650", (-48700, 23000, -5650), (-46800, 23000, -5650)),
        ("R5 N-S lane high z -5800", (-46800, 23000, -5800), (-46800, 23700, -5800)),
        ("R5 N-S lane high z -5650", (-46800, 23000, -5650), (-46800, 23700, -5650)),
    ]
    sw = []
    for name, p0, p1 in legs:
        h = sweep(p0, p1)
        sw.append({"leg": name, "hits": h, "clear": len(h) == 0})
    out["sweep"] = sw
    out["sweep_clear"] = all(s["clear"] for s in sw)
    # controls: sweeps that MUST hit props (aisle1 -> through rack row 2; R6 through a desk)
    ctrl1 = sweep((-48200, 21900, -6050), (-47500, 21900, -6050), 60.0)
    ctrl2 = sweep((-47900, 24300, -6100), (-47400, 24300, -6100), 30.0)
    out["controls"] = {"rack": ctrl1, "desk": ctrl2, "detect_ok": any(n.startswith("DR_R5_Rack") for n in ctrl1) and any(n.startswith("DR_R6_Desk") for n in ctrl2)}
    ok = (out["sweep_clear"] and out["controls"]["detect_ok"] and sum(out["overlap_counts"].values()) == 0
          and out["R5_lights"]["lights"] <= 8 and out["R6_lights"]["lights"] <= 8
          and out["R5_lights"]["shadow"] <= 2 and out["R6_lights"]["shadow"] <= 2
          and out["R5_lights"]["max_attenuation"] <= 1500 and out["R6_lights"]["max_attenuation"] <= 1500)
    out["PASS"] = bool(ok)
    return out


def save():
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        return True
    except Exception as ex:
        return str(ex)


if MODE in ("clear", "build", "all"):
    RESULT["cleared"] = clear()
if MODE in ("build", "all"):
    RESULT["built"] = build()
if MODE in ("verify", "all"):
    RESULT["verify"] = verify()
    try:
        p = unreal.Paths.project_saved_dir() + "C01_dress_verify.json"
        with open(p, "w") as f:
            json.dump(RESULT["verify"], f, indent=1)
        RESULT["verify_file"] = p
    except Exception as ex:
        RESULT["verify_file_err"] = str(ex)
if MODE in ("save", "all"):
    RESULT["saved"] = save()
