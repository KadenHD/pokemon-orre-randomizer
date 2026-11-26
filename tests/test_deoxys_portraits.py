"""Execute instance-face selection independently of any original game dump."""
import unittest

from orre_randomizer.deoxys_portraits import FIRST_KEY, _descriptor_stub, _identity_stub, _previous_target
from orre_randomizer.deoxys_resources import FACE_RESOURCES, FORMS
from orre_randomizer.deoxys_identity import FORM_TAG
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.gift_move_hooks import branch
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine

NATIVE = ADDRESS + 0x1000
RECORD = 0x81002000


class DeoxysPortraitTests(unittest.TestCase):
    def test_faces_use_saved_form_and_native_rarity_without_modifying_specimens(self):
        for register in (27, 28, 30):
            for pid in (0, 1, 2, 3, 0xFFFFFFFF, 0xABCDEF02):
                for rare in (0, 1):
                    with self.subTest(register=register, pid=pid, rare=rare):
                        m = WrapperMachine(_identity_stub(ADDRESS, NATIVE, register))
                        m.reg[register], m.reg[3], m.reg[6] = RECORD, 0, rare
                        m.store(RECORD, 410, 2)
                        m.store(RECORD + 4, pid, 4)
                        m.store(RECORD + 0xD2, FORM_TAG | (pid & 3), 2)
                        before, memory, link = m.reg.copy(), m.memory.copy(), m.lr
                        m.callbacks[NATIVE] = lambda machine: machine.reg.__setitem__(3, 0x123)
                        m.run()
                        form = pid & 3
                        self.assertEqual(m.reg[3], FIRST_KEY + 2 * (form - 1) + rare if form else 0x123)
                        self.assertEqual(len(m.calls), int(form == 0))
                        self.assertEqual(m.reg[1:3], before[1:3])
                        self.assertEqual(m.reg[4:11], before[4:11])
                        self.assertEqual(m.reg[12:], before[12:])
                        self.assertEqual(m.memory, memory)
                        self.assertEqual(m.lr, link)

    def test_other_species_and_bad_pointers_keep_the_previous_chain(self):
        for pointer, species in ((0, 410), (1, 410), (0x7FFFFFFC, 410),
                                 (0x817FFEC9, 410), (0x90000000, 410), (RECORD, 249)):
            m = WrapperMachine(_identity_stub(ADDRESS, NATIVE, 28))
            m.reg[28] = pointer
            m.store(pointer, species, 2)
            m.store(pointer + 4, 3, 4)
            m.callbacks[NATIVE] = lambda machine: machine.reg.__setitem__(3, 111)
            m.run()
            self.assertEqual(m.reg[3], 111)
            self.assertEqual([a for a, _ in m.calls], [NATIVE])
            if pointer != RECORD:
                self.assertNotIn((pointer, 2), m.reads)
                self.assertNotIn((pointer + 4, 4), m.reads)

    def test_unmarked_and_foreign_records_remain_native_despite_their_pid_bits(self):
        for tag in (0, 1, 2, 3, 0xFFFF, 0xDE00):
            m = WrapperMachine(_identity_stub(ADDRESS, NATIVE, 28))
            m.reg[28] = RECORD
            m.store(RECORD, 410, 2)
            m.store(RECORD + 4, 0x12345673, 4)
            m.store(RECORD + 0xD2, tag, 2)
            m.callbacks[NATIVE] = lambda machine: machine.reg.__setitem__(3, 111)
            m.run()
            self.assertEqual(m.reg[3], 111)

    def test_each_virtual_face_resolves_its_own_atlas_and_correct_shiny_row(self):
        for index, form in enumerate(FORMS):
            for shiny in (False, True):
                for crop in (False, True):
                    m = WrapperMachine(_descriptor_stub(ADDRESS, NATIVE, crop=crop))
                    m.reg[3] = FIRST_KEY + index * 2 + shiny
                    before = m.reg.copy()
                    m.run()
                    self.assertEqual(m.reg[3], int(shiny) if crop else FACE_RESOURCES[form])
                    self.assertEqual(m.reg[1:3], before[1:3])
                    self.assertEqual(m.reg[4:], before[4:])
                    self.assertFalse(m.calls)

    def test_descriptor_leaves_ordinary_and_existing_appearance_keys_to_their_owner(self):
        for key in (0, 410, 796, 0x7F10, 0x7FF1, FIRST_KEY - 1, FIRST_KEY + 6, 0xFFFF):
            m = WrapperMachine(_descriptor_stub(ADDRESS, NATIVE))
            m.reg[3] = key
            m.callbacks[NATIVE] = lambda machine: machine.reg.__setitem__(3, 0x99)
            m.run()
            self.assertEqual(m.reg[3], 0x99)
            self.assertEqual([a for a, _ in m.calls], [NATIVE])

    def test_chaining_accepts_native_and_owned_arena_targets_only(self):
        ram, size, native = 0x80500000, 0x500, ADDRESS + 0x2000
        original = branch(ADDRESS, native, link=True)
        self.assertEqual(_previous_target(original, original, ADDRESS, native, ram, size, link=True), native)
        owned = ram + 0x100
        self.assertEqual(_previous_target(branch(ADDRESS, owned, link=True), original, ADDRESS,
                                         native, ram, size, link=True), owned)
        # Entry-point adapters (Lugia/Castform descriptors) use b, not bl.
        self.assertEqual(_previous_target(branch(ADDRESS, owned), 0x9421FFF0, ADDRESS,
                                         ADDRESS + 4, ram, size, link=False), owned)
        for target in (ram, ram + size, 0x80004000):
            with self.assertRaises(FormatError):
                _previous_target(branch(ADDRESS, target, link=True), original, ADDRESS,
                                 native, ram, size, link=True)
        for word in (0x60000000, branch(ADDRESS, owned), branch(ADDRESS, owned, link=True) | 2):
            with self.assertRaises(FormatError):
                _previous_target(word, original, ADDRESS, native, ram, size, link=True)


if __name__ == '__main__':
    unittest.main()
