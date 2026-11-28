"""Render saved specimen appearances inside the keypad's existing CMPR atlas."""

from collections import Counter
import struct

from .actor_palette import pkx_recipe, remap_rgb565
from .analyze_game import FormatError, parse_fsys, u32
from .colo_spinda_field import _LAYOUTS, _PARSE_SIGNATURE, _PARSE_WORD, _load_constant
from .dna_keypad import (
    DNA_KEYPAD_SPECIES, _ATLAS_DESCRIPTOR, _ATLAS_OFFSET, _ATLAS_SIGNATURE, _ATLAS_WIDTH,
    _BLOCK_BYTES, _BLOCK_SIZE, _KEYPAD_DAT_SIZE, _SPINDA_ART_RECT, _SPINDA_KEYPAD_MARKER,
    _TILE_ORIGINS, _atlas_block_offset, _BODY_ART_RECT, _CUSTOM_BODY_ART_RECT,
)
from .dna_lab import _emit_sample_pid
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .rebuild_iso import decoded_member
from .shiny_rules import _Code
from .spinda import SPINDA
from .spinda_art import _FACE_ORDER, _FACE_SIZE, _SPOT_ORDER, _SPOT_SIZE, _linear_rgb565
from .spinda_runtime import spinda_face_writer


_FACE_BYTES = _FACE_SIZE ** 2 * 2
_ATLAS_BYTES = _ATLAS_WIDTH ** 2 // 2
_PID_TABLE_MARKER = b"ORRE_SPND_DIAGRAM_PID_V1\0".ljust(32, b"\0")


def _sample_offsets():
    """Map the diagram's CMPR texel order to the native tiled RGB565 face."""
    size = _SPINDA_ART_RECT[2]
    native_offset = [0] * len(_FACE_ORDER)
    for offset, pixel in enumerate(_FACE_ORDER):
        native_offset[pixel] = offset * 2
    return [
        native_offset[(y + dy + row) * _FACE_SIZE // size * _FACE_SIZE
                      + (x + dx + col) * _FACE_SIZE // size]
        for y in range(0, size, _BLOCK_SIZE)
        for x in range(0, size, _BLOCK_SIZE)
        for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4))
        for row in range(4)
        for col in range(4)
    ]


def _endpoints(base, spot):
    first, second = sorted((base, spot), reverse=True)
    if first == second:
        raise FormatError("Spinda keypad spot and background have the same color")
    return first << 16 | second, int(spot == second)


