"""Only proven Shadow field actors receive the dark Lugia model."""
from types import SimpleNamespace
from unittest.mock import patch
import struct
import unittest

from orre_randomizer.xd_field_actors import _field_model, GATEON_LUGIA_SHINY_RESOURCE
from orre_randomizer.xd_shadow_lugia_model import _field_actor_stub
from tests.test_shiny_rules import is_shiny
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


class ShadowLugiaFieldTests(unittest.TestCase):
    def test_generic_field_lugia_stays_normal_unless_caller_proves_shadow_provenance(self):
        rel = bytearray((249+1)*0x124)
        struct.pack_into('>H', rel, 249*0x124+8, 52)
        struct.pack_into('>H', rel, 249*0x124+0x2E, 249)
        for shadow in (False, True):
            for shiny in (False, True):
                with self.subTest(shadow=shadow, shiny=shiny), \
                        patch('orre_randomizer.xd_field_actors.load_actor_model', return_value=b'ordinary') as ordinary, \
                        patch('orre_randomizer.xd_shadow_lugia_model.load_shadow_lugia_field_model', return_value=b'dark') as dark:
                    model, report = _field_model(rel, 0, {249: (249,)}, b'dol', 'GXXP01',
                                                 lambda _: None, 249, .8, shiny=shiny,
                                                 height_limit=7.2, shadow_lugia=shadow)
                    self.assertEqual(model, b'dark' if shadow else b'ordinary')
                    self.assertEqual(dark.call_count, int(shadow))
                    self.assertEqual(ordinary.call_count, int(not shadow))
                    self.assertAlmostEqual(report['scale'], 7.2/52)
                    (dark if shadow else ordinary).assert_called_once()

    def test_gateon_lugia_uses_shadow30_identity_independently_from_xd001(self):
        seen, saved, player, rare, hero = 0x80101000, 0x80101010, 0x80101020, 0x80101030, 0x80601000
        state = SimpleNamespace(shadow_seen=seen, shadow_pid=saved)
        identity = SimpleNamespace(player_lookup=player)
        source = 0x18490400
        for startup in (False, True):
            for generated in (False, True):
                for shiny in (False, True):
                    for default in (False, True):
                        with self.subTest(startup=startup, generated=generated, shiny=shiny, default=default):
                            code = _field_actor_stub(ADDRESS, RETURN, state, identity, rare,
                                startup=startup, routes=((source, GATEON_LUGIA_SHINY_RESOURCE, 30, default),))
                            machine = WrapperMachine(code)
                            register = 30 if startup else 27
                            machine.reg[register] = source
                            pid = 0xABCDEF01
                            owner = (pid >> 16) ^ (pid & 65535) ^ (0 if shiny else 8)
                            machine.store(hero+0x2C, owner, 4)
                            before = machine.reg.copy()

                            def reply(m, value):
                                m.clobber_volatile()
                                m.reg[3] = value

                            def native_seen(m):
                                self.assertEqual(m.reg[3], 30)
                                reply(m, int(generated))

                            def native_pid(m):
                                self.assertEqual(m.reg[3], 30)
                                reply(m, pid)

                            def native_player(m):
                                self.assertEqual(m.reg[3:5], [0, 2])
                                reply(m, hero)

                            def native_rare(m):
                                self.assertEqual(m.reg[3:5], [owner, pid])
                                reply(m, int(is_shiny(pid, owner)))

                            machine.callbacks = {seen: native_seen, saved: native_pid,
                                                 player: native_player, rare: native_rare}
                            machine.run()
                            selected = shiny if generated else default
                            self.assertEqual(machine.reg[register], GATEON_LUGIA_SHINY_RESOURCE if selected else source)
                            self.assertEqual(machine.reg[1:3], before[1:3])
                            self.assertEqual(machine.reg[3:7], before[3:7])
                            for i in range(13, 32):
                                if i not in {register, 27}:
                                    self.assertEqual(machine.reg[i], before[i])


if __name__ == '__main__':
    unittest.main()
