import random
import struct
import unittest

from orre_randomizer.engine.spinda_art import _SPOT_ORDER, _FACE_ORDER, spinda_face_texture
from orre_randomizer.engine.spinda_diagram import diagram_layer, cmpr_layer, spot_origin, TEXTURE_BYTES
from orre_randomizer.hd_overlays import _Texture, _pixels, dolphin_texture_name


def retail(size, pixels, order):
    header = bytearray(128)
    struct.pack_into(">HHBBHI", header, 0, size, size, 16, 1, 0, 0x44)
    struct.pack_into(">I", header, 0x28, 128)
    return bytes(header) + struct.pack(f">{size*size}H", *(pixels[p] for p in order))


class SpindaDiagramTests(unittest.TestCase):
    def setUp(self):
        self.background = 0xA300
        self.face = retail(128, [self.background] * 16384, _FACE_ORDER)
        # Deliberately asymmetric stamp with below/equal/above background colours.
        self.spot = retail(32, [0xB100 if (x * 7 + y * 11) % 13 < 7 else
                              self.background if (x + y) % 2 else 0x9300
                              for y in range(32) for x in range(32)], _SPOT_ORDER)

    def test_all_1024_byte_positions_match_native_linear_row_bounds(self):
        for index in range(4):
            for value in range(256):
                actual = diagram_layer(self.spot, self.background, index, value)
                # Independent direct native loop; it must retain row-start checks
                # and carry x across the 128-pixel row, including negative x.
                origin = ((6, 7), (91, 6), (30, 65), (68, 65))[index]
                x = origin[0] + int(((value & 15) - 8) * 3.4)
                y = origin[1] + int(((value >> 4) - 8) * 3.4)
                expected = bytearray(1024)
                for row in range(32):
                    start = (y + row) * 128 + x
                    if not 0 <= start < 16384:
                        continue
                    for col in range(32):
                        target = start + col
                        if target < 16384 and target % 4 == 0 and target // 128 % 4 == 0:
                            expected[target // 512 * 32 + target % 128 // 4] |= int((col * 7 + row * 11) % 13 < 7)
                self.assertEqual(actual, bytes(expected), (index, value))
                self.assertEqual(spot_origin(index, value), (x, y))

    def test_four_layers_union_matches_original_full_face_writer(self):
        rng = random.Random(873921)
        for pid in [0, 0xFFFFFFFF, 0x88888888, 0x888888B2, *[rng.getrandbits(32) for _ in range(100)]]:
            tiled = struct.unpack(">16384H", spinda_face_texture(self.face, self.spot, pid))
            linear = [0] * 16384
            for position, value in zip(_FACE_ORDER, tiled):
                linear[position] = value
            expected = bytes(int(linear[y * 128 + x] != self.background)
                             for y in range(0, 128, 4) for x in range(0, 128, 4))
            layers = [diagram_layer(self.spot, self.background, i, pid >> (i * 8) & 255) for i in range(4)]
            self.assertEqual(bytes(int(any(values)) for values in zip(*layers)), expected)

    def test_native_cmpr_clamp_rim_is_transparent_and_ink_is_exact(self):
        mask = bytes(int((x + y) % 3 == 0) for y in range(32) for x in range(32))
        encoded = cmpr_layer(mask, 0xFACC)
        self.assertEqual(len(encoded), TEXTURE_BYTES)
        rgba = _pixels(_Texture(40, 40, 14, encoded))
        for y in range(40):
            for x in range(40):
                lit = 4 <= x < 36 and 4 <= y < 36 and mask[(y - 4) * 32 + x - 4]
                self.assertEqual(rgba[(y * 40 + x) * 4 + 3], 255 if lit else 0)
                if lit:
                    self.assertEqual(rgba[(y * 40 + x) * 4:(y * 40 + x) * 4 + 3], bytes((255, 89, 99)))

    def test_invisible_identity_prevents_pid_aliases_without_changing_visible_pixels(self):
        mask = bytes([1]) * 1024
        first, second = (cmpr_layer(mask, 0xFACC, identity=value) for value in (1, 2048))
        self.assertNotEqual(first, second)
        a, b = (_pixels(_Texture(40, 40, 14, raw)) for raw in (first, second))
        self.assertEqual(a[3::4], b[3::4])
        self.assertEqual(a, b)  # Hidden RGB is also invariant under LINEAR filtering.
        self.assertEqual(a[:4], bytes((127,127,127,0)))
        for identity in (32,255,256,1024,4096,4097):
            raw=cmpr_layer(mask,0xFACC,identity=identity)
            self.assertEqual(_pixels(_Texture(40,40,14,raw)),a)

    def test_all_2048_distinct_invisible_keys_remain_finite_even_for_identical_masks(self):
        mask=bytes([1])*1024
        keys={dolphin_texture_name(40,40,14,cmpr_layer(mask,0xFACC,identity=identity))
              for identity in range(1,2049)}
        self.assertEqual(len(keys),2048)

    def test_pid_components_reject_invalid_indices_types_and_values(self):
        for args in ((-1, 0), (4, 0), (True, 0), (0, -1), (0, 256), (0, True)):
            with self.assertRaises(ValueError):
                spot_origin(*args)


if __name__ == "__main__":
    unittest.main()
