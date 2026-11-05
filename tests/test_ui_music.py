"""Music loops on an independent channel and releases its file when stopped."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
try:
    from PySide6.QtWidgets import QApplication, QWidget
    from orre_randomizer.ui_music import MenuMusic
except ImportError:
    MenuMusic = None


@unittest.skipIf(MenuMusic is None, "requires optional Qt dependencies")
class MusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_independent_channel_loop_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"a title.wav"
            path.write_bytes(b"test fixture, not played")
            window, backend = QWidget(), Mock()
            music = MenuMusic(window, path, backend=backend)
            self.assertTrue(music.start())
            backend.open_file.assert_called_once_with(path)
            self.assertTrue(music.playing)
            backend.is_playing.return_value = True
            music.poll()
            backend.play.assert_called_once_with()
            music.stop()
            backend.close.assert_called()
            self.assertFalse(music.playing)
            self.assertFalse(music.timer.isActive())
            window.deleteLater()

    def test_failed_device_and_missing_track_remain_recoverable(self):
        window, backend = QWidget(), Mock()
        music = MenuMusic(window, None, backend=backend)
        self.assertFalse(music.start())
        backend.open_file.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"title.wav"
            path.write_bytes(b"test fixture")
            music.path = path
            backend.open_file.side_effect = OSError("no audio device")
            self.assertFalse(music.start())
            self.assertFalse(music.timer.isActive())
        window.deleteLater()
