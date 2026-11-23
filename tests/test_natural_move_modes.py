"""Regression cases from player reports: species moves and unrestricted starters."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import unittest

from orre_randomizer import xd
from orre_randomizer.challenges import encode_challenge, decode_challenge
from orre_randomizer.move_modes import natural_moves
from orre_randomizer.options import Options
from orre_randomizer.profiles import (configuration_data, parse_profile, parse_xd_profile,
    PREVIOUS_MOVE_MODES_ENGINE, PREVIOUS_XD_MOVE_MODES_ENGINE, _canonical)
from orre_randomizer.service import UserError, validate_options

ROOT = Path(__file__).resolve().parents[1]


class NaturalMoveModes(unittest.TestCase):
    def test_species_moves_replace_the_predecessor_without_a_random_draw(self):
        # Registeel replacing Sunkern must not inherit its single Absorb slot.
        learned = ((1, 153), (1, 232), (9, 174), (17, 276), (25, 246), (33, 334))
        moves = {153, 232, 174, 276, 246, 334, 71}
        self.assertEqual(natural_moves(learned, 20, [71, 0, 0, 0], moves), [153, 232, 174, 276])
        self.assertEqual(natural_moves(learned, 30, [71, 0, 0, 0], moves), [232, 174, 276, 246])

    def test_shadow_and_special_slots_survive_and_duplicate_learning_is_ordered(self):
        learnset = ((1, 33), (2, 39), (3, 33), (4, 44), (20, 98))
        self.assertEqual(natural_moves(learnset, 10, [355, 1, 0, 65535], {1, 33, 39, 44, 98}),
                         [355, 33, 44, 65535])
        self.assertEqual(natural_moves(((1, 150),), 10, [33, 39, 44, 28], {33, 39, 44, 28, 150}),
                         [150, 0, 0, 0])

    def test_all_three_modes_validate_and_round_trip_for_both_games(self):
        for defaults in (Options.none(), xd.XDOptions.unchanged()):
            for mode in (False, "natural", True):
                value = replace(defaults, randomize_trainer_moves=mode,
                    randomize_starter_moves=mode, randomize_gift_moves=mode)
                parsed = xd.validate_options(value) if isinstance(value, xd.XDOptions) else validate_options(value)
                self.assertEqual(parsed, value)
                self.assertEqual(decode_challenge(encode_challenge("exact seed", value))[1].options, value)
            for bad in (1, 0, "false", "random", None):
                invalid = replace(defaults, randomize_trainer_moves=bad)
                with self.assertRaises(UserError):
                    xd.validate_options(invalid) if isinstance(invalid, xd.XDOptions) else validate_options(invalid)

    def test_previous_engine_profiles_keep_boolean_settings_and_show_migration(self):
        for defaults, previous, parser in ((Options.none(), PREVIOUS_MOVE_MODES_ENGINE, parse_profile),
                                          (xd.XDOptions.unchanged(), PREVIOUS_XD_MOVE_MODES_ENGINE, parse_xd_profile)):
            payload = configuration_data("old run", defaults)
            payload["engine_version"] = previous
            if "app_version" in payload:
                payload["app_version"] = "2.0.5"
            payload.pop("configuration_sha256")
            payload["configuration_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
            profile = parser(_canonical(payload))
            self.assertIs(profile.options.randomize_trainer_moves, False)
            self.assertTrue(profile.engine_migration)

    def test_cli_keeps_boolean_aliases_and_accepts_the_three_readable_modes(self):
        import argparse
        from orre_randomizer.cli import add_options
        for kind, prefix in ((Options, ""), (xd.XDOptions, "xd-")):
            parser = argparse.ArgumentParser()
            add_options(parser, kind, prefix)
            name = prefix.replace("-", "_") + "randomize_trainer_moves"
            argument = "--" + prefix + "randomize-trainer-moves"
            for word, expected in (("original", False), ("natural", "natural"), ("random", True)):
                self.assertEqual(getattr(parser.parse_args([argument, word]), name), expected)
            self.assertIs(getattr(parser.parse_args([argument]), name), True)
            self.assertIs(getattr(parser.parse_args(["--no-" + argument[2:]]), name), False)


class NativeXDStarterRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_xd_legendary_shadows import XDNativeLegendaryShadowsTests as Source
        Source.setUpClass()
        cls.species, cls.edges, cls.families = Source.species, Source.edges, Source.families
        cls.rel, cls.symbols = Source.rel, Source.symbols
        cls.decks = Source.decks
        with Source.iso.open("rb") as stream:
            stream.seek(struct.unpack_from(">I", Source.boot, 0x420)[0])
            cls.dol = stream.read(xd.REGIONS["GXXP01"].dol_size)

    def test_beldum_metang_and_magikarp_work_without_random_starting_moves(self):
        from orre_randomizer.xd_species_gameplay import XDMoveRandomizer
        for national, expected in ((374, 36), (375, 36), (129, 150)):
            for mode in (False, "natural"):
                with self.subTest(national=national, mode=mode):
                    options = replace(xd.XDOptions.unchanged(), randomize_starter=True, starter_species=national,
                        allow_gen1=True, allow_gen2=True, allow_gen3=True, randomize_starter_moves=mode,
                        starter_stage="any", starter_three_stage_families=False)
                    mover = XDMoveRandomizer(self.rel, self.symbols, self.species, options)
                    result, row = xd._starter(self.dol, xd.STARTERS["GXXP01"], "reddit-regression",
                        self.species, self.edges, self.families, set(self.species), options, mover)
                    self.assertEqual(self.species[row["species"]][0], national)
                    self.assertEqual(row["moves"], [expected, 0, 0, 0])
                    self.assertEqual([struct.unpack_from(">H", result, xd.STARTERS["GXXP01"] + 0x12 + 4 * i)[0]
                                      for i in range(4)], row["moves"])

    def test_native_story_opponents_get_the_replacement_species_moves(self):
        from orre_randomizer.xd_battle_rules import apply_deck_rules, DPKM_MOVES
        from orre_randomizer.xd_species_gameplay import XDMoveRandomizer
        native = self.decks["DeckData_Story.bin"]
        slots = xd._shadow_slots(self.decks["DeckData_DarkPokemon.bin"])
        options = replace(xd.XDOptions.unchanged(), randomize_trainers=True,
            randomize_trainer_moves="natural", allow_gen1=True, allow_gen2=True, allow_gen3=True,
            balance_species=False)
        seed = "reddit-native-species-moves"
        changed, _ = xd._deck(native, "Story", slots, seed, self.species, self.families, set(), options)
        mover = XDMoveRandomizer(self.rel, self.symbols, self.species, options)
        result, report = apply_deck_rules(native, changed, "Story", slots, seed, options,
            move_randomizer=mover, edges=self.edges, protected_shadows=set(xd.PROTECTED_SHADOWS))
        start = 0x20 + struct.unpack_from(">I", native, 0x14)[0]
        self.assertGreater(len(report["trainer_move_edits"]), 100)
        for row in report["trainer_move_edits"]:
            at = start + row["index"] * 0x20
            species = struct.unpack_from(">H", result, at)[0]
            slots = [i for i, move in enumerate(row["before"]) if move == 0 or move in mover.catalog]
            last = {move: ordinal for ordinal, (level, move) in enumerate(self.species[species][3])
                    if 0 < level <= result[at + 2] and move in mover.catalog}
            learned = sorted(last, key=last.get)[-len(slots):] if slots else []
            expected = list(row["before"])
            for i, move in zip(slots, learned + [0] * (len(slots) - len(learned)), strict=True):
                expected[i] = move
            self.assertEqual(row["after"], expected)
            self.assertEqual([struct.unpack_from(">H", result, at + field)[0] for field in DPKM_MOVES], row["after"])


@unittest.skipUnless((ROOT / "game/sys/main.dol").is_file(), "requires local original Colosseum data")
class NativeColosseumStarterRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from orre_randomizer.engine.randomize_trainers import original_common
        cls.rel = original_common(ROOT / "game")[2]
        cls.dol = (ROOT / "game/sys/main.dol").read_bytes()

    def test_beldum_metang_and_magikarp_are_accepted_with_both_nonrandom_modes(self):
        from orre_randomizer.engine.gameplay_rules import apply_dol_rules
        for national in (374, 375, 129):
            for mode in (False, "natural"):
                with self.subTest(national=national, mode=mode):
                    options = replace(Options.none(), starter_umbreon=True, starter_umbreon_species=national,
                        allow_gen1=True, allow_gen2=True, allow_gen3=True, starter_stage="any",
                        randomize_starter_moves=mode, starter_three_stage_families=False)
                    result, report = apply_dol_rules(self.dol, self.dol, self.rel, self.rel, "reddit-regression", options)
                    row = next(r for r in report["specials"] if r["key"] == "umbreon")
                    if mode == "natural":
                        self.assertIn("moves", row)
                        if national == 374:
                            self.assertEqual(row["moves"], [36, 0, 0, 0])
                        if national == 129:
                            self.assertEqual(row["moves"], [150, 33, 0, 0])
                    self.assertNotEqual(result, self.dol)

    def test_native_opponents_get_the_replacement_species_moves(self):
        from orre_randomizer.engine.gameplay_rules import apply_rel_rules, expanded_layout, move_catalog
        from orre_randomizer.engine.species_rules import species_catalog
        from orre_randomizer.engine.inspect_tables import u16
        options = replace(Options.none(), randomize_trainers=True, randomize_trainer_moves="natural",
                          allow_gen1=True, allow_gen2=True, allow_gen3=True, balance_species=False)
        result, report = apply_rel_rules(self.rel, self.rel, "reddit-native-species-moves", options)
        tables = expanded_layout(self.rel)
        catalog, valid = species_catalog(self.rel, tables), move_catalog(self.rel, tables)
        self.assertGreater(len(report["trainer_move_edits"]), 100)
        changed_species = 0
        for row in report["trainer_move_edits"]:
            at = tables["trainer_pokemon"]["offset"] + row["index"] * tables["trainer_pokemon"]["stride"]
            changed_species += u16(self.rel, at + 0xA) != row["species"]
            slots = [i for i, move in enumerate(row["before"]) if move == 0 or move in valid]
            last = {move: ordinal for ordinal, (level, move) in enumerate(catalog[row["species"]]["learnset"])
                    if 0 < level <= row["level"] and move in valid}
            learned = sorted(last, key=last.get)[-len(slots):] if slots else []
            expected = list(row["before"])
            for i, move in zip(slots, learned + [0] * (len(slots) - len(learned)), strict=True):
                expected[i] = move
            self.assertEqual(row["after"], expected)
        self.assertGreater(changed_species, 100)


if __name__ == "__main__":
    unittest.main()
