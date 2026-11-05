"""Synthetic field-mask checks and optional original-PAL boss composition."""
from dataclasses import asdict, dataclass
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine import boss_rules
from orre_randomizer.engine.evolution_rules import evolution_families
from orre_randomizer.engine.gameplay_rules import MOVE_FIELDS, apply_rel_rules, damaging, expanded_layout, move_catalog
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.randomize_trainers import original_common
from orre_randomizer.engine.species_rules import species_catalog
from orre_randomizer.options import Options


@dataclass(frozen=True)
class BossTestOptions(Options):
    boss_stronger: bool = False
    boss_team_variety: bool = False


def options(**changes):
    return BossTestOptions(**{**asdict(Options()), "boss_stronger": False,
                             "boss_team_variety": False, **changes})


def fixture():
    data = bytearray(8192)
    tables = {"trainers": {"offset": 0, "count": 3, "stride": 0x34},
              "trainer_pokemon": {"offset": 0x100, "count": 13, "stride": 0x50},
              "species": {"offset": 0x800, "count": 9, "stride": 0x11C},
              "shadow": {"offset": 0x1800, "count": 2, "stride": 0x38}}
    struct.pack_into(">H", data, 4, 1)
    struct.pack_into(">H", data, 0x34 + 4, 7)
    for index in range(1, 9):
        pos = 0x800 + index * 0x11C
        struct.pack_into(">H", data, pos + 0x10, index)
        struct.pack_into(">I", data, pos + 0x18, 500 + index)
        data[pos + 0x32] = 1
        for field in (0x85, 0x87, 0x89, 0x8B, 0x8D, 0x8F):
            data[pos + field] = 50
    data[0x800 + 0x11C + 0x33] = 2
    # Species 1 and 2 are one evolution family.
    pos = 0x800 + 0x11C + 0x9C
    data[pos] = 4
    struct.pack_into(">HH", data, pos + 2, 16, 2)
    for index, species in ((1, 1), (2, 1), (3, 2), (4, 3), (6, 4), (7, 5)):
        pos = 0x100 + index * 0x50
        data[pos + 4] = 20
        data[pos] = 1 if species == 1 else 0
        struct.pack_into(">H", data, pos + 0xA, species)
        struct.pack_into(">I", data, pos + 0x14, 500 + species)
        for field, move in zip(MOVE_FIELDS, (10, 11, 13, 14)):
            struct.pack_into(">H", data, pos + field, move)
    shadow = 0x100 + 4 * 0x50
    data[shadow + 3] = 1
    data[shadow + 0x1C:shadow + 0x22] = b"\xff" * 6
    struct.pack_into(">H", data, 0x100 + 6 * 0x50 + MOVE_FIELDS[0], 0xFFFF)
    return bytes(data), tables, [{"key": "fixture", "trainer_id": 0}]


