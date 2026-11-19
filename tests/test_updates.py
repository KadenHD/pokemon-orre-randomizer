"""Official, stable release selection and nonblocking native home notification."""
import copy
from dataclasses import replace
import hashlib
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from orre_randomizer.update_service import (LATEST_RELEASE_API, ReleaseUpdate,
                                           allowed_download, release_update, _version_key)


def metadata(version="1.2.20", data=b"verified update"):
    name = f"pokemon-orre-randomizer-{version}-windows-x64-setup.exe"
    names = (name, name.replace('-setup.exe', '.zip'))
    return {"tag_name": f"v{version}", "prerelease": False, "draft": False,
            "assets": [{"name": name, "state": "uploaded", "size": len(data),
                        "digest": "sha256:" + hashlib.sha256(data).hexdigest(), "browser_download_url":
                        f"https://github.com/KadenHD/pokemon-orre-randomizer/releases/download/v{version}/{name}"}
                       for name in names]}


class ReleaseSelectionTests(unittest.TestCase):
    def test_only_newer_stable_version_is_offered(self):
        self.assertEqual(release_update(metadata(), "1.2.19").version, "1.2.20")
        for version in ("1.2.20", "1.3.0", "2.0.0", "invalid"):
            with self.subTest(current=version):
                self.assertIsNone(release_update(metadata(), version))
        self.assertIsNotNone(release_update(metadata(), "1.2.20-rc.10"))
        self.assertIsNotNone(release_update(metadata(), "1.2.20rc1"))
        for field in ("prerelease", "draft"):
            payload = metadata()
            payload[field] = True
            self.assertIsNone(release_update(payload, "1.2.19"))
        self.assertIsNone(release_update(metadata("1.2.21-rc.1"), "1.2.19"))

    def test_semantic_versions_order_numeric_components_and_prereleases(self):
        versions = ("1.2.9", "1.2.10-alpha", "1.2.10-alpha.1", "1.2.10-alpha.beta",
                    "1.2.10-beta", "1.2.10-beta.2", "1.2.10-beta.11", "1.2.10-rc.1", "1.2.10", "1.10.0", "2.0.0")
        self.assertEqual(sorted(reversed(versions), key=_version_key), list(versions))
        self.assertEqual(_version_key("1.2.10+build.7"), _version_key("1.2.10"))
        self.assertNotEqual(_version_key("1.2.10-rc1"), _version_key("1.2.10-rc.1"))
        for version in ("01.2.3", "1.2.03", "1.2", "1.2.3-alpha.01", "1.2.3-", "1.2.3+", "1.2.3-a..b"):
            self.assertIsNone(_version_key(version), version)

    def test_no_release_body_title_or_arbitrary_executable_is_trusted(self):
        payload = metadata()
        payload.update(name="<script>bad()</script>", body="run this shell command")
        update = release_update(payload, "1.0.0")
        self.assertEqual(update.version, "1.2.20")
        for field, value in (("name", "random.exe"), ("state", "new"), ("browser_download_url", "file:///C:/run.exe")):
            malformed = copy.deepcopy(payload)
            malformed["assets"][0][field] = value
            self.assertIsNone(release_update(malformed, "1.0.0"))
        for malformed in (None, [], {}, {"draft": False, "prerelease": False, "tag_name": []}):
            self.assertIsNone(release_update(malformed, "1.0.0"))

    def test_download_namespace_is_exact_and_https(self):
        good = release_update(metadata(), "1.0.0")
        for url in (good.download_url.replace("https:", "http:"),
                    good.download_url.replace("github.com/", "github.com.evil.test/"),
                    good.download_url.replace("KadenHD/", "someone/"),
                    good.download_url.replace("/v1.2.20/", "/v1.2.19/"),
                    good.download_url + "?redirect=bad", good.download_url + "#bad",
                    good.download_url.replace("github.com", "evil@github.com"),
                    "https://[bad", "javascript:alert(1)"):
            with self.subTest(url=url):
                self.assertFalse(allowed_download(replace(good, download_url=url)))
        self.assertTrue(allowed_download(good))

    def test_installer_and_portable_require_size_and_sha256_from_the_release(self):
        for kind in ('installer', 'portable'):
            payload = metadata()
            self.assertEqual(release_update(payload, '1.0.0', kind).kind, kind)
            for field, value in (('size', 0), ('size', True), ('size', 2**31), ('digest', None),
                                 ('digest', 'sha256:wrong'), ('digest', 'md5:' + 'a' * 64)):
                broken = copy.deepcopy(payload)
                for asset in broken['assets']:
                    asset[field] = value
                self.assertIsNone(release_update(broken, '1.0.0', kind))

