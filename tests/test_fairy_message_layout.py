"""Native wrapping proofs use real parsed glyph metrics, without local ROMs."""
from fractions import Fraction
from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.fairy_data import LANGUAGES, NEW_MOVE_IDS, move_description
from orre_randomizer.fairy_message_layout import (
    LINE_BREAK, NativeFontMetrics, encode_native_description, native_description,
    native_font_metrics, wrap_native_text,
)


def font_dol():
    alphabet = sorted({ord(char) for language in LANGUAGES for move in NEW_MOVE_IDS
                       for char in native_description(move, language)} | set(map(ord, 'Wi「」『』。、')))
    count = len(alphabet)
    directory = bytearray(24 + 8 * count)
    struct.pack_into('>HBBIHHIII', directory, 0, 0, 22, 22, 0, count, 0, 16 + count * 8, 0, 0)
    pixels = bytearray()
    for index, code in enumerate(alphabet):
        width = 18 if code >= 0x3000 or code == ord('W') else 2 if code == ord('i') else 8
        struct.pack_into('>HBBI', directory, 24 + 8 * index, code, width, 1, len(pixels))
        pixels.extend(b'\xff' * ((width + 1) // 2))
    bank = directory + pixels
    dol = bytearray(0x120 + len(bank))
    for at, value in ((0, 0x100), (0x48, 0x80003000), (0x90, 4),
                      (0x1C, 0x120), (0x64, 0x80004000), (0xAC, len(bank)), (0xE0, 0x80003000)):
        struct.pack_into('>I', dol, at, value)
    dol[0x120:] = bank
    return bytes(dol)


class FairyNativeMoveProse(unittest.TestCase):
    def test_separate_complete_native_prose_retains_full_reference(self):
        for language in LANGUAGES:
            for move in NEW_MOVE_IDS:
                compact = native_description(move, language)
                reference = move_description(move, language)
                self.assertTrue(compact)
                self.assertNotIn('\n', compact)
                self.assertNotIn('\uffff', compact)
                self.assertNotEqual(compact, reference)
        self.assertIn('3/4', native_description(577, 'en'))
        self.assertIn('3/4', native_description(577, 'fr'))
        self.assertIn('４ぶんの３', native_description(577, 'ja'))
        with self.assertRaises(ValueError):
            native_description(375, 'en')  # Allocated native IDs are not canonical IDs.
        with self.assertRaises(ValueError):
            native_description(574, 'unknown')

    def test_exact_parsed_widths_and_native_space_rule(self):
        metrics = native_font_metrics(font_dol(), 'GXXP01', 0)
        self.assertEqual(metrics.maximum_width, 22)
        self.assertEqual(metrics.measure('Wi W'), 18 + 2 + 11 + 18)
        self.assertEqual(wrap_native_text('WW ii', 'en', metrics=metrics, width=40), ('WW', 'ii'))
        self.assertEqual(wrap_native_text('iiii iiii', 'en', metrics=metrics, width=40), ('iiii iiii',))
        fractional = NativeFontMetrics(0, 21, ((ord('i'), 2),))
        self.assertEqual(fractional.measure('i i'), 14)

    def test_two_native_font_choices_share_one_original_dol_scan(self):
        from orre_randomizer.fairy_message_layout import _font_records
        from orre_randomizer.hd_text import font_banks_from_dol
        original = font_dol()
        banks, glyphs = font_banks_from_dol(original)
        banks += [{**bank, 'font_id': 1} for bank in banks]
        glyphs += [replace(glyph, font_id=1) for glyph in glyphs]
        _font_records.cache_clear()
        native_font_metrics.cache_clear()
        with patch('orre_randomizer.fairy_message_layout.font_banks_from_dol',
                   return_value=(banks, glyphs)) as scanner:
            first = native_font_metrics(original, 'GXXP01', 0)
            second = native_font_metrics(original, 'GXXP01', 1)
            self.assertEqual(first.measure('Wi'), second.measure('Wi'))
            self.assertEqual(scanner.call_count, 1)
        _font_records.cache_clear()
        native_font_metrics.cache_clear()

    def test_encoder_wraps_all_six_languages_without_ui_truncation_or_terminators(self):
        original = font_dol()
        metrics = native_font_metrics(original, 'GXXP01', 0)
        reference = {(move, language): move_description(move, language)
                     for language in LANGUAGES for move in NEW_MOVE_IDS}
        for language in LANGUAGES:
            for move in NEW_MOVE_IDS:
                with self.subTest(language=language, move=move):
                    payload = encode_native_description(move, language, original_dol=original,
                        game_id='GXXP01', width=260, font_id=0)
                    self.assertFalse(payload.endswith(b'\0\0'))
                    self.assertNotIn(b'\xff\xff\x02', payload)
                    lines = [row.decode('utf-16-be') for row in payload.split(LINE_BREAK)]
                    self.assertLessEqual(len(lines), 3)
                    self.assertTrue(all(metrics.measure(row) <= 260 for row in lines))
                    self.assertEqual(''.join(''.join(lines).split()),
                                     ''.join(native_description(move, language).split()))
        self.assertEqual(original, font_dol())
        self.assertEqual(reference, {(move, language): move_description(move, language)
                                    for language in LANGUAGES for move in NEW_MOVE_IDS})

    def test_overflow_unknown_glyph_and_invalid_caller_fail_without_partial_output(self):
        original = font_dol()
        metrics = native_font_metrics(original, 'GXXP01', 0)
        for text, width in (('WW', 20), ('W W W', 18), ('🌙', 100)):
            with self.assertRaises(FormatError):
                wrap_native_text(text, 'en', metrics=metrics, width=width, max_lines=2)
        for text in ('x\ny', '\uffff', '\ud800'):
            with self.assertRaises(FormatError):
                wrap_native_text(text, 'en', metrics=metrics, width=100)
        for kwargs in ({}, {'width': 260}, {'font_id': 0}):
            with self.assertRaises(ValueError):
                encode_native_description(605, 'en', original_dol=original, game_id='GXXP01', **kwargs)
        with self.assertRaises(FormatError):
            native_font_metrics(original, 'GXXP01', 1)
        with self.assertRaises(ValueError):
            native_font_metrics(original, 'other', 0)
        with self.assertRaises(ValueError):
            wrap_native_text('W', 'en', metrics=metrics, width=True)

    def test_japanese_closing_punctuation_and_small_kana_stay_with_previous_glyph(self):
        metrics = native_font_metrics(font_dol(), 'GXXJ01', 0)
        lines = wrap_native_text('こうげき。こうげき。', 'ja', metrics=metrics, width=90)
        self.assertTrue(all(not row.startswith('。') for row in lines))
        lines = wrap_native_text('「こうげき」こうげき。', 'ja', metrics=metrics, width=90)
        self.assertTrue(all(not row.startswith('」') and not row.endswith('「') for row in lines))
        with self.assertRaises(FormatError):
            wrap_native_text('。こうげき', 'ja', metrics=metrics, width=90)


if __name__ == '__main__':
    unittest.main()
