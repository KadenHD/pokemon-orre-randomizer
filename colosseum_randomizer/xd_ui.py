"""Pokémon XD creation form, sharing the desktop's validation and job runner."""

from dataclasses import fields
from html import escape
from pathlib import Path
import secrets

from PySide6.QtCore import QSignalBlocker, QSize, Qt, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QSpinBox, QStackedWidget, QTabBar, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .i18n import Message
from .locales.selection_names import SPECIES_NAMES
from .profiles import XD_SPOT_MIGRATION, load_profile, load_xd_creation_report, save_profile, validate_seed
from .service import RVZToolRequired, UserError, check_header, validate_paths
from .ui_exclusions import ExcludedSelection, search_key
from .ui_pokemon_names import PreviewNameDelegate, RICH_NAME_ROLE, shiny_name_html
from .ui_species import SpeciesChoice
from .ui_theme import MenuCheckBox, MenuPanel
from .ui_workspace import bounded, scroll_area
from .xd import XDOptions, validate_options
from .xd_gifts import GIFT_TRADE_REQUIREMENTS, TOGETIC


RULES = fields(XDOptions)
MOVE_RULES = ("randomize_trainer_moves", "randomize_starter_moves", "randomize_gift_moves", "randomize_learnsets")
DEPENDENCIES = {
    "unique_shadow_families": ("randomize_shadows",),
    "boss_shadow_legendary_mode": ("randomize_shadows",),
    "boss_shadow_power_mode": ("randomize_shadows",),
    "boss_shadow_min_bst": ("randomize_shadows",),
    "starter_species": ("randomize_starter",),
    "starter_stage": ("randomize_starter",),
    "starter_three_stage_families": ("randomize_starter",),
    "shiny_chance_percent": ("custom_shinies",),
    "trainer_theme_mode": ("randomize_trainers",),
    "trainer_evolution_level": ("trainer_force_evolved",),
    "abilities_family_consistent": ("randomize_abilities",),
    "preserve_stat_totals": ("randomize_stats",),
    "types_family_consistent": ("randomize_types",),
    "useful_held_items_only": ("randomize_held_items",),
    "early_level_multiplier": ("progressive_levels",),
    "mid_level_multiplier": ("progressive_levels",),
    "late_level_multiplier": ("progressive_levels",),
    "shop_keep_healing": ("randomize_shop_items",),
    "items_similar_value": ("randomize_field_items", "randomize_shop_items"),
    "keep_capture_items": ("randomize_field_items", "randomize_shop_items"),
    **dict.fromkeys(("ensure_damaging_move", "ensure_stab_move", "no_duplicate_moves",
                     "ban_self_destruct", "ban_ohko", "moves_mode"), MOVE_RULES),
}

SPOT_LABELS = {"rock": "Roche", "oasis": "Oasis", "cave": "Grotte"}
STEP_HELP = ("Utilisez une ROM Pokémon XD complète et non modifiée.",
             "Le mode Avancé permet de modifier chaque option du choix sélectionné.",
             "La ROM d’origine est conservée.")


