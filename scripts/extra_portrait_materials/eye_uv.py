"""Retarget genuine HD Deoxys eyes using native UV landmarks, not RGB fitting."""
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


def masks(rgba):
    rgb=rgba[:,:,:3].astype(float)
    hi,lo=rgb.max(axis=2),rgb.min(axis=2)
    return {'black':(hi<90)&(hi-lo<35),'white':(lo>160)&(hi-lo<80)}


def features(mask):
    yy,xx=np.nonzero(mask)
    if not len(xx): return []
    result=[]
    rows=np.unique(yy)
    for f in np.linspace(0.,1.,11):
        y=int(rows[min(len(rows)-1,round(f*(len(rows)-1)))])
        xs=np.flatnonzero(mask[y]); result.extend(((float(xs.min()),float(y)),(float(xs.max()),float(y))))
    columns=np.unique(xx)
    for f in np.linspace(0.,1.,11):
        x=int(columns[min(len(columns)-1,round(f*(len(columns)-1)))])
        ys=np.flatnonzero(mask[:,x]);result.extend(((float(x),float(ys.min())),(float(x),float(ys.max()))))
    return result


def controls(source,target, *, white_only=False):
    s,t=[],[]
    for kind in (('white',) if white_only else ('black','white')):
        a,b=features(masks(source)[kind]),features(masks(target)[kind])
        if a and b:
            s.extend(a);t.extend(b)
    width=source.shape[1]
    s.extend(((0,0),(0,63),(width-1,63)));t.extend(((0,0),(0,63),(width-1,63)))
    grouped={}
    for a,b in zip(t,s):grouped.setdefault(a,[]).append(b)
    return np.array(list(grouped),float),np.array([np.mean(v,axis=0) for v in grouped.values()])


def tps_coefficients(target,source):
    target=target/64.
    rr=np.sum((target[:,None]-target[None,:])**2,axis=2)
    kernel=rr*np.log(np.maximum(rr,1e-12))
    affine=np.column_stack((np.ones(len(target)),target))
    lhs=np.block([[kernel+np.eye(len(target))*1e-5,affine],[affine.T,np.zeros((3,3))]])
    rhs=np.vstack((source,np.zeros((3,2))))
    return target,np.linalg.solve(lhs,rhs)


def map_points(points,target,coefficients):
    points=points/64.
    rr=np.sum((points[:,None]-target[None,:])**2,axis=2)
    kernel=rr*np.log(np.maximum(rr,1e-12))
    return np.column_stack((kernel,np.ones(len(points)),points))@coefficients


def sample(image,coordinates):
    x=np.clip(coordinates[:,0],0,image.shape[1]-1)
    y=np.clip(coordinates[:,1],0,image.shape[0]-1)
    x0,y0=x.astype(int),y.astype(int);x1=np.minimum(x0+1,image.shape[1]-1);y1=np.minimum(y0+1,image.shape[0]-1)
    tx,ty=(x-x0)[:,None],(y-y0)[:,None]
    return (image[y0,x0]*(1-tx)+image[y0,x1]*tx)*(1-ty)+(image[y1,x0]*(1-tx)+image[y1,x1]*tx)*ty


def iou(a,b):
    union=np.count_nonzero(a|b)
    return float(np.count_nonzero(a&b)/union) if union else 1.