try:
    from PySide6.QtCore import QObject, QSettings, Signal, QCoreApplication, QEvent, QTimer, QUrl, Qt
    from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
    from PySide6.QtWidgets import QApplication
    from orre_randomizer.ui_updates import UpdateChecker, UpdateInstaller
    from orre_randomizer.gui import MainWindow
except ImportError:
    MainWindow = None


if MainWindow is not None:
    class FakeReply(QObject):
        readyRead = Signal()
        finished = Signal()

        def __init__(self):
            super().__init__()
            self.data = bytearray()
            self.running = True
            self.failure = QNetworkReply.NetworkError.NoError
            self.status = 200
            self.redirect = QUrl()

        def read(self, count):
            result = self.data[:count]
            del self.data[:count]
            return bytes(result)

        def setReadBufferSize(self, size):
            self.read_buffer_size = size

        def bytesAvailable(self):
            return len(self.data)

        def feed(self, data):
            self.data.extend(data)
            self.readyRead.emit()

        def complete(self, payload=None):
            if payload is not None:
                self.data.extend(json.dumps(payload).encode())
            self.running = False
            self.finished.emit()

        def isRunning(self):
            return self.running

        def abort(self):
            self.failure = QNetworkReply.NetworkError.OperationCanceledError
            self.running = False
            self.finished.emit()

        def error(self):
            return self.failure

        def attribute(self, attribute):
            if attribute == QNetworkRequest.Attribute.RedirectionTargetAttribute:
                return self.redirect
            return self.status

        def url(self):
            return QUrl('https://github.com/KadenHD/pokemon-orre-randomizer/releases/download/v1.2.20/update.zip')


