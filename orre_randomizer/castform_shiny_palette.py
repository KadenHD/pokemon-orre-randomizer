"""Source-guarded semantic weather palettes; geometry and motion retained."""
from __future__ import annotations
import hashlib
import struct
import math
from .engine.analyze_game import FormatError, u32
from .engine.actor_palette import _walk_materials, _cmpr_endpoints
from .hd_overlays import _pkx_dat, _Texture, _pixels, _size, _texture_key, _dat_textures

PALETTES = {
    'f': {'head': (174, 30, 73), 'mask': (247, 151, 137),
          'source_head': (252, 70, 3), 'source_mask': (250, 223, 121),
          'cloud': (227, 182, 214)},
    'w': {'head': (21, 139, 143), 'mask': (133, 226, 70),
          'source_head': (0, 119, 213), 'source_mask': (188, 215, 236),
          'cloud': (120, 157, 178)},
    'i': {'head': (66, 88, 194), 'mask': (229, 234, 111),
          'source_head': (133, 128, 217), 'source_mask': (173, 173, 220)},
}
SOURCE_PKX = {
    ('colosseum', 'f'): 'f70cda7cba9f2a132652fb910ac11d5662557dc77d39214f3ce99aed8a7d482b',
    ('colosseum', 'w'): '56dc626b5aafaf63558568f29a2d41846c4d3699d9147bb37ba6556045da5372',
    ('colosseum', 'i'): 'fad5ec994c69ba35c1c2fbbdb01b6f0148f943df6a905035682402c9cb416809',
    ('xd', 'f'): 'a3ac41da46d8229e1008b133a1fea59e906cb1e9f6ad1221cc9e9ce8a752c1ac',
    ('xd', 'w'): '8e67ca400c2019463a06faecb55811552e7ab36c244ac6d8a0cc55421a6b77f8',
    ('xd', 'i'): '9fb6693498c7961becf94c34784b6317621740ce3a97efef202d9ef3bd30db8a',
}

def _inverse3(matrix):
    a,b,c=matrix[0];d,e,f=matrix[1];g,h,i=matrix[2]
    det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
    if abs(det)<1e-8:raise ValueError('Degenerate palette anchors')
    return [[(e*i-f*h)/det,(c*h-b*i)/det,(b*f-c*e)/det],
            [(f*g-d*i)/det,(a*i-c*g)/det,(c*d-a*f)/det],
            [(d*h-e*g)/det,(b*g-a*h)/det,(a*e-b*d)/det]]

