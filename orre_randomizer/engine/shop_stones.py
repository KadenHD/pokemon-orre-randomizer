"""Make the six evolution stones buyable in PAL Colosseum's early cash shops.

The original shop REL is shared by all five language archives. Reorder the
first three inventories to share suffixes, then repack all lists in the existing
122-item allocation. Original stock and REL layout are preserved; only the item
array and the descriptors' start indices change. No input file is written.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import struct

from .analyze_game import FormatError, check_range, parse_fsys, parse_rel, sha256, u32
from .inspect_tables import rel_symbols, u16
from .rebuild_iso import decoded_member, repack_fsys
from .rel_regions import region_for_rel, region_for_shop_rel


SOURCE = "https://github.com/PekanMmd/Pokemon-XD-Code/tree/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0"
REL_SHA256 = "524ad778c3618d0c675e69f6a6bd6fab2e4e929d5a2e6981c1a8c25a555f9f20"
STONE_IDS = (93, 94, 95, 96, 97, 98)  # Sun, Moon, Fire, Thunder, Water, Leaf.
STONE_SHOPS = (3, 5)  # Phenac / Pyrite, observed buy menus; type 2 lists 0..2 stay distinct.
ARCHIVE_NAMES = tuple(f"pocket_menu{suffix}.fsys" for suffix in ("", "_fr", "_ge", "_it", "_sp"))
FIRST_STOCKS = (
    (14, 15, 16, 17, 18),
    (14, 15, 16, 17, 18, 3, 4, 23),
    (14, 15, 16, 17, 18, 23, 3, 4, 2, 6, 8, 10),
)


def read_shops(data: bytes, layout: dict) -> list[dict]:
    """Descriptor BBH = dialog type, shop type, item-list index; 0 ends stock."""
    start, count = layout["item_offset"], layout["item_count"]
    shops, number = layout["shop_offset"], layout["shop_count"]
    if count <= 0 or number < 3:
        raise FormatError("shop table must contain at least three inventories")
    check_range(data, start, count * 2, "shop item array")
    check_range(data, shops, number * 4, "shop descriptors")
    if max(start, shops) < min(start + count * 2, shops + number * 4):
        raise FormatError("shop items overlap descriptors")
    items = struct.unpack_from(f">{count}H", data, start)
    result = []
    for index in range(number):
        kind, subtype, first = struct.unpack_from(">BBH", data, shops + 4 * index)
        if first >= count:
            raise FormatError("shop start index exceeds item array")
        end = first
        while end < count and items[end]:
            end += 1
        if end == count:
            raise FormatError("unterminated shop inventory")
        result.append({"index": index, "type": kind, "subtype": subtype,
                       "start_index": first, "items": list(items[first:end])})
    return result


def pack_shop_lists(stocks: list[list[int]], capacity: int) -> tuple[list[int], list[int], int]:
    """Pack complete zero-terminated lists, sharing identical lists and suffixes."""
    if not 1 <= capacity <= 0x10000:
        raise FormatError("invalid shop item-array capacity")
    if any(any(not isinstance(item, int) or not 1 <= item <= 0xFFFF for item in stock)
           for stock in stocks):
        raise FormatError("stock contains an invalid item or a premature terminator")
    packed, starts = [], [0] * len(stocks)
    for index in sorted(range(len(stocks)), key=lambda i: (-len(stocks[i]), i)):
        wanted = stocks[index] + [0]
        found = next((p for p in range(len(packed) - len(wanted) + 1)
                      if packed[p:p + len(wanted)] == wanted), None)
        if found is None:
            found = len(packed)
            packed.extend(wanted)
        starts[index] = found
    used = len(packed)
    if used > capacity:
        raise FormatError("new shop inventories exceed the existing allocation")
    return packed + [0] * (capacity - used), starts, used


def patch_shop_tables(data: bytes, layout: dict, shop_indices: tuple[int, ...] = STONE_SHOPS) -> tuple[bytes, dict]:
    """Core table transform. Production callers validate the original via patch_rel."""
    before = read_shops(data, layout)
    if tuple(tuple(shop["items"]) for shop in before[:3]) != FIRST_STOCKS:
        raise FormatError("first three shops differ from the validated PAL inventories")
    if any((before[index]["type"], before[index]["subtype"]) != (0, 0)
           for index in STONE_SHOPS):
        raise FormatError("stone destinations are not the validated cash buy menus")
    stocks = [shop["items"].copy() for shop in before]
    stocks[2] = [2, 6, 8, 10, 3, 4, 23, 14, 15, 16, 17, 18]
    stocks[1], stocks[0] = stocks[2][4:], stocks[2][7:]
    if not shop_indices or len(set(shop_indices)) != len(shop_indices) or set(shop_indices) - set(STONE_SHOPS):
        raise FormatError("select at least one of the validated cash shops")
    for index in shop_indices:
        stocks[index].extend(STONE_IDS)
    packed, starts, used = pack_shop_lists(stocks, layout["item_count"])
    output = bytearray(data)
    struct.pack_into(f">{len(packed)}H", output, layout["item_offset"], *packed)
    allowed = set(range(layout["item_offset"], layout["item_offset"] + len(packed) * 2))
    for index, first in enumerate(starts):
        pos = layout["shop_offset"] + 4 * index + 2
        struct.pack_into(">H", output, pos, first)
        allowed.update((pos, pos + 1))
    modified = bytes(output)
    after = read_shops(modified, layout)
    for index, (old, new) in enumerate(zip(before, after, strict=True)):
        if (old["type"], old["subtype"]) != (new["type"], new["subtype"]):
            raise FormatError("shop dialog/currency type changed")
        expected = Counter(old["items"]) + (Counter(STONE_IDS) if index in shop_indices else Counter())
        if Counter(new["items"]) != expected:
            raise FormatError("original shop stock was lost or altered")
        if index >= 3 and index not in shop_indices and new["items"] != old["items"]:
            raise FormatError("unselected shop inventory/order changed")
    changed = [i for i, (old, new) in enumerate(zip(data, modified, strict=True)) if old != new]
    if set(changed) - allowed:
        raise FormatError("shop patch changed bytes outside stock/start fields")
    plan = {"source": SOURCE, "source_rel_sha256": sha256(data),
            "patched_rel_sha256": sha256(modified), "rel_size": len(data),
            "layout": layout, "stone_ids": list(STONE_IDS),
            "shops_receiving_stones": list(shop_indices), "before": before, "after": after,
            "packed_item_entries_used": used, "changed_byte_count": len(changed),
            "all_original_stock_preserved": True, "rel_layout_preserved": True}
    return modified, plan


def patch_rel(data: bytes, shop_indices: tuple[int, ...] = STONE_SHOPS) -> tuple[bytes, dict]:
    region_for_shop_rel(data)
    symbols = rel_symbols(data, parse_rel(data))
    if len(symbols) != 8:
        raise FormatError("unexpected pocket_menu REL symbol table")
    layout = {"item_offset": symbols[2]["offset"], "item_count": u32(data, symbols[3]["offset"]),
              "shop_offset": symbols[4]["offset"], "shop_count": u32(data, symbols[5]["offset"])}
    if layout != {"item_offset": 0x2AC, "item_count": 122, "shop_offset": 0x3A0, "shop_count": 14}:
        raise FormatError("unexpected PAL shop table layout")
    return patch_shop_tables(data, layout, shop_indices)


def patch_fsys(source: bytes, shop_indices: tuple[int, ...] = STONE_SHOPS) -> tuple[bytes, dict]:
    members = parse_fsys(source)["members"]
    if not members or members[0]["index"] != 0 or members[0]["name"] != "pocket_menu":
        raise FormatError("archive lacks the expected pocket_menu REL member")
    modified, plan = patch_rel(decoded_member(source, members[0]), shop_indices)
    rebuilt, checks = repack_fsys(source, {0: modified})
    if any(not row["decoded_byte_identical"] for row in checks[1:]):
        raise FormatError("shop archive patch altered another decoded member")
    plan.update({"source_fsys_sha256": sha256(source), "patched_fsys_sha256": sha256(rebuilt),
                 "fsys_member_checks": checks})
    return rebuilt, plan


def patch_shop_archives(game: Path) -> tuple[dict[str, bytes], dict]:
    """Return only the exact region's native archive overrides, no writes."""
    common = (game / "files/common.fsys").read_bytes()
    members = parse_fsys(common)["members"]
    if not members or members[0]["name"] != "common_rel":
        raise FormatError("missing original common REL for regional shop selection")
    region = region_for_rel(decoded_member(common, members[0]))
    overrides, plans = {}, []
    for name in region.shop_archives:
        payload, plan = patch_fsys((game / "files" / name).read_bytes())
        overrides[name] = payload
        plans.append({"path": name, **plan})
    if len({plan["patched_rel_sha256"] for plan in plans}) != 1:
        raise FormatError("language variants produced different shop data")
    return overrides, {"archives": plans, "stone_ids": list(STONE_IDS),
                       "all_language_shop_rels_identical": True}
