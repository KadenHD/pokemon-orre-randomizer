"""Save-compatible allocation of the dedicated Lugia introduction flag."""
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine import postgame_scene_state as state
from orre_randomizer.engine.analyze_game import FormatError, parse_rel, u32
from orre_randomizer.engine.inspect_tables import rel_symbols
from orre_randomizer.engine.postgame_lugia import _extend_tables


class SceneFlagStorageTests(unittest.TestCase):
    def test_new_state_uses_spare_bits_in_last_existing_word(self):
        self.assertEqual(state.INTRO_STATE_FLAG, 3593)
        self.assertEqual(struct.unpack(">BBBBHh", state.FLAG_DESCRIPTOR),
                         (0xC2, 0, 0, 0, 6414, -1))
        self.assertEqual((state.FLAG_BIT + 31) // 32, (state.FLAG_BIT + state.FLAG_WIDTH + 31) // 32)
        self.assertLess((state.FLAG_BIT + state.FLAG_WIDTH + 31) // 32, state.FLAG_BUFFER_WORDS)
        # Native setters mask exactly their declared width. The saved retail
        # word's fourteen used bits survive every valid mission phase.
        for original in (0, 1, 0x1555, 0x2AAA, 0x3FFF):
            for phase in (state.PHASE_UNAVAILABLE, state.PHASE_AVAILABLE, state.PHASE_INTRODUCED):
                marked = original | (phase << (state.FLAG_BIT & 31))
                self.assertEqual(marked & 0x3FFF, original)
                self.assertEqual(marked >> 14, phase)


class NativeSceneFlagAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.sources = []
        for tag in ("pal", "usa", "japan"):
            path = root / "build/region-compat-2026-11-02/rel-research" / tag / "common.fsys-common_rel.rel"
            if path.exists():
                cls.sources.append((tag, path.read_bytes()))
        if not cls.sources:
            raise unittest.SkipTest("requires locally extracted original common RELs")

    def test_append_preserves_all_native_descriptors_and_does_not_expand_saved_storage(self):
        for tag, original in self.sources:
            with self.subTest(region=tag):
                symbols = rel_symbols(original, parse_rel(original))
                addition, manifest = state.flag_table_extension(original, symbols)
                result, report = _extend_tables(original, original, symbols, (addition,))
                relocated = rel_symbols(result, parse_rel(result))
                old, new = symbols[54]["offset"], relocated[54]["offset"]
                size = state.INTRO_STATE_FLAG * 8
                self.assertEqual(result[old:old + size], original[old:old + size])
                self.assertEqual(result[new:new + size], original[old:old + size])
                self.assertEqual(result[new + size:new + size + 8], state.FLAG_DESCRIPTOR)
                self.assertEqual(u32(result, relocated[55]["offset"]), 3594)
                self.assertEqual(result[relocated[55]["offset"] + 4:relocated[55]["offset"] + 8],
                                 original[symbols[55]["offset"] + 4:symbols[55]["offset"] + 8])
                self.assertEqual(manifest["used_words_before"], 201)
                self.assertEqual(manifest["used_words_after"], 201)
                self.assertEqual(manifest["allocated_words"], 384)
                self.assertTrue(manifest["save_layout_unchanged"])
                self.assertEqual(report["tables"]["scene_flags"]["count"], 3594)
                changed = bytearray(original)
                changed[old + 8] ^= 1
                with self.assertRaises(FormatError):
                    state.flag_table_extension(bytes(changed), symbols)


if __name__ == "__main__":
    unittest.main()
