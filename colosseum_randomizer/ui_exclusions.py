"""Searchable, transactional exclusion lists in the existing desktop menu.

The checked state always means excluded. No ROM or network is needed; IDs are
National Dex IDs for species and native Gen III IDs for original types.
"""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QVBoxLayout, QWidget)

from .locales.selection_names import SPECIES_NAMES, TYPE_NAMES


def search_key(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


class ExclusionDelegate(QStyledItemDelegate):
    """Keep Qt check semantics, with the same readable cyan mark as menu rules."""
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        box = option.widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, styled, option.widget)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#d9f4eb" if checked else "#b6ccc4"), 1))
        painter.setBrush(QColor("#71e2e6" if checked else "#0b1c20"))
        painter.drawRect(box.adjusted(0, 0, -1, -1))
        if checked:
            painter.setPen(QPen(QColor("#082b24"), 2))
            painter.drawPolyline(QPolygonF([QPointF(box.x()+box.width()*.18, box.y()+box.height()*.5),
                                            QPointF(box.x()+box.width()*.42, box.y()+box.height()*.75),
                                            QPointF(box.x()+box.width()*.82, box.y()+box.height()*.22)]))
        painter.restore()


class ExclusionDialog(QDialog):
    def __init__(self, kind, values, language, text, parent=None):
        super().__init__(parent)
        self.kind, self.text = kind, text
        title = text("Pokémon exclus" if kind == "species_set" else "Types d’origine exclus")
        self.setWindowTitle(title)
        self.setModal(True)
        if parent:
            self.setPalette(parent.palette())
        self.setAutoFillBackground(True)
        self.resize(min(640, parent.width() - 48) if parent else 640,
                    min(620, parent.height() - 48) if parent else 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName("subheading")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        hint = QLabel(text("Cochez les éléments à exclure des remplacements."))
        hint.setObjectName("note")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.search = QLineEdit()
        prompt = text("Rechercher un nom ou un numéro…" if kind == "species_set" else "Rechercher un type…")
        self.search.setPlaceholderText(prompt)
        self.search.setAccessibleName(prompt)
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)
        self.items = QListWidget()
        self.items.setItemDelegate(ExclusionDelegate(self.items))
        self.items.setAccessibleName(title)
        names = SPECIES_NAMES if kind == "species_set" else TYPE_NAMES
        self.search_terms = {}
        for identifier, name in names[language].items():
            item = QListWidgetItem(f"#{identifier:03d}  {name}" if kind == "species_set" else name)
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if identifier in values else Qt.CheckState.Unchecked)
            self.items.addItem(item)
            self.search_terms[identifier] = search_key(" ".join([str(identifier), f"{identifier:03d}", *(n[identifier] for n in names.values())]))
        layout.addWidget(self.items, 1)
        actions = QHBoxLayout()
        self.exclude_results = QPushButton(text("Exclure les résultats"))
        self.allow_results = QPushButton(text("Autoriser les résultats"))
        actions.addWidget(self.exclude_results)
        actions.addWidget(self.allow_results)
        layout.addLayout(actions)
        footer = QHBoxLayout()
        self.count = QLabel()
        self.count.setObjectName("note")
        footer.addWidget(self.count, 1)
        self.buttons = QDialogButtonBox()
        # Own the Python wrappers explicitly. Fetching auto-created buttons via
        # buttons() can return an unrelated item wrapper after repeated dialogs
        # with this PySide build (observed in the clean-archive validation).
        self.ok_button = QPushButton(QCoreApplication.translate("QPlatformTheme", "OK"), self.buttons)
        self.cancel_button = QPushButton(text("Annuler"), self.buttons)
        self.buttons.addButton(self.ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton(self.cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        footer.addWidget(self.buttons)
        layout.addLayout(footer)
        # Enter in the search field must not silently accept the selection.
        for button in (self.ok_button, self.cancel_button, self.exclude_results, self.allow_results):
            button.setAutoDefault(False)
        self.exclude_results.clicked.connect(lambda: self.set_visible(True))
        self.allow_results.clicked.connect(lambda: self.set_visible(False))
        self.items.itemChanged.connect(self.update_count)
        self.search.textChanged.connect(self.filter_items)
        self.update_count()
        self.search.setFocus()

    def eventFilter(self, watched, event):
        if (watched is self.search and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            return True
        return super().eventFilter(watched, event)

    def value(self):
        return tuple(sorted(item.data(Qt.ItemDataRole.UserRole) for i in range(self.items.count())
                            if (item := self.items.item(i)).checkState() == Qt.CheckState.Checked))

    def filter_items(self, query):
        key = search_key(query.strip())
        visible = 0
        for i in range(self.items.count()):
            item = self.items.item(i)
            item.setHidden(key not in self.search_terms[item.data(Qt.ItemDataRole.UserRole)])
            visible += not item.isHidden()
        self.exclude_results.setEnabled(bool(visible))
        self.allow_results.setEnabled(bool(visible))

    def set_visible(self, excluded):
        self.items.blockSignals(True)
        for i in range(self.items.count()):
            item = self.items.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked if excluded else Qt.CheckState.Unchecked)
        self.items.blockSignals(False)
        self.update_count()

    def update_count(self):
        self.count.setText(self.text("Sélection : {count}", count=len(self.value())))


class ExcludedSelection(QWidget):
    valueChanged = Signal()

    def __init__(self, kind, window):
        super().__init__()
        self.kind, self.window, self._values = kind, window, ()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary, 1)
        self.choose = QPushButton()
        layout.addWidget(self.choose)
        self.setFocusProxy(self.choose)
        self.choose.clicked.connect(self.open_dialog)
        self.retranslate()

    def value(self):
        return self._values

    def setValue(self, values):
        value = tuple(sorted(set(values)))
        if value != self._values:
            self._values = value
            self.retranslate()
            self.valueChanged.emit()

    def retranslate(self):
        self.choose.setText(self.window.text("Choisir…"))
        self.choose.setAccessibleName(self.window.text("Pokémon exclus" if self.kind == "species_set" else "Types d’origine exclus"))
        self.summary.setText(self.window.text("Exclusions : {count}", count=len(self._values)) if self._values
                             else self.window.text("Aucune exclusion"))

    def open_dialog(self):
        dialog = ExclusionDialog(self.kind, self._values, self.window.language, self.window.text, self.window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setValue(dialog.value())
        dialog.deleteLater()
