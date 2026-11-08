"""Execute the emitted Shadow wrappers through native-call boundaries.

The decoder is independent of the builders. Native probes only check wrapper
arguments and emulate ABI clobbers; they do not simulate the game's PID logic.
"""
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer.engine.shiny_rules import _Code
from orre_randomizer.xd_shadow_shinies import (
    SHADOW_COUNT, _owner_stub, _pid_stub, shadow_statuses,
)
from orre_randomizer.xd_spinda import _pid_hook, _reward_hook
from orre_randomizer.xd_spinda_field import _LAYOUTS as FIELD_LAYOUTS, _field_hook, _load_gateon_pid
from orre_randomizer.xd_spinda_trainers import _trainer_pid_hook, spinda_deck_pids


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
            elif op == 13:
                value = (self.reg[ra] + signed) & MASK
                self.reg[rd] = value
                self.cr = [bool(value & 0x80000000), 0 < value < 0x80000000, value == 0, False]
            elif op == 24:
                self.reg[ra] = self.reg[rd] | immediate
            elif op == 27:
                self.reg[ra] = self.reg[rd] ^ (immediate << 16)
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
            elif op == 46:
                address = (self.reg[ra] + signed) & MASK
                for index in range(rd, 32):
                    self.reg[index] = self.load(address + 4 * (index - rd), 4)
            elif op == 21:
                shift, first, last = word >> 11 & 31, word >> 6 & 31, word >> 1 & 31
                value = ((self.reg[rd] << shift) | (self.reg[rd] >> ((32 - shift) % 32))) & MASK
                bits = range(first, last + 1) if first <= last else (*range(first, 32), *range(last + 1))
                mask = sum(1 << (31 - bit) for bit in bits)
                self.reg[ra] = value & mask
            elif op == 31 and xo == 444:
                self.reg[ra] = self.reg[rd] | self.reg[rb]
            elif op == 31 and xo == 316:
                self.reg[ra] = self.reg[rd] ^ self.reg[rb]
            elif op == 31 and xo == 266:
                self.reg[rd] = (self.reg[ra] + self.reg[rb]) & MASK
            elif op == 31 and xo == 32:
                left, right = self.reg[ra], self.reg[rb]
                self.cr = [left < right, left > right, left == right, False]
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

    def test_spinda_shadow_pid_follows_the_key_and_owner_without_affecting_other_slots(self):
        owner = 0xA0B0C0D0
        candidates = {1: 0, 2: 0xABCD9876, 83: 0xEFEF8F8F}
        for hero in (False, True):
            for shadow_id in (0, 1, 2, 3, 83, 84):
                for mode in (0, 1):
                    with self.subTest(hero=hero, shadow=shadow_id, mode=mode):
                        flags = bytes([0] + [mode] * SHADOW_COUNT)
                        machine = WrapperMachine(_pid_stub(ADDRESS, PID_GENERATOR, flags, hero=hero,
                                                           spinda_pids=candidates))
                        machine.reg[3:8] = [0x80901000, MASK, MASK, 0, owner]
                        machine.reg[29], machine.reg[30] = 0x80902000, shadow_id
                        machine.store(machine.reg[29] + 4, shadow_id, 2)
                        before = machine.reg.copy()

                        def pid_probe(state):
                            self.assertEqual(state.reg[3:6], before[3:6])
                            self.assertEqual(state.reg[6], flags[shadow_id] if shadow_id <= SHADOW_COUNT else 0)
                            self.assertEqual(state.reg[7], owner)
                            state.clobber_volatile()
                            state.reg[3] = 0x99998888

                        machine.callbacks[PID_GENERATOR] = pid_probe
                        machine.run()
                        self.assert_abi(machine, before)
                        self.assertEqual(len(machine.calls), 1)
                        if shadow_id not in candidates:
                            self.assertEqual(machine.reg[3], 0x99998888)
                            continue
                        pid = machine.reg[3]
                        self.assertEqual(pid & 0xFFFF, candidates[shadow_id] & 0xFFFF)
                        self.assertEqual(((pid ^ (pid >> 16) ^ owner ^ (owner >> 16)) & 0xFFFF) < 8, bool(mode))

    def test_spinda_reward_marker_uses_gift_key_and_restores_nested_state(self):
        state_address, hero, parameters = 0x80543000, 0x801543A4, 0x80902000
        for species, key, expected in ((308, 8, 0), (308, 14, 0xCAFEBEEF), (308, 9, None),
                                       (308, 7, None), (201, 8, None)):
            with self.subTest(species=species, key=key):
                payload = _reward_hook(ADDRESS, hero, state_address,
                                       gifts=[0, None, None, None, None, None, 0xCAFEBEEF])
                machine = WrapperMachine(payload)
                machine.store(state_address, 0, 4)
                machine.store(state_address + 4, 0xDEADBEEF, 4)
                machine.reg[4], machine.reg[30] = parameters, key
                machine.store(parameters + 2, species, 2)
                before = machine.reg.copy()

                def hero_probe(state):
                    self.assertEqual(state.reg[3:6], before[3:6])
                    self.assertEqual(state.load(state_address, 4), int(expected is not None))
                    self.assertEqual(state.load(state_address + 4, 4), expected if expected is not None else 0xDEADBEEF)
                    state.clobber_volatile()
                    state.reg[3] = 4

                machine.callbacks[hero] = hero_probe
                machine.run()
                self.assert_abi(machine, before)
                self.assertEqual(machine.reg[3], 4)
                self.assertEqual(machine.load(state_address, 4), 0)
                self.assertEqual(machine.load(state_address + 4, 4), 0xDEADBEEF)

    def test_spinda_reward_pid_honors_native_unrestricted_mode(self):
        owner, raw = 0x12345678, 0xBEEFF00D
        state_address = ADDRESS + 0xA0
        machine = WrapperMachine(_pid_hook(ADDRESS, PID_GENERATOR, state_address))
        machine.store(state_address, 1, 4)
        machine.store(state_address + 4, raw, 4)
        machine.reg[3:8] = [0x80901000, MASK, MASK, MASK, owner]
        before = machine.reg.copy()

        def pid_probe(state):
            self.assertEqual(state.reg[3:8], before[3:8])
            state.clobber_volatile()
            state.reg[3] = 0x11223344

        machine.callbacks[PID_GENERATOR] = pid_probe
        machine.run()
        self.assert_abi(machine, before)
        self.assertEqual(machine.reg[3], raw)

    def test_spinda_ordinary_deck_draws_distinct_pids_with_retail_nature_and_gender(self):
        deck = bytearray(0x68 + 4 * 0x20)
        struct.pack_into(">4sII", deck, 0x10, b"DTNR", 0x48, 1)
        struct.pack_into(">3H", deck, 0x3C, 1, 2, 3)
        struct.pack_into(">4sII", deck, 0x58, b"DPKM", 0x90, 4)
        for index, gender, nature in ((1, 0, 6), (2, 1, 8), (3, 2, 10)):
            position = 0x68 + index * 0x20
            struct.pack_into(">H", deck, position, 308)
            deck[position + 0x1E] = nature << 3 | gender << 1
        pids = spinda_deck_pids(deck, {}, "a", "Story")
        self.assertEqual(pids, spinda_deck_pids(deck, {}, "a", "Story"))
        self.assertNotEqual(pids, spinda_deck_pids(deck, {}, "a", "Colosseum"))
        self.assertEqual(len(set(pids.values())), 3)
        self.assertGreaterEqual(pids[1] & 0xFF, 127)
        self.assertLess(pids[2] & 0xFF, 127)
        self.assertEqual([pid % 25 for pid in pids.values()], [6, 8, 10])

    def test_spinda_ordinary_hook_uses_deck_resource_and_dpkm_slot(self):
        state_address = ADDRESS + 0x1000
        story, other = 0x18503400, 0x184C3400
        payload = _trainer_pid_hook(ADDRESS, PID_GENERATOR, state_address,
                                   [(story, 54, 0x12345678), (story, 446, 0x87654321), (other, 54, 123)])
        for resource, slot, species, expected in ((story, 54, 308, 0x12345678), (story, 446, 308, 0x87654321),
                                                  (other, 54, 308, 123), (other, 446, 308, 99),
                                                  (story, 54, 201, 99)):
            with self.subTest(resource=resource, slot=slot, species=species):
                machine = WrapperMachine(payload)
                machine.store(state_address, resource, 4)
                machine.store(machine.reg[1] + 0x38, slot, 4)
                machine.reg[18] = species
                before = machine.reg.copy()

                def pid_probe(state):
                    self.assertEqual(state.reg[3:8], before[3:8])
                    state.clobber_volatile()
                    state.reg[3] = 99

                machine.callbacks[PID_GENERATOR] = pid_probe
                machine.run()
                self.assert_abi(machine, before)
                self.assertEqual(len(machine.calls), 1)
                self.assertEqual(machine.reg[3], expected)

    @patch("orre_randomizer.xd_spinda_field.spinda_face_writer", return_value=bytes(32))
    def test_spinda_field_uses_only_the_saved_pid_for_the_matching_model(self, _writer):
        layout = FIELD_LAYOUTS["GXXP01"]
        normal, shiny = 0x161D0400, 0x23070400
        resources = ((normal, 2, False), (shiny, 2, True))
        texture = 0x80905000
        cases = ((False, 1, normal, 308, 128, True), (False, 1, shiny, 308, 128, True),
                 (False, 0, normal, 308, 128, False), (False, 1, 1, 308, 128, False),
                 (False, 1, normal, 201, 128, False), (False, 1, normal, 308, 64, False),
                 (True, 1, normal, 308, 128, True), (True, 0, normal, 308, 128, False))
        for startup, success, resource, species, width, expected in cases:
            with self.subTest(startup=startup, success=success, resource=resource, species=species, width=width):
                payload = _field_hook(ADDRESS, RETURN, layout, resources, b"", b"", None, startup=startup)
                machine = WrapperMachine(payload)
                machine.reg[3] = success
                machine.reg[30 if startup else 27] = resource
                machine.reg[27 if startup else 29] = 0x80901000
                before = machine.reg.copy()
                first, offset = (27, 0xC) if startup else (25, 0x24)
                for register in range(first, 32):
                    machine.store(before[1] + offset + (register - first) * 4, before[register], 4)
                part, material, mobj, tobj, descriptor = (0x80903000 + i * 0x100 for i in range(5))
                for offset, value in ((0x80901008, 0x80902000), (material + 8, mobj), (mobj + 8, tobj),
                                      (tobj + 0x58, descriptor), (descriptor, texture),
                                      (descriptor + 4, width << 16 | 128), (descriptor + 8, 4)):
                    machine.store(offset, value, 4)

                def native_probe(arguments, result):
                    def probe(state):
                        self.assertEqual(state.reg[3:3 + len(arguments)], list(arguments))
                        state.clobber_volatile()
                        state.reg[3] = result
                    return probe

                writer = ADDRESS + 0x300
                pid = 0x00CAFEBE
                machine.callbacks = {
                    layout.spot_species: native_probe((2,), species),
                    layout.get_part: native_probe((0x80902000, 2), part),
                    layout.get_material: native_probe((part, 0), material),
                    layout.free_part: native_probe((part,), 0),
                    layout.spot_pid: native_probe((2,), pid),
                    writer: native_probe((texture, pid, int(resource == shiny)), texture),
                    layout.store_cache: native_probe((texture, 0x8000), 0),
                    layout.invalidate_texture: native_probe((), 0),
                }
                machine.run()
                self.assert_abi(machine, before)
                self.assertEqual(machine.reg[3], success)
                self.assertEqual(writer in [address for address, _ in machine.calls], expected)

    def test_gateon_uses_saved_pid_even_zero_and_real_owner_for_first_fight(self):
        layout = FIELD_LAYOUTS["GXXP01"]
        code = _Code(ADDRESS)
        code.emit(0x7C0802A6, 0x90010004)
        _load_gateon_pid(code, layout, 0x12345678, True)
        code.label("pid_ready")
        code.emit(0x80010004, 0x7C0803A6, 0x4E800020)
        code.label("restore")
        code.emit(0x38600000, 0x80010004, 0x7C0803A6, 0x4E800020)
        payload = code.finish()
        owner = 0x43546576
        player = 0x80901000
        for seen in (True, False):
            with self.subTest(seen=seen):
                machine = WrapperMachine(payload)
                machine.store(player + 0x2C, owner, 4)

                def shadow_seen(state):
                    self.assertEqual(state.reg[3], 30)
                    state.clobber_volatile()
                    state.reg[3] = int(seen)

                def stored_pid(state):
                    self.assertEqual(state.reg[3], 30)
                    state.clobber_volatile()
                    state.reg[3] = 0

                def real_player(state):
                    self.assertEqual(state.reg[3:5], [0, 2])
                    state.clobber_volatile()
                    state.reg[3] = player

                machine.callbacks = {layout.shadow_seen: shadow_seen, layout.shadow_pid: stored_pid,
                                     layout.player_lookup: real_player}
                machine.run()
                self.assertEqual([address for address, _ in machine.calls],
                                 [layout.shadow_seen, layout.shadow_pid if seen else layout.player_lookup])
                pid = machine.reg[3]
                if seen:
                    self.assertEqual(pid, 0)
                else:
                    self.assertEqual(pid & 0xFFFF, 0x5678)
                    self.assertLess((pid ^ pid >> 16 ^ owner ^ owner >> 16) & 0xFFFF, 8)

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
