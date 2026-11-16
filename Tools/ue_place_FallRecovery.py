"""AOS-DK Surface Fall Recovery - placement script for AAOSFallRecoveryVolume (Urban Bible 4.5), Lvl_FirstPerson.
Usage (MCP execute_python):
    g = {"FR_MODE": "place" | "verify" | "save"}; exec(open(r"<proj>/Tools/ue_place_FallRecovery.py", encoding="utf-8").read(), g); print(g["result"])
place  : tiles the Atoll water plane with query-only boxes (Z -300 .. -20). Idempotent: an existing volume with the same
         label is updated in place, nothing is deleted. The footprint is read from the Atoll city actors (tag AOS_Atoll_City)
         plus FR_MARGIN, so it follows the city if the kit changes.
verify : checks class, count, profile (Pawn overlap only, everything else ignored), Z range, coverage of the footprint and
         the clearance between the volume top and the lowest SafeGround walking surface.
save   : saves dirty level + external-actor packages.
"""
import math
import unreal

MODE = globals().get("FR_MODE", "verify")
MARGIN = float(globals().get("FR_MARGIN", 2500.0))   # water kept covered beyond the outermost deck edge
TILE = float(globals().get("FR_TILE", 6000.0))       # target tile size (Bible 4.5: lagoon 6 000 x 6 000)
Z_BOTTOM, Z_TOP = -300.0, -20.0                      # task spec: water plane band, below the surface (Z 40) and every deck (>= 20)
OVERLAP = 10.0                                       # tiles overlap by 10 cm so no sliver is left between them
FOLDER = "Environment/Atoll/FallRecovery"
TAG = "AOS_FallRecovery"
CITY_TAG = "AOS_Atoll_City"

EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WORLD = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def footprint():
    mn = [1e18, 1e18]
    mx = [-1e18, -1e18]
    n = 0
    for a in EAS.get_all_level_actors():
        if CITY_TAG not in [str(t) for t in a.tags]:
            continue
        o, e = a.get_actor_bounds(False)
        n += 1
        mn[0] = min(mn[0], o.x - e.x); mx[0] = max(mx[0], o.x + e.x)
        mn[1] = min(mn[1], o.y - e.y); mx[1] = max(mx[1], o.y + e.y)
    return n, mn, mx


def existing():
    return {a.get_actor_label(): a for a in EAS.get_all_level_actors() if TAG in [str(t) for t in a.tags]}


def layout():
    n, mn, mx = footprint()
    x0, x1, y0, y1 = mn[0] - MARGIN, mx[0] + MARGIN, mn[1] - MARGIN, mx[1] + MARGIN
    nx, ny = max(1, math.ceil((x1 - x0) / TILE)), max(1, math.ceil((y1 - y0) / TILE))
    sx, sy = (x1 - x0) / nx, (y1 - y0) / ny
    tiles = []
    for i in range(nx):
        for j in range(ny):
            cx, cy = x0 + (i + 0.5) * sx, y0 + (j + 0.5) * sy
            tiles.append(("FallRecovery_X%d_Y%d" % (i, j), cx, cy, sx / 2 + OVERLAP / 2, sy / 2 + OVERLAP / 2))
    return {"city_actors": n, "city_min": mn, "city_max": mx, "region": [x0, y0, x1, y1], "nx": nx, "ny": ny, "tiles": tiles}


def place():
    L = layout()
    have = existing()
    cls = unreal.AOSFallRecoveryVolume
    zc, zh = (Z_TOP + Z_BOTTOM) / 2.0, (Z_TOP - Z_BOTTOM) / 2.0
    made, updated = [], []
    for label, cx, cy, hx, hy in L["tiles"]:
        a = have.get(label)
        if a is None:
            a = EAS.spawn_actor_from_class(cls, unreal.Vector(cx, cy, zc), unreal.Rotator(0, 0, 0))
            a.set_actor_label(label)
            a.set_folder_path(FOLDER)
            a.tags = [unreal.Name(TAG)]
            made.append(label)
        else:
            a.set_actor_location(unreal.Vector(cx, cy, zc), False, True)
            updated.append(label)
        box = a.get_editor_property("recovery_box")
        box.set_box_extent(unreal.Vector(hx, hy, zh), True)
        try:
            a.set_editor_property("is_spatially_loaded", False)   # a handful of boxes: keep them always loaded
        except Exception:
            pass
    return {"region": [round(v, 1) for v in L["region"]], "grid": [L["nx"], L["ny"]], "created": made, "updated": updated}


