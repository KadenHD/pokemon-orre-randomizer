"""Private four-atlas Japanese UI composition from genuine HD pack art."""
from pathlib import Path
import argparse,hashlib,json,os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw,ImageChops
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_atlases import _render_vector_text,_pixel_bytes
from orre_randomizer.hd_menu_svg import render_background
HERE=Path(__file__).resolve().parent
def sha(payload):return hashlib.sha256(payload).hexdigest()
def b4(box):return tuple(round(v*4)for v in box)
def safe(root,name):
 if Path(name).name!=name or '..'in Path(name).parts:raise ValueError('Unsafe author input basename')
 p=root/name
 if p.is_symlink()or p.is_junction():raise ValueError('Linked author input refused')
 return p
def donor(pack,record):
 p=safe(pack,record['file']);payload=p.read_bytes()
 if sha(payload)!=record['sha256']:raise ValueError('Genuine HD source differs')
 with Image.open(p)as im:out=im.convert('RGBA')
 if list(out.size)!=record['HD_dimensions']:raise ValueError('HD source dimensions differ')
 return out
def matches_hue(rgb,kind):
 r,g,b=rgb
 if kind=='purple':return b>65 and b>r*1.02 and r>g*1.02
 if kind=='orange':return r>65 and r>g*1.25 and g>b*1.3
 if kind=='green':return g>65 and g>r*1.4 and g>b*1.3
 if kind=='blue':return b>130 and b>r*1.15 and g>70
 raise ValueError('Unknown HD palette field')
def palette_patch(image,original,record):
 """Extend clean, actual HD source colours by row; never read native pixels.

 Captions and their black/white outlines are excluded by the declared colour
 family. The selected RGB is an actual source colour closest to the component
 median, not a native bitmap resize. Pattern geometry is restored separately.
 """
 x,y,z,t=b4(record['target_box_native']);start,end=(round(v*4)for v in record['sample_x_native'])
 patch=Image.new('RGBA',(z-x,t-y));draw=ImageDraw.Draw(patch);pixels=original.load()
 for row in range(y,t):
  colors=[pixels[col,row][:3]for col in range(start,end)if pixels[col,row][3]>=240 and matches_hue(pixels[col,row][:3],record['hue'])]
  if not colors:raise ValueError('HD palette row has no unlettered source colour')
  med=tuple(sorted(c[i]for c in colors)[len(colors)//2]for i in range(3))
  color=min(colors,key=lambda c:(sum(abs(c[i]-med[i])for i in range(3)),c))
  draw.line((0,row-y,z-x-1,row-y),fill=(*color,255))
 image.paste(patch,(x,y))
def coons_patch(image,original,record):
 """Reconstruct only an HD caption backdrop from its original HD borders.

 The continuous colour surface matches all four unchanged boundary rows.
 It contains no sampled native bitmap and cannot touch a photograph/frame.
 """
 x,y,z,t=b4(record['target_box_native']);width,height=z-x,t-y;px=original.load()
 top=[px[x+i,y][:3]for i in range(width)];bottom=[px[x+i,t-1][:3]for i in range(width)]
 left=[px[x,y+i][:3]for i in range(height)];right=[px[z-1,y+i][:3]for i in range(height)]
 corners=[top[0],top[-1],bottom[0],bottom[-1]];data=bytearray(width*height*4)
 for row in range(height):
  v=row/(height-1)
  for col in range(width):
   u=col/(width-1);at=(row*width+col)*4
   for c in range(3):
    edge=(1-u)*left[row][c]+u*right[row][c]+(1-v)*top[col][c]+v*bottom[col][c]
    corner=(1-u)*(1-v)*corners[0][c]+u*(1-v)*corners[1][c]+(1-u)*v*corners[2][c]+u*v*corners[3][c]
    data[at+c]=max(0,min(255,round(edge-corner)))
   data[at+3]=255
 image.paste(Image.frombytes('RGBA',(width,height),bytes(data)),(x,y))
def compose(record,inputs,pack,vectors):
 original=donor(pack,record['background_donor']);image=original.copy()
 for box in record['clear_rectangles_native']:image.paste((0,0,0,0),b4(box))
 for item in record.get('HD_palette_patches',[]):palette_patch(image,original,item)
 for item in record.get('HD_coons_patches',[]):coons_patch(image,original,item)
 for layer in record.get('vector_layers',[]):
  data=safe(inputs,layer['file']).read_bytes()
  if sha(data)!=layer['sha256']:raise ValueError('Vector geometry source differs')
  q,_=render_background(data,expected_sha256=layer['sha256'],native_size=tuple(record['native_dimensions']),remove_ids=())
  overlay=Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q))
  if layer.get('continuous_RGB_face'):
   # Native silhouette/alpha is never recomputed. Only RGB is blended to the real HD source.
   outer=b4(layer['feather_outer_native']);inner=b4(layer['feather_inner_native'])
   if not(outer[0]<inner[0]<inner[2]<outer[2]and outer[1]<inner[1]<inner[3]<outer[3]):raise ValueError('Invalid continuous face envelope')
   def smooth(v):
    v=max(0.0,min(1.0,v));return v*v*(3-2*v)
   mask=Image.new('L',overlay.size);mp=mask.load();ap=image.getchannel('A').load()
   foreground=[b4(c['target_box_native'])for c in record.get('genuine_HD_cells',[])if c.get('exact_RGBA_restore')]
   feather=layer['preserve_HD_foreground_fade_native']*4
   for yy in range(outer[1],outer[3]):
    py=yy+.5;vy=smooth((py-outer[1])/(inner[1]-outer[1]))*smooth((outer[3]-py)/(outer[3]-inner[3]))
    for xx in range(outer[0],outer[2]):
     if not ap[xx,yy]:continue
     px=xx+.5;coverage=vy*smooth((px-outer[0])/(inner[0]-outer[0]))*smooth((outer[2]-px)/(outer[2]-inner[2]))
     for left,top,right,bottom in foreground:
      if right<=outer[0]or left>=outer[2]or bottom<=outer[1]or top>=outer[3]:continue
      dx=max(left-px,0,px-right);dy=max(top-py,0,py-bottom)
      # Wider lateral blend beside the ball/rivet, short underbar return below all lettering.
      reach=8 if left<=49*4 and right>=227*4 else feather
      coverage*=smooth(max(dx,dy)/reach)
     mp[xx,yy]=round(255*coverage)
   mask=ImageChops.multiply(mask,overlay.getchannel('A'))
   rgb=Image.composite(overlay.convert('RGB'),image.convert('RGB'),mask)
   image=Image.merge('RGBA',(*rgb.split(),image.getchannel('A')))
   continue
  if layer.get('feather_native'):
   # Analytic rectangle coverage, not a sampled native bitmap mask.
   mask=Image.new('L',overlay.size);pixels=mask.load();width=layer['feather_native']*4
   for box in layer['rectangles_native']:
    x,y,z,t=b4(box)
    for yy in range(y,t):
     for xx in range(x,z):
      coverage=min(1,(xx+.5-x)/width,(z-.5-xx)/width,(yy+.5-y)/width,(t-.5-yy)/width)
      pixels[xx,yy]=max(pixels[xx,yy],round(255*coverage))
   overlay.putalpha(ImageChops.multiply(overlay.getchannel('A'),mask))
  image.alpha_composite(overlay)
 for cell in record.get('genuine_HD_cells',[]):
  crop=original.crop(b4(cell['source_box_native']));target=cell['target_box_native'];size=((target[2]-target[0])*4,(target[3]-target[1])*4)
  if crop.size!=size:crop=crop.resize(size,Image.Resampling.LANCZOS)
  if cell.get('exact_RGBA_restore'):image.paste(crop,(target[0]*4,target[1]*4))
  else:image.alpha_composite(crop,(target[0]*4,target[1]*4))
 q,_=_render_vector_text(dict(native_dimensions=record['native_dimensions'],family=record['family'],language='ja',font_family='japanese',labels=record['labels'],native_guide=record['native_guide']),vectors)
 image.alpha_composite(Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q)))
 return image
