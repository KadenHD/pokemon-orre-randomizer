from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.fairy_runtime import (
    FAIRY_TYPE, FAIRY_NAME_ID, FAIRY_SPRITE, FAIRY_SMALL_SPRITE,
    LANGUAGES, TYPE_NAMES, DEFAULT_BADGE_RESOURCES, DEFAULT_SMALL_BADGE_RESOURCES,
    NATIVE_NEUTRAL, NATIVE_SUPER, NATIVE_RESIST, NATIVE_IMMUNE,
    _LAYOUTS, _descriptor, _descriptor_stub, _matchup_stub, _name_bank,
    _name_stub, _offset, _read, _resources, _value_stub, _move_category_stub,
    _direct_sprite_stub, _text_sprite_stub, _DIRECT_SPRITE_READS, _COLO_JP_NATIVE_SPRITES,
    fairy_effectiveness, install_fairy_type, install_colosseum_category_callers,
    install_move_category_callers, qualify_fairy_runtime,
)
from tests.test_deoxys_meteorite import ItemMachine, MASK

class FairyMachine(ItemMachine):
    """PowerPC contract runner including native byte stores used by type AI."""
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
            elif op in (36, 37, 38, 44):
                address = (self.reg[ra] + signed) & MASK
                self.write(address, self.reg[rs], 1 if op == 38 else 2 if op == 44 else 4)
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
        raise AssertionError('Fairy native contract did not terminate')


ADDRESS, CONTINUATION = 0x81600000, 0x80010004
DISPLACED = 0x800D0000  # lwz r0,0(r13), a synthetic replayable native prefix


def machine_for(code):
    machine = ItemMachine(code, ADDRESS)
    machine.reg[13] = 0x80800000
    machine.write(machine.reg[13], 0x1234)
    return machine


