"""Move-policy fixtures and optional original-PAL composition checks.

These tests never write a disc or run an emulator. Synthetic cases cover the
choice logic without game assets; local integration checks actual field masks.
"""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.engine.gameplay_rules import (
    MOVE_FIELDS, OHKO, SELF_DESTRUCT, USEFUL_ITEMS, apply_dol_rules, apply_rel_rules,
    apply_story_rules, choose_moves, damaging, expanded_layout, move_catalog)
from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL, species_catalog
from orre_randomizer.options import Options
from orre_randomizer.service import UserError, validate_options


def synthetic_moves():
    # The ID is intentionally independent of type/power except for protected
    # native effect IDs, making policy failures easy to distinguish.
    definitions = {
        10: (0, 35), 11: (11, 40), 13: (11, 20), 14: (10, 30),
        15: (12, 0), 16: (11, 0), 17: (13, 25), 18: (11, 100),
        19: (0, 250), 20: (7, 80), 21: (7, 120),
        12: (0, 1), 32: (0, 1), 90: (4, 1), 329: (15, 1),
        120: (0, 200), 153: (0, 250), 69: (1, 1), 101: (7, 1),
    }
    return {index: {"index": index, "type": kind, "power": power, "pp": 20,
                    "accuracy": 100, "effect": 0}
            for index, (kind, power) in definitions.items()}


class MoveChoiceTests(unittest.TestCase):
    def setUp(self):
        self.moves = synthetic_moves()
        self.species = {"types": (11, 11), "stats": (50, 40, 50, 100, 50, 50)}

    def test_balanced_guards_and_seed_reproduction(self):
        options = Options()
        actual = choose_moves("été-seed", "fixture", self.species, 5, self.moves, options)
        self.assertEqual(choose_moves("été-seed", "fixture", self.species, 5, self.moves, options), actual)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertTrue(any(damaging(self.moves[i]) for i in actual))
        self.assertTrue(any(damaging(self.moves[i]) and self.moves[i]["type"] == 11 for i in actual))
        self.assertTrue(all(self.moves[i]["power"] <= 40 for i in actual))
        self.assertFalse(set(actual) & (SELF_DESTRUCT | OHKO))

    def test_chaos_really_allows_power_and_explicitly_unbanned_moves(self):
        options = replace(Options.none(), moves_mode="chaos", no_duplicate_moves=True)
        unrestricted = {i: self.moves[i] for i in (12, 120, 153, 329)}
        actual = choose_moves("chaos", "fixture", self.species, 1, unrestricted, options)
        self.assertEqual(set(actual), set(unrestricted))
        self.assertTrue(any(self.moves[i]["power"] > 120 for i in actual))

    def test_used_moves_and_duplicates_are_excluded(self):
        options = replace(Options.none(), moves_mode="chaos", no_duplicate_moves=True)
        used = {10, 11, 13}
        actual = choose_moves("seed", "used", self.species, 20, self.moves, options, count=4, used=used)
        self.assertFalse(set(actual) & used)
        self.assertEqual(len(set(actual)), 4)

    def test_duplicates_can_be_allowed(self):
        options = replace(Options.none(), moves_mode="chaos")
        actual = choose_moves("seed", "duplicate", self.species, 20, {10: self.moves[10]}, options)
        self.assertEqual(actual, [10] * 4)

    def test_stab_guard_can_use_the_weakest_available_move_above_ceiling(self):
        species = {**self.species, "types": (7, 7)}
        options = Options()
        actual = choose_moves("seed", "ghost", species, 1, self.moves, options)
        # Night Shade has fixed level damage and raw power1, so it counts as
        # offensive. Either it or a weakest safe Ghost option fulfils the guard.
        self.assertTrue(damaging(self.moves[actual[0]]))
        self.assertEqual(self.moves[actual[0]]["type"], 7)

    def test_missing_required_type_errors_instead_of_silently_dropping_guard(self):
        species = {**self.species, "types": (8, 8)}
        with self.assertRaises(FormatError):
            choose_moves("seed", "no-stab", species, 5, self.moves, Options())


