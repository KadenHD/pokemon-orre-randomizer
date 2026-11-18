"""Original-bank MusyX synthesis and bounded Nintendo DSP ADPCM decoding.

The native renderer is built reproducibly by scripts/build_music.py. This
module never opens an audio device or reads an emulator process.
"""
from __future__ import annotations
from array import array
import ctypes as C
import hashlib
import json
from math import isfinite
from pathlib import Path
import struct
import threading
from types import MappingProxyType
from .engine.rebuild_iso import decoded_member
from .native_music_resources import MAX_ASSET
RATE = 32000
_musyx_lock = threading.Lock()

# Source recipe exercised by the EU revision-0 native/final-mix validation.
# Binary digests vary with the toolchain; each installed digest is verified too.
VALIDATED_RENDERER_RECIPE = MappingProxyType({
    'abi': 1,
    'source_commit': '717404d77c17a95dd101bbe737d0f9549ab600e6',
    'archive_sha256': '378a43b85da94a64549019956dc1cfac8134ce1ffbe6d9e31f9358659906e29d',
    'patches_sha256': 'ff6ff89b8edc6644f773ba943f1d860c9380c7f2c59876e7c74ee57778df5f27',
    'adapter_sha256': '047530b85217a7a0bc49c877ee7967d2a6ffe3aa98ed9270a78415df15338067',
})

def renderer_path():
    return Path(__file__).resolve().parent / '_native/orre_musyx.dll'