def _diagram_writer(address, face, stamp, recipe):
    """Draw the native spot mask as a two-color swatch (r3 atlas, r4 face, r5 shiny)."""
    background = _linear_rgb565(face, _FACE_SIZE, _FACE_ORDER)[0]
    spots = Counter(color for color in _linear_rgb565(stamp, _SPOT_SIZE, _SPOT_ORDER) if color > background)
    if not spots:
        raise FormatError("Spinda keypad texture has no visible spots")
    spot = spots.most_common(1)[0][0]
    normal_endpoints, normal_index = _endpoints(background, spot)
    shiny_endpoints, shiny_index = _endpoints(remap_rgb565(background, *recipe), remap_rgb565(spot, *recipe))
    blocks = _SPINDA_ART_RECT[2] // _BLOCK_SIZE
    skip = (_ATLAS_WIDTH // _BLOCK_SIZE - blocks) * _BLOCK_BYTES

    code = _Code(address)
    code.emit(0x28050000)
    code.conditional(0x41820000, "normal")
    _load_constant(code, 5, shiny_endpoints)
    code.emit(0x39400000 | shiny_index)
    code.jump("start")
    code.label("normal")
    _load_constant(code, 5, normal_endpoints)
    code.emit(0x39400000 | normal_index)
    code.label("start")
    table_load = len(code.words)
    code.emit(0, 0, 0x38E00000 | blocks)
    code.label("row")
    code.emit(0x39000000 | blocks)
    code.label("block")
    code.emit(0x39200004)
    code.label("quadrant")
    code.emit(0x39800010, 0x7D8903A6, 0x38000000)  # 16 pixels per CMPR quadrant
    code.label("pixel")
    code.emit(0xA1860000, 0x38C60002, 0x7D84622E, 0x5400103A, 0x280C0000 | background)
    code.conditional(0x40820000, "spot")
    code.emit(0x694B0001)  # background selector is the opposite of the spot selector
    code.jump("index")
    code.label("spot")
    code.emit(0x7D4B5378)  # mr r11,r10
    code.label("index")
    code.emit(0x7C005B78)
    code.conditional(0x42000000, "pixel")  # bdnz
    code.emit(0x90A30000, 0x90030004, 0x38630008, 0x3529FFFF)
    code.conditional(0x40820000, "quadrant")
    code.emit(0x3508FFFF)
    code.conditional(0x40820000, "block")
    code.emit(0x38630000 | skip, 0x34E7FFFF)
    code.conditional(0x40820000, "row")
    code.emit(0x4E800020)
    table = address + ((len(code.words) * 4 + 31) & ~31)
    code.words[table_load:table_load + 2] = (0x3CC00000 | (table >> 16), 0x60C60000 | (table & 0xFFFF))
    offsets = _sample_offsets()
    return code.finish() + struct.pack(f">{len(offsets)}H", *offsets)


def _keypad_hook(address, parser, chained, flush, invalidate, region, samples, pid, face, stamp, recipe):
    # Both writers use the same retail stamps as the hologram. The face is
    # generated in a dedicated arena buffer, outside the native parser stack.
    # Resolve writer positions after emitting every sample. A fixed0x800
    # reservation overflowed when many samples independently became Spinda.
    writer_calls = []
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    code.emit(0x28040000)
    code.conditional(0x41820000, "native")
    _load_constant(code, 8, _KEYPAD_DAT_SIZE)
    code.emit(0x7C054040)  # validate the actual length before reading the DAT
    code.conditional(0x40820000, "native")
    code.emit(0x80C40018)
    _load_constant(code, 8, _SPINDA_KEYPAD_MARKER)
    code.emit(0x7C064040)
    code.conditional(0x40820000, "native")
    for offset, expected in zip(range(_ATLAS_DESCRIPTOR, _ATLAS_DESCRIPTOR + 12, 4), _ATLAS_SIGNATURE, strict=True):
        code.emit(0x80C40000 | offset)
        _load_constant(code, 8, expected)
        code.emit(0x7C064040)
        code.conditional(0x40820000, "native")

    code.emit(0x9421FEA0, 0x7C0802A6, 0x90010164, 0x90610010, 0x9081000C, 0x90A10014,
              0x38000000, 0x3940004E, 0x7D4903A6, 0x3961001C)
    code.label("clear")
    code.emit(0x940B0004)
    code.conditional(0x42000000, "clear")
    code.emit(0x38000000 | SPINDA, 0xB0010020, 0x38610020, 0x90610008)
    scratch_loads = []
    record_loads = []
    # A later independent-texture bridge consumes these exact already-resolved
    # identities. They are transient arena data; no player/save data is written.
    for old in samples:
        record_loads.append((len(code.words), old))
        code.emit(0, 0, 0x38000000, 0x900C0004)  # reset ready for this parse
    for old, sample in samples.items():
        _emit_sample_pid(code, region, old, sample, pid, f"skip_{old}")
        record_loads.append((len(code.words), old))
        code.emit(0, 0, 0x906C0008)  # keep the complete saved/seeded PID
        # Evaluate the resolved PID against the same owner as the hologram.
        code.emit(0x7C603A78, 0x540C843E, 0x7C006278, 0x5400043E, 0x38A00000, 0x28000008)
        code.conditional(0x40800000, f"color_{old}")
        code.emit(0x38A00001)
        code.label(f"color_{old}")
        record_loads.append((len(code.words), old))
        code.emit(0, 0)
        code.emit(0x90AC000C, 0x38000001, 0x900C0004,
                  0x90A10018, 0x7C641B78, 0x38A00000)
        scratch_loads.append((len(code.words), 3))
        code.emit(0, 0)
        writer_calls.append((len(code.words), "face"))
        code.emit(0)

        x, y = _TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(old)]
        left, top, _ = _SPINDA_ART_RECT
        _load_constant(code, 12, _atlas_block_offset(x + left, y + top))
        code.emit(0x8061000C, 0x7C636214, 0x80A10018)
        scratch_loads.append((len(code.words), 4))
        code.emit(0, 0)
        writer_calls.append((len(code.words), "diagram"))
        code.emit(0)
        code.label(f"skip_{old}")

    code.emit(0x8061000C, 0x38630000 | _ATLAS_OFFSET)
    _load_constant(code, 4, _ATLAS_BYTES)
    code.call(flush)
    code.call(invalidate)
    code.emit(0x80610010, 0x8081000C, 0x80A10014, 0x80010164, 0x7C0803A6, 0x38210160)
    code.label("native")
    if chained is None:
        code.emit(_PARSE_WORD)
    code.emit(branch(address + len(code.words) * 4, chained if chained is not None else parser + 4))

    face_writer = (address + len(code.words) * 4 + 31) & ~31
    face_code = spinda_face_writer(face_writer, face, stamp, recipe)
    diagram_writer = (face_writer + len(face_code) + 31) & ~31
    diagram_code = _diagram_writer(diagram_writer, face, stamp, recipe)
    scratch = (diagram_writer + len(diagram_code) + 31) & ~31
    table = scratch + _FACE_BYTES
    for index, old in record_loads:
        record = table + 48 + list(samples).index(old) * 16
        code.words[index:index + 2] = (0x3D800000 | record >> 16, 0x618C0000 | (record & 65535))
    for index, register in scratch_loads:
        code.words[index:index + 2] = (
            0x3C000000 | register << 21 | scratch >> 16,
            0x60000000 | register << 21 | register << 16 | (scratch & 0xFFFF),
        )
    for index, writer in writer_calls:
        target = face_writer if writer == "face" else diagram_writer
        code.words[index] = branch(address + index * 4, target, link=True)
    payload = code.finish()
    if len(payload) > face_writer - address or len(face_code) > diagram_writer - face_writer:
        raise FormatError("DNA keypad hook overlaps its texture writers")
    result = (payload.ljust(face_writer - address, b"\0") + face_code).ljust(diagram_writer - address, b"\0") + (
        diagram_code.ljust(scratch - diagram_writer, b"\0") + bytes(_FACE_BYTES)
        + _PID_TABLE_MARKER + struct.pack(">4I", len(samples), 0, 0, 0)
        + b"".join(struct.pack(">HHIII", old, sample[0], 0, 0, 0) for old, sample in samples.items())
    )
    return result + bytes(-len(result) % 32)


