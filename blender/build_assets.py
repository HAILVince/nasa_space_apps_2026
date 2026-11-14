"""Blender asset pipeline for the Blackfox fire-safety lab.

Builds every 3D asset the web viewer loads, from code, so the model can be rebuilt,
reviewed and changed like the rest of the repository:

  frontend/assets/3d/habitat.glb        HAB-01 research module (cutaway), animated fan,
                                        hatch and solar-array tracking, fire/vent anchors
  frontend/assets/3d/habitat_ao.webp    Cycles-baked ambient occlusion atlas (UV0)
  frontend/assets/3d/rocks.glb          four regolith rock variants
  frontend/assets/3d/terrain_<body>.*   Moon / Mars terrain: height (16 bit in R+G),
                                        Cycles-baked albedo x AO, rock placements
  frontend/assets/3d/moon_globe.webp    lunar albedo for the lunar-orbit backdrop
  frontend/assets/3d/moon_globe_height.webp

Run with Blender 4.2+ (or the `bpy` wheel):

    blender -b -P blender/build_assets.py -- [--quick] [--only habitat|terrain|globe]
    python blender/build_assets.py [--quick]          # with `pip install bpy`

Geometry follows blackfox/physics/habitat_layout.json (Y-up metres, the glTF frame);
Blender works Z-up, so a layout point (x, y, z) is Blender (x, -z, y).
"""
import json
import math
import sys
from pathlib import Path

import bpy  # noqa: I001 - bpy must be imported before bmesh/mathutils
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "assets" / "3d"
LAYOUT = json.loads((ROOT / "blackfox" / "physics" / "habitat_layout.json").read_text())
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
QUICK = "--quick" in ARGS
ONLY = ARGS[ARGS.index("--only") + 1] if "--only" in ARGS else None
TAU = 2 * math.pi
DEG = math.pi / 180
RNG = np.random.default_rng(2026)


def B(p):
    """layout (Y-up) -> Blender (Z-up)"""
    x, y, z = p
    return Vector((x, -z, y))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.render.fps = 30
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    return sc


