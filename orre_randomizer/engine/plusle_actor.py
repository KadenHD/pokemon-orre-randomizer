"""Reuse the selected species' retail model in the two Pyrite story rooms."""

from collections.abc import Callable
import struct

from .analyze_game import FormatError, check_range, cstring, parse_fsys, u32
from .rebuild_iso import decoded_member, repack_fsys


ACTOR_ARCHIVES = ("M2_guild_1F_1.fsys", "M2_cave_1F_2.fsys")
_MODEL_TABLE = {"GC6P01": 0x3BACC8, "GC6E01": 0x36DBD0, "GC6J01": 0x35A338}
_PLUSLE_RECORD = (0x1BF, 0x045F1E00, 0x51F)
_ACTOR_ID = "0x06f90400"
# Cover the range of motion indices used by the Pyrite scripts.
_FIELD_MOTIONS = 12


def _model_resource(toc: bytes, group: int) -> str:
    check_range(toc, 0, 0x20, "archive directory header")
    if toc[:4] != b"GLLA":
        raise FormatError("unexpected archive directory signature")
    count, table = u32(toc, 8), u32(toc, 0x10)
    check_range(toc, table, count * 8, "archive directory entries")
    for handle, name_offset in struct.iter_unpack(">II", toc[table:table + count * 8]):
        if handle == group:
            name = cstring(toc, name_offset)
            if name.startswith("pkx_") and name.isascii() and name.replace("_", "").isalnum():
                return name + ".fsys"
            break
    raise FormatError("story Pokémon model archive was not found")


def _field_model(pkx: bytes) -> bytes:
    # The battle model's HSD DAT follows the 64-byte PKX header. The field
    # actor requests movement and emote slots, whose battle counterparts are
    # species-specific attacks. Reuse the species' idle motion in each slot.
    dat = pkx[0x40:]
    check_range(dat, 0, 0x20, "story Pokémon DAT header")
    length, data_size, reloc_count, exports, imports = struct.unpack_from(">5I", dat)
    reloc_start = 0x20 + data_size
    exports_start = reloc_start + reloc_count * 4
    check_range(dat, reloc_start, reloc_count * 4 + 19, "story Pokémon DAT tables")
    if (exports != 1 or imports or not exports_start + 19 <= length <= len(dat)
            or dat[exports_start + 4:exports_start + 19] != b"\0\0\0\0scene_data\0"):
        raise FormatError("unexpected story Pokémon DAT public symbol")
    data = bytearray(dat[0x20:reloc_start])
    relocations = set(struct.unpack_from(f">{reloc_count}I", dat, reloc_start))
    scene = u32(dat, exports_start)
    model_list = u32(data, scene)
    model = u32(data, model_list)
    check_range(data, model, 16, "story Pokémon model set")
    for field in (model + 4, model + 8, model + 12):
        table = u32(data, field)
        if not table:
            continue
        idle = u32(data, table)
        if not idle:
            if field == model + 4:
                raise FormatError("story Pokémon has no idle motion")
            struct.pack_into(">I", data, field, 0)
            relocations.discard(field)
            continue
        if idle >= data_size or field not in relocations or table not in relocations:
            raise FormatError("invalid story Pokémon idle motion pointer")
        start = len(data)
        struct.pack_into(">I", data, field, start)
        data.extend(struct.pack(">I", idle) * _FIELD_MOTIONS + bytes(4))
        relocations.update(range(start, start + _FIELD_MOTIONS * 4, 4))
    header = bytearray(dat[:0x20])
    pointers = struct.pack(f">{len(relocations)}I", *sorted(relocations))
    exports_data = dat[exports_start:length]
    struct.pack_into(">III", header, 0, len(header) + len(data) + len(pointers) + len(exports_data),
                     len(data), len(relocations))
    return bytes(header + data + pointers + exports_data)


def load_actor_model(dol: bytes, game_id: str, model_id: int, archive: Callable[[str], bytes]) -> bytes:
    table = _MODEL_TABLE[game_id]
    if struct.unpack_from(">III", dol, table + 353 * 12) != _PLUSLE_RECORD:
        raise FormatError("unexpected original story Pokémon model table")
    group, resource, _ = struct.unpack_from(">III", dol, table + model_id * 12)
    if model_id == 201 and group == 0:
        # Unown selects its model at runtime. Form A is its field stand-in.
        payload = archive("pkx_unknown_a.fsys")
        members = parse_fsys(payload)["members"]
    else:
        payload = archive(_model_resource(archive("GSfsys.toc"), group))
        parsed = parse_fsys(payload)
        if parsed["group_id"] != group:
            raise FormatError("story Pokémon model archive group differs")
        members = [row for row in parsed["members"] if int(row["identifier_raw"], 16) == resource]
    if len(members) != 1 or not members[0]["identifier_raw"].endswith("1e00"):
        raise FormatError("expected one story Pokémon battle model")
    return _field_model(decoded_member(payload, members[0]))


def patch_actor(source: bytes, model: bytes) -> bytes:
    members = [row for row in parse_fsys(source)["members"] if row["identifier_raw"] == _ACTOR_ID]
    if len(members) != 1 or members[0]["name"] != "prasle_b1":
        raise FormatError("expected the original Plusle actor in the story room")
    return repack_fsys(source, {members[0]["index"]: model})[0]
