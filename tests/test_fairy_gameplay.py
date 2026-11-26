"""Fairy generation views must share one baseline without leaking across jobs."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import hashlib
import struct
import threading
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.gameplay_rules import (
    _has_special_moves, apply_species_gameplay, choose_moves, move_catalog, physical,
)
from orre_randomizer.engine.gift_move_hooks import patch_gift_moves, _gift_stub, SECTION_RAM, NATIVE_SET_MOVE
from orre_randomizer.engine.species_rules import READABLE_TYPES, VALID_TYPES, species_catalog
from orre_randomizer.fairy_data import (
    FAIRY_SPECIES, NEW_MOVE_IDS, move_definition, native_type, reference_manifest,
)
from orre_randomizer.fairy_gameplay import (
    NATIVE_MOVE_MAP, catalog_from_rows, content_from_rows, current_context,
    fairy_gameplay_context,
)
from orre_randomizer.options import Options
from orre_randomizer.pokemon_details import (
    append_fairy_details, build_detail_catalog, encounter_details,
)
from orre_randomizer.xd_species_gameplay import (
    XDMoveRandomizer, patch_species_gameplay,
)


def move_rows(game_id):
    """Synthetic native rows for pure plumbing, not effect qualification."""
    power, effect = (0x17, 0x1A) if game_id.startswith('GC6') else (0x19, 0x1C)
    result = {}
    for ordinal, (canonical, native) in enumerate(NATIVE_MOVE_MAP.items()):
        meta = move_definition(canonical)
        row = bytearray(0x38)
        row[1], row[2], row[4], row[power] = meta['pp'], 19, meta['accuracy'] or 0, meta['power'] or 0
        struct.pack_into('>H', row, effect, 100 + ordinal)
        struct.pack_into('>I', row, 0x20, 0xF0400 + ordinal)
        result[native] = bytes(row)
    return result


def fixture(game_id):
    xd = game_id.startswith('GXX')
    stride, count = (0x124, 415) if xd else (0x11C, 413)
    species_start, move_start = 0x100, 0x20000
    move_count = 375 if xd else 358
    rel = bytearray(move_start + move_count * 0x38)
    tables = {'species': {'offset': species_start, 'count': count, 'stride': stride},
              'moves': {'offset': move_start, 'count': move_count, 'stride': 0x38}}
    reference = reference_manifest()
    species, families = {}, {}
    for national in range(1, 387):
        index = {282: 394, 386: 410}.get(national, national)
        pos = species_start + index * stride
        struct.pack_into('>H', rel, pos + (0x0E if xd else 0x10), national)
        values = reference['species'].get(str(national), {}).get('native_generation_three_types', [1])
        types = tuple(native_type(value, fairy_type_id=19) for value in values)
        if len(types) == 1:
            types *= 2
        rel[pos + 0x30:pos + 0x34] = bytes((*types, 1, 0))
        for field in ((0x8E, 0x90, 0x92, 0x94, 0x96, 0x98) if xd else (0x85, 0x87, 0x89, 0x8B, 0x8D, 0x8F)):
            if xd:
                struct.pack_into('>H', rel, pos + field, 50)
            else:
                rel[pos + field] = 50
        learning = 0xC4 if xd else 0xBA
        for slot, (level, move) in enumerate(((1, 1), (5, 2))):
            struct.pack_into('>BxH', rel, pos + learning + slot * 4, level, move)
        species[index], families[index] = (national,), index
    for index in range(1, 355):
        pos = move_start + index * 0x38
        rel[pos + 1], rel[pos + 2], rel[pos + 4] = 10, 0, 100
        rel[pos + (0x19 if xd else 0x17)] = 50
        struct.pack_into('>I', rel, pos + 0x20, 2000 + index)
    symbols = [{} for _ in range(126)]
    for symbol, table, counter in ((88, tables['species'], 0), (124, tables['moves'], 4)):
        symbols[symbol] = {'offset': table['offset']}
        symbols[symbol + 1] = {'offset': counter}
        struct.pack_into('>I', rel, counter, table['count'])
    original = bytes(rel)
    content = content_from_rows(game_id, move_rows(game_id), original_rel=original,
                                original_dol=b'authenticated original DOL fixture', tables=tables)
    return original, tables, symbols, species, families, content


class ScopedContent(unittest.TestCase):
    def test_nested_contexts_restore_on_success_and_exception_and_keep_content_immutable(self):
        *_, colo = fixture('GC6P01')
        *_, xd = fixture('GXXP01')
        self.assertIsNone(current_context())
        with fairy_gameplay_context(colo):
            self.assertIs(current_context('colosseum'), colo)
            with self.assertRaises(RuntimeError):
                with fairy_gameplay_context(xd):
                    self.assertIs(current_context('xd'), xd)
                    raise RuntimeError('cancel this generation')
            self.assertIs(current_context(), colo)
            with fairy_gameplay_context(None):
                self.assertIsNone(current_context())
            with self.assertRaises(FormatError):
                current_context('xd')
        self.assertIsNone(current_context())
        with self.assertRaises(FrozenInstanceError):
            colo.game_id = 'GXXP01'
        metadata = colo.summary()
        metadata['type_baseline']['species_edits'].clear()
        self.assertEqual(len(colo.summary()['type_baseline']['species_edits']), 18)
        exported = colo.moves
        exported[375]['names'].clear()
        self.assertTrue(colo.moves[375]['names']['fr'])

    def test_concurrent_game_jobs_cannot_observe_or_leave_each_others_context(self):
        *_, colo = fixture('GC6P01')
        *_, xd = fixture('GXXP01')
        barrier = threading.Barrier(2)
        def run(content):
            self.assertIsNone(current_context())
            with fairy_gameplay_context(content):
                barrier.wait(timeout=10)
                observed = current_context().game_id
                barrier.wait(timeout=10)
            self.assertIsNone(current_context())
            return observed
        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = executor.submit(run, colo), executor.submit(run, xd)
            self.assertEqual((first.result(timeout=15), second.result(timeout=15)), ('GC6P01', 'GXXP01'))
        self.assertIsNone(current_context())

    def test_baseline_overlay_preserves_prior_encounter_edits_and_rejects_late_trait_overwrites(self):
        original, tables, *_unused, content = fixture('GC6P01')
        current = bytearray(original)
        current[0x80] = 99
        applied = content.apply_baseline(bytes(current))
        self.assertEqual(applied[0x80], 99)
        self.assertEqual(content.apply_baseline(applied), applied)
        trait = bytearray(applied)
        pos = tables['species']['offset'] + 35 * tables['species']['stride'] + 0x30
        trait[pos] = 10
        with self.assertRaises(FormatError):
            content.apply_baseline(bytes(trait))

    def test_prepared_rows_decode_native_effects_instead_of_canonical_numbers(self):
        for game in ('GC6P01', 'GXXP01'):
            rows = move_rows(game)
            catalog = catalog_from_rows(game, rows)
            self.assertEqual(catalog[377]['effect'], 102)
            self.assertEqual(catalog[377]['canonical_effect_id'], 69)
            self.assertEqual(catalog[377]['power'], 90)
            damaged = dict(rows)
            wrong = bytearray(damaged[377])
            wrong[2] = 0
            damaged[377] = bytes(wrong)
            with self.assertRaises(ValueError):
                catalog_from_rows(game, damaged)


class GameplayReference(unittest.TestCase):
    def test_native_shadow_markers_stay_protected_but_prepared_new_moves_are_ordinary(self):
        original, tables, *_unused, content = fixture('GC6P01')
        legacy = move_catalog(original, tables)
        self.assertTrue(_has_special_moves((1, 375, 381, 0), legacy))
        with fairy_gameplay_context(content):
            modern = move_catalog(original, tables)
            self.assertFalse(_has_special_moves((1, 375, 381, 0), modern))
            for marker in (355, 357, 358, 374, 382, 0xFFFF):
                self.assertTrue(_has_special_moves((1, marker, 0, 0), modern))
        self.assertFalse(_has_special_moves((1, 165, 354, 0), legacy))

    def test_gift_hooks_accept_only_prepared_extra_ids_and_forward_each_move_unchanged(self):
        from tests.test_gift_move_hooks import PPCMachine
        *_, content = fixture('GC6P01')
        sentinel = RuntimeError('reached independent retail authentication')
        with patch('orre_randomizer.engine.gift_move_hooks._validate_original', side_effect=sentinel):
            for move in range(375, 382):
                with self.assertRaises(FormatError):
                    patch_gift_moves(b'original', b'current', {'plusle': [1, move, 0, 0]})
            with fairy_gameplay_context(content):
                for move in range(375, 382):
                    with self.assertRaisesRegex(RuntimeError, 'retail authentication'):
                        patch_gift_moves(b'original', b'current', {'plusle': [1, move, 0, 0]})
                for move in (165, 355, 357, 358, 374, 382, 0xFFFF, True):
                    with self.assertRaises(FormatError):
                        patch_gift_moves(b'original', b'current', {'plusle': [1, move, 0, 0]})
        moves = [375, 377, 381, 0]
        machine = PPCMachine(_gift_stub(SECTION_RAM + 32, moves), SECTION_RAM + 32)
        machine.registers[3:7] = [0x80507700, 123, 70, 1]
        machine.execute()
        self.assertEqual([(target, args[1:3]) for target, args in machine.calls[1:]],
                         [(NATIVE_SET_MOVE, [slot, move]) for slot, move in enumerate(moves)])

    def test_original_and_final_readers_use_one_baseline_without_resetting_random_types(self):
        original, tables, *_unused, content = fixture('GC6P01')
        digest = hashlib.sha256(original).hexdigest()
        native = species_catalog(original, tables)
        self.assertEqual(native[394]['types'], (14, 14))
        with fairy_gameplay_context(content):
            projected = species_catalog(original, tables)
            self.assertEqual(projected[394]['types'], (14, 19))
            self.assertIn((12, 376), projected[394]['learnset'])
            moves = move_catalog(original, tables)
            self.assertEqual(moves[186]['type'], 19)
            self.assertEqual(set(range(375, 382)) - set(moves), set())
            final = bytearray(content.baseline_rel)
            pos = tables['species']['offset'] + 394 * tables['species']['stride']
            final[pos + 0x30:pos + 0x32] = bytes((10, 11))
            self.assertEqual(species_catalog(bytes(final), tables)[394]['types'], (10, 11))
        self.assertEqual(move_catalog(original, tables)[186]['type'], 0)
        self.assertFalse(set(range(375, 382)) & set(move_catalog(original, tables)))
        self.assertEqual(hashlib.sha256(original).hexdigest(), digest)

    def test_preserved_species_receive_only_the_deterministic_baseline(self):
        original, tables, *_unused, content = fixture('GC6P01')
        options = replace(Options.none(), enable_fairy_type=True)
        plain, _ = apply_species_gameplay(original, original, 'seed', Options.none(), tables)
        self.assertEqual(plain, original)
        with fairy_gameplay_context(content):
            final, report = apply_species_gameplay(original, original, 'seed', options, tables)
        self.assertEqual(final, content.baseline_rel)
        self.assertIn('fairy_baseline', report)
        self.assertNotIn(19, VALID_TYPES)
        self.assertIn(19, READABLE_TYPES)

    def test_xd_natural_moves_and_conditional_type_pool_follow_the_same_current_baseline(self):
        original, tables, symbols, species, families, content = fixture('GXXP01')
        options = replace(Options.none(), enable_fairy_type=True)
        with fairy_gameplay_context(content):
            randomizer = XDMoveRandomizer(original, symbols, species, options)
            self.assertEqual(randomizer.species[394]['types'], (14, 19))
            natural = randomizer.moves('seed', 'starter', 394, 12, [0, 0, 0, 0], mode='natural')
            self.assertIn(376, natural)
            baseline, _ = patch_species_gameplay(original, symbols, 'seed', species, families, options,
                                                 preserve_species=set(species))
            self.assertEqual(baseline, content.baseline_rel)
            choices = []
            def select(_seed, _key, pool):
                choices.append(set(pool))
                return max(pool)
            with patch('orre_randomizer.xd_species_gameplay._draw', side_effect=select):
                modified, _ = patch_species_gameplay(original, symbols, 'seed', species, families,
                    replace(options, randomize_types=True), selected_species={394})
            self.assertTrue(any(19 in pool for pool in choices))
            pos = tables['species']['offset'] + 394 * tables['species']['stride']
            self.assertEqual(modified[pos + 0x30], 19)
        choices = []
        with patch('orre_randomizer.xd_species_gameplay._draw', side_effect=select):
            patch_species_gameplay(original, symbols, 'seed', species, families,
                replace(Options.none(), randomize_types=True), selected_species={394})
        self.assertTrue(choices)
        self.assertFalse(any(19 in pool for pool in choices))

    def test_fairy_stab_and_physical_category_are_not_derived_from_its_high_type_number(self):
        original, tables, *_unused, content = fixture('GC6P01')
        options = replace(Options.none(), ensure_damaging_move=True, ensure_stab_move=True,
                          moves_mode='chaos', no_duplicate_moves=True)
        with fairy_gameplay_context(content):
            moves = move_catalog(original, tables)
            species = species_catalog(original, tables)[35]
            selected = choose_moves('stab', 'moves', species, 40, moves, options)
            self.assertEqual(moves[selected[0]]['type'], 19)
            self.assertGreater(moves[selected[0]]['power'], 1)
            self.assertTrue(physical(moves[377]))
            self.assertFalse(physical(moves[379]))
        self.assertTrue(physical({'type': 7}))
        self.assertFalse(physical({'type': 14}))


class FinalFairyDetails(unittest.TestCase):
    def test_final_details_use_verified_dol_rows_and_the_actual_57_tm_permutation(self):
        from tests.test_pokemon_details import fixture as detail_fixture
        original, final, dol, tables, names, region = detail_fixture()
        region.game_id = 'GC6P01'
        final = bytearray(final)
        first = tables['species']['offset'] + tables['species']['stride']
        struct.pack_into('>H', final, first + 0xBC, 375)
        final[first + 0x30] = 19
        current_dol = bytearray(dol)
        struct.pack_into('>H', current_dol, region.tm_table_offset + 6, 375)
        native_tms = [{'tm': i + 1, 'move': struct.unpack_from('>H', current_dol, region.tm_table_offset + i * 8 + 6)[0]}
                      for i in range(50)]
        tms = native_tms + [{'tm': 51 + i, 'move': 1 if i == 0 else 375 + i} for i in range(7)]
        installed = {'moves': move_rows('GC6P01'), 'tms': tms,
                     'compatibility': {national: (True, False, True, False, True, False, True)
                                       for national in (95, 208, 133)}}
        with patch('orre_randomizer.fairy_tms.read_installed_content', return_value=installed) as reader:
            catalog = build_detail_catalog(original, bytes(final), dol, bytes(current_dol),
                tables=tables, symbols=[], names=names, dol_info=region, fairy_report={'game_id': 'GC6P01'})
        reader.assert_called_once_with(bytes(current_dol), {'game_id': 'GC6P01'})
        self.assertEqual(len(catalog['tms']), 57)
        self.assertEqual(catalog['tms'][0]['move'], 375)
        self.assertEqual(catalog['tms'][50]['move'], 1)
        self.assertEqual(catalog['moves']['375']['names']['fr'], 'Voix enjôleuse')
        self.assertEqual(catalog['moves']['380']['names']['fr'], 'Éclat magique')
        self.assertEqual(catalog['species']['1']['type_names']['fr'][0], 'Fée')
        self.assertIn(51, catalog['species']['1']['compatible_tms'])
        self.assertNotIn(52, catalog['species']['1']['compatible_tms'])
        self.assertTrue(catalog['moves']['377']['native_row_verified'])
        # A prepared/installed Fairy ID must not degrade to an unrelated marker.
        with self.assertRaises(FormatError):
            encounter_details({**catalog, 'moves': {}}, 1, moves=[375])

    def test_missing_installation_proof_cannot_publish_new_learning_or_tm_details(self):
        from tests.test_pokemon_details import fixture as detail_fixture
        original, final, dol, tables, names, region = detail_fixture()
        changed = bytearray(final)
        first = tables['species']['offset'] + tables['species']['stride']
        struct.pack_into('>H', changed, first + 0xBC, 375)
        with self.assertRaisesRegex(FormatError, 'level-up move'):
            build_detail_catalog(original, bytes(changed), dol, dol,
                                 tables=tables, symbols=[], names=names, dol_info=region)
        with self.assertRaisesRegex(FormatError, 'different games'):
            append_fairy_details({}, {}, [], dol, {'game_id': 'GXXP01'}, 'GC6P01')


if __name__ == '__main__':
    unittest.main()
