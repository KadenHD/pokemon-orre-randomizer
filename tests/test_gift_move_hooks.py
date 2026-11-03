"""Independent PPC-subset execution checks for the emitted gift/arena stubs."""
from pathlib import Path
import struct
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError, parse_dol
from colosseum_randomizer.engine.gift_move_hooks import (
    _arena_guard, _gift_stub, branch, patch_gift_moves, GIFT_BASES,
    NATIVE_CONSTRUCTOR, NATIVE_SET_MOVE, SECTION_RAM, SET_ARENA_LO, TEXT_TO_RAM,
)

MASK = 0xFFFFFFFF


class PPCMachine:
    """Execute only the documented integer instructions emitted by this module.

    Native constructor and setter calls are external test doubles with ordinary
    volatile-register clobbers, different return values, and recorded arguments.
    This is an ABI/instruction test, not a game-runtime emulation claim.
    """
    def __init__(self, code, address):
        self.instructions = {address + p: word[0] for p, word in
                             zip(range(0, len(code), 4), struct.iter_unpack(">I", code))}
        self.registers = [((index + 1) * 0x01010101) & MASK for index in range(32)]
        self.registers[1] = 0x80500000
        self.registers[13] = 0x804CDCC0
        self.lr = 0x81234560
        self.memory = {}
        self.calls = []
        self.pc = address
        self.less_than = False

    def execute(self):
        return_address = self.lr
        for _ in range(300):
            if self.pc == return_address:
                return
            instruction = self.instructions[self.pc]
            old_pc = self.pc
            self.pc += 4
            opcode = instruction >> 26
            first, second, third = ((instruction >> shift) & 31 for shift in (21, 16, 11))
            immediate = instruction & 0xFFFF
            signed = immediate - 0x10000 if immediate & 0x8000 else immediate
            if instruction == 0x7C0802A6:       # mflr r0
                self.registers[0] = self.lr
            elif instruction == 0x7C0803A6:     # mtlr r0
                self.lr = self.registers[0]
            elif instruction == 0x4E800020:     # blr
                self.pc = self.lr
            elif instruction == 0x7C030040:     # cmplw r3,r0
                self.less_than = self.registers[3] < self.registers[0]
            elif instruction == 0x4080000C:     # bge +12
                if not self.less_than:
                    self.pc = old_pc + 12
            elif opcode == 14:                 # addi / li
                self.registers[first] = ((self.registers[second] if second else 0) + signed) & MASK
            elif opcode == 15:                 # addis / lis
                self.registers[first] = ((self.registers[second] if second else 0) + (signed << 16)) & MASK
            elif opcode == 24:                 # ori rA,rS,immediate
                self.registers[second] = self.registers[first] | immediate
            elif opcode in (36, 37):           # stw / stwu
                address = (self.registers[second] + signed) & MASK
                self.memory[address] = self.registers[first]
                if opcode == 37:
                    self.registers[second] = address
            elif opcode == 32:                 # lwz
                address = (self.registers[second] + signed) & MASK
                self.registers[first] = self.memory[address]
            elif opcode == 31 and (instruction >> 1) & 0x3FF == 444:  # or / mr
                self.registers[second] = self.registers[first] | self.registers[third]
            elif opcode == 18:                 # relative b / bl
                self.assert_relative(instruction)
                displacement = instruction & 0x03FFFFFC
                if displacement & 0x02000000:
                    displacement -= 0x04000000
                target = old_pc + displacement
                if instruction & 1:
                    self.lr = old_pc + 4
                if target in (NATIVE_CONSTRUCTOR, NATIVE_SET_MOVE):
                    self.native_call(target)
                    self.pc = self.lr
                else:
                    self.pc = target
            else:
                raise AssertionError(f"unsupported emitted instruction {instruction:#010x} at {old_pc:#x}")
        raise AssertionError("stub did not return")

    @staticmethod
    def assert_relative(instruction):
        if instruction & 2:
            raise AssertionError("absolute branch is not allowed")

    def native_call(self, target):
        self.calls.append((target, self.registers[3:7].copy()))
        for index in (0, 4, 5, 6, 7, 8, 9, 10, 11, 12):
            self.registers[index] = 0xDEAD0000 | index
        self.registers[3] = 0x11111111 if target == NATIVE_CONSTRUCTOR else 0x22222222


