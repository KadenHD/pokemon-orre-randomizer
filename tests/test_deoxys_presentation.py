from types import SimpleNamespace
import unittest

from orre_randomizer.deoxys import BASE_STATS, FORM_ORDER, form_label
from orre_randomizer.deoxys_presentation import annotate_catalog, decorate_encounter, encounter_key, form_stat_tables


class DeoxysPresentationTests(unittest.TestCase):
    def test_native_form_stats_and_names_cover_all_six_languages(self):
        stats = form_stat_tables('forms', SimpleNamespace(randomize_stats=False), BASE_STATS['normal'])
        self.assertEqual(stats, BASE_STATS)
        for language in ('fr', 'en', 'de', 'es', 'it', 'ja'):
            labels = [form_label(i, language) for i in range(4)]
            self.assertEqual(len(set(labels)), 4)
            self.assertTrue(all(labels))
        self.assertIn('Défense', form_label(2, 'fr'))
        self.assertIn('Velocità', form_label(3, 'it'))

    def test_stat_randomization_retains_hp_and_exact_total_for_free_form_changes(self):
        normal = (100, 160, 75, 80, 95, 90)
        options = SimpleNamespace(randomize_stats=True)
        first = form_stat_tables('forms', options, normal)
        self.assertEqual(first, form_stat_tables('forms', options, normal))
        self.assertNotEqual(first, form_stat_tables('other', options, normal))
        self.assertEqual(first['normal'], normal)
        for row in first.values():
            self.assertEqual(row[0], normal[0])
            self.assertEqual(sum(row), sum(normal))
            self.assertTrue(all(1 <= n <= 255 for n in row))

    def test_the_same_encounter_identity_selects_its_saved_plan_for_every_view(self):
        rows = [({'key': 'umbreon'}, 'special:umbreon'),
                ({'key': 'trainer:40'}, 'trainer:40'),
                ({'slot_index': 40, 'shadow_id': 3}, 'shadow:3'),
                ({'slot': 40}, 'trainer:40')]
        for row, key in rows:
            self.assertEqual(encounter_key(row), key)
        self.assertIsNone(encounter_key({}))

    def test_form_sheet_uses_rom_form_stats_without_mutating_other_fields(self):
        row = {'species': 410, 'national_dex': 386, 'shadow_id': 7, 'shiny': True,
               'details': {'base_stats': {}, 'moves': [1, 2], 'shadow': True, 'abilities': [46]}}
        metadata = {'encounters': {'shadow:7': 2}, 'base_stats': BASE_STATS}
        decorate_encounter(row, metadata, artwork=False)
        self.assertEqual(row['deoxys_form'], 2)
        self.assertEqual(row['details']['base_stats']['defense'], 160)
        self.assertEqual(row['details']['base_stat_total'], 600)
        self.assertEqual(row['details']['moves'], [1, 2])
        self.assertEqual(row['details']['abilities'], [46])
        self.assertTrue(row['shiny'] and row['details']['shadow'])

    def test_preserved_and_other_species_do_not_get_a_random_form(self):
        original = {'species': 410, 'key': 'plusle'}
        decorate_encounter(original, {}, artwork=False)
        self.assertEqual(original['deoxys_form'], 0)
        other = {'species': 1, 'national_dex': 1}
        decorate_encounter(other, {'encounters': {'special:plusle': 3}}, artwork=False)
        self.assertNotIn('deoxys_form', other)

    def test_known_normal_form_preserves_already_resolved_stats_without_a_full_plan(self):
        custom = {'hp': 99, 'attack': 101, 'defense': 103, 'sp_attack': 107,
                  'sp_defense': 109, 'speed': 113}
        row = {'species': 410, 'details': {'base_stats': custom.copy(), 'base_stat_total': sum(custom.values())}}
        decorate_encounter(row, {}, artwork=False)
        self.assertEqual(row['deoxys_form'], 0)
        self.assertEqual(row['details']['base_stats'], custom)
        self.assertEqual(row['details']['base_stat_total'], sum(custom.values()))

    def test_catalog_encounters_retain_their_distinct_forms(self):
        catalog = {'species': {'410': {'base_stats': dict()}},
                   'specials': {'umbreon': {'species': 410}},
                   'shadows': {'7': {'species': 410, 'variants': [{'species': 410}]}},
                   'trainers': [{'team': [{'species': 410, 'slot_index': 40}]}]}
        metadata = {'encounters': {'special:umbreon': 1, 'shadow:7': 2, 'trainer:40': 3},
                    'base_stats': BASE_STATS}
        annotate_catalog(catalog, metadata)
        self.assertEqual(catalog['specials']['umbreon']['deoxys_form'], 1)
        self.assertEqual(catalog['shadows']['7']['variants'][0]['deoxys_form'], 2)
        self.assertEqual(catalog['trainers'][0]['team'][0]['deoxys_form'], 3)
        self.assertEqual(catalog['species']['410']['base_stats'], {})
        catalog['deoxys_forms']['encounters']['shadow:7'] = 0
        self.assertEqual(metadata['encounters']['shadow:7'], 2)


if __name__ == '__main__':
    unittest.main()
