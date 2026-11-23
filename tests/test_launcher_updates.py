"""Upgrading the control files must never regenerate a run or migrate its assets."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from orre_randomizer import __version__
from orre_randomizer.hd_packs import PACKS
from orre_randomizer import launcher_updates as updates
from orre_randomizer.play_folders import PlayLock, launcher_command
from orre_randomizer.service import Cancelled, UserError


class LauncherUpdates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "Run"
        self.folder.mkdir()
        self.manifest = self.folder / "game.json"
        self.data = {"schema": 1, "orre_version": "1.9.9", "game": "colosseum", "game_id": "GC6P01",
            "seed": "keep-my-run", "rom": "Game/game.iso", "shared": str(self.root / "Shared"),
            "dolphin": str(self.root / "Dolphin.exe"), "language": "fr", "pack": PACKS['colosseum'].key,
            "settings": {"graphics": "original", "speed": 2, "native_music": False}}
        self.manifest.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        self.protected = {"game.json": self.manifest.read_bytes(), "Game/game.iso": b"existing randomized ROM",
            "DolphinUser/GC/MemoryCardA.EUR.raw": b"existing saved game",
            "DolphinUser/StateSaves/run.sav": b"existing state",
            "DolphinUser/Config/GCPadNew.ini": b"my custom controls",
            "Textures/NativeReferences/keep.bin": b"frozen native resources"}
        for name, content in self.protected.items():
            file = self.folder / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(content)
        self.launcher = "Launcher.exe" if os.name == "nt" else "Launcher"
        self.old = self.runtime("1.9.9", b"old cached application")
        self.current = self.runtime(__version__, b"current application")
        self.native = self.root / "native launcher"; self.native.write_bytes(b"new native launcher")
        (self.folder / self.launcher).write_bytes(b"old native launcher")
        self.previous_descriptor = self.descriptor(self.old)
        (self.folder / "launcher-runtime.txt").write_bytes(self.previous_descriptor)
        self.patchers = [patch('orre_randomizer.play_folders._runtime', return_value=self.current),
                         patch.object(updates, 'native_launcher_path', return_value=self.native)]
        for p in self.patchers:
            p.start(); self.addCleanup(p.stop)

    def runtime(self, version, payload):
        directory = self.root / 'Shared/Runtimes' / (version + '-' + hashlib.sha256(payload).hexdigest()[:16])
        directory.mkdir(parents=True)
        executable = directory / 'OrreRandomizer.exe'; executable.write_bytes(payload)
        return [str(executable), str(directory)]

    @staticmethod
    def descriptor(command):
        return ('\n'.join(['ORRE-LAUNCHER-1', *command]) + '\n').encode('utf-8')

    def assert_preserved(self):
        for name, content in self.protected.items():
            self.assertEqual((self.folder / name).read_bytes(), content, name)

    def test_upgrade_changes_only_launcher_files_and_reopens_the_current_runtime(self):
        result = updates.upgrade_launcher(self.manifest)
        self.assertTrue(result['changed'])
        self.assertEqual(updates.launcher_version(self.folder, self.data), __version__)
        command, directory = launcher_command(self.manifest)
        self.assertEqual(command[0], self.current[0]); self.assertEqual(directory, self.current[1])
        self.assert_preserved()
        backup = Path(result['backup_directory'])
        self.assertEqual((backup / self.launcher).read_bytes(), b'old native launcher')
        self.assertEqual((backup / 'launcher-runtime.txt').read_bytes(), self.previous_descriptor)
        self.assertIsNone(json.loads((backup / 'backup.json').read_text())['files'][updates.RECEIPT])
        self.assertFalse(updates.upgrade_launcher(self.manifest)['changed'])

    def test_xd_keeps_both_original_pack_pins(self):
        self.data.update(game='xd', game_id='GXXP01', pack=PACKS['xd'].key,
            packs={game: PACKS[game].key for game in ('xd', 'colosseum')})
        self.manifest.write_text(json.dumps(self.data), encoding='utf-8')
        self.protected['game.json'] = self.manifest.read_bytes()
        updates.upgrade_launcher(self.manifest)
        self.assert_preserved()

    def test_incompatible_frozen_packs_and_downgrades_are_refused(self):
        self.data['pack'] = 'future-or-unknown-pack'
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaises(UserError): updates.upgrade_status(self.manifest)
        self.data['pack'] = PACKS['colosseum'].key
        self.data['orre_version'] = '999.0.0'
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaises(UserError): updates.upgrade_status(self.manifest)
        self.assertFalse((self.folder / updates.RECEIPT).exists())

    def test_cancel_during_preparation_never_publishes_or_copies_the_run(self):
        cancel = threading.Event()
        def prepared(*_args, **kwargs):
            self.assertIs(kwargs['cancel'], cancel)
            cancel.set(); return self.current
        with patch('orre_randomizer.play_folders._runtime', side_effect=prepared):
            with self.assertRaises(Cancelled): updates.upgrade_launcher(self.manifest, cancel=cancel)
        self.assertEqual((self.folder / 'launcher-runtime.txt').read_bytes(), self.previous_descriptor)
        self.assertFalse((self.folder / 'LauncherBackups').exists())
        self.assert_preserved()

    def test_active_game_lock_prevents_upgrading(self):
        lock = PlayLock(self.folder)
        try:
            with self.assertRaises(UserError): updates.upgrade_launcher(self.manifest)
        finally:
            lock.close()
        self.assert_preserved()

    def test_settings_changed_during_preparation_are_kept_and_publication_is_refused(self):
        changed = {**self.data, 'language': 'en'}
        def preparing(*_args, **_kwargs):
            self.manifest.write_text(json.dumps(changed), encoding='utf-8')
            return self.current
        with patch('orre_randomizer.play_folders._runtime', side_effect=preparing):
            with self.assertRaises(UserError): updates.upgrade_launcher(self.manifest)
        self.assertEqual(json.loads(self.manifest.read_text('utf-8')), changed)
        self.assertEqual((self.folder / 'launcher-runtime.txt').read_bytes(), self.previous_descriptor)
        self.assertFalse((self.folder / 'LauncherBackups').exists())

    def test_version_is_checked_after_acquiring_the_run_lock(self):
        def locked(folder):
            self.data['orre_version'] = '999.0.0'
            self.manifest.write_text(json.dumps(self.data), encoding='utf-8')
            return PlayLock(folder)
        with patch('orre_randomizer.play_folders.PlayLock', side_effect=locked):
            with self.assertRaises(UserError): updates.upgrade_launcher(self.manifest)
        self.assertEqual((self.folder / 'launcher-runtime.txt').read_bytes(), self.previous_descriptor)
        self.assertFalse((self.folder / 'LauncherBackups').exists())

    def test_partial_publication_rolls_back_every_control_file(self):
        replace = updates._replace
        calls = 0
        def failing(path, payload):
            nonlocal calls
            calls += 1
            if calls == 3: raise OSError('simulated descriptor write failure')
            return replace(path, payload)
        with patch.object(updates, '_replace', side_effect=failing):
            with self.assertRaises(OSError): updates.upgrade_launcher(self.manifest)
        self.assertEqual((self.folder / self.launcher).read_bytes(), b'old native launcher')
        self.assertEqual((self.folder / 'launcher-runtime.txt').read_bytes(), self.previous_descriptor)
        self.assertFalse((self.folder / updates.RECEIPT).exists())
        self.assertFalse(list(self.folder.glob('.launcher-update-*')))
        self.assert_preserved()

    def test_interruption_before_commit_still_resolves_the_prior_runtime(self):
        updates.upgrade_launcher(self.manifest)
        (self.folder / 'launcher-runtime.txt').write_bytes(self.previous_descriptor)
        command, _ = launcher_command(self.manifest)
        self.assertEqual(command[0], self.old[0])
        self.assertTrue(updates.upgrade_status(self.manifest)['available'])

    def test_corrupted_receipt_never_selects_an_unverified_runtime(self):
        updates.upgrade_launcher(self.manifest)
        (self.folder / 'launcher-runtime.txt').write_bytes(b'ORRE-LAUNCHER-1\nuntrusted\npath\n')
        with self.assertRaises(UserError): launcher_command(self.manifest)
        self.assert_preserved()

    def test_runtime_cache_repair_refreshes_the_receipt(self):
        updates.upgrade_launcher(self.manifest)
        Path(self.current[0]).unlink()
        repaired = self.runtime(__version__, b'repaired same-version build')
        def install(folder, _shared):
            (folder / 'launcher-runtime.txt').write_bytes(self.descriptor(repaired))
        with patch('orre_randomizer.play_folders.install_launcher', side_effect=install), \
             patch('orre_randomizer.play_folders._runtime', return_value=repaired):
            self.assertEqual(launcher_command(self.manifest)[0][0], repaired[0])
        self.assertEqual(updates.launcher_version(self.folder, self.data), __version__)
        self.assert_preserved()


if __name__ == '__main__':
    unittest.main()
