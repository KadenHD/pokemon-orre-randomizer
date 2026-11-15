"""Fit native pre-tint RGBA model captures to the DNA keypad's whole-body size.

Inputs are untouched 256px menuModelRender captures and the guarded reader's
sibling .export.json evidence. No model, color, pose or texture is synthesized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer.artwork import _png, _png_pixels


def fit_body(path: Path, shiny: bool) -> tuple[bytes, dict]:
    payload = path.read_bytes()
    source = _png_pixels(payload, (256, 256))
    evidence = json.loads(path.with_suffix('.export.json').read_text('utf-8'))
    pid, owner = int(evidence['PID'], 16), int(evidence['owner'], 16)
    observed = ((pid >> 16) ^ (pid & 65535) ^ (owner >> 16) ^ (owner & 65535)) < 8
    if (evidence['species'] != 249 or not 1 <= evidence['shadow'] <= 96
            or evidence['dimensions'] != [256, 256] or observed is not shiny
            or hashlib.sha256(source).hexdigest() != evidence['RGBA_sha256']):
        raise ValueError('the guarded native capture does not match the requested model')
    opaque = [index for index in range(256 * 256) if source[index * 4 + 3]]
    if not opaque: raise ValueError('the native framebuffer is empty')
    left, right = min(index % 256 for index in opaque), max(index % 256 for index in opaque) + 1
    top, bottom = min(index // 256 for index in opaque), max(index // 256 for index in opaque) + 1
    if min(left, top, 256 - right, 256 - bottom) < 3:
        raise ValueError('the native capture clips the silhouette; choose another frame')
    width, height = right - left, bottom - top
    scale = 56 / max(width, height)
    fit_width, fit_height = round(width * scale), round(height * scale)
    xpad, ypad = (64 - fit_width) // 2, (64 - fit_height) // 2
    result = bytearray(64 * 64 * 4)
    # Area filtering in premultiplied-alpha space preserves the native colors
    # and clean silhouette without adding a matte or sharpening outlines.
    for y in range(fit_height):
        y0, y1 = top + y * height / fit_height, top + (y + 1) * height / fit_height
        for x in range(fit_width):
            x0, x1 = left + x * width / fit_width, left + (x + 1) * width / fit_width
            sums, alpha, weight = [0., 0., 0.], 0., 0.
            for sy in range(math.floor(y0), math.ceil(y1)):
                for sx in range(math.floor(x0), math.ceil(x1)):
                    w = (min(x1, sx + 1) - max(x0, sx)) * (min(y1, sy + 1) - max(y0, sy))
                    at = (sy * 256 + sx) * 4
                    a = source[at + 3]
                    weight += w
                    alpha += a * w
                    for channel in range(3): sums[channel] += source[at + channel] * a * w
            out = ((y + ypad) * 64 + x + xpad) * 4
            if alpha:
                result[out:out + 4] = bytes([min(255, round(value / alpha)) for value in sums]
                                            + [min(255, round(alpha / weight))])
    output = _png((64, 64), bytes(result))
    return output, {'shiny': shiny, 'bytes': len(output),
        'sha256': hashlib.sha256(output).hexdigest(),
        'source_RGBA_sha256': evidence['RGBA_sha256'],
        'source_capture_sha256': hashlib.sha256(payload).hexdigest(),
        'source_alpha_bbox': [left, top, right, bottom],
        'fitted_dimensions': [fit_width, fit_height]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normal', type=Path, required=True)
    parser.add_argument('--shiny', type=Path, required=True)
    args = parser.parse_args()
    pack = ROOT / 'orre_randomizer/assets/game'
    models = pack / 'models'
    model_source = json.loads((models / 'manifest.json').read_text('utf-8'))
    manifest = {'version': 1, 'dimensions': [64, 64],
        'source_model': {'game_id': model_source['source']['game_id'],
            'archive': model_source['source']['archive'], 'member': model_source['source']['member'],
            'original_sha256': model_source['source']['model_sha256'],
            'colosseum_port_sha256': model_source['converted_sha256'],
            'shiny_port_sha256': model_source['shiny_variant']['generated_sha256']},
        'capture': 'Native Colosseum menuModelRender RGBA8 framebuffer before the DNA hologram tint, rendered in an isolated Dolphin instance. Whole-body mesh, textures, native lighting and red eyes retained. Purified display-only fixtures omit Shadow aura particles.',
        'conversion': 'Crop the complete transparent silhouette, fit within 56px without changing aspect ratio, area-filter premultiplied RGBA into a 64px transparent canvas. No recoloring or generated artwork.',
        'rights': 'Original game-derived resources, separate from the MIT code license. See THIRD_PARTY_NOTICES.md.',
        'files': {}}
    for path, shiny in ((args.normal, False), (args.shiny, True)):
        filename = 'dark-lugia-shiny-body.png' if shiny else 'dark-lugia-body.png'
        output, metadata = fit_body(path, shiny)
        (models / filename).write_bytes(output)
        manifest['files'][filename] = metadata
    (models / 'fullbody-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n',
                                                encoding='utf-8', newline='\n')
    provenance_path = pack / 'provenance.json'
    provenance = json.loads(provenance_path.read_text('utf-8'))
    for path in ([models / filename for filename in (*manifest['files'], 'fullbody-manifest.json')]
                 + [pack / 'README.md']):
        payload = path.read_bytes()
        provenance['files'][path.relative_to(pack).as_posix()] = {
            'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    provenance['shadow_lugia_body_metadata'] = 'models/fullbody-manifest.json'
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8', newline='\n')
    print(json.dumps(manifest['files'], indent=2))


if __name__ == '__main__': main()
