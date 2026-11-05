"""Pokémon XD creation form, sharing the desktop's validation and job runner."""

from dataclasses import fields, replace
from html import escape
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QSize, Qt, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QProgressBar, QSpinBox, QToolButton, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .i18n import Message
from .locales.selection_names import SPECIES_NAMES
from .profiles import XD_SPOT_MIGRATION, load_profile, load_xd_creation_report, save_profile, validate_seed
from .service import RVZToolRequired, UserError, check_header, validate_paths
from .ui_icons import CATEGORY_SYMBOLS
from .ui_exclusions import ExcludedSelection, search_key
from .settings_presentation import search_settings
from .ui_pokemon_names import RICH_NAME_ROLE, shiny_name_html
from .ui_species import SpeciesChoice
from .ui_theme import MenuCheckBox
from .ui_workspace import (EncounterTable, RuleNavigation, configuration_workspace, file_field, preset_buttons,
                           preview_toolbar, scroll_area, search_field, settings_workspace, starter_slot,
                           wizard_frame, wizard_page)
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
        self.step = 0
        layout, self.pages, self.step_buttons = wizard_frame(self, window, self.go_step, xd=True)

        rom = wizard_page(self.pages)
        self.add_heading(rom, "Choisissez votre ROM")
        rom.addWidget(window.note("Pokémon XD · Europe, USA et Japon"))
        rom.addSpacing(16)
        self.source, _ = file_field(
            rom, window, "ROM d’&origine", "ROM d’origine",
            "Sélectionnez un fichier ISO ou RVZ, ou glissez-le ici", "Parcourir…", self.choose_source)
        rom.addWidget(window.note("La ROM sera vérifiée avant la création. Aucun fichier existant ne sera remplacé."))
        self.tool_block, self.tool = window.build_tool_field()
        self.tool_block.layout().addWidget(window.note(
            "DolphinTool est nécessaire pour lire ou créer une RVZ. Utilisez celui fourni avec Dolphin."))
        self.source_conversion = self.disclosure("Conversion RVZ · DolphinTool", self.tool_block)
        rom.addWidget(self.source_conversion, 0, Qt.AlignmentFlag.AlignLeft)
        rom.addWidget(self.tool_block)
        rom.addStretch(1)
        rom.addWidget(window.note("Votre ROM sert uniquement à créer une nouvelle partie."))

        settings = wizard_page(self.pages, scrolling=False)
        self.workspace_tabs, self.seed, views = settings_workspace(settings, window)
        self.workspace_tabs.currentChanged.connect(views.setCurrentIndex)
        self.workspace_tabs.currentChanged.connect(lambda _index: self.set_status() if self.step == 1 else None)
        self.build_configuration(views)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addLayout(self.build_preview())
        views.addWidget(preview)

        output = wizard_page(self.pages)
        output.setSpacing(8)
        self.add_heading(output, "Créez votre ROM")
        self.destination, _ = file_field(
            output, window, "&Nouvelle ROM", "Nouvelle ROM",
            "Choisissez où enregistrer la nouvelle ROM", "Enregistrer sous…", self.choose_destination)
        self.format = QComboBox()
        window.bind(self.format.setAccessibleName, "Format de sortie")
        self.format.addItems(("ISO", "RVZ"))
        format_row = QHBoxLayout()
        format_label = window.label("Format de sortie")
        format_label.setBuddy(self.format)
        format_row.addWidget(format_label)
        format_row.addWidget(self.format)
        format_row.addStretch(1)
        output.addLayout(format_row)
        self.output_tool_block, self.output_tool = window.build_tool_field(label=True)
        self.tool.textChanged.connect(self.output_tool.setText)
        self.output_tool.textChanged.connect(self.tool.setText)
        if tool_path:
            self.tool.setText(str(tool_path))
        output.addWidget(self.output_tool_block)
        output.addWidget(window.note("Un rapport avec la seed et les réglages sera enregistré à côté de la ROM."))
        self.review = QLabel()
        self.review.setWordWrap(True)
        self.review.setTextFormat(Qt.TextFormat.PlainText)
        self.review.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        window.bind(self.review.setAccessibleDescription, "Les valeurs mémorisées sans effet ne sont pas affichées ici.")
        self.review_toggle = self.disclosure("Réglages appliqués", self.review)
        output.addWidget(self.review_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        output.addWidget(self.review)

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

    def build_configuration(self, views):
        window = self.window
        self.configuration_pages, self.mode_buttons = configuration_workspace(window, views, self.set_advanced_mode)
        self.mode_buttons[0].setChecked(True)
        simple = QWidget()
        simple_layout = QVBoxLayout(simple)
        simple_layout.setContentsMargins(0, 8, 0, 0)
        self.presets = preset_buttons(window, simple_layout,
            (XDOptions.recommended, XDOptions.species_only, XDOptions.unchanged), self.set_options)
        self.preset_note = QLabel()
        self.preset_note.setWordWrap(True)
        simple_layout.addWidget(self.preset_note)
        self.preset_common = window.note(
            "Les échanges de Doking suivent les Poké Places. Le tirage évite les familles en double dans l’histoire.")
        simple_layout.addWidget(self.preset_common)
        self.preset_shiny = window.note(
            "Le starter et les cadeaux ont 5 % de chance d’être chromatiques. La seed fixe le résultat.")
        simple_layout.addWidget(self.preset_shiny)
        simple_layout.addStretch(1)
        self.configuration_pages.addWidget(scroll_area(simple))

        self.rule_panel = panel = RuleNavigation(window, self.reset_rule_category, xd=True)
        self.configuration_pages.addWidget(panel)
        self.rules, self.controls = {}, {}
        groups = {item.metadata["group"] for item in RULES}
        self.rule_groups = tuple(group for group in CATEGORY_SYMBOLS if group in groups)
        for group in self.rule_groups:
            page = QWidget()
            form = QVBoxLayout(page)
            form.setSpacing(8)
            for item in RULES:
                if item.metadata["group"] == group:
                    self.add_control(form, item)
            form.addStretch(1)
            panel.add_category(group, scroll_area(page))
        panel.categories.setCurrentRow(0)
        panel.categories.currentRowChanged.connect(self.rule_category_changed)
        panel.search.textChanged.connect(self.search_rules)
        panel.search.returnPressed.connect(lambda: self.open_rule_result(panel.results.currentItem()))
        panel.results.itemClicked.connect(self.open_rule_result)
        panel.results.itemActivated.connect(self.open_rule_result)
        self.rule_category_changed()

    def set_advanced_mode(self, advanced):
        for index, button in enumerate(self.mode_buttons):
            button.setChecked(index == int(advanced))
        self.configuration_pages.setCurrentIndex(int(advanced))
        if not advanced:
            self.rule_panel.search.clear()

    def rule_category_changed(self, *_):
        panel = self.rule_panel
        index = panel.categories.currentRow()
        if index < 0:
            return
        group = self.rule_groups[index]
        category = self.window.text(group)
        panel.selector.setToolTip(category)
        description = self.window.text(
            "Rétablir uniquement « {category} » selon le mode « Pokémon + capacités ». Les autres catégories restent intactes.",
            category=category)
        panel.reset.setToolTip(description)
        panel.reset.setAccessibleName(description)

    def search_rules(self, *_):
        panel = self.rule_panel
        matches = search_settings(panel.search.text(), self.window.language, options_type=XDOptions)
        panel.show_results(matches, busy=self.window.busy)

    def open_rule_result(self, item):
        panel = self.rule_panel
        if item is None or not panel.search.text().strip():
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        metadata = next(rule.metadata for rule in RULES if rule.name == name)
        panel.search.clear()
        panel.categories.setCurrentRow(self.rule_groups.index(metadata["group"]))
        control = self.controls[name]
        page = panel.pages.currentWidget()
        page.ensureWidgetVisible(control, 12, 24)
        if control.isEnabled():
            control.setFocus(Qt.FocusReason.OtherFocusReason)
        self.set_status(Message("Réglage : {label}.", label=self.window.text(metadata["label"])))
        QTimer.singleShot(0, self, lambda: page.ensureWidgetVisible(control, 12, 24))

    def reset_rule_category(self):
        if self.window.busy:
            return
        group = self.rule_groups[self.rule_panel.categories.currentRow()]
        reference = XDOptions.recommended()
        values = {item.name: getattr(reference, item.name) for item in RULES if item.metadata["group"] == group}
        self.set_options(replace(self.current_options(), **values))
        self.set_status(Message("Catégorie « {category} » : valeurs conseillées rétablies.",
                                category=self.window.text(group)))

    def add_control(self, form, item):
        window = self.window
        metadata = item.metadata
        kind, title = metadata["kind"], metadata["label"]
        if kind == "bool":
            control = MenuCheckBox()
            self.rules[item.name] = control
            window.bind(control.setText, title)
            form.addWidget(control)
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
            row = QFormLayout()
            row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            row.addRow(label, control)
            form.addLayout(row)
        if metadata["description"]:
            window.bind(control.setToolTip, metadata["description"])
            window.bind(control.setAccessibleDescription, metadata["description"])
        self.controls[item.name] = control

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
        self.status.setText(text(self.status_message or self.step_help()))
        self.refresh_review()

    def step_help(self):
        if self.step == 1 and self.workspace_tabs.currentIndex() == 1:
            return "Aperçu pour une nouvelle partie. Aucune ROM n’a été créée."
        return STEP_HELP[self.step]

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
        for (button, constructor), note in zip(self.presets, descriptions, strict=True):
            preset = constructor()
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
        window = self.window
        preview = QVBoxLayout()
        preview.setSpacing(6)
        (self.encounter_tabs, self.preview_button, self.preview_cancel, self.preview_status,
         self.preview_progress) = preview_toolbar(
            preview, window, ("Starter · 1", "Obscurs · 83", "Cadeaux · 7", "Poké Places · 9"),
            self.start_preview, window.cancel)
        self.preview_hint = window.note("Calculez l’aperçu pour afficher le tirage de cette seed.")
        self.preview_hint.setTextFormat(Qt.TextFormat.PlainText)
        preview.addWidget(self.preview_hint)
        self.preview_search = search_field(window, "Rechercher un Pokémon…")
        self.preview_search.textChanged.connect(self.render_preview)
        preview.addWidget(self.preview_search)

        party = QWidget()
        party_layout = QVBoxLayout(party)
        party_layout.setContentsMargins(0, 12, 0, 0)
        slot, self.preview_portrait, self.preview_starter, self.starter_details = starter_slot(
            window, "Pokémon de départ", self.open_starter_details)
        party_layout.addLayout(slot)
        party_layout.addStretch(1)
        self.preview_starter_row = scroll_area(party)
        preview.addWidget(self.preview_starter_row, 1)

        self.preview_details = EncounterTable(window, "Détails de l’aperçu XD")
        self.preview_details.itemClicked.connect(self.open_encounter_details)
        self.preview_details.itemActivated.connect(self.open_encounter_details)
        preview.addWidget(self.preview_details, 1)
        footer = QHBoxLayout()
        self.encounter_hint = window.label("Cliquez sur une ligne pour ouvrir sa fiche.")
        self.encounter_hint.setObjectName("previewCount")
        footer.addWidget(self.encounter_hint)
        footer.addStretch(1)
        self.preview_count = QLabel()
        self.preview_count.setObjectName("previewCount")
        footer.addWidget(self.preview_count)
        preview.addLayout(footer)
        self.preview_details.scrollbar.valueChanged.connect(self.update_preview_count)
        self.encounter_tabs.currentChanged.connect(self.render_preview)
        return preview

    def update_preview_count(self):
        if self.preview_details.isHidden():
            self.preview_count.clear()
        else:
            self.preview_count.setText(self.preview_details.visible_count(self.window.text))

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
        self.preview_hint.setText(self.window.text(message))

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
        if self.preview_hint.styleSheet() != status_style:
            self.preview_hint.setStyleSheet(status_style)
        self.preview_hint.setText("" if ready and self.preview_message == "Aperçu à jour"
                                  else self.window.text(self.preview_message))
        self.preview_hint.setVisible(bool(self.preview_hint.text()))
        self.preview_status.setText("✓ " + self.window.text("Aperçu à jour")
                                    if ready and self.preview_message == "Aperçu à jour" else "")
        self.preview_status.setVisible(bool(self.preview_status.text()))
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
        self.preview_starter_row.setVisible(tab == 0)
        self.starter_details.setVisible(bool(starter and starter.get("details")))
        rich = bool(starter and starter.get("shiny"))
        self.preview_starter.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
        name_text = encounter(starter, show_original=True) if starter else "?"
        self.preview_starter.setText(encounter(starter, rich=True, show_original=True) if rich else name_text)
        self.preview_starter.setAccessibleName(name_text)
        portrait_row = dict(starter, national_dex=ids.get(str(starter["species"]), starter["species"])) if starter else {}
        self.preview_portrait.setPixmap(self.window.preview_portrait(portrait_row, xd=True).pixmap(42, 42))
        self.preview_portrait.setAccessibleName(name_text)
        self.preview_portrait.setToolTip(name_text)

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
            child.setSizeHint(0, QSize(0, 46))
            child.setToolTip(0, native)
            child.setToolTip(1, result)
            child.setIcon(1, self.window.preview_portrait(dict(row, national_dex=number), xd=True))
            if row.get("shiny"):
                child.setData(1, RICH_NAME_ROLE, f"{encounter(row, rich=True)}{escape(suffix)}")
        self.preview_search.setVisible(ready and tab > 0)
        tree.setVisible(tab > 0)
        self.encounter_hint.setVisible(any(row.get("details") for row, _, _ in rows))
        tree.scrollbar.setValue(position)
        self.update_preview_count()

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

    def add_heading(self, layout, title):
        label = self.window.label(title)
        label.setObjectName("section")
        layout.addWidget(label)

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
        self.status_message = message
        self.status.setText(self.window.text(message or self.step_help()))

    def retranslate(self):
        for control in self.controls.values():
            if isinstance(control, (SpeciesChoice, ExcludedSelection)):
                control.retranslate()
        self.refresh_navigation()
        self.refresh_presets()
        self.rule_category_changed()
        self.search_rules()
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
