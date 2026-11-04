import math
import struct
from types import SimpleNamespace

import unittest

from colosseum_randomizer.engine.analyze_game import FormatError
from colosseum_randomizer.engine.inspect_tables import u16
from colosseum_randomizer.options import Options
from colosseum_randomizer.xd_battle_rules import (
    ARENA,
    DOL_CONTRACTS,
    DPKM_MOVES,
    _experience_stub,
    _purification_stub,
    apply_deck_rules,
    apply_dol_battle_rules,
    apply_shadow_rules,
    experience_numerator,
)
from tests.test_qol_rules import HookMachine


def _options(**values):
    return SimpleNamespace(**(vars(Options.none()) | values))


def _deck_fixture():
    start = 0x30 + 2 * 0x38
    deck = bytearray(start + 7 * 0x20)
    struct.pack_into(">4sII", deck, 0x10, b"DTNR", 0x10 + 2 * 0x38, 2)
    struct.pack_into(">4sII", deck, start - 0x10, b"DPKM", 0x10 + 7 * 0x20, 7)
    struct.pack_into(">HHHH", deck, 0x20 + 0x1C, 1, 2, 3, 1)
    deck[0x20 + 4] = 0b1000
    struct.pack_into(">H", deck, 0x58 + 0x1C, 2)
    deck[0x58 + 4] = 1
    for i, level in enumerate((35, 36, 51, 48, 11, 29), 1):
        pos = start + i * 0x20
        struct.pack_into(">HBBH", deck, pos, 1, level, 10, {1: 202, 4: 213}.get(i, 0))
        struct.pack_into(">4H", deck, pos + 0x14, 1, 2, 3, 4)
    return bytes(deck), start


class _MoveRandomizer:
    species = {
        1: {"types": (0, 1), "total": 200},
        2: {"types": (1, 2), "total": 300},
        3: {"types": (1, 2), "total": 350},
        4: {"types": (3, 4), "total": 300},
    }
    catalog = {move: {"type": 10, "power": 60, "index": move} for move in range(1, 9)}

    def moves(self, seed, key, species_id, level, before):
        return [5, 6, 7, 8]


def _patch_deck(deck, options, current=None):
    return apply_deck_rules(
        deck, deck if current is None else current, "Story", {1: 4, 2: 5}, "fixture", options,
        move_randomizer=_MoveRandomizer(), edges={1: [(0, 4, 16, 2)]},
        protected_shadows={2},
    )


