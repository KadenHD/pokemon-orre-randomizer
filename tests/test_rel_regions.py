"""Regional identity, native text decoding and real-table invariants.

Small text fixtures run without ROM data. Optional integration checks consume
the separately extracted local originals; no game payload is part of sources.
"""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.boss_rules import boss_inventory
from orre_randomizer.engine.gameplay_rules import expanded_layout
from orre_randomizer.engine.inspect_tables import localized_names, u16
from orre_randomizer.engine.item_rules import apply_field_items, patch_item_archive
from orre_randomizer.engine.item_text import apply_item_name_spacing
from orre_randomizer.engine.randomize_trainers import layout, randomize_rel
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.engine.rel_regions import COMMON_COUNTS, region_for_rel, shop_archive_names
from orre_randomizer.engine.tm_rules import apply_tm_rules
from orre_randomizer.options import Options


def text_bank(language: str, text: str) -> bytes:
    japanese = language == "JP"
    header = struct.pack(">IHHII", int(not japanese), 1,
                         1 if japanese else int.from_bytes(language.encode("ascii"), "big"), 0, 0)
    return header + struct.pack(">II", 1001, 24) + text.encode("utf-16-be") + b"\0\0"


class NativeTextRegionTests(unittest.TestCase):
    def test_usa_bank_uses_actual_us_tag(self):
        data = text_bank("US", "BULBASAUR")
        names, banks = localized_names(data, [{"offset": 0, "index": 0}])
        self.assertEqual(names["US"][1001], "BULBASAUR")
        self.assertEqual(names["UK"], {})
        self.assertEqual(banks[0]["language_tag"], "US")

    def test_japanese_numeric_header_decodes_native_utf16(self):
        data = text_bank("JP", "フシギダネ")
        names, banks = localized_names(data, [{"offset": 0, "index": 0}])
        self.assertEqual(names["JP"][1001], "フシギダネ")
        self.assertTrue(all(not names[tag] for tag in ("UK", "US", "FR")))
        self.assertEqual(banks[0]["language_tag"], "JP")

    def test_unknown_and_modified_identities_are_rejected(self):
        with self.assertRaises(FormatError):
            region_for_rel(text_bank("JP", "フシギダネ"))


class RegionalDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        work = root / "build/region-compat-2026-11-02"
        cls.inputs = {}
        for tag, game_id in (("pal", "GC6P01"), ("usa", "GC6E01"), ("japan", "GC6J01")):
            common = work / "rel-research" / tag / "common.fsys-common_rel.rel"
            shop = work / "rel-research" / tag / "pocket_menu.fsys"
            dol = (root / "game/sys/main.dol" if tag == "pal" else
                   work / "dol-research" / f"{tag}-main.dol")
            if not all(path.is_file() for path in (common, shop, dol)):
                raise unittest.SkipTest("local three-region original fixtures are not available")
            cls.inputs[tag] = (game_id, common.read_bytes(), shop.read_bytes(), dol.read_bytes())

    def test_all_core_references_and_shadow_aliases(self):
        for tag, (game_id, original, _, _) in self.inputs.items():
            with self.subTest(region=tag):
                self.assertEqual(region_for_rel(original).game_id, game_id)
                tables = expanded_layout(original)
                self.assertEqual({key: row["count"] for key, row in tables.items()}, COMMON_COUNTS)
                species = tables["species"]
                national = [u16(original, species["offset"] + i * species["stride"] + 0x10)
                            for i in range(species["count"])]
                self.assertEqual(sorted(dex for dex in national if 1 <= dex <= 386), list(range(1, 387)))
                teams = tables["trainer_pokemon"]
                for index in range(teams["count"]):
                    pos = teams["offset"] + index * teams["stride"]
                    self.assertLess(u16(original, pos + 0xA), species["count"])
                    sid = original[pos + 3]
                    self.assertLess(sid, tables["shadow"]["count"])
                    if sid:
                        self.assertEqual(u16(original, pos + 0xA),
                                         u16(original, tables["shadow"]["offset"] + sid * 0x38 + 2))
                first, plan = randomize_rel(original, "regional-check")
                self.assertEqual(first, randomize_rel(original, "regional-check")[0])
                self.assertTrue(plan["summary"]["only_authorized_fields_changed"])
                self.assertTrue(plan["summary"]["shadow_species_consistent"])

    def test_native_boss_names_and_stone_spacing(self):
        for tag, (game_id, original, _, _) in self.inputs.items():
            with self.subTest(region=tag):
                self.assertEqual(len(boss_inventory(original)[1]), 32)
                output, report = apply_item_name_spacing(original, original)
                self.assertEqual(report["changed_names"], {"pal": 11, "usa": 1, "japan": 0}[tag])
                self.assertTrue(report["all_other_ids_resolve_to_identical_bytes"])
                names, _ = localized_names(output, layout(original)[1])
                if tag == "usa":
                    self.assertEqual(names["US"][5077], "THUNDER STONE")
                if tag == "japan":
                    self.assertEqual(output, original)
                    self.assertEqual(names["JP"][5074], "たいようのいし")
                self.assertEqual(len(shop_archive_names(original)), 5 if tag == "pal" else 1)

    def test_field_items_shops_and_tm_rules_on_each_region(self):
        options = replace(Options.recommended(), randomize_field_items=True, randomize_shop_items=True,
                          randomize_tm_moves=True, tm_compatibility_mode="type")
        for tag, (_, original, shop, dol) in self.inputs.items():
            with self.subTest(region=tag):
                field, field_report = apply_field_items(original, original, dol, "regional-items", options)
                self.assertTrue(field_report["only_item_ids_changed"])
                self.assertEqual(field, apply_field_items(original, original, dol, "regional-items", options)[0])
                changed, report = patch_item_archive(shop, dol, "regional-items", options)
                old_members, new_members = parse_fsys(shop)["members"], parse_fsys(changed)["members"]
                for old, new in zip(old_members[1:], new_members[1:], strict=True):
                    self.assertEqual(decoded_member(shop, old), decoded_member(changed, new))
                self.assertTrue(report["randomized_stock"]["protected_shops_unchanged"])
                rel_out, dol_out, tm_report = apply_tm_rules(original, original, dol, dol, "regional-tms", options)
                self.assertTrue(tm_report["rel_patch"]["outside_whitelist_unchanged"])
                self.assertTrue(tm_report["dol_patch"]["outside_whitelist_unchanged"])
                repeated = apply_tm_rules(original, original, dol, dol, "regional-tms", options)
                self.assertEqual((rel_out, dol_out), repeated[:2])

    def test_mixed_region_inputs_are_rejected(self):
        _, original, shop, _ = self.inputs["usa"]
        japanese_dol = self.inputs["japan"][3]
        options = replace(Options.recommended(), randomize_field_items=True, randomize_shop_items=True)
        with self.assertRaises(FormatError):
            apply_field_items(original, original, japanese_dol, "mixed", options)
        with self.assertRaises(FormatError):
            patch_item_archive(shop, japanese_dol, "mixed", options)
        with self.assertRaises(FormatError):
            apply_tm_rules(original, original, japanese_dol, japanese_dol, "mixed", options)


if __name__ == "__main__":
    unittest.main()
