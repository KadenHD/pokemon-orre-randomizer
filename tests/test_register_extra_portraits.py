"""The reviewed set publishes atomically and preserves unrelated interface assets."""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.register_extra_portraits import register
from tests.test_hd_extra_portraits import registered_catalog


@contextmanager
def linked_material_assets():
    """Use the real authenticated 43-paint catalogue, without touching it."""
    assets = Path(__file__).resolve().parents[1] / "orre_randomizer/assets/game"
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        source, destination = root / "source", root / "game"
        shutil.copytree(assets / "models/extra-portraits", source)
        destination.mkdir()
        shutil.copytree(assets / "form-materials", destination / "form-materials")
        shutil.copyfile(assets / "provenance.json", destination / "provenance.json")
        # A framing receipt changes the registry digest, while its model paint
        # and the normal/shiny atlas pixels remain exactly the real inputs.
        manifest = source / "extra-portraits.json"
        metadata = json.loads(manifest.read_text("utf8"))
        metadata["framing_review"] = "Same reviewed material paints; updated portrait framing receipt."
        manifest.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
        yield source, destination, metadata


class RegisterExtraPortraitTests(unittest.TestCase):
    def test_framing_only_registration_refreshes_real_material_link_and_all_regional_loaders(self):
        from orre_randomizer.hd_form_materials import material_recipes
        from orre_randomizer.hd_menu_catalog import SUPPORTED

        with linked_material_assets() as (source, destination, metadata):
            path = destination / "form-materials/catalog.json"
            previous = json.loads(path.read_bytes())
            provenance = json.loads((destination / "provenance.json").read_bytes())
            register(source, destination)
            current = json.loads(path.read_bytes())
            registry = destination / "models/extra-portraits/extra-portraits.json"
            self.assertEqual(current["portrait_registry_sha256"], hashlib.sha256(registry.read_bytes()).hexdigest())
            self.assertNotEqual(current["portrait_registry_sha256"], previous.pop("portrait_registry_sha256"))
            self.assertEqual({k: v for k, v in current.items() if k != "portrait_registry_sha256"}, previous)
            updated = json.loads((destination / "provenance.json").read_bytes())
            for name, value in provenance["files"].items():
                if not name.startswith("models/extra-portraits/") and name != "form-materials/catalog.json":
                    self.assertEqual(updated["files"][name], value)
            with patch("orre_randomizer.resources.bundle_root", return_value=destination):
                for game_id in SUPPORTED:
                    self.assertEqual(len(material_recipes(game_id)), 15 if game_id.startswith("GC6") else 43)

    def test_changed_capture_material_cannot_be_blessed_by_refreshing_the_catalogue_link(self):
        with linked_material_assets() as (source, destination, metadata):
            path = destination / "form-materials/catalog.json"
            before = path.read_bytes()
            provenance = (destination / "provenance.json").read_bytes()
            target = json.loads(before)["records"][0]["file"]
            for capture in metadata["captures"].values():
                for row in capture["material_recipes"]:
                    if row["target"] == target:
                        row["sha256"] = "f" * 64
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "stock form-material identities differ"):
                register(source, destination)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual((destination / "provenance.json").read_bytes(), provenance)
            self.assertFalse((destination / "models").exists())

    def test_corrupt_linked_catalogue_or_paint_is_rejected_even_in_check_only(self):
        for corrupted in ("catalogue", "paint"):
            with self.subTest(corrupted=corrupted), linked_material_assets() as (source, destination, metadata):
                catalogue = destination / "form-materials/catalog.json"
                if corrupted == "paint":
                    name = json.loads(catalogue.read_bytes())["records"][0]["file"]
                    path = catalogue.parent / name
                else:
                    path = catalogue
                path.write_bytes(path.read_bytes() + b"corrupted")
                before = (destination / "provenance.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "integrity check failed"):
                    register(source, destination, check_only=True)
                self.assertEqual((destination / "provenance.json").read_bytes(), before)
                self.assertFalse((destination / "models").exists())

    def test_failed_publication_rolls_back_catalogue_portraits_and_provenance_together(self):
        with linked_material_assets() as (source, destination, metadata):
            assets = Path(__file__).resolve().parents[1] / "orre_randomizer/assets/game"
            shutil.copytree(assets / "models/extra-portraits", destination / "models/extra-portraits")
            files = [destination / "provenance.json", destination / "form-materials/catalog.json",
                     *(destination / "models/extra-portraits").iterdir()]
            before = {path: path.read_bytes() for path in files}
            actual_write, failed = Path.write_bytes, False

            def fail_once(path, data):
                nonlocal failed
                if path.resolve() == (destination / "provenance.json").resolve() and not failed:
                    failed = True
                    raise OSError("simulated linked publication failure")
                return actual_write(path, data)

            with patch.object(Path, "write_bytes", fail_once):
                with self.assertRaisesRegex(OSError, "simulated linked"):
                    register(source, destination)
            self.assertTrue(failed)
            self.assertEqual({path: path.read_bytes() for path in files}, before)

    def test_check_only_validates_every_atlas_without_creating_a_destination(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            destination = Path(temporary) / "game-assets"
            register(source, destination, check_only=True)
            self.assertFalse(destination.exists())

    def test_registration_preserves_font_provenance_and_all_original_bytes(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            destination = Path(temporary)
            font = destination / "fonts/font.json"
            font.parent.mkdir()
            font.write_bytes(b"font-original")
            old = {"files": {"fonts/font.json": {"bytes": 13, "sha256": hashlib.sha256(font.read_bytes()).hexdigest()}},
                   "font_metadata": {"native_source": "verified original"}}
            (destination / "provenance.json").write_text(json.dumps(old))
            register(source, destination)
            result = json.loads((destination / "provenance.json").read_text())
            self.assertEqual(result["files"]["fonts/font.json"], old["files"]["fonts/font.json"])
            self.assertEqual(result["font_metadata"], old["font_metadata"])
            self.assertEqual(font.read_bytes(), b"font-original")
            self.assertEqual(len(result["files"]), 11)
            self.assertEqual(len(list((destination / "models/extra-portraits").iterdir())), 10)

    def test_corrupt_last_file_prevents_any_publication(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            last = next(reversed(metadata["files"].values()))["file"]
            (source / last).write_bytes(b"bad")
            destination = Path(temporary) / "game-assets"
            with self.assertRaisesRegex(ValueError, "integrity"):
                register(source, destination)
            self.assertFalse(destination.exists())

    def test_failed_publication_restores_the_global_provenance_and_existing_portrait(self):
        with registered_catalog() as (source, _, metadata), TemporaryDirectory() as temporary:
            metadata["native_bitmap_upscaled_for_hd"] = False
            (source / "extra-portraits.json").write_text(json.dumps(metadata))
            destination = Path(temporary)
            previous = b'{"files": {}, "fonts": "preserve"}'
            provenance = destination / "provenance.json"
            provenance.write_bytes(previous)
            portraits = destination / "models/extra-portraits"
            portraits.mkdir(parents=True)
            old = portraits / "extra-portraits.json"
            old.write_bytes(b"old registry")
            actual_write = Path.write_bytes
            failed = False

            def fail_once(path, data):
                nonlocal failed
                # Windows runners may expose TEMP through a DOS 8.3 alias.
                if path.resolve() == provenance.resolve() and not failed:
                    failed = True
                    raise OSError("simulated publication failure")
                return actual_write(path, data)

            with patch.object(Path, "write_bytes", fail_once):
                with self.assertRaisesRegex(OSError, "simulated"):
                    register(source, destination)
            self.assertEqual(provenance.read_bytes(), previous)
            self.assertEqual(old.read_bytes(), b"old registry")
            self.assertEqual(list(portraits.iterdir()), [old])


if __name__ == "__main__":
    unittest.main()
