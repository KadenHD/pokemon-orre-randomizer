"""Pin real HD donors to each model's exact image/TLUT descriptor pair."""

import os
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(os.environ['VS_WORKDIR']).resolve()
ROOT = Path(os.environ['VS_PROJECT_ROOT']).resolve()
sys.path.insert(0, str(ROOT))
from orre_randomizer.hd_overlays import _Texture, _size, _texture_key, _walk_materials
from orre_randomizer.hd_images import resolve_texture, load_texture
from orre_randomizer.artwork import _png
from PySide6.QtGui import QImage


def pairs(raw):
    length, data_size, count, exports, imports = struct.unpack_from('>5I', raw)
    assert length == len(raw) and imports == 0
    data = raw[32:32+data_size]
    relocation_at = 32+data_size
    reloc = set(struct.unpack_from(f'>{count}I', raw, relocation_at))
    symbols = relocation_at + count*4
    names = symbols + exports*8
    scene, = [p for p,n in struct.iter_unpack('>II',raw[symbols:names])
              if raw[names+n:].split(b'\0',1)[0] == b'scene_data']
    u32 = lambda at:struct.unpack_from('>I',data,at)[0]
    table = u32(scene)
    images, palettes = set(), set()
    for index in range(64):
        model = u32(table+4*index)
        if not model:break
        ii,pp,_ = _walk_materials(data,reloc,model)
        images.update(ii);palettes.update(pp)
    for image in sorted(images):
        start,w,h,fmt,mipmap,_,max_lod = struct.unpack_from('>IHHIIff',data,image)
        samples = data[start:start+_size(w,h,fmt)]
        if fmt not in (8,9,10):
            yield image,0,_Texture(w,h,fmt,samples,mipmaps=bool(mipmap))
            continue
        direct = {u32(slot+4) for slot in reloc if u32(slot)==image
                  and slot+4 in reloc and u32(slot+4) in palettes}
        for palette in sorted(direct or palettes):
            pointer,kind,_,entries = struct.unpack_from('>IIIH',data,palette)
            required={8:16,9:256,10:16384}[fmt]
            assert 0<entries<=required
            words=data[pointer:pointer+entries*2]+bytes((required-entries)*2)
            yield image,palette,_Texture(w,h,fmt,samples,words,kind,bool(mipmap))


def main():
    output=HERE/'hd-textures';output.mkdir(exist_ok=True)
    result={}
    for name in ('rinto_0100','trainer_f_0100','gba_fl_f_0100','gba_fl_m_0100','gba_emr_f_0100','gba_emr_m_0100'):
        mapping={}
        raw=(HERE/'models'/f'{name}.dat').read_bytes()
        for image,palette,tex in pairs(raw):
            key=_texture_key(tex)
            metadata=None
            for version in ('xd-1.0','colosseum-2.00'):
                root=Path(os.environ['VS_XD_PACK'] if version=='xd-1.0' else os.environ['VS_COLO_PACK'])
                root=root/'Textures' if (root/'Textures').is_dir() else root
                try:
                    loaded=load_texture(resolve_texture(root,key),expected_native_size=(tex.width,tex.height))
                except FileNotFoundError:continue
                rgba=loaded.image.convertToFormat(QImage.Format.Format_RGBA8888)
                assert rgba.bytesPerLine()==rgba.width()*4
                png=_png((rgba.width(),rgba.height()),bytes(rgba.constBits()))
                target=output/key
                if target.exists():assert target.read_bytes()==png
                else:target.write_bytes(png)
                metadata={'key':key,'pack':version,**loaded.metadata,
                          'decoded_png':str(target.relative_to(HERE)),
                          'decoded_png_sha256':hashlib.sha256(png).hexdigest()}
                break
            mapping[f'{image}:{palette}']={'native_key':key,'native_size':[tex.width,tex.height],'hd':metadata}
        result[name]=mapping
    (HERE/'material-map.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({name:{'descriptor_pairs':len(mapping),'HD':sum(bool(x['hd']) for x in mapping.values())} for name,mapping in result.items()},indent=2))

if __name__=='__main__':main()
