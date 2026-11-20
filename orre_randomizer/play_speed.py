"""Foreground-scoped speed holds for one launcher-owned Dolphin child.

Stock Dolphin exposes ten-percent speed steps, not an external fixed-speed
command. A dedicated loopback DSU device emits bounded press/release pulses.
Release cancels the current ramp and returns to normal speed. Focus
loss pauses this profile; restoration takes priority when focus returns. Native
keyboard hotkeys retain their own device and bindings. UDP has no acknowledgement: the
tracked speed is an estimate, and a stalled emulator can miss a pulse. Starting
a new session always starts at 100%. The selected 100/200/300% value is only
the acceleration target. Ctrl+Tab latches that target until pressed again.
"""
from __future__ import annotations

import configparser
import ctypes
from dataclasses import dataclass, field
from pathlib import Path
import socket
import struct
import sys
import threading
import time
import zlib


DEVICE_NAME = "OrreSpeed"
DEVICE = f"DSUClient/0/{DEVICE_NAME}"
_SERVER_ID = 0x4F525350
_PROTOCOL = 1001
_PRESS_SECONDS = 0.06
_RELEASE_SECONDS = 0.06
_CLIENT_TIMEOUT = 3.0
_CLOSE_TIMEOUT = 3.0
_INCREASE = 4  # DSU R3, button byte one
_DECREASE = 1  # DSU Share
_PAD_INFO = b"\x00\x02\x02\x01ORRESP\x05"


def _native_windows_hotkeys():
    """Seed stock defaults only for a profile with no Hotkeys.ini yet.

    A partial Hotkeys.ini bypasses Dolphin's LoadDefaults, so the stock Windows
    bindings must be present before adding our fully qualified DSU expressions.
    Existing profiles are never filled or reset from this table.
    """
    values = {
        "Device": "DInput/0/Keyboard Mouse",
        "General/Open": "@(Ctrl+O)", "General/Toggle Pause": "F10",
        "General/Stop": "ESCAPE", "General/Toggle Fullscreen": "@(Alt+RETURN)",
        "General/Open Achievements": "@(Alt+A)", "General/Take Screenshot": "F9",
        "Stepping/Step Into": "F11", "Stepping/Step Over": "@(Shift+F10)",
        "Stepping/Step Out": "@(Shift+F11)", "Breakpoint/Toggle Breakpoint": "@(Shift+F9)",
        "Other State Hotkeys/Undo Load State": "F12",
        "Other State Hotkeys/Undo Save State": "@(Shift+F12)",
        "GBA Core/Load ROM": "@(`Ctrl`+`Shift`+`O`)",
        "GBA Core/Unload ROM": "@(`Ctrl`+`Shift`+`W`)",
        "GBA Core/Reset": "@(`Ctrl`+`Shift`+`R`)",
        "GBA Volume/Volume Down": "`SUBTRACT`", "GBA Volume/Volume Up": "`ADD`",
        "GBA Volume/Volume Toggle Mute": "`M`",
        "USB Emulation Devices/Show Skylanders Portal": "@(Ctrl+P)",
        "USB Emulation Devices/Show Infinity Base": "@(Ctrl+I)",
    }
    for index in range(1, 9):
        values[f"Load State/Load State Slot {index}"] = f"F{index}"
        values[f"Save State/Save State Slot {index}"] = f"@(Shift+F{index})"
    for index in range(1, 5):
        values[f"Wii/Connect Wii Remote {index}"] = f"@(Alt+F{index + 4})"
        values[f"GBA Window Size/{index}x"] = f"`NUMPAD{index}`"
    values["Wii/Connect Balance Board"] = "@(Alt+F9)"
    return values


@dataclass(frozen=True)
class SpeedBindings:
    """Windows virtual-key chords; modifier chords take priority over plain Tab."""
    fast: tuple[int, ...] = (0x09,)
    slow: tuple[int, ...] = (0x10, 0x09)
    toggle: tuple[int, ...] = (0x11, 0x09)

    def __post_init__(self):
        chords = (self.fast, self.slow, self.toggle)
        for chord in chords:
            if (not isinstance(chord, tuple) or not 1 <= len(chord) <= 3
                    or any(type(key) is not int or not 1 <= key <= 0xFE for key in chord)
                    or len(set(chord)) != len(chord)):
                raise ValueError("speed bindings require one to three distinct Windows virtual keys")
        if len({frozenset(chord) for chord in chords}) != len(chords):
            raise ValueError("speed bindings must differ")


