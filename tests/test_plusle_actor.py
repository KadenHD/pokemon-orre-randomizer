"""Verify that the field actor keeps a valid HSD motion table after replacement."""

from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.plusle_actor import _field_model, load_actor_model, patch_actor
from orre_randomizer.engine.rebuild_iso import decoded_member


def _model_fixture():
    data = bytearray(0x40)
    # Public scene -> model list -> model -> joint and material motions.
    for offset, target in ((0, 4), (4, 8), (8, 0x34), (12, 0x24), (16, 0x2C),
                           (0x24, 0x38), (0x2C, 0x3C)):
        struct.pack_into(">I", data, offset, target)
    relocations = struct.pack(">7I", 0, 4, 8, 12, 16, 0x24, 0x2C)
    export = bytes(8) + b"scene_data\0"
    header = struct.pack(">8I", 0x20 + len(data) + len(relocations) + len(export),
                         len(data), 7, 1, 0, 0, 0, 0)
    return bytes(0x40) + header + data + relocations + export


class FieldModelTests(unittest.TestCase):
    def test_each_field_slot_uses_relocated_idle_motion(self):
        field = _field_model(_model_fixture())
        self.assertEqual(u32(field, 0), len(field))
        self.assertEqual(u32(field, 8), 31)
        for pointer_field, idle in ((12, 0x38), (16, 0x3C)):
            table = u32(field, 0x20 + pointer_field)
            self.assertEqual(struct.unpack_from(">13I", field, 0x20 + table), (idle,) * 12 + (0,))
            relocations = set(struct.unpack_from(">31I", field, 0x20 + u32(field, 4)))
            self.assertTrue(set(range(table, table + 48, 4)) <= relocations)
            self.assertNotIn(table + 48, relocations)

    def test_missing_idle_pointer_is_rejected(self):
        model = bytearray(_model_fixture())
        struct.pack_into(">I", model, 0x40 + 0x20 + 0x24, 0)
        with self.assertRaisesRegex(FormatError, "no idle motion"):
            _field_model(bytes(model))

    def test_attachment_keeps_scaling_separate_from_the_root_and_idle(self):
        field = _field_model(_model_fixture(), scale=0.125, attachment_offset=(1.0, 0.75, -1.0))
        joints = field[0x20:0x20 + u32(field, 4)]
        outer = u32(joints, 8)
        scaled = u32(joints, outer + 8)
        self.assertEqual(u32(joints, scaled + 8), 0x34)
        self.assertEqual(struct.unpack_from(">3f", joints, outer + 0x20), (1.0,) * 3)
        self.assertEqual(struct.unpack_from(">3f", joints, scaled + 0x20), (0.125,) * 3)
        self.assertEqual(struct.unpack_from(">3f", joints, scaled + 0x2C), (1.0, 0.75, -1.0))
        relocations = set(struct.unpack_from(f">{u32(field, 8)}I", field, 0x20 + len(joints)))
        self.assertTrue({outer + 8, scaled + 8} <= relocations)
        for pointer_field, idle in ((12, 0x38), (16, 0x3C)):
            animation = u32(joints, u32(joints, pointer_field))
            child = u32(joints, animation)
            self.assertEqual(u32(joints, child), idle)
            self.assertTrue({animation, child} <= relocations)

    @unittest.skipUnless(Path("game/files/M2_guild_1F_1.fsys").is_file(),
                         "requires the local original PAL Colosseum files")
    def test_pyrite_room_preserves_other_resources_and_actor_id(self):
        root = Path("game")

        def archive(name):
            return (root / "files" / name).read_bytes()

        snorlax = load_actor_model((root / "sys/main.dol").read_bytes(), "GC6P01", 143, archive)
        source = archive("M2_guild_1F_1.fsys")
        output = patch_actor(source, snorlax)
        for old, new in zip(parse_fsys(source)["members"], parse_fsys(output)["members"], strict=True):
            self.assertEqual(old["identifier_raw"], new["identifier_raw"])
            expected = snorlax if old["name"] == "prasle_b1" else decoded_member(source, old)
            self.assertEqual(decoded_member(output, new), expected)
