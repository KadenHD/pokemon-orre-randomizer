from pathlib import Path
import hashlib
import copy
import struct
import unittest

from orre_randomizer.fairy_tms import (
    ADDITIONAL_TMS, CANONICAL_MOVES, ITEM_IDS, MACHINE_INDICES, MOVE_IDS,
    NATIVE_POCKET_CAPACITY, _QUALIFIED, _compatibility, _display_number,
    _machine_move, _move_getter, _move_rows, _physical_category, compatibility_bytes,
    extra_item_catalog, install_additional_tms, read_installed_content,
    plan_tms, permute_compatibility, _item_name_refresh, prepare_candidate_moves, _contest_effect,
    _ordinary_validity, _menu_move_count,
)
from orre_randomizer.deoxys_meteorite import _read, _offset
from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from tests.test_deoxys_meteorite import ItemMachine

BASE, TABLE, CONTINUE, SPECIES = 0x81500020, 0x81510000, 0x80100000, 0x80600000
ROOT = Path(__file__).resolve().parents[1]


def run(code, args, *, rows=(), stop=None):
    machine = ItemMachine(code, BASE)
    machine.reg[3:3 + len(args)] = args
    for address, data in rows:
        for i, value in enumerate(data):
            machine.write(address + i, value, 1)
    before = machine.reg.copy()
    original_lr = machine.lr
    original_sp = machine.reg[1]
    machine.run(stop=stop)
    assert machine.lr == original_lr and machine.reg[1] == original_sp
    assert machine.reg[14:] == before[14:]
    return machine


def move_rows():
    result = {}
    for index, move in enumerate(MOVE_IDS):
        row = bytearray(0x38)
        row[1], row[2] = 10, 19
        struct.pack_into('>I', row, 0x20, 0xF0500 + index)
        result[move] = bytes(row)
    return result


