import unittest
from unittest.mock import patch
import struct
from pathlib import Path

from orre_randomizer.artwork import _decode_pixels
from orre_randomizer.engine.dna_keypad import (
    DNA_KEYPAD_SPECIES, _SPINDA_ART_RECT, _SPINDA_BODY_ART_RECT, _body_pixels,
    _tile_art, _tile_rows, _TILE_ORIGINS, patch_dna_keypad, _CUSTOM_BODY_ART_RECT,
)
from orre_randomizer.engine.dna_keypad_runtime import _sample_offsets
from orre_randomizer.engine.unown_form import unown_suffix
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys
from orre_randomizer.engine.rebuild_iso import decoded_member


class DnaKeypadTests(unittest.TestCase):
    def test_identity_mapping_preserves_original_keypad(self):
        original = b"original keypad"
        mapping = {species: (species, False) for species in DNA_KEYPAD_SPECIES}
        self.assertEqual(patch_dna_keypad(original, b"", mapping), original)

    def test_tile_keeps_the_entire_body_alpha_bevel_and_duplicate_number(self):
        green = bytes((0, 255, 0, 255))
        blue = bytes((0, 0, 255, 255))
        red = bytes((255, 0, 0, 255))
        template = green * (128 * 128)
        body = bytearray(64 * 64 * 4)
        for y in range(8, 56):
            for x in range(16, 48):
                at = (y * 64 + x) * 4
                body[at:at+4] = red if y < 32 else blue

        def pixel(tile, x, y):
            index = (y * 128 + x) * 4
            return tile[index:index + 4]

        normal = _decode_pixels(128, 128, 4, _tile_art(template, body, 64, 64, 0))
        marked = _decode_pixels(128, 128, 4, _tile_art(template, body, 64, 64, 1))
        self.assertEqual(pixel(normal, 64, 32), red)
        self.assertEqual(pixel(marked, 64, 88), blue)
        self.assertEqual(pixel(normal, 16, 64), green)
        self.assertEqual(pixel(normal, 0, 64), green)
        self.assertEqual(pixel(normal, 111, 99), green)
        self.assertEqual(pixel(marked, 111, 99), b"\xff\xff\xff\xff")

    def test_native_body_lookup_uses_shiny_image_and_all_unown_forms(self):
        def texture(word):
            raw = bytearray(128 + 64 * 64 * 2)
            struct.pack_into('>HHBBHI', raw, 0, 64, 64, 16, 1, 0, 0x90)
            struct.pack_into('>I', raw, 0x28, 128)
            raw[128:] = struct.pack('>H', word) * (64 * 64)
            return bytes(raw)
        normal, shiny = texture(0xFC00), texture(0x801F)
        members = {}
        for index in range(28):
            name = f'body201{unown_suffix(index)}'
            members[name] = {'data': normal}
            members[name + '_c'] = {'data': shiny}
        members['face249'] = {'data': normal}
        with patch('orre_randomizer.engine.dna_keypad.decoded_member', side_effect=lambda _, member: member['data']):
            for index in range(28):
                self.assertEqual(_body_pixels(b'', members, 201, False, index), b'\xff\0\0\xff' * 4096)
                self.assertEqual(_body_pixels(b'', members, 201, True, index), b'\0\0\xff\xff' * 4096)
            with self.assertRaisesRegex(FormatError, 'full-body'):
                _body_pixels(b'', members, 249, False)

    def test_custom_body_uses_more_of_the_key_without_changing_the_bevel(self):
        template = b'\0\xff\0\xff' * (128 * 128)
        body = bytes(channel for y in range(64) for x in range(64)
                     for channel in ((255, 0, 0, 255) if 2 <= x < 62 and 2 <= y < 62 else (0, 0, 0, 0)))
        retail = _decode_pixels(128, 128, 4, _tile_art(template, body, 64, 64, 0))
        custom = _decode_pixels(128, 128, 4, _tile_art(template, body, 64, 64, 0, rect=_CUSTOM_BODY_ART_RECT))
        def red_area(image):
            return sum(r > 200 and g < 30 for r, g, _b, _a in zip(*[iter(image)] * 4))
        self.assertGreater(red_area(custom), red_area(retail) * 1.1)
        for y in range(128):
            for x in range(128):
                if min(x, y, 127 - x, 127 - y) < 4:
                    at = (y * 128 + x) * 4
                    self.assertEqual(custom[at:at + 4], retail[at:at + 4])

    def test_atypical_retail_body_dimensions_keep_both_corners_and_their_proportions(self):
        for width, height, fitted in ((64, 59, (0, 2, 64, 59)), (64, 68, (2, 0, 60, 64)),
                                      (58, 58, (3, 3, 58, 58)), (64, 63, (0, 0, 64, 63))):
            with self.subTest(size=(width, height)):
                source = bytearray(b'\xff\0\0\xff' * (width * height))
                source[:4], source[-4:] = b'\0\0\xff\xff', b'\0\xff\0\xff'
                with patch('orre_randomizer.engine.dna_keypad.decoded_member', return_value=struct.pack('>HH', width, height)), \
                        patch('orre_randomizer.engine.dna_keypad._texture', return_value=bytes(source)):
                    actual = _body_pixels(b'', {'body108': {}}, 108, False)
                left, top, fitted_width, fitted_height = fitted
                first = (top * 64 + left) * 4
                last = ((top + fitted_height - 1) * 64 + left + fitted_width - 1) * 4
                self.assertEqual(actual[first:first+4], b'\0\0\xff\xff')
                self.assertEqual(actual[last:last+4], b'\0\xff\0\xff')
                self.assertEqual(sum(alpha > 0 for alpha in actual[3::4]), fitted_width * fitted_height)

    def test_body_alpha_blends_with_the_native_background(self):
        template = b'\0\xff\0\xff' * (128 * 128)
        body = b'\xff\0\0\x80' * (64 * 64)
        pixels = _decode_pixels(128, 128, 4, _tile_art(template, body, 64, 64, 0))
        at = (64 * 128 + 64) * 4
        for actual, expected in zip(pixels[at:at+3], (128, 127, 0), strict=True):
            self.assertLessEqual(abs(actual - expected), 5)
        self.assertEqual(pixels[:4], b'\0\xff\0\xff')

    def test_spinda_mask_samples_native_texels_without_covering_the_tile_number(self):
        left, top, size = _SPINDA_ART_RECT
        self.assertEqual((left % 8, top % 8, size % 8), (0, 0, 0))
        self.assertLessEqual(top + size, 124)
        self.assertLessEqual(left + size, 102)

        # Simulate the native RGB565 layout with a white box over a black face.
        # Interpret the sampled bytes as CMPR selectors to check both layouts.
        native_white = set()
        for y in range(12, 28):
            for x in range(32, 64):
                block = y // 4 * 32 + x // 4
                native_white.add((block * 16 + y % 4 * 4 + x % 4) * 2)
        encoded = bytearray()
        offsets = _sample_offsets()
        for index in range(0, len(offsets), 16):
            selectors = 0
            for offset in offsets[index:index + 16]:
                selectors = selectors << 2 | int(offset not in native_white)
            encoded.extend(b"\xff\xff\x00\x00" + selectors.to_bytes(4, "big"))
        actual = _decode_pixels(size, size, 4, encoded)
        expected = b"".join(
            b"\xff\xff\xff\xff" if 12 <= y * 128 // size < 28 and 32 <= x * 128 // size < 64 else b"\0\0\0\xff"
            for y in range(size) for x in range(size)
        )
        self.assertEqual(actual, expected)

    def test_native_spinda_full_body_does_not_touch_its_pid_inset_or_number(self):
        path = Path(__file__).resolve().parents[1] / 'game/files/poke_body.fsys'
        if not path.exists():
            self.skipTest('requires the original local full-body archive')
        source = path.read_bytes()
        members = {row['name']: row for row in parse_fsys(source)['members']}
        left, top, size = _SPINDA_BODY_ART_RECT
        for shiny in (False, True):
            with self.subTest(shiny=shiny):
                pixels = _body_pixels(source, members, 308, shiny)
                self.assertEqual(size, 112)
                for target_left, target_top, target_width, target_height in ((8, 88, 32, 32), (102, 96, 21, 27)):
                    for y in range(target_top, target_top + target_height):
                        for x in range(target_left, target_left + target_width):
                            if left <= x < left + size and top <= y < top + size:
                                old = (((y - top) * 64 // size) * 64 + (x - left) * 64 // size) * 4
                                self.assertEqual(pixels[old + 3], 0, (shiny, x, y))

    def test_native_keypad_roundtrip_keeps_every_non_tile_byte_and_other_member(self):
        folder = Path(__file__).resolve().parents[1] / 'game/files'
        if not all((folder / name).exists() for name in ('DNA_key.fsys', 'poke_body.fsys')):
            self.skipTest('requires the original local keypad and full-body archives')
        original, bodies = ((folder / name).read_bytes() for name in ('DNA_key.fsys', 'poke_body.fsys'))
        replacements = (25, 277, 249, 287, 108, 201, 308, 181, 227)
        mapping = {old: (new, index % 2 == 0)
                   for index, (old, new) in enumerate(zip(DNA_KEYPAD_SPECIES, replacements, strict=True))}
        output = patch_dna_keypad(original, bodies, mapping, unown_form_index=27, spinda_samples={153: ()})
        old_members = parse_fsys(original)['members']
        new_members = parse_fsys(output)['members']
        self.assertEqual([member['identifier_raw'] for member in old_members],
                         [member['identifier_raw'] for member in new_members])
        for before, after in zip(old_members, new_members, strict=True):
            old_data, new_data = decoded_member(original, before), decoded_member(output, after)
            if before['identifier_raw'] != '0x107e0200':
                self.assertEqual(old_data, new_data)
                continue
            allowed = set(range(0x18, 0x1C))
            for position, old in enumerate(DNA_KEYPAD_SPECIES):
                species, shiny = mapping[old]
                if species != old or shiny:
                    for start, end in _tile_rows(*_TILE_ORIGINS[position]):
                        allowed.update(range(start, end))
            self.assertEqual(len(old_data), len(new_data))
            self.assertTrue({index for index, (a, b) in enumerate(zip(old_data, new_data)) if a != b} <= allowed)
        self.assertEqual((folder / 'DNA_key.fsys').read_bytes(), original)
        self.assertEqual((folder / 'poke_body.fsys').read_bytes(), bodies)
