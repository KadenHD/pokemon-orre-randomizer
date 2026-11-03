"""Seeded gameplay rules for the verified regional original artifacts.

Transforms operate on copies. Special move markers, shadow metadata identities,
unreferenced trainer slots and every field outside an explicit whitelist survive.
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
import math
import struct

from .analyze_game import FormatError, parse_dol, u32
from .evolution_rules import evolution_families
from .inspect_tables import SCHEMAS, u16
from .randomize_trainers import choose_species, layout, randomize_rel
from .randomize_story import SPECIALS, experience_at_level
from .species_rules import apply_species_rules, candidate_species, species_catalog
from .gift_move_hooks import patch_gift_moves
from .starter_rules import apply_starter_rules
from .shadow_boss_rules import apply_shadow_boss_rules, shadow_boss_rules_active
from .story_families import allocate_story_families, ordered_family_edges, select_story_starters
from .pool_filters import has_exclusions
from ..options import SPECIAL_OPTIONS
from .dol_regions import special_targets
from .level_curve import encounter_level

VERSION = "gameplay-rules-sha256-v1"
MOVE_FIELDS = (0x36, 0x3E, 0x46, 0x4E)
SELF_DESTRUCT = {120, 153}
OHKO = {12, 32, 90, 329}
USEFUL_ITEMS = (133,134,135,136,137,138,139,140,141,142,168,169,170,171,172,
                179,180,183,185,186,187,196,198,200,219,221)


def pick(seed: str, key: str, pool) -> int:
    choices = sorted(set(pool))
    if not choices:
        raise FormatError(f"no safe candidates for {key}")
    return choose_species(seed, VERSION + ":" + key, choices, -1)


def move_catalog(original: bytes, tables: dict) -> dict[int, dict]:
    table = tables["moves"]
    result = {}
    for index in range(1, min(355, table["count"])):
        pos = table["offset"] + index * table["stride"]
        if index == 165 or not original[pos + 1] or not u32(original, pos + 0x20):
            continue
        result[index] = {"index": index, "pp": original[pos + 1], "type": original[pos + 2],
                         "power": original[pos + 0x17], "accuracy": original[pos + 4],
                         "effect": u16(original, pos + 0x1A)}
    if len(result) < 300:
        raise FormatError("unexpected original regular move catalog")
    return result


def expanded_layout(original: bytes) -> dict:
    tables, symbols = layout(original)
    pointer, counter, stride = SCHEMAS["moves"]
    tables["moves"] = {"offset": symbols[pointer]["offset"], "count": u32(original, symbols[counter]["offset"]), "stride": stride}
    return tables


def damaging(move: dict) -> bool:
    # Seismic Toss/Night Shade are deterministic level damage despite raw power 1.
    return move["power"] > 1 or move["index"] in {69, 101}


def choose_moves(seed: str, key: str, species: dict, level: int, moves: dict,
                 options, count: int = 4, used: set[int] | None = None) -> list[int]:
    allowed = {index for index in moves if not (
        options.ban_self_destruct and index in SELF_DESTRUCT or options.ban_ohko and index in OHKO)}
    if options.no_duplicate_moves:
        allowed -= used or set()
    if options.moves_mode == "balanced":
        ceiling = min(120, max(40, 30 + 2 * level))
        pool = {i for i in allowed if moves[i]["power"] <= ceiling and
                (moves[i]["power"] != 1 or i in {69, 101})}
    else:
        pool = set(allowed)
    if len(pool) < count and options.no_duplicate_moves:
        pool = set(allowed)
    result = []
    for slot in range(count):
        available = pool - set(result) if options.no_duplicate_moves else pool
        need_stab = slot == 0 and options.ensure_stab_move
        need_damage = slot == 0 and (options.ensure_damaging_move or need_stab)
        if need_damage:
            wanted = {i for i in available if damaging(moves[i]) and
                      (not need_stab or moves[i]["type"] in species["types"])}
            if not wanted:
                wanted = {i for i in allowed - set(result) if damaging(moves[i]) and
                          (not need_stab or moves[i]["type"] in species["types"])}
                if wanted and options.moves_mode == "balanced":
                    minimum = min(moves[i]["power"] for i in wanted)
                    wanted = {i for i in wanted if moves[i]["power"] == minimum}
            available = wanted
        elif options.moves_mode == "balanced" and slot == 1:
            attack, special = species["stats"][1], species["stats"][3]
            preferred = {i for i in available if damaging(moves[i]) and
                         ((moves[i]["type"] <= 8) == (attack >= special))}
            available = preferred or available
        result.append(pick(seed, f"moves:{key}:{slot}", available))
    return result


def _filtered(options) -> bool:
    return has_exclusions(options) or options.balance_species or not all((options.allow_gen1, options.allow_gen2,
                                                options.allow_gen3, options.allow_legendaries))


def _pool_function(original: bytes, tables: dict, options):
    @lru_cache(maxsize=None)
    def candidates(old: int, reserved: tuple[int, ...] = ()):
        catalog = species_catalog(original, tables)
        choices = [index for index in candidate_species(original, tables, old, replace(options, balance_species=False), set(reserved))
                   if catalog[index]["national_dex"] != 292]
        if not choices:
            raise FormatError("no safe replacement after excluding Wonder Guard encounters")
        if options.balance_species:
            target = catalog[old]["total"]
            tolerance = max(50, target // 5)
            close = [index for index in choices if abs(catalog[index]["total"] - target) <= tolerance]
            if close:
                choices = close
            else:
                nearest = min(abs(catalog[index]["total"] - target) for index in choices)
                choices = [index for index in choices if abs(catalog[index]["total"] - target) == nearest]
        return choices
    return candidates


def apply_rel_rules(original: bytes, current: bytes, seed: str, options, *, allocate_shadows=None) -> tuple[bytes, dict]:
    tables = expanded_layout(original)
    original_species = species_catalog(original, tables)
    source_plan = randomize_rel(original, seed)[1]
    records = source_plan["trainer_pokemon_changes"]
    output, allowed = bytearray(current), set()
    summary = {"version": VERSION}
    families = evolution_families(original, tables)[0]
    boss_shadow_active = options.randomize_shadows and (allocate_shadows is not None or shadow_boss_rules_active(options))
    if _filtered(options) and (options.randomize_trainers or options.randomize_shadows):
        pool = _pool_function(original, tables, options)
        selected_shadows, reserved = {}, set()
        for change in source_plan["shadow_changes"] if options.randomize_shadows and not boss_shadow_active else []:
            sid, old = change["shadow_id"], change["old_species_index"]
            candidates = pool(old, tuple(sorted(reserved)) if options.unique_shadows else ())
            new = pick(seed, f"species:shadow:{sid}", candidates)
            selected_shadows[sid] = new
            reserved.add(families[new])
            struct.pack_into(">H", output, change["offset"], new)
            allowed.update(range(change["offset"], change["offset"] + 2))
        for row in records:
            sid, pos = row["shadow_id"], row["offset"]
            if not (options.randomize_shadows if sid else options.randomize_trainers):
                continue
            if sid and boss_shadow_active:
                continue
            new = selected_shadows[sid] if sid else pick(seed, f"species:slot:{row['index']}", pool(row["old_species_index"]))
            struct.pack_into(">H", output, pos + 0xA, new)
            struct.pack_into(">I", output, pos + 0x14, u32(original, original_species[new]["offset"] + 0x18))
            output[pos] = 0 if original[pos] == 1 and not original_species[new]["abilities"][1] else original[pos]
            allowed.update((pos, pos + 0xA, pos + 0xB, *range(pos + 0x14, pos + 0x18)))
        summary["species_pool_rules_applied"] = True
    if boss_shadow_active:
        transformed, summary["shadow_boss"] = apply_shadow_boss_rules(
            original, bytes(output), seed, options, tables, allocate=allocate_shadows)
        allowed.update(i for i, (a, b) in enumerate(zip(output, transformed, strict=True)) if a != b)
        output = bytearray(transformed)
    before_species = bytes(output)
    modified_species, species_summary = apply_species_rules(original, before_species, seed, options, tables)
    allowed.update(i for i, (a, b) in enumerate(zip(before_species, modified_species)) if a != b)
    output = bytearray(modified_species)
    summary["species_properties"] = species_summary
    catalog = species_catalog(bytes(output), tables)
    moves = move_catalog(original, tables)
    learned_edits = []
    if options.randomize_learnsets:
        for index, meta in catalog.items():
            slots = [(slot, original[meta["offset"] + 0xBA + slot * 4],
                      u16(original, meta["offset"] + 0xBC + slot * 4)) for slot in range(19)]
            active = [(slot, level, move) for slot, level, move in slots if level and move in moves]
            chosen = set()
            for ordinal, (slot, level, old) in enumerate(active):
                # Every rolling four learned moves retains the offensive/STAB guarantees.
                guards = options if ordinal % 4 == 0 else replace(options, ensure_damaging_move=False, ensure_stab_move=False)
                available_moves = moves
                if ordinal % 4 and options.no_duplicate_moves and options.ensure_stab_move:
                    # Reserve scarce STAB moves (Ghost/Steel/Dragon) for the
                    # required rolling-window slots instead of exhausting them.
                    available_moves = {i: move for i, move in moves.items() if not (
                        damaging(move) and move["type"] in meta["types"])}
                new = choose_moves(seed, f"learn:{index}:{slot}", meta, level, available_moves, guards, 1, chosen)[0]
                chosen.add(new)
                pos = meta["offset"] + 0xBC + slot * 4
                struct.pack_into(">H", output, pos, new)
                allowed.update((pos, pos + 1))
                learned_edits.append({"species": index, "slot": slot, "level": level, "before": old, "after": new})
    summary["learnset_edits"] = learned_edits
    move_edits, levels, items, protected = [], [], [], []
    held_pool = {u16(original, row["offset"] + 0x12) for row in records} - {0, 0xFFFF}
    if options.useful_held_items_only:
        held_pool &= set(USEFUL_ITEMS)
    for row in records:
        pos = row["offset"]
        index = u16(output, pos + 0xA)
        level = encounter_level(original[pos + 4], options)
        if level != original[pos + 4]:
            output[pos + 4] = level
            allowed.add(pos + 4)
            levels.append({"index": row["index"], "before": original[pos + 4], "after": level})
        old_moves = [u16(original, pos + field) for field in MOVE_FIELDS]
        if options.randomize_trainer_moves:
            if any(move == 0xFFFF or move >= 355 for move in old_moves):
                protected.append(row["index"])
            else:
                new_moves = choose_moves(seed, f"trainer:{row['index']}", catalog[index], level, moves, options)
                for field, new in zip(MOVE_FIELDS, new_moves):
                    struct.pack_into(">H", output, pos + field, new)
                    allowed.update((pos + field, pos + field + 1))
                move_edits.append({"index": row["index"], "shadow_id": row["shadow_id"],
                                   "species": index, "level": level, "before": old_moves, "after": new_moves})
        old_item = u16(original, pos + 0x12)
        if options.randomize_held_items and old_item not in (0, 0xFFFF):
            new_pool = held_pool - {old_item}
            actual_moves = [u16(output, pos + field) for field in MOVE_FIELDS]
            if not any(m in moves and damaging(moves[m]) and moves[m]["type"] <= 8 for m in actual_moves):
                new_pool -= {186}  # Choice Band requires a physical attacking move.
            new = pick(seed, f"item:{row['index']}", new_pool)
            struct.pack_into(">H", output, pos + 0x12, new)
            allowed.update((pos + 0x12, pos + 0x13))
            items.append({"index": row["index"], "before": old_item, "after": new})
    catches = []
    for row in source_plan["shadow_changes"]:
        pos = tables["shadow"]["offset"] + row["shadow_id"] * tables["shadow"]["stride"]
        before = original[pos]
        new = min(255, max(options.minimum_catch_rate, 1, math.floor(before * options.capture_rate_multiplier + 0.5)))
        if new != before:
            output[pos] = new
            allowed.add(pos)
            catches.append({"shadow_id": row["shadow_id"], "before": before, "after": new})
    result = bytes(output)
    actual = {i for i, (a, b) in enumerate(zip(current, result)) if a != b}
    if actual - allowed:
        raise FormatError("gameplay rules altered an unauthorized field")
    if evolution_families(original, tables) != evolution_families(result, tables):
        raise FormatError("gameplay rules changed evolution families")
    if options.randomize_shadows and options.unique_shadows:
        picks = [u16(result, row["offset"]) for row in source_plan["shadow_changes"]]
        if len({families[p] for p in picks}) != 48:
            raise FormatError("filtered shadow pool did not preserve 48 unique families")
    summary.update(trainer_move_edits=move_edits, protected_move_records=protected,
                   trainer_level_edits=levels, held_item_edits=items, capture_edits=catches,
                   changed_bytes=len(actual), all_advanced_changes_whitelisted=True)
    return result, summary


def apply_story_rules(original_rel, base_rel, original_dol, base_dol, seed, options):
    tables = expanded_layout(original_rel)
    families = evolution_families(original_rel, tables)[0]
    targets = special_targets(original_dol)
    starters = [row for row in targets if "xp" in row]
    gifts = [row for row in targets if "xp" not in row]
    fixed = {families[row["old"]] for row in gifts if not getattr(options, SPECIAL_OPTIONS[row["key"]])}
    shadow_table = tables["shadow"]

    def shadow_families(rel):
        return {families[index] for sid in range(1, shadow_table["count"])
                if (index := u16(rel, shadow_table["offset"] + sid * shadow_table["stride"] + 2))}

    if not options.randomize_shadows:
        fixed.update(shadow_families(original_rel))
    preferred_pool = _pool_function(original_rel, tables, options)
    eligible_pool = _pool_function(original_rel, tables, replace(options, balance_species=False))
    gift_hard = {row["key"]: eligible_pool(row["old"]) for row in gifts if getattr(options, SPECIAL_OPTIONS[row["key"]])}
    gift_preferred = {row["key"]: preferred_pool(row["old"]) for row in gifts if row["key"] in gift_hard}
    gift_edges = ordered_family_edges(seed, gift_hard, gift_preferred, families)

    # The duo evaluates final types and BST. These fields can be projected
    # independently of the encounter, move and item edits in the REL pass.
    starter_rel = base_rel
    if options.randomize_types or options.randomize_stats:
        starter_rel = apply_species_rules(original_rel, base_rel, seed, options, tables)[0]
    starter_result, gift_assignments = None, None
    reserved = set()

    def allocate(hard, preferred):
        nonlocal starter_result, gift_assignments, reserved
        shadow_edges = ordered_family_edges(seed, {f"shadow:{sid}": pool for sid, pool in hard.items()},
                                            {f"shadow:{sid}": pool for sid, pool in preferred.items()}, families)
        edges = shadow_edges | gift_edges

        def select_pair(pair, pairings):
            return select_story_starters(pair, pairings, families, edges, fixed)

        starter_result = apply_starter_rules(original_dol, base_dol, original_rel, starter_rel,
                                             seed, options, select_pair=select_pair)
        reserved = fixed | {families[u16(starter_result[0], row["base"] + 2)] for row in starters}
        favored = {f"shadow:{sid}": pool for sid, pool in preferred.items()} | gift_preferred
        favored_edges = ordered_family_edges(seed, favored, favored, families)
        assignments = allocate_story_families(favored_edges, reserved)
        if len(assignments) < len(edges):
            assignments = allocate_story_families(edges, reserved)
        if len(assignments) == len(edges):
            gift_assignments = assignments
        else:
            # Keep the strict Shadow rules even if the cross-group preference
            # is impossible. Gifts can still avoid the final Shadow families.
            assignments = allocate_story_families(shadow_edges, reserved)
            if len(assignments) < len(shadow_edges):
                return None
        return {sid: assignments[f"shadow:{sid}"] for sid in hard}

    if not options.randomize_shadows:
        allocate({}, {})
    rel, summary = apply_rel_rules(original_rel, base_rel, seed, options, allocate_shadows=allocate)
    if gift_assignments is None:
        gift_assignments = allocate_story_families(gift_edges, reserved | shadow_families(rel))
    gift_picks = {}
    for key, pool in gift_hard.items():
        family = gift_assignments.get(key)
        preferred = [index for index in gift_preferred[key] if families[index] == family]
        within_family = [index for index in pool if families[index] == family]
        gift_picks[key] = pick(seed, "story-family:gift:" + key, preferred or within_family or gift_preferred[key])
    return rel, summary, starter_result, gift_picks


def apply_dol_rules(original: bytes, current: bytes, original_rel: bytes, rel: bytes,
                    seed: str, options, *, starter_result=None, gift_picks=None) -> tuple[bytes, dict]:
    tables = expanded_layout(original_rel)
    catalog = species_catalog(rel, tables)
    moves = move_catalog(original_rel, tables)
    pool = _pool_function(original_rel, tables, options)
    starter_dol, starter_report = starter_result or apply_starter_rules(original, current, original_rel, rel, seed, options)
    gift_picks = gift_picks or {}
    allowed = {i for i, (a, b) in enumerate(zip(current, starter_dol, strict=True)) if a != b}
    output, specials, gift_moves = bytearray(starter_dol), [], {}
    for target in special_targets(original):
        key, pos = target["key"], target["base"]
        level = target["level"]
        if options.accessible_event_gifts and key in ("pikachu-event", "celebi-event"):
            level = getattr(options, "event_pikachu_level" if key == "pikachu-event" else "event_celebi_level")
            for displacement in (4, 0x38):  # constructor level and met-level
                if (u32(original, pos + displacement) != 0x38A00000 | target["level"]
                        or u32(output, pos + displacement) != u32(original, pos + displacement)):
                    raise FormatError("unexpected original event gift level instruction")
                struct.pack_into(">H", output, pos + displacement + 2, level)
                allowed.update((pos + displacement + 2, pos + displacement + 3))
        index = u16(output, pos + 2)
        if key in gift_picks:
            index = gift_picks[key]
            struct.pack_into(">H", output, pos + 2, index)
            allowed.update((pos + 2, pos + 3))
        elif (_filtered(options) and getattr(options, SPECIAL_OPTIONS[key])
                and not ("xp" in target and starter_report["applied"])):
            index = pick(seed, "species:special:" + key, pool(target["old"]))
            struct.pack_into(">H", output, pos + 2, index)
            allowed.update((pos + 2, pos + 3))
            if "xp" in target:
                xp = experience_at_level(original_rel[catalog[index]["offset"]], target["level"])
                struct.pack_into(">H", output, pos + 0x92, xp)
                allowed.update((pos + 0x92, pos + 0x93))
        change = {"key": key, "species": index, "level": level}
        do_moves = options.randomize_starter_moves if "xp" in target else options.randomize_gift_moves
        if do_moves:
            new_moves = choose_moves(seed, "special:" + key, catalog[index], level, moves, options)
            change["moves"] = new_moves
            if "xp" in target:
                for slot, move in enumerate(new_moves):
                    instruction = pos + 0x14 + slot * 0x10
                    if u32(original, instruction) & 0xFFFF0000 != 0x38A00000:
                        raise FormatError("unknown original starter move instruction")
                    struct.pack_into(">H", output, instruction + 2, move)
                    allowed.update((instruction + 2, instruction + 3))
            else:
                gift_moves[key] = new_moves
        elif "xp" not in target and options.randomize_learnsets:
            # Gifts normally read the global learnset. Preserve their original
            # species-appropriate starting moves when only learns are randomized.
            native = []
            species_pos = catalog[index]["offset"]
            for slot in range(19):
                level = original_rel[species_pos + 0xBA + slot * 4]
                move = u16(original_rel, species_pos + 0xBC + slot * 4)
                if level and level <= change["level"] and move in moves:
                    if move in native:
                        native.remove(move)
                    native.append(move)
            native = native[-4:]
            native += [0] * (4 - len(native))
            gift_moves[key] = native
            change.update(moves=native, moves_source="original-species-learnset-preserved")
        specials.append(change)
    result = bytes(output)
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(current, result))):
        raise FormatError("advanced DOL edits exceeded their whitelist")
    result, hook_report = patch_gift_moves(original, result, gift_moves)
    parse_dol(result)
    return result, {"specials": specials, "gift_move_hooks": hook_report, "starter_pair": starter_report}
