"""Resolve saved Deoxys forms inside the DNA keypad without changing its answers."""
from collections import Counter
import struct

from ..artwork import _decode_pixels
from ..deoxys_identity import FORM_TAG
from .analyze_game import FormatError, parse_fsys, sha256, u32
from .colo_spinda_field import _LAYOUTS, _PARSE_SIGNATURE, _PARSE_WORD, _load_constant
from .dna_keypad import (DNA_KEYPAD_SPECIES, _DAT_SHA256, _ATLAS_DESCRIPTOR,
    _ATLAS_SIGNATURE, _KEYPAD_DAT_SIZE, _SPINDA_KEYPAD_MARKER, _ATLAS_OFFSET,
    _TILE_ORIGINS, _atlas_block_offset, _tile_rows, _tile_art, _body_pixels,
    _BODY_ART_RECT, _CUSTOM_BODY_ART_RECT)
from .dna_keypad_runtime import _ATLAS_BYTES, _lugia_tile_copy
from .dna_lab import _emit_sample_pid
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .postgame_lugia_model import _SAVED_IDENTITIES
from .rebuild_iso import decoded_member
from .shiny_rules import _Code


def native_body_variants(bodies_archive):
    """Return all eight full silhouettes with ink added only to new captures."""
    from ..deoxys_assets import body_pixels
    from .dna_artwork import outline_dna_body
    members = {row['name']: row for row in parse_fsys(bodies_archive)['members']}
    result = [_body_pixels(bodies_archive, members, 410, shiny) for shiny in (False, True)]
    for form in ('attack', 'defense', 'speed'):
        result.extend(outline_dna_body(body_pixels(form, shiny), 64) for shiny in (False, True))
    return tuple(result)


def native_tile_variants(read_archive, appearances, samples, *, legendary_shadow=False):
    """Finite per-cell keys: four forms by two palettes, no cross products."""
    source = read_archive('DNA_key.fsys')
    matches = [row for row in parse_fsys(source)['members'] if row['identifier_raw'] == '0x107e0200']
    if len(matches) != 1:
        raise FormatError('Expected the original DNA keypad model')
    dat = decoded_member(source, matches[0])
    if sha256(dat) != _DAT_SHA256:
        raise FormatError('Unexpected Deoxys DNA keypad template')
    template = _decode_pixels(128, 128, 4, b''.join(dat[a:b] for a, b in _tile_rows(896, 512)))
    bodies = native_body_variants(read_archive('poke_body.fsys'))
    if legendary_shadow:
        from ..artwork import _png_pixels
        from ..legendary_shadow_assets import dna
        bodies += tuple(_png_pixels(dna(stem, shiny), (64, 64))
                        for stem in ('386', '386-attack', '386-defense', '386-speed') for shiny in (False, True))
    counts = Counter(species for species, _ in appearances.values())
    return {old: tuple(_tile_art(template, pixels, 64, 64,
                DNA_KEYPAD_SPECIES.index(old) + 1 if counts[410] > 1 else 0,
                rect=_CUSTOM_BODY_ART_RECT if variant >= 2 else _BODY_ART_RECT)
            for variant, pixels in enumerate(bodies)) for old in samples}


