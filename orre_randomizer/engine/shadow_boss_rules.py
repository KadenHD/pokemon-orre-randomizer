"""Seeded boss-Shadow species policies over the verified original PAL tables.

Every appearance of a Shadow ID shares one pick. The unique-family option is
solved across all active Shadows with bipartite matching, rather than rerolling
the seven boss groups after other encounters have consumed their candidates.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import struct

from .analyze_game import FormatError, check_range, u32
from ..i18n import Message
from .evolution_rules import evolution_families
from .family_matching import match_families
from .inspect_tables import u16
from .randomize_trainers import choose_species
from .species_rules import LEGENDARY_NATIONAL, species_catalog
from .pool_filters import has_exclusions, species_excluded

VERSION = "shadow-boss-species-sha256-v1"
LEGENDARY_MODES = frozenset(("any", "preserve", "exclude"))
POWER_MODES = frozenset(("global", "similar", "free"))


def _settings(options) -> tuple[str, str, int]:
    legendary = getattr(options, "boss_shadow_legendary_mode", "any")
    power = getattr(options, "boss_shadow_power_mode", "global")
    minimum = getattr(options, "boss_shadow_min_bst", 0)
    if (type(legendary) is not str or legendary not in LEGENDARY_MODES
            or type(power) is not str or power not in POWER_MODES):
        raise ValueError("mode de Pokémon obscur de boss invalide")
    if type(minimum) is not int or not 0 <= minimum <= 780:
        raise ValueError("le total minimal des obscurs de boss doit être compris entre 0 et 780")
    return legendary, power, minimum


def shadow_boss_rules_active(options) -> bool:
    """Defaults intentionally keep the legacy v0.4 species draws unchanged."""
    return _settings(options) != ("any", "global", 0) or has_exclusions(options)


def _flag(options, name: str, default: bool) -> bool:
    value = getattr(options, name, default)
    if type(value) is not bool:
        raise ValueError(f"{name} doit être un booléen")
    return value


def _rank(seed: str, key: str, value: int) -> bytes:
    raw = seed.encode("utf-8")
    if not 1 <= len(raw) <= 256:
        raise ValueError("seed must contain 1..256 UTF-8 bytes")
    return hashlib.sha256(VERSION.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big")
                          + raw + b"\0" + key.encode("ascii") + b"\0"
                          + str(value).encode("ascii")).digest()


def _position(data: bytes, tables: dict, name: str, index: int, minimum: int) -> int:
    try:
        table = tables[name]
        start, count, stride = (table[key] for key in ("offset", "count", "stride"))
    except (KeyError, TypeError) as error:
        raise FormatError(f"table {name} absente pour les obscurs des boss") from error
    if (any(type(value) is not int for value in (start, count, stride)) or start < 0
            or stride < minimum or not 0 <= index < count):
        raise FormatError(f"entrée {name} invalide pour les obscurs des boss")
    pos = start + index * stride
    check_range(data, pos, stride, name)
    return pos


def _match_families(seed: str, pools: dict[int, list[int]], families: dict[int, int],
                    catalog: dict, originals: dict[int, int], balanced: dict[int, bool],
                    boss_ids: set[int]) -> dict[int, int] | None:
    """Complete deterministic augmenting-path matching; no greedy dead end."""
    edges = {}
    for sid, pool in sorted(pools.items()):
        grouped = defaultdict(list)
        for index in pool:
            grouped[families[index]].append(index)
        target = catalog[originals[sid]]["total"]
        edges[sid] = sorted(grouped, key=lambda family: (
            min(abs(catalog[i]["total"] - target) for i in grouped[family]) if balanced[sid] else 0,
            _rank(seed, f"family-order:{sid}", family), family))
    order = sorted(edges, key=lambda sid: (len(edges[sid]), sid not in boss_ids,
                                          _rank(seed, "group-order", sid), sid))
    chosen = match_families(edges, order)
    return chosen if len(chosen) == len(edges) else None


def _power_preference(pool: list[int], old: int, catalog: dict) -> list[int]:
    target = catalog[old]["total"]
    tolerance = max(50, target // 5)
    close = [i for i in pool if abs(catalog[i]["total"] - target) <= tolerance]
    if close:
        return close
    distance = min(abs(catalog[i]["total"] - target) for i in pool)
    return [i for i in pool if abs(catalog[i]["total"] - target) == distance]


def apply_shadow_boss_tables(original: bytes, current: bytes, seed: str, options,
                            tables: dict, bosses: list[dict], *, allocate=None) -> tuple[bytes, dict]:
    """Pure core; production validates the pinned boss identities first.

    ``similar`` is a strict +/- max(50, 20%) original-BST constraint. ``global``
    retains the existing window/nearest preference, with a reported fallback if
    all-family uniqueness requires another eligible family. Generation, legend,
    minimum BST and strict-similarity exclusions are never relaxed.
    """
    legendary_mode, power_mode, minimum = _settings(options)
    report = {"version": VERSION, "legendary_mode": legendary_mode, "power_mode": power_mode,
              "minimum_bst": minimum, "active": False, "picks": [], "boss_groups": [],
              "changed_bytes": 0, "all_changes_whitelisted": True,
              "levels_and_capture_rates_preserved": True,
              "shadow_metadata_identities_preserved": True,
              "bst_scope": "original species base-stat totals, before optional stat redistribution"}
    if len(original) != len(current):
        raise FormatError("les règles des obscurs de boss doivent conserver la taille du REL")
    if not _flag(options, "randomize_shadows", True):
        report["inactive_reason"] = "Shadow species randomization disabled"
        return current, report
    if allocate is None and not shadow_boss_rules_active(options):
        report["inactive_reason"] = "default policies preserve legacy draws"
        return current, report
    _rank(seed, "validation", 0)
    catalog = species_catalog(original, tables)
    families, _ = evolution_families(original, tables)
    unique = _flag(options, "unique_shadows", True)
    global_balance = _flag(options, "balance_species", False)
    generations = tuple(_flag(options, f"allow_gen{i}", True) for i in (1, 2, 3))
    legends = _flag(options, "allow_legendaries", True)
    originals, metadata = {}, {}
    for sid in range(1, tables["shadow"]["count"]):
        pos = _position(original, tables, "shadow", sid, 4)
        index = u16(original, pos + 2)
        if index:
            if index not in catalog:
                raise FormatError("une espèce obscure originale est invalide")
            originals[sid], metadata[sid] = index, pos + 2
    if not originals:
        raise FormatError("aucun groupe obscur n’a été identifié")
    aliases = defaultdict(list)
    for index in range(tables["trainer_pokemon"]["count"]):
        pos = _position(original, tables, "trainer_pokemon", index, 0x50)
        old, sid = u16(original, pos + 0xA), original[pos + 3]
        if bool(old) != bool(u16(current, pos + 0xA)) or current[pos + 3] != sid:
            raise FormatError("les emplacements ou identifiants obscurs ont changé")
        if old and sid:
            if sid not in originals or old != originals[sid]:
                raise FormatError("les apparitions d’un obscur original sont incohérentes")
            if u32(original, pos + 0x14) != u32(original, catalog[old]["offset"] + 0x18):
                raise FormatError("surnom personnalisé d’un obscur non pris en charge")
            if original[pos] not in (0, 1, 0xFF):
                raise FormatError("sélecteur de talent obscur non reconnu")
            aliases[sid].append((index, pos))
    if set(aliases) != set(originals):
        raise FormatError("un groupe obscur n’a aucune apparition de dresseur")
    boss_groups = defaultdict(list)
    for boss in sorted(bosses, key=lambda row: (row["trainer_id"], row["key"])):
        ids = set()
        for slot in boss["slots"]:
            pos = _position(original, tables, "trainer_pokemon", slot["index"], 0x50)
            sid = original[pos + 3]
            if slot.get("offset", pos) != pos or slot.get("shadow_id", sid) != sid:
                raise FormatError("l’inventaire obscur d’un boss est incohérent")
            if sid and u16(original, pos + 0xA):
                if sid not in originals:
                    raise FormatError("un boss référence un groupe obscur absent")
                ids.add(sid)
        for sid in sorted(ids):
            boss_groups[sid].append({"key": boss["key"], "trainer_id": boss["trainer_id"]})
    boss_ids = set(boss_groups)
    if not boss_ids:
        raise FormatError("aucun obscur des boss identifiés n’est disponible")
    hard, preferred, balanced = {}, {}, {}
    for sid, old in sorted(originals.items()):
        is_boss = sid in boss_ids
        old_legend = catalog[old]["national_dex"] in LEGENDARY_NATIONAL
        pool = []
        for index, row in sorted(catalog.items()):
            national = row["national_dex"]
            generation = 0 if national <= 151 else 1 if national <= 251 else 2
            legend = national in LEGENDARY_NATIONAL
            if (index == old or national == 292 or not generations[generation] or (legend and not legends)
                    or species_excluded(row, options)):
                continue
            if is_boss and (row["total"] < minimum or
                    legendary_mode == "exclude" and legend or
                    legendary_mode == "preserve" and legend != old_legend):
                continue
            if is_boss and power_mode == "similar" and abs(row["total"] - catalog[old]["total"]) > max(50, catalog[old]["total"] // 5):
                continue
            pool.append(index)
        if not pool:
            if has_exclusions(options):
                raise FormatError("Aucun Pokémon admissible avec ces filtres. Autorisez d’autres espèces ou types.")
            label = Message("de boss ") if is_boss else ""
            raise FormatError(Message("Aucune espèce admissible pour l’obscur {label}n°{sid}. "
                                      "Vérifiez les générations, légendaires, puissance minimale et puissance comparable.",
                                      label=label, sid=sid))
        hard[sid] = pool
        balanced[sid] = (power_mode == "similar" or power_mode == "global" and global_balance) if is_boss else global_balance
        preferred[sid] = _power_preference(pool, old, catalog) if balanced[sid] else pool
    assignments = allocate(hard, preferred) if allocate is not None else None
    if unique and assignments is None:
        assignments = _match_families(seed, preferred, families, catalog, originals, balanced, boss_ids)
        if assignments is None:
            assignments = _match_families(seed, hard, families, catalog, originals, balanced, boss_ids)
        if assignments is None:
            raise FormatError("Impossible d’attribuer une famille d’évolution distincte à chaque obscur "
                              "avec ces règles de boss. Élargissez les espèces autorisées ou assouplissez "
                              "les règles de boss ; aucune exclusion n’a été contournée.")
    output, allowed, picks = bytearray(current), set(), {}
    for sid, old in sorted(originals.items()):
        pool = hard[sid]
        if assignments is not None:
            pool = [index for index in pool if families[index] == assignments[sid]]
        if balanced[sid]:
            pool = _power_preference(pool, old, catalog)
        new = choose_species(seed, f"{VERSION}:shadow:{sid}", pool, -1)
        picks[sid] = new
        struct.pack_into(">H", output, metadata[sid], new)
        allowed.update((metadata[sid], metadata[sid] + 1))
        for index, pos in aliases[sid]:
            struct.pack_into(">H", output, pos + 0xA, new)
            struct.pack_into(">I", output, pos + 0x14, u32(original, catalog[new]["offset"] + 0x18))
            output[pos] = 0 if original[pos] == 1 and not catalog[new]["abilities"][1] else original[pos]
            allowed.update((pos, pos + 0xA, pos + 0xB, *range(pos + 0x14, pos + 0x18)))
        report["picks"].append({"shadow_id": sid, "boss": sid in boss_ids,
            "boss_appearances": boss_groups.get(sid, []), "old_species_index": old,
            "new_species_index": new, "national_dex": catalog[new]["national_dex"],
            "family": families[new], "original_bst": catalog[old]["total"],
            "replacement_bst": catalog[new]["total"], "candidate_count": len(hard[sid]),
            "preferred_candidate_count": len(preferred[sid]),
            "power_preference_fallback": new not in preferred[sid],
            "trainer_pokemon_indices": [index for index, _ in aliases[sid]]})
    if unique and len({families[index] for index in picks.values()}) != len(originals):
        raise FormatError("les familles obscures ne sont pas toutes distinctes")
    result = bytes(output)
    changed = {i for i, (before, after) in enumerate(zip(current, result, strict=True)) if before != after}
    if changed - allowed:
        raise FormatError("les règles des obscurs de boss ont modifié un champ non autorisé")
    report.update(active=True, boss_groups=sorted(boss_ids), shadow_group_count=len(originals),
                  distinct_family_count=len({families[index] for index in picks.values()}),
                  unique_families=unique, changed_bytes=len(changed),
                  power_preference_fallback_ids=[row["shadow_id"] for row in report["picks"]
                                                 if row["power_preference_fallback"]])
    return result, report


def apply_shadow_boss_rules(original: bytes, current: bytes, seed: str, options,
                           tables: dict | None = None, *, allocate=None) -> tuple[bytes, dict]:
    """Validate the original fingerprint and seven pinned boss identities."""
    if (allocate is None and not shadow_boss_rules_active(options)) or not _flag(options, "randomize_shadows", True):
        return apply_shadow_boss_tables(original, current, seed, options, tables or {}, [])
    # Local import avoids boss_rules -> gameplay_rules -> this module cycling.
    from .boss_rules import boss_inventory
    verified, bosses = boss_inventory(original)
    if tables is not None and any(tables.get(name) != table for name, table in verified.items()):
        raise FormatError("les tables des obscurs de boss diffèrent de l’inventaire PAL vérifié")
    return apply_shadow_boss_tables(original, current, seed, options, verified, bosses, allocate=allocate)
