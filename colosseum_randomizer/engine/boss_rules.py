"""Conservative boss rules for explicitly identified original PAL trainer rows.

No team pointer, populated-slot count, Shadow Pokémon or script record changes.
The allowlist is based on names/IDs in the original tables, never level guesses.
"""
from __future__ import annotations

from collections import defaultdict
import struct

from .analyze_game import FormatError, check_range, u32
from .evolution_rules import evolution_families
from .gameplay_rules import MOVE_FIELDS, choose_moves, expanded_layout, move_catalog
from .inspect_tables import localized_names, u16
from .randomize_trainers import choose_species, layout
from .species_rules import candidate_species, species_catalog
from .rel_regions import region_for_rel

VERSION = "boss-rules-sha256-v1"
IV_FIELDS = tuple(range(0x1C, 0x22))
EV_FIELDS = tuple(range(0x23, 0x2E, 2))
# key, French name, English name, class ID, name ID, (trainer ID, first slot)
BOSS_IDENTITIES = (
    ("miror-b", "BOULEDISCO", "MIROR B.", 4, 4285,
     ((162, 2478), (163, 3991), (164, 3998), (165, 4831), (166, 4838), (793, 5412))),
    ("dakim", "DAKIM", "DAKIM", 4, 4195,
     ((211, 2555), (212, 4005), (213, 4012), (214, 4866), (215, 4873), (795, 5300))),
    ("venus", "VENUS", "VENUS", 4, 4113,
     ((326, 2674), (327, 4019), (328, 4026), (329, 4901), (330, 4908), (796, 5426))),
    ("ein", "TECK", "EIN", 4, 4269,
     ((403, 2814), (404, 4033), (405, 4040), (406, 4936), (407, 4943), (807, 5293))),
    ("gonzap", "HELGONZA", "GONZAP", 23, 4266,
     ((425, 4047), (426, 5209), (427, 5216), (811, 5328))),
    ("nascour", "JAKYLLA", "NASCOUR", 5, 4167, ((437, 4110), (438, 4117))),
    ("evice", "NOSFRAT", "EVICE", 6, 4326, ((439, 4124), (440, 4131))),
)
BOSS_JAPANESE_NAMES = {
    "miror-b": "ミラーボ", "dakim": "ダキム", "venus": "ヴィーナス", "ein": "ボルグ",
    "gonzap": "ヘルゴンザ", "nascour": "ジャキラ", "evice": "ワルダック",
}


def _position(data: bytes, table: dict, index: int, minimum_stride: int) -> int:
    if table["stride"] < minimum_stride or not 0 <= index < table["count"]:
        raise FormatError("boss rule references an invalid table record")
    pos = table["offset"] + index * table["stride"]
    check_range(data, pos, table["stride"], "boss table record")
    return pos


def _references(original: bytes, tables: dict) -> dict[int, list[int]]:
    references = defaultdict(list)
    for trainer in range(tables["trainers"]["count"]):
        pos = _position(original, tables["trainers"], trainer, 0x34)
        first = u16(original, pos + 4)
        if first:
            if first + 6 > tables["trainer_pokemon"]["count"]:
                raise FormatError("boss inventory found an out-of-range team")
            for index in range(first, first + 6):
                references[index].append(trainer)
    return dict(references)


def boss_inventory(original: bytes) -> tuple[dict, list[dict]]:
    """Validate every pinned row and return names, offsets, slots and sharing."""
    tables, symbols = layout(original)
    region = region_for_rel(original)
    names, _ = localized_names(original, symbols)
    references, bosses = _references(original, tables), []
    for key, french, english, class_id, name_id, variants in BOSS_IDENTITIES:
        for trainer, first in variants:
            pos = _position(original, tables["trainers"], trainer, 0x34)
            if (original[pos + 3], u16(original, pos + 4), u32(original, pos + 8)) != (
                    class_id, first, name_id):
                raise FormatError("pinned boss record differs from the original regional inventory")
            expected_names = ({"FR": french, "UK": english} if region.game_id == "GC6P01" else
                              {"US": english} if region.game_id == "GC6E01" else
                              {"JP": BOSS_JAPANESE_NAMES[key]})
            if any(names[language].get(name_id) != name for language, name in expected_names.items()):
                raise FormatError("pinned native boss name differs from the original regional inventory")
            slots = []
            for index in range(first, first + 6):
                slot = _position(original, tables["trainer_pokemon"], index, 0x50)
                if u16(original, slot + 0xA):
                    slots.append({"index": index, "offset": slot,
                                  "shadow_id": original[slot + 3],
                                  "referencing_trainers": references[index]})
            bosses.append({"key": key, "trainer_id": trainer, "trainer_offset": pos,
                           "name_fr": french, "name_en": english, "class_id": class_id,
                           "name_id": name_id, "first_pokemon_index": first, "slots": slots})
    return tables, sorted(bosses, key=lambda row: row["trainer_id"])


