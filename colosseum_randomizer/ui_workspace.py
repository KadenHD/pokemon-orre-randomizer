"""Native workspace helpers: bounded reading width and deliberate value edits."""
from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollArea, QWidget


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
