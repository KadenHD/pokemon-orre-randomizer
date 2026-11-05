"""Seeded ordinary treasure and cash shop items for the three retail XD layouts."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import struct

from .engine.analyze_game import FormatError, check_range, parse_rel, u32
from .engine.inspect_tables import rel_symbols, u16
from .engine.item_rules import item_mapping
from .engine.shop_stones import STONE_IDS, read_shops
from .xd_shops import shop_layout

VERSION = "xd-field-items-sha256-v1"
SHOP_VERSION = "xd-shop-items-sha256-v1"
TREASURE_COUNT, TREASURE_SIZE = 116, 0x1C
ITEM_COUNT, ITEM_SIZE = 444, 0x28
FIRST_SPECIAL_ITEM = 0x15E  # Native XD script IDs add 150 from here on.
CASH_SHOPS = (0, 1, 2, 3, 5, 6, 12, 13, 14, 15, 19)
_LAYOUTS = {
    (0x20D50, 0x21EA4),  # Europe
    (0x1ED90, 0x1FEE4),  # USA
    (0x1DB44, 0x1EC98),  # Japan
}


def _category(data: bytes, position: int) -> str | None:
    bag, effect, held = data[position], data[position + 4], data[position + 0xB]
    if bag in (1, 3, 4):
        return {1: "balls", 3: "berries", 4: "tms"}[bag]
    if bag != 2:
        return None
    if 1 <= effect <= 30:
        return "healing"
    if effect:
        return "utility"
    return "held" if held else None


def _ordinary_items(rel: bytes, start: int) -> dict[int, tuple[str, int]]:
    items = {}
    for item in range(1, FIRST_SPECIAL_ITEM):
        if item in STONE_IDS:
            continue
        pos = start + item * ITEM_SIZE
        price = u16(rel, pos + 6)
        category = _category(rel, pos)
        if category and price and u32(rel, pos + 0x10) and u32(rel, pos + 0x14):
            items[item] = (category, price)
    return items


def _table_offsets(original: bytes) -> tuple[int, int]:
    native = parse_rel(original)
    symbols = rel_symbols(original, native)
    if native["module_id"] != 88 or len(symbols) < 73:
        raise FormatError("unexpected XD common REL for field items")
    treasure, items = (symbols[index]["offset"] for index in (66, 70))
    counts = (u32(original, symbols[67]["offset"]), u32(original, symbols[71]["offset"]))
    if (treasure, items) not in _LAYOUTS or counts != (TREASURE_COUNT, ITEM_COUNT):
        raise FormatError("unexpected XD field item table layout")
    length = TREASURE_COUNT * TREASURE_SIZE
    if (treasure + length != symbols[68]["offset"]
            or items + ITEM_COUNT * ITEM_SIZE != symbols[72]["offset"]):
        raise FormatError("unexpected XD field item table boundaries")
    check_range(original, treasure, length, "XD treasure table")
    check_range(original, items, ITEM_COUNT * ITEM_SIZE, "XD item catalogue")
    return treasure, items


def apply_field_items(original: bytes, current: bytes, seed: str, options) -> tuple[bytes, dict]:
    report = {"version": VERSION, "enabled": options.randomize_field_items, "edits": [],
              "protected_records": [], "unmatched_records": []}
    if not options.randomize_field_items:
        return current, report
    treasure, items = _table_offsets(original)
    if len(current) != len(original):
        raise FormatError("unexpected XD common REL length for field items")
    length = TREASURE_COUNT * TREASURE_SIZE
    if current[treasure:treasure + length] != original[treasure:treasure + length]:
        raise FormatError("XD treasure table has already been changed")

    catalogue = _ordinary_items(original, items)
    categories = defaultdict(list)
    for item, (category, price) in catalogue.items():
        categories[category].append((item, price))
    output = bytearray(current)
    for index in range(TREASURE_COUNT):
        row = treasure + index * TREASURE_SIZE
        position = row + 0xC
        old = u32(original, position)
        entry = catalogue.get(old)
        if not entry or not original[row + 1] or (entry[0] == "balls" and options.keep_capture_items):
            report["protected_records"].append(index)
            continue
        category, price = entry
        candidates = [item for item, value in categories[category] if item != old
                      and (not options.items_similar_value or price <= 2 * value <= 4 * price)]
        if not candidates:
            report["unmatched_records"].append(index)
            continue
        coin = hashlib.sha256(f"{VERSION}\0{seed}\0{index}".encode("utf-8")).digest()
        new = candidates[int.from_bytes(coin[:8], "big") % len(candidates)]
        struct.pack_into(">H", output, position + 2, new)
        report["edits"].append({"index": index, "offset": position + 2, "before": old, "after": new,
                                "quantity_preserved": original[row + 1]})
    report["changed_records"] = len(report["edits"])
    return bytes(output), report


def apply_shop_items(original: bytes, current: bytes, game_id: str, seed: str, options) -> tuple[bytes, dict]:
    report = {"version": SHOP_VERSION, "enabled": options.randomize_shop_items, "edits": []}
    if not options.randomize_shop_items:
        return current, report
    _, item_table = _table_offsets(original)
    layout = shop_layout(current, game_id)
    shops = read_shops(current, layout)
    if tuple(shop["index"] for shop in shops if (shop["type"], shop["subtype"]) == (0, 0)) != CASH_SHOPS:
        raise FormatError("unexpected XD cash shop descriptors")

    items = _ordinary_items(original, item_table)
    catalogue = {item: {"category": category, "price": price, "safe": True}
                 for item, (category, price) in items.items()}
    selected = {item for index in CASH_SHOPS for item in shops[index]["items"]}
    protected = {item for item in selected if item not in items
                 or (options.keep_capture_items and items[item][0] == "balls")
                 or (options.shop_keep_healing and items[item][0] == "healing")}
    mapping = item_mapping(SHOP_VERSION + "\0" + seed, selected - protected, catalogue, options, protected)
    output = bytearray(current)
    for index in CASH_SHOPS:
        shop = shops[index]
        for slot, old in enumerate(shop["items"], shop["start_index"]):
            new = mapping.get(old, old)
            if new != old:
                struct.pack_into(">H", output, layout["item_offset"] + slot * 2, new)
                report["edits"].append({"mart": index, "before": old, "after": new})

    for original_shop, new_shop in zip(shops, read_shops(output, layout), strict=True):
        index = original_shop["index"]
        expected = ([mapping.get(item, item) for item in original_shop["items"]] if index in CASH_SHOPS
                    else original_shop["items"])
        if new_shop["items"] != expected or (index in CASH_SHOPS and len(expected) != len(set(expected))):
            raise FormatError("XD cash item replacement modified a protected shop or duplicated stock")
    report["changed_records"] = len(report["edits"])
    report["mart_ids"] = list(CASH_SHOPS)
    return bytes(output), report
