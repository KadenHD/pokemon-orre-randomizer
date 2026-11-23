"""Coordinated starter selection for the two identified regional constructor calls.

Only species and EXP immediates are written. Types and BST are evaluated from
the current REL, while evolution roots and family membership use the original
graph. A fixed starter constrains its randomized partner but is never edited.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, check_range, sha256, u32
from .evolution_rules import (EVOLUTION_COUNT, EVOLUTION_OFFSET,
                              EVOLUTION_STRIDE, evolution_families, evolution_stage_info)
from .inspect_tables import u16
from .randomize_story import DOL_SHA256, SPECIALS, experience_at_level
from .randomize_trainers import layout
from .species_rules import LEGENDARY_NATIONAL, SHEDINJA_NATIONAL, species_catalog
from .pool_filters import species_excluded
from .dol_regions import special_targets
from ..move_modes import natural_moves

VERSION = "starter-pair-natural-safety-v3"
# Keep the historical domain outside automatic natural-move pair selection.
DRAW_VERSION = "starter-pair-sha256-v1"
NATURAL_DRAW_VERSION = "starter-pair-natural-safe-sha256-v1"
# Certify only these native, harmless effects. Raw power 0/1 is insufficient:
# Transform, Sketch, Counter and indirect/variable damage must remain eligible.
HARMLESS_NATURAL_EFFECTS = {100: 153, 106: 11, 150: 85}  # Teleport, Harden, Splash
STARTERS = tuple(target for target in SPECIALS if "xp" in target)
RULE_DEFAULTS = {"starter_balance_pair": False, "starter_distinct_families": False,
                 "starter_complementary_types": False, "starter_three_stage_families": False}


def _flag(options, name: str, default: bool = False) -> bool:
    value = getattr(options, name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _rules(options) -> dict:
    rules = {name: _flag(options, name, default) for name, default in RULE_DEFAULTS.items()}
    stage = (getattr(options, "starter_stage") if hasattr(options, "starter_stage") else
             "base" if _flag(options, "starter_base_forms") else "any")
    if type(stage) is not str or stage not in ("any", "base", "first", "final"):
        raise ValueError("invalid starter stage")
    return {**rules, "starter_stage": stage}


def _active(rules: dict) -> bool:
    return rules["starter_stage"] != "any" or any(rules[name] for name in RULE_DEFAULTS)


def starter_rules_active(options) -> bool:
    rules = _rules(options)
    randomized = any(_flag(options, "starter_" + target["key"]) for target in STARTERS)
    manual = any(_flag(options, "starter_" + target["key"]) and
                 getattr(options, "starter_" + target["key"] + "_species", 0) for target in STARTERS)
    return randomized and (_active(rules) or manual or
                           getattr(options, "randomize_starter_moves", False) == "natural")


def _sample(seed: str, count: int, *, domain: str = DRAW_VERSION) -> int:
    raw = seed.encode("utf-8")
    if not 1 <= len(raw) <= 256 or count < 1:
        raise ValueError("invalid starter seed or candidate count")
    prefix = domain.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big") + raw + b"\0pair\0"
    limit = (1 << 256) // count * count
    counter = 0
    while True:
        value = int.from_bytes(hashlib.sha256(prefix + counter.to_bytes(4, "big")).digest(), "big")
        if value < limit:
            return value % count
        counter += 1


def base_species(original: bytes, tables: dict) -> set[int]:
    """Species with no incoming evolution edge; single-stage species qualify."""
    families, _ = evolution_families(original, tables)  # Validate every edge first.
    table = tables["species"]
    incoming = set()
    for index in families:
        pos = table["offset"] + index * table["stride"] + EVOLUTION_OFFSET
        for slot in range(EVOLUTION_COUNT):
            edge = pos + slot * EVOLUTION_STRIDE
            if original[edge]:
                incoming.add(u16(original, edge + 4))
    return set(families) - incoming


def _candidates(target: dict, original_catalog: dict, catalog: dict,
                stages: dict, options, rules: dict) -> list[int]:
    generations = tuple(_flag(options, f"allow_gen{i}", True) for i in (1, 2, 3))
    legends = _flag(options, "allow_legendaries", True)
    choices = []
    for index, row in catalog.items():
        info = stages[index]
        national = row["national_dex"]
        generation = 0 if national <= 151 else 1 if national <= 251 else 2
        if (index == target["old"] or national == SHEDINJA_NATIONAL or not generations[generation]
                or species_excluded(original_catalog[index], options)
                or not legends and national in LEGENDARY_NATIONAL
                or rules["starter_stage"] == "base" and not info["base_form"]
                or rules["starter_stage"] == "first" and info["stage"] != 1
                or rules["starter_stage"] == "final" and not info["final_form"]
                or rules["starter_three_stage_families"] and info["family_stages"] != 3):
            continue
        choices.append(index)
    if not choices:
        if getattr(options, "excluded_species", ()) or getattr(options, "excluded_types", ()):
            raise FormatError("Aucun Pokémon admissible avec ces filtres. Autorisez d’autres espèces ou types.")
        raise FormatError("Aucun starter admissible : vérifiez les générations, légendaires, stades et familles à trois stades.")
    if _flag(options, "balance_species", False):
        # Compare the final candidate's BST to the original encounter's BST.
        # Apply all hard exclusions first, including the base-form constraint.
        target_total = original_catalog[target["old"]]["total"]
        if rules["starter_three_stage_families"] and rules["starter_stage"] == "base":
            # Compare the new three-stage bases to Eevee, not to its evolved 525-BST forms.
            # Existing profiles have this new filter disabled and retain the v1 window.
            target_total = max(original_catalog[index]["total"]
                               for index in stages[target["old"]]["base_species"])
        tolerance = max(50, target_total // 5)
        close = [index for index in choices if abs(catalog[index]["total"] - target_total) <= tolerance]
        if close:
            choices = close
        else:
            nearest = min(abs(catalog[index]["total"] - target_total) for index in choices)
            choices = [index for index in choices if abs(catalog[index]["total"] - target_total) == nearest]
    return sorted(choices)


def _harmless_natural_pools(catalog, pools, targets, native_moves):
    """Prove a narrow passive set from final learns and original move effects."""
    if native_moves is None:
        raise FormatError("missing native move catalogue for starter-pair safety")
    for index, effect in HARMLESS_NATURAL_EFFECTS.items():
        row = native_moves.get(index, {})
        if row.get("power") != 0 or row.get("effect") != effect:
            raise FormatError("unknown native harmless-move effect for starter-pair safety")
    harmless = set(HARMLESS_NATURAL_EFFECTS) | {0}
    return tuple({index for index in pool if set(natural_moves(
        catalog[index]["learnset"], target["level"], [0] * 4, native_moves)) <= harmless}
        for pool, target in zip(pools, targets, strict=True))


def apply_starter_tables(original_dol: bytes, current_dol: bytes, original_rel: bytes,
                         rel: bytes, seed: str, options, tables: dict,
                         *, targets: tuple[dict, ...] = STARTERS, select_pair=None,
                         native_moves=None) -> tuple[bytes, dict]:
    """Core for a production-validated table layout, also usable by fixtures.

    Uniformly sample the complete set of valid ordered pairs. Never retry a
    bounded number of draws or weaken a rule when a valid pair is scarce.
    """
    if len(current_dol) < len(original_dol) or len(rel) != len(original_rel):
        raise FormatError("starter rules must preserve DOL and REL allocations")
    rules = _rules(options)
    selected = tuple(_flag(options, "starter_" + target["key"]) for target in targets)
    report = {"version": VERSION, "applied": False, "rules": rules, "edits": [],
              "levels_preserved": True, "disabled_starters_preserved": True,
              "only_species_and_exp_immediates_changed": True}
    manual = tuple(getattr(options, "starter_" + target["key"] + "_species", 0) for target in targets)
    natural = getattr(options, "randomize_starter_moves", False) == "natural"
    if any(type(value) is not int or not 0 <= value <= 386 for value in manual):
        raise ValueError("invalid manual starter national dex")
    if not any(selected) or not (select_pair is not None or _active(rules) or natural
                                or any(value and enabled for value, enabled in zip(manual, selected))):
        return current_dol, report

    original_catalog, catalog = species_catalog(original_rel, tables), species_catalog(rel, tables)
    if set(catalog) != set(original_catalog):
        raise FormatError("starter species inventory changed")
    families, _ = evolution_families(original_rel, tables)
    stages = evolution_stage_info(original_rel, tables)
    roots = {index for index, info in stages.items() if info["base_form"]}
    pools = []
    before = []
    for target, randomized, forced in zip(targets, selected, manual, strict=True):
        pos = target["base"]
        check_range(original_dol, pos, 0x94, "starter instructions")
        if (u32(original_dol, pos) != 0x38800000 | target["old"]
                or u32(original_dol, pos + 4) != 0x38A00000 | target["level"]
                or u32(original_dol, pos + 0x90) != 0x38E00000 | target["xp"]):
            raise FormatError("unknown original starter species/level/EXP instructions")
        if (u32(current_dol, pos) & 0xFFFF0000 != 0x38800000
                or u32(current_dol, pos + 4) != u32(original_dol, pos + 4)
                or u32(current_dol, pos + 0x90) & 0xFFFF0000 != 0x38E00000):
            raise FormatError("current starter species/level/EXP instruction differs")
        index = u16(current_dol, pos + 2)
        if index not in catalog or target["old"] not in original_catalog:
            raise FormatError("starter references an invalid real species")
        before.append(index)
        if randomized and forced:
            matches = [i for i, row in catalog.items() if row["national_dex"] == forced]
            if len(matches) != 1:
                raise FormatError("Le starter choisi n’existe pas dans cette ROM.")
            chosen_index = matches[0]
            native_row = original_catalog[chosen_index]
            generation = 1 if forced <= 151 else 2 if forced <= 251 else 3
            if (forced == SHEDINJA_NATIONAL or not _flag(options, f"allow_gen{generation}", True)
                    or species_excluded(native_row, options)
                    or forced in LEGENDARY_NATIONAL and not _flag(options, "allow_legendaries", True)):
                raise FormatError("Le starter choisi est exclu par les filtres. Modifiez le choix manuel ou les Pokémon autorisés.")
            pools.append([chosen_index])
        else:
            pools.append(_candidates(target, original_catalog, catalog, stages, options, rules)
                         if randomized else [index])

    def compatible(first: int, second: int) -> bool:
        a, b = catalog[first], catalog[second]
        return not (
            rules["starter_distinct_families"] and families[first] == families[second]
            or rules["starter_complementary_types"] and set(a["types"]) & set(b["types"])
            or rules["starter_balance_pair"] and abs(a["total"] - b["total"]) > max(50, min(a["total"], b["total"]) // 5))

    pairings = {first: [second for second in pools[1] if compatible(first, second)] for first in pools[0]}
    harmless_pools = _harmless_natural_pools(catalog, pools, targets, native_moves) if natural else (set(), set())
    protect_pair = natural and any(enabled and not forced for enabled, forced in zip(selected, manual, strict=True))
    prior_count = sum(map(len, pairings.values()))
    if protect_pair:
        pairings = {first: [second for second in seconds if not (
            first in harmless_pools[0] and second in harmless_pools[1])]
            for first, seconds in pairings.items()}
    count = sum(map(len, pairings.values()))
    if not count:
        if protect_pair and prior_count:
            raise FormatError("Les deux starters n’auraient que des capacités sans effet offensif. Élargissez les Pokémon autorisés ou choisissez un partenaire différent.")
        raise FormatError("Aucun couple de starters ne respecte toutes les règles. Désactivez une contrainte de types, de puissance ou de famille, ou élargissez les espèces autorisées.")
    draw_domain = NATURAL_DRAW_VERSION if protect_pair else DRAW_VERSION
    ordinal = _sample(seed, count, domain=draw_domain)
    chosen = None
    for first, seconds in pairings.items():
        if ordinal < len(seconds):
            chosen = first, seconds[ordinal]
            break
        ordinal -= len(seconds)
    assert chosen is not None
    if select_pair is not None:
        chosen = select_pair(chosen, pairings)
    if protect_pair and chosen[0] in harmless_pools[0] and chosen[1] in harmless_pools[1]:
        raise FormatError("story-family allocation returned an unsafe passive starter pair")

    output, allowed = bytearray(current_dol), set()
    pair_report = []
    for target, randomized, old, index in zip(targets, selected, before, chosen, strict=True):
        row = catalog[index]
        pos = target["base"]
        xp = u16(current_dol, pos + 0x92)
        if randomized:
            xp = experience_at_level(rel[row["offset"]], target["level"])
            if not 0 <= xp < 0x8000:
                raise FormatError("starter EXP exceeds signed li immediate")
            struct.pack_into(">H", output, pos + 2, index)
            struct.pack_into(">H", output, pos + 0x92, xp)
            allowed.update((pos + 2, pos + 3, pos + 0x92, pos + 0x93))
            report["edits"].append({"key": target["key"], "old_species_index": old,
                                    "new_species_index": index, "species_field_offset": pos + 2,
                                    "exp_field_offset": pos + 0x92, "new_exp": xp})
        pair_report.append({"key": target["key"], "randomized": randomized,
                            "manual": randomized and bool(manual[len(pair_report)]),
                            "species_index": index, "national_dex": row["national_dex"],
                            "family": families[index], "base_form": index in roots,
                            "evolution_stage": stages[index]["stage"],
                            "final_form": stages[index]["final_form"],
                            "family_stages": stages[index]["family_stages"],
                            "types": list(row["types"]), "bst": row["total"],
                            "level": target["level"], "experience": xp})
    result = bytes(output)
    if any(a != b and index not in allowed for index, (a, b) in enumerate(zip(current_dol, result, strict=True))):
        raise FormatError("starter patch changed an unauthorized field")
    report.update(applied=True, valid_pair_count=count, pair=pair_report,
                  pair_bst_difference=abs(catalog[chosen[0]]["total"] - catalog[chosen[1]]["total"]),
                  pair_bst_tolerance=max(50, min(catalog[chosen[0]]["total"], catalog[chosen[1]]["total"]) // 5),
                  properties_source="final REL types and BST; original evolution graph",
                  power_window_source=("original base ancestor BST; final candidate BST"
                    if rules["starter_three_stage_families"] and rules["starter_stage"] == "base" else
                    "original encounter BST; final candidate BST"),
                  draw_domain=draw_domain,
                  draw=("seeded valid pair selected with the story family allocation" if select_pair is not None
                        else "uniform ordered valid pairs; no constraint relaxation"))
    if natural:
        report["natural_pair_safety"] = {
            "automatic_draw_protected": bool(protect_pair),
            "excluded_pair_count": prior_count - count,
            "known_harmless_moves": sorted(HARMLESS_NATURAL_EFFECTS),
            "both_known_harmless": chosen[0] in harmless_pools[0] and chosen[1] in harmless_pools[1],
            "manual_choices_preserved": True,
            "scope": "Reject only two proven harmless natural movesets in an automatic draw; not a battle-win guarantee",
        }
    return result, report


def apply_starter_rules(original_dol: bytes, current_dol: bytes, original_rel: bytes,
                        rel: bytes, seed: str, options, *, select_pair=None) -> tuple[bytes, dict]:
    """Validate exact regional artifacts before editing starter immediates."""
    targets = tuple(target for target in special_targets(original_dol) if "xp" in target)
    tables, _ = layout(original_rel)
    native_moves = None
    if getattr(options, "randomize_starter_moves", False) == "natural":
        # Lazy import avoids a module-level cycle; gameplay_rules owns the
        # bounded, regional move-table reader used for actual natural moves.
        from .gameplay_rules import expanded_layout, move_catalog
        native_moves = move_catalog(original_rel, expanded_layout(original_rel))
    return apply_starter_tables(original_dol, current_dol, original_rel, rel, seed, options, tables,
                                targets=targets, select_pair=select_pair, native_moves=native_moves)
