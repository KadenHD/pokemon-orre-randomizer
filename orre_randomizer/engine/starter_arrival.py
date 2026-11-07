"""Show the generated starters during the Outskirt Stand motorcycle scene."""

import struct

from .actor_archive import append_actor_models
from .analyze_game import FormatError, parse_fsys, u32
from .dol_regions import dol_layout, special_targets
from .event_gifts import _call, _fingerprint, _POP, _push, _statement
from .inspect_tables import u16
from .plusle_actor import companion_scale, load_actor_model
from .randomize_trainers import layout
from .rebuild_iso import decoded_member
from .species_rules import species_catalog


ARRIVAL_ARCHIVE = "S1_out.fsys"
_SCRIPT_ID = 0x01430E00
_BIKE_ID = 0x0C6C0400
_BIKE_ALIAS = 0x7DF20400
_BIKE_OPERAND = 0x9D2
_BEFORE_CAMERA_WAIT = 0xAE6
_BEFORE_BIKE_CLOSE = 0xB05
_BIKE_HASH = "179d05c87f08ce865d22ed4551d610e0e568989feb8583611456dbb053101d80"
_SCRIPT_HASH = "399743cde072bc62a5e488fa497620b873426df3d68046da0161930537360836"

# Part indexes for Umbreon and Espeon, followed by their polygon display-list
# lengths in the native DAT. The original skeleton and animation remain intact.
_RIDERS = (
    (61, (0x1FFFA, 0x203B2, 0x206B2, 0x20756, 0x20856, 0x20BD6, 0x20D1A)),
    (92, (0x21C3A, 0x21EA6, 0x21F56, 0x22056, 0x22136, 0x22286, 0x22932, 0x22A76)),
)


def _read_local(index):
    return _push(index) + b"\x10\x02\x00\x01"


def _jump(offset):
    return b"\x06" + struct.pack(">I", offset)


def _patch_program(source, actors):
    _fingerprint(source, _SCRIPT_HASH, "Outskirt Stand arrival script")
    code = bytearray(source)
    struct.pack_into(">I", code, _BIKE_OPERAND, _BIKE_ALIAS)
    load, unload = bytearray(), bytearray()
    group, bike = _read_local(3), _read_local(6)
    zero = b"\x08\x03" + bytes(4)
    for slot, (resource, lift) in actors.items():
        local = 7 + slot
        actor = _read_local(local)
        load.extend(_push(local) + _call(112, resource) + b"\x1f\x82\x02" + _POP)
        load.extend(_statement(70, group, actor, group, bike, _RIDERS[slot][0]))
        load.extend(_statement(59, group, actor, zero, b"\x08\x03" + struct.pack(">f", lift), zero))
        load.extend(_statement(115, actor, 0, 0, 1))
        unload.extend(_statement(113, actor))
    for offset, block in ((_BEFORE_CAMERA_WAIT, load), (_BEFORE_BIKE_CLOSE, unload)):
        code[offset:offset + 5] = _jump(len(code))
        code.extend(block + _push(0) + _jump(offset + 6))
    return bytes(code)


def patch_starter_arrival(original_dol, dol, rel, read_archive, shiny_decisions, guaranteed_shiny):
    """Use the final starter constructor operands, preserving any untouched rider."""
    chosen = {}
    for slot, target in enumerate(special_targets(original_dol)[:2]):
        word = u32(dol, target["base"])
        if word >> 16 != 0x3880:
            raise FormatError("unexpected starter constructor for Outskirt Stand")
        species = word & 0xFFFF
        shiny = shiny_decisions.get(target["key"], guaranteed_shiny)
        if species != target["old"] or shiny:
            chosen[slot] = species, shiny
    if not chosen:
        return None

    room = read_archive(ARRIVAL_ARCHIVE)
    members = {int(row["identifier_raw"], 16): row for row in parse_fsys(room)["members"]}
    if _SCRIPT_ID not in members or _BIKE_ID not in members:
        raise FormatError("missing native Outskirt Stand motorcycle resources")
    program = members[_SCRIPT_ID]
    bike = decoded_member(room, members[_BIKE_ID])
    _fingerprint(bike, _BIKE_HASH, "Outskirt Stand motorcycle")
    hidden = bytearray(bike)
    catalog = species_catalog(rel, layout(rel)[0])
    game = dol_layout(original_dol).game_id
    models, actors, report = {}, {}, []
    for slot, (species, shiny) in chosen.items():
        if species not in catalog:
            raise FormatError("invalid starter species for Outskirt Stand")
        row = catalog[species]
        national = row["national_dex"]
        # Use the native height in decimeters for every rider. Keep the
        # tighter field limits for especially wide or long battle models.
        height = max(1, u16(rel, row["offset"] + 0x0A))
        scale = min(companion_scale(national, 0.7), 0.7 * min(1.0, 18 / height))
        lift = 0.24 + max(0, 9 - height) / 10
        payload = load_actor_model(original_dol, game, u32(rel, row["offset"] + 0x2C),
                                   read_archive, scale=scale, shiny=shiny)
        resource = 0x7DF00400 + (slot << 16)
        actors[slot] = resource, lift
        models[resource] = f"orre_intro_starter_{slot + 1}", payload
        for length in _RIDERS[slot][1]:
            struct.pack_into(">H", hidden, length, 0)
        report.append({"slot": slot + 1, "species": species, "national_dex": national,
                       "shiny": shiny, "scale": scale})
    # A dedicated alias avoids changing the shared motorcycle used elsewhere.
    models[_BIKE_ALIAS] = ("orre_intro_bike", bytes(hidden))
    patched = _patch_program(decoded_member(room, program), actors)
    return append_actor_models(room, {program["index"]: patched}, room, _BIKE_ID, models), report
