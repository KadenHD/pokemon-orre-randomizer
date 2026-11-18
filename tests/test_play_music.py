"""Music policy, output ownership, decoder and fallback checks without speakers."""
from array import array
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from orre_randomizer.native_music_output import WaveOutStream
from orre_randomizer.native_music_endpoint import matching_waveout_device, waveout_endpoint
from orre_randomizer.native_music_render import decode_xd, load_renderer, render_streams, renderer_path, VALIDATED_RENDERER_RECIPE
from orre_randomizer.native_music_resources import MusicAssets, prepare_music_assets, selected_resource
from orre_randomizer.native_music_state import MusicState
from orre_randomizer.native_music_clock import ConsoleDacClock, GC_CLOCK_RATIO
from orre_randomizer.native_music_volume import session_gains, AudioSessionPending
from orre_randomizer.play_music import MusicSession, OwnedDolphinMemory, PlaybackGate, music_capability, validate_music_metadata


def fake_disc(path, game_id='GC6P01'):
    names = b'common.fsys\0bgm_archive.fsys\0sound\0snd_music.samp\0'
    entries = [(0x01000000, 0, 5), (0, 0x1000, 3), (12, 0x1100, 4),
               (0x01000000 | 29, 0, 5), (35, 0x1200, 5)]
    fst = b''.join(struct.pack('>III', *entry) for entry in entries) + names
    raw = bytearray(0x1205)
    raw[:6] = game_id.encode()
    raw[0x1c:0x20] = b'\xc2\x33\x9f\x3d'
    struct.pack_into('>II', raw, 0x424, 0x600, len(fst))
    raw[0x600:0x600 + len(fst)] = fst
    raw[0x1000:0x1003] = b'one'
    raw[0x1100:0x1104] = b'two!'
    raw[0x1200:] = b'three'
    path.write_bytes(raw)


class ResourceTests(unittest.TestCase):
    def test_rvz_is_converted_inside_temporary_cache_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, cache = root / 'source.rvz', root / 'Audio'
            source.write_bytes(b'compressed fixture')
            cancelled = threading.Event()
            def convert(input_path, output_path, cancel):
                self.assertEqual(input_path, source)
                self.assertEqual(cancel, cancelled)
                self.assertTrue(output_path.is_relative_to(root))
                fake_disc(output_path)
            with patch('orre_randomizer.disc_images.convert', side_effect=convert) as converter:
                prepare_music_assets(source, cache, game_id='GC6P01', cancel=cancelled)
            converter.assert_called_once()
            self.assertEqual(source.read_bytes(), b'compressed fixture')
            self.assertEqual(MusicAssets(cache).file('common.fsys'), b'one')
            self.assertEqual(sorted(path.name for path in root.iterdir()), ['Audio', 'source.rvz'])

    def test_read_only_atomic_shared_cache_and_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, cache = root / 'source.gcm', root / 'shared/Audio'
            fake_disc(source)
            before = hashlib.sha256(source.read_bytes()).digest()
            manifest = prepare_music_assets(source, cache, game_id='GC6P01')
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)
            self.assertEqual(MusicAssets(cache).file('sound/snd_music.samp'), b'three')
            self.assertEqual(prepare_music_assets(source, cache, game_id='GC6P01'), manifest)
            (cache / 'common.fsys').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'hash'):
                prepare_music_assets(source, cache, game_id='GC6P01')

    def test_cancellation_does_not_publish_partial_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, cache = root / 'source.iso', root / 'Audio'
            fake_disc(source)
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(InterruptedError):
                prepare_music_assets(source, cache, game_id='GC6P01', cancel=cancelled)
            self.assertFalse(cache.exists())
            self.assertEqual(sorted(path.name for path in root.iterdir()), ['source.iso'])

    def test_cries_and_movie_archives_are_not_host_music(self):
        self.assertTrue(selected_resource('GXXP01', 'stm_me_victory.fsys'))
        self.assertTrue(selected_resource('GXXP01', 'stm_bgm_title.fsys'))
        self.assertFalse(selected_resource('GXXP01', 'stm_se_nakigoe_archive.fsys'))
        self.assertFalse(selected_resource('GXXP01', 'movie.thp'))
        self.assertFalse(selected_resource('GXXP01', '../stm_bgm_title.fsys'))

    def test_unknown_region_or_wrong_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.iso'
            fake_disc(source)
            with self.assertRaises(ValueError):
                prepare_music_assets(source, root / 'Audio', game_id='GC6E01')
            self.assertFalse((root / 'Audio').exists())


