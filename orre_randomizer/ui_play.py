"""THESIS: reopen one party and play, without reopening the randomizer wizard.
OWN-WORLD: existing game palettes, clipped frames and shared native Qt controls.
STORY: choose graphics, keep controls/audio, launch the isolated Dolphin profile.
FIRST VIEWPORT: game identity above fixed settings; Play stays visible without page scrolling.
FORM: approved per-ROM launcher mockup, with working state and recovery feedback.
"""
from pathlib import Path
import subprocess
import sys
import threading

from PySide6.QtCore import QLocale, QTimer, QThread, Qt, QUrl, Signal, QSize
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QBoxLayout, QCheckBox, QComboBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QStyle, QVBoxLayout, QWidget)

from . import APP_NAME
from .i18n import LANGUAGES, Message, resolve_language, translate
from .play_folders import PlayLock, _write_ini, configure_profile, launch_command, load_game, save_game, validate_dolphin
from .preferences import application_preferences
from .resources import application_icon, home_logos, interface_assets
from .service import Cancelled, UserError
from .ui_game_folder import show_packs
from .ui_theme import GameSurface, MenuPanel, STYLE, XD_STYLE, theme_palette
from .ui_workspace import scroll_area
from .ui_play_controls import ControllerDiagram, VisibleChoices, separator, navigation_icon


class LaunchPreparation(QThread):
    succeeded = Signal(list, dict)
    failed = Signal(object)

    def __init__(self, folder, manifest, parent):
        super().__init__(parent)
        self.folder, self.manifest = folder, manifest
        self.cancel = threading.Event()
        self.session_context = {}

    def run(self):
        try:
            command = launch_command(self.folder, self.manifest, cancel=self.cancel,
                                     session_context=self.session_context)
            if self.cancel.is_set():
                raise Cancelled("Opération annulée.")
        except (OSError, ValueError, UserError, Cancelled) as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(command, self.session_context)


