"""Evolution families and explicit PAL evolution fixes for randomizer v3.

Family membership follows every declared branch in the original species table,
in both directions. It does not imply that a native runtime can trigger a branch.
All transformations return new bytes; these helpers perform no filesystem writes.
"""

from __future__ import annotations

from collections import defaultdict
import struct

from .analyze_game import FormatError, check_range, sha256


EVOLUTION_OFFSET = 0x9C
EVOLUTION_COUNT = 5
EVOLUTION_STRIDE = 6
SHADOW_GROUP_COUNT = 48

# source, target, original method, original condition, new method, new condition
# Internal species indices are intentionally distinct from national dex numbers.
EVOLUTION_FIXES = (
    (64, 65, 5, 0, 4, 40),
    (67, 68, 5, 0, 4, 40),
    (75, 76, 5, 0, 4, 40),
    (93, 94, 5, 0, 4, 40),
    (95, 208, 6, 199, 4, 40),
    (117, 230, 6, 201, 4, 40),
    (123, 212, 6, 199, 4, 40),
    (137, 233, 6, 218, 4, 40),
    (61, 186, 6, 187, 7, 93),
    (79, 199, 6, 187, 7, 97),
    (373, 374, 6, 192, 7, 97),
    (373, 375, 6, 193, 7, 94),
    (133, 196, 2, 0, 7, 93),
    (133, 197, 3, 0, 7, 94),
    (328, 329, 15, 170, 4, 40),
)


def _table(data: bytes, tables: dict, name: str, minimum_stride: int) -> dict:
    try:
        source = tables[name]
        result = {key: source[key] for key in ("offset", "count", "stride")}
    except (KeyError, TypeError) as exc:
        raise FormatError(f"missing {name} table layout") from exc
    if (any(type(value) is not int for value in result.values())
            or result["offset"] < 0 or result["count"] < 1
            or result["stride"] < minimum_stride):
        raise FormatError(f"invalid {name} table layout")
    check_range(data, result["offset"], result["count"] * result["stride"], name)
    return result


def _species_and_edges(data: bytes, tables: dict) -> tuple[set[int], list[dict]]:
    meta = _table(data, tables, "species", EVOLUTION_OFFSET + EVOLUTION_COUNT * EVOLUTION_STRIDE)
    species = set()
    national_seen = set()
    for index in range(meta["count"]):
        position = meta["offset"] + index * meta["stride"]
        national = struct.unpack_from(">H", data, position + 0x10)[0]
        if 1 <= national <= 386:
            if national in national_seen:
                raise FormatError("duplicate real national dex number")
            national_seen.add(national)
            species.add(index)
    if not species:
        raise FormatError("species table has no real species")
    edges = []
    for index in sorted(species):
        for slot in range(EVOLUTION_COUNT):
            position = (meta["offset"] + index * meta["stride"]
                        + EVOLUTION_OFFSET + slot * EVOLUTION_STRIDE)
            method = data[position]
            condition, target = struct.unpack_from(">HH", data, position + 2)
            if method == 0:
                if condition or target:
                    raise FormatError("unused evolution slot has a condition or target")
                continue
            if method not in range(1, 16):
                raise FormatError(f"unknown evolution method {method}")
            if target not in species:
                raise FormatError(f"evolution target {target} is not a real species")
            edges.append({"species_index": index, "evolution_slot": slot,
                          "record_offset": position, "method": method,
                          "condition": condition, "target_species_index": target})
    return species, edges


def evolution_families(original_rel: bytes, tables: dict) -> tuple[dict[int, int], dict[int, list[int]]]:
    """Return all real species' undirected components, keyed by minimum index."""
    species, edges = _species_and_edges(original_rel, tables)
    neighbors = {index: set() for index in species}
    for edge in edges:
        source, target = edge["species_index"], edge["target_species_index"]
        neighbors[source].add(target)
        neighbors[target].add(source)
    family_by_species, families = {}, {}
    remaining = set(species)
    while remaining:
        first = min(remaining)
        pending, members = [first], set()
        while pending:
            current = pending.pop()
            if current in members:
                continue
            members.add(current)
            pending.extend(neighbors[current] - members)
        remaining.difference_update(members)
        identifier = min(members)
        families[identifier] = sorted(members)
        for index in sorted(members):
            family_by_species[index] = identifier
    return dict(sorted(family_by_species.items())), families


