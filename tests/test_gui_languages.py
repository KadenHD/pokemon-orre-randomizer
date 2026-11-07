"""Real Qt controls, settings persistence and language changes during a job."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from orre_randomizer.gui import MainWindow
except ImportError:
    MainWindow = None

from orre_randomizer.i18n import CATALOGS, LANGUAGES, Message, translate
from orre_randomizer.options import Options
from orre_randomizer.profiles import profile_data
from orre_randomizer.service import Cancelled, UserError


@unittest.skipIf(MainWindow is None, "requires optional Qt desktop dependencies")
class GuiLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.settings_path = str(Path(self.folder.name) / "preferences.ini")
        settings = QSettings(self.settings_path, QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = self.make_window(["fr-FR"])

    def make_window(self, tags):
        return MainWindow(settings=QSettings(self.settings_path, QSettings.Format.IniFormat),
                          system_languages=tags)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.folder.cleanup()

    def select_language(self, language):
        self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))

    def test_first_launch_follows_system_and_unsupported_language_uses_english(self):
        self.assertEqual(self.window.language, "fr")
        self.assertEqual(self.window.language_combo.currentData(), "system")
        self.assertEqual(self.window.language_combo.itemText(0), "Système (Français)")
        self.window.close()
        self.window = self.make_window(["ko-KR"])
        self.assertEqual(self.window.language, "en")
        self.assertEqual(self.window.source_button.text(), "Browse…")
        self.assertEqual(self.window.language_combo.itemText(0), "System (English)")

    def test_japanese_system_language_and_manual_preference_persist(self):
        self.window.close()
        self.window = self.make_window(["ja-JP", "en-US"])
        self.assertEqual(self.window.language, "ja")
        self.assertEqual(self.window.locale().name(), "ja_JP")
        self.assertEqual(self.window.language_combo.itemText(0), "自動（日本語）")
        self.assertEqual(self.window.source_button.text(), "参照…")
        self.assertEqual(self.window.next_button.text(), "次へ")
        self.assertIsNotNone(self.window._qt_translator)
        self.select_language("ja")
        self.window.close()
        self.window = self.make_window(["fr-FR"])
        self.assertEqual(self.window.language, "ja")
        self.assertEqual(self.window.language_combo.currentData(), "ja")
        self.select_language("system")
        self.assertEqual(self.window.language, "fr")

    def test_japanese_switch_keeps_profile_paths_format_and_category(self):
        self.window.seed.setText("星/{seed}/🌟")
        self.window.source.setText("C:/日本語/{source}/original.rvz")
        self.window.destination.setText("C:/保存/{out}/新しい.iso")
        self.window.sync_format()
        self.window.tool.setText("C:/Dolphin/DolphinTool.exe")
        self.window.rule_fields["trainer_level_multiplier"].setValue(1.25)
        self.window.rule_nav.setCurrentRow(4)
        expected = profile_data(self.window.seed.text(), self.window.current_options())
        paths = [field.text() for field in (self.window.source, self.window.destination, self.window.tool)]
        self.select_language("ja")
        self.assertEqual(profile_data(self.window.seed.text(), self.window.current_options()), expected)
        self.assertEqual([field.text() for field in (self.window.source, self.window.destination, self.window.tool)], paths)
        self.assertEqual(self.window.format.currentText(), "ISO")
        self.assertEqual(self.window.rule_nav.currentRow(), 4)
        self.assertEqual(self.window.rule_checks["starter_umbreon"].text(), "最初の1匹目を変更")
        self.assertEqual(self.window.rule_fields["moves_mode"].currentText(), "適性に合わせる")
        self.assertEqual(self.window.create_button.text(), "ROMを作成")

    def test_missing_pack_does_not_restore_unavailable_music_or_report_an_error(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        preferences = QSettings(self.settings_path, QSettings.Format.IniFormat)
        preferences.setValue("interface/music", True)
        preferences.sync()
        with patch("orre_randomizer.resources.bundle_root", return_value=Path(self.folder.name)/"missing-pack"):
            self.window = self.make_window(["fr-FR"])
        self.assertFalse(self.window.music_toggle.isEnabled())
        self.assertFalse(self.window.music_toggle.isChecked())
        self.assertFalse(self.window.sound_toggle.isEnabled())
        self.assertEqual(self.window.status.text(), "Choisissez la ROM d’origine.")

    def test_manual_choice_persists_and_returning_to_system_removes_override(self):
        self.select_language("en")
        self.window.close()
        self.window = self.make_window(["fr-FR"])
        self.assertEqual(self.window.language, "en")
        self.assertEqual(self.window.language_combo.currentData(), "en")
        self.select_language("system")
        self.window.close()
        self.window = self.make_window(["fr-CA"])
        self.assertEqual(self.window.language, "fr")
        self.assertEqual(self.window.language_combo.currentData(), "system")

    def test_switch_preserves_every_rule_path_seed_category_and_progress(self):
        self.window.seed.setText("étoile/{seed}/🌟")
        self.window.source.setText("C:/étoile/{source}/original.iso")
        self.window.destination.setText("C:/étoile/{out}/new.rvz")
        self.window.tool.setText("C:/Dolphin/DolphinTool.exe")
        self.window.rule_nav.setCurrentRow(4)
        self.window.rule_fields["trainer_level_multiplier"].setValue(1.25)
        self.window.rule_fields["boss_shadow_power_mode"].setCurrentIndex(2)
        self.window.advanced_toggle.setChecked(True)
        options = self.window.current_options()
        profile = profile_data(self.window.seed.text(), options)
        values = [widget.text() for widget in (self.window.seed, self.window.source, self.window.destination, self.window.tool)]
        message = Message("Boutiques : étape {number}/5…", number=3)
        self.window.on_progress(43, message)
        self.select_language("en")
        self.assertEqual(self.window.current_options(), options)
        self.assertEqual(profile_data(self.window.seed.text(), self.window.current_options()), profile)
        self.assertEqual([widget.text() for widget in (self.window.seed, self.window.source, self.window.destination, self.window.tool)], values)
        self.assertEqual(self.window.rule_nav.currentRow(), 4)
        self.assertTrue(self.window.advanced_toggle.isChecked())
        self.assertEqual(self.window.progress_bar.value(), 43)
        self.assertEqual(self.window.status.text(), "Shops: step 3/5…")
        self.assertEqual(self.window.log.toPlainText(), "Shops: step 3/5…")
        self.assertEqual(self.window.rule_fields["boss_shadow_power_mode"].currentData(), "free")
        self.assertEqual(self.window.rule_fields["boss_shadow_power_mode"].currentText(), "No power matching")
        self.assertEqual(self.window.rule_checks["starter_umbreon"].text(), "Replace the first starter")
        self.assertIn("1.25", self.window.rule_fields["trainer_level_multiplier"].text())
        self.select_language("fr")
        self.assertEqual(self.window.status.text(), str(message))
        self.assertIn("1,25", self.window.rule_fields["trainer_level_multiplier"].text())

    def test_every_bound_ui_text_is_rendered_and_small_windows_keep_actions_visible(self):
        for language in LANGUAGES:
            self.select_language(language)
            self.window.resize(680, 540)
            self.window.show()
            self.app.processEvents()
            self.assertTrue(self.window.next_button.isVisible())
            self.assertTrue(self.window.language_combo.isVisible())
            self.assertGreater(self.window.settings.height(), 0)
            for item in self.window.rule_fields.values():
                self.assertTrue(item.accessibleName())
                self.assertTrue(item.toolTip())
            for _, source in self.window._text_bindings:
                self.assertIn(source.template if isinstance(source, Message) else source, CATALOGS["en"])
            # Every explanatory paragraph is checked, including dynamically
            # created category descriptions that source AST scans cannot see.
            self.assertTrue(self.window.report_rom_status.isHidden())
            bound_text = {translate(source, language) for _, source in self.window._text_bindings}
            allowed = set(CATALOGS[language].values() if language != "fr" else CATALOGS["en"]) | bound_text
            for label in self.window.findChildren(QLabel):
                if label.objectName() == "note" and label not in (self.window.report_rom_status,
                                                                 self.window.xd.report_rom_status):
                    self.assertIn(label.text(), allowed)

    def test_all_six_languages_available_without_rom_and_keep_configuration(self):
        self.window.seed.setText("étoile/{seed}/🌟")
        self.window.rule_fields["trainer_level_multiplier"].setValue(1.25)
        self.window.rule_fields["boss_shadow_power_mode"].setCurrentIndex(2)
        self.window.rule_nav.setCurrentRow(4)
        expected = profile_data(self.window.seed.text(), self.window.current_options())
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.select_language(language)
                self.assertEqual(self.window.language, language)
                self.assertEqual(self.window.locale().language().name.lower(),
                                 {"fr": "french", "en": "english", "de": "german", "es": "spanish",
                                  "it": "italian", "ja": "japanese"}[language])
                if language != "en":
                    self.assertIsNotNone(self.window._qt_translator)
                self.assertEqual(self.window.source.text(), "")
                self.assertEqual(self.window.rule_nav.currentRow(), 4)
                self.assertEqual(profile_data(self.window.seed.text(), self.window.current_options()), expected)
                self.assertEqual(self.window.rule_fields["trainer_level_multiplier"].value(), 1.25)
                self.window.close()
                self.window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.window = self.make_window(["ko-KR"])
                self.assertEqual(self.window.language, language)
                # Restore the form for the next switch; only the language is persisted.
                self.window.seed.setText("étoile/{seed}/🌟")
                self.window.rule_fields["trainer_level_multiplier"].setValue(1.25)
                self.window.rule_fields["boss_shadow_power_mode"].setCurrentIndex(2)
                self.window.rule_nav.setCurrentRow(4)

    def test_errors_cancellation_and_success_retranslate_without_losing_result(self):
        self.window.start()
        self.select_language("en")
        self.assertEqual(self.window.status.text(), "Choose the original ROM and where to save the new ROM.")
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / "profile.json"
            invalid.write_text("{}", encoding="utf-8")
            self.window.import_profile(invalid)
        self.assertIn("Import failed: This file is not a supported", self.window.status.text())
        self.window.show_error(Cancelled("Création annulée. Aucun fichier de sortie n'a été conservé."), True)
        self.assertEqual(self.window.status.text(), "Creation cancelled. No output file was kept.")
        report = {"output": "C:/étoile/{seed}/final.iso"}
        self.window.succeeded(report)
        self.select_language("fr")
        self.assertIs(self.window.result, report)
        self.assertIn(report["output"], self.window.status.text())
        self.assertTrue(self.window.open_report.isHidden() is False)

    def test_file_dialog_captions_and_filters_follow_the_manual_language(self):
        self.select_language("en")
        with patch("orre_randomizer.gui.QFileDialog.getOpenFileName", return_value=("", "")) as dialog:
            self.window.choose_source()
            self.assertEqual(dialog.call_args.args[1], "Choose the original ROM")
            self.assertEqual(dialog.call_args.args[3], "GameCube ROM (*.iso *.rvz)")
        with patch("orre_randomizer.gui.QFileDialog.getSaveFileName", return_value=("", "")) as dialog:
            self.window.choose_destination()
            self.assertEqual(dialog.call_args.args[1], "Choose where to save the ROM")
            self.assertEqual(dialog.call_args.args[3], "ISO image (*.iso)")

    def test_busy_worker_keeps_running_while_language_changes(self):
        started, release = threading.Event(), threading.Event()
        source = Path(self.folder.name) / "input.iso"
        source.write_bytes(b"private test fixture")
        destination = Path(self.folder.name) / "output.iso"
        self.window.source.setText(str(source))
        self.window.destination.setText(str(destination))
        def job(**arguments):
            arguments["progress"](23, Message("Boutiques : étape {number}/5…", number=2))
            started.set()
            if not release.wait(3):
                raise RuntimeError("test did not release worker")
            arguments["progress"](99, "Enregistrement de la ROM et du rapport…")
            return {"output": str(destination)}
        def until(predicate):
            deadline = time.monotonic() + 4
            while not predicate() and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertTrue(predicate())
        with patch("orre_randomizer.gui.randomize", side_effect=job):
            try:
                self.window.start()
                until(lambda: started.is_set() and self.window.progress_bar.value() == 23)
                self.assertTrue(self.window.busy)
                self.assertFalse(self.window.settings.isEnabled())
                self.assertTrue(self.window.language_combo.isEnabled())
                self.select_language("en")
                self.assertEqual(self.window.status.text(), "Shops: step 2/5…")
                self.assertFalse(self.window.create_button.isEnabled())
                self.select_language("ja")
                self.assertEqual(self.window.status.text(), "ショップを処理中：2/5…")
                self.assertTrue(self.window.busy)
                self.select_language("en")
            finally:
                release.set()
                until(lambda: not self.window.busy)
        self.assertEqual(self.window.status.text(), "ROM created and verified.\n" + str(destination))
        self.assertIn("Saving the ROM and report…", self.window.log.toPlainText())


if __name__ == "__main__":
    unittest.main()
