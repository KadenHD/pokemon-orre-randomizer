"""THESIS: manage existing runs without moving their ROMs or exposing spoilers.
OWN-WORLD: incumbent neutral charcoal, silver menu frames and native Qt text.
STORY: find a run, protect its cards, review cache cleanup, or share its rules.
FIRST VIEWPORT: fixed header and actions around one bounded data table.
FORM: extensions of Home and the per-run launcher, with background file work.
"""
from datetime import datetime
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor, QPen, QPainterPath
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFileDialog,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QSizePolicy, QItemDelegate)

from .challenges import encode_challenge, decode_challenge, MAX_CODE
from .hd_packs import shared_root
from .i18n import Message
from .play_folders import load_game
from .run_library import window_library
from .save_backups import backup_cards, list_backups, restore_backup
from .service import Cancelled, UserError
from .storage import scan_storage, cleanup_caches
from .ui_game_folder import PACK_STYLE
from .ui_theme import MenuPanel, theme_palette

TOOL_STYLE = PACK_STYLE + """
QTableWidget { background: #191b1e; color: #eceef2; border: 1px solid #727782;
    selection-background-color: #30343a; selection-color: #eceef2; }
QTableWidget::item { padding: 6px; border-bottom: 1px solid #30343a; }
QHeaderView::section { background: #202327; color: #eceef2;
    border: none; border-bottom: 1px solid #727782; padding: 6px; }
QTableCornerButton::section { background: #202327; border: none; }
"""

def size_text(value):
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or suffix == "TiB":
            return f"{value:.1f} {suffix}"
        value /= 1024


class CacheCheckDelegate(QItemDelegate):
    """Keep Qt's checkable-item interaction, with an explicit neutral outline."""
    def drawCheck(self, painter, option, rect, state):
        painter.save()
        box = rect.adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#cbd0d8"), 1.5))
        painter.setBrush(QColor("#30343a" if state == Qt.CheckState.Checked else "#191b1e"))
        painter.drawRect(box)
        if state == Qt.CheckState.Checked:
            path = QPainterPath()
            path.moveTo(box.left() + box.width() * .18, box.top() + box.height() * .52)
            path.lineTo(box.left() + box.width() * .42, box.top() + box.height() * .78)
            path.lineTo(box.left() + box.width() * .84, box.top() + box.height() * .22)
            painter.setPen(QPen(QColor("#eceef2"), 2)); painter.drawPath(path)
        painter.restore()


class FileTask(QThread):
    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation, self.cancel = operation, threading.Event()
        self.result = self.error = None

    def run(self):
        try:
            self.result = self.operation(self.cancel)
        except Exception as error:
            self.error = error