@unittest.skipIf(MainWindow is None, "requires optional Qt desktop dependencies")
class UpdateQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.music = patch("orre_randomizer.ui_music.NativeMusic").start()
        self.sound = patch("orre_randomizer.ui_audio.winsound").start()
        self.addCleanup(patch.stopall)
        self.reply = FakeReply()
        self.manager = Mock()
        self.manager.get.return_value = self.reply
        patch("orre_randomizer.ui_updates.QNetworkAccessManager", return_value=self.manager).start()
        patch("orre_randomizer.ui_updates.update_kind", return_value="installer").start()
        patch("orre_randomizer.ui_home.automatic_updates_supported", return_value=True).start()
        self.checker = UpdateChecker("1.2.19")
        self.results = []
        self.checker.available.connect(self.results.append)
        self.window = None

    def tearDown(self):
        if self.window is not None:
            self.window.home.installer.state = 'idle'
            self.window.home.update_state_changed('idle')
            self.window.close()
            self.window.deleteLater()
        self.checker.close()
        self.checker.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def make_window(self):
        settings = QSettings(str(Path(self.folder.name) / "settings.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = MainWindow(settings=settings, system_languages=["en-US"], start_on_home=True)
        return self.window

    def test_async_check_runs_once_with_bounded_public_request(self):
        self.checker.check_once()
        self.checker.check_once()
        self.manager.get.assert_called_once()
        request = self.manager.get.call_args.args[0]
        self.assertEqual(request.url().toString(), LATEST_RELEASE_API)
        self.assertEqual(request.transferTimeout(), 8000)
        self.assertFalse(request.hasRawHeader("Authorization"))
        self.assertEqual(self.reply.read_buffer_size, self.checker.MAX_BYTES + 1)
        self.assertTrue(self.checker.timeout.isActive())
        self.assertFalse(self.results)
        self.reply.complete(metadata())
        self.assertEqual(len(self.results), 1)
        self.assertIsNone(self.checker.reply)
        self.assertFalse(self.checker.timeout.isActive())

    def test_window_checks_for_updates_by_default(self):
        window = self.make_window()
        self.manager.get.assert_called_once()
        self.assertTrue(window.update_checker.started)
        window.show_colosseum()
        window.show_home()
        self.app.processEvents()
        self.manager.get.assert_called_once()

    def test_window_can_disable_update_checks_before_the_first_home_render(self):
        settings = QSettings(str(Path(self.folder.name) / "offline.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        self.window = MainWindow(settings=settings, system_languages=["en-US"],
                                 start_on_home=True, allow_update_checks=False)
        for select in (self.window.show_colosseum, self.window.show_xd):
            select()
            self.window.show_home()
            self.app.processEvents()
        self.manager.get.assert_not_called()
        self.assertFalse(self.window.update_checker.started)
        self.assertTrue(self.window.update_checker.closed)
        self.assertIsNone(self.window.update_checker.reply)
        self.assertFalse(self.window.update_checker.timeout.isActive())

    def test_offline_malformed_rate_limited_and_oversized_responses_are_silent(self):
        for case in ("offline", "rate_limit", "malformed", "oversize"):
            reply = FakeReply()
            self.manager.get.return_value = reply
            checker = UpdateChecker("1.2.19")
            results = []
            checker.available.connect(results.append)
            checker.check_once()
            if case == "offline":
                reply.failure = QNetworkReply.NetworkError.HostNotFoundError
            elif case == "rate_limit":
                reply.status = 403
            elif case == "malformed":
                reply.feed(b"not json")
            else:
                reply.feed(b" " * (checker.MAX_BYTES + 1))
            if reply.running:
                reply.complete(metadata() if case != "malformed" else None)
            self.assertFalse(results, case)
            self.assertFalse(checker.timeout.isActive(), case)
            checker.close()
            checker.deleteLater()

    def test_timeout_and_close_abort_without_waiting_or_emitting(self):
        for action in ("timeout", "close"):
            reply = FakeReply()
            self.manager.get.return_value = reply
            checker = UpdateChecker("1.2.19")
            results = []
            checker.available.connect(results.append)
            checker.check_once()
            started = time.monotonic()
            checker.timeout.timeout.emit() if action == "timeout" else checker.close()
            self.assertLess(time.monotonic() - started, 0.2)
            self.assertFalse(results)
            self.assertFalse(reply.running)
            checker.deleteLater()

    def test_home_button_is_hidden_until_ready_localized_and_user_initiated(self):
        window = self.make_window()
        self.assertTrue(window.home.update_button.isHidden())
        self.reply.complete(metadata("9.8.7"))
        button = window.home.update_button
        self.assertFalse(button.isHidden())
        self.assertEqual(button.text(), "Update to 9.8.7")
        from orre_randomizer.i18n import LANGUAGES, translate, Message
        for language in LANGUAGES:
            window.language_combo.setCurrentIndex(window.language_combo.findData(language))
            self.assertEqual(button.text(), translate(Message("Mettre à jour vers {version}", version="9.8.7"), language))
            self.assertEqual(button.accessibleName(), button.text())
        with patch.object(window.home.installer, "start") as started:
            started.assert_not_called()
            button.click()
            self.assertEqual(started.call_args.args[0].version, "9.8.7")
        for switch in (window.show_xd, window.show_home, window.show_colosseum, window.show_home):
            switch()
        self.manager.get.assert_called_once()
        self.assertFalse(button.isHidden())
        self.music.return_value.play.assert_not_called()
        self.sound.PlaySound.assert_not_called()

    def test_window_remains_responsive_and_closes_with_pending_check(self):
        window = self.make_window()
        fired = []
        QTimer.singleShot(0, lambda: fired.append(True))
        self.app.processEvents()
        self.assertEqual(fired, [True])
        self.assertTrue(self.reply.running)
        started = time.monotonic()
        window.close()
        self.assertLess(time.monotonic() - started, 0.2)
        self.assertTrue(window.update_checker.closed)
        self.assertFalse(self.reply.running)

    def test_update_and_both_game_choices_fit_all_languages_and_supported_sizes(self):
        from orre_randomizer.i18n import LANGUAGES
        window = self.make_window()
        self.reply.complete(metadata("9.8.7"))
        window.show()
        for width, height in ((1040, 800), (680, 540)):
            for language in LANGUAGES:
                window.language_combo.setCurrentIndex(window.language_combo.findData(language))
                window.resize(width, height)
                self.app.processEvents()
                with self.subTest(size=(width, height), language=language):
                    self.assertLessEqual(window.width(), width)
                    self.assertLessEqual(window.height(), height)
                    for control in (window.home.update_button, window.open_colosseum, window.open_xd):
                        top = control.mapTo(window, control.rect().topLeft())
                        bottom = control.mapTo(window, control.rect().bottomRight())
                        self.assertGreaterEqual(top.x(), 0)
                        self.assertLessEqual(bottom.x(), width)
                    window.home.scroll.ensureWidgetVisible(window.home.update_button)
                    self.app.processEvents()
                    button = window.home.update_button
                    self.assertTrue(window.rect().contains(button.mapTo(window, button.rect().bottomRight())))
                    self.assertGreater(button.mapTo(window.home.scroll.widget(), button.rect().topLeft()).y(),
                                       window.open_xd.mapTo(window.home.scroll.widget(), window.open_xd.rect().bottomRight()).y())
                    self.assertEqual(window.home.scroll.horizontalScrollBar().maximum(), 0)
                    button = window.home.update_button
                    self.assertLessEqual(button.fontMetrics().horizontalAdvance(button.text())
                                         + 20, button.width())

    def test_update_download_hashes_streaming_bytes_and_only_then_starts_the_helper(self):
        download = UpdateInstaller()
        self.addCleanup(download.close)
        update = release_update(metadata(), '1.0.0')
        with patch('orre_randomizer.ui_updates.start_helper') as helper:
            helper.return_value.poll.return_value = None
            download.start(update)
            self.reply.feed(b'verified ')
            helper.assert_not_called()
            self.reply.feed(b'update')
            self.reply.complete()
            self.assertEqual(download.package.read_bytes(), b'verified update')
            helper.assert_called_once()
            self.assertEqual(download.state, 'prepare')
            ready = []
            download.ready.connect(lambda: ready.append(True))
            (download.work / 'status.json').write_text('{"state":"ready"}')
            download.poll_helper()
            self.assertEqual(ready, [True])
            self.assertEqual(download.state, 'ready')
            # No real helper is running: explicitly release this synthetic job.
            download.state = 'idle'
            helper.return_value.poll.return_value = 0

    def test_incomplete_tampered_oversized_or_failed_download_never_executes(self):
        for content in (b'short', b'wrong content!!', b'x' * 16, None):
            reply = FakeReply()
            self.manager.get.return_value = reply
            download = UpdateInstaller()
            failed = []
            download.failed.connect(failed.append)
            with patch('orre_randomizer.ui_updates.start_helper') as helper:
                download.start(release_update(metadata(), '1.0.0'))
                work = download.work
                if content is None:
                    reply.failure = QNetworkReply.NetworkError.HostNotFoundError
                else:
                    reply.feed(content)
                if reply.running:
                    reply.complete()
                helper.assert_not_called()
                self.assertTrue(failed)
                self.assertFalse(work.exists())
                download.close()

    def test_cancel_is_nonblocking_removes_partial_package_and_allows_retry(self):
        download = UpdateInstaller()
        self.addCleanup(download.close)
        update = release_update(metadata(), '1.0.0')
        download.start(update)
        work = download.work
        self.reply.feed(b'part')
        started = time.monotonic()
        download.cancel()
        self.assertLess(time.monotonic() - started, .2)
        self.assertFalse(work.exists())
        self.assertEqual(download.state, 'idle')
        self.manager.get.return_value = FakeReply()
        download.start(update)
        self.assertEqual(download.state, 'download')

    def test_home_download_states_are_localized_cancellable_and_restore_controls(self):
        from orre_randomizer.i18n import LANGUAGES
        window = self.make_window()
        self.reply.complete(metadata('9.8.7'))
        for state in ('download', 'prepare', 'ready', 'idle'):
            window.home.installer.state = state
            window.home.update_state_changed(state)
            self.assertEqual(window.home.colosseum.isEnabled(), state == 'idle')
            self.assertEqual(window.home.update_cancel.isEnabled(), state == 'download')
            for language in LANGUAGES:
                window.language_combo.setCurrentIndex(window.language_combo.findData(language))
                self.assertEqual(window.home.update_status.isHidden(), state == 'idle')
        window.home.installer.state = 'error'
        window.home.update_failed('checksum')
        self.assertTrue(window.home.update_button.isEnabled())
        self.assertFalse(window.home.update_notice.isHidden())

    def test_update_locks_navigation_header_profiles_drops_and_close_until_cancelled(self):
        from PySide6.QtTest import QTest
        window = self.make_window()
        self.reply.complete(metadata('9.8.7'))
        window.show()
        self.app.processEvents()
        window.sound_toggle.setEnabled(False)
        original_source = window.source.text()
        window.home.download_update()
        self.app.processEvents()
        self.assertTrue(window.home.updating)
        self.assertIs(window.home.pages.currentWidget(), window.home.update_page)
        self.assertFalse(window.home.scroll.isVisible())
        for control in (window.music_toggle, window.sound_toggle, window.language_combo,
                        window.profile_menu, window.import_profile_button,
                        window.export_profile_button, window.import_report_button,
                        window.colosseum, window.xd, window.open_colosseum, window.open_xd):
            self.assertFalse(control.isEnabled())
        self.assertFalse(window.acceptDrops())
        with patch('orre_randomizer.gui.QFileDialog.getOpenFileName') as open_file, \
                patch('orre_randomizer.gui.QFileDialog.getSaveFileName') as save_file, \
                patch.object(window.known_preview, 'request_full') as colosseum_preview, \
                patch.object(window.xd.known_preview, 'request_full') as xd_preview:
            for action in (window.show_colosseum, window.show_xd, window.show_home,
                           window.choose_profile, window.choose_profile_destination,
                           window.choose_creation_report, window.start, window.xd.start,
                           window.start_preview, window.xd.start_preview):
                action()
            window.go_step(2)
            window.xd.go_step(2)
            window.import_profile_button.trigger()
            window.import_report_button.trigger()
            window.export_profile_button.trigger()
            open_file.assert_not_called()
            save_file.assert_not_called()
            colosseum_preview.assert_not_called()
            xd_preview.assert_not_called()
        self.assertIs(window.game_views.currentWidget(), window.home)
        self.assertEqual((window.step, window.xd.step), (0, 0))
        for handler in (window.dragEnterEvent, window.dropEvent):
            event = Mock()
            handler(event)
            event.ignore.assert_called_once()
            event.mimeData.assert_not_called()
            event.acceptProposedAction.assert_not_called()
        self.assertEqual(window.source.text(), original_source)
        self.assertFalse(window.close())
        self.assertTrue(window.isVisible())
        QTest.keyClick(window.home.update_cancel, Qt.Key.Key_Escape)
        self.app.processEvents()
        self.assertFalse(window.home.updating)
        self.assertEqual(window.home.installer.state, 'idle')
        self.assertIs(window.home.pages.currentWidget(), window.home.scroll)
        self.assertTrue(window.language_combo.isEnabled())
        self.assertFalse(window.sound_toggle.isEnabled())
        self.assertTrue(window.import_profile_button.isEnabled())
        self.assertTrue(window.acceptDrops())

    def test_preparation_blocks_escape_and_close_but_error_restores_access(self):
        from PySide6.QtTest import QTest
        window = self.make_window()
        self.reply.complete(metadata('9.8.7'))
        window.show()
        window.home.installer.state = 'prepare'
        window.home.update_state_changed('prepare')
        self.app.processEvents()
        self.assertFalse(window.home.update_cancel.isVisible())
        self.assertFalse(window.close())
        with patch.object(window.home.installer, 'cancel') as cancel:
            QTest.keyClick(window.home.update_panel, Qt.Key.Key_Escape)
            cancel.assert_not_called()
        window.home.installer.fail('checksum')
        self.app.processEvents()
        self.assertFalse(window.home.updating)
        self.assertTrue(window.home.update_notice.isVisible())
        self.assertTrue(window.home.update_button.isEnabled())
        self.assertTrue(window.language_combo.isEnabled())
        window.home.installer.state = 'ready'
        window.home.update_state_changed('ready')
        self.assertTrue(window.close())

    def test_download_redirects_require_https_and_github_asset_hosts(self):
        for url, allowed in (('https://release-assets.githubusercontent.com/asset?signature=test', True),
                             ('http://release-assets.githubusercontent.com/asset', False),
                             ('https://github.com.evil.test/asset', False),
                             ('https://attacker@github.com/asset', False)):
            reply = FakeReply()
            self.manager.get.return_value = reply
            download = UpdateInstaller()
            download.start(release_update(metadata(), '1.0.0'))
            calls = self.manager.get.call_count
            reply.status, reply.redirect = 302, QUrl(url)
            self.manager.get.return_value = FakeReply()
            reply.complete()
            self.assertEqual(self.manager.get.call_count, calls + int(allowed), url)
            self.assertEqual(download.state, 'download' if allowed else 'error')
            download.close()

    def test_installing_error_and_success_fit_all_languages_and_sizes(self):
        from orre_randomizer.i18n import LANGUAGES, translate
        window = self.make_window()
        self.reply.complete(metadata('9.8.7'))
        window.show()
        for width, height in ((1040, 800), (680, 540)):
            window.resize(width, height)
            for language in LANGUAGES:
                window.language_combo.setCurrentIndex(window.language_combo.findData(language))
                for state in ('download', 'prepare', 'ready', 'checksum', 'disk', 'complete'):
                    if state in ('download', 'prepare', 'ready'):
                        window.home.installer.state = state
                        window.home.update_state_changed(state)
                    elif state == 'complete':
                        window.home.update_state_changed('idle')
                        window.home.show_update_result(dict(state='complete', version='9.8.7'))
                    else:
                        window.home.update_failed(state)
                    self.app.processEvents()
                    with self.subTest(size=(width, height), language=language, state=state):
                        self.assertEqual(window.home.scroll.horizontalScrollBar().maximum(), 0)
                        label = window.home.update_status if window.home.updating else window.home.update_notice
                        self.assertFalse(label.isHidden())
                        self.assertGreater(label.height(), 0)
                        if state in ('download', 'prepare', 'ready'):
                            self.assertFalse(window.home.update_controls.isHidden())
                            panel = window.home.update_panel
                            center = panel.mapTo(window.home.pages, panel.rect().center())
                            target = window.home.pages.rect().center()
                            self.assertLessEqual(abs(center.x() - target.x()), 2)
                            self.assertLessEqual(abs(center.y() - target.y()), 2)
                            self.assertTrue(window.rect().contains(panel.mapTo(window, panel.rect().bottomRight())))
                            self.assertEqual((window.width(), window.height()), (width, height))
                            self.assertEqual(window.home.update_cancel.isVisible(), state == 'download')
                        # Exact catalog lookup, including the dynamically rendered message.
                        if state == 'download':
                            self.assertEqual(label.text(), translate('Téléchargement de la mise à jour…', language))
        window.home.installer.state = 'idle'
