"""Landing-page hero cinematic: the HAB-01 module in Earth orbit, rendered in Cycles.

The hero of index.html shows a still behind the wordmark. This script renders the same subject
as a short seamless loop (and the stills that stand in for it), from the shipped model
`frontend/assets/3d/habitat.glb`, so the film and the lab always show the same spacecraft.

Look: one hard sun, black sky, the Earth's limb low in the frame, the module seen as the lab's
cutaway (front wall off), a slow camera sway. Every motion is a sine of the loop phase, so the
last frame runs straight into the first one: no cross-fade, no jump.

    pip install bpy                                  # or Blender 4.2+ / 5.x
    python blender/build_cinematic.py --test         # one low-res frame per framing, fast
    python blender/build_cinematic.py --frames OUT   # PNG frames of the loop (desktop 16:9)
    python blender/build_cinematic.py --stills OUT   # poster stills: desktop 16:9 + phone portrait
    python blender/build_cinematic.py --save FILE    # keep the editable .blend

Encoding (scripts/encode_hero.sh) turns the frames into the web MP4/WebM and the poster WebP.
Coordinates: Blender Z-up; the glTF importer turns the model's Y-up into Z-up.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLB = os.path.join(ROOT, "frontend", "assets", "3d", "habitat.glb")

FPS = 24
LOOP_S = 10                      # one full sway; slow is the point
FRAMES = FPS * LOOP_S
EARTH_R = 1000.0                 # same scale as the lab's Earth-orbit backdrop
EARTH_C = Vector((0.0, 260.0, -1072.0))
SUN_DIR = Vector((0.50, -0.60, 0.62)).normalized()     # towards the sun (Blender axes)
TARGET = Vector((0.2, 0.0, -0.15))                     # what the camera looks at (module centre)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true")
    p.add_argument("--frames")
    p.add_argument("--stills")
    p.add_argument("--save")
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=FRAMES - 1)
    p.add_argument("--step", type=int, default=1, help="render every Nth frame (the encoder interpolates the rest)")
    p.add_argument("--res", default="1920x1080")
    return p.parse_args(a)


# ------------------------------------------------------------------ scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.02
    s.cycles.use_denoising = True
    s.cycles.denoiser = "OPENIMAGEDENOISE"
    s.cycles.max_bounces = 6
    s.cycles.diffuse_bounces = 3
    s.cycles.glossy_bounces = 3
    s.cycles.transmission_bounces = 4
    s.cycles.transparent_max_bounces = 6
    s.cycles.sample_clamp_indirect = 6.0
    s.cycles.seed = 7                       # same noise pattern every frame: no shimmer in the loop
    s.render.fps = FPS
    s.frame_start, s.frame_end = 0, FRAMES - 1
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    s.view_settings.exposure = -0.35
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_depth = "8"
    s.render.film_transparent = False
    return s


def import_module():
    bpy.ops.import_scene.gltf(filepath=GLB)
    objs = list(bpy.context.selected_objects)
    for o in objs:
        o.animation_data_clear()
        base = o.name.split(".")[0]
        # the lab's exterior look: cutaway (front wall off), orbit kit on, surface kit off
        if base in ("FrontWall", "SurfaceKit") or o.type == "EMPTY":
            o.hide_render = True
            o.hide_viewport = True
    # two finishes read better under a single hard sun than the lab's real-time values
    for m in bpy.data.materials:
        if not m.node_tree:
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        if m.name.startswith("MLI_Kapton"):        # crinkled foil: a touch more sheen, less mirror
            bsdf.inputs["Roughness"].default_value = max(bsdf.inputs["Roughness"].default_value, 0.32)
        if m.name.startswith("Solar_Cell"):        # cover glass: dark, with a clean sun glint
            bsdf.inputs["Roughness"].default_value = 0.12
            bsdf.inputs["Metallic"].default_value = 0.0
            bsdf.inputs["Specular IOR Level"].default_value = 0.6
    return objs


def node(nt, kind, loc=(0, 0), **inputs):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in inputs.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:                                   # a node property such as operation or blend type
            setattr(n, k, v)
    return n


def earth():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=EARTH_R, location=EARTH_C)
    e = bpy.context.object
    e.name = "Earth"
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("Earth")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (900, 0))
    tc = node(nt, "ShaderNodeTexCoord", (-1200, 0))
    rot = node(nt, "ShaderNodeVectorRotate", (-1000, 0))
    rot.rotation_type = "EULER_XYZ"
    rot.inputs["Rotation"].default_value = (0.35, 0.8, 0.12)
    nt.links.new(tc.outputs["Object"], rot.inputs["Vector"])
    # continents: two octaves of fBm like the lab's shader, thresholded with a narrow coast
    n1 = node(nt, "ShaderNodeTexNoise", (-800, 200), Scale=0.006, Detail=6.0, Roughness=0.55)
    nt.links.new(rot.outputs["Vector"], n1.inputs["Vector"])
    land = node(nt, "ShaderNodeValToRGB", (-600, 200))
    land.color_ramp.elements[0].position, land.color_ramp.elements[1].position = 0.50, 0.525
    nt.links.new(n1.outputs["Fac"], land.inputs["Fac"])
    n2 = node(nt, "ShaderNodeTexNoise", (-800, -100), Scale=0.03, Detail=4.0)
    nt.links.new(rot.outputs["Vector"], n2.inputs["Vector"])
    ground = node(nt, "ShaderNodeValToRGB", (-600, -100))
    cr = ground.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.35, (0.022, 0.035, 0.014, 1)
    cr.elements[1].position, cr.elements[1].color = 0.68, (0.16, 0.115, 0.066, 1)
    nt.links.new(n2.outputs["Fac"], ground.inputs["Fac"])
    ocean = (0.004, 0.017, 0.055, 1)
    mix = node(nt, "ShaderNodeMix", (-350, 100))
    mix.data_type = "RGBA"
    mix.inputs["B"].default_value = ocean
    nt.links.new(land.outputs["Color"], mix.inputs["Factor"])
    mix.inputs["A"].default_value = ocean
    nt.links.new(ground.outputs["Color"], mix.inputs["B"])
    # clouds: a finer, more contrasted noise; they sit on the surface (no parallax needed from 70 km)
    n3 = node(nt, "ShaderNodeTexNoise", (-800, -400), Scale=0.016, Detail=8.0, Roughness=0.62, Distortion=0.4)
    nt.links.new(rot.outputs["Vector"], n3.inputs["Vector"])
    cl = node(nt, "ShaderNodeValToRGB", (-600, -400))
    cl.color_ramp.elements[0].position, cl.color_ramp.elements[1].position = 0.55, 0.74
    nt.links.new(n3.outputs["Fac"], cl.inputs["Fac"])
    mix2 = node(nt, "ShaderNodeMix", (-150, 0))
    mix2.data_type = "RGBA"
    mix2.inputs["B"].default_value = (0.62, 0.64, 0.67, 1)
    nt.links.new(mix.outputs["Result"], mix2.inputs["A"])
    nt.links.new(cl.outputs["Color"], mix2.inputs["Factor"])
    # water is glossy, land and cloud are matte
    rough = node(nt, "ShaderNodeMath", (-150, -250), operation="MAXIMUM")
    nt.links.new(land.outputs["Color"], rough.inputs[0])
    nt.links.new(cl.outputs["Color"], rough.inputs[1])
    rmap = node(nt, "ShaderNodeMapRange", (50, -250))
    rmap.inputs["To Min"].default_value, rmap.inputs["To Max"].default_value = 0.22, 0.95
    nt.links.new(rough.outputs[0], rmap.inputs["Value"])
    bsdf = node(nt, "ShaderNodeBsdfPrincipled", (300, 0))
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    nt.links.new(mix2.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(rmap.outputs["Result"], bsdf.inputs["Roughness"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    e.data.materials.append(m)
    e.visible_shadow = False            # the module never shadows the planet at this scale
    return e


def atmosphere():
    """a thin shell whose glow follows the limb (facing ratio) and the lit side (sun angle)"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=EARTH_R * 1.012, location=EARTH_C)
    a = bpy.context.object
    a.name = "Atmosphere"
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("Atmosphere")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (900, 0))
    lw = node(nt, "ShaderNodeLayerWeight", (-600, 0), Blend=0.5)
    pw = node(nt, "ShaderNodeMath", (-400, 0), operation="POWER")
    pw.inputs[1].default_value = 7.0
    nt.links.new(lw.outputs["Facing"], pw.inputs[0])
    geo = node(nt, "ShaderNodeNewGeometry", (-800, -250))
    dot = node(nt, "ShaderNodeVectorMath", (-600, -250), operation="DOT_PRODUCT")
    dot.inputs[1].default_value = SUN_DIR
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    lit = node(nt, "ShaderNodeMapRange", (-400, -250))
    lit.inputs["From Min"].default_value, lit.inputs["From Max"].default_value = -0.25, 0.45
    nt.links.new(dot.outputs["Value"], lit.inputs["Value"])
    k = node(nt, "ShaderNodeMath", (-200, 0), operation="MULTIPLY")
    nt.links.new(pw.outputs[0], k.inputs[0])
    nt.links.new(lit.outputs["Result"], k.inputs[1])
    em = node(nt, "ShaderNodeEmission", (100, 100), Strength=1.6)
    em.inputs["Color"].default_value = (0.20, 0.42, 1.0, 1)
    tr = node(nt, "ShaderNodeBsdfTransparent", (100, -100))
    sc = node(nt, "ShaderNodeMath", (100, -300), operation="MULTIPLY")
    nt.links.new(k.outputs[0], sc.inputs[0])
    sc.inputs[1].default_value = 1.0
    mixs = node(nt, "ShaderNodeMixShader", (400, -150))
    nt.links.new(sc.outputs[0], mixs.inputs["Fac"])
    nt.links.new(tr.outputs[0], mixs.inputs[1])
    nt.links.new(em.outputs[0], mixs.inputs[2])
    nt.links.new(mixs.outputs[0], out.inputs["Surface"])
    a.data.materials.append(m)
    a.visible_shadow = False
    a.visible_diffuse = a.visible_glossy = False
    return a


