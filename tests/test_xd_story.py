from types import SimpleNamespace
import unittest

from colosseum_randomizer.xd_story import hordel_candidates, tutorial_candidates


class XDHordelTests(unittest.TestCase):
    def test_requires_a_base_form_with_one_accessible_evolution(self):
        families = {1: 1, 2: 1, 3: 1, 23: 23, 24: 23, 95: 95, 208: 95, 133: 133, 134: 133, 135: 133}
        edges = {1: [(0, 4, 16, 2)], 2: [(0, 4, 32, 3)], 23: [(0, 4, 22, 24)],
                 95: [(0, 6, 0, 208)], 133: [(0, 7, 1, 134), (0, 7, 2, 135)]}
        self.assertEqual(hordel_candidates(families, edges, families, accessible_evolutions=False), {23: 24})
        self.assertEqual(hordel_candidates(families, edges, families, accessible_evolutions=True), {23: 24, 95: 208})


class XDTutorialTests(unittest.TestCase):
    def test_only_compatible_tutorial_opponents_are_eligible(self):
        rows = {
            1: {"national_dex": 1, "types": (12, 3), "abilities": (65,), "total": 318},
            92: {"national_dex": 92, "types": (7, 3), "abilities": (26,), "total": 310},
            216: {"national_dex": 216, "types": (0,), "abilities": (53,), "total": 330},
            292: {"national_dex": 292, "types": (6, 7), "abilities": (25,), "total": 236},
        }
        regular = {"index": 33, "power": 35, "type": 0}
        explosion = {"index": 153, "power": 250, "type": 0}
        rules = SimpleNamespace(species=rows, catalog={33: regular, 153: explosion})
        self.assertEqual(tutorial_candidates({"moves": [33]}, rows, rules), [1])
        self.assertEqual(tutorial_candidates({"moves": [153]}, rows, rules), [])
