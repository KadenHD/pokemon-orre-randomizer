"""Private Japanese link/VS atlas authoring from pinned HD art and vectors.

No native bitmap is sampled for the artwork. Original PNGs are optional
diagnostic guides only. The CB portrait input is independently supplied.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QLinearGradient,QColor,QTransform,QPainterPathStroker
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _render_vector_text,_pixel_bytes,_word_path
HERE=Path(__file__).resolve().parent
PORTRAIT_COMPOSITE_SHA256='7ad759de13ceaa7604ccee14de135da78def4dcd84ba08b1ce72d6566deffcf3'

def sha(data):return hashlib.sha256(data).hexdigest()
def qpil(image):return Image.frombytes('RGBA',(image.width(),image.height()),_pixel_bytes(image))
def safe(root,name):
 path=Path(name)
 if path.is_absolute() or path.name!=name or '..' in path.parts:raise ValueError('Unsafe source basename')
 result=root/path
 if result.is_symlink() or result.is_junction():raise ValueError('Linked source refused')
 return result
def svg(root,record):
 payload=safe(root,record['file']).read_bytes()
 if sha(payload)!=record['sha256']:raise ValueError('Vector source hash differs')
 result,_=render_background(payload,expected_sha256=record['sha256'],native_size=tuple(record['native_size']),remove_ids=())
 return qpil(result)
def source(pack,record):
 path=safe(pack,record['file']);payload=path.read_bytes()
 if sha(payload)!=record['sha256']:raise ValueError('Real HD donor hash differs')
 with Image.open(path)as im:result=im.convert('RGBA')
 if list(result.size)!=record['HD_dimensions']:raise ValueError('Real HD donor dimensions differ')
 return result
def b4(box):return tuple(round(v*4)for v in box)
def fade_approved_portrait(image):
 if sha((HERE/'cb_portrait_composite.py').read_bytes())!=PORTRAIT_COMPOSITE_SHA256:
  raise ValueError('Shared approved portrait compositing helper differs')
 from cb_portrait_composite import fade_portrait_rgba
 return fade_portrait_rgba(image,native_rows=14,source_scale=4)
def paste_donor(image,donor,record):
 crop=donor.crop(b4(record['source_box_native']))
 if record.get('trim_HD_alpha_pixels'):
  actual=crop.getchannel('A').getbbox()
  if list(actual)!=record['trim_HD_alpha_pixels']:raise ValueError('HD alpha footprint differs')
  crop=crop.crop(actual)
 box=record['target_box_native'];size=((box[2]-box[0])*4,(box[3]-box[1])*4)
 if crop.size!=size:crop=crop.resize(size,Image.Resampling.LANCZOS)
 image.alpha_composite(crop,(box[0]*4,box[1]*4))
def raised_text(dimensions,labels,vectors):
 """True outline paths with a declared silver bevel; no native glyph pixels."""
 output=QImage(dimensions[0]*4,dimensions[1]*4,QImage.Format.Format_RGBA8888);output.fill(Qt.GlobalColor.transparent)
 painter=QPainter(output);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
 try:
  for label in labels:
   x,y,z,t=label['bounds'];word=_word_path(label['text'],label.get('font_family','japanese'),vectors);bounds=word.boundingRect()
   if bounds.isEmpty() or not(0<=x<z<=dimensions[0] and 0<=y<t<=dimensions[1]):raise ValueError('Raised label has invalid UV bounds')
   tr=QTransform();tr.translate((x+1.1)*4,(y+1.1)*4);tr.scale((z-x-2.2)*4/bounds.width(),(t-y-2.2)*4/bounds.height());tr.translate(-bounds.left(),-bounds.top());path=tr.map(word)
   back=QTransform().translate(2.6,3.5).map(path);painter.fillPath(back,QColor('#1c1c1c'))
   stroke=QPainterPathStroker();stroke.setWidth(2.8);painter.fillPath(stroke.createStroke(path),QColor('#343434'))
   high=QTransform().translate(-1.3,-1.4).map(path);painter.fillPath(high,QColor('#ededed'))
   grad=QLinearGradient(0,y*4,0,t*4);grad.setColorAt(0,QColor('#d4d4d4'));grad.setColorAt(.4,QColor('#a1a1a1'));grad.setColorAt(.57,QColor('#656565'));grad.setColorAt(1,QColor('#8b8b8b'))
   painter.fillPath(path,grad)
 finally:painter.end()
 return qpil(output)
def compose(record,inputs,pack,vectors,portraits=None):
 w,h=record['native_dimensions'];image=Image.new('RGBA',(w*4,h*4))
 if record.get('background_donor'):
  image=source(pack,record['background_donor'])
 for box in record.get('clear_rectangles_native',[]):image.paste((0,0,0,0),b4(box))
 for layer in record.get('vector_layers',[]):
  image.alpha_composite(svg(inputs,layer),(layer.get('x',0)*4,layer.get('y',0)*4))
 for cell in record.get('genuine_HD_cells',[]):paste_donor(image,source(pack,cell),cell)
 if record.get('labels'):
  if record.get('label_style')=='silver-bevel-vector':layer=raised_text((w,h),record['labels'],vectors)
  else:
   result,_=_render_vector_text(dict(native_dimensions=[w,h],font_family=record.get('font_family','japanese'),family=record['family'],language='ja',labels=record['labels'],native_guide=record['native_guide']),vectors);layer=qpil(result)
  image.alpha_composite(layer)
 used=[]
 if record.get('portrait_slots'):
  if portraits is not None:
   expected={slot['identity']for slot in record['portrait_slots']}
   if (not isinstance(portraits.get('portraits'),dict)
       or set(portraits['portraits'])!=expected):
    raise ValueError('Exactly five reviewed model portrait records are required')
   for slot in record['portrait_slots']:
    item=portraits['portraits'][slot['identity']];path=safe(Path(portraits['directory']),item['file']);payload=path.read_bytes()
    if sha(payload)!=item['sha256']:raise ValueError('Portrait render hash differs')
    with Image.open(path)as im:portrait=im.convert('RGBA')
    if list(portrait.size)!=slot['HD_dimensions']:raise ValueError('Portrait render canvas differs')
    # Root approved one common alpha-only envelope for both PAL and JP. The
    # input hash above always refers to the immutable, unfaded render master.
    portrait=fade_approved_portrait(portrait)
    image.alpha_composite(portrait,(slot['target_box_native'][0]*4,slot['target_box_native'][1]*4))
    used.append(dict(identity=slot['identity'],sha256=item['sha256'],file=item['file'],
       source_proof=item.get('source_proof',portraits.get('source_proof'))))
 return image,used
def build(inputs,pack,vectors_path,output,portraits=None):
 output.mkdir(parents=True,exist_ok=False)
 layout=json.loads(safe(inputs,'jp-layout.json').read_text(encoding='utf8'));vraw=vectors_path.read_bytes()
 if sha(vraw)!=layout['vectors_sha256']:raise ValueError('Vector contours differ')
 vectors=json.loads(vraw);records=[]
 for r in layout['records']:
  image,used=compose(r,inputs,pack,vectors,portraits);name=r['target'];image.save(output/name)
  records.append(dict(**r,file=name,sha256=sha((output/name).read_bytes()),RGBA_sha256=sha(image.tobytes()),
    complete=not r.get('portrait_slots') or len(used)==5,portrait_render_inputs=used,
    portrait_compositing=(dict(helper_file='cb_portrait_composite.py',helper_sha256=PORTRAIT_COMPOSITE_SHA256,
       native_rows=14,source_scale=4,operation='alpha only; applied once before any scaling',
       envelope='.6*(1-t)+.4*(1-3*t*t+2*t*t*t), t=0..1 inclusive over last56 HD rows',
       RGB_unchanged_in_helper=True,master_files_unchanged=True) if used else None),
    native_bitmap_used_for_HD_art=False,Dolphin_started=False))
 report=dict(schema=1,scope='six Colosseum Japanese VS/link resource identities',game_ids=['GC6J01'],
  complete_atlases=sum(r['complete']for r in records),UI_layers=len(records),records=records,
  vectors_sha256=layout['vectors_sha256'],layout_sha256=sha(safe(inputs,'jp-layout.json').read_bytes()))
 (output/'jp-link-receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return report
def review(report,output,native):
 for r in report['records']:
  source_image=Image.open(native/r['target']).convert('RGBA');hd=Image.open(output/r['file']).convert('RGBA')
  scale=2 if source_image.width<450 else 1
  left=source_image.resize((source_image.width*scale,source_image.height*scale),Image.Resampling.NEAREST)
  right=hd.resize(left.size,Image.Resampling.LANCZOS)
  canvas=Image.new('RGB',(left.width*2+20,left.height+32),'#686868');d=ImageDraw.Draw(canvas)
  d.text((8,7),'Original - diagnostic source',fill='white');d.text((left.width+28,7),'HD' if r['complete'] else 'HD UI - portraits pending',fill='white')
  canvas.paste(left,(0,30),left);canvas.paste(right,(left.width+20,30),right)
  canvas.save(output/(Path(r['file']).stem+'-review.png'))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--inputs',type=Path,required=True);p.add_argument('--pack-textures',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--native-diagnostics',type=Path);p.add_argument('--portraits',type=Path)
 args=p.parse_args();app=QGuiApplication.instance()or QGuiApplication([])
 portraits=None
 if args.portraits:
  portraits=json.loads(args.portraits.read_text(encoding='utf8'));portraits['directory']=str(args.portraits.parent.resolve())
 receipt=build(args.inputs,args.pack_textures,args.vectors,args.output,portraits)
 if args.native_diagnostics:review(receipt,args.output,args.native_diagnostics)
 print(json.dumps(dict(UI_layers=receipt['UI_layers'],complete_atlases=receipt['complete_atlases'])))
if __name__=='__main__':main()