class GameplayOptionValidationTests(unittest.TestCase):
    def test_numeric_bounds_nan_infinity_and_wrong_types(self):
        bad_values = {
            "trainer_level_multiplier": (0.49, 2.01, float("nan"), float("inf"), -float("inf"), True, "1.0"),
            "capture_rate_multiplier": (0.24, 5.01, float("nan"), float("inf"), -float("inf"), False, "1.0"),
            "minimum_catch_rate": (-1, 256, 1.0, 1.5, float("nan"), float("inf"), True, "10"),
        }
        for name, values in bad_values.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(UserError):
                    validate_options(replace(Options(), **{name: value}))

    def test_boundary_values_and_unknown_mode(self):
        for options in (replace(Options(), trainer_level_multiplier=0.5, capture_rate_multiplier=0.25, minimum_catch_rate=0),
                        replace(Options(), trainer_level_multiplier=2.0, capture_rate_multiplier=5.0, minimum_catch_rate=255)):
            self.assertEqual(validate_options(options), options)
        with self.assertRaises(UserError):
            validate_options(replace(Options(), moves_mode="unknown"))

    def test_generation_none_rejected_only_when_species_are_randomized(self):
        for flag in ("randomize_trainers", "randomize_shadows", "starter_umbreon", "gift_plusle"):
            with self.subTest(flag=flag), self.assertRaises(UserError):
                validate_options(replace(Options.none(), **{flag: True}))
        options = replace(Options.none(), randomize_trainer_moves=True)
        self.assertEqual(validate_options(options), options)


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires user's original local PAL image")
class PalGameplayIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from orre_randomizer.engine.randomize_trainers import original_common, randomize_rel
        from orre_randomizer.service import transform_rel, transform_dol
        cls.original = original_common(GAME)[2]
        cls.dol = (GAME / "sys/main.dol").read_bytes()
        cls.seed = "qa-colosseum-v1"
        cls.tables = expanded_layout(cls.original)
        cls.moves = move_catalog(cls.original, cls.tables)
        cls.rows = randomize_rel(cls.original, cls.seed)[1]["trainer_pokemon_changes"]
        cls.shadow_rows = randomize_rel(cls.original, cls.seed)[1]["shadow_changes"]
        cls.legacy = replace(Options(), starter_stage="any", starter_three_stage_families=False,
                             accessible_event_gifts=False)
        cls.base = transform_rel(cls.original, cls.seed, cls.legacy)[0]
        cls.base_dol = transform_dol(cls.dol, cls.original, cls.seed, cls.legacy)[0]
        cls.options = replace(Options.recommended(), randomize_types=True, randomize_abilities=True,
            randomize_stats=True, randomize_held_items=True, allow_gen1=False, allow_gen2=False,
            allow_legendaries=False, trainer_level_multiplier=2.0,
            capture_rate_multiplier=5.0, minimum_catch_rate=200)
        cls.result, cls.report = apply_rel_rules(cls.original, cls.base, cls.seed, cls.options)
        cls.final_catalog = species_catalog(cls.result, cls.tables)

    def test_legacy_advanced_off_preserves_base_rel_and_dol(self):
        result, report = apply_rel_rules(self.original, self.base, self.seed, self.legacy)
        self.assertEqual(result, self.base)
        dol, summary = apply_dol_rules(self.dol, self.base_dol, self.original, result, self.seed, self.legacy)
        self.assertEqual(dol, self.base_dol)
        self.assertFalse(summary["gift_move_hooks"]["enabled"])
        self.assertEqual(report["learnset_edits"], [])

    def test_plusle_keeps_its_draw_with_large_species_allowed(self):
        from orre_randomizer.service import transform_dol

        options = replace(Options.none(), gift_plusle=True, allow_gen1=True, allow_gen2=True, allow_gen3=True)
        for seed, allow_legendaries, expected in (
            ("pyrite-scene-600", False, 321),
            ("pyrite-scene-17", False, 94),
            ("pyrite-unfiltered-312", True, 321),
        ):
            with self.subTest(seed=seed):
                settings = replace(options, allow_legendaries=allow_legendaries)
                base, changes = transform_dol(self.dol, self.original, seed, settings)
                if allow_legendaries:
                    self.assertEqual(changes[0]["new_species_index"], 314)
                result, summary = apply_dol_rules(self.dol, base, self.original, self.original, seed, settings)
                gift = next(row for row in summary["specials"] if row["key"] == "plusle")
                self.assertEqual(gift["level"], 13)
                national_dex = self.final_catalog[gift["species"]]["national_dex"]
                self.assertEqual(national_dex, expected)
                self.assertEqual(apply_dol_rules(self.dol, base, self.original, self.original, seed, settings)[0], result)

    def test_plusle_family_pool_can_choose_wailord(self):
        options = replace(Options.none(), gift_plusle=True, diverse_story_families=True,
                          allow_gen3=True, excluded_species=tuple(i for i in range(1, 387) if i != 321))
        _, _, _, gifts = apply_story_rules(self.original, self.original, self.dol, self.dol, self.seed, options)
        self.assertEqual(self.final_catalog[gifts["plusle"]]["national_dex"], 321)

    def test_plusle_can_draw_from_a_pool_with_only_wailord(self):
        options = replace(Options.none(), gift_plusle=True, allow_gen3=True,
                          excluded_species=tuple(i for i in range(1, 387) if i != 321))
        _, report = apply_dol_rules(self.dol, self.dol, self.original, self.original, self.seed, options)
        gift = next(row for row in report["specials"] if row["key"] == "plusle")
        self.assertEqual(self.final_catalog[gift["species"]]["national_dex"], 321)

    def test_thirty_special_records_and_every_nonmove_subrecord_byte_survive(self):
        protected = set(self.report["protected_move_records"])
        self.assertEqual(len(protected), 30)
        for row in self.rows:
            pos = row["offset"]
            for field in MOVE_FIELDS:
                block = pos + field - 6
                if row["index"] in protected:
                    self.assertEqual(self.result[block:block + 8], self.original[block:block + 8])
                else:
                    self.assertEqual(self.result[block:block + 6], self.original[block:block + 6])
                    self.assertIn(struct.unpack_from(">H", self.result, pos + field)[0], self.moves)

    def test_every_randomized_team_has_damage_stab_and_unique_moves(self):
        for change in self.report["trainer_move_edits"]:
            moves = change["after"]
            meta = self.final_catalog[change["species"]]
            self.assertEqual(len(set(moves)), 4)
            self.assertFalse(set(moves) & (SELF_DESTRUCT | OHKO))
            self.assertTrue(any(damaging(self.moves[i]) for i in moves))
            self.assertTrue(any(damaging(self.moves[i]) and self.moves[i]["type"] in meta["types"] for i in moves))

    def test_learnsets_keep_level_padding_and_have_stab_in_every_four(self):
        edits = {(row["species"], row["slot"]): row for row in self.report["learnset_edits"]}
        self.assertGreater(len(edits), 3000)
        for index, meta in self.final_catalog.items():
            learned = []
            for slot in range(19):
                pos = meta["offset"] + 0xBA + slot * 4
                self.assertEqual(self.result[pos:pos + 2], self.original[pos:pos + 2])
                if (index, slot) in edits:
                    move = struct.unpack_from(">H", self.result, pos + 2)[0]
                    self.assertIn(move, self.moves)
                    learned.append(move)
                else:
                    self.assertEqual(self.result[pos + 2:pos + 4], self.original[pos + 2:pos + 4])
            self.assertEqual(len(learned), len(set(learned)))
            for start in range(max(0, len(learned) - 3)):
                window = learned[start:start + 4]
                self.assertTrue(any(damaging(self.moves[i]) and self.moves[i]["type"] in meta["types"] for i in window))

    def test_restricted_species_pool_and_unique_shadow_families(self):
        from orre_randomizer.engine.evolution_rules import evolution_families
        families = evolution_families(self.original, self.tables)[0]
        for row in self.rows:
            index = struct.unpack_from(">H", self.result, row["offset"] + 0xA)[0]
            national = self.final_catalog[index]["national_dex"]
            self.assertGreaterEqual(national, 252)
            self.assertNotIn(national, LEGENDARY_NATIONAL)
            self.assertNotEqual(national, 292)
        picks = [struct.unpack_from(">H", self.result, row["offset"])[0] for row in self.shadow_rows]
        self.assertEqual(len({families[i] for i in picks}), 48)

    def test_levels_capture_and_useful_items_stay_in_bounds(self):
        for row in self.rows:
            pos = row["offset"]
            self.assertEqual(self.result[pos + 4], min(100, self.original[pos + 4] * 2))
            old_item = struct.unpack_from(">H", self.original, pos + 0x12)[0]
            actual_item = struct.unpack_from(">H", self.result, pos + 0x12)[0]
            if old_item in (0, 0xFFFF):
                self.assertEqual(actual_item, old_item)
            else:
                self.assertIn(actual_item, USEFUL_ITEMS)
        shadow = self.tables["shadow"]
        for row in self.shadow_rows:
            pos = shadow["offset"] + row["shadow_id"] * shadow["stride"]
            self.assertEqual(self.result[pos], min(255, max(200, self.original[pos] * 5)))
        self.assertTrue(any(self.result[row["offset"] + 4] == 100 for row in self.rows))

    def test_starting_moves_and_gift_hooks_use_final_species_and_preserve_exp(self):
        from orre_randomizer.engine.randomize_story import SPECIALS, experience_at_level
        result, summary = apply_dol_rules(self.dol, self.base_dol, self.original, self.result,
                                          self.seed, self.options)
        self.assertGreater(len(result), len(self.dol))
        parse_dol(result)
        self.assertEqual(len(summary["gift_move_hooks"]["gift_hooks"]), 4)
        for target, special in zip(SPECIALS, summary["specials"]):
            expected_level = {"pikachu-event": 30, "celebi-event": 45}.get(target["key"], target["level"])
            self.assertEqual(struct.unpack_from(">H", result, target["base"] + 6)[0], expected_level)
            self.assertTrue(special["moves"])
            self.assertFalse(set(special["moves"]) & (SELF_DESTRUCT | OHKO))
            self.assertEqual(len(set(special["moves"])), 4)
            species = self.final_catalog[special["species"]]
            self.assertTrue(any(damaging(self.moves[i]) and self.moves[i]["type"] in species["types"] for i in special["moves"]))
            if "xp" in target:
                actual_exp = struct.unpack_from(">H", result, target["base"] + 0x92)[0]
                self.assertEqual(actual_exp, experience_at_level(self.original[species["offset"]], target["level"]))

    def test_gift_moves_off_does_not_inherit_randomized_global_learnsets(self):
        from orre_randomizer.engine.randomize_story import SPECIALS
        options = replace(self.options, randomize_gift_moves=False)
        result, summary = apply_dol_rules(self.dol, self.base_dol, self.original, self.result, self.seed, options)
        hooks = {row["key"]: row for row in summary["gift_move_hooks"]["gift_hooks"]}
        for target, special in zip(SPECIALS, summary["specials"]):
            if "xp" in target:
                continue
            native = []
            pos = self.final_catalog[special["species"]]["offset"]
            for slot in range(19):
                level = self.original[pos + 0xBA + slot * 4]
                move = struct.unpack_from(">H", self.original, pos + 0xBC + slot * 4)[0]
                if level and level <= special["level"] and move in self.moves:
                    if move in native:
                        native.remove(move)
                    native.append(move)
            native = native[-4:]
            expected = native + [0] * (4 - len(native))
            self.assertEqual(special["moves_source"], "original-species-learnset-preserved")
            self.assertEqual(hooks[target["key"]]["moves"], expected)

    def test_accessible_event_gift_levels_keep_met_level_and_only_change_two_pairs(self):
        from orre_randomizer.engine.randomize_story import SPECIALS
        options = replace(Options.none(), accessible_event_gifts=True,
                          event_pikachu_level=17, event_celebi_level=63)
        result, summary = apply_dol_rules(self.dol, self.dol, self.original,
                                         self.original, self.seed, options)
        allowed = set()
        expected_levels = {"pikachu-event": 17, "celebi-event": 63}
        for target in SPECIALS:
            if target["key"] not in expected_levels:
                continue
            for field in (6, 0x3A):
                offset = target["base"] + field
                self.assertEqual(struct.unpack_from(">H", result, offset)[0], expected_levels[target["key"]])
                allowed.update((offset, offset + 1))
        changed = {i for i, (before, after) in enumerate(zip(self.dol, result, strict=True)) if before != after}
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        disabled = replace(options, accessible_event_gifts=False)
        self.assertEqual(apply_dol_rules(self.dol, self.dol, self.original,
                                         self.original, self.seed, disabled)[0], self.dol)


if __name__ == "__main__":
    unittest.main()
