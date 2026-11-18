"""Independent PPC execution and composition checks; no ROM or emulator needed."""
from copy import deepcopy
import hashlib
import json
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError, parse_dol, u32
from orre_randomizer.engine.gift_move_hooks import _arena_guard, branch
from orre_randomizer.engine import play_music_bridge as bridge


MASK = 0xFFFFFFFF


class PPC:
    """Small interpreter independent of the emitter and its label relocation."""

    def __init__(self, code, address):
        self.code = {address + i: int.from_bytes(code[i:i + 4], "big") for i in range(0, len(code), 4)}
        self.pc = address
        self.reg = [0x12340000 + i * 257 for i in range(32)]
        self.reg[1] = 0x81200000
        self.mem = {}
        self.cr, self.xer, self.lr, self.ctr = 0xA53C9876, 0xA000007F, 0xDEAD1234, 0xABCD5678

    def write(self, address, value, width=4):
        for i, byte in enumerate((value & ((1 << (8 * width)) - 1)).to_bytes(width, "big")):
            self.mem[address + i] = byte

    def read(self, address, width=4):
        return int.from_bytes(bytes(self.mem.get(address + i, 0) for i in range(width)), "big")

    def compare(self, left, right):
        field = (8 if left < right else 4 if left > right else 2) | ((self.xer >> 31) & 1)
        self.cr = (self.cr & 0x0FFFFFFF) | (field << 28)

    def run(self, stop):
        for _ in range(5000):
            if self.pc == stop:
                return
            pc = self.pc
            word = self.code[pc]
            self.pc += 4
            opcode = word >> 26
            rs, ra, rb = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
            imm = word & 0xFFFF
            signed = imm - 0x10000 if imm & 0x8000 else imm
            if word == 0x7C000026:
                self.reg[0] = self.cr
            elif word == 0x7C0FF120:
                self.cr = self.reg[0]
            elif opcode in (14, 15):
                self.reg[rs] = ((self.reg[ra] if ra else 0) + (signed << (16 if opcode == 15 else 0))) & MASK
            elif opcode == 24:
                self.reg[ra] = self.reg[rs] | imm
            elif opcode == 28:
                self.reg[ra] = self.reg[rs] & imm
                self.compare(self.reg[ra], 0)
            elif opcode in (32, 34):
                self.reg[rs] = self.read((self.reg[ra] + signed) & MASK, 1 if opcode == 34 else 4)
            elif opcode in (36, 37):
                address = (self.reg[ra] + signed) & MASK
                self.write(address, self.reg[rs])
                if opcode == 37:
                    self.reg[ra] = address
            elif opcode == 10:
                self.compare(self.reg[ra], imm)
            elif opcode == 31 and (word >> 1) & 1023 == 32:
                self.compare(self.reg[ra], self.reg[rb])
            elif opcode == 31 and (word >> 1) & 1023 == 40:
                self.reg[rs] = (self.reg[rb] - self.reg[ra]) & MASK
            elif opcode == 16:
                bo, bi = (word >> 21) & 31, (word >> 16) & 31
                if bo not in (4, 12):
                    raise AssertionError(f"unsupported condition {word:08x}")
                condition = bool(self.cr & (1 << (31 - bi)))
                if condition == (bo == 12):
                    displacement = word & 0xFFFC
                    self.pc = pc + (displacement - 0x10000 if displacement & 0x8000 else displacement)
            elif opcode == 18:
                if word & 3:
                    raise AssertionError("gain hooks must preserve LR and use relative branches")
                displacement = word & 0x03FFFFFC
                self.pc = pc + (displacement - 0x04000000 if displacement & 0x02000000 else displacement)
            else:
                raise AssertionError(f"unsupported {word:08x} at {pc:08x}")
        raise AssertionError("gain hook did not resume native execution")


