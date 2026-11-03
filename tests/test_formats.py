"""Independent small binary fixtures: bounds, corruption and overlapping LZSS."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import FormatError, decompress_lzss, parse_dol, parse_fsys, parse_rel
from inspect_tables import plain_name, rel_symbols


def put(data, pos, value):
    struct.pack_into(">I", data, pos, value)


def lzss(expected, payload):
    return b"LZSS" + struct.pack(">III", expected, 16 + len(payload), 0) + payload


def fsys_fixture(payload=b"data", expected=None):
    data = bytearray(0xD0 + len(payload))
    data[:4] = b"FSYS"
    for pos, value in ((0xC, 1), (0x20, len(data)), (0x40, 0x60), (0x60, 0x80),
                       (0x84, 0xD0), (0x88, len(payload) if expected is None else expected),
                       (0x94, len(payload)), (0xA4, 0xC0)):
        put(data, pos, value)
    data[0xC0:0xC5] = b"test\0"
    data[0xD0:] = payload
    return data


def dol_fixture():
    data = bytearray(0x108)
    for pos, value in ((0, 0x100), (0x48, 0x80003100), (0x90, 8), (0xE0, 0x80003100)):
        put(data, pos, value)
    data[0x100:] = bytes.fromhex("600000004e800020")
    return data


def rel_fixture():
    data = bytearray(0x74)
    for pos, value in ((0, 125), (0xC, 2), (0x10, 0x4C), (0x1C, 3),
                       (0x24, 0x6C), (0x28, 0x64), (0x2C, 8),
                       (0x54, 0x61), (0x58, 4), (0x64, 125), (0x68, 0x6C)):
        put(data, pos, value)
    data[0x30:0x33] = b"\1\1\1"
    data[0x6E] = 203
    return data


class LzssTests(unittest.TestCase):
    def test_literal_and_self_overlapping_reference(self):
        self.assertEqual(decompress_lzss(lzss(9, b"\x07abc\xee\xf3")), b"abcabcabc")

    def test_zero_initialized_ring(self):
        self.assertEqual(decompress_lzss(lzss(3, b"\0\xee\xf0")), b"\0\0\0")

    def test_ring_wraparound(self):
        self.assertEqual(decompress_lzss(lzss(32, b"\x01A\xee\xff\xee\xfa")), b"A" * 32)

    def test_rejects_truncation_overrun_and_trailing_bytes(self):
        for encoded in (lzss(1, b"\1"), lzss(3, b"\0\xee"),
                        lzss(2, b"\0\xee\xf0"), lzss(1, b"\1AB")):
            with self.subTest(encoded=encoded), self.assertRaises(FormatError):
                decompress_lzss(encoded)

    def test_output_bound_and_declared_size(self):
        with self.assertRaises(FormatError):
            decompress_lzss(lzss(3, b"\7abc"), max_output=2)
        with self.assertRaises(FormatError):
            decompress_lzss(lzss(3, b"\7abc")[:-1])


class ContainerTests(unittest.TestCase):
    def test_fsys_raw_and_compressed_members(self):
        self.assertEqual(parse_fsys(fsys_fixture())["members"][0]["name"], "test")
        encoded = lzss(3, b"\7abc")
        self.assertEqual(parse_fsys(fsys_fixture(encoded, 3))["members"][0]["compression"], "LZSS")

    def test_fsys_member_header_must_fit_within_member(self):
        data = fsys_fixture(b"LZSS" + struct.pack(">III", 3, 4, 0), 3)
        put(data, 0x94, 4)
        with self.assertRaisesRegex(FormatError, "shorter"):
            parse_fsys(data)

    def test_fsys_rejects_payload_outside_file_and_size_mismatch(self):
        data = fsys_fixture()
        put(data, 0x84, len(data) - 1)
        with self.assertRaises(FormatError):
            parse_fsys(data)
        data = fsys_fixture(lzss(3, b"\7abc"), 4)
        with self.assertRaises(FormatError):
            parse_fsys(data)

    def test_dol_entry_and_memory_ranges(self):
        data = dol_fixture()
        self.assertEqual(parse_dol(data)["entry_ram_address"], 0x80003100)
        put(data, 0xE0, 0x80004100)
        with self.assertRaises(FormatError):
            parse_dol(data)
        data = dol_fixture()
        put(data, 0x48, 0xFFFFFFFC)
        with self.assertRaises(FormatError):
            parse_dol(data)

    def test_dol_rejects_overlapping_sections(self):
        data = dol_fixture()
        for pos, value in ((0x1C, 0x104), (0x64, 0x80004100), (0xAC, 4)):
            put(data, pos, value)
        with self.assertRaises(FormatError):
            parse_dol(data)

    def test_rel_imports_callbacks_and_stream_termination(self):
        data = rel_fixture()
        parsed = parse_rel(data)
        self.assertEqual(parsed["module_id"], 125)
        self.assertEqual(rel_symbols(data, parsed), [])
        bad = bytearray(data)
        put(bad, 0x68, 0xFFFFFFFF)
        with self.assertRaises(FormatError):
            parse_rel(bad)
        bad = bytearray(data)
        bad[0x30] = 255
        with self.assertRaises(FormatError):
            parse_rel(bad)
        bad = bytearray(data)
        bad[0x6E] = 0
        with self.assertRaises(FormatError):
            rel_symbols(bad, parsed)

    def test_plain_names_preserve_controls_as_unknown(self):
        data = "MENTALI\0".encode("utf-16-be")
        self.assertEqual(plain_name(data, 0, len(data)), "MENTALI")
        self.assertIsNone(plain_name(b"\xff\xff\0\0", 0, 4))


if __name__ == "__main__":
    unittest.main()
