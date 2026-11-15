"""Known rows reuse the exact background plan without revealing a random draw."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from orre_randomizer.options import Options
from orre_randomizer.preview import baseline_rows
from orre_randomizer.xd import XDOptions
from orre_randomizer.xd_preview import baseline_rows as xd_baseline_rows
try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
    from PySide6.QtWidgets import QApplication
    from orre_randomizer.gui import MainWindow
    from orre_randomizer.ui_known_preview import known_rows
except ImportError:
    MainWindow = None


def computed_fixture(options, *, xd=False, seed='seed'):
    """Already-computed production-shaped decisions, never another UI RNG."""
    result = deepcopy(xd_baseline_rows(options) if xd else baseline_rows(options))
    if xd:
        rows = [result['starter'], *result['decks']['Story']['shadows'],
                *result['gifts'], *result['poke_spots']]
        for row in rows:
            dex = row.get('national_dex')
            if dex is None:
                dex = result['national_ids'].get(str(row.get('species')), row.get('species'))
            if dex is None:
                dex = 25
            row['species'] = row.get('species') or dex
            row['national_dex'] = dex
    else:
        rows = [*result['starters'], *result['shadows'], *result['gifts']]
        if options.postgame_shadow_lugia:
            result['postgame_shadow_lugia']['team'] = [
                dict(national_dex=dex, species=dex, level=65 + i)
                for i, dex in enumerate((282, 178, 356, 365, 257, 249))]
            rows += result['postgame_shadow_lugia']['team']
        for row in rows:
            row['national_dex'] = row.get('national_dex') or 25
            row['species'] = row['national_dex']
    for index, row in enumerate(rows):
        row['shiny'] = options.shiny_chance_percent == 100 or (
            options.shiny_chance_percent not in (0, 100) and index % 3 == 0)
        row['portrait_png'] = b'exact-shiny-png' if row['shiny'] else b'exact-normal-png'
        row['details'] = {'national_dex': row['national_dex'], 'production_seed': seed, 'moves': [{'id': 1}]}
    result['seed'] = seed
    return result


@unittest.skipIf(MainWindow is None, 'requires optional Qt desktop dependencies')
class KnownRowTests(unittest.TestCase):
    def test_fixed_rows_keep_exact_decisions_at_zero_five_and_one_hundred_percent(self):
        for xd in (False, True):
            factory = XDOptions.recommended if xd else Options.recommended
            for rate in (0, 5, 100):
                options = replace(factory(), custom_shinies=True, shiny_chance_percent=rate)
                full = computed_fixture(options, xd=xd)
                visible = known_rows(options, full, xd=xd)
                original = full['decks']['Story']['shadows'] if xd else full['shadows']
                shown = visible['decks']['Story']['shadows'] if xd else visible['shadows']
                legendaries = (73, 74, 75, 76) if xd else (21, 23, 34)
                by_id = {row['shadow_id']: row for row in original}
                for row in shown:
                    if row['shadow_id'] in legendaries:
                        self.assertEqual(row, by_id[row['shadow_id']])
                    else:
                        self.assertNotIn('details', row)
                        self.assertIsNone(row.get('national_dex') if not xd else row['species'])
                self.assertEqual(known_rows(options, full, xd=xd), visible)

    def test_unprotected_legendaries_are_hidden_and_native_xd_lugia_stays_known(self):
        for xd in (False, True):
            factory = XDOptions.recommended if xd else Options.recommended
            options = replace(factory(), randomize_legendary_shadows=True)
            visible = known_rows(options, computed_fixture(options, xd=xd), xd=xd)
            shadows = visible['decks']['Story']['shadows'] if xd else visible['shadows']
            for row in shadows:
                self.assertEqual(bool(row.get('details')), xd and row['shadow_id'] == 73)

    def test_fixed_manual_starters_gifts_and_event_team_have_sheets(self):
        for xd in (False, True):
            options = XDOptions.unchanged() if xd else replace(Options.none(), postgame_shadow_lugia=True)
            visible = known_rows(options, computed_fixture(options, xd=xd), xd=xd)
            rows = ([visible['starter'], *visible['gifts'], *visible['poke_spots']] if xd else
                    [*visible['starters'], *visible['gifts'], *visible['postgame_shadow_lugia']['team']])
            self.assertTrue(all(row.get('details') for row in rows))
            options = (replace(XDOptions.recommended(), starter_species=252) if xd else
                       replace(Options.recommended(), starter_umbreon_species=252))
            visible = known_rows(options, computed_fixture(options, xd=xd), xd=xd)
            row = visible['starter'] if xd else visible['starters'][0]
            self.assertEqual(row['national_dex'], 252)
            self.assertIn('details', row)

    def test_no_rom_or_species_mismatch_never_fabricates_a_sheet_or_shiny(self):
        for xd in (False, True):
            options = XDOptions.recommended() if xd else Options.recommended()
            baseline = known_rows(options, xd=xd)
            rows = baseline['decks']['Story']['shadows'] if xd else baseline['shadows']
            self.assertTrue(all('details' not in row and 'shiny' not in row for row in rows))
            full = computed_fixture(options, xd=xd)
            targets = full['decks']['Story']['shadows'] if xd else full['shadows']
            for row in targets:
                row['national_dex'] = 25
            shown = known_rows(options, full, xd=xd)
            targets = shown['decks']['Story']['shadows'] if xd else shown['shadows']
            self.assertTrue(all('details' not in row for row in targets))


@unittest.skipIf(MainWindow is None, 'requires optional Qt desktop dependencies')
class KnownPreviewGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.updates = patch('orre_randomizer.gui.UpdateChecker.check_once')
        self.updates.start()
        settings = QSettings(str(self.root / 'private.ini'), QSettings.Format.IniFormat)
        settings.setValue('interface/music', False)
        settings.setValue('interface/sounds', False)
        settings.setValue('interface/language', 'fr')
        self.window = MainWindow(settings=settings, system_languages=['fr'])
        self.window.show()

    def pump(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition(), 'background preview did not finish')

    def tearDown(self):
        self.window.close_after_cancel = True
        self.window.cancel_preview()
        self.pump(lambda: self.window.preview_thread is None)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.updates.stop()
        self.folder.cleanup()

    def select(self, xd=False):
        w = self.window
        w.show_xd() if xd else w.show_colosseum()
        workspace = w.xd if xd else w
        workspace.step = 1
        (workspace.pages if xd else workspace.settings).setCurrentIndex(1)
        workspace.workspace_tabs.setCurrentIndex(1)
        source = self.root / ('xd.iso' if xd else 'colo.iso')
        source.write_bytes(b'owned fixture, production task is mocked')
        workspace.source.setText(str(source))
        workspace.known_preview.timer.setInterval(10)
        workspace.render_preview()
        return workspace

    def test_auto_prefetch_shows_only_known_rows_and_calculate_reuses_it_in_both_games(self):
        for xd in (False, True):
            calls = []
            def calculate(**arguments):
                calls.append(arguments['seed'])
                options = arguments['xd_options' if xd else 'options']
                return computed_fixture(options, xd=xd, seed=arguments['seed'])
            with patch('orre_randomizer.ui_known_preview.' + ('preview_xd' if xd else 'preview_starters'),
                       side_effect=calculate):
                pane = self.select(xd)
                self.pump(lambda: pane.known_preview.result is not None and self.window.preview_thread is None)
                self.assertIsNone(pane.preview_result)
                known = pane.preview_rows()
                shadows = known['decks']['Story']['shadows'] if xd else known['shadows']
                self.assertNotIn('details', shadows[0])
                self.assertIn('details', shadows[73 if xd else 20])
                pane.start_preview()
                self.assertIs(pane.preview_result, pane.known_preview.result)
                self.assertEqual(len(calls), 1)

    def test_loading_can_be_promoted_without_a_second_worker(self):
        for xd in (False, True):
            entered, release = threading.Event(), threading.Event()
            def calculate(**arguments):
                entered.set()
                release.wait(3)
                return computed_fixture(arguments['xd_options' if xd else 'options'], xd=xd)
            with patch('orre_randomizer.ui_known_preview.' + ('preview_xd' if xd else 'preview_starters'),
                       side_effect=calculate) as compute:
                pane = self.select(xd)
                self.pump(entered.is_set)
                self.assertTrue(pane.seed.isEnabled())
                thread = self.window.preview_thread
                pane.start_preview()
                self.assertIs(self.window.preview_thread, thread)
                self.assertTrue(pane.known_preview.reveal_requested)
                release.set()
                self.pump(lambda: self.window.preview_thread is None)
                self.assertIsNotNone(pane.preview_result)
                self.assertEqual(compute.call_count, 1)

    def test_seed_and_source_changes_clear_old_fixed_sheets_and_reject_late_results(self):
        entered = threading.Event()
        calls = []
        def calculate(**arguments):
            calls.append(arguments['seed'])
            if len(calls) == 1:
                entered.set()
                arguments['cancel'].wait(3)
            return computed_fixture(arguments['options'], seed=arguments['seed'])
        with patch('orre_randomizer.ui_known_preview.preview_starters', side_effect=calculate):
            pane = self.select()
            self.pump(entered.is_set)
            pane.seed.setText('new-seed')
            self.assertIsNone(pane.known_preview.result)
            self.pump(lambda: pane.known_preview.result is not None and self.window.preview_thread is None)
            self.assertEqual(pane.known_preview.result['seed'], 'new-seed')
            self.assertEqual(len(calls), 2)
            pane.source.clear()
            self.assertIsNone(pane.known_preview.result)
            self.assertTrue(all('details' not in row for row in pane.preview_rows()['shadows']))

    def test_missing_rom_stays_pending_without_error_or_worker(self):
        for xd in (False, True):
            pane = self.select(xd)
            pane.source.clear()
            pane.known_preview.start()
            self.assertIsNone(self.window.preview_thread)
            self.assertIsNone(pane.preview_result)
            self.assertIsNone(pane.known_preview.result)

    def test_option_edits_remove_sheets_immediately_and_fixed_rows_open_with_one_click(self):
        for xd in (False, True):
            def calculate(**arguments):
                return computed_fixture(arguments['xd_options' if xd else 'options'], xd=xd)
            with patch('orre_randomizer.ui_known_preview.' + ('preview_xd' if xd else 'preview_starters'),
                       side_effect=calculate):
                pane = self.select(xd)
                self.pump(lambda: pane.known_preview.result is not None and self.window.preview_thread is None)
                tabs = pane.encounter_tabs if xd else pane.preview_tabs
                tabs.setCurrentIndex(1)
                tree = pane.preview_details if xd else pane.encounters_tree
                item = tree.topLevelItem(73 if xd else 20)
                self.assertIn('details', item.data(0, Qt.ItemDataRole.UserRole + 2))
                with patch.object(self.window, 'show_pokemon_detail') as opened:
                    if xd:
                        pane.open_encounter_details(item, 1)
                    else:
                        pane.show_encounter_detail(item)
                    self.assertEqual(opened.call_count, 1)
                pane.set_options(replace(pane.current_options(), randomize_legendary_shadows=True))
                self.assertIsNone(pane.known_preview.result)
                rows = pane.preview_rows()
                shadows = rows['decks']['Story']['shadows'] if xd else rows['shadows']
                self.assertNotIn('details', shadows[73 if xd else 20])

    def test_background_cancel_leaves_no_worker(self):
        for xd in (False, True):
            entered = threading.Event()
            def calculate(**arguments):
                from orre_randomizer.service import Cancelled
                entered.set()
                arguments['cancel'].wait(3)
                raise Cancelled('Aperçu annulé.')
            with patch('orre_randomizer.ui_known_preview.' + ('preview_xd' if xd else 'preview_starters'),
                       side_effect=calculate):
                pane = self.select(xd)
                self.pump(entered.is_set)
                pane.cancel_preview()
                self.pump(lambda: self.window.preview_thread is None)
                self.assertIsNone(pane.preview_result)
                self.assertIsNone(pane.known_preview.result)

    def test_closing_while_the_automatic_job_runs_cancels_and_cleans_up(self):
        entered = threading.Event()
        def calculate(**arguments):
            from orre_randomizer.service import Cancelled
            entered.set()
            arguments['cancel'].wait(3)
            raise Cancelled('Aperçu annulé.')
        with patch('orre_randomizer.ui_known_preview.preview_starters', side_effect=calculate):
            self.select()
            self.pump(entered.is_set)
            self.window.close()
            self.pump(lambda: self.window.preview_thread is None and not self.window.isVisible())

    def test_promoted_cancel_rejects_a_late_success_and_finishes_the_loading_state(self):
        entered, release = threading.Event(), threading.Event()
        def calculate(**arguments):
            entered.set()
            release.wait(3)
            return computed_fixture(arguments['options'])
        with patch('orre_randomizer.ui_known_preview.preview_starters', side_effect=calculate):
            pane = self.select()
            self.pump(entered.is_set)
            pane.start_preview()
            pane.cancel_preview()
            release.set()
            self.pump(lambda: self.window.preview_thread is None)
            self.assertIsNone(pane.preview_result)
            self.assertIsNone(pane.known_preview.result)
            self.assertNotIn('Annulation', pane._preview_message)

    def test_fixed_starters_and_bonus_cards_open_their_prefetched_sheet(self):
        for xd in (False, True):
            def calculate(**arguments):
                return computed_fixture(arguments['xd_options' if xd else 'options'], xd=xd)
            with patch('orre_randomizer.ui_known_preview.' + ('preview_xd' if xd else 'preview_starters'),
                       side_effect=calculate):
                pane = self.select(xd)
                pane.set_options(XDOptions.unchanged() if xd else
                                 replace(Options.none(), postgame_shadow_lugia=True))
                self.pump(lambda: pane.known_preview.result is not None and self.window.preview_thread is None)
                self.assertIsNone(pane.preview_result)
                button = pane.starter_details if xd else pane.starter_detail_buttons['umbreon']
                self.assertFalse(button.isHidden())
                with patch.object(self.window, 'show_pokemon_detail') as opened:
                    button.click()
                    self.assertEqual(opened.call_count, 1)
                if not xd:
                    self.assertTrue(all(not action.isHidden() for _p, _n, action in pane.bonus_event_preview.slots))
                    with patch.object(self.window, 'show_pokemon_detail') as opened:
                        pane.bonus_event_preview.slots[5][2].click()
                        self.assertEqual(opened.call_args.args[0]['national_dex'], 249)

    def test_empty_seed_does_not_start_or_raise_an_automatic_job(self):
        for xd in (False, True):
            pane = self.select(xd)
            pane.seed.clear()
            pane.known_preview.start()
            self.assertIsNone(self.window.preview_thread)

    def test_retired_shop_scope_is_preserved_and_part_of_the_preview_identity(self):
        if 'legacy_shop_scope' not in Options.__dataclass_fields__:
            self.skipTest('shop profile compatibility is not installed')
        w = self.window
        kept = replace(Options.recommended(), legacy_shop_scope=True)
        w.set_options(kept)
        before = w.preview_configuration()
        self.assertTrue(w.current_options().legacy_shop_scope)
        self.assertTrue(w.rule_fields['legacy_shop_scope'].isHidden())
        w.set_options(Options.recommended())
        self.assertFalse(w.current_options().legacy_shop_scope)
        self.assertNotEqual(w.preview_configuration(), before)
