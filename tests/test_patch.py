import sys
import unittest
from pathlib import Path
import struct

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import FormatError
from patch_trainer import patch_one, validate_payload


class PatchValidationTests(unittest.TestCase):
    def fixture(self):
        original = bytearray(range(80))
        struct.pack_into(">H", original, 10, 232)
        struct.pack_into(">I", original, 20, 1232)
        new = bytearray(original)
        struct.pack_into(">H", new, 10, 25)
        struct.pack_into(">I", new, 20, 1025)
        plan = {"species_field_offset": 10, "name_field_offset": 20,
                "old_species_index": 232, "new_species_index": 25,
                "old_name_id": 1232, "new_name_id": 1025}
        return bytes(original), new, plan

    def test_exact_species_and_name_changes(self):
        old, new, plan = self.fixture()
        changes = validate_payload(old, bytes(new), plan)
        self.assertEqual([x["offset"] for x in changes], [11, 23])

    def test_rejects_extra_gameplay_or_neighbor_changes(self):
        for index in (4, 30, 79):
            old, new, plan = self.fixture()
            new[index] ^= 1
            with self.subTest(index=index), self.assertRaises(FormatError):
                validate_payload(old, bytes(new), plan)

    def test_rejects_wrong_species_and_wrong_build(self):
        old, new, plan = self.fixture()
        new[11] = 26
        with self.assertRaises(FormatError):
            validate_payload(old, bytes(new), plan)
        with self.assertRaises(FormatError):
            patch_one(b"unrecognized build")


if __name__ == "__main__":
    unittest.main()
