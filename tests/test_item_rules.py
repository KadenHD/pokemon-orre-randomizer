"""Item assignment properties and optional PAL archive/pipeline integration."""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from colosseum_randomizer.engine import item_rules
from colosseum_randomizer.engine.analyze_game import parse_fsys
from colosseum_randomizer.engine.gameplay_rules import apply_rel_rules
from colosseum_randomizer.engine.inspect_tables import u16
from colosseum_randomizer.engine.randomize_trainers import layout, original_common
from colosseum_randomizer.engine.rebuild_iso import decoded_member
from colosseum_randomizer.engine.shop_stones import ARCHIVE_NAMES, STONE_IDS, patch_rel, read_shops
from colosseum_randomizer.options import Options


def synthetic_catalog():
    return {index: {"safe": True, "price": 100, "category": "held"}
            for index in range(1, 13)}


class ItemMatchingTests(unittest.TestCase):
    def test_augmenting_paths_avoid_greedy_self_fallback(self):
        # Greedy 1->10, 2->12 leaves source3 with its own item. A complete
        # nonidentity assignment exists only after moving source1 to11.
        graph = {1: [10, 11], 2: [10, 12], 3: [10, 12]}
        with patch.object(item_rules, "_candidates", side_effect=lambda old, *_: graph[old]), \
             patch.object(item_rules, "_order", side_effect=lambda seed, key, choices: sorted(choices)):
            result = item_rules.item_mapping("augment", (1, 2, 3), synthetic_catalog(), Options())
        self.assertEqual(set(result), {1, 2, 3})
        self.assertEqual(set(result.values()), {10, 11, 12})

    def test_order_independence_injectivity_and_reserved_targets(self):
        catalog = synthetic_catalog()
        choices = (1, 2, 3, 4, 1, 2)
        first = item_rules.item_mapping("été", choices, catalog, Options(), reserved=(7, 8, 9))
        second = item_rules.item_mapping("été", reversed(choices), dict(reversed(list(catalog.items()))),
                                         Options(), reserved=(9, 8, 7))
        self.assertEqual(first, second)
        self.assertEqual(set(first), {1, 2, 3, 4})
        self.assertEqual(len(set(first.values())), 4)
        self.assertFalse(set(first.values()) & {7, 8, 9})
        variants = {tuple(sorted(item_rules.item_mapping(str(seed), choices, catalog, Options()).items()))
                    for seed in range(6)}
        self.assertGreater(len(variants), 1)

    def test_one_and_two_item_palettes_keep_a_complete_assignment(self):
        catalog = synthetic_catalog()
        one = item_rules.item_mapping("small", [1], {1: catalog[1]}, Options())
        self.assertEqual(one, {1: 1})
        two = item_rules.item_mapping("small", [1, 2], {i: catalog[i] for i in (1, 2)}, Options())
        self.assertEqual(set(two), {1, 2})
        self.assertEqual(set(two.values()), {1, 2})

    def test_category_and_price_constraints_survive_global_matching(self):
        catalog = synthetic_catalog()
        catalog[1].update(price=100, category="healing")
        catalog[2].update(price=50, category="healing")
        catalog[3].update(price=200, category="healing")
        catalog[4].update(price=201, category="healing")
        catalog[5].update(price=49, category="healing")
        for similar in (False, True):
            settings = replace(Options(), items_similar_value=similar)
            mapping = item_rules.item_mapping("constraint", (1, 2, 3, 4, 5, 6), catalog, settings)
            self.assertEqual(len(set(mapping.values())), 6)
            for old, new in mapping.items():
                self.assertEqual(catalog[new]["category"], catalog[old]["category"])
                if similar:
                    self.assertLessEqual(catalog[old]["price"] / 2, catalog[new]["price"])
                    self.assertLessEqual(catalog[new]["price"], catalog[old]["price"] * 2)

    def test_price_guard_can_be_disabled_without_relaxing_category(self):
        catalog = {1: {"safe": True, "price": 100, "category": "held"},
                   2: {"safe": True, "price": 201, "category": "held"},
                   3: {"safe": True, "price": 100, "category": "balls"}}
        constrained = item_rules.item_mapping("price", (1,), catalog, Options())
        unrestricted = item_rules.item_mapping("price", (1,), catalog,
            replace(Options(), items_similar_value=False))
        self.assertEqual(constrained, {1: 1})
        self.assertEqual(unrestricted, {1: 2})


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires user's original local PAL image")
class PalItemRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_common(GAME)[2]
        cls.dol = (GAME / "sys/main.dol").read_bytes()
        cls.catalog = item_rules.item_catalog(cls.dol)
        cls.start = layout(cls.original)[1][60]["offset"]
        cls.archive = (GAME / "files/pocket_menu.fsys").read_bytes()
        cls.shop_rel = decoded_member(cls.archive, parse_fsys(cls.archive)["members"][0])
        cls.seed = "items-pal-review"

    def test_catalog_namespace_and_permanently_protected_items(self):
        for raw in (537, 543, 544, 545):
            native = item_rules.script_to_item(raw)
            self.assertEqual(self.catalog[raw]["index"], native)
            self.assertEqual(item_rules.item_to_script(native), raw)
            self.assertFalse(self.catalog[raw]["safe"])
        # The pinned upstream namespace has an asymmetric alias here: raw500
        # decodes to349, whose canonical encoder emits349. Unknown raw500 must
        # remain protected rather than being treated as a candidate item.
        self.assertEqual(item_rules.script_to_item(500), 349)
        self.assertEqual(self.catalog[349]["bag"], 5)
        self.assertFalse(self.catalog[349]["safe"])
        self.assertNotIn(500, self.catalog)
        self.assertEqual(self.catalog[537]["price"], 0)
        for raw in STONE_IDS:
            self.assertFalse(self.catalog[raw]["safe"])
        for row in self.catalog.values():
            if row["safe"]:
                self.assertGreater(row["price"], 0)
                self.assertNotIn(row["bag"], (5, 6))

    def test_all_74_treasures_preserve_every_nonitem_byte_and_progression_items(self):
        settings = replace(Options(), randomize_field_items=True, keep_capture_items=False)
        result, report = item_rules.apply_field_items(self.original, self.original, self.dol,
                                                      self.seed, settings)
        protected, flutes, jail_key_flags, changed = [], [], [], 0
        for index in range(74):
            pos = self.start + index * 0x1C
            before = self.original[pos:pos + 0x1C]
            after = result[pos:pos + 0x1C]
            self.assertEqual(before[:0xE], after[:0xE])
            self.assertEqual(before[0x10:], after[0x10:])
            old, new = u16(before, 0xE), u16(after, 0xE)
            meta = self.catalog.get(old)
            is_protected = not old or not meta or meta["bag"] in (5, 6) or not meta["price"] or old in STONE_IDS
            if is_protected:
                protected.append(index)
                self.assertEqual(after, before)
            else:
                changed += old != new
                self.assertTrue(self.catalog[new]["safe"])
                self.assertEqual(meta["category"], self.catalog[new]["category"])
                self.assertLessEqual(meta["price"] / 2, self.catalog[new]["price"])
                self.assertLessEqual(self.catalog[new]["price"], meta["price"] * 2)
            if old == 537:
                flutes.append(index)
            if old == 500:
                jail_key_flags.append(u16(before, 6))
        self.assertEqual(len(flutes), 2)
        self.assertEqual(jail_key_flags, [153, 153])
        self.assertGreater(changed, 0)
        self.assertTrue(set(protected) <= set(report["protected_records"]))
        self.assertEqual(result[:self.start], self.original[:self.start])
        self.assertEqual(result[self.start + 74 * 0x1C:], self.original[self.start + 74 * 0x1C:])

    def test_capture_toggle_is_independent_of_key_and_time_flute_protection(self):
        results = []
        for keep in (True, False):
            settings = replace(Options(), randomize_field_items=True, keep_capture_items=keep)
            results.append(item_rules.apply_field_items(self.original, self.original,
                self.dol, self.seed, settings)[0])
        balls = [self.start + index * 0x1C + 0xE for index in range(74)
                 if self.catalog.get(u16(self.original, self.start + index * 0x1C + 0xE), {}).get("category") == "balls"]
        self.assertTrue(balls)
        self.assertTrue(all(u16(results[0], pos) == u16(self.original, pos) for pos in balls))
        self.assertTrue(all(u16(results[1], pos) != u16(self.original, pos) for pos in balls))
        for result in results:
            for index in range(74):
                pos = self.start + index * 0x1C + 0xE
                if u16(self.original, pos) in (0, 500, 537):
                    self.assertEqual(u16(result, pos), u16(self.original, pos))

    def test_composed_rel_preserves_prior_gameplay_changes_and_disabled_identity(self):
        from colosseum_randomizer.service import transform_rel
        settings = replace(Options.recommended(), randomize_types=True)
        base = transform_rel(self.original, self.seed, settings)[0]
        current = apply_rel_rules(self.original, base, self.seed, settings)[0]
        result, _ = item_rules.apply_field_items(self.original, current, self.dol, self.seed, settings)
        allowed = {self.start + index * 0x1C + field for index in range(74) for field in (0xE, 0xF)}
        self.assertTrue(all(index in allowed for index, (a, b) in enumerate(zip(current, result)) if a != b))
        repeated, _ = item_rules.apply_field_items(self.original, current, self.dol, self.seed, settings)
        self.assertEqual(repeated, result)
        off = replace(settings, randomize_field_items=False)
        self.assertEqual(item_rules.apply_field_items(self.original, current, self.dol, self.seed, off)[0], current)

    def test_cash_shops_and_stones_keep_capacity_protected_stocks_and_global_mapping(self):
        for keep_balls, keep_healing, similar in ((True, True, True), (False, False, True),
                                                 (False, False, False), (True, False, False)):
            settings = replace(Options(), randomize_shop_items=True, keep_capture_items=keep_balls,
                               shop_keep_healing=keep_healing, items_similar_value=similar)
            baseline, _ = patch_rel(self.shop_rel, settings.stone_shops)
            result, report = item_rules.patch_cash_shops(baseline, self.dol, self.seed, settings)
            before, after = read_shops(baseline, item_rules.SHOP_LAYOUT), read_shops(result, item_rules.SHOP_LAYOUT)
            self.assertEqual(len(after), 14)
            self.assertLessEqual(report["packed_entries"], 122)
            mapping = {row["before"]: row["after"] for row in report["mapping"]}
            self.assertEqual(len(mapping), len(set(mapping.values())))
            self.assertFalse(set(mapping.values()) & set(report["protected_items"]))
            for old, new in mapping.items():
                self.assertTrue(self.catalog[new]["safe"])
                self.assertEqual(self.catalog[old]["category"], self.catalog[new]["category"])
                if similar:
                    self.assertLessEqual(self.catalog[old]["price"] / 2, self.catalog[new]["price"])
                    self.assertLessEqual(self.catalog[new]["price"], self.catalog[old]["price"] * 2)
            for old, new in zip(before, after, strict=True):
                self.assertEqual((old["type"], old["subtype"]), (new["type"], new["subtype"]))
                self.assertEqual(len(new["items"]), len(set(new["items"])))
                if old["index"] not in (3, 4, 5, 6, 7, 9):
                    self.assertEqual(new["items"], old["items"])
                else:
                    self.assertEqual(new["items"], [mapping.get(item, item) for item in old["items"]])
                    for old_item, new_item in zip(old["items"], new["items"], strict=True):
                        meta = self.catalog.get(old_item)
                        if old_item in STONE_IDS or old_item in (543, 544, 545) or (meta and (
                            keep_balls and meta["category"] == "balls" or keep_healing and meta["category"] == "healing")):
                            self.assertEqual(old_item, new_item)
            for index in (3, 5):
                self.assertTrue(set(STONE_IDS) <= set(after[index]["items"]))
            allowed = set(range(0x2AC, 0x2AC + 122 * 2)) | {
                0x3A0 + index * 4 + field for index in range(14) for field in (2, 3)}
            self.assertTrue(all(index in allowed for index, (a, b) in enumerate(zip(baseline, result)) if a != b))

    def test_five_languages_have_identical_shop_rel_and_unchanged_other_members(self):
        settings = replace(Options(), randomize_shop_items=True, shop_keep_healing=False,
                           keep_capture_items=False)
        results = []
        for filename in ARCHIVE_NAMES:
            source = (GAME / "files" / filename).read_bytes()
            rebuilt, report = item_rules.patch_item_archive(source, self.dol, self.seed, settings)
            old_members, new_members = parse_fsys(source)["members"], parse_fsys(rebuilt)["members"]
            self.assertEqual(len(old_members), len(new_members))
            for old, new in zip(old_members, new_members, strict=True):
                self.assertEqual((old["name"], old["identifier_raw"], old["compression"]),
                                 (new["name"], new["identifier_raw"], new["compression"]))
                if old["index"]:
                    self.assertEqual(decoded_member(source, old), decoded_member(rebuilt, new))
            results.append(decoded_member(rebuilt, new_members[0]))
            self.assertTrue(report["other_archive_members_identical"])
        self.assertEqual(len(set(results)), 1)


if __name__ == "__main__":
    unittest.main()
