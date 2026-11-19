"""Declared procedural Bingo scene reconstructions, never native bitmap upscales.

The game supplies palette/composition references only. No arena identity or
original camera is claimed. Scene pixels are evaluated at their actual HD size.
"""
from pathlib import Path
import hashlib, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
OUT = HERE / 'ambiences-v3'
OUT.mkdir(exist_ok=False)
SIZE = 360
S = SIZE / 90
SOURCE_KEY = 'tex1_990x90_aba46b368231bae1_dd9c673d5477f338_9.png'
SOURCE = ROOT / 'build/hd-menu-completion/menus/native' / SOURCE_KEY
WINDOW = HERE / 'model-frames/geometric-picture-window-x4.png'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def noise(x, y, seed):
    value = np.zeros_like(x)
    # Continuous value noise evaluated at every final pixel. These are hashed
    # lattice values, not a lower-resolution bitmap enlarged by a filter.
    for scale, amplitude in ((23,.51),(11,.28),(5,.14),(2.4,.07)):
        xx,yy=x/scale,y/scale
        ix,iy=np.floor(xx),np.floor(yy)
        fx,fy=xx-ix,yy-iy
        fx=fx*fx*(3-2*fx);fy=fy*fy*(3-2*fy)
        def vertex(a,b):
            v=np.sin(a*127.1+b*311.7+seed*29.3)*43758.5453
            return (v-np.floor(v))*2-1
        top=vertex(ix,iy)*(1-fx)+vertex(ix+1,iy)*fx
        bottom=vertex(ix,iy+1)*(1-fx)+vertex(ix+1,iy+1)*fx
        value += (top*(1-fy)+bottom*fy)*amplitude
    return value

def color_field(a, b, amount):
    a = np.array(a)[None, None, :]
    b = np.array(b)[None, None, :]
    return a + (b-a) * np.clip(amount[:, :, None], 0, 1)

def image_from(rgb):
    return Image.fromarray(np.uint8(np.clip(rgb, 0, 255)), 'RGB').convert('RGBA')

def poly(draw, points, fill):
    draw.polygon([(round(x*S), round(y*S)) for x,y in points], fill=fill)

def scene(kind, seed):
    y,x = np.mgrid[:SIZE,:SIZE].astype(np.float64)
    x = (x + .5) / S
    y = (y + .5) / S
    n = noise(x, y, seed)
    if kind in ('flame','pale-ember'):
        # Fire/ember-lit rock: analytic tongues rather than enlarged flame pixels.
        warp=noise(x*.7,y*.45,seed+17)*13
        heat=np.clip(.36+noise(x+warp,y*.52,seed+2)*1.15+(y-15)/130*.20,0,1)
        rgb = color_field((35,13,3),(232,103,5),heat)
        bright = np.maximum(0,heat-.48)[:, :, None] * np.array((140,170,60))
        rgb += bright + n[:, :, None] * np.array((22,8,2))
        if kind=='pale-ember':
            heat=np.clip(.45+np.abs(x-45)/45*.48+noise(x*.65,y*.18,seed)*.45,0,1)
            rgb=color_field((45,27,12),(248,229,160),heat)
            rgb+=np.maximum(0,heat-.68)[:, :, None]*np.array((80,80,120))
            rgb+=n[:, :, None]*np.array((26,16,3))
        image = image_from(rgb)
    elif kind == 'dark-blue':
        amount = .28 + .35*np.sin(y*.10) + n*.34
        image = image_from(color_field((4,15,48),(10,73,119),amount))
    elif kind == 'shore':
        rgb = color_field((33,64,28),(64,93,20),.5+n*.3)
        bank = y > (39 + np.sin(x*.05)*3)
        water = color_field((4,64,77),(17,114,131),.5 + n*.15 + np.sin(y*.25)*.12)
        rgb[bank] = water[bank]
        image = image_from(rgb)
        draw = ImageDraw.Draw(image)
        poly(draw,[(0,29),(17,27),(34,33),(54,31),(70,17),(90,20),(90,39),(60,44),(19,42),(0,41)],(60,57,30,255))
        poly(draw,[(0,40),(23,38),(52,41),(90,34),(90,42),(50,47),(0,45)],(24,104,36,255))
        for yy in (50,58,67,76):
            draw.line((0,yy*S,SIZE,(yy-1)*S),fill=(39,117,118,120),width=2)
    elif kind == 'forest':
        rgb = color_field((28,50,17),(111,116,49),.47+n*.25)
        rgb += np.maximum(0,np.sin((x+y)*.05))[:, :, None] * np.array((12,15,1))
        light=np.maximum(0,1-np.sqrt(((x-14)/36)**2+((y-55)/50)**2))
        rgb+=light[:, :, None]*np.array((85,76,44))
        image = image_from(rgb)
        draw = ImageDraw.Draw(image)
        # Trunk/branch composition matches the brown/green source context,
        # without attributing this hand-authored plate to a specific game stage.
        shift = ((seed*7)%13)-6
        poly(draw,[(52+shift,0),(69+shift,0),(63+shift,90),(41+shift,90)],(91,71,40,255))
        poly(draw,[(53+shift,25),(24,6),(18,10),(49+shift,39)],(78,61,35,255))
        poly(draw,[(61+shift,41),(87,18),(90,23),(60+shift,52)],(80,63,34,255))
        for i in range(8):
            xx = 45+shift+i*2.2
            draw.line((xx*S,0,(xx-6)*S,SIZE),fill=(54+i*3,46+i*2,25,190),width=2)
        for i in range(17):
            xx = (i*29+seed*7)%96-7
            yy = (i*13+seed*5)%30-5
            draw.ellipse(((xx-9)*S,(yy-7)*S,(xx+10)*S,(yy+7)*S),fill=(24+i%4*7,70+i%5*7,24,255))
        poly(draw,[(0,76),(30,70),(60,77),(90,69),(90,90),(0,90)],(38,63,27,255))
    elif kind == 'blue-rock':
        rgb = color_field((5,17,37),(46,66,86),.45+n*.25)
        image = image_from(rgb)
        draw = ImageDraw.Draw(image)
        poly(draw,[(48,0),(76,0),(82,40),(64,57),(51,29)],(89,76,46,255))
        poly(draw,[(64,0),(72,0),(74,40),(64,57)],(49,45,35,255))
        poly(draw,[(0,68),(26,58),(45,71),(65,60),(90,64),(90,90),(0,90)],(16,31,48,255))
        for i in range(7):
            yy = 29+i*8
            draw.line((51*S,yy*S,77*S,(yy-4)*S),fill=(40,38,31,200),width=2)
    elif kind == 'purple-angles':
        rgb = color_field((40,17,55),(155,46,171),.35+n*.28)
        image = image_from(rgb)
        draw = ImageDraw.Draw(image)
        poly(draw,[(40,0),(65,0),(90,31),(90,56),(54,25)],(110,31,147,255))
        poly(draw,[(65,0),(86,0),(90,11),(90,31)],(180,55,192,255))
        poly(draw,[(18,57),(43,36),(69,72),(90,50),(90,90),(0,90)],(29,23,42,255))
        poly(draw,[(27,51),(43,36),(61,59),(49,54)],(72,48,91,255))
    else:
        raise ValueError(kind)
    # The independent vector aperture came from measured frame geometry. It is
    # not an enlarged native bitmap mask or an actor silhouette.
    image=image.filter(ImageFilter.GaussianBlur(.6))
    with Image.open(WINDOW) as aperture:
        mask = aperture.convert('RGBA').getchannel('A')
    image.putalpha(mask)
    return image

