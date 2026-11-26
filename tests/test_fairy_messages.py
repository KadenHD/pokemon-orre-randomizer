import hashlib
from itertools import product
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.fairy_messages import (
    ITEM_MESSAGE_IDS, ITEM_NAME_IDS, ITEM_DESCRIPTION_IDS, LANGUAGES, MOVE_DESCRIPTION_IDS,
    MOVE_NAME_IDS, TRANSFER_REFUSAL_ID, _transfer_messages, description_font,
    install_fairy_messages, message_bank, message_texts,
)
from orre_randomizer.fairy_data import move_description
from orre_randomizer.fairy_message_layout import LINE_BREAK, native_font_metrics
from tests.test_fairy_message_layout import font_dol


def two_font_dol():
    original = bytearray(font_dol())
    bank = bytearray(original[0x120:])
    struct.pack_into('>H', bank, 0, 1)
    original.extend(bytes(-len(original) % 4))
    original.extend(bank)
    struct.pack_into('>I', original, 0xAC, len(original) - 0x120)
    return bytes(original)


def bodies(data):
    count = struct.unpack_from('>H', data, 4)[0]
    entries = [struct.unpack_from('>II', data, 16 + 8 * index) for index in range(count)]
    return {identifier: data[position:entries[index + 1][1]]
            for index, (identifier, position) in enumerate(entries[:-1])}


class FairyMessageTests(unittest.TestCase):
    def test_both_games_wrap_all_languages_for_each_native_pane_without_changing_ui_prose(self):
        original = two_font_dol()
        for game_id, language in product(('GC6P01', 'GC6E01', 'GC6J01', 'GXXP01', 'GXXE01', 'GXXJ01'), LANGUAGES):
            with self.subTest(game_id=game_id, language=language):
                data = message_bank(language, original_dol=original, game_id=game_id)
                self.assertEqual(len(data) % 32, 0)
                self.assertEqual(struct.unpack_from('>H', data, 4)[0], 30)
                expected_font = description_font(game_id, language)
                actual_font = struct.unpack_from('>H', data, 6)[0] if game_id == 'GC6J01' else data[3]
                self.assertEqual(actual_font, expected_font)
                if game_id == 'GC6J01':
                    self.assertEqual(data[:4], bytes(4))
                    self.assertNotEqual(data[6:8], b'JP')
                actual = bodies(data)
                expected = message_texts(language)
                self.assertEqual(set(actual), set(expected))
                for identifier, body in actual.items():
                    self.assertTrue(body.endswith(b'\0\0'))
                    lines = [line.decode('utf-16-be') for line in body[:-2].split(LINE_BREAK)]
                    self.assertEqual(''.join(''.join(lines).split()), ''.join(expected[identifier].split()))
                    self.assertTrue(all('\n' not in line and '\r' not in line for line in lines))
                    if identifier in MOVE_DESCRIPTION_IDS.values() or identifier in ITEM_DESCRIPTION_IDS.values():
                        is_item = identifier in ITEM_DESCRIPTION_IDS.values()
                        if is_item:
                            width = 216 if game_id.startswith('GC6') else 228
                        else:
                            width = 351 if game_id.startswith('GC6') else 322
                        metrics = native_font_metrics(original, game_id, actual_font)
                        self.assertLessEqual(len(lines), 3 if is_item else 2)
                        self.assertTrue(all(metrics.measure(line) <= width for line in lines))
                identifier, position = struct.unpack_from('>II', data, 16 + 29 * 8)
                body = _transfer_messages()[language]
                self.assertEqual(identifier, TRANSFER_REFUSAL_ID)
                self.assertEqual(data[position:position + len(body)], body)
                if language == 'ja':
                    self.assertIn(b'\xff\xff\x04', body)
                    self.assertIn(b'\xff\xff\x05', body)
                    self.assertIn(b'\xff\xff\x06', body)

    def test_japanese_colosseum_retains_native_message_header_font_field(self):
        original = two_font_dol()
        for language in LANGUAGES:
            jp = message_bank(language, original_dol=original, game_id='GC6J01')
            western = message_bank(language, original_dol=original, game_id='GC6E01')
            self.assertEqual(jp[4:6], western[4:6])
            self.assertEqual(jp[8:], western[8:])
            self.assertEqual(struct.unpack_from('>H', jp, 6)[0], description_font('GC6J01', language))
            self.assertEqual(western[3], description_font('GC6E01', language))

    def test_tm_and_move_help_share_prose_with_separate_ids_for_their_native_panes(self):
        self.assertEqual(set(ITEM_NAME_IDS), set(range(278, 285)))
        self.assertEqual(set(MOVE_NAME_IDS), set(range(375, 382)))
        for index, (item, pair) in enumerate(ITEM_MESSAGE_IDS.items()):
            self.assertEqual(pair, (ITEM_NAME_IDS[item], ITEM_DESCRIPTION_IDS[item]))
            self.assertNotEqual(pair[1], MOVE_DESCRIPTION_IDS[375 + index])
            for language in LANGUAGES:
                texts = message_texts(language)
                self.assertTrue(texts[pair[0]].endswith(str(51 + index)))
                self.assertEqual(texts[pair[1]], texts[MOVE_DESCRIPTION_IDS[375 + index]])
                self.assertEqual(texts[MOVE_NAME_IDS[375 + index]], texts[MOVE_NAME_IDS[375 + index]].upper())
                self.assertNotEqual(texts[pair[1]], move_description((574, 577, 583, 584, 585, 605, 608)[index], language))

    def test_bad_languages_and_unknown_executables_fail_closed(self):
        for language in ('ko', '', None):
            with self.assertRaises(ValueError):
                message_bank(language, original_dol=two_font_dol(), game_id='GC6P01')
        with self.assertRaises(ValueError):
            description_font('unknown', 'en')
        self.assertEqual(description_font('GC6J01', 'ja'), 1)
        self.assertEqual(description_font('GXXJ01', 'ja'), 1)
        with self.assertRaises(FormatError):
            install_fairy_messages(bytes(256), bytes(256), 'GC6P01')

    def test_optional_retail_banks_compose_after_existing_type_arena(self):
        from orre_randomizer.fairy_runtime import install_fairy_type
        root = Path(__file__).resolve().parents[1]
        cases = [(f'GC6{letter}01', root / f'build/hd-completion/hud/GC6{letter}01.dol')
                 for letter in 'PEJ']
        cases += [(f'GXX{letter}01', root / f'build/xd-validation/{region}/main.dol')
                  for letter, region in (('P', 'eu'), ('E', 'us'), ('J', 'jp'))]
        found = 0
        for game_id, path in cases:
            if not path.is_file():
                continue
            found += 1
            with self.subTest(game_id=game_id):
                original = path.read_bytes()
                digest = hashlib.sha256(original).hexdigest()
                typed, _, _ = install_fairy_type(original, original, game_id)
                result, report = install_fairy_messages(original, typed, game_id)
                offset = struct.unpack_from('>I', result, 8)[0]
                self.assertEqual(result[offset + 32:len(typed)], typed[offset + 32:])
                arena = next(s for s in parse_dol(result)['sections'] if s['name'] == 'text2')
                self.assertEqual(arena['offset'] + arena['size'], len(result))
                self.assertGreaterEqual(report['refresh_address'], arena['ram_address'] + 32)
                for language, address in report['banks'].items():
                    bank = message_bank(language, original_dol=original, game_id=game_id)
                    position = offset + address - arena['ram_address']
                    self.assertEqual(result[position:position + len(bank)], bank)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        if not found:
            self.skipTest('Optional private retail executables are unavailable')


if __name__ == '__main__':
    unittest.main()
