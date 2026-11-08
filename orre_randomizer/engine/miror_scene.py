"""Keep Miror B.'s four Pyrite dancers tied to his cave battle."""

import struct

from .actor_archive import append_actor_models
from .analyze_game import FormatError, parse_fsys, u32
from .inspect_tables import u16
from .plusle_actor import companion_scale, load_actor_model
from .randomize_trainers import layout
from .rebuild_iso import decoded_member


MIROR_CAVE = "M2_cave_1F_2.fsys"
_DANCER_MODELS = (145, 146, 147, 148)
_DANCER_IDS = (0x012E0400, 0x11060400, 0x10D20400, 0x10D10400)


def synchronize_cave_team(original, current):
    tables, _ = layout(original)
    trainers, party = (tables[name] for name in ("trainers", "trainer_pokemon"))
    first = u16(original, trainers["offset"] + trainers["stride"] * 162 + 4)
    rematch = u16(original, trainers["offset"] + trainers["stride"] * 793 + 4)
    stride = party["stride"]
    updated = bytearray(current)
    species, slots = [], []
    for slot in range(4):
        battle_slot, retry_slot = first + 1 + slot, rematch + slot
        battle = party["offset"] + battle_slot * stride
        retry = party["offset"] + retry_slot * stride
        # The same fight can resume after Sudowoodo has already been snagged.
        # The four originals differ only in their slot identifier.
        if (u16(original, battle + 0xA) != 297
                or original[battle:battle + 0x18] != original[retry:retry + 0x18]
                or original[battle + 0x1C:battle + stride] != original[retry + 0x1C:retry + stride]):
            raise FormatError("unexpected Pyrite dancer party slots")
        updated[retry:retry + 0x18] = current[battle:battle + 0x18]
        updated[retry + 0x1C:retry + stride] = current[battle + 0x1C:battle + stride]
        species.append(u16(current, battle + 0xA))
        slots.append((battle_slot, retry_slot))
    return bytes(updated), tuple(species), tuple(slots)


def patch_cave_dancers(source, dol, game_id, dancers, shiny, species_table, rel, archive, *,
                       unown_form_index=0, spinda_pids=(None,) * 4):
    members = parse_fsys(source)["members"]
    room = next(row for row in members if row["identifier_raw"].endswith("1c00"))
    template = next(row for row in members if row["name"] == "runpappa")
    if int(template["identifier_raw"], 16) != _DANCER_IDS[0] or template["compression"] != "LZSS":
        raise FormatError("unexpected Ludicolo actor in the Pyrite cave")
    character_data = bytearray(decoded_member(source, room))
    models = []
    actors = zip(dancers, shiny, _DANCER_MODELS, _DANCER_IDS, spinda_pids, strict=True)
    for slot, (species, is_shiny, actor_index, resource_id, spinda_pid) in enumerate(actors):
        # The first character in this native four-entry group starts the
        # same script sequence on all three regional discs.
        positions = [i for i in range(0, len(character_data) - 16, 2)
                     if u16(character_data, i) == 145 and u16(character_data, i + 16) == 5 + slot]
        if len(positions) != 1:
            raise FormatError("unexpected Pyrite dancer character record")
        struct.pack_into(">H", character_data, positions[0], actor_index)
        pos = species_table["offset"] + species_table["stride"] * species
        national = u16(rel, pos + 0x10)
        if national == 272 and not is_shiny:
            model = decoded_member(source, template)
        else:
            model = load_actor_model(dol, game_id, u32(rel, pos + 0x2C), archive,
                                     scale=companion_scale(national, 0.8), shiny=is_shiny,
                                     unown_form_index=unown_form_index, spinda_pid=spinda_pid)
        models.append((resource_id, model))
    return append_actor_models(
        source, {room["index"]: bytes(character_data), template["index"]: models[0][1]},
        source, _DANCER_IDS[0],
        {resource: (f"pyrite_dancer_{index}", model)
         for index, (resource, model) in enumerate(models[1:], 1)},
    )
