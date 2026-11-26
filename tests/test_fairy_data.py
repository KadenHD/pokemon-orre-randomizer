from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.fairy_data import (
    DATA_DIRECTORY, DATA_SHA256, FAIRY_SPECIES, LANGUAGES, NEW_MOVE_IDS,
    RETYPE_MOVE_IDS, FairyLearnsetOverflow, _data, apply_type_baseline, apply_levelup_baseline,
    compatibility, fairy_matchups, learning_records, localized_move_names,
    merge_natural_learnset, move_definition, move_description, move_name,
    native_move_ids, native_type, new_move_catalog, project_catalog,
    reference_manifest, species_types, type_name,
)


ALLOCATED = dict(zip(NEW_MOVE_IDS, range(375, 382)))
NATIVE_EFFECTS = dict(zip(NEW_MOVE_IDS, range(100, 107)))


def baseline_fixture(game):
    tables = {'species': {'offset': 16, 'count': 20, 'stride': 0x40},
              'moves': {'offset': 0x600, 'count': 358, 'stride': 0x34}}
    rel = bytearray(b'\xA5' * (0x600 + 358 * 0x34 + 32))
    data = reference_manifest()
    for slot, national in enumerate((25, *FAIRY_SPECIES, 386)):
        pos = 16 + slot * 0x40
        struct.pack_into('>H', rel, pos + (0x10 if game == 'colosseum' else 0x0E), national)
        if national in FAIRY_SPECIES:
            types = tuple(native_type(value, fairy_type_id=19)
                          for value in data['species'][str(national)]['native_generation_three_types'])
            if len(types) == 1:
                types *= 2
        else:
            types = (13, 13) if national == 25 else (14, 14)
        rel[pos + 0x30:pos + 0x32] = bytes(types)
    for move in RETYPE_MOVE_IDS:
        pos = 0x600 + move * 0x34
        rel[pos + 1:pos + 3] = bytes((10, 0))
    return bytes(rel), tables


def learning_fixture(game):
    table = {'offset': 32, 'count': 387, 'stride': 0x124}
    rel = bytearray(32 + 387 * 0x124 + 16)
    national_offset, learning_offset = (0x10, 0xBA) if game == 'colosseum' else (0x0E, 0xC4)
    for national in range(1, 387):
        pos = 32 + national * 0x124
        struct.pack_into('>H', rel, pos + national_offset, national)
        rel[pos + 0x50:pos + 0x54] = b'keep'
        for slot, (level, move) in enumerate(((1, 45), (10, 93))):
            field = pos + learning_offset + slot * 4
            rel[field] = level
            struct.pack_into('>H', rel, field + 2, move)
    return bytes(rel), table


