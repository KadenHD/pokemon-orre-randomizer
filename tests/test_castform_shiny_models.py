"""Execute weather rare selectors and their native Lugia-loader composition."""
import hashlib
from pathlib import Path
import struct
import unittest

from orre_randomizer.castform_shiny_models import (
    SHINY_RESOURCES, _HOOKS, _model_selector, _resources, install_castform_shiny_models,
)
from orre_randomizer.engine.analyze_game import FormatError, parse_dol
from orre_randomizer.engine.gift_move_hooks import branch
from orre_randomizer.xd_shadow_lugia_model import _model_stub as lugia_model_selector
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


def put_code(machine, address, payload):
    for at in range(0, len(payload), 4):
        machine.store(address + at, struct.unpack_from(">I", payload, at)[0], 4)


class CastformShinyModelTests(unittest.TestCase):
    def test_only_weather_models_with_native_rare_flag_select_alternate_pkx(self):
        for xd in (False, True):
            for model in (0, 249, 385, 413, 414, 415, 416, 417, 0x7FF0, 0xABCD019F):
                for rare in (0, 1, 0x100, 0x101):
                    with self.subTest(xd=xd, model=model, rare=rare):
                        machine = WrapperMachine(_model_selector(ADDRESS, RETURN, SHINY_RESOURCES, xd=xd))
                        mr, rr = (27, 29) if xd else (26, 28)
                        machine.reg[mr], machine.reg[rr] = model, rare
                        before = machine.reg.copy()
                        memory, link = machine.memory.copy(), machine.lr
                        machine.run()
                        active = model & 0xFFFF in (414, 415, 416) and rare & 0xFF != 0
                        expected = before.copy()
                        if xd:
                            if active:
                                expected[6], expected[7] = before[31], SHINY_RESOURCES[model & 0xFFFF]
                        else:
                            expected[23] = before[31]  # Native displaced mr r23,r31.
                            if active:
                                expected[29], expected[30] = 1, SHINY_RESOURCES[model & 0xFFFF]
                        self.assertEqual(machine.reg[1:], expected[1:])
                        self.assertEqual(machine.memory, memory)
                        self.assertEqual(machine.lr, link)
                        self.assertFalse(machine.calls)

    def test_xd_native_rare_assignment_skips_generic_tint_without_changing_lugia_selector(self):
        # Exact instructions observed at all three XD rare-table exits. The
        # existing Lugia selector remains at its own subsequent hook boundary.
        native, lugia = ADDRESS + 0x200, ADDRESS + 0x300
        for model in (249, 385, 414, 415, 416, 417):
            with self.subTest(model=model):
                machine = WrapperMachine(_model_selector(ADDRESS, native, SHINY_RESOURCES, xd=True))
                machine.reg[27], machine.reg[29], machine.reg[30] = model, 1, 0
                machine.reg[31], machine.reg[4], machine.reg[6], machine.reg[7] = 0x1BA, 0x03DA1E00, 0, 0
                native_words = [0x28060000, 0x41820018, 0x28070000, 0x41820010,
                                0x7CDF3378, 0x7CE43B78, 0x3BC00001,
                                branch(native + 0x1C, lugia)]
                put_code(machine, native, struct.pack(">8I", *native_words))
                put_code(machine, lugia, lugia_model_selector(lugia, RETURN))
                before = machine.reg.copy()
                memory = machine.memory.copy()
                machine.run(max_steps=180)
                self.assertEqual(machine.reg[3], before[31])
                if model in (414, 415, 416):
                    self.assertEqual(machine.reg[4], SHINY_RESOURCES[model])
                    self.assertEqual(machine.reg[30], 1)
                elif model == 417:
                    self.assertEqual(machine.reg[4], 0x7DF41E00)  # Existing shiny XD001 route.
                    self.assertEqual(machine.reg[30], 1)
                else:
                    self.assertEqual(machine.reg[4], before[4])
                    self.assertEqual(machine.reg[30], before[30])
                self.assertEqual(machine.reg[27:30], before[27:30])
                self.assertEqual(machine.reg[31], before[31])
                self.assertEqual(machine.memory, memory)
                self.assertEqual(machine.lr, RETURN)

    def test_colosseum_lugia_early_selector_can_jump_through_weather_hook_unchanged(self):
        from orre_randomizer.engine.postgame_lugia_model import MODEL_MARKER, _resource_selector
        loader = 0x801DE190
        weather = ADDRESS + 0x400
        group = 0x16E
        for rare, expected in ((0, 0x7DF31E00), (1, 0x7DF41E00)):
            with self.subTest(rare=rare):
                machine = WrapperMachine(_resource_selector(ADDRESS, loader, 0x800D84B0, group))
                machine.reg[3], machine.reg[26], machine.reg[28] = MODEL_MARKER, MODEL_MARKER, rare
                machine.store(loader + 0x14C, branch(loader + 0x14C, weather), 4)
                put_code(machine, weather, _model_selector(weather, RETURN, SHINY_RESOURCES, xd=False))
                before, memory = machine.reg.copy(), machine.memory.copy()
                machine.run(max_steps=160)
                self.assertEqual(machine.reg[26], 249)
                self.assertEqual(machine.reg[28], before[28])
                self.assertEqual(machine.reg[29:32], [1, expected, group])
                self.assertEqual(machine.reg[23], group)
                self.assertEqual(machine.memory, memory)
                self.assertEqual(machine.lr, RETURN)

    def test_invalid_duplicate_or_already_used_model_resources_are_rejected(self):
        invalid = ({}, {414: 1, 415: 2, 416: 3},
                   {414: True, 415: 0x7DA21E00, 416: 0x7DA31E00},
                   {414: -0x1E00, 415: 0x7DA21E00, 416: 0x7DA31E00},
                   {414: 0x100001E00, 415: 0x7DA21E00, 416: 0x7DA31E00},
                   {414: 0x7DA11E00, 415: 0x7DA11E00, 416: 0x7DA31E00},
                   {385: 0x7DA11E00, 415: 0x7DA21E00, 416: 0x7DA31E00})
        for resources in invalid:
            with self.subTest(resources=resources), self.assertRaises(FormatError):
                _resources(resources, b"unaltered original")
        with self.assertRaisesRegex(FormatError, "collides"):
            _resources(SHINY_RESOURCES, struct.pack(">I", 0x7DA21E00))
        self.assertEqual(_resources(SHINY_RESOURCES, b"unaltered original"), SHINY_RESOURCES)
        with self.assertRaisesRegex(FormatError, "unknown original"):
            install_castform_shiny_models(b"unknown", b"unknown", "GC6P01")

    def test_optional_retail_sources_install_in_six_regions_with_lugia_and_live_portraits(self):
        # Local runtime-research inputs are optional and never distributed.
        sources = {
            "GC6P01": Path("game/sys/main.dol"),
            "GC6E01": Path("build/region-compat-2026-11-02/dol-research/usa-main.dol"),
            "GC6J01": Path("build/region-compat-2026-11-02/dol-research/japan-main.dol"),
            **{"GXX" + region + "01": Path(f"build/xd-validation/{name}/main.dol")
               for region, name in (("P", "eu"), ("E", "us"), ("J", "jp"))},
        }
        if not all(path.is_file() for path in sources.values()):
            self.skipTest("Optional original regional research executables are absent")
        from orre_randomizer.castform_portraits import install_castform_portraits
        from orre_randomizer.engine.postgame_lugia_model import _install_hooks
        from orre_randomizer.xd_battle_rules import append_xd_dol_text
        from orre_randomizer.xd_shadow_lugia_model import _HOOKS as LUGIA_HOOKS
        for gid, path in sources.items():
            original = path.read_bytes()
            before_sha = hashlib.sha256(original).hexdigest()
            for compose in (False, True):
                with self.subTest(game_id=gid, compose=compose):
                    current = original
                    if compose:
                        if gid.startswith("GXX"):
                            at = LUGIA_HOOKS[gid][0]
                            current, _ = append_xd_dol_text(original, current, gid,
                                [(at, 0x7FE3FB78, lugia_model_selector)])
                        else:
                            current, _ = _install_hooks(original, current, 0x16E)
                        current, _ = install_castform_portraits(original, current, gid)
                    output, report = install_castform_shiny_models(original, current, gid)
                    hook = _HOOKS[gid][0] - (0x800030A0 if gid.startswith("GXX") else 0x80003000)
                    self.assertNotEqual(output[hook:hook + 4], current[hook:hook + 4])
                    self.assertEqual(output[hook + 4:hook + 16], current[hook + 4:hook + 16])
                    self.assertEqual(report["resources"], {str(k): v for k, v in SHINY_RESOURCES.items()})
                    self.assertTrue(report["save_data_unchanged"])
                    self.assertTrue(report["native_model_ids_preserved"])
                    self.assertTrue(any(section["name"] == "text2" for section in parse_dol(output)["sections"]))
                    with self.assertRaisesRegex(FormatError, "instruction window"):
                        install_castform_shiny_models(original, output, gid)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before_sha)


if __name__ == "__main__":
    unittest.main()
