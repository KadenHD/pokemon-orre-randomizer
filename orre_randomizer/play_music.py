"""Owned-process gameplay music companion with native audio fallback.

Gameplay and native effects follow Dolphin speed. Only identified music and
fanfares are rendered on the output clock. Prerecorded movies retain Dolphin's
complete picture and soundtrack at the selected emulation speed.
"""
from __future__ import annotations

from array import array
import ctypes as C
from dataclasses import dataclass
from copy import deepcopy
from math import isfinite
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time

from .native_music_render import RATE, load_renderer, renderer_path, renderer_provenance, VALIDATED_RENDERER_RECIPE
from .native_music_volume import NATIVE_MUSIC_OUTPUT_GAIN


@dataclass(frozen=True)
class MusicCapability:
    supported: bool
    code: str
    reason: str
    prototype_validated: bool = False
    production_validated: bool = False


class NativeMusicUnavailable(RuntimeError):
    pass


def music_capability(game_id: str, revision: int = 0) -> MusicCapability:
    checked = game_id in ('GC6P01', 'GXXP01') and type(revision) is int and revision == 0
    if not checked:
        return MusicCapability(False, 'unsupported_disc', 'Native-speed music requires Europe revision 0')
    if sys.platform != 'win32':
        return MusicCapability(False, 'unsupported_platform', 'Native-speed music requires Windows', True)
    if not renderer_path().is_file() or not renderer_path().with_suffix('.json').is_file():
        return MusicCapability(False, 'renderer_missing', 'The original-bank music renderer is not installed', True)
    try:
        provenance = renderer_provenance()
        if any(provenance.get(key) != value for key, value in VALIDATED_RENDERER_RECIPE.items()):
            raise ValueError('Unvalidated renderer recipe')
    except (OSError, ValueError):
        return MusicCapability(False, 'renderer_unverified', 'The installed music renderer does not match the checked source recipe', True)
    return MusicCapability(True, 'validated', 'Native-speed music checked on Europe revision 0 with native movie and failure recovery', True, True)


def require_native_music(game_id: str, revision: int = 0):
    capability = music_capability(game_id, revision)
    if not capability.supported:
        raise NativeMusicUnavailable(capability.reason)
    return capability


def validate_music_metadata(metadata):
    """Validate fixed retail addresses and dynamic arena ranges before mapping."""
    from .engine.play_music_bridge import music_bridge_profile
    profile = music_bridge_profile(metadata['game_id'], revision=metadata.get('revision', 0))
    for key, expected in profile.items():
        actual = metadata.get(key)
        if key == 'hooks' and isinstance(actual, (list, tuple)):
            actual = tuple(actual)
        if actual != expected:
            raise ValueError('Native music metadata differs from the verified profile: ' + key)
    section = metadata.get('section', {})
    base, size = section.get('address'), section.get('size')
    if (base != profile['base'] or type(size) is not int or not 64 <= size <= 0x81700000 - base
            or size % 32 or metadata.get('reserved_end') != base + size
            or metadata.get('control') != base + size - 64
            or metadata.get('bridge_abi') != 1 or metadata.get('mailbox_bytes') != 64
            or not metadata.get('native_movie_bypass')):
        raise ValueError('Native music arena metadata differs')
    hooks = metadata.get('gain_hooks', [])
    if [hook.get('address') for hook in hooks] != list(profile['hooks']):
        raise ValueError('Native music gain-hook list differs')
    spans = []
    for hook in hooks:
        start, length = hook.get('stub_address'), hook.get('stub_size')
        if (type(start) is not int or type(length) is not int or start % 4 or length % 4
                or length <= 0 or not base + 32 <= start < start + length <= metadata['control']):
            raise ValueError('Native music gain stub is outside the reserved section')
        if any(max(start, left) < min(start + length, right) for left, right in spans):
            raise ValueError('Native music gain stubs overlap')
        spans.append((start, start + length))


