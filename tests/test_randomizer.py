import copy
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import FormatError
from randomize_trainers import choose_species, randomize_rel, randomize_tables, validate_changes


class RandomizerTests(unittest.TestCase):
    def fixture(self):
        tables = {"trainers": {"offset": 0x100, "count": 3, "stride": 0x34},
                  "trainer_pokemon": {"offset": 0x300, "count": 10, "stride": 0x50},
                  "shadow": {"offset": 0x900, "count": 3, "stride": 0x38},
                  "species": {"offset": 0x1000, "count": 387, "stride": 0x11C}}
        data = bytearray(0x1000 + 387 * 0x11C)
        for i in range(1, 387):
            p = 0x1000 + i * 0x11C
            struct.pack_into(">H", data, p + 0x10, i)
            struct.pack_into(">I", data, p + 0x18, 1000 + i)
            data[p + 0x32:p + 0x34] = bytes((1, 2 if i % 2 else 0))
            data[p + 0x85:p + 0x91:2] = bytes([50] * 6)
        for i, start in ((1, 1), (2, 3)):
            struct.pack_into(">H", data, 0x100 + i * 0x34 + 4, start)
        for i in range(1, 10):
            p = 0x300 + i * 0x50
            old = 25 if i in (1, 5) else 2 * i + 1
            data[p] = 1
            data[p + 3] = 1 if i in (1, 5) else 0
            data[p + 4] = 20 + i
            struct.pack_into(">H", data, p + 0xA, old)
            struct.pack_into(">I", data, p + 0x14, 1000 + old)
            # Unknown/individual fields must stay intact, not just levels.
            data[p + 0x20:p + 0x50] = bytes(range(48))
        struct.pack_into(">H", data, 0x900 + 0x38 + 2, 25)
        return bytes(data), tables

    def test_seed_vectors_and_input_contract(self):
        # Fixed vectors pin the versioned byte encoding and draw algorithm.
        self.assertEqual(choose_species("test", "slot:1", [1, 2, 3, 4], 1), 4)
        self.assertEqual(choose_species("test", "shadow:1", [1, 2, 3, 4], 1), 4)
        self.assertEqual(choose_species("test", "slot:1", [4, 3, 2, 1, 1], 1), 4)
        for seed in ("", "é" * 129):
            with self.subTest(seed=seed[:5]), self.assertRaises(ValueError):
                choose_species(seed, "slot:1", [1, 2], 1)

    def test_seed_repeats_and_different_seed_changes_output(self):
        data, tables = self.fixture()
        a, ma = randomize_tables(data, "seed-a", tables)
        b, mb = randomize_tables(data, "seed-a", tables)
        other, _ = randomize_tables(data, "seed-b", tables)
        self.assertEqual((a, ma), (b, mb))
        self.assertNotEqual(a, other)
        self.assertEqual(ma["summary"]["trainer_pokemon_records_changed"], 8)
        self.assertEqual(ma["summary"]["populated_unreferenced_slots_preserved"], 1)
        self.assertEqual(a[0x300:0x350], data[0x300:0x350])  # Empty slot.
        self.assertEqual(a[0x300 + 9 * 0x50:0x300 + 10 * 0x50], data[0x300 + 9 * 0x50:0x300 + 10 * 0x50])

    def test_shadow_aliases_shared_slots_and_other_fields(self):
        data, tables = self.fixture()
        patched, plan = randomize_tables(data, "seed-a", tables)
        shadow = plan["shadow_changes"][0]
        self.assertEqual(shadow["trainer_pokemon_indices"], [1, 5])
        for c in plan["trainer_pokemon_changes"]:
            p = c["offset"]
            if c["shadow_id"]:
                self.assertEqual(c["new_species_index"], shadow["new_species_index"])
            self.assertNotEqual(c["old_species_index"], c["new_species_index"])
            self.assertEqual(data[p + 1:p + 0xA], patched[p + 1:p + 0xA])
            self.assertEqual(data[p + 0x18:p + 0x50], patched[p + 0x18:p + 0x50])
        shared = next(c for c in plan["trainer_pokemon_changes"] if c["index"] == 3)
        self.assertEqual(shared["referencing_trainers"], [1, 2])
        self.assertEqual(len({c["index"] for c in plan["trainer_pokemon_changes"]}), 8)
        self.assertGreater(plan["summary"]["ability_selectors_normalized"], 0)
        self.assertEqual(struct.unpack_from(">H", patched, shadow["offset"])[0], shadow["new_species_index"])

    def test_verifier_rejects_neighbor_level_and_move_mutations(self):
        data, tables = self.fixture()
        patched, plan = randomize_tables(data, "seed-a", tables)
        for index in (0, 0x300 + 0x50 + 4, 0x300 + 0x50 + 0x36):
            bad = bytearray(patched)
            bad[index] ^= 1
            with self.subTest(index=index), self.assertRaises(FormatError):
                validate_changes(data, bytes(bad), plan)
        bad_plan = copy.deepcopy(plan)
        bad_plan["shadow_changes"][0]["new_species_index"] += 1
        with self.assertRaises(FormatError):
            validate_changes(data, patched, bad_plan)

    def test_random_ability_selector_is_preserved(self):
        data, tables = self.fixture()
        source = bytearray(data)
        source[0x300 + 2 * 0x50] = 0xFF
        patched, _ = randomize_tables(bytes(source), "seed-a", tables)
        self.assertEqual(patched[0x300 + 2 * 0x50], 0xFF)

    def test_refuses_unknown_build_pool_name_and_shadow_mismatch(self):
        with self.assertRaises(FormatError):
            randomize_rel(b"unknown dump", "seed-a")
        data, tables = self.fixture()
        for index in (0x1000 + 0x11C + 0x10, 0x300 + 0x50 + 0x14, 0x900 + 0x38 + 2):
            bad = bytearray(data)
            bad[index] ^= 1
            with self.subTest(index=index), self.assertRaises(FormatError):
                randomize_tables(bytes(bad), "seed-a", tables)


if __name__ == "__main__":
    unittest.main()
