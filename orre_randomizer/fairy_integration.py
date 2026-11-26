"""One 57-TM gameplay transform shared by Colosseum and XD Fairy builds.

The seven new machine indices follow, and never replace, the eight HMs. This
stage only writes species compatibility. The additional-TM installer applies
the returned complete move/description plan once final runtime data is ready.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
import hashlib
import struct

from .engine.analyze_game import FormatError, parse_rel, u32
from .engine.inspect_tables import rel_symbols
from .engine.tm_rules import ORIGINAL_TM_MOVES, UNSAFE_OFFENSE
from .fairy_data import compatibility
from .fairy_gameplay import current_context
from .fairy_messages import ITEM_DESCRIPTION_IDS_BY_MOVE
from .fairy_tms import ITEM_IDS, plan_tms, permute_compatibility, _sample

VERSION = "fairy-57-tm-gameplay-v1"
_SHOP_SHA256 = {
    "GC6P01": "524ad778c3618d0c675e69f6a6bd6fab2e4e929d5a2e6981c1a8c25a555f9f20",
    "GC6E01": "b1da5e636775cbcfd42979693f780d868fe03c2046f913ffab3b304864078d8a",
    "GC6J01": "23d388add709ff9975697105b1e471f228d1491b1ea8b6e7f36d84952bb51f4b",
    "GXXP01": "551a28eff2ca2e748015889d32dff8924eba677a49259e6e32f629a533e29251",
    "GXXE01": "b94a6473d7083c923f7febd51498f6b50bda0b23b692c2df8f70123b39f7a115",
    "GXXJ01": "27ec1be3f77360b387940a063cc1188092da9ee1861e943355a58b371eae80f9",
}


def add_tm_shop_stock(original: bytes, current: bytes, game_id: str):
    """Keep TM51..57 available in Phenac or every Gateon progression stage.

    Apply after optional evolution stones and shop randomization. Every prior
    item is retained; only existing stock slots and descriptor starts change.
    Shared zero-terminated suffixes fit the native allocation without REL or
    save growth. This does not change any currency, dialogue or story flag.
    """
    from .engine.shop_stones import read_shops, pack_shop_lists
    from .xd_shops import shop_layout
    if (game_id not in _SHOP_SHA256 or type(original) is not bytes
            or hashlib.sha256(original).hexdigest() != _SHOP_SHA256[game_id]
            or type(current) is not bytes or len(current) != len(original)):
        raise FormatError("Additional TM stock requires the matching original shop REL")
    xd = game_id.startswith("GXX")
    if xd:
        layout = shop_layout(original, game_id)
    else:
        symbols = rel_symbols(original, parse_rel(original))
        if len(symbols) != 8:
            raise FormatError("Unexpected Colosseum shop REL")
        layout = {"item_offset": symbols[2]["offset"], "item_count": u32(original, symbols[3]["offset"]),
                  "shop_offset": symbols[4]["offset"], "shop_count": u32(original, symbols[5]["offset"])}
        if layout != {"item_offset": 0x2AC, "item_count": 122, "shop_offset": 0x3A0, "shop_count": 14}:
            raise FormatError("Unexpected Colosseum shop allocation")
    before = read_shops(current, layout)
    native = read_shops(original, layout)
    targets = (6, 14, 15) if xd else (3,)
    if (any((row["type"], row["subtype"]) != (other["type"], other["subtype"])
            for row, other in zip(before, native, strict=True))
            or any((before[i]["type"], before[i]["subtype"]) != (0, 0) for i in targets)):
        raise FormatError("Additional TM destination is no longer the qualified cash shop")
    stocks = [row["items"].copy() for row in before]
    if xd:
        shared = []
        for index in targets:
            # Extra IDs can already occur in randomized stock. Put them once
            # in the common tail; retain every other item and its multiplicity.
            previous = [item for item in stocks[index] if item not in ITEM_IDS]
            if Counter(shared) - Counter(previous):
                raise FormatError("Gateon progression inventories are no longer nested")
            additional, prefix = Counter(previous) - Counter(shared), []
            for item in previous:
                if additional[item]:
                    prefix.append(item)
                    additional[item] -= 1
            shared = prefix + shared
            stocks[index] = shared + list(ITEM_IDS)
    else:
        stocks[3].extend(item for item in ITEM_IDS if item not in stocks[3])
    packed, starts, used = pack_shop_lists(stocks, layout["item_count"])
    output = bytearray(current)
    struct.pack_into(f">{len(packed)}H", output, layout["item_offset"], *packed)
    allowed = set(range(layout["item_offset"], layout["item_offset"] + 2 * layout["item_count"]))
    for index, start in enumerate(starts):
        position = layout["shop_offset"] + 4 * index + 2
        struct.pack_into(">H", output, position, start)
        allowed.update((position, position + 1))
    after = read_shops(output, layout)
    for i, (old, new) in enumerate(zip(before, after, strict=True)):
        if (new["type"], new["subtype"]) != (old["type"], old["subtype"]):
            raise AssertionError("Additional TMs changed a shop currency or dialogue")
        expected = Counter(old["items"])
        if i in targets:
            for item in ITEM_IDS: expected[item] = max(1, expected[item])
        if Counter(new["items"]) != expected or i not in targets and new["items"] != old["items"]:
            raise FormatError("Additional TMs changed or removed existing shop stock")
    result = bytes(output)
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(current, result, strict=True))):
        raise AssertionError("Additional TM acquisition patch escaped its shop fields")
    return result, {"version": VERSION, "enabled": True, "item_ids": list(ITEM_IDS),
        "tm_numbers": list(range(51, 58)), "shop_indices": list(targets),
        "location": "gateon-port" if xd else "phenac-city", "packed_entries": used,
        "native_capacity": layout["item_count"], "original_stock_preserved": True,
        "shop_currency_dialogue_and_story_flags_unchanged": True,
        "only_stock_and_start_fields_changed": True, "rel_size_unchanged": True}


def _moves(current_rel, content):
    xd = content.family == "xd"
    symbols = rel_symbols(content.original_rel, parse_rel(content.original_rel))
    start = symbols[124 if xd else 62]["offset"]
    count = u32(content.original_rel, symbols[125 if xd else 63]["offset"])
    if count != (375 if xd else 358) or start + count * 56 > len(current_rel):
        raise FormatError("Unexpected native Fairy TM move allocation")
    result = {}
    for index in range(1, 355):
        pos = start + index * 56
        if not current_rel[pos + 1] or not u32(current_rel, pos + 32):
            raise FormatError("Native Fairy TM pool contains an invalid move")
        result[index] = {"index": index, "type": current_rel[pos + 2],
                         "power": current_rel[pos + (25 if xd else 23)]}
    return content.project_moves(result, current_rel)


def _species(original_rel, current_rel, table, family):
    if not isinstance(table, Mapping):
        raise FormatError("Missing Fairy TM species layout")
    try:
        start, count, stride = (table[key] for key in ("offset", "count", "stride"))
    except KeyError as error:
        raise FormatError("Missing Fairy TM species layout") from error
    expected_stride, expected_count = (0x124, 415) if family == "xd" else (0x11C, 413)
    if (any(type(value) is not int for value in (start, count, stride)) or start < 0
            or stride != expected_stride or count != expected_count
            or start + count * stride > len(original_rel)):
        raise FormatError("Unexpected native Fairy TM species allocation")
    dex = 14 if family == "xd" else 16
    rows, seen = {}, set()
    for index in range(count):
        position = start + index * stride
        national = struct.unpack_from(">H", original_rel, position + dex)[0]
        if struct.unpack_from(">H", current_rel, position + dex)[0] != national:
            raise FormatError("A Fairy TM species identity changed")
        if not 1 <= national <= 386:
            continue
        if national in seen:
            raise FormatError("Duplicate national species in Fairy TM compatibility")
        seen.add(national)
        original = original_rel[position + 52:position + 110]
        if (len(original) != 58 or any(value not in (0, 1) for value in original)
                or current_rel[position + 52:position + 110] != original):
            raise FormatError("Fairy TMs must be applied once, before native compatibility changes")
        types = tuple(current_rel[position + 48:position + 50])
        if any(value > 19 for value in types):
            raise FormatError("Unknown final species type for Fairy TM compatibility")
        rows[index] = {"national_dex": national, "offset": position,
                       "types": types, "native": original[:50]}
    if seen != set(range(1, 387)):
        raise FormatError("Fairy TM compatibility must cover all 386 species")
    return rows


def apply_tm_gameplay(original_rel: bytes, current_rel: bytes, original_dol: bytes,
        current_dol: bytes, seed: str, options, game_id: str, *,
        species_table, preserve_species=(), selected_species=None):
    """Return REL, unchanged DOL and an explicit final 57-TM installation plan.

    Original-mode, retained and unselected species keep learnability attached
    to each move after shuffling. New authored TMs accept any BDSP learning
    method, an explicit policy rather than a claim that all seven were TMs.
    """
    content = current_context(game_id)
    if (content is None or content.game_id != game_id
            or content.original_rel != original_rel or content.original_dol != original_dol):
        raise FormatError("Fairy TM gameplay requires its matching active original content")
    if (type(current_rel) is not bytes or type(current_dol) is not bytes
            or len(current_rel) != len(original_rel) or len(current_dol) < len(original_dol)):
        raise FormatError("Fairy TM gameplay source lengths differ")
    shuffle, ensure = options.randomize_tm_moves, options.tm_ensure_offensive
    mode = options.tm_compatibility_mode
    if type(shuffle) is not bool or type(ensure) is not bool or mode not in ("original", "type", "universal", "random"):
        raise ValueError("Invalid Fairy TM compatibility options")
    plan = plan_tms(seed, extra_description_ids=ITEM_DESCRIPTION_IDS_BY_MOVE, shuffle=shuffle)
    rows = _species(original_rel, current_rel, species_table, content.family)
    rows = content.project_species(rows, current_rel)
    moves = _moves(current_rel, content)
    final = [row["after_move"] for row in plan["mapping"]]
    if any(index not in moves for index in final):
        raise FormatError("The 57-TM plan refers to an unavailable native move")
    offensive = [i for i, move in enumerate(final) if move not in UNSAFE_OFFENSE
                 and (moves[move]["power"] > 1 or move in (69, 101))]
    if mode != "original" and ensure and not offensive:
        raise FormatError("The 57-TM plan has no ordinary damaging move")
    preserved = set(preserve_species)
    selected = None if selected_species is None else set(selected_species)
    if (any(type(index) is not int for index in preserved) or not preserved <= rows.keys()
            or selected is not None and (any(type(index) is not int for index in selected) or not selected <= rows.keys())):
        raise ValueError("Unknown species selection in Fairy TM compatibility")
    output, extra, reports, additions, unmet, ranges = bytearray(current_rel), {}, [], [], [], []
    for index, row in sorted(rows.items()):
        national = row["national_dex"]
        natural = permute_compatibility(row["native"], compatibility(national, method="learnable"), plan)
        retained = index in preserved or selected is not None and index not in selected
        if retained or mode == "original":
            enabled = list(natural)
        elif mode == "universal":
            enabled = [1] * 57
        elif mode == "type":
            enabled = [int(moves[move]["type"] in row["types"]) for move in final]
        else:
            enabled = [_sample(seed, f"compatibility:{index}:{i + 1}", 2) for i in range(57)]
        if not retained and mode != "original" and ensure and not any(enabled[i] for i in offensive):
            matching = [i for i in offensive if moves[final[i]]["type"] in row["types"]]
            pool = matching or offensive
            chosen = pool[_sample(seed, f"offensive:{index}", len(pool))]
            enabled[chosen] = 1
            additions.append({"species": index, "national_dex": national,
                              "tm": chosen + 1, "move": final[chosen], "matches_type": bool(matching)})
        if not any(enabled[i] for i in offensive):
            unmet.append(index)
        position = row["offset"] + 52
        before, after = current_rel[position:position + 50], bytes(enabled[:50])
        output[position:position + 50] = after
        extra[national] = tuple(enabled[50:])
        ranges.append((position, position + 50))
        reports.append({"species": index, "national_dex": national, "types": list(row["types"]),
                        "retained": retained, "enabled_before": sum(row["native"]),
                        "enabled_after": sum(enabled),
                        "changed_native_entries": sum(a != b for a, b in zip(before, after))})
    result = bytes(output)
    permitted = {position for lo, hi in ranges for position in range(lo, hi)}
    changed = {i for i, (a, b) in enumerate(zip(current_rel, result, strict=True)) if a != b}
    if changed - permitted:
        raise AssertionError("Fairy TM compatibility escaped its native 50-byte columns")
    return result, current_dol, {
        "version": VERSION, "tm_count": 57, "randomize_tm_moves": shuffle,
        "tm_compatibility_mode": mode, "compatibility_mode": mode,
        "move_pool": "permutation-of-50-native-and-7-added-tms",
        "tm_plan": plan, "mapping": plan["mapping"], "tm_moves": final,
        "extra_compatibility": extra, "new_tm_learning_policy": "bdsp-any-learning-method",
        "tms_moved": sum(i != source for i, source in enumerate(plan["source_order"])),
        "species_compatibility_changed": sum(bool(row["changed_native_entries"]) for row in reports),
        "compatibility": reports,
        "offensive_guarantee": {"requested": ensure, "applied": ensure and mode != "original",
            "added": additions, "species_without_offensive_tm": unmet},
        "hms": {"count": 8, "move_entries_unchanged": True,
            "item_descriptions_unchanged": True, "species_compatibility_unchanged": True},
        "native_compatibility_changed_bytes": len(changed),
        "only_first_50_species_compatibility_bytes_changed": True,
        "dol_moves_and_item_descriptions_deferred_to_installer": True,
    }
