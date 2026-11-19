"""Native legendary Shadow species stay fixed unless explicitly randomized."""
from dataclasses import replace
from pathlib import Path
import struct
import threading
import unittest
from unittest.mock import patch

from orre_randomizer import xd
from orre_randomizer.engine.analyze_game import parse_fsys, parse_rel, u32
from orre_randomizer.engine.inspect_tables import rel_symbols, u16
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL
from orre_randomizer.engine.survey_assets import fst_inventory
from orre_randomizer.service import UserError
from orre_randomizer.xd_preview import baseline_rows


def fixture():
    native = {1: 216, 2: 4, 73: 249, 74: 144, 75: 145, 76: 146, 81: 175}
    shadows = {sid: index for index, sid in enumerate(native, 1)}
    start = 0x30 + 2*0x38
    deck = bytearray(start + 9*0x20)
    struct.pack_into('>4sII', deck, 0x10, b'DTNR', 0x10 + 2*0x38, 2)
    struct.pack_into('>4sII', deck, start-0x10, b'DPKM', 0x10 + 9*0x20, 9)
    for ordinal, (sid, species) in enumerate(native.items()):
        trainer, slot = divmod(ordinal, 6)
        deck[0x20 + trainer*0x38 + 4] |= 1 << slot
        struct.pack_into('>H', deck, 0x20 + trainer*0x38 + 0x1c + slot*2, sid)
        position = start + shadows[sid]*0x20
        struct.pack_into('>HBB', deck, position, species, 50, 10)
    struct.pack_into('>H', deck, 0x20 + 0x38 + 0x1e, 8)
    struct.pack_into('>HBB', deck, start + 8*0x20, 7, 50, 10)
    species = {index: (index, 0, 300, ((1, 33),))
               for index in {*range(1, 40), 133, *native.values()}}
    families = {index: index for index in species}
    return bytes(deck), start, shadows, native, species, families


