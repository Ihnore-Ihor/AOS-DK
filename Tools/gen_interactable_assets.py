"""AOS-DK Lab 3 - procedural source art for the Interactables suite (OBJ meshes + WAV one-shots).
Run: python3 Tools/gen_interactable_assets.py   ->  SourceArt/Interactables/*.obj|*.wav
Units cm, Z-up, +X forward (UE space). Deterministic (fixed seeds). Pure stdlib."""
import math, os, random, struct, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SourceArt", "Interactables")
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------- mesh builder
class Mesh:
    def __init__(self):
        self.v, self.vt, self.vn = [], [], []
        self.groups = {}  # material -> list of faces [(vi,ti,ni)*3]
    def _add(self, p, uv, n):
        self.v.append(p); self.vt.append(uv)
        l = math.sqrt(sum(c * c for c in n)) or 1.0
        self.vn.append(tuple(c / l for c in n))
        return len(self.v)  # 1-based
    def tri(self, mat, a, b, c):
        self.groups.setdefault(mat, []).append((a, b, c))
    def quad_flat(self, mat, p0, p1, p2, p3, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        n = cross(sub(p1, p0), sub(p3, p0))
        ids = [self._add(p, uv, n) for p, uv in zip((p0, p1, p2, p3), uvs)]
        self.tri(mat, ids[0], ids[1], ids[2]); self.tri(mat, ids[0], ids[2], ids[3])
    def box(self, mat, c, e):
        x, y, z = c; a, b, d = e
        P = lambda sx, sy, sz: (x + sx * a, y + sy * b, z + sz * d)
        self.quad_flat(mat, P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1))     # +Z
        self.quad_flat(mat, P(-1, 1, -1), P(1, 1, -1), P(1, -1, -1), P(-1, -1, -1))  # -Z
        self.quad_flat(mat, P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1))      # +X
        self.quad_flat(mat, P(-1, 1, -1), P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1))  # -X
        self.quad_flat(mat, P(1, 1, -1), P(-1, 1, -1), P(-1, 1, 1), P(1, 1, 1))      # +Y
        self.quad_flat(mat, P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1))  # -Y
    def lathe(self, mat, profile, sides, xf=lambda p: p, nf=lambda n: n):
        """profile: [(r, z)] bottom->top around +Z. Smooth within runs, hard edge where the slope breaks > 35 deg."""
        rings = []
        for i in range(len(profile) - 1):
            (r0, z0), (r1, z1) = profile[i], profile[i + 1]
            dz, dr = z1 - z0, r1 - r0
            nr, nz = dz, -dr  # outward normal in (r,z)
            for s in range(sides):
                a0 = 2 * math.pi * s / sides; a1 = 2 * math.pi * (s + 1) / sides
                q = []
                for (r, z, a) in ((r0, z0, a0), (r0, z0, a1), (r1, z1, a1), (r1, z1, a0)):
                    p = (r * math.cos(a), r * math.sin(a), z)
                    n = (nr * math.cos(a), nr * math.sin(a), nz)
                    q.append(self._add(xf(p), (a / (2 * math.pi), z * 0.01), nf(n)))
                if r0 < 1e-6:
                    self.tri(mat, q[0], q[2], q[3])
                elif r1 < 1e-6:
                    self.tri(mat, q[0], q[1], q[2])
                else:
                    self.tri(mat, q[0], q[1], q[2]); self.tri(mat, q[0], q[2], q[3])
    def tube(self, mat, pts, radius, sides, cap_mat=None):
        frames = transport_frames(pts)
        base = []
        L = 0.0
        for i, (p, t, n, b) in enumerate(frames):
            if i: L += dist(pts[i], pts[i - 1])
            ring = []
            for s in range(sides + 1):
                a = 2 * math.pi * s / sides
                d = add(scale(n, math.cos(a)), scale(b, math.sin(a)))
                ring.append(self._add(add(p, scale(d, radius)), (s / sides, L * 0.02), d))
            base.append(ring)
        for i in range(len(base) - 1):
            for s in range(sides):
                a, b2, c, d = base[i][s], base[i][s + 1], base[i + 1][s + 1], base[i + 1][s]
                self.tri(mat, a, b2, c); self.tri(mat, a, c, d)
        if cap_mat:
            for (idx, sign) in ((0, -1), (len(frames) - 1, 1)):
                p, t, n, b = frames[idx]
                tip = add(p, scale(t, sign * radius * 0.35))
                ci = self._add(tip, (0.5, 0.5), scale(t, sign))
                ring = []
                for s in range(sides + 1):
                    a = 2 * math.pi * s / sides
                    d = add(scale(n, math.cos(a)), scale(b, math.sin(a)))
                    ring.append(self._add(add(p, scale(d, radius * 1.02)), (s / sides, 0), add(scale(t, sign), scale(d, 0.3))))
                for s in range(sides):
                    if sign > 0: self.tri(cap_mat, ring[s], ring[s + 1], ci)
                    else: self.tri(cap_mat, ring[s + 1], ring[s], ci)
    def bounds(self):
        mn = [min(p[i] for p in self.v) for i in range(3)]; mx = [max(p[i] for p in self.v) for i in range(3)]
        return mn, mx
    def ntris(self):
        return sum(len(f) for f in self.groups.values())
    def write(self, name):
        path = os.path.join(OUT, name + ".obj")
        with open(path, "w", newline="\n") as f:
            f.write("# AOS-DK %s - Tools/gen_interactable_assets.py (cm, Z-up)\n" % name)
            f.write("o %s\n" % name)
            for p in self.v: f.write("v %.4f %.4f %.4f\n" % p)
            for t in self.vt: f.write("vt %.5f %.5f\n" % t)
            for n in self.vn: f.write("vn %.5f %.5f %.5f\n" % n)
            for mat, faces in self.groups.items():
                f.write("usemtl %s\n" % mat)
                for (a, b, c) in faces:
                    f.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (a, a, a, b, b, b, c, c, c))
        return path

