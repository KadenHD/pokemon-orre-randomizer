from pathlib import Path
import tempfile
import unittest

from orre_randomizer import hd_overlays as hd
from orre_randomizer.fairy_badges import (
    LANGUAGES, LARGE_RESOURCES, native_texture, hd_overrides, append_badges,
)
from tests.test_hd_overlays import archive, disc
from tests.test_castform_resources import archive as native_archive


class FairyHDBindings(unittest.TestCase):
    def test_all_six_languages_capture_real_native_resources_and_export_independent_x4(self):
        for game in ('colosseum', 'xd'):
            xd = game == 'xd'
            with self.subTest(game=game), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                common = native_archive([(0x12341200, 'retail_texture', bytes(128))], 0x600, xd)
                for language in LANGUAGES:
                    common, _ = append_badges(common, game, language)
                image = root / 'game.iso'
                original = disc(image, [('common.fsys', common)], xd=xd)
                target = root / 'assets'
                report = hd.capture_native_assets(image, target, is_xd=xd,
                    asset_context={'fairy': {'enabled': True}})
                self.assertEqual(report['fairy_badges']['resources'], 12 if xd else 6)
                self.assertFalse(report['fairy_badges']['native_bitmap_upscaled_for_hd'])
                prepared = hd.prepare_hd_overlays(target, target, pack_roots={})
                expected = {key + '.png': payload for key, payload in hd_overrides(game).items()}
                self.assertEqual({row['file'] for row in prepared['files']}, set(expected))
                self.assertFalse(prepared['missing_assets'])
                for name, payload in expected.items():
                    self.assertEqual((target / name).read_bytes(), payload)
                self.assertEqual(image.read_bytes(), original)

    def test_enabled_contract_rejects_a_missing_locale_or_changed_native_badge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / 'game.iso'
            original = native_texture('xd', 'fr')
            for payload in (original, original[:-1] + bytes([original[-1] ^ 1])):
                disc(image, [('common.fsys', archive([(LARGE_RESOURCES['fr'], 'orre_fairy_fr', payload)]))], xd=True)
                with self.assertRaises(hd.OverlayError):
                    hd.capture_native_assets(image, root / 'assets', is_xd=True,
                        asset_context={'fairy': {'enabled': True}})


if __name__ == '__main__':
    unittest.main()
