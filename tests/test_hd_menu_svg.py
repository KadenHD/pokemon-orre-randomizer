"""Real author geometry survives; native raster guides cannot reach the output."""
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QGuiApplication, QImage
from orre_randomizer.hd_menu_svg import _integer_straight_alpha, render_background


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
        self.assertTrue(all(r["rasterization"] == "integer-premultiplied-alpha"
                            and r["alpha_conversion"] == "rgba8888-pm-integer-half-up-v1"
                            for r in receipt["outputs"]))

    def test_translucent_art_is_painted_premultiplied_and_exported_without_qt_unpremultiply(self):
        from PySide6.QtSvg import QSvgRenderer
        formats = []
        class ObservedRenderer:
            def __init__(self, payload):
                self.native = QSvgRenderer(payload)
            def isValid(self):
                return self.native.isValid()
            def render(self, painter, bounds):
                formats.append(painter.device().format())
                self.native.render(painter, bounds)

        source = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">
          <rect width="8" height="4" fill="#808080" fill-opacity="0.023529411764705882"/>
        </svg>'''
        with patch("orre_randomizer.hd_menu_svg.QSvgRenderer", ObservedRenderer), patch.object(
                QImage, "convertToFormat", side_effect=AssertionError("Qt straight-alpha conversion is forbidden")):
            image, receipt = self.render(source, remove_ids=(), integer_alpha=True)
        self.assertEqual(receipt["rasterization"], "integer-premultiplied-alpha")
        self.assertEqual(formats, [QImage.Format.Format_RGBA8888_Premultiplied])
        self.assertEqual(image.format(), QImage.Format.Format_RGBA8888)
        self.assertTrue(all(image.pixelColor(x, y) == QColor(128, 128, 128, 6)
                            for y in range(16) for x in range(32)))

    def test_integer_alpha_rounds_every_valid_premultiplied_byte_pair_exactly(self):
        # Covers every alpha, the problematic 127.5 ties, full opacity, and
        # transparent RGB cleanup without consulting Qt's inverse conversion.
        pairs = [(value, alpha) for alpha in range(256) for value in range(alpha + 1)]
        pairs.extend([(255, 0)])
        raw = bytes(value for channel, alpha in pairs for value in (channel, channel, channel, alpha))
        image = QImage(raw, len(pairs), 1, len(raw), QImage.Format.Format_RGBA8888_Premultiplied)
        output = _integer_straight_alpha(image)
        actual = bytes(output.constBits())[:output.sizeInBytes()]
        expected = bytearray()
        for value, alpha in pairs:
            # Independent divmod formulation explicitly resolves a half tie up.
            quotient, remainder = divmod(value * 255, alpha or 1)
            straight = min(255, quotient + (2 * remainder >= alpha)) if alpha else 0
            expected.extend((straight, straight, straight, alpha))
        self.assertEqual(actual, bytes(expected))
        for index, (value, alpha) in enumerate(pairs[:-1]):
            self.assertEqual((actual[index * 4] * alpha + 127) // 255, value)
        with self.assertRaisesRegex(ValueError, "premultiplied"):
            _integer_straight_alpha(output)

    def test_integer_authoring_keeps_opaque_and_grouped_art_on_the_same_math_contract(self):
        flat = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">
          <rect width="8" height="4" fill="black"/>
          <path d="M1 1H7V3H1Z" fill="white"/>
        </svg>'''
        image, receipt = self.render(flat, remove_ids=(), integer_alpha=True)
        self.assertEqual(receipt["rasterization"], "integer-premultiplied-alpha")
        self.assertEqual(image.pixelColor(0, 0), QColor(0, 0, 0, 255))
        self.assertEqual(image.pixelColor(8, 8), QColor(255, 255, 255, 255))
        grouped = flat.replace(b'<path ', b'<g opacity=".5"><path ').replace(b'</svg>', b'</g></svg>')
        for source in (grouped,
                       flat.replace(b'viewBox=', b'opacity=".5" viewBox='),
                       flat.replace(b'fill="black"', b'fill="black" fill-opacity=".5"')):
            _, receipt = self.render(source, remove_ids=(), integer_alpha=True)
            self.assertEqual(receipt["rasterization"], "integer-premultiplied-alpha")

    def test_reproduction_rejects_a_single_wrong_pixel_before_canonical_png_publication(self):
        from scripts.build_hd_geometry_additions import reproduce
        original = render_background
        for wrong in (QColor(255, 0, 255, 255), QColor(18, 18, 18, 1)):
            def changed(*args, **kwargs):
                image, metadata = original(*args, **kwargs)
                image.setPixelColor(0, 0, wrong)
                return image, metadata
            with self.subTest(wrong=wrong), TemporaryDirectory() as temporary, patch(
                    "orre_randomizer.hd_menu_svg.render_background", side_effect=changed):
                output = Path(temporary) / "changed"
                with self.assertRaisesRegex(ValueError, "Geometry pixels differ"):
                    reproduce(output)
                self.assertEqual(list(output.iterdir()), [])

    def test_reproduction_checks_the_native_premultiplied_identity_before_publication(self):
        from scripts.build_hd_geometry_additions import reproduce
        original = render_background
        def changed(*args, **kwargs):
            image, metadata = original(*args, **kwargs)
            return image, dict(metadata, premultiplied_rgba_sha256="0" * 64)
        with TemporaryDirectory() as temporary, patch(
                "orre_randomizer.hd_menu_svg.render_background", side_effect=changed):
            output = Path(temporary) / "changed"
            with self.assertRaisesRegex(ValueError, "premultiplied pixels differ"):
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
