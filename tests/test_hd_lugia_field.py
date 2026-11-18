"""Reviewed shared-UV field belly transfer from a real 4x donor image."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtGui import QImage

from orre_randomizer import hd_lugia_field as field


class LugiaFieldMaterial(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.pack = Path(temporary.name)
        (self.pack / "Textures").mkdir()
        self.path = self.pack / "Textures" / field.BATTLE_BELLY
        self.pixels = bytearray()
        for y in range(128):
            for x in range(128):
                self.pixels.extend((160 + x % 64, 176 + y % 48,
                                    188 + (x + 3 * y) % 60, (0, 64, 128, 255)[(x + y) % 4]))
        self.pixels[:4] = bytes((255, 255, 255, 255))
        self.save_source(self.pixels, 128)
        pin = patch.object(field, "_HD_SOURCE_SHA256", hashlib.sha256(self.path.read_bytes()).hexdigest())
        pin.start()
        self.addCleanup(pin.stop)

    def save_source(self, pixels, size):
        image = QImage(bytes(pixels), size, size, size * 4, QImage.Format.Format_RGBA8888)
        self.assertTrue(image.save(str(self.path), "PNG"))

    def render(self, target=None):
        return field.render_lugia_field_material(self.pack, native_key=field.FIELD_BELLY,
                                                 target_key=target or field.FIELD_BELLY_SHINY)

    def test_output_uses_each_hd_texel_and_preserves_alpha_without_resizing(self):
        original = self.path.read_bytes()
        image, provenance = self.render()
        self.assertEqual((image.width(), image.height()), (128, 128))
        actual = bytes(image.constBits())
        self.assertEqual(actual[3::4], bytes(self.pixels[3::4]))
        self.assertEqual(actual[:4], bytes((255, 255, 255, 255)))
        # Genuine sub-native-pixel detail survives: adjacent HD samples within
        # one 4x4 native footprint do not collapse to one expanded native pixel.
        self.assertGreater(len({actual[x * 4:x * 4 + 3] for x in range(4, 8)}), 1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(provenance["no_upscale_native"])
        self.assertFalse(provenance["native_bitmap_resampled"])

    def test_fixed_transfer_brings_independent_native_color_anchors_closer(self):
        # Representative native CMPR colors are measurements, not image fixtures.
        source = [(184, 194, 209), (189, 199, 214), (237, 237, 237)]
        expected_field = [(188, 195, 201), (195, 199, 204), (237, 237, 237)]
        pixels = bytearray(bytes((*source[0], 255)) * (128 * 128))
        for index, rgb in enumerate(source):
            pixels[index * 4:index * 4 + 4] = bytes((*rgb, 255))
        self.save_source(pixels, 128)
        with patch.object(field, "_HD_SOURCE_SHA256", hashlib.sha256(self.path.read_bytes()).hexdigest()):
            image, _ = self.render()
        actual = bytes(image.constBits())
        before = sum((source[i][c] - expected_field[i][c]) ** 2 for i in range(3) for c in range(3))
        after = sum((actual[i * 4 + c] - expected_field[i][c]) ** 2 for i in range(3) for c in range(3))
        self.assertLess(after, before / 2)

    def test_normal_and_shiny_requests_get_the_same_untinted_base(self):
        normal, a = self.render(field.FIELD_BELLY)
        shiny, b = self.render(field.FIELD_BELLY_SHINY)
        self.assertEqual(bytes(normal.constBits()), bytes(shiny.constBits()))
        self.assertFalse(a["shiny_tint_applied"])
        self.assertFalse(b["shiny_tint_applied"])
        self.assertGreater(shiny.pixelColor(0, 0).red(), 240)

    def test_eye_body_and_unrelated_field_routes_are_not_modified(self):
        for native, target in (
            ("tex1_64x64_830778f52c6de2c0_44fccd7f7f60660f_9.png", field.FIELD_BELLY_SHINY),
            (field.FIELD_BELLY, "tex1_32x32_f135b3b243a3e441_14.png"),
            (field.BATTLE_BELLY, field.FIELD_BELLY_SHINY),
            ("../" + field.FIELD_BELLY, field.FIELD_BELLY_SHINY),
        ):
            with self.subTest(native=native, target=target):
                self.assertIsNone(field.render_lugia_field_material(self.pack, native_key=native, target_key=target))

    def test_mipmap_aliases_keep_the_same_explicit_route(self):
        image, provenance = field.render_lugia_field_material(
            self.pack, native_key=field.FIELD_BELLY.replace("32x32_", "32x32_m_"),
            target_key=field.FIELD_BELLY_SHINY.replace("32x32_", "32x32_m_"))
        self.assertEqual(image.width(), 128)
        self.assertEqual(provenance["target_key"], field.FIELD_BELLY_SHINY)

    def test_provenance_records_actual_source_and_auditable_native_material_proof(self):
        _, provenance = self.render()
        reference = provenance["reference"]
        self.assertEqual(reference["file"], field.BATTLE_BELLY)
        self.assertEqual(reference["physical_file"], self.path.name)
        self.assertEqual(reference["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual((reference["width"], reference["height"], reference["source_scale"]), (128, 128, 4))
        proof = provenance["material_proof"]
        self.assertEqual(proof["unique_uv_pairs"], 102)
        self.assertEqual(len(proof["field_models"]), 3)
        self.assertEqual(len({m["dat_sha256"] for m in proof["field_models"]}), 3)
        self.assertEqual(sum(proof["calibration"]["sse_rgb_before"]), 59652)
        self.assertEqual(sum(proof["calibration"]["sse_rgb_after_integer_transfer"]), 12853)
        self.assertFalse(provenance["native_payload_modified"])
        self.assertFalse(provenance["other_materials_modified"])
        json.dumps(provenance)
        proof["field_models"].clear()
        _, next_provenance = self.render()
        self.assertEqual(len(next_provenance["material_proof"]["field_models"]), 3)

    def test_missing_source_does_not_invent_a_donor(self):
        self.path.unlink()
        self.assertIsNone(self.render())

    def test_native_resolution_and_changed_donor_fail_closed(self):
        self.save_source(bytes((190, 195, 205, 255)) * (32 * 32), 32)
        with self.assertRaisesRegex(ValueError, "4x"):
            self.render()
        self.save_source(bytes((190, 195, 205, 255)) * (128 * 128), 128)
        with self.assertRaisesRegex(ValueError, "differs"):
            self.render()


class LugiaFieldEyes(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.pack = Path(temporary.name)
        (self.pack / "Textures").mkdir()
        self.path = self.pack / "Textures" / field.BATTLE_EYES
        pixels = bytearray(256 * 256 * 4)
        # The upper iris arc is absent from this atlas. Hidden RGB is garbage;
        # a plain crop or copying its alpha cannot supply the opaque field iris.
        for y in range(128):
            for x in range(256):
                radius = math.hypot(x - 131.5, y - 65.5)
                ring = 35 <= radius <= 50
                visible = y >= 65 and radius <= 112
                rgb = (0, 0, 0) if radius >= 100 else (250, 110, 100) if ring else (220, 16, 8)
                at = (y * 256 + x) * 4
                pixels[at:at+4] = bytes((*rgb, 255)) if visible else bytes((255, 255, 255, 0))
        image = QImage(bytes(pixels), 256, 256, 1024, QImage.Format.Format_RGBA8888)
        self.assertTrue(image.save(str(self.path), "PNG"))
        pin = patch.object(field, "_EYE_HD_SOURCE_SHA256", hashlib.sha256(self.path.read_bytes()).hexdigest())
        pin.start()
        self.addCleanup(pin.stop)

    def render(self, key):
        return field.render_lugia_field_material(self.pack, native_key=key, target_key=key)

    def test_occluded_iris_arc_is_completed_from_visible_hd_pixels(self):
        image, provenance = self.render(field.FIELD_EYE_IRIS)
        self.assertEqual((image.width(), image.height()), (256, 128))
        center = image.pixelColor(130, 66)
        upper = image.pixelColor(130, 24)
        lower = image.pixelColor(130, 108)
        self.assertGreater(upper.green(), center.green() + 40)
        self.assertGreater(lower.green(), center.green() + 40)
        self.assertLess(abs(upper.green() - lower.green()), 5)
        self.assertGreater(center.red(), center.green() * 3)
        self.assertGreater(image.pixelColor(0, 0).red(), 200)
        self.assertEqual(set(bytes(image.constBits())[3::4]), {255})
        self.assertEqual(provenance["material_role"], "red_iris")
        self.assertTrue(provenance["no_upscale_native"])

    def test_socket_is_a_blue_opaque_layer_not_a_second_red_iris(self):
        before = self.path.read_bytes()
        image, provenance = self.render(field.FIELD_EYE_SOCKET)
        data = bytes(image.constBits())
        self.assertEqual((image.width(), image.height()), (256, 128))
        self.assertEqual(set(data[3::4]), {255})
        self.assertGreater(max(data[2::4]), max(data[0::4]) * 2)
        self.assertGreater(len(set(data[2::4])), 30)
        self.assertEqual(provenance["material_role"], "blue_socket")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(provenance["reference"]["source_scale"], 4)

    def test_both_eye_layers_are_identical_for_normal_and_shiny_calls(self):
        for key in (field.FIELD_EYE_SOCKET, field.FIELD_EYE_IRIS):
            first, a = self.render(key)
            second, b = field.render_lugia_field_eye_material(self.pack, native_key=key, target_key=key)
            self.assertEqual(bytes(first.constBits()), bytes(second.constBits()))
            self.assertTrue(a["normal_shiny_identical"])
            self.assertFalse(b["shiny_tint_applied"])
            self.assertIsNone(field.render_lugia_field_eye_material(
                self.pack, native_key=key, target_key=field.FIELD_BELLY_SHINY))

    def test_eye_provenance_includes_uv_geometry_alpha_and_native_calibration(self):
        for key in (field.FIELD_EYE_SOCKET, field.FIELD_EYE_IRIS):
            _, provenance = self.render(key)
            self.assertEqual(provenance["reference"]["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
            proof = provenance["material_proof"]
            self.assertEqual(proof["source_frame_native_rect"], [0, 0, 64, 32])
            self.assertEqual(proof["wrap"], ["CLAMP", "CLAMP"])
            self.assertEqual(len(proof["field_uv_signature"]), 64)
            self.assertLess(proof["native_rgb_calibration_rmse"], 4.3)
            self.assertFalse(provenance["native_payload_modified"])
            json.dumps(provenance)

    def test_material_inventory_requires_every_material_in_all_three_models(self):
        inventory = field.field_material_inventory(self.pack)
        self.assertTrue(inventory["custom_models_require_every_material"])
        self.assertEqual([len(m["materials"]) for m in inventory["models"]], [5, 7, 6])
        materials = [m for model in inventory["models"] for m in model["materials"]]
        self.assertTrue(all(m["hd_required"] and m["required_scale"] == 4 for m in materials))
        eye = next(m for m in materials if m["native_key"] == field.BATTLE_EYES)
        self.assertTrue(eye["source_available"])
        self.assertEqual((eye["width"], eye["height"], eye["format"]), (64, 64, 9))
        for key in (field.FIELD_EYE_SOCKET, field.FIELD_EYE_IRIS):
            matches = [m for m in materials if m["native_key"] == key]
            self.assertEqual(len(matches), 2)
            self.assertTrue(all(not m["source_available"] for m in matches))
            self.assertTrue(all(m["shiny_key"] == key for m in matches))
            self.assertTrue(all(m["hd_route"] == "field-eye-layer-reconstruction" for m in matches))

    def test_unreviewed_or_missing_eye_atlas_fails_closed(self):
        with patch.object(field, "_EYE_HD_SOURCE_SHA256", "0" * 64):
            with self.assertRaises(ValueError):
                self.render(field.FIELD_EYE_IRIS)
        self.path.unlink()
        self.assertIsNone(self.render(field.FIELD_EYE_SOCKET))


if __name__ == "__main__":
    unittest.main()
