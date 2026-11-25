"""Genuine v2.1.1 exports retain settings across the Chobin progression fix.

The fixture was exported before the revision by modules verified byte for byte
(LF-normalized) against the published v2.1.1 commit. Its creation report is a
real fresh-start report reduced to parser inputs, with no paths or save data.
"""
from dataclasses import asdict
import json
from pathlib import Path
import unittest

from orre_randomizer import profiles, xd
from orre_randomizer.challenges import decode_challenge
from orre_randomizer.service import UserError


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/profiles/xd-v211.json').read_text('utf-8'))


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


class V211XDProfileMigrationTests(unittest.TestCase):
    def test_old_signed_presets_keep_all_settings_and_the_exact_seed(self):
        for name, payload in FIXTURE['profiles'].items():
            with self.subTest(preset=name):
                old = profiles.parse_xd_profile(encoded(payload))
                self.assertEqual(old.source_engine_version, 'xd-native-capture-tutorial-v18')
                self.assertTrue(old.engine_migration)
                self.assertEqual(old.seed, payload['seed'])
                self.assertEqual(json.loads(json.dumps(asdict(old.options))), payload['options'])
                current = profiles.configuration_data(old.seed, old.options)
                self.assertEqual(current['engine_version'], xd.VERSION)
                self.assertNotEqual(current['engine_version'], payload['engine_version'])
                self.assertEqual(profiles.parse_xd_profile(encoded(current)).options, old.options)
                self.assertFalse(profiles.parse_xd_profile(encoded(current)).engine_migration)

    def test_old_real_creation_report_keeps_its_region_and_options(self):
        payload = FIXTURE['creation_report']
        report = profiles.parse_creation_report(encoded(payload), is_xd=True)
        self.assertEqual(report.region.game_id, payload['game_id'])
        self.assertEqual(report.source_sha256, payload['source_sha256'])
        self.assertEqual(report.profile.seed, payload['seed'])
        self.assertEqual(json.loads(json.dumps(asdict(report.profile.options))), payload['options'])
        self.assertTrue(report.profile.engine_migration)

    def test_old_challenge_codes_still_require_their_exact_engine(self):
        for name, code in FIXTURE['challenges'].items():
            with self.subTest(preset=name), self.assertRaises(UserError):
                decode_challenge(code)
