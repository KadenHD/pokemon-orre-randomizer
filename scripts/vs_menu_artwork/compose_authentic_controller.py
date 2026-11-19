"""Composite the approved authentic photo without tinting or axis stretching."""

import os
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw

HERE = Path(os.environ['VS_WORKDIR']).resolve()
ROOT = Path(os.environ['VS_PROJECT_ROOT']).resolve()
photo=Path(os.environ['VS_CONTROLLER_PHOTO'])
payload=photo.read_bytes()
expected='9bf8d0c7ba77ba048c5912814b38b005b0b4ba84b9d38c9fdd9284cd220dea63'
assert hashlib.sha256(payload).hexdigest()==expected
with Image.open(photo) as source:
    source=source.convert('RGBA')
    assert source.size==(1800,1400)
    # Exactly the same rational scale on both axes; original alpha retained.
    reduced=source.convert('RGBa').resize((288,224),Image.Resampling.LANCZOS).convert('RGBA')
    anchor_y=100
    row=[x for x in range(800,1100) if source.getpixel((x,anchor_y))[3]>=200]
    assert row and 10<max(row)-min(row)<150
    center=(min(row)+max(row))/2
    color=source.getpixel((round(center),anchor_y))
left,top=291,129
cable_x=left+center*.16
cable_width=(max(row)-min(row)+1)*.16
scale=4
wire=Image.new('RGBA',(864*scale,472*scale),(0,0,0,0))
draw=ImageDraw.Draw(wire)
end_y=top+anchor_y*.16+5
points=[(round((cable_x-2)*scale),-4*scale),(round(cable_x*scale),round(end_y*scale))]
draw.line(points,fill=(*color[:3],255),width=max(2,round(cable_width*scale)))
wire=wire.convert('RGBa').resize((864,472),Image.Resampling.LANCZOS).convert('RGBA')
outputs=[]
for kind,input_name in [('composite','controller-clean-background-render.png'),('foreground','controller-clean-foreground-render.png')]:
    with Image.open(HERE/input_name) as source:base=source.convert('RGBA')
    base=Image.alpha_composite(base,wire)
    base.alpha_composite(reduced,(left,top))
    output=HERE/('controller-scene-'+kind+'-authentic-review.png')
    base.save(output)
    outputs.append({'file':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size})
receipt={'review_only':True,'manual_controller_geometry_rejected':True,
         'source_file':'assets/app/controller.png','source_sha256':expected,
         'source_url':'https://commons.wikimedia.org/wiki/File:GameCube_controller.png',
         'authors':['Evan-Amos','Alphathon'],'license':'CC-BY-SA-3.0',
         'license_url':'https://creativecommons.org/licenses/by-sa/3.0/',
         'source_dimensions':[1800,1400],'resized_dimensions':[288,224],
         'uniform_scale_numerator':4,'uniform_scale_denominator':25,
         'no_tint_or_recolour':True,'original_alpha_preserved':True,
         'resampling':'premultiplied RGBa Lanczos reduction',
         'placement':[left,top],'native_cable_extension':{'authored':True,'photo_anchor_row':anchor_y,'x':cable_x,'width':cable_width,'colour':list(color),'range_y':[0,end_y]},
         'composition_changes':'Uniform reduction, alpha composition over source-mesh characters and procedural flame background; separate cable extension to frame top.',
         'photo_derivative_contribution_license':'CC-BY-SA-3.0',
         'other_materials':'retain their own source rights; no license claim over game assets',
         'source_photo_unchanged':hashlib.sha256(photo.read_bytes()).hexdigest()==expected,
         'outputs':outputs,'owned_Blender_closed':json.loads((HERE/'blender-run.json').read_text())['owned_closed']}
(HERE/'authentic-controller-provenance.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
