"""Execute installed Fairy lookups inside actual retail algorithms.

These private-retail tests load authentic table bytes and follow the emitted
type hook. Only Pokémon input accessors are substituted for controlled inputs.
"""
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import parse_dol, parse_rel, u32
from orre_randomizer.engine.inspect_tables import rel_symbols
from orre_randomizer.engine.gift_move_hooks import branch
from orre_randomizer.fairy_runtime import (
    _CONVERSION_LAYOUTS, _PURIFICATION_LAYOUTS, _AI_SWITCH_LAYOUTS, _read, fairy_effectiveness,
    install_fairy_type, qualify_fairy_runtime,
)
from tests.test_fairy_move_effects import EffectMachine, add_code, native_calls
from tests.test_fairy_runtime import SOURCES


ROOT = Path(__file__).resolve().parents[1]
REL_SOURCES = {f'GXX{k}01': ROOT / f'build/xd-validation/{region}/common_rel'
               for k, region in (('P', 'eu'), ('E', 'us'), ('J', 'jp'))}


def prepare_lookup(machine, original, patched, game, original_rel=None):
    """Map real original chart storage and installed lookup/dual/score code."""
    layout = qualify_fairy_runtime(original, game)
    for role in ('matchup', 'dual', 'score'):
        row = layout['qualifications'][role]
        add_code(machine, _read(patched, row['address'], row['size']), row['address'])
    conversion = _CONVERSION_LAYOUTS[game]
    affinity_wrapper = native_calls(_read(patched, conversion['address'], conversion['size']),
                                    conversion['address'])[-1]
    add_code(machine, _read(patched, affinity_wrapper, 0x30), affinity_wrapper)
    arena = next(s for s in parse_dol(patched)['sections'] if s['name'] == 'text2')
    add_code(machine, _read(patched, arena['ram_address'], arena['size']), arena['ram_address'])
    machine.reg[13] = 0x80800000
    row = layout['qualifications']['matchup']
    original_lookup = _read(original, row['address'], row['size'])
    if game.startswith('GXX'):
        if original_rel is None:
            original_rel = REL_SOURCES[game].read_bytes()
        base = rel_symbols(original_rel, parse_rel(original_rel))[130]['offset']
        raw = original_rel[base:base + 18 * 48]
        pointer = 0x80500100
        # The qualified retail function's r13 reads bind the live REL symbols.
        count_read = u32(original_lookup, 0)
        table_read = next(u32(original_lookup, i) for i in range(0, len(original_lookup), 4)
                          if u32(original_lookup, i) & 0xffff0000 == 0x80cd0000)
        for word, address in ((count_read, 0x80500000), (table_read, pointer)):
            delta = word & 65535
            machine.write(machine.reg[13] + (delta - 65536 if delta & 32768 else delta), address)
        machine.write(0x80500000, 18)
        chart = [[int.from_bytes(raw[a * 48 + 12 + b * 2:a * 48 + 14 + b * 2], 'big')
                  for b in range(18)] for a in range(18)]
    else:
        high = next(u32(original_lookup, i) & 65535 for i in range(0, len(original_lookup), 4)
                    if u32(original_lookup, i) & 0xffff0000 == 0x3ca00000)
        low = next(u32(original_lookup, i) & 65535 for i in range(0, len(original_lookup), 4)
                   if u32(original_lookup, i) & 0xffff0000 == 0x38a50000)
        pointer = (high << 16) + (low - 65536 if low & 32768 else low)
        raw = _read(original, pointer, 18 * 44)
        count_read = u32(original_lookup, 0)
        delta = count_read & 65535
        machine.write(machine.reg[13] + (delta - 65536 if delta & 32768 else delta), 18)
        chart = [[int.from_bytes(raw[a * 44 + 8 + b * 2:a * 44 + 10 + b * 2], 'big')
                  for b in range(18)] for a in range(18)]
    for index, value in enumerate(raw):
        machine.write(pointer + index, value, 1)
    def affinity(a, b):
        result = fairy_effectiveness(a, b)
        return result if result is not None else chart[a][b] if a < 18 and b < 18 else 0
    return layout, affinity


@unittest.skipUnless(all(p.is_file() for p in (*SOURCES.values(), *REL_SOURCES.values())),
                     'requires all six private original DOL/REL pairs')
