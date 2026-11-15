"""Execute display routing across the saved-identity and native ABI boundaries."""
from types import SimpleNamespace
from pathlib import Path
import hashlib
import unittest

from orre_randomizer.xd_shadow_lugia_model import (
    DARK_MODEL, FIELD_RESOURCES, RESOURCE, _field_actor_stub, _model_stub,
    _retained_display_stub, _retained_snag_copy_stub, _install_retained_displays,
    _DISPLAY_CALLS, _CEREMONY_MODELS, _retained_ceremony_stub, _install_retained_ceremony,
)
from tests.test_shiny_rules import is_shiny
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine
from orre_randomizer.xd_shadow_shinies import _LAYOUTS as NATIVE_IDENTITIES
from orre_randomizer.xd_battle_rules import TEXT1_TO_RAM
from orre_randomizer.engine.analyze_game import FormatError

SEEN, PID, PLAYER, RARE = (0x80101000, 0x80101010, 0x80101020, 0x80101030)
HERO = 0x80601000
LAYOUT = SimpleNamespace(shadow_seen=SEEN, shadow_pid=PID)
IDENTITY = SimpleNamespace(player_lookup=PLAYER)
NATIVE_RESOURCE = 0x19661E00


class ShadowLugiaModelTests(unittest.TestCase):
    def machine(self, *, model=DARK_MODEL, native_shiny=False, generated=True,
                player=True, saved_shiny=False, fallback=False):
        machine = WrapperMachine(_model_stub(ADDRESS, RETURN))
        machine.reg[4] = NATIVE_RESOURCE
        machine.reg[27], machine.reg[29:32] = model, [int(native_shiny), 0, 2263]
        owner = 0x12345678
        pid = 0xABCDEF81 if saved_shiny else 0xABCDEF89
        # Derive an OT with the requested status without simulating a generator.
        owner = (pid >> 16) ^ (pid & 0xFFFF) ^ (0 if saved_shiny else 8)
        machine.store(HERO + 0x2C, owner, 4)

        def reply(m, value):
            m.clobber_volatile()
            m.reg[3] = value

        def seen(m):
            self.assertEqual(m.reg[3], 73)
            reply(m, int(generated))

        def saved(m):
            self.assertEqual(m.reg[3], 73)
            reply(m, pid)

        def player_lookup(m):
            self.assertEqual(m.reg[3:5], [0, 2])
            reply(m, HERO if player else 0)

        def rare(m):
            self.assertEqual(m.reg[3:5], [owner, pid])
            reply(m, int(is_shiny(pid, owner)))

        machine.callbacks = {SEEN: seen, PID: saved, PLAYER: player_lookup, RARE: rare}
        return machine

    def assert_result(self, machine, variant):
        before = machine.reg.copy()
        owner = machine.load(HERO + 0x2C, 4)
        machine.run()
        self.assertEqual(machine.reg[3], 2263)
        self.assertEqual(machine.reg[4], RESOURCE if variant else NATIVE_RESOURCE)
        self.assertEqual(machine.reg[29:32], [1, 1, 2263] if variant else before[29:32])
        self.assertEqual(machine.reg[1:3], before[1:3])
        self.assertEqual(machine.reg[13:29], before[13:29])
        self.assertEqual(machine.lr, RETURN)
        self.assertEqual(machine.load(HERO + 0x2C, 4), owner)

    def test_native_shiny_selects_alternate_resource_without_reading_or_generating_pid(self):
        machine = self.machine(native_shiny=True)
        self.assert_result(machine, True)
        self.assertEqual(machine.calls, [])

    def test_every_dark_model_uses_its_own_native_status_not_xd001_status(self):
        for native_shiny in (False, True):
            for saved_shiny in (False, True):
                for player in (False, True):
                    with self.subTest(actual=native_shiny, xd001=saved_shiny, player=player):
                        machine = self.machine(native_shiny=native_shiny,
                                               saved_shiny=saved_shiny, player=player,
                                               fallback=not native_shiny)
                        self.assert_result(machine, native_shiny)
                        self.assertEqual(machine.calls, [])

    def test_purified_lugia_and_all_other_models_keep_native_resource_and_shiny_flag(self):
        for model in (1, 249, 416, 418):
            for shiny in (False, True):
                machine = self.machine(model=model, native_shiny=shiny, saved_shiny=True, fallback=True)
                self.assert_result(machine, False)
                self.assertEqual(machine.calls, [])

    def test_authored_field_forms_select_exact_saved_or_seeded_identity_before_loading(self):
        conditions = (({"saved_shiny": True}, True), ({"saved_shiny": False}, False),
                      ({"generated": False, "fallback": True}, True),
                      ({"generated": False, "fallback": False}, False),
                      ({"saved_shiny": True, "player": False}, False))
        for startup in (False, True):
            for source, target in FIELD_RESOURCES:
                for options, selected in conditions:
                    with self.subTest(startup=startup, source=source, options=options):
                        machine = self.machine(**options)
                        code = _field_actor_stub(ADDRESS, RETURN, LAYOUT, IDENTITY, RARE,
                                                startup=startup, fallback=options.get("fallback", False))
                        machine.memory.update({ADDRESS+i: value for i, value in enumerate(code)})
                        register = 30 if startup else 27
                        machine.reg[register] = source
                        before = machine.reg.copy()
                        machine.run()
                        self.assertEqual(machine.reg[register], target if selected else source)
                        self.assertEqual(machine.reg[3:7], before[3:7])
                        self.assertEqual(machine.reg[1:3], before[1:3])
                        allowed = {register, 27} if startup else {register}
                        for index in range(13, 32):
                            if index not in allowed:
                                self.assertEqual(machine.reg[index], before[index])
                        if startup:
                            self.assertEqual(machine.reg[27], before[3])
                        self.assertEqual(machine.lr, RETURN)
                        if not options.get("generated", True):
                            self.assertEqual([call[0] for call in machine.calls], [SEEN])

    def test_unrelated_field_species_and_purified_lugia_do_not_consult_shadow_identity(self):
        for startup in (False, True):
            for source in (0x18880400, 0x166B0400, FIELD_RESOURCES[0][1]):
                machine = WrapperMachine(_field_actor_stub(ADDRESS, RETURN, LAYOUT, IDENTITY, RARE,
                                                          startup=startup, fallback=True))
                register = 30 if startup else 27
                machine.reg[register] = source
                before = machine.reg.copy()
                machine.run()
                self.assertEqual(machine.reg[register], source)
                self.assertEqual(machine.reg[3:7], before[3:7])
                self.assertEqual(machine.calls, [])
                self.assertEqual(machine.lr, RETURN)

    def test_retained_display_requires_real_lugia_with_known_shadow_provenance(self):
        specimen = 0x80602000
        for species in (1, 132, 249):
            for shadow in (0, 1, 30, 73, 83, 84, 65535):
                with self.subTest(species=species, shadow=shadow):
                    machine = WrapperMachine(_retained_display_stub(ADDRESS))
                    machine.reg[3] = specimen
                    machine.store(specimen, species, 2)
                    machine.store(specimen+0xBA, shadow, 2)
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run()
                    self.assertEqual(machine.reg[3], int(species == 249 and 1 <= shadow <= 83))
                    self.assertEqual(machine.memory, memory)
                    self.assertEqual(machine.reg[1:3], before[1:3])
                    self.assertEqual(machine.reg[4:], before[4:])
                    self.assertEqual(machine.calls, [])
        machine = WrapperMachine(_retained_display_stub(ADDRESS))
        machine.reg[3] = 0
        machine.run()
        self.assertEqual(machine.reg[3], 0)

    def test_purified_snag_copy_retains_only_lugia_selected_shadow_id(self):
        setter, specimen = 0x80102000, 0x80602000
        for species in (1, 249):
            for shadow in (0, 1, 30, 73, 83, 84):
                machine = WrapperMachine(_retained_snag_copy_stub(ADDRESS, setter))
                machine.reg[3], machine.reg[4], machine.reg[30] = specimen, 0, shadow
                machine.store(specimen, species, 2)
                before, memory = machine.reg.copy(), machine.memory.copy()

                def native(m):
                    self.assertEqual(m.reg[3], specimen)
                    expected = shadow if species == 249 and 1 <= shadow <= 83 else 0
                    self.assertEqual(m.reg[4], expected)

                machine.callbacks[setter] = native
                machine.run()
                self.assertEqual(machine.reg[1:3], before[1:3])
                self.assertEqual(machine.reg[5:], before[5:])
                self.assertEqual(machine.memory, memory)

    def test_retained_display_never_confuses_an_ordinary_lugia_with_an_identical_pid(self):
        specimen = 0x80602000
        machine = WrapperMachine(_retained_display_stub(ADDRESS))
        machine.reg[3] = specimen
        machine.store(specimen, 249, 2)
        machine.store(specimen+0x24, 0x12345678, 4)
        machine.store(specimen+0x28, 0xABCDEF81, 4)
        machine.store(specimen+0xBA, 0, 2)
        machine.run()
        self.assertEqual(machine.reg[3], 0)
        self.assertEqual(machine.calls, [])

    def test_purification_second_model_keeps_only_real_shadow_lugia_and_native_identity(self):
        specimen = 0x80602000
        for species in (249, 250):
            for shadow_id in (0, 1, 30, 73, 83, 84):
                for shiny in (False, True):
                    with self.subTest(species=species, shadow=shadow_id, shiny=shiny):
                        machine = WrapperMachine(_retained_ceremony_stub(ADDRESS, RETURN))
                        machine.reg[31] = specimen
                        machine.reg[4:6] = [0xCD0D6B85, int(shiny)]
                        machine.store(specimen, species, 2)
                        machine.store(specimen+0xBA, shadow_id, 2)
                        before, memory = machine.reg.copy(), machine.memory.copy()
                        machine.run()
                        self.assertEqual(machine.reg[3],
                            DARK_MODEL if species == 249 and 1 <= shadow_id <= 83 else 249)
                        self.assertEqual(machine.reg[1:3], before[1:3])
                        self.assertEqual(machine.reg[4:], before[4:])
                        self.assertEqual(machine.memory, memory)
                        self.assertEqual(machine.calls, [])
                        self.assertEqual(machine.lr, RETURN)
        machine = WrapperMachine(_retained_ceremony_stub(ADDRESS, RETURN))
        machine.reg[31] = 0
        machine.run()
        self.assertEqual(machine.reg[3], 249)

    def test_purification_second_model_hooks_match_all_three_retail_windows(self):
        root = Path(__file__).resolve().parents[1]
        paths = [(root/f'build/xd-validation/{region}/main.dol', gid)
                 for region, gid in (('eu', 'GXXP01'), ('us', 'GXXE01'), ('jp', 'GXXJ01'))]
        if not all(path.is_file() for path, _gid in paths):
            self.skipTest('requires three locally retained original XD executables')
        for path, gid in paths:
            with self.subTest(game=gid):
                original = path.read_bytes()
                patched, hooks = _install_retained_ceremony(original, original, gid)
                self.assertEqual(len(hooks), 1)
                self.assertEqual(hooks[0]['hook_address'], _CEREMONY_MODELS[gid])
                at = _CEREMONY_MODELS[gid]-TEXT1_TO_RAM
                self.assertNotEqual(patched[at:at+4], original[at:at+4])
                self.assertEqual(patched[at+4:at+20], original[at+4:at+20])
                changed = bytearray(original)
                changed[at-4:at] = bytes(4)
                with self.assertRaises(FormatError):
                    _install_retained_ceremony(original, changed, gid)

    def test_retained_hooks_preserve_shared_gameplay_predicate_in_all_originals(self):
        root = Path(__file__).resolve().parents[1]
        paths = [(root/f'build/xd-validation/{region}/main.dol', gid)
                 for region, gid in (('eu', 'GXXP01'), ('us', 'GXXE01'), ('jp', 'GXXJ01'))]
        if not all(path.is_file() for path, _gid in paths):
            self.skipTest('requires three locally retained original XD executables')
        for path, gid in paths:
            with self.subTest(game=gid):
                original = path.read_bytes()
                self.assertEqual(hashlib.sha256(original).hexdigest(), NATIVE_IDENTITIES[gid].original_sha256)
                patched, hooks = _install_retained_displays(original, original, gid)
                self.assertEqual(len(hooks), 5)
                self.assertEqual([h['hook_address'] for h in hooks], list(_DISPLAY_CALLS[gid]))
                for h in hooks:
                    # Every changed native call site is an explicitly admitted
                    # display request. The original callees still execute for
                    # all non-display callers in the rest of the game.
                    at = h['hook_address']-TEXT1_TO_RAM
                    word = int.from_bytes(original[at:at+4], 'big')
                    delta = word & 0x03FFFFFC
                    if delta & 0x02000000:
                        delta -= 0x04000000
                    target = h['hook_address']+delta-TEXT1_TO_RAM
                    self.assertEqual(patched[target:target+96], original[target:target+96])
                changed = bytearray(original)
                first = _DISPLAY_CALLS[gid][0]-TEXT1_TO_RAM
                changed[first-4:first] = bytes(4)
                with self.assertRaises(FormatError):
                    _install_retained_displays(original, changed, gid)


if __name__ == "__main__":
    unittest.main()
