"""Frozen-app diagnostics must reject errors raised in real Qt callbacks."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QObject, Signal

from orre_randomizer import diagnostics


class DiagnosticEventErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_real_qt_slot_failure_fails_the_report(self):
        class Emitter(QObject):
            trigger = Signal()

        def bad_slot():
            raise RuntimeError("Destroyed dialog callback")

        def exercise_callback(*_args, **_kwargs):
            emitter = Emitter()
            emitter.trigger.connect(bad_slot)
            emitter.trigger.emit()
            return {"successful": True}

        previous_hook = sys.excepthook
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostic.json"
            with patch.object(diagnostics, "run_checks", side_effect=exercise_callback):
                self.assertEqual(diagnostics.main([str(path)]), 1)
            result = json.loads(path.read_text("utf-8"))
            self.assertFalse(result["successful"])
            self.assertIn("Destroyed dialog callback", result["error"])
        self.assertIs(sys.excepthook, previous_hook)

    def test_success_and_existing_evidence_are_preserved(self):
        previous_hook = sys.excepthook
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostic.json"
            with patch.object(diagnostics, "run_checks", return_value={"successful": True}):
                self.assertEqual(diagnostics.main([str(path)]), 0)
                original = path.read_bytes()
                result = json.loads(original)
                self.assertEqual(result["unhandled_event_errors"], [])
                self.assertEqual(diagnostics.main([str(path)]), 2)
                self.assertEqual(path.read_bytes(), original)
        self.assertIs(sys.excepthook, previous_hook)


if __name__ == "__main__":
    unittest.main()