class PinnedFairyReference(unittest.TestCase):
    def test_pinned_registry_has_complete_reference_provenance_and_six_languages(self):
        self.assertEqual(hashlib.sha256((DATA_DIRECTORY / 'catalog.json').read_bytes()).hexdigest(), DATA_SHA256)
        data = reference_manifest()
        self.assertEqual(data['reference_version_group']['identifier'], 'brilliant-diamond-shining-pearl')
        self.assertEqual(data['coverage'], {'national_species': 386, 'fairy_retyped_species': 18,
                                           'existing_retyped_moves': 3, 'new_moves': 7})
        self.assertEqual(data['provenance']['pokemon_moves.csv']['national_species_with_any_baseline_move'], 386)
        self.assertEqual(data['provenance']['pokemon_moves.csv']['selected_rows'], 223)
        self.assertIn('Redistribution and use in source and binary forms',
                      (DATA_DIRECTORY / 'LICENSE-PokeAPI.txt').read_text('utf-8'))
        for canonical in RETYPE_MOVE_IDS + NEW_MOVE_IDS:
            row = move_definition(canonical)
            self.assertEqual(set(row['names']), set(LANGUAGES))
            self.assertEqual(set(row['descriptions']), set(LANGUAGES))
            for language in LANGUAGES:
                self.assertTrue(move_name(canonical, language))
                self.assertTrue(move_description(canonical, language))
                self.assertFalse(any(char in move_description(canonical, language) for char in '\n\r\f'))

    def test_data_tampering_fails_closed_without_changing_the_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'catalog.json').write_bytes((DATA_DIRECTORY / 'catalog.json').read_bytes() + b' ')
            _data.cache_clear()
            try:
                with patch('orre_randomizer.fairy_data.DATA_DIRECTORY', root), self.assertRaises(FormatError):
                    reference_manifest()
            finally:
                _data.cache_clear()
        self.assertEqual(reference_manifest()['coverage']['new_moves'], 7)

    def test_reference_exports_are_independent_and_locale_fallback_is_english(self):
        data = reference_manifest()
        data['moves']['583']['names']['fr'] = 'modified'
        self.assertEqual(move_name(583, 'fr'), 'Câlinerie')
        row = move_definition(583)
        row['flags'].clear()
        self.assertIn('contact', move_definition(583)['flags'])
        self.assertEqual(move_name(605, 'fr'), 'Éclat magique')
        self.assertEqual(move_name(577, 'fr'), 'Vampibaiser')
        self.assertEqual(move_name(605, 'fr', uppercase=True), 'ÉCLAT MAGIQUE')
        self.assertEqual(move_name(583, 'unconfigured'), move_name(583, 'en'))
        self.assertEqual(move_description(583, 'unconfigured'), move_description(583, 'en'))
        self.assertEqual(type_name('fr'), 'Fée')
        self.assertEqual(type_name('ja'), 'フェアリー')
        self.assertEqual(type_name('unknown'), 'Fairy')

    def test_native_ids_never_confuse_national_and_canonical_namespaces(self):
        self.assertEqual(species_types(35, fairy_type_id=19), (19, 19))
        self.assertEqual(species_types(176, fairy_type_id=19), (19, 2))
        self.assertEqual(species_types(183, fairy_type_id=19), (11, 19))
        self.assertEqual(species_types(282, fairy_type_id=19), (14, 19))
        self.assertEqual(species_types(303, fairy_type_id=19), (8, 19))
        self.assertIsNone(species_types(25, fairy_type_id=19))
        for value in (True, 0, 410, -1):
            with self.assertRaises(ValueError):
                species_types(value, fairy_type_id=19)
        for value in (True, 9, 18, 0, 256):
            with self.assertRaises(ValueError):
                species_types(35, fairy_type_id=value)
        for value in (0, 19, 10001, True):
            with self.assertRaises(ValueError):
                native_type(value, fairy_type_id=19)

    def test_fairy_chart_contains_only_ordinary_fairy_interactions(self):
        chart = fairy_matchups(fairy_type_id=19)
        self.assertEqual(len(chart), 35)
        self.assertEqual(chart[19, 16], 200)  # Fairy -> Dragon.
        self.assertEqual(chart[16, 19], 0)
        self.assertEqual(chart[3, 19], 200)   # Poison -> Fairy.
        self.assertEqual(chart[8, 19], 200)   # Steel -> Fairy.
        self.assertEqual(chart[19, 10], 50)  # Fire resists Fairy.
        self.assertEqual(chart[1, 19], 50)   # Fairy resists Fighting.
        self.assertFalse(any(9 in pair or 18 in pair for pair in chart))
        self.assertNotIn((7, 8), chart)       # No global Ghost/Steel update.

    def test_new_move_catalog_requires_independently_qualified_native_effects(self):
        rows = new_move_catalog(ALLOCATED, NATIVE_EFFECTS, fairy_type_id=19)
        self.assertEqual(set(rows), set(range(375, 382)))
        self.assertEqual(rows[376]['drain_percent'], 75)
        self.assertEqual(rows[377]['damage_class'], 'physical')
        self.assertEqual(rows[377]['effect_chance'], 10)
        self.assertEqual(rows[379]['effect_chance'], 30)
        self.assertEqual(rows[381]['priority'], 1)
        self.assertEqual(rows[375]['target'], 'all-opponents')
        self.assertIn('sound', rows[375]['flags'])
        self.assertIn('authentic', rows[375]['flags'])
        self.assertTrue(rows[375]['always_hits'])
        for canonical in NEW_MOVE_IDS:
            self.assertEqual(rows[ALLOCATED[canonical]]['effect'], NATIVE_EFFECTS[canonical])
            self.assertEqual(rows[ALLOCATED[canonical]]['canonical_effect_id'], move_definition(canonical)['canonical_effect_id'])
        for invalid in ({}, {**NATIVE_EFFECTS, 574: True}, {**NATIVE_EFFECTS, 574: -1}):
            with self.assertRaises(ValueError):
                new_move_catalog(ALLOCATED, invalid, fairy_type_id=19)

    def test_move_allocation_rejects_shadow_collisions_aliases_and_retyping_old_ids(self):
        self.assertEqual(native_move_ids(ALLOCATED)[186], 186)
        self.assertEqual(localized_move_names(ALLOCATED, 'fr')[380], 'Éclat magique')
        for invalid in ({}, {**ALLOCATED, 574: 355}, {**ALLOCATED, 574: 374},
                        {**ALLOCATED, 574: True}, {**ALLOCATED, 574: 376},
                        {**ALLOCATED, 186: 375, 204: 204, 236: 236}):
            with self.assertRaises(ValueError):
                native_move_ids(invalid)


