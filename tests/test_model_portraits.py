"""Registered portraits cannot drift across game, variant or source integrity."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from orre_randomizer.artwork import _png
from orre_randomizer.model_portraits import MANIFEST, portrait_filename, registered_portrait


class ModelPortraitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"schema": 1, "files": {}}

    def install(self, game="xd", shiny=False, scale=1):
        name = portrait_filename(game, shiny, scale)
        size = 42 * scale
        payload = _png((size, size), bytes((64, 24, 80, 255)) * size * size)
        (self.root / name).write_bytes(payload)
        self.manifest["files"][name] = {"game": game, "shiny": shiny, "scale": scale,
            "dimensions": [size, size], "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}
        self.publish()
        return name, payload

    def publish(self):
        (self.root / MANIFEST).write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_missing_optional_set_is_distinct_from_corruption(self):
        self.assertIsNone(registered_portrait(self.root, game="xd"))
        (self.root / MANIFEST).write_text("not json")
        with self.assertRaises(ValueError):
            registered_portrait(self.root, game="xd")

    def test_all_eight_variants_retain_distinct_fixed_names_and_dimensions(self):
        names = set()
        for game in ("colosseum", "xd"):
            for shiny in (False, True):
                for scale in (1, 4):
                    name, payload = self.install(game, shiny, scale)
                    names.add(name)
                    self.assertEqual(registered_portrait(self.root, game=game, shiny=shiny, scale=scale), payload)
        self.assertEqual(len(names), 8)

    def test_tampered_pixels_and_wrong_variant_fail_instead_of_falling_back(self):
        name, payload = self.install()
        (self.root / name).write_bytes(payload + b"changed")
        with self.assertRaisesRegex(ValueError, "integrity"):
            registered_portrait(self.root, game="xd")
        (self.root / name).write_bytes(payload)
        self.manifest["files"][name]["shiny"] = True
        self.publish()
        with self.assertRaisesRegex(ValueError, "metadata"):
            registered_portrait(self.root, game="xd")

    def test_review_candidates_cannot_replace_installed_portraits(self):
        self.install()
        self.manifest["review_only"] = True
        self.publish()
        with self.assertRaisesRegex(ValueError, "visual review"):
            registered_portrait(self.root, game="xd")

    def test_manifest_cannot_supply_an_outside_path_or_wrong_resolution(self):
        name, _ = self.install()
        self.manifest["files"]["../outside.png"] = self.manifest["files"].pop(name)
        self.publish()
        with self.assertRaises(ValueError):
            registered_portrait(self.root, game="xd")
        self.install()
        self.manifest["files"][name]["dimensions"] = [168, 168]
        self.publish()
        with self.assertRaises(ValueError):
            registered_portrait(self.root, game="xd")

    def test_invalid_arguments_are_rejected_before_filesystem_access(self):
        for arguments in (("other", False, 1), ("xd", 1, 1), ("xd", False, True), ("xd", False, 2)):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                portrait_filename(*arguments)


if __name__ == "__main__":
    unittest.main()