def sky():
    w = bpy.data.worlds.new("Space")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputWorld", (800, 0))
    # stars only for the camera; the module is lit by the sun, the Earth's bounce and a faint fill
    lp = node(nt, "ShaderNodeLightPath", (-200, 300))
    vor = node(nt, "ShaderNodeTexVoronoi", (-700, 0), Scale=260.0)
    vor.feature = "F1"
    geo = node(nt, "ShaderNodeNewGeometry", (-900, -200))
    nt.links.new(geo.outputs["Incoming"], vor.inputs["Vector"])
    # small, sparse points: distance under a threshold, brightness from the cell's random colour
    thr = node(nt, "ShaderNodeMapRange", (-500, 0))
    thr.inputs["From Min"].default_value, thr.inputs["From Max"].default_value = 0.065, 0.0
    nt.links.new(vor.outputs["Distance"], thr.inputs["Value"])
    sep = node(nt, "ShaderNodeSeparateColor", (-500, -200))
    nt.links.new(vor.outputs["Color"], sep.inputs["Color"])
    keep = node(nt, "ShaderNodeMath", (-300, -200), operation="GREATER_THAN")
    keep.inputs[1].default_value = 0.9                        # ~1 cell in 10 has a star
    nt.links.new(sep.outputs["Red"], keep.inputs[0])
    b = node(nt, "ShaderNodeMath", (-100, 0), operation="MULTIPLY")
    nt.links.new(thr.outputs["Result"], b.inputs[0])
    nt.links.new(keep.outputs[0], b.inputs[1])
    g = node(nt, "ShaderNodeMath", (100, 0), operation="MULTIPLY")
    nt.links.new(b.outputs[0], g.inputs[0])
    nt.links.new(sep.outputs["Green"], g.inputs[1])
    bg_stars = node(nt, "ShaderNodeBackground", (300, 100))
    bg_stars.inputs["Color"].default_value = (0.92, 0.95, 1.0, 1)
    sm = node(nt, "ShaderNodeMath", (300, -50), operation="MULTIPLY")
    sm.inputs[1].default_value = 3.0
    nt.links.new(g.outputs[0], sm.inputs[0])
    nt.links.new(sm.outputs[0], bg_stars.inputs["Strength"])
    bg_fill = node(nt, "ShaderNodeBackground", (300, -200), Strength=0.035)
    bg_fill.inputs["Color"].default_value = (0.55, 0.65, 0.85, 1)
    mixs = node(nt, "ShaderNodeMixShader", (600, 0))
    nt.links.new(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
    nt.links.new(bg_fill.outputs[0], mixs.inputs[1])
    nt.links.new(bg_stars.outputs[0], mixs.inputs[2])
    nt.links.new(mixs.outputs[0], out.inputs["Surface"])


def sun():
    d = bpy.data.lights.new("Sun", "SUN")
    d.energy = 4.2
    d.angle = math.radians(0.53)
    d.color = (1.0, 0.975, 0.94)
    o = bpy.data.objects.new("Sun", d)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = SUN_DIR.to_track_quat("Z", "Y").to_euler()
    # Earthshine: a broad, weak blue-white light from below, as the lit planet fills the shadows
    e = bpy.data.lights.new("Earthshine", "SUN")
    e.energy = 0.32
    e.angle = math.radians(60)
    e.color = (0.62, 0.74, 1.0)
    eo = bpy.data.objects.new("Earthshine", e)
    bpy.context.scene.collection.objects.link(eo)
    eo.rotation_euler = (-Vector((0.1, 0.25, -1)).normalized()).to_track_quat("Z", "Y").to_euler()


# ------------------------------------------------------------------ camera
FRAMING = {
    # azimuth / elevation (deg) around TARGET, distance (m), lens (mm), screen shift
    "desktop": dict(az=-126.0, el=15.0, dist=31.0, lens=42.0, shift_y=0.15, shift_x=0.0),
    "phone": dict(az=-122.0, el=16.0, dist=38.0, lens=35.0, shift_y=0.175, shift_x=0.0),
}


def camera(kind):
    f = FRAMING[kind]
    c = bpy.data.cameras.new("Cam")
    c.lens = f["lens"]
    c.shift_y = f["shift_y"]
    c.shift_x = f["shift_x"]
    c.clip_start, c.clip_end = 0.1, 5000
    o = bpy.data.objects.new("Cam", c)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.scene.camera = o
    return o, f


def place(cam, f, phase):
    """camera at loop phase 0..1: every term is periodic, so phase 1 == phase 0 exactly"""
    w = 2 * math.pi * phase
    az = math.radians(f["az"] + 7.0 * math.sin(w))
    el = math.radians(f["el"] + 1.6 * math.sin(w + math.pi / 2) - 1.6)
    dist = f["dist"] * (1 - 0.035 * (0.5 - 0.5 * math.cos(w)))       # a slight push-in mid-loop
    off = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))) * dist
    cam.location = TARGET + off
    look = (TARGET - cam.location).normalized()
    q = look.to_track_quat("-Z", "Y")
    # a whisper of roll keeps it from feeling like a turntable
    cam.rotation_euler = q.to_euler()
    cam.rotation_euler.rotate_axis("Z", math.radians(0.6 * math.sin(w + 0.7)))