class PlaybackGate:
    """Detect stalls, near-boundary VI rollover, and timeline discontinuities."""

    def __init__(self, timeout=.2):
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError('Playback timeout must be finite and positive')
        self.timeout = timeout
        self.paused = False
        self.generation = 0
        self.last_vi = self.last_time = self.progress_at = None
        self.seen_progress = False

    def update(self, vi, now):
        if type(vi) is not int or not 0 <= vi <= 0xffffffff or not isfinite(now):
            raise ValueError('Invalid playback clock sample')
        if self.last_time is not None and now < self.last_time:
            raise ValueError('Playback clock moved backwards')
        rewound = forward = False
        if self.last_vi is None:
            self.seen_progress = vi != 0
            self.progress_at = now
        elif vi != self.last_vi:
            wrapped = self.last_vi >= 0xffff0000 and vi < 0x10000
            rewound = vi < self.last_vi and not wrapped
            delta = (vi - self.last_vi) & 0xffffffff
            forward = not rewound and not wrapped and delta > max(60, (now - self.last_time) * 960)
            if rewound or forward:
                self.generation += 1
            else:
                self.seen_progress = True
            self.progress_at = now
        self.last_vi, self.last_time = vi, now
        self.paused = not (rewound or forward) and self.seen_progress and now - self.progress_at >= self.timeout
        return {'paused': self.paused, 'rewound': rewound, 'forward': forward}


