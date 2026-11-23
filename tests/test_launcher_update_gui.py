"""The optional launcher update remains explicit, localized and cancellable."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from orre_randomizer.gui import MainWindow
from orre_randomizer.i18n import LANGUAGES, is_translatable
from orre_randomizer.service import Cancelled
from orre_randomizer.ui_launcher_update import LauncherUpdateDialog


class LauncherUpdateGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        settings = QSettings(str(self.root / 'preferences.ini'), QSettings.Format.IniFormat)
        settings.setValue('interface/music', False); settings.setValue('interface/sounds', False)
        settings.setValue('launcher/shared', str(self.root / 'Shared'))
        self.checker = patch('orre_randomizer.gui.UpdateChecker.check_once'); self.checker.start()
        self.addCleanup(self.checker.stop)
        self.window = MainWindow(settings=settings, system_languages=['en-US'])
        self.status = patch('orre_randomizer.ui_launcher_update.upgrade_status', return_value={
            'previous_version': '2.0.0', 'version': '2.0.6', 'available': True})
        self.status.start(); self.addCleanup(self.status.stop)
        self.dialog = None

    def tearDown(self):
        if self.dialog:
            if self.dialog.thread:
                self.dialog.thread.cancel.set()
                deadline = time.monotonic() + 3
                while self.dialog.thread and time.monotonic() < deadline:
                    self.app.processEvents(); time.sleep(.005)
            self.dialog.close(); self.dialog.deleteLater()
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def make_dialog(self):
        self.dialog = LauncherUpdateDialog(self.window, self.root / 'Existing run/game.json')
        self.dialog.show(); self.app.processEvents()
        return self.dialog

    def drain(self):
        deadline = time.monotonic() + 3
        while self.dialog.thread and time.monotonic() < deadline:
            self.app.processEvents(); time.sleep(.005)
        self.assertIsNone(self.dialog.thread)

    def test_opening_the_dialog_does_not_upgrade_and_all_six_languages_fit(self):
        with patch('orre_randomizer.ui_launcher_update.upgrade_launcher') as task:
            for language in LANGUAGES:
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
                self.window.resize(680, 540); self.window.show_home(); self.window.show()
                self.app.processEvents()
                self.assertEqual(self.window.home.scroll.horizontalScrollBar().maximum(), 0)
                dialog = self.make_dialog()
                self.assertEqual((dialog.width(), dialog.height()), (760, 400))
                self.assertLessEqual(dialog.layout().minimumSize().height(), dialog.height())
                self.assertLessEqual(dialog.layout().minimumSize().width(), dialog.width())
                self.assertTrue(dialog.update.isEnabled())
                task.assert_not_called()
                dialog.close(); dialog.deleteLater(); self.dialog = None
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        for text in ('Mettre à jour un lanceur…', 'Partie Orre (game.json)', 'Lanceur déjà à jour.', 'Préparation du nouveau lanceur…'):
            self.assertTrue(is_translatable(text), text)

    def test_already_current_launchers_cannot_start_an_update(self):
        with patch('orre_randomizer.ui_launcher_update.upgrade_status', return_value={
                'previous_version': '2.0.6', 'version': '2.0.6', 'available': False}):
            dialog = self.make_dialog()
        self.assertFalse(dialog.update.isEnabled())
        self.assertEqual(dialog.status.text(), self.window.text('Lanceur déjà à jour.'))
        dialog.start(); self.assertIsNone(dialog.thread)

    def test_long_folder_names_remain_accessible_without_expanding_the_dialog(self):
        self.dialog = LauncherUpdateDialog(self.window, self.root / ('Very long game name ' * 12) / 'game.json')
        self.dialog.show(); self.app.processEvents()
        from PySide6.QtWidgets import QLabel
        name = next(label for label in self.dialog.findChildren(QLabel) if label.accessibleName() == str(self.dialog.path.parent))
        self.assertIn('…', name.text())
        self.assertEqual(name.toolTip(), str(self.dialog.path.parent))
        self.assertEqual(self.dialog.width(), 760)

    def test_close_cancels_the_worker_without_blocking_events_or_destroying_it(self):
        beats = []
        timer = QTimer(); timer.setInterval(5); timer.timeout.connect(lambda: beats.append(True))
        def task(path, *, cancel):
            cancel.wait(1)
            time.sleep(.08)  # visible native-thread cleanup after cancellation
            raise Cancelled('Opération annulée.')
        with patch('orre_randomizer.ui_launcher_update.upgrade_launcher', side_effect=task):
            dialog = self.make_dialog(); timer.start(); dialog.start()
            self.assertFalse(dialog.update.isEnabled())
            dialog.close()
            self.assertIsNotNone(dialog.thread)
            self.assertTrue(dialog.thread.cancel.is_set())
            self.drain(); timer.stop()
        self.assertGreater(len(beats), 2)
        self.assertFalse(dialog.isVisible())

    def test_success_clears_progress_and_prevents_a_duplicate_upgrade(self):
        with patch('orre_randomizer.ui_launcher_update.upgrade_launcher', return_value={'changed': True}) as task:
            dialog = self.make_dialog(); dialog.start(); self.drain()
            self.assertEqual(dialog.progress.value(), 1)
            self.assertFalse(dialog.update.isEnabled())
            self.assertTrue(dialog.done.isEnabled())
            dialog.start(); self.assertEqual(task.call_count, 1)

    def test_unexpected_worker_failure_is_not_reported_as_a_success(self):
        with patch('orre_randomizer.ui_launcher_update.upgrade_launcher', side_effect=RuntimeError('worker failed')):
            dialog = self.make_dialog(); dialog.start(); self.drain()
        self.assertEqual(dialog.progress.value(), 0)
        self.assertEqual(dialog.status.text(), self.window.text('Impossible de mettre à jour le lanceur.'))
        self.assertTrue(dialog.update.isEnabled())

    def test_main_window_waits_for_a_cancelled_launcher_update_to_finish(self):
        def task(path, *, cancel):
            cancel.wait(1); time.sleep(.05)
            raise Cancelled('Opération annulée.')
        with patch('orre_randomizer.ui_launcher_update.upgrade_launcher', side_effect=task):
            self.window.show(); dialog = self.make_dialog()
            self.window.launcher_update_dialog = dialog
            dialog.start(); self.window.close()
            self.assertTrue(dialog.thread.cancel.is_set())
            self.assertTrue(dialog.close_parent_after_cancel)
            self.assertTrue(self.window.isVisible())
            self.drain(); self.assertFalse(self.window.isVisible())


if __name__ == '__main__':
    unittest.main()