def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def scale(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return scale(a, 1.0 / l)
def dist(a, b): return math.sqrt(dot(sub(a, b), sub(a, b)))

def transport_frames(pts):
    tans = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        tans.append(norm(sub(b, a)))
    ref = (0, 0, 1) if abs(tans[0][2]) < 0.9 else (1, 0, 0)
    n = norm(cross(cross(tans[0], ref), tans[0]))
    out = []
    for i, t in enumerate(tans):
        if i:
            n = norm(sub(n, scale(t, dot(n, t))))
        b = cross(t, n)
        out.append((pts[i], t, n, b))
    return out

def catmull(ctrl, steps):
    pts = []
    P = [ctrl[0]] + ctrl + [ctrl[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(steps):
            t = s / steps; t2 = t * t; t3 = t2 * t
            pts.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(3)))
    pts.append(ctrl[-1])
    return pts

report = {}

# ----------------------------------------------------------------------------- SM_AOS_EnergyCell (Z-up, pivot centre, 88 cm)
m = Mesh()
S = 2.0
prof = [(0, -22), (9, -22), (11.2, -21), (12, -19.5), (12, -14), (11, -13), (11, 13), (12, 14), (12, 19.5), (11.2, 21), (9, 22), (0, 22)]
m.lathe("Body", [(r * S, z * S) for r, z in prof], 32)
m.lathe("GlowA", [(11.4 * S, -11 * S), (11.4 * S, 11 * S)], 32)                     # yellow core window
for k in range(4):                                                                  # 4 armour ribs over the window
    a = math.pi / 4 + k * math.pi / 2
    c = (math.cos(a) * 11.6 * S, math.sin(a) * 11.6 * S, 0)
    # rib oriented radially: build as box in local then rotate around Z
    w, d, h = 1.4 * S, 1.0 * S, 12.5 * S
    corners = []
    m_rib = Mesh()
    m_rib.box("Body", (0, 0, 0), (d, w, h))
    for p, uv, n in zip(m_rib.v, m_rib.vt, m_rib.vn):
        rp = (p[0] * math.cos(a) - p[1] * math.sin(a) + c[0], p[0] * math.sin(a) + p[1] * math.cos(a) + c[1], p[2])
        rn = (n[0] * math.cos(a) - n[1] * math.sin(a), n[0] * math.sin(a) + n[1] * math.cos(a), n[2])
        corners.append(m._add(rp, uv, rn))
    off = corners[0] - 1
    for (x, y, z) in m_rib.groups["Body"]:
        m.tri("Body", x + off, y + off, z + off)
m.lathe("Body", [(0, 22 * S), (4.5 * S, 22 * S), (4.5 * S, 24.5 * S), (3.2 * S, 25.5 * S), (0, 25.5 * S)], 24)   # + terminal
m.lathe("GlowB", [(4.7 * S, 22.6 * S), (4.7 * S, 23.6 * S)], 24)                                                  # green ring
m.lathe("Body", [(0, -25 * S), (6 * S, -25 * S), (6 * S, -22 * S), (0, -22 * S)], 24)                             # - terminal
m.lathe("GlowB", [(6.2 * S, -24 * S), (6.2 * S, -23 * S)], 24)
m.write("SM_AOS_EnergyCell"); report["SM_AOS_EnergyCell"] = (m.bounds(), m.ntris())

# ----------------------------------------------------------------------------- SM_AOS_TorpedoCanister (axis +X, pivot centre, 160 cm)
m = Mesh()
toX = lambda p: (p[2], p[1], -p[0])   # lathe Z-axis -> +X
prof = [(0, -80), (14, -80), (19, -78), (21, -74), (21, 74), (19, 78), (14, 80), (0, 80)]
m.lathe("Body", prof, 32, xf=toX, nf=toX)
for x0 in (-58, 0, 58):
    m.lathe("GlowA", [(21.6, x0 - 3), (21.6, x0 + 3)], 32, xf=toX, nf=toX)            # pink bands
for x0 in (-78.5, 78.5):
    m.lathe("GlowB", [(15.5, x0 - 1.2), (15.5, x0 + 1.2)], 32, xf=toX, nf=toX)        # purple end rings
for sy in (-1, 1):                                                                   # purple dorsal strips
    a = math.radians(90 + sy * 28)
    c = (0, math.cos(a) * 21.2, math.sin(a) * 21.2)
    m.box("GlowB", (0, c[1], c[2]), (24, 1.2, 1.2))
    m.box("GlowB", (-29, c[1], c[2]), (3.5, 1.2, 1.2)); m.box("GlowB", (29, c[1], c[2]), (3.5, 1.2, 1.2))
for x0 in (-36, 36):                                                                 # carry handles
    m.box("Body", (x0 - 7, 0, 24.5), (1.4, 6, 3.5)); m.box("Body", (x0 + 7, 0, 24.5), (1.4, 6, 3.5))
    m.box("Body", (x0, 0, 28.5), (8.4, 6, 1.4))
for x0 in (-40, 40):                                                                 # cradle skids
    m.box("Body", (x0, 0, -21.5), (5, 15, 2.5))
m.write("SM_AOS_TorpedoCanister"); report["SM_AOS_TorpedoCanister"] = (m.bounds(), m.ntris())

# ----------------------------------------------------------------------------- SM_AOS_BulkheadSlab (pivot bottom centre; plate in YZ, thickness X)
m = Mesh()
W, H, T = 1400.0, 1250.0, 40.0
m.box("Steel", (0, 0, H / 2), (T / 2, W / 2, H / 2))                                 # plate
for z in (40.0, H - 40.0):                                                           # top / bottom frame
    m.box("Frame", (0, 0, z), (T / 2 + 18, W / 2 + 20, 40))
for y in (-W / 2, W / 2):                                                            # side frame
    m.box("Frame", (0, y, H / 2), (T / 2 + 18, 40, H / 2))
for y in (-420.0, -140.0, 140.0, 420.0):                                             # vertical stiffeners (both faces)
    for sx in (-1, 1):
        m.box("Frame", (sx * (T / 2 + 12), y, H / 2), (12, 14, H / 2 - 80))
        m.box("Frame", (sx * (T / 2 + 22), y, H / 2), (2, 30, H / 2 - 80))          # T flange
for z in (430.0, 840.0):                                                             # horizontal stringers
    for sx in (-1, 1):
        m.box("Frame", (sx * (T / 2 + 10), 0, z), (10, W / 2 - 40, 12))
m.box("Frame", (0, 0, 15), (60, W / 2 + 60, 15))                                     # footing
for sx in (-1, 1):                                                                   # warning band + status lamps
    m.box("Status", (sx * (T / 2 + 30.5), 0, H - 110), (0.6, W / 2 - 60, 6))
    for y in (-560.0, -280.0, 0.0, 280.0, 560.0):
        m.box("Status", (sx * (T / 2 + 20), y, H - 150), (2.5, 14, 9))
m.write("SM_AOS_BulkheadSlab"); report["SM_AOS_BulkheadSlab"] = (m.bounds(), m.ntris())

# ----------------------------------------------------------------------------- SM_AOS_CableTangle (pivot centre, ~560 x 760 x 560)
rnd = random.Random(1010)
m = Mesh()
RX, RY, RZ = 270.0, 370.0, 270.0
def in_ell(f=1.0):
    while True:
        p = (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))
        if dot(p, p) <= 1.0:
            return (p[0] * RX * f, p[1] * RY * f, p[2] * RZ * f)
