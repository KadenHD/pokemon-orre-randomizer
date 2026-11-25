"""Reversible regional projection codes and isolated launch settings."""
import tempfile
import struct
import json
from pathlib import Path
import unittest

from orre_randomizer.play_display import (acceleration_target, display_mode,
    configure_projection, projection_entries, PROJECTIONS, PATCH_NAME,
    _bounds_adapter, _background_entries, _flash_entries, _menu_camera_entries, FLASH_SCRATCH)
from orre_randomizer._display_regions import RENDER_PASSES, WINDOW_BACKGROUNDS, FLASH_BACKGROUNDS, MENU_CAMERAS


RETAIL = json.loads((Path(__file__).parent / 'fixtures/display_revision0.json').read_text('utf-8'))


def single(value):
    return struct.unpack('>f', struct.pack('>f', value))[0]


def branch_destination(address, word):
    displacement = word & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return displacement if word & 2 else address + displacement


def execute_stub(test, code, pc, registers, floats, memory, lr, *, conditions=None, stores=None, reads=None):
    """Independent PPC32 subset; execute emitted words, stopping at native code."""
    visited = []
    conditions = [0] * 8 if conditions is None else conditions
    ctr = 0

    def comparison(field, left, right):
        conditions[field] = 8 if left < right else 4 if left > right else 2

    def signed(value):
        return value - 0x100000000 if value & 0x80000000 else value

    for _ in range(512):
        if pc not in code:
            return pc, lr, visited
        visited.append(pc)
        word = code[pc]
        if word == 0x4E800020:
            return lr, lr, visited
        opcode = word >> 26
        target, ra = (word >> 21) & 31, (word >> 16) & 31
        rb, rc = (word >> 11) & 31, (word >> 6) & 31
        displacement = word & 0xFFFF
        if displacement & 0x8000:
            displacement -= 0x10000
        if opcode == 32:  # lwz
            address = (registers[ra] if ra else 0) + displacement
            if reads is not None:
                reads.append(address)
            registers[target] = memory[address]
        elif opcode == 42:  # lha, big-endian halfword within the word fixture
            address = (registers[ra] if ra else 0) + displacement
            value = memory[address & ~3] >> (0 if address & 2 else 16) & 0xFFFF
            registers[target] = (value if value < 0x8000 else value - 0x10000) & 0xFFFFFFFF
        elif opcode in (14, 15):  # addi / addis (including li / lis)
            immediate = displacement << (16 if opcode == 15 else 0)
            registers[target] = ((registers[ra] if ra else 0) + immediate) & 0xFFFFFFFF
        elif opcode == 27:  # xoris
            registers[ra] = registers[target] ^ ((word & 0xFFFF) << 16)
        elif opcode == 24:  # ori
            registers[ra] = registers[target] | (word & 0xFFFF)
        elif opcode == 21:  # rlwinm (including slwi)
            shift, first, last = rb, (word >> 6) & 31, (word >> 1) & 31
            mask = sum(1 << (31 - bit) for bit in range(32)
                       if (first <= bit <= last if first <= last else bit >= first or bit <= last))
            rotated = ((registers[target] << shift) | (registers[target] >> (32 - shift))) & 0xFFFFFFFF
            registers[ra] = rotated & mask
            test.assertFalse(word & 1, 'The display shift must leave condition flags intact')
        elif opcode == 31 and (word >> 1) & 0x3FF == 444:  # or / mr / or.
            registers[ra] = registers[target] | registers[rb]
            if word & 1:
                comparison(0, signed(registers[ra]), 0)
        elif opcode in (10, 11):  # cmplwi / cmpwi
            field = (word >> 23) & 7
            left = signed(registers[ra]) if opcode == 11 else registers[ra]
            comparison(field, left, displacement if opcode == 11 else word & 0xFFFF)
        elif opcode == 31 and (word >> 1) & 0x3FF == 0:  # cmpw
            comparison((word >> 23) & 7, signed(registers[ra]), signed(registers[rb]))
        elif opcode == 31 and (word >> 1) & 0x3FF == 32:  # cmplw (unsigned addresses)
            comparison((word >> 23) & 7, registers[ra], registers[rb])
        elif opcode == 31 and (word >> 1) & 0x3FF == 467:  # mtspr / mtctr
            spr = (word >> 16) & 31 | (word >> 6) & 0x3E0
            test.assertEqual(spr, 9, 'The adapter may only write CTR')
            ctr = registers[target] & 0xFFFFFFFF
        elif opcode == 31 and (word >> 1) & 0x3FF == 266:  # add
            registers[target] = (registers[ra] + registers[rb]) & 0xFFFFFFFF
            test.assertFalse(word & 1, 'The display addition must leave condition flags intact')
        elif opcode == 31 and (word >> 1) & 0x3FF == 491:  # divw (truncate toward zero)
            left, right = signed(registers[ra]), signed(registers[rb])
            test.assertNotEqual(right, 0)
            quotient = abs(left) // abs(right)
            registers[target] = (-quotient if (left < 0) != (right < 0) else quotient) & 0xFFFFFFFF
            test.assertFalse(word & 1, 'The display division must leave condition flags intact')
        elif opcode == 16:  # bc / bdnz
            option, bit = (word >> 21) & 31, (word >> 16) & 31
            test.assertIn(option, (4, 12, 16))
            if option == 16:
                ctr = (ctr - 1) & 0xFFFFFFFF
                take_branch = ctr != 0
            else:
                condition = bool(conditions[bit // 4] & (8 >> (bit % 4)))
                take_branch = condition == (option == 12)
            if take_branch:
                if word & 1:
                    lr = pc + 4
                pc = (displacement & ~3) if word & 2 else pc + (displacement & ~3)
                continue
        elif opcode in (36, 44):  # stw / sth, signed D-form offset
            address = ((registers[ra] if ra else 0) + displacement) & 0xFFFFFFFF
            size = 4 if opcode == 36 else 2
            value = registers[target] & (0xFFFFFFFF if size == 4 else 0xFFFF)
            memory[address] = value
            if stores is not None:
                stores.append((address, value, size))
        elif opcode in (48, 52):
            address = (registers[ra] if ra else 0) + displacement
            if opcode == 48:
                if reads is not None:
                    reads.append(address)
                floats[target] = memory[address]
            else:
                memory[address] = single(floats[target])
        elif opcode == 59:
            test.assertFalse(word & 1, 'The adapter must not alter condition flags')
            operation = word & 0x3F
            if operation == 0x28:
                result = floats[ra] - floats[rb]
            elif operation == 0x2A:
                result = floats[ra] + floats[rb]
            elif operation == 0x32:
                result = floats[ra] * floats[rc]
            else:
                test.fail(f'Unexpected single-precision instruction {word:08x}')
            floats[target] = single(result)
        elif opcode == 18:
            if word & 1:
                lr = pc + 4
            pc = branch_destination(pc, word)
            continue
        else:
            test.fail(f'Unexpected display instruction {word:08x}')
        pc += 4
    test.fail('Emitted display stub did not terminate')


def native_ortho(left, right):
    width = single(right - left)
    return [single(2 / width), 0., 0., single(-single(right + left) / width),
            0., -1 / 240, 0., 1., 0., 0., -.5, 0., 0., 0., 0., 1.]


def patched_ortho(test, game_id, left, right):
    """Run the real global matrix-return hook after a native matrix calculation."""
    matrix = native_ortho(left, right)
    registers = [0x10000 + index * 0x100 for index in range(32)]
    registers[2], registers[3] = PROJECTIONS[game_id][1], 0x81000000
    memory = {registers[3] + index * 4: value for index, value in enumerate(matrix)}
    memory[PROJECTIONS[game_id][2]] = .75
    code = {address: value for address, value, _ in projection_entries(game_id, True)}
    execute_stub(test, code, 0x80005310, registers, [0.] * 32, memory, 0x81234560)
    return [memory[registers[3] + index * 4] for index in range(16)]


def background_state(game_id, call, x, *, position=0, size=(640, 480), rotation=0):
    """Two different sprite records catch accidental use of the wrong pointer."""
    callee, textured, _ = WINDOW_BACKGROUNDS[game_id]
    registers = [0x11000000 + index * 0x1000 for index in range(32)]
    registers[26], registers[31] = 0x8100A000, 0x8100B000
    sprite_register = 31 if callee is None and call == textured else 26
    x_register = 0 if callee is None else 3
    registers[x_register] = x & 0xFFFFFFFF
    memory = {base + offset: 0x12340000 + offset
              for base in (registers[26], registers[31]) for offset in range(0, 0x90, 4)}
    for base in (registers[26], registers[31]):
        memory.update({base + 0x50: 1, base + 0x54: (64 << 16) | 64, base + 0x70: 0})
    base = registers[sprite_register]
    memory.update({base + 0x50: position, base + 0x54: ((size[0] & 0xFFFF) << 16) | (size[1] & 0xFFFF),
                   base + 0x70: rotation})
    return registers, memory, x_register


def menu_camera_state(game_id, *, records=None, table=0x81000000, count=None,
                      camera=0x81534200, aspect=1.28, fov=61.37):
    """A retail-addressed GSres table, independent of the emitted instruction table."""
    fixture = RETAIL[game_id]['menu_camera']
    groups = [int(group, 16) for group in fixture['groups']]
    if records is None:
        records = [{}]
    registers = [0x11000000 + index * 0x1000 for index in range(32)]
    registers[2], registers[13], registers[30] = PROJECTIONS[game_id][1], int(fixture['r13'], 16), camera
    floats = [single(index + .25) for index in range(32)]
    floats[1:5] = [single(fov), single(aspect), .125, 30000.]
    memory = {int(fixture['table']['address'], 16): table,
              int(fixture['count']['address'], 16): len(records) if count is None else count,
              int(fixture['three_quarters_constant']['address'], 16): .75}
    for index, record in enumerate(records):
        address = table + index * 0x14
        if not 0x80000000 <= address <= 0x817FFFE0:
            continue
        data = record.get('data', 0x81010000 + index * 0x100)
        memory.update({address: 0x12340000 + index, address + 4: data,
                       address + 8: record.get('group', groups[0]),
                       address + 12: record.get('id', int(fixture['resource_id'], 16)),
                       address + 16: 0xABCD0000 + index})
        # Invalid pointers deliberately have no backing fixture: an accidental
        # dereference must fail instead of being hidden by a forgiving memory model.
        if 0x80000000 <= data <= 0x817FFFF0:
            memory[data + 12] = record.get('hsd', camera)
    return registers, floats, memory


class DisplayTests(unittest.TestCase):
    def test_camera_stub_widens_the_view_without_changing_vertical_scale(self):
        for game in PROJECTIONS:
            rows = projection_entries(game, True)
            word = rows[1][1]
            self.assertEqual((word >> 26, word & 0x3F), (59, 0x24))  # fdivs
            fd, fa, fb = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
            for aspect in (4 / 3, 1, 1.5, 16 / 9):
                floats = [0.] * 32; floats[29], floats[2] = .75, aspect
                floats[fd] = struct.unpack('>f', struct.pack('>f', floats[fa] / floats[fb]))[0]
                self.assertAlmostEqual(floats[29] / aspect, 4 / 3, places=6)
                self.assertEqual(floats[2], aspect)
            # The only native data exception is XD's independently qualified fade quad.
            allowed_data = ({FLASH_BACKGROUNDS[game][1] + offset for offset in (0, 8, 16, 24)}
                            if game in FLASH_BACKGROUNDS else set())
            self.assertTrue(all(address < 0x80300000 or address in allowed_data for address, *_ in rows))

    def test_emitted_orthographic_stub_preserves_pixel_proportions_and_other_matrix_rows(self):
        # Execute the actual instructions, independently of their emitter.
        for game, (hook, r2, constant) in PROJECTIONS.items():
            for left, right in ((0, 640), (-320, 320), (0, 512)):
                original = [2 / (right - left), 0, 0, -(right + left) / (right - left),
                            0, -1 / 240, 0, 1, 0, 0, -.5, 0, 0, 0, 0, 1]
                registers = [0x10000 + index * 0x100 for index in range(32)]
                registers[2], registers[3] = r2, 0x81000000
                before = registers[:]
                floats = [index + .25 for index in range(32)]
                memory = {registers[3] + index * 4: value for index, value in enumerate(original)}
                memory[constant] = .75
                code = {address: value for address, value, _ in projection_entries(game, True)}
                pc = 0x80005310
                while code[pc] != 0x4E800020:
                    word = code[pc]; pc += 4
                    opcode = word >> 26
                    target, ra, rc = (word >> 21) & 31, (word >> 16) & 31, (word >> 6) & 31
                    displacement = (word & 0xFFFF) - (0x10000 if word & 0x8000 else 0)
                    if opcode == 48:
                        floats[target] = memory[registers[ra] + displacement]
                    elif opcode == 52:
                        memory[registers[ra] + displacement] = floats[target]
                    elif opcode == 59 and word & 0x3F == 0x32:
                        floats[target] = struct.unpack('>f', struct.pack('>f', floats[ra] * floats[rc]))[0]
                    else:
                        self.fail(f'Unexpected display instruction {word:08x}')
                result = [memory[registers[3] + index * 4] for index in range(16)]
                self.assertEqual(registers, before)
                self.assertEqual(result[4:], original[4:])
                self.assertAlmostEqual(result[0], original[0] * .75)
                self.assertAlmostEqual(result[3], original[3] * .75)
                # 16:9 viewport is 4/3 wider: net width stays exactly native.
                self.assertAlmostEqual((result[0] / original[0]) * (16 / 9) / (4 / 3), 1, places=6)

    def test_legacy_folders_start_normally_with_a_200_percent_shortcut(self):
        for previous in (1, 2):
            self.assertEqual(acceleration_target({"speed": previous}), 2)
        for value in (1, 2, 3):
            self.assertEqual(acceleration_target({"acceleration": value}), value)
        for value in (0, .5, 4, True, "2", float("nan")):
            with self.assertRaises(ValueError):
                acceleration_target({"acceleration": value})
        self.assertEqual(display_mode({}), "16:9")
        with self.assertRaises(ValueError):
            display_mode({"display": "stretch"})

    def test_projection_uses_the_three_upstream_ralf_hook_sites(self):
        expected = {
            "GC6P01": (0x480A1C68, 0x4BF5E394),
            "GC6E01": (0x4809E62C, 0x4BF619D0),
            "GXXP01": (0x480AF7A8, 0x4BF50854),
        }
        for game, words in expected.items():
            rows = projection_entries(game, True)
            self.assertEqual((rows[2][1], rows[3][1]), words)
            self.assertEqual(rows[3][2], 0xFFA01090)

    def test_every_port_loads_the_correct_constant_and_returns_after_the_hook(self):
        for game, (hook, r2, constant) in PROJECTIONS.items():
            rows = projection_entries(game, True)
            disp = rows[0][1] & 0xFFFF
            self.assertEqual(r2 + (disp if disp < 32768 else disp - 65536), constant)
            for source, word, target in ((rows[2][0], rows[2][1], hook + 4),
                                         (hook, rows[3][1], 0x80005300)):
                delta = word & 0x03FFFFFC
                self.assertEqual(source + (delta if delta < 0x2000000 else delta - 0x4000000), target)
            restore = projection_entries(game, False)
            self.assertEqual(restore[0], (hook, 0xFFA01090, rows[3][1]))
            self.assertEqual(restore[1], (hook + 0x144, 0x4E800020,
                {address: value for address, value, _ in rows}[hook + 0x144]))

    def test_bounds_adapter_executes_both_argument_orders_without_clobbering_abi_state(self):
        for game_id in PROJECTIONS:
            target, eighth, _, _ = RENDER_PASSES[game_id]
            r2 = PROJECTIONS[game_id][1]
            constant = struct.unpack('>f', bytes.fromhex(RETAIL[game_id]['eighth']['expected_word']))[0]
            for sdk_order in (False, True):
                left_register, right_register = (3, 4) if sdk_order else (1, 3)
                for left, right in ((0., 640.), (-320., 320.), (0., 608.), (-304., 304.), (64., 672.)):
                    with self.subTest(game=game_id, sdk_order=sdk_order, left=left, right=right):
                        code = {address: word for address, word, _ in _bounds_adapter(
                            0x80005330, target, r2, eighth, sdk_order=sdk_order)}
                        registers = [0x10000 + index * 0x100 for index in range(32)]
                        registers[2] = r2
                        before_registers = registers[:]
                        floats = [index + .25 for index in range(32)]
                        floats[left_register], floats[right_register] = left, right
                        before_floats = floats[:]
                        memory = {eighth: constant}
                        destination, lr, visited = execute_stub(
                            self, code, 0x80005330, registers, floats, memory, 0x81234560)
                        self.assertEqual(destination, target)
                        self.assertEqual(lr, 0x81234560)
                        self.assertEqual(len(visited), 6)
                        self.assertEqual(registers, before_registers)
                        self.assertEqual(memory, {eighth: .125})
                        allowed = {0, 10, left_register, right_register}
                        self.assertEqual([value for index, value in enumerate(floats) if index not in allowed],
                            [value for index, value in enumerate(before_floats) if index not in allowed])
                        self.assertEqual(floats[left_register], left + (right - left) / 8)
                        self.assertEqual(floats[right_register], right - (right - left) / 8)

    def test_emitted_fullscreen_calls_cover_the_native_screen_and_hud_keeps_its_proportions(self):
        for game_id, (target, eighth, fullscreen, _) in RENDER_PASSES.items():
            left_register, right_register = (3, 4) if game_id.startswith('GXX') else (1, 3)
            code = {address: value for address, value, _ in projection_entries(game_id, True)}
            for call in fullscreen:
                for left, right in ((0., 640.), (-320., 320.), (0., 608.), (-304., 304.), (64., 672.)):
                    with self.subTest(game=game_id, call=hex(call), bounds=(left, right)):
                        registers = [0.] * 32; registers[2] = PROJECTIONS[game_id][1]
                        floats = [index + .25 for index in range(32)]
                        floats[left_register], floats[right_register] = left, right
                        destination, lr, visited = execute_stub(
                            self, code, call, registers, floats, {eighth: .125}, 0x81234560)
                        self.assertEqual(destination, target)
                        self.assertEqual(lr, call + 4)
                        self.assertEqual(visited.count(0x80005330), 1)
                        full = patched_ortho(self, game_id, floats[left_register], floats[right_register])
                        native = native_ortho(left, right)
                        for actual, expected in zip(full, native):
                            self.assertAlmostEqual(actual, expected, places=6)
                        self.assertAlmostEqual(full[0] * left + full[3], -1., places=6)
                        self.assertAlmostEqual(full[0] * right + full[3], 1., places=6)
                        hud = patched_ortho(self, game_id, left, right)
                        self.assertAlmostEqual(hud[0] * left + hud[3], -.75, places=6)
                        self.assertAlmostEqual(hud[0] * right + hud[3], .75, places=6)
                        self.assertAlmostEqual(hud[0] / native[0] * (16 / 9) / (4 / 3), 1., places=6)

    def test_colosseum_deferred_command_58_records_adjusted_bounds_only_once(self):
        for game_id in ('GC6P01', 'GC6E01', 'GC6J01'):
            target, eighth, fullscreen, _ = RENDER_PASSES[game_id]
            code = {address: value for address, value, _ in projection_entries(game_id, True)}
            self.assertNotIn(target, code, 'The command producer itself must remain native')
            for left, right in ((0., 640.), (-304., 304.)):
                registers = [0] * 32; registers[2] = PROJECTIONS[game_id][1]
                floats = [0.] * 32
                floats[1], floats[2], floats[3], floats[4] = left, 0., right, 480.
                native_target, _, visited = execute_stub(
                    self, code, fullscreen[0], registers, floats, {eighth: .125}, 0x81234560)
                self.assertEqual(native_target, target)
                # The native producer records command 58 plus four adjusted f32s.
                recorded = struct.pack('>I4f', 58, *floats[1:5])
                command, replay_left, top, replay_right, bottom = struct.unpack('>I4f', recorded)
                self.assertEqual((command, top, bottom), (58, 0., 480.))
                self.assertEqual(visited.count(0x80005330), 1)
                # Replay calls the unmodified producer; no adapter runs again.
                result = patched_ortho(self, game_id, replay_left, replay_right)
                self.assertAlmostEqual(result[0] * left + result[3], -1., places=6)
                self.assertAlmostEqual(result[0] * right + result[3], 1., places=6)
        eu_writes = {address for address, _, _ in projection_entries('GC6P01', True)}
        self.assertNotIn(0x800D8250, eu_writes, 'The qualified native command-58 replay BL must stay native')

    def test_regional_constants_and_original_call_words_match_the_retail_fixture(self):
        self.assertEqual(set(RETAIL), set(PROJECTIONS))
        self.assertEqual(set(RENDER_PASSES), set(PROJECTIONS))
        for game_id, (target, eighth, fullscreen, textures) in RENDER_PASSES.items():
            evidence = RETAIL[game_id]
            constant = evidence['eighth']
            self.assertEqual(constant['expected_word'], '3e000000')
            self.assertEqual(eighth, int(constant['address'], 16))
            self.assertEqual(eighth - PROJECTIONS[game_id][1], constant['r2_signed_displacement'])
            wide = {address: (value, expected) for address, value, expected in projection_entries(game_id, True)}
            restores = {address: (value, expected) for address, value, expected in projection_entries(game_id, False)}
            self.assertEqual(wide[0x80005330][0] & 0xFFFF, int(constant['r2_immediate'], 16))
            for call, original_target in [*((call, target) for call in fullscreen), *textures]:
                original = int(evidence['words'][f'0x{call:08x}'], 16)
                patched, required = wide[call]
                self.assertEqual(required, original)
                self.assertEqual(original >> 26, 18)
                self.assertEqual(original & 3, 1)
                self.assertEqual(branch_destination(call, original), original_target)
                self.assertEqual(patched & 3, 1)
                self.assertIn(branch_destination(call, patched), (0x80005330, 0x80005350))
                self.assertEqual(restores[call], (original, patched))

    def test_window_background_calls_match_retail_words_and_restore_conditionally(self):
        self.assertEqual(set(WINDOW_BACKGROUNDS), set(PROJECTIONS))
        for game_id, (callee, textured, solid) in WINDOW_BACKGROUNDS.items():
            wide = {address: (value, expected) for address, value, expected in _background_entries(game_id, True)}
            restored = {address: (value, expected) for address, value, expected in _background_entries(game_id, False)}
            fixture = {int(address, 16): int(word, 16)
                       for address, word in RETAIL[game_id]['background_words'].items()}
            self.assertEqual(set(fixture), {textured, *solid})
            for call, original in fixture.items():
                patched, required = wide[call]
                self.assertEqual(required, original)
                self.assertEqual(patched & 3, 1, 'Inline stores also require a linked branch for BLR')
                self.assertEqual(restored[call], (original, patched))
                if callee is not None:
                    self.assertEqual(branch_destination(call, original), callee)
                else:
                    self.assertEqual(original, 0xB0158000 if call == textured else 0xB0068000)
            injected = sorted(address for address, (_, expected) in wide.items() if expected is None)
            start, count = (0x80005368, 16) if callee is not None else (0x80005350, 21)
            self.assertEqual(injected, list(range(start, start + count * 4, 4)))

    def test_window_background_adapters_expand_covering_panels_and_preserve_bounded_sprites(self):
        cases = (
            ('fullscreen', {}, True),
            ('portrait', {'size': (64, 64)}, False),
            ('text', {'size': (16, 16)}, False),
            ('608 canvas', {'size': (608, 480)}, False),
            ('translated x', {'position': 1 << 16}, False),
            ('tile at y 240', {'position': 240, 'size': (640, 240)}, True),
            ('translated y', {'position': 1}, True),
            ('negative origin', {'position': 0xFFFF0000}, False),
            ('scaled width', {'size': (320, 480)}, False),
            ('scaled height', {'size': (640, 240)}, True),
            ('overscan tile', {'position': (0xFFEC << 16) | 240, 'size': (680, 240)}, True),
            ('overscan touches right', {'position': 0xFFEC << 16, 'size': (660, 480)}, True),
            ('overscan leaves right gap', {'position': 0xFFEC << 16, 'size': (659, 480)}, False),
            ('negative width', {'size': (-1, 480)}, False),
            ('zero width', {'size': (0, 480)}, False),
            ('rotated', {'rotation': 0x3F800000}, False),
            ('negative zero', {'rotation': 0x80000000}, False),
        )
        for game_id, (callee, textured, solid) in WINDOW_BACKGROUNDS.items():
            code = {address: value for address, value, _ in projection_entries(game_id, True)}
            for call in (textured, *solid):
                for case, sprite, full in cases:
                    for x in (-21, -20, -1, 0, 1, 160, 320, 480, 639, 640, 660, 661):
                        with self.subTest(game=game_id, call=hex(call), sprite=case, x=x):
                            registers, memory, x_register = background_state(game_id, call, x, **sprite)
                            destination, lr, _ = execute_stub(
                                self, code, call, registers, [0.] * 32, memory, 0x81234560)
                            numerator = 4 * x + 2
                            quotient = numerator // 3 if numerator >= 0 else -((-numerator) // 3)
                            expected = quotient - 107 if full else x
                            self.assertEqual(registers[x_register], expected & 0xFFFFFFFF)
                            self.assertEqual(destination, callee if callee is not None else call + 4)
                            self.assertEqual(lr, call + 4)
                            if callee is None:
                                self.assertEqual(memory[0xCC008000], expected & 0xFFFF)
            # The rounded native X limits overlap the final viewport slightly, avoiding seams.
            hud = patched_ortho(self, game_id, 0., 640.)
            self.assertLess(hud[0] * -107 + hud[3], -1.)
            self.assertGreater(hud[0] * 747 + hud[3], 1.)
            self.assertAlmostEqual(hud[0] * -107 + hud[3], -1., delta=.001)
            self.assertAlmostEqual(hud[0] * 747 + hud[3], 1., delta=.001)

    def test_window_background_preserves_uv_y_sprite_data_and_abi_and_uses_native_fifo(self):
        for game_id, (callee, textured, solid) in WINDOW_BACKGROUNDS.items():
            code = {address: value for address, value, _ in projection_entries(game_id, True)}
            for call in (textured, *solid):
                for x, sprite in ((0, {}), (640, {}), (320, {}),
                                  (0, {'position': 1}), (640, {'size': (64, 64)}),
                                  (660, {'position': 0xFFEC << 16, 'size': (680, 240)}),
                                  (0, {'rotation': 0x80000000})):
                    with self.subTest(game=game_id, call=hex(call), x=x, sprite=sprite):
                        registers, memory, x_register = background_state(game_id, call, x, **sprite)
                        before_registers, before_memory = registers[:], memory.copy()
                        floats = [index + .25 for index in range(32)]
                        before_floats = floats[:]
                        conditions = [0xA, 0x5, 0xC, 0x6, 0x4, 0x8, 0x2, 0x6]
                        before_conditions = conditions[:]
                        stores = []
                        destination, lr, _ = execute_stub(self, code, call, registers, floats, memory,
                            0x81234560, conditions=conditions, stores=stores)
                        allowed_registers = {x_register, 0, 12} if callee is not None else {0, 11, 12}
                        self.assertEqual([value for index, value in enumerate(registers) if index not in allowed_registers],
                            [value for index, value in enumerate(before_registers) if index not in allowed_registers])
                        self.assertEqual(floats, before_floats)
                        allowed_conditions = {0, 7} if callee is not None else {7}
                        self.assertEqual([value for index, value in enumerate(conditions) if index not in allowed_conditions],
                            [value for index, value in enumerate(before_conditions) if index not in allowed_conditions])
                        if callee is not None:
                            self.assertEqual((destination, lr), (callee, call + 4))
                            self.assertEqual(memory, before_memory)
                            self.assertFalse(stores)
                        else:
                            self.assertEqual((destination, lr), (call + 4, call + 4))
                            self.assertEqual(stores, [(0xCC008000, registers[x_register] & 0xFFFF, 2)])
                            self.assertEqual({address: value for address, value in memory.items()
                                              if address != 0xCC008000}, before_memory)
                            self.assertNotIn(0xCBFF8000, memory, 'lis CC00 plus signed -8000 targets the wrong FIFO')

    def test_flash_adapter_changes_only_four_full_width_stack_x_values(self):
        def bits(value):
            return struct.unpack('>I', struct.pack('>f', value))[0]

        cases = (
            ('full canvas', (0., 640., 640., 0.), True),
            ('portrait', (0., 64., 64., 0.), False),
            ('text', (0., 16., 16., 0.), False),
            ('translated', (64., 704., 704., 64.), False),
            ('scaled', (0., 320., 320., 0.), False),
            ('rotated', (64., 640., 576., 0.), False),
            ('unequal right edge', (0., 640., 639., 0.), False),
            ('unequal left edge', (0., 640., 640., 1.), False),
            ('negative zero', (-0., 640., 640., 0.), False),
        )
        offsets = (0x24, 0x2C, 0x34, 0x3C)
        for game_id, (hook, _) in FLASH_BACKGROUNDS.items():
            code = {address: value for address, value, _ in projection_entries(game_id, True)}
            for case, x_values, full in cases:
                for top, bottom in ((0., 480.), (0., 240.), (240., 480.), (-120., 120.)):
                    with self.subTest(game=game_id, quad=case, top=top, bottom=bottom):
                        registers = [0x11000000 + index * 0x1000 for index in range(32)]
                        stack, data = 0x817FF000, 0x81234000
                        registers[1], registers[31] = stack, data
                        memory = {stack + offset: 0x12340000 + offset for offset in range(0x10, 0xA0, 4)}
                        memory[data] = 0xFFFE1234
                        memory.update({stack + offset: bits(value) for offset, value in zip(offsets, x_values)})
                        memory.update({stack + offset: bits(value) for offset, value in
                            zip((0x28, 0x30, 0x38, 0x40), (top, top, bottom, bottom))})
                        before_registers, before_memory = registers[:], memory.copy()
                        floats = [index + .25 for index in range(32)]
                        before_floats = floats[:]
                        conditions = [0xA, 0x5, 0xC, 0x6, 0x4, 0x8, 0x2, 0x6]
                        before_conditions = conditions[:]
                        stores = []
                        destination, lr, visited = execute_stub(self, code, hook, registers, floats,
                            memory, 0x81234560, conditions=conditions, stores=stores)
                        expected = before_memory.copy()
                        if full:
                            expected.update({stack + offset: bits(value) for offset, value in
                                             zip(offsets, (-107., 747., 747., -107.))})
                        self.assertEqual(memory, expected, 'Y, UVs and other stack records must stay native')
                        self.assertEqual({address for address, _, _ in stores},
                                         {stack + offset for offset in offsets} if full else set())
                        self.assertTrue(all(size == 4 for _, _, size in stores))
                        self.assertEqual((destination, lr), (hook + 4, 0x81234560))
                        self.assertEqual(registers[3], 0xFFFFFFFE, 'The overwritten signed lha must be reissued')
                        self.assertEqual([value for index, value in enumerate(registers) if index not in {0, 3, 12}],
                            [value for index, value in enumerate(before_registers) if index not in {0, 3, 12}])
                        self.assertEqual(conditions[:7], before_conditions[:7])
                        self.assertEqual(floats, before_floats)
                        self.assertEqual(visited.count(FLASH_SCRATCH), 1)
        for game_id in ('GC6P01', 'GC6E01', 'GC6J01'):
            self.assertEqual(_flash_entries(game_id, True), [])
            self.assertEqual(_flash_entries(game_id, False), [])

    def test_flash_hook_and_alpha_quad_use_retail_fixture_and_owned_restoration(self):
        for game_id, (hook, alpha) in FLASH_BACKGROUNDS.items():
            evidence = RETAIL[game_id]
            self.assertEqual(evidence['flash_hook'], {f'0x{hook:08x}': '0xa87f0000'})
            self.assertEqual(int(evidence['alpha_quad']['address'], 16), alpha)
            original = struct.unpack('>8I', bytes.fromhex(evidence['alpha_quad']['original']))
            wide = {address: (word, expected) for address, word, expected in _flash_entries(game_id, True)}
            restored = {address: (word, expected) for address, word, expected in _flash_entries(game_id, False)}
            self.assertEqual(wide[hook][1], 0xA87F0000)
            self.assertEqual(wide[hook][0] & 3, 0, 'FLASH preserves LR with a plain branch')
            self.assertEqual(branch_destination(hook, wide[hook][0]), FLASH_SCRATCH)
            self.assertEqual(restored[hook], (0xA87F0000, wide[hook][0]))
            for index, expanded in zip((0, 2, 4, 6), (0xC2D60000, 0x443AC000, 0x443AC000, 0xC2D60000)):
                address = alpha + index * 4
                self.assertEqual(wide[address], (expanded, original[index]))
                self.assertEqual(restored[address], (original[index], expanded))
            self.assertFalse(any(alpha + index * 4 in wide for index in (1, 3, 5, 7)),
                             'The dedicated alpha quad Y values stay native')

    def _assert_menu_camera_case(self, game_id, compensate, **state):
        fixture = RETAIL[game_id]['menu_camera']
        code = {address: value for address, value, _ in projection_entries(game_id, True)}
        results = []
        for address in fixture['calls']:
            call = int(address, 16)
            registers, floats, memory = menu_camera_state(game_id, **state)
            before_registers, before_floats, before_memory = registers[:], floats[:], memory.copy()
            conditions = [0xA, 0x5, 0xC, 0x6, 0x4, 0x8, 0x2, 0x6]
            before_conditions = conditions[:]
            reads, stores = [], []
            destination, lr, visited = execute_stub(self, code, call, registers, floats, memory,
                0x81234560, conditions=conditions, reads=reads, stores=stores)
            self.assertEqual((destination, lr), (int(fixture['sdk'], 16), call + 4))
            self.assertEqual(visited.count(FLASH_SCRATCH), 1)
            self.assertEqual(memory, before_memory, 'Resource/camera/constant data must never be edited')
            self.assertFalse(stores)
            self.assertEqual([value for index, value in enumerate(registers) if index not in {0, 11, 12}],
                [value for index, value in enumerate(before_registers) if index not in {0, 11, 12}])
            self.assertEqual([value for index, value in enumerate(floats) if index not in {0, 2}],
                [value for index, value in enumerate(before_floats) if index not in {0, 2}])
            self.assertEqual(conditions[:7], before_conditions[:7])
            expected_aspect = single(before_floats[2] * .75) if compensate else before_floats[2]
            self.assertEqual(floats[2], expected_aspect)
            constant = int(fixture['three_quarters_constant']['address'], 16)
            self.assertEqual(reads.count(constant), 1 if compensate else 0)
            if compensate:
                # The subsequent ordinary Hor+ SDK hook cancels this input
                # compensation, keeping the finite background at native aspect.
                self.assertAlmostEqual(single(floats[2] / .75), before_floats[2], places=6)
            results.append(reads)
        return results

    def test_menu_camera_matches_every_qualified_archive_group_and_both_native_callers(self):
        for game_id in MENU_CAMERAS:
            groups = [int(group, 16) for group in RETAIL[game_id]['menu_camera']['groups']]
            for group in groups:
                for fov, aspect in ((20., 1.), (61.37, 1.28), (75., 16 / 9)):
                    with self.subTest(game=game_id, group=hex(group), fov=fov, aspect=aspect):
                        self._assert_menu_camera_case(game_id, True,
                            records=[{'group': group}], fov=fov, aspect=aspect)

    def test_menu_camera_rejects_other_ids_groups_and_objects_even_at_the_same_fov(self):
        for game_id in MENU_CAMERAS:
            first, last = map(lambda value: int(value, 16),
                              RETAIL[game_id]['menu_camera']['regional_interval'])
            excluded_groups = {0, 0x37B, 0x37D, 0x530, 0x532, first - 1, last + 1,
                               0xFFFFFFFF, 0x80000000,
                               0x632 if game_id == 'GC6P01' else 0x7CF}
            for group in excluded_groups:
                with self.subTest(game=game_id, wrong_group=hex(group)):
                    self._assert_menu_camera_case(game_id, False, records=[{'group': group}])
            for resource_id in (0, 0x0FFF1000, 0x0FFE1800, 0x1FFF1800, 0x0FFF1801):
                with self.subTest(game=game_id, wrong_id=hex(resource_id)):
                    self._assert_menu_camera_case(game_id, False, records=[{'id': resource_id}])
            with self.subTest(game=game_id, wrong_camera=True):
                self._assert_menu_camera_case(game_id, False, records=[{'hsd': 0x81534204}])

    def test_menu_camera_scan_skips_stale_records_and_stops_at_the_declared_count(self):
        for game_id in MENU_CAMERAS:
            for stale in ({'data': 0}, {'id': 0x0FFF1801}, {'group': 0}, {'hsd': 0x81534204}):
                with self.subTest(game=game_id, stale=stale):
                    self._assert_menu_camera_case(game_id, True,
                        records=[stale, {'id': 0x0FFE1000}, {}])
            with self.subTest(game=game_id, declared_count=1):
                reads = self._assert_menu_camera_case(game_id, False,
                    records=[{'id': 0}, {}], count=1)
                self.assertTrue(all(0x81000020 not in visited_reads for visited_reads in reads),
                                'The matching second record lies outside the declared table')
            with self.subTest(game=game_id, declared_count=8192):
                self._assert_menu_camera_case(game_id, True, count=8192)

    def test_menu_camera_guards_counts_and_table_bounds_before_dereferencing(self):
        for game_id in MENU_CAMERAS:
            fixture = RETAIL[game_id]['menu_camera']
            globals_only = {int(fixture[key]['address'], 16) for key in ('table', 'count')}
            for count in (0, 8193, 0x80000000, 0xFFFFFFFF):
                with self.subTest(game=game_id, invalid_count=count):
                    reads = self._assert_menu_camera_case(game_id, False, count=count)
                    self.assertTrue(all(set(visited_reads) <= globals_only for visited_reads in reads))
            for table in (0, 0x7FFFFFF0, 0x817FFFE4, 0x81800000, 0xFFFFFFF0):
                with self.subTest(game=game_id, invalid_table=hex(table)):
                    reads = self._assert_menu_camera_case(game_id, False, table=table)
                    self.assertTrue(all(set(visited_reads) <= globals_only for visited_reads in reads))
            for table in (0x80000000, 0x817FFFE0):
                with self.subTest(game=game_id, valid_boundary=hex(table)):
                    self._assert_menu_camera_case(game_id, True, table=table)
            # A valid first record can be followed by a corrupt count/window.
            # The per-record bound must prevent even an ID read beyond MEM1.
            with self.subTest(game=game_id, table_crosses_mem1=True):
                self._assert_menu_camera_case(game_id, False,
                    table=0x817FFFE0, records=[{'id': 0}, {}])

    def test_menu_camera_guards_camera_pointer_and_complete_hsd_field(self):
        for game_id in MENU_CAMERAS:
            for data in (0, 0x7FFFFFFC, 0x817FFFF4, 0x81800000, 0xFFFFFFFF):
                with self.subTest(game=game_id, invalid_camera_data=hex(data)):
                    reads = self._assert_menu_camera_case(game_id, False, records=[{'data': data}])
                    self.assertTrue(all(data + 12 not in visited_reads for visited_reads in reads))
            for data in (0x80000000, 0x817FFFF0):
                with self.subTest(game=game_id, valid_camera_boundary=hex(data)):
                    self._assert_menu_camera_case(game_id, True, records=[{'data': data}])

    def test_menu_camera_regional_guards_and_owned_restoration_match_retail_fixture(self):
        for game_id in PROJECTIONS:
            fixture = RETAIL[game_id]['menu_camera']
            if fixture is None:
                self.assertEqual(_menu_camera_entries(game_id, True), [])
                self.assertEqual(_menu_camera_entries(game_id, False), [])
                continue
            table, count, first, last, calls = MENU_CAMERAS[game_id]
            self.assertEqual((table, count), (fixture['table']['r13_signed_displacement'],
                                            fixture['count']['r13_signed_displacement']))
            self.assertEqual((first, last), tuple(int(value, 16) for value in fixture['regional_interval']))
            for key in ('table', 'count'):
                self.assertEqual(int(fixture['r13'], 16) + fixture[key]['r13_signed_displacement'],
                                 int(fixture[key]['address'], 16))
            self.assertEqual(fixture['resource_id'], '0x0fff1800')
            self.assertEqual(fixture['three_quarters_constant']['expected_word'], '3f400000')
            wide = {address: (word, expected) for address, word, expected in _menu_camera_entries(game_id, True)}
            restored = {address: (word, expected) for address, word, expected in _menu_camera_entries(game_id, False)}
            self.assertEqual(set(calls), {int(address, 16) for address in fixture['calls']})
            for address, expected in fixture['calls'].items():
                call, original = int(address, 16), int(expected, 16)
                patched, guard = wide[call]
                self.assertEqual(guard, original)
                self.assertEqual(original & 3, 1)
                self.assertEqual(branch_destination(call, original), int(fixture['sdk'], 16))
                self.assertEqual(patched & 3, 1)
                self.assertEqual(branch_destination(call, patched), FLASH_SCRATCH)
                self.assertEqual(restored[call], (original, patched))
            self.assertEqual(set(restored), set(calls))

    def test_native_anti_action_replay_clear_cannot_erase_either_adapter_between_frames(self):
        """Execute installed PPC after the retail wipe, without reapplying OnFrame."""
        for game_id in PROJECTIONS:
            # Colosseum uses the same low-memory arena. Apply the independently
            # verified XD wipe there too, rather than assume native code owns it.
            clear_fixture = RETAIL[game_id if game_id in FLASH_BACKGROUNDS else 'GXXE01']['anti_action_replay']
            table = struct.unpack('>32I', bytes.fromhex(clear_fixture['table_hex']))
            intervals = [(0x80000000 + left + 0x15, 0x80000000 + right + 0x16)
                         for left, right in zip(table[::2], table[1::2])]
            intervals.append((0x80001801, 0x80003000))
            self.assertEqual(intervals[0], (0x80001800, 0x80003000))
            self.assertEqual(len(intervals), 17)
            self.assertTrue(all(end <= 0x80003000 for _, end in intervals))

            def native_clear(words):
                result = words.copy()
                for address, value in words.items():
                    if not any(address < end and address + 4 > start for start, end in intervals):
                        continue
                    data = bytearray(value.to_bytes(4, 'big'))
                    for index in range(4):
                        if any(start <= address + index < end for start, end in intervals):
                            data[index] = 0
                    result[address] = int.from_bytes(data, 'big')
                return result

            installed = {address: value for address, value, _ in projection_entries(game_id, True)}
            code = native_clear(installed)
            self.assertEqual(code, installed, 'Native clears must not touch any installed display code or data')
            markers = {address: 0xA5A5A5A5 for address in
                       (0x80001800, 0x800027FC, 0x80002800, 0x800028FC, 0x80002FFC,
                        0x80003000, 0x80004CFC, 0x80004E00, 0x800052FC, 0x800053AC)}
            memory = native_clear(markers)
            self.assertEqual(memory[0x80002800], 0, 'The old code-handler address reproduces the native wipe')
            for address in (0x80003000, 0x80004CFC, 0x80004E00, 0x800052FC, 0x800053AC):
                self.assertEqual(memory[address], markers[address])

            if game_id in MENU_CAMERAS:
                registers, floats, state = menu_camera_state(game_id)
                memory.update(state)
                call = next(iter(MENU_CAMERAS[game_id][4]))
                expected_target = PROJECTIONS[game_id][0] - 0x20
                allowed_stores = set()
            else:
                registers = [0x11000000 + index * 0x1000 for index in range(32)]
                stack, data = 0x817FF000, 0x81234000
                registers[1], registers[31] = stack, data
                floats = [index + .25 for index in range(32)]
                memory[data] = 0xFFFE1234
                offsets = (0x24, 0x2C, 0x34, 0x3C)
                memory.update({stack + offset: struct.unpack('>I', struct.pack('>f', value))[0]
                               for offset, value in zip(offsets, (0., 640., 640., 0.))})
                call = FLASH_BACKGROUNDS[game_id][0]
                expected_target = call + 4
                allowed_stores = {stack + offset for offset in offsets}
            before_memory = memory.copy()
            stores = []
            destination, _, visited = execute_stub(self, code, call, registers, floats, memory,
                                                   0x81234560, stores=stores)
            self.assertEqual(destination, expected_target)
            self.assertEqual(visited.count(0x80004D00), 1)
            self.assertEqual({address for address, _, _ in stores}, allowed_stores)
            self.assertEqual({address: value for address, value in memory.items() if address not in allowed_stores},
                             {address: value for address, value in before_memory.items() if address not in allowed_stores})
            self.assertEqual(code, installed, 'Executing an adapter must not modify its own code')

    def test_display_modes_do_not_depend_on_gecko_handler_ownership_or_change_cheat_setting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / 'Config/Dolphin.ini'
            config.parent.mkdir()
            config.write_text('[Core]\nEnableCheats = True\n', encoding='utf-8')
            for game_id in PROJECTIONS:
                path = root / 'GameSettings' / (game_id + '.ini')
                path.parent.mkdir(exist_ok=True)
                path.write_text('[Core]\nCustomSetting = keep\n', encoding='utf-8')
                with self.subTest(game=game_id):
                    configure_projection(root, game_id, '16:9')
                    self.assertIn('CustomSetting = keep', path.read_text('utf-8'))
                    self.assertIn('0x80004D00:dword:', path.read_text('utf-8'))
                self.assertFalse(path.with_suffix('.ini.orre-tmp').exists())
                configure_projection(root, game_id, '4:3')
                self.assertIn('CustomSetting = keep', path.read_text('utf-8'))
            self.assertEqual(config.read_text('utf-8'), '[Core]\nEnableCheats = True\n')

    def test_four_three_restores_owned_render_calls_and_keeps_foreign_hooks(self):
        def apply(memory, entries):
            for address, value, expected in entries:
                if expected is None or memory.get(address) == expected:
                    memory[address] = value
        for game_id in PROJECTIONS:
            wide, native = projection_entries(game_id, True), projection_entries(game_id, False)
            original = {address: expected for address, _, expected in wide if expected is not None}
            memory = original.copy()
            apply(memory, wide)
            for address, value, _ in wide:
                self.assertEqual(memory[address], value)
            apply(memory, native)
            for address, value in original.items():
                self.assertEqual(memory[address], value)
            # An unrelated replacement at any native hook cannot be replaced in either mode.
            for foreign_address in original:
                memory = {**original, foreign_address: 0x60000000}
                apply(memory, wide)
                self.assertEqual(memory[foreign_address], 0x60000000)
                apply(memory, native)
                self.assertEqual(memory[foreign_address], 0x60000000)

    def test_display_code_stays_inside_the_qualified_zero_cave(self):
        for game_id in PROJECTIONS:
            cave_end = int(RETAIL[game_id]['cave_zero_end_exclusive'], 16)
            self.assertEqual(cave_end, 0x800053AC)
            injected = [address for address, _, expected in projection_entries(game_id, True) if expected is None]
            self.assertTrue(injected)
            exception_padding = [address for address in injected if 0x80005300 <= address < cave_end]
            extended = [address for address in injected if address not in exception_padding]
            self.assertTrue(all(address + 4 <= cave_end and address % 4 == 0 for address in exception_padding))
            if game_id in FLASH_BACKGROUNDS:
                self.assertEqual(extended, list(range(FLASH_SCRATCH, FLASH_SCRATCH + 21 * 4, 4)))
            else:
                self.assertIn(game_id, MENU_CAMERAS)
                self.assertTrue(extended)
                self.assertEqual(extended, list(range(FLASH_SCRATCH, max(extended) + 4, 4)))
            reserved = RETAIL[game_id]['reserved_adapter']
            start, end = (int(reserved[key], 16) for key in ('start', 'end_exclusive'))
            self.assertEqual((start, end), (0x80004D00, 0x80004E00))
            self.assertEqual(FLASH_SCRATCH, start)
            self.assertEqual(bytes.fromhex(reserved['native_bytes']), bytes(end - start))
            vector_base = int(reserved['template_base'], 16)
            reserved_start = int(reserved['reserved_start'], 16)
            reserved_end = int(reserved['reserved_end_exclusive'], 16)
            self.assertLessEqual(reserved_start, start)
            self.assertLessEqual(end, reserved_end)
            for offset in reserved['copy_offsets']:
                vector_start = vector_base + int(offset, 16)
                self.assertFalse(vector_start < end and vector_start + 0x100 > start,
                                 'Injected code must not be copied into a native exception vector')
            self.assertTrue(all(start <= address and address + 4 <= end for address in extended))
            self.assertFalse(set(injected) & set(range(0x80001800, 0x80003000, 4)))
            self.assertEqual(len(injected), len(set(injected)))
            self.assertFalse(any(expected is None for _, _, expected in projection_entries(game_id, False)))

    def test_original_european_movie_projection_calls_are_not_retargeted(self):
        for game_id, movie_calls in {
            'GC6P01': (0x801E68D4, 0x801E5C30),
            'GXXP01': (0x801E60A8,),
        }.items():
            for mode in (True, False):
                writes = {address for address, _, _ in projection_entries(game_id, mode)}
                self.assertTrue(writes.isdisjoint(movie_calls), (game_id, mode))

    def test_switching_modes_is_idempotent_and_preserves_unrelated_game_patches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "GameSettings/GC6P01.ini"
            path.parent.mkdir()
            original = "[Core]\nCPUThread = False\n[OnFrame]\n$Keep\n0x80006000:dword:0x12345678\n[OnFrame_Enabled]\n$Keep\n"
            path.write_text(original, encoding="utf-8")
            for mode in ("16:9", "16:9", "4:3", "16:9", "4:3"):
                configure_projection(root, "GC6P01", mode)
                text = path.read_text("utf-8")
                self.assertIn("CPUThread = False", text)
                self.assertIn("$Keep\n0x80006000:dword:0x12345678", text)
                self.assertEqual(text.count("$" + PATCH_NAME), 2)
                self.assertEqual(text.count("[OnFrame]"), 1)
                self.assertEqual("0x80005300:dword:" in text, mode == "16:9")


if __name__ == "__main__":
    unittest.main()
