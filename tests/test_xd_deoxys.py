"""XD form plans share identities across rewards, shadows and localized decks."""
from copy import deepcopy
import unittest

from orre_randomizer.xd_deoxys import reward_tokens, merge_shadows, encounter_metadata, annotate_summary, token
from orre_randomizer.engine.analyze_game import FormatError


class XDDeoxysPlans(unittest.TestCase):
    def test_only_final_deoxys_encounters_get_forms_and_native_deoxys_stays_normal(self):
        summary = {'starter': {'original': 133, 'species': 410},
            'gifts': [{'key': 'one', 'original': 25, 'species': 410},
                      {'key': 'two', 'original': 410, 'species': 410},
                      {'key': 'three', 'original': 410, 'species': 25}],
            'poke_spots': [{'spot': 'cave', 'slot': 3, 'original': 194, 'species': 410}]}
        before = deepcopy(summary)
        rewards, spots = reward_tokens(summary, 'été 日本')
        self.assertEqual(set(rewards), {'starter', 'one', 'two'})
        self.assertEqual(set(spots), {('cave', 3)})
        self.assertEqual(rewards['two'] >> 30, 0)
        self.assertEqual(summary, before)
        self.assertEqual((rewards, spots), reward_tokens(summary, 'été 日本'))
        self.assertNotEqual(rewards['starter'], reward_tokens(summary, 'another seed')[0]['starter'])

    def test_encounter_domains_cover_all_four_forms_without_affecting_pid_bits(self):
        values = [token('forms', f'shadow:{index}', 25) for index in range(96)]
        self.assertEqual({value >> 30 for value in values}, set(range(4)))
        self.assertTrue(all(0 < value <= 0xFFFFFFFF for value in values))
        self.assertNotEqual(token('forms', 'starter', 133), token('forms', 'shadow:1', 25))

    def test_conflicting_localized_shadow_choices_are_rejected(self):
        choices = {3: 100}
        merge_shadows(choices, {3: 100, 4: 200})
        self.assertEqual(choices, {3: 100, 4: 200})
        with self.assertRaises(FormatError):
            merge_shadows(choices, {3: 300})

    def test_preview_and_journal_metadata_keep_distinct_forms_per_encounter(self):
        metadata = encounter_metadata({'starter': 0x40000001}, {3: 0x80000001},
            {0x1234: {5: 0xC0000001}}, {('cave', 3): 1})
        self.assertEqual(metadata, {'special:starter': 1, 'shadow:3': 2,
            'trainer:4660:5': 3, 'pokespot:cave:3': 0})
        summary = {'deoxys_forms': {'enabled': True, 'encounters': metadata},
            'starter': {'species': 410}, 'decks': {'Story': {'shadows': [{'species': 410, 'shadow_id': 3}]}},
            'poke_spots': [{'species': 410, 'spot': 'cave', 'slot': 3}]}
        annotate_summary(summary)
        self.assertEqual(summary['starter']['deoxys_form'], 1)
        self.assertEqual(summary['decks']['Story']['shadows'][0]['deoxys_form'], 2)
        self.assertEqual(summary['poke_spots'][0]['deoxys_form'], 0)


if __name__ == '__main__':
    unittest.main()
