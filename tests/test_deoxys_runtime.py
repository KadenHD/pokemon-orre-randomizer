"""Execute scoped Deoxys selectors and verify their native hook composition."""
from contextlib import ExitStack
from dataclasses import replace
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.castform_layouts import LAYOUTS as WEATHER_LAYOUTS
from orre_randomizer.castform_shiny_models import (
    SHINY_RESOURCES, _model_selector as weather_selector, install_castform_shiny_models,
)
from orre_randomizer.deoxys_resources import FORMS, MODEL_GROUPS, MODEL_RESOURCES
from orre_randomizer.deoxys_identity import (
    FORM_TAG, FORM_OFFSETS, RECORD_SIZES, MODEL_MARKERS, saved_form,
    with_saved_form, form_reader, form_from_tag, game_family,
    owned_form_reader, SAVEDATA_GETTERS,
    transform_tag_copy,
)
from orre_randomizer.deoxys_runtime import (
    DEOXYS, STAT_FUNCTIONS, STAT_GETTERS, STAT_WINDOWS, _model_selector,
    _resources, _stat_selector, _stats, install_deoxys_forms, _record_identity, _battle_identity,
    TRANSFORM_FUNCTIONS,
)
from orre_randomizer.engine.analyze_game import FormatError, parse_dol, u32
from orre_randomizer.engine.dol_regions import LAYOUTS
from orre_randomizer.engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from orre_randomizer.engine.postgame_lugia_model import (
    _LAYOUTS as MODEL_LAYOUTS, _resource_selector as lugia_selector, MODEL_MARKER,
    _MENU_GETTERS, _CEREMONY_GETTERS,
)
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


STATS = {
    "normal": (50, 150, 50, 150, 50, 150),
    "attack": (50, 180, 20, 180, 20, 150),
    "defense": (50, 70, 160, 70, 160, 90),
    "speed": (50, 95, 90, 95, 90, 180),
}
RECORD = 0x80401000
GETTER = 0x8012640C


def put(machine, address, payload):
    for offset, value in enumerate(payload):
        machine.memory[address + offset] = value


def destination(at, word):
    value = word & 0x3FFFFFC
    return at + (value - 0x4000000 if value & 0x2000000 else value)


