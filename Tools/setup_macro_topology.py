# AOS-DK | Tower A macro-topology | UE 5.7.4 (run via execute_python)
# Source of truth: AOS_TowerA_Spatial_Bible_EN.md §1.2 (KillZ), §1.3 (vertical zoning), §1.4 (plan layout), §2.4 (GIS busducts);
#                  claude/AOS_GIS_BusCoupler_Spec_EN.md (pivot at mid-length, +X = busduct axis, snap ±3 000).
# Idempotent: every actor carries the tag "AOS_MacroID=<id>". Existing actors are re-aligned to the spec, never duplicated.
# MODE: "apply" = spawn/reconcile + KillZ; "verify" = read-only checks; "save" = save dirty map packages; "all" = apply + verify.
# Run: g={"MT_MODE":"all"}; exec(open(<proj>/Tools/setup_macro_topology.py, encoding="utf-8").read(), g); result=g["result"]
import unreal, math

MODE = globals().get("MT_MODE", "all")
LEVEL = "/Game/AOS_DK_Game/Maps/Lvl_FirstPerson"
COUPLER = "/Game/AOS_DK_Game/Environment/CustomHero/SM_GIS_BusCoupler"
TAG_ALL, TAG_ID = "AOS_MacroTopology", "AOS_MacroID="
F_SPIRE, F_D1, F_ANC, F_BND = "Environment/Macro/Spire_A0", "Environment/Macro/Conduits_D1", "Environment/Anchors", "Environment/Bounds"

# ---- Bible metrics (cm) ---------------------------------------------------------------------------------------------
KILL_Z = -175000.0                       # §1.2: separate Tower A test level
Z_TOP, Z_BED = 20000.0, -160000.0        # §1.1/§1.3: S0 top / floor of sector A (Bus Plate)
Z_RING_BUS = -90000.0                    # §1.3: ring bus and busduct axes D-1…D-6
R_RING_TAP = 24000.0                     # §2.4: D-* start at the ring bus outer surface (torus r 20 000 + OD/2)
SEG = 6000.0                             # §2.4: segment between flanges; coupler snap sockets at X ∓3 000
D1_AZIMUTH = 0.0                         # §2.4: D-1 azimuth 0° (+X, east)
D1_SEGMENTS = 6                          # C-04 = compartments D-1/1 + D-1/2 = 2 × 18 000 = 6 segments -> r 24 000 … 60 000

# id, folder, (x, y, z), note
MARKERS = [
    # Twin spires A-0↓ / A-0↑, junction band S4 (§1.3, §2.1, §2.2)
    ("A0_Down_SlabAttach", F_SPIRE, (0, 0, -23000),  "A-0↓ attachment, underside of Slab"),
    ("A0_S4_Top",          F_SPIRE, (0, 0, -82000),  "S4 junction band top"),
    ("A0_Down_DiscBottom", F_SPIRE, (0, 0, -88500),  "IC-M: bottom of disc A-0↓"),
    ("A0_RingBus_Axis",    F_SPIRE, (0, 0, -90000),  "ring bus / D-1…D-6 axis plane"),
    ("A0_Up_DiscTop",      F_SPIRE, (0, 0, -91500),  "IC-M: top of disc A-0↑ (gap 3 000)"),
    ("A0_S4_Bottom",       F_SPIRE, (0, 0, -98000),  "S4 junction band bottom"),
    ("A0_Up_Base",         F_SPIRE, (0, 0, -160000), "A-0↑ plinth on sector floor"),
    # D-1 route ends (§2.4)
    ("D1_Tap_RingBus",     F_D1, (R_RING_TAP, 0, Z_RING_BUS), "D-1 start, ring bus r 24 000"),
    ("D1_Terminus",        F_D1, (R_RING_TAP + D1_SEGMENTS * SEG, 0, Z_RING_BUS), "D-1 end of C-04 run"),
    # Explorable towers: cluster origin = lower bound of cluster Z (§1.4, §4.3 origin B)
    ("ANC_A3_home_a03",    F_ANC, (-48000, 22000, -9800),  "A-3 crown, C-01 /home/a03, Z -9 800…-5 200"),
    ("ANC_S2_var_s2",      F_ANC, (35000, -30000, -36000), "S-2 stalactite, C-02 /var/s2, Z -36 000…-32 000"),
    ("ANC_S5_sys_s5",      F_ANC, (20000, 40000, -83000),  "S-5 stalactite, C-03 /sys/s5, Z -83 000…-78 000"),
    ("ANC_X4_mnt_x4",      F_ANC, (-20000, -55000, -42000),"X-4 evac lift, C-05 /mnt/x4, Z -42 000…-39 000"),
    # Socket dock shaft Ø 6 000, 0 … -26 500 (§1.4)
    ("ANC_Socket_Rim",     F_ANC, (-60000, 0, 0),      "Socket shaft rim (waterline)"),
    ("ANC_Socket_Base",    F_ANC, (-60000, 0, -26500), "Socket shaft bottom"),
]

