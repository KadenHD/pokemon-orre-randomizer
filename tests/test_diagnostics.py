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
    def test_existing_or_invalid_report_path_is_refused_without_opening_the_gui(self):
        from orre_randomizer.diagnostics import main
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / 'existing.json'
            report.write_text('preserve earlier evidence')
            with patch('orre_randomizer.diagnostics.run_checks') as checked:
                self.assertEqual(main([str(report)]), 2)
                self.assertEqual(main([str(root / 'missing/report.json')]), 2)
                checked.assert_not_called()
            self.assertEqual(report.read_text(), 'preserve earlier evidence')

    def test_public_window_in_all_languages_and_sizes_without_personal_settings(self):
        from orre_randomizer.diagnostics import run_checks
        self.app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("orre_randomizer.resources.bundle_root", return_value=root/"missing-pack"), \
                 patch("orre_randomizer.ui_updates.QNetworkAccessManager.get",
                       side_effect=AssertionError("Offline diagnostics must not issue HTTP requests")) as network:
                report = run_checks(root/"diagnostics.json", screenshots=True, screenshot_scope="smoke")
            network.assert_not_called()
            self.assertTrue(report["successful"])
            tools = report["run_management_check"]
            self.assertTrue(tools["sqlite_roundtrip"] and tools["card_restore_verified"])
            self.assertEqual(tools["challenge_roundtrips"], 2)
            self.assertEqual(len(tools["dialogs"]), 4)
            self.assertFalse(tools["personal_runs_opened"] or tools["emulator_started"])
            self.assertEqual(report["images"], [])
            self.assertEqual(report["sounds"], [])
            self.assertFalse(report["music_available"])
            self.assertFalse(report["rom_opened"])
            self.assertFalse(report["personal_preferences_opened"])
            self.assertEqual(report["automatic_update_check"], {
                "closed": True, "started": False, "reply_created": False, "timer_active": False})
            self.assertEqual(report["screenshot_capture"], {
                "enabled": True, "scope": "smoke", "rendered": 474, "saved": 210,
                "rendered_without_png": 264})
            self.assertEqual(len(report["states"]), 48)
            self.assertEqual(len(report["exclusion_states"]), 24)
            self.assertEqual(len(report["consolidation_states"]), 12)
            self.assertTrue(all(state["effective_review"] and state["category_reset_isolated"]
                                and not state["source_and_rng_used"] for state in report["consolidation_states"]))
            self.assertEqual({state["language"] for state in report["states"]}, {"fr", "en", "de", "es", "it", "ja"})
            self.assertEqual(len(list(root.glob("*.png"))), 210)
            self.assertFalse(list(root.rglob("*.ini")))

    def test_screenshot_cli_keeps_all_captures_by_default_and_smoke_is_explicit(self):
        from orre_randomizer.diagnostics import main
        for arguments, expected in ((["--screenshots"], "all"),
                                    (["--screenshots", "--screenshot-scope", "smoke"], "smoke")):
            with self.subTest(scope=expected), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "diagnostics.json"
                with patch("orre_randomizer.diagnostics.run_checks", return_value={"successful": True}) as run:
                    self.assertEqual(main([str(path), *arguments]), 0)
                run.assert_called_once_with(path, screenshots=True, screenshot_scope=expected)

    def test_disposable_launcher_upgrade_is_explicit_and_failures_fail_the_report(self):
        import json
        from orre_randomizer.diagnostics import main
        for enabled in (False, True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "diagnostics.json"
                arguments = [str(path)] + (["--launcher-upgrade-check"] if enabled else [])
                with patch("orre_randomizer.diagnostics.run_checks", return_value={"successful": True}), \
                     patch("orre_randomizer.diagnostics.check_launcher_upgrades",
                           side_effect=RuntimeError("synthetic upgrade failed")) as upgrade:
                    self.assertEqual(main(arguments), 1 if enabled else 0)
                self.assertEqual(upgrade.call_count, int(enabled))
                self.assertEqual(json.loads(path.read_text())["successful"], not enabled)


if __name__ == "__main__":
    unittest.main()