def build(inputs,pack,output):
 output.mkdir(parents=True,exist_ok=False);raw=safe(inputs,'extra-layout.json').read_bytes();layout=json.loads(raw)
 vraw=safe(inputs,'extra-vector-fragment.json').read_bytes()
 if sha(vraw)!=layout['vectors_sha256']:raise ValueError('Captured font vectors differ')
 vectors=json.loads(vraw);records=[]
 for r in layout['records']:
  im=compose(r,inputs,pack,vectors);path=output/r['target'];im.save(path)
  records.append(dict(**r,file=path.name,sha256=sha(path.read_bytes()),RGBA_sha256=sha(im.tobytes()),native_bitmap_resampled_for_HD=False,runtime_validated=False))
 receipt=dict(schema=1,complete_atlases=4,game_ids=['GC6J01'],layout_sha256=sha(raw),vectors_sha256=sha(vraw),records=records,Dolphin_started=False)
 (output/'extra-four-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return receipt
def reviews(receipt,output,native):
 for r in receipt['records']:
  with Image.open(native/r['target'])as im:src=im.convert('RGBA')
  with Image.open(output/r['file'])as im:art=im.convert('RGBA')
  scale=2 if src.width<450 else 1
  a=src.resize((src.width*scale,src.height*scale),Image.Resampling.NEAREST);b=art.resize(a.size,Image.Resampling.LANCZOS)
  board=Image.new('RGB',(a.width*2+20,a.height+32),'#686868');d=ImageDraw.Draw(board);d.text((8,7),'Original - diagnostic source',fill='white');d.text((a.width+28,7),'HD',fill='white');board.paste(a,(0,30),a);board.paste(b,(a.width+20,30),b);board.save(output/(Path(r['target']).stem+'-review.png'))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--pack-textures',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--native-diagnostics',type=Path);args=p.parse_args();app=QGuiApplication.instance()or QGuiApplication([])
 receipt=build(args.inputs,args.pack_textures,args.output)
 if args.native_diagnostics:reviews(receipt,args.output,args.native_diagnostics)
 print(json.dumps(dict(atlases=4,labels=sum(len(r['labels'])for r in receipt['records']))))
if __name__=='__main__':main()
