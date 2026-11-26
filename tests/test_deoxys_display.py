"""Display adapters preserve native returns and use a specimen's current form."""
from itertools import product
import unittest

from orre_randomizer.deoxys_display import emit_fake_form
from orre_randomizer.deoxys_identity import FORM_TAG
from orre_randomizer.engine.shiny_rules import _Code
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


READER, RECORD = 0x80108000, 0x80502000


class DeoxysDisplayTests(unittest.TestCase):
    def test_display_tags_use_the_current_owned_form_and_preserve_native_pid(self):
        for xd, initial, current in product((False, True), range(4), range(4)):
            with self.subTest(xd=xd, initial=initial, current=current):
                code = _Code(ADDRESS)
                code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044, 0x91610008)
                emit_fake_form(code, 'GXXP01' if xd else 'GC6P01', {21: initial}, READER,
                    shadow_register=20, write_pid=xd)
                code.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
                m = WrapperMachine(code.finish())
                m.reg[3], m.reg[11], m.reg[20] = 0x12345678, RECORD, 21
                m.store(RECORD, 410, 2)
                at, sid_at = (0xC, 0xBA) if xd else (0xD2, 0xD8)
                def lookup(machine):
                    self.assertEqual(machine.reg[3], RECORD)
                    self.assertEqual(machine.load(RECORD + at, 2), FORM_TAG | initial)
                    self.assertEqual(machine.load(RECORD + sid_at, 2), 21)
                    if xd:
                        self.assertEqual(machine.load(RECORD + 0x28, 4), 0x12345678)
                    machine.reg[0] = 0xD00D
                    machine.reg[11] = 0xBAD0
                    machine.reg[3] = current
                m.callbacks[READER] = lookup
                m.run(max_steps=300)
                self.assertEqual(m.load(RECORD + at, 2), FORM_TAG | current)
                self.assertEqual(m.reg[3], 0x12345678)
                self.assertEqual(m.lr, RETURN)

    def test_unrelated_species_and_shadow_ids_do_not_gain_form_tags(self):
        for species, sid in ((25, 21), (410, 20), (249, 21)):
            code = _Code(ADDRESS)
            code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044, 0x91610008)
            emit_fake_form(code, 'GC6P01', {21: 2}, READER, shadow_register=20)
            code.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
            m = WrapperMachine(code.finish())
            m.reg[3], m.reg[11], m.reg[20] = 55, RECORD, sid
            m.store(RECORD, species, 2)
            m.run()
            self.assertEqual(m.calls, [])
            self.assertEqual(m.load(RECORD + 0xD2, 2), 0)
            self.assertEqual(m.reg[3], 55)


if __name__ == '__main__':
    unittest.main()
