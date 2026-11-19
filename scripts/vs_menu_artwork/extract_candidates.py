"""Read-only XD model extraction for the two VS illustration studies.

Private model/texture outputs only; no game image or upstream pack writes.
"""

import os
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT = Path(os.environ['VS_PROJECT_ROOT']).resolve()
HERE = Path(os.environ['VS_WORKDIR']).resolve()
sys.path.insert(0, str(ROOT))
from orre_randomizer.engine.analyze_game import parse_fsys
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.engine.survey_assets import fst_inventory
from orre_randomizer.hd_overlays import _dat_textures, _texture_key, _pixels
from orre_randomizer.hd_images import resolve_texture, load_texture
from orre_randomizer.artwork import _png


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    source = Path(os.environ['VS_SOURCE_ISO'])
    chosen = {'rinto_0100','trainer_f_0100','gba_fl_f_0100','gba_fl_m_0100','gba_emr_f_0100','gba_emr_m_0100'}
    chosen.update(sys.argv[1:])
    manifest = HERE/'candidate-models.json'
    if manifest.exists():
        chosen.update(row['member'] for row in json.loads(manifest.read_text())['models'])
    with source.open('rb') as stream:
        boot=stream.read(0x440);assert boot[:8]==b'GXXP01\0\0'
        offset,size=struct.unpack_from('>II',boot,0x424);stream.seek(offset);fst=stream.read(size)
        entries={r['path']:r for r in fst_inventory(fst)[0]}
        entry=entries['people_archive.fsys'];assert entry['size']<64*1024**2
        stream.seek(entry['disc_offset']);archive=stream.read(entry['size'])
        assert sha(archive)=='3da4a673c0b720db7a349c1d1dbca47110e08c6a269dace4ac913d446e75fa75'
    result={'source':'build/xd-validation/verified-eu.iso','source_access':'rb only',
        'game_id':'GXXP01','fst_sha256':sha(fst),'archive':'people_archive.fsys',
        'archive_sha256':sha(archive),'models':[], 'no_GPU_or_Dolphin_started':True,
        'identification':'Candidates until actual model geometry/material rendering is compared to the reference; no character name inferred from member alone'}
    output=HERE/'models';output.mkdir(exist_ok=True)
    textures=HERE/'native-textures';textures.mkdir(exist_ok=True)
    for member in parse_fsys(archive)['members']:
        if member['name'] not in chosen:continue
        raw=decoded_member(archive,member)
        assert struct.unpack_from('>I',raw)[0]==len(raw)
        name=member['name']+'.dat';path=output/name
        if path.exists():assert path.read_bytes()==raw
        else:path.write_bytes(raw)
        row={'member':member['name'],'identifier':member['identifier_raw'],'bytes':len(raw),
             'sha256':sha(raw),'file':str(path.relative_to(HERE)),'textures':[]}
        for tex in _dat_textures(raw):
            key=_texture_key(tex);png=textures/key
            if not png.exists():png.write_bytes(_png((tex.width,tex.height),_pixels(tex)))
            hits={}
            for game,version in [('xd','xd-1.0'),('colosseum','colosseum-2.00')]:
                root=Path(os.environ['VS_XD_PACK'] if game=='xd' else os.environ['VS_COLO_PACK'])
                root=root/'Textures' if (root/'Textures').is_dir() else root
                try:
                    texture=load_texture(resolve_texture(root,key),expected_native_size=(tex.width,tex.height))
                except FileNotFoundError:continue
                hits[game]=texture.metadata
            row['textures'].append({'native_key':key,'native_size':[tex.width,tex.height],
                'native_rgba_sha256':sha(_pixels(tex)),'pack_donors':hits})
        result['models'].append(row)
    assert {r['member'] for r in result['models']}==chosen
    (HERE/'candidate-models.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'models':len(result['models']),'bytes':sum(r['bytes'] for r in result['models']),
        'textures':[{'model':r['member'],'count':len(r['textures']),'with_pack':sum(bool(t['pack_donors']) for t in r['textures'])} for r in result['models']]},indent=2))


if __name__=='__main__':main()
