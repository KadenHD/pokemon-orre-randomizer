from dataclasses import replace
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import patch

from orre_randomizer.fairy_content import prepare_content, scoped_content, install_content
from orre_randomizer.fairy_gameplay import current_context, fairy_gameplay_context, _layouts
from orre_randomizer.fairy_integration import apply_tm_gameplay
from orre_randomizer.fairy_tms import read_installed_content
from orre_randomizer.options import Options
from tests.test_fairy_tms import PATHS, ROOT


class FairyContentTests(unittest.TestCase):
    def test_disabled_worker_does_no_preparation_or_disc_read(self):
        seen = []
        @scoped_content
        def worker(iso, boot, seed, options, progress, cancel):
            seen.append(current_context())
            return 'unchanged'
        with patch('orre_randomizer.known_encounters._read', side_effect=AssertionError('Unexpected disc read')):
            self.assertEqual(worker(Path('absent.iso'), b'', 'seed', Options.none(), None, Event()), 'unchanged')
        self.assertEqual(seen, [None])

    def test_incorrect_enablement_is_rejected_before_any_source_read(self):
        @scoped_content
        def worker(iso, boot, seed, options, cancel):
            self.fail('The invalid setting reached the transform')
        from types import SimpleNamespace
        for value in (1, 'yes', None):
            with self.assertRaises(ValueError):
                worker(Path('absent.iso'), b'', 'seed', SimpleNamespace(enable_fairy_type=value), Event())

    def test_optional_six_retail_complete_runtime_installations_and_meteorite_compose(self):
        from orre_randomizer.deoxys_meteorite import install_meteorite
        found = 0
        for game_id, path in PATHS.items():
            region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game_id[3]]
            rel_path = ROOT / (f'build/xd-validation/{region}/common_rel' if game_id.startswith('GXX') else
                f'build/region-compat-2026-11-02/rel-research/{ {"eu":"pal", "us":"usa", "jp":"japan"}[region] }/common.fsys-common_rel.rel')
            if not path.is_file() or not rel_path.is_file():
                continue
            found += 1
            with self.subTest(game_id=game_id):
                original_rel, original_dol = rel_path.read_bytes(), path.read_bytes()
                content = prepare_content(original_rel, original_dol, game_id)
                options = replace(Options.none(), enable_fairy_type=True, randomize_tm_moves=True)
                with fairy_gameplay_context(content):
                    current_rel, dol, report = apply_tm_gameplay(original_rel, content.baseline_rel,
                        original_dol, original_dol, 'fairy-content-contract', options, game_id,
                        species_table=_layouts(original_rel, game_id)['species'])
                    current_rel, dol, content_report = install_content(current_rel, dol, report)
                    self.assertFalse(content_report['preview_data_only'])
                    self.assertIsNotNone(content_report['move_effects'])
                    snapshot = read_installed_content(dol, content_report['additional_tms'])
                    self.assertEqual(len(snapshot['moves']), 7)
                    self.assertEqual(len(snapshot['tms']), 57)
                    extended, meteorite_rel, meteorite = install_meteorite(original_dol, dol, game_id,
                        **({'original_rel': original_rel, 'current_rel': current_rel} if game_id.startswith('GXX') else {}))
                    self.assertEqual(meteorite['item_id'], 277)
                    self.assertEqual(read_installed_content(extended, content_report['additional_tms']), snapshot)
                    if meteorite_rel is not None:
                        self.assertEqual(len(meteorite_rel), len(original_rel))
                self.assertIsNone(current_context())
        if not found:
            self.skipTest('Optional private regional original files are unavailable')

    def test_optional_known_only_previews_read_fixed_species_without_a_replacement_draw(self):
        from orre_randomizer import known_encounters, xd
        from orre_randomizer.engine.analyze_game import parse_rel
        from orre_randomizer.engine.inspect_tables import rel_symbols
        from orre_randomizer.xd_species_gameplay import XDMoveRandomizer
        found = 0
        for game_id, path in PATHS.items():
            region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game_id[3]]
            xd_game = game_id.startswith('GXX')
            rel_path = ROOT / (f'build/xd-validation/{region}/common_rel' if xd_game else
                f'build/region-compat-2026-11-02/rel-research/{ {"eu":"pal", "us":"usa", "jp":"japan"}[region] }/common.fsys-common_rel.rel')
            if not path.is_file() or not rel_path.is_file():
                continue
            if xd_game and not all((ROOT / f'build/xd-validation/{region}/{name}').is_file()
                    for name in ('DeckData_Story.bin', 'DeckData_DarkPokemon.bin')):
                continue
            found += 1
            with self.subTest(game_id=game_id):
                original_rel, dol = rel_path.read_bytes(), path.read_bytes()
                boot = bytearray(0x440)
                boot[:6] = game_id.encode('ascii')
                boot[0x1C:0x20] = bytes.fromhex('c2339f3d')
                def member(archive, name):
                    return (ROOT / f'build/xd-validation/{region}/{name}').read_bytes()
                options = replace(xd.XDOptions.unchanged() if xd_game else Options.none(), enable_fairy_type=True)
                with patch('orre_randomizer.known_encounters._read', return_value=(original_rel, dol, lambda _: b'', member)), \
                     patch('orre_randomizer.engine.randomize_trainers.choose_species', side_effect=AssertionError('Replacement draw')), \
                     patch('orre_randomizer.xd.choose_species', side_effect=AssertionError('Replacement draw')):
                    result = (known_encounters.xd_known if xd_game else known_encounters.colosseum_known)(
                        Path('not-opened.iso'), bytes(boot), 'known-fairy-only', options, Event())
                catalog = result['detail_catalog']
                self.assertEqual(len(catalog['tms']), 57)
                self.assertEqual(set(range(375, 382)), {int(i) for i in catalog['moves'] if int(i) >= 375})
                gardevoir = catalog['species']['394']
                self.assertIn(19, gardevoir['types'])
                self.assertTrue(any(row['move'] == 380 for row in gardevoir['learnset']))
                self.assertEqual(len(result['decks']['Story']['shadows'] if xd_game else result['final_shadow_picks']), 83 if xd_game else 48)
                self.assertIsNone(current_context())
        if not found:
            self.skipTest('Optional private regional original files are unavailable')


if __name__ == '__main__':
    unittest.main()
