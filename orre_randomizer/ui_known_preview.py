"""Load only retained encounters automatically; full previews require a click."""
from copy import deepcopy
from pathlib import Path
import threading

from PySide6.QtCore import QObject, QTimer, Slot

from .preview import baseline_rows, preview_known, preview_xd_known
from .profiles import validate_seed
from .service import UserError
from .xd_preview import baseline_rows as xd_baseline_rows


def known_rows(options, result=None, *, xd=False):
    """Enrich only species established by the current effective settings."""
    baseline = xd_baseline_rows(options) if xd else baseline_rows(options)
    if not result:
        return baseline

    def merge(pending, actual):
        dex = pending.get('national_dex')
        if xd and dex is None and pending.get('species') is not None:
            dex = baseline['national_ids'].get(str(pending['species']), pending['species'])
        if dex is None or actual is None:
            return pending
        actual_dex = actual.get('national_dex')
        if xd and actual_dex is None:
            species = actual.get('species')
            actual_dex = result.get('national_ids', {}).get(str(species), species)
        if dex != actual_dex:
            return pending
        return deepcopy(actual)

    def merge_list(pending, actual, key):
        by_key = {row[key]: row for row in actual}
        return [merge(row, by_key.get(row[key])) for row in pending]

    if xd:
        baseline['starter'] = merge(baseline['starter'], result.get('starter'))
        baseline['decks']['Story']['shadows'] = merge_list(
            baseline['decks']['Story']['shadows'], result.get('decks', {}).get('Story', {}).get('shadows', ()),
            'shadow_id')
        baseline['gifts'] = merge_list(baseline['gifts'], result.get('gifts', ()), 'key')
        spots = {(row['spot'], row['slot']): row for row in result.get('poke_spots', ())}
        baseline['poke_spots'] = [merge(row, spots.get((row['spot'], row['slot'])))
                                 for row in baseline['poke_spots']]
    else:
        for field, key in (('starters', 'key'), ('shadows', 'shadow_id'), ('gifts', 'key')):
            baseline[field] = merge_list(baseline[field], result.get(field, ()), key)
        event = baseline['postgame_shadow_lugia']
        if event['enabled']:
            event['team'] = [dict(national_dex=None if (
                options.postgame_randomize_lugia if index == 5 else options.postgame_randomize_team)
                else dex, level=65 + index)
                for index, dex in enumerate((282, 178, 356, 365, 257, 249))]
            actual = result.get('postgame_shadow_lugia', {}).get('team', ())
            by_slot = {row.get('slot', 5510 + index): row for index, row in enumerate(actual)}
            event['team'] = [merge(row, by_slot.get(5510 + index))
                             for index, row in enumerate(event['team'])]
    return baseline


