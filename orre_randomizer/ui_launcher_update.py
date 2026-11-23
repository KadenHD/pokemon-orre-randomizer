"""Opt-in launcher updates using the incumbent neutral shared-resource surface."""
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from .launcher_updates import upgrade_launcher, upgrade_status
from .service import Cancelled, UserError
from .ui_game_folder import PACK_STYLE
from .ui_theme import MenuPanel, theme_palette


class LauncherUpdate(QThread):
    def __init__(self, path, parent):
        super().__init__(parent)
        self.path, self.cancel = path, threading.Event()
        self.result = self.error = None

    def run(self):
        try:
            self.result = upgrade_launcher(self.path, cancel=self.cancel)
        except Exception as error:
            self.error = error


class LauncherUpdateDialog(QDialog):
    def __init__(self, window, path):
        super().__init__(window)
        self.window, self.path = window, Path(path)
        self.thread = None
        self.close_after_cancel = False
        self.close_parent_after_cancel = False
        self.details = upgrade_status(self.path)
        self.setWindowTitle(window.text("Mettre à jour un lanceur…"))
        self.setFixedSize(760, 400)
        self.setPalette(theme_palette(self.palette(), home=True))
        self.setStyleSheet(PACK_STYLE)
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        panel = MenuPanel(home=True)
        body = QVBoxLayout(panel)
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)
        title = QLabel(window.text("Lanceur de la partie")); title.setObjectName("section")
        body.addWidget(title)
        name = QLabel()
        name.setText(name.fontMetrics().elidedText(self.path.parent.name, Qt.TextElideMode.ElideMiddle, 650))
        name.setToolTip(str(self.path.parent)); name.setAccessibleName(str(self.path.parent))
        body.addWidget(name)
        version = QLabel(self.details['previous_version'] + " → " + self.details['version']
                         if self.details['available'] else self.details['version'])
        version.setObjectName("subheading"); body.addWidget(version)
        for message in (
            "La ROM, les sauvegardes, les réglages et les versions des packs sont conservés.",
            "Les anciens fichiers du lanceur seront sauvegardés dans LauncherBackups/.",
            "Fermez le lanceur et Dolphin de cette partie avant de continuer.",
        ):
            label = QLabel(window.text(message)); label.setWordWrap(True); body.addWidget(label)
        body.addStretch(1)
        outer.addWidget(panel, 1)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.hide()
        outer.addWidget(self.progress)
        self.status = QLabel(window.text("Lanceur déjà à jour.") if not self.details['available'] else "")
        self.status.setWordWrap(True); outer.addWidget(self.status)
        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.done = QPushButton(window.text("Fermer")); self.done.clicked.connect(self.close)
        buttons.addWidget(self.done)
        self.update = QPushButton(window.text("Mettre à jour le lanceur"))
        self.update.setObjectName("updateDownload")
        self.update.setEnabled(self.details['available']); self.update.clicked.connect(self.start)
        buttons.addWidget(self.update); outer.addLayout(buttons)

    def start(self):
        if self.thread is not None or not self.details['available']:
            return
        self.update.setEnabled(False)
        self.done.setText(self.window.text("Annuler"))
        self.progress.setRange(0, 0); self.progress.show()
        self.status.setText(self.window.text("Préparation du nouveau lanceur…"))
        self.thread = LauncherUpdate(self.path, self)
        self.thread.finished.connect(self.finished_update)
        self.thread.start()

    def finished_update(self):
        worker, self.thread = self.thread, None
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if worker.error is None else 0)
        self.done.setText(self.window.text("Fermer")); self.done.setEnabled(True)
        if worker.error is None:
            self.details['available'] = False
            self.status.setText(self.window.text("Lanceur mis à jour. Vous pouvez rouvrir cette partie."))
        else:
            self.update.setEnabled(True)
            self.status.setText(self.window.text(str(worker.error)) if isinstance(worker.error, (UserError, Cancelled))
                                else self.window.text("Impossible de mettre à jour le lanceur."))
            self.status.setToolTip(str(worker.error))
        worker.deleteLater()
        if self.close_after_cancel:
            self.close()
        if self.close_parent_after_cancel:
            self.window.close()

    def reject(self):
        self.close()

    def closeEvent(self, event):
        if self.thread is not None:
            self.close_after_cancel = True
            self.thread.cancel.set()
            self.done.setEnabled(False)
            self.status.setText(self.window.text("Annulation en cours…"))
            event.ignore()
        else:
            event.accept()


def choose_launcher_update(window):
    existing = getattr(window, "launcher_update_dialog", None)
    if existing is not None:
        existing.raise_(); existing.activateWindow()
        return
    path, _ = QFileDialog.getOpenFileName(window, window.text("Mettre à jour un lanceur…"), "",
                                        window.text("Partie Orre (game.json)"))
    if path:
        try:
            dialog = LauncherUpdateDialog(window, Path(path))
        except (OSError, ValueError, UserError) as error:
            window.show_error(error, False)
            return
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.launcher_update_dialog = dialog
        dialog.destroyed.connect(lambda *_: setattr(window, "launcher_update_dialog", None))
        dialog.show()
