"""HD activation requires the genuine dual-asset contract, not legacy upscales."""
import hashlib
from contextlib import ExitStack
import json
import os
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
        self.data = {"game": "colosseum", "game_id": "GC6P01", "shared": str(self.root/"Shared"),
                     "features": {"overlays": self.plan}, "packs": {}}
        forms = patch("orre_randomizer.hd_extra_portraits.prepare_extra_portrait_overlays",
                      return_value={"files": {}, "assets": [], "active": False})
        self.forms = forms.start(); self.addCleanup(forms.stop)
        materials = patch("orre_randomizer.hd_form_materials.prepare_form_materials",
                          return_value={"files": {}, "assets": [], "active": False})
        self.materials = materials.start(); self.addCleanup(materials.stop)
        recipes = patch("orre_randomizer.hd_form_materials.material_recipes", return_value={})
        self.material_recipes = recipes.start(); self.addCleanup(recipes.stop)

    @unittest.skipUnless(os.name == "nt", "Windows directory sharing")
    def test_temporary_cache_publication_lock_retries_without_discarding_completed_art(self):
        for pack in PACKS.values():
            location = self.root / "Shared/TexturePacks" / pack.key
            location.mkdir(parents=True); (location / "installed.json").write_text('{}')
        payload, name = b"completed HD art", "tex1_4x4_0123456789abcdef_6.png"
        def render(_source, destination, **kwargs):
            destination.mkdir(parents=True); (destination / name).write_bytes(payload)
            return {"schema":2, "hd_ready":True, "files":[{"file":name,
                "sha256":hashlib.sha256(payload).hexdigest()}]}
        rename, attempts = Path.rename, []
        def temporarily_locked(path, target):
            if path.name == "assets":
                attempts.append(path)
                if len(attempts) == 1:
                    error = PermissionError("temporary cache directory lock"); error.winerror = 5
                    raise error
            return rename(path, target)
        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=render), \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", return_value={"files":{}, "assets":[]}), \
             patch.object(Path, "rename", temporarily_locked):
            result = prepare_custom_hd(self.folder, self.data)
        self.assertEqual(len(attempts), 2)
        self.assertEqual((Path(result["directory"]) / name).read_bytes(), payload)
        self.assertTrue((Path(result["directory"]) / "cache.json").is_file())
        self.assertFalse(list((self.folder / "Textures/HD").glob(".hd-*")))

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

    def test_face_companion_context_is_only_published_for_prepared_hd(self):
        dolphin = self.root / "Dolphin.exe"; dolphin.write_bytes(b"not executed")
        metadata = {"contract": "test-only", "game_id": "GC6P01"}
        data = {**self.data, "dolphin": str(dolphin), "rom": "Game/game.iso",
                "pack": PACKS["colosseum"].key,
                "features": {"spinda_face": metadata},
                "settings": {"graphics": "hd", "speed": 1, "native_music": False}}
        cache = self.root / "prepared"
        context = {"stale": "must not survive a later Original launch"}
        with patch("orre_randomizer.play_folders.prepare_custom_hd",
                   return_value={"directory": str(cache), "spinda_face": {"complete": True}}), \
             patch.object(PackStore, "texture_view", return_value=self.root / "Load"):
            launch_command(self.folder, data, session_context=context)
        self.assertEqual(context, {"spinda_face": {"assets": str(cache / "SpindaFace"), "metadata": metadata}})
        data["settings"]["graphics"] = "original"
        with patch("orre_randomizer.play_folders.prepare_custom_hd") as preparation:
            launch_command(self.folder, data, session_context=context)
        preparation.assert_not_called()
        self.assertEqual(context, {})

    def test_auxiliary_cache_files_are_authenticated_and_cannot_escape(self):
        from orre_randomizer.play_folders import _checked_cache_file
        cache = self.root / "cache"
        (cache / "TextSources").mkdir(parents=True)
        path = cache / "TextSources/license.txt"
        path.write_bytes(b"pinned license")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        cancel = threading.Event()
        self.assertTrue(_checked_cache_file(cache, "TextSources/license.txt", digest, cancel))
        for name in ("../outside", str(self.root / "outside"), "C:outside", None):
            with self.subTest(name=name):
                self.assertFalse(_checked_cache_file(cache, name, digest, cancel))
        path.write_bytes(b"changed")
        self.assertFalse(_checked_cache_file(cache, "TextSources/license.txt", digest, cancel))

    def test_missing_or_changed_native_font_guides_block_hd_before_rendering(self):
        reference = self.folder / "Textures/TextPages/plan.json"
        reference.parent.mkdir()
        payload = b"native font plan; renderer is not called in this test"
        data = {**self.data, "features": {**self.data["features"], "text_hd_bridge": {
            "auxiliary_files": {"TextPages/plan.json": hashlib.sha256(payload).hexdigest()}}}}
        for broken in (None, b"changed reference"):
            with self.subTest(missing=broken is None):
                if broken is not None:
                    reference.write_bytes(broken)
                with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
                     patch.object(PackStore, "installed", return_value=True), \
                     patch("orre_randomizer.hd_overlays.prepare_hd_overlays") as renderer, \
                     self.assertRaises(UserError):
                    prepare_custom_hd(self.folder, data)
                renderer.assert_not_called()
        self.assertFalse((self.folder / "Textures/HD").exists())

    def test_launcher_only_merges_packs_required_by_this_game_folder(self):
        dolphin = self.root / "Dolphin.exe"
        dolphin.write_bytes(b"not executed")
        prepared = self.root / "prepared"
        load = self.root / "texture-view/Load"
        scenarios = (("xd", [], (PACKS["colosseum"],)),
                     ("colosseum", [], ()),
                     ("colosseum", ["xd"], (PACKS["xd"],)))
        for game, dependencies, expected in scenarios:
            with self.subTest(game=game, dependencies=dependencies):
                data = {**self.data, "game": game, "game_id": "GXXP01" if game == "xd" else "GC6P01",
                        "pack": PACKS[game].key, "rom": "Game/game.iso", "dolphin": str(dolphin),
                        "features": {"overlays": {"required_packs": dependencies}},
                        "settings": {"graphics": "hd", "speed": 1, "native_music": False}}
                with patch("orre_randomizer.play_folders.prepare_custom_hd",
                           return_value={"directory": str(prepared)}), \
                     patch.object(PackStore, "texture_view", return_value=load) as view:
                    launch_command(self.folder, data, muted=True)
                view.assert_called_once_with(PACKS[game], data["game_id"], prepared,
                                             fallback_packs=expected)

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
             patch("orre_randomizer.hd_hud.hud_recipes", return_value={}), \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", return_value={"files": {}, "assets": []}), \
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

    def test_revised_form_materials_do_not_reuse_older_prepared_art(self):
        for pack in PACKS.values():
            location = self.root / "Shared/TexturePacks" / pack.key
            location.mkdir(parents=True)
            (location / "installed.json").write_text('{}')

        def prepared(_native, destination, **_kwargs):
            destination.mkdir(parents=True)
            return {"schema": 2, "hd_ready": True, "texture_count": 0, "files": []}

        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_hud.hud_recipes", return_value={}), \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", return_value={"files": {}, "assets": []}), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=prepared) as render:
            self.material_recipes.return_value = {"model": {"catalogue_sha256": "first"}}
            first = prepare_custom_hd(self.folder, self.data)
            self.material_recipes.return_value = {"model": {"catalogue_sha256": "second"}}
            second = prepare_custom_hd(self.folder, self.data)
            again = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(first["directory"], second["directory"])
        self.assertEqual(second["directory"], again["directory"])
        self.assertEqual(render.call_count, 2)
        self.assertTrue(Path(first["directory"]).is_dir())

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
             patch("orre_randomizer.hd_hud.hud_recipes", return_value={}), \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", return_value={"files": {}, "assets": []}), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=prepared) as render:
            first = prepare_custom_hd(self.folder, self.data)
            registry.write_text('{"recipe_version":"second"}')
            second = prepare_custom_hd(self.folder, self.data)
            again = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(first["directory"], second["directory"])
        self.assertEqual(second["directory"], again["directory"])
        self.assertEqual(render.call_count, 2)
        self.assertTrue(Path(first["directory"]).is_dir())

    def test_localized_hud_is_published_and_checked_with_the_custom_cache(self):
        for pack in PACKS.values():
            location = self.root / "Shared/TexturePacks" / pack.key
            location.mkdir(parents=True)
            (location / "installed.json").write_text('{}')
        data = {**self.data, "game": "xd", "game_id": "GXXP01"}
        hud_key = "tex1_258x20_0f24338507dc4276_223f8305fab2b998_9.png"
        payload = b"authenticated localized atlas"

        def custom(_native, destination, **_kwargs):
            destination.mkdir(parents=True)
            return {"schema": 2, "hd_ready": True, "texture_count": 0, "files": []}

        def localized(game_id, pack_roots, destination):
            self.assertEqual(game_id, "GXXP01")
            self.assertIn("xd", pack_roots)
            (destination / hud_key).write_bytes(payload)
            return {"files": {hud_key: hashlib.sha256(payload).hexdigest()}, "assets": []}

        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=custom), \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", side_effect=localized) as hud:
            first = prepare_custom_hd(self.folder, data)
            cached = prepare_custom_hd(self.folder, data)
            self.assertEqual(hud.call_count, 1)
            self.assertEqual(cached["directory"], first["directory"])
            self.assertEqual(cached["texture_count"], 1)
            self.assertEqual(cached["files"][0]["file"], hud_key)
            published = json.loads((Path(first["directory"]) / "orre-overlays-v2.json").read_text())
            self.assertEqual(published["files"], cached["files"])
            (Path(first["directory"]) / hud_key).write_bytes(b"damaged atlas")
            with self.assertRaises(UserError):
                prepare_custom_hd(self.folder, data)

    def test_failed_hud_preparation_leaves_no_published_partial_epoch(self):
        for pack in PACKS.values():
            location = self.root / "Shared/TexturePacks" / pack.key
            location.mkdir(parents=True)
            (location / "installed.json").write_text('{}')

        def custom(_native, destination, **_kwargs):
            destination.mkdir(parents=True)
            (destination / "already-prepared.png").write_bytes(b"keep private until complete")
            return {"schema": 2, "hd_ready": True, "texture_count": 0, "files": []}

        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=custom), \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", side_effect=ValueError("incorrect donor")):
            with self.assertRaises(UserError):
                prepare_custom_hd(self.folder, self.data)
        self.assertEqual(list((self.folder / "Textures/HD").iterdir()), [])

    def test_updated_hud_recipe_does_not_reuse_prepared_art_from_an_older_recipe(self):
        for pack in PACKS.values():
            location = self.root / "Shared/TexturePacks" / pack.key
            location.mkdir(parents=True)
            (location / "installed.json").write_text('{}')

        def custom(_native, destination, **_kwargs):
            destination.mkdir(parents=True)
            return {"schema": 2, "hd_ready": True, "texture_count": 0, "files": []}

        with patch("orre_randomizer.hd_overlays.native_asset_manifest", return_value=self.plan), \
             patch.object(PackStore, "installed", return_value=True), \
             patch("orre_randomizer.hd_overlays.prepare_hd_overlays", side_effect=custom) as render, \
             patch("orre_randomizer.hd_hud.hud_recipes", return_value={"version": 1}) as recipes, \
             patch("orre_randomizer.hd_hud.prepare_hud_overlays", return_value={"files": {}, "assets": []}):
            first = prepare_custom_hd(self.folder, self.data)
            recipes.return_value = {"version": 2}
            second = prepare_custom_hd(self.folder, self.data)
            again = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(first["directory"], second["directory"])
        self.assertEqual(second["directory"], again["directory"])
        self.assertEqual(render.call_count, 2)
        self.assertTrue(Path(first["directory"]).is_dir())


