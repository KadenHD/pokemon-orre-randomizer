"""Semantic color variants retain source identity, opacity and animation data."""
import hashlib
from pathlib import Path
import unittest

from orre_randomizer.castform_shiny_palette import (
    PALETTES, SOURCE_PKX, make_weather_shiny_pkx, map_rgb,
)
from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.hd_overlays import _dat_textures, _pkx_dat, _pixels, _texture_key


class WeatherShinyPaletteTests(unittest.TestCase):
    def test_face_palette_uses_modern_anchors_and_retains_neutral_eye_detail(self):
        for form, palette in PALETTES.items():
            with self.subTest(form=form):
                self.assertEqual(map_rgb(palette['source_head'], form, 'face'), palette['head'])
                self.assertEqual(map_rgb(palette['source_mask'], form, 'face'), palette['mask'])
                self.assertEqual(map_rgb(palette['source_mask'], form, 'mask'), palette['mask'])
                for value in (0, 32, 127, 255):
                    self.assertEqual(map_rgb((value,) * 3, form, 'face'), (value,) * 3)
                    self.assertEqual(map_rgb((value,) * 3, form, 'mask'), (value,) * 3)

    def test_blue_antialias_colors_do_not_extrapolate_into_magenta_fringes(self):
        # Actual native/HD rainy face samples that exposed the affine failure.
        for sample in ((0, 116, 210), (0, 110, 210)):
            self.assertEqual(map_rgb(sample, 'w', 'face'), (21, 137, 141))
        for form in ('w', 'i'):
            for warm in ((230, 80, 90), (180, 70, 50)):
                self.assertEqual(map_rgb(warm, form, 'face'), warm)

    def test_unrecognized_sources_and_already_authored_variants_are_rejected(self):
        for game, form in SOURCE_PKX:
            with self.subTest(game=game, form=form):
                with self.assertRaisesRegex(FormatError, 'source changed'):
                    make_weather_shiny_pkx(bytes(256), game=game, form=form)
        for game, form in [('other', 'f'), ('xd', 'x')]:
            with self.assertRaisesRegex(FormatError, 'Unknown weather'):
                make_weather_shiny_pkx(b'', game=game, form=form)

    def test_six_native_sources_retain_headers_footer_and_texture_alpha(self):
        root = Path(__file__).resolve().parents[1] / 'build/hd-deep-audit/portraits/models'
        sources = {(game, form): root / game / f'pkx_powalen_{form}.fsys' / f'powalen_{form}.pkx'
                   for game, form in SOURCE_PKX}
        if not all(path.is_file() for path in sources.values()):
            self.skipTest('Private exact native model fixtures are not distributed')
        for (game, form), path in sources.items():
            with self.subTest(game=game, form=form):
                source = path.read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), SOURCE_PKX[game, form])
                output, report = make_weather_shiny_pkx(source, game=game, form=form)
                self.assertEqual(len(output), len(source))
                original_dat, authored_dat = _pkx_dat(source, game == 'xd'), _pkx_dat(output, game == 'xd')
                offset = len(source) - len(original_dat)
                self.assertEqual(output[:offset + 32], source[:offset + 32])
                # Relocations, public symbols, motion schedules and PKX footer.
                end_of_colors = offset + 32 + u32(original_dat, 4)
                self.assertEqual(output[end_of_colors:], source[end_of_colors:])
                before = list(_dat_textures(original_dat))
                after = list(_dat_textures(authored_dat))
                self.assertEqual(len(before), len(after))
                for original, authored in zip(before, after, strict=True):
                    self.assertEqual((original.width, original.height, original.fmt),
                                     (authored.width, authored.height, authored.fmt))
                    self.assertEqual(_pixels(original)[3::4], _pixels(authored)[3::4])
                if form == 'f':
                    # Golden solar halo/reflection and specular alpha map stay native.
                    keys = {_texture_key(texture) for texture in after}
                    self.assertIn('tex1_64x64_365396ccc950f84d_14.png', keys)
                    self.assertIn('tex1_32x32_fca892c7108cd8b2_2.png', keys)
                self.assertTrue(report['geometry_animation_uv_footer_unchanged'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), SOURCE_PKX[game, form])
                with self.assertRaises(FormatError):
                    make_weather_shiny_pkx(output, game=game, form=form)


if __name__ == '__main__':
    unittest.main()