def native_fixture(game_id):
    profile = deepcopy(bridge._PROFILES[game_id])
    address, size = 0x80003100, 0x200000
    original = bytearray(0x100 + size)
    for offset, value in ((0, 0x100), (0x48, address), (0x90, size),
                          (0xD8, 0x80300000), (0xDC, 0x1000), (0xE0, address)):
        struct.pack_into(">I", original, offset, value)
    arena = profile["arena_setter"] - address + 0x100
    struct.pack_into(">II", original, arena, profile["arena_store"], 0x4E800020)
    for hook, window in zip(profile["hooks"], profile["hook_windows"], strict=True):
        pos = hook - address + 0x100
        original[pos:pos + 64] = bytes.fromhex(window)
    profile["source_dol_sha256"] = hashlib.sha256(original).hexdigest()
    return bytes(original), profile


class CompositionTests(unittest.TestCase):
    def test_public_fixed_profile_is_detached_and_rejects_unsupported_builds(self):
        profile = bridge.music_bridge_profile("GC6P01")
        self.assertEqual(profile["movie_player"], 0x804B80E0)
        self.assertNotIn("control", profile)
        self.assertNotIn("hook_windows", profile)
        profile["vi"] = 0
        self.assertNotEqual(bridge.music_bridge_profile("GC6P01")["vi"], 0)
        for game_id, revision in (("GC6E01", 0), ("GXXP01", 1), ("GC6P01", False)):
            with self.assertRaises(FormatError):
                bridge.music_bridge_profile(game_id, revision=revision)

    def test_pristine_and_existing_guarded_runtime_hooks_compose_for_both_games(self):
        for game_id in bridge.SUPPORTED_GAME_IDS:
            for existing in (False, True):
                with self.subTest(game_id=game_id, existing=existing):
                    original, profile = native_fixture(game_id)
                    current = bytearray(original)
                    current[0x400:0x408] = b"randomiz"
                    section_offset = (len(original) + 31) & ~31
                    if existing:
                        sentinel = bytes.fromhex("60000000") * 32
                        body = _arena_guard(profile["base"] + 32 + len(sentinel), profile["arena_store"]) + sentinel
                        current.extend(bytes(section_offset - len(current)))
                        current.extend(body)
                        for pos, value in zip((8, 0x50, 0x98), (section_offset, profile["base"], len(body)), strict=True):
                            struct.pack_into(">I", current, pos, value)
                        arena = bridge._offset(parse_dol(original), profile["arena_setter"])
                        struct.pack_into(">I", current, arena, branch(profile["arena_setter"], profile["base"]))
                    current = bytes(current)
                    with patch.dict(bridge._PROFILES, {game_id: profile}):
                        output, info = bridge.patch_music_bridge(original, current, game_id)
                    self.assertEqual(output[0x400:0x408], b"randomiz")
                    self.assertEqual(info["source_dol_sha256"], hashlib.sha256(original).hexdigest())
                    self.assertEqual(info["dol_sha256_before"], hashlib.sha256(current).hexdigest())
                    self.assertEqual(info["dol_sha256_after"], hashlib.sha256(output).hexdigest())
                    added = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
                    self.assertEqual(added["offset"] + added["size"], len(output))
                    self.assertEqual(output[section_offset:section_offset + 32], _arena_guard(info["reserved_end"], profile["arena_store"]))
                    if existing:
                        self.assertEqual(output[section_offset + 32:section_offset + len(body)], sentinel)
                        self.assertGreaterEqual(info["gain_hooks"][0]["stub_address"], profile["base"] + len(body))
                    mailbox = section_offset + info["control"] - profile["base"]
                    values = struct.unpack_from(">16I", output, mailbox)
                    self.assertEqual(values[:8], (0, 0, 0, 0, 0, 0, bridge.MAILBOX_MAGIC, bridge.BRIDGE_ABI))
                    self.assertEqual(mailbox + 64, len(output))
                    self.assertNotIn("original_dol", json.dumps(info))
                    allowed = info["allowed_changed_ranges"]
                    for pos, (before, after) in enumerate(zip(current, output)):
                        if before != after:
                            self.assertTrue(any(start <= pos < stop for start, stop in allowed), hex(pos))
                    with patch.dict(bridge._PROFILES, {game_id: profile}):
                        with self.assertRaisesRegex(FormatError, "context changed"):
                            bridge.patch_music_bridge(original, output, game_id)

    def test_rejects_unknown_identity_regions_revisions_and_current_hook_context(self):
        original, profile = native_fixture("GC6P01")
        with self.assertRaisesRegex(FormatError, "verified retail"):
            bridge.patch_music_bridge(original, original, "GC6P01")
        for game_id, revision in (("GC6E01", 0), ("GXXJ01", 0), ("GC6P01", 1), ("GC6P01", False)):
            with self.assertRaisesRegex(FormatError, "Europe revision 0"):
                bridge.patch_music_bridge(original, original, game_id, revision=revision)
        changed = bytearray(original)
        pos = bridge._offset(parse_dol(original), profile["hooks"][0])
        changed[pos + 60] ^= 1  # first prologue word alone is insufficient
        with patch.dict(bridge._PROFILES, {"GC6P01": profile}):
            with self.assertRaisesRegex(FormatError, "context changed"):
                bridge.patch_music_bridge(original, bytes(changed), "GC6P01")

    def test_rejects_foreign_cave_corrupt_guard_and_changed_arena_return(self):
        original, profile = native_fixture("GXXP01")
        for damage in ("foreign_section", "arena_return", "tail"):
            current = bytearray(original)
            if damage == "foreign_section":
                for pos, value in zip((8, 0x50, 0x98), (len(original), profile["base"], 32), strict=True):
                    struct.pack_into(">I", current, pos, value)
                current.extend(bytes(32))
            elif damage == "arena_return":
                pos = bridge._offset(parse_dol(original), profile["arena_setter"])
                current[pos + 4:pos + 8] = bytes(4)
            else:
                current.extend(bytes(32))
            with self.subTest(damage=damage), patch.dict(bridge._PROFILES, {"GXXP01": profile}):
                with self.assertRaises(FormatError):
                    bridge.patch_music_bridge(original, bytes(current), "GXXP01")


