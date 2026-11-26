from __future__ import annotations

import hashlib
from itertools import product
import struct
import unittest
from pathlib import Path

from orre_randomizer.deoxys_meteorite import (
    ITEM_ID, LANGUAGES, MESSAGE_IDS, METEORITE_TEXT, _QUALIFIED,
    _action_filter, _bank, _bank_refresh, _callback_relocation,
    _field_callback, _grant, install_meteorite,
)
from orre_randomizer.deoxys_identity import FORM_TAG, RECORD_SIZES, form_offset
from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.xd_item_rules import _table_offsets
from tests.test_shiny_rules import Machine, MASK


class ItemMachine(Machine):
    """Small PowerPC contract runner; native UI/stat/inventory calls are doubles."""
    def run(self, stop=None):
        stop = self.lr if stop is None else stop
        for _ in range(10000):
            if self.pc == stop:
                return
            w = self.code[self.pc]; pc = self.pc; self.pc += 4
            op = w >> 26; rs = w >> 21 & 31; ra = w >> 16 & 31; rb = w >> 11 & 31
            imm = w & 0xFFFF; signed = imm - 0x10000 if imm & 0x8000 else imm
            xo = w >> 1 & 1023
            if w == 0x7C0802A6: self.reg[0] = self.lr
            elif w == 0x7C0803A6: self.lr = self.reg[0]
            elif w == 0x4E800020: self.pc = self.lr
            elif op in (14, 15): self.reg[rs] = ((self.reg[ra] if ra else 0) + (signed << (16 if op == 15 else 0))) & MASK
            elif op == 7: self.reg[rs] = self.reg[ra] * signed & MASK
            elif op == 24: self.reg[ra] = self.reg[rs] | imm
            elif op == 28:
                self.reg[ra] = self.reg[rs] & imm
                self.cr = (False, self.reg[ra] == 0)
            elif op in (32, 40): self.reg[rs] = self.read((self.reg[ra] + signed) & MASK, 2 if op == 40 else 4)
            elif op == 34: self.reg[rs] = self.read((self.reg[ra] + signed) & MASK, 1)
            elif op in (36, 37, 44):
                address = (self.reg[ra] + signed) & MASK
                self.write(address, self.reg[rs], 2 if op == 44 else 4)
                if op == 37: self.reg[ra] = address
            elif op in (46, 47):
                address = (self.reg[ra] + signed) & MASK
                for i in range(rs, 32):
                    if op == 46: self.reg[i] = self.read(address + (i - rs) * 4)
                    else: self.write(address + (i - rs) * 4, self.reg[i])
            elif op in (10, 11):
                left = self.reg[ra]
                if op == 11 and left & 0x80000000: left -= 0x100000000
                self.cr = (left < (imm if op == 10 else signed), left == (imm if op == 10 else signed))
            elif op == 31 and xo == 32: self.cr = (self.reg[ra] < self.reg[rb], self.reg[ra] == self.reg[rb])
            elif op == 31 and xo == 0:
                left, right = (value - (0x100000000 if value & 0x80000000 else 0) for value in (self.reg[ra], self.reg[rb]))
                self.cr = (left < right, left == right)
            elif op == 31 and xo == 40: self.reg[rs] = self.reg[rb] - self.reg[ra] & MASK
            elif op == 31 and xo == 444: self.reg[ra] = self.reg[rs] | self.reg[rb]
            elif op == 31 and xo == 266: self.reg[rs] = self.reg[ra] + self.reg[rb] & MASK
            elif op == 31 and xo == 23: self.reg[rs] = self.read((self.reg[ra] + self.reg[rb]) & MASK)
            elif op == 31 and xo == 279: self.reg[rs] = self.read((self.reg[ra] + self.reg[rb]) & MASK, 2)
            elif op == 31 and xo == 954:
                self.reg[ra] = ((self.reg[rs] & 255) - (256 if self.reg[rs] & 128 else 0)) & MASK
            elif op == 21:
                shift = w >> 11 & 31; mb = w >> 6 & 31; me = w >> 1 & 31
                mask = sum(1 << (31 - i) for i in range(32) if (mb <= i <= me if mb <= me else i >= mb or i <= me))
                value = self.reg[rs]
                self.reg[ra] = ((value << shift | value >> (32 - shift) if shift else value) & MASK) & mask
                if w & 1: self.cr = (bool(self.reg[ra] & 0x80000000), self.reg[ra] == 0)
            elif op == 16:
                bo, bi = w >> 21 & 31, w >> 16 & 31
                condition = self.cr[0] if bi == 0 else self.cr[1] if bi == 2 else not any(self.cr)
                if (bo == 12 and condition) or (bo == 4 and not condition): self.pc = pc + (signed & ~3)
            elif op == 18:
                displacement = w & 0x3FFFFFC
                if displacement & 0x2000000: displacement -= 0x4000000
                target = pc + displacement
                if w & 1: self.lr = pc + 4
                if target in getattr(self, 'native_targets', ()):
                    self.native(target); self.pc = self.lr
                else: self.pc = target
            else: raise AssertionError(f'Unsupported {w:08x} at {pc:08x}')
        raise AssertionError('Meteorite callback did not terminate')


