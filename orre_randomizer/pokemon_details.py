"""Read final ROM bytes for Pokémon sheets; never draw or modify game data.

Properties come from the final REL/DOL, not from modern Pokédex data. The BSD
name catalog is used only when a monolingual ROM lacks the UI language.
"""
from __future__ import annotations

import copy
from .detail_texts import LANGUAGES, detail_text
from .engine.analyze_game import FormatError, check_range, u32
from .engine.dol_regions import dol_layout, special_targets
from .engine.gameplay_rules import expanded_layout
from .engine.inspect_tables import localized_names, u16
from .engine.randomize_trainers import layout
from .engine.species_rules import species_catalog
from .locales.detail_names import ABILITY_NAMES, EVOLUTION_ITEM_NAMES, MOVE_NAMES
from .locales.selection_names import SPECIES_NAMES, TYPE_NAMES

_BANKS = {"fr": ("FR",), "en": ("UK", "US"), "de": ("GE",),
          "es": ("SP",), "it": ("IT",), "ja": ("JP",)}
STAT_NAMES = ("hp", "attack", "defense", "sp_attack", "sp_defense", "speed")


def display_name(row: dict, language: str = "fr") -> str:
    """Accept both a sheet/name map and legacy final-report rows."""
    names = row.get("names", {})
    return (names.get(language) or row.get("name_" + language)
            or names.get("en") or row.get("name_en")
            or str(row.get("national_dex", row.get("species", "?"))))


def _name_map(identifier: int, names: dict, fallback: dict) -> dict[str, str]:
    return {language: next((names.get(bank, {}).get(identifier) for bank in _BANKS[language]
                            if names.get(bank, {}).get(identifier)), fallback[language])
            for language in LANGUAGES}


def _type_names(types) -> dict[str, list[str]]:
    return {language: [TYPE_NAMES[language].get(index, "???") for index in dict.fromkeys(types)]
            for language in LANGUAGES}


def evolution_text(method: int, condition: int, *, language: str = "fr",
                   item_names: dict | None = None) -> str:
    """Describe the actual final method/condition; no options-based guess."""
    key = {1: "evo_friend", 2: "evo_day", 3: "evo_night", 4: "evo_level",
           5: "evo_trade", 6: "evo_trade_item", 7: "evo_item", 8: "evo_attack",
           9: "evo_equal", 10: "evo_defense", 11: "evo_personality",
           12: "evo_personality", 13: "evo_level", 14: "evo_shedinja", 15: "evo_beauty",
           16: "evo_key_item"}.get(method)
    if key is None:
        raise FormatError(f"unsupported final evolution method {method}")
    item = (item_names or {}).get(language) or EVOLUTION_ITEM_NAMES.get(language, {}).get(condition)
    item = item or detail_text("item", language, id=condition)
    result = detail_text(key, language, level=condition, item=item)
    if method in (2, 3, 5, 6, 15):
        result += " " + detail_text("unavailable", language)
    return result


