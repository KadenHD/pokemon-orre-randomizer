"""Shared visible choices and proportionally rendered controller artwork."""
from pathlib import Path
from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget


class VisibleChoices(QWidget):
    """Keep the existing combo model/API, expose its choices as native buttons."""
    def __init__(self, combo):
        super().__init__()
        self.combo = combo
        combo.setParent(self)
        combo.hide()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.buttons = []
        for index in range(combo.count()):
            button = QPushButton()
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(button, index)
            layout.addWidget(button, 1)
            self.buttons.append(button)
        self.group.idClicked.connect(combo.setCurrentIndex)
        combo.currentIndexChanged.connect(self.refresh)
        combo.model().dataChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        for index, button in enumerate(self.buttons):
            button.setText(self.combo.itemText(index))
            button.setAccessibleName(self.combo.itemText(index))
            button.setChecked(index == self.combo.currentIndex())


def separator(vertical=False):
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine if vertical else QFrame.Shape.HLine)
    line.setObjectName("sectionDivider")
    line.setFixedWidth(1) if vertical else line.setFixedHeight(1)
    return line


def navigation_icon(kind, *, xd=False):
    """The approved comp's gold play triangle and light outline file/folder marks."""
    # A wider transparent icon box keeps the folder mark clear of its label.
    pixmap = QPixmap(80 if kind == 'folder' else 64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    ink = QColor('#fff4e6' if xd else '#f2f6f1')
    if kind == 'play':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#ffc772' if xd else '#efd574'))
        painter.drawPolygon(QPolygonF([QPointF(9, 4), QPointF(27, 16), QPointF(9, 28)]))
    else:
        painter.setPen(QPen(ink, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor('#efc66b') if kind == 'folder-fill' else Qt.BrushStyle.NoBrush)
        shape = QPainterPath()
        if kind.startswith('folder'):
            shape.moveTo(3, 26); shape.lineTo(3, 7); shape.lineTo(13, 7)
            shape.lineTo(17, 11); shape.lineTo(29, 11); shape.lineTo(29, 26); shape.closeSubpath()
        else:
            shape.moveTo(8, 3); shape.lineTo(21, 3); shape.lineTo(27, 9)
            shape.lineTo(27, 29); shape.lineTo(8, 29); shape.closeSubpath()
            shape.moveTo(21, 3); shape.lineTo(21, 9); shape.lineTo(27, 9)
        painter.drawPath(shape)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class ControllerDiagram(QWidget):
    """Reference photograph, never stretched or cropped. See controller.json."""
    def sizeHint(self):
        return QSize(183, 142)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(145, 86)
        self.setMaximumHeight(142)
        self.setAccessibleName("GameCube")
        self.artwork = QPixmap(str(Path(__file__).parent / "assets/app/controller.png"))

    def paintEvent(self, _):
        painter = QPainter(self)
        artwork = self.artwork.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((self.width()-artwork.width())//2, (self.height()-artwork.height())//2, artwork)
