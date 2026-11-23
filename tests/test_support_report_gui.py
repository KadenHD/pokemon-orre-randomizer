"""Exercise the diagnostic action and local export without personal state."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtTest import QTest

from orre_randomizer.gui import MainWindow
from orre_randomizer.i18n import CATALOGS, LANGUAGES
from orre_randomizer.support_i18n import ROWS
from orre_randomizer.support_report import operation_snapshot, remember_failure
from orre_randomizer.ui_support_report import SupportReportDialog, show_support_report


class SupportReportGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if os.name == "nt":
            from PySide6.QtGui import QFont, QFontDatabase
            fonts = Path(os.environ.get("SystemRoot", "C:/Windows"))/"Fonts"
            for name in ("segoeui.ttf", "YuGothR.ttc"):
                QFontDatabase.addApplicationFont(str(fonts/name))
            cls.app.setFont(QFont("Segoe UI",10))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        settings = QSettings(str(self.root/"preferences.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music",False); settings.setValue("interface/sounds",False)
        self.window = MainWindow(settings=settings, system_languages=["en"], start_on_home=True,allow_update_checks=False)
        self.dialogs = []

    def tearDown(self):
        deadline = time.monotonic()+8
        while self.window.thread is not None or self.window.preview_thread is not None:
            self.app.processEvents(); QTest.qWait(5)
            self.assertLess(time.monotonic(),deadline)
        for dialog in self.dialogs:
            while dialog.task is not None:
                self.app.processEvents(); QTest.qWait(5)
                self.assertLess(time.monotonic(),deadline)
            dialog.close(); dialog.deleteLater()
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def dialog(self):
        dialog = SupportReportDialog(self.window); self.dialogs.append(dialog)
        dialog.show(); self.app.processEvents()
        return dialog

    def test_translations_and_bounds_in_both_games_all_six_languages(self):
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.app.processEvents()
            self.assertEqual(self.window.language,language)
            for game in ("colosseum","xd"):
                with self.subTest(language=language,game=game):
                    (self.window.show_xd if game=="xd" else self.window.show_colosseum)()
                    dialog = self.dialog()
                    self.assertLessEqual(dialog.layout().minimumSize().height(),dialog.height())
                    self.assertLessEqual(dialog.layout().minimumSize().width(),dialog.width())
                    self.assertEqual(dialog.preview.horizontalScrollBarPolicy(),Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    self.assertFalse(dialog.preview.horizontalScrollBar().isVisible())
                    for control in (dialog.context,dialog.include_seed,dialog.preview,dialog.export,dialog.done):
                        point = control.mapTo(dialog,control.rect().topLeft())
                        self.assertTrue(dialog.rect().contains(point))
                        self.assertTrue(dialog.rect().contains(control.mapTo(dialog,control.rect().bottomRight())))
                    if language != "fr":
                        self.assertTrue(all(key in CATALOGS[language] for key in ROWS))
                    dialog.close()

    def test_last_failure_and_current_settings_are_distinct_and_seed_is_optional(self):
        self.window.show_xd(); owner = self.window.xd
        owner.seed.setText("failed-seed")
        operation_snapshot(owner,"creation")
        remember_failure(owner,OSError("C:/Users/private-player/private-asset"),False)
        owner.seed.setText("current-seed")
        dialog = self.dialog()
        data = json.loads(dialog.preview.toPlainText())
        self.assertEqual(data["game"],"xd"); self.assertEqual(data["seed"],"failed-seed")
        self.assertEqual(data["operation"]["stage"],"creation")
        self.assertNotIn("private-player",dialog.preview.toPlainText())
        dialog.context.setCurrentIndex(1)
        self.assertEqual(json.loads(dialog.preview.toPlainText())["seed"],"current-seed")
        self.assertNotIn("error",json.loads(dialog.preview.toPlainText())["operation"])
        dialog.include_seed.setChecked(False)
        self.assertIsNone(json.loads(dialog.preview.toPlainText())["seed"])

    def test_sensitive_seed_cannot_be_inadvertently_included(self):
        self.window.show_colosseum(); self.window.seed.setText("C:/Users/private-player/seed")
        dialog = self.dialog()
        self.assertFalse(dialog.include_seed.isEnabled() or dialog.include_seed.isChecked())
        self.assertNotIn("private-player",dialog.preview.toPlainText())

    def test_save_uses_actual_reviewed_json_and_refuses_an_existing_file(self):
        self.window.show_colosseum(); self.window.seed.setText("export-test")
        dialog = self.dialog()
        path = self.root/"support.json"
        for attempt in range(2):
            with patch("orre_randomizer.ui_support_report.QFileDialog.getSaveFileName",return_value=(str(path),"JSON (*.json)")):
                dialog.choose_destination()
            deadline = time.monotonic()+5
            while dialog.task is not None:
                self.app.processEvents(); QTest.qWait(5)
                self.assertLess(time.monotonic(),deadline)
            self.assertEqual(json.loads(path.read_text("utf-8")),json.loads(dialog.preview.toPlainText()))
            self.assertTrue(dialog.export.isEnabled())
            if attempt == 0:
                self.assertIn("saved",dialog.status.text())
            else:
                self.assertNotIn("saved",dialog.status.text())

    def test_creation_worker_error_keeps_original_snapshot_on_gui_thread(self):
        self.window.show_xd(); owner = self.window.xd
        owner.seed.setText("worker-seed")
        def failing(**kwargs):
            raise OSError("C:/Users/private-player/a-file")
        self.window.start_worker({"source":Path("selected.iso"),"seed":"worker-seed","xd_options":owner.current_options()},
            owner.on_progress,owner.succeeded,owner.failed,task=failing)
        deadline = time.monotonic()+5
        while self.window.thread is not None:
            self.app.processEvents(); QTest.qWait(5)
            self.assertLess(time.monotonic(),deadline)
        self.assertEqual(owner._support_last_failure["seed"],"worker-seed")
        self.assertNotIn("private-player",json.dumps(owner._support_last_failure))
        self.assertEqual(owner._support_last_failure["operation"]["error"]["kind"],"io")

    def test_known_preview_controller_keeps_its_workspace_context_in_both_games(self):
        for game in ("colosseum","xd"):
            with self.subTest(game=game):
                (self.window.show_xd if game=="xd" else self.window.show_colosseum)()
                owner = self.window.xd if game=="xd" else self.window
                source = self.root/(game+".iso"); source.write_bytes(b"synthetic never decoded")
                owner.source.setText(str(source)); owner.seed.setText("known-worker-seed")
                controller = owner.known_preview
                controller.timer.stop()
                def failing(**kwargs):
                    raise OSError("private error never exported")
                name = "preview_xd_known" if game=="xd" else "preview_known"
                with patch.object(controller,"active",return_value=True), \
                     patch("orre_randomizer.ui_known_preview."+name,side_effect=failing):
                    controller.start()
                    self.assertIs(self.window.preview_owner,controller)
                    self.assertIsNotNone(self.window.preview_thread)
                    deadline = time.monotonic()+5
                    while self.window.preview_thread is not None:
                        self.app.processEvents(); QTest.qWait(5)
                        self.assertLess(time.monotonic(),deadline)
                controller.timer.stop()
                self.assertEqual(owner._support_last_failure["game"],game)
                self.assertEqual(owner._support_last_failure["seed"],"known-worker-seed")
                self.assertEqual(owner._support_last_failure["operation"]["stage"],"preview")
                self.assertNotIn("private error",json.dumps(owner._support_last_failure))

    def test_export_waits_for_any_global_preview_or_report_check(self):
        for owner, attribute in ((self.window,"preview_thread"),(self.window,"report_check"),(self.window.xd,"report_check")):
            with self.subTest(attribute=attribute):
                setattr(owner,attribute,object())
                try:
                    with patch("orre_randomizer.ui_support_report.SupportReportDialog") as dialog:
                        show_support_report(self.window)
                    dialog.assert_not_called()
                finally:
                    setattr(owner,attribute,None)

    def test_modal_pauses_pending_previews_and_report_timers_until_close(self):
        self.window.show_colosseum()
        # Place the empty synthetic workspace on Preview without bypassing any
        # production ROM validation through a made-up disc header.
        self.window.step = 1; self.window.settings.setCurrentIndex(1)
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.show(); self.app.processEvents()
        self.assertTrue(self.window.known_preview.active())
        for owner in (self.window,self.window.xd):
            owner.known_preview.timer.start(10000)
            owner.report_rom_timer.start(10000)
        def inspect_modal():
            self.assertTrue(self.window._support_modal_open)
            for owner in (self.window,self.window.xd):
                self.assertFalse(owner.known_preview.timer.isActive())
                self.assertFalse(owner.report_rom_timer.isActive())
                self.assertFalse(owner.known_preview.active())
                owner.known_preview.start()
            self.assertIsNone(self.window.preview_thread)
        with patch("orre_randomizer.ui_support_report.SupportReportDialog") as dialog:
            dialog.return_value.exec.side_effect = inspect_modal
            show_support_report(self.window)
        self.assertFalse(self.window._support_modal_open)
        self.assertTrue(self.window.known_preview.active())
        for owner in (self.window,self.window.xd):
            self.assertTrue(owner.report_rom_timer.isActive())
            owner.report_rom_timer.stop(); owner.known_preview.timer.stop()


if __name__ == "__main__":
    unittest.main()
