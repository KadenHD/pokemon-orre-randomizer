"""Read-only inheritance of the owned Dolphin's Windows audio-session gain.

No volume setter is used. The companion only attenuates its PCM with its
Dolphin child's session volume/mute. Its own Windows preference is preserved.
"""
from __future__ import annotations
import ctypes as C
from math import isfinite
import subprocess
import time

from .native_music_endpoint import _Guid, _guid, _method

# Common attenuation for both Dolphin and the companion. It preserves their
# ratio and reserves headroom when independently timed music and effects overlap.
NATIVE_MUSIC_OUTPUT_GAIN = .5


class AudioSessionPending(OSError):
    pass


def session_gains(records):
    """Require exactly one attributable session; never pick an arbitrary one."""
    if not records:
        raise AudioSessionPending('Owned Dolphin audio session is not ready')
    if len(records) != 1 or not records[0].get('single_process'):
        raise ValueError('Owned Dolphin audio sessions are ambiguous; native audio restored')
    row = records[0]
    channels, master = row['channels'], row['master']
    if (not 1 <= len(channels) <= 32 or any(not isfinite(value) or not 0 <= value <= 1 for value in (master, *channels))
            or type(row['muted']) is not bool):
        raise ValueError('Owned Dolphin audio-session gain is invalid')
    if row['muted']:
        return 0., 0.
    # Windows channel order starts with front-left/front-right. Mono session
    # gain applies to both stereo source channels before endpoint conversion.
    return master * channels[0], master * channels[1 if len(channels) > 1 else 0]


