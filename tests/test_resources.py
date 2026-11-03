"""The shipped interface pack works without a selected ROM or user cache."""
import hashlib
import json
import unittest
import tempfile
import struct
from pathlib import Path
from unittest.mock import patch
from colosseum_randomizer.resources import application_icon, bundle_root, interface_assets, menu_icon, music_track


class ResourceTests(unittest.TestCase):
    def test_application_icon_is_available_without_game_data_and_contains_all_sizes(self):
        path = application_icon()
        self.assertIsNotNone(path)
        data = path.read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", data)
        self.assertEqual((reserved, kind, count), (0, 1, 9))
        sizes = []
        for index in range(count):
            w, h, _, _, planes, depth, length, offset = struct.unpack_from("<BBBBHHII", data, 6+16*index)
            self.assertEqual(w, h)
            self.assertEqual((planes, depth), (1, 32))
            payload = data[offset:offset+length]
            self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(len(payload), length)
            sizes.append(w or 256)
        self.assertEqual(sizes, [16, 20, 24, 32, 40, 48, 64, 128, 256])
        manifest = json.loads(path.with_name("provenance.json").read_text("utf-8"))
        for name, expected in manifest["files"].items():
            payload = path.with_name(name).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), expected["sha256"])
            self.assertEqual(len(payload), expected["bytes"])

    @unittest.skipUnless((bundle_root()/"provenance.json").is_file(), "local game interface pack is not distributed publicly")
    def test_complete_pack_matches_its_recorded_hashes(self):
        root = bundle_root()
        document = json.loads((root/"provenance.json").read_text("utf-8"))
        expected = document["files"]
        self.assertEqual({p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()},
                         set(expected) | {"provenance.json"})
        for name, record in expected.items():
            path = root/name
            self.assertTrue(path.resolve().is_relative_to(root))
            self.assertNotIn(path.suffix, {".iso", ".rvz", ".fsys", ".dol", ".rel", ".raw", ".sav"})
            self.assertEqual(path.stat().st_size, record["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])
        images, sounds = interface_assets()
        self.assertEqual(set(images), {"background", "logo", "espeon", "umbreon", "pikachu"})
        self.assertEqual(set(sounds), {"move", "confirm", "back"})
        self.assertIsNotNone(music_track())
        self.assertIsNotNone(menu_icon())

    def test_public_edition_starts_with_no_game_pack(self):
        with tempfile.TemporaryDirectory() as folder, patch("colosseum_randomizer.resources.bundle_root", return_value=Path(folder)):
            self.assertEqual(interface_assets(), ({}, {}))
            self.assertIsNone(music_track())
            self.assertIsNone(menu_icon())
            self.assertIsNotNone(application_icon())

    def test_malformed_optional_metadata_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder, patch("colosseum_randomizer.resources.bundle_root", return_value=Path(folder)):
            root = Path(folder)
            for directory, filename in (("music", "track.json"), ("interface", "icon.json")):
                (root/directory).mkdir()
            (root/"music/title.wav").write_bytes(bytes(44))
            (root/"interface/pokeball.png").write_bytes(bytes(44))
            for value in ("{broken", "[]", "null", "3", '{"bytes": null}', '{"bytes": 44}'):
                for directory, filename in (("music", "track.json"), ("interface", "icon.json")):
                    (root/directory/filename).write_text(value, encoding="utf-8")
                with self.subTest(value=value):
                    self.assertIsNone(music_track())
                    self.assertIsNone(menu_icon())
