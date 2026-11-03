"""Manual starter constraints and progression boundaries, without game files."""
from dataclasses import dataclass, replace
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError
from colosseum_randomizer.engine.starter_rules import apply_starter_tables
from colosseum_randomizer.engine.level_curve import encounter_level
from colosseum_randomizer.options import Options
from tests.test_starter_rules import StageRules, fixture


@dataclass(frozen=True)
class ManualRules(StageRules):
    starter_umbreon_species: int = 0
    starter_espeon_species: int = 0
    excluded_species: tuple = ()
    excluded_types: tuple = ()


class ManualStarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dol, cls.rel, cls.tables = fixture()

    def apply(self, options, seed="manual"):
        return apply_starter_tables(self.dol, self.dol, self.rel, self.rel,
                                    seed, options, self.tables)

    def test_two_manual_picks_override_stage_and_repeat_across_seeds(self):
        options = ManualRules(starter_umbreon_species=144, starter_espeon_species=25,
                              starter_stage="base", starter_three_stage_families=True)
        first, report = self.apply(options)
        other, other_report = self.apply(options, "another seed")
        self.assertEqual(first, other)
        self.assertEqual([row["national_dex"] for row in report["pair"]], [144, 25])
        self.assertTrue(all(row["manual"] for row in report["pair"]))
        self.assertEqual([row["level"] for row in other_report["pair"]], [26, 25])

    def test_one_manual_pick_still_allows_a_seeded_partner(self):
        options = ManualRules(starter_umbreon_species=144, starter_distinct_families=True)
        partners = set()
        for seed in ("one", "two", "three", "four", "five"):
            _, report = self.apply(options, seed)
            self.assertEqual(report["pair"][0]["national_dex"], 144)
            partners.add(report["pair"][1]["national_dex"])
        self.assertGreater(len(partners), 1)

    def test_filters_and_pair_rules_are_never_bypassed(self):
        for options in (
            ManualRules(starter_umbreon_species=144, allow_legendaries=False),
            ManualRules(starter_umbreon_species=252, allow_gen3=False),
            ManualRules(starter_umbreon_species=1, excluded_species=(1,)),
            ManualRules(starter_umbreon_species=1, excluded_types=(12,)),
            ManualRules(starter_umbreon_species=292),
            ManualRules(starter_umbreon_species=1, starter_espeon_species=2, starter_distinct_families=True),
        ):
            with self.subTest(options=options), self.assertRaises(FormatError):
                self.apply(options)

    def test_disabled_manual_choice_does_not_modify_a_starter(self):
        options = ManualRules(starter_umbreon=False, starter_espeon=False,
                              starter_umbreon_species=144, starter_espeon_species=25)
        output, report = self.apply(options)
        self.assertEqual(output, self.dol)
        self.assertFalse(report["applied"])


class ProgressiveLevelTests(unittest.TestCase):
    def test_original_level_tiers_round_and_cap_before_boss_bonuses(self):
        options = replace(Options.none(), progressive_levels=True,
                          early_level_multiplier=0.5, mid_level_multiplier=1.2,
                          late_level_multiplier=2.0, trainer_level_multiplier=1.8)
        expected = {1: 1, 25: 13, 35: 18, 36: 43, 50: 60, 51: 100, 100: 100}
        self.assertEqual({n: encounter_level(n, options) for n in expected}, expected)

    def test_inactive_tiers_and_neutral_curve_preserve_original_behavior(self):
        options = replace(Options.none(), early_level_multiplier=2.0,
                          mid_level_multiplier=2.0, late_level_multiplier=2.0)
        self.assertFalse(options.has_changes)
        self.assertEqual([encounter_level(n, options) for n in (20, 40, 60)], [20, 40, 60])
        neutral = replace(options, progressive_levels=True, early_level_multiplier=1.0,
                          mid_level_multiplier=1.0, late_level_multiplier=1.0,
                          trainer_level_multiplier=2.0)
        self.assertFalse(neutral.has_changes)
        self.assertEqual([encounter_level(n, neutral) for n in (20, 40, 60)], [20, 40, 60])