def evolution_stage_info(original_rel: bytes, tables: dict) -> dict[int, dict]:
    """Directed stages and longest chain per family, including babies and branches.

    A branched family can contain many species while having only two stages.
    Cycles are refused rather than interpreted as an evolution stage.
    """
    from heapq import heapify, heappop, heappush

    species, edges = _species_and_edges(original_rel, tables)
    family_by_species, families = evolution_families(original_rel, tables)
    parents = {index: set() for index in species}
    children = {index: set() for index in species}
    for edge in edges:
        source, target = edge["species_index"], edge["target_species_index"]
        children[source].add(target)
        parents[target].add(source)
    remaining = {index: len(parents[index]) for index in species}
    pending = [index for index in species if not parents[index]]
    heapify(pending)
    depth = {index: 0 for index in pending}
    longest = dict(depth)
    roots = {index: {index} for index in pending}
    visited = 0
    while pending:
        current = heappop(pending)
        visited += 1
        for target in sorted(children[current]):
            depth[target] = min(depth.get(target, depth[current] + 1), depth[current] + 1)
            longest[target] = max(longest.get(target, 0), longest[current] + 1)
            roots.setdefault(target, set()).update(roots[current])
            remaining[target] -= 1
            if remaining[target] == 0:
                heappush(pending, target)
    if visited != len(species):
        raise FormatError("evolution graph contains a cycle")
    lengths = {family: 1 + max(longest[index] for index in members)
               for family, members in families.items()}
    return {index: {"stage": depth[index], "base_form": not parents[index],
                    "final_form": bool(parents[index]) and not children[index],
                    "family_stages": lengths[family_by_species[index]],
                    "base_species": sorted(roots[index])}
            for index in sorted(species)}


def patch_evolutions(original_rel: bytes, tables: dict, enabled_groups: set[str] | None = None) -> tuple[bytes, dict]:
    """Apply exactly fifteen recognized PAL method/condition substitutions.

    Alternate branches use distinct item triggers. Native happiness, level,
    stat-dependent, PID-dependent and additional-Pokemon rules remain intact.
    """
    _, edges = _species_and_edges(original_rel, tables)
    expected = {(source, target): (old_method, old_condition, new_method, new_condition)
                for source, target, old_method, old_condition, new_method, new_condition
                in EVOLUTION_FIXES}
    found = {}
    for edge in edges:
        key = (edge["species_index"], edge["target_species_index"])
        if key in expected:
            if key in found:
                raise FormatError("duplicate expected evolution edge")
            if (edge["method"], edge["condition"]) != expected[key][:2]:
                raise FormatError(f"unexpected original evolution method/condition for {key}")
            found[key] = edge
        elif edge["method"] in (2, 3, 5, 6, 15):
            raise FormatError(f"unrecognized blocked evolution edge {key}")
    if set(found) != set(expected):
        raise FormatError(f"missing expected evolution edges: {sorted(set(expected) - set(found))}")

    modified = bytearray(original_rel)
    edits, allowed = [], set()
    for key, edge in sorted(found.items(), key=lambda item: item[1]["record_offset"]):
        old_method, old_condition, new_method, new_condition = expected[key]
        group = ("coquiperl" if key[0] == 373 else "trade" if old_method == 5 else
                 "trade_items" if old_method == 6 else "day_night" if old_method in (2, 3) else "beauty")
        if enabled_groups is not None and group not in enabled_groups:
            continue
        position = edge["record_offset"]
        modified[position] = new_method
        struct.pack_into(">H", modified, position + 2, new_condition)
        allowed.update((position, position + 2, position + 3))
        edits.append({"species_index": key[0], "evolution_slot": edge["evolution_slot"],
                      "target_species_index": key[1], "record_offset": position,
                      "method_field_offset": position, "condition_field_offset": position + 2,
                      "old_method": old_method, "old_condition": old_condition,
                      "new_method": new_method, "new_condition": new_condition})
    result = bytes(modified)
    changes = [{"offset": index, "before": old, "after": new}
               for index, (old, new) in enumerate(zip(original_rel, result, strict=True)) if old != new]
    if any(change["offset"] not in allowed for change in changes):
        raise FormatError("unexpected bytes changed outside evolution methods/conditions")
    if evolution_families(original_rel, tables) != evolution_families(result, tables):
        raise FormatError("evolution family membership changed")
    plan = {"version": "colosseum-evolution-rules-v3", "edit_count": len(edits),
            "edits": edits, "changed_rel_bytes": len(changes), "byte_changes": changes,
            "source_rel_sha256": sha256(original_rel), "patched_rel_sha256": sha256(result),
            "targets_and_native_branches_preserved": True}
    return result, plan


