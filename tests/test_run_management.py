"""Run references, bounded sharing, card recovery and non-destructive cleanup."""
from dataclasses import replace
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import subprocess
from unittest.mock import patch
import zlib

from orre_randomizer.challenges import encode_challenge, decode_challenge
from orre_randomizer.options import Options
from orre_randomizer.xd import XDOptions
from orre_randomizer.profiles import configuration_data
from orre_randomizer.play_folders import PlayLock
from orre_randomizer.run_library import RunLibrary
from orre_randomizer.run_safety import assert_dolphin_idle
from orre_randomizer.save_backups import backup_cards, restore_backup, list_backups
from orre_randomizer.storage import scan_storage, cleanup_caches
from orre_randomizer.service import UserError


def game_fixture(root, game="colosseum"):
    folder = root / game; (folder / "Game").mkdir(parents=True)
    (folder / "Game/game.iso").write_bytes(b"synthetic QA disc")
    (folder / "DolphinUser/GC").mkdir(parents=True)
    manifest = {"schema": 1, "orre_version": "2.0.6", "game": game,
        "game_id": "GXXP01" if game == "xd" else "GC6P01", "seed": "seed-é",
        "rom": "Game/game.iso", "rom_sha256": hashlib.sha256(b"synthetic QA disc").hexdigest(),
        "shared": str(root / "Shared"), "dolphin": str(root / "Dolphin.exe"), "pack": game + "-test",
        "settings": {"graphics": "original", "speed": 1}}
    (folder / "game.json").write_text(json.dumps(manifest), "utf-8")
    return folder, manifest


