"""Shop-only Ball retention must not restrict treasure randomization."""
from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine import item_rules
from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.shop_stones import pack_shop_lists, read_shops
from orre_randomizer.options import Options
from orre_randomizer.xd import XDOptions
from orre_randomizer import xd_item_rules


BALLS = tuple(range(2, 13))
STOCK = (*BALLS, 13, 301)
XD_LAYOUT = {"item_offset": 0x300, "item_count": 184, "shop_offset": 0x1C8, "shop_count": 21}


def shop_data(layout, cash_shops):
    stocks = [list(STOCK) if index in cash_shops else [511] for index in range(layout["shop_count"])]
    packed, starts, _ = pack_shop_lists(stocks, layout["item_count"])
    output = bytearray(max(layout["item_offset"] + len(packed) * 2,
                           layout["shop_offset"] + len(starts) * 4))
    struct.pack_into(f">{len(packed)}H", output, layout["item_offset"], *packed)
    for index, start in enumerate(starts):
        kind = (2 if index < 3 else 0) if layout == item_rules.SHOP_LAYOUT else 0
        struct.pack_into(">BBH", output, layout["shop_offset"] + index * 4,
                         kind if index in cash_shops else 1, 0, start)
    return bytes(output)


class ShopCapturePolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {item: {"safe": True, "category": category, "price": 100 * item}
                        for item, category in ((*((item, "balls") for item in BALLS),
                                               (13, "healing"), (14, "healing"),
                                               (301, "tms"), (312, "tms")))}
        self.xd_items = 0x1000
        self.common = bytearray(self.xd_items + xd_item_rules.ITEM_COUNT * xd_item_rules.ITEM_SIZE)
        for item, row in self.catalog.items():
            pos = self.xd_items + item * xd_item_rules.ITEM_SIZE
            self.common[pos] = {"balls": 1, "healing": 2, "tms": 4}[row["category"]]
            self.common[pos + 4] = int(row["category"] == "healing")
            struct.pack_into(">H", self.common, pos + 6, row["price"])
            struct.pack_into(">2I", self.common, pos + 0x10, item + 5000, item + 6000)

    def test_every_shop_ball_is_kept_and_opt_out_randomizes_it_in_both_games(self):
        for is_xd in (False, True):
            layout = XD_LAYOUT if is_xd else item_rules.SHOP_LAYOUT
            cash_shops = xd_item_rules.CASH_SHOPS if is_xd else item_rules.CASH_SHOPS
            original = shop_data(layout, cash_shops)
            defaults = XDOptions.recommended() if is_xd else Options.recommended()
            defaults = replace(defaults, shop_keep_healing=False)

            def apply(seed, options):
                if is_xd:
                    with (patch("orre_randomizer.xd_item_rules._table_offsets", return_value=(0x100, self.xd_items)),
                          patch("orre_randomizer.xd_item_rules.shop_layout", return_value=layout)):
                        return xd_item_rules.apply_shop_items(self.common, original, "GXXE01", seed, options)[0]
                with patch("orre_randomizer.engine.item_rules.item_catalog", return_value=self.catalog):
                    return item_rules.patch_cash_shops(original, b"", seed, options)[0]

            for seed in ("shop-a", "shop-b", "shop-c", "shop-étoile"):
                for keep_global, keep_shop in ((False, True), (True, False), (False, False)):
                    options = replace(defaults, keep_capture_items=keep_global, shop_keep_capture_items=keep_shop)
                    result = apply(seed, options)
                    self.assertEqual(apply(seed, options), result)
                    for mart in read_shops(result, layout):
                        with self.subTest(xd=is_xd, seed=seed, global_guard=keep_global, shop_guard=keep_shop, mart=mart["index"]):
                            if mart["index"] not in cash_shops:
                                self.assertEqual(mart["items"], [511])
                                continue
                            self.assertEqual(len(mart["items"]), len(set(mart["items"])))
                            if keep_global or keep_shop:
                                self.assertEqual(mart["items"][:len(BALLS)], list(BALLS))
                            else:
                                self.assertNotEqual(mart["items"][:len(BALLS)], list(BALLS))
                            self.assertNotEqual(mart["items"][-2:], list(STOCK[-2:]))

    def test_xd_shop_guard_does_not_keep_a_ball_in_a_treasure(self):
        treasure = 0x100
        self.common[treasure + 1] = 1
        struct.pack_into(">I", self.common, treasure + 0xC, BALLS[0])
        options = XDOptions.recommended()
        self.assertTrue(options.shop_keep_capture_items)
        self.assertFalse(options.keep_capture_items)
        with patch("orre_randomizer.xd_item_rules._table_offsets", return_value=(treasure, self.xd_items)):
            for seed in ("shop-a", "shop-b", "shop-c"):
                result, _ = xd_item_rules.apply_field_items(self.common, self.common, seed, options)
                self.assertNotEqual(u32(result, treasure + 0xC), BALLS[0])

    def test_colosseum_type_two_shop_lists_keep_their_native_currency_and_dialogue(self):
        self.assertEqual(item_rules.CASH_SHOPS, (0, 1, 2, 3, 4, 5, 6, 7, 9))
        original = shop_data(item_rules.SHOP_LAYOUT, item_rules.CASH_SHOPS)
        for index in (0, 1, 2):
            for field, invalid in ((0, 0), (1, 2)):
                broken = bytearray(original)
                broken[item_rules.SHOP_LAYOUT["shop_offset"] + index * 4 + field] = invalid
                with self.subTest(shop=index, field=field), self.assertRaises(FormatError):
                    item_rules.patch_cash_shops(broken, b"", "currency", Options.recommended())


if __name__ == "__main__":
    unittest.main()