class GameLauncher(QMainWindow):
    playing = Signal(bool)
    music_error = Signal(str)
    hd_error = Signal(str)

    def __init__(self, path, *, manifest=None, preferences=None):
        super().__init__()
        self.path = Path(path).resolve()
        self.folder = self.path.parent
        self.data = manifest if manifest is not None else load_game(self.path)
        self.shared_folder_override = self.data["shared"]
        self.preferences = preferences if preferences is not None else application_preferences()
        self.language = self.data.get("language", "en")
        self.process = self.preparation = self.log = self.play_lock = self.music_session = self.speed_session = None
        self.speed_controls = None
        self.face_session = None
        self.close_after_preparation = False
        self._text_bindings = []
        self.setWindowTitle(f"{APP_NAME} - {self.folder.name}")
        if application_icon():
            self.setWindowIcon(QIcon(str(application_icon())))
        self.setFixedSize(1100, 800)
        xd = self.data["game"] == "xd"
        self.setPalette(theme_palette(self.palette(), xd=xd))
        self.setStyleSheet(XD_STYLE if xd else STYLE)
        surface = GameSurface()
        surface.set_xd(xd)
        if not xd:
            surface.set_background(interface_assets()[0].get("background"))
        self.setCentralWidget(surface)
        outer = QVBoxLayout(surface)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)
        header = QHBoxLayout()
        logo = QLabel()
        logo_path = home_logos().get(self.data["game"])
        if logo_path:
            logo.setPixmap(QPixmap(str(logo_path)).scaled(180, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo)
        header.addWidget(separator(vertical=True))
        identity = QVBoxLayout()
        title = QLabel(self.folder.name)
        title.setObjectName("section")
        title.setStyleSheet("font-size: 30px; font-weight: 700;")
        title.setWordWrap(True)
        identity.addWidget(title)
        seed = QLabel(f"Seed: {self.data['seed']}")
        seed.setWordWrap(True)
        seed.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        identity.addWidget(seed)
        header.addLayout(identity, 1)
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.language)))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_combo)
        outer.addLayout(header)
        panel = MenuPanel(xd=xd)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        title = self.label("Votre partie")
        title.setObjectName("section")
        title.setStyleSheet("font-size: 28px; font-weight: 650;")
        form.addWidget(title)
        self.fields = QWidget()
        fields = QVBoxLayout(self.fields)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(16)
        graphics_row = QHBoxLayout()
        self.graphics = QComboBox()
        self.graphics.addItem("", "original"); self.graphics.addItem("", "hd")
        self.bind(lambda text: self.graphics.setItemText(0, text), "Origine")
        self.bind(lambda text: self.graphics.setItemText(1, text), "HD")
        self.graphics.setCurrentIndex(self.graphics.findData(self.data["settings"]["graphics"]))
        heading = self.label("Graphismes"); heading.setObjectName("subheading")
        graphics_row.addWidget(heading)
        graphics_choices = VisibleChoices(self.graphics); graphics_choices.setFixedWidth(220)
        graphics_row.addWidget(graphics_choices)
        graphics_row.addWidget(separator(vertical=True))
        self.pack_status = self.note("Installé")
        graphics_row.addWidget(self.pack_status)
        self.graphics.currentIndexChanged.connect(self.refresh_pack_status)
        self.bind(lambda _: self.refresh_pack_status(), "Installé")
        graphics_row.addStretch(1)
        packs = self.button("Gérer les packs HD")
        packs.clicked.connect(lambda: show_packs(self))
        graphics_row.addWidget(packs)
        fields.addLayout(graphics_row)
        if self.data["game"] == "xd":
            fields.addWidget(self.note("XD en HD nécessite les deux packs : XD pour les textures, Colosseum pour les vignettes."))
        fields.addWidget(separator())
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(32)
        self.columns.setAlignment(Qt.AlignmentFlag.AlignTop)
        audio = QVBoxLayout()
        audio.setSpacing(8)
        heading = self.label("Vitesse et audio"); heading.setObjectName("subheading")
        audio.addWidget(heading)
        row = QHBoxLayout()
        row.addWidget(self.label("Vitesse du jeu"))
        self.speed = QComboBox()
        for percent in (100, 200):
            self.speed.addItem(f"{percent} %", percent / 100)
        self.speed.setCurrentIndex(self.speed.findData(self.data["settings"]["speed"]))
        speed_choices = VisibleChoices(self.speed); speed_choices.setFixedWidth(210)
        row.addWidget(speed_choices); row.addStretch(1)
        audio.addLayout(row)
        self.native_music = QCheckBox()
        self.bind(self.native_music.setText, "Garder la musique à 100 %")
        self.native_music.setChecked(self.data["settings"].get("native_music", False))
        from .play_music import music_capability
        capability = music_capability(self.data["game_id"])
        metadata = self.data.get("features", {}).get("music", {})
        supported = capability.supported and bool(metadata.get("enabled"))
        available = supported and capability.production_validated
        self.native_music.setEnabled(available)
        if not available:
            self.native_music.setChecked(False)
        audio.addWidget(self.native_music)
        if supported and not capability.production_validated:
            audio.addWidget(self.note("Musique indépendante : validation audio finale en attente."))
        elif not available:
            audio.addWidget(self.note("La musique à 100 % n’est pas disponible pour cette partie."))
        audio.addWidget(self.note("Bruitages et cris : suivent le jeu."))
        audio.addWidget(self.note("Vidéos précalculées : image et son suivent le jeu."))
        audio.addSpacing(8)
        shortcuts = self.label("Raccourcis"); shortcuts.setObjectName("subheading")
        audio.addWidget(shortcuts)
        for caption, key in (("Accélérer à 200 %", "Tab"), ("Ralentir à 50 %", "Maj + Tab")):
            row = QHBoxLayout()
            row.addWidget(self.label(caption), 1)
            keycap = self.label(key)
            keycap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            keycap.setMinimumWidth(92)
            keycap.setObjectName("shortcutKey")
            row.addWidget(keycap)
            audio.addLayout(row)
            audio.addWidget(separator())
        audio.addWidget(self.note("Maintenez la touche. La vitesse choisie revient au relâchement."))
        audio.addStretch(1)
        self.columns.addLayout(audio, 1)
        self.column_divider = separator(vertical=True)
        self.columns.addWidget(self.column_divider)
        controls = QVBoxLayout()
        controls.setSpacing(8)
        heading = self.label("Commandes"); heading.setObjectName("subheading")
        controls.addWidget(heading)
        self.controller = QComboBox()
        self.controller.addItem("", "keyboard"); self.controller.addItem("", "controller")
        self.bind(lambda text: self.controller.setItemText(0, text), "Clavier")
        self.bind(lambda text: self.controller.setItemText(1, text), "Manette")
        self.controller.setCurrentIndex(max(0, self.controller.findData(self.data["settings"].get("controller", "keyboard"))))
        controls.addWidget(VisibleChoices(self.controller))
        controller_row = QHBoxLayout()
        controller_row.addWidget(ControllerDiagram(), 1)
        help_controls = QVBoxLayout()
        help_controls.addWidget(self.note("Profil GameCube standard. Les touches restent modifiables dans Dolphin."))
        configure = self.button("Configurer les touches…")
        configure.clicked.connect(self.configure_controls)
        help_controls.addWidget(configure)
        controller_row.addLayout(help_controls, 1)
        controls.addLayout(controller_row)
        controls.addWidget(separator())
        heading = self.label("Sauvegardes"); heading.setObjectName("subheading")
        controls.addWidget(heading)
        controls.addWidget(self.note("Carte mémoire et sauvegardes rapides dans DolphinUser/. Vos autres parties restent séparées."))
        saves = self.button("Ouvrir les sauvegardes")
        saves.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder / "DolphinUser"))))
        controls.addWidget(saves)
        controls.addStretch(1)
        self.columns.addLayout(controls, 1)
        fields.addLayout(self.columns)
        self.dolphin = QLineEdit(self.data["dolphin"])
        self.dolphin.hide()
        form.addWidget(self.fields)
        form.addWidget(separator())
        form.addStretch(1)
        self.status = self.note("Paramètres conservés pour cette partie.")
        form.addWidget(self.status)
        panel_layout.addWidget(content)
        outer.addWidget(panel, 1)
        footer = QHBoxLayout()
        folder_button = self.button("Ouvrir le dossier")
        folder_button.setIcon(navigation_icon('folder', xd=xd))
        folder_button.setIconSize(QSize(36, 28))
        folder_button.setStyleSheet("font-size: 18px;")
        folder_button.setFixedSize(220, 54)
        folder_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder))))
        footer.addWidget(folder_button); footer.addStretch(1)
        change = self.button("Dolphin…")
        change.setToolTip(self.data["dolphin"])
        change.clicked.connect(self.choose_dolphin)
        footer.addWidget(change)
        self.change_dolphin = change
        change.setVisible(not Path(self.data['dolphin']).is_file())
        self.play = self.button("Jouer"); self.play.setObjectName("primary")
        self.play.setIcon(navigation_icon('play', xd=xd))
        self.play.setIconSize(QSize(26, 26))
        self.play.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.play.setFixedSize(250, 54)
        self.play.clicked.connect(self.start)
        footer.addWidget(self.play)
        outer.addLayout(footer)
        self.timer = QTimer(self); self.timer.setInterval(200); self.timer.timeout.connect(self.poll)
        self.music_error.connect(self.on_music_error)
        self.hd_error.connect(self.on_hd_error)

    def on_hd_error(self, error):
        if self.log is not None:
            self.log.write(("\nOrre Spinda face: " + str(error) + "\n").encode("utf-8"))
            self.log.flush()
        self.status.setText(self.text("Le visage de Spinda utilise le rendu d’origine. Consultez le journal du lanceur."))

    def on_music_error(self, error):
        if self.log is not None:
            self.log.write(("\nOrre music: " + str(error) + "\n").encode("utf-8"))
            self.log.flush()
        self.status.setText(self.text("Le son d’origine a été rétabli. Consultez le journal du lanceur."))

    def text(self, message):
        return translate(message, self.language)

    def bind(self, setter, message):
        self._text_bindings.append((setter, message)); setter(self.text(message))

    def label(self, message):
        widget = QLabel(); self.bind(widget.setText, message); return widget

    def note(self, message):
        widget = self.label(message); widget.setObjectName("note"); widget.setWordWrap(True); return widget

    def button(self, message):
        widget = QPushButton(); self.bind(widget.setText, message); return widget

    def error_message(self, error):
        return self.text(error.args[0]) if isinstance(error, UserError) else self.text("Impossible de lancer Dolphin. Vérifiez son chemin et réessayez.")

    def change_language(self):
        self.language = self.language_combo.currentData()
        for setter, message in self._text_bindings:
            setter(self.text(message))
        self.data["language"] = self.language
        save_game(self.path, self.data)

    def choose_dolphin(self):
        path, _ = QFileDialog.getOpenFileName(self, self.text("Choisir Dolphin"), self.dolphin.text(), "Dolphin (Dolphin.exe dolphin-emu dolphin)")
        if path:
            self.dolphin.setText(path)
            self.change_dolphin.hide()

    def shared_folder_changed(self, path):
        self.shared_folder_override = path
        self.data["shared"] = path
        save_game(self.path, self.data)
        self.refresh_pack_status()

    def refresh_pack_status(self):
        from .play_folders import missing_hd_packs
        self.pack_status.setToolTip("")
        if self.graphics.currentData() == "original":
            message = "Le mode Origine reste disponible sans téléchargement."
        else:
            missing = missing_hd_packs(self.data)
            message = "Packs HD installés" if not missing else "Packs HD à installer"
            if missing:
                self.pack_status.setToolTip(", ".join("Pokémon XD" if game == "xd" else "Pokémon Colosseum" for game in missing))
        self.pack_status.setText(self.text(message))

    def persist(self):
        self.data["dolphin"] = str(validate_dolphin(Path(self.dolphin.text())))
        self.data["settings"].update(graphics=self.graphics.currentData(), speed=self.speed.currentData(),
            native_music=self.native_music.isChecked(), controller=self.controller.currentData())
        save_game(self.path, self.data)

    def start(self):
        if self.preparation is not None:
            self.preparation.cancel.set()
            self.play.setEnabled(False)
            self.status.setText(self.text("Annulation en cours…"))
            return
        if self.process is not None:
            return
        if getattr(getattr(self, "pack_dialog", None), "thread", None) is not None:
            self.status.setText(self.text("Installation des textures HD…")); return
        try:
            self.persist()
            self.play_lock = PlayLock(self.folder)
        except (OSError, UserError) as error:
            self.change_dolphin.setVisible(not Path(self.dolphin.text()).is_file())
            self.status.setText(self.error_message(error)); return
        self.fields.setEnabled(False); self.play.setEnabled(True)
        self.play.setText(self.text("Annuler"))
        self.status.setText(self.text("Préparation du lancement…"))
        self.preparation = LaunchPreparation(self.folder, self.data, self)
        self.preparation.succeeded.connect(self.launch)
        self.preparation.failed.connect(self.failed)
        self.preparation.finished.connect(self.prepared)
        self.preparation.start()

    def prepared(self):
        thread, self.preparation = self.preparation, None
        thread.deleteLater()
        if self.close_after_preparation and self.process is None:
            self.close()

    def launch(self, command, session_context=None):
        if self.preparation is not None and self.preparation.cancel.is_set():
            self.failed(Cancelled("Opération annulée.")); return
        try:
            from .play_speed import prepare_speed_controls, SpeedSession
            self.speed_controls = prepare_speed_controls(self.folder / "DolphinUser")
            log_path = self.folder / "DolphinUser/Logs/launcher.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log = log_path.open("ab")
            self.process = subprocess.Popen(command, cwd=Path(command[0]).parent, stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=self.log, creationflags=0x08000000 if sys.platform == "win32" else 0)
            self.speed_session = SpeedSession(self.process, self.data["settings"]["speed"], self.speed_controls).start()
            if self.native_music.isChecked():
                from .play_music import MusicSession
                metadata = self.data["features"]["music"]
                self.music_session = MusicSession(self.process, Path(metadata["assets"]), metadata,
                    Path(command[0]).parent, on_error=self.music_error.emit).start()
            face = (session_context or {}).get("spinda_face")
            face_error = None
            if face:
                from .hd_spinda_face import SpindaFaceSession
                try:
                    self.face_session = SpindaFaceSession(self.process, Path(face["assets"]), face["metadata"],
                        on_error=self.hd_error.emit).start()
                except (OSError, ValueError, RuntimeError) as error:
                    face_error = error
            self.playing.emit(True)
            self.play.setText(self.text("Jouer")); self.play.setEnabled(False)
            self.status.setText(self.text("Partie en cours dans Dolphin."))
            if face_error is not None:
                self.on_hd_error(face_error)
            self.timer.start()
        except (OSError, ValueError, RuntimeError) as error:
            if self.process is not None and self.process.poll() is None:
                self.status.setText(self.text("Le son d’origine a été rétabli. Consultez le journal du lanceur."))
                self.timer.start(); self.playing.emit(True)
            else:
                self.process = None
                self.failed(error)

    def failed(self, error):
        self.status.setText(self.text("Opération annulée.") if isinstance(error, Cancelled) else self.error_message(error))
        self.release()

    def release(self):
        if self.face_session is not None:
            self.face_session.stop(); self.face_session = None
        if self.music_session is not None:
            self.music_session.stop(); self.music_session = None
        if self.speed_session is not None:
            self.speed_session.close(); self.speed_session = None
        if self.speed_controls is not None:
            self.speed_controls.close(); self.speed_controls = None
        if self.log is not None:
            self.log.close(); self.log = None
        if self.play_lock is not None:
            self.play_lock.close(); self.play_lock = None
        self.fields.setEnabled(True); self.play.setEnabled(True)
        self.play.setText(self.text("Jouer"))

    def poll(self):
        if self.process is None or self.process.poll() is None:
            return
        self.timer.stop(); self.process = None
        self.release(); self.playing.emit(False)
        self.status.setText(self.text("Partie terminée. Vos sauvegardes sont conservées."))

    def configure_controls(self):
        if self.preparation is not None:
            return
        if self.process is not None:
            return
        try:
            self.persist()
            self.play_lock = PlayLock(self.folder)
            configure_profile(self.folder, self.data)
            self.process = subprocess.Popen([self.data["dolphin"], "-u", str(self.folder / "DolphinUser")],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.fields.setEnabled(False); self.play.setEnabled(False)
            self.timer.start()
            self.status.setText(self.text("Dans Dolphin, ouvrez Manettes pour modifier les touches, puis fermez Dolphin."))
        except (OSError, UserError) as error:
            self.failed(error)

    def resizeEvent(self, event):
        if hasattr(self, "columns"):
            compact = self.width() < 840
            self.columns.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
            self.column_divider.setVisible(not compact)
        super().resizeEvent(event)

    def closeEvent(self, event):
        dialog = getattr(self, "pack_dialog", None)
        if dialog is not None and dialog.thread is not None:
            dialog.close_parent_after_cancel = True; dialog.close(); event.ignore(); return
        if self.process is not None or self.preparation is not None:
            self.status.setText(self.text("Fermez Dolphin avant de fermer le lanceur.")); event.ignore(); return
        try:
            self.persist()
        except (OSError, UserError):
            pass
        event.accept()


def main(path: Path):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    try:
        window = GameLauncher(path)
    except (OSError, UserError, ValueError):
        window = QLabel("This game folder could not be opened. Select its game.json in Pokémon Orre Randomizer.")
        window.resize(600, 120)
    window.show()
    return app.exec()
