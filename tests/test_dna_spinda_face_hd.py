"""Synthetic DOL and independent PPC execution; no game data or Dolphin."""
import hashlib
import struct
import unittest
from copy import deepcopy
from unittest.mock import patch

from orre_randomizer.engine import dna_spinda_face_hd as b
from orre_randomizer.engine.analyze_game import FormatError, parse_dol, u32
from orre_randomizer.engine.gift_move_hooks import _arena_guard, branch
from tests.test_dna_hd_tiles import PPC as BasePPC


class PPC(BasePPC):
    """Add integer operations to the existing independent fixture interpreter."""
    def run(self, stop, limit=20000):
        # The base interpreter intentionally fails when one instruction does
        # not reach stop within the single-step budget. Its state is retained.
        for _ in range(limit):
            if self.pc == stop:
                return
            if self.pc in self.external:
                self.external[self.pc](self)
                continue
            word = self.code[self.pc]
            op = word >> 26
            rt, ra, rb = ((word >> shift) & 31 for shift in (21, 16, 11))
            if word == 0x4E800020:
                self.pc = self.lr
            elif word == 0x7C0004AC:  # sync
                self.pc += 4
            elif op in (46, 47):
                offset = word & 65535
                offset -= 65536 if offset & 32768 else 0
                for index in range(rt, 32):
                    address = self.reg[ra] + offset + (index - rt) * 4
                    if op == 47:
                        self.write(address, self.reg[index])
                    else:
                        self.reg[index] = self.read(address)
                self.pc += 4
            elif op == 40:
                signed = word & 65535
                signed -= 65536 if signed & 32768 else 0
                self.reg[rt] = self.read((self.reg[ra] + signed) & 0xFFFFFFFF, 2)
                self.pc += 4
            elif op == 21:
                shift, left, right = rb, (word >> 6) & 31, (word >> 1) & 31
                value = self.reg[rt]
                rotated = ((value << shift) | (value >> ((32 - shift) % 32))) & 0xFFFFFFFF
                mask = sum(1 << (31 - i) for i in range(32)
                           if (left <= i <= right if left <= right else i >= left or i <= right))
                self.reg[ra] = rotated & mask
                self.pc += 4
            elif op == 31 and (word >> 1) & 1023 in (40, 444):
                if (word >> 1) & 1023 == 40:
                    self.reg[rt] = (self.reg[rb] - self.reg[ra]) & 0xFFFFFFFF
                else:
                    self.reg[ra] = self.reg[rt] | self.reg[rb]
                self.pc += 4
            else:
                try:
                    super().run(stop, limit=1)
                except AssertionError as error:
                    if str(error) != "bridge failed to reach the native continuation":
                        raise
        raise AssertionError("Spinda face hook did not return")


def fixture(game_id="GC6P01"):
    profile = deepcopy(b._PROFILES[game_id])
    base, length = 0x80003100, 0x240000
    raw = bytearray(0x100 + length)
    for at, value in ((0, 0x100), (0x48, base), (0x90, length),
                       (0xD8, 0x80300000), (0xDC, 0x1000), (0xE0, base)):
        struct.pack_into(">I", raw, at, value)
    for name in ("factory", "setup"):
        at = 0x100 + profile[name] - base
        raw[at:at + 64] = bytes.fromhex(profile[name + "_window"])
    struct.pack_into(">I", raw, 0x100 + profile["arena_setter"] - base, profile["arena_store"])
    profile["source_dol_sha256"] = hashlib.sha256(raw).hexdigest()
    return bytes(raw), profile


