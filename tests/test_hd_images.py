"""Actual PNG/DDS donors, native dimensions and mipmap-name compatibility."""
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from orre_randomizer.hd_images import load_texture, resolve_texture


class HDImages(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_dds_decodes_level_zero_with_scale_and_source_hash(self):
        path = self.root / "tex1_8x8_abc_14.dds"
        Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(path, pixel_format="DXT1")
        loaded = load_texture(path, expected_native_size=(8, 8))
        self.assertEqual(loaded.image.pixelColor(10, 10).getRgb(), (255, 0, 0, 255))
        self.assertEqual(loaded.metadata["source_scale"], 4)
        self.assertEqual(loaded.metadata["format"], "DDS")
        self.assertEqual(len(loaded.metadata["sha256"]), 64)
        self.assertEqual(loaded.metadata["mip_levels"], 1)

    def test_resolver_accepts_format_case_and_mipmap_alias(self):
        path = self.root / "TEX1_8x8_m_abc_14.DDS"
        Image.new("RGBA", (32, 32)).save(path, format="DDS")
        self.assertEqual(resolve_texture(self.root, "tex1_8x8_abc_14.png"), path)
        self.assertEqual(resolve_texture(self.root, "tex1_8x8_m_abc_14.png"), path)
        with self.assertRaises(FileNotFoundError):
            resolve_texture(self.root, "tex1_8x8_def_14.png")
        with self.assertRaises(ValueError):
            resolve_texture(self.root, "../tex1_8x8_abc_14.png")

    def test_png_preserves_alpha_and_rejects_wrong_native_dimensions(self):
        path = self.root / "tex1_8x8_abc_6.png"
        Image.new("RGBA", (32, 32), (10, 20, 30, 72)).save(path)
        self.assertEqual(load_texture(path).image.pixelColor(0, 0).alpha(), 72)
        with self.assertRaises(ValueError):
            load_texture(path, expected_native_size=(8, 4))
        with self.assertRaises(ValueError):
            load_texture(path, expected_native_size=(8, 8), max_scale=2)

    def test_ambiguous_donors_and_truncated_dds_fail(self):
        stem = "tex1_8x8_abc_14"
        (self.root / (stem + ".dds")).write_bytes(b"DDS ")
        (self.root / (stem + ".png")).write_bytes(b"bad")
        with self.assertRaises(ValueError):
            resolve_texture(self.root, stem + ".png")
        with self.assertRaises(ValueError):
            load_texture(self.root / (stem + ".dds"))
