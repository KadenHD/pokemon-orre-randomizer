"""Qt state tests: errors remain recoverable, controls fit a small window."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from pathlib import Path
import tempfile
try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtWidgets import QApplication
    from orre_randomizer.gui import MainWindow, recommended_preset
except ImportError:
    MainWindow = None


@unittest.skipIf(MainWindow is None, "requires optional Qt desktop dependencies")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.preferences_dir = tempfile.TemporaryDirectory()
        settings = QSettings(str(Path(self.preferences_dir.name) / "settings.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = MainWindow(settings=settings, system_languages=["fr-FR"])

    def tearDown(self):
        from PySide6.QtTest import QTest
        self.window.cancel_preview()
        for _ in range(100):
            if self.window.preview_thread is None:
                break
            QTest.qWait(10)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.preferences_dir.cleanup()

    def test_empty_form_reports_recoverable_error(self):
        self.window.start()
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.create_button.isEnabled())
        self.assertIn("Choisissez", self.window.status.text())

    def test_return_home_leaves_game_cards_neutral_until_tab(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        window = self.window
        window.show_home()
        window.show()
        self.app.processEvents()
        for card, workspace, back in (
            (window.open_colosseum, window.colosseum, window.back_button),
            (window.open_xd, window.xd, window.xd.home_button),
        ):
            with self.subTest(game=card.text()):
                QTest.mouseClick(card, Qt.MouseButton.LeftButton)
                self.assertIs(window.game_views.currentWidget(), workspace)
                QTest.mouseClick(back, Qt.MouseButton.LeftButton)
                self.assertIs(window.game_views.currentWidget(), window.home)
                self.assertFalse(window.open_colosseum.hasFocus())
                self.assertFalse(window.open_xd.hasFocus())
                QTest.keyClick(window.focusWidget(), Qt.Key.Key_Tab)
                self.assertTrue(window.open_colosseum.hasFocus())

    def test_xd_theme_and_rom_format_follow_game_selection(self):
        from unittest.mock import patch

        window = self.window
        window.show_home()
        self.assertEqual(window.home.colosseum.logo.width(), 1280)
        self.assertEqual(window.home.xd.logo.width(), 1280)
        window.open_xd.click()
        xd = window.xd
        self.assertIs(window.game_views.currentWidget(), xd)
        self.assertTrue(window.surface.xd)
        self.assertEqual(window.logo.isHidden(), window.xd_logo.isNull())
        self.assertFalse(window.profile_menu.isHidden())
        self.assertEqual(xd.pages.currentIndex(), 0)
        xd.create_button.click()
        self.assertEqual(xd.pages.currentIndex(), 0)
        xd.source.setText("C:/original.RVZ")
        self.assertEqual(xd.format.currentText(), "RVZ")
        self.assertEqual(Path(xd.destination.text()).name, "xd-randomized.rvz")
        self.assertFalse(xd.source_conversion.isHidden())
        self.assertFalse(xd.tool_block.isHidden())
        xd.source_conversion.click()
        self.assertTrue(xd.tool_block.isHidden())
        self.assertFalse(xd.output_tool_block.isHidden())
        xd.tool.setText("C:/DolphinTool.exe")
        self.assertEqual(xd.output_tool.text(), xd.tool.text())
        xd.format.setCurrentText("ISO")
        self.assertTrue(xd.tool_block.isHidden())
        self.assertTrue(xd.output_tool_block.isHidden())
        xd.source.setText("C:/original.iso")
        self.assertTrue(xd.tool_block.isHidden())
        xd.rules["randomize_shadows"].setChecked(False)
        self.assertFalse(xd.rules["unique_shadow_families"].isEnabled())

        with patch.object(xd, "validate_source"):
            xd.create_button.click()
            self.assertEqual(xd.pages.currentIndex(), 1)
            xd.create_button.click()
            self.assertEqual(xd.pages.currentIndex(), 2)
        window.language_combo.setCurrentIndex(window.language_combo.findData("ja"))
        self.assertEqual(xd.create_button.text(), "ROMを作成")
        self.assertFalse(xd.rules["randomize_shadows"].isChecked())
        window.show_home()
        window.open_colosseum.click()
        self.assertIs(window.game_views.currentWidget(), window.colosseum)
        self.assertFalse(window.surface.xd)
        self.assertEqual(window.source.text(), "")
        self.assertFalse(window.profile_menu.isHidden())

    def test_xd_creation_uses_its_options_in_the_shared_worker(self):
        from unittest.mock import patch
        from PySide6.QtCore import QThread
        from PySide6.QtTest import QTest

        window = self.window
        window.show_xd()
        xd = window.xd
        source = Path(self.preferences_dir.name) / "original.iso"
        source.write_bytes(b"path validation fixture")
        xd.source.setText(str(source))
        xd.rules["randomize_shadows"].setChecked(False)
        captured = {}

        def fake_randomize(**arguments):
            captured.update(arguments, thread=QThread.currentThread())
            arguments["progress"](50, "Création de la nouvelle ISO…")
            return {"output": str(arguments["destination"])}

        with patch("orre_randomizer.gui.randomize", side_effect=fake_randomize):
            xd.start()
            for _ in range(100):
                if not window.busy:
                    break
                QTest.qWait(10)

        self.assertFalse(window.busy)
        self.assertIsNot(captured["thread"], self.app.thread())
        self.assertFalse(captured["xd_options"].randomize_shadows)
        self.assertFalse(captured["xd_options"].unique_shadow_families)
        self.assertEqual(xd.progress.value(), 100)
        self.assertTrue(xd.create_button.isEnabled())
        self.assertIsNone(window.result)

    def test_xd_advanced_search_and_reset_use_the_selected_category(self):
        window = self.window
        window.resize(680, 540)
        window.show_xd()
        window.show()
        xd = window.xd
        xd.step = 1
        xd.pages.setCurrentIndex(1)
        xd.set_advanced_mode(True)
        self.app.processEvents()
        panel = xd.rule_panel
        self.assertTrue(panel.categories.isHidden())
        self.assertFalse(panel.selector.isHidden())
        xd.rules["randomize_shadows"].setChecked(False)
        xd.rules["randomize_starter"].setChecked(False)

        panel.search.setText("remplacer le premier starter")
        self.assertEqual(panel.content.currentIndex(), 1)
        panel.search.returnPressed.emit()
        self.assertEqual(panel.content.currentIndex(), 0)
        self.assertEqual(xd.rule_groups[panel.categories.currentRow()], "Starters et cadeaux")
        panel.reset.click()
        self.assertTrue(xd.rules["randomize_starter"].isChecked())
        self.assertFalse(xd.rules["randomize_shadows"].isChecked())

    def test_xd_preview_keeps_the_same_result_across_language_changes(self):
        from unittest.mock import patch
        from PySide6.QtCore import QThread, Qt
        from PySide6.QtTest import QTest

        window = self.window
        window.show_xd()
        xd = window.xd
        source = Path(self.preferences_dir.name) / "original.iso"
        source.write_bytes(b"preview fixture")
        xd.source.setText(str(source))
        started_on = []
        summary = {
            "starter": {"original": 133, "species": 283, "level": 10},
            "national_ids": {"283": 258},
            "decks": {"Story": {"shadows": [{"shadow_id": 2, "original": 37, "species": 25, "level": 21}]}},
            "poke_spots": [{"spot": "rock", "slot": 3, "original": 332, "species": 25,
                            "levels": [10, 20], "chance": 15}],
            "gifts": [{"key": "duking-trapinch", "required_species": 25, "original": 25, "species": 283, "level": 20},
                      {"key": "hordel-trade", "required_species": 25, "required_evolution": 26,
                       "original": 239, "species": 283, "level": 20}],
        }

        def fake_preview(**arguments):
            started_on.append(QThread.currentThread())
            arguments["progress"](20, "Application des réglages…")
            return summary

        with patch("orre_randomizer.preview.preview_xd", side_effect=fake_preview) as calculate:
            xd.start_preview()
            for _ in range(100):
                if window.preview_thread is None:
                    break
                QTest.qWait(10)
            self.assertFalse(window.busy)
            self.assertIsNot(started_on[0], self.app.thread())
            self.assertTrue(xd.preview_button.isHidden())
            self.assertIn("Gobou", xd.preview_starter.text())
            self.assertIn("Évoli → Gobou", xd.preview_portrait.toolTip())
            xd.encounter_tabs.setCurrentIndex(2)
            self.assertEqual(xd.preview_details.topLevelItemCount(), 2)
            duking, hordel = (xd.preview_details.topLevelItem(i) for i in range(2))
            for row in (duking, hordel):
                for column in range(2):
                    self.assertEqual(row.textAlignment(column), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.assertIn("Gobou · Niv. 20\nDoking demande Pikachu · Roche\n15 % des rencontres", duking.text(1))
            self.assertIn("Échange contre Togepi ou Togetic", hordel.text(0))
            self.assertIn("\nÉchange contre Pikachu ou Raichu", hordel.text(1))
            window.language_combo.setCurrentIndex(window.language_combo.findData("en"))
            self.assertEqual(xd.encounter_tabs.currentIndex(), 2)
            self.assertIn("Duking wants Pikachu · Rock\n15% of encounters", xd.preview_details.topLevelItem(0).text(1))
            self.assertIn("Trade for Pikachu or Raichu", xd.preview_details.topLevelItem(1).text(1))
            self.assertIn("Mudkip", xd.preview_starter.text())
            xd.start_preview()
            calculate.assert_called_once()

        xd.seed.setText("changed")
        self.assertIsNone(xd.preview_result)
        self.assertEqual(xd.preview_starter.text(), "?")
        self.assertTrue(xd.starter_details.isHidden())
        self.assertFalse(xd.preview_button.isHidden())
        self.assertIsNone(window.result)
        self.assertEqual(list(source.parent.glob("*.iso")), [source])

    def test_xd_preview_keeps_gui_responsive_during_thread_cleanup(self):
        from threading import Event
        from unittest.mock import patch
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtTest import QTest

        window = self.window
        window.show_xd()
        source = Path(self.preferences_dir.name) / "original.iso"
        source.write_bytes(b"preview fixture")
        window.xd.source.setText(str(source))
        allow_result = Event()
        release_cleanup = Event()
        released_from_gui = []
        timer = QTimer(window)
        timer.setSingleShot(True)
        timer.timeout.connect(release_cleanup.set)

        def fake_preview(**_arguments):
            allow_result.wait(2)
            return {"starter": {"original": 133, "species": 25, "level": 10}}

        def finish_cleanup():
            released_from_gui.append(release_cleanup.wait(2))

        with patch("orre_randomizer.preview.preview_xd", side_effect=fake_preview):
            window.xd.start_preview()
            try:
                thread = window.preview_thread
                thread.finished.connect(timer.start, Qt.ConnectionType.QueuedConnection)
                thread.finished.connect(finish_cleanup, Qt.ConnectionType.DirectConnection)
            finally:
                allow_result.set()
            for _ in range(300):
                if window.preview_thread is None:
                    break
                QTest.qWait(10)

        self.assertEqual(released_from_gui, [True])
        self.assertIsNone(window.preview_thread)
        self.assertIsNotNone(window.xd.preview_result)

    def test_xd_preview_ignores_a_late_result_after_editing_the_seed(self):
        from unittest.mock import patch
        from PySide6.QtTest import QTest

        window = self.window
        window.show_xd()
        xd = window.xd
        source = Path(self.preferences_dir.name) / "original.iso"
        source.write_bytes(b"preview fixture")
        xd.source.setText(str(source))
        observed_cancellation = []

        def fake_preview(**arguments):
            observed_cancellation.append(arguments["cancel"].wait(2))
            return {"starter": {"original": 133, "species": 25, "level": 10}}

        with patch("orre_randomizer.preview.preview_xd", side_effect=fake_preview):
            xd.start_preview()
            self.assertTrue(xd.preview_running)
            self.assertFalse(window.busy)
            xd.step = 2
            xd.refresh_navigation()
            self.assertFalse(xd.create_button.isEnabled())
            xd.seed.setText("changed while loading")
            for _ in range(100):
                if window.preview_thread is None:
                    break
                QTest.qWait(10)

        self.assertEqual(observed_cancellation, [True])
        self.assertFalse(window.busy)
        self.assertIsNone(xd.preview_result)
        self.assertEqual(xd.preview_starter.text(), "?")
        self.assertTrue(xd.starter_details.isHidden())
        self.assertFalse(xd.preview_button.isHidden())
        self.assertTrue(xd.create_button.isEnabled())

    def test_shiny_switch_gates_rate_and_preserves_values_across_languages(self):
        rate = self.window.rule_fields["shiny_chance_percent"]
        toggle = self.window.rule_checks["custom_shinies"]
        self.assertTrue(toggle.isChecked())
        self.assertEqual(rate.value(), 5.0)
        rate.setValue(3.125)
        for language in ("en", "de", "es", "it", "ja", "fr"):
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.assertTrue(rate.isEnabled())
            self.assertEqual(self.window.current_options().shiny_chance_percent, 3.125)
            self.assertTrue(self.window.current_options().custom_shinies)
        toggle.setChecked(False)
        self.assertFalse(rate.isEnabled())
        self.assertEqual(rate.value(), 3.125)

    def test_selected_shiny_category_remains_visible_after_small_window_and_language_change(self):
        self.window.step = 1
        self.window.set_advanced_mode(True)
        self.window.refresh_navigation()
        self.window.rule_nav.setCurrentRow(self.window.rule_nav.count() - 1)
        self.window.show()
        self.window.resize(680, 540)
        for language in ("de", "ja"):
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.app.processEvents()
            self.app.processEvents()
            nav = self.window.rule_nav
            selected = nav.visualItemRect(nav.currentItem())
            self.assertGreaterEqual(selected.top(), 0)
            self.assertLessEqual(selected.bottom(), nav.viewport().height())

    def test_event_access_switch_gates_fields_and_keeps_choices_across_languages(self):
        values = {"event_pikachu_purifications": 0, "event_celebi_purifications": 48,
                  "event_pikachu_level": 100, "event_celebi_level": 1}
        toggle = self.window.rule_checks["accessible_event_gifts"]
        self.assertTrue(toggle.isChecked())
        for name, value in values.items():
            self.assertTrue(self.window.rule_fields[name].isEnabled())
            self.window.rule_fields[name].setValue(value)
        for enabled in (False, True):
            toggle.setChecked(enabled)
            for language in ("en", "de", "es", "it", "ja", "fr"):
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
                for name, value in values.items():
                    self.assertEqual(self.window.rule_fields[name].isEnabled(), enabled)
                    self.assertEqual(self.window.rule_fields[name].value(), value)

    def test_safe_defaults_and_rvz_configuration(self):
        from orre_randomizer.options import Options
        self.assertEqual(len(self.window.rule_fields), 83)
        self.assertEqual(self.window.current_options(), recommended_preset())
        self.window.source.setText("/example/source.iso")
        self.window.suggest_destination()
        self.assertNotEqual(self.window.destination.text(), self.window.source.text())
        self.window.format.setCurrentText("RVZ")
        self.assertTrue(self.window.destination.text().endswith(".rvz"))
        self.assertTrue(self.window.advanced_toggle.isHidden())
        self.assertTrue(self.window.advanced.isHidden())
        self.assertFalse(self.window.output_conversion.isHidden())
        self.window.tool.setText("C:/Dolphin/DolphinTool.exe")
        self.assertEqual(self.window.output_tool.text(), self.window.tool.text())
        self.window.output_tool.setText("C:/Other/DolphinTool.exe")
        self.assertEqual(self.window.tool.text(), self.window.output_tool.text())
        self.window.format.setCurrentText("ISO")
        self.assertTrue(self.window.output_conversion.isHidden())
        self.window.format.setCurrentText("RVZ")
        self.assertEqual(self.window.output_tool.text(), "C:/Other/DolphinTool.exe")

    def test_conversion_field_follows_source_extension_and_preserves_tool(self):
        self.assertTrue(self.window.advanced_toggle.isHidden())
        self.assertTrue(self.window.advanced.isHidden())
        self.window.tool.setText("C:/Dolphin/DolphinTool.exe")
        for value, visible in (("C:/partie.RVZ", True), ("C:/partie.iso", False),
                               ("C:/partie.rvz.iso", False), ("", False),
                               ("  C:/partie.rvz  ", True), ("C:/partie.txt", False)):
            with self.subTest(source=value):
                self.window.source.setText(value)
                self.assertEqual(not self.window.advanced_toggle.isHidden(), visible)
                self.assertEqual(not self.window.advanced.isHidden(), visible)
                self.assertEqual(self.window.tool.text(), "C:/Dolphin/DolphinTool.exe")

    def test_browsing_or_dropping_rom_updates_conversion_field(self):
        from unittest.mock import patch
        from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
        from PySide6.QtGui import QDropEvent
        with patch("orre_randomizer.gui.QFileDialog.getOpenFileName", return_value=("C:/partie.rvz", "")):
            self.window.choose_source()
        self.assertFalse(self.window.advanced.isHidden())
        for filename in ("partie.iso", "partie.RVZ", "autre.iso"):
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(Path(self.preferences_dir.name)/filename))])
            event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.window.dropEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(not self.window.advanced.isHidden(), filename.lower().endswith(".rvz"))
            self.assertEqual(self.window.format.currentText(), Path(filename).suffix[1:].upper())
            self.assertEqual(Path(self.window.destination.text()).suffix, Path(filename).suffix.lower())

    def test_output_format_defaults_to_each_new_source_and_keeps_custom_basename(self):
        self.window.destination.setText(str(Path(self.preferences_dir.name)/"ma-partie.iso"))
        for extension in ("RVZ", "iso", "rvz"):
            with self.subTest(extension=extension):
                self.window.source.setText("  C:/original." + extension + "  ")
                self.assertEqual(self.window.format.currentText(), extension.upper())
                self.assertEqual(Path(self.window.destination.text()).name, "ma-partie." + extension.lower())

    def test_manual_output_format_survives_suggestions_and_step_navigation(self):
        source = Path(self.preferences_dir.name)/"original.rvz"
        source.write_bytes(b"synthetic path fixture; no conversion is run")
        tool = source.with_name("DolphinTool.exe")
        tool.write_bytes(b"synthetic converter path; never executed")
        self.window.source.setText(str(source))
        self.window.tool.setText(str(tool))
        self.window.suggest_destination()
        self.assertEqual(self.window.format.currentText(), "RVZ")
        self.assertTrue(self.window.destination.text().endswith(".rvz"))
        self.window.format.setCurrentText("ISO")
        self.window.suggest_destination()
        self.window.go_step(1)
        self.window.go_step(0)
        self.window.go_step(1)
        self.assertEqual(self.window.step, 1)
        self.assertEqual(self.window.format.currentText(), "ISO")
        self.assertTrue(self.window.destination.text().endswith(".iso"))

    def test_iso_to_rvz_requires_tool_in_output_field_without_opening_dialog(self):
        from unittest.mock import patch
        source = Path(self.preferences_dir.name)/"source.iso"
        source.write_bytes(b"synthetic input, no worker should start")
        self.window.source.setText(str(source))
        self.window.destination.setText(str(source.with_name("output.rvz")))
        self.window.tool.clear()
        self.window.step = 2
        self.window.refresh_navigation()
        self.window.show()
        with patch("orre_randomizer.gui.QFileDialog.getOpenFileName") as dialog:
            self.window.start()
        dialog.assert_not_called()
        self.assertTrue(self.window.output_tool.isVisible())
        self.assertFalse(self.window.busy)
        self.assertIsNone(self.window.thread)
        self.assertTrue(self.window.advanced_toggle.isHidden())
        self.assertTrue(self.window.advanced.isHidden())
        self.assertIn("DolphinTool", self.window.status.text())
        self.assertFalse(source.with_name("output.rvz").exists())

    def test_none_preset_and_shadow_dependency(self):
        from orre_randomizer.options import Options
        self.window.set_options(Options.none())
        self.assertEqual(self.window.current_options(), Options.none())
        self.assertFalse(self.window.rule_checks["unique_shadows"].isEnabled())
        self.assertIn("copie", self.window.create_button.text())
        self.window.set_options(Options())
        self.assertEqual(self.window.current_options(), Options())
        self.assertTrue(self.window.rule_checks["unique_shadows"].isEnabled())

    def test_individual_starter_can_be_kept(self):
        self.window.rule_checks["starter_umbreon"].setChecked(False)
        options = self.window.current_options()
        self.assertFalse(options.starter_umbreon)
        self.assertTrue(options.starter_espeon)

    def test_numeric_and_mode_controls_are_bound(self):
        self.window.rule_fields["trainer_level_multiplier"].setValue(1.25)
        self.window.rule_fields["minimum_catch_rate"].setValue(100)
        control = self.window.rule_fields["moves_mode"]
        control.setCurrentIndex(control.findData("chaos"))
        options = self.window.current_options()
        self.assertEqual(options.trainer_level_multiplier, 1.25)
        self.assertEqual(options.minimum_catch_rate, 100)
        self.assertEqual(options.moves_mode, "chaos")
        self.assertEqual(self.window.rule_nav.count(), 15)
        self.assertTrue(all(not self.window.rule_nav.item(index).icon().isNull()
                            for index in range(self.window.rule_nav.count())))

    def test_small_window_keeps_primary_action_visible(self):
        self.window.resize(680, 540)
        self.window.show()
        self.app.processEvents()
        self.assertEqual((self.window.width(), self.window.height()), (680, 540))
        self.assertTrue(self.window.next_button.isVisible())
        self.assertGreater(self.window.next_button.width(), 80)
        self.window.step = 2
        self.window.refresh_navigation()
        self.app.processEvents()
        self.assertTrue(self.window.create_button.isVisible())
        self.assertFalse(self.window.cancel_button.isEnabled())

    def test_profile_import_export_restores_rules_seed_and_preserves_paths(self):
        from orre_randomizer.options import Options
        original = self.window.current_options()
        self.window.source.setText("/user/original.iso")
        self.window.destination.setText("/user/randomized.iso")
        self.window.seed.setText("partie-à-partager")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shared.json"
            self.window.export_profile(path)
            self.assertIn("enregistré", self.window.status.text())
            self.window.set_options(Options.none())
            self.window.seed.setText("another-seed")
            self.window.import_profile(path)
        self.assertEqual(self.window.current_options(), original)
        self.assertEqual(self.window.seed.text(), "partie-à-partager")
        self.assertEqual(self.window.source.text(), "/user/original.iso")
        self.assertEqual(self.window.destination.text(), "/user/randomized.iso")

    def test_invalid_profile_is_recoverable_and_does_not_change_configuration(self):
        original, seed = self.window.current_options(), self.window.seed.text()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text('{"options":{"starter_umbreon":false}}', encoding="utf-8")
            self.window.import_profile(path)
        self.assertIn("Import impossible", self.window.status.text())
        self.assertEqual(self.window.current_options(), original)
        self.assertEqual(self.window.seed.text(), seed)
        self.assertTrue(self.window.create_button.isEnabled())

    def test_dependencies_disable_without_erasing_starter_and_boss_rules(self):
        self.window.rule_fields["boss_shadow_min_bst"].setValue(450)
        self.window.rule_checks["randomize_shadows"].setChecked(False)
        self.assertFalse(self.window.rule_fields["boss_shadow_min_bst"].isEnabled())
        self.window.rule_checks["randomize_shadows"].setChecked(True)
        self.assertTrue(self.window.rule_fields["boss_shadow_min_bst"].isEnabled())
        self.assertEqual(self.window.current_options().boss_shadow_min_bst, 450)
        for name in ("starter_umbreon", "starter_espeon"):
            self.window.rule_checks[name].setChecked(False)
        self.assertFalse(self.window.rule_fields["starter_balance_pair"].isEnabled())
        self.assertFalse(self.window.rule_fields["starter_stage"].isEnabled())
        self.assertFalse(self.window.rule_fields["starter_three_stage_families"].isEnabled())
        self.window.rule_checks["starter_umbreon"].setChecked(True)
        self.assertTrue(self.window.rule_fields["starter_balance_pair"].isEnabled())
        self.assertTrue(self.window.rule_fields["starter_stage"].isEnabled())
        self.assertTrue(self.window.current_options().starter_three_stage_families)
        self.assertEqual(self.window.rule_fields["starter_stage"].currentData(), "base")

    def test_interface_assets_available_before_selecting_any_rom(self):
        from orre_randomizer.resources import interface_assets
        images, sounds = interface_assets()
        self.assertEqual(self.window.source.text(), "")
        self.assertEqual(self.window.artwork, images)
        self.assertEqual(self.window.audio.paths, sounds)
        if "espeon" in images:
            self.assertFalse(self.window.portraits["espeon"].pixmap().isNull())
        else:
            self.assertTrue(self.window.logo.isHidden())
            self.assertTrue(self.window.cursor_icon.isNull())

    def test_wizard_rejects_missing_rom_and_keeps_actual_step_selected(self):
        self.window.step_buttons[1].click()
        self.assertEqual(self.window.step, 0)
        self.assertEqual([b.isChecked() for b in self.window.step_buttons], [True, False, False])
        self.assertIn("existant", self.window.status.text())

    def test_simple_advanced_preserve_custom_options_and_seed(self):
        from dataclasses import replace
        from orre_randomizer.options import Options
        custom = replace(Options.recommended(), trainer_level_multiplier=1.35, starter_stage="base")
        self.window.set_options(custom)
        self.window.seed.setText("étoile")
        for advanced in (True, False, True):
            self.window.set_advanced_mode(advanced)
            self.assertEqual(self.window.current_options(), custom)
            self.assertEqual(self.window.seed.text(), "étoile")
        self.assertIn("personnalisés", self.window.preset_description.text())
        self.assertFalse(any(button.isChecked() for button, _ in self.window.presets))
        self.window.workspace_tabs.setCurrentIndex(1)
        self.assertEqual(self.window.current_options(), custom)
        self.assertEqual(self.window.workspace_pages.currentIndex(), 1)
        self.window.workspace_tabs.setCurrentIndex(0)
        self.assertEqual(self.window.seed.text(), "étoile")

    def test_wizard_roundtrip_preserves_paths_rules_and_validates_seed(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.iso"
            source.write_bytes(b"synthetic header checked separately")
            self.window.source.setText(str(source))
            self.window.seed.setText("reproducible")
            original = self.window.current_options()
            with patch("orre_randomizer.gui.check_header"):
                self.window.go_step(1)
                self.assertEqual(self.window.step, 1)
                self.window.seed.setText(" ")
                self.window.go_step(2)
                self.assertEqual(self.window.step, 1)
                self.window.seed.setText("reproducible")
                self.window.go_step(2)
                self.assertEqual(self.window.step, 2)
                self.window.go_step(0)
                self.window.go_step(1)
            self.assertEqual(self.window.current_options(), original)
            self.assertEqual(self.window.source.text(), str(source))
            self.assertNotEqual(self.window.source.text(), self.window.destination.text())


if __name__ == "__main__":
    unittest.main()
