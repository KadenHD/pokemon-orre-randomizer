"""HD activation requires the genuine dual-asset contract, not legacy upscales."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer.hd_packs import PACKS, PackStore
from orre_randomizer.play_folders import missing_hd_packs, prepare_custom_hd, launch_command, _prepare_extras
from orre_randomizer.service import Cancelled, UserError


class HdGameFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "Party"
        (self.folder / "Textures").mkdir(parents=True)
        (self.folder / "Textures/orre-overlays-v2.json").write_text('{"schema":2}')
        self.plan = {"schema": 2, "required_packs": ["xd"], "assets": []}
        self.data = {"game": "colosseum", "shared": str(self.root/"Shared"),
                     "features": {"overlays": self.plan}, "packs": {}}

    def test_cross_game_custom_model_exposes_both_pack_dependencies(self):
        with patch.object(PackStore, "installed", side_effect=lambda pack: pack.game == "colosseum"):
            self.assertEqual(missing_hd_packs(self.data), ["xd"])

    def test_a_legacy_filtered_image_is_never_accepted_as_a_dual_asset_contract(self):
        (self.folder / "Textures/orre-overlays-v2.json").unlink()
        (self.folder / "Textures/tex1_4x4_deadbeef_6.png").write_bytes(b'legacy upscale')
        with self.assertRaises(UserError):
            prepare_custom_hd(self.folder, self.data)

    def test_missing_donor_pack_blocks_preparation_before_rendering(self):
        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=False), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays") as render:
            with self.assertRaises(UserError):
                prepare_custom_hd(self.folder, self.data)
        render.assert_not_called()

    def test_incomplete_hd_is_not_published_or_silently_substituted(self):
        packs = self.root / "Shared/TexturePacks"
        for name in (PACKS["colosseum"].key, PACKS["xd"].key):
            (packs/name).mkdir(parents=True)
            (packs/name/"installed.json").write_text('{}')
        incomplete = {"schema":2, "hd_ready":False, "texture_count":0,
                      "files":[], "missing_assets":[{"file":"new-model", "reason":"HD donor missing"}]}
        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", return_value=incomplete):
            with self.assertRaises(UserError):
                prepare_custom_hd(self.folder, self.data)
        self.assertFalse(list((self.folder/"Textures/HD").iterdir()))
        self.assertTrue((self.folder/"Textures/hd-diagnostics.json").is_file())

    def test_native_mode_never_prepares_or_requires_hd(self):
        dolphin = self.root / "Dolphin.exe"; dolphin.write_bytes(b'not executed')
        data = {**self.data, "game_id":"GC6P01", "rom":"Game/game.iso", "dolphin":str(dolphin),
                "settings":{"graphics":"original", "speed":1, "native_music":False}}
        with patch("orre_randomizer.play_folders.prepare_custom_hd") as prepare:
            command = launch_command(self.folder, data, muted=True)
        prepare.assert_not_called()
        self.assertIn("Dolphin.DSP.Volume=0", command)

    def test_new_recipe_revision_rebuilds_without_changing_native_assets(self):
        packs = self.root / "Shared/TexturePacks"
        for pack in PACKS.values():
            (packs / pack.key).mkdir(parents=True)
            (packs / pack.key / "installed.json").write_text('{}')
        source = self.folder / "Textures/orre-overlays-v2.json"
        before = source.read_bytes()
        complete = {"schema": 2, "hd_ready": True, "texture_count": 0, "files": []}
        def prepared(_native, destination, **_kwargs):
            destination.mkdir(parents=True)
            return complete.copy()
        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=prepared) as render:
            with patch("orre_randomizer.play_folders.HD_CACHE_REVISION", 1):
                previous = prepare_custom_hd(self.folder, self.data)
            with patch("orre_randomizer.play_folders.HD_CACHE_REVISION", 2):
                current = prepare_custom_hd(self.folder, self.data)
                again = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(previous["directory"], current["directory"])
        self.assertEqual(current["directory"], again["directory"])
        self.assertEqual(current["generator_revision"], 2)
        self.assertEqual(render.call_count, 2)
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue(Path(previous["directory"]).is_dir())

    def test_revised_portrait_registry_does_not_reuse_older_prepared_art(self):
        packs = self.root / "Shared/TexturePacks"
        for pack in PACKS.values():
            (packs / pack.key).mkdir(parents=True)
            (packs / pack.key / "installed.json").write_text('{}')
        models = self.root / "assets/models"
        models.mkdir(parents=True)
        registry = models / "portrait-variants.json"
        registry.write_text('{"recipe_version":"first"}')

        def prepared(_native, destination, **_kwargs):
            destination.mkdir(parents=True)
            return {"schema": 2, "hd_ready": True, "texture_count": 0, "files": []}

        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch("orre_randomizer.resources.bundle_root", return_value=models.parent), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=prepared) as render:
            first = prepare_custom_hd(self.folder, self.data)
            registry.write_text('{"recipe_version":"second"}')
            second = prepare_custom_hd(self.folder, self.data)
            again = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(first["directory"], second["directory"])
        self.assertEqual(second["directory"], again["directory"])
        self.assertEqual(render.call_count, 2)
        self.assertTrue(Path(first["directory"]).is_dir())


class SpindaGameFolderIntegrationTests(unittest.TestCase):
    def test_native_adapter_receives_pristine_art_and_blocks_publication_on_failure(self):
        """Randomized output is not a valid donor for a saved-PID adapter."""
        from orre_randomizer.engine.analyze_game import FormatError
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "original.iso", root / "randomized.iso"
            source.write_bytes(b"pristine executable")
            output.write_bytes(b"staged disc must remain intact")
            source_before, output_before = source.read_bytes(), output.read_bytes()
            boot = bytearray(0x440)
            boot[:6] = b"GC6P01"
            struct.pack_into(">I", boot, 0x420, 0)
            references = {"DNA_key.fsys": b"pristine keypad", "poke_body.fsys": b"pristine bodies",
                          "pkx_patcheel.fsys": b"pristine Spinda"}

            def archives(path, names):
                if path == output:
                    return {"DNA_key.fsys": b"randomized keypad"}
                self.assertEqual(path, source)
                return {name: references[name] for name in names}

            def refused(archive, layout, samples, face, spot, recipe, **donors):
                self.assertEqual(archive, b"independent cells")
                self.assertEqual(samples, [153])
                self.assertEqual((face, spot), (b"face", b"buti_a"))
                self.assertEqual(donors, {"original_keypad": references["DNA_key.fsys"],
                                          "bodies_archive": references["poke_body.fsys"]})
                raise FormatError("PID adapter refused an unverified source")

            with patch("orre_randomizer.artwork._disc_files", side_effect=archives), \
                 patch("orre_randomizer.engine.dna_hd_tiles.split_keypad_archive",
                       return_value=(b"independent cells", {})), \
                 patch("orre_randomizer.engine.analyze_game.parse_fsys",
                       return_value={"members": [{"name": name} for name in ("face", "buti_a", "patcheel")]}), \
                 patch("orre_randomizer.engine.rebuild_iso.decoded_member",
                       side_effect=lambda raw, member: member["name"].encode()), \
                 patch("orre_randomizer.engine.actor_palette.pkx_recipe", return_value=((), ())), \
                 patch("orre_randomizer.engine.dna_spinda_hd.extend_spinda_keypad_archive", side_effect=refused), \
                 patch("orre_randomizer.engine.dna_hd_tiles.install_dna_hd_tile_bridge") as bridge, \
                 patch("orre_randomizer.play_rom.update_staged_disc") as publish, \
                 patch("orre_randomizer.hd_overlays.capture_native_assets") as capture:
                with self.assertRaisesRegex(FormatError, "PID adapter refused"):
                    _prepare_extras(source, output, bytes(boot), root / "stage", root / "shared",
                                    lambda *_: None, threading.Event(), asset_context={
                                        "dna_lab": {"153": {"species": 308, "shiny": False},
                                                    "287": {"species": 308, "shiny": False},
                                                    "244": {"species": 249, "shiny": True}}})
                bridge.assert_not_called()
                publish.assert_not_called()
                capture.assert_not_called()
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(output.read_bytes(), output_before)

    def test_ordinary_keypad_uses_existing_bridge_without_reading_spinda_donors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "original.iso", root / "randomized.iso"
            source.write_bytes(b"original executable")
            boot = bytearray(0x440)
            boot[:6] = b"GC6P01"
            with patch("orre_randomizer.artwork._disc_files", return_value={"DNA_key.fsys": b"keypad"}) as archives, \
                 patch("orre_randomizer.engine.dna_hd_tiles.split_keypad_archive", return_value=(b"cells", {})), \
                 patch("orre_randomizer.engine.regions.region_for_boot", return_value=SimpleNamespace(dol_size=19)), \
                 patch("orre_randomizer.play_rom.read_executable", return_value=b"executable"), \
                 patch("orre_randomizer.engine.dna_hd_tiles.install_dna_hd_tile_bridge", return_value=(b"patched", {})), \
                 patch("orre_randomizer.play_rom.update_staged_disc", return_value={}), \
                 patch("orre_randomizer.hd_overlays.capture_native_assets", return_value={"texture_count": 0}), \
                 patch("orre_randomizer.engine.play_music_bridge.SUPPORTED_GAME_IDS", set()), \
                 patch("orre_randomizer.engine.dna_spinda_hd.extend_spinda_keypad_archive") as adapter:
                _prepare_extras(source, output, bytes(boot), root / "stage", root / "shared",
                                lambda *_: None, threading.Event(), asset_context={
                                    "dna_lab": {"153": {"species": 1, "shiny": False}}})
                adapter.assert_not_called()
                self.assertTrue(all(call.args[0] == output for call in archives.call_args_list))


if __name__ == "__main__":
    unittest.main()