def apply_boss_tables(original: bytes, current: bytes, seed: str, options,
                      tables: dict, bosses: list[dict]) -> tuple[bytes, dict]:
    """Pure core; callers validate the original identity before supplying rows.

    Shadow slots, shared slots and move-marker slots remain byte-identical to
    current. A constrained pool that cannot improve diversity is reported;
    filters are never relaxed. Stats/typing are read from the final current REL.
    """
    stronger = getattr(options, "boss_stronger", False)
    variety = getattr(options, "boss_team_variety", False)
    if type(stronger) is not bool or type(variety) is not bool:
        raise ValueError("boss options must be booleans")
    if len(original) != len(current):
        raise FormatError("boss rules must preserve REL size")
    report = {"version": VERSION, "boss_stronger": stronger, "boss_team_variety": variety,
              "boss_characters": len({row["key"] for row in bosses}),
              "boss_trainer_records": len(bosses), "edits": [], "skipped": [],
              "unresolved_team_duplicates": [], "changed_bytes": 0,
              "shadow_records_unchanged": True, "team_pointers_and_slot_counts_unchanged": True,
              "all_boss_changes_whitelisted": True}
    if not (stronger or variety):
        return current, report
    output, allowed = bytearray(current), set()
    catalog = species_catalog(current, tables)
    families = evolution_families(original, tables)[0]
    references = _references(original, tables)
    moves = None
    seen = set()
    for boss in sorted(bosses, key=lambda row: row["trainer_id"]):
        trainer = boss["trainer_id"]
        trainer_pos = _position(original, tables["trainers"], trainer, 0x34)
        first = u16(original, trainer_pos + 4)
        # Never trust a caller-supplied offset or team membership over the bytes.
        if not first:
            raise FormatError("boss has no original team")
        slots, editable = [], []
        for index in range(first, first + 6):
            pos = _position(original, tables["trainer_pokemon"], index, 0x50)
            old_species, index_species = u16(original, pos + 0xA), u16(current, pos + 0xA)
            if bool(old_species) != bool(index_species) or original[pos + 3] != current[pos + 3]:
                raise FormatError("boss input changed populated slots or shadow identities")
            if not old_species:
                continue
            if index_species not in catalog or old_species not in catalog:
                raise FormatError("boss slot has an invalid species")
            slots.append((index, pos))
            reason = ("shadow" if original[pos + 3] else
                      "shared trainer slot" if references.get(index) != [trainer] else
                      "special move marker" if any(u16(original, pos + f) == 0xFFFF or
                          u16(original, pos + f) >= 355 or u16(current, pos + f) == 0xFFFF or
                          u16(current, pos + f) >= 355 for f in MOVE_FIELDS) else None)
            if reason:
                report["skipped"].append({"trainer_id": trainer, "index": index, "reason": reason})
            else:
                editable.append((index, pos))
        editable_ids = {index for index, _ in editable}
        retained = {families[u16(output, pos + 0xA)] for index, pos in slots if index not in editable_ids}
        reserved = {families[u16(output, pos + 0xA)] for _, pos in slots}
        for index, pos in editable:
            if index in seen:
                raise FormatError("boss slot would be processed twice")
            seen.add(index)
            before = bytes(output[pos:pos + 0x50])
            species = u16(output, pos + 0xA)
            change = {"trainer_id": trainer, "index": index, "offset": pos,
                      "old_species_index": species}
            if variety and families[species] in retained:
                try:
                    pool = candidate_species(original, tables, u16(original, pos + 0xA), options, reserved)
                    pool = [candidate for candidate in pool if catalog[candidate]["national_dex"] != 292]
                    if not pool:
                        raise FormatError("no safe species after protected Shedinja exclusion")
                    species = choose_species(seed, f"{VERSION}:trainer:{trainer}:slot:{index}", pool, -1)
                except FormatError as error:
                    report["unresolved_team_duplicates"].append(
                        {"trainer_id": trainer, "index": index, "reason": str(error)})
                else:
                    struct.pack_into(">H", output, pos + 0xA, species)
                    struct.pack_into(">I", output, pos + 0x14, u32(current, catalog[species]["offset"] + 0x18))
                    if output[pos] == 1 and not catalog[species]["abilities"][1]:
                        output[pos] = 0
                    allowed.update((pos, pos + 0xA, pos + 0xB, *range(pos + 0x14, pos + 0x18)))
                    if getattr(options, "randomize_trainer_moves", False):
                        if moves is None:
                            moves = move_catalog(original, tables)
                        chosen = choose_moves(seed, f"{VERSION}:moves:{trainer}:{index}",
                            catalog[species], output[pos + 4], moves, options)
                        for field, move in zip(MOVE_FIELDS, chosen, strict=True):
                            struct.pack_into(">H", output, pos + field, move)
                            allowed.update((pos + field, pos + field + 1))
            retained.add(families[species])
            reserved.add(families[species])
            if stronger:
                level = output[pos + 4]
                if not 1 <= level <= 100:
                    raise FormatError("boss has an invalid current level")
                output[pos + 4] = min(100, (level * 11 + 5) // 10)
                allowed.add(pos + 4)
                for field in IV_FIELDS:
                    # Preserve out-of-range/sentinel bytes; do not treat FF as 31.
                    if output[pos + field] <= 31:
                        output[pos + field] = max(20, output[pos + field])
                        allowed.add(pos + field)
                evs = [output[pos + field] for field in EV_FIELDS]
                proposed = [max(64, value) for value in evs]
                if sum(proposed) <= 510:
                    for field, value in zip(EV_FIELDS, proposed, strict=True):
                        output[pos + field] = value
                        allowed.add(pos + field)
                else:
                    change["ev_floor_skipped"] = "would exceed legal total 510; current EVs preserved"
            change.update(new_species_index=species, level_before=before[4], level_after=output[pos + 4],
                          ivs_before=[before[f] for f in IV_FIELDS], ivs_after=[output[pos + f] for f in IV_FIELDS],
                          evs_before=[before[f] for f in EV_FIELDS], evs_after=[output[pos + f] for f in EV_FIELDS])
            if bytes(output[pos:pos + 0x50]) != before:
                report["edits"].append(change)
        fixed_duplicate_count = len(slots) - len({families[u16(output, pos + 0xA)] for _, pos in slots})
        if variety and fixed_duplicate_count and not any(r["trainer_id"] == trainer for r in report["unresolved_team_duplicates"]):
            report["unresolved_team_duplicates"].append({"trainer_id": trainer,
                "reason": "duplicate families in protected slots", "duplicate_count": fixed_duplicate_count})
    result = bytes(output)
    changed = {i for i, (before, after) in enumerate(zip(current, result, strict=True)) if before != after}
    if changed - allowed:
        raise FormatError("boss patch altered an unauthorized field")
    report["changed_bytes"] = len(changed)
    return result, report


def apply_boss_rules(original: bytes, current: bytes, seed: str, options,
                     tables: dict | None = None) -> tuple[bytes, dict]:
    verified, bosses = boss_inventory(original)
    if tables is not None and any(tables.get(name) != table for name, table in verified.items()):
        raise FormatError("boss layout differs from verified original layout")
    if getattr(options, "randomize_trainer_moves", False):
        verified = expanded_layout(original)
    return apply_boss_tables(original, current, seed, options, verified, bosses)
