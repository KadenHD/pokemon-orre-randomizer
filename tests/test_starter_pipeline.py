"""Complete Colosseum patch plans and their real preview, when a retail ISO exists.

The native tests are deliberately separate from constructor-only tests. Public
source archives skip them explicitly rather than replacing retail validators.
The developer matrix script expands this bounded subset to every starter.
"""
import hashlib
from pathlib import Path
import unittest

from scripts.validate_starter_matrix import expected_policy_rejection, plan_case, source_identity, starter_options, validate_plan

ROOT = Path(__file__).resolve().parents[1]


class StarterMatrixHarness(unittest.TestCase):
    def test_policy_exclusions_cannot_hide_unrelated_generation_errors(self):
        from orre_randomizer.engine.analyze_game import FormatError
        self.assertTrue(expected_policy_rejection("GXXP01", 292, "starter-only",
                                                 FormatError("the selected XD starter is excluded")))
        for national, preset, error in ((129, "starter-only", FormatError("the selected XD starter is excluded")),
                                        (292, "starter-only", FormatError("damaged native capture contract")),
                                        (249, "starter-only", FormatError("the selected XD starter is excluded")),
                                        (292, "starter-only", OSError("the selected XD starter is excluded"))):
            with self.subTest(national=national, preset=preset, error=error):
                self.assertFalse(expected_policy_rejection("GXXP01", national, preset, error))

    def test_complete_serialized_plan_rejects_overlap_and_out_of_bounds(self):
        for invalid in ([], [(2, b"abc"), (4, b"collision")], [(15, b"too long")], [(-1, b"invalid")]):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                validate_plan(invalid, 16)
        first = validate_plan([(2, b"abc"), (7, b"def")], 16)
        self.assertNotEqual(first, validate_plan([(2, b"abc"), (7, b"deF")], 16))
        self.assertNotEqual(first, validate_plan([(2, b"abc"), (8, b"def")], 16))

    def test_matrix_scope_keeps_modes_distinct_and_does_not_weaken_real_presets(self):
        from dataclasses import replace
        from orre_randomizer.presets import species_preset
        from orre_randomizer.xd import XDOptions
        for game in ("GC6P01", "GXXP01"):
            for word, value in (("original", False), ("natural", "natural"), ("random", True)):
                options = starter_options(game, 129, word)
                self.assertEqual(options.randomize_starter_moves, value)
                if isinstance(value, bool):
                    self.assertIs(options.randomize_starter_moves, value)
                self.assertTrue(options.allow_legendaries)
        self.assertEqual(starter_options("GC6P01", 129, "natural", "pokemon"),
                         replace(species_preset(), starter_umbreon_species=129))
        self.assertEqual(starter_options("GXXP01", 129, "natural", "pokemon"),
                         replace(XDOptions.species_only(), starter_species=129))
        self.assertEqual(starter_options("GC6P01", 0, "natural", "pokemon"), species_preset())
        self.assertEqual(starter_options("GXXP01", 0, "natural", "pokemon"), XDOptions.species_only())


class NativeColosseumStarterPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso"
        if not path.is_file():
            raise unittest.SkipTest("requires a locally retained original European Colosseum ISO")
        cls.identity = source_identity(path)

    @classmethod
    def tearDownClass(cls):
        with cls.identity["path"].open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != cls.identity["sha256"]:
            raise AssertionError("Original Colosseum image changed during read-only patch-plan tests")

    def test_reported_short_learnsets_reach_the_complete_plan_in_both_slots(self):
        for national in (129, 374, 375):
            with self.subTest(national=national):
                row = plan_case(self.identity, national, "natural", "starter-pipeline-regression")
                self.assertEqual([starter["level"] for starter in row["starters"]], [26, 25])
                self.assertEqual([starter["national"] for starter in row["starters"]], [national, national])
                if national == 129:
                    self.assertEqual([starter["moves"] for starter in row["starters"]], [[150, 33, 0, 0]] * 2)
                if national == 374:
                    self.assertEqual([starter["moves"] for starter in row["starters"]], [[36, 0, 0, 0]] * 2)

    def test_both_complete_presets_keep_the_requested_starter(self):
        for preset, mode in (("pokemon", "natural"), ("pokemon-moves", "random")):
            with self.subTest(preset=preset):
                row = plan_case(self.identity, 374, mode, "starter-preset-regression", preset)
                self.assertEqual(row["starters"][0]["national"], 374)
                self.assertEqual(len(row["starters"][0]["moves"]), 4)

    def test_real_preview_and_final_serialized_plan_have_identical_starters_and_bytes(self):
        from orre_randomizer.preview import preview_starters
        options = starter_options("GC6P01", 374, "natural")
        seed = "starter-preview-pipeline"
        final = plan_case(self.identity, 374, "natural", seed)
        prepared = []
        preview = preview_starters(self.identity["path"], seed, options, on_prepared=prepared.append)
        self.assertEqual(len(prepared), 1)
        self.assertEqual(validate_plan(prepared[0].patches, self.identity["bytes"]), final["patch_sha256"])
        for actual, expected in zip(preview["starters"], final["starters"], strict=True):
            self.assertEqual((actual["species"], actual["level"]), (expected["species"], expected["level"]))
            self.assertEqual([entry["move"] for entry in actual["details"]["moves"]],
                             [move for move in expected["moves"] if move])


if __name__ == "__main__":
    unittest.main()
