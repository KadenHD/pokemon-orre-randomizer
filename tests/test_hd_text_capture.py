"""Font capture reads only bounded source spans and never changes its disc."""
from pathlib import Path
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.hd_text_capture import collect_source_glyphs
from orre_randomizer.service import Cancelled


def font():
    raw = bytearray(52)
    struct.pack_into(">HBBIHHIII", raw, 0, 1, 18, 18, 0, 2, 0, 32, 0, 0)
    struct.pack_into(">HBBI", raw, 24, 65, 3, 3, 0xFE000000)
    struct.pack_into(">HBBI", raw, 32, 66, 3, 3, 6)
    raw[40:] = bytes.fromhex("123456789abcdef012345678")
    return bytes(raw)


class TextCapture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "verified-fixture.iso"
        image = bytearray(0x3000)
        image[:6] = b"GC6P01"
        image[0x1C:0x20] = bytes.fromhex("c2339f3d")
        struct.pack_into(">3I", image, 0x420, 0x500, 0x800, 64)
        dol = bytearray(0x200)
        struct.pack_into(">I", dol, 0, 0x100)
        struct.pack_into(">I", dol, 0x48, 0x80003100)
        struct.pack_into(">I", dol, 0x90, 0x20)
        struct.pack_into(">I", dol, 0xE0, 0x80003100)
        struct.pack_into(">I", dol, 0x1C, 0x120)  # data0
        struct.pack_into(">I", dol, 0x64, 0x80004000)
        struct.pack_into(">I", dol, 0xAC, 0xE0)
        image[0x500:0x700] = dol
        fst = bytearray(64)
        struct.pack_into(">III", fst, 0, 0x01000000, 0, 3)
        struct.pack_into(">III", fst, 12, 0, 0x1000, 0x1000)
        struct.pack_into(">III", fst, 24, 11, 0x2100, 64)
        fst[36:56] = b"fonts.fsys\0keep.bin\0\0"
        image[0x800:0x840] = fst
        archive = bytearray(0x1000)
        archive[:4] = b"FSYS"
        struct.pack_into(">I", archive, 0xC, 2)
        struct.pack_into(">I", archive, 0x20, len(archive))
        struct.pack_into(">I", archive, 0x40, 0x60)
        struct.pack_into(">2I", archive, 0x60, 0x80, 0xB0)
        for at, identity, offset, payload in ((0x80, 0x17000C00, 0x100, font()),
                                             (0xB0, 0x11001E00, 0x400, b"not a font")):
            struct.pack_into(">3I", archive, at, identity, offset, len(payload))
            struct.pack_into(">I", archive, at + 0x14, len(payload))
            archive[offset:offset + len(payload)] = payload
        image[0x1000:0x2000] = archive
        image[0x2100:0x2140] = b"untouched non-archive".ljust(64, b"!")
        self.path.write_bytes(image)
        self.before = self.path.read_bytes()
        mocked_region = patch("orre_randomizer.engine.regions.region_for_boot",
                              return_value=SimpleNamespace(dol_size=0x200))
        mocked_region.start()
        self.addCleanup(mocked_region.stop)

    def test_complete_font_capture_keeps_source_and_ignores_nonfont_members(self):
        original, glyphs, audit = collect_source_glyphs(self.path, game_id="GC6P01")
        self.assertEqual(original, self.before[0x500:0x700])
        self.assertEqual([glyph.code for glyph in glyphs], [65, 66])
        self.assertEqual(glyphs[0].samples, bytes.fromhex("123456789abc"))
        self.assertEqual(audit["archives_examined"], 1)
        self.assertEqual(audit["font_members"], 1)
        self.assertEqual(audit["sources"][1]["file"], "fonts.fsys/0:17000c00")
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_empty_archive_has_no_font_directory_to_read(self):
        changed = bytearray(self.before)
        struct.pack_into(">I", changed, 0x100C, 0)
        struct.pack_into(">I", changed, 0x1040, 0)
        self.path.write_bytes(changed)
        _, glyphs, audit = collect_source_glyphs(self.path, game_id="GC6P01")
        self.assertEqual(glyphs, [])
        self.assertEqual(audit["font_members"], 0)
        self.assertEqual(self.path.read_bytes(), changed)

    def test_overrun_directory_and_font_payloads_fail_before_any_write(self):
        for offset, value in ((0x1040, 0xFFF), (0x1060, 0xFFF),
                              (0x1084, 0xFFF), (0x1088, 16 * 1024 * 1024),
                              (0x1094, 16 * 1024 * 1024)):
            with self.subTest(offset=offset):
                changed = bytearray(self.before)
                struct.pack_into(">I", changed, offset, value)
                self.path.write_bytes(changed)
                with self.assertRaises(FormatError):
                    collect_source_glyphs(self.path, game_id="GC6P01")
                self.assertEqual(self.path.read_bytes(), changed)

    def test_cancelled_capture_does_not_write_or_return_partial_references(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            collect_source_glyphs(self.path, game_id="GC6P01", cancel=cancel)
        self.assertEqual(self.path.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
