"""Offline, atomic preparation of both original HD author archives."""
from dataclasses import replace
import errno
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from orre_randomizer.hd_packs import Pack, Part
from orre_randomizer.service import Cancelled
from scripts import prepare_hd_hosting as hosting


class HostingPreparation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "review-bundle"
        self.sources = {}
        self.packs = {}
        for game, version in (("colosseum", "2.00"), ("xd", "1.0")):
            source = self.root / (game + ".zip")
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(f"{game}/tex1_4x4_abcd_6.png", game.encode() * 128)
            data = source.read_bytes()
            part = Part("", hashlib.sha256(data).hexdigest(), len(data), game + " author.zip")
            self.sources[game] = source
            self.packs[game] = Pack(game, version, len(data), (part,), author=game + " author",
                                    source="https://author.example/" + game,
                                    archive_source="https://author.example/" + game + ".zip",
                                    excluded_paths=(game + "/excluded.dds",))
        catalog = patch.object(hosting, "PACKS", self.packs)
        catalog.start()
        self.addCleanup(catalog.stop)

    def prepare(self, **kwargs):
        return hosting.prepare_hosting(self.sources["colosseum"], self.sources["xd"], self.output, **kwargs)

    def assert_no_stage(self):
        self.assertEqual(list(self.root.glob(".review-bundle.staging-*")), [])

    def test_both_original_archives_and_metadata_are_prepared_without_network(self):
        originals = {game: source.read_bytes() for game, source in self.sources.items()}
        with patch("urllib.request.urlopen", side_effect=AssertionError("Offline tool made a network request")):
            result = self.prepare()
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), result)
        self.assertFalse(result["production_configured"])
        self.assertFalse(result["published"])
        self.assertIsNone(result["proposed_base_url"])
        self.assertEqual([item["game"] for item in result["packs"]], ["colosseum", "xd"])
        for item in result["packs"]:
            pack = self.packs[item["game"]]
            self.assertEqual(item["archive_filename"], pack.parts[0].filename)
            self.assertEqual(item["relative_path"], f"packs/{pack.game}/{pack.version}/{item['sha256'][:12]}.zip")
            self.assertEqual(item["excluded_paths"], list(pack.excluded_paths))
            self.assertEqual(item["author"], pack.author)
            self.assertEqual(item["source"], pack.source)
            self.assertEqual(item["archive_source"], pack.archive_source)
            self.assertNotIn("proposed_download_url", item)
            self.assertEqual((self.output / item["relative_path"]).read_bytes(), originals[pack.game])
            self.assertEqual(self.sources[pack.game].read_bytes(), originals[pack.game])
        readme = (self.output / "README.md").read_text(encoding="utf-8")
        self.assertIn("No production hosting is configured", readme)
        self.assertIn("Sephie", readme)
        self.assertIn("mikeyX", readme)
        self.assertIn("CC BY-NC-SA 4.0", readme)
        self.assertIn("appropriate permissions", readme)
        self.assert_no_stage()

    def test_same_volume_archives_are_hardlinked_without_copying(self):
        with patch.object(hosting, "_copy_archive", side_effect=AssertionError("Unexpected archive copy")):
            result = self.prepare()
        for item in result["packs"]:
            self.assertEqual(item["storage"], "hardlink")
            self.assertTrue(self.sources[item["game"]].samefile(self.output / item["relative_path"]))

    def test_invalid_second_archive_leaves_no_output_or_staging_directory(self):
        pack = self.packs["xd"]
        self.packs["xd"] = replace(pack, parts=(replace(pack.parts[0], sha256="0" * 64),))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.prepare()
        self.assertFalse(os.path.lexists(self.output))
        self.assert_no_stage()

    def test_wrong_size_is_rejected_before_staging(self):
        pack = self.packs["xd"]
        self.packs["xd"] = replace(pack, parts=(replace(pack.parts[0], size=pack.parts[0].size + 1),))
        with self.assertRaisesRegex(ValueError, "size"):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assert_no_stage()

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assert_no_stage()

    def test_copy_fallback_preserves_both_sources(self):
        with patch.object(hosting.os, "link", side_effect=OSError(errno.EXDEV, "different volume")):
            result = self.prepare()
        for item in result["packs"]:
            source, copied = self.sources[item["game"]], self.output / item["relative_path"]
            self.assertEqual(item["storage"], "copy")
            self.assertFalse(source.samefile(copied))
            self.assertEqual(source.read_bytes(), copied.read_bytes())

    def test_cancelled_copy_cleans_stage_and_keeps_sources(self):
        cancel = threading.Event()
        originals = {game: path.read_bytes() for game, path in self.sources.items()}
        def unavailable_link(*args, **kwargs):
            cancel.set()
            raise OSError(errno.EXDEV, "different volume")
        with patch.object(hosting.os, "link", side_effect=unavailable_link):
            with self.assertRaises(Cancelled):
                self.prepare(cancel=cancel)
        self.assertFalse(self.output.exists())
        self.assert_no_stage()
        for game, path in self.sources.items():
            self.assertEqual(path.read_bytes(), originals[game])

    def test_copy_failure_cleans_an_already_staged_first_archive(self):
        real_link = os.link
        calls = 0
        def second_link_fails(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError(errno.EXDEV, "different volume")
            return real_link(*args, **kwargs)
        with patch.object(hosting.os, "link", side_effect=second_link_fails):
            with patch.object(hosting, "_copy_archive", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    self.prepare()
        self.assertFalse(self.output.exists())
        self.assert_no_stage()
        self.assertTrue(all(path.is_file() for path in self.sources.values()))

    def test_optional_https_urls_are_proposals_only(self):
        result = self.prepare(base_url="https://storage.example/review/")
        self.assertEqual(result["proposed_base_url"], "https://storage.example/review")
        self.assertFalse(result["production_configured"])
        for item in result["packs"]:
            self.assertEqual(item["proposed_download_url"], "https://storage.example/review/" + item["relative_path"])
        self.assertIn("not deployed", (self.output / "README.md").read_text(encoding="utf-8"))

    def test_invalid_base_url_and_catalog_paths_never_create_output(self):
        for value in ("http://storage.example", "https://user:password@storage.example",
                      "https://storage.example/?token=1", "https://storage.example/#fragment",
                      "https://storage.example/?", "https://storage.example/#"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prepare(base_url=value)
        self.packs["xd"] = replace(self.packs["xd"], version="../outside")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assert_no_stage()

    def test_concurrent_empty_output_is_not_replaced(self):
        real_publish = hosting._publish
        observed = []
        def concurrent_directory(stage, output):
            output.mkdir()
            observed.append(output.stat().st_ino)
            real_publish(stage, output)
        with patch.object(hosting, "_publish", side_effect=concurrent_directory):
            with self.assertRaises(FileExistsError):
                self.prepare()
        self.assertEqual(self.output.stat().st_ino, observed[0])
        self.assertEqual(list(self.output.iterdir()), [])
        self.assert_no_stage()

    def test_windows_access_denied_on_existing_directory_is_a_collision(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        error = PermissionError(errno.EACCES, "Access denied", str(self.output))
        error.winerror = 5
        with patch.object(hosting.os, "name", "nt"), \
             patch.object(hosting.os, "rename", side_effect=error):
            with self.assertRaises(FileExistsError) as caught:
                hosting._publish(self.root / "stage", self.output)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_windows_access_denied_without_a_target_remains_an_access_error(self):
        error = PermissionError(errno.EACCES, "Access denied", str(self.output))
        error.winerror = 5
        with patch.object(hosting.os, "name", "nt"), \
             patch.object(hosting.os, "rename", side_effect=error) as rename, \
             patch.object(hosting.time, "monotonic", side_effect=(100, 106)):
            with self.assertRaises(PermissionError) as caught:
                hosting._publish(self.root / "stage", self.output)
        self.assertIs(caught.exception, error)
        rename.assert_called_once()
        self.assertFalse(self.output.exists())

    def test_windows_transient_lock_retries_atomic_publication(self):
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "keep.txt").write_text("prepared archive")
        original = os.rename
        error = PermissionError(errno.EACCES, "Temporary sharing lock")
        error.winerror = 32
        calls = []

        def rename(source, destination):
            calls.append(source)
            if len(calls) == 1:
                raise error
            original(source, destination)

        with patch.object(hosting.os, "name", "nt"), \
             patch.object(hosting.os, "rename", side_effect=rename), \
             patch.object(hosting.time, "sleep") as wait:
            hosting._publish(stage, self.output)
        self.assertEqual(len(calls), 2)
        wait.assert_called_once_with(.1)
        self.assertEqual((self.output / "keep.txt").read_text(), "prepared archive")
        self.assertFalse(stage.exists())

    def test_symlink_source_and_parent_are_refused(self):
        linked = self.root / "source-link.zip"
        try:
            linked.symlink_to(self.sources["xd"])
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlink creation is unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "Symbolic links"):
            hosting.prepare_hosting(self.sources["colosseum"], linked, self.output)
        parent = self.root / "parent-link"
        parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symbolic links"):
            hosting.prepare_hosting(self.sources["colosseum"], self.sources["xd"], parent / "nested")
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "nested").exists())
        self.assert_no_stage()


if __name__ == "__main__":
    unittest.main()
