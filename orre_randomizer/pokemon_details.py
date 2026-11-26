"""Read final ROM bytes for Pokémon sheets; never draw or modify game data.

Properties come from the final REL/DOL. The BSD name catalog supplies missing
translations and restores diacritics in displayed names.
"""
from __future__ import annotations

import copy
from unicodedata import combining, normalize
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
COLOSSEUM_SHADOW_RUSH = 356


def display_name(row: dict, language: str = "fr") -> str:
    """Accept both a sheet/name map and legacy final-report rows."""
    names = row.get("names", {})
    return (names.get(language) or row.get("name_" + language)
            or names.get("en") or row.get("name_en")
            or str(row.get("national_dex", row.get("species", "?"))))


def _without_accents(letter: str) -> str:
    return "".join(char for char in normalize("NFD", letter) if not combining(char))


def _display_localized_name(name: str, reference: str | None, language: str) -> str:
    if language == "ja" or not reference or name == reference:
        return name.capitalize()

    # Only restore missing accents when the letters match. Keep native
    # abbreviations, spellings, spaces, hyphens and apostrophes.
    name = normalize("NFC", name.lower())
    native = [letter for letter in name if letter.isalpha()]
    localized = [letter for letter in normalize("NFC", reference.lower()) if letter.isalpha()]
    native_plain = [_without_accents(letter) for letter in native]
    if native_plain == [_without_accents(letter) for letter in localized]:
        restored = iter(accented if original == plain else original
                        for original, plain, accented in zip(native, native_plain, localized, strict=True))
        name = "".join(next(restored) if char.isalpha() else char for char in name)
    return name.capitalize()


def _display_move_name(row: dict, language: str) -> str:
    if row.get("canonical_move_id") in (574, 577, 583, 584, 585, 605, 608):
        from .fairy_data import move_name
        reference = move_name(row["canonical_move_id"], language)
    else:
        reference = MOVE_NAMES.get(language, {}).get(row.get("move"))
    return _display_localized_name(display_name(row, language), reference, language)


def display_species_name(national_dex: int | None, language: str, name: str | None = None) -> str:
    reference = SPECIES_NAMES[language].get(national_dex)
    return _display_localized_name(name or reference or (f"#{national_dex}" if national_dex else "?"),
                                   reference, language)


def _name_map(identifier: int, names: dict, fallback: dict) -> dict[str, str]:
    return {language: next((names.get(bank, {}).get(identifier) for bank in _BANKS[language]
                            if names.get(bank, {}).get(identifier)), fallback[language])
            for language in LANGUAGES}


def _type_names(types) -> dict[str, list[str]]:
    from .fairy_data import type_name
    return {language: [type_name(language) if index == 19 else TYPE_NAMES[language].get(index, "???") for index in dict.fromkeys(types)]
            for language in LANGUAGES}


def append_fairy_details(species: dict, moves: dict, tms: list, dol: bytes,
                         report: dict, game_id: str) -> dict:
    """Add only rows/TMs verified in this final DOL, never a prepared preview guess."""
    from .fairy_tms import read_installed_content
    from .fairy_gameplay import catalog_from_rows, current_context
    from .fairy_data import move_name, move_description
    if report.get("game_id") != game_id:
        raise FormatError("Fairy details and installed runtime belong to different games")
    installed = read_installed_content(dol, report)
    context = current_context(game_id)
    if context is not None and installed["moves"] != context.move_rows:
        raise FormatError("Installed Fairy moves differ from the generation reference")
    catalog = catalog_from_rows(game_id, installed["moves"])
    for index, row in catalog.items():
        canonical = row["canonical_move_id"]
        moves[str(index)] = {"move": index, "canonical_move_id": canonical,
            "names": {language: move_name(canonical, language) for language in LANGUAGES},
            "descriptions": {language: move_description(canonical, language) for language in LANGUAGES},
            "type": row["type"], "type_names": _type_names([row["type"]]),
            "pp": row["pp"], "power": row["power"], "accuracy": row["accuracy"],
            "damage_class": row["damage_class"], "effect": row["effect"],
            "native_row_verified": True}
    native = {row["tm"]: row["move"] for row in tms}
    actual = {row["tm"]: row["move"] for row in installed["tms"]}
    if any(actual.get(number) != move for number, move in native.items()):
        raise FormatError("Fairy TM details disagree with the native final table")
    if set(actual) != set(range(1, 58)):
        raise FormatError("Fairy TM details do not contain all 57 machines")
    tms[:] = [dict(row) for row in installed["tms"]]
    for sheet in species.values():
        compatibility = installed["compatibility"][sheet["national_dex"]]
        sheet["compatible_tms"] = [number for number in sheet["compatible_tms"] if number <= 50]
        sheet["compatible_tms"].extend(51 + index for index, enabled in enumerate(compatibility) if enabled)
    return installed


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
    item = EVOLUTION_ITEM_NAMES.get(language, {}).get(condition) or (item_names or {}).get(language)
    result = detail_text(key, language, level=condition,
                         item=item.capitalize() if item else detail_text("item", language, id=condition))
    if method in (2, 3, 5, 6, 15):
        result += " " + detail_text("unavailable", language)
    return result