def machine(kind="setup", game_id="GC6P01"):
    p = b.bridge_profile(game_id)
    origin, control = 0x80500000, 0x80510000
    buffers = (control + 512, control + 512 + b.BUFFER_BYTES)
    m = PPC()
    payload = b._setup_stub(origin, control, buffers, p) if kind == "setup" else b._factory_stub(origin, control, p)
    m.load_code(origin, payload)
    m.pc, m.lr = origin, 0x81300000
    m.write(control + b.FIELDS["active_bank"], b.NONE)
    m.write(control + b.FIELDS["ready_bank"], b.NONE)
    m.write(p["vi"], 100)
    # Simulate the original first stack allocation executed in the trampoline;
    # the rest of each native function is an ABI-clobbering external callee.
    def native_return(cpu):
        cpu.reg[1] += 0x80 if kind == "setup" else 0x50
        cpu.pc = cpu.lr
    m.external[p[kind] + 4] = native_return
    def external(cpu):
        target, pc = cpu.pc, cpu.lr
        cpu.calls.append((target, cpu.reg[3], cpu.reg[4]))
        for index in (0, *range(3, 13)):
            cpu.reg[index] = 0xDEAD0000 + index
        cpu.cr, cpu.xer, cpu.ctr = 0xBEEF1234, 0x12345678, 0x98765432
        cpu.pc = pc
    for name in ("draw_done", "dc_invalidate", "gx_invalidate"):
        m.external[p[name]] = external
    return m, origin, control, buffers, p


def set_request(m, c, epoch=1, pid=0x12345678, profile=None):
    tobj, desc, pixels = 0x80900000, 0x80901000, 0x80902000
    m.reg[3] = tobj
    m.write(tobj + 0x58, desc)
    for at, value in ((0, pixels), (4, 0x00800080), (8, 4)):
        m.write(desc + at, value)
    for at, value in ((0, epoch), (4, pixels), (8, pid)):
        m.write(c + 128 + at, value)
    m.write(c + 8, 1)
    m.write(c + 12, 100)
    m.write((profile or b.bridge_profile())["analyzer"], 0x80800000)
    m.write(0x8080000C, 308, 2)
    m.write(0x80800168, 0x80810000)
    return tobj, desc, pixels