def _write_ini(path, values):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    if path.is_file():
        parser.read(path, encoding="utf-8")
    for section, entries in values.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for name, value in entries.items():
            parser.set(section, name, str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".speed-tmp")
    with pending.open("w", encoding="utf-8") as stream:
        parser.write(stream)
    pending.replace(path)


def _packet(kind, data):
    body = struct.pack("<I", kind) + data
    packet = bytearray(struct.pack("<4sHHII", b"DSUS", _PROTOCOL, len(body), 0, _SERVER_ID) + body)
    struct.pack_into("<I", packet, 8, zlib.crc32(packet))
    return bytes(packet)


def _request_kind(data):
    if len(data) < 20 or len(data) > 128 or data[:4] != b"DSUC":
        return None
    version, size, expected = struct.unpack_from("<HHI", data, 4)
    if version != _PROTOCOL or size != len(data) - 16:
        return None
    checked = bytearray(data)
    checked[8:12] = bytes(4)
    if zlib.crc32(checked) != expected:
        return None
    kind = struct.unpack_from("<I", data, 16)[0]
    if kind == 0x100000 and len(data) == 20:
        return kind
    if kind == 0x100001 and len(data) >= 24:
        count = struct.unpack_from("<I", data, 20)[0]
        return kind if (1 <= count <= 4 and len(data) in (24 + count, 28)
                        and all(index < 4 for index in data[24:24 + count])) else None
    if kind == 0x100002 and len(data) == 28:
        return kind
    return None


class _SpeedPad:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("127.0.0.1", 0))
            self.socket.setblocking(False)
        except BaseException:
            self.socket.close()
            raise
        self.port = self.socket.getsockname()[1]
        self.clients = {}
        self.counter, self.next_send = 0, 0.0
        self.sent_packets = 0

    def step(self, now, button=0, *, send=True):
        for _ in range(32):
            try:
                data, endpoint = self.socket.recvfrom(256)
            except BlockingIOError:
                break
            if endpoint[0] != "127.0.0.1":
                continue
            kind = _request_kind(data)
            if kind == 0x100000:
                self.socket.sendto(_packet(kind, struct.pack("<H2x", _PROTOCOL)), endpoint)
            elif kind == 0x100001:
                # This server owns pad zero only. Other requested pads are absent.
                count = struct.unpack_from("<I", data, 20)[0]
                for index in data[24:24 + count]:
                    info = _PAD_INFO if index == 0 else bytes([index]) + bytes(10)
                    self.socket.sendto(_packet(kind, info + b"\0"), endpoint)
            elif kind == 0x100002:
                flags, pad = data[20:22]
                mac = data[22:28]
                matches = flags == 0 or (flags & 1 and pad == 0) or (flags & 2 and mac == _PAD_INFO[4:10])
                if flags <= 3 and matches and (endpoint in self.clients or len(self.clients) < 4):
                    self.clients[endpoint] = now
        self.clients = {endpoint: last for endpoint, last in self.clients.items() if now - last < _CLIENT_TIMEOUT}
        if not send or now < self.next_send:
            return
        self.next_send = now + 0.008
        payload = _PAD_INFO + struct.pack("<BIBBBB4B8B", 1, self.counter, button, 0, 0, 0,
                                          128, 128, 128, 128, *([0] * 8)) + bytes(48)
        self.counter = (self.counter + 1) & 0xFFFFFFFF
        packet = _packet(0x100002, payload)
        for endpoint in list(self.clients):
            try:
                self.socket.sendto(packet, endpoint)
                self.sent_packets += 1
            except OSError:
                self.clients.pop(endpoint, None)

    def close(self):
        self.socket.close()


@dataclass
class SpeedControls:
    enabled: bool
    reason: str = ""
    port: int | None = None
    device: str = DEVICE
    _pad: _SpeedPad | None = field(default=None, repr=False)
    _claimed: bool = field(default=False, repr=False)

    def close(self):
        if self._pad is not None:
            self._pad.close()
            self._pad = None