class AdditionalTMContracts(unittest.TestCase):
    def test_battle_menu_count_guard_extends_only_owned_ids_without_changing_registers(self):
        code = _menu_move_count(BASE, CONTINUE, 0x7C1D0040)
        for move in (0, 1, 354, 355, 357, 358, 374, *MOVE_IDS, 382, 65535):
            for count in (0, 1, 355, 358, 375, 382, 65535):
                machine = ItemMachine(code, BASE)
                machine.reg[29], machine.reg[0] = move, count
                before, lr, sp = machine.reg.copy(), machine.lr, machine.reg[1]
                machine.run(stop=CONTINUE)
                expected = (True, False) if move in MOVE_IDS else (move < count, move == count)
                self.assertEqual(machine.cr, expected, (move, count))
                self.assertEqual(machine.reg, before)
                self.assertEqual((machine.lr, machine.reg[1]), (lr, sp))

    def test_xd_ordinary_slot_id_predicate_whitelists_only_the_seven_added_moves(self):
        code = _ordinary_validity(BASE, CONTINUE)
        # Exhaust every native u16 input, including Shadow and unknown IDs.
        for move in range(65536):
            machine = ItemMachine(code, BASE)
            machine.reg[0] = move
            before, lr, sp = machine.reg.copy(), machine.lr, machine.reg[1]
            machine.run(stop=CONTINUE)
            self.assertEqual(machine.reg[3], int(move < 355 or move in MOVE_IDS))
            self.assertEqual(machine.reg[0], move)
            self.assertEqual(machine.reg[14:], before[14:])
            self.assertEqual((machine.lr, machine.reg[1]), (lr, sp))

    def test_original_tm_name_can_open_its_new_description_before_any_move_lookup(self):
        refresh = 0x81520000
        class RefreshMachine(ItemMachine):
            native_targets = {refresh}
            def native(self, target):
                self.calls.append(target)
                for i in (0, *range(3, 13)): self.reg[i] = 0xBAD00000 + i
        for field, description, expected in ((0x10, 0xF0410, 0), (0x14, 0xF0410, 1),
                                              (0x14, 10195, 0), (0x14, 0xF044D, 1)):
            code = _item_name_refresh(BASE, CONTINUE, 0x28030000, refresh, field=field)
            m = RefreshMachine(code, BASE)
            m.reg[3] = SPECIES
            m.write(SPECIES + 0x10, 289)  # Native TM01 name never enters F04.
            m.write(SPECIES + 0x14, description)
            old_sp, old_lr, preserved = m.reg[1], m.lr, m.reg[14:].copy()
            m.run(stop=CONTINUE)
            self.assertEqual(len(m.calls), expected)
            self.assertEqual(m.reg[3], SPECIES)
            self.assertEqual(m.reg[1], old_sp); self.assertEqual(m.lr, old_lr)
            self.assertEqual(m.reg[14:], preserved)

    def test_virtual_contest_effect_preserves_every_native_index(self):
        code = _contest_effect(BASE, CONTINUE, 0x60000000, TABLE)
        for index in (0, 1, 30, 50, 51, 254, 255, 256, 65535):
            m = run(code, [index], stop=None if index == 255 else CONTINUE)
            self.assertEqual(m.reg[3], TABLE if index == 255 else index)

    def test_private_message_refresh_preserves_arguments_and_only_runs_for_owned_names(self):
        refresh = 0x81520000
        class RefreshMachine(ItemMachine):
            native_targets = {refresh}
            def native(self, target):
                self.calls.append(target)
                for i in (0, *range(3, 13)): self.reg[i] = 0xDEAD0000 + i
        for name in (0, 1, 2000, 0xF03FF, 0xF0400, 0xF0440, 0xF04FF, 0xF0500):
            code = _item_name_refresh(BASE, CONTINUE, 0x28030000, refresh)
            m = RefreshMachine(code, BASE); m.reg[3] = SPECIES
            m.write(SPECIES + 16, name)
            before = m.reg.copy(); lr = m.lr
            m.run(stop=CONTINUE)
            self.assertEqual(len(m.calls), int(0xF0400 <= name < 0xF0500))
            self.assertEqual(m.reg[3], SPECIES)
            self.assertEqual(m.reg[1], before[1]); self.assertEqual(m.lr, lr)
            self.assertEqual(m.reg[14:], before[14:])
        m = RefreshMachine(code, BASE); m.reg[3] = 0; m.run(stop=CONTINUE)
        self.assertFalse(m.calls)
        code = _move_getter(BASE, CONTINUE, 0x60000000, TABLE, refresh=refresh)
        for move in (354, 374, *MOVE_IDS, 382):
            m = RefreshMachine(code, BASE); m.reg[3] = move
            before = m.reg.copy(); lr = m.lr
            m.run(stop=None if move in MOVE_IDS else CONTINUE)
            self.assertEqual(len(m.calls), int(move in MOVE_IDS))
            self.assertEqual(m.reg[3], TABLE + (move - 375) * 56 if move in MOVE_IDS else move)
            self.assertEqual(m.reg[1], before[1]); self.assertEqual(m.lr, lr)
            self.assertEqual(m.reg[14:], before[14:])

    def test_complete_tm_permutation_carries_descriptions_and_compatibility(self):
        from orre_randomizer.engine.tm_rules import ORIGINAL_TM_MOVES
        descriptions = {move: 0xF0401 + i * 2 for i, move in enumerate(MOVE_IDS)}
        plain = plan_tms('fairy-a', extra_description_ids=descriptions)
        self.assertEqual(plain['source_order'], list(range(57)))
        plan = plan_tms('fairy-a', extra_description_ids=descriptions, shuffle=True)
        self.assertEqual(plan, plan_tms('fairy-a', extra_description_ids=descriptions, shuffle=True))
        self.assertNotEqual(plan['source_order'], plan_tms('fairy-b', extra_description_ids=descriptions, shuffle=True)['source_order'])
        self.assertEqual(sorted(plan['source_order']), list(range(57)))
        self.assertTrue(all(i != source for i, source in enumerate(plan['source_order'])))
        self.assertEqual({row['machine_index'] for row in plan['mapping']}, {*range(50), *range(58, 65)})
        pool = (*ORIGINAL_TM_MOVES, *MOVE_IDS)
        descs = (*range(10195, 10245), *(descriptions[move] for move in MOVE_IDS))
        for row, source in zip(plan['mapping'], plan['source_order']):
            self.assertEqual(row['after_move'], pool[source])
            self.assertEqual(row['after_description_id'], descs[source])
        self.assertTrue(set(MOVE_IDS) & {row['after_move'] for row in plan['mapping'][:50]})
        native, added = tuple(i % 2 for i in range(50)), (1, 1, 0, 0, 1, 1, 0)
        result = permute_compatibility(native, added, plan)
        self.assertEqual(result, tuple((*native, *added)[source] for source in plan['source_order']))
        self.assertEqual(permute_compatibility(native, added, plain), (*native, *added))
        bad = copy.deepcopy(plan); bad['mapping'][0]['after_description_id'] += 1
        with self.assertRaises(ValueError): permute_compatibility(native, added, bad)
        bad = copy.deepcopy(plan); bad['source_order'][0] = bad['source_order'][1]
        with self.assertRaises(ValueError): permute_compatibility(native, added, bad)
        bad = copy.deepcopy(plan); bad['native_hm_indices_unchanged'] = []
        with self.assertRaises(ValueError): permute_compatibility(native, added, bad)
        for invalid in ({}, {**descriptions, 375: 10195}):
            with self.assertRaises(ValueError): plan_tms('fairy-a', extra_description_ids=invalid)
        for invalid in ([0] * 49, [2] * 50, [0.] * 50):
            with self.assertRaises(ValueError): permute_compatibility(invalid, added, plain)

    def test_allocation_preserves_native_tm_hm_and_fits_native_saved_pocket(self):
        self.assertEqual(len(ADDITIONAL_TMS), 7)
        self.assertEqual([row.number for row in ADDITIONAL_TMS], list(range(51, 58)))
        self.assertEqual([row.machine_index for row in ADDITIONAL_TMS], list(range(58, 65)))
        self.assertFalse(set(ITEM_IDS) & {277, *range(289, 347)})
        self.assertFalse(set(MOVE_IDS) & set(range(355, 375)))
        self.assertEqual(CANONICAL_MOVES, (574, 577, 583, 584, 585, 605, 608))
        self.assertLessEqual(50 + len(ADDITIONAL_TMS), NATIVE_POCKET_CAPACITY)
        rows = extra_item_catalog()
        self.assertEqual(set(rows), set(ITEM_IDS))
        self.assertTrue(all(row['bag'] == 4 and row['safe'] for row in rows.values()))
        for price in (0, 65536, True, '3000'):
            with self.assertRaises(ValueError): extra_item_catalog(price=price)

    def test_new_move_rows_are_explicit_and_do_not_alias_canonical_ids(self):
        rows = move_rows()
        self.assertEqual(len(_move_rows(rows)), 7 * 0x38)
        for invalid in ({}, {**rows, 382: rows[375]}, {**rows, 375: bytes(0x38)},
                        {**rows, 375: rows[375][:-1]}):
            with self.assertRaises(ValueError): _move_rows(invalid)
        bad = bytearray(rows[375]); bad[2] = 18
        with self.assertRaises(ValueError): _move_rows({**rows, 375: bytes(bad)})
        with self.assertRaises(FormatError):
            prepare_candidate_moves(b'foreign table', 'GC6P01', move_message_ids={})

    def test_compatibility_matrix_is_bounded_and_absent_species_learn_none(self):
        blob = compatibility_bytes({1: [1, 0, 0, 0, 1, 0, 0], 386: [True] * 7})
        self.assertEqual(len(blob), 387 * 7)
        self.assertEqual(blob[:7], bytes(7))
        self.assertEqual(blob[7:14], bytes((1, 0, 0, 0, 1, 0, 0)))
        self.assertEqual(blob[-7:], bytes([1] * 7))
        for bad in ({0: [0] * 7}, {387: [0] * 7}, {1: [0] * 6}, {True: [0] * 7},
                    {1: [2] * 7}, {1: [0.] * 7}, {1: '0000000'}):
            with self.assertRaises(ValueError): compatibility_bytes(bad)

    def test_machine_lookup_serves_only_added_indices_and_preserves_native_fallback(self):
        code = _machine_move(BASE, CONTINUE, 0x60000000, TABLE)
        table = struct.pack('>7H', *MOVE_IDS)
        for index, move in zip(MACHINE_INDICES, MOVE_IDS):
            for high in (0, 0x123400):
                m = run(code, [index | high], rows=[(TABLE, table)])
                self.assertEqual(m.reg[3], move)
        for index in (0, 49, 50, 57, 65, 255):
            m = run(code, [index], rows=[(TABLE, table)], stop=CONTINUE)
            self.assertEqual(m.reg[3], index)

    def test_move_getter_serves_only_added_rows_and_masks_native_u16_input(self):
        code = _move_getter(BASE, CONTINUE, 0x60000000, TABLE)
        for index, move in enumerate(MOVE_IDS):
            for high in (0, 0x12340000):
                m = run(code, [move | high])
                self.assertEqual(m.reg[3], TABLE + index * 0x38)
        for move in (0, 1, 354, 355, 357, 374, 382, 65535):
            m = run(code, [move], stop=CONTINUE)
            self.assertEqual(m.reg[3], move)

    def test_both_compatibility_hooks_read_only_the_separate_columns(self):
        blob = compatibility_bytes({1: [1, 0, 1, 0, 1, 0, 1], 386: [0, 1, 0, 1, 0, 1, 0]})
        for xd in (False, True):
            code = _compatibility(BASE, CONTINUE, 0x60000000, TABLE, xd=xd)
            for national in (0, 1, 2, 386, 387, 65535):
                record = bytearray(0x124)
                struct.pack_into('>H', record, 0xE if xd else 0x10, national)
                for column in range(7):
                    m = run(code, [SPECIES, 58 + column], rows=[(TABLE, blob), (SPECIES, record)])
                    expected = blob[national * 7 + column] if national <= 386 else 0
                    self.assertEqual(m.reg[3], expected)
                    self.assertEqual(bytes(m.read(SPECIES + i, 1) for i in range(len(record))), record)
            self.assertEqual(run(code, [0, 58]).reg[3], 0)
            for index in (0, 49, 50, 57, 65, 65535):
                m = run(code, [SPECIES, index], stop=CONTINUE)
                self.assertEqual(m.reg[3], SPECIES)

    def test_display_number_remaps_only_added_physical_indices(self):
        for xd in (False, True):
            source, dest = (25, 24) if xd else (20, 19)
            word = 0x38000001 | dest << 21 | source << 16
            code = _display_number(BASE, CONTINUE, word, xd=xd)
            for index in (0, 49, 50, 57, 58, 59, 64, 65, 255):
                m = ItemMachine(code, BASE); m.reg[source] = index
                original = m.reg.copy(); lr = m.lr
                m.run(stop=CONTINUE)
                self.assertEqual(m.reg[dest], index + 1 - (8 if 58 <= index < 65 else 0))
                self.assertEqual(m.reg[source], index)
                self.assertEqual(m.lr, lr)
                self.assertTrue(all(m.reg[i] == original[i] for i in range(32) if i != dest))


    def test_only_play_rough_gets_physical_category_in_both_calling_conventions(self):
        for register, displaced in ((3, 0x60000000), (17, None)):
            code = _physical_category(BASE, CONTINUE, move_register=register, displaced=displaced)
            for move in (0, 1, 354, 355, 374, *MOVE_IDS, 382, 65535):
                m = ItemMachine(code, BASE); m.reg[3] = 19 if register == 17 else move
                m.reg[register] = move
                before = m.reg.copy(); original_lr = m.lr
                m.run(stop=None if move == 377 else CONTINUE)
                self.assertEqual(m.reg[3], 1 if move == 377 else before[3])
                self.assertEqual(m.lr, original_lr)
                self.assertEqual(m.reg[14:], before[14:])


