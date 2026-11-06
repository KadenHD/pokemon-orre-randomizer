"""Code-owned Colosseum menu frames. Game pictures come from the exported local interface pack."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QCheckBox, QFrame, QStyle, QStyleOptionButton, QWidget


class MenuCheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            option = QStyleOptionButton()
            self.initStyleOption(option)
            box = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#082b24" if self.isEnabled() else "#c1d8cf"), 2.2))
            painter.drawPolyline(QPolygonF([QPointF(box.x()+4, box.y()+9),
                                            QPointF(box.x()+8, box.y()+13),
                                            QPointF(box.x()+15, box.y()+5)]))


class GameSurface(QWidget):
    def __init__(self):
        super().__init__()
        self.background = QPixmap()
        self.xd = False
        self.home = False

    def set_xd(self, enabled):
        self.xd = enabled
        self.update()

    def set_home(self, enabled):
        self.home = enabled
        self.update()

    def set_background(self, path):
        self.background = QPixmap(str(path)) if path else QPixmap()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.home:
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, QColor("#090a0b"))
            gradient.setColorAt(0.5, QColor("#191a1c"))
            gradient.setColorAt(1, QColor("#34363a"))
            painter.fillRect(self.rect(), gradient)
            return
        if self.xd:
            painter.fillRect(self.rect(), QColor("#1d1112"))
            painter.setPen(Qt.PenStyle.NoPen)
            for edge, color in ((0.62, "#2d191a"), (0.80, "#3b2021")):
                x, y = self.width(), self.height()
                painter.setBrush(QColor(color))
                painter.drawPolygon(QPolygonF([QPointF(x * edge, 0), QPointF(x, 0),
                                               QPointF(x, y), QPointF(x * (edge - 0.24), y)]))
            return
        painter.fillRect(self.rect(), QColor("#181b3b"))
        if not self.background.isNull():
            image = self.background.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                           Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width()-image.width())//2, (self.height()-image.height())//2, image)
            painter.fillRect(self.rect(), QColor(10, 15, 31, 115))


class MenuPanel(QFrame):
    """Silver clipped corners, with Qt children remaining fully accessible."""

    def __init__(self, *, xd=False):
        super().__init__()
        self.xd = xd

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border, trim, fill = ("#c5b6a9", "#6c4945", "#24191a") if self.xd else (
            "#b6ccc4", "#54726c", "#082b24")
        for inset, color, width in ((1, border, 2), (5, trim, 1)):
            box = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
            x, y, r, b = box.left(), box.top(), box.right(), box.bottom()
            cut = 11 if inset == 1 else 8
            polygon = QPolygonF([QPointF(x+cut, y), QPointF(r-cut, y), QPointF(r, y+cut),
                                 QPointF(r, b-cut), QPointF(r-cut, b), QPointF(x+cut, b),
                                 QPointF(x, b-cut), QPointF(x, y+cut)])
            painter.setPen(QPen(QColor(color), width))
            painter.setBrush(QColor(fill) if inset == 1 else Qt.BrushStyle.NoBrush)
            painter.drawPolygon(polygon)


JAPANESE_FONT_STYLE = """
QWidget { font-family: "Yu Gothic UI", "Meiryo", "Noto Sans CJK JP", "Noto Sans JP", sans-serif; }
QLabel#title { font-family: "Segoe UI", sans-serif; }
"""

STYLE = """
QMainWindow { background: #181b3b; }
QWidget { color: #f2f6f1; font-size: 14px; }
QLabel { background: transparent; }
QLabel#title { font-size: 27px; font-weight: 700; color: #e4eee8; }
QLabel#section { font-size: 23px; font-weight: 650; }
QLabel#note { color: #c1d8cf; font-size: 13px; }
QLabel#previewCount { color: #c1d8cf; font-size: 13px; }
QLabel#subheading { color: #dce8e1; font-size: 16px; font-weight: 600; }
QLabel#previewStatus { color: #8be8e7; font-size: 14px; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background: #0b1c20; color: #f2f6f1; border: 1px solid #829e98;
    border-radius: 4px; padding: 5px 8px; min-height: 24px; selection-background-color: #17666b;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 2px solid #71e2e6; padding: 4px 7px; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #9dafa9; border-color: #40534f; }
QComboBox QAbstractItemView { background: #0c3029; color: #f2f6f1; selection-background-color: #17666b; }
QPushButton, QToolButton {
    background: #172c33; color: #f2f6f1; border: 1px solid #9eafa9;
    border-radius: 4px; min-height: 28px; padding: 4px 12px;
}
QPushButton:hover, QToolButton:hover { background: #24483f; border-color: #bce9de; }
QPushButton:pressed, QToolButton:pressed { background: #0a3935; }
QPushButton:checked, QToolButton:checked { background: #125359; border: 2px solid #71e2e6; padding: 3px 11px; }
QPushButton:focus, QToolButton:focus { border: 2px solid #71e2e6; padding: 3px 11px; }
QToolButton#headerControl { padding-left: 8px; padding-right: 8px; }
QToolButton#profileMenu { padding-left: 8px; padding-right: 9px; }
QToolButton#profileMenu::menu-indicator {
    subcontrol-origin: padding; subcontrol-position: center right; right: 5px; width: 8px; height: 7px;
}
QPushButton:disabled, QToolButton:disabled { color: #9dafa9; background: #1b292c; border-color: #40534f; }
QLineEdit > QToolButton, QLineEdit > QToolButton:hover, QLineEdit > QToolButton:pressed {
    background: transparent; border: 0; padding: 0; min-height: 0;
}
QPushButton#primary { border: 2px solid #efd574; background: #173e38; font-weight: 600; padding: 3px 17px; }
QPushButton#primary:hover { background: #245d4f; }
QPushButton#primary:focus { border-color: #71e2e6; }
QPushButton#primary:disabled { color: #9dafa9; border-color: #53615a; background: #1b292c; }
QPushButton#step, QPushButton#preset { qproperty-iconSize: 20px 20px; }
QPushButton#step { border-radius: 0; min-height: 30px; }
QPushButton#preset { text-align: left; min-height: 48px; }
QPushButton#preset:checked { background: #125359; }
QCheckBox { spacing: 9px; padding: 6px 0; }
QCheckBox:disabled { color: #9dafa9; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #a3bdb1; border-radius: 2px; background: #0b1c20; }
QCheckBox::indicator:checked { background: #60d4d9; border: 2px solid #d6faf1; }
QCheckBox::indicator:disabled { border-color: #50665b; background: #40564d; }
QCheckBox:focus { outline: none; color: #8be8e7; }
QListWidget { background: #09271f; border: 0; border-right: 1px solid #69877a; outline: 0; padding-right: 8px; }
QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #294f41; }
QListWidget::item:selected { background: #125359; color: #ffffff; border: 1px solid #71e2e6; }
QListWidget::item:hover { background: #173f32; }
QTreeWidget#encountersPreview { background: #09271f; border: 1px solid #69877a; }
QTreeWidget#encountersPreview::item { padding: 4px; }
QTreeWidget#encountersPreview::item:hover { background: #173f32; }
QTreeWidget#encountersPreview::item:selected { background: #125359; color: #ffffff; }
QTreeWidget#encountersPreview QHeaderView::section { background: #172c33; color: #f2f6f1; border: 0; padding: 7px; }
QScrollArea, QStackedWidget, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #0b1c20; border: 1px solid #829e98; border-radius: 3px; min-height: 16px; text-align: center; }
QProgressBar::chunk { background: #287b71; }
QProgressBar#previewProgress { min-height: 6px; max-height: 6px; border: 0; background: #173f32; }
QProgressBar#previewProgress::chunk { background: #60d4d9; }
QLabel#previewPortrait, QLabel#sheetPortrait, QLabel#sheetEvolutionPortrait { background: #172c33; border: 1px solid #69877a; }
QLabel#sheetType { color: #a8f0ed; font-weight: 600; }
QLabel#sheetHeading { background: #172c33; color: #e4eee8; padding: 4px 7px; font-weight: 600; }
QLabel#sheetEntry { background: #102e26; padding: 8px; }
QWidget#sheetEvolution { background: #102e26; border: 1px solid #36584f; }
QLabel#sheetEvolutionArrow { color: #8be8e7; font-size: 26px; min-height: 48px; }
QTabWidget#sheetTabs::pane { border: 1px solid #69877a; background: #09271f; }
QProgressBar#sheetStat { min-height: 8px; max-height: 8px; border: 1px solid #54726c; }
QProgressBar#sheetStat::chunk { background: #60d4d9; }
QToolTip { background: #0b2520; color: #f2f6f1; border: 1px solid #a3bdb1; padding: 8px; }
QListWidget#ruleNavigation::item { padding: 4px 6px; }
QTabBar::tab { background: #172c33; color: #f2f6f1; padding: 6px 13px; border: 1px solid #69877a; }
QTabBar#previewTabs::tab { padding: 6px 8px; }
QTabBar::tab:selected { background: #125359; border-bottom: 2px solid #71e2e6; }
QTabBar::tab:hover { background: #24483f; }
QTabBar:focus { border: 1px solid #71e2e6; }
QMenu { background: #172c33; color: #f2f6f1; border: 1px solid #69877a; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background: #125359; }
QScrollBar:vertical { background: #102e26; width: 15px; margin: 0; }
QScrollBar::handle:vertical { background: #a3bdb1; border: 1px solid #69877a; border-radius: 3px; min-height: 44px; }
"""


def xd_stylesheet():
    """Apply XD's charcoal, red and gold palette to the shared Qt controls."""
    style = STYLE
    for original, replacement in {
        "#181b3b": "#1d1112", "#f2f6f1": "#fff4e6", "#e4eee8": "#fff4e6",
        "#dce8e1": "#f7e5d6", "#c1d8cf": "#e2c9bb", "#8be8e7": "#ffb384",
        "#0b1c20": "#181314", "#829e98": "#a1837a", "#17666b": "#793d32",
        "#71e2e6": "#ffad93", "#0c3029": "#382326", "#172c33": "#382527",
        "#9eafa9": "#9d817a", "#24483f": "#593d3d", "#bce9de": "#f4cbb3",
        "#0a3935": "#542e2d", "#125359": "#66302a", "#9dafa9": "#c4a79d",
        "#1b292c": "#332323", "#40534f": "#765653", "#efd574": "#ffc772",
        "#173e38": "#502f2e", "#245d4f": "#764139", "#a3bdb1": "#ba9c90",
        "#60d4d9": "#ffad93", "#d6faf1": "#ffe5d6", "#50665b": "#836460",
        "#40564d": "#654641", "#287b71": "#a45145", "#0b2520": "#352223",
        "#102e26": "#352223", "#69877a": "#a3847c",
        "#09271f": "#261b1c", "#173f32": "#583635",
        "#a8f0ed": "#ffcfad", "#36584f": "#694743", "#54726c": "#795854",
        "#294f41": "#654641",
    }.items():
        style = style.replace(original, replacement)
    return style


XD_STYLE = xd_stylesheet()

HOME_STYLE = STYLE + """
QPushButton#authorLink {
    background: transparent; color: #cdd7e6; border: 1px solid transparent;
    font-size: 13px; text-decoration: underline; min-height: 20px; padding: 2px 8px;
}
QPushButton#authorLink:hover { color: #ffffff; }
QPushButton#authorLink:focus { border-color: #cbd0d8; }
QToolButton#headerControl {
    background: #202327; color: #e5e7eb; border: 1px solid #727782;
}
QToolButton#headerControl:checked {
    background: #30343a; color: #f2f3f5; border: 2px solid #cbd0d8;
}
QToolButton#headerControl:hover {
    background: #30343a; border-color: #cbd0d8;
}
QToolButton#headerControl:focus { border: 2px solid #cbd0d8; }
QToolButton#headerControl:pressed { background: #17191c; }
QToolButton#headerControl:disabled {
    background: #202327; color: #969ba5; border-color: #626772;
}
QComboBox#languageSelector {
    background: #191b1e; color: #eceef2; border-color: #727782;
    selection-background-color: #30343a;
}
QComboBox#languageSelector:focus, QComboBox#languageSelector:hover {
    border-color: #cbd0d8;
}
QComboBox#languageSelector QAbstractItemView {
    background: #202327; color: #eceef2; border: 1px solid #727782;
    selection-background-color: #30343a; selection-color: #f2f3f5;
}
"""