def palette_matrix(form):
    p=PALETTES[form]
    inv=_inverse3([[p['source_head'][i],p['source_mask'][i],255] for i in range(3)])
    target=[[p['head'][i],p['mask'][i],255] for i in range(3)]
    return [[sum(target[i][k]*inv[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def map_rgb(rgb, form, role):
    p=PALETTES[form]
    if role=='head-flat':return p['head']
    if role=='cloud':
        # Gray cloud's baked light remains multiplicative, not a flat repaint.
        light=sum(rgb)/3/179
        return tuple(min(255,round(c*light)) for c in p['cloud'])
    if max(rgb)-min(rgb)<=8:return tuple(rgb)  # pupil, teeth, white highlights
    if form in ('w','i'):
        # These native blue head/mask anchors are almost collinear with white.
        # A 3D affine inverse extrapolates antialias pixels into magenta. Use a
        # bounded saturation coordinate inside the actual source hue cone.
        source=p['source_head'];mean=sum(source)/3;chroma=[c-mean for c in source]
        mean_rgb=sum(rgb)/3;observed=[c-mean_rgb for c in rgb]
        dot=sum(a*b for a,b in zip(chroma,observed))
        norm=math.sqrt(sum(a*a for a in chroma)*sum(a*a for a in observed))
        if norm<=0 or dot/norm<0.90:return tuple(rgb)  # warm mouth/iris/artwork stays original
        def saturation(color):return (max(color)-min(color))/max(1,max(color))
        start,end=saturation(p['source_mask']),saturation(source)
        weight=max(0,min(1,(saturation(rgb)-start)/(end-start)))
        old_peak=(1-weight)*max(p['source_mask'])+weight*max(source)
        light=max(rgb)/old_peak
        return tuple(max(0,min(255,round(((1-weight)*p['mask'][i]+weight*p['head'][i])*light))) for i in range(3))
    if role=='mask':
        source=p['source_mask'];mean=sum(source)/3
        chroma=[c-mean for c in source];rgb_mean=sum(rgb)/3
        weight=sum((c-rgb_mean)*v for c,v in zip(rgb,chroma))/sum(v*v for v in chroma)
        if weight<=0:return tuple(rgb)
        out=[rgb[i]+weight*(p['mask'][i]-source[i]) for i in range(3)]
    else:
        matrix=palette_matrix(form)
        out=[sum(matrix[i][j]*rgb[j] for j in range(3)) for i in range(3)]
    return tuple(max(0,min(255,round(c))) for c in out)

def _unpack565(value):
    return ((value>>11)*255+16)//31, (((value>>5)&63)*255+32)//63, ((value&31)*255+16)//31

def _pack565(rgb):
    r,g,b=rgb
    return ((r*31+127)//255)<<11 | ((g*63+127)//255)<<5 | (b*31+127)//255

def _dat_graph(dat):
    length,size,count,exports,imports=struct.unpack_from('>5I',dat)
    if imports or not 0<size<length<=len(dat):raise FormatError('Unexpected weather DAT')
    data=dat[32:32+size];rel=set(struct.unpack_from('>'+str(count)+'I',dat,32+size))
    syms=32+size+count*4;names=syms+exports*8
    def string(at):return dat[at:dat.index(b'\0',at)].decode('ascii')
    scenes=[p for p,n in struct.iter_unpack('>II',dat[syms:names]) if string(names+n)=='scene_data']
    if len(scenes)!=1:raise FormatError('No weather scene')
    model=u32(data,u32(data,scenes[0]))
    images,palettes,solid=_walk_materials(data,rel,model,include_textured_colors=True)
    if palettes:raise FormatError('Unexpected weather palette format')
    return data,images,solid

def texture_roles(original_dat, form):
    data,images,solid=_dat_graph(original_dat)
    result={}
    for desc in sorted(images):
        start,w,h,fmt,mip,_,lod=struct.unpack_from('>IHHIIff',data,desc)
        if mip or lod != 0:raise FormatError('Unknown mipmapped weather source; author every level before support')
        raw=data[start:start+_size(w,h,fmt)]
        tex=_Texture(w,h,fmt,raw,mipmaps=bool(mip))
        role= ('mask' if (w,h)==(64,768) else 'face' if (w,h)==(128,720)
               else 'head-flat' if (w,h)==(4,4) and _pixels(tex)[:3]==bytes(PALETTES[form]['source_head'])
               else 'cloud' if form=='w' and (w,h) in ((64,64),(4,4)) and
                    max(_pixels(tex)[:3])-min(_pixels(tex)[:3])<12 else None)
        if role:result[start]={'role':role,'descriptor':desc,'width':w,'height':h,'format':fmt,
            'bytes':len(raw),'native_key':_texture_key(tex),'native_rgba_sha256':hashlib.sha256(_pixels(tex)).hexdigest()}
    return result,solid

def make_weather_shiny_pkx(original, *, game, form):
    if game not in ('colosseum','xd') or form not in PALETTES:raise FormatError('Unknown weather model')
    expected=SOURCE_PKX.get((game,form))
    if expected is None:raise FormatError('Weather source identity not installed')
    if hashlib.sha256(original).hexdigest()!=expected:raise FormatError('Weather model source changed')
    offset=0xe60 if game=='xd' else 0x40
    dat=_pkx_dat(original,game=='xd');length=u32(dat,0)
    textures,solid=texture_roles(dat,form)
    if len([r for r in textures.values() if r['role'] in ('face','mask','head-flat')])!=3:
        raise FormatError('Unexpected weather face material identities')
    out=bytearray(original);allowed=set();edits=[]
    for start,row in textures.items():
        if row['format']!=14:raise FormatError('Expected original CMPR weather paint')
        for at in range(offset+32+start,offset+32+start+row['bytes'],8):
            a,b=struct.unpack_from('>HH',original,at);indices=original[at+4:at+8]
            c,d=(_pack565(map_rgb(_unpack565(v),form,row['role'])) for v in (a,b))
            c,d,indices=_cmpr_endpoints(a,b,indices,c,d)
            struct.pack_into('>HH4s',out,at,c,d,indices);allowed.update(range(at,at+8))
        edits.append(row)
    cloud_edits=0
    if form in ('f','w'):
        data=dat[32:32+u32(dat,4)]
        for at in sorted(solid):
            rgb=tuple(data[at+4:at+7])
            # Cloud white and base-lobe gray are native untextured materials.
            if rgb not in ((255,255,255),(179,179,179)):continue
            # Textured head/face also use white but must stay neutral.
            if at not in ((0x2db4,0x2f40) if form=='f' else (0x321c,)):continue
            for color_at in (at+4,at+8):
                pos=offset+32+color_at
                base=tuple(original[pos:pos+3]);scale=sum(base)/3/255
                target=tuple(round(c*scale) for c in PALETTES[form]['cloud'])
                out[pos:pos+3]=bytes(target);allowed.update(range(pos,pos+3))
            edits.append({'role':'cloud-untextured','material':at,'native_diffuse':rgb})
            cloud_edits+=1
        if cloud_edits != (2 if form=='f' else 1):raise FormatError('Expected native cloud materials missing')
    changed=[i for i,(a,b) in enumerate(zip(original,out)) if a!=b]
    if not changed or any(i not in allowed for i in changed):raise FormatError('Weather edit escaped colour payload')
    before=list(_dat_textures(dat));after=list(_dat_textures(_pkx_dat(bytes(out),game=='xd')))
    if len(before)!=len(after):raise FormatError('Weather descriptor count changed')
    all_textures=[]
    for a,b in zip(before,after):
        if (a.width,a.height,a.fmt)!=(b.width,b.height,b.fmt) or _pixels(a)[3::4]!=_pixels(b)[3::4]:
            raise FormatError('Weather texture dimensions or opacity changed')
        for row in edits:
            if row.get('native_key')==_texture_key(a):
                row['shiny_native_key']=_texture_key(b)
                row['shiny_native_rgba_sha256']=hashlib.sha256(_pixels(b)).hexdigest()
        texture_row={'original_native_key':_texture_key(a),'native_key':_texture_key(b),
            'native_dimensions':[b.width,b.height],'format':b.fmt,
            'native_rgba_sha256':hashlib.sha256(_pixels(b)).hexdigest()}
        if texture_row not in all_textures:all_textures.append(texture_row)
    ranges=[]
    for at in changed:
        if ranges and ranges[-1][1]==at:ranges[-1][1]=at+1
        else:ranges.append([at,at+1])
    return bytes(out),{'game':game,'form':form,'source_sha256':expected,
        'sha256':hashlib.sha256(out).hexdigest(),'dat_sha256':hashlib.sha256(_pkx_dat(bytes(out),game=='xd')[:length]).hexdigest(),
        'changed_bytes':len(changed),'changed_ranges':ranges,'materials':edits,'palette':PALETTES[form],
        'all_textures':all_textures,
        'geometry_animation_uv_footer_unchanged':True,'native_texture_alpha_unchanged':True}
