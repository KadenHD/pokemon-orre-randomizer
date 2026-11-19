"""Custom weather paint is separate, exact-key, x4 and safe to stage offline."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from orre_randomizer import hd_castform_shinies as art
from orre_randomizer.hd_packs import PACKS


def record(payload):
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


@contextmanager
def artwork():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        bundle, pack = root / "bundle", root / "source-pack"
        folder = bundle / "castform-shinies"
        folder.mkdir(parents=True)
        (pack / "Textures").mkdir(parents=True)
        source_key = "tex1_4x4_1111111111111111_6.png"
        source = pack / "Textures" / source_key
        Image.new("RGBA", (16, 16), (80, 40, 160, 255)).save(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        selected = PACKS["colosseum"]
        marker = {"key": selected.key, "archives": [part.sha256 for part in selected.parts]}
        (pack / "installed.json").write_text(json.dumps(marker))
        files, payloads = [], {}
        targets = [
            ("model-map.png", "tex1_4x4_2222222222222222_6.png", "material", [4, 4], ["GC6P01", "GXXP01"]),
            ("square-face.png", "tex1_42x84_3333333333333333_6.png", "portrait", [42, 84], ["GC6P01"]),
            ("round-face.png", "tex1_42x84_4444444444444444_5555555555555555_9.png", "portrait", [42, 84], ["GXXP01"]),
        ]
        for name, key, role, native_size, games in targets:
            size = tuple(v * 4 for v in native_size)
            image = Image.new("RGBA", size, (180, 90, 220, 255))
            if name == "round-face.png":
                rgba = bytearray(image.tobytes())
                for y in range(336):
                    for x in range(168):
                        if (x + .5 - 84) ** 2 + (y % 168 + .5 - 84) ** 2 >= 90 ** 2:
                            at = (y * 168 + x) * 4
                            rgba[at:at + 4] = bytes(4)
                image = Image.frombytes("RGBA", size, bytes(rgba))
            path = folder / name
            image.save(path)
            payloads["castform-shinies/" + name] = path.read_bytes()
            files.append({"file": name, "native_key": key, "native_dimensions": native_size,
                "dimensions": list(size), "game_ids": games, "required_pack": "colosseum", "role": role,
                "native_rgba_sha256": hashlib.sha256(image.resize(tuple(native_size), Image.Resampling.NEAREST).tobytes()).hexdigest(),
                "material_sources": ["sun-paint"], **record(path.read_bytes())})
        catalogue = {"schema": 1, "kind": "castform-shiny-native-and-hd", "review_only": False,
            "material_sources": {"sun-paint": {"pack": "colosseum", "native_key": source_key,
                "physical_file": source_key, "sha256": digest}}, "files": files,
            "source_models": {"sun": {"sha256": "a" * 64}},
            "faces": {"colosseum": {"sun": files[1]["native_key"]}, "xd": {"sun": files[2]["native_key"]}}}

        def save():
            manifest = (json.dumps(catalogue, sort_keys=True) + "\n").encode()
            (bundle / art.CATALOGUE).write_bytes(manifest)
            provenance = {"files": {name: record(payload) for name, payload in payloads.items()}}
            provenance["files"][art.CATALOGUE] = record(manifest)
            (bundle / "provenance.json").write_text(json.dumps(provenance))

        save()
        pins = {"colosseum": {source_key: digest}, "xd": {}}
        with patch.object(art, "bundle_root", return_value=bundle), \
                patch("orre_randomizer.resources.bundle_root", return_value=bundle), \
                patch.object(art, "HD_MATERIAL_SOURCE_PINS", pins):
            yield root, bundle, pack, catalogue, payloads, save


class CastformShinyHDTests(unittest.TestCase):
    def test_old_build_without_catalogue_is_inactive_and_does_not_create_output(self):
        with TemporaryDirectory() as directory, patch.object(art, "bundle_root", return_value=Path(directory)):
            output = Path(directory) / "HD"
            self.assertFalse(art.prepare_castform_shiny_overlays("GC6P01", {}, output)["active"])
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, "Unknown"):
                art.castform_shiny_recipes("GXXK01")

    def test_selected_native_keys_get_exact_x4_bytes_and_leave_source_packs_unchanged(self):
        for game in ("GC6P01", "GXXP01"):
            with self.subTest(game=game), artwork() as (root, bundle, pack, catalogue, payloads, save):
                before = {str(path.relative_to(pack)): path.read_bytes() for path in pack.rglob("*") if path.is_file()}
                output = root / "HD"
                report = art.prepare_castform_shiny_overlays(game, {"colosseum": pack}, output)
                wanted = [row for row in catalogue["files"] if game in row["game_ids"]]
                self.assertEqual(set(report["files"]), {row["native_key"] for row in wanted})
                for row in wanted:
                    self.assertEqual((output / row["native_key"]).read_bytes(), payloads["castform-shinies/" + row["file"]])
                self.assertEqual(len(report["assets"]), 2)
                self.assertEqual(report["required_packs"], ["colosseum"])
                self.assertFalse(report["native_rom_changed"])
                self.assertEqual({str(path.relative_to(pack)): path.read_bytes() for path in pack.rglob("*") if path.is_file()}, before)
                self.assertEqual(art.prepare_castform_shiny_overlays(game, {"colosseum": pack}, output)["files"], report["files"])

    def test_changed_pack_paint_or_marker_and_missing_pack_fail_before_output(self):
        for failure in ("paint", "marker", "absent"):
            with self.subTest(failure=failure), artwork() as (root, bundle, pack, catalogue, payloads, save):
                roots = {"colosseum": pack}
                if failure == "paint":
                    next((pack / "Textures").iterdir()).write_bytes(b"tampered pack paint")
                elif failure == "marker":
                    (pack / "installed.json").write_text('{}')
                else:
                    roots.clear()
                with self.assertRaises(ValueError):
                    art.prepare_castform_shiny_overlays("GC6P01", roots, root / "HD")
                self.assertFalse((root / "HD").exists())

    def test_output_cannot_replace_bundled_artwork_or_write_into_either_source_pack(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            for target in (pack, pack / "Textures/HD", bundle / "HD"):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, "cannot write inside"):
                    art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, target)

    def test_conflicting_output_rejects_the_whole_staged_set_without_new_files(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            output = root / "HD"
            output.mkdir()
            clash = output / catalogue["files"][1]["native_key"]
            clash.write_bytes(b"preserve existing texture")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, output)
            self.assertEqual(list(output.iterdir()), [clash])
            self.assertEqual(clash.read_bytes(), b"preserve existing texture")

    def test_unregistered_source_or_arbitrary_filename_and_wrong_native_size_are_rejected(self):
        changes = (("file", "../escape.png"), ("native_key", "game.iso"), ("native_dimensions", [8, 4]),
                   ("dimensions", [16, 12]), ("game_ids", ["GXXK01"]), ("game_ids", [{}]),
                   ("material_sources", ["unknown"]), ("material_sources", [{}]), ("role", "script"))
        for field, value in changes:
            with self.subTest(field=field, value=value), artwork() as (root, bundle, pack, catalogue, payloads, save):
                catalogue["files"][0][field] = value
                save()
                with self.assertRaises(ValueError):
                    art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, root / "HD")
                self.assertFalse((root / "HD").exists())

    def test_duplicate_native_key_and_source_that_is_not_pinned_cannot_be_registered(self):
        for failure in ("key", "source"):
            with self.subTest(failure=failure), artwork() as (root, bundle, pack, catalogue, payloads, save):
                if failure == "key":
                    catalogue["files"].append(deepcopy(catalogue["files"][0]))
                else:
                    catalogue["material_sources"]["sun-paint"]["sha256"] = "e" * 64
                save()
                with self.assertRaises(ValueError):
                    art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, root / "HD")
                self.assertFalse((root / "HD").exists())

    def test_present_but_unregistered_catalogue_and_changed_png_fail_closed(self):
        for failure in ("catalogue", "PNG"):
            with self.subTest(failure=failure), artwork() as (root, bundle, pack, catalogue, payloads, save):
                path = bundle / (art.CATALOGUE if failure == "catalogue" else "castform-shinies/model-map.png")
                path.write_bytes(path.read_bytes() + b"tampered")
                with self.assertRaises(ValueError):
                    art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, root / "HD")
                self.assertFalse((root / "HD").exists())

    def test_square_portrait_cannot_be_declared_as_xd_and_png_dimensions_are_checked_before_decode(self):
        for failure in ("frame", "dimensions"):
            with self.subTest(failure=failure), artwork() as (root, bundle, pack, catalogue, payloads, save):
                row = catalogue["files"][2]
                if failure == "frame":
                    payload = payloads["castform-shinies/square-face.png"]
                else:
                    payload = payloads["castform-shinies/model-map.png"]
                (bundle / "castform-shinies/round-face.png").write_bytes(payload)
                payloads["castform-shinies/round-face.png"] = payload
                row.update(record(payload))
                save()
                with self.assertRaisesRegex(ValueError, "round frame|header dimensions"):
                    art.prepare_castform_shiny_overlays("GXXP01", {"colosseum": pack}, root / "HD")
                self.assertFalse((root / "HD").exists())

    def test_cache_identity_changes_with_a_new_reviewed_palette(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            before = art.castform_shiny_recipes("GC6P01")["catalogue_sha256"]
            catalogue["palette_revision"] = 2
            save()
            self.assertNotEqual(art.castform_shiny_recipes("GC6P01")["catalogue_sha256"], before)

    def test_declared_hd_route_cannot_publish_only_models_without_their_portraits(self):
        with artwork() as (root, bundle, pack, catalogue, payloads, save):
            catalogue["files"] = [row for row in catalogue["files"] if row["role"] == "material"]
            save()
            with self.assertRaisesRegex(ValueError, "both model paint and portrait"):
                art.prepare_castform_shiny_overlays("GC6P01", {"colosseum": pack}, root / "HD")
            self.assertFalse((root / "HD").exists())


if __name__ == "__main__":
    unittest.main()
