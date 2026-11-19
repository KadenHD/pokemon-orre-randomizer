"""Render the four unchanged source-mesh characters; hide rejected hardware."""

import os
from pathlib import Path
import bpy

HERE = Path(os.environ['VS_WORKDIR']).resolve()
bpy.ops.wm.open_mainfile(filepath=str(HERE/'gba-scene-review.blend'))
scene=bpy.context.scene
actors=set()
prefixes=tuple(name+'_skeleton_' for name in ('gba_fl_f_0100','gba_fl_m_0100','gba_emr_f_0100','gba_emr_m_0100'))
for obj in bpy.data.objects:
    if obj.type=='ARMATURE' and obj.name.startswith(prefixes):
        actors.update([obj,*list(obj.children_recursive)])
assert len(actors)>30
background=[]
for obj in bpy.data.objects:
    keep_background=(obj.name=='procedural lightning background' or obj.name.startswith('lightning '))
    if keep_background:background.append(obj)
    if obj.type in ('CAMERA','LIGHT'):continue
    obj.hide_render=obj not in actors and not keep_background
assert len(background)==7
scene.render.filepath=str(HERE/'gba-clean-background-render.png')
bpy.ops.render.render(write_still=True)
for obj in background:obj.hide_render=True
scene.render.filepath=str(HERE/'gba-clean-foreground-render.png')
bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.file_preview_type='NONE'
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'gba-authentic-photo-characters.blend'))
print('CLEAN_GBA_CHARACTERS_RENDER_COMPLETE',flush=True)