# Containment: 24-gon, inner apothem 150 000 around A-0, walls Z_TOP … Z_BED-5 000, floor slab top at Z_BED
BND_R, BND_T, BND_N, BND_FLOOR_T = 150000.0, 2000.0, 24, 5000.0
BND_L = math.ceil(2 * (BND_R + BND_T) * math.tan(math.pi / BND_N) / 100.0) * 100.0  # covers outer corners
BND_ZMIN = Z_BED - BND_FLOOR_T
BRUSH = 200.0  # default CubeBuilder edge

def spec():
    s = []
    for i, f, p, n in MARKERS:
        s.append(dict(id=i, kind="marker", folder=f, loc=p, rot=(0, 0, 0), scale=(1, 1, 1), note=n))
    az = math.radians(D1_AZIMUTH)
    for k in range(D1_SEGMENTS):
        r = R_RING_TAP + SEG * (k + 0.5)
        s.append(dict(id="D1_Seg_%02d" % (k + 1), kind="coupler", folder=F_D1,
                      loc=(r * math.cos(az), r * math.sin(az), Z_RING_BUS), rot=(0, D1_AZIMUTH, 0), scale=(1, 1, 1),
                      note="D-1 compartment %d, segment %d" % (k // 3 + 1, k % 3 + 1)))
    h = Z_TOP - BND_ZMIN; zc = (Z_TOP + BND_ZMIN) / 2
    for k in range(BND_N):
        a = 360.0 * k / BND_N; rc = BND_R + BND_T / 2
        s.append(dict(id="BND_Wall_%02d" % k, kind="volume", folder=F_BND,
                      loc=(rc * math.cos(math.radians(a)), rc * math.sin(math.radians(a)), zc), rot=(0, a, 0),
                      scale=(BND_T / BRUSH, BND_L / BRUSH, h / BRUSH), note="containment wall az %.1f" % a))
    s.append(dict(id="BND_Floor", kind="volume", folder=F_BND, loc=(0, 0, Z_BED - BND_FLOOR_T / 2), rot=(0, 0, 0),
                  scale=(2 * (BND_R + BND_T) / BRUSH, 2 * (BND_R + BND_T) / BRUSH, BND_FLOOR_T / BRUSH),
                  note="sector bed slab, top Z -160 000"))
    return s

V = lambda t: unreal.Vector(*[float(x) for x in t])
R = lambda t: unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(t[1]))   # rot = (0, yaw, 0); macro actors are yaw-only
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

def index():
    idx = {}
    for a in EAS.get_all_level_actors():
        for t in a.tags:
            t = str(t)
            if t.startswith(TAG_ID):
                idx.setdefault(t[len(TAG_ID):], []).append(a)
    return idx

def spawn(e, mesh):
    if e["kind"] == "marker":
        a = EAS.spawn_actor_from_class(unreal.TargetPoint, V(e["loc"]), R(e["rot"]))
    elif e["kind"] == "coupler":
        a = EAS.spawn_actor_from_object(mesh, V(e["loc"]), R(e["rot"]))
    else:
        a = EAS.spawn_actor_from_class(unreal.BlockingVolume, V(e["loc"]), R(e["rot"]))
    a.set_editor_property("tags", [unreal.Name(TAG_ALL), unreal.Name(TAG_ID + e["id"])])
    return a

def reconcile(a, e, mesh):
    a.set_actor_label(e["id"])
    a.set_folder_path(e["folder"])
    a.set_actor_location_and_rotation(V(e["loc"]), R(e["rot"]), False, True)
    a.set_actor_scale3d(V(e["scale"]))
    if e["kind"] == "coupler":
        c = a.static_mesh_component
        if c.static_mesh != mesh: c.set_static_mesh(mesh)
        c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_collision_profile_name("BlockAll")              # §3.0.4: never BlockAllDynamic on architecture
    if e["kind"] == "volume":
        a.set_editor_property("is_spatially_loaded", False)   # bounds must exist regardless of WP streaming

def apply():
    w = world()
    if not w.get_path_name().startswith(LEVEL):
        raise RuntimeError("Active level is %s, expected %s" % (w.get_path_name(), LEVEL))
    mesh = unreal.EditorAssetLibrary.load_asset(COUPLER)
    if not mesh: raise RuntimeError("Missing " + COUPLER)
    idx = index(); spawned, updated, dupes = [], [], []
    with unreal.ScopedEditorTransaction("AOS Macro Topology"):
        for e in spec():
            found = idx.get(e["id"], [])
            if len(found) > 1: dupes.append(e["id"])
            a = found[0] if found else spawn(e, mesh)
            (updated if found else spawned).append(e["id"])
            reconcile(a, e, mesh)
        ws = w.get_world_settings()
        ws.modify()
        ws.set_editor_property("kill_z", KILL_Z)
    return dict(spawned=len(spawned), reconciled=len(updated), duplicates=dupes, kill_z=KILL_Z)

def close(a, b, tol): return all(abs(x - y) <= tol for x, y in zip(a, b))

def verify():
    idx = index(); mesh = unreal.EditorAssetLibrary.load_asset(COUPLER)
    fails, rows, maxdrift = [], [], 0.0
    for e in spec():
        found = idx.get(e["id"], [])
        if len(found) != 1: fails.append("%s: %d actors" % (e["id"], len(found))); continue
        a = found[0]; l = a.get_actor_location(); r = a.get_actor_rotation(); s = a.get_actor_scale3d()
        d = max(abs(l.x - e["loc"][0]), abs(l.y - e["loc"][1]), abs(l.z - e["loc"][2])); maxdrift = max(maxdrift, d)
        tol = 0.0 if e["kind"] != "volume" else 0.01   # volume centres are trig-derived doubles
        if d > tol: fails.append("%s: drift %.4f" % (e["id"], d))
        dyaw = abs(((r.yaw - e["rot"][1] + 180.0) % 360.0) - 180.0)
        if dyaw > 1e-3 or abs(r.pitch) > 1e-3 or abs(r.roll) > 1e-3: fails.append("%s: rot %s" % (e["id"], r))
        if not close((s.x, s.y, s.z), e["scale"], 1e-4): fails.append("%s: scale" % e["id"])
        if str(a.get_folder_path()) != e["folder"]: fails.append("%s: folder %s" % (e["id"], a.get_folder_path()))
        if a.get_actor_label() != e["id"]: fails.append("%s: label" % e["id"])
        if e["kind"] == "coupler" and a.static_mesh_component.static_mesh != mesh: fails.append("%s: mesh" % e["id"])
        if e["kind"] != "volume":
            rows.append([e["id"], round(l.x), round(l.y), round(l.z)])
    # D-1 chain continuity via the asset's snap sockets
    segs = [idx["D1_Seg_%02d" % (k + 1)][0] for k in range(D1_SEGMENTS) if len(idx.get("D1_Seg_%02d" % (k + 1), [])) == 1]
    gaps = []
    for a, b in zip(segs, segs[1:]):
        p = a.static_mesh_component.get_socket_location("SOCKET_Snap_Rear")
        q = b.static_mesh_component.get_socket_location("SOCKET_Snap_Front")
        gaps.append(round((p - q).length(), 4))
    f0 = segs[0].static_mesh_component.get_socket_location("SOCKET_Snap_Front") if segs else None
    fN = segs[-1].static_mesh_component.get_socket_location("SOCKET_Snap_Rear") if segs else None
    if any(g > 0 for g in gaps): fails.append("D-1 snap gaps %s" % gaps)
    if f0 and not close((f0.x, f0.y, f0.z), (R_RING_TAP, 0, Z_RING_BUS), 0.0): fails.append("D-1 front snap off tap")
    # every explorable anchor and D-1 end lies inside the containment apothem
    inside = all(math.hypot(m[2][0], m[2][1]) < BND_R for m in MARKERS)
    if not inside: fails.append("anchor outside bounds")
    kz = world().get_world_settings().get_editor_property("kill_z")
    if kz != KILL_Z: fails.append("kill_z %s" % kz)
    return dict(ok=not fails, fails=fails, actors=len(spec()), max_drift_cm=maxdrift, d1_snap_gaps=gaps,
                d1_front=[f0.x, f0.y, f0.z] if f0 else None, d1_rear=[fN.x, fN.y, fN.z] if fN else None,
                kill_z=kz, wall_len=BND_L, positions=rows)

def save():
    U = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_name() for p in U.get_dirty_map_packages()]
    ok = U.save_dirty_packages(True, False)
    return dict(saved=ok, packages=len(dirty), sample=dirty[:5])

if MODE == "apply": result = apply()
elif MODE == "verify": result = verify()
elif MODE == "save": result = save()
else: result = dict(apply=apply(), verify=verify())
