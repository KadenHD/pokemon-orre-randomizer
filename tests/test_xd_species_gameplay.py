from dataclasses import replace
import struct
import unittest

from orre_randomizer.engine.gameplay_rules import damaging
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.tm_rules import ORIGINAL_HM_MOVES, ORIGINAL_TM_MOVES
from orre_randomizer.options import Options
from orre_randomizer.xd_species_gameplay import (
    SPECIES_STRIDE, STAT_FIELDS, TM_OFFSETS, XDMoveRandomizer,
    patch_species_gameplay, patch_tm_gameplay,
)


def fixture():
    species = {1: (1,), 2: (2,), 303: (292,)}
    families = {1: 1, 2: 1, 303: 303}
    item_start, species_start, move_start = 0x20, 0x5000, 0x23000
    rel = bytearray(move_start + 375 * 0x38)
    symbols = [{} for _ in range(126)]
    tables = ((70, item_start, 444), (88, species_start, 415), (124, move_start, 375))
    for slot, (index, start, count) in enumerate(tables):
        symbols[index] = {"offset": start}
        symbols[index + 1] = {"offset": slot * 4}
        struct.pack_into(">I", rel, symbols[index + 1]["offset"], count)
    for index, (national,) in species.items():
        pos = species_start + index * SPECIES_STRIDE
        struct.pack_into(">H", rel, pos + 0xE, national)
        rel[pos + 0x30:pos + 0x34] = bytes((6, 7, 25, 0) if national == 292 else (1, 1, index, index + 10))
        struct.pack_into(">6H", rel, pos + STAT_FIELDS[0], 1 if national == 292 else 61, 65, 67, 72, 74, 85)
        for slot in range(8):
            struct.pack_into(">BxH", rel, pos + 0xC4 + 4 * slot, 1 + 2 * slot, 1 + slot)
        rel[pos + 0x34:pos + 0x34 + 58] = bytes((i % 2 for i in range(58)))
    types = tuple(i for i in range(18) if i != 9)
    for index in range(1, 355):
        pos = move_start + index * 0x38
        rel[pos + 1:pos + 3] = bytes((5, types[index % len(types)]))
        rel[pos + 0x19] = 50
        struct.pack_into(">I", rel, pos + 0x20, 2000 + index)
    dol = bytearray(TM_OFFSETS["GXXJ01"] + 58 * 8)
    for i, move in enumerate(ORIGINAL_TM_MOVES + ORIGINAL_HM_MOVES):
        struct.pack_into(">B5xH", dol, TM_OFFSETS["GXXJ01"] + i * 8, i >= 50, move)
        if i < 50:
            pos = item_start + (0x121 + i) * 0x28
            rel[pos], rel[pos + 0x1B] = 4, i
            struct.pack_into(">I", rel, pos + 0x14, 10195 + i)
    return bytes(rel), bytes(dol), symbols, species, families


class XDSpeciesGameplayTests(unittest.TestCase):
    def test_species_transforms_keep_family_properties_learn_levels_and_shedinja(self):
        rel, _, symbols, species, families = fixture()
        options = replace(Options(), randomize_types=True, randomize_stats=True,
                          randomize_abilities=True, randomize_learnsets=True)
        before = XDMoveRandomizer(rel, symbols, species, options)
        updated, report = patch_species_gameplay(rel, symbols, "fixture", species, families, options)
        self.assertEqual(patch_species_gameplay(rel, symbols, "fixture", species, families, options), (updated, report))
        self.assertGreater(report["learnset_moves_changed"], 0)
        after = XDMoveRandomizer(updated, symbols, species, options)
        self.assertEqual(after.species[1]["types"], after.species[2]["types"])
        self.assertEqual(after.species[1]["abilities"], after.species[2]["abilities"])
        self.assertEqual(after.species[303]["abilities"], (25, 0))
        self.assertEqual(after.species[303]["types"], (6, 7))
        self.assertEqual(after.species[303]["stats"][0], 1)
        for index, row in after.species.items():
            self.assertEqual(row["total"], before.species[index]["total"])
            learn = row["offset"] + 0xC4
            self.assertEqual(updated[learn:learn + 32:4], rel[learn:learn + 32:4])
            learned = [u16(updated, learn + 4 * slot + 2) for slot in range(8)]
            self.assertEqual(len(set(learned)), len(learned))
            for slot in (0, 4):
                move = after.catalog[learned[slot]]
                self.assertIn(move["type"], row["types"])
                self.assertTrue(damaging(move))
        self.assertEqual(after.moves("fixture", "trainer", 1, 12, [33, 0, 356, 65535])[2:], [356, 65535])

    def test_tm_permutation_moves_localized_references_and_keeps_hms(self):
        rel, dol, symbols, species, _ = fixture()
        options = replace(Options(), randomize_tm_moves=True, tm_compatibility_mode="universal")
        modified, executable, report = patch_tm_gameplay(rel, dol, symbols, "GXXJ01", "fixture", species, options)
        start = TM_OFFSETS["GXXJ01"]
        moves = [u16(executable, start + i * 8 + 6) for i in range(50)]
        self.assertCountEqual(moves, ORIGINAL_TM_MOVES)
        self.assertTrue(all(before != after for before, after in zip(ORIGINAL_TM_MOVES, moves, strict=True)))
        self.assertEqual(executable[start + 50 * 8:], dol[start + 50 * 8:])
        for i, move in enumerate(moves):
            pos = symbols[70]["offset"] + (0x121 + i) * 0x28 + 0x14
            self.assertEqual(struct.unpack_from(">I", modified, pos)[0], 10195 + ORIGINAL_TM_MOVES.index(move))
        for i in species:
            pos = symbols[88]["offset"] + i * SPECIES_STRIDE + 0x34
            self.assertEqual(modified[pos:pos + 50], bytes([1]) * 50)
            self.assertEqual(modified[pos + 50:pos + 58], rel[pos + 50:pos + 58])
        self.assertEqual(report["tms_moved"], 50)
