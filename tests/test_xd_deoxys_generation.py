"""Execute initial form-tag hooks without replacing native personality draws."""
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.deoxys_identity import FORM_TAG
from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.gift_move_hooks import branch
from orre_randomizer.xd_battle_rules import TEXT1_TO_RAM
from orre_randomizer.xd_deoxys_generation import (
    _rows, _trainer, _hero, _reward_pre, _reward_clear, _wild, _capture_slot,
    install_xd_deoxys_generation, WILD, REWARDS, TRAINERS,
)
from tests.test_xd_deoxys_runtime import fixture as runtime_fixture
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine

STATE, RECORD, PARAMETER = 0x80500000, 0x80600000, 0x80700000


def fixture(game):
    data = bytearray(runtime_fixture(game))
    r, t = REWARDS[game], TRAINERS[game]
    hero, trainer, wild = r.hero_policy - 0x138 + TEXT1_TO_RAM, t.slot_lookup - 0x60, WILD[game]
    words = [(t.register + 4, 0x38610008), (trainer + 0x24, 0x7C9F2378),
             (trainer + 0x700, 0x7FE3FB78), (hero + 0x16C, 0x38610008),
             (wild + 0xF8, 0x1C7B001C), (wild + 0x214, 0x7C1F0378), (wild + 0x2EC, 0x7FE3FB78)]
    starter, gift = r.starter_policy + TEXT1_TO_RAM + 0x20, r.gift_setup + TEXT1_TO_RAM + 0x28
    words += [(starter - 4, 0x9001003C), (starter, branch(starter, hero, link=True)),
              (starter + 4, 0x7FC3F378 if game == "GXXJ01" else 0x7FE3FB78),
              (gift - 4, 0x9001001C), (gift, branch(gift, hero, link=True)), (gift + 4, 0xA0010010)]
    for at, word in words:
        struct.pack_into(">I", data, at - TEXT1_TO_RAM, word)
    return bytes(data)


def put(machine, address, payload):
    for index, value in enumerate(payload):
        machine.memory[address + index] = value


def make_record(machine, address=RECORD, *, species=410, tag=0, shadow=0):
    machine.store(address, species, 2)
    machine.store(address + 0xC, tag, 2)
    machine.store(address + 0xBA, shadow, 2)
    machine.store(address + 0x28, 0x12345678, 4)
    machine.store(address + 4, 77, 2)
    machine.store(address + 0x90, 120, 2)