def build_detail_catalog(original_rel: bytes, final_rel: bytes, original_dol: bytes,
                         final_dol: bytes, *, tables: dict | None = None,
                         symbols: list | None = None, names: dict | None = None,
                         dol_info=None, summary: dict | None = None) -> dict:
    """Build a JSON-only snapshot once, after every gameplay transformation.

    Production layout selection fingerprints the original artifacts. Explicit
    layouts/name banks support the same pure reader on bounded test fixtures.
    Nothing is written, no option is changed, and no RNG is called.
    """
    if len(original_rel) != len(final_rel) or len(final_dol) < len(original_dol):
        raise FormatError("final details artifact lengths differ")
    if tables is None or symbols is None:
        found_tables, found_symbols = layout(original_rel)
        tables = found_tables if tables is None else tables
        symbols = found_symbols if symbols is None else symbols
    tables = dict(tables)
    if "moves" not in tables:
        tables["moves"] = expanded_layout(original_rel)["moves"]
    if names is None:
        names, _ = localized_names(final_rel, symbols)
    region = dol_info or dol_layout(original_dol)
    native = species_catalog(original_rel, tables)
    final = species_catalog(final_rel, tables)
    if {i: r["national_dex"] for i, r in native.items()} != {i: r["national_dex"] for i, r in final.items()}:
        raise FormatError("final details species identities differ")
    species = {}
    for index, row in final.items():
        offset, national = row["offset"], row["national_dex"]
        check_range(final_rel, offset, 0x106, "final species details")
        species[str(index)] = {
            "species": index, "national_dex": national,
            "names": _name_map(u32(final_rel, offset + 0x18), names,
                                {language: SPECIES_NAMES[language][national] for language in LANGUAGES}),
            "types": list(dict.fromkeys(row["types"])), "type_names": _type_names(row["types"]),
            "abilities": list(dict.fromkeys(a for a in row["abilities"] if a)),
            "ability_names": {language: [ABILITY_NAMES[language].get(a, str(a))
                for a in dict.fromkeys(a for a in row["abilities"] if a)] for language in LANGUAGES},
            "base_stats": dict(zip(STAT_NAMES, row["stats"], strict=True)),
            "base_stat_total": row["total"], "evolutions": [], "learnset": [],
            "compatible_tms": [slot + 1 for slot in range(50) if final_rel[offset + 0x34 + slot]],
        }
    items = {}
    for index in EVOLUTION_ITEM_NAMES["en"]:
        position = region.item_table_offset + index * 0x28 + 0x10
        check_range(final_dol, position, 4, "evolution item name")
        items[str(index)] = _name_map(u32(final_dol, position), names,
            {language: EVOLUTION_ITEM_NAMES[language][index] for language in LANGUAGES})
    move_table = tables["moves"]
    check_range(final_rel, move_table["offset"], move_table["count"] * move_table["stride"], "final move table")
    moves = {}
    for index in range(1, move_table["count"]):
        position = move_table["offset"] + index * move_table["stride"]
        identifier = u32(final_rel, position + 0x20)
        if not identifier:
            continue
        fallback = {language: MOVE_NAMES[language].get(index,
                    detail_text("move_marker", language, id=index)) for language in LANGUAGES}
        moves[str(index)] = {"move": index, "names": _name_map(identifier, names, fallback),
            "type": final_rel[position + 2], "type_names": _type_names([final_rel[position + 2]]),
            "pp": final_rel[position + 1], "power": final_rel[position + 0x17],
            "accuracy": final_rel[position + 4]}
    for index, row in final.items():
        offset = row["offset"]
        sheet = species[str(index)]
        for slot in range(5):
            position = offset + 0x9C + slot * 6
            method = final_rel[position]
            condition, target = u16(final_rel, position + 2), u16(final_rel, position + 4)
            if not method:
                if condition or target:
                    raise FormatError("unused final evolution slot is not empty")
                continue
            if str(target) not in species:
                raise FormatError("invalid final evolution target")
            item_names = items.get(str(condition), {}) if method in (6, 7) else {}
            sheet["evolutions"].append({"target_species": target,
                "target_national_dex": species[str(target)]["national_dex"],
                "names": dict(species[str(target)]["names"]), "method": method, "condition": condition,
                "accessible_in_colosseum": method not in (2, 3, 5, 6, 15),
                "texts": {language: evolution_text(method, condition, language=language, item_names=item_names)
                          for language in LANGUAGES}})
        for slot in range(19):
            position = offset + 0xBA + slot * 4
            level, move = final_rel[position], u16(final_rel, position + 2)
            if level and move:
                if str(move) not in moves:
                    raise FormatError("invalid final level-up move")
                sheet["learnset"].append({"level": level, "move": move})
    check_range(final_dol, region.tm_table_offset, 50 * 8, "final TM table")
    tms = [{"tm": number + 1, "move": u16(final_dol, region.tm_table_offset + number * 8 + 6)}
           for number in range(50)]
    if any(str(row["move"]) not in moves for row in tms):
        raise FormatError("invalid final TM move")
    trainers = []
    shadow_variants = {}
    trainer_table, pokemon_table = tables["trainers"], tables["trainer_pokemon"]
    for trainer_id in range(trainer_table["count"]):
        position = trainer_table["offset"] + trainer_id * trainer_table["stride"]
        check_range(final_rel, position, trainer_table["stride"], "final trainer")
        first = u16(final_rel, position + 4)
        if not first:
            continue
        if first + 6 > pokemon_table["count"]:
            raise FormatError("final trainer team out of bounds")
        team = []
        for slot in range(first, first + 6):
            at = pokemon_table["offset"] + slot * pokemon_table["stride"]
            check_range(final_rel, at, pokemon_table["stride"], "final trainer Pokémon")
            index = u16(final_rel, at + 0xA)
            if not index:
                continue
            if str(index) not in species:
                raise FormatError("final team species out of bounds")
            encounter = {"slot_index": slot, "species": index, "level": final_rel[at + 4],
                "shadow_id": final_rel[at + 3], "moves": [u16(final_rel, at + field)
                for field in (0x36, 0x3E, 0x46, 0x4E)], "held_item": u16(final_rel, at + 0x12)}
            team.append(encounter)
            if encounter["shadow_id"]:
                variants = shadow_variants.setdefault(str(encounter["shadow_id"]), {})
                if slot not in variants:
                    variants[slot] = dict(encounter, trainer_ids=[])
                variants[slot]["trainer_ids"].append(trainer_id)
        if team:
            identifier = u32(final_rel, position + 8)
            native_name = next((bank[identifier] for bank in names.values() if identifier in bank), None)
            trainers.append({"trainer_id": trainer_id, "class_id": final_rel[position + 3],
                "names": _name_map(identifier, names,
                    {language: native_name or detail_text("trainer", language, id=trainer_id)
                     for language in LANGUAGES}), "team": team})
    shadows = {}
    shadow_table = tables["shadow"]
    for sid, variants in shadow_variants.items():
        position = shadow_table["offset"] + int(sid) * shadow_table["stride"]
        check_range(final_rel, position, shadow_table["stride"], "final Shadow metadata")
        preferred = u16(final_rel, position + 4)
        ordered = sorted(variants.values(), key=lambda row: (preferred not in row["trainer_ids"], row["slot_index"]))
        shadows[sid] = {**ordered[0], "variants": ordered}
    specials = {}
    final_specials = {r["key"]: r for r in (summary or {}).get("special_gameplay", {}).get("specials", [])}
    # The production constructor's fixed starter move instructions and gift
    # overrides are authoritative. Native unoverridden gifts use their learnset.
    if dol_info is None:
        for target in special_targets(original_dol):
            key, position = target["key"], target["base"]
            index, level = u16(final_dol, position + 2), u16(final_dol, position + 6)
            if str(index) not in species:
                raise FormatError("final special species out of bounds")
            if "xp" in target:
                encounter_moves = [u16(final_dol, position + 0x16 + slot * 0x10) for slot in range(4)]
            elif "moves" in final_specials.get(key, {}):
                encounter_moves = list(final_specials[key]["moves"])
            else:
                encounter_moves = []
                for learned in species[str(index)]["learnset"]:
                    if learned["level"] <= level:
                        if learned["move"] in encounter_moves:
                            encounter_moves.remove(learned["move"])
                        encounter_moves.append(learned["move"])
                encounter_moves = encounter_moves[-4:]
                encounter_moves += [0] * (4 - len(encounter_moves))
            specials[key] = {"species": index, "level": level, "moves": encounter_moves}
    return {"schema": 1, "scope": "Final REL/DOL bytes; presentation-only fallback names",
            "game_id": getattr(region, "game_id", None), "species": species,
            "moves": moves, "tms": tms, "trainers": trainers, "shadows": shadows, "specials": specials}


