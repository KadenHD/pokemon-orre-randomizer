"""Use the player's actual Spinda face for a motorcycle arrival actor."""

import struct

from .actor_palette import pkx_recipe
from .analyze_game import FormatError, parse_fsys, u32
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .rebuild_iso import decoded_member
from .shiny_rules import _Code
from .spinda import SPINDA
from .spinda_runtime import spinda_face_writer


_LAYOUTS = {
    # HSD_ArchiveParse, DCFlushRange, GXInvalidateTexAll.
    "GC6P01": (0x801962D8, 0x8009E7F8, 0x800BE89C),
    "GC6E01": (0x80191F64, 0x8009B2D0, 0x800BB29C),
    "GC6J01": (0x8018DB28, 0x80098F7C, 0x800B8D10),
}
_MARKER = 0x53504E40
_FACE_DESC = 0x3FD4
_FACE_PIXELS = 0x4CF40
_FACE_LENGTH = 0x8000
_PARSE_WORD = 0x9421FFE0
_PARSE_SIGNATURE = (_PARSE_WORD, 0x7C0802A6, 0x90010024, 0x93E1001C, 0x3BE00000, 0x93C10018,
                    0x7C9E2378, 0x93A10014, 0x7C7D1B79, 0x93810010, 0x7CBC2B78)


def mark_spinda_starter_actor(dat: bytes, slot: int, pid_seed: int, shiny: bool) -> bytes:
    """Tag the DAT in its unused padding so the retail parser can paint it."""
    if (slot not in (0, 1) or not 0 <= pid_seed <= 0xFFFFFFFF
            or len(dat) < _FACE_PIXELS + _FACE_LENGTH or any(dat[0x18:0x20])
            or struct.unpack_from(">III", dat, _FACE_DESC) != (_FACE_PIXELS - 0x20, 0x00800080, 4)):
        raise FormatError("unexpected Spinda starter actor DAT")
    marker = _MARKER | slot | (int(shiny) << 1)
    return dat[:0x18] + struct.pack(">II", marker, pid_seed) + dat[0x20:]


def _load_constant(code, register, value):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | (value & 0xFFFF))


def _starter_hook(address, parser, flush, invalidate, player_pointer, resolver, face, spot, recipe):
    code = _Code(address)
    writer = address + 0x200
    code.emit(0x28040000)
    code.conditional(0x41820000, "native")
    code.emit(0x80C40018, 0x54C7003A)  # marker with low two flag bits cleared
    _load_constant(code, 8, _MARKER)
    code.emit(0x7C074040)
    code.conditional(0x40820000, "native")
    code.emit(0x80E40000)
    _load_constant(code, 8, _FACE_PIXELS + _FACE_LENGTH)
    code.emit(0x7C074040)
    code.conditional(0x41800000, "native")
    for offset, value in zip(range(_FACE_DESC, _FACE_DESC + 12, 4),
                             (_FACE_PIXELS - 0x20, 0x00800080, 4), strict=True):
        code.emit(0x80E40000 | offset)
        _load_constant(code, 8, value)
        code.emit(0x7C074040)
        code.conditional(0x40820000, "native")
    _load_constant(code, 7, player_pointer)
    code.emit(0x80E70000, 0x28070000)
    code.conditional(0x41820000, "native")
    code.emit(0x9421FE80, 0x7C0802A6, 0x90010184, 0x90610008, 0x9081000C,
              0x90A10010, 0x90C10014, 0x90E10018)
    # The CK3 party is at player+0xA0, 0x138 bytes per slot in all regions.
    code.emit(0x70C60001, 0x1CC60138, 0x38E700A0, 0x7CE73214, 0xA0C70000,
              0x28060000 | SPINDA)
    code.conditional(0x40820000, "resolve")
    code.emit(0x80870004, 0x80C70014, 0x7C863278, 0x54C5843E, 0x7CC62A78,
              0x54C6043E, 0x28060008, 0x38A00000)
    code.conditional(0x40800000, "paint")
    code.emit(0x38A00001)
    code.jump("paint")
    code.label("resolve")
    # The room can preload before its starters enter the party. Resolve the
    # same seed, gender and shiny policy against the real player's OT then.
    code.emit(0x8104001C, 0x28080000)
    code.conditional(0x41820000, "restore")
    code.emit(0x38000000, 0x3940004E, 0x7D4903A6, 0x3961002C)
    code.label("clear")
    code.emit(0x940B0004)
    code.conditional(0x42000000, "clear")
    code.emit(0x38000000 | SPINDA, 0xB0010030, 0x38610030, 0x38800000,
              0x38A0FFFF, 0x80C10014, 0x54C6FFFE, 0x80E10018, 0x80E7009C)
    code.call(resolver)
    code.emit(0x7C641B78, 0x80A10014, 0x54A5FFFE)
    code.label("paint")
    code.emit(0x8061000C, 0x3C630005, 0x3863CF40)
    code.call(writer)
    code.emit(0x8061000C, 0x3C630005, 0x3863CF40, 0x38807FFF, 0x38840001)
    code.call(flush)
    code.call(invalidate)
    code.label("restore")
    code.emit(0x80610008, 0x8081000C, 0x80A10010, 0x80010184, 0x7C0803A6, 0x38210180)
    code.label("native")
    code.emit(_PARSE_WORD, branch(address + (len(code.words) + 1) * 4, parser + 4))
    body = code.finish()
    if len(body) > writer - address:
        raise FormatError("Colosseum Spinda starter hook overlaps its face writer")
    payload = body + bytes(writer - address - len(body)) + spinda_face_writer(writer, face, spot, recipe)
    return payload + bytes(-len(payload) % 32)