def build(kind="desktop"):
    s = reset()
    import_module()
    earth()
    atmosphere()
    sky()
    sun()
    cam, f = camera(kind)
    for i in range(FRAMES + 1):          # keyframes so the saved .blend scrubs like the film
        place(cam, f, i / FRAMES)
        cam.keyframe_insert("location", frame=i)
        cam.keyframe_insert("rotation_euler", frame=i)
    return s, cam, f


def render_frames(out, a):
    s, cam, f = build("desktop")
    w, h = (int(x) for x in a.res.split("x"))
    s.render.resolution_x, s.render.resolution_y = w, h
    s.cycles.samples = a.samples
    os.makedirs(out, exist_ok=True)
    for i in range(a.start, a.end + 1, a.step):
        p = os.path.join(out, f"f{i:04d}.png")
        if os.path.exists(p):
            continue
        s.frame_set(i)
        s.render.filepath = p
        bpy.ops.render.render(write_still=True)
        print(f"frame {i}/{FRAMES - 1}", flush=True)


def render_stills(out, a):
    os.makedirs(out, exist_ok=True)
    for kind, (w, h) in (("desktop", (2400, 1350)), ("phone", (828, 1792))):
        s, cam, f = build(kind)
        s.render.resolution_x, s.render.resolution_y = w, h
        s.cycles.samples = max(a.samples, 128)
        s.frame_set(0)
        s.render.filepath = os.path.join(out, f"hero-{kind}.png")
        bpy.ops.render.render(write_still=True)


def main():
    a = args()
    if a.test:
        out = a.frames or "/tmp/cine_test"
        os.makedirs(out, exist_ok=True)
        for kind, (w, h) in (("desktop", (960, 540)), ("phone", (414, 896))):
            s, cam, f = build(kind)
            s.render.resolution_x, s.render.resolution_y = w, h
            s.cycles.samples = 24
            for ph in (0.0, 0.25, 0.5):
                s.frame_set(int(ph * FRAMES))
                s.render.filepath = os.path.join(out, f"test-{kind}-{int(ph * 100):02d}.png")
                bpy.ops.render.render(write_still=True)
        return
    if a.frames:
        render_frames(a.frames, a)
    if a.stills:
        render_stills(a.stills, a)
    if a.save:
        build("desktop")
        bpy.context.scene.cycles.samples = a.samples
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save), compress=True)


if __name__ == "__main__":
    main()