def spinda_diagram_pid_records(dol: bytes) -> dict[int, dict]:
    """Locate a unique qualified table emitted by our own text2 writer."""
    section, size, ram = u32(dol, 8), u32(dol, 0x98), u32(dol, 0x50)
    if not size:
        return {}
    if not section or section + size != len(dol) or not 0x80000000 < ram < 0x81700000:
        raise FormatError("Invalid Spinda diagram PID arena")
    first = dol.find(_PID_TABLE_MARKER, section)
    if first < 0:
        return {}
    if dol.find(_PID_TABLE_MARKER, first + 1) >= 0 or first + 48 > len(dol):
        raise FormatError("Ambiguous or truncated Spinda diagram PID table")
    count, a, b, c = struct.unpack_from(">4I", dol, first + 32)
    if not 1 <= count <= 9 or a or b or c or first + 48 + count * 16 > len(dol):
        raise FormatError("Invalid Spinda diagram PID table header")
    records = {}
    for index in range(count):
        at = first + 48 + index * 16
        old, sid, ready, pid_value, shiny = struct.unpack_from(">HHIII", dol, at)
        if old not in DNA_KEYPAD_SPECIES or old in records or not 1 <= sid <= 96 or ready or pid_value or shiny:
            raise FormatError("Invalid compiled Spinda diagram PID record")
        records[old] = {"address": ram + at - section, "shadow_id": sid}
    return records


