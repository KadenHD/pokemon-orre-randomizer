"""Added artwork respects each game's frame and keeps DNA bodies separate."""
import unittest

from orre_randomizer.artwork import _png_pixels
from orre_randomizer.model_artwork import format_model_portrait, validate_model_body
from orre_randomizer.resources import bundle_root, shadow_lugia_portrait


class ModelArtworkTests(unittest.TestCase):
    def test_custom_faces_use_square_or_circle_without_losing_source_corners(self):
        source = bytearray(bytes((0, 0, 0, 255)) * (42 * 42))
        for x, y, rgb in ((0, 0, (255, 0, 0)), (41, 0, (0, 255, 0)),
                          (0, 41, (0, 0, 255)), (41, 41, (255, 255, 255))):
            at = (y * 42 + x) * 4
            source[at:at + 3] = bytes(rgb)
        self.assertEqual(format_model_portrait(bytes(source), game="colosseum"), source)
        image = format_model_portrait(bytes(source), game="xd")
        for x, y in ((0, 0), (41, 0), (0, 41), (41, 41)):
            at = (y * 42 + x) * 4
            self.assertEqual(image[at:at + 4], bytes(4))
        for x, y, rgb in ((7, 7, (113, 0, 0)), (34, 7, (0, 113, 0)),
                          (7, 34, (0, 0, 113)), (34, 34, (113, 113, 113))):
            at = (y * 42 + x) * 4
            self.assertEqual(image[at:at + 4], bytes((*rgb, 255)))
        self.assertEqual(image[(21 * 42 + 21) * 4 + 3], 255)
        self.assertEqual(image[3::4], bytes(image[(y * 42 + 41 - x) * 4 + 3]
                         for y in range(42) for x in range(42)))

    def test_bad_game_dimensions_alpha_and_fit_are_rejected(self):
        face = bytes((4, 8, 12, 255)) * (42 * 42)
        for kwargs in (dict(game="other"), dict(game="xd", alpha_mask=b""),
                       dict(game="colosseum", alpha_mask=bytes(42 * 42)),
                       dict(game="xd", artwork_size=43), dict(game="xd", artwork_size=True)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                format_model_portrait(face, **kwargs)
        for invalid in (b"", bytes(42 * 42 * 4), bytes(64 * 64 * 4)):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                format_model_portrait(invalid, game="xd")

    def test_dna_requires_separate_visible_body_with_transparent_margin(self):
        body = bytearray(64 * 64 * 4)
        at = (32 * 64 + 32) * 4
        body[at:at + 4] = bytes((12, 34, 56, 255))
        self.assertEqual(validate_model_body(bytes(body)), body)
        for invalid in (bytes(64 * 64 * 4), bytes((0, 0, 0, 255)) * (42 * 42),
                        bytes((0, 0, 0, 255)) * (64 * 64)):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                validate_model_body(invalid)

    def test_shadow_lugia_faces_share_native_game_masks_in_both_variants(self):
        from orre_randomizer.engine.shadow_lugia_face import make_xd_shadow_lugia_round_portrait
        pack = bundle_root() / "models"
        if not (pack / "dark-lugia.png").is_file():
            self.skipTest("requires optional game interface pack")
        reference = _png_pixels((pack / "dark-lugia.png").read_bytes(), (42, 42))
        for shiny, name in ((False, "dark-lugia.png"), (True, "dark-lugia-shiny.png")):
            with self.subTest(shiny=shiny):
                source = _png_pixels((pack / name).read_bytes(), (42, 42))
                square = _png_pixels(shadow_lugia_portrait(shiny=shiny, game="colosseum"), (42, 42))
                circle = _png_pixels(shadow_lugia_portrait(shiny=shiny, game="xd"), (42, 42))
                self.assertEqual(square[3::4], bytes((255,)) * (42 * 42))
                from orre_randomizer.model_portraits import registered_portrait
                registered = registered_portrait(pack, game="xd", shiny=shiny)
                expected = (_png_pixels(registered, (42, 42)) if registered is not None
                            else make_xd_shadow_lugia_round_portrait(source, reference=reference))
                self.assertEqual(circle, expected)
                self.assertEqual(circle[3::4], reference[3::4])
                self.assertEqual(circle[:4], bytes(4))
                self.assertNotEqual(square, circle)


if __name__ == "__main__":
    unittest.main()
