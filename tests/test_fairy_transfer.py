"""Trade-selection rejection and bounded native Conversion2 collection."""
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_dol, parse_rel
from orre_randomizer.engine.inspect_tables import rel_symbols
from orre_randomizer.fairy_runtime import (
    _CONVERSION_LAYOUTS, _LAYOUTS, _PURIFICATION_LAYOUTS, _GRID_LAYOUTS, _AI_SWITCH_LAYOUTS,
    _HELPING_HAND_LAYOUTS, _helping_hand_iterator_stub,
    _grid_stub, _read, FAIRY_SPRITE, fairy_effectiveness, install_fairy_type,
)
from orre_randomizer.fairy_transfer import (
    _QUALIFIED, _xd_guard, _colo_guard, _refusal_message, install_fairy_transfer,
)
from tests.test_fairy_runtime import SOURCES
from tests.test_fairy_move_effects import EffectMachine, native_calls, MASK


ADDRESS, POKEMON, FLAG, NATIVE, REFRESH, CONTINUE = (0x81600000, 0x80610000, 0x81620000,
                                                   0x80100000, 0x81630000, 0x80020000)


class FairyTransferContracts(unittest.TestCase):
    def test_helping_hand_iterator_skips_absent_rows_and_preserves_other_registers(self):
        for iterator,native_count in ((22,358),(23,375)):
            for candidate in (*range(350,386),0,1,65535):
                machine=EffectMachine(_helping_hand_iterator_stub(ADDRESS,NATIVE,iterator),ADDRESS)
                machine.reg[0],machine.reg[4],machine.reg[iterator]=native_count,candidate,candidate
                before=machine.reg.copy();stack,link=machine.reg[1],machine.lr
                machine.run(stop=NATIVE+4)
                expected=375 if native_count <= candidate < 375 else candidate
                self.assertEqual(machine.reg[4],expected)
                self.assertEqual(machine.reg[iterator],expected)
                self.assertEqual(machine.cr,(expected < 382,expected==native_count) if expected<native_count else
                                 (True,False) if expected<382 else (False,False))
                for register in set(range(32))-{4,iterator}:
                    self.assertEqual(machine.reg[register],before[register])
                self.assertEqual((machine.reg[1],machine.lr),(stack,link))
                self.assertEqual(machine.mem,{})

    def test_dragon_rage_grid_retains_fixed_damage_and_displays_fairy_immunity(self):
        for row in _GRID_LAYOUTS.values():
            for attack in (0, 1, 3, 8, 16, 17, 18, 19):
                machine = EffectMachine(_grid_stub(ADDRESS, row), ADDRESS)
                for register in range(24, 32):
                    machine.write(machine.reg[1]+0x10+4*(register-24),0x11110000+register)
                machine.reg[26:32] = [17, 82, 0, 0, POKEMON+0x1000, POKEMON]
                machine.write(POKEMON+6, 0x1e8, 2)
                machine.native_targets = {row[k] for k in ('compatible','move_status','affinity','layer','draw_sprite')}
                draws = []
                def native(target):
                    args = machine.reg[3:9].copy()
                    if target == row['compatible']:
                        self.assertEqual(args[0], 82)
                        result = 15
                    elif target == row['move_status']:
                        self.assertEqual(args[:4], [0,82,3,0])
                        result = attack
                    elif target == row['affinity']:
                        self.assertEqual(args[:2], [attack,19])
                        result = fairy_effectiveness(attack,19)
                    elif target == row['layer']:
                        result = 7
                    else:
                        draws.append(args)
                        result = 0
                    machine.reg[3] = result
                machine.native = native
                machine.run(stop=row['epilogue_address']+4)
                expected = 0x35e if attack == 16 else 0x35d
                self.assertEqual(draws[1][3], expected)

    def test_xd_fairy_grid_uses_the_native_move_compatibility_modes_and_reserved_cell(self):
        effect_sprites = {0x3f: 0x35d, 0x41: 0x35f, 0x42: 0x360, 0x43: 0x35e}
        for row in _GRID_LAYOUTS.values():
            payload = _grid_stub(ADDRESS, row)
            for mode in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16):
                for attack in (0, 1, 3, 8, 16, 17, 18, 19):
                    machine = EffectMachine(payload, ADDRESS)
                    stack = machine.reg[1]
                    for register in range(24, 32):
                        machine.write(stack + 0x10 + 4 * (register-24), 0x11110000 + register)
                    machine.reg[26:32] = [17, 204, 0, 0, POKEMON+0x1000, POKEMON]
                    machine.write(POKEMON+6, 0x1e8, 2)
                    machine.native_targets = {row[k] for k in ('compatible','move_status','affinity','layer','draw_sprite')}
                    draws, queries = [], []
                    def native(target):
                        args = machine.reg[3:9].copy()
                        result = 0
                        if target == row['compatible']:
                            self.assertEqual(args[0], 204)
                            result = mode
                        elif target == row['move_status']:
                            self.assertEqual(args[:4], [0, 204, 3, 0])
                            result = attack
                        elif target == row['affinity']:
                            self.assertEqual(args[:2], [attack, 19])
                            queries.append(tuple(args[:2]))
                            result = fairy_effectiveness(*args[:2])
                        elif target == row['layer']:
                            self.assertEqual(args[:2], [POKEMON+0x1000, POKEMON])
                            result = 7
                        else:
                            draws.append(args)
                        for register in (0, *range(3, 13)):
                            machine.reg[register] = 0xdead0000 + register
                        machine.reg[3] = result
                    machine.native = native
                    machine.run(stop=row['epilogue_address']+4)
                    marker = (effect_sprites.get(fairy_effectiveness(attack,19), 0) if mode == 1
                              else 0x376 if mode in (10,11,14)
                              else 0x35d if 4 <= mode <= 15 else 0)
                    self.assertEqual(draws[0], [MASK-87,12,POKEMON+0x1000,FAIRY_SPRITE,0,7])
                    self.assertEqual(draws[1:], [[0,14,POKEMON+0x1000,marker,0,7]] if marker else [])
                    self.assertEqual(queries, [(attack,19)] if mode == 1 else [])
                    self.assertEqual(machine.reg[1], stack)
            for active_type, item in ((0,0x1e8), (17,0x1f8), (0,0x1f8)):
                machine = EffectMachine(payload, ADDRESS)
                for register in range(24,32):
                    machine.write(machine.reg[1]+0x10+4*(register-24), 0)
                machine.reg[26], machine.reg[31] = active_type, POKEMON
                machine.write(POKEMON+6,item,2)
                machine.run(stop=row['epilogue_address']+4)
                self.assertEqual(machine.calls, [])

    def test_colosseum_rejects_each_added_move_in_any_slot_and_preserves_other_checks(self):
        for move in (0,33,354,355,*range(375,382),382,65535):
            for slot in range(4):
                for bad_egg in (0,1):
                    machine=EffectMachine(_colo_guard(ADDRESS,NATIVE,FLAG,REFRESH),ADDRESS)
                    machine.reg[3]=POKEMON
                    raw=bytes((i*17+3)&255 for i in range(0x138))
                    for i,b in enumerate(raw):machine.write(POKEMON+i,b,1)
                    for i in range(4):machine.write(POKEMON+0x78+4*i,move if i==slot else 33,2)
                    before=bytes(machine.read(POKEMON+i,1)for i in range(len(raw)))
                    machine.write(FLAG,999);machine.native_targets={NATIVE,REFRESH};calls=[]
                    def native(target):
                        calls.append(target)
                        if target==NATIVE:self.assertEqual(machine.reg[3],POKEMON)
                        for register in (0,*range(3,13)):machine.reg[register]=0xdead0000+register
                        machine.reg[3]=bad_egg if target==NATIVE else 0
                    machine.native=native;sp,lr=machine.reg[1],machine.lr
                    machine.run()
                    rejected=375<=move<=381
                    self.assertEqual(calls,[REFRESH]if rejected else[NATIVE])
                    self.assertEqual(machine.reg[3],1 if rejected else bad_egg)
                    self.assertEqual(machine.read(FLAG),int(rejected))
                    self.assertEqual((machine.reg[1],machine.lr),(sp,lr))
                    self.assertEqual(bytes(machine.read(POKEMON+i,1)for i in range(len(raw))),before)

    def test_colosseum_only_custom_refusal_uses_private_message_and_native_bad_egg_stays_native(self):
        row={'message_word':0x380044BE}
        for rejected in (False,True):
            machine=EffectMachine(_refusal_message(ADDRESS,CONTINUE,FLAG,row['message_word'],0xF0480),ADDRESS)
            machine.write(FLAG,int(rejected));machine.native_targets={CONTINUE};result=[]
            machine.reg[11] = 0x12345678
            machine.cr = (True, False)
            stack = machine.reg[1]
            machine.native=lambda _target:result.append(machine.reg[0])
            machine.run();self.assertEqual(result,[0xF0480 if rejected else 0x44BE])
            self.assertEqual((machine.reg[11], machine.reg[1], machine.cr), (0x12345678, stack, (True, False)))

    def test_xd_outgoing_only_refusal_keeps_all_native_return_states_otherwise(self):
        row={'first_word':0x9421FFF0,'address':NATIVE,'refusal_state':5}
        for side in (0,1,-1):
            for move in (0,33,354,*range(375,382),382):
                for pointer in (0,POKEMON):
                    machine=EffectMachine(_xd_guard(ADDRESS,row),ADDRESS)
                    machine.reg[3:5]=[pointer,side&MASK]
                    for i in range(4):machine.write(POKEMON+0x80+4*i,move,2)
                    machine.native_targets={NATIVE+4};calls=[];sp,lr=machine.reg[1],machine.lr
                    def native(target):
                        calls.append((target,machine.reg[3],machine.reg[4]))
                        machine.reg[1]+=16;machine.reg[3]=7 # original permitted state
                    machine.native=native;machine.run()
                    rejected=pointer and side==0 and 375<=move<=381
                    self.assertEqual(machine.reg[3],5 if rejected else 7)
                    self.assertEqual(len(calls),0 if rejected else 1)
                    self.assertEqual((machine.reg[1],machine.lr),(sp,lr))

    def test_disabled_does_not_qualify_or_require_messages(self):
        data=b'unchanged';result,report=install_fairy_transfer(b'',data,'?',enabled=False)
        self.assertIs(result,data);self.assertFalse(report['enabled'])


