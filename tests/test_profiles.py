"""Shareable profiles round-trip without paths, code, or silent rule changes."""
from dataclasses import asdict, replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from colosseum_randomizer import __version__
from colosseum_randomizer.options import Options
from colosseum_randomizer.profiles import (MAX_PROFILE_BYTES, load_profile, parse_profile,
                                           profile_data, save_profile, NEW_POLICY_FIELDS, SHINY_FIELDS,
                                           EVENT_GIFT_FIELDS, V15_FIELDS)
from colosseum_randomizer.service import UserError
from colosseum_randomizer.profiles import LEGACY_GAME, parse_creation_report
from colosseum_randomizer.engine.regions import REGIONS


# Exported by the preserved v0.14.0 public source distribution, not generated
# from the current Options class. Archive SHA-256:
# ad93e8816a16d3a19188711ef94f3cb2ceada6aed02ce0c07700163d897de18c.
V014_EXPORTED_PROFILE = b'''{
  "format": "colosseum-randomizer-profile",
  "schema_version": 1,
  "app_version": "0.14.0",
  "engine_version": "regional-purification-gifts-v14",
  "game": {
    "id": "pokemon-colosseum",
    "roms": [
      {"id": "GC6P01", "revision": 0, "iso_sha256": "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9"},
      {"id": "GC6E01", "revision": 0, "iso_sha256": "78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5"},
      {"id": "GC6J01", "revision": 0, "iso_sha256": "17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f"}
    ]
  },
  "seed": "regional-v014-archive",
  "options": {
    "randomize_trainers": true, "randomize_shadows": true, "unique_shadows": true,
    "trainer_theme_mode": "none", "trainer_force_evolved": false, "trainer_evolution_level": 40,
    "custom_shinies": true, "seeded_shinies": true, "shiny_chance_percent": 25,
    "starter_umbreon": true, "starter_espeon": true, "starter_stage": "base",
    "starter_three_stage_families": true, "starter_balance_pair": true,
    "starter_distinct_families": true, "starter_complementary_types": true,
    "gift_plusle": true, "gift_hooh": true, "event_celebi": true, "event_pikachu": true,
    "accessible_event_gifts": true, "event_pikachu_purifications": 7,
    "event_celebi_purifications": 25, "event_pikachu_level": 30, "event_celebi_level": 67,
    "evolve_trade": true, "evolve_trade_items": true, "evolve_coquiperl": true,
    "evolve_day_night": true, "evolve_beauty": true, "stones_phenac": true,
    "stones_pyrite": true, "readable_stone_names": true,
    "randomize_trainer_moves": true, "randomize_starter_moves": true,
    "randomize_gift_moves": true, "randomize_learnsets": true,
    "ensure_damaging_move": true, "ensure_stab_move": true, "no_duplicate_moves": true,
    "ban_self_destruct": true, "ban_ohko": true, "moves_mode": "balanced",
    "randomize_abilities": false, "abilities_family_consistent": true,
    "randomize_stats": false, "preserve_stat_totals": true,
    "randomize_types": false, "types_family_consistent": true,
    "allow_gen1": true, "allow_gen2": true, "allow_gen3": true, "allow_legendaries": true,
    "excluded_species": [], "excluded_types": [], "balance_species": true,
    "randomize_held_items": false, "useful_held_items_only": true,
    "trainer_level_multiplier": 1.0, "capture_rate_multiplier": 1.0, "minimum_catch_rate": 0,
    "randomize_tm_moves": true, "tm_compatibility_mode": "type", "tm_ensure_offensive": true,
    "randomize_field_items": true, "items_similar_value": true, "keep_capture_items": true,
    "randomize_shop_items": true, "shop_keep_healing": true, "boss_stronger": false,
    "boss_team_variety": true, "boss_shadow_legendary_mode": "any",
    "boss_shadow_power_mode": "global", "boss_shadow_min_bst": 0
  },
  "configuration_sha256": "793f63e1ae76e499676d992bf0a22523f47b253edad8f08371ee00bf28a8a765"
}'''


