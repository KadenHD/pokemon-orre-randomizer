"""Navigation, usable table height, filtered results and safe native wheels."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import gc

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QSettings, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication, QScrollArea, QScrollBar, QListWidgetItem
    from colosseum_randomizer.gui import MainWindow
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "requires optional Qt desktop dependencies")
class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        settings = QSettings(str(Path(self.folder.name) / "preferences.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = MainWindow(settings=settings, system_languages=["fr-FR"])
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.show()
        self.pump()

    def pump(self):
        for _ in range(3): self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.folder.cleanup()

    def wheel(self, control, delta=120):
        event = QWheelEvent(QPointF(10, 10), QPointF(control.mapToGlobal(QPoint(10, 10))),
                            QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
        self.app.sendEvent(control, event)
        self.pump()

    def test_unfocused_wheel_scrolls_the_form_without_changing_rate(self):
        w = self.window
        w.resize(680, 540)
        w.set_advanced_mode(True)
        w.rule_nav.setCurrentRow(w.rule_nav.count() - 1)
        w.rule_checks["custom_shinies"].setChecked(True)
        self.pump()
        spin = w.rule_fields["shiny_chance_percent"]
        scroll = w.rule_pages.currentWidget()
        scroll.ensureWidgetVisible(spin)
        self.pump()
        w.next_button.setFocus()
        self.pump()
        before, position = spin.value(), scroll.verticalScrollBar().value()
        self.assertFalse(spin.hasFocus())
        self.assertGreater(position, 0)
        self.wheel(spin)
        self.assertEqual(spin.value(), before)
        self.assertLess(scroll.verticalScrollBar().value(), position)
        spin.setFocus()
        self.pump()
        self.wheel(spin)
        self.assertGreater(spin.value(), before)

    def test_compact_selector_and_large_sidebar_keep_category_and_values(self):
        w = self.window
        w.set_advanced_mode(True)
        w.rule_nav.setCurrentRow(8)
        before = w.current_options()
        for size in ((2048, 1113), (680, 540), (1040, 840), (2048, 1113)):
            w.resize(*size)
            self.pump()
            self.assertEqual(w.category_selector.currentIndex(), 8)
            self.assertEqual(w.rule_pages.currentIndex(), 8)
            self.assertEqual(w.current_options(), before)
            self.assertNotIsInstance(w.settings.widget(1), QScrollArea)
            content_width = w.workspace_tabs.parentWidget().width()
            self.assertGreater(content_width, min(size[0] - 100, 1100))
            if size[0] == 680:
                self.assertTrue(w.category_selector.isVisible())
                self.assertFalse(w.rule_nav.isVisible())
            if size[0] == 2048:
                self.assertTrue(w.rule_nav.isVisible())
                self.assertFalse(w.category_selector.isVisible())
            self.assertTrue(w.next_button.isVisible())
        w.resize(680, 540)
        self.pump()
        w.category_selector.setCurrentIndex(3)
        self.assertEqual(w.rule_nav.currentRow(), 3)

    def test_selected_preset_displays_description_and_seeded_shiny_rate(self):
        w = self.window
        for index in (0, 1, 2):
            w.presets[index][0].click()
            options = w.current_options()
            self.assertEqual(w.preset_common.isHidden(), index == 2)
            self.assertEqual(w.preset_shiny.isHidden(), index == 2)
            self.assertEqual(options.custom_shinies, index != 2)
            if index != 2:
                self.assertEqual(options.shiny_chance_percent, 5.0)
                self.assertTrue(options.seeded_shinies)
            else:
                self.assertFalse(options.has_changes)

    def test_reopening_translated_windows_keeps_valid_native_wrappers(self):
        for cycle in range(4):
            for language in ("fr", "en", "de", "es", "it", "ja"):
                with self.subTest(cycle=cycle, language=language):
                    settings = QSettings(str(Path(self.folder.name) / "lifecycle.ini"), QSettings.Format.IniFormat)
                    settings.setValue("interface/music", False)
                    settings.setValue("interface/sounds", False)
                    settings.setValue("interface/language", language)
                    other = MainWindow(settings=settings, system_languages=["ko-KR"])
                    self.assertIsInstance(other.encounters_scrollbar, QScrollBar)
                    self.assertIs(other.encounters_tree.verticalScrollBar(), other.encounters_scrollbar)
                    self.assertIsInstance(other.rule_nav.currentItem(), QListWidgetItem)
                    other.close()
                    other.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    del other
                    gc.collect()
    def test_list_fills_height_search_preserves_seed_and_options(self):
        w = self.window
        w.set_options(replace(w.current_options(), custom_shinies=True))
        sample = dict(national_dex=133, name_fr="Évoli", name_en="Eevee", name_de="Evoli",
                      name_es="Eevee", name_it="Eevee", portrait_png=b"", original={"national_dex": 1, "name_en": "Bulbasaur"})
        rows = [dict(sample, shadow_id=i, shiny=i % 2 == 0) for i in range(1, 49)]
        w.preview_result = {"shiny_policy": "seeded", "starters": [], "shadows": rows, "gifts": rows[:4]}
        w.workspace_tabs.setCurrentIndex(1)
        w.preview_tabs.setCurrentIndex(1)
        w.resize(2048, 1113)
        w.render_encounters()
        self.pump()
        before, seed = w.current_options(), w.seed.text()
        tree = w.encounters_tree
        self.assertGreater(tree.height(), 400)
        self.assertIn("48", w.preview_count.text())
        w.preview_search.setText("evoli")
        self.pump()
        self.assertEqual(sum(not tree.topLevelItem(i).isHidden() for i in range(48)), 48)
        w.preview_search.setText("no matching species")
        self.assertEqual(w.preview_count.text(), "Aucun résultat")
        w.preview_search.clear()
        tree.verticalScrollBar().setValue(tree.verticalScrollBar().maximum())
        self.pump()
        self.assertIn("48 sur 48", w.preview_count.text())
        w.preview_tabs.setCurrentIndex(2)
        self.assertEqual(tree.topLevelItemCount(), 4)
        w.workspace_tabs.setCurrentIndex(0)
        w.workspace_tabs.setCurrentIndex(1)
        self.assertEqual(w.current_options(), before)
        self.assertEqual(w.seed.text(), seed)