class DolphinSessionVolume:
    def __init__(self, process, endpoint):
        if not isinstance(process, subprocess.Popen) or process.poll() is not None:
            raise ValueError('Audio gain requires the live Dolphin child owned by this launcher')
        if not isinstance(endpoint, str) or not endpoint or len(endpoint) > 32768:
            raise ValueError('Audio gain requires the verified output endpoint')
        self.process, self.pid, self.endpoint = process, process.pid, endpoint
        self.ole = C.WinDLL('ole32')
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetProcessId.argtypes = [C.c_void_p]; self.kernel.GetProcessId.restype = C.c_uint32
        self.kernel.GetProcessTimes.argtypes = [C.c_void_p] + [C.POINTER(C.c_uint64)] * 4
        self.kernel.GetProcessTimes.restype = C.c_int
        self.ole.CoInitializeEx.argtypes = [C.c_void_p, C.c_uint32]; self.ole.CoInitializeEx.restype = C.c_int32
        self.ole.CoCreateInstance.argtypes = [C.POINTER(_Guid), C.c_void_p, C.c_uint32, C.POINTER(_Guid), C.POINTER(C.c_void_p)]
        self.ole.CoCreateInstance.restype = C.c_int32
        self.ole.CoUninitialize.argtypes = []; self.ole.CoUninitialize.restype = None
        self.enumerator, self.device, self.manager = (C.c_void_p() for _ in range(3))
        self.initialized = False; self.cached = None; self.read_at = 0.
        try:
            self.creation = self._creation()
            hr = self.ole.CoInitializeEx(None, 0)
            self.initialized = hr in (0, 1)
            if hr < 0 and hr != -2147417850:
                self._check(hr)
            cls = _guid('BCDE0395-E52F-467C-8E3D-C4579291692E')
            iid = _guid('A95664D2-9614-4F35-A746-DE8DB63617E6')
            self._check(self.ole.CoCreateInstance(C.byref(cls), None, 1, C.byref(iid), C.byref(self.enumerator)))
            self._check(_method(self.enumerator, 5, C.c_int32, C.c_wchar_p, C.POINTER(C.c_void_p))(
                self.enumerator, endpoint, C.byref(self.device)))
            iid = _guid('77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F')
            self._check(_method(self.device, 3, C.c_int32, C.POINTER(_Guid), C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p))(
                self.device, C.byref(iid), 23, None, C.byref(self.manager)))
        except BaseException:
            self.close(); raise

    @staticmethod
    def _check(hr):
        if hr < 0:
            raise OSError('Cannot read owned Dolphin audio-session gain: ' + hex(hr & 0xffffffff))

    @staticmethod
    def _release(pointer):
        if pointer.value:
            _method(pointer, 2, C.c_uint32)(pointer); pointer.value = None

    def _creation(self):
        handle = C.c_void_p(int(self.process._handle))
        values = [C.c_uint64() for _ in range(4)]
        if self.kernel.GetProcessId(handle) != self.pid or not self.kernel.GetProcessTimes(handle, *(C.byref(value) for value in values)):
            raise OSError('Owned Dolphin process identity differs')
        return values[0].value

    def sample(self):
        if self.process.poll() is not None or self._creation() != self.creation:
            raise OSError('Owned Dolphin process ended or changed')
        now = time.monotonic()
        if self.cached is not None and now-self.read_at < .1:
            return self.cached
        sessions = C.c_void_p(); records = []
        try:
            self._check(_method(self.manager, 5, C.c_int32, C.POINTER(C.c_void_p))(self.manager, C.byref(sessions)))
            count = C.c_int()
            self._check(_method(sessions, 3, C.c_int32, C.POINTER(C.c_int))(sessions, C.byref(count)))
            if not 0 <= count.value <= 256:
                raise ValueError('Audio-session count exceeds bounds')
            for index in range(count.value):
                control, identity, volume, channels = (C.c_void_p() for _ in range(4))
                try:
                    self._check(_method(sessions, 4, C.c_int32, C.c_int, C.POINTER(C.c_void_p))(sessions, index, C.byref(control)))
                    iid = _guid('BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D')
                    self._check(_method(control, 0, C.c_int32, C.POINTER(_Guid), C.POINTER(C.c_void_p))(control, C.byref(iid), C.byref(identity)))
                    owner = C.c_uint32()
                    hr = _method(identity, 14, C.c_int32, C.POINTER(C.c_uint32))(identity, C.byref(owner))
                    self._check(hr)
                    if owner.value != self.pid:
                        continue
                    if hr != 0:
                        raise ValueError('Dolphin audio session spans other processes; native audio restored')
                    state = C.c_int()
                    self._check(_method(control, 3, C.c_int32, C.POINTER(C.c_int))(control, C.byref(state)))
                    if state.value == 2:  # AudioSessionStateExpired
                        continue
                    iid = _guid('87CE5498-68D6-44E5-9215-6DA47EF883D8')
                    self._check(_method(control, 0, C.c_int32, C.POINTER(_Guid), C.POINTER(C.c_void_p))(control, C.byref(iid), C.byref(volume)))
                    master, muted = C.c_float(), C.c_int()
                    self._check(_method(volume, 4, C.c_int32, C.POINTER(C.c_float))(volume, C.byref(master)))
                    self._check(_method(volume, 6, C.c_int32, C.POINTER(C.c_int))(volume, C.byref(muted)))
                    iid = _guid('1C158861-B533-4B30-B1CF-E853E51C59B8')
                    self._check(_method(control, 0, C.c_int32, C.POINTER(_Guid), C.POINTER(C.c_void_p))(control, C.byref(iid), C.byref(channels)))
                    size = C.c_uint32()
                    self._check(_method(channels, 3, C.c_int32, C.POINTER(C.c_uint32))(channels, C.byref(size)))
                    if not 1 <= size.value <= 32:
                        raise ValueError('Dolphin session channel count exceeds bounds')
                    values = []
                    for channel in range(size.value):
                        value = C.c_float()
                        self._check(_method(channels, 5, C.c_int32, C.c_uint32, C.POINTER(C.c_float))(channels, channel, C.byref(value)))
                        values.append(value.value)
                    records.append({'single_process':True,'master':master.value,'muted':bool(muted.value),'channels':values})
                finally:
                    for pointer in (channels, volume, identity, control):
                        self._release(pointer)
        finally:
            self._release(sessions)
        self.cached = session_gains(records); self.read_at = now
        return self.cached

    def close(self):
        for pointer in (self.manager, self.device, self.enumerator):
            self._release(pointer)
        if self.initialized:
            self.ole.CoUninitialize(); self.initialized = False