ADDRESS, POKEMON, OUT, CHOICES = 0x81500020, 0x80610000, 0x80620000, 0x81510000
FUNCTIONS = {name: 0x80100000 + i * 0x100 for i, name in enumerate(
    ('party_open', 'party_get', 'party_close', 'choice', 'recalculate', 'message',
     'message_close', 'have', 'can_add', 'add', 'bank_open', 'bank_close', 'language'))}


class CallbackMachine(ItemMachine):
    def __init__(self, data, game_id, *, slot=2, form=3, hp=37, maximum=100):
        super().__init__(data, ADDRESS)
        self.game_id, self.slot, self.form = game_id, slot, form
        self.current_hp = 0x8A if game_id.startswith('GC6') else 4
        self.maximum_hp = 0x8C if game_id.startswith('GC6') else 0x90
        self.maximum = maximum
        self.native_targets = set(FUNCTIONS.values())
        self.reg[3:5] = [ITEM_ID, OUT]
        self.write(OUT, 999)
        self.raw = bytearray((i * 7 + 3) & 255 for i in range(RECORD_SIZES['colosseum' if game_id.startswith('GC6') else 'xd']))
        struct.pack_into('>H', self.raw, 0, 410)
        struct.pack_into('>H', self.raw, form_offset(game_id), 0)
        struct.pack_into('>H', self.raw, self.current_hp, hp)
        for i, byte in enumerate(self.raw): self.write(POKEMON + i, byte, 1)

    def native(self, target):
        args = self.reg[3:9].copy()
        self.calls.append((target, args))
        if target == FUNCTIONS['party_open']: result = self.slot
        elif target == FUNCTIONS['party_get']:
            self.write(args[1], POKEMON); self.write(args[2], 0); result = 0
        elif target == FUNCTIONS['choice']: result = self.form
        elif target == FUNCTIONS['recalculate']:
            self.write(POKEMON + self.maximum_hp, self.maximum, 2)
            # Deliberately heal in the double to prove callback undoes healing.
            self.write(POKEMON + self.current_hp, self.maximum, 2)
            result = 0
        else: result = 0
        for i in (0, *range(3, 13)): self.reg[i] = 0xDEAD0000 + i
        self.reg[3] = result & MASK