class InstalledFairyInteractions(unittest.TestCase):
    def test_switch_scan_uses_real_installed_dual_affinity_for_candidate_and_opponents(self):
        cases = (((16, 16), ((16, 16), (17, 17)), (2, 2)),
                 ((16, 16), ((16, 16), (17, 17)), (1, 2)),
                 ((19, 19), ((16, 16), (19, 19)), (2, 2)),
                 ((8, 19), ((16, 16), (19, 19)), (2, 3)))
        for game, source in SOURCES.items():
            original = source.read_bytes()
            patched = install_fairy_type(original, original, game)[0]
            row = _AI_SWITCH_LAYOUTS[game]
            raw = _read(patched, row['address'], row['size'])
            targets = native_calls(raw, row['address'])
            for candidate, opponents, categories in cases:
                for count in (0, 1, 2):
                    for bound in (18, 20):
                        payload = bytearray(raw)
                        struct.pack_into('>I', payload, row['bound_address'] - row['address'], 0x38000000 | bound)
                        adapter = 0x81640000
                        for i in range(0, len(payload), 4):
                            if u32(payload, i) == branch(row['address'] + i, targets[0], link=True):
                                struct.pack_into('>I', payload, i, branch(row['address'] + i, adapter, link=True))
                        machine = EffectMachine(bytes(payload), row['address'])
                        layout, affinity = prepare_lookup(machine, original, patched, game)
                        add_code(machine, struct.pack('>III', 0x7ca32b78, 0x38a00002,
                                 branch(adapter + 8, layout['qualifications']['dual']['address'])), adapter)
                        pokemon, score = 0x80610000, 0x80620000
                        for index, pair in enumerate((candidate, *opponents)):
                            for slot, value in enumerate(pair):
                                machine.write(pokemon + index * 0x100 + slot * 2, value, 2)
                        xd = game.startswith('GXX')
                        machine.reg[30 if xd else 15] = pokemon
                        machine.reg[24 if xd else 27] = pokemon
                        machine.reg[26 if xd else 29] = score
                        machine.reg[27 if xd else 30] = 0
                        machine.write(score, 41)
                        words = struct.unpack('>' + 'I' * (len(payload) // 4), payload)
                        counts = {word & 65535 for word in words if word & 0xffff0000 == 0x80010000}
                        array_offset = next(word & 65535 for word in words if word & 0xffff0000 == 0x39c10000)
                        for value in counts:
                            machine.write(machine.reg[1] + value, count)
                        for index in range(2):
                            machine.write(machine.reg[1] + array_offset + index * 4, pokemon + (index + 1) * 0x100)
                        machine.native_targets = set(targets[1:])
                        def native(target):
                            args = machine.reg[3:9].copy()
                            if target == targets[1]:
                                result = 1
                            elif target == targets[2]:
                                result = categories[(args[1] - pokemon) // 0x100 - 1]
                            elif target == targets[3]:
                                result = args[0] + 1
                            else:
                                result = 0
                            for register in (0, *range(3, 13)):
                                machine.reg[register] = 0xdead0000 + register
                            machine.reg[3] = result
                        machine.native = native
                        machine.run(stop=row['address'] + row['size'])
                        def super_effective(attack, pair):
                            effects = [affinity(attack, t) for t in pair]
                            return 0x43 not in effects and effects.count(0x41) > effects.count(0x42)
                        expected = 41 + sum(super_effective(attack, candidate) and super_effective(attack, opponents[i])
                                            for attack in range(bound) if attack != 9 for i in range(count)
                                            if categories[i] in (2, 3))
                        self.assertEqual(machine.read(score), expected,
                                         (game, candidate, opponents, categories, count, bound))

    def test_ai_scoring_executes_installed_chart_with_every_type_mode_and_mask(self):
        for game, source in SOURCES.items():
            original = source.read_bytes()
            patched = install_fairy_type(original, original, game)[0]
            machine = EffectMachine(b'', 0)
            layout, affinity = prepare_lookup(machine, original, patched, game)
            for kind in range(20):
                for mode in (0, 1):
                    for mask in (0, 1, 2):
                        machine.pc = layout['qualifications']['score']['address']
                        machine.lr = 0x80000000
                        machine.reg[3:6] = [kind, mode, mask]
                        stack, nonvolatile = machine.reg[1], machine.reg[13:].copy()
                        values = [affinity(kind, t) if mode else affinity(t, kind)
                                  for t in range(20) if t != 9]
                        low = sum(v in (0x42, 0x43) for v in values)
                        high = values.count(0x41)
                        effective_mask = mask if game.startswith('GXX') else 0
                        expected = ((-10 * low if effective_mask != 1 else 0) + (10 * high if effective_mask != 2 else 0)
                                    if mode else (10 * low if effective_mask != 2 else 0) - (10 * high if effective_mask != 1 else 0))
                        machine.run()
                        self.assertEqual(machine.reg[3], expected & 0xffffffff, (game, kind, mode, mask))
                        self.assertEqual((machine.reg[1], machine.reg[13:]), (stack, nonvolatile))

    def test_conversion2_executes_installed_affinity_and_keeps_empty_tail_and_guards(self):
        for game, source in SOURCES.items():
            original = source.read_bytes()
            patched = install_fairy_type(original, original, game)[0]
            row = _CONVERSION_LAYOUTS[game]
            payload = _read(patched, row['address'], row['size'])
            machine = EffectMachine(payload, row['address'])
            _, affinity = prepare_lookup(machine, original, patched, game)
            getters = native_calls(payload, row['address'])
            machine.native_targets = {getters[0]}
            for attack in range(20):
                for owned in ((0, 0), (19, 19), (14, 19), (3, 8)):
                    output = 0x80610000
                    machine.reg[3:6] = [0x80620000, attack, output]
                    machine.pc, machine.lr = row['address'], 0x80000000
                    machine.write(output - 4, 0x12345678)
                    machine.write(output + 18 * 4, 0x89abcdef)
                    def native(_target):
                        args = machine.reg[3:9].copy()
                        machine.reg[3] = int(args[1] in owned) if game.startswith('GXX') else owned[args[3]]
                    machine.native = native
                    stack, nonvolatile = machine.reg[1], machine.reg[13:].copy()
                    machine.run()
                    expected = [t for t in range(20) if t not in owned and affinity(attack, t) in (0x42, 0x43)]
                    self.assertEqual(machine.reg[3], len(expected), (game, attack, owned))
                    self.assertEqual([machine.read(output + i * 4) for i in range(18)],
                                     expected + [0xffffffff] * (18 - len(expected)))
                    self.assertEqual((machine.read(output - 4), machine.read(output + 72)),
                                     (0x12345678, 0x89abcdef))
                    self.assertEqual((machine.reg[1], machine.reg[13:]), (stack, nonvolatile))

    def test_purify_chamber_partial_rings_empty_centers_and_fairy_duplicates(self):
        scenarios = (((), None, False), ((), (19, 19), True),
                     (((19, 19),), None, False), (((19, 19),), None, True),
                     (((19, 19),), (19, 19), True),
                     (((19, 14), (8, 8)), (14, 14), True),
                     (((19, 14), (8, 8)), (19, 19), False),
                     (((19, 14), (8, 8), (16, 16), (10, 10)), (3, 3), True),
                     (((19, 14), (8, 8), (16, 16), (10, 10)), (19, 19), True))
        for game, row in _PURIFICATION_LAYOUTS.items():
            original = SOURCES[game].read_bytes()
            patched = install_fairy_type(original, original, game)[0]
            payload = _read(patched, row['address'], row['size'])
            targets = native_calls(payload, row['address'])
            for pairs, center, include in scenarios:
                machine = EffectMachine(payload, row['address'])
                machine.reg[3:5] = [0x80610000, int(include)]
                machine.reg[13] = 0x80800000
                for i in range(0, 0x50, 4):
                    word = u32(payload, i)
                    if word & 0xffff0000 == 0x80ad0000:
                        delta = word & 65535
                        machine.write(machine.reg[13] + (delta - 65536 if delta & 32768 else delta), 0x80500000)
                machine.write(0x80500000, 18)
                machine.native_targets = set(targets)
                buffers = []
                def native(target):
                    if target == targets[0]:
                        address, value, count = machine.reg[3:6]
                        self.assertEqual((value, count), (0, 20))
                        buffers.append(address)
                        for i in range(24):
                            machine.write(address + i, 0 if i < 20 else 0xa5, 1)
                        return
                    slot = (machine.reg[3] - 0x80610000) // 0xc4
                    pair = center if slot == 4 else pairs[slot] if slot < len(pairs) else None
                    if target == targets[1]:
                        machine.reg[3] = int(pair is not None)
                    elif target == targets[3]:
                        self.assertIsNotNone(pair)
                        machine.reg[3] = pair[machine.reg[4]]
                machine.native = native
                stack, nonvolatile = machine.reg[1], machine.reg[13:].copy()
                machine.run()
                flattened = [t for pair in (*pairs, *((center,) if include and center else ())) for t in set(pair)]
                self.assertEqual(machine.reg[3], int(len(flattened) == len(set(flattened))),
                                 (game, pairs, center, include))
                self.assertEqual(bytes(machine.read(buffers[0] + i, 1) for i in range(20, 24)), b'\xa5' * 4)
                self.assertEqual(machine.read(0x80500000), 18)
                self.assertEqual((machine.reg[1], machine.reg[13:]), (stack, nonvolatile))


if __name__ == '__main__':
    unittest.main()