class XDBattleRulesTests(unittest.TestCase):
    def test_xd_battle_rules_only_change_referenced_writable_fields(self):
        native, start = _deck_fixture()
        options = _options(progressive_levels=True, early_level_multiplier=0.5, mid_level_multiplier=1.5,
                           late_level_multiplier=2, randomize_trainer_moves=True, randomize_held_items=True,
                           useful_held_items_only=True, trainer_force_evolved=True, trainer_evolution_level=50)
        output, report = _patch_deck(native, options)
        assert (output, report) == _patch_deck(native, options)
        assert [output[start + i * 0x20 + 2] for i in range(1, 7)] == [18, 54, 100, 72, 11, 29]
        assert [u16(output, start + i * 0x20) for i in range(1, 7)] == [1, 2, 2, 1, 1, 1]
        assert [edit["shadow_id"] for edit in report["trainer_move_edits"]] == [0, 0, 0, 1]
        assert [edit["index"] for edit in report["trainer_policy_edits"]] == [2, 3]
        assert [edit["shadow_id"] for edit in report["held_item_edits"]] == [0, 1]
        assert all(edit["after"] not in (0, 186, 202, 213) for edit in report["held_item_edits"])
        allowed = {start + i * 0x20 + field for i in range(1, 5)
                   for field in (0, 1, 2, 4, 5, *range(0x14, 0x1C))}
        assert {i for i, (a, b) in enumerate(zip(native, output, strict=True)) if a != b} <= allowed
        assert [u16(output, start + 4 * 0x20 + field) for field in DPKM_MOVES] == [5, 6, 7, 8]
        assert _patch_deck(native, _options())[0] == native


    def test_xd_trainer_theme_preserves_a_feasible_original_common_type(self):
        native, start = _deck_fixture()
        output, report = _patch_deck(native, _options(randomize_trainers=True, trainer_theme_mode="preserve",
                                                    trainer_force_evolved=True, trainer_evolution_level=36))
        assert {edit["type"] for edit in report["trainer_policy_edits"]} == {1}
        assert all(u16(output, start + i * 0x20) in (2, 3) for i in range(1, 4))
        assert u16(output, start + 4 * 0x20) == 1


    def test_xd_shadow_rates_preserve_protected_rows_gauge_and_capture_level(self):
        dark = bytearray(0x20 + 128 * 0x18)
        struct.pack_into(">4sII", dark, 0x10, b"DDPK", 0x10 + 128 * 0x18, 128)
        for sid, index, catch_rate in ((1, 4, 33), (2, 5, 3), (3, 8, 225)):
            pos = 0x20 + sid * 0x18
            struct.pack_into(">BBBBHHH", dark, pos, 0, catch_rate, 11, 0x80, 0, index, 1501)
        dark = bytes(dark)
        slots = {1: 4, 2: 5, 3: 8}
        options = _options(capture_rate_multiplier=2, minimum_catch_rate=80)
        output, report = apply_shadow_rules(dark, slots, options, protected_shadows={2})
        assert [row["after"] for row in report["capture_edits"]] == [80, 255]
        allowed = {0x20 + sid * 0x18 + 1 for sid in (1, 3)}
        assert {i for i, (a, b) in enumerate(zip(dark, output, strict=True)) if a != b} == allowed
        assert apply_shadow_rules(dark, slots, _options(), protected_shadows={2})[0] == dark
        with self.assertRaisesRegex(FormatError, "invalid XD Shadow record"):
            apply_shadow_rules(dark, {1: 5}, options, protected_shadows={2})

    def test_xd_battle_experience_hook_scales_award_and_retains_native_zero(self):
        for game_id, (section, _, _) in ARENA.items():
            continuation = DOL_CONTRACTS[game_id]["experience"][0] + 0x1C
            address = section + 32
            for rate in (0.25, 2.25, 5):
                for award in (0, 1, 17, 65535, 65536):
                    with self.subTest(game_id=game_id, rate=rate, award=award):
                        hook = HookMachine(_experience_stub(address, continuation, experience_numerator(rate)), address)
                        hook.reg[18] = award
                        before, fp, lr = hook.reg.copy(), hook.fp.copy(), hook.lr
                        hook.run(continuation)
                        expected = max(bool(award), math.floor(min(65535, award) * rate + 0.5))
                        self.assertEqual(hook.reg[18], expected)
                        self.assertEqual(hook.reg[3], before[19])
                        self.assertEqual(hook.lr, lr)
                        self.assertEqual(hook.fp, fp)
                        self.assertEqual([v for i, v in enumerate(hook.reg) if i not in (3, 11, 12, 18)],
                                         [v for i, v in enumerate(before) if i not in (3, 11, 12, 18)])

    def test_xd_purification_hook_scales_only_negative_changes_before_zero_clamp(self):
        for game_id, (section, _, _) in ARENA.items():
            continuation = DOL_CONTRACTS[game_id]["purification"][0] + 0x2C
            address = section + 32
            for gauge, delta in ((20, -2), (20, -10), (20, 2), (20, 0)):
                with self.subTest(game_id=game_id, gauge=gauge, delta=delta):
                    hook = HookMachine(_purification_stub(address, continuation, 4), address)
                    # Native continuation loads zero, compares, and clamps.
                    clamp = bytes.fromhex("c0029d88fc01004040800008fc200090")
                    hook.memory.update({continuation + i: byte for i, byte in enumerate(clamp)})
                    hook.fp[1], hook.fp[31] = gauge, delta
                    before, fp, lr = hook.reg.copy(), hook.fp.copy(), hook.lr
                    hook.run(continuation + len(clamp))
                    self.assertEqual(hook.fp[1], max(0, gauge + delta * (4 if delta < 0 else 1)))
                    self.assertEqual(hook.lr, lr)
                    self.assertEqual(hook.fp[2:31], fp[2:31])
                    self.assertEqual(hook.reg[:12], before[:12])
                    self.assertEqual(hook.reg[13:], before[13:])

    def test_neutral_dol_battle_rules_return_current_without_relocation(self):
        output, report = apply_dol_battle_rules(b"original", b"existing edits", "GXXE01", _options())
        self.assertEqual(output, b"existing edits")
        self.assertEqual(report["hooks"], [])
