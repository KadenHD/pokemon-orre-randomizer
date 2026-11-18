"""Pokémon XD creation form, sharing the desktop's validation and job runner."""

from dataclasses import replace
from html import escape
from pathlib import Path
import threading

from PySide6.QtCore import QSignalBlocker, QSize, Qt, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QProgressBar, QSpinBox, QToolButton, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .i18n import Message
from .locales.selection_names import SPECIES_NAMES
from .profiles import XD_SPOT_MIGRATION, load_creation_report, load_profile, save_profile, validate_seed
from .disc_images import FORMATS, SUFFIXES, RAW_SUFFIXES
from .service import UserError, check_header, validate_paths
from .ui_icons import CATEGORY_SYMBOLS
from .ui_exclusions import ExcludedSelection, search_key
from .settings_presentation import (configuration_review, effective_xd_setting_names,
                                    presentation_fields, search_settings)
from .ui_pokemon_names import RICH_NAME_ROLE, shiny_name_html
from .ui_species import SpeciesChoice
from .ui_theme import MenuCheckBox
from .ui_workspace import (CreationLog, EncounterTable, RuleNavigation, configuration_workspace, file_field, preset_buttons,
                           preview_toolbar, scroll_area, search_field, settings_workspace, starter_slot,
                           wizard_frame, wizard_page)
from .xd import XDOptions, validate_options
from .xd_gifts import GIFT_TRADE_REQUIREMENTS, SPOT_LABELS, TOGETIC, duking_trade_encounters
from .xd_preview import baseline_rows
from .preview import ROULETTE_SPECIES
from .workspace_copy import (CATEGORY_HELP, CUSTOM_PRESET, PRESET_DESCRIPTIONS, PRESET_EVOLUTIONS,
                             PRESET_LEGENDARIES, PRESET_SHINIES, ROM_DESCRIPTION, ROM_USE_NOTICE,
                             STEP_HELP, XD_CATEGORY_HELP, XD_PRESET_NATIVE)
from .ui_game_folder import PlayFolderFields
from .play_folders import create_game_folder


