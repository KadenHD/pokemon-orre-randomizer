"""Portable private recipe driver. No network, source writes or addon install."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project-root','iso','xd-pack','colosseum-pack','addon','blender','controller-photo','gba-photo','work'):
        parser.add_argument('--'+name,required=True,type=Path)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-only',action='store_true',help='CPU extraction and donor pinning only; never starts Blender')
    modes.add_argument('--render-prepared',action='store_true',help='Use a previously prepared work folder')
    args=parser.parse_args()
    from PIL import __version__ as pillow_version
    assert pillow_version.split('.')[0]=='13','Use the project Pillow13 environment'
    root=args.project_root.resolve();work=args.work.resolve()
    assert (root/'orre_randomizer').is_dir()
    for path in (args.iso,args.blender,args.controller_photo,args.gba_photo):assert path.is_file(),path
    assert args.addon.is_dir() and (args.addon/'importer/importer.py').is_file()
    for path in (args.xd_pack,args.colosseum_pack):assert path.is_dir(),path
    if args.render_prepared:
        assert (work/'prepared-inputs.json').is_file(),'Missing verified preparation'
    else:
        work.mkdir(parents=False,exist_ok=False)
    env=os.environ.copy()
    env.update({'VS_WORKDIR':str(work),'VS_PROJECT_ROOT':str(root),'VS_SOURCE_ISO':str(args.iso.resolve()),
                'VS_XD_PACK':str(args.xd_pack.resolve()),'VS_COLO_PACK':str(args.colosseum_pack.resolve()),
                'VS_HSD_ADDON':str(args.addon.resolve()),'VS_CONTROLLER_PHOTO':str(args.controller_photo.resolve()),
                'VS_GBA_PHOTO':str(args.gba_photo.resolve()),'PYTHONDONTWRITEBYTECODE':'1',
                'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
    for key in ('BLENDER_USER_CONFIG','BLENDER_USER_SCRIPTS','BLENDER_USER_EXTENSIONS','BLENDER_USER_DATAFILES','TEMP','TMP','XDG_CACHE_HOME'):
        folder=work/'isolated'/key;folder.mkdir(parents=True,exist_ok=True);env[key]=str(folder)
    recipe=json.loads((HERE/'scene-recipe.json').read_text())
    controller_expected=next(row['hardware_photo']['source_sha256'] for row in recipe['scenes'] if row['scene']=='controller')
    gba_expected=next(row['hardware_photo']['source_sha256'] for row in recipe['scenes'] if row['scene']=='gba')
    for path,expected in ((args.controller_photo,controller_expected),(args.gba_photo,gba_expected)):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Changed photo source'
    receipts=[]

    def run(script,blender=False):
        if blender:
            command=[str(args.blender.resolve()),'--background','--factory-startup','--disable-autoexec',
                     '--threads','2','--python-exit-code','1','--python',str(HERE/script)]
        else:command=[sys.executable,str(HERE/script)]
        log_path=work/(Path(script).stem+'.log')
        with log_path.open('w',encoding='utf-8') as log:
            process=subprocess.Popen(command,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            print(json.dumps({'stage':script,'owned_pid':process.pid}),flush=True)
            try:code=process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=10);raise
        receipts.append({'stage':script,'exit':code,'owned_closed':True,'log':log_path.name})
        assert code==0,'Stage failed: '+script+'; read '+str(log_path)

    if not args.render_prepared:
        shutil.copyfile(HERE/'genuine-gba-reference.json',work/'genuine-gba-reference.json')
        run('extract_candidates.py');run('material_maps.py')
        actual=json.loads((work/'candidate-models.json').read_text())
        wanted={actor['model']:actor['native_model_sha256'] for scene in recipe['scenes'] for actor in scene['actors']}
        assert {row['member']:row['sha256'] for row in actual['models']}==wanted
        mapping=json.loads((work/'material-map.json').read_text())
        expected={row['native_key']:row['HD_donor'] for values in recipe['material_records'].values() for row in values if row['HD_donor']}
        for entries in mapping.values():
            for row in entries.values():
                donor=expected.get(row['native_key'])
                if donor:assert row['hd'] and row['hd']['sha256']==donor['sha256']
        (work/'prepared-inputs.json').write_text(json.dumps({'verified_model_count':len(wanted),'photos_pinned':True,'source_archive_sha256':actual['archive_sha256'],'no_Blender_started':True},indent=2),encoding='utf-8')
    if not args.prepare_only:
        for script in ('import_scene.py','render_scenes.py','render_authentic_controller.py','render_authentic_gba.py'):
            run(script,blender=True)
        for script in ('compose_authentic_controller.py','compose_authentic_gba.py'):run(script)
    (work/'reproduction-run.json').write_text(json.dumps({'stages':receipts,'prepare_only':args.prepare_only,'product_modified':False,'source_modified':False,'all_owned_children_closed':True},indent=2),encoding='utf-8')
    print(str(work),flush=True)

if __name__=='__main__':main()
