"""Both import routes expose engine migrations without changing portable rules."""
from dataclasses import asdict
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer import __version__, xd
from orre_randomizer.engine.regions import REGIONS
from orre_randomizer.i18n import LANGUAGES, translate
from orre_randomizer.profiles import ENGINE_MIGRATION, PREVIOUS_PRESERVED_ENGINE, PREVIOUS_XD_PRESERVED_ENGINE
from tests.test_forecast_profiles import encode, profile_payload, sign

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtWidgets import QApplication
    from orre_randomizer.gui import MainWindow
except ImportError:
    MainWindow = None


@unittest.skipIf(MainWindow is None, "requires optional Qt desktop dependencies")
class ForecastProfileUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_both_games_warn_on_old_profile_or_report_and_translate_the_notice(self):
        with tempfile.TemporaryDirectory() as folder, patch("orre_randomizer.gui.UpdateChecker.check_once"):
            settings = QSettings(str(Path(folder) / "preferences.ini"), QSettings.Format.IniFormat)
            settings.setValue("interface/music", False)
            settings.setValue("interface/sounds", False)
            window = MainWindow(settings=settings, system_languages=["fr-FR"])
            try:
                for is_xd in (False, True):
                    (window.show_xd if is_xd else window.show_colosseum)()
                    panel = window.xd if is_xd else window
                    panel.source.clear()
                    for report in (False, True):
                        for previous in (False, True):
                            payload, options = profile_payload(is_xd, False)
                            if previous:
                                payload["engine_version"] = PREVIOUS_XD_PRESERVED_ENGINE if is_xd else PREVIOUS_PRESERVED_ENGINE
                            if report:
                                region = xd.REGIONS["GXXP01"] if is_xd else REGIONS[0]
                                payload = dict(application_version=__version__, engine_version=payload["engine_version"],
                                               game_id=region.game_id, revision=region.revision,
                                               source_sha256="a" * 64, source_iso_sha256=region.iso_sha256,
                                               seed=payload["seed"], options=asdict(options))
                            else:
                                sign(payload)
                            path = Path(folder) / "import.json"
                            path.write_bytes(encode(payload))
                            for language in LANGUAGES:
                                with self.subTest(xd=is_xd, report=report, previous=previous, language=language):
                                    window.language_combo.setCurrentIndex(window.language_combo.findData(language))
                                    (window.import_creation_report if report else window.import_profile)(path)
                                    self.assertEqual(panel.current_options(), options)
                                    self.assertEqual(panel.seed.text(), "Forecast-seed")
                                    expected = translate(ENGINE_MIGRATION, language)
                                    if previous:
                                        self.assertEqual(panel.status.text(), expected)
                                    else:
                                        self.assertNotEqual(panel.status.text(), expected)
            finally:
                window.close()
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