class FairyNativeContracts(unittest.TestCase):
    def test_japanese_direct_badge_load_intercepts_only_fairy_and_preserves_native_loads(self):
        for displaced, base_register in ((0x7CC3022E, 3), (0x7CC4022E, 4)):
            payload = _direct_sprite_stub(ADDRESS, CONTINUATION, displaced)
            for kind in range(24):
                machine = FairyMachine(payload, ADDRESS)
                machine.reg[:] = [0x81000000 + i * 0x100 for i in range(32)]
                machine.reg[0] = kind * 2
                pointer = machine.reg[base_register]
                machine.write(pointer + kind * 2, 0x2345 + kind, 2)
                before = list(machine.reg); sp, lr = machine.reg[1], machine.lr
                machine.run(stop=CONTINUATION)
                self.assertEqual(machine.reg[6], FAIRY_SPRITE if kind == 19 else 0x2345 + kind)
                self.assertEqual(machine.reg[:6] + machine.reg[7:], before[:6] + before[7:])
                self.assertEqual((machine.reg[1], machine.lr), (sp, lr))

    def test_japanese_name_bank_retains_each_games_qualified_native_font(self):
        self.assertEqual(_name_bank('ja', 'GC6J01')[3], 0)
        self.assertEqual(_name_bank('ja', 'GXXJ01')[3], 1)
        for language in LANGUAGES:
            self.assertEqual(struct.unpack_from('>4H',_name_bank(language,'GC6J01')),
                             (0,0,1,1))
        for game in ('GC6P01', 'GXXP01'):
            for language in LANGUAGES:
                self.assertEqual(_name_bank(language, game)[3],1)

    def test_every_pair_intercepts_only_fairy_and_retains_native_reserved_types(self):
        code = _matchup_stub(ADDRESS, CONTINUATION, DISPLACED)
        for attacker in (*range(23), 0x10013, 0xFFFFFFFF):
            for defender in (*range(23), 0x10013, 0xFFFFFFFF):
                machine = machine_for(code)
                machine.reg[3:5] = [attacker, defender]
                sp, lr = machine.reg[1], machine.lr
                expected = fairy_effectiveness(attacker, defender)
                machine.run(stop=CONTINUATION if expected is None else machine.lr)
                if expected is None:
                    self.assertEqual(machine.reg[3:5], [attacker, defender])
                    self.assertEqual(machine.reg[0], 0x1234)
                else:
                    self.assertEqual(machine.reg[3], expected, (attacker, defender))
                self.assertEqual((machine.reg[1], machine.lr), (sp, lr))
        self.assertEqual(fairy_effectiveness(19, 18), 0)
        self.assertEqual(fairy_effectiveness(18, 19), 0)
        self.assertIsNone(fairy_effectiveness(9, 16))
        self.assertIsNone(fairy_effectiveness(18, 9))

    def test_official_fairy_matchups_use_native_effect_codes(self):
        self.assertEqual([fairy_effectiveness(19, t) for t in (1, 16, 17)], [NATIVE_SUPER] * 3)
        self.assertEqual([fairy_effectiveness(19, t) for t in (3, 8, 10)], [NATIVE_RESIST] * 3)
        self.assertEqual([fairy_effectiveness(t, 19) for t in (3, 8)], [NATIVE_SUPER] * 2)
        self.assertEqual([fairy_effectiveness(t, 19) for t in (1, 6, 17)], [NATIVE_RESIST] * 3)
        self.assertEqual(fairy_effectiveness(16, 19), NATIVE_IMMUNE)
        self.assertEqual(fairy_effectiveness(19, 19), NATIVE_NEUTRAL)
        with self.assertRaises(ValueError):
            fairy_effectiveness(True, 19)

    def test_property_getters_retain_native_u16_narrowing_and_leaf_abi(self):
        for value in (2, FAIRY_SPRITE, FAIRY_SMALL_SPRITE):
            code = _value_stub(ADDRESS, CONTINUATION, DISPLACED, value)
            for kind in (9, 18, 19, 20, 0x10013, 0x10009, 0xFFFFFFFF):
                machine = machine_for(code)
                machine.reg[3] = kind
                fairy = kind & 0xFFFF == 19
                machine.run(stop=machine.lr if fairy else CONTINUATION)
                self.assertEqual(machine.reg[3], value if fairy else kind)
                if not fairy:
                    self.assertEqual(machine.reg[0], 0x1234)

    def test_name_bank_and_lazy_registration_cover_all_six_native_languages(self):
        refresh = ADDRESS + 0x1000
        code = _name_stub(ADDRESS, CONTINUATION, DISPLACED, refresh)
        for kind in (19, 0x10013, 9, 18):
            machine = machine_for(code)
            machine.reg[3] = kind
            sp, lr = machine.reg[1], machine.lr
            machine.native_targets = {refresh}
            machine.native = lambda target: machine.calls.append(target)
            fairy = kind & 0xFFFF == 19
            machine.run(stop=machine.lr if fairy else CONTINUATION)
            self.assertEqual(machine.calls, [refresh] if fairy else [])
            self.assertEqual(machine.reg[3], FAIRY_NAME_ID if fairy else kind)
            self.assertEqual((machine.reg[1], machine.lr), (sp, lr))
        for language in LANGUAGES:
            bank = _name_bank(language)
            self.assertEqual(struct.unpack_from(">H", bank, 4)[0], 1)
            self.assertEqual(struct.unpack_from(">II", bank, 16), (FAIRY_NAME_ID, 24))
            self.assertEqual(bank[24:24 + len(TYPE_NAMES[language].encode("utf-16-be"))].decode("utf-16-be"), TYPE_NAMES[language])
            self.assertEqual(len(bank) % 32, 0)

    def test_real_native_sprite_records_have_exact_crops_and_localized_resources(self):
        for game, length in (("GC6P01", 72), ("GC6E01", 24), ("GC6J01", 24),
                             ("GXXP01", 72), ("GXXE01", 72), ("GXXJ01", 24)):
            template = bytes.fromhex("9000000000ff0000" if length == 72 else "90000000000000ff") + bytes(length - 8)
            for small in (False, True) if game.startswith("GXX") else (False,):
                resources = DEFAULT_SMALL_BADGE_RESOURCES if small else DEFAULT_BADGE_RESOURCES
                record = _descriptor(template, resources, game, small=small)
                self.assertEqual(record[:8], template[:8])
                self.assertEqual(len(record), length)
                languages = LANGUAGES[:5] if length == 72 else ("ja" if game[3] == "J" else "en",)
                width, height = (21, 18) if small else (72, 18) if game.startswith("GXX") else (79, 27)
                for index, language in enumerate(languages):
                    self.assertEqual(struct.unpack_from(">HHHHI", record, 8 + index * 12), (0, 0, width, height, resources[language]))
                self.assertEqual(struct.unpack_from(">H", record, length - 4)[0], (FAIRY_SMALL_SPRITE if small else FAIRY_SPRITE) + 1)

    def test_descriptor_router_preserves_every_other_sprite_including_mystery(self):
        descriptors = {FAIRY_SPRITE: 0x81650000, FAIRY_SMALL_SPRITE: 0x81650080}
        code = _descriptor_stub(ADDRESS, CONTINUATION, DISPLACED, descriptors)
        for index in (0, 9, 18, 67, 74, 86, 93, 116, 123, 403, 414, FAIRY_SPRITE, FAIRY_SMALL_SPRITE, 0x17F50):
            machine = machine_for(code)
            machine.reg[3] = index
            owned = index in descriptors
            machine.run(stop=machine.lr if owned else CONTINUATION)
            self.assertEqual(machine.reg[3], descriptors[index] if owned else index)
            if not owned:
                self.assertEqual(machine.reg[0], 0x1234)

    def test_disabled_is_byte_identical_and_unqualified_inputs_fail_closed(self):
        dol, rel = b"existing executable", b"existing REL"
        result = install_fairy_type(b"unknown", dol, "unknown", current_rel=rel, enabled=False)
        self.assertIs(result[0], dol)
        self.assertIs(result[1], rel)
        self.assertFalse(result[2]["enabled"])
        with self.assertRaises(ValueError):
            install_fairy_type(b"", b"", "", enabled=1)
        with self.assertRaises(FormatError):
            qualify_fairy_runtime(b"", "GXXP01")
        for invalid in (None, {}, {**DEFAULT_BADGE_RESOURCES, "en": 1},
                        {**DEFAULT_BADGE_RESOURCES, "de": DEFAULT_BADGE_RESOURCES["en"]}):
            with self.assertRaises(FormatError):
                _resources(invalid, "badge")

    def test_added_move_category_dispatch_preserves_other_moves_and_caller_state(self):
        native = 0x80100000
        categories = {375: 2, 376: 2, 377: 1, 378: 2, 379: 2, 380: 2, 381: 0}
        for register in (20, 23, 25, 27, 30, 31):
            code = _move_category_stub(ADDRESS, native, register, categories)
            for move in (0, 1, 19, 354, 355, 374, *categories, 382, 0x10179):
                machine = machine_for(code)
                machine.reg[3] = 19
                machine.reg[register] = move
                sp, lr = machine.reg[1], machine.lr
                machine.native_targets = {native}
                def callback(target):
                    machine.calls.append((target, machine.reg[3]))
                    machine.reg[3] = 0x1234
                machine.native = callback
                machine.run()
                self.assertEqual(machine.reg[register], move)
                expected = categories.get(move & 0xFFFF)
                self.assertEqual(machine.reg[3], 0x1234 if expected is None else expected)
                self.assertEqual(machine.calls, [(native, 19)] if expected is None else [])
                self.assertEqual((machine.reg[1], machine.lr), (sp, lr))


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {**{f"GC6{k}01": ROOT / f"build/hd-completion/hud/GC6{k}01.dol" for k in "PEJ"},
           **{f"GXX{k}01": ROOT / f"build/xd-validation/{region}/main.dol"
              for k, region in (("P", "eu"), ("E", "us"), ("J", "jp"))}}