def archived_v015_payload():
    """Exact export of the preserved v0.15 public sources, independent of Options.

    Archive SHA-256: 6b16e8958200264b61d6d916d54842ad240300738f1fa5e189a22ae8eee8a204.
    Its 74 legacy values match the fixed v0.14 fixture; all eight new values
    below are deliberately nonneutral. The digest is the old export's digest.
    """
    payload = json.loads(V014_EXPORTED_PROFILE)
    payload.update(app_version='0.15.0', engine_version='details-and-progression-v15',
                   seed='details-v015-archive',
                   configuration_sha256='930ad11d619b6284a5aa6f92f195702ba10b545cffe7f2c149b35972de2fba9a')
    payload['options'].update(starter_umbreon_species=94, starter_espeon_species=208,
        progressive_levels=True, early_level_multiplier=.9, mid_level_multiplier=1.1,
        late_level_multiplier=1.25, experience_multiplier=2.5, purification_multiplier=3)
    return payload


class ProfileTests(unittest.TestCase):
    def encode(self, payload):
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def sign(self, payload):
        payload.pop("configuration_sha256", None)
        payload["configuration_sha256"] = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        return payload

    def old_payload(self, seed, options, version="0.7.0"):
        payload = profile_data(seed, options)
        payload["app_version"] = version
        payload["game"] = dict(LEGACY_GAME)
        payload["engine_version"] = ("native-text-and-boss-rules-v8" if version == "0.7.0"
                                     else "starter-shadow-boss-rules-v7")
        for name in NEW_POLICY_FIELDS | SHINY_FIELDS | EVENT_GIFT_FIELDS | V15_FIELDS | {"diverse_story_families"}:
            payload["options"].pop(name)
        payload["options"]["starter_base_forms"] = payload["options"].pop("starter_stage") == "base"
        payload["options"].pop("starter_three_stage_families")
        if version != "0.7.0":
            payload["options"].pop("readable_stone_names")
        return self.sign(payload)

    def test_roundtrip_all_options_and_unicode_seed_without_personal_paths(self):
        options = replace(Options.recommended(), starter_stage="first",
                          boss_shadow_legendary_mode="preserve", boss_shadow_min_bst=400)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ma-partie.json"
            save_profile(path, "étoile-🌟", options)
            profile = load_profile(path)
            self.assertEqual(profile.seed, "étoile-🌟")
            self.assertEqual(asdict(profile.options), asdict(options))
            content = path.read_text("utf-8")
            self.assertNotIn(folder, content)
            self.assertNotIn("destination", content)
            self.assertNotIn("dolphin", content.lower())
            self.assertLess(path.stat().st_size, 8192)

    def test_no_changes_profile_stays_no_changes(self):
        parsed = parse_profile(self.encode(profile_data("vanilla", Options.none())))
        self.assertFalse(parsed.options.has_changes)
        self.assertEqual(parsed.options, Options.none())

    def test_v010_profile_preserves_all_choices_and_shiny_rate(self):
        options = replace(Options.recommended(), custom_shinies=True, shiny_chance_percent=100)
        for version in ('0.10.0', '0.10.1'):
            with self.subTest(version=version):
                payload = profile_data("same-draw", options)
                payload.update(app_version=version, engine_version="native-shiny-generation-v11")
                payload["game"] = dict(LEGACY_GAME)
                payload["options"].pop("seeded_shinies")
                for name in EVENT_GIFT_FIELDS | V15_FIELDS | {"diverse_story_families"}:
                    payload["options"].pop(name)
                self.sign(payload)
                parsed = parse_profile(self.encode(payload))
                self.assertEqual(parsed.options, replace(options, seeded_shinies=False, accessible_event_gifts=False))
                self.assertEqual(parsed.seed, "same-draw")

    def test_v011_and_v012_profiles_keep_seeded_draw_and_disable_new_gifts(self):
        options = replace(Options.recommended(), custom_shinies=True,
                          shiny_chance_percent=25, seeded_shinies=True,
                          boss_shadow_min_bst=400, starter_stage="first")
        for version in ("0.11.0", "0.12.0"):
            with self.subTest(version=version):
                payload = profile_data("same-seeded-draw", options)
                payload.update(app_version=version, engine_version="seeded-shiny-status-v12")
                payload["game"] = dict(LEGACY_GAME)
                for name in EVENT_GIFT_FIELDS | V15_FIELDS | {"diverse_story_families"}:
                    payload["options"].pop(name)
                self.sign(payload)
                parsed = parse_profile(self.encode(payload))
                self.assertEqual(parsed.options, replace(options, accessible_event_gifts=False))
                self.assertEqual(parsed.seed, "same-seeded-draw")
                exported = profile_data(parsed.seed, parsed.options)
                self.assertEqual(parse_profile(self.encode(exported)), parsed)
                payload["seed"] = "tampered"
                with self.assertRaises(UserError):
                    parse_profile(self.encode(payload))

    def test_older_profiles_reject_signed_new_gift_fields_instead_of_enabling_them(self):
        payload = profile_data("old-format", Options.recommended())
        payload.update(app_version="0.12.0", engine_version="seeded-shiny-status-v12")
        payload["game"] = dict(LEGACY_GAME)
        for name in V15_FIELDS | {"diverse_story_families"}:
            payload["options"].pop(name)
        self.sign(payload)
        with self.assertRaises(UserError):
            parse_profile(self.encode(payload))

    def test_v09_profile_migrates_without_enabling_shinies_and_rejects_tampering(self):
        payload = profile_data("old-seed", Options.recommended())
        payload.update(app_version="0.9.0", engine_version="trainer-policies-and-exclusions-v10")
        payload["game"] = dict(LEGACY_GAME)
        for name in SHINY_FIELDS | EVENT_GIFT_FIELDS | V15_FIELDS | {"diverse_story_families"}:
            payload["options"].pop(name)
        self.sign(payload)
        parsed = parse_profile(self.encode(payload))
        self.assertEqual(parsed.options, replace(Options.recommended(), seeded_shinies=False, accessible_event_gifts=False))
        self.assertFalse(parsed.options.custom_shinies)
        payload["options"]["starter_stage"] = "any"
        with self.assertRaises(UserError):
            parse_profile(self.encode(payload))

    def test_shiny_rate_round_trip_and_strict_validation(self):
        for chance in (0, 0.0122, 1, 50.125, 100):
            options = replace(Options.none(), custom_shinies=True, shiny_chance_percent=chance)
            self.assertTrue(options.has_changes)
            self.assertEqual(parse_profile(self.encode(profile_data("shiny", options))).options, options)
        for chance in (True, -0.1, 100.1, "1", float("inf")):
            with self.subTest(chance=chance), self.assertRaises(UserError):
                profile_data("invalid", replace(Options.none(), custom_shinies=True, shiny_chance_percent=chance))

    def test_legacy_profiles_keep_verified_digest_and_disable_new_text_rule(self):
        expected = replace(Options.recommended(), starter_stage="any", starter_three_stage_families=False,
                           readable_stone_names=False, seeded_shinies=False, accessible_event_gifts=False)
        for version in ('0.5.0', '0.6.0', '0.6.1'):
            with self.subTest(version=version):
                payload = self.old_payload("shared-05-seed", expected, version=version)
                parsed = parse_profile(self.encode(payload))
                self.assertEqual(parsed.seed, "shared-05-seed")
                self.assertEqual(parsed.options, expected)
                payload["seed"] = "tampered"
                with self.assertRaises(UserError):
                    parse_profile(self.encode(payload))

    def test_v07_stage_migration_preserves_rules_and_reexports_without_new_defaults(self):
        for stage in ("base", "any"):
            options = replace(Options.recommended(), starter_stage=stage, starter_three_stage_families=False)
            payload = self.old_payload("shared-07-seed", options)
            parsed = parse_profile(self.encode(payload))
            self.assertEqual(parsed.options, replace(options, seeded_shinies=False, accessible_event_gifts=False))
            self.assertEqual(parse_profile(self.encode(profile_data(parsed.seed, parsed.options))), parsed)
            payload["options"]["starter_base_forms"] = "false"
            with self.assertRaises(UserError):
                parse_profile(self.encode(self.sign(payload)))

    def test_digest_stable_for_same_configuration_and_sensitive_to_rules_seed(self):
        base = profile_data("stable", Options.recommended())
        self.assertEqual(base, profile_data("stable", Options.recommended()))
        self.assertNotEqual(base["configuration_sha256"], profile_data("another", Options.recommended())["configuration_sha256"])
        self.assertNotEqual(base["configuration_sha256"], profile_data("stable", Options())["configuration_sha256"])

    def test_v013_profile_preserves_every_choice_including_event_gifts(self):
        options = replace(Options.recommended(), custom_shinies=True, shiny_chance_percent=25,
                          event_celebi_level=67, event_pikachu_purifications=7)
        payload = profile_data('pal-v013', options)
        payload.update(app_version='0.13.0', engine_version='purification-gifts-v13', game=dict(LEGACY_GAME))
        for name in V15_FIELDS | {"diverse_story_families"}:
            payload['options'].pop(name)
        parsed = parse_profile(self.encode(self.sign(payload)))
        self.assertEqual(parsed.options, options)
        self.assertEqual(parsed.seed, 'pal-v013')
        exported = profile_data(parsed.seed, parsed.options)
        self.assertEqual(parse_profile(self.encode(exported)), parsed)
        self.assertEqual({r['id'] for r in exported['game']['roms']}, {'GC6P01', 'GC6E01', 'GC6J01'})

    def test_archived_v014_profile_keeps_every_legacy_choice_and_new_fields_neutral(self):
        payload = json.loads(V014_EXPORTED_PROFILE)
        self.assertEqual(len(payload['options']), 74)
        parsed = parse_profile(V014_EXPORTED_PROFILE)
        self.assertEqual(parsed.seed, payload['seed'])
        actual = json.loads(self.encode(asdict(parsed.options)))
        self.assertEqual({name: actual[name] for name in payload['options']}, payload['options'])
        self.assertEqual({name: actual[name] for name in V15_FIELDS}, {
            'starter_umbreon_species': 0, 'starter_espeon_species': 0,
            'progressive_levels': False, 'early_level_multiplier': 1.0,
            'mid_level_multiplier': 1.0, 'late_level_multiplier': 1.0,
            'experience_multiplier': 1.0, 'purification_multiplier': 1,
        })
        exported = profile_data(parsed.seed, parsed.options)
        self.assertEqual(exported['app_version'], __version__)
        self.assertEqual(parse_profile(self.encode(exported)), parsed)

    def test_archived_v014_digest_is_checked_and_signed_unknown_fields_remain_rejected(self):
        payload = json.loads(V014_EXPORTED_PROFILE)
        payload['options']['event_pikachu_purifications'] = 8
        with self.assertRaises(UserError):
            parse_profile(self.encode(payload))
        for name in (*sorted(V15_FIELDS), 'unknown'):
            with self.subTest(field=name):
                payload = json.loads(V014_EXPORTED_PROFILE)
                payload['options'][name] = getattr(Options(), name, True)
                with self.assertRaises(UserError):
                    parse_profile(self.encode(self.sign(payload)))
        payload = json.loads(V014_EXPORTED_PROFILE)
        payload['options'].pop('event_pikachu_level')
        with self.assertRaises(UserError):
            parse_profile(self.encode(self.sign(payload)))

    def test_current_profile_roundtrip_preserves_all_eight_nondefault_v015_fields(self):
        options = replace(Options.recommended(), starter_umbreon_species=152,
            starter_espeon_species=155, progressive_levels=True, early_level_multiplier=0.9,
            mid_level_multiplier=1.1, late_level_multiplier=1.3,
            experience_multiplier=2.5, purification_multiplier=3)
        payload = profile_data('new-settings', options)
        self.assertTrue(V15_FIELDS <= payload['options'].keys())
        self.assertEqual(parse_profile(self.encode(payload)).options, options)
        previous = json.loads(self.encode(payload))
        previous.update(app_version='0.17.4', engine_version='details-and-progression-v15')
        previous['options'].pop('diverse_story_families')
        self.assertEqual(parse_profile(self.encode(self.sign(previous))).options, options)
        enabled = replace(options, diverse_story_families=True)
        self.assertEqual(parse_profile(self.encode(profile_data('new-rule', enabled))).options, enabled)
        for name in V15_FIELDS | {"diverse_story_families"}:
            with self.subTest(missing=name):
                incomplete = json.loads(self.encode(payload))
                incomplete['options'].pop(name)
                with self.assertRaises(UserError):
                    parse_profile(self.encode(self.sign(incomplete)))

    def test_v008_stage_profile_retains_stage_without_enabling_later_features(self):
        options = replace(Options.recommended(), starter_stage='first',
                          starter_three_stage_families=False)
        payload = profile_data('stage-v008', options)
        payload.update(app_version='0.8.0', engine_version='starter-evolution-stages-v9',
                       game=dict(LEGACY_GAME))
        for name in NEW_POLICY_FIELDS | SHINY_FIELDS | EVENT_GIFT_FIELDS | V15_FIELDS | {"diverse_story_families"}:
            payload['options'].pop(name)
        parsed = parse_profile(self.encode(self.sign(payload)))
        self.assertEqual(parsed.options, replace(options, seeded_shinies=False,
                                                accessible_event_gifts=False))

    def test_archived_v015_import_keeps_all_82_values_and_disables_new_rule(self):
        from colosseum_randomizer.profiles import SCHEMA_VERSION
        from colosseum_randomizer.service import ENGINE_VERSION
        payload = archived_v015_payload()
        self.assertEqual(len(payload['options']), 82)
        parsed = parse_profile(self.encode(payload))
        self.assertEqual(parsed.seed, payload['seed'])
        self.assertEqual(json.loads(self.encode(asdict(parsed.options))), dict(payload['options'], diverse_story_families=False))
        exported = profile_data(parsed.seed, parsed.options)
        self.assertEqual(exported['app_version'], __version__)
        self.assertEqual(exported['engine_version'], ENGINE_VERSION)
        self.assertEqual(ENGINE_VERSION, 'story-family-diversity-v16')
        self.assertEqual(exported['schema_version'], SCHEMA_VERSION)
        self.assertEqual(SCHEMA_VERSION, 1)
        self.assertEqual(json.loads(self.encode(exported['options'])), dict(payload['options'], diverse_story_families=False))
        self.assertEqual(parse_profile(self.encode(exported)), parsed)

    def test_archived_v015_still_checks_digest_full_fields_and_typed_values(self):
        payload = archived_v015_payload()
        payload['options']['experience_multiplier'] = 3
        with self.assertRaises(UserError):
            parse_profile(self.encode(payload))
        for change in (
            lambda p: p['options'].pop('progressive_levels'),
            lambda p: p['options'].update(unknown=True),
            lambda p: p['options'].update(progressive_levels='false'),
            lambda p: p.update(engine_version='details-and-progression-v16'),
            lambda p: p.update(schema_version=2),
        ):
            payload = archived_v015_payload()
            change(payload)
            with self.assertRaises(UserError):
                parse_profile(self.encode(self.sign(payload)))

    def test_refuses_tampering_unknown_or_missing_fields_and_engine_versions(self):
        base = profile_data("stable", Options.recommended())
        for change in (lambda p: p.update(seed="edited"),
                       lambda p: p.update(engine_version="future"),
                       lambda p: p.update(app_version="0.1.0"),
                       lambda p: p.update(schema_version=True),
                       lambda p: p.update(extra="ignored?"),
                       lambda p: p["options"].pop("starter_stage"),
                       lambda p: p["options"].update(unknown=True),
                       lambda p: p["game"].update(revision=False),
                       lambda p: p["game"].update(id="GC6E01")):
            payload = json.loads(json.dumps(base))
            change(payload)
            with self.assertRaises(UserError):
                parse_profile(self.encode(payload))

    def test_refuses_invalid_typed_values_even_if_they_reach_validation(self):
        for name, value in (("starter_three_stage_families", "false"), ("starter_stage", "unknown"), ("minimum_catch_rate", True),
                            ("trainer_level_multiplier", 1e999), ("moves_mode", []),
                            ("boss_shadow_min_bst", -1), ("boss_shadow_power_mode", "unknown")):
            payload = profile_data("stable", Options.recommended())
            payload["options"][name] = value
            with self.assertRaises(UserError):
                parse_profile(self.encode(payload))

    def test_refuses_malformed_duplicate_oversized_and_non_profile_json(self):
        samples = (b"{", b"[]", b"null", b'{"seed":"a","seed":"b"}',
                   b'{"x":NaN}', b'{"x":Infinity}', b"\xff", b" " * (MAX_PROFILE_BYTES + 1),
                   b"[" * 2000 + b"]" * 2000)
        for content in samples:
            with self.subTest(content=content[:40]), self.assertRaises(UserError):
                parse_profile(content)

    def test_refuses_empty_and_overlong_seed_accepts_bom(self):
        for seed in ("", "  ", "é" * 129, "\ud800", None):
            with self.assertRaises(UserError):
                profile_data(seed, Options())
        payload = self.encode(profile_data("BOM", Options()))
        self.assertEqual(parse_profile(b"\xef\xbb\xbf" + payload).seed, "BOM")

    def test_export_never_overwrites_existing_file_or_rom_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "existing.json"
            path.write_bytes(b"original content")
            with self.assertRaises(UserError):
                save_profile(path, "seed", Options())
            self.assertEqual(path.read_bytes(), b"original content")
            with self.assertRaises(UserError):
                save_profile(Path(folder) / "original.iso", "seed", Options())

    def test_cli_profile_preserves_rules_and_accepts_explicit_overrides(self):
        from colosseum_randomizer.cli import main
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            options = replace(Options.recommended(), boss_shadow_power_mode="free")
            save_profile(path, "shared-seed", options)
            for extra, expected in (([], options), (["--no-randomize-tm-moves"], replace(options, randomize_tm_moves=False))):
                with patch("sys.argv", ["randomizer", "input.iso", "output.iso", "--profile", str(path), *extra]), \
                     patch("colosseum_randomizer.cli.randomize", return_value={}) as run, \
                     patch("sys.stdout", new_callable=io.StringIO):
                    self.assertEqual(main(), 0)
                    self.assertEqual(run.call_args.args[2:4], ("shared-seed", expected))


