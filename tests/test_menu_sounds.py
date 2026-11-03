"""Bounded DSP decoding, native audio provenance and safe cache publication."""
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from colosseum_randomizer import menu_sounds as sounds


class DSPMenuTests(unittest.TestCase):
    def test_signed_nibbles_scale_and_partial_frame(self):
        frame = bytes.fromhex("02178f0000000000")
        pcm = sounds._decode_dsp(frame, (0,) * 16, 4)
        self.assertEqual(struct.unpack("<4h", pcm), (4, 28, -32, -4))
        self.assertEqual(sounds._decode_dsp(frame, (0,) * 16, 1), struct.pack("<h", 4))

    def test_predictor_history_continues_between_frames_and_clips(self):
        frame = b"\x00" + b"\x11" * 7
        pcm = sounds._decode_dsp(frame * 2, (2048, 0) + (0,) * 14, 28)
        self.assertEqual(struct.unpack("<28h", pcm), tuple(range(1, 29)))
        pcm = sounds._decode_dsp(bytes.fromhex("0f78000000000000"), (0,) * 16, 2)
        self.assertEqual(struct.unpack("<2h", pcm), (32767, -32768))

    def test_malformed_dsp_and_pcm_are_rejected_before_large_allocation(self):
        frame = bytes(8)
        for data, coefs, count in ((frame[:-1], (0,) * 16, 14), (frame * 2, (0,) * 16, 14),
                                   (frame, (0,) * 15, 14), (frame, (40000,) * 16, 14),
                                   (frame, (0,) * 16, 0), (frame, (0,) * 16, True),
                                   (frame, (0,) * 16, 1000000), (b"\x80" + frame[1:], (0,) * 16, 14)):
            with self.subTest(count=count, data=data[:1]), self.assertRaises(sounds.MenuSoundError):
                sounds._decode_dsp(data, coefs, count)
        for pcm, rate in ((b"\0", 44100), (b"\0\0", 0), (b"\0\0", 200000), (b"", 44100)):
            with self.subTest(rate=rate), self.assertRaises(sounds.MenuSoundError):
                sounds._wav(pcm, rate)

    def test_wav_is_standard_mono_pcm16_with_the_native_playback_rate(self):
        pcm = struct.pack("<4h", 1000, -1000, 32767, -32768)
        data = sounds._wav(pcm, 88200)
        with wave.open(io.BytesIO(data)) as reader:
            self.assertEqual((reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.getnframes()),
                             (1, 2, 88200, 4))
            self.assertEqual(reader.readframes(4), pcm)

    def test_interface_gain_is_quarter_amplitude_and_keeps_sample_count(self):
        pcm = struct.pack("<6h", 3, -3, 1000, -1000, 32767, -32768)
        self.assertEqual(struct.unpack("<6h", sounds._quiet_pcm(pcm)), (0, 0, 250, -250, 8191, -8192))
        for invalid in (b"", b"\0", bytes(sounds._MAX_SAMPLES * 2 + 2)):
            with self.assertRaises(sounds.MenuSoundError):
                sounds._quiet_pcm(invalid)


class MenuSoundCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.cache = self.root / "cache"
        self.waves = {key: sounds._wav(bytes(spec[-1] * 2), spec[-2]) for key, spec in sounds._SOUNDS.items()}

    def publish(self):
        with patch.object(sounds, "_disc_files", return_value={}), patch.object(sounds, "_native_wavs", return_value=self.waves):
            return sounds.extract_menu_sounds(self.root / "private-ROM.iso", self.cache)

    def test_atomic_complete_cache_has_no_rom_path_and_survives_restart(self):
        self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})
        paths = self.publish()
        self.assertEqual(set(paths), {"move", "confirm", "back"})
        self.assertEqual(paths, sounds.load_cached_menu_sounds(self.cache))
        manifest = (self.cache / sounds._MANIFEST).read_text()
        self.assertNotIn("private-ROM", manifest)
        self.assertNotIn(str(self.root), manifest)
        self.assertFalse(list(self.cache.glob("*.tmp")))
        for key, path in paths.items():
            self.assertEqual(path.parent, self.cache)
            self.assertEqual(path.read_bytes(), self.waves[key])

    def test_corrupt_truncated_or_oversized_audio_never_loads(self):
        for variant in (b"RIFF", b"\0" * (sounds._MAX_WAV + 1)):
            paths = self.publish()
            paths["move"].write_bytes(variant)
            self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})
        paths = self.publish()
        data = bytearray(paths["confirm"].read_bytes())
        data[-1] ^= 1
        paths["confirm"].write_bytes(data)
        self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})

    def test_bad_manifest_schema_and_path_traversal_never_load(self):
        for mutate in (lambda doc: doc["assets"]["move"].update(file="../outside.wav"),
                       lambda doc: doc["assets"]["move"].update(bytes=True),
                       lambda doc: doc["assets"]["move"].update(sample_rate=44100),
                       lambda doc: doc["assets"].pop("back"),
                       lambda doc: doc.update(version=2),
                       lambda doc: doc.update(gain=[1, 1]),
                       lambda doc: doc.update(extra="unrecognized")):
            self.publish()
            manifest = self.cache / sounds._MANIFEST
            document = json.loads(manifest.read_bytes())
            mutate(document)
            manifest.write_text(json.dumps(document))
            self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})
        manifest.write_bytes(b"x" * (sounds._MAX_MANIFEST + 1))
        self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})
        manifest.write_bytes(b"[" * 2000 + b"0" + b"]" * 2000)
        self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})

    def test_failed_extraction_keeps_existing_cache_manifest(self):
        self.publish()
        manifest = self.cache / sounds._MANIFEST
        before = manifest.read_bytes()
        with patch.object(sounds, "_disc_files", side_effect=sounds.MenuSoundError("unsupported")), self.assertRaises(sounds.MenuSoundError):
            sounds.extract_menu_sounds(self.root / "invalid.iso", self.cache)
        self.assertEqual(manifest.read_bytes(), before)
        with patch.object(sounds, "_disc_files", return_value={}), patch.object(sounds, "_native_wavs", return_value=self.waves), \
                patch.object(sounds.os, "replace", side_effect=OSError("publication refused")), self.assertRaises(sounds.MenuSoundError):
            sounds.extract_menu_sounds(self.root / "source.iso", self.cache)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertFalse(list(self.cache.glob("*.tmp")))

    def test_symlinked_cache_is_never_used_when_host_supports_symlinks(self):
        paths = self.publish()
        alias = self.root / "cache-alias"
        try:
            alias.symlink_to(self.cache, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks require a Windows privilege on this host")
        self.assertEqual(sounds.load_cached_menu_sounds(alias), {})
        original = paths["move"]
        alias_file = self.root / "audio-alias.wav"
        original.rename(alias_file)
        original.symlink_to(alias_file)
        self.assertEqual(sounds.load_cached_menu_sounds(self.cache), {})


class MenuSoundSourceTests(unittest.TestCase):
    def test_unknown_identity_or_unbounded_fst_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            iso = Path(folder) / "small.iso"
            for offset, value in ((None, None), (0x424, 0xFFFFFFF0), (0x428, sounds._MAX_FST + 1)):
                boot = bytearray(0x440)
                if offset is not None:
                    boot[:8] = b"GC6P01\0\0"
                    boot[0x1C:0x20] = bytes.fromhex("c2339f3d")
                    struct.pack_into(">II", boot, 0x424, 0x440, 12)
                    struct.pack_into(">I", boot, offset, value)
                iso.write_bytes(boot)
                with self.subTest(offset=offset), self.assertRaises(sounds.MenuSoundError):
                    sounds.extract_menu_sounds(iso, Path(folder) / "cache")
                self.assertEqual(sounds.load_cached_menu_sounds(Path(folder) / "cache"), {})

    def test_member_size_limits_ranges_and_fingerprint_are_refused(self):
        row = {"name": "snd_se_sdir", "offset": 0, "stored_size": 4, "unpacked_size": 4, "compression": "none"}
        for changes in ({}, {"unpacked_size": 1000000}, {"offset": -1}, {"stored_size": 100}):
            with self.subTest(changes=changes), self.assertRaises(sounds.MenuSoundError):
                sounds._member(b"data", [{**row, **changes}], "snd_se_sdir")


@unittest.skipUnless(Path("Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso").is_file(),
                     "local original PAL ISO is unavailable")
class LocalPALMenuSoundTests(unittest.TestCase):
    def test_original_native_sounds_extract_reproducibly_and_keep_source_metadata(self):
        source = Path("Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso")
        before = source.stat()
        with tempfile.TemporaryDirectory() as folder:
            first = sounds.extract_menu_sounds(source, Path(folder) / "one")
            second = sounds.extract_menu_sounds(source, Path(folder) / "two")
            self.assertEqual(set(first), {"move", "confirm", "back"})
            expected_hashes = {"move": "27e695277e0dea9dadfb002124d223d6ad34de8d9c34ea14f3480afe4097bd24",
                               "confirm": "56289058fd95859c3c78196946367bc190cf46c1b3de0b9e7a66cc7c2adc8139",
                               "back": "27a171cce7c82a87e27708dd98940666e1900b0d68a7a5dd8ad9d5a76cc6f4bd"}
            for key in first:
                self.assertEqual(first[key].read_bytes(), second[key].read_bytes())
                self.assertEqual(sounds._sha(first[key].read_bytes()), expected_hashes[key])
                with wave.open(str(first[key])) as reader:
                    self.assertLess(reader.getnframes() / reader.getframerate(), .25)
        after = source.stat()
        self.assertEqual((after.st_size, after.st_mtime_ns), (before.st_size, before.st_mtime_ns))


if __name__ == "__main__":
    unittest.main()
