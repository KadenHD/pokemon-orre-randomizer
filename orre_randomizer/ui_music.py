"""Independent native PCM music channel; filenames are opened by Python, not MCI."""
from __future__ import annotations
import ctypes
from pathlib import Path
import sys
import wave
from PySide6.QtCore import QObject, QTimer, Signal


class _WaveFormat(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("tag", ctypes.c_uint16), ("channels", ctypes.c_uint16),
                ("rate", ctypes.c_uint32), ("bytes_per_second", ctypes.c_uint32),
                ("alignment", ctypes.c_uint16), ("bits", ctypes.c_uint16),
                ("extra", ctypes.c_uint16)]


class _WaveHeader(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("length", ctypes.c_uint32),
                ("recorded", ctypes.c_uint32), ("user", ctypes.c_size_t),
                ("flags", ctypes.c_uint32), ("loops", ctypes.c_uint32),
                ("next", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


class NativeMusic:
    """WaveOut owns a separate output channel and loops one prepared PCM buffer.

    https://learn.microsoft.com/windows/win32/api/mmeapi/nf-mmeapi-waveoutwrite
    Buffer and header remain alive until reset, unprepare and close complete.
    No system or hardware volume setting is changed.
    """
    def __init__(self):
        self.library = ctypes.WinDLL("winmm")
        self.device = ctypes.c_void_p()
        self.header = self.buffer = None
        self.library.waveOutOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint,
            ctypes.POINTER(_WaveFormat), ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
        for name in ("waveOutPrepareHeader", "waveOutWrite", "waveOutUnprepareHeader"):
            getattr(self.library, name).argtypes = [ctypes.c_void_p, ctypes.POINTER(_WaveHeader), ctypes.c_uint]
        for name in ("waveOutReset", "waveOutClose"):
            getattr(self.library, name).argtypes = [ctypes.c_void_p]
        for name in ("waveOutOpen", "waveOutPrepareHeader", "waveOutWrite",
                     "waveOutUnprepareHeader", "waveOutReset", "waveOutClose"):
            getattr(self.library, name).restype = ctypes.c_uint

    @staticmethod
    def check(result):
        if result:
            raise OSError(f"Audio output returned {result}")

    def open_file(self, path):
        self.close()
        with wave.open(str(path), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (2, 2, 44100, "NONE"):
                raise ValueError("Music must be stereo PCM16 at 44100 Hz")
            frames = source.getnframes()
            if not 0 < frames <= 44100 * 180:
                raise ValueError("Music exceeds playback bounds")
            pcm = source.readframes(frames)
            if len(pcm) != frames * 4:
                raise ValueError("Truncated music")
        self.buffer = ctypes.create_string_buffer(pcm)
        # WHDR_BEGINLOOP | WHDR_ENDLOOP, with both ends on this single buffer.
        self.header = _WaveHeader(ctypes.addressof(self.buffer), len(pcm), 0, 0, 0x0C, 0xFFFFFFFF, None, 0)
        format_ = _WaveFormat(1, 2, 44100, 176400, 4, 16, 0)
        self.check(self.library.waveOutOpen(ctypes.byref(self.device), 0xFFFFFFFF,
                                         ctypes.byref(format_), 0, 0, 0))
        try:
            self.check(self.library.waveOutPrepareHeader(self.device, ctypes.byref(self.header), ctypes.sizeof(self.header)))
        except OSError:
            self.close()
            raise

    def play(self):
        self.check(self.library.waveOutWrite(self.device, ctypes.byref(self.header), ctypes.sizeof(self.header)))

    def is_playing(self):
        return bool(self.device.value and self.header is not None and not self.header.flags & 1)

    def close(self):
        if self.device.value:
            self.check(self.library.waveOutReset(self.device))
            if self.header is not None and self.header.flags & 2:
                self.check(self.library.waveOutUnprepareHeader(self.device, ctypes.byref(self.header), ctypes.sizeof(self.header)))
            self.check(self.library.waveOutClose(self.device))
        self.device = ctypes.c_void_p()
        self.header = self.buffer = None


class MenuMusic(QObject):
    failed = Signal()

    def __init__(self, parent, path: Path | None, backend=None):
        super().__init__(parent)
        self.path = path
        self.backend = backend
        if backend is None and sys.platform == "win32":
            try:
                self.backend = NativeMusic()
            except OSError:
                pass
        self.opened = self.playing = False
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.poll)

    @property
    def supported(self):
        return self.backend is not None and self.path is not None

    def start(self):
        if not self.supported:
            return False
        try:
            if not self.opened:
                self.backend.open_file(self.path)
                self.opened = True
            self.backend.play()
            self.playing = True
            self.timer.start()
            return True
        except (OSError, ValueError, wave.Error, EOFError):
            self.stop()
            return False

    def poll(self):
        if self.playing and not self.backend.is_playing():
            self.stop()
            self.failed.emit()

    def stop(self):
        self.timer.stop()
        self.playing = False
        try:
            self.backend.close() if self.backend is not None else None
        except OSError:
            pass
        self.opened = False
