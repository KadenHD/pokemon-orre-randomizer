"""Bounded PCM16 WaveOut queue; no process hooks, global volume or Qt dependency."""
from __future__ import annotations

import ctypes as C
import sys


class _Format(C.Structure):
    _pack_ = 1
    _fields_ = [("tag", C.c_uint16), ("channels", C.c_uint16), ("rate", C.c_uint32),
                ("bytes_per_second", C.c_uint32), ("alignment", C.c_uint16),
                ("bits", C.c_uint16), ("extra", C.c_uint16)]


class _Header(C.Structure):
    _fields_ = [("data", C.c_void_p), ("length", C.c_uint32), ("recorded", C.c_uint32),
                ("user", C.c_size_t), ("flags", C.c_uint32), ("loops", C.c_uint32),
                ("next", C.c_void_p), ("reserved", C.c_size_t)]


class WaveOutStream:
    """Four 20ms blocks by default; the output consumer drives rendering.

    Every prepared header and its data stay alive until reset/unprepare/close
    complete. A full queue refuses more data instead of growing without bound.
    ``clear`` discards queued music when a movie or pause is observed.
    """

    def __init__(self, *, rate=32000, frames=640, blocks=4, library=None):
        if not 8000 <= rate <= 96000 or not 1 <= frames <= rate or not 2 <= blocks <= 16:
            raise ValueError("Invalid PCM output queue bounds")
        if library is None and sys.platform != "win32":
            raise OSError("Native gameplay music output requires Windows")
        self.library = library or C.WinDLL("winmm")
        self.endpoint_id = None
        device_id = 0xffffffff
        if library is None:
            from .native_music_endpoint import matching_waveout_device
            device_id, self.endpoint_id = matching_waveout_device(self.library)
        self.rate, self.frames = rate, frames
        self.device = C.c_void_p()
        self.slots = []
        self.submitted_frames = 0
        self.completed_frames = 0
        self._configure()
        format_ = _Format(1, 2, rate, rate * 4, 4, 16, 0)
        self.check(self.library.waveOutOpen(C.byref(self.device), device_id, C.byref(format_), 0, 0, 0))
        try:
            if self.endpoint_id is not None:
                from .native_music_endpoint import waveout_endpoint
                self.library.waveOutGetID.argtypes = [C.c_void_p, C.POINTER(C.c_uint32)]
                self.library.waveOutGetID.restype = C.c_uint32
                actual_id = C.c_uint32()
                self.check(self.library.waveOutGetID(self.device, C.byref(actual_id)))
                actual_endpoint = waveout_endpoint(self.library, actual_id.value)
                if not actual_endpoint or actual_endpoint.casefold() != self.endpoint_id.casefold():
                    raise OSError('Windows routed gameplay music to another output; native audio restored')
            for _ in range(blocks):
                buffer = C.create_string_buffer(frames * 4)
                header = _Header(C.addressof(buffer), frames * 4, 0, 0, 0, 0, None, 0)
                slot = {"buffer": buffer, "header": header, "queued": False, "prepared": False}
                self.slots.append(slot)
                self.check(self.library.waveOutPrepareHeader(self.device, C.byref(header), C.sizeof(header)))
                slot["prepared"] = True
        except BaseException:
            self.close()
            raise

    def _configure(self):
        self.library.waveOutOpen.argtypes = [C.POINTER(C.c_void_p), C.c_uint, C.POINTER(_Format), C.c_size_t, C.c_size_t, C.c_uint]
        for name in ("waveOutPrepareHeader", "waveOutWrite", "waveOutUnprepareHeader"):
            getattr(self.library, name).argtypes = [C.c_void_p, C.POINTER(_Header), C.c_uint]
        for name in ("waveOutReset", "waveOutClose"):
            getattr(self.library, name).argtypes = [C.c_void_p]
        for name in ("waveOutOpen", "waveOutPrepareHeader", "waveOutWrite", "waveOutUnprepareHeader", "waveOutReset", "waveOutClose"):
            getattr(self.library, name).restype = C.c_uint

    @staticmethod
    def check(result):
        if result:
            raise OSError(f"Gameplay music output returned {result}")

    def poll(self):
        for slot in self.slots:
            if slot["queued"] and slot["header"].flags & 1:  # WHDR_DONE
                slot["queued"] = False
                self.completed_frames += self.frames
        return sum(not slot["queued"] for slot in self.slots)

    def matches_default_endpoint(self):
        if self.endpoint_id is None:
            return True
        from .native_music_endpoint import default_console_endpoint
        return default_console_endpoint().casefold() == self.endpoint_id.casefold()

    def submit(self, pcm: bytes):
        if len(pcm) != self.frames * 4:
            raise ValueError("Gameplay music PCM block size differs")
        if not self.device.value:
            raise OSError("Gameplay music output is closed")
        self.poll()
        slot = next((slot for slot in self.slots if not slot["queued"]), None)
        if slot is None:
            return False
        C.memmove(slot["buffer"], pcm, len(pcm))
        self.check(self.library.waveOutWrite(self.device, C.byref(slot["header"]), C.sizeof(_Header)))
        slot["queued"] = True
        self.submitted_frames += self.frames
        return True

    def clear(self):
        if self.device.value:
            self.check(self.library.waveOutReset(self.device))
            for slot in self.slots:
                slot["queued"] = False

    def close(self):
        if self.device.value:
            self.clear()
            for slot in self.slots:
                if slot["prepared"]:
                    self.check(self.library.waveOutUnprepareHeader(self.device, C.byref(slot["header"]), C.sizeof(_Header)))
                    slot["prepared"] = False
            self.check(self.library.waveOutClose(self.device))
            self.device = C.c_void_p()
            self.slots.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
