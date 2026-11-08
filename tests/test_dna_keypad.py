import unittest

from orre_randomizer.artwork import _decode_pixels
from orre_randomizer.engine.dna_keypad import (
    DNA_KEYPAD_SPECIES, _SPINDA_ART_RECT, _tile_art, patch_dna_keypad,
)
from orre_randomizer.engine.dna_keypad_runtime import _sample_offsets


class DnaKeypadTests(unittest.TestCase):
    def test_identity_mapping_preserves_original_keypad(self):
        original = b"original keypad"
        mapping = {species: (species, False) for species in DNA_KEYPAD_SPECIES}
        self.assertEqual(patch_dna_keypad(original, b"", mapping), original)

    def test_tile_uses_the_left_portrait_frame_and_marks_duplicates(self):
        green = bytes((0, 255, 0, 255))
        blue = bytes((0, 0, 255, 255))
        red = bytes((255, 0, 0, 255))
        template = green * (128 * 128)
        normal_row = red * 42 + green * 42
        shiny_row = blue * 42 + green * 42
        portrait = normal_row * 42 + shiny_row * 42

        def pixel(tile, x, y):
            index = (y * 128 + x) * 4
            return tile[index:index + 4]

        normal = _decode_pixels(128, 128, 4, _tile_art(template, portrait, 84, False, 0))
        marked = _decode_pixels(128, 128, 4, _tile_art(template, portrait, 84, True, 1))
        self.assertEqual(pixel(normal, 64, 64), red)
        self.assertEqual(pixel(marked, 64, 64), blue)
        self.assertEqual(pixel(normal, 111, 99), green)
        self.assertEqual(pixel(marked, 111, 99), b"\xff\xff\xff\xff")

    def test_spinda_mask_samples_native_texels_without_covering_the_tile_number(self):
        left, top, size = _SPINDA_ART_RECT
        self.assertEqual((left % 8, top % 8, size % 8), (0, 0, 0))
        self.assertLessEqual(top + size, 96)

        # Simulate the native RGB565 layout with a white box over a black face.
        # Interpret the sampled bytes as CMPR selectors to check both layouts.
        native_white = set()
        for y in range(12, 28):
            for x in range(32, 64):
                block = y // 4 * 32 + x // 4
                native_white.add((block * 16 + y % 4 * 4 + x % 4) * 2)
        encoded = bytearray()
        offsets = _sample_offsets()
        for index in range(0, len(offsets), 16):
            selectors = 0
            for offset in offsets[index:index + 16]:
                selectors = selectors << 2 | int(offset not in native_white)
            encoded.extend(b"\xff\xff\x00\x00" + selectors.to_bytes(4, "big"))
        actual = _decode_pixels(size, size, 4, encoded)
        expected = b"".join(
            b"\xff\xff\xff\xff" if 8 <= y < 18 and 20 <= x < 40 else b"\0\0\0\xff"
            for y in range(size) for x in range(size)
        )
        self.assertEqual(actual, expected)
