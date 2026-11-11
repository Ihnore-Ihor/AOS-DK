# =============================================================================
# AOS-DK | Lab 5 | SM_WPN_SigkillPike  (3ds Max 2027, pymxs)   -- Dorsal Arc Pike
# Spec: Docs/AOS_Lab5_AI_Bots_Specification_EN.md  Section 2.2  (+ task brief overrides, see NAMING below)
# Units: cm. Max space: +X = butt -> tip (strike axis), +Z up, +Y = UE LEFT (UE import flips Y).
# Pivot = centre of the mount collar (0,0,0). Overall length 288 (X -26 .. +262).
#   Mount collar  : dia 12, X -20..+20, with the 4 clamp flats -> grip section 8 x 8 (dia 8) over X -13..+13
#   Capacitor bank: hex prism 18 across flats, X +20..+60;  Shaft dia 9, X +60..+200
#   Emitter coil  : 8 turns, X +195..+205;  Insulator collar X +205..+214
#   Emitter head  : two electrode blades in a V (gap 10 at X+200 -> 24 at X+262), head W 30 x H 22
# Collision: 4 convex UCX hulls (<= 32 verts each): collar prism, shaft box, 2 prong boxes.
# Sockets (helpers SOCKET_*, linked to the mesh, NOT exported; UE step authors them from the JSON):
#   SOCKET_Mount_Base, SOCKET_Arc_Tip_L/_R, SOCKET_Strike_Trace_Start/_End
# NAMING (task brief overrides spec): sockets Mount_Base / Arc_Tip_L / Arc_Tip_R / Strike_Trace_Start / Strike_Trace_End;
#   L = Max +Y (= UE left), consistent with the LARS arm (Jaw_L at +Y).
# Re-runnable: removes previous PIKE_* / SM_WPN_SigkillPike / UCX_SM_WPN_SigkillPike_* / SOCKET_* objects first.
# Run (build + save + FBX):  ns={}; exec(open(r"<proj>\Tools\max_build_SM_WPN_SigkillPike.py", encoding="utf-8").read(), ns); ns["PIKE_RESULT"]
#   build only:  ns={"PIKE_EXPORT": False}
# =============================================================================
from pymxs import runtime as rt
import math, json, os

ASSET = "SM_WPN_SigkillPike"
PFX = "PIKE_"
PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
JSON_PATH = os.path.join(PROJ, "Tools", ASSET + "_spec.json")
MAX_PATH = os.path.join(PROJ, "SourceArt", "Enemies", ASSET + ".max")
FBX_PATH = os.path.join(PROJ, "Content", "AOS_DK_Game", "Enemies", "Reaper", ASSET + ".fbx")
UCX_NAMES = ["UCX_%s_%02d" % (ASSET, i) for i in range(4)]
ALLOY, COIL, ACCENT = 1, 2, 3
SLOTS = ["MS_HardenedAlloy", "MS_PowerCoil", "MS_AccentEmissive"]

# ---------------------------------------------------------------- layout (cm)
X_MIN, X_MAX = -26.0, 262.0
BLADE_T, BLADE_H = 3.0, 22.0
BLADE_A_X, BLADE_A_Y = 200.0, 5.0            # inner-face root  (gap 10)
BLADE_E_X, BLADE_E_Y = 262.0, 12.0           # inner-face tip   (gap 24)
UCX_COLLAR_R = 11.4                          # 12-sided prism circumradius (inradius 11.0 >= coil bands r 11.0, hex corner 10.39)

# ---------------------------------------------------------------- math
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vlen(a): return math.sqrt(a[0]**2 + a[1]**2 + a[2]**2)
def vnorm(a):
    l = vlen(a); return (a[0]/l, a[1]/l, a[2]/l)
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def vdot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def P(a): return rt.Point3(float(a[0]), float(a[1]), float(a[2]))

def frame_z(zdir, roll=0.0, yhint=(0.0, 1.0, 0.0)):
    z = vnorm(zdir)
    if abs(vdot(z, yhint)) > 0.99: yhint = (0.0, 0.0, 1.0)
    x = vnorm(vcross(yhint, z)); y = vcross(z, x)
    if roll:
        c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
        x, y = vadd(vmul(x, c), vmul(y, s)), vadd(vmul(x, -s), vmul(y, c))
    return x, y, z

def mtx(x, y, z, p): return rt.Matrix3(P(x), P(y), P(z), P(p))

