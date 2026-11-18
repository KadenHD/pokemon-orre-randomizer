"""XD HD requires both pinned packs before generation, installation and launch."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from orre_randomizer.hd_packs import PACKS, Pack, Part, PackStore
from orre_randomizer.play_folders import (PlayFolderRequest, create_game_folder,
    hd_game_requirements, missing_hd_packs, prepare_custom_hd)
from orre_randomizer.service import Cancelled, UserError


class HdDependencies(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = PackStore(self.root / "Shared", source=self.root / "Distribution")
        self.data = {"game": "xd", "shared": str(self.store.root)}

    def fixture_packs(self):
        """Real local ZIPs exercise download verification and publication without GBs."""
        archive = self.root / "pack.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("tex1_4x4_abc_6.png", b"\x89PNG\r\n\x1a\n" + bytes(32))
        payload = archive.read_bytes()
        part = Part("", hashlib.sha256(payload).hexdigest(), len(payload))
        packs = {game: Pack(game, "fixture", 40, (part,)) for game in PACKS}
        for pack in packs.values():
            path = self.store.archive_source(pack, part)
            path.parent.mkdir(parents=True)
            path.write_bytes(payload)
        return packs

    def test_xd_requires_both_without_recorded_overlay_dependencies(self):
        self.assertEqual(hd_game_requirements(self.data), ("xd", "colosseum"))
        for installed in (set(), {"xd"}, {"colosseum"}, {"xd", "colosseum"}):
            with self.subTest(installed=installed), patch.object(PackStore, "installed",
                    side_effect=lambda pack: pack.game in installed):
                self.assertEqual(missing_hd_packs(self.data),
                    [game for game in ("xd", "colosseum") if game not in installed])

    def test_colosseum_keeps_only_its_actual_custom_model_dependencies(self):
        self.assertEqual(hd_game_requirements({"game": "colosseum"}), ("colosseum",))
        self.assertEqual(hd_game_requirements({"game": "colosseum", "features": {
            "overlays": {"required_packs": ["xd", "colosseum", "xd"]}}}), ("colosseum", "xd"))

    def test_xd_creation_refuses_missing_colosseum_before_any_rom_work(self):
        source = self.root / "original.iso"; source.write_bytes(b"original")
        dolphin = self.root / "Dolphin.exe"; dolphin.write_bytes(b"never executed")
        request = PlayFolderRequest(self.root / "Party", dolphin, graphics="hd", shared=self.store.root)
        with patch.object(PackStore, "installed", side_effect=lambda pack: pack.game == "xd"), \
             patch("orre_randomizer.play_folders.randomize") as generate, \
             patch("orre_randomizer.play_folders.install_launcher") as launcher:
            with self.assertRaises(UserError) as error:
                create_game_folder(request=request, source=source, destination=Path("game.iso"),
                                   seed="test", xd_options=object())
        self.assertIn("Pokémon Colosseum", str(error.exception))
        generate.assert_not_called(); launcher.assert_not_called()
        self.assertFalse(request.folder.exists())
        self.assertEqual(source.read_bytes(), b"original")

    def test_original_xd_folder_pins_both_for_a_later_hd_switch_without_downloads(self):
        source = self.root / "original.iso"; source.write_bytes(b"original")
        dolphin = self.root / "Dolphin.exe"; dolphin.write_bytes(b"never executed")
        request = PlayFolderRequest(self.root / "Party", dolphin, shared=self.store.root)
        def completed(**arguments):
            arguments["destination"].write_bytes(b"generated fixture")
            return {"game_id": "GXXP01", "output_sha256": "fixture", "summary": {}, "seed": "test"}
        with patch.object(PackStore, "installed", side_effect=AssertionError("Original needs no packs")), \
             patch("orre_randomizer.play_folders.install_launcher"), \
             patch("orre_randomizer.play_folders.randomize", side_effect=completed), \
             patch("orre_randomizer.journal.render_journal", return_value="fixture"):
            create_game_folder(request=request, source=source, destination=Path("game.iso"),
                               seed="test", xd_options=object())
        manifest = json.loads((request.folder / "game.json").read_text("utf-8"))
        self.assertEqual(manifest["packs"], {game: PACKS[game].key for game in PACKS})
        self.assertEqual(source.read_bytes(), b"original")

    def test_hd_preparation_refuses_missing_colosseum_even_without_donor_metadata(self):
        folder = self.root / "Party"
        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value={"schema": 2, "assets": []}), \
             patch.object(PackStore, "installed", side_effect=lambda pack: pack.game == "xd"), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays") as render:
            with self.assertRaises(UserError) as error:
                prepare_custom_hd(folder, self.data)
        self.assertIn("Pokémon Colosseum", str(error.exception))
        render.assert_not_called()

    def test_one_xd_install_installs_both_and_reuses_completed_packs(self):
        packs = self.fixture_packs()
        progress = []
        with patch.dict(PACKS, packs, clear=True), \
             patch("urllib.request.urlopen", side_effect=AssertionError("no network")), \
             patch.object(self.store, "_download", wraps=self.store._download) as download:
            result = self.store.install_game("xd", progress=lambda value, _: progress.append(value))
            self.assertTrue(all(self.store.installed(pack) for pack in packs.values()))
            self.assertEqual(len(result["packs"]), 2)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(self.store.install_game("xd")["packs"], [])
            self.assertEqual(download.call_count, 2)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 100)

    def test_failed_second_pack_keeps_first_and_retry_downloads_only_missing_pack(self):
        packs = self.fixture_packs()
        missing = self.store.archive_source(packs["colosseum"], packs["colosseum"].parts[0])
        payload = missing.read_bytes(); missing.unlink()
        with patch.dict(PACKS, packs, clear=True):
            with self.assertRaises(UserError):
                self.store.install_game("xd")
            self.assertTrue(self.store.installed(packs["xd"]))
            self.assertFalse(self.store.installed(packs["colosseum"]))
            before = (self.store.location(packs["xd"]) / "installed.json").read_bytes()
            missing.write_bytes(payload)
            with patch.object(self.store, "_download", wraps=self.store._download) as download:
                self.store.install_game("xd")
            self.assertEqual(download.call_count, 1)
            self.assertTrue(self.store.installed(packs["colosseum"]))
            self.assertEqual((self.store.location(packs["xd"]) / "installed.json").read_bytes(), before)

    def test_cancel_between_packs_keeps_completed_pack(self):
        packs = self.fixture_packs()
        cancel = threading.Event()
        def progress(_value, message):
            if message == "Pack HD installé et vérifié.":
                cancel.set()
        with patch.dict(PACKS, packs, clear=True):
            with self.assertRaises(Cancelled):
                self.store.install_game("xd", cancel=cancel, progress=progress)
            self.assertTrue(self.store.installed(packs["xd"]))
            self.assertFalse(self.store.installed(packs["colosseum"]))
            cancel.clear()
            self.store.install_game("xd", cancel=cancel)
            self.assertTrue(all(self.store.installed(pack) for pack in packs.values()))

    def test_repair_xd_does_not_reinstall_shared_colosseum_pack(self):
        packs = self.fixture_packs()
        with patch.dict(PACKS, packs, clear=True):
            self.store.install_game("xd")
            before = (self.store.location(packs["colosseum"]) / "installed.json").read_bytes()
            with patch.object(self.store, "_download", wraps=self.store._download) as download:
                self.store.install_game("xd", force=True)
            self.assertEqual(download.call_count, 1)
            self.assertEqual((self.store.location(packs["colosseum"]) / "installed.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
