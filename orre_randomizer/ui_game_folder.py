"""THESIS: a play folder is one visible creation choice, with shared assets.
OWN-WORLD: incumbent game forms; neutral silver for global pack management.
STORY: choose a folder, find Dolphin, select graphics, keep each party's saves.
FIRST VIEWPORT: existing wizard controls above one compact, scrollable form.
FORM: approved creation and shared-pack mockups; no replacement navigation.
"""
from pathlib import Path
import re
import threading

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout,
    QBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QPushButton,
    QStyle, QVBoxLayout, QWidget, QMenu)

from .hd_packs import PACKS, PackStore, shared_root, required_pack_games
from .i18n import Message
from .play_folders import PlayFolderRequest, find_dolphin, validate_request
from .resources import application_logo, home_logos
from .service import Cancelled, UserError
from .ui_theme import HOME_STYLE, MenuPanel, theme_palette
from .ui_workspace import scroll_area
from .ui_play_controls import VisibleChoices, separator, navigation_icon

PACK_STYLE = HOME_STYLE + """
QWidget { color: #eceef2; }
QLabel#note { color: #cbd0d8; }
QPushButton { background: #202327; color: #eceef2; border-color: #727782; }
QPushButton:hover, QPushButton:focus { background: #30343a; border-color: #cbd0d8; }
QPushButton:disabled { color: #969ba5; border-color: #626772; }
QLineEdit { background: #191b1e; border-color: #727782; selection-background-color: #535b66; }
QLineEdit:focus { border-color: #cbd0d8; }
QProgressBar { background: #191b1e; border-color: #727782; }
QProgressBar::chunk { background: #535b66; }
"""


