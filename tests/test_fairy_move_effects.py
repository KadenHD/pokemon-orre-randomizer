"""Emitted and actual retail PowerPC mechanics, without animation assumptions."""
from __future__ import annotations

import hashlib
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.fairy_move_effects import (
    DISARMING_VOICE, DRAINING_KISS, _QUALIFIED, _drain_stub, _substitute_stub,
    drain_amount, install_fairy_move_effects, qualify_fairy_move_effects,
)
from orre_randomizer.fairy_runtime import _read, install_fairy_type
from tests.test_deoxys_meteorite import ItemMachine, MASK
from tests.test_fairy_runtime import SOURCES


class EffectMachine(ItemMachine):
    """Native arithmetic, carry and record-bit semantics used by these scripts."""
    def run(self, stop=None):
        stop = self.lr if stop is None else stop
        carry = 0
        for _ in range(getattr(self, 'max_steps', 10000)):
            if self.pc == stop: return
            w = self.code[self.pc]; pc = self.pc; self.pc += 4
            op, rs, ra, rb = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31
            imm = w & 65535; signed = imm - 65536 if imm & 32768 else imm
            xo = w >> 1 & 1023
            result_register = None
            if w == 0x7C0802A6: self.reg[0] = self.lr
            elif w == 0x7C0803A6: self.lr = self.reg[0]
            elif w == 0x7C0102A6: self.reg[0] = getattr(self, 'xer', 0)
            elif w == 0x7C0103A6: self.xer = self.reg[0]
            elif w == 0x7C0902A6: self.reg[0] = getattr(self, 'ctr', 0)
            elif w == 0x7C0903A6: self.ctr = self.reg[0]
            elif w == 0x4E800020: self.pc = self.lr
            elif op in (14, 15): self.reg[rs] = ((self.reg[ra] if ra else 0) + (signed << (16 if op == 15 else 0))) & MASK
            elif op == 7: self.reg[rs] = self.reg[ra] * signed & MASK
            elif op in (24, 25): self.reg[ra] = self.reg[rs] | (imm << (16 if op == 25 else 0))
            elif op in (32, 34, 40): self.reg[rs] = self.read((self.reg[ra] + signed) & MASK, {32:4,34:1,40:2}[op])
            elif op in (36, 37, 38, 44):
                address = (self.reg[ra] + signed) & MASK
                self.write(address, self.reg[rs], 1 if op == 38 else 2 if op == 44 else 4)
                if op == 37: self.reg[ra] = address
            elif op in (46, 47):
                address = (self.reg[ra] + signed) & MASK
                for i in range(rs,32):
                    if op == 46: self.reg[i] = self.read(address + 4*(i-rs))
                    else: self.write(address + 4*(i-rs), self.reg[i])
            elif op in (10, 11):
                value = self.reg[ra]
                if op == 11 and value & 0x80000000: value -= 0x100000000
                compare = imm if op == 10 else signed
                self.cr = (value < compare, value == compare)
            elif op == 31 and xo in (0,32):
                left,right=self.reg[ra],self.reg[rb]
                if xo == 0:
                    left -= 0x100000000 if left & 0x80000000 else 0
                    right -= 0x100000000 if right & 0x80000000 else 0
                self.cr=(left < right,left == right)
            elif op == 31 and xo == 40: self.reg[rs] = (self.reg[rb] - self.reg[ra]) & MASK; result_register=rs
            elif op == 31 and xo == 104: self.reg[rs] = -self.reg[ra] & MASK; result_register=rs
            elif op == 31 and xo == 202:
                value = self.reg[ra] + carry; self.reg[rs] = value & MASK; carry=int(value > MASK); result_register=rs
            elif op == 31 and xo == 266: self.reg[rs] = (self.reg[ra] + self.reg[rb]) & MASK; result_register=rs
            elif op == 31 and xo == 151: self.write((self.reg[ra] + self.reg[rb]) & MASK, self.reg[rs])
            elif op == 31 and xo == 23: self.reg[rs] = self.read((self.reg[ra] + self.reg[rb]) & MASK)
            elif op == 31 and xo == 279: self.reg[rs] = self.read((self.reg[ra] + self.reg[rb]) & MASK, 2)
            elif op == 31 and xo == 183:
                address = (self.reg[ra] + self.reg[rb]) & MASK
                self.write(address, self.reg[rs])
                self.reg[ra] = address
            elif op == 31 and xo == 87: self.reg[rs] = self.read((self.reg[ra] + self.reg[rb]) & MASK, 1)
            elif op == 31 and xo == 215: self.write((self.reg[ra] + self.reg[rb]) & MASK, self.reg[rs], 1)
            elif op == 31 and xo == 19:
                # mfcr: these contract functions only compare through CR0.
                lt, eq = self.cr
                self.reg[rs] = (int(lt) << 31) | (int(not lt and not eq) << 30) | (int(eq) << 29)
            elif op == 31 and xo == 144:
                if w >> 12 & 0x80:
                    self.cr = (bool(self.reg[rs] & 0x80000000), bool(self.reg[rs] & 0x20000000))
            elif op == 31 and xo == 444: self.reg[ra] = self.reg[rs] | self.reg[rb]; result_register=ra
            elif op == 31 and xo == 824:
                value=self.reg[rs]; value -= 0x100000000 if value & 0x80000000 else 0
                self.reg[ra] = value >> rb & MASK
                carry = int(value < 0 and bool(value & ((1 << rb) - 1))); result_register=ra
            elif op == 21:
                shift,mb,me=w>>11&31,w>>6&31,w>>1&31
                mask=sum(1 << (31-i) for i in range(32) if (mb<=i<=me if mb<=me else i>=mb or i<=me))
                value=self.reg[rs]
                self.reg[ra]=((value<<shift|value>>(32-shift) if shift else value)&MASK)&mask
                result_register=ra
            elif op == 16:
                bo,bi=w>>21&31,w>>16&31
                condition=self.cr[0] if bi==0 else self.cr[1] if bi==2 else not any(self.cr)
                if bo==12 and condition or bo==4 and not condition:self.pc=pc+(signed&~3)
            elif op == 18:
                delta=w&0x3FFFFFC; delta-=0x4000000 if delta&0x2000000 else 0
                target=pc+delta
                if w&1:self.lr=pc+4
                if target in getattr(self,'native_targets',()):self.native(target);self.pc=self.lr
                else:self.pc=target
            else:raise AssertionError(f'Unsupported effect instruction {w:08x} at {pc:08x}')
            if result_register is not None and w & 1:
                value=self.reg[result_register]; self.cr=(bool(value&0x80000000),value==0)
        raise AssertionError('Native effect contract did not terminate')


