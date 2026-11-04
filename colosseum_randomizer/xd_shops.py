"""Add the native evolution stones to all three Gateon Port shop inventories."""
from collections import Counter
import struct

from .engine.analyze_game import FormatError, parse_rel, u32
from .engine.inspect_tables import rel_symbols, u16
from .engine.item_text import DONORS, REPLACEMENTS, patch_item_name_banks
from .engine.shop_stones import STONE_IDS, pack_shop_lists, read_shops


GATEON_MARTS = (6, 14, 15)
STONE_PRICE = 2100


def patch_stone_price(rel: bytes, symbols: list[dict]) -> bytes:
    """The retail Moon Stone has no cash price. Use the other stones' price."""
    start = symbols[70]["offset"]
    for index, price in zip(STONE_IDS, (2100, 0, 2100, 2100, 2100, 2100), strict=True):
        row = start + index * 0x28
        if rel[row] != 2 or u16(rel, row + 6) != price or u32(rel, row + 0x10) != 5074 + index - 93:
            raise FormatError("unexpected XD evolution stone item record")
    output = bytearray(rel)
    struct.pack_into(">H", output, start + 94 * 0x28 + 6, STONE_PRICE)
    return bytes(output)


def patch_stone_names(original: bytes, current: bytes, game_id: str) -> tuple[bytes, dict]:
    # XD's western RELs contain the same banks, but the USA game uses US.
    if game_id == "GXXJ01":
        return current, {"changed_names": 0}
    if game_id == "GXXE01":
        indices, languages = (136,), ("US",)
    else:
        indices, languages = (136, 138, 139, 140, 141, 142), ("US", "UK", "GE", "FR", "IT", "SP")
    donors = dict(DONORS, IT=((3377, 3313), (3372, 3315)))
    return patch_item_name_banks(original, current, indices, languages, REPLACEMENTS, donors, reclaim_replaced=True)


def shop_layout(rel: bytes, game_id: str) -> dict:
    native = parse_rel(rel)
    symbols = rel_symbols(rel, native)
    expected_id = 2 if game_id == "GXXJ01" else 250
    if native["module_id"] != expected_id or len(symbols) != 8:
        raise FormatError("unexpected XD shop REL")
    layout = {
        "item_offset": symbols[4]["offset"], "item_count": u32(rel, symbols[5]["offset"]),
        "shop_offset": symbols[0]["offset"], "shop_count": u32(rel, symbols[1]["offset"]),
    }
    if layout != {"item_offset": 0x300, "item_count": 184, "shop_offset": 0x1C8, "shop_count": 21}:
        raise FormatError("unexpected XD shop table layout")
    return layout


def patch_stone_stock(rel: bytes, game_id: str) -> tuple[bytes, dict]:
    layout = shop_layout(rel, game_id)
    original = read_shops(rel, layout)
    stocks = [row["items"] for row in original]
    for index in GATEON_MARTS:
        row = original[index]
        if (row["type"], row["subtype"]) != (0, 0) or set(row["items"]) & set(STONE_IDS):
            raise FormatError("unexpected Gateon Port cash stock")
    # Each later stage contains the full earlier inventory. Share their
    # zero-terminated suffixes to fit all six stones in the existing allocation.
    shared = []
    for index in GATEON_MARTS:
        added = Counter(stocks[index]) - Counter(shared)
        if Counter(shared) - Counter(stocks[index]):
            raise FormatError("Gateon Port stocks are not nested")
        prefix = []
        for item in stocks[index]:
            if added[item]:
                prefix.append(item)
                added[item] -= 1
        shared = prefix + shared
        stocks[index] = shared + list(STONE_IDS)
    packed, starts, used = pack_shop_lists(stocks, layout["item_count"])
    patched = bytearray(rel)
    struct.pack_into(f">{len(packed)}H", patched, layout["item_offset"], *packed)
    for index, start in enumerate(starts):
        struct.pack_into(">H", patched, layout["shop_offset"] + index * 4 + 2, start)
    for old, new in zip(original, read_shops(patched, layout), strict=True):
        index = old["index"]
        if (new["type"], new["subtype"], new["items"]) != (old["type"], old["subtype"], stocks[index]):
            raise FormatError("Gateon Port stock failed round-trip verification")
        expected = Counter(old["items"]) + (Counter(STONE_IDS) if index in GATEON_MARTS else Counter())
        if Counter(new["items"]) != expected:
            raise FormatError("XD shop patch changed original inventory")
    return bytes(patched), {"mart_ids": list(GATEON_MARTS), "item_ids": list(STONE_IDS), "price": STONE_PRICE,
                            "location": "gateon-port", "used_entries": used}
