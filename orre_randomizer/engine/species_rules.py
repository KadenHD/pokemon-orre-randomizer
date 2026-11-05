"""Pure, seeded species rules for the fingerprinted Colosseum PAL tables.

Production callers validate the original REL before providing its table layout.
The schema is corroborated by inspect_tables.py and the original PAL bytes. This
module changes only type, ability and base-stat fields, never evolution targets,
learnsets, levels, EXP groups or names. All randomness is keyed SHA-256 sampling.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, check_range
from .evolution_rules import evolution_families
from .pool_filters import species_excluded
from ..i18n import Message

VERSION = "species-properties-sha256-v1"
STAT_OFFSETS = (0x85, 0x87, 0x89, 0x8B, 0x8D, 0x8F)
VALID_TYPES = frozenset(range(18)) - {9}  # Mystery is not a real PAL species type.
WONDER_GUARD = 25
SHEDINJA_NATIONAL = 292
LEGENDARY_NATIONAL = frozenset((144, 145, 146, 150, 151, 243, 244, 245, 249,
                               250, 251, 377, 378, 379, 380, 381, 382, 383,
                               384, 385, 386))


def _flag(options, name: str, default: bool) -> bool:
    value = getattr(options, name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _sample(seed: str, key: str, count: int) -> int:
    """Unbiased integer sampling with domain and per-property isolation."""
    raw = seed.encode("utf-8")
    if not 1 <= len(raw) <= 256 or count < 1:
        raise ValueError("invalid species-rule seed or candidate count")
    prefix = VERSION.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big") + raw
    prefix += b"\0" + key.encode("ascii") + b"\0"
    limit = (1 << 256) // count * count
    counter = 0
    while True:
        value = int.from_bytes(hashlib.sha256(prefix + counter.to_bytes(4, "big")).digest(), "big")
        if value < limit:
            return value % count
        counter += 1


def _pick(seed: str, key: str, candidates) -> int:
    choices = sorted(set(candidates))
    if not choices:
        raise FormatError("species property has no safe candidates")
    return choices[_sample(seed, key, len(choices))]


def species_catalog(original: bytes, tables: dict) -> dict[int, dict]:
    """Read actual internal IDs, rather than confusing them with national IDs."""
    try:
        table = tables["species"]
        offset, count, stride = (table[key] for key in ("offset", "count", "stride"))
    except (KeyError, TypeError) as error:
        raise FormatError("missing species table layout") from error
    if any(type(value) is not int for value in (offset, count, stride)) or offset < 0 or count < 1 or stride < 0x91:
        raise FormatError("invalid species table layout")
    check_range(original, offset, count * stride, "species table")
    result, national_seen = {}, set()
    for index in range(count):
        pos = offset + index * stride
        national = struct.unpack_from(">H", original, pos + 0x10)[0]
        if not 1 <= national <= 386:
            continue
        if national in national_seen:
            raise FormatError("duplicate real national dex number")
        national_seen.add(national)
        types = tuple(original[pos + 0x30:pos + 0x32])
        abilities = tuple(original[pos + 0x32:pos + 0x34])
        stats = tuple(original[pos + field] for field in STAT_OFFSETS)
        if not set(types) <= VALID_TYPES or not abilities[0] or not all(stats):
            raise FormatError("invalid original real-species type, ability or base stats")
        result[index] = {"national_dex": national, "types": types, "abilities": abilities,
                         "stats": stats, "total": sum(stats), "offset": pos}
    if not result:
        raise FormatError("species table has no real species")
    return result


def candidate_species(original: bytes, tables: dict, old: int, options,
                      reserved_families: set[int] | None = None) -> list[int]:
    """Filter first, then balance within that pool; never relax exclusions.

    Balance uses the original species' BST. If none is within max(50, 20%) of
    that total, retain only the nearest available total(s). An empty eligible
    pool is an error, including when family uniqueness cannot be satisfied.
    """
    catalog = species_catalog(original, tables)
    if old not in catalog:
        raise FormatError("original replacement species is not a real species")
    generations = tuple(_flag(options, f"allow_gen{i}", True) for i in (1, 2, 3))
    legends = _flag(options, "allow_legendaries", True)
    pool = []
    for index, row in catalog.items():
        national = row["national_dex"]
        generation = 0 if national <= 151 else 1 if national <= 251 else 2
        if (index != old and generations[generation] and (legends or national not in LEGENDARY_NATIONAL)
                and not species_excluded(row, options)):
            pool.append(index)
    if reserved_families:
        families, _ = evolution_families(original, tables)
        pool = [index for index in pool if families[index] not in reserved_families]
    if not pool:
        raise FormatError(Message("Aucun Pokémon admissible avec ces filtres. Autorisez d’autres espèces ou types."))
    if _flag(options, "balance_species", False):
        target = catalog[old]["total"]
        tolerance = max(50, target // 5)
        close = [index for index in pool if abs(catalog[index]["total"] - target) <= tolerance]
        if close:
            pool = close
        else:
            nearest = min(abs(catalog[index]["total"] - target) for index in pool)
            pool = [index for index in pool if abs(catalog[index]["total"] - target) == nearest]
    return sorted(pool)


def _redistribute(seed: str, key: str, total: int, locked_hp: bool) -> tuple[int, ...]:
    """Weighted integer apportionment with exact totals and byte-sized stats."""
    output = [1] * 6
    available = list(range(1 if locked_hp else 0, 6))
    maximum_total = 1 + 5 * 255 if locked_hp else 6 * 255
    if not 6 <= total <= maximum_total:
        raise FormatError("base-stat total cannot satisfy byte bounds")
    remaining = total - sum(output)
    weights = {i: 1 + _sample(seed, f"{key}:weight:{i}", 65535) for i in available}
    while remaining:
        weight_sum = sum(weights[i] for i in available)
        saturated = [i for i in available if remaining * weights[i] // weight_sum >= 254]
        if saturated:
            for i in saturated:
                output[i] = 255
                remaining -= 254
                available.remove(i)
            continue
        portions = {i: remaining * weights[i] // weight_sum for i in available}
        remainder = remaining - sum(portions.values())
        order = sorted(available, key=lambda i: (-(remaining * weights[i] % weight_sum), i))
        for i in order[:remainder]:
            portions[i] += 1
        for i in available:
            output[i] += portions[i]
        remaining = 0
    return tuple(output)


def apply_species_rules(original: bytes, current: bytes, seed: str, options,
                        tables: dict) -> tuple[bytes, dict]:
    """Apply independent type, ability and stat rules over prior seeded changes.

    Family consistency shares keyed first/second draws but preserves whether a
    species was mono- or dual-type, and whether it had one or two abilities.
    Shedinja keeps its native types, abilities and one-HP mechanic: assigning
    Wonder Guard elsewhere could create an encounter without a weakness.
    """
    if len(original) != len(current):
        raise FormatError("species transform must preserve REL size")
    catalog = species_catalog(original, tables)
    do_types = _flag(options, "randomize_types", False)
    do_abilities = _flag(options, "randomize_abilities", False)
    do_stats = _flag(options, "randomize_stats", False)
    type_family = _flag(options, "types_family_consistent", True)
    ability_family = _flag(options, "abilities_family_consistent", True)
    preserve_total = _flag(options, "preserve_stat_totals", True)
    families = (evolution_families(original, tables)[0] if
                (do_types and type_family) or (do_abilities and ability_family) else {i: i for i in catalog})
    type_pool = sorted({value for row in catalog.values() for value in row["types"]})
    ability_pool = sorted({value for row in catalog.values() for value in row["abilities"]} - {0, WONDER_GUARD})
    output, allowed, edits = bytearray(current), set(), []
    for index, row in catalog.items():
        pos = row["offset"]
        protected = row["national_dex"] == SHEDINJA_NATIONAL
        new_types, new_abilities, new_stats = row["types"], row["abilities"], row["stats"]
        if do_types and not protected:
            identifier = families[index] if type_family else index
            first = _pick(seed, f"types:{identifier}:first", type_pool)
            second = (_pick(seed, f"types:{identifier}:second", set(type_pool) - {first})
                      if row["types"][0] != row["types"][1] else first)
            new_types = first, second
            output[pos + 0x30:pos + 0x32] = bytes(new_types)
            allowed.update((pos + 0x30, pos + 0x31))
        if do_abilities and not protected:
            identifier = families[index] if ability_family else index
            first = _pick(seed, f"abilities:{identifier}:first", ability_pool)
            second = (_pick(seed, f"abilities:{identifier}:second", set(ability_pool) - {first} or {first})
                      if row["abilities"][1] else 0)
            new_abilities = first, second
            output[pos + 0x32:pos + 0x34] = bytes(new_abilities)
            allowed.update((pos + 0x32, pos + 0x33))
        if do_stats:
            total = row["total"] if preserve_total else 250 + _sample(seed, f"stats:{index}:total", 431)
            new_stats = _redistribute(seed, f"stats:{index}", total, protected)
            for field, value in zip(STAT_OFFSETS, new_stats, strict=True):
                output[pos + field] = value
                allowed.add(pos + field)
        if (new_types, new_abilities, new_stats) != (row["types"], row["abilities"], row["stats"]):
            edits.append({"species_index": index, "national_dex": row["national_dex"],
                          "types_before": list(row["types"]), "types_after": list(new_types),
                          "abilities_before": list(row["abilities"]), "abilities_after": list(new_abilities),
                          "stats_before": list(row["stats"]), "stats_after": list(new_stats),
                          "total_before": row["total"], "total_after": sum(new_stats)})
    result = bytes(output)
    changed = {i for i, (before, after) in enumerate(zip(current, result, strict=True)) if before != after}
    if changed - allowed:
        raise FormatError("species patch changed an unauthorized field")
    return result, {"version": VERSION, "species_changed": len(edits), "changed_bytes": len(changed),
                    "types_randomized": do_types, "abilities_randomized": do_abilities,
                    "stats_randomized": do_stats, "stat_totals_preserved": not do_stats or preserve_total,
                    "types_family_consistent": do_types and type_family,
                    "abilities_family_consistent": do_abilities and ability_family,
                    "protected_species_national": [SHEDINJA_NATIONAL] if any(
                        row["national_dex"] == SHEDINJA_NATIONAL for row in catalog.values()) else [],
                    "wonder_guard_not_assigned_to_new_species": True,
                    "only_type_ability_stat_fields_changed": True, "edits": edits}
