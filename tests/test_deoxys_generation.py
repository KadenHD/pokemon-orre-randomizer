"""Execute form-PID hooks against an ABI-clobbering native generator double."""
from dataclasses import replace
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.deoxys import (
    BASE_STAT_FIELDS, BASE_STATS, DEOXYS, FORM_ORDER, encounter_forms,
    form_label, form_seed,
)
from orre_randomizer.engine.deoxys_generation import colo_deoxys_seeds, deoxys_pid_call, trainer_form_tag
from orre_randomizer.deoxys_identity import FORM_TAG, form_offset
from orre_randomizer.engine.dol_regions import PAL
from orre_randomizer.engine.shiny_rules import (
    PID_GENERATOR, SECTION_RAM, _pid_wrapper, _seeded_trainer_wrapper,
    _spinda_pid_call, apply_shiny_rules,
)
from orre_randomizer.engine.spinda import SPINDA
from orre_randomizer.options import Options
from tests.test_colo_spinda import POKEMON, RNG_INITIAL, RNG_STATE, RNG_POINTER_DISPLACEMENT
from tests.test_shiny_rules import Machine, is_shiny


class FormMachine(Machine):
    def __init__(self, data, address, pids):
        super().__init__(data, address)
        self.pids = iter(pids)
        self.states = []
        self.write(self.reg[13] + RNG_POINTER_DISPLACEMENT, RNG_STATE)
        self.write(RNG_STATE, RNG_INITIAL)

    def native(self, target):
        if target != PID_GENERATOR:
            return super().native(target)
        self.calls.append((target, self.reg[3:8].copy()))
        state = self.read(RNG_STATE)
        self.states.append(state)
        self.write(RNG_STATE, (state * 0x343FD + 0x269EC3) & 0xFFFFFFFF)
        pid = next(self.pids)
        for i in (0, *range(3, 13)):
            self.reg[i] = 0xDEAD0000 + i
        self.reg[3] = pid