PARTS = []
SOCK = {}

# ---------------------------------------------------------------- primitives (all end up Editable Poly, matID = slot)
def _finish(node, mat):
    node.name = "%sPart_%03d" % (PFX, len(PARTS))
    rt.convertToPoly(node)
    rt.polyop.setFaceMatID(node, rt.Name("all"), mat)
    PARTS.append(node)
    return node

def ccyl(mat, p0, p1, r, sides=12, fil=0.5, seg=1, roll=0.0):
    d = vsub(p1, p0); h = vlen(d)
    f = min(fil, 0.4*min(r, h))
    n = rt.execute("ChamferCyl radius:%f height:%f fillet:%f Fillet_Segments:%d sides:%d Height_Segments:1 Cap_Segments:1 smoothOn:true mapcoords:false"
                   % (r, h, f, seg, sides))
    x, y, z = frame_z(d, roll); n.transform = mtx(x, y, z, p0)
    return _finish(n, mat)

def xcyl(mat, x0, x1, r, y=0.0, z=0.0, **kw):          # cylinder along the strike axis
    return ccyl(mat, (x0, y, z), (x1, y, z), r, **kw)

def cbox(mat, x0, x1, y0, y1, z0, z1, fil=0.5, seg=1):
    w, l, h = x1-x0, y1-y0, z1-z0
    f = min(fil, 0.4*min(w, l, h))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:%f Fillet_Segments:%d smooth:true mapcoords:false pos:[%f,%f,%f]"
                   % (w, l, h, f, seg, (x0+x1)/2.0, (y0+y1)/2.0, z0))
    return _finish(n, mat)

def xband(mat, x0, x1, r_in, r_out, sides=24):          # ring (Tube) around the strike axis
    n = rt.execute("Tube radius1:%f radius2:%f height:%f sides:%d height_segs:1 cap_segs:1 smooth:true mapcoords:false" % (r_out, r_in, x1-x0, sides))
    x, y, z = frame_z((1, 0, 0)); n.transform = mtx(x, y, z, (x0, 0.0, 0.0))
    return _finish(n, mat)

def xtorus(mat, xc, R, r, seg=20, sides=6):
    n = rt.execute("Torus radius1:%f radius2:%f segments:%d sides:%d smooth:2 mapcoords:false" % (R, r, seg, sides))
    x, y, z = frame_z((1, 0, 0)); n.transform = mtx(x, y, z, (xc, 0.0, 0.0))
    return _finish(n, mat)

def blade(s):
    """Electrode blade on side s (+1 = Max +Y = UE left). Inner face (toward the arc gap) -> MS_AccentEmissive."""
    A = (BLADE_A_X, s*BLADE_A_Y, 0.0); E = (BLADE_E_X, s*BLADE_E_Y, 0.0)
    W = vlen(vsub(E, A)); d = vnorm(vsub(E, A))
    z = (0.0, 0.0, 1.0); y = vcross(z, d)                 # local +Y (points to world +Y side)
    n_out = vmul(y, s)                                    # outward normal (away from the gap)
    mid = vadd(vmul(vadd(A, E), 0.5), vmul(n_out, BLADE_T/2.0))
    n = rt.execute("ChamferBox width:%f length:%f height:%f fillet:0.3 Fillet_Segments:1 smooth:true mapcoords:false" % (W, BLADE_T, BLADE_H))
    n.name = "%sPart_%03d" % (PFX, len(PARTS))
    rt.convertToPoly(n)
    rt.polyop.setFaceMatID(n, rt.Name("all"), ALLOY)
    inner_local = (0.0, -s, 0.0)                          # local inner-face normal (box is still axis aligned here)
    for fi in range(1, int(rt.polyop.getNumFaces(n)) + 1):
        nn = rt.polyop.getFaceNormal(n, fi)
        if vdot((nn.x, nn.y, nn.z), inner_local) > 0.95: rt.polyop.setFaceMatID(n, fi, ACCENT)
    n.transform = mtx(d, y, z, (mid[0], mid[1], -BLADE_H/2.0))
    PARTS.append(n)
    return n

