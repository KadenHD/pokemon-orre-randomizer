"""Fresh source import; fixed camera; native90 then pinned-HD360, no blends."""
from pathlib import Path
import hashlib,json,os,re,struct,sys
import bpy
from mathutils import Matrix,Vector
WORK=Path(os.environ['BINGO_WORKDIR']);sys.path.insert(0,os.environ['BINGO_ADDON'])
recipe=json.loads((WORK/'bingo-recipe.json').read_text())
if not hasattr(bpy.types.Action,'fcurves'):
 from bpy_extras.anim_utils import action_ensure_channelbag_for_slot
 bpy.types.Action.fcurves=property(lambda action:action_ensure_channelbag_for_slot(action,action.slots.active).fcurves)
import importer.importer as module
from importer.phases.build_blender.helpers import materials as material_builder
from shared.helpers.logger import Logger
plan=module.plan_scene
def idle_only(ir_scene,options,logger):
 result=plan(ir_scene,options,logger=logger);index=options['pkx_header'].anim_entries[0].sub_anims[0].anim_index
 for model in result.models:model.actions=[model.actions[index]]
 return result
module.plan_scene=idle_only
native_resolver=material_builder._resolve_image
def tagged_image(br_image,cache):
 image=native_resolver(br_image,cache)
 if image is not None:image['bingo_descriptor_pair']=':'.join(str(n) for n in br_image.cache_key)
 return image
material_builder._resolve_image=tagged_image
def pose_signature(arm):
 return hashlib.sha256(b''.join(struct.pack('<16f',*(v for r in b.matrix for v in r)) for b in arm.pose.bones)).hexdigest()
def geometry_signature(scene):
 deps=bpy.context.evaluated_depsgraph_get();entries=[]
 for obj in scene.objects:
  if obj.type!='MESH' or obj.hide_render:continue
  evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();source=bytearray()
  payload=bytearray(struct.pack('<2I',len(mesh.vertices),len(mesh.loops)))
  for v in obj.data.vertices:source.extend(struct.pack('<3f',*v.co))
  for loop in obj.data.loops:
   source.extend(struct.pack('<I',loop.vertex_index))
   if obj.data.uv_layers.active:source.extend(struct.pack('<2f',*obj.data.uv_layers.active.data[loop.index].uv))
  for v in mesh.vertices:payload.extend(struct.pack('<3f',*(obj.matrix_world@v.co)))
  for loop in mesh.loops:
   payload.extend(struct.pack('<I',loop.vertex_index))
   if mesh.uv_layers.active:payload.extend(struct.pack('<2f',*mesh.uv_layers.active.data[loop.index].uv))
  entries.append((hashlib.sha256(source).hexdigest(),hashlib.sha256(payload).hexdigest()));evaluated.to_mesh_clear()
 entries.sort();return hashlib.sha256(''.join(w for s,w in entries).encode()).hexdigest()
out=WORK/'actors';out.mkdir(exist_ok=False);receipts=[]
for row in recipe['models']:
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
 scene.render.engine='BLENDER_EEVEE';scene.render.film_transparent=True
 scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
 scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-.6
 scene.world=bpy.data.worlds.new('owned world');scene.world.use_nodes=True
 scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5
 path=WORK/'models'/(row['model']+'.pkx');raw=path.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==row['source']['PKX_sha256']
 log=Logger(model_name='bingo-reproduce-'+row['model'])
 module.Importer.run(bpy.context,raw,path.name,{'game':'COLO_XD','colo_xd_kind':'PKX_POKEMON',
  'max_frame':180 if row['frame'] else 15,'ik_hack':False,'include_shiny':False,
  'import_lights':False,'import_cameras':False},logger=log)
 scene.frame_set(row['frame']);bpy.context.view_layer.update()
 arm=next(o for o in scene.objects if o.type=='ARMATURE')
 assert pose_signature(arm)==row['pose_signature_sha256'],('Source pose mismatch',row['model'])
 assert geometry_signature(scene)==row['geometry_UV_sha256'],('Source visible geometry/UV mismatch',row['model'])
 bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
 camera.matrix_world=Matrix(row['camera']['matrix']);camera.data.type=row['camera']['type']
 camera.data.lens=row['camera']['lens'];camera.data.sensor_fit='HORIZONTAL';camera.data.sensor_width=row['camera']['sensor_width']
 camera.data.shift_x,camera.data.shift_y=row['camera']['shift'];camera.data.clip_end=10000
 target=Vector(row['lights']['source_target']);height=row['lights']['source_height']
 for index in (0,1):
  bpy.ops.object.light_add(type='AREA');light=bpy.context.object
  light.location=target+Vector(((-1 if index==0 else 1)*height,-height*2,height*2))
  light.data.energy=(250 if index==0 else 100)*height*height;light.data.size=height*2
  light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
 scene.render.resolution_x=scene.render.resolution_y=90
 native=out/f'{row["cell"]:02d}-{row["model"]}-native90.png';scene.render.filepath=str(native);bpy.ops.render.render(write_still=True)
 used=set()
 for material in bpy.data.materials:
  if not material.use_nodes:continue
  for node in material.node_tree.nodes:
   if node.type!='TEX_IMAGE' or not node.image:continue
   pair=node.image.get('bingo_descriptor_pair');assert pair in row['materials'],pair
   donor=row['materials'][pair];path=WORK/donor['render_PNG']
   assert hashlib.sha256(path.read_bytes()).hexdigest()==donor['render_PNG_sha256']
   alpha=node.image.alpha_mode;node.image=bpy.data.images.load(str(path),check_existing=True);node.image.alpha_mode=alpha
   used.add(pair)
 assert used and all(row['materials'][pair]['source']['source_scale']==4 for pair in used)
 assert pose_signature(arm)==row['pose_signature_sha256'] and geometry_signature(scene)==row['geometry_UV_sha256']
 scene.render.resolution_x=scene.render.resolution_y=360
 hd=out/f'{row["cell"]:02d}-{row["model"]}-HD360.png';scene.render.filepath=str(hd);bpy.ops.render.render(write_still=True)
 receipts.append({'cell':row['cell'],'model':row['model'],'pose_signature_sha256':row['pose_signature_sha256'],
  'geometry_UV_sha256':row['geometry_UV_sha256'],'exact_x4_material_pairs':sorted(used),
  'native_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'HD_sha256':hashlib.sha256(hd.read_bytes()).hexdigest(),
  'lighting_reconstructed':True,'GPU_byte_exact_across_drivers_claimed':False})
 (WORK/'actor-render-receipt.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
print('PORTABLE_BINGO_RENDER_COMPLETE',flush=True)
