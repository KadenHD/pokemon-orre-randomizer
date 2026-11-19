"""Composition preserves GPU framing and the real geometric portrait boundary."""
import unittest

from PIL import Image

from scripts.compose_extra_portraits import compose_atlas, native_circle_alpha


def native_circle():
    alpha = bytes(255 if (x + .5 - 21) ** 2 + (y + .5 - 21) ** 2 < 22.5 ** 2 else 0
                  for y in range(42) for x in range(42))
    image = Image.new("RGBA", (42, 84), (120, 220, 30, 255))
    image.putalpha(Image.frombytes("L", (42, 84), alpha * 2))
    return image


class ExtraPortraitCompositionTests(unittest.TestCase):
    def test_native_disk_is_rebuilt_smoothly_without_filter_ringing_or_isolated_dots(self):
        alpha = native_circle_alpha(native_circle())
        rows = [list(alpha[y * 168:(y + 1) * 168]) for y in range(168)]
        self.assertGreater(sum(0 < value < 255 for value in alpha), 0)
        for y, row in enumerate(rows):
            self.assertEqual(row, row[::-1])
            self.assertEqual(row, rows[167 - y])
            self.assertEqual(row[:84], sorted(row[:84]))
        self.assertEqual(rows[0][0], 0)
        self.assertEqual(rows[84][84], 255)

    def test_a_hole_in_one_native_cell_cannot_be_mistaken_for_frame_geometry(self):
        image = native_circle()
        image.putpixel((21, 63), (0, 0, 0, 0))
        with self.assertRaisesRegex(ValueError, "verified shared XD disk"):
            native_circle_alpha(image)

    def test_both_variants_keep_the_same_gpu_crop_without_fitting_or_native_colours(self):
        normal = Image.new("RGBA", (1024, 1024), (240, 10, 30, 255))
        shiny = Image.new("RGBA", (1024, 1024), (10, 30, 240, 255))
        for raw in (normal, shiny):
            raw.paste((255, 255, 255, 255), (340, 340, 360, 360))
        result = compose_atlas(normal, shiny, [300, 300, 500, 500], native_circle(), game="xd")
        self.assertEqual(result.getpixel((84, 84)), (240, 10, 30, 255))
        self.assertEqual(result.getpixel((84, 252)), (10, 30, 240, 255))
        self.assertEqual(result.getpixel((42, 42)), (255, 255, 255, 255))
        self.assertEqual(result.getpixel((42, 210)), (255, 255, 255, 255))
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 0))
        self.assertEqual(result.crop((0, 0, 168, 168)).getchannel("A").tobytes(),
                         result.crop((0, 168, 168, 336)).getchannel("A").tobytes())

    def test_colosseum_has_full_opaque_square_and_hidden_model_colour_is_not_leaked(self):
        normal = Image.new("RGBA", (1024, 1024), (255, 255, 255, 0))
        shiny = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
        result = compose_atlas(normal, shiny, [0, 0, 200, 200], native_circle(), game="colosseum")
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 255))
        self.assertEqual(result.getpixel((0, 168)), (255, 255, 255, 255))
        self.assertEqual(set(result.getchannel("A").tobytes()), {255})

    def test_small_capture_or_non_square_crop_cannot_be_upscaled_as_hd(self):
        image = Image.new("RGBA", (1024, 1024))
        guide = native_circle()
        for crop in ([0, 0, 160, 160], [0, 0, 200, 220], [-1, 0, 200, 201]):
            with self.assertRaises(ValueError):
                compose_atlas(image, image, crop, guide, game="xd")
        with self.assertRaisesRegex(ValueError, "GPU1024"):
            compose_atlas(image.resize((256, 256)), image, [0, 0, 200, 200], guide, game="xd")


if __name__ == "__main__":
    unittest.main()
