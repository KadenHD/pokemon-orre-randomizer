"""Windows bundles must carry the current runtime, sources, and private-free paths."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import build_desktop, verify_release
from scripts.build_music import PIN
from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME


def pe(machine=0x8664):
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, machine)
    return bytes(data)


class WindowsDistributionTests(unittest.TestCase):
    def test_build_dependency_pins_cannot_be_silently_ignored(self):
        with patch.object(build_desktop, "version", return_value="wrong"):
            with self.assertRaisesRegex(RuntimeError, "Build dependency differs"):
                build_desktop.validate_build_dependencies()

    def test_missing_extracted_runner_is_an_incomplete_source_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "missing its test runner"):
                verify_release.verify_source_tests(Path(directory))

    def test_source_tests_execute_the_archived_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts/run_tests.py").write_text(
                "import sys\nprint('ARCHIVED RUNNER EXECUTED', file=sys.stderr)\n", encoding="utf-8")
            self.assertEqual(verify_release.verify_source_tests(root), "ARCHIVED RUNNER EXECUTED")

    def test_pe_architecture_is_checked_without_loading_a_dll(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.dll"
            path.write_bytes(pe())
            build_desktop.validate_pe_x64(path)
            for payload in (pe(0x14c), b"not PE", pe()[:0x82]):
                path.write_bytes(payload)
                with self.assertRaises(RuntimeError):
                    build_desktop.validate_pe_x64(path)

    def test_private_paths_are_rejected_in_text_and_native_encodings(self):
        for prefix in (str(build_desktop.ROOT), build_desktop.ROOT.as_posix(), str(Path.home())):
            for encoding in ("utf-8", "utf-16le"):
                with self.subTest(encoding=encoding):
                    with self.assertRaisesRegex(RuntimeError, "Private build path"):
                        verify_release.reject_private_build_paths(prefix.encode(encoding), "fixture")
        verify_release.reject_private_build_paths(b"orre/src/main.rs; Windows/System32", "fixture")

    def test_required_game_folder_modules_have_real_source_files(self):
        for name in build_desktop.REQUIRED_RUNTIME_MODULES:
            if name.startswith("orre_randomizer."):
                self.assertTrue((build_desktop.ROOT / (name.replace(".", "/") + ".py")).is_file(), name)
            else:
                import importlib.util
                self.assertTrue(name.startswith("sqlite3"), name)
                self.assertIsNotNone(importlib.util.find_spec(name), name)

    def test_native_music_hashes_match_both_binary_and_current_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = root / "orre_randomizer/_native"
            native.mkdir(parents=True)
            music = root / "native/music"
            music.mkdir(parents=True)
            (music / "patches.json").write_text("[]", encoding="utf-8")
            (music / "renderer_adapter.c").write_text("adapter", encoding="utf-8")
            for name in build_desktop.NATIVE_RUNTIME_NAMES:
                (native / name).write_bytes(pe())
            record = {"abi": 1, "source_commit": PIN,
                "renderer_sha256": hashlib.sha256(pe()).hexdigest(),
                "patches_sha256": hashlib.sha256(b"[]").hexdigest(),
                "adapter_sha256": hashlib.sha256(b"adapter").hexdigest()}
            metadata = native / "orre_musyx.json"
            metadata.write_text(json.dumps(record), encoding="utf-8")
            with patch.object(build_desktop, "ROOT", root):
                build_desktop.validate_native_runtime()
                for field in ("renderer_sha256", "patches_sha256", "adapter_sha256", "source_commit"):
                    changed = {**record, field: "stale"}
                    metadata.write_text(json.dumps(changed), encoding="utf-8")
                    with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "stale"):
                        build_desktop.validate_native_runtime()

    def test_build_record_has_no_absolute_paths_and_detects_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["orre_randomizer/example.py", "orre_randomizer/assets/game/provenance.json",
                *["orre_randomizer/_native/" + n for n in (*build_desktop.NATIVE_RUNTIME_NAMES, "orre_musyx.json")],
                "scripts/desktop.spec", "scripts/desktop_entry.py", "scripts/build_desktop.py", "scripts/release_media.py",
                "scripts/build_native.py", "scripts/build_music.py", "pyproject.toml", "requirements-build.txt",
                "native/music/patches.json", "native/music/renderer_adapter.c", "orre_randomizer/windows_update.ps1",
                "orre_randomizer/assets/app/provenance.json", "orre_randomizer/assets/app/logo.json",
                "orre_randomizer/assets/app/controller.json"]
            for folder in ("native", "native/disc", "native/launcher"):
                names += [folder + "/" + name for name in ("Cargo.toml", "Cargo.lock", "src/main.rs")]
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("initial", encoding="utf-8")
            with patch.object(build_desktop, "ROOT", root):
                before = build_desktop.runtime_build_inputs()
                self.assertEqual(set(before["files"]), set(names))
                self.assertNotIn(str(root), json.dumps(before))
                (root / "orre_randomizer/example.py").write_text("updated", encoding="utf-8")
                self.assertNotEqual(build_desktop.runtime_build_inputs(), before)

    def test_binary_source_copy_and_native_build_inputs_must_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_name = "pokemon-orre-randomizer-2.0.0-source.zip"
            with zipfile.ZipFile(root / source_name, "w") as sources:
                sources.writestr(f"{REPOSITORY_NAME}/orre_randomizer/example.py", b"source")
                sources.writestr(f"{REPOSITORY_NAME}/orre_randomizer/helper.ps1", b"helper")
            source = (root / source_name).read_bytes()
            manifest = {source_name: {"sha256": hashlib.sha256(source).hexdigest()}}
            record = {"schema": 1, "files": {"orre_randomizer/example.py": hashlib.sha256(b"source").hexdigest(),
                                            "orre_randomizer/helper.ps1": hashlib.sha256(b"helper").hexdigest()}}
            for mismatch in (False, "source", "data"):
                package = root / ((str(mismatch) + ".zip") if mismatch else "good.zip")
                with zipfile.ZipFile(package, "w") as archive:
                    archive.writestr(f"{APP_EXECUTABLE}/" + source_name, source)
                    changed = {**record, "files": {"orre_randomizer/example.py": "0" * 64}} if mismatch == "source" else record
                    archive.writestr(f"{APP_EXECUTABLE}/" + build_desktop.RUNTIME_BUILD_RECORD, json.dumps(changed))
                    archive.writestr(verify_release.BINARY_ROOT + "orre_randomizer/helper.ps1", b"wrong" if mismatch == "data" else b"helper")
                with zipfile.ZipFile(package) as archive:
                    if mismatch:
                        with self.assertRaisesRegex(RuntimeError, "differs from its source"):
                            verify_release.verify_runtime_inputs(archive, root, manifest)
                    else:
                        self.assertEqual(verify_release.verify_runtime_inputs(archive, root, manifest)["runtime_inputs"], 2)


if __name__ == "__main__":
    unittest.main()