class ToolDialog(QDialog):
    def __init__(self, window, title, *, width=1000, height=720):
        super().__init__(window)
        self.window, self.task, self.want_close = window, None, False
        self.setWindowTitle(window.text(title)); self.setFixedSize(width, height)
        self.setPalette(theme_palette(self.palette(), home=True)); self.setStyleSheet(TOOL_STYLE)
        self.outer = QVBoxLayout(self); self.outer.setContentsMargins(20, 20, 20, 20)
        panel = MenuPanel(home=True)
        self.body = QVBoxLayout(panel); self.body.setContentsMargins(20, 20, 20, 20); self.body.setSpacing(12)
        heading = QLabel(window.text(title)); heading.setObjectName("section")
        self.body.addWidget(heading); self.outer.addWidget(panel, 1)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.body.addWidget(self.status)
        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.hide()
        self.outer.addWidget(self.progress)
        self.footer = QHBoxLayout(); self.outer.addLayout(self.footer)
        self.footer.addStretch(1)
        self.done = self.button("Fermer", self.close); self.footer.addWidget(self.done)

    def button(self, text, callback):
        # Dialog strings are owned by the dialog, avoiding retained bindings to
        # destroyed widgets in the parent window's translation registry.
        from PySide6.QtWidgets import QPushButton
        result = QPushButton(self.window.text(text)); result.clicked.connect(callback)
        result.setCursor(Qt.CursorShape.PointingHandCursor)
        return result

    def note(self, text):
        widget = QLabel(self.window.text(text)); widget.setObjectName("note")
        widget.setWordWrap(True); widget.setTextFormat(Qt.TextFormat.PlainText)
        return widget

    def table(self, headings):
        table = QTableWidget(0, len(headings))
        table.setHorizontalHeaderLabels([self.window.text(text) for text in headings])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False); table.setWordWrap(False)
        return table

    def message(self, value):
        self.status.setText(self.window.text(value))

    def start_task(self, operation, success, *, message="Opération en cours…"):
        if self.task is not None:
            return
        self.message(message); self.progress.show(); self.body.parentWidget().setEnabled(False)
        self.saved_controls = []
        for index in range(self.footer.count()):
            widget = self.footer.itemAt(index).widget()
            if widget is not None:
                self.saved_controls.append((widget, widget.isEnabled())); widget.setEnabled(False)
        self.task = FileTask(operation, self)
        self.task.finished.connect(lambda: self.task_finished(success))
        self.task.start()

    def task_finished(self, success):
        worker, self.task = self.task, None
        self.progress.hide(); self.body.parentWidget().setEnabled(True)
        for widget, enabled in self.saved_controls:
            widget.setEnabled(enabled)
        if worker.error is not None:
            self.message(str(worker.error) if isinstance(worker.error, UserError) else "Opération impossible. Vérifiez les fichiers et réessayez.")
            self.status.setToolTip(str(worker.error))
        else:
            success(worker.result)
        worker.deleteLater()
        if self.want_close:
            self.close()

    def reject(self):
        self.close()

    def closeEvent(self, event):
        if self.task is not None:
            self.want_close = True; self.task.cancel.set()
            self.message("Annulation en cours…"); event.ignore()
        else:
            event.accept()


