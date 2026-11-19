"""Execute emitted PPC independently, including hostile volatile-register calls."""
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer import hd_text_runtime as bridge
from orre_randomizer.hd_text import Glyph, build_native_pages
from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from tests.test_dna_hd_tiles import PPC

MASK = 0xFFFFFFFF


class TextPPC(PPC):
    def __init__(self):
        super().__init__()
        self.fpr = [(0x3FF0000000000000 + i, 0x40000000 + i) for i in range(32)]
        self.fpscr = 0xFEDC0123

    def load_code(self, address, payload):
        super().load_code(address, payload)
        for pc in range(address, address + len(payload), 4):
            word = self.code[pc]
            op, xo = word >> 26, word >> 1 & 1023
            if op not in (11, 21, 34, 40, 44, 48, 50, 52, 54, 56, 59, 60, 63) and not (op == 31 and xo in (40, 444, 87, 922)):
                continue
            def step(m, ins=word, at=pc):
                rt, ra, rb = (ins >> 21 & 31, ins >> 16 & 31, ins >> 11 & 31)
                opcode, ext = ins >> 26, ins >> 1 & 1023
                imm = ins & 65535
                signed = imm - 65536 if imm & 32768 else imm
                if opcode == 11:
                    value = m.reg[ra]
                    value -= 0x100000000 if value & 0x80000000 else 0
                    m.compare(value, signed)
                elif opcode == 21:
                    begin, end = ins >> 6 & 31, ins >> 1 & 31
                    mask = sum(1 << (31 - b) for b in range(32) if
                               (begin <= b <= end if begin <= end else b >= begin or b <= end))
                    value = m.reg[rt]
                    m.reg[ra] = ((value << rb) | (value >> ((32 - rb) or 32))) & MASK & mask
                elif opcode == 31:
                    if ext == 40:
                        m.reg[rt] = (m.reg[rb] - m.reg[ra]) & MASK
                    elif ext == 444:
                        m.reg[ra] = m.reg[rt] | m.reg[rb]
                    elif ext == 87:
                        m.reg[rt] = m.read((m.reg[ra] + m.reg[rb]) & MASK, 1)
                    else:
                        value = m.reg[rt] & 65535
                        m.reg[ra] = (value - 65536 if value & 32768 else value) & MASK
                elif opcode in (34, 40):
                    m.reg[rt] = m.read((m.reg[ra] + signed) & MASK, 1 if opcode == 34 else 2)
                elif opcode == 44:
                    m.write((m.reg[ra] + signed) & MASK, m.reg[rt], 2)
                elif opcode == 54:
                    m.write((m.reg[ra] + signed) & MASK, m.fpr[rt][0], 8)
                elif opcode == 50:
                    m.fpr[rt] = (m.read((m.reg[ra] + signed) & MASK, 8), m.fpr[rt][1])
                elif opcode == 48:
                    value = struct.unpack(">f", struct.pack(">I", m.read((m.reg[ra] + signed) & MASK)))[0]
                    m.fpr[rt] = (int.from_bytes(struct.pack(">d", value), "big"), m.fpr[rt][1])
                elif opcode == 52:
                    value = struct.unpack(">d", struct.pack(">Q", m.fpr[rt][0]))[0]
                    m.write((m.reg[ra] + signed) & MASK, int.from_bytes(struct.pack(">f", value), "big"))
                elif opcode == 59:
                    value = lambda r: struct.unpack(">d", struct.pack(">Q", m.fpr[r][0]))[0]
                    operation = ins >> 1 & 31
                    if operation == 25:
                        result = value(ra) * value(ins >> 6 & 31)
                    elif operation == 20:
                        result = value(ra) - value(rb)
                    else:
                        raise AssertionError("Unsupported independent single-precision operation")
                    result = struct.unpack(">f", struct.pack(">f", result))[0]
                    m.fpr[rt] = (int.from_bytes(struct.pack(">d", result), "big"), m.fpr[rt][1])
                elif opcode == 60:
                    displacement = ins & 4095
                    displacement -= 4096 if displacement & 2048 else 0
                    m.write((m.reg[ra] + displacement) & MASK, m.fpr[rt][1], 8)
                elif opcode == 56:
                    displacement = ins & 4095
                    displacement -= 4096 if displacement & 2048 else 0
                    m.fpr[rt] = (m.fpr[rt][0], m.read((m.reg[ra] + displacement) & MASK, 8))
                elif ins == 0xFC00048E:
                    m.fpr[0] = (m.fpscr, m.fpr[0][1])
                elif ins == 0xFDFE058E:
                    m.fpscr = m.fpr[0][0]
                else:
                    raise AssertionError(f"Unsupported independent opcode {ins:08x}")
                m.pc = at + 4
            self.external[pc] = step


