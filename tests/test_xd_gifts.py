"""Regression coverage for independent XD reward text pointers and controls."""

import struct
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from colosseum_randomizer.engine.rebuild_iso import decoded_member
from colosseum_randomizer.xd_gifts import (_duking_script, _hordel_dialogue, _hordel_offer_script,
                                          _patch_duking, _patch_messages, _prize_label)
from tests.test_formats import fsys_fixture


class XDGiftTextTests(unittest.TestCase):
    def test_hordel_retargets_both_forms_and_keeps_other_trade_instructions(self):
        script = bytearray(b"\xFE" * 0x1900)
        expected = bytearray(script)
        for old, new, positions in ((175, 23, (0xF24, 0x1350, 0x18DC)),
                                     (176, 24, (0xF34, 0x1100, 0x1200, 0x1330, 0x18B8))):
            for offset in positions:
                struct.pack_into(">II", script, offset - 4, 0x02010000, old)
                struct.pack_into(">II", expected, offset - 4, 0x02010000, new)
        self.assertEqual(_hordel_offer_script(bytes(script), 23, 24), expected)
        script[0xF20] = 0
        with self.assertRaises(FormatError):
            _hordel_offer_script(bytes(script), 23, 24)

    def test_duking_checks_and_displays_the_new_requested_species(self):
        original = bytearray(0x1770)
        original[:4] = b"TCOD"
        original[0x16F0:0x16F4] = b"ARRY"
        expected = bytearray(original)
        cases = ((0xD30, 0xB48, 0xD1C, 1307, 1328, 1653, 332, 27, 1027),
                 (0xD74, 0xB98, 0xD60, 1213, 1283, 1654, 311, 187, 1187),
                 (0xDB8, 0xBE8, 0xDA4, 1246, 1194, 1655, 194, 382, 1304))
        for slot, (offer, first, second, reward, request, flag, old, new, name) in enumerate(cases):
            for target, species, shown in ((original, old, request), (expected, new, name)):
                for check in (first, second):
                    struct.pack_into(">II", target, check - 4, 0x02010000, species)
                struct.pack_into(">9I", target, offer - 4, 0x02010000, reward, 0x02010000, shown,
                                 0x02010000, flag, 0x0301FFFB, 0x0700031B, 0x06040000)
                struct.pack_into(">II", target, 0x1750 + slot * 8, 0x00010000, shown)
        requests = [(new, name) for *_, new, name in cases]
        rewards = [row[3] for row in cases]
        self.assertEqual(_duking_script(bytes(original), rewards, requests), expected)
        corrupt_array = bytearray(original)
        corrupt_array[0x1754] = 0xFF
        with self.assertRaisesRegex(FormatError, "remaining trade name"):
            _duking_script(bytes(corrupt_array), rewards, requests)
        original[0xB48] = 0xFF
        with self.assertRaises(FormatError):
            _duking_script(bytes(original), rewards, requests)

    def test_prize_label_can_grow_without_moving_an_aliased_string(self):
        original = "DITTO".encode("utf-16-be") + bytes(2)
        neighbor = "Ready?".encode("utf-16-be") + bytes(2)
        header = bytearray(40)
        struct.pack_into(">H2s", header, 4, 3, b"UK")
        struct.pack_into(">6I", header, 16, 0x7A49, 40, 0x7A50, 40, 0x7A51, 40 + len(original))
        source = bytes(header) + original + neighbor
        patched = _patch_messages(source, {
            0x7A49: lambda before: _prize_label(before, "DITTO", "BUTTERFREE"),
        })
        self.assertEqual(u32(patched, 20), len(source))
        self.assertEqual(patched[24:len(source)], source[24:])
        self.assertEqual(patched[len(source):], "BUTTERFREE".encode("utf-16-be") + bytes(2))

    def test_hordel_preserves_odd_offset_control_bytes_and_corrects_articles(self):
        examples = (("FR", "l'ELEKID", "le PAPILUSION", "PAPILUSION"),
                    ("FR", "cet ELEKID", "ce PAPILUSION", "PAPILUSION"),
                    ("IT", "l'ELEKID", "lo SHUCKLE", "SHUCKLE"),
                    ("JP", "コンセント", "ピカチュウ", "ピカチュウ"))
        for language, original, expected, chosen in examples:
            with self.subTest(language=language, original=original):
                prefix, suffix = b"\xff\xff\x59", b"\xff\xff\x03\xff\xff\x4e\0\0"
                text = prefix + original.encode("utf-16-be") + suffix
                self.assertEqual(_hordel_dialogue(text, language, chosen),
                                 prefix + expected.encode("utf-16-be") + suffix)
        with self.assertRaises(FormatError):
            _hordel_dialogue(b"\xff\xff\x59\0\0", "UK", "BUTTERFREE")

    def test_duking_writes_only_received_name_ids_and_checks_trade_arguments(self):
        script = bytearray(0xDE0)
        script[:4] = b"TCOD"
        for offset, name, required, flag in ((0xD30, 1307, 1328, 1653), (0xD74, 1213, 1283, 1654),
                                              (0xDB8, 1246, 1194, 1655)):
            struct.pack_into(">9I", script, offset - 4, 0x02010000, name, 0x02010000, required,
                             0x02010000, flag, 0x0301FFFB, 0x0700031B, 0x06040000)

        def archive_for(payload):
            data = fsys_fixture(bytes(payload) + b"FSYS")
            struct.pack_into(">I", data, 0x80, 0x014F0E00)
            data[0xC0:0xCD] = b"M2_guild_1F_2"
            data[0xCD] = 0
            return bytes(data)

        output = _patch_duking(archive_for(script), [1001, 1004, 1007])
        member = parse_fsys(output)["members"][0]
        expected = bytearray(script)
        for offset, name in ((0xD30, 1001), (0xD74, 1004), (0xDB8, 1007)):
            struct.pack_into(">I", expected, offset, name)
        self.assertEqual(decoded_member(output, member), bytes(expected) + b"FSYS")
        struct.pack_into(">I", script, 0xD38, 1000)
        with self.assertRaises(FormatError):
            _patch_duking(archive_for(script), [1001, 1004, 1007])
