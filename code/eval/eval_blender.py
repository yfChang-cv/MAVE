"""Blender side of the MAVEBench evaluator (run by evaluate.py, not by hand):

    blender -b scene.blend -P eval_blender.py -- <job.json>

job.json: {"width", "height", "frames" (video frame count), "keyframes" (0-based video frames), "out"}.
Video frame f is Blender frame f + 1 (METHOD_PROMPT.md rule 1). Writes into "out":
  cameras.json   per video frame: COLMAP-style R, t (x_cam = R X + t, +z forward, y down) and fx, fy, cx, cy at
                 width x height; plus the scene facts the evaluator checks (frame range, fps, resolution, camera)
  kf_<i>.npz     index (int16: 0 = nothing, 1 = scene geometry, 2 + p = person p, front-most surface, so
                 occlusion counts) and depth (float32 planar depth along the camera axis, 0 = nothing)
  people.json    the people found (rule, names, objects) and which are hidden on each keyframe
Rendering: Cycles, 1 sample, no pixel filter, one flat material on everything (no transparency), film
transparent; object index + position passes through a File Output node (EXR), read back with bpy.
People: children of the "People" collection (METHOD_PROMPT rule 3: each direct child object with its descendants,
or each sub-collection, is one person). If there is no such collection (outputs made before the rule),
root objects named P<number>... (P01, P02_Root) are taken as people, rule "name_P". A person whose root object is
keyed hide_render is hidden with all its parts (Blender itself would still render unhidden children).
"""

import json
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Matrix

job = json.loads(open(sys.argv[sys.argv.index("--") + 1]).read())
W, H, OUT = job["width"], job["height"], job["out"]
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
facts = {"frame_start": scene.frame_start, "frame_end": scene.frame_end, "fps": scene.render.fps / scene.render.fps_base,
         "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
         "camera": scene.camera.name if scene.camera else None, "warnings": []}


# ---------- people ----------
def descendants(obj):
    out = [obj]
    for child in obj.children:
        out += descendants(child)
    return out


def collection_objects(col):
    out = list(col.objects)
    for child in col.children:
        out += collection_objects(child)
    return out


people = []  # [{"name", "root" (object or None), "objects"}]
people_col = next((c for c in bpy.data.collections if c.name.lower() == "people"), None)
if people_col is not None and collection_objects(people_col):
    rule = "collection"
    members = set(collection_objects(people_col))
    for sub in people_col.children:
        objs = collection_objects(sub)
        roots = [o for o in objs if o.parent not in objs]
        people.append({"name": sub.name, "root": roots[0] if len(roots) == 1 else None, "objects": objs})
    for obj in people_col.objects:
        if obj.parent is None or obj.parent not in members:
            people.append({"name": obj.name, "root": obj, "objects": descendants(obj)})
else:
    rule = "name_P"
    for obj in scene.objects:
        if obj.parent is None and re.match(r"^P\d+", obj.name):
            people.append({"name": obj.name, "root": obj, "objects": descendants(obj)})
people.sort(key=lambda p: p["name"])
person_of = {}
for p, person in enumerate(people):
    for obj in person["objects"]:
        person_of.setdefault(obj.name, p)

# ---------- render settings ----------
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
device = None
for kind in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = kind
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            device = kind
            break
    except TypeError:
        continue
for d in prefs.devices:
    d.use = d.type == device
scene.cycles.device = "GPU" if device else "CPU"
facts["device"] = device or "CPU"
scene.cycles.samples = 1
scene.cycles.use_adaptive_sampling = False
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 0
scene.cycles.filter_width = 0.01
scene.render.film_transparent = True
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
scene.render.use_motion_blur = False
scene.render.use_persistent_data = True
if facts["resolution"][0] * H != facts["resolution"][1] * W:
    facts["warnings"].append(f"render aspect {facts['resolution'][:2]} differs from the video {W}x{H}")

flat = bpy.data.materials.new("eval_flat")
view_layer = scene.view_layers[0]
for vl in scene.view_layers:
    vl.use = vl == view_layer
view_layer.material_override = flat
view_layer.use_pass_object_index = True
view_layer.use_pass_position = True
view_layer.use_pass_combined = True

base_hidden = {}
for obj in scene.objects:
    obj.pass_index = 2 + person_of[obj.name] if obj.name in person_of else 1
    base_hidden[obj.name] = obj.hide_render


