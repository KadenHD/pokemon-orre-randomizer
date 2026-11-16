"""Final Qt portrait shapes, including loading and missing-artwork states."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap


def unknown_portrait(background, foreground, *, circular=False):
    pixmap = QPixmap(42, 42)
    pixmap.fill(Qt.GlobalColor.transparent if circular else QColor(background))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if circular:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawEllipse(QRectF(.5, .5, 41, 41))
    painter.setPen(QColor(foreground))
    painter.setFont(QFont('Segoe UI', 16, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, '?')
    painter.end()
    return QIcon(pixmap)


def circular_portrait(source):
    """Contain every XD state in the same 42px circle, regardless of its source."""
    pixmap = QPixmap(42, 42)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, 42, 42))
    painter.setClipPath(path)
    image = source.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    painter.drawPixmap((42-image.width())//2, (42-image.height())//2, image)
    painter.end()
    return pixmap