class GateTests(unittest.TestCase):
    def test_speed_change_does_not_change_wall_clock_pause_gate(self):
        gate = PlaybackGate()
        self.assertFalse(gate.update(10, 0)['paused'])
        gate.update(70, 1)
        gate.update(190, 2)
        self.assertTrue(gate.update(190, 2.21)['paused'])
        self.assertFalse(gate.update(191, 2.22)['paused'])
        self.assertTrue(gate.update(100, 2.23)['rewound'])
        self.assertEqual(gate.generation, 1)

    def test_rollover_is_not_state_load_but_unrecognized_forward_jump_is(self):
        gate = PlaybackGate()
        gate.update(0xfffffffe, 0)
        self.assertFalse(gate.update(1, .02)['rewound'])
        self.assertTrue(gate.update(10000, .03)['forward'])

    def test_unknown_build_and_regions_never_claim_validation(self):
        for game_id, revision in [('GC6E01', 0), ('GXXJ01', 0), ('GC6P01', 1)]:
            capability = music_capability(game_id, revision)
            self.assertFalse(capability.supported)
            self.assertFalse(capability.production_validated)

    def test_checked_eu_profiles_require_verified_current_renderer_recipe(self):
        with tempfile.TemporaryDirectory() as folder:
            library = Path(folder)/'renderer.dll'
            library.write_bytes(b'synthetic fixture; never loaded')
            manifest = dict(VALIDATED_RENDERER_RECIPE)
            manifest['renderer_sha256'] = hashlib.sha256(library.read_bytes()).hexdigest()
            metadata = library.with_suffix('.json')
            metadata.write_text(json.dumps(manifest))
            with patch('orre_randomizer.play_music.sys.platform', 'win32'), \
                 patch('orre_randomizer.play_music.renderer_path', return_value=library), \
                 patch('orre_randomizer.native_music_render.renderer_path', return_value=library), \
                 patch('orre_randomizer.native_music_render.C.CDLL') as loader:
                for game in ('GC6P01', 'GXXP01'):
                    self.assertTrue(music_capability(game).production_validated)
                for key in ('abi', 'source_commit', 'archive_sha256', 'patches_sha256', 'adapter_sha256'):
                    with self.subTest(stale_field=key):
                        metadata.write_text(json.dumps({**manifest, key: 'stale'}))
                        result = music_capability('GC6P01')
                        self.assertFalse(result.supported)
                        self.assertFalse(result.production_validated)
                loader.assert_not_called()

    def test_corrupt_renderer_or_manifest_never_enables_checked_music(self):
        with tempfile.TemporaryDirectory() as folder:
            library = Path(folder)/'renderer.dll'
            library.write_bytes(b'synthetic fixture; never loaded')
            manifest = dict(VALIDATED_RENDERER_RECIPE)
            manifest['renderer_sha256'] = hashlib.sha256(library.read_bytes()).hexdigest()
            metadata = library.with_suffix('.json')
            with patch('orre_randomizer.play_music.sys.platform', 'win32'), \
                 patch('orre_randomizer.play_music.renderer_path', return_value=library), \
                 patch('orre_randomizer.native_music_render.renderer_path', return_value=library):
                for content in ('{broken', '[]', json.dumps({**manifest, 'renderer_sha256': 'bad'})):
                    metadata.write_text(content)
                    capability = music_capability('GC6P01')
                    self.assertFalse(capability.supported)
                    self.assertFalse(capability.production_validated)


def fake_winmm():
    library = Mock()
    headers = []
    library.waveOutOpen.side_effect = lambda device, *_: setattr(device._obj, 'value', 1) or 0
    def prepare(device, header, size):
        headers.append(header._obj)
        header._obj.flags |= 2
        return 0
    library.waveOutPrepareHeader.side_effect = prepare
    def write(device, header, size):
        header._obj.flags = (header._obj.flags | 16) & ~1
        return 0
    library.waveOutWrite.side_effect = write
    def reset(device):
        for header in headers:
            header.flags = (header.flags | 1) & ~16
        return 0
    library.waveOutReset.side_effect = reset
    library.waveOutUnprepareHeader.return_value = 0
    library.waveOutClose.return_value = 0
    return library, headers


