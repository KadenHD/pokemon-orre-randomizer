"""Second and final CB framing pass: actual source meshes, paired raster sizes.

Run inside an isolated Blender CLI after prepare_models.py. No model, bone or
UV is edited. Native maps are retained where no exact external HD map exists.
"""
from pathlib import Path
import hashlib,json,math,struct,sys,os
import bpy
from mathutils import Vector

HERE=Path(os.environ['CB_WORKDIR']);ROOT=Path(os.environ['CB_PROJECT_ROOT'])
OUT=HERE/'renders';OUT.mkdir(exist_ok=False)
sys.path.insert(0,os.environ['CB_ADDON'])
if not hasattr(bpy.types.Action,'fcurves'):
 from bpy_extras.anim_utils import action_ensure_channelbag_for_slot
 bpy.types.Action.fcurves=property(lambda a:action_ensure_channelbag_for_slot(a,a.slots.active).fcurves)
import importer.importer as imp
from importer.phases.build_blender.helpers import materials as material_builder
from shared.helpers.logger import Logger
native_image=material_builder._resolve_image;uses=[]
def tagged(br_image,cache):
 image=native_image(br_image,cache)
 if image is not None:
  pair=':'.join(str(v) for v in br_image.cache_key)
  image['cb_descriptor_pair']=pair;uses.append(pair)
 return image
material_builder._resolve_image=tagged
original_plan=imp.plan_scene
def first_idle(ir_scene,options,logger):
 result=original_plan(ir_scene,options,logger=logger);header=options.get('pkx_header')
 index=header.anim_entries[0].sub_anims[0].anim_index if header and header.anim_entries and header.anim_entries[0].sub_anims else 0
 for model in result.models:
  if model.actions:model.actions=[model.actions[index]]
 return result
imp.plan_scene=first_idle
sha=lambda b:hashlib.sha256(b).hexdigest()
def pose(arm):
 return sha(b''.join(struct.pack('<16f',*(v for r in b.matrix for v in r)) for b in arm.pose.bones))
def geometry(scene):
 deps=bpy.context.evaluated_depsgraph_get();records=[]
 for obj in scene.objects:
  if obj.type!='MESH' or obj.hide_render:continue
  evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
  data=b''.join(struct.pack('<3f',*(obj.matrix_world@v.co)) for v in mesh.vertices)
  data+=b''.join(struct.pack('<I',i) for p in mesh.polygons for i in p.vertices)
  for layer in mesh.uv_layers:data+=b''.join(struct.pack('<2f',*v.uv) for v in layer.data)
  records.append(sha(data));evaluated.to_mesh_clear()
 return sha('\n'.join(sorted(records)).encode())
