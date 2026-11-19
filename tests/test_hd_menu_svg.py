"""Real author geometry survives; native raster guides cannot reach the output."""
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QGuiApplication
from orre_randomizer.hd_menu_svg import render_background


class MenuSvgAuthoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def render(self, source, **kwargs):
        return render_background(source, expected_sha256=hashlib.sha256(source).hexdigest(),
                                 native_size=(8, 4), **kwargs)

    def test_only_real_vector_geometry_survives_explicit_guide_removal(self):
        source = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">
          <g id="native-guide"><image href="data:image/png;base64,AAA" width="8" height="4"/></g>
          <rect id="real-shape" x="1" y="1" width="6" height="2" fill="#10a0f0"/>
          <text x="1" y="2" font-family="Missing System Font">Caption removed</text>
        </svg>'''
        output, receipt = self.render(source, remove_ids=("native-guide",))
        self.assertEqual((output.width(), output.height()), (32, 16))
        self.assertEqual(output.pixelColor(8, 8), QColor(16, 160, 240))
        self.assertEqual(output.pixelColor(0, 0).alpha(), 0)
        self.assertFalse(receipt["native_bitmap_resampled"])
        self.assertFalse(receipt["font_rendering_remaining"])
        self.assertEqual(receipt["raster_images_remaining"], 0)
        with self.assertRaisesRegex(ValueError, "Non-vector.*image"):
            self.render(source, remove_ids=())

    def test_external_references_unreviewed_layout_and_unknown_removal_fail_closed(self):
        for element in (b'<use href="file:///private.png"/>',
                        b'<rect width="8" height="4" fill="url(https://external/image)"/>',
                        b'<filter id="unsupported"/>', b'<script>untrusted()</script>'):
            source = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">' + element + b'</svg>'
            with self.assertRaises(ValueError):
                self.render(source, remove_ids=())
        source = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4"/>'
        with self.assertRaisesRegex(ValueError, "missing"):
            self.render(source, remove_ids=("unknown",))
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            render_background(source, expected_sha256="altered", native_size=(8, 4), remove_ids=())
        with self.assertRaisesRegex(ValueError, "canvas"):
            render_background(source, expected_sha256=hashlib.sha256(source).hexdigest(),
                              native_size=(4, 8), remove_ids=())

    def test_geometry_additions_reproduce_without_native_rasters_or_system_fonts(self):
        from scripts.build_hd_geometry_additions import reproduce
        with TemporaryDirectory() as temporary, patch("PIL.Image.Image.save",
                side_effect=AssertionError("Reproduction must not depend on the platform PNG encoder")):
            receipt = reproduce(Path(temporary) / "new")
        self.assertEqual(len(receipt["outputs"]), 7)
        self.assertFalse(receipt["source_ROM_opened"])
        self.assertTrue(all(r["source_scale"] == 4 and not r["native_bitmap_resampled"]
                            and not r["font_rendering_remaining"]
                            and r["raster_images_remaining"] == 0
                            for r in receipt["outputs"]))

    def test_reproduction_rejects_a_single_wrong_pixel_before_canonical_png_publication(self):
        from scripts.build_hd_geometry_additions import reproduce
        original = render_background
        def changed(*args, **kwargs):
            image, metadata = original(*args, **kwargs)
            image.setPixelColor(0, 0, QColor(255, 0, 255, 255))
            return image, metadata
        with TemporaryDirectory() as temporary, patch(
                "orre_randomizer.hd_menu_svg.render_background", side_effect=changed):
            output = Path(temporary) / "changed"
            with self.assertRaisesRegex(ValueError, "Geometry pixels differ"):
                reproduce(output)
            self.assertEqual(list(output.iterdir()), [])

    def test_xd_command_panels_keep_their_translucent_centers_and_separate_cap(self):
        from orre_randomizer.hd_menu_catalog import menu_image, menu_recipes
        key = "tex1_112x74_c0a04eab9ac90631_50d5715452d09e56_8.png"
        for game in ("GXXE01", "GXXP01", "GXXJ01"):
            row = menu_recipes(game)[key]
            image = menu_image(row["bundled_donor"], (112, 74)).image
            # Qt's SVG opacity quantizes once before straight-RGBA export.
            self.assertAlmostEqual(image.pixelColor(40 * 4, 36 * 4).alpha(), 146, delta=1)
            self.assertEqual(image.pixelColor(12 * 4, 36 * 4).alpha(), 255)
            self.assertEqual(image.pixelColor(76 * 4, 50 * 4).alpha(), 0)
            self.assertEqual(image.pixelColor(103 * 4, 12 * 4).alpha(), 255)

    def test_unknown_species_icon_stays_circular_in_each_xd_region(self):
        from orre_randomizer.hd_menu_catalog import menu_image, menu_recipes
        key = "tex1_64x64_b0ae7e7c04406d86_6373c39a87ff6ec0_8.png"
        for game in ("GXXE01", "GXXP01", "GXXJ01"):
            row = menu_recipes(game)[key]
            image = menu_image(row["bundled_donor"], (64, 64)).image
            self.assertEqual((image.width(), image.height()), (256, 256))
            self.assertEqual(image.pixelColor(8 * 4, 8 * 4).alpha(), 0)
            self.assertAlmostEqual(image.pixelColor(32 * 4, 10 * 4).alpha(), 182, delta=1)
            self.assertEqual(image.pixelColor(5 * 4, 32 * 4).alpha(), 0)

    def test_warning_pages_keep_each_original_language_line_layout_and_opaque_background(self):
        from scripts.build_hd_geometry_additions import reproduce, SOURCES
        from orre_randomizer.hd_menu_catalog import _asset, menu_image, menu_recipes
        packet, _ = _asset(SOURCES["warnings"])
        self.assertEqual({r["language"] for r in packet["records"]}, {"en", "fr", "de", "es", "it"})
        with TemporaryDirectory() as temporary:
            receipt = reproduce(Path(temporary) / "warnings", source=SOURCES["warnings"])
        self.assertEqual(len(receipt["outputs"]), 5)
        for row in packet["records"]:
            recipe = menu_recipes("GXXP01")[row["target"]]
            self.assertNotIn(row["target"], menu_recipes("GXXE01"))
            self.assertNotIn(row["target"], menu_recipes("GXXJ01"))
            image = menu_image(recipe["bundled_donor"], (608, 448)).image
            self.assertEqual((image.width(), image.height()), (2432, 1792))
            self.assertEqual(image.pixelColor(0, 0), QColor(0, 0, 0, 255))
            url = row["labels"][-1]
            self.assertEqual(url["text"], "www.nintendo-europe.com/consumerinformation/")
            # Palette-colour antialias pixels above the URL must not expand its
            # measured line across the notice, hiding the original text.
            self.assertGreater(url["bounds"][1], row["labels"][-2]["bounds"][3])
            self.assertLessEqual(url["bounds"][3] - url["bounds"][1], 25)
            self.assertTrue(all(0 < label["bounds"][3] - label["bounds"][1] <= 40
                                for label in row["labels"]))


if __name__ == "__main__":
    unittest.main()