def renderer_provenance(path=None):
    """Verify the installed manifest/bytes without loading native code."""
    path = Path(path) if path else renderer_path()
    provenance = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if not isinstance(provenance, dict) or provenance.get('abi') != 1 or provenance.get('source_commit') != '717404d77c17a95dd101bbe737d0f9549ab600e6' or provenance.get('renderer_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('Music renderer provenance differs')
    return provenance

def load_renderer(path=None):
    path = Path(path) if path else renderer_path()
    renderer_provenance(path)
    library = C.CDLL(str(path))
    library.orre_music_abi_version.restype = C.c_uint32
    if library.orre_music_abi_version() != 1:
        raise ValueError('Music renderer ABI differs')
    return library

class Span(C.Structure):
    _fields_ = [('data', C.c_void_p), ('size', C.c_size_t)]

class Group(C.Structure):
    _fields_ = [('project', Span), ('pool', Span), ('directory', Span), ('samples', Span)]

class Error(C.Structure):
    _fields_ = [('section', C.c_char_p), ('offset', C.c_size_t), ('reason', C.c_char_p)]

class Musyx:
    rate = 32000

    def __init__(self, disc, coefficient_path, library_path=None):
        if not _musyx_lock.acquire(blocking=False):
            raise RuntimeError('Another original-bank synthesizer is already active in this launcher')
        self.initialized = False
        self.closed = False
        try:
            self._initialize(disc, coefficient_path, library_path)
        except BaseException:
            self.close()
            raise

    def _initialize(self, disc, coefficient_path, library_path):
        """Load original banks; adapt only the host copy of sample581's -1/1 loop sentinel to a monitored one-shot."""
        self.lib = load_renderer(library_path)
        self.lib.orre_music_abi_version.restype = C.c_uint32
        if self.lib.orre_music_abi_version() != 1:
            raise RuntimeError('Music renderer ABI differs')
        l = self.lib
        l.orre_init.argtypes = [C.c_uint]
        l.orre_init.restype = C.c_int
        l.orre_reverb.argtypes = [C.c_float] * 6
        l.orre_reverb.restype = C.c_int
        l.orre_set_native_src.argtypes = [C.c_void_p, C.c_uint32]
        l.orre_set_native_src.restype = C.c_int
        coefficients = Path(coefficient_path).read_bytes()
        if len(coefficients) != 4096:
            raise ValueError('DSP SRC coefficient size differs')
        self.coefficients = C.create_string_buffer(coefficients)
        if not l.orre_set_native_src(self.coefficients, len(coefficients)):
            raise RuntimeError('DSP SRC coefficients rejected')
        self.room = None
        l.sndPCValidateGroup.argtypes = [C.POINTER(Group), C.POINTER(Error)]
        l.sndPCValidateGroup.restype = C.c_bool
        l.sndPCValidateArrangement.argtypes = [Span, C.POINTER(Error)]
        l.sndPCValidateArrangement.restype = C.c_bool
        l.sndPushGroup.argtypes = [C.c_void_p, C.c_uint16, C.c_void_p, C.c_void_p, C.c_void_p]
        l.sndPushGroup.restype = C.c_bool
        l.sndSeqPlayEx.argtypes = [C.c_uint16, C.c_uint16, C.c_void_p, C.c_void_p, C.c_uint8]
        l.sndSeqPlayEx.restype = C.c_uint32
        l.sndSeqStop.argtypes = [C.c_uint32]
        l.sndPCRender.argtypes = [C.c_void_p, C.c_size_t]
        l.sndPCRender.restype = C.c_bool
        raw = [disc.member('common.fsys', 'snd_music_' + suffix) for suffix in ['proj', 'pool', 'sdir']]
        directory = bytearray(raw[2])
        at = 0x800
        expected = bytes.fromhex('0245000000134b400000000064002b1100002611ffffffff0000000100002444')
        if directory[at:at + 32] != expected:
            raise ValueError('Unknown sample-581 sentinel preimage')
        struct.pack_into('>II', directory, at + 20, 0, 0)
        self.adaptations = [{'sample': 581, 'kind': 'loop-sentinel-to-one-shot', 'original_loop_start': 0xffffffff, 'original_loop_length': 1}]
        raw[2] = bytes(directory)
        raw.append(disc.file('sound/snd_music.samp'))
        self.bank = [C.create_string_buffer(b) for b in raw]
        assets = Group(*(Span(C.addressof(b), len(r)) for b, r in zip(self.bank, raw)))
        error = Error()
        if not l.sndPCValidateGroup(C.byref(assets), C.byref(error)):
            raise ValueError((error.section, error.offset, error.reason))
        if l.orre_init(self.rate) != 0:
            raise RuntimeError('MusyX init failed')
        self.initialized = True
        l.orre_native_envelope.argtypes = [C.c_uint32]
        l.orre_native_envelope(1)
        l.orre_retail_predelay.argtypes = [C.c_uint32]
        l.orre_retail_predelay(1)
        if not l.sndPushGroup(self.bank[0], 0, self.bank[3], self.bank[2], self.bank[1]):
            raise RuntimeError('MusyX group rejected')
        self.voices = {}
        self.buffers = {}
        l.sndSeqVolume.argtypes = [C.c_uint8, C.c_uint16, C.c_uint32, C.c_uint8]
        l.sndSeqGetValid.argtypes = [C.c_uint32]
        l.sndSeqGetValid.restype = C.c_bool
        a, b = disc.archive('bgm_archive.fsys')
        self.songs = {m['name']: decoded_member(b, m) for m in a['members']}

    def start(self, name, sid, token=0):
        self.stop(token)
        raw = self.songs[name]
        buffer = C.create_string_buffer(raw)
        self.buffers[token] = buffer
        error = Error()
        if not self.lib.sndPCValidateArrangement(Span(C.addressof(buffer), len(raw)), C.byref(error)):
            raise ValueError((error.section, error.offset, error.reason))
        playing = self.lib.sndSeqPlayEx(0, sid, buffer, None, 0)
        if playing == 0xffffffff:
            raise ValueError(f'Invalid native song ID {sid}')
        self.voices[token] = playing

    def stop(self, token):
        playing = self.voices.pop(token, None)
        if playing is not None and self.lib.sndSeqGetValid(playing):
            self.lib.sndSeqStop(playing)
        self.buffers.pop(token, None)

    def volume(self, token, gain):
        playing = self.voices.get(token)
        if playing is not None and self.lib.sndSeqGetValid(playing):
            self.lib.sndSeqVolume(max(0, min(127, round(gain * 127))), 0, playing, 0)

    def render(self, frames):
        if not 0 < frames <= 32000:
            raise ValueError('Music render block exceeds bounds')
        result = (C.c_int16 * (frames * 2))()
        if not self.lib.sndPCRender(result, frames):
            raise RuntimeError('MusyX render failed')
        if self.lib.orre_sample581_outside():
            raise RuntimeError('Retail sample-581 end reached; native fallback required')
        pcm = array('h')
        pcm.frombytes(bytes(result))
        return pcm

    def reverb(self, values):
        if self.room == tuple(values):
            return
        if not all((isfinite(v) for v in values)) or not 0.01 <= values[2] <= 10:
            return
        if not self.lib.orre_reverb(*values):
            raise RuntimeError('Native reverb parameters rejected')
        self.room = tuple(values)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.initialized:
                self.sample581_reads = int(self.lib.orre_sample581_count())
                self.lib.orre_room_shutdown()
                self.lib.sndQuit()
                self.initialized = False
        finally:
            _musyx_lock.release()

def decode_xd(disc, name, library=None):
    """Decode one identified music/fanfare archive, preserving its source rate."""
    archive, raw = disc.archive(name)
    if not 1 < len(archive['members']) <= 8:
        raise ValueError('Unknown XD stream member count')
    if any((not 0 < member['unpacked_size'] <= MAX_ASSET for member in archive['members'])):
        raise ValueError('XD stream member exceeds bounds')
    members = [decoded_member(raw, member) for member in archive['members']]
    headers = [data for data in members if data.startswith(b'I_SF')]
    if len(headers) != 1 or len(headers[0]) < 0x80:
        raise ValueError('Unknown XD stream header')
    head = headers[0]
    body = max((data for data in members if data is not head), key=len)
    rate, frames, size, channels, interleave, loop, begin, end = struct.unpack_from('>8I', head, 8)
    if channels not in (1, 2) or not 8000 <= rate <= 96000 or (not 0 < frames <= MAX_ASSET // 4) or (not 8 <= interleave <= 1024 * 1024) or interleave % 8 or (loop not in (0, 1)) or (len(head) < 0x40 + channels * 0x40):
        raise ValueError('Unknown XD stream format')
    loop_begin, loop_end = (begin * 14 // 8 // channels, end * 14 // 8 // channels)
    if loop and (not 0 <= loop_begin < loop_end <= frames):
        raise ValueError('Invalid XD loop bounds')
    meta = {'rate': rate, 'frames': frames, 'loop': bool(loop), 'loop_begin': loop_begin, 'loop_end': loop_end}
    if library is not None:
        decoder = library.orre_decode_dsp
        decoder.argtypes = [C.c_void_p, C.c_size_t, C.POINTER(C.c_int16), C.c_uint32, C.c_uint32, C.c_uint32, C.POINTER(C.c_int16), C.c_size_t]
        decoder.restype = C.c_int
        coefficients = []
        for channel in range(channels):
            coefficients.extend(struct.unpack_from('>16h', head, 0x40 + channel * 0x40))
        native_coefficients = (C.c_int16 * len(coefficients))(*coefficients)
        output = (C.c_int16 * (frames * 2))()
        buffer = C.create_string_buffer(body)
        if not decoder(buffer, len(body), native_coefficients, frames, channels, interleave, output, frames * 2):
            raise ValueError('Native DSP decoder rejected stream')
        result = array('h')
        result.frombytes(bytes(output))
        return (result, meta)
    result = array('h', [0]) * (frames * 2)
    for channel in range(channels):
        coefficients = struct.unpack_from('>16h', head, 0x40 + 0x40 * channel)
        first = second = written = 0
        for block in range(0, len(body), interleave * channels):
            chunk = body[block + channel * interleave:block + (channel + 1) * interleave]
            for offset in range(0, len(chunk) - 7, 8):
                control = chunk[offset]
                predictor = control >> 4
                if predictor >= 8:
                    raise ValueError('Invalid DSP ADPCM predictor')
                scale = 1 << (control & 15)
                a1, a2 = coefficients[predictor * 2:predictor * 2 + 2]
                for byte in chunk[offset + 1:offset + 8]:
                    for nibble in (byte >> 4, byte & 15):
                        value = nibble - 16 if nibble & 8 else nibble
                        sample = (value * scale << 11) + 1024 + a1 * first + a2 * second >> 11
                        sample = max(-32768, min(32767, sample))
                        result[written * 2 + channel] = sample
                        if channels == 1:
                            result[written * 2 + 1] = sample
                        second, first = (first, sample)
                        written += 1
                        if written == frames:
                            break
                    if written == frames:
                        break
                if written == frames:
                    break
            if written == frames:
                break
        if written != frames:
            raise ValueError('Truncated XD stream')
    return (result, meta)

def render_streams(voices, cache, count, *, source_clock_ratio=1):
    """Mix at 32kHz, never using the emulator speed as a source-frame clock."""
    if not 0 < count <= RATE or not isfinite(source_clock_ratio) or not 0 < source_clock_ratio <= 2:
        raise ValueError('Music render block exceeds bounds')
    accumulator = [0.0] * (count * 2)
    for voice in voices.values():
        description = voice['description']
        pcm, meta = cache[description['name']]
        position = voice['frame']
        step = meta['rate'] / RATE * source_clock_ratio
        for frame in range(count):
            if meta['loop'] and position >= meta['loop_end']:
                position = meta['loop_begin'] + (position - meta['loop_begin']) % (meta['loop_end'] - meta['loop_begin'])
            if position < meta['frames']:
                low = int(position)
                high = low + 1
                if meta['loop'] and high >= meta['loop_end']:
                    high = meta['loop_begin']
                else:
                    high = min(high, meta['frames'] - 1)
                fraction = position - low
                for channel in (0, 1):
                    value = pcm[low * 2 + channel] * (1 - fraction) + pcm[high * 2 + channel] * fraction
                    accumulator[frame * 2 + channel] += value * description['gain']
            position += step
        voice['frame'] = position
    return array('h', (max(-32768, min(32767, round(value))) for value in accumulator))
