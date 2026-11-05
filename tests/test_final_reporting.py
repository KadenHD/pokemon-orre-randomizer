"""The report must describe final patch bytes after advanced species selection."""
import copy
from dataclasses import replace
from pathlib import Path
import struct
import threading
import unittest
from unittest.mock import patch

from orre_randomizer import service
from orre_randomizer.engine.gameplay_rules import apply_dol_rules, apply_rel_rules
from orre_randomizer.engine.inspect_tables import localized_names, u16
from orre_randomizer.engine.randomize_story import SPECIALS, experience_at_level
from orre_randomizer.engine.randomize_trainers import layout, original_common
from orre_randomizer.engine.species_rules import species_catalog
from orre_randomizer.options import Options


class FinalReportTests(unittest.TestCase):
    def test_final_constants_replace_stale_names_exp_and_shadow_provenance(self):
        original = bytearray(256)
        for index, offset in ((1, 32), (2, 64)):
            struct.pack_into(">I", original, offset + 0x18, 100 + index)
            original[offset] = (0, 5)[index - 1]
            struct.pack_into(">H", original, 200 + index * 4 + 2, index)
        base = bytearray(original)
        struct.pack_into(">HH", base, 206, 2, 0)
        struct.pack_into(">H", base, 210, 1)
        final = bytes(original)
        dol = bytearray(160)
        struct.pack_into(">H", dol, 2, 1)
        struct.pack_into(">H", dol, 6, 26)
        struct.pack_into(">H", dol, 0x92, 26 ** 3)
        summary = {
            "special_changes": [{"key": "umbreon", "new_species_index": 2,
                "new_species_fr": "stale", "level_preserved": 26, "growth_group": 5,
                "exp_field_offset": 0x92, "old_exp": 999, "new_exp": 999}],
            "special_gameplay": {"specials": [{"key": "umbreon", "species": 2,
                                              "moves": [10, 11, 12, 13]}]},
            "shadow_families": {"version": "shadow-family-v3",
                "rerolls": [{"shadow_id": 99, "new_species_index": 999}],
                "rerolled_shadow_ids": [99], "retained_shadow_ids": []}}
        saved = copy.deepcopy(summary)
        metadata = {1: {"offset": 32, "national_dex": 1},
                    2: {"offset": 64, "national_dex": 2}}
        names = {"FR": {101: "Bulbizarre", 102: "Herbizarre"},
                 "UK": {101: "Bulbasaur", 102: "Ivysaur"},
                 "GE": {101: "Bisasam", 102: "Bisaknosp"},
                 "IT": {101: "Bulbasaur", 102: "Ivysaur"},
                 "SP": {101: "Bulbasaur", 102: "Ivysaur"}}
        tables = {"shadow": {"offset": 200, "stride": 4, "count": 3}}
        with patch.object(service, "layout", return_value=(tables, {})), \
             patch.object(service, "localized_names", return_value=(names, {})), \
             patch.object(service, "species_catalog", return_value=metadata), \
             patch.object(service, "evolution_families", return_value=({1: 1, 2: 2}, {1: [1], 2: [2]})), \
             patch.object(service, "special_targets", return_value=({"key": "umbreon", "base": 0, "xp": 17576, "old": 1},)):
            result = service.final_report_summary(bytes(original), bytes(base), final,
                bytes(dol), bytes(dol), "fixture", Options.recommended(), summary)
        self.assertEqual(summary, saved)
        self.assertEqual(final, original)
        special = result["special_changes"][0]
        self.assertEqual((special["new_species_index"], special["new_species_fr"],
                          special["growth_group"], special["new_exp"]), (1, "Bulbizarre", 0, 17576))
        gameplay = result["special_gameplay"]["specials"][0]
        self.assertEqual((gameplay["species"], gameplay["name_en"], gameplay["experience"]),
                         (1, "Bulbasaur", 17576))
        self.assertEqual((gameplay["name_de"], gameplay["name_es"], gameplay["name_it"]),
                         ("Bisasam", "Bulbasaur", "Bulbasaur"))
        self.assertEqual(gameplay["moves"], [10, 11, 12, 13])
        shadow = result["shadow_families"]
        self.assertEqual(shadow["final_distinct_family_count"], 2)
        self.assertEqual(shadow["rerolled_shadow_ids"], [1, 2])
        self.assertEqual([(r["base_species_index"], r["new_species_index"])
                          for r in shadow["rerolls"]], [(2, 1), (1, 2)])
        self.assertEqual(shadow["base_pick_source"], "REL immediately before advanced gameplay rules")


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires user's original local PAL image")
class PalFinalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_common(GAME)[2]
        cls.original_dol = (GAME / "sys/main.dol").read_bytes()
        cls.seed = "report-regression"
        cls.options = replace(Options.recommended(), allow_gen1=False,
                              allow_gen2=False, allow_legendaries=False)
        cls.base, summary = service.transform_rel(cls.original, cls.seed, cls.options)
        cls.rel, summary["gameplay"] = apply_rel_rules(cls.original, cls.base, cls.seed, cls.options)
        base_dol, summary["special_changes"] = service.transform_dol(
            cls.original_dol, cls.original, cls.seed, cls.options)
        cls.dol, summary["special_gameplay"] = apply_dol_rules(cls.original_dol,
            base_dol, cls.original, cls.rel, cls.seed, cls.options)
        cls.intermediate = copy.deepcopy(summary)
        cls.report = service.final_report_summary(cls.original, cls.base, cls.rel,
            cls.original_dol, cls.dol, cls.seed, cls.options, summary)
        cls.tables, cls.symbols = layout(cls.original)

    def test_six_special_rows_are_verified_against_final_dol_and_rel(self):
        names, _ = localized_names(self.rel, self.symbols)
        catalog = species_catalog(self.rel, self.tables)
        old_picks = {r["key"]: r["new_species_index"] for r in self.intermediate["special_changes"]}
        final_picks = {r["key"]: r for r in self.report["special_changes"]}
        self.assertTrue(any(old_picks[k] != r["new_species_index"] for k, r in final_picks.items()))
        for target in SPECIALS:
            row = final_picks[target["key"]]
            actual = u16(self.dol, target["base"] + 2)
            meta = catalog[actual]
            name_id = struct.unpack_from(">I", self.rel, meta["offset"] + 0x18)[0]
            self.assertEqual(row["new_species_index"], actual)
            self.assertEqual(row["new_species_fr"], names["FR"][name_id])
            self.assertEqual(row["new_national_dex"], meta["national_dex"])
            self.assertEqual(row["growth_group"], self.rel[meta["offset"]])
            if "xp" in target:
                self.assertEqual(row["new_exp"], u16(self.dol, target["base"] + 0x92))
                self.assertEqual(row["new_exp"], experience_at_level(row["growth_group"], row["level_preserved"]))
            special = next(r for r in self.report["special_gameplay"]["specials"]
                           if r["key"] == target["key"])
            self.assertEqual(special["species"], actual)
            self.assertEqual(special["growth_group"], row["growth_group"])
            self.assertEqual(special["name_fr"], row["new_species_fr"])
            for language, bank in (("de", "GE"), ("es", "SP"), ("it", "IT")):
                self.assertEqual(special["name_" + language], names[bank][name_id])

    def test_final_shadow_snapshot_and_rerolls_describe_all_48_actual_families(self):
        from orre_randomizer.engine.evolution_rules import evolution_families
        families, _ = evolution_families(self.original, self.tables)
        shadow = self.tables["shadow"]
        rows = self.report["final_shadow_picks"]
        self.assertEqual(len(rows), 48)
        self.assertEqual(len({r["family"] for r in rows}), 48)
        for row in rows:
            pos = shadow["offset"] + row["shadow_id"] * shadow["stride"] + 2
            self.assertEqual(row["species_index"], u16(self.rel, pos))
            self.assertEqual(row["family"], families[u16(self.rel, pos)])
        report = self.report["shadow_families"]
        self.assertEqual(report["final_picks"], rows)
        self.assertEqual(report["final_distinct_family_count"], 48)
        for row in report["rerolls"]:
            pos = shadow["offset"] + row["shadow_id"] * shadow["stride"] + 2
            self.assertEqual((row["base_species_index"], row["new_species_index"]),
                             (u16(self.base, pos), u16(self.rel, pos)))
            self.assertNotIn("remaining_species_pool_size", row)

    def test_disabled_advanced_rules_keep_legacy_collision_report(self):
        options = Options()
        base, summary = service.transform_rel(self.original, self.seed, options)
        dol, summary["special_changes"] = service.transform_dol(self.original_dol,
            self.original, self.seed, options)
        before = copy.deepcopy(summary["shadow_families"])
        report = service.final_report_summary(self.original, base, base,
            self.original_dol, dol, self.seed, options, summary)["shadow_families"]
        for key, value in before.items():
            self.assertEqual(report[key], value, key)
        self.assertEqual(len(report["final_picks"]), 48)

    def test_report_refresh_does_not_change_any_iso_patch_payload(self):
        iso = ROOT / "Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso"
        if not iso.is_file():
            self.skipTest("requires user's original local ISO")
        boot = service.check_header(iso)
        args = (iso, boot, self.seed, self.options, lambda *_: None, threading.Event())
        with patch.object(service, "final_report_summary", side_effect=lambda *args: args[-1]):
            before, stale = service.build_patches(*args)
        after, refreshed = service.build_patches(*args)
        self.assertEqual(after, before)
        self.assertNotEqual(stale["special_changes"], refreshed["special_changes"])
        self.assertNotEqual(stale["shadow_families"], refreshed["shadow_families"])


if __name__ == "__main__":
    unittest.main()
