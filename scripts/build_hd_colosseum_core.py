"""Portable reproduction of reviewed Colosseum core UI artwork, without ROMs.

Coordinates, SVG primitives and font contours are authenticated package data.
The only external input is the real Colosseum HD texture directory. No source
ROM, native PNG, save, emulator, private author folder or system font is needed.
"""
from pathlib import Path
import argparse, hashlib, json, os, sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtGui import QGuiApplication,QImage
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _render_vector_text,_pixel_bytes
from orre_randomizer.hd_menu_catalog import SUPPORTED,menu_recipes,menu_vectors,menu_artwork_metadata

def sha(data):return hashlib.sha256(data).hexdigest()
def safe(root,name):
    p=Path(name)
    if p.name!=name or p.is_absolute()or'..'in p.parts:raise ValueError('Unsafe author basename')
    path=root/p
    if path.is_symlink()or path.is_junction():raise ValueError('Author input is a link')
    return path
def vector(root,name,digest,size):
    payload=root[name].encode('utf8')if isinstance(root,dict)else safe(root,name).read_bytes()
    if sha(payload)!=digest:raise ValueError('Author vector source differs')
    q,_=render_background(payload,expected_sha256=digest,native_size=tuple(size),remove_ids=())
    return Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q))
def box(rect):return tuple(round(v*4)for v in rect)
def paste_cell(output,pack,record):
    path=safe(pack,record['file']);payload=path.read_bytes()
    if sha(payload)!=record['sha256']:raise ValueError('HD icon donor differs')
    with Image.open(path)as image:source=image.convert('RGBA')
    crop=source.crop(box(record['source_box_native']))
    if record.get('trim_HD_alpha_pixels'):
        bounds=crop.getchannel('A').getbbox()
        if list(bounds)!=record['trim_HD_alpha_pixels']:raise ValueError('HD alpha crop differs')
        crop=crop.crop(bounds)
    target=record['destination_box_native'];size=(round((target[2]-target[0])*4),round((target[3]-target[1])*4))
    if crop.size!=size:crop=crop.resize(size,Image.Resampling.LANCZOS)
    if record.get('compositing')=='source-over existing vector geometry':output.alpha_composite(crop,(round(target[0]*4),round(target[1]*4)))
    else:output.paste(crop,(round(target[0]*4),round(target[1]*4)))

def atlas(record,inputs,pack,vectors):
    output=vector(inputs,record['background_vector_file'],record['background_vector_sha256'],record['native_dimensions'])
    for source in record['HD_sources']:paste_cell(output,pack,source)
    if record.get('cell_vector_file'):
        cells=vector(inputs,record['cell_vector_file'],record['cell_vector_sha256'],record['native_dimensions'])
        output.alpha_composite(cells)
    recipe={'native_dimensions':record['native_dimensions'],'family':record['family'],'language':record['language'],
       'font_family':'latin_bold','labels':record['labels'],'native_guide':record['native_guide']}
    q,_=_render_vector_text(recipe,vectors)
    output.alpha_composite(Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q)))
    return output

def geometry(record,inputs,pack):
    output=vector(inputs,record['vector_source'],record['vector_sha256'],record['native_dimensions'])
    if record['family']=='pda-frame':
        output.paste((0,0,0,0),(0,0,77*4,193*4))
    for source in record.get('genuine_HD_cells',()):
        path=safe(pack,source['file']);payload=path.read_bytes()
        if sha(payload)!=source['sha256']:raise ValueError('HD frame donor differs')
        with Image.open(path)as image:donor=image.convert('RGBA')
        crop=donor.crop(box(source['source_native_box']));target=source['destination_native_box']
        if crop.size!=((target[2]-target[0])*4,(target[3]-target[1])*4):raise ValueError('Exact frame cell was resized')
        output.paste(crop,(target[0]*4,target[1]*4))
    return output

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack-textures',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=False)
    app=QGuiApplication.instance()or QGuiApplication([])
    references={(r['transform']['author_source']['reproduction_source'],
                 r['transform']['author_source']['reproduction_source_sha256'])
                for game in SUPPORTED for r in menu_recipes(game).values()
                if r['transform']['family']=='colosseum-combat-controls'}
    if len(references)!=1:raise ValueError('Reviewed Colosseum source package is unavailable')
    source=menu_artwork_metadata(*next(iter(references)))
    if source.get('kind')!='registered-colosseum-core-vector-source':raise ValueError('Unexpected vector source kind')
    records=source['atlas_records'];vectors=menu_vectors()
    outputs=[]
    for record in records:
        image=atlas(record,source['atlas_vectors'],args.pack_textures,vectors)
        path=safe(args.output_dir,record['file']);image.save(path)
        if sha(path.read_bytes())!=record['sha256']:raise ValueError('Atlas reproduction differs: '+path.name)
        outputs.append({'file':path.name,'sha256':record['sha256'],'exact':True})
    shapes=source['geometry_records']
    for record in shapes:
        image=geometry(record,source['geometry_vectors'],args.pack_textures)
        path=safe(args.output_dir,record['file'])
        if record['family']=='pc-frame':
            raw=image.tobytes()
            q=QImage(raw,image.width,image.height,image.width*4,QImage.Format.Format_RGBA8888).copy()
            if not q.save(str(path),'PNG'):raise ValueError('Cannot encode the reviewed vector frame')
        else:image.save(path)
        if sha(path.read_bytes())!=record['sha256']:raise ValueError('Geometry reproduction differs: '+path.name)
        outputs.append({'file':path.name,'sha256':record['sha256'],'exact':True})
    (args.output_dir/'reproduction-receipt.json').write_text(json.dumps({'outputs':outputs,
        'native_bitmaps_or_ROM_required':False,'Dolphin_started':False},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'outputs':len(outputs),'exact':True}))

if __name__=='__main__':main()
