"""Seeded PAL TM permutation and byte-per-TM species compatibility.

The fifty existing TM moves and their localized item-description IDs travel
together. HM entries, HM compatibility, item names and localized text payloads
are never rewritten. Production entry points fingerprint the unmodified inputs;
the table transform remains usable with synthetic fixtures for verification.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, check_range, sha256
from .gameplay_rules import damaging, expanded_layout, move_catalog
from .inspect_tables import u16
from .randomize_story import DOL_SHA256
from .species_rules import species_catalog
from .dol_regions import dol_layout
from .rel_regions import region_for_rel

VERSION = "tm-rules-sha256-v1"
TM_COUNT, HM_COUNT = 50, 8
TM_OFFSET, TM_STRIDE = 0x3B20D0, 8
ITEM_OFFSET, ITEM_STRIDE, FIRST_TM_ITEM = 0x3ADDA0, 0x28, 0x121
COMPAT_OFFSET = 0x34
ORIGINAL_TM_MOVES = (
    264, 337, 352, 347, 46, 92, 258, 339, 331, 237, 241, 269, 58, 59,
    63, 113, 182, 240, 202, 219, 218, 76, 231, 85, 87, 89, 216, 91,
    94, 247, 280, 104, 115, 351, 53, 188, 201, 126, 317, 332, 259,
    263, 290, 156, 213, 168, 211, 285, 289, 315)
ORIGINAL_HM_MOVES = (15, 19, 57, 70, 148, 249, 127, 291)
UNSAFE_OFFENSE = frozenset((12, 32, 90, 120, 153, 165, 329))


def _flag(options, name: str, default: bool) -> bool:
    value = getattr(options, name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _sample(seed: str, key: str, count: int) -> int:
    """Unbiased keyed sampling, isolated from every other randomizer feature."""
    if type(seed) is not str or not 1 <= len(seed.encode("utf-8")) <= 256 or count < 1:
        raise ValueError("invalid TM-rule seed or candidate count")
    raw = seed.encode("utf-8")
    prefix = VERSION.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big") + raw
    prefix += b"\0" + key.encode("ascii") + b"\0"
    limit = (1 << 256) // count * count
    counter = 0
    while True:
        number = int.from_bytes(hashlib.sha256(prefix + counter.to_bytes(4, "big")).digest(), "big")
        if number < limit:
            return number % count
        counter += 1


def _whitelist(before: bytes, after: bytes, ranges: list[tuple[int, int]]) -> dict:
    """Check every byte, including existing appended DOL sections and header."""
    if len(before) != len(after):
        raise AssertionError("TM rules changed the input length")
    end, changed = 0, 0
    for start, stop in sorted(ranges):
        if not end <= start < stop <= len(before):
            raise AssertionError("invalid TM patch whitelist")
        if before[end:start] != after[end:start]:
            raise AssertionError("TM patch escaped its whitelist")
        changed += sum(a != b for a, b in zip(before[start:stop], after[start:stop]))
        end = stop
    if before[end:] != after[end:]:
        raise AssertionError("TM patch escaped its whitelist")
    return {"changed_bytes": changed, "allowed_bytes": sum(b - a for a, b in ranges),
            "ranges": [{"offset": a, "size": b - a} for a, b in sorted(ranges)],
            "outside_whitelist_unchanged": True}


def _tm_records(original: bytes, current: bytes, *, tm_offset: int = TM_OFFSET,
                item_offset: int = ITEM_OFFSET) -> tuple[list[int], list[int]]:
    check_range(original, tm_offset, (TM_COUNT + HM_COUNT) * TM_STRIDE, "TM/HM move table")
    check_range(original, item_offset + FIRST_TM_ITEM * ITEM_STRIDE,
                (TM_COUNT + HM_COUNT) * ITEM_STRIDE, "TM/HM items")
    if len(current) < len(original):
        raise FormatError("current DOL is shorter than the original")
    moves, descriptions = [], []
    for index in range(TM_COUNT + HM_COUNT):
        pos = tm_offset + index * TM_STRIDE
        # Six unknown bytes stay intact, including the native TM/HM marker.
        expected = bytes((int(index >= TM_COUNT), 0, 0, 0, 0, 0))
        if original[pos:pos + 6] != expected or current[pos:pos + 8] != original[pos:pos + 8]:
            raise FormatError("TM/HM table signature differs from the original PAL layout")
        item = item_offset + (FIRST_TM_ITEM + index) * ITEM_STRIDE + 0x14
        if current[item:item + 4] != original[item:item + 4]:
            raise FormatError("TM/HM item descriptions were already modified")
        if index < TM_COUNT:
            moves.append(u16(original, pos + 6))
            descriptions.append(struct.unpack_from(">I", original, item)[0])
    if tuple(moves) != ORIGINAL_TM_MOVES or tuple(
            u16(original, tm_offset + i * TM_STRIDE + 6)
            for i in range(TM_COUNT, TM_COUNT + HM_COUNT)) != ORIGINAL_HM_MOVES:
        raise FormatError("native PAL TM/HM move identities differ")
    if descriptions != list(range(10195, 10245)):
        raise FormatError("native PAL TM description identities differ")
    return moves, descriptions


def apply_tm_tables(original_rel: bytes, current_rel: bytes, original_dol: bytes,
                    current_dol: bytes, seed: str, options, tables: dict, *,
                    tm_offset: int = TM_OFFSET, item_offset: int = ITEM_OFFSET,
                    native_languages: tuple[str, ...] = ("UK", "GE", "FR", "IT", "SP")) -> tuple[bytes, bytes, dict]:
    """Pure table transform; the caller validates original file fingerprints.

    Compatibility follows final current species types and final TM moves. In
    ``original`` mode every compatibility byte is preserved even when the
    offensive guarantee is enabled. In rewriting modes that guarantee may add
    an off-type TM when no offensive TM of a species' type exists.
    """
    shuffle = _flag(options, "randomize_tm_moves", False)
    ensure_offense = _flag(options, "tm_ensure_offensive", True)
    mode = getattr(options, "tm_compatibility_mode", "original")
    if mode not in ("original", "type", "universal", "random"):
        raise ValueError("unknown TM compatibility mode")
    _sample(seed, "validate", 1)
    if len(current_rel) != len(original_rel):
        raise FormatError("current REL length differs from the original")
    original_species = species_catalog(original_rel, tables)
    species = species_catalog(current_rel, tables)
    if {i: row["national_dex"] for i, row in original_species.items()} != {
            i: row["national_dex"] for i, row in species.items()}:
        raise FormatError("current real-species identities differ")
    moves = move_catalog(original_rel, tables)
    native, descriptions = _tm_records(original_dol, current_dol, tm_offset=tm_offset,
                                       item_offset=item_offset)
    if any(index not in moves for index in native):
        raise FormatError("TM table refers to a non-regular move")
    for index, row in original_species.items():
        pos = row["offset"] + COMPAT_OFFSET
        check_range(original_rel, pos, TM_COUNT + HM_COUNT, "species TM/HM compatibility")
        values = original_rel[pos:pos + TM_COUNT + HM_COUNT]
        if not set(values) <= {0, 1} or current_rel[pos:pos + len(values)] != values:
            raise FormatError(f"species {index} TM/HM compatibility differs from the original")

    order = list(range(TM_COUNT))
    if shuffle:
        # Sattolo's cycle preserves the entire native pool with no fixed CT.
        for index in range(TM_COUNT - 1, 0, -1):
            target = _sample(seed, f"permutation:{index}", index)
            order[index], order[target] = order[target], order[index]
    final_moves = [native[index] for index in order]
    dol, rel = bytearray(current_dol), bytearray(current_rel)
    dol_ranges, rel_ranges, mapping, compatibility = [], [], [], []
    for index, source in enumerate(order):
        move_pos = tm_offset + index * TM_STRIDE + 6
        desc_pos = item_offset + (FIRST_TM_ITEM + index) * ITEM_STRIDE + 0x14
        if shuffle:
            struct.pack_into(">H", dol, move_pos, final_moves[index])
            struct.pack_into(">I", dol, desc_pos, descriptions[source])
            dol_ranges.extend(((move_pos, move_pos + 2), (desc_pos, desc_pos + 4)))
        mapping.append({"tm": index + 1, "item_index": FIRST_TM_ITEM + index,
                        "source_tm": source + 1, "before_move": native[index],
                        "after_move": final_moves[index], "move_offset": move_pos,
                        "before_description_id": descriptions[index],
                        "after_description_id": descriptions[source], "description_offset": desc_pos})

    offensive = [index for index, move in enumerate(final_moves)
                 if move not in UNSAFE_OFFENSE and damaging(moves[move])]
    additions, unmet = [], []
    if mode != "original" and ensure_offense and not offensive:
        raise FormatError("final TM pool has no ordinary offensive move")
    for index, row in sorted(species.items()):
        pos = row["offset"] + COMPAT_OFFSET
        before = current_rel[pos:pos + TM_COUNT]
        values = list(before)
        if mode == "universal":
            values = [1] * TM_COUNT
        elif mode == "type":
            values = [int(moves[move]["type"] in row["types"]) for move in final_moves]
        elif mode == "random":
            values = [_sample(seed, f"compatibility:{index}:{tm + 1}", 2) for tm in range(TM_COUNT)]
        has_offense = any(values[tm] for tm in offensive)
        added = None
        if mode != "original" and ensure_offense and not has_offense:
            matching = [tm for tm in offensive if moves[final_moves[tm]]["type"] in row["types"]]
            pool = matching or offensive
            added = pool[_sample(seed, f"offensive:{index}", len(pool))]
            values[added] = 1
            additions.append({"species": index, "national_dex": row["national_dex"], "tm": added + 1,
                              "move": final_moves[added], "matches_type": bool(matching)})
        if not any(values[tm] for tm in offensive):
            unmet.append(index)
        if mode != "original":
            rel[pos:pos + TM_COUNT] = bytes(values)
            rel_ranges.append((pos, pos + TM_COUNT))
        compatibility.append({"species": index, "national_dex": row["national_dex"],
                              "types": list(row["types"]), "enabled_before": sum(before),
                              "enabled_after": sum(values),
                              "changed_entries": sum(a != b for a, b in zip(before, values))})

    rel_result, dol_result = bytes(rel), bytes(dol)
    report = {"version": VERSION, "randomize_tm_moves": shuffle,
              "move_pool": "permutation-of-50-native-tms", "tm_count": TM_COUNT,
              "moved_tms": sum(i != source for i, source in enumerate(order)),
              "mapping": mapping, "compatibility_mode": mode, "real_species_count": len(species),
              "compatibility": compatibility,
              "offensive_guarantee": {"requested": ensure_offense,
                                      "applied": ensure_offense and mode != "original",
                                      "added": additions, "species_without_offensive_tm": unmet},
              "hms": {"count": HM_COUNT, "move_entries_unchanged": True,
                      "item_descriptions_unchanged": True, "species_compatibility_unchanged": True},
              "localized_descriptions": {"policy": "move-existing-item-description-ids-with-tm-moves",
                                         "resource_payloads_unchanged": True,
                                         "validated_original_languages": list(native_languages)},
              "rel_patch": _whitelist(current_rel, rel_result, rel_ranges),
              "dol_patch": _whitelist(current_dol, dol_result, dol_ranges)}
    return rel_result, dol_result, report


def apply_tm_rules(original_rel: bytes, current_rel: bytes, original_dol: bytes,
                   current_dol: bytes, seed: str, options, tables: dict | None = None) -> tuple[bytes, bytes, dict]:
    """Fingerprint original PAL inputs; preserve existing current DOL extensions."""
    expected = expanded_layout(original_rel)  # Validates the original REL SHA-256.
    dol_region, rel_region = dol_layout(original_dol), region_for_rel(original_rel)
    if dol_region.game_id != rel_region.game_id:
        raise FormatError("original TM DOL and REL regions differ")
    if tables is not None and any(tables.get(key) != expected[key] for key in ("species", "moves")):
        raise FormatError("provided TM table layout differs from the fingerprinted original")
    if len(species_catalog(original_rel, expected)) != 386:
        raise FormatError("unexpected original real-species count for TM rules")
    return apply_tm_tables(original_rel, current_rel, original_dol, current_dol, seed, options, expected,
                           tm_offset=dol_region.tm_table_offset, item_offset=dol_region.item_table_offset,
                           native_languages=rel_region.native_languages)