class OwnedDolphinMemory:
    """Read MEM1 of the launcher's live Popen child; writes stay in its mailbox."""

    def __init__(self, process: subprocess.Popen, metadata):
        if not isinstance(process, subprocess.Popen) or process.poll() is not None:
            raise ValueError('Music requires the live Dolphin child spawned by this launcher')
        validate_music_metadata(metadata)
        self.process, self.info = process, metadata
        self.control = metadata['control']
        if type(self.control) is not int or self.control % 32 or not 0x80003000 <= self.control <= 0x817fffc0:
            raise ValueError('Music control mailbox is outside MEM1')
        if metadata.get('bridge_abi') != 1 or metadata.get('mailbox_bytes') != 64:
            raise ValueError('Music bridge ABI differs')
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        k = self.kernel
        k.OpenFileMappingW.argtypes = [C.c_uint32, C.c_int, C.c_wchar_p]
        k.OpenFileMappingW.restype = C.c_void_p
        k.MapViewOfFile.argtypes = [C.c_void_p, C.c_uint32, C.c_uint32, C.c_uint32, C.c_size_t]
        k.MapViewOfFile.restype = C.c_void_p
        k.UnmapViewOfFile.argtypes = [C.c_void_p]
        k.CloseHandle.argtypes = [C.c_void_p]
        self.handle = k.OpenFileMappingW(6, False, f'dolphin-emu.{process.pid}')
        self.pointer = None
        if not self.handle:
            raise OSError('Dolphin MEM1 is not ready')
        self.pointer = k.MapViewOfFile(self.handle, 6, 0, 0, 0x1800000)
        if not self.pointer:
            self.close()
            raise OSError('Cannot map owned Dolphin MEM1')
        try:
            if self.read(0x80000000, 6) != metadata['game_id'].encode('ascii') or self.read(0x80000007, 1) != bytes([metadata['revision']]):
                raise OSError('Dolphin has not booted the matching game revision')
            if self.read(self.control + 24, 8) != struct.pack('>II', 0x4f4d5553, 1):
                raise OSError('Dolphin music mailbox is not initialized')
            from .engine.gift_move_hooks import branch
            for hook in metadata['gain_hooks']:
                if self.u32(hook['address']) != branch(hook['address'], hook['stub_address']):
                    raise OSError('Dolphin music gain hook differs')
        except BaseException:
            self.close()
            raise

    def read(self, address, size):
        if type(address) is not int or type(size) is not int or not 0 <= size <= 0x1800000 or not 0x80000000 <= address <= address + size <= 0x81800000:
            raise ValueError('Music read is outside MEM1')
        if not self.pointer or self.process.poll() is not None:
            raise OSError('Owned Dolphin is no longer running')
        return C.string_at(self.pointer + address - 0x80000000, size)

    def u32(self, address):
        return int.from_bytes(self.read(address, 4), 'big')

    def f32(self, address):
        return struct.unpack('>f', self.read(address, 4))[0]

    def write(self, offset, data):
        allowed = offset in (0, 4, 8) and len(data) == 4
        allowed |= self.info['kind'] == 'xd' and offset == 32 and len(data) == 32
        if not allowed or not self.pointer or self.process.poll() is not None:
            raise ValueError('Music write is outside its host-owned mailbox fields')
        C.memmove(self.pointer + self.control - 0x80000000 + offset, data, len(data))

    def put(self, offset, value):
        self.write(offset, struct.pack('>I', value))

    def close(self):
        if getattr(self, 'pointer', None):
            self.kernel.UnmapViewOfFile(self.pointer)
            self.pointer = None
        if getattr(self, 'handle', None):
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class MusicSession:
    """One companion for one owned child; failure restores native audio.

    The caller configures Dolphin's output volume to100*native_output_gain.
    The same fixed factor is applied to hostPCM, then the owned Dolphin's
    Windows session gain. The default reserves common half-gain headroom.
    ``start`` is asynchronous; inspect ``error``/``active`` in the launcher.
    The caller owns the child process; this class never terminates it.
    """

    def __init__(self, process, assets_dir, metadata, dolphin_dir, *, on_error=None,
                 memory_factory=OwnedDolphinMemory, output_factory=None, state_factory=None, volume_factory=None,
                 native_output_gain=NATIVE_MUSIC_OUTPUT_GAIN):
        from .native_music_output import WaveOutStream
        from .native_music_state import MusicState
        from .native_music_volume import DolphinSessionVolume
        if type(native_output_gain) not in (int,float) or not isfinite(native_output_gain) or not 0 < native_output_gain <= 1:
            raise ValueError('Invalid common Dolphin/companion output gain')
        self.native_output_gain = float(native_output_gain)
        self.process = process
        self.assets_dir, self.metadata = Path(assets_dir), deepcopy(metadata)
        self.coefficients = Path(dolphin_dir) / 'Sys/GC/dsp_coef.bin'
        self.on_error = on_error
        self.memory_factory = memory_factory
        self.output_factory = output_factory or WaveOutStream
        self.state_factory = state_factory or MusicState
        self.volume_factory = volume_factory or DolphinSessionVolume
        self.session_gain = None
        self.error = None
        self.active = False
        self.stopped = threading.Event()
        self.thread = None

    def start(self):
        require_native_music(self.metadata['game_id'], self.metadata.get('revision', 0))
        validate_music_metadata(self.metadata)
        if self.thread is not None:
            raise RuntimeError('Music session was already started')
        self.thread = threading.Thread(target=self._run, name='orre-gameplay-music', daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.stopped.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=5)

    def _lease(self, memory, state, enabled):
        if not enabled:
            memory.put(0, 0)
            return
        voices = [voice for voice in state.voices.values() if not voice.get('native_stopped')]
        if self.metadata['kind'] == 'colosseum':
            groups = [voice['description']['group'] - 23 for voice in voices]
            if any(not 0 <= group <= 7 for group in groups):
                raise ValueError('Unrecognized native music volume group')
            memory.put(8, sum(1 << group for group in set(groups)))
        else:
            ids = list(dict.fromkeys(sid for voice in voices for sid in voice['description']['sdk_ids']))
            if len(ids) > 8:
                raise ValueError('Native music stream list exceeds bridge capacity')
            memory.write(32, struct.pack('>8I', *(ids + [0xffffffff] * (8 - len(ids)))))
        memory.put(4, memory.u32(self.metadata['vi']))
        memory.put(0, 1)

    def _run(self):
        from .native_music_resources import MusicAssets
        memory = state = output = volume = None
        try:
            assets = MusicAssets(self.assets_dir)
            if assets.game_id != self.metadata['game_id'] or assets.revision != self.metadata.get('revision', 0):
                raise ValueError('Music cache and game identities differ')
            state = self.state_factory(self.metadata['kind'], assets, self.metadata, self.coefficients)
            deadline = time.monotonic() + 30
            while not self.stopped.is_set() and self.process.poll() is None:
                try:
                    memory = self.memory_factory(self.process, self.metadata)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise OSError('Dolphin music bridge did not become ready')
                    self.stopped.wait(.05)
            if memory is None:
                return
            output = self.output_factory()
            volume = self.volume_factory(self.process, output.endpoint_id)
            from .native_music_volume import AudioSessionPending
            volume_deadline = time.monotonic() + 5
            while not self.stopped.is_set() and self.process.poll() is None:
                try:
                    self.session_gain = volume.sample()
                    break
                except AudioSessionPending:
                    memory.put(0, 0)
                    if time.monotonic() >= volume_deadline:
                        raise OSError('Owned Dolphin audio session did not become ready; native audio restored')
                    self.stopped.wait(.05)
            if self.session_gain is None:
                return
            gate = PlaybackGate()
            self.active = True
            was_paused = was_cinema = False
            next_endpoint_check = time.monotonic() + 1
            while not self.stopped.is_set() and self.process.poll() is None:
                now = time.monotonic()
                gains = volume.sample()
                if gains != self.session_gain:
                    output.clear()
                    self.session_gain = gains
                if now >= next_endpoint_check:
                    if not output.matches_default_endpoint():
                        raise OSError('Dolphin audio output changed; native audio restored')
                    next_endpoint_check = now + 1
                vi = memory.u32(self.metadata['vi'])
                change = gate.update(vi, now)
                if change['forward']:
                    raise RuntimeError('Unrecognized forward timeline change; native audio restored')
                if change['rewound']:
                    output.clear()
                    # Keep the bounded lease live while rebuilding synth phase.
                    restoring = threading.Event()
                    def heartbeat():
                        while not restoring.wait(.02) and not self.stopped.is_set():
                            try:
                                memory.put(4, memory.u32(self.metadata['vi']))
                            except (OSError, ValueError):
                                break
                    worker = threading.Thread(target=heartbeat, daemon=True)
                    worker.start()
                    try:
                        state.reset_timeline(now, vi)
                    finally:
                        restoring.set()
                        worker.join(timeout=1)
                cinema = state.cinema(memory)
                if cinema != was_cinema or gate.paused != was_paused:
                    output.clear()
                if not gate.paused:
                    state.sync([] if cinema else state.describe(memory), now, render=not cinema)
                    state.remember_timeline(vi)
                self._lease(memory, state, not cinema)
                if not cinema and not gate.paused:
                    for _ in range(output.poll()):
                        pcm = state.render(output.frames)
                        # Python's signed rounding is symmetric; no global/device volume changes.
                        scaled = array('h', (round(sample * self.native_output_gain * self.session_gain[index % 2])
                                            for index, sample in enumerate(pcm))).tobytes()
                        if not output.submit(scaled):
                            raise OSError('Gameplay music queue stopped accepting PCM')
                was_cinema, was_paused = cinema, gate.paused
                self.stopped.wait(.005)
        except Exception as error:
            self.error = str(error)
            if self.on_error:
                try:
                    self.on_error(self.error)
                except Exception:
                    pass
        finally:
            self.active = False
            if output:
                try:
                    output.clear()
                except OSError:
                    pass
            if memory:
                try:
                    memory.put(0, 0)
                except (OSError, ValueError):
                    pass
                memory.close()
            if output:
                try:
                    output.close()
                except OSError:
                    pass
            if state:
                state.close()
            if volume:
                volume.close()
