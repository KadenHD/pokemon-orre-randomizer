"""Shared Qt layouts for the Colosseum and XD wizards."""
import secrets

from PySide6.QtCore import QEvent, QObject, QPointF, QSize, QTimer, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPlainTextEdit, QProgressBar, QScrollArea, QScrollBar,
    QStackedWidget, QTabBar, QToolButton, QTreeWidget, QVBoxLayout, QWidget,
)

from .ui_icons import category_icon
from .ui_pokemon_names import PreviewNameDelegate
from .ui_theme import MenuPanel


class CreationLog(QObject):
    """The shared, collapsible log of an actual creation, confined to step 3."""
    def __init__(self, layout, window):
        super().__init__(layout.parentWidget())
        self.window = window
        self.started = False
        self.step = 0
        self.messages = []
        self.toggle = QToolButton()
        window.bind(self.toggle.setText, "Détails")
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(200)
        self.view.setMaximumHeight(90)
        layout.addWidget(self.view)
        self.toggle.toggled.connect(self.refresh_visibility)
        self.refresh_visibility()

    def set_step(self, step):
        self.step = step
        self.refresh_visibility()

    def refresh_visibility(self):
        visible = self.started and self.step == 2
        self.toggle.setVisible(visible)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if self.toggle.isChecked() else Qt.ArrowType.RightArrow)
        self.view.setVisible(visible and self.toggle.isChecked())

    def reset(self):
        self.started = False
        self.messages.clear()
        self.view.clear()
        self.toggle.setChecked(False)
        self.refresh_visibility()

    def begin(self):
        self.reset()
        self.started = True
        self.append("Lecture de la ROM d’origine…")
        self.refresh_visibility()

    def append(self, message):
        if self.messages and self.messages[-1] == message:
            return
        self.messages = [*self.messages[-199:], message]
        self.view.appendPlainText(self.window.text(message))

    def retranslate(self):
        self.view.setPlainText("\n".join(self.window.text(message) for message in self.messages))


def bounded(widget, width=1200):
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.addStretch(0)
    widget.setMaximumWidth(width)
    row.addWidget(widget, 1)
    row.addStretch(0)
    return host


def scroll_area(widget):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


def wizard_frame(host, window, go_step, *, xd=False):
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    steps = QHBoxLayout()
    steps.setSpacing(0)
    buttons = []
    for index, label in enumerate(("1. ROM", "2. Réglages", "3. Créer")):
        button = window.button(label)
        button.setObjectName("step")
        button.setCheckable(True)
        button.clicked.connect(lambda checked=False, index=index: go_step(index))
        buttons.append(button)
        steps.addWidget(button, 1)
    layout.addLayout(steps)
    panel = MenuPanel(xd=xd)
    frame = QVBoxLayout(panel)
    frame.setContentsMargins(8, 8, 8, 8)
    pages = QStackedWidget()
    frame.addWidget(pages)
    layout.addWidget(panel, 1)
    return layout, pages, buttons


def wizard_page(pages, *, scrolling=True):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(12)
    host = bounded(page)
    pages.addWidget(scroll_area(host) if scrolling else host)
    return layout


def file_field(layout, window, label, name, placeholder, action, browse):
    field = QLineEdit()
    window.bind(field.setAccessibleName, name)
    window.bind(field.setPlaceholderText, placeholder)
    caption = window.label(label)
    caption.setBuddy(field)
    layout.addWidget(caption)
    button = window.button(action)
    button.clicked.connect(browse)
    row = QHBoxLayout()
    row.addWidget(field, 1)
    row.addWidget(button)
    layout.addLayout(row)
    return field, button


def tab_bar(window, name, accessible_name, labels):
    tabs = QTabBar()
    tabs.setObjectName(name)
    window.bind(tabs.setAccessibleName, accessible_name)
    for label in labels:
        index = tabs.addTab("")
        window.bind(lambda text, index=index: tabs.setTabText(index, text), label)
    return tabs


def settings_workspace(layout, window):
    layout.setSpacing(6)
    tabs = tab_bar(window, "workspaceTabs", "Vues des réglages", ("Configuration", "Aperçu des Pokémon"))
    layout.addWidget(tabs)
    seed_row = QHBoxLayout()
    seed = QLineEdit(secrets.token_hex(8))
    seed.setMaxLength(256)
    seed.setMaximumWidth(520)
    window.bind(seed.setAccessibleName, "Seed")
    label = window.label("&Seed")
    label.setBuddy(seed)
    seed_row.addWidget(label)
    seed_row.addWidget(seed, 1)
    new_seed = window.button("Nouvelle seed")
    new_seed.clicked.connect(lambda: seed.setText(secrets.token_hex(8)))
    seed_row.addWidget(new_seed)
    seed_row.addStretch(1)
    layout.addLayout(seed_row)
    pages = QStackedWidget()
    layout.addWidget(pages, 1)
    return tabs, seed, pages


