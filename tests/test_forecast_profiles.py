"""Old ability draws import as settings without claiming current-engine identity."""
from dataclasses import asdict, replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer import __version__, xd
from orre_randomizer.engine.regions import REGIONS
from orre_randomizer.options import Options
from orre_randomizer.profiles import (
    PREVIOUS_PRESERVED_ENGINE, PREVIOUS_XD_PRESERVED_ENGINE, parse_creation_report,
    parse_profile, parse_xd_profile, save_profile,
)
from orre_randomizer.service import ENGINE_VERSION, UserError


def encode(payload):
    return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")


def sign(payload):
    values = {key: value for key, value in payload.items() if key != "configuration_sha256"}
    canonical = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                           allow_nan=False).encode("utf-8")
    payload["configuration_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def profile_payload(is_xd, preserved):
    options = xd.XDOptions.recommended() if is_xd else Options.recommended()
    options = replace(options, randomize_preserved_properties=preserved)
    with tempfile.TemporaryDirectory() as folder:
        return save_profile(Path(folder) / "profile.json", "Forecast-seed", options), options


class ForecastProfileTests(unittest.TestCase):
    payload = staticmethod(profile_payload)

    def test_previous_complete_profiles_preserve_both_property_choices(self):
        for is_xd in (False, True):
            parser = parse_xd_profile if is_xd else parse_profile
            previous = PREVIOUS_XD_PRESERVED_ENGINE if is_xd else PREVIOUS_PRESERVED_ENGINE
            for preserved in (False, True):
                with self.subTest(xd=is_xd, preserved=preserved):
                    payload, options = self.payload(is_xd, preserved)
                    payload["engine_version"] = previous
                    imported = parser(encode(sign(payload)))
                    self.assertEqual(imported.options, options)
                    self.assertEqual(imported.seed, "Forecast-seed")
                    self.assertEqual(imported.source_engine_version, previous)
                    self.assertTrue(imported.engine_migration)
                    with tempfile.TemporaryDirectory() as folder:
                        exported = save_profile(Path(folder) / "current.json", imported.seed, imported.options)
                    current = parser(encode(exported))
                    self.assertEqual(current.options, options)
                    self.assertEqual(current, imported)
                    self.assertFalse(current.engine_migration)
                    self.assertEqual(current.source_engine_version, xd.VERSION if is_xd else ENGINE_VERSION)

    def test_previous_and_current_schemas_require_the_preservation_choice(self):
        for is_xd in (False, True):
            parser = parse_xd_profile if is_xd else parse_profile
            for previous in (False, True):
                payload, _ = self.payload(is_xd, False)
                if previous:
                    payload["engine_version"] = PREVIOUS_XD_PRESERVED_ENGINE if is_xd else PREVIOUS_PRESERVED_ENGINE
                payload["options"].pop("randomize_preserved_properties")
                with self.subTest(xd=is_xd, previous=previous), self.assertRaises(UserError):
                    parser(encode(sign(payload)))

    def test_published_xd_weather_profiles_and_reports_keep_explicit_settings(self):
        previous = "xd-castform-weather-portraits-v15"
        region = xd.REGIONS["GXXP01"]
        for preserved in (False, True):
            payload, options = self.payload(True, preserved)
            payload.update(app_version="2.0.4", engine_version=previous)
            with self.subTest(preserved=preserved):
                imported = parse_xd_profile(encode(sign(payload)))
                self.assertEqual(imported.options, options)
                self.assertEqual(imported.source_engine_version, previous)
                self.assertTrue(imported.engine_migration)
                report = dict(application_version="2.0.4", engine_version=previous,
                              game_id=region.game_id, revision=region.revision,
                              source_sha256="a" * 64, source_iso_sha256=region.iso_sha256,
                              seed=imported.seed, options=asdict(options))
                self.assertEqual(parse_creation_report(encode(report), is_xd=True).profile,
                                 imported)
                with tempfile.TemporaryDirectory() as folder:
                    exported = save_profile(Path(folder) / "current.json",
                                            imported.seed, imported.options)
                self.assertEqual(exported["engine_version"], xd.VERSION)
                self.assertFalse(parse_xd_profile(encode(exported)).engine_migration)
                payload["options"].pop("randomize_preserved_properties")
                with self.assertRaises(UserError):
                    parse_xd_profile(encode(sign(payload)))

    def test_previous_reports_retain_engine_identity_and_complete_settings(self):
        for is_xd in (False, True):
            _, options = self.payload(is_xd, False)
            region = xd.REGIONS["GXXP01"] if is_xd else REGIONS[0]
            for previous in (False, True):
                current = xd.VERSION if is_xd else ENGINE_VERSION
                engine = (PREVIOUS_XD_PRESERVED_ENGINE if is_xd else PREVIOUS_PRESERVED_ENGINE) if previous else current
                report = dict(application_version=__version__, engine_version=engine,
                              game_id=region.game_id, revision=region.revision,
                              source_sha256="a" * 64, source_iso_sha256=region.iso_sha256,
                              seed="Forecast-seed", options=asdict(options))
                with self.subTest(xd=is_xd, previous=previous):
                    profile = parse_creation_report(encode(report), is_xd=is_xd).profile
                    self.assertEqual(profile.options, options)
                    self.assertEqual(profile.source_engine_version, engine)
                    self.assertEqual(profile.engine_migration, previous)

    def test_published_v2_colosseum_profiles_remain_supported_after_the_bump(self):
        for version in ("2.0.0", "2.0.1", "2.0.2"):
            payload, options = self.payload(False, False)
            payload.update(app_version=version, engine_version=PREVIOUS_PRESERVED_ENGINE)
            with self.subTest(version=version):
                imported = parse_profile(encode(sign(payload)))
                self.assertEqual(imported.options, options)
                self.assertTrue(imported.engine_migration)

    def test_cli_warns_about_old_engine_in_each_language_without_changing_settings(self):
        from orre_randomizer.cli import main
        from orre_randomizer.i18n import LANGUAGES, translate
        from orre_randomizer.profiles import ENGINE_MIGRATION
        for is_xd in (False, True):
            for previous in (False, True):
                payload, options = self.payload(is_xd, False)
                if previous:
                    payload["engine_version"] = PREVIOUS_XD_PRESERVED_ENGINE if is_xd else PREVIOUS_PRESERVED_ENGINE
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "profile.json"
                    path.write_bytes(encode(sign(payload)))
                    for language in LANGUAGES:
                        command = ["randomizer", "source.iso", "result.iso", "--profile", str(path),
                                   "--journal-language", language]
                        if is_xd:
                            command.extend(("--game", "xd"))
                        with self.subTest(xd=is_xd, previous=previous, language=language), \
                             patch("sys.argv", command), patch("sys.stdout", new_callable=io.StringIO), \
                             patch("sys.stderr", new_callable=io.StringIO) as stderr, \
                             patch("orre_randomizer.cli.randomize", return_value={}) as randomize:
                            self.assertEqual(main(), 0)
                            expected = translate(ENGINE_MIGRATION, language)
                            self.assertEqual(expected in stderr.getvalue(), previous)
                            if language != "fr":
                                self.assertNotEqual(expected, ENGINE_MIGRATION)
                            self.assertEqual(randomize.call_args.kwargs["xd_options"] if is_xd
                                             else randomize.call_args.args[3], options)


if __name__ == "__main__":
    unittest.main()
