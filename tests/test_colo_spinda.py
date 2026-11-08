"""Execute the Colosseum Spinda wrappers against a native-ABI test double."""

from dataclasses import replace
from pathlib import Path
import unittest

from orre_randomizer.engine.shiny_rules import (
    PID_CALLS, PID_GENERATOR, PLAYER_POINTER, SECTION_RAM, TEXT_TO_RAM,
    _pid_wrapper, _seeded_trainer_wrapper, _spinda_party_owner, _spinda_pid_call, apply_shiny_rules,
)
from orre_randomizer.engine.colo_spinda import ORDINARY_SPINDA_OT, colo_spinda_pid
from orre_randomizer.engine.dol_regions import PAL
from orre_randomizer.engine.spinda import SPINDA
from orre_randomizer.options import Options
from test_shiny_rules import Machine


RNG_POINTER_DISPLACEMENT = -0x7B8C
RNG_STATE = 0x80500060
POKEMON = 0x80510000
RNG_INITIAL = 0xDEADBEEF


class SeedMachine(Machine):
    def __init__(self, data, address):
        super().__init__(data, address)
        self.write(self.reg[13] + RNG_POINTER_DISPLACEMENT, RNG_STATE)
        self.write(RNG_STATE, RNG_INITIAL)
        self.draws = []

    def native(self, target):
        if target == PID_GENERATOR:
            seed = self.read(RNG_STATE)
            self.draws.append(seed)
            self.write(RNG_STATE, (seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF)
        super().native(target)


class ColosseumSpindaTests(unittest.TestCase):
    def test_rng_state_isolated_for_spinda_and_non_spinda_remains_native(self):
        address = SECTION_RAM + 32
        code = _spinda_pid_call(address, 0x8474, PAL)
        for species, seed in ((SPINDA, 0x12345678), (SPINDA, 0xF0000001), (SPINDA, 0), (25, 0x12345678)):
            with self.subTest(species=species, seed=seed):
                machine = SeedMachine(code, address)
                machine.reg[3:9] = [POKEMON, 2, 7, 1, 0x24681357, seed]
                machine.write(POKEMON, species, 2)
                machine.run()
                targeted = species == SPINDA and seed != 0
                gender = seed >> 31 if targeted else 2
                self.assertEqual(machine.calls, [(PID_GENERATOR, [POKEMON, gender, 7, 1, 0x24681357])])
                self.assertEqual(machine.draws, [seed if targeted else RNG_INITIAL])
                expected = RNG_INITIAL if targeted else (RNG_INITIAL * 0x343FD + 0x269EC3) & 0xFFFFFFFF
                self.assertEqual(machine.read(RNG_STATE), expected)

    def test_regular_and_shadow_lookup_keep_distinct_seed_and_owner(self):
        trainer_flags, shadow_flags = 0x81600000, 0x81602000
        trainer_seeds, shadow_seeds = 0x81603000, 0x81609000
        helper = SECTION_RAM + 32
        code = _spinda_pid_call(helper, 0x8474, PAL)
        wrapper = helper + len(code)
        code += _seeded_trainer_wrapper(wrapper, trainer_flags, shadow_flags, spinda_pid=helper,
                                        spinda_tables=(trainer_seeds, shadow_seeds))
        for shadow_id in (0, 21):
            with self.subTest(shadow_id=shadow_id):
                machine = SeedMachine(code, helper)
                machine.pc = wrapper
                machine.reg[3:8] = [POKEMON, 1, 7, 0, 0x12345678]
                machine.reg[30] = shadow_id
                machine.write(POKEMON, SPINDA, 2)
                machine.write(machine.reg[1] + 0x48, 5)
                machine.write(PLAYER_POINTER, POKEMON)
                machine.write(POKEMON + 0x9C, 0x2468ABCD)
                machine.write(trainer_flags + 5, 0, 1)
                machine.write(shadow_flags + 21, 1, 1)
                machine.write(trainer_seeds + 5 * 4, 0x22222222)
                machine.write(shadow_seeds + 21 * 4, 0x33333333)
                machine.run()
                owner = 0x2468ABCD if shadow_id else ORDINARY_SPINDA_OT
                self.assertEqual(machine.calls, [(PID_GENERATOR, [POKEMON, 1, 7, bool(shadow_id), owner])])
                self.assertEqual(machine.draws, [0x33333333 if shadow_id else 0x22222222])
                self.assertEqual(machine.read(RNG_STATE), RNG_INITIAL)

    def test_native_policy_gift_wrapper_passes_through_stock_arguments(self):
        helper = SECTION_RAM + 32
        code = _spinda_pid_call(helper, 0x8474, PAL)
        wrapper = helper + len(code)
        code += _pid_wrapper(wrapper, None, spinda_pid=helper, spinda_seed=0x97530468)
        machine = SeedMachine(code, helper)
        machine.pc = wrapper
        machine.reg[3:8] = [POKEMON, 1, 7, 0, 0x12345678]
        machine.write(POKEMON, SPINDA, 2)
        machine.run()
        self.assertEqual(machine.calls, [(PID_GENERATOR, [POKEMON, 1, 7, 0, 0x12345678])])
        self.assertEqual(machine.draws, [0x97530468])

    def test_owner_copy_only_affects_non_shadow_spinda_in_trainer_parties(self):
        address, party_return, native = SECTION_RAM + 32, 0x801FE734, 0x80128064
        for species, shadow, caller in ((SPINDA, 0, party_return), (SPINDA, 21, party_return),
                                        (25, 0, party_return), (SPINDA, 0, 0x801F0100)):
            with self.subTest(species=species, shadow=shadow, caller=caller):
                machine = Machine(_spinda_party_owner(address, party_return, native), address)
                machine.reg[3:10] = [POKEMON, 1, 7, 0, 4, 0x12345678, 0x80501000]
                machine.write(POKEMON, species, 2)
                machine.write(POKEMON + 0xD8, shadow, 2)
                machine.write(machine.reg[1] + 0x164, caller)
                expected = machine.reg[3:10]
                if species == SPINDA and not shadow and caller == party_return:
                    expected[5] = ORDINARY_SPINDA_OT
                machine.run(stop=native)
                self.assertEqual(machine.reg[3:10], expected)

    def test_preview_pid_honours_native_nature_gender_and_shiny_constraints(self):
        args = dict(owner=ORDINARY_SPINDA_OT, gender=1, nature=7)
        normal = colo_spinda_pid(0x12345678, shiny=False, **args)
        shiny = colo_spinda_pid(0x12345678, shiny=True, **args)
        self.assertNotEqual(normal, shiny)
        for pid, expected in ((normal, False), (shiny, True)):
            self.assertLess(pid & 0xFF, 127)
            self.assertEqual(pid % 25, 7)
            high, low = pid >> 16, pid & 0xFFFF
            xor = high ^ low ^ (ORDINARY_SPINDA_OT >> 16) ^ (ORDINARY_SPINDA_OT & 0xFFFF)
            self.assertEqual(xor < 8, expected)


ORIGINAL = Path(__file__).resolve().parents[1] / 'game/sys/main.dol'


@unittest.skipUnless(ORIGINAL.is_file(), "requires user's original PAL DOL")
class ColosseumSpindaCompositionTests(unittest.TestCase):
    def test_existing_shadow_pid_reuse_and_native_gifts_untouched(self):
        dol = ORIGINAL.read_bytes()
        seeds = {"trainer:5": 0x3141519, "shadow:21": 0x12345678, "special:plusle": 0xFEDCBA98}
        for custom, seeded in ((False, False), (True, False), (True, True)):
            with self.subTest(custom=custom, seeded=seeded):
                options = replace(Options(), custom_shinies=custom, seeded_shinies=seeded)
                output, report = apply_shiny_rules(dol, dol, options, seed="spinda", spinda_seeds=seeds)
                self.assertEqual(report['spinda_pid']['seeds'], seeds)
                self.assertEqual(report['spinda_pid']['stored_shadow_pid'], 0x801F2FC4)
                self.assertEqual(report['spinda_pid']['ordinary_trainer_ot'], ORDINARY_SPINDA_OT)
                reuse = slice(0x801FEC44 - TEXT_TO_RAM, 0x801FEC84 - TEXT_TO_RAM)
                self.assertEqual(output[reuse], dol[reuse])
                if not custom:
                    gift = PID_CALLS['espeon'] - TEXT_TO_RAM
                    self.assertEqual(output[gift:gift + 4], dol[gift:gift + 4])
                    self.assertFalse(report['enabled'])
