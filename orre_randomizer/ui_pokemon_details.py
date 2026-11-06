"""Pokémon summary screen for the final encounter from the preview."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from .detail_texts import detail_text
from .i18n import translate
from .pokemon_details import STAT_NAMES, detail_sections, display_name
from .resources import type_badge
from .ui_pokemon_names import shiny_name_html
from .ui_theme import GameSurface, MenuPanel
from .ui_workspace import scroll_area


TYPE_BADGE_SIZES = {"colosseum": QSize(64, 22), "xd": QSize(88, 22)}


def text_label(text, role=None):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if role:
        label.setObjectName(role)
    return label


def type_label(game, language, type_id, name):
    label = text_label(name, "sheetType")
    label.setWordWrap(False)
    label.setAccessibleName(name)
    label.setToolTip(name)
    path = type_badge(game, language, type_id) if type_id is not None else None
    if path is not None:
        image = QPixmap(str(path))
        if not image.isNull():
            label.setPixmap(image.scaled(TYPE_BADGE_SIZES[game], Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
    return label


def move_type_label(game, language, move):
    # Shadow moves use a separate classification from their stored type byte (0).
    last_shadow_move = 373 if game == "xd" else 356
    if 356 <= move["move"] <= last_shadow_move:
        return type_label(game, language, None, detail_text("shadow_type", language))
    type_names = move.get("type_names")
    if type_names:
        return type_label(game, language, move.get("type"), " / ".join(type_names[language]))
    return None


def evolution_form(name, icon):
    form = QVBoxLayout()
    form.setSpacing(4)
    portrait = QLabel()
    portrait.setObjectName("sheetEvolutionPortrait")
    portrait.setFixedSize(48, 48)
    portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
    portrait.setPixmap(icon.pixmap(42, 42))
    form.addWidget(portrait, alignment=Qt.AlignmentFlag.AlignHCenter)
    title = text_label(name.capitalize())
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    form.addWidget(title)
    return form


class PokemonSheet(QDialog):
    def __init__(self, parent, row, name, icon, language, *, xd=False):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(detail_text("details", language))
        self.resize(660, 530)
        self.setMinimumSize(460, 360)
        details = row["details"]
        game = "xd" if xd else "colosseum"
        tr = lambda key, **values: detail_text(key, language, **values)
        surface = GameSurface()
        if xd:
            surface.set_xd(True)
        else:
            surface.set_background(parent.artwork.get("background"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(surface)
        frame = QVBoxLayout(surface)
        frame.setContentsMargins(12, 12, 12, 12)
        panel = MenuPanel(xd=xd)
        frame.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 15, 18, 14)
        layout.setSpacing(10)

        hero = QHBoxLayout()
        hero.setSpacing(14)
        portrait = QLabel()
        portrait.setObjectName("sheetPortrait")
        portrait.setFixedSize(74, 74)
        portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        portrait.setPixmap(icon.pixmap(42, 42).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio))
        hero.addWidget(portrait)
        identity = QVBoxLayout()
        identity.setSpacing(3)
        name = name.capitalize()
        title = text_label(name, "section")
        if row.get("shiny"):
            title.setTextFormat(Qt.TextFormat.RichText)
            title.setText(shiny_name_html(name, 17))
            title.setAccessibleName(translate("{name} chromatique", language).format(name=name))
        identity.addWidget(title)
        level = details.get("level")
        metadata = [f"#{details['national_dex']:03d}"]
        if level is not None:
            metadata.append(tr("level", level=level))
        identity.addWidget(text_label(" · ".join(metadata), "note"))
        types = QHBoxLayout()
        types.setSpacing(5)
        type_ids = details.get("types", ())
        for index, type_name in enumerate(details["type_names"][language]):
            type_id = type_ids[index] if index < len(type_ids) else None
            types.addWidget(type_label(game, language, type_id, type_name))
        types.addStretch(1)
        identity.addLayout(types)
        hero.addLayout(identity, 1)
        layout.addLayout(hero)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("sheetTabs")
        self.tabs.setUsesScrollButtons(False)
        layout.addWidget(self.tabs, 1)
        summary = self.add_tab(translate("Résumé", language))
        summary.addWidget(text_label(tr("abilities"), "sheetHeading"))
        summary.addWidget(text_label(" / ".join(details["ability_names"][language])))
        summary.addWidget(text_label(tr("ability_note"), "note"))
        summary.addWidget(text_label(tr("stats"), "sheetHeading"))
        stats = QGridLayout()
        stats.setHorizontalSpacing(12)
        stats.setVerticalSpacing(5)
        stats.setColumnStretch(1, 1)
        for index, key in enumerate(STAT_NAMES):
            title, value = tr(key), details["base_stats"][key]
            stats.addWidget(text_label(title), index, 0)
            meter = QProgressBar()
            meter.setObjectName("sheetStat")
            meter.setRange(0, 255)
            meter.setValue(value)
            meter.setTextVisible(False)
            meter.setAccessibleName(title)
            stats.addWidget(meter, index, 1)
            stats.addWidget(text_label(str(value)), index, 2, Qt.AlignmentFlag.AlignRight)
        summary.addLayout(stats)
        summary.addStretch(1)

        sections = detail_sections(details, language, include_move_types=False)
        moves = self.add_tab(tr("moves"))
        for key in ("moves", "learnset", "tms"):
            if key not in sections:
                continue
            moves.addWidget(text_label(tr(key), "sheetHeading"))
            if not details[key]:
                moves.addWidget(text_label(tr("none")))
                continue
            for description, entry in zip(sections[key], details[key], strict=True):
                move = entry.get("details", entry)
                badge = move_type_label(game, language, move)
                if badge is None:
                    moves.addWidget(text_label(description))
                    continue
                move_row = QHBoxLayout()
                move_row.setSpacing(8)
                badge.setMinimumSize(TYPE_BADGE_SIZES[game])
                move_row.addWidget(badge)
                move_row.addWidget(text_label(description), 1)
                moves.addLayout(move_row)
        moves.addStretch(1)
        evolutions = self.add_tab(tr("evolutions"))
        if details.get("shadow"):
            evolutions.addWidget(text_label(tr("shadow_first"), "note"))
        chain = details["evolution_chain"]
        if not chain:
            evolutions.addWidget(text_label(tr("no_evolution"), "sheetEntry"))
        portraits = row.get("evolution_portraits", {})
        for branch in chain:
            entry = QWidget()
            entry.setObjectName("sheetEvolution")
            grid = QGridLayout(entry)
            grid.setContentsMargins(12, 9, 12, 9)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(2, 1)
            source = parent.preview_portrait({"portrait_png": portraits.get(str(branch["source_species"]))}, xd=xd)
            target = parent.preview_portrait({"portrait_png": portraits.get(str(branch["target_species"]))}, xd=xd)
            grid.addLayout(evolution_form(branch["source_names"][language], source), 0, 0)
            arrow = text_label("→", "sheetEvolutionArrow")
            grid.addWidget(arrow, 0, 1, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            grid.addLayout(evolution_form(display_name(branch, language), target), 0, 2)
            condition = text_label(branch["texts"][language], "note")
            condition.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(condition, 1, 0, 1, 3)
            evolutions.addWidget(entry)
        evolutions.addStretch(1)

        close = QPushButton(translate("Fermer", language))
        close.setObjectName("primary")
        close.clicked.connect(self.close)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

    def add_tab(self, title):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.tabs.addTab(scroll_area(content), title)
        return layout