# ---------------------------------------------------------------- geometry
def build_geometry():
    # ---- butt cap (8-sided, dia 16) + conduit inlet boss
    xcyl(ALLOY, -24.0, -20.0, 8.0, sides=8, fil=0.6)
    xcyl(ALLOY, -26.0, -24.0, 3.0, sides=12, fil=0.4)
    # ---- mount collar: dia 12 rims + grip section (4 clamp flats 2 deep => 8 x 8) over X -13..+13
    xcyl(ALLOY, -20.0, -13.0, 6.0, sides=12, fil=0.6)
    xcyl(ALLOY, 13.0, 20.0, 6.0, sides=12, fil=0.6)
    cbox(ALLOY, -13.0, 13.0, -4.0, 4.0, -4.0, 4.0, fil=1.3, seg=2)
    # ---- capacitor bank: hex prism 18 across flats (flats up/down), 3 coil bands, 4 window slots
    xcyl(ALLOY, 20.0, 60.0, 9.0/math.cos(math.radians(30)), sides=6, fil=0.6, roll=30.0)
    for xc in (30.0, 40.0, 50.0):
        xband(COIL, xc-1.2, xc+1.2, 10.0, 11.0, sides=24)
    for xc in (30.0, 40.0, 50.0):
        for sy in (1, -1):
            cbox(COIL, xc-3.0, xc+3.0, *sorted((sy*9.6, sy*10.6)), -2.5, 2.5, fil=0.3, seg=1)   # exposed coil windows
    # ---- power conduit feeds: two dia-3 hoses on the underside + 3 clips each
    for sy in (1, -1):
        y = sy*3.5
        pts = [(-22.0, y, -7.5), (18.0, y, -7.5), (24.0, y, -10.6), (55.0, y, -10.6)]
        for a, b in zip(pts[:-1], pts[1:]): ccyl(COIL, a, b, 1.5, sides=8, fil=0.3, seg=1)
        for xc, zc in ((-12.0, -7.5), (8.0, -7.5), (40.0, -10.6)):
            xcyl(ALLOY, xc-0.8, xc+0.8, 2.4, y=y, z=zc, sides=8, fil=0.2, seg=1)
    # ---- shaft dia 9 (12-sided) + 3 reinforcement brackets (ring dia 13 x 4, 4 gussets)
    xcyl(ALLOY, 60.0, 200.0, 4.5, sides=12, fil=0.5)
    for xc in (95.0, 130.0, 165.0):
        xcyl(ALLOY, xc-2.0, xc+2.0, 6.5, sides=12, fil=0.4)
        for k in range(4):
            a = math.radians(k*90.0 + 45.0)
            rm = 5.5
            ym, zm = rm*math.cos(a), rm*math.sin(a)
            ccyl(ALLOY, (xc-4.0, ym, zm), (xc+4.0, ym, zm), 0.9, sides=4, fil=0.1, seg=1)
    # ---- emitter coil: 8 turns on a core, X +195..+205 (dia 18)
    xcyl(ALLOY, 195.0, 205.0, 7.2, sides=12, fil=0.4)
    for k in range(8):
        xtorus(COIL, 195.6 + k*(8.8/7.0), 8.1, 0.6, seg=20, sides=5)
    # ---- insulator collar + twin electrode blades (V, inner faces emissive)
    xcyl(ALLOY, 205.0, 214.0, 8.0, sides=12, fil=0.6)
    blade(+1); blade(-1)

# ---------------------------------------------------------------- collision (convex hulls)
def hull3d(pts, eps=1e-3):
    n = len(pts); planes = []
    for i in range(n):
        for j in range(i+1, n):
            for k in range(j+1, n):
                nv = vcross(vsub(pts[j], pts[i]), vsub(pts[k], pts[i])); l = vlen(nv)
                if l < 1e-6: continue
                nv = vmul(nv, 1.0/l); d = vdot(nv, pts[i])
                sd = [vdot(nv, p) - d for p in pts]
                if max(sd) <= eps: pass
                elif min(sd) >= -eps: nv, d = vmul(nv, -1.0), -d
                else: continue
                if any(vdot(nv, q[0]) > 0.99999 and abs(d - q[1]) < 1e-2 for q in planes): continue
                planes.append((nv, d))
    faces = []
    for (nv, d) in planes:
        idx = [i for i, p in enumerate(pts) if abs(vdot(nv, p) - d) < 1e-2]
        c = vmul(tuple(map(sum, zip(*[pts[i] for i in idx]))), 1.0/len(idx))
        u = vnorm(vsub(pts[idx[0]], c)); w = vcross(nv, u)
        idx.sort(key=lambda i: math.atan2(vdot(vsub(pts[i], c), w), vdot(vsub(pts[i], c), u)))
        for m in range(1, len(idx)-1): faces.append((idx[0], idx[m], idx[m+1]))
    return planes, faces

