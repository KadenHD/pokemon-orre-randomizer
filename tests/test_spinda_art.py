import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.colo_spinda_field import mark_spinda_starter_actor
from orre_randomizer.engine.spinda_art import spinda_face_texture


def _retail_texture(size, pixels):
    header = bytearray(128)
    struct.pack_into(">HHBBHI", header, 0, size, size, 16, 1, 0, 0x44)
    struct.pack_into(">I", header, 0x28, 128)
    return bytes(header) + pixels


class SpindaArtTests(unittest.TestCase):
    def test_native_pid_nibbles_and_row_wrapping(self):
        face = _retail_texture(128, b"\xe6\x98" * (128 * 128))
        stamp = _retail_texture(32, b"\xfa\xcc" + bytes((32 * 32 - 1) * 2))

        def spots(pid):
            pixels = spinda_face_texture(face, stamp, pid)
            return {(tile % 32 * 4 + index % 4, tile // 32 * 4 + index // 4)
                    for tile in range(32 * 32) for index in range(16)
                    if struct.unpack_from(">H", pixels, (tile * 16 + index) * 2)[0] == 0xFACC}

        self.assertEqual(spots(0x88888888), {(6, 7), (91, 6), (30, 65), (68, 65)})
        self.assertEqual(spots(0x888888B2), {(114, 16), (91, 6), (30, 65), (68, 65)})

    def test_malformed_native_texture_is_rejected(self):
        with self.assertRaises(FormatError):
            spinda_face_texture(bytes(32768 + 128), bytes(2048 + 128), 0)

    def test_motorcycle_marker_preserves_the_dat_and_requires_the_spinda_face(self):
        model = bytearray(0x54F40)
        model[0x14:0x18] = b"HSD0"
        struct.pack_into(">III", model, 0x3FD4, 0x4CF20, 0x00800080, 4)
        marked = mark_spinda_starter_actor(bytes(model), 1, 0xAABBCCDD, True)
        self.assertEqual(marked[:0x18], model[:0x18])
        self.assertEqual(marked[0x18:0x20], bytes.fromhex("53504E43 AABBCCDD"))
        self.assertEqual(marked[0x20:], model[0x20:])
        with self.assertRaises(FormatError):
            mark_spinda_starter_actor(marked, 1, 0xAABBCCDD, True)
