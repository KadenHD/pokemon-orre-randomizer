"""Render each live Spinda motif inside the keypad's existing CMPR atlas."""

from collections import Counter
import struct

from .actor_palette import pkx_recipe, remap_rgb565
from .analyze_game import FormatError, parse_fsys, u32
from .colo_spinda_field import _LAYOUTS, _PARSE_SIGNATURE, _PARSE_WORD, _load_constant
from .dna_keypad import (
    DNA_KEYPAD_SPECIES, _ATLAS_DESCRIPTOR, _ATLAS_OFFSET, _ATLAS_SIGNATURE, _ATLAS_WIDTH,
    _BLOCK_BYTES, _BLOCK_SIZE, _KEYPAD_DAT_SIZE, _SPINDA_ART_RECT, _SPINDA_KEYPAD_MARKER,
    _TILE_ORIGINS, _atlas_block_offset,
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
    face_writer = address + 0x800
    diagram_writer = face_writer + 0xA00
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
    for old, sample in samples.items():
        _emit_sample_pid(code, region, old, sample, pid, f"skip_{old}")
        # Evaluate the resolved PID against the same owner as the hologram.
        code.emit(0x7C603A78, 0x540C843E, 0x7C006278, 0x5400043E, 0x38A00000, 0x28000008)
        code.conditional(0x40800000, f"color_{old}")
        code.emit(0x38A00001)
        code.label(f"color_{old}")
        code.emit(0x90A10018, 0x7C641B78, 0x38A00000)
        scratch_loads.append((len(code.words), 3))
        code.emit(0, 0)
        code.call(face_writer)

        x, y = _TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(old)]
        left, top, _ = _SPINDA_ART_RECT
        _load_constant(code, 12, _atlas_block_offset(x + left, y + top))
        code.emit(0x8061000C, 0x7C636214, 0x80A10018)
        scratch_loads.append((len(code.words), 4))
        code.emit(0, 0)
        code.call(diagram_writer)
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

    face_code = spinda_face_writer(face_writer, face, stamp, recipe)
    diagram_code = _diagram_writer(diagram_writer, face, stamp, recipe)
    scratch = (diagram_writer + len(diagram_code) + 31) & ~31
    for index, register in scratch_loads:
        code.words[index:index + 2] = (
            0x3C000000 | register << 21 | scratch >> 16,
            0x60000000 | register << 21 | register << 16 | (scratch & 0xFFFF),
        )
    payload = code.finish()
    if len(payload) > face_writer - address or len(face_code) > diagram_writer - face_writer:
        raise FormatError("DNA keypad hook overlaps its texture writers")
    return (payload.ljust(face_writer - address, b"\0") + face_code).ljust(diagram_writer - address, b"\0") + (
        diagram_code.ljust(scratch - diagram_writer, b"\0") + bytes(_FACE_BYTES)
    )


def apply_dna_keypad_runtime(original, current, read_archive, samples, pid):
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
