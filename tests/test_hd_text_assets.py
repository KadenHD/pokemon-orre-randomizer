from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.hd_text import Glyph, build_native_pages
from orre_randomizer.hd_text_runtime import BRIDGE_CONTRACT
from orre_randomizer.hd_text_vectors import native_padding
from orre_randomizer.hd_text_assets import (MANIFEST, capture_text_assets, prepare_text_overlays,
                                           native_text_contract, text_recipe)


class TextAssetLifecycle(unittest.TestCase):
    def test_legacy_corpus_guides_remain_readable_without_claiming_new_native_coverage(self):
        dol, plan = self.fixture()
        with TemporaryDirectory() as directory:
            native = Path(directory) / "Textures"
            capture_text_assets(dol, plan, native)
            path = native / MANIFEST
            old = json.loads(path.read_text())
            old["native_contract"]["native_corpus_policy"] = "regional-native-message-alphabet-v1"
            old["recipe"]["native_corpus_policy"] = "regional-native-message-alphabet-v1"
            path.write_text(json.dumps(old))
            before = path.read_bytes()
            output = native / "HD/legacy-corpus"
            report = prepare_text_overlays(native, output)
            self.assertTrue(report["legacy_native_coverage"])
            self.assertFalse(report["source_iso_needed"])
            self.assertEqual(report["native_contract"], old["native_contract"])
            provenance = json.loads((output / "TextSources/native-guides.json").read_text())
            self.assertEqual(provenance["native_contract"], old["native_contract"])
            self.assertEqual(path.read_bytes(), before)
            old["native_contract"]["native_corpus_policy"] = "unverified-corpus"
            path.write_text(json.dumps(old))
            with self.assertRaises(FormatError):
                prepare_text_overlays(native, native / "HD/unverified-corpus")

    def test_rasterizer_versions_change_only_the_artistic_recipe(self):
        native=native_text_contract()
        art=text_recipe()
        changed=dict(art['vector']['rasterizer'],freetype='different-renderer')
        with patch.dict('orre_randomizer.hd_text_assets.SOURCE',{'rasterizer':changed}):
            self.assertEqual(native_text_contract(),native)
            self.assertNotEqual(text_recipe(),art)

    def test_packaged_font_manifest_matches_native_and_artistic_contracts(self):
        fonts = Path(__file__).resolve().parents[1] / "orre_randomizer/assets/game/fonts"
        manifest = json.loads((fonts / "manifest.json").read_text())
        for field, value in text_recipe().items():
            self.assertEqual(manifest[field], value, field)
        for relative, record in manifest["files"].items():
            data = (fonts.parent / relative).read_bytes()
            self.assertEqual(len(data), record["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])

    def fixture(self):
        glyphs=[Glyph(0, 65, 3, 3, 0, b"\xFF\xF0" * 3, "math", 0)]
        margins,_=native_padding(glyphs)
        pages, plan = build_native_pages(glyphs,padding_by_identity=margins)
        plan.update(bridge_contract=BRIDGE_CONTRACT, game_id="GC6P01", runtime_installed=True)
        plan["page_records"] = [{"index": 0, "file_offset": 32, "address": 0x81000020,
                                 "bytes": len(pages[0]), "sha256": hashlib.sha256(pages[0]).hexdigest()}]
        return bytes(32) + pages[0], plan

    def test_capture_and_hd_prepare_work_offline_in_normal_nested_cache(self):
        dol, plan = self.fixture()
        with TemporaryDirectory() as directory:
            native = Path(directory) / "Textures"
            captured = capture_text_assets(dol, plan, native)
            destination = native / "HD/.new-cache/assets"
            report = prepare_text_overlays(native, destination)
            self.assertTrue(report["hd_ready"])
            self.assertFalse(report["source_iso_needed"])
            self.assertEqual(report["drawn_glyphs"], 1)
            self.assertEqual(len(report["files"]), 1)
            for file, sha in report["files"].items():
                self.assertRegex(file, r"^tex1_512x512_[0-9a-f]{16}_0\.png$")
                self.assertEqual(hashlib.sha256((destination / file).read_bytes()).hexdigest(), sha)
            self.assertTrue((destination / "TextSources/OFL-NotoSansJP.txt").is_file())
            self.assertFalse(captured["source_iso_needed_for_hd"])
            with self.assertRaises(FormatError):
                prepare_text_overlays(native, native / "TextPages/output")
            self.assertEqual(capture_text_assets(dol, plan, native), captured)

    def test_cancellation_and_modified_native_bytes_fail_without_new_output(self):
        dol, plan = self.fixture()
        with TemporaryDirectory() as directory:
            native = Path(directory) / "Textures"
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(InterruptedError):
                capture_text_assets(dol, plan, native, cancel=cancelled)
            self.assertFalse(native.exists())
            capture_text_assets(dol, plan, native)
            with self.assertRaises(InterruptedError):
                prepare_text_overlays(native, native / "HD/cancelled", cancel=cancelled)
            self.assertFalse((native / "HD/cancelled").exists())
            manifest = json.loads((native / MANIFEST).read_text())
            file = native / manifest["references"][0]["file"]
            file.write_bytes(file.read_bytes()[:-1] + b"\xFF")
            with self.assertRaises(FormatError):
                prepare_text_overlays(native, native / "HD/changed")
            self.assertFalse((native / "HD/changed").exists())

    def test_historical_hd_recipe_does_not_invalidate_native_guides(self):
        dol, plan = self.fixture()
        with TemporaryDirectory() as directory:
            native = Path(directory) / "Textures"
            capture_text_assets(dol, plan, native)
            path = native / MANIFEST
            manifest = json.loads(path.read_text())
            self.assertEqual(manifest["native_contract"], native_text_contract())
            self.assertNotIn("vector", native_text_contract())
            # Reproduce a version1 capture made with an older artistic recipe.
            manifest["version"] = 1
            del manifest["native_contract"]
            manifest["recipe"]["symbol_recipes_sha256"] = "0" * 64
            manifest["recipe"]["vector"]["font_sha256"] = "1" * 64
            path.write_text(json.dumps(manifest))
            before = {str(p.relative_to(native)): p.read_bytes() for p in native.rglob("*") if p.is_file()}
            output = native / "HD/current-recipe"
            result = prepare_text_overlays(native, output)
            self.assertTrue(result["hd_ready"])
            self.assertFalse(result["source_iso_needed"])
            self.assertTrue(result["historical_hd_recipe_changed"])
            self.assertEqual(json.loads((output / "TextSources/recipe.json").read_text()), text_recipe())
            provenance = json.loads((output / "TextSources/native-guides.json").read_text())
            self.assertEqual(provenance["historical_capture_recipe"], manifest["recipe"])
            for relative, data in before.items():
                self.assertEqual((native / relative).read_bytes(), data)
            # The native sub-contract and content hashes remain strict.
            manifest["recipe"]["native_glyph_draw_policy"] = "unknown-space-rule"
            path.write_text(json.dumps(manifest))
            with self.assertRaises(FormatError):
                prepare_text_overlays(native, native / "HD/bad-native")
            self.assertFalse((native / "HD/bad-native").exists())

    def test_version2_native_contract_and_plan_cannot_be_changed(self):
        dol, plan = self.fixture()
        with TemporaryDirectory() as directory:
            native = Path(directory) / "Textures"
            capture_text_assets(dol, plan, native)
            path = native / MANIFEST
            manifest = json.loads(path.read_text())
            for field in ("native_contract", "plan"):
                altered = deepcopy(manifest)
                altered[field]["bridge_contract"] = "unknown"
                path.write_text(json.dumps(altered))
                with self.assertRaises(FormatError):
                    prepare_text_overlays(native, native / f"HD/bad-{field}")
