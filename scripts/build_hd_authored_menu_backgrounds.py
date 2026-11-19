"""Reproduce self-contained vector menu backgrounds from registered recipes.

No source ROM, bitmap, save or font is needed. The strict SVG renderer rejects
embedded images, active text, external references, scripts and raster filters.
Caption paths are added separately by render_hd_menu_atlases.py.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, __version__ as pillow_version
from PySide6.QtCore import qVersion
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_catalog import SUPPORTED,menu_recipes
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _pixel_bytes

def reproduce(record,output:Path):
    source=record['transform']['author_source'];payload=source['vector_svg'].encode('utf8')
    if output.exists():raise ValueError('Use a new output path')
    if hashlib.sha256(payload).hexdigest()!=source['vector_svg_sha256']:raise ValueError('Vector recipe changed')
    image,_=render_background(payload,expected_sha256=source['vector_svg_sha256'],
                             native_size=tuple(record['source_native_dimensions']),remove_ids=())
    out=Image.frombytes('RGBA',(image.width(),image.height()),_pixel_bytes(image));out.save(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    if digest!=record['source_sha256']:raise ValueError('Reproduced vector PNG differs')
    return{'file':output.name,'sha256':digest,'native_bitmap_used':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family',required=True)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=False);app=QGuiApplication.instance()or QGuiApplication([])
    rows={key:row for game in SUPPORTED for key,row in menu_recipes(game).items()
          if row['transform']['family']==args.family}
    if not rows:raise ValueError('No registered vector family')
    receipts={}
    for row in rows.values():
        name=Path(row['bundled_donor']).name
        if name in receipts:
            if row['source_sha256']!=receipts[name]['sha256']:raise ValueError('Conflicting registered background')
        else:receipts[name]=reproduce(row,args.output_dir/name)
    report={'files':list(receipts.values()),'identity_count':len(rows),'pillow':pillow_version,'qt':qVersion()}
    (args.output_dir/'reproduction-receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'identities':len(rows),'exact_unique_PNGs':len(receipts)}))
if __name__=='__main__':main()