class RunManagement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder, self.manifest = game_fixture(self.root)
        self.card = self.folder / "DolphinUser/GC/MemoryCardA.EUR.raw"
        self.card.write_bytes(b"first card data")
        self.library = RunLibrary(self.root / "LocalData")
        self.library.register(self.folder / "game.json")
        self.idle = patch("orre_randomizer.run_safety.dolphin_arguments", return_value=[])
        self.idle.start(); self.addCleanup(self.idle.stop)

    def test_library_is_a_reference_and_forgetting_does_not_delete_files(self):
        path = self.folder / "game.json"
        initial = path.read_bytes()
        self.library.register(path, opened=True)
        entries = self.library.entries()
        self.assertEqual(len(entries), 1)
        self.assertGreater(entries[0]["opened"], 0)
        self.library.forget(path)
        self.assertEqual(self.library.entries(), [])
        self.assertEqual(path.read_bytes(), initial)
        self.assertEqual(self.card.read_bytes(), b"first card data")

    def test_missing_library_reference_is_retained_and_prevents_cleanup(self):
        (self.folder / "game.json").rename(self.folder / "moved.json")
        self.assertEqual(len(self.library.entries()), 1)
        with self.assertRaises(UserError):
            scan_storage(self.root / "Shared", self.library.entries())

    def test_both_challenge_codes_round_trip_exact_options_and_unicode_seed(self):
        for options in (Options(), XDOptions()):
            code = encode_challenge("Étoile {ami} 日本語", options)
            game, result = decode_challenge(code)
            self.assertEqual(result.seed, "Étoile {ami} 日本語")
            self.assertEqual(result.options, options)
            self.assertEqual(game, "xd" if isinstance(options, XDOptions) else "colosseum")
            self.assertEqual(code, encode_challenge(result.seed, result.options))
            raw = zlib.decompress(base64.urlsafe_b64decode(code.split('.')[1] + '=' * (-len(code.split('.')[1]) % 4)))
            self.assertNotIn(str(self.root).encode(), raw)
            self.assertNotIn(b"dolphin", raw.lower())

    def test_codes_preserve_spaces_and_reject_damage_unknown_engine_and_bombs(self):
        code = encode_challenge(" a A ", Options())
        self.assertEqual(decode_challenge(code)[1].seed, " a A ")
        for bad in (code[:-1] + ("0" if code[-1] != "0" else "1"), "ORRE2." + code.split('.', 1)[1], "x" * 100001):
            with self.assertRaises(UserError):
                decode_challenge(bad)
        bomb = base64.urlsafe_b64encode(zlib.compress(b" " * 1000000)).decode().rstrip("=")
        with self.assertRaises(UserError):
            decode_challenge("ORRE1." + bomb + "." + "0" * 16)
        encoded = code.split('.')[1]
        payload = json.loads(zlib.decompress(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))))
        raw = json.dumps(dict(payload, engine_version="future-unknown")).encode()
        bad = "ORRE1." + base64.urlsafe_b64encode(zlib.compress(raw)).decode().rstrip("=") + "." + hashlib.sha256(raw).hexdigest()[:16]
        with self.assertRaises(UserError):
            decode_challenge(bad)

    def test_backup_deduplicates_rotates_and_preserves_the_live_card(self):
        first = backup_cards(self.folder)
        self.assertEqual(first, backup_cards(self.folder))
        for i in range(7):
            self.card.write_bytes(f"card {i}".encode())
            backup_cards(self.folder)
        copies = list_backups(self.folder)
        self.assertEqual(len(copies), 5)
        self.assertEqual(self.card.read_bytes(), b"card 6")
        self.assertFalse((self.folder / "SaveBackups" / first).exists())

    def test_restore_checks_content_and_keeps_current_backup_and_save_states(self):
        first = backup_cards(self.folder)
        states = self.folder / "DolphinUser/StateSaves"; states.mkdir()
        (states / "game.s01").write_bytes(b"separate save state")
        self.card.write_bytes(b"newer card")
        restore_backup(self.folder, first)
        self.assertEqual(self.card.read_bytes(), b"first card data")
        self.assertEqual((states / "game.s01").read_bytes(), b"separate save state")
        copies = list_backups(self.folder)
        self.assertTrue(any(c["reason"] == "before-restore" for c in copies))
        self.assertTrue(any((self.folder / "SaveBackups" / c["name"] / self.card.name).read_bytes() == b"newer card" for c in copies))

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_backup_retries_a_transient_windows_lock_without_changing_card(self):
        original = Path.rename
        attempts = []
        blocked = PermissionError("temporary Windows file lock")
        blocked.winerror = 5

        def rename(stage, destination):
            if stage.name.startswith(".snapshot-"):
                attempts.append(stage)
                if len(attempts) == 1:
                    raise blocked
            return original(stage, destination)

        with patch.object(Path, "rename", rename):
            name = backup_cards(self.folder)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.card.read_bytes(), b"first card data")
        self.assertEqual((self.folder / "SaveBackups" / name / self.card.name).read_bytes(), b"first card data")
        self.assertFalse(list((self.folder / "SaveBackups").glob(".snapshot-*")))

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_backup_persistent_windows_lock_is_bounded_and_leaves_no_partial_backup(self):
        blocked = PermissionError("persistent Windows file lock")
        blocked.winerror = 32
        with patch.object(Path, "rename", side_effect=blocked) as rename, \
             patch("orre_randomizer.play_folders.time.monotonic", side_effect=(100, 106)):
            with self.assertRaises(PermissionError) as caught:
                backup_cards(self.folder)
        self.assertIs(caught.exception, blocked)
        rename.assert_called_once()
        self.assertEqual(self.card.read_bytes(), b"first card data")
        self.assertEqual(list_backups(self.folder), [])
        self.assertFalse(list((self.folder / "SaveBackups").glob(".snapshot-*")))

    def test_damaged_backup_and_wrong_run_are_refused_before_replacing_card(self):
        first = backup_cards(self.folder)
        snapshot = self.folder / "SaveBackups" / first
        (snapshot / self.card.name).write_bytes(b"broken")
        with self.assertRaises(UserError):
            restore_backup(self.folder, first)
        self.assertEqual(self.card.read_bytes(), b"first card data")
        (snapshot / self.card.name).write_bytes(b"first card data")
        metadata = json.loads((snapshot / "snapshot.json").read_text())
        metadata["identity"]["seed"] = "another run"
        (snapshot / "snapshot.json").write_text(json.dumps(metadata))
        with self.assertRaises(UserError):
            restore_backup(self.folder, first)

    def test_partial_restore_publication_rolls_back_both_cards(self):
        second = self.card.with_name("MemoryCardB.EUR.raw"); second.write_bytes(b"old B")
        first = backup_cards(self.folder)
        self.card.write_bytes(b"new A"); second.write_bytes(b"new B")
        original = os.replace
        def replace_file(source, target):
            if Path(source).parent.name.startswith(".restore-") and Path(target).name == second.name:
                raise OSError("synthetic second-card publication failure")
            return original(source, target)
        with patch("orre_randomizer.save_backups.os.replace", side_effect=replace_file):
            with self.assertRaises(OSError):
                restore_backup(self.folder, first)
        self.assertEqual(self.card.read_bytes(), b"new A")
        self.assertEqual(second.read_bytes(), b"new B")

    def test_an_active_launcher_refuses_backup(self):
        lock = PlayLock(self.folder)
        try:
            with self.assertRaises(UserError):
                backup_cards(self.folder)
        finally:
            lock.close()

    def test_external_dolphin_profile_and_rom_checks(self):
        profile = str(self.folder / "DolphinUser")
        rom = str(self.folder / "Game/game.iso")
        for argv in (None, ["Dolphin.exe"], ["Dolphin.exe", "-u", profile], ["Dolphin.exe", "-u", str(self.root / "other"), "-e", rom]):
            with patch("orre_randomizer.run_safety.dolphin_arguments", return_value=[argv]):
                with self.assertRaises(UserError):
                    assert_dolphin_idle(self.folder, self.manifest)
        with patch("orre_randomizer.run_safety.dolphin_arguments", return_value=[["Dolphin.exe", "-u", str(self.root / "other")]]):
            assert_dolphin_idle(self.folder, self.manifest)

    def cache_fixture(self):
        shared = self.root / "Shared"
        pack = shared / "TexturePacks/colosseum-2.00/Textures"; pack.mkdir(parents=True)
        source = pack / "tex1_1x1_original.png"; source.write_bytes(b"immutable texture" * 100)
        view = shared / "TextureViews/colosseum-2.00-GC6P01-old"
        target = view / "Load/Textures/GC6P01"; target.mkdir(parents=True)
        os.link(source, target / source.name)
        marker = view / "complete.json"; marker.write_text('{"pack":"colosseum-2.00"}')
        os.utime(marker, (time.time() - 90000,) * 2)
        runtime = shared / "Runtimes/2.0.6/OrreRandomizer.exe"; runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b"keep pinned runtime")
        return shared, view, source, runtime

    def test_cache_cleanup_counts_hardlinks_and_never_targets_rom_saves_packs_or_runtime(self):
        shared, view, source, runtime = self.cache_fixture()
        plan = scan_storage(shared, self.library.entries())
        self.assertEqual(len(plan.candidates), 1)
        self.assertLess(plan.candidates[0].reclaimable_bytes, plan.candidates[0].logical_bytes)
        before = source.read_bytes()
        # Windows runners may expose TEMP through its short 8.3 alias. Cleanup
        # reports canonical paths, captured before the directory is removed.
        expected_path = str(view.resolve())
        removed = cleanup_caches(plan, [str(view)])
        self.assertEqual(removed, [expected_path])
        self.assertFalse(view.exists())
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue(runtime.is_file())
        self.assertEqual(self.card.read_bytes(), b"first card data")
        self.assertEqual((self.folder / "Game/game.iso").read_bytes(), b"synthetic QA disc")

    def test_referenced_cache_and_recent_cache_are_not_offered(self):
        shared, view, _, _ = self.cache_fixture()
        config = self.folder / "DolphinUser/Config"; config.mkdir()
        (config / "Dolphin.ini").write_text("[General]\nLoadPath=" + str(view / "Load") + "\n")
        self.assertEqual(scan_storage(shared, self.library.entries()).candidates, [])
        (config / "Dolphin.ini").unlink()
        os.utime(view / "complete.json", None)
        self.assertEqual(scan_storage(shared, self.library.entries()).candidates, [])

    def test_cleanup_refuses_a_library_changed_by_another_app_instance(self):
        shared, view, _, _ = self.cache_fixture()
        plan = scan_storage(shared, self.library.entries())
        other, _ = game_fixture(self.root, "xd")
        self.library.register(other / "game.json")
        with self.assertRaises(UserError):
            cleanup_caches(plan, [str(view)], current_entries=self.library.entries)
        self.assertTrue(view.is_dir())

    def test_cleanup_rechecks_mutations_and_installer_locks(self):
        shared, view, _, _ = self.cache_fixture()
        plan = scan_storage(shared, self.library.entries())
        (view / "new-file").write_bytes(b"changed")
        with self.assertRaises(UserError):
            cleanup_caches(plan, [str(view)])
        (view / "new-file").unlink()
        plan = scan_storage(shared, self.library.entries())
        (shared / "TexturePacks/install.lock").touch()
        with self.assertRaises(UserError):
            cleanup_caches(plan, [str(view)])
        self.assertTrue(view.is_dir())

    def test_cleanup_rechecks_new_references_before_any_delete(self):
        shared, view, _, _ = self.cache_fixture()
        plan = scan_storage(shared, self.library.entries())
        config = self.folder / "DolphinUser/Config"; config.mkdir()
        (config / "Dolphin.ini").write_text("[General]\nLoadPath=" + str(view / "Load") + "\n")
        with self.assertRaises(UserError):
            cleanup_caches(plan, [str(view)])
        self.assertTrue(view.is_dir())

    def test_external_links_are_refused_without_touching_target(self):
        outside = self.root / "outside"; outside.mkdir(); (outside / "keep").write_bytes(b"safe")
        link = self.folder / "SaveBackups"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            if os.name != 'nt':
                self.skipTest("Creating a test link is not permitted")
            powershell = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command',
                'New-Item -ItemType Junction -Path $env:ORRE_TEST_LINK -Target $env:ORRE_TEST_TARGET -ErrorAction Stop | Out-Null'],
                env=dict(os.environ, ORRE_TEST_LINK=str(link), ORRE_TEST_TARGET=str(outside)),
                capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        with self.assertRaises(UserError):
            backup_cards(self.folder)
        self.assertEqual((outside / "keep").read_bytes(), b"safe")


if __name__ == "__main__":
    unittest.main()
