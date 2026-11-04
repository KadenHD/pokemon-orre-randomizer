"""Seeded XD species, moves and TM changes for the three verified retail discs."""
from __future__ import annotations

from dataclasses import replace
import struct

from .engine.analyze_game import FormatError, check_range, u32
from .engine.gameplay_rules import choose_moves, damaging, pick
from .engine.inspect_tables import u16
from .engine.species_rules import SHEDINJA_NATIONAL, VALID_TYPES, WONDER_GUARD, _redistribute
from .engine.tm_rules import ORIGINAL_HM_MOVES, ORIGINAL_TM_MOVES, UNSAFE_OFFENSE


VERSION = "xd-species-gameplay-v1"
SPECIES_STRIDE = 0x124
STAT_FIELDS = (0x8E, 0x90, 0x92, 0x94, 0x96, 0x98)
LAST_REGULAR_MOVE = 354
TM_OFFSETS = {"GXXP01": 0x43CC80, "GXXE01": 0x4023A0, "GXXJ01": 0x3DFA60}
TM_COUNT, TM_STRIDE, FIRST_TM_ITEM = 50, 8, 0x121


def _table(rel, symbols, index, count, stride):
    start = symbols[index]["offset"]
    if u32(rel, symbols[index + 1]["offset"]) != count:
        raise FormatError(f"unexpected XD table count at symbol {index}")
    check_range(rel, start, count * stride, "XD gameplay table")
    return start


def _species_catalog(rel, symbols, species):
    start = _table(rel, symbols, 88, 415, SPECIES_STRIDE)
    result = {}
    for index, (national, *_rest) in sorted(species.items()):
        pos = start + index * SPECIES_STRIDE
        types = tuple(rel[pos + 0x30:pos + 0x32])
        abilities = tuple(rel[pos + 0x32:pos + 0x34])
        stats = tuple(u16(rel, pos + field) for field in STAT_FIELDS)
        if (u16(rel, pos + 0xE) != national or not set(types) <= VALID_TYPES
                or not abilities[0] or max(abilities) > 77 or not all(0 < value <= 255 for value in stats)):
            raise FormatError("invalid XD species properties")
        result[index] = {"national_dex": national, "offset": pos, "types": types,
                         "abilities": abilities, "stats": stats, "total": sum(stats)}
    return result


def _move_catalog(rel, symbols):
    # XD uses 0x38-byte move rows. Ordinary moves precede the Shadow block.
    stride = 0x38
    start = _table(rel, symbols, 124, 375, stride)
    result = {}
    for index in range(1, LAST_REGULAR_MOVE + 1):
        pos = start + index * stride
        if not rel[pos + 1] or u32(rel, pos + 0x20) != 2000 + index:
            raise FormatError("unexpected XD regular move record")
        if index != 165:  # Struggle is engine-controlled.
            result[index] = {"index": index, "pp": rel[pos + 1], "type": rel[pos + 2],
                             "power": rel[pos + 0x19], "accuracy": rel[pos + 4],
                             "effect": u16(rel, pos + 0x1C)}
    return result


class XDMoveRandomizer:
    """Draw normal moves from the native XD catalog using final types and stats."""

    def __init__(self, rel, symbols, species, options):
        self.species = _species_catalog(rel, symbols, species)
        self.catalog = _move_catalog(rel, symbols)
        self.options = options

    def moves(self, seed, key, species_id, level, originals):
        """Fill regular slots while preserving any native Shadow or scripted move."""
        result = list(originals)
        slots = [i for i, value in enumerate(result) if value == 0 or value in self.catalog]
        chosen = choose_moves(seed, f"{VERSION}:{key}", self.species[species_id], level,
                              self.catalog, self.options, len(slots))
        for slot, move in zip(slots, chosen, strict=True):
            result[slot] = move
        return result