class XDLegendaryShadowsTests(unittest.TestCase):
    def test_both_presets_keep_native_legendary_species_by_default(self):
        for options in (xd.XDOptions.recommended(), xd.XDOptions.species_only()):
            self.assertFalse(options.randomize_legendary_shadows)
            self.assertFalse(options.allow_legendaries)

    def test_original_legendaries_remain_even_when_excluded_from_replacement_pool(self):
        deck, start, slots, native, species, families = fixture()
        options = replace(xd.XDOptions.unchanged(), randomize_shadows=True, balance_species=False)
        eligible = {i for i, row in species.items() if row[0] not in LEGENDARY_NATIONAL}
        before = bytes(deck)
        for seed in ('birds-a', 'birds-b'):
            result, report = xd._deck(deck, 'Story', slots, seed, species, families, set(), options, eligible)
            choices = {row['shadow_id']: row['species'] for row in report['shadows']}
            for sid in (73, 74, 75, 76):
                self.assertEqual(choices[sid], native[sid])
                self.assertEqual(result[start + slots[sid]*0x20:start + (slots[sid]+1)*0x20],
                                 before[start + slots[sid]*0x20:start + (slots[sid]+1)*0x20])
            self.assertNotEqual(choices[2], native[2])
            self.assertEqual(deck, before)

    def test_protection_does_not_freeze_non_shadow_legendary_opponents(self):
        deck, start, slots, _native, species, families = fixture()
        deck = bytearray(deck)
        struct.pack_into('>H', deck, start + 8*0x20, 144)
        options = replace(xd.XDOptions.unchanged(), randomize_trainers=True, balance_species=False)
        result, report = xd._deck(bytes(deck), 'Story', slots, 'regular-legendary',
                                   species, families, set(), options)
        self.assertNotEqual(u16(result, start + 8*0x20), 144)
        self.assertEqual(next(row['species'] for row in report['shadows'] if row['shadow_id'] == 74), 144)

    def test_precalculation_preview_knows_protected_birds_and_always_knows_xd001(self):
        for enabled in (False, True):
            options = replace(xd.XDOptions.recommended(), randomize_legendary_shadows=enabled)
            rows = {row['shadow_id']: row for row in baseline_rows(options)['decks']['Story']['shadows']}
            for sid, original in ((74, 145), (75, 146), (76, 144)):
                self.assertEqual(rows[sid]['species'], None if enabled else original)
            self.assertEqual(rows[73]['species'], 249)

    def test_opt_in_randomizes_each_bird_but_keeps_native_xd001_protection(self):
        deck, _start, slots, native, species, families = fixture()
        options = replace(xd.XDOptions.unchanged(), randomize_shadows=True,
                          randomize_legendary_shadows=True, balance_species=False)
        first = xd._deck(deck, 'Story', slots, 'change-birds', species, families, set(), options)
        self.assertEqual(first, xd._deck(deck, 'Story', slots, 'change-birds', species, families, set(), options))
        choices = {row['shadow_id']: row['species'] for row in first[1]['shadows']}
        for sid in (74, 75, 76):
            self.assertNotEqual(choices[sid], native[sid])
        self.assertEqual(choices[73], 249)

    def test_boss_filters_cannot_replace_fixed_native_legendaries(self):
        deck, _start, slots, native, species, families = fixture()
        options = replace(xd.XDOptions.unchanged(), randomize_shadows=True,
                          boss_shadow_legendary_mode='exclude', boss_shadow_min_bst=600)
        # Admit only the native birds as bosses, then make their replacement
        # filters impossible. Protected slots must bypass replacement entirely.
        with patch('orre_randomizer.xd.boss_shadows', return_value={74, 75, 76}):
            _, report = xd._deck(deck, 'Story', slots, 'boss-birds', species, families, set(), options)
        choices = {row['shadow_id']: row['species'] for row in report['shadows']}
        self.assertEqual({sid: choices[sid] for sid in (74, 75, 76)},
                         {sid: native[sid] for sid in (74, 75, 76)})

    def test_fixed_families_are_reserved_before_the_starter_and_other_shadows(self):
        deck, _start, slots, _native, species, families = fixture()
        options = replace(xd.XDOptions.unchanged(), randomize_starter=True,
                          randomize_starter_moves=True, randomize_shadows=True,
                          unique_shadow_families=True, diverse_story_families=True,
                          balance_species=False, starter_stage='any')
        fixed = xd._fixed_shadow_species(deck, slots, species, options)
        reserved = {families[index] for index in fixed.values()}
        dol = bytearray(0x68)
        for at, word in zip((0, 8, 0x10, 0x14, 0x18, 0x1c, 0x64),
                            (0x38600085, 0x3900000a, 0x38c00021, 0x38a00027,
                             0x3880002c, 0x3800001c, 0x380004e2), strict=True):
            struct.pack_into('>I', dol, at, word)
        mover = type('Moves', (), {'moves': lambda *_args: [33, 39, 44, 28]})()
        _, starter = xd._starter(bytes(dol), 0, 'fixed-families', species, {}, families,
                                {25, 144, 145, 146}, options, mover, fixed_shadow_families=reserved)
        self.assertEqual(starter['species'], 25)
        _, report = xd._deck(deck, 'Story', slots, 'fixed-families', species, families,
                             reserved | {25}, options, fixed_shadows=fixed)
        ordinary = next(row for row in report['shadows'] if row['shadow_id'] == 2)
        self.assertNotIn(ordinary['family'], reserved | {25})

    def test_preserve_boss_legendary_status_needs_no_legendary_pool_when_originals_are_fixed(self):
        options = replace(xd.XDOptions.unchanged(), randomize_shadows=True,
                          allow_gen1=True, allow_legendaries=False, boss_shadow_legendary_mode='preserve')
        self.assertEqual(xd.validate_options(options), options)
        with self.assertRaises(UserError):
            xd.validate_options(replace(options, randomize_legendary_shadows=True))


class XDNativeLegendaryShadowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iso = Path(__file__).resolve().parents[1]/'build/xd-validation/verified-eu.iso'
        if not cls.iso.is_file():
            raise unittest.SkipTest('requires a locally retained original European XD disc')
        with cls.iso.open('rb') as stream:
            cls.boot = stream.read(0x440)
            stream.seek(u32(cls.boot, 0x424))
            files = fst_inventory(stream.read(u32(cls.boot, 0x428)))[0]
            cls.archives = {}
            for name in ('common.fsys', 'deck_archive.fsys'):
                entry = next(row for row in files if row['path'] == name)
                stream.seek(entry['disc_offset'])
                cls.archives[name] = stream.read(entry['size'])
        common = cls.archives['common.fsys']
        members = {row['name']: row for row in parse_fsys(common)['members']}
        cls.rel = decoded_member(common, members['common_rel'])
        cls.symbols = rel_symbols(cls.rel, parse_rel(cls.rel))
        cls.species, cls.edges, cls.families = xd._species(cls.rel, cls.symbols)
        archive = cls.archives['deck_archive.fsys']
        cls.decks = {row['name']: decoded_member(archive, row) for row in parse_fsys(archive)['members']}

    def test_default_draws_exclude_legendaries_across_starter_gifts_shadows_and_poke_spots(self):
        for options in (xd.XDOptions.recommended(), xd.XDOptions.species_only()):
            for seed in ('default-no-legends-a', 'default-no-legends-b'):
                with self.subTest(moves=options.randomize_trainer_moves, seed=seed):
                    _, summary = xd.build_patches(self.iso, self.boot, seed,
                        options, lambda *_args: None, threading.Event())
                    self.assertEqual(summary['castform_portraits']['game_id'], 'GXXP01')
                    self.assertTrue(summary['castform_portraits']['native_async_loading'])
                    self.assertTrue(summary['castform_portraits']['save_data_unchanged'])
                    self.assertTrue(summary['poke_spot_shinies']['enabled'])
                    self.assertEqual(summary['poke_spot_shinies']['chance_percent'], 5.0)
                    self.assertEqual(len(summary['poke_spot_shinies']['hooks']), 5)
                    self.assertTrue(all('shiny' not in row for row in summary['poke_spots']))
                    self.assertTrue(all(row['shiny_model_resource'] != row['model_resource']
                                        for row in summary.get('poke_spot_actors', ())))
                    for row in (summary['starter'], *summary['gifts'], *summary['poke_spots']):
                        self.assertNotIn(self.species[row['species']][0], LEGENDARY_NATIONAL, row)
                    for row in summary['decks']['Story']['shadows']:
                        if self.species[row['original']][0] in LEGENDARY_NATIONAL:
                            self.assertEqual(row['species'], row['original'])
                        else:
                            self.assertNotIn(self.species[row['species']][0], LEGENDARY_NATIONAL, row)

    def test_native_story_and_eu_variant_agree_with_both_legendary_policies(self):
        eligible = set(self.species)
        for enabled in (False, True):
            options = replace(xd.XDOptions.recommended(), randomize_legendary_shadows=enabled)
            summaries = []
            for suffix in ('', '_EU'):
                deck = self.decks[f'DeckData_Story{suffix}.bin']
                slots = xd._shadow_slots(self.decks[f'DeckData_DarkPokemon{suffix}.bin'])
                _, report = xd._deck(deck, 'Story', slots, 'native-legendary-policy', self.species,
                                     self.families, set(), options, eligible)
                birds = [row for row in report['shadows'] if self.species[row['original']][0] in (144, 145, 146)]
                self.assertEqual(len(birds), 3)
                for row in birds:
                    self.assertEqual(row['species'] == row['original'], not enabled)
                self.assertEqual(next(row['species'] for row in report['shadows'] if row['shadow_id'] == 73), 249)
                summaries.append(report)
            self.assertEqual(*summaries)

    def test_native_boss_filters_apply_to_randomized_birds_only(self):
        deck = self.decks['DeckData_Story.bin']
        slots = xd._shadow_slots(self.decks['DeckData_DarkPokemon.bin'])
        for enabled in (False, True):
            options = replace(xd.XDOptions.recommended(), randomize_legendary_shadows=enabled,
                              boss_shadow_legendary_mode='exclude', boss_shadow_power_mode='similar')
            _, report = xd._deck(deck, 'Story', slots, 'native-boss-birds', self.species,
                                 self.families, set(), options)
            birds = [row for row in report['shadows'] if self.species[row['original']][0] in (144, 145, 146)]
            for row in birds:
                if enabled:
                    self.assertNotIn(self.species[row['species']][0], LEGENDARY_NATIONAL)
                else:
                    self.assertEqual(row['species'], row['original'])
            self.assertEqual(next(row['species'] for row in report['shadows'] if row['shadow_id'] == 73), 249)

    def test_native_creation_reserves_fixed_birds_for_starters_and_gifts(self):
        options = replace(xd.XDOptions.unchanged(), randomize_starter=True, randomize_gifts=True,
                          randomize_shadows=True, diverse_story_families=True, unique_shadow_families=True,
                          allow_gen1=True, allow_gen2=True, allow_gen3=True,
                          allow_legendaries=True, balance_species=False)
        _, summary = xd.build_patches(self.iso, self.boot, 'native-fixed-bird-families',
                                      options, lambda *_args: None, threading.Event())
        birds = {row['family'] for row in summary['decks']['Story']['shadows']
                 if self.species[row['original']][0] in (144, 145, 146)}
        self.assertEqual(len(birds), 3)
        self.assertNotIn(self.families[summary['starter']['species']], birds)
        self.assertTrue(all(row['family'] not in birds for row in summary['gifts']))
