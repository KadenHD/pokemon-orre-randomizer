from dataclasses import fields, replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.options import Options, SPECIAL_OPTIONS
from orre_randomizer.service import transform_dol, transform_rel, validate_options, UserError


class OptionValidationTests(unittest.TestCase):
    def test_typed_options_and_empty_preset(self):
        self.assertEqual(len(fields(Options)), 83)
        self.assertTrue(all(type(getattr(Options(), f.name)) is bool for f in fields(Options) if f.metadata["kind"] == "bool"))
        self.assertFalse(Options.none().has_changes)
        self.assertTrue(Options.recommended().has_changes)
        for options in (Options(), Options.recommended()):
            self.assertEqual(options.starter_stage, "base")
            self.assertTrue(options.starter_three_stage_families)
            self.assertTrue(options.accessible_event_gifts)
        self.assertEqual(Options.none().starter_stage, "any")
        self.assertFalse(Options.none().starter_three_stage_families)
        self.assertFalse(Options.none().accessible_event_gifts)

    def test_event_access_alone_is_a_change_and_numeric_fields_are_strict(self):
        base = Options.none()
        self.assertTrue(replace(base, accessible_event_gifts=True).has_changes)
        self.assertFalse(replace(base, event_pikachu_purifications=0,
                                 event_celebi_purifications=48, event_pikachu_level=100,
                                 event_celebi_level=1).has_changes)
        for field, valid, invalid in (
            ("event_pikachu_purifications", (0, 10, 48), (-1, 49, True, 1.5)),
            ("event_celebi_purifications", (0, 25, 48), (-1, 49, True, 1.5)),
            ("event_pikachu_level", (1, 30, 100), (0, 101, True, 1.5)),
            ("event_celebi_level", (1, 45, 100), (0, 101, True, 1.5)),
        ):
            for value in valid:
                with self.subTest(field=field, value=value):
                    self.assertEqual(getattr(validate_options(replace(base, **{field: value})), field), value)
            for value in invalid:
                with self.subTest(field=field, value=value), self.assertRaises(UserError):
                    validate_options(replace(base, **{field: value}))

    def test_stone_evolutions_require_a_shop(self):
        for name in ("evolve_trade_items", "evolve_coquiperl", "evolve_day_night"):
            options = replace(Options.none(), **{name: True})
            with self.assertRaises(UserError):
                validate_options(options)
            self.assertEqual(validate_options(replace(options, stones_pyrite=True)).stone_shops, (5,))

    def test_non_boolean_values_refused_and_shadow_option_normalized(self):
        with self.assertRaises(UserError):
            validate_options(replace(Options(), starter_umbreon="false"))
        self.assertFalse(validate_options(replace(Options(), randomize_shadows=False)).unique_shadows)


GAME = Path(__file__).resolve().parents[1] / "game"


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires user's original PAL dump")
class SelectiveIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from orre_randomizer.engine.randomize_trainers import original_common, layout
        cls.original = original_common(GAME)[2]
        cls.tables = layout(cls.original)[0]
        cls.dol = (GAME / "sys/main.dol").read_bytes()
        cls.seed = "qa-colosseum-v1"

    def test_default_data_is_identical_to_validated_v3(self):
        from orre_randomizer.engine.randomize_accessible import randomize_accessible_rel, randomize_accessible_dol
        self.assertEqual(transform_rel(self.original, self.seed, Options())[0], randomize_accessible_rel(self.original, self.seed)[0])
        self.assertEqual(transform_dol(self.dol, self.original, self.seed, Options())[0], randomize_accessible_dol(self.dol, self.original, self.seed)[0])

    def test_everything_off_preserves_rel_and_dol_exactly(self):
        rel, summary = transform_rel(self.original, self.seed, Options.none())
        dol, gifts = transform_dol(self.dol, self.original, self.seed, Options.none())
        self.assertEqual(rel, self.original)
        self.assertEqual(dol, self.dol)
        self.assertEqual(summary["trainers"]["trainer_pokemon_records_changed"], 0)
        self.assertEqual(gifts, [])

    def test_trainers_and_shadows_are_independent(self):
        from orre_randomizer.engine.randomize_trainers import randomize_rel
        plan = randomize_rel(self.original, self.seed)[1]
        for shadows in (False, True):
            options = replace(Options.none(), randomize_trainers=not shadows, randomize_shadows=shadows, unique_shadows=shadows)
            rel, summary = transform_rel(self.original, self.seed, options)
            for change in plan["trainer_pokemon_changes"]:
                pos = change["offset"]
                if bool(change["shadow_id"]) == shadows:
                    self.assertNotEqual(rel[pos:pos + 80], self.original[pos:pos + 80])
                else:
                    self.assertEqual(rel[pos:pos + 80], self.original[pos:pos + 80])
            self.assertEqual(summary["trainers"]["shadow_groups_changed"], 48 if shadows else 0)
            if shadows:
                self.assertEqual(summary["shadow_families"]["final_distinct_family_count"], 48)

    def test_six_specials_can_each_be_randomized_alone(self):
        for key, flag in SPECIAL_OPTIONS.items():
            with self.subTest(flag=flag):
                result, changes = transform_dol(self.dol, self.original, self.seed, replace(Options.none(), **{flag: True}))
                self.assertEqual([c["key"] for c in changes], [key])
                allowed = set()
                for field in ("species_field_offset", "exp_field_offset"):
                    if field in changes[0]:
                        pos = changes[0][field]
                        allowed.update((pos, pos + 1))
                actual = {i for i, (a, b) in enumerate(zip(self.dol, result)) if a != b}
                self.assertTrue(actual)
                self.assertLessEqual(actual, allowed)

    def test_five_evolution_groups_are_independent(self):
        from orre_randomizer.engine.evolution_rules import patch_evolutions, evolution_families
        full = patch_evolutions(self.original, self.tables)[1]
        families = evolution_families(self.original, self.tables)
        for name, count in (("trade", 4), ("trade_items", 6), ("coquiperl", 2), ("day_night", 2), ("beauty", 1)):
            with self.subTest(group=name):
                rel, summary = transform_rel(self.original, self.seed, replace(Options.none(), **{"evolve_" + name: True}))
                self.assertEqual(summary["evolution_edits"], count)
                self.assertEqual(evolution_families(rel, self.tables), families)
                changed = 0
                for edit in full["edits"]:
                    pos = edit["record_offset"]
                    changed += rel[pos:pos + 6] != self.original[pos:pos + 6]
                self.assertEqual(changed, count)

    def test_shops_are_independent_and_original_stock_preserved(self):
        from collections import Counter
        from orre_randomizer.engine.analyze_game import parse_fsys
        from orre_randomizer.engine.rebuild_iso import decoded_member
        from orre_randomizer.engine.shop_stones import patch_rel, STONE_IDS
        archive = (GAME / "files/pocket_menu.fsys").read_bytes()
        original = decoded_member(archive, parse_fsys(archive)["members"][0])
        for shops in ((3,), (5,), (3, 5)):
            _, plan = patch_rel(original, shops)
            self.assertEqual(plan["shops_receiving_stones"], list(shops))
            for before, after in zip(plan["before"], plan["after"]):
                expected = Counter(before["items"]) + (Counter(STONE_IDS) if before["index"] in shops else Counter())
                self.assertEqual(Counter(after["items"]), expected)


if __name__ == "__main__":
    unittest.main()