def build_detail_catalog(original_rel: bytes, final_rel: bytes, original_dol: bytes,
                         final_dol: bytes, *, tables: dict | None = None,
                         symbols: list | None = None, names: dict | None = None,
                         dol_info=None, summary: dict | None = None, fairy_report: dict | None = None) -> dict:
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
    move_table = tables["moves"]
    check_range(final_rel, move_table["offset"], move_table["count"] * move_table["stride"], "final move table")
    moves = {}
    for index in range(1, move_table["count"]):
        position = move_table["offset"] + index * move_table["stride"]
        identifier = u32(final_rel, position + 0x20)
        if not identifier:
            continue
        type_id = final_rel[position + 2]
        if index == COLOSSEUM_SHADOW_RUSH:
            fallback = {language: detail_text("colosseum_shadow_rush", language) for language in LANGUAGES}
            type_names = {language: [detail_text("shadow_type", language)] for language in LANGUAGES}
        else:
            fallback = {language: MOVE_NAMES[language].get(index,
                        detail_text("move_marker", language, id=index)) for language in LANGUAGES}
            type_names = _type_names([type_id])
        moves[str(index)] = {"move": index, "names": _name_map(identifier, names, fallback),
            "type": type_id, "type_names": type_names,
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
            sheet["evolutions"].append({"target_species": target,
                "target_national_dex": species[str(target)]["national_dex"],
                "names": dict(species[str(target)]["names"]), "method": method, "condition": condition,
                "accessible_in_colosseum": method not in (2, 3, 5, 6, 15),
                "texts": {language: evolution_text(method, condition, language=language)
                          for language in LANGUAGES}})
        for slot in range(19):
            position = offset + 0xBA + slot * 4
            level, move = final_rel[position], u16(final_rel, position + 2)
            if level and move:
                sheet["learnset"].append({"level": level, "move": move})
    check_range(final_dol, region.tm_table_offset, 50 * 8, "final TM table")
    tms = [{"tm": number + 1, "move": u16(final_dol, region.tm_table_offset + number * 8 + 6)}
           for number in range(50)]
    if fairy_report is None:
        fairy_report = (summary or {}).get("fairy", {}).get("additional_tms")
    if fairy_report is not None:
        append_fairy_details(species, moves, tms, final_dol, fairy_report, getattr(region, "game_id", None))
    if any(str(row["move"]) not in moves for sheet in species.values() for row in sheet["learnset"]):
        raise FormatError("invalid final level-up move")
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


def append_postgame_trainer_details(catalog: dict, final_rel: bytes, event: dict) -> None:
    """Read the appended encounter from final bytes, keeping native rows intact."""
    if not event.get("enabled"):
        return
    trainer_id = event["trainer_id"]
    if any(row["trainer_id"] == trainer_id for row in catalog["trainers"]):
        raise FormatError("duplicate bonus trainer in final details")
    tables = event["tables"]
    trainer_table, party = tables["trainers"], tables["trainer_pokemon"]
    at = trainer_table["offset"] + trainer_id * trainer_table["stride"]
    check_range(final_rel, at, trainer_table["stride"], "bonus trainer details")
    first = u16(final_rel, at + 4)
    if first != event["first_party_slot"] or first + 6 > party["count"]:
        raise FormatError("bonus details team out of bounds")
    original = next((row for row in catalog["trainers"] if row["trainer_id"] == 437), None)
    if original is None or u32(final_rel, at + 8) != event["opponent"]["name_id"]:
        raise FormatError("missing native bonus opponent name")
    team = []
    for slot in range(first, first + 6):
        position = party["offset"] + slot * party["stride"]
        check_range(final_rel, position, party["stride"], "bonus team details")
        row = {"slot_index": slot, "species": u16(final_rel, position + 0xA),
               "level": final_rel[position + 4], "shadow_id": final_rel[position + 3],
               "moves": [u16(final_rel, position + field) for field in (0x36, 0x3E, 0x46, 0x4E)],
               "held_item": u16(final_rel, position + 0x12)}
        if str(row["species"]) not in catalog["species"]:
            raise FormatError("invalid bonus team species in details")
        team.append(row)
    if (team[-1]["species"], team[-1]["shadow_id"]) != (event["species"], 96):
        raise FormatError("bonus team details lost Shadow Lugia")
    catalog["trainers"].append({"trainer_id": trainer_id, "class_id": final_rel[at + 3],
        "names": dict(original["names"]), "team": team, "battle_ids": [event["battle_id"]],
        "event": "postgame_shadow_lugia"})
    shadow = dict(team[-1], trainer_ids=[trainer_id])
    catalog["shadows"]["96"] = {**shadow, "variants": [shadow]}


def encounter_details(catalog: dict, species_index: int, *, level: int | None = None,
                      moves=None, shadow: bool = False, deoxys_form: int | None = None) -> dict:
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
            if 375 <= index <= 381:
                raise FormatError("The additional Fairy move is not present in this final ROM snapshot")
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
            chain.append({**copy.deepcopy(branch), "source_species": current, "source_national_dex": source["national_dex"],
                          "source_names": dict(source["names"])})
            pending.append((branch["target_species"], ancestors | {current}))
    result["evolution_chain"] = chain
    if deoxys_form is not None:
        from .deoxys_presentation import decorate_encounter
        decorate_encounter({'species': species_index, 'key': 'sheet', 'details': result},
            {**catalog.get('deoxys_forms', {}), 'encounters': {'special:sheet': deoxys_form}}, artwork=False)
    return result


def format_detail_lines(details: dict, language: str = "fr") -> list[str]:
    """Compact plain text for native dialogs, tooltips and accessible output."""
    language = language if language in LANGUAGES else "en"
    lines = [display_species_name(details["national_dex"], language, display_name(details, language))]
    if details.get("level") is not None:
        lines.append(detail_text("level", language, level=details["level"]))
    lines.extend((detail_text("types", language) + " : " + " / ".join(details["type_names"][language]),
                  detail_text("abilities", language) + " : " + " / ".join(details["ability_names"][language]),
                  detail_text("ability_note", language)))
    for key, rows in detail_sections(details, language).items():
        lines.extend(("", detail_text(key, language), *rows))
    return lines


def detail_sections(details: dict, language: str, *, include_move_types: bool = True) -> dict[str, list[str]]:
    sections = {}
    for key, show in (("initial_shadow_moves", bool(details.get("initial_shadow_moves"))),
                      ("moves", details.get("moves_known"))):
        if not show:
            continue
        moves = []
        for row in details[key]:
            value = _display_move_name(row, language)
            if not row.get("special_marker"):
                if include_move_types:
                    value += " · " + " / ".join(row["type_names"][language])
                value += f" · PP {row['pp']}"
                value += " · " + detail_text("power", language) + " " + (str(row['power']) if row['power'] > 1 else "-")
                value += " · " + detail_text("accuracy", language) + " " + (str(row['accuracy']) if row['accuracy'] else "-")
            moves.append(value)
        sections[key] = moves or [detail_text("none", language)]
    sections["stats"] = [" · ".join(detail_text(key, language) + " " + str(details["base_stats"][key])
                                    for key in STAT_NAMES)]
    evolutions = []
    if details.get("shadow"):
        evolutions.append(detail_text("shadow_first", language))
    if details["evolutions"]:
        for row in details["evolution_chain"]:
            source = display_species_name(row["source_national_dex"], language, row["source_names"][language])
            target = display_species_name(row["target_national_dex"], language, display_name(row, language))
            evolutions.append(source + " → " + target + " : " + row["texts"][language])
    else:
        evolutions.append(detail_text("no_evolution", language))
    sections["evolutions"] = evolutions
    sections["learnset"] = [detail_text("level", language, level=row["level"]) + " · "
                            + _display_move_name(row["details"], language) for row in details["learnset"]]
    sections["tms"] = [detail_text("tm", language) + f" {row['tm']:02d} · "
                       + _display_move_name(row["details"], language) for row in details["tms"]]
    for key in ("learnset", "tms"):
        if not sections[key]:
            sections[key] = [detail_text("none", language)]
    return sections
