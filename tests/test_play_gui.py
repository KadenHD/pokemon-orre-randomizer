"""The shared creation choice and per-game launcher use real Qt controls."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
from orre_randomizer.hd_packs import PACKS
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QScrollArea
from PySide6.QtGui import QFontDatabase, QFont
from orre_randomizer.gui import MainWindow
from orre_randomizer.i18n import CATALOGS, LANGUAGES, translate
from orre_randomizer.ui_play import GameLauncher
from orre_randomizer.ui_game_folder import PackDialog
from orre_randomizer.play_folders import create_game_folder
from orre_randomizer.play_music import MusicCapability


class PlayGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if os.name == "nt":
            fonts = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
            for name in ("segoeui.ttf", "YuGothR.ttc"):
                QFontDatabase.addApplicationFont(str(fonts / name))
            cls.app.setFont(QFont("Segoe UI", 10))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = QSettings(str(self.root / "prefs.ini"), QSettings.Format.IniFormat)
        self.settings.setValue("interface/music", False); self.settings.setValue("interface/sounds", False)
        self.settings.setValue("launcher/shared", str(self.root / "Shared"))
        self.update = patch("orre_randomizer.gui.UpdateChecker.check_once"); self.update.start(); self.addCleanup(self.update.stop)
        self.window = MainWindow(settings=self.settings, system_languages=["en-US"])

    def tearDown(self):
        self.window.busy = False
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_new_game_folder_is_default_and_rom_only_remains_available(self):
        for owner in (self.window, self.window.xd):
            self.assertTrue(owner.play_folder.enabled.isChecked())
            self.assertTrue(owner.rom_output_fields.isHidden())
            owner.play_folder.enabled.setChecked(False)
            self.assertFalse(owner.rom_output_fields.isHidden())

    def test_both_games_send_their_own_options_to_the_folder_worker(self):
        source = self.root / "original.gcm"; source.write_bytes(b"synthetic; worker mocked")
        dolphin = self.root / "Dolphin.exe"; dolphin.write_bytes(b"fake; never executed")
        for owner, show in ((self.window, self.window.show_colosseum), (self.window.xd, self.window.show_xd)):
            self.window.busy = False; show()
            owner.source.setText(str(source)); owner.format.setCurrentText("GCM")
            owner.play_folder.folder.setText(str(self.root / ("xd-party" if owner is self.window.xd else "colo-party")))
            owner.play_folder.dolphin.setText(str(dolphin))
            with patch.object(self.window, "start_worker") as worker:
                owner.start()
            self.assertTrue(worker.called)
            arguments = worker.call_args.args[0]
            self.assertEqual(worker.call_args.kwargs["task"], create_game_folder)
            self.assertEqual(arguments["destination"].suffix, ".gcm")
            self.assertEqual("xd_options" in arguments, owner is self.window.xd)
            self.assertEqual(arguments["request"].dolphin, dolphin)

    def test_launcher_controls_and_notes_have_all_six_languages(self):
        game = self.root / "Party"; (game / "Game").mkdir(parents=True)
        (game / "Game/game.iso").write_bytes(b"owned synthetic ROM")
        dolphin = self.root / "Dolphin.exe"; dolphin.write_bytes(b"fake")
        data = {"schema": 1, "game": "xd", "game_id": "GXXP01", "seed": "test", "rom": "Game/game.iso",
            "dolphin": str(dolphin), "shared": str(self.root / "Shared"), "pack": PACKS["xd"].key, "language": "en",
            "settings": {"graphics": "original", "speed": 1, "native_music": False}}
        path = game / "game.json"; path.write_text(json.dumps(data))
        launcher = GameLauncher(path, preferences=self.settings)
        try:
            for _, key in launcher._text_bindings:
                self.assertTrue(key in CATALOGS["en"], key)
                for language in LANGUAGES:
                    if language != "fr":
                        self.assertTrue(key in CATALOGS[language], (key, language))
            for language in LANGUAGES:
                launcher.language_combo.setCurrentIndex(launcher.language_combo.findData(language))
                launcher.show(); self.app.processEvents()
                self.assertEqual(launcher.play.text(), translate("Jouer", language))
                self.assertEqual(launcher.speed.currentData(), 1)
                self.assertFalse(launcher.findChildren(QScrollArea))
                self.assertLessEqual(launcher.layout().minimumSize().height(), launcher.height())
                self.assertEqual(launcher.minimumSize(), launcher.maximumSize())
            launcher.language_combo.setCurrentIndex(launcher.language_combo.findData("en"))
            launcher.graphics.setCurrentIndex(launcher.graphics.findData("hd"))
            with patch("orre_randomizer.hd_packs.PackStore.installed", side_effect=lambda pack: pack.game == "xd"):
                launcher.refresh_pack_status()
                self.assertEqual(launcher.pack_status.text(), translate("Packs HD à installer", "en"))
                self.assertEqual(launcher.pack_status.toolTip(), "Pokémon Colosseum")
            with patch("orre_randomizer.hd_packs.PackStore.installed", return_value=True):
                launcher.refresh_pack_status()
                self.assertEqual(launcher.pack_status.text(), translate("Packs HD installés", "en"))
                self.assertEqual(launcher.pack_status.toolTip(), "")
        finally:
            launcher.close(); launcher.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_fixed_hd_manager_fits_all_languages_without_page_scrolling(self):
        dialog = PackDialog(self.window)
        try:
            dialog.show()
            for language in LANGUAGES:
                dialog.language_combo.setCurrentIndex(dialog.language_combo.findData(language))
                self.app.processEvents()
                self.assertFalse(dialog.findChildren(QScrollArea))
                self.assertLessEqual(dialog.layout().minimumSize().height(), dialog.height(), language)
                self.assertLessEqual(dialog.layout().minimumSize().width(), dialog.width(), language)
                self.assertEqual(dialog.minimumSize(), dialog.maximumSize())
        finally:
            dialog.close(); dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_manager_distinguishes_published_catalog_from_an_unconfigured_source(self):
        for available in (True, False):
            with self.subTest(available=available), patch(
                    "orre_randomizer.hd_packs.PackStore.downloads_available", return_value=available):
                dialog = PackDialog(self.window)
                try:
                    expected = "" if available else translate("La source des packs HD n’est pas encore configurée.", "en")
                    self.assertEqual(dialog.status.text(), expected)
                finally:
                    dialog.close(); dialog.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_xd_manager_requires_both_packs_and_installs_missing_dependencies(self):
        dialog = PackDialog(self.window)
        try:
            with patch("orre_randomizer.hd_packs.PackStore.downloads_available", return_value=True):
                for installed in (set(), {"xd"}, {"colosseum"}, {"xd", "colosseum"}):
                    with self.subTest(installed=installed), patch("orre_randomizer.hd_packs.PackStore.installed",
                            side_effect=lambda pack: pack.game in installed):
                        dialog.refresh()
                        status, button = dialog.rows["xd"]
                        self.assertIn(translate("Installé" if len(installed) == 2 else "Incomplet" if installed else "Disponible", "en"), status.text())
                        self.assertEqual(button.text(), translate("Réinstaller" if len(installed) == 2 else "Installer", "en"))
                        self.assertTrue(button.isEnabled())
                with patch("orre_randomizer.hd_packs.PackStore.installed", side_effect=lambda pack: pack.game == "xd"), \
                     patch("orre_randomizer.ui_game_folder.PackInstall") as worker:
                    dialog.install("xd")
                    self.assertEqual(worker.call_args.args[1], "xd")
                    self.assertFalse(worker.call_args.kwargs["force"])
                    worker.return_value.start.assert_called_once()
                dialog.thread = None
            with patch("orre_randomizer.hd_packs.PackStore.installed", side_effect=lambda pack: pack.game == "xd"), \
                 patch("orre_randomizer.hd_packs.PackStore.downloads_available", side_effect=lambda pack: pack.game == "xd"):
                dialog.refresh()
                self.assertFalse(dialog.rows["xd"][1].isEnabled())
        finally:
            dialog.thread = None
            dialog.close(); dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_unvalidated_audio_cannot_be_enabled_from_a_saved_manifest(self):
        game = self.root / "Audio party"; (game / "Game").mkdir(parents=True)
        (game / "Game/game.iso").write_bytes(b"fixture")
        data = {"schema":1, "game":"colosseum", "game_id":"GC6P01", "seed":"test",
            "rom":"Game/game.iso", "dolphin":str(self.root/"Dolphin.exe"),
            "shared":str(self.root/"Shared"), "pack":PACKS["colosseum"].key, "language":"en",
            "settings":{"graphics":"original", "speed":2, "native_music":True},
            "features":{"music":{"enabled":True}}}
        path = game / "game.json"; path.write_text(json.dumps(data))
        with patch("orre_randomizer.play_music.music_capability",
                   return_value=MusicCapability(True, "experimental", "pending", True, False)):
            launcher = GameLauncher(path, preferences=self.settings)
        try:
            self.assertFalse(launcher.native_music.isEnabled())
            self.assertFalse(launcher.native_music.isChecked())
        finally:
            launcher.close(); launcher.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