class LibraryDialog(ToolDialog):
    def __init__(self, window):
        super().__init__(window, "Mes parties")
        self.library = window_library(window); self.rows = []
        self.body.insertWidget(1, self.note("Retrouvez les parties créées ou ajoutées sur ce PC."))
        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText(window.text("Rechercher une partie…"))
        self.search.setAccessibleName(window.text("Rechercher une partie…")); self.search.textChanged.connect(self.filter_rows)
        bar.addWidget(self.search, 1); bar.addWidget(self.button("Ajouter une partie…", self.add_run))
        self.body.insertLayout(2, bar)
        self.list = self.table(("Partie", "Jeu", "Seed", "Version", "État"))
        self.body.insertWidget(3, self.list, 1)
        self.list.itemSelectionChanged.connect(self.selection_changed)
        self.list.cellDoubleClicked.connect(lambda _row, _column: self.play_run())
        self.location = self.note(""); self.body.insertWidget(4, self.location)
        self.location.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.open_folder = self.button("Ouvrir le dossier", self.reveal)
        self.backups = self.button("Copies de secours…", self.show_backups)
        self.forget = self.button("Retirer de la liste", self.forget_run)
        self.play = self.button("Jouer", self.play_run); self.play.setObjectName("primary")
        secondary = QHBoxLayout()
        for button in (self.open_folder, self.backups, self.forget):
            secondary.addWidget(button)
        secondary.addStretch(1); self.body.insertLayout(5, secondary)
        self.footer.insertWidget(0, self.play)
        self.refresh()

    def refresh(self):
        def operation(cancel):
            rows = self.library.entries()
            for row in rows:
                if cancel.is_set():
                    raise Cancelled("Opération annulée.")
                try:
                    data = load_game(Path(row["path"]))
                    from .launcher_updates import launcher_version
                    row.update(valid=True, game=data["game"], seed=data["seed"],
                               version=launcher_version(Path(row["path"]).parent, data))
                except (OSError, ValueError, UserError):
                    row["valid"] = False
            return rows
        self.start_task(operation, self.render, message="Chargement des parties…")

    def render(self, rows):
        self.rows = rows; self.list.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = (row["name"], "Pokémon XD" if row["game"] == "xd" else "Pokémon Colosseum",
                      row["seed"], row["version"] or "?", self.window.text("Disponible" if row["valid"] else "Introuvable"))
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text)); item.setToolTip(str(text))
                self.list.setItem(index, col, item)
            self.list.setRowHeight(index, 50)
        self.message("Ajoutez un dossier de partie pour commencer." if not rows else "Les fichiers restent dans leurs dossiers d’origine.")
        self.filter_rows()
        if rows:
            self.list.selectRow(0)
        self.selection_changed()

    def filter_rows(self):
        query = self.search.text().casefold()
        for index, row in enumerate(self.rows):
            displayed = " ".join(self.list.item(index, column).text() for column in range(4))
            self.list.setRowHidden(index, query not in displayed.casefold())
        self.selection_changed()

    def selected(self):
        index = self.list.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) and not self.list.isRowHidden(index) else None

    def selection_changed(self):
        row = self.selected()
        for button in (self.open_folder, self.backups, self.play):
            button.setEnabled(bool(row and row["valid"]))
        self.forget.setEnabled(bool(row))
        text = str(Path(row["path"]).parent) if row else ""
        self.location.setText(self.location.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, 880))
        self.location.setToolTip(text)

    def add_run(self):
        path, _ = QFileDialog.getOpenFileName(self, self.window.text("Ajouter une partie…"), "", "Orre (game.json)")
        if path:
            self.start_task(lambda cancel: self.library.register(Path(path)), lambda _: self.refresh())

    def play_run(self):
        row = self.selected()
        if row and row["valid"]:
            self.window.open_play_folder(Path(row["path"]))
            self.refresh()

    def reveal(self):
        row = self.selected()
        if row and row["valid"]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(row["path"]).parent)))

    def show_backups(self):
        row = self.selected()
        if row and row["valid"]:
            BackupDialog(self.window, Path(row["path"]).parent).exec()

    def forget_run(self):
        row = self.selected()
        if row:
            self.start_task(lambda cancel: self.library.forget(row["path"]), lambda _: self.refresh())


