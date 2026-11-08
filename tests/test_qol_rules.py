"""Execute emitted QoL PowerPC instructions and qualify real regional patches."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import math
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.dol_regions import LAYOUTS
from orre_randomizer.engine.gift_move_hooks import patch_gift_moves
from orre_randomizer.engine.shiny_rules import apply_shiny_rules
from orre_randomizer.engine.qol_rules import (
    CONTRACTS, HOOKS, _experience_stub, _purification_stub,
    apply_qol_rules, experience_numerator)
from orre_randomizer.options import Options

MASK = 0xFFFFFFFF


def single(value):
    return struct.unpack('>f', struct.pack('>f', value))[0]


class HookMachine:
    """Small independent PPC decoder; no function substitutes or patched results."""
    def __init__(self, payload, address):
        self.memory = {address + i: byte for i, byte in enumerate(payload)}
        self.pc = address
        self.reg = [0x12340000 + i for i in range(32)]
        self.fp = [float(i) for i in range(32)]
        self.lr = 0x80005500
        self.cr0 = [False, False, False, False]

    def load(self, address, width):
        return int.from_bytes(bytes(self.memory.get(address + i, 0) for i in range(width)), 'big')

    def run(self, stop):
        for _ in range(100):
            if self.pc == stop:
                return
            pc = self.pc
            word = self.load(pc, 4)
            self.pc += 4
            op = word >> 26
            rd, ra, rb = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
            imm = word & 0xFFFF
            signed = imm - 65536 if imm & 32768 else imm
            xo = (word >> 1) & 1023
            if op in (14, 15):
                self.reg[rd] = ((self.reg[ra] if ra else 0) + (signed << (16 if op == 15 else 0))) & MASK
            elif op == 24:
                self.reg[ra] = self.reg[rd] | imm
            elif op == 40:
                self.reg[rd] = self.load((self.reg[ra] + signed) & MASK, 2)
            elif op in (10, 11):
                left = self.reg[ra]
                if op == 11 and left & 0x80000000:
                    left -= 0x100000000
                right = imm if op == 10 else signed
                self.cr0 = [left < right, left > right, left == right, False]
            elif op == 31 and xo == 235:
                self.reg[rd] = (self.reg[ra] * self.reg[rb]) & MASK
            elif op == 31 and xo == 266:
                self.reg[rd] = (self.reg[ra] + self.reg[rb]) & MASK
            elif op == 31 and xo == 459:
                self.reg[rd] = self.reg[ra] // self.reg[rb]
            elif op == 31 and xo == 444:
                self.reg[ra] = self.reg[rd] | self.reg[rb]
            elif op == 48:
                address = (self.reg[ra] + signed) & MASK
                self.fp[rd] = struct.unpack('>f', self.load(address, 4).to_bytes(4, 'big'))[0]
            elif op == 63 and xo in (0, 32):
                assert (word >> 23) & 7 == 0
                left, right = self.fp[ra], self.fp[rb]
                self.cr0 = [left < right, left > right, left == right, math.isnan(left) or math.isnan(right)]
            elif op == 63 and xo == 72:
                self.fp[rd] = self.fp[rb]
            elif op == 59 and ((word >> 1) & 31) == 25:
                rc = (word >> 6) & 31
                self.fp[rd] = single(self.fp[ra] * self.fp[rc])
            elif op == 59 and ((word >> 1) & 31) == 21:
                self.fp[rd] = single(self.fp[ra] + self.fp[rb])
            elif op == 16:
                bo, bi = (word >> 21) & 31, (word >> 16) & 31
                assert bo in (4, 12) and bi < 4
                if self.cr0[bi] == (bo == 12):
                    offset = word & 0xFFFC
                    self.pc = pc + (offset - 65536 if offset & 32768 else offset)
            elif op == 18:
                assert word & 3 == 0  # no LR mutation or absolute jump
                offset = word & 0x03FFFFFC
                self.pc = pc + (offset - (1 << 26) if offset & (1 << 25) else offset)
            else:
                raise AssertionError(f'unsupported {word:08x} at {pc:08x}')
        raise AssertionError('hook failed to return to native continuation')


class QualityOfLifeHookTests(unittest.TestCase):
    def test_exp_instruction_execution_rounding_and_live_registers(self):
        for region in LAYOUTS:
            for rate in (0.25, 0.33, 0.5, 1, 1.25, 2.5, 5):
                for award in (1, 2, 3, 17, 255, 12291, 65535, 65536, MASK):
                    with self.subTest(region=region.game_id, rate=rate, award=award):
                        address = region.section_ram + 32
                        continuation = CONTRACTS[region.game_id]['experience'][0] + HOOKS['experience'][0] + 4
                        m = HookMachine(_experience_stub(address, continuation, experience_numerator(rate)), address)
                        m.reg[16] = award
                        before, fp_before, lr = m.reg.copy(), m.fp.copy(), m.lr
                        m.run(continuation)
                        expected = max(1, int(math.floor(min(award, 65535) * rate + 0.5)))
                        self.assertEqual(m.reg[16], expected)
                        self.assertEqual(m.reg[3], before[23])
                        self.assertEqual(m.lr, lr)
                        self.assertEqual(m.fp, fp_before)
                        self.assertEqual([v for i, v in enumerate(m.reg) if i not in (3, 11, 12, 16)],
                                         [v for i, v in enumerate(before) if i not in (3, 11, 12, 16)])

    def test_purification_instructions_scale_only_reductions_and_native_clamp(self):
        for region in LAYOUTS:
            for multiplier in (1, 2, 3, 10):
                for gauge, delta in ((20, -1), (20, -30), (0, -1), (20, 1), (20, 0), (0.5, -0.125)):
                    with self.subTest(region=region.game_id, multiplier=multiplier, gauge=gauge, delta=delta):
                        address = region.section_ram + 32
                        continuation = CONTRACTS[region.game_id]['purification'][0] + HOOKS['purification'][0] + 4
                        m = HookMachine(_purification_stub(address, continuation, multiplier), address)
                        # Unmodified retail clamp following the displaced addition:
                        # lfs f0,-0x66b0(r2); fcmpo cr0,f1,f0; bge +8; fmr f1,f0.
                        clamp = bytes.fromhex('c0029950fc01004040800008fc200090')
                        m.memory.update({continuation + i: b for i, b in enumerate(clamp)})
                        zero = (m.reg[2] - 0x66B0) & MASK
                        m.memory.update({zero + i: 0 for i in range(4)})
                        m.fp[0], m.fp[31] = single(gauge), single(delta)
                        before, fp_before, lr = m.reg.copy(), m.fp.copy(), m.lr
                        m.run(continuation + len(clamp))
                        self.assertEqual(m.fp[1], max(0, gauge + delta * (multiplier if delta < 0 else 1)))
                        self.assertEqual(m.lr, lr)
                        self.assertEqual(m.reg[:12], before[:12])
                        self.assertEqual(m.reg[13:], before[13:])
                        self.assertEqual(m.fp[2:31], fp_before[2:31])

    def test_multiplier_validation_and_neutral_byte_identity(self):
        for value in (True, None, '2', float('nan'), float('inf'), 0.2499, 5.0001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                experience_numerator(value)
        source, current = b'original', b'current with unrelated patches'
        self.assertEqual(apply_qol_rules(source, current, SimpleNamespace())[0], current)
        self.assertFalse(apply_qol_rules(source, current, SimpleNamespace())[1]['enabled'])
        for value in (False, 0, 11, 1.0, '2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply_qol_rules(source, current, SimpleNamespace(purification_multiplier=value))


ROOT = Path(__file__).resolve().parents[1]
DOLS = {'GC6P01': ROOT / 'game/sys/main.dol',
        'GC6E01': ROOT / 'build/region-compat-2026-11-02/dol-research/usa-main.dol',
        'GC6J01': ROOT / 'build/region-compat-2026-11-02/dol-research/japan-main.dol'}


@unittest.skipUnless(all(path.is_file() for path in DOLS.values()), "requires original regional local DOLs")
class RegionalQualityOfLifePatchTests(unittest.TestCase):
    def test_each_exact_region_reproduces_and_changes_only_declared_ranges(self):
        for game_id, path in DOLS.items():
            original = path.read_bytes()
            options = SimpleNamespace(experience_multiplier=2.5, purification_multiplier=3)
            result, report = apply_qol_rules(original, original, options)
            self.assertEqual((result, report), apply_qol_rules(original, original, options))
            self.assertEqual(report['game_id'], game_id)
            self.assertTrue(report['outside_whitelist_unchanged'])
            ranges = report['allowed_changed_ranges']
            self.assertTrue(all(a == b or any(lo <= i < hi for lo, hi in ranges)
                                for i, (a, b) in enumerate(zip(original, result))))
            self.assertEqual(len(report['hooks']), 2)
            for hook in report['hooks']:
                # Next native instruction and all original code after it stay intact.
                continuation = hook['continuation'] - 0x80003000
                self.assertEqual(result[continuation:continuation + 32], original[continuation:continuation + 32])

    def test_composes_with_existing_gift_and_seeded_shiny_reservation(self):
        for region in LAYOUTS:
            original = DOLS[region.game_id].read_bytes()
            current = patch_gift_moves(original, original, {'pikachu-event': [33, 53, 94, 0]})[0]
            current, shiny = apply_shiny_rules(original, current,
                replace(Options.none(), custom_shinies=True, seeded_shinies=True, shiny_chance_percent=25), seed='qol-composition')
            result, report = apply_qol_rules(original, current,
                SimpleNamespace(experience_multiplier=5, purification_multiplier=10))
            self.assertEqual(report['code_section']['previous_size'], shiny['code_section']['size'])
            section = report['code_section']['offset']
            self.assertEqual(result[section + 32:len(current)], current[section + 32:])
            self.assertEqual(apply_qol_rules(original, result, SimpleNamespace())[0], result)

    def test_bad_preimages_headers_and_existing_reservations_are_rejected(self):
        for game_id, path in DOLS.items():
            original = path.read_bytes()
            options = SimpleNamespace(experience_multiplier=2, purification_multiplier=2)
            for offset in (0x10, CONTRACTS[game_id]['experience'][0] - 0x80003000,
                           CONTRACTS[game_id]['purification'][0] - 0x80003000):
                changed = bytearray(original)
                changed[offset] ^= 1
                with self.subTest(game_id=game_id, offset=offset), self.assertRaises(FormatError):
                    apply_qol_rules(original, bytes(changed), options)
            changed, _ = apply_qol_rules(original, original, options)
            with self.assertRaises(FormatError):
                apply_qol_rules(original, changed, options)


if __name__ == '__main__':
    unittest.main()