manifest=json.loads((HERE/'model-materials.json').read_text(encoding='utf8'))
guides=json.loads((HERE/'guide-metadata.json').read_text(encoding='utf8'))
guide_map={r['identity_visual']:r for r in guides['records']}
reports=[]
for row in manifest['models']:
 name=row['proposed_identity'];uses=[]
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
 scene.render.engine='BLENDER_EEVEE';scene.render.film_transparent=True
 scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
 scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-1.0
 scene.world=bpy.data.worlds.new('owned CB world');scene.world.use_nodes=True
 scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
 scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6
 source=HERE/row['file'];raw=source.read_bytes();assert sha(raw)==row['source']['raw_sha256']
 log=Logger(model_name='CB-final-'+name)
 imp.Importer.run(bpy.context,raw,source.name,{'game':'COLO_XD','colo_xd_kind':row['source']['kind'],
  'max_frame':15,'ik_hack':False,'include_shiny':False,'import_lights':False,'import_cameras':False},logger=log)
 scene.frame_set(0);bpy.context.view_layer.update()
 arm=next(o for o in scene.objects if o.type=='ARMATURE')
 fk=row.get('authored_shoulder_FK')
 if fk:
  from mathutils import Matrix
  arm.animation_data_clear();affected=set()
  for index in fk['native_bone_indices']:
   bone=arm.pose.bones[f'Bone_{index:02d}'];affected.add(bone.name);affected.update(b.name for b in bone.children_recursive)
  for bone in arm.pose.bones:
   if bone.name in affected:
    for constraint in bone.constraints:
     if constraint.type=='IK':constraint.mute=True
  bpy.context.view_layer.update()
  for index,degrees in zip(fk['native_bone_indices'],fk['armature_Y_degrees']):
   bone=arm.pose.bones[f'Bone_{index:02d}'];pivot=bone.head.copy()
   bone.matrix=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(degrees),4,'Y')@Matrix.Translation(-pivot)@bone.matrix
   bpy.context.view_layer.update()
 deps=bpy.context.evaluated_depsgraph_get();points=[]
 for obj in scene.objects:
  if obj.type!='MESH' or obj.hide_render:continue
  ev=obj.evaluated_get(deps);mesh=ev.to_mesh();points.extend(obj.matrix_world@v.co for v in mesh.vertices);ev.to_mesh_clear()
 low=Vector([min(p[i] for p in points) for i in range(3)]);high=Vector([max(p[i] for p in points) for i in range(3)])
 height=high.z-low.z;head=[p for p in points if p.z>=high.z-height*.22]
 center=Vector([(min(p[i] for p in head)+max(p[i] for p in head))/2 for i in range(3)])
 target=Vector((center.x,center.y,high.z-height*(.11 if name=='wes' else .14)))
 span=height*(.34 if name=='wes' else .42)
 elevation=math.radians(8);direction=Vector((0,-math.cos(elevation),math.sin(elevation)))
 bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
 camera.location=target+direction*height*3;camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
 camera.data.type='ORTHO';camera.data.ortho_scale=span;camera.data.clip_end=10000
 for i in (0,1):
  bpy.ops.object.light_add(type='AREA');light=bpy.context.object
  light.location=target+Vector(((-1 if i==0 else 1)*height,-height*2,height*2))
  light.data.energy=(100 if i==0 else 65)*height*height;light.data.size=height*2
  light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
 guide=guide_map[row['visual_guide']];large=next(r for r in guide['files'] if 'large-' in r['file'])
 dims=large['dimensions'];signature=pose(arm);geo=geometry(scene)
 base={'identity':name,'visual_guide':row['visual_guide'],'identity_basis':'direct rendered cap/bandana, face, hair and costume match to the original menu guide',
  'source':row['source'],'native_dimensions':dims,'HD_dimensions':[4*v for v in dims],
  'pose_signature_sha256':signature,'evaluated_geometry_and_UV_sha256':geo,'bone_count':len(arm.pose.bones),
  'action':arm.animation_data.action.name if arm.animation_data and arm.animation_data.action else None,'frame':0,
  'camera':{'type':'ORTHO','span':span,'target':list(target),'matrix':[list(r) for r in camera.matrix_world],
    'elevation_degrees':8,'reconstructed_framing_from_original_guide':True},
  'lighting':{'reconstructed':True,'view':'Standard','exposure':-1,'key_energy_per_height_squared':100,'fill_energy_per_height_squared':65},
  'native_bitmap_upscaled_for_HD':False,'mesh_bones_UV_edited':False,
  'source_guide':large,'importer_leniencies':log.leniency_categories,'files':{}}
 for scale in (1,4):
  if scale==4:
   for material in bpy.data.materials:
    if not material.use_nodes:continue
    for node in material.node_tree.nodes:
     image=getattr(node,'image',None)
     if image is None:continue
     pair=image.get('cb_descriptor_pair');entry=row['material_map'].get(pair,{})
     donor=entry.get('HD')
     if donor:
      path=HERE/donor['render_file'];assert sha(path.read_bytes())==donor['render_sha256']
      replacement=bpy.data.images.load(str(path),check_existing=True)
      replacement.colorspace_settings.name=image.colorspace_settings.name;node.image=replacement
   bpy.context.view_layer.update()
  assert pose(arm)==signature and geometry(scene)==geo
  scene.render.resolution_x=dims[0]*scale;scene.render.resolution_y=dims[1]*scale;scene.render.resolution_percentage=100
  path=OUT/(name+('-native.png' if scale==1 else '-x4.png'))
  scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
  base['files'][str(scale)]={'file':path.name,'sha256':sha(path.read_bytes()),'bytes':path.stat().st_size,
   'dimensions':[v*scale for v in dims]}
 actual=sorted(set(uses));assert all(k in row['material_map'] for k in actual)
 base['materials']=[{'pair':k,'native_key':row['material_map'][k]['native_key'],
  'native_dimensions':row['material_map'][k]['native_dimensions'],
  'HD':({field:row['material_map'][k]['HD'][field] for field in ('pack','sha256','width','height','source_scale','format','mip_levels','render_sha256')}
        if row['material_map'][k]['HD'] else None),
  'native_map_retained_without_pre_enlargement':row['material_map'][k]['HD'] is None} for k in actual]
 base['HD_material_count']=sum(x['HD'] is not None for x in base['materials'])
 base['native_retained_material_count']=len(actual)-base['HD_material_count']
 base['pose_limit']='Source Idle for May/Brendan/Wes; approved authored shoulder FK for Red/Leaf. Original CGI lighting and exact pose are not claimed.'
 base['authored_shoulder_FK']=row.get('authored_shoulder_FK')
 base['pose_matrices_authored']=bool(row.get('authored_shoulder_FK'))
 reports.append(base)
 (OUT/'paired-render-proof.json').write_text(json.dumps({'schema':1,'review_only':True,'renders':reports},indent=2)+'\n',encoding='utf-8')
 bpy.context.preferences.filepaths.file_preview_type='NONE';bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'-paired.blend')))
 print('CB_FINAL_PAIR_DONE '+name,flush=True)
print('CB_FINAL_FIVE_COMPLETE',flush=True)