class XDDeoxysGenerationTests(unittest.TestCase):
    def test_trainer_initialization_uses_shadow_or_deck_slot_and_preserves_existing_forms(self):
        rows = ((0, 37, FORM_TAG | 3), (0x1234, 5, FORM_TAG | 1))
        for shadow in (0, 37, 38):
            for species in (410, 411):
                for old_tag in (0, FORM_TAG | 2, 0x1234):
                    machine = WrapperMachine(_trainer(ADDRESS, RETURN, STATE, rows))
                    machine.reg[31] = RECORD
                    machine.store(machine.reg[1] + 0x38, 5, 4)
                    machine.store(STATE + 4, 0x1234, 4)
                    make_record(machine, species=species, tag=old_tag, shadow=shadow)
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run(max_steps=180)
                    expected = (FORM_TAG | (3 if shadow == 37 else 1)) if species == 410 and old_tag == 0 and shadow != 38 else old_tag
                    self.assertEqual(machine.load(RECORD + 0xC, 2), expected)
                    self.assertEqual(machine.reg[3], RECORD)
                    self.assertEqual(machine.reg[13:], before[13:])
                    changed = {at for at in set(memory) | set(machine.memory) if memory.get(at, 0) != machine.memory.get(at, 0)}
                    self.assertTrue(changed <= {RECORD + 0xC, RECORD + 0xD})
                    self.assertEqual(machine.lr, RETURN)

    def test_reward_activation_then_constructor_consumes_only_its_form_without_pid_edits(self):
        tags = {"starter": FORM_TAG | 2, "hordel-trade": FORM_TAG | 3}
        for starter in (False, True):
            for species in (410, 411):
                machine = WrapperMachine(_reward_pre(ADDRESS, RETURN, 0x9001003C, STATE, tags, starter=starter))
                machine.reg[0], machine.reg[4], machine.reg[30] = 0xABCD1234, PARAMETER, 8
                machine.store(PARAMETER + 2, species, 2)
                machine.run(max_steps=150)
                self.assertEqual(machine.load(machine.reg[1] + 0x3C, 4), 0xABCD1234)
                expected = (FORM_TAG | (2 if starter else 3)) if species == 410 else 0
                self.assertEqual(machine.load(STATE, 4), expected)
                constructor = WrapperMachine(_hero(ADDRESS, RETURN, STATE, ()))
                constructor.memory.update({a: v for a, v in machine.memory.items() if a < ADDRESS or a >= ADDRESS + 0x200})
                # Put back the initializer after sharing data, not caller code.
                put(constructor, ADDRESS, _hero(ADDRESS, RETURN, STATE, ()))
                constructor.reg[29] = PARAMETER
                target = constructor.reg[1] + 8
                make_record(constructor, target, species=species)
                constructor.store(PARAMETER + 4, 0, 2)
                original_pid = constructor.load(target + 0x28, 4)
                constructor.run(max_steps=150)
                self.assertEqual(constructor.load(target + 0xC, 2), expected)
                self.assertEqual(constructor.load(target + 0x28, 4), original_pid)
                self.assertEqual(constructor.load(STATE, 4), 0)
                self.assertEqual(constructor.reg[3], target)

    def test_reward_clear_clears_failed_activation_and_replays_native_load(self):
        machine = WrapperMachine(_reward_clear(ADDRESS, RETURN, 0xA0010010, STATE))
        machine.store(STATE, FORM_TAG | 3, 4)
        machine.store(machine.reg[1] + 0x10, 0x1234, 2)
        machine.run(max_steps=80)
        self.assertEqual(machine.load(STATE, 4), 0)
        self.assertEqual(machine.reg[0], 0x1234)

    def test_hero_shadow_initialization_also_covers_cached_pid_path(self):
        machine = WrapperMachine(_hero(ADDRESS, RETURN, STATE, ((0, 37, FORM_TAG | 1),)))
        target = machine.reg[1] + 8
        machine.reg[29] = PARAMETER
        machine.store(PARAMETER + 4, 37, 2)
        make_record(machine, target, shadow=37)
        machine.run(max_steps=150)
        self.assertEqual(machine.load(target + 0xC, 2), FORM_TAG | 1)
        self.assertEqual(machine.load(target + 0x28, 4), 0x12345678)
        self.assertEqual(machine.calls, [])  # No PID generator or RNG is invoked.

    def test_wild_initialization_recalculates_after_tag_without_changing_personality(self):
        recalculate = 0x80141CD4
        machine = WrapperMachine(_wild(ADDRESS, RETURN, ((2, 1, FORM_TAG | 2),), recalculate))
        target, original_stack = machine.reg[1] + 8, machine.reg[1]
        machine.reg[31] = 0x80404000
        machine.store(original_stack + 0xD0, 2, 4)
        machine.store(original_stack + 0xD4, 1, 4)
        make_record(machine, target)
        def recalc(state):
            self.assertEqual(state.reg[3], target)
            self.assertEqual(state.load(target + 0xC, 2), FORM_TAG | 2)
            state.clobber_volatile()
        machine.callbacks[recalculate] = recalc
        before = machine.reg.copy()
        machine.run(max_steps=220)
        self.assertEqual(machine.load(target + 0x28, 4), 0x12345678)
        self.assertEqual(machine.reg[3], before[31])
        self.assertEqual(machine.reg[13:], before[13:])
        self.assertEqual(machine.reg[1], original_stack)
        self.assertEqual(machine.lr, RETURN)

    def test_native_slot_capture_keeps_original_assignment(self):
        machine = WrapperMachine(_capture_slot(ADDRESS, RETURN))
        machine.reg[3:5] = [532, RECORD]
        machine.run(max_steps=40)
        self.assertEqual(machine.reg[31], RECORD)
        self.assertEqual(machine.load(machine.reg[1] + 0x38, 4), 532)

    def test_plan_validation_and_empty_plan(self):
        self.assertEqual(_rows({"starter": 0x80000001}, {2: 0xC0000001}, {}, {("rock", 1): 1})[0], {"starter": FORM_TAG | 2})
        for args in (({"bad": 1}, {}, {}, {}), ({"starter": 0}, {}, {}, {}),
                     ({}, {84: 1}, {}, {}), ({}, {}, {0x1234: {0: 1}}, {}),
                     ({}, {}, {}, {("rock", 4): 1})):
            with self.assertRaises(ValueError):
                _rows(*args)
        self.assertEqual(install_xd_deoxys_generation(b"", b"", "GXXP01", rewards={}, shadows={}, decks={}, poke_spots={})[0], b"")

    def test_three_synthetic_regions_refuse_foreign_hooks_and_keep_byte_allowlist(self):
        for game in WILD:
            original = fixture(game)
            plans = dict(rewards={"starter": 0x80000001, "hordel-trade": 0xC0000001},
                         shadows={37: 0x40000001}, decks={0x1234: {5: 0x80000001}}, poke_spots={("cave", 2): 1})
            with patch.dict("orre_randomizer.xd_deoxys_generation.ORIGINALS", {game: {"sha256": hashlib.sha256(original).hexdigest()}}):
                output, report = install_xd_deoxys_generation(original, original, game, **plans)
                self.assertEqual(len(report["hooks"]), 11)
                self.assertTrue(report["native_pid_generation_and_rng_unchanged"])
                self.assertGreater(report["state"], 0x80000000)
                for hook in report["hooks"]:
                    self.assertEqual(u32(output, hook["hook_address"] - TEXT1_TO_RAM) & 3, 0)
                data = bytearray(original)
                at = report["hooks"][0]["hook_address"]
                struct.pack_into(">I", data, at - TEXT1_TO_RAM, branch(at, 0x80006000))
                with self.assertRaises(FormatError):
                    install_xd_deoxys_generation(original, bytes(data), game, **plans)

    def test_optional_three_retail_regions_compose_with_runtime_and_spinda(self):
        from orre_randomizer.xd_deoxys_runtime import install_xd_deoxys_forms
        from orre_randomizer.xd_spinda import apply_spinda_pids
        from orre_randomizer.xd_spinda_trainers import apply_spinda_trainer_pids
        sources = {"GXXP01": Path("build/xd-validation/eu/main.dol"), "GXXE01": Path("build/xd-validation/us/main.dol"),
                   "GXXJ01": Path("build/xd-validation/jp/main.dol")}
        if not all(path.is_file() for path in sources.values()):
            self.skipTest("Optional regional research originals are absent")
        for game, path in sources.items():
            original = path.read_bytes()
            current, _ = install_xd_deoxys_forms(original, original, game)
            current, report = install_xd_deoxys_generation(original, current, game,
                rewards={"starter": 0x80000001, "hordel-trade": 0x40000001}, shadows={37: 0xC0000001},
                decks={0x1234: {5: 0x40000001}}, poke_spots={("cave", 3): 0x80000001})
            current, _ = apply_spinda_pids(original, current, game, {"starter": 0xABCD1234, "hordel-trade": 0x1234ABCD})
            current, _ = apply_spinda_trainer_pids(original, current, game, {0x1234: {8: 0xABCD1234}})
            self.assertTrue(report["unrelated_executable_bytes_preserved"])
            self.assertGreater(len(current), len(original))
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