def _apply_spinda_keypad_runtime(original, current, read_archive, samples, pid):
    """Patch the native DAT parser only when a randomized sample can be Spinda."""
    if not samples:
        return current
    region = dol_layout(original)
    parser, flush, invalidate = _LAYOUTS[region.game_id]
    parser_offset = parser - TEXT_TO_RAM
    if (tuple(u32(original, parser_offset + i * 4) for i in range(len(_PARSE_SIGNATURE))) != _PARSE_SIGNATURE
            or tuple(u32(current, parser_offset + i * 4) for i in range(1, len(_PARSE_SIGNATURE))) != _PARSE_SIGNATURE[1:]):
        raise FormatError("unexpected DNA keypad parser")
    section = (len(original) + 31) & ~31
    previous_size = u32(current, 0x98)
    end = region.section_ram + previous_size
    arena = region.set_arena_lo - TEXT_TO_RAM
    if (previous_size < 32 or previous_size % 32 or section + previous_size != len(current)
            or (u32(current, 0x08), u32(current, 0x50)) != (section, region.section_ram)
            or current[section:section + 32] != _arena_guard(end, region.arena_lo_store)
            or u32(current, arena) != branch(region.set_arena_lo, region.section_ram)
            or not region.section_ram + 32 <= pid["resolver"] < end):
        raise FormatError("invalid DNA keypad DOL reservation")

    # The opening motorcycle can already hook this parser. Keep its entry
    # intact and route non-keypad calls through it, including startup Spinda.
    previous = u32(current, parser_offset)
    chained = None
    if previous != _PARSE_WORD:
        if previous & 0xFC000003 != 0x48000000:
            raise FormatError("unexpected existing DNA keypad parser hook")
        displacement = previous & 0x03FFFFFC
        chained = parser + displacement - ((1 << 26) if displacement & (1 << 25) else 0)
        if not region.section_ram + 32 <= chained < end:
            raise FormatError("existing DNA keypad parser hook outside the reserved section")

    source = read_archive("pkx_patcheel.fsys")
    members = {row["name"]: row for row in parse_fsys(source)["members"]}
    face, stamp, model = (decoded_member(source, members[name]) for name in ("face", "buti_a", "patcheel"))
    payload = _keypad_hook(end, parser, chained, flush, invalidate, region, samples, pid,
                           face, stamp, pkx_recipe(model, xd=False))
    if end + len(payload) >= 0x81700000:
        raise FormatError("DNA keypad hook exceeds the arena reservation")
    output = bytearray(current)
    output.extend(payload)
    output[section:section + 32] = _arena_guard(end + len(payload), region.arena_lo_store)
    struct.pack_into(">I", output, 0x98, previous_size + len(payload))
    struct.pack_into(">I", output, parser_offset, branch(parser, end))
    return bytes(output)


def _shadow_model_tiles(read_archive, appearances, samples):
    """Encode the four native appearance states without changing puzzle keys."""
    from ..artwork import _decode_pixels, _png_pixels
    from ..legendary_shadow_assets import dna, stem_for
    from .dna_keypad import _body_pixels, _tile_art, _tile_rows
    from .shadow_lugia_body import shadow_lugia_body_pixels
    keypad = read_archive("DNA_key.fsys")
    member = next(row for row in parse_fsys(keypad)["members"]
                  if row["identifier_raw"] == "0x107e0200")
    dat = decoded_member(keypad, member)
    template = _decode_pixels(128, 128, 4, b"".join(dat[a:b] for a, b in _tile_rows(896, 512)))
    bodies = read_archive("poke_body.fsys")
    members = {row["name"]: row for row in parse_fsys(bodies)["members"]}
    counts = Counter(species for species, _ in appearances.values())
    result = {}
    for old in samples:
        species = appearances[old][0]
        stem = stem_for(species)
        shadow = (tuple(shadow_lugia_body_pixels(shiny) for shiny in (False, True)) if species == 249 else
                  tuple(_png_pixels(dna(stem, shiny), (64, 64)) for shiny in (False, True)))
        variants = shadow + tuple(_body_pixels(bodies, members, species, shiny) for shiny in (False, True))
        number = DNA_KEYPAD_SPECIES.index(old) + 1 if counts[species] > 1 else 0
        result[old] = tuple(_tile_art(template, pixels, 64, 64, number,
            rect=_CUSTOM_BODY_ART_RECT if variant < 2 else _BODY_ART_RECT)
            for variant, pixels in enumerate(variants))
    return result


