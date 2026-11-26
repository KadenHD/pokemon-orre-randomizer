"""The DNA hologram uses the same saved form and personality as its specimen."""
import unittest
from dataclasses import replace
from itertools import product

from orre_randomizer.engine.dna_lab import _DNA_MODEL, _DNA_SHINY, _model_constructor
from orre_randomizer.engine.dol_regions import PAL
from orre_randomizer.engine.postgame_lugia_model import _SAVED_IDENTITIES
from orre_randomizer.deoxys_identity import FORM_TAG
from tests.test_xd_shadow_shinies import ADDRESS
from tests.test_shiny_rules import Machine


CONSTRUCTOR, READER, POKEMON, PLAYER = 0x80108000, 0x80109000, 0x80501000, 0x80502000
OWNER = 0x12345678


class DNAMachine(Machine):
    def __init__(self, payload):
        super().__init__(payload, ADDRESS)
        self.callbacks = {}

    store = Machine.write
    load = Machine.read

    @property
    def native_targets(self):
        return tuple(self.callbacks)

    def clobber_volatile(self):
        for register in (0, *range(3, 13)):
            self.reg[register] = 0xBAD00000 + register

    def native(self, target):
        self.calls.append((target, self.reg[3:8].copy()))
        self.callbacks[target](self)


class DeoxysDNA(unittest.TestCase):
    def test_hologram_keeps_real_pid_shiny_and_latest_owned_form(self):
        for initial, current, shiny, generated in product(range(4), range(4), (False, True), (False, True)):
            region = replace(PAL, native_constructor=CONSTRUCTOR)
            payload = _model_constructor(ADDRESS, region, {}, None,
                deoxys_samples={153: (2, initial)}, deoxys_reader=READER)
            m = DNAMachine(payload)
            return_address = m.lr
            m.reg[3:5] = [POKEMON, 410 | _DNA_MODEL | (1 << 9) | (_DNA_SHINY if shiny else 0)]
            m.store(region.player_pointer, PLAYER, 4)
            m.store(PLAYER + 0x9C, OWNER, 4)
            pid = 0xAABB0000 | (0xAABB ^ 0x1234 ^ 0x5678 ^ (0 if shiny else 8))
            def native(machine):
                self.assertEqual(machine.reg[3:5], [POKEMON, 410])
                machine.store(POKEMON, 410, 2)
                machine.store(POKEMON + 4, pid, 4)
                machine.store(POKEMON + 0x14, OWNER, 4)
                machine.store(POKEMON + 0xD2, 0, 2)
                machine.clobber_volatile()
                machine.reg[3] = 0x123
            def result(value):
                def callback(machine):
                    machine.clobber_volatile()
                    machine.reg[3] = value
                return callback
            saved, seen, _ = _SAVED_IDENTITIES[PAL.game_id]
            def owned(machine):
                self.assertEqual(machine.reg[3], POKEMON)
                self.assertEqual(machine.load(POKEMON + 4, 4), pid)
                self.assertEqual(machine.load(POKEMON + 0x14, 4), OWNER)
                self.assertEqual(machine.load(POKEMON + 0xD8, 2), 2)
                self.assertEqual(machine.load(POKEMON + 0xD2, 2), FORM_TAG | initial)
                machine.reg[3] = current if generated else initial
            m.callbacks = {CONSTRUCTOR: native, seen: result(int(generated)), saved: result(pid), READER: owned}
            m.run()
            self.assertEqual(m.load(POKEMON + 0xD2, 2), FORM_TAG | (current if generated else initial))
            self.assertEqual(m.reg[3], 0x123)
            self.assertEqual(m.lr, return_address)


if __name__ == '__main__':
    unittest.main()
