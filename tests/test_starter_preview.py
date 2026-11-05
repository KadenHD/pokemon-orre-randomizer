"""Preview input integrity and isolated conversion, without distributed ROM data."""
from contextlib import ExitStack
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import call, patch

from orre_randomizer import artwork, service
from orre_randomizer.preview import preview_starters
from orre_randomizer.options import Options
from orre_randomizer.locales.species_ja import SPECIES_NAMES
from orre_randomizer.engine.regions import REGIONS
from tests.test_artwork import fsys, portrait, texture


class StarterPreviewTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        self.source = self.root / "original.iso"
        self.source.write_bytes(b"synthetic original")
        self.summary = {"special_gameplay": {"specials": [
            {"key": "umbreon", "species": 277, "national_dex": 252,
             "level": 26, "name_fr": "Arcko", "name_en": "Treecko",
             "name_de": "Geckarbor", "name_it": "Treecko", "name_es": "Treecko", "name_ja": "キモリ"},
            {"key": "espeon", "species": 196, "national_dex": 196,
             "level": 25, "name_fr": "Mentali", "name_en": "Espeon",
             "name_de": "Psiana", "name_it": "Espeon", "name_es": "Espeon", "name_ja": "エーフィ"}]}}

    def tearDown(self):
        self.folder.cleanup()

    def pipeline(self, stack):
        stack.enter_context(patch.object(service, "check_header", return_value=b"header"))
        stack.enter_context(patch.object(service, "ISO_SHA256", hashlib.sha256(self.source.read_bytes()).hexdigest()))
        stack.enter_context(patch.object(service, "check_disc_identity", return_value=REGIONS[0]))
        build = stack.enter_context(patch.object(service, "build_patches", return_value=([], self.summary)))
        stack.enter_context(patch("orre_randomizer.preview.extract_portraits", return_value={277: b"PNG277", 196: b"PNG196"}))
        return build

    def test_exact_production_result_and_internal_portrait_ids_without_output(self):
        before = self.source.read_bytes()
        with ExitStack() as stack:
            build = self.pipeline(stack)
            result = preview_starters(self.source, " seed 🌟 ", Options.recommended())
        self.assertEqual(build.call_args.args[2:4], (" seed 🌟 ", Options.recommended()))
        self.assertEqual(result["starters"][0]["national_dex"], 252)
        for language, name in (("fr", "Arcko"), ("en", "Treecko"), ("de", "Geckarbor"),
                               ("it", "Treecko"), ("es", "Treecko")):
            self.assertEqual(result["starters"][0]["name_" + language], name)
        self.assertEqual(result["starters"][0]["portrait_png"], b"PNG277")
        self.assertEqual([r["key"] for r in result["starters"]], ["umbreon", "espeon"])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_bad_seed_invalid_source_and_pre_cancel_refuse_work(self):
        for seed in ("", " ", "é" * 129):
            with self.assertRaises(service.UserError):
                preview_starters(self.source, seed, Options())
        with self.assertRaises(service.UserError):
            preview_starters(self.root / "missing.iso", "seed", Options())
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(service.Cancelled):
            preview_starters(self.source, "seed", Options(), cancel=cancel)

    def test_creation_reuses_only_the_verified_matching_preview_plan(self):
        original = self.source.read_bytes()
        options = Options.recommended()
        plans = []
        with ExitStack() as stack:
            build = self.pipeline(stack)
            stack.enter_context(patch.object(service, "ISO_SIZE", len(original)))
            stack.enter_context(patch.object(service, "render_journal", return_value=""))
            build.return_value = ([(0, b"A")], self.summary)
            preview_starters(self.source, "seed", options, on_prepared=plans.append)
            self.assertEqual(len(plans), 1)
            plan = plans[0]
            reused = self.root / "reused.iso"
            report = service.randomize(self.source, reused, "seed", options, prepared_patches=plan)
            self.assertTrue(report["preview_plan_reused"])
            self.assertTrue(report["all_output_iso_bytes_verified"])
            self.assertEqual(build.call_count, 1)
            fresh = self.root / "fresh.iso"
            report = service.randomize(self.source, fresh, "seed", options)
            self.assertFalse(report["preview_plan_reused"])
            self.assertEqual(reused.read_bytes(), fresh.read_bytes())
            self.assertEqual(build.call_count, 2)

            build.return_value = ([(0, b"B")], self.summary)
            for index, (seed, settings, candidate) in enumerate((
                ("different", options, plan),
                ("seed", replace(options, custom_shinies=True), plan),
                ("seed", options, replace(plan, iso_sha256="different ISO")),
                ("seed", options, replace(plan, source_sha256="different source")),
            )):
                with self.subTest(index=index):
                    target = self.root / f"fallback-{index}.iso"
                    report = service.randomize(self.source, target, seed, settings, prepared_patches=candidate)
                    self.assertFalse(report["preview_plan_reused"])
                    self.assertEqual(target.read_bytes(), b"B" + original[1:])
            self.assertEqual(build.call_count, 6)
        self.assertEqual(self.source.read_bytes(), original)
        with self.assertRaises(service.UserError):
            preview_starters(self.source, "seed", Options())

    def test_wrong_fingerprint_is_rejected_before_patching(self):
        with patch.object(service, "check_header"), patch.object(service, "build_patches") as build:
            with self.assertRaises(service.UserError):
                preview_starters(self.source, "seed", Options())
            build.assert_not_called()

    def test_source_changed_during_preview_is_not_returned(self):
        plans = []
        with ExitStack() as stack:
            self.pipeline(stack)
            expected = hashlib.sha256(self.source.read_bytes()).hexdigest()
            stack.enter_context(patch.object(service, "file_hash", side_effect=[expected, "changed"]))
            with self.assertRaisesRegex(service.UserError, "changé"):
                preview_starters(self.source, "seed", Options(), on_prepared=plans.append)
        self.assertEqual(plans, [])

    def test_missing_portrait_keeps_exact_species_names(self):
        with ExitStack() as stack:
            self.pipeline(stack)
            stack.enter_context(patch("orre_randomizer.preview.extract_portraits", side_effect=artwork.ArtworkError("unavailable")))
            result = preview_starters(self.source, "seed", Options())
        self.assertEqual(result["starters"][0]["name_en"], "Treecko")
        self.assertEqual(result["starters"][0]["portrait_png"], b"")

    def test_shadow_and_gift_preview_keeps_final_choices_and_batches_portraits(self):
        original = dict(national_dex=197, name_fr="Noctali", name_en="Umbreon",
                        name_de="Nachtara", name_es="Umbreon", name_it="Umbreon")
        shadow = dict(self.summary["special_gameplay"]["specials"][0],
                      species_index=277, shadow_id=21, original=original)
        self.summary["final_shadow_picks"] = [shadow]
        gift = dict(self.summary["special_gameplay"]["specials"][1],
                    key="pikachu-event", original=original)
        self.summary["special_gameplay"]["specials"].append(gift)
        with ExitStack() as stack:
            self.pipeline(stack)
            extract = stack.enter_context(patch("orre_randomizer.preview.extract_portraits", return_value={277: b"A", 196: b"B"}))
            result = preview_starters(self.source, "encounters", replace(Options(), accessible_event_gifts=False,
                custom_shinies=True, seeded_shinies=False, shiny_chance_percent=100))
        self.assertEqual([row["shadow_id"] for row in result["shadows"]], [21])
        self.assertEqual(result["shadows"][0]["name_de"], "Geckarbor")
        self.assertEqual(result["shadows"][0]["original"], original)
        self.assertEqual(result["gifts"][0]["key"], "pikachu-event")
        self.assertTrue(result["gifts"][0]["event"])
        self.assertEqual(result["gifts"][0]["portrait_png"], b"B")
        self.assertTrue(all(row["shiny"] for row in result["shadows"] + result["gifts"]))
        extract.assert_called_once_with(self.source, (277, 196), shiny=True)

    def test_event_gift_access_metadata_follows_options_without_changing_final_draw(self):
        sample = self.summary["special_gameplay"]["specials"][0]
        self.summary["special_gameplay"]["specials"].extend(
            dict(sample, key=key, level=level) for key, level in (
                ("plusle", 13), ("ho-oh", 70), ("pikachu-event", 38), ("celebi-event", 51)))
        for enabled in (False, True):
            options = replace(Options.recommended(), accessible_event_gifts=enabled,
                              event_pikachu_purifications=0, event_celebi_purifications=48,
                              event_pikachu_level=38, event_celebi_level=51)
            with ExitStack() as stack:
                self.pipeline(stack)
                result = preview_starters(self.source, "purification-gifts", options)
            rows = {row["key"]: row for row in result["gifts"]}
            for key, threshold, level in (("pikachu-event", 0, 38), ("celebi-event", 48, 51)):
                self.assertEqual(rows[key]["event"], not enabled)
                self.assertEqual(rows[key].get("purifications"), threshold if enabled else None)
                self.assertEqual(rows[key]["level"], level)
                self.assertEqual(rows[key]["species"], sample["species"])
            for key in ("plusle", "ho-oh"):
                self.assertFalse(rows[key]["event"])
                self.assertNotIn("purifications", rows[key])

    def test_several_portraits_are_decoded_in_one_archive_read(self):
        archive = fsys([(f"face{i:03}", portrait((i, 23, 37, 255), (255, 0, 0, 255))) for i in range(1, 4)])
        with patch.object(artwork, "_disc_files", return_value={"poke_face.fsys": archive}) as read:
            images = artwork.extract_portraits(self.source, (1, 2, 3))
        read.assert_called_once()
        for i in range(1, 4):
            self.assertEqual(artwork._png_pixels(images[i], (42, 42)), bytes((i, 23, 37, 255)) * 42**2)

    def test_rvz_uses_owned_temporary_iso_and_leaves_input_intact(self):
        rvz = self.root / "original.rvz"
        rvz.write_bytes(b"synthetic compressed source")
        tool = self.root / "DolphinTool.exe"
        tool.touch()
        temporary = []

        def convert(selected_tool, source, destination, work, cancel):
            self.assertEqual(selected_tool, tool)
            self.assertEqual(source, rvz)
            self.assertEqual(destination.parent, work)
            self.assertNotEqual(work, self.root)
            temporary.append(work)
            destination.write_bytes(self.source.read_bytes())

        with self.assertRaises(service.RVZToolRequired):
            preview_starters(rvz, "seed", Options())
        with ExitStack() as stack:
            self.pipeline(stack)
            stack.enter_context(patch.object(service, "convert", side_effect=convert))
            result = preview_starters(rvz, "seed", Options(), tool)
        self.assertFalse(temporary[0].exists())
        self.assertEqual(rvz.read_bytes(), b"synthetic compressed source")
        self.assertEqual(result["source_iso_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(set(self.root.iterdir()), {self.source, rvz, tool})

    def test_portraits_use_internal_id_and_ordinary_half(self):
        color = (11, 23, 37, 255)
        archive = fsys([("face277", portrait(color, (255, 0, 0, 255)))])
        with patch.object(artwork, "_disc_files", return_value={"poke_face.fsys": archive}):
            image = artwork.extract_portraits(self.source, (277,))[277]
        self.assertEqual(artwork._png_pixels(image, (42, 42)), bytes(color) * (42 * 42))
        for ids in ((), (0,), (True,), (413,), tuple(range(1, 66))):
            with self.assertRaises(artwork.ArtworkError):
                artwork.extract_portraits(self.source, ids)

    def test_shiny_portraits_use_actual_lower_half_without_changing_normal_portraits(self):
        ordinary, shiny = (11, 23, 37, 255), (181, 53, 97, 255)
        archive = fsys([("face277", portrait(ordinary, shiny))])
        with patch.object(artwork, "_disc_files", return_value={"poke_face.fsys": archive}):
            normal = artwork.extract_portraits(self.source, (277,))[277]
            alternate = artwork.extract_portraits(self.source, (277,), shiny=True)[277]
            with self.assertRaises(artwork.ArtworkError):
                artwork.extract_portraits(self.source, (277,), shiny=1)
        self.assertEqual(artwork._png_pixels(normal, (42, 42)), bytes(ordinary) * 42**2)
        self.assertEqual(artwork._png_pixels(alternate, (42, 42)), bytes(shiny) * 42**2)

    def test_preview_distinguishes_guaranteed_shinies_from_runtime_rolls(self):
        for enabled, chance, policy in ((False, 100, "original"), (True, 0, "never"),
                                        (True, 1, "in-game"), (True, 100, "always")):
            with self.subTest(enabled=enabled, chance=chance), ExitStack() as stack:
                self.pipeline(stack)
                extract = stack.enter_context(patch("orre_randomizer.preview.extract_portraits", return_value={}))
                options = replace(Options.recommended(), custom_shinies=enabled, seeded_shinies=False, shiny_chance_percent=chance)
                result = preview_starters(self.source, "fixed", options)
                self.assertEqual(result["shiny_policy"], policy)
                self.assertTrue(all(row["shiny"] == (policy == "always") for row in result["starters"]))
                self.assertEqual(extract.call_args.kwargs, {"shiny": True} if policy == "always" else {})

    def test_seeded_preview_uses_exact_summary_flags_and_both_faces_of_same_species(self):
        special = self.summary["special_gameplay"]["specials"]
        self.summary["final_shadow_picks"] = [dict(special[0], species_index=277, shadow_id=21)]
        special.append(dict(special[1], key="pikachu-event"))
        self.summary["shinies"] = {"enabled": True, "seeded": True, "seeded_decisions": {
            "specials": {"umbreon": True, "espeon": False, "pikachu-event": True},
            "shadows": {"21": False}, "trainer_slots": {}}}

        def faces(source, species, *, shiny=False):
            return {index: f"{index}-{'shiny' if shiny else 'normal'}".encode() for index in species}

        with ExitStack() as stack:
            self.pipeline(stack)
            extract = stack.enter_context(patch("orre_randomizer.preview.extract_portraits", side_effect=faces))
            result = preview_starters(self.source, "fixed", replace(Options(), custom_shinies=True,
                                                                    seeded_shinies=True, shiny_chance_percent=1))
        self.assertEqual(result["shiny_policy"], "seeded")
        rows = result["starters"] + result["shadows"] + result["gifts"]
        self.assertEqual([row["shiny"] for row in rows], [True, False, False, True])
        self.assertEqual([row["portrait_png"] for row in rows],
                         [b"277-shiny", b"196-normal", b"277-normal", b"196-shiny"])
        self.assertEqual(extract.call_args_list,
                         [call(self.source, (196, 277)), call(self.source, (277, 196), shiny=True)])

    def test_seeded_endpoints_keep_policies_and_read_production_decisions(self):
        for chance, policy in ((0, "never"), (100, "always")):
            with self.subTest(chance=chance), ExitStack() as stack:
                self.summary["shinies"] = {"enabled": True, "seeded": True, "seeded_decisions": {
                    "specials": {"umbreon": chance == 100, "espeon": chance == 100},
                    "shadows": {}, "trainer_slots": {}}}
                self.pipeline(stack)
                result = preview_starters(self.source, "fixed", replace(Options(), custom_shinies=True,
                                                                        seeded_shinies=True, shiny_chance_percent=chance))
            self.assertEqual(result["shiny_policy"], policy)
            self.assertEqual([row["shiny"] for row in result["starters"]], [chance == 100] * 2)

    def test_portrait_requests_are_deduplicated_and_bounded_to_64_species(self):
        sample = self.summary["special_gameplay"]["specials"][0]
        self.summary["final_shadow_picks"] = [dict(sample, species_index=index, shadow_id=index)
                                              for index in range(1, 98)]
        self.summary["final_shadow_picks"].append(dict(sample, species_index=1, shadow_id=98))
        with ExitStack() as stack:
            self.pipeline(stack)
            extract = stack.enter_context(patch("orre_randomizer.preview.extract_portraits", return_value={}))
            result = preview_starters(self.source, "fixed", Options())
        batches = [item.args[1] for item in extract.call_args_list]
        self.assertEqual([len(batch) for batch in batches], [64, 35])
        self.assertEqual(len({index for batch in batches for index in batch}), 99)
        self.assertEqual(result["shadows"][-1]["species"], 1)

    def test_japanese_names_cover_all_candidates_by_national_number(self):
        self.assertEqual(set(SPECIES_NAMES), set(range(1, 387)))
        self.assertEqual(SPECIES_NAMES[252], "キモリ")
        self.assertEqual(SPECIES_NAMES[196], "エーフィ")
        self.assertEqual(SPECIES_NAMES[197], "ブラッキー")

    def test_wide_faces_and_unown_use_one_ordinary_frame(self):
        color, other = (11, 23, 37, 255), (255, 0, 0, 255)
        tiles = bytearray()
        for by in range(0, 84, 4):
            for bx in range(0, 84, 4):
                colors = [color if bx+i % 4 < 42 and by+i // 4 < 42 else other for i in range(16)]
                tiles.extend(bytes(value for r, g, b, a in colors for value in (a, r)))
                tiles.extend(bytes(value for r, g, b, a in colors for value in (g, b)))
        archive = fsys([("face001", texture(84, 84, 32, tiles)),
                        ("face201a", portrait(color, other))])
        with patch.object(artwork, "_disc_files", return_value={"poke_face.fsys": archive}):
            images = artwork.extract_portraits(self.source, (1, 201))
        for image in images.values():
            self.assertEqual(artwork._png_pixels(image, (42, 42)), bytes(color) * (42 * 42))


if __name__ == "__main__":
    unittest.main()
