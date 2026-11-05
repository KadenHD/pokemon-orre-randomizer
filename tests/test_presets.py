"""Shared balance policy and compatibility with published RC2 preset exports."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import unittest

from orre_randomizer.presets import recommended_preset, species_preset
from orre_randomizer.profiles import load_profile, parse_profile, parse_xd_profile, PREVIOUS_XD_QOL_ENGINE
from orre_randomizer.xd import XDOptions


FIXTURES = Path(__file__).parent / "fixtures/presets"
# Exported by the published RC2 source archive, SHA-256:
# 34cabf07dc669ee998728da8228167054aec4150adb5207c567e63ccc4206629.
SCOPE_FIELDS = {"randomize_trainer_moves", "randomize_starter_moves", "randomize_gift_moves",
                "randomize_learnsets", "randomize_tm_moves", "tm_compatibility_mode",
                "randomize_field_items", "randomize_shop_items"}


class PresetTests(unittest.TestCase):
    def test_modes_differ_only_in_move_tm_and_item_randomization(self):
        for recommended, species in ((recommended_preset(), species_preset()),
                                     (XDOptions.recommended(), XDOptions.species_only())):
            with self.subTest(game=type(recommended).__name__):
                full, limited = asdict(recommended), asdict(species)
                self.assertEqual({key for key in full if full[key] != limited[key]}, SCOPE_FIELDS)
                for name in SCOPE_FIELDS - {"tm_compatibility_mode"}:
                    self.assertTrue(full[name], name)
                    self.assertFalse(limited[name], name)
                self.assertEqual((full["tm_compatibility_mode"], limited["tm_compatibility_mode"]),
                                 ("type", "original"))

    def test_common_defaults_match_between_games(self):
        for colosseum, xd in ((recommended_preset(), XDOptions.recommended()),
                              (species_preset(), XDOptions.species_only())):
            first, second = asdict(colosseum), asdict(xd)
            self.assertEqual({k: first[k] for k in first.keys() & second.keys()},
                             {k: second[k] for k in first.keys() & second.keys()})
            for name in ("balance_species", "diverse_story_families", "boss_team_variety", "custom_shinies"):
                self.assertTrue(first[name], name)
            self.assertEqual(first["shiny_chance_percent"], 5.0)
            for name in ("trainer_level_multiplier", "experience_multiplier", "purification_multiplier",
                         "capture_rate_multiplier"):
                self.assertEqual(first[name], 1, name)
            self.assertTrue(colosseum.starter_balance_pair)
            self.assertTrue(colosseum.starter_distinct_families)
            self.assertTrue(colosseum.starter_complementary_types)
            self.assertFalse(xd.randomize_tutorial_shadow)
            self.assertFalse(xd.randomize_hordel_gift)

    def test_published_rc2_exports_keep_every_original_option(self):
        for game in ("colosseum", "xd"):
            for mode in ("moves", "species"):
                path = FIXTURES / f"rc2-{game}-{mode}.json"
                payload = json.loads(path.read_text("utf-8"))
                profile = load_profile(path, is_xd=game == "xd")
                self.assertEqual(json.loads(json.dumps(asdict(profile.options))), payload["options"])
                self.assertEqual(profile.seed, "rc2-preset-compatibility")
                # New presets must never be substituted for imported RC values.
                if game == "colosseum" and mode == "species":
                    self.assertFalse(profile.options.balance_species)
                    self.assertFalse(profile.options.starter_balance_pair)
                if game == "xd":
                    self.assertFalse(profile.options.boss_team_variety)

    def test_rc1_profile_version_and_previous_xd_engine_remain_accepted(self):
        for game in ("colosseum", "xd"):
            payload = json.loads((FIXTURES / f"rc2-{game}-species.json").read_text("utf-8"))
            expected = payload["options"]
            if game == "colosseum":
                payload["app_version"] = "0.21.0rc1"
            if game == "xd":
                payload["engine_version"] = PREVIOUS_XD_QOL_ENGINE
            payload.pop("configuration_sha256")
            payload["configuration_sha256"] = hashlib.sha256(json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False).encode("utf-8")).hexdigest()
            parser = parse_xd_profile if game == "xd" else parse_profile
            actual = parser(json.dumps(payload).encode("utf-8"))
            self.assertEqual(json.loads(json.dumps(asdict(actual.options))), expected)
