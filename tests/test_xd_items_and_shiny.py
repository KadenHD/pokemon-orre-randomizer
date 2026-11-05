"""XD treasure safeguards and the starter/reward shiny preview contract."""

import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import u32
from orre_randomizer.engine.shop_stones import pack_shop_lists, read_shops
from orre_randomizer.xd_item_rules import (
    CASH_SHOPS, ITEM_COUNT, ITEM_SIZE, TREASURE_SIZE, apply_field_items, apply_shop_items,
)
from orre_randomizer.xd_shiny_rules import GIFT_KEYS, encounter_shiny


class XDItemRulesTests(unittest.TestCase):
    def setUp(self):
        self.treasure, self.items = 0x100, 0x1000
        self.rel = bytearray(self.items + ITEM_COUNT * ITEM_SIZE)
        for item, bag, effect, price in ((1, 1, 0, 0), (2, 1, 0, 1200), (3, 1, 0, 600),
                                         (13, 2, 1, 300), (14, 2, 2, 300), (93, 2, 48, 2100),
                                         (301, 4, 0, 3000), (312, 4, 0, 3000), (361, 2, 0, 300)):
            pos = self.items + item * ITEM_SIZE
            self.rel[pos], self.rel[pos + 4] = bag, effect
            struct.pack_into(">H", self.rel, pos + 6, price)
            struct.pack_into(">2I", self.rel, pos + 0x10, item + 5000, item + 6000)
        self.options = SimpleNamespace(randomize_field_items=True, randomize_shop_items=True,
                                       items_similar_value=True, keep_capture_items=True, shop_keep_healing=True)

    def test_treasures_change_only_item_ids_and_keep_progression(self):
        original = (1, 2, 13, 93, 508, 511, 538)
        for index, item in enumerate(original):
            pos = self.treasure + index * TREASURE_SIZE
            struct.pack_into(">BB5HI3I", self.rel, pos, 0x24, 3, 4, 5, 6, 7, 0, item, 9, 10, 11)
        with patch("orre_randomizer.xd_item_rules._table_offsets", return_value=(self.treasure, self.items)):
            result, report = apply_field_items(self.rel, self.rel, "seed", self.options)
            self.options.keep_capture_items = False
            unrestricted, _ = apply_field_items(self.rel, self.rel, "seed", self.options)
        healing = self.treasure + 2 * TREASURE_SIZE + 0xC
        expected = self.rel.copy()
        struct.pack_into(">I", expected, healing, 14)
        self.assertEqual(result, expected)
        self.assertEqual(report["changed_records"], 1)
        self.assertEqual(u32(unrestricted, self.treasure + TREASURE_SIZE + 0xC), 3)
        self.assertEqual(u32(unrestricted, self.treasure + 0xC), 1)

    def test_cash_items_preserve_stones_special_stock_and_shared_suffixes(self):
        layout = {"item_offset": 0x300, "item_count": 184, "shop_offset": 0x1C8, "shop_count": 21}
        stocks = [[2, 13, 301, 93, 511] if index in CASH_SHOPS else [301, 538] for index in range(21)]
        array, starts, _ = pack_shop_lists(stocks, layout["item_count"])
        shop = bytearray(0x300 + 2 * len(array))
        struct.pack_into(f">{len(array)}H", shop, 0x300, *array)
        for index, start in enumerate(starts):
            struct.pack_into(">BBH", shop, 0x1C8 + 4 * index, 0 if index in CASH_SHOPS else 1, 0, start)
        with (patch("orre_randomizer.xd_item_rules._table_offsets", return_value=(self.treasure, self.items)),
              patch("orre_randomizer.xd_item_rules.shop_layout", return_value=layout)):
            result, report = apply_shop_items(self.rel, shop, "GXXE01", "seed", self.options)
        self.assertEqual(report["changed_records"], len(CASH_SHOPS))
        self.assertEqual(result[:0x300], shop[:0x300])
        self.assertEqual([row["items"] for row in read_shops(result, layout)], [
            [2, 13, 312, 93, 511] if index in CASH_SHOPS else stocks[index] for index in range(21)
        ])


class XDShinyRulesTests(unittest.TestCase):
    def test_preview_is_deterministic_and_scoped_to_ordinary_rewards(self):
        keys = ("starter", *GIFT_KEYS)
        options = SimpleNamespace(custom_shinies=True, shiny_chance_percent=0)
        self.assertEqual([encounter_shiny("seed", options, key) for key in keys], [False] * len(keys))
        options.shiny_chance_percent = 100
        self.assertEqual([encounter_shiny("seed", options, key) for key in keys], [True] * len(keys))
        self.assertIsNone(encounter_shiny("seed", options, "shadow-togepi"))
        options.shiny_chance_percent = 50
        roll = [encounter_shiny("shiny-test", options, key) for key in keys]
        self.assertEqual(roll, [False, True, True, False, True, True, False, False])
        options.custom_shinies = False
        self.assertIsNone(encounter_shiny("seed", options, "starter"))