class PlayFolderFields(QWidget):
    def __init__(self, window, owner, game):
        super().__init__()
        self.window, self.owner, self.game = window, owner, game
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.enabled = QCheckBox()
        window.bind(self.enabled.setText, "Créer un dossier de partie avec lanceur")
        self.enabled.setChecked(window.preferences.value("launcher/createFolder", True) in (True, "true", "1", 1))
        layout.addWidget(self.enabled)
        self.fields = QWidget()
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.fields)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(28)
        self.form_widget = QWidget()
        form = self.form_layout = QVBoxLayout(self.form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self.columns.addWidget(self.form_widget, 2)
        self.folder = QLineEdit()
        window.bind(self.folder.setAccessibleName, "Dossier de partie")
        window.bind(self.folder.setPlaceholderText, "Choisissez le nom d’un nouveau dossier")
        label = window.label("Dossier de partie")
        label.setObjectName("subheading")
        label.setBuddy(self.folder)
        form.addWidget(label)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        browse = window.button("Parcourir…")
        browse.clicked.connect(self.choose_folder)
        row.addWidget(browse)
        form.addLayout(row)
        form.addWidget(separator())
        self.dolphin = QLineEdit()
        preferred = window.preferences.value("launcher/dolphin", "")
        found = find_dolphin(preferred)
        self.dolphin.setText(str(found) if found else "")
        window.bind(self.dolphin.setAccessibleName, "Dolphin")
        window.bind(self.dolphin.setPlaceholderText, "Sélectionnez Dolphin.exe")
        label = window.label("Dolphin")
        label.setObjectName("subheading")
        label.setBuddy(self.dolphin)
        form.addWidget(label)
        row = QHBoxLayout()
        row.addWidget(self.dolphin, 1)
        browse = window.button("Changer…")
        browse.clicked.connect(self.choose_dolphin)
        row.addWidget(browse)
        form.addLayout(row)
        form.addWidget(window.note("Détection automatique ou choix manuel. Vos sauvegardes Dolphin habituelles restent séparées."))
        form.addWidget(separator())
        self.graphics = QComboBox()
        self.graphics.addItem("", "original")
        self.graphics.addItem("", "hd")
        window.bind(lambda value: self.graphics.setItemText(0, value), "Origine")
        window.bind(lambda value: self.graphics.setItemText(1, value), "HD")
        window.bind(self.graphics.setAccessibleName, "Graphismes")
        label = window.label("Graphismes")
        label.setObjectName("subheading")
        label.setBuddy(self.graphics)
        form.addWidget(label)
        form.addWidget(VisibleChoices(self.graphics))
        if game == "xd":
            self.hd_requirement = window.note("XD en HD nécessite les deux packs : XD pour les textures, Colosseum pour les vignettes.")
            form.addWidget(self.hd_requirement)
            self.hd_requirement.setVisible(self.graphics.currentData() == "hd")
            self.graphics.currentIndexChanged.connect(
                lambda: self.hd_requirement.setVisible(self.graphics.currentData() == "hd"))
        row = QHBoxLayout()
        row.addWidget(window.note("Dolphin et les packs HD sont partagés. Chaque partie conserve ses sauvegardes et ses réglages."), 1)
        manage = window.button("Gérer les packs HD")
        manage.clicked.connect(lambda: show_packs(window))
        row.addWidget(manage)
        form.addLayout(row)
        contents = window.note("Game/ · Launcher.exe · DolphinUser/ · Textures/ · game.json · README.txt")
        contents.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addWidget(contents)
        self.compact_contents = contents
        self.preview = QWidget()
        preview = QVBoxLayout(self.preview)
        preview.setContentsMargins(0, 0, 0, 0)
        preview.setSpacing(12)
        title = window.label("Dans ce dossier")
        title.setObjectName("subheading")
        preview.addWidget(title)
        self.rom_name = QLabel("Game/game." + owner.format.currentText().lower())
        owner.format.currentTextChanged.connect(lambda value: self.rom_name.setText("Game/game." + value.lower()))
        for label in (self.rom_name, QLabel("Launcher.exe"), QLabel("DolphinUser/"), QLabel("Textures/"), QLabel("game.json"), QLabel("README.txt")):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            frame = QWidget()
            frame.setObjectName("folderEntry")
            row = QHBoxLayout(frame)
            row.setContentsMargins(10, 7, 10, 7)
            icon = QLabel()
            kind = 'folder-fill' if label.text().endswith("/") else 'file'
            icon.setPixmap(navigation_icon(kind, xd=self.game=='xd').pixmap(24,24))
            row.addWidget(icon); row.addWidget(label, 1)
            preview.addWidget(frame)
        preview.addWidget(window.note("Sauvegardes et réglages propres à cette partie."))
        preview.addStretch(1)
        self.divider = separator(vertical=True)
        self.columns.addWidget(self.divider)
        self.columns.addWidget(self.preview, 1)
        layout.addWidget(self.fields)
        self.enabled.toggled.connect(self.fields.setVisible)
        self.enabled.toggled.connect(lambda value: window.preferences.setValue("launcher/createFolder", value))
        self.fields.setVisible(self.enabled.isChecked())
        owner.source.textChanged.connect(self.suggest_folder)
        self.suggest_folder()

    def attach_format(self, widget, output_layout):
        layout = widget.layout()
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is self.owner.format:
                layout.removeWidget(self.owner.format)
                self.format_choices = VisibleChoices(self.owner.format)
                layout.insertWidget(index, self.format_choices, 1)
                break
        def place(enabled):
            if enabled:
                output_layout.removeWidget(widget)
                self.form_layout.insertWidget(2, widget)
            else:
                self.form_layout.removeWidget(widget)
                output_layout.insertWidget(2, widget)
            widget.show()
            self.format_choices.setVisible(enabled)
            self.owner.format.setVisible(not enabled)
            if not enabled:
                layout.insertWidget(1, self.owner.format)
        self.enabled.toggled.connect(place)
        place(self.enabled.isChecked())

    def resizeEvent(self, event):
        compact = self.width() < 820
        self.preview.setVisible(not compact)
        self.divider.setVisible(not compact)
        self.compact_contents.setVisible(compact)
        super().resizeEvent(event)

    def suggest_folder(self):
        if self.folder.text().strip() or not self.owner.source.text().strip():
            return
        seed = re.sub(r"[^a-zA-Z0-9_-]", "-", self.owner.seed.text())[:24] or "New-Game"
        self.folder.setText(str(Path(self.owner.source.text()).parent / f"{'XD' if self.game == 'xd' else 'Colosseum'}-{seed}"))

    def choose_folder(self):
        current = Path(self.folder.text()) if self.folder.text() else Path.home() / "Orre-Game"
        parent = QFileDialog.getExistingDirectory(self, self.window.text("Choisir le dossier parent"), str(current.parent))
        if parent:
            self.folder.setText(str(Path(parent) / current.name))

    def choose_dolphin(self):
        path, _ = QFileDialog.getOpenFileName(self, self.window.text("Choisir Dolphin"), self.dolphin.text(), "Dolphin (Dolphin.exe dolphin-emu dolphin)")
        if path:
            self.dolphin.setText(path)
            self.window.preferences.setValue("launcher/dolphin", path)

    def request(self, source, suffix, seed):
        if not self.folder.text().strip() or not self.dolphin.text().strip():
            raise UserError("Choisissez le dossier de partie et l’exécutable Dolphin.")
        shared = Path(self.window.preferences.value("launcher/shared", str(shared_root())))
        value = PlayFolderRequest(Path(self.folder.text().strip()), Path(self.dolphin.text().strip()),
                                  self.graphics.currentData(), shared, self.window.language)
        validate_request(value, source, suffix, seed)
        self.window.preferences.setValue("launcher/dolphin", self.dolphin.text().strip())
        return value


class PackInstall(QThread):
    progress = Signal(int, object)
    succeeded = Signal(dict)
    failed = Signal(object)

    def __init__(self, store, game, parent, *, force=False):
        super().__init__(parent)
        self.store, self.game = store, game
        self.force = force
        self.cancel = threading.Event()

    def run(self):
        try:
            result = self.store.install_game(self.game, cancel=self.cancel, progress=self.progress.emit, force=self.force)
        except (Cancelled, UserError, OSError, ValueError) as error:
            self.failed.emit(error)
        except Exception:
            self.failed.emit(UserError("Le pack HD n’a pas pu être installé. Réessayez."))
        else:
            self.succeeded.emit(result)


class PackDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.thread = None
        self.close_after_cancel = self.close_parent_after_cancel = False
        window.bind(self.setWindowTitle, "Packs HD")
        self.setStyleSheet(PACK_STYLE)
        self.setPalette(theme_palette(self.palette(), home=True))
        self.setAutoFillBackground(True)
        self.setFixedSize(1000, 800)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        header = QHBoxLayout()
        logo = QLabel()
        if application_logo():
            logo.setPixmap(QPixmap(str(application_logo())).scaled(200, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo)
        header.addWidget(separator(vertical=True))
        title = window.label("Packs HD")
        title.setObjectName("section")
        title.setStyleSheet("font-size: 30px; font-weight: 700;")
        identity = QVBoxLayout()
        identity.addWidget(title)
        identity.addWidget(window.note("Une installation par jeu et par version, partagée entre vos parties."))
        header.addLayout(identity, 1)
        header.addStretch(1)
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("languageSelector")
        for index in range(window.language_combo.count()):
            self.language_combo.addItem(window.language_combo.itemText(index), window.language_combo.itemData(index))
        self.language_combo.setCurrentIndex(window.language_combo.currentIndex())
        self.language_combo.currentIndexChanged.connect(window.language_combo.setCurrentIndex)
        window.language_combo.currentIndexChanged.connect(self.language_combo.setCurrentIndex)
        header.addWidget(self.language_combo)
        outer.addLayout(header)
        panel = MenuPanel(home=True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        title = window.label("Versions validées par Orre")
        title.setObjectName("subheading")
        form.addWidget(title)
        form.addWidget(window.note("Chaque release Orre utilise des packs précis. Les parties existantes conservent leur version."))
        form.addWidget(window.note("XD en HD nécessite les deux packs : XD pour les textures, Colosseum pour les vignettes."))
        self.rows = {}
        self.row_layouts = []
        logos = home_logos()
        for game, pack in PACKS.items():
            frame = MenuPanel(home=True)
            row = QHBoxLayout(frame)
            row.setContentsMargins(16, 12, 16, 12)
            row.setSpacing(16)
            logo = QLabel()
            if game in logos:
                logo.setPixmap(QPixmap(str(logos[game])).scaled(135, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            row.addWidget(logo)
            row.addWidget(separator(vertical=True))
            text = QVBoxLayout()
            name = QLabel("Pokémon XD" if game == "xd" else "Pokémon Colosseum")
            name.setStyleSheet("font-size: 18px; font-weight: 600;")
            text.addWidget(name)
            text.addWidget(QLabel(f"{pack.version} · {pack.author}"))
            details = window.note(Message("Téléchargement : {download} Go · installé : {installed} Go",
                download=f"{sum(p.size for p in pack.parts)/1e9:.2f}", installed=f"{pack.unpacked/1e9:.2f}"))
            text.addWidget(details)
            row.addLayout(text, 1)
            status = QLabel()
            actions = QVBoxLayout()
            actions.addWidget(status)
            button = window.button("Installer")
            button.clicked.connect(lambda _checked=False, key=game: self.install(key))
            actions.addWidget(button)
            row.addLayout(actions)
            self.row_layouts.append((logo, game))
            self.rows[game] = status, button
            form.addWidget(frame)
        label = window.label("Dossier partagé")
        form.addWidget(label)
        self.path = QLineEdit(str(getattr(window, "shared_folder_override", window.preferences.value("launcher/shared", str(shared_root())))))
        label.setBuddy(self.path)
        self.path.setAccessibleName(window.text("Dossier partagé"))
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        self.browse = window.button("Changer…")
        self.browse.clicked.connect(self.choose_cache)
        row.addWidget(self.browse)
        form.addLayout(row)
        form.addWidget(separator())
        title = window.label("Vos modèles personnalisés")
        title.setObjectName("subheading")
        form.addWidget(title)
        form.addWidget(window.note("Les textures et vignettes personnalisées x4 correspondantes prennent priorité sur le pack HD, variantes chromatiques comprises."))
        form.addWidget(window.note("Le mode Origine reste disponible sans téléchargement."))
        details_button = window.button("Détails du téléchargement")
        details_dialog = QDialog(self)
        window.bind(details_dialog.setWindowTitle, "Détails du téléchargement")
        details_dialog.setFixedSize(900, 480)
        details_layout = QVBoxLayout(details_dialog)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText("\n\n".join(f"{p.game} {p.version} - {p.author}\n{p.source}\n{p.archive_source}\n"
            + "\n".join(f"{part.filename}\n{part.url}\nSHA-256: {part.sha256}"
                + "".join(f"\n{fragment.filename}\n{fragment.url}\nSHA-256: {fragment.sha256}"
                          for fragment in part.fragments) for part in p.parts)
            for p in PACKS.values()))
        details_layout.addWidget(self.details)
        done = window.button("Terminé"); done.clicked.connect(details_dialog.close)
        details_layout.addWidget(done, 0, Qt.AlignmentFlag.AlignRight)
        details_button.clicked.connect(details_dialog.show)
        details_row = QHBoxLayout()
        details_row.addWidget(details_button)
        source_button = window.button("Crédits des packs")
        source_menu = QMenu(source_button)
        for game, pack in PACKS.items():
            action = source_menu.addAction(("Pokémon XD" if game == "xd" else "Pokémon Colosseum") + " - " + pack.author)
            action.triggered.connect(lambda _checked=False, url=pack.source: QDesktopServices.openUrl(QUrl(url)))
        source_button.setMenu(source_menu)
        details_row.addWidget(source_button)
        details_row.addStretch(1)
        form.addLayout(details_row)
        self.status = QLabel()
        self.status.setObjectName("packStatus")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        store = PackStore()
        if not all(store.downloads_available(pack) for pack in PACKS.values()):
            window.bind(self.status.setText, "La source des packs HD n’est pas encore configurée.")
        form.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setObjectName("packProgress")
        self.progress.hide()
        form.addWidget(self.progress)
        form.addStretch(1)
        panel_layout.addWidget(content)
        outer.addWidget(panel, 1)
        footer = QHBoxLayout()
        self.cancel = window.button("Annuler")
        self.cancel.clicked.connect(self.cancel_install)
        self.cancel.hide()
        footer.addWidget(self.cancel)
        footer.addStretch(1)
        self.done = window.button("Terminé")
        self.done.setStyleSheet("font-size: 18px; font-weight: 600; border: 2px solid #cbd0d8; background: #30343a;")
        self.done.setFixedSize(150, 50)
        self.done.clicked.connect(self.close)
        footer.addWidget(self.done)
        outer.addLayout(footer)
        self.path.editingFinished.connect(self.save_path)
        window.language_combo.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def resizeEvent(self, event):
        logos = home_logos()
        for logo, game in getattr(self, "row_layouts", ()):
            width = 80 if self.width() < 760 else 135
            source = logos.get(game)
            if source is None:
                logo.clear()
            else:
                logo.setPixmap(QPixmap(str(source)).scaled(width, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        super().resizeEvent(event)

    def save_path(self):
        if self.thread is None and self.path.text().strip():
            self.window.preferences.setValue("launcher/shared", self.path.text().strip())
            callback = getattr(self.window, "shared_folder_changed", None)
            if callback is not None:
                callback(self.path.text().strip())
            self.refresh()

    def choose_cache(self):
        value = QFileDialog.getExistingDirectory(self, self.window.text("Dossier partagé"), self.path.text())
        if value:
            self.path.setText(value)
            self.save_path()

    def refresh(self):
        store = PackStore(Path(self.path.text()))
        for game, (status, button) in self.rows.items():
            required = [PACKS[key] for key in required_pack_games(game)]
            missing = [pack for pack in required if not store.installed(pack)]
            ready = not missing
            partial = not ready and len(missing) < len(required)
            status.setText(("✓ " if ready else "↓ ") + self.window.text("Installé" if ready else "Incomplet" if partial else "Disponible"))
            button.setText(self.window.text("Réinstaller" if ready else "Installer"))
            button.setEnabled(self.thread is None and all(store.downloads_available(pack)
                              for pack in (missing or [PACKS[game]])))
        self.path.setEnabled(self.thread is None)
        self.browse.setEnabled(self.thread is None)

    def install(self, game):
        if self.thread is not None:
            return
        self.close_after_cancel = self.close_parent_after_cancel = False
        self.save_path()
        store = PackStore(Path(self.path.text()))
        ready = all(store.installed(PACKS[key]) for key in required_pack_games(game))
        self.thread = PackInstall(store, game, self, force=ready)
        self.thread.progress.connect(self.install_progress)
        self.thread.succeeded.connect(self.install_succeeded)
        self.thread.failed.connect(self.install_failed)
        self.thread.finished.connect(self.install_finished)
        self.status.setText(self.window.text("Préparation des packs HD…"))
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel.show()
        self.done.setEnabled(False)
        self.thread.start()
        self.refresh()

    @Slot(int, object)
    def install_progress(self, value, message):
        self.progress.setRange(0, 100)
        self.progress.setValue(value)
        if self.thread is not None and not self.thread.cancel.is_set():
            self.status.setText(self.window.text(message))

    @Slot(dict)
    def install_succeeded(self, _result):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status.setText(self.window.text("Packs HD installés et vérifiés."))

    @Slot(object)
    def install_failed(self, error):
        self.progress.setRange(0, 100)
        self.status.setText(self.window.error_message(error))

    def cancel_install(self):
        if self.thread is not None:
            self.thread.cancel.set()
            self.cancel.setEnabled(False)
            self.status.setText(self.window.text("Annulation en cours…"))

    @Slot()
    def install_finished(self):
        thread, self.thread = self.thread, None
        thread.deleteLater()
        self.cancel.hide()
        self.cancel.setEnabled(True)
        self.done.setEnabled(True)
        self.refresh()
        if hasattr(self.window, "refresh_pack_status"):
            self.window.refresh_pack_status()
        if self.close_after_cancel:
            self.close()
        if self.close_parent_after_cancel:
            self.window.close()

    def closeEvent(self, event):
        if self.thread is not None:
            self.close_after_cancel = True
            self.cancel_install()
            event.ignore()
        else:
            event.accept()


def show_packs(window):
    dialog = getattr(window, "pack_dialog", None)
    if dialog is None:
        window.pack_dialog = dialog = PackDialog(window)
    dialog.refresh()
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
