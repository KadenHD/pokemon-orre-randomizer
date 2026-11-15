"""Threshold order is numeric, stable and independent of display language."""
from dataclasses import replace
import unittest

from orre_randomizer.gift_presentation import order_purification_gifts
from orre_randomizer.options import Options
from orre_randomizer.preview import baseline_rows


class GiftPresentationTests(unittest.TestCase):
    def test_numeric_thresholds_zero_ties_and_other_gifts_stay_in_place(self):
        for celebi, pikachu, expected in ((25, 10, ['pikachu', 'celebi']),
                                         (5, 30, ['celebi', 'pikachu']),
                                         (10, 10, ['celebi', 'pikachu']),
                                         (10, 0, ['pikachu', 'celebi'])):
            rows = [dict(key='plusle'), dict(key='celebi', purifications=celebi),
                    dict(key='ho-oh'), dict(key='pikachu', purifications=pikachu)]
            original = rows[:]
            result = order_purification_gifts(rows)
            self.assertEqual([row['key'] for row in result], ['plusle', expected[0], 'ho-oh', expected[1]])
            self.assertEqual(rows, original)
            self.assertIs(result[0], rows[0])
            self.assertIs(result[2], rows[2])

    def test_baseline_gifts_follow_configured_counts_without_changing_native_event_order(self):
        for celebi, pikachu, expected in ((25, 10, ['pikachu-event', 'celebi-event']),
                                         (5, 30, ['celebi-event', 'pikachu-event']),
                                         (10, 10, ['celebi-event', 'pikachu-event']),
                                         (10, 0, ['pikachu-event', 'celebi-event'])):
            options = replace(Options.recommended(), event_celebi_purifications=celebi,
                              event_pikachu_purifications=pikachu)
            rows = baseline_rows(options)['gifts']
            self.assertEqual([row['key'] for row in rows], ['plusle', 'ho-oh', *expected])
            native = baseline_rows(replace(options, accessible_event_gifts=False))['gifts']
            self.assertEqual([row['key'] for row in native], ['plusle', 'ho-oh', 'celebi-event', 'pikachu-event'])
