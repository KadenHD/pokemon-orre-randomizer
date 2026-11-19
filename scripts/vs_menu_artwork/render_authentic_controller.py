"""Owned render of unchanged characters; all rejected controller props hidden."""

import os
from pathlib import Path
import bpy

HERE = Path(os.environ['VS_WORKDIR']).resolve()
bpy.ops.wm.open_mainfile(filepath=str(HERE/'controller-scene-review.blend'))
scene=bpy.context.scene
actors=set()
for obj in bpy.data.objects:
    if obj.type=='ARMATURE' and obj.name.startswith(('rinto_0100_','trainer_f_0100_')):
        actors.update([obj,*list(obj.children_recursive)])
assert len(actors)>10
background=bpy.data.objects['procedural flame background']
for obj in bpy.data.objects:
    if obj.type in ('CAMERA','LIGHT'):continue
    obj.hide_render=obj not in actors and obj!=background
scene.render.filepath=str(HERE/'controller-clean-background-render.png')
bpy.ops.render.render(write_still=True)
background.hide_render=True
scene.render.filepath=str(HERE/'controller-clean-foreground-render.png')
bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.file_preview_type='NONE'
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'controller-authentic-photo-characters.blend'))
print('CLEAN_CHARACTERS_RENDER_COMPLETE',flush=True)
