import struct
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer.xd_battle_rules import DPKM_MOVES
from orre_randomizer.xd_story import (
    TRAINER_REMARK_REWRITES, _tutorial_script, hordel_candidates, trainer_dialogue_edits,
    tutorial_candidates, validate_tutorial_matchup,
)
from orre_randomizer.engine.analyze_game import FormatError


class XDTrainerDialogueTests(unittest.TestCase):
    def test_skill_swap_line_survives_unrelated_changes_until_the_last_user_loses_it(self):
        original = bytearray(0xC8)
        struct.pack_into(">I", original, 0x14, 0x48)
        struct.pack_into(">HH", original, 0x3C, 1, 2)
        for slot, species in enumerate((1, 2), 1):
            entry = 0x68 + slot * 0x20
            struct.pack_into(">H", original, entry, species)
            struct.pack_into(">H", original, entry + DPKM_MOVES[0], 285)
        current = bytearray(original)
        struct.pack_into(">H", current, 0x88 + DPKM_MOVES[0], 33)
        species = {1: (1,), 2: (2,)}
        fixture = {"Colosseum": ((0, (1, 2), "fight_common.fsys", (0x5E48,)),)}
        with patch("orre_randomizer.xd_story._TRAINER_DIALOGUE", fixture):
            self.assertEqual(trainer_dialogue_edits("Colosseum", original, current, species, "GXXP01"), {})
            struct.pack_into(">H", current, 0xA8 + DPKM_MOVES[0], 33)
            edits = trainer_dialogue_edits("Colosseum", original, current, species, "GXXP01")
        self.assertEqual(set(edits), {"fight_common.fsys", *(f"fight_common_{lang}.fsys" for lang in ("fr", "ge", "it", "sp"))})
        self.assertTrue(all(set(remarks) == {0x5E48} for remarks in edits.values()))

    def test_two_page_remark_keeps_the_native_second_page_and_close_control(self):
        speaker = b"\xff\xff\x59"
        page = b"\xff\xff\x03" + speaker + ": I like them!".encode("utf-16-be")
        close = b"\xff\xff\x02\0\0"
        source = speaker + ": Dark and Rock are cool!".encode("utf-16-be") + page + close
        rewrite = TRAINER_REMARK_REWRITES[0x799A]
        english = rewrite(source, changes={}, language="UK")
        self.assertEqual(english, rewrite(source, changes={}, language="US"))
        self.assertTrue(english.endswith(page + close))
        self.assertTrue(english.startswith(speaker + ": I love battling with these two Pokémon!".encode("utf-16-be")))


class XDHordelTests(unittest.TestCase):
    def test_requires_a_base_form_with_one_accessible_evolution(self):
        families = {1: 1, 2: 1, 3: 1, 23: 23, 24: 23, 95: 95, 208: 95, 133: 133, 134: 133, 135: 133}
        edges = {1: [(0, 4, 16, 2)], 2: [(0, 4, 32, 3)], 23: [(0, 4, 22, 24)],
                 95: [(0, 6, 0, 208)], 133: [(0, 7, 1, 134), (0, 7, 2, 135)]}
        self.assertEqual(hordel_candidates(families, edges, families, accessible_evolutions=False), {23: 24})
        self.assertEqual(hordel_candidates(families, edges, families, accessible_evolutions=True), {23: 24, 95: 208})


