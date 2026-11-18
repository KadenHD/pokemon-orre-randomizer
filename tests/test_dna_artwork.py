"""DNA ink follows the silhouette without recoloring, mirroring or clipping it."""
import unittest

from orre_randomizer.engine.dna_artwork import outline_dna_body


class DnaArtwork(unittest.TestCase):
    def test_outline_has_the_same_native_width_at_both_resolutions(self):
        for scale in (1, 4):
            size = 64 * scale
            pixels = bytearray(size * size * 4)
            for y in range(16 * scale, 48 * scale):
                for x in range(8 * scale, 24 * scale):
                    at = (y * size + x) * 4
                    pixels[at:at + 4] = b'\xfe\x20\x40\xff'
            outlined = outline_dna_body(bytes(pixels), size)
            def pixel(x, y):
                at = (y * size + x) * 4
                return outlined[at:at + 4]
            self.assertEqual(pixel(8 * scale, 24 * scale), b'\xfe\x20\x40\xff')
            self.assertEqual(pixel(7 * scale, 24 * scale), b'\0\0\0\xff')
            self.assertEqual(pixel(7 * scale - 1, 24 * scale), bytes(4))
            self.assertEqual(pixel(24 * scale + scale - 1, 24 * scale), b'\0\0\0\xff')
            # Its asymmetric position is retained, not mirrored across the tile.
            self.assertEqual(pixel(48 * scale, 24 * scale), bytes(4))

    def test_antialiased_edges_are_composited_over_black_without_white_fringe(self):
        size = 64
        pixels = bytearray(size * size * 4)
        at = (32 * size + 32) * 4
        pixels[at:at + 4] = b'\xff\xff\xff\xff'
        pixels[at + 4:at + 8] = b'\xff\xff\xff\x80'
        outlined = outline_dna_body(bytes(pixels), size)
        self.assertEqual(outlined[at:at + 4], b'\xff\xff\xff\xff')
        self.assertEqual(outlined[at + 4:at + 8], b'\x80\x80\x80\xff')
        self.assertEqual(outlined[at + 8:at + 12], b'\0\0\0\x80')
        self.assertEqual(pixels[at + 4:at + 8], b'\xff\xff\xff\x80')

    def test_empty_alpha_has_no_invented_shape_or_hidden_rgb(self):
        self.assertEqual(outline_dna_body(b'\xff\xff\xff\0' * 4096, 64), bytes(64 * 64 * 4))

    def test_invalid_dimensions_do_not_enter_native_or_hd_composition(self):
        for pixels, size in ((bytes(42 * 42 * 4), 42), (bytes(16), 64), (bytes(4), True)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                outline_dna_body(pixels, size)


if __name__ == '__main__':
    unittest.main()
