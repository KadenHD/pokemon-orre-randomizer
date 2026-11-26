"""Execute XD form dispatch instructions and qualify all regional hooks."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.deoxys import BASE_STATS
from orre_randomizer.deoxys_identity import FORM_TAG
from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.gift_move_hooks import branch
from orre_randomizer.xd_battle_rules import ARENA, ARENA_INITIALIZERS, TEXT1_TO_RAM
from orre_randomizer.xd_deoxys_runtime import (
    LAYOUTS, _selector, _menu_form, _face_form, _pid_cache, _cached_model, _stat,
    install_xd_deoxys_forms,
    TRANSFORM_FUNCTIONS,
    ANT_LAYOUTS, _bodies, _body_resource,
)
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine

RECORD, NATIVE = 0x80401000, 0x80142E7C
BODY_RESOURCES = {("attack", False): 0x1BF63200, ("attack", True): 0x1BF73200,
                  ("defense", False): 0x1BF93200, ("defense", True): 0x1BFA3200,
                  ("speed", False): 0x1BFB3200, ("speed", True): 0x1BFC3200}


def record(machine, species=410, tag=FORM_TAG):
    machine.store(RECORD, species, 2)
    machine.store(RECORD + 0x0C, tag, 2)
    machine.store(RECORD + 0x28, 0xDEADBEEF, 4)


def fixture(game):
    layout = LAYOUTS[game]
    stat, menu, face, battle, switch, ceremony, evolve, gba, gba_sel, table, getter, fight_sel, loader, pid_getter = layout
    size = (table - TEXT1_TO_RAM + 80 + 31) & ~31
    data = bytearray(size)
    for position, value in ((0, 0x100), (0x48, TEXT1_TO_RAM + 0x100), (0x90, size - 0x100),
                            (0xD8, 0x80400000), (0xDC, 0x100), (0xE0, TEXT1_TO_RAM + 0x100)):
        struct.pack_into(">I", data, position, value)
    section, setter, store = ARENA[game]
    struct.pack_into(">II", data, setter - TEXT1_TO_RAM, store, 0x4E800020)
    struct.pack_into(">II", data, ARENA_INITIALIZERS[game] - TEXT1_TO_RAM,
                     0x3C600000 | ((section + 0x8000) >> 16), 0x38630000 | section & 0xFFFF)
    prefix = bytes.fromhex("9421ffd07c0802a690010034bee1000c7c771b787c9823787cb92b78")
    data[stat - TEXT1_TO_RAM:stat - TEXT1_TO_RAM + len(prefix)] = prefix
    data[stat - TEXT1_TO_RAM + 0x44:stat - TEXT1_TO_RAM + 0x54] = bytes.fromhex("7fe4fb787f45d3783860000038c00000")
    calls = [(stat + 0x54, getter), (battle + 0x98, fight_sel), (switch + 0x110, fight_sel)]
    calls += [(gba + relative, gba_sel) for relative in (0x134, 0x188, 0x1E0, 0x238, 0x290)]
    calls += [(ceremony + 0x68, pid_getter), (ceremony + 0x9C, loader),
              (evolve + 0x44, pid_getter), (evolve + 0x78, loader)]
    visitor, any_body, generic, body_getter = ANT_LAYOUTS[game]
    for base, relative, owner in ((visitor, 0x114, 30), (any_body, 0x114, 30), (generic, 0x120, 29)):
        prefix = bytes.fromhex("9421ff007c0802a638a0003490010104bf6100ec7c9e23787c7d1b7838800000"
                    if owner == 30 else
                    "9421ff007c0802a638a000349001010493e100fc7c7f1b7893c100f893a100f47c9d237838800000938100f0")
        data[base - TEXT1_TO_RAM:base - TEXT1_TO_RAM + len(prefix)] = prefix
        calls.append((base + relative, body_getter))
    for at, target in calls:
        struct.pack_into(">I", data, at - TEXT1_TO_RAM, branch(at, target, link=True))
    for at, word in ((menu + 0x9C, 0x38000000), (face + 0x20, 0x7C9D2378)):
        struct.pack_into(">I", data, at - TEXT1_TO_RAM, word)
    at = TRANSFORM_FUNCTIONS[game] - TEXT1_TO_RAM
    data[at:at + 8] = bytes.fromhex("9421ffa07c0802a6")
    struct.pack_into(">I", data, at + 0xF4, 0x3B600000)
    data[table - TEXT1_TO_RAM:table - TEXT1_TO_RAM + 80] = b"".join(struct.pack(">5I", *row[1:]) for row in BASE_STATS.values())
    return bytes(data)


class XDDeoxysRuntimeTests(unittest.TestCase):
    def test_chamber_bodies_use_all_six_resources_and_preserve_normal_and_other_species(self):
        self.assertEqual(_bodies(BODY_RESOURCES), BODY_RESOURCES)
        for owner in (29, 30):
            for species in (249, 410, 411):
                for form in range(4):
                    for shiny in (0, 1):
                        machine = WrapperMachine(_body_resource(ADDRESS, NATIVE, owner, BODY_RESOURCES))
                        machine.reg[3:5] = [species, shiny]
                        machine.reg[owner] = RECORD
                        record(machine, species, FORM_TAG | form)
                        calls = []
                        def native(state):
                            calls.append(tuple(state.reg[3:5]))
                            state.reg[3] = 0x1BF83200 if shiny else 0x1BF53200
                        machine.callbacks[NATIVE] = native
                        before, memory = machine.reg.copy(), machine.memory.copy()
                        machine.run(max_steps=150)
                        tagged = species == 410 and form != 0
                        name = ("normal", "attack", "defense", "speed")[form]
                        expected = BODY_RESOURCES[name, bool(shiny)] if tagged else (0x1BF83200 if shiny else 0x1BF53200)
                        self.assertEqual(machine.reg[3], expected)
                        self.assertEqual(calls, [] if tagged else [(species, shiny)])
                        self.assertEqual(machine.reg[4], before[4])
                        self.assertEqual(machine.reg[13:], before[13:])
                        self.assertEqual(machine.memory, memory)
                        self.assertEqual(machine.lr, RETURN)
        for invalid in ({}, {**BODY_RESOURCES, ("attack", False): 0x1BF53200},
                        {**BODY_RESOURCES, ("attack", False): 0},
                        {**BODY_RESOURCES, ("attack", False): 0x7DB41201},
                        {**BODY_RESOURCES, ("attack", False): BODY_RESOURCES["attack", True]}):
            with self.assertRaises(FormatError):
                _bodies(invalid)
    def test_native_battle_and_gba_selectors_only_override_tagged_real_records(self):
        for owner in (19, 29, 30):
            for species in (410, 411):
                for tag in (0, 0x1234, *(FORM_TAG | form for form in range(4))):
                    machine = WrapperMachine(_selector(ADDRESS, NATIVE, owner))
                    machine.reg[3], machine.reg[owner] = 0x80405000, RECORD
                    record(machine, species, tag)
                    machine.callbacks[NATIVE] = lambda m: m.reg.__setitem__(3, 99)
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run(max_steps=100)
                    tagged = species == 410 and tag & 0xFFFC == FORM_TAG
                    self.assertEqual(machine.reg[3], tag & 3 if tagged else 99)
                    self.assertEqual(machine.reg[13:], before[13:])
                    self.assertEqual(machine.memory, memory)
                    self.assertEqual(len(machine.calls), 0 if tagged else 1)
                    self.assertEqual(machine.lr, RETURN)

    def test_menu_models_and_faces_follow_tag_while_preserving_foreign_species(self):
        for species in (410, 411):
            for tag in (0, *(FORM_TAG | form for form in range(4))):
                for portrait in (False, True):
                    machine = WrapperMachine((_face_form if portrait else _menu_form)(ADDRESS, RETURN))
                    machine.reg[4], machine.reg[28], machine.reg[31] = 2, RECORD, RECORD
                    record(machine, species, tag)
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run(max_steps=100)
                    tagged = species == 410 and tag & 0xFFFC == FORM_TAG
                    self.assertEqual(machine.reg[29] if portrait else machine.reg[0],
                                     tag & 3 if tagged else 2 if portrait else 0)
                    self.assertEqual(machine.reg[28], before[28])
                    self.assertEqual(machine.reg[31], before[31])
                    self.assertEqual(machine.memory, memory)
                    self.assertEqual(machine.lr, RETURN)

    def test_ceremony_form_cache_returns_exact_pid_and_only_writes_native_padding(self):
        for species in (410, 411):
            for tag in (0, *(FORM_TAG | form for form in range(4))):
                machine = WrapperMachine(_pid_cache(ADDRESS, NATIVE))
                machine.reg[3] = RECORD
                record(machine, species, tag)
                def native(state):
                    self.assertEqual(state.reg[3], RECORD)
                    state.clobber_volatile()
                    state.reg[3] = 0xDEADBEEF
                machine.callbacks[NATIVE] = native
                before, memory = machine.reg.copy(), machine.memory.copy()
                machine.run(max_steps=100)
                self.assertEqual(machine.reg[3], 0xDEADBEEF)
                expected = tag & 3 if species == 410 and tag & 0xFFFC == FORM_TAG else 0xFFFFFFFF
                self.assertEqual(machine.load(before[1] + 8, 4), expected)
                self.assertEqual(machine.reg[13:], before[13:])
                self.assertEqual({at: v for at, v in machine.memory.items() if not before[1] + 8 <= at < before[1] + 12}, memory)
                self.assertEqual(machine.lr, RETURN)

    def test_cached_model_uses_form_only_for_deoxys_and_keeps_native_shiny_argument(self):
        for model in (249, 410, 411, 417):
            for form in (0, 1, 2, 3, 4, 0xFFFFFFFF):
                machine = WrapperMachine(_cached_model(ADDRESS, NATIVE))
                machine.reg[3:6] = [model, 0xDEADBEEF, 1]
                machine.store(machine.reg[1] + 8, form, 4)
                calls = []
                machine.callbacks[NATIVE] = lambda m: calls.append(tuple(m.reg[3:6]))
                machine.run(max_steps=100)
                self.assertEqual(calls, [(model, form if model == 410 and form <= 3 else 0xDEADBEEF, 1)])

    def test_native_stat_formula_only_receives_tagged_non_hp_base_values(self):
        for species in (410, 411):
            for form, name in enumerate(BASE_STATS):
                for selector, column in ((3, 0), (4, 1), (5, 2), (6, 3), (7, 4), (8, 5)):
                    machine = WrapperMachine(_stat(ADDRESS, NATIVE, BASE_STATS))
                    machine.reg[3:7], machine.reg[23] = [0, 410, selector, 0], RECORD
                    record(machine, species, FORM_TAG | form)
                    machine.callbacks[NATIVE] = lambda m: m.reg.__setitem__(3, 27)
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run(max_steps=130)
                    expected = BASE_STATS[name][column] if species == 410 and form and selector != 3 else 27
                    self.assertEqual(machine.reg[3], expected)
                    self.assertEqual(machine.reg[13:], before[13:])
                    self.assertEqual(machine.memory, memory)

    def test_three_regions_install_with_exact_hook_and_byte_allowlist_and_refuse_foreign_calls(self):
        for game in LAYOUTS:
            original = fixture(game)
            with patch.dict("orre_randomizer.xd_deoxys_runtime.ORIGINALS", {game: {"sha256": hashlib.sha256(original).hexdigest()}}):
                output, report = install_xd_deoxys_forms(original, original, game)
                self.assertEqual(len(report["hooks"]), 18)
                self.assertTrue(report["unrelated_executable_bytes_preserved"])
                self.assertEqual(len(output) % 32, 0)
                for entry in report["hooks"]:
                    word = u32(output, entry["hook_address"] - TEXT1_TO_RAM)
                    self.assertEqual(word & 3, 0 if entry["kind"] in ("menu_model", "portrait", "transform") else 1)
                for call in (LAYOUTS[game][0] + 0x54, LAYOUTS[game][3] + 0x98,
                             LAYOUTS[game][1] + 0x9C, LAYOUTS[game][2] + 0x20):
                    foreign = bytearray(original)
                    struct.pack_into(">I", foreign, call - TEXT1_TO_RAM, branch(call, 0x80008000))
                    with self.assertRaises(FormatError):
                        install_xd_deoxys_forms(original, bytes(foreign), game)
                with self.assertRaises(FormatError):
                    install_xd_deoxys_forms(original, output, game)

    def test_unknown_original_and_invalid_stats_are_refused(self):
        with self.assertRaises(FormatError):
            install_xd_deoxys_forms(b"modified", b"modified", "GXXP01")
        original = fixture("GXXP01")
        with patch.dict("orre_randomizer.xd_deoxys_runtime.ORIGINALS", {"GXXP01": {"sha256": hashlib.sha256(original).hexdigest()}}):
            with self.assertRaises(FormatError):
                install_xd_deoxys_forms(original, original, "GXXP01", base_stats={})

    def test_optional_retail_originals_and_owned_lugia_castform_composition(self):
        sources = {"GXXP01": Path("build/xd-validation/eu/main.dol"),
                   "GXXE01": Path("build/xd-validation/us/main.dol"),
                   "GXXJ01": Path("build/xd-validation/jp/main.dol")}
        if not all(p.is_file() for p in sources.values()):
            self.skipTest("Optional regional research originals are absent")
        from orre_randomizer.xd_shadow_lugia_model import _install_retained_displays, _install_retained_ceremony
        from orre_randomizer.castform_portraits import install_castform_portraits
        from orre_randomizer.castform_shiny_models import install_castform_shiny_models
        from orre_randomizer.engine.shadow_lugia_face import install_xd_shadow_lugia_face
        for game, source in sources.items():
            original = source.read_bytes()
            current, _ = _install_retained_displays(original, original, game)
            current, _ = _install_retained_ceremony(original, current, game)
            current, _ = install_xd_shadow_lugia_face(original, current, game)
            current, _ = install_castform_portraits(original, current, game)
            current, _ = install_castform_shiny_models(original, current, game)
            output, report = install_xd_deoxys_forms(original, current, game)
            self.assertGreater(len(output), len(current))
            self.assertTrue(report["native_models_shiny_assets_and_animations_preserved"])
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