class CreationReportTests(unittest.TestCase):
    def test_current_and_archived_settings_are_restored_without_paths(self):
        region = REGIONS[2]
        options = replace(Options.recommended(), excluded_species=(1, 4), diverse_story_families=True)
        report = dict(application_version=__version__, engine_version="story-family-diversity-v16",
                      game_id=region.game_id, revision=region.revision,
                      source_sha256="a" * 64, source_iso_sha256=region.iso_sha256,
                      seed="シード 🌟", options=asdict(options),
                      source="never used", output="never used")
        result = parse_creation_report(json.dumps(report).encode())
        self.assertEqual((result.profile.seed, result.profile.options, result.region),
                         (report["seed"], options, region))
        with self.assertRaisesRegex(UserError, "version prise en charge"):
            parse_creation_report(json.dumps(dict(report, source_iso_sha256="b" * 64)).encode())
        with self.assertRaisesRegex(UserError, "incomplets"):
            parse_creation_report(json.dumps(dict(report, options={})).encode())

        previous = json.loads(V014_EXPORTED_PROFILE)
        report.update(application_version=previous["app_version"], engine_version=previous["engine_version"],
                      seed=previous["seed"], options=previous["options"])
        self.assertEqual(parse_creation_report(json.dumps(report).encode()).profile,
                         parse_profile(V014_EXPORTED_PROFILE))


if __name__ == "__main__":
    unittest.main()
