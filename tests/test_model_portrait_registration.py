"""Portrait publication requires a complete reviewed set with native frames."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from orre_randomizer.artwork import _png
from orre_randomizer.hd_packs import PACKS
from orre_randomizer.model_portraits import MANIFEST, portrait_filename, violet_backdrop
from scripts.register_model_portraits import register


class PortraitRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "captures"
        self.source.mkdir()
        self.pack = self.root / "game"
        self.models = self.pack / "models"
        self.models.mkdir(parents=True)
        (self.models / "dark-lugia.png").write_bytes(b"original extraction kept")
        (self.pack / "provenance.json").write_text('{"files": {}}')
        parent = json.dumps({"source": {"hd_art_revision": 2, "hd_material_coverage": {
            "total_native_materials": 5, "exact_pack_materials": 2,
            "authored_pack_derived": 3, "derived_shiny_materials": 1, "inherited_stock": []}}}).encode()
        (self.models / "hd-fullbody-manifest.json").write_bytes(parent)
        self.data = {"schema": 1, "kind": "native-mesh-render-portrait", "review_only": False,
            "native_bitmap_upscaled_for_hd": False,
            "source": {"hd": {"pack": PACKS["xd"].key,
                "archives": [part.sha256 for part in PACKS["xd"].parts],
                "material_manifest_sha256": hashlib.sha256(parent).hexdigest()}}, "files": {}}
        for game in ("colosseum", "xd"):
            for shiny in (False, True):
                for scale in (1, 4):
                    name = portrait_filename(game, shiny, scale)
                    size = 42 * scale
                    payload = _png((size, size), violet_backdrop(game=game, scale=scale))
                    (self.source / name).write_bytes(payload)
                    self.data["files"][name] = {"game": game, "shiny": shiny, "scale": scale,
                        "dimensions": [size, size], "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest()}
        self.save()

    def save(self):
        (self.source / MANIFEST).write_text(json.dumps(self.data), encoding="utf-8")

    def assert_not_published(self):
        self.assertFalse((self.models / MANIFEST).exists())
        self.assertEqual(json.loads((self.pack / "provenance.json").read_text()), {"files": {}})
        self.assertEqual((self.models / "dark-lugia.png").read_bytes(), b"original extraction kept")

    def test_reviewed_set_updates_allowlist_and_keeps_the_original_extraction(self):
        register(self.source, self.pack, check_only=True)
        self.assert_not_published()
        register(self.source, self.pack)
        catalogue = json.loads((self.pack / "provenance.json").read_text())
        self.assertEqual(len(catalogue["files"]), 9)
        for name, record in catalogue["files"].items():
            payload = (self.pack / name).read_bytes()
            self.assertEqual(len(payload), record["bytes"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])
        self.assertEqual((self.models / "dark-lugia.png").read_bytes(), b"original extraction kept")

    def test_draft_or_changed_parent_is_rejected_before_any_write(self):
        self.data["review_only"] = True
        self.save()
        with self.assertRaises(ValueError):
            register(self.source, self.pack)
        self.assert_not_published()
        self.data["review_only"] = False
        self.data["source"]["hd"]["material_manifest_sha256"] = "0" * 64
        self.save()
        with self.assertRaises(ValueError):
            register(self.source, self.pack)
        self.assert_not_published()

    def test_corrupt_file_does_not_publish_a_partial_set(self):
        name = portrait_filename("xd", True, 4)
        (self.source / name).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            register(self.source, self.pack)
        self.assert_not_published()

    def test_private_capture_paths_cannot_enter_the_public_registry(self):
        self.data["source"]["private_reference"] = "C:/Users/example/private-save.raw"
        self.save()
        with self.assertRaisesRegex(ValueError, "Private"):
            register(self.source, self.pack)
        self.assert_not_published()

    def test_native_xd_palette_overflow_is_rejected_before_rom_creation(self):
        name = portrait_filename("xd", False, 1)
        pixels = bytearray(violet_backdrop(game="xd", scale=1))
        for y in range(42):
            for x in range(42):
                at = (y * 42 + x) * 4
                if pixels[at + 3]:
                    pixels[at:at + 3] = bytes(((x % 32) * 8, (y % 32) * 8, 96))
        payload = _png((42, 42), pixels)
        (self.source / name).write_bytes(payload)
        self.data["files"][name].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        self.save()
        with self.assertRaisesRegex(ValueError, "CI8 palette"):
            register(self.source, self.pack)
        self.assert_not_published()

    def test_square_and_round_backdrops_keep_the_game_specific_alpha(self):
        self.assertEqual(violet_backdrop(game="colosseum", scale=1)[3::4], bytes((255,)) * 42 * 42)
        native = violet_backdrop(game="xd", scale=1)
        self.assertEqual(native[3::4].count(255), 1520)
        self.assertEqual(native[:4], bytes(4))
        hd = violet_backdrop(game="xd", scale=4)
        self.assertTrue(any(0 < alpha < 255 for alpha in hd[3::4]))
        self.assertTrue(all(not any(hd[at:at + 3]) for at in range(0, len(hd), 4) if not hd[at + 3]))


if __name__ == "__main__":
    unittest.main()
