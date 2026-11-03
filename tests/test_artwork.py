"""Synthetic artwork/cache boundaries; optional local-ROM pixel attestation.

Fixtures contain solid mathematical colors, never distributed game imagery.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from colosseum_randomizer import artwork
from colosseum_randomizer.artwork import ArtworkError, extract_artwork, load_cached_artwork

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso"


def texture(width, height, fmt, payload):
    header = bytearray(128)
    struct.pack_into(">HHBB", header, 0, width, height, fmt, 1)
    struct.pack_into(">I", header, 8, {4: 0xb0, 16: 0x90, 32: 0x45}[fmt])
    struct.pack_into(">I", header, 0x28, 128)
    return bytes(header) + payload


def portrait(ordinary, shiny):
    blocks = bytearray()
    for by in range(0, 84, 4):
        for _ in range(11):
            colors = [ordinary if by + index // 4 < 42 else shiny for index in range(16)]
            blocks.extend(bytes(value for r, g, b, a in colors for value in (a, r)))
            blocks.extend(bytes(value for r, g, b, a in colors for value in (g, b)))
    return texture(42, 84, 32, blocks)


def fsys(members):
    data = bytearray(0x80 + len(members) * 0x30)
    data[:4] = b"FSYS"
    struct.pack_into(">I", data, 0xc, len(members))
    struct.pack_into(">I", data, 0x40, 0x60)
    for index, (name, payload) in enumerate(members):
        header = 0x80 + index * 0x30
        struct.pack_into(">I", data, 0x60 + index * 4, header)
        struct.pack_into(">I", data, header + 0x24, len(data))
        data.extend(name.encode("ascii") + b"\0")
        data.extend(b"\0" * (-len(data) % 32))
        for field, value in ((4, len(data)), (8, len(payload)), (0x14, len(payload))):
            struct.pack_into(">I", data, header + field, value)
        data.extend(payload)
    data.extend(b"FSYS")
    struct.pack_into(">I", data, 0x20, len(data))
    return bytes(data)


def iso_fixture(path):
    red_cmpr = struct.pack(">HH", 0xf800, 0) + b"\0" * 4
    title = fsys([("menu_042", texture(640, 480, 4, red_cmpr * (80 * 60 * 4)))])
    faces = fsys([(name, portrait(color, (240, 1, 2, 255))) for name, color in (
        ("face196", (11, 13, 17, 255)), ("face197", (19, 23, 29, 255)),
        ("face025", (31, 37, 41, 255)))])
    banner = bytearray(8096)
    banner[:4] = b"BNR2"
    banner[0x20:0x1820] = bytes.fromhex("83e0") * (96 * 32)
    files = [("title.fsys", title), ("poke_face.fsys", faces), ("opening.bnr", banner)]
    disc = bytearray(0x1000)
    disc[:8] = b"GC6P01\0\0"
    disc[0x1c:0x20] = bytes.fromhex("c2339f3d")
    names, entries = bytearray(), bytearray(struct.pack(">III", 0x01000000, 0, len(files) + 1))
    for name, payload in files:
        entries.extend(struct.pack(">III", len(names), len(disc), len(payload)))
        names.extend(name.encode("ascii") + b"\0")
        disc.extend(payload)
    fst = entries + names
    disc[0x440:0x440 + len(fst)] = fst
    struct.pack_into(">II", disc, 0x424, 0x440, len(fst))
    path.write_bytes(disc)
    return disc


def save_manifest(cache, manifest):
    (cache / "artwork-v1.json").write_text(json.dumps(manifest), encoding="utf-8")


def forged_image(cache, manifest, key, data):
    record = manifest["assets"][key]
    digest = hashlib.sha256(data).hexdigest()
    record.update(file=f"{key}-v1-{digest}.png", sha256=digest, bytes=len(data))
    (cache / record["file"]).write_bytes(data)
    save_manifest(cache, manifest)


class ArtworkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "private-source.iso"
        self.disc = iso_fixture(self.source)
        self.cache = self.root / "cache"

    def ready(self):
        paths = extract_artwork(self.source, self.cache)
        document = json.loads((self.cache / "artwork-v1.json").read_text("utf-8"))
        return paths, document

    def test_synthetic_disc_extracts_normal_portraits_without_source_change(self):
        before = self.source.stat().st_mtime_ns
        paths, manifest = self.ready()
        expected = {"background": (255, 0, 0, 255), "logo": (0, 255, 0, 255),
                    "espeon": (11, 13, 17, 255), "umbreon": (19, 23, 29, 255),
                    "pikachu": (31, 37, 41, 255)}
        self.assertEqual(set(paths), set(expected))
        for key, color in expected.items():
            dimensions = (manifest["assets"][key]["width"], manifest["assets"][key]["height"])
            self.assertEqual(artwork._png_pixels(paths[key].read_bytes(), dimensions),
                             bytes(color) * (dimensions[0] * dimensions[1]))
        self.assertEqual(load_cached_artwork(self.cache), paths)
        self.assertEqual(self.source.read_bytes(), self.disc)
        self.assertEqual(self.source.stat().st_mtime_ns, before)
        self.assertEqual(len(list(self.cache.iterdir())), 6)
        encoded = (self.cache / "artwork-v1.json").read_text("utf-8")
        self.assertNotIn(str(self.source), encoded)
        self.assertNotIn(self.source.name, encoded)

    def test_missing_cache_is_empty_and_does_not_create_directory(self):
        self.assertEqual(load_cached_artwork(self.cache), {})
        self.assertFalse(self.cache.exists())

    def test_cache_rejects_hash_corruption_and_missing_png(self):
        paths, _ = self.ready()
        original = paths["logo"].read_bytes()
        paths["logo"].write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaises(ArtworkError):
            load_cached_artwork(self.cache)
        paths["logo"].unlink()
        with self.assertRaises(ArtworkError):
            load_cached_artwork(self.cache)

    def test_cache_rejects_paths_versions_dimensions_and_unbounded_metadata(self):
        _, original = self.ready()
        documents = []
        for filename in ("../outside.png", str(self.source), "sub/image.png", "..\\outside.png"):
            value = deepcopy(original)
            value["assets"]["logo"]["file"] = filename
            documents.append(value)
        for key, value in (("width", 100000), ("height", True), ("bytes", artwork._MAX_PNG + 1),
                           ("sha256", "x" * 64)):
            document = deepcopy(original)
            document["assets"]["background"][key] = value
            documents.append(document)
        documents.extend([dict(original, version=999), dict(original, version=True),
                          dict(original, assets=[]), [], dict(original, source=str(self.source))])
        for document in documents:
            with self.subTest(document=document):
                save_manifest(self.cache, document)
                with self.assertRaises(ArtworkError):
                    load_cached_artwork(self.cache)
        (self.cache / "artwork-v1.json").write_bytes(b" " * (artwork._MAX_MANIFEST + 1))
        with self.assertRaises(ArtworkError):
            load_cached_artwork(self.cache)

    def test_even_matching_file_hash_cannot_hide_invalid_png_or_inflation_bomb(self):
        paths, original = self.ready()
        logo = paths["logo"].read_bytes()
        for data in (logo[:-2], logo + b"trailing", artwork._png((1, 1), bytes([1, 2, 3, 4]))):
            forged_image(self.cache, deepcopy(original), "logo", data)
            with self.assertRaises(ArtworkError):
                load_cached_artwork(self.cache)
        # Keep valid dimensions and CRCs while expanding beyond the pixel bound.
        import binascii
        compressed = zlib.compress(b"\0" * (32 * (96 * 4 + 1) + 1000))
        bomb = (logo[:33] + struct.pack(">I", len(compressed)) + b"IDAT" + compressed +
                struct.pack(">I", binascii.crc32(b"IDAT" + compressed) & 0xffffffff) + logo[-12:])
        forged_image(self.cache, deepcopy(original), "logo", bomb)
        with self.assertRaises(ArtworkError):
            load_cached_artwork(self.cache)

    def test_symlinked_cache_blob_cannot_read_outside_cache(self):
        paths, _ = self.ready()
        outside = self.root / "outside.png"
        outside.write_bytes(paths["logo"].read_bytes())
        paths["logo"].unlink()
        try:
            paths["logo"].symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this platform")
        with self.assertRaises(ArtworkError):
            load_cached_artwork(self.cache)
        self.assertTrue(outside.is_file())

    def test_atomic_manifest_failure_preserves_previous_cache_and_cleans_temps(self):
        paths, _ = self.ready()
        before = (self.cache / "artwork-v1.json").read_bytes()
        real_replace = artwork.os.replace

        def fail_manifest(source, target):
            if Path(target).name == "artwork-v1.json":
                raise OSError("Synthetic commit failure")
            return real_replace(source, target)

        with patch.object(artwork.os, "replace", side_effect=fail_manifest):
            with self.assertRaises(ArtworkError):
                extract_artwork(self.source, self.cache)
        self.assertEqual((self.cache / "artwork-v1.json").read_bytes(), before)
        self.assertEqual(load_cached_artwork(self.cache), paths)
        self.assertEqual(list(self.cache.glob(".artwork-*.tmp")), [])

    def test_source_named_like_manifest_cannot_be_overwritten(self):
        self.cache.mkdir()
        source = self.cache / "artwork-v1.json"
        source.write_bytes(self.disc)
        with self.assertRaisesRegex(ArtworkError, "overlaps"):
            extract_artwork(source, self.cache)
        self.assertEqual(source.read_bytes(), self.disc)

    def test_malformed_iso_and_fst_are_rejected_before_cache_creation(self):
        cases = [b"", self.disc[:0x430]]
        bad_id = bytearray(self.disc)
        bad_id[0] = 0
        cases.append(bad_id)
        for field, value in ((0x428, artwork._MAX_FST + 1), (0x424, len(self.disc) + 1),
                             (0x440 + 12 + 4, len(self.disc) + 1)):
            invalid = bytearray(self.disc)
            struct.pack_into(">I", invalid, field, value)
            cases.append(invalid)
        for index, invalid in enumerate(cases):
            with self.subTest(index=index):
                self.source.write_bytes(invalid)
                with self.assertRaises(ArtworkError):
                    extract_artwork(self.source, self.cache)
                self.assertFalse(self.cache.exists())

    def test_archive_member_and_texture_limits(self):
        with patch.object(artwork, "_MAX_ARCHIVE", 1024):
            with self.assertRaises(ArtworkError):
                extract_artwork(self.source, self.cache)
        with patch.object(artwork, "decompress_lzss") as decoder:
            with self.assertRaises(ArtworkError):
                artwork._member(b"", [{"name": "face196", "unpacked_size": artwork._MAX_MEMBER + 1}], "face196")
            decoder.assert_not_called()
        for raw in (b"", texture(2049, 1, 32, b"\0" * 64), texture(42, 84, 32, b"\0" * 64)):
            with self.assertRaises(ArtworkError):
                artwork._texture(raw, (42, 84))
        with self.assertRaises(ArtworkError):
            artwork._decode_pixels(2049, 1, 32, b"")

    def test_cmpr_uses_gamecube_blending_and_transparent_midpoint(self):
        block = struct.pack(">HH", 0xffff, 0) + b"\xaa" * 4
        self.assertEqual(artwork._decode_pixels(8, 8, 4, block * 4), bytes([159, 159, 159, 255]) * 64)
        transparent = struct.pack(">HH", 0, 0xffff) + b"\xff" * 4
        self.assertEqual(artwork._decode_pixels(8, 8, 4, transparent * 4), bytes([127, 127, 127, 0]) * 64)


class LocalOriginalArtworkTests(unittest.TestCase):
    @unittest.skipUnless(ORIGINAL.is_file(), "Local original ISO unavailable")
    def test_local_original_integrity_and_independently_attested_pixels(self):
        # Recorded by the private static decoder and visual inspection on 2026-10-31.
        expected = {
            "background": "19a3326829190acb754085bb5b3751cd18c6aa03dc5e7c9143a6ee9eb04a8d50",
            "logo": "b5754397d7d578c56360dfeeec1ce9f227080ca0784415770722779f3682cd1c",
            "espeon": "47c74b083337914bfd3cfc8bccaa21921e789e4127b5cb1de43b358a36f3b7cb",
            "umbreon": "e96e772e138fcf86b9349e4d4dc46aa036da688a37f7f7c4fc11ab2eebb68849",
            "pikachu": "a3d5f96c0c7e6104bebf59b9b071c2d5e80611a26a4595b65593951d2e29c42c"}
        before = (ORIGINAL.stat().st_size, ORIGINAL.stat().st_mtime_ns)
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            paths = extract_artwork(ORIGINAL, cache)
            self.assertEqual(load_cached_artwork(cache), paths)
            for key, digest in expected.items():
                pixels = artwork._png_pixels(paths[key].read_bytes(), artwork._DIMENSIONS[key])
                self.assertEqual(hashlib.sha256(pixels).hexdigest(), digest, key)
            self.assertLess(sum(path.stat().st_size for path in paths.values()), 100000)
        self.assertEqual((ORIGINAL.stat().st_size, ORIGINAL.stat().st_mtime_ns), before)
        digest = hashlib.sha256()
        with ORIGINAL.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        self.assertEqual(digest.hexdigest(), "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9")


if __name__ == "__main__":
    unittest.main()