def detail_catalog(rel, dol, symbols, game_id, edges, move_randomizer):
    from .engine.inspect_tables import localized_names
    from .locales.detail_names import ABILITY_NAMES, MOVE_NAMES
    from .locales.selection_names import SPECIES_NAMES
    from .pokemon_details import LANGUAGES, STAT_NAMES, _name_map, _type_names, detail_text, evolution_text

    banks, _ = localized_names(rel, symbols)
    species = {}
    for index, row in move_randomizer.species.items():
        offset, national = row["offset"], row["national_dex"]
        species[str(index)] = {
            "species": index, "national_dex": national,
            "names": {lang: SPECIES_NAMES[lang][national] for lang in LANGUAGES},
            "type_names": _type_names(row["types"]),
            "ability_names": {lang: [ABILITY_NAMES[lang].get(ability, str(ability))
                                     for ability in dict.fromkeys(row["abilities"]) if ability] for lang in LANGUAGES},
            "base_stats": dict(zip(STAT_NAMES, row["stats"], strict=True)),
            "base_stat_total": row["total"],
            "learnset": [{"level": rel[pos], "move": u16(rel, pos + 2)}
                         for pos in range(offset + 0xC4, offset + 0x110, 4)
                         if rel[pos] and u16(rel, pos + 2)],
            "compatible_tms": [slot + 1 for slot in range(50) if rel[offset + 0x34 + slot]],
            "evolutions": [],
        }
    items = _table(rel, symbols, 70, 444, 0x28)
    for index, routes in edges.items():
        for pos, _, _, target in routes:
            method, condition = rel[pos], u16(rel, pos + 2)
            target_row = species[str(target)]
            item_names = None
            if method in (6, 7, 16) and 0 < condition < 444:
                item_names = _name_map(u32(rel, items + condition * 0x28 + 0x10), banks,
                                       {lang: detail_text("item", lang, id=condition) for lang in LANGUAGES})
            species[str(index)]["evolutions"].append({
                "target_species": target, "target_national_dex": target_row["national_dex"],
                "names": target_row["names"], "method": method, "condition": condition,
                "texts": {lang: evolution_text(method, condition, language=lang, item_names=item_names)
                          for lang in LANGUAGES},
            })
    moves = {}
    table = _table(rel, symbols, 124, 375, 0x38)
    for index in range(1, 375):
        pos = table + index * 0x38
        names = {lang: MOVE_NAMES[lang].get(index, detail_text("move_marker", lang, id=index))
                 for lang in LANGUAGES}
        moves[str(index)] = {
            "move": index, "names": _name_map(u32(rel, pos + 0x20), banks, names),
            "type_names": _type_names([rel[pos + 2]]), "pp": rel[pos + 1],
            "power": rel[pos + 0x19], "accuracy": rel[pos + 4],
        }
    tm = TM_OFFSETS[game_id]
    tms = [{"tm": i + 1, "move": u16(dol, tm + 8 * i + 6)} for i in range(50)]
    return {"species": species, "moves": moves, "tms": tms}


def _draw(seed, key, pool):
    return pick(seed, f"{VERSION}:{key}", pool)


def _learnset(rel, output, seed, index, species, move_catalog, options):
    pos = species["offset"]
    slots = []
    for slot in range(19):
        entry = pos + 0xC4 + slot * 4
        level, move = rel[entry], u16(rel, entry + 2)
        if level and move in move_catalog:
            slots.append((slot, entry, level))
    plain = replace(options, ensure_damaging_move=False, ensure_stab_move=False)
    # Reserve the guaranteed move first in every rolling group of four, before
    # the other slots can consume a rare compatible offensive move.
    guarded = options.ensure_damaging_move or options.ensure_stab_move
    required = slots[::4] if guarded else []
    other = [row for ordinal, row in enumerate(slots) if not guarded or ordinal % 4]
    used = set()
    changed = 0
    for group, rules in ((required, options), (other, plain)):
        for slot, entry, level in group:
            move = choose_moves(seed, f"{VERSION}:learn:{index}:{slot}", species, level,
                                move_catalog, rules, 1, used)[0]
            struct.pack_into(">H", output, entry + 2, move)
            used.add(move)
            changed += move != u16(rel, entry + 2)
    return changed


def patch_species_gameplay(rel, symbols, seed, species, families, options):
    """Apply optional type, ability, base-stat and level-up move rules in place in the REL layout."""
    report = {"version": VERSION, "types_changed": 0, "abilities_changed": 0,
              "base_stats_changed": 0, "learnset_moves_changed": 0}
    if not (options.randomize_types or options.randomize_abilities or options.randomize_stats
            or options.randomize_learnsets):
        return rel, report
    catalog = _species_catalog(rel, symbols, species)
    ability_pool = {value for row in catalog.values() for value in row["abilities"]} - {0, WONDER_GUARD}
    output = bytearray(rel)
    for index, row in catalog.items():
        pos = row["offset"]
        shedinja = row["national_dex"] == SHEDINJA_NATIONAL
        if options.randomize_types and not shedinja:
            key = f"types:{families[index] if options.types_family_consistent else index}"
            first = _draw(seed, f"{key}:primary", VALID_TYPES)
            second = (_draw(seed, f"{key}:secondary", VALID_TYPES - {first})
                      if len(set(row["types"])) == 2 else first)
            output[pos + 0x30:pos + 0x32] = bytes((first, second))
            report["types_changed"] += (first, second) != row["types"]
        if options.randomize_abilities and not shedinja:
            key = f"abilities:{families[index] if options.abilities_family_consistent else index}"
            first = _draw(seed, f"{key}:primary", ability_pool)
            second = _draw(seed, f"{key}:secondary", ability_pool - {first}) if row["abilities"][1] else 0
            output[pos + 0x32:pos + 0x34] = bytes((first, second))
            report["abilities_changed"] += (first, second) != row["abilities"]
        if options.randomize_stats:
            total = row["total"] if options.preserve_stat_totals else _draw(seed, f"stats:{index}:total", range(250, 681))
            stats = _redistribute(seed, f"{VERSION}:stats:{index}", total, shedinja)
            for field, value in zip(STAT_FIELDS, stats, strict=True):
                struct.pack_into(">H", output, pos + field, value)
            report["base_stats_changed"] += stats != row["stats"]
    if options.randomize_learnsets:
        final = _species_catalog(output, symbols, species)
        moves = _move_catalog(rel, symbols)
        for index, row in final.items():
            report["learnset_moves_changed"] += _learnset(rel, output, seed, index, row, moves, options)
    return bytes(output), report