class DeoxysIdentity(unittest.TestCase):
    def test_form_seeds_are_stable_unicode_domain_separated_and_not_zero(self):
        first = form_seed('été - 日本', 'colo:shadow:21')
        self.assertEqual(first, form_seed('été - 日本', 'colo:shadow:21'))
        self.assertNotEqual(first, form_seed('été - 日本', 'colo:shadow:22'))
        self.assertNotEqual(first, form_seed('other', 'colo:shadow:21'))
        forms = {form_seed('forms', f'colo:trainer:{n}') >> 30 for n in range(100)}
        self.assertEqual(forms, {0, 1, 2, 3})
        for seed, key in (('', 'key'), (' ' * 2, 'key'), ('x' * 257, 'key'), ('x', ''), ('x', 'é')):
            with self.assertRaises(ValueError):
                form_seed(seed, key)

    def test_seed_preview_official_stats_and_labels_agree_on_form_indices(self):
        for index, name in enumerate(FORM_ORDER):
            self.assertEqual(encounter_forms({'key': (index << 30) | 1}), {'key': index})
            self.assertIn(name, BASE_STATS)
            self.assertEqual(len(BASE_STATS[name]), len(BASE_STAT_FIELDS))
            for language in ('fr', 'en', 'de', 'es', 'it', 'ja'):
                self.assertEqual(form_label(name, language), form_label(index, language))
                self.assertTrue(form_label(name, language))
        self.assertEqual(BASE_STATS['attack'], (50, 180, 20, 180, 20, 150))
        self.assertEqual(BASE_STATS['defense'], (50, 70, 160, 70, 160, 90))
        self.assertEqual(BASE_STATS['speed'], (50, 95, 90, 95, 90, 180))
        self.assertEqual(form_label(1, 'unknown'), form_label(1, 'en'))
        for token in (-1, 0, 2**32, True):
            with self.assertRaises(ValueError):
                encounter_forms({'key': token})

    def test_seed_collection_keeps_retained_deoxys_normal_and_applies_aliases(self):
        original, current = bytearray(8 * 24), bytearray(8 * 24)
        for slot, before, after, shadow in ((0, 25, DEOXYS, 0), (1, 25, DEOXYS, 0),
                                             (2, DEOXYS, DEOXYS, 0), (3, 25, DEOXYS, 21),
                                             (4, 25, DEOXYS, 21), (5, 25, 25, 0),
                                             (6, 25, DEOXYS, 0), (7, DEOXYS, DEOXYS, 0)):
            struct.pack_into('>H', original, slot * 24 + 10, before)
            struct.pack_into('>H', current, slot * 24 + 10, after)
            current[slot * 24 + 3] = shadow
        dol_original, dol_current = bytearray(8), bytearray(8)
        struct.pack_into('>H', dol_original, 2, 25)
        struct.pack_into('>H', dol_current, 2, DEOXYS)
        shape = ({'trainer_pokemon': {'offset': 0, 'stride': 24, 'count': 8}},)
        with patch('orre_randomizer.engine.randomize_trainers.layout', return_value=shape), \
             patch('orre_randomizer.engine.dol_regions.special_targets', return_value=({'key': 'pikachu-event', 'base': 0},)):
            result = colo_deoxys_seeds(original, current, dol_original, dol_current, 'forms',
                ((0, 1),), trainer_special_aliases=((6, 'pikachu-event'),),
                extra_rows=({'slot': 5510, 'species': DEOXYS, 'shadow_id': 49},))
        self.assertEqual(result['trainer:0'], result['trainer:1'])
        self.assertEqual(result['trainer:6'], result['special:pikachu-event'])
        self.assertEqual(result['trainer:2'] >> 30, 0)
        self.assertEqual(result['trainer:7'] >> 30, 0)
        self.assertIn('shadow:21', result)
        self.assertIn('shadow:49', result)
        self.assertNotIn('trainer:5', result)
        self.assertNotIn('trainer:3', result)