def encounter_details(catalog: dict, species_index: int, *, level: int | None = None,
                      moves=None, shadow: bool = False) -> dict:
    """Select an immutable sheet, adding encounter-specific moves when known."""
    try:
        result = copy.deepcopy(catalog["species"][str(species_index)])
    except (KeyError, TypeError):
        raise FormatError("Pokémon details are not available for this species") from None
    result.update(level=level, shadow=shadow,
                  ability_is_determined_in_game=True, values_scope="final-patched-rom")
    selected = []
    for index in moves or ():
        if not index:
            continue
        row = catalog["moves"].get(str(index))
        if row is None:
            row = {"move": index, "names": {language: detail_text("move_marker", language, id=index)
                    for language in LANGUAGES}, "special_marker": True}
        selected.append(copy.deepcopy(row))
    result["moves"] = selected
    result["moves_known"] = moves is not None
    result["learnset"] = [{**entry, "details": copy.deepcopy(catalog["moves"][str(entry["move"])])}
                           for entry in result["learnset"]]
    result["tms"] = [{**entry, "details": copy.deepcopy(catalog["moves"][str(entry["move"])])}
                      for entry in catalog["tms"] if entry["tm"] in result["compatible_tms"]]
    chain, visited, pending = [], set(), [(species_index, frozenset())]
    while pending:
        current, ancestors = pending.pop(0)
        if current in ancestors:
            raise FormatError("final evolution chain contains a cycle")
        if current in visited:
            continue
        visited.add(current)
        source = catalog["species"][str(current)]
        for branch in source["evolutions"]:
            chain.append({**copy.deepcopy(branch), "source_species": current,
                          "source_names": dict(source["names"])})
            pending.append((branch["target_species"], ancestors | {current}))
    result["evolution_chain"] = chain
    return result


