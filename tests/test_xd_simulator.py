import unittest

from orre_randomizer.xd_battle_rules import ARENA
from orre_randomizer.xd_simulator import (
    _CONTRACTS, _FLOOR_CONTRACTS, _OBJECT_GETTERS, _simulator_species_stub)
from orre_randomizer.xd_species_gameplay import SPECIES_STRIDE
from tests.test_qol_rules import HookMachine


class XDSimulatorTests(unittest.TestCase):
    def test_fixed_rental_traits_for_bingo_cds_lessons_and_randomized_traits_elsewhere(self):
        native = bytearray(110 * SPECIES_STRIDE)
        rattata = 19 * SPECIES_STRIDE
        koffing = 109 * SPECIES_STRIDE
        native[rattata + 0x30:rattata + 0x34] = bytes((0, 0, 50, 62))
        native[koffing + 0x30:koffing + 0x34] = bytes((3, 3, 26, 0))
        randomized = 0x80710000
        for game_id, (getter, _, displacement, _) in _CONTRACTS.items():
            address, continuation = ARENA[game_id][0] + 32, getter + 0x28
            species_pointer = 0xA810 if game_id == "GXXJ01" else 0xA818
            floor_pointer = _FLOOR_CONTRACTS[game_id][0]
            stub = _simulator_species_stub(address, continuation, displacement, native,
                                           floor_pointer, species_pointer)
            self.assertEqual(len(stub) % 32, 0)
            machine = HookMachine(stub, address)
            encounter = machine.reg[13] + displacement - 0x10000
            pointer = machine.reg[13] + species_pointer - 0x10000
            machine.memory.update(dict(enumerate(randomized.to_bytes(4, "big"), pointer)))
            for battle in (0, 11, 12, 13, 14, 0, 15, 0xFFFF, 12, 0):
                machine.memory.update(dict(enumerate(battle.to_bytes(2, "big"), encounter)))
                for offset, expected, altered in ((rattata, 0x0000323E, 0x07072132),
                                                  (koffing, 0x03031A00, 0x0A0A3200)):
                    with self.subTest(game_id=game_id, battle=battle, offset=offset):
                        field = randomized + offset + 0x30
                        machine.memory.update(dict(enumerate(altered.to_bytes(4, "big"), field)))
                        machine.pc = address
                        machine.reg[0], machine.reg[3] = offset, randomized
                        before, link = machine.reg.copy(), machine.lr
                        machine.run(continuation)
                        self.assertEqual(machine.load(machine.reg[3] + 0x30, 4),
                                         expected if battle in (12, 13, 14) else altered)
                        self.assertEqual(machine.reg[:3], before[:3])
                        self.assertEqual(machine.reg[5:], before[5:])
                        self.assertEqual(machine.lr, link)

    def test_bingo_grid_construction_and_return_use_native_traits_without_leaking(self):
        native = bytearray(20 * SPECIES_STRIDE)
        offset = 19 * SPECIES_STRIDE
        native[offset + 0x30:offset + 0x34] = bytes((0, 0, 50, 62))
        randomized, manager, stack, entries = 0x80710000, 0x80720000, 0x80721000, 0x80722000
        # An empty/uninitialized stack is valid outside the Bingo overlay.
        contexts = [
            (0, 0x388, 0, 4, "valid", True),
            (0, 0x38B, 2, 4, "valid", True),
            (0, 0x38B, 3, 4, "valid", True),
            (0, 0x387, 0, 4, "valid", False),
            (0, 0x389, 0, 4, "valid", False),
            (0, 0x38C, 0, 4, "valid", False),
            (0, 0x388, -1, 4, "valid", False),
            (0, 0x388, 4, 4, "valid", False),
            (0, 0x388, 0, 0, "valid", False),
            (0, 0x388, 0, 4, "manager-null", False),
            (0, 0x388, 0, 4, "list-null", False),
            (0, 0x388, 0, 4, "array-null", False),
            (15, 0x388, 0, 4, "valid", False),
            (12, 0x387, 0, 4, "manager-null", True),
            (13, 0x387, -1, 0, "list-null", True),
            (14, 0x387, -1, 0, "array-null", True),
            (0, 0x388, 1, 4, "valid", True),
            (0, 0x100, 0, 4, "valid", False),  # leave Bingo
            (0, 0x388, 0, 4, "valid", True),   # re-enter
        ]
        for game_id, (getter, _, displacement, _) in _CONTRACTS.items():
            address, continuation = ARENA[game_id][0] + 32, getter + 0x28
            species_pointer = 0xA810 if game_id == "GXXJ01" else 0xA818
            floor_pointer = _FLOOR_CONTRACTS[game_id][0]
            stub = _simulator_species_stub(address, continuation, displacement, native,
                                           floor_pointer, species_pointer)
            table_address = address + len(stub) - ((len(native) + 31) // 32 * 32)
            object_address, object_continuation = address + len(stub), _OBJECT_GETTERS[game_id] + 0x38
            object_stub = _simulator_species_stub(
                object_address, object_continuation, displacement, b"", floor_pointer,
                species_pointer, native_table_address=table_address)
            self.assertEqual(len(object_stub), table_address - address)
            machine = HookMachine(stub + object_stub, address)

            def store(location, value):
                machine.memory.update(dict(enumerate((value & 0xFFFFFFFF).to_bytes(4, "big"), location)))

            store(machine.reg[13] + species_pointer - 0x10000, randomized)
            store(randomized + offset + 0x30, 0x07072132)
            for battle, floor, index, capacity, state, expected_native in contexts:
                with self.subTest(region=game_id, battle=battle, floor=floor, index=index, state=state):
                    encounter = machine.reg[13] + displacement - 0x10000
                    machine.memory.update(dict(enumerate(battle.to_bytes(2, "big"), encounter)))
                    store(machine.reg[13] + floor_pointer - 0x10000,
                          0 if state == "manager-null" else manager)
                    store(manager + 4, 0 if state == "list-null" else stack)
                    store(stack, 0 if state == "array-null" else entries)
                    store(stack + 4, index)
                    store(stack + 8, capacity)
                    # A different lower entry detects using a stale/first floor.
                    for slot in range(4):
                        store(entries + slot * 0x224 + 4, floor if slot == index else 0x100)
                    for entry, exit_address in ((address, continuation),
                                                (object_address, object_continuation)):
                        machine.pc = entry
                        machine.reg[0], machine.reg[3] = offset, randomized
                        before, link = machine.reg.copy(), machine.lr
                        machine.run(exit_address)
                        self.assertEqual(machine.load(machine.reg[3] + 0x30, 4),
                                         0x0000323E if expected_native else 0x07072132)
                        self.assertEqual(machine.reg[:3], before[:3])
                        self.assertEqual(machine.reg[5:], before[5:])
                        self.assertEqual(machine.lr, link)
