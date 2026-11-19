"""Release media must match the explicit interface-pack allowlist."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch

from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME
from scripts import build_desktop, verify_release
from scripts.release_media import (BINGO_AUTHORING_LAYERS, BINGO_AUTHORING_ROOT,
    DOCUMENTATION_IMAGES, bingo_authoring_media, documentation_media, game_asset_name_allowed)


class PublicDistributionTests(unittest.TestCase):
    def test_all_registered_assets_share_the_source_and_release_audit_policy(self):
        pack = build_desktop.ROOT / "orre_randomizer/assets/game"
        manifest = json.loads((pack / "provenance.json").read_text("utf-8"))
        self.assertIn("fonts/NotoSansJP.ttf", manifest["files"])
        self.assertIn("fonts/OFL-NotoSansJP.txt", manifest["files"])
        for name in manifest["files"]:
            self.assertTrue(game_asset_name_allowed(name), name)
        for unsafe in ("fonts/other.ttf", "fonts/license.txt", "../fonts/NotoSansJP.ttf",
                       "/fonts/NotoSansJP.ttf", "C:/fonts/NotoSansJP.ttf", "fonts\\NotoSansJP.ttf",
                       "fonts/example.png:stream.json", "game.iso", "models/other.pkx"):
            self.assertFalse(game_asset_name_allowed(unsafe), unsafe)

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
            if relative not in {"docs/images/" + name for name in DOCUMENTATION_IMAGES} | {
                                BINGO_AUTHORING_ROOT + name for name in BINGO_AUTHORING_LAYERS} | {"orre_randomizer/assets/app/icon.png", "orre_randomizer/assets/app/icon.ico",
                                "orre_randomizer/assets/app/logo.png", "orre_randomizer/assets/app/controller.png"}:
                self.assertNotIn(path.suffix.lower(), {".iso", ".rvz", ".fsys", ".raw", ".sav", ".png", ".ico", ".wav", ".dll"})

    def test_bingo_authoring_media_rejects_tampered_or_unregistered_layers(self):
        root = build_desktop.ROOT / BINGO_AUTHORING_ROOT
        read = lambda name: (root / name).read_bytes()
        self.assertEqual(bingo_authoring_media(read), BINGO_AUTHORING_LAYERS | {"bingo-recipe.json", "README.md"})
        chosen = sorted(BINGO_AUTHORING_LAYERS)[0]
        with self.assertRaisesRegex(RuntimeError, "Invalid Bingo"):
            bingo_authoring_media(lambda name: read(name) + (b"X" if name == chosen else b""))
        recipe = json.loads(read("bingo-recipe.json"))
        recipe["authored_layers"][0]["file"] = "../unregistered.png"
        with self.assertRaisesRegex(RuntimeError, "Unexpected Bingo"):
            bingo_authoring_media(lambda name: json.dumps(recipe).encode() if name == "bingo-recipe.json" else read(name))

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

    def test_source_archive_reports_the_test_running_at_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tests = root / "tests"
            tests.mkdir()
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("run_tests.py", "test_processes.py"):
                shutil.copyfile(build_desktop.ROOT / "scripts" / name, scripts / name)
            (tests / "test_hanging.py").write_text(
                "import json, os, sys, time\n"
                "from pathlib import Path\n"
                "from threading import Event\n"
                "from unittest import TestCase\n"
                # Discovery can be slower than the intentionally short hang
                # deadline. Exercise that case independently of machine load.
                "time.sleep(2.1)\n"
                "class HangingTest(TestCase):\n"
                "    def test_waits_forever(self):\n"
                "        Path('worker-ready.tmp').write_text(json.dumps({'pid': os.getpid(), 'argv': sys.argv}))\n"
                "        os.replace('worker-ready.tmp', 'worker-ready.json')\n"
                "        Event().wait()\n",
                encoding="utf-8",
            )
            real_popen = verify_release.subprocess.Popen
            ready = root / "worker-ready.json"
            worker_handle = None
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel32.OpenProcess.restype = wintypes.HANDLE
                kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                kernel32.WaitForSingleObject.restype = wintypes.DWORD
                kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel32.CloseHandle.restype = wintypes.BOOL

            def start_ready_worker(*args, **kwargs):
                nonlocal worker_handle, hang_started
                process = real_popen(*args, **kwargs)
                try:
                    startup_deadline = time.monotonic() + 10
                    while not ready.is_file():
                        self.assertIsNone(process.poll(), "The source runner exited before its test method started")
                        self.assertLess(time.monotonic(), startup_deadline,
                                        "The hanging fixture did not reach its test method within 10 seconds")
                        time.sleep(.01)
                    worker = json.loads(ready.read_text("utf-8"))
                    self.assertNotEqual(worker["pid"], process.pid)
                    # Windows virtualenv redirectors add an intermediate PID;
                    # verify the real worker invocation rather than its parent.
                    self.assertEqual(worker["argv"][1:3], ["--worker", "test_hanging.py"],
                                     "The marker must come from the isolated test worker")
                    if os.name == "nt":
                        # Hold this exact process identity across termination;
                        # checking a PID afterward could observe a reused PID.
                        worker_handle = kernel32.OpenProcess(0x00100000, False, worker["pid"])
                        self.assertTrue(worker_handle, "Cannot observe the fixture worker's termination")
                        self.assertEqual(kernel32.WaitForSingleObject(worker_handle, 0), 258,
                                         "The fixture worker must still be running before the hang deadline")
                    hang_started = time.monotonic()
                    return process
                except BaseException:
                    # Popen's context manager has not taken ownership yet.
                    if os.name == "nt":
                        process.kill()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.communicate(timeout=5)
                    raise

            hang_started = None
            try:
                with patch.object(verify_release, "SOURCE_TEST_TIMEOUT", 2), \
                        patch.object(verify_release.subprocess, "Popen", side_effect=start_ready_worker):
                    with self.assertRaisesRegex(RuntimeError, r"(?s)exceeded 2 seconds.*test_waits_forever"):
                        verify_release.verify_source_tests(root)
                self.assertIsNotNone(hang_started)
                if os.name == "nt":
                    # Job termination can close the inherited pipes just before
                    # the worker's process object becomes signaled.
                    self.assertEqual(kernel32.WaitForSingleObject(worker_handle, 1000), 0,
                                     "The timed-out isolated worker was not terminated")
                self.assertLess(time.monotonic() - hang_started, 7, "A worker kept the timeout's pipes open")
            finally:
                if worker_handle:
                    kernel32.CloseHandle(worker_handle)

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
