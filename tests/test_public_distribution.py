"""Public packaging must never sweep the local exported game pack into sources."""
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from colosseum_randomizer import APP_EXECUTABLE, REPOSITORY_NAME
from scripts import build_desktop, verify_release


class PublicDistributionTests(unittest.TestCase):
    def test_public_source_list_excludes_local_game_media_and_native_dll(self):
        files = build_desktop.source_files(include_game_assets=False)
        self.assertTrue(any(path.name == "gui.py" for path in files))
        for path in files:
            relative = path.relative_to(build_desktop.ROOT).as_posix()
            self.assertNotIn("assets/game/", relative)
            if relative not in {"colosseum_randomizer/assets/app/icon.png", "colosseum_randomizer/assets/app/icon.ico"}:
                self.assertNotIn(path.suffix.lower(), {".iso", ".rvz", ".fsys", ".raw", ".sav", ".png", ".ico", ".wav", ".dll"})

    def test_public_media_exception_is_limited_to_exact_application_icons(self):
        for binary, prefix in ((False, f"{REPOSITORY_NAME}/"), (True, f"{APP_EXECUTABLE}/_internal/")):
            self.assertTrue(verify_release.application_media_allowed(prefix + "colosseum_randomizer/assets/app/icon.ico", binary))
            self.assertEqual(verify_release.application_media_allowed(prefix + "colosseum_randomizer/assets/app/icon.png", binary), not binary)
            for relative in ("colosseum_randomizer/assets/game/icon.ico", "colosseum_randomizer/assets/app/pokemon.png",
                             "colosseum_randomizer/assets/app/nested/icon.ico", "other/icon.ico"):
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
                self.assertIn(f"{REPOSITORY_NAME}/colosseum_randomizer/gui.py", names)
                self.assertIn(f"{REPOSITORY_NAME}/.github/workflows/tests.yml", names)
                self.assertIn(f"{REPOSITORY_NAME}/.github/workflows/package.yml", names)
                self.assertIn(f"{REPOSITORY_NAME}/colosseum_randomizer/assets/app/icon.ico", names)
                self.assertIn(f"{REPOSITORY_NAME}/colosseum_randomizer/assets/app/icon.png", names)
                self.assertFalse(any("/assets/game/" in name for name in names))
                self.assertIsNone(archive.testzip())


if __name__ == "__main__":
    unittest.main()
