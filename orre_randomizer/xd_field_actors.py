"""Keep scripted XD field Pokémon tied to their battle slots."""

import re
import struct

from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, check_range, parse_fsys, parse_rel, u32
from .engine.inspect_tables import rel_symbols, u16
from .engine.plusle_actor import companion_scale, load_actor_model, patch_actor
from .engine.rebuild_iso import decoded_member
from .xd_gifts import _patch_script, patch_species_operand


LIGHTHOUSE_ARCHIVE = "M6_tower_top.fsys"
LIGHTHOUSE_TRAINER = 221
LIGHTHOUSE_CRY_MESSAGES = (0xA16C, 0xA16D, 0xA16E, 0xA16F)
LUDICOLO = 297
_LUDICOLO_MODEL = 223
_LUDICOLO_RESOURCE = 0x166E0400
# Room-local copies override stock field resources only inside the lighthouse.
# The aliases use the same field flags as Ludicolo and similarly sized hitboxes.
_LIGHTHOUSE_MODELS = ((_LUDICOLO_MODEL, _LUDICOLO_RESOURCE), (195, 0x18820400),
                      (186, 0x18560400), (187, 0x18570400))
_SHARED_ACTORS = "people_archive.fsys"

GATEON_SHADOW = 30
_GATEON_ARCHIVE = "M6_out.fsys"
_ZANGOOSE = 380
_ZANGOOSE_RESOURCE = "0x18490400"
_ZANGOOSE_CRY = bytes.fromhex("02010000 0000017c 1101fff6 09250010")

WAKIN_TRAINER = 144
WAKIN_SHIP = "D3_out.fsys"
WAKIN_LAIR = "D5_out.fsys"
WAKIN_CRY_MESSAGE = 0x84ED
GLOOM = 44
_GLOOM_RESOURCE = "0x166b0400"
_GLOOM_CRY = bytes.fromhex("02010000 000084ed 02010000 0000002c 02010000 0000000f 11010001 09230049")


def _field_model(rel, species_table, species, dol, game_id, read_archive, chosen, normal_scale, *,
                 shiny=False, height_limit=None):
    national = species[chosen][0]
    scale = companion_scale(national, normal_scale)
    entry = species_table + 0x124 * chosen
    if height_limit is not None:
        height = u16(rel, entry + 8)  # Native Pokédex height in decimeters.
        if not height:
            raise FormatError("missing XD scripted Pokémon height")
        scale = min(scale, height_limit / height)
    model_id = u16(rel, entry + 0x2E)
    return (load_actor_model(dol, game_id, model_id, read_archive, scale=scale, shiny=shiny),
            {"species": chosen, "national_dex": national, "scale": scale})


def _lighthouse_rel(raw, common, common_models):
    symbols = rel_symbols(raw, parse_rel(raw))
    start = symbols[0]["offset"]
    count = u32(raw, symbols[1]["offset"])
    check_range(raw, start, 0x24 * count, "XD lighthouse character table")
    updated = bytearray(raw)
    for index, (model, ident) in enumerate(_LIGHTHOUSE_MODELS):
        if u32(common, common_models + model * 0x34 + 4) != ident:
            raise FormatError("unexpected XD lighthouse character model table")
        position = start + (4 + index) * 0x24
        if (count <= 4 + index or u16(raw, position + 6) != _LUDICOLO_MODEL
                or u16(raw, position + 0x16) != 10 + index):
            raise FormatError("unexpected XD lighthouse dancer record")
        struct.pack_into(">H", updated, position + 6, model)
    return bytes(updated)


_LIGHTHOUSE_CRY = re.compile(
    rb"\x02\x01\x00\x00(.{4})\x02\x01\x00\x00\x00\x00\x01\x29"
    rb"\x02\x01\x00\x00\x00\x00\x00\x0f.{4}\x09\x23\x00\x49", re.DOTALL,
)


def _lighthouse_script(raw, chosen):
    by_message = dict(zip(LIGHTHOUSE_CRY_MESSAGES, chosen, strict=True))
    updated = bytearray(raw)
    found = set()
    for call in _LIGHTHOUSE_CRY.finditer(raw):
        message = u32(raw, call.start(1))
        if message in by_message:
            patch_species_operand(raw, updated, call.start() + 12, LUDICOLO, by_message[message])
            found.add(message)
    if found != set(by_message):
        raise FormatError("missing XD lighthouse dancer cries")
    return bytes(updated)