def fixture(layout):
    """Sparse test DOL, using independent captured retail instruction windows."""
    function, loader = STAT_FUNCTIONS[layout.game_id], MODEL_LAYOUTS[layout.game_id][0]
    size = (max(loader + 0x280, _CEREMONY_GETTERS[layout.game_id] + 0x20,
                MODEL_LAYOUTS[layout.game_id][3] + TEXT_TO_RAM + 249 * 12 + 4) - TEXT_TO_RAM + 31) & ~31
    data = bytearray(size)
    for at, value in ((0, 0x100), (0x48, 0x80003100), (0x90, size - 0x100),
                      (0xD8, 0x80400000), (0xDC, 0x100), (0xE0, 0x80003100),
                      (layout.set_arena_lo - TEXT_TO_RAM, layout.arena_lo_store)):
        struct.pack_into(">I", data, at, value)
    prefix = bytes.fromhex(
        "9421ffd07c0802a638a0006e38c0000090010034bf0100107c9b23787c7e1b7838800000")
    first = function - TEXT_TO_RAM
    data[first:first + len(prefix)] = prefix
    struct.pack_into(">I", data, first + 0x24, branch(function + 0x24, STAT_GETTERS[layout.game_id], link=True))
    # Keep one native HP base-stat request separate from the five form hooks.
    hp = function + 0xC4
    data[hp - TEXT_TO_RAM - 12:hp - TEXT_TO_RAM] = bytes.fromhex("3860000038a0000338c00000")
    struct.pack_into(">I", data, hp - TEXT_TO_RAM, branch(hp, STAT_GETTERS[layout.game_id], link=True))
    windows = (
        (0x198, "3860000038a0000438c000004bffe9195478043e"),
        (0x2A8, "3860000038a0000538c000004bffe809547a043e"),
        (0x3B4, "3860000038a0000838c000004bffe6fd547a043e"),
        (0x4C0, "3860000038a0000638c000004bffe5f1547a043e"),
        (0x5CC, "3860000038a0000738c000004bffe4e5547a043e"),
    )
    for relative, value in windows:
        at = first + relative - 12
        data[at:at + 20] = bytes.fromhex(value)
    loader_prefix = bytes.fromhex(
        "9421ffd07c0802a690010034bee1000c7c7a1b785463043f7c9b23787cbc2b783ba00000")
    at = loader - TEXT_TO_RAM
    data[at:at + len(loader_prefix)] = loader_prefix
    struct.pack_into(">II", data, at + 0x28,
                     0x800D84A0 if layout.game_id == "GC6J01" else 0x800D84B0, 0x7C030040)
    struct.pack_into(">I", data, MODEL_LAYOUTS[layout.game_id][3] + 249 * 12, 0x16E)
    for call, prefix, suffix in (
            (MODEL_LAYOUTS[layout.game_id][1], "7fc4f3785783043e", "7c601b7838600008"),
            (MODEL_LAYOUTS[layout.game_id][2], "7c651b7857e3043e", "7c601b7838610010")):
        pos = call - TEXT_TO_RAM
        data[pos - 8:pos] = bytes.fromhex(prefix)
        struct.pack_into(">I", data, pos, branch(call, loader, link=True))
        data[pos + 4:pos + 12] = bytes.fromhex(suffix)
    for call, store in zip(_MENU_GETTERS[layout.game_id][:2], (0xB0810014, 0xB09E0010)):
        data[call - TEXT_TO_RAM - 16:call - TEXT_TO_RAM + 12] = struct.pack(
            ">7I", 0x38600000, store, 0x38A00066, 0x38C00000,
            branch(call, STAT_GETTERS[layout.game_id], link=True), 0x5460043E, 0x7FE3FB78)
    call = _CEREMONY_GETTERS[layout.game_id]
    data[call - TEXT_TO_RAM - 12:call - TEXT_TO_RAM + 8] = struct.pack(
        ">5I", 0x38600000, 0x38A00066, 0x38C00000,
        branch(call, STAT_GETTERS[layout.game_id], link=True), 0x547E043F)
    at = TRANSFORM_FUNCTIONS[layout.game_id] - TEXT_TO_RAM
    data[at:at + 8] = bytes.fromhex("9421ffa07c0802a6")
    struct.pack_into(">I", data, at + 0x168, 0x3BA00000)
    tails = {"GC6P01": "7ff7fb787fe3fb784bf9cae92c030000",
             "GC6E01": "7ff7fb787fe3fb784bf9cfe92c030000",
             "GC6J01": "7ff7fb787fe3fb784bf9def92c030000"}
    at = loader - TEXT_TO_RAM + 0x14C
    data[at:at + 16] = bytes.fromhex(tails[layout.game_id])
    result = bytes(data)
    return result, replace(layout, sha256=hashlib.sha256(result).hexdigest())


def mock_fixture(original, region):
    stack = ExitStack()
    stack.enter_context(patch("orre_randomizer.deoxys_runtime.dol_layout", return_value=region))
    stack.enter_context(patch("orre_randomizer.castform_portraits.dol_layout", return_value=region))
    stack.enter_context(patch.dict(WEATHER_LAYOUTS, {region.game_id:
        {**WEATHER_LAYOUTS[region.game_id], "sha256": hashlib.sha256(original).hexdigest()}}))
    return stack


