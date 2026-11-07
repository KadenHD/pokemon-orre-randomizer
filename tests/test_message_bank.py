import struct
import unittest

from orre_randomizer.engine.message_bank import patch_messages, replace_names
from orre_randomizer.xd_story import TRAINER_REMARK_REWRITES


class MessageBankTests(unittest.TestCase):
    def test_swap_names_without_touching_controls_or_longer_names(self):
        first = "MEW et MEWTWO".encode("utf-16-be")
        second = "ÉVOLI".encode("utf-16-be")
        control = b"\xff\xff\x07\x02\xff\xff\x00"
        end = b"\xff\xff\x02\0\0"
        source = first + control + second + end
        expected = "ÉVOLI et MEWTWO".encode("utf-16-be") + control + "MEW".encode("utf-16-be") + end
        self.assertEqual(replace_names(source, {"MEW": "ÉVOLI", "ÉVOLI": "MEW"}, "FR"), expected)

    def test_menu_bank_preserves_original_records_and_unrelated_pointer(self):
        first = "MEW".encode("utf-16-be") + b"\0\0"
        second = "PIKACHU".encode("utf-16-be") + b"\0\0"
        bank = struct.pack(">IH2s8xIIII", 1, 2, b"FR", 10, 32, 20, 32 + len(first)) + first + second
        updated = patch_messages(bank, {10: lambda line: replace_names(line, {"MEW": "ÉVOLI"}, "FR")})
        self.assertEqual(updated[:20], bank[:20])
        self.assertEqual(struct.unpack_from(">I", updated, 20)[0], len(bank))
        self.assertEqual(updated[24:len(bank)], bank[24:])
        self.assertEqual(updated[len(bank):], "ÉVOLI".encode("utf-16-be") + b"\0\0")

    def test_mt_battle_remark_uses_both_final_species(self):
        speaker, line_break, end = b"\xff\xff\x59", b"\xff\xff\x00", b"\xff\xff\x02\0\0"
        source = (speaker + ": MORPHEO".encode("utf-16-be") + line_break
                  + "WAILORD".encode("utf-16-be") + end)
        updated = TRAINER_REMARK_REWRITES[0x7A0F](
            source, language="FR", changes={"MORPHEO": "ÉVOLI", "WAILORD": "WAILORD"}
        )
        expected = speaker + ": Mon duo, ÉVOLI et WAILORD !".encode("utf-16-be") + end
        self.assertEqual(updated, expected)

    def test_battle_introduction_keeps_its_bare_terminator(self):
        speaker, end = b"\xff\xff\x59", b"\0\0"
        source = speaker + "「あめよ　ふれ！".encode("utf-16-be") + end
        updated = TRAINER_REMARK_REWRITES[0x5E63](source, language="JP", changes={})
        expected = speaker + "「わたしのチームに　かてるかな？".encode("utf-16-be") + end
        self.assertEqual(updated, expected)
