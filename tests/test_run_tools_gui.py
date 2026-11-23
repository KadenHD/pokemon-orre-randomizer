"""Native widgets exercise all four tools with private preferences and fake cards."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import ast
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest

from orre_randomizer.challenges import encode_challenge
from orre_randomizer.gui import MainWindow
from orre_randomizer.i18n import CATALOGS, LANGUAGES
from orre_randomizer.options import Options
from orre_randomizer.run_library import window_library
from orre_randomizer.ui_run_tools import LibraryDialog, BackupDialog, StorageDialog, ChallengeDialog
from orre_randomizer.ui_play import GameLauncher, LaunchPreparation
from orre_randomizer.xd import XDOptions
from tests.test_run_management import game_fixture


class RunToolsGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if os.name == "nt":
            from PySide6.QtGui import QFont, QFontDatabase
            fonts = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
            for name in ("segoeui.ttf", "YuGothR.ttc"):
                QFontDatabase.addApplicationFont(str(fonts / name))
            cls.app.setFont(QFont("Segoe UI", 10))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        settings = QSettings(str(self.root / "preferences.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False); settings.setValue("interface/sounds", False)
        settings.setValue("launcher/shared", str(self.root / "Shared"))
        self.window = MainWindow(settings=settings, system_languages=["en"], start_on_home=True, allow_update_checks=False)
        self.folder, self.manifest = game_fixture(self.root)
        window_library(self.window).register(self.folder / "game.json")
        self.dialogs = []
        self.idle = patch("orre_randomizer.run_safety.dolphin_arguments", return_value=[])
        self.idle.start(); self.addCleanup(self.idle.stop)

    def tearDown(self):
        for dialog in self.dialogs:
            self.wait(dialog); dialog.close(); dialog.deleteLater()
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def wait(self, dialog):
        deadline = time.monotonic() + 8
        while dialog.task is not None:
            self.app.processEvents(); QTest.qWait(5)
            self.assertLess(time.monotonic(), deadline, "Worker did not finish")
        self.app.processEvents()

    def dialog(self, cls, *args, **kwargs):
        dialog = cls(self.window, *args, **kwargs); self.dialogs.append(dialog)
        dialog.show()
        if hasattr(dialog, "task"):
            self.wait(dialog)
        return dialog

    def test_library_lists_real_metadata_filters_and_only_forgets_the_reference(self):
        dialog = self.dialog(LibraryDialog)
        self.assertEqual(dialog.list.rowCount(), 1)
        self.assertEqual(dialog.list.item(0, 2).text(), "seed-é")
        dialog.search.setText("Pokémon Colosseum")
        self.assertFalse(dialog.list.isRowHidden(0))
        dialog.search.setText("does not exist")
        self.assertTrue(dialog.list.isRowHidden(0))
        self.assertFalse(dialog.play.isEnabled())
        dialog.search.clear(); dialog.list.selectRow(0)
        dialog.forget_run(); self.wait(dialog)
        self.assertEqual(dialog.list.rowCount(), 0)
        self.assertTrue((self.folder / "Game/game.iso").is_file())

    def test_backup_dialog_creates_and_restores_real_synthetic_card(self):
        card = self.folder / "DolphinUser/GC/MemoryCardA.EUR.raw"; card.write_bytes(b"saved progress")
        dialog = self.dialog(BackupDialog, self.folder)
        dialog.create_backup(); self.wait(dialog)
        self.assertEqual(dialog.list.rowCount(), 1)
        card.write_bytes(b"new progress")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog.restore_selected(); self.wait(dialog)
        self.assertEqual(card.read_bytes(), b"saved progress")
        self.assertIn("restored", dialog.status.text())

    def test_storage_readonly_scan_keeps_cleanup_disabled_without_eligible_caches(self):
        dialog = self.dialog(StorageDialog)
        self.assertEqual(dialog.plan.categories["roms"], len(b"synthetic QA disc"))
        self.assertFalse(dialog.clean.isEnabled())
        self.assertTrue((self.folder / "Game/game.iso").is_file())

    def test_challenge_import_switches_game_after_complete_validation(self):
        dialog = self.dialog(ChallengeDialog, importing=True)
        seed = self.window.seed.text()
        dialog.code.setPlainText("broken code"); dialog.apply()
        self.assertEqual(self.window.seed.text(), seed)
        self.assertIs(self.window.game_views.currentWidget(), self.window.home)
        options = XDOptions()
        dialog.code.setPlainText(encode_challenge("Amis 日本語", options)); dialog.apply()
        self.assertIs(self.window.game_views.currentWidget(), self.window.xd)
        self.assertEqual(self.window.xd.seed.text(), "Amis 日本語")
        self.assertEqual(self.window.xd.current_options(), options)

    def test_all_dialogs_fit_fixed_windows_in_all_six_languages(self):
        overflows = []
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            for cls, args, kwargs in ((LibraryDialog, (), {}), (StorageDialog, (), {}),
                                      (BackupDialog, (self.folder,), {}), (ChallengeDialog, (), {"importing": True})):
                dialog = self.dialog(cls, *args, **kwargs)
                dialog.layout().activate()
                minimum = dialog.layout().minimumSize()
                if minimum.height() > dialog.height() or minimum.width() > dialog.width():
                    overflows.append((language, cls.__name__, minimum.width(), minimum.height()))
                dialog.close()
        self.assertEqual(overflows, [])

    def test_home_utilities_fit_without_scrolling_at_normal_window_size(self):
        self.window.resize(1040, 800); self.window.show_home(); self.window.show()
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.app.processEvents()
            with self.subTest(language=language):
                self.assertEqual(self.window.home.scroll.verticalScrollBar().maximum(), 0)
                self.assertEqual(self.window.home.scroll.horizontalScrollBar().maximum(), 0)

    def test_move_choices_keep_bool_and_species_modes_distinct_in_both_workspaces(self):
        for view, defaults in ((self.window, Options.none()), (self.window.xd, XDOptions.unchanged())):
            for mode in (False, "natural", True):
                expected = replace(defaults, randomize_trainer_moves=mode,
                    randomize_starter_moves=mode, randomize_gift_moves=mode)
                view.set_options(expected)
                self.assertEqual(view.current_options(), expected)

    def test_new_copy_has_all_languages_and_preserves_format_parameters(self):
        from orre_randomizer.run_i18n import ROWS
        for language, catalog in CATALOGS.items():
            self.assertFalse(set(ROWS) - catalog.keys(), language)
            for key in ROWS:
                self.assertTrue(catalog[key])
                import string
                fields = lambda text: sorted(name for _, name, _, _ in string.Formatter().parse(text) if name)
                self.assertEqual(fields(key), fields(catalog[key]), (language, key))

    def test_closing_a_worker_waits_for_cooperative_cleanup(self):
        dialog = self.dialog(StorageDialog)
        def until_cancel(cancel):
            self.assertTrue(cancel.wait(4))
        dialog.start_task(until_cancel, lambda result: None)
        dialog.close()
        self.assertTrue(dialog.want_close)
        self.wait(dialog)
        self.assertFalse(dialog.isVisible())

    def test_launch_preparation_checks_backup_before_releasing_the_command(self):
        worker = LaunchPreparation(self.folder, self.manifest, None)
        events = []
        worker.succeeded.connect(lambda command, context: events.append("ready"))
        with patch("orre_randomizer.ui_play.launch_command", side_effect=lambda *args, **kwargs: events.append("prepare") or ["fake"]), \
             patch("orre_randomizer.save_backups.backup_cards", side_effect=lambda *args, **kwargs: events.append("backup")):
            worker.run()
        self.assertEqual(events, ["prepare", "backup", "ready"])
        self.manifest["settings"]["save_backups"] = False
        with patch("orre_randomizer.ui_play.launch_command", return_value=["fake"]), \
             patch("orre_randomizer.save_backups.backup_cards") as backup:
            worker.run()
            backup.assert_not_called()
        worker.deleteLater()

    def test_launcher_creates_a_real_copy_before_its_launch_slot(self):
        tool = self.root / "Dolphin.exe"; tool.write_bytes(b"never executed")
        card = self.folder / "DolphinUser/GC/MemoryCardA.EUR.raw"; card.write_bytes(b"card before play")
        launcher = GameLauncher(self.folder / "game.json", preferences=self.window.preferences)
        try:
            with patch("orre_randomizer.ui_play.launch_command", return_value=[str(tool)]), \
                 patch.object(launcher, "launch") as launch:
                launcher.start()
                deadline = time.monotonic() + 8
                while launcher.preparation is not None:
                    self.app.processEvents(); QTest.qWait(5)
                    self.assertLess(time.monotonic(), deadline)
                launch.assert_called_once()
            from orre_randomizer.save_backups import list_backups
            copies = list_backups(self.folder)
            self.assertEqual(len(copies), 1)
            self.assertEqual((self.folder / "SaveBackups" / copies[0]["name"] / card.name).read_bytes(), card.read_bytes())
        finally:
            launcher.release(); launcher.close(); launcher.deleteLater()


if __name__ == "__main__":
    unittest.main()