class OutputTests(unittest.TestCase):
    def test_bounded_buffers_remain_alive_until_device_completes(self):
        library, headers = fake_winmm()
        stream = WaveOutStream(frames=2, blocks=2, library=library)
        first = array('h', [1, 2, 3, 4]).tobytes()
        second = array('h', [5, 6, 7, 8]).tobytes()
        self.assertTrue(stream.submit(first))
        self.assertTrue(stream.submit(second))
        self.assertFalse(stream.submit(bytes(8)))
        self.assertEqual(C.string_at(headers[0].data, 8), first)
        headers[0].flags = (headers[0].flags | 1) & ~16
        self.assertEqual(stream.poll(), 1)
        self.assertTrue(stream.submit(bytes(8)))
        self.assertEqual(C.string_at(headers[1].data, 8), second)
        self.assertEqual(stream.completed_frames, 2)
        stream.close()
        stream.close()
        self.assertEqual(library.waveOutUnprepareHeader.call_count, 2)
        library.waveOutClose.assert_called_once()
        library.waveOutSetVolume.assert_not_called()

    def test_movie_or_pause_flush_discards_pending_music(self):
        library, headers = fake_winmm()
        with WaveOutStream(frames=2, blocks=3, library=library) as stream:
            stream.submit(bytes(8))
            stream.clear()
            self.assertEqual(stream.poll(), 3)


class EndpointTests(unittest.TestCase):
    def test_mapper_is_only_used_when_it_matches_the_cubeb_console_endpoint(self):
        library = Mock()
        with patch('orre_randomizer.native_music_endpoint.waveout_endpoint', return_value='console'):
            device, endpoint = matching_waveout_device(library, endpoint='CONSOLE')
        self.assertEqual(device, 0xffffffff)
        library.waveOutGetNumDevs.assert_not_called()

    def test_console_endpoint_can_be_selected_when_mapper_points_elsewhere(self):
        library = Mock()
        library.waveOutGetNumDevs.return_value = 2
        values = {0xffffffff: 'other-default', 0: 'other-device', 1: 'console'}
        with patch('orre_randomizer.native_music_endpoint.waveout_endpoint', side_effect=lambda lib, device: values[device]):
            device, endpoint = matching_waveout_device(library, endpoint='console')
        self.assertEqual(device, 1)

    def test_no_matching_output_restores_native_instead_of_using_another_device(self):
        library = Mock()
        library.waveOutGetNumDevs.return_value = 2
        with patch('orre_randomizer.native_music_endpoint.waveout_endpoint', return_value='other'):
            with self.assertRaisesRegex(OSError, 'no matching audio output'):
                matching_waveout_device(library, endpoint='console')

    def test_driver_endpoint_size_is_bounded(self):
        library = Mock()
        def query(device, message, pointer, size):
            C.cast(pointer, C.POINTER(C.c_uint32)).contents.value = 0xffffffff
            return 0
        library.waveOutMessage.side_effect = query
        self.assertIsNone(waveout_endpoint(library, 0))
        self.assertEqual(library.waveOutMessage.call_count, 1)


class DSPFixture:
    def __init__(self, *, rate=32000, channels=1, frames=14, loop=False):
        head = bytearray(0xc0)
        head[:4] = b'I_SF'
        struct.pack_into('>8I', head, 8, rate, frames, 8 * channels, channels, 8, int(loop), 0, 8 * channels)
        # Predictor zero, scale1: signed nibbles 1..7, -8..-2.
        body = bytes.fromhex('00123456789abcde') * channels
        self.raw = bytes(head) + body
        self.rows = [{'offset': 0, 'stored_size': len(head), 'unpacked_size': len(head), 'compression': 'none'},
                     {'offset': len(head), 'stored_size': len(body), 'unpacked_size': len(body), 'compression': 'none'}]

    def archive(self, name):
        return {'members': self.rows}, self.raw


