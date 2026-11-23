"""Complete XD planning/preview regressions: constructor success is not enough."""
import hashlib
from dataclasses import replace
from pathlib import Path
import unittest

from scripts.validate_starter_matrix import plan_case, source_identity, starter_options, validate_plan

ROOT = Path(__file__).resolve().parents[1]


class NativeXDStarterPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "build/xd-validation/verified-eu.iso"
        if not path.is_file():
            raise unittest.SkipTest("requires a locally retained original European XD ISO")
        cls.identity = source_identity(path)

    @classmethod
    def tearDownClass(cls):
        with cls.identity["path"].open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != cls.identity["sha256"]:
            raise AssertionError("Original XD image changed during read-only patch-plan tests")

    def test_short_learnsets_reach_the_complete_plan_without_random_moves(self):
        for national, moves in ((129, [150, 0, 0, 0]), (374, [36, 0, 0, 0]), (375, [36, 0, 0, 0])):
            with self.subTest(national=national):
                row = plan_case(self.identity, national, "natural", "starter-pipeline-regression")
                self.assertEqual(row["starters"][0]["moves"], moves)
                self.assertEqual(row["starters"][0]["level"], 10)

    def test_magikarp_reaches_both_complete_default_presets(self):
        for preset, mode in (("pokemon", "natural"), ("pokemon-moves", "random")):
            with self.subTest(preset=preset):
                row = plan_case(self.identity, 129, mode, "starter-preset-regression", preset)
                self.assertEqual(row["starters"][0]["national"], 129)
                if preset == "pokemon":
                    self.assertEqual(row["starters"][0]["moves"], [150, 0, 0, 0])

    def test_native_boolean_move_mode_reaches_the_complete_plan(self):
        row = plan_case(self.identity, 129, "original", "starter-original-regression")
        self.assertEqual(row["starters"][0]["moves"], [150, 0, 0, 0])

    def test_harden_only_starter_with_randomized_types_and_abilities_keeps_native_capture(self):
        from orre_randomizer import service
        import threading
        options = replace(starter_options("GXXP01", 11, "natural"),
                          randomize_types=True, randomize_abilities=True)
        patches, summary = service.build_xd_patches(
            self.identity["path"], self.identity["boot"], "starter-advanced-regression", options,
            lambda *_args: None, threading.Event())
        validate_plan(patches, self.identity["bytes"])
        self.assertEqual(summary["starter"]["moves"], [106, 0, 0, 0])
        self.assertEqual(summary["capture_tutorial"], {
            "battle_id": 224, "shadow_id": 1, "native_snag_only": True,
            "native_guaranteed_capture": True, "starter_attack_required": False})

    def test_real_preview_and_final_serialized_plan_have_identical_starter_and_bytes(self):
        from orre_randomizer.preview import preview_xd
        options = starter_options("GXXP01", 129, "natural")
        seed = "starter-preview-pipeline"
        final = plan_case(self.identity, 129, "natural", seed)
        prepared = []
        preview = preview_xd(self.identity["path"], seed, options, on_prepared=prepared.append)
        self.assertEqual(len(prepared), 1)
        self.assertEqual(validate_plan(prepared[0].patches, self.identity["bytes"]), final["patch_sha256"])
        actual, expected = preview["starter"], final["starters"][0]
        self.assertEqual((actual["species"], actual["level"]), (expected["species"], expected["level"]))
        self.assertEqual([entry["move"] for entry in actual["details"]["moves"]], [150])


if __name__ == "__main__":
    unittest.main()
