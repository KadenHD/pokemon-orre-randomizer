"""Analytic x4 Bingo frame overlays. Does not reconstruct unknown scene plates."""
from pathlib import Path
import hashlib,itertools,json,math,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
HERE=Path(__file__).parent/'model-frames';HERE.mkdir(exist_ok=False)
from PIL import Image
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QColor,QImage,QLinearGradient,QPainter,QPainterPath,QPainterPathStroker,QTransform

source=ROOT/'build/hd-menu-completion/menus/native/tex1_990x90_aba46b368231bae1_dd9c673d5477f338_9.png'
original=Image.open(source).convert('RGBA')
assert hashlib.sha256(original.tobytes()).hexdigest()=='7e7c7e3ba5785e849add3042c806af2895bb1956fbe8016c368d3b795db24104'
reference=original.crop((0,0,90,90)).getchannel('A')
opaque=[v>=128 for v in reference.get_flattened_data()]
def path(box,radius):
    result=QPainterPath();result.addRoundedRect(QRectF(box[0],box[1],box[2]-box[0],box[3]-box[1]),radius,radius)
    return result
def rgba(image):
    image=image.convertToFormat(QImage.Format.Format_RGBA8888)
    return bytes(image.constBits())[:image.sizeInBytes()]
def fit_score(box,radius):
    output=QImage(360,360,QImage.Format.Format_RGBA8888);output.fill(0)
    painter=QPainter(output);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillPath(QTransform.fromScale(4,4).map(path(box,radius)),QColor('white'));painter.end()
    alpha=Image.frombytes('RGBA',(360,360),rgba(output)).getchannel('A').resize((90,90),Image.Resampling.BOX)
    mask=[v>=128 for v in alpha.get_flattened_data()]
    union=sum(a or b for a,b in zip(opaque,mask));common=sum(a and b for a,b in zip(opaque,mask))
    return common/union
fits=[]
for left,top,right,bottom,radius in itertools.product((2.5,3),(2.5,3),(79.5,80),(78.5,79),(5,5.5,6,6.5,7)):
    box=(left,top,right,bottom);fits.append((fit_score(box,radius),box,radius))
score,box,radius=max(fits,key=lambda row:row[0])

# Polygon/curves trace the visible generic viewport, never a Pokemon silhouette.
window=QPainterPath();window.moveTo(8,20);window.lineTo(53,20);window.lineTo(65,8);window.lineTo(73,8)
window.quadTo(76,8,76,11);window.lineTo(76,72);window.quadTo(76,75,73,75)
window.lineTo(11,75);window.quadTo(8,75,8,72);window.closeSubpath()
mask=QImage(360,360,QImage.Format.Format_RGBA8888);mask.fill(0)
painter=QPainter(mask);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
painter.fillPath(QTransform.fromScale(4,4).map(window),QColor('white'));painter.end()
assert mask.save(str(HERE/'geometric-picture-window-x4.png'),'PNG')

def shadow_alpha(x,y):
    # Continuous signed-distance rounded rectangle, 3px penumbra at native scale.
    l,t,r,b=box;l+=4;r+=4;t+=5;b+=5
    cx,cy=(l+r)/2,(t+b)/2;hx,hy=(r-l)/2-radius,(b-t)/2-radius
    qx,qy=abs(x-cx)-hx,abs(y-cy)-hy
    distance=math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-radius
    return round(109*min(1,max(0,(1.5-distance)/3)))
shadow=bytearray(360*360*4)
for y in range(360):
    for x in range(360):shadow[(y*360+x)*4+3]=shadow_alpha((x+.5)/4,(y+.5)/4)
outer=path(box,radius);records=[]
for index in range(11):
    cell=original.crop((index*90,0,(index+1)*90,90))
    primary=cell.getpixel((20,8))[:3];light=cell.getpixel((5,40))[:3];dark=cell.getpixel((20,76))[:3]
    output=QImage(bytes(shadow),360,360,1440,QImage.Format.Format_RGBA8888).copy()
    painter=QPainter(output);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient=QLinearGradient(12,12,12,316)
    gradient.setColorAt(0,QColor(*[min(255,round(c*.5+127))for c in light]))
    gradient.setColorAt(.035,QColor(*light));gradient.setColorAt(.14,QColor(*primary))
    gradient.setColorAt(.90,QColor(*primary));gradient.setColorAt(1,QColor(*dark))
    painter.fillPath(QTransform.fromScale(4,4).map(outer),gradient)
    stroke=QPainterPathStroker();stroke.setWidth(1)
    painter.fillPath(QTransform.fromScale(4,4).map(stroke.createStroke(window)),QColor(0,0,0,180))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.fillPath(QTransform.fromScale(4,4).map(window),QColor('white'));painter.end()
    filename=f'frame-overlay-{index:02d}-x4.png';target=HERE/filename
    assert output.save(str(target),'PNG')
    records.append({'index':index,'file':filename,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
      'native_cell_crop':[index*90,0,(index+1)*90,90],'actor_canvas':[360,360],
      'actor_translation':[0,0],'actor_scale':1,'palette':{'primary':primary,'light':light,'dark':dark},
      'original_alpha_bbox':cell.getchannel('A').getbbox(),
      'scene_background':'unresolved; transparent interior is NOT a finished background plate'})
report={'kind':'authored-analytic-bingo-frame-overlays','review_only':True,'runtime_validated':False,
 'source_native_member_sha256':'54d41c7dcdf2d5dd96f695dde58f7c26765909e17082ca19f2b71909025b55f5',
 'source_native_RGBA_sha256':hashlib.sha256(original.tobytes()).hexdigest(),
 'geometry':{'outer_rounded_rectangle':box,'radius':radius,'outer_alpha_threshold128_IoU_diagnostic':score,
  'shadow':'continuous rounded-rectangle SDF, offset4/5native, 3native penumbra, maxalpha109',
  'window':'M8,20 L53,20 L65,8 L73,8 Q76,8 76,11 L76,72 Q76,75 73,75 L11,75 Q8,75 8,72 Z'},
 'native_bitmap_resampled':False,'native_Pokemon_mask_used':False,'Dolphin_started':False,
 'composition_order':['genuine-HD-scene-plate (not yet identified)','true-HD-rendered actor clipped by geometric window','frame overlay'],
 'window_mask_sha256':hashlib.sha256((HERE/'geometric-picture-window-x4.png').read_bytes()).hexdigest(),
 'records':records,'limits':['Only frame/viewport geometry is reconstructed here; no original camera/arena claim.',
  'Frame clipping is geometric and must be reviewed with the actual aligned actors.',
  'No replacement for an unknown scene background is silently supplied.']}
with (HERE/'frame-manifest.json').open('x',encoding='utf-8')as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps({'frames':11,'unique_frame_hashes':len({r['sha256']for r in records}),
 'outer_alpha_IoU_diagnostic':score,'geometry':box,'radius':radius,'scene_backgrounds_resolved':0}))
