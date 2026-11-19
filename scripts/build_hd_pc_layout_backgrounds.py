"""Reproduce reviewed PC layout fragments from explicit genuine HD sources.

Native images are not inputs. Exact source hashes, target rectangles, optional
premultiplied reductions and the author's separate geometry are catalogue data.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_catalog import SUPPORTED,menu_recipes
from orre_randomizer.hd_images import load_texture
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _pixel_bytes
FAMILIES=('xd-pc-pal-front','xd-pc-controls-glyphs','pc-japanese-frame')
def pil(q):return Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q))
def reproduce(record,pack:Path):
    recipe=record['transform'];source=recipe['author_source'];name=source['source_file'];path=pack/name
    if Path(name).name!=name or hashlib.sha256(path.read_bytes()).hexdigest()!=source['source_sha256']:
        raise ValueError('The pinned PC image donor differs')
    family=recipe['family']
    if family=='pc-japanese-frame':
        with Image.open(path)as original:
            if list(original.size)!=source['source_dimensions']:raise ValueError('Unexpected source icon dimensions')
            donor=original.convert('RGBA')
        out=Image.new('RGBA',(1000,528))
        for step in source['transfers']:
            tile=donor.crop(tuple(step['source']));x,y,xx,yy=step['target'];size=(xx-x,yy-y)
            if tile.size!=size:tile=tile.convert('RGBa').resize(size,Image.Resampling.LANCZOS).convert('RGBA')
            if hashlib.sha256(tile.tobytes()).hexdigest()!=step['result_rgba_sha256']:
                raise ValueError('Transferred HD component differs')
            out.paste(tile,(x,y))
        return out
    donor=load_texture(path,expected_native_size=tuple(record['source_native_dimensions']));out=pil(donor.image)
    if family=='xd-pc-controls-glyphs':
        for box in source['exact_transparent_native_regions']:out.paste((0,0,0,0),tuple(v*4 for v in box))
    elif family=='xd-pc-pal-front':
        # A horizontal row function, measured only from the genuine HD margin.
        # Sorting the tiny rows gives the same per-channel median as the author
        # array tool, without a NumPy requirement for distributed reproduction.
        box=tuple(v*4 for v in source['source_profile_native_box']);region=out.crop(box);pixels=region.load()
        header=Image.new('RGBA',(292*4,25*4));rows=[]
        for y in range(region.height):
            colors=[pixels[x,y]for x in range(region.width)];median=[]
            for channel in range(4):
                values=sorted(p[channel]for p in colors);median.append((values[7]+values[8])//2)
            rows.extend([tuple(median)]*header.width)
        header.putdata(rows);out.paste(header,(0,0))
        payload=source['header_vector_svg'].encode('utf8')
        q,_=render_background(payload,expected_sha256=source['header_vector_svg_sha256'],native_size=(292,25),remove_ids=())
        out.alpha_composite(pil(q),(0,0))
    else:raise ValueError('Unsupported registered PC family')
    return out
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path);args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False);app=QGuiApplication.instance()or QGuiApplication([])
    rows={key:row for game in SUPPORTED for key,row in menu_recipes(game).items()if row['transform']['family']in FAMILIES};receipts=[]
    if len(rows)!=4:raise ValueError('Expected four reviewed PC layout sources')
    for row in rows.values():
        out=reproduce(row,args.pack);path=args.output_dir/Path(row['bundled_donor']).name;out.save(path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=row['source_sha256']:raise ValueError('Reproduced PC background differs: '+path.name)
        receipts.append({'file':path.name,'sha256':digest,'native_bitmap_used':False})
    (args.output_dir/'reproduction-receipt.json').write_text(json.dumps({'files':receipts},indent=2)+'\n',encoding='utf8')
    print('Four PC layout backgrounds exactly reproduced')
if __name__=='__main__':main()
