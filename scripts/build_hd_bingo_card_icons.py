"""Reproduce the registered analytic sliced Bingo cards without native bitmaps.

The original atlas supplies measured primitive bounds and constant colours only.
The regular star, bevels, shadows and UV gaps are rendered from vector recipes.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,re,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_catalog import menu_recipes
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _pixel_bytes
TARGET='tex1_130x100_958ff16d27b739bd_cd06f6f72b296d39_9.png'
def star(cx,cy,r,ratio,angle):return[[cx+math.cos(math.radians(angle+36*i))*r*(ratio if i%2 else 1),cy+math.sin(math.radians(angle+36*i))*r*(ratio if i%2 else 1)]for i in range(10)]
def svg_recipe(source):
 def partial(x,y,right,height,radius):
  k=radius*.5522847498
  return(f'M{right},{y} H{x+radius} C{x+radius-k},{y} {x},{y+radius-k} {x},{y+radius} '
   f'V{y+height-radius} C{x},{y+height-radius+k} {x+radius-k},{y+height} {x+radius},{y+height} H{right} Z')
 defs=[];groups=[]
 for i,palette in enumerate(source['palettes']):
  main,light,side,dark,window=palette['main'],palette['top_bevel'],palette['side_bevel'],palette['bottom_bevel'],palette['window']
  defs.extend([f'<linearGradient id="body{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{light}"/><stop offset="0.13" stop-color="{side}"/><stop offset="0.85" stop-color="{side}"/><stop offset="1" stop-color="{dark}"/></linearGradient>',
   f'<linearGradient id="inside{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{main}"/><stop offset="0.88" stop-color="{main}"/><stop offset="1" stop-color="{dark}"/></linearGradient>',
   f'<linearGradient id="window{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#080008"/><stop offset="0.83" stop-color="#080008"/><stop offset="1" stop-color="{light}"/></linearGradient>',
   f'<clipPath id="tile{i}"><rect x="0" y="0" width="64" height="100"/></clipPath>'])
  shapes=[]
  for n in range(8,0,-1):shapes.append(f'<path d="{partial(13-n*.65,11-n*.65,64,80+n*1.3,18+n*.65)}" fill="#000000" opacity=".10"/>')
  shapes.extend([f'<path d="{partial(13,11,64,80,18)}" fill="url(#body{i})"/>',
   f'<path d="{partial(18,16,64,70,13)}" fill="url(#inside{i})"/>',
   f'<path d="{partial(29,26,64,30,15)}" fill="url(#window{i})"/>',
   f'<path d="{partial(30,28,64,26,13)}" fill="{window}"/>'])
  cx,cy,radius,ratio,angle=source['star_parameters']
  for n in range(7,0,-1):
   points=star(cx+.4,cy+3,radius+n*.45,ratio,angle)
   shapes.append('<polygon points="'+' '.join(f'{x:.8f},{y:.8f}'for x,y in points)+'" fill="#000000" opacity=".08"/>')
  shapes.append('<polygon points="'+' '.join(f'{x:.8f},{y:.8f}'for x,y in star(cx,cy,radius,ratio,angle))+'" fill="url(#star)" stroke="#d8d500" stroke-width=".65" stroke-linejoin="round"/>')
  groups.append(f'<g transform="translate({65*i},0)">'+''.join(shapes)+'</g>')
 return('<svg xmlns="http://www.w3.org/2000/svg" width="130" height="100" viewBox="0 0 130 100"><defs>'+
 '<linearGradient id="star" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffff26"/><stop offset=".4" stop-color="#ffff00"/><stop offset="1" stop-color="#f4f600"/></linearGradient>'+''.join(defs)+'</defs>'+''.join(groups)+'</svg>').encode('utf8')
def reproduce(output:Path):
    record=menu_recipes('GXXP01')[TARGET];source=record['transform']['author_source']
    if output.exists():raise ValueError('Use a new output path')
    for palette in source['palettes']:
        if any(not re.fullmatch(r'#[0-9a-f]{6}',v)for v in palette.values()):raise ValueError('Invalid vector colour')
    if len(source['star_parameters'])!=5 or any(not math.isfinite(v)for v in source['star_parameters']):
        raise ValueError('Invalid star parameters')
    payload=svg_recipe(source);digest=hashlib.sha256(payload).hexdigest()
    if digest!=source['SVG_recipe_sha256']:raise ValueError('Declared vector recipe differs')
    image,_=render_background(payload,expected_sha256=digest,native_size=(130,100),remove_ids=())
    out=Image.frombytes('RGBA',(image.width(),image.height()),_pixel_bytes(image))
    for box in source['sliced_UV_clear_rectangles']:out.paste((0,0,0,0),tuple(v*4 for v in box))
    output.parent.mkdir(parents=True,exist_ok=True);out.save(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    if digest!=record['source_sha256']:raise ValueError('Reproduced vector artwork differs')
    return{'sha256':digest,'native_bitmap_used':False,'exact_registered_background':True}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();app=QGuiApplication.instance()or QGuiApplication([])
    print(json.dumps(reproduce(args.output),indent=2))
if __name__=='__main__':main()
