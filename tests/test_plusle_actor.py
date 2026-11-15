"""Verify that the field actor keeps a valid HSD motion table after replacement."""

from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.actor_palette import _walk_materials
from orre_randomizer.engine.plusle_actor import _field_model, _pkx_idle_motion, load_actor_model, patch_actor
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


def _two_motion_fixture():
    data = bytearray(0x70)
    pointers = ((0, 4), (4, 8), (8, 0x60), (12, 0x24), (16, 0x30),
                (0x24, 0x50), (0x28, 0x54), (0x30, 0x58), (0x34, 0x5C))
    for at, value in pointers:
        struct.pack_into(">I", data, at, value)
    relocations = struct.pack(">9I", *(at for at, _ in pointers))
    export = bytes(8) + b"scene_data\0"
    header = struct.pack(">8I", 0x20 + len(data) + len(relocations) + len(export),
                         len(data), len(pointers), 1, 0, 0, 0, 0)
    return bytes(0x40) + header + data + relocations + export


class FieldModelTests(unittest.TestCase):
    def test_shiny_palette_covers_textures_in_nonzero_animation_slots(self):
        data = bytearray(0x120)
        pointers = ((0, 0x40), (8, 0x80), (0x80, 0xA0), (0x84, 0xB0),
                    (0xB8, 0xC0), (0xC8, 0xD0), (0xDC, 0xF0), (0xF0, 0x100))
        for at, value in pointers:
            struct.pack_into(">I", data, at, value)
        struct.pack_into(">HH", data, 0xE4, 1, 0)
        images, palettes, solid = _walk_materials(data, {at for at, _ in pointers}, 0)
        self.assertEqual(images, {0x100})
        self.assertFalse(palettes | solid)

    def test_idle_slot_is_resolved_for_both_pkx_layouts(self):
        for xd in (False, True):
            with self.subTest(xd=xd):
                pkx = bytearray(0x200)
                if xd:
                    struct.pack_into(">I", pkx, 0x10, 1)
                    metadata = 0x84
                else:
                    struct.pack_into(">3I", pkx, 0, 0x31, 0x11, 1)
                    metadata = 0x40 + 0x40 + 0x20
                struct.pack_into(">2I", pkx, metadata, 2, 1)
                struct.pack_into(">I", pkx, metadata + 0x90, 3)
                self.assertEqual(_pkx_idle_motion(bytes(pkx), xd=xd), 3)

    def test_nonzero_idle_uses_matching_joint_and_texture_animation(self):
        field = _field_model(_two_motion_fixture(), motion_indices=(1,) * 12)
        for pointer_field, expected in ((12, 0x54), (16, 0x5C)):
            table = u32(field, 0x20 + pointer_field)
            self.assertEqual(struct.unpack_from(">13I", field, 0x20 + table), (expected,) * 12 + (0,))

    def test_native_field_motion_order_is_preserved_and_missing_slots_are_padded(self):
        field = _field_model(_two_motion_fixture(), motion_indices=(0, 1) + (0,) * 10)
        for pointer_field, pair in ((12, (0x50, 0x54)), (16, (0x58, 0x5C))):
            table = u32(field, 0x20 + pointer_field)
            self.assertEqual(struct.unpack_from(">13I", field, 0x20 + table), pair + (pair[0],) * 10 + (0,))

    def test_missing_selected_idle_is_rejected(self):
        with self.assertRaisesRegex(FormatError, "requested index"):
            _field_model(_model_fixture(), motion_indices=(1,) * 12)

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

    @unittest.skipUnless(Path("game/files/M2_guild_1F_1.fsys").is_file(),
                         "requires the local original PAL Colosseum files")
    def test_retail_plusle_keeps_native_scene_choreography_in_both_palettes(self):
        def archive(name):
            return Path("game/files", name).read_bytes()

        source = archive("M2_guild_1F_1.fsys")
        native = decoded_member(source, next(m for m in parse_fsys(source)["members"] if m["name"] == "prasle_b1"))
        dol = Path("game/sys/main.dol").read_bytes()

        def joint_motions(dat):
            # The native Plusle model's public scene is the sole export.
            export = 0x20 + u32(dat, 4) + 4 * u32(dat, 8)
            scene = u32(dat, export)
            model = u32(dat, 0x20 + u32(dat, 0x20 + scene))
            table = u32(dat, 0x20 + model + 4)
            return struct.unpack_from(">10I", dat, 0x20 + table)

        normal = load_actor_model(dol, "GC6P01", 353, archive, native_field_motions=True)
        shiny = load_actor_model(dol, "GC6P01", 353, archive, shiny=True, native_field_motions=True)
        self.assertEqual(joint_motions(normal), joint_motions(native))
        self.assertEqual(joint_motions(shiny), joint_motions(native))
        self.assertNotEqual(shiny, normal)

    @unittest.skipUnless(Path("game/files/pkx_prasle.fsys").is_file(),
                         "requires the local original PAL Colosseum files")
    def test_retail_battle_plusle_selects_idle_not_blink(self):
        def archive(name):
            return Path("game/files", name).read_bytes()

        source = archive("pkx_prasle.fsys")
        pkx = decoded_member(source, parse_fsys(source)["members"][0])
        self.assertEqual(_pkx_idle_motion(pkx, xd=False), 3)
        model = load_actor_model(Path("game/sys/main.dol").read_bytes(), "GC6P01", 353, archive)
        self.assertEqual(model, _field_model(pkx, motion_indices=(3,) * 12))
