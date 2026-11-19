"""Speed-form eye construction from genuine HD aperture/iris and native UV guides.

The native bitmap supplies ellipse/pupil coordinates only. It supplies no output
RGB or enlarged image. This is an authored-material study, not a released asset.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

from orre_randomizer.artwork import _png
from orre_randomizer.hd_images import load_texture,resolve_texture
from . import eye_uv as _uv_module
uv={"sample":_uv_module.sample}

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


def circle_and_pupil(image):
    rgb=image[:,:,:3].astype(float)
    white=(rgb.min(2)>150)&(rgb.max(2)-rgb.min(2)<25)
    visited=np.zeros(white.shape,bool)
    components=[]
    height,width=white.shape
    for y,x in zip(*np.nonzero(white)):
        if visited[y,x]:
            continue
        stack=[(int(y),int(x))];visited[y,x]=True;points=[]
        while stack:
            yy,xx=stack.pop();points.append((yy,xx))
            for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
                a,b=yy+dy,xx+dx
                if 0<=a<height and 0<=b<width and white[a,b] and not visited[a,b]:
                    visited[a,b]=True;stack.append((a,b))
        components.append(points)
    if components:
        selected=max(components,key=len)
        white[:]=False
        for y,x in selected:
            white[y,x]=True
    yy,xx=np.nonzero(white)
    if len(xx)<20:
        return None
    radius=(xx.max()-xx.min()+1)/2
    center=np.array(((xx.max()+xx.min())/2,yy.max()-radius+.5))
    pupil=np.zeros(white.shape,bool)
    for y in range(white.shape[0]):
        xs=np.flatnonzero(white[y])
        if len(xs)>1:
            pupil[y,xs.min():xs.max()+1]=(rgb[y,xs.min():xs.max()+1].max(1)<70)
    py,px=np.nonzero(pupil)
    if len(px)<3:
        raise ValueError('Native iris does not identify its pupil unambiguously')
    pupil_center=np.array((px.mean(),py.mean()))
    pupil_radius=np.sqrt(len(px)/np.pi)
    return center,float(radius),pupil_center,float(pupil_radius)


def iris_retarget(source_hd,target_guide):
    target=circle_and_pupil(target_guide)
    if target is None:
        return source_hd.copy(),{'kind':'closed-eye upstream HD aperture retained'}
    geometry=circle_and_pupil(source_hd)
    center,radius,pupil_center,pupil_radius=geometry
    dst,dr,dp,dpr=target
    dst=dst*4+1.5
    dr*=4
    dp=dp*4+1.5
    dpr*=4
    height,width=source_hd.shape[:2]
    yy,xx=np.mgrid[:height,:width]
    rr=np.hypot(xx-center[0],yy-center[1])/radius
    rgb=source_hd[:,:,:3].astype(float)
    # Profile from the actual upstream iris repairs only the old pupil hole.
    white=(rgb.min(2)>90)&(rgb.max(2)-rgb.min(2)<30)
    bins=np.linspace(0,1.05,65)
    profile=[]
    for left,right in zip(bins,bins[1:]):
        samples=rgb[white&(rr>=left)&(rr<right)]
        profile.append(np.median(samples,axis=0) if len(samples) else np.array((255.,255.,255.)))
    coordinates=np.column_stack(((xx.ravel()-dst[0])*radius/dr+center[0],
                                  (yy.ravel()-dst[1])*radius/dr+center[1]))
    sampled=uv['sample'](source_hd.astype(float),coordinates).reshape(height,width,4)
    old_pupil_distance=np.hypot(coordinates[:,0]-pupil_center[0],coordinates[:,1]-pupil_center[1]).reshape(height,width)
    mapped_rr=np.hypot(coordinates[:,0]-center[0],coordinates[:,1]-center[1]).reshape(height,width)/radius
    radius_knots=(bins[:-1]+bins[1:])/2
    repaired=np.stack([np.interp(mapped_rr,radius_knots,np.asarray(profile)[:,channel]) for channel in range(3)],axis=2)
    repair_alpha=np.clip((pupil_radius+10-old_pupil_distance)/5,0,1)
    sampled[:,:,:3]=sampled[:,:,:3]*(1-repair_alpha[:,:,None])+repaired*repair_alpha[:,:,None]
    pupil_distance=np.hypot(xx-dp[0],yy-dp[1])
    pupil_alpha=np.clip(dpr+.5-pupil_distance,0,1)
    sampled[:,:,:3]*=(1-pupil_alpha[:,:,None])
    # Source aperture is actual HD, including its authored eyelid and border.
    hi,lo=rgb.max(2),rgb.min(2)
    neutral=np.clip((35-(hi-lo))/15,0,1)
    aperture=neutral*((hi<75)|(lo>80))
    base=source_hd.astype(float).copy()
    base[:,:,:3]*=(1-aperture[:,:,None])
    circle=np.clip(dr+.5-np.hypot(xx-dst[0],yy-dst[1]),0,1)*aperture
    base[:,:,:3]=base[:,:,:3]*(1-circle[:,:,None])+sampled[:,:,:3]*circle[:,:,None]
    base[:,:,3]=255
    return base.round().clip(0,255).astype('uint8'),{
        'kind':'upstream HD iris UV scaling plus independent native pupil placement',
        'source_iris_center_hd':center.tolist(),'source_iris_radius_hd':radius,
        'target_iris_center_hd':dst.tolist(),'target_iris_radius_hd':dr,
        'target_pupil_center_hd':dp.tolist(),'target_pupil_radius_hd':dpr,
        'old_pupil_repair':'radial colour profile measured from genuine HD iris',
        'source_hd_aperture_preserved':True,'native_bitmap_resampled':False}


def rebuild_background(image,target_guide,shiny,palettes):
    """Keep the actual HD eye paint, without importing another form's UV panels.

    Defense's coloured background has painted bevels in different positions.
    Multiplying it by a smooth lighting curve cannot remove those foreign
    panels. Reconstruct Speed's coloured UV regions analytically and preserve
    the real HD neutral aperture/iris, including its antialiased border.
    """
    from . import deoxys
    rgb=image[:,:,:3].astype(float)
    flat_palettes={};colour_receipt=[]
    for kind,colors in palettes.items():
        # The neighbouring face plate uses these same physical median anchors.
        # A separately sampled eye-background palette exposes its polygon seam.
        color=colors[1]
        flat_palettes[kind]=np.array([color]*3)
        colour_receipt.append({'class':kind,'source_hd_median_rgb':color.tolist(),
                               'shared_with_other_native_equal_colour_materials':True})
    guide=target_guide.copy()
    families=deoxys.classes(guide[:,:,:3],shiny)
    cyan=guide[:,:,:3][families==2]
    if not len(cyan):
        raise ValueError('The Speed eye has no unambiguous cyan material background')
    values,counts=np.unique(cyan,axis=0,return_counts=True)
    anchor=values[counts.argmax()]
    # Remove the native low-resolution eye from the background layer entirely.
    # Its feature geometry already positioned the actual HD iris. Rendering a
    # second vector copy beneath it would leave a jagged black fringe.
    guide[:,:,:3][(families!=1)&(families!=2)]=anchor
    background,construction=deoxys.construct(guide,shiny,flat_palettes,allow_analytic_rgb_ramp=False)
    hi,lo=rgb.max(2),rgb.min(2)
    neutral=np.clip((40-(hi-lo))/10,0,1)*((hi<75)|(lo>80))
    # This coverage comes from the genuine HD paint, not an enlarged native eye.
    mask=Image.fromarray((neutral*255).round().astype('uint8'))
    mask=mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.4))
    coverage=np.asarray(mask).astype(float)/255
    output=background.astype(float)
    output[:,:,:3]=output[:,:,:3]*(1-coverage[:,:,None])+rgb*coverage[:,:,None]
    return output.round().clip(0,255).astype('uint8'),{
        'kind':'native-form vector UV background with actual HD aperture/iris paint',
        'foreign_source_form_background_panels_retained':False,
        'native_bitmap_resampled':False,'hd_aperture_coverage_source':'actual HD neutral eye paint',
        'coloured_background_policy':'shared canonical HD family medians, no foreign painted UV panels',
        'native_neutral_eye_rendered_beneath_hd_iris':False,
        'neutral_uv_region_material_family':'cyan',
        'background_hd_colours':colour_receipt,
        'background_construction':construction}


def main():
    from . import deoxys
    deoxys.configure(HERE,STUDY,INVENTORY,PACK_ROOTS)
    inventory=INVENTORY
    def eye(form,shiny):
        return next(t for m in inventory['pkx_deoxys_'+form+('_c' if shiny else '')+'.fsys']['members'] for t in m.get('textures',[]) if t['dimensions']==[416,64])
    tiles=[];reports=[]
    normal_palettes,normal_references=deoxys.reference_palettes(False)
    for shiny in (False,True):
        palettes,palette_references=deoxys.reference_palettes(shiny)
        # This cyan is byte-identical in the native normal/shiny face plate;
        # its shared authored texture is generated once from the normal donor.
        palettes[2]=normal_palettes[2]
        palette_references[2]=normal_references[2]
        source,target=eye('def',shiny),eye('sp',shiny)
        loaded=load_texture(resolve_texture(PACK_ROOTS['xd']/'Textures',source['native_key']),expected_native_size=(416,64))
        hd=np.array(Image.frombytes('RGBA',(1664,256),bytes(loaded.image.constBits())))
        guide=np.asarray(Image.open(STUDY/target['png']).convert('RGBA'))
        output=hd.copy();recipes=[]
        for left,right in ((0,130),(130,288),(288,416)):
            pixels,recipe=iris_retarget(hd[:,left*4:right*4],guide[:,left:right])
            pixels,background=rebuild_background(pixels,guide[:,left:right],shiny,palettes)
            recipe['background']=background
            recipe['background_palette_references']={str(key):value for key,value in palette_references.items()}
            output[:,left*4:right*4]=pixels;recipes.append(recipe)
        path=HERE/'material-studies/eyes-analytic'/target['native_key']
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(_png((1664,256),output.tobytes()))
        tiles.extend((('native Speed '+str(shiny),Image.fromarray(guide)),('authored HD '+str(shiny),Image.fromarray(output))))
        reports.append({'target':target['native_key'],'source_hd':loaded.metadata,'recipes':recipes,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'background_lighting_pending':False,'review_only':True,'GPU_verified':False})
    board=Image.new('RGB',(1040,4*200),'#ddd');draw=ImageDraw.Draw(board)
    for i,(label,image) in enumerate(tiles):
        draw.text((0,i*200),label,fill='black')
        image.thumbnail((1040,165))
        board.paste(image,(0,i*200+25))
    board.save(HERE/'deoxys-eye-analytic-study.png')
    (HERE/'deoxys-eye-analytic-study.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':
    main()
