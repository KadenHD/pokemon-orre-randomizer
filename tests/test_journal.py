"""The local journal reveals spoilers explicitly and treats report text as data."""
import copy
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest

from colosseum_randomizer.detail_texts import LANGUAGES
from colosseum_randomizer.journal import render_journal, save_journal
from test_pokemon_details import catalog_fixture


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


def report_fixture():
    catalog = catalog_fixture()
    return {'seed': '<script>alert("x")</script>', 'application_version': 'fixture', 'engine_version': 'test',
        'game_id': 'GC6P01', 'source': 'C:/Private/person/rom.iso', 'output': 'C:/Private/person/new.iso',
        'source_iso_sha256': 'a' * 64, 'options': {'custom_shinies': True, 'seeded_shinies': True,
            'shiny_chance_percent': 25.0, 'accessible_event_gifts': True, 'event_pikachu_purifications': 10},
        'summary': {'detail_catalog': catalog, 'special_gameplay': {'specials': [
            {'key': 'umbreon', 'species': 1, 'level': 26},
            {'key': 'pikachu-event', 'species': 2, 'level': 30}]},
            'final_shadow_picks': [{'shadow_id': 1, 'species_index': 1, 'name_fr': 'ONIX', 'name_en': 'Onix'}],
            'shinies': {'seeded_decisions': {'specials': {'umbreon': True, 'pikachu-event': False}, 'shadows': {'1': False}}}}}


class JournalTests(unittest.TestCase):
    def test_all_sections_localized_and_closed_without_scripts_or_paths(self):
        report = report_fixture()
        saved = copy.deepcopy(report)
        for language in LANGUAGES:
            output = render_journal(report, language)
            parser = Inspector()
            parser.feed(output)
            self.assertIn('lang="' + language + '"', output)
            self.assertNotIn('script', parser.tags)
            self.assertNotIn(('open', None), parser.attributes)
            self.assertFalse(any(key.lower().startswith('on') for key, _ in parser.attributes))
            self.assertFalse(any(key in ('src', 'href') for key, _ in parser.attributes))
            self.assertNotIn('C:/Private', output)
            self.assertIn('&lt;script&gt;', output)
            self.assertIn('Content-Security-Policy', output)
            self.assertGreaterEqual(parser.tags.count('details'), 12)
            self.assertIn('40', output)
        self.assertEqual(report, saved)

    def test_seeded_shiny_and_purification_conditions_are_visible_on_reveal(self):
        output = render_journal(report_fixture(), 'fr')
        self.assertIn('Chromatique', output)
        self.assertIn('Non chromatique', output)
        self.assertIn('10 purifications', output)
        self.assertIn('Purifiez ce Pokémon', output)
        self.assertIn('Niveau 30', output)
        self.assertIn('DRESSEUR NATIF', output)

    def test_nonseeded_rate_does_not_claim_a_specific_shiny_status(self):
        report = report_fixture()
        report['options']['seeded_shinies'] = False
        output = render_journal(report, 'en')
        self.assertIn('Shiny status decided in-game', output)

    def test_exclusive_write_and_bad_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.html'
            save_journal(path, report_fixture(), 'ja')
            content = path.read_bytes()
            with self.assertRaises(FileExistsError):
                save_journal(path, report_fixture(), 'ja')
            self.assertEqual(path.read_bytes(), content)
            with self.assertRaises(ValueError):
                save_journal(path.with_suffix('.iso'), report_fixture())
        with self.assertRaises(ValueError):
            render_journal({}, 'xx')


if __name__ == '__main__':
    unittest.main()
