"""Runtime additions preserve every non-replaced file and the fixed disc extent."""
import struct
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.play_rom import read_executable, update_staged_disc, _updated_load_budget


def dol(size):
    result = bytearray(size)
    struct.pack_into(">I", result, 0, 0x100)
    struct.pack_into(">I", result, 0x90, size - 0x100)
    result[0x100:] = b"D" * (size - 0x100)
    return bytes(result)


class StagedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "pending.iso"
        image = bytearray(b"\xee" * 0x10000)
        struct.pack_into(">IIII", image, 0x420, 0x3000, 0x4000, 64, 0x800)
        image[0x2440:0x2460] = bytes(0x20)
        fst = bytearray(64)
        struct.pack_into(">III", fst, 0, 0x01000000, 0, 3)
        struct.pack_into(">III", fst, 12, 0, 0x4800, 0x1000)
        struct.pack_into(">III", fst, 24, 9, 0x6000, 0x2000)
        names = b"DNA.fsys\0keep.bin\0"
        fst[36:36 + len(names)] = names
        image[0x4000:0x4040] = fst
        image[0x3000:0x3400] = dol(0x400)
        self.path.write_bytes(image)

    def test_larger_dol_and_archive_are_placed_without_touching_other_resources(self):
        before = self.path.read_bytes()
        result = update_staged_disc(self.path, dol(0x3000), {"DNA.fsys": b"A" * 0x1800})
        after = self.path.read_bytes()
        self.assertEqual(len(before), len(after))
        self.assertEqual(after[0x6000:0x8000], before[0x6000:0x8000])
        self.assertEqual(after[0x2440:0x2460], before[0x2440:0x2460])
        self.assertEqual(read_executable(self.path), dol(0x3000))
        offset = result["archives"]["DNA.fsys"]["disc_offset"]
        self.assertEqual(after[offset:offset + 0x1800], b"A" * 0x1800)
        self.assertFalse(result["dol_disc_offset"] < offset + 0x1800
                         and offset < result["dol_disc_offset"] + 0x3000)
        # No writes outside the reported payloads and two system pointers.
        allowed = [(0x420, 0x424), (0x4000, 0x4040), (offset, offset + 0x1800),
                   (result["dol_disc_offset"], result["dol_disc_offset"] + 0x3000)]
        for index, (old, new) in enumerate(zip(before, after)):
            if old != new:
                self.assertTrue(any(start <= index < end for start, end in allowed), hex(index))

    def test_invalid_or_oversized_payloads_fail_before_any_write(self):
        before = self.path.read_bytes()
        for executable, archives in ((dol(0x10000), {}), (dol(0x400), {"absent": b"A"}),
                                      (dol(0x400), {"DNA.fsys": b"A" * 0x10000})):
            with self.subTest(size=len(executable), archives=list(archives)), self.assertRaises(FormatError):
                update_staged_disc(self.path, executable, archives)
            self.assertEqual(self.path.read_bytes(), before)

    def budget_fixture(self):
        with self.path.open('r+b') as stream:
            stream.truncate(12 * 1024 * 1024)
            stream.seek(0); stream.write(b'GC6J01')
            stream.seek(0x468); stream.write(struct.pack('>I', 4 * 1024 * 1024))
        executable = bytearray(dol(4 * 1024 * 1024 + 0x221))
        struct.pack_into('>I', executable, 0x48, 0x80010000)
        struct.pack_into('>I', executable, 0xE0, 0x80010000)
        return bytes(executable)

    def test_verified_apploader_keeps_a_finite_exact_rounded_budget(self):
        executable = self.budget_fixture()
        before = self.path.read_bytes()
        expected = (len(executable) - 0x100 + 31) & ~31
        with patch('orre_randomizer.play_rom._BUDGET_APPLOADERS', {b'GC6J01':hashlib.sha256(b'').hexdigest()}):
            result = update_staged_disc(self.path, executable)
            # A later runtime addition can raise the same finite budget again.
            self.assertIsNone(_updated_load_budget(b'GC6J01', b'', expected, executable))
            self.assertIsNone(_updated_load_budget(b'GC6J01', b'', 0, executable))
        after = self.path.read_bytes()
        self.assertEqual(struct.unpack_from('>I', after, 0x468)[0], expected)
        self.assertEqual(result['apploader_dol_budget']['previous'], 4 * 1024 * 1024)
        self.assertTrue(result['apploader_dol_budget']['section_boundary_checks_preserved'])
        self.assertEqual(after[0x2440:0x2460], before[0x2440:0x2460])
        self.assertEqual(after[0x6000:0x8000], before[0x6000:0x8000])
        self.assertEqual(read_executable(self.path), executable)

    def test_unknown_apploader_or_out_of_range_sections_fail_without_disc_writes(self):
        executable = self.budget_fixture()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(FormatError, 'Unverified Japanese apploader'):
            update_staged_disc(self.path, executable)
        self.assertEqual(self.path.read_bytes(), before)
        invalid = bytearray(executable)
        struct.pack_into('>I', invalid, 0x48, 0x811FF000)
        struct.pack_into('>I', invalid, 0xE0, 0x811FF000)
        with patch('orre_randomizer.play_rom._BUDGET_APPLOADERS', {b'GC6J01':hashlib.sha256(b'').hexdigest()}):
            with self.assertRaisesRegex(FormatError, 'memory boundary'):
                update_staged_disc(self.path, bytes(invalid))
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
