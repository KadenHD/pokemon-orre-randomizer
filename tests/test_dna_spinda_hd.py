import hashlib
import struct
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from orre_randomizer.engine import dna_hd_tiles as tiles, dna_spinda_hd as spinda
from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.dna_keypad_runtime import _PID_TABLE_MARKER, spinda_diagram_pid_records, _keypad_hook
from orre_randomizer.engine.dna_keypad import DNA_KEYPAD_SPECIES
from tests.test_spinda_diagram import retail
from orre_randomizer.engine.spinda_art import _FACE_ORDER, _SPOT_ORDER
from orre_randomizer.engine.spinda_diagram import TEXTURE_BYTES
from orre_randomizer.hd_spinda_diagram import DONOR, render_spinda_diagram_layer, _paint
from tests.test_dna_hd_tiles import split_fixture, PPC


def extended_fixture(samples=(185,)):
    _, original, base = split_fixture()
    original = bytearray(original)
    struct.pack_into(">694I", original, 32 + base["new_data_size"], *range(0, 694 * 4, 4))
    original = bytes(original)
    layout = spinda.expanded_layout(tiles._layout(), sorted(samples))
    bank = bytes(layout["spinda_diagram"]["bank_bytes"])
    def body_images(raw, cell, *args):
        original = raw[cell["file_offset"]:cell["file_offset"] + cell["bytes"]]
        return original, bytes([0x61]) * len(original)
    with patch.object(spinda, "native_bank", return_value=(bank, {"test_only": True})), patch.object(spinda,"body_variants",side_effect=body_images):
        result, report = spinda.extend_spinda_keypad_dat(original, base, sorted(samples), b"face", b"stamp")
    return original, result, base, report


