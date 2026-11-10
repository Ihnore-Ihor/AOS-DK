"""AOS-DK Lab 4 - procedural source art for the Evacuation Transit Shafts (OBJ mesh + WAV one-shots).
Run: python3 Tools/gen_teleport_assets.py   ->  SourceArt/Teleport/SM_AOS_TransitShaft.obj, SW_Transit_*.wav
Units cm, Z-up, UE space. The shaft axis is +X from the pivot (x = 0 is the end that tucks into the portal frame).
Deterministic, pure stdlib."""
import math, os, random, struct, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SourceArt", "Teleport")
os.makedirs(OUT, exist_ok=True)

# Shaft dimensions (cm). The SomaLock lens is R 248, Shell-1 needs a sphere R 245 -> inner R 330.
L, R_IN, R_OUT, SIDES = 2400.0, 330.0, 370.0, 48
RIB_R, RIB_W, RIB_PITCH = 410.0, 30.0, 400.0
STRIP_HALF_W, STRIP_T = 9.0, 3.0


class Mesh:
    def __init__(self):
        self.v, self.vt, self.vn, self.groups = [], [], [], {}

    def add(self, p, uv, n):
        l = math.sqrt(sum(c * c for c in n)) or 1.0
        self.v.append(p); self.vt.append(uv); self.vn.append(tuple(c / l for c in n))
        return len(self.v)

    def tri(self, mat, a, b, c):
        self.groups.setdefault(mat, []).append((a, b, c))

    def lathe(self, mat, profile, sides=SIDES):
        """profile [(r, x)] around +X; outward normal on the left of the walking direction (r, x) -> UE (x, r cos, r sin)."""
        for i in range(len(profile) - 1):
            (r0, x0), (r1, x1) = profile[i], profile[i + 1]
            dx, dr = x1 - x0, r1 - r0
            nr, nx = dx, -dr
            for s in range(sides):
                a0, a1 = 2 * math.pi * s / sides, 2 * math.pi * (s + 1) / sides
                q = []
                for (r, x, a) in ((r0, x0, a0), (r0, x0, a1), (r1, x1, a1), (r1, x1, a0)):
                    p = (x, r * math.cos(a), r * math.sin(a))
                    n = (nx, nr * math.cos(a), nr * math.sin(a))
                    q.append(self.add(p, (a * R_OUT / 200.0, x / 200.0), n))
                if r0 < 1e-6:
                    self.tri(mat, q[0], q[2], q[3])
                elif r1 < 1e-6:
                    self.tri(mat, q[0], q[1], q[2])
                else:
                    self.tri(mat, q[0], q[1], q[2]); self.tri(mat, q[0], q[2], q[3])

    def quad(self, mat, p0, p1, p2, p3):
        e1 = [p1[i] - p0[i] for i in range(3)]; e2 = [p3[i] - p0[i] for i in range(3)]
        n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        ids = [self.add(p, uv, n) for p, uv in zip((p0, p1, p2, p3), ((0, 0), (1, 0), (1, 1), (0, 1)))]
        self.tri(mat, ids[0], ids[1], ids[2]); self.tri(mat, ids[0], ids[2], ids[3])

    def write(self, name):
        path = os.path.join(OUT, name + ".obj")
        with open(path, "w", newline="\n") as f:
            f.write("# AOS-DK %s - Tools/gen_teleport_assets.py (cm, Z-up, axis +X)\no %s\n" % (name, name))
            for p in self.v: f.write("v %.4f %.4f %.4f\n" % p)
            for t in self.vt: f.write("vt %.5f %.5f\n" % t)
            for n in self.vn: f.write("vn %.5f %.5f %.5f\n" % n)
            for mat, faces in self.groups.items():
                f.write("usemtl %s\n" % mat)
                for (a, b, c) in faces:
                    f.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (a, a, a, b, b, b, c, c, c))
        return path


