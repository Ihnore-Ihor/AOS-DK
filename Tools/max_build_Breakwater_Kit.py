# =============================================================================
# AOS-DK | Surface Pontoon Atoll, Stage 2A: Outer Damping Breakwater Ring (BW) | 3ds Max 2027 (pymxs) -> FBX -> UE 5.7.4
# AOS_PontoonHub_Urban_Bible §2.2 (perimeter geometry, mooring), §2.6 (dry holds), §5.1 M-16, §5.4.
# Reuses the mesh builder / Max layer of Tools/max_build_Atoll_Kit.py as a library (closed chamfered solids, convex UCX
# hulls <= 32 verts, box UVW 1 UV = 200 cm, meshes authored in UE-local space and mirrored in Y for Max).
# Writes Tools/Breakwater_Kit_spec.json (mesh stats + ring / pipe / mooring assembly table) = single source for
# Tools/ue_build_Breakwater.py.  No geometry is generated in Unreal.
#
# Live anchor: the ring is centred on the built Atoll city in Lvl_FirstPerson, C = (-1000, 700, 0), NOT the Bible S (-60000, 0).
# Local axes of every perimeter module: +X = along the side (tangent), +Y = seaward, Z 0 = Bible water mark 0 (live ocean Z = 40).
# Deviations from the Bible (measured in 5.7.4, see the Stage 2A report):
#   * AWaterBodyExclusionVolume does not cut the ocean surface mesh, so the visible compressor bay under the hatches has a
#     sealed floor at Z +560 (above the swell) instead of the -1000 hold floor; the hull below it is solid.
#   * SM_BW_PorousCurtain is a 1 600 module (3 per full hull, 1 per short hull) instead of a 4 800 mesh + a scaled short one.
#   * SM_Mooring_Link is a 343.75 segment of 4 stud-less links (bar 18): 64 segments = one 22 000 line (Bible: 64 samples per line).
#
# Run in Max:  ns = {}; exec(open(r"<proj>\Tools\max_build_Breakwater_Kit.py", encoding="utf-8").read(), ns)
#              ns["build"]()  -> per-asset stats, writes the spec JSON, saves SourceArt/Atoll/Breakwater_Kit.max
#              ns["export"]() -> one FBX per asset in Content/AOS_DK_Game/Environment/Atoll/Breakwater
# Headless (no Max): python max_build_Breakwater_Kit.py  -> builder self-test + spec JSON
# =============================================================================
import math, json, os

PROJ = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK"
if not os.path.isdir(PROJ): PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # headless run from a mounted copy
FBX_DIR = os.path.join(PROJ, "Content", "AOS_DK_Game", "Environment", "Atoll", "Breakwater")
SPEC_PATH = os.path.join(PROJ, "Tools", "Breakwater_Kit_spec.json")
MAX_PATH = os.path.join(PROJ, "SourceArt", "Atoll", "Breakwater_Kit.max")

AK = {"__name__": "ak_lib"}
exec(compile(open(os.path.join(PROJ, "Tools", "max_build_Atoll_Kit.py"), encoding="utf-8").read(), "max_build_Atoll_Kit.py", "exec"), AK)
rt = AK["rt"]
I, cbox, cyl, lathe, ring, cprism, zfr, yawfr, Kit = AK["I"], AK["cbox"], AK["cyl"], AK["lathe"], AK["ring"], AK["cprism"], AK["zfr"], AK["yawfr"], AK["Kit"]
rad = math.radians

# new slots (Max preview colour, metalness, roughness, emission); the rest come from the Atoll SLOT_CAT
BW_SLOTS = {
    "MS_Fouled": ((38, 52, 40), 0.2, 0.90, None),       # below-waterline steel, biofouled
    "MS_Concrete": ((128, 126, 118), 0.0, 0.92, None),  # caisson shaft, curtain ballast
    "MS_HDPE": ((18, 24, 20), 0.0, 0.55, None),         # M-16 black HDPE pipe, biofouled
    "MS_Sled": ((110, 108, 100), 0.0, 0.95, None),      # M-16 concrete weights
    "MS_Chain": ((74, 46, 34), 0.8, 0.75, None),        # mooring chain, rusted
}
AK["SLOT_CAT"].update(BW_SLOTS)
SLOT_CAT = AK["SLOT_CAT"]

