"""Execute the emitted Shadow wrappers through native-call boundaries.

The decoder is independent of the builders. Native probes only check wrapper
arguments and emulate ABI clobbers; they do not simulate the game's PID logic.
"""
from types import SimpleNamespace
import unittest

from orre_randomizer.xd_shadow_shinies import (
    SHADOW_COUNT, _owner_stub, _pid_stub, shadow_statuses,
)


MASK = 0xFFFFFFFF
ADDRESS = 0x80542400
RETURN = 0x801F0004
PID_GENERATOR = 0x80142E04
PLAYER_LOOKUP = 0x801D0A8C
OWNER_SETTER = 0x80149DB0


class WrapperMachine:
    """Small PPC instruction decoder with explicitly observed native calls."""
    def __init__(self, payload):
        self.memory = {ADDRESS + i: value for i, value in enumerate(payload)}
        self.reg = [0x12340000 + i for i in range(32)]
        self.reg[1] = 0x81700000
        self.pc, self.lr = ADDRESS, RETURN
        self.cr = [False] * 4
        self.callbacks, self.calls, self.reads = {}, [], []

    def store(self, address, value, width):
        encoded = (value & ((1 << (8 * width)) - 1)).to_bytes(width, 'big')
        self.memory.update({address + i: byte for i, byte in enumerate(encoded)})

    def load(self, address, width):
        self.reads.append((address, width))
        return int.from_bytes(bytes(self.memory.get(address + i, 0) for i in range(width)), 'big')

    def clobber_volatile(self):
        for index in (0, *range(3, 13)):
            self.reg[index] = 0xBAD00000 + index

    def run(self):
        for _ in range(150):
            if self.pc == RETURN:
                return
            if self.pc in self.callbacks:
                self.calls.append((self.pc, tuple(self.reg[3:8])))
                self.callbacks[self.pc](self)
                self.pc = self.lr
                continue
            pc = self.pc
            word = self.load(pc, 4)
            self.pc += 4
            op, rd, ra, rb = word >> 26, word >> 21 & 31, word >> 16 & 31, word >> 11 & 31
            immediate = word & 0xFFFF
            signed = immediate - 65536 if immediate & 32768 else immediate
            xo = word >> 1 & 1023
            if op in (14, 15):
                self.reg[rd] = ((self.reg[ra] if ra else 0) + (signed << (16 if op == 15 else 0))) & MASK
            elif op == 24:
                self.reg[ra] = self.reg[rd] | immediate
            elif op in (10, 11):
                left = self.reg[ra]
                if op == 11 and left & 0x80000000:
                    left -= 0x100000000
                right = immediate if op == 10 else signed
                self.cr = [left < right, left > right, left == right, False]
            elif op in (32, 34, 40):
                width = {32: 4, 34: 1, 40: 2}[op]
                self.reg[rd] = self.load(((self.reg[ra] if ra else 0) + signed) & MASK, width)
            elif op in (36, 37):
                address = ((self.reg[ra] if ra else 0) + signed) & MASK
                self.store(address, self.reg[rd], 4)
                if op == 37:
                    self.reg[ra] = address
            elif op == 21:
                shift, first, last = word >> 11 & 31, word >> 6 & 31, word >> 1 & 31
                value = ((self.reg[rd] << shift) | (self.reg[rd] >> ((32 - shift) % 32))) & MASK
                bits = range(first, last + 1) if first <= last else (*range(first, 32), *range(last + 1))
                mask = sum(1 << (31 - bit) for bit in bits)
                self.reg[ra] = value & mask
            elif op == 31 and xo == 444:
                self.reg[ra] = self.reg[rd] | self.reg[rb]
            elif op == 31 and xo == 87:
                self.reg[rd] = self.load(((self.reg[ra] if ra else 0) + self.reg[rb]) & MASK, 1)
            elif op == 31 and xo in (339, 467):
                spr = (word >> 16 & 31) | ((word >> 11 & 31) << 5)
                if spr != 8:
                    raise AssertionError(f'Unexpected SPR {spr}')
                if xo == 339:
                    self.reg[rd] = self.lr
                else:
                    self.lr = self.reg[rd]
            elif op == 16:
                bo, bi = word >> 21 & 31, word >> 16 & 31
                if bo not in (4, 12) or bi >= 4:
                    raise AssertionError(f'Unsupported condition {word:08x}')
                if self.cr[bi] == (bo == 12):
                    offset = word & 0xFFFC
                    self.pc = pc + (offset - 65536 if offset & 32768 else offset)
            elif op == 18:
                if word & 2:
                    raise AssertionError('Absolute branch not expected')
                offset = word & 0x03FFFFFC
                if word & 1:
                    self.lr = pc + 4
                self.pc = (pc + (offset - (1 << 26) if offset & (1 << 25) else offset)) & MASK
            elif word == 0x4E800020:
                self.pc = self.lr & ~3
            else:
                raise AssertionError(f'Unsupported instruction {word:08x} at {pc:08x}')
        raise AssertionError('Wrapper did not return')


