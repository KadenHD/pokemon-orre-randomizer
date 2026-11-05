"""Quiet, optional native menu feedback. Samples live in the exported local interface pack."""
from __future__ import annotations

import sys
import time
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QAbstractButton, QComboBox, QListWidget, QWidget

if sys.platform == "win32":
    import winsound
else:
    winsound = None


class MenuAudio(QObject):
    def __init__(self, window, enabled=True, backend=None):
        super().__init__(window)
        self.window = window
        self.enabled = enabled
        self.backend = backend if backend is not None else winsound
        self.paths = {}
        self.last_play = 0.0

    @property
    def supported(self):
        return self.backend is not None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled and self.backend is not None:
            try:
                self.backend.PlaySound(None, 0)
            except (RuntimeError, OSError):
                pass

    def set_paths(self, paths):
        self.paths = dict(paths)

    def play(self, name):
        now = time.monotonic()
        if (not self.enabled or self.backend is None or name not in self.paths or
                now - self.last_play < (0.09 if name == "move" else 0.035)):
            return
        try:
            self.backend.PlaySound(str(self.paths[name]), self.backend.SND_FILENAME |
                                   self.backend.SND_ASYNC | self.backend.SND_NODEFAULT)
        except (RuntimeError, OSError):
            return  # An unavailable audio device never interrupts a ROM job.
        self.last_play = now

    def attach(self):
        for button in self.window.findChildren(QAbstractButton):
            button.clicked.connect(lambda checked=False, widget=button:
                                   self.play(widget.property("menuSound") or "confirm"))
        for combo in self.window.findChildren(QComboBox):
            combo.activated.connect(lambda index: self.play("confirm"))
        for listing in self.window.findChildren(QListWidget):
            listing.currentRowChanged.connect(lambda index: self.play("move"))
            listing.setMouseTracking(True)
            listing.itemEntered.connect(lambda item: self.play("move"))
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.Enter and isinstance(watched, QAbstractButton) and
                self.window.isAncestorOf(watched) and watched.isEnabled() and
                watched.property("menuSound") != "silent"):
            self.play("move")
        if (event.type() == QEvent.Type.FocusIn and isinstance(watched, QWidget) and
                self.window.isAncestorOf(watched) and event.reason() in
                (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)):
            self.play("move")
        return False

    def close(self):
        QApplication.instance().removeEventFilter(self)
        self.set_enabled(False)