def configuration_workspace(window, pages, set_mode):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    row = QHBoxLayout()
    title = window.label("Choisissez ce qui change")
    title.setObjectName("subheading")
    row.addWidget(title, 1)
    buttons = []
    for index, message in enumerate(("Simple", "Avancé")):
        button = window.button(message)
        button.setCheckable(True)
        button.clicked.connect(lambda checked=False, index=index: set_mode(index == 1))
        row.addWidget(button)
        buttons.append(button)
    layout.addLayout(row)
    modes = QStackedWidget()
    layout.addWidget(modes, 1)
    pages.addWidget(widget)
    return modes, buttons


def preset_buttons(window, layout, constructors, apply):
    row = QHBoxLayout()
    buttons = []
    labels = (("Pokémon + capacités", "CT et objets aussi"),
              ("Pokémon seuls", "Capacités et CT conservées"),
              ("Copie à l’identique", "Aucune randomisation"))
    for (title, subtitle), constructor in zip(labels, constructors, strict=True):
        button = window.button(title)
        window.bind(button.setAccessibleDescription, subtitle)
        button.setObjectName("preset")
        button.setCheckable(True)
        button.clicked.connect(lambda checked=False, constructor=constructor: apply(constructor()))
        column = QVBoxLayout()
        column.addWidget(button)
        column.addWidget(window.note(subtitle))
        row.addLayout(column, 1)
        buttons.append((button, constructor))
    layout.addLayout(row)
    return buttons


class RuleNavigation(QWidget):
    def __init__(self, window, reset, *, xd=False):
        super().__init__()
        self.window = window
        self.xd = xd
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.selector = QComboBox()
        window.bind(self.selector.setAccessibleName, "Catégorie de réglages")
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.selector.setMaximumWidth(245)
        row.addWidget(self.selector)
        self.search = search_field(window, "Rechercher un réglage…")
        self.search.setMaxLength(160)
        row.addWidget(self.search, 1)
        self.reset = window.button("Valeurs conseillées")
        self.reset.clicked.connect(reset)
        row.addWidget(self.reset)
        layout.addLayout(row)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.hide()
        layout.addWidget(self.notice)
        self.content = QStackedWidget()
        self.form = QWidget()
        columns = QHBoxLayout(self.form)
        columns.setContentsMargins(0, 0, 0, 0)
        self.categories = QListWidget()
        self.categories.setObjectName("ruleNavigation")
        self.categories.setIconSize(QSize(20, 20))
        self.categories.setFixedWidth(192)
        self.categories.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.categories.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        window.bind(self.categories.setAccessibleName, "Catégories de réglages")
        self.pages = QStackedWidget()
        columns.addWidget(self.categories)
        columns.addWidget(self.pages, 1)
        self.content.addWidget(self.form)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        window.bind(self.results.setAccessibleName, "Résultats des réglages")
        self.content.addWidget(self.results)
        layout.addWidget(self.content, 1)
        self.selector.currentIndexChanged.connect(self.categories.setCurrentRow)
        self.categories.currentRowChanged.connect(self.selector.setCurrentIndex)
        self.categories.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.search.installEventFilter(self)
        self.results.installEventFilter(self)
        self.setTabOrder(self.selector, self.search)
        self.setTabOrder(self.search, self.reset)

    def add_category(self, group, page):
        self.pages.addWidget(page)
        icon = category_icon(group, xd=self.xd)
        item = QListWidgetItem(icon, group)
        self.categories.addItem(item)
        self.window.bind(item.setText, group)
        index = self.selector.count()
        self.selector.addItem(icon, "")
        self.window.bind(lambda text, index=index: self.selector.setItemText(index, text), group)

    def fit(self):
        needed = sum(max(28, self.categories.sizeHintForRow(i)) for i in range(self.categories.count())) + 8
        compact = self.window.width() < 900 or self.form.height() - 8 < needed
        self.categories.setVisible(not compact)
        self.selector.setVisible(compact and not self.search.text().strip())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self, self.fit)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self, self.fit)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            if watched is self.search and event.key() == Qt.Key.Key_Down and self.results.count():
                self.results.setFocus(Qt.FocusReason.OtherFocusReason)
                self.results.setCurrentRow(0)
                return True
            if watched in (self.search, self.results) and event.key() == Qt.Key.Key_Escape:
                self.search.clear()
                self.search.setFocus(Qt.FocusReason.OtherFocusReason)
                return True
        return super().eventFilter(watched, event)

    def show_results(self, matches, *, busy=False):
        query = self.search.text().strip()
        self.results.clear()
        self.content.setCurrentIndex(int(bool(query)))
        self.reset.setEnabled(not query and not busy)
        self.notice.setVisible(bool(query and not matches))
        if query:
            self.notice.setText(self.window.text("Résultats : {count}", count=len(matches)) if matches
                                else self.window.text("Aucun réglage trouvé. Essayez un autre mot."))
            self.results.setAccessibleDescription(self.notice.text())
        items = []
        for row in matches:
            item = QListWidgetItem(row["label"] + "\n" + row["group"])
            item.setData(Qt.ItemDataRole.UserRole, row["name"])
            item.setToolTip(row["description"])
            item.setSizeHint(QSize(0, 60))
            self.results.addItem(item)
            items.append(item)
        if matches:
            self.results.setCurrentRow(0)
        self.fit()
        return items


