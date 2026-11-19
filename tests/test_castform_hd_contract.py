"""Actual synthetic archives must bind custom weather resources to native/x4 pairs."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtGui import QImage

from orre_randomizer import hd_castform_shinies as art
from orre_randomizer import hd_overlays as hd
from orre_randomizer.hd_form_materials import material_recipes
from orre_randomizer.hd_packs import PACKS
from tests.test_artwork import portrait
from tests.test_hd_castform_shinies import artwork, record
from tests.test_hd_overlays import archive, disc
from tests.test_shadow_lugia_palette import fixture as model_fixture


def bind_model(bundle, catalogue, payloads, save, raw, *, xd=False):
    texture = next(hd._dat_textures(hd._pkx_dat(raw, xd)))
    key = hd._texture_key(texture)
    item = catalogue["files"][0]
    image = Image.new("RGBA", (texture.width * 4, texture.height * 4), (180, 90, 220, 255))
    path = bundle / "castform-shinies" / item["file"]
    image.save(path)
    payload = path.read_bytes()
    item.update(record(payload), native_key=key,
        native_dimensions=[texture.width, texture.height], dimensions=list(image.size),
        native_rgba_sha256=hashlib.sha256(hd._pixels(texture)).hexdigest())
    payloads["castform-shinies/" + item["file"]] = payload
    save()
    return key


def capture(source, native, *, xd=False):
    # These tests qualify the weather contract; existing tests independently
    # qualify the unrelated Lugia and generic stock-field origin catalogues.
    with patch.object(hd, "_dark_origins", return_value={}), \
            patch("orre_randomizer.hd_form_materials.material_recipes", return_value={}):
        return hd.capture_native_assets(source, native, is_xd=xd)


class CastformNativeHDContractTests(unittest.TestCase):
    def test_selection_uses_only_the_three_reserved_archive_and_resource_pairs(self):
        for name, resource in hd._CASTFORM_ARCHIVES.items():
            self.assertEqual(hd._selected(name, {"identifier_raw": hex(resource), "name": "custom"}, False), "castform_battle")
            self.assertIsNone(hd._selected("pkx_unrelated.fsys", {"identifier_raw": hex(resource), "name": "custom"}, False))
        for resource in hd._CASTFORM_FACES:
            self.assertEqual(hd._selected("poke_face.fsys", {"identifier_raw": hex(resource), "name": "custom"}, False), "castform_portrait")

    def test_bounded_archive_selection_does_not_turn_on_the_all_pkx_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.iso"
            resource = archive([(0x7DA21E00, "custom", model_fixture(False)[0])])
            disc(path, [("pkx_powalen_f.fsys", resource), ("pkx_unrelated.fsys", resource)])
            self.assertEqual([name for name, _ in hd._disc_archives(path, is_xd=False)], ["pkx_powalen_f.fsys"])

    def test_custom_model_capture_and_hd_output_use_exact_registered_png_bytes(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            raw = model_fixture(False)[0]
            key = bind_model(bundle, catalogue, payloads, save, raw)
            source = root / "fixture.iso"
            disc(source, [("pkx_powalen_f.fsys", archive([(0x7DA21E00, "custom_sun", raw)]))])
            original = source.read_bytes()
            native = root / "Native"
            captured = capture(source, native)
            self.assertEqual(captured["resources"][0]["role"], "castform_battle")
            self.assertTrue(captured["castform_shinies"]["native_rgba_bound"])
            self.assertEqual(captured["required_packs"], ["colosseum"])
            self.assertEqual(captured["assets"][0]["hd"]["transform"]["native_rgba_sha256"], catalogue["files"][0]["native_rgba_sha256"])
            with patch.object(hd, "_resolve_hd", side_effect=AssertionError("No generic identity lookup")):
                prepared = hd.prepare_hd_overlays(native, root / "HD", pack_roots={"colosseum": pack})
            self.assertTrue(prepared["hd_ready"])
            self.assertEqual((root / "HD" / key).read_bytes(), payloads["castform-shinies/model-map.png"])
            self.assertFalse(prepared["files"][0]["hd_source"]["components"]["native_bitmap_resampled"])
            # The later party-cache installer may encounter the same key; its
            # exact bytes must agree rather than creating a false conflict.
            repeated = art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, root / "HD")
            self.assertEqual(repeated["files"][key], prepared["files"][0]["sha256"])
            self.assertEqual(source.read_bytes(), original)

    def test_separate_face_resource_uses_the_custom_catalogue_not_the_nine_retail_guards(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            raw = portrait((70, 90, 120, 255), (170, 20, 200, 255))
            texture = hd._face(raw)
            key = hd._texture_key(texture)
            item = catalogue["files"][1]
            item.update(native_key=key, native_rgba_sha256=hashlib.sha256(hd._pixels(texture)).hexdigest())
            save()
            source = root / "fixture.iso"
            disc(source, [("poke_face.fsys", archive([(0x7DA21200, "custom_sunny_face", raw)]))])
            with patch("orre_randomizer.hd_extra_portraits.portrait_origin", side_effect=AssertionError("Retail identity stays separate")):
                captured = capture(source, root / "Native")
                prepared = hd.prepare_hd_overlays(root / "Native", root / "HD", pack_roots={"colosseum": pack})
            self.assertEqual(captured["resources"][0]["role"], "castform_portrait")
            self.assertTrue(prepared["hd_ready"])
            self.assertEqual((root / "HD" / key).read_bytes(), payloads["castform-shinies/square-face.png"])

    def test_xd_model_container_and_regional_contract_have_the_same_exact_native_x4_binding(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            original = model_fixture(False)[0]
            length = hd.u32(original, 0)
            dat = original[0x40:0x40 + length]
            header = bytearray(0xE60)
            struct.pack_into(">I", header, 0, length)
            raw = bytes(header) + dat + bytes(-length % 32)
            key = bind_model(bundle, catalogue, payloads, save, raw, xd=True)
            source = root / "fixture.iso"
            disc(source, [("pkx_powalen_i.fsys", archive([(0x7DA31E00, "custom_snow", raw)]))], xd=True)
            captured = capture(source, root / "Native", xd=True)
            self.assertEqual(captured["castform_shinies"]["game_id"], "GXXP01")
            self.assertEqual(captured["assets"][0]["hd"]["transform"]["game_id"], "GXXP01")
            prepared = hd.prepare_hd_overlays(root / "Native", root / "HD", pack_roots={"colosseum": pack})
            self.assertTrue(prepared["hd_ready"])
            self.assertEqual((root / "HD" / key).read_bytes(), payloads["castform-shinies/model-map.png"])

    def test_unregistered_custom_key_and_wrong_registered_rgba_cannot_fall_back_to_stock(self):
        for failure in ("unknown_key", "wrong_rgba"):
            with self.subTest(failure=failure), artwork() as (root, bundle, pack, catalogue, payloads, save):
                raw = model_fixture(False)[0]
                if failure == "wrong_rgba":
                    bind_model(bundle, catalogue, payloads, save, raw)
                    catalogue["files"][0]["native_rgba_sha256"] = "e" * 64
                    save()
                source = root / "fixture.iso"
                disc(source, [("pkx_powalen_f.fsys", archive([(0x7DA21E00, "custom_sun", raw)]))])
                captured = capture(source, root / "Native")
                self.assertIsNone(captured["assets"][0]["hd"])
                with patch.object(hd, "_resolve_hd", side_effect=AssertionError("No guessing for custom weather")):
                    prepared = hd.prepare_hd_overlays(root / "Native", root / "HD", pack_roots={"colosseum": pack})
                self.assertFalse(prepared["hd_ready"])
                self.assertTrue(prepared["missing_assets"])

    def test_removing_a_catalogue_blocks_custom_resources_but_not_an_old_unmodified_weather_archive(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            (bundle / art.CATALOGUE).unlink()
            raw = model_fixture(False)[0]
            for custom in (True, False):
                source = root / f"fixture-{custom}.iso"
                disc(source, [("pkx_powalen_f.fsys", archive([(0x7DA21E00 if custom else 0x01231E00, "sun", raw)]))])
                directory = root / f"Native-{custom}"
                captured = capture(source, directory)
                prepared = hd.prepare_hd_overlays(directory, root / f"HD-{custom}", pack_roots={"colosseum": pack})
                self.assertEqual(prepared["hd_ready"], not custom)
                self.assertEqual(bool(captured.get("castform_shinies")), custom)

    def test_replacing_a_captured_native_png_and_updating_its_file_hash_still_fails_rgba_binding(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            raw = model_fixture(False)[0]
            bind_model(bundle, catalogue, payloads, save, raw)
            source = root / "fixture.iso"
            disc(source, [("pkx_powalen_f.fsys", archive([(0x7DA21E00, "sun", raw)]))])
            captured = capture(source, root / "Native")
            reference = captured["assets"][0]["native"]
            image = QImage(32, 32, QImage.Format.Format_RGBA8888)
            image.fill(0xFF203040)
            png = hd._png((32, 32), bytes(image.constBits()))
            digest = hashlib.sha256(png).hexdigest()
            path = root / "Native/NativeReferences" / (digest + ".png")
            path.write_bytes(png)
            reference.update(file="NativeReferences/" + path.name, sha256=digest)
            (root / "Native/orre-overlays-v2.json").write_text(json.dumps(captured))
            prepared = hd.prepare_hd_overlays(root / "Native", root / "HD", pack_roots={"colosseum": pack})
            self.assertFalse(prepared["hd_ready"])
            self.assertTrue(any("native pixels" in row["reason"] for row in prepared["missing_assets"]))

    def test_real_stock_material_registry_is_an_exact_additional_route_not_a_filtered_native_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = next(iter(material_recipes("GC6P01").values()))
            size = row["native_dimensions"]
            image = QImage(*size, QImage.Format.Format_RGBA8888)
            image.fill(0xFF102030)
            native = root / "Native"
            native.mkdir()
            reference = hd._native_reference(native, bytes(image.constBits()), *size)
            asset = {"file": row["file"], "base_key": row["file"], "native": reference,
                     "native_format": 14, "role": "castform_battle", "castform_roles": ["castform_battle"]}
            with patch.object(art, "castform_shiny_recipes", return_value={"active": True}), \
                    patch.object(art, "castform_shiny_origin", return_value=None):
                origin, gap = hd._castform_hd_origin("GC6P01", asset, bytes(image.constBits()))
                self.assertIsNone(gap)
                asset["hd"] = origin
                report = {"version": hd.VERSION, "schema": 2, "contract": "native-game-and-pack-derived-hd-v2",
                    "assets": [asset], "castform_shinies": {"game_id": "GC6P01"}}
                (native / "orre-overlays-v2.json").write_text(json.dumps(report))
                pack = root / "Pack"
                pack.mkdir()
                pinned = PACKS["colosseum"]
                (pack / "installed.json").write_text(json.dumps({"key": pinned.key, "archives": [p.sha256 for p in pinned.parts]}))
                with patch.object(hd, "_resolve_hd", side_effect=AssertionError("No stock-key guessing")):
                    prepared = hd.prepare_hd_overlays(native, root / "HD", pack_roots={"colosseum": pack})
            self.assertTrue(prepared["hd_ready"])
            output = root / "HD" / row["file"]
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), row["sha256"])
            self.assertEqual(prepared["files"][0]["hd_source"]["kind"], "reviewed-stock-castform-material")


if __name__ == "__main__":
    unittest.main()
