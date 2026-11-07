"""Shared name decoration for Pokémon sheets and previews."""
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QAbstractTextDocumentLayout, QPalette, QTextDocument
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

RICH_NAME_ROLE = Qt.ItemDataRole.UserRole + 3


def shiny_name_html(name, star_size):
    return escape(name) + f'&nbsp;<sup style="color:#ff777f; font-size:{star_size}px;">★</sup>'


class PreviewNameDelegate(QStyledItemDelegate):
    """Draw a rich name inside the native text area, beside its portrait."""

    def paint(self, painter, option, index):
        markup = index.data(RICH_NAME_ROLE)
        if not markup:
            super().paint(painter, option, index)
            return

        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        widget = item.widget
        style = widget.style() if widget else QApplication.style()
        text_area = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, item, widget)
        # Match the inset Qt uses when painting plain item text beside a portrait.
        text_margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, item, widget) + 1
        text_area.adjust(text_margin, 0, -text_margin, 0)
        item.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item, painter, widget)
        if text_area.isEmpty():
            return

        document = QTextDocument()
        document.setDefaultFont(item.font)
        document.setDocumentMargin(0)
        document.setHtml(markup)
        document.setTextWidth(text_area.width())
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette = item.palette
        if item.state & QStyle.StateFlag.State_Selected:
            context.palette.setColor(QPalette.ColorRole.Text, item.palette.color(QPalette.ColorRole.HighlightedText))
        top = text_area.y()
        if not item.displayAlignment & Qt.AlignmentFlag.AlignTop:
            top += max(0.0, (text_area.height() - document.size().height()) / 2)
        painter.save()
        painter.setClipRect(text_area, Qt.ClipOperation.IntersectClip)
        painter.translate(text_area.x(), top)
        document.documentLayout().draw(painter, context)
        painter.restore()
