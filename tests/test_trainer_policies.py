"""Trainer constraints on small binary fixtures and the optional original PAL."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.boss_rules import apply_boss_rules, boss_inventory
from orre_randomizer.engine.evolution_rules import _species_and_edges, evolution_families
from orre_randomizer.engine.gameplay_rules import MOVE_FIELDS, apply_rel_rules
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.pool_filters import species_excluded
from orre_randomizer.engine.randomize_trainers import original_common
from orre_randomizer.engine.species_rules import species_catalog
from orre_randomizer.engine.trainer_policies import apply_trainer_policies, apply_trainer_tables
from orre_randomizer.options import Options


def fixture():
    data = bytearray(8192)
    tables = {"trainers": {"offset": 0, "count": 3, "stride": 0x34},
              "trainer_pokemon": {"offset": 0x100, "count": 13, "stride": 0x50},
              "species": {"offset": 0x800, "count": 9, "stride": 0x11C}}
    for trainer, first in ((0, 1), (1, 1), (2, 7)):
        struct.pack_into(">H", data, trainer * 0x34 + 4, first)
    for i, kind in enumerate((11, 11, 11, 10, 10, 12, 11, 11), 1):
        pos = 0x800 + i * 0x11C
        struct.pack_into(">H", data, pos + 0x10, i)
        struct.pack_into(">I", data, pos + 0x18, 500 + i)
        data[pos + 0x30:pos + 0x34] = bytes((kind, kind, 1, 0))
        for f in (0x85, 0x87, 0x89, 0x8B, 0x8D, 0x8F):
            data[pos + f] = 30 + 10 * i
    for source, target in ((1, 2), (2, 3)):
        pos = 0x800 + source * 0x11C + 0x9C
        data[pos] = 4
        struct.pack_into(">HH", data, pos + 2, 16, target)
    for i, species, level in ((1, 1, 40), (2, 4, 50), (3, 6, 80), (4, 2, 60),
                              (7, 1, 39), (8, 2, 40), (9, 7, 50)):
        pos = 0x100 + i * 0x50
        data[pos], data[pos + 4] = 1, level
        struct.pack_into(">H", data, pos + 0xA, species)
        struct.pack_into(">I", data, pos + 0x14, 500 + species)
        for f, move in zip(MOVE_FIELDS, (10, 11, 13, 14), strict=True):
            struct.pack_into(">H", data, pos + f, move)
    data[0x100 + 3 * 0x50 + 3] = 1
    struct.pack_into(">H", data, 0x100 + 4 * 0x50 + MOVE_FIELDS[0], 0xFFFF)
    return bytes(data), tables


class TrainerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.original, self.tables = fixture()

    def run_policy(self, current=None, seed="constraints", **kwargs):
        return apply_trainer_tables(self.original, current or self.original, seed,
            replace(Options.none(), allow_gen1=True, allow_gen2=True, allow_gen3=True, **kwargs),
            self.tables, [{"trainer_id": 0}])

    def species(self, data, index):
        return u16(data, 0x100 + index * 0x50 + 0xA)

    def test_inactive_and_theme_without_species_randomization_are_identity(self):
        for kwargs in ({}, {"trainer_theme_mode": "random"}):
            result, report = self.run_policy(**kwargs)
            self.assertEqual(result, self.original)
            self.assertEqual(report["edits"], [])

    def test_final_evolution_without_randomization_uses_own_descendants_and_final_level(self):
        result, report = self.run_policy(trainer_force_evolved=True, trainer_evolution_level=40)
        for i, expected in ((1, 3), (2, 4), (3, 6), (4, 3), (7, 1), (8, 3), (9, 7)):
            self.assertEqual(self.species(result, i), expected)
        self.assertEqual(u16(result, 0x100 + 4 * 0x50 + MOVE_FIELDS[0]), 0xFFFF)
        self.assertEqual(result[:0x100], self.original[:0x100])
        self.assertEqual(len([row for row in report["edits"] if row["index"] == 1]), 1)
        row = next(row for row in report["edits"] if row["index"] == 1)
        self.assertEqual(row["referencing_trainers"], [0, 1])
        current = bytearray(self.original)
        current[0x100 + 7 * 0x50 + 4] = 43  # Already received a level/boss bonus.
        result, _ = self.run_policy(bytes(current), trainer_force_evolved=True)
        self.assertEqual(self.species(result, 7), 3)

    def test_random_theme_final_forms_and_boss_family_uniqueness_share_records(self):
        result, report = self.run_policy(randomize_trainers=True, trainer_theme_mode="random",
            trainer_force_evolved=True, trainer_evolution_level=1, boss_team_variety=True)
        family = evolution_families(self.original, self.tables)[0]
        catalog = species_catalog(result, self.tables)
        for group in report["groups"]:
            self.assertTrue(all(group["type"] in catalog[self.species(result, i)]["types"] for i in group["slots"]))
        self.assertEqual(len({family[self.species(result, i)] for i in (1, 2, 3, 4)}), 4)
        self.assertFalse(any(self.species(result, i) in (1, 2) for i in (1, 2, 4, 7, 8, 9)))
        shadow = 0x100 + 3 * 0x50
        self.assertEqual(result[shadow:shadow + 0x50], self.original[shadow:shadow + 0x50])
        self.assertEqual(self.run_policy(randomize_trainers=True, trainer_theme_mode="random",
            trainer_force_evolved=True, trainer_evolution_level=1, boss_team_variety=True)[0], result)

    def test_preserve_theme_uses_original_common_type_and_reports_fallback(self):
        original = bytearray(self.original)
        # Make first team originally all Water except its protected Shadow.
        struct.pack_into(">H", original, 0x100 + 2 * 0x50 + 0xA, 7)
        self.original = bytes(original)
        result, report = self.run_policy(randomize_trainers=True, trainer_theme_mode="preserve")
        self.assertTrue(all(g["type"] == 11 and g["original_type_preserved"] for g in report["groups"]))
        result, report = self.run_policy(randomize_trainers=True, trainer_theme_mode="preserve", excluded_types=(11,))
        self.assertTrue(all(g["type"] != 11 and not g["original_type_preserved"] for g in report["groups"]))

    def test_hard_exclusions_use_native_types_even_after_type_randomization(self):
        current = bytearray(self.original)
        # Species 3 becomes Fire, but must still be excluded as original Water.
        pos = 0x800 + 3 * 0x11C
        current[pos + 0x30:pos + 0x32] = bytes((10, 10))
        result, _ = self.run_policy(bytes(current), randomize_trainers=True, trainer_theme_mode="random",
                                   trainer_force_evolved=True, excluded_types=(11,), excluded_species=(4,))
        self.assertTrue(all(self.species(result, i) in (5, 6) for i in (1, 2, 4, 7, 8, 9)))

    def test_impossible_constraints_refuse_instead_of_relaxing_exclusions(self):
        for kwargs in ({"excluded_species": tuple(range(1, 9))},
                       {"excluded_species": (3,), "randomize_trainers": False},
                       {"excluded_types": (11, 12), "boss_team_variety": True}):
            with self.assertRaises(FormatError):
                self.run_policy(randomize_trainers=kwargs.get("randomize_trainers", True),
                                trainer_theme_mode="random", trainer_force_evolved=True,
                                **{k:v for k,v in kwargs.items() if k != "randomize_trainers"})


@unittest.skipUnless(Path("game/files/common.fsys").exists(), "requires user's local original PAL dump")
class PalTrainerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_common(Path("game"))[2]
        cls.tables, cls.bosses = boss_inventory(cls.original)

    def test_combined_filters_themes_final_stages_shadow_families_and_moves(self):
        from orre_randomizer.service import transform_rel
        choices = replace(Options.recommended(), excluded_species=(25, 133, 196, 197),
            excluded_types=(0,), trainer_theme_mode="preserve", trainer_force_evolved=True,
            trainer_evolution_level=45, trainer_level_multiplier=1.15, boss_stronger=True,
            randomize_types=True, randomize_stats=True)
        seed = "pal-combined-constraints"
        base = transform_rel(self.original, seed, choices)[0]
        filtered = apply_rel_rules(self.original, base, seed, choices)[0]
        current = apply_boss_rules(self.original, filtered, seed, choices)[0]
        result, report = apply_trainer_policies(self.original, current, seed, choices)
        self.assertGreater(len(report["edits"]), 1000)
        native = species_catalog(self.original, self.tables)
        catalog = species_catalog(result, self.tables)
        children = {e["species_index"] for e in _species_and_edges(self.original, self.tables)[1]}
        for row in report["edits"]:
            species = row["after_species"]
            self.assertNotEqual(species, row["original_species"])
            self.assertFalse(species_excluded(native[species], choices))
            self.assertIn(row["type"], catalog[species]["types"])
            if row["final_stage_required"]:
                self.assertNotIn(species, children)
        family = evolution_families(self.original, self.tables)[0]
        shadow = self.tables["shadow"]
        picks = [u16(result, shadow["offset"] + sid * shadow["stride"] + 2)
                 for sid in range(1, shadow["count"]) if u16(self.original, shadow["offset"] + sid * shadow["stride"] + 2)]
        self.assertEqual(len({family[s] for s in picks}), 48)
        self.assertTrue(all(not species_excluded(native[s], choices) for s in picks))
        for boss in self.bosses:
            team = [u16(result, row["offset"] + 0xA) for row in boss["slots"]]
            self.assertEqual(len(team), len({family[s] for s in team}))
        table = self.tables["trainer_pokemon"]
        for i in range(table["count"]):
            pos = table["offset"] + i * table["stride"]
            if self.original[pos + 3]:
                self.assertEqual(result[pos:pos + table["stride"]], current[pos:pos + table["stride"]])
        self.assertEqual(apply_trainer_policies(self.original, current, seed, choices)[0], result)


if __name__ == "__main__":
    unittest.main()
