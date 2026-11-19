import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.hd_text import Glyph, PAGE_BYTES, PAGE_SIZE, _sample_offset, build_native_pages, parse_font_bank
from orre_randomizer.hd_text import select_runtime_glyphs
from orre_randomizer.hd_text import font_banks_from_dol


class NativeGlyphPages(unittest.TestCase):
    def bank(self):
        raw = bytearray(24 + 16 + 12)
        struct.pack_into(">HBBIHHIII", raw, 0, 1, 18, 18, 0, 2, 0, 32, 0, 0)
        struct.pack_into(">HBBI", raw, 24, 65, 3, 3, 0xFE000000)
        struct.pack_into(">HBBI", raw, 32, 66, 3, 3, 6)
        raw[40:] = bytes.fromhex("123456789abcdef012345678")
        return bytes(raw)

    def test_native_bank_preserves_baseline_and_padding_nibbles(self):
        raw = self.bank()
        metadata, glyphs = parse_font_bank(raw)
        self.assertEqual(metadata["count"], 2)
        self.assertEqual(glyphs[0].y_offset, -2)
        self.assertEqual(glyphs[0].samples, bytes.fromhex("123456789abc"))
        self.assertEqual(raw, self.bank())
        pages, plan = build_native_pages(glyphs)
        self.assertEqual(len(pages[0]), 128 + PAGE_BYTES)
        self.assertEqual(plan["contract"], "orre-gsmsg-static-glyph-pages-v1")
        self.assertFalse(plan["hd_ready"])
        for glyph, record in zip(glyphs, plan["glyphs"], strict=True):
            samples = pages[record["page"]][128:]
            for y in range(3):
                for x in range(4):
                    at, shift = _sample_offset(record["x"] + x, record["y"] + y)
                    expected = (glyph.samples[y * 2 + x // 2] >> (4 if x % 2 == 0 else 0)) & 15
                    self.assertEqual(samples[at] >> shift & 15, expected)

    def test_bad_bank_structure_is_rejected(self):
        raw = self.bank()
        for at, patch in ((8, b"\0\0"), (12, b"\0\0\0\x10"), (24, b"\0B"), (28, b"\0\xff\xff\xff")):
            changed = bytearray(raw)
            changed[at:at + len(patch)] = patch
            with self.assertRaises(FormatError):
                parse_font_bank(bytes(changed))
        with self.assertRaises(FormatError):
            parse_font_bank(raw[:-1])

    def test_small_dol_supplement_bank_is_collected_without_relaxing_structure(self):
        bank = self.bank()
        dol = bytearray(0x120 + len(bank))
        for at, value in ((0, 0x100), (0x48, 0x80003000), (0x90, 4),
                          (0x1C, 0x120), (0x64, 0x80004000), (0xAC, len(bank)), (0xE0, 0x80003000)):
            struct.pack_into(">I", dol, at, value)
        dol[0x120:] = bank
        banks, glyphs = font_banks_from_dol(bytes(dol))
        self.assertEqual([g.code for g in glyphs], [65, 66])
        self.assertEqual(banks[0]["count"], 2)
        struct.pack_into(">H", dol, 0x120 + 10, 2)
        self.assertEqual(font_banks_from_dol(bytes(dol)), ([], []))

    def test_page_packing_is_deterministic_and_keeps_all_uvs_inside_guards(self):
        glyphs = [Glyph(0, code, 23, 22, 0, bytes([code & 255]) * 12 * 22, "test", code)
                  for code in range(32, 1232)]
        first, plan = build_native_pages(glyphs)
        second, again = build_native_pages(list(reversed(glyphs)))
        self.assertEqual(first, second)
        self.assertEqual(plan, again)
        self.assertGreater(plan["pages"], 1)
        footprints = [set() for _ in first]
        for row in plan["glyphs"]:
            self.assertGreaterEqual(row["y"], 8)
            self.assertEqual(row["x"] % 2, 0)
            self.assertLessEqual(row["x"] + row["width"] + 2, PAGE_SIZE)
            self.assertLess(row["y"] + row["height"], PAGE_SIZE)
            cells = {(x, y) for x in range(row["x"] - 2, row["x"] + ((row["width"] + 1) & ~1) + 2)
                     for y in range(row["y"] - 1, row["y"] + row["height"] + 1)}
            # Horizontal guard pixels may be shared but ink windows cannot.
            ink = {(x, y) for x in range(row["x"], row["x"] + ((row["width"] + 1) & ~1))
                   for y in range(row["y"], row["y"] + row["height"])}
            self.assertFalse(footprints[row["page"]] & ink)
            footprints[row["page"]].update(ink)

    def test_exact_duplicates_share_one_glyph_record(self):
        glyph = Glyph(2, 65, 3, 3, 0, b"\x12\x30" * 3, "source", 0)
        _, plan = build_native_pages([glyph, glyph])
        self.assertEqual(len(plan["glyphs"]), 1)

    def test_transparent_canvas_preserves_visible_samples_and_odd_padding_separately(self):
        glyph = Glyph(2, 65, 3, 3, -2, b"\x12\x3F\x45\x6E\x78\x9D", "math", 0)
        pages, plan = build_native_pages([glyph], padding_by_identity={glyph.identity:(1, 2, 3, 1)})
        row = plan["glyphs"][0]
        self.assertEqual(row["padding_ltrb"], [2, 2, 3, 1])
        self.assertEqual((row["draw_width"], row["draw_height"]), (8, 6))
        self.assertEqual(row["x"] - row["draw_x"], 2)
        self.assertEqual(row["y"] - row["draw_y"], 2)
        self.assertEqual(row["source_padding_nibbles_hex"], "0f0e0d")
        raw = pages[0][128:]
        for y in range(row["draw_height"]):
            for x in range(row["draw_width"]):
                at, shift = _sample_offset(row["draw_x"] + x, row["draw_y"] + y)
                expected = 0
                if 2 <= x < 5 and 2 <= y < 5:
                    column, line = x - 2, y - 2
                    expected = glyph.samples[line * 2 + column // 2] >> (4 if column % 2 == 0 else 0) & 15
                self.assertEqual(raw[at] >> shift & 15, expected)
        self.assertTrue(plan["native_visible_samples_unchanged"])
        self.assertTrue(plan["native_samples_losslessly_recoverable"])

    def test_invalid_margins_are_rejected_instead_of_overlapping_another_glyph(self):
        glyph = Glyph(2, 65, 3, 3, 0, b"\x12\x30" * 3, "math", 0)
        for margins in ((-1, 0, 0, 0), (17, 0, 0, 0), (True, 0, 0, 0), (1, 2)):
            with self.subTest(margins=margins), self.assertRaises(FormatError):
                build_native_pages([glyph], padding_by_identity={glyph.identity:margins})

    def test_nonempty_font_bank_space_still_never_generates_a_glyph_quad(self):
        space = Glyph(2, 32, 8, 8, 0, b"\xFF" * 32, "math", 0)
        letter = Glyph(2, 65, 8, 8, 0, b"\xFF" * 32, "math", 0)
        _, plan = build_native_pages([space, letter])
        self.assertEqual([g["code"] for g in plan["glyphs"]], [65])
        self.assertEqual(plan["non_drawn_codes"], [32])

    def test_zero_height_space_is_valid_and_never_gets_an_ink_quad(self):
        raw = bytearray(self.bank())
        struct.pack_into(">HBBI", raw, 24, 32, 8, 0, 0x16000000)
        _, glyphs = parse_font_bank(bytes(raw))
        self.assertEqual(glyphs[0].samples, b"")
        _, plan = build_native_pages(glyphs)
        self.assertEqual([g["code"] for g in plan["glyphs"]], [66])

    def test_ideographic_zero_height_space_is_reported_as_non_drawn(self):
        blank = Glyph(0, 0x3000, 23, 0, 22, b"", "native", 0)
        letter = Glyph(0, 65, 3, 3, 0, b"\xFF\xF0" * 3, "native", 0)
        _, plan = build_native_pages([blank, letter])
        self.assertEqual(plan["non_drawn_codes"], [32, 0x3000])
        self.assertEqual([r["code"] for r in plan["glyphs"]], [65])

    def test_builtin_latin_flag_one_is_preserved_and_other_flags_rejected(self):
        raw = bytearray(self.bank())
        struct.pack_into(">H", raw, 10, 1)
        meta, glyphs = parse_font_bank(bytes(raw))
        self.assertEqual(meta["flags"], 1)
        self.assertEqual([g.code for g in glyphs], [65, 66])
        struct.pack_into(">H", raw, 10, 2)
        with self.assertRaises(FormatError):
            parse_font_bank(bytes(raw))

    def test_western_residency_keeps_latin_and_gschar_with_native_japanese_fallback(self):
        glyphs = [Glyph(0, code, 3, 3, 0, b"\xFF\xF0" * 3, "math", 0)
                  for code in (0x41, 0xDF, 0x3B1, 0x25A1, 0x6F22)]
        western, policy = select_runtime_glyphs(glyphs, "GC6P01")
        self.assertEqual([g.code for g in western], [0x41, 0xDF, 0x3B1, 0x25A1])
        self.assertEqual(policy["fallback_codes"], [0x6F22])
        self.assertTrue(policy["all_original_font_banks_preserved"])
        self.assertFalse(policy["runtime_coverage_validated"])
        japanese, report = select_runtime_glyphs(glyphs, "GXXJ01")
        self.assertEqual(japanese, glyphs)
        self.assertEqual(report["fallback_codes"], [])

    def test_western_ui_brackets_and_verified_currency_do_not_pull_in_cjk_alphabet(self):
        glyphs = [Glyph(0, code, 3, 3, 0, b"\xFF\xF0" * 3, "native", 0)
                  for code in (0x3010, 0x3011, 0xFF04, 0x6F22)]
        selected, policy = select_runtime_glyphs(glyphs, "GXXP01")
        self.assertEqual([g.code for g in selected], [0x3010, 0x3011, 0xFF04])
        self.assertEqual(policy["fallback_codes"], [0x6F22])
