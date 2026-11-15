"""Original-ROM projection never invokes the full randomizer or species draws."""
from pathlib import Path
from unittest.mock import patch
import unittest

from orre_randomizer.preview import preview_known, preview_xd_known
from orre_randomizer.presets import recommended_preset
from orre_randomizer.xd import XDOptions


ROOT = Path(__file__).resolve().parents[1]
COLOSSEUM = ROOT / 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso'
XD = ROOT / 'build/xd-validation/verified-eu.iso'


class KnownEncounterProjectionTests(unittest.TestCase):
    @unittest.skipUnless(COLOSSEUM.is_file(), 'requires an original local Colosseum ROM')
    def test_colosseum_projects_fixed_legends_and_bonus_team_without_full_build(self):
        with patch('orre_randomizer.service.build_patches', side_effect=AssertionError('full plan')), \
             patch('orre_randomizer.engine.gameplay_rules.apply_dol_rules', side_effect=AssertionError('species draw')):
            result = preview_known(COLOSSEUM, 'fixed-projection', recommended_preset(),
                                   on_prepared=lambda _: self.fail('partial data is not a ROM patch plan'))
        self.assertFalse(result['starters'])
        self.assertFalse(result['gifts'])
        self.assertEqual({r['shadow_id'] for r in result['shadows']}, {21, 23, 34})
        team = result['postgame_shadow_lugia']['team']
        self.assertEqual([r['level'] for r in team], list(range(65, 71)))
        self.assertTrue(all(r['details']['moves_known'] for r in result['shadows'] + team))
        self.assertTrue(all('shiny' in r for r in result['shadows'] + team))

    @unittest.skipUnless(XD.is_file(), 'requires an original local XD ROM')
    def test_xd_projects_only_native_legends_without_full_build_or_species_pick(self):
        with patch('orre_randomizer.service.build_xd_patches', side_effect=AssertionError('full plan')), \
             patch('orre_randomizer.xd._pick', side_effect=AssertionError('species draw')), \
             patch('orre_randomizer.xd._deck', side_effect=AssertionError('whole deck')):
            result = preview_xd_known(XD, 'fixed-projection', XDOptions.recommended(),
                                     on_prepared=lambda _: self.fail('partial data is not a ROM patch plan'))
        self.assertIsNone(result['starter'])
        self.assertFalse(result['gifts'])
        self.assertFalse(result['poke_spots'])
        shadows = result['decks']['Story']['shadows']
        self.assertEqual({r['shadow_id'] for r in shadows}, {73, 74, 75, 76})
        self.assertTrue(all(r['details']['moves_known'] and 'shiny' in r for r in shadows))


if __name__ == '__main__':
    unittest.main()
