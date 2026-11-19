"""The localized HUD must be vector art over an unchanged genuine donor."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtGui import QColor, QImage
from orre_randomizer.hd_hud import (
    SOURCE_SHA256, _ERASE_RECTS, hud_origin, hud_recipes, prepare_hud_overlays, render_hud,
)


class LocalizedHud(unittest.TestCase):
    def setUp(self):
        # These fixtures exercise the original status/reformat adapters. The
        # separately pinned menu donors have their own source images/tests.
        menu_patch = patch("orre_randomizer.hd_menu_catalog.menu_recipes", return_value={})
        menu_patch.start()
        self.addCleanup(menu_patch.stop)
        self.image = QImage(1032, 80, QImage.Format.Format_RGBA8888)
        self.image.fill(QColor(31, 71, 109, 193))
        self.metadata = {"sha256": SOURCE_SHA256, "source_scale": 4, "format": "PNG"}

    def render(self, recipe):
        return render_hud(self.image, recipe["transform"], source_metadata=self.metadata)

    def test_only_verified_pal_identities_have_recipes(self):
        recipes = hud_recipes("GXXP01")
        self.assertEqual(len(recipes), 5)
        self.assertEqual({r["transform"]["language"] for r in recipes.values()}, {"en", "fr", "de", "it", "es"})
        self.assertEqual({tuple(r["transform"]["labels"]) for r in recipes.values()},
                         {("HP", "Lv."), ("PV", "N."), ("KP", "Lv."), ("PS", "L."), ("PS", "Nv.")})
        for game in ("GC6P01", "GC6E01", "GXXE01", "GXXJ01"):
            self.assertEqual(hud_recipes(game), {})
        self.assertEqual(len(hud_recipes("GC6J01")), 2)
        with self.assertRaises(ValueError):
            hud_recipes("GXXP02")

    def test_changed_native_identity_is_not_relabelled(self):
        key = next(iter(hud_recipes("GXXP01")))
        self.assertIsNotNone(hud_origin("GXXP01", key, (258, 20)))
        self.assertIsNone(hud_origin("GXXP01", key.replace("258", "259", 1), (258, 20)))
        with self.assertRaises(ValueError):
            hud_origin("GXXP01", key, (257, 20))

    def test_recipe_mutation_and_filtered_or_wrong_sources_are_rejected(self):
        recipe = next(iter(hud_recipes("GXXP01").values()))
        mutated = deepcopy(recipe["transform"])
        mutated["labels"][0] = "FAKE"
        with self.assertRaises(ValueError):
            render_hud(self.image, mutated, source_metadata=self.metadata)
        for change in ({"sha256": "0" * 64}, {"source_scale": 1}, {"source_scale": 2}):
            with self.assertRaises(ValueError):
                render_hud(self.image, recipe["transform"], source_metadata=dict(self.metadata, **change))

    def test_source_pixels_and_alpha_outside_the_two_labels_stay_exact(self):
        original = bytes(self.image.constBits())
        for recipe in hud_recipes("GXXP01").values():
            rendered, report = self.render(recipe)
            actual = bytes(rendered.constBits())
            changed = 0
            for y in range(80):
                for x in range(1032):
                    at = (y * 1032 + x) * 4
                    if original[at:at + 4] == actual[at:at + 4]:
                        continue
                    changed += 1
                    self.assertTrue(any(l * 4 <= x < (l + w) * 4 and t * 4 <= y < (t + h) * 4
                                        for l, t, w, h in _ERASE_RECTS))
            self.assertGreater(changed, 3000)
            self.assertFalse(report["native_raster_used_for_HD_art"])
            self.assertEqual(report["vector_source"]["author"], "mikeyX")
            self.assertFalse(report["runtime_validated"])
        self.assertEqual(bytes(self.image.constBits()), original)

    def test_letters_are_deterministic_vectors_without_a_font_runtime(self):
        recipes = hud_recipes("GXXP01")
        outputs = []
        with patch("PySide6.QtGui.QRawFont", side_effect=AssertionError("no font dependency")):
            for recipe in recipes.values():
                first, _ = self.render(recipe)
                second, _ = self.render(recipe)
                self.assertEqual(bytes(first.constBits()), bytes(second.constBits()))
                outputs.append(bytes(first.constBits()))
        self.assertEqual(len(set(outputs)), 5)

    def test_catalog_calls_do_not_share_mutable_recipes(self):
        first = hud_recipes("GXXP01")
        key = next(iter(first))
        first[key]["transform"]["labels"][0] = "changed"
        self.assertEqual(hud_recipes("GXXP01")[key]["transform"]["labels"][0], "HP")

    def test_controlled_reformat_reuses_every_hd_pixel_including_transparent_rgb(self):
        for key, recipe in hud_recipes("GC6J01").items():
            width, height = recipe["source_native_dimensions"]
            image = QImage(width * 4, height * 4, QImage.Format.Format_RGBA8888)
            image.fill(QColor(97, 43, 211, 0))
            metadata = {"sha256": recipe["source_sha256"], "source_scale": 4}
            actual, report = render_hud(image, recipe["transform"], source_metadata=metadata)
            self.assertEqual(bytes(actual.constBits()), bytes(image.constBits()))
            self.assertEqual(report["type"], "exact_native_reformat")
            self.assertTrue(report["proof"]["rgba_exact_after_conversion"])
            self.assertEqual(hud_origin("GC6J01", key, (width, height)), recipe)
            bad = deepcopy(recipe["transform"])
            bad["proof"]["opaque_threshold"] = 255
            with self.assertRaises(ValueError):
                render_hud(image, bad, source_metadata=metadata)

    def test_write_preflight_preserves_pack_and_existing_epoch(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "pack"
            pack.mkdir()
            destination = root / "overlays"
            destination.mkdir()
            existing_key = list(hud_recipes("GXXP01"))[2]
            (destination / existing_key).write_bytes(b"an older epoch")
            loaded = SimpleNamespace(image=self.image, metadata=self.metadata)
            with patch("orre_randomizer.hd_images.resolve_texture", return_value=pack / "source.png"), \
                 patch("orre_randomizer.hd_images.load_texture", return_value=loaded):
                with self.assertRaises(ValueError):
                    prepare_hud_overlays("GXXP01", {"xd": pack}, destination)
                self.assertEqual(list(destination.iterdir()), [destination / existing_key])
                with self.assertRaises(ValueError):
                    prepare_hud_overlays("GXXP01", {"xd": pack}, pack / "do-not-write")
                result = prepare_hud_overlays("GXXP01", {"xd": pack}, root / "new-overlays")
                self.assertEqual(len(result["files"]), 5)
                self.assertEqual(prepare_hud_overlays("GXXP01", {"xd": pack}, root / "new-overlays"), result)
            self.assertEqual(list(pack.iterdir()), [])
