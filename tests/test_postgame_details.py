"""The bonus encounter is visible in the journal without changing native rows."""
import copy
import struct
import unittest

from orre_randomizer.detail_texts import LANGUAGES, detail_text
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.journal import render_journal
from orre_randomizer.pokemon_details import append_postgame_trainer_details
from tests.test_journal import report_fixture


def fixture():
    report = report_fixture()
    catalog = report['summary']['detail_catalog']
    catalog['species']['249'] = copy.deepcopy(catalog['species']['1'])
    catalog['species']['249']['names'] = {language: 'Lugia' for language in LANGUAGES}
    catalog['trainers'].append({'trainer_id': 437, 'class_id': 5,
        'names': {language: 'Jakylla' if language == 'fr' else 'Nascour' for language in LANGUAGES},
        'team': []})
    data = bytearray(0xD000)
    position = 0x100 + 820 * 0x34
    struct.pack_into('>H', data, position + 4, 1)
    struct.pack_into('>I', data, position + 8, 4167)
    data[position + 3] = 5
    for index in range(6):
        at = 0xC000 + (1 + index) * 0x50
        data[at + 3:at + 5] = bytes((96 if index == 5 else 0, 65 + index))
        struct.pack_into('>H', data, at + 0xA, 249 if index == 5 else 1)
        struct.pack_into('>H', data, at + 0x12, 99 + index)
        struct.pack_into('>H', data, at + 0x36, 2)
    event = {'enabled': True, 'trainer_id': 820, 'first_party_slot': 1,
        'battle_id': 566, 'species': 249, 'shadow_id': 96, 'opponent': {'name_id': 4167},
        'tables': {'trainers': {'offset': 0x100, 'stride': 0x34, 'count': 821},
                   'trainer_pokemon': {'offset': 0xC000, 'stride': 0x50, 'count': 7}}}
    report['summary']['postgame_shadow_lugia'] = event
    return report, bytes(data), event


class BonusDetailsTests(unittest.TestCase):
    def test_reads_final_team_and_exposes_battle_in_all_journal_languages(self):
        report, data, event = fixture()
        catalog = report['summary']['detail_catalog']
        native_trainers, native_shadows = copy.deepcopy((catalog['trainers'], catalog['shadows']))
        native_roster = copy.deepcopy(report['summary']['final_shadow_picks'])
        append_postgame_trainer_details(catalog, data, event)
        row = catalog['trainers'][-1]
        self.assertEqual(row['battle_ids'], [566])
        self.assertEqual([p['level'] for p in row['team']], list(range(65, 71)))
        self.assertEqual(row['team'][-1]['moves'], [2, 0, 0, 0])
        self.assertEqual(row['team'][-1]['held_item'], 104)
        self.assertEqual(catalog['shadows']['96']['trainer_ids'], [820])
        self.assertEqual(catalog['trainers'][:-1], native_trainers)
        self.assertEqual({k: v for k, v in catalog['shadows'].items() if k != '96'}, native_shadows)
        self.assertEqual(report['summary']['final_shadow_picks'], native_roster)
        for language in LANGUAGES:
            html = render_journal(report, language)
            self.assertIn(detail_text('battle_marker', language, id=566), html)
            self.assertIn('96 · Lugia', html)
        with self.assertRaises(FormatError):
            append_postgame_trainer_details(catalog, data, event)

    def test_disabled_bonus_keeps_catalog_unchanged_and_bad_team_is_rejected(self):
        report, data, event = fixture()
        catalog = report['summary']['detail_catalog']
        before = copy.deepcopy(catalog)
        append_postgame_trainer_details(catalog, b'', {'enabled': False})
        self.assertEqual(catalog, before)
        corrupted = bytearray(data)
        corrupted[0xC000 + 6*0x50 + 3] = 0
        with self.assertRaises(FormatError):
            append_postgame_trainer_details(catalog, bytes(corrupted), event)
        self.assertEqual(catalog, before)


if __name__ == '__main__':
    unittest.main()
