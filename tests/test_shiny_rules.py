"""Independent PPC execution of emitted hooks, canonical status and composition.

The PID generator/RNG are ABI-clobbering test doubles here. Native game runtime
validation is separate; these tests never open a save or start Dolphin.
"""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.engine.gift_move_hooks import patch_gift_moves, SECTION_RAM, _arena_guard
from orre_randomizer.engine.shiny_rules import (COIN_RANGE, NATIVE_RNG, OT_EXIT,
    PID_GENERATOR, PID_CALLS, PLAYER_POINTER, TEXT_TO_RAM, chance_threshold,
    TRAINER_INDEX_HOOK, TRAINER_INDEX_WORD, TRAINER_SLOT_COUNT, SHADOW_COUNT,
    seeded_coin, seeded_status, _index_trampoline, _seeded_trainer_wrapper,
    _pid_wrapper, _ot_wrapper, apply_shiny_rules)
from orre_randomizer.options import Options
from orre_randomizer.service import UserError, validate_options

MASK=0xFFFFFFFF


def is_shiny(pid, trainer_id):
    return ((pid >> 16) ^ (pid & 0xFFFF) ^ (trainer_id >> 16) ^ (trainer_id & 0xFFFF)) < 8


class Machine:
    def __init__(self, data, address, random_values=()):
        self.code={address+i:word[0] for i,word in zip(range(0,len(data),4),struct.iter_unpack('>I',data))}
        self.pc=address
        self.reg=[(0x12340000+i*257)&MASK for i in range(32)]
        self.reg[1]=0x80500000
        self.lr=0x81234560
        self.mem={}
        self.cr=(False,False)
        self.rng=iter(random_values)
        self.calls=[]

    def write(self,address,value,width=4):
        for i,b in enumerate((value&((1<<(width*8))-1)).to_bytes(width,'big')):
            self.mem[address+i]=b

    def read(self,address,width=4):
        return int.from_bytes(bytes(self.mem[address+i] for i in range(width)),'big')

    def native(self,target):
        args=self.reg[3:8].copy()
        self.calls.append((target,args))
        if target==NATIVE_RNG:
            result=next(self.rng)
        elif target==PID_GENERATOR:
            _,gender,nature,policy,tid=args
            assert policy in (0,1)
            high=0xABCD
            low=high^(tid>>16)^(tid&0xFFFF)^(0 if policy else 8)
            result=(high<<16)|(low&0xFFFF)
        else:
            raise AssertionError(hex(target))
        for i in (0,*range(3,13)):
            self.reg[i]=0xDEAD0000+i
        self.reg[3]=result

    def run(self,stop=None):
        stop=self.lr if stop is None else stop
        for _ in range(500):
            if self.pc==stop:
                return
            w=self.code[self.pc];pc=self.pc;self.pc+=4
            op=w>>26;rs=(w>>21)&31;ra=(w>>16)&31;rb=(w>>11)&31
            imm=w&0xFFFF;signed=imm-0x10000 if imm&0x8000 else imm
            if w==0x7C0802A6:self.reg[0]=self.lr
            elif w==0x7C0803A6:self.lr=self.reg[0]
            elif w==0x4E800020:self.pc=self.lr
            elif op in (14,15):
                self.reg[rs]=((self.reg[ra] if ra else 0)+(signed<<(16 if op==15 else 0)))&MASK
            elif op==24:self.reg[ra]=self.reg[rs]|imm
            elif op in (32,40):self.reg[rs]=self.read((self.reg[ra]+signed)&MASK,2 if op==40 else 4)
            elif op in (36,37):
                address=(self.reg[ra]+signed)&MASK;self.write(address,self.reg[rs])
                if op==37:self.reg[ra]=address
            elif op==46:
                address=(self.reg[ra]+signed)&MASK
                for i in range(rs,32):self.reg[i]=self.read(address+(i-rs)*4)
            elif op in (10,11):
                left=self.reg[ra]
                if op==11:left=left-(1<<32) if left&(1<<31) else left
                right=imm if op==10 else signed
                self.cr=(left<right,left==right)
            elif op==31 and ((w>>1)&1023)==32:
                self.cr=(self.reg[ra]<self.reg[rb],self.reg[ra]==self.reg[rb])
            elif op==31 and ((w>>1)&1023)==444:self.reg[ra]=self.reg[rs]|self.reg[rb]
            elif op==31 and ((w>>1)&1023)==87:self.reg[rs]=self.read((self.reg[ra]+self.reg[rb])&MASK,1)
            elif op==21:
                shift=(w>>11)&31;mb=(w>>6)&31;me=(w>>1)&31
                mask=sum(1<<(31-i) for i in range(32) if (mb<=i<=me if mb<=me else i>=mb or i<=me))
                value=self.reg[rs]
                self.reg[ra]=(((value<<shift)|(value>>(32-shift) if shift else value))&MASK)&mask
            elif op==16:
                bo=(w>>21)&31;bi=(w>>16)&31
                condition=self.cr[0] if bi==0 else self.cr[1] if bi==2 else None
                assert condition is not None and bo in (4,12)
                if condition==(bo==12):
                    displacement=w&0xFFFC
                    self.pc=pc+(displacement-0x10000 if displacement&0x8000 else displacement)
            elif op==18:
                assert not w&2
                displacement=w&0x3FFFFFC
                if displacement&0x2000000:displacement-=0x4000000
                target=pc+displacement
                if w&1:self.lr=pc+4
                if target in (NATIVE_RNG,PID_GENERATOR):self.native(target);self.pc=self.lr
                else:self.pc=target
            else:raise AssertionError(f'unsupported {w:08x} at {pc:08x}')
        raise AssertionError('hook did not return')


