"""Independent v0.15 UI/state and publication transaction regressions."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from colosseum_randomizer import service
from colosseum_randomizer.options import Options
from colosseum_randomizer.pokemon_details import encounter_details
from tests.test_pokemon_details import catalog_fixture

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QProgressBar
    from colosseum_randomizer.gui import MainWindow
except ImportError:
    MainWindow = None


def final_preview():
    catalog = catalog_fixture()
    def row(key, index, level):
        details = encounter_details(catalog, index, level=level, moves=[1, 2])
        return {'key': key, 'species': index, 'national_dex': details['national_dex'],
                **{'name_' + language: name for language, name in details['names'].items()},
                'level': level, 'portrait_png': b'', 'details': details}
    first, second = row('umbreon', 1, 26), row('espeon', 2, 25)
    shadow = dict(row('shadow-1', 1, 31), shadow_id=1, original=second)
    shadow['details']['shadow'] = True
    gift = dict(row('plusle', 2, 13), original=first, event=False)
    return {'starters': [first, second], 'shadows': [shadow], 'gifts': [gift], 'shiny_policy': 'original'}


@unittest.skipIf(MainWindow is None, 'requires optional Qt desktop dependencies')
class V15GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / 'source.iso'
        self.source.write_bytes(b'owned synthetic source; preview worker mocked')
        settings = QSettings(str(self.root / 'prefs.ini'), QSettings.Format.IniFormat)
        settings.setValue('interface/music', False)
        settings.setValue('interface/sounds', False)
        self.window = MainWindow(settings=settings, system_languages=['fr-FR'])
        self.window.source.setText(str(self.source))
        self.window.seed.setText('v15-review')

    def pump_until(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition())

    def tearDown(self):
        self.window.cancel_preview()
        self.pump_until(lambda: self.window.preview_thread is None)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.directory.cleanup()

    def load_preview(self):
        with patch('colosseum_randomizer.gui.preview_starters', return_value=final_preview()):
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)

    def test_manual_species_ids_survive_all_languages_and_disabled_starter(self):
        first = self.window.rule_fields['starter_umbreon_species']
        second = self.window.rule_fields['starter_espeon_species']
        first.setCurrentIndex(first.findData(95))
        second.setCurrentIndex(second.findData(133))
        for language in ('fr', 'en', 'de', 'es', 'it', 'ja'):
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            options = self.window.current_options()
            self.assertEqual((options.starter_umbreon_species, options.starter_espeon_species), (95, 133))
            self.assertEqual(first.currentData(), 95)
            self.assertIn('095', first.currentText())
        self.window.rule_checks['starter_umbreon'].setChecked(False)
        self.assertFalse(first.isEnabled())
        self.assertEqual(self.window.current_options().starter_umbreon_species, 95)
        self.window.rule_checks['starter_umbreon'].setChecked(True)
        self.assertTrue(first.isEnabled())

    def test_unmatched_typed_species_is_not_silently_used_as_another_choice(self):
        combo = self.window.rule_fields['starter_umbreon_species']
        combo.setCurrentIndex(combo.findData(95))
        combo.setEditText('not a Pokémon selection')
        combo.lineEdit().editingFinished.emit()
        self.app.processEvents()
        self.assertEqual(self.window.current_options().starter_umbreon_species, -1,
                         'unmatched edit must be rejected instead of silently using the old choice')
        with patch('colosseum_randomizer.gui.preview_starters') as worker:
            self.window.start_preview()
            worker.assert_not_called()
        self.assertIsNone(self.window.preview_thread)
        self.assertIn('Choisissez un Pokémon', self.window.preview_hint.text())
        self.assertEqual(combo.currentData(), 95)

    def test_exact_typed_species_entry_resolves_its_own_id(self):
        combo = self.window.rule_fields['starter_umbreon_species']
        combo.setCurrentIndex(combo.findData(95))
        combo.setEditText(combo.itemText(combo.findData(25)))
        combo.lineEdit().editingFinished.emit()
        self.app.processEvents()
        self.assertEqual(self.window.current_options().starter_umbreon_species, 25)

    def test_starter_and_single_click_encounter_sheets_use_final_data_and_clear_on_stale(self):
        self.assertFalse(self.window.starter_detail_buttons['umbreon'].isEnabled())
        self.load_preview()
        self.assertTrue(self.window.starter_detail_buttons['umbreon'].isEnabled())
        self.window.show_starter_detail('umbreon')
        self.assertIsNotNone(self.window.detail_window)
        sheet = self.window.detail_window
        text = "\n".join(label.text() for label in sheet.findChildren(QLabel))
        self.assertEqual(sheet.tabs.count(), 3)
        self.assertEqual(len(sheet.findChildren(QProgressBar, "sheetStat")), 6)
        self.assertIn('Onix natif', text)
        self.assertIn('Steelix natif', text)
        self.assertIn('Feu / Eau', text)
        self.assertIn('90', text)
        self.assertIn('40', text)
        self.assertNotIn('Échanger ce Pokémon', text)
        self.window.detail_window.close()
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.show()
        self.window.activateWindow()
        tree = self.window.encounters_tree
        for tab, column, name in ((1, 0, 'Onix natif'), (2, 1, 'Steelix natif')):
            self.window.preview_tabs.setCurrentIndex(tab)
            self.app.processEvents()
            index = tree.model().index(0, column)
            point = tree.visualRect(index).center()
            self.assertTrue(tree.viewport().rect().contains(point))
            self.assertTrue(self.window.encounter_detail_hint.isVisible())
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.RightButton, pos=point)
            self.assertIsNone(self.window.detail_window)
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point)
            self.pump_until(lambda: self.window.detail_window is not None)
            self.assertIn(name, "\n".join(label.text() for label in self.window.detail_window.findChildren(QLabel)))
            self.window.detail_window.close()
        self.window.preview_tabs.setCurrentIndex(1)
        self.window.activateWindow()
        tree.setFocus()
        tree.setCurrentItem(tree.topLevelItem(0))
        self.app.processEvents()
        self.assertIsNone(self.window.detail_window)
        QTest.keyClick(tree, Qt.Key.Key_Return)
        self.pump_until(lambda: self.window.detail_window is not None)
        dialog = self.window.detail_window
        self.assertIn('Purifiez ce Pokémon', "\n".join(label.text() for label in dialog.findChildren(QLabel)))
        self.window.seed.setText('stale')
        self.assertIsNone(self.window.preview_result)
        self.assertIsNone(self.window.detail_window)
        self.assertFalse(dialog.isVisible())
        self.assertFalse(self.window.starter_detail_buttons['umbreon'].isEnabled())
        self.assertTrue(self.window.encounter_detail_hint.isHidden())
        self.window.show_starter_detail('umbreon')
        self.assertIsNone(self.window.detail_window)


class JournalPublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.source, self.output = self.root / 'original.iso', self.root / 'copy.iso'
        self.source.write_bytes(bytes(range(64)))
        self.json_path, self.html_path = self.root / 'copy.iso.json', self.root / 'copy.iso.html'

    def tearDown(self):
        self.directory.cleanup()

    def run_tiny_copy(self, *, publication=None):
        # Exercise the real copy, verification, JSON/HTML rendering and three-file
        # publication transaction. Only the original disc parser/patch plan are
        # replaced by a bounded, synthetic unchanged image.
        with patch.object(service, 'ISO_SIZE', 64), patch.object(service, 'CHUNK', 11), \
             patch.object(service, 'check_header', return_value=bytes(0x440)), \
             patch.object(service, 'check_disc_identity', return_value=SimpleNamespace(game_id='GC6P01', revision=0)), \
             patch.object(service, 'build_patches', return_value=([], {})) as plan:
            self.last_plan = plan
            if publication:
                with patch.object(service, 'publish_new', side_effect=publication):
                    return service.randomize(self.source, self.output, 'copy-seed', Options.none(), journal_language='ja')
            report = service.randomize(self.source, self.output, 'copy-seed', Options.none(), journal_language='ja')
            self.assertEqual(plan.call_args.args[3], Options.none())
            return report

    def test_unchanged_copy_publishes_matching_json_and_localized_html(self):
        before = self.source.read_bytes()
        report = self.run_tiny_copy()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(json.loads(self.json_path.read_text('utf8')), json.loads(json.dumps(report)))
        self.assertEqual(report['journal'], str(self.html_path))
        self.assertIn('lang="ja"', self.html_path.read_text('utf8'))
        self.assertNotIn(str(self.source), self.html_path.read_text('utf8'))
        self.assertFalse(list(self.root.glob('.colosseum-*')))

    def test_preexisting_journal_is_preserved_before_any_work(self):
        self.html_path.write_bytes(b'preexisting journal')
        with self.assertRaises(service.UserError):
            self.run_tiny_copy()
        self.last_plan.assert_not_called()
        self.assertEqual(self.html_path.read_bytes(), b'preexisting journal')
        self.assertFalse(self.output.exists())
        self.assertFalse(self.json_path.exists())

    def test_racing_journal_is_never_deleted_by_rollback(self):
        original_publish = service.publish_new
        def publish(source, target):
            if target == self.html_path:
                self.html_path.write_bytes(b'journal created by another process')
            return original_publish(source, target)
        with self.assertRaises(service.UserError):
            self.run_tiny_copy(publication=publish)
        self.assertEqual(self.html_path.read_bytes(), b'journal created by another process')
        self.assertFalse(self.json_path.exists())
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.colosseum-*')))

    def test_racing_rom_is_preserved_and_owned_json_html_rolled_back(self):
        original_publish = service.publish_new
        def publish(source, target):
            if target == self.output:
                self.output.write_bytes(b'ROM created by another process')
            return original_publish(source, target)
        with self.assertRaises(service.UserError):
            self.run_tiny_copy(publication=publish)
        self.assertEqual(self.output.read_bytes(), b'ROM created by another process')
        self.assertFalse(self.json_path.exists())
        self.assertFalse(self.html_path.exists())
        self.assertEqual(self.source.read_bytes(), bytes(range(64)))
        self.assertFalse(list(self.root.glob('.colosseum-*')))


if __name__ == '__main__':
    unittest.main()