def _lugia_tile_copy(address):
    """Copy sixteen native CMPR block rows (r3 destination, r4 source)."""
    code = _Code(address)
    code.emit(0x39400010)
    code.label("row")
    code.emit(0x39200080)
    code.label("word")
    code.emit(0x80040000, 0x90030000, 0x38840004, 0x38630004, 0x3529FFFF)
    code.conditional(0x40820000, "word")
    code.emit(0x38630E00, 0x354AFFFF)
    code.conditional(0x40820000, "row")
    code.emit(0x4E800020)
    return code.finish()


def _lugia_keypad_hook(address, parser, chained, flush, invalidate, region, samples,
                       appearances, tiles, *, keep_after_purification=False):
    from .postgame_lugia_model import _SAVED_IDENTITIES
    saved, generated, purified = _SAVED_IDENTITIES[region.game_id]
    readers = {"stored_shadow_pid": saved, "shadow_generated": generated}
    writer = address + 0x2000
    writer_code = _lugia_tile_copy(writer)
    data_start = (writer + len(writer_code) + 31) & ~31
    tile_size = 128 * 128 // 2
    if any(len(image) != tile_size for row in tiles.values() for image in row):
        raise FormatError("invalid native Lugia keypad tile")
    source = {old: tuple(data_start + (index * 4 + variant) * tile_size for variant in range(4))
              for index, old in enumerate(samples)}
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    code.emit(0x28040000)
    code.conditional(0x41820000, "native")
    _load_constant(code, 8, _KEYPAD_DAT_SIZE)
    code.emit(0x7C054040)
    code.conditional(0x40820000, "native")
    code.emit(0x80C40018)
    _load_constant(code, 8, _SPINDA_KEYPAD_MARKER)
    code.emit(0x7C064040)
    code.conditional(0x40820000, "native")
    for offset, expected in zip(range(_ATLAS_DESCRIPTOR, _ATLAS_DESCRIPTOR + 12, 4), _ATLAS_SIGNATURE, strict=True):
        code.emit(0x80C40000 | offset)
        _load_constant(code, 8, expected)
        code.emit(0x7C064040)
        code.conditional(0x40820000, "native")
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044,
              0x90610008, 0x9081000C, 0x90A10010)
    for old, sid in samples.items():
        code.emit(0x38000000 | int(appearances[old][1]), 0x90010018)
        _emit_sample_pid(code, region, old, (sid, None, None, None), readers, f"palette_{old}")
        code.emit(0x7C603A78, 0x540C843E, 0x7C006278, 0x5400043E, 0x38A00000, 0x28000008)
        code.conditional(0x40800000, f"color_{old}")
        code.emit(0x38A00001)
        code.label(f"color_{old}")
        code.emit(0x90A10018)
        code.label(f"palette_{old}")
        if not keep_after_purification:
            code.emit(0x38600000 | sid)
            code.call(purified)
            code.emit(0x5460063E, 0x28000001)
            code.conditional(0x40820000, f"draw_{old}")
            code.emit(0x80A10018, 0x38A50002, 0x90A10018)
        code.label(f"draw_{old}")
        # r0 holds only a tiny variant index; no saved pointer is modified.
        code.emit(0x80010018)
        for variant in range(3):
            code.emit(0x28000000 | variant)
            code.conditional(0x41820000, f"tile_{old}_{variant}")
        _load_constant(code, 4, source[old][3])
        code.jump(f"copy_{old}")
        for variant in range(3):
            code.label(f"tile_{old}_{variant}")
            _load_constant(code, 4, source[old][variant])
            code.jump(f"copy_{old}")
        code.label(f"copy_{old}")
        _load_constant(code, 12, _atlas_block_offset(*_TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(old)]))
        code.emit(0x8061000C, 0x7C636214)
        code.call(writer)
    code.emit(0x8061000C, 0x38630000 | _ATLAS_OFFSET)
    _load_constant(code, 4, _ATLAS_BYTES)
    code.call(flush)
    code.call(invalidate)
    code.emit(0x80610008, 0x8081000C, 0x80A10010,
              0x80010044, 0x7C0803A6, 0x38210040)
    code.label("native")
    if chained is None:
        code.emit(_PARSE_WORD)
    code.emit(branch(address + len(code.words) * 4, chained if chained is not None else parser + 4))
    body = code.finish()
    if len(body) > writer - address:
        raise FormatError("Lugia keypad callback overlaps its writer")
    return (body.ljust(writer - address, b"\0") + writer_code).ljust(data_start - address, b"\0") + b"".join(
        image for old in samples for image in tiles[old])