class BackupDialog(ToolDialog):
    def __init__(self, window, folder):
        super().__init__(window, "Copies de secours", width=900, height=600)
        self.folder, self.snapshots = Path(folder), []
        self.body.insertWidget(1, self.note("Cinq copies maximum, dans la limite de 256 MiB. Les sauvegardes rapides ne sont pas incluses."))
        self.list = self.table(("Date", "Origine de la copie", "Taille")); self.body.insertWidget(2, self.list, 1)
        self.list.itemSelectionChanged.connect(self.selection_changed)
        self.create = self.button("Créer une copie", self.create_backup)
        self.restore = self.button("Restaurer la sélection…", self.restore_selected)
        self.footer.insertWidget(0, self.create); self.footer.insertWidget(1, self.restore)
        self.refresh()

    def refresh(self):
        self.start_task(lambda cancel: list_backups(self.folder), self.render, message="Chargement des sauvegardes…")

    def render(self, snapshots):
        self.snapshots = snapshots; self.list.setRowCount(len(snapshots))
        origins = {"before-launch": "Avant lancement", "before-restore": "Avant restauration", "manual": "Copie manuelle"}
        for row, snapshot in enumerate(snapshots):
            date = datetime.fromisoformat(snapshot["created"]).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            values = (date, self.window.text(origins.get(snapshot.get("reason"), "Copie manuelle")), size_text(snapshot["bytes"]))
            for col, value in enumerate(values):
                self.list.setItem(row, col, QTableWidgetItem(value))
            self.list.setRowHeight(row, 48)
        if snapshots:
            self.list.selectRow(0)
        self.selection_changed()
        self.message("Aucune copie pour cette partie." if not snapshots else "Fermez Dolphin avant de créer ou restaurer une copie.")
        if getattr(self, "restored_message", False):
            self.message("Cartes mémoire restaurées. Les sauvegardes rapides restent inchangées.")
            self.restored_message = False

    def selection_changed(self):
        self.restore.setEnabled(0 <= self.list.currentRow() < len(self.snapshots))

    def create_backup(self):
        self.start_task(lambda cancel: backup_cards(self.folder, reason="manual"),
                        lambda name: self.refresh() if name else self.message("Aucune carte mémoire à copier. Sauvegardez d’abord dans le jeu."))

    def restore_selected(self):
        row = self.list.currentRow()
        if not 0 <= row < len(self.snapshots):
            return
        question = self.window.text("Remplacer les cartes mémoire par cette copie ? Une copie de l’état actuel sera conservée avant la restauration.")
        if QMessageBox.question(self, self.window.text("Restaurer les cartes mémoire"), question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        name = self.snapshots[row]["name"]
        self.start_task(lambda cancel: restore_backup(self.folder, name), self.restored)

    def restored(self, _result):
        self.restored_message = True
        self.refresh()


class StorageDialog(ToolDialog):
    def __init__(self, window):
        super().__init__(window, "Stockage")
        self.plan = None
        self.root = Path(getattr(window, "shared_folder_override", window.preferences.value("launcher/shared", str(shared_root()))))
        self.body.insertWidget(1, self.note("L’analyse couvre les parties de la bibliothèque et le dossier partagé sélectionné."))
        self.summary = self.note(""); self.body.insertWidget(2, self.summary)
        self.sizes = self.table(("Données", "Taille")); self.sizes.setFixedHeight(230)
        self.body.insertWidget(3, self.sizes)
        self.body.insertWidget(4, self.note("Vues de textures non référencées, créées il y a plus de 24 heures"))
        self.caches = self.table(("Cache", "Libérable estimé")); self.body.insertWidget(5, self.caches, 1)
        self.caches.setItemDelegate(CacheCheckDelegate(self.caches))
        self.caches.itemChanged.connect(self.selection_changed)
        self.body.insertWidget(6, self.note("Les ROM, cartes mémoire, packs et runtimes ne sont jamais supprimés ici. Les liens de fichiers ne sont pas comptés comme de nouvelles copies."))
        self.analyze = self.button("Analyser", self.refresh)
        self.clean = self.button("Supprimer les caches sélectionnés…", self.clean_selected); self.clean.setEnabled(False)
        self.footer.insertWidget(0, self.analyze); self.footer.insertWidget(1, self.clean)
        self.refresh()

    def refresh(self):
        library = window_library(self.window)
        self.start_task(lambda cancel: scan_storage(self.root, library.entries(), cancel=cancel),
                        self.render, message="Analyse de l’espace disque…")

    def render(self, plan):
        self.plan = plan
        self.summary.setText(self.window.text(Message("Données uniques : {used} · espace libre : {free}",
                                                    used=size_text(plan.physical_bytes), free=size_text(plan.free_bytes))))
        self.summary.setToolTip(str(plan.root))
        labels = {"roms": "ROM des parties", "saves": "Cartes et sauvegardes rapides", "backups": "Copies de secours",
                  "packs": "Packs HD", "runtimes": "Runtimes des lanceurs", "views": "Vues de textures",
                  "audio": "Ressources musicales", "downloads": "Téléchargements conservés"}
        self.sizes.setRowCount(len(labels))
        for row, (key, label) in enumerate(labels.items()):
            self.sizes.setItem(row, 0, QTableWidgetItem(self.window.text(label)))
            self.sizes.setItem(row, 1, QTableWidgetItem(size_text(plan.categories[key])))
            self.sizes.setRowHeight(row, 24)
        self.caches.blockSignals(True); self.caches.setRowCount(len(plan.candidates))
        for row, candidate in enumerate(plan.candidates):
            item = QTableWidgetItem(candidate.path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked); item.setToolTip(str(candidate.path))
            self.caches.setItem(row, 0, item)
            self.caches.setItem(row, 1, QTableWidgetItem(size_text(candidate.reclaimable_bytes)))
        self.caches.blockSignals(False); self.selection_changed()
        self.message("Cochez les caches à supprimer." if plan.candidates else "Aucun ancien cache inutilisé à supprimer.")
        if hasattr(self, "last_cleanup_count"):
            self.message(Message("Caches supprimés : {count}.", count=self.last_cleanup_count))
            del self.last_cleanup_count

    def selection_changed(self):
        self.clean.setEnabled(self.plan is not None and any(self.caches.item(row, 0).checkState() == Qt.CheckState.Checked
                              for row in range(self.caches.rowCount())))

    def clean_selected(self):
        selected = [str(candidate.path) for row, candidate in enumerate(self.plan.candidates)
                    if self.caches.item(row, 0).checkState() == Qt.CheckState.Checked]
        if not selected:
            return
        question = self.window.text(Message("Supprimer {count} caches recréables ? Les fichiers sélectionnés sont indiqués dans la liste.", count=len(selected)))
        if QMessageBox.question(self, self.window.text("Nettoyer les caches"), question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            library = window_library(self.window)
            self.start_task(lambda cancel: cleanup_caches(self.plan, selected, cancel=cancel,
                            current_entries=library.entries), self.cleaned)

    def cleaned(self, result):
        self.last_cleanup_count = len(result)
        self.refresh()


class ChallengeDialog(ToolDialog):
    def __init__(self, window, *, importing=False):
        super().__init__(window, "Importer un défi" if importing else "Partager un défi", width=860, height=560)
        self.importing = importing
        self.body.insertWidget(1, self.note("Le code contient la seed, les réglages et le moteur. Pour le même tirage, utilisez la même ROM d’origine. Aucun chemin local n’est inclus."))
        self.code = QPlainTextEdit(); self.code.setAccessibleName(window.text("Code de défi"))
        self.code.setReadOnly(not importing); self.code.setPlaceholderText(window.text("Collez le code de défi ici…"))
        self.body.insertWidget(2, self.code, 1)
        if not importing:
            owner = window.xd if window.game_views.currentWidget() is window.xd else window
            self.code.setPlainText(encode_challenge(owner.seed.text(), owner.current_options()))
        action = self.button("Importer le défi" if importing else "Copier le code", self.apply)
        action.setObjectName("primary"); self.footer.insertWidget(0, action)
        self.code.textChanged.connect(self.limit_text)

    def limit_text(self):
        if len(self.code.toPlainText()) > MAX_CODE:
            self.code.setPlainText(self.code.toPlainText()[:MAX_CODE])

    def apply(self):
        if not self.importing:
            QApplication.clipboard().setText(self.code.toPlainText())
            self.message("Code copié."); return
        if self.window.busy or self.window.home.updating:
            self.message("Attendez la fin de l’opération en cours."); return
        try:
            game, profile = decode_challenge(self.code.toPlainText())
        except UserError as error:
            self.message(str(error)); return
        if game == "xd":
            self.window.show_xd(); owner = self.window.xd
        else:
            self.window.show_colosseum(); owner = self.window
        owner.set_options(profile.options); owner.seed.setText(profile.seed); owner.creation_report = None
        self.window.schedule_report_rom_check(owner=owner if game == "xd" else None)
        owner.set_status("Défi chargé. Choisissez votre ROM d’origine.")
        self.close()


def show_library(window):
    LibraryDialog(window).exec()


def show_storage(window):
    StorageDialog(window).exec()


def show_challenge(window, *, importing=False):
    try:
        ChallengeDialog(window, importing=importing).exec()
    except (UserError, OSError) as error:
        window.show_error(error, False)