class GiftHookInstructionTests(unittest.TestCase):
    def test_wrapper_preserves_abi_and_constructor_result(self):
        moves = [33, 53, 94, 120]
        machine = PPCMachine(_gift_stub(SECTION_RAM + 32, moves), SECTION_RAM + 32)
        machine.registers[3:7] = [0x8050AB00, 197, 26, 0x1234]
        before = machine.registers.copy()
        link = machine.lr
        machine.execute()
        self.assertEqual(machine.calls[0], (NATIVE_CONSTRUCTOR, before[3:7]))
        self.assertEqual(len(machine.calls), 5)
        for slot, (target, arguments) in enumerate(machine.calls[1:]):
            self.assertEqual(target, NATIVE_SET_MOVE)
            self.assertEqual(arguments[:3], [before[3], slot, moves[slot]])
        self.assertEqual(machine.registers[3], 0x11111111)
        self.assertEqual(machine.registers[1:3], before[1:3])
        self.assertEqual(machine.registers[13:], before[13:])
        self.assertEqual(machine.lr, link)
        self.assertEqual(machine.memory[before[1] - 48], before[1])

    def test_arena_low_is_clamped_without_changing_argument(self):
        bound = SECTION_RAM + 544
        for argument in (0, SECTION_RAM, bound - 1, bound, bound + 0x1000, 0x81700000, 0xFFFFFFFF):
            with self.subTest(argument=hex(argument)):
                machine = PPCMachine(_arena_guard(bound), SECTION_RAM)
                machine.registers[3] = argument
                before = machine.registers.copy()
                machine.execute()
                variable = (before[13] - 0x7E98) & MASK
                self.assertEqual(machine.memory[variable], max(argument, bound))
                self.assertEqual(machine.registers[1:], before[1:])

    def test_branch_range_and_alignment(self):
        for source, target in ((0, 1), (0, 1 << 25), (1 << 25, -4)):
            with self.assertRaises(FormatError):
                branch(source, target)


ORIGINAL = Path(__file__).resolve().parents[1] / "game/sys/main.dol"


@unittest.skipUnless(ORIGINAL.is_file(), "requires user's original PAL DOL")
class GiftHookIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ORIGINAL.read_bytes()

    def test_all_gifts_have_separate_stubs_and_exact_change_ranges(self):
        requested = {key: [33 + index, 53, 94, 354] for index, key in enumerate(GIFT_BASES)}
        result, report = patch_gift_moves(self.original, self.original, requested)
        self.assertEqual(len(result), len(self.original) + 544)
        sections = parse_dol(result)["sections"]
        self.assertEqual(sections[-1]["name"], "data5")  # parser lists text then data
        added = next(row for row in sections if row["name"] == "text2")
        self.assertEqual(added["ram_address"], SECTION_RAM)
        self.assertEqual(added["size"], 544)
        self.assertEqual(len(report["gift_hooks"]), 4)
        allowed = {index for lo, hi in report["allowed_changed_ranges"] for index in range(lo, min(hi, len(self.original)))}
        changed = {i for i, (old, new) in enumerate(zip(self.original, result)) if old != new}
        self.assertLessEqual(changed, allowed)
        for hook in report["gift_hooks"]:
            code = result[hook["stub_offset"]:hook["stub_offset"] + hook["stub_size"]]
            machine = PPCMachine(code, hook["stub_address"])
            machine.registers[3:7] = [0x80507700, 123, 70, 1]
            machine.execute()
            self.assertEqual([call[1][2] for call in machine.calls[1:]], requested[hook["key"]])
        self.assertEqual(result[SET_ARENA_LO - TEXT_TO_RAM + 4:SET_ARENA_LO - TEXT_TO_RAM + 8], bytes.fromhex("4e800020"))

    def test_empty_does_nothing_and_single_gift_is_scoped(self):
        self.assertEqual(patch_gift_moves(self.original, self.original, {})[0], self.original)
        modified, report = patch_gift_moves(self.original, self.original, {"plusle": [1, 2, 3, 4]})
        self.assertEqual(report["section"]["size"], 160)
        for name, base in GIFT_BASES.items():
            if name != "plusle":
                self.assertEqual(modified[base:base + 0xA0], self.original[base:base + 0xA0])

    def test_invalid_moves_or_modified_hook_are_rejected(self):
        for requested in ({"umbreon": [1, 2, 3, 4]}, {"plusle": [1, 2, 3]},
                          {"plusle": [1, 2, 3, 356]}, {"plusle": [1, 2, 3, 165]},
                          {"plusle": [1, 2, 3, True]}):
            with self.assertRaises(FormatError):
                patch_gift_moves(self.original, self.original, requested)
        corrupt = bytearray(self.original)
        corrupt[SET_ARENA_LO - TEXT_TO_RAM] ^= 1
        with self.assertRaises(FormatError):
            patch_gift_moves(self.original, bytes(corrupt), {"plusle": [1, 2, 3, 4]})


if __name__ == "__main__":
    unittest.main()
