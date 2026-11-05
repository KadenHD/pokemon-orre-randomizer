"""Search/reset navigation never changes unrelated configuration or reveals draws."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from dataclasses import asdict,fields,replace
from pathlib import Path
import tempfile
import unittest

from orre_randomizer.i18n import LANGUAGES,translate
from orre_randomizer.options import Options
from orre_randomizer.settings_presentation import configuration_review,effective_setting_names,search_settings

try:
    from PySide6.QtCore import QCoreApplication,QEvent,QSettings,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from orre_randomizer.gui import MainWindow, recommended_preset
except ImportError:
    MainWindow=None


class SettingsPresentationTests(unittest.TestCase):
    def test_all_83_translated_labels_are_searchable(self):
        self.assertEqual(len(fields(Options)),83)
        for language in LANGUAGES:
            for field in fields(Options):
                query=translate(field.metadata['label'],language)
                names={row['name'] for row in search_settings(query,language)}
                self.assertIn(field.name,names,(language,field.name,query))

    def test_help_groups_accents_and_shiny_aliases(self):
        for query in ('shiny','shinies','chromatique','chromatiques','schillernd','variocolor','cromatico','色違い'):
            self.assertTrue({'custom_shinies','seeded_shinies','shiny_chance_percent'} <=
                {row['name'] for row in search_settings(query,'fr')},query)
        self.assertIn('evolve_trade',{r['name'] for r in search_settings('evolutions echange','fr')})
        self.assertIn('boss_stronger',{r['name'] for r in search_settings('IV','fr')})
        self.assertIn('purification_multiplier',{r['name'] for r in search_settings('リライブ','ja')})
        self.assertEqual(search_settings('unmatched998877'),[])
        self.assertEqual(search_settings(''),[])

    def test_none_review_is_exactly_copy_even_with_inactive_remembered_values(self):
        options=replace(Options.none(),starter_umbreon_species=94,starter_espeon_species=208,
            shiny_chance_percent=100,early_level_multiplier=2,late_level_multiplier=2)
        for language in LANGUAGES:
            details=configuration_review(options,language)
            self.assertEqual(details,translate('Copie à l’identique : aucune donnée du jeu ne sera modifiée.',language))

    def test_summary_lists_manual_choices_but_never_a_seed_draw(self):
        options=replace(Options.recommended(),starter_umbreon_species=94,starter_espeon_species=208)
        details=configuration_review(options,'fr')
        self.assertIn('Ectoplasma',details)
        self.assertIn('Steelix',details)
        self.assertNotIn('Forme de base',details)
        self.assertNotIn('Familles à trois stades',details)
        details=configuration_review(Options.recommended(),'fr')
        self.assertIn('Tirage avec la seed',details)
        self.assertNotIn('Ectoplasma',details)
        self.assertNotIn('Steelix',details)

    def test_effective_settings_ignore_disabled_controls_and_override(self):
        options=replace(Options.none(),evolve_trade=True,starter_umbreon_species=94,
            shiny_chance_percent=100,trainer_level_multiplier=1.8,progressive_levels=True,
            early_level_multiplier=.9,mid_level_multiplier=1.1,late_level_multiplier=1.3,
            event_pikachu_level=99,boss_shadow_min_bst=700)
        selected=effective_setting_names(options)
        for name in ('starter_umbreon_species','shiny_chance_percent','seeded_shinies',
                     'trainer_level_multiplier','event_pikachu_level','boss_shadow_min_bst'):
            self.assertNotIn(name,selected)
        for name in ('early_level_multiplier','mid_level_multiplier','late_level_multiplier'):
            self.assertIn(name,selected)
        details=configuration_review(options,'fr')
        self.assertIn('0.9',details)
        self.assertNotIn('1.8',details)
        self.assertIn('Chromatiques : règles du jeu d’origine.',details)
        self.assertNotIn('Ectoplasma',details)


@unittest.skipIf(MainWindow is None,'requires optional Qt desktop dependencies')
class SettingsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        settings=QSettings(str(Path(self.temp.name)/'prefs.ini'),QSettings.Format.IniFormat)
        settings.setValue('interface/music',False)
        settings.setValue('interface/sounds',False)
        self.window=MainWindow(settings=settings,system_languages=['fr-FR'])
        self.window.set_advanced_mode(True)
        self.window.step=1
        self.window.refresh_navigation()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.temp.cleanup()

    def test_search_opening_result_focuses_category_without_changing_values(self):
        options=replace(Options.recommended(),experience_multiplier=2,starter_umbreon_species=94)
        self.window.set_options(options)
        before=self.window.current_options()
        self.window.rule_search.setText('expérience gagnée')
        self.assertEqual(self.window.rule_content.currentIndex(),1)
        self.assertGreater(self.window.rule_results.count(),0)
        item=self.window.rule_results.item(0)
        self.window.open_rule_result(item)
        self.app.processEvents()
        self.assertEqual(self.window.rule_search.text(),'')
        self.assertEqual(self.window.rule_content.currentIndex(),0)
        self.assertEqual(self.window.rule_groups[self.window.rule_nav.currentRow()],'Niveaux et capture')
        self.assertEqual(self.window.current_options(),before)

    def test_results_retranslate_and_empty_search_recovers_form(self):
        self.window.rule_search.setText('shiny')
        before=self.window.current_options()
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.assertEqual(self.window.rule_search.text(),'shiny')
            self.assertGreater(self.window.rule_results.count(),0)
            self.assertFalse(self.window.rule_reset.isEnabled())
            self.assertEqual(self.window.current_options(),before)
        self.window.rule_search.setText('unmatched998877')
        self.assertEqual(self.window.rule_results.count(),0)
        self.assertFalse(self.window.rule_search_note.isHidden())
        self.window.rule_search.clear()
        self.assertEqual(self.window.rule_content.currentIndex(),0)
        self.assertTrue(self.window.rule_reset.isEnabled())

    def test_keyboard_search_opens_result_without_advancing_wizard(self):
        self.window.show()
        self.window.rule_search.setFocus()
        self.window.rule_search.setText('shiny')
        self.app.processEvents()
        before=self.window.current_options()
        QTest.keyClick(self.window.rule_search,Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(self.window.step,1)
        self.assertEqual(self.window.rule_content.currentIndex(),0)
        self.assertEqual(self.window.current_options(),before)
        self.window.rule_search.setText('shiny')
        QTest.keyClick(self.window.rule_search,Qt.Key.Key_Down)
        self.assertTrue(self.window.rule_results.hasFocus())
        QTest.keyClick(self.window.rule_results,Qt.Key.Key_Escape)
        self.assertEqual(self.window.rule_search.text(),'')

    def test_reset_only_current_category_uses_recommended_reference(self):
        custom=replace(Options.recommended(),experience_multiplier=3,purification_multiplier=4,
            randomize_types=True,types_family_consistent=False,custom_shinies=True,
            shiny_chance_percent=12.5,starter_umbreon_species=94,starter_espeon_species=208)
        for group in self.window.rule_groups:
            self.window.set_options(custom)
            self.window.rule_nav.setCurrentRow(self.window.rule_groups.index(group))
            self.window.seed.setText('keep-my-seed')
            before=asdict(self.window.current_options())
            self.window.reset_rule_category()
            after=asdict(self.window.current_options())
            reference=asdict(recommended_preset())
            for field in fields(Options):
                self.assertEqual(after[field.name],reference[field.name] if field.metadata['group']==group else before[field.name],(group,field.name))
            self.assertEqual(self.window.seed.text(),'keep-my-seed')
            self.assertIn('valeurs conseillées',self.window.status.text())

    def test_reset_does_not_apply_to_search_results_or_while_creating(self):
        before=self.window.current_options()
        self.window.rule_search.setText('shiny')
        self.window.reset_rule_category()
        self.assertEqual(self.window.current_options(),before)
        self.window.rule_search.clear()
        self.window.busy=True
        self.window.reset_rule_category()
        self.assertEqual(self.window.current_options(),before)
        self.window.busy=False

    def test_review_uses_configuration_only_and_cancel_copy_is_current(self):
        self.window.set_options(replace(Options.recommended(),starter_umbreon_species=94,starter_espeon_species=208))
        self.assertIn('Ectoplasma',self.window.review_details.text())
        self.assertIn('Steelix',self.window.review_details.text())
        self.assertTrue(self.window.review_details.isHidden())
        self.window.review_toggle.setChecked(True)
        self.assertFalse(self.window.review_details.isHidden())
        for language in LANGUAGES:
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.window.cancel()
            self.assertEqual(self.window.status.text(),translate('Annulation…',language))
        self.window.set_options(Options.none())
        self.assertFalse(self.window.review_toggle.isHidden())
        self.assertFalse(self.window.review_details.isHidden())
        self.assertIn(translate('Copie à l’identique : aucune donnée du jeu ne sera modifiée.',self.window.language),
                      self.window.review_details.text())


if __name__=='__main__':
    unittest.main()
