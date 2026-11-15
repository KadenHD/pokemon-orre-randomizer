"""Game selection using the same menu frames and native buttons as the wizard."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                              QSizePolicy, QStyle, QStyleOptionButton, QVBoxLayout, QWidget)

from .i18n import Message
from .resources import home_logos
from .ui_workspace import bounded, scroll_area
from .update_service import allowed_download
from .update_apply import automatic_updates_supported
from .ui_updates import UpdateInstaller


class GameChoice(QPushButton):
    def __init__(self, *, xd=False):
        super().__init__()
        self.xd = xd
        self.compact = False
        self.logo = QPixmap()
        self.game_name = ""
        self.description = ""
        self.setObjectName("gameChoice")
        self.setAutoDefault(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 360)
        self.setMaximumHeight(680)

    def sizeHint(self):
        return QSize(560, 168) if self.compact else QSize(440, 480)

    def minimumSizeHint(self):
        return QSize(240, 160 if self.compact else 360)

    def set_compact(self, compact):
        if self.compact != compact:
            self.compact = compact
            self.setMinimumHeight(160 if compact else 360)
            self.updateGeometry()
            self.update()

    def set_logo(self, logo):
        self.logo = logo
        self.update()

    def set_game_name(self, text):
        self.game_name = text
        self.update()

    def set_description(self, text):
        self.description = text
        self.setAccessibleDescription(text)
        self.update()

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        active = bool(option.state & (QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_HasFocus))
        fill, trim, accent, secondary = ("#24191a", "#8b6660", "#ffad93", "#e2c9bb") if self.xd else (
            "#082b24", "#54726c", "#71e2e6", "#c1d8cf")
        if not self.isEnabled():
            accent = trim
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        box = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        cut = 14
        shape = QPainterPath()
        shape.moveTo(box.left() + cut, box.top())
        shape.lineTo(box.right() - cut, box.top())
        shape.lineTo(box.right(), box.top() + cut)
        shape.lineTo(box.right(), box.bottom() - cut)
        shape.lineTo(box.right() - cut, box.bottom())
        shape.lineTo(box.left() + cut, box.bottom())
        shape.lineTo(box.left(), box.bottom() - cut)
        shape.lineTo(box.left(), box.top() + cut)
        shape.closeSubpath()
        painter.fillPath(shape, QColor(fill))
        painter.save()
        painter.setClipPath(shape)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#382326" if self.xd else "#103e37"))
        painter.drawPolygon(QPolygonF([
            box.topRight(), box.bottomRight(), box.bottomLeft(),
            QPointF(box.right() - box.width() * 0.35, box.top()),
        ]))
        painter.setBrush(QColor("#422829" if self.xd else "#15483f"))
        painter.drawPolygon(QPolygonF([
            box.bottomRight(), box.bottomLeft(),
            QPointF(box.right(), box.top() + box.height() * 0.65),
        ]))
        painter.restore()
        painter.setPen(QPen(QColor(accent if active else "#c5b6a9" if self.xd else "#b6ccc4"),
                            2 if active else 1.5))
        painter.drawPath(shape)
        painter.setPen(QPen(QColor(trim), 1))
        painter.drawLine(int(box.left() + 16), int(box.top() + 6),
                         int(box.right() - 16), int(box.top() + 6))

        if self.compact:
            brand = QRectF(24, 22, 174, self.height() - 44)
            identity = QRectF(218, 24, self.width() - 242, 30)
            description = QRectF(218, 58, self.width() - 242, 40)
            action = QRectF(218, self.height() - 58, self.width() - 242, 36)
        else:
            brand = QRectF(36, self.height() * 0.18, self.width() - 72,
                          min(116, self.height() * 0.33 - 16))
            identity = QRectF(24, self.height() * 0.51, self.width() - 48, 32)
            description = QRectF(24, identity.bottom() + 8, self.width() - 48, 48)
            action = QRectF(24, self.height() - 78, self.width() - 48, 48)

        painter.setPen(QColor("#fff4e6" if self.xd else "#f2f6f1"))
        if self.logo.isNull():
            font = QFont(self.font())
            font.setPixelSize(20 if self.compact else 28)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(brand, Qt.AlignmentFlag.AlignCenter, "XD" if self.xd else "COLOSSEUM")
        else:
            available = brand.size().toSize().boundedTo(QSize(240, 116))
            size = self.logo.size().scaled(available, Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(0, 0, size.width(), size.height())
            target.moveCenter(brand.center())
            painter.drawPixmap(target.toRect(), self.logo)

        font = QFont(self.font())
        font.setPixelSize(18 if self.compact else 23)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        align = Qt.AlignmentFlag.AlignVCenter | (
            Qt.AlignmentFlag.AlignLeft if self.compact else Qt.AlignmentFlag.AlignHCenter)
        painter.drawText(identity, align, self.game_name)
        font.setPixelSize(13 if self.compact else 14)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(secondary))
        painter.drawText(description, align | Qt.TextFlag.TextWordWrap, self.description)

        painter.setPen(QPen(QColor(accent if active else trim), 1))
        face = "#66302a" if self.xd else "#125359"
        painter.setBrush(QColor(fill if self.isDown() else face))
        painter.drawRect(action)
        painter.setPen(QColor("#fff4e6" if self.xd else "#f2f6f1"))
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        label = action.adjusted(12, 0, -36, 0)
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, self.text())
        painter.setPen(QColor(accent))
        painter.drawText(action.adjusted(0, 0, -14, 0),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "→")


class GameSelection(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.update_release = None
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)
        header = QWidget()
        header.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        heading = QVBoxLayout(header)
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(8)
        title = window.label("Choisissez un jeu")
        title.setObjectName("section")
        heading.addWidget(title)
        heading.addWidget(window.note("ISO ou RVZ · Europe, USA et Japon"))
        layout.addWidget(header)
        layout.addSpacing(16)
        self.choices = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.choices.setSpacing(16)
        self.colosseum = GameChoice()
        self.xd = GameChoice(xd=True)
        self.logo_assets = home_logos()
        self.colosseum.set_logo(QPixmap(str(self.logo_assets["colosseum"])) if "colosseum" in self.logo_assets else QPixmap())
        self.xd.set_logo(QPixmap(str(self.logo_assets["xd"])) if "xd" in self.logo_assets else window.xd_logo)
        for button, name, description, action, callback in (
            (self.colosseum, "Pokémon Colosseum", "Deux starters · 48 Pokémon obscurs",
             "Ouvrir Colosseum", window.show_colosseum),
            (self.xd, "Pokémon XD", "Un starter · 83 Pokémon obscurs", "Ouvrir XD", window.show_xd),
        ):
            window.bind(button.set_game_name, name)
            window.bind(button.set_description, description)
            window.bind(button.setText, action)
            window.bind(button.setAccessibleName, action)
            button.clicked.connect(callback)
            self.choices.addWidget(button, 1)
        layout.addLayout(self.choices, 1)
        self.update_button = QPushButton()
        self.update_button.setObjectName("updateDownload")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.download_update)
        self.update_button.hide()
        layout.addWidget(self.update_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.update_status = QLabel()
        self.update_status.setWordWrap(True)
        self.update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status.setTextFormat(Qt.TextFormat.PlainText)
        self.update_status.hide()
        layout.addWidget(self.update_status)
        self.update_controls = QWidget()
        progress_row = QHBoxLayout(self.update_controls)
        progress_row.setContentsMargins(0, 0, 0, 0)
        self.update_progress = QProgressBar()
        self.update_progress.setObjectName("updateProgress")
        self.update_progress.setRange(0, 100)
        self.update_cancel = QPushButton()
        self.update_cancel.setObjectName("updateCancel")
        window.bind(self.update_cancel.setText, "Annuler")
        progress_row.addWidget(self.update_progress, 1)
        progress_row.addWidget(self.update_cancel)
        self.update_controls.hide()
        layout.addWidget(self.update_controls)
        self.installer = UpdateInstaller(self)
        self.installer.progress.connect(self.update_progress.setValue)
        self.installer.state_changed.connect(self.update_state_changed)
        self.installer.failed.connect(self.update_failed)
        self.installer.ready.connect(window.close)
        self.update_cancel.clicked.connect(self.installer.cancel)
        self.update_error = None
        self.updated_version = None
        credit = window.button(Message("Fait par {author}", author="KadenHD (Pierre CLEMENT)"))
        credit.setObjectName("authorLink")
        credit.setCursor(Qt.CursorShape.PointingHandCursor)
        credit.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/KadenHD")))
        layout.addWidget(credit, 0, Qt.AlignmentFlag.AlignHCenter)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scroll_area(bounded(content))
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        outer.addWidget(self.scroll)
        self.update_visibility_timer = QTimer(self)
        self.update_visibility_timer.setSingleShot(True)
        self.update_visibility_timer.timeout.connect(self.keep_update_visible)

    def show_update(self, update):
        if not automatic_updates_supported() or not allowed_download(update):
            return
        self.update_release = update
        self.retranslate()
        self.update_button.show()

    def retranslate(self):
        if self.update_release is not None:
            label = self.window.text("Mettre à jour vers {version}", version=self.update_release.version)
            self.update_button.setText(label)
            self.update_button.setAccessibleName(label)
            self.update_button.setToolTip(self.window.text(
                "Télécharger, installer et redémarrer l’outil. Vos ROM et sauvegardes sont conservées."))
        messages = {
            "network": "Téléchargement interrompu. Vérifiez votre connexion, puis réessayez.",
            "checksum": "Le fichier téléchargé est incomplet ou invalide. Réessayez la mise à jour.",
            "package": "Le paquet de mise à jour est invalide. La version actuelle est conservée.",
            "disk": "Impossible de préparer la mise à jour. Vérifiez l’espace disque et l’accès au dossier de l’outil.",
            "running": "Fermez les autres fenêtres du randomizer, puis réessayez.",
            "busy": "Attendez la fin du calcul ou de la création de ROM avant de mettre à jour.",
            "update_failed": "La mise à jour a échoué. La version actuelle est conservée. Réessayez.",
        }
        if self.update_error:
            message = messages.get(self.update_error, messages["update_failed"])
        elif self.updated_version:
            message = Message("Version {version} installée.", version=self.updated_version)
        else:
            message = {"download": "Téléchargement de la mise à jour…",
                       "prepare": "Préparation de la mise à jour. L’outil va redémarrer…",
                       "ready": "Redémarrage pour terminer la mise à jour…"}.get(self.installer.state, "")
        self.update_status.setText(self.window.text(message))
        self.update_status.setVisible(bool(message))
        self.update_progress.setAccessibleName(self.window.text("Téléchargement de la mise à jour…"))
        if message and hasattr(self, "update_visibility_timer"):
            self.update_visibility_timer.start(0)

    def keep_update_visible(self):
        control = self.update_controls if self.update_controls.isVisible() else self.update_status
        if control.isVisible():
            self.scroll.ensureWidgetVisible(control, 0, 12)

    def download_update(self):
        if self.update_release is not None and allowed_download(self.update_release):
            if (self.window.busy or self.window.preview_thread is not None
                    or self.window.report_check is not None or self.window.xd.report_check is not None):
                self.update_failed("busy")
                return
            self.update_error = None
            self.installer.start(self.update_release)

    def update_state_changed(self, state):
        active = state in ("download", "prepare", "ready")
        self.update_error = None
        self.updated_version = None
        self.update_button.setEnabled(not active)
        self.update_controls.setVisible(state in ("download", "prepare"))
        self.update_cancel.setEnabled(state == "download")
        self.update_progress.setRange(0, 100 if state == "download" else 0)
        for widget in (self.colosseum, self.xd, self.window.colosseum, self.window.xd, self.window.profile_menu):
            widget.setEnabled(not active)
        self.retranslate()

    def update_failed(self, reason):
        self.update_state_changed("error")
        self.update_error = reason
        self.retranslate()

    def show_update_result(self, result):
        if result.get("state") == "complete":
            self.updated_version = result["version"]
            self.retranslate()
        else:
            self.update_failed(result.get("code", "update_failed"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = event.size().width() < 800
        self.choices.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        for button in (self.colosseum, self.xd):
            button.set_compact(compact)
