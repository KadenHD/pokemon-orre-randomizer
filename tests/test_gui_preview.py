"""Real Qt worker completion, stale-result rejection and safe preview closing."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QBuffer, QCoreApplication, QEvent, QIODevice, QSettings, Qt
    from PySide6.QtWidgets import QApplication
    from colosseum_randomizer.gui import MainWindow
    from colosseum_randomizer.ui_pokemon_names import RICH_NAME_ROLE
except ImportError:
    MainWindow = None

from colosseum_randomizer import __version__
from colosseum_randomizer.engine.regions import REGIONS
from colosseum_randomizer.service import Cancelled, ENGINE_VERSION, UserError
from colosseum_randomizer.preview import baseline_rows
from colosseum_randomizer.i18n import translate

RESULT = {"starters": [
    {"key": "umbreon", "national_dex": 252, "name_fr": "Arcko", "name_en": "Treecko",
     "name_de": "Geckarbor", "name_es": "Treecko", "name_it": "Treecko", "level": 26, "portrait_png": b""},
    {"key": "espeon", "national_dex": 196, "name_fr": "Mentali", "name_en": "Espeon",
     "name_de": "Psiana", "name_es": "Espeon", "name_it": "Espeon", "level": 25, "portrait_png": b""}]}


@unittest.skipIf(MainWindow is None, "requires optional Qt desktop dependencies")
class GuiPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.source = Path(self.folder.name) / "original.iso"
        self.source.write_bytes(b"synthetic; preview service mocked")
        settings = QSettings(str(Path(self.folder.name) / "preferences.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        self.window = MainWindow(settings=settings, system_languages=["fr-FR"])
        self.window.source.setText(str(self.source))
        self.window.seed.setText("été-🌟")

    def pump_until(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(condition())

    def tearDown(self):
        self.window.cancel_preview()
        self.pump_until(lambda: self.window.preview_thread is None)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.folder.cleanup()

    def test_completion_preserves_configuration_and_retranslates_result(self):
        options = self.window.current_options()
        with patch("colosseum_randomizer.gui.preview_starters", return_value=deepcopy(RESULT)) as preview:
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertEqual(preview.call_args.kwargs["seed"], "été-🌟")
        self.assertEqual(self.window.current_options(), options)

        self.assertIn("Arcko", self.window.preview_names["umbreon"].text())
        self.assertIn("26", self.window.preview_names["umbreon"].text())
        self.assertTrue(self.window.preview_button.isHidden())
        self.assertFalse(self.window.preview_button.isEnabled())
        self.assertEqual(self.window.preview_status.text(), "✓ Aperçu à jour")
        self.assertTrue(self.window.preview_progress.isHidden())
        # Direct invocation must also avoid the expensive calculation for the same inputs.
        with patch("colosseum_randomizer.gui.preview_starters") as duplicate:
            self.window.start_preview()
            duplicate.assert_not_called()
        for language, name in (("en", "Treecko"), ("de", "Geckarbor"), ("es", "Treecko"),
                               ("it", "Treecko"), ("ja", "キモリ"), ("fr", "Arcko")):
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.assertIsNotNone(self.window.preview_result)
            self.assertIn(name, self.window.preview_names["umbreon"].text())
            self.assertEqual(self.window.preview_status.text(), "✓ " + translate("Aperçu à jour", language))
            self.assertTrue(self.window.preview_button.isHidden())
        self.window.set_advanced_mode(True)
        self.window.workspace_tabs.setCurrentIndex(1)
        self.assertFalse(self.window.party_strip.isHidden())
        self.assertEqual(self.window.current_options(), options)

    def test_family_tab_names_duplicates_and_hides_after_seed_change(self):
        result = baseline_rows(self.window.current_options())
        result["starters"][0]["national_dex"] = 1
        result["shadows"][0]["national_dex"] = 2
        result["gifts"][0]["national_dex"] = 3
        result["family_duplicates"] = [["umbreon", "shadow:1", "plusle"]]
        with patch("colosseum_randomizer.gui.preview_starters", return_value=result):
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
        tabs = self.window.preview_tabs
        tab = self.window.family_tab
        self.assertTrue(tabs.isTabVisible(tab))
        tabs.setCurrentIndex(tab)
        self.assertTrue(self.window.preview_search.isHidden())
        self.assertIn("Bulbizarre (starter) · Herbizarre (obscur nº 01) · Florizarre (cadeau)",
                      self.window.family_duplicates.text())
        self.window.language_combo.setCurrentIndex(self.window.language_combo.findData("en"))
        self.assertIn("Ivysaur (Shadow #01)", self.window.family_duplicates.text())
        self.window.seed.setText("autre seed")
        self.assertFalse(tabs.isTabVisible(tab))
        self.assertNotEqual(tabs.currentIndex(), tab)

    def test_report_import_keeps_paths_and_updates_the_rom_verdict(self):
        w = self.window
        destination = self.source.with_name("new.iso")
        w.destination.setText(str(destination))
        report = self.source.with_suffix(".iso.json")
        region = REGIONS[0]
        options = replace(w.current_options(), experience_multiplier=2.0)
        report.write_text(json.dumps(dict(application_version=__version__, engine_version=ENGINE_VERSION,
            game_id=region.game_id, revision=region.revision, source_sha256=region.iso_sha256,
            source_iso_sha256=region.iso_sha256, seed="restored", options=asdict(options),
            source="ignored", output="ignored")), encoding="utf-8")
        with patch("colosseum_randomizer.gui.report_rom_matches",
                   side_effect=lambda _report, source, *_: source == self.source):
            w.import_creation_report(report)
            self.assertEqual((w.source.text(), w.destination.text()), (str(self.source), str(destination)))
            self.assertEqual((w.seed.text(), w.current_options()), ("restored", options))
            self.pump_until(lambda: "correspond" in w.report_rom_status.text())
            w.source.setText(str(self.source.with_name("different.iso")))
            self.pump_until(lambda: "diffère" in w.report_rom_status.text())
        w.language_combo.setCurrentIndex(w.language_combo.findData("en"))
        self.assertIn("differs", w.report_rom_status.text())
        report.write_text("{", encoding="utf-8")
        w.import_creation_report(report)
        self.assertEqual((w.seed.text(), w.current_options()), ("restored", options))
        self.assertIn("Invalid JSON report", w.status.text())

    def test_current_preview_plan_is_forwarded_to_creation_and_cleared_on_seed_change(self):
        plan = object()

        def completed(**arguments):
            arguments["on_prepared"](plan)
            return deepcopy(RESULT)

        with patch("colosseum_randomizer.gui.preview_starters", side_effect=completed):
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertIs(self.window.preview_plan, plan)
        self.window.destination.setText(str(self.source.with_name("output.iso")))
        with patch("colosseum_randomizer.gui.randomize", return_value={"output": "output.iso"}) as create:
            self.window.start()
            self.pump_until(lambda: self.window.thread is None)
            self.assertIs(create.call_args.kwargs["prepared_patches"], plan)
            self.window.seed.setText("new seed")
            self.assertIsNone(self.window.preview_plan)
            self.window.start()
            self.pump_until(lambda: self.window.thread is None)
            self.assertIsNone(create.call_args.kwargs["prepared_patches"])

    def test_pending_preview_only_names_known_species_and_lists_original_encounters(self):
        self.assertEqual([name.text() for name in self.window.preview_names.values()], ["?", "?"])
        self.window.set_options(replace(self.window.current_options(), starter_umbreon=False,
                                        starter_espeon_species=25))
        self.assertIn("Noctali", self.window.preview_names["umbreon"].text())
        self.assertIn("Pikachu", self.window.preview_names["espeon"].text())
        self.assertTrue(all(button.isHidden() for button in self.window.starter_detail_buttons.values()))
        tree = self.window.encounters_tree
        for index, count, name in ((1, 48, "Makuhita"), (2, 4, "Posipi")):
            self.window.preview_tabs.setCurrentIndex(index)
            self.assertEqual(tree.topLevelItemCount(), count)
            row = tree.topLevelItem(0)
            self.assertIn(name, row.text(0))
            self.assertEqual(row.text(1), "?")
            self.assertFalse(row.icon(1).isNull())
            self.window.show_encounter_detail(row)
            self.assertIsNone(self.window.detail_window)

    def test_seed_options_source_and_tool_changes_clear_previous_result(self):
        for mutate in (lambda: self.window.seed.setText("new"),
                       lambda: self.window.set_options(replace(self.window.current_options(), starter_umbreon=False)),
                       lambda: self.window.source.setText(str(self.source.with_name("other.iso"))),
                       lambda: self.window.tool.setText("C:/other/DolphinTool.exe")):
            self.window.preview_key = self.window.preview_configuration()
            self.window.preview_result = deepcopy(RESULT)
            self.window.render_preview()
            mutate()
            self.assertIsNone(self.window.preview_result)
            self.assertIn("Actualisez", self.window.preview_hint.text())
            self.assertNotIn("Arcko", self.window.preview_names["umbreon"].text())
            self.assertFalse(self.window.preview_button.isHidden())
            self.assertTrue(self.window.preview_button.isEnabled())
            self.assertEqual(self.window.preview_button.text(), "Actualiser l’aperçu")
            self.assertTrue(self.window.preview_status.isHidden())

    def test_guaranteed_shiny_preview_is_labeled_and_chance_edit_invalidates_it(self):
        result = deepcopy(RESULT)
        result["shiny_policy"] = "always"
        for row in result["starters"]:
            row["shiny"] = True
        self.window.set_options(replace(self.window.current_options(), custom_shinies=True, shiny_chance_percent=100))
        with patch("colosseum_randomizer.gui.preview_starters", return_value=result):
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertIn("★", self.window.preview_names["umbreon"].text())
        self.assertIn("garantis", self.window.preview_hint.text())
        self.window.rule_fields["shiny_chance_percent"].setValue(1)
        self.assertIsNone(self.window.preview_result)

    def test_event_gift_changes_invalidate_preview_and_update_gift_help(self):
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.preview_tabs.setCurrentIndex(2)
        for name, value in (("event_pikachu_purifications", 11), ("event_celebi_purifications", 26),
                            ("event_pikachu_level", 31), ("event_celebi_level", 46)):
            self.window.preview_key = self.window.preview_configuration()
            self.window.preview_result = deepcopy(RESULT)
            self.window.render_preview()
            self.window.rule_fields[name].setValue(value)
            self.assertIsNone(self.window.preview_result)
            self.assertEqual(self.window.encounters_tree.topLevelItemCount(), 4)
        self.assertIn("Adelbert", self.window.status.text())
        self.window.preview_key = self.window.preview_configuration()
        self.window.preview_result = deepcopy(RESULT)
        self.window.rule_checks["accessible_event_gifts"].setChecked(False)
        self.assertIsNone(self.window.preview_result)
        self.assertEqual(self.window.status.text(), "Les événements gardent leurs conditions d’obtention.")

    def test_purification_gift_rows_keep_original_names_and_localize_donor(self):
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.preview_tabs.setCurrentIndex(2)
        result = deepcopy(RESULT)
        gift = dict(result["starters"][0], original=result["starters"][1], event=False, purifications=1)
        result["gifts"] = [gift]
        self.window.preview_key = self.window.preview_configuration()
        self.window.preview_result = result
        for count in (0, 1, 25):
            gift["purifications"] = count
            for language, donor in (("fr", "Adelbert"), ("en", "Eagun"), ("de", "Sophos"),
                                    ("es", "Mauricio"), ("it", "Salapuzio"), ("ja", "ローガン")):
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
                self.window.render_encounters()
                original = self.window.encounters_tree.topLevelItem(0).text(0)
                self.assertIn(self.window.preview_species_name(gift["original"]), original)
                source = "Adelbert · {count} purification" if count == 1 else "Adelbert · {count} purifications"
                self.assertIn(translate(source, language).format(count=count), original)
                self.assertIn(donor, original)
                self.assertEqual(self.window.status.text(), translate(
                    "Adelbert remet ces cadeaux après le nombre de purifications choisi.", language))
                self.assertIs(self.window.preview_result, result)

    def test_partial_rate_preview_explains_that_status_is_rolled_in_game(self):
        result = deepcopy(RESULT)
        result["shiny_policy"] = "in-game"
        self.window.set_options(replace(self.window.current_options(), custom_shinies=True, seeded_shinies=False, shiny_chance_percent=1))
        with patch("colosseum_randomizer.gui.preview_starters", return_value=result):
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertIn("tiré en jeu", self.window.preview_hint.text())
        self.assertNotIn("chromatique", self.window.preview_names["umbreon"].text())

    def test_seeded_status_is_visible_before_calculation_and_checkbox_follows_custom(self):
        self.assertTrue(self.window.rule_checks["seeded_shinies"].isEnabled())
        self.window.set_options(replace(self.window.current_options(), custom_shinies=True,
                                        seeded_shinies=True, shiny_chance_percent=1))
        self.assertTrue(self.window.rule_checks["seeded_shinies"].isEnabled())
        self.assertTrue(self.window.rule_fields["shiny_chance_percent"].isEnabled())
        for language in ("fr", "en", "de", "es", "it", "ja"):
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.assertEqual(self.window.preview_shiny_status.text(),
                             translate("Statuts chromatiques fixés par la seed.", language))
        self.window.rule_checks["seeded_shinies"].setChecked(False)
        self.assertTrue(self.window.rule_fields["shiny_chance_percent"].isEnabled())
        self.window.rule_checks["custom_shinies"].setChecked(False)
        self.assertFalse(self.window.rule_checks["seeded_shinies"].isEnabled())
        self.assertFalse(self.window.rule_fields["shiny_chance_percent"].isEnabled())

    def test_seeded_preview_labels_each_status_translates_and_checkbox_invalidates_cache(self):
        result = deepcopy(RESULT)
        result["shiny_policy"] = "seeded"
        result["starters"][0]["shiny"] = True
        result["starters"][1]["shiny"] = False
        result["shadows"] = [dict(result["starters"][1], shadow_id=21, original=result["starters"][0])]
        result["gifts"] = [dict(result["starters"][0], original=result["starters"][1], event=True)]
        self.window.set_options(replace(self.window.current_options(), custom_shinies=True,
                                        seeded_shinies=True, shiny_chance_percent=1))
        with patch("colosseum_randomizer.gui.preview_starters", return_value=result) as preview:
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
            for language in ("fr", "en", "de", "es", "it", "ja"):
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
                ordinary = self.window.preview_species_name(result["starters"][1])
                shiny = self.window.preview_species_name(result["starters"][0])
                self.assertIn(shiny + "&nbsp;<sup", self.window.preview_names["umbreon"].text())
                expected = translate("{name} · Niv. {level}", language).format(name=ordinary, level=25)
                self.assertEqual(self.window.preview_names["espeon"].text(), expected)
                self.window.preview_tabs.setCurrentIndex(1)
                shadow = self.window.encounters_tree.topLevelItem(0)
                self.assertEqual(shadow.text(1), expected)
                self.assertIsNone(shadow.data(1, RICH_NAME_ROLE))
                self.window.preview_tabs.setCurrentIndex(2)
                gift = self.window.encounters_tree.topLevelItem(0)
                self.assertIn(shiny + " ★", gift.text(1))
                self.assertIn(shiny + "&nbsp;<sup", gift.data(1, RICH_NAME_ROLE))
                self.assertEqual(self.window.preview_hint.text(), translate(
                    "Espèces et statuts fixés pour une nouvelle partie.", language))
            self.assertEqual(preview.call_count, 1)
            self.window.rule_checks["seeded_shinies"].click()
            self.assertIsNone(self.window.preview_result)
            self.assertTrue(self.window.preview_button.isEnabled())
            self.assertEqual(self.window.encounters_tree.topLevelItemCount(), 4)
            self.assertEqual(preview.call_count, 1)

    def test_shiny_guarantee_is_visible_before_calculation_and_respects_enable_switch(self):
        self.window.set_options(replace(self.window.current_options(), custom_shinies=True, shiny_chance_percent=100))
        self.assertIn("garantis", self.window.preview_shiny_status.text())
        self.assertIsNone(self.window.preview_result)
        self.window.rule_checks["custom_shinies"].setChecked(False)
        self.assertIn("origine", self.window.preview_shiny_status.text())
        self.window.rule_checks["custom_shinies"].setChecked(True)
        self.window.rule_fields["shiny_chance_percent"].setValue(0)
        self.assertIn("aucun", self.window.preview_shiny_status.text())

    def test_encounter_tabs_reuse_preview_translate_and_clear_stale_draws(self):
        result = deepcopy(RESULT)
        result["shadows"] = [dict(result["starters"][0], shadow_id=21, original=result["starters"][1])]
        result["gifts"] = [dict(result["starters"][1], original=result["starters"][0], event=True)]
        self.window.rule_checks["accessible_event_gifts"].setChecked(False)
        self.assertEqual(self.window.workspace_pages.currentIndex(), 0)
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.preview_tabs.setCurrentIndex(1)
        with patch("colosseum_randomizer.gui.preview_starters", return_value=result) as preview:
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
            tree = self.window.encounters_tree
            self.assertEqual(tree.topLevelItemCount(), 1)
            self.assertIn("Mentali", tree.topLevelItem(0).text(0))
            self.assertIn("Arcko", tree.topLevelItem(0).text(1))
            self.window.preview_tabs.setCurrentIndex(2)
            self.assertIn("Événement", tree.topLevelItem(0).text(0))
            self.window.preview_tabs.setCurrentIndex(1)
            for language in ("en", "de", "es", "it", "ja", "fr"):
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
                if language == "ja":
                    self.assertIn("エーフィ", tree.topLevelItem(0).text(0))
                    self.assertIn("キモリ", tree.topLevelItem(0).text(1))
            self.window.workspace_tabs.setCurrentIndex(0)
            self.window.workspace_tabs.setCurrentIndex(1)
            self.assertEqual(preview.call_count, 1)
            self.window.seed.setText("changed")
            self.assertEqual(tree.topLevelItemCount(), 48)
            self.assertEqual(tree.topLevelItem(0).text(1), "?")
            self.assertIn("modifiés", self.window.preview_hint.text())
            self.assertEqual(preview.call_count, 1)

    def test_loading_is_visible_translatable_and_prevents_duplicate_requests(self):
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.show()
        entered, release = threading.Event(), threading.Event()
        image = QBuffer()
        image.open(QIODevice.OpenModeFlag.WriteOnly)
        self.assertTrue(self.window.unknown_portrait.pixmap(42, 42).save(image, "PNG"))
        portrait = bytes(image.data())

        def delayed(**arguments):
            arguments["roulette"]({1: portrait})
            entered.set()
            release.wait(3)
            return deepcopy(RESULT)

        with patch("colosseum_randomizer.gui.preview_starters", side_effect=delayed) as preview:
            try:
                self.window.start_preview()
                self.pump_until(entered.is_set)
                self.assertFalse(self.window.preview_progress.isHidden())
                self.assertEqual((self.window.preview_progress.minimum(), self.window.preview_progress.maximum()), (0, 0))
                self.assertTrue(self.window.preview_button.isHidden())
                self.assertFalse(self.window.preview_cancel_button.isHidden())
                self.assertTrue(self.window.preview_cancel_button.isEnabled())
                self.assertEqual(self.window.preview_status.text(), "Calcul en cours…")
                self.assertTrue(self.window.roulette_timer.isActive())
                self.pump_until(lambda: 1 in self.window.roulette_faces)
                self.pump_until(lambda: self.window.preview_names["umbreon"].text() != "?")
                first = self.window.preview_names["umbreon"].text()
                self.pump_until(lambda: self.window.preview_names["umbreon"].text() != first)
                self.window.start_preview()
                self.assertEqual(preview.call_count, 1)
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData("de"))
                self.assertEqual(self.window.preview_status.text(), "Berechnung läuft…")
                self.assertTrue(self.window.seed.isEnabled())
            finally:
                release.set()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertTrue(self.window.preview_progress.isHidden())
        self.assertEqual(self.window.preview_status.text(), "✓ Vorschau aktuell")
        self.assertFalse(self.window.roulette_timer.isActive())

    def test_cancel_shows_waiting_then_retry_and_rejects_late_success(self):
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.show()
        entered, release = threading.Event(), threading.Event()

        def delayed(**arguments):
            entered.set()
            release.wait(3)
            return deepcopy(RESULT)

        with patch("colosseum_randomizer.gui.preview_starters", side_effect=delayed):
            try:
                self.window.start_preview()
                self.pump_until(entered.is_set)
                self.window.cancel_preview()
                self.assertFalse(self.window.roulette_timer.isActive())
                self.assertEqual(self.window.preview_status.text(), "Annulation de l’aperçu…")
                self.assertFalse(self.window.preview_cancel_button.isEnabled())
                self.assertFalse(self.window.preview_progress.isHidden())
            finally:
                release.set()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertIsNone(self.window.preview_result)
        self.assertTrue(self.window.preview_progress.isHidden())
        self.assertTrue(self.window.preview_status.isHidden())
        self.assertEqual(self.window.preview_hint.text(), "Aperçu annulé.")
        self.assertEqual(self.window.preview_button.text(), "Réessayer")
        self.assertTrue(self.window.preview_button.isEnabled())

    def test_failure_clears_loading_and_offers_retry(self):
        with patch("colosseum_randomizer.gui.preview_starters", side_effect=UserError("Choisissez la ROM d’origine.")):
            self.window.start_preview()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertIsNone(self.window.preview_result)
        self.assertTrue(self.window.preview_progress.isHidden())
        self.assertTrue(self.window.preview_status.isHidden())
        self.assertEqual(self.window.preview_button.text(), "Réessayer")
        self.assertTrue(self.window.preview_button.isEnabled())

    def test_late_result_after_edit_is_ignored_and_ui_stays_usable(self):
        self.window.step = 1
        self.window.refresh_navigation()
        self.window.workspace_tabs.setCurrentIndex(1)
        self.window.show()
        entered, release = threading.Event(), threading.Event()

        def delayed(**arguments):
            entered.set()
            release.wait(3)
            return deepcopy(RESULT)  # Deliberately ignore cancellation to test UI rejection.

        with patch("colosseum_randomizer.gui.preview_starters", side_effect=delayed):
            try:
                self.window.start_preview()
                self.pump_until(entered.is_set)
                self.assertFalse(self.window.busy)
                self.assertTrue(self.window.seed.isEnabled())
                self.assertFalse(self.window.create_button.isEnabled())
                self.window.seed.setText("new-seed")
                self.assertTrue(self.window.preview_cancel_event.is_set())
            finally:
                release.set()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertIsNone(self.window.preview_result)
        self.assertTrue(self.window.create_button.isEnabled())
        self.assertTrue(self.window.preview_button.isEnabled())
        self.assertIn("modifiés", self.window.preview_hint.text())

    def test_close_cancels_worker_before_window_cleanup(self):
        entered = threading.Event()

        def waiting(**arguments):
            entered.set()
            arguments["cancel"].wait(3)
            raise Cancelled("cancelled")

        self.window.show()
        with patch("colosseum_randomizer.gui.preview_starters", side_effect=waiting):
            self.window.start_preview()
            self.pump_until(entered.is_set)
            self.window.close()
            self.pump_until(lambda: self.window.preview_thread is None)
        self.assertFalse(self.window.isVisible())
        self.assertIsNone(self.window.preview_result)

    def test_missing_rom_error_stays_in_preview_and_leaves_form_intact(self):
        self.window.source.clear()
        options = self.window.current_options()
        self.window.start_preview()
        self.assertIsNone(self.window.preview_thread)
        self.assertIn("ROM d’origine", self.window.preview_hint.text())
        self.assertEqual(self.window.current_options(), options)
        self.assertEqual(self.window.seed.text(), "été-🌟")


if __name__ == "__main__":
    unittest.main()