def search_field(window, message):
    search = QLineEdit()
    search.setClearButtonEnabled(True)
    window.bind(search.setPlaceholderText, message)
    window.bind(search.setAccessibleName, message)
    return search


def preview_toolbar(layout, window, labels, start, stop):
    toolbar = QHBoxLayout()
    tabs = tab_bar(window, "previewTabs", "Groupes de Pokémon", labels)
    tabs.setUsesScrollButtons(False)
    tabs.setElideMode(Qt.TextElideMode.ElideRight)
    toolbar.addWidget(tabs, 1)
    start_button = window.button("Calculer l’aperçu")
    start_button.clicked.connect(start)
    toolbar.addWidget(start_button)
    cancel = window.button("Annuler l’aperçu")
    cancel.setProperty("menuSound", "back")
    cancel.clicked.connect(stop)
    cancel.hide()
    toolbar.addWidget(cancel)
    status = QLabel()
    status.setObjectName("previewStatus")
    status.setTextFormat(Qt.TextFormat.PlainText)
    toolbar.addWidget(status)
    layout.addLayout(toolbar)
    progress = QProgressBar()
    progress.setRange(0, 0)
    progress.setObjectName("previewProgress")
    progress.setTextVisible(False)
    progress.setFixedHeight(6)
    progress.hide()
    layout.addWidget(progress)
    return tabs, start_button, cancel, status, progress


def starter_slot(window, label, open_details):
    slot = QVBoxLayout()
    identity = QHBoxLayout()
    portrait = QLabel()
    portrait.setFixedSize(48, 48)
    portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
    portrait.setObjectName("previewPortrait")
    identity.addWidget(portrait)
    description = QVBoxLayout()
    description.setSpacing(2)
    description.addWidget(window.note(label))
    name = QLabel()
    name.setObjectName("subheading")
    name.setWordWrap(True)
    name.setTextFormat(Qt.TextFormat.PlainText)
    description.addWidget(name)
    identity.addLayout(description, 1)
    slot.addLayout(identity)
    details = window.button("Fiche du Pokémon")
    window.bind(details.setToolTip, "Consultez ses statistiques, ses capacités et ses évolutions.")
    details.hide()
    details.clicked.connect(open_details)
    slot.addWidget(details, 0, Qt.AlignmentFlag.AlignLeft)
    return slot, portrait, name, details


class EncounterTable(QTreeWidget):
    def __init__(self, window, accessible_name):
        super().__init__()
        # Keep Python ownership of the wrappers across deferred window destruction.
        self.scrollbar = QScrollBar(Qt.Orientation.Vertical, self)
        self.setVerticalScrollBar(self.scrollbar)
        self.setObjectName("encountersPreview")
        self.setColumnCount(2)
        self.name_delegate = PreviewNameDelegate(self)
        self.setItemDelegateForColumn(1, self.name_delegate)
        self.setIconSize(QSize(42, 42))
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        window.bind(self.setAccessibleName, accessible_name)
        window.bind(self.setAccessibleDescription,
                    "Cliquez sur une ligne ou appuyez sur Entrée pour ouvrir la fiche du Pokémon obtenu.")

    def visible_count(self, text):
        items = [item for i in range(self.topLevelItemCount())
                 if not (item := self.topLevelItem(i)).isHidden()]
        if not items:
            return text("Aucun résultat")
        visible = [i for i, item in enumerate(items, 1)
                   if self.visualItemRect(item).intersects(self.viewport().rect())]
        if not visible:
            return text("{count} résultats", count=len(items))
        return text("{first}–{last} sur {count}", first=visible[0], last=visible[-1], count=len(items))


class DeliberateWheel(QObject):
    """Route wheels over unfocused value controls to the enclosing scroll area."""
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel and not watched.hasFocus():
            parent = watched.parentWidget()
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    viewport = parent.viewport()
                    forwarded = QWheelEvent(QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint())),
                        event.globalPosition(), event.pixelDelta(), event.angleDelta(), event.buttons(),
                        event.modifiers(), event.phase(), event.inverted())
                    QApplication.sendEvent(viewport, forwarded)
                    event.accept()
                    return True
                parent = parent.parentWidget()
            event.ignore()
            return True
        return super().eventFilter(watched, event)