def format_detail_lines(details: dict, language: str = "fr") -> list[str]:
    """Compact plain text for native dialogs, tooltips and accessible output."""
    language = language if language in LANGUAGES else "en"
    lines = [display_name(details, language)]
    if details.get("level") is not None:
        lines.append(detail_text("level", language, level=details["level"]))
    lines.extend((detail_text("types", language) + " : " + " / ".join(details["type_names"][language]),
                  detail_text("abilities", language) + " : " + " / ".join(details["ability_names"][language]),
                  detail_text("ability_note", language)))
    for key, rows in detail_sections(details, language).items():
        lines.extend(("", detail_text(key, language), *rows))
    return lines


def detail_sections(details: dict, language: str) -> dict[str, list[str]]:
    sections = {}
    if details.get("moves_known"):
        moves = []
        for row in details["moves"]:
            value = display_name(row, language)
            if not row.get("special_marker"):
                value += " · " + " / ".join(row["type_names"][language]) + f" · PP {row['pp']}"
                value += " · " + detail_text("power", language) + " " + (str(row['power']) if row['power'] > 1 else "—")
                value += " · " + detail_text("accuracy", language) + " " + (str(row['accuracy']) if row['accuracy'] else "—")
            moves.append(value)
        sections["moves"] = moves or [detail_text("none", language)]
    sections["stats"] = [" · ".join(detail_text(key, language) + " " + str(details["base_stats"][key])
                                    for key in STAT_NAMES)]
    evolutions = []
    if details.get("shadow"):
        evolutions.append(detail_text("shadow_first", language))
    if details["evolutions"]:
        evolutions.extend(row["source_names"][language] + " → " + display_name(row, language)
                          + " : " + row["texts"][language] for row in details["evolution_chain"])
    else:
        evolutions.append(detail_text("no_evolution", language))
    sections["evolutions"] = evolutions
    sections["learnset"] = [detail_text("level", language, level=row["level"]) + " · "
                            + display_name(row["details"], language) for row in details["learnset"]]
    sections["tms"] = [detail_text("tms", language) + f" {row['tm']:02d} · "
                       + display_name(row["details"], language) for row in details["tms"]]
    for key in ("learnset", "tms"):
        if not sections[key]:
            sections[key] = [detail_text("none", language)]
    return sections
