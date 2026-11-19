"""Reproduce registered localized Bingo charts from genuine HD PNG/SVG sources.

The catalogue declares every translated component, caption-erasure rectangle,
native canvas and source digest. Neither ROMs nor native bitmaps are inputs.
The author's grid remains the verified 17-type Gen3 chart, with 289 symbols.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_images import load_texture
from orre_randomizer.hd_menu_catalog import SUPPORTED,menu_recipes
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _pixel_bytes,_render_vector_geometry

def px(box):return tuple(int(round(v*4))for v in box)
def pil(image):return Image.frombytes('RGBA',(image.width(),image.height()),_pixel_bytes(image))
def patch_opaque(image,clean,box):
    a=image.crop(px(box));b=clean.crop(px(box));mask=a.getchannel('A').point(lambda v:255 if v==255 else 0)
    a.paste(b,(0,0),mask);image.paste(a,px(box)[:2])
def vertical_slice(image,size,border=80):
    w,h=image.size;out=Image.new('RGBA',size)
    if w!=size[0]or min(h,size[1])<border*2:raise ValueError('Invalid fixed-edge relayout')
    out.paste(image.crop((0,0,w,border)),(0,0));out.paste(image.crop((0,h-border,w,h)),(0,size[1]-border))
    out.paste(image.crop((0,border,w,h-border)).resize((w,size[1]-border*2),Image.Resampling.LANCZOS),(0,border));return out

def reproduce(record,pack:Path,svg_root:Path):
    recipe=record['transform'];source=recipe['author_source'];name=source['source_file'];svg_name=source['source_SVG']
    if Path(name).name!=name or Path(svg_name).name!=svg_name:raise ValueError('Unsafe source basename')
    loaded=load_texture(pack/name,expected_native_size=(640,454))
    if loaded.metadata['sha256']!=source['source_sha256']:raise ValueError('Genuine HD chart differs')
    donor=pil(loaded.image);payload=(svg_root/svg_name).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=source['source_SVG_sha256']:raise ValueError('Author SVG differs')
    q,_=render_background(payload,expected_sha256=source['source_SVG_sha256'],native_size=(640,454),remove_ids=('g8',))
    clean=pil(q);base=donor.copy()
    for box in source['caption_background_rectangles']:patch_opaque(base,clean,box)
    symbols=[]
    for box in source['source_symbol_boxes_HD']:
        symbols.append(clean.crop(tuple(box)));base.paste((41,41,41,255),tuple(box))
    if recipe['language']=='ja':
        geom={'family':'bingo-type-chart','native_guide':{'role':'analytic native JP rectangle only'},'native_dimensions':[544,412],
          'layers':[{'color':[99,99,99,255],'operations':[{'shape':'rounded-rectangle','bounds':[1,1,543,411],'radius':10}],
                     'stroke':{'width':2,'color':[0,0,0,255]}}]}
        image=pil(_render_vector_geometry(geom)[0])
        for step in source['placements']:image.paste(base.crop(px(step['source_native'])),px(step['target_native'])[:2])
    else:
        image=base.copy()
        for step in source['placements']:
            if 'source_native'in step:
                a,b=step['source_native'],step['target_native'];size=((b[2]-b[0])*4,(b[3]-b[1])*4)
                strip=donor.crop(px([0,180,143,181])).resize(size,Image.Resampling.NEAREST);image.paste(strip,px(b)[:2])
                image.paste(vertical_slice(base.crop(px(a)),size),px(b)[:2])
            else:
                for symbol,box in zip(symbols,step['target_native'],strict=True):
                    image.paste(symbol.resize(((box[2]-box[0])*4,(box[3]-box[1])*4),Image.Resampling.LANCZOS),px(box)[:2])
    return image

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',required=True,type=Path,help='Pinned XD pack Textures directory')
    parser.add_argument('--svg-root',required=True,type=Path,help='Original author svg directory')
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=False);app=QGuiApplication.instance()or QGuiApplication([])
    records={key:row for game in SUPPORTED for key,row in menu_recipes(game).items()if row['transform']['family']=='bingo-type-chart'}
    if len(records)!=5:raise ValueError('The five reviewed chart recipes are required')
    results=[]
    for record in records.values():
        image=reproduce(record,args.pack,args.svg_root);path=args.output_dir/Path(record['bundled_donor']).name;image.save(path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=record['source_sha256']:raise ValueError('Reproduced chart differs: '+path.name)
        results.append({'file':path.name,'sha256':digest,'exact_registered_background':True})
    (args.output_dir/'reproduction-receipt.json').write_text(json.dumps({'records':results,'native_bitmaps_required':False},indent=2)+'\n',encoding='utf8')
    print('Five chart backgrounds match registered bytes')
if __name__=='__main__':main()
