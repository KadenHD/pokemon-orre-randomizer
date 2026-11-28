"""Pack locally reviewed artwork. Never include complete donor or variant models."""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image

from orre_randomizer.artwork import _png
from orre_randomizer.deoxys_resources import convert_deoxys_model
from orre_randomizer.hd_overlays import _pkx_dat
from orre_randomizer.legendary_shadow_assets import STEMS, VERSION


def material_recipe(donor, recolored, *, xd):
    dat = _pkx_dat(donor, xd)
    insertion = len(donor) - len(dat) + 32 + struct.unpack_from('>I', dat, 4)[0]
    added = len(recolored) - len(donor)
    if added <= 0 or added % 32:
        raise ValueError('the reviewed model must add aligned GX textures')
    texture = recolored[insertion:insertion + added]
    changed = recolored[:insertion] + recolored[insertion + added:]
    patches = []
    start = end = -1
    for position, (before, after) in enumerate(zip(donor, changed, strict=True)):
        if before == after:
            continue
        if start == -1 or position - end > 5 or position == insertion or position - start == 0xffff:
            if start != -1:
                patches.append((start, changed[start:end + 1]))
            start = position
        end = position
    if start != -1:
        patches.append((start, changed[start:end + 1]))
    return (struct.pack('>III', insertion, added, len(patches))
            + b''.join(struct.pack('>IH', offset, len(change)) + change for offset, change in patches)
            + texture)


def build(review: Path, output: Path, hd: Path | None = None):
    assets = review / 'qualified-assets'
    entries = {}
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        def add(name, data):
            archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED, compresslevel=9)

        for game, folder in (('colosseum', 'colosseum-sources'), ('xd', 'sources')):
            for stem in STEMS:
                source = review / folder / f'{stem}.pkx'
                if game == 'colosseum' and stem.startswith('386-'):
                    donor = convert_deoxys_model((review / 'sources' / f'{stem}.pkx').read_bytes(),
                                                (review / folder / '386.pkx').read_bytes(),
                                                form=stem[4:], shiny=False)
                else:
                    donor = source.read_bytes()
                for variant in ('shadow', 'shiny'):
                    key = f'{game}-{stem}-{variant}'
                    model = (review / 'native-prototypes' / f'{key}.pkx').read_bytes()
                    add(key + '.materials', material_recipe(donor, model, xd=game == 'xd'))
                    entries[key] = {'donor': sha256(donor).hexdigest(), 'model': sha256(model).hexdigest()}
                    for size in (42, 168):
                        name = f'{key}-portrait-{size}.png'
                        add(name, (assets / name).read_bytes())
                    if game == 'xd' or variant == 'shadow':
                        name = (key if game == 'xd' else f'{game}-{stem}') + '-face.bin'
                        add(name, (assets / name).read_bytes())
                    if game == 'colosseum':
                        for size in (64, 256):
                            name = f'{stem}-{variant}-dna-{size}.png'
                            if size == 64:
                                with Image.open(assets / name) as image:
                                    add(name, _png((64, 64), image.convert('RGBA').tobytes()))
                            else:
                                add(name, (assets / name).read_bytes())
        add('manifest.json', json.dumps({'version': VERSION, 'entries': entries}, sort_keys=True))
        if hd is not None:
            seen = set()
            for game in ('colosseum', 'xd'):
                materials = {}
                for variant in ('shadow', 'shiny'):
                    folder = hd / f'{game}-{variant}'
                    rows = json.loads((folder / 'materials.json').read_text('utf8'))
                    for row in rows:
                        if 'target' not in row:
                            continue
                        key = row['target']
                        png = (folder / key).read_bytes()
                        digest = sha256(png).hexdigest()
                        if key in materials and materials[key]['image_sha256'] != digest:
                            if (key == 'tex1_8x8_b3246dccb53fcc35_6.png'
                                    and row['species'] == '379' and row['original'] == materials[key]['original']):
                                # Both Registeel variants share this native detail.
                                materials[key]['shared_native_material'] = True
                                continue
                            raise ValueError('Conflicting x4 color assignments for the same runtime texture')
                        materials[key] = {k: row[k] for k in ('donor', 'donor_sha256', 'original')}
                        materials[key]['image_sha256'] = digest
                        if digest not in seen:
                            add(f'hd/{digest}.png', png)
                            seen.add(digest)
                add(f'hd/{game}.json', json.dumps(materials, sort_keys=True))


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--hd', type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='legendary-artwork-', dir=args.output.parent) as folder:
        candidate = Path(folder) / args.output.name
        build(args.review, candidate, args.hd)
        candidate.replace(args.output)