class KnownPreview(QObject):
    """One debounced, cancellable job using the existing shared worker lifetime."""
    def __init__(self, window, workspace, *, xd=False):
        super().__init__(window)
        self.window, self.workspace, self.xd = window, workspace, xd
        self.key = self.running_key = self.failed_key = None
        self.result = self.prepared = self.visible_result = None
        self.reveal_requested = False
        self.manual_requested = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.start)

    @property
    def running(self):
        return self.window.preview_thread is not None and getattr(self.window, 'preview_owner', None) is self

    def active(self):
        panel = self.workspace if self.xd else self.window.colosseum
        return (not self.window.close_after_cancel and not getattr(self.window, "_support_modal_open", False)
                and self.window.isVisible()
                and self.window.game_views.currentWidget() is panel
                and self.workspace.step == 1 and self.workspace.workspace_tabs.currentIndex() == 1)

    def schedule(self):
        current = self.workspace.preview_configuration()
        if current != self.key:
            self.key, self.result, self.prepared, self.failed_key = current, None, None, None
            self.visible_result = None
            self.manual_requested = self.reveal_requested = False
            if self.running:
                self.window.preview_cancel_event.set()
            if self.window.detail_window is not None:
                self.window.detail_window.close()
        if self.running and not self.active() and not self.reveal_requested:
            self.window.preview_cancel_event.set()
        if self.workspace.preview_result is not None:
            self.timer.stop()
            return
        if self.active() and not self.manual_requested and self.result is None and self.failed_key != current:
            if not self.running:
                self.timer.start()
        else:
            self.timer.stop()

    def rows(self, options):
        result = self.result if self.key == self.workspace.preview_configuration() else None
        if result is not None and self.visible_result is not None:
            return self.visible_result
        return known_rows(options, result, xd=self.xd)

    @Slot()
    def start(self):
        self.schedule()
        self.timer.stop()
        if (not self.active() or self.result is not None or self.failed_key == self.key
                or self.manual_requested or self.workspace.preview_result is not None):
            return
        options = self.workspace.current_options()
        baseline = known_rows(options, xd=self.xd)
        if self.xd:
            rows = [baseline['starter'], *baseline['decks']['Story']['shadows'],
                    *baseline['gifts'], *baseline['poke_spots']]
            available = any(row.get('species') or row.get('national_dex') for row in rows)
        else:
            available = any(row.get('national_dex') for group in ('starters', 'shadows', 'gifts')
                            for row in baseline[group]) or options.postgame_shadow_lugia and (
                                not options.postgame_randomize_team or not options.postgame_randomize_lugia)
        if not available:
            self.result = self.visible_result = baseline
            return
        if self.window.busy or self.window.preview_thread is not None:
            self.timer.start(200)
            return
        source = Path(self.workspace.source.text().strip())
        tool = None
        try:
            validate_seed(self.workspace.seed.text())
            if source.suffix.lower() not in ('.iso', '.gcm', '.rvz') or not source.is_file():
                return
        except (OSError, UserError, ValueError):
            return
        self.running_key = self.key
        self.reveal_requested = False
        self.window.preview_cancel_event = threading.Event()
        arguments = dict(source=source, seed=self.workspace.seed.text(),
                         dolphin_tool=tool, cancel=self.window.preview_cancel_event,
                         cache=self.window.preview_cache)
        arguments['xd_options' if self.xd else 'options'] = options
        self.window.launch_preview(arguments, owner=self, succeeded=self.succeeded, failed=self.failed,
                                   roulette=lambda _faces: None,
                                   task=preview_xd_known if self.xd else preview_known)
        self.workspace.render_preview()

    def request_full(self):
        """Queue a full preview after a retained-only job, without promoting it."""
        self.schedule()
        self.timer.stop()
        self.manual_requested = True
        if not self.running:
            return False
        self.reveal_requested = True
        self.workspace.render_preview()
        return True

    @Slot(dict, object)
    def succeeded(self, result, prepared):
        if (self.window.preview_cancel_event.is_set() or self.running_key != self.key
                or self.key != self.workspace.preview_configuration()):
            return
        self.result, self.prepared = result, None
        self.visible_result = known_rows(self.workspace.current_options(), result, xd=self.xd)
        self.workspace.render_preview()

    @Slot(object, bool)
    def failed(self, error, cancelled):
        if self.running_key != self.key:
            return
        if not cancelled:
            self.failed_key = self.key

    def cancel_preview(self):
        self.timer.stop()
        self.failed_key = self.key
        self.window.preview_cancel_event.set()
        if self.reveal_requested:
            self.workspace.preview_key = self.workspace.preview_result = self.workspace.preview_plan = None
            if self.xd:
                self.workspace.preview_action = 'Réessayer'
                self.workspace.preview_message = 'Annulation de l’aperçu…'
            else:
                self.workspace._preview_action = 'Réessayer'
                self.workspace._preview_message = 'Annulation de l’aperçu…'
        self.reveal_requested = False
        self.workspace.render_preview()

    def finished_preview(self):
        reveal, key = self.reveal_requested, self.key
        self.running_key = None
        self.reveal_requested = False
        if not self.xd:
            self.workspace.preview_running_key = None
            if self.workspace._preview_message == 'Annulation de l’aperçu…':
                self.workspace._preview_message = 'Aperçu annulé.'
        self.workspace.render_preview()
        if reveal and not self.window.close_after_cancel:
            def launch():
                if self.manual_requested and key == self.key and self.active():
                    self.workspace.start_preview()
            QTimer.singleShot(0, self, launch)
        if not self.window.close_after_cancel:
            self.schedule()