class DeoxysRuntimeTests(unittest.TestCase):
    def test_transform_copies_target_tag_only_to_native_temporary_record_in_both_games(self):
        source, destination = 0x80600000, 0x80700000
        for game, src_reg, dst_reg, displaced, counter in (("GC6P01", 28, 27, 0x3BA00000, 29),
                                                          ("GXXP01", 26, 25, 0x3B600000, 27)):
            offset = 0xD2 if game.startswith("GC6") else 0xC
            for tag in (0, 0x1234, *(FORM_TAG | form for form in range(4))):
                machine = WrapperMachine(transform_tag_copy(ADDRESS, RETURN, game_id=game,
                    source=src_reg, destination=dst_reg, displaced=displaced))
                machine.reg[src_reg], machine.reg[dst_reg] = source, destination
                for ptr in (source, destination):
                    machine.store(ptr, 410, 2)
                    machine.store(ptr + 4, 0x12345678, 4)
                machine.store(source + offset, tag, 2)
                machine.store(destination + offset, FORM_TAG | 1, 2)
                before, memory = machine.reg.copy(), machine.memory.copy()
                machine.run(max_steps=120)
                self.assertEqual(machine.load(destination + offset, 2), tag if tag & 0xFFFC == FORM_TAG else 0)
                changed = {at for at in set(memory) | set(machine.memory) if memory.get(at) != machine.memory.get(at)}
                self.assertTrue(changed <= {destination + offset, destination + offset + 1})
                self.assertEqual(machine.reg[counter], 0)
                for index in set(range(13, 32)) - {counter}:
                    self.assertEqual(machine.reg[index], before[index])
                self.assertEqual(machine.lr, RETURN)

    def test_saved_tags_change_only_the_reserved_halfword_without_editing_pid_or_status(self):
        for game, size in RECORD_SIZES.items():
            original = bytearray((index * 17 + 11) & 255 for index in range(size))
            struct.pack_into(">H", original, 0, 410)
            offset = FORM_OFFSETS[game]
            struct.pack_into(">H", original, offset, 0)
            self.assertEqual(saved_form(original, game), 0)
            for form in range(4):
                changed = with_saved_form(original, game, form)
                self.assertEqual(saved_form(changed, game), form)
                self.assertEqual(changed[:offset], original[:offset])
                self.assertEqual(changed[offset + 2:], original[offset + 2:])
                self.assertEqual(changed[offset:offset + 2], struct.pack(">H", FORM_TAG | form))
                self.assertEqual(saved_form(with_saved_form(changed, game, (form + 1) % 4), game), (form + 1) % 4)
            for foreign in (1, 0x1234, FORM_TAG ^ 4, 0xFFFF):
                struct.pack_into(">H", original, offset, foreign)
                self.assertEqual(saved_form(original, game), 0)
                with self.assertRaises(ValueError):
                    with_saved_form(original, game, 3)
            struct.pack_into(">H", original, offset, FORM_TAG | 3)
            struct.pack_into(">H", original, 0, 411)  # preserved cloned species with Deoxys model
            self.assertEqual(saved_form(original, game), 0)
            with self.assertRaises(ValueError):
                with_saved_form(original, game, 1)
        for invalid in (None, 0, [], "unknown", "GC6K01"):
            with self.assertRaises(ValueError):
                game_family(invalid)
        for invalid in (-1, 0x10000, True, None):
            with self.assertRaises(ValueError):
                form_from_tag(invalid)
        for record in (b"", bytes(0x137), bytes(0x139), None):
            with self.assertRaises(ValueError):
                saved_form(record, "GC6P01")

    def test_pure_native_form_getter_reads_tags_in_both_layouts_without_writes(self):
        for game in RECORD_SIZES:
            offset = FORM_OFFSETS[game]
            for species in (249, 410, 411):
                for tag in (0, 1, 0xFFFF, 0xDEC4, *(FORM_TAG | form for form in range(4))):
                    machine = WrapperMachine(form_reader(ADDRESS, game_id=game))
                    machine.reg[3] = RECORD
                    machine.store(RECORD, species, 2)
                    machine.store(RECORD + offset, tag, 2)
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run(max_steps=80)
                    self.assertEqual(machine.reg[3], form_from_tag(tag) if species == 410 else 0)
                    self.assertEqual(machine.reg[4:11], before[4:11])
                    self.assertEqual(machine.reg[12:], before[12:])
                    self.assertEqual(machine.memory, memory)
                    self.assertEqual(machine.lr, RETURN)
            for pointer in (0, 0x7FFFFFFC, 0x81800000, 0x817FFFFC, RECORD + 1, RECORD + 2):
                machine = WrapperMachine(form_reader(ADDRESS, game_id=game))
                machine.reg[3] = pointer
                machine.run(max_steps=80)
                self.assertEqual(machine.reg[3], 0)
                self.assertFalse(any(at == pointer or at == pointer + offset for at, _ in machine.reads))

    def test_full_record_menu_and_ceremony_emit_form_markers_without_saved_record_edits(self):
        reader, native = ADDRESS + 0x500, ADDRESS + 0x900
        for load_model in (False, True):
            for species in (410, 411):
                for form in range(4):
                    machine = WrapperMachine(_record_identity(ADDRESS, native, reader, load_model=load_model))
                    put(machine, reader, form_reader(reader, game_id="GC6P01"))
                    machine.reg[3:6] = [410 if load_model else 0, 0x11223344, 1]
                    machine.reg[31] = RECORD
                    machine.store(RECORD, species, 2)
                    machine.store(RECORD + 0xD2, FORM_TAG | form, 2)
                    native_requests = []
                    def request(state):
                        native_requests.append(tuple(state.reg[3:6]))
                        state.reg[3] = 0x1234
                    machine.callbacks[native] = request
                    before = machine.reg.copy()
                    record = {at: value for at, value in machine.memory.items() if RECORD <= at < RECORD + 0x138}
                    machine.run(max_steps=160)
                    if species == 410:
                        if load_model:
                            self.assertEqual(native_requests, [(MODEL_MARKERS[form], *before[4:6])])
                        else:
                            self.assertEqual(native_requests, [])
                            self.assertEqual(machine.reg[3], MODEL_MARKERS[form])
                    else:
                        self.assertEqual(native_requests, [tuple(before[3:6])])
                    self.assertEqual(machine.reg[13:], before[13:])
                    self.assertEqual(machine.reg[1], before[1])
                    self.assertEqual(machine.lr, RETURN)
                    self.assertEqual({at: value for at, value in machine.memory.items() if RECORD <= at < RECORD + 0x138}, record)

    def test_reduced_shadow_views_prefer_current_captured_form_in_party_or_last_pc_slot(self):
        hero, pc = 0x80600000, 0x80700000
        for game in ("GC6P01", "GXXP01"):
            xd = game.startswith("GXX")
            family = "xd" if xd else "colosseum"
            size, tag = RECORD_SIZES[family], FORM_OFFSETS[family]
            pid, sid, boxes = (0x28, 0xBA, 8) if xd else (4, 0xD8, 3)
            last = pc + (boxes - 1) * (0x14 + 30 * size) + 0x14 + 29 * size
            for target in (None, hero + 0x30 + 5 * size, last):
                for matching in (False, True):
                    with self.subTest(game=game, target=target, matching=matching):
                        machine = WrapperMachine(owned_form_reader(ADDRESS, game_id=game))
                        machine.reg[3] = RECORD
                        for at, width, value in ((RECORD, 2, 410), (RECORD + pid, 4, 0xABCD1234),
                                                 (RECORD + sid, 2, 37), (RECORD + tag, 2, FORM_TAG | 1)):
                            machine.store(at, value, width)
                        if target is not None:
                            for at, width, value in ((target, 2, 410), (target + pid, 4, 0xABCD1234 + int(not matching)),
                                                     (target + sid, 2, 37), (target + tag, 2, FORM_TAG | 3)):
                                machine.store(at, value, width)
                        def accessor(state):
                            which = state.reg[4]
                            state.clobber_volatile()
                            state.reg[3] = {2: hero, 3: pc}.get(which, 0)
                        machine.callbacks[SAVEDATA_GETTERS[game]] = accessor
                        before = machine.reg.copy()
                        saved = {at: value for at, value in machine.memory.items() if 0x80400000 <= at < 0x81000000}
                        machine.run(max_steps=6000)
                        self.assertEqual(machine.reg[3], 3 if matching and target is not None else 1)
                        self.assertEqual(machine.reg[4:11], before[4:11])
                        self.assertEqual(machine.reg[12:], before[12:])
                        self.assertEqual(machine.reg[1], before[1])
                        self.assertEqual(machine.lr, RETURN)
                        self.assertEqual({at: value for at, value in machine.memory.items() if 0x80400000 <= at < 0x81000000}, saved)

    def test_reduced_shadow_views_find_daycare_and_last_chamber_visitor_without_writes(self):
        for game in ("GC6P01", "GXXP01"):
            xd = game.startswith("GXX")
            family = "xd" if xd else "colosseum"
            size, tag = RECORD_SIZES[family], FORM_OFFSETS[family]
            pid, sid = (0x28, 0xBA) if xd else (4, 0xD8)
            daycare, chamber = 0x80600000, 0x80700000
            targets = [(daycare + 8, True), (daycare + 8, False)]
            if xd:
                targets += [(chamber + 8 * 0x3D8 + 4 * size, True)]
            for target, occupied in targets:
                machine = WrapperMachine(owned_form_reader(ADDRESS, game_id=game))
                machine.reg[3] = RECORD
                for record, form in ((RECORD, 1), (target, 3)):
                    for at, width, value in ((record, 2, 410), (record + pid, 4, 0xABCD1234),
                                             (record + sid, 2, 37), (record + tag, 2, FORM_TAG | form)):
                        machine.store(at, value, width)
                machine.store(daycare, int(occupied), 1)
                requests = []
                def accessor(state):
                    which = state.reg[4]
                    requests.append(which)
                    state.clobber_volatile()
                    state.reg[3] = {0xB: daycare, 0x15: chamber}.get(which, 0)
                machine.callbacks[SAVEDATA_GETTERS[game]] = accessor
                before = machine.reg.copy()
                saved = {at: value for at, value in machine.memory.items() if 0x80400000 <= at < 0x81000000}
                machine.run(max_steps=3500)
                expected = 3 if target >= chamber or occupied else 1
                self.assertEqual(machine.reg[3], expected)
                self.assertEqual(machine.reg[4:11], before[4:11])
                self.assertEqual(machine.reg[12:], before[12:])
                self.assertEqual(machine.reg[1], before[1])
                self.assertEqual(machine.lr, RETURN)
                self.assertIn(0xB, requests)
                self.assertEqual({at: value for at, value in machine.memory.items() if 0x80400000 <= at < 0x81000000}, saved)

    def test_battle_marker_reads_original_record_and_preserves_substitute_and_cloned_species(self):
        reader, native, handle = ADDRESS + 0x500, ADDRESS + 0x900, 0x80402000
        for requested in (249, 410):
            for species in (410, 411):
                for form in range(4):
                    machine = WrapperMachine(_battle_identity(ADDRESS, native, reader, GETTER))
                    put(machine, reader, form_reader(reader, game_id="GC6P01"))
                    machine.reg[3:6], machine.reg[30] = [requested, 0xABCD1234, 1], 0x80403000
                    machine.store(RECORD, species, 2)
                    machine.store(RECORD + 0xD2, FORM_TAG | form, 2)
                    def getter(state):
                        selector = state.reg[5]
                        state.clobber_volatile()
                        state.reg[3] = handle if selector == 0xD6 else RECORD
                    machine.callbacks[GETTER] = getter
                    requests = []
                    machine.callbacks[native] = lambda m: requests.append(tuple(m.reg[3:6]))
                    before = machine.reg.copy()
                    machine.run(max_steps=180)
                    expected = MODEL_MARKERS[form] if requested == 410 and species == 410 else requested
                    self.assertEqual(requests, [(expected, *before[4:6])])
                    self.assertEqual(machine.reg[13:], before[13:])
                    self.assertEqual(machine.reg[1], before[1])
                    self.assertEqual(machine.lr, RETURN)

    def test_models_resolve_explicit_markers_and_leave_native_deoxys_clones_unchanged(self):
        loader = 0x801DE190
        for model in (249, 385, 410, 414, 415, 416, *MODEL_MARKERS):
            for pid in (0, 1, 2, 3, 0x12340000, 0xABCDFFF1, 0x80000002, 0xFFFFFFFF):
                for shiny in (0, 1, 0xAB000000, 0xAB000001):
                    with self.subTest(model=model, pid=pid, shiny=shiny):
                        machine = WrapperMachine(_model_selector(ADDRESS, loader, None, MODEL_RESOURCES, MODEL_GROUPS))
                        machine.store(loader + 0x2C, branch(loader + 0x2C, RETURN), 4)
                        machine.store(loader + 0x14C, 0x7FF7FB78, 4)
                        machine.store(loader + 0x150, branch(loader + 0x150, RETURN), 4)
                        machine.reg[3] = model
                        machine.reg[26:32] = [model, pid, shiny, 0, 0x007A1E00, 0x386]
                        before, memory, lr = machine.reg.copy(), machine.memory.copy(), machine.lr
                        machine.run(max_steps=100)
                        self.assertEqual(machine.reg[27:29], before[27:29])
                        if model in MODEL_MARKERS[1:]:
                            name = FORMS[MODEL_MARKERS.index(model) - 1]
                            self.assertEqual(machine.reg[26], 410)
                            self.assertEqual(machine.reg[29:32], [1, MODEL_RESOURCES[name, bool(shiny)], MODEL_GROUPS[bool(shiny)]])
                            self.assertEqual(machine.reg[23], machine.reg[31])
                        else:
                            self.assertEqual(machine.reg[29:32], before[29:32])
                            self.assertEqual(machine.reg[26], 410 if model == MODEL_MARKERS[0] else model)
                        self.assertEqual(machine.reg[4:11], before[4:11])
                        self.assertEqual(machine.reg[12:23], before[12:23])
                        self.assertEqual(machine.memory, memory)
                        self.assertEqual(machine.lr, lr)

    def test_existing_weather_and_lugia_resources_keep_their_owned_dispatch(self):
        loader, lugia, weather = 0x801DE190, ADDRESS + 0x400, ADDRESS + 0x800
        for model in (MODEL_MARKER, 249, 410, 414, 415, 416, *MODEL_MARKERS):
            for rare in (0, 1):
                machine = WrapperMachine(_model_selector(ADDRESS, loader, lugia, MODEL_RESOURCES, MODEL_GROUPS))
                put(machine, lugia, lugia_selector(lugia, loader, 0x800D84B0, 0x16E))
                put(machine, weather, weather_selector(weather, RETURN, SHINY_RESOURCES, xd=False))
                machine.store(loader + 0x2C, branch(loader + 0x2C, loader + 0x14C), 4)
                machine.store(loader + 0x14C, branch(loader + 0x14C, weather), 4)
                machine.reg[3], machine.reg[26], machine.reg[28] = model, model, rare
                machine.reg[30:32] = [0x007A1E00, 0x386]
                machine.run(max_steps=200)
                if model == MODEL_MARKER:
                    self.assertEqual(machine.reg[26], 249)
                    self.assertEqual(machine.reg[29:32], [1, 0x7DF41E00 if rare else 0x7DF31E00, 0x16E])
                elif model in SHINY_RESOURCES and rare:
                    self.assertEqual(machine.reg[30], SHINY_RESOURCES[model])
                elif model in MODEL_MARKERS[1:]:
                    self.assertEqual(machine.reg[30], MODEL_RESOURCES[FORMS[MODEL_MARKERS.index(model)-1], bool(rare)])
                else:
                    self.assertEqual(machine.reg[30], 0x007A1E00)

    def test_stat_overrides_leave_the_native_saved_identity_and_nonvolatile_registers_intact(self):
        for form, name in enumerate(STATS):
            for selector, column in ((4, 1), (5, 2), (6, 3), (7, 4), (8, 5)):
                with self.subTest(form=name, selector=selector):
                    machine = WrapperMachine(_stat_selector(ADDRESS, GETTER, STATS))
                    machine.reg[3:7] = [0, 410, selector, 0]
                    machine.reg[30] = RECORD
                    machine.store(RECORD, 410, 2)
                    machine.store(RECORD + 4, 0xABCD1231, 4)
                    machine.store(RECORD + 0xD2, FORM_TAG | form, 2)
                    def native(m):
                        m.clobber_volatile(); m.reg[3] = STATS["normal"][column]
                    machine.callbacks[GETTER] = native
                    before, memory = machine.reg.copy(), machine.memory.copy()
                    machine.run(max_steps=160)
                    self.assertEqual(machine.reg[3], STATS[name][column])
                    self.assertEqual(len(machine.calls), int(form == 0))
                    self.assertEqual(machine.reg[13:32], before[13:32])
                    self.assertEqual(machine.reg[1], before[1])
                    self.assertEqual(machine.memory, memory)
                    self.assertEqual(machine.lr, RETURN)

    def test_hp_unrelated_species_and_mismatched_records_use_the_native_getter(self):
        for argument, species, stored, selector in ((0, 249, 249, 4), (0, 410, 132, 4),
                                                    (0, 410, 410, 3), (0, 410, 410, 9),
                                                    (RECORD, 410, 410, 4)):
            with self.subTest(argument=argument, species=species, stored=stored, selector=selector):
                machine = WrapperMachine(_stat_selector(ADDRESS, GETTER, STATS))
                machine.reg[3:7] = [argument, species, selector, 0]
                machine.reg[30] = RECORD
                machine.store(RECORD, stored, 2)
                machine.store(RECORD + 0xD2, FORM_TAG | 3, 2)
                machine.callbacks[GETTER] = lambda m: m.reg.__setitem__(3, 123)
                machine.run(max_steps=150)
                self.assertEqual(machine.reg[3], 123)
                self.assertEqual(len(machine.calls), 1)

    def test_stat_record_bounds_are_checked_before_reading_species_or_tag(self):
        for pointer in (0, 0x7FFFFFFC, 0x81800000, 0x817FFFFC, RECORD + 1, RECORD + 2):
            with self.subTest(pointer=pointer):
                machine = WrapperMachine(_stat_selector(ADDRESS, GETTER, STATS))
                machine.reg[3:7], machine.reg[30] = [0, 410, 4, 0], pointer
                machine.callbacks[GETTER] = lambda m: m.reg.__setitem__(3, 91)
                machine.run(max_steps=100)
                self.assertEqual(machine.reg[3], 91)
                self.assertFalse(any(at == pointer or at == pointer + 0xD2 for at, _ in machine.reads))
        machine = WrapperMachine(_stat_selector(ADDRESS, GETTER, STATS))
        last = 0x81800000 - 0x138
        machine.reg[3:7], machine.reg[30] = [0, 410, 8, 0], last
        machine.store(last, 410, 2); machine.store(last + 0xD2, FORM_TAG | 3, 2)
        machine.run(max_steps=150)
        self.assertEqual(machine.reg[3], 180)

    def test_explicit_advanced_stat_table_is_used_without_changing_hp(self):
        customized = {name: tuple(v + 1 for v in row) for name, row in STATS.items()}
        machine = WrapperMachine(_stat_selector(ADDRESS, GETTER, customized))
        machine.reg[3:7], machine.reg[30] = [0, 410, 4, 0], RECORD
        machine.store(RECORD, 410, 2)
        machine.store(RECORD + 0xD2, FORM_TAG | 1, 2)
        machine.run(max_steps=100)
        self.assertEqual(machine.reg[3], 181)

    def test_resource_groups_and_form_tables_reject_invalid_or_colliding_inputs(self):
        for value in ({}, {**MODEL_RESOURCES, ("attack", False): True},
                      {**MODEL_RESOURCES, ("attack", False): MODEL_RESOURCES["defense", False]},
                      {**MODEL_RESOURCES, ("attack", False): 0x100001E00},
                      {**MODEL_RESOURCES, ("attack", False): 0x7DB11200}):
            with self.subTest(value=value), self.assertRaises(FormatError):
                _resources(value, MODEL_GROUPS, b"retail")
        for groups in ({}, {False: True, True: 0x77E}, {False: 0x10000, True: 0x77E}, {False: 0, True: 0x77E}):
            with self.subTest(groups=groups), self.assertRaises(FormatError):
                _resources(MODEL_RESOURCES, groups, b"retail")
        with self.assertRaisesRegex(FormatError, "collides"):
            _resources(MODEL_RESOURCES, MODEL_GROUPS, struct.pack(">I", MODEL_RESOURCES["speed", True]))
        for table in ({}, {**STATS, "speed": (50, 95, 90, 95, 90)},
                      {**STATS, "speed": (50, 95, 90, 95, 90, True)},
                      {**STATS, "speed": (50, 95, 90, 95, 90, 256)}):
            with self.subTest(table=table), self.assertRaises(FormatError):
                _stats(table)
        self.assertEqual(_resources(MODEL_RESOURCES, MODEL_GROUPS, b"retail"), (MODEL_RESOURCES, MODEL_GROUPS))

    def test_install_changes_only_five_scoped_calls_explicit_identity_sites_and_owned_arena(self):
        for layout in LAYOUTS:
            for compose in (False, True):
                with self.subTest(game=layout.game_id, compose=compose):
                    original, region = fixture(layout)
                    with mock_fixture(original, region):
                        current = (install_castform_shiny_models(original, original, region.game_id)[0]
                                   if compose else original)
                        output, report = install_deoxys_forms(original, current, region.game_id, base_stats=STATS)
                    function = STAT_FUNCTIONS[region.game_id]
                    changes = {at for at in range(function - TEXT_TO_RAM, function - TEXT_TO_RAM + 0x700)
                               if current[at] != output[at]}
                    allowed = {function + relative - TEXT_TO_RAM + i for relative, _, _ in STAT_WINDOWS for i in range(4)}
                    self.assertTrue(changes <= allowed)
                    self.assertTrue(changes)
                    hp = function + 0xC4 - TEXT_TO_RAM
                    self.assertEqual(output[hp:hp + 4], current[hp:hp + 4])
                    self.assertEqual(bool(report["previous_weather_stub"]), compose)
                    for entry in report["base_stat_calls"]:
                        word = u32(output, entry["address"] - TEXT_TO_RAM)
                        self.assertEqual(word & 3, 1)
                        self.assertEqual(destination(entry["address"], word), report["stat_stub"])
                    self.assertEqual(destination(report["model_hook"], u32(output, report["model_hook"] - TEXT_TO_RAM)), report["model_stub"])
                    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
                    self.assertEqual(output[section["offset"]:section["offset"] + 32],
                                     _arena_guard(section["ram_address"] + section["size"], region.arena_lo_store))
                    self.assertTrue(report["save_data_unchanged"])

    def test_foreign_stat_body_or_getter_and_model_hook_chains_are_rejected(self):
        original, region = fixture(LAYOUTS[0])
        with mock_fixture(original, region):
            for offset in (STAT_FUNCTIONS[region.game_id] - TEXT_TO_RAM + 0x40,
                           STAT_GETTERS[region.game_id] - TEXT_TO_RAM + 4):
                data = bytearray(original); data[offset] ^= 1
                with self.assertRaisesRegex(FormatError, "stat calculator"):
                    install_deoxys_forms(original, bytes(data), region.game_id, base_stats=STATS)
            hook = MODEL_LAYOUTS[region.game_id][0] + 0x14C
            for word in (0x60000000, branch(hook, 0x80005000), branch(hook, 0x80005000, link=True)):
                data = bytearray(original); struct.pack_into(">I", data, hook - TEXT_TO_RAM, word)
                with self.assertRaisesRegex(FormatError, "unowned"):
                    install_deoxys_forms(original, bytes(data), region.game_id, base_stats=STATS)
            current, _ = install_castform_shiny_models(original, original, region.game_id)
            target = destination(hook, u32(current, hook - TEXT_TO_RAM))
            offset = u32(current, 8) + target - u32(current, 0x50)
            data = bytearray(current); data[offset + 3] ^= 1
            with self.assertRaisesRegex(FormatError, "unowned"):
                install_deoxys_forms(original, bytes(data), region.game_id, base_stats=STATS)

    def test_unknown_identity_mismatched_game_and_reinstallation_are_refused(self):
        with self.assertRaises(FormatError):
            install_deoxys_forms(b"unknown", b"unknown", "GC6P01", base_stats=STATS)
        original, region = fixture(LAYOUTS[0])
        with mock_fixture(original, region):
            with self.assertRaisesRegex(FormatError, "unknown original"):
                install_deoxys_forms(original, original, "GXXP01", base_stats=STATS)
            output, _ = install_deoxys_forms(original, original, region.game_id, base_stats=STATS)
            with self.assertRaisesRegex(FormatError, "stat calculator"):
                install_deoxys_forms(original, output, region.game_id, base_stats=STATS)

    def test_optional_retail_regions_compose_with_lugia_weather_and_live_portraits(self):
        sources = {gid: Path("build/hd-completion/hud") / (gid + ".dol") for gid in STAT_FUNCTIONS}
        if not all(p.is_file() for p in sources.values()):
            self.skipTest("Optional original regional research executables are absent")
        from orre_randomizer.castform_portraits import install_castform_portraits
        from orre_randomizer.engine.postgame_lugia_model import _install_hooks
        for game, source in sources.items():
            original = source.read_bytes(); digest = hashlib.sha256(original).hexdigest()
            for compose in (False, True):
                with self.subTest(game=game, compose=compose):
                    current = original
                    if compose:
                        current, _ = _install_hooks(original, current, 0x16E)
                        current, _ = install_castform_portraits(original, current, game)
                        current, _ = install_castform_shiny_models(original, current, game)
                    output, report = install_deoxys_forms(original, current, game, base_stats=STATS)
                    self.assertTrue(report["unrelated_executable_bytes_preserved"])
                    self.assertEqual(bool(report["previous_weather_stub"]), compose)
                    self.assertGreater(len(output), len(current))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