class XDWorkspace(QWidget):
    def __init__(self, window, tool_path):
        super().__init__()
        self.window = window
        self.result = None
        self.status_message = ""
        self.status_error = False
        self.preview_result = None
        self.preview_key = None
        self.preview_running = False
        self.preview_message = "Choisissez la ROM d’origine pour calculer l’aperçu."
        self.preview_error = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.step = 0
        self.step_buttons = []
        steps = QHBoxLayout()
        steps.setSpacing(0)
        for index, label in enumerate(("1. ROM", "2. Réglages", "3. Créer")):
            button = window.button(label)
            button.setObjectName("step")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, index=index: self.go_step(index))
            self.step_buttons.append(button)
            steps.addWidget(button, 1)
        layout.addLayout(steps)

        panel = MenuPanel(xd=True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        self.pages = QStackedWidget()
        panel_layout.addWidget(self.pages)
        layout.addWidget(panel, 1)

        rom = self.add_page()
        source_group = self.section("Choisissez votre ROM")
        source_label = window.label("ROM d’origine")
        self.source = QLineEdit()
        self.source.setObjectName("xdSource")
        window.bind(self.source.setAccessibleName, "ROM d’origine")
        window.bind(self.source.setPlaceholderText, "Déposez ou choisissez une image ISO ou RVZ")
        source_label.setBuddy(self.source)
        source_group.addWidget(source_label)
        source_group.addLayout(self.path_row(self.source, self.choose_source))
        source_group.addWidget(window.note("Pokémon XD · Europe, USA et Japon"))
        self.tool_block, self.tool = window.build_tool_field()
        self.source_conversion = self.disclosure("Conversion RVZ · DolphinTool", self.tool_block)
        source_group.addWidget(self.source_conversion)
        source_group.addWidget(self.tool_block)
        rom.addLayout(source_group)
        rom.addStretch(1)

        settings = self.add_page(scrolling=False)
        settings.setSpacing(6)
        tabs = QTabBar()
        tabs.setObjectName("workspaceTabs")
        window.bind(tabs.setAccessibleName, "Vues des réglages")
        for label in ("Configuration", "Aperçu des Pokémon"):
            index = tabs.addTab("")
            window.bind(lambda value, index=index: tabs.setTabText(index, value), label)
        settings.addWidget(tabs)
        seed_row = QHBoxLayout()
        seed_label = window.label("Seed")
        self.seed = QLineEdit(secrets.token_hex(8))
        self.seed.setMaxLength(256)
        self.seed.setMaximumWidth(520)
        seed_label.setBuddy(self.seed)
        window.bind(self.seed.setAccessibleName, "Seed")
        new_seed = window.button("Nouvelle seed")
        new_seed.clicked.connect(lambda: self.seed.setText(secrets.token_hex(8)))
        seed_row.addWidget(seed_label)
        seed_row.addWidget(self.seed, 1)
        seed_row.addWidget(new_seed)
        seed_row.addStretch(1)
        settings.addLayout(seed_row)
        views = QStackedWidget()
        settings.addWidget(views, 1)
        tabs.currentChanged.connect(views.setCurrentIndex)
        self.build_configuration(views)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addLayout(self.build_preview())
        views.addWidget(preview)

        output = self.add_page()
        output_group = self.section("Créez votre ROM")
        self.destination = QLineEdit()
        self.destination.setObjectName("xdDestination")
        window.bind(self.destination.setAccessibleName, "Nouvelle ROM")
        self.format = QComboBox()
        window.bind(self.format.setAccessibleName, "Format de sortie")
        self.format.addItems(("ISO", "RVZ"))
        destination_label = window.label("Nouvelle ROM")
        destination_label.setBuddy(self.destination)
        output_group.addWidget(destination_label)
        output_group.addLayout(self.path_row(self.destination, self.choose_destination))
        format_row = QHBoxLayout()
        format_label = window.label("Format de sortie")
        format_label.setBuddy(self.format)
        format_row.addWidget(format_label)
        format_row.addWidget(self.format)
        format_row.addStretch(1)
        output_group.addLayout(format_row)
        self.output_tool_block, self.output_tool = window.build_tool_field(label=True)
        self.tool.textChanged.connect(self.output_tool.setText)
        self.output_tool.textChanged.connect(self.tool.setText)
        if tool_path:
            self.tool.setText(str(tool_path))
        output_group.addWidget(self.output_tool_block)
        self.review = QLabel()
        self.review.setObjectName("xdReview")
        self.review.setWordWrap(True)
        self.review.setTextFormat(Qt.TextFormat.PlainText)
        output_group.addWidget(self.disclosure("Réglages appliqués", self.review))
        output_group.addWidget(self.review)
        output.addLayout(output_group)

        result_row = QHBoxLayout()
        self.folder_button = window.button("Ouvrir le dossier")
        self.folder_button.clicked.connect(lambda: window.open_result(False))
        self.folder_button.hide()
        result_row.addWidget(self.folder_button)
        self.report_button = window.button("Ouvrir le rapport")
        self.report_button.clicked.connect(lambda: window.open_result(True))
        self.report_button.hide()
        result_row.addWidget(self.report_button)
        self.journal_button = window.button("Ouvrir le journal")
        self.journal_button.clicked.connect(window.show_journal)
        self.journal_button.hide()
        result_row.addWidget(self.journal_button)
        result_row.addStretch(1)
        output.addLayout(result_row)
        output.addStretch(1)

        self.status = QLabel()
        self.status.setObjectName("xdStatus")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)

        footer = QHBoxLayout()
        self.home_button = window.button("Accueil")
        self.home_button.setProperty("menuSound", "back")
        self.home_button.clicked.connect(self.go_back)
        footer.addWidget(self.home_button)
        footer.addStretch(1)
        self.cancel_button = window.button("Annuler")
        self.cancel_button.setProperty("menuSound", "back")
        self.cancel_button.clicked.connect(window.cancel)
        self.cancel_button.hide()
        footer.addWidget(self.cancel_button)
        self.create_button = window.button("Continuer")
        self.create_button.setObjectName("primary")
        self.create_button.clicked.connect(self.advance)
        footer.addWidget(self.create_button)
        layout.addLayout(footer)

        self.source.textChanged.connect(self.source_changed)
        self.source.textChanged.connect(self.invalidate_preview)
        self.seed.textChanged.connect(self.invalidate_preview)
        self.tool.textChanged.connect(self.invalidate_preview)
        self.destination.textChanged.connect(self.destination_changed)
        self.format.currentTextChanged.connect(self.format_changed)
        self.update_tool()
        self.set_options(XDOptions.recommended())
        self.refresh_navigation()

    def add_page(self, *, scrolling=True):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        host = bounded(page)
        self.pages.addWidget(scroll_area(host) if scrolling else host)
        return layout

    def build_configuration(self, views):
        window = self.window
        configuration = QWidget()
        layout = QVBoxLayout(configuration)
        layout.setContentsMargins(0, 6, 0, 0)
        views.addWidget(configuration)
        header = QHBoxLayout()
        title = window.label("Choisissez ce qui change")
        title.setObjectName("subheading")
        header.addWidget(title, 1)
        modes = QStackedWidget()
        self.mode_buttons = []
        for index, name in enumerate(("Simple", "Avancé")):
            button = window.button(name)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda checked=False, index=index: (
                modes.setCurrentIndex(index), self.refresh_mode(index)))
            self.mode_buttons.append(button)
            header.addWidget(button)
        modes.currentChanged.connect(self.refresh_mode)
        layout.addLayout(header)
        layout.addWidget(modes, 1)

        simple = QWidget()
        simple_layout = QVBoxLayout(simple)
        simple_layout.setContentsMargins(0, 8, 0, 0)
        presets = QHBoxLayout()
        self.presets = []
        for title, subtitle, constructor in (
            ("Pokémon + capacités", "CT et objets aussi", XDOptions.recommended),
            ("Pokémon seuls", "Capacités et CT conservées", XDOptions.species_only),
            ("Copie à l’identique", "Aucune randomisation", XDOptions.unchanged),
        ):
            button = window.button(title)
            window.bind(button.setAccessibleDescription, subtitle)
            button.setCheckable(True)
            button.setObjectName("preset")
            button.clicked.connect(lambda checked=False, constructor=constructor: self.set_options(constructor()))
            column = QVBoxLayout()
            column.addWidget(button)
            column.addWidget(window.note(subtitle))
            presets.addLayout(column, 1)
            self.presets.append((button, constructor()))
        simple_layout.addLayout(presets)
        self.preset_note = QLabel()
        self.preset_note.setObjectName("note")
        self.preset_note.setWordWrap(True)
        simple_layout.addWidget(self.preset_note)
        self.preset_common = window.note(
            "Les échanges de Doking suivent les Poké Places. Le tirage évite les familles en double dans l’histoire.")
        simple_layout.addWidget(self.preset_common)
        self.preset_shiny = window.note(
            "Le starter et les cadeaux ont 5 % de chance d’être chromatiques. La seed fixe le résultat.")
        simple_layout.addWidget(self.preset_shiny)
        simple_layout.addStretch(1)
        modes.addWidget(scroll_area(simple))

        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        categories = QComboBox()
        window.bind(categories.setAccessibleName, "Catégorie de réglages")
        advanced_layout.addWidget(categories, 0, Qt.AlignmentFlag.AlignLeft)
        groups = QStackedWidget()
        advanced_layout.addWidget(groups, 1)
        categories.currentIndexChanged.connect(groups.setCurrentIndex)
        modes.addWidget(advanced)
        self.rules, self.controls, forms = {}, {}, {}
        for item in RULES:
            metadata = item.metadata
            group = metadata["group"]
            if group not in forms:
                page = QWidget()
                form = QFormLayout(page)
                form.setContentsMargins(0, 8, 6, 4)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                index = groups.addWidget(scroll_area(page))
                categories.addItem("")
                window.bind(lambda value, index=index: categories.setItemText(index, value), group)
                forms[group] = form
            self.add_control(forms[group], item)

    def add_control(self, form, item):
        window = self.window
        metadata = item.metadata
        kind, title = metadata["kind"], metadata["label"]
        if kind == "bool":
            control = MenuCheckBox()
            self.rules[item.name] = control
            window.bind(control.setText, title)
            form.addRow(control)
            control.toggled.connect(self.invalidate_preview)
        else:
            if metadata.get("selector") == "species":
                control = SpeciesChoice(window, self.invalidate_preview)
                control.currentIndexChanged.connect(self.invalidate_preview)
            elif kind in ("species_set", "type_set"):
                control = ExcludedSelection(kind, window)
                control.valueChanged.connect(self.invalidate_preview)
            elif kind == "choice":
                control = QComboBox()
                for value, label in metadata["choices"]:
                    control.addItem("", value)
                    index = control.count() - 1
                    window.bind(lambda text, index=index: control.setItemText(index, text), label)
                control.currentIndexChanged.connect(self.invalidate_preview)
            else:
                control = QDoubleSpinBox() if kind == "float" else QSpinBox()
                if kind == "float":
                    control.setDecimals(metadata.get("decimals", 2))
                control.setRange(metadata["minimum"], metadata["maximum"])
                control.setSingleStep(metadata["step"])
                control.valueChanged.connect(self.invalidate_preview)
            label = window.label(title)
            label.setWordWrap(True)
            label.setBuddy(control)
            window.bind(control.setAccessibleName, title)
            form.addRow(label, control)
        if metadata["description"]:
            window.bind(control.setToolTip, metadata["description"])
        self.controls[item.name] = control

    def refresh_mode(self, index):
        for current, button in enumerate(self.mode_buttons):
            button.setChecked(current == index)

    def disclosure(self, label, content):
        button = QToolButton()
        self.window.bind(button.setText, label)
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setArrowType(Qt.ArrowType.RightArrow)
        content.hide()
        button.toggled.connect(content.setVisible)
        button.toggled.connect(lambda expanded: button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow))
        return button

    def focus_current_step(self):
        (self.source, self.seed, self.destination)[self.step].setFocus()

    def refresh_navigation(self):
        text = self.window.text
        for index, button in enumerate(self.step_buttons):
            button.setChecked(index == self.step)
            button.setIcon(self.window.cursor_icon if index == self.step else QIcon())
            button.setEnabled(not self.window.busy)
        self.home_button.setText(text("Accueil" if self.step == 0 else "Retour"))
        self.create_button.setText(text("Créer la ROM" if self.step == 2 else "Continuer"))
        for button in (self.home_button, self.create_button):
            button.setEnabled(not self.window.busy)
        if self.window.game_views.currentWidget() is self:
            self.window.profile_menu.setEnabled(not self.window.busy)
        self.status.setText(text(self.status_message or STEP_HELP[self.step]))
        self.refresh_review()

    def refresh_review(self):
        if not hasattr(self, "review"):
            return
        text = self.window.text
        options = self.current_options()
        entries = [text("Seed") + "  " + self.seed.text()]
        defaults = XDOptions.unchanged()
        for item in RULES:
            name, metadata = item.name, item.metadata
            value = getattr(options, name)
            if not self.rule_applies(options, name):
                continue
            if value == getattr(defaults, name) and name not in ("starter_stage", "shiny_chance_percent"):
                continue
            label = text(metadata["label"])
            if metadata["kind"] == "choice":
                value = text(dict(metadata["choices"])[value])
            elif metadata.get("selector") == "species":
                value = SPECIES_NAMES[self.window.language].get(value, value)
            elif metadata["kind"] in ("species_set", "type_set"):
                value = len(value)
            entries.append(label if metadata["kind"] == "bool" else f"{label}  {value}")
        self.review.setText("\n".join(entries))

    def refresh_presets(self):
        options = self.current_options()
        descriptions = (
            "Change les Pokémon, les capacités, les CT et les objets dans XD.",
            "Change les Pokémon. Les capacités, les CT et les objets suivent leurs règles d’origine.",
            "Ces réglages produisent une copie à l’identique.",
        )
        description = "Réglages personnalisés"
        randomizing = False
        for (button, preset), note in zip(self.presets, descriptions, strict=True):
            selected = preset == options
            button.setChecked(selected)
            button.setIcon(self.window.cursor_icon if selected else QIcon())
            if selected:
                description = note
                randomizing = preset != XDOptions.unchanged()
        self.preset_note.setText(self.window.text(description))
        self.preset_common.setVisible(randomizing)
        self.preset_shiny.setVisible(randomizing)

    @staticmethod
    def rule_applies(options, name):
        if name == "trainer_level_multiplier":
            return not options.progressive_levels
        if name == "tm_ensure_offensive":
            return options.tm_compatibility_mode != "original"
        required = DEPENDENCIES.get(name)
        return required is None or any(getattr(options, rule) for rule in required)

    def go_back(self):
        if self.step == 0:
            self.window.show_home()
        else:
            self.go_step(self.step - 1)

    def advance(self):
        if self.step == 2:
            self.start()
        else:
            self.go_step(self.step + 1)

    def go_step(self, index):
        if self.window.busy:
            self.refresh_navigation()
            return
        if index > self.step:
            try:
                self.validate_source()
                if index == 2:
                    validate_seed(self.seed.text())
            except (UserError, OSError) as error:
                if isinstance(error, RVZToolRequired):
                    self.source_conversion.setChecked(True)
                    self.tool.setFocus()
                self.failed(error, False)
                self.refresh_navigation()
                return
        self.step = index
        self.pages.setCurrentIndex(index)
        self.set_status()
        self.refresh_navigation()
        self.focus_current_step()

    def validate_source(self):
        value = self.source.text().strip()
        source = Path(value)
        if source.suffix.lower() not in (".iso", ".rvz") or not source.is_file():
            raise UserError("Sélectionnez un fichier ISO ou RVZ existant.")
        if source.suffix.lower() == ".iso":
            check_header(source, is_xd=True)
        elif not self.tool.text().strip() or not Path(self.tool.text().strip()).is_file():
            raise RVZToolRequired("Pour utiliser le format RVZ, sélectionnez DolphinTool dans votre installation de Dolphin.")

    def import_configuration(self, path, *, report=False):
        try:
            profile = load_xd_creation_report(path) if report else load_profile(path, is_xd=True)
        except (UserError, OSError) as error:
            self.set_status(Message("Import impossible : {error}", error=self.window.error_message(error)), error=True)
            return
        self.set_options(profile.options)
        self.seed.setText(profile.seed)
        if profile.xd_spot_migration:
            self.set_status(XD_SPOT_MIGRATION)
            return
        message = "Seed et réglages repris depuis le rapport." if report else Message("Profil chargé : {name}.", name=path.name)
        self.set_status(message)

    def export_configuration(self, path):
        try:
            save_profile(path, self.seed.text(), self.current_options())
        except (UserError, OSError) as error:
            self.set_status(Message("Export impossible : {error}", error=self.window.error_message(error)), error=True)
            return
        self.set_status(Message("Profil enregistré : {path}.", path=path))

    def build_preview(self):
        preview = QVBoxLayout()
        preview.setSpacing(7)
        header = QHBoxLayout()
        heading = self.window.label("Aperçu de la seed")
        heading.setObjectName("subheading")
        header.addWidget(heading, 1)
        self.preview_button = self.window.button("Calculer l’aperçu")
        self.preview_button.clicked.connect(self.start_preview)
        header.addWidget(self.preview_button)
        self.preview_cancel = self.window.button("Annuler l’aperçu")
        self.preview_cancel.setProperty("menuSound", "back")
        self.preview_cancel.clicked.connect(self.window.cancel)
        header.addWidget(self.preview_cancel)
        preview.addLayout(header)
        self.preview_status = QLabel()
        self.preview_status.setObjectName("note")
        self.preview_status.setWordWrap(True)
        self.preview_status.setTextFormat(Qt.TextFormat.PlainText)
        preview.addWidget(self.preview_status)
        self.preview_progress = QProgressBar()
        self.preview_progress.setObjectName("previewProgress")
        self.preview_progress.setTextVisible(False)
        self.window.bind(self.preview_progress.setAccessibleName, "Aperçu de la seed")
        preview.addWidget(self.preview_progress)
        self.encounter_tabs = QTabBar()
        self.encounter_tabs.setObjectName("previewTabs")
        self.encounter_tabs.setUsesScrollButtons(False)
        self.encounter_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.window.bind(self.encounter_tabs.setAccessibleName, "Groupes de Pokémon")
        for label in ("Starter · 1", "Obscurs · 83", "Cadeaux · 7", "Poké Places · 9"):
            index = self.encounter_tabs.addTab("")
            self.window.bind(lambda text, index=index: self.encounter_tabs.setTabText(index, text), label)
        preview.addWidget(self.encounter_tabs)
        self.preview_starter_row = QWidget()
        starter_row = QHBoxLayout(self.preview_starter_row)
        starter_row.setContentsMargins(0, 0, 0, 0)
        starter_row.setSpacing(10)
        self.preview_portrait = QLabel()
        self.preview_portrait.setObjectName("previewPortrait")
        self.preview_portrait.setFixedSize(42, 42)
        self.preview_portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        starter_row.addWidget(self.preview_portrait)
        self.preview_starter = QLabel()
        self.preview_starter.setObjectName("subheading")
        self.preview_starter.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_starter.setWordWrap(True)
        starter_row.addWidget(self.preview_starter, 1)
        self.starter_details = self.window.button("Fiche Pokémon")
        self.starter_details.clicked.connect(self.open_starter_details)
        starter_row.addWidget(self.starter_details)
        preview.addWidget(self.preview_starter_row)
        self.preview_search = QLineEdit()
        self.preview_search.setClearButtonEnabled(True)
        self.window.bind(self.preview_search.setPlaceholderText, "Rechercher un Pokémon…")
        self.window.bind(self.preview_search.setAccessibleName, "Rechercher un Pokémon…")
        self.preview_search.textChanged.connect(self.render_preview)
        preview.addWidget(self.preview_search)
        self.preview_details = QTreeWidget()
        self.preview_details.setObjectName("encountersPreview")
        self.preview_details.setColumnCount(2)
        self.preview_details.setRootIsDecorated(False)
        self.preview_details.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_details.setUniformRowHeights(True)
        self.preview_details.setIconSize(QSize(28, 28))
        self.preview_details.setItemDelegate(PreviewNameDelegate(self.preview_details))
        self.preview_details.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.window.bind(self.preview_details.setAccessibleName, "Détails de l’aperçu XD")
        self.preview_details.itemClicked.connect(self.open_encounter_details)
        self.preview_details.itemActivated.connect(self.open_encounter_details)
        preview.addWidget(self.preview_details, 1)
        self.preview_space = QWidget()
        preview.addWidget(self.preview_space, 1)
        self.encounter_tabs.currentChanged.connect(self.render_preview)
        return preview

    def current_options(self):
        values = {}
        for name, control in self.controls.items():
            if name in self.rules:
                values[name] = control.isChecked()
            elif isinstance(control, QComboBox) and not isinstance(control, SpeciesChoice):
                values[name] = control.currentData()
            else:
                values[name] = control.value()
        values["unique_shadow_families"] &= values["randomize_shadows"]
        return XDOptions(**values)

    def set_options(self, options):
        for name, control in self.controls.items():
            value = getattr(options, name)
            with QSignalBlocker(control):
                if name in self.rules:
                    control.setChecked(value)
                elif isinstance(control, QComboBox):
                    control.setCurrentIndex(control.findData(value))
                else:
                    control.setValue(value)
        self.invalidate_preview()

    def preview_configuration(self):
        def file_key(value):
            path = value.strip()
            if not path:
                return "", None
            try:
                stat = Path(path).stat()
                return path, (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            except (OSError, ValueError):
                return path, None

        source = self.source.text().strip()
        tool = file_key(self.tool.text()) if Path(source).suffix.lower() == ".rvz" else None
        return file_key(source), self.seed.text(), self.current_options(), tool

    def refresh_preview_identity(self):
        if self.preview_key is not None and self.preview_key != self.preview_configuration():
            self.invalidate_preview()

    @Slot()
    def invalidate_preview(self):
        options = self.current_options()
        for name, control in self.controls.items():
            control.setEnabled(self.rule_applies(options, name))
        self.refresh_review()
        self.refresh_presets()
        if self.preview_key is not None:
            self.preview_key = self.preview_result = None
            if self.preview_running:
                self.window.cancel_event.set()
                self.preview_cancel.setEnabled(False)
            self.preview_message = "Seed ou réglages modifiés. Actualisez l’aperçu."
        elif not self.preview_running:
            self.preview_message = ("L’aperçu utilise la ROM, la seed et les réglages ci-dessus."
                                    if self.source.text().strip() else
                                    "Choisissez la ROM d’origine pour calculer l’aperçu.")
        self.preview_error = False
        self.render_preview()

    @Slot()
    def start_preview(self):
        if self.window.busy or self.window.preview_thread is not None:
            return
        self.refresh_preview_identity()
        if self.preview_result is not None:
            return
        source = self.source.text().strip()
        if not source:
            self.preview_failed(UserError("Choisissez la ROM d’origine pour calculer l’aperçu."), False)
            return
        from .preview import preview_xd

        tool = self.tool.text().strip()
        self.preview_key = self.preview_configuration()
        self.preview_running = True
        self.preview_error = False
        self.preview_message = "Calcul en cours…"
        self.preview_progress.setRange(0, 0)
        self.preview_cancel.setEnabled(True)
        self.home_button.setEnabled(False)
        self.create_button.setEnabled(False)
        self.render_preview()
        self.preview_cancel.setFocus()
        self.window.start_worker(
            dict(source=Path(source), seed=self.seed.text(), xd_options=self.preview_key[2],
                 dolphin_tool=Path(tool) if tool else None, cache=self.window.preview_cache),
            self.on_preview_progress, self.preview_succeeded, self.preview_failed,
            task=preview_xd,
            failure_message="Impossible de calculer l’aperçu. Vérifiez la ROM et les réglages, puis réessayez.",
        )
        self.refresh_navigation()

    @Slot(int, object)
    def on_preview_progress(self, percent, message):
        if self.preview_key is None or self.window.cancel_event.is_set():
            return
        if percent > 0:
            self.preview_progress.setRange(0, 100)
            self.preview_progress.setValue(percent)
        self.preview_message = message
        self.preview_status.setText(self.window.text(message))

    @Slot(dict)
    def preview_succeeded(self, result):
        self.refresh_preview_identity()
        if self.preview_key is None:
            return
        if self.window.cancel_event.is_set():
            self.preview_failed("", True)
            return
        self.preview_result = result
        self.preview_message = ("Aperçu à jour" if result.get("starter") or result.get("gifts")
                                else "Ces réglages produisent une copie à l’identique.")
        focus_result = self.preview_cancel.hasFocus()
        self.render_preview()
        if focus_result:
            target = self.preview_details if not self.preview_details.isHidden() else self.create_button
            target.setFocus()

    @Slot(object, bool)
    def preview_failed(self, error, cancelled):
        if self.preview_running and self.preview_key is None:
            return
        self.preview_key = self.preview_result = None
        self.preview_error = not cancelled
        if cancelled:
            self.preview_message = "Aperçu annulé."
        else:
            self.preview_message = self.window.error_message(error) if isinstance(error, Exception) else error
        self.render_preview()

    def render_preview(self):
        ready = self.preview_result is not None
        self.preview_button.setVisible(not self.preview_running and not ready)
        self.preview_cancel.setVisible(self.preview_running and not ready)
        self.preview_progress.setVisible(self.preview_running and not ready)
        status_style = "color: #ffb4c4;" if self.preview_error else ""
        if self.preview_status.styleSheet() != status_style:
            self.preview_status.setStyleSheet(status_style)
        self.preview_status.setText(self.window.text(self.preview_message))
        data = self.preview_result or {}
        names = SPECIES_NAMES[self.window.language]
        ids = data.get("national_ids", {})

        def name(index):
            national = ids.get(str(index), index)
            return names.get(national, f"#{national}").capitalize()

        def encounter(row, *, rich=False, show_original=False):
            species = row["species"]
            shown = name(species)
            if rich:
                shown = shiny_name_html(shown, 14) if row.get("shiny") else escape(shown)
            original = row.get("original", species)
            if show_original and original != species:
                native = escape(name(original)) if rich else name(original)
                shown = f"{native} → {shown}"
            level = row.get("level")
            if row.get("levels"):
                level = "–".join(map(str, row["levels"]))
            return self.window.text("{name} · Niv. {level}", name=shown, level=level) if level is not None else shown

        tab = self.encounter_tabs.currentIndex()
        starter = data.get("starter")
        show_starter = bool(starter and tab == 0)
        self.preview_starter_row.setVisible(show_starter)
        self.preview_starter.setVisible(show_starter)
        self.starter_details.setVisible(bool(show_starter and starter.get("details")))
        if starter:
            rich = bool(starter.get("shiny"))
            self.preview_starter.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
            self.preview_starter.setText(self.window.text(
                "Pokémon de départ · {pokemon}", pokemon=encounter(starter, rich=rich, show_original=True)))
        portrait = QPixmap()
        png = starter.get("portrait_png") if starter else None
        if isinstance(png, bytes):
            portrait.loadFromData(png)
        self.preview_portrait.setVisible(not portrait.isNull())
        self.preview_portrait.setPixmap(portrait.scaled(
            40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            if not portrait.isNull() else portrait)

        tree = self.preview_details
        position = tree.verticalScrollBar().value()
        tree.clear()
        tree.setHeaderLabels([self.window.text("Pokémon d’origine"), self.window.text("Avec cette seed")])
        shadows = data.get("decks", {}).get("Story", {}).get("shadows", ())
        spots = data.get("poke_spots", ())
        gifts = data.get("gifts", ())
        query = search_key(self.preview_search.text().strip())
        def gift_origin(row, *, original=False):
            required_species = row.get("required_species")
            if required_species is not None:
                evolution = row.get("required_evolution")
                if original:
                    required_species = GIFT_TRADE_REQUIREMENTS.get(row["key"], required_species)
                    if evolution is not None:
                        evolution = TOGETIC
                if evolution is not None:
                    return self.window.text("Échange contre {pokemon} ou {evolution}",
                                            pokemon=name(required_species), evolution=name(evolution))
                return self.window.text("Échange contre {pokemon}", pokemon=name(required_species))
            return self.window.text("Mont Bataille") if row.get("key", "").startswith("mt-battle-") else ""

        rows = ()
        if tab == 1:
            rows = [(row, f"#{row['shadow_id']:02d}", "") for row in shadows]
        elif tab == 2:
            rows = []
            for row in gifts:
                original_offer = gift_origin(row, original=True)
                seeded_offer = gift_origin(row)
                suffix = f" · {seeded_offer}" if seeded_offer != original_offer else ""
                rows.append((row, original_offer, suffix))
        elif tab == 3:
            rows = [(row, self.window.text(SPOT_LABELS.get(row["spot"], row["spot"])),
                     f" · {row['chance']} %") for row in spots]
        for row, prefix, suffix in rows:
            original = name(row.get("original", row["species"]))
            native = f"{prefix} · {original}" if prefix else original
            result = f"{encounter(row)}{suffix}"
            number = ids.get(str(row["species"]), row["species"])
            if query and query not in search_key(f"{native} {result} #{number:03d}"):
                continue
            child = QTreeWidgetItem(tree, [native, result])
            child.setData(0, Qt.ItemDataRole.UserRole + 2, row)
            if row.get("portrait_png"):
                child.setIcon(1, self.window.preview_portrait(row))
            if row.get("shiny"):
                child.setData(1, RICH_NAME_ROLE, f"{encounter(row, rich=True)}{escape(suffix)}")
        self.preview_search.setVisible(ready and tab > 0)
        tree.setVisible(ready and tab > 0)
        self.preview_space.setVisible(tree.isHidden())
        if ready:
            tree.verticalScrollBar().setValue(position)

    def open_starter_details(self):
        row = (self.preview_result or {}).get("starter")
        if row:
            self.open_sheet(row)

    def open_encounter_details(self, item, _column):
        row = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if row:
            self.open_sheet(row)

    def open_sheet(self, row):
        if row.get("details"):
            self.window.show_pokemon_detail(dict(row, national_dex=row["details"]["national_dex"]))

    def section(self, title):
        group = QVBoxLayout()
        group.setSpacing(7)
        label = self.window.label(title)
        label.setObjectName("section")
        group.addWidget(label)
        return group

    def path_row(self, field, choose):
        browse = self.window.button("Parcourir…")
        browse.clicked.connect(choose)
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(browse)
        return row

    def choose_source(self):
        text = self.window.text
        path, _ = QFileDialog.getOpenFileName(self, text("Choisir la ROM d’origine"),
                                             self.source.text(), text("ROM GameCube (*.iso *.rvz)"))
        if path:
            self.source.setText(path)

    def choose_destination(self):
        text = self.window.text
        suffix = self.format.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(
            self, text("Choisir où enregistrer la ROM"), self.destination.text(),
            text("Image {format} (*.{extension})", format=suffix.upper(), extension=suffix),
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if path:
            self.destination.setText(path if Path(path).suffix else f"{path}.{suffix}")

    def source_changed(self, value):
        source = Path(value.strip())
        suffix = source.suffix.lower()
        if suffix in (".iso", ".rvz"):
            self.format.setCurrentText(suffix[1:].upper())
            if not self.destination.text().strip():
                self.destination.setText(str(source.with_name(f"xd-randomized{suffix}")))
        self.update_tool()

    def destination_changed(self, value):
        suffix = Path(value.strip()).suffix.lower()
        if suffix in (".iso", ".rvz"):
            self.format.setCurrentText(suffix[1:].upper())
        self.update_tool()

    def format_changed(self, value):
        destination = self.destination.text().strip()
        suffix = "." + value.lower()
        if destination and Path(destination).name and Path(destination).suffix.lower() != suffix:
            self.destination.setText(str(Path(destination).with_suffix(suffix)))
        self.update_tool()

    def update_tool(self):
        source_rvz = Path(self.source.text().strip()).suffix.lower() == ".rvz"
        self.source_conversion.setVisible(source_rvz)
        self.tool_block.setVisible(source_rvz and self.source_conversion.isChecked())
        self.output_tool_block.setVisible(self.format.currentText() == "RVZ")

    def set_status(self, message="", *, error=False):
        if error != self.status_error:
            self.status_error = error
            self.status.setStyleSheet("color: #ffb4c4;" if error else "")
        if message != self.status_message:
            self.status_message = message
            self.status.setText(self.window.text(message or STEP_HELP[self.step]))

    def retranslate(self):
        for control in self.controls.values():
            if isinstance(control, (SpeciesChoice, ExcludedSelection)):
                control.retranslate()
        self.refresh_navigation()
        self.refresh_presets()
        self.render_preview()

    def start(self):
        if self.window.busy:
            return
        if self.window.preview_thread is not None:
            self.set_status("Un calcul est déjà en cours. Réessayez dans un instant.")
            return
        source, destination, tool = (field.text().strip() for field in (self.source, self.destination, self.tool))
        tool_path = Path(tool) if tool else None
        try:
            if not source or not destination:
                raise UserError("Choisissez la ROM d’origine et l’emplacement de la nouvelle ROM.")
            source, destination, _ = validate_paths(Path(source), Path(destination), self.seed.text(), tool_path)
            options = validate_options(self.current_options())
        except (UserError, OSError) as error:
            if isinstance(error, RVZToolRequired):
                if Path(self.source.text().strip()).suffix.lower() == ".rvz":
                    self.go_step(0)
                    self.source_conversion.setChecked(True)
                    self.tool.setFocus()
                else:
                    self.output_tool.setFocus()
            self.failed(error, False)
            return
        self.refresh_preview_identity()
        self.result = None
        self.folder_button.hide()
        self.report_button.hide()
        self.journal_button.hide()
        self.pages.setEnabled(False)
        self.home_button.setEnabled(False)
        self.create_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.progress.setValue(0)
        self.progress.show()
        self.set_status("Lecture de la ROM d’origine…")
        self.window.start_worker(
            dict(source=source, destination=destination, seed=self.seed.text(),
                 dolphin_tool=tool_path, journal_language=self.window.language, xd_options=options),
            self.on_progress, self.succeeded, self.failed,
        )
        self.refresh_navigation()

    @Slot(int, object)
    def on_progress(self, percent, message):
        self.progress.setValue(percent)
        self.set_status(message)

    @Slot(dict)
    def succeeded(self, report):
        self.result = report
        self.progress.setValue(100)
        self.set_status(Message("ROM créée et vérifiée.\n{path}", path=report["output"]))
        self.folder_button.show()
        self.report_button.show()
        self.journal_button.setVisible(bool(report.get("journal")))

    @Slot(object, bool)
    def failed(self, message, cancelled):
        self.set_status(self.window.error_message(message) if isinstance(message, Exception) else message,
                        error=not cancelled)

    def cancelling(self):
        if self.preview_running:
            self.preview_cancel.setEnabled(False)
            self.preview_message = "Annulation de l’aperçu…"
            self.render_preview()
        else:
            self.cancel_button.setEnabled(False)
            self.set_status("Annulation…")

    def finished(self):
        if self.preview_running:
            self.preview_running = False
            self.render_preview()
            self.refresh_navigation()
            return
        self.pages.setEnabled(True)
        self.refresh_navigation()
        self.cancel_button.hide()
        if self.result is None:
            self.progress.hide()
