"""Private VS scene reconstruction from source HSD meshes; not an HD atlas."""

import os
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

HERE = Path(os.environ['VS_WORKDIR']).resolve()
bpy.ops.wm.open_mainfile(filepath=str(HERE / 'identity-probe.blend'))
SCENE = bpy.context.scene
SCENE.render.resolution_x = 864
SCENE.render.resolution_y = 472
SCENE.render.resolution_percentage = 100
SCENE.render.film_transparent = True
SCENE.view_settings.view_transform = 'Standard'
SCENE.view_settings.exposure = -0.6
SCENE.view_settings.look = 'None'
SCENE.render.image_settings.file_format = 'PNG'
SCENE.render.image_settings.color_mode = 'RGBA'
CAMERA = SCENE.camera
CAMERA.data.type = 'ORTHO'
CAMERA.data.ortho_scale = 8.64
CAMERA.location = (0, -20, 0)
CAMERA.rotation_euler = (Vector((0, 0, 0))-CAMERA.location).to_track_quat('-Z','Y').to_euler()
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':bpy.data.objects.remove(obj,do_unlink=True)
for location,energy,size in [((-4,-7,7),1800,8),((5,-5,4),700,7)]:
    bpy.ops.object.light_add(type='AREA',location=location)
    light=bpy.context.object;light.data.energy=energy;light.data.size=size
    light.rotation_euler=(Vector((0,0,.7))-light.location).to_track_quat('-Z','Y').to_euler()

MODELS = {}
for obj in bpy.data.objects:
    if obj.type != 'ARMATURE':continue
    name=obj.name.rsplit('_skeleton_',1)[0]
    objects=[obj,*list(obj.children_recursive)]
    for member in objects:member.hide_render=True
    MODELS[name]=(obj,objects)


def pose_rot(arm,bone,axis,angle):
    pose=arm.pose.bones[bone]
    rest=pose.bone.matrix_local.to_3x3()
    pose.rotation_mode='QUATERNION'
    pose.rotation_quaternion=(rest.inverted()@Matrix.Rotation(math.radians(angle),3,axis)@rest).to_quaternion()


def character(name,x,top_pixel,scale,yaw=0,depth=0,salute=False):
    arm,objects=MODELS[name]
    if arm.animation_data:arm.animation_data_clear()
    muted=[]
    for pose in arm.pose.bones:
        pose.matrix_basis=Matrix.Identity(4)
        # This is an authored static FK pose, not native IK playback. The
        # imported target constraints would otherwise restore the bind arms.
        for constraint in pose.constraints:
            muted.append({'bone':pose.name,'constraint':constraint.type})
            constraint.mute=True
    arm.data.pose_position='POSE'
    # Select real upper-arm joints by rest hierarchy; no mesh/UV alteration.
    shoulders=[]
    for bone in arm.data.bones:
        if not .08<abs(bone.head_local.x)<.16 or bone.head_local.z<.85:continue
        if any(abs(c.head_local.x)>abs(bone.head_local.x)+.12 and abs(c.head_local.z-bone.head_local.z)<.05 for c in bone.children):
            shoulders.append(bone)
    for bone in shoulders:
        sign=1 if bone.head_local.x>0 else -1
        angle=sign*72
        if salute and sign>0:angle=-40
        pose_rot(arm,bone.name,'Y',angle)
        if salute and sign>0:
            elbow=next(c for c in bone.children if abs(c.head_local.x)>.25)
            pose_rot(arm,elbow.name,'Y',-100)
            wrists=[c for c in elbow.children if abs(c.head_local.x)>.4]
            if wrists:pose_rot(arm,wrists[0].name,'Y',110)
    arm.rotation_euler=(0,0,math.radians(yaw))
    arm.scale=(scale,)*3
    source=json.loads((HERE/'import-probe.json').read_text())
    high=next(r['bounds'][1][2] for r in source if r['model']==name)
    arm.location=(x,depth,2.36-top_pixel/100-high*scale)
    for obj in objects:obj.hide_render=False
    native_sources=json.loads((HERE/'candidate-models.json').read_text())['models']
    native_source=next(row for row in native_sources if row['member']==name)
    return {'model':name,'native_model_sha256':native_source['sha256'],
            'source_height':high,'scale':scale,'location':list(arm.location),
            'yaw_degrees':yaw,'upper_arm_bones':[b.name for b in shoulders],
            'native_constraints_muted_for_authored_FK_pose':muted,
            'authored_pose_not_original_prerender_pose':True,
            'pose_basis':{p.name:[list(row) for row in p.matrix_basis] for p in arm.pose.bones if not p.matrix_basis.is_identity}}


