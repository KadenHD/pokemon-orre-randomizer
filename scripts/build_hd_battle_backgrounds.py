"""Portable source-only reconstruction of registered battle HUD backgrounds.

Inputs are explicit author SVG/PSD sources, the genuine HD texture directory and
the registered catalogue or reviewed recipe fragment. No ROM, native PNG, save
or private build path is used. Keep read_hd_menu_psd_layers.py beside this tool.
"""
from pathlib import Path
import argparse, hashlib, json, os, sys
from xml.etree import ElementTree as ET
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageChops
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_svg import render_background
from orre_randomizer.hd_menu_atlases import _pixel_bytes
from read_hd_menu_psd_layers import layers as read_psd

SVG='http://www.w3.org/2000/svg'
def sha(payload):return hashlib.sha256(payload).hexdigest()
def pixel_box(box):return tuple(v*4 for v in box)
def png(q):return Image.frombytes('RGBA',(q.width(),q.height()),_pixel_bytes(q))
def expand(box,n,w,h):return[max(0,box[0]-n),max(0,box[1]-n),min(w,box[2]+n),min(h,box[3]+n)]

def clean_svg(author_root,source,size):
    member=Path(source['source_member'])
    if member.is_absolute()or'..'in member.parts or member.parts[0]!='svg':raise ValueError('Unsafe author member')
    original=(author_root/member).read_bytes()
    if sha(original)!=source['source_original_sha256']:raise ValueError('Original author SVG differs')
    payload=original
    normal=source['normalization']
    if normal:
        root=ET.fromstring(original)
        if [float(v)for v in root.attrib['viewBox'].split()]!=normal['original_viewBox']:raise ValueError('SVG viewBox changed')
        sx,sy=normal['scale']
        group=ET.Element('{'+SVG+'}g',{'id':'declared-pixel-unit-normalization','transform':f'scale({sx:.14g},{sy:.14g})'})
        for child in list(root):
            if child.tag not in ('{'+SVG+'}defs','{'+SVG+'}metadata'):
                root.remove(child);group.append(child)
        root.append(group);root.set('viewBox',f'0 0 {size[0]} {size[1]}')
        payload=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    # The precise XML prefix serialization can vary when another library has
    # registered namespaces in the process. Rendering is asserted against the
    # final registered PNG, not an incidental prefix spelling.
    image,_=render_background(payload,expected_sha256=sha(payload),native_size=size,
                              remove_ids=tuple(source['remove_ids']))
    return png(image)

def commands_clean(author_root,source):
    clean=clean_svg(author_root,source,(454,78))
    record=source['author_PSD_metal_layer'];member=Path(record['source_member'])
    if member.is_absolute()or'..'in member.parts or member.parts[0]!='edited':raise ValueError('Unsafe PSD member')
    psd=author_root/member
    if sha(psd.read_bytes())!=record['sha256']:raise ValueError('Author PSD differs')
    size,layers=read_psd(psd);layer=layers[record['layer_index']]
    if size!=(1816,312)or layer['bounds']!=record['bounds']or layer['name']!=record['layer_name']or layer['blend']!='over':
        raise ValueError('PSD metal layer identity differs')
    left,top,right,bottom=layer['bounds']
    grain=layer['image'].convert('RGB').crop((146*4-left,2*4-top,336*4-left,52*4-top))
    region=clean.crop((146*4,2*4,336*4,52*4))
    shade=ImageChops.overlay(region.convert('RGB'),grain).convert('RGBA');shade.putalpha(region.getchannel('A'))
    clean.paste(shade,(146*4,2*4));return clean

def erased(pack,source,clean):
    name=Path(source['source_pack_file'])
    if name.name!=str(name):raise ValueError('Unsafe donor basename')
    path=pack/name
    if sha(path.read_bytes())!=source['source_pack_sha256']:raise ValueError('HD donor differs')
    with Image.open(path)as im:out=im.convert('RGBA')
    for box in source['source_caption_erasure_rectangles']:
        out.paste(clean.crop(pixel_box(box)),(box[0]*4,box[1]*4))
    return out