class ShinyHookTests(unittest.TestCase):
    def test_seeded_status_is_per_encounter_stable_unicode_and_monotonic_in_rate(self):
        keys = ["special:umbreon", "special:espeon", "shadow:21", "trainer:123"]
        self.assertEqual([seeded_coin("été 🌟", key) for key in keys],
                         [seeded_coin("été 🌟", key) for key in keys])
        self.assertEqual(len({seeded_coin("été 🌟", key) for key in keys}), len(keys))
        self.assertNotEqual(seeded_coin("été 🌟", keys[0]), seeded_coin("été 🌟 ", keys[0]))
        for key in keys:
            self.assertFalse(seeded_status("été 🌟", key, 0))
            self.assertTrue(seeded_status("été 🌟", key, 100))
            values = [seeded_status("été 🌟", key, rate) for rate in range(101)]
            self.assertEqual(values, sorted(values))
        for seed in (None, "", " ", "é" * 129):
            with self.assertRaises(ValueError):seeded_coin(seed, keys[0])

    def test_index_trampoline_preserves_every_register_except_displaced_r28(self):
        m = Machine(_index_trampoline(SECTION_RAM+32), SECTION_RAM+32)
        m.reg[3] = 0xBEEF0456
        before, link = m.reg.copy(), m.lr
        m.run(stop=TRAINER_INDEX_HOOK+4)
        expected = before.copy(); expected[28] = before[3]
        self.assertEqual(m.reg, expected)
        self.assertEqual(m.read(before[1]+0x48), before[3])
        self.assertEqual(m.lr, link)

    def test_seeded_native_lookup_owner_abi_bounds_and_no_runtime_coin(self):
        trainer_flags, shadow_flags = 0x81600000, 0x81602000
        for sid, index, expected, player in ((0, 5, True, True), (0, 6, False, True),
                (21, 5, False, True), (22, 6, True, True), (22, 6, True, False),
                (0, 0xABCD0005, True, True), (0, TRAINER_SLOT_COUNT, False, True),
                (SHADOW_COUNT, 5, False, True)):
            m = Machine(_seeded_trainer_wrapper(SECTION_RAM+32, trainer_flags, shadow_flags), SECTION_RAM+32)
            m.reg[3:8] = [0x8050AB00, 1, 7, 0, 0x12345678]
            m.reg[30] = sid
            m.write(m.reg[1]+0x48, index)
            m.write(PLAYER_POINTER, 0x80510000 if player else 0)
            m.write(0x8051009C, 0x2468ABCD)
            m.write(trainer_flags+5, 1, 1); m.write(trainer_flags+6, 0, 1)
            m.write(shadow_flags+21, 0, 1); m.write(shadow_flags+22, 1, 1)
            before, link = m.reg.copy(), m.lr
            m.run()
            owner = 0x2468ABCD if sid and player else 0x12345678
            self.assertEqual(m.calls, [(PID_GENERATOR, [before[3], 1, 7, int(expected), owner])])
            self.assertEqual(is_shiny(m.reg[3], owner), expected)
            self.assertEqual(m.reg[1:3], before[1:3])
            self.assertEqual(m.reg[13:], before[13:])
            self.assertEqual(m.lr, link)
    def test_thresholds_endpoints_native_rate_and_invalid_values(self):
        self.assertEqual(chance_threshold(0),0)
        self.assertEqual(chance_threshold(100),COIN_RANGE)
        self.assertEqual(chance_threshold(100/8192),1<<19)
        self.assertEqual(chance_threshold(50),1<<31)
        self.assertEqual(chance_threshold(1e-20),1)
        for value in (True,-1,101,float('nan'),float('inf'),'1',None):
            with self.assertRaises(ValueError):chance_threshold(value)
        for value in (-1,101,float('nan'),True):
            with self.assertRaises(UserError):validate_options(replace(Options(),shiny_chance_percent=value))

    def test_wrapper_coin_boundaries_preserve_native_arguments_and_abi(self):
        for percent in (0,100,1,50,100/8192):
            threshold=chance_threshold(percent)
            for coin in sorted({0,MASK,max(0,min(MASK,threshold-1)),min(MASK,threshold)}):
                for trainer_context,shadow in ((False,False),(True,False),(True,True)):
                    m=Machine(_pid_wrapper(SECTION_RAM+32,threshold,trainers=trainer_context),SECTION_RAM+32,
                              (0xCAFE0000|(coin>>16),0xBEEF0000|(coin&0xFFFF)))
                    m.reg[3:8]=[0x8050AB00,1,7,0,0x12345678]
                    m.reg[30]=int(shadow)
                    m.write(PLAYER_POINTER,0x80510000);m.write(0x8051009C,0x2468ABCD)
                    before=m.reg.copy();link=m.lr
                    m.run()
                    expected_tid=0x2468ABCD if trainer_context and shadow else 0x12345678
                    expected=int(coin<threshold)
                    calls=[c for c in m.calls if c[0]==PID_GENERATOR]
                    self.assertEqual(calls,[(PID_GENERATOR,[before[3],1,7,expected,expected_tid])])
                    self.assertEqual(is_shiny(m.reg[3],expected_tid),bool(expected))
                    self.assertEqual(m.reg[1:3],before[1:3]);self.assertEqual(m.reg[13:],before[13:])
                    self.assertEqual(m.lr,link)
                    self.assertEqual(sum(c[0]==NATIVE_RNG for c in m.calls),0 if percent in (0,100) else 2)

    def test_ot_wrapper_aligns_only_unpurified_shadows_and_preserves_pid_return_and_abi(self):
        for shadow_id,purification,has_player in ((1,1000,True),(0,1000,True),(1,-100,True),(1,0,False)):
            m=Machine(_ot_wrapper(SECTION_RAM+32),SECTION_RAM+32)
            obj=0x8050AB00;m.reg[26]=obj
            for i in range(0x138):m.mem[obj+i]=0xA5
            m.write(obj+0xD8,shadow_id,2);m.write(obj+0xDC,purification)
            m.write(PLAYER_POINTER,0x80510000 if has_player else 0)
            m.write(0x8051009C,0x2468ABCD)
            original=bytes(m.mem[obj+i] for i in range(0x138))
            before=m.reg.copy()
            for r in range(26,32):m.write(m.reg[1]+8+(r-26)*4,0xCAFE0000+r)
            m.run(stop=OT_EXIT+4)
            expected=bytearray(original)
            if shadow_id and purification!=-100 and has_player:
                struct.pack_into('>I',expected,0x14,0x2468ABCD)
            self.assertEqual(bytes(m.mem[obj+i] for i in range(0x138)),expected)
            self.assertEqual(m.reg[3],before[3]);self.assertEqual(m.reg[1],before[1])
            self.assertEqual(m.reg[26:],[0xCAFE0000+r for r in range(26,32)])