cables = 0
for i in range(16):
    kind = i % 4
    if kind == 0:   # drapes from the ceiling, sags, ends severed mid-volume
        start = (rnd.uniform(-RX, RX) * 0.7, rnd.uniform(-RY, RY) * 0.8, RZ)
        ctrl = [start] + [in_ell(0.85) for _ in range(rnd.randint(3, 5))]
    elif kind == 1: # wall to wall across the corridor
        ctrl = [(rnd.uniform(-RX, RX) * 0.6, -RY, rnd.uniform(-RZ, RZ) * 0.6)] + [in_ell(0.8) for _ in range(3)] + [(rnd.uniform(-RX, RX) * 0.6, RY, rnd.uniform(-RZ, RZ) * 0.6)]
    elif kind == 2: # lying on the floor in loops
        ctrl = [(rnd.uniform(-RX, RX) * 0.8, rnd.uniform(-RY, RY) * 0.8, -RZ + rnd.uniform(5, 40)) for _ in range(5)]
    else:           # free loop
        c = in_ell(0.5); r = rnd.uniform(80, 160)
        a0 = rnd.uniform(0, 6.28)
        ctrl = [add(c, (r * math.cos(a0 + k * 1.3), r * math.sin(a0 + k * 1.3) * 1.2, rnd.uniform(-60, 60))) for k in range(6)]
    pts = catmull(ctrl, 18)
    rad = rnd.uniform(3.0, 6.5)
    m.tube("Sheath", pts, rad, 10, cap_mat="Core")
    cables += 1
