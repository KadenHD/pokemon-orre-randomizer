"""Public pipeline safety checks; no ROM or emulator needed for this suite."""
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

from colosseum_randomizer import service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.iso"
        self.source.write_bytes(b"original")
        self.output = self.root / "output.iso"
        self.event = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def test_source_and_aliases_refused(self):
        for target in (self.source, self.root / "." / "source.iso"):
            with self.assertRaises(service.UserError):
                service.validate_paths(self.source, target, "seed", None)
        alias = self.root / "alias.iso"
        try:
            os.link(self.source, alias)
        except OSError:
            # Restricted Windows test runners may prohibit hardlinks altogether.
            alias.write_bytes(b"alias")
        with self.assertRaises(service.UserError):
            service.validate_paths(self.source, alias, "seed", None)
        self.assertEqual(self.source.read_bytes(), b"original")

    def test_existing_rom_or_report_never_overwritten(self):
        for target in (self.output, self.output.with_suffix(".iso.json")):
            target.write_bytes(b"keep")
            with self.assertRaises(service.UserError):
                service.validate_paths(self.source, self.output, "seed", None)
            self.assertEqual(target.read_bytes(), b"keep")
            target.unlink()

    def test_empty_and_oversized_seed_refused_but_unicode_preserved(self):
        for seed in ("", "   ", "é" * 129):
            with self.assertRaises(service.UserError):
                service.validate_paths(self.source, self.output, seed, None)
        service.validate_paths(self.source, self.output, "été 🎲", None)

    def test_rvz_requires_external_converter(self):
        with self.assertRaises(service.UserError):
            service.validate_paths(self.source, self.output.with_suffix(".rvz"), "seed", None)

    def test_invalid_header_leaves_no_output_or_temp(self):
        before = set(self.root.iterdir())
        with self.assertRaises(service.UserError):
            service.randomize(self.source, self.output, "seed")
        self.assertEqual(set(self.root.iterdir()), before)

    def test_pre_cancelled_job_leaves_source_and_directory_intact(self):
        self.event.set()
        with self.assertRaises(service.Cancelled):
            service.randomize(self.source, self.output, "seed", cancel=self.event)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_publication_refuses_racing_destination(self):
        self.output.write_bytes(b"another user's file")
        with self.assertRaises(service.UserError):
            service.publish_new(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), b"another user's file")
        self.assertEqual(self.source.read_bytes(), b"original")

    def test_exclusive_fallback_and_partial_cleanup(self):
        with patch.object(service.os, "link", side_effect=OSError("no hardlinks")):
            service.publish_new(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), self.source.read_bytes())
        self.output.unlink()
        with patch.object(service.os, "link", side_effect=OSError("no hardlinks")), \
             patch.object(service.shutil, "copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                service.publish_new(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_publication_input_never_leaves_empty_output(self):
        with patch.object(service.os, "link", side_effect=OSError("no hardlinks")):
            with self.assertRaises(FileNotFoundError):
                service.publish_new(self.root / "missing", self.output)
        self.assertFalse(self.output.exists())

    def test_every_byte_verified_including_untouched_regions(self):
        self.source.write_bytes(bytes(range(64)))
        expected = bytearray(self.source.read_bytes())
        expected[9:13] = b"TEST"
        self.output.write_bytes(expected)
        with patch.object(service, "ISO_SIZE", 64), patch.object(service, "CHUNK", 11):
            digest = service.verify_patches(self.source, self.output, [(9, b"TEST")], lambda *a: None, self.event)
            self.assertEqual(digest, service.sha256(expected))
            expected[50] ^= 1
            self.output.write_bytes(expected)
            with self.assertRaises(service.FormatError):
                service.verify_patches(self.source, self.output, [(9, b"TEST")], lambda *a: None, self.event)

    def test_conversion_failure_and_cancel_cleanup_owned_temp_directory(self):
        source = self.root / "source.rvz"
        source.write_bytes(b"RVZ input")
        tool = self.root / "DolphinTool.exe"
        tool.touch()
        for error in (service.UserError("failed"), service.Cancelled("cancelled")):
            with patch.object(service, "convert", side_effect=error):
                with self.assertRaises(type(error)):
                    service.randomize(source, self.output, "seed", dolphin_tool=tool)
            self.assertFalse(list(self.root.glob(".colosseum-*")))
            self.assertFalse(self.output.exists())
            self.assertEqual(source.read_bytes(), b"RVZ input")


class OptionIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(Path("game/files/common.fsys").exists(), "requires user's local PAL dump")
    def test_all_option_combinations_preserve_evolution_routes(self):
        from colosseum_randomizer.engine.randomize_trainers import original_common, layout
        from colosseum_randomizer.engine.evolution_rules import evolution_families, patch_evolutions
        _, _, original = original_common(Path("game"))
        tables, _ = layout(original)
        family, _ = evolution_families(original, tables)
        _, evolution_plan = patch_evolutions(original, tables)
        for unique in (False, True):
            for accessible in (False, True):
                options = service.Options(unique_shadows=unique, evolve_trade=accessible,
                    evolve_trade_items=accessible, evolve_coquiperl=accessible,
                    evolve_day_night=accessible, evolve_beauty=accessible)
                result, summary = service.transform_rel(original, "été 🎲", options)
                self.assertEqual(evolution_families(result, tables)[0], family)
                self.assertEqual(summary["evolution_edits"], 15 if accessible else 0)
                if unique:
                    self.assertEqual(summary["shadow_families"]["final_distinct_family_count"], 48)
                if not accessible:
                    for edit in evolution_plan["edits"]:
                        pos = edit["record_offset"]
                        self.assertEqual(result[pos:pos + 6], original[pos:pos + 6])


if __name__ == "__main__":
    unittest.main()
