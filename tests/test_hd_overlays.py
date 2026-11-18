"""Native overlays: real Dolphin keys, authored variants and read-only ROMs."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from orre_randomizer import hd_overlays as hd
from orre_randomizer.artwork import _png_pixels
from orre_randomizer.engine.shadow_lugia_palette import make_shadow_lugia_shiny
from tests.test_artwork import fsys, portrait, texture
from tests.test_shadow_lugia_palette import fixture


def archive(resources):
    """Synthetic resource IDs with mathematical colour payloads."""
    value = bytearray(fsys([(name, data) for _, name, data in resources]))
    for index, (ident, _, _) in enumerate(resources):
        struct.pack_into(">I", value, 0x80 + index * 0x30, ident)
    return bytes(value)


def disc(path, files, *, xd=False):
    data = bytearray(0x1000)
    data[:8] = (b"GXXP01" if xd else b"GC6P01") + bytes(2)
    data[0x1C:0x20] = bytes.fromhex("c2339f3d")
    names = bytearray()
    entries = bytearray(struct.pack(">III", 0x01000000, 0, len(files) + 1))
    for name, payload in files:
        entries.extend(struct.pack(">III", len(names), len(data), len(payload)))
        names.extend(name.encode() + b"\0")
        data.extend(payload)
    fst = entries + names
    data[0x440:0x440 + len(fst)] = fst
    struct.pack_into(">II", data, 0x424, 0x440, len(fst))
    path.write_bytes(data)
    return bytes(data)


class HashTests(unittest.TestCase):
    def test_seed_zero_reference_vectors_cover_every_hash_tail_and_long_lanes(self):
        vectors = [(b"", 0xEF46DB3751D8E999), (b"a", 0xD24EC4F1A98C6E5B),
                   (b"abc", 0x44BC2CF5AD770999), (b"hello", 0x26C7827D889F6DA3),
                   (bytes(range(256)), 0x1FACBE8406CD904B)]
        for data, expected in vectors:
            self.assertEqual(hd.xxhash64(data), expected)

    def test_dolphin_ci8_trims_palette_using_padding_indices(self):
        # One visible pixel, but all 32 tiled samples contribute to the key.
        data = bytes((3,)) + bytes((9,)) * 31
        palette = struct.pack(">256H", *range(256))
        expected = f"tex1_1x1_{hd.xxhash64(data):016x}_{hd.xxhash64(palette[6:20]):016x}_9"
        self.assertEqual(hd.dolphin_texture_name(1, 1, 9, data, palette=palette), expected)
        unused_changed = bytearray(palette)
        unused_changed[:6] = b"\xff" * 6
        self.assertEqual(hd.dolphin_texture_name(1, 1, 9, data, palette=unused_changed), expected)
        unused_changed[18] ^= 1
        self.assertNotEqual(hd.dolphin_texture_name(1, 1, 9, data, palette=unused_changed), expected)

    def test_ci4_uses_both_nibbles_and_ci14_masks_high_bits(self):
        data = b"\x25" * 32
        palette = bytes(range(32))
        self.assertIn(f"_{hd.xxhash64(palette[4:12]):016x}_8",
                      hd.dolphin_texture_name(1, 1, 8, data, palette=palette))
        data = b"\xc0\x07" * 16
        palette = bytes(32768)
        self.assertIn(f"_{hd.xxhash64(palette[14:16]):016x}_10",
                      hd.dolphin_texture_name(1, 1, 10, data, palette=palette))

    def test_base_hash_excludes_mips_and_format_uses_gx_integer(self):
        data = bytes(32)
        self.assertEqual(hd.dolphin_texture_name(8, 8, 14, data, mipmaps=True),
                         "tex1_8x8_m_f6e9be5d70632cf5_14")
        for invalid in (data[:-1], data + data):
            with self.assertRaises(hd.OverlayError):
                hd.dolphin_texture_name(8, 8, 14, invalid)


class PixelTests(unittest.TestCase):
    def test_native_direct_intensity_alpha_and_indexed_layouts(self):
        cases = [(0, b"\x88" * 32, (136, 136, 136, 136)),
                 (1, b"\x80" * 32, (128, 128, 128, 128)),
                 (2, b"\xf2" * 32, (34, 34, 34, 255)),
                 (3, b"\x80\x2a" * 16, (42, 42, 42, 128)),
                 (4, b"\xf8\x00" * 16, (255, 0, 0, 255))]
        for fmt, samples, color in cases:
            with self.subTest(fmt=fmt):
                self.assertEqual(hd._pixels(hd._Texture(1, 1, fmt, samples)), bytes(color))
        palette = b"\x80\x00\xfc\x00" + bytes(508)
        self.assertEqual(hd._pixels(hd._Texture(1, 1, 9, b"\x01" * 32, palette)),
                         bytes((255, 0, 0, 255)))

    def test_native_reference_preserves_native_rgba_and_dimensions(self):
        texture = hd._Texture(3, 2, 4, b"\xf8\x00" * 16)
        with tempfile.TemporaryDirectory() as temporary:
            reference = hd._native_reference(Path(temporary), hd._pixels(texture), 3, 2)
            png = (Path(temporary) / reference["file"]).read_bytes()
        self.assertEqual(_png_pixels(png, (3, 2)), bytes((255, 0, 0, 255)) * 6)

    def test_custom_normal_and_shiny_material_maps_remain_distinct(self):
        normal, _ = fixture(False)
        shiny = make_shadow_lugia_shiny(normal, xd=False)
        first = list(hd._dat_textures(normal[0x40:]))
        second = list(hd._dat_textures(shiny[0x40:]))
        self.assertEqual(len(first), 1)
        self.assertEqual(hd._pixels(first[0])[3::4], hd._pixels(second[0])[3::4])
        self.assertNotEqual(hd.dolphin_texture_name(32, 32, 14, first[0].data),
                            hd.dolphin_texture_name(32, 32, 14, second[0].data))

    def test_plusle_shiny_uses_its_dedicated_field_texture_donor(self):
        field_pkx, _ = fixture(False)
        field_dat = field_pkx[0x40:]
        battle = bytearray(field_pkx)
        struct.pack_into(">HH", battle, 0x40 + 0x20 + 0x300, 0xF800, 0)
        recipe_bytes = bytearray(17)
        recipe_bytes[0:13:4] = bytes((0, 1, 2, 3))
        recipe_bytes[13:] = bytes((127, 64, 64, 64))
        battle[-17:] = recipe_bytes
        from orre_randomizer.engine.actor_palette import pkx_recipe
        recipe = pkx_recipe(bytes(battle), xd=False)
        target = list(hd._dat_textures(hd._tinted_dat(field_dat, recipe)))[0]
        source = list(hd._dat_textures(field_dat))[0]
        files = {"M2_guild_1F_1.fsys": archive([(0x06F90400, "prasle_b1", field_dat)]),
                 "pkx_prasle.fsys": archive([(0x01231E00, "prasle", bytes(battle))])}
        with patch.object(hd, "_disc_archives", return_value=[]), \
             patch("orre_randomizer.artwork._disc_files", return_value=files):
            origins, failures = hd._field_origins(Path("unused.iso"), False, {hd._texture_key(target)}, None, None)
        self.assertEqual(failures, [])
        self.assertEqual(origins[hd._texture_key(target)]["file"], hd._texture_key(source))
        self.assertIn("dedicated field model", origins[hd._texture_key(target)]["native_source"])

    def test_xd_shadow_field_belly_uses_its_own_verified_native_map(self):
        from orre_randomizer import xd_shadow_lugia_model as xd_lugia
        from orre_randomizer.engine.shadow_lugia_palette import make_shadow_lugia_shiny_dat
        pkx, _ = fixture(False)
        dat = pkx[0x40:]
        target = list(hd._dat_textures(make_shadow_lugia_shiny_dat(dat)))[0]
        source = list(hd._dat_textures(dat))[0]
        resource = 0x166C0400
        people = archive([(resource, "darklugia_0100", dat)])
        with patch.object(hd, "_disc_archives", return_value=[("people_archive.fsys", people)]), \
             patch.object(xd_lugia, "FIELD_RESOURCES", ((resource, 0x7DF60400),)), \
             patch.object(xd_lugia, "_FIELD_SHA256", {resource: hashlib.sha256(dat).hexdigest()}):
            origins, failures = hd._field_origins(Path("unused.iso"), True, {hd._texture_key(target)}, None, None)
        origin = origins[hd._texture_key(target)]
        self.assertEqual(failures, [])
        self.assertEqual(origin["file"], hd._texture_key(source))
        self.assertEqual(origin["transform"]["type"], "shadow_lugia_belly")
        self.assertIn("authored field model", origin["native_source"])


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.iso = self.root / "generated.iso"
        self.output = self.root / "Textures"

    def test_full_atlas_keeps_normal_and_shiny_rows_without_reading_ordinary_lugia(self):
        atlas = portrait((10, 20, 30, 255), (240, 230, 220, 255))
        data = archive([(0x00191200, "face249", b"not an overlay"),
                        (0x7DF61200, "face249dark_bonus", atlas)])
        original = disc(self.iso, [("poke_face.fsys", data),
                        ("pkx_lugia.fsys", archive([(0x01111E00, "lugia", b"must stay native")]))])
        stat = self.iso.stat()
        report = hd.generate_custom_overlays(self.iso, self.output)
        self.assertEqual(report["texture_count"], 1)
        self.assertEqual([r["resource"] for r in report["resources"]], ["0x7df61200"])
        self.assertFalse(report["hd_ready"])
        self.assertEqual(report["files"], [])
        record = report["assets"][0]["native"]
        pixels = _png_pixels((self.output / record["file"]).read_bytes(), (42, 84))
        self.assertEqual(pixels[:4], bytes((10, 20, 30, 255)))
        self.assertEqual(pixels[-4:], bytes((240, 230, 220, 255)))
        self.assertEqual(self.iso.read_bytes(), original)
        self.assertEqual(self.iso.stat().st_mtime_ns, stat.st_mtime_ns)
        self.assertEqual(hd.native_asset_manifest(self.output), report)
        self.assertNotIn(str(self.iso), json.dumps(report))

    def test_both_dark_battle_variants_and_appended_field_models_are_exported(self):
        normal, _ = fixture(False)
        shiny = make_shadow_lugia_shiny(normal, xd=False)
        models = archive([(0x7DF31E00, "darklugia_bonus", normal),
                          (0x7DF41E00, "rare_darklugia_bonus", shiny)])
        field = archive([(0x7DF00400, "orre_intro_starter_1", shiny[0x40:])])
        disc(self.iso, [("pkx_lugia.fsys", models), ("S1_out.fsys", field)])
        report = hd.generate_custom_overlays(self.iso, self.output)
        self.assertEqual(report["texture_count"], 2)
        self.assertEqual([r["role"] for r in report["resources"]], ["battle", "battle", "field"])
        self.assertEqual(report["resources"][1]["textures"], report["resources"][2]["textures"])
        for row in report["assets"]:
            row = row["native"]
            self.assertEqual(hashlib.sha256((self.output / row["file"]).read_bytes()).hexdigest(), row["sha256"])

    def test_xd_ci8_round_portraits_keep_true_palette_hash_and_alpha(self):
        # Synthetic circular alpha mask; CI8 palettes remain independent.
        raw = bytearray(4672)
        struct.pack_into(">HHBBHI", raw, 0, 42, 84, 8, 1, 0, 1)
        struct.pack_into(">I", raw, 0xC, 3)
        struct.pack_into(">I", raw, 0x28, 128)
        struct.pack_into(">I", raw, 0x48, 4160)
        raw[128:4160] = bytes((1,)) * 4032
        raw[128] = 0
        struct.pack_into(">HH", raw, 4160, 0, 0xFC00)
        rare = bytearray(raw)
        struct.pack_into(">H", rare, 4162, 0xFFFF)
        data = archive([(0x21581200, "face249dark", b"unmodified source"),
                        (0x7DF71200, "face249dark_black", bytes(raw)),
                        (0x7DF51200, "face249dark_shiny", bytes(rare))])
        disc(self.iso, [("poke_face.fsys", data)], xd=True)
        report = hd.generate_custom_overlays(self.iso, self.output, is_xd=True)
        self.assertEqual(report["texture_count"], 2)
        self.assertTrue(all(r["native_format"] == 9 for r in report["assets"]))
        for asset in report["assets"]:
            record = asset["native"]
            pixels = _png_pixels((self.output / record["file"]).read_bytes(), (42, 84))
            self.assertEqual(pixels[3], 0)

    def test_cancellation_and_invalid_iso_write_nothing(self):
        self.iso.write_bytes(bytes(64))
        event = Event()
        event.set()
        with self.assertRaises(InterruptedError):
            hd.generate_custom_overlays(self.iso, self.output, cancel=event)
        self.assertFalse(self.output.exists())
        with self.assertRaises(hd.OverlayError):
            hd.generate_custom_overlays(self.iso, self.output)
        self.assertFalse(self.output.exists())

    def test_malformed_selected_model_fails_without_publishing_manifest(self):
        disc(self.iso, [("pkx_lugia.fsys", archive([(0x7DF31E00, "darklugia_bonus", bytes(64))]))])
        with self.assertRaises(hd.OverlayError):
            hd.generate_custom_overlays(self.iso, self.output)
        self.assertFalse((self.output / "orre-overlays-v2.json").exists())

    def test_rejects_symlink_destination_and_overlapping_source(self):
        disc(self.iso, [])
        with self.assertRaises(hd.OverlayError):
            hd.generate_custom_overlays(self.iso, self.root)
        outside = self.root / "outside"
        outside.mkdir()
        try:
            self.output.symlink_to(outside, target_is_directory=True)
        except OSError:
            return
        with self.assertRaises(hd.OverlayError):
            hd.generate_custom_overlays(self.iso, self.output)


class PackDerivedTests(unittest.TestCase):
    def setUp(self):
        from orre_randomizer.hd_packs import PACKS
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = self.root / "native"
        self.output = self.root / "HD"
        self.pack = self.root / "pack"
        (self.pack / "Textures").mkdir(parents=True)
        pinned = PACKS["colosseum"]
        (self.pack / "installed.json").write_text(json.dumps({"key": pinned.key,
                    "archives": [part.sha256 for part in pinned.parts]}))
        source = self.root / "source.iso"
        normal, _ = fixture(False)
        disc(source, [("pkx_lugia.fsys", archive([(0x7DF31E00, "darklugia_bonus", normal)]))])
        self.report = hd.capture_native_assets(source, self.native)
        source.unlink()  # Lazy HD preparation cannot consult any ROM.
        self.asset = self.report["assets"][0]
        self.donor_name = self.asset["file"]
        self.pattern = bytes(value for y in range(128) for x in range(128)
                             for value in (240 if (x + y) % 2 else 40, 120, 200, 255))
        (self.pack / "Textures" / self.donor_name).write_bytes(hd._png((128, 128), self.pattern))

    def save(self):
        (self.native / "orre-overlays-v2.json").write_text(json.dumps(self.report))

    def test_hd_preserves_actual_pack_details_without_a_rom(self):
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "identity"}}
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertTrue(report["hd_ready"])
        self.assertEqual(_png_pixels((self.output / self.asset["file"]).read_bytes(), (128, 128)), self.pattern)
        self.assertEqual(report["files"][0]["hd_source"]["file"], self.donor_name)
        self.assertNotIn("filter", report)

    def test_authored_recolor_keeps_hd_variation_and_alpha(self):
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "shadow_lugia_belly", "factors": [0.18, 0.18, 0.20]}}
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        output = _png_pixels((self.output / self.asset["file"]).read_bytes(), (128, 128))
        self.assertTrue(report["hd_ready"])
        self.assertEqual(output[3::4], self.pattern[3::4])
        self.assertEqual(set(output[0::4]), {7, 43})
        self.assertEqual(set(output[2::4]), {40})

    def test_pack_sampler_alias_preserves_the_exact_texture_and_palette_hashes(self):
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "identity"}}
        alias = hd._mipmap_alias(self.donor_name)
        (self.pack / "Textures" / self.donor_name).rename(self.pack / "Textures" / alias)
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertTrue(report["hd_ready"])
        self.assertEqual(report["files"][0]["hd_source"]["physical_file"], alias)
        self.assertEqual(report["files"][0]["hd_source"]["logical_file"], self.donor_name)
        self.assertEqual(_png_pixels((self.output / self.asset["file"]).read_bytes(), (128, 128)), self.pattern)

    def test_missing_pack_or_native_only_asset_blocks_hd_without_native_filtering(self):
        for origin in (None, {"game": "xd", "file": "missing.png", "transform": {"type": "identity"}}):
            self.asset["hd"] = origin
            self.save()
            report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={})
            self.assertFalse(report["hd_ready"])
            self.assertEqual(report["files"], [])
            self.assertTrue(report["missing_assets"])
            self.assertFalse((self.output / self.asset["file"]).exists())

    def test_unpinned_pack_and_modified_native_reference_are_rejected(self):
        (self.pack / "installed.json").write_text('{"key":"unexpected","archives":[]}')
        self.save()
        with self.assertRaises(hd.OverlayError):
            hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        (self.native / self.asset["native"]["file"]).write_bytes(b"modified")
        with self.assertRaises(hd.OverlayError):
            hd.prepare_hd_overlays(self.native, self.output, pack_roots={})
        self.assertFalse(self.output.exists())

    def test_exact_constant_colour_is_analytic_and_needs_no_painted_donor(self):
        self.asset["hd"] = {"transform": {"type": "constant-color", "rgba": [21, 34, 55, 255]}}
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={})
        self.assertTrue(report["hd_ready"])
        self.assertEqual(report["files"][0]["hd_source"]["kind"], "constant-color")
        pixels = _png_pixels((self.output / self.asset["file"]).read_bytes(), (128, 128))
        self.assertEqual(pixels, bytes((21, 34, 55, 255)) * 128**2)

    def test_actual_upstream_x2_detail_can_fill_x4_with_declared_provenance(self):
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "identity"}}
        pixels = bytes(channel for y in range(64) for x in range(64)
                       for channel in (255 if x % 2 else 0, 80, 160, 255))
        (self.pack / "Textures" / self.donor_name).write_bytes(hd._png((64, 64), pixels))
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertTrue(report["hd_ready"])
        source = report["files"][0]["hd_source"]
        self.assertEqual((source["source_scale"], source["output_scale"]), (2, 4))
        self.assertEqual(source["resample"]["source"], "actual upstream HD texture")
        output = _png_pixels((self.output / self.asset["file"]).read_bytes(), (128, 128))
        self.assertGreater(len(set(output[0::4])), 2)

    def test_dds_x8_source_is_decoded_and_reduced_with_physical_provenance(self):
        from PIL import Image
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "identity"}}
        (self.pack / "Textures" / self.donor_name).unlink()
        path = self.pack / "Textures" / Path(self.donor_name).with_suffix(".DDS")
        pixels = bytes(channel for y in range(256) for x in range(256)
                       for channel in (x, 80, 160, 255))
        Image.frombytes("RGBA", (256, 256), pixels).save(path, pixel_format="DXT5")
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertTrue(report["hd_ready"])
        record = report["files"][0]
        source = record["hd_source"]
        self.assertEqual(source["logical_file"], self.donor_name)
        self.assertEqual(source["physical_file"], path.name)
        self.assertEqual(source["format"], "DDS")
        self.assertEqual(source["source_scale"], 8)
        self.assertEqual(source["output_scale"], 4)
        self.assertEqual(source["resample"]["from_scale"], 8)
        self.assertEqual(source["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual((record["width"], record["height"]), (128, 128))

    def test_native_sized_bitmap_is_never_accepted_as_an_hd_donor(self):
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "identity"}}
        (self.pack / "Textures" / self.donor_name).write_bytes(hd._png((32, 32), bytes((17, 31, 47, 255)) * 1024))
        self.save()
        with self.assertRaisesRegex(hd.OverlayError, "genuine high-resolution"):
            hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})

    def test_actual_pack_x16_donor_is_reduced_to_x4_and_reports_its_full_source(self):
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "transform": {"type": "identity"}}
        pixels = bytes(c for y in range(512) for x in range(512) for c in (x // 2, 90, 150, 255))
        (self.pack / "Textures" / self.donor_name).write_bytes(hd._png((512, 512), pixels))
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertTrue(report["hd_ready"])
        source = report["files"][0]["hd_source"]
        self.assertEqual(source["source_scale"], 16)
        self.assertEqual(source["resample"], {"source": "actual upstream HD texture", "from_scale": 16, "to_scale": 4})
        self.assertEqual((report["files"][0]["width"], report["files"][0]["height"]), (128, 128))

    def test_byte_identical_stock_field_gap_preserves_the_upstream_fallback(self):
        (self.pack / "Textures" / self.donor_name).unlink()
        self.asset.update(role="field", classification="inherited_stock")
        self.asset["hd"] = {"game": "colosseum", "file": self.donor_name,
                            "native_source": "original.pkx/model", "native_model_sha256": "0" * 64,
                            "native_texture_sha256": "1" * 64, "transform": {"type": "identity"}}
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertTrue(report["hd_ready"])
        self.assertEqual(report["files"], [])
        self.assertEqual(report["inherited_stock"][0]["policy"], "base_pack_fallback")
        self.asset["hd"]["transform"] = {"type": "pkx_recipe", "route": [0, 1, 2, 3], "gain": [64] * 4}
        self.save()
        report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        self.assertFalse(report["hd_ready"])
        self.assertTrue(report["missing_assets"])

    def test_authored_ramp_uses_real_hd_palette_pixels_and_no_native_bitmap_input(self):
        filename = "tex1_64x64_48fd3f1e8b93d316_5.png"
        pixels = bytes(channel for y in range(256) for x in range(256)
                       for channel in ((45, 45, 45, 255) if x < 86 else
                                       (230, 180, 15, 255) if x < 171 else (245, 245, 245, 255)))
        path = self.pack / "Textures" / filename
        path.write_bytes(hd._png((256, 256), pixels))
        origin = {"file": "tex1_64x2_d3688e7d5cede59d_1a3985ee4c048206_9.png"}
        image, provenance = hd._authored_material_retouch(origin, self.pack)
        self.assertEqual((image.width(), image.height()), (256, 8))
        self.assertEqual(provenance["kind"], "authored-hd-material-retouch")
        self.assertFalse(provenance["native_bitmap_resampled"])
        self.assertEqual(provenance["reference"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        for anchor in provenance["palette"].values():
            x, y = anchor["pixel"]
            self.assertEqual(list(pixels[(y * 256 + x) * 4:(y * 256 + x) * 4 + 3]), anchor["rgb"])
        self.assertEqual(provenance["palette"]["gold_rings"]["rgb"], [230, 180, 15])

    def test_field_material_is_reconstructed_before_shiny_factor_is_applied_once(self):
        from PySide6.QtGui import QImage, QColor
        target = "tex1_32x32_72d6885b2651fd6f_14.png"
        key = "tex1_32x32_a7a1e0130c44ec22_14.png"
        self.asset.update(file=target, base_key=target, role="field")
        self.asset["hd"] = {"game": "colosseum", "file": key,
                            "transform": {"type": "shadow_lugia_belly", "factors": [.18, .18, .20]}}
        self.save()
        image = QImage(128, 128, QImage.Format.Format_RGBA8888)
        image.fill(QColor(100, 80, 60, 255))
        reference = {"file": self.donor_name,
                     **hd._load_hd(self.pack / "Textures" / self.donor_name, (32, 32)).metadata}
        provenance = {"kind": "authored-hd-field-material-retouch", "reference": reference,
                      "native_bitmap_resampled": False}
        with patch("orre_randomizer.hd_lugia_field.render_lugia_field_material", return_value=(image, provenance)) as render:
            report = hd.prepare_hd_overlays(self.native, self.output, pack_roots={"colosseum": self.pack})
        render.assert_called_once_with(self.pack.resolve(), native_key=key, target_key=target)
        self.assertTrue(report["hd_ready"])
        pixels = _png_pixels((self.output / target).read_bytes(), (128, 128))
        self.assertEqual(pixels[:4], bytes((18, 14, 12, 255)))
        self.assertEqual(report["files"][0]["hd_source"]["kind"], "authored-hd-field-material-retouch")


class LugiaMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pack = Path(self.temp.name)
        (self.pack / "Textures").mkdir()
        self.sources = {}
        for name, size, colors in (
                ("tex1_32x32_afade9df5d7d12c3_14.png", 128, ((170, 180, 200), (240, 244, 250))),
                ("tex1_64x64_830778f52c6de2c0_44fccd7f7f60660f_9.png", 256,
                 ((110, 15, 25), (180, 35, 50), (250, 70, 85)))):
            rgba = bytes(channel for y in range(size) for x in range(size)
                         for channel in (*colors[min(len(colors) - 1, x * len(colors) // size)], 255))
            (self.pack / "Textures" / name).write_bytes(hd._png((size, size), rgba))
            self.sources[name] = (size, rgba)

    def test_all_missing_lugia_maps_are_authored_x4_with_real_hd_palette_anchors(self):
        for key, specification in hd._LUGIA_RECONSTRUCTED_MATERIALS.items():
            with self.subTest(key=key):
                image, proof = hd._lugia_material_reconstruction({"file": key}, self.pack)
                size = specification[0] * 4
                self.assertEqual((image.width(), image.height()), (size, size))
                rgba = bytes(image.constBits())
                self.assertEqual(set(rgba[3::4]), {255})
                self.assertGreater(len(set(rgba[0::4])), 20)
                self.assertEqual(proof["kind"], "authored-hd-lugia-material")
                self.assertEqual(proof["hd_art_revision"], 2)
                self.assertFalse(proof["native_bitmap_resampled"])
                self.assertTrue(proof["material"]["specular_unchanged"])
                for anchor in proof["palette"].values():
                    width, pixels = self.sources[anchor["physical_file"]]
                    x, y = anchor["pixel"]
                    self.assertEqual(list(pixels[(y * width + x) * 4:(y * width + x) * 4 + 3]), anchor["rgb"])
                for source in proof["references"]:
                    self.assertEqual(source["sha256"], hashlib.sha256((self.pack / "Textures" / source["file"]).read_bytes()).hexdigest())
                # Continuous functions create subpixel detail inside native texels.
                self.assertTrue(any(len({rgba[((y + dy) * size + x + dx) * 4]
                                         for dy in range(4) for dx in range(4)}) > 4
                                    for y in range(0, size, 4) for x in range(0, size, 4)))

    def test_reflection_and_oral_symbols_keep_their_native_material_roles(self):
        keys = list(hd._LUGIA_RECONSTRUCTED_MATERIALS)
        reflection, proof = hd._lugia_material_reconstruction({"file": keys[0]}, self.pack)
        self.assertEqual(proof["material"]["projection"], "HSD normal-vector reflection")
        self.assertGreater(reflection.pixelColor(27, 33).red(), reflection.pixelColor(64, 92).red() + 100)
        mouth, _ = hd._lugia_material_reconstruction({"file": keys[1]}, self.pack)
        self.assertGreater(mouth.pixelColor(0, 32).red(), 200)
        self.assertLess(mouth.pixelColor(32, 60).red(), mouth.pixelColor(10, 30).red())
        tongue, proof = hd._lugia_material_reconstruction({"file": keys[2]}, self.pack)
        self.assertEqual(proof["material"]["native_colors"], "808080ffffffffff000000ff")
        self.assertGreater(tongue.pixelColor(5, 10).green(), tongue.pixelColor(48, 10).green() + 80)

    def test_changed_native_projection_is_rejected_and_no_native_fallback_is_allowed(self):
        from orre_randomizer.engine.postgame_lugia_model import verified_model_asset
        model, provenance = verified_model_asset()
        key = next(iter(hd._LUGIA_RECONSTRUCTED_MATERIALS))
        changed = bytearray(model)
        struct.pack_into(">I", changed, 0x40 + 32 + 0x6e50 + 0x40, 0x30010)
        with patch("orre_randomizer.engine.postgame_lugia_model.verified_model_asset", return_value=(bytes(changed), provenance)):
            with self.assertRaisesRegex(hd.OverlayError, "projection"):
                hd._lugia_material_reconstruction({"file": key}, self.pack)
        self.assertFalse(hd._inherited_stock({"base_key": key, "role": "battle"}, {"file": key}))
        (self.pack / "Textures" / next(iter(self.sources))).unlink()
        with self.assertRaises(hd._MissingHDAsset):
            hd._lugia_material_reconstruction({"file": key}, self.pack)

    def test_every_lugia_field_variant_requires_hd_even_for_unchanged_stock_maps(self):
        from orre_randomizer.xd_shadow_lugia_model import _FIELD_SHA256
        from orre_randomizer.engine.postgame_lugia_model import verified_model_asset
        _, model = verified_model_asset()
        key = "tex1_64x32_049351b1fbbbcf67_14.png"
        asset = {"base_key": key, "role": "field", "classification": "inherited_stock"}
        origin = {"file": key, "native_texture_sha256": "a" * 64, "transform": {"type": "identity"}}
        for sha in (*_FIELD_SHA256.values(), model["source"]["model_sha256"]):
            self.assertFalse(hd._inherited_stock(asset, dict(origin, native_model_sha256=sha)))
        # This policy is specific to the custom Lugia models.
        self.assertTrue(hd._inherited_stock(asset, dict(origin, native_model_sha256="b" * 64)))


class HDWholeBodyTests(unittest.TestCase):
    def test_accepted_model_portraits_follow_saved_variant_and_material_registry(self):
        from orre_randomizer.hd_packs import PACKS
        from orre_randomizer.model_portraits import portrait_filename
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "assets/game/models"
            models.mkdir(parents=True)
            parent = {"source": {"hd_art_revision": 2, "hd_material_coverage": {
                "total_native_materials": 5, "exact_pack_materials": 2,
                "authored_pack_derived": 3, "derived_shiny_materials": 1, "inherited_stock": []}}}
            parent_path = models / "hd-fullbody-manifest.json"
            parent_path.write_text(json.dumps(parent))
            registry = {"schema": 1, "kind": "native-mesh-render-portrait", "review_only": False,
                "native_bitmap_upscaled_for_hd": False,
                "source": {"hd": {"pack": PACKS["xd"].key,
                    "archives": [part.sha256 for part in PACKS["xd"].parts],
                    "material_manifest_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest()}},
                "files": {}}
            colors = [bytes((41, 16, 57, 255)) * 168 * 168,
                      bytes((230, 232, 236, 255)) * 168 * 168]
            for game in ("colosseum", "xd"):
                for shiny in (False, True):
                    name = portrait_filename(game, shiny, 4)
                    payload = hd._png((168, 168), colors[int(shiny)])
                    (models / name).write_bytes(payload)
                    registry["files"][name] = {"game": game, "shiny": shiny, "scale": 4,
                        "dimensions": [168, 168], "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest()}
            registry_path = models / "portrait-variants.json"
            registry_path.write_text(json.dumps(registry))
            with patch.object(hd, "__file__", str(root / "hd_overlays.py")):
                for game, shiny, expected in (("colosseum", False, colors[0] + colors[1]),
                                              ("xd", False, colors[0] * 2),
                                              ("xd", True, colors[1] * 2)):
                    image, proof = hd._portrait_hd(None, {"game": game, "shiny": shiny}, root)
                    self.assertEqual(bytes(image.constBits()), expected)
                    self.assertEqual(proof["kind"], "registered-model-render-portrait")
                # A repaint candidate and a render with a changed material
                # parent are both rejected before they can replace game art.
                registry["review_only"] = True
                registry_path.write_text(json.dumps(registry))
                with self.assertRaisesRegex(hd._MissingHDAsset, "visual validation"):
                    hd._portrait_hd(None, {"game": "xd", "shiny": False}, root)
                registry["review_only"] = False
                registry_path.write_text(json.dumps(registry))
                parent_path.write_text(parent_path.read_text() + " ")
                with self.assertRaisesRegex(hd._MissingHDAsset, "visual validation"):
                    hd._portrait_hd(None, {"game": "xd", "shiny": True}, root)

    def test_pack_model_variant_and_png_integrity_are_required(self):
        from orre_randomizer.hd_packs import PACKS
        from orre_randomizer.engine.postgame_lugia_model import verified_model_asset
        _, native = verified_model_asset()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "assets/game/models"
            folder.mkdir(parents=True)
            filename = "dark-lugia-body-x4.png"
            pixels = bytes(channel for y in range(256) for x in range(256)
                           for channel in ((30, 60, 90, 255) if 16 <= x < 240 and 16 <= y < 240 else (0, 0, 0, 0)))
            png = hd._png((256, 256), pixels)
            (folder / filename).write_bytes(png)
            manifest = {"kind": "native-mesh-render-with-pack-hd-textures",
                "source": {"pack": PACKS["xd"].key, "archives": [p.sha256 for p in PACKS["xd"].parts],
                           "hd_art_revision": 2, "hd_material_coverage": {"total_native_materials": 5,
                               "exact_pack_materials": 2, "authored_pack_derived": 3,
                               "derived_shiny_materials": 1, "inherited_stock": []},
                           "model": {"original_sha256": native["source"]["model_sha256"]}},
                "files": {filename: {"sha256": hashlib.sha256(png).hexdigest(), "shiny": False}}}
            path = folder / "hd-fullbody-manifest.json"
            path.write_text(json.dumps(manifest))
            with patch.object(hd, "__file__", str(root / "hd_overlays.py")):
                image, record = hd._rendered_body(False)
                self.assertEqual(image.width(), 256)
                self.assertEqual(record["source"]["model"]["original_sha256"], native["source"]["model_sha256"])
                (folder / filename).write_bytes(png[:-1] + b"x")
                with self.assertRaises(hd.OverlayError):
                    hd._rendered_body(False)
                (folder / filename).write_bytes(png)
                manifest["source"]["model"]["original_sha256"] = "0" * 64
                path.write_text(json.dumps(manifest))
                with self.assertRaises(hd.OverlayError):
                    hd._rendered_body(False)
                manifest["source"]["model"]["original_sha256"] = native["source"]["model_sha256"]
                manifest["files"][filename]["shiny"] = True
                path.write_text(json.dumps(manifest))
                with self.assertRaises(hd.OverlayError):
                    hd._rendered_body(False)
                manifest["files"][filename]["shiny"] = False
                manifest["source"]["pack"] = "unselected-pack"
                path.write_text(json.dumps(manifest))
                with self.assertRaises(hd.OverlayError):
                    hd._rendered_body(False)

                manifest["source"]["pack"] = PACKS["xd"].key
                manifest["files"][filename]["shiny"] = False
                common = {"schema": 1, "matrix_count": 86, "pose_signature_sha256": "1" * 64}
                native_name = "dark-lugia-body.png"
                native_body = hd._png((64, 64), b'\x20\x40\x60\xff' * 4096)
                (folder / native_name).write_bytes(native_body)
                native_record = {"sha256": hashlib.sha256(native_body).hexdigest(), "source_capture_sha256": "2" * 64}
                native_manifest = {"common_capture": common, "files": {native_name: native_record}}
                native_bytes = json.dumps(native_manifest).encode()
                (folder / "fullbody-manifest.json").write_bytes(native_bytes)
                manifest.update(common_capture=common, paired_native={
                    "manifest_sha256": hashlib.sha256(native_bytes).hexdigest(), "files": {native_name: native_record}})
                manifest["files"][filename]["pose_signature_sha256"] = common["pose_signature_sha256"]
                path.write_text(json.dumps(manifest))
                hd._rendered_body(False)
                manifest["files"][filename]["pose_signature_sha256"] = "3" * 64
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(hd.OverlayError, "poses do not match"):
                    hd._rendered_body(False)
                manifest["files"][filename]["pose_signature_sha256"] = common["pose_signature_sha256"]
                path.write_text(json.dumps(manifest))
                (folder / native_name).write_bytes(native_body + b'changed')
                with self.assertRaisesRegex(hd.OverlayError, "poses do not match"):
                    hd._rendered_body(False)

    def test_both_body_and_portrait_refuse_old_partial_material_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "assets/game/models"
            folder.mkdir(parents=True)
            (folder / "dark-lugia-body-x4.png").write_bytes(b"presence only")
            for source in ({}, {"hd_art_revision": 2, "hd_material_coverage": {
                    "total_native_materials": 5, "exact_pack_materials": 2,
                    "derived_shiny_materials": 1, "inherited_stock": ["three native maps"]}}):
                (folder / "hd-fullbody-manifest.json").write_text(json.dumps({"source": source}))
                with patch.object(hd, "__file__", str(root / "hd_overlays.py")):
                    with self.assertRaisesRegex(hd._MissingHDAsset, "complete revision-2"):
                        hd._rendered_body(False)
                    with self.assertRaisesRegex(hd._MissingHDAsset, "complete revision-2"):
                        hd._rendered_portrait({"game": "colosseum"}, root)


class DNAVariantTests(unittest.TestCase):
    def test_hd_body_does_not_silently_replace_a_different_native_pose(self):
        from PySide6.QtGui import QImage, QColor
        ui = QImage(4096, 4096, QImage.Format.Format_RGBA8888)
        ui.fill(QColor(80, 150, 110))
        rendered = QImage(256, 256, QImage.Format.Format_RGBA8888)
        rendered.fill(QColor(240, 200, 160))
        pixels = b'\x20\x40\x60\xff' * 4096
        source = {"kind": "rendered-dark-lugia", "shiny": False, "native_art_rect": [4, 4, 120]}
        recipe = {"tiles": [{"position": 0, "number": 0, "body": source}]}
        with patch.object(hd, "_rendered_body", return_value=(rendered, {})), \
             patch("orre_randomizer.engine.shadow_lugia_body.shadow_lugia_body_pixels", return_value=pixels):
            for binding in (None, "0" * 64):
                source["native_rgba_sha256"] = binding
                with self.assertRaisesRegex(hd._MissingHDAsset, "older pose or outline"):
                    hd._dna_hd(ui, recipe, {})
            source["native_rgba_sha256"] = hashlib.sha256(pixels).hexdigest()
            image, _ = hd._dna_hd(ui, recipe, {})
        self.assertEqual(image.pixelColor(3648, 64), QColor(240, 200, 160))
        self.assertEqual(image.pixelColor(3000, 1000), QColor(80, 150, 110))

    def test_pid_specific_spinda_gap_stays_explicit_and_blocks_hd_composition(self):
        reason = "The independent Spinda cell still requires specimen PID HD spot rendering."
        asset = {"hd": {"transform": {"type": "dna_cell", "runtime_gap": reason}}}
        self.assertEqual(hd._runtime_limitations([asset]), [reason])
        self.assertEqual(hd._runtime_limitations([{"hd": {"transform": {"type": "dna_cell"}}}]), [])
        with self.assertRaisesRegex(hd._MissingHDAsset, "Spinda"):
            hd._dna_hd(None, {"runtime_gap": reason}, {})

    def test_independent_cells_keep_nine_lugia_variants_additive(self):
        from orre_randomizer.engine import dna_keypad as dna, dna_hd_tiles as split
        from tests.test_dna_hd_tiles import dat_fixture
        native, fingerprint = dat_fixture()
        original = archive([(0x107E0200, "dnakey", native)])
        bodies = archive([(0x10101200, "body249", texture(64, 64, 16, b"\xfc\x00" * 4096)),
                          (0x10111200, "body249_c", texture(64, 64, 16, b"\x83\xe0" * 4096))])
        mapping = dict.fromkeys(dna.DNA_KEYPAD_SPECIES, (249, False))
        context = {"dna_lab": {str(old): {"species": 249, "shiny": False} for old in mapping}}
        with patch.object(dna, "_DAT_SHA256", hashlib.sha256(native).hexdigest()):
            generated = dna.patch_dna_keypad(original, bodies, mapping)
            raw = hd._raw_member(generated, hd.parse_fsys(generated)["members"][0])
            with patch.object(split, "STRUCTURAL_SHA256", fingerprint):
                independent, layout = split.split_keypad_dat(raw)
            with patch("orre_randomizer.artwork._disc_files", return_value={"DNA_key.fsys": original, "poke_body.fsys": bodies}), \
                 patch("orre_randomizer.engine.shadow_lugia_body.shadow_lugia_body_pixels",
                       side_effect=lambda shiny: bytes((30, 60 if shiny else 20, 220, 255)) * 4096):
                textures, recipes = hd._dna_cell_variants(independent, layout, Path("unused.iso"), context, None)
        self.assertEqual(len(textures), 36)
        self.assertTrue(all(r["transform"]["type"] == "dna_cell" for r in recipes.values()))
        self.assertTrue(all("runtime_gap" not in r["transform"] for r in recipes.values()))
        for index in range(9):
            self.assertEqual(sum(r["transform"]["cell"]["screen_index"] == index for r in recipes.values()), 4)

    def test_hd_cell_crop_preserves_native_uv_filtering_footprint(self):
        from PySide6.QtGui import QImage, QColor
        from orre_randomizer.engine.dna_hd_tiles import _layout
        cell = _layout()["cells"][0]
        image = QImage(4096, 4096, QImage.Format.Format_RGBA8888)
        image.fill(0)
        x, y = cell["crop_x"] * 4, cell["crop_y"] * 4
        image.setPixelColor(x, y, QColor(17, 29, 43, 255))
        image.setPixelColor(x + cell["width"] * 4 - 1, y + cell["height"] * 4 - 1, QColor(73, 83, 97, 255))
        result, sources = hd._dna_cell_hd(image, {"cell": cell, "tile": None}, {})
        self.assertEqual((result.width(), result.height()), (cell["width"] * 4, cell["height"] * 4))
        self.assertEqual(result.pixelColor(0, 0).getRgb(), (17, 29, 43, 255))
        self.assertEqual(result.pixelColor(result.width() - 1, result.height() - 1).getRgb(), (73, 83, 97, 255))
        self.assertEqual(sources, [])

    def test_deterministic_retained_shinies_bound_many_lugia_samples_to_one_runtime_state(self):
        from orre_randomizer.engine import dna_keypad as dna
        dat = bytearray(dna._KEYPAD_DAT_SIZE)
        struct.pack_into(">III", dat, dna._ATLAS_DESCRIPTOR, *dna._ATLAS_SIGNATURE)
        original = archive([(0x107E0200, "dnakey", bytes(dat))])
        bodies = archive([(0x10101200, "body249", texture(64, 64, 16, b"\xfc\x00" * 4096)),
                          (0x10111200, "body249_c", texture(64, 64, 16, b"\x83\xe0" * 4096))])
        mapping = dict.fromkeys(dna.DNA_KEYPAD_SPECIES, (249, True))
        context = {"dna_lab": {str(old): {"species": 249, "shiny": True} for old in mapping},
                   "asset_options": {"custom_shinies": True, "shiny_chance_percent": 100,
                                     "keep_shadow_lugia_after_purification": True}}
        with patch.object(dna, "_DAT_SHA256", hashlib.sha256(dat).hexdigest()):
            generated = dna.patch_dna_keypad(original, bodies, mapping)
            raw = hd._raw_member(generated, hd.parse_fsys(generated)["members"][0])
            atlas = hd._Texture(1024, 1024, 14, raw[0x7820:0x87820])
            with patch("orre_randomizer.artwork._disc_files", return_value={"DNA_key.fsys": original, "poke_body.fsys": bodies}), \
                 patch("orre_randomizer.engine.shadow_lugia_body.shadow_lugia_body_pixels",
                       side_effect=lambda shiny: bytes((30, 60 if shiny else 20, 220, 255)) * 4096):
                textures, recipes = hd._dna_variants(atlas, Path("unused.iso"), context, None)
        self.assertEqual(len(textures), 2)
        runtime = [r["transform"] for r in recipes.values() if "runtime_lugia_states" in r["transform"]]
        self.assertEqual(runtime[0]["runtime_lugia_states"], [1] * 9)
        self.assertNotIn("runtime_gap", runtime[0])

    def test_lugia_runtime_keys_cover_dark_shiny_and_purified_native_tiles(self):
        from orre_randomizer.engine import dna_keypad as dna
        dat = bytearray(dna._KEYPAD_DAT_SIZE)
        struct.pack_into(">III", dat, dna._ATLAS_DESCRIPTOR, *dna._ATLAS_SIGNATURE)
        original = archive([(0x107E0200, "dnakey", bytes(dat))])
        bodies = archive([(0x10101200, "body249", texture(64, 64, 16, b"\xfc\x00" * 4096)),
                          (0x10111200, "body249_c", texture(64, 64, 16, b"\x83\xe0" * 4096))])
        mapping = {old: (249 if index == 0 else old, False)
                   for index, old in enumerate(dna.DNA_KEYPAD_SPECIES)}
        context = {"dna_lab": {str(old): {"species": species, "shiny": shiny}
                               for old, (species, shiny) in mapping.items()}}
        with patch.object(dna, "_DAT_SHA256", hashlib.sha256(dat).hexdigest()):
            generated = dna.patch_dna_keypad(original, bodies, mapping)
            member = hd.parse_fsys(generated)["members"][0]
            raw = hd._raw_member(generated, member)
            atlas = hd._Texture(1024, 1024, 14, raw[0x7820:0x87820])
            with patch("orre_randomizer.artwork._disc_files", return_value={"DNA_key.fsys": original, "poke_body.fsys": bodies}), \
                 patch("orre_randomizer.engine.shadow_lugia_body.shadow_lugia_body_pixels",
                       side_effect=lambda shiny: bytes((30, 60 if shiny else 20, 220, 255)) * 4096):
                textures, recipes = hd._dna_variants(atlas, Path("unused.iso"), context, None)
        self.assertEqual(len(textures), 4)
        self.assertEqual(set(recipes), {hd._texture_key(t) for t in textures})
        self.assertEqual(sum(any(tile["body"]["kind"] == "rendered-dark-lugia"
                                 for tile in r["transform"]["tiles"]) for r in recipes.values()), 2)
        self.assertTrue(all("source_scale" not in r for r in recipes.values()))
        self.assertEqual(len({t.data for t in textures}), 4)

    def test_missing_true_dark_fullbody_capture_is_a_blocking_hd_gap(self):
        with patch.object(hd, "_rendered_body", side_effect=hd._MissingHDAsset("Missing real GPU HD capture")):
            from PySide6.QtGui import QImage
            ui = QImage(4096, 4096, QImage.Format.Format_RGBA8888)
            ui.fill(0)
            recipe = {"tiles": [{"position": 0, "number": 0,
                       "body": {"kind": "rendered-dark-lugia", "shiny": False}}]}
            with self.assertRaisesRegex(hd._MissingHDAsset, "GPU HD"):
                hd._dna_hd(ui, recipe, {})

if __name__ == "__main__":
    unittest.main()
