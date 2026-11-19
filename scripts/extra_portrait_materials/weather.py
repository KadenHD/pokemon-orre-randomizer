"""Deterministic weather-form material authoring from pinned Sunny HD paint.

Native maps supply flat palette anchors and analytic lighting parameters only.
All painted eye/mouth/reflection detail comes from the actual HD source.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image,ImageDraw
from orre_randomizer.artwork import _png
from orre_randomizer.hd_images import load_texture,resolve_texture

HERE=None
STUDY=None
INVENTORY={}
PACK_ROOTS={}


def configure(output,native_directory,models,packs):
    global HERE,STUDY,INVENTORY,PACK_ROOTS
    HERE=Path(output)
    STUDY=Path(native_directory)
    INVENTORY=models
    PACK_ROOTS=packs


def rows(form):
    return [t for m in INVENTORY['pkx_powalen'+form+'.fsys']['members'] for t in m.get('textures',[])]


def native(row):
    return np.asarray(Image.open(STUDY/row['png']).convert('RGBA'))


def load_hd(row):
    loaded=load_texture(resolve_texture(PACK_ROOTS['colosseum']/'Textures',row['native_key']),expected_native_size=tuple(row['dimensions']))
    assert loaded.metadata['sha256']==row['hd']['colosseum']['sha256']
    return np.array(Image.frombytes('RGBA',(loaded.image.width(),loaded.image.height()),bytes(loaded.image.constBits()))),loaded.metadata


def major_colours(image,count):
    colors,counts=np.unique(image[:,:,:3].reshape(-1,3),axis=0,return_counts=True)
    order=np.argsort(counts)[::-1]
    selected=[]
    for at in order:
        color=colors[at].astype(float)
        if color.max()-color.min()<30:
            continue
        if all(np.linalg.norm(color-other)>60 for other in selected):
            selected.append(color)
        if len(selected)==count:
            return np.array(selected)
    raise ValueError('The colour plate does not contain the expected distinct flat anchors')


def recolour_paint(hd,guide,target,count):
    colors=major_colours(guide,count)
    source_hd=major_colours(hd,count)
    source_hd=np.array([source_hd[np.argmin(np.linalg.norm(source_hd-color,axis=1))] for color in colors])
    target_colors=[]
    for color in colors:
        mask=np.linalg.norm(guide[:,:,:3].astype(float)-color,axis=2)<2
        target_colors.append(np.median(target[:,:,:3][mask],axis=0))
    target_colors=np.array(target_colors)
    source_palette=np.vstack((np.zeros(3),np.ones(3)*255,source_hd))
    destination=np.vstack((np.zeros(3),np.ones(3)*255,target_colors))
    if count==1:
        # Unique colour plus black/white: decompose colour saturation from grey.
        chroma=source_hd[0]-source_hd[0].mean()
        rgb=hd[:,:,:3].astype(float)
        strength=np.sum((rgb-rgb.mean(2)[:,:,None])*chroma,axis=2)/np.dot(chroma,chroma)
        neutral=rgb.mean(2)-strength*source_hd[0].mean()
        mapped=neutral[:,:,None]+strength[:,:,None]*target_colors[0]
        mask=(strength>0)&(hd[:,:,3]>0)
    else:
        basis=np.column_stack((source_palette,np.ones(4)))
        weights=np.column_stack((hd[:,:,:3].reshape(-1,3),np.ones(hd.shape[0]*hd.shape[1])))@np.linalg.inv(basis)
        mapped=(weights@destination).reshape(hd.shape[0],hd.shape[1],3)
        mask=hd[:,:,3]>0
    result=hd.copy()
    result[:,:,:3][mask]=mapped[mask].round().clip(0,255).astype('uint8')
    return result,{'kind':'fixed semantic flat-palette transfer on genuine HD paint',
        'source_native_palette':colors.tolist(),'source_hd_palette':source_hd.tolist(),
        'target_native_palette':target_colors.tolist(),'no_rgb_regression':True}


def environment(hd,guide,target):
    # Three physical environment-palette stops; the painted image remains HD.
    native_luma=guide[:,:,:3].mean(2)
    bounds=np.quantile(native_luma,[0,.25,.5,.75,1])
    source_hd_luma=hd[:,:,:3].mean(2)
    stops=[]
    for low,high in zip(bounds[:-1],bounds[1:]):
        mask=(native_luma>=low)&(native_luma<=high)
        stops.append(np.median(target[:,:,:3][mask],axis=0))
    levels=np.quantile(source_hd_luma,[.125,.375,.625,.875])
    mapped=np.stack([np.interp(source_hd_luma,levels,np.array(stops)[:,c]) for c in range(3)],axis=2)
    result=hd.copy();result[:,:,:3]=mapped.round().clip(0,255).astype('uint8')
    return result,{'kind':'four-stop form environment palette over original HD reflection paint',
        'source_luma_stops':levels.tolist(),'target_rgb_stops':np.array(stops).tolist()}


def analytic_grey(target):
    height,width=target.shape[:2]
    yy,xx=np.mgrid[:height,:width]
    u=(xx+.5)/width;v=(yy+.5)/height
    # Polynomial lighting and centred radial lobes are continuous UV functions.
    def terms(x,y):
        cols=[np.ones_like(x),x,y,x*x,x*y,y*y,x**3,x*x*y,x*y*y,y**3]
        for sigma in (.08,.18,.35):
            cols.append(np.exp(-((x-.5)**2+(y-.5)**2)/(2*sigma*sigma)))
        return np.stack(cols,axis=2)
    values=target[:,:,:3].mean(2)
    coefficients=np.linalg.lstsq(terms(u,v).reshape(-1,13),values.ravel(),rcond=None)[0]
    reconstructed=terms(u,v)@coefficients
    hy,hx=np.mgrid[:height*4,:width*4]
    luminance=(terms((hx+.5)/(width*4),(hy+.5)/(height*4))@coefficients).round().clip(0,255).astype('uint8')
    result=np.full((height*4,width*4,4),255,dtype='uint8');result[:,:,:3]=luminance[:,:,None]
    return result,{'kind':'analytic continuous UV lighting material',
        'basis':'cubic UV polynomial plus three centred Gaussian lobes',
        'coefficients':coefficients.tolist(),'native_guide_mae':float(np.abs(reconstructed-values).mean()),
        'native_guide_p99':float(np.quantile(np.abs(reconstructed-values),.99))}


def retarget_opacity(hd_alpha,source_alpha,target_alpha):
    values=np.unique(source_alpha)
    stops=np.array([np.median(target_alpha[source_alpha==value]) for value in values])
    stops=np.maximum.accumulate(stops)
    stops[values==0]=0
    stops[values==255]=255
    output=np.interp(hd_alpha,values,stops).round().clip(0,255).astype('uint8')
    predicted=np.interp(source_alpha,values,stops)
    return output,{'kind':'monotone physical-opacity curve on actual HD specular alpha',
                   'source_native_levels':values.tolist(),'target_opacity_levels':stops.tolist(),
                   'native_guide_mae':float(np.abs(predicted-target_alpha).mean()),
                   'hd_lobe_positions_and_detail_preserved':True}


def main():
    source_rows=rows('_f');reports=[];tiles=[]
    for form in ('_w','_i'):
        folder=HERE/'weather-authored'/('rain' if form=='_w' else 'snow');folder.mkdir(parents=True,exist_ok=True)
        for i,row in enumerate(rows(form)):
            target=native(row)
            source=source_rows[0 if i==0 else 1 if i==1 else 4 if i==len(rows(form))-1 else 3]
            hd,reference=load_hd(source)
            unique=np.unique(target.reshape(-1,4),axis=0)
            if len(unique)==1:
                output=np.tile(unique[0],(target.shape[0]*4,target.shape[1]*4,1))
                recipe={'kind':'exact constant-colour analytic material','rgba':unique[0].tolist()}
            elif i in (0,1):
                source=source_rows[i];hd,reference=load_hd(source)
                output,recipe=recolour_paint(hd,native(source),target,1 if i==0 else 2)
            elif i==len(rows(form))-1:
                output,recipe=environment(hd,native(source),target)
            elif row['dimensions']==[32,32]:
                # The same three native specular lobes; use the real HD paint.
                source_native=native(source)
                gain=float(target[:,:,:3].max()/max(1,source_native[:,:,:3].max()))
                output=hd.copy()
                output[:,:,:3]=(output[:,:,:3].astype(float)*gain).round().clip(0,255).astype('uint8')
                output[:,:,3],opacity=retarget_opacity(hd[:,:,3],source_native[:,:,3],target[:,:,3])
                recipe={'kind':'genuine HD Castform specular-lobe paint with form intensity',
                        'intensity_gain_from_native_material_extrema':gain,
                        'native_alpha_values':np.unique(target[:,:,3]).tolist(),
                        'opacity':opacity,
                        'native_uv_guide_sha256':hashlib.sha256(target.tobytes()).hexdigest()}
            else:
                output,recipe=analytic_grey(target)
                if recipe['native_guide_p99']>14:
                    raise ValueError('Analytic material needs a more faithful lighting model: '+row['native_key'])
            path=folder/row['native_key'];path.write_bytes(_png((output.shape[1],output.shape[0]),output.tobytes()))
            reports.append({'target':row['native_key'],'form':form,'dimensions':[output.shape[1],output.shape[0]],
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'reference':reference,
                'kind':'authored-pack-derived-material','native_bitmap_resampled':False,
                'recipe':recipe,'review_only':True,'GPU_verified':False})
            if i in (0,1,len(rows(form))-1):
                original=Image.fromarray(target)
                painted=Image.fromarray(output)
                if original.height>original.width*2:original=original.crop((0,0,original.width,original.width))
                if painted.height>painted.width*2:painted=painted.crop((0,0,painted.width,painted.width))
                tiles.extend(((form+' #'+str(i)+' native guide',original),(form+' #'+str(i)+' authored HD',painted)))
    (HERE/'weather-authored/materials.json').write_text(json.dumps(reports,indent=2)+'\n')
    board=Image.new('RGB',(6*200,((len(tiles)+5)//6)*220),'#ddd');draw=ImageDraw.Draw(board)
    for i,(label,im) in enumerate(tiles):
        x,y=(i%6)*200,(i//6)*220;draw.text((x+4,y+4),label,fill='black')
        im.thumbnail((190,190));im=im.resize((190,190),Image.Resampling.NEAREST)
        board.paste(im,(x+4,y+24))
    board.save(HERE/'weather-authored/material-review.png')
    print('Authored',len(reports),'source-pinned material candidates; GPU validation pending.')


if __name__=='__main__':main()
