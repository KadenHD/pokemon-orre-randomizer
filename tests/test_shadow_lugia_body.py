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
                self.assertGreaterEqual(min(x for x, _ in occupied), 4)
                self.assertLess(max(x for x, _ in occupied), 60)
                self.assertGreaterEqual(min(y for _, y in occupied), 4)
                self.assertLess(max(y for _, y in occupied), 60)
                self.assertTrue(any(a > 100 and r > g * 1.3 and r > b * 1.2
                                    for r, g, b, a in zip(*[iter(pixels)] * 4)))

    def test_native_variant_retains_dark_body_and_shiny_swaps_it(self):
        ordinary, shiny = (shadow_lugia_body_pixels(value) for value in (False, True))
        self.assertNotEqual(ordinary, shiny)
        def bright_count(data):
            return sum(a > 100 and min(r, g, b) > 170
                       for r, g, b, a in zip(*[iter(data)] * 4))
        self.assertGreater(bright_count(shiny), bright_count(ordinary) * 2)

    def test_invalid_variant_is_rejected(self):
        for value in (None, 0, 1, 'shiny'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                shadow_lugia_body_pixels(value)


if __name__ == '__main__': unittest.main()
