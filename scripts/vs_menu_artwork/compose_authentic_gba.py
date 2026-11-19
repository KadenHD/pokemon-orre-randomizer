"""Use the genuine GBA photo with one uniform scale and a rigid rotation."""

import os
from pathlib import Path
import hashlib
import json
import math
from PIL import Image, ImageDraw

HERE = Path(os.environ['VS_WORKDIR']).resolve()
path=Path(os.environ['VS_GBA_PHOTO'])
payload=path.read_bytes()
assert hashlib.sha256(payload).hexdigest()=='67bfde0165b6daa1edc9b1a9efd36756fffdd584c8969b421682a7473d791789'
with Image.open(path) as image:
    source=image.convert('RGBA');assert source.size==(960,663)
    rotated=source.convert('RGBa').rotate(17,Image.Resampling.BICUBIC,expand=True)
    factor=.36
    size=(math.ceil(rotated.width*factor),math.ceil(rotated.height*factor))
    # One shared affine scalar, with canvas padding from ceil. No independent
    # width/height fitting, perspective warp, recoloring or screen replacement.
    photograph=rotated.transform(size,Image.Transform.AFFINE,(1/factor,0,0,0,1/factor,0),resample=Image.Resampling.BICUBIC).convert('RGBA')
box=photograph.getbbox()
left=round(440-(box[0]+box[2])/2)
top=round(256-(box[1]+box[3])/2)
wire=Image.new('RGBA',(864*4,472*4),(0,0,0,0))
draw=ImageDraw.Draw(wire)
draw.line([(440*4,-8*4),(440*4,(top+box[1]+12)*4)],fill=(134,138,143,255),width=5*4)
wire=wire.convert('RGBa').resize((864,472),Image.Resampling.LANCZOS).convert('RGBA')
outputs=[]
for kind,input_name in [('composite','gba-clean-background-render.png'),('foreground','gba-clean-foreground-render.png')]:
    with Image.open(HERE/input_name) as image:base=image.convert('RGBA')
    base=Image.alpha_composite(base,wire)
    base.alpha_composite(photograph,(left,top))
    output=HERE/('gba-scene-'+kind+'-authentic-review.png')
    base.save(output)
    outputs.append({'file':output.name,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
reference=json.loads((HERE/'genuine-gba-reference.json').read_text())
reference={key:reference[key] for key in ('source_page','source_page_oldid','author','photograph_date',
            'png_uploader','license','source_original','downloaded_official_thumbnail')}
receipt={'review_only':True,'manual_gba_geometry_rejected':True,
         'reference':reference,'source_sha256':hashlib.sha256(payload).hexdigest(),
         'no_tint_or_recolour':True,'no_screen_changes':True,'original_alpha_preserved':True,
         'rigid_rotation_degrees_ccw':17,'uniform_scale':factor,'single_affine_scalar':True,
         'resampling':'premultiplied RGBa bicubic rigid rotation then uniform affine reduction',
         'transformed_image_dimensions':list(photograph.size),'placement':[left,top],
         'projected_photo_alpha_box':[left+box[0],top+box[1],left+box[2],top+box[3]],
         'link_cable':'separate authored five-pixel gray cable, behind authentic photograph',
         'source_photo_unchanged':hashlib.sha256(path.read_bytes()).hexdigest()==hashlib.sha256(payload).hexdigest(),
         'material_coverage':'authentic hardware photo; four source-mesh characters, three retain native materials',
         'outputs':outputs,'owned_Blender_closed':json.loads((HERE/'blender-run.json').read_text())['owned_closed']}
(HERE/'authentic-gba-provenance.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
