"""Reproduce the PC bar's genuine-HD caption-free source for PAL locales."""
from pathlib import Path
import argparse,hashlib,json,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_images import load_texture
from orre_randomizer.hd_menu_catalog import menu_recipes
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _pixel_bytes
def pil(q):return Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q))
def reproduce(pack:Path,svg_root:Path,output:Path):
    rows=[r for r in menu_recipes('GXXP01').values()if r['transform']['family']=='xd-pc-hp']
    if len(rows)!=5 or len({r['source_sha256']for r in rows})!=1:raise ValueError('Expected five reviewed PAL caption layouts')
    row=rows[0];source=row['transform']['author_source']
    if output.exists():raise ValueError('Use a new output path')
    if any(Path(source[k]).name!=source[k]for k in('source_file','source_SVG')):raise ValueError('Unsafe donor basename')
    loaded=load_texture(pack/source['source_file'],expected_native_size=(258,20))
    if loaded.metadata['sha256']!=source['source_sha256']:raise ValueError('Pinned genuine HD donor changed')
    payload=(svg_root/source['source_SVG']).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=source['source_SVG_sha256']:raise ValueError('Pinned author SVG changed')
    q,_=render_background(payload,expected_sha256=source['source_SVG_sha256'],native_size=(258,20),remove_ids=('g8',))
    clean=pil(q);image=pil(loaded.image)
    for box in source['caption_background_rectangles']:
        image.paste(clean.crop(tuple(v*4 for v in box)),(box[0]*4,box[1]*4))
    output.parent.mkdir(parents=True,exist_ok=True);image.save(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    if digest!=row['source_sha256']:raise ValueError('Reproduced PC bar differs')
    return{'sha256':digest,'native_bitmap_used':False,'exact_registered_background':True}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',required=True,type=Path);parser.add_argument('--svg-root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    app=QGuiApplication.instance()or QGuiApplication([]);print(json.dumps(reproduce(args.pack,args.svg_root,args.output),indent=2))
if __name__=='__main__':main()
