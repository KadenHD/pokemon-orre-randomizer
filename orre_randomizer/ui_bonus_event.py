"""Preview the optional Colosseum event with the production team's identities."""
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from .i18n import Message
from .resources import shadow_lugia_portrait
from .ui_theme import MenuCheckBox
from .ui_workspace import starter_slot


class BonusEventPreview(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.rows = window, []
        self.randomized_slots = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        self.enabled = MenuCheckBox()
        window.bind(self.enabled.setText, "Combat bonus : Lugia obscur")
        self.enabled.toggled.connect(window.rule_checks["postgame_shadow_lugia"].setChecked)
        layout.addWidget(self.enabled)
        self.conditions = window.note("Relique Sacrée · Après avoir capturé et purifié les 48 Pokémon obscurs d’origine.")
        layout.addWidget(self.conditions)
        layout.addWidget(window.note("Jakylla menace la Relique Sacrée avec six Pokémon de niveau 65 à 70. Il reste sur place tant que son Pokémon obscur n’est pas capturé."))
        self.off_note = window.note("Activez ce combat pour l’ajouter à la nouvelle ROM.")
        layout.addWidget(self.off_note)
        self.team = QWidget()
        self.grid = QGridLayout(self.team)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(16)
        self.slots, self.cards, self.columns = [], [], 2
        for index in range(6):
            card, portrait, name, button = starter_slot(window, Message("Pokémon {number}", number=index + 1),
                lambda checked=False, i=index: self.open_detail(i))
            self.grid.addLayout(card, index // 2, index % 2)
            self.grid.setColumnStretch(index % 2, 1)
            self.cards.append(card)
            self.slots.append((portrait, name, button))
        layout.addWidget(self.team)
        self.shiny_note = window.note("Lugia obscur chromatique est blanc et noir. Après purification, il retrouve l’apparence chromatique rose de Lugia.")
        layout.addWidget(self.shiny_note)
        layout.addStretch(1)

    def render(self, options, result):
        active = options.postgame_shadow_lugia
        with QSignalBlocker(self.enabled):
            self.enabled.setChecked(active)
        self.enabled.setEnabled(not self.window.busy and self.window.preview_thread is None)
        self.off_note.setVisible(not active)
        self.team.setVisible(active)
        event = result.get("postgame_shadow_lugia", {}) if result else {}
        self.rows = event.get("team", []) if event.get("enabled") else []
        self.randomized_slots = tuple(range(5)) if options.postgame_randomize_team else ()
        if options.postgame_randomize_lugia:
            self.randomized_slots += (5,)
        lugia = (self.rows[-1].get("species") == 249 or self.rows[-1].get("national_dex") == 249
                 if len(self.rows) == 6 else not options.postgame_randomize_lugia)
        self.shiny_note.setVisible(active and lugia)
        self.shiny_note.setText(self.window.text(
            "Lugia obscur chromatique est blanc et noir. L’option de conservation de son apparence est activée : il garde ce modèle après purification."
            if options.keep_shadow_lugia_after_purification else
            "Lugia obscur chromatique est blanc et noir. Après purification, il retrouve l’apparence chromatique rose de Lugia."))
        for index, (portrait, name, button) in enumerate(self.slots):
            row = self.rows[index] if index < len(self.rows) else (
                {"national_dex": (282, 178, 356, 365, 257, 249)[index]
                    if index not in self.randomized_slots else None, "level": 65 + index,
                 "shiny": bool(index not in self.randomized_slots and options.custom_shinies
                               and options.shiny_chance_percent == 100)})
            if (index == 5 and (row.get("species") == 249 or row.get("national_dex") == 249)
                    and not row.get("portrait_png")):
                row = dict(row, portrait_png=shadow_lugia_portrait(shiny=bool(row.get("shiny"))))
            plain = self.window.preview_row_name(row)
            markup = self.window.preview_row_name(row, rich=True) if row.get("shiny") else None
            name.setTextFormat(Qt.TextFormat.RichText if markup else Qt.TextFormat.PlainText)
            name.setText(markup or plain)
            portrait.setPixmap(self.window.preview_portrait(row).pixmap(42, 42))
            portrait.setAccessibleName(plain)
            portrait.setToolTip(plain)
            ready = bool(row.get("details"))
            button.setVisible(ready)
            button.setEnabled(ready)

    def open_detail(self, index):
        if index < len(self.rows):
            self.window.show_pokemon_detail(self.rows[index])

    def animate(self, sample):
        if self.rows or not self.enabled.isChecked():
            return
        for index in self.randomized_slots:
            portrait, name, _button = self.slots[index]
            text, icon = sample(index)
            name.setTextFormat(Qt.TextFormat.PlainText)
            name.setText(text)
            portrait.setPixmap(icon.pixmap(42, 42))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 3 if self.width() >= 850 else 2
        if columns != self.columns:
            for card in self.cards:
                self.grid.removeItem(card)
            for index, card in enumerate(self.cards):
                self.grid.addLayout(card, index // columns, index % columns)
            for column in range(3):
                self.grid.setColumnStretch(column, int(column < columns))
            self.columns = columns