class FairyLearning(unittest.TestCase):
    def test_method_evidence_does_not_invent_official_tm_compatibility(self):
        self.assertEqual(compatibility(303, method='machine'), (False,) * 7)
        learnable = compatibility(303, method='learnable')
        self.assertTrue(learnable[2])  # Mawile naturally learns Play Rough.
        self.assertTrue(learnable[3])  # And Fairy Wind.
        self.assertFalse(learnable[5])
        self.assertTrue(compatibility(151)[5])  # Mew -> native BDSP Dazzling Gleam TM.
        self.assertEqual(compatibility(132), (False,) * 7)
        self.assertEqual(compatibility(132, method='learnable'), (False,) * 7)
        with self.assertRaises(ValueError):
            compatibility(303, method='inferred')

    def test_native_moves_and_levels_survive_merge_with_ordered_new_fairy_additions(self):
        native = ((1, 45), (1, 204), (3, 6), (20, 93), (40, 94))
        plan = merge_natural_learnset(282, native, ALLOCATED)
        self.assertEqual(plan.native, native)
        self.assertEqual(tuple(row for row in plan.learnset if row in native), native)
        self.assertEqual(plan.learnset.count((1, 204)), 1)
        self.assertIn((1, 379), plan.additions)  # Moonblast from the pinned reference.
        self.assertIn((12, 376), plan.additions)
        self.assertEqual(tuple(sorted(plan.learnset, key=lambda row: row[0])), plan.learnset)
        self.assertEqual(plan.evolution_moves, (380,))
        self.assertNotIn(0, [level for level, _move in plan.learnset])
        self.assertEqual(merge_natural_learnset(282, plan.learnset, ALLOCATED).learnset, plan.learnset)

    def test_evolution_only_rows_are_separate_from_legitimate_level_one_records(self):
        plan = merge_natural_learnset(176, (), ALLOCATED)
        self.assertEqual(plan.evolution_moves, (378,))
        self.assertIn((1, 378), plan.learnset)  # Separate actual BDSP level-one row.
        self.assertEqual(len([row for row in learning_records(176) if row['move'] == 584 and row['method'] == 1]), 2)

    def test_overflow_is_reported_losslessly_and_never_serialized_by_truncation(self):
        native = tuple((level, level) for level in range(1, 20))
        plan = merge_natural_learnset(282, native, ALLOCATED)
        self.assertTrue(plan.requires_relocation)
        self.assertGreater(len(plan.learnset), 19)
        self.assertEqual(plan.overflow_records, plan.learnset[19:])
        for row in native:
            self.assertIn(row, plan.learnset)
        with self.assertRaises(FairyLearnsetOverflow) as error:
            plan.require_inline_capacity()
        self.assertIs(error.exception.plan, plan)
        self.assertEqual(merge_natural_learnset(25, (), ALLOCATED).require_inline_capacity(),
                         merge_natural_learnset(25, (), ALLOCATED).learnset)

    def test_learning_validation_rejects_terminators_boolean_ids_and_unordered_records(self):
        for native in (((0, 45),), ((1, True),), ((101, 45),), ((2, 45), (1, 93)), ((1, 0),)):
            with self.assertRaises(ValueError):
                merge_natural_learnset(282, native, ALLOCATED)
        with self.assertRaises(ValueError):
            merge_natural_learnset(282, (), ALLOCATED, native_capacity=0)

    def test_catalog_projection_respects_national_ids_and_leaves_native_traits_intact(self):
        original = {410: {'national_dex': 282, 'types': (14, 14), 'abilities': (28, 36),
                          'stats': (68, 65, 65, 125, 115, 80), 'learnset': ((1, 45), (6, 93))},
                    19: {'national_dex': 25, 'types': (13, 13), 'abilities': (9, 0), 'learnset': ()}}
        frozen = copy.deepcopy(original)
        projected = project_catalog(original, fairy_type_id=19, move_ids=ALLOCATED)
        self.assertEqual(original, frozen)
        self.assertEqual(projected[410]['types'], (14, 19))
        self.assertEqual(projected[19]['types'], (13, 13))
        self.assertEqual(projected[410]['abilities'], original[410]['abilities'])
        self.assertEqual(projected[410]['stats'], original[410]['stats'])
        self.assertIn((12, 376), projected[410]['learnset'])
        self.assertIs(project_catalog(original, fairy_type_id=9, enabled=False), original)