class GainHookExecutionTests(unittest.TestCase):
    def machine(self, kind, *, enabled=1, heartbeat=90, vi=100, hook_index=0):
        game_id = "GC6P01" if kind == "colosseum" else "GXXP01"
        profile = bridge._PROFILES[game_id]
        address, control, continuation = 0x80600020, 0x80608000, profile["hooks"][hook_index] + 4
        original = int(profile["hook_windows"][hook_index][:8], 16)
        machine = PPC(bridge._gain_stub(address, control, profile, original, continuation), address)
        machine.profile, machine.control, machine.stop = profile, control, continuation
        machine.native_frame = 0x10000 - (original & 0xFFFF)
        words = [enabled, heartbeat, 0, 0, 0, 0, bridge.MAILBOX_MAGIC, bridge.BRIDGE_ABI] + [0xFFFFFFFF] * 8
        for i, value in enumerate(words):
            machine.write(control + i * 4, value)
        machine.write(profile["vi"], vi)
        if kind == "colosseum":
            for i in range(8):
                machine.write(profile["fader"] + (23 + i) * 48 + 20, 0x3F800000 + i)
        else:
            machine.write(profile["movie_count_global"], 0)
        return machine

    def run_preserving(self, machine, *, stream_muted=False):
        before = machine.reg.copy()
        cr, xer, lr, ctr = machine.cr, machine.xer, machine.lr, machine.ctr
        machine.run(machine.stop)
        before[1] -= machine.native_frame  # replayed native stack prologue
        if stream_muted:
            before[4] = 0
        self.assertEqual(machine.reg, before)
        self.assertEqual((machine.cr, machine.xer, machine.lr, machine.ctr), (cr, xer, lr, ctr))
        self.assertEqual(machine.read(before[1]), before[1] + machine.native_frame)

    def test_colosseum_only_mutes_selected_music_groups_and_restores_after_lease_loss(self):
        machine = self.machine("colosseum")
        machine.write(machine.control + 8, 0b10000101)
        original = [machine.read(machine.profile["fader"] + (23 + i) * 48 + 20) for i in range(8)]
        self.run_preserving(machine)
        self.assertEqual(machine.read(machine.control + 12), 0b10000101)
        self.assertEqual(machine.read(machine.control + 16), 3)
        for i in range(8):
            self.assertEqual(machine.read(machine.profile["fader"] + (23 + i) * 48 + 20),
                             0 if (1 << i) & 0b10000101 else original[i])
        # A subsequent call with the heartbeat expired restores exact float bits.
        machine.pc = min(machine.code)
        machine.reg[1] = 0x81200000
        machine.write(machine.profile["vi"], 121)
        self.run_preserving(machine)
        self.assertEqual(machine.read(machine.control + 12), 0)
        self.assertEqual(machine.read(machine.control + 20), 3)
        for i in range(8):
            self.assertEqual(machine.read(machine.profile["fader"] + (23 + i) * 48 + 20), original[i])

    def test_stream_hooks_mute_only_selected_ids_preserving_other_native_arguments(self):
        for selected in (False, True):
            for hook_index in (0, 1):
                machine = self.machine("xd", hook_index=hook_index)
                machine.reg[3] = 42
                machine.write(machine.control + 32, 42 if selected else 43)
                self.run_preserving(machine, stream_muted=selected)
                self.assertEqual(machine.read(machine.control + (16 if selected else 20)), 1)

    def test_disabled_stale_future_or_incompatible_lease_uses_native_gain(self):
        for enabled, heartbeat, vi, magic, abi in (
                (0, 100, 100, bridge.MAILBOX_MAGIC, 1),
                (1, 69, 100, bridge.MAILBOX_MAGIC, 1),
                (1, 101, 100, bridge.MAILBOX_MAGIC, 1),
                (1, 100, 100, 0, 1), (1, 100, 100, bridge.MAILBOX_MAGIC, 2)):
            for kind in ("colosseum", "xd"):
                with self.subTest(kind=kind, enabled=enabled, heartbeat=heartbeat, magic=magic, abi=abi):
                    machine = self.machine(kind, enabled=enabled, heartbeat=heartbeat, vi=vi)
                    machine.write(machine.control + 8, 255)
                    machine.write(machine.control + 24, magic)
                    machine.write(machine.control + 28, abi)
                    machine.write(machine.control + 32, machine.reg[3])
                    self.run_preserving(machine)
                    self.assertEqual(machine.read(machine.control + 16), 0)

    def test_wrapping_vi_heartbeat_remains_valid(self):
        machine = self.machine("xd", heartbeat=0xFFFFFFF0, vi=14)  # exactly 30
        machine.write(machine.control + 32, machine.reg[3])
        self.run_preserving(machine, stream_muted=True)

    def test_native_colosseum_movie_immediately_restores_muted_music(self):
        machine = self.machine("colosseum")
        machine.write(machine.control + 8, 1)
        self.run_preserving(machine)
        self.assertEqual(machine.read(machine.control + 12), 1)
        machine.pc = min(machine.code)
        machine.reg[1] = 0x81200000
        player = machine.profile["movie_player"]
        machine.write(player + 0x3C, 0x54485000)
        machine.write(player + 0xA0, 1)
        machine.write(player + 0xA4, 2, 1)
        self.run_preserving(machine)
        self.assertEqual(machine.read(machine.control + 12), 0)
        self.assertEqual(machine.read(machine.profile["fader"] + 23 * 48 + 20), 0x3F800000)

    def test_xd_movie_state_three_bypasses_and_released_slots_allow_music(self):
        for status in (0, 1, 2, 3, 16):
            machine = self.machine("xd")
            machine.write(machine.control + 32, machine.reg[3])
            machine.write(machine.profile["movie_count_global"], 2)
            machine.write(machine.profile["movie_slots_global"], 0x80800000)
            machine.write(0x80800020, status)
            self.run_preserving(machine, stream_muted=status == 0)

    def test_invalid_xd_movie_table_falls_back_without_dereferencing(self):
        for count, table in ((33, 0x80800000), (0xFFFFFFFF, 0), (1, 0),
                             (1, 0x80800001), (32, 0x817FFC04), (1, 0xFFFFFFFF)):
            machine = self.machine("xd")
            machine.write(machine.control + 32, machine.reg[3])
            machine.write(machine.profile["movie_count_global"], count)
            machine.write(machine.profile["movie_slots_global"], table)
            original_read = machine.read

            def bounded_read(address, width=4):
                if address == table:
                    raise AssertionError("invalid movie pointer was followed")
                return original_read(address, width)

            machine.read = bounded_read
            self.run_preserving(machine)


if __name__ == "__main__":
    unittest.main()