class GlyphBridgePPC(unittest.TestCase):
    STATE, TABLE, PAGE, WORK, SOURCE = (0x81000000, 0x81001000, 0x81100000, 0x80500000, 0x80501000)

    def setup_lookup(self, *, altered=False, unknown=False, rows=3, width=11, padded=False):
        m = TextPPC()
        glyph = Glyph(2, 0xC9, width, rows, -2,
                      bytes((i * 17 + 3) & 255 for i in range((width + 1) // 2 * rows)), "math", 0)
        pages, plan = build_native_pages([glyph],
            padding_by_identity={glyph.identity: (1, 2, 3, 1)} if padded else None)
        r = plan["glyphs"][0]
        m.load_data(self.PAGE, pages[0])
        m.load_data(self.SOURCE, glyph.samples)
        if altered:
            m.write(self.SOURCE + 1, m.read(self.SOURCE + 1, 1) ^ 1, 1)
        metrics = width << 24 | rows << 16 | 254 << 8
        m.load_data(self.TABLE, struct.pack(">IIIHHIIII", 2 << 16 | 0xC9, metrics,
                                         self.PAGE, r["x"], r["y"], len(glyph.samples), 0, 0, 0))
        if padded:
            nibbles = self.PAGE + len(pages[0]) + 32
            m.load_data(nibbles, bytes.fromhex(r["source_padding_nibbles_hex"]))
            m.load_data(self.TABLE, struct.pack(">IIIHH4BHHfI", 2 << 16 | 0xC9, metrics,
                self.PAGE, r["x"], r["y"], *r["padding_ltrb"], r["draw_width"], r["draw_height"],
                float(r["padding_ltrb"][0]), nibbles))
        m.write(self.WORK + 0x20, 2, 2)
        m.write(self.STATE, self.WORK)
        m.write(self.STATE + 4, 0xCA if unknown else 0xC9)
        m.reg[3:8] = [self.WORK, self.SOURCE, width, rows, 0xFFFFFFFE]
        return m, r

    def test_padded_canvas_retains_exact_source_identity_including_unused_nibbles(self):
        for altered in (False, True):
            m, row = self.setup_lookup(padded=True)
            if altered:
                last = self.SOURCE + 5
                m.write(last, m.read(last, 1) ^ 1, 1)
            code, native = 0x81200000, 0x800FD69C
            m.load_code(code, bridge._lookup(code, native, 0x9421FF20, self.STATE, self.TABLE, 1))
            m.pc = code; m.run(native + 4)
            self.assertEqual(m.read(self.STATE + 8), 0 if altered else self.TABLE)

    def test_padded_geometry_preserves_advance_stride_and_restores_task_origin(self):
        for game, spec in bridge._REGIONS.items():
            with self.subTest(game=game):
                m, row = self.setup_lookup(padded=True)
                m.write(self.STATE + 8, self.TABLE)
                manager, dynamic = 0x80510000, 0x80511000
                m.reg[13] = 0x80520000; m.reg[31] = self.WORK; m.reg[30] = 0x12345678
                m.reg[8:10] = m.reg[5:7]
                m.write(m.reg[13] + spec[5] - 65536, manager)
                cursor, textures, index = (0x14, 8, 0x19) if game.startswith("GXX") else (0x18, 12, 0x1D)
                m.write(manager + cursor, 0x002A0046); m.write(manager + index, 1, 1)
                m.write(manager + textures + 4, dynamic)
                original_x = int.from_bytes(struct.pack(">f", 100.5), "big")
                m.write(self.WORK + 0x0C, original_x)
                scale_x = 0x64 if game.startswith("GXX") else 0x60
                other_field = 0x60 if game.startswith("GXX") else 0x64
                m.write(self.WORK + scale_x, int.from_bytes(struct.pack(">f", 1.5), "big"))
                m.write(self.WORK + other_field, int.from_bytes(struct.pack(">f", 37.25), "big"))
                m.write(self.WORK + 0x14, 0xCAFEBABE)
                def host(machine):
                    if machine.pc == spec[6]:
                        machine.write(self.PAGE + 0x28, self.PAGE + 128)
                    machine.pc = machine.lr
                m.external[spec[6]] = m.external[spec[7]] = host
                floats = m.fpr[:]
                for after, target in ((False, spec[3]), (True, spec[4])):
                    code = 0x81200000 + int(after) * 0x2000
                    displaced = 0x808D0000 | spec[5] if after else 0x7CE30734
                    m.load_code(code, bridge._drawing(code, target, displaced, self.STATE, spec, after=after))
                    m.pc = code; m.run(target + 4)
                    self.assertEqual(m.reg[30], 0x12345678)
                    self.assertEqual(m.fpr, floats)
                    self.assertEqual(m.read(self.WORK + 0x14), 0xCAFEBABE)
                    if not after:
                        self.assertEqual([m.reg[r] for r in (5, 8)], [row["draw_width"]] * 2)
                        self.assertEqual([m.reg[r] for r in (6, 9)], [row["draw_height"]] * 2)
                        self.assertEqual(m.reg[7], (-4) & MASK)
                        self.assertEqual(m.read(manager + cursor, 2), row["draw_x"])
                        self.assertEqual(m.read(manager + cursor + 2, 2), row["draw_y"])
                        self.assertEqual(struct.unpack(">f", struct.pack(">I", m.read(self.WORK + 0x0C)))[0], 97.5)
                    else:
                        self.assertEqual(m.read(self.WORK + 0x0C), original_x)
                        self.assertEqual(m.read(manager + cursor), 0x002A0046)

    def test_exact_bitmap_lookup_crosses_gx_tiles_and_preserves_entry_abi(self):
        for width, height in ((3, 3), (11, 17), (23, 22), (40, 40)):
            m, row = self.setup_lookup(width=width, rows=height)
            code, native = 0x81200000, 0x800FD69C
            m.load_code(code, bridge._lookup(code, native, 0x9421FF20, self.STATE, self.TABLE, 1))
            before, special = m.reg[:], (m.lr, m.cr, m.ctr, m.xer)
            m.pc = code
            m.run(native + 4)
            self.assertEqual(m.read(self.STATE + 8), self.TABLE)
            expected = before[:]
            expected[1] -= 0xE0  # displaced retail frame allocation
            self.assertEqual(m.reg, expected)
            self.assertEqual((m.lr, m.cr, m.ctr, m.xer), special)
            self.assertEqual(m.read(self.STATE), 0)  # a lookup can be consumed only once

    def test_unknown_code_or_one_changed_native_nibble_stays_native(self):
        for args in ({"unknown": True}, {"altered": True}):
            m, _ = self.setup_lookup(**args)
            code, native = 0x81200000, 0x800FD69C
            m.load_code(code, bridge._lookup(code, native, 0x9421FF20, self.STATE, self.TABLE, 1))
            m.pc = code
            m.run(native + 4)
            self.assertEqual(m.read(self.STATE + 8), 0)

    def test_zero_area_and_visible_fallback_counts_preserve_native_drawing_for_all_regions(self):
        for game, spec in bridge._REGIONS.items():
            for width, height in ((23, 0), (0, 22), (23, 19), (0x12340000, 22)):
                with self.subTest(game=game, width=width, height=height):
                    m, _ = self.setup_lookup()
                    m.reg[5:7] = [width, height]
                    m.write(self.STATE + 8, 0)
                    for offset, value in ((24, 12), (44, 4), (48, 8), (52, 0xCAFEBABE)):
                        m.write(self.STATE + offset, value)
                    manager, dynamic = 0x80510000, 0x80511000
                    m.reg[13] = 0x80520000
                    m.write(m.reg[13] + spec[5] - 65536, manager)
                    cursor, textures, index = (0x14, 8, 0x19) if game.startswith("GXX") else (0x18, 12, 0x1D)
                    m.write(manager + cursor, 0x002A0046)
                    m.write(manager + index, 1, 1)
                    m.write(manager + textures + 4, dynamic)
                    selected = []
                    def select(machine):
                        selected.append((machine.reg[3], machine.reg[4]))
                        machine.pc = machine.lr
                    m.external[spec[7]] = select
                    code = 0x81200000
                    m.load_code(code, bridge._drawing(code, spec[3], 0x7CE30734,
                                                    self.STATE, spec, after=False))
                    before, floating = m.reg[:], m.fpr[:]
                    special = m.lr, m.cr, m.ctr, m.xer, m.fpscr
                    m.pc = code; m.run(spec[3] + 4)
                    expected = before[:]
                    expected[3] = ((before[7] & 65535) - 65536) & MASK
                    self.assertEqual(m.reg, expected)
                    self.assertEqual(m.fpr, floating)
                    self.assertEqual((m.lr, m.cr, m.ctr, m.xer, m.fpscr), special)
                    self.assertEqual(selected, [(0, dynamic)])
                    self.assertEqual(m.read(manager + cursor), 0x002A0046)
                    self.assertEqual(m.read(self.STATE + 24), 13)
                    zero = not (width & 65535) or not (height & 65535)
                    self.assertEqual(m.read(self.STATE + 44), 4 + int(zero))
                    self.assertEqual(m.read(self.STATE + 48), 8 + int(not zero))
                    self.assertEqual(m.read(self.STATE + 52), 0xCAFEBABE)

    def test_texture_binding_and_cursor_restore_with_volatile_fp_clobber(self):
        for game in ("GC6P01", "GXXP01"):
            spec = bridge._REGIONS[game]
            m, row = self.setup_lookup()
            m.write(self.STATE + 8, self.TABLE)
            m.write(self.STATE + 20, 40)
            manager, dynamic = 0x80510000, 0x80511000
            m.reg[13] = 0x80520000
            displacement = spec[5] - 65536
            m.write(m.reg[13] + displacement, manager)
            cursor, textures, tex_index = (0x14, 8, 0x19) if game.startswith("GXX") else (0x18, 12, 0x1D)
            m.write(manager + cursor, 0x002A0046)
            m.write(manager + tex_index, 1, 1)
            m.write(manager + textures + 4, dynamic)
            m.load_data(dynamic + 0x10, bytes(range(20)))
            selections = []
            def hostile_call(machine):
                return_pc = machine.lr
                if machine.pc == spec[6]:
                    self.assertEqual(machine.reg[3], self.PAGE)
                    machine.write(self.PAGE + 0x28, self.PAGE + 128)
                else:
                    self.assertEqual(machine.reg[3], 0)
                    selections.append(machine.reg[4])
                for reg in (0, *range(3, 13)):
                    machine.reg[reg] = 0xDEAD0000 + reg
                for reg in range(14):
                    machine.fpr[reg] = (0xDEAD00000000 + reg, 0xBEEF00000000 + reg)
                machine.lr, machine.cr, machine.ctr, machine.xer = 1, 2, 3, 4
                machine.fpscr = 0xF0F0
                machine.pc = return_pc
            m.external[spec[6]] = m.external[spec[7]] = hostile_call
            for after, target in ((False, spec[3]), (True, spec[4])):
                code = 0x81200000 + int(after) * 0x2000
                displaced = 0x7CE30734 if not after else 0x808D0000 | spec[5]
                m.load_code(code, bridge._drawing(code, target, displaced, self.STATE, spec, after=after))
                before, floats = m.reg[:], m.fpr[:]
                special = m.lr, m.cr, m.ctr, m.xer, m.fpscr
                m.pc = code
                m.run(target + 4)
                expected = before[:]
                if after:
                    expected[4] = manager
                    self.assertEqual(m.read(manager + cursor), 0x002A0046)
                else:
                    expected[3] = ((before[7] & 65535) - 65536) & MASK
                    self.assertEqual(m.read(manager + cursor, 2), row["x"])
                    self.assertEqual(m.read(manager + cursor + 2, 2), row["y"])
                self.assertEqual(m.reg, expected)
                self.assertEqual(m.fpr, floats)
                self.assertEqual((m.lr, m.cr, m.ctr, m.xer, m.fpscr), special)
            self.assertEqual(selections, [self.PAGE, dynamic])
            self.assertEqual(m.read(self.STATE + 16), 0)
            self.assertEqual(m.read(self.STATE + 20), 41)


class InstallGlyphBridge(unittest.TestCase):
    def test_exact_declared_xd_tail_accepts_canonical_current_for_eu_and_japan(self):
        canonical = bytearray(0x300)
        struct.pack_into(">I", canonical, 0, 0x100)
        struct.pack_into(">I", canonical, 0x48, 0x80003000)
        struct.pack_into(">I", canonical, 0x90, 0x200)
        struct.pack_into(">I", canonical, 0xE0, 0x80003000)
        canonical = bytes(canonical)
        declared = canonical + bytes(224)
        for game in ("GXXP01", "GXXJ01"):
            spec = (hashlib.sha256(canonical).hexdigest(), *bridge._REGIONS[game][1:])
            with patch.dict(bridge._REGIONS, {game: spec}), patch.dict(bridge._EXACT_DOL_VARIANTS,
                    {game: {hashlib.sha256(declared).hexdigest()}}):
                self.assertEqual(bridge._normalize_current(declared, canonical, game), (declared, 224))
                modified = bytearray(canonical)
                modified[0x180] = 9
                result, added = bridge._normalize_current(declared, bytes(modified), game)
                self.assertEqual(result, bytes(modified) + bytes(224))
                self.assertEqual(added, 224)
                modified[0x94] = 1
                with self.assertRaises(FormatError):
                    bridge._normalize_current(declared, bytes(modified), game)
                with self.assertRaises(FormatError):
                    bridge._normalize_current(declared, canonical[:-1], game)

    def test_all_pages_align_and_only_qualified_original_words_change(self):
        original = bytearray(0x900)
        struct.pack_into(">I", original, 4, 0x100)
        struct.pack_into(">I", original, 0x4C, 0x80003000)
        struct.pack_into(">I", original, 0x94, 0x800)
        struct.pack_into(">I", original, 0xE0, 0x80003000)
        make, pre, post, get, load, select, setter = (0x80003020, 0x80003060, 0x800030A0,
            0x80003140, 0x80003240, 0x80003500, 0x800036E0)
        def at(a):
            return 0x100 + a - 0x80003000
        for a, w in ((make, 0x9421FF20), (pre, 0x7CE30734), (post, 0x808D82E8),
                     (get, 0x810D82E8), (setter, 0x906D8168), (setter + 4, 0x4E800020)):
            struct.pack_into(">I", original, at(a), w)
        original = bytes(original)
        spec = (hashlib.sha256(original).hexdigest(), make, 0x100, pre, post, 0x82E8, load, select, get)
        region = SimpleNamespace(section_ram=0x80600000, set_arena_lo=setter, arena_lo_store=0x906D8168)
        glyphs = [Glyph(0, code, 23, 22, 0, bytes([code & 255]) * 264, "math", code) for code in range(32, 1232)]
        with patch.dict(bridge._REGIONS, {"GC6P01": spec}), patch.object(bridge, "dol_layout", return_value=region):
            output, plan = bridge.prepare_text_bridge(original, original, "GC6P01", glyphs)
            again = bridge.prepare_text_bridge(original, original, "GC6P01", glyphs)
            self.assertEqual((output, plan), again)
            with self.assertRaises(FormatError):
                bridge.prepare_text_bridge(original, output, "GC6P01", glyphs)
        self.assertGreater(plan["pages"], 1)
        self.assertEqual(plan["counter_layout"], bridge.COUNTER_LAYOUT)
        self.assertTrue(all(r["address"] % 32 == 0 and r["file_offset"] % 32 == 0 for r in plan["page_records"]))
        selected, _ = bridge.select_runtime_glyphs(glyphs, "GC6P01")
        pages, _ = build_native_pages(selected)
        self.assertEqual([hashlib.sha256(p).hexdigest() for p in bridge.native_text_pages(output, plan)],
                         [hashlib.sha256(p).hexdigest() for p in pages])
        allowed = {p + j for p in (8, 0x50, 0x98, at(setter), at(make), at(pre), at(post), at(get)) for j in range(4)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(original, output))))
        self.assertEqual(next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")["size"], plan["section_bytes"])
        corrupt = bytearray(output)
        corrupt[plan["page_records"][0]["file_offset"] + 128] ^= 1
        with self.assertRaises(FormatError):
            bridge.native_text_pages(bytes(corrupt), plan)
