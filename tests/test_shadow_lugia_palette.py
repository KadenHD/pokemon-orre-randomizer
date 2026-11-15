"""Verify the custom Shadow palette changes authored colors, never identity/geometry."""
import hashlib
import json
from pathlib import Path
import struct
import unittest

from orre_randomizer.artwork import _png_pixels, _decode_pixels
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.shadow_lugia_palette import (
    VERSION, make_shadow_lugia_shiny, make_shadow_lugia_shiny_dat, make_shadow_lugia_portrait,
)

DARK = bytes.fromhex('191933ff666680ff595973ff')
PALE = bytes.fromhex('b3b3b3ffffffffffffffffff')


def fixture(xd):
    data = bytearray(0x600)
    pointers = {0: 0x10, 0x10: 0x20, 0x20: 0x40, 0x50: 0x80,
                0x84: 0xA0, 0x88: 0xC0, 0xA8: 0xD0, 0xCC: 0x100, 0xDC: 0x120,
                0xD8: 0x200, 0x24C: 0x260, 0x260: 0x300}
    for at, value in pointers.items():
        struct.pack_into('>I', data, at, value)
    data[0x100:0x10C], data[0x120:0x12C] = DARK, PALE
    data[0x150:0x154] = bytes((231, 25, 42, 127))  # unrelated red-eye sample
    struct.pack_into('>HHIIff', data, 0x264, 32, 32, 14, 0, 0., 0.)
    data[0x300:0x500] = struct.pack('>HH4B', 0xFFFF, 0xBDF7, 0x1B, 0x1B, 0x1B, 0x1B)*64
    # First opaque block collapses after darkening; a transparent block retains
    # its three-color+alpha mode. Both must keep their original alpha mask.
    struct.pack_into('>HH4B', data, 0x300, 0xFFFF, 0xFFFE, 255, 255, 255, 255)
    struct.pack_into('>HH4B', data, 0x308, 0, 0xFFFF, 255, 255, 255, 255)
    relocations = struct.pack(f'>{len(pointers)}I', *pointers)
    name = b'scene_data\0'
    length = 0x20+len(data)+len(relocations)+8+len(name)
    dat = struct.pack('>5I12x', length, len(data), len(pointers), 1, 0)+data+relocations+bytes(8)+name
    header = bytearray(0xE60 if xd else 0x40)
    struct.pack_into('>I', header, 0, length)
    container = bytes(header)+dat+bytes(-len(dat) % 32)+b'native-animation-schedule'
    return container, len(header)+0x20