def shaft():
    m = Mesh()
    # Walls: outer (walk +x -> normal +r), far end cap (seal iris), inner (walk -x -> normal -r), near-end annulus (normal -x).
    m.lathe("Steel", [(R_OUT, 0.0), (R_OUT, L)])
    m.lathe("Seal", [(R_OUT, L), (0.0, L)])
    m.lathe("Steel", [(R_IN, L - 2.0), (R_IN, 0.0)])
    m.lathe("Seal", [(0.0, L - 2.0), (R_IN, L - 2.0)])  # inner face of the seal (normal -x)
    m.lathe("Steel", [(R_IN, 0.0), (R_OUT, 0.0)])
    # External rib rings
    x = RIB_PITCH * 0.5
    while x < L - RIB_W:
        m.lathe("Frame", [(R_OUT, x), (RIB_R, x), (RIB_R, x + RIB_W), (R_OUT, x + RIB_W)])
        x += RIB_PITCH
    # Inner guide strips (emissive) at 45/135/225/315 deg, slightly proud of the inner wall
    for k in range(4):
        a = math.radians(45 + 90 * k)
        c, s = math.cos(a), math.sin(a)
        t = (0.0, -s, c)  # tangential
        def P(xx, rr, off):
            return (xx, rr * c + off * t[1], rr * s + off * t[2])
        r = R_IN - STRIP_T
        x0, x1 = 60.0, L - 60.0
        m.quad("Guide", P(x0, r, STRIP_HALF_W), P(x0, r, -STRIP_HALF_W), P(x1, r, -STRIP_HALF_W), P(x1, r, STRIP_HALF_W))  # faces the axis
    # emissive guide rings every 600 cm, inner face
    for xr in (150.0, 750.0, 1350.0, 1950.0):
        m.lathe("Guide", [(R_IN - 2.0, xr + 24.0), (R_IN - 2.0, xr)])
    return m


report = {}
m = shaft()
report["SM_AOS_TransitShaft"] = (m.write("SM_AOS_TransitShaft"), len(m.v), sum(len(f) for f in m.groups.values()))

SR = 48000
rn = random.Random(404)

def write_wav(name, samples, peak_db=-3.0):
    peak = max(1e-9, max(abs(s) for s in samples)); g = 10 ** (peak_db / 20) / peak
    path = os.path.join(OUT, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * g)) * 32767)) for s in samples))
    report[name] = path

# Departure: heavy seal clunk + rising decompression hiss + suction sweep (2.0 s = intake + fade)
buf = [0.0] * int(2.0 * SR); lp = 0.0; ph = 0.0
for i in range(len(buf)):
    t = i / SR
    s = 1.2 * math.sin(2 * math.pi * 55 * t) * math.exp(-t * 14) + 0.6 * rn.uniform(-1, 1) * math.exp(-t * 80)
    lp += 0.08 * (rn.uniform(-1, 1) - lp)
    s += 1.6 * lp * min(1, t / 0.4) * math.exp(-max(0, t - 1.4) * 4)
    f = 60 + 140 * t * t; ph += 2 * math.pi * f / SR
    s += 0.45 * math.sin(ph) * min(1, t / 0.2) * math.exp(-max(0, t - 1.5) * 5)
    buf[i] = s
write_wav("SW_Transit_Departure", buf)
# Arrival: pressure release whoosh + bubble rush + latch tick
buf = [0.0] * int(1.4 * SR); lp = 0.0
for i in range(len(buf)):
    t = i / SR
    lp += 0.15 * (rn.uniform(-1, 1) - lp)
    s = 2.2 * lp * math.exp(-t * 3.2) * min(1, t / 0.02)
    for k, (t0, f0) in enumerate(((0.05, 420), (0.12, 610), (0.21, 380), (0.3, 720), (0.42, 520), (0.55, 840))):
        if t >= t0:
            u = t - t0; s += 0.25 * math.sin(2 * math.pi * (f0 + 900 * u) * u) * math.exp(-u * 18)
    if t >= 0.9:
        u = t - 0.9; s += 0.5 * math.sin(2 * math.pi * 1400 * u) * math.exp(-u * 40)
    buf[i] = s
write_wav("SW_Transit_Arrival", buf)

for k, v in report.items():
    print(k, v)
