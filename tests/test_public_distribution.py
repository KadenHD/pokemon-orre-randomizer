"""Release media must match the explicit interface-pack allowlist."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME
from scripts import build_desktop, verify_release
from scripts.release_media import DOCUMENTATION_IMAGES, documentation_media


class PublicDistributionTests(unittest.TestCase):
    def test_default_archive_includes_exact_verified_interface_pack(self):
        pack = build_desktop.ROOT / "orre_randomizer/assets/game"
        manifest = json.loads((pack / "provenance.json").read_text("utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "release.zip"
            build_desktop.zip_sources(destination)
            with zipfile.ZipFile(destination) as archive:
                prefix = f"{REPOSITORY_NAME}/orre_randomizer/assets/game/"
                actual = {name.removeprefix(prefix) for name in archive.namelist() if name.startswith(prefix)}
                self.assertEqual(actual, set(manifest["files"]) | {"provenance.json"})
                for name, expected in manifest["files"].items():
                    payload = archive.read(prefix + name)
                    self.assertEqual(len(payload), expected["bytes"])
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), expected["sha256"])

    def test_pack_with_unlisted_file_is_rejected(self):
        pack = build_desktop.ROOT / "orre_randomizer/assets/game"
        original = Path.rglob
        def with_extra(path, pattern):
            yield from original(path, pattern)
            if path == pack:
                yield pack / "undeclared.wav"
        with patch.object(Path, "rglob", with_extra):
            with self.assertRaisesRegex(RuntimeError, "Unlisted files"):
                build_desktop.source_files()

    def test_public_source_list_excludes_local_game_media_and_native_dll(self):
        files = build_desktop.source_files(include_game_assets=False)
        self.assertTrue(any(path.name == "gui.py" for path in files))
        for path in files:
            relative = path.relative_to(build_desktop.ROOT).as_posix()
            self.assertNotIn("assets/game/", relative)
            if relative not in {"docs/images/" + name for name in DOCUMENTATION_IMAGES} | {"orre_randomizer/assets/app/icon.png", "orre_randomizer/assets/app/icon.ico",
                                "orre_randomizer/assets/app/logo.png"}:
                self.assertNotIn(path.suffix.lower(), {".iso", ".rvz", ".fsys", ".raw", ".sav", ".png", ".ico", ".wav", ".dll"})

    def test_documentation_media_rejects_tampering_and_unknown_names(self):
        root = build_desktop.ROOT / "docs/images"
        read = lambda name: (root / name).read_bytes()
        self.assertEqual(documentation_media(read), DOCUMENTATION_IMAGES | {"manifest.json"})
        with self.assertRaisesRegex(RuntimeError, "Invalid documentation screenshot"):
            documentation_media(lambda name: b"changed" if name == "home.png" else read(name))
        manifest = json.loads(read("manifest.json"))
        manifest["files"]["private.png"] = manifest["files"]["home.png"]
        with self.assertRaisesRegex(RuntimeError, "Unexpected documentation screenshots"):
            documentation_media(lambda name: json.dumps(manifest).encode() if name == "manifest.json" else read(name))

    def test_public_media_exception_is_limited_to_exact_application_branding(self):
        for binary, prefix in ((False, f"{REPOSITORY_NAME}/"), (True, f"{APP_EXECUTABLE}/_internal/")):
            self.assertTrue(verify_release.application_media_allowed(prefix + "orre_randomizer/assets/app/icon.ico", binary))
            self.assertTrue(verify_release.application_media_allowed(prefix + "orre_randomizer/assets/app/logo.png", binary))
            self.assertEqual(verify_release.application_media_allowed(prefix + "orre_randomizer/assets/app/icon.png", binary), not binary)
            for relative in ("orre_randomizer/assets/game/icon.ico", "orre_randomizer/assets/app/pokemon.png",
                             "orre_randomizer/assets/app/nested/icon.ico", "other/icon.ico"):
                self.assertFalse(verify_release.application_media_allowed(prefix + relative, binary))

    def test_public_source_list_does_not_read_a_pack_manifest(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("pack was read")):
            build_desktop.source_files(include_game_assets=False)

    def test_public_archive_contains_code_and_ci_without_the_local_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "public.zip"
            build_desktop.zip_sources(destination, include_game_assets=False)
            with zipfile.ZipFile(destination) as archive:
                names = archive.namelist()
                self.assertIn(f"{REPOSITORY_NAME}/orre_randomizer/gui.py", names)
                self.assertIn(f"{REPOSITORY_NAME}/.github/workflows/tests.yml", names)
                self.assertIn(f"{REPOSITORY_NAME}/.github/workflows/package.yml", names)
                self.assertIn(f"{REPOSITORY_NAME}/orre_randomizer/assets/app/icon.ico", names)
                self.assertIn(f"{REPOSITORY_NAME}/orre_randomizer/assets/app/icon.png", names)
                self.assertIn(f"{REPOSITORY_NAME}/orre_randomizer/assets/app/logo.png", names)
                self.assertIn(f"{REPOSITORY_NAME}/orre_randomizer/assets/app/logo.json", names)
                self.assertFalse(any("/assets/game/" in name for name in names))
                self.assertIsNone(archive.testzip())


if __name__ == "__main__":
    unittest.main()