# ---- materials -------------------------------------------------------------------
MATS = {}


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def material(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, alpha=1.0, coat=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*srgb(color), 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if coat:
        p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = (*srgb(emit), 1)
        p.inputs["Emission Strength"].default_value = strength
    if alpha < 1:
        p.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    MATS[name] = m
    return m


def palette():
    return {
        "hull": material("Hull_Aluminium", "#aeb6bb", 0.38, 0.85),
        "hull_in": material("Hull_Primer", "#8d9a95", 0.6, 0.2),
        "mli": material("MLI_Kapton", "#c99a3c", 0.28, 0.9),
        "blanket": material("MMOD_BetaCloth", "#e9e7df", 0.78, 0.0),
        "blanket_seam": material("MMOD_Seam", "#b9b5aa", 0.85, 0.0),
        "panel": material("Rack_Panel", "#dcdcd3", 0.55, 0.05),
        "panel2": material("Rack_Panel_Warm", "#cfcabd", 0.6, 0.05),
        "locker": material("Locker_Door", "#e6e5de", 0.5, 0.05),
        "dark": material("Avionics_Dark", "#30363b", 0.45, 0.35),
        "graphite": material("Graphite", "#1b2025", 0.5, 0.2),
        "metal": material("Machined_Aluminium", "#c4cbd0", 0.3, 1.0),
        "steel": material("Fastener_Steel", "#8e959a", 0.35, 1.0),
        "rail": material("IVA_Handrail", "#7e95a8", 0.4, 0.6),
        "eva": material("EVA_Handrail_Yellow", "#e2b01c", 0.45, 0.2),
        "cable": material("Cable_Jacket", "#2a2d2f", 0.65, 0.0),
        "cable2": material("Cable_Jacket_White", "#cfd2d0", 0.6, 0.0),
        "duct": material("Duct_Fabric", "#b8bcb6", 0.8, 0.0),
        "fabric": material("Nomex_Bag", "#ddd3b8", 0.9, 0.0),
        "fabric_blue": material("Sleeping_Bag", "#3f5f86", 0.88, 0.0),
        "foam": material("Foam_Grey", "#9aa09c", 0.95, 0.0),
        "strap": material("Strap_Orange", "#c2602d", 0.75, 0.0),
        "red": material("Warning_Red", "#b3271e", 0.5, 0.0),
        "hazard": material("Hazard_Yellow", "#e5b316", 0.55, 0.0),
        "glass": material("Viewport_Glass", "#1d3440", 0.05, 0.0, alpha=0.35),
        "led": material("LED_Panel", "#f4f8f6", 0.3, 0.0, emit="#eef6ff", strength=6.0),
        "screen": material("Display_Screen", "#05080b", 0.2, 0.0, emit="#3b8fb0", strength=1.4),
        "status": material("Status_LED", "#0d0d0d", 0.3, 0.0, emit="#7dff8a", strength=8.0),
        "solar": material("Solar_Cell", "#0e1f3a", 0.25, 0.4),
        "radiator": material("Radiator_White", "#f1f2ee", 0.5, 0.0),
        "foot": material("Footpad_Ti", "#7d868b", 0.45, 0.9),
    }


# ---- geometry builder ---------------------------------------------------------------
class Part:
    """One Blender object assembled from many primitives, one material slot per material."""

    def __init__(self, name):
        self.name, self.bm, self.slots = name, bmesh.new(), []

    def _slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def _finish(self, verts, mat, bevel=0.0, segments=1):
        idx = self._slot(mat)
        verts = list(verts)
        faces = {f for v in verts for f in v.link_faces}
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, segments=segments, affect="EDGES",
                                  profile=0.5, clamp_overlap=True)
            faces |= set(res["faces"])
            faces |= {f for v in verts if v.is_valid for f in v.link_faces}
        for f in faces:
            if f.is_valid:
                f.material_index = idx
                f.smooth = segments > 1

    def box(self, mat, center, size, bevel=0.0, rot=None, segments=1):
        m = Matrix.Translation(Vector(center))
        if rot is not None:
            m = m @ rot.to_4x4()
        m = m @ Matrix.Diagonal((*size, 1))
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        self._finish(res["verts"], mat, bevel, segments)

    def cyl(self, mat, p0, p1, r, seg=20, r2=None, bevel=0.0, smooth=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        m = Matrix.Translation((p0 + p1) / 2) @ rot
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=seg, radius1=r,
                                    radius2=r if r2 is None else r2, depth=d.length, matrix=m)
        self._finish(res["verts"], mat, bevel, 2 if smooth and bevel else 1)
        if smooth:
            for v in res["verts"]:
                for f in v.link_faces:
                    if len(f.verts) == 4:
                        f.smooth = True

    def tube(self, mat, pts, r, seg=8):
        """sweep a circle along a polyline (cables, hoses, handrail bends)"""
        pts = [Vector(p) for p in pts]
        rings = []
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            q = t.to_track_quat("Z", "Y").to_matrix()
            rings.append([self.bm.verts.new(p + q @ Vector((r * math.cos(a), r * math.sin(a), 0)))
                          for a in np.linspace(0, TAU, seg, endpoint=False)])
        idx = self._slot(mat)
        for a, b in zip(rings, rings[1:]):
            for k in range(seg):
                f = self.bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
                f.material_index, f.smooth = idx, True
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            f = self.bm.faces.new(ring[::-1] if rev else ring)
            f.material_index = idx

    def revolve(self, mat, profile, a0, a1, steps=None, smooth=True):
        """revolve a closed (x, r) polygon about the X axis from angle a0 to a1 (radians,
        0 = +Y, pi/2 = +Z). Partial revolutions are closed with cut faces."""
        full = abs(a1 - a0) >= TAU - 1e-6
        steps = steps or max(4, int(abs(a1 - a0) / (4 * DEG)))
        idx = self._slot(mat)
        rings = []
        n = steps if full else steps + 1
        for i in range(n):
            a = a0 + (a1 - a0) * i / steps
            ca, sa = math.cos(a), math.sin(a)
            rings.append([self.bm.verts.new((x, r * ca, r * sa)) for x, r in profile])
        k = len(profile)
        pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if full else [])
        for ra, rb in pairs:
            for j in range(k):
                f = self.bm.faces.new((ra[j], ra[(j + 1) % k], rb[(j + 1) % k], rb[j]))
                f.material_index, f.smooth = idx, smooth
        if not full:
            for ring, rev in ((rings[0], True), (rings[-1], False)):
                f = self.bm.faces.new(ring if rev else ring[::-1])
                f.material_index = idx

    def build(self, collection=None):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for mat in self.slots:
            me.materials.append(mat)
        ob = bpy.data.objects.new(self.name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        # flat-shaded hard surfaces, smooth curved ones, without shading artefacts
        try:
            me.set_sharp_from_angle(angle=40 * DEG)
        except AttributeError:
            pass
        return ob


def ring_profile(x0, x1, r0, r1, bevel=0.0):
    """rectangular (x, r) section with an optional chamfer on the outer edges"""
    if bevel <= 0:
        return [(x0, r0), (x1, r0), (x1, r1), (x0, r1)]
    return [(x0, r0), (x1, r0), (x1, r1 - bevel), (x1 - bevel, r1), (x0 + bevel, r1), (x0, r1 - bevel)]


def quat_x(angle):
    return Matrix.Rotation(angle, 3, "X")


# ---- HAB-01 --------------------------------------------------------------------------
def build_habitat():
    sc = reset()
    M = palette()
    mod = LAYOUT["module"]
    R = mod["pressure_shell_inner_radius_m"]
    HW = mod["cabin_half_width_m"]
    pitch, n_racks = mod["rack_pitch_m"], mod["racks_per_wall"]
    XR = pitch * n_racks / 2                 # rack rows end (3.15)
    XC = 3.45                                # cylinder -> end cone
    CUT = (100 * DEG, 222 * DEG)            # cutaway window, front-upper quadrant
    XCUT = 2.95
    rack_x = [-XR + pitch * (i + 0.5) for i in range(n_racks)]
    W2 = 0.80                                # half span of a rack face across the wall

    shell = Part("Shell")
    # pressure shell: full rings at the ends, cutaway window in the middle
    for x0, x1 in ((-XC, -XCUT), (XCUT, XC)):
        shell.revolve(M["hull"], ring_profile(x0, x1, R, R + 0.06), 0, TAU, 90)
        shell.revolve(M["mli"], ring_profile(x0, x1, R + 0.065, R + 0.085), 0, TAU, 90)
    shell.revolve(M["hull"], ring_profile(-XCUT, XCUT, R, R + 0.06), CUT[1], CUT[0] + TAU)
    shell.revolve(M["mli"], ring_profile(-XCUT, XCUT, R + 0.065, R + 0.085), CUT[1] - 0.6 * DEG, CUT[0] + TAU + 0.6 * DEG)
    # isogrid ribs and ring frames on the inner skin (visible through the cut)
    for x in np.arange(-XCUT, XCUT + 0.01, 0.525):
        shell.revolve(M["hull_in"], ring_profile(x - 0.03, x + 0.03, R - 0.09, R + 0.001, 0.01), CUT[1], CUT[0] + TAU, 60)
    for a in np.arange(CUT[1] + 6 * DEG, CUT[0] + TAU - 2 * DEG, 12 * DEG):
        c, s = math.cos(a), math.sin(a)
        shell.box(M["hull_in"], (0, (R - 0.025) * c, (R - 0.025) * s), (2 * XCUT, 0.05, 0.035), 0.005, quat_x(a))
    # cut faces get a machined lip
    for a in CUT:
        c, s = math.cos(a), math.sin(a)
        shell.box(M["hazard"], (0, (R + 0.03) * c, (R + 0.03) * s), (2 * XCUT, 0.07, 0.012), 0.0, quat_x(a))
    for x in (-XCUT, XCUT):
        shell.revolve(M["hazard"], ring_profile(x - 0.006, x + 0.006, R - 0.005, R + 0.065), CUT[0], CUT[1], 30)
    # end cones (inner skin + outer skin) and bulkheads
    for sgn in (-1, 1):
        x0, x1 = sgn * XC, sgn * 3.95
        prof = [(x0, R), (x1, 1.12), (x1, 1.18), (x0, R + 0.06)]
        if sgn < 0:
            prof = [(x1, 1.12), (x0, R), (x0, R + 0.06), (x1, 1.18)]
        shell.revolve(M["hull"], prof, 0, TAU, 90)
        # CBM berthing ring with bolts
        shell.revolve(M["metal"], ring_profile(min(x1, sgn * 4.12), max(x1, sgn * 4.12), 0.92, 1.16, 0.02), 0, TAU, 72)
        for a in np.arange(0, TAU, TAU / 16):
            c, s = math.cos(a), math.sin(a)
            shell.cyl(M["steel"], (sgn * 4.10, 1.08 * c, 1.08 * s), (sgn * 4.17, 1.08 * c, 1.08 * s), 0.028, 10)
    # MMOD blanket panels on the cylinder and cones, seams left open
    seg = 15 * DEG
    gap = 0.35 * DEG
    for i in range(24):
        a0, a1 = i * seg + gap, (i + 1) * seg - gap
        mid = (a0 + a1) / 2 % TAU
        in_cut = CUT[0] - 4 * DEG < mid < CUT[1] + 4 * DEG
        for j in range(8):
            x0 = -XC + j * (2 * XC / 8) + 0.012
            x1 = x0 + 2 * XC / 8 - 0.024
            if in_cut and (x1 > -XCUT and x0 < XCUT):
                xs = [(x0, min(x1, -XCUT - 0.012))] if x0 < -XCUT else []
                xs += [(max(x0, XCUT + 0.012), x1)] if x1 > XCUT else []
            else:
                xs = [(x0, x1)]
            for u0, u1 in xs:
                if u1 - u0 > 0.02:
                    shell.revolve(M["blanket"], ring_profile(u0, u1, R + 0.105, R + 0.165, 0.025), a0, a1, 4)
    # cutaway: blanket edge stripes so the section reads clearly
    for sgn in (-1, 1):
        x0, x1 = sgn * XC, sgn * 3.93
        for i in range(24):
            a0, a1 = i * seg + gap, (i + 1) * seg - gap
            prof = [(x0, R + 0.1), (x1, 1.22), (x1, 1.27), (x0, R + 0.16)]
            if sgn < 0:
                prof = [(x1, 1.22), (x0, R + 0.1), (x0, R + 0.16), (x1, 1.27)]
            shell.revolve(M["blanket"], prof, a0, a1, 3)
    # EVA handrails (yellow) along the hull, avoiding the cut
    for a in (20 * DEG, 70 * DEG, 245 * DEG, 300 * DEG, 340 * DEG):
        c, s = math.cos(a), math.sin(a)
        rr = R + 0.31
        for x0 in (-2.9, 0.3):
            pts = [(x0, (R + 0.17) * c, (R + 0.17) * s), (x0 + 0.04, rr * c, rr * s),
                   (x0 + 2.5, rr * c, rr * s), (x0 + 2.54, (R + 0.17) * c, (R + 0.17) * s)]
            shell.tube(M["eva"], pts, 0.019, 10)
    # grapple fixture, trunnions, window
    a = 60 * DEG
    c, s = math.cos(a), math.sin(a)
    shell.box(M["metal"], (1.2, (R + 0.22) * c, (R + 0.22) * s), (0.42, 0.42, 0.12), 0.015, quat_x(a - math.pi / 2))
    shell.cyl(M["steel"], (1.2, (R + 0.25) * c, (R + 0.25) * s), (1.2, (R + 0.48) * c, (R + 0.48) * s), 0.035, 16)
    shell.cyl(M["graphite"], (1.2, (R + 0.47) * c, (R + 0.47) * s), (1.2, (R + 0.53) * c, (R + 0.53) * s), 0.07, 20)
    for sgn in (-1, 1):
        shell.cyl(M["steel"], (0.3, sgn * (R + 0.1), 0), (0.3, sgn * (R + 0.42), 0), 0.055, 18)
    shell_ob = shell.build()

    # ---- interior: racks (deck, overhead, starboard/back), standoffs, end cones --------
    inner = Part("Interior")
    front = Part("FrontWall")

    def wall_frame(normal_angle):
        """basis for a wall whose face normal points to the cabin centre at angle a"""
        n = Vector((0, -math.cos(normal_angle), -math.sin(normal_angle)))      # into cabin
        out = -n
        t = Vector((0, -math.sin(normal_angle), math.cos(normal_angle)))      # along wall
        return out, t

    def P(x, u, d, out, t):
        """point on wall: x axial, u along the wall, d distance from cabin axis"""
        return Vector((x, 0, 0)) + t * u + out * d

    def rack(part, x, ang, kind):
        out, t = wall_frame(ang)
        rot = Matrix((Vector((1, 0, 0)), t, out)).transposed()            # local x, y=t, z=out
        w = pitch - 0.022
        # rack body (behind the face) and face plate; crew quarters are a hollow sleeping volume
        if kind == "crew_quarters":
            part.box(M["graphite"], P(x, 0, HW + 0.76, out, t), (w, 2 * W2, 0.04), 0.0, rot)
            for sx in (-1, 1):
                part.box(M["panel2"], P(x + sx * (w / 2 - 0.02), 0, HW + 0.4, out, t), (0.04, 2 * W2, 0.74), 0.0, rot)
                part.box(M["panel2"], P(x, sx * (W2 - 0.02), HW + 0.4, out, t), (w, 0.04, 0.74), 0.0, rot)
            part.box(M["led"], P(x, W2 - 0.06, HW + 0.4, out, t), (0.5, 0.02, 0.05), 0.0, rot)
        else:
            part.box(M["graphite"], P(x, 0, HW + 0.4, out, t), (w, 2 * W2, 0.78), 0.0, rot)
        if kind not in ("crew_quarters",):
            part.box(M["panel"] if kind != "avionics" else M["dark"], P(x, 0, HW + 0.012, out, t),
                     (w, 2 * W2 - 0.01, 0.024), 0.006, rot)
        # seat-track posts either side
        for sx in (-1, 1):
            part.box(M["metal"], P(x + sx * (w / 2 - 0.012), 0, HW - 0.008, out, t), (0.024, 2 * W2, 0.035), 0.004, rot)
        if kind == "lockers":
            for i in (-1, 1):
                for j in range(4):
                    u = -W2 + 0.2 + j * 0.4
                    c = P(x + i * 0.245, u, HW - 0.012, out, t)
                    part.box(M["locker"], c, (0.455, 0.37, 0.03), 0.01, rot, 2)
                    part.box(M["steel"], P(x + i * 0.245, u + 0.13, HW - 0.032, out, t), (0.1, 0.03, 0.014), 0.004, rot)
                    part.box(M["graphite"], P(x + i * 0.245 - 0.17, u - 0.14, HW - 0.028, out, t), (0.06, 0.04, 0.006), 0.0, rot)
        elif kind == "avionics":
            for j in range(9):
                u = -W2 + 0.18 + j * 0.06
                part.box(M["graphite"], P(x, u, HW - 0.01, out, t), (0.8, 0.018, 0.022), 0.003, rot)
            part.box(M["panel2"], P(x - 0.2, 0.25, HW - 0.02, out, t), (0.5, 0.5, 0.04), 0.01, rot, 2)
            for k in range(5):
                part.cyl(M["metal"], P(x + 0.18 + 0.07 * (k % 3), 0.18 + 0.1 * (k // 3), HW - 0.015, out, t),
                         P(x + 0.18 + 0.07 * (k % 3), 0.18 + 0.1 * (k // 3), HW - 0.06, out, t), 0.022, 12)
            part.box(M["status"], P(x + 0.35, 0.62, HW - 0.03, out, t), (0.02, 0.02, 0.01), 0.0, rot)
            part.box(M["red"], P(x - 0.38, 0.62, HW - 0.03, out, t), (0.06, 0.06, 0.02), 0.005, rot)
        elif kind == "experiment":
            part.box(M["panel2"], P(x, -0.35, HW - 0.025, out, t), (0.9, 0.7, 0.05), 0.012, rot, 2)
            part.box(M["dark"], P(x, 0.35, HW - 0.02, out, t), (0.9, 0.55, 0.04), 0.01, rot)
            for k in range(4):
                part.box(M["locker"], P(x - 0.32 + 0.21 * k, -0.35, HW - 0.055, out, t), (0.17, 0.5, 0.012), 0.004, rot)
        elif kind == "crew_quarters":
            # door frame with the sleeping volume behind it
            for sx in (-1, 1):
                part.box(M["panel"], P(x + sx * 0.4, 0, HW - 0.04, out, t), (0.08, 1.45, 0.08), 0.015, rot, 2)
            for su in (-1, 1):
                part.box(M["panel"], P(x, su * 0.72, HW - 0.04, out, t), (0.88, 0.08, 0.08), 0.015, rot, 2)
            part.box(M["fabric_blue"], P(x, -0.05, HW + 0.6, out, t), (0.55, 1.3, 0.16), 0.06, rot, 3)
            part.box(M["fabric"], P(x, 0.55, HW + 0.55, out, t), (0.3, 0.22, 0.1), 0.04, rot, 3)
            part.box(M["graphite"], P(x + 0.3, 0.1, HW + 0.7, out, t), (0.3, 0.22, 0.04), 0.01, rot)
        elif kind == "glovebox":
            part.box(M["panel"], P(x, 0.45, HW - 0.02, out, t), (0.95, 0.6, 0.04), 0.01, rot, 2)
            # work volume: five walls and a window, so a sample inside stays visible
            part.box(M["metal"], P(x, -0.15, HW - 0.02, out, t), (0.95, 0.55, 0.04), 0.01, rot)
            for su in (-1, 1):
                part.box(M["metal"], P(x, -0.15 + su * 0.255, HW - 0.26, out, t), (0.95, 0.04, 0.48), 0.01, rot)
            for sx in (-1, 1):
                part.box(M["metal"], P(x + sx * 0.455, -0.15, HW - 0.26, out, t), (0.04, 0.55, 0.48), 0.01, rot)
            part.box(M["glass"], P(x, -0.15, HW - 0.505, out, t), (0.9, 0.5, 0.012), 0.0, rot)
            part.box(M["led"], P(x, 0.1, HW - 0.06, out, t), (0.6, 0.02, 0.02), 0.0, rot)
            for sx in (-1, 1):
                c0 = P(x + sx * 0.22, -0.15, HW - 0.5, out, t)
                part.cyl(M["graphite"], c0, c0 - out * 0.05, 0.075, 24)
        elif kind == "workstation":
            part.box(M["panel2"], P(x, 0, HW - 0.01, out, t), (w, 2 * W2, 0.02), 0.0, rot)
            for k in (-1, 1):
                part.box(M["graphite"], P(x + k * 0.24, 0.1, HW - 0.08, out, t), (0.36, 0.26, 0.02), 0.006, rot)
            part.box(M["metal"], P(x, -0.35, HW - 0.05, out, t), (0.8, 0.06, 0.08), 0.01, rot)
        # IVA handrail on every rack (left edge)
        h0 = P(x - w / 2 + 0.07, -0.25, HW - 0.01, out, t)
        h1 = P(x - w / 2 + 0.07, 0.25, HW - 0.01, out, t)
        pts = [h0, h0 - out * 0.07, h1 - out * 0.07, h1]
        part.tube(M["rail"], pts, 0.016, 10)

    walls = {
        "back": (0.0, ["crew_quarters", "glovebox", "lockers", "experiment", "avionics", "lockers"]),
        "overhead": (math.pi / 2, ["avionics", "lockers", "experiment", "lockers", "avionics", "lockers"]),
        "deck": (3 * math.pi / 2, ["lockers", "lockers", "experiment", "lockers", "lockers", "avionics"]),
        "front": (math.pi, ["lockers", "workstation", "lockers", "avionics", "lockers", "experiment"]),
    }
    for name, (ang, kinds) in walls.items():
        part = front if name == "front" else inner
        for x, k in zip(rack_x, kinds):
            rack(part, x, ang, k)

    # corner standoffs: closeout panels, LED light strips on the overhead corners, utility runs
    for k, a in enumerate((45 * DEG, 135 * DEG, 225 * DEG, 315 * DEG)):
        c, s = math.cos(a), math.sin(a)
        d = (HW + W2) / math.sqrt(2) * 1.0
        part = front if k in (1, 2) else inner
        rot = quat_x(a)
        part.box(M["panel"], (0, d * c, d * s), (2 * XR, 0.012, 0.27), 0.0, rot)
        if k in (0, 1):
            part.box(M["led"], (0, (d - 0.012) * c, (d - 0.012) * s), (2 * XR - 0.3, 0.008, 0.09), 0.0, rot)
        # utility run behind the closeout: cable bundles, water lines, IMV duct
        for j, (dd, dr, mat) in enumerate(((0.32, -0.08, "cable"), (0.36, 0.06, "cable2"), (0.42, 0.0, "cable"),
                                           (0.48, -0.1, "steel"), (0.5, 0.1, "steel"))):
            pc = Vector((0, (d + dd) * c - dr * s, (d + dd) * s + dr * c))
            pts = [(x, pc.y + 0.01 * math.sin(x * 3 + j), pc.z + 0.01 * math.cos(x * 2.4 + j)) for x in np.linspace(-XC + 0.05, XC - 0.05, 24)]
            inner.tube(M[mat], pts, 0.028 if mat != "steel" else 0.012, 8)
        pc = Vector((0, (d + 0.62) * c, (d + 0.62) * s))
        inner.cyl(M["duct"], (-XR, pc.y, pc.z), (XR, pc.y, pc.z), 0.085, 18)
        for x in np.arange(-XR + 0.3, XR, 0.7):
            inner.cyl(M["metal"], (x, pc.y, pc.z), (x + 0.03, pc.y, pc.z), 0.095, 18)
    # cable trays / brackets in the front-upper standoff (visible through the cut)
    for x in np.arange(-2.8, 2.81, 0.4):
        a = 135 * DEG
        c, s = math.cos(a), math.sin(a)
        d = (HW + W2) / math.sqrt(2) + 0.36
        inner.box(M["metal"], (x, d * c, d * s), (0.03, 0.5, 0.03), 0.004, quat_x(a))

    # end cones (interior): conical closeout, hatch frame, diffusers, return grille, fan
    for sgn in (-1, 1):
        prof = [(sgn * XR, 1.45), (sgn * 3.84, 0.98), (sgn * 3.84, 1.02), (sgn * XR, 1.49)]
        if sgn < 0:
            prof = prof[::-1]
        inner.revolve(M["panel"], prof, 0, TAU, 72)
        # square CBM hatch frame (four bars)
        for dy, dz, sy, sz in ((0, 0.66, 1.45, 0.13), (0, -0.66, 1.45, 0.13), (0.66, 0, 0.13, 1.2), (-0.66, 0, 0.13, 1.2)):
            inner.box(M["metal"], (sgn * 3.88, dy, dz), (0.08, sy, sz), 0.02, None, 2)
    # short vestibule behind the open -X hatch, closed by the berthed neighbour's dark hatch
    inner.revolve(M["hull_in"], ring_profile(-4.12, -3.9, 0.8, 0.84), 0, TAU, 48)
    inner.box(M["graphite"], (-4.1, 0, 0), (0.02, 1.3, 1.3))
    # inlet diffuser (overhead, -X) and return grille + smoke detector (deck, +X)
    vin, vret, det = (B(LAYOUT["ventilation"][k]) for k in ("inlet", "return", "cabin_detector"))
    inner.box(M["metal"], (vin.x, vin.y, HW + 0.02), (0.5, 0.5, 0.06), 0.012, None, 2)
    for k in range(7):
        inner.box(M["graphite"], (vin.x - 0.18 + 0.06 * k, vin.y, HW - 0.015), (0.025, 0.42, 0.02), 0.004)
    inner.box(M["metal"], (vret.x, vret.y, -HW - 0.02), (0.5, 0.42, 0.06), 0.012, None, 2)
    for k in range(7):
        inner.box(M["graphite"], (vret.x - 0.18 + 0.06 * k, vret.y, -HW + 0.015), (0.025, 0.34, 0.02), 0.004)
    inner.cyl(M["panel"], (det.x, det.y, -HW + 0.02), (det.x, det.y, -HW + 0.09), 0.07, 24)
    inner.cyl(M["status"], (det.x, det.y, -HW + 0.09), (det.x, det.y, -HW + 0.1), 0.012, 8)
    # galley table on the deck
    g = B(LAYOUT["locations"]["galley"]["anchor"])
    top = g.z - 0.06
    inner.box(M["panel"], (g.x, g.y, top), (0.9, 0.62, 0.035), 0.012, None, 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            inner.cyl(M["metal"], (g.x + sx * 0.38, g.y + sy * 0.24, -HW), (g.x + sx * 0.38, g.y + sy * 0.24, top - 0.02), 0.018, 10)
    for k, (dx, dy) in enumerate(((-0.25, 0.1), (-0.05, -0.12), (0.2, 0.05), (0.3, -0.15))):
        inner.box(M["cable2"] if k % 2 else M["fabric"], (g.x + dx, g.y + dy, top + 0.045), (0.16, 0.11, 0.05), 0.02, None, 2)
    # stowage bags strapped under the overhead
    st = B(LAYOUT["locations"]["stowage"]["anchor"])
    for k, (dx, dy, sz) in enumerate(((-0.3, -0.1, 0.32), (0.2, 0.2, 0.28), (0.25, -0.35, 0.24), (-0.25, 0.35, 0.3))):
        inner.box(M["fabric"], (st.x + dx, st.y + dy, HW - sz / 2 - 0.02), (0.5, 0.42, sz), 0.06, None, 3)
    inner.box(M["strap"], (st.x, st.y, HW - 0.2), (1.1, 0.05, 0.012))
    inner.box(M["strap"], (st.x, st.y, HW - 0.2), (0.05, 1.2, 0.012))
    # cable harness in the open avionics rack (the default fire location)
    av = B(LAYOUT["locations"]["avionics_rack"]["anchor"])
    pts = [(av.x - 0.45 + 0.9 * i / 15, HW - 0.06, av.z + 0.05 * math.sin(i / 2)) for i in range(16)]
    inner.tube(M["cable2"], pts, 0.022, 8)
    pts = [(av.x - 0.45 + 0.9 * i / 15, HW - 0.09, av.z - 0.06 + 0.04 * math.cos(i / 2)) for i in range(16)]
    inner.tube(M["cable"], pts, 0.018, 8)
    inner_ob = inner.build()
    front_ob = front.build()

    # ---- animated parts --------------------------------------------------------------
    # cabin fan in the front-upper standoff, visible through the cutaway
    fan = Part("Fan")
    a = 135 * DEG
    fp = Vector((-2.35, 1.5 * math.cos(a), 1.5 * math.sin(a)))
    for k in range(7):
        rot = Matrix.Rotation(k * TAU / 7, 3, "X") @ Matrix.Rotation(28 * DEG, 3, "Y")
        fan.box(M["graphite"], rot @ Vector((0, 0.09, 0)), (0.05, 0.13, 0.008), 0.0, rot)
    fan.cyl(M["metal"], (-0.04, 0, 0), (0.04, 0, 0), 0.04, 18)
    fan_ob = fan.build()
    fan_ob.location = fp
    housing = Part("FanHousing")
    housing.revolve(M["metal"], ring_profile(-0.09, 0.09, 0.175, 0.2, 0.01), 0, TAU, 40)
    housing.cyl(M["metal"], (0.02, 0, 0), (0.06, 0, 0), 0.05, 16)
    for k in range(3):
        b = k * TAU / 3
        housing.box(M["metal"], (0.04, 0.1 * math.cos(b), 0.1 * math.sin(b)), (0.02, 0.16, 0.02), 0.0, quat_x(b))
    hob = housing.build()
    hob.location = fp

    hatch = Part("Hatch")
    hatch.box(M["panel"], (0, 0.6, 0), (0.07, 1.2, 1.2), 0.03, None, 2)
    hatch.box(M["metal"], (-0.05, 0.6, 0), (0.03, 0.5, 0.08), 0.01)
    hatch.cyl(M["glass"], (-0.04, 0.6, 0.35), (0.04, 0.6, 0.35), 0.08, 24)
    hatch_ob = hatch.build()
    hatch_ob.location = (3.8, -0.6, 0)

    # surface kit: saddles, legs, footpads (Moon / Mars) and orbit kit: solar arrays
    surf = Part("SurfaceKit")
    ground = -3.4
    for x in (-2.2, 2.2):
        surf.revolve(M["metal"], ring_profile(x - 0.12, x + 0.12, R + 0.17, R + 0.3, 0.02), 200 * DEG, 340 * DEG, 24)
        for sy in (-1, 1):
            top = Vector((x, sy * 1.4, -1.9))
            foot = Vector((x + 0.0, sy * 2.3, ground + 0.12))
            surf.cyl(M["metal"], top, foot, 0.07, 16)
            surf.cyl(M["steel"], top + (foot - top) * 0.45, foot, 0.05, 16)
            surf.cyl(M["foot"], foot - Vector((0, 0, 0.12)), foot, 0.36, 28, r2=0.24)
        surf.box(M["metal"], (x, 0, -2.0), (0.18, 2.8, 0.14), 0.02)
    # ladder at -X end
    for sy in (-1, 1):
        surf.cyl(M["metal"], (-4.2, sy * 0.3, ground), (-4.2, sy * 0.3, -0.9), 0.025, 10)
    for z in np.arange(ground + 0.3, -1.0, 0.3):
        surf.cyl(M["metal"], (-4.2, -0.3, z), (-4.2, 0.3, z), 0.02, 8)
    surf_ob = surf.build()

    orbit = Part("OrbitKit")
    orbit.cyl(M["metal"], (4.15, 0, 0), (5.4, 0, 0), 0.12, 20)
    orbit.box(M["metal"], (5.4, 0, 0), (0.35, 0.5, 0.5), 0.03)
    orbit_ob = orbit.build()
    wings = []
    for sgn in (-1, 1):
        w = Part(f"OrbitKit_Wing{'A' if sgn > 0 else 'B'}")
        w.cyl(M["metal"], (0, 0, sgn * 0.2), (0, 0, sgn * 8.2), 0.035, 12)
        for k in range(4):
            z0 = sgn * (0.5 + k * 1.95)
            w.box(M["solar"], (0, 0, z0 + sgn * 0.95), (2.2, 0.02, 1.88), 0.004)
            w.box(M["metal"], (0, 0, z0 + sgn * 0.95), (2.26, 0.012, 1.94), 0.0)
        wob = w.build()
        wob.location = (5.4, 0, 0)
        wings.append(wob)
    # radiator panel on the far side
    rad = Part("OrbitKit_Radiator")
    rad.box(M["radiator"], (-1.0, R + 1.2, 0.0), (4.0, 0.04, 1.4), 0.01)
    rad.cyl(M["metal"], (-1.0, R + 0.17, 0), (-1.0, R + 1.2, 0), 0.04, 12)
    rad_ob = rad.build()

    # anchors (fire locations, vents, detector) as empties so the GLB is self-describing
    for name, loc in LAYOUT["locations"].items():
        e = bpy.data.objects.new(f"anchor_{name}", None)
        e.location = B(loc["anchor"])
        sc.collection.objects.link(e)
    for k, p in LAYOUT["ventilation"].items():
        e = bpy.data.objects.new(f"vent_{k}", None)
        e.location = B(p)
        sc.collection.objects.link(e)

    # ---- animation -----------------------------------------------------------------------
    sc.frame_start, sc.frame_end = 0, 60
    fan_ob.keyframe_insert("rotation_euler", frame=0)
    fan_ob.rotation_euler = (TAU, 0, 0)
    fan_ob.keyframe_insert("rotation_euler", frame=15)
    hatch_ob.keyframe_insert("rotation_euler", frame=0)
    hatch_ob.rotation_euler = (0, 0, 100 * DEG)
    hatch_ob.keyframe_insert("rotation_euler", frame=45)
    for wob in wings:
        wob.rotation_euler = (0, 0, -25 * DEG)
        wob.keyframe_insert("rotation_euler", frame=0)
        wob.rotation_euler = (0, 0, 25 * DEG)
        wob.keyframe_insert("rotation_euler", frame=300)
    for ob, name in ((fan_ob, "FanSpin"), (hatch_ob, "HatchOpen"), *((w, "ArrayTrack") for w in wings)):
        act = ob.animation_data.action
        act.name = f"{name}_{ob.name}"
        _linear(act)

    # ---- AO bake into one atlas --------------------------------------------------------------
    baked = [shell_ob, inner_ob, front_ob, surf_ob, hatch_ob, hob, rad_ob, orbit_ob]
    size = 1024 if QUICK else 4096
    bake_ao(sc, baked, OUT / "habitat_ao.webp", size, samples=16 if QUICK else 96, distance=0.55)
    for w in wings:
        uv_box(w)

    OUT.mkdir(parents=True, exist_ok=True)
    export(OUT / "habitat.glb")
    stats = {ob.name: len(ob.data.polygons) for ob in sc.objects if ob.type == "MESH"}
    print("habitat polygons:", stats, "total", sum(stats.values()))


def _linear(action):
    try:
        curves = action.fcurves
    except AttributeError:            # Blender 5: layered actions
        curves = [fc for layer in action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def uv_box(ob):
    """planar UV for solar wings: one cell texture across each blanket"""
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (v.x / 2.2 + 0.5, abs(v.z) / 1.95)


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def bake_ao(sc, objs, path, size, samples, distance):
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66 * DEG, island_margin=0.0015, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False, margin_method="FRACTION")
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.0015, shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.0015)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("AO", size, size, alpha=False, float_buffer=True)
    nodes = []
    for o in objs:
        for m in o.data.materials:
            n = m.node_tree.nodes.new("ShaderNodeTexImage")
            n.image = img
            m.node_tree.nodes.active = n
            nodes.append((m, n))
    sc.world.light_settings.distance = distance
    sc.cycles.samples = samples
    sc.render.bake.margin = 6
    sc.render.bake.margin_type = "EXTEND"
    bpy.ops.object.bake(type="AO")
    for m, n in nodes:
        m.node_tree.nodes.remove(n)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)[..., 0]
    px = soften(px)
    px = np.clip(px, 0, 1) ** 0.85
    save_gray(px, path)
    bpy.data.images.remove(img)


def soften(px):
    """small separable blur: removes bake noise but keeps contact shadows"""
    k = np.array([1, 4, 6, 4, 1], np.float32) / 16
    out = px.copy()
    for ax in (0, 1):
        out = sum(np.roll(out, s - 2, axis=ax) * w for s, w in enumerate(k))
    return out


def save_gray(px, path, quality=88):
    save_rgb(np.repeat(px[..., None], 3, -1), path, quality)


def save_rgb(rgb, path, quality=86, fmt="WEBP"):
    """write raw values (no view transform): pixel row 0 is the bottom of the image"""
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w, _ = rgb.shape
    img = bpy.data.images.new(path.stem, w, h, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(rgb, 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = str(path)
    img.file_format = fmt
    img.save(quality=quality)
    bpy.data.images.remove(img)


def export(path, selection=None):
    if selection:
        select_only(selection)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=bool(selection),
                              export_apply=True, export_animations=True, export_yup=True,
                              export_texcoords=True, export_normals=True, export_extras=True,
                              export_materials="EXPORT", export_image_format="NONE", export_cameras=False,
                              export_lights=False, export_animation_mode="ACTIONS",
                              export_meshopt_compression_enable=True)


# ---- terrain --------------------------------------------------------------------------------
TERRAIN = {"size_m": 240.0, "res": 512, "ground_y": -3.4}


def fbm(n, octaves, seed, base=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n), np.float32)
    amp = 1.0
    for o in range(octaves):
        g = base * 2 ** o
        grid = rng.standard_normal((g + 3, g + 3)).astype(np.float32)
        out += amp * upsample(grid, n)
        amp *= 0.5
    return out / 2


def upsample(grid, n):
    """bicubic-ish (smoothstep) interpolation of a periodic random grid"""
    g = grid.shape[0] - 3
    t = np.linspace(0, g, n, endpoint=False)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    rows = grid[i][:, None, :] * (1 - f)[:, None, None] + grid[i + 1][:, None, :] * f[:, None, None]
    rows = rows[:, 0, :]
    return rows[:, i] * (1 - f)[None, :] + rows[:, i + 1] * f[None, :]


def craters(h, n, size, count, rmin, rmax, seed, depth=0.35):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n] * (size / n) - size / 2
    for _ in range(count):
        r = rmin * (rmax / rmin) ** (rng.random() ** 2.2)
        cx, cy = rng.uniform(-size / 2, size / 2, 2)
        if math.hypot(cx, cy) < 22 + r:
            continue
        d = np.hypot(xx - cx, yy - cy) / r
        bowl = np.where(d < 1, (d ** 2 - 1) * depth * r * 0.5, 0)
        rim = np.exp(-((d - 1.0) / 0.22) ** 2) * depth * r * 0.18
        ejecta = np.where(d > 1, np.exp(-(d - 1) * 2.2) * depth * r * 0.05, 0)
        h += bowl + rim + ejecta
    return h


def build_terrain(body):
    sc = reset()
    n, size = TERRAIN["res"], TERRAIN["size_m"]
    yy, xx = np.mgrid[0:n, 0:n] * (size / n) - size / 2
    rr = np.hypot(xx, yy)
    if body == "moon":
        h = fbm(n, 7, 11, 3) * 1.2
        h = craters(h, n, size, 260, 0.6, 26, 5, 0.42)
        h += np.clip((rr - 60) / 60, 0, 1) ** 2 * fbm(n, 4, 3, 2) * 14
    else:
        dunes = np.sin(xx * 0.16 + fbm(n, 3, 8, 2) * 3.5) * 0.45 + np.sin(yy * 0.07 + xx * 0.03) * 0.6
        h = fbm(n, 7, 21, 3) * 1.6 + dunes
        h = craters(h, n, size, 40, 1.0, 18, 9, 0.25)
        h += np.clip((rr - 55) / 55, 0, 1) ** 1.6 * (fbm(n, 5, 4, 2) * 10 + 9)
        # a mesa escarpment on the horizon
        h += np.clip((xx + yy * 0.3 - 70) / 10, 0, 1) * 16
    # flat, compacted pad under the habitat
    pad = np.clip((rr - 9) / 14, 0, 1)
    pad = pad * pad * (3 - 2 * pad)
    h = h * pad
    h -= h[n // 2, n // 2]

    # mesh for baking: displaced grid with the rocks on it
    res = 256 if QUICK else 384
    me = bpy.data.meshes.new(f"terrain_{body}")
    gy, gx = np.mgrid[0:res, 0:res] / (res - 1)
    hi = sample(h, gx * (n - 1), gy * (n - 1))
    verts = np.stack([(gx - 0.5) * size, (gy - 0.5) * size, hi], -1).reshape(-1, 3)
    faces = []
    for j in range(res - 1):
        for i in range(res - 1):
            a = j * res + i
            faces.append((a, a + 1, a + res + 1, a + res))
    me.from_pydata(verts.tolist(), [], faces)
    uv = me.uv_layers.new(name="UVMap")
    loops_v = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loops_v)
    uvs = np.stack([verts[loops_v, 0] / size + 0.5, verts[loops_v, 1] / size + 0.5], -1)
    uv.data.foreach_set("uv", uvs.ravel())
    for p in me.polygons:
        p.use_smooth = True
    ground = bpy.data.objects.new(f"terrain_{body}", me)
    sc.collection.objects.link(ground)

    # rocks: four variants, scattered with a size power law, kept clear of the pad
    rock_meshes = make_rocks(body)
    rng = np.random.default_rng(77 if body == "mars" else 78)
    rocks = []
    count = 520 if body == "mars" else 380
    while len(rocks) < count:
        x, y = rng.uniform(-size / 2 * 0.92, size / 2 * 0.92, 2)
        r = math.hypot(x, y)
        if r < 7.5:
            continue
        s = 0.08 + 1.4 * rng.random() ** 5 * (1 + r / 60)
        if r < 14:
            s *= 0.4
        z = float(sample(h, np.array([(x / size + 0.5) * (n - 1)]), np.array([(y / size + 0.5) * (n - 1)]))[0])
        rocks.append({"v": int(rng.integers(4)), "p": [round(x, 3), round(z - s * 0.25, 3), round(-y, 3)],
                      "s": [round(s * rng.uniform(0.8, 1.3), 3), round(s * rng.uniform(0.5, 0.9), 3),
                            round(s * rng.uniform(0.8, 1.3), 3)], "r": round(float(rng.uniform(0, TAU)), 3)})
    for k, rk in enumerate(rocks):
        ob = bpy.data.objects.new(f"rock{k}", rock_meshes[rk["v"]])
        x, y3, z3 = rk["p"]
        ob.location = (x, -z3, y3)
        ob.scale = (rk["s"][0], rk["s"][2], rk["s"][1])
        ob.rotation_euler = (0, 0, rk["r"])
        sc.collection.objects.link(ob)
    # a stand-in for the habitat footprint so the pad gets its contact shadow
    pad_ob = bpy.data.objects.new("hab_shadow", bpy.data.meshes.new("hab_shadow"))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=2.3, radius2=2.3, depth=8.2,
                          matrix=Matrix.Translation((0, 0, 3.4)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    bm.to_mesh(pad_ob.data)
    bm.free()
    sc.collection.objects.link(pad_ob)

    # procedural regolith shader -> baked albedo
    m = bpy.data.materials.new(f"regolith_{body}")
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 0.08
    tex.inputs["Detail"].default_value = 12
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 1.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.35
    if body == "mars":
        cols = ["#5f2f1b", "#9a5634", "#c08052", "#7a3f25"]
    else:
        cols = ["#3f3e3c", "#6b6965", "#94918c", "#55534f"]
    el = ramp.color_ramp.elements
    el[0].color = (*srgb(cols[0]), 1)
    el[1].color = (*srgb(cols[2]), 1)
    e = el.new(0.5)
    e.color = (*srgb(cols[1]), 1)
    e = el.new(0.8)
    e.color = (*srgb(cols[3]), 1)
    nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(coord.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix.inputs["A"])
    nt.links.new(vor.outputs["Color"], mix.inputs["B"])
    # convex edges (crater rims, rock shoulders) brighter, hollows darker: Cycles pointiness
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    rng_ = nt.nodes.new("ShaderNodeMapRange")
    rng_.inputs["From Min"].default_value = 0.47
    rng_.inputs["From Max"].default_value = 0.53
    rng_.inputs["To Min"].default_value = 0.72
    rng_.inputs["To Max"].default_value = 1.25
    edge = nt.nodes.new("ShaderNodeMix")
    edge.data_type = "RGBA"
    edge.blend_type = "MULTIPLY"
    edge.inputs["Factor"].default_value = 1.0
    nt.links.new(geo.outputs["Pointiness"], rng_.inputs["Value"])
    nt.links.new(mix.outputs["Result"], edge.inputs["A"])
    nt.links.new(rng_.outputs["Result"], edge.inputs["B"])
    nt.links.new(edge.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.95
    me.materials.append(m)
    rock_mat = bpy.data.materials.new(f"rock_{body}")
    rock_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*srgb(cols[0]), 1)
    for rm in rock_meshes:
        rm.materials.clear()
        rm.materials.append(rock_mat)
    pad_ob.data.materials.append(rock_mat)

    bsize = 1024 if QUICK else 2048
    img_c = bpy.data.images.new("albedo", bsize, bsize, alpha=False, float_buffer=True)
    img_a = bpy.data.images.new("ao", bsize, bsize, alpha=False, float_buffer=True)
    node = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = node
    select_only([ground])
    sc.cycles.samples = 1
    node.image = img_c
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    sc.render.bake.margin = 4
    bpy.ops.object.bake(type="DIFFUSE")
    node.image = img_a
    sc.world.light_settings.distance = 6.0
    sc.cycles.samples = 16 if QUICK else 96
    bpy.ops.object.bake(type="AO")
    col = np.array(img_c.pixels[:], np.float32).reshape(bsize, bsize, 4)[..., :3]
    ao = soften(np.array(img_a.pixels[:], np.float32).reshape(bsize, bsize, 4)[..., 0])
    shade = (0.35 + 0.65 * ao)[..., None]
    lin = np.clip(col * shade, 0, 1)
    rgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    save_rgb(rgb, OUT / f"terrain_{body}_albedo.webp", 84)

    # height: 16 bit fixed point in R (high byte) and G (low byte), range in the JSON
    lo, hi_ = float(h.min()), float(h.max())
    q = np.round((h - lo) / (hi_ - lo) * 65535).astype(np.uint32)
    enc = np.zeros((n, n, 3), np.float32)
    enc[..., 0] = (q >> 8) / 255.0
    enc[..., 1] = (q & 255) / 255.0
    save_rgb(enc, OUT / f"terrain_{body}_height.png", 100, fmt="PNG")
    meta = {"body": body, "size_m": size, "resolution": n, "height_min_m": lo, "height_max_m": hi_,
            "ground_y": TERRAIN["ground_y"], "encoding": "R*256+G over 65535, row 0 = -Z edge, column 0 = -X edge",
            "rocks": rocks}
    (OUT / f"terrain_{body}.json").write_text(json.dumps(meta, separators=(",", ":")))


def sample(h, x, y):
    n = h.shape[0]
    x = np.clip(x, 0, n - 1.001)
    y = np.clip(y, 0, n - 1.001)
    i, j = x.astype(int), y.astype(int)
    fx, fy = x - i, y - j
    return (h[j, i] * (1 - fx) * (1 - fy) + h[j, i + 1] * fx * (1 - fy)
            + h[j + 1, i] * (1 - fx) * fy + h[j + 1, i + 1] * fx * fy)


ROCKS = []


def make_rocks(body):
    if ROCKS:
        return ROCKS
    for k in range(4):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        rng = np.random.default_rng(100 + k)
        dirs = rng.standard_normal((9, 3))
        dirs /= np.linalg.norm(dirs, axis=1)[:, None]
        for v in bm.verts:
            p = np.array(v.co)
            # flatten a few faces (fractured facets) and add lumps
            d = 1.0 + 0.18 * np.sin(p @ dirs[0] * 3 + k) + 0.1 * np.sin(p @ dirs[1] * 6)
            for c in dirs[2:6]:
                d = min(d, 0.78 / max(0.3, p @ c) if p @ c > 0.3 else d)
            v.co = Vector(p * d)
        me = bpy.data.meshes.new(f"rock_v{k}")
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = False
        ROCKS.append(me)
    sc = bpy.context.scene
    objs = []
    for k, me in enumerate(ROCKS):
        ob = bpy.data.objects.new(f"rock_v{k}", me)
        sc.collection.objects.link(ob)
        ob.location = (k * 3, 0, -100)
        objs.append(ob)
    return ROCKS


def export_rocks():
    reset()
    ROCKS.clear()
    make_rocks("any")
    m = material("Rock", "#777777", 0.92)
    objs = [o for o in bpy.context.scene.objects if o.name.startswith("rock_v")]
    for o in objs:
        o.location = (0, 0, 0)
        o.data.materials.clear()
        o.data.materials.append(m)
    export(OUT / "rocks.glb", objs)


# ---- lunar globe (lunar-orbit backdrop) --------------------------------------------------------
def build_globe():
    w, h = (1024, 512) if QUICK else (2048, 1024)
    lon = (np.arange(w) + 0.5) / w * TAU - math.pi
    lat = math.pi / 2 - (np.arange(h) + 0.5) / h * math.pi
    lo, la = np.meshgrid(lon, lat)
    xyz = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1).astype(np.float32)
    rng = np.random.default_rng(1969)
    height = np.zeros((h, w), np.float32)
    # maria: broad dark basins (mostly on the near side)
    albedo = np.full((h, w), 0.62, np.float32)
    for _ in range(14):
        c = rng.standard_normal(3)
        c[0] = abs(c[0]) + 0.6
        c /= np.linalg.norm(c)
        r = rng.uniform(0.18, 0.45)
        d = np.arccos(np.clip(xyz @ c, -1, 1)) / r
        albedo -= 0.3 * np.exp(-d ** 3) * rng.uniform(0.6, 1)
        height -= 0.4 * np.exp(-d ** 2)
    # craters, power-law sizes, with bright rays on the youngest
    for k in range(1800 if not QUICK else 400):
        c = rng.standard_normal(3)
        c /= np.linalg.norm(c)
        r = 0.004 * (40 ** (rng.random() ** 3.2))
        cosd = xyz @ c
        mask = cosd > math.cos(min(r * 4, 1.2))
        if not mask.any():
            continue
        d = np.arccos(np.clip(cosd[mask], -1, 1)) / r
        height[mask] += np.where(d < 1, (d ** 2 - 1) * 0.6, 0) + np.exp(-((d - 1) / 0.25) ** 2) * 0.25
        albedo[mask] += np.where(d < 1.15, 0.06, 0) + (0.12 if k % 97 == 0 else 0) * np.exp(-(d - 1) / 1.6) * (d > 1)
    noise = upsample(rng.standard_normal((131, 131)).astype(np.float32), max(w, h))[:h, :w] * 0.04
    albedo = np.clip(albedo + noise, 0.08, 0.95)
    save_rgb(np.repeat(albedo[..., None], 3, -1), OUT / "moon_globe.webp", 86)
    hn = (height - height.min()) / (np.ptp(height) + 1e-6)
    save_rgb(np.repeat(hn[..., None], 3, -1), OUT / "moon_globe_height.webp", 88)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if ONLY in (None, "habitat"):
        build_habitat()
    if ONLY in (None, "terrain"):
        for body in ("moon", "mars"):
            ROCKS.clear()
            build_terrain(body)
        export_rocks()
    if ONLY in (None, "globe"):
        build_globe()
    print("done ->", OUT)
