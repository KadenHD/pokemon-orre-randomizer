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
import sys
import threading
import traceback

from PySide6.QtCore import QLibraryInfo, QLocale, QObject, QPoint, QSettings, QSignalBlocker, QSize, QThread, QTimer, QTranslator, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QDesktopServices, QColor, QFont, QIcon, QKeySequence, QPainter, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMenu, QProgressBar, QPushButton,
                               QScrollArea, QSpinBox, QStackedWidget, QTabBar, QToolButton, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import APP_NAME, __version__
from .engine.analyze_game import FormatError
from .service import Cancelled, Options, RVZToolRequired, UserError, find_dolphin_tool, randomize, validate_options, validate_paths, check_header
from .profiles import load_creation_report, load_profile, save_profile, validate_seed
from .preferences import application_preferences
from .presets import recommended_preset, species_preset
from .preview import baseline_rows, preview_starters, report_rom_matches, ROULETTE_SPECIES
from .preview_cache import PreviewCache
from .ui_species import SpeciesChoice
from .locales.selection_names import SPECIES_NAMES
from .pokemon_details import display_species_name
from .ui_theme import GameSurface, MenuPanel, MenuCheckBox, STYLE, XD_STYLE, HOME_STYLE, JAPANESE_FONT_STYLE
from .xd_ui import XDWorkspace
from .ui_audio import MenuAudio
from .ui_music import MenuMusic
from .ui_exclusions import ExcludedSelection, search_key
from .ui_pokemon_details import PokemonSheet
from .ui_home import GameSelection
from .ui_pokemon_names import RICH_NAME_ROLE, shiny_name_html
from .ui_workspace import (CreationLog, DeliberateWheel, EncounterTable, RuleNavigation, configuration_workspace, file_field,
                           preset_buttons, preview_toolbar, scroll_area, search_field, settings_workspace,
                           starter_slot, wizard_frame, wizard_page)
from .settings_presentation import configuration_review, search_settings
from .resources import MUSIC_FILES, application_icon, application_logo, interface_assets, music_track, menu_icon, xd_logo
from .i18n import LANGUAGES, Message, is_translatable, language_preference, resolve_language, translate
from .workspace_copy import (CATEGORY_HELP, CUSTOM_PRESET, PRESET_DESCRIPTIONS,
                             PRESET_EVOLUTIONS, PRESET_SHINIES, ROM_DESCRIPTION, ROM_USE_NOTICE, STEP_HELP)


class Worker(QObject):
    progress = Signal(int, object)
    succeeded = Signal(dict)
    failed = Signal(object, bool)
    finished = Signal()

    def __init__(self, arguments: dict, task=None, failure_message=None):
        super().__init__()
        self.arguments = arguments
        self.task = task or randomize
        self.failure_message = failure_message or "La création a échoué. Relancez l’application, puis réessayez."

    @Slot()
    def run(self):
        try:
            self.succeeded.emit(self.task(**self.arguments, progress=self.progress.emit))
        except Cancelled as error:
            self.failed.emit(error, True)
        except (UserError, FormatError, OSError) as error:
            self.failed.emit(error, False)
        except Exception:
            if sys.stderr:
                traceback.print_exc()
            self.failed.emit(self.failure_message, False)
        finally:
            self.finished.emit()


class PreviewWorker(QObject):
    succeeded = Signal(dict, object)
    progress = Signal(int, object)
    roulette = Signal(object)
    failed = Signal(object, bool)
    finished = Signal()

    def __init__(self, arguments, task=None):
        super().__init__()
        self.arguments = arguments
        self.task = task or preview_starters

    @Slot()
    def run(self):
        prepared = None

        def keep_plan(plan):
            nonlocal prepared
            prepared = plan

        try:
            result = self.task(**self.arguments, progress=self.progress.emit,
                               roulette=self.roulette.emit, on_prepared=keep_plan)
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


