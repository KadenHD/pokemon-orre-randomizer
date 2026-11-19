"""Execute the HUD wrappers across form changes, asynchronous IO and ABI edges."""
import unittest

from orre_randomizer.castform_portraits import (
    FIRST_FACE, MODELS, NORMAL_FACE, SHINY_FACE,
    _descriptor_stub, _draw_stub, _status_stub, _shiny_resources,
)
from orre_randomizer.engine.analyze_game import FormatError
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine

STATUS, POKEMON, SEQUENCE = 0x81600100, 0x81012340, 0x81500200
FUNCTIONS = dict(sequence_get=0x80110100, sequence_id=0x80110200,
                 ready=0x80110300, load=0x80110400)
DRAW = 0x80110500


class CastformPortraitTests(unittest.TestCase):
    def test_compact_battle_identity_preserves_native_flag_and_neighbors(self):
        for xd in (False, True):
            for pointer in (0, 0x80010000, POKEMON, 0x817FFFFC):
                with self.subTest(xd=xd, pointer=pointer):
                    # Colosseum's displaced register restore is separately guarded.
                    displaced = 0x981D002D if xd else 0x60000000
                    m = WrapperMachine(_status_stub(ADDRESS, RETURN, displaced, fight=True, xd=xd))
                    status, pokemon = (29, 28) if xd else (31, 30)
                    m.reg[status], m.reg[pokemon], m.reg[0] = STATUS, pointer, 0x5A
                    for i in range(0x30): m.store(STATUS + i, 0x5A, 1)
                    m.run()
                    packed = m.load(STATUS + 0x2C, 1) << 16 | m.load(STATUS + 0x2E, 2)
                    self.assertEqual((0x80000000 | packed << 2) if packed else 0, pointer)
                    self.assertEqual(m.load(STATUS + 0x2D, 1), 0x5A)
                    self.assertEqual(m.load(STATUS + 0x2A, 2), 0x5A5A)
                    m = WrapperMachine(_status_stub(ADDRESS, RETURN, 0x60000000, fight=False, xd=xd))
                    m.reg[30] = STATUS
                    m.store(STATUS + 0x2C, 0xFFFFFFFF, 4)
                    m.run()
                    self.assertEqual(m.load(STATUS + 0x2C, 4), 0x00FF0000)

    def test_live_loaded_model_controls_normal_and_shiny_faces_with_async_fallback(self):
        for xd in (False, True):
            for model in (385, *MODELS, 249):
                for face in (NORMAL_FACE, SHINY_FACE, 249):
                    for state in (-1, 0, 1):
                        with self.subTest(xd=xd, model=model, face=face, state=state):
                            m = WrapperMachine(_draw_stub(ADDRESS, DRAW, FUNCTIONS, xd=xd))
                            m.reg[28 if xd else 30] = STATUS
                            m.reg[3:6] = (0x80600010, 0x80600100, face)
                            packed = (POKEMON >> 2) & 0xFFFFFF
                            m.store(STATUS + 0x2C, packed >> 16, 1)
                            m.store(STATUS + 0x2E, packed, 2)
                            m.store(STATUS + 0x2D, 0xA5, 1)
                            before, link = m.reg.copy(), m.lr
                            wanted = FIRST_FACE + 2 * MODELS.index(model) + int(face == SHINY_FACE) if model in MODELS else face
                            def seq(machine):
                                self.assertEqual(machine.reg[3], POKEMON)
                                machine.clobber_volatile(); machine.reg[3] = SEQUENCE
                            def identity(machine):
                                self.assertEqual(machine.reg[3], SEQUENCE)
                                machine.clobber_volatile(); machine.reg[3] = model
                            def ready(machine):
                                self.assertEqual(machine.reg[3], wanted)
                                machine.clobber_volatile(); machine.reg[3] = state & 0xFFFFFFFF
                            def load(machine):
                                self.assertEqual(machine.reg[3:6], [wanted, 0, 0])
                                machine.clobber_volatile(); machine.reg[3] = 1
                            def draw(machine):
                                eligible = face in (NORMAL_FACE, SHINY_FACE) and model in MODELS
                                self.assertEqual(machine.reg[3:6], before[3:5] + [wanted if eligible and state == 1 else face])
                                machine.clobber_volatile(); machine.reg[3] = 1
                            m.callbacks = {FUNCTIONS['sequence_get']: seq, FUNCTIONS['sequence_id']: identity,
                                FUNCTIONS['ready']: ready, FUNCTIONS['load']: load, DRAW: draw}
                            m.run(max_steps=220)
                            eligible = face in (NORMAL_FACE, SHINY_FACE) and model in MODELS
                            self.assertEqual(sum(target == FUNCTIONS['load'] for target, _ in m.calls), int(eligible and state == -1))
                            self.assertEqual(m.reg[1:3], before[1:3])
                            self.assertEqual(m.reg[13:], before[13:])
                            self.assertEqual(m.lr, link)
                            self.assertEqual(m.load(STATUS + 0x2D, 1), 0xA5)

    def test_empty_or_out_of_mem1_context_never_dereferences_a_battle_pointer(self):
        for packed in (0, 1, 0x5FFFFF, 0xFFFFFF):
            m = WrapperMachine(_draw_stub(ADDRESS, DRAW, FUNCTIONS, xd=True))
            m.reg[28], m.reg[5] = STATUS, NORMAL_FACE
            m.store(STATUS + 0x2C, packed >> 16, 1)
            m.store(STATUS + 0x2E, packed, 2)
            m.callbacks[DRAW] = lambda machine: None
            m.run()
            self.assertEqual([target for target, _ in m.calls], [DRAW])

    def test_native_texture_descriptor_and_shiny_atlas_row_in_both_games(self):
        # Independent native archive identities: f=sun, w=rain, i=hail.
        native_resources = {'colosseum': (0x0F671200, 0x0F691200, 0x0F681200),
                            'xd': (0x0E9D1200, 0x0E9F1200, 0x0E9E1200)}
        for game in ('colosseum', 'xd'):
            for index in range(6):
                for crop in ((False, True) if game == 'colosseum' else (False,)):
                    m = WrapperMachine(_descriptor_stub(ADDRESS, DRAW, game=game, replay=False, crop=crop))
                    m.reg[3] = FIRST_FACE + index
                    m.run()
                    if game == 'xd':
                        self.assertEqual(m.load(m.reg[3], 4), 0xC0000000 if index % 2 else 0x40000000)
                        result = m.load(m.reg[3] + 4, 4)
                    else: result = m.reg[3]
                    self.assertEqual(result, index % 2 if crop else native_resources[game][index // 2])
            for face in (0, NORMAL_FACE, SHINY_FACE, 0x7F00, 0x7FF1):
                m = WrapperMachine(_descriptor_stub(ADDRESS, DRAW, game=game, replay=False))
                m.reg[3] = face
                m.callbacks[DRAW] = lambda machine: self.assertEqual(machine.reg[3], face)
                m.run()

    def test_authored_shiny_descriptors_keep_ordinary_faces_and_native_row_selection(self):
        authored = {414: 0x7DA11200, 415: 0x7DA21200, 416: 0x7DA31200}
        # Independent retail mapping; custom resources only replace rare entries.
        native = {'colosseum': (0x0F671200, 0x0F691200, 0x0F681200),
                  'xd': (0x0E9D1200, 0x0E9F1200, 0x0E9E1200)}
        for game in ('colosseum', 'xd'):
            for index in range(6):
                for crop in ((False, True) if game == 'colosseum' else (False,)):
                    with self.subTest(game=game, index=index, crop=crop):
                        m = WrapperMachine(_descriptor_stub(ADDRESS, DRAW, game=game, replay=False,
                            crop=crop, shiny_resources=authored))
                        m.reg[3] = FIRST_FACE + index
                        m.run()
                        if game == 'xd':
                            self.assertEqual(m.load(m.reg[3], 4), 0xC0000000 if index % 2 else 0x40000000)
                            result = m.load(m.reg[3] + 4, 4)
                        else:
                            result = m.reg[3]
                        expected = authored[(415, 414, 416)[index // 2]] if index % 2 else native[game][index // 2]
                        self.assertEqual(result, index % 2 if crop else expected)

    def test_authored_shiny_descriptors_reject_invalid_or_native_aliases(self):
        for resources in ({}, {414: 0x7DA11E00, 415: 0x7DA21200, 416: 0x7DA31200},
                          {414: 0x7DA11200, 415: 0x7DA11200, 416: 0x7DA31200},
                          {414: 0x0F671200, 415: 0x7DA21200, 416: 0x7DA31200},
                          {414: True, 415: 0x7DA21200, 416: 0x7DA31200}):
            with self.subTest(resources=resources), self.assertRaises(FormatError):
                _shiny_resources(resources)
        self.assertIsNone(_shiny_resources(None))


if __name__ == '__main__':
    unittest.main()