class XDTutorialTests(unittest.TestCase):
    def test_only_compatible_tutorial_opponents_are_eligible(self):
        rows = {
            1: {"national_dex": 1, "types": (12, 3), "abilities": (65,), "total": 318},
            92: {"national_dex": 92, "types": (7, 3), "abilities": (26,), "total": 310},
            216: {"national_dex": 216, "types": (0,), "abilities": (53,), "total": 330},
            292: {"national_dex": 292, "types": (6, 7), "abilities": (25,), "total": 236},
        }
        regular = {"index": 33, "power": 35, "type": 0}
        explosion = {"index": 153, "power": 250, "type": 0}
        rules = SimpleNamespace(species=rows, catalog={33: regular, 153: explosion})
        self.assertEqual(tutorial_candidates({"moves": [33]}, rows, rules), [1])
        self.assertEqual(tutorial_candidates({"moves": [153]}, rows, rules), [])

    def test_fixed_teddiursa_is_checked_against_the_generated_starter_too(self):
        moves = {33: {"index": 33, "power": 35, "type": 0},
                 122: {"index": 122, "power": 20, "type": 7},
                 264: {"index": 264, "power": 150, "type": 1}}
        rules = SimpleNamespace(species={216: {"types": (0,), "abilities": (53,)}}, catalog=moves)
        for unusable in ([122], [264], []):
            with self.subTest(moves=unusable), self.assertRaises(FormatError):
                validate_tutorial_matchup({"moves": unusable}, 216, rules)
        validate_tutorial_matchup({"moves": [264, 33]}, 216, rules)

    def test_fixed_tutorial_uses_final_type_and_ability_immunities(self):
        attacks = {89: {"index": 89, "power": 100, "type": 4},
                   85: {"index": 85, "power": 95, "type": 13},
                   304: {"index": 304, "power": 90, "type": 0}}
        for target, move in (({"types": (2,), "abilities": (1,)}, 89),
                             ({"types": (0,), "abilities": (26,)}, 89),
                             ({"types": (4,), "abilities": (1,)}, 85),
                             ({"types": (0,), "abilities": (10,)}, 85),
                             ({"types": (0,), "abilities": (43,)}, 304),
                             ({"types": (0,), "abilities": (25,)}, 85)):
            rules = SimpleNamespace(species={216: target}, catalog=attacks)
            with self.subTest(target=target), self.assertRaises(FormatError):
                validate_tutorial_matchup({"moves": [move]}, 216, rules)

    def test_tutorial_script_patch_preserves_all_control_flow_and_state_operands(self):
        for game in ("GXXP01", "GXXE01", "GXXJ01"):
            offset = 0x816C if game == "GXXJ01" else 0x818C
            original = bytearray(b"\xFE" * (offset + 64))
            struct.pack_into(">7I", original, offset - 4, 0x02010000, 216, 0x02010000,
                             0x4E, 0x11030028, 0x0928001C, 0x06030000)
            expected = bytearray(original)
            struct.pack_into(">I", expected, offset, 95)
            self.assertEqual(_tutorial_script(bytes(original), game, 95), bytes(expected))


class NativeXDStoryFlowTests(unittest.TestCase):
    def test_native_gastly_starting_moves_cannot_pass_the_fixed_normal_tutorial_check(self):
        from orre_randomizer import xd
        from orre_randomizer.engine.analyze_game import parse_rel
        from orre_randomizer.engine.inspect_tables import rel_symbols
        from orre_randomizer.xd_species_gameplay import XDMoveRandomizer
        root = Path(__file__).resolve().parents[1] / "build/xd-validation"
        if not all((root / tag / "common_rel").exists() for tag in ("eu", "us", "jp")):
            self.skipTest("local extracted XD original tables are unavailable")
        for tag in ("eu", "us", "jp"):
            original = (root / tag / "common_rel").read_bytes()
            symbols = rel_symbols(original, parse_rel(original))
            species, _, _ = xd._species(original, symbols)
            rules = XDMoveRandomizer(original, symbols, species, xd.XDOptions.unchanged())
            ghost = next(index for index, row in species.items() if row[0] == 92)
            starter = {"moves": [move for level, move in species[ghost][3] if 0 < level <= 10]}
            self.assertIn(122, starter["moves"])
            with self.subTest(region=tag), self.assertRaises(FormatError):
                validate_tutorial_matchup(starter, 216, rules)
            self.assertTrue(tutorial_candidates(starter, species, rules))

    def test_native_trade_and_tutorial_scripts_keep_every_byte_outside_species_or_name_operands(self):
        from orre_randomizer.xd_gifts import _duking_script, _hordel_offer_script
        root = Path(__file__).resolve().parents[1] / "build/xd-research"
        if not all((root / tag / "S1_shop_1F.scd").exists() for tag in ("eu", "us", "jp")):
            self.skipTest("local extracted XD script originals are unavailable")
        for tag, game in (("eu", "GXXP01"), ("us", "GXXE01"), ("jp", "GXXJ01")):
            with self.subTest(region=tag):
                source = (root / tag / "S1_shop_1F.scd").read_bytes()
                output = _hordel_offer_script(source, 23, 24)
                allowed = {at + byte for at in (0xF24, 0x1350, 0x18DC, 0xF34, 0x1100, 0x1200, 0x1330, 0x18B8)
                           for byte in range(4)}
                self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(source, output))))
                source = (root / tag / "M2_guild_1F_2.scd").read_bytes()
                output = _duking_script(source, [1001, 1004, 1007], [(25, 1025), (133, 1133), (150, 1150)])
                words = (0xD30, 0xD74, 0xDB8, 0xB48, 0xD1C, 0xB98, 0xD60, 0xBE8, 0xDA4,
                         0xD38, 0xD7C, 0xDC0, 0x1754, 0x175C, 0x1764)
                allowed = {at + byte for at in words for byte in range(4)}
                self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(source, output))))
                source = (root / tag / "M5_labo_1F.scd").read_bytes()
                output = _tutorial_script(source, game, 95)
                at = 0x816C if game == "GXXJ01" else 0x818C
                self.assertEqual(source[:at], output[:at])
                self.assertEqual(source[at + 4:], output[at + 4:])