ORIGINAL=Path(__file__).resolve().parents[1]/'game/sys/main.dol'


@unittest.skipUnless(ORIGINAL.is_file(),"requires user's original PAL DOL")
class ShinyCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=ORIGINAL.read_bytes()

    def test_disabled_identity_and_coexistence_with_gift_move_code(self):
        for gifts in ({},{'plusle':[33,53,94,0]},dict.fromkeys(('plusle','ho-oh','celebi-event','pikachu-event'),[33,53,94,0])):
            current,prior=patch_gift_moves(self.original,self.original,gifts)
            self.assertEqual(apply_shiny_rules(self.original,current,Options())[0],current)
            for percent in (0,1,100):
                options=replace(Options(),custom_shinies=True,seeded_shinies=False,shiny_chance_percent=percent)
                result,report=apply_shiny_rules(self.original,current,options)
                self.assertEqual(apply_shiny_rules(self.original,current,options)[0],result)
                self.assertEqual(len(report['hooks']),7)
                self.assertEqual(result[PID_GENERATOR-TEXT_TO_RAM:PID_GENERATOR-TEXT_TO_RAM+0x4B4],
                                 self.original[PID_GENERATOR-TEXT_TO_RAM:PID_GENERATOR-TEXT_TO_RAM+0x4B4])
                section=report['code_section'];base=section['offset']
                self.assertEqual(result[base:base+32],_arena_guard(section['reserved_end']))
                if gifts:self.assertEqual(result[base+32:len(current)],current[base+32:])
                self.assertEqual(next(s for s in parse_dol(result)['sections'] if s['name']=='text2')['size'],section['size'])
                allowed=report['allowed_changed_ranges']
                self.assertTrue(all(any(lo<=i<hi for lo,hi in allowed) for i,(a,b) in enumerate(zip(current,result)) if a!=b))

    def test_corrupt_call_header_native_predicate_and_existing_section_refused(self):
        options=replace(Options(),custom_shinies=True,seeded_shinies=False)
        for offset in (next(iter(PID_CALLS.values()))-TEXT_TO_RAM,0xE0,0x1289B8-0x3000,0x98):
            current=bytearray(self.original);current[offset]^=1
            with self.assertRaises(FormatError):apply_shiny_rules(self.original,bytes(current),options)

    def test_seeded_tables_are_the_reported_decisions_and_reuse_branch_is_untouched(self):
        options=replace(Options(),custom_shinies=True,shiny_chance_percent=37.5)
        for gifts in ({}, {'plusle': [33, 53, 94, 0]}):
            current,_=patch_gift_moves(self.original,self.original,gifts)
            result,report=apply_shiny_rules(self.original,current,options,seed="seeded-proof")
            self.assertEqual(result,apply_shiny_rules(self.original,current,options,seed="seeded-proof")[0])
            self.assertNotEqual(result,apply_shiny_rules(self.original,current,options,seed="other-seed")[0])
            section=report['code_section']
            def ram(address,size):
                start=section['offset']+address-section['address']
                return result[start:start+size]
            for table,key in (('trainer_slots','trainer_slots'),('shadows','shadows')):
                meta=report['status_tables'][table]
                flags=ram(meta['address'],meta['count'])
                self.assertEqual(list(flags),[int(report['seeded_decisions'][key][str(i)]) for i in range(meta['count'])])
            self.assertEqual(result[0x801FEC44-TEXT_TO_RAM:0x801FEC84-TEXT_TO_RAM],
                             current[0x801FEC44-TEXT_TO_RAM:0x801FEC84-TEXT_TO_RAM])
            for hook in report['hooks']:
                if hook['key']=='trainers':continue
                machine=Machine(ram(hook['wrapper_address'],128),hook['wrapper_address'])
                machine.reg[3:8]=[0x8050AB00,1,7,0,0x12345678]
                machine.run()
                expected=report['seeded_decisions']['specials'][hook['key']]
                self.assertEqual(is_shiny(machine.reg[3],0x12345678),expected)
            self.assertEqual(result[PID_GENERATOR-TEXT_TO_RAM:PID_GENERATOR-TEXT_TO_RAM+0x4B4],
                             self.original[PID_GENERATOR-TEXT_TO_RAM:PID_GENERATOR-TEXT_TO_RAM+0x4B4])
        corrupted=bytearray(self.original)
        corrupted[TRAINER_INDEX_HOOK-TEXT_TO_RAM]^=1
        with self.assertRaises(FormatError):apply_shiny_rules(self.original,bytes(corrupted),options,seed="seeded-proof")


if __name__=='__main__':unittest.main()