class SpindaDATTests(unittest.TestCase):
    def test_all_gx_pixel_allocations_stay_32_aligned_with_eight_and_nine_samples(self):
        for count in (8,9):
            _, raw, _, layout=extended_fixture(DNA_KEYPAD_SPECIES[:count])
            spec=layout['spinda_diagram']
            pointers=[spec['frozen_case_atlas_data_offset'],spec['empty_data_offset'],*spec['background_data_offsets']]
            pointers.extend(start+value*TEXTURE_BYTES for group in spec['spot_data_offsets']for start in group for value in range(256))
            for cell in spec['cells']:
                pointers.extend(cell['body_data_offsets'])
                pointers.extend(u32(raw,desc+32)for desc in cell['image_descriptors'])
            self.assertTrue(all(pointer%32==0 for pointer in pointers))
            self.assertTrue(all(pointer+TEXTURE_BYTES<=layout['new_data_size']for pointer in pointers))
            # GX stores the base address as addr>>5. This independent hardware
            # roundtrip detects the bug even if CPU hashes use an unaligned ptr.
            self.assertEqual([pointer>>5<<5 for pointer in pointers],pointers)

    def test_eight_and_nine_native_samples_reserve_writer_code_from_actual_emitted_size(self):
        face = retail(128, [0xE698] * 16384, _FACE_ORDER)
        stamp = retail(32, [0xFACC] * 1024, _SPOT_ORDER)
        origin = 0x81000000
        for count in (1, 8, 9):
            samples = {old: (i + 1, 123 + i, (0, -1), i % 2)
                       for i, old in enumerate(DNA_KEYPAD_SPECIES[:count])}
            payload = _keypad_hook(origin, 0x801962D8, None, 0x8009E7F8, 0x800BE89C,
                SimpleNamespace(player_pointer=0x804C8268), samples,
                {"resolver": 0x81200000, "shadow_generated": 0x81200100, "stored_shadow_pid": 0x81200200},
                face, stamp, ((1, 0, 2, 3), (171, 158, 137, 127)))
            self.assertEqual(len(payload) % 32, 0)
            calls = []
            for at in range(0, payload.find(_PID_TABLE_MARKER), 4):
                word = u32(payload, at)
                if word & 0xFC000003 != 0x48000001:
                    continue
                displacement = word & 0x03FFFFFC
                if displacement & (1 << 25):displacement -= 1 << 26
                target = origin + at + displacement
                if origin <= target < origin + len(payload):calls.append((at, target))
            targets = sorted({target for _, target in calls})
            self.assertEqual(len(targets), 2)
            self.assertEqual([sum(target == expected for _, target in calls) for expected in targets], [count, count])
            self.assertEqual(u32(payload, targets[0] - origin), 0x9421FFA0)
            self.assertEqual(u32(payload, targets[1] - origin), 0x28050000)
            self.assertGreater(targets[0] - origin, max(at for at, _ in calls))
            if count == 8:self.assertGreater(targets[0] - origin, 0x800)
            header = bytearray(256)
            for offset,value in ((8,256),(0x50,origin),(0x98,len(payload))):struct.pack_into(">I",header,offset,value)
            self.assertEqual(set(spinda_diagram_pid_records(bytes(header)+payload)), set(samples))

    def test_descriptor_graph_relocations_frozen_pixels_and_directory_are_bounded(self):
        original, result, base, report = extended_fixture()
        layout = tiles._validated_layout(report)
        self.assertEqual(len(result), layout["new_dat_size"])
        self.assertEqual(struct.unpack_from(">3I", result), (len(result), layout["new_data_size"], 709))
        self.assertEqual(result[32 + layout["new_data_size"] + 709 * 4:],
                         original[32 + base["new_data_size"] + 694 * 4:])
        selected = layout["spinda_diagram"]["cells"][0]
        frozen_case = layout["spinda_diagram"]["frozen_case_atlas_data_offset"] + 32
        self.assertEqual(result[frozen_case:frozen_case + 0x80000],original[0x7820:0x87820])
        cell = layout["cells"][selected["model_index"]]
        left, top, _ = selected["diagram_in_cell"]
        expected = b"".join(original[cell["file_offset"] + (top // 8 + y) * cell["row_bytes"] + left // 8 * 32:
            cell["file_offset"] + (top // 8 + y) * cell["row_bytes"] + left // 8 * 32 + 128] for y in range(4))
        frozen = selected["frozen_diagram_data_offset"] + 32
        self.assertEqual(result[frozen:frozen + 512], expected)
        relocations = struct.unpack_from(">709I", result, 32 + layout["new_data_size"])
        new_relocations = set(relocations) - set(struct.unpack_from(">694I", original, 32 + base["new_data_size"]))
        self.assertEqual(len(new_relocations), 15)
        for at in new_relocations:
            self.assertEqual(at % 4, 0)
            self.assertLess(u32(result, at + 32), layout["new_data_size"])
        for index, (desc, texture) in enumerate(zip(selected["image_descriptors"], selected["texture_objects"])):
            self.assertEqual(struct.unpack_from(">IHHII", result, desc + 32),
                (layout["spinda_diagram"]["empty_data_offset"], 40, 40, 14, 0))
            self.assertEqual(u32(result, texture + 32 + 0x40), 0x510010)
            next_tobj = selected["texture_objects"][index + 1] if index < 4 else 0
            self.assertEqual(u32(result, texture + 32 + 4), next_tobj)
            scale = struct.unpack_from(">ff", result, texture + 32 + 0x1C)
            translate = struct.unpack_from(">ff", result, texture + 32 + 0x28)
            self.assertAlmostEqual((left / cell["width"] - translate[0]) / scale[0], 4 / 40, places=5)
            self.assertAlmostEqual((top / cell["height"] - translate[1]) / scale[1], 4 / 40, places=5)

    def test_unknown_samples_and_repeated_extension_are_rejected(self):
        original, result, base, report = extended_fixture()
        for values in ([], [185, 185], [1], [True], [200, 185]):
            with self.assertRaises(FormatError):
                spinda.expanded_layout(tiles._layout(), values)
        with self.assertRaises(FormatError):
            spinda.extend_spinda_keypad_dat(result, report, [185], b"face", b"stamp")
        bad = dict(report, new_data_size=report["new_data_size"] + 32)
        with self.assertRaises(FormatError):
            tiles._validated_layout(bad)

    def test_pid_metadata_requires_unique_original_compiled_records(self):
        header = bytearray(256)
        payload = _PID_TABLE_MARKER + struct.pack(">4IHHIII", 1, 0, 0, 0, 185, 6, 0, 0, 0)
        struct.pack_into(">I", header, 8, 256)
        struct.pack_into(">I", header, 0x50, 0x81000000)
        struct.pack_into(">I", header, 0x98, len(payload))
        dol = bytes(header) + payload
        self.assertEqual(spinda_diagram_pid_records(dol), {185: {"address": 0x81000030, "shadow_id": 6}})
        for change in (b"\0\0\0\1", b"\0\0\0\2"):
            damaged = bytearray(dol)
            damaged[256 + 52:256 + 56] = change
            with self.assertRaises(FormatError):
                spinda_diagram_pid_records(bytes(damaged))


class SpindaPPCBridgeTests(unittest.TestCase):
    def execute(self, pid, shiny, ready=1):
        original, dat, base, report = extended_fixture()
        layout = tiles._validated_layout(report)
        record_address = 0x81400000
        runtime_layout = dict(layout, _spinda_pid_records={185: {"address": record_address, "shadow_id": 6}})
        parser, flush, invalidate = tiles._LAYOUTS["GC6P01"]
        machine = PPC()
        address, data_address = 0x81000000, 0x80600000
        machine.load_code(address, tiles._sync_stub(address, parser, flush, invalidate, runtime_layout))
        # Sparse memory: the immutable1.64MB bank is never read by this selector.
        machine.load_data(data_address, dat[:32 + base["new_data_size"]])
        spec = layout["spinda_diagram"]
        selected = spec["cells"][0]
        frozen = selected["frozen_diagram_data_offset"] + 32
        machine.load_data(data_address + frozen, dat[frozen:frozen + 512])
        for desc in selected["image_descriptors"]:
            machine.load_data(data_address + desc + 32, dat[desc + 32:desc + 56])
        machine.load_data(record_address, struct.pack(">HHIII", 185, 6, ready, pid, shiny))
        machine.write(data_address + 28, tiles._ACTIVE_MAGIC)
        machine.reg[3:6] = [0x80500000, data_address, tiles.OLD_DAT_SIZE]
        saved = machine.reg[:]
        saved_special = machine.cr, machine.xer, machine.ctr, machine.lr
        machine.pc = address
        # Independent semantics for the two additional selection instructions.
        for pc, instruction in list(machine.code.items()):
            op = instruction >> 26
            if op not in (7, 21):
                continue
            def arithmetic(m, ins=instruction, at=pc):
                rt, ra, rb = ((ins >> shift) & 31 for shift in (21, 16, 11))
                if ins >> 26 == 7:
                    imm = ins & 65535
                    m.reg[rt] = m.reg[ra] * (imm - 65536 if imm & 32768 else imm) & 0xFFFFFFFF
                else:
                    left, right = ins >> 6 & 31, ins >> 1 & 31
                    mask = ((1 << (32 - left)) - 1) ^ ((1 << (31 - right)) - 1)
                    value = m.reg[rt]
                    rotated = ((value << rb) | (value >> (32 - rb if rb else 32))) & 0xFFFFFFFF
                    m.reg[ra] = rotated & mask
                m.pc = at + 4
            machine.external[pc] = arithmetic
        def cache_call(m):
            continuation = m.lr
            m.calls.append((m.pc, m.reg[3], m.reg[4]))
            for register in (0, *range(3, 13)):
                m.reg[register] = 0xD00D0000 + register
            m.cr, m.xer, m.ctr, m.lr = 0xDEADBEEF, 0xA1B2C3D4, 7, 9
            m.pc = continuation
        machine.external[flush] = machine.external[invalidate] = cache_call
        cell = layout["cells"][selected["model_index"]]
        left, top, _ = selected["diagram_in_cell"]
        old_at = cell["source_file_offset"] + top // 8 * 4096 + left // 8 * 32
        for row in range(4):
            machine.load_data(data_address + old_at + row * 4096, b"\xC7" * 128)
        machine.run(parser + 8)
        expected_registers = saved[:]
        expected_registers[0] = machine.lr  # displaced native mflr r0
        expected_registers[5] = layout["new_dat_size"]
        self.assertEqual(machine.reg, expected_registers)
        self.assertEqual((machine.cr, machine.xer, machine.ctr, machine.lr), saved_special)
        for row in range(4):
            for target in (old_at + row * 4096,
                           cell["file_offset"] + (top // 8 + row) * cell["row_bytes"] + left // 8 * 32):
                self.assertEqual(bytes(machine.read(data_address + target + i, 1) for i in range(128)),
                                 dat[frozen + row * 128:frozen + (row + 1) * 128])
        self.assertEqual(len(machine.calls), 4)
        for desc in spec["frozen_case_image_descriptor_file_offsets"]:
            self.assertEqual(machine.read(data_address+desc),spec["frozen_case_atlas_data_offset"])
        return machine, data_address, selected, spec

    def test_saved_arbitrary_pid_bytes_select_independent_shiny_layers_and_preserve_abi(self):
        for pid, shiny in ((0x0123ABFF, 0), (0xFFEEDD00, 1), (0, 1)):
            machine, data, selected, spec = self.execute(pid, shiny)
            expected = [spec["background_data_offsets"][shiny], *[
                spec["spot_data_offsets"][shiny][i] + ((pid >> (8 * i)) & 255) * TEXTURE_BYTES for i in range(4)]]
            self.assertEqual([machine.read(data + desc + 32) for desc in selected["image_descriptors"]], expected)
            self.assertEqual(machine.read(data+selected["body_image_descriptor_file_offset"]),selected["body_data_offsets"][shiny])

    def test_unavailable_identity_stays_invisible_and_does_not_invent_a_pid(self):
        machine, data, selected, spec = self.execute(0xABCDEF12, 0, ready=0)
        self.assertEqual([machine.read(data + desc + 32) for desc in selected["image_descriptors"]], [spec["empty_data_offset"]] * 5)


class SpindaHDSourceTests(unittest.TestCase):
    def test_actual_hd_paint_and_vector_mask_provenance_no_native_bitmap_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            donor = root / DONOR
            image = Image.new("RGBA", (512, 512), (230, 211, 198, 255))
            image.paste((252, 70, 90, 255), (128, 80, 176, 144))
            image.save(donor)
            transform = {"layer": "spot", "shiny": False, "spot": 2, "pid_byte": 136}
            result, records = render_spinda_diagram_layer(transform, {"colosseum": root})
            self.assertEqual((result.width(), result.height()), (160, 160))
            self.assertEqual(records[0]["sha256"], hashlib.sha256(donor.read_bytes()).hexdigest())
            self.assertEqual(records[0]["source_scale"], 4)
            self.assertFalse(records[0]["native_stamp_bitmap_filtered"])
            self.assertEqual(result.pixelColor(16 + 30 + 14, 16 + 65 + 16).getRgb(), (252, 70, 90, 255))
            self.assertEqual(result.pixelColor(0, 0).alpha(), 0)
            _paint.cache_clear()
            Image.new("RGBA", (128, 128), (255, 0, 0, 255)).save(donor)
            with self.assertRaises(ValueError):
                render_spinda_diagram_layer(transform, {"colosseum": root})


if __name__ == "__main__":
    unittest.main()