def _keypad_hook(address, parser, chained, flush, invalidate, region, samples,
                 appearances, tiles, reader, *, legendary_shadow=False, keep=False):
    """Use a temporary full CK3 for the shared read-only saved-form resolver."""
    variants_per_cell = 16 if legendary_shadow else 8
    if set(tiles) != set(samples) or any(len(row) != variants_per_cell or any(len(tile) != 8192 for tile in row)
                                        for row in tiles.values()):
        raise FormatError('Invalid Deoxys DNA keypad tile set')
    saved, generated, purified = _SAVED_IDENTITIES[region.game_id]
    readers = {'stored_shadow_pid': saved, 'shadow_generated': generated}
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'native')
    code.emit(0x28040000)
    code.conditional(0x41820000, 'native')
    _load_constant(code, 8, _KEYPAD_DAT_SIZE)
    code.emit(0x7C054040)
    code.conditional(0x40820000, 'native')
    code.emit(0x80C40018)
    _load_constant(code, 8, _SPINDA_KEYPAD_MARKER)
    code.emit(0x7C064040)
    code.conditional(0x40820000, 'native')
    for offset, expected in zip(range(_ATLAS_DESCRIPTOR, _ATLAS_DESCRIPTOR + 12, 4), _ATLAS_SIGNATURE, strict=True):
        code.emit(0x80C40000 | offset)
        _load_constant(code, 8, expected)
        code.emit(0x7C064040)
        code.conditional(0x40820000, 'native')
    code.emit(0x9421FE60, 0x7C0802A6, 0x900101A4,
              0x9061000C, 0x90810010, 0x90A10014,
              0x38000000, 0x3900004E, 0x3921003C)
    code.label('clear')
    code.emit(0x94090004, 0x3508FFFF)
    code.conditional(0x40820000, 'clear')
    code.emit(0x39010040, 0x91010008, 0x3800019A, 0xB0080000)
    calls, source_loads = [], []
    for old, (sid, initial_form) in samples.items():
        code.emit(0x81010008, 0x38000000 | sid, 0xB00800D8,
                  0x38000000 | FORM_TAG | initial_form, 0xB00800D2,
                  0x38000000, 0x90080004, 0x90080014,
                  0x38000000 | int(appearances[old][1]), 0x9001001C)
        _emit_sample_pid(code, region, old, (sid, None, None, None), readers, f'identity_{old}')
        code.emit(0x81010008, 0x90680004, 0x90E80014,
                  0x7C603A78, 0x540C843E, 0x7C006278, 0x5400043E,
                  0x38A00000, 0x28000008)
        code.conditional(0x40800000, f'color_{old}')
        code.emit(0x38A00001)
        code.label(f'color_{old}')
        code.emit(0x90A1001C)
        code.label(f'identity_{old}')
        if legendary_shadow:
            code.emit(0x38000008, 0x90010020)
            if not keep:
                code.emit(0x38600000 | sid)
                code.call(purified)
                code.emit(0x5460063E, 0x28000001)
                code.conditional(0x40820000, f'palette_ready_{old}')
                code.emit(0x38000000, 0x90010020)
                code.label(f'palette_ready_{old}')
        code.emit(0x80610008)
        code.call(reader)
        code.emit(0x28030003)
        code.conditional(0x40810000, f'bounded_{old}')  # ble
        code.emit(0x38600000 | initial_form)
        code.label(f'bounded_{old}')
        code.emit(0x5460083C, 0x80A1001C, 0x7C002A14)
        if legendary_shadow:
            code.emit(0x80A10020, 0x7C002A14)
        code.emit(0x54006824)
        source_loads.append((len(code.words), old))
        code.emit(0, 0, 0x7C840214)
        _load_constant(code, 12, _atlas_block_offset(*_TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(old)]))
        code.emit(0x80610010, 0x7C636214)
        calls.append(len(code.words))
        code.emit(0)
    code.emit(0x80610010, 0x38630000 | _ATLAS_OFFSET)
    _load_constant(code, 4, _ATLAS_BYTES)
    code.call(flush)
    code.call(invalidate)
    code.emit(0x8061000C, 0x80810010, 0x80A10014,
              0x800101A4, 0x7C0803A6, 0x382101A0)
    code.label('native')
    if chained is None:
        code.emit(_PARSE_WORD)
    code.emit(branch(address + len(code.words) * 4, chained if chained is not None else parser + 4))
    writer = (address + len(code.words) * 4 + 31) & ~31
    writer_code = _lugia_tile_copy(writer)
    data = (writer + len(writer_code) + 31) & ~31
    for index, old in source_loads:
        pointer = data + list(samples).index(old) * variants_per_cell * 8192
        code.words[index:index + 2] = (0x3C800000 | pointer >> 16, 0x60840000 | pointer & 65535)
    for index in calls:
        code.words[index] = branch(address + index * 4, writer, link=True)
    result = (code.finish().ljust(writer - address, b'\0') + writer_code).ljust(data - address, b'\0')
    result += b''.join(tile for old in samples for tile in tiles[old])
    return result + bytes(-len(result) % 32)