def regions(image):
    labels=masks(image);mask=labels['black']|labels['white'];visited=np.zeros(mask.shape,bool);objects=[]
    for y,x in zip(*np.nonzero(mask)):
        if visited[y,x]:continue
        stack=[(y,x)];visited[y,x]=True;points=[]
        while stack:
            yy,xx=stack.pop();points.append((yy,xx))
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    a,b=yy+dy,xx+dx
                    if 0<=a<64 and 0<=b<416 and mask[a,b] and not visited[a,b]:
                        visited[a,b]=True;stack.append((a,b))
        if len(points)>20:
            objects.append((min(p[1] for p in points),max(p[1] for p in points),len(points)))
    objects=sorted(sorted(objects,key=lambda x:x[2],reverse=True)[:3])
    assert len(objects)==3,objects
    edges=[0]+[int((objects[i][1]+objects[i+1][0])//2) for i in range(2)]+[416]
    return list(zip(edges,edges[1:]))


def main():
    inventory=INVENTORY
    def eye(archive):
        return next(t for m in inventory[archive]['members'] for t in m.get('textures',[]) if t['dimensions']==[416,64])
    reports=[];tiles=[]
    for rare in (False,True):
        source=eye('pkx_deoxys_def'+('_c' if rare else '')+'.fsys')
        native_source=np.asarray(Image.open(STUDY/source['png']).convert('RGBA'))
        path=resolve_texture(PACK_ROOTS['xd']/'Textures',source['native_key'])
        loaded=load_texture(path,expected_native_size=(416,64))
        assert loaded.metadata['source_scale']==4 and loaded.metadata['sha256']==source['hd']['xd']['sha256']
        hd=np.array(Image.frombytes('RGBA',(1664,256),bytes(loaded.image.constBits())))
        for form in ('atk',):
            target=eye('pkx_deoxys_'+form+('_c' if rare else '')+'.fsys')
            native_target=np.asarray(Image.open(STUDY/target['png']).convert('RGBA'))
            atlas=np.empty_like(hd);frames=[]
            for frame,(left,right) in enumerate(regions(native_source)):
                width=right-left
                s=native_source[:,left:right]
                t=native_target[:,left:right]
                target_points,source_points=controls(s,t,white_only=form=='sp')
                fixed,coefficients=tps_coefficients(target_points,source_points)
                yy,xx=np.mgrid[:64,:width]
                native_coordinates=map_points(np.column_stack((xx.ravel(),yy.ravel())),fixed,coefficients)
                predicted=sample(s.astype(float),native_coordinates).reshape(64,width,4).round().clip(0,255).astype('uint8')
                eye_masks=masks(t);predicted_masks=masks(predicted)
                scores={kind:iou(eye_masks[kind],predicted_masks[kind]) for kind in eye_masks}
                yy,xx=np.mgrid[:256,:width*4]
                points=np.column_stack(((xx.ravel()+.5)/4-.5,(yy.ravel()+.5)/4-.5))
                hd_coordinates=map_points(points,fixed,coefficients)*4+1.5
                pixels=sample(hd[:,left*4:right*4].astype(float),hd_coordinates).reshape(256,width*4,4)
                pixels[:,:,3]=255
                rendered=pixels.round().clip(0,255).astype('uint8')
                atlas[:,left*4:right*4]=rendered
                frames.append({'pose_region':frame,'native_x_range':[left,right],'source_native_landmarks':source_points.tolist(),
                               'target_native_landmarks':target_points.tolist(),'mask_iou':scores})
                if frame==0:tiles.append((form+(' shiny' if rare else ' normal'),t,rendered,predicted))
            folder=HERE/'material-studies/eyes';folder.mkdir(parents=True,exist_ok=True)
            output=folder/target['native_key'];output.write_bytes(_png((1664,256),atlas.tobytes()))
            reports.append({'target':target['native_key'],'source':source['native_key'],'source_hd':loaded.metadata,
                            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'frames':frames,
                            'kind':'authored-hd-eye-uv-retarget-study','native_bitmap_resampled_for_hd':False,
                            'eye_texture_only':True,'background_lighting_not_yet_reconstructed':True,
                            'GPU_verified':False,'approved_for_publication':False})
    board=Image.new('RGB',(len(tiles)*240,370),'#ddd');draw=ImageDraw.Draw(board)
    for i,(label,native,hd,predicted) in enumerate(tiles):
        x=i*240;draw.text((x,0),label,fill='black')
        for j,(image,tag) in enumerate([(native,'native guide'),(predicted,'UV prediction'),(hd,'true HD donor warped')]):
            tile=Image.fromarray(image).resize((72,144),Image.Resampling.NEAREST if j<2 else Image.Resampling.LANCZOS)
            board.paste(tile,(x+j*78,25));draw.text((x+j*78,175),tag,fill='black')
    board.save(HERE/'deoxys-eye-uv-study.png')
    (HERE/'deoxys-eye-uv-study.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf8')
    for report in reports:print(report['target'],report['frames'][0]['mask_iou'])


if __name__=='__main__':main()
