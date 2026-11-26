"""Render new type badges from pinned vector outlines, separately at native and x4."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION
from orre_randomizer.artwork import _png
from orre_randomizer.fairy_badges import LANGUAGES, SIZES, SMALL_SIZE, VERSION, badge_name
from orre_randomizer.fairy_data import type_name, DATA_SHA256
from orre_randomizer.hd_text_vectors import FONT_SHA256

ABBREVIATIONS = {'en': 'Fa', 'fr': 'Fé', 'de': 'Fe', 'es': 'Ha', 'it': 'Fo', 'ja': 'フェ'}


def render(game, language, *, small=False, scale=1):
    if PILLOW_VERSION.split('.')[0] != '13':
        raise ValueError('Use the pinned Pillow13 renderer')
    if game not in SIZES or language not in LANGUAGES or small and game != 'xd' or scale not in (1, 4):
        raise ValueError('Unsupported badge rendering')
    font_file = ROOT / 'orre_randomizer/assets/game/fonts/NotoSansJP.ttf'
    if hashlib.sha256(font_file.read_bytes()).hexdigest() != FONT_SHA256:
        raise ValueError('Pinned vector font changed')
    width, height = SMALL_SIZE if small else SIZES[game]
    # Rasterize vector geometry at a separate high-resolution target in both modes.
    factor = scale * 4
    image = Image.new('RGBA', (width * factor, height * factor))
    draw = ImageDraw.Draw(image)
    radius = (2 if small else height / 2 - .5) * factor
    shape = (factor / 2, factor / 2, width * factor - factor / 2 - 1, height * factor - factor / 2 - 1)
    draw.rounded_rectangle(shape, radius, fill='#513442' if game == 'xd' else '#4b4f52')
    inset = 1 if game == 'xd' else 2
    bounds = (inset * factor, inset * factor, (width - inset) * factor - 1, (height - inset) * factor - 1)
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).rounded_rectangle(bounds, max(1, radius - inset * factor), fill=255)
    fill = Image.new('RGBA', image.size)
    gradient = ImageDraw.Draw(fill)
    for y in range(height * factor):
        t = y / max(1, height * factor - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip((249, 187, 207), (221, 137, 171))) + (255,)
        gradient.line((0, y, width * factor - 1, y), fill=color)
    image.paste(fill, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    if game == 'colosseum':
        draw.rounded_rectangle(shape, radius, outline='#cbd1d4', width=factor)
    label = ABBREVIATIONS[language] if small else type_name(language, uppercase=True)
    stroke = factor if game == 'colosseum' else 0
    font_size = (height - (8 if game == 'colosseum' else 5)) * factor
    margin = (3 if small else 5) * factor
    while font_size >= 5 * factor:
        font = ImageFont.truetype(str(font_file), font_size)
        font.set_variation_by_axes([700])
        box = draw.textbbox((0, 0), label, font=font, stroke_width=stroke)
        if box[2] - box[0] <= image.width - margin * 2 and box[3] - box[1] <= image.height - 4 * factor:
            break
        font_size -= 1
    else:
        raise ValueError('Badge label does not fit: ' + label)
    origin = ((image.width - (box[2] - box[0])) / 2 - box[0],
              (image.height - (box[3] - box[1])) / 2 - box[1])
    draw.text(origin, label, font=font, fill='#ffffff' if game == 'colosseum' else '#151015',
              stroke_width=stroke, stroke_fill='#353238')
    image = image.resize((width * scale, height * scale), Image.Resampling.LANCZOS)
    return image, label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        parser.error('Use an owned output directory inside the project')
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for game in SIZES:
        for language in LANGUAGES:
            for small in ((False, True) if game == 'xd' else (False,)):
                for hd in (False, True):
                    image, label = render(game, language, small=small, scale=4 if hd else 1)
                    name = badge_name(game, language, small=small, hd=hd)
                    target = output / name
                    if target.is_symlink():
                        raise ValueError('Linked badge output refused')
                    payload = _png(image.size, image.convert('RGBA').tobytes())
                    target.write_bytes(payload)
                    records[name] = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                                     'dimensions': list(image.size), 'label': label,
                                     'game': game, 'language': language, 'small': small, 'scale': 4 if hd else 1}
    manifest = {'schema': 1, 'version': VERSION, 'type_id': 19,
                'native_bitmap_upscaled_for_hd': False, 'font_sha256': FONT_SHA256,
                'reference_data_sha256': DATA_SHA256, 'recipe': 'scripts/build_fairy_badges.py',
                'style': 'New vector lettering and geometry following each native type badge layout',
                'files': records}
    (output / 'fairy-badges.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                            'utf-8', newline='\n')
    print(json.dumps({'files': len(records), 'output': str(output), 'vector_rendered_native_and_x4': True}))


if __name__ == '__main__':
    main()
