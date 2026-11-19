"""Authored vector/analytic form materials using genuine Deoxys HD palettes.

UV outlines and low-order lighting are reconstructed from original form guides;
neither a native colour bitmap nor a filtered enlargement is an output layer.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
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


def rows(form,shiny):
    return [t for m in INVENTORY['pkx_deoxys_'+form+('_c' if shiny else '')+'.fsys']['members'] for t in m.get('textures',[])]


def native(row):
    return np.asarray(Image.open(STUDY/row['png']).convert('RGBA'))


def classes(rgb,shiny=False):
    data=rgb.astype(float);r,g,b=np.moveaxis(data,-1,0)
    result=np.zeros(r.shape,dtype='uint8')
    result[(r>g+20)&(r>b+20) if not shiny else (r>b+25)&(g>b+15)]=1
    result[(g>r+20)&(b>r+20)]=2
    result[(b>g+20)&(r>g+15)]=3
    result[(b>g+35)&(b>r+25)&(r+10>g*.75)]=3
    result[(data.max(2)<65)&(data.max(2)-data.min(2)<25)]=4
    return result


def rdp(points,tolerance=.45):
    if len(points)<3:
        return points
    start,end=np.array(points[0]),np.array(points[-1])
    delta=end-start
    if not np.dot(delta,delta):
        distances=np.linalg.norm(np.array(points)-start,axis=1)
    else:
        t=np.clip(((np.array(points)-start)@delta)/np.dot(delta,delta),0,1)
        distances=np.linalg.norm(np.array(points)-(start+t[:,None]*delta),axis=1)
    pivot=int(distances.argmax())
    if distances[pivot]<=tolerance:
        return [points[0],points[-1]]
    return rdp(points[:pivot+1],tolerance)[:-1]+rdp(points[pivot:],tolerance)


def polygons(mask):
    """Trace oriented pixel-cell boundaries, then fit simplified UV polylines."""
    height,width=mask.shape;edges={}
    def edge(a,b):
        edges.setdefault(a,[]).append(b)
    for y,x in zip(*np.nonzero(mask)):
        x,y=int(x),int(y)
        if y==0 or not mask[y-1,x]:edge((x,y),(x+1,y))
        if x==width-1 or not mask[y,x+1]:edge((x+1,y),(x+1,y+1))
        if y==height-1 or not mask[y+1,x]:edge((x+1,y+1),(x,y+1))
        if x==0 or not mask[y,x-1]:edge((x,y+1),(x,y))
    result=[]
    while edges:
        start=next(iter(edges));points=[start];at=start
        while True:
            after=edges[at].pop()
            if not edges[at]:del edges[at]
            points.append(after);at=after
            if at==start:break
        if len(points)>=5:
            # Split the closed loop at its farthest vertex before simplification.
            pivot=int(np.linalg.norm(np.array(points)-points[0],axis=1).argmax())
            simple=rdp(points[:pivot+1],.7)[:-1]+rdp(points[pivot:],.7)
            rounded=[]
            for index,a in enumerate(simple[:-1]):
                b=simple[(index+1)%(len(simple)-1)]
                previous=simple[(index-1)%(len(simple)-1)]
                incoming=np.array(a)-previous;outgoing=np.array(b)-a
                li,lo=np.linalg.norm(incoming),np.linalg.norm(outgoing)
                turn=np.dot(incoming,outgoing)/max(1e-8,li*lo)
                if a[0] in (0,width) or a[1] in (0,height) or turn<.5:
                    rounded.append(a)
                else:
                    left=np.array(a)-incoming*min(.2,.6/max(li,1e-8))
                    right=np.array(a)+outgoing*min(.2,.6/max(lo,1e-8))
                    rounded.extend((tuple(left),tuple(right)))
            simple=rounded+[rounded[0]]
            area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(simple,simple[1:]))/2
            if abs(area)>=.5:result.append((simple,area))
    return result


def vector_mask(mask,scale=4):
    height,width=mask.shape
    canvas=Image.new('L',(width*scale*2,height*scale*2))
    draw=ImageDraw.Draw(canvas)
    paths=polygons(mask)
    # Outer clockwise regions first; hole boundaries follow with zero fill.
    for points,area in sorted(paths,key=lambda item:abs(item[1]),reverse=True):
        draw.polygon([(x*scale*2,y*scale*2) for x,y in points],fill=255 if area>0 else 0)
    image=resize_uv_field(canvas,(width*scale,height*scale),Image.Resampling.LANCZOS)
    return np.asarray(image).astype(float)/255,paths


def resize_uv_field(image,size,resample):
    """Keep H-then-V quantization stable across Pillow11/13 optimization choices.

    The filters are separable, but their intermediate 8-bit rounding is not
    commutative. Pillow13 may choose V-then-H for tall inputs. The explicit
    passes preserve the reviewed material pixels and their GPU capture inputs.
    """
    width,height=size
    if image.width!=width:image=image.resize((width,image.height),resample)
    if image.height!=height:image=image.resize((image.width,height),resample)
    return image


def basis(x,y):
    return np.stack((np.ones_like(x),x,y,x*x,x*y,y*y,x**3,x*x*y,x*y*y,y**3,
                     np.exp(-((x-.5)**2+(y-.5)**2)/.08)),axis=2)


def boundary_distance(x,y,paths,width,height):
    distance=np.full(x.shape,float(max(width,height)))
    for points,_ in paths:
        for a,b in zip(points,points[1:]+points[:1]):
            if (a[0]==b[0] and a[0] in (0,width)) or (a[1]==b[1] and a[1] in (0,height)):
                continue
            dx,dy=b[0]-a[0],b[1]-a[1]
            length=dx*dx+dy*dy
            if not length:continue
            t=np.clip(((x-a[0])*dx+(y-a[1])*dy)/length,0,1)
            distance=np.minimum(distance,np.hypot(x-a[0]-t*dx,y-a[1]-t*dy))
    return distance


def boundary_fields(paths,width,height):
    canvas=Image.new('L',(width*4,height*4))
    draw=ImageDraw.Draw(canvas)
    for points,_ in paths:
        for a,b in zip(points,points[1:]+points[:1]):
            if (a[0]==b[0] and a[0] in (0,width)) or (a[1]==b[1] and a[1] in (0,height)):
                continue
            draw.line((a[0]*4,a[1]*4,b[0]*4,b[1]*4),fill=255,width=1)
    hd,native=[],[]
    for radius in (6,20):
        field=canvas.filter(ImageFilter.GaussianBlur(radius))
        maximum=max(field.getextrema()[1],1)
        hd.append(np.asarray(field).astype(float)/maximum)
        native.append(np.asarray(resize_uv_field(field,(width,height),Image.Resampling.BOX)).astype(float)/maximum)
    return np.stack(native,2),np.stack(hd,2)


def reference_palettes(shiny):
    choices={0:12,1:2,2:8,3:0,4:9}
    textures=rows('def',shiny);palettes={};references={}
    for label,index in choices.items():
        row=textures[index]
        loaded=load_texture(resolve_texture(PACK_ROOTS['xd']/'Textures',row['native_key']),expected_native_size=tuple(row['dimensions']))
        assert loaded.metadata['sha256']==row['hd']['xd']['sha256']
        pixels=np.array(Image.frombytes('RGBA',(loaded.image.width(),loaded.image.height()),bytes(loaded.image.constBits())))
        labels=classes(pixels[:,:,:3],shiny)
        selected=pixels[:,:,:3][(labels==label)&(pixels[:,:,3]>200)]
        if label==0:
            rgb=pixels[:,:,:3].astype(float)
            selected=pixels[:,:,:3][(rgb.max(2)-rgb.min(2)<35)&(rgb.mean(2)>60)&(rgb.mean(2)<180)]
        if label==4:
            selected=pixels[:,:,:3][pixels[:,:,:3].max(2)<35]
        if len(selected)<3:
            raise ValueError('HD reference does not identify material palette '+str(label))
        # A source palette, not a fit of native RGB triples.
        luminance=selected.mean(1)
        stops=np.quantile(luminance,[.05,.5,.95])
        colors=[]
        for stop in stops:
            order=np.argsort(np.abs(luminance-stop))[:max(3,len(selected)//25)]
            colors.append(np.median(selected[order],axis=0))
        palettes[label]=np.array(colors)
        references[label]=loaded.metadata
    return palettes,references


def apply_native_alpha_vector(result,guide,proof):
    if np.any(guide[:,:,3]!=255):
        mask=guide[:,:,3]>=128
        coverage,paths=vector_mask(mask)
        result[:,:,3]=(coverage*255).round().clip(0,255).astype('uint8')
        sampled=np.asarray(resize_uv_field(Image.fromarray(result[:,:,3]),(mask.shape[1],mask.shape[0]),Image.Resampling.BOX))>=128
        union=np.count_nonzero(sampled|mask)
        proof.append({'kind':'native UV alpha cutout reconstructed as simplified vector contours',
                      'paths':[{'points':points,'oriented_area':area} for points,area in paths],
                      'native_alpha_mask_iou':float(np.count_nonzero(sampled&mask)/max(union,1)),
                      'native_rgb_bitmap_resampled':False})
    return result,proof


def distinct_lighting_stops(bounds,colors):
    """A flat dominant level maps to the median palette, never a false highlight.

    Quantiles can coincide when a UV plate is largely constant. np.interp with
    duplicate coordinates selects the last colour, turning compression-level
    differences into a bright rectangular patch. Prefer the physical median
    anchor for a coincident group and retain the other genuinely distinct stops.
    """
    levels=[];selected=[]
    for value in bounds:
        if levels and abs(value-levels[-1])<1e-7:
            continue
        indices=[index for index,other in enumerate(bounds) if abs(value-other)<1e-7]
        anchor=min(indices,key=lambda index:abs(index-1))
        levels.append(float(value));selected.append(colors[anchor])
    return np.array(levels),np.array(selected)


def construct(guide,shiny,palettes,*,allow_analytic_rgb_ramp=True):
    rgb=guide[:,:,:3].astype(float);labels=classes(rgb,shiny)
    height,width=labels.shape;yy,xx=np.mgrid[:height,:width]
    columns=np.median(rgb,axis=1)
    if allow_analytic_rgb_ramp and np.mean(np.abs(rgb-columns[:,None,:]))<2.5:
        v=(np.arange(height)+.5)/height
        coefficients=[np.polynomial.polynomial.polyfit(v,columns[:,channel],min(5,height-1)) for channel in range(3)]
        lighting=np.column_stack([np.polynomial.polynomial.polyval((np.arange(height*4)+.5)/(height*4),coef) for coef in coefficients])
        result=np.full((height*4,width*4,4),255,dtype='uint8')
        result[:,:,:3]=lighting[:,None,:].round().clip(0,255).astype('uint8')
        return apply_native_alpha_vector(result,guide,[{'kind':'continuous analytic one-dimensional material colour function',
                       'native_UV_guide_only':True,'rgb_coefficients':[coef.tolist() for coef in coefficients],
                       'native_bitmap_resampled':False,'painted_bitmap_detail_claimed':False}])
    native_basis=basis((xx+.5)/width,(yy+.5)/height)
    hy,hx=np.mgrid[:height*4,:width*4]
    hd_basis=basis((hx+.5)/(width*4),(hy+.5)/(height*4))
    output=np.zeros((height*4,width*4,3));total=np.zeros((height*4,width*4));proof=[]
    for label in sorted(np.unique(labels).tolist()):
        mask=labels==label
        if mask.sum()<2:continue
        coverage,paths=vector_mask(mask)
        luma=rgb.mean(2)[mask]
        bounds=np.quantile(luma,[.05,.5,.95])
        if label==4:
            colors=np.array([[0.,0.,0.],[2.,2.,3.],[12.,12.,14.]])
        else:
            colors=palettes[label]
        effective_bounds,effective_colors=distinct_lighting_stops(bounds,colors)
        if bounds[-1]-bounds[0]<3:
            paint=np.broadcast_to(colors[1],output.shape)
            error=0.;coefficients=[]
        else:
            native_edges,hd_edges=boundary_fields(paths,width,height)
            native_lighting=np.concatenate((native_basis,native_edges),axis=2)
            hd_lighting=np.concatenate((hd_basis,hd_edges),axis=2)
            coefficients=np.linalg.lstsq(native_lighting[mask],luma,rcond=None)[0]
            reconstructed=native_lighting[mask]@coefficients
            lighting=(hd_lighting@coefficients).clip(luma.min(),luma.max())
            if label in (0,1):
                paint=colors[1]*np.clip(lighting/np.median(luma),.15,1.4)[:,:,None]
            else:
                paint=np.stack([np.interp(lighting,effective_bounds,effective_colors[:,channel]) for channel in range(3)],axis=2)
            error=float(np.abs(reconstructed-luma).mean())
        output+=paint*coverage[:,:,None];total+=coverage
        proof.append({'class':label,'native_uv_paths':[{'points':p,'oriented_area':a} for p,a in paths],
                      'source_hd_palette':colors.tolist(),'native_lighting_stops':bounds.tolist(),
                      'effective_native_lighting_stops':effective_bounds.tolist(),
                      'effective_hd_palette':effective_colors.tolist(),
                      'lighting_coefficients':list(coefficients),'native_lighting_mae':error})
    result=np.full((height*4,width*4,4),255,dtype='uint8')
    result[:,:,:3]=(output/np.maximum(total[:,:,None],1e-5)).round().clip(0,255).astype('uint8')
    return apply_native_alpha_vector(result,guide,proof)


def main():
    reports=[];tiles=[];shared={}
    eye_tps={r['target']:r for r in json.loads((HERE/'deoxys-eye-uv-study.json').read_text())}
    eye_analytic={r['target']:r for r in json.loads((HERE/'deoxys-eye-analytic-study.json').read_text())}
    for shiny in (False,True):
        palettes,references=reference_palettes(shiny)
        for form in ('atk','sp'):
            folder=HERE/'deoxys-authored'/(form+('-shiny' if shiny else '-normal'));folder.mkdir(parents=True,exist_ok=True)
            for i,row in enumerate(rows(form,shiny)):
                if row['hd']:continue
                target=native(row)
                native_sha=hashlib.sha256(target.tobytes()).hexdigest()
                if row['native_key'] in shared:
                    previous=shared[row['native_key']]
                    assert previous['native_sha']==native_sha
                    payload,output,reference=previous['payload'],previous['output'],previous['reference']
                    recipe={**previous['recipe'],'normal_shiny_share_exact_native_texture_identity':True}
                elif row['dimensions']==[416,64]:
                    eye=(eye_tps if form=='atk' else eye_analytic)[row['native_key']]
                    parent=HERE/'material-studies'/('eyes' if form=='atk' else 'eyes-analytic')
                    payload=(parent/row['native_key']).read_bytes()
                    assert hashlib.sha256(payload).hexdigest()==eye['sha256']
                    recipe={'kind':'HD eye component/UV retarget','eye_receipt':eye}
                    output=np.asarray(Image.open(parent/row['native_key']).convert('RGBA'))
                    reference=eye['source_hd']
                else:
                    output,paths=construct(target,shiny,palettes)
                    payload=_png((output.shape[1],output.shape[0]),output.tobytes())
                    recipe={'kind':'vector UV material reconstruction with genuine HD class palettes',
                            'components':paths,'source_hd_references':list(references.values())}
                    reference=references[1]
                shared[row['native_key']]={'native_sha':native_sha,'payload':payload,'output':output,
                                          'reference':reference,'recipe':recipe}
                path=folder/row['native_key'];path.write_bytes(payload)
                reports.append({'target':row['native_key'],'form':form,'shiny':shiny,
                    'sha256':hashlib.sha256(payload).hexdigest(),'dimensions':[output.shape[1],output.shape[0]],
                    'kind':'authored-pack-derived-material','reference':reference,'recipe':recipe,
                    'native_bitmap_resampled':False,'review_only':True,'GPU_verified':False})
                if i not in (5,13):
                    tiles.extend(((form+' '+str(shiny)+' #'+str(i)+' native',Image.fromarray(target)),
                                  (form+' '+str(shiny)+' #'+str(i)+' authored HD',Image.fromarray(output))))
    (HERE/'deoxys-authored/materials.json').write_text(json.dumps(reports,indent=2)+'\n')
    board=Image.new('RGB',(8*150,((len(tiles)+7)//8)*180),'#ddd');draw=ImageDraw.Draw(board)
    for i,(label,im) in enumerate(tiles):
        x,y=(i%8)*150,(i//8)*180;draw.text((x+2,y+2),label,fill='black')
        im.thumbnail((140,150));board.paste(im,(x+2,y+20))
    board.save(HERE/'deoxys-authored/material-review.png')
    print('Authored',len(reports),'Deoxys material candidates; GPU and visual review pending.')


if __name__=='__main__':main()
