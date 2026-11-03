from collections import Counter
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import FormatError, parse_fsys
from rebuild_iso import decoded_member
from shop_stones import (ARCHIVE_NAMES, FIRST_STOCKS, REL_SHA256, STONE_IDS, STONE_SHOPS,
                         pack_shop_lists, patch_rel, patch_shop_tables, read_shops)


class ShopStoneTests(unittest.TestCase):
    def fixture(self):
        stocks = [list(stock) for stock in FIRST_STOCKS] + [
            [13, 22, 14, 15, 16, 17, 18, 23], [73, 74, 75, 76, 77, 78, 79],
            [21, 22, 23, 24, 14, 15, 16, 17, 18],
            [21, 22, 23, 24, 63, 64, 65, 66, 67, 70, 543, 544, 545],
            [19, 20, 21, 23, 24, 298, 302, 303, 304, 305, 308, 313, 321, 326],
            [30, 31, 32, 33], [298, 302, 303, 304, 305, 308, 313, 321, 326],
            [26, 27, 28],
            [301, 312, 317, 323, 320, 169, 170, 171, 172, 200, 185, 196, 180, 183, 179, 187, 198, 186],
        ]
        stocks += [stocks[-1].copy(), stocks[-1].copy()]
        layout = {"item_offset": 32, "item_count": 122, "shop_offset": 276, "shop_count": 14}
        data = bytearray(b"\xA5" * 400)
        items, starts = [], []
        for index, stock in enumerate(stocks):
            if index >= 12:
                starts.append(starts[11])
            else:
                starts.append(len(items))
                items += stock + [0]
        self.assertEqual(len(items), 122)
        struct.pack_into(">122H", data, layout["item_offset"], *items)
        for index, first in enumerate(starts):
            struct.pack_into(">BBH", data, layout["shop_offset"] + index * 4,
                             2 if index < 3 else 0 if index in STONE_SHOPS else index % 4,
                             0 if index < 3 or index in STONE_SHOPS else index % 5, first)
        return bytes(data), layout

    def test_preserves_every_original_item_and_other_fields(self):
        source, layout = self.fixture()
        modified, plan = patch_shop_tables(source, layout)
        self.assertEqual((modified, plan), patch_shop_tables(source, layout))
        self.assertEqual(len(source), len(modified))
        self.assertLessEqual(plan["packed_item_entries_used"], 122)
        old, new = read_shops(source, layout), read_shops(modified, layout)
        for index in range(14):
            self.assertEqual((old[index]["type"], old[index]["subtype"]),
                             (new[index]["type"], new[index]["subtype"]))
            if index in STONE_SHOPS:
                self.assertEqual(Counter(new[index]["items"]),
                                 Counter(old[index]["items"]) + Counter(STONE_IDS))
            elif index < 3:
                self.assertEqual(Counter(old[index]["items"]), Counter(new[index]["items"]))
            else:
                self.assertEqual(old[index]["items"], new[index]["items"])
        # Original header, following data, and both descriptor type bytes survive.
        allowed = set(range(32, 276))
        for index in range(14):
            allowed.update((278 + index * 4, 279 + index * 4))
        self.assertTrue(all(a == b for index, (a, b) in enumerate(zip(source, modified))
                            if index not in allowed))
        self.assertEqual(new[1]["start_index"], new[2]["start_index"] + 4)
        self.assertEqual(new[0]["start_index"], new[2]["start_index"] + 7)

    def test_exact_suffix_and_duplicate_sharing_only(self):
        packed, starts, used = pack_shop_lists([[4, 5], [3, 4, 5], [4, 5], [4]], 10)
        self.assertEqual(used, 6)
        self.assertEqual(starts[0], starts[1] + 1)
        self.assertEqual(starts[0], starts[2])
        self.assertNotEqual(starts[3], starts[0])
        for original, start in zip([[4, 5], [3, 4, 5], [4, 5], [4]], starts):
            self.assertEqual(packed[start:start + len(original) + 1], original + [0])
        with self.assertRaises(FormatError):
            pack_shop_lists([[1, 2], [3, 4]], 5)
        with self.assertRaises(FormatError):
            pack_shop_lists([[1, 0, 2]], 10)

    def test_refuses_wrong_build_stock_and_bad_terminators(self):
        with self.assertRaises(FormatError):
            patch_rel(b"unknown REL")
        source, layout = self.fixture()
        for offset, value in ((layout["item_offset"], 99),
                              (layout["shop_offset"] + 2, 122)):
            data = bytearray(source)
            struct.pack_into(">H", data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(FormatError):
                patch_shop_tables(bytes(data), layout)
        data = bytearray(source)
        for index in range(122):
            struct.pack_into(">H", data, layout["item_offset"] + 2 * index, 1)
        with self.assertRaises(FormatError):
            read_shops(bytes(data), layout)

    def test_local_five_languages_share_the_validated_rel(self):
        game = Path(__file__).resolve().parents[1] / "game/files"
        if not all((game / name).is_file() for name in ARCHIVE_NAMES):
            self.skipTest("original game files are not distributed with the project")
        patched_hashes = set()
        from analyze_game import sha256
        for name in ARCHIVE_NAMES:
            source = (game / name).read_bytes()
            original = decoded_member(source, parse_fsys(source)["members"][0])
            self.assertEqual(sha256(original), REL_SHA256)
            modified, plan = patch_rel(original)
            self.assertEqual(len(modified), len(original))
            self.assertLessEqual(plan["packed_item_entries_used"], 122)
            before, after = read_shops(original, plan["layout"]), read_shops(modified, plan["layout"])
            # Regression: runtime Pyrite stock must gain the stones; sell menus must not.
            self.assertEqual(before[5]["items"], [21,22,23,24,14,15,16,17,18])
            for index in (3, 5):
                self.assertEqual((after[index]["type"], after[index]["subtype"]), (0, 0))
                self.assertEqual(after[index]["items"], before[index]["items"] + list(STONE_IDS))
            for index in range(3):
                self.assertFalse(set(after[index]["items"]) & set(STONE_IDS))
            patched_hashes.add(sha256(modified))
        self.assertEqual(len(patched_hashes), 1)


if __name__ == "__main__":
    unittest.main()
