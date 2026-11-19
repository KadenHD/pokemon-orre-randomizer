"""The reviewed set publishes atomically and preserves unrelated interface assets."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.register_extra_portraits import register
from tests.test_hd_extra_portraits import registered_catalog


class RegisterExtraPortraitTests(unittest.TestCase):
    def test_check_only_validates_every_atlas_without_creating_a_destination(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            destination = Path(temporary) / "game-assets"
            register(source, destination, check_only=True)
            self.assertFalse(destination.exists())

    def test_registration_preserves_font_provenance_and_all_original_bytes(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            destination = Path(temporary)
            font = destination / "fonts/font.json"
            font.parent.mkdir()
            font.write_bytes(b"font-original")
            old = {"files": {"fonts/font.json": {"bytes": 13, "sha256": hashlib.sha256(font.read_bytes()).hexdigest()}},
                   "font_metadata": {"native_source": "verified original"}}
            (destination / "provenance.json").write_text(json.dumps(old))
            register(source, destination)
            result = json.loads((destination / "provenance.json").read_text())
            self.assertEqual(result["files"]["fonts/font.json"], old["files"]["fonts/font.json"])
            self.assertEqual(result["font_metadata"], old["font_metadata"])
            self.assertEqual(font.read_bytes(), b"font-original")
            self.assertEqual(len(result["files"]), 11)
            self.assertEqual(len(list((destination / "models/extra-portraits").iterdir())), 10)

    def test_corrupt_last_file_prevents_any_publication(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            last = next(reversed(metadata["files"].values()))["file"]
            (source / last).write_bytes(b"bad")
            destination = Path(temporary) / "game-assets"
            with self.assertRaisesRegex(ValueError, "integrity"):
                register(source, destination)
            self.assertFalse(destination.exists())

    def test_failed_publication_restores_the_global_provenance_and_existing_portrait(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            destination = Path(temporary)
            previous = b'{"files": {}, "fonts": "preserve"}'
            provenance = destination / "provenance.json"
            provenance.write_bytes(previous)
            portraits = destination / "models/extra-portraits"
            portraits.mkdir(parents=True)
            old = portraits / "extra-portraits.json"
            old.write_bytes(b"old registry")
            actual_write = Path.write_bytes
            failed = False

            def fail_once(path, data):
                nonlocal failed
                # Windows runners may expose TEMP through a DOS 8.3 alias.
                if path.resolve() == provenance.resolve() and not failed:
                    failed = True
                    raise OSError("simulated publication failure")
                return actual_write(path, data)

            with patch.object(Path, "write_bytes", fail_once):
                with self.assertRaisesRegex(OSError, "simulated"):
                    register(source, destination)
            self.assertEqual(provenance.read_bytes(), previous)
            self.assertEqual(old.read_bytes(), b"old registry")
            self.assertEqual(list(portraits.iterdir()), [old])


if __name__ == "__main__":
    unittest.main()
