"""Keep native post-Snag copies of a Colosseum team on the same seeded draw.

Identify a battle by its trainer row, excluding its team pointer and dialogue.
Its ordinary Pokemon must occur in the same order with byte-identical native
records, excluding their opaque per-record identifier. Genuine progression
teams, their levels and the native replacement for a captured Shadow stay apart.
"""
from collections import defaultdict
from dataclasses import replace
import struct

from .analyze_game import FormatError, check_range, u32
from .inspect_tables import u16
from .randomize_trainers import choose_species, layout

VERSION = "trainer-post-snag-aliases-v1"

def merge_trainer_aliases(*groups):
    """Flatten overlapping alias sets to one deterministic final source."""
    parents = {}

    def root(index):
        if type(index) is not int or not 0 <= index < 0x10000:
            raise FormatError("invalid trainer alias index")
        parents.setdefault(index, index)
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for source, alias in (pair for group in groups for pair in group):
        a, b = root(source), root(alias)
        parents[max(a, b)] = min(a, b)
    return tuple((root(index), index) for index in sorted(parents) if root(index) != index)


def _position(data, table, index):
    if not 0 <= index < table["count"] or table["stride"] < 0x34:
        raise FormatError("invalid rematch table record")
    position = table["offset"] + index * table["stride"]
    check_range(data, position, table["stride"], "rematch record")
    return position


def rematch_inventory(original, tables):
    """Return proven native capture-state pairs and canonical ordinary slots."""
    trainers, party = tables["trainers"], tables["trainer_pokemon"]
    if trainers["stride"] != 0x34 or party["stride"] != 0x50:
        raise FormatError("unsupported native rematch record layout")
    groups = defaultdict(list)

    def team(first):
        result = []
        if first + 6 > party["count"]:
            raise FormatError("rematch team exceeds Pokemon table")
        for index in range(first, first + 6):
            position = _position(original, party, index)
            raw = original[position:position + 0x50]
            if u16(raw, 0xA):
                result.append((index, raw[3], raw[:0x18] + raw[0x1C:]))
        return result

    for trainer in range(trainers["count"]):
        position = _position(original, trainers, trainer)
        raw = original[position:position + 0x34]
        first = u16(raw, 4)
        if first:
            # Native 0x24/0x28/0x2C are the three battle dialogue IDs. A post-
            # capture line can change without changing the team (Reath 125/126).
            groups[raw[:4] + raw[6:0x24] + raw[0x30:]].append((trainer, team(first)))
    pairs, parents = [], {}

    def root(index):
        parents.setdefault(index, index)
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for group in groups.values():
        for trainer, before in group:
            shadows = [shadow for _, shadow, _ in before if shadow]
            ordinary = [(index, signature) for index, shadow, signature in before if not shadow]
            if not shadows or not ordinary:
                continue
            for captured_trainer, after in group:
                if any(shadow for _, shadow, _ in after):
                    continue
                if not len(ordinary) <= len(after) <= len(before):
                    continue
                shared, cursor = [], 0
                for index, signature in ordinary:
                    while cursor < len(after) and after[cursor][2] != signature:
                        cursor += 1
                    if cursor == len(after):
                        break
                    shared.append((index, after[cursor][0]))
                    cursor += 1
                if len(shared) != len(ordinary) or all(a == b for a, b in shared):
                    continue
                matched = {alias for _, alias in shared}
                pairs.append({"trainer": trainer, "captured_trainer": captured_trainer,
                              "shadow_ids": shadows, "shared_slots": shared,
                              "replacement_slots": [index for index, _, _ in after if index not in matched]})
                for source, alias in shared:
                    a, b = root(source), root(alias)
                    parents[max(a, b)] = min(a, b)
    aliases = tuple((root(index), index) for index in sorted(parents) if root(index) != index)
    return pairs, aliases