def patch_tm_gameplay(rel, dol, symbols, game_id, seed, species, options):
    """Shuffle native TM moves and description IDs, then update compatibility if requested."""
    shuffle, mode = options.randomize_tm_moves, options.tm_compatibility_mode
    report = {"version": VERSION, "tm_compatibility_mode": mode, "tms_moved": 0,
              "species_compatibility_changed": 0}
    if not shuffle and mode == "original":
        return rel, dol, report
    if mode not in ("original", "type", "universal", "random"):
        raise ValueError("unknown XD TM compatibility mode")
    tm_start = TM_OFFSETS[game_id]
    item_start = _table(rel, symbols, 70, 444, 0x28)
    native = ORIGINAL_TM_MOVES + ORIGINAL_HM_MOVES
    check_range(dol, tm_start, len(native) * TM_STRIDE, "XD TM/HM move table")
    for i, move in enumerate(native):
        pos = tm_start + i * TM_STRIDE
        if dol[pos:pos + TM_STRIDE] != struct.pack(">B5xH", i >= TM_COUNT, move):
            raise FormatError("unexpected native XD TM/HM record")
    descriptions = []
    for i in range(TM_COUNT):
        item = item_start + (FIRST_TM_ITEM + i) * 0x28
        if rel[item] != 4 or rel[item + 0x1B] != i or u32(rel, item + 0x14) != 10195 + i:
            raise FormatError("unexpected native XD TM item record")
        descriptions.append(item + 0x14)
    order = list(range(TM_COUNT))
    if shuffle:
        # A Sattolo cycle moves every native TM exactly once, with no fixed slot.
        for i in range(TM_COUNT - 1, 0, -1):
            target = _draw(seed, f"tm:permutation:{i}", range(i))
            order[i], order[target] = order[target], order[i]
    final = [native[i] for i in order]
    rel_out, dol_out = bytearray(rel), bytearray(dol)
    if shuffle:
        for i, source in enumerate(order):
            struct.pack_into(">H", dol_out, tm_start + i * TM_STRIDE + 6, final[i])
            struct.pack_into(">I", rel_out, descriptions[i], u32(rel, descriptions[source]))
        report["tms_moved"] = TM_COUNT
        report["tm_moves"] = final
    if mode != "original":
        catalog = _move_catalog(rel, symbols)
        rows = _species_catalog(rel, symbols, species)
        offensive = [i for i, move in enumerate(final) if move not in UNSAFE_OFFENSE and damaging(catalog[move])]
        for index, row in rows.items():
            pos = row["offset"] + 0x34
            before = rel[pos:pos + TM_COUNT]
            if not set(before) <= {0, 1}:
                raise FormatError("unexpected native XD TM compatibility")
            matching = [catalog[move]["type"] in row["types"] for move in final]
            if mode == "universal":
                enabled = [1] * TM_COUNT
            elif mode == "type":
                enabled = matching.copy()
            else:
                enabled = [_draw(seed, f"tm:compatible:{index}:{i}", (0, 1)) for i in range(TM_COUNT)]
            if options.tm_ensure_offensive and not any(enabled[i] for i in offensive):
                compatible = [i for i in offensive if matching[i]]
                enabled[_draw(seed, f"tm:offensive:{index}", compatible or offensive)] = 1
            rel_out[pos:pos + TM_COUNT] = bytes(enabled)
            report["species_compatibility_changed"] += before != bytes(enabled)
    return bytes(rel_out), bytes(dol_out), report