def keyed_hide(obj) -> bool:
    ad = obj.animation_data
    return bool(ad and ad.action and any(fc.data_path == "hide_render" for fc in ad.action.fcurves))


scene.use_nodes = True
tree = scene.node_tree
tree.nodes.clear()
layers = tree.nodes.new("CompositorNodeRLayers")
composite = tree.nodes.new("CompositorNodeComposite")
tree.links.new(layers.outputs["Image"], composite.inputs["Image"])
file_out = tree.nodes.new("CompositorNodeOutputFile")
file_out.base_path = os.path.join(OUT, "exr")
file_out.format.file_format = "OPEN_EXR"
file_out.format.color_depth = "32"
file_out.format.exr_codec = "ZIP"
file_out.file_slots.clear()
for name, socket in (("index", "IndexOB"), ("position", "Position")):
    file_out.file_slots.new(name)
    tree.links.new(layers.outputs[socket], file_out.inputs[name])
scene.render.filepath = os.path.join(OUT, "exr", "combined_")


# ---------- camera ----------
FLIP = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))


def camera_at(frame: int) -> dict:
    scene.frame_set(frame)
    cam = scene.camera
    data = cam.data
    world = cam.matrix_world.normalized()
    R_bl = world.to_3x3().transposed()
    t_bl = -(R_bl @ world.translation)
    R, t = FLIP @ R_bl, FLIP @ t_bl
    fit = data.sensor_fit
    if fit == "AUTO":
        fit = "HORIZONTAL" if W >= H else "VERTICAL"
    sensor = data.sensor_width if fit == "HORIZONTAL" or data.sensor_fit == "AUTO" else data.sensor_height
    f = data.lens / sensor * (W if fit == "HORIZONTAL" else H)
    size = max(W, H)
    return {"R": [list(r) for r in R], "t": list(t), "fx": f, "fy": f, "cx": W / 2 - data.shift_x * size,
            "cy": H / 2 + data.shift_y * size, "type": data.type}


cameras = []
if scene.camera is None:
    facts["warnings"].append("no scene.camera")
else:
    for f in range(job["frames"]):
        cameras.append(camera_at(f + 1))
    if any(c["type"] != "PERSP" for c in cameras):
        facts["warnings"].append("camera is not perspective")


# ---------- keyframes ----------
def read_exr(path: str, channels: int) -> np.ndarray:
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    buf = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, img.channels)[::-1, :, :channels]
    bpy.data.images.remove(img)
    return arr


hidden_on = {}
for i, f in enumerate(job["keyframes"]):
    frame = f + 1
    scene.frame_set(frame)
    hidden = []
    for p, person in enumerate(people):
        root_hidden = person["root"] is not None and person["root"].hide_render
        for obj in person["objects"]:
            own = obj.hide_render if keyed_hide(obj) else base_hidden[obj.name]
            obj.hide_render = own or root_hidden
        if root_hidden or all(o.hide_render for o in person["objects"] if o.type == "MESH"):
            hidden.append(p)
    hidden_on[str(i)] = hidden
    if scene.camera is None:
        continue
    bpy.ops.render.render(write_still=False)
    index = np.rint(read_exr(os.path.join(OUT, "exr", f"index{frame:04d}.exr"), 1)[..., 0]).astype(np.int16)
    pos = read_exr(os.path.join(OUT, "exr", f"position{frame:04d}.exr"), 3)
    c = cameras[f]
    R_bl = np.array(FLIP) @ np.array(c["R"])
    t_bl = np.array(FLIP) @ np.array(c["t"])
    depth = -(pos @ R_bl.T + t_bl)[..., 2]
    depth[index == 0] = 0
    np.savez_compressed(os.path.join(OUT, f"kf_{i}.npz"), index=index, depth=depth.astype(np.float32))
    for name in (f"index{frame:04d}.exr", f"position{frame:04d}.exr"):
        os.remove(os.path.join(OUT, "exr", name))

json.dump({"facts": facts, "cameras": cameras}, open(os.path.join(OUT, "cameras.json"), "w"))
json.dump({"rule": rule, "people": [{"name": p["name"], "objects": len(p["objects"])} for p in people],
           "hidden": hidden_on}, open(os.path.join(OUT, "people.json"), "w"), indent=1)
print("EVAL_BLENDER_DONE", rule, len(people), "people", facts["device"])
