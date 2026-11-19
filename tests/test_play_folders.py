"""Creation publication, isolated profiles, no-clobber and launcher ownership."""
from dataclasses import replace
import configparser
import json
import hashlib
import os
from pathlib import Path
from orre_randomizer.hd_packs import PACKS
import tempfile
import threading
import unittest
from unittest.mock import patch

from orre_randomizer.play_folders import (PlayFolderRequest, PlayLock, configure_profile,
    create_game_folder, launch_command, launcher_command, load_game, _publish_folder)
from orre_randomizer.service import Cancelled, UserError


class GameFolders(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "original.iso"; self.source.write_bytes(b"original")
        self.dolphin = self.root / "Dolphin.exe"; self.dolphin.write_bytes(b"test executable")
        self.request = PlayFolderRequest(self.root / "Game folder", self.dolphin, shared=self.root / "Shared")

    def manifest(self):
        return {"schema": 1, "game": "colosseum", "game_id": "GC6P01", "seed": "test", "rom": "Game/game.iso",
            "dolphin": str(self.dolphin), "shared": str(self.root / "Shared"), "pack": PACKS["colosseum"].key,
            "language": "en", "settings": {"graphics": "original", "speed": 1, "native_music": False}}

    def test_profile_keeps_cards_inside_game_and_preserves_custom_controls(self):
        folder = self.root / "Party"
        configure_profile(folder, self.manifest())
        ini = (folder / "DolphinUser/Config/Dolphin.ini").read_text()
        self.assertIn((folder / "DolphinUser/GC/MemoryCardA.EUR.raw").as_posix(), ini)
        controls = folder / "DolphinUser/Config/GCPadNew.ini"
        self.assertIn("`RETURN`" if os.name == "nt" else "`Return`", controls.read_text())
        controls.write_text("[GCPad1]\nDevice = My controller\nButtons/A = custom\n")
        configure_profile(folder, self.manifest())
        self.assertIn("custom", controls.read_text())

    def test_profile_refuses_a_junction_into_other_saves(self):
        folder = self.root / "Party"
        folder.mkdir()
        protected = self.root / "Other saves"
        protected.mkdir()
        (protected / "keep.raw").write_bytes(b"personal save")
        link = folder / "DolphinUser"
        if os.name == "nt":
            import subprocess
            # Native PowerShell creates the directory junction in this owned fixture.
            subprocess.run(["powershell", "-NoProfile", "-Command",
                "New-Item -ItemType Junction -Path $env:ORRE_TEST_LINK -Target $env:ORRE_TEST_TARGET | Out-Null"],
                env={**os.environ, "ORRE_TEST_LINK": str(link), "ORRE_TEST_TARGET": str(protected)},
                check=True, capture_output=True)
        else:
            link.symlink_to(protected, target_is_directory=True)
        try:
            with self.assertRaises(UserError):
                configure_profile(folder, self.manifest())
            self.assertEqual(list(protected.iterdir()), [protected / "keep.raw"])
        finally:
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()

    def test_hd_filter_is_local_and_resets_when_returning_to_original(self):
        folder = self.root / "Party"
        manifest = self.manifest()
        manifest["settings"]["graphics"] = "hd"
        profile = configure_profile(folder, manifest)
        path = profile / "Config/GFX.ini"
        settings = configparser.ConfigParser()
        settings.optionxform = str
        settings.read(path)
        self.assertEqual(settings.getint("Enhancements", "ForceTextureFiltering"), 2)
        self.assertTrue(settings.getboolean("Settings", "HiresTextures"))
        settings.set("Enhancements", "MaxAnisotropy", "4")
        with path.open("w", encoding="utf-8") as output:
            settings.write(output)

        manifest["settings"]["graphics"] = "original"
        configure_profile(folder, manifest)
        settings.read(path)
        self.assertEqual(settings.getint("Enhancements", "ForceTextureFiltering"), 0)
        self.assertFalse(settings.getboolean("Settings", "HiresTextures"))
        self.assertEqual(settings.getint("Settings", "InternalResolution"), 1)
        self.assertEqual(settings.getint("Enhancements", "MaxAnisotropy"), 4)
        self.assertFalse((self.root / "Config").exists())

    def test_music_reserves_equal_headroom_and_qa_mute_is_reversible(self):
        folder = self.root / "Party"
        manifest = self.manifest()

        def volume():
            config = configparser.ConfigParser()
            config.read(folder / "DolphinUser/Config/Dolphin.ini")
            return config.getint("DSP", "Volume")

        configure_profile(folder, manifest)
        self.assertEqual(volume(), 100)
        manifest["settings"]["native_music"] = True
        configure_profile(folder, manifest)
        self.assertEqual(volume(), 50)
        configure_profile(folder, manifest, muted=True)
        self.assertEqual(volume(), 0)
        configure_profile(folder, manifest)
        self.assertEqual(volume(), 50)
        manifest["settings"]["native_music"] = False
        configure_profile(folder, manifest)
        self.assertEqual(volume(), 100)

    def test_exclusive_lock_releases_without_deleting_saves(self):
        lock = PlayLock(self.root)
        with self.assertRaises(UserError):
            PlayLock(self.root)
        lock.close()
        second = PlayLock(self.root); second.close()

    def test_manifest_rejects_a_rom_outside_the_folder(self):
        data = self.manifest(); data["rom"] = "../original.iso"
        path = self.root / "game.json"; path.write_text(json.dumps(data))
        with self.assertRaises(UserError):
            load_game(path)

    def test_launch_command_uses_explicit_separate_profile_and_mute_override(self):
        folder = self.root / "Party"
        result = launch_command(folder, self.manifest(), muted=True)
        self.assertIn(str(folder / "DolphinUser"), result)
        self.assertIn("Dolphin.DSP.Volume=0", result)
        self.assertNotIn(str(self.source), result)

    def test_failed_job_leaves_no_published_folder_or_original_changes(self):
        def cancelled(**kwargs):
            kwargs["destination"].write_bytes(b"partial")
            raise Cancelled("cancelled")
        with patch("orre_randomizer.play_folders.install_launcher"), patch("orre_randomizer.play_folders.randomize", side_effect=cancelled):
            with self.assertRaises(Cancelled):
                create_game_folder(request=self.request, source=self.source, destination=Path("game.iso"), seed="test")
        self.assertFalse(self.request.folder.exists())
        self.assertEqual(self.source.read_bytes(), b"original")
        self.assertFalse(list(self.root.glob(".orre-play-*")))

    def test_success_publishes_all_paths_and_keeps_the_source(self):
        def completed(**arguments):
            arguments["destination"].write_bytes(b"owned new ROM")
            return {"game_id":"GC6P01", "source_unchanged":True,
                    "output_sha256":hashlib.sha256(b"owned new ROM").hexdigest(),
                    "summary":{}, "seed":"test", "options":{}}
        with patch("orre_randomizer.play_folders.install_launcher"), \
             patch("orre_randomizer.play_folders.randomize", side_effect=completed), \
             patch("orre_randomizer.journal.render_journal", return_value="<p>Test</p>"):
            result = create_game_folder(request=self.request, source=self.source,
                                        destination=Path("game.iso"), seed="test")
        folder = self.request.folder
        self.assertTrue((folder / "Game/game.iso").is_file())
        self.assertEqual(json.loads((folder / "Game/game.iso.json").read_text())["play_folder"], str(folder))
        manifest = load_game(folder / "game.json")
        self.assertEqual(manifest["rom"], "Game/game.iso")
        self.assertEqual(result["play_folder"], str(folder))
        self.assertEqual(self.source.read_bytes(), b"original")
        self.assertFalse(list(self.root.glob(".orre-play-*")))

    def test_existing_folder_is_never_replaced(self):
        self.request.folder.mkdir()
        existing = self.request.folder / "keep.sav"; existing.write_bytes(b"save")
        with self.assertRaises(UserError):
            create_game_folder(request=self.request, source=self.source, destination=Path("game.iso"), seed="test")
        self.assertEqual(existing.read_bytes(), b"save")

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_transient_windows_file_lock_does_not_discard_a_completed_run(self):
        stage = self.root / "stage"; stage.mkdir()
        (stage / "game.iso").write_bytes(b"new")
        original = Path.rename
        blocked = PermissionError("temporary sharing lock"); blocked.winerror = 32
        calls = []
        def rename(path, target):
            calls.append(path)
            if len(calls) == 1:
                raise blocked
            return original(path, target)
        with patch.object(Path, "rename", rename):
            _publish_folder(stage, self.request.folder, threading.Event())
        self.assertEqual((self.request.folder / "game.iso").read_bytes(), b"new")
        self.assertEqual(len(calls), 2)

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_a_folder_created_during_a_publication_retry_is_kept(self):
        stage = self.root / "stage"; stage.mkdir()
        def race(*arguments):
            self.request.folder.mkdir()
            (self.request.folder / "keep.raw").write_bytes(b"save")
            blocked = PermissionError("temporary sharing lock"); blocked.winerror = 5
            raise blocked
        with patch.object(Path, "rename", race), self.assertRaises(UserError):
            _publish_folder(stage, self.request.folder, threading.Event())
        self.assertEqual((self.request.folder / "keep.raw").read_bytes(), b"save")

    def test_open_game_keeps_a_verified_older_shared_runtime(self):
        data = self.manifest(); data['orre_version'] = '1.9.9'
        (self.root/'Game').mkdir(); (self.root/'Game/game.iso').write_bytes(b'fixture')
        payload = b'owned previous runtime'
        runtime = self.root/'Shared/Runtimes'/('1.9.9-'+hashlib.sha256(payload).hexdigest()[:16])
        runtime.mkdir(parents=True)
        executable = runtime/'OrreRandomizer.exe'; executable.write_bytes(payload)
        (self.root/'launcher-runtime.txt').write_text(f'ORRE-LAUNCHER-1\n{executable}\n{runtime}\n')
        manifest = self.root/'game.json'; manifest.write_text(json.dumps(data))
        with patch('orre_randomizer.play_folders.install_launcher') as repaired:
            command, cwd = launcher_command(manifest)
        repaired.assert_not_called()
        self.assertEqual(command[0], str(executable))
        self.assertEqual(cwd, str(runtime))

    def test_open_game_rejects_an_external_or_modified_older_runtime(self):
        data = self.manifest(); data['orre_version'] = '1.9.9'
        (self.root/'Game').mkdir(); (self.root/'Game/game.iso').write_bytes(b'fixture')
        manifest = self.root/'game.json'; manifest.write_text(json.dumps(data))
        (self.root/'launcher-runtime.txt').write_text(f'ORRE-LAUNCHER-1\n{self.dolphin}\n{self.root}\n')
        with self.assertRaises(UserError):
            launcher_command(manifest)


if __name__ == "__main__":
    unittest.main()
