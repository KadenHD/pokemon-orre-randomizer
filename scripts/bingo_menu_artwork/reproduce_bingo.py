"""Portable CPU preparation and explicit isolated Blender render of Bingo art."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,struct,subprocess,sys,time

HERE=Path(__file__).resolve().parent
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--project-root',required=True,type=Path)
 parser.add_argument('--iso',required=True,type=Path)
 parser.add_argument('--xd-pack',required=True,type=Path)
 parser.add_argument('--addon',required=True,type=Path)
 parser.add_argument('--blender',type=Path)
 parser.add_argument('--work',required=True,type=Path)
 parser.add_argument('--render',action='store_true',help='Explicit graphical pass after CPU preparation')
 parser.add_argument('--render-prepared',action='store_true',help='Render an existing verified prepared directory')
 args=parser.parse_args();root=args.project_root.resolve();sys.path.insert(0,str(root))
 recipe=json.loads((HERE/'bingo-recipe.json').read_text())
 for relative,expected in recipe['addon']['python_sources_sha256'].items():
  assert digest(args.addon/relative)==expected,('Addon source mismatch',relative)
 from orre_randomizer.engine.survey_assets import fst_inventory
 from orre_randomizer.engine.analyze_game import parse_fsys
 from orre_randomizer.engine.rebuild_iso import decoded_member
 from orre_randomizer.hd_overlays import _pkx_dat
 from orre_randomizer.hd_images import resolve_texture,load_texture
 from orre_randomizer.artwork import _png
 from PySide6.QtGui import QImage
 work=args.work.resolve()
 if args.work.is_symlink():raise ValueError('Work directory cannot be a symlink')
 if args.render_prepared:
  receipt=json.loads((work/'prepared-inputs.json').read_text())
  assert receipt['recipe_sha256']==digest(HERE/'bingo-recipe.json')
  for row in receipt['files']:assert digest(work/row['file'])==row['sha256']
 else:
  work.mkdir(parents=True,exist_ok=False)
  (work/'models').mkdir();(work/'HD-textures').mkdir();(work/'layers').mkdir()
  pack=args.xd_pack/'Textures' if (args.xd_pack/'Textures').is_dir() else args.xd_pack
  files=[]
  def record(path):files.append({'file':path.relative_to(work).as_posix(),'sha256':digest(path)})
  with args.iso.open('rb') as stream:
   boot=stream.read(0x440);assert boot[:6]==b'GXXP01' and boot[7]==0
   offset,size=struct.unpack_from('>II',boot,0x424);assert size<8*1024**2
   stream.seek(offset);entries={r['path']:r for r in fst_inventory(stream.read(size))[0]}
   for row in recipe['models']:
    source=row['source'];entry=entries[source['archive']];assert entry['size']<4*1024**2
    stream.seek(entry['disc_offset']);archive=stream.read(entry['size'])
    assert hashlib.sha256(archive).hexdigest()==source['archive_sha256']
    member=next(r for r in parse_fsys(archive)['members'] if r['name']==row['model'])
    raw=decoded_member(archive,member);assert hashlib.sha256(raw).hexdigest()==source['PKX_sha256']
    dat=_pkx_dat(raw,True);assert hashlib.sha256(dat).hexdigest()==source['DAT_sha256']
    path=work/'models'/(row['model']+'.pkx');path.write_bytes(raw);record(path)
    for donor in row['materials'].values():
     target=work/donor['render_PNG']
     if target.exists():assert digest(target)==donor['render_PNG_sha256'];continue
     loaded=load_texture(resolve_texture(pack,donor['native_key']),expected_native_size=tuple(donor['native_dimensions']))
     assert loaded.metadata['source_scale']==4 and loaded.metadata['sha256']==donor['source']['sha256']
     image=loaded.image.convertToFormat(QImage.Format.Format_RGBA8888)
     target.write_bytes(_png((image.width(),image.height()),bytes(image.constBits())))
     assert digest(target)==donor['render_PNG_sha256'];record(target)
  for row in recipe['authored_layers']:
   source=HERE/row['file'];assert digest(source)==row['sha256']
   target=work/row['file'];shutil.copyfile(source,target);record(target)
  receipt={'schema':1,'recipe_sha256':digest(HERE/'bingo-recipe.json'),'source_opened_readonly':True,
    'models':11,'inventory_exact_x4_material_pairs':112,'selected_normal_clip_shader_pairs':103,
    'files':files,'Dolphin_started':False,'Blender_started':False}
  (work/'prepared-inputs.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
  shutil.copyfile(HERE/'bingo-recipe.json',work/'bingo-recipe.json')
 if args.render or args.render_prepared:
  if not args.blender or not args.blender.is_file():raise ValueError('Explicit Blender executable required for rendering')
  env=os.environ.copy();env['BINGO_WORKDIR']=str(work);env['BINGO_ADDON']=str(args.addon.resolve())
  for key in ('BLENDER_USER_CONFIG','BLENDER_USER_SCRIPTS','BLENDER_USER_EXTENSIONS','BLENDER_USER_DATAFILES','TEMP','TMP','XDG_CACHE_HOME'):
   folder=work/'isolated'/key;folder.mkdir(parents=True,exist_ok=True);env[key]=str(folder)
  command=[str(args.blender),'--background','--factory-startup','--disable-autoexec','--threads','2',
   '--python-exit-code','1','--python',str(HERE/'render_bingo_recipe.py')]
  start=time.perf_counter()
  with (work/'blender.log').open('w',encoding='utf-8') as log:
   process=subprocess.Popen(command,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   try:code=process.wait(timeout=180)
   except subprocess.TimeoutExpired:
    process.kill();process.wait(timeout=10);raise
  (work/'render-process.json').write_text(json.dumps({'pid':process.pid,'exit':code,'owned_closed':True,
   'seconds':time.perf_counter()-start},indent=2),encoding='utf-8')
  if code:raise RuntimeError('Isolated Blender render failed; inspect blender.log')
  from PIL import Image
  mask=Image.open(work/'layers/geometric-picture-window-x4.png').convert('RGBA').getchannel('A')
  band=Image.new('RGBA',(3960,360));outputs=[]
  for row in recipe['models']:
   index=row['cell'];actor=Image.open(work/f'actors/{index:02d}-{row["model"]}-HD360.png').convert('RGBA')
   bg=Image.open(work/f'layers/background-{index:02d}-x4.png').convert('RGBA');bg.putalpha(255)
   tile=Image.alpha_composite(bg,actor);tile.putalpha(mask)
   tile=Image.alpha_composite(tile,Image.open(work/f'layers/frame-overlay-{index:02d}-x4.png').convert('RGBA'))
   pixels=bytearray(tile.tobytes())
   for at in range(0,len(pixels),4):
    if not pixels[at+3]:pixels[at:at+3]=b'\0\0\0'
   tile=Image.frombytes('RGBA',(360,360),bytes(pixels));band.alpha_composite(tile,(index*360,0))
  target=work/recipe['source_native_key'];band.save(target)
  (work/'reproduction-result.json').write_text(json.dumps({'file':target.name,'sha256':digest(target),
   'dimensions':[3960,360],'reviewed_candidate_sha256':recipe['approved_band_sha256'],
   'GPU_byte_exact_across_drivers_claimed':False,'native_bitmap_upscaled_for_HD':False},indent=2),encoding='utf-8')
 print(json.dumps({'work':str(work),'prepared':True,'rendered':bool(args.render or args.render_prepared)}))
if __name__=='__main__':main()
