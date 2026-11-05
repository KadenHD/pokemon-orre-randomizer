"""Regional hooks executed by the existing independent PowerPC instruction models."""
import unittest
from unittest.mock import patch

import test_gift_move_hooks as gift_model
import test_shiny_rules as shiny_model
from orre_randomizer.engine.dol_regions import LAYOUTS, dol_layout
from orre_randomizer.engine.gift_move_hooks import _arena_guard, _gift_stub
from orre_randomizer.engine.shiny_rules import (
    _pid_wrapper, _seeded_trainer_wrapper, _ot_wrapper, _index_trampoline,
    chance_threshold)
from orre_randomizer.engine.analyze_game import FormatError


class RegionalHookExecutionTests(unittest.TestCase):
    def test_native_gift_calls_return_and_nonvolatile_registers_in_each_region(self):
        for region in LAYOUTS:
            with self.subTest(region=region.game_id), patch.multiple(gift_model,
                    NATIVE_CONSTRUCTOR=region.native_constructor, NATIVE_SET_MOVE=region.native_set_move):
                start = region.section_ram + 32
                m = gift_model.PPCMachine(_gift_stub(start, [33, 53, 94, 0], region=region), start)
                m.registers[3:7] = [0x80508000, 197, 26, 0xA5]
                before, link = m.registers.copy(), m.lr
                m.execute()
                self.assertEqual(m.calls[0], (region.native_constructor, before[3:7]))
                self.assertEqual([call[1][:3] for call in m.calls[1:]],
                                 [[before[3], slot, move] for slot, move in enumerate([33, 53, 94, 0])])
                self.assertTrue(all(call[0] == region.native_set_move for call in m.calls[1:]))
                self.assertEqual(m.registers[3], 0x11111111)
                self.assertEqual(m.registers[1:3], before[1:3])
                self.assertEqual(m.registers[13:], before[13:])
                self.assertEqual(m.lr, link)

    def test_arena_guard_stores_to_each_native_sdk_variable_including_japan(self):
        # Observed SDK r13 values and OS arenaLo absolute variables, independent
        # from the layout's encoded store instruction.
        sdk = {'GC6P01': (0x804CDCC0, 0x804C5E28),
               'GC6E01': (0x80480820, 0x80478988),
               'GC6J01': (0x8046BF00, 0x80464060)}
        for region in LAYOUTS:
            for argument in (0, region.section_ram, region.section_ram + 0x1000):
                with self.subTest(region=region.game_id, argument=argument):
                    bound = region.section_ram + 0x200
                    m = gift_model.PPCMachine(_arena_guard(bound, region.arena_lo_store), region.section_ram)
                    m.registers[13], variable = sdk[region.game_id]
                    m.registers[3] = argument
                    before = m.registers.copy()
                    m.execute()
                    self.assertEqual(m.memory[variable], max(argument, bound))
                    self.assertEqual(m.registers[1:], before[1:])

    def test_seeded_and_rng_wrappers_use_regional_owner_and_native_pid_abi(self):
        for region in LAYOUTS:
            with self.subTest(region=region.game_id), patch.multiple(shiny_model,
                    NATIVE_RNG=region.native_rng, PID_GENERATOR=region.pid_generator):
                start = region.section_ram + 32
                wrappers = [
                    (_pid_wrapper(start, chance_threshold(50), trainers=True, region=region), (0, 0), 1),
                    (_seeded_trainer_wrapper(start, 0x81600000, 0x81602000, region=region), (), 1)]
                for code, rng, expected in wrappers:
                    m = shiny_model.Machine(code, start, rng)
                    m.reg[3:8] = [0x80508000, 1, 7, 0, 0x11112222]
                    m.reg[30] = 22
                    m.write(region.player_pointer, 0x80510000)
                    m.write(0x8051009C, 0x2468ABCD)
                    m.write(m.reg[1] + 0x48, 5)
                    m.write(0x81602000 + 22, 1, 1)
                    before, link = m.reg.copy(), m.lr
                    m.run()
                    self.assertEqual([args for target, args in m.calls if target == region.pid_generator],
                                     [[before[3], 1, 7, expected, 0x2468ABCD]])
                    self.assertEqual(m.reg[1:3], before[1:3])
                    self.assertEqual(m.reg[13:], before[13:])
                    self.assertEqual(m.lr, link)

    def test_ot_hook_and_index_trampoline_return_to_the_regional_continuation(self):
        for region in LAYOUTS:
            with self.subTest(region=region.game_id):
                start = region.section_ram + 32
                m = shiny_model.Machine(_index_trampoline(start, region=region), start)
                m.reg[3] = 1234
                before, link = m.reg.copy(), m.lr
                m.run(stop=region.trainer_index_hook + 4)
                self.assertEqual(m.read(before[1] + 0x48), 1234)
                self.assertEqual(m.reg[28], 1234)
                self.assertEqual(m.lr, link)
                m = shiny_model.Machine(_ot_wrapper(start, region=region), start)
                obj = 0x80508000
                m.reg[26] = obj
                m.write(obj + 0xD8, 1, 2)
                m.write(obj + 0xDC, 1000)
                m.write(region.player_pointer, 0x80510000)
                m.write(0x8051009C, 0x2468ABCD)
                before = m.reg.copy()
                for r in range(26, 32):
                    m.write(m.reg[1] + 8 + (r - 26) * 4, 0xCAFE0000 + r)
                m.run(stop=region.ot_exit + 4)
                self.assertEqual(m.read(obj + 0x14), 0x2468ABCD)
                self.assertEqual(m.reg[1], before[1])
                self.assertEqual(m.reg[3], before[3])
                self.assertEqual(m.reg[26:], [0xCAFE0000 + r for r in range(26, 32)])

    def test_unknown_and_modified_executables_are_not_guessed_from_size(self):
        for size in (128, 3779808, 3699680):
            with self.assertRaises(FormatError):
                dol_layout(bytes(size))


if __name__ == '__main__':
    unittest.main()
