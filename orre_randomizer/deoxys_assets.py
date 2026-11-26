"""Authenticated native/x4 Deoxys imports and independently rendered artwork."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .artwork import _png, _png_pixels
from .deoxys_resources import FORMS, verify_xd_deoxys_model
from .engine.analyze_game import FormatError

VERSION = "colosseum-deoxys-native-hd-assets-v1"
_FILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,126}\.(png|pkx)\Z")


def asset_directory():
    from .resources import bundle_root
    return bundle_root() / 'models/deoxys'


def asset_manifest(directory=None):
    root = Path(directory) if directory is not None else asset_directory()
    path = root / 'deoxys-assets.json'
    if root.is_symlink() or root.is_junction() or path.is_symlink() or not path.is_file():
        raise FormatError('Deoxys resources are not registered')
    if path.stat().st_size > 1024 * 1024:
        raise FormatError('Deoxys resource registry exceeds its size limit')
    manifest = json.loads(path.read_text('utf-8'))
    if (not isinstance(manifest, dict) or manifest.get('schema') != 1
            or manifest.get('version') != VERSION or manifest.get('review_only') is not False
            or manifest.get('game') != 'colosseum' or not isinstance(manifest.get('files'), dict)
            or manifest.get('native_bitmap_upscaled_for_hd') is not False):
        raise FormatError('Deoxys resource registry is unqualified')
    expected = {f'{role}-{form}-{variant}-{scale}.png'
                for role in ('head', 'body') for form in FORMS
                for variant in ('normal', 'shiny') for scale in ('native', 'hd')}
    expected.update(f'xd-{form}-{variant}.pkx' for form in FORMS for variant in ('normal', 'shiny'))
    if set(manifest['files']) != expected:
        raise FormatError('Deoxys native/HD resource set is incomplete')
    return root, manifest


def _read(name, directory=None):
    root, manifest = asset_manifest(directory)
    if _FILE.fullmatch(name) is None or name not in manifest['files']:
        raise FormatError('Invalid Deoxys resource name')
    path = root / name
    row = manifest['files'][name]
    if (not isinstance(row, dict) or path.is_symlink() or path.is_junction()
            or not path.is_file() or not 0 < path.stat().st_size <= 8 * 1024 * 1024):
        raise FormatError('Invalid Deoxys resource file')
    payload = path.read_bytes()
    if len(payload) != row.get('bytes') or hashlib.sha256(payload).hexdigest() != row.get('sha256'):
        raise FormatError('Registered Deoxys resource identity changed')
    return payload, row


def xd_models(directory=None):
    result = {}
    for form in FORMS:
        for shiny in (False, True):
            payload, _ = _read(f'xd-{form}-{"shiny" if shiny else "normal"}.pkx', directory)
            verify_xd_deoxys_model(payload, form, shiny)
            result[form, shiny] = payload
    return result


def artwork_png(form, *, shiny=False, hd=False, role='head', directory=None):
    if form not in FORMS or type(shiny) is not bool or type(hd) is not bool or role not in ('head', 'body'):
        raise FormatError('Invalid Deoxys artwork request')
    side = (42 if role == 'head' else 64) * (4 if hd else 1)
    payload, row = _read(f'{role}-{form}-{"shiny" if shiny else "normal"}-{"hd" if hd else "native"}.png', directory)
    if row.get('dimensions') != [side, side]:
        raise FormatError('Invalid registered Deoxys artwork dimensions')
    pixels = _png_pixels(payload, (side, side))
    if role == 'head' and any(alpha != 255 for alpha in pixels[3::4]):
        raise FormatError('Colosseum Deoxys heads must retain their opaque square framing')
    if role == 'body':
        from .model_artwork import validate_model_body
        if side == 64:
            validate_model_body(pixels)
        elif (not any(pixels[3::4]) or any(pixels[(y * side + x) * 4 + 3]
                for y in range(side) for x in range(side)
                if x in (0, side - 1) or y in (0, side - 1))):
            raise FormatError('HD Deoxys bodies require a visible, unclipped transparent silhouette')
    return payload


def portrait_pixels(form, shiny=False, *, directory=None):
    return _png_pixels(artwork_png(form, shiny=shiny, directory=directory), (42, 42))


def body_pixels(form, shiny=False, *, hd=False, directory=None):
    side = 256 if hd else 64
    return _png_pixels(artwork_png(form, shiny=shiny, hd=hd, role='body', directory=directory), (side, side))


def _rgba8(pixels, width, height):
    output = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = [pixels[((by + dy) * width + bx + dx) * 4:((by + dy) * width + bx + dx + 1) * 4]
                     if bx + dx < width and by + dy < height else bytes(4)
                     for dy in range(4) for dx in range(4)]
            output.extend(value for r, g, b, a in block for value in (a, r))
            output.extend(value for r, g, b, a in block for value in (g, b))
    return bytes(output)


def hd_face_recipes(directory=None):
    from .hd_overlays import dolphin_texture_name
    result = {}
    for form in FORMS:
        native = b''.join(portrait_pixels(form, shiny, directory=directory) for shiny in (False, True))
        images = [artwork_png(form, shiny=shiny, hd=True, directory=directory) for shiny in (False, True)]
        pixels = b''.join(_png_pixels(image, (168, 168)) for image in images)
        name = dolphin_texture_name(42, 84, 6, _rgba8(native, 42, 84)) + '.png'
        result[name] = {'form': form, 'png': _png((168, 336), pixels),
                        'native_rgba_sha256': hashlib.sha256(native).hexdigest()}
    return result


def prepare_hd_faces(destination, *, directory=None):
    """Publish only complete genuine paired head atlases; never resize the native face."""
    target = Path(destination)
    if target.is_symlink() or target.is_junction():
        raise FormatError('Deoxys HD destination must not be a linked directory')
    staged = []
    for name, recipe in hd_face_recipes(directory).items():
        path, payload = target / name, recipe['png']
        if path.is_symlink() or path.is_junction() or (path.exists() and path.read_bytes() != payload):
            raise FormatError('Conflicting Deoxys HD face output')
        staged.append((path, payload))
    target.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for path, payload in staged:
            if not path.exists():
                with path.open('xb') as stream:
                    stream.write(payload)
                created.append(path)
    except BaseException:
        for path in created:
            path.unlink()
        raise
    return {'version': VERSION, 'active': True,
            'files': {p.name: hashlib.sha256(data).hexdigest() for p, data in staged},
            'native_dimensions': [42, 84], 'hd_dimensions': [168, 336],
            'native_bitmap_upscaled_for_hd': False}
