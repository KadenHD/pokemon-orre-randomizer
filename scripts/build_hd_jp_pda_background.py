"""Reproduce the Japanese P-AD layout from its registered genuine HD donor.

Supply the pinned XD pack's Textures directory. Caption outlines are added later
by render_hd_menu_atlases.py. This tool needs no ROM, native bitmap or save.
"""
from pathlib import Path
import argparse,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from orre_randomizer.hd_menu_catalog import menu_recipes
from orre_randomizer.hd_images import load_texture
from orre_randomizer.hd_menu_atlases import _pixel_bytes

TARGET='tex1_446x220_f660a60c5992b936_8110c51933687b97_9.png'
def pixels(box):return tuple(v*4 for v in box)

def reproduce(pack:Path,output:Path):
    record=menu_recipes('GXXJ01')[TARGET];source=record['transform']['author_source']
    name=source['source_file']
    if Path(name).name!=name or output.exists():raise ValueError('Use a registered donor and new output path')
    path=pack/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=source['source_sha256']:
        raise ValueError('The pinned P-AD image donor changed')
    loaded=load_texture(path,expected_native_size=(512,230))
    donor=Image.frombytes('RGBA',(loaded.image.width(),loaded.image.height()),_pixel_bytes(loaded.image))
    if donor.size!=(2048,920):raise ValueError('Unexpected genuine HD P-AD size')
    width,height=record['source_native_dimensions'];image=donor.crop((0,0,width*4,height*4))
    for box in source['clear_regions_native']:image.paste((0,0,0,0),pixels(box))
    for step in source['placements']:
        target=step['destination_native']
        if 'source_native'in step:
            tile=donor.crop(pixels(step['source_native']))
            if tile.size!=((target[2]-target[0])*4,(target[3]-target[1])*4):
                raise ValueError('An exact-scale component changed dimensions')
        else:
            tile=donor.crop(tuple(step['source_HD_box']))
            tile=tile.resize(((target[2]-target[0])*4,(target[3]-target[1])*4),Image.Resampling.LANCZOS)
        image.paste(tile,pixels(target)[:2])
    output.parent.mkdir(parents=True,exist_ok=True);image.save(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    if digest!=record['source_sha256']:raise ValueError('Reproduced P-AD background differs')
    return{'sha256':digest,'native_bitmap_resampled':False,'exact_registered_background':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(reproduce(args.pack,args.output),indent=2))
if __name__=='__main__':main()
