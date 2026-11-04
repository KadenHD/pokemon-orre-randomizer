"""Searchable native combo for explicit starter choices; IDs survive translation."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

from .locales.selection_names import SPECIES_NAMES


class SpeciesChoice(QComboBox):
    def __init__(self, window, on_edit=None):
        super().__init__()
        self.window = window
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(16)
        self.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.retranslate()
        on_edit = on_edit or window.rules_changed
        self.lineEdit().textEdited.connect(lambda _text: on_edit())
        self.lineEdit().editingFinished.connect(self.commit_text)

    def value(self):
        typed = self.currentText().strip()
        entry = self.findText(typed, Qt.MatchFlag.MatchFixedString)
        if entry >= 0:
            return self.itemData(entry)
        if typed.lstrip("#").isdigit():
            number = int(typed.lstrip("#"))
            return number if 0 <= number <= 386 else -1
        names = SPECIES_NAMES.get(self.window.language, SPECIES_NAMES["en"])
        matches = [number for number, name in names.items() if name.casefold() == typed.casefold()]
        return matches[0] if len(matches) == 1 else -1

    def commit_text(self):
        selected = self.value()
        if selected >= 0:
            self.setCurrentIndex(self.findData(selected))

    def retranslate(self):
        selected = self.value() if self.count() else 0
        if selected < 0:
            selected = self.currentData() or 0
        blocked = self.blockSignals(True)
        self.clear()
        self.addItem(self.window.text("Tirage avec la seed"), 0)
        names = SPECIES_NAMES.get(self.window.language, SPECIES_NAMES["en"])
        for number in range(1, 387):
            self.addItem(f"{number:03d} · {names[number]}", number)
        self.setCurrentIndex(self.findData(selected))
        self.blockSignals(blocked)
