"""Pure synthetic species rules, with an optional local PAL cross-check."""
from dataclasses import dataclass, replace
from pathlib import Path
import struct
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError
from colosseum_randomizer.engine.evolution_rules import evolution_families
from colosseum_randomizer.engine.species_rules import (
    LEGENDARY_NATIONAL, STAT_OFFSETS, apply_species_rules, candidate_species, species_catalog)


@dataclass(frozen=True)
class Rules:
    allow_gen1: bool = True
    allow_gen2: bool = True
    allow_gen3: bool = True
    allow_legendaries: bool = True
    balance_species: bool = False
    randomize_types: bool = False
    types_family_consistent: bool = True
    randomize_abilities: bool = False
    abilities_family_consistent: bool = True
    randomize_stats: bool = False
    preserve_stat_totals: bool = True


def fixture():
    tables = {"species": {"offset": 64, "count": 10, "stride": 0x11C}}
    raw = bytearray(64 + 10 * 0x11C + 16)
    rows = {
        1: (1, (12, 12), (65, 0), (45, 49, 49, 65, 65, 45)),
        2: (2, (12, 3), (65, 34), (60, 62, 63, 80, 80, 60)),
        3: (152, (12, 12), (65, 0), (45, 49, 65, 49, 65, 45)),
        4: (251, (14, 12), (30, 0), (100, 100, 100, 100, 100, 100)),
        5: (252, (12, 12), (65, 0), (40, 45, 35, 65, 55, 70)),
        6: (292, (6, 7), (25, 0), (1, 90, 45, 30, 30, 40)),
        7: (382, (11, 11), (2, 0), (100, 100, 90, 150, 140, 90)),
        8: (144, (15, 2), (46, 0), (90, 85, 100, 95, 125, 85)),
        9: (3, (12, 3), (65, 34), (80, 82, 83, 100, 100, 80)),
    }
    for index, (national, types, abilities, stats) in rows.items():
        pos = 64 + index * 0x11C
        struct.pack_into(">H", raw, pos + 0x10, national)
        raw[pos + 0x30:pos + 0x34] = bytes((*types, *abilities))
        for offset, value in zip(STAT_OFFSETS, stats):
            raw[pos + offset] = value
        raw[pos + 0x20] = 0xA5  # Non-selected metadata must survive.
    for source, target in ((1, 2), (2, 9)):
        pos = 64 + source * 0x11C + 0x9C
        struct.pack_into(">BBHH", raw, pos, 4, 0, 16, target)
    raw[:12] = b"source guard"
    raw[-12:] = b"suffix guard"
    return bytes(raw), tables


class SpeciesCatalogTests(unittest.TestCase):
    def test_uses_national_numbers_and_preserves_sparse_internal_ids(self):
        original, tables = fixture()
        catalog = species_catalog(original, tables)
        self.assertEqual(catalog[6]["national_dex"], 292)
        self.assertEqual(catalog[6]["stats"][0], 1)
        self.assertEqual(catalog[7]["national_dex"], 382)
        self.assertNotIn(0, catalog)

    def test_rejects_bad_layout_and_unknown_real_metadata(self):
        original, tables = fixture()
        with self.assertRaises(FormatError):
            species_catalog(original[:-100], tables)
        for field, value in ((0x30, 9), (0x32, 0), (0x85, 0)):
            modified = bytearray(original)
            modified[64 + 0x11C + field] = value
            with self.subTest(field=field), self.assertRaises(FormatError):
                species_catalog(bytes(modified), tables)


class CandidatePoolTests(unittest.TestCase):
    def test_generation_and_legendary_filters_use_national_ids(self):
        original, tables = fixture()
        rules = replace(Rules(), allow_gen1=False, allow_gen2=False, allow_legendaries=False)
        self.assertEqual(candidate_species(original, tables, 1, rules), [5, 6])
        with self.assertRaises(FormatError):
            candidate_species(original, tables, 1, replace(rules, allow_gen3=False))
        self.assertEqual(len(LEGENDARY_NATIONAL), 21)

    def test_families_exclude_every_related_stage(self):
        original, tables = fixture()
        self.assertEqual(candidate_species(original, tables, 3, Rules(), {1}), [4, 5, 6, 7, 8])

    def test_balance_uses_window_then_nearest_without_relaxing_filters(self):
        original, tables = fixture()
        self.assertEqual(candidate_species(original, tables, 1, replace(Rules(), balance_species=True)), [3, 5])
        # Only legendary Gen II remains (600 BST), so use nearest despite the
        # low original BST, without reintroducing species from disabled gens.
        rules = replace(Rules(), allow_gen1=False, allow_gen3=False, balance_species=True)
        self.assertEqual(candidate_species(original, tables, 3, rules), [4])