class ShadowLugiaPaletteTests(unittest.TestCase):
    def test_authored_field_dat_has_the_same_color_only_conversion_as_its_pkx(self):
        for xd in (False, True):
            source, data = fixture(xd)
            start = data - 0x20
            dat = source[start:]
            self.assertEqual(make_shadow_lugia_shiny_dat(dat),
                             make_shadow_lugia_shiny(source, xd=xd)[start:])
            self.assertEqual(len(make_shadow_lugia_shiny_dat(dat)), len(dat))
        for invalid in (b"", bytes(0x20), dat[:0x30]):
            with self.assertRaises(FormatError):
                make_shadow_lugia_shiny_dat(invalid)

    def test_both_container_layouts_change_only_body_belly_colors_and_belly_map(self):
        for xd in (False, True):
            with self.subTest(xd=xd):
                source, start = fixture(xd)
                output = make_shadow_lugia_shiny(source, xd=xd)
                self.assertEqual(len(output), len(source))
                self.assertEqual(output[start+0x100:start+0x10C], PALE)
                self.assertEqual(output[start+0x120:start+0x12C], DARK)
                allowed = {*range(start+0x100, start+0x10C), *range(start+0x120, start+0x12C),
                           *range(start+0x300, start+0x500)}
                self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(source, output))))
                self.assertEqual(output[start+0x150:start+0x154], bytes((231, 25, 42, 127)))
                self.assertEqual(output[-25:], source[-25:])
                before = _decode_pixels(32, 32, 4, source[start+0x300:start+0x500])
                after = _decode_pixels(32, 32, 4, output[start+0x300:start+0x500])
                self.assertEqual(before[3::4], after[3::4])
                self.assertLess(max(v for i, v in enumerate(after) if i % 4 != 3), 64)

    def test_unknown_or_truncated_materials_are_rejected(self):
        source, start = fixture(False)
        wrong = bytearray(source)
        wrong[start+0x100] ^= 1
        for model in (bytes(12), source[:0x45], bytes(wrong)):
            with self.subTest(length=len(model)), self.assertRaises(FormatError):
                make_shadow_lugia_shiny(model, xd=False)

    def test_cmpr_alpha_survives_endpoint_ties_and_color_order_changes(self):
        for first, second in ((0, 0), (0xFFFF, 0xFFFF), (0xFFFF, 0xFFFE),
                              (0x8000, 0x7FFF), (0x7FFF, 0x8000),
                              (0x0840, 0x07FF), (0x07FF, 0x0840),
                              (0, 0xFFFF), (0xFFFF, 0)):
            with self.subTest(first=first, second=second):
                source, start = fixture(False)
                source = bytearray(source)
                source[start+0x300:start+0x500] = struct.pack('>HH4B', first, second, 0x1B, 0x1B, 0x1B, 0x1B)*64
                output = make_shadow_lugia_shiny(bytes(source), xd=False)
                before = _decode_pixels(32, 32, 4, source[start+0x300:start+0x500])
                after = _decode_pixels(32, 32, 4, output[start+0x300:start+0x500])
                self.assertEqual(before[3::4], after[3::4])

    def test_generic_color_pass_keeps_red_iris_neutral_whites_black_lines_and_alpha(self):
        source = bytes((231, 25, 42, 255, 245, 245, 245, 255, 0, 0, 0, 255,
                        50, 52, 98, 255, 100, 105, 170, 128, 50, 52, 98, 0))
        output = make_shadow_lugia_portrait(source)
        self.assertEqual(output[:12], source[:12])
        self.assertEqual(output[-4:], source[-4:])
        self.assertEqual(output[3::4], source[3::4])
        self.assertEqual(output[12], output[13])
        self.assertEqual(output[13], output[14])
        self.assertLess(output[12], output[16])
        self.assertGreater(output[12], source[14])
        with self.assertRaises(ValueError):
            make_shadow_lugia_portrait(bytes(3))

    def test_native_portrait_background_border_and_red_iris_stay_exact(self):
        path = Path(__file__).resolve().parents[1]/'orre_randomizer/assets/game/models/dark-lugia.png'
        if not path.exists():
            self.skipTest('optional game resource pack is not present')
        source = _png_pixels(path.read_bytes(), (42, 42))
        output = make_shadow_lugia_portrait(source)
        known_native_backgrounds = {(82, 24, 107, 255)}
        protected = 0
        for y in range(42):
            for x in range(42):
                at = (y*42+x)*4
                pixel = tuple(source[at:at+4])
                # The eye-mask anatomy extends to the right crop edge.
                border = x in (0, 41) or y in (0, 41)
                anatomy_edge = x == 41 and 12 <= y <= 29
                if (border and not anatomy_edge) or pixel in known_native_backgrounds or not pixel[3] or pixel[0] > pixel[2]+20:
                    self.assertEqual(source[at:at+4], output[at:at+4])
                    protected += 1
        self.assertGreater(protected, 350)
        def color(pixels, x, y):
            at = (y*42+x)*4
            return tuple(pixels[at:at+4])
        self.assertEqual(color(source, 25, 14), color(output, 25, 14))  # red iris
        self.assertGreater(color(source, 35, 10)[0], 200)
        self.assertLess(max(color(output, 35, 10)[:3]), 48)  # dark material triangle
        self.assertGreater(color(output, 30, 5)[0], 200)  # white body forehead
        self.assertLess(color(source, 37, 25)[0], 64)
        self.assertGreater(color(output, 37, 25)[0], 190)  # body neck, not backdrop
        self.assertEqual(color(source, 28, 32), color(output, 28, 32))  # violet gap
        self.assertGreater(color(output, 16, 39)[0], 190)  # thin lower jaw
        for at in range(24*42*4, len(source), 4):
            r, g, b, _ = source[at:at+4]
            if r == g == b or r > b+20:  # white teeth and red mouth, not blue head shading
                self.assertEqual(source[at:at+4], output[at:at+4])

    def test_optional_original_model_and_face_match_reproducible_manifest(self):
        pack = Path(__file__).resolve().parents[1]/'orre_randomizer/assets/game/models'
        source_path = pack/'dark-lugia-colosseum-v1.pkx'
        if not source_path.exists():
            self.skipTest('optional game resource pack is not present')
        source = source_path.read_bytes()
        output = make_shadow_lugia_shiny(source, xd=False)
        manifest = json.loads((pack/'manifest.json').read_text('utf-8'))['shiny_variant']
        self.assertEqual(manifest['version'], VERSION)
        self.assertEqual(len(output), manifest['generated_bytes'])
        self.assertEqual(hashlib.sha256(output).hexdigest(), manifest['generated_sha256'])
        self.assertGreater(sum(a != b for a, b in zip(source, output)), 18)
        start = 0x40+0x20
        allowed = {*range(start+0x6E0C, start+0x6E18), *range(start+0x6EAC, start+0x6EB8),
                   *range(start+0x4C5E0, start+0x4C7E0)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(source, output))))
        before = _decode_pixels(32, 32, 4, source[start+0x4C5E0:start+0x4C7E0])
        after = _decode_pixels(32, 32, 4, output[start+0x4C5E0:start+0x4C7E0])
        self.assertEqual(before[3::4], after[3::4])
        face = (pack/'dark-lugia.png').read_bytes()
        rare = (pack/'dark-lugia-shiny.png').read_bytes()
        self.assertEqual(hashlib.sha256(rare).hexdigest(), manifest['portrait_sha256'])
        self.assertEqual(_png_pixels(rare, (42, 42)),
                         make_shadow_lugia_portrait(_png_pixels(face, (42, 42))))


if __name__ == '__main__':
    unittest.main()