ADDRESS, SITE, MOVE = 0x81600000, 0x80200000, 0x80610000


def add_code(machine, payload, address):
    machine.code.update({address+i: int.from_bytes(payload[i:i+4],'big') for i in range(0,len(payload),4)})


def native_calls(payload, address):
    result=[]
    for i in range(0,len(payload),4):
        word=int.from_bytes(payload[i:i+4],'big')
        if word&0xFC000003 == 0x48000001:
            delta=word&0x3FFFFFC;delta-=0x4000000 if delta&0x2000000 else 0
            target=address+i+delta
            if target not in result:result.append(target)
    return result


def set_script(machine, payload, script):
    machine.reg[13]=0x80800000;slots=[]
    for i in range(0,len(payload),4):
        word=int.from_bytes(payload[i:i+4],'big')
        if word>>26==32 and word>>16&31==13:
            delta=word&65535;delta-=65536 if delta&32768 else 0
            slot=(machine.reg[13]+delta)&MASK
            machine.write(slot,script);slots.append(slot)
    return slots


class FairyEffectContracts(unittest.TestCase):
    def test_modern_75_percent_rounding_uses_actual_native_hp_amount(self):
        for damage in range(65536):
            self.assertEqual(drain_amount(damage), max(1,(damage*3+2)//4))
        for invalid in (-1,65536,True,1.5,None):
            with self.assertRaises(ValueError):drain_amount(invalid)
        self.assertEqual([drain_amount(n) for n in range(1,9)],[1,2,2,3,4,5,5,6])

    def test_emitted_kiss_fraction_and_exact_legacy_arithmetic_execute_in_both_abis(self):
        for xd in (False,True):
            legacy=bytes.fromhex('7c600e707c000194'+('7c8000d1408200083880ffff' if xd else '7ce000d14082000838e0ffff'))
            for move in (1,72,138,DRAINING_KISS,375,377,0x10178):
                for damage in (0,1,2,3,4,5,6,7,8,11,101,1023,65535):
                    machine=EffectMachine(_drain_stub(ADDRESS,SITE,xd=xd),ADDRESS)
                    add_code(machine,legacy,SITE);add_code(machine,bytes.fromhex('4e800020'),SITE+20)
                    machine.reg[3],machine.reg[31]=damage,MOVE;machine.write(MOVE+4,move,2)
                    sp,lr=machine.reg[1],machine.lr;before=machine.reg.copy()
                    machine.run()
                    expected=drain_amount(damage) if move&65535==DRAINING_KISS else max(1,damage//2)
                    self.assertEqual(machine.reg[4 if xd else 7],-expected&MASK,(xd,move,damage))
                    self.assertEqual(machine.reg[3],damage)
                    self.assertEqual((machine.reg[1],machine.lr),(sp,lr))
                    self.assertEqual(machine.reg[13:],before[13:])

    def test_voice_bypasses_hp_branch_without_removing_substitute_or_affecting_other_moves(self):
        for register in (25,30):
            row={'move_register':register,'native_continuation':SITE,'native_no_substitute':SITE+16}
            for move in (0,33,129,DISARMING_VOICE,DRAINING_KISS,0x10177):
                for hp in (0,1,90):
                    machine=EffectMachine(_substitute_stub(ADDRESS,row),ADDRESS)
                    add_code(machine,bytes.fromhex('386000004e800020'),SITE)
                    add_code(machine,bytes.fromhex('386000014e800020'),SITE+16)
                    machine.reg[register]=move;machine.cr=(False,hp==0);machine.write(MOVE,hp,2)
                    machine.run()
                    self.assertEqual(machine.reg[3],int(hp==0 or move&65535==DISARMING_VOICE))
                    self.assertEqual(machine.read(MOVE,2),hp)

    def test_disabled_mechanics_are_identity_without_qualification(self):
        source=b'current';result,report=install_fairy_move_effects(b'',source,'?',enabled=False)
        self.assertIs(result,source);self.assertFalse(report['enabled'])


@unittest.skipUnless(all(path.is_file() for path in SOURCES.values()),'requires all six private retail DOL inputs')
class FairyRetailEffectContracts(unittest.TestCase):
    def test_all_six_native_hooks_compose_without_duplicate_arenas_or_unrelated_changes(self):
        for game,path in SOURCES.items():
            original=path.read_bytes();digest=hashlib.sha256(original).hexdigest()
            before,_,_=install_fairy_type(original,original,game)
            result,report=install_fairy_move_effects(original,before,game)
            self.assertEqual(len(report['hooks']),2)
            arena=next(s for s in parse_dol(before)['sections'] if s['name']=='text2')
            self.assertEqual(result[arena['offset']+32:len(before)],before[arena['offset']+32:])
            row=qualify_fairy_move_effects(original,game)
            for command in row['commands'].values():
                self.assertEqual(_read(result,command['address'],command['size']),_read(original,command['address'],command['size']))
            with self.assertRaises(FormatError):install_fairy_move_effects(original,result,game)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)

    def test_actual_native_ooze_ability_branch_selects_its_negation_only_for_ability64(self):
        for game,path in SOURCES.items():
            original=path.read_bytes();row=qualify_fairy_move_effects(original,game)
            command=row['commands']['30'];payload=_read(original,command['address'],command['size'])
            tail=row['drain_script_tail'];script=MOVE+0x1000
            for ability in (0,43,64,65):
                machine=EffectMachine(payload,command['address']);slots=set_script(machine,payload,script)
                for i,value in enumerate(_read(original,tail['address']+10,7)):machine.write(script+i,value,1)
                targets=native_calls(payload,command['address']);xd=game.startswith('GXX');state={'pc':script}
                machine.native_targets=set(targets)
                def native(target):
                    index=targets.index(target)
                    args=machine.reg[3:9].copy();result=0
                    if xd:
                        if index==0:result=script
                        elif index==1:self.assertEqual(args[0],0x12);result=MOVE+0x2000
                        elif index==2:result=ability
                        elif index==3:result=0 # no Mold Breaker suppression
                        elif index==5:state['pc']=args[0]
                        elif index==6:state['pc']+=args[0]
                    else:
                        if index==0:self.assertEqual(args[0],0x12);result=MOVE+0x2000
                        elif index==1:result=ability
                    machine.reg[3]=result
                machine.native=native;machine.run()
                expected=tail['ooze_negation_target'] if ability==64 else script+7
                self.assertEqual(state['pc'] if xd else machine.read(slots[0]),expected,(game,ability))

    def test_actual_native_ooze_damage_negation_preserves_the_whole_75_percent_amount(self):
        for game,path in SOURCES.items():
            original=path.read_bytes();row=qualify_fairy_move_effects(original,game)
            command=row['commands']['128'];payload=_read(original,command['address'],command['size'])
            for removed in (1,2,5,6,101,65535):
                amount=drain_amount(removed);machine=EffectMachine(payload,command['address'])
                script=MOVE+0x1000;set_script(machine,payload,script);machine.write(script+1,0,1)
                targets=native_calls(payload,command['address']);machine.native_targets=set(targets)
                xd=game.startswith('GXX');written=[]
                def native(target):
                    index=targets.index(target);args=machine.reg[3:9].copy();result=0
                    if xd:
                        if index==0:result=script
                        elif index==1:result=MOVE+0x2000
                        elif index==2:result=MOVE
                        elif index==3:result=-amount&MASK
                        elif index==4:result=MOVE+0x3000
                        elif index==5:result=65535
                        elif index==6:written.append(args[1])
                    else:
                        if index==0:result=MOVE+0x2000
                        elif index==1:result=MOVE if args[2]==0xD9 else 65535
                        elif index==2:result=-amount&MASK
                        elif index==3:result=MOVE+0x3000
                        elif index==4:written.append(args[4])
                    machine.reg[3]=result
                machine.native=native;machine.run()
                self.assertEqual(written,[amount],(game,removed))


if __name__=='__main__':unittest.main()
