import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer.xd_battle_rules import DPKM_MOVES
from orre_randomizer.xd_story import (
    TRAINER_REMARK_REWRITES, hordel_candidates, trainer_dialogue_edits, tutorial_candidates,
)


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
