"""GitHub transport assets retain both original archive identities."""
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from orre_randomizer.hd_packs import Pack, Part
from orre_randomizer.service import Cancelled
from scripts.prepare_hd_github import prepare_github, GITHUB_ASSET_LIMIT


class GithubAssets(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = {"colosseum": b"PK\x03\x04" + bytes(40), "xd": b"PK\x03\x04" + bytes(range(200))}
        self.sources, self.packs = {}, {}
        for game, data in self.data.items():
            self.sources[game] = self.root / (game + ".zip")
            self.sources[game].write_bytes(data)
            part = Part("", hashlib.sha256(data).hexdigest(), len(data), game + " original.zip")
            self.packs[game] = Pack(game, "test", len(data), (part,), author=game + " author")
        catalog = patch("scripts.prepare_hd_github.PACKS", self.packs)
        catalog.start()
        self.addCleanup(catalog.stop)

    def prepare(self, **kwargs):
        return prepare_github(self.sources["colosseum"], self.sources["xd"], self.root / "review",
            fragment_bytes=100, **kwargs)

    def test_fragments_reassemble_exactly_and_small_archive_is_unchanged(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("Preparation made a network call")):
            result = self.prepare(repository="owner/hd-packs", tag="packs-test")
        self.assertFalse(result["published"])
        self.assertFalse(result["production_configured"])
        for archive in result["archives"]:
            combined = b"".join((self.root / "review" / name).read_bytes() for name in archive["assets"])
            self.assertEqual(combined, self.data[archive["game"]])
            self.assertEqual(hashlib.sha256(combined).hexdigest(), archive["sha256"])
        self.assertEqual(len(result["assets"]), 4)
        for asset in result["assets"]:
            data = (self.root / "review" / asset["name"]).read_bytes()
            self.assertEqual(len(data), asset["size"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), asset["sha256"])
            self.assertLess(asset["size"], GITHUB_ASSET_LIMIT)
            self.assertIn("/releases/download/packs-test/", asset["proposed_url"])
        self.assertTrue((self.root / "review" / "SHA256SUMS").is_file())
        for game, source in self.sources.items():
            self.assertEqual(source.read_bytes(), self.data[game])

    def test_bad_original_never_publishes_any_fragment(self):
        self.sources["xd"].write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse((self.root / "review").exists())

    def test_existing_output_is_preserved(self):
        folder = self.root / "review"
        folder.mkdir()
        (folder / "keep").write_text("original")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual((folder / "keep").read_text(), "original")

    def test_cancel_cleans_only_owned_stage(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            self.prepare(cancel=cancel)
        self.assertFalse((self.root / "review").exists())
        self.assertEqual(list(self.root.glob(".review.staging-*")), [])

    def test_github_limits_and_repository_are_validated_before_writes(self):
        for size in (0, GITHUB_ASSET_LIMIT, True):
            with self.subTest(size=size), self.assertRaises(ValueError):
                prepare_github(self.sources["colosseum"], self.sources["xd"], self.root / "review", fragment_bytes=size)
        with self.assertRaises(ValueError):
            self.prepare(repository="https://github.com/owner/repo", tag="test")
        self.assertFalse((self.root / "review").exists())


if __name__ == "__main__":
    unittest.main()