# ---------------------------------------------------------------- ring constants (world cm)
CENTER = (-1000.0, 700.0, 0.0)                 # live Atoll city centre (ChargingZone_Dock / Moonpool berth)
APOTHEM = 12000.0
R_VERT = APOTHEM/math.cos(rad(15.0))           # 12 423.3
SIDE = 2.0*APOTHEM*math.tan(rad(15.0))         # 6 430.8
GATES = (180.0, 60.0, 300.0)                   # side azimuths with a 1 600 fairway
GATE_W = 1600.0
HULL_L, SHORT_L, HULL_W = 4800.0, 1600.0, 1400.0
Z_KEEL, Z_DECK, Z_BAY, Z_CURT = -1400.0, 1200.0, 560.0, -4200.0
RING_R, RING_N, RING_Z = 11000.0, 70, -800.0   # BC-R Taylor ring
GATE_PIPE_Z, GATE_PIPE_OUT = -1800.0, 120.0    # gate pipes run 120 seaward of the curtain plane (their 200 extensions pass beside the curtains)
SLAB_Z = -18000.0                              # KikutakeSlab_Tiles top (measured)
ANCHOR_R = 24000.0
FAIRLEAD = (880.0, 0.0, -600.0)                # node-local
SEG_N, SLACK = 64, 1.05
LINKS, BAR = 4, 18.0

# ================================================================= builders (UE-local cm)
HSEC = [(-535.0, Z_KEEL), (535.0, Z_KEEL), (685.0, -1250.0), (685.0, 100.0), (-685.0, 100.0), (-685.0, -1250.0)]
UCX_SEC = [(-535.0, Z_KEEL), (535.0, Z_KEEL), (700.0, -1250.0), (700.0, Z_DECK), (-700.0, Z_DECK), (-700.0, -1250.0)]

def tlcd(k, xc):
    """Tuned liquid column damper: U-tube across the beam (2 columns + cross duct, liquid column ~2 000) with an air crossover."""
    mb = k.mb
    for y in (-430.0, 430.0):
        cyl(mb, "MS_Tin", (xc, y, Z_DECK), (xc, y, Z_DECK+280.0), 120.0, 14, 6.0)
        cyl(mb, "MS_Hazard", (xc, y, Z_DECK+280.0), (xc, y, Z_DECK+300.0), 126.0, 14, 3.0)
        cyl(mb, "MS_Pipe", (xc, y, Z_DECK+300.0), (xc, y, Z_DECK+352.0), 22.0, 8, 2.0)
    cyl(mb, "MS_Tin", (xc, -430.0, Z_DECK+95.0), (xc, 430.0, Z_DECK+95.0), 80.0, 12, 4.0)
    cyl(mb, "MS_Pipe", (xc, -452.0, Z_DECK+340.0), (xc, 452.0, Z_DECK+340.0), 22.0, 8, 2.0)
    k.ucx_box(xc-130.0, xc+130.0, -560.0, 560.0, Z_DECK, Z_DECK+300.0)

def bay(k, hc):
    """Taylor compressor set on the bay floor, centred under a 600 x 600 hatch."""
    mb = k.mb
    cbox(mb, "MS_Trim", I, hc-270.0, hc+270.0, -230.0, 250.0, Z_BAY+6.0, Z_BAY+30.0, 2.0)
    cbox(mb, "MS_Yellow", I, hc-235.0, hc-20.0, -190.0, 50.0, Z_BAY+30.0, Z_BAY+290.0, 6.0)
    cbox(mb, "MS_Status", I, hc-200.0, hc-55.0, -150.0, -128.0, Z_BAY+290.0, Z_BAY+296.0, 1.0)
    cyl(mb, "MS_Chassis", (hc-5.0, -70.0, Z_BAY+160.0), (hc+245.0, -70.0, Z_BAY+160.0), 88.0, 12, 5.0)
    cyl(mb, "MS_Tin", (hc-240.0, 150.0, Z_BAY+125.0), (hc+240.0, 150.0, Z_BAY+125.0), 82.0, 12, 6.0)
    cyl(mb, "MS_Pipe", (hc+205.0, 245.0, Z_BAY+6.0), (hc+205.0, 245.0, Z_DECK-100.0), 22.0, 8, 0.0)
    cyl(mb, "MS_Pipe", (hc-120.0, -70.0, Z_BAY+290.0), (hc-120.0, 150.0, Z_BAY+215.0), 16.0, 8, 0.0)

