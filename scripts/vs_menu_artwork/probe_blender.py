"""Private HSD identity probe. No addon installation or user preferences."""

import os
from pathlib import Path
import hashlib
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = Path(os.environ['VS_WORKDIR']).resolve()
ROOT = Path(os.environ['VS_PROJECT_ROOT']).resolve()
ADDON = Path(os.environ['VS_HSD_ADDON']).resolve()
sys.path.insert(0, str(ADDON))

# Process-local compatibility for Blender's layered action API. No addon edits.
if not hasattr(bpy.types.Action, "fcurves"):
    from bpy_extras.anim_utils import action_ensure_channelbag_for_slot
    bpy.types.Action.fcurves = property(
        lambda action: action_ensure_channelbag_for_slot(
            action, action.slots.active
        ).fcurves
    )

from importer.importer import Importer
from shared.helpers.logger import Logger
from importer.phases.build_blender.helpers import materials as material_builder

MATERIAL_MAP = json.loads((HERE / 'material-map.json').read_text()) if (HERE / 'material-map.json').exists() else {}
CURRENT_MAP = {}
IMAGE_USE = []
_native_resolver = material_builder._resolve_image

def pinned_image(br_image, cache):
    if br_image is None:
        return None
    pair = ':'.join(str(value) for value in br_image.cache_key)
    entry = CURRENT_MAP.get(pair)
    IMAGE_USE.append({'descriptor_pair': pair, 'native_key': entry and entry['native_key'],
                      'hd': bool(entry and entry['hd'])})
    if entry and entry['hd']:
        image = bpy.data.images.load(str(HERE / entry['hd']['decoded_png']), check_existing=True)
        cache[br_image.cache_key] = image
        return image
    return _native_resolver(br_image, cache)

material_builder._resolve_image = pinned_image

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.render.use_file_extension = True
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast" if False else "None"
scene.world.color = (0.6, 0.6, 0.6)
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
bpy.ops.object.camera_add()
camera = bpy.context.object
camera.name = "PRIVATE_PROBE_CAMERA"
camera.data.type = "ORTHO"
camera.data.clip_end = 10000
scene.camera = camera
bpy.ops.object.light_add(type="AREA", location=(3, 5, 7))
key = bpy.context.object
key.data.energy = 500
key.data.shape = "DISK"
key.data.size = 5
bpy.ops.object.light_add(type="AREA", location=(-3, 3, 4))
fill = bpy.context.object
fill.data.energy = 200
fill.data.size = 5
reports = json.loads((HERE / 'import-probe.json').read_text()) if (HERE / 'import-probe.json').exists() else []
names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["pc_f_0000", "pc_f_1000", "rinto_0100"]
for name in names:
    CURRENT_MAP = MATERIAL_MAP.get(name, {})
    IMAGE_USE = []
    before = set(bpy.data.objects)
    source = HERE / "models" / (name + ".dat")
    log = Logger(model_name=name)
    error = None
    try:
        Importer.run(
            bpy.context, source.read_bytes(), source.name,
            {"ik_hack": False, "max_frame": 0, "game": "COLO_XD",
             "colo_xd_kind": "DAT_MODEL", "include_shiny": False,
             "import_lights": False, "import_cameras": False}, logger=log,
        )
    except Exception as exc:
        error = repr(exc)
    new = set(bpy.data.objects) - before
    meshes = [obj for obj in new if obj.type == "MESH" and obj.data.vertices]
    scene.frame_set(0)
    bpy.context.view_layer.update()
    corners = [obj.matrix_world @ Vector(p) for obj in meshes for p in obj.bound_box]
    report = {"model": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "error": error, "log": str(log.log_path), "warnings": log.warning_count,
              "leniencies": log.leniency_categories, "mesh_count": len(meshes),
              "vertices": sum(len(obj.data.vertices) for obj in meshes),
              "armatures": [{"name": obj.name, "bones": len(obj.data.bones)} for obj in new if obj.type == "ARMATURE"],
              "images": [{"name": im.name, "size": list(im.size)} for im in bpy.data.images if im.type == "IMAGE"]}
    report['used_material_images'] = IMAGE_USE
    report['bones'] = [{'name': bone.name, 'parent': bone.parent and bone.parent.name,
                        'head': list(bone.head_local), 'tail': list(bone.tail_local),
                        'matrix_local': [list(row) for row in bone.matrix_local]}
                       for obj in new if obj.type == 'ARMATURE' for bone in obj.data.bones]
    if corners:
        low = Vector(tuple(min(p[i] for p in corners) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in corners) for i in range(3)))
        report["bounds"] = [list(low), list(high)]
        target = (low + high) / 2
        height = max(high.z - low.z, high.x - low.x)
        # Upper-body framing, to identify the model. Not a final VS composition.
        target.z = low.z + (high.z - low.z) * 0.73
        camera.data.ortho_scale = height * 0.65
        for side in (() if os.environ.get('VS_IMPORT_ONLY')=='1' else (-1,)):
            camera.location = target + Vector((0, side * height * 2, 0))
            camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
            key.location = target + Vector((height, side * height, height * 1.5))
            fill.location = target + Vector((-height, side * height, height))
            key.data.energy = 300 * height * height
            fill.data.energy = 100 * height * height
            mode = 'hd-mixed' if CURRENT_MAP else 'native'
            scene.render.filepath = str(HERE / (name + f"-{mode}-view-{side:+d}.png"))
            bpy.ops.render.render(write_still=True)
    for obj in new:
        obj.hide_render = True
    reports = [entry for entry in reports if entry['model'] != name] + [report]
    (HERE / "import-probe.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
bpy.context.preferences.filepaths.file_preview_type = 'NONE'
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "identity-probe.blend"))
print("PRIVATE_PROBE_COMPLETE", flush=True)