class SpeciesPropertyTests(unittest.TestCase):
    def test_all_disabled_is_identity_and_preserves_prior_changes(self):
        original, tables = fixture()
        current = bytearray(original)
        current[23] = 8
        result, report = apply_species_rules(original, bytes(current), "seed", Rules(), tables)
        self.assertEqual(result, current)
        self.assertEqual(report["changed_bytes"], 0)

    def test_only_declared_fields_change_and_family_arity_is_kept(self):
        original, tables = fixture()
        rules = replace(Rules(), randomize_types=True, randomize_abilities=True, randomize_stats=True)
        modified, report = apply_species_rules(original, original, "stable-été", rules, tables)
        self.assertEqual(apply_species_rules(original, original, "stable-été", rules, tables), (modified, report))
        before, after = species_catalog(original, tables), species_catalog(modified, tables)
        self.assertEqual(evolution_families(original, tables), evolution_families(modified, tables))
        self.assertEqual(after[1]["types"][0], after[2]["types"][0])
        self.assertEqual(after[2]["types"], after[9]["types"])
        self.assertEqual(after[1]["types"][0], after[1]["types"][1])
        self.assertNotEqual(after[2]["types"][0], after[2]["types"][1])
        self.assertEqual(after[1]["abilities"][0], after[2]["abilities"][0])
        self.assertEqual(after[1]["abilities"][1], 0)
        self.assertGreater(after[2]["abilities"][1], 0)
        allowed = set()
        for index, row in before.items():
            for relative in (0x30, 0x31, 0x32, 0x33, *STAT_OFFSETS):
                allowed.add(row["offset"] + relative)
            self.assertEqual(after[index]["total"], row["total"])
            self.assertTrue(all(1 <= value <= 255 for value in after[index]["stats"]))
        actual = {i for i, (a, b) in enumerate(zip(original, modified)) if a != b}
        self.assertTrue(actual)
        self.assertLessEqual(actual, allowed)
        self.assertEqual(after[6]["types"], before[6]["types"])
        self.assertEqual(after[6]["abilities"], (25, 0))
        self.assertEqual(after[6]["stats"][0], 1)
        self.assertFalse(any(25 in row["abilities"] for index, row in after.items() if index != 6))

    def test_random_total_and_rule_isolation(self):
        original, tables = fixture()
        types_only = replace(Rules(), randomize_types=True)
        all_rules = replace(types_only, randomize_abilities=True, randomize_stats=True, preserve_stat_totals=False)
        one = species_catalog(apply_species_rules(original, original, "seed", types_only, tables)[0], tables)
        both = species_catalog(apply_species_rules(original, original, "seed", all_rules, tables)[0], tables)
        self.assertEqual({i: row["types"] for i, row in one.items()}, {i: row["types"] for i, row in both.items()})
        for row in both.values():
            self.assertTrue(250 <= row["total"] <= 680)

    def test_stats_cap_255_with_high_totals_and_many_seeds(self):
        original, tables = fixture()
        patched = bytearray(original)
        pos = species_catalog(original, tables)[1]["offset"]
        for field in STAT_OFFSETS:
            patched[pos + field] = 255
        for seed in ("a", "b", "c", "d", "e"):
            modified, _ = apply_species_rules(bytes(patched), bytes(patched), seed,
                                               replace(Rules(), randomize_stats=True), tables)
            self.assertEqual(species_catalog(modified, tables)[1]["stats"], (255,) * 6)


@unittest.skipUnless(Path("game/files/common.fsys").is_file(), "requires original local PAL dump")
class PalSpeciesIntegrationTests(unittest.TestCase):
    def test_all_real_species_bounds_totals_and_graph(self):
        from colosseum_randomizer.engine.randomize_trainers import layout, original_common
        original = original_common(Path("game"))[2]
        tables = layout(original)[0]
        rules = replace(Rules(), randomize_types=True, randomize_abilities=True, randomize_stats=True)
        modified, report = apply_species_rules(original, original, "qa-colosseum-v1", rules, tables)
        before, after = species_catalog(original, tables), species_catalog(modified, tables)
        self.assertEqual(len(after), 386)
        self.assertEqual(after[303]["national_dex"], 292)
        self.assertEqual(after[303]["stats"][0], 1)
        self.assertEqual({i: row["total"] for i, row in before.items()}, {i: row["total"] for i, row in after.items()})
        self.assertEqual(evolution_families(original, tables), evolution_families(modified, tables))
        self.assertGreater(report["species_changed"], 380)


if __name__ == "__main__":
    unittest.main()
