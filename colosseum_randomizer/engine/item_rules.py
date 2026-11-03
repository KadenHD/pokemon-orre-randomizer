"""Seeded PAL treasure items and six verified cash shop inventories.

Item IDs in scripts have a different namespace from the DOL item table. Only
known, priced, ordinary items are candidates. Flags, quantities, room IDs,
positions, special currencies and evolution stones are never rewritten.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import struct

from .analyze_game import FormatError, parse_fsys, sha256, u32
from .inspect_tables import REL_SHA256, u16
from .randomize_trainers import layout
from .rel_regions import region_for_rel, region_for_shop_rel
from .dol_regions import dol_layout
from .randomize_story import DOL_SHA256
from .rebuild_iso import decoded_member, repack_fsys
from .shop_stones import (REL_SHA256 as SHOP_SHA256, STONE_IDS, pack_shop_lists,
                          patch_rel as stone_patch, read_shops)

VERSION = "items-sha256-v1"
ITEM_TABLE = 0x3ADDA0
ITEM_COUNT = 397
ITEM_STRIDE = 0x28
CASH_SHOPS = (3, 4, 5, 6, 7, 9)
SHOP_LAYOUT = {"item_offset": 0x2AC, "item_count": 122,
               "shop_offset": 0x3A0, "shop_count": 14}


def script_to_item(index: int) -> int:
    return index - 151 if ITEM_COUNT < index < 0x250 else index


def item_to_script(index: int) -> int:
    return index + 151 if index >= 0x15E else index


@lru_cache(maxsize=3)
def item_catalog(original_dol: bytes) -> dict[int, dict]:
    region = dol_layout(original_dol)
    result = {}
    for index in range(1, ITEM_COUNT):
        pos = region.item_table_offset + index * ITEM_STRIDE
        bag, effect, held = original_dol[pos], original_dol[pos + 4], original_dol[pos + 0xB]
        price, name, description = u16(original_dol, pos + 6), u32(original_dol, pos + 0x10), u32(original_dol, pos + 0x14)
        category = ({1: "balls", 3: "berries", 4: "tms", 6: "scents"}.get(bag)
                    or ("healing" if effect else "held" if held else "utility"))
        safe = (bag in (1, 2, 3, 4) and price > 0 and name > 0 and description > 0
                and index not in STONE_IDS and not 339 <= index <= 346)
        raw = item_to_script(index)
        result[raw] = {"index": index, "script_index": raw, "bag": bag,
                       "price": price, "name_id": name, "category": category, "safe": safe}
    return result


def _protected(raw: int, catalog: dict, options, *, shop: bool = False) -> bool:
    row = catalog.get(raw)
    return (not row or not row["safe"] or options.keep_capture_items and row["category"] == "balls"
            or shop and options.shop_keep_healing and row["category"] == "healing")


def _candidates(raw: int, catalog: dict, options) -> list[int]:
    old = catalog[raw]
    return [index for index, row in catalog.items() if row["safe"] and row["category"] == old["category"]
            and (not options.items_similar_value or old["price"] / 2 <= row["price"] <= old["price"] * 2)]


def _order(seed: str, key: str, choices) -> list[int]:
    return sorted(choices, key=lambda value: (hashlib.sha256(
        (VERSION + "\0" + seed + "\0" + key + ":" + str(value)).encode("utf-8")).digest(), value))


def item_mapping(seed: str, sources, catalog: dict, options, reserved=()) -> dict[int, int]:
    """Stable bipartite matching: keep stocks duplicate-free without greedy traps.

    Every source retains its own item as a last resort, so a constrained price
    band can always be matched without relaxing a filter or duplicating stock.
    """
    sources, reserved = sorted(set(sources)), set(reserved)
    pools = {old: _order(seed, f"shop:{old}", set(_candidates(old, catalog, options)) - reserved - {old})
             + ([old] if old not in reserved else []) for old in sources}
    owners = {}

    def match(old: int, visited: set[int]) -> bool:
        for new in pools[old]:
            if new in visited:
                continue
            visited.add(new)
            if new not in owners or match(owners[new], visited):
                owners[new] = old
                return True
        return False

    for old in sorted(sources, key=lambda value: (len(pools[value]), value)):
        if not match(old, set()):
            raise FormatError("no safe duplicate-free shop item assignment")
    return {old: new for new, old in owners.items()}


def apply_field_items(original: bytes, current: bytes, original_dol: bytes,
                      seed: str, options) -> tuple[bytes, dict]:
    report = {"version": VERSION, "enabled": options.randomize_field_items, "edits": [], "protected_records": []}
    if not options.randomize_field_items:
        return current, report
    region = region_for_rel(original)
    if dol_layout(original_dol).game_id != region.game_id:
        raise FormatError("treasure REL and item DOL regions differ")
    if len(current) != len(original):
        raise FormatError("treasure rules require the original regional REL layout")
    _, symbols = layout(original)
    start, count, stride = symbols[60]["offset"], u32(original, symbols[61]["offset"]), 0x1C
    if (start, count, start + count * stride) != (region.treasure_offset, 74, symbols[62]["offset"]):
        raise FormatError("unexpected validated regional treasure table")
    catalog, output, allowed = item_catalog(original_dol), bytearray(current), set()
    for index in range(count):
        pos = start + index * stride + 0xE
        old = u16(original, pos)
        if _protected(old, catalog, options):
            report["protected_records"].append(index)
            continue
        pool = set(_candidates(old, catalog, options)) - {old}
        new = _order(seed, f"treasure:{index}", pool)[0] if pool else old
        struct.pack_into(">H", output, pos, new)
        allowed.update((pos, pos + 1))
        report["edits"].append({"index": index, "offset": pos, "before": old, "after": new,
                                "quantity_preserved": original[start + index * stride + 1]})
    if any(a != b and index not in allowed for index, (a, b) in enumerate(zip(current, output, strict=True))):
        raise FormatError("treasure rules exceeded their item-ID whitelist")
    report.update(changed_records=sum(row["before"] != row["after"] for row in report["edits"]),
                  flags_quantities_coordinates_preserved=True, only_item_ids_changed=True)
    return bytes(output), report


def patch_cash_shops(current: bytes, original_dol: bytes, seed: str, options) -> tuple[bytes, dict]:
    before = read_shops(current, SHOP_LAYOUT)
    if any((before[index]["type"], before[index]["subtype"]) != (0, 0) for index in CASH_SHOPS):
        raise FormatError("cash shop descriptors differ from the verified PAL table")
    catalog = item_catalog(original_dol)
    stocks = [row["items"].copy() for row in before]
    selected = {raw for index in CASH_SHOPS for raw in stocks[index]}
    protected = {raw for raw in selected if _protected(raw, catalog, options, shop=True)}
    mapping = item_mapping(seed, selected - protected, catalog, options, protected)
    for index in CASH_SHOPS:
        stocks[index] = [mapping.get(raw, raw) for raw in stocks[index]]
        if len(stocks[index]) != len(set(stocks[index])):
            raise FormatError("shop rules introduced duplicate stock")
    packed, starts, used = pack_shop_lists(stocks, SHOP_LAYOUT["item_count"])
    output = bytearray(current)
    struct.pack_into(f">{len(packed)}H", output, SHOP_LAYOUT["item_offset"], *packed)
    allowed = set(range(SHOP_LAYOUT["item_offset"], SHOP_LAYOUT["item_offset"] + len(packed) * 2))
    for index, start in enumerate(starts):
        pos = SHOP_LAYOUT["shop_offset"] + index * 4 + 2
        struct.pack_into(">H", output, pos, start)
        allowed.update((pos, pos + 1))
    after = read_shops(output, SHOP_LAYOUT)
    for old, new in zip(before, after, strict=True):
        if (old["type"], old["subtype"]) != (new["type"], new["subtype"]):
            raise FormatError("shop dialogue or currency type changed")
        if old["index"] not in CASH_SHOPS and old["items"] != new["items"]:
            raise FormatError("a protected shop inventory changed")
    if any(a != b and index not in allowed for index, (a, b) in enumerate(zip(current, output, strict=True))):
        raise FormatError("shop rules exceeded stock/start-index whitelist")
    return bytes(output), {"version": VERSION, "selected_cash_shops": list(CASH_SHOPS),
                           "mapping": [{"before": old, "after": mapping[old]} for old in sorted(mapping)],
                           "protected_items": sorted(protected), "packed_entries": used,
                           "before": before, "after": after, "protected_shops_unchanged": True,
                           "only_stock_and_starts_changed": True}


def patch_item_archive(source: bytes, original_dol: bytes, seed: str, options) -> tuple[bytes, dict]:
    members = parse_fsys(source)["members"]
    if not members or members[0]["name"] != "pocket_menu":
        raise FormatError("missing native pocket_menu shop REL")
    original = decoded_member(source, members[0])
    shop_region = region_for_shop_rel(original)
    if dol_layout(original_dol).game_id != shop_region.game_id:
        raise FormatError("shop REL and item DOL regions differ")
    current, stone_report = stone_patch(original, options.stone_shops) if options.stone_shops else (original, None)
    current, shop_report = patch_cash_shops(current, original_dol, seed, options) if options.randomize_shop_items else (current, None)
    if current == original:
        return source, {"stones": stone_report, "randomized_stock": shop_report}
    rebuilt, checks = repack_fsys(source, {0: current})
    if any(not row["decoded_byte_identical"] for row in checks[1:]):
        raise FormatError("shop rules changed another archive member")
    return rebuilt, {"stones": stone_report, "randomized_stock": shop_report,
                     "other_archive_members_identical": True}
