import unittest

from orre_randomizer.xd_battle_rules import ARENA
from orre_randomizer.xd_simulator import _CONTRACTS, _simulator_species_stub
from orre_randomizer.xd_species_gameplay import SPECIES_STRIDE
from tests.test_qol_rules import HookMachine


class XDSimulatorTests(unittest.TestCase):
    def test_uses_native_rental_traits_only_inside_virtual_encounters(self):
        native = bytearray(110 * SPECIES_STRIDE)
        rattata = 19 * SPECIES_STRIDE
        koffing = 109 * SPECIES_STRIDE
        native[rattata + 0x30:rattata + 0x34] = bytes((0, 0, 50, 62))
        native[koffing + 0x30:koffing + 0x34] = bytes((3, 3, 26, 0))
        randomized = 0x80710000
        for game_id, (getter, _, displacement, _) in _CONTRACTS.items():
            address, continuation = ARENA[game_id][0] + 32, getter + 0x28
            stub = _simulator_species_stub(address, continuation, displacement, native)
            self.assertEqual(len(stub) % 32, 0)
            machine = HookMachine(stub, address)
            encounter = machine.reg[13] + displacement - 0x10000
            for battle in (0, 13, 14, 0, 15, 0xFFFF):
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
                                         expected if battle in (13, 14) else altered)
                        self.assertEqual(machine.reg[:3], before[:3])
                        self.assertEqual(machine.reg[5:], before[5:])
                        self.assertEqual(machine.lr, link)
