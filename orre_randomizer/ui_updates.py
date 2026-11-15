"""One bounded, asynchronous GitHub check per application session."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .update_service import LATEST_RELEASE_API, allowed_download, release_update
from .update_apply import start_helper, update_kind


class UpdateChecker(QObject):
    available = Signal(object)
    TIMEOUT_MS = 8000
    MAX_BYTES = 256 * 1024

    def __init__(self, current_version, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.manager = QNetworkAccessManager(self)
        self.reply = None
        self.started = self.closed = self.cancelled = False
        self.buffer = bytearray()
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.cancel)

    def check_once(self):
        if self.started or self.closed:
            return
        self.started = True
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"OrreRandomizer-release-check")
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setTransferTimeout(self.TIMEOUT_MS)
        self.reply = self.manager.get(request)
        self.reply.setReadBufferSize(self.MAX_BYTES + 1)
        self.reply.readyRead.connect(self.read)
        self.reply.finished.connect(self.finished)
        self.timeout.start(self.TIMEOUT_MS)

    def read(self):
        if self.reply is None:
            return
        self.buffer.extend(bytes(self.reply.read(self.MAX_BYTES + 1 - len(self.buffer))))
        if len(self.buffer) > self.MAX_BYTES:
            self.cancel()

    def finished(self):
        reply = self.reply
        if reply is None:
            return
        self.timeout.stop()
        self.read()
        self.reply = None
        try:
            if (not self.closed and not self.cancelled and reply.error() == QNetworkReply.NetworkError.NoError
                    and reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 200
                    and len(self.buffer) <= self.MAX_BYTES):
                update = release_update(json.loads(self.buffer), self.current_version, update_kind())
                if update is not None:
                    self.available.emit(update)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            pass  # Optional checks never interrupt the offline randomizer.
        finally:
            self.buffer.clear()
            reply.deleteLater()

    def cancel(self):
        self.cancelled = True
        self.timeout.stop()
        if self.reply is not None and self.reply.isRunning():
            self.reply.abort()

    def close(self):
        self.closed = True
        self.cancel()


class UpdateInstaller(QObject):
    """Stream a bounded package, then hand off to an isolated Windows process."""
    progress = Signal(int)
    state_changed = Signal(str)
    failed = Signal(str)
    ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.reply = self.process = self.file = self.work = None
        self.state = "idle"
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self.fail("network"))
        self.poll = QTimer(self)
        self.poll.setInterval(100)
        self.poll.timeout.connect(self.poll_helper)

    def start(self, update):
        if self.state in ("download", "prepare", "ready"):
            return
        if not allowed_download(update):
            self.fail("checksum")
            return
        self.process = None
        self.update = update
        try:
            self.work = Path(tempfile.mkdtemp(prefix="orre-update-"))
            self.package = self.work / ("package.exe" if update.kind == "installer" else "package.zip")
            self.file = self.package.open("xb")
        except OSError:
            self.fail("disk")
            return
        self.received, self.redirects, self.digest = 0, 0, hashlib.sha256()
        self.state = "download"
        self.state_changed.emit(self.state)
        self.progress.emit(0)
        self.timeout.start(10 * 60 * 1000)
        self.request(update.download_url)

    def request(self, url):
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"OrreRandomizer-update")
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setTransferTimeout(30000)
        reply = self.manager.get(request)
        self.reply = reply
        reply.setReadBufferSize(256 * 1024)
        reply.readyRead.connect(lambda: self.read(reply))
        reply.finished.connect(lambda: self.finished(reply))

    def read(self, reply):
        if self.reply is not reply or self.state != "download":
            return
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status != 200:
            return
        try:
            while reply.bytesAvailable():
                data = bytes(reply.read(64 * 1024))
                if not data:
                    break
                self.received += len(data)
                if self.received > self.update.size:
                    self.fail("checksum")
                    return
                self.file.write(data)
                self.digest.update(data)
            self.progress.emit(self.received * 100 // self.update.size)
        except OSError:
            self.fail("disk")

    def finished(self, reply):
        if self.reply is not reply:
            return
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.fail("network")
            return
        if status in (301, 302, 303, 307, 308):
            target = reply.url().resolved(reply.attribute(QNetworkRequest.Attribute.RedirectionTargetAttribute))
            try:
                parsed = urlsplit(target.toString())
            except ValueError:
                self.fail("network")
                return
            if (self.redirects >= 5 or parsed.scheme != "https" or parsed.username or parsed.password
                    or parsed.netloc not in ("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com")):
                self.fail("network")
                return
            self.redirects += 1
            self.reply = None
            reply.deleteLater()
            self.request(target.toString())
            return
        if status != 200:
            self.fail("network")
            return
        self.read(reply)
        if self.reply is not reply:
            return
        self.reply = None
        reply.deleteLater()
        self.timeout.stop()
        try:
            self.file.close()
            self.file = None
        except OSError:
            self.fail("disk")
            return
        if self.received != self.update.size or self.digest.hexdigest() != self.update.sha256:
            self.fail("checksum")
            return
        self.state = "prepare"
        self.state_changed.emit(self.state)
        try:
            self.process = start_helper(self.package, self.update, self.work)
        except OSError:
            self.fail("disk")
            return
        self.poll.start()
        self.timeout.start(5 * 60 * 1000)

    def poll_helper(self):
        if self.work is None:
            return
        status = self.work / "status.json"
        try:
            if status.is_file() and status.stat().st_size < 1024:
                payload = json.loads(status.read_text("utf-8-sig"))
                if payload.get("state") == "error":
                    self.fail(payload.get("code", "update_failed"))
                    return
                if payload.get("state") == "ready":
                    self.poll.stop()
                    self.timeout.stop()
                    self.state = "ready"
                    self.state_changed.emit(self.state)
                    self.ready.emit()
                    return
        except (OSError, ValueError):
            pass  # The helper atomically replaces a tiny status file.
        if self.process is not None and self.process.poll() is not None:
            self.fail("update_failed")

    def fail(self, reason):
        self.close()
        self.state = "error"
        self.failed.emit(reason)

    def cancel(self):
        self.close()
        self.state = "idle"
        self.state_changed.emit(self.state)

    def close(self):
        if self.state == "ready":
            return  # The verified helper now owns the job and waits for our exit.
        self.timeout.stop()
        self.poll.stop()
        reply, self.reply = self.reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()
        if self.file is not None:
            try:
                self.file.close()
            except OSError:
                pass
            self.file = None
        if self.work is not None:
            if self.process is not None and self.process.poll() is None:
                (self.work / "cancel").touch()
                # Do not wait in Qt; the helper removes its private staging files.
            else:
                shutil.rmtree(self.work, ignore_errors=True)
            self.work = None