@unittest.skipUnless(all(path.is_file()for path in SOURCES.values()),'requires six private retail DOLs')
class FairyRetailTransferContracts(unittest.TestCase):
    def test_actual_helping_hand_loop_observes_added_attacks_without_growing_any_table(self):
        for game,row in _HELPING_HAND_LAYOUTS.items():
            original=SOURCES[game].read_bytes()
            patched,_,report=install_fairy_type(original,original,game)
            hook=next(h for h in report['hooks']if h['role']=='helping_hand_move_scan')
            payload=_read(patched,row['address'],row['size'])
            stub=_read(patched,hook['stub'],hook['bytes'])
            calls=native_calls(_read(original,row['address'],row['size']),row['address'])
            self.assertEqual(len(calls),2)
            for knows_added_attack in (False,True):
                machine=EffectMachine(payload,row['address'])
                machine.code.update({hook['stub']+i:int.from_bytes(stub[i:i+4],'big')for i in range(0,len(stub),4)})
                machine.reg[13]=0x80800000
                count_word=int.from_bytes(_read(original,row['compare_address']-12,4),'big')
                displacement=count_word&65535;displacement-=65536 if displacement&32768 else 0
                machine.write(machine.reg[13]+displacement,FLAG)
                machine.write(FLAG,row['native_count'])
                machine.native_targets=set(calls);seen=[];membership=[]
                def native(target):
                    args=machine.reg[3:9].copy()
                    if target==calls[0]:
                        move=args[1];seen.append(move)
                        result=int(375<=move<=380)
                    else:
                        membership.append(args[4]);result=int(knows_added_attack)
                    for register in (0,*range(3,13)):machine.reg[register]=0xdead0000+register
                    machine.reg[3]=result
                machine.native=native
                machine.run(stop=row['address']+row['size'])
                excluded={0,355,374 if game.startswith('GXX') else 357}
                expected=[i for i in range(row['native_count'])if i not in excluded]+list(range(375,382))
                self.assertEqual(seen,expected)
                self.assertEqual(membership,list(range(375,381)))
                self.assertEqual(machine.reg[row['iterator_register']-1],int(knows_added_attack))
                self.assertEqual(machine.read(FLAG),row['native_count'])
                self.assertTrue(report['native_move_count_unchanged'])

    def test_actual_ai_switch_scan_scores_fairy_threats_without_type_indexed_arrays(self):
        for game, row in _AI_SWITCH_LAYOUTS.items():
            original = SOURCES[game].read_bytes()
            patched, _, report = install_fairy_type(original, original, game)
            self.assertEqual(report['ai_switch_scan_bound'], 20)
            payload = _read(patched, row['address'], row['size'])
            xd = game.startswith('GXX')
            targets = native_calls(payload, row['address'])
            self.assertEqual(len(targets), 4 if xd else 6)
            for opponents in (0, 1):
                for fairy_is_threat in (False, True):
                    machine = EffectMachine(payload, row['address'])
                    machine.reg[13] = 0x80800000
                    if xd:
                        machine.reg[30], machine.reg[24] = POKEMON+0x2000, POKEMON
                        machine.reg[26], machine.reg[27] = FLAG, 0
                        displacement = int.from_bytes(_read(original, row['bound_address']-6, 2), 'big', signed=True)
                        machine.write(machine.reg[13]+displacement, FLAG+0x100)
                        machine.write(FLAG+0x100, 18)
                    else:
                        machine.reg[15], machine.reg[27] = POKEMON+0x2000, POKEMON
                        machine.reg[29], machine.reg[30] = FLAG, 0
                    machine.write(FLAG, 0)
                    words = struct.unpack('>'+'I'*(len(payload)//4), payload)
                    count_offsets = {word & 65535 for word in words if word & 0xffff0000 == 0x80010000}
                    array_offset = next(word & 65535 for word in words if word & 0xffff0000 == 0x39c10000)
                    self.assertEqual(len(count_offsets), 1)
                    self.assertTrue(all(0x700 <= value <= 0xa00 for value in count_offsets))
                    for value in count_offsets:
                        machine.write(machine.reg[1]+value, opponents)
                    machine.write(machine.reg[1]+array_offset, POKEMON+0x4000)
                    machine.native_targets = set(targets)
                    seen = []
                    def native(target):
                        args = machine.reg[3:9].copy()
                        result = 0
                        if target == targets[0]:
                            seen.append(args[2])
                            result = 0x41 if args[2] == 19 and fairy_is_threat else 0x3f
                        elif target == targets[1]:
                            result = 1
                        elif target == targets[2]:
                            result = 2
                        elif target == targets[3]:
                            result = args[0]+1
                        for register in (0, *range(3,13)):
                            machine.reg[register] = 0xdead0000+register
                        machine.reg[3] = result
                    machine.native = native
                    machine.run(stop=row['address']+row['size'])
                    self.assertEqual(set(seen), set(range(20))-{9})
                    self.assertEqual(seen.count(19), 1+int(bool(opponents and fairy_is_threat)))
                    self.assertEqual(machine.read(FLAG), int(bool(opponents and fairy_is_threat)))
                    self.assertEqual(machine.reg[20 if xd else 17], 20)

    def test_actual_xd_purification_type_array_initializes_and_bounds_fairy_index(self):
        for game, row in _PURIFICATION_LAYOUTS.items():
            original = SOURCES[game].read_bytes()
            patched, _, report = install_fairy_type(original, original, game)
            self.assertEqual(report['purification_type_buffer_slots'], 20)
            self.assertEqual(report['purification_type_buffer_stack_bytes'], 32)
            payload = _read(patched, row['address'], row['size'])
            targets = native_calls(payload, row['address'])
            self.assertEqual(len(targets), 4)
            for types in (((19, 19), (14, 14), (0, 0), (16, 16)),
                          ((19, 14), (14, 14), (0, 0), (16, 16)),
                          ((19, 19), (8, 8), (16, 16), (10, 10))):
                for include_center in (False, True):
                    machine = EffectMachine(payload, row['address'])
                    machine.reg[3:5] = [POKEMON, int(include_center)]
                    machine.reg[13] = 0x80800000
                    # Both original count-pointer reads stay intact. Deliberately
                    # leave that count at 18, proving there is no global growth.
                    for i in range(0, 0x50, 4):
                        word = int.from_bytes(payload[i:i+4], 'big')
                        if word & 0xffff0000 == 0x80ad0000:
                            delta = word & 65535
                            delta -= 65536 if delta & 32768 else 0
                            machine.write(machine.reg[13] + delta, FLAG)
                    machine.write(FLAG, 18)
                    stack, link = machine.reg[1], machine.lr
                    native_registers = machine.reg[21:32].copy()
                    buffer = []
                    center = (3, 3)
                    machine.native_targets = set(targets)
                    def native(target):
                        if target == targets[0]:
                            address, value, count = machine.reg[3:6]
                            self.assertEqual((value, count), (0, 20))
                            buffer.append(address)
                            for i in range(20):
                                machine.write(address+i, 0, 1)
                            for i in range(20, 24):
                                machine.write(address+i, 0xa5, 1)
                        elif target == targets[1]:
                            machine.reg[3] = 1
                        elif target == targets[2]:
                            pass  # native embedded-record pointer getter
                        else:
                            pokemon, index = machine.reg[3:5]
                            slot = (pokemon - POKEMON) // 0xc4
                            machine.reg[3] = (center if slot == 4 else types[slot])[index]
                    machine.native = native
                    machine.run()
                    flattened = []
                    unique = True
                    for pair in (*types, *((center,) if include_center else ())):
                        for type_id in set(pair):
                            if type_id in flattened:
                                unique = False
                            flattened.append(type_id)
                    self.assertEqual(machine.reg[3], int(unique), (game, types, include_center))
                    self.assertEqual(len(buffer), 1)
                    self.assertEqual(machine.read(buffer[0]+19, 1), 1)
                    self.assertEqual(bytes(machine.read(buffer[0]+i, 1) for i in range(20, 24)), b'\xa5'*4)
                    self.assertEqual(machine.read(FLAG), 18)
                    self.assertEqual((machine.reg[1], machine.lr), (stack, link))
                    self.assertEqual(machine.reg[21:32], native_registers)

    def test_six_export_guards_compose_after_type_and_preserve_existing_arenas(self):
        for game,path in SOURCES.items():
            original=path.read_bytes();before,_,_=install_fairy_type(original,original,game)
            xd=game.startswith('GXX');kwargs={}if xd else{'message_refresh_address':REFRESH,'refusal_message_id':0xF0480}
            after,report=install_fairy_transfer(original,before,game,**kwargs)
            self.assertEqual(report['rejected_move_ids'],list(range(375,382)))
            arena=next(s for s in parse_dol(before)['sections']if s['name']=='text2')
            self.assertEqual(after[arena['offset']+32:len(before)],before[arena['offset']+32:])
            with self.assertRaises(FormatError):install_fairy_transfer(original,after,game,**kwargs)
            if not xd:
                with self.assertRaises(FormatError):install_fairy_transfer(original,before,game)

    def test_actual_conversion2_collects_fairy_resistance_without_overwriting_18_slot_buffer(self):
        for game,path in SOURCES.items():
            original=path.read_bytes();row=_CONVERSION_LAYOUTS[game]
            function=bytearray(_read(original,row['address'],row['size']))
            struct.pack_into('>I',function,row['bound_address']-row['address'],0x28000014)
            xd=game.startswith('GXX')
            if xd:
                region={'P':'eu','E':'us','J':'jp'}[game[3]]
                rel=(Path(__file__).resolve().parents[1]/f'build/xd-validation/{region}/common_rel').read_bytes()
                base=rel_symbols(rel,parse_rel(rel))[130]['offset']
                chart=[[int.from_bytes(rel[base+i*48+12+j*2:base+i*48+14+j*2],'big')for j in range(18)]for i in range(18)]
            else:
                q=_LAYOUTS[game]['qualifications']['matchup'];lookup=_read(original,q['address'],q['size'])
                high=next(int.from_bytes(lookup[i:i+4],'big')&65535 for i in range(0,len(lookup),4)
                          if int.from_bytes(lookup[i:i+4],'big')&0xffff0000==0x3ca00000)
                low=next(int.from_bytes(lookup[i:i+4],'big')&65535 for i in range(0,len(lookup),4)
                         if int.from_bytes(lookup[i:i+4],'big')&0xffff0000==0x38a50000)
                base=(high<<16)+(low-65536 if low&32768 else low)
                raw=_read(original,base,18*44)
                chart=[[int.from_bytes(raw[i*44+8+j*2:i*44+10+j*2],'big')for j in range(18)]for i in range(18)]
            self.assertTrue(all(chart[i][9]==0x3f for i in range(18)))
            def affinity(a,b):
                value=fairy_effectiveness(a,b)
                return value if value is not None else chart[a][b]if a<18 and b<18 else 0
            for attack in range(20):
                for owned in ((0,0),(19,19),(14,19),(3,8)):
                    machine=EffectMachine(bytes(function),row['address']);out=POKEMON+0x1000
                    machine.reg[3:6]=[POKEMON,attack,out]
                    machine.write(out-4,0x12345678);machine.write(out+18*4,0x89abcdef)
                    targets=native_calls(function,row['address']);machine.native_targets=set(targets)
                    def native(target):
                        args=machine.reg[3:9].copy()
                        if targets.index(target)==0:
                            value=int(args[1]in owned)if xd else owned[args[3]]
                        else:value=affinity(args[0],args[1])
                        machine.reg[3]=value
                    machine.native=native;machine.run();count=machine.reg[3]
                    expected=[i for i in range(20)if i not in owned and affinity(attack,i)in(0x42,0x43)]
                    self.assertEqual([machine.read(out+4*i)for i in range(count)],expected,(game,attack,owned))
                    self.assertLessEqual(count,18);self.assertNotIn(9,expected);self.assertNotIn(18,expected)
                    self.assertEqual((machine.read(out-4),machine.read(out+18*4)),(0x12345678,0x89abcdef))
                    if attack==16 and 19 not in owned:self.assertIn(19,expected)


if __name__=='__main__':unittest.main()
