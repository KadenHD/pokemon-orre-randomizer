"""XD battle rules for referenced DPKM slots and active DDPK encounters."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import math
import struct

from .engine.analyze_game import FormatError, check_range, parse_dol, u32
from .engine.gameplay_rules import USEFUL_ITEMS, damaging, pick
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.inspect_tables import u16
from .engine.level_curve import encounter_level
from .engine.qol_rules import EXPERIENCE_DIVISOR, experience_numerator
from .engine.shiny_rules import _Code


DPKM_STRIDE = 0x20
DPKM_MOVES = (0x14, 0x16, 0x18, 0x1A)
DDPK_STRIDE = 0x18
DDPK_START = 0x20
# Story fights and rematches, excluding the intro and roaming templates.
BOSS_TRAINERS = {
    61: 6067, 72: 6103, 104: 6127, 134: 6103, 165: 6130, 173: 6067,
    191: 6127, 193: 6005, 194: 6130, 196: 6046, 199: 6157, 200: 6157,
    201: 6157, 221: 6103,
}
# Nonzero held IDs present on referenced ordinary and Shadow opponents in
# all three rev-0 builds. Several are trade items or species-specific.
NATIVE_HELD_ITEMS = frozenset({
    134, 138, 140, 141, 168, 170, 179, 180, 183, 186, 187, 188, 196, 198,
    199, 200, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213,
    214, 215, 216, 217, 220, 221, 222, 223, 224, 225,
})
TEXT1_TO_RAM = 0x800030A0
TEXT2_HEADER = (0x08, 0x50, 0x98)
# Native initial arena low, OSSetArenaLo address, and its stw instruction.
ARENA = {
    "GXXP01": (0x805423A0, 0x800ABEB0, 0x906D82F0),
    "GXXE01": (0x80507DA0, 0x800AA968, 0x906D82F0),
    "GXXJ01": (0x804E5200, 0x800A6DFC, 0x906D82E8),
}
# OSInit's native lis/addi pair loads the arena floor above the startup stack.
# Checking BSS alone misses that stack: its clearing overwrote the old stubs.
ARENA_INITIALIZERS = {"GXXP01": 0x800AAE98, "GXXE01": 0x800A9950, "GXXJ01": 0x800A5DE4}
# Fixed instruction windows matched across the three retail DOLs. The EXP
# window spans the last award bonus through the native shadow/ordinary split.
DOL_CONTRACTS = {
    "GXXP01": {
        "experience": (0x80214CAC, 0x9C, "8f8b54f0ceaaaea02a1fff24b7f16b009f0fe8ffc5addacba005389937307226"),
        "purification": (0x801407D0, 0x60, "5f15376842333fe9c9646b0dd59a9ecdd05369dd569afff93e91b9d1513ecce6"),
    },
    "GXXE01": {
        "experience": (0x80212E68, 0x9C, "09bcd60e28f52b7f8bf651f4d26e224d4d465fb2798054644a16b796b28ee3b9"),
        "purification": (0x8013EF0C, 0x60, "5f15376842333fe9c9646b0dd59a9ecdd05369dd569afff93e91b9d1513ecce6"),
    },
    "GXXJ01": {
        "experience": (0x8020D8A0, 0x9C, "05ef3b4655274208734ec7a02d071c31de3a127b452fe56f70bfe7d0c9786da3"),
        "purification": (0x8013A318, 0x60, "c1aa474642cebda25ab4d8e8d7a7f008750a251c9b5022e52385053445d185f5"),
    },
}


def deck_rules_active(options):
    levels = (options.early_level_multiplier, options.mid_level_multiplier,
              options.late_level_multiplier) if options.progressive_levels else (options.trainer_level_multiplier,)
    return (any(value != 1.0 for value in levels) or options.randomize_held_items
            or options.randomize_trainer_moves or options.trainer_force_evolved
            or getattr(options, "boss_stronger", False) or getattr(options, "boss_team_variety", False)
            or (options.randomize_trainers and options.trainer_theme_mode != "none"))


def boss_shadows(deck):
    result = set()
    for trainer, identity in BOSS_TRAINERS.items():
        pos = 0x20 + trainer * 0x38
        if trainer >= u32(deck, 0x18) or u16(deck, pos + 6) != identity:
            raise FormatError("unexpected XD story boss identity")
        result.update(u16(deck, pos + 0x1C + 2 * slot) for slot in range(6) if deck[pos + 4] & (1 << slot))
    return result


def shadow_rules_active(options):
    return options.capture_rate_multiplier != 1.0 or options.minimum_catch_rate != 0


def _deck_teams(deck, shadow_slots):
    header = 0x10 + u32(deck, 0x14)
    trainers = u32(deck, 0x18)
    if deck[0x10:0x14] != b"DTNR" or header != 0x20 + trainers * 0x38:
        raise FormatError("unexpected XD trainer deck")
    check_range(deck, header, 0x10, "XD DPKM header")
    count = u32(deck, header + 8)
    start = header + 0x10
    if deck[header:header + 4] != b"DPKM" or u32(deck, header + 4) != 0x10 + count * DPKM_STRIDE:
        raise FormatError("unexpected XD opponent table")
    check_range(deck, start, count * DPKM_STRIDE, "XD DPKM records")
    teams, ordinary, shadows = {}, set(), set()
    for trainer in range(trainers):
        pos = 0x20 + trainer * 0x38
        team = set()
        for slot in range(6):
            index = u16(deck, pos + 0x1C + slot * 2)
            if index:
                (shadows if deck[pos + 4] & (1 << slot) else team).add(index)
        if team:
            if team & ordinary:
                raise FormatError("unexpected XD ordinary Pokémon shared across teams")
            teams[trainer] = sorted(team)
            ordinary.update(team)
    if (shadows != set(shadow_slots) or ordinary & set(shadow_slots.values())
            or any(not 0 < index < count for index in ordinary | set(shadow_slots.values()))):
        raise FormatError("inconsistent XD opponent references")
    return start, teams, ordinary


def _apply_trainer_species(original, output, name, start, teams, seed, options,
                           species, native, edges, eligible):
    theme_mode = options.trainer_theme_mode if options.randomize_trainers else "none"
    if theme_mode == "none" and not options.trainer_force_evolved:
        return []
    if theme_mode not in ("none", "random", "preserve"):
        raise FormatError("invalid XD trainer theme")

    @lru_cache(maxsize=None)
    def terminals(index):
        children = edges.get(index, ())
        if not children:
            return frozenset({index})
        return frozenset(child for edge in children for child in terminals(edge[3]))

    final_pool = {index for index in eligible if not edges.get(index)}
    changes = []
    for trainer, indices in teams.items():
        originals, candidates = {}, {}
        for index in indices:
            pos = start + index * DPKM_STRIDE
            before, current = u16(original, pos), u16(output, pos)
            forced = options.trainer_force_evolved and output[pos + 2] >= options.trainer_evolution_level
            if theme_mode == "none" and (not forced or not edges.get(current)):
                continue
            originals[index] = before, forced
            if options.randomize_trainers:
                candidates[index] = (final_pool if forced else eligible) - {before}
            else:
                candidates[index] = terminals(current) & eligible
            if not candidates[index]:
                raise FormatError(f"no eligible XD final stage for {name} opponent {index}")
        if not candidates:
            continue
        theme = None
        if theme_mode != "none":
            feasible = set.intersection(*(set(t for index in pool for t in species[index]["types"])
                                          for pool in candidates.values()))
            if theme_mode == "preserve":
                shared_native = set.intersection(*(set(native[before]["types"])
                                                   for before, _ in originals.values()))
                feasible = feasible & shared_native or feasible
            theme = pick(seed, f"xd:{name}:team:{trainer}:theme", feasible)
        for index, pool in candidates.items():
            pos = start + index * DPKM_STRIDE
            before, forced = originals[index]
            current = u16(output, pos)
            if theme is not None:
                pool = {candidate for candidate in pool if theme in species[candidate]["types"]}
            if options.balance_species:
                total = max(native[value]["total"] for value in (terminals(before) if forced else (before,)))
                pool = sorted(pool, key=lambda value: (abs(native[value]["total"] - total), value))[:40]
            after = pick(seed, f"xd:{name}:team:{trainer}:opponent:{index}", pool)
            struct.pack_into(">H", output, pos, after)
            changes.append({"trainer": trainer, "index": index, "before": current, "after": after,
                            "type": theme, "final_stage_required": forced})
    return changes


def _vary_boss_teams(original, result, start, teams, shadow_slots, seed, options, families, species,
                    native, eligible, edges, policy_edits):
    themes = {row["trainer"]: row["type"] for row in policy_edits}
    changes = []
    for trainer, slots in teams.items():
        pos = 0x20 + trainer * 0x38
        shadow_indices = [shadow_slots[u16(original, pos + 0x1C + 2 * slot)]
                          for slot in range(6) if original[pos + 4] & (1 << slot)]
        used = {families[u16(result, start + index * DPKM_STRIDE)] for index in shadow_indices}
        theme = themes.get(trainer)
        for index in slots:
            pos = start + index * DPKM_STRIDE
            old = u16(result, pos)
            if families[old] in used:
                final = options.trainer_force_evolved and result[pos + 2] >= options.trainer_evolution_level
                pool = [value for value in eligible if families[value] not in used
                        and (theme is None or theme in species[value]["types"])
                        and (not final or not edges.get(value))]
                if options.balance_species:
                    total = native[old]["total"]
                    pool = sorted(pool, key=lambda value: (abs(native[value]["total"] - total), value))[:40]
                if pool:
                    new = pick(seed, f"xd:boss:{trainer}:family:{index}", pool)
                    struct.pack_into(">H", result, pos, new)
                    changes.append({"index": index, "before": old, "after": new})
                    old = new
            used.add(families[old])
    return changes


def apply_deck_rules(original, current, name, shadow_slots, seed, options, *, move_randomizer,
                     edges, protected_shadows, eligible_species=None, original_species_catalog=None, families=None):
    """Apply XD trainer settings to an already species-patched deck."""
    report = {"trainer_level_edits": [], "trainer_move_edits": [], "held_item_edits": [],
              "trainer_policy_edits": [], "boss_edits": []}
    if not deck_rules_active(options):
        return current, report
    if len(current) != len(original):
        raise FormatError("unexpected XD trainer deck size")
    start, teams, ordinary = _deck_teams(original, shadow_slots)
    result = bytearray(current)
    species = move_randomizer.species
    original_species_catalog = original_species_catalog or species
    eligible = set(species) if eligible_species is None else set(eligible_species)
    active = {index: 0 for index in ordinary}
    active.update({index: sid for sid, index in shadow_slots.items() if sid not in protected_shadows})
    stronger = getattr(options, "boss_stronger", False)
    variety = getattr(options, "boss_team_variety", False)
    boss_teams = {}
    if name == "Story" and (stronger or variety):
        boss_shadows(original)
        boss_teams = {trainer: slots for trainer, slots in teams.items() if trainer in BOSS_TRAINERS}
    boost = {index for slots in boss_teams.values() for index in slots} if stronger else set()
    for index, sid in sorted(active.items()):
        pos = start + index * DPKM_STRIDE
        before = original[pos + 2]
        if not 1 <= before <= 100 or u16(current, pos) not in species:
            raise FormatError("invalid XD opponent level or species")
        level = encounter_level(before, options)
        if index in boost:
            level = min(100, (level * 11 + 5) // 10)
            result[pos + 8:pos + 14] = bytes(max(20, v) if v <= 31 else v for v in original[pos + 8:pos + 14])
            evs = bytes(max(64, v) for v in original[pos + 14:pos + 20])
            if sum(evs) <= 510:
                result[pos + 14:pos + 20] = evs
            report["boss_edits"].append({"index": index, "level": level, "strengthened": True})
        if before != level:
            result[pos + 2] = level
            report["trainer_level_edits"].append({"index": index, "shadow_id": sid,
                                                  "before": before, "after": level})
    report["trainer_policy_edits"] = _apply_trainer_species(
        original, result, name, start, teams, seed, options, species,
        original_species_catalog, edges, eligible,
    )
    if variety and boss_teams:
        report["boss_edits"].extend(_vary_boss_teams(
            original, result, start, boss_teams, shadow_slots, seed, options, families, species,
            original_species_catalog, eligible, edges, report["trainer_policy_edits"],
        ))
    held_pool = NATIVE_HELD_ITEMS & set(USEFUL_ITEMS) if options.useful_held_items_only else NATIVE_HELD_ITEMS
    for index, sid in sorted(active.items()):
        pos = start + index * DPKM_STRIDE
        before_moves = [u16(original, pos + offset) for offset in DPKM_MOVES]
        after_moves = before_moves
        if options.randomize_trainer_moves:
            after_moves = move_randomizer.moves(seed, f"xd:{name}:trainer:{index}",
                                               u16(result, pos), result[pos + 2], before_moves)
            if before_moves != after_moves:
                for offset, move in zip(DPKM_MOVES, after_moves, strict=True):
                    struct.pack_into(">H", result, pos + offset, move)
                report["trainer_move_edits"].append({"index": index, "shadow_id": sid,
                    "before": before_moves, "after": after_moves})
        before_item = u16(original, pos + 4)
        if options.randomize_held_items and before_item in NATIVE_HELD_ITEMS:
            pool = held_pool - {before_item}
            if not any(move in move_randomizer.catalog and move_randomizer.catalog[move]["type"] <= 8
                       and damaging(move_randomizer.catalog[move]) for move in after_moves):
                pool -= {186}  # Choice Band needs a physical attack in Gen III.
            after_item = pick(seed, f"xd:{name}:held:{index}", pool)
            struct.pack_into(">H", result, pos + 4, after_item)
            report["held_item_edits"].append({"index": index, "shadow_id": sid,
                                             "before": before_item, "after": after_item})
    return bytes(result), report


def apply_shadow_rules(dark, shadow_slots, options, *, protected_shadows):
    """Apply capture settings to the active DDPK rows."""
    report = {"capture_edits": []}
    if not shadow_rules_active(options):
        return dark, report
    if (dark[0x10:0x14] != b"DDPK" or u32(dark, 0x18) != 128
            or len(dark) != DDPK_START + 128 * DDPK_STRIDE):
        raise FormatError("unexpected XD Shadow deck")
    capture = options.capture_rate_multiplier
    minimum = options.minimum_catch_rate
    result = bytearray(dark)
    for sid, index in sorted(shadow_slots.items()):
        if not 1 <= sid <= 83:
            raise FormatError("invalid XD Shadow ID")
        pos = DDPK_START + sid * DDPK_STRIDE
        if dark[pos + 3] != 0x80 or u16(dark, pos + 6) != index:
            raise FormatError("invalid XD Shadow record")
        if sid in protected_shadows:
            continue
        old_catch = dark[pos + 1]
        if old_catch:
            new_catch = min(255, max(minimum, 1, math.floor(old_catch * capture + 0.5)))
            if new_catch != old_catch:
                result[pos + 1] = new_catch
                report["capture_edits"].append({"shadow_id": sid, "before": old_catch, "after": new_catch})
    return bytes(result), report


def _experience_stub(address, continuation, numerator):
    # r18 is the award, r11/r12 and CR0 are caller-volatile before the next bl.
    # The unsigned 16-bit cap avoids overflowing mul for any permitted ratio.
    code = _Code(address)
    code.emit(0x28120000)  # cmplwi r18,0
    code.conditional(0x41820000, "continue")
    code.emit(0x2812FFFF)  # cmplwi r18,65535
    code.conditional(0x40810000, "bounded")
    code.emit(0x3A400000, 0x6252FFFF)  # li r18,0; ori r18,r18,65535
    code.label("bounded")
    code.emit(0x3D600000 | (numerator >> 16), 0x616B0000 | (numerator & 0xFFFF),
              0x7D7259D6,  # mullw r11,r18,r11
              0x396B1388,  # addi r11,r11,5000 (nearest integer, ties upward)
              0x39802710,  # li r12,10000
              0x7E4B6396,  # divwu r18,r11,r12
              0x28120000)  # cmplwi r18,0
    code.conditional(0x40820000, "continue")
    code.emit(0x3A400001)  # positive native awards stay at least 1
    code.label("continue")
    code.emit(0x7E639B78)  # displaced mr r3,r19
    code.emit(branch(address + 4 * len(code.words), continuation))
    return code.finish()


def _purification_stub(address, continuation, multiplier):
    # f31 holds the delta and f1 the old gauge. Native code next reloads f0
    # and sets CR0 for its zero clamp. r12 is dead across the displaced add.
    constants = address + 64
    code = _Code(address)
    code.emit(0x3D800000 | (constants >> 16), 0x618C0000 | (constants & 0xFFFF),
              0xC00C0000,  # lfs f0,0(r12): zero
              0xFC1F0000)  # fcmpu cr0,f31,f0
    code.conditional(0x40800000, "add")
    code.emit(0xC00C0004, 0xEFFF0032)  # lfs f0,4(r12); fmuls f31,f31,f0
    code.label("add")
    code.emit(0xEC21F82A)  # displaced fadds f1,f1,f31
    code.emit(branch(address + 4 * len(code.words), continuation))
    payload = code.finish()
    if len(payload) != 64:
        raise AssertionError("XD purification constant relocation changed")
    return payload + struct.pack(">ff", 0.0, multiplier) + bytes(24)


def append_xd_dol_text(original, current, game_id, hooks):
    """Reserve or extend text2 and apply preimage-checked inline hooks.

    Each hook is a native RAM address, its displaced instruction, and a
    callable taking the new stub address and native continuation address.
    """
    section_ram, arena_setter, arena_store = ARENA[game_id]
    initializer = ARENA_INITIALIZERS[game_id] - TEXT1_TO_RAM
    expected_floor = struct.pack(">II", 0x3C600000 | ((section_ram + 0x8000) >> 16),
                                 0x38630000 | (section_ram & 0xFFFF))
    if any(data[initializer:initializer + 8] != expected_floor for data in (original, current)):
        raise FormatError("unexpected XD native arena floor")
    arena_offset = arena_setter - TEXT1_TO_RAM
    section_offset = (len(original) + 31) & ~31
    section_header = tuple(u32(current, offset) for offset in TEXT2_HEADER)
    previous_size = section_header[2]
    if (len(current) < len(original) or any(u32(original, offset) for offset in TEXT2_HEADER)
            or any(current[offset:offset + 4] != original[offset:offset + 4]
                   for offset in range(0, 0x100, 4) if offset not in TEXT2_HEADER)
            or original[arena_offset:arena_offset + 8] != struct.pack(">II", arena_store, 0x4E800020)):
        raise FormatError("unsupported XD DOL arena layout")
    if previous_size:
        if (section_header != (section_offset, section_ram, previous_size)
                or section_offset + previous_size != len(current) or previous_size % 32
                or current[section_offset:section_offset + 32] != _arena_guard(section_ram + previous_size, arena_store)
                or u32(current, arena_offset) != branch(arena_setter, section_ram)):
            raise FormatError("invalid existing XD text section reservation")
        code = bytearray(current[section_offset:])
    else:
        if any(section_header) or len(current) != len(original) or u32(current, arena_offset) != arena_store:
            raise FormatError("invalid unpatched XD text section")
        code = bytearray(32)
    descriptor = parse_dol(original)
    if (descriptor["bss_ram_address"] + descriptor["bss_size"] > section_ram
            or any(item["ram_address"] + item["size"] > section_ram for item in descriptor["sections"])):
        raise FormatError("native XD memory overlaps the text reservation")
    output = bytearray(current[:section_offset])
    report = []
    for address, expected, stub_builder in hooks:
        hook_offset = address - TEXT1_TO_RAM
        if u32(current, hook_offset) != expected or u32(original, hook_offset) != expected:
            raise FormatError("unexpected XD DOL hook instruction")
        stub = section_ram + len(code)
        payload = stub_builder(stub, address + 4)
        if not payload or len(payload) % 32:
            raise FormatError("invalid XD DOL stub alignment")
        code.extend(payload)
        struct.pack_into(">I", output, hook_offset, branch(address, stub))
        report.append({"hook_address": address, "stub_address": stub, "stub_size": len(payload),
                       "continuation": address + 4})
    reserved_end = section_ram + len(code)
    if reserved_end >= 0x81700000:
        raise FormatError("XD DOL code exceeds the arena reservation")
    code[:32] = _arena_guard(reserved_end, arena_store)
    output.extend(bytes(section_offset - len(output)))
    output.extend(code)
    for offset, value in zip(TEXT2_HEADER, (section_offset, section_ram, len(code)), strict=True):
        struct.pack_into(">I", output, offset, value)
    struct.pack_into(">I", output, arena_offset, branch(arena_setter, section_ram))
    return bytes(output), report


def apply_dol_battle_rules(original, current, game_id, options):
    numerator = experience_numerator(options.experience_multiplier)
    multiplier = options.purification_multiplier
    if type(multiplier) is not int or not 1 <= multiplier <= 10:
        raise ValueError("XD purification multiplier must be an integer from 1 to 10")
    report = {"experience_multiplier": options.experience_multiplier,
              "purification_multiplier": multiplier, "hooks": []}
    requested = []
    if numerator != EXPERIENCE_DIVISOR:
        requested.append(("experience", 0x18, 0x7E639B78,
                          lambda address, continuation: _experience_stub(address, continuation, numerator)))
    if multiplier != 1:
        requested.append(("purification", 0x28, 0xEC21F82A,
                          lambda address, continuation: _purification_stub(address, continuation, multiplier)))
    if not requested:
        return current, report
    hooks = []
    for name, delta, expected, stub in requested:
        base, length, digest = DOL_CONTRACTS[game_id][name]
        offset = base - TEXT1_TO_RAM
        if any(hashlib.sha256(data[offset:offset + length]).hexdigest() != digest for data in (original, current)):
            raise FormatError(f"unexpected native XD {name} instructions")
        hooks.append((base + delta, expected, stub))
    output, report["hooks"] = append_xd_dol_text(original, current, game_id, hooks)
    for (name, *_), hook in zip(requested, report["hooks"], strict=True):
        hook["key"] = name
    return output, report
