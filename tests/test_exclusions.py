"""Exclusion validation, profiles and complete native selectors without a ROM."""
from dataclasses import replace
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from colosseum_randomizer.i18n import LANGUAGES
from colosseum_randomizer.locales.selection_names import SPECIES_NAMES, TYPE_NAMES
from colosseum_randomizer.options import Options
from colosseum_randomizer.profiles import NEW_POLICY_FIELDS, SHINY_FIELDS, EVENT_GIFT_FIELDS, V15_FIELDS, LEGACY_GAME, parse_profile, profile_data
from colosseum_randomizer.service import UserError, validate_options


class ExclusionValidationTests(unittest.TestCase):
    def test_lists_normalized_and_invalid_ids_or_boolean_ids_rejected(self):
        options = validate_options(replace(Options(), excluded_species=[386, 1, 1], excluded_types=[17, 0, 17]))
        self.assertEqual(options.excluded_species, (1, 386))
        self.assertEqual(options.excluded_types, (0, 17))
        for field, invalid in (("excluded_species", [0]), ("excluded_species", [387]),
                               ("excluded_species", [True]), ("excluded_species", "25"),
                               ("excluded_species", [[25]]), ("excluded_types", [9]),
                               ("excluded_types", [18]), ("excluded_types", [False]),
                               ("excluded_types", None)):
            with self.subTest(field=field, value=invalid), self.assertRaises(UserError):
                validate_options(replace(Options(), **{field: invalid}))

    def test_nonempty_exclusions_and_policies_roundtrip_and_v08_migration_off(self):
        options = replace(Options.recommended(), excluded_species=(1, 2, 3), excluded_types=(10, 11),
                          trainer_theme_mode="preserve", trainer_force_evolved=True, trainer_evolution_level=50)
        encode = lambda payload: json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.assertEqual(parse_profile(encode(profile_data("種-é", options))).options, options)
        legacy = profile_data("v08", Options.recommended())
        legacy.update(app_version="0.8.0", engine_version="starter-evolution-stages-v9")
        legacy["game"] = dict(LEGACY_GAME)
        for name in NEW_POLICY_FIELDS | SHINY_FIELDS | EVENT_GIFT_FIELDS | V15_FIELDS | {"diverse_story_families"}:
            legacy["options"].pop(name)
        from tests.test_profiles import ProfileTests
        ProfileTests().sign(legacy)
        self.assertEqual(parse_profile(encode(legacy)).options, replace(Options.recommended(), seeded_shinies=False,
                                                                      accessible_event_gifts=False))
        legacy["options"]["excluded_species"] = []
        ProfileTests().sign(legacy)
        with self.assertRaises(UserError):
            parse_profile(encode(legacy))

    def test_names_complete_in_all_six_languages_and_native_types_skip_mystery(self):
        self.assertEqual(set(SPECIES_NAMES), set(LANGUAGES))
        for language in LANGUAGES:
            self.assertEqual(set(SPECIES_NAMES[language]), set(range(1, 387)))
            self.assertEqual(set(TYPE_NAMES[language]), set(range(18)) - {9})
        from colosseum_randomizer.locales.species_ja import SPECIES_NAMES as previous_ja
        self.assertEqual(SPECIES_NAMES["ja"], previous_ja)


class ExclusionGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtCore import QSettings
        from colosseum_randomizer.gui import MainWindow
        self.folder = tempfile.TemporaryDirectory()
        settings = QSettings(str(Path(self.folder.name) / "settings.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = MainWindow(settings=settings, system_languages=["fr-FR"])

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.folder.cleanup()

    def dialog(self, kind, values=()):
        from colosseum_randomizer.ui_exclusions import ExclusionDialog
        return ExclusionDialog(kind, values, self.window.language, self.window.text, self.window)

    def test_search_enter_does_not_accept_and_explicit_buttons_keep_their_roles(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QDialog
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            dialog = self.dialog("type_set", (10,))
            dialog.show()
            self.app.processEvents()
            QTest.keyClick(dialog.search, Qt.Key.Key_Return)
            self.app.processEvents()
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.value(), (10,))
            dialog.cancel_button.click()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
            accepted = self.dialog("species_set", (133,))
            accepted.show()
            accepted.ok_button.click()
            self.assertEqual(accepted.result(), QDialog.DialogCode.Accepted)
            self.assertEqual(accepted.value(), (133,))

    def test_search_accepts_accents_numbers_other_languages_and_bulk_only_visible(self):
        dialog = self.dialog("species_set", (1,))
        self.assertEqual(dialog.items.count(), 386)
        for query in ("Evoli", "ÉVOLI", "133", "イーブイ", "Eevee"):
            dialog.search.setText(query)
            matches = [dialog.items.item(i).text() for i in range(386) if not dialog.items.item(i).isHidden()]
            self.assertEqual(matches, ["#133  Évoli"], query)
        dialog.exclude_results.click()
        self.assertEqual(dialog.value(), (1, 133))
        dialog.allow_results.click()
        self.assertEqual(dialog.value(), (1,))
        dialog.search.setText("nothing matches")
        self.assertFalse(dialog.exclude_results.isEnabled())
        self.assertEqual(dialog.value(), (1,))
        dialog.close()

    def test_cancel_is_transactional_and_ok_applies(self):
        from PySide6.QtWidgets import QDialog
        control = self.window.rule_fields["excluded_species"]
        control.setValue((25,))
        def cancel(dialog):
            dialog.search.setText("133")
            dialog.set_visible(True)
            return QDialog.DialogCode.Rejected
        with patch("colosseum_randomizer.ui_exclusions.ExclusionDialog.exec", cancel):
            control.open_dialog()
        self.assertEqual(control.value(), (25,))
        def accept(dialog):
            dialog.search.setText("133")
            dialog.set_visible(True)
            return QDialog.DialogCode.Accepted
        with patch("colosseum_randomizer.ui_exclusions.ExclusionDialog.exec", accept):
            control.open_dialog()
        self.assertEqual(control.value(), (25, 133))

    def test_language_changes_retain_ids_and_profiles_and_dependencies(self):
        options = replace(Options.recommended(), excluded_species=(1, 133), excluded_types=(10, 17),
                          trainer_theme_mode="random", trainer_force_evolved=True)
        self.window.set_options(options)
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.assertEqual(self.window.current_options(), options)
            dialog = self.dialog("type_set", options.excluded_types)
            self.assertEqual(dialog.items.count(), 17)
            self.assertEqual(dialog.value(), options.excluded_types)
            self.assertEqual(dialog.items.item(0).text(), TYPE_NAMES[language][0])
            dialog.close()
        self.window.set_options(replace(options, randomize_trainers=False, trainer_force_evolved=False))
        self.assertFalse(self.window.rule_fields["trainer_theme_mode"].isEnabled())
        self.assertFalse(self.window.rule_fields["trainer_evolution_level"].isEnabled())
        self.assertEqual(self.window.current_options().trainer_theme_mode, "random")


if __name__ == "__main__":
    unittest.main()