class NativeFairyTypeBaseline(unittest.TestCase):
    def test_both_layouts_change_only_the_qualified_type_fields_and_are_idempotent(self):
        for game in ('colosseum', 'xd'):
            with self.subTest(game=game):
                original, tables = baseline_fixture(game)
                result, report = apply_type_baseline(original, tables, game=game, fairy_type_id=19)
                self.assertEqual(len(report['species_edits']), 18)
                self.assertEqual(len(report['move_edits']), 3)
                allowed = {16 + slot * 0x40 + field for slot in range(1, 19) for field in (0x30, 0x31)}
                allowed.update(0x600 + move * 0x34 + 2 for move in RETYPE_MOVE_IDS)
                self.assertTrue(all(before == after or index in allowed
                                    for index, (before, after) in enumerate(zip(original, result))))
                repeated, again = apply_type_baseline(result, tables, game=game, fairy_type_id=19)
                self.assertEqual(repeated, result)
                self.assertEqual(again['changed_bytes'], 0)
                self.assertTrue(report['only_type_fields_changed'])

    def test_disabled_option_is_exact_passthrough_without_layout_or_asset_reads(self):
        original = b'unchanged native baseline'
        with patch('orre_randomizer.fairy_data._data', side_effect=AssertionError('must not read')):
            result, report = apply_type_baseline(original, {}, game='unsupported', fairy_type_id=9, enabled=False)
        self.assertIs(result, original)
        self.assertFalse(report['applied'])

    def test_incomplete_duplicate_or_already_randomized_sources_fail_without_writes(self):
        original, tables = baseline_fixture('xd')
        for offset, value in ((16 + 0x40 + 0x0E, b'\x00\x19'),
                              (16 + 19 * 0x40 + 0x0E, b'\x00\x23'),
                              (16 + 0x40 + 0x30, b'\x0A\x0A'),
                              (0x600 + 186 * 0x34 + 2, b'\x0A')):
            damaged = bytearray(original)
            damaged[offset:offset + len(value)] = value
            before = bytes(damaged)
            with self.assertRaises(FormatError):
                apply_type_baseline(bytes(damaged), tables, game='xd', fairy_type_id=19)
            self.assertEqual(bytes(damaged), before)
        for bad_tables in ({}, {**tables, 'moves': {'offset': 16, 'count': 358, 'stride': 0x34}},
                           {**tables, 'moves': {'offset': 0x600, 'count': 10, 'stride': 0x34}}):
            with self.assertRaises(FormatError):
                apply_type_baseline(original, bad_tables, game='xd', fairy_type_id=19)
        self.assertEqual(baseline_fixture('xd')[0], original)


