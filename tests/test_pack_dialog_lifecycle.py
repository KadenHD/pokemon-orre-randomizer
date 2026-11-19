"""Exercise real Qt worker signals, cancellation and neutral popup rendering."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from orre_randomizer.gui import MainWindow
from orre_randomizer.service import Cancelled
from orre_randomizer.ui_game_folder import PackDialog


class PackDialogLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        prefs = QSettings(str(self.root / "preferences.ini"), QSettings.Format.IniFormat)
        prefs.setValue("interface/music", False)
        prefs.setValue("interface/sounds", False)
        prefs.setValue("launcher/shared", str(self.root / "Shared"))
        self.update = patch("orre_randomizer.gui.UpdateChecker.check_once")
        self.update.start()
        self.addCleanup(self.update.stop)
        self.window = MainWindow(settings=prefs, system_languages=["en-US"], start_on_home=True)
        self.dialog = PackDialog(self.window)

    def wait_for(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition(), "Qt worker did not reach the expected state")

    def tearDown(self):
        if self.dialog.thread is not None:
            self.dialog.thread.cancel.set()
            self.wait_for(lambda: self.dialog.thread is None)
        self.dialog.close()
        self.dialog.deleteLater()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_real_worker_starts_reports_progress_and_finishes(self):
        started, release = threading.Event(), threading.Event()

        def install(_store, _game, *, cancel, progress, force):
            started.set()
            progress(34, "Téléchargement du pack HD…")
            while not release.wait(.01):
                if cancel.is_set():
                    raise Cancelled("Opération annulée.")
            return {}

        try:
            with patch("orre_randomizer.hd_packs.PackStore.install_game", install):
                self.dialog.show()
                self.dialog.install("colosseum")
                self.assertEqual((self.dialog.progress.minimum(), self.dialog.progress.maximum()), (0, 0))
                self.assertFalse(self.dialog.done.isEnabled())
                self.wait_for(lambda: started.is_set() and self.dialog.progress.value() == 34)
                self.assertTrue(self.dialog.progress.isVisible())
                self.assertTrue(self.dialog.cancel.isVisible())
                release.set()
                self.wait_for(lambda: self.dialog.thread is None)
                self.assertEqual(self.dialog.progress.value(), 100)
                self.assertEqual(self.dialog.status.text(), self.window.text("Packs HD installés et vérifiés."))
                self.assertTrue(self.dialog.done.isEnabled())
        finally:
            release.set()

    def test_close_cancels_the_real_worker_and_closes_after_cleanup(self):
        started = threading.Event()

        def install(_store, _game, *, cancel, progress, force):
            started.set()
            cancel.wait(2)
            if cancel.is_set():
                raise Cancelled("Opération annulée.")
            return {}

        with patch("orre_randomizer.hd_packs.PackStore.install_game", install):
            self.dialog.show()
            self.dialog.install("xd")
            self.wait_for(started.is_set)
            responsive = []
            QTimer.singleShot(0, lambda: responsive.append(True))
            self.wait_for(lambda: bool(responsive))
            self.dialog.close()
            self.assertEqual(self.dialog.status.text(), self.window.text("Annulation en cours…"))
            self.wait_for(lambda: self.dialog.thread is None and not self.dialog.isVisible())

    def test_failed_worker_releases_controls_for_retry(self):
        def install(*args, **kwargs):
            raise OSError("Offline test")

        with patch("orre_randomizer.hd_packs.PackStore.install_game", install):
            self.dialog.install("colosseum")
            self.wait_for(lambda: self.dialog.thread is None)
        self.assertTrue(self.dialog.done.isEnabled())
        self.assertTrue(self.dialog.rows["colosseum"][1].isEnabled())
        self.assertIn("Offline test", self.dialog.status.text())

    def test_reopening_after_cancel_does_not_close_the_next_install(self):
        attempts = []

        def install(_store, _game, *, cancel, progress, force):
            attempts.append(True)
            if len(attempts) == 1:
                cancel.wait(2)
                if cancel.is_set():
                    raise Cancelled("Opération annulée.")
            return {}

        with patch("orre_randomizer.hd_packs.PackStore.install_game", install):
            self.dialog.show()
            self.dialog.install("colosseum")
            self.wait_for(lambda: len(attempts) == 1)
            self.dialog.close()
            self.wait_for(lambda: self.dialog.thread is None and not self.dialog.isVisible())
            self.dialog.show()
            self.dialog.install("colosseum")
            self.wait_for(lambda: self.dialog.thread is None)
            self.assertEqual(len(attempts), 2)
            self.assertTrue(self.dialog.isVisible())
            self.assertTrue(self.dialog.done.isEnabled())

    def test_neutral_download_details_have_a_charcoal_field(self):
        self.dialog.show()
        for show in (self.window.show_colosseum, self.window.show_xd, self.window.show_home):
            show()
            self.dialog.details.ensurePolished()
            for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Window,
                         QPalette.ColorRole.ToolTipBase):
                self.assertEqual(self.dialog.palette().color(role).name(), "#191b1e")
            self.assertEqual(self.dialog.details.palette().color(QPalette.ColorRole.Base).name(), "#191b1e")
        self.assertEqual(self.window.palette().color(QPalette.ColorRole.ToolTipBase).name(), "#191b1e")

    def test_destroyed_pack_dialog_does_not_break_later_language_changes(self):
        from PySide6.QtWidgets import QLabel
        targets = [self.dialog, *self.dialog.findChildren(QLabel)]
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(any(getattr(setter, "__self__", None) is target
                             for setter, _ in self.window._text_bindings for target in targets))
        self.window.language_combo.setCurrentIndex(self.window.language_combo.findData("fr"))
        self.window.retranslate()
        replacement = PackDialog(self.window)
        self.dialog = replacement
        replacement.show()
        self.assertEqual(replacement.windowTitle(), self.window.text("Packs HD"))


if __name__ == "__main__":
    unittest.main()