def material(name,color,rough=.35,metallic=0,emission=False):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    tree=mat.node_tree;tree.nodes.clear()
    output=tree.nodes.new('ShaderNodeOutputMaterial')
    shader=tree.nodes.new('ShaderNodeEmission' if emission else 'ShaderNodeBsdfPrincipled')
    if emission:
        shader.inputs['Color'].default_value=(*color[:3],1)
        shader.inputs['Strength'].default_value=1
    else:
        shader.inputs['Base Color'].default_value=(*color[:3],1)
        shader.inputs['Roughness'].default_value=rough
        shader.inputs['Metallic'].default_value=metallic
    tree.links.new(shader.outputs[0],output.inputs['Surface'])
    return mat


def mesh_shape(name,points,depth,mat,bevel=.04):
    n=len(points)
    vertices=[(x,-depth/2,z) for x,z in points]+[(x,depth/2,z) for x,z in points]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh);SCENE.collection.objects.link(obj)
    obj.data.materials.append(mat)
    if bevel:
        modifier=obj.modifiers.new('authored shell rounded edges','BEVEL');modifier.width=bevel;modifier.segments=4
        obj.modifiers.new('shell weighted normals','WEIGHTED_NORMAL')
    return obj




def rectangle(name,x,y,z,width,height,depth,mat,radius=.025):
    obj=mesh_shape(name,[(-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2)],depth,mat,radius)
    obj.location=(x,y,z);return obj


def line(name,coords,mat,radius=.02,poly=False):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.resolution_u=12
    if poly:
        spline=curve.splines.new('POLY');spline.points.add(len(coords)-1)
        for point,coord in zip(spline.points,coords):point.co=(*coord,1)
    else:
        spline=curve.splines.new('BEZIER');spline.bezier_points.add(len(coords)-1)
        for point,coord in zip(spline.bezier_points,coords):
            point.co=coord;point.handle_left_type='AUTO';point.handle_right_type='AUTO'
    curve.bevel_depth=radius;curve.bevel_resolution=4
    obj=bpy.data.objects.new(name,curve);SCENE.collection.objects.link(obj);obj.data.materials.append(mat)
    return obj








def backdrop(kind):
    before=set(bpy.data.objects)
    base=material('procedural '+kind+' backdrop',(0,0,0),emission=True)
    tree=base.node_tree;shader=next(n for n in tree.nodes if n.type=='EMISSION')
    coords=tree.nodes.new('ShaderNodeTexCoord')
    separate=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(coords.outputs['Generated'],separate.inputs[0])
    if kind=='flame':
        mapping=tree.nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY';mapping.inputs[1].default_value=(5,1,1.6)
        tree.links.new(coords.outputs['Generated'],mapping.inputs[0])
        noise=tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=2.1;noise.inputs['Detail'].default_value=3;noise.inputs['Roughness'].default_value=.68
        tree.links.new(mapping.outputs[0],noise.inputs['Vector'])
        height=tree.nodes.new('ShaderNodeMath');height.operation='MULTIPLY';height.inputs[1].default_value=.6
        tree.links.new(separate.outputs['Z'],height.inputs[0])
        cutoff=tree.nodes.new('ShaderNodeMath');cutoff.operation='SUBTRACT'
        tree.links.new(noise.outputs['Fac'],cutoff.inputs[0]);tree.links.new(height.outputs[0],cutoff.inputs[1])
        ramp=tree.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
        for idx,(position,color) in enumerate([(0,(.004,0,0,1)),(.21,(.027,.001,0,1)),(.34,(.13,.005,.001,1)),(.42,(.60,.025,.001,1)),(.50,(1,.20,.005,1)),(.62,(1,.65,.04,1))]):
            el=ramp.color_ramp.elements[0] if idx==0 else ramp.color_ramp.elements.new(position);el.position=position;el.color=color
        tree.links.new(cutoff.outputs[0],ramp.inputs[0]);tree.links.new(ramp.outputs[0],shader.inputs['Color'])
    else:
        noise=tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3;noise.inputs['Detail'].default_value=3
        tree.links.new(coords.outputs['Generated'],noise.inputs['Vector'])
        ramp=tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.0005,0,.004,1);ramp.color_ramp.elements[1].color=(.065,.004,.26,1)
        tree.links.new(noise.outputs['Fac'],ramp.inputs[0]);tree.links.new(ramp.outputs[0],shader.inputs['Color'])
    plane=rectangle('procedural '+kind+' background',0,5,0,8.7,4.8,.01,base,0)
    if kind!='flame':
        white=material('lightning white',(.85,.72,1),emission=True)
        purple=material('lightning purple',(.31,.025,.8),emission=True)
        paths=[[(.02,4.8,2.6),(.03,4.8,1.6),(-.19,4.8,1.45),(.12,4.8,.9),(-.15,4.8,.58),(.1,4.8,-.1)],
               [(-.08,4.8,1.6),(-.70,4.8,2.04),(-1.10,4.8,1.71),(-1.4,4.8,2.4)],
               [(.03,4.8,1.7),(.65,4.8,2.13),(1.3,4.8,1.85),(1.7,4.8,2.55)]]
        for i,path in enumerate(paths):
            line('lightning halo'+str(i),path,purple,.065,poly=True)
            line('lightning core'+str(i),[(x,y-.02,z) for x,y,z in path],white,.019,poly=True)
    return set(bpy.data.objects)-before