class MainWindow(QMainWindow):
    def __init__(self, *, settings: QSettings | None = None, system_languages=None, start_on_home=False):
        super().__init__()
        self.wheel_guard = DeliberateWheel(self)
        self.rule_visibility_timer = QTimer(self)
        self.rule_visibility_timer.setSingleShot(True)
        self.rule_visibility_timer.timeout.connect(self.keep_rule_visible)
        self.preferences = settings if settings is not None else application_preferences()
        self.preferences.setFallbacksEnabled(False)
        self.system_languages = tuple(QLocale.system().uiLanguages() if system_languages is None else system_languages)
        self.language_preference = language_preference(self.preferences.value("interface/language", "system"))
        self.language = resolve_language(self.language_preference, self.system_languages)
        self._text_bindings = []
        self._status_message = "Choisissez la ROM d’origine."
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
        xd_logo_path = xd_logo()
        self.xd_logo = QPixmap(str(xd_logo_path)) if xd_logo_path else QPixmap()
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
        brand_path = application_logo()
        self.brand_pixmap = QPixmap(str(brand_path)) if brand_path else QPixmap()
        self.brand_logo = QLabel()
        self.brand_logo.setAccessibleName(APP_NAME)
        self.brand_logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.brand_logo.hide()
        header.addWidget(self.brand_logo, 1)
        self.refresh_brand_logo()
        self.logo = QLabel()
        self.logo.hide()
        header.addWidget(self.logo)
        self.title = QLabel("RANDOMIZER")
        self.title.setObjectName("title")
        header.addWidget(self.title, 1)
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("languageSelector")
        self.language_combo.addItem("", "system")
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language_preference))
        self.language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.bind(self.language_combo.setAccessibleName, "Langue")
        self.bind(self.language_combo.setToolTip, "Choisissez une langue ou suivez celle du système. Le choix est enregistré. La langue du jeu reste indépendante.")
        self.music_tracks = {scene: music_track(scene) for scene in MUSIC_FILES}
        self.music_requested = self.preferences.value("interface/music", True) in (True, "true", "1", 1)
        self.music = MenuMusic(self, None)
        self.music_toggle = QToolButton()
        self.music_toggle.setObjectName("headerControl")
        self.bind(self.music_toggle.setText, "Musique")
        self.bind(self.music_toggle.setAccessibleName, "Musique")
        self.bind(self.music_toggle.setToolTip, "Activer ou couper la musique, indépendamment des sons des menus.")
        self.music_toggle.setCheckable(True)
        self.music_toggle.setEnabled(self.music.supported)
        self.music_toggle.setProperty("menuSound", "silent")
        self.music_toggle.toggled.connect(self.change_music)
        self.music.failed.connect(self.music_failed)
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
        outer, self.settings, self.step_buttons = wizard_frame(self.colosseum, self, self.go_step)

        source_layout = wizard_page(self.settings)
        heading = self.label("Choisissez votre ROM")
        heading.setObjectName("section")
        source_layout.addWidget(heading)
        source_layout.addWidget(self.note(Message(ROM_DESCRIPTION, game="Pokémon Colosseum")))
        source_layout.addSpacing(16)
        self.source, self.source_button = file_field(
            source_layout, self, "ROM d’&origine", "ROM d’origine",
            "Sélectionnez un fichier ISO ou RVZ, ou glissez-le ici", "Parcourir…", self.choose_source)
        source_layout.addWidget(self.note("La ROM sera vérifiée avant la création. Aucun fichier existant ne sera remplacé."))
        self.art_note = self.note(ROM_USE_NOTICE)
        source_layout.addWidget(self.art_note)
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

        self.build_settings_workspace()

        output_layout = wizard_page(self.settings)
        output_layout.setSpacing(8)
        self.output_scroll = self.settings.widget(self.settings.count() - 1)
        heading = self.label("Créez votre ROM")
        heading.setObjectName("section")
        output_layout.addWidget(heading)
        self.destination, _ = file_field(
            output_layout, self, "&Nouvelle ROM", "Nouvelle ROM",
            "Choisissez où enregistrer la nouvelle ROM", "Enregistrer sous…", self.choose_destination)
        self.destination.editingFinished.connect(self.sync_format)
        self.format = QComboBox()
        self.format.addItems(["ISO", "RVZ"])
        self.bind(self.format.setAccessibleName, "Format de sortie")
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
        self.creation_log = CreationLog(outer, self)
        self.details, self.log = self.creation_log.toggle, self.creation_log.view
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
        self.xd = XDWorkspace(self, found)
        self.game_views.addWidget(self.xd)
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
        if start_on_home:
            self.show_home()
        self.game_views.currentChanged.connect(self.refresh_music_scene)
        self.refresh_music_scene()

    def change_music(self, enabled):
        self.music_requested = bool(enabled)
        self.preferences.setValue("interface/music", self.music_requested)
        self.preferences.sync()
        self.refresh_music_scene()

    def refresh_music_scene(self):
        current = self.game_views.currentWidget()
        scene = "home" if current is self.home else "xd" if current is self.xd else "colosseum"
        self.music.set_track(self.music_tracks[scene])
        self.music_toggle.setEnabled(self.music.supported)
        playing = False
        if self.music_requested and self.music.supported:
            playing = self.music.start()
            if not playing:
                self.music_failed()
        else:
            self.music.stop()
        with QSignalBlocker(self.music_toggle):
            self.music_toggle.setChecked(playing)

    def music_failed(self):
        with QSignalBlocker(self.music_toggle):
            self.music_toggle.setChecked(False)
        self.set_status("Lecture de la musique indisponible. Les autres fonctions restent disponibles.")

    def change_sound(self, enabled):
        self.audio.set_enabled(enabled)
        self.preferences.setValue("interface/sounds", bool(enabled))
        self.preferences.sync()

    def build_home(self):
        home = GameSelection(self)
        self.open_colosseum, self.open_xd = home.colosseum, home.xd
        return home

    def show_home(self):
        if self.busy:
            return
        self.game_views.setCurrentWidget(self.home)
        self.logo.hide()
        self.brand_logo.setVisible(not self.brand_pixmap.isNull())
        self.title.setVisible(self.brand_pixmap.isNull())
        self.title.setText("ORRE RANDOMIZER")
        self.title.setAccessibleName(APP_NAME)
        self.profile_menu.hide()
        self.apply_game_style()
        self.home.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_colosseum(self):
        if self.busy:
            return
        self.game_views.setCurrentWidget(self.colosseum)
        self.brand_logo.hide()
        self.title.show()
        self.logo.setPixmap(QPixmap(str(self.artwork["logo"])) if "logo" in self.artwork else QPixmap())
        self.logo.setVisible("logo" in self.artwork)
        self.title.setText("RANDOMIZER" if "logo" in self.artwork else "COLOSSEUM")
        self.title.setAccessibleName("Pokémon Colosseum")
        self.profile_menu.show()
        self.apply_game_style()
        self.source.setFocus()

    def show_xd(self):
        if self.busy:
            return
        self.game_views.setCurrentWidget(self.xd)
        self.brand_logo.hide()
        self.title.show()
        self.logo.setPixmap(self.xd_logo)
        self.logo.setVisible(not self.xd_logo.isNull())
        self.title.setText("RANDOMIZER" if not self.xd_logo.isNull() else "POKÉMON XD")
        self.title.setAccessibleName("Pokémon XD")
        self.profile_menu.show()
        if not self.xd.tool.text() and self.tool.text():
            self.xd.tool.setText(self.tool.text())
        self.xd.refresh_preview_identity()
        self.apply_game_style()
        self.xd.focus_current_step()

    def apply_game_style(self):
        home = self.game_views.currentWidget() is self.home
        xd = self.game_views.currentWidget() is self.xd
        self.surface.set_home(home)
        self.surface.set_xd(xd)
        if home:
            style = HOME_STYLE
        elif xd:
            style = XD_STYLE
        else:
            style = STYLE
        self.setStyleSheet(style + (JAPANESE_FONT_STYLE if self.language == "ja" else ""))

    def go_back(self):
        if self.step == 0:
            self.show_home()
        else:
            self.go_step(self.step - 1)

    def build_settings_workspace(self):
        layout = wizard_page(self.settings, scrolling=False)
        self.workspace_tabs, self.seed, self.workspace_pages = settings_workspace(layout, self)
        self.workspace_tabs.currentChanged.connect(self.change_workspace_view)
        self.configuration_pages, (self.simple_mode, self.advanced_mode) = configuration_workspace(
            self, self.workspace_pages, self.set_advanced_mode)
        self.simple_panel = QWidget()
        simple = QVBoxLayout(self.simple_panel)
        simple.setContentsMargins(0, 8, 0, 0)
        self.presets = preset_buttons(self, simple, (recommended_preset, species_preset, Options.none),
                                      self.set_options)
        self.preset_description = QLabel()
        self.preset_description.setWordWrap(True)
        simple.addWidget(self.preset_description)
        self.preset_common = self.note(PRESET_EVOLUTIONS)
        simple.addWidget(self.preset_common)
        self.preset_shiny = self.note(PRESET_SHINIES)
        simple.addWidget(self.preset_shiny)
        simple.addStretch(1)
        self.configuration_pages.addWidget(scroll_area(self.simple_panel))

        self.rule_panel = panel = RuleNavigation(self, self.reset_rule_category)
        self.rule_search, self.rule_reset = panel.search, panel.reset
        self.rule_search_note, self.category_selector = panel.notice, panel.selector
        self.rule_content = panel.content
        self.rule_nav, self.rule_pages, self.rule_results = panel.categories, panel.pages, panel.results
        self.rule_checks, self.rule_fields = {}, {}
        self.build_rules()
        self.rule_nav.currentRowChanged.connect(self.rule_category_changed)
        self.rule_search.textChanged.connect(self.search_rules)
        self.rule_search.returnPressed.connect(lambda: self.open_rule_result(self.rule_results.currentItem()))
        self.rule_results.itemClicked.connect(self.open_rule_result)
        self.rule_results.itemActivated.connect(self.open_rule_result)
        self.rule_category_changed()
        self.configuration_pages.addWidget(self.rule_panel)

        self.build_preview_workspace()

    def build_preview_workspace(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        (self.preview_tabs, self.preview_button, self.preview_cancel_button, self.preview_status,
         self.preview_progress) = preview_toolbar(
            layout, self, (Message("Starters · {count}", count=2), Message("Obscurs · {count}", count=48),
                           Message("Cadeaux · {count}", count=4)), self.start_preview, self.cancel_preview)
        self.family_tab = self.preview_tabs.addTab("")
        self.preview_tabs.setTabVisible(self.family_tab, False)
        self.preview_hint = self.note("Calculez l’aperçu pour afficher le tirage de cette seed.")
        self.preview_hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.preview_hint)
        self.preview_search = search_field(self, "Rechercher un Pokémon…")
        layout.addWidget(self.preview_search)
        self.preview_pages = QStackedWidget()
        layout.addWidget(self.preview_pages, 1)
        self.party_strip = QWidget()
        party = QVBoxLayout(self.party_strip)
        party.setContentsMargins(0, 12, 0, 0)
        preview_pair = QHBoxLayout()
        self.portraits, self.preview_names, self.starter_detail_buttons = {}, {}, {}
        for key, message in (("umbreon", "Premier starter"), ("espeon", "Second starter")):
            slot, self.portraits[key], self.preview_names[key], self.starter_detail_buttons[key] = starter_slot(
                self, message, lambda checked=False, key=key: self.show_starter_detail(key))
            preview_pair.addLayout(slot, 1)
        party.addLayout(preview_pair)
        self.preview_shiny_status = QLabel()
        self.preview_shiny_status.setWordWrap(True)
        self.preview_shiny_status.setObjectName("note")
        self.preview_shiny_status.setTextFormat(Qt.TextFormat.PlainText)
        party.addWidget(self.preview_shiny_status)
        party.addStretch(1)
        self.preview_pages.addWidget(scroll_area(self.party_strip))
        self.unknown_portrait = self.placeholder_portrait("#172c33", "#8be8e7")
        self.xd_unknown_portrait = self.placeholder_portrait("#382527", "#ffb384")
        self.encounters_tree = EncounterTable(self, "Tirage des Pokémon obscurs et offerts")
        self.encounters_scrollbar = self.encounters_tree.scrollbar
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
        self.creation_log.set_step(self.step)
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
                    raise UserError("Sélectionnez un fichier ISO ou RVZ existant.")
                if source.suffix.lower() not in (".iso", ".rvz"):
                    raise UserError("Sélectionnez un fichier ISO ou RVZ existant.")
                if source.suffix.lower() == ".iso":
                    check_header(source)
                elif not self.tool.text().strip() or not Path(self.tool.text().strip()).is_file():
                    self.advanced_toggle.setChecked(True)
                    self.tool.setFocus()
                    raise RVZToolRequired("Pour utiliser le format RVZ, sélectionnez DolphinTool dans votre installation de Dolphin.")
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
        self.set_status(STEP_HELP[index])
        self.refresh_settings_help()
        self.refresh_navigation()

    def apply_artwork(self, assets):
        if not assets:
            return
        self.artwork = assets
        if "colosseum" not in self.home.logo_assets:
            self.home.colosseum.set_logo(QPixmap(str(assets["logo"])) if "logo" in assets else QPixmap())
        self.surface.set_background(assets.get("background"))
        self.render_preview()
        if "logo" in assets:
            self.logo.setPixmap(QPixmap(str(assets["logo"])))
            self.logo.show()

    def build_rules(self):
        descriptions = CATEGORY_HELP
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
            self.rule_panel.add_category(group, scroll_page)
        self.rule_nav.currentRowChanged.connect(lambda _row: self.keep_rule_visible())
        self.rule_nav.setCurrentRow(0)

    def keep_rule_visible(self):
        if hasattr(self, "rule_nav") and self.rule_nav.currentItem() is not None:
            self.rule_panel.fit()
        if hasattr(self, "preview_count"):
            self.update_preview_count()

    def refresh_brand_logo(self):
        height = 88 if self.width() >= 900 and self.height() >= 700 else 48
        self.brand_logo.setFixedHeight(height)
        if not self.brand_pixmap.isNull():
            self.brand_logo.setPixmap(self.brand_pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "brand_logo"):
            self.refresh_brand_logo()
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
        matches = search_settings(query, self.language)
        self._setting_result_items = self.rule_panel.show_results(matches, busy=self.busy)
        if matches:
            self.set_status("Résultats : {count}", count=len(matches))
        elif not query and self.step == 1 and _text is not None:
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
        self.creation_log.append(message)

    def error_message(self, error) -> str:
        if isinstance(error, OSError):
            return Message("Impossible d’accéder au fichier : {detail}", detail=str(error))
        message = error.args[0] if isinstance(error, Exception) and len(error.args) == 1 else str(error)
        if isinstance(error, FormatError) and not is_translatable(message):
            return Message("Création impossible : {detail}", detail=message)
        return message

    def retranslate(self):
        self.setLocale(QLocale(self.language))
        self.apply_game_style()
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
        self.xd.retranslate()
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
        self.creation_log.retranslate()
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
        descriptions = PRESET_DESCRIPTIONS
        selected = None
        for index, (button, constructor) in enumerate(self.presets):
            active = options == constructor()
            button.setChecked(active)
            button.setIcon(self.cursor_icon if active else QIcon())
            if active:
                selected = index
        self.preset_description.setText(self.text(descriptions[selected]) if selected is not None else
                                        self.text(CUSTOM_PRESET))
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
        running = self.preview_thread is not None and getattr(self, 'preview_owner', self) is self
        ready = self.preview_result is not None and self.preview_key == self.preview_configuration()
        rolling = running and self.preview_key is not None and not ready and not self.preview_cancel_event.is_set()
        if rolling and not self.roulette_timer.isActive():
            self.roulette_timer.start()
        elif not rolling:
            self.roulette_timer.stop()
        self.preview_button.setText(self.text(self._preview_action))
        self.preview_button.setVisible(not running and not ready)
        self.preview_button.setEnabled(not self.busy and self.preview_thread is None and not ready)
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

    @staticmethod
    def placeholder_portrait(background, foreground):
        placeholder = QPixmap(42, 42)
        placeholder.fill(QColor(background))
        painter = QPainter(placeholder)
        painter.setPen(QColor(foreground))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        return QIcon(placeholder)

    def preview_portrait(self, row, *, xd=False):
        image = QPixmap()
        if row.get("portrait_png"):
            image.loadFromData(row["portrait_png"])
        elif not xd and (key := {197: "umbreon", 196: "espeon", 25: "pikachu"}.get(row.get("national_dex"))) in self.artwork:
            image.load(str(self.artwork[key]))
        if image.isNull():
            return self.xd_unknown_portrait if xd else self.unknown_portrait
        return QIcon(image)

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
        self.preview_shiny_status.setText(self.shiny_status_text(self.current_options()))

    def shiny_status_text(self, options, *, xd=False):
        if not options.custom_shinies:
            status = self.text("Chromatiques : règles du jeu d’origine." if xd else
                "Avec les règles d’origine, les starters ont 0 % de chance d’être chromatiques. Pour les obscurs capturés, c’est environ 1 sur 8 192 (0,0122 %).")
        elif options.shiny_chance_percent == 100:
            status = self.text("★ 100 % : starters chromatiques garantis.")
        elif options.shiny_chance_percent == 0:
            status = self.text("0 % : aucun starter chromatique.")
        elif xd or options.seeded_shinies:
            status = self.text("Statuts chromatiques fixés par la seed.")
        else:
            rate = QLocale(self.language).toString(options.shiny_chance_percent, 'f', 4).rstrip('0').rstrip('.,')
            status = self.text("{rate} % : statut chromatique tiré en jeu.", rate=rate)
        return status

    def preview_species_name(self, row):
        return display_species_name(row.get("national_dex"), self.language, row.get("name_" + self.language))

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
        self.preview_count.setText(self.encounters_tree.visible_count(self.text))

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
        self.launch_preview(dict(source=source, seed=self.seed.text(), options=options,
                                 dolphin_tool=tool, cancel=self.preview_cancel_event, cache=self.preview_cache),
                            owner=self, succeeded=self.preview_succeeded, failed=self.preview_failed,
                            roulette=self.load_roulette_faces)
        self.render_preview()

    def launch_preview(self, arguments, *, owner, succeeded, failed, roulette, progress=None, task=None):
        """Both workspaces use the same responsive preview thread and lifetime."""
        self.preview_owner = owner
        self.preview_thread = QThread(self)
        self.preview_worker = PreviewWorker(arguments, task)
        self.preview_worker.moveToThread(self.preview_thread)
        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_worker.succeeded.connect(succeeded)
        self.preview_worker.roulette.connect(roulette)
        self.preview_worker.failed.connect(failed)
        if progress is not None:
            self.preview_worker.progress.connect(progress)
        self.preview_worker.finished.connect(self.preview_thread.quit)
        self.preview_worker.finished.connect(self.preview_worker.deleteLater)
        self.preview_thread.finished.connect(self.preview_finished)
        self.preview_thread.finished.connect(self.preview_thread.deleteLater)
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
        owner = self.preview_owner
        self.preview_owner = None
        if owner is self.xd:
            self.xd.finished_preview()
            self.update_preview_controls()
            if self.close_after_cancel:
                self.close()
            return
        self.preview_running_key = None
        if self._preview_message == "Annulation de l’aperçu…":
            self._preview_message = "Aperçu annulé."
        self.render_preview()
        if self.close_after_cancel:
            self.close()

    @Slot()
    def cancel_preview(self):
        if getattr(self, 'preview_owner', None) is self.xd:
            self.xd.cancel_preview()
            return
        self.preview_cancel_event.set()
        self.preview_key = self.preview_result = self.preview_plan = None
        self._preview_action = "Réessayer"
        self._preview_message = "Annulation de l’aperçu…" if self.preview_thread is not None else "Aperçu annulé."
        self.render_preview()

    def import_profile(self, path: Path):
        if self.busy:
            return
        if self.game_views.currentWidget() is self.xd:
            self.xd.import_configuration(path)
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
        if self.game_views.currentWidget() is self.xd:
            self.xd.import_configuration(path, report=True)
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

    def schedule_report_rom_check(self, *, owner=None):
        owner = owner or self
        owner.report_rom_timer.stop()
        if owner.report_check is not None:
            owner.report_check.cancel.set()
        if owner.creation_report is None:
            owner.report_rom_message = ""
        elif not owner.source.text().strip():
            owner.report_rom_message = "Sélectionnez la ROM d’origine pour la comparer au rapport."
        else:
            owner.report_rom_message = "Comparaison de la ROM avec le rapport…"
            owner.report_rom_timer.start(250)
        self.render_report_rom_status(owner=owner)

    def render_report_rom_status(self, *, owner=None):
        owner = owner or self
        owner.report_rom_status.setText(self.text(owner.report_rom_message))
        owner.report_rom_status.setVisible(bool(owner.report_rom_message))

    @Slot()
    def check_report_rom(self, *, owner=None):
        owner = owner or self
        if owner.report_check is not None or owner.creation_report is None or self.close_after_cancel:
            return
        tool = owner.tool.text().strip()
        owner.report_check = ReportRomCheck(self, owner.creation_report, Path(owner.source.text().strip()),
                                            Path(tool) if tool else None, self.preview_cache)
        owner.report_check.finished.connect(lambda: self.report_rom_checked(owner=owner))
        owner.report_check.start()

    @Slot()
    def report_rom_checked(self, *, owner=None):
        owner = owner or self
        check = owner.report_check
        check.wait()
        owner.report_check = None
        check.deleteLater()
        if self.close_after_cancel:
            self.close()
        elif check.cancel.is_set():
            if not owner.report_rom_timer.isActive() and owner.creation_report is not None and owner.source.text().strip():
                owner.report_rom_timer.start(0)
        else:
            owner.report_rom_message = check.message
            self.render_report_rom_status(owner=owner)

    def export_profile(self, path: Path):
        if self.busy:
            return
        if self.game_views.currentWidget() is self.xd:
            self.xd.export_configuration(path)
            return
        try:
            save_profile(path, self.seed.text(), self.current_options())
        except (UserError, OSError) as error:
            message = self.error_message(error)
            self.set_status("Export impossible : {error}", error=message if isinstance(message, Message) else Message(message))
            return
        self.set_status("Profil enregistré : {path}.", path=path)

    def choose_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, self.text("Importer un profil"), "", self.profile_filter())
        if path:
            self.import_profile(Path(path))

    def choose_profile_destination(self):
        game = "xd" if self.game_views.currentWidget() is self.xd else "colosseum"
        path, _ = QFileDialog.getSaveFileName(self, self.text("Exporter le profil"), f"{game}-profile.json",
                                             self.profile_filter(), options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            self.export_profile(Path(path))

    def profile_filter(self):
        return self.text("Profil XD (*.json)" if self.game_views.currentWidget() is self.xd else "Profil Colosseum (*.json)")

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
        if (self.game_views.currentWidget() in (self.colosseum, self.xd) and not self.busy and len(urls) == 1
                and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in (".iso", ".rvz")):
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        if self.game_views.currentWidget() is self.xd:
            self.xd.source.setText(path)
        else:
            self.source.setText(path)
            self.suggest_destination()
        event.acceptProposedAction()

    @Slot()
    def start(self):
        if self.busy or self.preview_thread is not None:
            return
        self.creation_log.reset()
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
        self.busy = True
        self.step = 2
        self.refresh_navigation()
        self.progress_bar.show()
        self.creation_log.begin()
        self.cancel_button.show()
        self.settings.setEnabled(False)
        self.create_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_folder.hide()
        self.open_report.hide()
        self.open_journal.hide()
        self.status.setStyleSheet("")
        self.progress_bar.setValue(0)
        self.set_status("Lecture de la ROM d’origine…")
        arguments = dict(source=source, destination=destination, seed=self.seed.text(),
                         options=options,
                         dolphin_tool=tool, prepared_patches=self.preview_plan)
        arguments["journal_language"] = self.language
        self.start_worker(arguments, self.on_progress, self.succeeded, self.show_error)

    def start_worker(self, arguments, on_progress, on_success, on_error, *, task=None, failure_message=None):
        self.cancel_event = threading.Event()
        self.busy = True
        self.thread = QThread(self)
        self.worker = Worker(dict(arguments, cancel=self.cancel_event), task, failure_message)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(on_progress)
        self.worker.succeeded.connect(on_success)
        self.worker.failed.connect(on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(int, object)
    def on_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.set_status(message)
        self.append_log(message)

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
        if self.creation_log.started and self.busy:
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
        if self.game_views.currentWidget() is self.xd:
            self.xd.finished()
        else:
            self.settings.setEnabled(True)
            self.create_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.refresh_navigation()
        if self.close_after_cancel:
            self.close()

    def cancel(self):
        self.cancel_event.set()
        if self.game_views.currentWidget() is self.xd:
            self.xd.cancelling()
        else:
            self.cancel_button.setEnabled(False)
            self.set_status("Annulation…")

    def open_result(self, report):
        result = self.xd.result if self.game_views.currentWidget() is self.xd else self.result
        if result:
            path = Path(result["output"])
            path = path.with_suffix(path.suffix + ".json") if report else path.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def show_journal(self):
        result = self.xd.result if self.game_views.currentWidget() is self.xd else self.result
        if result and result.get("journal"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result["journal"])))

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
        xd = self.game_views.currentWidget() is self.xd
        dialog = PokemonSheet(self, row, self.preview_species_name(row), self.preview_portrait(row, xd=xd),
                              self.language, xd=xd)
        dialog.finished.connect(lambda _result: setattr(self, "detail_window", None))
        self.detail_window = dialog
        dialog.show()

    def closeEvent(self, event):
        self.report_rom_timer.stop()
        self.xd.report_rom_timer.stop()
        if self.report_check is not None:
            self.report_check.cancel.set()
        if self.xd.report_check is not None:
            self.xd.report_check.cancel.set()
        if self.busy:
            self.close_after_cancel = True
            self.cancel()
            event.ignore()
        elif self.preview_thread is not None:
            self.close_after_cancel = True
            self.cancel_preview()
            event.ignore()
        elif self.report_check is not None or self.xd.report_check is not None:
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
    window = MainWindow(start_on_home=True)
    window.show()
    return app.exec()
