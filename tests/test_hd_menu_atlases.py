"""Pinned donors, coherent label alpha and menu-vector contour regression."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from orre_randomizer import hd_menu_atlases as art
from orre_randomizer import hd_menu_catalog as catalog


def vectors():
    # Overlapping same-winding rectangles model the component contours used
    # in variable fonts. Odd-even filling would cut a hole through the stroke.
    glyph = {"advance": 12, "path": [["M", 0, 0], ["L", 8, 0], ["L", 8, 10],
        ["L", 0, 10], ["L", 0, 0], ["M", 4, 0], ["L", 12, 0], ["L", 12, 10],
        ["L", 4, 10], ["L", 4, 0]]}
    family = {"source": {"font": "synthetic vector fixture"}, "glyphs": {"A": glyph}}
    return {"schema": 1, "kind": "captured-vector-font-outlines",
            "families": {"latin": family, "japanese": deepcopy(family)}}


def fixture():
    image = QImage(96, 48, QImage.Format.Format_RGBA8888)
    image.fill(QColor(41, 73, 119, 0))
    painter = QPainter(image)
    painter.fillRect(8, 8, 80, 32, QColor(170, 80, 50, 240))
    painter.fillRect(28, 16, 12, 16, QColor(0, 0, 0, 255))
    painter.end()
    recipe = {"type": art.RECIPE_TYPE, "version": 1, "target": "tex1_24x12_a_9.png",
        "family": "synthetic-badge", "language": "en", "font_family": "latin",
        "native_dimensions": [24, 12], "native_guide": {"role": "metrics only"},
        "cells": [{"bounds": [2, 2, 22, 10], "donor_bounds": [8, 8, 88, 40],
                   "text_bounds": [14, 4, 20, 8], "text": "A"}]}
    return image, recipe


class RenderMenuAtlases(unittest.TestCase):
    def test_menu_fill_ramp_preserves_native_axis_and_rejects_invalid_stops(self):
        _, recipe = fixture()
        recipe.update(type="menu_atlas_vector_text", labels=[{
            "text": "A", "bounds": [2, 2, 22, 10], "stroke_native": 0,
            "fill_gradient": {"axis": [0, 2, 0, 10],
                "stops": [[0, [0, 0, 255, 255]], [1, [0, 255, 0, 255]]]}}])
        image, _ = art._render_vector_text(recipe, vectors())
        self.assertGreater(image.pixelColor(32, 12).blue(), image.pixelColor(32, 12).green())
        self.assertGreater(image.pixelColor(32, 36).green(), image.pixelColor(32, 36).blue())
        recipe["labels"][0]["fill_gradient"]["stops"].reverse()
        with self.assertRaisesRegex(ValueError, "fill stop"):
            art._render_vector_text(recipe, vectors())

    def test_bonus_registry_uses_the_final_genuine_hand_and_circular_coin(self):
        records, _, _ = catalog._catalogue()
        rows = [r for r in records.values()
                if r["transform"].get("author_source", {}).get("manifest") == "menu-atlases/bonus-menu-source.json"]
        self.assertEqual(len(rows), 3)
        source = rows[0]["transform"]["author_source"]
        packet = catalog.menu_artwork_metadata(source["manifest"], source["manifest_sha256"])
        self.assertFalse(packet["native_bitmap_upscaled_for_art"])
        components = [c for r in packet["records"] for c in r.get("components", [])]
        self.assertTrue(any("774x139_0546115a697a53ee" in c["source"]["file"] for c in components))
        self.assertTrue(any("360x322_5c9c" in c["source"]["file"] and c.get("circular_crop") for c in components))
        self.assertTrue(all(set(r["game_ids"]) == catalog.SUPPORTED for r in rows))

    def test_pal_auxiliary_new_labels_preserve_each_original_language(self):
        expected = {"fr": {"PV", "NOUVEAU"}, "de": {"KP", "NEU"},
                    "it": {"PS", "NUOVA"}, "es": {"PS", "NUEVO"}}
        rows = [r for r in catalog.menu_recipes("GXXP01").values()
                if r["transform"]["family"] == "xd-pokemon-sheet-aux"]
        self.assertEqual(len(rows), 4)
        for row in rows:
            recipe = row["transform"]
            self.assertEqual({v["text"] for v in recipe["labels"]}, expected[recipe["language"]])
            self.assertEqual(row["source_native_dimensions"], [318, 117])
            self.assertEqual(recipe["author_source"]["donor_sha256"],
                             "0fb211102b8a0a44e7db47a99c6f4f3d0bbc2aa98a3a49ac28b6227b280dc970")

    def test_registered_image_preserves_pixels_and_rejects_unregistered_native_art(self):
        image, _ = fixture()
        recipe = {"type": "menu_atlas_registered_image", "version": 1,
            "target": "tex1_24x12_a_9.png", "family": "analytic-card",
            "native_dimensions": [24, 12], "native_guide": {"role": "measured geometry"},
            "author_source": {"native_bitmap_resampled": False}}
        expected = {"file": None, "bundled_donor": "menu-atlases/card.png",
            "source_sha256": "pinned", "source_native_dimensions": [24, 12], "transform": recipe}
        source = {"kind": "registered-authored-menu-artwork", "sha256": "pinned", "source_scale": 4}
        with patch.object(catalog, "menu_recipes", return_value={recipe["target"]: expected}):
            output, report = art.render_menu_atlas(image, recipe, source_metadata=source)
            self.assertEqual(art._pixel_bytes(output), art._pixel_bytes(image))
            self.assertEqual(report["kind"], "registered-authored-menu-image")
            self.assertFalse(report["native_raster_used_for_HD_art"])
            self.assertFalse(report["runtime_validated"])
            with self.assertRaisesRegex(ValueError, "registered"):
                art.render_menu_atlas(image, recipe, source_metadata=dict(source, kind="native-upscale"))
            recipe["author_source"]["native_bitmap_resampled"] = True
            with self.assertRaisesRegex(ValueError, "genuinely authored"):
                art.render_menu_atlas(image, recipe, source_metadata=source)

    def test_registered_capture_requires_its_manifest_image_binding(self):
        image, _ = fixture()
        recipe = {"type": "menu_atlas_registered_image", "version": 1, "family": "capture",
            "target": "tex1_24x12_a_9.png", "native_dimensions": [24, 12], "native_guide": {},
            "author_source": {"native_bitmap_resampled": False, "manifest": "menu-atlases/capture.json",
                "manifest_sha256": "receipt", "artwork_file": "capture.png"}}
        expected = {"file": None, "bundled_donor": "menu-atlases/capture.png", "source_sha256": "pinned",
                    "source_native_dimensions": [24, 12], "transform": recipe}
        source = {"kind": "registered-authored-menu-artwork", "sha256": "pinned", "source_scale": 4}
        entry = {"sha256": "pinned", "dimensions": [96, 48]}
        with patch.object(catalog, "menu_recipes", return_value={recipe["target"]: expected}), \
                patch.object(catalog, "menu_artwork_metadata", return_value={"files": {"capture.png": entry}}):
            out, _ = art.render_menu_atlas(image, recipe, source_metadata=source)
            self.assertEqual(art._pixel_bytes(out), art._pixel_bytes(image))
            entry["sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "manifest"):
                art.render_menu_atlas(image, recipe, source_metadata=source)

    def test_upstream_name_alias_changes_only_the_missing_runtime_name(self):
        image, _ = fixture()
        recipe = {"type": "menu_atlas_upstream_name_alias", "version": 1,
            "target": "tex1_24x12_a_9.png", "native_guide": {}, "author_source": {"role": "same-key upstream PNG"}}
        expected = {"file": "tex1_24x12_a_9_nope.png", "source_sha256": "pinned",
                    "source_native_dimensions": [24, 12], "transform": recipe}
        with patch.object(catalog, "menu_recipes", return_value={recipe["target"]: expected}):
            out, report = art.render_menu_atlas(image, recipe, source_metadata={"sha256": "pinned", "source_scale": 4})
            self.assertEqual(art._pixel_bytes(out), art._pixel_bytes(image))
            self.assertEqual(report["kind"], "pinned-upstream-HD-name-alias")
            expected["file"] = "tex1_24x12_other_9_nope.png"
            with self.assertRaisesRegex(ValueError, "native texture identity"):
                art.render_menu_atlas(image, recipe, source_metadata={"sha256": "pinned", "source_scale": 4})

    def test_registered_title_footer_keeps_the_native_slice_gap_empty(self):
        for game in ("GXXP01", "GXXJ01"):
            rows = [r for r in catalog.menu_recipes(game).values()
                    if r["transform"]["family"] == "xd-title-controls"
                    and r["source_native_dimensions"] in ([316, 270], [184, 246])]
            self.assertTrue(rows)
            for row in rows:
                source = catalog.menu_image(row["bundled_donor"], tuple(row["source_native_dimensions"]))
                self.assertEqual(source.image.pixelColor(76 * 4 + 2, 220 * 4 + 2).alpha(), 0)
                self.assertNotIn('clip-path=', row["transform"]["author_source"]["vector_svg"])

    def test_reviewed_pc_bars_supersede_only_identical_legacy_native_identities(self):
        from orre_randomizer.hd_hud import hud_recipes, _CATALOG, _REFORMATS
        reviewed = catalog.menu_recipes("GXXP01")
        actual = hud_recipes("GXXP01")
        for key in _CATALOG:
            self.assertEqual(actual[key]["transform"]["family"], "xd-pc-hp")
        changed = deepcopy(reviewed)
        key = next(iter(_CATALOG))
        changed[key]["transform"]["native_guide"]["rgba_sha256"] = "wrong native identity"
        with patch.object(catalog, "menu_recipes", return_value=changed):
            with self.assertRaisesRegex(ValueError, "collide"):
                hud_recipes("GXXP01")
        unrelated = deepcopy(_REFORMATS)
        unchanged = deepcopy(unrelated)
        with patch.object(catalog, "menu_recipes", return_value=unrelated):
            with self.assertRaisesRegex(ValueError, "collide"):
                hud_recipes("GC6J01")
        self.assertEqual(unrelated, unchanged)

    def test_bingo_card_vectors_cut_each_tile_without_unsupported_svg_clipping(self):
        from scripts.build_hd_bingo_card_icons import svg_recipe
        row = next(r for r in catalog.menu_recipes("GXXP01").values()
                   if r["transform"]["family"] == "bingo-card-icons")
        payload = svg_recipe(row["transform"]["author_source"])
        self.assertNotIn(b'clip-path=', payload)
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                         row["transform"]["author_source"]["SVG_recipe_sha256"])
        source = catalog.menu_image(row["bundled_donor"], (130, 100))
        # A fully cut first tile cannot paint a purple panel behind the second
        # card's transparent left margin, even where no horizontal UV gap exists.
        for x in range(65 * 4, 71 * 4):
            self.assertEqual(source.image.pixelColor(x, 45 * 4).alpha(), 0)

    def test_variable_font_component_overlap_is_filled_not_cancelled(self):
        path = art._word_path("A", "latin", vectors())
        self.assertEqual(path.fillRule(), Qt.FillRule.WindingFill)
        image = QImage(20, 20, QImage.Format.Format_RGBA8888)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.fillPath(path, QColor("black"))
        painter.end()
        self.assertEqual(image.pixelColor(6, 5), QColor("black"))

    def test_replaced_letters_do_not_retain_the_old_alpha_or_colour(self):
        image, recipe = fixture()
        original = art._pixel_bytes(image)
        output, report = art._render_badges(image, recipe, vectors())
        self.assertEqual(output.pixelColor(32, 20), QColor(170, 80, 50, 240))
        self.assertEqual(output.pixelColor(64, 22), QColor(0, 0, 0, 255))
        self.assertEqual(art._pixel_bytes(image), original)
        self.assertEqual(output.pixelColor(0, 0), image.pixelColor(0, 0))
        self.assertFalse(report["native_raster_used_for_HD_art"])
        self.assertFalse(report["runtime_validated"])
        self.assertEqual(report["output_rgba_sha256"], hashlib.sha256(art._pixel_bytes(output)).hexdigest())

    def test_explicit_gradient_samples_erase_wide_white_donor_letters(self):
        image, recipe = fixture()
        painter = QPainter(image)
        painter.fillRect(14, 8, 68, 32, QColor(255, 255, 255, 255))
        painter.end()
        recipe["cells"][0]["gradient_sample_bounds"] = [[8, 8, 12, 40], [84, 8, 88, 40]]
        output, _ = art._render_badges(image, recipe, vectors())
        self.assertEqual(output.pixelColor(30, 24), QColor(170, 80, 50, 240))
        recipe["cells"][0]["gradient_sample_bounds"] = [[0, 8, 12, 40]]
        with self.assertRaisesRegex(ValueError, "gradient samples"):
            art._render_badges(image, recipe, vectors())

    def test_glossy_side_samples_cover_ink_between_different_margin_colors(self):
        image, recipe = fixture()
        painter = QPainter(image)
        painter.fillRect(8, 8, 40, 32, QColor(170, 80, 50, 255))
        painter.fillRect(48, 8, 40, 32, QColor(160, 70, 40, 255))
        painter.fillRect(14, 8, 68, 32, QColor(255, 255, 255, 255))
        painter.end()
        # Two distinct glossy margins must bracket the old glyph, although
        # only the left margin equals the modal continuation sample.
        recipe["cells"][0]["gradient_sample_bounds"] = [[8, 8, 12, 40], [84, 8, 88, 40]]
        output, _ = art._render_badges(image, recipe, vectors())
        self.assertEqual(output.pixelColor(30, 24), QColor(170, 80, 50, 255))
        self.assertEqual(output.pixelColor(0, 0), image.pixelColor(0, 0))

    def test_native_donor_dimensions_and_overlapping_slots_fail_closed(self):
        image, recipe = fixture()
        for malformed in (dict(recipe, native_dimensions=[25, 12]),
                          dict(recipe, cells=recipe["cells"] * 2)):
            with self.assertRaises(ValueError):
                art._render_badges(image, malformed, vectors())
        invalid = deepcopy(recipe)
        invalid["cells"][0]["donor_bounds"] = [-1, 8, 88, 40]
        with self.assertRaises(ValueError):
            art._render_badges(image, invalid, vectors())

    def test_native_language_must_have_a_real_outline(self):
        image, recipe = fixture()
        recipe["cells"][0]["text"] = "missing"
        with self.assertRaisesRegex(ValueError, "outline"):
            art._render_badges(image, recipe, vectors())

    def test_native_geometry_rebuild_uses_a_registered_hd_gradient(self):
        image, recipe = fixture()
        vector = vectors()
        vector["palettes"] = {"mint": {"rows": [[20, 130, 110, 240], [20, 130, 110, 240]]}}
        recipe["cells"][0]["background"] = {
            "type": "rounded-rectangle", "radius_native": 3, "palette": "mint"}
        output, report = art._render_badges(image, recipe, vector)
        self.assertEqual(output.pixelColor(32, 20), QColor(20, 130, 110, 240))
        self.assertEqual(output.pixelColor(0, 0), image.pixelColor(0, 0))
        self.assertEqual(report["authored_backgrounds"][0]["palette"], "mint")
        del vector["palettes"]
        with self.assertRaisesRegex(ValueError, "palette"):
            art._render_badges(image, recipe, vector)

    def test_white_japanese_capsule_style_has_a_dark_outline_without_changing_the_default(self):
        image, recipe = fixture()
        original, _ = art._render_badges(image, recipe, vectors())
        recipe["cells"][0].update(fill="#ffffff", outline="#123456", stroke_native=.5)
        styled, _ = art._render_badges(image, recipe, vectors())
        self.assertEqual(original.pixelColor(64, 22), QColor("black"))
        self.assertEqual(styled.pixelColor(64, 22), QColor("white"))
        self.assertNotEqual(art._pixel_bytes(original), art._pixel_bytes(styled))
        self.assertEqual(styled.pixelColor(0, 0), image.pixelColor(0, 0))
        self.assertTrue(any(styled.pixelColor(x, y) == QColor("#123456")
                            for x in range(56, 80) for y in range(16, 32)))

    def test_pinned_donor_and_unchanged_recipe_are_required(self):
        image, recipe = fixture()
        expected = {"file": "donor.png", "source_sha256": "pinned", "source_native_dimensions": [24, 12], "transform": recipe}
        with patch.object(catalog, "menu_recipes", return_value={recipe["target"]: expected}), \
             patch.object(catalog, "menu_vectors", return_value=vectors()):
            output, _ = art.render_menu_atlas(image, recipe,
                source_metadata={"sha256": "pinned", "source_scale": 4})
            self.assertEqual(output.size(), image.size())
            for metadata in ({"sha256": "changed", "source_scale": 4},
                             {"sha256": "pinned", "source_scale": 1}):
                with self.assertRaises(ValueError):
                    art.render_menu_atlas(image, recipe, source_metadata=metadata)
            altered = deepcopy(recipe)
            altered["cells"][0]["text"] = "AA"
            with self.assertRaises(ValueError):
                art.render_menu_atlas(image, altered,
                    source_metadata={"sha256": "pinned", "source_scale": 4})

    def test_pure_vector_text_keeps_its_native_rectangle_and_transparent_canvas(self):
        _, recipe = fixture()
        recipe.update(type="menu_atlas_vector_text", labels=[{
            "text": "A", "bounds": [2, 2, 22, 10], "stroke_native": 1., "fill": "#ffffff"}])
        output, report = art._render_vector_text(recipe, vectors())
        self.assertEqual((output.width(), output.height()), (96, 48))
        self.assertEqual(output.pixelColor(0, 0), QColor(0, 0, 0, 0))
        self.assertEqual(output.pixelColor(48, 24), QColor("white"))
        self.assertFalse(report["native_raster_used_for_HD_art"])
        for y in range(output.height()):
            for x in range(output.width()):
                if output.pixelColor(x, y).alpha():
                    self.assertTrue(8 <= x < 88 and 8 <= y < 40)
        recipe["labels"][0]["bounds"] = [-1, 2, 22, 10]
        with self.assertRaises(ValueError):
            art._render_vector_text(recipe, vectors())

    def test_layered_title_outlines_keep_grey_core_dark_ring_and_light_outer_ring(self):
        _, recipe = fixture()
        recipe.update(type="menu_atlas_vector_text", labels=[{
            "text": "A", "bounds": [2, 2, 22, 10], "stroke_native": 1.5, "fill": "#999999",
            "outline_layers": [{"width_native": 1.5, "color": "#ffffff"},
                               {"width_native": .7, "color": "#000000"}]}])
        image, _ = art._render_vector_text(recipe, vectors())
        colors = {image.pixelColor(x, y).name() for y in range(image.height())
                  for x in range(image.width()) if image.pixelColor(x, y).alpha() == 255}
        self.assertTrue({"#999999", "#000000", "#ffffff"} <= colors)
        for layers in ([{"width_native": 2, "color": "#fff"}],
                       [{"width_native": 1, "color": "#fff"}, {"width_native": 1.2, "color": "#000"}],
                       [{"width_native": 1, "color": "not-a-color"}]):
            recipe["labels"][0]["outline_layers"] = layers
            with self.assertRaises(ValueError):
                art._render_vector_text(recipe, vectors())

    def test_analytic_geometry_has_a_real_hole_and_needs_no_image_donor(self):
        recipe = {"type": "menu_atlas_vector_geometry", "version": 1,
            "target": "tex1_20x20_a_5.png", "family": "synthetic-ring",
            "native_dimensions": [20, 20], "native_guide": {"role": "geometry measurements"},
            "layers": [{"color": [99, 255, 189, 255], "operations": [
                {"shape": "ellipse", "bounds": [1, 1, 19, 19]},
                {"shape": "ellipse", "bounds": [5, 5, 15, 15], "operation": "subtract"}]}]}
        expected = {"file": None, "transform": recipe}
        with patch.object(catalog, "menu_recipes", return_value={recipe["target"]: expected}):
            output, report = art.render_menu_atlas(QImage(), recipe,
                source_metadata={"kind": "authored-vector-artwork"})
            self.assertEqual((output.width(), output.height()), (80, 80))
            self.assertEqual(output.pixelColor(40, 40).alpha(), 0)
            self.assertEqual(output.pixelColor(40, 8), QColor(99, 255, 189, 255))
            self.assertTrue(any(0 < output.pixelColor(x, y).alpha() < 255
                                for x in range(80) for y in range(8)))
            self.assertFalse(report["native_raster_resampled_for_HD_art"])
            with self.assertRaisesRegex(ValueError, "Unexpected image donor"):
                art.render_menu_atlas(output, recipe, source_metadata={"kind": "authored-vector-artwork"})
        for invalid in ([float("nan"), 1, 19, 19], [-1, 1, 19, 19], [1, 1, 21, 19]):
            altered = deepcopy(recipe)
            altered["layers"][0]["operations"][0]["bounds"] = invalid
            with self.assertRaises(ValueError):
                art._render_vector_geometry(altered)

    def test_source_vector_panel_gradient_counter_and_caption_keep_native_side(self):
        recipe = {"type": "menu_atlas_authored_panel", "version": 1,
            "family": "synthetic-panel", "language": "ja", "font_family": "latin",
            "native_dimensions": [24, 12], "native_guide": {"role": "original layout"},
            "author_source": {"sha256": "real-vector-source"},
            "layers": [{"color": [120, 120, 120, 255], "operations": [{"shape": "rounded-rectangle",
                "bounds": [1, 1, 23, 11], "radius": 3}], "gradient": {
                "axis": [0, 1, 0, 11], "stops": [[0, [150, 150, 150, 255]], [1, [90, 90, 90, 255]]]}},
                {"color": [0, 0, 0, 255], "operations": [{"shape": "rounded-rectangle",
                 "bounds": [2, 3, 7, 9], "radius": 1}]}],
            "labels": [{"text": "A", "bounds": [9, 3, 20, 9], "stroke_native": .5}]}
        output, receipt = art._render_authored_panel(recipe, vectors())
        self.assertGreater(output.pixelColor(88, 12).red(), output.pixelColor(88, 36).red())
        self.assertEqual(output.pixelColor(16, 24), QColor("black"))
        self.assertEqual(output.pixelColor(58, 24), QColor("white"))
        self.assertEqual(receipt["author_source"]["sha256"], "real-vector-source")
        recipe["layers"][0]["gradient"]["stops"][0][0] = float("nan")
        with self.assertRaises(ValueError):
            art._render_authored_panel(recipe, vectors())

    def test_real_scene_composition_keeps_exact_uv_size_and_checks_capture_sha(self):
        image = QImage(8, 12, QImage.Format.Format_RGBA8888)
        image.fill(QColor("purple"))
        source = SimpleNamespace(image=image, metadata={"sha256": "approved"})
        proof = {"files": {"original.png": {"sha256": "approved", "dimensions": [8, 12]}}}
        recipe = {"family": "synthetic-scene", "native_dimensions": [24, 12], "native_guide": {"role": "original UV window"},
            "layers": [{"color": [20, 30, 40, 255], "operations": [
                {"shape": "rectangle", "bounds": [0, 0, 24, 12]}]}],
            "provenance_file": "menu-atlases/synthetic.json", "provenance_sha256": "proof",
            "images": [{"file": "menu-atlases/scene.png", "native_dimensions": [2, 3],
                "bounds": [2, 2, 4, 5], "manifest_file": "original.png", "sha256": "approved"}]}
        with patch.object(catalog, "menu_artwork_metadata", return_value=proof), \
             patch.object(catalog, "menu_image", return_value=source):
            output, receipt = art._render_registered_composition(recipe, vectors())
            self.assertEqual(output.pixelColor(9, 9), QColor("purple"))
            self.assertEqual(output.pixelColor(17, 9), QColor(20, 30, 40))
            self.assertEqual(receipt["images"][0]["native_window"], [2, 2, 4, 5])
            altered = deepcopy(recipe)
            altered["images"][0]["bounds"][2] = 5
            with self.assertRaisesRegex(ValueError, "original UV window"):
                art._render_registered_composition(altered, vectors())
            source.metadata["sha256"] = "unreviewed"
            with self.assertRaisesRegex(ValueError, "approved capture"):
                art._render_registered_composition(recipe, vectors())

    def test_analytic_geometry_preparation_does_not_require_a_fake_pack(self):
        from orre_randomizer import hd_hud
        recipe = {"game": "colosseum", "file": None,
            "transform": {"type": "menu_atlas_vector_geometry"}}
        image = QImage(8, 8, QImage.Format.Format_RGBA8888)
        image.fill(QColor("green"))
        with TemporaryDirectory() as temporary, \
             patch.object(hd_hud, "hud_recipes", return_value={"tex1_2x2_a_5.png": recipe}), \
             patch.object(hd_hud, "render_hud", return_value=(image, {"kind": "authored"})) as render:
            report = hd_hud.prepare_hud_overlays("GC6P01", {}, Path(temporary))
            self.assertEqual(report["required_packs"], [])
            self.assertTrue((Path(temporary) / "tex1_2x2_a_5.png").is_file())
            self.assertTrue(render.call_args.args[0].isNull())

    def test_real_reviewed_pda_recipes_prepare_for_eu_and_japan_without_a_donor(self):
        from orre_randomizer import hd_hud
        for game_id, key in (("GC6P01", "tex1_74x74_d153167baed12b1f_5.png"),
                             ("GC6J01", "tex1_74x74_e16115b2d00078a9_6.png")):
            recipe = catalog.menu_recipes(game_id)[key]
            with TemporaryDirectory() as temporary, \
                 patch.object(hd_hud, "hud_recipes", return_value={key: recipe}):
                report = hd_hud.prepare_hud_overlays(game_id, {}, Path(temporary))
                output = QImage(str(Path(temporary) / key))
                self.assertEqual((output.width(), output.height()), (296, 296))
                self.assertEqual(report["required_packs"], [])
                self.assertEqual(report["files"][key], hashlib.sha256((Path(temporary) / key).read_bytes()).hexdigest())
                for kind in ("authored-vector-artwork", "authored-vector-geometry"):
                    actual, _ = art.render_menu_atlas(QImage(), recipe["transform"], source_metadata={"kind": kind})
                    self.assertEqual(art._pixel_bytes(actual), art._pixel_bytes(output))

    def test_localized_caption_keeps_every_pixel_outside_its_clear_rectangle(self):
        image, recipe = fixture()
        recipe.update(type="menu_atlas_hd_patch_labels", clear_rects=[[2, 2, 22, 10]],
            labels=[{"text": "A", "bounds": [3, 3, 20, 9], "stroke_native": .5,
                     "fill": "#ffffff", "outline": "#9f3c56"}])
        before = art._pixel_bytes(image)
        output, report = art._render_pack_labels(image, recipe, vectors())
        after = art._pixel_bytes(output)
        self.assertEqual(art._pixel_bytes(image), before)
        for y in range(48):
            for x in range(96):
                if not (8 <= x < 88 and 8 <= y < 40):
                    at = (y * 96 + x) * 4
                    self.assertEqual(after[at:at + 4], before[at:at + 4])
        self.assertEqual(output.pixelColor(10, 10).alpha(), 0)
        self.assertEqual(report["kind"], "pack-derived-menu-caption-localization")
        recipe["labels"][0]["bounds"][0] = 1
        with self.assertRaisesRegex(ValueError, "leaves its replacement"):
            art._render_pack_labels(image, recipe, vectors())


class MenuCatalogue(unittest.TestCase):
    def setUp(self):
        catalog._catalogue.cache_clear()
        catalog._vectors.cache_clear()

    def tearDown(self):
        self.setUp()

    def test_review_gate_and_region_and_native_dimensions(self):
        _, transform = fixture()
        row = {"target": transform["target"], "game_ids": ["GXXP01"], "game": "xd",
               "transform": dict(transform, vectors_sha256="vectors")}
        data = {"schema": 1, "contract": catalog.CONTRACT, "review_only": False,
                "vectors_sha256": "vectors", "records": [row]}
        with patch.object(catalog, "_asset", return_value=(data, "catalogue")):
            self.assertEqual(set(catalog.menu_recipes("GXXP01")), {row["target"]})
            self.assertEqual(catalog.menu_recipes("GC6P01"), {})
            with self.assertRaises(ValueError):
                catalog.menu_origin("GXXP01", row["target"], (23, 12))
            first = catalog.menu_recipes("GXXP01")
            first[row["target"]]["transform"]["cells"].clear()
            self.assertEqual(len(catalog.menu_recipes("GXXP01")[row["target"]]["transform"]["cells"]), 1)
        catalog._catalogue.cache_clear()
        data["review_only"] = True
        with patch.object(catalog, "_asset", return_value=(data, "catalogue")):
            with self.assertRaisesRegex(ValueError, "reviewed"):
                catalog.menu_recipes("GXXP01")

    def test_registered_asset_digest_is_checked_before_parsing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "menu-atlases").mkdir()
            payload = b'{"schema":1}'
            (root / catalog.CATALOGUE).write_bytes(payload)
            provenance = {"files": {catalog.CATALOGUE: {"bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest()}}}
            (root / "provenance.json").write_text(json.dumps(provenance))
            with patch("orre_randomizer.resources.bundle_root", return_value=root):
                self.assertEqual(catalog._asset(catalog.CATALOGUE)[0], {"schema": 1})
                (root / catalog.CATALOGUE).write_bytes(b'{"schema":2}')
                with self.assertRaisesRegex(ValueError, "registered artwork"):
                    catalog._asset(catalog.CATALOGUE)

    def test_registered_vector_background_checks_sha_and_png_dimensions_before_decode(self):
        image = QImage(8, 12, QImage.Format.Format_RGBA8888)
        image.fill(QColor(30, 90, 150, 255))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.assertTrue(image.save(buffer, "PNG"))
        payload = bytes(buffer.data())
        logical = "menu-atlases/synthetic-background.png"
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "menu-atlases").mkdir()
            (root / logical).write_bytes(payload)
            (root / "provenance.json").write_text(json.dumps({"files": {logical: {
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}}}))
            with patch("orre_randomizer.resources.bundle_root", return_value=root):
                source = catalog.menu_image(logical, (2, 3))
                self.assertEqual(art._pixel_bytes(source.image), art._pixel_bytes(image))
                self.assertEqual(source.metadata["source_scale"], 4)
                self.assertEqual(source.metadata["physical_file"], logical)
                for wrong in ((3, 2), (200000, 3)):
                    with self.assertRaises(ValueError):
                        catalog.menu_image(logical, wrong)
                (root / logical).write_bytes(payload[:-1] + b"X")
                with self.assertRaisesRegex(ValueError, "registered artwork"):
                    catalog.menu_image(logical, (2, 3))
        with self.assertRaisesRegex(ValueError, "Unknown"):
            catalog.menu_image("../outside.png", (2, 3))

    def test_registered_release_badges_are_region_exact_and_use_real_outlines(self):
        records, vector_digest, _ = catalog._catalogue()
        families = {"type-big", "type-small", "status-big", "status-small"}
        badges = {key: row for key, row in records.items()
                  if row["transform"]["type"] == art.RECIPE_TYPE and row["transform"]["family"] in families}
        self.assertEqual(len(badges), 23)
        self.assertEqual({r["transform"]["language"] for r in badges.values()},
                         {"en", "fr", "de", "it", "es", "ja"})
        self.assertEqual({r["transform"]["family"] for r in badges.values()},
                         {"type-big", "type-small", "status-big", "status-small"})
        data = catalog.menu_vectors()
        for key, row in records.items():
            self.assertEqual(row["transform"]["vectors_sha256"], vector_digest)
            if key in badges:
                self.assertEqual(row["game"], "xd")
            for game_id in catalog.SUPPORTED:
                self.assertEqual(key in catalog.menu_recipes(game_id), game_id in row["game_ids"])
            for cell in row["transform"].get("cells", row["transform"].get("labels", [])):
                if cell.get("replace", True):
                    self.assertFalse(art._word_path(cell["text"], cell.get("font_family", row["transform"]["font_family"]), data).isEmpty())
        data["families"]["latin"]["glyphs"].clear()
        self.assertTrue(catalog.menu_vectors()["families"]["latin"]["glyphs"])

    def test_cb_compositions_bind_approved_outputs_and_honest_material_coverage(self):
        data, _ = catalog._asset("menu-atlases/cb-composition-source.json")
        self.assertFalse(data["review_only"])
        self.assertEqual(len(data["files"]), 16)
        recipe = data["pal_recipe"]
        self.assertTrue(recipe["art_approval"])
        self.assertEqual(recipe["lower_portrait_fade"]["native_rows"], 14)
        self.assertTrue(recipe["lower_portrait_fade"]["applied_once"])
        self.assertEqual(len(recipe["approved_outputs"]), 10)
        for name, source in data["binary_inputs"].items():
            payload, digest = catalog._asset_bytes(source["asset"])
            self.assertEqual(digest, source["sha256"], name)
        records = catalog._catalogue()[0]
        bound = [row for row in records.values()
                 if row["transform"].get("author_source", {}).get("manifest")
                 == "menu-atlases/cb-composition-source.json"]
        self.assertEqual(len(bound), 16)
        for row in bound:
            origin = row["transform"]["author_source"]
            self.assertEqual(origin["material_coverage"], {"exact_HD_Wes": 4, "native_retained_GBA": 14})
            self.assertFalse(origin["runtime_validated"])
            metadata = catalog.menu_artwork_metadata(origin["manifest"], origin["manifest_sha256"])
            self.assertEqual(metadata["files"][origin["artwork_file"]]["sha256"], row["source_sha256"])

    def test_xd_connection_console_visible_pixels_fit_the_native_uv_cells(self):
        data, _ = catalog._asset("menu-atlases/xd-link-trade-source.json")
        checked = 0
        records = catalog._catalogue()[0]
        for recipe in data["records"]:
            parts = [part for part in recipe["components"] if "visible_body_fit" in part]
            if not parts:
                continue
            self.assertEqual(len(parts), 1)
            fit = parts[0]["visible_body_fit"]
            target = [v * 4 for v in fit["native_body_bounds"]]
            native_size = tuple(recipe["native_dimensions"])
            row = records[recipe["target"]]
            image = catalog.menu_image(row["bundled_donor"], native_size).image
            pixels = art._pixel_bytes(image)
            # These isolated native regions contain only the console; the
            # Japanese cable and adjacent glyph cells have different UVs.
            region = (140, 82, 242, 213) if native_size == (295, 213) else (164, 80, 272, 240)
            coordinates = [(x, y) for y in range(region[1] * 4, region[3] * 4)
                           for x in range(region[0] * 4, region[2] * 4)
                           if pixels[(y * image.width() + x) * 4 + 3] >= 128]
            self.assertTrue(coordinates)
            self.assertGreaterEqual(min(x for x, _ in coordinates), target[0])
            self.assertGreaterEqual(min(y for _, y in coordinates), target[1])
            self.assertLessEqual(max(x for x, _ in coordinates) + 1, target[2])
            self.assertLessEqual(max(y for _, y in coordinates) + 1, target[3])
            crop, destination = parts[0]["crop"], parts[0]["destination"]
            self.assertAlmostEqual((crop[2] - crop[0]) / (crop[3] - crop[1]),
                                   (destination[2] - destination[0]) / (destination[3] - destination[1]))
            checked += 1
        self.assertEqual(checked, 5)


if __name__ == "__main__":
    unittest.main()