class DeoxysGenerationABI(unittest.TestCase):
    def test_initial_tag_keeps_native_pid_arguments_rng_result_and_abi(self):
        address = SECTION_RAM + 32
        code = deoxys_pid_call(address, 0x8474, PAL, _spinda_pid_call)
        for desired in range(4):
            seed = (desired << 30) | 0x1234567
            candidates = [0x12340000 | (desired + 1) % 4]
            machine = FormMachine(code, address, candidates)
            machine.reg[3:9] = [POKEMON, 2, 7, 1, 0xABCDEF01, seed]
            machine.write(POKEMON, DEOXYS, 2)
            machine.write(POKEMON + form_offset('GC6P01'), 0, 2)
            before, old_lr = machine.reg.copy(), machine.lr
            machine.run()
            self.assertEqual(machine.calls, [(PID_GENERATOR, before[3:8])])
            self.assertEqual(machine.states, [RNG_INITIAL])
            self.assertEqual(machine.read(RNG_STATE), (RNG_INITIAL * 0x343FD + 0x269EC3) & 0xFFFFFFFF)
            self.assertEqual(machine.reg[3], candidates[-1])
            self.assertNotEqual(machine.reg[3] & 3, desired)
            self.assertEqual(machine.read(POKEMON + form_offset('GC6P01'), 2), FORM_TAG | desired)
            self.assertEqual(machine.reg[1], before[1])
            self.assertEqual(machine.reg[13:], before[13:])
            self.assertEqual(machine.lr, old_lr)

    def test_spinda_zero_seed_and_unrelated_species_keep_legacy_semantics(self):
        address = SECTION_RAM + 32
        for species, seed in ((SPINDA, 0x1234567), (25, 0x1234567), (DEOXYS, 0)):
            code = deoxys_pid_call(address, 0x8474, PAL, _spinda_pid_call)
            machine = FormMachine(code, address, [0xABCDEF12])
            machine.reg[3:9] = [POKEMON, 2, 7, 0, 0x12345678, seed]
            machine.write(POKEMON, species, 2)
            machine.run()
            gender = seed >> 31 if species == SPINDA and seed else 2
            self.assertEqual(machine.calls, [(PID_GENERATOR, [POKEMON, gender, 7, 0, 0x12345678])])
            expected_seed = seed if species == SPINDA and seed else RNG_INITIAL
            self.assertEqual(machine.states, [expected_seed])

    def test_shared_trainer_tables_never_apply_spinda_owner_to_deoxys(self):
        helper = SECTION_RAM + 32
        trainer_seeds, shadow_seeds = 0x81600000, 0x81608000
        trainer_flags, shadow_flags = 0x81610000, 0x81618000
        for seeded in (False, True):
            code = deoxys_pid_call(helper, 0x8474, PAL, _spinda_pid_call)
            wrapper = helper + len(code)
            if seeded:
                code += _seeded_trainer_wrapper(wrapper, trainer_flags, shadow_flags,
                    spinda_pid=helper, spinda_tables=(trainer_seeds, shadow_seeds), owner_species_guard=True)
            else:
                code += _pid_wrapper(wrapper, None, trainers=True, spinda_pid=helper,
                    spinda_tables=(trainer_seeds, shadow_seeds), owner_species_guard=True)
            machine = FormMachine(code, helper, [0xABCD0001])
            machine.pc = wrapper
            machine.reg[3:8] = [POKEMON, 2, 7, 1, 0x12345678]
            machine.reg[30] = 0
            machine.write(POKEMON, DEOXYS, 2)
            machine.write(POKEMON + form_offset('GC6P01'), 0, 2)
            machine.write(machine.reg[1] + 0x48, 5)
            machine.write(trainer_seeds + 5 * 4, 0x81234567)
            machine.write(trainer_flags + 5, 1, 1)
            machine.run()
            self.assertEqual(machine.calls, [(PID_GENERATOR, [POKEMON, 2, 7, 1, 0x12345678])])
            self.assertEqual(machine.reg[3], 0xABCD0001)
            self.assertEqual(machine.read(POKEMON + form_offset('GC6P01'), 2), FORM_TAG | 2)

    def test_existing_changed_forms_and_foreign_reservations_are_not_reset(self):
        address = SECTION_RAM + 32
        code = deoxys_pid_call(address, 0x8474, PAL, _spinda_pid_call)
        for original_tag in (FORM_TAG | 3, 0x1234):
            machine = FormMachine(code, address, [0x12345678])
            machine.reg[3:9] = [POKEMON, 2, 7, 1, 0x12345678, 0x41234567]
            machine.write(POKEMON, DEOXYS, 2)
            machine.write(POKEMON + form_offset('GC6P01'), original_tag, 2)
            machine.run()
            self.assertEqual(machine.read(POKEMON + form_offset('GC6P01'), 2), original_tag)
            self.assertEqual(machine.reg[3], 0x12345678)

    def test_trainer_finalization_tags_both_fresh_and_cached_shadow_records(self):
        address, continuation = SECTION_RAM + 32, 0x801FED44
        tables = (0x81600000, 0x81608000)
        code = trainer_form_tag(address, continuation, tables, game_id='GC6P01', trainer_slot_count=100)
        for species, shadow, slot, prior, expected in (
                (DEOXYS, 0, 5, 0, FORM_TAG | 2),
                (DEOXYS, 21, 5, 0, FORM_TAG | 3),
                (DEOXYS, 97, 5, 0, 0), (DEOXYS, 0, 100, 0, 0),
                (DEOXYS, 21, 5, FORM_TAG | 1, FORM_TAG | 1),
                (DEOXYS, 21, 5, 0x1234, 0x1234), (25, 21, 5, 0, 0)):
            machine = FormMachine(code, address, [])
            machine.reg[31], machine.reg[30] = POKEMON, shadow
            machine.write(POKEMON, species, 2)
            machine.write(POKEMON + form_offset('GC6P01'), prior, 2)
            machine.write(POKEMON + 4, 0x89ABCDEF)
            machine.write(machine.reg[1] + 0x48, slot)
            machine.write(tables[0] + 5 * 4, 0x81234567)
            machine.write(tables[1] + 21 * 4, 0xC1234567)
            machine.run(stop=continuation)
            self.assertEqual(machine.reg[3], POKEMON)
            self.assertEqual(machine.read(POKEMON + form_offset('GC6P01'), 2), expected)
            self.assertEqual(machine.read(POKEMON + 4), 0x89ABCDEF)
            self.assertEqual(machine.calls, [])
            self.assertEqual(machine.read(RNG_STATE), RNG_INITIAL)

    def test_absent_deoxys_option_keeps_emitted_legacy_bytes(self):
        address = 0x81500020
        hashes = {
            'd4c3885088664dcf652c30a4c6ffbfac7be31616b6bc19509d5689be77aac616': _spinda_pid_call(address, 0x8474, PAL),
            '99d3f3a87926f3559a0d44efd340f1536e16eff2bd33988a7f81a94f8083c43b': _pid_wrapper(
                address, None, trainers=True, spinda_pid=0x81502000, spinda_tables=(0x81503000, 0x81509000)),
            '97d36588195faff8b4d905bb253ef824f2879c4d94391dcd31d46242b20edfc7': _seeded_trainer_wrapper(
                address, 0x81504000, 0x81506000, spinda_pid=0x81502000, spinda_tables=(0x81503000, 0x81509000)),
        }
        for expected, emitted in hashes.items():
            self.assertEqual(hashlib.sha256(emitted).hexdigest(), expected)

    def test_invalid_and_colliding_private_seeds_fail_before_native_reads(self):
        for seeds in ({'trainer:0': 0}, {'shadow:0': 1}, {'shadow:97': 1},
                      {'trainer:99999': 1}, {'special:trainers': 1}, {'bad': 1}):
            with self.assertRaises(ValueError):
                apply_shiny_rules(b'', b'', Options(), deoxys_seeds=seeds)
        with self.assertRaises(ValueError):
            apply_shiny_rules(b'', b'', Options(), spinda_seeds={'trainer:1': 3}, deoxys_seeds={'trainer:1': 2})