for i in range(5):  # thin fibre bundles
    pts = catmull([in_ell(0.9) for _ in range(5)], 16)
    m.tube("Core", pts, 1.4, 6)
m.write("SM_AOS_CableTangle"); report["SM_AOS_CableTangle"] = (m.bounds(), m.ntris())

# ----------------------------------------------------------------------------- WAV one-shots (44.1 kHz mono 16-bit)
SR = 44100
def write_wav(name, samples, peak_db=-3.0):
    pk = max(1e-9, max(abs(s) for s in samples)); g = 10 ** (peak_db / 20) / pk
    path = os.path.join(OUT, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * g)) * 32767)) for s in samples))
    report[name] = (len(samples) / SR, "s")

def bell(buf, t0, f, amp, decay):
    partials = ((1.0, 1.0), (2.76, 0.45), (5.40, 0.22), (8.93, 0.09))
    i0 = int(t0 * SR)
    for i in range(i0, len(buf)):
        t = (i - i0) / SR
        att = min(1.0, t / 0.004)
        buf[i] += amp * att * sum(a * math.sin(2 * math.pi * f * r * t) * math.exp(-t * decay * (1 + 0.6 * (r - 1))) for r, a in partials)

rn = random.Random(7)
# energy chime: E6 -> B6 -> E7 with shimmer
buf = [0.0] * int(1.5 * SR)
bell(buf, 0.00, 1318.5, 0.9, 3.2); bell(buf, 0.11, 1975.5, 0.75, 3.6); bell(buf, 0.22, 2637.0, 0.45, 4.5)
for i in range(len(buf)):
    t = i / SR; buf[i] *= 1.0 + 0.08 * math.sin(2 * math.pi * 6.0 * t)
write_wav("SW_Pickup_EnergyChime", buf)
# torpedo canister: magnetic latch click + metal ring + low thunk + second click
buf = [0.0] * int(0.9 * SR)
for i in range(len(buf)):
    t = i / SR
    s = 0.0
    if t < 0.006: s += rn.uniform(-1, 1) * (1 - t / 0.006)
    if 0.12 <= t < 0.125: s += 0.7 * rn.uniform(-1, 1) * (1 - (t - 0.12) / 0.005)
    s += 0.9 * math.sin(2 * math.pi * 72 * t) * math.exp(-t * 22)
    s += 0.35 * math.sin(2 * math.pi * 880 * t) * math.exp(-t * 7) + 0.22 * math.sin(2 * math.pi * 1347 * t) * math.exp(-t * 9)
    if t >= 0.12:
        u = t - 0.12; s += 0.3 * math.sin(2 * math.pi * 1760 * u) * math.exp(-u * 10)
    buf[i] = s
write_wav("SW_Pickup_TorpedoLatch", buf)
# tangle snag: rubbery stretch groan
buf = [0.0] * int(0.8 * SR); lp = 0.0
for i in range(len(buf)):
    t = i / SR
    env = min(1, t / 0.03) * math.exp(-t * 3.5)
    f = 95 + 25 * math.sin(2 * math.pi * 7 * t) - 30 * t
    lp += 0.04 * (rn.uniform(-1, 1) - lp)
    buf[i] = env * (0.7 * math.sin(2 * math.pi * f * t + 0.6 * math.sin(2 * math.pi * 2 * f * t)) + 2.5 * lp)
write_wav("SW_Tangle_Snag", buf)
# tangle sever: snap + falling whip
buf = [0.0] * int(0.6 * SR); ph = 0.0
for i in range(len(buf)):
    t = i / SR
    s = (rn.uniform(-1, 1) * math.exp(-t * 60))
    f = 900 * math.exp(-t * 6) + 120; ph += 2 * math.pi * f / SR
    s += 0.5 * math.sin(ph) * math.exp(-t * 8)
    buf[i] = s
write_wav("SW_Tangle_Sever", buf)

for k, v in report.items():
    print(k, v)