PATHS = {**{game: ROOT / f'build/hd-completion/hud/{game}.dol' for game in ('GC6P01', 'GC6E01', 'GC6J01')},
         **{f'GXX{letter}01': ROOT / f'build/xd-validation/{region}/main.dol'
            for letter, region in (('P', 'eu'), ('E', 'us'), ('J', 'jp'))}}


@unittest.skipUnless(all(p.is_file() for p in PATHS.values()), 'requires six privately retained retail DOLs')
class AdditionalTMRetailQualifications(unittest.TestCase):
    def test_actual_xd_battle_eligibility_still_rejects_pp_and_status_restrictions(self):
        from tests.test_fairy_move_effects import EffectMachine, add_code
        from orre_randomizer.engine.gift_move_hooks import branch
        callers = {
            'GXXP01': (0x802030D4, 'a6fe9836bff5700517fcf56409a5521a05d99649c91019dc88c1e8db3c29c97b'),
            'GXXE01': (0x802013A0, '2c82512efdfd83b55992e9408bfa24fd92a6e32a562b47310250ea696a6d5646'),
            'GXXJ01': (0x801FC064, '881e8e979d055883f6431bd0299d08d1278600db425b3edcf5683c8873c7a642'),
        }
        roles = {'pokemon': 0x30, 'move': 0x3C, 'power': 0x44, 'pp': 0x54,
                 'item': 0x60, 'last': 0x6C, 'status': 0x7C, 'buff': 0x94,
                 'clear_torment': 0xF8, 'imprison': 0x130, 'validity': 0x1B8}
        for game, (entry, expected_hash) in callers.items():
            original = PATHS[game].read_bytes()
            caller = _read(original, entry, 0x1E8)
            self.assertEqual(hashlib.sha256(caller).hexdigest(), expected_hash)
            targets = {}
            for role, offset in roles.items():
                word = int.from_bytes(caller[offset:offset + 4], 'big')
                self.assertEqual(word & 0xFC000003, 0x48000001)
                delta = word & 0x3FFFFFC
                delta -= 0x4000000 if delta & 0x2000000 else 0
                targets[entry + offset + delta] = role
            validity_entry, size, _ = _QUALIFIED[game][1]['ordinary_validity_function']
            validity_site = _QUALIFIED[game][1]['ordinary_validity'][0]
            validity = bytearray(_read(original, validity_entry, size))
            struct.pack_into('>I', validity, validity_site - validity_entry, branch(validity_site, BASE))
            targets.pop(validity_entry)
            class EligibilityMachine(EffectMachine):
                native_targets = set(targets)
                def native(self, target):
                    role = targets[target]
                    self.calls.append((role, self.reg[3:7].copy()))
                    result = {'pokemon': SPECIES, 'move': selected_move,
                        'power': 0 if selected_move == 381 else 40, 'pp': pp,
                        'item': 0x1D if condition == 'choice' else 0,
                        'last': selected_move, 'clear_torment': 0,
                        'imprison': int(condition == 'imprison')}.get(role, 0)
                    if role == 'status':
                        result = int(self.reg[4] == {
                            'disabled': 0x29, 'torment': 0x1B,
                            'taunt': 0x30, 'choice': 0x36}.get(condition))
                    elif role == 'buff':
                        result = selected_move + int(condition == 'choice')
                    self.reg[3] = result
            for selected_move in (33, *MOVE_IDS, 355, 374, 382):
                for condition, pp, restriction in (('ordinary', 10, 0), ('ordinary', 0, 6),
                        ('disabled', 10, 1), ('torment', 10, 2), ('taunt', 10, 3),
                        ('imprison', 10, 4), ('choice', 10, 5)):
                    machine = EligibilityMachine(caller, entry)
                    add_code(machine, bytes(validity), validity_entry)
                    add_code(machine, _ordinary_validity(BASE, validity_site + 12), BASE)
                    machine.reg[3:7] = [SPECIES, 0, 0, TABLE]
                    before, lr, sp = machine.reg.copy(), machine.lr, machine.reg[1]
                    machine.run()
                    expected = 6 if selected_move in (355, 374, 382) else (
                        0 if condition == 'taunt' and selected_move != 381 else restriction)
                    self.assertEqual(machine.reg[3], expected, (game, selected_move, condition, pp))
                    self.assertEqual(machine.reg[14:], before[14:])
                    self.assertEqual((machine.lr, machine.reg[1]), (lr, sp))

    def test_actual_xd_slot_predicate_preserves_null_empty_and_shadow_guards(self):
        from tests.test_fairy_move_effects import EffectMachine, add_code
        from orre_randomizer.engine.gift_move_hooks import branch
        for game, path in PATHS.items():
            if not game.startswith('GXX'):
                continue
            original = path.read_bytes()
            entry, length, _ = _QUALIFIED[game][1]['ordinary_validity_function']
            site = _QUALIFIED[game][1]['ordinary_validity'][0]
            payload = bytearray(_read(original, entry, length))
            struct.pack_into('>I', payload, site - entry, branch(site, BASE))
            targets = set()
            for offset in range(0, len(payload), 4):
                word = int.from_bytes(payload[offset:offset + 4], 'big')
                if word & 0xFC000003 == 0x48000001:
                    delta = word & 0x3FFFFFC
                    delta -= 0x4000000 if delta & 0x2000000 else 0
                    targets.add(entry + offset + delta)
            self.assertEqual(len(targets), 1)
            class SlotMachine(EffectMachine):
                native_targets = targets
                def native(self, target):
                    self.calls.append((target, self.reg[3], self.reg[4]))
                    self.reg[3] = selected_move
            for pokemon in (0, SPECIES):
                for selected_move in (0, 1, 354, *range(355, 382), 382, 65535):
                    machine = SlotMachine(bytes(payload), entry)
                    add_code(machine, _ordinary_validity(BASE, site + 12), BASE)
                    machine.reg[3:5] = [pokemon, 2]
                    before, lr, sp = machine.reg.copy(), machine.lr, machine.reg[1]
                    machine.run()
                    self.assertEqual(machine.reg[3], int(bool(pokemon and selected_move)
                        and (selected_move < 355 or selected_move in MOVE_IDS)), (game, selected_move))
                    self.assertEqual(len(machine.calls), 0 if not pokemon else 1 if not selected_move else 2)
                    self.assertTrue(all(call[1:] == (pokemon, 2) for call in machine.calls))
                    self.assertEqual(machine.reg[14:], before[14:])
                    self.assertEqual((machine.lr, machine.reg[1]), (lr, sp))

    def test_private_message_banks_compose_before_getters_without_losing_prior_arena(self):
        from orre_randomizer.fairy_messages import install_fairy_messages, ITEM_MESSAGE_IDS, MOVE_NAME_IDS, MOVE_DESCRIPTION_IDS
        from orre_randomizer.fairy_gameplay import content_from_rows, fairy_gameplay_context, _layouts
        from orre_randomizer.fairy_integration import apply_tm_gameplay
        from orre_randomizer.options import Options
        from dataclasses import replace
        for game, path in PATHS.items():
            with self.subTest(game=game):
                xd = game.startswith('GXX'); region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
                rp = ROOT / (f'build/xd-validation/{region}/common_rel' if xd else
                    f'build/region-compat-2026-11-02/rel-research/{ {"eu":"pal", "us":"usa", "jp":"japan"}[region] }/common.fsys-common_rel.rel')
                if not rp.is_file(): self.skipTest('requires private regional RELs')
                rel, original = rp.read_bytes(), path.read_bytes()
                candidate = prepare_candidate_moves(rel, game,
                    move_message_ids={move: (MOVE_NAME_IDS[move], MOVE_DESCRIPTION_IDS[move]) for move in MOVE_IDS})
                content = content_from_rows(game, candidate['move_rows'], original_rel=rel, original_dol=original)
                with fairy_gameplay_context(content):
                    current_rel, _, tms = apply_tm_gameplay(rel, content.baseline_rel, original, original,
                        'integrated-tms', replace(Options.none(), randomize_tm_moves=True), game,
                        species_table=_layouts(rel, game)['species'])
                with_messages, message_report = install_fairy_messages(original, original, game)
                output, out_rel, report = install_additional_tms(original, with_messages, game,
                    move_rows=candidate['move_rows'], compatibility=tms['extra_compatibility'],
                    item_message_ids=ITEM_MESSAGE_IDS, tm_plan=tms['tm_plan'],
                    message_refresh_address=message_report['refresh_address'],
                    **(dict(original_rel=rel, current_rel=current_rel) if xd else {}))
                previous = next(row for row in parse_dol(with_messages)['sections'] if row['name'] == 'text2')
                start, stop = previous['offset'] + 32, previous['offset'] + previous['size']
                self.assertEqual(output[start:stop], with_messages[start:stop])
                snapshot = read_installed_content(output, report)
                self.assertEqual(len(snapshot['tms']), 57)
                self.assertEqual([row['move'] for row in snapshot['tms']], tms['tm_moves'])
                self.assertEqual(len(report['hooks']), 11 if xd else 10)
                with self.assertRaises(FormatError):
                    install_additional_tms(original, original, game, move_rows=candidate['move_rows'],
                        compatibility={}, item_message_ids=ITEM_MESSAGE_IDS,
                        message_refresh_address=0x80100000,
                        **(dict(original_rel=rel, current_rel=rel) if xd else {}))

    def test_candidate_rows_are_real_new_moves_with_modern_fields_and_explicit_remaining_contracts(self):
        from orre_randomizer.fairy_data import move_definition
        from orre_randomizer.engine.inspect_tables import rel_symbols
        from orre_randomizer.engine.analyze_game import parse_rel
        for game in PATHS:
            xd = game.startswith('GXX')
            region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
            path = ROOT / (f'build/xd-validation/{region}/common_rel' if xd else
                f'build/region-compat-2026-11-02/rel-research/{ {"eu":"pal", "us":"usa", "jp":"japan"}[region] }/common.fsys-common_rel.rel')
            if not path.is_file(): self.skipTest('requires six private common RELs')
            with self.subTest(game=game):
                rel = path.read_bytes()
                messages = {move: (0xF0440 + i * 2, 0xF0441 + i * 2) for i, move in enumerate(MOVE_IDS)}
                result = prepare_candidate_moves(rel, game, move_message_ids=messages)
                self.assertFalse(result['qualified'])
                self.assertTrue(result['original_native_moves_untouched'])
                self.assertTrue(result['requires_user_animation_choice'])
                self.assertEqual(result['native_effect_ids'], dict(zip(CANONICAL_MOVES, (17, 3, 68, 0, 71, 0, 18))))
                symbols = rel_symbols(rel, parse_rel(rel)); start = symbols[124 if xd else 62]['offset']
                for canonical, move in zip(CANONICAL_MOVES, MOVE_IDS):
                    definition = move_definition(canonical); row = result['move_rows'][move]
                    self.assertEqual(row[0], definition['priority'])
                    self.assertEqual(row[1], definition['pp']); self.assertEqual(row[2], 19)
                    self.assertEqual(row[3], 4 if definition['target'] == 'all-opponents' else 0)
                    self.assertEqual(row[4], definition['accuracy'] or 0)
                    self.assertEqual(row[5], definition['effect_chance'] or 0)
                    self.assertEqual(row[25 if xd else 23], definition['power'] or 0)
                    for flag, field in (('contact', 6), ('protect', 7), ('reflectable', 8),
                                        ('snatch', 9), ('mirror', 10), ('sound', 16)):
                        self.assertEqual(row[field], int(flag in definition['flags']))
                    self.assertEqual(row[18], 0)
                    self.assertEqual(row[0x16 if xd else 0x14], 0 if xd else 255)
                    self.assertEqual(row[0x17 if xd else 0x15], 0)
                    self.assertEqual(struct.unpack_from('>I', row, 32)[0], messages[move][0])
                    self.assertEqual(struct.unpack_from('>I', row, 44)[0], messages[move][1])
                    contract = next(r for r in result['contracts'] if r['move_id'] == move)
                    donor = rel[start + contract['effect_donor'] * 56:start + (contract['effect_donor'] + 1) * 56]
                    self.assertEqual(row[28 if xd else 26:30 if xd else 28], donor[28 if xd else 26:30 if xd else 28])
                self.assertIn('sound-move-substitute-bypass', result['contracts'][0]['pending'])
                self.assertIn('drain-75-percent-and-liquid-ooze', result['contracts'][1]['pending'])
                alternative = prepare_candidate_moves(rel, game, move_message_ids=messages,
                    animation_donors={canonical: 33 for canonical in CANONICAL_MOVES})
                for move in MOVE_IDS:
                    permitted = {*(range(30, 32) if xd else range(28, 30)), 50, 51}
                    self.assertTrue(all(a == b or i in permitted for i, (a, b) in enumerate(
                        zip(result['move_rows'][move], alternative['move_rows'][move]))))
                self.assertEqual(path.read_bytes(), rel)

    def test_all_six_complete_tm_plans_reach_native_rewards_without_changing_hms(self):
        from orre_randomizer.fairy_tms import _item_locations
        from orre_randomizer.engine.dol_regions import dol_layout
        from orre_randomizer.xd_species_gameplay import TM_OFFSETS
        for game, path in PATHS.items():
            with self.subTest(game=game):
                original = path.read_bytes(); xd = game.startswith('GXX')
                region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
                rp = ROOT / f'build/xd-validation/{region}/common_rel'
                if xd and not rp.is_file(): self.skipTest('requires private XD common RELs')
                rel = rp.read_bytes() if xd else None
                names = {item: (0xF0400 + i * 2, 0xF0401 + i * 2) for i, item in enumerate(ITEM_IDS)}
                plan = plan_tms('fairy-a', extra_description_ids={move: names[item][1]
                    for item, move in zip(ITEM_IDS, MOVE_IDS)}, shuffle=True)
                original_columns = tuple(i % 2 for i in range(50))
                columns = permute_compatibility(original_columns, (1, 0, 1, 0, 1, 0, 1), plan)
                output, changed_rel, report = install_additional_tms(original, original, game,
                    move_rows=move_rows(), compatibility={386: columns[50:]}, item_message_ids=names,
                    tm_plan=plan, **(dict(original_rel=rel, current_rel=rel) if xd else {}))
                native_tm = TM_OFFSETS[game] if xd else dol_layout(original).tm_table_offset
                self.assertEqual(output[native_tm + 400:native_tm + 464], original[native_tm + 400:native_tm + 464])
                items, _, _ = _item_locations(original, rel, game)
                before, after = (rel, changed_rel) if xd else (original, output)
                for i, row in enumerate(plan['mapping'][:50]):
                    self.assertEqual(output[native_tm + i * 8:native_tm + i * 8 + 6], original[native_tm + i * 8:native_tm + i * 8 + 6])
                    self.assertEqual(struct.unpack_from('>H', output, native_tm + i * 8 + 6)[0], row['after_move'])
                    self.assertEqual(struct.unpack_from('>I', after, items + row['item_index'] * 40 + 20)[0], row['after_description_id'])
                    self.assertEqual(after[items + row['item_index'] * 40:items + row['item_index'] * 40 + 20], before[items + row['item_index'] * 40:items + row['item_index'] * 40 + 20])
                    self.assertEqual(after[items + row['item_index'] * 40 + 24:items + (row['item_index'] + 1) * 40], before[items + row['item_index'] * 40 + 24:items + (row['item_index'] + 1) * 40])
                for row in plan['mapping'][50:]:
                    self.assertEqual(struct.unpack_from('>I', after, items + row['item_index'] * 40 + 20)[0], row['after_description_id'])
                    self.assertEqual(report['acquisition_catalog'][row['item_index']]['move'], row['after_move'])
                snapshot = read_installed_content(output, report)
                self.assertEqual([row['move'] for row in snapshot['tms']], [row['after_move'] for row in plan['mapping']])
                self.assertEqual(snapshot['compatibility'][386], tuple(bool(v) for v in columns[50:]))
                self.assertFalse(report['native_tm_hm_rows_preserved'])
                self.assertTrue(report['native_hm_rows_preserved'])
                bad = copy.deepcopy(plan); bad['mapping'][0]['before_description_id'] += 999
                # Update dependent pair so the plan is internally paired but not a retail layout.
                for row in bad['mapping']:
                    if row['source_tm'] == 1: row['after_description_id'] += 999
                with self.assertRaises(FormatError):
                    install_additional_tms(original, original, game, move_rows=move_rows(), compatibility={},
                        item_message_ids=names, tm_plan=bad,
                        **(dict(original_rel=rel, current_rel=rel) if xd else {}))

    def test_all_six_originals_receive_only_owned_getter_and_placeholder_edits(self):
        from orre_randomizer.engine.inspect_tables import rel_symbols
        from orre_randomizer.engine.analyze_game import parse_rel
        from orre_randomizer.engine.tm_rules import ORIGINAL_TM_MOVES, ORIGINAL_HM_MOVES
        from orre_randomizer.fairy_tms import _item_locations
        for game, path in PATHS.items():
            with self.subTest(game=game):
                original = path.read_bytes(); xd = game.startswith('GXX')
                region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
                rp = ROOT / f'build/xd-validation/{region}/common_rel'
                if xd and not rp.is_file(): self.skipTest('requires private XD common RELs')
                rel = rp.read_bytes() if xd else None
                kwargs = dict(original_rel=rel, current_rel=rel) if xd else {}
                names = {item: (0xF0400 + i * 2, 0xF0401 + i * 2) for i, item in enumerate(ITEM_IDS)}
                output, changed_rel, report = install_additional_tms(original, original, game,
                    move_rows=move_rows(), compatibility={386: [1] * 7}, item_message_ids=names, **kwargs)
                items, mapping, _ = _item_locations(original, rel, game)
                source, changed = (rel, changed_rel) if xd else (original, output)
                self.assertEqual(source[items + 289 * 40:items + 347 * 40], changed[items + 289 * 40:items + 347 * 40])
                self.assertEqual(source[items + 277 * 40:items + 278 * 40], changed[items + 277 * 40:items + 278 * 40])
                for i, tm in enumerate(ADDITIONAL_TMS):
                    row = changed[items + tm.item_id * 40:items + (tm.item_id + 1) * 40]
                    self.assertEqual(row[:4], bytes((4, 1, 0, 1)))
                    self.assertEqual(row[0x1B], tm.machine_index)
                    self.assertEqual(struct.unpack_from('>H', changed, mapping + 2 * tm.item_id)[0], tm.item_id)
                    self.assertEqual(struct.unpack_from('>II', row, 16), names[tm.item_id])
                allowed = set(range(8, 12)) | set(range(0x50, 0x54)) | set(range(0x98, 0x9C))
                section = next(row for row in parse_dol(output)['sections'] if row['name'] == 'text2')
                self.assertEqual(section['offset'] + section['size'], len(output))
                from orre_randomizer.castform_portraits import _reservation
                _, _, setter, _, _ = _reservation(original, original, game)
                allowed.update(range(_offset(original, setter), _offset(original, setter) + 4))
                for hook in report['hooks']:
                    start = _offset(original, hook['address']); allowed.update(range(start, start + 4))
                if not xd:
                    for tm in ADDITIONAL_TMS:
                        allowed.update(range(items + tm.item_id * 40, items + (tm.item_id + 1) * 40))
                        allowed.update(range(mapping + tm.item_id * 2, mapping + tm.item_id * 2 + 2))
                self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(original, output))))
                if xd:
                    from orre_randomizer.deoxys_meteorite import _callback_relocation
                    rel_allowed = set()
                    for tm in ADDITIONAL_TMS:
                        rel_allowed.update(range(items + tm.item_id * 40, items + (tm.item_id + 1) * 40))
                        rel_allowed.update(range(mapping + tm.item_id * 2, mapping + tm.item_id * 2 + 2))
                        relocation = _callback_relocation(rel, items + tm.item_id * 40, game)
                        rel_allowed.update(range(relocation + 4, relocation + 8))
                    self.assertEqual(len(changed_rel), len(rel))
                    self.assertTrue(all(a == b or i in rel_allowed for i, (a, b) in enumerate(zip(rel, changed_rel))))
                if xd:
                    address, length, _ = _QUALIFIED[game][1]['shadow_classifier']
                    code = _read(original, address, length)
                    for added in MOVE_IDS:
                        machine = ItemMachine(code, BASE); machine.reg[3] = added
                        machine.run()
                        self.assertEqual(machine.reg[3], 0)
                snapshot = read_installed_content(output, report)
                self.assertEqual(snapshot['moves'], move_rows())
                self.assertEqual(snapshot['tm_moves'], list(MOVE_IDS))
                self.assertEqual(snapshot['compatibility'][386], (True,) * 7)
                broken = bytearray(output)
                broken[_offset(output, report['compatibility_table']) + 7] ^= 1
                with self.assertRaises(FormatError): read_installed_content(bytes(broken), report)
                missing = dict(report); missing['hooks'] = report['hooks'][:-1]
                with self.assertRaises(FormatError): read_installed_content(output, missing)
                self.assertTrue(report['save_format_unchanged'])
                self.assertEqual(len(report['hooks']), 9 if xd else 8)
                self.assertEqual(path.read_bytes(), original)
                if xd: self.assertEqual(rp.read_bytes(), rel)
                with self.assertRaises(FormatError):
                    install_additional_tms(original, output, game, move_rows=move_rows(),
                        compatibility={}, item_message_ids=names,
                        **(dict(original_rel=rel, current_rel=changed_rel) if xd else {}))


if __name__ == '__main__':
    unittest.main()
