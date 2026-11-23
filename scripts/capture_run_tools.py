"""Capture native run-management widgets with labeled synthetic, private data."""
from pathlib import Path
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from orre_randomizer.gui import MainWindow
from orre_randomizer.run_library import window_library
from orre_randomizer.save_backups import backup_cards
from orre_randomizer.ui_run_tools import LibraryDialog, BackupDialog, StorageDialog, ChallengeDialog
from orre_randomizer.ui_play import GameLauncher
from tests.test_run_management import game_fixture


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    if os.name == "nt":
        fonts = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "YuGothR.ttc"):
            QFontDatabase.addApplicationFont(str(fonts / name))
    app.setFont(QFont("Segoe UI", 10))
    results = []
    def wait(dialog):
        deadline = time.monotonic() + 12
        while dialog.task is not None:
            app.processEvents(); QTest.qWait(5)
            if time.monotonic() > deadline:
                raise RuntimeError("UI fixture worker deadline")
        app.processEvents()
    def capture(widget, name):
        widget.show(); app.processEvents(); widget.layout().activate(); QTest.qWait(40)
        path = output / (name + ".png")
        assert widget.grab().save(str(path))
        minimum = widget.layout().minimumSize()
        results.append({"image": str(path), "minimum": [minimum.width(), minimum.height()],
                        "size": [widget.width(), widget.height()], "synthetic": True})
    with tempfile.TemporaryDirectory(prefix="orre-ui-demo-") as temporary, \
         patch("orre_randomizer.run_safety.dolphin_arguments", return_value=[]):
        root = Path(temporary)
        settings = QSettings(str(root / "preferences.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False); settings.setValue("interface/sounds", False)
        settings.setValue("launcher/shared", str(root / "Shared"))
        window = MainWindow(settings=settings, system_languages=["en"], start_on_home=True, allow_update_checks=False)
        window.resize(1040, 800)
        window.seed.setText("orre-weekend")
        folders = {}
        for game in ("colosseum", "xd"):
            folder, data = game_fixture(root, game)
            data["dolphin"] = str(root / "Dolphin.exe"); data["features"] = {}
            data["language"] = "en"; data["seed"] = "orre-weekend" if game == "colosseum" else "friends-2026"
            (folder / "game.json").write_text(json.dumps(data), "utf-8")
            folders[game] = folder
            window_library(window).register(folder / "game.json", opened=game == "xd")
        (root / "Dolphin.exe").write_bytes(b"Synthetic UI fixture, never executed")
        card = folders["colosseum"] / "DolphinUser/GC/MemoryCardA.EUR.raw"
        for index in range(3):
            card.write_bytes(("Synthetic card state " + str(index)).encode() * 8192)
            backup_cards(folders["colosseum"])
        pack = root / "Shared/TexturePacks/colosseum-2.00/Textures"
        pack.mkdir(parents=True); source = pack / "tex1_128x128_demo.png"
        source.write_bytes(b"Synthetic shared resource, not a game texture" * 4096)
        view = root / "Shared/TextureViews/colosseum-2.00-GC6P01-demo"
        target = view / "Load/Textures/GC6P01"; target.mkdir(parents=True)
        os.link(source, target / source.name)
        marker = view / "complete.json"; marker.write_text('{"pack":"colosseum-2.00"}')
        os.utime(marker, (time.time() - 90000,) * 2)
        for language in ("en", "fr", "ja"):
            window.language_combo.setCurrentIndex(window.language_combo.findData(language))
            window.show_home()
            capture(window, "home-" + language)
            for cls, args, kwargs, name in (
                (LibraryDialog, (), {}, "library"),
                (BackupDialog, (folders["colosseum"],), {}, "backups"),
                (StorageDialog, (), {}, "storage"),
                (ChallengeDialog, (), {}, "challenge"),
            ):
                dialog = cls(window, *args, **kwargs); wait(dialog)
                if cls is LibraryDialog:
                    # Public documentation uses an explicit demonstration path.
                    dialog.location.setText("D:/Orre/Games/XD-Friends")
                capture(dialog, name + "-" + language)
                dialog.close(); dialog.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        for game, folder in folders.items():
            launcher = GameLauncher(folder / "game.json", preferences=settings)
            capture(launcher, "launcher-" + game)
            launcher.close(); launcher.deleteLater()
        window.close(); window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    (output / "capture-report.json").write_text(json.dumps(results, indent=2), "utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/run-management-qa/round1")
