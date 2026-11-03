import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import decompress_lzss, parse_fsys
from rebuild_iso import compress_lzss, decoded_member, repack_fsys


class EncoderTests(unittest.TestCase):
    def test_known_literal_encoding(self):
        encoded = compress_lzss(b"abc")
        self.assertEqual(encoded[16:], b"\7abc")

    def test_lossless_edge_cases_and_wrapping(self):
        rng = random.Random(29173)
        cases = [b"", b"a", b"ab", b"abc", b"A" * 12000, bytes(10000),
                 b"abcabcabc" * 2000, bytes(range(256)) * 40, rng.randbytes(9000)]
        for raw in cases:
            with self.subTest(size=len(raw)):
                encoded = compress_lzss(raw)
                self.assertEqual(decompress_lzss(encoded), raw)
                self.assertEqual(compress_lzss(raw), encoded)

    def test_reference_encoding_is_actually_used(self):
        raw = b"abc" * 1000
        self.assertLess(len(compress_lzss(raw)), len(raw) // 2)

    def test_fsys_preserves_metadata_and_member_bytes(self):
        raw = b"abcabcabc" * 100
        payload = compress_lzss(raw)
        data = bytearray(0xD0 + len(payload))
        data[:4] = b"FSYS"
        for offset, value in ((0xC, 1), (0x40, 0x60), (0x60, 0x80), (0x80, 0x12345678),
                              (0x84, 0xD0), (0x88, len(raw)), (0x94, len(payload)), (0xA4, 0xC0)):
            struct.pack_into(">I", data, offset, value)
        data[0xC0:0xC5] = b"test\0"
        data[0xD0:] = payload
        data.extend(b"\0" * (-len(data) % 32) + b"\0" * 28 + b"FSYS")
        struct.pack_into(">I", data, 0x20, len(data))
        rebuilt, checks = repack_fsys(bytes(data))
        member = parse_fsys(rebuilt)["members"][0]
        self.assertEqual(decoded_member(rebuilt, member), raw)
        self.assertEqual(member["identifier_raw"], "0x12345678")
        self.assertEqual(member["offset"] % 32, 0)
        self.assertEqual(rebuilt[-4:], b"FSYS")
        self.assertTrue(checks[0]["decoded_byte_identical"])
        replacement = b"changed payload" * 20
        modified, changed_checks = repack_fsys(bytes(data), {0: replacement})
        modified_member = parse_fsys(modified)["members"][0]
        self.assertEqual(decoded_member(modified, modified_member), replacement)
        self.assertFalse(changed_checks[0]["decoded_byte_identical"])
        with self.assertRaises(ValueError):
            repack_fsys(bytes(data), {1: replacement})


if __name__ == "__main__":
    unittest.main()