def apply_colo_spinda_starters(original, current, resolver, read_archive):
    """Extend the guarded text2 section already holding the Spinda PID resolver."""
    region = dol_layout(original)
    parser, flush, invalidate = _LAYOUTS[region.game_id]
    for address, expected in ((parser, _PARSE_SIGNATURE), (flush, (0x28040000, 0x4C810020, 0x546506FE)),
                              (invalidate, (0x7C0802A6, 0x90010004, 0x9421FFF8))):
        if any(struct.unpack_from(f">{len(expected)}I", data, address - TEXT_TO_RAM) != expected
               for data in (original, current)):
            raise FormatError(f"unexpected Colosseum Spinda field instruction at {address:#x}")
    section_offset = (len(original) + 31) & ~31
    previous_size = u32(current, 0x98)
    end = region.section_ram + previous_size
    if (previous_size < 32 or previous_size % 32 or section_offset + previous_size != len(current)
            or (u32(current, 0x08), u32(current, 0x50)) != (section_offset, region.section_ram)
            or current[section_offset:section_offset + 32] != _arena_guard(end, region.arena_lo_store)
            or u32(current, region.set_arena_lo - TEXT_TO_RAM) != branch(region.set_arena_lo, region.section_ram)
            or not region.section_ram + 32 <= resolver < end):
        raise FormatError("invalid Colosseum Spinda field reservation")
    source = read_archive("pkx_patcheel.fsys")
    members = {row["name"]: row for row in parse_fsys(source)["members"]}
    face, spot, model = (decoded_member(source, members[name]) for name in ("face", "buti_a", "patcheel"))
    payload = _starter_hook(end, parser, flush, invalidate, region.player_pointer, resolver,
                            face, spot, pkx_recipe(model, xd=False))
    if end + len(payload) >= 0x81700000:
        raise FormatError("Colosseum Spinda starter hook exceeds the arena reservation")
    output = bytearray(current)
    output.extend(payload)
    output[section_offset:section_offset + 32] = _arena_guard(end + len(payload), region.arena_lo_store)
    struct.pack_into(">I", output, 0x98, previous_size + len(payload))
    struct.pack_into(">I", output, parser - TEXT_TO_RAM, branch(parser, end))
    return bytes(output)
