import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import FormatError
from prepare_dolphin_test import prepare
from randomize_story import (SPECIALS, experience_at_level, patch_special_tables,
                             randomize_specials, validate_dol_changes)


class StoryRandomizerTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(0x132000)
        for target in SPECIALS:
            p = target["base"]
            struct.pack_into(">II", data, p, 0x38800000 | target["old"], 0x38A00000 | target["level"])
            if "xp" in target:
                struct.pack_into(">I", data, p + 0x90, 0x38E00000 | target["xp"])
        species = {i: {"national_dex": i, "name_fr": str(i), "growth_group": i % 6}
                   for i in range(1, 387)}
        return bytes(data), species

    def test_growth_known_values_boundaries_and_monotonicity(self):
        at_25 = (15625, 23437, 12187, 11735, 12500, 19531)
        at_26 = (17576, 26012, 14060, 13411, 14060, 21970)
        at_100 = (1000000, 600000, 1640000, 1059860, 800000, 1250000)
        for group in range(6):
            with self.subTest(group=group):
                self.assertEqual(experience_at_level(group, 1), 0)
                self.assertEqual(experience_at_level(group, 25), at_25[group])
                self.assertEqual(experience_at_level(group, 26), at_26[group])
                self.assertEqual(experience_at_level(group, 100), at_100[group])
                values = [experience_at_level(group, level) for level in range(1, 101)]
                self.assertTrue(all(a < b for a, b in zip(values, values[1:])))
        for group, level in ((6, 25), (0, 0), (0, 101)):
            with self.assertRaises(ValueError):
                experience_at_level(group, level)

    def test_six_species_repeat_and_only_starters_override_exp(self):
        source, species = self.fixture()
        patched, plan = patch_special_tables(source, "seed-a", species)
        self.assertEqual((patched, plan), patch_special_tables(source, "seed-a", species))
        self.assertNotEqual(patched, patch_special_tables(source, "seed-b", species)[0])
        self.assertEqual(len(plan["special_changes"]), 6)
        self.assertEqual(sum("new_exp" in c for c in plan["special_changes"]), 2)
        for c in plan["special_changes"]:
            self.assertNotEqual(c["old_species_index"], c["new_species_index"])
            p = c["routine_offset"]
            self.assertEqual(source[p + 4:p + 8], patched[p + 4:p + 8])
            if "new_exp" in c:
                self.assertEqual(c["new_exp"], experience_at_level(c["growth_group"], c["level_preserved"]))
                self.assertLess(c["new_exp"], 0x8000)

    def test_reject_unknown_build_or_wrong_instruction(self):
        with self.assertRaises(FormatError):
            randomize_specials(b"unknown DOL", b"", "seed-a")
        source, species = self.fixture()
        for index in (SPECIALS[0]["base"], SPECIALS[1]["base"] + 4, SPECIALS[0]["base"] + 0x90):
            data = bytearray(source)
            data[index] ^= 1
            with self.subTest(index=index), self.assertRaises(FormatError):
                patch_special_tables(bytes(data), "seed-a", species)

    def test_reject_changes_to_level_moves_code_and_header(self):
        source, species = self.fixture()
        patched, plan = patch_special_tables(source, "seed-a", species)
        for index in (0, SPECIALS[0]["base"] + 7, SPECIALS[0]["base"] + 0x16, SPECIALS[2]["base"] + 8):
            data = bytearray(patched)
            data[index] ^= 1
            with self.subTest(index=index), self.assertRaises(FormatError):
                validate_dol_changes(source, bytes(data), plan)


class EmptyProfileTests(unittest.TestCase):
    def test_empty_profile_preserves_original_and_imports_no_save(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original"
            (original / "GC").mkdir(parents=True)
            card = original / "GC/MemoryCardA.EUR.raw"
            sram = original / "GC/SRAM.raw"
            card.write_bytes(b"original memory card")
            sram.write_bytes(b"original SRAM")
            output = root / "build/dolphin-user"
            report = prepare(output, original, copy_saves=False)
            self.assertEqual(report["copied_save_files"], [])
            self.assertFalse((output / "GC/MemoryCardA.EUR.raw").exists())
            self.assertFalse((output / "GC/SRAM.raw").exists())
            self.assertEqual(card.read_bytes(), b"original memory card")
            self.assertEqual(sram.read_bytes(), b"original SRAM")
            self.assertIn((output / "GC/MemoryCardA.EUR.raw").as_posix(), (output / "Config/Dolphin.ini").read_text())


if __name__ == "__main__":
    unittest.main()
