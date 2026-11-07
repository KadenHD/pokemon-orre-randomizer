"""Convert retail battle models for use by scripted field actors."""

from collections.abc import Callable
import struct

from .actor_palette import pkx_recipe, tint_field_model
from .analyze_game import FormatError, check_range, cstring, parse_fsys, u32
from .rebuild_iso import decoded_member, repack_fsys


ACTOR_ARCHIVES = ("M2_guild_1F_1.fsys", "M2_cave_1F_2.fsys")
_MODEL_TABLE = {"GC6P01": 0x3BACC8, "GC6E01": 0x36DBD0, "GC6J01": 0x35A338}
_XD_MODEL_TABLE = {"GXXP01": 0x444988, "GXXE01": 0x40A0A8, "GXXJ01": 0x3E7758}
_PLUSLE_RECORD = (0x1BF, 0x045F1E00, 0x51F)
_ACTOR_ID = "0x06f90400"
OVERSIZED_FIELD_SPECIES = frozenset((24, 95, 130, 143, 148, 208, 249, 250, 321, 350, 382, 383, 384))
# Cover the range of motion indices used by the Pyrite scripts.
_FIELD_MOTIONS = 12


def companion_scale(national: int, regular: float) -> float:
    if national == 321:  # Wailord can fill the frame even at 30%.
        return 0.12
    if national in (95, 130, 208, 384):
        return 0.22
    return 0.30 if national in OVERSIZED_FIELD_SPECIES else regular


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


def _field_model(pkx: bytes, *, header_size: int = 0x40, scale: float = 1.0, recipe=None) -> bytes:
    # Movement and emote slots in battle models contain species-specific
    # attacks. Reuse the species' idle motion for the field actor.
    dat = pkx[header_size:]
    check_range(dat, 0, 0x20, "story Pokémon DAT header")
    length, data_size, reloc_count, exports, imports = struct.unpack_from(">5I", dat)
    reloc_start = 0x20 + data_size
    exports_start = reloc_start + reloc_count * 4
    names_start = exports_start + 8 * exports
    if not exports or imports or not names_start < length <= len(dat):
        raise FormatError("unexpected story Pokémon DAT public symbol")
    public_symbols = struct.iter_unpack(">II", dat[exports_start:names_start])
    scenes = [pointer for pointer, name in public_symbols
              if names_start + name < length and cstring(dat[:length], names_start + name) == "scene_data"]
    if len(scenes) != 1:
        raise FormatError("expected one story Pokémon DAT scene")
    data = bytearray(dat[0x20:reloc_start])
    relocations = set(struct.unpack_from(f">{reloc_count}I", dat, reloc_start))
    model_list = u32(data, scenes[0])
    model = u32(data, model_list)
    check_range(data, model, 16, "story Pokémon model set")
    if recipe is not None:
        tint_field_model(data, relocations, model, recipe)
    if scale != 1.0:
        root = u32(data, model)
        check_range(data, root + 0x20, 12, "story Pokémon model root scale")
        values = struct.unpack_from(">3f", data, root + 0x20)
        if not all(0 < value <= 10 for value in values):
            raise FormatError("unexpected story Pokémon model root scale")
        struct.pack_into(">3f", data, root + 0x20, *(value * scale for value in values))
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


def load_actor_model(dol: bytes, game_id: str, model_id: int, archive: Callable[[str], bytes],
                     *, scale: float = 1.0, shiny: bool = False) -> bytes:
    xd = game_id in _XD_MODEL_TABLE
    if xd:
        table = _XD_MODEL_TABLE[game_id]
        if struct.unpack_from(">II", dol, table + 25 * 8) != (191, 0x02D51E00):
            raise FormatError("unexpected XD Pokémon model table")
        group, resource = struct.unpack_from(">II", dol, table + model_id * 8)
    else:
        table = _MODEL_TABLE[game_id]
        if struct.unpack_from(">III", dol, table + 353 * 12) != _PLUSLE_RECORD:
            raise FormatError("unexpected original story Pokémon model table")
        group, resource, _ = struct.unpack_from(">III", dol, table + model_id * 12)
    toc = archive("GSfsys.toc")
    if model_id == 201 and group == 0:
        # Unown selects its model at runtime. Form A is its field stand-in.
        name = "pkx_unknown_a.fsys"
        payload = archive(name)
        members = parse_fsys(payload)["members"]
    else:
        name = _model_resource(toc, group)
        payload = archive(name)
        parsed = parse_fsys(payload)
        if parsed["group_id"] != group:
            raise FormatError("story Pokémon model archive group differs")
        members = [row for row in parsed["members"] if int(row["identifier_raw"], 16) == resource]
    if len(members) != 1 or not members[0]["identifier_raw"].endswith("1e00"):
        raise FormatError("expected one story Pokémon battle model")
    pkx = decoded_member(payload, members[0])
    recipe = None
    if shiny:
        # A subset of species (including Charizard and Ho-Oh) have a retail
        # shiny model. Other species use a recipe in the ordinary PKX.
        rare = "pkx_rarecoil.fsys" if name == "pkx_coil.fsys" else name.replace("pkx_", "pkx_rare_", 1)
        if rare.removesuffix(".fsys").encode("ascii") + b"\0" in toc:
            payload = archive(rare)
            members = [row for row in parse_fsys(payload)["members"] if row["identifier_raw"].endswith("1e00")]
            if len(members) != 1:
                raise FormatError("expected one shiny story Pokémon battle model")
            pkx = decoded_member(payload, members[0])
        else:
            recipe = pkx_recipe(pkx, xd=xd)
    # XD adds a variable-length effects header before its 32-byte-aligned DAT.
    header_size = (len(pkx) - u32(pkx, 0)) & ~31 if xd else 0x40
    if xd and (header_size < 0x40 or u32(pkx, header_size) != u32(pkx, 0)):
        raise FormatError("unexpected XD Pokémon DAT offset")
    return _field_model(pkx, header_size=header_size, scale=scale, recipe=recipe)


def patch_actor(source: bytes, model: bytes, *, identifier: str = _ACTOR_ID, name: str = "prasle_b1") -> bytes:
    members = [row for row in parse_fsys(source)["members"] if row["identifier_raw"] == identifier]
    if len(members) != 1 or members[0]["name"] != name:
        raise FormatError(f"expected the original {name} actor in the story room")
    return repack_fsys(source, {members[0]["index"]: model})[0]
