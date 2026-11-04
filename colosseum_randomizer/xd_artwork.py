"""Original XD badge for the game selector and workspace header."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def xd_emblem() -> QPixmap:
    """Render a chrome XD monogram without requiring an external image or font."""
    badge = QPixmap(192, 64)
    badge.setDevicePixelRatio(2)
    badge.fill(Qt.GlobalColor.transparent)

    frame = QPainterPath()
    frame.moveTo(12, 1)
    frame.lineTo(86, 1)
    frame.lineTo(95, 10)
    frame.lineTo(85, 31)
    frame.lineTo(10, 31)
    frame.lineTo(1, 22)
    frame.closeSubpath()

    monogram = QPainterPath()
    monogram.moveTo(25, 6)
    monogram.lineTo(35, 6)
    monogram.lineTo(41, 12)
    monogram.lineTo(48, 6)
    monogram.lineTo(59, 6)
    monogram.lineTo(46, 16)
    monogram.lineTo(54, 26)
    monogram.lineTo(44, 26)
    monogram.lineTo(39, 20)
    monogram.lineTo(31, 26)
    monogram.lineTo(20, 26)
    monogram.lineTo(33, 16)
    monogram.closeSubpath()
    monogram.moveTo(62, 6)
    monogram.lineTo(72, 6)
    monogram.cubicTo(91, 6, 86, 26, 68, 26)
    monogram.lineTo(55, 26)
    monogram.closeSubpath()
    monogram.moveTo(68, 12)
    monogram.lineTo(65, 20)
    monogram.lineTo(70, 20)
    monogram.cubicTo(77, 20, 79, 12, 72, 12)
    monogram.closeSubpath()

    chrome = QLinearGradient(0, 6, 0, 26)
    chrome.setColorAt(0, QColor("#fff6de"))
    chrome.setColorAt(0.48, QColor("#f2d3a7"))
    chrome.setColorAt(0.52, QColor("#c49c75"))
    chrome.setColorAt(1, QColor("#fff6de"))

    painter = QPainter(badge)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#c6a88a"), 1))
    painter.setBrush(QColor("#422020"))
    painter.drawPath(frame)
    painter.setPen(QPen(QColor("#e28764"), 1))
    painter.drawLine(QPointF(13, 5), QPointF(21, 5))
    painter.drawLine(QPointF(75, 27), QPointF(83, 27))
    painter.fillPath(monogram, chrome)
    painter.end()
    return badge
