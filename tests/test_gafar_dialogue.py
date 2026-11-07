import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.gafar_dialogue import _victory_line


class GafarDialogueTests(unittest.TestCase):
    def test_two_species_keep_team_order_and_following_page(self):
        end = b"\xff\xff\x03" + "Suite.".encode("utf-16-be") + b"\xff\xff\x02\0\0"
        original = "GAFAR: Tu as rétamé mon CHUCHMUR...".encode("utf-16-be") + end
        expected = "GAFAR: ÉVOLI et NIDORAN♀ K.O. !".encode("utf-16-be") + end
        self.assertEqual(_victory_line(original, "FR", "CHUCHMUR", "ÉVOLI", "NIDORAN♀"), expected)

    def test_identical_species_keep_original_sentence_structure(self):
        end = b"\xff\xff\x03\xff\xff\x02\0\0"
        original = "Tu as battu mon CHUCHMUR !".encode("utf-16-be") + end
        expected = "Tu as battu mon ÉVOLI !".encode("utf-16-be") + end
        self.assertEqual(_victory_line(original, "FR", "CHUCHMUR", "ÉVOLI", "ÉVOLI"), expected)

    def test_rejects_unexpected_message(self):
        original = "Autre réplique.".encode("utf-16-be") + b"\xff\xff\x03\xff\xff\x02\0\0"
        with self.assertRaises(FormatError):
            _victory_line(original, "FR", "CHUCHMUR", "ÉVOLI", "NIDORAN♀")
