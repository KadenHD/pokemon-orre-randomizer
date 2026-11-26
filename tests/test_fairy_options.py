"""Fairy preset defaults and signed historical-profile compatibility."""
from dataclasses import asdict, fields, replace
import hashlib
import json
from pathlib import Path
import unittest

from orre_randomizer.challenges import decode_challenge, encode_challenge
from orre_randomizer.i18n import LANGUAGES, translate
from orre_randomizer.options import Options
from orre_randomizer.presets import recommended_preset, species_preset
from orre_randomizer.profiles import configuration_data, parse_profile, parse_xd_profile
from orre_randomizer.service import UserError
from orre_randomizer.settings_presentation import (
    configuration_review, effective_setting_names, effective_xd_setting_names, search_settings,
)
from orre_randomizer.xd import XDOptions


FIXTURES = Path(__file__).resolve().parent / 'fixtures/profiles'


def signed(payload):
    body = {key: value for key, value in payload.items() if key != 'configuration_sha256'}
    payload['configuration_sha256'] = hashlib.sha256(json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
    ).encode('utf-8')).hexdigest()
    return json.dumps(payload, ensure_ascii=False).encode('utf-8')


class FairyOptionTests(unittest.TestCase):
    def test_both_games_enable_fairy_in_randomizing_presets_and_keep_copy_unchanged(self):
        for options in (Options(), Options.none(), XDOptions(), XDOptions.unchanged()):
            self.assertIs(options.enable_fairy_type, False)
        for options in (Options.recommended(), recommended_preset(), species_preset(),
                        XDOptions.recommended(), XDOptions.species_only()):
            self.assertIs(options.enable_fairy_type, True)
            self.assertIs(replace(options, enable_fairy_type=False).enable_fairy_type, False)
        self.assertFalse(Options.none().has_changes)
        self.assertTrue(replace(Options.none(), enable_fairy_type=True).has_changes)

    def test_one_shared_independent_type_control_is_searchable_and_reviewed_in_six_languages(self):
        common = next(item for item in fields(Options) if item.name == 'enable_fairy_type')
        xd = next(item for item in fields(XDOptions) if item.name == 'enable_fairy_type')
        self.assertEqual(common.metadata, xd.metadata)
        self.assertEqual(common.metadata['group'], 'Types')
        for base, effective in ((Options.none(), effective_setting_names),
                                (XDOptions.unchanged(), effective_xd_setting_names)):
            self.assertNotIn('enable_fairy_type', effective(base))
            enabled = replace(base, enable_fairy_type=True)
            self.assertIn('enable_fairy_type', effective(enabled))
            for language in LANGUAGES:
                label = translate(common.metadata['label'], language)
                self.assertIn(label, configuration_review(enabled, language))
                matches = search_settings(label, language, options_type=type(base))
                self.assertIn('enable_fairy_type', [row['name'] for row in matches])

    def test_current_profiles_and_challenges_round_trip_an_enabled_option(self):
        for options, parser, game in ((Options.none(), parse_profile, 'colosseum'),
                                      (XDOptions.unchanged(), parse_xd_profile, 'xd')):
            options = replace(options, enable_fairy_type=True)
            payload = configuration_data('fairy-round-trip', options)
            restored = parser(json.dumps(payload).encode('utf-8'))
            self.assertEqual(restored.options, options)
            decoded_game, challenge = decode_challenge(encode_challenge(restored.seed, options))
            self.assertEqual(decoded_game, game)
            self.assertEqual(challenge.options, options)

    def test_real_v214_exports_import_without_enabling_fairy_or_changing_other_options(self):
        # Captured before adding this field, using the actual released v2.1.4 exporter.
        for game, parser in (('colosseum', parse_profile), ('xd', parse_xd_profile)):
            raw = (FIXTURES / f'{game}-v214.json').read_bytes()
            historical = json.loads(raw)
            if game == 'colosseum':
                self.assertEqual(historical['app_version'], '2.1.4')
            self.assertNotIn('enable_fairy_type', historical['options'])
            restored = parser(raw)
            self.assertIs(restored.options.enable_fairy_type, False)
            values = asdict(restored.options)
            values.pop('enable_fairy_type')
            self.assertEqual(json.loads(json.dumps(values)), historical['options'])
            self.assertEqual(restored.source_engine_version, historical['engine_version'])
            self.assertTrue(restored.engine_migration)

    def test_current_schema_requires_the_boolean_and_rejects_typed_lookalikes(self):
        for options, parser in ((Options.none(), parse_profile), (XDOptions.unchanged(), parse_xd_profile)):
            for value in (None, 0, 1, 'false', [], {}):
                payload = configuration_data('strict-fairy', options)
                payload['options']['enable_fairy_type'] = value
                with self.subTest(game=type(options).__name__, value=value), self.assertRaises(UserError):
                    parser(signed(payload))
            payload = configuration_data('missing-fairy', options)
            del payload['options']['enable_fairy_type']
            with self.assertRaises(UserError):
                parser(signed(payload))

    def test_historical_engine_cannot_claim_fairy_support_even_with_a_valid_digest(self):
        for game, parser in (('colosseum', parse_profile), ('xd', parse_xd_profile)):
            for invalid in (True, 0, None, 'false'):
                payload = json.loads((FIXTURES / f'{game}-v214.json').read_bytes())
                payload['options']['enable_fairy_type'] = invalid
                with self.subTest(game=game, value=invalid), self.assertRaises(UserError):
                    parser(signed(payload))


if __name__ == '__main__':
    unittest.main()