def prism(x0, x1, R, sides, phase=0.0):
    ring = [(R*math.cos(math.radians(phase + i*360.0/sides)), R*math.sin(math.radians(phase + i*360.0/sides))) for i in range(sides)]
    return [(x0, y, z) for (y, z) in ring] + [(x1, y, z) for (y, z) in ring]

def box_pts(x0, x1, y0, y1, z0, z1):
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

def ucx_defs():
    ye = BLADE_E_Y + BLADE_T                     # outer face at the tip (~15)
    return [
        # 00 collar prism: butt + collar + capacitor bank (12-sided prism, 24 verts)
        (UCX_NAMES[0], prism(X_MIN, 60.0, UCX_COLLAR_R, 12, 15.0)),
        # 01 shaft box (tapered, 8 verts): shaft + brackets + emitter coil + insulator collar (half-width 6.5 @X60 -> 8.0 @X214)
        (UCX_NAMES[1], [(x, sy*h, sz*h) for (x, h) in ((60.0, 6.5), (214.0, 8.0)) for sy in (1, -1) for sz in (1, -1)]),
        # 02 / 03 prong boxes (electrode blades, one per side; 8 verts each)
        (UCX_NAMES[2], box_pts(BLADE_A_X, X_MAX, BLADE_A_Y, ye, -BLADE_H/2.0, BLADE_H/2.0)),     # L  (+Y)
        (UCX_NAMES[3], box_pts(BLADE_A_X, X_MAX, -ye, -BLADE_A_Y, -BLADE_H/2.0, BLADE_H/2.0)),   # R  (-Y)
    ]

def build_collision():
    out = []
    for name, pts in ucx_defs():
        planes, faces = hull3d(pts)
        m = rt.mesh(vertices=[P(p) for p in pts], faces=[rt.Point3(f[0]+1, f[1]+1, f[2]+1) for f in faces])
        m.name = name; m.wirecolor = rt.Color(255, 60, 60)
        out.append((m, pts, planes, faces))
    return out

def inside(planes, p, tol=0.3):
    return all(vdot(nv, p) - d <= tol for nv, d in planes)