class CompositionTests(unittest.TestCase):
    def test_all_three_exact_profiles_patch_and_unvalidated_regions_are_explicit(self):
        for game in b.PATCHABLE_GAME_IDS:
            original, profile = fixture(game)
            with patch.dict(b._PROFILES[game], profile):
                result, info = b.patch_spinda_face_bridge(original, original, game)
            self.assertEqual(info["game_id"], game)
            self.assertEqual(info["source_dol_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(info["production_validated"], b.face_runtime_validated(game))
            self.assertEqual(result[0x400:0x408], original[0x400:0x408])
        self.assertTrue(b.face_runtime_validated("GC6P01"))
        self.assertTrue(b.face_runtime_validated("GC6E01"))
        self.assertFalse(b.face_runtime_validated("GC6J01"))
        for game, revision in (("GXXP01", 0), ("GC6P01", 1), ("GC6P01", True)):
            with self.assertRaises(FormatError):
                b.bridge_profile(game, revision)

    def test_pristine_and_guarded_dol_preserve_existing_code_and_native_descriptors(self):
        for existing in (False, True):
            original, profile = fixture()
            current = bytearray(original)
            current[0x400:0x408] = b"seeddata"
            offset = (len(original) + 31) & ~31
            sentinel = bytes.fromhex("60000000") * 24
            if existing:
                body = _arena_guard(profile["base"] + 32 + len(sentinel), profile["arena_store"]) + sentinel
                current.extend(bytes(offset - len(current)) + body)
                for at, value in ((8, offset), (0x50, profile["base"]), (0x98, len(body))):
                    struct.pack_into(">I", current, at, value)
                struct.pack_into(">I", current, 0x100 + profile["arena_setter"] - 0x80003100,
                                 branch(profile["arena_setter"], profile["base"]))
            with patch.dict(b._PROFILE, profile):
                output, metadata = b.patch_spinda_face_bridge(original, bytes(current))
            self.assertEqual(output[0x400:0x408], b"seeddata")
            if existing:
                self.assertEqual(output[offset + 32:offset + len(body)], sentinel)
            self.assertEqual(output[offset:offset + 32], _arena_guard(metadata["reserved_end"], profile["arena_store"]))
            self.assertEqual(metadata["hd_texture_maps"], 5)
            self.assertFalse(metadata["hd_materials_embedded"])
            self.assertTrue(metadata["production_validated"])
            for buffer in metadata["buffers"]:
                self.assertEqual(buffer % 32, 0)
            self.assertLess(metadata["section_bytes"], 1060000)
            parse_dol(output)

    def test_reject_unknown_source_hook_and_bad_existing_arena_before_output(self):
        original, profile = fixture()
        for kind in ("source", "hook", "arena"):
            modified = bytearray(original)
            at = 0x100 + profile["factory"] - 0x80003100 if kind == "hook" else 0x400
            modified[at] ^= 1
            if kind == "arena":
                struct.pack_into(">I", modified, 0x98, 32)
            with patch.dict(b._PROFILE, profile), self.assertRaises(FormatError):
                b.patch_spinda_face_bridge(bytes(modified) if kind == "source" else original, bytes(modified))


class NativeProtocolTests(unittest.TestCase):
    def test_acknowledged_packet_resumes_after_fallback_and_active_packet_is_not_replayed(self):
        m, origin, c, buffers, p = machine()
        tobj, desc, pixels = set_request(m, c)
        for name, value in (("ready_bank", 0), ("ready_epoch", 1), ("ready_pixels", pixels),
                            ("ready_pid", 0x12345678), ("ready_serial", 1),
                            ("ack_serial", 1), ("ready_commit", 1)):
            m.write(c + b.FIELDS[name], value)
        def draw():
            m.pc, m.lr, m.reg[3] = origin, 0x81300000, tobj
            m.run(0x81300000)
            self.assertEqual(m.read(tobj + 0x58), desc)
        draw()
        self.assertEqual(m.read(c + 20), 0)
        self.assertEqual(len(m.calls), 3)
        m.calls.clear()
        draw()
        self.assertEqual(m.calls, [])
        m.write(c + 8, 0)
        draw()
        self.assertEqual(m.read(c + 20), b.NONE)
        self.assertEqual(m.read(c + 76), 1)
        m.calls.clear()
        m.write(c + 8, 1)
        draw()
        self.assertEqual(m.read(c + 20), 0)
        self.assertEqual(m.read(c + 24), 1)
        self.assertEqual([row[0] for row in m.calls], [p["draw_done"], p["dc_invalidate"], p["gx_invalidate"]])

    def test_every_regional_profile_uses_its_own_analyzer_and_tick_and_publishes_after_its_gpu_fence(self):
        for game in b.PATCHABLE_GAME_IDS:
            m, origin, c, buffers, p = machine(game_id=game)
            tobj, desc, pixels = set_request(m, c, profile=p)
            for name, value in (("ready_bank", 0), ("ready_epoch", 1), ("ready_pixels", pixels),
                                ("ready_pid", 0x12345678), ("ready_serial", 1), ("ready_commit", 1)):
                m.write(c + b.FIELDS[name], value)
            m.run(0x81300000)
            self.assertEqual(m.read(c + 20), 0, game)
            self.assertEqual(m.read(c + 24), 1, game)
            self.assertEqual(m.read(tobj + 0x58), desc, game)
            self.assertEqual([row[0] for row in m.calls], [p["draw_done"], p["dc_invalidate"], p["gx_invalidate"]], game)

    def test_field_or_battle_spinda_without_the_active_dna_view_stay_native(self):
        m, origin, c, buffers, p = machine()
        tobj, desc, pixels = set_request(m, c)
        m.write(p["analyzer"], 0)
        m.run(0x81300000)
        self.assertEqual(m.read(tobj + 0x58), desc)
        self.assertEqual(m.read(c + 28), 0)
        self.assertEqual(m.calls, [])

    def test_absent_or_expired_companion_uses_native_and_releases_gpu_bank_after_fence(self):
        for enabled, heartbeat, active in ((0, 100, b.NONE), (1, 69, 0), (0, 100, 1)):
            m, origin, c, buffers, p = machine()
            tobj, desc, pixels = set_request(m, c)
            m.write(c + 8, enabled)
            m.write(c + 12, heartbeat)
            m.write(c + 20, active)
            native_desc = []
            def native(cpu):
                native_desc.append(cpu.read(tobj + 0x58))
                cpu.reg[1] += 0x80
                cpu.pc = cpu.lr
            m.external[p["setup"] + 4] = native
            before = m.reg[14:]
            sp = m.reg[1]
            m.run(0x81300000)
            self.assertEqual(native_desc, [desc])
            self.assertEqual(m.read(tobj + 0x58), desc)
            self.assertEqual(m.read(c + 20), b.NONE)
            self.assertEqual(m.reg[14:], before)
            self.assertEqual(m.reg[1], sp)
            self.assertEqual([row[0] for row in m.calls], [] if active == b.NONE else [p["draw_done"]])

    def test_publish_complete_descriptor_fence_invalidate_then_restore_all_five_maps(self):
        for bank in (0, 1):
            m, origin, c, buffers, p = machine()
            tobj, desc, pixels = set_request(m, c)
            # The initial request is emitted by this same callback, serial1.
            for name, value in (("ready_bank", bank), ("ready_epoch", 1), ("ready_pixels", pixels),
                                ("ready_pid", 0x12345678), ("ready_serial", 1), ("ready_commit", 1)):
                m.write(c + b.FIELDS[name], value)
            seen = []
            def native(cpu):
                seen.append(cpu.read(tobj + 0x58))
                cpu.reg[1] += 0x80
                cpu.pc = cpu.lr
            m.external[p["setup"] + 4] = native
            # Feature chain bytes are mathematical sentinels. None may change.
            features = bytes((i * 29 + 7) & 255 for i in range(0x300))
            m.load_data(tobj + 0xAC, features)
            m.run(0x81300000)
            self.assertEqual(seen, [c + 256 + bank * 32])
            self.assertEqual(m.read(tobj + 0x58), desc)
            self.assertEqual(m.read(c + 20), bank)
            self.assertEqual(m.read(c + 24), 1)
            self.assertEqual(m.read(c + 76), 1)
            self.assertEqual([row[0] for row in m.calls], [p["draw_done"], p["dc_invalidate"], p["gx_invalidate"]])
            self.assertEqual(m.calls[1][1:], (buffers[bank], b.BUFFER_BYTES))
            self.assertEqual(bytes(m.mem[tobj + 0xAC + i] for i in range(len(features))), features)

    def test_stale_pid_epoch_serial_commit_or_active_bank_are_rejected_and_acknowledged(self):
        for field, value in (("ready_pid", 7), ("ready_epoch", 2), ("ready_serial", 2),
                             ("ready_commit", 3), ("ready_pixels", 0x80903000), ("ready_bank", 2)):
            m, origin, c, buffers, p = machine()
            tobj, desc, pixels = set_request(m, c)
            values = {"ready_bank": 0, "ready_epoch": 1, "ready_pixels": pixels,
                      "ready_pid": 0x12345678, "ready_serial": 1, "ready_commit": 1}
            values[field] = value
            for name, v in values.items():
                m.write(c + b.FIELDS[name], v)
            m.run(0x81300000)
            self.assertEqual(m.read(c + 20), b.NONE, field)
            self.assertEqual(m.read(c + 76), values["ready_serial"], field)
            self.assertEqual(m.read(tobj + 0x58), desc)
            self.assertEqual(m.calls, [])

    def test_factory_registers_full_pid_and_bounded_ring_without_touching_saved_data(self):
        m, origin, c, buffers, p = machine("factory")
        texture, pixels = 0x80900000, 0x80902000
        m.write(texture, 0x00800080)
        m.write(texture + 0x28, pixels)
        def native(cpu):
            cpu.reg[3] = texture
            cpu.reg[1] += 0x50
            cpu.pc = cpu.lr
        m.external[p["factory"] + 4] = native
        before = m.reg[14:]
        for index in range(20):
            m.pc, m.lr = origin, 0x81300000
            m.reg[5] = 0xABC00000 + index
            m.run(0x81300000)
            serial = index + 1
            at = c + 128 + (serial % 8) * 16
            self.assertEqual([m.read(at + i * 4) for i in range(4)],
                             [serial, pixels, 0xABC00000 + index, texture])
            self.assertEqual(m.reg[14:], before)
        self.assertEqual(m.read(c + 88), 20)


if __name__ == "__main__":
    unittest.main()