ORIGINAL = Path(__file__).resolve().parents[1] / 'game/sys/main.dol'


@unittest.skipUnless(ORIGINAL.is_file(), "requires user's original PAL DOL")
class DeoxysShinyComposition(unittest.TestCase):
    def test_shared_resolver_keeps_reports_separate_and_no_deoxys_is_byte_identical(self):
        original = ORIGINAL.read_bytes()
        spinda = {'trainer:5': 0x12345678}
        deoxys = {'trainer:6': 0x81234567, 'special:plusle': 0xC1234567}
        for custom in (False, True):
            options = replace(Options(), custom_shinies=custom)
            before, report = apply_shiny_rules(original, original, options, seed='forms', spinda_seeds=spinda)
            absent, _ = apply_shiny_rules(original, original, options, seed='forms', spinda_seeds=spinda, deoxys_seeds={})
            self.assertEqual(before, absent)
            result, report = apply_shiny_rules(original, original, options, seed='forms',
                spinda_seeds=spinda, deoxys_seeds=deoxys)
            self.assertEqual(report['spinda_pid']['seeds'], spinda)
            self.assertEqual(report['deoxys_pid']['seeds'], deoxys)
            self.assertEqual(report['deoxys_pid']['resolver'], report['spinda_pid']['resolver'])
            self.assertNotEqual(result, before)
            only, report = apply_shiny_rules(original, original, options, seed='forms', deoxys_seeds=deoxys)
            self.assertIn('deoxys_pid', report)
            self.assertNotIn('spinda_pid', report)
