"""Music ownership and bounded same-session phase reconstruction."""
from __future__ import annotations
from collections import deque
from copy import deepcopy
import hashlib
import struct
import time
from .engine.rebuild_iso import decoded_member
from .native_music_render import Musyx, decode_xd, render_streams, RATE
from .native_music_resources import MAX_ASSET
from .native_music_render import load_renderer
from .native_music_clock import ConsoleDacClock, GC_CLOCK_RATIO

def valid(pointer, size=4):
    return isinstance(pointer, int) and isinstance(size, int) and (size >= 0) and (0x80003000 <= pointer <= pointer + size <= 0x81800000)

class MusicState:
    """Bounded original-bank playback and same-session cursor reconstruction."""

    def __init__(self, kind, disc, info, coefficient_path=None, library_path=None):
        self.kind, self.disc, self.info = (kind, disc, info)
        self.backend = None
        self.dac_clock = ConsoleDacClock()
        self.voices = {}
        self.events = deque(maxlen=256)
        self.cache = {}
        self.failures = deque(maxlen=0x20)
        self.native_only = {}
        self.journal = []
        self.timeline = []
        self.replaying = False
        self.restorable = True
        self.journal_frames = 0
        self.last_journal_sync = None
        self.coefficient_path = coefficient_path
        self.library_path = library_path
        self.decoder_library = load_renderer(library_path) if kind == 'xd' else None
        self.colsongs = {}
        if kind == 'colosseum':
            a, b = disc.archive('bgm_archive.fsys')
            for member in a['members']:
                data = decoded_member(b, member)
                fingerprint = hashlib.sha256(data[:0x80]).hexdigest()
                if fingerprint in self.colsongs:
                    raise ValueError('Ambiguous arrangement fingerprint')
                self.colsongs[fingerprint] = member['name']
            self.backend = Musyx(disc, coefficient_path, library_path)
        else:
            self.streams = {}
            self.resources = {}
            for name in disc.entries:
                data = disc.file(name)
                if data[:4] != b'FSYS' or len(data) < 12:
                    raise ValueError('Invalid XD music archive')
                group_id = int.from_bytes(data[8:12], 'big')
                if group_id in self.streams:
                    raise ValueError('Ambiguous XD stream resource ID')
                self.resources[group_id] = name
                self.streams[group_id] = name

    def describe(self, mem):
        """Correlate native handles with known original music resources only."""
        p = self.info
        result = []
        params = mem.u32(p['sound_params_global'])
        if not valid(params):
            return result
        if self.kind == 'colosseum':
            rowdata = mem.read(params, 1236 * 12)
            owners = {}
            for sid in range(1236):
                row = rowdata[sid * 12:sid * 12 + 12]
                work = int.from_bytes(row[8:12], 'big')
                # FX voice handles and sequence public IDs are separate domains.
                # A numerically equal FX handle must not replace a BGM owner.
                if row[0] & 0x80 or row[1] != 0 or not valid(work, 20):
                    continue
                handle = mem.u32(work + 8)
                owners[handle] = (sid, row, work)
            seq = mem.u32(p['seq_active_global'])
            seen = set()
            while valid(seq, 0x1868) and seq not in seen and (len(seen) < 8):
                seen.add(seq)
                raw = mem.read(seq, 0x124)
                state, index, gid, pub = struct.unpack_from('>BBHI', raw, 8)
                if gid == 0 and pub in owners:
                    sid, row, work = owners[pub]
                    resource = mem.u32(seq + 0x118)
                    fingerprint = hashlib.sha256(mem.read(resource, 0x80)).hexdigest() if valid(resource, 0x80) else None
                    name = self.colsongs.get(fingerprint)
                    if name:
                        if name in ('null_bgm_song', 'wind_atmos_loop_song') or row[0] & 0x80:
                            self.native_only[name] = sid
                            seq = int.from_bytes(raw[:4], 'big')
                            continue
                        group = mem.read(seq + 0xeb0, 1)[0]
                        if group != 23 + index:
                            raise ValueError('Unknown native volume group')
                        gain = mem.f32(p['fader'] + group * 0x30)
                        result.append({'key': pub, 'sound_id': sid, 'name': name, 'sid': int.from_bytes(row[4:6], 'big'), 'gain': gain, 'group': group, 'sequence': seq, 'reverb': list(struct.unpack('>6f', mem.read(p['reverb_parameters'], 24)))})
                    else:
                        self.failures.append({'reason': 'unknown-colo-resource', 'resource': hex(resource), 'work': mem.read(work, 20).hex(), 'sound_id': sid})
                seq = int.from_bytes(raw[:4], 'big')
        else:
            streams = mem.u32(p['streams_global'])
            count = mem.u32(p['stream_count_global'])
            if not valid(streams, count * 256) or not 0 < count <= 0x40:
                return result
            for i in range(count):
                work = streams + i * 256
                raw = mem.read(work, 256)
                status = struct.unpack_from('>I', raw, 8)[0]
                if status != 9 or raw[0x3b] != 0 or int.from_bytes(raw[:4], 'big') != 0:
                    continue
                sound_id = int.from_bytes(raw[0x30:0x34], 'big')
                group_id = int.from_bytes(raw[0x28:0x2c], 'big')
                name = self.streams.get(group_id)
                if not name:
                    if group_id in self.resources:
                        self.native_only[self.resources[group_id]] = sound_id
                    else:
                        self.failures.append({'reason': 'unknown-xd-resource', 'group': hex(group_id), 'work': raw[:0x40].hex(), 'sound_id': sound_id})
                    continue
                right = int.from_bytes(raw[4:8], 'big')
                ids = [int.from_bytes(raw[12:16], 'big')]
                if valid(right, 256):
                    ids.append(mem.u32(right + 12))
                volume = raw[0x37] / 127
                if not 0 <= sound_id <= 16384 or not valid(params + sound_id * 12, 12):
                    raise ValueError('XD music sound row outside bounds')
                master = mem.read(params + sound_id * 12 + 1, 1)[0] / 127
                result.append({'key': (work, sound_id, group_id, tuple(ids)), 'sound_id': sound_id, 'name': name, 'gain': volume * master, 'sdk_ids': ids, 'status': status, 'cursor': int.from_bytes(raw[0x20:0x24], 'big')})
        return result

    def cinema(self, mem):
        """Recognize THP playback and nonempty XD movie slots, including state3."""
        if self.kind == 'colosseum':
            raw = mem.read(self.info['movie_player'], 0xa8)
            return raw[0x3c:0x40] == b'THP\x00' and int.from_bytes(raw[0xa0:0xa4], 'big') == 1 and (raw[0xa4] in (1, 2))
        count = mem.u32(self.info['movie_count_global'])
        table = mem.u32(self.info['movie_slots_global'])
        if not 0 < count <= 0x20 or not valid(table, count * 0x20):
            return False
        return any((0 < mem.u32(table + i * 0x20) <= 16 for i in range(count)))

    def sync(self, descriptions, elapsed, *, render=True):
        if self.restorable and (not self.replaying):
            snapshot = (descriptions, render)
            if self.backend and snapshot != self.last_journal_sync:
                self.last_journal_sync = deepcopy(snapshot)
                self.journal.append(('sync', deepcopy(descriptions), elapsed, render))
                if len(self.journal) > 30000:
                    self.restorable = False
                    self.journal.clear()
                    self.timeline.clear()
        wanted = {d['key']: d for d in descriptions}
        for key in list(self.voices):
            if key not in wanted:
                voice = self.voices[key]
                name = voice['description']['name']
                fanfare = name.startswith(('stm_me_', 'me_', 'level_up'))
                if render and fanfare:
                    if self.backend:
                        playing = self.backend.voices.get(key)
                        finished = playing is None or not self.backend.lib.sndSeqGetValid(playing)
                    else:
                        pcm, meta = self.cache[name]
                        finished = voice['frame'] >= meta['frames']
                    if not finished:
                        if not voice.get('native_stopped'):
                            self.events.append({'time': elapsed, 'event': 'native-ended-host-fanfare-continues', 'name': name})
                        voice['native_stopped'] = True
                        continue
                if self.backend:
                    self.backend.stop(key)
                self.events.append({'time': elapsed, 'event': 'stop', 'name': self.voices[key]['description']['name']})
                del self.voices[key]
        for key, d in wanted.items():
            if self.backend and render:
                self.backend.reverb(d['reverb'])
            if key not in self.voices:
                if render:
                    if self.backend:
                        self.backend.start(d['name'], d['sid'], key)
                    elif d['name'] not in self.cache:
                        self._make_cache_room()
                        self.cache[d['name']] = decode_xd(self.disc, d['name'], self.decoder_library)
                self.voices[key] = {'description': d, 'frame': 0.0}
                self.events.append({'time': elapsed, 'event': 'play', **{k: v for k, v in d.items() if k != 'key'}})
            else:
                self.voices[key]['description'] = d
                self.voices[key]['native_stopped'] = False
            if self.backend and render:
                self.backend.volume(key, d['gain'])

    def render(self, count):
        if self.restorable and (not self.replaying):
            if self.backend:
                self.journal.append(('render', count))
        if not self.replaying:
            self.journal_frames += count
        if self.journal_frames > RATE * 120 and self.backend:
            self.restorable = False
            self.journal.clear()
            self.timeline.clear()
        if self.backend:
            return self.dac_clock.render(count, self.backend.render)
        return render_streams(self.voices, self.cache, count, source_clock_ratio=GC_CLOCK_RATIO)

    def _make_cache_room(self):
        active = {v['description']['name'] for v in self.voices.values()}
        while sum((len(pcm) * 2 for pcm, meta in self.cache.values())) > 192 * 1024 * 1024:
            discard = next((name for name in self.cache if name not in active), None)
            if discard is None:
                raise RuntimeError('Active music exceeds memory bound')
            del self.cache[discard]

    def remember_timeline(self, vi):
        if not self.restorable:
            return
        self.timeline.append((vi, len(self.journal), deepcopy(self.voices) if not self.backend else None))
        if len(self.timeline) > 6000:
            del self.timeline[:1000]

    def reset_timeline(self, elapsed, vi=None):
        checkpoint = next((p for p in reversed(getattr(self, 'timeline', [])) if p[0] <= vi), None) if vi is not None else None
        if checkpoint and 0 <= vi - checkpoint[0] <= 4:
            started = time.monotonic()
            saved_events = self.events
            self.events = []
            journal = self.journal[:checkpoint[1]]
            if self.backend:
                self.backend.close()
                self.backend = Musyx(self.disc, self.coefficient_path, self.library_path)
                self.dac_clock = ConsoleDacClock()
                self.voices = {}
                self.replaying = True
                try:
                    for op in journal:
                        if op[0] == 'sync':
                            self.sync(op[1], op[2], render=op[3])
                        else:
                            left = op[1]
                            while left:
                                count = min(left, 32000)
                                self.render(count)
                                left -= count
                finally:
                    self.replaying = False
            else:
                self.voices = deepcopy(checkpoint[2])
            self.events = saved_events
            self.journal = journal
            self.last_journal_sync = None
            self.journal_frames = sum((op[1] for op in journal if op[0] == 'render'))
            self.timeline = [p for p in self.timeline if p[0] <= checkpoint[0]]
            self.events.append({'time': elapsed, 'event': 'native-timeline-rewind', 'music_restarts': False, 'restored_vi': checkpoint[0], 'requested_vi': vi, 'restore_wall_seconds': time.monotonic() - started})
            return
        raise RuntimeError('Music phase cannot be restored for this state; native audio restored')

    def close(self):
        if self.backend:
            self.backend.close()
        self.voices.clear()
        self.cache.clear()
        self.journal.clear()
        self.timeline.clear()
