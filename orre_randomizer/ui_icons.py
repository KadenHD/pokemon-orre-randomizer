"""Semantic setting icons, drawn by the app in one consistent outline style."""
from functools import lru_cache
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


CATEGORY_SYMBOLS = {
    "Dresseurs": "trainers",
    "Starters et cadeaux": "gift",
    "Poké Places": "pin",
    "Capacités": "bolt",
    "CT": "disc",
    "Boss": "crown",
    "Pokémon autorisés": "filter",
    "Talents": "spark",
    "Statistiques": "bars",
    "Types": "tag",
    "Objets tenus": "hand",
    "Objets trouvés": "chest",
    "Niveaux et capture": "capture",
    "Évolutions": "branches",
    "Boutiques": "shop",
    "Chromatiques": "shiny",
}


def _draw(painter: QPainter, symbol: str):
    """Shapes use a shared 24-unit canvas; no fonts, sprites or external files."""
    def line(x1, y1, x2, y2):
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def outline(points, *, closed=False):
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        if closed:
            path.closeSubpath()
        painter.drawPath(path)

    def rect(x, y, width, height, radius=0):
        painter.drawRoundedRect(QRectF(x, y, width, height), radius, radius)

    def circle(x, y, radius):
        painter.drawEllipse(QRectF(x-radius, y-radius, radius*2, radius*2))

    if symbol == "trainers":
        circle(9, 6, 3)
        path = QPainterPath(QPointF(3, 21))
        path.lineTo(3, 17)
        path.cubicTo(3, 10, 15, 10, 15, 17)
        path.lineTo(15, 21)
        painter.drawPath(path)
        circle(18, 8, 2.5)
        path = QPainterPath(QPointF(18, 13))
        path.cubicTo(21, 13, 22, 15, 22, 18)
        path.lineTo(22, 21)
        painter.drawPath(path)
    elif symbol == "gift":
        rect(4, 10, 16, 11, 1)
        rect(3, 7, 18, 4, 1)
        line(12, 7, 12, 21)
        path = QPainterPath(QPointF(12, 7))
        path.cubicTo(2, 7, 6, -1, 12, 7)
        path.cubicTo(18, -1, 22, 7, 12, 7)
        painter.drawPath(path)
    elif symbol == "pin":
        path = QPainterPath(QPointF(12, 22))
        path.cubicTo(10, 19, 5, 14, 5, 9)
        path.cubicTo(5, 0, 19, 0, 19, 9)
        path.cubicTo(19, 14, 14, 19, 12, 22)
        painter.drawPath(path)
        circle(12, 9, 2.5)
    elif symbol == "bolt":
        outline([(13, 2), (5, 13), (11, 13), (10, 22), (20, 9), (13, 9)], closed=True)
    elif symbol == "disc":
        circle(12, 12, 9)
        circle(12, 12, 2.5)
        line(15.5, 5.5, 18.5, 8.5)
        line(5.5, 15.5, 8.5, 18.5)
    elif symbol == "crown":
        outline([(3, 7), (8, 12), (12, 4), (16, 12), (21, 7), (19, 19), (5, 19)], closed=True)
        line(6, 22, 18, 22)
    elif symbol == "filter":
        outline([(3, 4), (21, 4), (14, 12), (14, 21), (10, 18), (10, 12)], closed=True)
    elif symbol == "spark":
        outline([(12, 3), (14.5, 9.5), (21, 12), (14.5, 14.5),
                 (12, 21), (9.5, 14.5), (3, 12), (9.5, 9.5)], closed=True)
        line(20, 2, 20, 6)
        line(18, 4, 22, 4)
    elif symbol == "shiny":
        circle(10, 14, 7)
        circle(10, 14, 2)
        line(3, 14, 8, 14)
        line(12, 14, 17, 14)
        outline([(18, 1), (19.5, 5.5), (23, 7), (19.5, 8.5),
                 (18, 13), (16.5, 8.5), (13, 7), (16.5, 5.5)], closed=True)
    elif symbol == "bars":
        rect(4, 14, 4, 7, 0.5)
        rect(10, 9, 4, 12, 0.5)
        rect(16, 3, 4, 18, 0.5)
    elif symbol == "tag":
        outline([(3, 4), (12, 4), (21, 13), (13, 21), (3, 11)], closed=True)
        circle(7, 8, 1.3)
    elif symbol == "hand":
        circle(14, 5, 3)
        rect(2, 14, 4, 7, 0.5)
        outline([(6, 15), (9, 12), (15, 12), (17, 14), (15, 16), (11, 16)])
        outline([(6, 20), (9, 21), (14, 20), (21, 14), (20, 12), (17, 14)])
    elif symbol == "chest":
        rect(3, 5, 18, 16, 3)
        line(3, 11, 10, 11)
        line(14, 11, 21, 11)
        rect(10, 9, 4, 5, 0.5)
        line(12, 14, 12, 17)
    elif symbol == "capture":
        circle(10.5, 13, 8)
        circle(10.5, 13, 2.5)
        line(2.5, 13, 8, 13)
        line(13, 13, 18.5, 13)
        line(19, 2, 19, 8)
        outline([(16, 5), (19, 2), (22, 5)])
    elif symbol == "branches":
        circle(6, 12, 3)
        circle(18, 5, 3)
        circle(18, 19, 3)
        outline([(9, 12), (12, 12), (12, 5), (15, 5)])
        outline([(12, 12), (12, 19), (15, 19)])
    elif symbol == "shop":
        outline([(3, 10), (4.5, 4), (19.5, 4), (21, 10)], closed=True)
        line(8, 4, 7, 10)
        line(16, 4, 17, 10)
        outline([(4, 10), (4, 21), (20, 21), (20, 10)])
        rect(7, 14, 4, 3, 0.5)
        rect(14, 14, 3, 7)
    else:
        raise ValueError("Unknown category symbol: " + symbol)


@lru_cache(maxsize=2 * len(CATEGORY_SYMBOLS))
def category_icon(group: str, *, xd=False) -> QIcon:
    symbol = CATEGORY_SYMBOLS[group]
    icon = QIcon()
    normal, active, disabled = ("#e2c9bb", "#ffad93", "#a1837a") if xd else ("#c1d8cf", "#71e2e6", "#809d8f")
    for size in (20, 40):
        for mode, color in ((QIcon.Mode.Normal, normal), (QIcon.Mode.Selected, active),
                            (QIcon.Mode.Active, active), (QIcon.Mode.Disabled, disabled)):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(size/24, size/24)
            painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            _draw(painter, symbol)
            painter.end()
            icon.addPixmap(pixmap, mode)
    return icon
