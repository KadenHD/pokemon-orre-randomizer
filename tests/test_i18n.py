"""Language detection, complete catalogs and presentation-only formatting."""
import ast
from dataclasses import fields
from pathlib import Path
from string import Formatter
import unittest

from colosseum_randomizer.i18n import (CATALOGS, LANGUAGES, Message, language_preference,
                                       resolve_language, translate)
from colosseum_randomizer.locales.en import OPTION_TEXTS
from colosseum_randomizer.locales import de, en, es, it, ja
from colosseum_randomizer.options import Options
from colosseum_randomizer.service import UserError, validate_options

ROOT = Path(__file__).resolve().parents[1]


class TranslationTests(unittest.TestCase):
    def test_system_language_priority_regions_and_english_fallback(self):
        for tags, expected in ((["fr-Latn-CA", "en-US"], "fr"), (["en_GB", "fr-FR"], "en"),
                               (["de-DE", "FR-fr"], "de"), (["es-MX"], "es"),
                               (["it_CH"], "it"), (["ja-JP", "en-US"], "ja"),
                               (["JA_jp"], "ja"), (["ja-Jpan-JP"], "ja"), (["ko-KR"], "en"), ([], "en")):
            self.assertEqual(resolve_language("system", tags), expected)
        self.assertEqual(resolve_language("en", ["fr-FR"]), "en")
        self.assertEqual(resolve_language("fr", ["en-US"]), "fr")
        self.assertEqual(resolve_language("ja", ["fr-FR"]), "ja")

    def test_invalid_preference_recovers_to_system(self):
        for value in (None, "ko", "FR", "", 1, ["fr"]):
            self.assertEqual(language_preference(value), "system")
            self.assertEqual(resolve_language(value, ["fr-FR"]), "fr")

    def test_option_labels_help_and_choices_are_completely_translated(self):
        self.assertEqual(set(OPTION_TEXTS), {item.name for item in fields(Options)})
        self.assertEqual(set(LANGUAGES), {"fr", "en", "de", "es", "it", "ja"})
        for locale in (de, es, it, ja):
            self.assertEqual(set(locale.OPTION_TEXTS), set(en.OPTION_TEXTS))
            self.assertEqual(set(locale.TEXTS), set(en.TEXTS))
        for language, catalog in CATALOGS.items():
            self.assertEqual(set(catalog), set(CATALOGS["en"]))
            for item in fields(Options):
                for key in ("label", "description", "group"):
                    self.assertIn(item.metadata[key], catalog, language)
                for _, label in item.metadata.get("choices", ()):
                    self.assertIn(label, catalog, language)

    def test_placeholders_and_format_specifiers_match_in_every_catalog_entry(self):
        def placeholders(text):
            return sorted((name, spec, conversion) for _, name, spec, conversion in Formatter().parse(text)
                          if name is not None)
        for language, catalog in CATALOGS.items():
            for source, target in catalog.items():
                with self.subTest(language=language, source=source):
                    self.assertTrue(target)
                    self.assertEqual(placeholders(source), placeholders(target))

    def test_static_ui_and_recoverable_pipeline_messages_have_no_catalog_gaps(self):
        messages = set()
        for filename in ("gui.py", "xd_ui.py", "service.py", "profiles.py", "preview.py",
                         "ui_exclusions.py", "engine/trainer_policies.py"):
            tree = ast.parse((ROOT / "colosseum_randomizer" / filename).read_text("utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                index = 1 if function == "bind" else 0
                if function in {"label", "note", "button", "bind", "text", "set_status", "UserError", "Cancelled", "Message"}:
                    if len(node.args) > index and isinstance(node.args[index], ast.Constant) and isinstance(node.args[index].value, str):
                        messages.add(node.args[index].value)
                if function == "progress" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    messages.add(node.args[1].value)
        self.assertGreater(len(messages), 80)
        for language, catalog in CATALOGS.items():
            self.assertEqual(sorted(messages - catalog.keys()), [], language)

    def test_nested_messages_translate_but_paths_and_seeds_are_literal(self):
        path = "C:/étoile/{seed}/Créer la ROM randomisée.iso"
        message = Message("Profil enregistré : {path}.", path=path)
        self.assertIn(path, translate(message, "en"))
        self.assertIn(path, translate(message, "ja"))
        error = UserError("Choix inconnu : {label}.", label=Message("Choix des capacités"))
        nested = Message("Import impossible : {error}", error=error.args[0])
        self.assertEqual(translate(nested, "en"), "Import failed: Unknown choice: Move selection.")
        self.assertEqual(translate(nested, "ja"), "読み込みできません：「わざの選び方」の選択値が不正です。")
        self.assertIsInstance(message, str)
        self.assertEqual(str(message), translate(message, "fr"))
        self.assertEqual(translate("unmapped technical detail {x}", "en"), "unmapped technical detail {x}")

    def test_typed_validation_error_keeps_a_translatable_option_label(self):
        from dataclasses import replace
        with self.assertRaises(UserError) as caught:
            validate_options(replace(Options(), boss_shadow_min_bst=999))
        self.assertEqual(translate(caught.exception.args[0], "en"),
                         "Value out of range: Minimum Shadow base stat total.")


if __name__ == "__main__":
    unittest.main()
