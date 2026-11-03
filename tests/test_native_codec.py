import random
import struct
import unittest
import threading
from colosseum_randomizer import native_codec
from colosseum_randomizer.engine.analyze_game import decompress_lzss_python, FormatError
from colosseum_randomizer.engine.rebuild_iso import compress_lzss_python


@unittest.skipIf(native_codec.library() is None, "optional Rust codec is not built")
class NativeCodecTests(unittest.TestCase):
    def test_byte_identical_against_independent_python_encoder(self):
        rng = random.Random(71483)
        cases = [b"", b"a", b"ab", b"abc", bytes(20000), b"A" * 12000,
                 b"abcabcabc" * 2000, bytes(range(256)) * 60]
        cases += [rng.randbytes(size) for size in (3, 17, 19, 128, 4095, 4096, 4097, 12000)]
        for raw in cases:
            expected = compress_lzss_python(raw)
            self.assertEqual(native_codec.compress(raw), expected)
            self.assertEqual(native_codec.decompress(expected, 64 * 1024 * 1024), raw)
            self.assertEqual(decompress_lzss_python(native_codec.compress(raw)), raw)

    def test_zero_ring_and_overlapping_references(self):
        for size, payload, expected in ((3, b"\0\xee\xf0", b"\0" * 3),
                                        (9, b"\7abc\xee\xf3", b"abcabcabc"),
                                        (32, b"\1A\xee\xff\xee\xfa", b"A" * 32)):
            stream = b"LZSS" + struct.pack(">III", size, 16 + len(payload), 0) + payload
            self.assertEqual(native_codec.decompress(stream, 64), expected)

    def test_malformed_streams_rejected_like_reference(self):
        valid = compress_lzss_python(b"abcdef" * 20)
        cases = [valid[:i] for i in range(len(valid))] + [valid + b"\0"]
        rng = random.Random(419)
        for _ in range(100):
            payload = rng.randbytes(rng.randrange(20))
            cases.append(b"LZSS" + struct.pack(">III", rng.randrange(30), 16 + len(payload), 0) + payload)
        for encoded in cases:
            try:
                expected = decompress_lzss_python(encoded, 1024)
            except FormatError:
                with self.assertRaises(ValueError):
                    native_codec.decompress(encoded, 1024)
            else:
                self.assertEqual(native_codec.decompress(encoded, 1024), expected)

    def test_native_call_cancels_inside_the_encoder_and_context_does_not_leak(self):
        class CancelDuringCompression:
            calls = 0
            def is_set(self):
                self.calls += 1
                return self.calls >= 5
        event = CancelDuringCompression()
        self.assertTrue(hasattr(native_codec.library(), 'colosseum_compress_cancellable'))
        with native_codec.cancellation_scope(event):
            with self.assertRaises(native_codec.CodecCancelled):
                native_codec.compress(b'ABCD' * 65536)
        self.assertGreaterEqual(event.calls, 5)
        self.assertEqual(native_codec.compress(b'abc'), compress_lzss_python(b'abc'))

    def test_live_cancellable_path_remains_bit_identical(self):
        data = bytes(range(256)) * 130
        with native_codec.cancellation_scope(threading.Event()):
            self.assertEqual(native_codec.compress(data), compress_lzss_python(data))


class CodecCancellationTests(unittest.TestCase):
    def test_python_fallback_can_stop_during_compression(self):
        class CancelDuringCompression:
            calls = 0
            def is_set(self):
                self.calls += 1
                return self.calls >= 5
        event = CancelDuringCompression()
        with native_codec.cancellation_scope(event):
            with self.assertRaises(native_codec.CodecCancelled):
                compress_lzss_python(b'ABCD' * 65536)
        self.assertGreaterEqual(event.calls, 5)

    def test_service_translates_codec_cancellation_to_normal_cancelled_outcome(self):
        from colosseum_randomizer import service
        @service._cancellable_compression
        def operation(iso, boot, seed, options, progress, cancel):
            cancel.set()
            return compress_lzss_python(b'abc')
        with self.assertRaises(service.Cancelled):
            operation(None, None, None, None, None, threading.Event())
        self.assertEqual(compress_lzss_python(b'abc')[16:], b'\x07abc')


if __name__ == "__main__":
    unittest.main()
