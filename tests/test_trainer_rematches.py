"""Capture-state aliases, final roster fields and preserved progression teams."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.trainer_rematches import (
    merge_trainer_aliases, rematch_inventory, synchronize_rematch_tables,
    synchronize_trainer_rematches,
)
from orre_randomizer.options import Options


def fixture():
    tables = {"trainers": {"offset": 0x100, "count": 5, "stride": 0x34},
              "trainer_pokemon": {"offset": 0x300, "count": 40, "stride": 0x50},
              "species": {"offset": 0x1400, "count": 10, "stride": 0x11C}}
    data = bytearray(0x2200)
    for trainer, first in enumerate((1, 8, 15, 22, 29)):
        position = 0x100 + trainer * 0x34
        data[position + 3] = 4
        struct.pack_into(">H", data, position + 4, first)
        struct.pack_into(">I", data, position + 8, 6001 if trainer == 4 else 5001)
    for index in range(1, 10):
        position = 0x1400 + index * 0x11C
        struct.pack_into(">H", data, position + 0x10, index)
        struct.pack_into(">I", data, position + 0x18, 1000 + index)
        kind = 12 if index >= 6 else 11
        data[position + 0x30:position + 0x34] = bytes((kind, kind, 1, 0))
        data[position + 0x85:position + 0x91:2] = bytes([50] * 6)

    def add(index, species, level, shadow=0):
        position = 0x300 + index * 0x50
        data[position:position + 4] = bytes((0, 0, 5, shadow))
        data[position + 4] = level
        struct.pack_into(">H", data, position + 0xA, species)
        struct.pack_into(">H", data, position + 0x12, 100 + species)
        struct.pack_into(">I", data, position + 0x14, 1000 + species)
        struct.pack_into(">I", data, position + 0x18, 0xABC00000 + index)
        data[position + 0x1C:position + 0x22] = bytes([20] * 6)
        for field, move in zip((0x36, 0x3E, 0x46, 0x4E), (10, 11, 12, 13)):
            struct.pack_into(">H", data, position + field, move)

    add(1, 1, 30, shadow=5)
    for index, species, level in ((2, 2, 31), (3, 3, 32), (4, 4, 33),
                                  (8, 2, 31), (9, 3, 32), (10, 4, 33),
                                  (15, 5, 40), (16, 2, 31), (17, 3, 32), (18, 4, 33),
                                  (22, 2, 41), (23, 3, 42), (24, 4, 43),
                                  (29, 2, 31), (30, 3, 32), (31, 4, 33)):
        add(index, species, level)
    return bytes(data), tables


def record(data, index):
    position = 0x300 + index * 0x50
    return data[position:position + 0x50]


class RematchTests(unittest.TestCase):
    def setUp(self):
        self.original, self.tables = fixture()

    def changed(self):
        output = bytearray(self.original)
        for index, species in ((2, 7), (3, 8), (4, 9), (8, 1), (9, 2), (10, 3),
                               (16, 4), (17, 5), (18, 6)):
            position = 0x300 + index * 0x50
            struct.pack_into(">H", output, position + 0xA, species)
            struct.pack_into(">I", output, position + 0x14, 1000 + species)
            output[position + 4] += 10
            output[position + 0x1C] = index
            struct.pack_into(">H", output, position + 0x12, 200 + index)
            struct.pack_into(">H", output, position + 0x36, 100 + index)
        return bytes(output)

    def test_replacement_and_removed_shadow_variants_map_only_their_exact_common_records(self):
        pairs, aliases = rematch_inventory(self.original, self.tables)
        self.assertEqual([(row["trainer"], row["captured_trainer"]) for row in pairs], [(0, 1), (0, 2)])
        self.assertEqual(pairs[0]["replacement_slots"], [])
        self.assertEqual(pairs[1]["replacement_slots"], [15])
        self.assertEqual(aliases, ((2, 8), (3, 9), (4, 10), (2, 16), (3, 17), (4, 18)))

    def test_final_species_moves_items_levels_and_ivs_follow_the_original_with_opaque_ids_intact(self):
        current = self.changed()
        result, report, aliases = synchronize_rematch_tables(self.original, current, self.tables)
        allowed = set()
        for source, alias in aliases:
            a, b = record(result, source), record(result, alias)
            self.assertEqual(a[:0x18] + a[0x1C:], b[:0x18] + b[0x1C:])
            self.assertEqual(b[0x18:0x1C], record(current, alias)[0x18:0x1C])
            position = 0x300 + alias * 0x50
            allowed.update(range(position, position + 0x18))
            allowed.update(range(position + 0x1C, position + 0x50))
        actual = {i for i, (a, b) in enumerate(zip(current, result)) if a != b}
        self.assertTrue(actual <= allowed)
        for protected in (1, 15, 22, 23, 24, 29, 30, 31):
            self.assertEqual(record(result, protected), record(current, protected))
        self.assertEqual(report["changed_bytes"], len(actual))
        self.assertEqual(synchronize_rematch_tables(self.original, result, self.tables)[0], result)

    def test_original_and_disabled_species_remain_unchanged(self):
        options = replace(Options.none(), boss_team_variety=True, randomize_held_items=True)
        result, report, _ = synchronize_rematch_tables(self.original, self.original, self.tables,
                                                     seed="native", options=options, boss_ids={2})
        self.assertEqual(result, self.original)
        self.assertEqual(report["replacement_edits"], [])

    def test_captured_replacement_keeps_boss_diversity_and_the_shared_theme(self):
        current = bytearray(self.changed())
        struct.pack_into(">H", current, 0x300 + 15 * 0x50 + 0xA, 7)
        options = replace(Options.none(), randomize_trainers=True, boss_team_variety=True,
                          trainer_theme_mode="random", trainer_force_evolved=True,
                          trainer_evolution_level=1, allow_gen1=True)
        result, report, _ = synchronize_rematch_tables(self.original, bytes(current), self.tables,
                                                     seed="rematch", options=options, boss_ids={2})
        self.assertEqual(u16(result, 0x300 + 15 * 0x50 + 0xA), 6)
        self.assertEqual(len(report["replacement_edits"]), 1)
        self.assertEqual(report["unresolved_replacement_constraints"], [])
        self.assertEqual(record(result, 15)[0x18:0x1C], record(current, 15)[0x18:0x1C])

    def test_same_species_at_different_levels_or_different_trainer_identity_is_not_an_alias(self):
        _, aliases = rematch_inventory(self.original, self.tables)
        self.assertFalse(any(alias >= 22 for _, alias in aliases))

    def test_a_changed_post_battle_dialogue_does_not_change_the_native_team_identity(self):
        original = bytearray(self.original)
        struct.pack_into(">I", original, 0x100 + 0x34 + 0x2C, 12345)
        pairs, _ = rematch_inventory(bytes(original), self.tables)
        self.assertIn((0, 1), {(row["trainer"], row["captured_trainer"]) for row in pairs})

    def test_corrupt_slot_occupancy_or_shadow_status_is_rejected(self):
        for field in (3, 0xA):
            current = bytearray(self.changed())
            position = 0x300 + 8 * 0x50
            if field == 3:
                current[position + field] = 1
            else:
                current[position + field:position + field + 2] = bytes(2)
            with self.assertRaises(FormatError):
                synchronize_rematch_tables(self.original, bytes(current), self.tables)

    def test_alias_chains_and_overlapping_dancer_aliases_are_flattened_before_pid_builders(self):
        aliases = merge_trainer_aliases(((10, 20), (20, 30)), ((10, 20), (5, 10)))
        self.assertEqual(aliases, ((5, 10), (5, 20), (5, 30)))
        self.assertEqual(merge_trainer_aliases(tuple(reversed(aliases))), aliases)
        for bad in (-1, True, 65536):
            with self.assertRaises(FormatError):
                merge_trainer_aliases(((bad, 2),))


class NativeRematchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        folder = root / "build/region-compat-2026-11-02/rel-research"
        cls.sources = {}
        for tag in ("pal", "usa", "japan"):
            path = folder / tag / "common.fsys-common_rel.rel"
            if not path.exists():
                raise unittest.SkipTest("local extracted regional original tables are unavailable")
            cls.sources[tag] = path.read_bytes()

    def test_all_regions_admit_the_same_capture_variants_without_merging_progression(self):
        from orre_randomizer.engine.randomize_trainers import layout, randomize_rel
        for tag, original in self.sources.items():
            with self.subTest(region=tag):
                tables = layout(original)[0]
                pairs, aliases = rematch_inventory(original, tables)
                identities = {(row["trainer"], row["captured_trainer"]) for row in pairs}
                self.assertTrue({(211, 795), (212, 213), (214, 215)} <= identities)
                self.assertNotIn((211, 212), identities)
                self.assertIn((125, 126), identities)
                self.assertEqual((len(pairs), len(aliases)), (70, 184))
                current = randomize_rel(original, "rematch-native")[0]
                result, _, _ = synchronize_rematch_tables(original, current, tables)
                party = tables["trainer_pokemon"]
                for source, alias in aliases:
                    a, b = (party["offset"] + index * 0x50 for index in (source, alias))
                    self.assertEqual(result[a:a + 0x18] + result[a + 0x1C:a + 0x50],
                                     result[b:b + 0x18] + result[b + 0x1C:b + 0x50])
                    self.assertEqual(result[b + 0x18:b + 0x1C], current[b + 0x18:b + 0x1C])

    def test_native_seeded_shiny_flags_and_spinda_patterns_use_the_final_alias_source(self):
        from orre_randomizer.engine.colo_spinda import colo_spinda_seeds, colo_spinda_trainer_pid
        from orre_randomizer.engine.randomize_trainers import layout
        from orre_randomizer.engine.shiny_rules import apply_shiny_rules
        from orre_randomizer.engine.spinda import SPINDA
        dol_path = Path(__file__).resolve().parents[1] / "game/sys/main.dol"
        if not dol_path.exists():
            self.skipTest("local original executable is unavailable")
        original, dol = self.sources["pal"], dol_path.read_bytes()
        tables = layout(original)[0]
        aliases = merge_trainer_aliases(rematch_inventory(original, tables)[1], ((2479, 5412),))
        choices = replace(Options.none(), custom_shinies=True, seeded_shinies=True,
                          shiny_chance_percent=37.5)
        _, report = apply_shiny_rules(dol, dol, choices, seed="rematch-identity", trainer_aliases=aliases)
        flags = report["seeded_decisions"]["trainer_slots"]
        for source, alias in aliases:
            self.assertEqual(flags[str(source)], flags[str(alias)])
        source, alias = 2556, 5300
        current = bytearray(original)
        for index in (source, alias):
            struct.pack_into(">H", current, tables["trainer_pokemon"]["offset"] + index * 0x50 + 0xA, SPINDA)
        seeds = colo_spinda_seeds(original, bytes(current), dol, dol, "rematch-identity", aliases)
        self.assertEqual(seeds[f"trainer:{source}"], seeds[f"trainer:{alias}"])
        for shiny in (False, True):
            self.assertEqual(colo_spinda_trainer_pid(original, bytes(current), seeds, source, shiny),
                             colo_spinda_trainer_pid(original, bytes(current), seeds, alias, shiny))


if __name__ == "__main__":
    unittest.main()