def _apply_lugia_keypad_runtime(original, current, read_archive, samples, appearances,
                                *, keep_after_purification=False):
    region = dol_layout(original)
    parser, flush, invalidate = _LAYOUTS[region.game_id]
    parser_offset = parser - TEXT_TO_RAM
    if (tuple(u32(original, parser_offset + i * 4) for i in range(len(_PARSE_SIGNATURE))) != _PARSE_SIGNATURE
            or tuple(u32(current, parser_offset + i * 4) for i in range(1, len(_PARSE_SIGNATURE))) != _PARSE_SIGNATURE[1:]):
        raise FormatError("unexpected native Lugia keypad parser")
    section = (len(original) + 31) & ~31
    previous_size = u32(current, 0x98)
    end = region.section_ram + previous_size
    arena = region.set_arena_lo - TEXT_TO_RAM
    if (previous_size < 32 or previous_size % 32 or section + previous_size != len(current)
            or (u32(current, 0x08), u32(current, 0x50)) != (section, region.section_ram)
            or current[section:section + 32] != _arena_guard(end, region.arena_lo_store)
            or u32(current, arena) != branch(region.set_arena_lo, region.section_ram)):
        raise FormatError("invalid Lugia keypad DOL reservation")
    previous = u32(current, parser_offset)
    chained = None
    if previous != _PARSE_WORD:
        if previous & 0xFC000003 != 0x48000000:
            raise FormatError("unexpected existing Lugia keypad parser hook")
        displacement = previous & 0x03FFFFFC
        chained = parser + displacement - ((1 << 26) if displacement & (1 << 25) else 0)
        if not region.section_ram + 32 <= chained < end:
            raise FormatError("existing Lugia keypad parser hook outside its reservation")
    payload = _lugia_keypad_hook(end, parser, chained, flush, invalidate, region, samples,
        appearances, _shadow_model_tiles(read_archive, appearances, samples),
        keep_after_purification=keep_after_purification)
    if end + len(payload) >= 0x81700000:
        raise FormatError("Lugia keypad hook exceeds the native arena")
    output = bytearray(current)
    output.extend(payload)
    output[section:section + 32] = _arena_guard(end + len(payload), region.arena_lo_store)
    struct.pack_into(">I", output, 0x98, previous_size + len(payload))
    struct.pack_into(">I", output, parser_offset, branch(parser, end))
    return bytes(output)


def apply_dna_keypad_runtime(original, current, read_archive, samples, pid, *,
                              shadow_lugia_samples=None, appearances=None,
                              legendary_samples=None, keep_after_purification=False):
    """Paint only known specimen tiles, preserving all native keypad answers."""
    output = _apply_spinda_keypad_runtime(original, current, read_archive, samples, pid)
    model_samples = (shadow_lugia_samples or {}) | (legendary_samples or {})
    if model_samples:
        from ..legendary_shadow_assets import SPECIES
        if (type(keep_after_purification) is not bool or not appearances
                or any(old not in DNA_KEYPAD_SPECIES or old not in appearances
                       or appearances[old][0] not in ({249} | (SPECIES.keys() - {410}))
                       or type(sid) is not int or not 1 <= sid <= 96
                       for old, sid in model_samples.items())):
            raise FormatError("invalid Lugia keypad specimen metadata")
        output = _apply_lugia_keypad_runtime(original, output, read_archive,
            model_samples, appearances, keep_after_purification=keep_after_purification)
    return output
