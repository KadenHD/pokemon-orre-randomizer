"""The story allocator can move an earlier choice to avoid a family collision."""
import unittest

from colosseum_randomizer.engine.story_families import allocate_story_families, select_story_starters


class StoryFamilyAllocationTests(unittest.TestCase):
    def test_gift_can_keep_its_only_family_by_moving_a_shadow(self):
        edges = {"shadow:1": [1, 2], "shadow:2": [2, 3], "plusle": [1]}
        self.assertEqual(allocate_story_families(edges, set()), {"plusle": 1, "shadow:1": 2, "shadow:2": 3})

    def test_alternate_valid_starter_pair_reserves_the_only_gift_family(self):
        families = {1: 1, 2: 2, 3: 3, 4: 4}
        edges = {"plusle": [1], "shadow:1": [1, 4]}
        self.assertEqual(select_story_starters((1, 2), {1: [2], 3: [2]}, families, edges, set()), (3, 2))

    def test_impossible_full_allocation_still_prefers_distinct_starters(self):
        families = {1: 1, 2: 1, 3: 2}
        edges = {"plusle": [1], "shadow:1": [1]}
        self.assertEqual(select_story_starters((1, 2), {1: [2, 3]}, families, edges, set()), (1, 3))
