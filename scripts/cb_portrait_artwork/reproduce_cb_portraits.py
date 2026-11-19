"""Verify user-owned sources and reproduce five paired source-mesh portraits.

CPU preparation is the default. --render explicitly starts one isolated,
bounded Blender CLI process. No Dolphin, global input or network is used.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time,struct
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for option in ('project-root','colosseum-iso','xd-iso','colosseum-pack','xd-pack','addon','work'):
  parser.add_argument('--'+option,required=True,type=Path)
 parser.add_argument('--blender',type=Path);parser.add_argument('--render',action='store_true');parser.add_argument('--recipe',type=Path)
 args=parser.parse_args();sys.path.insert(0,str(args.project_root.resolve()));sys.dont_write_bytecode=True
 from orre_randomizer.engine.analyze_game import parse_fsys,decompress_lzss_python
 from orre_randomizer.engine.survey_assets import fst_inventory
 from orre_randomizer.hd_images import load_texture,resolve_texture
 from orre_randomizer.artwork import _png
 from PySide6.QtGui import QImage
 recipe_path=args.recipe or args.project_root/'orre_randomizer/assets/game/menu-atlases/cb-portrait-render-source.json'
 recipe=json.loads(recipe_path.read_text(encoding='utf-8'))
 for relative,expected in recipe['addon']['python_sources_sha256'].items():
  assert sha((args.addon/relative).read_bytes())==expected,('Addon changed',relative)
 if args.work.is_symlink():raise ValueError('Work cannot be a symbolic link')
 work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
 for name in ('models','HD-textures'):(work/name).mkdir()
 cache={};files=[]
 def record(path):files.append({'file':path.relative_to(work).as_posix(),'sha256':sha(path.read_bytes())})
 for model in recipe['models']:
  source=model['source'];game='colosseum' if source['game_id']=='GC6P01' else 'xd'
  source_iso=args.colosseum_iso if game=='colosseum' else args.xd_iso
  key=(game,source['archive'])
  if key not in cache:
   with source_iso.open('rb') as stream:
    boot=stream.read(0x440);assert boot[:6].decode('ascii')==source['game_id'] and boot[7]==0
    offset,length=struct.unpack_from('>II',boot,0x424);assert 0<length<=8*1024**2
    stream.seek(offset);entries=fst_inventory(stream.read(length))[0]
    entry=next(r for r in entries if r['path']==source['archive'])
    assert entry['disc_offset']==source['disc_offset'] and entry['size']==source['archive_bytes']
    stream.seek(entry['disc_offset']);raw=stream.read(entry['size'])
   assert sha(raw)==source['archive_sha256'];cache[key]=raw
  archive=cache[key];member=next(m for m in parse_fsys(archive)['members'] if m['name']==source['member'])
  assert member['identifier_raw']==source['member_identifier']
  payload=archive[member['offset']:member['offset']+member['stored_size']]
  raw=decompress_lzss_python(payload) if member['compression']=='LZSS' else payload
  assert sha(raw)==source['raw_sha256'] and len(raw)==source['raw_bytes']
  target=work/model['file'];target.write_bytes(raw);record(target)
  for material in model['material_map'].values():
   donor=material['HD']
   if donor is None:continue
   target=work/donor['render_file']
   if target.exists():assert sha(target.read_bytes())==donor['render_sha256'];continue
   pack=args.colosseum_pack if donor['pack']=='colosseum-2.00' else args.xd_pack
   pack=pack/'Textures' if (pack/'Textures').is_dir() else pack
   loaded=load_texture(resolve_texture(pack,material['native_key']),expected_native_size=tuple(material['native_dimensions']))
   assert loaded.metadata['sha256']==donor['sha256'] and loaded.metadata['source_scale']==4
   image=loaded.image.convertToFormat(QImage.Format.Format_RGBA8888)
   png=_png((image.width(),image.height()),bytes(image.constBits()));assert sha(png)==donor['render_sha256']
   target.write_bytes(png);record(target)
 (work/'model-materials.json').write_text(json.dumps({'models':recipe['models']},indent=2)+'\n',encoding='utf-8')
 (work/'guide-metadata.json').write_text(json.dumps(recipe['guide_metadata'],indent=2)+'\n',encoding='utf-8')
 record(work/'model-materials.json');record(work/'guide-metadata.json')
 receipt={'schema':1,'recipe_sha256':sha(recipe_path.read_bytes()),'models':5,
  'source_access':'rb only; selected original archives verified by exact SHA256',
  'Dolphin_started':False,'Blender_started':False,'files':files,'output_new_directory':True}
 (work/'prepared-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 if args.render:
  if args.blender is None or not args.blender.is_file():raise ValueError('An explicit Blender executable is required')
  env=os.environ.copy();env.update(CB_WORKDIR=str(work),CB_PROJECT_ROOT=str(args.project_root.resolve()),CB_ADDON=str(args.addon.resolve()),PYTHONDONTWRITEBYTECODE='1')
  for key in ('BLENDER_USER_CONFIG','BLENDER_USER_SCRIPTS','BLENDER_USER_EXTENSIONS','BLENDER_USER_DATAFILES','TEMP','TMP','XDG_CACHE_HOME'):
   path=work/'isolated'/key;path.mkdir(parents=True);env[key]=str(path)
  command=[str(args.blender),'--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','1','--python',str(HERE/'render_cb_recipe.py')]
  start=time.perf_counter()
  with (work/'blender.log').open('w',encoding='utf-8') as log:
   process=subprocess.Popen(command,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   print(json.dumps({'owned_pid':process.pid}),flush=True)
   try:code=process.wait(timeout=180)
   except subprocess.TimeoutExpired:
    process.kill();code=process.wait(timeout=10)
    raise RuntimeError('Owned renderer exceeded 180 seconds and was closed')
  receipt.update(Blender_started=True,owned_pid=process.pid,owned_closed=True,exit_code=code,seconds=time.perf_counter()-start)
  (work/'render-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
  if code:raise RuntimeError('Renderer failed; inspect its private blender.log')
  from PIL import Image
  renders=work/'renders';exports=work/'candidates';exports.mkdir()
  rendered=json.loads((renders/'paired-render-proof.json').read_text(encoding='utf-8'))
  exported=[]
  for model in rendered['renders']:
   for asset in model['files'].values():
    with Image.open(renders/asset['file']) as im:
     rgba=bytearray(im.convert('RGBA').tobytes())
     for index in range(0,len(rgba),4):
      if rgba[index+3]==0:rgba[index:index+3]=b'\0\0\0'
     png=_png(im.size,bytes(rgba))
    target=exports/asset['file'];target.write_bytes(png)
    exported.append({'file':target.relative_to(work).as_posix(),'sha256':sha(png),'bytes':len(png)})
  (work/'exported-pngs.json').write_text(json.dumps(exported,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'prepared':str(work),'models':5,'rendered':args.render}),flush=True)
if __name__=='__main__':main()
