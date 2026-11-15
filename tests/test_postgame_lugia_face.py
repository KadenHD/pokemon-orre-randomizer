"""Execute native face selection without changing the Pokémon or normal faces."""
import unittest

from orre_randomizer.engine.postgame_lugia_face import (
    NORMAL_KEY, SHINY_KEY, _descriptor, _identity,
)
from orre_randomizer.engine.shadow_lugia_face import COLOSSEUM_RESOURCE
from tests.test_shiny_rules import Machine

ADDRESS, NATIVE, POKEMON = 0x80500020, 0x8012640C, 0x80600000


class BonusLugiaFaceTests(unittest.TestCase):
    def test_saved_shadow_identity_and_actual_rarity_choose_the_face(self):
        for register in (27, 28, 30):
            for species, shadow, gauge in ((249, 96, 5000), (249, 96, 0),
                    (249, 96, -100), (249, 1, 0), (249, 44, -100),
                    (249, 0, 0), (249, 0, -100), (249, 97, 0), (250, 96, 5000)):
              for keep in (False, True):
                for rare in (0, 1):
                    with self.subTest(register=register, species=species, shadow=shadow, gauge=gauge, rare=rare, keep=keep):
                        machine = Machine(_identity(ADDRESS, NATIVE, register, keep_after_purification=keep), ADDRESS)
                        machine.reg[register] = POKEMON
                        machine.reg[3:7] = [0, species, 0x5B, rare]
                        machine.write(POKEMON, species, 2)
                        machine.write(POKEMON + 0xD8, shadow, 2)
                        machine.write(POKEMON + 0xDC, gauge)
                        before, memory = machine.reg.copy(), machine.mem.copy()
                        bonus = species == 249 and 1 <= shadow <= 96 and (keep or gauge != -100)
                        machine.run(stop=machine.lr if bonus else NATIVE)
                        self.assertEqual(machine.reg[3], (SHINY_KEY if rare else NORMAL_KEY) if bonus else 0)
                        self.assertEqual(machine.reg[4:], before[4:])
                        self.assertEqual(machine.mem, memory)
        machine = Machine(_identity(ADDRESS, NATIVE, 28), ADDRESS)
        machine.reg[28] = 0
        machine.run(stop=NATIVE)

    def test_virtual_keys_share_an_atlas_but_select_separate_native_frames(self):
        for crop in (False, True):
            for key in (NORMAL_KEY, SHINY_KEY, 249, 0x33D, 0):
                machine = Machine(_descriptor(ADDRESS, NATIVE, crop=crop), ADDRESS)
                machine.reg[3] = key
                before, lr = machine.reg.copy(), machine.lr
                virtual = key in (NORMAL_KEY, SHINY_KEY)
                machine.run(stop=lr if virtual else NATIVE)
                if virtual:
                    self.assertEqual(machine.reg[3], int(key == SHINY_KEY) if crop else COLOSSEUM_RESOURCE)
                    self.assertEqual(machine.reg[1:3], before[1:3])
                    self.assertEqual(machine.reg[4:], before[4:])
                    self.assertFalse(machine.mem)
                else:
                    self.assertEqual(machine.reg[3], key)
                    self.assertEqual(machine.reg[1], before[1] - 16)
                    self.assertEqual(machine.read(before[1] - 16), before[1])
                self.assertEqual(machine.lr, lr)


if __name__ == "__main__":
    unittest.main()
