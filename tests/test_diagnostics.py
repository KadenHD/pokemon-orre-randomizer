"""Exercise the real window with no pack, no ROM and private settings."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "requires optional Qt desktop dependencies")
class DiagnosticTests(unittest.TestCase):
    def test_public_window_in_all_languages_and_sizes_without_personal_settings(self):
        from orre_randomizer.diagnostics import run_checks
        self.app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("orre_randomizer.resources.bundle_root", return_value=root/"missing-pack"):
                report = run_checks(root/"diagnostics.json")
            self.assertTrue(report["successful"])
            self.assertEqual(report["images"], [])
            self.assertEqual(report["sounds"], [])
            self.assertFalse(report["music_available"])
            self.assertFalse(report["rom_opened"])
            self.assertFalse(report["personal_preferences_opened"])
            self.assertEqual(len(report["states"]), 48)
            self.assertEqual(len(report["exclusion_states"]), 24)
            self.assertEqual(len(report["consolidation_states"]), 12)
            self.assertTrue(all(state["effective_review"] and state["category_reset_isolated"]
                                and not state["source_and_rng_used"] for state in report["consolidation_states"]))
            self.assertEqual({state["language"] for state in report["states"]}, {"fr", "en", "de", "es", "it", "ja"})
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
