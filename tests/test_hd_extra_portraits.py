"""Additional portraits fail closed on changed native identity or capture proof."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtGui import QImage
from orre_randomizer import hd_extra_portraits as portraits
from orre_randomizer.hd_extra_portrait_catalog import MODEL_IDENTITIES, HD_MATERIAL_SOURCE_PINS
from orre_randomizer.hd_packs import PACKS


@contextmanager
def registered():
    game, key = next((g, k) for g, k in portraits._CATALOG if g == "xd" and portraits._CATALOG[g, k][0] == "face410def")
    original = portraits._CATALOG[game, key]
    member = original[0]
    native_pixels = bytearray()
    for y in range(84):
        for x in range(42):
            inside = (x + .5 - 21) ** 2 + ((y % 42) + .5 - 21) ** 2 < 22 ** 2
            native_pixels.extend((128, 144, 160, 255) if inside else (0, 0, 0, 0))
    native = QImage(bytes(native_pixels), 42, 84, 168, QImage.Format.Format_RGBA8888).copy()
    native_sha = hashlib.sha256(bytes(native.constBits())).hexdigest()
    portraits._CATALOG[game, key] = (member, native_sha)
    try:
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            origin = portraits.portrait_origin(game, key, (42, 84))
            hd_pixels = bytearray()
            for y in range(336):
                for x in range(168):
                    alpha = native_pixels[((y // 4) * 42 + x // 4) * 4 + 3]
                    hd_pixels.extend((160, 176, 192, 255) if alpha else (0, 0, 0, 0))
            image = QImage(bytes(hd_pixels), 168, 336, 672, QImage.Format.Format_RGBA8888).copy()
            image.save(str(folder / "deoxys-defence-xd.png"))
            pack = PACKS["xd"]
            captures, frames = {}, []
            for shiny in (False, True):
                capture_id = "defence-shiny" if shiny else "defence-normal"
                model = MODEL_IDENTITIES[member][shiny]
                recipes = [{"target": target, "kind": "exact-pack-material", "sha256": "a" * 64,
                            "native_bitmap_resampled": False,
                            "reference": {"source_scale": 4, "sha256": HD_MATERIAL_SOURCE_PINS['xd'][target],
                                          "physical_file": target}}
                           for target in model["material_keys"]]
                captures[capture_id] = dict(model, sha256="c" * 64, pose_signature_sha256="d" * 64,
                    camera={"method": "unchanged analyzer camera from qualified fresh state",
                            "render_target": [256, 256], "cobj_readback_captured": False},
                    source_dimensions=[1024, 1024],
                    native_bitmap_upscaled_for_hd=False, material_recipes=recipes,
                    pack=pack.key, archives=[part.sha256 for part in pack.parts])
                frames.append({"shiny": shiny, "capture": capture_id, "source_crop": [200, 200, 440, 440]})
            manifest = {"schema": 1, "kind": "native-form-mesh-render-portrait", "review_only": False,
                "captures": captures, "files": {"xd/face410def": {
                    "file": "deoxys-defence-xd.png", "sha256": hashlib.sha256((folder / "deoxys-defence-xd.png").read_bytes()).hexdigest(),
                    "native_key": key, "native_rgba_sha256": native_sha, "dimensions": [168, 336], "frames": frames}}}
            yield folder, origin, native, manifest
    finally:
        portraits._CATALOG[game, key] = original


def render(fixture):
    directory, origin, native, manifest = fixture
    (directory / "extra-portraits.json").write_text(json.dumps(manifest), encoding="utf8")
    return portraits.render_extra_portrait(origin, native_image=native, asset_directory=directory)


@contextmanager
def registered_catalog():
    with registered() as fixture:
        folder, _, _, manifest = fixture
        round_image = (folder / "deoxys-defence-xd.png").read_bytes()
        square = QImage(168, 336, QImage.Format.Format_RGBA8888)
        square.fill(0xFF90A0B0)
        square.save(str(folder / "square.png"))
        manifest["captures"], manifest["files"] = {}, {}
        for (game, key), (member, rgba) in portraits._CATALOG.items():
            source_game = "colosseum" if member.startswith("face385") else "xd"
            pack = PACKS[source_game]
            filename = game + "-" + member + ".png"
            payload = (folder / "square.png").read_bytes() if game == "colosseum" else round_image
            (folder / filename).write_bytes(payload)
            frames = []
            for shiny in (False, True):
                model = MODEL_IDENTITIES[member][shiny]
                capture_id = game + "-" + member + "-" + str(shiny)
                pins = HD_MATERIAL_SOURCE_PINS[source_game]
                recipes = []
                for target in model["material_keys"]:
                    source = target if target in pins else next(iter(pins))
                    physical = source.replace(".png", ".dds") if source_game == "colosseum" else source
                    recipes.append({"target": target, "sha256": "a" * 64,
                        "kind": "exact-pack-material" if target in pins else "authored-pack-derived-material",
                        "native_bitmap_resampled": False,
                        "reference": {"source_scale": 4, "sha256": pins[source], "physical_file": physical}})
                manifest["captures"][capture_id] = dict(model, sha256="c" * 64,
                    pose_signature_sha256="d" * 64, camera={"method": "declared fixture camera",
                        "render_target": [256, 256], "cobj_readback_captured": False},
                    source_dimensions=[1024, 1024], native_bitmap_upscaled_for_hd=False,
                    material_recipes=recipes, pack=pack.key, archives=[p.sha256 for p in pack.parts])
                frames.append({"shiny": shiny, "capture": capture_id, "source_crop": [200, 200, 440, 440]})
            manifest["files"][game + "/" + member] = {"file": filename,
                "sha256": hashlib.sha256(payload).hexdigest(), "dimensions": [168, 336],
                "native_key": key, "native_rgba_sha256": rgba, "frames": frames}
        (folder / "extra-portraits.json").write_text(json.dumps(manifest))
        packs = {}
        for game, pack in PACKS.items():
            path = folder / ("pack-" + game)
            path.mkdir()
            (path / "installed.json").write_text(json.dumps({"key": pack.key,
                "archives": [p.sha256 for p in pack.parts]}))
            packs[game] = path
        yield folder, packs, manifest


class ExtraPortraitTests(unittest.TestCase):
    def test_catalogue_contains_all_nine_native_atlases_without_base_form(self):
        self.assertEqual(len(portraits._CATALOG), 9)
        for (game, key), (member, rgba) in portraits._CATALOG.items():
            origin = portraits.portrait_origin(game, key, (42, 84))
            self.assertEqual(origin["transform"]["member"], member)
            self.assertEqual(len(rgba), 64)
            self.assertEqual(origin["required_packs"], ["colosseum" if "385" in member else "xd"])
        self.assertIsNone(portraits.portrait_origin("xd", "tex1_42x84_unknown_9.png", (42, 84)))

    def test_region_ids_and_mipmap_alias_without_accepting_changed_dimensions(self):
        for game_id, game in (("GC6P01", "colosseum"), ("GXXE01", "xd")):
            key = next(key for g, key in portraits._CATALOG if g == game)
            alias = key.replace("tex1_42x84_", "tex1_42x84_m_", 1)
            self.assertEqual(portraits.portrait_origin(game_id, alias, (42, 84)),
                             portraits.portrait_origin(game, key, (42, 84)))
            with self.assertRaisesRegex(ValueError, "dimensions"):
                portraits.portrait_origin(game_id, key, (84, 84))

    def test_gen3_weather_colours_are_shared_but_deoxys_shiny_is_distinct(self):
        for member in ("face385f", "face385i", "face385w"):
            self.assertEqual(MODEL_IDENTITIES[member][False], MODEL_IDENTITIES[member][True])
        for member in ("face410atk", "face410def", "face410sp"):
            self.assertNotEqual(MODEL_IDENTITIES[member][False]["dat_sha256"], MODEL_IDENTITIES[member][True]["dat_sha256"])

    def test_registered_capture_returns_exact_atlas_and_provenance(self):
        with registered() as fixture:
            image, proof = render(fixture)
            self.assertEqual((image.width(), image.height()), (168, 336))
            self.assertFalse(proof["native_bitmap_upscaled_for_hd"])
            self.assertEqual(proof["pose_signature_sha256"], "d" * 64)

    def test_changed_pose_form_pack_or_upscaled_native_is_rejected(self):
        for field, value in (("pose_signature_sha256", "f" * 64), ("camera", {"changed": True}),
            ("matrix_count", 51), ("model_sha256", "f" * 64), ("dat_sha256", "f" * 64),
            ("source_dimensions", [256, 256]), ("native_bitmap_upscaled_for_hd", True),
            ("archives", ["f" * 64]), ("material_keys", [])):
            with self.subTest(field=field), registered() as fixture:
                fixture[3]["captures"]["defence-shiny"][field] = value
                with self.assertRaises(ValueError):
                    render(fixture)

    def test_missing_material_cannot_be_a_stock_fallback(self):
        with registered() as fixture:
            fixture[3]["captures"]["defence-normal"]["material_recipes"].pop()
            with self.assertRaisesRegex(ValueError, "coverage"):
                render(fixture)

    def test_inherited_stock_material_is_rejected(self):
        with registered() as fixture:
            fixture[3]["captures"]["defence-normal"]["material_recipes"][0]["kind"] = "inherited_stock"
            with self.assertRaisesRegex(ValueError, "genuine HD"):
                render(fixture)

    def test_unreviewed_capture_is_rejected(self):
        with registered() as fixture:
            fixture[3]["review_only"] = True
            with self.assertRaisesRegex(ValueError, "review"):
                render(fixture)

    def test_native_pixels_are_identity_checked(self):
        with registered() as fixture:
            fixture[2].setPixel(20, 20, 0xFFFFFFFF)
            with self.assertRaisesRegex(ValueError, "native.*pixels"):
                render(fixture)

    def test_png_tampering_is_rejected(self):
        with registered() as fixture:
            (fixture[0] / "deoxys-defence-xd.png").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "integrity"):
                render(fixture)

    def test_missing_capture_remains_unavailable(self):
        with registered() as fixture:
            fixture[3]["files"].clear()
            with self.assertRaisesRegex(FileNotFoundError, "registered HD capture"):
                render(fixture)

    def test_a_registered_xd_atlas_cannot_substitute_a_square_frame(self):
        with registered() as fixture:
            image = QImage(168, 336, QImage.Format.Format_RGBA8888)
            image.fill(0xFFFFFFFF)
            path = fixture[0] / "deoxys-defence-xd.png"
            image.save(str(path))
            fixture[3]["files"]["xd/face410def"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "round frame"):
                render(fixture)

    def test_portrait_crop_cannot_enlarge_a_small_bitmap(self):
        with registered() as fixture:
            for frame in fixture[3]["files"]["xd/face410def"]["frames"]:
                frame["source_crop"] = [20, 20, 62, 62]
            with self.assertRaisesRegex(ValueError, "enlarge"):
                render(fixture)

    def test_native_capture_selection_is_gated_on_the_complete_registry(self):
        from orre_randomizer.hd_overlays import _selected
        for (game, _), (member, _) in portraits._CATALOG.items():
            record = {"name": member, "identifier_raw": "0x12341200"}
            with patch.object(portraits, "extra_portraits_registered", return_value=False):
                self.assertIsNone(_selected("poke_face.fsys", record, game == "xd"))
            with patch.object(portraits, "extra_portraits_registered", return_value=True):
                self.assertEqual(_selected("poke_face.fsys", record, game == "xd"), "retail_form")
        with patch.object(portraits, "extra_portraits_registered", return_value=True):
            for member in ("face412", "face1001"):
                self.assertIsNone(_selected("poke_face.fsys", {"name": member, "identifier_raw": "0x12341200"}, True))

    def test_overlay_dispatch_uses_registered_image_without_a_fictitious_pack_texture(self):
        from orre_randomizer import hd_overlays as overlays
        with registered() as fixture:
            image, proof = render(fixture)
            folder, origin, native, _ = fixture
            key = origin["transform"]["native_key"]
            native_report = {"assets": [{"file": key, "base_key": key, "native_format": 9,
                "role": "retail_form", "native": {"width": 42, "height": 84}, "hd": origin}]}
            pack_folder = folder / "pack"
            pack_folder.mkdir()
            (pack_folder / "installed.json").write_text(json.dumps({"key": PACKS["xd"].key,
                "archives": [part.sha256 for part in PACKS["xd"].parts]}))
            with patch.object(overlays, "native_asset_manifest", return_value=native_report), \
                    patch.object(overlays, "_load_reference", return_value=native), \
                    patch.object(overlays, "_resolve_hd", side_effect=AssertionError("No texture lookup for a rendered atlas")), \
                    patch.object(portraits, "render_extra_portrait", return_value=(image, proof)):
                result = overlays.prepare_hd_overlays(folder, folder / "HD", pack_roots={"xd": pack_folder})
            self.assertTrue(result["hd_ready"])
            self.assertEqual(result["texture_count"], 1)
            self.assertEqual(result["files"][0]["hd_source"]["kind"], "native-form-mesh-render-portrait")

    def test_missing_registered_image_blocks_hd_preparation(self):
        from orre_randomizer import hd_overlays as overlays
        with registered() as fixture:
            folder, origin, native, _ = fixture
            key = origin["transform"]["native_key"]
            native_report = {"assets": [{"file": key, "base_key": key, "native_format": 9,
                "role": "retail_form", "native": {"width": 42, "height": 84}, "hd": origin}]}
            pack_folder = folder / "pack"
            pack_folder.mkdir()
            (pack_folder / "installed.json").write_text(json.dumps({"key": PACKS["xd"].key,
                "archives": [part.sha256 for part in PACKS["xd"].parts]}))
            with patch.object(overlays, "native_asset_manifest", return_value=native_report), \
                    patch.object(overlays, "_load_reference", return_value=native), \
                    patch.object(portraits, "render_extra_portrait", side_effect=FileNotFoundError("capture absent")):
                result = overlays.prepare_hd_overlays(folder, folder / "HD", pack_roots={"xd": pack_folder})
            self.assertFalse(result["hd_ready"])
            self.assertEqual(result["missing_assets"][0]["reason"], "capture absent")

    def test_legacy_addition_never_manufactures_a_native_image(self):
        with registered_catalog() as (folder, packs, _), \
                patch.object(portraits, "render_extra_portrait", side_effect=AssertionError("No native image is available")):
            result = portraits.prepare_extra_portrait_overlays("GXXP01", packs, folder / "HD", asset_directory=folder)
            self.assertTrue(result["active"])
            self.assertEqual(len(result["files"]), 6)
            self.assertEqual(result["required_packs"], ["colosseum", "xd"])
            self.assertFalse(result["native_rgba_read_at_launch"])
            self.assertTrue(all(row["components"]["identity_validation"] == "catalogued-native-dolphin-key"
                                for row in result["assets"]))
            for filename, sha in result["files"].items():
                self.assertEqual(hashlib.sha256((folder / "HD" / filename).read_bytes()).hexdigest(), sha)

    def test_colosseum_global_addition_requires_only_its_weather_pack(self):
        with registered_catalog() as (folder, packs, _):
            result = portraits.prepare_extra_portrait_overlays("GC6P01", {"colosseum": packs["colosseum"]},
                folder / "HD", asset_directory=folder)
            self.assertEqual(len(result["files"]), 3)
            self.assertEqual(result["required_packs"], ["colosseum"])

    def test_global_addition_validates_all_nine_pngs_before_writing(self):
        with registered_catalog() as (folder, packs, manifest):
            missing = manifest["files"]["xd/face410sp"]["file"]
            (folder / missing).unlink()
            with self.assertRaises(FileNotFoundError):
                portraits.prepare_extra_portrait_overlays("GC6P01", packs, folder / "HD", asset_directory=folder)
            self.assertFalse((folder / "HD").exists())

    def test_incomplete_registry_keeps_the_previous_native_fallback(self):
        with registered_catalog() as (folder, packs, manifest):
            manifest["files"].pop("xd/face410sp")
            (folder / "extra-portraits.json").write_text(json.dumps(manifest))
            result = portraits.prepare_extra_portrait_overlays("GXXP01", packs, folder / "HD", asset_directory=folder)
            self.assertFalse(result["active"])
            self.assertEqual(result["files"], {})
            self.assertFalse((folder / "HD").exists())

    def test_material_reference_cannot_claim_an_arbitrary_file_as_upstream_hd(self):
        with registered() as fixture:
            fixture[3]["captures"]["defence-normal"]["material_recipes"][0]["reference"]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "actual pinned HD source"):
                render(fixture)


if __name__ == "__main__":
    unittest.main()
