"""Native desktop wizard for Pokémon Orre Randomizer.

THESIS: Three steps make a verified ROM without exposing every switch first.
OWN-WORLD: Colosseum's forest panels, clipped silver frames, cyan selection;
bundled title texture and 42px portraits, readable system text and Qt controls.
STORY: Choose the original ROM, select rules and seed, create a separate file.
FIRST VIEWPORT: Compact title and language above three stages; one central
framed task panel; back and continue anchored below, including at 680x540.
FORM: User-selected C, assistant compact; the approved image is
.impeccable/mocks/c-assistant-compact.png. Approved refinement: configuration
and preview share the seed; one content scroll, compact category selector.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import asdict, fields, replace
import secrets
import sys
import threading
import traceback

from PySide6.QtCore import QEvent, QLibraryInfo, QLocale, QObject, QPoint, QSettings, QSize, QThread, QTimer, QTranslator, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QDesktopServices, QColor, QFont, QIcon, QKeySequence, QPainter, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QScrollBar, QSpinBox, QStackedWidget, QTabBar, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import APP_NAME, __version__
from .engine.analyze_game import FormatError
from .service import Cancelled, Options, RVZToolRequired, UserError, find_dolphin_tool, randomize, validate_options, validate_paths, check_header
from .profiles import load_creation_report, load_profile, save_profile, validate_seed
from .preview import baseline_rows, preview_starters, report_rom_matches, ROULETTE_SPECIES
from .preview_cache import PreviewCache
from .ui_species import SpeciesChoice
from .locales.selection_names import SPECIES_NAMES
from .ui_theme import GameSurface, MenuPanel, MenuCheckBox, STYLE, JAPANESE_FONT_STYLE
from .ui_icons import category_icon
from .ui_audio import MenuAudio
from .ui_music import MenuMusic
from .ui_exclusions import ExcludedSelection, search_key
from .ui_pokemon_details import PokemonSheet
from .ui_pokemon_names import PreviewNameDelegate, RICH_NAME_ROLE, shiny_name_html
from .ui_workspace import bounded, scroll_area, DeliberateWheel
from .settings_presentation import configuration_review, search_settings
from .resources import application_icon, interface_assets, music_track, menu_icon
from .i18n import LANGUAGES, Message, is_translatable, language_preference, resolve_language, translate


class Worker(QObject):
    progress = Signal(int, object)
    succeeded = Signal(dict)
    failed = Signal(object, bool)
    finished = Signal()

    def __init__(self, arguments: dict):
        super().__init__()
        self.arguments = arguments

    @Slot()
    def run(self):
        try:
            self.succeeded.emit(randomize(**self.arguments, progress=self.progress.emit))
        except Cancelled as error:
            self.failed.emit(error, True)
        except (UserError, FormatError, OSError) as error:
            self.failed.emit(error, False)
        except Exception:
            if sys.stderr:
                traceback.print_exc()
            self.failed.emit("La création a échoué. Relancez l’application, puis réessayez.", False)
        finally:
            self.finished.emit()


class PreviewWorker(QObject):
    succeeded = Signal(dict, object)
    roulette = Signal(object)
    failed = Signal(object, bool)
    finished = Signal()

    def __init__(self, arguments):
        super().__init__()
        self.arguments = arguments

    @Slot()
    def run(self):
        prepared = None

        def keep_plan(plan):
            nonlocal prepared
            prepared = plan

        try:
            result = preview_starters(**self.arguments, roulette=self.roulette.emit, on_prepared=keep_plan)
            self.succeeded.emit(result, prepared)
        except Cancelled as error:
            self.failed.emit(error, True)
        except (UserError, FormatError, OSError) as error:
            self.failed.emit(error, False)
        except Exception:
            if sys.stderr:
                traceback.print_exc()
            self.failed.emit("Impossible de calculer l’aperçu. Vérifiez la ROM et les réglages, puis réessayez.", False)
        finally:
            self.finished.emit()


class ReportRomCheck(QThread):
    def __init__(self, parent, report, source, tool, cache):
        super().__init__(parent)
        self.report, self.source, self.tool, self.cache = report, source, tool, cache
        self.cancel = threading.Event()
        self.message = ""

    def run(self):
        try:
            matches = report_rom_matches(self.report, self.source, self.tool, self.cache, self.cancel)
        except Cancelled:
            return
        except UserError as error:
            self.message = error.args[0]
        except (OSError, FormatError, ValueError):
            self.message = "Comparaison impossible. Vérifiez le fichier ROM et réessayez."
        else:
            region = {"Japan": "Japon"}.get(self.report.region.name, self.report.region.name)
            self.message = Message("La ROM sélectionnée correspond au rapport ({region})." if matches else
                                   "La ROM sélectionnée diffère. Choisissez la ROM du rapport ({region}) pour reproduire la partie.",
                                   region=Message(region))


def line() -> QFrame:
    widget = QFrame()
    widget.setFrameShape(QFrame.Shape.HLine)
    widget.setFrameShadow(QFrame.Shadow.Sunken)
    return widget


_DESKTOP_RANDOM_RULES = dict(custom_shinies=True, shiny_chance_percent=5.0, diverse_story_families=True)


def recommended_preset():
    return replace(Options.recommended(), **_DESKTOP_RANDOM_RULES)


def species_preset():
    return replace(Options(), **_DESKTOP_RANDOM_RULES)


class MainWindow(QMainWindow):
    def __init__(self, *, settings: QSettings | None = None, system_languages=None):
        super().__init__()
        self.wheel_guard = DeliberateWheel(self)
        self.rule_visibility_timer = QTimer(self)
        self.rule_visibility_timer.setSingleShot(True)
        self.rule_visibility_timer.timeout.connect(self.keep_rule_visible)
        self.preferences = settings if settings is not None else QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "ColosseumRandomizer", "ColosseumRandomizer")
        self.preferences.setFallbacksEnabled(False)
        self.system_languages = tuple(QLocale.system().uiLanguages() if system_languages is None else system_languages)
        self.language_preference = language_preference(self.preferences.value("interface/language", "system"))
        self.language = resolve_language(self.language_preference, self.system_languages)
        self._text_bindings = []
        self._status_message = "Choisissez la ROM d’origine."
        self._log_messages = []
        self._qt_translator = None
        self.setWindowTitle(f"{APP_NAME} · {__version__}")
        app_icon = application_icon()
        if app_icon:
            self.setWindowIcon(QIcon(str(app_icon)))
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(1040, available.width()-40) if available else 1040,
                    min(800, available.height()-70) if available else 800)
        self.setMinimumSize(680, 540)
        self.setAcceptDrops(True)
        self.thread = self.worker = None
        self.preview_thread = self.preview_worker = None
        self.preview_cancel_event = threading.Event()
        self.preview_key = self.preview_running_key = self.preview_result = self.preview_plan = None
        self.preview_cache = PreviewCache()
        self.creation_report = self.report_check = None
        self.report_rom_message = ""
        self.report_rom_timer = QTimer(self)
        self.report_rom_timer.setSingleShot(True)
        self.report_rom_timer.timeout.connect(self.check_report_rom)
        self._cache_source_key = None
        self.detail_window = None
        self._preview_action = "Calculer l’aperçu"
        self._preview_message = "Calculez l’aperçu pour afficher le tirage de cette seed."
        self.busy = self.close_after_cancel = False
        self.cancel_event = threading.Event()
        self.last_stage = ""
        self.result = None
        self.step = 0
        icon = menu_icon()
        self.cursor_icon = QIcon()
        if icon:
            face = QPixmap(str(icon))
            if not face.isNull():
                # Qt centers the icon canvas. Extra space above the sprite
                # brings its visible center down to the label's glyphs.
                # Space on the right separates the sprite from the label.
                canvas = QPixmap(face.width() + 4, face.height() + 4)
                canvas.fill(Qt.GlobalColor.transparent)
                painter = QPainter(canvas)
                painter.drawPixmap(0, 4, face)
                painter.end()
                self.cursor_icon = QIcon(canvas)
        self.artwork = {}
        self.roulette_faces = {}
        self.roulette_index = 0
        self.roulette_timer = QTimer(self)
        self.roulette_timer.setInterval(115)
        self.roulette_timer.timeout.connect(self.advance_roulette)
        sound_preference = self.preferences.value("interface/sounds", True)
        self.audio = MenuAudio(self, enabled=sound_preference not in (False, "false", "0", 0))
        self.surface = GameSurface()
        self.setCentralWidget(self.surface)
        outer = QVBoxLayout(self.surface)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(6)
        self.logo = QLabel()
        self.logo.hide()
        header.addWidget(self.logo)
        self.title = QLabel("RANDOMIZER")
        self.title.setObjectName("title")
        header.addWidget(self.title, 1)
        self.language_combo = QComboBox()
        self.language_combo.addItem("", "system")
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language_preference))
        self.language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.bind(self.language_combo.setAccessibleName, "Langue")
        self.bind(self.language_combo.setToolTip, "Choisissez une langue ou suivez celle du système. Le choix est enregistré. La langue du jeu reste indépendante.")
        self.music = MenuMusic(self, music_track())
        self.music_toggle = QToolButton()
        self.music_toggle.setObjectName("headerControl")
        self.bind(self.music_toggle.setText, "Musique")
        self.bind(self.music_toggle.setAccessibleName, "Musique du titre")
        self.bind(self.music_toggle.setToolTip, "Activer ou couper la musique du titre, indépendamment des sons des menus.")
        self.music_toggle.setCheckable(True)
        self.music_toggle.setEnabled(self.music.supported)
        self.music_toggle.setProperty("menuSound", "silent")
        self.music_toggle.toggled.connect(self.change_music)
        self.music.failed.connect(lambda: self.music_toggle.setChecked(False))
        header.addWidget(self.music_toggle)
        self.sound_toggle = QToolButton()
        self.sound_toggle.setObjectName("headerControl")
        self.bind(self.sound_toggle.setText, "Sons")
        self.bind(self.sound_toggle.setAccessibleName, "Sons des menus")
        self.bind(self.sound_toggle.setToolTip, "Activer ou couper les sons des menus.")
        self.sound_toggle.setCheckable(True)
        self.sound_toggle.setChecked(self.audio.enabled)
        self.sound_toggle.setEnabled(self.audio.supported)
        self.sound_toggle.setProperty("menuSound", "silent")
        self.sound_toggle.toggled.connect(self.change_sound)
        header.addWidget(self.sound_toggle)
        self.profile_menu = QToolButton()
        self.profile_menu.setObjectName("profileMenu")
        self.bind(self.profile_menu.setText, "Profils")
        self.profile_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.profile_menu)
        self.import_profile_button = menu.addAction("")
        self.export_profile_button = menu.addAction("")
        menu.addSeparator()
        self.import_report_button = menu.addAction("")
        self.bind(self.import_profile_button.setText, "Importer un profil…")
        self.bind(self.export_profile_button.setText, "Exporter le profil…")
        self.bind(self.import_report_button.setText, "Reprendre depuis un rapport…")
        self.import_profile_button.triggered.connect(self.choose_profile)
        self.export_profile_button.triggered.connect(self.choose_profile_destination)
        self.import_report_button.triggered.connect(self.choose_creation_report)
        self.profile_menu.setMenu(menu)
        header.addWidget(self.profile_menu)
        header.addWidget(self.language_combo)
        outer.addLayout(header)
        self.game_views = QStackedWidget()
        outer.addWidget(self.game_views, 1)
        self.home = self.build_home()
        self.game_views.addWidget(self.home)
        self.colosseum = QWidget()
        self.game_views.addWidget(self.colosseum)
        self.game_views.setCurrentWidget(self.colosseum)
        outer = QVBoxLayout(self.colosseum)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        self.step_buttons = []
        step_row = QHBoxLayout()
        step_row.setSpacing(0)
        for index, message in enumerate(("1. ROM", "2. Réglages", "3. Créer")):
            button = self.button(message)
            button.setObjectName("step")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, index=index: self.go_step(index))
            step_row.addWidget(button, 1)
            self.step_buttons.append(button)
        outer.addLayout(step_row)
        panel = MenuPanel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        self.settings = QStackedWidget()
        panel_layout.addWidget(self.settings)
        outer.addWidget(panel, 1)

        source_layout = self.add_page()
        heading = self.label("Choisissez votre ROM")
        heading.setObjectName("section")
        source_layout.addWidget(heading)
        source_layout.addWidget(self.note("Colosseum Europe, USA ou Japon (révision 0), sans modification. Le fichier d’origine est conservé."))
        source_layout.addSpacing(16)
        self.source = QLineEdit()
        self.bind(self.source.setPlaceholderText, "Sélectionnez un fichier ISO ou RVZ, ou glissez-le ici")
        self.bind(self.source.setAccessibleName, "ROM d’origine")
        self.source_button = self.button("Parcourir…")
        self.source_button.clicked.connect(self.choose_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source, 1)
        source_row.addWidget(self.source_button)
        source_label = self.label("ROM d’&origine")
        source_label.setBuddy(self.source)
        source_layout.addWidget(source_label)
        source_layout.addLayout(source_row)
        source_layout.addWidget(self.note("La ROM sera vérifiée avant la création. Aucun fichier existant ne sera remplacé."))
        self.source.editingFinished.connect(self.suggest_destination)
        self.advanced_toggle = QToolButton()
        self.bind(self.advanced_toggle.setText, "Conversion RVZ · DolphinTool")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        source_layout.addWidget(self.advanced_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.advanced, self.tool = self.build_tool_field()
        found = find_dolphin_tool()
        if found:
            self.tool.setText(str(found))
        self.advanced.layout().addWidget(self.note("DolphinTool est nécessaire pour lire ou créer une RVZ. Utilisez celui fourni avec Dolphin."))
        source_layout.addWidget(self.advanced)
        self.advanced.hide()
        self.advanced_toggle.toggled.connect(self.toggle_advanced)
        source_layout.addStretch(1)
        self.art_note = self.note("Votre ROM sert uniquement à créer une nouvelle partie.")
        source_layout.addWidget(self.art_note)

        self.build_settings_workspace()

        output_layout = self.add_page()
        output_layout.setSpacing(8)
        self.output_scroll = self.settings.widget(self.settings.count() - 1)
        heading = self.label("Créez votre ROM")
        heading.setObjectName("section")
        output_layout.addWidget(heading)
        self.destination = QLineEdit()
        self.bind(self.destination.setAccessibleName, "Nouvelle ROM")
        self.bind(self.destination.setPlaceholderText, "Choisissez où enregistrer la nouvelle ROM")
        self.destination.editingFinished.connect(self.sync_format)
        self.format = QComboBox()
        self.format.addItems(["ISO", "RVZ"])
        self.bind(self.format.setAccessibleName, "Format de sortie")
        save_button = self.button("Enregistrer sous…")
        save_button.clicked.connect(self.choose_destination)
        output_label = self.label("&Nouvelle ROM")
        output_label.setBuddy(self.destination)
        output_layout.addWidget(output_label)
        output_row = QHBoxLayout()
        output_row.addWidget(self.destination, 1)
        output_row.addWidget(save_button)
        output_layout.addLayout(output_row)
        format_row = QHBoxLayout()
        format_row.addWidget(self.label("Format de sortie"))
        format_row.addWidget(self.format)
        format_row.addStretch(1)
        output_layout.addLayout(format_row)
        self.output_conversion, self.output_tool = self.build_tool_field(label=True)
        self.output_tool.setText(self.tool.text())
        self.tool.textChanged.connect(self.output_tool.setText)
        self.output_tool.textChanged.connect(self.tool.setText)
        output_layout.addWidget(self.output_conversion)
        self.format.currentTextChanged.connect(self.format_changed)
        self.output_conversion.hide()
        output_layout.addWidget(self.note("Un rapport avec la seed et les réglages sera enregistré à côté de la ROM."))
        self.review_toggle = QToolButton()
        self.bind(self.review_toggle.setText, "Réglages appliqués")
        self.review_toggle.setCheckable(True)
        self.review_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.review_toggle.setArrowType(Qt.ArrowType.RightArrow)
        output_layout.addWidget(self.review_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.review_details = QLabel()
        self.review_details.setWordWrap(True)
        self.review_details.setTextFormat(Qt.TextFormat.PlainText)
        self.review_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.bind(self.review_details.setAccessibleDescription, "Les valeurs mémorisées sans effet ne sont pas affichées ici.")
        self.review_details.hide()
        output_layout.addWidget(self.review_details)
        self.review_toggle.toggled.connect(self.toggle_review_details)
        output_layout.addStretch(1)

        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.status)
        self.report_rom_status = QLabel()
        self.report_rom_status.setObjectName("note")
        self.report_rom_status.setWordWrap(True)
        self.report_rom_status.setTextFormat(Qt.TextFormat.PlainText)
        self.report_rom_status.hide()
        outer.addWidget(self.report_rom_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.bind(self.progress_bar.setAccessibleName, "Progression de la création")
        self.progress_bar.hide()
        outer.addWidget(self.progress_bar)
        self.details = QToolButton()
        self.bind(self.details.setText, "Détails")
        self.details.setCheckable(True)
        self.details.hide()
        outer.addWidget(self.details, 0, Qt.AlignmentFlag.AlignLeft)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        self.log.setMaximumHeight(90)
        self.log.hide()
        outer.addWidget(self.log)
        self.details.toggled.connect(self.log.setVisible)
        footer = QHBoxLayout()
        self.back_button = self.button("Retour")
        self.back_button.setProperty("menuSound", "back")
        self.back_button.clicked.connect(self.go_back)
        footer.addWidget(self.back_button)
        self.open_folder = self.button("Ouvrir le dossier")
        self.open_report = self.button("Ouvrir le rapport")
        self.open_journal = self.button("Ouvrir le journal")
        self.open_folder.hide()
        self.open_report.hide()
        self.open_journal.hide()
        self.open_folder.clicked.connect(lambda: self.open_result(False))
        self.open_report.clicked.connect(lambda: self.open_result(True))
        self.open_journal.clicked.connect(self.show_journal)
        result_row = QHBoxLayout()
        result_row.addWidget(self.open_folder)
        result_row.addWidget(self.open_report)
        result_row.addWidget(self.open_journal)
        result_row.addStretch(1)
        output_layout.addLayout(result_row)
        footer.addStretch(1)
        self.cancel_button = self.button("Annuler")
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()
        self.cancel_button.setProperty("menuSound", "back")
        self.cancel_button.clicked.connect(self.cancel)
        self.next_button = self.button("Continuer")
        self.next_button.setObjectName("primary")
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(lambda: self.go_step(self.step+1))
        self.create_button = self.button("Créer la ROM")
        self.create_button.setObjectName("primary")
        self.create_button.clicked.connect(self.start)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.next_button)
        footer.addWidget(self.create_button)
        outer.addLayout(footer)
        palette = self.palette()
        for role, color in ((QPalette.ColorRole.Window, "#082b24"),
                            (QPalette.ColorRole.Base, "#0b1c20"),
                            (QPalette.ColorRole.Text, "#f2f6f1"),
                            (QPalette.ColorRole.WindowText, "#f2f6f1"),
                            (QPalette.ColorRole.Button, "#172c33"),
                            (QPalette.ColorRole.ButtonText, "#f2f6f1"),
                            (QPalette.ColorRole.Highlight, "#17666b"),
                            (QPalette.ColorRole.HighlightedText, "#ffffff"),
                            (QPalette.ColorRole.PlaceholderText, "#b0c6bd")):
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setStyleSheet(STYLE)
        self.set_advanced_mode(False)
        self.set_options(recommended_preset())
        self.retranslate()
        self.refresh_navigation()
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.seed.textChanged.connect(self.refresh_review)
        self.source.textChanged.connect(self.refresh_review)
        self.source.textChanged.connect(self.update_conversion_visibility)
        self.source.textChanged.connect(self.match_source_format)
        self.seed.textChanged.connect(self.invalidate_preview)
        self.source.textChanged.connect(self.invalidate_preview)
        self.tool.textChanged.connect(self.invalidate_preview)
        self.source.textChanged.connect(self.schedule_report_rom_check)
        self.tool.textChanged.connect(self.schedule_report_rom_check)
        self.update_conversion_visibility()
        images, sounds = interface_assets()
        self.apply_artwork(images)
        self.audio.set_paths(sounds)
        self.sound_toggle.setEnabled(self.audio.supported and bool(sounds))
        self.audio.attach()
        for control in self.findChildren(QComboBox) + self.findChildren(QSpinBox) + self.findChildren(QDoubleSpinBox) + self.findChildren(QTabBar):
            control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            control.installEventFilter(self.wheel_guard)
        if self.music.supported and self.preferences.value("interface/music", True) in (True, "true", "1", 1):
            self.music_toggle.setChecked(True)

    def change_music(self, enabled):
        if enabled:
            if not self.music.start():
                self.music_toggle.blockSignals(True)
                self.music_toggle.setChecked(False)
                self.music_toggle.blockSignals(False)
                enabled = False
                self.set_status("Lecture de la musique indisponible. Les autres fonctions restent disponibles.")
        else:
            self.music.stop()
        self.preferences.setValue("interface/music", bool(enabled))
        self.preferences.sync()

    def change_sound(self, enabled):
        self.audio.set_enabled(enabled)
        self.preferences.setValue("interface/sounds", bool(enabled))
        self.preferences.sync()

    def build_home(self):
        panel = MenuPanel()
        frame = QVBoxLayout(panel)
        frame.setContentsMargins(8, 8, 8, 8)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        heading = self.label("Choisissez un jeu")
        heading.setObjectName("section")
        layout.addWidget(heading)
        layout.addSpacing(12)

        colosseum_row = QHBoxLayout()
        colosseum_text = QVBoxLayout()
        colosseum = self.label("Pokémon Colosseum")
        colosseum.setObjectName("subheading")
        colosseum_text.addWidget(colosseum)
        colosseum_text.addWidget(self.note("ISO ou RVZ · Europe, USA et Japon"))
        colosseum_row.addLayout(colosseum_text, 1)
        self.open_colosseum = self.button("Ouvrir Colosseum")
        self.open_colosseum.setObjectName("primary")
        self.open_colosseum.clicked.connect(self.show_colosseum)
        colosseum_row.addWidget(self.open_colosseum)
        layout.addLayout(colosseum_row)
        layout.addSpacing(8)
        layout.addWidget(line())
        layout.addSpacing(8)

        xd_row = QHBoxLayout()
        xd = self.label("Pokémon XD")
        xd.setObjectName("subheading")
        xd_row.addWidget(xd, 1)
        xd_row.addWidget(self.note("À venir"))
        layout.addLayout(xd_row)
        layout.addStretch(1)
        frame.addWidget(scroll_area(content))
        return panel

    def show_home(self):
        if self.busy:
            return
        self.game_views.setCurrentWidget(self.home)
        self.logo.hide()
        self.title.setText("ORRE RANDOMIZER")
        self.profile_menu.hide()
        self.open_colosseum.setFocus()

    def show_colosseum(self):
        self.game_views.setCurrentWidget(self.colosseum)
        self.logo.setVisible("logo" in self.artwork)
        self.title.setText("RANDOMIZER" if "logo" in self.artwork else "COLOSSEUM")
        self.profile_menu.show()
        self.source.setFocus()

    def go_back(self):
        if self.step == 0:
            self.show_home()
        else:
            self.go_step(self.step - 1)

    def add_page(self, *, scrolling=True):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        host = bounded(page)
        self.settings.addWidget(scroll_area(host) if scrolling else host)
        return layout

    def build_settings_workspace(self):
        layout = self.add_page(scrolling=False)
        layout.setSpacing(6)
        self.workspace_tabs = QTabBar()
        self.workspace_tabs.setObjectName("workspaceTabs")
        self.bind(self.workspace_tabs.setAccessibleName, "Vues des réglages")
        for message in ("Configuration", "Aperçu des Pokémon"):
            index = self.workspace_tabs.addTab("")
            self.bind(lambda text, i=index: self.workspace_tabs.setTabText(i, text), message)
        layout.addWidget(self.workspace_tabs)
        seed_row = QHBoxLayout()
        self.seed = QLineEdit(secrets.token_hex(8))
        self.seed.setMaxLength(256)
        self.seed.setMaximumWidth(520)
        self.bind(self.seed.setAccessibleName, "Seed")
        label = self.label("&Seed")
        label.setBuddy(self.seed)
        seed_row.addWidget(label)
        seed_row.addWidget(self.seed, 1)
        new_seed = self.button("Nouvelle seed")
        new_seed.clicked.connect(lambda: self.seed.setText(secrets.token_hex(8)))
        seed_row.addWidget(new_seed)
        seed_row.addStretch(1)
        layout.addLayout(seed_row)
        self.workspace_pages = QStackedWidget()
        layout.addWidget(self.workspace_pages, 1)
        self.workspace_tabs.currentChanged.connect(self.change_workspace_view)

        configuration = QWidget()
        config = QVBoxLayout(configuration)
        config.setContentsMargins(0, 0, 0, 0)
        mode_row = QHBoxLayout()
        title = self.label("Choisissez ce qui change")
        title.setObjectName("subheading")
        mode_row.addWidget(title, 1)
        self.simple_mode = self.button("Simple")
        self.advanced_mode = self.button("Avancé")
        for button, value in ((self.simple_mode, False), (self.advanced_mode, True)):
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=value: self.set_advanced_mode(value))
            mode_row.addWidget(button)
        config.addLayout(mode_row)
        self.configuration_pages = QStackedWidget()
        config.addWidget(self.configuration_pages, 1)
        self.workspace_pages.addWidget(configuration)
        self.simple_panel = QWidget()
        simple = QVBoxLayout(self.simple_panel)
        simple.setContentsMargins(0, 8, 0, 0)
        self.presets = []
        preset_row = QHBoxLayout()
        for title, subtitle, constructor in (("Pokémon + capacités", "CT et objets aussi", recommended_preset),
                                            ("Pokémon seuls", "Capacités et CT conservées", species_preset),
                                            ("Copie à l’identique", "Aucune randomisation", Options.none)):
            button = self.button(title)
            self.bind(button.setAccessibleDescription, subtitle)
            button.setObjectName("preset")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, constructor=constructor: self.set_options(constructor()))
            column = QVBoxLayout()
            column.addWidget(button)
            column.addWidget(self.note(subtitle))
            preset_row.addLayout(column, 1)
            self.presets.append((button, constructor))
        simple.addLayout(preset_row)
        self.preset_description = QLabel()
        self.preset_description.setWordWrap(True)
        simple.addWidget(self.preset_description)
        self.preset_common = self.note("Les évolutions sont adaptées à Colosseum et les pierres sont vendues à Phénacit et Pyrite. Les starters commencent sous leur forme de base, dans une famille à trois stades. Le tirage évite les familles en double entre starters, obscurs et cadeaux quand les règles le permettent.")
        simple.addWidget(self.preset_common)
        self.preset_shiny = self.note("Chaque Pokémon concerné a 5 % de chance d’être chromatique. La seed fixe le résultat.")
        simple.addWidget(self.preset_shiny)
        simple.addStretch(1)
        self.configuration_pages.addWidget(scroll_area(self.simple_panel))

        self.rule_panel = QWidget()
        rules = QVBoxLayout(self.rule_panel)
        rules.setContentsMargins(0, 0, 0, 0)
        search_row = QHBoxLayout()
        self.rule_search = QLineEdit()
        self.rule_search.setClearButtonEnabled(True)
        self.rule_search.setMaxLength(160)
        self.bind(self.rule_search.setPlaceholderText, "Rechercher un réglage…")
        self.bind(self.rule_search.setAccessibleName, "Rechercher un réglage…")
        search_row.addWidget(self.rule_search, 1)
        self.rule_reset = self.button("Valeurs conseillées")
        self.rule_reset.clicked.connect(self.reset_rule_category)
        search_row.addWidget(self.rule_reset)
        rules.addLayout(search_row)
        self.rule_search_note = QLabel()
        self.rule_search_note.setWordWrap(True)
        self.rule_search_note.setTextFormat(Qt.TextFormat.PlainText)
        self.rule_search_note.hide()
        rules.addWidget(self.rule_search_note)
        self.category_selector = QComboBox()
        self.bind(self.category_selector.setAccessibleName, "Catégorie de réglages")
        self.category_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.category_selector.setMaximumWidth(245)
        search_row.insertWidget(0, self.category_selector)
        self.setTabOrder(self.category_selector, self.rule_search)
        self.setTabOrder(self.rule_search, self.rule_reset)
        self.rule_content = QStackedWidget()
        self.rule_form = QWidget()
        row = QHBoxLayout(self.rule_form)
        row.setContentsMargins(0, 0, 0, 0)
        self.rule_nav = QListWidget()
        self.rule_nav.setObjectName("ruleNavigation")
        self.rule_nav.setIconSize(QSize(20, 20))
        self.rule_nav.setFixedWidth(192)
        self.rule_nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rule_nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bind(self.rule_nav.setAccessibleName, "Catégories de réglages")
        self.rule_pages = QStackedWidget()
        row.addWidget(self.rule_nav)
        row.addWidget(self.rule_pages, 1)
        self.rule_content.addWidget(self.rule_form)
        self.rule_results = QListWidget()
        self.rule_results.setWordWrap(True)
        self.rule_results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bind(self.rule_results.setAccessibleName, "Résultats des réglages")
        self.rule_content.addWidget(self.rule_results)
        rules.addWidget(self.rule_content, 1)
        self.rule_checks, self.rule_fields = {}, {}
        self.build_rules()
        self.category_selector.currentIndexChanged.connect(self.rule_nav.setCurrentRow)
        self.rule_nav.currentRowChanged.connect(self.category_selector.setCurrentIndex)
        self.rule_nav.currentRowChanged.connect(self.rule_category_changed)
        self.rule_search.textChanged.connect(self.search_rules)
        self.rule_search.returnPressed.connect(lambda: self.open_rule_result(self.rule_results.currentItem()))
        self.rule_results.itemClicked.connect(self.open_rule_result)
        self.rule_results.itemActivated.connect(self.open_rule_result)
        self.rule_search.installEventFilter(self)
        self.rule_results.installEventFilter(self)
        self.rule_category_changed()
        self.configuration_pages.addWidget(self.rule_panel)

        self.build_preview_workspace()

    def build_preview_workspace(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        toolbar = QHBoxLayout()
        self.preview_tabs = QTabBar()
        self.preview_tabs.setObjectName("previewTabs")
        self.preview_tabs.setUsesScrollButtons(False)
        self.preview_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.bind(self.preview_tabs.setAccessibleName, "Groupes de Pokémon")
        for message in ("Starters · 2", "Obscurs · 48", "Cadeaux · 4"):
            index = self.preview_tabs.addTab("")
            self.bind(lambda text, i=index: self.preview_tabs.setTabText(i, text), message)
        self.family_tab = self.preview_tabs.addTab("")
        self.preview_tabs.setTabVisible(self.family_tab, False)
        toolbar.addWidget(self.preview_tabs, 1)
        self.preview_button = self.button("Calculer l’aperçu")
        self.preview_button.clicked.connect(self.start_preview)
        toolbar.addWidget(self.preview_button)
        self.preview_cancel_button = self.button("Annuler l’aperçu")
        self.preview_cancel_button.clicked.connect(self.cancel_preview)
        self.preview_cancel_button.hide()
        toolbar.addWidget(self.preview_cancel_button)
        layout.addLayout(toolbar)
        self.preview_status = QLabel()
        self.preview_status.setObjectName("previewStatus")
        self.preview_status.setTextFormat(Qt.TextFormat.PlainText)
        toolbar.addWidget(self.preview_status)
        self.preview_progress = QProgressBar()
        self.preview_progress.setRange(0, 0)
        self.preview_progress.setObjectName("previewProgress")
        self.preview_progress.setTextVisible(False)
        self.preview_progress.setFixedHeight(6)
        self.preview_progress.hide()
        layout.addWidget(self.preview_progress)
        self.preview_hint = self.note("Calculez l’aperçu pour afficher le tirage de cette seed.")
        self.preview_hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.preview_hint)
        self.preview_search = QLineEdit()
        self.preview_search.setClearButtonEnabled(True)
        self.bind(self.preview_search.setPlaceholderText, "Rechercher un Pokémon…")
        self.bind(self.preview_search.setAccessibleName, "Rechercher un Pokémon…")
        layout.addWidget(self.preview_search)
        self.preview_pages = QStackedWidget()
        layout.addWidget(self.preview_pages, 1)
        self.party_strip = QWidget()
        party = QVBoxLayout(self.party_strip)
        party.setContentsMargins(0, 12, 0, 0)
        preview_pair = QHBoxLayout()
        self.portraits, self.preview_names, self.starter_detail_buttons = {}, {}, {}
        for key, message in (("umbreon", "Premier starter"), ("espeon", "Second starter")):
            slot = QVBoxLayout()
            identity = QHBoxLayout()
            portrait = QLabel()
            portrait.setFixedSize(48, 48)
            portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
            portrait.setObjectName("previewPortrait")
            identity.addWidget(portrait)
            self.portraits[key] = portrait
            slot_identity = QVBoxLayout()
            slot_identity.setSpacing(2)
            slot_identity.addWidget(self.note(message))
            name = QLabel()
            name.setObjectName("subheading")
            name.setWordWrap(True)
            name.setTextFormat(Qt.TextFormat.PlainText)
            slot_identity.addWidget(name)
            identity.addLayout(slot_identity, 1)
            slot.addLayout(identity)
            self.preview_names[key] = name
            detail_button = self.button("Fiche du Pokémon")
            self.bind(detail_button.setToolTip, "Consultez ses statistiques, ses capacités et ses évolutions.")
            detail_button.hide()
            detail_button.clicked.connect(lambda checked=False, key=key: self.show_starter_detail(key))
            slot.addWidget(detail_button, 0, Qt.AlignmentFlag.AlignLeft)
            self.starter_detail_buttons[key] = detail_button
            preview_pair.addLayout(slot, 1)
        party.addLayout(preview_pair)
        self.preview_shiny_status = QLabel()
        self.preview_shiny_status.setWordWrap(True)
        self.preview_shiny_status.setObjectName("note")
        self.preview_shiny_status.setTextFormat(Qt.TextFormat.PlainText)
        party.addWidget(self.preview_shiny_status)
        party.addStretch(1)
        self.preview_pages.addWidget(scroll_area(self.party_strip))
        placeholder = QPixmap(42, 42)
        placeholder.fill(QColor("#172c33"))
        painter = QPainter(placeholder)
        painter.setPen(QColor("#8be8e7"))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        self.unknown_portrait = QIcon(placeholder)
        self.encounters_tree = QTreeWidget()
        # Python owns these wrappers throughout the window's lifetime. Reusing
        # Qt-created item/scrollbar wrappers after deferred window destruction
        # can otherwise return a stale, unrelated Shiboken wrapper.
        self.encounters_scrollbar = QScrollBar(Qt.Orientation.Vertical, self.encounters_tree)
        self.encounters_tree.setVerticalScrollBar(self.encounters_scrollbar)
        self.encounters_tree.setObjectName("encountersPreview")
        self.encounters_tree.setColumnCount(2)
        self.encounter_name_delegate = PreviewNameDelegate(self.encounters_tree)
        self.encounters_tree.setItemDelegateForColumn(1, self.encounter_name_delegate)
        self.encounters_tree.setIconSize(QSize(42, 42))
        self.encounters_tree.setRootIsDecorated(False)
        self.encounters_tree.setIndentation(0)
        self.encounters_tree.setWordWrap(True)
        self.encounters_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.encounters_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bind(self.encounters_tree.setAccessibleName, "Tirage des Pokémon obscurs et offerts")
        self.bind(self.encounters_tree.setAccessibleDescription, "Cliquez sur une ligne ou appuyez sur Entrée pour ouvrir la fiche du Pokémon obtenu.")
        self.preview_pages.addWidget(self.encounters_tree)
        family_page = QWidget()
        family_layout = QVBoxLayout(family_page)
        family_layout.setContentsMargins(0, 12, 0, 0)
        heading = self.label("Familles en double")
        heading.setObjectName("subheading")
        family_layout.addWidget(heading)
        self.family_duplicates = QLabel()
        self.family_duplicates.setTextFormat(Qt.TextFormat.PlainText)
        self.family_duplicates.setWordWrap(True)
        family_layout.addWidget(self.family_duplicates)
        family_layout.addStretch(1)
        self.preview_pages.addWidget(scroll_area(family_page))
        footer = QHBoxLayout()
        self.encounter_detail_hint = self.label("Cliquez sur une ligne pour ouvrir sa fiche.")
        self.encounter_detail_hint.setObjectName("previewCount")
        footer.addWidget(self.encounter_detail_hint)
        footer.addStretch(1)
        self.preview_count = QLabel()
        self.preview_count.setObjectName("previewCount")
        footer.addWidget(self.preview_count)
        layout.addLayout(footer)
        self.workspace_pages.addWidget(page)
        self.preview_tabs.currentChanged.connect(self.change_preview_group)
        self.preview_search.textChanged.connect(self.filter_encounters)
        self.encounters_scrollbar.valueChanged.connect(self.update_preview_count)
        self.encounters_tree.itemClicked.connect(lambda item, _column: self.show_encounter_detail(item))
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            shortcut = QShortcut(QKeySequence(key), self.encounters_tree)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda: self.show_encounter_detail(self.encounters_tree.currentItem()))
        self.change_preview_group(0)

    def change_workspace_view(self, index):
        self.workspace_pages.setCurrentIndex(index)
        self.refresh_settings_help()
        self.keep_rule_visible()

    def change_preview_group(self, index):
        self.preview_pages.setCurrentIndex(2 if index == self.family_tab else int(index != 0))
        self.preview_search.setVisible(index in (1, 2))
        self.refresh_settings_help()
        self.render_encounters()
        if hasattr(self, "create_button"):
            self.update_preview_controls()

    def refresh_settings_help(self):
        if hasattr(self, "status") and self.step == 1 and not self.busy:
            message = "Le mode Avancé permet de modifier chaque option du choix sélectionné."
            if self.workspace_tabs.currentIndex() == 1:
                message = "Aperçu pour une nouvelle partie. Aucune ROM n’a été créée."
                if self.preview_tabs.currentIndex() == 2:
                    message = ("Adelbert remet ces cadeaux après le nombre de purifications choisi."
                               if self.rule_checks["accessible_event_gifts"].isChecked()
                               else "Les événements gardent leurs conditions d’obtention.")
            self.status.setStyleSheet("")
            self.set_status(message)

    def set_advanced_mode(self, advanced):
        self.simple_mode.setChecked(not advanced)
        self.advanced_mode.setChecked(advanced)
        self.configuration_pages.setCurrentIndex(int(advanced))
        if not advanced:
            self.rule_search.clear()
        self.rule_visibility_timer.start(0)

    def refresh_navigation(self):
        self.settings.setCurrentIndex(self.step)
        for index, button in enumerate(self.step_buttons):
            button.setChecked(index == self.step)
            button.setIcon(self.cursor_icon if index == self.step else QIcon())
            button.setEnabled(not self.busy)
        self.back_button.setEnabled(not self.busy)
        self.back_button.setText(self.text("Accueil" if self.step == 0 else "Retour"))
        self.profile_menu.setEnabled(not self.busy)
        self.next_button.setVisible(self.step < 2)
        self.next_button.setEnabled(not self.busy)
        self.next_button.setDefault(self.step < 2)
        self.create_button.setVisible(self.step == 2)
        self.create_button.setDefault(self.step == 2)
        self.refresh_review()
        self.update_preview_controls()

    def refresh_review(self):
        if not hasattr(self, "review_details"):
            return
        options = self.current_options()
        preset = next((button.text() for button, constructor in self.presets if options == constructor()), self.text("Personnalisés"))
        header = self.text("Réglages : {preset}\nSeed : {seed}", preset=preset, seed=self.seed.text())
        details = header + "\n\n" + configuration_review(options, self.language)
        self.review_details.setText(details)
        self.review_details.setVisible(self.review_toggle.isChecked())

    def toggle_review_details(self, checked):
        self.review_details.setVisible(checked and bool(self.review_details.text()))
        self.review_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        if checked:
            QTimer.singleShot(0, self, self.reveal_review_details)

    def reveal_review_details(self):
        if self.review_details.isVisible():
            content = self.output_scroll.widget()
            top = self.review_details.mapTo(content, self.review_details.rect().topLeft()).y()
            self.output_scroll.ensureVisible(0, top + min(72, self.review_details.height()), 0, 12)

    def go_step(self, index):
        if self.busy or not 0 <= index <= 2:
            return
        try:
            if index > self.step:
                source = Path(self.source.text().strip())
                if not self.source.text().strip() or not source.is_file():
                    raise UserError("Choisissez un fichier ISO ou RVZ existant.")
                if source.suffix.lower() not in (".iso", ".rvz"):
                    raise UserError("Choisissez un fichier ISO ou RVZ existant.")
                if source.suffix.lower() == ".iso":
                    check_header(source)
                elif not self.tool.text().strip() or not Path(self.tool.text().strip()).is_file():
                    self.advanced_toggle.setChecked(True)
                    raise UserError("Indiquez DolphinTool à l’étape ROM pour lire cette RVZ.")
                self.suggest_destination()
                if index == 2:
                    validate_seed(self.seed.text())
                    validate_options(self.current_options())
        except (UserError, OSError, FormatError) as error:
            self.show_error(error, False)
            self.refresh_navigation()
            return
        self.step = index
        self.status.setStyleSheet("")
        self.set_status(("Choisissez la ROM d’origine.", "Le mode Avancé permet de modifier chaque option du choix sélectionné.", "Vérifiez la destination, puis créez la ROM.")[index])
        self.refresh_settings_help()
        self.refresh_navigation()

    def apply_artwork(self, assets):
        if not assets:
            return
        self.artwork = assets
        self.surface.set_background(assets.get("background"))
        self.render_preview()
        if "logo" in assets:
            self.logo.setPixmap(QPixmap(str(assets["logo"])))
            self.logo.show()
        self.art_note.hide()

    def build_rules(self):
        descriptions = {
            "Dresseurs": "Les obscurs sont réglés séparément des autres Pokémon.",
            "Starters et cadeaux": "Réglez les deux starters et les Pokémon offerts.",
            "Capacités": "Choisissez les capacités à changer et les protections à appliquer.",
            "CT": "Les descriptions suivent les capacités tirées. Les CS restent inchangées.",
            "Boss": "Ces réglages concernent les sept boss. Le choix de chaque obscur est conservé lors de ses réapparitions.",
            "Pokémon autorisés": "Ces filtres s’appliquent aux Pokémon remplacés.",
            "Talents": "Garde Mystik reste réservé à Munja.",
            "Statistiques": "Les statistiques sont redistribuées pour chaque espèce. Munja garde 1 PV de base.",
            "Types": "Les nouveaux types sont pris en compte pour les capacités du même type.",
            "Objets tenus": "Les Pokémon sans objet restent sans objet.",
            "Objets trouvés": "Les coffres gardent leur position et leur quantité d’objets. Les objets clés restent inchangés.",
            "Niveaux et capture": "Ces réglages ne changent pas le niveau des starters ni des Pokémon offerts.",
            "Évolutions": "Pour les évolutions par pierre, activez la vente de pierres dans « Boutiques ».",
            "Boutiques": "Réglez les objets vendus et la disponibilité des pierres d’évolution.",
            "Chromatiques": "La seed fixe les statuts chromatiques ; décochez l’option pour un tirage en jeu.",
        }
        self.rule_groups = list(descriptions)
        for group, description in descriptions.items():
            scroll_page = QScrollArea()
            scroll_page.setWidgetResizable(True)
            scroll_page.setFrameShape(QFrame.Shape.NoFrame)
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setSpacing(8)
            page_layout.addWidget(self.note(description))
            for item in fields(Options):
                if item.metadata["group"] == group:
                    kind = item.metadata["kind"]
                    if kind == "bool":
                        control = MenuCheckBox()
                        self.bind(control.setText, item.metadata["label"])
                        control.setChecked(item.default)
                        self.rule_checks[item.name] = control
                        page_layout.addWidget(control)
                        control.toggled.connect(self.rules_changed)
                    else:
                        form = QFormLayout()
                        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                        if item.metadata.get("selector") == "species":
                            control = SpeciesChoice(self)
                            control.currentIndexChanged.connect(self.rules_changed)
                        elif kind == "choice":
                            control = QComboBox()
                            for value, label in item.metadata["choices"]:
                                index = control.count()
                                control.addItem("", value)
                                self.bind(lambda text, widget=control, index=index: widget.setItemText(index, text), label)
                            control.setCurrentIndex(control.findData(item.default))
                            control.currentIndexChanged.connect(self.rules_changed)
                        elif kind in ("species_set", "type_set"):
                            control = ExcludedSelection(kind, self)
                            control.valueChanged.connect(self.rules_changed)
                        else:
                            control = QDoubleSpinBox() if kind == "float" else QSpinBox()
                            if kind == "float" and "decimals" in item.metadata:
                                control.setDecimals(item.metadata["decimals"])
                            control.setRange(item.metadata["minimum"], item.metadata["maximum"])
                            control.setSingleStep(item.metadata["step"])
                            control.setValue(item.default)
                            control.valueChanged.connect(self.rules_changed)
                        field_label = self.label(item.metadata["label"])
                        field_label.setWordWrap(True)
                        field_label.setBuddy(control)
                        form.addRow(field_label, control)
                        page_layout.addLayout(form)
                    self.bind(control.setAccessibleName, item.metadata["label"])
                    self.bind(control.setToolTip, item.metadata["description"])
                    self.bind(control.setAccessibleDescription, item.metadata["description"])
                    self.rule_fields[item.name] = control
            if group == "Chromatiques":
                page_layout.addWidget(self.note("0 % : aucun ; 100 % : tous. Les Pokémon déjà générés gardent leur tirage."))
            page_layout.addStretch(1)
            scroll_page.setWidget(page)
            self.rule_pages.addWidget(scroll_page)
            navigation = QListWidgetItem(group)
            self.rule_nav.addItem(navigation)
            navigation.setIcon(category_icon(group))
            self.bind(navigation.setText, group)
            index = self.category_selector.count()
            self.category_selector.addItem(category_icon(group), "")
            self.bind(lambda text, i=index: self.category_selector.setItemText(i, text), group)
        self.rule_nav.currentRowChanged.connect(self.rule_pages.setCurrentIndex)
        self.rule_nav.currentRowChanged.connect(lambda _row: self.keep_rule_visible())
        self.rule_nav.setCurrentRow(0)

    def keep_rule_visible(self):
        if hasattr(self, "rule_nav") and self.rule_nav.currentItem() is not None:
            needed = sum(max(28, self.rule_nav.sizeHintForRow(i)) for i in range(self.rule_nav.count())) + 8
            compact = self.width() < 900 or self.rule_form.height() - 8 < needed
            self.rule_nav.setVisible(not compact)
            self.category_selector.setVisible(compact and not self.rule_search.text().strip())
        if hasattr(self, "preview_count"):
            self.update_preview_count()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "title"):
            compact = event.size().width() < 820
            if self.title.property("compact") != compact:
                self.title.setProperty("compact", compact)
                self.title.setStyleSheet("font-size: 20px;" if compact else "")
        if hasattr(self, "rule_visibility_timer"):
            self.rule_visibility_timer.start(0)

    def rule_category_changed(self, index=None):
        if index is not None and self.rule_search.text().strip():
            self.rule_search.clear()
        current = self.rule_nav.currentRow()
        if 0 <= current < len(self.rule_groups):
            category = self.text(self.rule_groups[current])
            self.category_selector.setToolTip(category)
            message = self.text("Rétablir uniquement « {category} » selon le mode « Pokémon + capacités ». Les autres catégories restent intactes.",
                                category=category)
            self.rule_reset.setToolTip(message)
            self.rule_reset.setAccessibleName(message)

    def search_rules(self, _text=None):
        query = self.rule_search.text().strip()
        self.rule_results.clear()
        self._setting_result_items = []
        self.rule_content.setCurrentIndex(1 if query else 0)
        self.rule_reset.setEnabled(not query and not self.busy)
        self.rule_search_note.hide()
        if query:
            matches = search_settings(query, self.language)
            self.rule_search_note.setText(self.text("Résultats : {count}", count=len(matches)) if matches
                else self.text("Aucun réglage trouvé. Essayez un autre mot."))
            self.rule_search_note.setVisible(not matches)
            self.rule_results.setAccessibleDescription(self.rule_search_note.text())
            if matches:
                self.set_status("Résultats : {count}", count=len(matches))
            for row in matches:
                item = QListWidgetItem(row["label"] + "\n" + row["group"])
                item.setData(Qt.ItemDataRole.UserRole, row["name"])
                item.setToolTip(row["description"])
                item.setSizeHint(QSize(0, 60))
                self.rule_results.addItem(item)
                self._setting_result_items.append(item)
            if matches:
                self.rule_results.setCurrentRow(0)
        elif self.step == 1 and _text is not None:
            self.refresh_settings_help()
        self.keep_rule_visible()

    def open_rule_result(self, item):
        if item is None or not self.rule_search.text().strip():
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        metadata = next((item.metadata for item in fields(Options) if item.name == name), None)
        if metadata is None:
            return
        self.rule_search.clear()
        self.rule_nav.setCurrentRow(self.rule_groups.index(metadata["group"]))
        control = self.rule_fields[name]
        page = self.rule_pages.currentWidget()
        page.ensureWidgetVisible(control, 12, 24)
        if control.isEnabled():
            control.setFocus(Qt.FocusReason.OtherFocusReason)
        self.set_status("Réglage : {label}.", label=self.text(metadata["label"]))
        if not control.isEnabled():
            self.status.setText(self.status.text() + " " + self.text("Cette option dépend d’un autre réglage."))
        QTimer.singleShot(0, self, lambda: page.ensureWidgetVisible(control, 12, 24))

    def reset_rule_category(self):
        current = self.rule_nav.currentRow()
        if self.busy or self.rule_search.text().strip() or not 0 <= current < len(self.rule_groups):
            return
        group = self.rule_groups[current]
        reference = recommended_preset()
        values = {item.name: getattr(reference, item.name) for item in fields(Options) if item.metadata["group"] == group}
        self.set_options(replace(self.current_options(), **values))
        self.set_status("Catégorie « {category} » : valeurs conseillées rétablies.", category=self.text(group))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            if watched is self.rule_search and event.key() == Qt.Key.Key_Down and self.rule_results.count():
                self.rule_results.setFocus(Qt.FocusReason.OtherFocusReason)
                self.rule_results.setCurrentRow(0)
                return True
            if watched in (self.rule_search, self.rule_results) and event.key() == Qt.Key.Key_Escape:
                self.rule_search.clear()
                self.rule_search.setFocus(Qt.FocusReason.OtherFocusReason)
                return True
        return super().eventFilter(watched, event)

    def text(self, message: str, **parameters) -> str:
        return translate(Message(message, **parameters) if parameters else message, self.language)

    def bind(self, setter, message: str):
        self._text_bindings.append((setter, message))
        setter(self.text(message))

    def label(self, message: str) -> QLabel:
        widget = QLabel()
        self.bind(widget.setText, message)
        return widget

    def note(self, message: str) -> QLabel:
        widget = self.label(message)
        widget.setWordWrap(True)
        widget.setObjectName("note")
        return widget

    def button(self, message: str) -> QPushButton:
        widget = QPushButton()
        self.bind(widget.setText, message)
        return widget

    def set_status(self, message: str, **parameters):
        self._status_message = Message(message, **parameters) if parameters else message
        self.status.setText(self.text(self._status_message))

    def append_log(self, message: str):
        self._log_messages = [*self._log_messages[-199:], message]
        self.log.appendPlainText(self.text(message))

    def error_message(self, error) -> str:
        if isinstance(error, OSError):
            return Message("Impossible d’accéder au fichier : {detail}", detail=str(error))
        message = error.args[0] if isinstance(error, Exception) and len(error.args) == 1 else str(error)
        if isinstance(error, FormatError) and not is_translatable(message):
            return Message("Création impossible : {detail}", detail=message)
        return message

    def retranslate(self):
        self.setLocale(QLocale(self.language))
        self.setStyleSheet(STYLE + (JAPANESE_FONT_STYLE if self.language == "ja" else ""))
        app = QApplication.instance()
        if self._qt_translator is not None:
            app.removeTranslator(self._qt_translator)
            self._qt_translator = None
        if self.language != "en":
            translator = QTranslator(self)
            if translator.load("qtbase_" + self.language, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
                app.installTranslator(translator)
                self._qt_translator = translator
        for setter, message in self._text_bindings:
            setter(self.text(message))
        self.rule_visibility_timer.start(0)
        for control in self.rule_fields.values():
            if isinstance(control, (ExcludedSelection, SpeciesChoice)):
                control.retranslate()
        system = resolve_language("system", self.system_languages)
        self.language_combo.setItemText(0, self.text("Système ({language})", language=LANGUAGES[system]))
        self.language_combo.ensurePolished()
        metrics = self.language_combo.fontMetrics()
        widest = max(metrics.horizontalAdvance(self.language_combo.itemText(index))
                     for index in range(self.language_combo.count()))
        self.language_combo.setMinimumWidth(widest + 36)
        self.status.setText(self.text(self._status_message))
        self.log.setPlainText("\n".join(self.text(message) for message in self._log_messages))
        self.rules_changed()
        self.refresh_review()
        self.render_preview()
        self.render_report_rom_status()
        self.back_button.setText(self.text("Accueil" if self.step == 0 else "Retour"))
        self.search_rules()
        self.rule_category_changed()
        if self.detail_window is not None:
            self.detail_window.close()
            self.detail_window = None

    @Slot(int)
    def change_language(self, _index):
        self.language_preference = self.language_combo.currentData()
        self.language = resolve_language(self.language_preference, self.system_languages)
        self.retranslate()
        self.preferences.setValue("interface/language", self.language_preference)
        self.preferences.sync()
        if self.preferences.status() != QSettings.Status.NoError:
            self.set_status("Impossible d’enregistrer la langue. Le choix reste actif jusqu’à la fermeture.")

    def current_options(self) -> Options:
        values = {}
        for name, control in self.rule_fields.items():
            values[name] = (control.isChecked() if isinstance(control, QCheckBox) else
                            control.value() if isinstance(control, SpeciesChoice) else
                            control.currentData() if isinstance(control, QComboBox) else control.value())
        return Options(**values)

    def set_options(self, options: Options):
        for name, value in asdict(options).items():
            control = self.rule_fields[name]
            control.blockSignals(True)
            if isinstance(control, QCheckBox):
                control.setChecked(value)
            elif isinstance(control, QComboBox):
                control.setCurrentIndex(control.findData(value))
            else:
                control.setValue(value)
            control.blockSignals(False)
        self.rules_changed()

    def rules_changed(self):
        if not hasattr(self, "create_button"):
            return
        shadows = self.rule_checks["randomize_shadows"].isChecked()
        self.rule_fields["trainer_theme_mode"].setEnabled(self.rule_checks["randomize_trainers"].isChecked())
        self.rule_fields["trainer_evolution_level"].setEnabled(self.rule_checks["trainer_force_evolved"].isChecked())
        self.rule_fields["shiny_chance_percent"].setEnabled(self.rule_checks["custom_shinies"].isChecked())
        self.rule_checks["seeded_shinies"].setEnabled(self.rule_checks["custom_shinies"].isChecked())
        self.rule_checks["unique_shadows"].setEnabled(shadows)
        if not shadows:
            self.rule_checks["unique_shadows"].setChecked(False)
        for name in ("boss_shadow_legendary_mode", "boss_shadow_power_mode", "boss_shadow_min_bst"):
            self.rule_fields[name].setEnabled(shadows)
        starters = any(self.rule_checks[name].isChecked() for name in ("starter_umbreon", "starter_espeon"))
        for name in ("starter_balance_pair", "starter_distinct_families", "starter_complementary_types", "starter_stage", "starter_three_stage_families"):
            self.rule_fields[name].setEnabled(starters)
        for name in ("event_pikachu_purifications", "event_celebi_purifications", "event_pikachu_level", "event_celebi_level"):
            self.rule_fields[name].setEnabled(self.rule_checks["accessible_event_gifts"].isChecked())
        for key in ("umbreon", "espeon"):
            self.rule_fields["starter_" + key + "_species"].setEnabled(self.rule_checks["starter_" + key].isChecked())
        progressive = self.rule_checks["progressive_levels"].isChecked()
        self.rule_fields["trainer_level_multiplier"].setEnabled(not progressive)
        for name in ("early_level_multiplier", "mid_level_multiplier", "late_level_multiplier"):
            self.rule_fields[name].setEnabled(progressive)
        self.create_button.setText(self.text("Créer la ROM" if self.current_options().has_changes
                                             else "Créer une copie à l’identique"))
        options = self.current_options()
        descriptions = (
            "Remplace les Pokémon des dresseurs, les obscurs, les starters et les cadeaux, avec une puissance proche de l’original.\nRandomise aussi les capacités de départ, les apprentissages par niveau, les CT et les objets des coffres et des boutiques.",
            "Remplace les Pokémon des dresseurs, les obscurs, les starters et les cadeaux, sans chercher une puissance proche de l’original.\nGarde les capacités de départ, les apprentissages par niveau et les CT. Les objets restent en place, sauf les pierres ajoutées en boutique.",
            "Crée une nouvelle ROM sans modifier les données du jeu. Aucun Pokémon, aucune capacité ni aucun objet n’est randomisé.\nUtile pour copier le jeu ou convertir son format ISO/RVZ.",
        )
        selected = None
        for index, (button, constructor) in enumerate(self.presets):
            active = options == constructor()
            button.setChecked(active)
            button.setIcon(self.cursor_icon if active else QIcon())
            if active:
                selected = index
        self.preset_description.setText(self.text(descriptions[selected]) if selected is not None else
                                        self.text("Réglages personnalisés : vos options ne correspondent plus à un choix prédéfini. Ouvrez Avancé pour les voir ou les modifier. Choisir un des trois modes ci-dessus remplacera ces réglages."))
        self.preset_common.setVisible(selected in (0, 1))
        self.preset_shiny.setVisible(selected in (0, 1))
        self.refresh_review()
        self.refresh_settings_help()
        if self.preview_key is None:
            self.render_preview()
        else:
            self.invalidate_preview()

    def preview_configuration(self):
        source = self.source.text().strip()
        try:
            stat = Path(source).stat() if source else None
            identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) if stat else None
        except (OSError, ValueError):
            identity = None
        return source, self.seed.text(), self.current_options(), self.tool.text().strip(), identity

    def update_preview_controls(self):
        running = self.preview_thread is not None
        ready = self.preview_result is not None and self.preview_key == self.preview_configuration()
        rolling = running and self.preview_key is not None and not ready and not self.preview_cancel_event.is_set()
        if rolling and not self.roulette_timer.isActive():
            self.roulette_timer.start()
        elif not rolling:
            self.roulette_timer.stop()
        self.preview_button.setText(self.text(self._preview_action))
        self.preview_button.setVisible(not running and not ready)
        self.preview_button.setEnabled(not self.busy and not running and not ready)
        self.preview_status.setVisible(ready)
        self.preview_hint.setVisible(not ready and not running and self._preview_action != "Calculer l’aperçu")
        self.preview_status.setToolTip(self.text(self._preview_message))
        status = (self.text("Aperçu à jour") if ready else
                  self.text("Annulation de l’aperçu…") if self.preview_cancel_event.is_set() else
                  self.text("Calcul en cours…"))
        self.preview_status.setText(("✓ " if ready else "") + status)
        self.preview_status.setAccessibleName(status)
        self.preview_progress.setAccessibleName(status)
        self.preview_progress.setVisible(running and not ready and self.preview_tabs.currentIndex() == 0)
        self.preview_cancel_button.setText(self.text("Annulation de l’aperçu…" if self.preview_cancel_event.is_set()
                                                    else "Annuler l’aperçu"))
        self.preview_cancel_button.setVisible(running and not ready)
        self.preview_cancel_button.setEnabled(running and not self.preview_cancel_event.is_set())
        self.create_button.setEnabled(not self.busy and not running)

    def render_preview(self):
        result = self.preview_result or baseline_rows(self.current_options())
        rows = {row["key"]: row for row in result["starters"]}
        for key, button in self.starter_detail_buttons.items():
            row = rows.get(key, {})
            ready = bool(row.get("details"))
            button.setEnabled(ready)
            button.setVisible(ready)
            name = self.preview_row_name(row)
            markup = self.preview_row_name(row, rich=True) if row.get("shiny") else None
            self.render_starter(key, name, self.preview_portrait(row), markup)
        self.preview_hint.setText(self.text(self._preview_message))
        self.render_shiny_status()
        self.render_family_duplicates(result)
        self.render_encounters()
        self.update_preview_controls()

    def render_family_duplicates(self, result):
        groups = result.get("family_duplicates", [])
        self.preview_tabs.setTabVisible(self.family_tab, bool(groups))
        if not groups:
            self.family_duplicates.clear()
            return
        names = {row["key"]: self.text("{name} (starter)", name=self.preview_species_name(row))
                 for row in result["starters"]}
        names.update({row["key"]: self.text("{name} (cadeau)", name=self.preview_species_name(row))
                      for row in result["gifts"]})
        names.update({f"shadow:{row['shadow_id']}": self.text("{name} (obscur nº {number})",
                      name=self.preview_species_name(row), number=f"{row['shadow_id']:02d}")
                      for row in result["shadows"]})
        self.preview_tabs.setTabText(self.family_tab, self.text("Doublons · {count}", count=len(groups)))
        self.family_duplicates.setText("\n\n".join(" · ".join(names[key] for key in group) for group in groups))

    def render_starter(self, key, name, icon, markup=None):
        portrait = self.portraits[key]
        portrait.setPixmap(icon.pixmap(42, 42))
        portrait.setAccessibleName(name)
        portrait.setToolTip(name)
        label = self.preview_names[key]
        label.setTextFormat(Qt.TextFormat.RichText if markup else Qt.TextFormat.PlainText)
        label.setText(markup or name)

    def preview_portrait(self, row):
        image = QPixmap()
        if row.get("portrait_png"):
            image.loadFromData(row["portrait_png"])
        elif (key := {197: "umbreon", 196: "espeon", 25: "pikachu"}.get(row.get("national_dex"))) in self.artwork:
            image.load(str(self.artwork[key]))
        return self.unknown_portrait if image.isNull() else QIcon(image)

    @Slot(object)
    def load_roulette_faces(self, faces):
        if not self.roulette_timer.isActive():
            return
        self.roulette_faces = {dex: self.preview_portrait(dict(portrait_png=png)) for dex, png in faces.items()}

    @Slot()
    def advance_roulette(self):
        if not self.preview_pages.isVisible():
            return
        self.roulette_index = (self.roulette_index + 1) % len(ROULETTE_SPECIES)

        def sample(offset):
            dex = ROULETTE_SPECIES[(self.roulette_index + offset * 7) % len(ROULETTE_SPECIES)]
            return SPECIES_NAMES[self.language][dex].capitalize(), self.roulette_faces.get(dex, self.unknown_portrait)

        if self.preview_tabs.currentIndex() == 0:
            for index, row in enumerate(baseline_rows(self.current_options())["starters"]):
                if row["national_dex"] is None:
                    self.render_starter(row["key"], *sample(index))
            return
        tree = self.encounters_tree
        viewport = tree.viewport().rect()
        for index in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(index)
            row = item.data(0, Qt.ItemDataRole.UserRole + 2)
            if row.get("national_dex") is None and viewport.intersects(tree.visualItemRect(item)):
                name, icon = sample(index)
                item.setText(1, name)
                item.setIcon(1, icon)

    def render_shiny_status(self):
        options = self.current_options()
        if not options.custom_shinies:
            status = self.text("Avec les règles d’origine, les starters ont 0 % de chance d’être chromatiques. Pour les obscurs capturés, c’est environ 1 sur 8 192 (0,0122 %).")
        elif options.shiny_chance_percent == 100:
            status = self.text("★ 100 % : starters chromatiques garantis.")
        elif options.shiny_chance_percent == 0:
            status = self.text("0 % : aucun starter chromatique.")
        elif options.seeded_shinies:
            status = self.text("Statuts chromatiques fixés par la seed.")
        else:
            rate = QLocale(self.language).toString(options.shiny_chance_percent, 'f', 4).rstrip('0').rstrip('.,')
            status = self.text("{rate} % : statut chromatique tiré en jeu.", rate=rate)
        self.preview_shiny_status.setText(status)

    def preview_species_name(self, row):
        dex = row.get("national_dex")
        name = row.get("name_" + self.language) or SPECIES_NAMES[self.language].get(dex, f"#{dex}" if dex else "?")
        return name.capitalize()

    def preview_row_name(self, row, *, rich=False):
        name = self.preview_species_name(row)
        if name == "?":
            return name
        if row.get("shiny"):
            name = shiny_name_html(name, 14) if rich else name + " ★"
        if "level" in row:
            name = self.text("{name} · Niv. {level}", name=name, level=row["level"])
        return name

    def render_encounters(self):
        if self.preview_tabs.currentIndex() == self.family_tab:
            self.encounter_detail_hint.hide()
            self.preview_count.clear()
            return
        tree = self.encounters_tree
        tree.clear()
        tree.setHeaderLabels([self.text("Pokémon d’origine"), self.text("Avec cette seed")])
        result = self.preview_result or baseline_rows(self.current_options())
        field = "gifts" if self.preview_tabs.currentIndex() == 2 else "shadows"
        rows = result.get(field, [])
        detail_available = self.preview_tabs.currentIndex() != 0 and any(row.get("details") for row in rows)
        rolling = (self.preview_tabs.currentIndex() != 0 and self.preview_thread is not None
                   and self.preview_result is None and self.preview_key is not None
                   and not self.preview_cancel_event.is_set())
        self.encounter_detail_hint.setVisible(detail_available or rolling)
        self.encounter_detail_hint.setText(self.text("Calcul en cours…" if rolling else
                                                    "Cliquez sur une ligne pour ouvrir sa fiche."))
        for row in rows:
            original = self.preview_species_name(row.get("original", {}))
            if field == "shadows":
                original = self.text("{number} · {name}", number=f"{row['shadow_id']:02d}", name=original)
            elif row.get("purifications") is not None:
                count = row["purifications"]
                source = "Adelbert · {count} purification" if count == 1 else "Adelbert · {count} purifications"
                original += "\n" + self.text(source, count=count)
            elif row.get("event"):
                original = self.text("{name} · Événement", name=original)
            name = self.preview_row_name(row)
            item = QTreeWidgetItem(tree, [original, name])
            if row.get("shiny"):
                item.setData(1, RICH_NAME_ROLE, self.preview_row_name(row, rich=True))
            item.setToolTip(0, original)
            item.setToolTip(1, name)
            words = [original, name, str(row.get("national_dex", "")), str(row.get("shadow_id", ""))]
            for record in (row, row.get("original", {})):
                words.extend(record.get("name_" + lang) or names.get(record.get("national_dex"), "")
                             for lang, names in SPECIES_NAMES.items())
            item.setData(0, Qt.ItemDataRole.UserRole, search_key(" ".join(words)))
            item.setData(0, Qt.ItemDataRole.UserRole + 2, row)
            item.setIcon(1, self.preview_portrait(row))
            item.setSizeHint(0, QSize(0, 46))
        self.filter_encounters()

    def filter_encounters(self):
        query = search_key(self.preview_search.text().strip())
        for i in range(self.encounters_tree.topLevelItemCount()):
            item = self.encounters_tree.topLevelItem(i)
            item.setHidden(query not in item.data(0, Qt.ItemDataRole.UserRole))
        self.update_preview_count()
        self.rule_visibility_timer.start(0)

    def update_preview_count(self):
        if self.preview_tabs.currentIndex() not in (1, 2):
            self.preview_count.clear()
            return
        tree = self.encounters_tree
        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
        visible = [i + 1 for i, item in enumerate(items) if tree.visualItemRect(item).intersects(tree.viewport().rect())]
        if not items:
            self.preview_count.setText(self.text("Aucun résultat"))
        elif not visible:
            self.preview_count.setText(self.text("{count} résultats", count=len(items)))
        else:
            self.preview_count.setText(self.text("{first}–{last} sur {count}", first=min(visible),
                                                last=max(visible), count=len(items)))

    def invalidate_preview(self):
        cache_source_key = (self.source.text().strip(), self.tool.text().strip())
        if cache_source_key != self._cache_source_key:
            self.preview_cache.invalidate()
            self._cache_source_key = cache_source_key
        self.render_shiny_status()
        if self.preview_key is not None and self.preview_key != self.preview_configuration():
            if self.detail_window is not None:
                self.detail_window.close()
                self.detail_window = None
            self.preview_cancel_event.set()
            self.preview_key = self.preview_result = self.preview_plan = None
            self._preview_action = "Actualiser l’aperçu"
            self._preview_message = "Seed ou réglages modifiés. Actualisez l’aperçu."
            self.render_preview()

    @Slot()
    def start_preview(self):
        if self.busy or self.preview_thread is not None:
            return
        # Include file identity changes, and never recompute an already current result.
        self.invalidate_preview()
        if self.preview_result is not None:
            return
        try:
            if not self.source.text().strip():
                raise UserError("Choisissez la ROM d’origine pour calculer l’aperçu.")
            validate_seed(self.seed.text())
            options = validate_options(self.current_options())
            source = Path(self.source.text().strip())
            if not source.is_file() or source.suffix.lower() not in (".iso", ".rvz"):
                raise UserError("Sélectionnez un fichier ISO ou RVZ existant.")
            tool = Path(self.tool.text().strip()) if self.tool.text().strip() else None
            if source.suffix.lower() == ".rvz" and (tool is None or not tool.is_file()):
                raise RVZToolRequired("Pour utiliser le format RVZ, sélectionnez DolphinTool dans votre installation de Dolphin.")
        except (UserError, OSError) as error:
            self.preview_failed(error, False)
            return
        self.preview_cancel_event = threading.Event()
        self.preview_key = self.preview_running_key = self.preview_configuration()
        self.preview_result = self.preview_plan = None
        self._preview_message = "Le tirage s’affichera à la fin du calcul…"
        self.roulette_faces.clear()
        self.roulette_index = 0
        self.preview_thread = QThread(self)
        self.preview_worker = PreviewWorker(dict(source=source, seed=self.seed.text(), options=options,
                                                 dolphin_tool=tool, cancel=self.preview_cancel_event, cache=self.preview_cache))
        self.preview_worker.moveToThread(self.preview_thread)
        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_worker.succeeded.connect(self.preview_succeeded)
        self.preview_worker.roulette.connect(self.load_roulette_faces)
        self.preview_worker.failed.connect(self.preview_failed)
        self.preview_worker.finished.connect(self.preview_thread.quit)
        self.preview_worker.finished.connect(self.preview_worker.deleteLater)
        self.preview_thread.finished.connect(self.preview_finished)
        self.preview_thread.finished.connect(self.preview_thread.deleteLater)
        self.render_preview()
        self.preview_thread.start()

    @Slot(dict, object)
    def preview_succeeded(self, result, prepared):
        if self.preview_key != self.preview_running_key or self.preview_key != self.preview_configuration() or self.preview_cancel_event.is_set():
            self.invalidate_preview()
            return
        self.preview_result = result
        self.preview_plan = prepared
        self._preview_message = "Aperçu pour une nouvelle partie. Aucune ROM n’a été créée."
        if result.get("shiny_policy") == "always":
            self._preview_message = "Chromatiques garantis pour une nouvelle partie."
        elif result.get("shiny_policy") == "in-game":
            self._preview_message = "Espèces fixées. Le statut chromatique sera tiré en jeu."
        elif result.get("shiny_policy") == "seeded":
            self._preview_message = "Espèces et statuts fixés pour une nouvelle partie."
        self.render_preview()

    @Slot(object, bool)
    def preview_failed(self, error, cancelled):
        if self.preview_thread is not None and self.preview_key != self.preview_running_key:
            return
        self.preview_key = self.preview_result = self.preview_plan = None
        self._preview_action = "Réessayer"
        if cancelled:
            self._preview_message = "Aperçu annulé."
        else:
            message = str(error) if isinstance(error, Exception) else error
            if isinstance(error, FormatError) and not is_translatable(message):
                message = "Impossible de calculer l’aperçu. Vérifiez la ROM et les réglages, puis réessayez."
            self._preview_message = Message("Aperçu indisponible : {error}", error=Message(message))
        self.render_preview()

    @Slot()
    def preview_finished(self):
        if self.preview_thread is not None:
            self.preview_thread.wait()
        self.preview_thread = self.preview_worker = None
        self.preview_running_key = None
        if self._preview_message == "Annulation de l’aperçu…":
            self._preview_message = "Aperçu annulé."
        self.render_preview()
        if self.close_after_cancel:
            self.close()

    @Slot()
    def cancel_preview(self):
        self.preview_cancel_event.set()
        self.preview_key = self.preview_result = self.preview_plan = None
        self._preview_action = "Réessayer"
        self._preview_message = "Annulation de l’aperçu…" if self.preview_thread is not None else "Aperçu annulé."
        self.render_preview()

    def import_profile(self, path: Path):
        if self.busy:
            return
        try:
            profile = load_profile(path)
        except (UserError, OSError) as error:
            message = self.error_message(error)
            self.set_status("Import impossible : {error}", error=message if isinstance(message, Message) else Message(message))
            return
        # Validate the whole file before changing any control or the seed.
        self.set_options(profile.options)
        self.seed.setText(profile.seed)
        self.creation_report = None
        self.schedule_report_rom_check()
        self.set_status("Profil chargé : {name}.", name=path.name)

    def import_creation_report(self, path: Path):
        if self.busy:
            return
        try:
            report = load_creation_report(path)
        except (UserError, OSError) as error:
            message = self.error_message(error)
            self.set_status("Import impossible : {error}", error=message if isinstance(message, Message) else Message(message))
            return
        self.set_options(report.profile.options)
        self.seed.setText(report.profile.seed)
        self.creation_report = report
        self.schedule_report_rom_check()
        self.set_status("Seed et réglages repris depuis le rapport.")

    def choose_creation_report(self):
        path, _ = QFileDialog.getOpenFileName(self, self.text("Reprendre depuis un rapport…"), "",
                                             self.text("Rapport de création (*.iso.json *.rvz.json);;Fichiers JSON (*.json)"))
        if path:
            self.import_creation_report(Path(path))

    def schedule_report_rom_check(self):
        self.report_rom_timer.stop()
        if self.report_check is not None:
            self.report_check.cancel.set()
        if self.creation_report is None:
            self.report_rom_message = ""
        elif not self.source.text().strip():
            self.report_rom_message = "Sélectionnez la ROM d’origine pour la comparer au rapport."
        else:
            self.report_rom_message = "Comparaison de la ROM avec le rapport…"
            self.report_rom_timer.start(250)
        self.render_report_rom_status()

    def render_report_rom_status(self):
        self.report_rom_status.setText(self.text(self.report_rom_message))
        self.report_rom_status.setVisible(bool(self.report_rom_message))

    @Slot()
    def check_report_rom(self):
        if self.report_check is not None or self.close_after_cancel:
            return
        tool = self.tool.text().strip()
        self.report_check = ReportRomCheck(self, self.creation_report, Path(self.source.text().strip()),
                                           Path(tool) if tool else None, self.preview_cache)
        self.report_check.finished.connect(self.report_rom_checked)
        self.report_check.start()

    @Slot()
    def report_rom_checked(self):
        check = self.report_check
        self.report_check = None
        check.deleteLater()
        if self.close_after_cancel:
            self.close()
        elif check.cancel.is_set():
            if not self.report_rom_timer.isActive() and self.creation_report is not None and self.source.text().strip():
                self.report_rom_timer.start(0)
        else:
            self.report_rom_message = check.message
            self.render_report_rom_status()

    def export_profile(self, path: Path):
        if self.busy:
            return
        try:
            save_profile(path, self.seed.text(), self.current_options())
        except (UserError, OSError) as error:
            message = self.error_message(error)
            self.set_status("Export impossible : {error}", error=message if isinstance(message, Message) else Message(message))
            return
        self.set_status("Profil enregistré : {path}.", path=path)

    def choose_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, self.text("Importer un profil"), "", self.text("Profil Colosseum (*.json)"))
        if path:
            self.import_profile(Path(path))

    def choose_profile_destination(self):
        path, _ = QFileDialog.getSaveFileName(self, self.text("Exporter le profil"), "colosseum-profile.json",
                                             self.text("Profil Colosseum (*.json)"), options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            self.export_profile(Path(path))

    def toggle_advanced(self, checked):
        self.advanced.setVisible(checked and Path(self.source.text().strip()).suffix.lower() == ".rvz")
        self.advanced_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def update_conversion_visibility(self):
        rvz = Path(self.source.text().strip()).suffix.lower() == ".rvz"
        self.advanced_toggle.setVisible(rvz)
        self.advanced_toggle.setChecked(rvz)
        self.toggle_advanced(rvz)

    def build_tool_field(self, *, label=False):
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit()
        self.bind(field.setAccessibleName, "DolphinTool")
        self.bind(field.setPlaceholderText, "DolphinTool.exe fourni avec votre installation de Dolphin")
        browse = self.button("Parcourir…")
        browse.clicked.connect(lambda: self.choose_tool(field))
        if label:
            title = self.label("DolphinTool pour la sortie RVZ")
            title.setBuddy(field)
            layout.addWidget(title)
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        return block, field

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, self.text("Choisir la ROM d’origine"), self.source.text(), self.text("ROM GameCube (*.iso *.rvz)"))
        if path:
            self.source.setText(path)
            self.suggest_destination()

    def match_source_format(self):
        extension = Path(self.source.text().strip()).suffix.lower()
        if extension in (".iso", ".rvz"):
            self.format.setCurrentText(extension[1:].upper())

    def suggest_destination(self):
        if self.source.text().strip() and not self.destination.text().strip():
            source = Path(self.source.text().strip())
            self.destination.setText(str(source.with_name("colosseum-randomized." + self.format.currentText().lower())))

    def format_changed(self, value):
        if self.destination.text():
            self.destination.setText(str(Path(self.destination.text()).with_suffix("." + value.lower())))
        self.output_conversion.setVisible(value == "RVZ")

    def sync_format(self):
        extension = Path(self.destination.text()).suffix.lower()
        if extension in (".iso", ".rvz"):
            self.format.setCurrentText(extension[1:].upper())

    def choose_destination(self):
        extension = self.format.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(self, self.text("Choisir où enregistrer la ROM"), self.destination.text(),
                                             self.text("Image {format} (*.{extension})", format=extension.upper(), extension=extension),
                                             options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            self.destination.setText(path if Path(path).suffix else path + "." + extension)
            self.sync_format()

    def choose_tool(self, field):
        path, _ = QFileDialog.getOpenFileName(self, self.text("Choisir DolphinTool"), field.text(), self.text("DolphinTool (DolphinTool.exe DolphinTool);;Tous les fichiers (*)"))
        if path:
            field.setText(path)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if (self.game_views.currentWidget() is self.colosseum and not self.busy and len(urls) == 1
                and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in (".iso", ".rvz")):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.source.setText(event.mimeData().urls()[0].toLocalFile())
        self.suggest_destination()
        event.acceptProposedAction()

    @Slot()
    def start(self):
        if self.busy or self.preview_thread is not None:
            return
        self.sync_format()
        self.invalidate_preview()
        source_text, dest_text = self.source.text().strip(), self.destination.text().strip()
        tool = Path(self.tool.text().strip()) if self.tool.text().strip() else None
        try:
            if not source_text or not dest_text:
                raise UserError("Choisissez la ROM d’origine et l’emplacement de la nouvelle ROM.")
            source, destination, _ = validate_paths(Path(source_text), Path(dest_text), self.seed.text(), tool)
            options = validate_options(self.current_options())
        except (UserError, OSError) as error:
            self.show_error(error, False)
            if isinstance(error, RVZToolRequired) and self.output_conversion.isVisible():
                self.output_tool.setFocus()
                self.output_scroll.ensureWidgetVisible(self.output_tool)
            return
        self.cancel_event = threading.Event()
        self.busy = True
        self.step = 2
        self.refresh_navigation()
        self.progress_bar.show()
        self.details.show()
        self.cancel_button.show()
        self.settings.setEnabled(False)
        self.create_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_folder.hide()
        self.open_report.hide()
        self.open_journal.hide()
        self.log.clear()
        self._log_messages.clear()
        self.last_stage = ""
        self.status.setStyleSheet("")
        self.progress_bar.setValue(0)
        arguments = dict(source=source, destination=destination, seed=self.seed.text(),
                         options=options,
                         dolphin_tool=tool, cancel=self.cancel_event, prepared_patches=self.preview_plan)
        arguments["journal_language"] = self.language
        self.thread = QThread(self)
        self.worker = Worker(arguments)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.succeeded.connect(self.succeeded)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(int, object)
    def on_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.set_status(message)
        if message != self.last_stage:
            self.append_log(message)
            self.last_stage = message

    @Slot(dict)
    def succeeded(self, report):
        self.result = report
        self.set_status("ROM créée et vérifiée.\n{path}", path=report["output"])
        self.progress_bar.setValue(100)
        self.open_folder.show()
        self.open_report.show()
        self.open_journal.setVisible(bool(report.get("journal")))

    @Slot(object, bool)
    def show_error(self, message, cancelled):
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        color = "#ff9b9b" if dark else "#a12424"
        self.status.setStyleSheet("" if cancelled else f"color: {color};")
        message = self.error_message(message) if isinstance(message, Exception) else message
        self.set_status(message)
        self.append_log(message)

    @Slot()
    def finished(self):
        # finished() can be queued before the native thread's final cleanup.
        # Keep its wrapper alive and wait before enabling/releasing the UI.
        if self.thread is not None:
            self.thread.wait()
        self.busy = False
        self.worker = None
        self.thread = None
        self.settings.setEnabled(True)
        self.create_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.refresh_navigation()
        if self.close_after_cancel:
            self.close()

    def cancel(self):
        self.cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.set_status("Annulation…")

    def open_result(self, report):
        if self.result:
            path = Path(self.result["output"])
            path = path.with_suffix(path.suffix + ".json") if report else path.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def show_journal(self):
        if self.result and self.result.get("journal"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result["journal"])))

    def show_starter_detail(self, key):
        rows = self.preview_result.get("starters", []) if self.preview_result else []
        row = next((row for row in rows if row["key"] == key), None)
        if row:
            self.show_pokemon_detail(row)

    def show_encounter_detail(self, item):
        if item is not None and not item.isHidden():
            row = item.data(0, Qt.ItemDataRole.UserRole + 2)
            if row:
                self.show_pokemon_detail(row)

    def show_pokemon_detail(self, row):
        if not row.get("details"):
            return
        if self.detail_window is not None:
            self.detail_window.close()
        dialog = PokemonSheet(self, row, self.preview_species_name(row), self.preview_portrait(row),
                              self.language)
        dialog.finished.connect(lambda _result: setattr(self, "detail_window", None))
        self.detail_window = dialog
        dialog.show()

    def closeEvent(self, event):
        self.report_rom_timer.stop()
        if self.report_check is not None:
            self.report_check.cancel.set()
        if self.busy:
            self.close_after_cancel = True
            self.cancel()
            event.ignore()
        elif self.preview_thread is not None:
            self.close_after_cancel = True
            self.cancel_preview()
            event.ignore()
        elif self.report_check is not None:
            self.close_after_cancel = True
            event.ignore()
        else:
            self.preview_cache.close()
            self.preview_plan = None
            if self.detail_window is not None:
                self.detail_window.close()
            self.audio.close()
            self.music.stop()
            if self._qt_translator is not None:
                QApplication.instance().removeTranslator(self._qt_translator)
            event.accept()


def main() -> int:
    if sys.argv[1:2] == ["--diagnostics"]:
        from .diagnostics import main as diagnostics_main
        return diagnostics_main(sys.argv[2:])
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    icon = application_icon()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show_home()
    window.show()
    return app.exec()