class BossRuleTests(unittest.TestCase):
    def setUp(self):
        self.original, self.tables, self.bosses = fixture()

    def run_rules(self, current=None, **changes):
        return boss_rules.apply_boss_tables(self.original, current or self.original,
            "boss-fixture", options(**changes), self.tables, self.bosses)

    def test_disabled_rules_are_identity(self):
        result, report = self.run_rules()
        self.assertEqual(result, self.original)
        self.assertEqual(report["edits"], [])

    def test_stronger_uses_current_level_caps_and_only_documented_stat_bytes(self):
        current = bytearray(self.original)
        first = 0x100 + 0x50
        current[first + 4] = 99
        current[first + 0x1C] = 30
        current[first + 0x1D] = 255
        result, report = self.run_rules(bytes(current), boss_stronger=True)
        self.assertEqual(result[first + 4], 100)
        self.assertEqual(result[first + 0x1C:first + 0x22], bytes((30, 255, 20, 20, 20, 20)))
        allowed = {0x100 + i * 0x50 + f for i in (1, 2, 3)
                   for f in (4, *boss_rules.IV_FIELDS, *boss_rules.EV_FIELDS)}
        actual = {i for i, (a, b) in enumerate(zip(current, result)) if a != b}
        self.assertTrue(actual <= allowed)
        self.assertEqual(len(report["edits"]), 3)
        for row in report["edits"]:
            self.assertTrue(all(a <= b for a, b in zip(row["evs_before"], row["evs_after"])))
            self.assertLessEqual(sum(row["evs_after"]), 510)
        self.assertEqual(result[0x1800:], current[0x1800:])

    def test_ev_floor_does_not_reduce_existing_evs_or_exceed_legal_total(self):
        current = bytearray(self.original)
        pos = 0x100 + 0x50
        for field, value in zip(boss_rules.EV_FIELDS, (252, 252, 0, 0, 0, 0)):
            current[pos + field] = value
        result, report = self.run_rules(bytes(current), boss_stronger=True)
        self.assertEqual([result[pos + f] for f in boss_rules.EV_FIELDS], [252, 252, 0, 0, 0, 0])
        self.assertIn("ev_floor_skipped", report["edits"][0])

    def test_variety_preserves_shadow_empty_marker_and_nonboss_slots(self):
        result, report = self.run_rules(boss_team_variety=True)
        family = evolution_families(self.original, self.tables)[0]
        actual = [u16(result, 0x100 + i * 0x50 + 0xA) for i in (1, 2, 3, 4, 6)]
        self.assertEqual(len({family[index] for index in actual}), 5)
        self.assertEqual(len(report["edits"]), 2)
        self.assertEqual(report["unresolved_team_duplicates"], [])
        for index in (4, 5, 6, 7):
            pos = 0x100 + index * 0x50
            self.assertEqual(result[pos:pos + 0x50], self.original[pos:pos + 0x50])
        for row in report["edits"]:
            pos = row["offset"]
            self.assertEqual(struct.unpack_from(">I", result, pos + 0x14)[0], 500 + row["new_species_index"])
            self.assertEqual(result[pos], 0)
            self.assertEqual(result[pos + 4], self.original[pos + 4])
        self.assertEqual(self.run_rules(boss_team_variety=True)[0], result)

    def test_a_shared_team_is_preserved_entirely(self):
        current = bytearray(self.original)
        struct.pack_into(">H", current, 2 * 0x34 + 4, 1)
        result, report = boss_rules.apply_boss_tables(bytes(current), bytes(current), "seed",
            options(boss_stronger=True, boss_team_variety=True), self.tables, self.bosses)
        self.assertEqual(result, current)
        self.assertTrue(any(row["reason"] == "shared trainer slot" for row in report["skipped"]))

    def test_empty_filtered_pool_preserves_duplicates_and_reports_failure(self):
        result, report = self.run_rules(boss_team_variety=True, allow_gen1=False,
                                        allow_gen2=False, allow_gen3=False)
        self.assertEqual(result, self.original)
        self.assertEqual(len(report["unresolved_team_duplicates"]), 2)

    def test_reselected_moves_use_final_types_and_keep_subrecord_prefixes(self):
        current = bytearray(self.original)
        for index in range(1, 9):
            pos = 0x800 + index * 0x11C
            current[pos + 0x30:pos + 0x32] = b"\x0a\x0a"
        moves = {index: {"index": index, "type": kind, "power": 35, "pp": 20,
                         "accuracy": 100, "effect": 0}
                 for index, kind in ((10, 0), (11, 10), (13, 0), (14, 0))}
        with patch.object(boss_rules, "move_catalog", return_value=moves):
            result, report = self.run_rules(bytes(current), boss_team_variety=True,
                                            randomize_trainer_moves=True)
        for row in report["edits"]:
            pos = row["offset"]
            actual = [u16(result, pos + f) for f in MOVE_FIELDS]
            self.assertIn(11, actual)
            self.assertEqual(len(set(actual)), 4)
            for field in MOVE_FIELDS:
                self.assertEqual(result[pos + field - 6:pos + field], current[pos + field - 6:pos + field])


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires user's original local PAL image")
class PalBossRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_common(GAME)[2]
        cls.tables, cls.bosses = boss_rules.boss_inventory(cls.original)

    def test_pinned_inventory_names_variants_and_reference_ownership(self):
        self.assertEqual(len(self.bosses), 32)
        self.assertEqual(len({row["key"] for row in self.bosses}), 7)
        slots = [slot for row in self.bosses for slot in row["slots"]]
        self.assertEqual(len(slots), 161)
        self.assertEqual(sum(bool(s["shadow_id"]) for s in slots), 16)
        for row in self.bosses:
            for slot in row["slots"]:
                self.assertEqual(slot["referencing_trainers"], [row["trainer_id"]])

    def test_original_teams_varied_and_strengthened_without_shadow_changes(self):
        result, report = boss_rules.apply_boss_rules(self.original, self.original, "boss-pal",
            options(boss_stronger=True, boss_team_variety=True))
        self.assertEqual(len(report["edits"]), 145)
        self.assertEqual(sum(row["old_species_index"] != row["new_species_index"]
                             for row in report["edits"]), 12)
        self.assertEqual(report["unresolved_team_duplicates"], [])
        shadow = self.tables["shadow"]
        begin, end = shadow["offset"], shadow["offset"] + shadow["count"] * shadow["stride"]
        self.assertEqual(result[begin:end], self.original[begin:end])
        for boss in self.bosses:
            for row in boss["slots"]:
                if row["shadow_id"]:
                    pos = row["offset"]
                    self.assertEqual(result[pos:pos + 0x50], self.original[pos:pos + 0x50])

    def test_advanced_composition_preserves_48_shadow_families_and_move_guards(self):
        from orre_randomizer.service import transform_rel
        choices = options(boss_stronger=True, boss_team_variety=True,
            randomize_trainer_moves=True, randomize_types=True, randomize_abilities=True,
            randomize_stats=True, balance_species=True, allow_gen1=False, allow_gen2=False,
            allow_legendaries=False, trainer_level_multiplier=2.0)
        seed = "boss-advanced-pal"
        base = transform_rel(self.original, seed, choices)[0]
        current = apply_rel_rules(self.original, base, seed, choices)[0]
        result, report = boss_rules.apply_boss_rules(self.original, current, seed, choices)
        family = evolution_families(self.original, self.tables)[0]
        shadow = self.tables["shadow"]
        ids = [i for i in range(1, shadow["count"])
               if u16(self.original, shadow["offset"] + i * shadow["stride"] + 2)]
        self.assertEqual(len({family[u16(result, shadow["offset"] + i * shadow["stride"] + 2)] for i in ids}), 48)
        self.assertEqual(result[shadow["offset"]:shadow["offset"] + shadow["count"] * shadow["stride"]],
                         current[shadow["offset"]:shadow["offset"] + shadow["count"] * shadow["stride"]])
        catalog = species_catalog(result, self.tables)
        moves = move_catalog(self.original, expanded_layout(self.original))
        for row in report["edits"]:
            pos, species = row["offset"], row["new_species_index"]
            actual = [u16(result, pos + field) for field in MOVE_FIELDS]
            self.assertLessEqual(result[pos + 4], 100)
            self.assertTrue(any(damaging(moves[i]) and moves[i]["type"] in catalog[species]["types"] for i in actual))
            if row["old_species_index"] != species:
                self.assertGreater(catalog[species]["national_dex"], 251)
            for field in MOVE_FIELDS:
                self.assertEqual(result[pos + field - 6:pos + field], current[pos + field - 6:pos + field])
        self.assertEqual(boss_rules.apply_boss_rules(self.original, current, seed, choices)[0], result)


if __name__ == "__main__":
    unittest.main()
