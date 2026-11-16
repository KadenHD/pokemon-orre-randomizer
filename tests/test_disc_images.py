"""Real bundled codec conversions, without ROMs or an external executable."""
import hashlib
import itertools
from pathlib import Path
import random
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from types import SimpleNamespace

from orre_randomizer import disc_images, service


@unittest.skipUnless(disc_images.library_path().is_file(), "Build native libraries first")
class DiscImageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "Été 日本語.iso"
        # Valid raw-disc container, intentionally not a playable or copyrighted ROM.
        self.data = bytearray(2 * 1024**2)
        self.data[:6] = b"GC6E01"
        struct.pack_into(">I", self.data, 0x1c, 0xc2339f3d)
        self.data[0x20000:0x40000] = random.Random(42).randbytes(0x20000)
        self.source.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).digest()
        self.cancel = threading.Event()

    def test_all_nine_input_output_combinations_preserve_every_byte(self):
        sources = {"ISO": self.source}
        for value in ("GCM", "RVZ"):
            sources[value] = self.root / ("entrée." + value.lower())
            disc_images.convert(self.source, sources[value], self.cancel)
        with patch("subprocess.Popen", side_effect=AssertionError("No external process allowed")):
            for input_format, output_format in itertools.product(disc_images.FORMATS, repeat=2):
                with self.subTest(input=input_format, output=output_format):
                    output = self.root / (input_format + "-sortie." + output_format.lower())
                    progress = []
                    disc_images.convert(sources[input_format], output, self.cancel,
                        lambda done, total: progress.append((done, total)))
                    raw = output
                    if output_format == "RVZ":
                        raw = output.with_name(output.stem + "-verified.gcm")
                        disc_images.convert(output, raw, self.cancel)
                    self.assertEqual(hashlib.sha256(raw.read_bytes()).digest(), self.digest)
                    self.assertEqual(progress[-1], (len(self.data), len(self.data)))
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_existing_output_and_source_alias_are_never_overwritten(self):
        target = self.root / "keep.rvz"
        target.write_bytes(b"existing data")
        for path in (target, self.source):
            with self.assertRaises(disc_images.DiscError):
                disc_images.convert(self.source, path, self.cancel)
        self.assertEqual(target.read_bytes(), b"existing data")
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_public_pipeline_supports_all_nine_pairs_for_each_game(self):
        sources = {"ISO": self.source}
        for value in ("GCM", "RVZ"):
            sources[value] = self.root / ("source." + value.lower())
            disc_images.convert(self.source, sources[value], self.cancel)
        # Only game tables/identity are synthetic. Real conversion, copying,
        # byte verification, report publication and cleanup run unchanged.
        from orre_randomizer.xd import XDOptions
        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "ISO_SIZE", len(self.data)))
            stack.enter_context(patch.object(service, "check_header", return_value=b"synthetic"))
            stack.enter_context(patch.object(service, "check_disc_identity",
                return_value=SimpleNamespace(game_id="GC6E01", revision=0)))
            stack.enter_context(patch.object(service, "build_patches", return_value=([], {})))
            stack.enter_context(patch.object(service, "build_xd_patches", return_value=([], {})))
            stack.enter_context(patch.object(service, "render_journal", return_value="<html></html>"))
            stack.enter_context(patch("subprocess.Popen", side_effect=AssertionError("External process")))
            for is_xd, input_format, output_format in itertools.product((False, True), disc_images.FORMATS, disc_images.FORMATS):
                with self.subTest(xd=is_xd, input=input_format, output=output_format):
                    target = self.root / (f"{is_xd}-{input_format}." + output_format.lower())
                    report = service.randomize(sources[input_format], target, "conversion-test",
                        service.Options.none(), xd_options=XDOptions.unchanged() if is_xd else None)
                    self.assertEqual(report["output_iso_sha256"], self.digest.hex())
                    self.assertTrue(report["source_unchanged"] and report["all_output_iso_bytes_verified"])
                    self.assertEqual(report["rvz_roundtrip_verified"], output_format == "RVZ")
                    self.assertEqual(report["disc_converter"], disc_images.BACKEND)
                    self.assertTrue(target.with_suffix(target.suffix + ".json").is_file())
                    self.assertTrue(target.with_suffix(target.suffix + ".html").is_file())
                    self.assertFalse(list(self.root.glob(".orre-*")))

    def test_cancellation_cleans_only_its_partial_output_for_both_writers(self):
        sentinel = self.root / "keep.txt"
        sentinel.write_bytes(b"untouched")
        for extension in ("rvz", "iso"):
            with self.subTest(extension=extension):
                self.cancel.clear()
                target = self.root / ("cancelled." + extension)
                def stop(done, total):
                    if done > 0:
                        self.cancel.set()
                with self.assertRaises(disc_images.DiscCancelled):
                    disc_images.convert(self.source, target, self.cancel, stop)
                self.assertFalse(target.exists())
        self.assertEqual(self.source.read_bytes(), self.data)
        self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_invalid_and_truncated_images_leave_no_output(self):
        target = self.root / "invalid.gcm"
        for content in (b"RVZ\x01", b"not a ROM", bytes(4096)):
            self.source.write_bytes(content)
            with self.assertRaises(disc_images.DiscError):
                disc_images.convert(self.source, target, self.cancel)
            self.assertFalse(target.exists())
            self.assertEqual(self.source.read_bytes(), content)

    def test_callback_error_cancels_native_job_and_is_rethrown(self):
        target = self.root / "callback.rvz"
        def fail(done, total):
            if done:
                raise RuntimeError("UI callback failed")
        with self.assertRaisesRegex(RuntimeError, "UI callback failed"):
            disc_images.convert(self.source, target, self.cancel, fail)
        self.assertFalse(target.exists())

    def test_service_never_launches_a_process_or_writes_a_dolphin_profile(self):
        target = self.root / "converted.rvz"
        with patch("subprocess.Popen", side_effect=AssertionError("external converter")):
            service.convert(None, self.source, target, self.root, self.cancel)
        self.assertEqual(set(self.root.iterdir()), {self.source, target})

    def test_service_cancellation_and_missing_library_are_actionable(self):
        target = self.root / "missing.rvz"
        self.cancel.set()
        with self.assertRaises(service.Cancelled):
            service.convert(None, self.source, target, self.root, self.cancel)
        self.cancel.clear()
        with patch.object(disc_images, "library_path", return_value=self.root / "absent.dll"), \
             patch.object(disc_images, "library", side_effect=disc_images.DiscError("missing")):
            with self.assertRaisesRegex(service.UserError, "convertisseur intégré"):
                service.convert(None, self.source, target, self.root, self.cancel)
        self.assertFalse(target.exists())