def patch_lighthouse_dancers(original, current, rel, symbols, species, dol, game_id, read_archive, updates):
    row = 0x20 + LIGHTHOUSE_TRAINER * 0x38
    start = 0x20 + u32(original, 0x14)
    slots = [start + 0x20 * u16(original, row + 0x1C + slot * 2) for slot in range(5)]
    if original[row + 4] & 0x1F or any(u16(original, position) != LUDICOLO for position in slots):
        raise FormatError("unexpected XD lighthouse battle team")
    # The first four of the five retail Ludicolo slots have actors on the roof.
    chosen = [u16(current, position) for position in slots[:4]]
    if all(index == LUDICOLO for index in chosen):
        return []
    source = updates[LIGHTHOUSE_ARCHIVE] if LIGHTHOUSE_ARCHIVE in updates else read_archive(LIGHTHOUSE_ARCHIVE)
    shared = read_archive(_SHARED_ACTORS)
    stock = next((m for m in parse_fsys(shared)["members"] if m["identifier_raw"] == "0x166e0400"), None)
    if stock is None or stock["name"] != "runpappa":
        raise FormatError("missing retail XD lighthouse dancer")
    members = parse_fsys(source)["members"]
    room = next(m for m in members if m["identifier_raw"].endswith("1c00"))
    script = next(m for m in members if m["identifier_raw"].endswith("0e00"))
    room_raw = _lighthouse_rel(decoded_member(source, room), rel, symbols[84]["offset"])
    script_raw = _lighthouse_script(decoded_member(source, script), chosen)
    models, report = {}, []
    for index, ((_, ident), pokemon) in enumerate(zip(_LIGHTHOUSE_MODELS, chosen, strict=True)):
        if pokemon == LUDICOLO:
            model = decoded_member(shared, stock)
            actor = {"species": pokemon, "national_dex": 272, "scale": 1.0}
        else:
            model, actor = _field_model(rel, symbols[88]["offset"], species, dol, game_id, read_archive, pokemon, 0.8)
        models[ident] = (f"orre_lighthouse_dancer_{index + 1}", model)
        report.append(actor)
    updates[LIGHTHOUSE_ARCHIVE] = append_actor_models(
        source, {room["index"]: room_raw, script["index"]: script_raw}, shared, _LUDICOLO_RESOURCE, models,
    )
    return report


def _gateon_cry(raw, chosen):
    if raw.count(_ZANGOOSE_CRY) != 1:
        raise FormatError("missing scripted Gateon Zangoose cry")
    result = bytearray(raw)
    patch_species_operand(raw, result, raw.index(_ZANGOOSE_CRY) + 4, _ZANGOOSE, chosen)
    return bytes(result)


def patch_gateon_shadow(shadow, rel, species_table, species, dol, game_id, read_archive, updates, shiny):
    if shadow["shadow_id"] != GATEON_SHADOW or shadow["original"] != _ZANGOOSE:
        raise FormatError("unexpected Gateon scripted Shadow slot")
    chosen = shadow["species"]
    if chosen == _ZANGOOSE and not shiny:
        return None
    # The low camera sits close to Barry's partner. Preserve the scene's
    # framing by limiting large replacements to a 7.2-decimeter field model.
    model, report = _field_model(rel, species_table, species, dol, game_id, read_archive, chosen, 0.8,
                                 shiny=shiny, height_limit=7.2)
    # Both the room actor and the scripted model request resolve this shared
    # resource. Its stock references belong to this one Gateon scene.
    source = updates[_SHARED_ACTORS] if _SHARED_ACTORS in updates else read_archive(_SHARED_ACTORS)
    updates[_SHARED_ACTORS] = patch_actor(source, model, identifier=_ZANGOOSE_RESOURCE, name="zangoose")
    if chosen != _ZANGOOSE:
        source = updates[_GATEON_ARCHIVE] if _GATEON_ARCHIVE in updates else read_archive(_GATEON_ARCHIVE)
        updates[_GATEON_ARCHIVE] = _patch_script(
            source, _GATEON_ARCHIVE.removesuffix(".fsys"), lambda raw: _gateon_cry(raw, chosen),
        )
    return dict(report, shiny=shiny)


def patch_wakin_partner(original, current, rel, species_table, species, dol, game_id, read_archive, updates):
    trainer = 0x20 + WAKIN_TRAINER * 0x38
    start = 0x20 + u32(original, 0x14)
    slots = [start + 0x20 * u16(original, trainer + 0x1C + slot * 2) for slot in range(2)]
    if original[trainer + 4] & 3 or any(u16(original, position) != GLOOM for position in slots):
        raise FormatError("unexpected XD Wakin battle team")
    chosen = u16(current, slots[0])
    if chosen == GLOOM:
        return None
    model, report = _field_model(rel, species_table, species, dol, game_id, read_archive, chosen, 0.8,
                                 height_limit=8.0)

    def cry(raw):
        if raw.count(_GLOOM_CRY) != 1:
            raise FormatError("missing scripted Wakin partner cry")
        result = bytearray(raw)
        patch_species_operand(raw, result, raw.index(_GLOOM_CRY) + 12, GLOOM, chosen)
        return bytes(result)

    # The S.S. Libra reads the shared resource. The later Key Lair scene
    # also carries a room-local copy, which takes precedence on that map.
    for archive in (_SHARED_ACTORS, WAKIN_LAIR):
        source = updates[archive] if archive in updates else read_archive(archive)
        updates[archive] = patch_actor(source, model, identifier=_GLOOM_RESOURCE, name="kusaihana")
    updates[WAKIN_LAIR] = _patch_script(updates[WAKIN_LAIR], WAKIN_LAIR.removesuffix(".fsys"), cry)
    return report
