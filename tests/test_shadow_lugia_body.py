import unittest

from orre_randomizer.engine.shadow_lugia_body import shadow_lugia_body_pixels


class ShadowLugiaBodyTests(unittest.TestCase):
    def test_native_silhouettes_have_clear_margin_and_visible_eyes(self):
        for shiny in (False, True):
            with self.subTest(shiny=shiny):
                pixels = shadow_lugia_body_pixels(shiny)
                self.assertEqual(len(pixels), 64 * 64 * 4)
                occupied = [(i % 64, i // 64) for i in range(4096) if pixels[4 * i + 3]]
                self.assertGreater(len(occupied), 500)
                # The whole model and its ink must retain a clear outer margin.
                self.assertGreaterEqual(min(x for x, _ in occupied), 1)
                self.assertLess(max(x for x, _ in occupied), 63)
                self.assertGreaterEqual(min(y for _, y in occupied), 1)
                self.assertLess(max(y for _, y in occupied), 63)
                self.assertTrue(any(a > 100 and r > g * 1.3 and r > b * 1.2
                                    for r, g, b, a in zip(*[iter(pixels)] * 4)))

    def test_native_variant_retains_dark_body_and_shiny_swaps_it(self):
        ordinary, shiny = (shadow_lugia_body_pixels(value) for value in (False, True))
        self.assertNotEqual(ordinary, shiny)
        def bright_count(data):
            return sum(a > 100 and min(r, g, b) > 170
                       for r, g, b, a in zip(*[iter(data)] * 4))
        self.assertGreater(bright_count(shiny), bright_count(ordinary) * 2)

    def test_dna_contour_surrounds_the_custom_body_in_both_variants(self):
        for shiny in (False, True):
            pixels = shadow_lugia_body_pixels(shiny)
            boundary = []
            for y in range(1, 63):
                for x in range(1, 63):
                    at = (y * 64 + x) * 4
                    if pixels[at + 3] >= 128 and any(pixels[(dy * 64 + dx) * 4 + 3] < 128
                            for dx, dy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                        boundary.append(pixels[at:at + 3])
            self.assertGreater(len(boundary), 100)
            self.assertGreater(sum(max(color) <= 32 for color in boundary) / len(boundary), .9)

    def test_invalid_variant_is_rejected(self):
        for value in (None, 0, 1, 'shiny'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                shadow_lugia_body_pixels(value)


if __name__ == '__main__': unittest.main()
