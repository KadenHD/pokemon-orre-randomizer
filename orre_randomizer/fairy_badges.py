"""Authored Fairy badges in the games' native layouts and independent x4 art."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

from .artwork import _png, _png_pixels, _texture
from .engine.analyze_game import FormatError

VERSION = 'fairy-type-badges-v1'
LANGUAGES = ('en', 'de', 'fr', 'it', 'es', 'ja')
SIZES = {'colosseum': (79, 27), 'xd': (72, 18)}
SMALL_SIZE = (21, 18)
LARGE_RESOURCES = {language: ((0x7F85 + index) << 16) | 0x1200
                   for index, language in enumerate(LANGUAGES)}
SMALL_RESOURCES = {language: ((0x7F8B + index) << 16) | 0x1200
                   for index, language in enumerate(LANGUAGES)}


def _directory():
    from .resources import bundle_root
    return bundle_root() / 'types'


def badge_name(game, language, *, small=False, hd=False):
    if game not in SIZES or language not in LANGUAGES or small and game != 'xd':
        raise ValueError('Unsupported Fairy badge layout')
    return f'{game}-{language}-19' + ('-small' if small else '') + ('-hd' if hd else '') + '.png'


@lru_cache(maxsize=1)
def _manifest():
    directory = _directory()
    path = directory / 'fairy-badges.json'
    if directory.is_symlink() or path.is_symlink():
        raise FormatError('Linked Fairy badges refused')
    data = json.loads(path.read_text('utf-8'))
    expected = {badge_name(game, language, small=small, hd=hd)
                for game in SIZES for language in LANGUAGES
                for small in ((False, True) if game == 'xd' else (False,))
                for hd in (False, True)}
    if (data.get('version') != VERSION or data.get('schema') != 1
            or set(data.get('files', {})) != expected
            or data.get('native_bitmap_upscaled_for_hd') is not False):
        raise FormatError('Incomplete Fairy badge registry')
    return data


def badge_png(game, language, *, small=False, hd=False):
    name = badge_name(game, language, small=small, hd=hd)
    row = _manifest()['files'][name]
    path = _directory() / name
    if path.is_symlink() or not path.is_file():
        raise FormatError('Missing Fairy badge: ' + name)
    payload = path.read_bytes()
    dimensions = SMALL_SIZE if small else SIZES[game]
    dimensions = tuple(value * (4 if hd else 1) for value in dimensions)
    if (len(payload) != row['bytes'] or hashlib.sha256(payload).hexdigest() != row['sha256']
            or tuple(row['dimensions']) != dimensions):
        raise FormatError('Changed Fairy badge: ' + name)
    _png_pixels(payload, dimensions)
    return payload


def texture_dimensions(*, small=False):
    return (32, 32) if small else (128, 32)


def native_texture(game, language, *, small=False):
    """Build a genuine GX RGBA8 resource, with native-size crops and clear padding."""
    width, height = texture_dimensions(small=small)
    badge_width, badge_height = SMALL_SIZE if small else SIZES[game]
    pixels = _png_pixels(badge_png(game, language, small=small), (badge_width, badge_height))
    canvas = bytearray(width * height * 4)
    for y in range(badge_height):
        canvas[y * width * 4:(y * width + badge_width) * 4] = pixels[y * badge_width * 4:(y + 1) * badge_width * 4]
    header = bytearray(128)
    struct.pack_into('>HHBBHI', header, 0, width, height, 32, 1, 0, 0x45)
    struct.pack_into('>I', header, 0x28, 128)
    tiled = bytearray()
    for top in range(0, height, 4):
        for left in range(0, width, 4):
            block = [canvas[((top + y) * width + left + x) * 4:((top + y) * width + left + x + 1) * 4]
                     for y in range(4) for x in range(4)]
            tiled.extend(component for r, g, b, a in block for component in (a, r))
            tiled.extend(component for r, g, b, a in block for component in (g, b))
    result = bytes(header + tiled)
    if _texture(result, (width, height)) != bytes(canvas):
        raise FormatError('Fairy badge GX roundtrip failed')
    return result


def hd_texture(game, language, *, small=False):
    width, height = texture_dimensions(small=small)
    badge_width, badge_height = SMALL_SIZE if small else SIZES[game]
    pixels = _png_pixels(badge_png(game, language, small=small, hd=True), (badge_width * 4, badge_height * 4))
    canvas = bytearray(width * height * 16 * 4)
    for y in range(badge_height * 4):
        start = y * width * 16
        canvas[start:start + badge_width * 16] = pixels[y * badge_width * 16:(y + 1) * badge_width * 16]
    return _png((width * 4, height * 4), bytes(canvas))


def append_badges(archive, game, language):
    """Append to the caller-selected loaded battle archive; keep every old member."""
    from .engine.actor_archive import append_actor_models
    from .engine.analyze_game import parse_fsys
    if game not in SIZES or language not in LANGUAGES:
        raise ValueError('Unsupported Fairy badge archive')
    members = parse_fsys(archive)['members']
    donors = [member for member in members if int(member['identifier_raw'], 16) & 0xFF00 == 0x1200
              and member['compression'] == 'LZSS']
    if not donors:
        raise FormatError('No native texture header for Fairy badges')
    additions = {LARGE_RESOURCES[language]: (f'orre_fairy_{language}', native_texture(game, language))}
    if game == 'xd':
        additions[SMALL_RESOURCES[language]] = (f'orre_fairy_small_{language}', native_texture(game, language, small=True))
    result = append_actor_models(archive, {}, archive, int(donors[0]['identifier_raw'], 16), additions,
                                 resource_type=0x1200)
    return result, {'version': VERSION, 'language': language,
                    'resources': [f'{index:08x}' for index in additions],
                    'native_dimensions': list(SIZES[game]), 'original_members_preserved': True}


def hd_overrides(game):
    """Texture-cache keys are derived from the exact native padded GX resources."""
    from .hd_overlays import dolphin_texture_name
    outputs = {}
    for language in LANGUAGES:
        for small in ((False, True) if game == 'xd' else (False,)):
            width, height = texture_dimensions(small=small)
            texture = native_texture(game, language, small=small)
            key = dolphin_texture_name(width, height, 6, texture[128:])
            payload = hd_texture(game, language, small=small)
            if key in outputs and outputs[key] != payload:
                raise FormatError('Conflicting Fairy badge HD recipes')
            outputs[key] = payload
    return outputs