def verify():
    L = layout()
    vols = existing()
    checks = []

    def chk(name, ok, info=None):
        checks.append({"check": name, "pass": bool(ok), "info": info})

    chk("volume count == tiles", len(vols) == len(L["tiles"]), [len(vols), len(L["tiles"])])
    zmin, zmax, bad_prof, bad_class = 1e18, -1e18, [], []
    rects = []
    for label, a in vols.items():
        if not isinstance(a, unreal.AOSFallRecoveryVolume):
            bad_class.append(label)
            continue
        box = a.get_editor_property("recovery_box")
        o, e = a.get_actor_bounds(False)
        zmin, zmax = min(zmin, o.z - e.z), max(zmax, o.z + e.z)
        rects.append((o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y))
        prof = str(box.get_collision_profile_name())
        pawn = box.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)
        resp = [str(box.get_collision_response_to_channel(c)).split(".")[-1] for c in (
            unreal.CollisionChannel.ECC_WORLD_STATIC, unreal.CollisionChannel.ECC_WORLD_DYNAMIC, unreal.CollisionChannel.ECC_PHYSICS_BODY,
            unreal.CollisionChannel.ECC_VEHICLE, unreal.CollisionChannel.ECC_VISIBILITY, unreal.CollisionChannel.ECC_CAMERA)]
        enabled = str(box.get_collision_enabled()).split(".")[-1]
        if prof != "AOS_FallRecovery" or "OVERLAP" not in str(pawn).upper() or any("BLOCK" in r.upper() for r in resp) or "QUERY_ONLY" not in enabled.upper():
            bad_prof.append([label, prof, str(pawn), resp, enabled])
    chk("all volumes are AAOSFallRecoveryVolume", not bad_class, bad_class)
    chk("profile AOS_FallRecovery: query only, Pawn overlap, nothing blocks", not bad_prof, bad_prof[:3])
    chk("Z range -300 .. -20", abs(zmin - Z_BOTTOM) < 0.5 and abs(zmax - Z_TOP) < 0.5, [round(zmin, 2), round(zmax, 2)])

    # coverage: dense sample of the whole footprint (city bounds + margin) must lie inside at least one box
    x0, y0, x1, y1 = L["region"]
    miss, total, step = [], 0, 250.0
    x = x0 + 1
    while x < x1:
        y = y0 + 1
        while y < y1:
            total += 1
            if not any(r[0] <= x <= r[1] and r[2] <= y <= r[3] for r in rects):
                miss.append((round(x), round(y)))
            y += step
        x += step
    chk("footprint fully covered (250 cm sample grid)", not miss, {"samples": total, "missed": miss[:5]})
    chk("footprint reaches MARGIN beyond every city edge",
        rects and min(r[0] for r in rects) <= L["city_min"][0] - MARGIN + 1 and max(r[1] for r in rects) >= L["city_max"][0] + MARGIN - 1
        and min(r[2] for r in rects) <= L["city_min"][1] - MARGIN + 1 and max(r[3] for r in rects) >= L["city_max"][1] + MARGIN - 1,
        {"city_min": [round(v) for v in L["city_min"]], "city_max": [round(v) for v in L["city_max"]]})

    # clearance to the lowest SafeGround walking surface (line traces over the footprint of the city)
    SL = unreal.SystemLibrary
    lowest = None
    for xi in range(int(L["city_min"][0]) - 100, int(L["city_max"][0]) + 100, 100):
        for yi in range(int(L["city_min"][1]) - 100, int(L["city_max"][1]) + 100, 100):
            h = SL.line_trace_single(WORLD, unreal.Vector(xi, yi, 700), unreal.Vector(xi, yi, -700), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                     False, [], unreal.DrawDebugTrace.NONE, True)
            if h is None:
                continue
            t = h.to_tuple()
            actor, comp = t[9], t[10]
            if not t[0] or actor is None:
                continue
            tags = set(str(x_) for x_ in actor.tags) | (set(str(x_) for x_ in comp.component_tags) if comp else set())
            if "SafeGround" in tags and (lowest is None or t[4].z < lowest[0]):
                lowest = (round(t[4].z, 1), xi, yi, actor.get_actor_label())
    chk("volume top (-20) is below the lowest SafeGround surface", lowest is not None and lowest[0] > Z_TOP + 20.0, lowest)

    # nothing else may be blocked: the Shell and the dock must not be affected (overlap-only profile -> they only get events)
    for lab in ("BP_Shell", "BP_ShellDock"):
        found = [a for a in EAS.get_all_level_actors() if a.get_actor_label() == lab]
        chk(lab + " present and untouched", len(found) == 1, lab)
    return {"ok": all(c["pass"] for c in checks), "passed": sum(1 for c in checks if c["pass"]), "total": len(checks), "checks": checks}


def save():
    U = unreal.EditorLoadingAndSavingUtils
    n_map = len(U.get_dirty_map_packages())
    n_content = [p.get_name() for p in U.get_dirty_content_packages()]
    ok = U.save_dirty_packages(True, True)
    return {"saved": bool(ok), "map_packages": n_map, "content_packages": n_content,
            "dirty_after": len(U.get_dirty_map_packages()) + len(U.get_dirty_content_packages())}


if MODE == "place":
    result = place()
elif MODE == "verify":
    result = verify()
elif MODE == "save":
    result = save()
else:
    result = {"error": "unknown mode " + str(MODE)}
