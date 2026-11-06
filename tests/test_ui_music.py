"""Music loops on an independent channel and releases its file when stopped."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
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

    def test_window_switches_tracks_and_keeps_global_music_preference(self):
        from PySide6.QtCore import QSettings
        from orre_randomizer.gui import MainWindow
        backend = Mock()
        tracks = {"home": Path("pyrite.wav"), "colosseum": Path("title.wav"), "xd": Path("xd-title.wav")}
        with tempfile.TemporaryDirectory() as directory, patch("orre_randomizer.gui.music_track", side_effect=tracks.get), \
                patch("orre_randomizer.gui.MenuMusic", side_effect=lambda parent, path: MenuMusic(parent, path, backend)):
            settings = QSettings(str(Path(directory) / "preferences.ini"), QSettings.Format.IniFormat)
            window = MainWindow(settings=settings, start_on_home=True)
            try:
                backend.open_file.assert_called_once_with(tracks["home"])
                window.show_colosseum()
                backend.open_file.assert_called_with(tracks["colosseum"])
                window.show_xd()
                backend.open_file.assert_called_with(tracks["xd"])
                window.show_xd()
                self.assertEqual(backend.open_file.call_count, 3)
                window.music_toggle.setChecked(False)
                window.show_home()
                self.assertFalse(window.music.playing)
                self.assertEqual(backend.open_file.call_count, 3)
                self.assertFalse(settings.value("interface/music", type=bool))
                window.music_toggle.setChecked(True)
                backend.open_file.assert_called_with(tracks["home"])
                window.music_tracks["xd"] = None
                window.show_xd()
                self.assertFalse(window.music_toggle.isEnabled())
                self.assertTrue(settings.value("interface/music", type=bool))
                window.show_colosseum()
                self.assertTrue(window.music_toggle.isChecked())
                backend.open_file.assert_called_with(tracks["colosseum"])
            finally:
                window.close()