def hull(k, L, hatches, tlcds, masts):
    mb = k.mb; hx = L/2.0
    cprism(mb, "MS_Fouled", I, HSEC, -hx, hx, 6.0)                                   # wetted hull, bilge chamfer 150
    cbox(mb, "MS_Corten", I, -hx, hx, -685.0, 685.0, 100.0, Z_BAY, 4.0)              # topsides, solid up to the bay floor
    cbox(mb, "MS_Stair", I, -hx+100.0, hx-100.0, -585.0, 585.0, Z_BAY, Z_BAY+6.0, 0.0)   # bay floor plate
    for s in (-1.0, 1.0):
        cbox(mb, "MS_Corten", I, -hx, hx, s*585.0, s*685.0, Z_BAY, Z_DECK-100.0, 3.0)                    # side shell
        cbox(mb, "MS_Corten", I, s*(hx-100.0), s*hx, -585.0, 585.0, Z_BAY, Z_DECK-100.0, 3.0)            # end bulkheads
        cbox(mb, "MS_Fender", I, -hx+20.0, hx-20.0, s*685.0, s*700.0, 270.0, 340.0, 4.0)                 # rubbing strake
        n = int(round((L-400.0)/600.0))
        for i in range(n+1):
            x = -hx+200.0+(L-400.0)*i/n
            cbox(mb, "MS_Trim", I, x-10.0, x+10.0, s*685.0, s*697.0, 350.0, Z_DECK-10.0, 2.0)            # shell frames
    # deck plate around the open hatches
    xs = [-hx]
    for hc in hatches: xs += [hc-300.0, hc+300.0]
    xs.append(hx)
    for i in range(0, len(xs), 2): cbox(mb, "MS_Deck", I, xs[i], xs[i+1], -685.0, 685.0, Z_DECK-100.0, Z_DECK, 2.0)
    for hc in hatches:
        for s in (-1.0, 1.0):
            cbox(mb, "MS_Deck", I, hc-300.0, hc+300.0, s*300.0, s*685.0, Z_DECK-100.0, Z_DECK, 2.0)
            cbox(mb, "MS_Hazard", I, hc-330.0, hc+330.0, s*300.0, s*330.0, Z_DECK, Z_DECK+50.0, 2.0)     # coamings
            cbox(mb, "MS_Hazard", I, hc+s*300.0, hc+s*330.0, -300.0, 300.0, Z_DECK, Z_DECK+50.0, 2.0)
            cbox(mb, "MS_Corten", I, hc+s*330.0, hc+s*344.0, -300.0, 300.0, Z_DECK+50.0, Z_DECK+350.0, 2.0)   # butterfly lid leaf, open
        bay(k, hc)
    cbox(mb, "MS_Corten", I, -hx, hx, 655.0, 685.0, Z_DECK, Z_DECK+110.0, 3.0)       # seaward bulwark
    cbox(mb, "MS_Trim", I, -hx, hx, -685.0, -670.0, Z_DECK, Z_DECK+25.0, 2.0)        # harbour-side toe rail
    for xc in tlcds: tlcd(k, xc)
    x0 = max([abs(h)+330.0 for h in hatches])
    if tlcds and min(abs(t) for t in tlcds)-150.0 > x0+200.0:                         # air mains between the dampers (full hull)
        xr = min(abs(t) for t in tlcds)-170.0
        for (y, z) in ((500.0, Z_DECK+60.0), (560.0, Z_DECK+60.0)): cyl(mb, "MS_Pipe", (-xr, y, z), (xr, y, z), 22.0, 8, 2.0)
        n = int(xr//400.0)
        for i in range(-n, n+1): cbox(mb, "MS_Trim", I, i*400.0-8.0, i*400.0+8.0, 470.0, 590.0, Z_DECK, Z_DECK+38.0, 1.0)
    for s in (-1.0, 1.0):
        cyl(mb, "MS_Trim", (s*(hx-150.0), -560.0, Z_DECK), (s*(hx-150.0), -560.0, Z_DECK+70.0), 28.0, 10, 3.0)   # bollards
    for (x, h) in masts:
        cyl(mb, "MS_Trim", (x, 610.0, Z_DECK+110.0), (x, 610.0, Z_DECK+h), 9.0, 8, 0.0)
        cyl(mb, "MS_Beacon", (x, 610.0, Z_DECK+h), (x, 610.0, Z_DECK+h+40.0), 22.0, 10, 4.0)
        k.socket("SOCKET_Light_Obstr_%02d" % len([s_ for s_ in k.sock if s_.startswith("SOCKET_Light")]), (x, 610.0, Z_DECK+h+20.0))
    k.ucx_pts([(x, y, z) for x in (-hx, hx) for (y, z) in UCX_SEC])
    for i, hc in enumerate(hatches): k.socket("SOCKET_Hatch_%02d" % i, (hc, 0.0, Z_DECK), z=(0, 0, 1))
    k.socket("SOCKET_Curtain", (0.0, 0.0, Z_KEEL)); k.socket("SOCKET_Hold_Center", (0.0, 0.0, -50.0))

def b_hull_a():
    k = Kit("BW full hull: converted tanker section 4 800 x 1 400, keel -1 400, deck +1 200; 2 open hatches with Taylor compressor bays, 2 TLCD U-tubes, air mains")
    hull(k, HULL_L, (-900.0, 900.0), (-1900.0, 1900.0), ((0.0, 420.0),)); return k
def b_hull_short():
    k = Kit("BW short hull flanking an ocean gate: 1 600 x 1 400; 1 open hatch, 2 TLCD U-tubes, gate marker masts")
    hull(k, SHORT_L, (0.0,), (-560.0, 560.0), ((-745.0, 520.0), (745.0, 520.0))); return k

def b_node():
    k = Kit("BW node caisson: 16-sided, dia 1 600, -1 400 .. +1 200; fender collar, bollards, chain stopper, fairlead at -600 on +X (seaward)")
    mb = k.mb; fr = zfr()
    lathe(mb, "MS_Fouled", fr, [(Z_KEEL, 0.0), (Z_KEEL, 760.0), (Z_KEEL+40.0, 800.0), (100.0, 800.0), (100.0, 0.0)], 16)
    lathe(mb, "MS_Concrete", fr, [(100.0, 0.0), (100.0, 780.0), (Z_DECK-100.0, 780.0), (Z_DECK-100.0, 0.0)], 16)
    ring(mb, "MS_Fender", fr, 180.0, 420.0, 770.0, 800.0, 16, 8.0)
    lathe(mb, "MS_Corten", fr, [(Z_DECK-100.0, 0.0), (Z_DECK-100.0, 800.0), (Z_DECK-10.0, 800.0), (Z_DECK, 790.0), (Z_DECK, 0.0)], 16)
    for i in range(8):
        f = yawfr((0.0, 0.0, 0.0), 22.5+45.0*i)
        cbox(mb, "MS_Corten", f, 760.0, 784.0, -18.0, 18.0, 420.0, Z_DECK-100.0, 2.0)
    for y in (-450.0, 450.0):
        cyl(mb, "MS_Trim", (0.0, y, Z_DECK), (0.0, y, Z_DECK+110.0), 45.0, 12, 4.0)
        cyl(mb, "MS_Trim", (0.0, y, Z_DECK+110.0), (0.0, y, Z_DECK+132.0), 62.0, 12, 5.0)
    cbox(mb, "MS_Yellow", I, 380.0, 650.0, -130.0, 130.0, Z_DECK, Z_DECK+160.0, 6.0)          # chain stopper / tensioner
    cbox(mb, "MS_Trim", I, 650.0, 800.0, -50.0, 50.0, Z_DECK, Z_DECK+60.0, 4.0)
    cbox(mb, "MS_Trim", I, 778.0, 850.0, -45.0, 45.0, -640.0, Z_DECK+60.0, 4.0)                # chain trunk down the seaward face
    cbox(mb, "MS_Trim", I, 770.0, 880.0, -80.0, 80.0, -680.0, -540.0, 8.0)                     # fairlead block
    cyl(mb, "MS_Trim", (0.0, 0.0, Z_DECK), (0.0, 0.0, Z_DECK+320.0), 10.0, 8, 0.0)
    cyl(mb, "MS_Beacon", (0.0, 0.0, Z_DECK+320.0), (0.0, 0.0, Z_DECK+360.0), 24.0, 10, 4.0)
    k.ucx_prism([(800.0*math.cos(rad(22.5*i)), 800.0*math.sin(rad(22.5*i))) for i in range(16)], Z_KEEL, Z_DECK)
    k.socket("SOCKET_Fairlead", FAIRLEAD, x=(0.5, 0.0, -0.85)); k.socket("SOCKET_Light_Obstr", (0.0, 0.0, Z_DECK+340.0))
    return k

def b_curtain():
    k = Kit("Jarlan porous curtain module 1 600 x 2 800 hung under a hull: -1 400 .. -4 200, 13 slats, porosity 25 %, concrete ballast beam")
    mb = k.mb; hx = SHORT_L/2.0
    cbox(mb, "MS_Trim", I, -hx, hx, -30.0, 30.0, Z_KEEL-80.0, Z_KEEL, 3.0)
    for i in range(13):
        z1 = -1500.0-197.0*i
        cbox(mb, "MS_Fouled", I, -hx, hx, -20.0, 20.0, z1-148.0, z1, 3.0)
    for x in (-770.0, -260.0, 260.0, 770.0):
        cbox(mb, "MS_Corten", I, x-30.0, x+30.0, -45.0, 45.0, -4040.0, Z_KEEL-80.0, 3.0)
    cbox(mb, "MS_Concrete", I, -hx, hx, -70.0, 70.0, Z_CURT, -4040.0, 8.0)
    k.ucx_box(-hx, hx, -20.0, 20.0, Z_CURT, Z_KEEL)
    k.socket("SOCKET_Snap_W", (-hx, 0.0, Z_KEEL), x=(-1, 0, 0)); k.socket("SOCKET_Snap_E", (hx, 0.0, Z_KEEL))
    return k

def b_taylor_pipe():
    k = Kit("M-16 Taylor bubble pipe 100 x 1 000 x 50: perforated HDPE pipe on two concrete saddle weights; pivot = centre of the pipe axis, axis = Y")
    mb = k.mb
    cyl(mb, "MS_HDPE", (0.0, -500.0, 0.0), (0.0, 500.0, 0.0), 23.0, 12, 2.0)
    for (y0, y1) in ((-500.0, -472.0), (-14.0, 14.0), (472.0, 500.0)): cyl(mb, "MS_Trim", (0.0, y0, 0.0), (0.0, y1, 0.0), 25.0, 12, 1.5)
    for y in (-300.0, 300.0): cbox(mb, "MS_Sled", I, -50.0, 50.0, y-70.0, y+70.0, -25.0, 8.0, 3.0)
    for i in range(10):
        y = -450.0+100.0*i
        cyl(mb, "MS_Trim", (0.0, y, 19.0), (0.0, y, 25.0), 5.0, 6, 0.0)
        k.socket("SOCKET_Emit_%02d" % i, (0.0, y, 25.0), x=(0, 0, 1), z=(0, 1, 0))
    k.ucx_box(-50.0, 50.0, -500.0, 500.0, -25.0, 25.0)
    k.socket("SOCKET_Snap_N", (0.0, 500.0, 0.0), x=(0, 1, 0)); k.socket("SOCKET_Snap_S", (0.0, -500.0, 0.0), x=(0, -1, 0))
    return k

SEG_LEN = 22000.0/SEG_N                                            # 343.75
def chain_link(mb, mat, cx, roll, pitch, d, sides=6, arc=5):
    """One stud-less link: stadium tube, long axis X, plane rolled about X."""
    a = (pitch+d)/2.0; rc = 1.2*d; st = a-rc; rb = d/2.0
    cr, sr = math.cos(roll), math.sin(roll)
    path = [(st+rc*math.cos(-math.pi/2+math.pi*i/arc), rc*math.sin(-math.pi/2+math.pi*i/arc)) for i in range(arc+1)]
    path += [(-st+rc*math.cos(math.pi/2+math.pi*i/arc), rc*math.sin(math.pi/2+math.pi*i/arc)) for i in range(arc+1)]
    n = len(path); R = []
    W = lambda x, v, w: (cx+x, v*cr-w*sr, v*sr+w*cr)
    for i in range(n):
        p0, p1 = path[i-1], path[(i+1) % n]
        tx, tv = p1[0]-p0[0], p1[1]-p0[1]; l = math.hypot(tx, tv); nx, nv = tv/l, -tx/l          # in-plane normal (outward for a CCW loop)
        R.append([mb.av(W(path[i][0]+rb*math.cos(2*math.pi*j/sides)*nx, path[i][1]+rb*math.cos(2*math.pi*j/sides)*nv, rb*math.sin(2*math.pi*j/sides))) for j in range(sides)])
    mb.begin()
    for i in range(n):
        i2 = (i+1) % n
        c = W((path[i][0]+path[i2][0])/2.0, (path[i][1]+path[i2][1])/2.0, 0.0)
        for j in range(sides):
            j2 = (j+1) % sides; q = [R[i][j], R[i][j2], R[i2][j2], R[i2][j]]
            m = AK["vmid"]([mb.v[x] for x in q])
            mb.poly(q, mat, 1, AK["vsub"](m, c))
    mb.end()

def b_mooring_link():
    k = Kit("Mooring chain segment 343.75: 4 stud-less links (bar 18, pitch 85.94), +X = down the line; 64 instances = one 22 000 semi-taut line")
    p = SEG_LEN/LINKS
    for i in range(LINKS): chain_link(k.mb, "MS_Chain", p*(i+0.5), rad(90.0*(i % 2)), p, BAR)
    k.ucx_pts([(x, 36.0*math.cos(rad(45.0*j+22.5)), 36.0*math.sin(rad(45.0*j+22.5))) for x in (0.0, SEG_LEN) for j in range(8)])
    k.socket("SOCKET_Snap_A", (0.0, 0.0, 0.0), x=(-1, 0, 0)); k.socket("SOCKET_Snap_B", (SEG_LEN, 0.0, 0.0))
    return k

# name, Bible ref, builder, Max scene offset
ASSETS = [
    ("SM_BW_Node", "2.2 / 5.4", b_node, (0.0, 0.0, 0.0)),
    ("SM_BW_Hull_A", "2.2 / 5.4", b_hull_a, (4500.0, 0.0, 0.0)),
    ("SM_BW_Hull_Short", "2.2 / 5.4", b_hull_short, (9000.0, 0.0, 0.0)),
    ("SM_BW_PorousCurtain", "2.2 / 5.4", b_curtain, (9000.0, 0.0, -400.0)),
    ("SM_Taylor_Pipe", "5.1 M-16", b_taylor_pipe, (0.0, -2500.0, 0.0)),
    ("SM_Mooring_Link", "2.2 / 5.4", b_mooring_link, (1500.0, -2500.0, 0.0)),
]
ASSET_IDX = {a[0]: a for a in ASSETS}

# ================================================================= assembly (world cm) -> spec
def pol(r, az, z=0.0, c=CENTER): return (c[0]+r*math.cos(rad(az)), c[1]+r*math.sin(rad(az)), c[2]+z)
def wrap(a): return (a+180.0) % 360.0-180.0

def catenary(A, B, L, n):
    """n+1 points, uniform in arc length, of a chain of length L hanging from A to B (never below B: it would lie on the slab)."""
    h = math.hypot(B[0]-A[0], B[1]-A[1]); v = A[2]-B[2]
    lo, hi = 10.0, 1e7; tgt = math.sqrt(L*L-v*v)
    for _ in range(200):
        a = (lo+hi)/2.0
        if 2.0*a*math.sinh(h/(2.0*a)) > tgt: lo = a
        else: hi = a
    x0 = h/2.0+a*math.atanh(v/L); s0 = math.sinh(x0/a); c0 = math.cosh(x0/a)
    ux, uy = (B[0]-A[0])/h, (B[1]-A[1])/h; pts = []
    for i in range(n+1):
        s = L*i/n; x = x0-a*math.asinh(s0-s/a); z = A[2]+a*(math.cosh((x-x0)/a)-c0)
        pts.append((A[0]+ux*x, A[1]+uy*x, max(z, B[2])))
    pts[0], pts[-1] = tuple(A), tuple(B)
    return pts, a, x0 >= h

def assembly():
    nodes, hulls, shorts, curt, gpipes, evs, gates = [], [], [], [], [], [], []
    for kx in range(12):
        az = 15.0+30.0*kx; p = pol(R_VERT, az); nodes.append([p[0], p[1], 0.0, wrap(az), 0.0])
    for j in range(12):
        az = 30.0*j; mid = pol(APOTHEM, az); yaw = wrap(az-90.0); t = (math.sin(rad(az)), -math.cos(rad(az)))      # local +X
        at = lambda s, out=0.0, z=0.0: [mid[0]+t[0]*s+out*math.cos(rad(az)), mid[1]+t[1]*s+out*math.sin(rad(az)), z]
        if az in GATES:
            for s in (-1600.0, 1600.0):
                shorts.append(at(s)+[yaw, 0.0]); curt.append(at(s)+[yaw, 0.0])
                evs.append({"label": "EV_BW_Hold_S_%02d" % (len([e for e in evs if "_S_" in e["label"]])+1), "loc": at(s, 0.0, -50.0), "yaw": yaw, "size": [1300.0, 1200.0, 2300.0]})
            for s in (-500.0, 500.0): gpipes.append(at(s, GATE_PIPE_OUT, GATE_PIPE_Z)+[wrap(az), 0.0])
            gates.append({"az": az, "mid": [mid[0], mid[1]], "dir": [math.cos(rad(az)), math.sin(rad(az))], "clear": GATE_W})
        else:
            hulls.append(at(0.0)+[yaw, 0.0])
            for s in (-1600.0, 0.0, 1600.0): curt.append(at(s)+[yaw, 0.0])
            evs.append({"label": "EV_BW_Hold_A_%02d" % (len(hulls)), "loc": at(0.0, 0.0, -50.0), "yaw": yaw, "size": [4400.0, 1200.0, 2300.0]})
    rpipes = []
    for i in range(RING_N):
        az = (i+0.5)*360.0/RING_N; p = pol(RING_R*math.cos(math.pi/RING_N), az, RING_Z); rpipes.append([p[0], p[1], p[2], wrap(az), 0.0])
    lines, upper, lower = [], [], []
    for kx in range(12):
        az = 15.0+30.0*kx
        A = pol(R_VERT+FAIRLEAD[0], az, FAIRLEAD[2]); B = pol(ANCHOR_R, az, SLAB_Z)
        straight = math.dist(A, B); pts, a, mono = catenary(A, B, SLACK*straight, SEG_N)
        for i in range(SEG_N):
            p, q = pts[i], pts[i+1]; d = (q[0]-p[0], q[1]-p[1], q[2]-p[2]); l = math.sqrt(d[0]**2+d[1]**2+d[2]**2)
            row = [p[0], p[1], p[2], math.degrees(math.atan2(d[1], d[0])), math.degrees(math.asin(d[2]/l)), l/SEG_LEN]
            (upper if (p[2]+q[2])/2.0 >= -4500.0 else lower).append(row)
        lines.append({"id": "L%02d" % (kx+1), "az": az, "fairlead": list(A), "anchor": list(B), "straight": straight, "length": SLACK*straight, "catenary_a": a,
                      "monotonic": mono, "pts": [[round(c, 2) for c in p] for p in pts]})
    R6 = lambda rows: [[round(c, 4) for c in r] for r in rows]
    F = "Environment/Atoll/Breakwater"
    actors = [
        {"label": "BW_Nodes", "mesh": "SM_BW_Node", "folder": F+"/Perimeter", "instances": R6(nodes)},
        {"label": "BW_Hulls_A", "mesh": "SM_BW_Hull_A", "folder": F+"/Perimeter", "instances": R6(hulls)},
        {"label": "BW_Hulls_Short", "mesh": "SM_BW_Hull_Short", "folder": F+"/Perimeter", "instances": R6(shorts)},
        {"label": "BW_PorousCurtains", "mesh": "SM_BW_PorousCurtain", "folder": F+"/Perimeter", "instances": R6(curt)},
        {"label": "BW_TaylorPipes_Gates", "mesh": "SM_Taylor_Pipe", "folder": F+"/TaylorPipes", "instances": R6(gpipes)},
        {"label": "BW_TaylorPipes_RingBCR", "mesh": "SM_Taylor_Pipe", "folder": F+"/TaylorPipes", "instances": R6(rpipes)},
        {"label": "BW_Mooring_Surface", "mesh": "SM_Mooring_Link", "folder": F+"/Mooring", "instances": R6(upper), "note": "segments above Z -4 500 (Bible 1.7: DL_A0_Surface part)"},
        {"label": "BW_Mooring_Deep", "mesh": "SM_Mooring_Link", "folder": F+"/Mooring", "instances": R6(lower), "note": "segments below Z -4 500 (Bible 1.7: DL_A1_Crowns part)"},
    ]
    return {"center": list(CENTER), "apothem": APOTHEM, "r_vertex": R_VERT, "side": SIDE, "gates": gates, "gate_azimuths": list(GATES),
            "z": {"keel": Z_KEEL, "deck": Z_DECK, "bay_floor": Z_BAY, "curtain_bottom": Z_CURT, "ring_pipes": RING_Z, "gate_pipes": GATE_PIPE_Z, "slab_top": SLAB_Z, "fairlead": FAIRLEAD[2]},
            "ring": {"r": RING_R, "n": RING_N}, "anchor_r": ANCHOR_R, "seg_len": SEG_LEN, "actors": actors, "exclusion_volumes": evs, "mooring": lines,
            "folder": F, "counts": {a["label"]: len(a["instances"]) for a in actors}}

# ================================================================= spec / Max layer
def run_builder(name):
    k = ASSET_IDX[name][2]()
    k.slots = [s for s in SLOT_CAT if any(m == s for (_, m, _) in k.mb.f)]
    return k

def asset_record(name, k):
    bmin, bmax = k.mb.bbox(); tris = k.mb.tris()
    return {"bible": ASSET_IDX[name][1], "note": k.note, "nanite": True, "slots": k.slots, "verts": len(k.mb.v), "tris": len(tris), "prims": k.mb.prims,
            "open_edges": k.mb.open_edges(), "bbox_min": [round(c, 2) for c in bmin], "bbox_max": [round(c, 2) for c in bmax],
            "size": [round(bmax[i]-bmin[i], 2) for i in range(3)], "ucx": len(k.ucx), "ucx_max_verts": max(len(h[0]) for h in k.ucx),
            "ucx_bbox": [[round(min(p[i] for h in k.ucx for p in h[0]), 2) for i in range(3)], [round(max(p[i] for h in k.ucx for p in h[0]), 2) for i in range(3)]],
            "sockets": k.sock}

def spec_dict(records, extra=None):
    d = {"kit": "AOS_DK Atoll Breakwater Kit (Stage 2A)", "units": "cm",
         "space": "meshes authored in UE-local space; Max scene holds them mirrored in Y (FBX import maps (x, y, z) -> (x, -y, z))",
         "content": "/Game/AOS_DK_Game/Environment/Atoll/Breakwater", "materials": "/Game/AOS_DK_Game/Environment/Atoll/Materials",
         "max_file": MAX_PATH, "fbx_dir": FBX_DIR, "uv_tile_cm": AK["TILE"],
         "new_slots": {s: {"rgb": list(v[0]), "metallic": v[1], "roughness": v[2]} for s, v in BW_SLOTS.items()},
         "meshes": records, "assembly": assembly()}
    if extra: d.update(extra)
    return d

def build(names=None):
    names = list(names) if names else [a[0] for a in ASSETS]
    AK["MAX_PATH"], AK["FBX_DIR"], AK["ASSETS"], AK["ASSET_IDX"] = MAX_PATH, FBX_DIR, ASSETS, ASSET_IDX
    P3 = AK["P3"]
    AK["prepare_scene"](names); rt.execute(AK["MXS"])
    records = {}
    if os.path.exists(SPEC_PATH):
        try: records = json.load(open(SPEC_PATH, encoding="utf-8")).get("meshes", {})
        except Exception: records = {}
    out = {"max_units": str(rt.units.SystemType), "max_scale": float(rt.units.SystemScale)}
    for name in names:
        k = run_builder(name); rec = asset_record(name, k); k.mirror_y()
        node = AK["make_node"](name, k); ucx = AK["make_ucx"](name, k)
        for u in ucx:
            if int(rt.getNumVerts(u)) > AK["UCX_MAX"]: raise RuntimeError("%s has %d verts" % (u.name, int(rt.getNumVerts(u))))
        off = ASSET_IDX[name][3]; tm = rt.transMatrix(P3(off)); node.transform = tm
        for u in ucx: u.transform = tm
        lay = rt.LayerManager.getLayerFromName("BW_"+name) or rt.LayerManager.newLayerFromName("BW_"+name)
        lay.addnode(node)
        for u in ucx: lay.addnode(u)
        rl = rt.LayerManager.getLayerFromName("BW_Ref_Sockets") or rt.LayerManager.newLayerFromName("BW_Ref_Sockets")
        for sn, sd in k.sock.items():
            pt = rt.Point(name=AK["REF_PFX"]+name+"__"+sn, size=10, box=True, cross=True, axistripod=False)
            pt.pos = rt.Point3(sd["pos"][0]+off[0], -sd["pos"][1]+off[1], sd["pos"][2]+off[2]); pt.wirecolor = rt.Color(255, 40, 160); rl.addnode(pt)
        rec["max"] = {"verts": int(rt.polyop.getNumVerts(node)), "polys": int(rt.polyop.getNumFaces(node)), "open_edges": int(rt.polyop.getOpenEdges(node).numberSet),
                      "ucx_nodes": len(ucx), "ucx_verts": [int(rt.getNumVerts(u)) for u in ucx], "map_verts": int(rt.polyop.getNumMapVerts(node, 1))}
        records[name] = rec
        out[name] = {"tris": rec["tris"], "polys": rec["max"]["polys"], "open": rec["max"]["open_edges"], "ucx": len(ucx), "ucx_verts": rec["max"]["ucx_verts"], "size": rec["size"], "slots": len(rec["slots"])}
    with open(SPEC_PATH, "w", encoding="utf-8") as f: json.dump(spec_dict(records, {"max": {"units": out["max_units"], "scale": out["max_scale"]}}), f, indent=1)
    AK["save_scene"]()
    out["_max_saved"] = os.path.exists(MAX_PATH); out["_dirty"] = bool(rt.getSaveRequired())
    return out

def export(names=None):
    AK["MAX_PATH"], AK["FBX_DIR"], AK["ASSETS"], AK["ASSET_IDX"] = MAX_PATH, FBX_DIR, ASSETS, ASSET_IDX
    return AK["export"](list(names) if names else [a[0] for a in ASSETS])

def selftest():
    out = {}
    for name in ASSET_IDX:
        k = run_builder(name); r = asset_record(name, k)
        out[name] = {x: r[x] for x in ("tris", "prims", "open_edges", "bbox_min", "bbox_max", "size", "ucx", "ucx_max_verts", "slots")}
        assert r["open_edges"] == 0 and r["ucx_max_verts"] <= 32, name
    return out

if __name__ == "__main__":
    st = selftest()
    for n, r in st.items(): print(n, json.dumps(r))
    A = assembly(); print(A["counts"]); print([(l["id"], round(l["straight"]), round(l["catenary_a"]), l["monotonic"]) for l in A["mooring"]][:3])
