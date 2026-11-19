"""True HD portrait transfer preserves forms, atlas cells and native round style."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from PySide6.QtGui import QImage, QColor

from orre_randomizer import hd_portraits as portraits


def native_atlas(width, background=(35, 15, 70, 255)):
    rgba = bytearray()
    for y in range(84):
        for x in range(width):
            xx, yy = x % 42, y % 42
            inside = (xx + .5 - 21) ** 2 + (yy + .5 - 21) ** 2 < 22 ** 2
            rgba.extend(background if inside else (0, 0, 0, 0))
    return QImage(bytes(rgba), width, 84, width * 4, QImage.Format.Format_RGBA8888).copy()


def fixture(member):
    national, width, source, target, sha = portraits._CATALOG[member]
    origin = portraits.ordinary_portrait_origin(member, target, (width, 84))
    image = QImage(width * 4, 336, QImage.Format.Format_RGBA8888)
    colors = [(240, 30, 50, 255), (30, 220, 60, 255), (40, 70, 240, 255), (240, 210, 20, 255)]
    columns = width // 42
    for y in range(336):
        for x in range(width * 4):
            image.setPixelColor(x, y, QColor(*colors[(y // 168) * columns + x // 168]))
    return origin, image, native_atlas(width), {"sha256": sha, "source_scale": 4}


class OrdinaryPortraitTests(unittest.TestCase):
    def test_catalog_covers_every_base_species_and_28_unown_without_form_substitution(self):
        with patch("orre_randomizer.hd_extra_portraits.extra_portraits_registered", return_value=False):
            report = portraits.portrait_coverage_report()
        self.assertEqual(report["texture_atlases"], 413)
        self.assertEqual(report["base_species"], 386)
        self.assertEqual(report["unown_forms"], 28)
        self.assertEqual({row[0] for row in portraits._CATALOG.values()}, set(range(1, 387)))
        self.assertEqual(len(report["missing_forms"]), 6)
        for member in ("face249dark", "face410atk", "face410def", "face410sp", "face385f"):
            self.assertFalse(portraits.is_ordinary_portrait_member(member))
            self.assertIsNone(portraits.ordinary_portrait_origin(member, "unused", (42, 84)))
        self.assertTrue(portraits.is_ordinary_portrait_member("face410"))

    def test_reviewed_extra_captures_close_portrait_gaps_without_claiming_stock3d_materials(self):
        with patch("orre_randomizer.hd_extra_portraits.extra_portraits_registered", return_value=True):
            report = portraits.portrait_coverage_report()
        self.assertEqual(report["texture_atlases"], 413)
        self.assertEqual(report["missing_forms"], [])
        self.assertEqual(len(report["forms_absent_from_upstream_portrait_donors"]), 6)
        self.assertEqual(report["additional_portraits"]["texture_atlases"], 9)
        self.assertTrue(report["additional_portraits"]["registered"])
        self.assertFalse(report["additional_portraits"]["stock_3d_materials_installed"])

    def test_every_identity_roundtrips_without_region_offsets_and_accepts_mipmap_alias(self):
        for member, (_, width, source, target, _) in portraits._CATALOG.items():
            with self.subTest(member=member):
                origin = portraits.ordinary_portrait_origin(member, target, (width, 84))
                self.assertEqual(origin["file"], source)
                self.assertEqual(origin["game"], "colosseum")
                alias = target.replace(f"tex1_{width}x84_", f"tex1_{width}x84_m_", 1)
                self.assertEqual(portraits.ordinary_portrait_origin(member, alias, (width, 84)), origin)
                self.assertNotIn("region", origin)
        self.assertTrue(portraits._CATALOG["face286"][2].endswith("_5.png"))

    def test_changed_known_identity_and_wrong_atlas_dimensions_fail_explicitly(self):
        _, width, _, target, _ = portraits._CATALOG["face249"]
        with self.assertRaisesRegex(ValueError, "unknown or changed"):
            portraits.ordinary_portrait_origin("face249", target.replace("_9.png", "_6.png"), (width, 84))
        with self.assertRaisesRegex(ValueError, "unknown or changed"):
            portraits.ordinary_portrait_origin("face249", target, (84, 84))

    def test_two_vertical_cells_keep_normal_and_shiny_and_coloured_native_background(self):
        origin, image, native, metadata = fixture("face249")
        for y in range(24):
            for x in range(image.width()):
                image.setPixelColor(x, y, QColor(0, 0, 0, 0))
        before = bytes(image.constBits()), bytes(native.constBits())
        output, proof = portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)
        self.assertEqual((output.width(), output.height()), (168, 336))
        self.assertEqual(output.pixelColor(84, 84).getRgb(), (240, 30, 50, 255))
        self.assertEqual(output.pixelColor(84, 252).getRgb(), (30, 220, 60, 255))
        self.assertEqual(output.pixelColor(84, 10).getRgb(), (35, 15, 70, 255))
        self.assertEqual(output.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(proof["backgrounds"][0]["kind"], "native uniform background")
        self.assertFalse(proof["native_colour_bitmap_resampled"])
        self.assertEqual(before, (bytes(image.constBits()), bytes(native.constBits())))

    def test_four_cell_atlas_keeps_both_sides_and_shiny_rows_separate(self):
        origin, image, native, metadata = fixture("face201b")
        output, proof = portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)
        self.assertEqual((output.width(), output.height()), (336, 336))
        self.assertEqual([output.pixelColor(x, y).getRgb() for x, y in ((84, 84), (252, 84), (84, 252), (252, 252))],
                         [(240, 30, 50, 255), (30, 220, 60, 255), (40, 70, 240, 255), (240, 210, 20, 255)])
        self.assertEqual(proof["cells"]["columns"], 2)

    def test_native_character_pixels_never_become_a_cutout_for_the_hd_donor(self):
        origin, image, native, metadata = fixture("face249")
        first, _ = portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)
        for y in range(12, 30):
            for x in range(12, 30):
                native.setPixelColor(x, y, QColor(10, 250, 10, 255))
        second, proof = portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)
        self.assertEqual(bytes(first.constBits()), bytes(second.constBits()))
        self.assertFalse(proof["framing"]["native_species_silhouette_used"])
        self.assertEqual(proof["framing"]["uniform_scale"], 1)
        self.assertEqual(proof["framing"]["source_cell"], proof["framing"]["destination_cell"])

    def test_all_four_cells_keep_pixel_coordinates_and_full_framing(self):
        origin, image, native, metadata = fixture("face201b")
        for y in (0, 168):
            for x in (0, 168):
                image.setPixelColor(x + 28, y + 84, QColor(140, 60, 220, 255))
                image.setPixelColor(x + 84, y + 6, QColor(10, 170, 220, 255))
        output, proof = portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)
        for y in (0, 168):
            for x in (0, 168):
                self.assertEqual(output.pixelColor(x + 28, y + 84), image.pixelColor(x + 28, y + 84))
                self.assertEqual(output.pixelColor(x + 84, y + 6), image.pixelColor(x + 84, y + 6))
        self.assertEqual(proof["framing"]["uniform_scale"], 1)

    def test_arbitrary_native_silhouette_cannot_pass_as_a_round_frame(self):
        origin, image, native, metadata = fixture("face249")
        for cy in (21, 63):
            for y in (cy - 1, cy):
                for x in (20, 21):
                    native.setPixelColor(x, y, QColor(0, 0, 0, 0))
        with self.assertRaisesRegex(ValueError, "round frame"):
            portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)

    def test_antialiased_round_native_frame_preserves_edge_and_normalizes_palette_noise(self):
        origin, image, native, metadata = fixture("face072")
        for y in range(84):
            for x in range(42):
                radius = ((x + .5 - 21) ** 2 + (y % 42 + .5 - 21) ** 2) ** .5
                alpha = round(max(0, min(1, 21.5 - radius)) * 255)
                native.setPixelColor(x, y, QColor(20, 40, 60, alpha))
        native.setPixelColor(17, 42, QColor(20, 40, 60, 50))
        output, proof = portraits.render_xd_portrait(image, origin["transform"], native_image=native, source_metadata=metadata)
        alpha = bytes(output.constBits())[3::4]
        self.assertTrue(any(0 < value < 255 for value in alpha))
        self.assertEqual(alpha[:168 * 168], alpha[168 * 168:])
        self.assertEqual(proof["round_alpha"]["edge_palette_differences_normalized"], [0, 1])

    def test_modified_hd_file_or_native_sized_bitmap_never_satisfies_hd_contract(self):
        origin, image, native, metadata = fixture("face249")
        with self.assertRaisesRegex(ValueError, "release-pinned"):
            portraits.render_xd_portrait(image, origin["transform"], native_image=native,
                                         source_metadata=dict(metadata, sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "genuine HD"):
            portraits.render_xd_portrait(image, origin["transform"], native_image=native,
                                         source_metadata=dict(metadata, source_scale=1))
        altered = deepcopy(origin["transform"])
        altered["layout"]["columns"] = 2
        with self.assertRaisesRegex(ValueError, "geometry or identity"):
            portraits.render_xd_portrait(image, altered, native_image=native, source_metadata=metadata)
