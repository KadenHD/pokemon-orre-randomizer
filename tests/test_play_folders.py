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
from orre_randomizer.play_music import MusicCapability


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

    def test_speed_is_a_shortcut_target_and_display_switch_is_reversible(self):
        folder = self.root / "Party"
        data = self.manifest()
        data["settings"].update(speed=2, acceleration=3, display="16:9")
        profile = configure_profile(folder, data)
        ini = configparser.ConfigParser()
        ini.read(profile / "Config/Dolphin.ini")
        self.assertEqual(ini.getfloat("Core", "EmulationSpeed"), 1)
        self.assertTrue(ini.getboolean("Display", "Fullscreen"))
        self.assertEqual(ini.get("Display", "FullscreenDisplayRes"), "Auto")
        gfx = configparser.ConfigParser()
        gfx.read(profile / "Config/GFX.ini")
        self.assertTrue(gfx.getboolean("Settings", "BorderlessFullscreen"))
        self.assertEqual(gfx.getint("Settings", "AspectRatio"), 1)
        self.assertFalse(gfx.getboolean("Settings", "wideScreenHack"))
        data["settings"]["display"] = "4:3"
        configure_profile(folder, data)
        gfx.read(profile / "Config/GFX.ini")
        self.assertEqual(gfx.getint("Settings", "AspectRatio"), 2)
        self.assertIn(":0xFFA01090:0x4BF5E394", (profile / "GameSettings/GC6P01.ini").read_text())

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
        manifest["features"] = {"music": {"enabled": True}}
        with patch('orre_randomizer.play_music.music_capability',
                   return_value=MusicCapability(True, 'validated', 'fixture', True, True)):
            configure_profile(folder, manifest)
            self.assertEqual(volume(), 50)
            configure_profile(folder, manifest, muted=True)
            self.assertEqual(volume(), 0)
            configure_profile(folder, manifest)
            self.assertEqual(volume(), 50)
        manifest["settings"]["native_music"] = False
        configure_profile(folder, manifest)
        self.assertEqual(volume(), 100)

    def test_missing_music_preference_uses_the_supported_default_without_muting_unsupported_audio(self):
        folder = self.root / 'Audio defaults'
        manifest = self.manifest()
        del manifest['settings']['native_music']
        manifest['features'] = {'music': {'enabled': True}}
        for game, game_id in (('colosseum', 'GC6P01'), ('xd', 'GXXP01')):
            manifest.update(game=game, game_id=game_id)
            for supported in (True, False):
                with self.subTest(game=game, supported=supported), patch(
                    'orre_randomizer.play_music.music_capability',
                    return_value=MusicCapability(supported, 'fixture', 'fixture', supported, supported)):
                    configure_profile(folder, manifest)
                    config = configparser.ConfigParser()
                    config.read(folder / 'DolphinUser/Config/Dolphin.ini')
                    self.assertEqual(config.getint('DSP', 'Volume'), 50 if supported else 100)
        manifest['settings']['native_music'] = True
        with patch('orre_randomizer.play_music.music_capability',
                   return_value=MusicCapability(False, 'renderer_missing', 'fixture')):
            configure_profile(folder, manifest)
            config.read(folder / 'DolphinUser/Config/Dolphin.ini')
            self.assertEqual(config.getint('DSP', 'Volume'), 100)

    def test_new_game_folders_enable_music_only_with_a_validated_music_bridge(self):
        for game, game_id in (('colosseum', 'GC6P01'), ('xd', 'GXXP01')):
            for bridge, validated in ((True, True), (True, False), (False, True)):
                request = replace(self.request, folder=self.root / f'{game}-{bridge}-{validated}')
                def completed(**arguments):
                    arguments['destination'].write_bytes(b'owned new ROM')
                    return {'game_id': game_id, 'source_unchanged': True,
                            'output_sha256': hashlib.sha256(b'owned new ROM').hexdigest(),
                            'summary': {}, 'seed': 'test', 'options': {},
                            'play_features': {'music': {'enabled': bridge}}}
                with self.subTest(game=game, bridge=bridge, validated=validated), \
                     patch('orre_randomizer.play_folders.install_launcher'), \
                     patch('orre_randomizer.play_folders.randomize', side_effect=completed), \
                     patch('orre_randomizer.journal.render_journal', return_value='<p>Test</p>'), \
                     patch('orre_randomizer.play_music.music_capability',
                           return_value=MusicCapability(True, 'fixture', 'fixture', True, validated)):
                    create_game_folder(request=request, source=self.source,
                        destination=Path('game.iso'), seed='test', **({'xd_options': object()} if game == 'xd' else {}))
                    data = load_game(request.folder / 'game.json')
                    self.assertEqual(data['settings']['native_music'], bridge and validated)

    def test_non_boolean_music_preferences_are_rejected(self):
        folder = self.root / 'Invalid audio'; (folder / 'Game').mkdir(parents=True)
        (folder / 'Game/game.iso').write_bytes(b'owned fixture')
        for value in ('false', 1, None, []):
            data = self.manifest(); data['settings']['native_music'] = value
            path = folder / 'game.json'; path.write_text(json.dumps(data))
            with self.subTest(value=value), self.assertRaises(UserError):
                load_game(path)

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

    def test_display_modes_preserve_existing_cheat_preferences_in_every_region(self):
        for game, prefix in (('colosseum', 'GC6'), ('xd', 'GXX')):
            for region in ('P', 'E', 'J'):
                for mode in ('16:9', '4:3'):
                    for enabled in (True, False):
                        manifest = self.manifest()
                        manifest.update(game=game, game_id=prefix + region + '01', pack=PACKS[game].key)
                        manifest['settings']['display'] = mode
                        folder = self.root / ('Existing-' + manifest['game_id'] + '-' + mode.replace(':', '-') + '-' + str(enabled))
                        config = folder / 'DolphinUser/Config/Dolphin.ini'
                        config.parent.mkdir(parents=True)
                        config.write_text('[Core]\nEnableCheats = ' + str(enabled) + '\nCustomSetting = keep\n', encoding='utf-8')
                        for operation in (configure_profile, launch_command):
                            with self.subTest(game=game, region=region, display=mode, enabled=enabled,
                                              operation=operation.__name__):
                                result = operation(folder, manifest)
                                settings = configparser.ConfigParser()
                                settings.read(config)
                                self.assertEqual(settings.getboolean('Core', 'EnableCheats'), enabled)
                                self.assertEqual(settings.get('Core', 'CustomSetting'), 'keep')
                                if operation is launch_command:
                                    self.assertFalse(any('EnableCheats' in argument for argument in result))
                        self.assertEqual(self.source.read_bytes(), b'original')

    def test_display_modes_do_not_add_a_cheat_preference_or_cli_override(self):
        for game, game_id, mode in (('xd', 'GXXP01', '16:9'), ('xd', 'GXXP01', '4:3'),
                                    ('colosseum', 'GC6P01', '16:9'), ('colosseum', 'GC6P01', '4:3')):
            with self.subTest(game=game, mode=mode):
                manifest = self.manifest()
                manifest.update(game=game, game_id=game_id, pack=PACKS[game].key)
                manifest['settings']['display'] = mode
                folder = self.root / (game + '-' + mode.replace(':', '-'))
                command = launch_command(folder, manifest)
                config = configparser.ConfigParser()
                config.read(folder / 'DolphinUser/Config/Dolphin.ini')
                self.assertFalse(config.has_option('Core', 'EnableCheats'))
                self.assertFalse(any('EnableCheats' in argument for argument in command))
                self.assertIn(str(folder / 'DolphinUser'), command)

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