# ---------------------------------------------------------------- sockets
def define_sockets():
    ytip = lambda x: BLADE_A_Y + (BLADE_E_Y - BLADE_A_Y) * (x - BLADE_A_X) / (BLADE_E_X - BLADE_A_X)
    xa = 255.0
    SOCK["SOCKET_Mount_Base"] = {"pos": (0.0, 0.0, 0.0), "x": (1, 0, 0), "z": (0, 0, 1)}
    # arc endpoints on the inner faces of the prongs; +X = emission direction (across the gap, toward the other prong)
    SOCK["SOCKET_Arc_Tip_L"] = {"pos": (xa, ytip(xa), 0.0), "x": (0, -1, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_Arc_Tip_R"] = {"pos": (xa, -ytip(xa), 0.0), "x": (0, 1, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_Strike_Trace_Start"] = {"pos": (170.0, 0.0, 0.0), "x": (1, 0, 0), "z": (0, 0, 1)}
    SOCK["SOCKET_Strike_Trace_End"] = {"pos": (X_MAX, 0.0, 0.0), "x": (1, 0, 0), "z": (0, 0, 1)}

# ---------------------------------------------------------------- MaxScript helpers
MXS = r'''
global pike_uv
fn pike_uv m = (
    max modify mode
    select m
    local uv = Unwrap_UVW()
    addModifier m uv
    modPanel.setCurrentObject uv
    uv.setMapChannel 1
    uv.flattenMap 45.0 #() 0.002 true 0 false true
    uv.selectOverlappedFaces()
    local ov = (uv.getSelectedFaces()).numberSet
    collapseStack m
    channelInfo.CopyChannel m 3 1
    channelInfo.PasteChannel m 3 2          -- UV1 (lightmap / bake) = same non-overlapping layout
    ov
)
'''

def settle_ui():
    rt.execute("max create mode")
    rt.windows.processPostedMessages()
    rt.completeRedraw()
    rt.windows.processPostedMessages()

def own(o):
    nm = str(o.name)
    return nm.startswith(PFX) or nm == ASSET or nm.startswith("UCX_" + ASSET) or nm.startswith("SOCKET_")

def prepare_scene():
    if str(rt.units.SystemType) != "centimeters" or abs(float(rt.units.SystemScale) - 1.0) > 1e-6:
        rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    cur = os.path.join(str(rt.maxFilePath), str(rt.maxFileName))
    foreign = [o for o in rt.objects if not own(o)]
    if foreign and os.path.normcase(cur) != os.path.normcase(MAX_PATH):
        if rt.getSaveRequired():
            raise RuntimeError("Scene has unsaved foreign content (%s) - save it first; build aborted." % cur)
        rt.resetMaxFile(rt.Name("noPrompt"))
        if str(rt.units.SystemType) != "centimeters":
            rt.units.SystemType = rt.Name("centimeters"); rt.units.SystemScale = 1.0
    for o in [o for o in rt.objects if own(o)]:
        try: rt.delete(o)
        except Exception: pass

# ---------------------------------------------------------------- build
def build():
    del PARTS[:]; SOCK.clear()
    prepare_scene()
    rt.execute(MXS)
    out = {"max_units": str(rt.units.SystemType)}
    MM = rt.execute('''(
        local mm = MultiMaterial numsubs:3 name:"MM_SigkillPike"
        mm.materialList[1] = PhysicalMaterial name:"MS_HardenedAlloy" base_color:(color 43 47 58) metalness:1.0 roughness:0.35
        mm.materialList[2] = PhysicalMaterial name:"MS_PowerCoil" base_color:(color 184 115 51) metalness:1.0 roughness:0.3 emit_color:(color 255 184 108) emission:0.5
        mm.materialList[3] = PhysicalMaterial name:"MS_AccentEmissive" base_color:(color 0 0 0) emit_color:(color 255 121 198) emission:2.0
        mm.names = #("MS_HardenedAlloy", "MS_PowerCoil", "MS_AccentEmissive")
        mm )''')
    build_geometry()
    nparts = len(PARTS)

    # single mesh, identity transform, pivot (0,0,0) = collar centre
    final = rt.Editable_Mesh(); final.name = ASSET
    rt.convertToPoly(final)
    for part in PARTS: rt.polyop.attach(final, part)
    final.material = MM
    rt.execute('(local m = getNodeByName "%s"; m.autoSmoothThreshold = 30.0; polyop.setFaceSelection m #all; m.EditablePoly.autosmooth(); polyop.setFaceSelection m #{})' % ASSET)
    out["uv_overlapping_faces"] = int(rt.pike_uv(final))

    # collision hulls
    hulls = build_collision()
    # sockets
    define_sockets()
    lay = rt.LayerManager.getLayerFromName(ASSET) or rt.LayerManager.newLayerFromName(ASSET)
    lay.addnode(final)
    for m, _, _, _ in hulls: lay.addnode(m)
    rl = rt.LayerManager.getLayerFromName("PIKE_Ref_Sockets") or rt.LayerManager.newLayerFromName("PIKE_Ref_Sockets")
    for k, sd in SOCK.items():
        x = vnorm(sd["x"]); z = vnorm(vsub(sd["z"], vmul(x, vdot(sd["z"], x)))); y = vcross(z, x)
        pt = rt.Point(name=k, size=12, box=True, cross=True, axistripod=True)
        pt.transform = mtx(x, y, z, sd["pos"]); pt.wirecolor = rt.Color(255, 40, 160)
        pt.parent = final
        rl.addnode(pt)

    # ---- stats / checks
    tm = rt.snapshotAsMesh(final)
    mat_ids = sorted(set(int(rt.getFaceMatID(tm, i)) for i in range(1, int(tm.numfaces) + 1)))
    nv = int(rt.polyop.getNumVerts(final))
    verts = []
    for i in range(1, nv + 1):
        v = rt.polyop.getVert(final, i); verts.append((float(v.x), float(v.y), float(v.z)))
    cov_all = 0; cov_core = 0; core_n = 0
    for p in verts:
        r = math.hypot(p[1], p[2]); is_core = (r <= 11.5 and X_MIN <= p[0] <= 215.0) or (p[0] > 200.0 and abs(p[1]) <= 15.2 and abs(p[2]) <= 11.2)
        ins = any(inside(h[2], p) for h in hulls)
        cov_all += 1 if ins else 0
        if is_core: core_n += 1; cov_core += 1 if ins else 0
    ucx_info = []
    for m, pts, planes, faces in hulls:
        ucx_info.append({"name": str(m.name), "verts": int(rt.getNumVerts(m)), "tris": len(faces), "planes": len(planes),
                         "bbox_min": [round(min(p[i] for p in pts), 2) for i in range(3)], "bbox_max": [round(max(p[i] for p in pts), 2) for i in range(3)]})
    bb_min = [round(float(final.min.x), 2), round(float(final.min.y), 2), round(float(final.min.z), 2)]
    bb_max = [round(float(final.max.x), 2), round(float(final.max.y), 2), round(float(final.max.z), 2)]
    out.update({
        "parts": nparts, "verts": int(tm.numverts), "tris": int(tm.numfaces), "mat_ids": mat_ids,
        "bbox_min": bb_min, "bbox_max": bb_max,
        "length_cm": round(bb_max[0] - bb_min[0], 2), "width_y_cm": round(bb_max[1] - bb_min[1], 2), "height_z_cm": round(bb_max[2] - bb_min[2], 2),
        "pivot": [round(float(final.pivot.x), 3), round(float(final.pivot.y), 3), round(float(final.pivot.z), 3)],
        "ucx": ucx_info, "ucx_count": len(hulls), "ucx_max_verts": max(u["verts"] for u in ucx_info),
        "verts_inside_ucx_union_pct": round(100.0*cov_all/max(nv, 1), 1),
        "core_verts_inside_ucx_pct": round(100.0*cov_core/max(core_n, 1), 1),
        "sockets": sorted(SOCK.keys()),
    })
    spec = {"asset": ASSET, "units": "cm",
            "space": "3ds Max RH Z-up, +X = butt->tip; UE import maps (x, y, z) -> (x, -y, z)",
            "slots": SLOTS, "ucx_names": UCX_NAMES,
            "sockets": {k: {"pos": [round(c, 3) for c in v["pos"]], "x": [round(c, 6) for c in v["x"]], "z": list(v["z"])} for k, v in SOCK.items()},
            "stats": out}
    with open(JSON_PATH, "w") as f: json.dump(spec, f, indent=2)

    rt.select(final)
    for m, _, _, _ in hulls: rt.selectMore(m)
    settle_ui()
    os.makedirs(os.path.dirname(MAX_PATH), exist_ok=True)
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)
    out["max_saved"] = MAX_PATH if os.path.exists(MAX_PATH) else None
    return out

