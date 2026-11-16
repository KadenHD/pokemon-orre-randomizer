"""Native display numbers, acquisition columns and XD portrait silhouettes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from orre_randomizer.encounter_presentation import colosseum_shadow_number, colosseum_gift_condition, PLUSLE_CONDITION, HOOH_CONDITION
from orre_randomizer.i18n import translate, LANGUAGES
from orre_randomizer.preview import BASE_SHADOWS, baseline_rows

try:
    from PySide6.QtCore import QBuffer, QIODevice, QPoint, QPointF, QSettings, Qt, QCoreApplication, QEvent
    from PySide6.QtGui import QPixmap, QColor, QWheelEvent
    from PySide6.QtWidgets import QApplication, QAbstractItemView
    from orre_randomizer.gui import MainWindow
except ImportError:
    MainWindow = None


class DisplayNumberTests(unittest.TestCase):
    def test_roster_numbers_are_contiguous_without_rewriting_internal_ids(self):
        self.assertEqual([colosseum_shadow_number(sid) for sid, _ in BASE_SHADOWS], list(range(1, 49)))
        self.assertEqual([sid for sid, _ in BASE_SHADOWS][-4:], [55, 56, 57, 67])
        self.assertEqual(colosseum_shadow_number(96), 49)

    def test_gift_conditions_cover_story_battle_mode_and_configurable_rewards_in_six_languages(self):
        for language in LANGUAGES:
            text = lambda source, **args: translate(source, language).format(**args)
            for key in ('plusle', 'ho-oh', 'pikachu-event', 'celebi-event'):
                row = {'key': key, 'purifications': 10} if key.endswith('event') else {'key': key}
                self.assertTrue(colosseum_gift_condition(row, text))
            for source in (PLUSLE_CONDITION, HOOH_CONDITION, 'Conditions d’obtention', 'Lieu et fréquence'):
                if language != 'fr':
                    self.assertNotEqual(text(source), source, (language, source))


@unittest.skipIf(MainWindow is None, 'requires Qt')
class EncounterViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        prefs = QSettings(str(Path(self.temp.name)/'private.ini'), QSettings.Format.IniFormat)
        prefs.setValue('interface/music', False)
        prefs.setValue('interface/sounds', False)
        prefs.setValue('interface/language', 'fr')
        self.updates = patch('orre_randomizer.gui.UpdateChecker.check_once')
        self.updates.start()
        self.window = MainWindow(settings=prefs, system_languages=['fr'])
        self.window.resize(1040, 800)
        self.window.show()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.updates.stop()
        self.temp.cleanup()

    def test_shadow_tail_displays_45_to_48_and_keeps_engine_keys(self):
        w = self.window
        w.show_colosseum()
        w.preview_tabs.setCurrentIndex(1)
        w.render_encounters()
        tree = w.encounters_tree
        tail = [tree.topLevelItem(i) for i in range(44, 48)]
        self.assertEqual([int(item.text(0).split(' · ')[0]) for item in tail], [45, 46, 47, 48])
        self.assertEqual([item.data(0, Qt.ItemDataRole.UserRole+2)['shadow_id'] for item in tail], [55, 56, 57, 67])

    def test_gifts_have_a_separate_wrapping_condition_column_and_switch_back_cleanly(self):
        w = self.window
        w.show_colosseum()
        w.preview_tabs.setCurrentIndex(2)
        w.render_encounters()
        tree = w.encounters_tree
        self.assertEqual((tree.columnCount(), tree.result_column), (3, 2))
        self.assertEqual(tree.topLevelItem(0).text(0), 'Posipi')
        self.assertIn('Bouledisco', tree.topLevelItem(0).text(1))
        self.assertIn('mode Combat', tree.topLevelItem(1).text(1))
        self.assertEqual(tree.topLevelItem(0).text(2), '?')
        w.resize(680, 540)
        self.app.processEvents()
        tree.layout_rows()
        self.assertGreater(tree.topLevelItem(1).sizeHint(0).height(), 54)
        self.assertEqual(tree.verticalScrollMode(), QAbstractItemView.ScrollMode.ScrollPerPixel)
        w.preview_tabs.setCurrentIndex(1)
        w.render_encounters()
        self.assertEqual((tree.columnCount(), tree.result_column), (2, 1))

    def test_xd_frequency_stays_in_the_middle_for_gifts_and_poke_spots(self):
        w = self.window
        w.show_xd()
        xd = w.xd
        for tab in (2, 3):
            xd.encounter_tabs.setCurrentIndex(tab)
            xd.render_preview()
            tree = xd.preview_details
            self.assertEqual((tree.columnCount(), tree.result_column), (3, 2))
            row = tree.topLevelItem(1 if tab == 2 else 2)
            self.assertIn('15 %', row.text(1))
            self.assertNotIn('%', row.text(0)+row.text(2))
            self.assertEqual(row.text(2), '?')
            if tab == 3:
                self.assertEqual(tree.headerItem().text(1), 'Lieu et fréquence')
                self.assertEqual(row.text(0), 'Kraknoix')
                self.assertEqual(row.text(1), 'Roche · 15 % des rencontres')
        xd.encounter_tabs.setCurrentIndex(1)
        xd.render_preview()
        self.assertEqual((xd.preview_details.columnCount(), xd.preview_details.result_column), (2, 1))

    def test_unknown_and_opaque_roulette_frames_are_round_only_in_xd(self):
        w = self.window
        image = QPixmap(42, 42)
        image.fill(QColor('red'))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        row = {'portrait_png': bytes(buffer.data())}
        for xd in (False, True):
            for current in ({}, row):
                png = w.preview_portrait(current, xd=xd).pixmap(42, 42).toImage()
                for x, y in ((0, 0), (41, 0), (0, 41), (41, 41)):
                    self.assertEqual(png.pixelColor(x, y).alpha(), 0 if xd else 255)
                self.assertEqual(png.pixelColor(21, 21).alpha(), 255)

    def test_horizontal_gestures_do_not_pan_rows_or_header_and_vertical_scroll_still_works(self):
        w = self.window
        for xd in (False, True):
            with self.subTest(xd=xd):
                (w.show_xd if xd else w.show_colosseum)()
                pane = w.xd if xd else w
                pane.step = 1
                if xd:
                    pane.pages.setCurrentIndex(1)
                pane.refresh_navigation()
                pane.workspace_tabs.setCurrentIndex(1)
                (pane.encounter_tabs if xd else pane.preview_tabs).setCurrentIndex(1)
                tree = pane.preview_details if xd else pane.encounters_tree
                # Hiding a scrollbar alone still permits wheel/selection panning
                # when the header's minimum widths exceed the available space.
                tree.header().setMinimumSectionSize(180)
                tree.setFixedWidth(300)
                for _ in range(3):
                    self.app.processEvents()
                vertical = tree.verticalScrollBar()
                self.assertGreater(vertical.maximum(), 0)

                def wheel(target, pixels, angles, modifiers=Qt.KeyboardModifier.NoModifier):
                    pos = QPoint(30, min(15, target.height() - 1))
                    event = QWheelEvent(QPointF(pos), QPointF(target.mapToGlobal(pos)),
                                        pixels, angles, Qt.MouseButton.NoButton, modifiers,
                                        Qt.ScrollPhase.ScrollUpdate, False)
                    self.app.sendEvent(target, event)
                    self.app.processEvents()
                    return event

                for target in (tree.viewport(), tree.header().viewport()):
                    for pixels, angles, modifiers in (
                        (QPoint(-90, 0), QPoint(), Qt.KeyboardModifier.NoModifier),
                        (QPoint(), QPoint(-120, 0), Qt.KeyboardModifier.NoModifier),
                        (QPoint(), QPoint(0, -120), Qt.KeyboardModifier.ShiftModifier),
                    ):
                        before_y = vertical.value()
                        event = wheel(target, pixels, angles, modifiers)
                        self.assertEqual(tree.header().offset(), 0)
                        self.assertEqual(tree.horizontalOffset(), 0)
                        self.assertEqual(vertical.value(), before_y)
                        self.assertTrue(event.isAccepted())
                self.assertEqual(tree.horizontalScrollBar().maximum(), 0)
                tree.setCurrentItem(tree.topLevelItem(0), tree.result_column)
                tree.scrollToItem(tree.topLevelItem(0))
                self.app.processEvents()
                self.assertEqual(tree.header().offset(), 0)
                for target, pixels, angles in (
                    (tree.viewport(), QPoint(), QPoint(0, -120)),
                    (tree.viewport(), QPoint(-30, -60), QPoint(-120, -120)),
                    (tree.header().viewport(), QPoint(), QPoint(0, -120)),
                ):
                    vertical.setValue(0)
                    wheel(target, pixels, angles)
                    self.assertGreater(vertical.value(), 0)
                    self.assertEqual(tree.header().offset(), 0)


if __name__ == '__main__':
    unittest.main()