class RendererTests(unittest.TestCase):
    def test_adpcm_sign_history_stereo_and_bounds(self):
        pcm, meta = decode_xd(DSPFixture(), 'fixture')
        expected = list(range(1, 8)) + list(range(-8, -1))
        self.assertEqual(list(pcm[::2]), expected)
        self.assertEqual(pcm[::2], pcm[1::2])
        self.assertEqual(meta['frames'], 14)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            decode_xd(DSPFixture(frames=28), 'fixture')

    @unittest.skipUnless(sys.platform == 'win32' and renderer_path().is_file(), 'requires source-built renderer')
    def test_source_built_decoder_matches_independent_python_for_signed_history(self):
        library = load_renderer()
        for channels in (1, 2):
            fixture = DSPFixture(channels=channels)
            raw = bytearray(fixture.raw)
            for channel in range(channels):
                struct.pack_into('>hh', raw, 0x40 + channel * 0x40, 2048, -1024)
            fixture.raw = bytes(raw)
            expected, meta = decode_xd(fixture, 'fixture')
            actual, actual_meta = decode_xd(fixture, 'fixture', library)
            self.assertEqual(actual, expected)
            self.assertEqual(actual_meta, meta)

    def test_loop_and_one_shot_advance_on_output_frames(self):
        pcm = array('h', [10, 10, 20, 20, 30, 30, 40, 40])
        meta = {'rate': 32000, 'frames': 4, 'loop': True, 'loop_begin': 1, 'loop_end': 4}
        voices = {1: {'frame': 0., 'description': {'name': 'loop', 'gain': 1}}}
        actual = render_streams(voices, {'loop': (pcm, meta)}, 8)
        self.assertEqual(list(actual[::2]), [10, 20, 30, 40, 20, 30, 40, 20])
        meta['loop'] = False
        voices[1]['frame'] = 0
        actual = render_streams(voices, {'loop': (pcm, meta)}, 8)
        self.assertEqual(list(actual[::2]), [10, 20, 30, 40, 0, 0, 0, 0])

    def test_resampling_uses_individual_source_rate_and_wraps_interpolation(self):
        pcm = array('h', [0, 0, 100, 100, 200, 200, 300, 300])
        meta = {'rate': 16000, 'frames': 4, 'loop': True, 'loop_begin': 0, 'loop_end': 4}
        voice = {'frame': 0., 'description': {'name': 'loop', 'gain': 1}}
        actual = render_streams({1: voice}, {'loop': (pcm, meta)}, 10)
        self.assertEqual(list(actual[::2]), [0, 50, 100, 150, 200, 250, 300, 150, 0, 50])