def nine_slice(image,source,target,border):
    image=image.crop(pixel_box(source));w,h=image.size
    size=((target[2]-target[0])*4,(target[3]-target[1])*4)
    if h!=size[1]or min(w,size[0])<border*2:raise ValueError('Bad fixed-corner relayout')
    out=Image.new('RGBA',size)
    out.paste(image.crop((0,0,border,h)),(0,0))
    out.paste(image.crop((w-border,0,w,h)),(size[0]-border,0))
    out.paste(image.crop((border,0,w-border,h)).resize((size[0]-border*2,h),Image.Resampling.LANCZOS),(border,0))
    return out

def players(source):
    root=ET.Element('{'+SVG+'}svg',{'width':'72','height':'132','viewBox':'0 0 72 132'})
    for i,color in enumerate(source['palette']):
        ET.SubElement(root,'{'+SVG+'}rect',{'x':'2.5','y':str(i*26+2.5),'width':'67','height':'23',
          'rx':'11.5','ry':'11.5','fill':color,'stroke':'#000000','stroke-width':'1'})
    payload=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    q,_=render_background(payload,expected_sha256=sha(payload),native_size=(72,132),remove_ids=())
    return png(q)

def reproduce(record,author_root,pack):
    recipe=record['transform'];source=recipe['author_source'];family=recipe['family']
    if family=='battle-player-badges':return players(source)
    if family=='battle-hud':
        clean=clean_svg(author_root,source,(244,58));out=erased(pack,source,clean)
        move=source['capsule_relayout'];old=move['source_native_rectangle'];new=move['target_native_rectangle']
        out.paste((0,0,0,0),pixel_box(old))
        out.paste(nine_slice(clean,old,new,move['fixed_edge_pixels_x4']),(new[0]*4,new[1]*4));return out
    if family=='battle-command-timers':
        clean=commands_clean(author_root,source);base=erased(pack,source,clean);out=base.copy()
        move=source['timer_relayout'];arch=source['white_arch_relayout']
        for box in move['source_native_rectangles']:out.paste((0,0,0,0),pixel_box(box))
        a,b=arch['source_native_rectangle'],arch['target_native_rectangle']
        if a!=b:
            a,b=expand(a,1,454,78),expand(b,1,454,78)
            out.paste((0,0,0,0),pixel_box(a))
        for a0,b0 in zip(move['source_native_rectangles'],move['target_native_rectangles']):
            out.paste(nine_slice(base,a0,b0,move['fixed_corner_pixels_x4']),(b0[0]*4,b0[1]*4))
        if arch['source_native_rectangle']!=arch['target_native_rectangle']:
            out.paste(base.crop(pixel_box(a)),(b[0]*4,b[1]*4))
        return out
    raise ValueError('Unreviewed battle background family')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author-root',type=Path,required=True)
    parser.add_argument('--pack-textures',type=Path,required=True)
    parser.add_argument('--recipes',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=False)
    app=QGuiApplication.instance()or QGuiApplication([])
    records=[row for row in json.loads(args.recipes.read_text(encoding='utf-8'))['records']
      if row['transform']['family']in('battle-player-badges','battle-hud','battle-command-timers')]
    if not records:raise ValueError('No registered battle backgrounds in the supplied catalogue')
    receipts=[];written={}
    for record in records:
        target=args.output_dir/Path(record['bundled_donor']).name
        image=reproduce(record,args.author_root,args.pack_textures)
        if target.name in written:
            if written[target.name]!=record['source_sha256']:raise ValueError('Conflicting registered output')
        else:image.save(target);written[target.name]=record['source_sha256']
        digest=sha(target.read_bytes())
        if digest!=record['source_sha256']:raise ValueError('Reproduced background differs: '+target.name)
        receipts.append({'file':target.name,'sha256':digest,'matches_registered_background':True})
    (args.output_dir/'reproduction-receipt.json').write_text(json.dumps({'records':receipts,
        'native_bitmaps_required':False,'Dolphin_started':False},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'backgrounds':len(receipts),'all_exact':True}))

if __name__=='__main__':main()
