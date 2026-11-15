"""Execute the Snag List hooks with saved identities and ABI-clobbering natives."""
import unittest
from itertools import product
from pathlib import Path
import struct

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.snag_list import (
    _bonus_cache_stub, _bonus_model_stub, _original_completion_stub, _colo_identity_stub, _xd_identity_stub,
    apply_snag_list_identities, _COLO_HOOKS, _COLO_NAVIGATION,
)
from tests.test_shiny_rules import is_shiny
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


SETTER = 0x80100010
SAVED_PID = 0x80100020
GENERATED = 0x80100030
CAPTURED = 0x80100060
PLAYER_LOOKUP = 0x80100040
GENERATOR = 0x80100050
CACHE_READER = 0x80100070
MODEL_REQUEST = 0x80100080
PLAYER_POINTER = 0x80401000
PLAYER = 0x80601000
POKEMON = 0x80602000
SHADOW = 0x80603000


def result(machine, value):
    machine.clobber_volatile()
    machine.reg[3] = value


class SnagListIdentityTests(unittest.TestCase):
    def test_bonus_capture_and_purification_do_not_inflate_original_completion_totals(self):
        original_ids = (*range(1, 45), 55, 56, 57, 67)
        self.assertEqual(len(original_ids), 48)
        for original_count in (0, 17, 47, 48):
            for bonus_flag in (0, 1):
                for reader in (CAPTURED, GENERATED):  # distinct native captured/purified readers
                    with self.subTest(original_count=original_count, bonus_flag=bonus_flag, reader=reader):
                        saved_flags = {shadow: 1 for shadow in original_ids[:original_count]}
                        saved_flags[96] = bonus_flag
                        before_flags = saved_flags.copy()
                        total = 0
                        for shadow in range(1, 97):
                            machine = WrapperMachine(_original_completion_stub(ADDRESS, reader))
                            machine.reg[3] = shadow

                            def native(m):
                                self.assertEqual(m.reg[3], shadow)
                                result(m, saved_flags.get(shadow, 0))

                            machine.callbacks[reader] = native
                            before = machine.reg.copy()
                            machine.run()
                            total += machine.reg[3]
                            self.assertEqual(machine.reg[1:3], before[1:3])
                            self.assertEqual(machine.reg[13:], before[13:])
                            self.assertEqual(machine.lr, RETURN)
                            if shadow == 96:
                                self.assertEqual(machine.calls, [])
                        self.assertEqual(total, original_count)
                        self.assertEqual(saved_flags, before_flags)

    def test_original_completion_excludes_only_exact_shadow96(self):
        for shadow in (0, 1, 48, 67, 95, 96, 97):
            with self.subTest(shadow=shadow):
                machine = WrapperMachine(_original_completion_stub(ADDRESS, CAPTURED))
                machine.reg[3] = shadow
                machine.callbacks[CAPTURED] = lambda m: result(m, 1)
                machine.run()
                self.assertEqual(machine.reg[3], 0 if shadow == 96 else 1)
                self.assertEqual(len(machine.calls), 0 if shadow == 96 else 1)

    def test_colosseum_reuses_the_saved_pid_and_player_owner_without_writing_the_save(self):
        owner = 0x12345678
        for species, pid in product((1, 201, 308), (0xABCDEF81, 0xABCDEF89, 0)):
            with self.subTest(species=species, pid=pid):
                machine = WrapperMachine(_colo_identity_stub(
                    ADDRESS, SETTER, SAVED_PID, GENERATED, PLAYER_POINTER, CAPTURED))
                machine.reg[3:5] = [POKEMON, 0x98765432]
                machine.reg[20] = 21
                machine.store(PLAYER_POINTER, PLAYER, 4)
                machine.store(PLAYER + 0x9C, owner, 4)
                machine.store(POKEMON + 4, 0x11111111, 4)
                machine.store(POKEMON, species, 2)
                machine.store(POKEMON + 0x14, 0, 4)
                machine.store(SHADOW, pid, 4)

                def generated(m):
                    self.assertEqual(m.reg[3], 21)
                    result(m, 1)

                def saved(m):
                    self.assertEqual(m.reg[3], 21)
                    result(m, m.load(SHADOW, 4))

                def setter(m):
                    pointer, value = m.reg[3:5]
                    self.assertEqual(pointer, POKEMON)
                    m.store(pointer + 4, value, 4)
                    result(m, pointer)

                machine.callbacks = {GENERATED: generated, SAVED_PID: saved, SETTER: setter,
                                     CAPTURED: lambda m: result(m, 1)}
                before = machine.reg.copy()
                machine.run()
                self.assertEqual(machine.load(POKEMON + 4, 4), pid)
                self.assertEqual(machine.load(POKEMON, 2), species)
                self.assertEqual(machine.load(POKEMON + 0x14, 4), owner)
                self.assertEqual(machine.load(SHADOW, 4), pid)
                self.assertEqual(machine.load(PLAYER + 0x9C, 4), owner)
                self.assertEqual(machine.reg[3], POKEMON)
                self.assertEqual(machine.reg[1:3], before[1:3])
                self.assertEqual(machine.reg[13:], before[13:])
                self.assertEqual(machine.lr, RETURN)
                self.assertEqual(is_shiny(machine.load(POKEMON + 4, 4), owner), is_shiny(pid, owner))

    def test_colosseum_missing_player_or_ungenerated_shadow_keeps_native_display_pid(self):
        for player, generated in ((0, 1), (PLAYER, 0), (PLAYER, 2)):
            with self.subTest(player=player, generated=generated):
                machine = WrapperMachine(_colo_identity_stub(
                    ADDRESS, SETTER, SAVED_PID, GENERATED, PLAYER_POINTER, CAPTURED))
                machine.reg[3:5] = [POKEMON, 0x98765432]
                machine.reg[20] = 7
                machine.store(PLAYER_POINTER, player, 4)
                machine.store(PLAYER + 0x9C, 0x12345678, 4)
                machine.store(POKEMON + 0x14, 0x87654321, 4)
                machine.callbacks[CAPTURED] = lambda m: result(m, 1)
                machine.callbacks[GENERATED] = lambda m: result(m, generated)

                def setter(m):
                    pointer, value = m.reg[3:5]
                    m.store(pointer + 4, value, 4)
                    result(m, pointer)

                machine.callbacks[SETTER] = setter
                machine.run()
                self.assertEqual(machine.load(POKEMON + 4, 4), 0x98765432)
                self.assertEqual(machine.load(POKEMON + 0x14, 4), 0x87654321)
                self.assertNotIn(SAVED_PID, [call[0] for call in machine.calls])

    def test_xd_saved_pid_and_owner_survive_native_calls_and_apply_to_only_the_display(self):
        owner = 0x12345678
        for species, pid in product((1, 201, 308), (0xABCDEF81, 0xABCDEF89, 0)):
            with self.subTest(species=species, pid=pid):
                machine = WrapperMachine(_xd_identity_stub(ADDRESS, GENERATOR, PLAYER_LOOKUP, GENERATED))
                machine.reg[3:8] = [POKEMON, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0]
                machine.reg[30:32] = [30, SHADOW]
                machine.store(SHADOW + 0x1C, pid, 4)
                machine.store(SHADOW, 3 << 5, 1)
                machine.store(PLAYER + 0x2C, owner, 4)
                machine.store(POKEMON + 0x24, 0, 4)
                machine.store(POKEMON, species, 2)

                def generated(m):
                    self.assertEqual(m.reg[3], 30)
                    result(m, 1)

                def player(m):
                    self.assertEqual(m.reg[3:5], [0, 2])
                    result(m, PLAYER)

                machine.callbacks = {GENERATED: generated, PLAYER_LOOKUP: player}
                before = machine.reg.copy()
                machine.run()
                self.assertEqual(machine.reg[3], pid)
                self.assertEqual(machine.load(POKEMON, 2), species)
                self.assertEqual(machine.load(POKEMON + 0x24, 4), owner)
                self.assertEqual(machine.load(SHADOW + 0x1C, 4), pid)
                self.assertEqual(machine.load(PLAYER + 0x2C, 4), owner)
                self.assertEqual(machine.reg[1:3], before[1:3])
                self.assertEqual(machine.reg[13:], before[13:])
                self.assertEqual(machine.lr, RETURN)
                self.assertNotIn(GENERATOR, [call[0] for call in machine.calls])

    def test_xd_unknown_shadow_or_missing_player_falls_back_with_original_arguments(self):
        for shadow, generated, player in ((0, 1, PLAYER), (SHADOW, 0, PLAYER), (SHADOW, 1, 0)):
            with self.subTest(shadow=shadow, generated=generated, player=player):
                machine = WrapperMachine(_xd_identity_stub(ADDRESS, GENERATOR, PLAYER_LOOKUP, GENERATED))
                arguments = [POKEMON, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0]
                machine.reg[3:8] = arguments
                machine.reg[30:32] = [30, shadow]
                machine.store(POKEMON + 0x24, 0x87654321, 4)
                machine.store(SHADOW, 3 << 5, 1)
                machine.callbacks[GENERATED] = lambda m: result(m, generated)
                machine.callbacks[PLAYER_LOOKUP] = lambda m: result(m, player)

                def generator(m):
                    self.assertEqual(m.reg[3:8], arguments)
                    result(m, 0x87654321)

                machine.callbacks[GENERATOR] = generator
                machine.run()
                self.assertEqual(machine.reg[3], 0x87654321)
                self.assertEqual(machine.load(POKEMON + 0x24, 4), 0x87654321)

    def test_unknown_games_and_modified_native_executables_are_rejected(self):
        for game in ("invalid", "GC6P01", "GXXP01"):
            with self.subTest(game=game), self.assertRaises(FormatError):
                apply_snag_list_identities(bytes(0x100), bytes(0x100), game)

    def test_uncaught_colosseum_shadows_only_use_the_player_owner_with_custom_rules(self):
        for custom in (False, True):
            with self.subTest(custom=custom):
                machine = WrapperMachine(_colo_identity_stub(
                    ADDRESS, SETTER, SAVED_PID, GENERATED, PLAYER_POINTER, CAPTURED,
                    custom_shadow_shinies=custom))
                machine.reg[3:5] = [POKEMON, 0x11111111]
                machine.store(PLAYER_POINTER, PLAYER, 4)
                machine.store(PLAYER + 0x9C, 0x12345678, 4)
                machine.store(POKEMON + 0x14, 0, 4)
                machine.callbacks = {CAPTURED: lambda m: result(m, 0),
                                     GENERATED: lambda m: result(m, 1),
                                     SAVED_PID: lambda m: result(m, 0xABCDEF81)}

                def setter(m):
                    pointer, value = m.reg[3:5]
                    m.store(pointer + 4, value, 4)
                    result(m, pointer)

                machine.callbacks[SETTER] = setter
                machine.run()
                self.assertEqual(machine.load(POKEMON + 4, 4), 0xABCDEF81 if custom else 0x11111111)
                self.assertEqual(machine.load(POKEMON + 0x14, 4), 0x12345678 if custom else 0)

    def test_uncaught_xd_shadows_only_use_the_player_owner_with_custom_rules(self):
        for custom in (False, True):
            with self.subTest(custom=custom):
                machine = WrapperMachine(_xd_identity_stub(
                    ADDRESS, GENERATOR, PLAYER_LOOKUP, GENERATED, custom_shadow_shinies=custom))
                machine.reg[3:8] = [POKEMON, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0]
                machine.reg[30:32] = [30, SHADOW]
                machine.store(SHADOW, 1 << 5, 1)
                machine.store(SHADOW + 0x1C, 0xABCDEF81, 4)
                machine.store(PLAYER + 0x2C, 0x12345678, 4)
                machine.store(POKEMON + 0x24, 0, 4)
                machine.callbacks = {GENERATED: lambda m: result(m, 1),
                                     PLAYER_LOOKUP: lambda m: result(m, PLAYER),
                                     GENERATOR: lambda m: result(m, 0x11111111)}
                machine.run()
                self.assertEqual(machine.reg[3], 0xABCDEF81 if custom else 0x11111111)
                self.assertEqual(machine.load(POKEMON + 0x24, 4), 0x12345678 if custom else 0)

    def test_failed_native_display_allocation_keeps_the_null_safe_native_path(self):
        for payload, target in (
            (_colo_identity_stub(ADDRESS, SETTER, SAVED_PID, GENERATED, PLAYER_POINTER, CAPTURED), SETTER),
            (_xd_identity_stub(ADDRESS, GENERATOR, PLAYER_LOOKUP, GENERATED), GENERATOR),
        ):
            with self.subTest(target=target):
                machine = WrapperMachine(payload)
                machine.reg[3] = 0
                arguments = tuple(machine.reg[3:8])

                def native(m):
                    self.assertEqual(tuple(m.reg[3:8]), arguments)
                    result(m, 0)

                machine.callbacks[target] = native
                machine.run()
                self.assertEqual([call[0] for call in machine.calls], [target])
                self.assertEqual(machine.reg[3], 0)

    def test_bonus_cache_fallback_preserves_every_original_shadow_row_and_existing_cache(self):
        for shadow, cached in product(range(1, 98), (0, 59, 249)):
            with self.subTest(shadow=shadow, cached=cached):
                machine = WrapperMachine(_bonus_cache_stub(ADDRESS, CACHE_READER))
                machine.reg[3] = shadow

                def reader(m):
                    self.assertEqual(m.reg[3], shadow)
                    result(m, cached)

                machine.callbacks[CACHE_READER] = reader
                before = machine.reg.copy()
                machine.run()
                self.assertEqual(machine.reg[3], 249 if shadow == 96 and cached == 0 else cached)
                self.assertEqual(machine.reg[1:3], before[1:3])
                self.assertEqual(machine.reg[13:], before[13:])
                self.assertEqual(machine.lr, RETURN)
                self.assertEqual([call[0] for call in machine.calls], [CACHE_READER])

    def test_bonus_cache_fallback_uses_the_actual_replacement_species(self):
        for species in (1, 201, 249, 411):
            for shadow, cached in ((96, 0), (96, 59), (1, 0), (95, 0)):
                with self.subTest(species=species, shadow=shadow, cached=cached):
                    machine = WrapperMachine(_bonus_cache_stub(ADDRESS, CACHE_READER, species))
                    machine.reg[3] = shadow
                    machine.callbacks[CACHE_READER] = lambda m, value=cached: result(m, value)
                    machine.run()
                    self.assertEqual(machine.reg[3], species if shadow == 96 and cached == 0 else cached)

    def test_lugia_list_models_get_the_selected_shadow_id_and_native_purified_state(self):
        for shadow in (1, 21, 44, 96):
          for mode in (0, 1, 2):
            with self.subTest(mode=mode, shadow=shadow):
                machine = WrapperMachine(_bonus_model_stub(ADDRESS, MODEL_REQUEST))
                machine.reg[3:5] = [0x80604000, POKEMON]
                machine.reg[20:22] = [shadow, mode]
                machine.store(POKEMON, 249, 2)
                machine.store(POKEMON + 4, 0xABCDEF81, 4)
                machine.store(POKEMON + 0x14, 0x12345678, 4)
                machine.store(POKEMON + 0xD8, 0x0001ABCD, 4)
                machine.store(POKEMON + 0xDC, 10, 4)
                arguments = tuple(machine.reg[3:8])

                def request(m):
                    self.assertEqual(tuple(m.reg[3:8]), arguments)
                    result(m, 0)

                machine.callbacks[MODEL_REQUEST] = request
                before = machine.reg.copy()
                machine.run()
                self.assertEqual(machine.load(POKEMON + 0xD8, 2), shadow)
                self.assertEqual(machine.load(POKEMON + 0xDA, 2), 0xABCD)
                self.assertEqual(machine.load(POKEMON + 0xDC, 4), 0xFFFFFF9C if mode == 1 else 10)
                self.assertEqual(machine.load(POKEMON + 4, 4), 0xABCDEF81)
                self.assertEqual(machine.load(POKEMON + 0x14, 4), 0x12345678)
                self.assertEqual(machine.reg[1:3], before[1:3])
                self.assertEqual(machine.reg[13:], before[13:])
                self.assertEqual(machine.lr, RETURN)

    def test_lugia_list_model_hook_rejects_invalid_rows_other_species_and_missing_records(self):
        for shadow, species, pointer in ((0, 249, POKEMON), (97, 249, POKEMON),
                (65535, 249, POKEMON), (96, 59, POKEMON), (96, 249, 0)):
            with self.subTest(shadow=shadow, species=species, pointer=pointer):
                machine = WrapperMachine(_bonus_model_stub(ADDRESS, MODEL_REQUEST))
                machine.reg[3:5] = [0x80604000, pointer]
                machine.reg[20:22] = [shadow, 1]
                machine.store(POKEMON, species, 2)
                machine.store(POKEMON + 0xD8, 0x0001ABCD, 4)
                machine.store(POKEMON + 0xDC, 10, 4)
                machine.callbacks[MODEL_REQUEST] = lambda m: result(m, 0)
                machine.run()
                self.assertEqual(machine.load(POKEMON + 0xD8, 4), 0x0001ABCD)
                self.assertEqual(machine.load(POKEMON + 0xDC, 4), 10)

    def test_browsing_rows_uses_navigation_registers_for_pid_owner_and_provenance(self):
        owner = 0xACC48BC9
        # This order reproduces the native failing sequence: first entry is
        # correct, then D-pad navigation visits both Shadow/purified palettes.
        cases = ((21, True, True), (1, False, False), (19, True, False),
                 (20, False, True), (19, True, False))
        for index, (shadow, shiny, purified) in enumerate(cases):
            shadow_register, mode_register = (20, 21) if index == 0 else (28, 27)
            high = 0xAB00 + index
            pid = high << 16 | high ^ (owner >> 16) ^ (owner & 65535) ^ (2 if shiny else 24)
            with self.subTest(index=index, shadow=shadow, shiny=shiny, purified=purified):
                machine = WrapperMachine(_colo_identity_stub(ADDRESS, SETTER, SAVED_PID,
                    GENERATED, PLAYER_POINTER, CAPTURED, custom_shadow_shinies=True,
                    shadow_register=shadow_register))
                machine.reg[3:5] = [POKEMON, 0xDEADBEEF]
                machine.reg[20], machine.reg[28] = 96, 96
                machine.reg[shadow_register] = shadow
                machine.store(PLAYER_POINTER, PLAYER, 4)
                machine.store(PLAYER + 0x9C, owner, 4)
                machine.store(POKEMON, 249, 2)

                def getter(value):
                    def call(m):
                        self.assertEqual(m.reg[3], shadow)
                        result(m, value)
                    return call

                def setter(m):
                    self.assertEqual(m.reg[3:5], [POKEMON, pid])
                    m.store(POKEMON + 4, m.reg[4], 4)
                    result(m, POKEMON)

                machine.callbacks = {GENERATED: getter(1), SAVED_PID: getter(pid), SETTER: setter}
                machine.run()
                self.assertEqual(machine.load(POKEMON + 0x14, 4), owner)
                self.assertEqual(is_shiny(machine.load(POKEMON + 4, 4), owner), shiny)
                request = WrapperMachine(_bonus_model_stub(ADDRESS, MODEL_REQUEST,
                    shadow_register=shadow_register, mode_register=mode_register))
                request.reg[3:5] = [0x80604000, POKEMON]
                request.reg[20:22] = [96, int(not purified)]
                request.reg[27:29] = [int(not purified), 96]
                request.reg[shadow_register] = shadow
                request.reg[mode_register] = int(purified)
                for offset in range(0x138):
                    request.memory[POKEMON + offset] = machine.memory.get(POKEMON + offset, 0)
                request.store(POKEMON + 0xD8, 0 if purified else 1, 2)
                request.store(POKEMON + 0xDC, 0 if purified else 10, 4)
                request.callbacks[MODEL_REQUEST] = lambda m: result(m, 0)
                before = request.reg.copy()
                request.run()
                self.assertEqual(request.load(POKEMON + 0xD8, 2), shadow)
                self.assertEqual(request.load(POKEMON + 0xDC, 4), 0xFFFFFF9C if purified else 10)
                self.assertEqual(request.load(POKEMON + 4, 4), pid)
                self.assertEqual(request.load(POKEMON + 0x14, 4), owner)
                self.assertEqual(request.reg[13:], before[13:])

    def test_both_native_snag_constructors_are_hooked_and_guarded_in_all_three_regions(self):
        root = Path(__file__).resolve().parents[1]
        sources = {'GC6P01': root / 'game/sys/main.dol',
                   'GC6E01': root / 'build/region-compat-2026-11-02/dol-research/usa-main.dol',
                   'GC6J01': root / 'build/region-compat-2026-11-02/dol-research/japan-main.dol'}
        if not all(path.exists() for path in sources.values()):
            self.skipTest('requires the original local three-region DOLs')
        for game, path in sources.items():
            original = path.read_bytes()
            with self.subTest(game=game):
                output, report = apply_snag_list_identities(original, original, game,
                    custom_shadow_shinies=True)
                navigation = _COLO_NAVIGATION[game][0]
                expected = {_COLO_HOOKS[game], _COLO_HOOKS[game] + 0x60,
                            navigation, navigation + 0x68}
                self.assertEqual({hook['hook_address'] for hook in report['hooks']}, expected)
                for call in expected:
                    self.assertNotEqual(output[call-0x80003000:call-0x80003000+4],
                                        original[call-0x80003000:call-0x80003000+4])
                for call in (navigation, navigation + 0x68):
                    modified = bytearray(original)
                    struct.pack_into('>I', modified, call - 0x80003000, 0x60000000)
                    with self.assertRaises(FormatError):
                        apply_snag_list_identities(original, modified, game, custom_shadow_shinies=True)
                self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
