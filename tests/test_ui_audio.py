"""Optional menu playback stays local, asynchronous and quiet when disabled."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
try:
    from PySide6.QtWidgets import QApplication, QWidget
    from colosseum_randomizer.ui_audio import MenuAudio
except ImportError:
    MenuAudio = None


@unittest.skipIf(MenuAudio is None, "requires optional Qt dependencies")
class MenuAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_async_native_playback_debounces_and_mute_stops_it(self):
        window = QWidget()
        backend = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4)
        audio = MenuAudio(window, backend=backend)
        audio.set_paths({"move": Path("cached-move.wav")})
        with patch("colosseum_randomizer.ui_audio.time.monotonic", side_effect=[10, 10.01, 10.2]):
            audio.play("move")
            audio.play("move")
            self.assertEqual(backend.PlaySound.call_count, 1)
            backend.PlaySound.assert_called_with("cached-move.wav", 7)
            audio.set_enabled(False)
            audio.play("move")
        backend.PlaySound.assert_called_with(None, 0)
        self.assertEqual(backend.PlaySound.call_count, 2)
        window.deleteLater()

    def test_missing_samples_and_audio_device_do_not_interrupt_work(self):
        window = QWidget()
        backend = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4)
        audio = MenuAudio(window, backend=backend)
        audio.play("confirm")
        backend.PlaySound.assert_not_called()
        audio.set_paths({"confirm": Path("cached-confirm.wav")})
        backend.PlaySound.side_effect = RuntimeError("no audio device")
        audio.play("confirm")
        audio.set_enabled(False)
        window.deleteLater()
