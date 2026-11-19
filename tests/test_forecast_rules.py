"""Forecast must stay useful when species abilities are randomized."""
from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine.species_rules import (
    CASTFORM_NATIONAL, FORECAST, apply_species_rules, species_catalog,
)
from orre_randomizer.options import Options
from orre_randomizer.xd_species_gameplay import (
    SPECIES_STRIDE, _species_catalog, patch_species_gameplay,
)
from tests.test_species_rules import Rules, fixture as colosseum_fixture
from tests.test_xd_species_gameplay import fixture as xd_fixture


def colosseum_castform():
    original, tables = colosseum_fixture()
    # Deliberately use a non-retail internal ID: the rule follows national dex.
    data = bytearray(original)
    row = tables["species"]["offset"] + 5 * tables["species"]["stride"]
    struct.pack_into(">H", data, row + 0x10, CASTFORM_NATIONAL)
    data[row + 0x32:row + 0x34] = bytes((FORECAST, 0))
    return bytes(data), tables, 5


def xd_castform():
    original, _, symbols, species, families = xd_fixture()
    data = bytearray(original)
    start = symbols[88]["offset"]
    castform = 385
    row = start + castform * SPECIES_STRIDE
    data[row:row + SPECIES_STRIDE] = data[start + SPECIES_STRIDE:start + 2 * SPECIES_STRIDE]
    struct.pack_into(">H", data, row + 0xE, CASTFORM_NATIONAL)
    data[row + 0x32:row + 0x34] = bytes((FORECAST, 0))
    species[castform] = (CASTFORM_NATIONAL,)
    families[castform] = castform
    return bytes(data), symbols, species, families, castform


class ForecastRulesTests(unittest.TestCase):
    def test_colosseum_castform_keeps_forecast_and_others_never_draw_it(self):
        original, tables, castform = colosseum_castform()
        for consistent in (False, True):
            rules = replace(Rules(), randomize_abilities=True,
                            abilities_family_consistent=consistent)
            for seed in range(16):
                with self.subTest(consistent=consistent, seed=seed):
                    result, _ = apply_species_rules(original, original, str(seed), rules, tables)
                    rows = species_catalog(result, tables)
                    self.assertEqual(rows[castform]["abilities"], (FORECAST, 0))
                    for index, row in rows.items():
                        if index != castform:
                            self.assertNotIn(FORECAST, row["abilities"])

    def test_xd_castform_keeps_forecast_and_others_never_draw_it(self):
        original, symbols, species, families, castform = xd_castform()
        for consistent in (False, True):
            options = replace(Options(), randomize_abilities=True,
                              abilities_family_consistent=consistent)
            for seed in range(16):
                with self.subTest(consistent=consistent, seed=seed):
                    result, _ = patch_species_gameplay(original, symbols, str(seed), species, families, options)
                    rows = _species_catalog(result, symbols, species)
                    self.assertEqual(rows[castform]["abilities"], (FORECAST, 0))
                    for index, row in rows.items():
                        if index != castform:
                            self.assertNotIn(FORECAST, row["abilities"])

    def test_colosseum_lock_does_not_protect_castform_stats_or_override_scope(self):
        original, tables, castform = colosseum_castform()
        rules = replace(Rules(), randomize_abilities=True, randomize_types=True, randomize_stats=True)
        with patch("orre_randomizer.preserved_pokemon.colosseum_species", return_value={1}):
            result, _ = apply_species_rules(original, original, "weather", rules, tables,
                                            selected_species={1, castform})
        before, after = [species_catalog(data, tables) for data in (original, result)]
        self.assertEqual(after[castform]["abilities"], (FORECAST, 0))
        self.assertNotEqual(after[castform]["stats"], before[castform]["stats"])
        for index in before:
            if index != castform:
                self.assertEqual(after[index], before[index])
        self.assertEqual(apply_species_rules(original, original, "weather", Rules(), tables)[0], original)

    def test_xd_lock_does_not_protect_castform_stats_or_override_scope(self):
        original, symbols, species, families, castform = xd_castform()
        options = replace(Options(), randomize_abilities=True, randomize_types=True, randomize_stats=True)
        result, _ = patch_species_gameplay(original, symbols, "weather", species, families, options,
                                           preserve_species={1}, selected_species={1, castform})
        before, after = [_species_catalog(data, symbols, species) for data in (original, result)]
        self.assertEqual(after[castform]["abilities"], (FORECAST, 0))
        self.assertNotEqual(after[castform]["stats"], before[castform]["stats"])
        for index in before:
            if index != castform:
                self.assertEqual(after[index], before[index])
        self.assertEqual(patch_species_gameplay(original, symbols, "weather", species, families, Options())[0],
                         original)


if __name__ == "__main__":
    unittest.main()