class MeteoriteContractTests(unittest.TestCase):
    def test_native_banks_are_sorted_utf16_and_cover_six_languages(self):
        for language in LANGUAGES:
            bank = _bank(language, MESSAGE_IDS)
            self.assertEqual(struct.unpack_from('>H', bank, 4)[0], 8)
            self.assertEqual(bank[3], 0 if language == 'ja' else 1)
            found = {}
            for index in range(8):
                key, offset = struct.unpack_from('>II', bank, 16 + index * 8)
                end, text = offset, []
                while bank[end:end + 2] != bytes(2):
                    if bank[end:end + 3] == b'\xff\xff\x00':
                        text.append('\n')
                        end += 3
                    else:
                        text.append(bank[end:end + 2].decode('utf-16-be'))
                        end += 2
                found[key] = ''.join(text)
            self.assertEqual(found, {MESSAGE_IDS[k]: v for k, v in METEORITE_TEXT[language].items()})
        self.assertEqual(METEORITE_TEXT['fr']['name'], 'MÉTÉORITE')
        for language in LANGUAGES:
            self.assertEqual(len(METEORITE_TEXT[language]['description'].split('\n')), 2)
            self.assertNotIn(b'\x00\x0a', _bank(language, MESSAGE_IDS))

    def test_native_banks_match_retail_uppercase_names_without_changing_application_labels(self):
        from orre_randomizer.deoxys import FORM_ORDER, form_label
        names = {'en': 'METEORITE', 'fr': 'MÉTÉORITE', 'de': 'METEORIT',
                 'es': 'METEORITO', 'it': 'METEORITE', 'ja': 'いんせき'}
        for language in LANGUAGES:
            text = METEORITE_TEXT[language]
            self.assertEqual(text['name'], names[language])
            for form in FORM_ORDER:
                self.assertEqual(text[form], form_label(form, language).upper())
            if language != 'ja':
                for key in ('description', 'no_effect', 'changed'):
                    self.assertIn('DEOXYS', text[key])
                    self.assertNotIn('Deoxys', text[key])
                    self.assertNotEqual(text[key], text[key].upper())
        self.assertEqual(form_label('normal', 'en'), 'Normal Forme')
        self.assertEqual(form_label('defense', 'fr'), 'Forme Défense')

    def test_change_all_forms_both_games_preserves_native_identity_and_hp(self):
        for game in ('GC6P01', 'GXXP01'):
            code = _field_callback(ADDRESS, FUNCTIONS, MESSAGE_IDS, CHOICES, game)
            for form in range(4):
                for old_hp, maximum in ((37, 100), (0, 100), (150, 90)):
                    machine = CallbackMachine(code, game, form=form, hp=old_hp, maximum=maximum)
                    before, lr = machine.reg.copy(), machine.lr
                    expected = machine.raw.copy()
                    struct.pack_into('>H', expected, form_offset(game), FORM_TAG | form)
                    struct.pack_into('>H', expected, machine.current_hp, min(old_hp, maximum))
                    struct.pack_into('>H', expected, machine.maximum_hp, maximum)
                    machine.run()
                    actual = bytes(machine.mem[POKEMON + i] for i in range(len(expected)))
                    self.assertEqual(actual, expected)
                    self.assertEqual(machine.read(OUT), 0)
                    self.assertEqual(machine.reg[3], 0)
                    self.assertEqual(machine.reg[1:3], before[1:3])
                    self.assertEqual(machine.reg[13:], before[13:])
                    self.assertEqual(machine.lr, lr)
                    self.assertEqual([a for t, a in machine.calls if t == FUNCTIONS['choice']][0][:6],
                                     [1, CHOICES, 4, 0x70, 0x70, 0])

    def test_cancel_invalid_species_and_foreign_reserved_field_do_not_modify_record(self):
        for slot, form, species, tag in ((-1, 2, 410, 0), (2, -1, 410, 0),
                (2, 4, 410, 0), (2, 1, 25, 0), (2, 1, 410, 0x1234)):
            code = _field_callback(ADDRESS, FUNCTIONS, MESSAGE_IDS, CHOICES, 'GXXP01')
            machine = CallbackMachine(code, 'GXXP01', slot=slot, form=form)
            machine.write(POKEMON, species, 2)
            machine.write(POKEMON + form_offset('xd'), tag, 2)
            before = bytes(machine.mem[POKEMON + i] for i in range(len(machine.raw)))
            machine.run()
            self.assertEqual(bytes(machine.mem[POKEMON + i] for i in range(len(before))), before)
            self.assertEqual(machine.read(OUT), 0)
            self.assertEqual(machine.reg[3], 1)
            self.assertFalse(any(t == FUNCTIONS['recalculate'] for t, _ in machine.calls))

    def test_grant_checks_capacity_and_never_overwrites_full_bag(self):
        for has_item, capacity, expected_adds in ((True, 0, 0), (False, -1, 0), (False, 0, 0), (False, 1, 1), (False, 99, 1)):
            machine = ItemMachine(_grant(ADDRESS, FUNCTIONS), ADDRESS)
            machine.reg[3] = POKEMON
            machine.native_targets = set(FUNCTIONS.values())
            def native(target):
                args = machine.reg[3:9].copy(); machine.calls.append((target, args))
                machine.reg[3] = (int(has_item) if target == FUNCTIONS['have'] else capacity) & MASK
            machine.native = native
            machine.run()
            adds = [args for target, args in machine.calls if target == FUNCTIONS['add']]
            self.assertEqual(len(adds), expected_adds)
            if adds: self.assertEqual(adds[0][:4], [POKEMON, ITEM_ID, 1, MASK])

    def test_implicit_current_player_zero_is_passed_to_native_inventory_apis(self):
        machine = ItemMachine(_grant(ADDRESS, FUNCTIONS), ADDRESS)
        machine.reg[3] = 0
        machine.native_targets = set(FUNCTIONS.values())
        def native(target):
            machine.calls.append((target, machine.reg[3:9].copy()))
            machine.reg[3] = 0 if target == FUNCTIONS['have'] else 99
        machine.native = native
        machine.run()
        self.assertEqual([args[:2] for target, args in machine.calls], [[0, ITEM_ID]] * 3)

    def test_colosseum_item_filter_keeps_use_and_cancel_and_other_items_intact(self):
        continuation, use = 0x80010000, 0x80013F80
        code = _action_filter(ADDRESS, continuation, 0xBB210014, use)
        rows = [(1, use, 0), (2, 0x80013A18, 0), (3, 0x80013DFC, 0), (4, 0, 0)]
        for item in (ITEM_ID, 1):
            machine = ItemMachine(code, ADDRESS)
            original_stack = machine.reg[1]
            for reg in range(25, 32): machine.write(original_stack + 0x14 + (reg - 25) * 4, machine.reg[reg])
            machine.reg[3], machine.reg[28], machine.reg[29] = len(rows), item, OUT + 12 * len(rows)
            for index, row in enumerate(rows):
                for col, value in enumerate(row): machine.write(OUT + index * 12 + col * 4, value)
            machine.run(stop=continuation)
            expected = [rows[0], rows[-1]] if item == ITEM_ID else rows
            self.assertEqual(machine.reg[3], len(expected))
            self.assertEqual([tuple(machine.read(OUT + i * 12 + col * 4) for col in range(3))
                              for i in range(len(expected))], expected)

    def test_bank_refresh_closes_only_owned_banks_and_uses_native_language_enum(self):
        banks = {language: 0x81600000 + i * 0x1000 for i, language in enumerate(LANGUAGES)}
        for selected in range(1, 7):
            machine = ItemMachine(_bank_refresh(ADDRESS, FUNCTIONS, banks, 'GXXP01'), ADDRESS)
            machine.native_targets = set(FUNCTIONS.values())
            def native(target):
                machine.calls.append((target, machine.reg[3:9].copy()))
                machine.reg[3] = selected if target == FUNCTIONS['language'] else 0
            machine.native = native
            machine.run()
            self.assertEqual([args[0] for target, args in machine.calls if target == FUNCTIONS['bank_close']], list(banks.values()))
            self.assertEqual([args[0] for target, args in machine.calls if target == FUNCTIONS['bank_open']], [banks[LANGUAGES[selected - 1]]])

    def test_xd_item_filter_only_changes_meteorite_field_actions_in_all_regions(self):
        continuation, table, context = 0x80010000, 0x80700000, 0x80710000
        # The emitted filter accepts a qualified lwz r3,SDA(r13) instruction.
        # Exercise signed displacement boundaries without private retail files;
        # MeteoriteRetailQualifications separately verifies original getters.
        for letter, displacement in product('PEJ', (-32768, -4, 0, 4, 32764)):
            game = f'GXX{letter}01'
            functions = _QUALIFIED[game][1]
            use = functions['use'][0]
            load = 0x806D0000 | (displacement & 0xFFFF)
            code = _action_filter(ADDRESS, continuation, 0xBB210014, use,
                                  xd_context=context, item_table_load=load)
            rows = [(1, use, 0), (2, use + 0x100, 0), (3, use + 0x200, 0), (4, 0, 0)]
            for item, mode in [(ITEM_ID, 0), (1, 0), (ITEM_ID, 1)]:
                machine = ItemMachine(code, ADDRESS)
                stack = machine.reg[1]
                for reg in range(25, 32): machine.write(stack + 0x14 + (reg - 25) * 4, machine.reg[reg])
                machine.reg[3], machine.reg[27], machine.reg[31] = len(rows), OUT + 12 * len(rows), table + item * 40
                machine.reg[13] = 0x80800000
                machine.write(context + 4, mode)
                offset = load & 65535
                machine.write(machine.reg[13] + offset - (65536 if offset & 32768 else 0), table)
                for index, row in enumerate(rows):
                    for column, value in enumerate(row): machine.write(OUT + index * 12 + column * 4, value)
                original_lr = machine.lr
                machine.run(stop=continuation)
                expected = [rows[0], rows[-1]] if item == ITEM_ID and mode == 0 else rows
                self.assertEqual(machine.reg[3], len(expected))
                self.assertEqual([tuple(machine.read(OUT + i * 12 + column * 4) for column in range(3))
                                  for i in range(len(expected))], expected)
                self.assertEqual(machine.reg[1], stack)
                self.assertEqual(machine.lr, original_lr)


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / 'build/xd-validation/jp/common_rel').is_file(), 'requires private retail validation inputs')
class MeteoriteRetailQualifications(unittest.TestCase):
    def test_original_native_item_getters_resolve_new_id_in_all_six_regions(self):
        from orre_randomizer.deoxys_meteorite import _read, _offset
        from orre_randomizer.engine.inspect_tables import rel_symbols
        from orre_randomizer.engine.analyze_game import parse_rel
        addresses = {'GC6P01': 0x80148414, 'GC6E01': 0x801440A0, 'GC6J01': 0x80141178,
                     'GXXP01': 0x801603E4, 'GXXE01': 0x8015EB34, 'GXXJ01': 0x8015A1A0}
        for game, address in addresses.items():
            xd = game.startswith('GXX')
            region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
            path = ROOT / (f'build/xd-validation/{region}/main.dol' if xd else f'build/hd-completion/hud/{game}.dol')
            original = path.read_bytes(); kwargs = {}
            if xd:
                original_rel = (ROOT / f'build/xd-validation/{region}/common_rel').read_bytes()
                kwargs = dict(original_rel=original_rel, current_rel=original_rel)
            patched, patched_rel, report = install_meteorite(original, original, game, **kwargs)
            for changed in (False, True):
                dol = patched if changed else original
                common = patched_rel if changed else (original_rel if xd else b'')
                class NativeGetterMachine(ItemMachine):
                    def read(self, at, n=4):
                        return int.from_bytes(bytes(self.mem[at + i] if at + i in self.mem
                            else common[at + i - 0x81000000] if xd and 0x81000000 <= at + i < 0x81000000 + len(common)
                            else _read(dol, at + i, 1)[0] for i in range(n)), 'big')
                machine = NativeGetterMachine(_read(original, address, 0x50), address)
                for at in range(0x100, 0x800, 4):
                    word = struct.unpack_from('>I', original, at)[0]
                    if word >> 16 == 0x3DA0:
                        machine.reg[13] = (word & 65535) << 16 | struct.unpack_from('>I', original, at + 4)[0] & 65535
                machine.reg[3] = ITEM_ID
                if xd:
                    symbols = rel_symbols(original_rel, parse_rel(original_rel))
                    # The original loader supplies pointers to symbols69/71/68/70.
                    for instruction_offset, symbol in ((0, 69), (0x1C, 71), (0x24, 68), (0x44, 70)):
                        word = struct.unpack('>I', _read(original, address + instruction_offset, 4))[0]
                        displacement = word & 65535
                        if displacement & 32768: displacement -= 65536
                        machine.write(machine.reg[13] + displacement, 0x81000000 + symbols[symbol]['offset'])
                    raw_table = 0x81000000 + symbols[70]['offset']
                else:
                    raw_table = next(s['ram_address'] + report['item_row'] - ITEM_ID * 40 - s['offset']
                        for s in parse_dol(original)['sections']
                        if s['offset'] <= report['item_row'] < s['offset'] + s['size'])
                machine.run()
                self.assertEqual(machine.reg[3], raw_table + (ITEM_ID * 40 if changed else 0))
                if changed:
                    self.assertEqual(machine.read(machine.reg[3], 3), 0x020101)
                    self.assertEqual(machine.read(machine.reg[3] + 16), MESSAGE_IDS['name'])

    def test_original_xd_field_hero_accessor_resolves_null_to_current_player(self):
        from orre_randomizer.deoxys_meteorite import _read
        original = (ROOT / 'build/xd-validation/us/main.dol').read_bytes()
        # Actual native heroGetStatus, including its zero-pointer branch/call.
        address, fallback, continuation = 0x8014D6E0, 0x8014D8C0, 0x8014D720
        machine = ItemMachine(_read(original, address, 0x44), address)
        machine.reg[3:6] = [0, 4, 0]
        machine.native_targets = {fallback}
        def native(target):
            self.assertEqual(target, fallback)
            machine.calls.append(target)
            machine.reg[3] = POKEMON
        machine.native = native
        machine.run(stop=continuation)
        self.assertEqual(machine.calls, [fallback])
        self.assertEqual(machine.reg[3], POKEMON)

    def test_original_native_capacity_routine_returns_quantity_zero_when_full(self):
        from orre_randomizer.deoxys_meteorite import _read
        original = (ROOT / 'build/hd-completion/hud/GC6E01.dol').read_bytes()
        address, getter = 0x80140588, 0x80142CF4
        code = _read(original, address, 0x514)
        # Exact20-slot census observed on the live six-Deoxys test card.
        inventory = [(537, 1), (68, 1), (14, 2), (15, 2), (16, 2), (18, 2), (17, 2),
                     (23, 3), (213, 1), (24, 1), (21, 3), (34, 3), (211, 1), (20, 1),
                     (65, 1), (64, 1), (66, 1), (70, 1), (181, 1), (214, 1)]
        from orre_randomizer.engine.dol_regions import dol_layout
        table = dol_layout(original).item_table_offset
        for free, expected in ((False, 0), (True, 99)):
            machine = ItemMachine(code, address)
            machine.reg[13] = 0x80480820
            machine.write(0x80478BD8, struct.unpack('>I', _read(original, 0x80478BD8, 4))[0])
            machine.reg[3:8] = [OUT, 20, ITEM_ID, 99, 1]
            for index, (item, quantity) in enumerate(inventory):
                if free and index == 14: item, quantity = 0, 0
                machine.write(OUT + index * 4, item, 2)
                machine.write(OUT + index * 4 + 2, quantity, 2)
            machine.native_targets = {getter}
            def native(target):
                pointer, item, selector, _ = machine.reg[3:7]
                if selector == 1:
                    native_index = item - 150 if item >= 500 else item
                    value = MESSAGE_IDS['name'] if item == ITEM_ID else struct.unpack_from('>I', original, table + native_index * 40 + 16)[0]
                elif selector in (0x1B, 0x1C):
                    value = machine.read(pointer + (2 if selector == 0x1C else 0), 2)
                else: raise AssertionError(selector)
                machine.reg[3] = value
            machine.native = native
            machine.run()
            self.assertEqual(machine.reg[3], expected)

    def test_actual_multilingual_native_bank_registration_and_lookup(self):
        from orre_randomizer.deoxys_meteorite import _read
        for game, path, lookup, lookup_size, mapper in (
                ('GC6P01', 'build/hd-completion/hud/GC6P01.dol', 0x800FDB5C, 0xE4, 0x800FF610),
                ('GXXE01', 'build/xd-validation/us/main.dol', 0x80107300, 0xD8, 0x8010B208)):
            original = (ROOT / path).read_bytes()
            fns = {k: v[0] for k, v in _QUALIFIED[game][1].items()}
            banks = {language: 0x81600000 + i * 0x1000 for i, language in enumerate(LANGUAGES)}
            code = _bank_refresh(ADDRESS, fns, banks, game)
            machine = ItemMachine(code, ADDRESS)
            for name in ('bank_open', 'bank_close'):
                address, size, _ = _QUALIFIED[game][1][name]
                data = _read(original, address, size)
                machine.code.update({address + i: struct.unpack_from('>I', data, i)[0] for i in range(0, len(data), 4)})
            for address, size in ((lookup, lookup_size), (mapper, 0x118)):
                data = _read(original, address, size)
                machine.code.update({address + i: struct.unpack_from('>I', data, i)[0] for i in range(0, len(data), 4)})
            for language, pointer in banks.items():
                for i, value in enumerate(_bank(language, MESSAGE_IDS)): machine.write(pointer + i, value, 1)
            # Native group system pointer: GSmsgOpen's first instruction is lwz r4,SDA(r13).
            first = struct.unpack('>I', _read(original, fns['bank_open'], 4))[0]
            self.assertEqual(first & 0xFFFF0000, 0x808D0000)
            displacement = first & 0xFFFF
            if displacement & 0x8000: displacement -= 0x10000
            system, foreign = 0x80630000, 0x81680000
            machine.write((machine.reg[13] + displacement) & MASK, system)
            groups_offset = 8 if game.startswith('GC6') else 4
            machine.write(system + groups_offset, foreign)
            for i in range(16): machine.write(foreign + i, 0, 1)
            selected = [1]
            machine.native_targets = {fns['language']}
            machine.native = lambda _target: machine.reg.__setitem__(3, selected[0])
            for index, language in enumerate(LANGUAGES, 1):
                selected[0] = index
                machine.pc, machine.lr = ADDRESS, 0x81234560
                machine.run()
                self.assertEqual(machine.read(system + groups_offset), foreign)
                self.assertEqual(machine.read(foreign + 8), banks[language])
                machine.pc, machine.lr = lookup, 0x81234560
                machine.reg[3] = MESSAGE_IDS['name']
                machine.run()
                raw = bytearray(); pointer = machine.reg[3]
                self.assertNotEqual(pointer, 0)
                for i in range(128):
                    value = machine.read(pointer + i * 2, 2)
                    if value == 0: break
                    raw.extend(value.to_bytes(2, 'big'))
                self.assertEqual(raw.decode('utf-16-be'), METEORITE_TEXT[language]['name'])

    def test_all_six_regions_keep_other_native_bytes_and_safe_callback_relocation(self):
        for family in ('colosseum', 'xd'):
            for letter, region in (('P', 'eu'), ('E', 'us'), ('J', 'jp')):
                game = ('GC6' if family == 'colosseum' else 'GXX') + letter + '01'
                path = ROOT / (f'build/hd-completion/hud/{game}.dol' if family == 'colosseum' else f'build/xd-validation/{region}/main.dol')
                original = path.read_bytes(); kwargs = {}
                if family == 'xd':
                    rel = (ROOT / f'build/xd-validation/{region}/common_rel').read_bytes()
                    kwargs = dict(original_rel=rel, current_rel=rel)
                dol, output_rel, report = install_meteorite(original, original, game, **kwargs)
                section = next(s for s in parse_dol(dol)['sections'] if s['name'] == 'text2')
                self.assertEqual(section['offset'] + section['size'], len(dol))
                allowed = set(range(8, 12)) | set(range(0x50, 0x54)) | set(range(0x98, 0x9C))
                # Existing arena setter and the exact reported hooks are the only native code changes.
                from orre_randomizer.castform_portraits import _reservation
                _, _, setter, _, _ = _reservation(original, original, game)
                from orre_randomizer.deoxys_meteorite import _offset
                for site in [setter, *(h['address'] for h in report['hooks'])]:
                    position = _offset(original, site); allowed.update(range(position, position + 4))
                if family == 'colosseum':
                    allowed.update(range(report['item_row'], report['item_row'] + 40))
                    allowed.update(range(report['item_conversion_offset'], report['item_conversion_offset'] + 2))
                self.assertTrue(all(x == y or i in allowed for i, (x, y) in enumerate(zip(original, dol))))
                if family == 'xd':
                    _, start = _table_offsets(rel); position = start + ITEM_ID * 40
                    relocation = _callback_relocation(rel, position, game)
                    edits = (set(range(position, position + 40)) | set(range(relocation + 4, relocation + 8))
                             | set(range(report['item_conversion_offset'], report['item_conversion_offset'] + 2)))
                    self.assertTrue(all(x == y or i in edits for i, (x, y) in enumerate(zip(rel, output_rel))))
                    self.assertEqual(struct.unpack_from('>I', output_rel, relocation + 4)[0], report['field_callback'])
                with self.assertRaises(FormatError): install_meteorite(original, dol, game, **kwargs)
