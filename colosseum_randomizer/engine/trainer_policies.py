"""Optional trainer themes and final stages, after level and boss adjustments.

Shared team slots form components: one record is drawn once. Shadow records,
team pointers, levels, IVs, EVs and special move markers are never rewritten.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import hashlib
import struct

from .analyze_game import FormatError, u32
from .boss_rules import _position, _references, boss_inventory
from .evolution_rules import _species_and_edges, evolution_families, evolution_stage_info
from .gameplay_rules import MOVE_FIELDS, choose_moves, expanded_layout, move_catalog
from .inspect_tables import u16
from .pool_filters import allowed_replacement
from .randomize_trainers import choose_species
from .species_rules import species_catalog
from ..i18n import Message

VERSION = "trainer-policies-sha256-v1"


def apply_trainer_tables(original: bytes, current: bytes, seed: str, options,
                         tables: dict, bosses: list[dict]) -> tuple[bytes, dict]:
    theme_mode = options.trainer_theme_mode if options.randomize_trainers else "none"
    force = options.trainer_force_evolved
    report = {"version": VERSION, "theme_mode": theme_mode, "force_evolved": force,
              "evolution_level": options.trainer_evolution_level, "groups": [], "edits": [],
              "changed_bytes": 0, "shadow_records_unchanged": True,
              "team_pointers_and_slot_counts_unchanged": True, "all_changes_whitelisted": True}
    if theme_mode == "none" and not force:
        return current, report
    if len(original) != len(current):
        raise FormatError("trainer policies must preserve REL size")
    catalog = species_catalog(current, tables)
    native = species_catalog(original, tables)
    family = evolution_families(original, tables)[0]
    evolution_stage_info(original, tables)  # Refuse cyclic or malformed graphs.
    nodes, edges = _species_and_edges(original, tables)
    children = {i: set() for i in nodes}
    for edge in edges:
        children[edge["species_index"]].add(edge["target_species_index"])

    @lru_cache(None)
    def terminals(index):
        return frozenset().union(*(terminals(i) for i in sorted(children[index]))) if children[index] else frozenset((index,))

    references = _references(original, tables)
    slots, teams = {}, defaultdict(list)
    for index, trainers in sorted(references.items()):
        pos = _position(original, tables["trainer_pokemon"], index, 0x50)
        before, now = u16(original, pos + 0xA), u16(current, pos + 0xA)
        if bool(before) != bool(now) or original[pos + 3] != current[pos + 3]:
            raise FormatError("trainer policy input changed slot occupancy or shadow IDs")
        if not before:
            continue
        if before not in native or now not in catalog:
            raise FormatError("trainer policy slot has an invalid species")
        for trainer in trainers:
            teams[trainer].append(index)
        slots[index] = {"pos": pos, "original": before, "current": now,
                        "shadow": original[pos + 3], "level": current[pos + 4]}

    # Union teams sharing non-Shadow records; the original team layout is kept.
    parent = {i: i for i, row in slots.items() if not row["shadow"]}

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for team in teams.values():
        ordinary = [i for i in team if i in parent]
        for i in ordinary[1:]:
            a, b = root(ordinary[0]), root(i)
            parent[max(a, b)] = min(a, b)
    groups = defaultdict(list)
    for i in sorted(parent):
        groups[root(i)].append(i)
    boss_ids = {row["trainer_id"] for row in bosses} if options.boss_team_variety else set()
    peers = defaultdict(set)
    for trainer in sorted(boss_ids):
        for i in teams.get(trainer, []):
            peers[i].update(j for j in teams[trainer] if j != i)
    eligible = {i for i, row in native.items() if allowed_replacement(row, options)}
    final_pool = {i for i in eligible if not children[i]}
    output, allowed = bytearray(current), set()
    moves = None

    def ranked(values, key):
        # Keyed independent draws; stable ordering and no process-global RNG.
        raw = seed.encode("utf-8")
        prefix = VERSION.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big") + raw + b"\0" + key.encode("ascii") + b"\0"
        return sorted(values, key=lambda i: (hashlib.sha256(prefix + str(i).encode("ascii")).digest(), i))

    def solve(pools, active, key):
        # Assign families first; different species in one family cannot provide
        # boss diversity. MRV plus forward checking bounds tiny native teams.
        choices = {}
        for i, pool in pools.items():
            blocked = {family[slots[j]["current"]] for j in peers[i] if j not in active}
            by_family = defaultdict(list)
            for species in pool:
                if family[species] not in blocked:
                    by_family[family[species]].append(species)
            choices[i] = by_family
        selected = {}

        def visit():
            if len(selected) == len(active):
                return True
            available = {i: [f for f in choices[i] if all(selected.get(j) != f for j in peers[i])]
                         for i in active if i not in selected}
            i = min(available, key=lambda j: (len(available[j]), j))
            for f in ranked(available[i], f"{key}:slot:{i}:family"):
                selected[i] = f
                if visit():
                    return True
            selected.pop(i, None)
            return False

        if not visit():
            return None
        return {i: choose_species(seed, f"{VERSION}:{key}:slot:{i}:species", sorted(choices[i][f]), -1)
                for i, f in selected.items()}

    for group, members in sorted(groups.items()):
        trainers = sorted({t for i in members for t in references[i]})
        forced = {i for i in members if force and slots[i]["level"] >= options.trainer_evolution_level}
        active = set(members) if theme_mode != "none" else {
            i for i in forced if options.randomize_trainers or children[slots[i]["current"]]}
        if not active:
            continue
        hard = {}
        targets = {}
        for i in sorted(active):
            row = slots[i]
            if not 1 <= row["level"] <= 100:
                raise FormatError("trainer policy has an invalid final level")
            if not options.randomize_trainers:
                pool = terminals(row["current"]) & eligible
            else:
                pool = final_pool if i in forced else eligible
                # The existing replacement rule always changes the native
                # species; a secondary theme/stage draw must keep that promise.
                pool = pool - {row["original"]}
            hard[i] = sorted(pool)
            target_species = terminals(row["original"]) if i in forced else (row["original"],)
            targets[i] = max(native[s]["total"] for s in target_species)
            if not pool:
                raise FormatError(Message("Aucun Pokémon admissible pour le dresseur {trainer}, emplacement {slot}. Modifiez les exclusions ou le stade demandé.", trainer=trainers[0], slot=i))
        common_original = set.intersection(*(set(native[slots[i]["original"]]["types"]) for i in members))
        themes = [None]
        if theme_mode != "none":
            feasible = set.intersection(*(set(t for s in hard[i] for t in catalog[s]["types"]) for i in sorted(active)))
            themes = ranked(feasible, f"group:{group}:theme")
            if theme_mode == "preserve":
                themes.sort(key=lambda t: t not in common_original)
        selected, selected_theme, relaxed = None, None, False
        for theme in themes:
            themed = {i: [s for s in pool if theme is None or theme in catalog[s]["types"]]
                      for i, pool in hard.items()}
            preferred = {}
            for i, pool in themed.items():
                if options.balance_species:
                    close = [s for s in pool if abs(native[s]["total"] - targets[i]) <= max(50, targets[i] // 5)]
                    distance = min((abs(native[s]["total"] - targets[i]) for s in pool), default=0)
                    preferred[i] = close or [s for s in pool if abs(native[s]["total"] - targets[i]) == distance]
                else:
                    preferred[i] = pool
            key = f"group:{group}:theme:{theme}"
            selected = solve(preferred, active, key)
            if selected is None and options.balance_species:
                selected = solve(themed, active, key + ":diversity")
                relaxed = selected is not None
            if selected is not None:
                selected_theme = theme
                break
        if selected is None:
            raise FormatError(Message("Aucun thème commun admissible pour le dresseur {trainer}. Modifiez les exclusions ou la diversité des boss.", trainer=trainers[0]))
        report["groups"].append({"group": group, "trainers": trainers, "slots": sorted(active),
            "type": selected_theme, "original_type_preserved": selected_theme in common_original if selected_theme is not None else None,
            "power_matching_relaxed_for_diversity": relaxed})
        for i, species in sorted(selected.items()):
            row, pos = slots[i], slots[i]["pos"]
            before_moves = [u16(current, pos + f) for f in MOVE_FIELDS]
            if species != row["current"]:
                struct.pack_into(">H", output, pos + 0xA, species)
                struct.pack_into(">I", output, pos + 0x14, u32(current, catalog[species]["offset"] + 0x18))
                if output[pos] == 1 and not catalog[species]["abilities"][1]:
                    output[pos] = 0
                allowed.update((pos, pos + 0xA, pos + 0xB, *range(pos + 0x14, pos + 0x18)))
                if options.randomize_trainer_moves and not any(move >= 355 for move in before_moves):
                    if moves is None:
                        moves = move_catalog(original, tables)
                    chosen = choose_moves(seed, f"{VERSION}:moves:{i}", catalog[species], row["level"], moves, options)
                    for f, move in zip(MOVE_FIELDS, chosen, strict=True):
                        struct.pack_into(">H", output, pos + f, move)
                        allowed.update((pos + f, pos + f + 1))
            report["edits"].append({"index": i, "offset": pos, "referencing_trainers": references[i],
                "original_species": row["original"], "before_species": row["current"], "after_species": species,
                "national_dex": catalog[species]["national_dex"], "level": row["level"],
                "final_stage_required": i in forced, "type": selected_theme,
                "moves_before": before_moves, "moves_after": [u16(output, pos + f) for f in MOVE_FIELDS]})
    result = bytes(output)
    changed = {i for i, (a, b) in enumerate(zip(current, result, strict=True)) if a != b}
    if changed - allowed:
        raise FormatError("trainer policy changed an unauthorized field")
    report["changed_bytes"] = len(changed)
    return result, report


def apply_trainer_policies(original: bytes, current: bytes, seed: str, options) -> tuple[bytes, dict]:
    # Inactive options deliberately avoid inventory work and any random draw.
    if options.trainer_theme_mode == "none" and not options.trainer_force_evolved:
        return current, {"version": VERSION, "enabled": False, "changed_bytes": 0, "groups": [], "edits": []}
    tables, bosses = boss_inventory(original)
    if options.randomize_trainer_moves:
        tables = expanded_layout(original)
    return apply_trainer_tables(original, current, seed, options, tables, bosses)
