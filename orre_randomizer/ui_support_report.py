"""Native review-and-save flow for the allowlisted offline support report."""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit

from .support_report import report_text, save_report, settings_snapshot
from .ui_run_tools import ToolDialog
from .ui_theme import MenuCheckBox


class SupportReportDialog(ToolDialog):
    def __init__(self, window):
        super().__init__(window, "Exporter un diagnostic", width=860, height=620)
        owner = window.xd if window.game_views.currentWidget() is window.xd else window
        self.contexts = []
        failure = getattr(owner, "_support_last_failure", None)
        if failure is not None:
            self.contexts.append(("Dernier échec", deepcopy(failure)))
        self.contexts.append(("Réglages actuels", settings_snapshot(owner)))
        self.body.insertWidget(1, self.note("Le fichier contient la version, le jeu, les réglages et, si vous l’incluez, la seed. L’erreur est résumée par un code."))
        self.body.insertWidget(2, self.note("Les chemins locaux, ROM, sauvegardes et journaux sont exclus. Rien n’est envoyé automatiquement."))
        row = QHBoxLayout()
        label = QLabel(window.text("Contexte"))
        self.context = QComboBox()
        self.context.setAccessibleName(window.text("Contexte du diagnostic"))
        label.setBuddy(self.context)
        for title, _data in self.contexts:
            self.context.addItem(window.text(title))
        row.addWidget(label); row.addWidget(self.context, 1)
        self.body.insertLayout(3, row)
        self.include_seed = MenuCheckBox(window.text("Inclure la seed"),
                                        check_color=self.palette().color(self.backgroundRole()))
        self.include_seed.setAccessibleName(window.text("Inclure la seed"))
        self.body.insertWidget(4, self.include_seed)
        self.seed_note = self.note("")
        self.body.insertWidget(5, self.seed_note)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setTabChangesFocus(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.preview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview.setAccessibleName(window.text("Contenu du diagnostic"))
        self.body.insertWidget(6, self.preview, 1)
        self.export = self.button("Enregistrer le diagnostic…", self.choose_destination)
        self.export.setObjectName("primary")
        self.footer.insertWidget(0, self.export)
        self.context.currentIndexChanged.connect(self.change_context)
        self.include_seed.toggled.connect(self.refresh_preview)
        self.change_context()

    def change_context(self):
        self.document = self.contexts[self.context.currentIndex()][1]
        allowed = self.document["seed_status"] == "included"
        self.include_seed.setEnabled(allowed)
        self.include_seed.setChecked(allowed)
        self.seed_note.setText(self.window.text(
            "Relisez la seed avant de partager ce fichier. Elle peut contenir du texte personnel." if allowed else
            "Seed non incluse : elle est invalide ou ressemble à une information privée. Vous pouvez la communiquer séparément si nécessaire."))
        self.refresh_preview()

    def refresh_preview(self):
        self.preview.setPlainText(report_text(self.document, include_seed=self.include_seed.isChecked()))

    def choose_destination(self):
        path, _filter = QFileDialog.getSaveFileName(self, self.window.text("Enregistrer le diagnostic"),
                                                   "orre-diagnostic.json", "JSON (*.json)")
        if not path:
            return
        document = deepcopy(self.document)
        include_seed = self.include_seed.isChecked()
        self.start_task(lambda cancel: save_report(path, document, include_seed=include_seed, cancel=cancel),
                        lambda _path: self.message("Diagnostic enregistré. Joignez ce fichier à votre signalement."),
                        message="Enregistrement du diagnostic…")


def show_support_report(window):
    if (window.busy or window.home.updating or window.preview_thread is not None
            or window.report_check is not None or window.xd.report_check is not None):
        window.set_status("Attendez la fin de l’opération en cours.")
        return
    workspaces = (window, window.xd)
    pending_reports = [(owner.report_rom_timer, owner.report_rom_timer.remainingTime())
                       for owner in workspaces if owner.report_rom_timer.isActive()]
    window._support_modal_open = True
    for owner in workspaces:
        owner.known_preview.timer.stop()
        owner.report_rom_timer.stop()
    try:
        SupportReportDialog(window).exec()
    finally:
        window._support_modal_open = False
        for timer, remaining in pending_reports:
            timer.start(max(0, remaining))
        for owner in workspaces:
            owner.known_preview.schedule()
