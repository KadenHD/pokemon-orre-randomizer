"""Portable offline material reconstruction checks, independent of ROM/save files."""
import unittest
import hashlib

try:
    import numpy as np
except ImportError:
    np = None

from orre_randomizer.hd_extra_portrait_catalog import HD_MATERIAL_SOURCE_PINS


class SourcePinTests(unittest.TestCase):
    def test_source_catalogue_contains_the_actual_independent_pack_file_pins(self):
        self.assertEqual(set(HD_MATERIAL_SOURCE_PINS), {"colosseum", "xd"})
        self.assertEqual(len(HD_MATERIAL_SOURCE_PINS["colosseum"]), 5)
        self.assertEqual(len(HD_MATERIAL_SOURCE_PINS["xd"]), 22)
        for pins in HD_MATERIAL_SOURCE_PINS.values():
            for key, sha in pins.items():
                self.assertRegex(key, r"^tex1_\d+x\d+_[a-f0-9_]+_\d+\.png$")
                self.assertRegex(sha, r"^[a-f0-9]{64}$")


@unittest.skipIf(np is None, "NumPy is needed only by the offline authoring tools")
class MaterialConstructionTests(unittest.TestCase):
    def test_fixed_weather_palette_preserves_hd_iris_neutrals_and_alpha(self):
        from scripts.extra_portrait_materials import weather
        guide = np.full((8, 8, 4), (255, 220, 120, 255), dtype="uint8")
        target = np.full((8, 8, 4), (180, 210, 240, 255), dtype="uint8")
        hd = np.full((32, 32, 4), (240, 220, 120, 255), dtype="uint8")
        hd[4:8, 4:8, :3] = 30
        hd[1, 1, 3] = 0
        original = hd.copy()
        result, recipe = weather.recolour_paint(hd, guide, target, 1)
        np.testing.assert_array_equal(result[4:8, 4:8, :3], 30)
        np.testing.assert_array_equal(result[:, :, 3], hd[:, :, 3])
        np.testing.assert_array_equal(result[20, 20, :3], target[0, 0, :3])
        np.testing.assert_array_equal(hd, original)
        self.assertTrue(recipe["no_rgb_regression"])

    def test_analytic_lighting_reconstructs_a_known_continuous_uv_function(self):
        from scripts.extra_portrait_materials import weather
        yy, xx = np.mgrid[:32, :32]
        values = (140 + 20 * (xx + .5) / 32 + 15 * ((yy + .5) / 32) ** 2).round().astype("uint8")
        guide = np.full((32, 32, 4), 255, dtype="uint8")
        guide[:, :, :3] = values[:, :, None]
        result, recipe = weather.analytic_grey(guide)
        self.assertEqual(result.shape, (128, 128, 4))
        self.assertLess(recipe["native_guide_mae"], .35)
        self.assertLess(recipe["native_guide_p99"], .7)

    def test_vector_uv_reconstruction_keeps_holes_and_hard_corners(self):
        from scripts.extra_portrait_materials import deoxys
        guide = np.zeros((24, 24), bool)
        guide[2:22, 2:22] = True
        guide[8:16, 8:16] = False
        coverage, paths = deoxys.vector_mask(guide)
        self.assertGreaterEqual(len(paths), 2)
        self.assertGreater(coverage[16, 16], .99)
        self.assertLess(coverage[48, 48], .01)
        self.assertAlmostEqual(coverage.sum() / 16, guide.sum(), delta=8)

    def test_material_classes_do_not_turn_cyan_shadows_into_purple_patchwork(self):
        from scripts.extra_portrait_materials import deoxys
        values = np.array([[[0, 40, 90], [80, 80, 160], [100, 105, 115], [30, 32, 36]]], dtype="uint8")
        labels = deoxys.classes(values)
        self.assertEqual(labels.tolist(), [[2, 3, 0, 4]])

    def test_a_one_dimensional_emissive_ramp_is_evaluated_without_bitmap_enlargement(self):
        from scripts.extra_portrait_materials import deoxys
        guide = np.full((64, 4, 4), 255, dtype="uint8")
        guide[:, :, :3] = np.linspace([240, 80, 100], [255, 100, 230], 64).round().astype("uint8")[:, None, :]
        result, recipe = deoxys.construct(guide, False, {})
        self.assertEqual(result.shape, (256, 16, 4))
        self.assertFalse(recipe[0]["native_bitmap_resampled"])
        self.assertFalse(recipe[0]["painted_bitmap_detail_claimed"])
        self.assertLess(np.abs(result[1, 1, :3].astype(int) - guide[0, 0, :3]).max(), 2)

    def test_authored_attack_material_preserves_native_alpha_cutouts(self):
        from scripts.extra_portrait_materials import deoxys
        guide = np.full((32, 32, 4), (100, 110, 120, 255), dtype="uint8")
        guide[8:24, 8:24, 3] = 0
        result, proof = deoxys.construct(guide, False, {})
        self.assertEqual(result[64, 64, 3], 0)
        self.assertEqual(result[16, 16, 3], 255)
        self.assertGreater(proof[-1]["native_alpha_mask_iou"], .98)
        # Hidden material RGB remains available to native TEV modes; zeroing
        # outside the final portrait frame is a separate compositor operation.
        self.assertTrue(np.all(result[64, 64, :3] > 0))

    def test_specular_opacity_transfer_keeps_extrema_and_hd_detail_order(self):
        from scripts.extra_portrait_materials import weather
        source = np.array([[0, 64, 128, 255]], dtype="uint8")
        target = np.array([[0, 80, 180, 255]], dtype="uint8")
        hd = np.arange(256, dtype="uint8")[None, :]
        result, proof = weather.retarget_opacity(hd, source, target)
        self.assertEqual(int(result.min()), 0)
        self.assertEqual(int(result.max()), 255)
        self.assertTrue(np.all(np.diff(result.astype(int)) >= 0))
        self.assertTrue(proof["hd_lobe_positions_and_detail_preserved"])

    def test_speed_eye_keeps_real_hd_iris_without_another_forms_coloured_uv_panel(self):
        from scripts.extra_portrait_materials import eye_analytic
        guide = np.full((32, 32, 4), (0, 160, 200, 255), dtype="uint8")
        guide[16:29, 16:29, :3] = 0  # Coarse native aperture extends outside the HD eye.
        source = np.full((128, 128, 4), (0, 160, 190, 255), dtype="uint8")
        source[12:48, 12:32, :3] = (100, 220, 240)  # Foreign Defense background detail.
        source[72:104, 72:112, :3] = 8
        source[80:96, 80:104, :3] = 240
        source[84:92, 88:96, :3] = 2
        original = source.copy()
        palettes = {2: np.array([[0., 160., 190.]] * 3)}
        output, proof = eye_analytic.rebuild_background(source, guide, False, palettes)
        np.testing.assert_array_equal(output[20:40, 16:28, :3], np.broadcast_to((0, 160, 190), (20, 12, 3)))
        np.testing.assert_array_equal(output[84:92, 88:96], source[84:92, 88:96])
        np.testing.assert_array_equal(output[80, 84], source[80, 84])
        np.testing.assert_array_equal(output[68, 68, :3], (0, 160, 190))
        np.testing.assert_array_equal(source, original)
        self.assertFalse(proof["foreign_source_form_background_panels_retained"])
        self.assertFalse(proof["native_bitmap_resampled"])
        self.assertFalse(proof["native_neutral_eye_rendered_beneath_hd_iris"])

    def test_coincident_lighting_quantiles_cannot_turn_a_flat_plate_into_a_highlight(self):
        from scripts.extra_portrait_materials import deoxys
        colors = np.array([[18., 97., 116.], [38., 156., 178.], [98., 194., 213.]])
        levels, palette = deoxys.distinct_lighting_stops(np.array([68.333, 126.667, 126.667]), colors)
        np.testing.assert_array_equal(levels, [68.333, 126.667])
        np.testing.assert_array_equal(palette[-1], colors[1])
        output = np.array([np.interp([126.666, 126.667, 126.668], levels, palette[:, channel])
                           for channel in range(3)]).T
        self.assertLess(np.max(np.abs(np.diff(output, axis=0))), .01)
        np.testing.assert_array_equal(output[-1], colors[1])

    def test_tall_uv_field_keeps_reviewed_filter_rounding_across_pillow_versions(self):
        from PIL import Image
        from scripts.extra_portrait_materials import deoxys
        yy, xx = np.mgrid[:512, :128]
        image = Image.fromarray(((xx * 17 + yy * 29 + (xx * yy % 19) * 5) % 256).astype("uint8"))
        expected = [(Image.Resampling.LANCZOS, (64, 256),
                     "c84a516195d7cb61c42fdf8fcdaeb33514eeed0da65b2fa08e913a6b9e8b45d3"),
                    (Image.Resampling.BOX, (32, 128),
                     "e4069cb6479a71b03514fb4bbd0a5d229b62d7d2088c34229125bdcb94dbd297")]
        for resample, size, digest in expected:
            with self.subTest(filter=resample):
                result = deoxys.resize_uv_field(image, size, resample)
                self.assertEqual(hashlib.sha256(result.tobytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