RULES = presentation_fields(XDOptions)
MOVE_RULES = ("randomize_trainer_moves", "randomize_starter_moves", "randomize_gift_moves", "randomize_learnsets")
DEPENDENCIES = {
    "poke_spots_full_pokedex": ("randomize_poke_spots",),
    "poke_spot_shiny_chance_percent": ("custom_poke_spot_shinies",),
    "unique_shadow_families": ("randomize_shadows",),
    "randomize_legendary_shadows": ("randomize_shadows",),
    "boss_shadow_legendary_mode": ("randomize_shadows",),
    "boss_shadow_power_mode": ("randomize_shadows",),
    "boss_shadow_min_bst": ("randomize_shadows",),
    "starter_species": ("randomize_starter",),
    "starter_stage": ("randomize_starter",),
    "starter_three_stage_families": ("randomize_starter",),
    "shiny_chance_percent": ("custom_shinies",),
    "custom_shadow_shinies": ("custom_shinies",),
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



class XDWorkspace(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.result = None
        self.status_message = ""
        self.status_error = False
        self.creation_report = self.report_check = None
        self.report_rom_message = ""
        self.report_rom_timer = QTimer(self)
        self.report_rom_timer.setSingleShot(True)
        self.report_rom_timer.timeout.connect(lambda: window.check_report_rom(owner=self))
        self.preview_result = None
        self.preview_plan = None
        self.preview_key = None
        self.preview_running = False
        self.preview_action = "Calculer l’aperçu"
        self.roulette_faces = {}
        self.roulette_index = 0
        self.roulette_timer = QTimer(self)
        self.roulette_timer.setInterval(115)
        self.roulette_timer.timeout.connect(self.advance_roulette)
        self._cache_source_key = None
        self.preview_message = "Choisissez la ROM d’origine pour calculer l’aperçu."
        self.preview_error = False
        self.step = 0
        layout, self.pages, self.step_buttons = wizard_frame(self, window, self.go_step, xd=True)

        rom = wizard_page(self.pages)
        self.add_heading(rom, "Choisissez votre ROM")
        rom.addWidget(window.note(Message(ROM_DESCRIPTION, game="Pokémon XD")))
        rom.addSpacing(16)
        self.source, _ = file_field(
            rom, window, "ROM d’&origine", "ROM d’origine",
            "Sélectionnez un fichier ISO, GCM ou RVZ, ou glissez-le ici", "Parcourir…", self.choose_source)
        rom.addWidget(window.note("La ROM sera vérifiée avant la création. Aucun fichier existant ne sera remplacé."))
        rom.addWidget(window.note(ROM_USE_NOTICE))
        rom.addStretch(1)

        settings = wizard_page(self.pages, scrolling=False)
        self.workspace_tabs, self.seed, views = settings_workspace(settings, window)
        self.workspace_tabs.currentChanged.connect(views.setCurrentIndex)
        self.workspace_tabs.currentChanged.connect(lambda _index: self.set_status() if self.step == 1 else None)
        self.workspace_tabs.currentChanged.connect(lambda _index: self.render_preview())
        self.build_configuration(views)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addLayout(self.build_preview())
        views.addWidget(preview)

        output = wizard_page(self.pages)
        self.output_scroll = self.pages.widget(self.pages.count() - 1)
        output.setSpacing(8)
        self.output_heading = self.add_heading(output, "Créez votre ROM")
        self.rom_output_fields = QWidget()
        rom_output_layout = QVBoxLayout(self.rom_output_fields)
        rom_output_layout.setContentsMargins(0, 0, 0, 0)
        output.addWidget(self.rom_output_fields)
        self.destination, _ = file_field(
            rom_output_layout, window, "&Nouvelle ROM", "Nouvelle ROM",
            "Choisissez où enregistrer la nouvelle ROM", "Enregistrer sous…", self.choose_destination)
        self.format = QComboBox()
        window.bind(self.format.setAccessibleName, "Format de sortie")
        self.format.addItems(FORMATS)
        format_widget = QWidget()
        format_row = QHBoxLayout(format_widget)
        format_row.setContentsMargins(0, 0, 0, 0)
        format_label = window.label("Format de sortie")
        format_label.setBuddy(self.format)
        format_row.addWidget(format_label)
        format_row.addWidget(self.format)
        format_row.addStretch(1)
        output.addWidget(format_widget)
        self.play_folder = PlayFolderFields(window, self, "xd")
        window.bind(lambda fallback: self.output_heading.setText(window.text("Créez votre partie") if self.play_folder.enabled.isChecked() else fallback), "Créez votre ROM")
        output.addWidget(self.play_folder)
        self.play_folder.attach_format(format_widget, output)
        self.play_folder.enabled.toggled.connect(lambda enabled: self.rom_output_fields.setVisible(not enabled))
        self.rom_output_fields.setVisible(not self.play_folder.enabled.isChecked())
        self.play_folder.enabled.toggled.connect(self.refresh_navigation)
        self.play_folder.enabled.toggled.connect(lambda enabled: self.output_heading.setText(window.text("Créez votre partie" if enabled else "Créez votre ROM")))
        output.addWidget(window.note("Un rapport avec la seed et les réglages sera enregistré à côté de la ROM."))
        self.review = QLabel()
        self.review.setWordWrap(True)
        self.review.setTextFormat(Qt.TextFormat.PlainText)
        self.review.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        window.bind(self.review.setAccessibleDescription, "Les valeurs mémorisées sans effet ne sont pas affichées ici.")
        self.review_toggle = self.disclosure("Réglages appliqués", self.review)
        self.review_toggle.toggled.connect(lambda expanded: QTimer.singleShot(0, self, self.reveal_review)
                                           if expanded else None)
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
        self.launcher_button = window.button("Ouvrir le lanceur")
        self.launcher_button.clicked.connect(window.open_result_launcher)
        self.launcher_button.hide()
        result_row.addWidget(self.launcher_button)
        result_row.addStretch(1)
        output.addLayout(result_row)
        output.addStretch(1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.report_rom_status = QLabel()
        self.report_rom_status.setObjectName("note")
        self.report_rom_status.setWordWrap(True)
        self.report_rom_status.setTextFormat(Qt.TextFormat.PlainText)
        self.report_rom_status.hide()
        layout.addWidget(self.report_rom_status)
        self.progress = QProgressBar()
        window.bind(self.progress.setAccessibleName, "Progression de la création")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.creation_log = CreationLog(layout, window)
        self.details, self.log = self.creation_log.toggle, self.creation_log.view

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
        self.source.textChanged.connect(lambda: window.schedule_report_rom_check(owner=self))
        self.destination.textChanged.connect(self.destination_changed)
        self.format.currentTextChanged.connect(self.format_changed)
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
        self.preset_common = window.note(PRESET_EVOLUTIONS)
        simple_layout.addWidget(self.preset_common)
        self.preset_legendaries = window.note(PRESET_LEGENDARIES)
        simple_layout.addWidget(self.preset_legendaries)
        self.preset_shiny = window.note(PRESET_SHINIES)
        simple_layout.addWidget(self.preset_shiny)
        self.preset_native = window.note(XD_PRESET_NATIVE)
        simple_layout.addWidget(self.preset_native)
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
            form.addWidget(window.note(XD_CATEGORY_HELP.get(group, CATEGORY_HELP.get(group, ""))))
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
        self.creation_log.set_step(self.step)
        for index, button in enumerate(self.step_buttons):
            button.setChecked(index == self.step)
            button.setIcon(self.window.cursor_icon if index == self.step else QIcon())
            button.setEnabled(not self.window.busy)
        self.home_button.setText(text("Accueil" if self.step == 0 else "Retour"))
        action = ("Créer le dossier" if self.play_folder.enabled.isChecked() else "Créer la ROM" if effective_xd_setting_names(self.current_options())
                  else "Créer une copie à l’identique")
        self.create_button.setText(text(action if self.step == 2 else "Continuer"))
        self.home_button.setEnabled(not self.window.busy)
        self.create_button.setEnabled(not self.window.busy and
                                      (self.step < 2 or self.window.preview_thread is None))
        if self.window.game_views.currentWidget() is self:
            self.window.profile_menu.setEnabled(not self.window.busy)
        self.status.setText(text(self.status_message or self.step_help()))
        self.refresh_review()
        if hasattr(self, 'known_preview'):
            self.known_preview.schedule()

    def step_help(self):
        if self.step == 1 and self.workspace_tabs.currentIndex() == 1:
            return "Aperçu pour une nouvelle partie. Aucune ROM n’a été créée."
        return STEP_HELP[self.step]

    def refresh_review(self):
        if not hasattr(self, "review"):
            return
        text = self.window.text
        options = self.current_options()
        preset = next((button.text() for button, constructor in self.presets if options == constructor()),
                      text("Personnalisés"))
        header = text("Réglages : {preset}\nSeed : {seed}", preset=preset, seed=self.seed.text())
        self.review.setText(header + "\n\n" + configuration_review(options, self.window.language))

    def reveal_review(self):
        if self.review.isVisible():
            top = self.review.mapTo(self.output_scroll.widget(), self.review.rect().topLeft()).y()
            self.output_scroll.ensureVisible(0, top + min(72, self.review.height()), 0, 12)

    def refresh_presets(self):
        options = self.current_options()
        descriptions = PRESET_DESCRIPTIONS
        description = CUSTOM_PRESET
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
        self.preset_legendaries.setVisible(randomizing)
        self.preset_shiny.setVisible(randomizing)
        self.preset_native.setVisible(randomizing)

    @staticmethod
    def rule_applies(options, name):
        if name in ("starter_stage", "starter_three_stage_families"):
            return options.randomize_starter and options.starter_species == 0
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
        if self.window.busy or self.window.home.updating:
            self.refresh_navigation()
            return
        if index > self.step:
            try:
                self.validate_source()
                if index == 2:
                    validate_seed(self.seed.text())
            except (UserError, OSError) as error:
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
        if source.suffix.lower() not in SUFFIXES or not source.is_file():
            raise UserError("Sélectionnez un fichier ISO, GCM ou RVZ existant.")
        if source.suffix.lower() in RAW_SUFFIXES:
            check_header(source, is_xd=True)

    def import_configuration(self, path, *, report=False):
        try:
            identity = load_creation_report(path, is_xd=True) if report else None
            profile = identity.profile if identity is not None else load_profile(path, is_xd=True)
        except (UserError, OSError) as error:
            self.set_status(Message("Import impossible : {error}", error=self.window.error_message(error)), error=True)
            return
        self.set_options(profile.options)
        self.seed.setText(profile.seed)
        self.creation_report = identity
        self.window.schedule_report_rom_check(owner=self)
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
            preview, window, (Message("Starters · {count}", count=1), Message("Obscurs · {count}", count=83),
                              Message("Cadeaux · {count}", count=7), "Poké Places · 9"),
            self.start_preview, self.cancel_preview)
        self.family_tab = self.encounter_tabs.addTab("")
        self.encounter_tabs.setTabVisible(self.family_tab, False)
        self.preview_hint = window.note("Calculez l’aperçu pour afficher le tirage de cette seed.")
        self.preview_hint.setTextFormat(Qt.TextFormat.PlainText)
        preview.addWidget(self.preview_hint)
        self.preview_search = search_field(window, "Rechercher un Pokémon…")
        self.preview_search.textChanged.connect(self.filter_encounters)
        preview.addWidget(self.preview_search)

        party = QWidget()
        party_layout = QVBoxLayout(party)
        party_layout.setContentsMargins(0, 12, 0, 0)
        slot, self.preview_portrait, self.preview_starter, self.starter_details = starter_slot(
            window, "Premier starter", self.open_starter_details)
        party_layout.addLayout(slot)
        self.preview_shiny_status = QLabel()
        self.preview_shiny_status.setWordWrap(True)
        self.preview_shiny_status.setObjectName("note")
        self.preview_shiny_status.setTextFormat(Qt.TextFormat.PlainText)
        party_layout.addWidget(self.preview_shiny_status)
        party_layout.addStretch(1)
        self.preview_starter_row = scroll_area(party)
        preview.addWidget(self.preview_starter_row, 1)

        self.preview_details = EncounterTable(window, "Tirage des Pokémon obscurs et offerts")
        self.preview_details.itemClicked.connect(self.open_encounter_details)
        self.preview_details.itemActivated.connect(self.open_encounter_details)
        preview.addWidget(self.preview_details, 1)
        self.family_page = QWidget()
        family_layout = QVBoxLayout(self.family_page)
        family_layout.setContentsMargins(0, 12, 0, 0)
        heading = window.label("Familles en double")
        heading.setObjectName("subheading")
        family_layout.addWidget(heading)
        self.family_duplicates = QLabel()
        self.family_duplicates.setTextFormat(Qt.TextFormat.PlainText)
        self.family_duplicates.setWordWrap(True)
        family_layout.addWidget(self.family_duplicates)
        family_layout.addStretch(1)
        self.family_scroll = scroll_area(self.family_page)
        preview.addWidget(self.family_scroll, 1)
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
        return file_key(source), self.seed.text(), self.current_options(), None

    def refresh_preview_identity(self):
        if self.preview_key is not None and self.preview_key != self.preview_configuration():
            self.invalidate_preview()

    @Slot()
    def invalidate_preview(self):
        cache_key = self.source.text().strip()
        if cache_key != self._cache_source_key:
            self.window.preview_cache.invalidate()
            self._cache_source_key = cache_key
        options = self.current_options()
        for name, control in self.controls.items():
            control.setEnabled(self.rule_applies(options, name))
        self.refresh_review()
        self.refresh_presets()
        if self.preview_key is not None and self.preview_key != self.preview_configuration():
            self.preview_key = self.preview_result = self.preview_plan = None
            if self.window.detail_window is not None:
                self.window.detail_window.close()
            if self.preview_running:
                self.window.preview_cancel_event.set()
                self.preview_cancel.setEnabled(False)
            self.preview_action = "Actualiser l’aperçu"
            self.preview_message = "Seed ou réglages modifiés. Actualisez l’aperçu."
        elif not self.preview_running:
            self.preview_message = ("L’aperçu utilise la ROM, la seed et les réglages ci-dessus."
                                    if self.source.text().strip() else
                                    "Choisissez la ROM d’origine pour calculer l’aperçu.")
        self.preview_error = False
        self.render_preview()
        self.refresh_navigation()

    @Slot()
    def start_preview(self):
        if self.window.busy or self.window.home.updating:
            return
        if hasattr(self, 'known_preview') and self.known_preview.request_full():
            return
        if self.window.preview_thread is not None:
            return
        self.refresh_preview_identity()
        if self.preview_result is not None:
            return
        source = self.source.text().strip()
        if not source:
            self.preview_failed(UserError("Choisissez la ROM d’origine pour calculer l’aperçu."), False)
            return
        from .preview import preview_xd

        try:
            validate_seed(self.seed.text())
            validate_options(self.current_options())
        except UserError as error:
            self.preview_failed(error, False)
            return
        self.preview_key = self.preview_configuration()
        self.preview_running = True
        self.preview_running_key = self.preview_key
        self.window.preview_cancel_event = threading.Event()
        self.roulette_faces.clear()
        self.roulette_index = 0
        self.preview_error = False
        self.preview_message = "Le tirage s’affichera à la fin du calcul…"
        self.preview_progress.setRange(0, 0)
        self.preview_cancel.setEnabled(True)
        self.render_preview()
        self.preview_cancel.setFocus()
        self.window.launch_preview(
            dict(source=Path(source), seed=self.seed.text(), xd_options=self.preview_key[2],
                 dolphin_tool=None, cache=self.window.preview_cache,
                 cancel=self.window.preview_cancel_event),
            owner=self, succeeded=self.preview_succeeded, failed=self.preview_failed,
            progress=self.on_preview_progress, roulette=self.load_roulette_faces,
            task=preview_xd,
        )
        self.refresh_navigation()

    @Slot(int, object)
    def on_preview_progress(self, percent, message):
        if self.preview_key is None or self.window.preview_cancel_event.is_set():
            return
        if percent > 0:
            self.preview_progress.setRange(0, 100)
            self.preview_progress.setValue(percent)
        self.preview_progress.setToolTip(self.window.text(message))

    @Slot(dict, object)
    def preview_succeeded(self, result, prepared=None):
        self.refresh_preview_identity()
        if self.preview_key is None:
            return
        if self.window.preview_cancel_event.is_set():
            self.preview_failed("", True)
            return
        self.preview_result = result
        self.preview_plan = prepared
        self.preview_message = "Aperçu pour une nouvelle partie. Aucune ROM n’a été créée."
        focus_result = self.preview_cancel.hasFocus()
        self.render_preview()
        if focus_result:
            target = self.preview_details if not self.preview_details.isHidden() else self.create_button
            target.setFocus()

    @Slot(object, bool)
    def preview_failed(self, error, cancelled):
        if self.preview_running and self.preview_key is None:
            return
        self.preview_key = self.preview_result = self.preview_plan = None
        self.preview_action = "Réessayer"
        self.preview_error = not cancelled
        if cancelled:
            self.preview_message = "Aperçu annulé."
        else:
            message = self.window.error_message(error) if isinstance(error, Exception) else error
            self.preview_message = Message("Aperçu indisponible : {error}", error=Message(message))
        self.render_preview()

    def cancel_preview(self):
        if hasattr(self, 'known_preview') and self.known_preview.running:
            self.known_preview.cancel_preview()
            return
        if not self.preview_running:
            return
        self.window.preview_cancel_event.set()
        self.preview_key = self.preview_result = self.preview_plan = None
        self.preview_action = "Réessayer"
        self.preview_message = "Annulation de l’aperçu…"
        self.render_preview()

    def finished_preview(self):
        self.preview_running = False
        self.preview_running_key = None
        if self.preview_message == "Annulation de l’aperçu…":
            self.preview_message = "Aperçu annulé."
        self.render_preview()
        self.refresh_navigation()

    def render_preview(self):
        if hasattr(self, 'known_preview'):
            self.known_preview.schedule()
        ready = self.preview_result is not None
        options = self.current_options()
        data = self.preview_rows()
        known = getattr(self, 'known_preview', None)
        loading_known = bool(known and known.running)
        self.render_family_duplicates(data)
        tab = self.encounter_tabs.currentIndex()
        rolling = (self.preview_running and self.preview_key is not None and not ready
                   and not self.window.preview_cancel_event.is_set())
        if rolling and not self.roulette_timer.isActive():
            self.roulette_timer.start()
        elif not rolling:
            self.roulette_timer.stop()
        self.preview_button.setText(self.window.text(self.preview_action))
        self.preview_button.setVisible(not self.preview_running and not ready)
        self.preview_button.setEnabled(not self.window.busy and (self.window.preview_thread is None or loading_known)
                                       and not ready and not (known and known.reveal_requested))
        self.preview_cancel.setVisible((self.preview_running or loading_known) and not ready)
        self.preview_cancel.setText(self.window.text("Annulation de l’aperçu…" if
            self.preview_running and self.window.preview_cancel_event.is_set() else "Annuler l’aperçu"))
        self.preview_cancel.setEnabled((rolling or loading_known) and not self.window.preview_cancel_event.is_set())
        self.preview_progress.setVisible((self.preview_running or loading_known) and not ready)
        if loading_known and not self.preview_running:
            self.preview_progress.setRange(0, 0)
        status_style = "color: #ffb4c4;" if self.preview_error else ""
        if self.preview_hint.styleSheet() != status_style:
            self.preview_hint.setStyleSheet(status_style)
        show_wild_rate = ready and tab == 3 and options.custom_poke_spot_shinies
        if show_wild_rate:
            self.preview_hint.setText(self.window.text("Chromatiques sauvages : {rate} % par nouvelle rencontre.",
                                                        rate=format(options.poke_spot_shiny_chance_percent, "g")))
        else:
            self.preview_hint.setText(self.window.text(self.preview_message))
        self.preview_hint.setVisible(show_wild_rate or not ready and (tab == 0 if self.preview_running else
                                      self.preview_action != "Calculer l’aperçu"))
        self.preview_status.setText("✓ " + self.window.text("Aperçu à jour") if ready else
                                    self.window.text("Calcul en cours…" if known.reveal_requested else
                                                     "Chargement des Pokémon connus…") if loading_known else "")
        self.preview_status.setToolTip(self.window.text(self.preview_message))
        self.preview_status.setVisible(bool(self.preview_status.text()))
        ids = data.get("national_ids", {})

        def name(index):
            return self.species_name(ids.get(str(index), index))

        def encounter(row, *, rich=False, show_original=False):
            shown = self.species_name(self.national_dex(row, data))
            if shown == "?":
                return shown
            if rich:
                shown = shiny_name_html(shown, 14) if row.get("shiny") else escape(shown)
            elif row.get("shiny"):
                shown += " ★"
            original = row.get("original", row["species"])
            if show_original and original != row["species"]:
                native = escape(name(original)) if rich else name(original)
                shown = f"{native} → {shown}"
            level = row.get("level")
            if row.get("levels"):
                level = "-".join(map(str, row["levels"]))
            return self.window.text("{name} · Niv. {level}", name=shown, level=level) if level is not None else shown

        starter = data.get("starter")
        self.preview_starter_row.setVisible(tab == 0)
        self.family_scroll.setVisible(tab == self.family_tab)
        self.starter_details.setVisible(bool(starter and starter.get("details")))
        rich = bool(starter and starter.get("shiny"))
        self.preview_starter.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
        name_text = encounter(starter) if starter else "?"
        self.preview_starter.setText(encounter(starter, rich=True) if rich else name_text)
        self.preview_starter.setAccessibleName(name_text)
        portrait_row = dict(starter, national_dex=self.national_dex(starter, data)) if starter else {}
        self.preview_portrait.setPixmap(self.window.preview_portrait(portrait_row, xd=True).pixmap(42, 42))
        self.preview_portrait.setAccessibleName(name_text)
        self.preview_portrait.setToolTip(encounter(starter, show_original=True) if starter else "?")
        self.preview_shiny_status.setText(self.window.shiny_status_text(options, xd=True))

        tree = self.preview_details
        position = tree.verticalScrollBar().value()
        tree.clear()
        context_header = self.window.text("Conditions d’obtention" if tab == 2 else "Lieu et fréquence") if tab in (2, 3) else None
        tree.set_context_column(context_header)
        tree.setHeaderLabels([self.window.text("Pokémon d’origine"), *([context_header] if context_header else []), self.window.text("Avec cette seed")])
        result_column = tree.result_column
        shadows = data.get("decks", {}).get("Story", {}).get("shadows", ())
        spots = data.get("poke_spots", ())
        gifts = data.get("gifts", ())
        def gift_condition(row):
            key = row.get("key")
            required = row.get("required_species")
            if required is not None:
                evolution = row.get("required_evolution")
                if evolution is not None:
                    return self.window.text("Échange contre {pokemon} ou {evolution}", pokemon=name(required), evolution=name(evolution))
                return self.window.text("Échange contre {pokemon}", pokemon=name(required))
            if key in GIFT_TRADE_REQUIREMENTS:
                return self.window.text("Échange contre {pokemon}", pokemon="?")
            return self.window.text("Mont Bataille") if key and key.startswith("mt-battle-") else ""

        rows = ()
        if tab == 1:
            rows = [(row, f"{row['shadow_id']:02d}", "") for row in shadows]
        elif tab == 2:
            rows = []
            trades = duking_trade_encounters(spots)
            for row in gifts:
                trade = trades.get(row["key"])
                condition = gift_condition(row)
                if trade is not None:
                    spot = self.window.text(SPOT_LABELS[trade["spot"]])
                    requested = trade.get("species")
                    condition = self.window.text("Doking demande {pokemon} · {spot}",
                                                 pokemon=name(requested) if requested is not None else "?", spot=spot)
                    if "chance" in trade:
                        condition += "\n" + self.window.text("{chance} % des rencontres", chance=trade["chance"])
                rows.append((row, "", condition))
        elif tab == 3:
            rows = []
            for row in spots:
                spot = self.window.text(SPOT_LABELS.get(row["spot"], row["spot"]))
                frequency = self.window.text("{chance} % des rencontres", chance=row["chance"]) if "chance" in row else "?"
                rows.append((row, "", spot + " · " + frequency))
        for row, prefix, condition in rows:
            original = name(row.get("original", row["species"]))
            native = f"{prefix} · {original}" if prefix else original
            result = encounter(row)
            number = self.national_dex(row, data)
            child = QTreeWidgetItem(tree, [native, condition, result] if context_header else [native, result])
            for column in range(tree.columnCount()):
                child.setTextAlignment(column, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            words = [native, condition, result, str(number or ""), str(row.get("shadow_id", ""))]
            for national in (number, ids.get(str(row.get("original")), row.get("original"))):
                if national:
                    words.append(f"#{national:03d}")
                    words.extend(names[national] for names in SPECIES_NAMES.values() if national in names)
            child.setData(0, Qt.ItemDataRole.UserRole, search_key(" ".join(words)))
            child.setData(0, Qt.ItemDataRole.UserRole + 2, row)
            child.setSizeHint(0, QSize(0, 54))
            child.setToolTip(0, native)
            child.setToolTip(result_column, result)
            if context_header:
                child.setToolTip(1, condition)
            child.setIcon(result_column, self.window.preview_portrait(dict(row, national_dex=number), xd=True))
            if row.get("shiny"):
                child.setData(result_column, RICH_NAME_ROLE, encounter(row, rich=True))
        tree.schedule_row_layout()
        self.preview_search.setVisible(0 < tab < self.family_tab)
        tree.setVisible(0 < tab < self.family_tab)
        self.encounter_hint.setText(self.window.text("Calcul en cours…" if rolling else
                                                    "Cliquez sur une ligne pour ouvrir sa fiche."))
        self.encounter_hint.setVisible(0 < tab < self.family_tab and
                                       (rolling or any(row.get("details") for row, _, _ in rows)))
        tree.scrollbar.setValue(position)
        self.filter_encounters()

    def filter_encounters(self):
        query = search_key(self.preview_search.text().strip())
        for index in range(self.preview_details.topLevelItemCount()):
            item = self.preview_details.topLevelItem(index)
            item.setHidden(query not in (item.data(0, Qt.ItemDataRole.UserRole) or ""))
        self.update_preview_count()

    @staticmethod
    def national_dex(row, data):
        return row.get("national_dex", data.get("national_ids", {}).get(str(row["species"]), row["species"]))

    def species_name(self, national):
        if national is None:
            return "?"
        return SPECIES_NAMES[self.window.language].get(national, f"#{national}").capitalize()

    def render_family_duplicates(self, data):
        groups = data.get("family_duplicates", [])
        self.encounter_tabs.setTabVisible(self.family_tab, bool(groups))
        self.encounter_tabs.setTabText(self.family_tab, self.window.text("Doublons · {count}", count=len(groups)))
        if not groups:
            self.family_duplicates.clear()
            return
        name = lambda row: self.species_name(self.national_dex(row, data))
        labels = {"starter": self.window.text("{name} (starter)", name=name(data["starter"]))}
        labels.update({f"shadow:{row['shadow_id']}": self.window.text("{name} (obscur nº {number})",
                       name=name(row), number=f"{row['shadow_id']:02d}")
                       for row in data.get("decks", {}).get("Story", {}).get("shadows", ())})
        labels.update({row["key"]: self.window.text("{name} (cadeau)", name=name(row)) for row in data.get("gifts", ())})
        self.family_duplicates.setText("\n\n".join(" · ".join(labels[key] for key in group) for group in groups))

    def load_roulette_faces(self, faces):
        if self.roulette_timer.isActive():
            self.roulette_faces = {dex: self.window.preview_portrait(dict(portrait_png=png), xd=True)
                                   for dex, png in faces.items()}

    def advance_roulette(self):
        if not self.preview_running or not self.isVisible() or self.workspace_tabs.currentIndex() != 1:
            return
        self.roulette_index = (self.roulette_index + 1) % len(ROULETTE_SPECIES)

        def sample(offset):
            dex = ROULETTE_SPECIES[(self.roulette_index + offset * 7) % len(ROULETTE_SPECIES)]
            return self.species_name(dex), self.roulette_faces.get(dex, self.window.xd_unknown_portrait)

        if self.encounter_tabs.currentIndex() == 0:
            if self.national_dex(baseline_rows(self.current_options())["starter"], {}) is None:
                name, icon = sample(0)
                self.preview_starter.setText(name)
                self.preview_portrait.setPixmap(icon.pixmap(42, 42))
            return
        tree = self.preview_details
        viewport = tree.viewport().rect()
        for index in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(index)
            row = item.data(0, Qt.ItemDataRole.UserRole + 2)
            if row.get("species") is None and not item.isHidden() and viewport.intersects(tree.visualItemRect(item)):
                name, icon = sample(index)
                item.setText(tree.result_column, name)
                item.setIcon(tree.result_column, icon)

    def open_starter_details(self):
        row = self.preview_rows().get("starter")
        if row:
            self.open_sheet(row)

    def open_encounter_details(self, item, _column):
        row = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if row:
            self.open_sheet(row)

    def preview_rows(self):
        if self.preview_result is not None:
            return self.preview_result
        if hasattr(self, 'known_preview'):
            return self.known_preview.rows(self.current_options())
        return baseline_rows(self.current_options())

    def open_sheet(self, row):
        if row.get("details"):
            self.window.show_pokemon_detail(dict(row, national_dex=row["details"]["national_dex"]))

    def add_heading(self, layout, title):
        label = self.window.label(title)
        label.setObjectName("section")
        layout.addWidget(label)
        return label

    def choose_source(self):
        text = self.window.text
        path, _ = QFileDialog.getOpenFileName(self, text("Choisir la ROM d’origine"),
                                             self.source.text(), text("ROM GameCube (*.iso *.gcm *.rvz)"))
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
        if suffix in SUFFIXES:
            self.format.setCurrentText(suffix[1:].upper())
            if not self.destination.text().strip():
                self.destination.setText(str(source.with_name(f"xd-randomized{suffix}")))

    def destination_changed(self, value):
        suffix = Path(value.strip()).suffix.lower()
        if suffix in SUFFIXES:
            self.format.setCurrentText(suffix[1:].upper())

    def format_changed(self, value):
        destination = self.destination.text().strip()
        suffix = "." + value.lower()
        if destination and Path(destination).name and Path(destination).suffix.lower() != suffix:
            self.destination.setText(str(Path(destination).with_suffix(suffix)))

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
        self.creation_log.retranslate()
        self.window.render_report_rom_status(owner=self)

    def start(self):
        if self.window.busy or self.window.home.updating:
            return
        if self.window.preview_thread is not None:
            self.set_status("Un calcul est déjà en cours. Réessayez dans un instant.")
            return
        self.creation_log.reset()
        source, destination = (field.text().strip() for field in (self.source, self.destination))
        try:
            if not source or (not destination and not self.play_folder.enabled.isChecked()):
                raise UserError("Choisissez la ROM d’origine et l’emplacement de la nouvelle ROM.")
            request = None
            if self.play_folder.enabled.isChecked():
                source = Path(source).expanduser().resolve()
                request = self.play_folder.request(source, "." + self.format.currentText().lower(), self.seed.text())
                destination = request.folder / "Game" / ("game." + self.format.currentText().lower())
            else:
                source, destination, _ = validate_paths(Path(source), Path(destination), self.seed.text())
            options = validate_options(self.current_options())
        except (UserError, OSError) as error:
            self.failed(error, False)
            return
        self.refresh_preview_identity()
        self.step = 2
        self.pages.setCurrentIndex(2)
        self.creation_log.set_step(2)
        self.creation_log.begin()
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
        arguments = dict(source=source, destination=destination, seed=self.seed.text(),
                 dolphin_tool=None, journal_language=self.window.language, xd_options=options,
                 prepared_patches=self.preview_plan)
        if request is not None:
            arguments["request"] = request
        self.window.start_worker(arguments,
            self.on_progress, self.succeeded, self.failed,
            task=create_game_folder if request is not None else None,
        )
        self.refresh_navigation()

    @Slot(int, object)
    def on_progress(self, percent, message):
        self.progress.setValue(percent)
        self.set_status(message)
        self.creation_log.append(message)

    @Slot(dict)
    def succeeded(self, report):
        self.result = report
        self.launcher_button.setVisible(bool(report.get("play_folder")))
        self.progress.setValue(100)
        self.set_status(Message("ROM créée et vérifiée.\n{path}", path=report["output"]))
        self.folder_button.show()
        self.report_button.show()
        self.journal_button.setVisible(bool(report.get("journal")))

    @Slot(object, bool)
    def failed(self, message, cancelled):
        message = self.window.error_message(message) if isinstance(message, Exception) else message
        self.set_status(message, error=not cancelled)
        if self.creation_log.started and self.window.busy:
            self.creation_log.append(message)

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