class NativeFairyLearningBaseline(unittest.TestCase):
    def test_inline_merge_preserves_native_traits_flags_and_moves_in_both_layouts(self):
        for game in ('colosseum', 'xd'):
            with self.subTest(game=game):
                original, table = learning_fixture(game)
                result, report = apply_levelup_baseline(original, table, game=game, move_ids=ALLOCATED)
                allowed = set()
                offset = 0xBA if game == 'colosseum' else 0xC4
                for row in report['species_edits']:
                    self.assertIn((1, 45), row['after'])
                    self.assertIn((10, 93), row['after'])
                    for slot in range(19):
                        field = 32 + row['species_index'] * 0x124 + offset + slot * 4
                        allowed.update((field, field + 2, field + 3))
                        self.assertEqual(result[field + 1], original[field + 1])
                self.assertTrue(all(before == after or index in allowed
                                    for index, (before, after) in enumerate(zip(original, result))))
                repeated, again = apply_levelup_baseline(result, table, game=game, move_ids=ALLOCATED)
                self.assertEqual(repeated, result)
                self.assertEqual(again['changed_bytes'], 0)
                self.assertEqual(len(report['evolution_events']), 2)
                self.assertTrue(report['all_native_records_preserved'])

    def test_overflow_flags_foreign_terminators_and_missing_species_fail_without_writes(self):
        original, table = learning_fixture('xd')
        gardevoir = 32 + 282 * 0x124
        overflow = bytearray(original)
        for slot in range(19):
            field = gardevoir + 0xC4 + slot * 4
            overflow[field] = slot + 1
            struct.pack_into('>H', overflow, field + 2, slot + 1)
        before = bytes(overflow)
        with self.assertRaises(FairyLearnsetOverflow) as error:
            apply_levelup_baseline(bytes(overflow), table, game='xd', move_ids=ALLOCATED)
        self.assertGreater(len(error.exception.plan.learnset), 19)
        self.assertEqual(bytes(overflow), before)
        for field, value in ((gardevoir + 0xC5, b'\x01'),
                             (gardevoir + 0xC4 + 2 * 4 + 2, b'\x00\x5D'),
                             (32 + 386 * 0x124 + 0x0E, b'\x00\x00')):
            damaged = bytearray(original)
            damaged[field:field + len(value)] = value
            unchanged = bytes(damaged)
            with self.assertRaises(FormatError):
                apply_levelup_baseline(bytes(damaged), table, game='xd', move_ids=ALLOCATED)
            self.assertEqual(bytes(damaged), unchanged)

    def test_disabled_learning_option_does_not_validate_or_read_any_data(self):
        original = b'untouched native source'
        with patch('orre_randomizer.fairy_data._data', side_effect=AssertionError('must not read')):
            result, report = apply_levelup_baseline(original, {}, game='unknown', move_ids={}, enabled=False)
        self.assertIs(result, original)
        self.assertEqual(report['changed_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
