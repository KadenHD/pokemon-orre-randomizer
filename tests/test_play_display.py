"""Reversible regional projection codes and isolated launch settings."""
import tempfile
import struct
from pathlib import Path
import unittest

from orre_randomizer.play_display import (acceleration_target, display_mode,
    configure_projection, projection_entries, PROJECTIONS, PATCH_NAME)


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
            # All writes target executable stubs/hooks, never native data/BSS.
            self.assertTrue(all(address < 0x80300000 for address, *_ in rows))

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
            self.assertEqual(restore[1], (hook + 0x144, 0x4E800020, rows[-1][1]))

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