def render(name):
    SCENE.render.filepath=str(HERE/(name+'.png'));bpy.ops.render.render(write_still=True)


def geometry_record(name):
    _,objects=MODELS[name]
    digest=hashlib.sha256()
    vertices=triangles=loops=0
    for obj in sorted(objects,key=lambda value:value.name):
        if obj.type!='MESH':continue
        mesh=obj.data;vertices+=len(mesh.vertices);loops+=len(mesh.loops)
        for vertex in mesh.vertices:digest.update(struct.pack('<3f',*vertex.co))
        for polygon in mesh.polygons:
            indices=list(polygon.vertices);digest.update(struct.pack('<I',len(indices)))
            digest.update(struct.pack('<'+'I'*len(indices),*indices));triangles+=max(0,len(indices)-2)
        for layer in mesh.uv_layers:
            for uv in layer.data:digest.update(struct.pack('<2f',*uv.uv))
    return {'mesh_uv_digest_sha256':digest.hexdigest(),'vertices':vertices,'triangles':triangles,'loops':loops,
            'no_mesh_or_UV_edits_after_import':True}


def projected_box(obj):
    points=[world_to_camera_view(SCENE,CAMERA,obj.matrix_world@Vector(point)) for point in obj.bound_box]
    return [min(p.x for p in points)*864,(1-max(p.y for p in points))*472,
            max(p.x for p in points)*864,(1-min(p.y for p in points))*472]


requested=tuple(sys.argv[sys.argv.index('--')+1:]) if '--' in sys.argv else ('controller','gba')
assert requested and set(requested)<=set(('controller','gba'))
previous=json.loads((HERE/'scene-render-receipt.json').read_text()) if (HERE/'scene-render-receipt.json').exists() else []
receipts=[entry for entry in previous if entry['scene'] not in requested]
for kind in requested:
    for _,objects in MODELS.values():
        for obj in objects:obj.hide_render=True
    if kind=='controller':
        poses=[character('rinto_0100',-2.50,28,6.5,25),character('trainer_f_0100',2.65,8,8.0,-25)]
        props=set()
    else:
        poses=[character('gba_fl_m_0100',-1.45,17,6.2,10,.6,True),
               character('gba_emr_m_0100',2.10,3,6.0,-8,.6),
               character('gba_fl_f_0100',-3.20,75,6.3,10,0),
               character('gba_emr_f_0100',3.23,73,6.3,-14,0)]
        props=set()
    bpy.context.view_layer.update()
    # Staging only: render later without any hardware geometry.
    background=backdrop('flame' if kind=='controller' else 'lightning')
    # Staging only: background is preserved in the posed blend.
    shell=None
    receipts.append({'scene':kind,'dimensions':[864,472],'poses':poses,
                     'foreground_file':kind+'-scene-foreground-review.png',
                     'composite_file':kind+'-scene-composite-review.png',
                     'source_meshes':True,'props':'authentic hardware photographs composited separately',
                     'background':'authored procedural reconstruction','review_only':True,
                     'not_claimed_original_CGI_camera_or_pose':True,
                     'renderer_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     'camera':{'type':CAMERA.data.type,'ortho_scale':CAMERA.data.ortho_scale,
                               'matrix_world':[list(value) for value in CAMERA.matrix_world],
                               'exposure':SCENE.view_settings.exposure},
                     'reference':{'source_native_key':'tex1_284x462_1627f59f3f8175e5_b5b61a84a0f84832_9.png','native_windows':[[23,6,239,124],[23,134,239,252]]},
                     'meshes':{pose['model']:geometry_record(pose['model']) for pose in poses},
                     'hardware':'authentic photograph composited after character rendering',
                     'no_hardware_geometry':True})
    bpy.context.preferences.filepaths.file_preview_type='NONE'
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/(kind+'-scene-review.blend')))
    for obj in props|background:obj.hide_render=True
(HERE/'scene-render-receipt.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
bpy.context.preferences.filepaths.file_preview_type='NONE'
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'vs-scenes-review.blend'))
print('PRIVATE_VS_SCENES_COMPLETE',flush=True)