names = ['Dragonair','Nidorino','Lotad','Charmander','Pikachu','Sudowoodo','Bonsly','Magikarp','Seadra','Scyther','Houndoom']
ids = [148,33,270,4,25,185,438,129,117,123,229]
kinds = ['flame','dark-blue','shore','flame','forest','pale-ember','forest','blue-rock','blue-rock','forest','purple-angles']
with Image.open(SOURCE) as original:
    source = original.convert('RGBA')
assert source.size == (990,90)
assert hashlib.sha256(source.tobytes()).hexdigest() == '7e7c7e3ba5785e849add3042c806af2895bb1956fbe8016c368d3b795db24104'
records = []
board = Image.new('RGB',(1230,920),'#aaa')
draw = ImageDraw.Draw(board)
for index,(name,species,kind) in enumerate(zip(names,ids,kinds)):
    image = scene(kind,index+31)
    filename = f'background-{index:02d}-x4.png'
    image.save(OUT/filename)
    records.append({'index':index,'species_national':species,'name':name,'ambience':kind,
      'file':filename,'sha256':digest(OUT/filename),'size':[360,360],
      'composition':'procedural reconstruction from native colour/context guide; no identified original terrain/camera',
      'pack_donor':None,'native_bitmap_resampled':False,'actor_pixels_present':False,
      'seed':index+31,'actor_placement':'same 360-square canvas; no additional translation or scale'})
    x=(index%3)*410;y=(index//3)*230
    draw.text((x+5,y+5),f'{index} {name} - {kind}',fill='black')
    native=source.crop((index*90,0,(index+1)*90,90)).resize((180,180),Image.Resampling.NEAREST)
    board.paste(native,(x+5,y+35),native)
    preview=image.resize((180,180),Image.Resampling.LANCZOS)
    # Below the native guide, show the plate without actors at readable size.
    board.paste(preview,(x+205,y+35),preview)
    draw.text((x+5,y+20),'Native guide',fill='black')
    draw.text((x+205,y+20),'Reconstructed plate',fill='black')
board.save(OUT/'ambiences-source-guide-and-drafts.png')
receipt={'kind':'declared-procedural-bingo-ambience-reconstruction','version':1,
  'source_key':SOURCE_KEY,'source_png_sha256':digest(SOURCE),'vector_window_sha256':digest(WINDOW),
  'native_bitmap_resampled_for_art':False,'source_native_role':'colours and broad composition only',
  'original_arena_or_camera_identified':False,'runtime_validated':False,
  'geometry':'same independent frame aperture as model-frames; do not include another frame in this layer',
  'records':records}
(OUT/'ambiences-manifest.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'files':len(records),'kinds':sorted(set(kinds)),'declared_reconstruction':True,'Dolphin_started':False}))
