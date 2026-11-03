"""Check the validator's independent final-byte readers on non-game fixtures."""
from pathlib import Path
import struct
import tempfile
import unittest

from scripts.validate_seed_matrix import dol_bytes_at, read_overlay


class FinalByteReaderTests(unittest.TestCase):
    def test_overlay_reads_only_intersecting_patch_bytes_and_keeps_source_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.iso"
            original = bytes(range(64))
            source.write_bytes(original)
            # Both partially intersecting edges and a nonintersecting patch.
            patches = [(6, b"abcdef"), (17, b"XYZ"), (40, b"untouched")]
            self.assertEqual(read_overlay(source, patches, 9, 10),
                             b"def" + original[12:17] + b"XY")
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(AssertionError):
                read_overlay(source, [], 60, 5)

    def test_final_dol_ram_lookup_handles_relocated_sections_and_rejects_gaps(self):
        data = bytearray(0x140)
        struct.pack_into(">I", data, 0, 0x100)
        struct.pack_into(">I", data, 0x48, 0x80003000)
        struct.pack_into(">I", data, 0x90, 0x10)
        struct.pack_into(">I", data, 8, 0x120)
        struct.pack_into(">I", data, 0x50, 0x80480000)
        struct.pack_into(">I", data, 0x98, 0x20)
        struct.pack_into(">I", data, 0xE0, 0x80003000)
        data[0x100:0x110] = b"native-original!"
        data[0x120:0x140] = bytes(range(32))
        self.assertEqual(dol_bytes_at(bytes(data), 0x80480010, 16), bytes(range(16, 32)))
        for address, size in ((0x8048001F, 2), (0x80003010, 1), (0x80470000, 4), (0x80480000, 0)):
            with self.subTest(address=address, size=size), self.assertRaises(AssertionError):
                dol_bytes_at(bytes(data), address, size)


if __name__ == "__main__":
    unittest.main()