@unittest.skipUnless(all(path.is_file() for path in SOURCES.values()), "requires all six private retail DOL inputs")
class FairyRetailQualifications(unittest.TestCase):
    def test_type_lookup_entries_have_real_native_callers_in_every_region(self):
        for game,path in SOURCES.items():
            original=path.read_bytes();layout=qualify_fairy_runtime(original,game)
            targets=set()
            for section in parse_dol(original)['sections']:
                if not section['name'].startswith('text'):continue
                payload=original[section['offset']:section['offset']+section['size']]
                for index,(word,) in enumerate(struct.iter_unpack('>I',payload)):
                    if word & 0xFC000003 != 0x48000001:continue
                    delta=word & 0x3FFFFFC
                    if delta & 0x2000000:delta-=0x4000000
                    targets.add(section['ram_address']+index*4+delta)
            for role in ('category','name','matchup','dual','score'):
                self.assertIn(layout['qualifications'][role]['address'],targets,(game,role))
            if game=='GC6J01':
                self.assertNotIn(0x80109E14,targets)
                self.assertIn(layout['qualifications']['text_sprite']['address'],targets)
                self.assertIn(layout['qualifications']['sprite_text_compare']['address'],targets)
            else:
                self.assertIn(layout['qualifications']['sprite']['address'],targets,(game,'sprite'))

    def test_japanese_real_name_sprite_converter_preserves_all_eighteen_native_names(self):
        original=SOURCES['GC6J01'].read_bytes()
        patched,_,report=install_fairy_type(original,original,'GC6J01',
            badge_resources=DEFAULT_BADGE_RESOURCES)
        row=_LAYOUTS['GC6J01']['qualifications']['text_sprite']
        hook=next(h for h in report['hooks'] if h['role']=='text_sprite')
        table=_read(original,0x802D2728,18*8)
        names=[]
        for i in range(18):
            pointer,sprite,_=struct.unpack_from('>IHH',table,8*i)
            name=_read(original,pointer,32).split(b'\0',1)[0].decode('shift_jis')
            names.append((name,sprite))
        fairy_pointer=report['message_banks']['ja']+24
        for text,expected in [*names,('フェアリー',FAIRY_SPRITE),('テスト',0),('',0),(None,0)]:
            machine=FairyMachine(_read(patched,row['address'],row['size']),row['address'])
            stub=_read(patched,hook['stub'],hook['bytes'])
            machine.code.update({hook['stub']+i:int.from_bytes(stub[i:i+4],'big') for i in range(0,len(stub),4)})
            def write_text(pointer,text):
                for i,value in enumerate(text.encode('utf-16-be')+b'\0\0'):machine.write(pointer+i,value,1)
            def text_at(pointer):
                if not pointer:return ''
                raw=bytearray()
                for i in range(128):
                    value=machine.read(pointer+2*i,2)
                    if not value:return raw.decode('utf-16-be')
                    raw.extend(value.to_bytes(2,'big'))
                self.fail('Unterminated native GSchar fixture')
            for i,value in enumerate(table):machine.write(0x802D2728+i,value,1)
            write_text(fairy_pointer,'フェアリー')
            if text is not None:write_text(0x80700000,text)
            machine.reg[3]=0 if text is None else 0x80700000
            sp,lr=machine.reg[1],machine.lr
            nonvolatile=machine.reg[13:]
            machine.native_targets={0x800F790C,0x800F7AEC}
            def native(target):
                if target==0x800F790C:
                    # Qualified native helper converts its literal Shift-JIS
                    # into the local GSchar buffer. No sprite result is mocked.
                    literal=_read(original,machine.reg[4],32).split(b'\0',1)[0].decode('shift_jis')
                    write_text(machine.reg[3],literal)
                else:
                    a,b=text_at(machine.reg[3]),text_at(machine.reg[4])
                    machine.reg[3]=(a>b)-(a<b) & MASK
            machine.native=native
            machine.run()
            self.assertEqual(machine.reg[3],expected,text)
            self.assertEqual((machine.reg[1],machine.lr),(sp,lr))
            self.assertEqual(machine.reg[13:],nonvolatile)

    def test_japanese_real_type_entries_execute_native_tables_and_fairy_lookup(self):
        original=SOURCES['GC6J01'].read_bytes()
        patched,_,report=install_fairy_type(original,original,'GC6J01',
            badge_resources=DEFAULT_BADGE_RESOURCES)
        layout=qualify_fairy_runtime(original,'GC6J01')
        # Independently exercise the actual table readers, rather than only
        # comparing a site's bytes with a newly copied qualification constant.
        table_address=0x80347C40
        table=_read(original,table_address,18*44)
        for role in ('category','matchup'):
            row=layout['qualifications'][role]
            hook=next(h for h in report['hooks'] if h['role']==role)
            pairs=[(kind,0) for kind in range(20)] if role=='category' else [
                (a,b) for a in range(20) for b in range(20)]
            for a,b in pairs:
                machine=FairyMachine(_read(patched,row['address'],row['size']),row['address'])
                stub=_read(patched,hook['stub'],hook['bytes'])
                machine.code.update({hook['stub']+i:int.from_bytes(stub[i:i+4],'big') for i in range(0,len(stub),4)})
                machine.reg[13]=0x80800000
                machine.write(machine.reg[13]-0x7CF8,18)
                for i,value in enumerate(table):machine.write(table_address+i,value,1)
                machine.reg[3:5]=[a,b]
                machine.run()
                expected=(2 if a==19 else table[44*a] if a<18 else 0) if role=='category' else (
                    fairy_effectiveness(a,b) if 19 in (a,b) else
                    int.from_bytes(table[44*a+8+2*b:44*a+10+2*b],'big') if a<18 and b<18 else 0)
                self.assertEqual(machine.reg[3],expected,(role,a,b))
        # The previously inferred western offset is the middle of an unrelated
        # Japanese function. It must now remain byte-identical, never hooked.
        self.assertNotIn('sprite',layout['qualifications'])
        self.assertEqual(_read(patched,0x80109E14,52),_read(original,0x80109E14,52))
        self.assertEqual(len([h for h in report['hooks'] if h['role']=='direct_type_sprite']),4)
        for row in _DIRECT_SPRITE_READS['GC6J01']:
            ids=struct.unpack('>18H',_read(original,row['table'],36))
            self.assertEqual(ids[0],86)
            self.assertEqual(ids[9],93)
            self.assertEqual(ids[14],83)
            # Those IDs really describe Normal/Mystery/Psychic pixels in the
            # native Japanese type atlas, not an unrelated same-sized sprite.
            for kind,xy in ((0,(6,193)),(9,(173,38)),(14,(90,38))):
                record=_read(original,layout['sprite_table']+ids[kind]*24,24)
                self.assertEqual(struct.unpack_from('>HHHHI',record,8),(*xy,79,27,0x02081200))

    def test_six_originals_qualify_and_only_owned_code_windows_change(self):
        for game, source in SOURCES.items():
            original = source.read_bytes()
            digest = hashlib.sha256(original).hexdigest()
            before_layout = qualify_fairy_runtime(original, game)
            dol, rel, report = install_fairy_type(original, original, game,
                badge_resources=DEFAULT_BADGE_RESOURCES,
                small_badge_resources=DEFAULT_SMALL_BADGE_RESOURCES if game.startswith("GXX") else None)
            self.assertIsNone(rel)
            self.assertTrue(report["native_badges_installed"])
            self.assertEqual(report["reserved_native_types_preserved"], [9, 18])
            self.assertEqual(report["ai_scan_bound"], 20)
            self.assertEqual(_read(dol, report["ai_scan_site"], 4), bytes.fromhex("38000014"))
            self.assertEqual(_read(dol, before_layout["sprite_table"], before_layout["sprite_stride"] * 18),
                             _read(original, before_layout["sprite_table"], before_layout["sprite_stride"] * 18))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
            section = next(s for s in parse_dol(dol)["sections"] if s["name"] == "text2")
            self.assertEqual(section["offset"] + section["size"], len(dol))
            with self.assertRaises(FormatError):
                install_fairy_type(original, dol, game)

    def test_actual_native_dual_type_algorithm_consumes_fairy_immunity_and_resistance(self):
        for game, source in SOURCES.items():
            original = source.read_bytes()
            layout = qualify_fairy_runtime(original, game)
            dual, lookup = (layout["qualifications"][key] for key in ("dual", "matchup"))
            for attack, defenders, expected in ((16, (19, 3), NATIVE_IMMUNE),
                    (3, (19, 0), NATIVE_SUPER), (1, (19, 0), NATIVE_RESIST),
                    (19, (19, 19), NATIVE_NEUTRAL), (10, (19, 0), NATIVE_NEUTRAL)):
                machine = ItemMachine(_read(original, dual["address"], dual["size"]), dual["address"])
                pointer = 0x80800000
                for index, value in enumerate(defenders):
                    machine.write(pointer + index * 2, value, 2)
                machine.reg[3:6] = [attack, pointer, len(defenders)]
                machine.native_targets = {lookup["address"]}
                def native(_target):
                    a, b = machine.reg[3:5]
                    value = fairy_effectiveness(a, b)
                    machine.reg[3] = NATIVE_NEUTRAL if value is None else value
                machine.native = native
                machine.run()
                self.assertEqual(machine.reg[3], expected, (game, attack, defenders))

    def test_actual_native_ai_scan_includes_fairy_and_keeps_its_existing_mask_rules(self):
        for game, source in SOURCES.items():
            original = source.read_bytes()
            layout = qualify_fairy_runtime(original, game)
            score, lookup = (layout["qualifications"][key] for key in ("score", "matchup"))
            payload = bytearray(_read(original, score["address"], score["size"]))
            struct.pack_into(">I", payload, layout["score_limit_offset"], 0x38000014)
            for kind, mode, mask, expected in ((16, 1, 0, -10), (3, 0, 0, 10),
                                               (19, 1, 0, 0)):
                machine = FairyMachine(bytes(payload), score["address"])
                machine.reg[13] = 0x80800000
                if game.startswith("GXX"):
                    displacement = int.from_bytes(payload[0x12A:0x12C], "big", signed=True)
                    machine.write(machine.reg[13] + displacement, 0x80610000)
                machine.reg[3:6] = [kind, mode, mask]
                machine.native_targets = {lookup["address"]}
                seen = []
                def native(_target):
                    a, b = machine.reg[3:5]
                    seen.append((a, b))
                    value = fairy_effectiveness(a, b)
                    machine.reg[3] = (NATIVE_NEUTRAL if a < 18 and b < 18 else 0) if value is None else value
                machine.native = native
                machine.run()
                value = machine.reg[3]
                self.assertEqual(value - 0x100000000 if value & 0x80000000 else value,
                                 expected, (game, kind, mode))
                self.assertTrue(any(19 in pair for pair in seen))
                self.assertEqual(len(seen), 19)  # 0..19 with Mystery9 skipped

    def test_supplemental_category_hooks_compose_after_type_and_leave_core_damage_calls_alone(self):
        for game, source in SOURCES.items():
            original = source.read_bytes()
            before, _, _ = install_fairy_type(original, original, game)
            after, report = install_move_category_callers(original, before, game, {377: 1, 375: 2})
            self.assertEqual({h["role"] for h in report["hooks"]},
                             {"damage_bookkeeping", "hustle_accuracy", "mirror_coat_ai", "counter_ai"})
            self.assertEqual([h["move_register"] for h in report["hooks"]],
                             [25,20,27,27] if game.startswith('GXX') else [30,31,23,23])
            category = _LAYOUTS[game]["qualifications"]["category"]["address"]
            self.assertEqual(_read(before, category, 4), _read(after, category, 4))
            arena = next(s for s in parse_dol(before)["sections"] if s["name"] == "text2")
            self.assertEqual(after[arena["offset"] + 32:len(before)], before[arena["offset"] + 32:])
            final_arena = next(s for s in parse_dol(after)["sections"] if s["name"] == "text2")
            self.assertEqual(final_arena["offset"] + final_arena["size"], len(after))
            with self.assertRaises(FormatError):
                install_move_category_callers(original, after, game, {377: 1})
            with self.assertRaises(FormatError):
                install_move_category_callers(original, before, game, {354: 1})

    def test_type_hooks_compose_after_existing_code_without_duplicating_its_arena(self):
        for game, source in SOURCES.items():
            if not game.startswith("GC6"):
                continue
            original = source.read_bytes()
            before, _ = install_colosseum_category_callers(original, original, game, {377: 1})
            after, _, _ = install_fairy_type(original, before, game,
                badge_resources=DEFAULT_BADGE_RESOURCES)
            arena = next(s for s in parse_dol(before)["sections"] if s["name"] == "text2")
            self.assertEqual(after[arena["offset"] + 32:len(before)], before[arena["offset"] + 32:])
            final_arena = next(s for s in parse_dol(after)["sections"] if s["name"] == "text2")
            self.assertEqual(final_arena["offset"] + final_arena["size"], len(after))


if __name__ == "__main__":
    unittest.main()