def prepare_speed_controls(profile: Path) -> SpeedControls:
    """Configure an isolated profile before spawn and reserve its speed socket.

    Game pads, the native hotkey device and unrelated shortcuts are preserved.
    Speed expressions explicitly select their separate DSU device. This profile
    pauses on focus loss; pending restoration runs first when focus returns.
    """
    if sys.platform != "win32":
        return SpeedControls(False, "foreground speed holds are supported on Windows only")
    profile = Path(profile)
    if profile.is_symlink() or profile.is_junction():
        raise ValueError("speed controls require an independent launcher profile")
    config = profile / "Config"
    for path in (config, config / "DSUClient.ini", config / "Hotkeys.ini", config / "Dolphin.ini"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("speed controls cannot write linked profile configuration")
    pad = _SpeedPad()
    try:
        ini = configparser.ConfigParser(interpolation=None)
        ini.optionxform = str
        ini.read(config / "DSUClient.ini", encoding="utf-8")
        old = ini.get("Server", "Entries", fallback="")
        entries = [entry for entry in old.split(";") if entry and not entry.startswith(DEVICE_NAME + ":")]
        entries.append(f"{DEVICE_NAME}:127.0.0.1:{pad.port}")
        _write_ini(config / "DSUClient.ini", {"Server": {"Enabled": "True", "Entries": ";".join(entries) + ";"}})
        hotkeys = {} if (config / "Hotkeys.ini").exists() else _native_windows_hotkeys()
        hotkeys.update({
            "Emulation Speed/Increase Emulation Speed": f"`{DEVICE}:R3`",
            "Emulation Speed/Decrease Emulation Speed": f"`{DEVICE}:Share`",
            "Emulation Speed/Disable Emulation Speed Limit": "",
        })
        _write_ini(config / "Hotkeys.ini", {"Hotkeys": hotkeys})
        _write_ini(config / "Dolphin.ini", {"General": {"HotkeysRequireFocus": "True"},
                                           "Interface": {"PauseOnFocusLost": "True",
                                                         "OnScreenDisplayMessages": "False"}})
    except BaseException:
        pad.close()
        raise
    return SpeedControls(True, port=pad.port, _pad=pad)


class _ForegroundKeys:
    def __init__(self, pid, bindings):
        from ctypes import wintypes
        self.pid, self.bindings = pid, bindings
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user.GetAsyncKeyState.restype = ctypes.c_short

    def focused(self):
        window = self.user.GetForegroundWindow()
        owner = ctypes.c_ulong()
        return bool(window and self.user.GetWindowThreadProcessId(window, ctypes.byref(owner)) and owner.value == self.pid)

    def __call__(self):
        if not self.focused():
            return None
        # Never read any key state before the foreground ownership check.
        keys = set(self.bindings.fast) | set(self.bindings.slow) | set(self.bindings.toggle)
        down = {key for key in keys if self.user.GetAsyncKeyState(key) & 0x8000}
        # Do not interpret a modifier released before Tab as a fresh fast hold.
        if getattr(self, "_chord_down", False):
            if not down:
                self._chord_down = False
            elif not (all(key in down for key in self.bindings.toggle)
                      or all(key in down for key in self.bindings.slow)):
                return "release"
        if all(key in down for key in self.bindings.toggle):
            self._chord_down = True
            return "toggle"
        if all(key in down for key in self.bindings.slow):
            self._chord_down = True
            return "slow"
        if all(key in down for key in self.bindings.fast):
            return "fast"
        return None


class _Ramp:
    def __init__(self, base_ticks):
        self.current = self.base = base_ticks
        self.button, self.until = 0, 0.0

    def step(self, now, target, connected):
        if now < self.until:
            return self.button
        if self.button:
            self.button = 0
            self.until = now + _RELEASE_SECONDS
            return 0
        if connected and self.current != target:
            direction = 1 if target > self.current else -1
            self.current += direction
            self.button = _INCREASE if direction == 1 else _DECREASE
            self.until = now + _PRESS_SECONDS
        return self.button

    @property
    def restored(self):
        return self.current == self.base and not self.button


class _Holds:
    """Defer all non-neutral inputs while background and restore first on return."""
    def __init__(self, ramp, acceleration=20):
        self.ramp = ramp
        self.acceleration = acceleration
        self.toggled = False
        self.toggle_down = False
        self.was_focused = False
        self.pending_restore = False

    def step(self, now, mode, focused, connected, stopping=False):
        if not focused:
            if self.was_focused:
                self.pending_restore = True
            self.was_focused = False
            self.toggled = self.toggle_down = False
            self.ramp.button = 0
            self.ramp.until = now + _RELEASE_SECONDS
            return 0
        if not self.was_focused:
            self.pending_restore = True
            self.ramp.button = 0
            self.ramp.until = now + _RELEASE_SECONDS
        self.was_focused = True
        restore = stopping or self.pending_restore
        if not restore and mode == "toggle" and not self.toggle_down:
            self.toggled = not self.toggled
        self.toggle_down = mode == "toggle"
        target = (self.ramp.base if restore else 5 if mode == "slow" else
                  self.acceleration if mode == "fast" or self.toggled else self.ramp.base)
        button = self.ramp.step(now, target, connected)
        if self.pending_restore and self.ramp.restored and now >= self.ramp.until:
            self.pending_restore = False
        return button


class SpeedSession:
    """Own the prepared DSU device for a supplied, launcher-spawned process.

    Call start() after Popen and close() before replacing the selected target or
    leaving the launcher. close() returns whether restoration was completed or
    the child had already exited. Abrupt parent termination cannot be repaired
    by stock Dolphin's one-shot speed API.
    """
    def __init__(self, process, acceleration_speed, controls: SpeedControls, *,
                 bindings: SpeedBindings | None = None, key_reader=None, foreground_reader=None):
        if type(acceleration_speed) not in (int, float) or acceleration_speed not in (1, 2, 3):
            raise ValueError("the acceleration target must be 100, 200 or 300 percent")
        if type(getattr(process, "pid", None)) is not int or process.pid <= 0 or not callable(getattr(process, "poll", None)):
            raise ValueError("speed sessions require the launcher-owned child process")
        if controls._claimed:
            raise ValueError("speed controls are already owned by another session")
        controls._claimed = True
        self.process, self.controls = process, controls
        self.enabled = controls.enabled and sys.platform == "win32"
        self.reason = controls.reason if sys.platform == "win32" else "foreground speed holds are supported on Windows only"
        self.bindings = bindings or SpeedBindings()
        self._keys = key_reader
        self._foreground = foreground_reader
        self._ramp = _Ramp(10)
        self._holds = _Holds(self._ramp, int(acceleration_speed * 10))
        self._stop = threading.Event()
        self._thread = None
        self.restored = True
        self.error = None
        self.transitions = 0

    def start(self):
        if self._thread is not None:
            raise RuntimeError("the speed session has already started")
        if not self.enabled or self.process.poll() is not None:
            return self
        if self.controls._pad is None:
            raise ValueError("speed controls have been closed")
        if self._keys is None:
            self._keys = _ForegroundKeys(self.process.pid, self.bindings)
        if self._foreground is None:
            self._foreground = (self._keys.focused if isinstance(self._keys, _ForegroundKeys)
                                else _ForegroundKeys(self.process.pid, self.bindings).focused)
        self._thread = threading.Thread(target=self._run, name="OrreSpeed", daemon=True)
        self._thread.start()
        return self

    def _run(self):
        pad = self.controls._pad
        disconnected_since = None
        stop_deadline = None
        try:
            while self.process.poll() is None:
                now = time.monotonic()
                focused = self._foreground()
                if self._stop.is_set():
                    stop_deadline = stop_deadline or now + _CLOSE_TIMEOUT - 0.2
                    if now >= stop_deadline:
                        raise RuntimeError("timed out restoring the selected Dolphin speed")
                    mode = None
                else:
                    try:
                        mode = self._keys() if focused else None
                    except Exception as error:
                        # Keyboard failures request restoration through the same
                        # still-owned DSU channel before ending this session.
                        self.error = str(error)
                        self._stop.set()
                        mode = None
                pad.step(now, send=False)
                connected = bool(pad.clients)
                if focused and not connected and self._ramp.current != self._ramp.base:
                    disconnected_since = disconnected_since or now
                    if now - disconnected_since > _CLIENT_TIMEOUT:
                        raise RuntimeError("Dolphin speed device disconnected; current speed is unknown")
                else:
                    disconnected_since = None
                before = self._ramp.current
                previous_button = self._ramp.button
                button = self._holds.step(now, mode, focused, connected, self._stop.is_set())
                self.transitions += before != self._ramp.current
                # Force the first packet of each edge promptly; retain neutral
                # packets for the complete release interval between all pulses.
                if button != previous_button:
                    pad.next_send = 0
                pad.step(now + 0.000001, button)
                self.restored = self._ramp.restored
                if self._stop.is_set() and self.restored:
                    break
                self._stop.wait(0.005) if not self._stop.is_set() else time.sleep(0.005)
        except Exception as error:
            self.error = str(error)
            self.restored = False
        finally:
            # A released virtual input prevents native edge state remaining down.
            try:
                pad.next_send = 0
                pad.step(time.monotonic(), 0)
            except OSError:
                pass
            if self.process.poll() is not None:
                self.restored = True
            if self._stop.is_set():
                self.controls.close()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(_CLOSE_TIMEOUT)
            if self._thread.is_alive():
                self.restored = False
                self.error = "timed out restoring the selected Dolphin speed"
                # The worker closes its socket when its bounded restoration
                # deadline expires. Never close a socket during its send.
                return False
        self.controls.close()
        return self.restored

    def __enter__(self):
        return self.start()

    def __exit__(self, *unused):
        self.close()
