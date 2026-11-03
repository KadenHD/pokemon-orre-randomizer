"""Final species policies must compose with moves, properties and reports."""
from dataclasses import replace
from pathlib import Path
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError
from colosseum_randomizer.engine.evolution_rules import evolution_families
from colosseum_randomizer.engine.gameplay_rules import (MOVE_FIELDS, apply_dol_rules,
    apply_rel_rules, damaging, expanded_layout, move_catalog)
from colosseum_randomizer.engine.inspect_tables import u16
from colosseum_randomizer.engine.randomize_story import SPECIALS, experience_at_level
from colosseum_randomizer.engine.randomize_trainers import original_common
from colosseum_randomizer.engine.species_rules import LEGENDARY_NATIONAL, species_catalog
from colosseum_randomizer.options import Options
from colosseum_randomizer.service import (UserError, final_report_summary, transform_dol,
                                          transform_rel, validate_options)

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"


class V05OptionTests(unittest.TestCase):
    def test_contradictory_boss_legendary_rules_rejected_before_reading_rom(self):
        options = replace(Options.recommended(), allow_legendaries=False,
                          boss_shadow_legendary_mode="preserve")
        with self.assertRaisesRegex(UserError, "légendaires"):
            validate_options(options)
        validate_options(replace(options, randomize_shadows=False))


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires original PAL dump")
class V05CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_common(GAME)[2]
        cls.dol = (GAME / "sys/main.dol").read_bytes()
        cls.tables = expanded_layout(cls.original)
        cls.seed = "qa-colosseum-v5"
        cls.options = replace(Options.recommended(), starter_stage="base",
            boss_shadow_legendary_mode="preserve", boss_shadow_power_mode="similar",
            boss_shadow_min_bst=450, randomize_types=True, randomize_stats=True,
            preserve_stat_totals=False)
        cls.base, cls.summary = transform_rel(cls.original, cls.seed, cls.options)
        cls.rel, cls.summary["gameplay"] = apply_rel_rules(cls.original, cls.base, cls.seed, cls.options)
        cls.base_dol, cls.summary["special_changes"] = transform_dol(cls.dol, cls.original, cls.seed, cls.options)
        cls.final_dol, cls.summary["special_gameplay"] = apply_dol_rules(cls.dol, cls.base_dol,
            cls.original, cls.rel, cls.seed, cls.options)

    def test_boss_policies_sync_every_shadow_alias_before_move_generation(self):
        report = self.summary["gameplay"]["shadow_boss"]
        self.assertTrue(report["active"])
        self.assertEqual(report["distinct_family_count"], 48)
        self.assertEqual(report["boss_groups"], [19, 21, 23, 34, 38, 43, 44])
        native_catalog = species_catalog(self.original, self.tables)
        catalog = species_catalog(self.rel, self.tables)
        moves = move_catalog(self.original, self.tables)
        edits = {row["index"]: row for row in self.summary["gameplay"]["trainer_move_edits"]}
        for pick in report["picks"]:
            new = pick["new_species_index"]
            if pick["boss"]:
                self.assertGreaterEqual(native_catalog[new]["total"], 450)
                self.assertEqual(native_catalog[new]["national_dex"] in LEGENDARY_NATIONAL,
                    native_catalog[pick["old_species_index"]]["national_dex"] in LEGENDARY_NATIONAL)
            for index in pick["trainer_pokemon_indices"]:
                pos = self.tables["trainer_pokemon"]["offset"] + index * self.tables["trainer_pokemon"]["stride"]
                self.assertEqual(u16(self.rel, pos + 0xA), new)
                self.assertEqual(self.rel[pos + 4], self.original[pos + 4])
                if index in edits:
                    actual = [u16(self.rel, pos + field) for field in MOVE_FIELDS]
                    self.assertEqual(edits[index]["species"], new)
                    self.assertTrue(any(damaging(moves[m]) and moves[m]["type"] in catalog[new]["types"] for m in actual))

    def test_starter_moves_exp_and_report_follow_final_coordinated_species(self):
        catalog = species_catalog(self.rel, self.tables)
        moves = move_catalog(self.original, self.tables)
        report = final_report_summary(self.original, self.base, self.rel, self.dol,
            self.final_dol, self.seed, self.options, self.summary)
        pair = report["special_gameplay"]["starter_pair"]
        self.assertTrue(pair["applied"])
        self.assertLessEqual(pair["pair_bst_difference"], pair["pair_bst_tolerance"])
        self.assertFalse(set(pair["pair"][0]["types"]) & set(pair["pair"][1]["types"]))
        for target, row in zip(SPECIALS[:2], pair["pair"]):
            index = u16(self.final_dol, target["base"] + 2)
            self.assertEqual(index, row["species_index"])
            self.assertTrue(row["base_form"])
            self.assertEqual(u16(self.final_dol, target["base"] + 0x92),
                experience_at_level(self.rel[catalog[index]["offset"]], target["level"]))
            final = next(r for r in report["special_gameplay"]["specials"] if r["key"] == target["key"])
            self.assertEqual(final["species"], index)
            self.assertTrue(any(damaging(moves[m]) and moves[m]["type"] in catalog[index]["types"] for m in final["moves"]))

    def test_disabled_species_features_ignore_their_dependent_rules(self):
        options = replace(Options.none(), starter_balance_pair=True, starter_stage="base",
            boss_shadow_legendary_mode="preserve", boss_shadow_power_mode="similar", boss_shadow_min_bst=700)
        rel, _ = apply_rel_rules(self.original, self.original, self.seed, options)
        dol, _ = apply_dol_rules(self.dol, self.dol, self.original, rel, self.seed, options)
        self.assertEqual(rel, self.original)
        self.assertEqual(dol, self.dol)
        self.assertFalse(options.has_changes)


if __name__ == "__main__":
    unittest.main()