def _repair_replacements(original, output, tables, pairs, seed, options, boss_ids):
    """Retain final common teammates; resolve a replacement's own constraints."""
    from .evolution_rules import evolution_families, evolution_stage_info
    from .species_rules import candidate_species, species_catalog
    from .gameplay_rules import MOVE_FIELDS, choose_moves, move_catalog

    theme = options.trainer_theme_mode if options.randomize_trainers else "none"
    variety = options.boss_team_variety
    if not options.randomize_trainers or (theme == "none" and not variety):
        return [], []
    catalog, native = species_catalog(bytes(output), tables), species_catalog(original, tables)
    families = evolution_families(original, tables)[0]
    stages = evolution_stage_info(original, tables)
    edits, unresolved, handled = [], [], set()
    moves = None
    for pair in pairs:
        diverse = variety and pair["captured_trainer"] in boss_ids
        common = [u16(output, _position(output, tables["trainer_pokemon"], index) + 0xA)
                  for _, index in pair["shared_slots"]]
        shared_types = set.intersection(*(set(catalog[index]["types"]) for index in common))
        reserved = {families[index] for index in common} if diverse else set()
        for index in pair["replacement_slots"]:
            if index in handled:
                continue
            handled.add(index)
            position = _position(output, tables["trainer_pokemon"], index)
            current = u16(output, position + 0xA)
            if not ((diverse and families[current] in reserved)
                    or (theme != "none" and not shared_types.intersection(catalog[current]["types"]))):
                continue
            old = u16(original, position + 0xA)
            try:
                pool = candidate_species(original, tables, old,
                                         replace(options, balance_species=False), reserved)
                if diverse:
                    # Match the existing boss rule's Shedinja protection.
                    pool = [candidate for candidate in pool if catalog[candidate]["national_dex"] != 292]
                if theme != "none":
                    pool = [candidate for candidate in pool if shared_types.intersection(catalog[candidate]["types"])]
                if options.trainer_force_evolved and output[position + 4] >= options.trainer_evolution_level:
                    pool = [candidate for candidate in pool if stages[candidate]["final_form"]
                            or stages[candidate]["family_stages"] == 1]
                if options.balance_species and pool:
                    target = native[old]["total"]
                    close = [candidate for candidate in pool if abs(native[candidate]["total"] - target) <= max(50, target // 5)]
                    nearest = min(abs(native[candidate]["total"] - target) for candidate in pool)
                    pool = close or [candidate for candidate in pool if abs(native[candidate]["total"] - target) == nearest]
                selected = choose_species(seed, f"{VERSION}:replacement:{index}", pool, -1)
            except (FormatError, ValueError) as error:
                unresolved.append({"index": index, "reason": str(error)})
                continue
            struct.pack_into(">H", output, position + 0xA, selected)
            struct.pack_into(">I", output, position + 0x14, u32(output, catalog[selected]["offset"] + 0x18))
            if output[position] == 1 and not catalog[selected]["abilities"][1]:
                output[position] = 0
            before_moves = [u16(output, position + field) for field in MOVE_FIELDS]
            if options.randomize_trainer_moves and not any(move >= 355 for move in before_moves):
                if moves is None:
                    moves = move_catalog(original, tables)
                chosen = choose_moves(seed, f"{VERSION}:moves:{index}", catalog[selected],
                                      output[position + 4], moves, options,
                                      mode=options.randomize_trainer_moves, originals=before_moves)
                for field, move in zip(MOVE_FIELDS, chosen, strict=True):
                    struct.pack_into(">H", output, position + field, move)
            edits.append({"index": index, "before_species": current, "after_species": selected})
    return edits, unresolved


def synchronize_rematch_tables(original, current, tables, *, seed=None, options=None, boss_ids=()):
    """Copy final ordinary records while retaining every native opaque ID."""
    if len(original) != len(current):
        raise FormatError("rematch synchronization must preserve REL size")
    pairs, aliases = rematch_inventory(original, tables)
    output, allowed = bytearray(current), set()
    party = tables["trainer_pokemon"]
    for source, alias in aliases:
        a, b = (_position(current, party, index) for index in (source, alias))
        if any(current[position + 3] or not u16(current, position + 0xA) for position in (a, b)):
            raise FormatError("rematch input changed native ordinary-slot occupancy or Shadow identity")
        output[b:b + 0x18] = current[a:a + 0x18]
        output[b + 0x1C:b + 0x50] = current[a + 0x1C:a + 0x50]
        allowed.update(range(b, b + 0x18))
        allowed.update(range(b + 0x1C, b + 0x50))
    repairs, unresolved = ([], [])
    if pairs and options is not None:
        before_repairs = bytes(output)
        repairs, unresolved = _repair_replacements(original, output, tables, pairs, seed, options, set(boss_ids))
        for edit in repairs:
            position = _position(current, party, edit["index"])
            allowed.update((position, position + 0xA, position + 0xB, *range(position + 0x14, position + 0x18)))
            from .gameplay_rules import MOVE_FIELDS
            allowed.update(position + field + byte for field in MOVE_FIELDS for byte in (0, 1))
        if any(output[i] != before_repairs[i] and i not in allowed for i in range(len(output))):
            raise FormatError("rematch replacement changed an unauthorized field")
    changed = {i for i, (before, after) in enumerate(zip(current, output, strict=True)) if before != after}
    if changed - allowed:
        raise FormatError("rematch synchronization changed an unauthorized field")
    return bytes(output), {"version": VERSION, "battle_pairs": pairs, "ordinary_slot_aliases": aliases,
                           "changed_bytes": len(changed), "replacement_edits": repairs,
                           "unresolved_replacement_constraints": unresolved,
                           "opaque_identifiers_preserved": True, "shadow_slots_unchanged": True}, aliases


def synchronize_trainer_rematches(original, current, seed, options):
    tables, _ = layout(original)
    from .boss_rules import boss_inventory
    from .gameplay_rules import expanded_layout
    if options.randomize_trainer_moves:
        tables = expanded_layout(original)
    bosses = boss_inventory(original)[1] if options.boss_team_variety else ()
    return synchronize_rematch_tables(original, current, tables, seed=seed, options=options,
                                     boss_ids={row["trainer_id"] for row in bosses})
