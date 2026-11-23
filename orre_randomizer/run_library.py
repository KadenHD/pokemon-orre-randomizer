"""Local references to runs; registering or forgetting never moves game data."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

from .play_folders import load_game
from .service import UserError


def data_root():
    base = os.environ.get("ORRE_DATA_HOME")
    if base:
        return Path(base)
    base = os.environ.get("LOCALAPPDATA" if os.name == "nt" else "XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local/share") / "OrreRandomizer"


class RunLibrary:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else data_root()

    @contextmanager
    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "library.sqlite3"
        if self.root.is_symlink() or self.root.is_junction() or path.is_symlink():
            raise OSError("Linked library location")
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE IF NOT EXISTS runs (path TEXT PRIMARY KEY, name TEXT NOT NULL, "
                           "game TEXT NOT NULL, seed TEXT NOT NULL, version TEXT NOT NULL, "
                           "added REAL NOT NULL, opened REAL NOT NULL DEFAULT 0)")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def register(self, path, *, opened=False):
        path = Path(path).expanduser().resolve()
        data = load_game(path)
        key = os.path.normcase(str(path))
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET "
                       "name=excluded.name, game=excluded.game, seed=excluded.seed, version=excluded.version, "
                       "opened=CASE WHEN excluded.opened>0 THEN excluded.opened ELSE runs.opened END",
                       (key, path.parent.name, data["game"], data["seed"], data.get("orre_version", ""),
                        time.time(), time.time() if opened else 0))
        return data

    def entries(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM runs ORDER BY opened DESC, added DESC")]

    def forget(self, path):
        with self.connect() as db:
            db.execute("DELETE FROM runs WHERE path=?", (os.path.normcase(str(Path(path).resolve())),))


def window_library(window):
    """Injected INI preferences keep tests/portable UI fixtures out of personal data."""
    existing = getattr(window, "run_library", None)
    if existing is None:
        from PySide6.QtCore import QSettings
        settings = window.preferences
        root = Path(settings.fileName()).parent / "OrreLibrary" if settings.format() == QSettings.Format.IniFormat else None
        existing = window.run_library = RunLibrary(root)
    return existing


def remember_run(window, path, *, opened=False):
    # A metadata-index failure must never invalidate a successful ROM creation.
    try:
        window_library(window).register(path, opened=opened)
    except (OSError, ValueError, UserError, sqlite3.Error):
        return False
    return True