class ClockTests(unittest.TestCase):
    @staticmethod
    def source():
        class Synth:
            def __init__(self, *args):
                self.position = 0
                self.requests = []

            def render(self, count):
                self.requests.append(count)
                values = array('h', (round(12000 * math.sin(2 * math.pi * 1000 * (self.position + frame) / 32000)) * sign
                                    for frame in range(count) for sign in (1, -1)))
                self.position += count
                return values

            def close(self):
                pass
        return Synth

    def test_rational_clock_has_identical_output_across_packet_boundaries(self):
        whole, split = ConsoleDacClock(), ConsoleDacClock()
        first, second = self.source()(), self.source()()
        expected = whole.render(2248, first.render)
        actual = array('h')
        for frames in (1, 639, 7, 1000, 601):
            actual.extend(split.render(frames, second.render))
        self.assertEqual(actual, expected)
        self.assertEqual(split.consumed_source_frames, 2250)
        self.assertEqual(split.phase, 0)
        self.assertLessEqual(len(split.pending), 4)
        self.assertEqual(actual[::2], array('h', (-sample for sample in actual[1::2])))

    def test_sine_pitch_follows_documented_dac_not_nominal_or_game_double_speed(self):
        clock, source = ConsoleDacClock(), self.source()()
        values = clock.render(32000, source.render)[::2]
        crossings = [index - previous / (current - previous)
            for index, (previous, current) in enumerate(zip(values, values[1:])) if previous <= 0 < current]
        measured = 32000 * (len(crossings) - 1) / (crossings[-1] - crossings[0])
        self.assertAlmostEqual(measured, 1000 * GC_CLOCK_RATIO, places=2)
        self.assertGreater(abs(measured - 1000), .8)
        self.assertTrue(all(0 < count <= 32000 for count in source.requests))
        self.assertEqual(clock.consumed_source_frames, 32000 * 1125 // 1124)

    def test_colosseum_journal_reconstructs_fractional_clock_and_lookahead(self):
        state = stream_state()
        state.kind = 'colosseum'
        state.backend = self.source()()
        state.dac_clock = ConsoleDacClock()
        state.disc = Mock(); state.coefficient_path = state.library_path = None
        state.render(638)
        self.assertNotEqual(state.dac_clock.phase, 0)
        state.remember_timeline(100)
        expected = state.render(640)
        with patch('orre_randomizer.native_music_state.Musyx', self.source()):
            for _ in range(2):
                state.reset_timeline(2, 100)
                self.assertEqual(state.render(640), expected)

    def test_xd_state_uses_console_rate_and_restores_fractional_cursor(self):
        state = stream_state()
        state.cache['stm_me_test'] = (array('h', [1200, -1200]) * 8000,
            {'rate': 32000, 'frames': 8000, 'loop': False, 'loop_begin': 0, 'loop_end': 8000})
        state.sync([{'key': 1, 'name': 'stm_me_test', 'gain': 1}], 0)
        state.render(1124)
        self.assertAlmostEqual(state.voices[1]['frame'], 1125, places=8)
        state.remember_timeline(100)
        expected = state.render(640)
        for _ in range(2):
            state.reset_timeline(2, 100)
            self.assertEqual(state.render(640), expected)


class LeaseTests(unittest.TestCase):
    def test_fixed_globals_and_dynamic_reserved_section_are_validated(self):
        from orre_randomizer.engine.play_music_bridge import music_bridge_profile
        for game_id in ('GC6P01', 'GXXP01'):
            profile = music_bridge_profile(game_id)
            base = profile['base']
            metadata = dict(profile, revision=0, section={'address': base, 'size': 1600},
                reserved_end=base + 1600, control=base + 1536, bridge_abi=1, mailbox_bytes=64,
                native_movie_bypass=True, gain_hooks=[{'address': address, 'stub_address': base + 32 + index * 64,
                    'stub_size': 64} for index, address in enumerate(profile['hooks'])])
            validate_music_metadata(metadata)
            metadata['vi'] += 4
            with self.assertRaisesRegex(ValueError, 'verified profile'):
                validate_music_metadata(metadata)

    def test_only_host_owned_mailbox_fields_are_writable(self):
        memory = OwnedDolphinMemory.__new__(OwnedDolphinMemory)
        backing = C.create_string_buffer(64)
        memory.pointer = C.addressof(backing)
        memory.control = 0x80000000
        memory.process = Mock()
        memory.process.poll.return_value = None
        memory.info = {'kind': 'colosseum'}
        for offset in (0, 4, 8):
            memory.put(offset, 123)
        for offset in (12, 16, 20, 24, 28, 32):
            with self.assertRaises(ValueError):
                memory.put(offset, 0)
        with self.assertRaises(ValueError):
            memory.write(32, bytes(32))
        memory.info['kind'] = 'xd'
        memory.write(32, bytes(32))
        with self.assertRaises(ValueError):
            memory.write(36, bytes(32))

    def test_unknown_stream_count_falls_back_instead_of_muting_partial_list(self):
        session = MusicSession.__new__(MusicSession)
        session.metadata = {'kind': 'xd', 'vi': 0x80000000}
        state = Mock()
        state.voices = {1: {'description': {'sdk_ids': list(range(9))}}}
        memory = Mock()
        with self.assertRaises(ValueError):
            session._lease(memory, state, True)
        memory.write.assert_not_called()
        memory.put.assert_not_called()


def stream_state():
    state = MusicState.__new__(MusicState)
    state.kind = 'xd'
    state.backend = None
    state.voices = {}
    state.events = []
    state.cache = {'stm_me_test': (array('h', [100, 100, 200, 200, 300, 300, 400, 400]),
        {'rate': 32000, 'frames': 4, 'loop': False, 'loop_begin': 0, 'loop_end': 4})}
    state.journal = []
    state.timeline = []
    state.replaying = False
    state.restorable = True
    state.journal_frames = 0
    state.last_journal_sync = None
    return state


class StateTests(unittest.TestCase):
    def test_native_fx_handle_collision_does_not_replace_the_music_owner(self):
        import hashlib
        data = bytearray(0x20000)
        base = 0x80010000
        info = {'sound_params_global': base, 'seq_active_global': base+4,
                'fader': base+0x18000, 'reverb_parameters': base+0x100}
        params, sequence, arrangement = base+0x1000, base+0x8000, base+0xb000
        music_work, fx_work = base+0xc000, base+0xc040
        def put(address, fmt, *values):
            struct.pack_into(fmt, data, address-base, *values)
        put(base, '>II', params, sequence)
        for sound_id, flags, work in ((1130, 0x20, music_work), (1134, 0xe0, fx_work)):
            put(params+sound_id*12, '>BBHHHI', flags, 0, 0, 58, 0, work)
            put(work+8, '>I', 2)
        put(sequence+8, '>BBHI', 1, 0, 0, 2)
        put(sequence+0x118, '>I', arrangement)
        put(sequence+0xeb0, '>B', 23)
        put(info['fader']+23*0x30, '>f', 1.)
        put(info['reverb_parameters'], '>6f', 0, 1, 3, 0, .1, 0)
        memory = Mock()
        memory.read.side_effect = lambda address, size: bytes(data[address-base:address-base+size])
        memory.u32.side_effect = lambda address: struct.unpack('>I', memory.read(address, 4))[0]
        memory.f32.side_effect = lambda address: struct.unpack('>f', memory.read(address, 4))[0]
        state = MusicState.__new__(MusicState)
        state.kind, state.info = 'colosseum', info
        state.colsongs = {hashlib.sha256(bytes(128)).hexdigest(): 'title_song'}
        state.native_only, state.failures = {}, []
        descriptions = state.describe(memory)
        self.assertEqual([(d['sound_id'], d['group']) for d in descriptions], [(1130, 23)])
        self.assertEqual(state.native_only, {})
        self.assertEqual(state.failures, [])

    def test_fanfare_finishes_on_music_clock_after_native_handle_retires(self):
        state = stream_state()
        description = {'key': 1, 'name': 'stm_me_test', 'sound_id': 4, 'gain': 1, 'sdk_ids': [1, 2]}
        state.sync([description], 0)
        state.render(2)
        state.sync([], .02)
        self.assertTrue(state.voices[1]['native_stopped'])
        self.assertEqual(list(state.render(2)[::2]), [300, 400])
        state.sync([], .04)
        self.assertFalse(state.voices)

    def test_xd_same_session_checkpoint_reloads_exact_phase_twice(self):
        state = stream_state()
        description = {'key': 1, 'name': 'stm_me_test', 'sound_id': 4, 'gain': 1, 'sdk_ids': [1, 2]}
        state.sync([description], 0)
        state.render(2)
        state.remember_timeline(100)
        expected = state.render(2)
        for _ in range(2):
            state.reset_timeline(2, 100)
            self.assertEqual(state.render(2), expected)

    def test_unknown_checkpoint_requires_native_fallback(self):
        state = stream_state()
        with self.assertRaisesRegex(RuntimeError, 'native audio restored'):
            state.reset_timeline(2, 200)


class SessionTests(unittest.TestCase):
    def test_changed_endpoint_restores_native_audio_without_terminating_owned_child(self):
        process = Mock(); process.poll.return_value = None
        metadata = {'kind': 'xd', 'game_id': 'GXXP01', 'revision': 0, 'vi': 0x80001000}
        memory, state, output = Mock(), Mock(), Mock()
        output.matches_default_endpoint.return_value = False
        volume = Mock(); volume.sample.return_value = (1., 1.)
        session = MusicSession(process, 'unused', metadata, 'unused',
            memory_factory=Mock(return_value=memory), output_factory=Mock(return_value=output),
            state_factory=Mock(return_value=state), volume_factory=Mock(return_value=volume))
        with patch('orre_randomizer.native_music_resources.MusicAssets',
                   return_value=Mock(game_id='GXXP01', revision=0)), \
             patch('orre_randomizer.play_music.time.monotonic', side_effect=[0., 0., 0., 2.]):
            session._run()
        self.assertEqual(session.error, 'Dolphin audio output changed; native audio restored')
        self.assertFalse(session.active)
        output.matches_default_endpoint.assert_called_once()
        output.clear.assert_called_once()
        output.close.assert_called_once()
        memory.put.assert_called_once_with(0, 0)
        memory.close.assert_called_once()
        state.render.assert_not_called()
        output.submit.assert_not_called()
        process.terminate.assert_not_called()

    def test_prerecorded_movie_clears_host_queue_and_keeps_native_lease_disabled(self):
        process = Mock()
        process.poll.side_effect = [None, None, None, 0]
        metadata = {'kind': 'xd', 'game_id': 'GXXP01', 'revision': 0, 'vi': 0x80001000}
        memory = Mock()
        memory.u32.return_value = 100
        state = Mock()
        state.cinema.return_value = True
        output = Mock()
        session = MusicSession(process, 'unused', metadata, 'unused', memory_factory=Mock(return_value=memory),
            output_factory=Mock(return_value=output), state_factory=Mock(return_value=state),
            volume_factory=Mock(return_value=Mock(sample=Mock(return_value=(1., 1.)))))
        with patch('orre_randomizer.native_music_resources.MusicAssets', return_value=Mock(game_id='GXXP01', revision=0)):
            session._run()
        self.assertIsNone(session.error)
        state.render.assert_not_called()
        state.describe.assert_not_called()
        state.sync.assert_called_once()
        self.assertEqual(state.sync.call_args.kwargs, {'render': False})
        self.assertGreaterEqual(output.clear.call_count, 1)
        self.assertTrue(all(call.args == (0, 0) for call in memory.put.call_args_list))
        process.terminate.assert_not_called()

    def test_renderer_failure_disables_lease_closes_output_and_keeps_child_alive(self):
        process = Mock()
        process.poll.return_value = None
        metadata = {'kind': 'xd', 'game_id': 'GXXP01', 'revision': 0, 'vi': 0x80001000}
        memory = Mock()
        memory.u32.return_value = 100
        state = Mock()
        state.voices = {}
        state.cinema.return_value = False
        state.describe.return_value = []
        state.render.side_effect = ValueError('Decoder rejected resource')
        output = Mock()
        output.frames = 640
        output.poll.return_value = 1
        factory = Mock(return_value=state)
        session = MusicSession(process, 'unused', metadata, 'unused', memory_factory=Mock(return_value=memory),
            output_factory=Mock(return_value=output), state_factory=factory,
            volume_factory=Mock(return_value=Mock(sample=Mock(return_value=(1., 1.)))))
        assets = Mock(game_id='GXXP01', revision=0)
        with patch('orre_randomizer.native_music_resources.MusicAssets', return_value=assets):
            session._run()
        self.assertEqual(session.error, 'Decoder rejected resource')
        self.assertFalse(session.active)
        self.assertEqual(memory.put.call_args.args, (0, 0))
        memory.close.assert_called_once()
        output.close.assert_called_once()
        state.close.assert_called_once()
        process.terminate.assert_not_called()

    def test_pcm_inherits_dolphin_volume_or_mute_in_addition_to_common_half_gain(self):
        for gains in ((.11, .11), (0., 0.), (.11, .055)):
            with self.subTest(gains=gains):
                process = Mock(); process.poll.side_effect = [None, None, None, 0]
                metadata = {'kind':'xd','game_id':'GXXP01','revision':0,'vi':0x80001000}
                memory = Mock(); memory.u32.return_value = 100
                state = Mock(); state.voices = {}; state.cinema.return_value = False; state.describe.return_value = []
                state.render.return_value = array('h', [10000, -20000])
                output = Mock(); output.frames = 1; output.poll.return_value = 1
                volume = Mock(); volume.sample.return_value = gains
                session = MusicSession(process,'unused',metadata,'unused',memory_factory=Mock(return_value=memory),
                    output_factory=Mock(return_value=output),state_factory=Mock(return_value=state),volume_factory=Mock(return_value=volume),
                    native_output_gain=.5)
                with patch('orre_randomizer.native_music_resources.MusicAssets',return_value=Mock(game_id='GXXP01',revision=0)):
                    session._run()
                actual = array('h'); actual.frombytes(output.submit.call_args.args[0])
                self.assertEqual(actual, array('h', [round(10000*.5*gains[0]),round(-20000*.5*gains[1])]))
                self.assertIsNone(session.error)
                volume.close.assert_called_once()
                process.terminate.assert_not_called()


class SessionGainTests(unittest.TestCase):
    def test_single_owned_session_gain_is_attenuation_only_and_mute_is_inherited(self):
        row = {'single_process':True,'master':.11,'muted':False,'channels':[1., .5]}
        self.assertEqual(session_gains([row]), (.11,.055))
        row['muted'] = True
        self.assertEqual(session_gains([row]), (0.,0.))
        row.update(muted=False,channels=[.5])
        self.assertEqual(session_gains([row]), (.055,.055))

    def test_missing_ambiguous_cross_process_or_invalid_gain_requires_native_fallback(self):
        row = {'single_process':True,'master':1.,'muted':False,'channels':[1.,1.]}
        with self.assertRaises(AudioSessionPending):
            session_gains([])
        for rows in ([row,row], [dict(row,single_process=False)], [dict(row,master=2)],
                     [dict(row,master=float('nan'))], [dict(row,channels=[])], [dict(row,channels=[-1])]):
            with self.assertRaises(ValueError):
                session_gains(rows)


if __name__ == '__main__':
    unittest.main()
