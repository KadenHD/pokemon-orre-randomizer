"""Cross-game vocabulary, preview states and verified-plan regressions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from contextlib import ExitStack
from dataclasses import asdict, fields, replace
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from orre_randomizer import __version__, service
from orre_randomizer.i18n import CATALOGS, LANGUAGES, translate
from orre_randomizer.options import Options
from orre_randomizer.preview import preview_xd
from orre_randomizer.settings_presentation import configuration_review
from orre_randomizer.workspace_copy import CATEGORY_HELP, CUSTOM_PRESET, PRESET_DESCRIPTIONS, PRESET_EVOLUTIONS
from orre_randomizer.xd import REGIONS, VERSION, XDOptions
from orre_randomizer.xd_preview import baseline_rows

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from orre_randomizer.gui import MainWindow
except ImportError:
    MainWindow = None


class SharedCopyTests(unittest.TestCase):
    def test_shared_options_use_identical_labels_groups_and_choices_in_six_languages(self):
        common = {item.name: item.metadata for item in fields(Options)}
        aliases = {"randomize_starter": "starter_umbreon", "starter_species": "starter_umbreon_species",
                   "unique_shadow_families": "unique_shadows"}
        compared = 0
        for item in fields(XDOptions):
            name = aliases.get(item.name, item.name)
            if name not in common:
                continue
            compared += 1
            for language in LANGUAGES:
                for key in ("label", "group"):
                    self.assertEqual(translate(item.metadata[key], language), translate(common[name][key], language),
                                     (item.name, language, key))
                self.assertEqual(item.metadata.get("choices"), common[name].get("choices"))
        self.assertGreater(compared, 55)

    def test_all_xd_settings_have_localized_help_without_colosseum_only_instructions(self):
        for item in fields(XDOptions):
            self.assertTrue(item.metadata["description"], item.name)
            for key in ("label", "description", "group"):
                self.assertNotIn("Colosseum", item.metadata[key], item.name)
                for language, catalog in CATALOGS.items():
                    self.assertIn(item.metadata[key], catalog, (item.name, key, language))

    def test_shared_copy_has_complete_translations(self):
        for source in (*CATEGORY_HELP.values(), *PRESET_DESCRIPTIONS, CUSTOM_PRESET, PRESET_EVOLUTIONS):
            for language, catalog in CATALOGS.items():
                self.assertIn(source, catalog, (language, source))

    def test_xd_initial_lists_have_known_origins_and_honest_unknowns(self):
        result = baseline_rows(XDOptions.recommended())
        shadows = result["decks"]["Story"]["shadows"]
        self.assertEqual((len(shadows), len(result["gifts"]), len(result["poke_spots"])), (83, 7, 9))
        self.assertIsNone(result["starter"]["species"])
        self.assertEqual(shadows[72]["species"], 249)  # Shadow Lugia retains its native species.
        self.assertIsNone(shadows[0]["species"])
        self.assertIsNone(shadows[80]["species"])
        kept = baseline_rows(XDOptions.unchanged())
        self.assertTrue(all(row["species"] == row["original"] for row in
                            [kept["starter"], *kept["decks"]["Story"]["shadows"], *kept["gifts"], *kept["poke_spots"]]))
        manual = baseline_rows(replace(XDOptions.recommended(), starter_species=252))
        self.assertEqual(manual["starter"]["national_dex"], 252)

    def test_xd_review_uses_shared_values_units_and_ignores_inactive_remembered_settings(self):
        for language in LANGUAGES:
            review = configuration_review(XDOptions.recommended(), language)
            self.assertIn("5 %", review)
            self.assertIn(translate("Dresseurs", language), review)
            self.assertIn(translate("Changer les Pokémon non obscurs", language), review)
            self.assertIn(translate("Familles différentes pour les obscurs", language), review)
            dormant = replace(XDOptions.unchanged(), starter_species=94, shiny_chance_percent=100,
                              early_level_multiplier=2, late_level_multiplier=2)
            self.assertEqual(configuration_review(dormant, language),
                             translate("Copie à l’identique : aucune donnée du jeu ne sera modifiée.", language))
        manual = configuration_review(replace(XDOptions.recommended(), starter_species=94))
        self.assertIn("Ectoplasma", manual)
        self.assertNotIn("Forme de base", manual)

    def test_xd_preview_plan_reuse_requires_matching_source_seed_and_game_options(self):
        options = XDOptions.recommended()
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder).resolve()
            source = root / "original.iso"
            original = b"synthetic original"
            source.write_bytes(original)
            stack.enter_context(patch.object(service, "check_header", return_value=b"header"))
            stack.enter_context(patch.object(service, "check_disc_identity", return_value=REGIONS["GXXP01"]))
            stack.enter_context(patch.object(service, "ISO_SIZE", len(original)))
            stack.enter_context(patch.object(service, "render_journal", return_value=""))
            build = stack.enter_context(patch.object(service, "build_xd_patches", return_value=([(0, b"A")], {})))
            plans = []
            preview_xd(source, "seed", options, on_prepared=plans.append)
            self.assertEqual(len(plans), 1)
            plan = plans[0]
            report = service.randomize(source, root / "reused.iso", "seed", xd_options=options, prepared_patches=plan)
            self.assertTrue(report["preview_plan_reused"])
            self.assertEqual(build.call_count, 1)
            fresh = service.randomize(source, root / "fresh.iso", "seed", xd_options=options)
            self.assertFalse(fresh["preview_plan_reused"])
            self.assertEqual((root / "reused.iso").read_bytes(), (root / "fresh.iso").read_bytes())
            self.assertEqual(build.call_count, 2)
            for index, changed in enumerate((replace(plan, seed="other"),
                                             replace(plan, source_sha256="0" * 64),
                                             replace(plan, iso_sha256="0" * 64),
                                             replace(plan, options=Options.recommended()))):
                result = service.randomize(source, root / f"fallback-{index}.iso", "seed",
                                           xd_options=options, prepared_patches=changed)
                self.assertFalse(result["preview_plan_reused"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), plan.source_sha256)
            self.assertFalse(list(root.glob(".orre-*")))


@unittest.skipIf(MainWindow is None, "requires optional Qt desktop dependencies")
class WorkspaceParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        settings = QSettings(str(self.root / "prefs.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = MainWindow(settings=settings, system_languages=["fr-FR"])

    def pump_until(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(condition())

    def tearDown(self):
        self.window.cancel_preview()
        self.pump_until(lambda: self.window.preview_thread is None)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.folder.cleanup()

    def test_presets_and_navigation_use_the_same_words_in_every_language(self):
        w, xd = self.window, self.window.xd
        for language in LANGUAGES:
            w.language_combo.setCurrentIndex(w.language_combo.findData(language))
            for step in range(3):
                w.step, xd.step = step, step
                w.refresh_navigation()
                xd.refresh_navigation()
                self.assertEqual([b.text() for b in w.step_buttons], [b.text() for b in xd.step_buttons])
                self.assertEqual(w.back_button.text(), xd.home_button.text())
            for index in range(3):
                w.set_options(w.presets[index][1]())
                xd.set_options(xd.presets[index][1]())
                self.assertEqual(w.preset_description.text(), xd.preset_note.text())
                self.assertEqual(w.preset_common.text(), xd.preset_common.text())
                self.assertEqual(w.preset_shiny.text(), xd.preset_shiny.text())
                self.assertEqual(w.review_details.text().splitlines()[0], xd.review.text().splitlines()[0])

    def test_xd_search_works_before_calculation_and_in_all_name_languages(self):
        w, xd = self.window, self.window.xd
        xd.encounter_tabs.setCurrentIndex(1)
        self.assertFalse(xd.preview_search.isHidden())
        self.assertEqual(xd.preview_details.topLevelItemCount(), 83)
        for query in ("teddiursa", "ヒメグマ", "216"):
            xd.preview_search.setText(query)
            visible = [xd.preview_details.topLevelItem(i) for i in range(83)
                       if not xd.preview_details.topLevelItem(i).isHidden()]
            self.assertEqual(len(visible), 1, query)
            self.assertIn("01", visible[0].text(0))
            self.assertEqual(visible[0].text(1), "?")
        for tab, count in ((2, 7), (3, 9)):
            xd.preview_search.clear()
            xd.encounter_tabs.setCurrentIndex(tab)
            self.assertEqual(xd.preview_details.topLevelItemCount(), count)
            self.assertFalse(xd.preview_search.isHidden())

    def test_xd_preview_is_responsive_animates_and_invalidates_all_stale_results(self):
        w, xd = self.window, self.window.xd
        w.show_xd()
        xd.step = 1
        xd.pages.setCurrentIndex(1)
        xd.workspace_tabs.setCurrentIndex(1)
        xd.encounter_tabs.setCurrentIndex(1)
        source = self.root / "source.iso"
        source.write_bytes(b"preview fixture; task mocked")
        xd.source.setText(str(source))
        w.show()
        self.app.processEvents()
        entered = threading.Event()
        def calculate(**arguments):
            entered.set()
            arguments["cancel"].wait(3)
            return {"starter": {"species": 25, "original": 133, "level": 10}}
        with patch("orre_randomizer.preview.preview_xd", side_effect=calculate):
            xd.start_preview()
            self.pump_until(entered.is_set)
            self.assertTrue(xd.preview_running)
            self.assertFalse(w.busy)
            self.assertTrue(xd.seed.isEnabled())
            self.assertTrue(xd.roulette_timer.isActive())
            xd.advance_roulette()
            item = xd.preview_details.topLevelItem(0)
            self.assertNotEqual(item.text(1), "?")
            self.assertEqual(item.data(0, Qt.ItemDataRole.UserRole + 2)["species"], None)
            xd.seed.setText("changed while loading")
            self.pump_until(lambda: w.preview_thread is None)
        self.assertIsNone(xd.preview_result)
        self.assertIsNone(xd.preview_plan)
        self.assertFalse(xd.roulette_timer.isActive())
        self.assertEqual(xd.preview_details.topLevelItem(0).text(1), "?")
        self.assertEqual(xd.preview_button.text(), "Actualiser l’aperçu")
        self.assertEqual(source.read_bytes(), b"preview fixture; task mocked")

    def test_xd_report_compares_the_original_without_changing_paths_or_the_other_game(self):
        w, xd = self.window, self.window.xd
        source = self.root / "original.iso"
        source.write_bytes(b"owned fixture; identity worker mocked")
        xd.source.setText(str(source))
        destination = xd.destination.text()
        region = REGIONS["GXXP01"]
        report = self.root / "created.iso.json"
        report.write_text(json.dumps(dict(application_version=__version__, engine_version=VERSION,
            game_id=region.game_id, revision=0, source_iso_sha256=region.iso_sha256,
            source_sha256=region.iso_sha256, seed="restored-seed", options=asdict(XDOptions.recommended()),
            source="ignored", output="ignored")), encoding="utf-8")
        with patch("orre_randomizer.gui.report_rom_matches", return_value=True) as check:
            xd.import_configuration(report, report=True)
            self.pump_until(lambda: "correspond" in xd.report_rom_status.text())
        self.assertEqual(xd.source.text(), str(source))
        self.assertEqual(xd.destination.text(), destination)
        self.assertEqual(xd.seed.text(), "restored-seed")
        self.assertIsNone(w.creation_report)
        self.assertEqual(check.call_args.args[0].region.game_id, "GXXP01")
        self.assertEqual(check.call_args.args[1], source)
        w.language_combo.setCurrentIndex(w.language_combo.findData("en"))
        self.assertIn("matches", xd.report_rom_status.text())

    def test_xd_family_warning_and_single_click_sheets_share_the_common_template(self):
        from tests.test_v15_gui_reporting import final_preview
        from PySide6.QtWidgets import QLabel
        w, xd = self.window, self.window.xd
        fixture = final_preview()
        row = dict(fixture["starters"][0], species=95, national_dex=95, original=133, shiny=True)
        data = dict(starter=row, decks={"Story": {"shadows": [dict(row, shadow_id=1, original=216)]}},
                    gifts=[dict(row, key="hordel-trade", original=239)],
                    family_duplicates=[["starter", "shadow:1", "hordel-trade"]])
        w.show_xd()
        xd.step = 1
        xd.pages.setCurrentIndex(1)
        xd.workspace_tabs.setCurrentIndex(1)
        xd.preview_key = xd.preview_configuration()
        xd.preview_result = data
        xd.render_preview()
        w.show()
        self.app.processEvents()
        self.assertTrue(xd.encounter_tabs.isTabVisible(xd.family_tab))
        self.assertIn("Onix (starter)", xd.family_duplicates.text())
        self.assertIn("color:", xd.preview_starter.text())  # shared superscript shiny marker.
        xd.starter_details.click()
        self.assertIsNotNone(w.detail_window)
        self.assertEqual(w.detail_window.tabs.count(), 3)
        self.assertTrue(w.detail_window.findChildren(QLabel, "sheetEvolutionPortrait"))
        w.detail_window.close()
        xd.encounter_tabs.setCurrentIndex(1)
        self.app.processEvents()
        index = xd.preview_details.model().index(0, 1)
        QTest.mouseClick(xd.preview_details.viewport(), Qt.MouseButton.LeftButton,
                         pos=xd.preview_details.visualRect(index).center())
        self.assertIsNotNone(w.detail_window)
        xd.encounter_tabs.setCurrentIndex(xd.family_tab)
        xd.seed.setText("stale draw")
        self.assertIsNone(w.detail_window)
        self.assertFalse(xd.encounter_tabs.isTabVisible(xd.family_tab))
        self.assertIsNone(xd.preview_result)

    def test_preflight_errors_never_expose_creation_details_in_either_game(self):
        w = self.window
        for language in LANGUAGES:
            w.language_combo.setCurrentIndex(w.language_combo.findData(language))
            statuses = []
            for owner in (w, w.xd):
                owner.step = 0
                owner.refresh_navigation()
                owner.go_step(2)
                self.assertEqual(owner.step, 0)
                self.assertTrue(owner.details.isHidden(), (language, type(owner).__name__))
                self.assertTrue(owner.log.isHidden())
                self.assertFalse(owner.creation_log.started)
                statuses.append(owner.status.text())
                owner.start()
                self.assertTrue(owner.details.isHidden())
                self.assertEqual(owner.log.toPlainText(), "")
                self.assertFalse(w.busy)
            self.assertEqual(statuses[0], statuses[1])
        self.assertFalse(w.art_note.isHidden())

    def test_real_creations_share_details_before_first_progress_and_hide_them_on_other_steps(self):
        w = self.window
        source = self.root / "creation-source.iso"
        source.write_bytes(b"owned synthetic input; creation service mocked")
        for owner in (w, w.xd):
            (w.show_colosseum if owner is w else w.show_xd)()
            owner.source.setText(str(source))
            owner.destination.setText(str(self.root / ("col-new.iso" if owner is w else "xd-new.iso")))
            entered, proceed = threading.Event(), threading.Event()
            def create(**arguments):
                entered.set()
                proceed.wait(3)
                arguments["progress"](50, "Application des réglages…")
                return {"output": str(arguments["destination"])}
            with patch("orre_randomizer.gui.randomize", side_effect=create):
                owner.start()
                self.pump_until(entered.is_set)
                self.assertTrue(w.busy)
                self.assertEqual(owner.step, 2)
                self.assertFalse(owner.details.isHidden())
                self.assertTrue(owner.log.isHidden())
                self.assertEqual(owner.log.toPlainText(), w.text("Lecture de la ROM d’origine…"))
                owner.details.click()
                self.assertFalse(owner.log.isHidden())
                w.language_combo.setCurrentIndex(w.language_combo.findData("en"))
                self.assertEqual(owner.log.toPlainText(), w.text("Lecture de la ROM d’origine…"))
                proceed.set()
                self.pump_until(lambda: w.thread is None)
            self.assertFalse(owner.details.isHidden())
            self.assertIn(w.text("Application des réglages…"), owner.log.toPlainText())
            owner.go_step(0)
            self.assertTrue(owner.details.isHidden())
            self.assertTrue(owner.log.isHidden())
            owner.source.clear()
            owner.start()
            self.assertFalse(owner.creation_log.started)
            self.assertTrue(owner.details.isHidden())
            self.assertEqual(owner.log.toPlainText(), "")

    def test_creation_failure_and_cancellation_keep_details_only_on_create(self):
        from orre_randomizer.service import Cancelled, UserError
        w = self.window
        source = self.root / "failure-source.iso"
        source.write_bytes(b"owned synthetic input; creation service mocked")
        for owner in (w, w.xd):
            (w.show_colosseum if owner is w else w.show_xd)()
            owner.source.setText(str(source))
            owner.destination.setText(str(self.root / "unused-output.iso"))
            for error in (UserError("La création a échoué. Relancez l’application, puis réessayez."),
                          Cancelled("Annulation…")):
                with patch("orre_randomizer.gui.randomize", side_effect=error):
                    owner.start()
                    self.pump_until(lambda: w.thread is None)
                self.assertTrue(owner.creation_log.started)
                self.assertFalse(owner.details.isHidden())
                self.assertIn(w.text(error.args[0]), owner.log.toPlainText())
                owner.go_step(0)
                self.assertTrue(owner.details.isHidden())
                self.assertTrue(owner.log.isHidden())