def unique_shadow_picks(original_rel: bytes, tables: dict, seed: str,
                        base_picks: dict[int, int]) -> tuple[dict[int, int], dict]:
    """Retain each family's lowest-ID draw, then reroll only its duplicates."""
    # Import locally so callers can compose this helper with the v1 transformer.
    from .randomize_trainers import choose_species

    family_by_species, families = evolution_families(original_rel, tables)
    if len(families) < SHADOW_GROUP_COUNT:
        raise FormatError("fewer than 48 evolution families are available")
    if len(base_picks) != SHADOW_GROUP_COUNT:
        raise FormatError("expected exactly 48 active shadow-group picks")
    shadows = _table(original_rel, tables, "shadow", 4)
    original_species = {}
    groups = defaultdict(list)
    pool = sorted(family_by_species)
    # Ensure seed validation is identical even if all base families are distinct.
    choose_species(seed, "shadow-family-v3:validation", pool, pool[0])
    for sid, selected in sorted(base_picks.items()):
        if type(sid) is not int or not 0 < sid < shadows["count"]:
            raise FormatError(f"invalid active shadow ID {sid}")
        position = shadows["offset"] + sid * shadows["stride"]
        old = struct.unpack_from(">H", original_rel, position + 2)[0]
        if type(selected) is not int or selected not in family_by_species or old not in family_by_species:
            raise FormatError("shadow pick/original species is not a real species")
        if old == selected:
            raise FormatError("base shadow pick must differ from its original species")
        original_species[sid] = old
        groups[family_by_species[selected]].append(sid)

    retained = sorted(ids[0] for ids in groups.values())
    rerolled = sorted(sid for ids in groups.values() for sid in ids[1:])
    # Reserve ALL winning base families before choosing any replacement.
    used_families = set(groups)
    final = {sid: base_picks[sid] for sid in retained}
    reroll_rows = []
    for sid in rerolled:
        remaining = [index for index in pool if family_by_species[index] not in used_families]
        key = f"shadow-family-v3:{sid}"
        try:
            selected = choose_species(seed, key, remaining, original_species[sid])
        except ValueError as exc:
            raise FormatError(f"no eligible unused-family replacement for shadow ID {sid}") from exc
        final[sid] = selected
        used_families.add(family_by_species[selected])
        reroll_rows.append({"shadow_id": sid, "key": key,
                            "old_species_index": original_species[sid],
                            "base_species_index": base_picks[sid],
                            "new_species_index": selected,
                            "base_family": family_by_species[base_picks[sid]],
                            "new_family": family_by_species[selected],
                            "remaining_species_pool_size": len(remaining)})
    final = dict(sorted(final.items()))
    if len(final) != SHADOW_GROUP_COUNT or len({family_by_species[index] for index in final.values()}) != SHADOW_GROUP_COUNT:
        raise FormatError("shadow families are not all distinct")
    plan = {"version": "shadow-family-v3", "seed": seed,
            "source_rel_sha256": sha256(original_rel), "shadow_group_count": len(final),
            "available_family_count": len(families), "base_distinct_family_count": len(groups),
            "final_distinct_family_count": len(final), "retained_shadow_ids": retained,
            "rerolled_shadow_ids": rerolled, "rerolls": reroll_rows,
            "all_evolution_stages_eligible": True}
    return final, plan