class SpindaGameFolderIntegrationTests(unittest.TestCase):
    def setUp(self):
        text = patch("orre_randomizer.play_folders._prepare_text_hd", return_value={})
        text.start()
        self.addCleanup(text.stop)

    def test_unqualified_face_keeps_native_rendering_without_reserving_its_banks(self):
        for game_id in ("GC6P01", "GC6E01", "GC6J01"):
            for qualified in (False, True):
                with self.subTest(game_id=game_id, qualified=qualified), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "original.iso"
                    source.write_bytes(b"pristine executable")
                    output = root / "randomized.iso"
                    boot = game_id.encode("ascii") + bytes(0x440 - 6)
                    references = {"DNA_key.fsys": b"keypad", "poke_body.fsys": b"bodies",
                                  "pkx_patcheel.fsys": b"spinda"}
                    with ExitStack() as stack:
                        def mock(name, **kwargs):
                            return stack.enter_context(patch(name, **kwargs))
                        mock("orre_randomizer.artwork._disc_files", return_value=references)
                        mock("orre_randomizer.engine.dna_hd_tiles.split_keypad_archive",
                             return_value=(b"cells", {}))
                        mock("orre_randomizer.engine.analyze_game.parse_fsys", return_value={"members": [
                            {"name": name} for name in ("face", "buti_a", "patcheel")]})
                        mock("orre_randomizer.engine.rebuild_iso.decoded_member", return_value=b"native")
                        mock("orre_randomizer.engine.actor_palette.pkx_recipe", return_value=((), ()))
                        mock("orre_randomizer.engine.dna_spinda_hd.extend_spinda_keypad_archive",
                             return_value=(b"extended cells", {}))
                        mock("orre_randomizer.engine.regions.region_for_boot",
                             return_value=SimpleNamespace(dol_size=19))
                        mock("orre_randomizer.play_rom.read_executable", return_value=b"current executable")
                        tiles = mock("orre_randomizer.engine.dna_hd_tiles.install_dna_hd_tile_bridge",
                                     return_value=(b"tile executable", {}))
                        mock("orre_randomizer.play_rom.update_staged_disc", return_value={})
                        mock("orre_randomizer.engine.dna_spinda_face_hd.face_runtime_validated",
                             return_value=qualified)
                        face = mock("orre_randomizer.engine.dna_spinda_face_hd.patch_spinda_face_bridge",
                                    return_value=(b"face executable", {"game_id": game_id}))
                        guides = mock("orre_randomizer.hd_spinda_face.capture_native_face_assets")
                        mock("orre_randomizer.play_folders.file_hash", return_value="reference hash")
                        mock("orre_randomizer.hd_overlays.capture_native_assets", return_value={"texture_count": 0})
                        mock("orre_randomizer.engine.play_music_bridge.SUPPORTED_GAME_IDS", new=set())
                        features = _prepare_extras(source, output, boot, root / "stage", root / "shared",
                            lambda *_: None, threading.Event(), asset_context={
                                "dna_lab": {"153": {"species": 308, "shiny": False}}})
                    tiles.assert_called_once()
                    if qualified:
                        face.assert_called_once_with(b"pristine executable", b"current executable",
                                                     game_id=game_id, revision=0)
                        guides.assert_called_once()
                        self.assertIn("spinda_face", features)
                    else:
                        face.assert_not_called()
                        guides.assert_not_called()
                        self.assertNotIn("spinda_face", features)
                    self.assertIn("dna_hd_tiles", features)
                    self.assertIn("text_hd_bridge", features)
                    self.assertEqual(source.read_bytes(), b"pristine executable")

    def test_hd_creation_supplies_exact_region_identity_to_hud_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for game_id, game in (("GC6P01", "colosseum"), ("GXXP01", "xd"),
                                  ("GC6J01", "colosseum"), ("GXXE01", "xd")):
                with self.subTest(game_id=game_id):
                    boot = game_id.encode("ascii") + bytes(0x440 - 6)

                    def prepared(stage, manifest, **kwargs):
                        self.assertEqual(manifest["game_id"], game_id)
                        self.assertEqual(manifest["game"], game)
                        self.assertEqual(manifest["shared"], str(root / "shared"))
                        self.assertIs(kwargs["cancel"], cancel)
                        return {"texture_count": 5}

                    cancel = threading.Event()
                    with patch("orre_randomizer.hd_overlays.capture_native_assets",
                               return_value={"texture_count": 1}), \
                         patch("orre_randomizer.play_folders.prepare_custom_hd", side_effect=prepared), \
                         patch("orre_randomizer.engine.play_music_bridge.SUPPORTED_GAME_IDS", set()):
                        features = _prepare_extras(root / "original.iso", root / "randomized.iso", boot,
                            root / "stage", root / "shared", lambda *_: None, cancel, hd_requested=True)
                    self.assertTrue(features["overlays"]["hd_ready"])
                    self.assertEqual(features["overlays"]["hd_count"], 5)

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
