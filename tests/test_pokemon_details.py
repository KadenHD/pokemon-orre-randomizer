"""Detail sheets must describe final bytes, independently of seed/options."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest

from colosseum_randomizer.detail_texts import LANGUAGES, TEXTS
from colosseum_randomizer.locales.detail_names import ABILITY_NAMES, EVOLUTION_ITEM_NAMES, MOVE_NAMES
from colosseum_randomizer.pokemon_details import (build_detail_catalog, encounter_details,
    evolution_text, format_detail_lines)
from colosseum_randomizer.engine.analyze_game import FormatError


def fixture():
    rel = bytearray(0x1100)
    tables = {'species': {'offset': 0x400, 'count': 4, 'stride': 0x11C},
              'moves': {'offset': 0x100, 'count': 3, 'stride': 0x38},
              'trainers': {'offset': 0xA00, 'count': 2, 'stride': 0x34},
              'trainer_pokemon': {'offset': 0xC00, 'count': 8, 'stride': 0x50},
              'shadow': {'offset': 0xF00, 'count': 2, 'stride': 0x38}}
    for index, dex in ((1, 95), (2, 208), (3, 133)):
        offset = 0x400 + index * 0x11C
        struct.pack_into('>H', rel, offset + 0x10, dex)
        struct.pack_into('>I', rel, offset + 0x18, 100 + index)
        rel[offset + 0x30:offset + 0x34] = bytes((5, 4, 69, 5))
        for field in (0x85, 0x87, 0x89, 0x8B, 0x8D, 0x8F):
            rel[offset + field] = 50
        rel[offset + 0x34] = 1
        for slot, move in enumerate((1, 2)):
            rel[offset + 0xBA + slot * 4] = 5 + slot * 5
            struct.pack_into('>H', rel, offset + 0xBC + slot * 4, move)
    species1 = 0x400 + 0x11C
    rel[species1 + 0x9C] = 6
    struct.pack_into('>HH', rel, species1 + 0x9E, 199, 2)
    for index in (1, 2):
        at = 0x100 + index * 0x38
        rel[at + 1:at + 3] = bytes((30, 10 + index))
        rel[at + 4], rel[at + 0x17] = 100, 40 + index
        struct.pack_into('>I', rel, at + 0x20, 200 + index)
    struct.pack_into('>H', rel, 0xA00 + 0x34 + 4, 1)
    struct.pack_into('>I', rel, 0xA00 + 0x34 + 8, 500)
    for slot, index, level, sid in ((1, 1, 30, 1), (2, 2, 40, 0)):
        at = 0xC00 + slot * 0x50
        rel[at + 3:at + 5] = bytes((sid, level))
        struct.pack_into('>H', rel, at + 0xA, index)
        for field, move in zip((0x36, 0x3E, 0x46, 0x4E), (1, 2, 0xFFFF, 0)):
            struct.pack_into('>H', rel, at + field, move)
    struct.pack_into('>HH', rel, 0xF00 + 0x38 + 2, 1, 1)
    dol = bytearray(0x4000)
    region = SimpleNamespace(item_table_offset=0x1000, tm_table_offset=0x200, game_id='fixture')
    for index in EVOLUTION_ITEM_NAMES['en']:
        struct.pack_into('>I', dol, 0x1000 + index * 0x28 + 0x10, 300 + index)
    for number in range(50):
        struct.pack_into('>H', dol, 0x200 + number * 8 + 6, 1 if number % 2 else 2)
    names = {'FR': {101: 'ONIX NATIF', 102: 'STEELIX NATIF', 201: 'CAPACITÉ NATIVE', 500: 'DRESSEUR NATIF',
                    300 + 199: 'PEAU MÉTAL NATIVE'}}
    final = bytearray(rel)
    final[species1 + 0x30:species1 + 0x34] = bytes((10, 11, 25, 25))
    final[species1 + 0x85] = 90
    final[species1 + 0x9C] = 4
    struct.pack_into('>H', final, species1 + 0x9E, 40)
    final[0xC00 + 0x50 + 4] = 31
    return bytes(rel), bytes(final), bytes(dol), tables, names, region


def catalog_fixture():
    original, final, dol, tables, names, region = fixture()
    return build_detail_catalog(original, final, dol, dol, tables=tables, symbols=[], names=names, dol_info=region)


class DetailTests(unittest.TestCase):
    def test_final_types_stats_abilities_evolution_and_moves_are_read(self):
        original, final, dol, tables, names, region = fixture()
        catalog = build_detail_catalog(original, final, dol, dol, tables=tables, symbols=[], names=names, dol_info=region)
        sheet = encounter_details(catalog, 1, level=31, moves=[1, 2, 0xFFFF, 0], shadow=True)
        self.assertEqual(sheet['types'], [10, 11])
        self.assertEqual(sheet['type_names']['fr'], ['Feu', 'Eau'])
        self.assertEqual(sheet['abilities'], [25])
        self.assertEqual(sheet['ability_names']['fr'], ['Garde Mystik'])
        self.assertEqual(sheet['base_stats']['hp'], 90)
        self.assertEqual(sheet['evolutions'][0]['method'], 4)
        self.assertEqual(sheet['evolutions'][0]['condition'], 40)
        self.assertIn('40', sheet['evolutions'][0]['texts']['fr'])
        self.assertNotIn('Échanger', sheet['evolutions'][0]['texts']['fr'])
        self.assertEqual(sheet['moves'][0]['names']['fr'], 'CAPACITÉ NATIVE')
        self.assertTrue(sheet['moves'][2]['special_marker'])
        self.assertEqual([r['tm'] for r in sheet['tms']], [1])
        self.assertEqual(sheet['tms'][0]['details']['move'], 2)
        self.assertEqual(catalog['shadows']['1']['level'], 31)
        self.assertIn('Purifiez', '\n'.join(format_detail_lines(sheet, 'fr')))
        self.assertEqual(original[0x400 + 0x11C + 0x9C], 6)
        self.assertEqual(final[0x400 + 0x11C + 0x9C], 4)
        json.dumps(catalog, ensure_ascii=False, allow_nan=False)

    def test_six_languages_and_native_name_precedence(self):
        catalog = catalog_fixture()
        row = catalog['species']['1']
        self.assertEqual(row['names']['fr'], 'ONIX NATIF')
        self.assertEqual(row['names']['en'], 'Onix')
        self.assertEqual(row['names']['ja'], 'イワーク')
        self.assertEqual(set(row['evolutions'][0]['texts']), set(LANGUAGES))
        self.assertEqual(set(TEXTS['fr']), set(TEXTS['ja']))
        for language in LANGUAGES:
            self.assertEqual(len(MOVE_NAMES[language]), 354)
            self.assertEqual(len(ABILITY_NAMES[language]), 77)
            self.assertEqual(len(EVOLUTION_ITEM_NAMES[language]), 12)
            self.assertTrue(format_detail_lines(encounter_details(catalog, 1), language))

    def test_sheet_changes_do_not_mutate_shared_snapshot(self):
        catalog = catalog_fixture()
        before = copy.deepcopy(catalog)
        sheet = encounter_details(catalog, 1, moves=[1])
        sheet['base_stats']['hp'] = 1
        sheet['evolutions'][0]['texts']['fr'] = 'changed'
        sheet['moves'][0]['names']['fr'] = 'changed'
        self.assertEqual(catalog, before)

    def test_unadapted_conditions_are_explicit_and_stone_names_translated(self):
        self.assertIn('adaptation', evolution_text(5, 0, language='fr'))
        self.assertIn('Water Stone', evolution_text(7, 97, language='en'))
        self.assertIn('Pierre Eau', evolution_text(7, 97, language='fr'))
        self.assertIn('みずのいし', evolution_text(7, 97, language='ja'))
        self.assertIn('Attaque > Défense', evolution_text(8, 20, language='fr'))
        with self.assertRaises(FormatError):
            evolution_text(99, 1)

    def test_final_identity_or_pointer_corruption_is_refused(self):
        original, final, dol, tables, names, region = fixture()
        bad = bytearray(final)
        struct.pack_into('>H', bad, 0x400 + 0x11C + 0x10, 94)
        with self.assertRaises(FormatError):
            build_detail_catalog(original, bytes(bad), dol, dol, tables=tables, symbols=[], names=names, dol_info=region)
        bad = bytearray(final)
        struct.pack_into('>H', bad, 0x400 + 0x11C + 0xA0, 399)
        with self.assertRaises(FormatError):
            build_detail_catalog(original, bytes(bad), dol, dol, tables=tables, symbols=[], names=names, dol_info=region)


@unittest.skipUnless((Path(__file__).resolve().parents[1] / 'game/files/common.fsys').is_file(),
                     "requires the user's original local PAL image")
class RealDetailTests(unittest.TestCase):
    def test_actual_adapted_onix_and_eevee_stones_use_final_methods(self):
        from colosseum_randomizer.engine.randomize_trainers import original_common
        from colosseum_randomizer.engine.evolution_rules import patch_evolutions
        root = Path(__file__).resolve().parents[1]
        original = original_common(root / 'game')[2]
        tables, _ = __import__('colosseum_randomizer.engine.randomize_trainers', fromlist=['layout']).layout(original)
        final, _ = patch_evolutions(original, tables)
        dol = (root / 'game/sys/main.dol').read_bytes()
        catalog = build_detail_catalog(original, final, dol, dol)
        self.assertEqual(len(catalog['species']), 386)
        self.assertEqual(len(catalog['trainers']), 817)
        self.assertEqual(len(catalog['shadows']), 48)
        onix = encounter_details(catalog, 95, shadow=True)
        self.assertEqual((onix['evolutions'][0]['method'], onix['evolutions'][0]['condition']), (4, 40))
        eevee = encounter_details(catalog, 133)
        branches = {r['target_national_dex']: r for r in eevee['evolutions']}
        self.assertEqual((branches[196]['method'], branches[196]['condition']), (7, 93))
        self.assertEqual((branches[197]['method'], branches[197]['condition']), (7, 94))
        self.assertIn('PIERRESOLEIL', branches[196]['texts']['fr'])
        self.assertIn('SUN STONE', branches[196]['texts']['en'])
        gastly = encounter_details(catalog, 92)
        self.assertEqual([(r['source_species'], r['target_species'], r['condition'])
                          for r in gastly['evolution_chain']], [(92, 93, 25), (93, 94, 40)])


if __name__ == '__main__':
    unittest.main()
