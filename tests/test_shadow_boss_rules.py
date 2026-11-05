"""Boss-Shadow hard filters, global family matching and byte whitelists."""
from dataclasses import asdict
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.evolution_rules import evolution_families
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine import shadow_boss_rules as rules
from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL, STAT_OFFSETS, species_catalog
from orre_randomizer.options import Options


def options(**changes):
    return SimpleNamespace(**{**asdict(Options()), "boss_shadow_legendary_mode": "any",
        "boss_shadow_power_mode": "global", "boss_shadow_min_bst": 0, **changes})


def fixture():
    data = bytearray(8192)
    tables = {"species": {"offset": 0x500, "count": 11, "stride": 0x11C},
              "trainer_pokemon": {"offset": 0x100, "count": 7, "stride": 0x50},
              "shadow": {"offset": 0x1800, "count": 4, "stride": 0x38}}
    species = {1: (1, 300), 2: (2, 300), 3: (244, 580), 4: (245, 580),
               5: (144, 580), 6: (25, 300), 7: (150, 680), 8: (292, 236),
               9: (252, 600), 10: (151, 600)}
    for index, (national, total) in species.items():
        pos = 0x500 + index * 0x11C
        struct.pack_into(">H", data, pos + 0x10, national)
        struct.pack_into(">I", data, pos + 0x18, 1000 + index)
        data[pos + 0x32:pos + 0x34] = bytes((1, 2 if index == 3 else 0))
        values = [total // 6] * 6
        values[0] += total - sum(values)
        for offset, value in zip(STAT_OFFSETS, values, strict=True):
            data[pos + offset] = value
    evolution = 0x500 + 0x11C + 0x9C
    struct.pack_into(">BBHH", data, evolution, 4, 0, 16, 2)
    for sid, old in ((1, 1), (2, 3), (3, 6)):
        pos = 0x1800 + sid * 0x38
        data[pos:pos + 2] = bytes((45, 127))
        struct.pack_into(">H", data, pos + 2, old)
        data[pos + 6:pos + 10] = b"FLAG"
    for index, species, sid in ((1, 1, 1), (2, 1, 1), (3, 3, 2), (4, 6, 3), (5, 2, 0)):
        pos = 0x100 + index * 0x50
        data[pos] = 1
        data[pos + 3] = sid
        data[pos + 4] = 20 + index
        struct.pack_into(">H", data, pos + 0xA, species)
        struct.pack_into(">I", data, pos + 0x14, 1000 + species)
        data[pos + 0x36:pos + 0x38] = b"\xff\xff"
    bosses = [{"key": "fixture-boss", "trainer_id": 0, "slots": [
        {"index": index, "offset": 0x100 + index * 0x50, "shadow_id": sid}
        for index, sid in ((1, 1), (3, 2))]}]
    return bytes(data), tables, bosses


class ShadowBossTests(unittest.TestCase):
    def setUp(self):
        self.original, self.tables, self.bosses = fixture()

    def run_rules(self, seed="boss-shadow-synth", current=None, **changes):
        return rules.apply_shadow_boss_tables(self.original, current or self.original,
            seed, options(**changes), self.tables, self.bosses)

    def test_defaults_and_disabled_shadow_randomization_keep_current_bytes(self):
        current = bytearray(self.original)
        current[27] = 99
        result, report = self.run_rules(current=bytes(current))
        self.assertEqual(result, current)
        self.assertFalse(report["active"])
        self.assertFalse(rules.shadow_boss_rules_active(options()))
        result, report = self.run_rules(current=bytes(current), randomize_shadows=False,
                                       boss_shadow_min_bst=780)
        self.assertEqual(result, current)
        self.assertFalse(report["active"])
        # No-op public route needs neither a fingerprint nor an inventory.
        self.assertEqual(rules.apply_shadow_boss_rules(b"abc", b"xyz", "seed", options())[0], b"xyz")

    def test_legendary_status_preserved_for_bosses_and_all_aliases_synchronized(self):
        result, report = self.run_rules(boss_shadow_legendary_mode="preserve")
        catalog = species_catalog(result, self.tables)
        self.assertEqual(report["boss_groups"], [1, 2])
        self.assertEqual(report["shadow_group_count"], 3)
        self.assertEqual(report["distinct_family_count"], 3)
        for row in report["picks"]:
            if row["boss"]:
                before = species_catalog(self.original, self.tables)[row["old_species_index"]]["national_dex"]
                self.assertEqual(before in LEGENDARY_NATIONAL,
                                 row["national_dex"] in LEGENDARY_NATIONAL)
            for index in row["trainer_pokemon_indices"]:
                pos = 0x100 + index * 0x50
                self.assertEqual(u16(result, pos + 0xA), row["new_species_index"])
                self.assertEqual(u32(result, pos + 0x14), 1000 + row["new_species_index"])
                self.assertFalse(result[pos] == 1 and not catalog[row["new_species_index"]]["abilities"][1])
        self.assertEqual(self.run_rules(boss_shadow_legendary_mode="preserve"), (result, report))

    def test_only_species_names_and_ability_selectors_change(self):
        current = bytearray(self.original)
        current[27] = 99
        result, report = self.run_rules(current=bytes(current), boss_shadow_legendary_mode="exclude")
        allowed = {0x1800 + sid * 0x38 + field for sid in (1, 2, 3) for field in (2, 3)}
        for index in (1, 2, 3, 4):
            pos = 0x100 + index * 0x50
            allowed.update((pos, pos + 0xA, pos + 0xB, *range(pos + 0x14, pos + 0x18)))
        changed = {i for i, (a, b) in enumerate(zip(current, result, strict=True)) if a != b}
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        self.assertTrue(report["levels_and_capture_rates_preserved"])
        for row in report["picks"]:
            self.assertNotEqual(row["national_dex"], 292)
            if row["boss"]:
                self.assertNotIn(row["national_dex"], LEGENDARY_NATIONAL)

    def test_minimum_bst_and_similarity_are_hard_constraints(self):
        result, report = self.run_rules(boss_shadow_min_bst=500)
        self.assertTrue(all(row["replacement_bst"] >= 500 for row in report["picks"] if row["boss"]))
        result, report = self.run_rules(boss_shadow_power_mode="similar")
        for row in report["picks"]:
            if row["boss"]:
                self.assertLessEqual(abs(row["replacement_bst"] - row["original_bst"]),
                                     max(50, row["original_bst"] // 5))
        with self.assertRaisesRegex(FormatError, "Aucune espèce admissible"):
            self.run_rules(boss_shadow_power_mode="similar", boss_shadow_min_bst=500)

    def test_generation_and_global_legendary_exclusions_are_never_relaxed(self):
        result, report = self.run_rules(boss_shadow_power_mode="free", allow_gen1=False,
                                       allow_gen2=False, unique_shadows=False)
        self.assertTrue(all(row["national_dex"] > 251 for row in report["picks"]))
        with self.assertRaisesRegex(FormatError, "Aucune espèce admissible"):
            self.run_rules(boss_shadow_legendary_mode="preserve", allow_legendaries=False)
        with self.assertRaisesRegex(FormatError, "Aucune espèce admissible"):
            self.run_rules(boss_shadow_legendary_mode="exclude", allow_gen1=False,
                           allow_gen2=False, allow_gen3=False)

    def test_impossible_unique_family_assignment_errors_without_silent_relaxation(self):
        with self.assertRaisesRegex(FormatError, "Impossible d’attribuer une famille"):
            self.run_rules(boss_shadow_legendary_mode="exclude", boss_shadow_min_bst=500)
        result, report = self.run_rules(boss_shadow_legendary_mode="exclude", boss_shadow_min_bst=500,
                                       unique_shadows=False)
        self.assertTrue(all(row["new_species_index"] == 9 for row in report["picks"] if row["boss"]))
        self.assertFalse(report["unique_families"])

    def test_matching_finds_a_full_assignment_when_a_shared_family_is_needed_elsewhere(self):
        catalog = species_catalog(self.original, self.tables)
        families = evolution_families(self.original, self.tables)[0]
        matched = rules._match_families("matching", {1: [4, 6], 2: [4]}, families,
                                      catalog, {1: 1, 2: 3}, {1: False, 2: False}, {2})
        self.assertEqual(matched, {1: families[6], 2: families[4]})
        self.assertIsNone(rules._match_families("matching", {1: [4], 2: [4]}, families,
            catalog, {1: 1, 2: 3}, {1: False, 2: False}, {2}))

    def test_seed_changes_picks_and_dict_iteration_order_does_not(self):
        outputs = {self.run_rules(seed=f"seed-{i}", boss_shadow_power_mode="free")[0] for i in range(6)}
        self.assertGreater(len(outputs), 1)
        one = self.run_rules(boss_shadow_power_mode="free")
        two = rules.apply_shadow_boss_tables(self.original, self.original, "boss-shadow-synth",
            options(boss_shadow_power_mode="free"), dict(reversed(list(self.tables.items()))),
            list(reversed(self.bosses)))
        self.assertEqual(one, two)

    def test_free_mode_ignores_global_balance_only_for_bosses(self):
        _, report = self.run_rules(boss_shadow_power_mode="free", balance_species=True)
        for row in report["picks"]:
            if row["boss"]:
                self.assertEqual(row["candidate_count"], row["preferred_candidate_count"])
        ordinary = next(row for row in report["picks"] if not row["boss"])
        self.assertLess(ordinary["preferred_candidate_count"], ordinary["candidate_count"])

    def test_global_power_fallback_is_reported_when_preferred_families_cannot_cover_all_groups(self):
        original = bytearray(self.original)
        for field in STAT_OFFSETS:
            original[0x500 + 3 * 0x11C + field] = 50
        result, report = rules.apply_shadow_boss_tables(bytes(original), bytes(original), "fallback",
            options(boss_shadow_legendary_mode="exclude", balance_species=True, allow_legendaries=False),
            self.tables, self.bosses)
        self.assertEqual(report["distinct_family_count"], 3)
        self.assertTrue(report["power_preference_fallback_ids"])
        for row in report["picks"]:
            if row["boss"]:
                self.assertNotIn(row["national_dex"], LEGENDARY_NATIONAL)
        self.assertEqual(len(result), len(original))

    def test_rejects_malformed_options_identity_and_alias_metadata(self):
        for changes in ({"boss_shadow_min_bst": True}, {"boss_shadow_min_bst": 781},
                        {"boss_shadow_legendary_mode": "unknown"}, {"boss_shadow_power_mode": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_rules(**changes)
        with self.assertRaises(FormatError):
            rules.apply_shadow_boss_tables(self.original, self.original[:-1], "seed",
                options(boss_shadow_power_mode="free"), self.tables, self.bosses)
        broken = bytearray(self.original)
        struct.pack_into(">H", broken, 0x100 + 2 * 0x50 + 0xA, 2)
        with self.assertRaisesRegex(FormatError, "apparitions"):
            rules.apply_shadow_boss_tables(bytes(broken), bytes(broken), "seed",
                options(boss_shadow_power_mode="free"), self.tables, self.bosses)


@unittest.skipUnless(Path("game/files/common.fsys").is_file(), "requires original local PAL dump")
class PalShadowBossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from orre_randomizer.engine.randomize_trainers import original_common
        from orre_randomizer.engine.boss_rules import boss_inventory
        cls.original = original_common(Path("game"))[2]
        cls.tables, cls.bosses = boss_inventory(cls.original)

    def test_seven_groups_48_families_and_all_aliases_with_legendary_preservation(self):
        choices = options(boss_shadow_legendary_mode="preserve", balance_species=True)
        result, report = rules.apply_shadow_boss_rules(self.original, self.original, "boss-pal-v05", choices)
        self.assertEqual(report["boss_groups"], [19, 21, 23, 34, 38, 43, 44])
        self.assertEqual(report["shadow_group_count"], 48)
        self.assertEqual(report["distinct_family_count"], 48)
        catalog = species_catalog(self.original, self.tables)
        for row in report["picks"]:
            if row["boss"]:
                self.assertEqual(catalog[row["old_species_index"]]["national_dex"] in LEGENDARY_NATIONAL,
                                 row["national_dex"] in LEGENDARY_NATIONAL)
            for index in row["trainer_pokemon_indices"]:
                pos = self.tables["trainer_pokemon"]["offset"] + index * self.tables["trainer_pokemon"]["stride"]
                self.assertEqual(u16(result, pos + 0xA), row["new_species_index"])
                self.assertEqual(result[pos + 3:pos + 0xA], self.original[pos + 3:pos + 0xA])
        self.assertEqual(rules.apply_shadow_boss_rules(self.original, self.original, "boss-pal-v05", choices),
                         (result, report))

    def test_strict_power_and_minimum_use_original_totals(self):
        choices = options(boss_shadow_power_mode="similar", boss_shadow_min_bst=400)
        _, report = rules.apply_shadow_boss_rules(self.original, self.original, "boss-pal-power", choices)
        self.assertEqual(report["distinct_family_count"], 48)
        for row in report["picks"]:
            if row["boss"]:
                self.assertGreaterEqual(row["replacement_bst"], 400)
                self.assertLessEqual(abs(row["replacement_bst"] - row["original_bst"]),
                                     max(50, row["original_bst"] // 5))

    def test_public_wrapper_rejects_modified_original_and_mismatching_tables(self):
        choices = options(boss_shadow_power_mode="free")
        changed = bytearray(self.original)
        changed[-1] ^= 1
        with self.assertRaises(FormatError):
            rules.apply_shadow_boss_rules(bytes(changed), bytes(changed), "seed", choices)
        wrong = {**self.tables, "shadow": {**self.tables["shadow"], "count": 4}}
        with self.assertRaisesRegex(FormatError, "inventaire PAL"):
            rules.apply_shadow_boss_rules(self.original, self.original, "seed", choices, wrong)


if __name__ == "__main__":
    unittest.main()
