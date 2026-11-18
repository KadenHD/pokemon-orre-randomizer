"""Synthetic DAT preservation and independent execution of the emitted PPC ABI."""
import hashlib
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine import dna_hd_tiles as tiles
from orre_randomizer.engine.analyze_game import FormatError, parse_dol, parse_fsys, u32
from orre_randomizer.engine.dol_regions import LAYOUTS
from orre_randomizer.engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from orre_randomizer.engine.rebuild_iso import decoded_member
from tests.test_artwork import fsys


def dat_fixture():
    """Mathematical samples and a synthetic directory, without game imagery."""
    data = bytearray(tiles.OLD_DAT_SIZE)
    struct.pack_into(">8I", data, 0, tiles.OLD_DAT_SIZE, tiles.OLD_DATA_SIZE, 694, 1, 0, 0, 0, 0)
    for index in range(18):
        struct.pack_into(">IHHIIff", data, 32 + 0x4590 + index * 0xA0,
                         0x7800, 1024, 1024, 14, 0, 0., 0.)
    for model, (x, y) in enumerate(tiles._KEY_ORIGINS):
        for i in range(8):
            struct.pack_into(">ff", data, 32 + 0x3E60 + (84 + model * 8 + i) * 8,
                             (x - 32 + (i % 2) * 159.25) / 1024,
                             (y - .25 + (i // 2 % 2) * 128.75) / 1024)
    for macroblock in range(tiles.ATLAS_SIZE // 32):
        start = tiles.ATLAS_OFFSET + macroblock * 32
        data[start:start + 32] = struct.pack(">I", macroblock) * 8
    # Nonzero mathematical directory sentinel verifies that moving it is exact.
    start = 32 + tiles.OLD_DATA_SIZE
    data[start:] = bytes((i * 13 + 7) & 255 for i in range(len(data) - start))
    canonical = bytearray(data)
    canonical[tiles.ATLAS_OFFSET:tiles.ATLAS_OFFSET + tiles.ATLAS_SIZE] = bytes(tiles.ATLAS_SIZE)
    return bytes(data), hashlib.sha256(canonical).hexdigest()


def split_fixture():
    original, fingerprint = dat_fixture()
    with patch.object(tiles, "STRUCTURAL_SHA256", fingerprint):
        result, layout = tiles.split_keypad_dat(original)
    return original, result, layout


class TileSplitTests(unittest.TestCase):
    def test_exact_macroblocks_uv_remap_directory_and_unrelated_native_bytes(self):
        original, result, layout = split_fixture()
        self.assertEqual(len(result), 0xA33AB)
        self.assertEqual(struct.unpack_from(">II", result), (len(result), 0xA28A0))
        self.assertEqual(u32(result, 28), tiles.MAGIC)
        self.assertEqual(result[tiles.ATLAS_OFFSET:tiles.ATLAS_OFFSET + tiles.ATLAS_SIZE],
                         original[tiles.ATLAS_OFFSET:tiles.ATLAS_OFFSET + tiles.ATLAS_SIZE])
        self.assertEqual(result[32 + layout["new_data_size"]:], original[32 + tiles.OLD_DATA_SIZE:])
        allowed = set(range(0, 8)) | set(range(28, 32))
        observed_uvs = set()
        for cell in layout["cells"]:
            start, row_bytes, rows = cell["file_offset"], cell["row_bytes"], cell["rows"]
            # Independent atlas block coordinates, rather than the emitter's row helper.
            expected = b"".join(
                original[tiles.ATLAS_OFFSET + ((cell["crop_y"] // 8 + by) * 128 + bx) * 32:
                         tiles.ATLAS_OFFSET + ((cell["crop_y"] // 8 + by) * 128 + bx + 1) * 32]
                for by in range(cell["height"] // 8)
                for bx in range(cell["crop_x"] // 8, (cell["crop_x"] + cell["width"]) // 8))
            self.assertEqual(result[start:start + rows * row_bytes], expected)
            desc = cell["image_descriptor_file_offset"]
            self.assertEqual(struct.unpack_from(">IHHII", result, desc),
                             (start - 32, cell["width"], cell["height"], 14, 0))
            allowed.update(range(desc, desc + 8))
            self.assertEqual((cell["art_x"], cell["art_y"]),
                             (40, 0 if cell["crop_y"] == 0 else 8))
            for index in cell["uv_indices"]:
                self.assertNotIn(index, observed_uvs)
                observed_uvs.add(index)
                pos = 32 + 0x3E60 + index * 8
                before = struct.unpack_from(">ff", original, pos)
                after = struct.unpack_from(">ff", result, pos)
                # Reconstruct the old pixel coordinate from the new one.
                self.assertAlmostEqual(after[0] * cell["width"] + cell["crop_x"], before[0] * 1024, places=4)
                self.assertAlmostEqual(after[1] * cell["height"] + cell["crop_y"], before[1] * 1024, places=4)
                allowed.update(range(pos, pos + 8))
        self.assertEqual(observed_uvs, set(range(84, 156)))
        changes = {pos for pos, (a, b) in enumerate(zip(original[:32 + tiles.OLD_DATA_SIZE], result)) if a != b}
        self.assertLessEqual(changes, allowed)

    def test_existing_native_art_and_spinda_marker_survive_and_input_is_immutable(self):
        original, fingerprint = dat_fixture()
        current = bytearray(original)
        struct.pack_into(">I", current, 24, 0x53504B44)
        current[tiles.ATLAS_OFFSET + 5000:tiles.ATLAS_OFFSET + 5032] = b"native samples kept".ljust(32, b"!")
        current = bytes(current)
        before = hashlib.sha256(current).hexdigest()
        with patch.object(tiles, "STRUCTURAL_SHA256", fingerprint):
            result, _ = tiles.split_keypad_dat(current)
        self.assertEqual(hashlib.sha256(current).hexdigest(), before)
        self.assertEqual(result[24:28], current[24:28])
        self.assertEqual(result[tiles.ATLAS_OFFSET:tiles.ATLAS_OFFSET + tiles.ATLAS_SIZE],
                         current[tiles.ATLAS_OFFSET:tiles.ATLAS_OFFSET + tiles.ATLAS_SIZE])

    def test_rejects_unknown_geometry_marker_size_and_second_split(self):
        original, fingerprint = dat_fixture()
        for damaged in (original[:-1], original[:4000] + b"x" + original[4001:],
                        original[:28] + b"DNAH" + original[32:],
                        original[:24] + b"oops" + original[28:]):
            with self.subTest(size=len(damaged)), patch.object(tiles, "STRUCTURAL_SHA256", fingerprint):
                with self.assertRaises(FormatError):
                    tiles.split_keypad_dat(damaged)
        with patch.object(tiles, "STRUCTURAL_SHA256", fingerprint):
            result, _ = tiles.split_keypad_dat(original)
            with self.assertRaises(FormatError):
                tiles.split_keypad_dat(result)

    def test_fsys_replaces_only_unique_keypad_member(self):
        original, fingerprint = dat_fixture()
        # All names precede the data area, as in the retail archive.
        archive = bytearray(0x100)
        archive[:4] = b"FSYS"
        for at,value in ((12,2),(0x40,0x60),(0x60,0x80),(0x64,0xB0)):
            struct.pack_into(">I", archive, at, value)
        archive[0xE0:0xE7], archive[0xE8:0xEF] = b"dnakey\0", b"camera\0"
        for header, ident, name_at, payload in ((0x80,0x107E0200,0xE0,original),
                                                (0xB0,0x107C1800,0xE8,b"camera sentinel")):
            archive.extend(bytes(-len(archive) % 32))
            for field,value in ((0,ident),(4,len(archive)),(8,len(payload)),
                                (0x14,len(payload)),(0x24,name_at)):
                struct.pack_into(">I", archive, header + field, value)
            archive.extend(payload)
        archive.extend(bytes(-len(archive) % 32) + bytes(28) + b"FSYS")
        struct.pack_into(">I", archive, 0x20, len(archive))
        archive = bytes(archive)
        with patch.object(tiles, "STRUCTURAL_SHA256", fingerprint):
            result, report = tiles.split_keypad_archive(archive)
        members = parse_fsys(result)["members"]
        self.assertEqual(decoded_member(result, members[1]), b"camera sentinel")
        self.assertEqual(u32(decoded_member(result, members[0]), 28), tiles.MAGIC)
        self.assertEqual(report["resource"], "0x107e0200")
        with self.assertRaises(FormatError):
            tiles.split_keypad_archive(fsys([("none", original)]))


MASK = 0xFFFFFFFF


class PPC:
    """Independent integer interpreter, including volatile-clobbering OS calls."""
    def __init__(self):
        self.code = {}
        self.mem = {}
        self.reg = [0x13570000 + 257 * i for i in range(32)]
        self.reg[1] = 0x817E0000
        self.cr, self.xer, self.ctr, self.lr = 0xA53C9876, 0xA000007F, 0xABCDEF09, 0x81234560
        self.calls = []
        self.external = {}
        self.pc = 0

    def load_code(self, address, payload):
        self.code.update({address + i: word[0] for i, word in
                          zip(range(0, len(payload), 4), struct.iter_unpack(">I", payload))})

    def load_data(self, address, payload):
        self.mem.update({address + i: value for i, value in enumerate(payload)})

    def read(self, address, size=4):
        return int.from_bytes(bytes(self.mem.get(address + i, 0) for i in range(size)), "big")

    def write(self, address, value, size=4):
        self.load_data(address, (value & ((1 << (size * 8)) - 1)).to_bytes(size, "big"))

    def compare(self, a, b):
        field = (8 if a < b else 4 if a > b else 2) | (self.xer >> 31 & 1)
        self.cr = self.cr & 0x0FFFFFFF | field << 28

    def run(self, stop, limit=220000):
        for _ in range(limit):
            if self.pc == stop:
                return
            if self.pc in self.external:
                self.external[self.pc](self)
                continue
            pc = self.pc
            word = self.code[pc]
            self.pc += 4
            op = word >> 26
            rt, ra, rb = ((word >> shift) & 31 for shift in (21, 16, 11))
            imm = word & 65535
            signed = imm - 65536 if imm & 32768 else imm
            specials = {0x7C0802A6: "lr", 0x7C0902A6: "ctr", 0x7C0102A6: "xer", 0x7C000026: "cr"}
            setters = {0x7C0803A6: "lr", 0x7C0903A6: "ctr", 0x7C0103A6: "xer", 0x7C0FF120: "cr"}
            if word in specials:
                self.reg[0] = getattr(self, specials[word])
            elif word in setters:
                setattr(self, setters[word], self.reg[0])
            elif word == 0x7D2903A6:
                self.ctr = self.reg[9]
            elif op in (14, 15):
                self.reg[rt] = ((self.reg[ra] if ra else 0) + (signed << (16 if op == 15 else 0))) & MASK
            elif op == 24:
                self.reg[ra] = self.reg[rt] | imm
            elif op == 28:
                self.reg[ra] = self.reg[rt] & imm
                self.compare(self.reg[ra], 0)
            elif op == 32:
                self.reg[rt] = self.read((self.reg[ra] + signed) & MASK)
            elif op in (36, 37):
                address = (self.reg[ra] + signed) & MASK
                self.write(address, self.reg[rt])
                if op == 37:
                    self.reg[ra] = address
            elif op == 10:
                self.compare(self.reg[ra], imm)
            elif op == 31 and word >> 1 & 1023 == 32:
                self.compare(self.reg[ra], self.reg[rb])
            elif op == 31 and word >> 1 & 1023 == 266:
                self.reg[rt] = (self.reg[ra] + self.reg[rb]) & MASK
            elif op == 18:
                if word & 2:
                    raise AssertionError("absolute branch is forbidden")
                delta = word & 0x03FFFFFC
                if delta & (1 << 25):
                    delta -= 1 << 26
                if word & 1:
                    self.lr = pc + 4
                self.pc = pc + delta
            elif op == 16:
                bo, bi = rt, ra
                if bo == 16:
                    self.ctr = (self.ctr - 1) & MASK
                    take = bool(self.ctr)
                elif bo in (4, 12):
                    take = bool(self.cr & (1 << (31 - bi))) == (bo == 12)
                else:
                    raise AssertionError(f"unsupported bc {word:08x}")
                if take:
                    delta = word & 0xFFFC
                    self.pc = pc + (delta - 65536 if delta & 32768 else delta)
            else:
                raise AssertionError(f"unsupported PPC {word:08x} at{pc:08x}")
        raise AssertionError("bridge failed to reach the native continuation")


class RuntimeBridgeTests(unittest.TestCase):
    def machine(self, *, chained=False):
        original, dat, layout = split_fixture()
        machine = PPC()
        parser, flush, invalidate = tiles._LAYOUTS["GC6P01"]
        entry, sync, previous = 0x81000000, 0x81001000, 0x81002000
        machine.load_code(entry, tiles._entry_stub(entry, parser, previous if chained else None, layout))
        machine.load_code(sync, tiles._sync_stub(sync, parser, flush, invalidate, layout))
        machine.load_code(parser, struct.pack(">II", branch(parser, entry), branch(parser + 4, sync)))
        base = 0x80600000
        machine.load_data(base, dat)
        machine.reg[3:6] = [0x80500000, base, layout["new_dat_size"]]
        machine.pc = parser

        def cache_call(m):
            return_pc = m.lr
            m.calls.append((m.pc, m.reg[3], m.reg[4]))
            for register in (0, *range(3, 13)):
                m.reg[register] = 0xDEAD0000 + register
            m.cr, m.xer, m.ctr, m.lr = 0xDEAD1234, 0xBEEF1234, 0xFF000111, 0x11111110
            m.pc = return_pc

        machine.external[flush] = cache_call
        machine.external[invalidate] = cache_call
        if chained:
            def old_writer(m):
                self.assertEqual(m.reg[5], tiles.OLD_DAT_SIZE)
                # A saved-appearance writer changes the old atlas before HSD parses it.
                cell = layout["cells"][3]
                source = (cell["source_file_offset"] + cell["art_y"] // 8 * 4096
                          + cell["art_x"] // 8 * 32 + 4096 * 4 + 40)
                m.write(base + source, 0xABCDEF01)
                # A neighbor's invisible padding must never change this cell's hash.
                padding = cell["source_file_offset"] + (cell["rows"] - 1) * 4096 + 16
                m.write(base + padding, 0x12345678)
                old_sp = m.reg[1]
                m.reg[1] -= 0x20
                m.write(m.reg[1], old_sp)
                m.pc = parser + 4
            machine.external[previous] = old_writer
        return machine, original, dat, layout, parser, flush, invalidate, base

    def assert_abi(self, m, before, special, *, size):
        expected = before.copy()
        expected[0], expected[1], expected[5] = special[3], before[1] - 0x20, size
        self.assertEqual(m.reg, expected)
        self.assertEqual((m.cr, m.xer, m.ctr, m.lr), special)

    def test_executes_native_and_chained_paths_preserving_abi_and_final_atlas(self):
        for chained in (False, True):
            with self.subTest(chained=chained):
                m, _, dat, layout, parser, flush, invalidate, base = self.machine(chained=chained)
                before = m.reg.copy()
                special = m.cr, m.xer, m.ctr, m.lr
                m.run(parser + 8)
                self.assert_abi(m, before, special, size=layout["new_dat_size"])
                self.assertEqual(u32(bytes(m.mem.get(base + i, 0) for i in range(32)), 28), tiles.MAGIC)
                self.assertEqual([call[0] for call in m.calls], [flush, invalidate])
                self.assertEqual(m.calls[0][1:], (base + layout["buffer_file_offset"], layout["buffer_bytes"]))
                for cell in layout["cells"]:
                    expected_cell = bytearray(dat[cell["file_offset"]:cell["file_offset"] + cell["bytes"]])
                    for row in range(16):
                        src = (base + cell["source_file_offset"] + (cell["art_y"] // 8 + row) * 4096
                               + cell["art_x"] // 8 * 32)
                        dst = (cell["art_y"] // 8 + row) * cell["row_bytes"] + cell["art_x"] // 8 * 32
                        expected_cell[dst:dst + 512] = bytes(m.mem.get(src + i, 0) for i in range(512))
                    self.assertEqual(bytes(m.mem.get(base + cell["file_offset"] + i, 0)
                                           for i in range(cell["bytes"])), expected_cell)
                # Header/directory/original atlas are preserved, except the old writer's deliberate sample.
                expected = bytearray(dat[:tiles._layout()["buffer_file_offset"]])
                if chained:
                    cell = layout["cells"][3]
                    source = (cell["source_file_offset"] + cell["art_y"] // 8 * 4096
                              + cell["art_x"] // 8 * 32 + 4096 * 4 + 40)
                    struct.pack_into(">I", expected, source, 0xABCDEF01)
                    padding = cell["source_file_offset"] + (cell["rows"] - 1) * 4096 + 16
                    struct.pack_into(">I", expected, padding, 0x12345678)
                self.assertEqual(bytes(m.mem.get(base + i, 0) for i in range(len(expected))), expected)

    def test_unrelated_null_short_misaligned_out_of_range_or_bad_header_passes_without_writes(self):
        cases = ("null_object", "null_dat", "old_length", "short", "unaligned", "end_mem1", "magic", "header")
        for case in cases:
            with self.subTest(case=case):
                m, _, dat, layout, parser, _, _, base = self.machine()
                if case == "null_object":m.reg[3] = 0
                elif case == "null_dat":m.reg[4] = 0
                elif case == "old_length":m.reg[5] = tiles.OLD_DAT_SIZE
                elif case == "short":m.reg[5] = 31
                elif case == "unaligned":m.reg[4] += 1
                elif case == "end_mem1":m.reg[4] = 0x817F0000
                elif case == "magic":m.write(base + 28, 0)
                else:m.write(base + 4, 0)
                before = m.reg.copy();special = m.cr, m.xer, m.ctr, m.lr
                memory_before = {k:v for k,v in m.mem.items() if base <= k < base + len(dat)}
                m.run(parser + 8)
                self.assert_abi(m, before, special, size=before[5])
                self.assertFalse(m.calls)
                self.assertEqual({k:v for k,v in m.mem.items() if base <= k < base + len(dat)}, memory_before)


def dol_fixture(region):
    original = bytearray(0x1A0000)
    struct.pack_into(">I", original, 0, 0x100)
    struct.pack_into(">I", original, 0x48, TEXT_TO_RAM + 0x100)
    struct.pack_into(">I", original, 0x90, len(original) - 0x100)
    struct.pack_into(">III", original, 0xD8, region.bss_end - 0x1000, 0x1000, TEXT_TO_RAM + 0x100)
    parser = tiles._LAYOUTS[region.game_id][0]
    struct.pack_into(f">{len(tiles._PARSE_SIGNATURE)}I", original,
                     parser - TEXT_TO_RAM, *tiles._PARSE_SIGNATURE)
    struct.pack_into(">II", original, region.set_arena_lo - TEXT_TO_RAM,
                     region.arena_lo_store, 0x4E800020)
    return bytes(original)


class BridgeCompositionTests(unittest.TestCase):
    def test_all_regions_append_preserve_other_patches_and_chain_existing_parser(self):
        for region in LAYOUTS:
            for existing in (False, True):
                with self.subTest(game=region.game_id, existing=existing):
                    original = dol_fixture(region)
                    current = bytearray(original)
                    current[0x500:0x508] = b"sentinel"
                    section = len(current)
                    parser = tiles._LAYOUTS[region.game_id][0]
                    if existing:
                        body = _arena_guard(region.section_ram + 96, region.arena_lo_store) + bytes.fromhex("60000000") * 16
                        current.extend(body)
                        for field,value in zip((8,0x50,0x98),(section,region.section_ram,96)):
                            struct.pack_into(">I", current, field, value)
                        struct.pack_into(">I", current, region.set_arena_lo - TEXT_TO_RAM,
                                         branch(region.set_arena_lo, region.section_ram))
                        struct.pack_into(">I", current, parser - TEXT_TO_RAM,
                                         branch(parser, region.section_ram + 32))
                    with patch.object(tiles, "dol_layout", return_value=region):
                        output, report = tiles.install_dna_hd_tile_bridge(original, bytes(current), tiles._layout())
                    self.assertEqual(output[0x500:0x508], b"sentinel")
                    self.assertEqual(report["chained_entry"], region.section_ram + 32 if existing else None)
                    self.assertEqual(output[section:section + 32], _arena_guard(report["reserved_end"], region.arena_lo_store))
                    if existing:self.assertEqual(output[section + 32:section + 96], current[section + 32:section + 96])
                    added = next(row for row in parse_dol(output)["sections"] if row["name"] == "text2")
                    self.assertEqual(added["offset"] + added["size"], len(output))
                    with patch.object(tiles, "dol_layout", return_value=region):
                        with self.assertRaisesRegex(FormatError, "continuation"):
                            tiles.install_dna_hd_tile_bridge(original, output, tiles._layout())

    def test_rejects_unknown_original_modified_layout_and_reserved_code_corruption(self):
        region = LAYOUTS[0];original = dol_fixture(region)
        with self.assertRaises(FormatError):tiles.install_dna_hd_tile_bridge(original, original, tiles._layout())
        layout = tiles._layout();layout["cells"][0]["file_offset"] += 4
        with self.assertRaisesRegex(FormatError, "layout contract"):
            tiles.install_dna_hd_tile_bridge(original, original, layout)
        for damage in ("continuation", "entry", "arena"):
            current = bytearray(original)
            at = (tiles._LAYOUTS[region.game_id][0] - TEXT_TO_RAM + (4 if damage == "continuation" else 0)
                  if damage != "arena" else region.set_arena_lo - TEXT_TO_RAM)
            struct.pack_into(">I", current, at, 0)
            with self.subTest(damage=damage), patch.object(tiles, "dol_layout", return_value=region):
                with self.assertRaises(FormatError):
                    tiles.install_dna_hd_tile_bridge(original, bytes(current), tiles._layout())


if __name__ == "__main__":
    unittest.main()
