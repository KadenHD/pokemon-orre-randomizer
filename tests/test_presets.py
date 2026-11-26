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
                "randomize_field_items", "randomize_shop_items", "randomize_held_items"}


class PresetTests(unittest.TestCase):
    def test_modes_differ_only_in_move_tm_and_item_randomization(self):
        for recommended, species in ((recommended_preset(), species_preset()),
                                     (XDOptions.recommended(), XDOptions.species_only())):
            with self.subTest(game=type(recommended).__name__):
                full, limited = asdict(recommended), asdict(species)
                self.assertEqual({key for key in full if full[key] != limited[key]}, SCOPE_FIELDS)
                for name in SCOPE_FIELDS - {"tm_compatibility_mode"}:
                    self.assertTrue(full[name], name)
                    if name in {"randomize_trainer_moves", "randomize_starter_moves", "randomize_gift_moves"}:
                        self.assertEqual(limited[name], "natural", name)
                    else:
                        self.assertFalse(limited[name], name)
                self.assertEqual((full["tm_compatibility_mode"], limited["tm_compatibility_mode"]),
                                 ("random", "original"))

    def test_common_defaults_match_between_games(self):
        for colosseum, xd in ((recommended_preset(), XDOptions.recommended()),
                              (species_preset(), XDOptions.species_only())):
            first, second = asdict(colosseum), asdict(xd)
            self.assertEqual({k: first[k] for k in first.keys() & second.keys()},
                             {k: second[k] for k in first.keys() & second.keys()})
            for name in ("randomize_abilities", "diverse_story_families", "boss_team_variety", "custom_shinies", "enable_fairy_type"):
                self.assertTrue(first[name], name)
            self.assertFalse(first["balance_species"])
            self.assertEqual(first["starter_stage"], "any")
            self.assertFalse(first["starter_three_stage_families"])
            self.assertFalse(first["keep_capture_items"])
            self.assertTrue(first["shop_keep_capture_items"])
            self.assertFalse(first["items_similar_value"])
            self.assertFalse(first["ensure_stab_move"])
            self.assertEqual(first["moves_mode"], "chaos")
            self.assertFalse(first["randomize_types"])
            self.assertFalse(first["allow_legendaries"])
            self.assertFalse(first["randomize_legendary_shadows"])
            self.assertEqual(first["shiny_chance_percent"], 5.0)
            for name in ("trainer_level_multiplier", "experience_multiplier", "purification_multiplier",
                         "capture_rate_multiplier"):
                self.assertEqual(first[name], 1, name)
            self.assertFalse(colosseum.starter_balance_pair)
            self.assertTrue(colosseum.starter_distinct_families)
            self.assertFalse(colosseum.starter_complementary_types)
            self.assertTrue(xd.randomize_tutorial_shadow)
            self.assertTrue(xd.poke_spots_full_pokedex)
            self.assertTrue(xd.custom_shadow_shinies)
            self.assertTrue(xd.custom_poke_spot_shinies)
            self.assertEqual(xd.poke_spot_shiny_chance_percent, 5.0)
            self.assertTrue(xd.randomize_hordel_gift)

    def test_bonus_quest_is_enabled_with_its_authored_team_only_in_desktop_presets(self):
        from orre_randomizer.options import Options
        for options in (recommended_preset(), species_preset()):
            self.assertTrue(options.postgame_shadow_lugia)
            self.assertFalse(options.postgame_randomize_team)
            self.assertFalse(options.postgame_randomize_lugia)
            self.assertFalse(options.randomize_legendary_shadows)
        for options in (Options(), Options.recommended(), Options.none()):
            self.assertFalse(options.postgame_shadow_lugia)
            self.assertFalse(options.postgame_randomize_team)
            self.assertFalse(options.postgame_randomize_lugia)

    def test_story_gift_defaults_change_only_randomizing_desktop_presets(self):
        for name in ("randomize_tutorial_shadow", "randomize_hordel_gift"):
            self.assertTrue(getattr(XDOptions.recommended(), name))
            self.assertTrue(getattr(XDOptions.species_only(), name))
            self.assertFalse(getattr(XDOptions.unchanged(), name))
            self.assertFalse(getattr(XDOptions(), name))
        self.assertFalse(XDOptions().poke_spots_full_pokedex)

    def test_published_rc2_exports_keep_every_original_option(self):
        for game in ("colosseum", "xd"):
            for mode in ("moves", "species"):
                path = FIXTURES / f"rc2-{game}-{mode}.json"
                payload = json.loads(path.read_text("utf-8"))
                profile = load_profile(path, is_xd=game == "xd")
                expected = dict(payload["options"])
                expected['enable_fairy_type'] = False
                expected["randomize_legendary_shadows"] = True
                expected["randomize_preserved_properties"] = True
                expected["keep_shadow_lugia_after_purification"] = False
                expected["shop_keep_capture_items"] = False
                if game == "colosseum":
                    expected["legacy_shop_scope"] = True
                    expected["postgame_shadow_lugia"] = False
                    expected["postgame_randomize_team"] = payload["options"]["randomize_trainers"]
                    expected["postgame_randomize_lugia"] = False
                if game == "xd":
                    expected["poke_spots_full_pokedex"] = False
                    expected["custom_shadow_shinies"] = False
                    expected["custom_poke_spot_shinies"] = False
                    expected["poke_spot_shiny_chance_percent"] = 5.0
                self.assertEqual(json.loads(json.dumps(asdict(profile.options))), expected)
                self.assertEqual(profile.seed, "rc2-preset-compatibility")
                # New presets must never be substituted for imported RC values.
                if game == "colosseum" and mode == "species":
                    self.assertFalse(profile.options.balance_species)
                    self.assertFalse(profile.options.starter_balance_pair)
                if game == "xd":
                    self.assertFalse(profile.options.boss_team_variety)
                    self.assertFalse(profile.options.randomize_tutorial_shadow)

    def test_rc1_profile_version_and_previous_xd_engine_remain_accepted(self):
        for game in ("colosseum", "xd"):
            payload = json.loads((FIXTURES / f"rc2-{game}-species.json").read_text("utf-8"))
            expected = dict(payload["options"])
            expected['enable_fairy_type'] = False
            expected["randomize_legendary_shadows"] = True
            expected["randomize_preserved_properties"] = True
            expected["keep_shadow_lugia_after_purification"] = False
            expected["shop_keep_capture_items"] = False
            if game == "colosseum":
                expected["legacy_shop_scope"] = True
                expected["postgame_shadow_lugia"] = False
                expected["postgame_randomize_team"] = payload["options"]["randomize_trainers"]
                expected["postgame_randomize_lugia"] = False
            if game == "colosseum":
                payload["app_version"] = "0.21.0rc1"
            if game == "xd":
                payload["engine_version"] = PREVIOUS_XD_QOL_ENGINE
                expected["poke_spots_full_pokedex"] = False
                expected["custom_shadow_shinies"] = False
                expected["custom_poke_spot_shinies"] = False
                expected["poke_spot_shiny_chance_percent"] = 5.0
            payload.pop("configuration_sha256")
            payload["configuration_sha256"] = hashlib.sha256(json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False).encode("utf-8")).hexdigest()
            parser = parse_xd_profile if game == "xd" else parse_profile
            actual = parser(json.dumps(payload).encode("utf-8"))
            self.assertEqual(json.loads(json.dumps(asdict(actual.options))), expected)

    def test_v100_colosseum_profile_keeps_its_saved_values(self):
        payload = json.loads((FIXTURES / "rc2-colosseum-species.json").read_text("utf-8"))
        payload["app_version"] = "1.0.0"
        expected = dict(payload["options"], postgame_shadow_lugia=False, randomize_preserved_properties=True,
                        enable_fairy_type=False,
                        shop_keep_capture_items=False,
                        legacy_shop_scope=True,
                        keep_shadow_lugia_after_purification=False,
                        randomize_legendary_shadows=True,
                        postgame_randomize_team=payload["options"]["randomize_trainers"],
                        postgame_randomize_lugia=False)
        payload.pop("configuration_sha256")
        payload["configuration_sha256"] = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode("utf-8")).hexdigest()
        actual = parse_profile(json.dumps(payload).encode("utf-8"))
        self.assertEqual(json.loads(json.dumps(asdict(actual.options))), expected)


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "game/files/common.fsys").is_file(), "requires the original local Colosseum image")
class NativePresetEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from orre_randomizer.engine.randomize_trainers import original_common

        cls.rel = original_common(ROOT / "game")[2]
        cls.dol = (ROOT / "game/sys/main.dol").read_bytes()

    def test_randomized_encounters_exclude_legendaries_but_keep_native_shadow_legends(self):
        from orre_randomizer.engine.gameplay_rules import apply_story_rules, apply_dol_rules, expanded_layout
        from orre_randomizer.engine.inspect_tables import u16
        from orre_randomizer.engine.randomize_trainers import randomize_rel
        from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL, species_catalog
        from orre_randomizer.service import transform_rel, transform_dol

        tables = expanded_layout(self.rel)
        catalog = species_catalog(self.rel, tables)
        records = randomize_rel(self.rel, "legendary-defaults")[1]["trainer_pokemon_changes"]
        for options in (recommended_preset(), species_preset()):
            with self.subTest(moves=options.randomize_trainer_moves):
                base_rel = transform_rel(self.rel, "legendary-defaults", options)[0]
                base_dol = transform_dol(self.dol, self.rel, "legendary-defaults", options)[0]
                rel, _, starters, gifts = apply_story_rules(
                    self.rel, base_rel, self.dol, base_dol, "legendary-defaults", options)
                _, report = apply_dol_rules(self.dol, base_dol, self.rel, rel,
                    "legendary-defaults", options, starter_result=starters, gift_picks=gifts)
                self.assertEqual(len(report["specials"]), 6)
                for row in report["specials"]:
                    self.assertNotIn(catalog[row["species"]]["national_dex"], LEGENDARY_NATIONAL, row["key"])
                for row in records:
                    chosen = u16(rel, row["offset"] + 0xA)
                    if row["shadow_id"] and catalog[row["old_species_index"]]["national_dex"] in LEGENDARY_NATIONAL:
                        self.assertEqual(chosen, row["old_species_index"])
                    else:
                        self.assertNotIn(catalog[chosen]["national_dex"], LEGENDARY_NATIONAL, row["index"])

    def test_preset_changes_reach_abilities_shadow_held_items_and_treasures(self):
        from orre_randomizer.engine.gameplay_rules import apply_rel_rules, damaging, expanded_layout, move_catalog
        from orre_randomizer.engine.inspect_tables import u16
        from orre_randomizer.engine.item_rules import apply_field_items, item_catalog
        from orre_randomizer.engine.randomize_trainers import randomize_rel
        from orre_randomizer.engine.species_rules import species_catalog
        from orre_randomizer.service import transform_rel

        _, plan = randomize_rel(self.rel, "preset-effects")
        base, _ = transform_rel(self.rel, "preset-effects", recommended_preset())
        tables = expanded_layout(self.rel)
        before = species_catalog(self.rel, tables)
        held_shadows = {row["index"] for row in plan["trainer_pokemon_changes"]
                        if row["shadow_id"] and u16(self.rel, row["offset"] + 0x12) not in (0, 0xFFFF)}
        self.assertTrue(held_shadows)
        catalogue = item_catalog(self.dol)
        for full, options in ((True, recommended_preset()), (False, species_preset())):
            with self.subTest(full=full):
                current, report = apply_rel_rules(self.rel, base, "preset-effects", options)
                after = species_catalog(current, tables)
                self.assertGreater(sum(row["abilities"] != after[index]["abilities"]
                                       for index, row in before.items()), 300)
                self.assertTrue(all(row["types"] == after[index]["types"] for index, row in before.items()))
                self.assertTrue(any(abs(before[row["old_species_index"]]["total"]
                                        - after[u16(current, row["offset"] + 0xA)]["total"])
                                    > max(50, before[row["old_species_index"]]["total"] // 5)
                                    for row in plan["trainer_pokemon_changes"]))
                changed_items = {row["index"] for row in report["held_item_edits"]}
                self.assertEqual(changed_items & held_shadows, held_shadows if full else set())
                _, treasure = apply_field_items(self.rel, current, self.dol, "preset-effects", options)
                if full:
                    moves = move_catalog(self.rel, tables)
                    self.assertTrue(any(not any(damaging(moves[move])
                                               and moves[move]["type"] in after[row["species"]]["types"]
                                               for move in row["after"])
                                        for row in report["trainer_move_edits"]))
                    self.assertGreater(treasure["changed_records"], 38)
                    self.assertTrue(any(catalogue[row["before"]]["category"] == "balls"
                                        and row["before"] != row["after"] for row in treasure["edits"]))
                else:
                    self.assertFalse(treasure["edits"])
