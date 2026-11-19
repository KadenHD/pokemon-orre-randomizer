"""Compose ten private PAL CB atlases from approved x4 head and UI PNGs."""
from pathlib import Path
import argparse,hashlib,json,math,sys
from PIL import Image
from cb_portrait_composite import fade_portrait_rgba

sha=lambda b:hashlib.sha256(b).hexdigest()
def checked_image(root,asset):
 path=root/asset['file'];payload=path.read_bytes()
 if sha(payload)!=asset['sha256']:raise ValueError('Pinned input SHA256 differs: '+asset['file'])
 with Image.open(path) as source:
  if source.mode!='RGBA' or list(source.size)!=asset['dimensions']:raise ValueError('Pinned RGBA dimensions differ: '+asset['file'])
  return source.copy()

def compose(recipe,inputs,output,project_root):
 """Validate every input/slot before creating the new output directory."""
 sys.path.insert(0,str(project_root));sys.dont_write_bytecode=True
 from orre_randomizer.artwork import _png
 if output.is_symlink() or output.exists():raise ValueError('Output must be a new nonsymlink directory')
 if sha(Path(fade_portrait_rgba.__code__.co_filename).read_bytes())!=recipe['lower_portrait_fade_helper_sha256']:
  raise ValueError('The approved shared fade helper differs')
 if recipe.get('lower_portrait_fade')!={'native_rows':14,'source_scale':4,'operation':'alpha-only-before-reduction',
     'envelope':'.6*(1-t)+.4*(1-3*t*t+2*t*t*t)','t':'0..1 inclusive over the last 56 source rows','applied_once':True}:
  raise ValueError('The approved shared lower-bust envelope is required')
 heads={name:fade_portrait_rgba(checked_image(inputs,asset)) for name,asset in recipe['heads'].items()}
 ready=[]
 for record in recipe['atlases']:
  image=checked_image(inputs,record['UI_layer']);expected=[4*v for v in record['native_dimensions']]
  if list(image.size)!=expected:raise ValueError('Atlas scale mismatch')
  if len(record['portraits'])!=5 or len({p['identity'] for p in record['portraits']})!=5:raise ValueError('Five distinct actors required')
  placements=[]
  for placement in record['portraits']:
   head=heads[placement['identity']];x,y,z,t=placement['box_x4']
   if not(0<=x<z<=image.width and 0<=y<t<=image.height):raise ValueError('Portrait slot is outside the atlas')
   if image.getchannel('A').crop((x,y,z,t)).getbbox() is not None:raise ValueError('Portrait would overwrite approved UI')
   if placement['operation']=='identity-canvas':
    if head.size!=(z-x,t-y):raise ValueError('Unscaled approved canvas does not match source crop')
    layer=head;offset=(x,y);scale=1.0
   elif placement['operation']=='uniform-contain-bottom-center':
    scale=min((z-x)/head.width,(t-y)/head.height)
    if scale>1:raise ValueError('Small portrait must be a reduction of its approved x4 render')
    width=max(1,round(head.width*scale));height=max(1,round(head.height*scale))
    if width>z-x or height>t-y:raise ValueError('Rounded portrait does not fit the slot')
    layer=head.convert('RGBa').resize((width,height),Image.Resampling.LANCZOS).convert('RGBA')
    offset=(x+((z-x)-width)//2,t-height)
   else:raise ValueError('Unknown composition operation')
   placements.append((layer,offset,{**placement,'uniform_scale':scale,'raster_dimensions':list(layer.size),'offset_x4':list(offset),
    'framing_rotation_changed':False,'nonuniform_geometry_scaling':False,'raster_rounding_max_pixels':.5,'new_clipping':False}))
  for layer,offset,_ in placements:image.alpha_composite(layer,offset)
  raw=bytearray(image.tobytes())
  for index in range(0,len(raw),4):
   if not raw[index+3]:raw[index:index+3]=b'\0\0\0'
  png=_png(image.size,bytes(raw))
  approved=recipe.get('approved_outputs',{}).get(record['target_native_key'])
  if approved and sha(png)!=approved:raise ValueError('Composition differs from its approved output SHA256')
  ready.append((record,png,[r for _,_,r in placements]))
 output.mkdir(parents=True,exist_ok=False);records=[]
 for record,png,placements in ready:
  name=record['target_native_key'];(output/name).write_bytes(png)
  records.append({**record,'file':name,'sha256':sha(png),'bytes':len(png),'dimensions':[4*v for v in record['native_dimensions']],
   'portrait_placements':placements,'complete_layers':True,'native_bitmap_upscaled_for_HD':False,'review_only':not bool(recipe.get('art_approval') and recipe.get('approved_outputs')),
   'visible_GUI_runtime_validated':False,'missing_layers':[],'lower_portrait_fade':recipe['lower_portrait_fade'],'notes':recipe['limitations']})
 (output/'atlas-manifest.json').write_text(json.dumps({'schema':1,'atlases':records,'review_only':not bool(recipe.get('art_approval') and recipe.get('approved_outputs')),'public_product_written':False},indent=2)+'\n',encoding='utf-8')
 return records

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--recipe',type=Path,required=True);parser.add_argument('--inputs',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True);parser.add_argument('--project-root',type=Path,required=True)
 args=parser.parse_args();recipe=json.loads(args.recipe.read_text(encoding='utf-8'))
 result=compose(recipe,args.inputs.resolve(),args.output.resolve(),args.project_root.resolve())
 print(json.dumps({'atlases':len(result),'output':str(args.output),'new_3D_render':False,'Dolphin_started':False}),flush=True)
if __name__=='__main__':main()
