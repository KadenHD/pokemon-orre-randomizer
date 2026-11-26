"""Native Fairy resource bindings, padding and independent HD registration."""
from __future__ import annotations

from pathlib import Path
import unittest

from orre_randomizer.artwork import _png_pixels, _texture
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.fairy_badges import (
    LANGUAGES, SIZES, SMALL_SIZE, LARGE_RESOURCES, SMALL_RESOURCES,
    badge_png, native_texture, hd_texture, hd_overrides, append_badges,
)
from orre_randomizer.fairy_runtime import DEFAULT_BADGE_RESOURCES, DEFAULT_SMALL_BADGE_RESOURCES
from tests.test_castform_resources import archive


class FairyBadgeBindings(unittest.TestCase):
    def test_runtime_resource_contract_matches_each_authored_locale(self):
        self.assertEqual(LARGE_RESOURCES, DEFAULT_BADGE_RESOURCES)
        self.assertEqual(SMALL_RESOURCES, DEFAULT_SMALL_BADGE_RESOURCES)
        self.assertEqual(len(set((*LARGE_RESOURCES.values(), *SMALL_RESOURCES.values()))), 12)

    def test_all_native_and_hd_pixels_have_exact_crops_and_transparent_padding(self):
        for game in SIZES:
            for language in LANGUAGES:
                for small in ((False, True) if game == 'xd' else (False,)):
                    with self.subTest(game=game, language=language, small=small):
                        size = SMALL_SIZE if small else SIZES[game]
                        dimensions = (32, 32) if small else (128, 32)
                        native = _texture(native_texture(game, language, small=small), dimensions)
                        hd = _png_pixels(hd_texture(game, language, small=small), tuple(v * 4 for v in dimensions))
                        for factor, pixels in ((1, native), (4, hd)):
                            expected = _png_pixels(badge_png(game, language, small=small, hd=factor == 4), tuple(v * factor for v in size))
                            width, height = (value * factor for value in dimensions)
                            crop_width, crop_height = (value * factor for value in size)
                            for y in range(height):
                                row = pixels[y * width * 4:(y + 1) * width * 4]
                                if y < crop_height:
                                    self.assertEqual(row[:crop_width * 4], expected[y * crop_width * 4:(y + 1) * crop_width * 4])
                                    self.assertEqual(row[crop_width * 4:], bytes((width - crop_width) * 4))
                                else:
                                    self.assertEqual(row, bytes(width * 4))
                        self.assertTrue(any(native))

    def test_native_append_preserves_all_existing_compressed_members_and_binds_all_locales(self):
        for game in SIZES:
            original = archive([(0x12341200, 'native_texture', bytes(128)),
                                (0x34560400, 'unrelated', b'original animation')], 0x600, game == 'xd')
            source = original
            for language in LANGUAGES:
                source, report = append_badges(source, game, language)
                self.assertTrue(report['original_members_preserved'])
            members = parse_fsys(source)['members']
            for old in parse_fsys(original)['members']:
                member = next(row for row in members if row['identifier_raw'] == old['identifier_raw'])
                self.assertEqual(source[member['offset']:member['offset'] + member['stored_size']],
                                 original[old['offset']:old['offset'] + old['stored_size']])
            for language in LANGUAGES:
                for small, resources in ((False, LARGE_RESOURCES), *(([(True, SMALL_RESOURCES)]) if game == 'xd' else [])):
                    member = next(row for row in members if int(row['identifier_raw'], 16) == resources[language])
                    self.assertEqual(decoded_member(source, member), native_texture(game, language, small=small))
            with self.assertRaises(FormatError):
                append_badges(source, game, 'en')

    def test_hd_keys_cover_all_native_bindings_without_runtime_locale_dependencies(self):
        from orre_randomizer.hd_overlays import dolphin_texture_name
        for game in SIZES:
            actual = hd_overrides(game)
            expected = {}
            for language in LANGUAGES:
                for small in ((False, True) if game == 'xd' else (False,)):
                    width, height = (32, 32) if small else (128, 32)
                    native = native_texture(game, language, small=small)
                    expected[dolphin_texture_name(width, height, 6, native[128:])] = hd_texture(game, language, small=small)
            self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