def apply_deoxys_keypad_runtime(original, current, read_archive, samples, appearances, *, deoxys_reader,
                                legendary_shadow=False, keep=False):
    """Chain before the independent-cell bridge; never write player records."""
    if not samples:
        return current, {'active': False, 'samples': 0}
    if (not isinstance(samples, dict) or not appearances
            or type(deoxys_reader) is not int or not 0x80000000 <= deoxys_reader < 0x81800000
            or deoxys_reader & 3
            or any(old not in DNA_KEYPAD_SPECIES or appearances.get(old, (None,))[0] != 410
                   or not isinstance(row, (tuple, list)) or len(row) != 2
                   or type(row[0]) is not int or not 1 <= row[0] <= 96
                   or type(row[1]) is not int or not 0 <= row[1] < 4 for old, row in samples.items())):
        raise FormatError('Invalid Deoxys DNA keypad sample identities')
    region = dol_layout(original)
    parser, flush, invalidate = _LAYOUTS[region.game_id]
    at = parser - TEXT_TO_RAM
    if (tuple(u32(original, at + i * 4) for i in range(len(_PARSE_SIGNATURE))) != _PARSE_SIGNATURE
            or tuple(u32(current, at + i * 4) for i in range(1, len(_PARSE_SIGNATURE))) != _PARSE_SIGNATURE[1:]):
        raise FormatError('Unexpected Deoxys DNA keypad parser')
    section = (len(original) + 31) & ~31
    size = u32(current, 0x98)
    end = region.section_ram + size
    if (size < 32 or size % 32 or section + size != len(current)
            or (u32(current, 8), u32(current, 0x50)) != (section, region.section_ram)
            or current[section:section + 32] != _arena_guard(end, region.arena_lo_store)
            or u32(current, region.set_arena_lo - TEXT_TO_RAM) != branch(region.set_arena_lo, region.section_ram)):
        raise FormatError('Invalid Deoxys DNA keypad arena reservation')
    previous, chained = u32(current, at), None
    if previous != _PARSE_WORD:
        if previous & 0xFC000003 != 0x48000000:
            raise FormatError('Unexpected previous DNA keypad parser')
        displacement = previous & 0x03FFFFFC
        chained = parser + displacement - ((1 << 26) if displacement & (1 << 25) else 0)
        if not region.section_ram + 32 <= chained < end:
            raise FormatError('Previous DNA parser is outside the reserved arena')
    tiles = native_tile_variants(read_archive, appearances, samples, legendary_shadow=legendary_shadow)
    payload = _keypad_hook(end, parser, chained, flush, invalidate, region,
                           samples, appearances, tiles, deoxys_reader, legendary_shadow=legendary_shadow, keep=keep)
    if end + len(payload) >= 0x81700000:
        raise FormatError('Deoxys DNA keypad variants exceed the native arena')
    output = bytearray(current)
    output.extend(payload)
    output[section:section + 32] = _arena_guard(end + len(payload), region.arena_lo_store)
    struct.pack_into('>I', output, 0x98, size + len(payload))
    struct.pack_into('>I', output, at, branch(parser, end))
    return bytes(output), {'active': True, 'samples': len(samples), 'variants_per_cell': 16 if legendary_shadow else 8,
        'bytes': len(payload), 'reader': deoxys_reader, 'saved_data_written': False,
        'forms': 'latest owned form, otherwise initial seeded form',
        'shiny': 'saved specimen PID and owner, otherwise seeded hint'}