class XDShadowShinyTests(unittest.TestCase):
    def assert_abi(self, machine, before):
        self.assertEqual(machine.lr, RETURN)
        self.assertEqual(machine.reg[1:3], before[1:3])
        self.assertEqual(machine.reg[13:], before[13:])

    def test_statuses_cover_each_shadow_and_preserve_customization_switches(self):
        self.assertEqual(SHADOW_COUNT, 83)
        options = SimpleNamespace(custom_shinies=True, custom_shadow_shinies=True, shiny_chance_percent=0)
        statuses = shadow_statuses('shadow-rates', options)
        self.assertEqual(set(statuses), {str(index) for index in range(1, 84)})
        self.assertEqual(set(statuses.values()), {False})
        options.shiny_chance_percent = 100
        self.assertEqual(set(shadow_statuses('shadow-rates', options).values()), {True})
        options.custom_shadow_shinies = False
        self.assertEqual(shadow_statuses('shadow-rates', options), {})
        options.custom_shadow_shinies, options.custom_shinies = True, False
        self.assertEqual(shadow_statuses('shadow-rates', options), {})

    def test_intermediate_statuses_are_repeatable_seeded_and_monotonic(self):
        options = SimpleNamespace(custom_shinies=True, custom_shadow_shinies=True, shiny_chance_percent=25)
        low = shadow_statuses('shadow-rates', options)
        self.assertTrue(any(low.values()))
        self.assertTrue(any(not value for value in low.values()))
        self.assertEqual(low, shadow_statuses('shadow-rates', options))
        options.shiny_chance_percent = 60
        high = shadow_statuses('shadow-rates', options)
        self.assertTrue(all(not status or high[key] for key, status in low.items()))
        self.assertNotEqual(high, shadow_statuses('another-shadow-seed', options))

    def test_pid_wrapper_executes_the_selected_policy_and_restores_abi(self):
        for chance in (0, 25, 100):
            options = SimpleNamespace(custom_shinies=True, custom_shadow_shinies=True, shiny_chance_percent=chance)
            statuses = shadow_statuses('shadow-wrapper', options)
            flags = bytes([0] + [int(statuses[str(index)]) for index in range(1, 84)])
            for hero in (False, True):
                for shadow_id in (0, 1, 42, 73, 81, 83, 84, 65535):
                    with self.subTest(chance=chance, hero=hero, shadow=shadow_id):
                        payload = _pid_stub(ADDRESS, PID_GENERATOR, flags, hero=hero)
                        machine = WrapperMachine(payload)
                        machine.reg[3:8] = [0x80901000, 0xA1B2C3D4, 0x11223344, 0, 0xBEEFCAFE]
                        machine.reg[29] = 0x80902000
                        # Different sources catch a wrapper reading the other caller's ID.
                        # Upper bits also verify the trainer's unsigned 16-bit extraction.
                        machine.reg[30] = 0xABCDFFFF if hero else 0xABCD0000 | shadow_id
                        parameter_id = shadow_id if hero else (shadow_id + 1) % 84
                        machine.store(machine.reg[29] + 4, parameter_id, 2)
                        before = machine.reg.copy()
                        expected = flags[shadow_id] if shadow_id <= 83 else 0

                        def pid_probe(state):
                            self.assertEqual(state.reg[3:6], before[3:6])
                            self.assertEqual(state.reg[7], before[7])
                            self.assertEqual(state.reg[6], expected)
                            state.clobber_volatile()
                            state.reg[3] = 0x87654321

                        machine.callbacks[PID_GENERATOR] = pid_probe
                        machine.run()
                        self.assertEqual(len(machine.calls), 1)
                        self.assertEqual(machine.reg[3], 0x87654321)
                        self.assert_abi(machine, before)
                        self.assertEqual(payload[0x100:0x100 + 84], flags)
                        self.assertEqual(len(payload) % 32, 0)
                        if shadow_id > 83:
                            self.assertFalse(any(ADDRESS + 0x100 <= address < ADDRESS + 0x100 + 84
                                                 for address, _ in machine.reads))

    def test_pid_wrapper_rejects_invalid_policy_tables(self):
        for flags in (bytes(83), bytes(85), bytes([0] * 83 + [2])):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                _pid_stub(ADDRESS, PID_GENERATOR, flags)

    def test_owner_wrapper_aligns_only_valid_shadows_to_the_player(self):
        for shadow_id in (0, 1, 73, 81, 83, 84, 65535):
            for player in (0, 0x80903000):
                for pokemon in (0, 0x80901000):
                    with self.subTest(shadow=shadow_id, player=player, pokemon=pokemon):
                        machine = WrapperMachine(_owner_stub(ADDRESS, PLAYER_LOOKUP, OWNER_SETTER))
                        machine.reg[3], machine.reg[4] = pokemon, 0x11112222
                        if pokemon:
                            machine.store(pokemon + 0xBA, shadow_id, 2)
                            machine.store(pokemon + 0x24, 0x11112222, 4)
                        machine.store(player + 0x2C, 0xABCD9876, 4)
                        before = machine.reg.copy()
                        lookup_needed = bool(pokemon and 1 <= shadow_id <= 83)
                        expected = 0xABCD9876 if lookup_needed and player else before[4]

                        def lookup_probe(state):
                            self.assertEqual(state.reg[3:5], [0, 2])
                            state.clobber_volatile()
                            state.reg[3] = player

                        def setter_probe(state):
                            self.assertEqual(state.reg[3:5], [pokemon, expected])
                            if pokemon:
                                state.store(pokemon + 0x24, state.reg[4], 4)
                            state.clobber_volatile()

                        machine.callbacks = {PLAYER_LOOKUP: lookup_probe, OWNER_SETTER: setter_probe}
                        machine.run()
                        self.assertEqual([call[0] for call in machine.calls],
                                         ([PLAYER_LOOKUP] if lookup_needed else []) + [OWNER_SETTER])
                        if pokemon:
                            self.assertEqual(machine.load(pokemon + 0x24, 4), expected)
                        self.assert_abi(machine, before)
                        if not pokemon:
                            self.assertNotIn((0xBA, 2), machine.reads)
