"""Seeded species choices and dialogue for scripted XD encounters."""
from collections import Counter
from functools import partial
import struct

from .engine.analyze_game import FormatError, check_range
from .engine.gameplay_rules import OHKO, SELF_DESTRUCT, damaging
from .engine.species_rules import LEGENDARY_NATIONAL, WONDER_GUARD
from .xd_gifts import _native_name, _patch_banks, _patch_script, patch_species_operand, replace_species_name


TUTORIAL_SHADOW = 1
TEDDIURSA = 216
STARTER_DIALOGUE_ARCHIVE = "M5_labo_2F.fsys"
_IMMUNE_TYPES = {0: 7, 1: 7, 3: 8, 4: 2, 7: 0, 13: 4, 14: 17}
_ABSORB_ABILITIES = {4: 26, 10: 18, 11: 11, 13: 10}
_CONDITIONAL_ATTACKS = OHKO | SELF_DESTRUCT | {68, 117, 138, 173, 243, 255}


def tutorial_candidates(starter, eligible, move_randomizer):
    """Exclude opponents that the starter's regular attacks cannot hit."""
    catalog = move_randomizer.species
    attacks = [move_randomizer.catalog[move] for move in starter["moves"]
               if move in move_randomizer.catalog and move not in _CONDITIONAL_ATTACKS
               and damaging(move_randomizer.catalog[move])]
    result = []
    for index in sorted(eligible):
        row = catalog[index]
        if (index == TEDDIURSA or row["national_dex"] in LEGENDARY_NATIONAL
                or row["total"] > 410 or WONDER_GUARD in row["abilities"]):
            continue
        for move in attacks:
            kind = move["type"]
            if (_IMMUNE_TYPES.get(kind) not in row["types"]
                    and _ABSORB_ABILITIES.get(kind) not in row["abilities"]
                    and (move["index"] not in (253, 304) or 43 not in row["abilities"])):
                result.append(index)
                break
    return result


def hordel_candidates(eligible, edges, families, *, accessible_evolutions):
    """Pick base forms with a single evolution that players can reach in XD."""
    family_sizes = Counter(families.values())
    methods = {4, 7} | ({5, 6, 15} if accessible_evolutions else set())
    result = {}
    for base in sorted(eligible):
        routes = edges.get(base, ())
        if family_sizes[families[base]] == 2 and len(routes) == 1:
            _, method, _, evolved = routes[0]
            if method in methods and not edges.get(evolved):
                result[base] = evolved
    return result


def patch_starter_dialogue(source, game_id, national, name_banks):
    def edits(language):
        native = _native_name(name_banks, language, 133).encode("utf-16-be")
        chosen = _native_name(name_banks, language, national).encode("utf-16-be")

        def replace_starter(original):
            if original.count(native) != 2:
                raise FormatError("unexpected starter names in the XD lab dialogue")
            return original.replace(native, chosen)

        return {0x9C42: replace_starter}

    return _patch_banks(source, game_id, edits)


def patch_tutorial(game_id, chosen, national, name_banks, read_archive):
    def edit_script(original):
        offset = 0x816C if game_id == "GXXJ01" else 0x818C
        check_range(original, offset - 4, 28, "XD tutorial dialogue variable")
        if struct.unpack_from(">7I", original, offset - 4) != (
            0x02010000, TEDDIURSA, 0x02010000, 0x4E, 0x11030028, 0x0928001C, 0x06030000,
        ):
            raise FormatError("unexpected XD tutorial dialogue variable")
        updated = bytearray(original)
        patch_species_operand(original, updated, offset, TEDDIURSA, chosen)
        return bytes(updated)

    def edits(language, message):
        old = _native_name(name_banks, language, TEDDIURSA)
        new = _native_name(name_banks, language, national)
        return {message: partial(replace_species_name, language=language, old=old, chosen=new)}

    lab = "M5_labo_1F.fsys"
    rematch = "D1_labo_B2.fsys"
    archives = {
        lab: _patch_banks(_patch_script(read_archive(lab), "M5_labo_1F", edit_script),
                          game_id, lambda lang: edits(lang, 0x9CDD)),
        rematch: _patch_banks(read_archive(rematch), game_id, lambda lang: edits(lang, 0x759E)),
    }
    fight_banks = {"GXXP01": {"": "UK", "_fr": "FR", "_ge": "GE", "_it": "IT", "_sp": "SP"},
                   "GXXE01": {"": "US"}, "GXXJ01": {"": "JP"}}
    for suffix, language in fight_banks[game_id].items():
        name = f"fight_common{suffix}.fsys"
        archives[name] = _patch_banks(read_archive(name), game_id, lambda lang: edits(lang, 0x5688),
                                      languages={language})
    return archives