def export_and_resave():
    rt.select(rt.getNodeByName(ASSET))
    for n in UCX_NAMES: rt.selectMore(rt.getNodeByName(n))
    rt.execute('''(
        FBXExporterSetParam "ResetExport"
        FBXExporterSetParam "SmoothingGroups" true
        FBXExporterSetParam "Triangulate" false
        FBXExporterSetParam "Animation" false
        FBXExporterSetParam "Cameras" false
        FBXExporterSetParam "Lights" false
        FBXExporterSetParam "EmbedTextures" false
        FBXExporterSetParam "ConvertUnit" "cm"
        FBXExporterSetParam "UpAxis" "Z"
        FBXExporterSetParam "ASCII" false
    )''')
    os.makedirs(os.path.dirname(FBX_PATH), exist_ok=True)
    ok = rt.exportFile(FBX_PATH, rt.Name("noPrompt"), selectedOnly=True, using=rt.FBXEXP)
    settle_ui()
    rt.saveMaxFile(MAX_PATH, clearNeedSaveFlag=True, useNewFile=True, quiet=True)
    rt.setSaveRequired(False)
    return {"fbx": FBX_PATH if ok and os.path.exists(FBX_PATH) else None,
            "fbx_bytes": os.path.getsize(FBX_PATH) if os.path.exists(FBX_PATH) else 0}

GUARD_MXS = r'''
global pike_guard_timer
fn pike_guard_tick s e = (
    s.Stop()
    if (maxFilePath + maxFileName) == @"%s" and getSaveRequired() do
        saveMaxFile (maxFilePath + maxFileName) clearNeedSaveFlag:true useNewFile:true quiet:true
    setSaveRequired false
    dotNet.removeAllEventHandlers s
)
pike_guard_timer = dotNetObject "System.Windows.Forms.Timer"
pike_guard_timer.Interval = 1500
dotNet.addEventHandler pike_guard_timer "Tick" pike_guard_tick
pike_guard_timer.Start()
''' % MAX_PATH

PIKE_RESULT = build()
if globals().get("PIKE_EXPORT", True):
    PIKE_RESULT["export"] = export_and_resave()
rt.execute(GUARD_MXS)
