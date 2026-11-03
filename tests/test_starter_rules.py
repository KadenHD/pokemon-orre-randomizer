"""Starter-pair policies on synthetic data and optional fingerprinted PAL bytes."""
from dataclasses import dataclass, replace
from pathlib import Path
import struct
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError
from colosseum_randomizer.engine.inspect_tables import u16
from colosseum_randomizer.engine.randomize_story import experience_at_level
from colosseum_randomizer.engine.species_rules import (LEGENDARY_NATIONAL, STAT_OFFSETS,
                                                     species_catalog)
from colosseum_randomizer.engine.starter_rules import (STARTERS, apply_starter_rules,
                                                      apply_starter_tables, base_species,
                                                      starter_rules_active)
from colosseum_randomizer.engine.evolution_rules import evolution_stage_info


@dataclass(frozen=True)
class Rules:
    starter_umbreon: bool = True
    starter_espeon: bool = True
    starter_balance_pair: bool = False
    starter_distinct_families: bool = False
    starter_complementary_types: bool = False
    starter_base_forms: bool = False
    allow_gen1: bool = True
    allow_gen2: bool = True
    allow_gen3: bool = True
    allow_legendaries: bool = True
    balance_species: bool = False


@dataclass(frozen=True)
class StageRules(Rules):
    starter_stage: str = "any"
    starter_three_stage_families: bool = False


def fixture():
    table = {"offset": 64, "count": 293, "stride": 0x11C}
    tables = {"species": table}
    raw = bytearray(table["offset"] + table["count"] * table["stride"] + 16)
    rows = {
        1: (1, (12, 12), 300), 2: (2, (12, 3), 390), 3: (3, (12, 3), 525),
        4: (4, (10, 10), 309), 5: (5, (10, 10), 405), 6: (6, (10, 2), 534),
        7: (7, (11, 11), 314), 8: (8, (11, 11), 405), 9: (9, (11, 11), 530),
        25: (25, (13, 13), 320), 133: (133, (0, 0), 325),
        144: (144, (15, 2), 580), 172: (172, (13, 13), 205),
        196: (196, (14, 14), 525), 197: (197, (17, 17), 525),
        252: (252, (12, 12), 310), 292: (292, (6, 7), 236),
    }
    for index, (national, types, total) in rows.items():
        pos = table["offset"] + index * table["stride"]
        raw[pos] = index % 6
        struct.pack_into(">H", raw, pos + 0x10, national)
        raw[pos + 0x30:pos + 0x34] = bytes((*types, 65, 0))
        for ordinal, field in enumerate(STAT_OFFSETS):
            raw[pos + field] = total // 6 + (ordinal < total % 6)
    for source, targets in {1: [2], 2: [3], 4: [5], 5: [6],
                            7: [8], 8: [9], 172: [25], 133: [196, 197]}.items():
        for slot, target in enumerate(targets):
            pos = table["offset"] + source * table["stride"] + 0x9C + slot * 6
            struct.pack_into(">BBHH", raw, pos, 4, 0, 16, target)
    dol = bytearray(0x132000)
    for target in STARTERS:
        pos = target["base"]
        struct.pack_into(">II", dol, pos, 0x38800000 | target["old"], 0x38A00000 | target["level"])
        struct.pack_into(">I", dol, pos + 0x90, 0x38E00000 | target["xp"])
    return bytes(dol), bytes(raw), tables


class StarterPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dol, cls.rel, cls.tables = fixture()

    def apply(self, options, seed="starter-seed", current_dol=None, rel=None):
        return apply_starter_tables(self.dol, self.dol if current_dol is None else current_dol,
                                    self.rel, self.rel if rel is None else rel,
                                    seed, options, self.tables)

    def test_inactive_and_all_fixed_preserve_every_prior_byte(self):
        current = bytearray(self.dol + b"appended section guard")
        current[7] = 0xA5
        for options in (Rules(), replace(Rules(), starter_umbreon=False, starter_espeon=False,
                                         starter_balance_pair=True, starter_distinct_families=True,
                                         starter_complementary_types=True, starter_base_forms=True)):
            patched, report = self.apply(options, current_dol=bytes(current))
            self.assertEqual(patched, current)
            self.assertFalse(report["applied"])
            self.assertFalse(starter_rules_active(options))

    def test_seed_repeats_and_only_species_exp_fields_change(self):
        options = replace(Rules(), starter_balance_pair=True, starter_distinct_families=True,
                          starter_complementary_types=True)
        actual, report = self.apply(options, seed="été reproductible")
        self.assertEqual((actual, report), self.apply(options, seed="été reproductible"))
        pairs = {tuple(row["species_index"] for row in self.apply(options, seed=f"seed-{i}")[1]["pair"])
                 for i in range(12)}
        self.assertGreater(len(pairs), 1)
        allowed = {target["base"] + field for target in STARTERS for field in (2, 3, 0x92, 0x93)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.dol, actual))))
        for target, row in zip(STARTERS, report["pair"]):
            self.assertNotEqual(row["species_index"], target["old"])
            pos = self.tables["species"]["offset"] + row["species_index"] * self.tables["species"]["stride"]
            self.assertEqual(row["experience"], experience_at_level(self.rel[pos], target["level"]))
            self.assertEqual(u16(actual, target["base"] + 6), target["level"])
        self.assertLessEqual(report["pair_bst_difference"], report["pair_bst_tolerance"])
        first, second = report["pair"]
        self.assertNotEqual(first["family"], second["family"])
        self.assertFalse(set(first["types"]) & set(second["types"]))

    def test_single_random_starter_respects_fixed_partner_and_never_edits_it(self):
        options = replace(Rules(), starter_espeon=False, starter_distinct_families=True,
                          starter_balance_pair=True, starter_complementary_types=True)
        fixed = STARTERS[1]["base"]
        for i in range(12):
            actual, report = self.apply(options, seed=f"single-{i}")
            self.assertEqual(actual[fixed:fixed + 0x94], self.dol[fixed:fixed + 0x94])
            self.assertEqual(report["pair"][1]["species_index"], 196)
            self.assertFalse(report["pair"][1]["randomized"])
            self.assertNotEqual(report["pair"][0]["family"], 133)

    def test_base_forms_use_incoming_evolution_edges_including_baby_species(self):
        roots = base_species(self.rel, self.tables)
        self.assertIn(172, roots)
        self.assertIn(144, roots)  # Single-stage species count as base forms.
        self.assertFalse(roots & {2, 3, 5, 6, 8, 9, 25, 196, 197})
        options = replace(Rules(), starter_base_forms=True)
        for i in range(12):
            _, report = self.apply(options, seed=f"base-{i}")
            self.assertTrue(all(row["species_index"] in roots and row["base_form"] for row in report["pair"]))
        # A fixed evolved partner is exempt from the base-form restriction.
        _, report = self.apply(replace(options, starter_espeon=False))
        self.assertEqual(report["pair"][1]["species_index"], 196)
        self.assertFalse(report["pair"][1]["base_form"])

    def test_three_stages_count_depth_not_branches_or_species_count(self):
        stages = evolution_stage_info(self.rel, self.tables)
        self.assertEqual([stages[i]["stage"] for i in (1, 2, 3)], [0, 1, 2])
        self.assertEqual([stages[i]["family_stages"] for i in (1, 2, 3)], [3, 3, 3])
        self.assertEqual(stages[196]["base_species"], [133])
        # Eevee + two branches are three species but only two successive stages.
        self.assertEqual(stages[133]["family_stages"], 2)
        self.assertEqual(stages[172]["stage"], 0)
        self.assertEqual(stages[25]["stage"], 1)
        self.assertFalse(stages[144]["final_form"])
        branched = bytearray(self.rel)
        def position(index, slot=0):
            return self.tables["species"]["offset"] + index*self.tables["species"]["stride"] + 0x9C + slot*6
        # One base with two separate two-evolution paths: five species, three stages.
        branched[position(4):position(4)+6] = b"\0"*6
        struct.pack_into(">BBHH", branched, position(1, 1), 4, 0, 16, 5)
        branch_stages = evolution_stage_info(bytes(branched), self.tables)
        self.assertEqual([branch_stages[i]["family_stages"] for i in (1, 2, 3, 5, 6)], [3]*5)
        for stage, allowed in (("base", {1, 4, 7}), ("first", {2, 5, 8}),
                               ("final", {3, 6, 9}), ("any", set(range(1, 10)))):
            options = StageRules(starter_stage=stage, starter_three_stage_families=True)
            for ordinal in range(8):
                _, report = self.apply(options, seed=f"stages-{ordinal}")
                for row in report["pair"]:
                    self.assertIn(row["species_index"], allowed)
                    self.assertEqual(row["family_stages"], 3)

    def test_stage_filters_ignore_fixed_starters_and_never_relax_empty_pools(self):
        options = StageRules(starter_stage="base", starter_three_stage_families=True, starter_espeon=False)
        output, report = self.apply(options)
        self.assertIn(report["pair"][0]["species_index"], {1, 4, 7})
        self.assertEqual(report["pair"][1]["species_index"], 196)
        fixed = STARTERS[1]["base"]
        self.assertEqual(output[fixed:fixed+0x94], self.dol[fixed:fixed+0x94])
        with self.assertRaisesRegex(FormatError, "Aucun starter"):
            self.apply(replace(options, allow_gen1=False, allow_gen3=False))
        for invalid in (None, "middle", True):
            with self.assertRaises(ValueError):
                self.apply(replace(options, starter_stage=invalid))
        with self.assertRaises(ValueError):
            self.apply(replace(options, starter_three_stage_families=1))

    def test_directed_cycles_are_refused(self):
        rel = bytearray(self.rel)
        pos = self.tables["species"]["offset"] + 3 * self.tables["species"]["stride"] + 0x9C
        struct.pack_into(">BBHH", rel, pos, 4, 0, 16, 1)
        with self.assertRaisesRegex(FormatError, "cycle"):
            evolution_stage_info(bytes(rel), self.tables)

    def test_base_three_stage_balancing_uses_original_base_ancestor(self):
        options = StageRules(starter_stage="base", starter_three_stage_families=True,
                             starter_distinct_families=True, starter_complementary_types=True,
                             starter_balance_pair=True, balance_species=True)
        output, report = self.apply(options)
        self.assertGreater(report["valid_pair_count"], 2)
        self.assertTrue(all(row["species_index"] in {1, 4, 7} for row in report["pair"]))
        self.assertEqual(output, self.apply(options)[0])
        self.assertEqual(report["power_window_source"], "original base ancestor BST; final candidate BST")

    def test_generation_legendary_and_shedinja_exclusions_remain_hard(self):
        options = replace(Rules(), starter_espeon=False, starter_base_forms=True,
                          allow_gen1=False, allow_gen2=False, allow_legendaries=False)
        _, report = self.apply(options)
        self.assertEqual(report["pair"][0]["species_index"], 252)
        self.assertNotIn(report["pair"][0]["national_dex"], LEGENDARY_NATIONAL | {292})
        with self.assertRaisesRegex(FormatError, "Aucun starter"):
            self.apply(replace(options, allow_gen3=False))

    def test_complementary_types_use_final_rel_and_impossible_pair_errors(self):
        current = bytearray(self.rel)
        catalog = species_catalog(self.rel, self.tables)
        for row in catalog.values():
            current[row["offset"] + 0x30:row["offset"] + 0x32] = b"\x0e\x0e"
        options = replace(Rules(), starter_espeon=False, starter_complementary_types=True)
        with self.assertRaisesRegex(FormatError, "Aucun couple"):
            self.apply(options, rel=bytes(current))
        pos = catalog[4]["offset"]
        current[pos + 0x30:pos + 0x32] = b"\x0a\x0a"
        _, report = self.apply(options, rel=bytes(current))
        self.assertEqual(report["valid_pair_count"], 1)
        self.assertEqual(report["pair"][0]["species_index"], 4)

    def test_pair_balance_uses_final_stats_with_strict_tolerance(self):
        current = bytearray(self.rel)
        catalog = species_catalog(self.rel, self.tables)
        for index, row in catalog.items():
            total = 525 if index == 196 else 520 if index == 1 else 250
            for ordinal, field in enumerate(STAT_OFFSETS):
                current[row["offset"] + field] = total // 6 + (ordinal < total % 6)
        options = replace(Rules(), starter_espeon=False, starter_balance_pair=True,
                          starter_distinct_families=True)
        _, report = self.apply(options, rel=bytes(current))
        self.assertEqual(report["pair"][0]["species_index"], 1)
        self.assertEqual(report["pair_bst_difference"], 5)
        self.assertEqual(report["pair_bst_tolerance"], 104)
        # Excluding the only balanced alternative fails; no power rule is relaxed.
        with self.assertRaisesRegex(FormatError, "Aucun couple"):
            self.apply(replace(options, allow_gen1=False), rel=bytes(current))

    def test_species_power_window_is_composed_after_base_form_exclusion(self):
        options = replace(Rules(), starter_base_forms=True, balance_species=True)
        _, report = self.apply(options)
        # The 580-BST single-stage legendary is the only eligible root within
        # the native 525 +/- 105 window; evolved 525/530/534 entries stay excluded.
        self.assertEqual([row["species_index"] for row in report["pair"]], [144, 144])
        # Excluding legends selects nearest eligible roots rather than readding them.
        _, report = self.apply(replace(options, allow_legendaries=False))
        self.assertTrue(all(row["base_form"] and row["national_dex"] not in LEGENDARY_NATIONAL
                            for row in report["pair"]))

    def test_reject_bad_instructions_shapes_and_boolean_settings(self):
        options = replace(Rules(), starter_distinct_families=True)
        for pos in (STARTERS[0]["base"], STARTERS[1]["base"] + 4,
                    STARTERS[0]["base"] + 0x90):
            current = bytearray(self.dol)
            current[pos] ^= 1
            with self.subTest(pos=pos), self.assertRaises(FormatError):
                self.apply(options, current_dol=bytes(current))
        with self.assertRaises(FormatError):
            self.apply(options, current_dol=self.dol[:-1])
        with self.assertRaises(FormatError):
            self.apply(options, rel=self.rel[:-1])
        with self.assertRaises(ValueError):
            self.apply(replace(options, starter_balance_pair="yes"))
        for seed in ("", "é" * 129):
            with self.assertRaises(ValueError):
                self.apply(options, seed=seed)
        with self.assertRaises(FormatError):
            apply_starter_rules(b"unknown", b"unknown", b"", b"", "seed", options)


class OriginalPalStarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        game = Path(__file__).resolve().parents[1] / "game"
        if not (game / "files/common.fsys").is_file() or not (game / "sys/main.dol").is_file():
            raise unittest.SkipTest("optional local original PAL assets unavailable")
        from colosseum_randomizer.engine.randomize_trainers import original_common
        cls.rel = original_common(game)[2]
        cls.dol = (game / "sys/main.dol").read_bytes()

    def test_real_pal_constraints_exp_and_all_disabled_identity(self):
        from colosseum_randomizer.engine.randomize_trainers import layout
        tables, _ = layout(self.rel)
        roots = base_species(self.rel, tables)
        rules = replace(Rules(), starter_balance_pair=True, starter_distinct_families=True,
                        starter_complementary_types=True, balance_species=True)
        patched, report = apply_starter_rules(self.dol, self.dol, self.rel, self.rel,
                                              "v05-real-starters", rules)
        self.assertGreater(report["valid_pair_count"], 0)
        first, second = report["pair"]
        self.assertNotEqual(first["family"], second["family"])
        self.assertFalse(set(first["types"]) & set(second["types"]))
        self.assertLessEqual(report["pair_bst_difference"], report["pair_bst_tolerance"])
        for target, row in zip(STARTERS, report["pair"]):
            pos = tables["species"]["offset"] + row["species_index"] * tables["species"]["stride"]
            self.assertEqual(u16(patched, target["base"] + 0x92),
                             experience_at_level(self.rel[pos], target["level"]))
        disabled = replace(rules, starter_umbreon=False, starter_espeon=False)
        self.assertEqual(apply_starter_rules(self.dol, self.dol, self.rel, self.rel,
                                            "v05-real-starters", disabled)[0], self.dol)
        _, base_report = apply_starter_rules(self.dol, self.dol, self.rel, self.rel,
                                             "v05-real-base", replace(rules, starter_base_forms=True))
        self.assertTrue(all(row["species_index"] in roots for row in base_report["pair"]))


if __name__ == "__main__":
    unittest.main()
