"""Retained species keep native properties without changing other seeded draws."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.options import Options
from orre_randomizer.presets import recommended_preset, species_preset
from orre_randomizer.preserved_pokemon import colosseum_species, colosseum_encounter_kept
from orre_randomizer.profiles import (PREVIOUS_PROPERTIES_ENGINE, PREVIOUS_XD_PROPERTIES_ENGINE,
    parse_profile, parse_xd_profile, save_profile)
from orre_randomizer.service import UserError
from orre_randomizer.xd import XDOptions
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.species_rules import apply_species_rules, species_catalog
from orre_randomizer.engine.tm_rules import apply_tm_tables, ORIGINAL_TM_MOVES
from orre_randomizer.xd_species_gameplay import (patch_species_gameplay, patch_tm_gameplay,
    SPECIES_STRIDE, TM_OFFSETS)
from test_species_rules import fixture as species_fixture
from test_tm_rules import fixture as tm_fixture
from test_xd_species_gameplay import fixture as xd_fixture


class PreservationOptionsTests(unittest.TestCase):
    def test_both_games_and_both_randomized_presets_default_to_original_properties(self):
        for options in (recommended_preset(), species_preset(), XDOptions.recommended(), XDOptions.species_only()):
            self.assertFalse(options.randomize_preserved_properties)
        self.assertFalse(replace(Options.none(), randomize_preserved_properties=True).has_changes)
        from orre_randomizer.settings_presentation import effective_xd_setting_names
        self.assertFalse(effective_xd_setting_names(replace(XDOptions.unchanged(), randomize_preserved_properties=True)))

    def test_current_profiles_roundtrip_and_old_profiles_explicitly_keep_old_rules(self):
        import hashlib
        for xd in (False, True):
            options = XDOptions.recommended() if xd else recommended_preset()
            parser = parse_xd_profile if xd else parse_profile
            for enabled in (False, True):
                current = replace(options, randomize_preserved_properties=enabled)
                with tempfile.TemporaryDirectory() as folder:
                    payload = save_profile(Path(folder) / 'profile.json', 'preservation', current)
                self.assertEqual(parser(json.dumps(payload).encode()).options, current)
            payload['options'].pop('randomize_preserved_properties')
            payload['engine_version'] = PREVIOUS_XD_PROPERTIES_ENGINE if xd else PREVIOUS_PROPERTIES_ENGINE
            payload.pop('configuration_sha256')
            payload['configuration_sha256'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            self.assertTrue(parser(json.dumps(payload).encode()).options.randomize_preserved_properties)
            payload['options']['randomize_preserved_properties'] = False
            with self.assertRaises(UserError):
                parser(json.dumps(payload).encode())

    def test_new_flag_is_a_strict_boolean(self):
        for value in (0, 1, None, 'false'):
            for xd in (False, True):
                options = replace(XDOptions.recommended() if xd else recommended_preset(),
                                  randomize_preserved_properties=value)
                with tempfile.TemporaryDirectory() as folder, self.subTest(xd=xd, value=value), self.assertRaises(UserError):
                    save_profile(Path(folder) / 'bad.json', 'seed', options)


class RetainedSpeciesTests(unittest.TestCase):
    def test_native_family_is_preserved_but_manual_replacement_is_not(self):
        original, tables = species_fixture()
        options = replace(Options.recommended(), starter_umbreon=False)
        with patch('orre_randomizer.engine.randomize_story.SPECIALS', [{'key': 'umbreon', 'old': 1}]):
            self.assertEqual(colosseum_species(original, tables, options), {1, 2, 9})
            self.assertFalse(colosseum_species(original, tables, replace(options, starter_umbreon=True,
                                                                        starter_umbreon_species=1)))
            self.assertFalse(colosseum_species(original, tables, replace(options, randomize_preserved_properties=True)))

    def test_retained_colosseum_species_keep_stats_types_abilities_and_other_draws(self):
        original, tables = species_fixture()
        options = replace(Options.recommended(), randomize_stats=True, randomize_types=True)
        with patch('orre_randomizer.preserved_pokemon.colosseum_species', return_value={1, 2, 9}):
            kept = apply_species_rules(original, original, 'properties', options, tables)[0]
        with patch('orre_randomizer.preserved_pokemon.colosseum_species', return_value=set()):
            all_changed = apply_species_rules(original, original, 'properties', options, tables)[0]
        before, after, legacy = [species_catalog(data, tables) for data in (original, kept, all_changed)]
        for index in before:
            self.assertEqual(after[index], before[index] if index in (1, 2, 9) else legacy[index])
        self.assertNotEqual(all_changed, kept)

    def test_native_shadow_moves_and_items_respect_the_species_toggle(self):
        original = bytearray(16)
        options = Options.recommended()
        for sid in (0, 1, 21, 23, 34):
            original[3] = sid
            self.assertEqual(colosseum_encounter_kept(original, 0, options), sid in (21, 23, 34))
            self.assertFalse(colosseum_encounter_kept(original, 0, replace(options, randomize_preserved_properties=True)))
        self.assertTrue(colosseum_encounter_kept(original, 0, replace(options, randomize_shadows=False)))

    def test_retained_colosseum_tm_moves_remain_identical_despite_global_permutation(self):
        rel, dol, tables = tm_fixture()
        options = replace(Options.recommended(), tm_compatibility_mode='universal')
        with patch('orre_randomizer.preserved_pokemon.colosseum_species', return_value={1}):
            changed, final, _ = apply_tm_tables(rel, rel, dol, dol, 'compatibility', options, tables)
        from orre_randomizer.engine.tm_rules import TM_OFFSET
        moves = [u16(final, TM_OFFSET + i * 8 + 6) for i in range(50)]
        self.assertNotEqual(moves, list(ORIGINAL_TM_MOVES))
        pos = tables['species']['offset'] + tables['species']['stride'] + 0x34
        native = {move for i, move in enumerate(ORIGINAL_TM_MOVES) if rel[pos+i]}
        self.assertEqual({move for i, move in enumerate(moves) if changed[pos+i]}, native)
        self.assertEqual(changed[pos+tables['species']['stride']:pos+tables['species']['stride']+50], b'\1'*50)

    def test_xd_retained_species_keep_native_properties_and_selected_projection_is_exact(self):
        rel, _, symbols, species, families = xd_fixture()
        options = replace(XDOptions.recommended(), randomize_types=True, randomize_stats=True)
        modified, _ = patch_species_gameplay(rel, symbols, 'properties', species, families, options,
                                            preserve_species={1})
        projected, _ = patch_species_gameplay(rel, symbols, 'properties', species, families, options,
                                             preserve_species={1}, selected_species={1, 2})
        full, _ = patch_species_gameplay(rel, symbols, 'properties', species, families, options)
        start = symbols[88]['offset']
        for index in species:
            span = slice(start+index*SPECIES_STRIDE, start+(index+1)*SPECIES_STRIDE)
            self.assertEqual(modified[span], rel[span] if index == 1 else full[span])
            self.assertEqual(projected[span], modified[span] if index in (1, 2) else rel[span])
        self.assertNotEqual(modified, full)

    def test_xd_retained_tm_moves_remain_identical_with_universal_rules_for_others(self):
        rel, dol, symbols, species, _ = xd_fixture()
        options = replace(XDOptions.recommended(), tm_compatibility_mode='universal')
        changed, final, _ = patch_tm_gameplay(rel, dol, symbols, 'GXXJ01', 'compatibility', species, options,
                                            preserve_species={1})
        moves = [u16(final, TM_OFFSETS['GXXJ01']+i*8+6) for i in range(50)]
        pos = symbols[88]['offset']+SPECIES_STRIDE+0x34
        native = {move for i, move in enumerate(ORIGINAL_TM_MOVES) if rel[pos+i]}
        self.assertEqual({move for i, move in enumerate(moves) if changed[pos+i]}, native)
        self.assertEqual(changed[pos+SPECIES_STRIDE:pos+SPECIES_STRIDE+50], b'\1'*50)


if __name__ == '__main__':
    unittest.main()
