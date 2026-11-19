"""Stock form paint keeps the exact reviewed portraits' materials and native keys."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from orre_randomizer import hd_form_materials as art
from orre_randomizer.hd_menu_catalog import _asset_bytes
from orre_randomizer.hd_packs import PACKS


def packs(root):
    result = {}
    for game, pack in PACKS.items():
        path = root / game
        path.mkdir()
        (path / "installed.json").write_text(json.dumps({"key": pack.key,
            "archives": [p.sha256 for p in pack.parts]}))
        result[game] = path
    return result


class StockFormMaterials(unittest.TestCase):
    def test_packaged_diagnostic_checks_every_form_and_region_without_external_inputs(self):
        from orre_randomizer.diagnostics import check_form_materials
        report = check_form_materials()
        self.assertEqual(report["checked_images"], 43)
        self.assertFalse(report["rom_opened"])
        self.assertFalse(report["external_packs_opened"])
        self.assertEqual(report["regional_counts"]["GC6J01"], 15)
        self.assertEqual(report["regional_counts"]["GXXJ01"], 43)

    def test_regions_use_observed_keys_and_pinned_portrait_materials(self):
        for game_id in art.SUPPORTED:
            rows = art.material_recipes(game_id)
            self.assertEqual(len(rows), 15 if game_id.startswith("GC6") else 43)
            self.assertTrue(all(game_id in row["game_ids"] for row in rows.values()))
            for row in rows.values():
                self.assertFalse(row["native_bitmap_resampled"])
                self.assertEqual(row["dimensions"], [v * 4 for v in row["native_dimensions"]])
        with self.assertRaises(ValueError):
            art.material_recipes("GXXK01")

    def test_preparation_publishes_exact_reviewed_pixels_without_touching_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = packs(root)
            before = {game: (path / "installed.json").read_bytes() for game, path in sources.items()}
            output = root / "HD"
            report = art.prepare_form_materials("GXXP01", sources, output)
            self.assertEqual(len(report["files"]), 43)
            for name, row in art.material_recipes("GXXP01").items():
                payload, _ = _asset_bytes("form-materials/" + name)
                self.assertEqual((output / name).read_bytes(), payload)
                with Image.open(output / name) as image:
                    self.assertEqual(image.size, tuple(row["dimensions"]))
            self.assertEqual(before, {g: (p / "installed.json").read_bytes() for g, p in sources.items()})
            self.assertFalse(report["native_rom_changed"])
            self.assertEqual(art.prepare_form_materials("GXXP01", sources, output)["files"], report["files"])

    def test_changed_art_or_conflicting_destination_fails_before_publication(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = packs(root)
            with patch.object(art, "_asset_bytes", return_value=(b"altered", "0" * 64)):
                with self.assertRaises(ValueError):
                    art.prepare_form_materials("GC6P01", sources, root / "HD")
            self.assertFalse((root / "HD").exists())
            output = root / "HD"
            output.mkdir()
            name = next(iter(art.material_recipes("GC6P01")))
            (output / name).write_bytes(b"keep existing")
            with self.assertRaises(ValueError):
                art.prepare_form_materials("GC6P01", sources, output)
            self.assertEqual(list(output.iterdir()), [output / name])
            self.assertEqual((output / name).read_bytes(), b"keep existing")

    def test_missing_wrong_pack_and_output_inside_pack_are_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = packs(root)
            with self.assertRaises(ValueError):
                art.prepare_form_materials("GC6P01", {}, root / "HD")
            with self.assertRaises(ValueError):
                art.prepare_form_materials("GC6P01", sources, sources["colosseum"] / "HD")
            (sources["colosseum"] / "installed.json").write_text('{}')
            with self.assertRaises(ValueError):
                art.prepare_form_materials("GC6P01", sources, root / "HD")
            self.assertFalse((root / "HD").exists())


if __name__ == "__main__":
    unittest.main()
