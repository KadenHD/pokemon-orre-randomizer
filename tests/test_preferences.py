"""The package rename preserves existing preferences and newer user choices."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QSettings
    from orre_randomizer.preferences import application_preferences
except ImportError:
    QSettings = None


@unittest.skipIf(QSettings is None, "requires optional Qt desktop dependencies")
class PreferenceMigrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.current = QSettings(str(root / "orre.ini"), QSettings.Format.IniFormat)
        self.legacy = QSettings(str(root / "colosseum.ini"), QSettings.Format.IniFormat)

    def tearDown(self):
        self.folder.cleanup()

    def migrate(self):
        with patch("orre_randomizer.preferences.QSettings",
                   side_effect=[self.current, self.legacy]) as constructor:
            constructor.Format = QSettings.Format
            constructor.Scope = QSettings.Scope
            constructor.Status = QSettings.Status
            return application_preferences()

    def test_language_and_disabled_audio_are_imported_once(self):
        self.legacy.setValue("interface/language", "ja")
        self.legacy.setValue("interface/music", False)
        self.legacy.setValue("interface/sounds", False)
        settings = self.migrate()
        self.assertEqual(settings.value("interface/language"), "ja")
        self.assertFalse(settings.value("interface/music", type=bool))
        self.assertFalse(settings.value("interface/sounds", type=bool))
        self.assertEqual(self.legacy.value("interface/language"), "ja")

        settings.remove("interface/music")
        self.legacy.setValue("interface/language", "de")
        self.migrate()
        self.assertEqual(settings.value("interface/language"), "ja")
        self.assertFalse(settings.contains("interface/music"))

    def test_existing_orre_preferences_take_precedence(self):
        self.current.setValue("interface/language", "en")
        self.legacy.setValue("interface/language", "fr")
        self.legacy.setValue("interface/sounds", False)
        settings = self.migrate()
        self.assertEqual(settings.value("interface/language"), "en")
        self.assertFalse(settings.value("interface/sounds", type=bool))

    def test_first_launch_uses_the_defaults_when_no_legacy_preferences_exist(self):
        settings = self.migrate()
        self.assertEqual(settings.value("interface/language", "system"), "system")
        self.assertTrue(settings.value("interface/music", True, type=bool))
        self.assertTrue(settings.value("interface/sounds", True, type=bool))
