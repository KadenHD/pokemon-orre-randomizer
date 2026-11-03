"""Independent TM/description mapping, compatibility and preservation checks."""
from dataclasses import dataclass, replace
from pathlib import Path
import struct
import unittest

from colosseum_randomizer.engine.analyze_game import FormatError
from colosseum_randomizer.engine.species_rules import STAT_OFFSETS
from colosseum_randomizer.engine.tm_rules import (
    COMPAT_OFFSET, FIRST_TM_ITEM, HM_COUNT, ITEM_OFFSET, ITEM_STRIDE,
    ORIGINAL_HM_MOVES, ORIGINAL_TM_MOVES, TM_COUNT, TM_OFFSET, TM_STRIDE,
    apply_tm_rules, apply_tm_tables)


@dataclass(frozen=True)
class Rules:
    randomize_tm_moves: bool = False
    tm_compatibility_mode: str = "original"
    tm_ensure_offensive: bool = True


def fixture():
    tables = {"species": {"offset": 64, "count": 5, "stride": 0x11C},
              "moves": {"offset": 64 + 5 * 0x11C, "count": 358, "stride": 0x38}}
    rel = bytearray(tables["moves"]["offset"] + 358 * 0x38 + 16)
    rel[64:64 + 0x11C] = b"\xA5" * 0x11C  # Reserved species, deliberately non-boolean.
    for index, types in enumerate(((10, 10), (11, 11), (6, 6), (12, 12)), 1):
        pos = 64 + index * 0x11C
        struct.pack_into(">H", rel, pos + 0x10, index)
        rel[pos + 0x30:pos + 0x34] = bytes((*types, 1, 0))
        for field in STAT_OFFSETS:
            rel[pos + field] = 50
        rel[pos + COMPAT_OFFSET:pos + COMPAT_OFFSET + TM_COUNT + HM_COUNT] = bytes(
            (i + index) % 2 for i in range(TM_COUNT + HM_COUNT))
        rel[pos + 0x6E:pos + 0x74] = b"guards"
    for index in range(1, 355):
        pos = tables["moves"]["offset"] + index * 0x38
        rel[pos + 1], rel[pos + 2], rel[pos + 4], rel[pos + 0x17] = 20, 0, 100, 40
        struct.pack_into(">I", rel, pos + 0x20, index)
    for index, move_type, power in ((264, 10, 0), (337, 11, 40), (352, 12, 40)):
        pos = tables["moves"]["offset"] + index * 0x38
        rel[pos + 2], rel[pos + 0x17] = move_type, power
    dol = bytearray(TM_OFFSET + (TM_COUNT + HM_COUNT) * TM_STRIDE + 16)
    dol[:16], dol[-16:] = b"DOL header guard", b"DOL suffix guard"
    for index, move in enumerate((*ORIGINAL_TM_MOVES, *ORIGINAL_HM_MOVES)):
        pos = TM_OFFSET + index * TM_STRIDE
        dol[pos] = int(index >= TM_COUNT)
        struct.pack_into(">H", dol, pos + 6, move)
        item = ITEM_OFFSET + (FIRST_TM_ITEM + index) * ITEM_STRIDE
        dol[item:item + ITEM_STRIDE] = b"\xA6" * ITEM_STRIDE
        struct.pack_into(">I", dol, item + 0x14, 10195 + index)
    return bytes(rel), bytes(dol), tables


def final_moves(dol):
    return [struct.unpack_from(">H", dol, TM_OFFSET + index * TM_STRIDE + 6)[0] for index in range(TM_COUNT)]


class TMRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_rel, cls.original_dol, cls.tables = fixture()

    def apply(self, rules=Rules(), seed="reproducible-CT", rel=None, dol=None):
        return apply_tm_tables(self.original_rel, rel or self.original_rel,
                               self.original_dol, dol or self.original_dol,
                               seed, rules, self.tables)

    def test_default_is_exact_identity_and_preserves_prior_changes(self):
        rel, dol = bytearray(self.original_rel), bytearray(self.original_dol)
        rel[-1] = 77
        dol[8] = 78  # An existing additional-section header is allowed.
        dol.extend(b"a pre-existing text section and alignment")
        output_rel, output_dol, report = self.apply(rel=bytes(rel), dol=bytes(dol))
        self.assertEqual(output_rel, bytes(rel))
        self.assertEqual(output_dol, bytes(dol))
        self.assertFalse(report["offensive_guarantee"]["applied"])
        self.assertEqual(report["rel_patch"]["allowed_bytes"], 0)
        self.assertEqual(report["dol_patch"]["allowed_bytes"], 0)

    def test_shuffle_moves_and_matching_existing_descriptions_without_fixed_points(self):
        rules = replace(Rules(), randomize_tm_moves=True)
        rel, dol, report = self.apply(rules)
        self.assertEqual(rel, self.original_rel)
        self.assertCountEqual(final_moves(dol), ORIGINAL_TM_MOVES)
        self.assertTrue(all(a != b for a, b in zip(final_moves(dol), ORIGINAL_TM_MOVES)))
        self.assertEqual(report["moved_tms"], 50)
        self.assertEqual(report["dol_patch"]["allowed_bytes"], 50 * 6)
        allowed = set()
        for index, move in enumerate(final_moves(dol)):
            source = ORIGINAL_TM_MOVES.index(move)
            desc = ITEM_OFFSET + (FIRST_TM_ITEM + index) * ITEM_STRIDE + 0x14
            self.assertEqual(struct.unpack_from(">I", dol, desc)[0], 10195 + source)
            allowed.update(range(desc, desc + 4))
            pos = TM_OFFSET + index * TM_STRIDE + 6
            allowed.update((pos, pos + 1))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(dol, self.original_dol)) if a != b))
        self.assertEqual(self.apply(rules), (rel, dol, report))
        self.assertNotEqual(final_moves(self.apply(rules, "another-seed")[1]), final_moves(dol))

    def test_universal_changes_only_50_bytes_for_each_real_species(self):
        rel, dol, report = self.apply(replace(Rules(), tm_compatibility_mode="universal"))
        allowed = set()
        for index in range(1, 5):
            pos = 64 + index * 0x11C + COMPAT_OFFSET
            self.assertEqual(rel[pos:pos + TM_COUNT], b"\x01" * TM_COUNT)
            self.assertEqual(rel[pos + TM_COUNT:pos + TM_COUNT + HM_COUNT],
                             self.original_rel[pos + TM_COUNT:pos + TM_COUNT + HM_COUNT])
            allowed.update(range(pos, pos + TM_COUNT))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(rel, self.original_rel)) if a != b))
        self.assertEqual(dol, self.original_dol)
        self.assertEqual(report["offensive_guarantee"]["species_without_offensive_tm"], [])
        self.assertEqual(report["hms"]["count"], 8)

    def test_type_mode_follows_final_species_types_and_final_tm_permutation(self):
        current = bytearray(self.original_rel)
        current[64 + 0x11C + 0x30:64 + 0x11C + 0x32] = bytes((11, 12))
        rules = Rules(True, "type", False)
        rel, dol, report = self.apply(rules, rel=bytes(current))
        moves = final_moves(dol)
        for index in range(1, 5):
            pos = 64 + index * 0x11C
            types = set(current[pos + 0x30:pos + 0x32])
            expected = bytes(int(self.original_rel[self.tables["moves"]["offset"] + move * 0x38 + 2] in types)
                             for move in moves)
            self.assertEqual(rel[pos + COMPAT_OFFSET:pos + COMPAT_OFFSET + TM_COUNT], expected)
        self.assertEqual(report["compatibility"][0]["types"], [11, 12])
        self.assertFalse(report["offensive_guarantee"]["applied"])

    def test_guard_adds_only_compatibility_and_reports_off_type_fallback(self):
        plain = self.apply(Rules(True, "type", False))
        guarded = self.apply(Rules(True, "type", True))
        self.assertEqual(plain[1], guarded[1])
        additions = guarded[2]["offensive_guarantee"]["added"]
        # Fire has only a status TM, Bug has no TM of its type in this fixture.
        self.assertEqual([row["species"] for row in additions], [1, 3])
        self.assertTrue(all(not row["matches_type"] for row in additions))
        allowed = {64 + row["species"] * 0x11C + COMPAT_OFFSET + row["tm"] - 1 for row in additions}
        self.assertEqual({i for i, (a, b) in enumerate(zip(plain[0], guarded[0])) if a != b}, allowed)
        self.assertEqual(guarded[2]["offensive_guarantee"]["species_without_offensive_tm"], [])

    def test_original_compatibility_ignores_guard_without_mutating_moves(self):
        without = self.apply(Rules(True, "original", False))
        with_guard = self.apply(Rules(True, "original", True))
        self.assertEqual(without[:2], with_guard[:2])
        self.assertEqual(with_guard[0], self.original_rel)
        self.assertFalse(with_guard[2]["offensive_guarantee"]["applied"])

    def test_random_draws_are_reproducible_and_isolated_from_tm_shuffle_and_guard(self):
        rules = Rules(False, "random", False)
        plain = self.apply(rules)
        shuffled = self.apply(replace(rules, randomize_tm_moves=True))
        self.assertEqual(plain[0], shuffled[0])
        self.assertEqual(plain, self.apply(rules))
        self.assertNotEqual(plain[0], self.apply(rules, "other-seed")[0])
        original_mode = self.apply(Rules(True, "original", True))
        universal_mode = self.apply(Rules(True, "universal", True))
        self.assertEqual(original_mode[1], universal_mode[1])
        self.assertTrue(any(row["changed_entries"] for row in plain[2]["compatibility"]))

    def test_rejects_wrong_flags_modes_seed_signatures_and_previous_tm_changes(self):
        for options in (Rules(1), Rules(False, "bogus"), Rules(False, "original", 1)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.apply(options)
        for seed in ("", "é" * 129, None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                self.apply(seed=seed)
        for pos in (TM_OFFSET, TM_OFFSET + 6,
                    ITEM_OFFSET + FIRST_TM_ITEM * ITEM_STRIDE + 0x14):
            current = bytearray(self.original_dol)
            current[pos] ^= 1
            with self.subTest(pos=pos), self.assertRaises(FormatError):
                self.apply(dol=bytes(current))
        current = bytearray(self.original_rel)
        current[64 + 0x11C + COMPAT_OFFSET + TM_COUNT] ^= 1
        with self.assertRaises(FormatError):
            self.apply(rel=bytes(current))
        with self.assertRaises(FormatError):
            self.apply(dol=self.original_dol[:-1])
        with self.assertRaises(FormatError):
            apply_tm_rules(self.original_rel, self.original_rel, self.original_dol,
                           self.original_dol, "seed", Rules())

    def test_extended_current_dol_remains_byte_exact_outside_tm_fields(self):
        current = bytearray(self.original_dol)
        current[8:12] = b"new!"
        current.extend(b"a previously appended text2 section")
        _, dol, report = self.apply(Rules(True, "universal", True), dol=bytes(current))
        self.assertEqual(dol[8:12], b"new!")
        self.assertEqual(dol[len(self.original_dol):], current[len(self.original_dol):])
        self.assertEqual(len(dol), len(current))
        self.assertTrue(report["dol_patch"]["outside_whitelist_unchanged"])


@unittest.skipUnless(Path("game/sys/main.dol").is_file() and Path("game/files/common.fsys").is_file(),
                     "local original PAL game is unavailable")
class LocalPALTMTests(unittest.TestCase):
    def test_original_pal_has_50_tms_8_hms_386_species_and_supported_guarantee(self):
        from colosseum_randomizer.engine.randomize_trainers import original_common
        rel = original_common(Path("game"))[2]
        dol = Path("game/sys/main.dol").read_bytes()
        output_rel, output_dol, report = apply_tm_rules(rel, rel, dol, dol, "PAL-CT-validation", Rules(True, "type", True))
        self.assertEqual(report["real_species_count"], 386)
        self.assertEqual(report["moved_tms"], 50)
        self.assertEqual(report["offensive_guarantee"]["species_without_offensive_tm"], [])
        self.assertEqual(len(output_rel), len(rel))
        self.assertEqual(len(output_dol), len(dol))
        self.assertEqual(report["rel_patch"]["allowed_bytes"], 386 * 50)
        with self.assertRaises(FormatError):
            apply_tm_rules(rel, rel, dol, dol, "seed", Rules(), tables={})
        changed_original = bytearray(dol)
        changed_original[-1] ^= 1
        with self.assertRaises(FormatError):
            apply_tm_rules(rel, rel, bytes(changed_original), dol, "seed", Rules())


if __name__ == "__main__":
    unittest.main()
