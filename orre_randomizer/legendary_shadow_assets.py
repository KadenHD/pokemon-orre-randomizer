"""Approved Shadow palettes and display assets for the Generation III legends.

The model recipes contain changed materials and texture data only. Geometry,
animation schedules and unmodified data are read from the player's ROM.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .deoxys import DEOXYS, FORM_ORDER
from .engine.analyze_game import FormatError
from .engine.species_rules import LEGENDARY_NATIONAL

VERSION = 'legendary-shadow-materials-v1'
PACK = Path(__file__).resolve().parent / 'assets/game/models/legendary-shadow.orreassets'
SPECIES = {n: n for n in LEGENDARY_NATIONAL if n < 252 and n != 249}
SPECIES.update(enumerate((377, 378, 379, 382, 383, 384, 380, 381, 385, 386), start=401))
STEMS = tuple(str(n) for n in sorted(SPECIES.values())) + tuple(f'386-{form}' for form in FORM_ORDER[1:])


def stem_for(species: int, form: int = 0) -> str | None:
    national = SPECIES.get(species)
    if species == DEOXYS and form in range(1, len(FORM_ORDER)):
        return f'386-{FORM_ORDER[form]}'
    return str(national) if national is not None else None


@lru_cache(maxsize=1)
def manifest() -> dict:
    with ZipFile(PACK) as archive:
        result = json.loads(archive.read('manifest.json'))
    if result.get('version') != VERSION or set(result.get('entries', ())) != {
        f'{game}-{stem}-{variant}' for game in ('colosseum', 'xd') for stem in STEMS
        for variant in ('shadow', 'shiny')
    }:
        raise FormatError('invalid legendary Shadow appearance manifest')
    return result['entries']


def _key(game: str, stem: str, shiny: bool) -> str:
    if game not in ('colosseum', 'xd') or stem not in STEMS:
        raise ValueError('unknown legendary Shadow appearance')
    return f'{game}-{stem}-{"shiny" if shiny else "shadow"}'


@lru_cache(maxsize=256)
def _asset(name: str) -> bytes:
    with ZipFile(PACK) as archive:
        return archive.read(name)


def build_model(game: str, stem: str, shiny: bool, donor: bytes) -> bytes | None:
    key = _key(game, stem, shiny)
    entry = manifest()[key]
    if sha256(donor).hexdigest() != entry['donor']:
        return None
    recipe = BytesIO(_asset(key + '.materials'))
    insertion, added, count = struct.unpack('>III', recipe.read(12))
    if not 0 < insertion <= len(donor) or not 0 < added <= 0x400000 or count > 16384:
        raise FormatError('invalid legendary Shadow texture layout')
    data = bytearray(donor)
    previous_end = 0
    for _ in range(count):
        start, size = struct.unpack('>IH', recipe.read(6))
        if not size or start < previous_end or start + size > len(donor):
            raise FormatError('invalid legendary Shadow material range')
        replacement = recipe.read(size)
        if len(replacement) != size:
            raise FormatError('truncated legendary Shadow material')
        data[start:start + size] = replacement
        previous_end = start + size
    texture = recipe.read()
    if len(texture) != added:
        raise FormatError('invalid legendary Shadow texture payload size')
    data[insertion:insertion] = texture
    if sha256(data).hexdigest() != entry['model']:
        raise FormatError('legendary Shadow model changed outside its recipe')
    return bytes(data)


def portrait(game: str, stem: str, shiny: bool, *, hd=False) -> bytes:
    return _asset(f'{_key(game, stem, shiny)}-portrait-{168 if hd else 42}.png')


def face(game: str, stem: str, shiny=False) -> bytes:
    key = _key(game, stem, shiny)
    return _asset((f'{game}-{stem}' if game == 'colosseum' else key) + '-face.bin')


def dna(stem: str, shiny: bool, *, hd=False) -> bytes:
    variant = 'shiny' if shiny else 'shadow'
    return _asset(f'{stem}-{variant}-dna-{256 if hd else 64}.png')


def decorate_preview(row, game, stems):
    if not row.get('shadow_id'):
        return
    stem = stem_for(row['species'], row.get('deoxys_form', 0))
    if stem in stems:
        row['portrait_png'] = portrait(game, stem, bool(row.get('shiny')))


@lru_cache(maxsize=2)
def hd_materials(game):
    try:
        return json.loads(_asset(f'hd/{game}.json'))
    except (FileNotFoundError, KeyError):
        return {}


def hd_material(game, native_key):
    source = hd_materials(game)[native_key]
    png = _asset(f"hd/{source['image_sha256']}.png")
    if sha256(png).hexdigest() != source['image_sha256']:
        raise FormatError('legendary Shadow HD material has changed')
    return png, source
