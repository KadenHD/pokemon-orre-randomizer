"""Story-safe scene guards and optional checks against local retail artifacts.

These tests neither create an ISO nor touch a save. Native fixtures are private
and optional; the emitted-CMS eligibility check also runs without game files.
"""
from dataclasses import replace
from pathlib import Path
import math
import struct
import unittest

from orre_randomizer.engine import event_gifts as events
from orre_randomizer.engine import postgame_boss as boss
from orre_randomizer.engine import postgame_scene as scene
from orre_randomizer.engine import postgame_scene_model as field
from orre_randomizer.engine import postgame_scene_text as text
from orre_randomizer.engine.analyze_game import cstring, parse_fsys, parse_rel, sha256, u32
from orre_randomizer.engine.inspect_tables import rel_symbols, u16
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.options import Options
from tests.test_event_gifts import execute


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "build/region-compat-2026-11-02"
NATIVE_COMMANDS = {number: lambda *_: 0 for number in (36, 40, 41, 59, 61, 62, 68, 69, 103, 165, 179)}


def ready_flags():
    return (dict.fromkeys(events.STORY_FLAGS, 1)
            | dict.fromkeys((2125 + sid for sid in events.SHADOW_IDS), 1)
            | dict.fromkeys((1261 + sid for sid in events.SHADOW_IDS), 1)
            | {scene.INTRO_STATE_FLAG: scene.PHASE_AVAILABLE})


class SceneArrivalGuardTests(unittest.TestCase):
    def test_introduction_state_is_independent_of_other_battle_results(self):
        resume = 0x20000
        refresh = scene.visibility(4, True) + scene.visibility(5, True)
        code = scene.refresh_guard(0, refresh, resume=resume, arrival_ready=boss._ready(),
                                   captured=events._call(81, boss.CAPTURE_FLAG), battle_id=566)
        for result in (0, 2, 3):
            for introduced in (False, True):
                with self.subTest(native_battle_result=result, introduced=introduced):
                    flags = ready_flags() | {scene.INTRO_STATE_FLAG: scene.PHASE_INTRODUCED if introduced else scene.PHASE_AVAILABLE}
                    globals_ = {0: 7, 1: 9, scene.SCENE_GLOBAL: 0, scene.ARRIVAL_GLOBAL: 0}
                    state = execute(code, 0, flags, stop_at=resume, globals_=globals_,
                                    builtins=NATIVE_COMMANDS | {103: lambda *_, r=result: r,
                                                               152: lambda *_: 0},
                                    talk_resources=(1, 4))
                    self.assertEqual(state["visibility"][:2], [[77, 4, 1], [77, 5, 1]])
                    self.assertEqual(state["globals"], {0: 7, 1: 9, 2: 0, 3: 1})
                    self.assertEqual(state["flags"], ready_flags() | {scene.INTRO_STATE_FLAG: scene.PHASE_INTRODUCED})
                    commands = [number for number, _ in state["calls"]]
                    if introduced:
                        self.assertEqual(state["messages"], [])
                        self.assertFalse({32, 36, 54, 152, 179} & set(commands))
                    else:
                        self.assertIn(152, commands)
                        self.assertEqual(state["messages"][:len(text.ARRIVAL_KEYS)],
                                         [text.MESSAGE_IDS[key] for key in text.ARRIVAL_KEYS])

    def test_arrival_never_interrupts_story_master_ball_or_a_completed_capture(self):
        code = scene.arrival(0, ready=boss._ready(), captured=events._call(81, boss.CAPTURE_FLAG))
        ready = ready_flags()
        cases = [("eligible", ready, True)]
        cases.extend((f"missing-{flag}", ready | {flag: 0}, False) for flag in ready)
        cases.extend((
            ("already-captured", ready | {boss.CAPTURE_FLAG: 1}, False),
            ("master-ball-pending", ready | {events.MASTER_BALL_NOTICE_FLAG: 1}, False),
            ("master-ball-received", ready | {events.MASTER_BALL_NOTICE_FLAG: 1,
                                             events.MASTER_BALL_RECEIPT_FLAG: 1}, True),
        ))
        for label, flags, eligible in cases:
            with self.subTest(case=label):
                globals_ = {0: 0x12345678, 1: 0x76543210, scene.SCENE_GLOBAL: 0}
                state = execute(code, 0, flags, globals_=globals_, initial_stack=(0,),
                                builtins=NATIVE_COMMANDS, talk_resources=(1, 4))
                self.assertEqual(state["flags"], flags | ({scene.INTRO_STATE_FLAG: scene.PHASE_INTRODUCED} if eligible else {}))
                self.assertEqual(state["gifts"], [])
                self.assertEqual(state["globals"], {0: 0x12345678, 1: 0x76543210, 2: 0})
                self.assertEqual(state["messages"],
                                 [text.MESSAGE_IDS[key] for key in text.ARRIVAL_KEYS] if eligible else [])
                self.assertEqual(state["visibility"], [[77, 4, 1], [77, 5, 1]] if eligible else [])
                commands = [number for number, _ in state["calls"]]
                self.assertEqual(commands.count(32), int(eligible))
                self.assertEqual(commands.count(33), int(eligible))
                self.assertEqual(commands.count(179), int(eligible))
                self.assertEqual(commands.count(80), int(eligible))
                self.assertNotIn(152, commands)
                if eligible:
                    self.assertEqual([args[:3] for number, args in state["calls"] if number == 61],
                                     [[0, 100, 1], [0, 101, 1]])
                    self.assertEqual(commands[-2:], [179, 33])

    def test_first_idle_only_allows_arrival_and_in_place_purification_does_not_restage_it(self):
        resume = 0x20000
        refresh = scene.visibility(4, True) + scene.visibility(5, True)
        code = scene.refresh_guard(0, refresh, resume=resume, arrival_ready=boss._ready(),
                                   captured=events._call(81, boss.CAPTURE_FLAG))
        ready = ready_flags()
        almost = ready | {1261 + events.SHADOW_IDS[-1]: 0}
        globals_ = {0: 7, 1: 9, scene.SCENE_GLOBAL: 0, scene.ARRIVAL_GLOBAL: 0}
        first = execute(code, 0, almost, stop_at=resume, globals_=globals_,
                        builtins=NATIVE_COMMANDS, talk_resources=(1, 4))
        self.assertEqual(first["messages"], [])
        self.assertEqual(first["globals"], {0: 7, 1: 9, 2: 0, 3: 1})
        refreshed = execute(code, 0, ready, stop_at=resume, globals_=globals_,
                            builtins=NATIVE_COMMANDS, talk_resources=(1, 4))
        self.assertEqual(refreshed["messages"], [])
        self.assertNotIn(179, [number for number, _ in refreshed["calls"]])
        self.assertEqual(refreshed["flags"], ready)
        globals_[scene.ARRIVAL_GLOBAL] = 0  # A new room load starts a new local allocation.
        entered = execute(code, 0, ready, stop_at=resume, globals_=globals_,
                          builtins=NATIVE_COMMANDS, talk_resources=(1, 4))
        self.assertEqual(entered["messages"], [text.MESSAGE_IDS[key] for key in text.ARRIVAL_KEYS])
        self.assertEqual(entered["globals"], {0: 7, 1: 9, 2: 0, 3: 1})
        self.assertEqual(entered["flags"], ready | {scene.INTRO_STATE_FLAG: scene.PHASE_INTRODUCED})
        # Wipeout or a cold save reload creates fresh room globals. The explicit
        # mission marker still suppresses the introduction without reading103.
        reloaded = execute(code, 0, entered["flags"], stop_at=resume,
                           globals_={0: 7, 1: 9, 2: 0, 3: 0},
                           builtins=NATIVE_COMMANDS, talk_resources=(1, 4))
        self.assertEqual(reloaded["messages"], [])
        self.assertEqual(reloaded["flags"], entered["flags"])
        self.assertNotIn(103, [number for number, _ in reloaded["calls"]])


class NativeSceneIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = []
        for tag, game_id in (("pal", "GC6P01"), ("usa", "GC6E01"), ("japan", "GC6J01")):
            archive = RESEARCH / "event-research/v2" / tag / "M3_shrine_1F.fsys"
            common = RESEARCH / "rel-research" / tag / "common.fsys-common_rel.rel"
            if tag == "pal" and not archive.exists():
                archive = ROOT / "game/files/M3_shrine_1F.fsys"
            if archive.exists() and common.exists():
                cls.sources.append((game_id, archive.read_bytes(), common.read_bytes()))
        if not cls.sources:
            raise unittest.SkipTest("requires locally extracted original shrine/common files")

    def test_native_cms_changes_only_reviewed_hooks_and_preserves_story_code_and_globals(self):
        allowed = ((4, 6), (16, 20), (0x48, 0x50), (0x24A, 0x24F), (0x25AB, 0x25B0))
        for game_id, archive, _ in self.sources:
            original = decoded_member(archive, parse_fsys(archive)["members"][1])
            for gifts in (False, True):
                with self.subTest(game=game_id, event_gifts=gifts):
                    current = events._patch_shrine_cms(original, 10, 25)[0] if gifts else original
                    current = bytearray(current)
                    old_globals = bytes.fromhex("1234567876543210")
                    globals_at = u32(current, 16)
                    current[globals_at:globals_at + 8] = old_globals
                    current = bytes(current)
                    output, report = boss._patch_script(original, current)
                    self.assertEqual(u16(output, 4), 14)
                    self.assertEqual(output[0x18:0x48], original[0x18:0x48])
                    self.assertEqual(u32(output, 12), u32(current, 12))
                    self.assertEqual(u32(output, 16), report["globals_offset"])
                    self.assertEqual(output[report["globals_offset"]:], old_globals + bytes(8))
                    self.assertEqual(u32(output, 0x48), report["eagun_entry"])
                    self.assertEqual(u32(output, 0x4C), report["boss_entry"])
                    self.assertEqual(report["event_gift_fallback"], u32(current, 0x48) if gifts else None)
                    self.assertTrue(report["arrival_after_native_yield"])
                    self.assertEqual(report["arrival_seen_global"], 3)
                    self.assertEqual(output[0x40F:0x414], original[0x40F:0x414])
                    self.assertEqual(output[0x25AB:0x25B0], b"\x06" + struct.pack(">I", report["visibility_refresh_entry"]))
                    self.assertEqual(output[0x449:0x2056], original[0x449:0x2056])
                    self.assertTrue(all(old == new or any(start <= index < end for start, end in allowed)
                                        for index, (old, new) in enumerate(zip(current, output))))
                    state = execute(output, 0x25AB, ready_flags(), stop_at=0x2056,
                                    globals_={0: 7, 1: 9, 2: 0, 3: 0},
                                    builtins=NATIVE_COMMANDS | {152: lambda *_: 0, 103: lambda *_: 2},
                                    talk_resources=(1, 4))
                    self.assertEqual(state["messages"], [text.MESSAGE_IDS[key]
                                     for key in (*text.ARRIVAL_KEYS, *text.RETRY_KEYS)])
                    self.assertEqual(state["globals"], {0: 7, 1: 9, 2: 0, 3: 1})
                    self.assertEqual(state["flags"], ready_flags() | {scene.INTRO_STATE_FLAG: scene.PHASE_INTRODUCED})
                    repeated = execute(output, 0x25AB, ready_flags(), stop_at=0x2056,
                                       globals_=state["globals"], builtins=NATIVE_COMMANDS,
                                       talk_resources=(1, 4))
                    self.assertEqual(repeated["messages"], [])
                    self.assertNotIn(179, [number for number, _ in repeated["calls"]])

    def test_two_added_actors_preserve_the_four_native_records_and_eagun_gift_redirect(self):
        for game_id, archive, _ in self.sources:
            original = decoded_member(archive, parse_fsys(archive)["members"][0])
            symbols = rel_symbols(original, parse_rel(original))
            base = symbols[5]["offset"]
            for gifts in (False, True):
                with self.subTest(game=game_id, event_gifts=gifts):
                    current = (events._patch_actor(original, events._REGIONAL_LAYOUTS[game_id]["actor"])[0]
                               if gifts else original)
                    output, report = boss._patch_actor(original, current)
                    rebuilt_symbols = rel_symbols(output, parse_rel(output))
                    table = rebuilt_symbols[5]["offset"]
                    self.assertEqual(u32(output, rebuilt_symbols[6]["offset"]), 6)
                    self.assertEqual(output[table:table + 4 * 0x24], current[base:base + 4 * 0x24])
                    expected_native = bytearray(original[base:base + 4 * 0x24])
                    if gifts:
                        expected_native[0x24 + 0x14] = 1
                        struct.pack_into(">H", expected_native, 0x24 + 0x16, 12)
                    self.assertEqual(output[table:table + 4 * 0x24], bytes(expected_native))
                    self.assertEqual((u16(output, table + 4 * 0x24 + 6),
                                      u16(output, table + 4 * 0x24 + 0x16)), (35, 13))
                    self.assertEqual(u16(output, table + 5 * 0x24 + 6), 69)
                    lugia_position = struct.unpack_from(">fff", output, table + 5 * 0x24 + 0x18)
                    eagun_position = struct.unpack_from(">fff", output, table + 0x24 + 0x18)
                    expected_heading = math.degrees(math.atan2(eagun_position[0] - lugia_position[0],
                                                               eagun_position[2] - lugia_position[2])) % 360
                    heading = u16(output, table + 5 * 0x24 + 4)
                    self.assertLess(abs((heading - expected_heading + 180) % 360 - 180), 0.5)
                    self.assertEqual(report["lugia_heading"], heading)
                    self.assertEqual(output[table + 5 * 0x24 + 0x14], 0)
                    self.assertEqual(report["tables"]["actors"]["count"], 6)

    def test_room_local_normal_and_shiny_lugia_keep_every_original_member_and_native_idle(self):
        donor = ROOT / "game/files/D4_casino_colo.fsys"
        if not donor.exists():
            self.skipTest("requires the original local Nascour model donor")
        donor = donor.read_bytes()
        variants = {}
        for game_id, archive, common in self.sources:
            native = parse_fsys(archive)["members"]
            source = boss._append_boss_asset(archive, donor)
            source_members = parse_fsys(source)["members"]
            symbols = rel_symbols(common, parse_rel(common))
            self.assertEqual(u32(common, symbols[72]["offset"] + 69 * 0x2C + 12), 0x009B0400)
            for shiny in (False, True):
                with self.subTest(game=game_id, shiny=shiny):
                    output, report = field.append_field_model(source, common, shiny=shiny)
                    members = parse_fsys(output)["members"]
                    self.assertEqual(len(members), len(native) + 2)
                    for old, new in zip(source_members, members):
                        self.assertEqual((old["name"], old["identifier_raw"]),
                                         (new["name"], new["identifier_raw"]))
                        self.assertEqual(decoded_member(source, old), decoded_member(output, new))
                    lugia = next(member for member in members if int(member["identifier_raw"], 16) == 0x009B0400)
                    model = decoded_member(output, lugia)
                    self.assertEqual(sha256(model), report["field_sha256"])
                    self.assertEqual((report["actor"], report["model"], report["resource"], report["shiny"]),
                                     (5, 69, 0x009B0400, shiny))
                    self.assertEqual(u32(model, 0), len(model))
                    data_end = 0x20 + u32(model, 4)
                    exports = data_end + 4 * u32(model, 8)
                    names = exports + 8 * u32(model, 12)
                    scenes = [pointer for pointer, name in struct.iter_unpack(">II", model[exports:names])
                              if cstring(model, names + name) == "scene_data"]
                    self.assertEqual(len(scenes), 1)
                    data = model[0x20:data_end]
                    model_set = u32(data, u32(data, scenes[0]))
                    root = u32(data, model_set)
                    for value in struct.unpack_from(">3f", data, root + 0x20):
                        self.assertGreater(value, 0.3)
                        self.assertLess(value, 0.5)
                    animation = u32(data, model_set + 4)
                    self.assertGreater(animation, 0)
                    idle_slots = struct.unpack_from(">13I", data, animation)
                    self.assertNotEqual(idle_slots[0], 0)
                    self.assertEqual(idle_slots[:12], (idle_slots[0],) * 12)
                    self.assertEqual(idle_slots[12], 0)
                    variants[game_id, shiny] = sha256(model)
            self.assertNotEqual(variants[game_id, False], variants[game_id, True])

    def test_bonus_battle_keeps_native_shrine_music_and_requests_nascour_music(self):
        options = replace(Options.none(), postgame_shadow_lugia=True)
        for game_id, _, common in self.sources:
            with self.subTest(game=game_id):
                symbols = rel_symbols(common, parse_rel(common))
                stride = 0x48 if game_id == "GC6P01" else 0x38
                native = symbols[50]["offset"] + 543 * stride
                output, report = boss.apply_common(common, common, options, seed="scene-integration")
                after_symbols = rel_symbols(output, parse_rel(output))
                battle = after_symbols[50]["offset"] + 566 * stride
                self.assertEqual(output[after_symbols[50]["offset"] + 543 * stride:
                                        after_symbols[50]["offset"] + 544 * stride],
                                 common[native:native + stride])
                self.assertEqual(u32(output, battle + 12), 1100)
                self.assertEqual(report["battle_music_id"], 1100)
                self.assertEqual([row["level"] for row in report["team"]], list(range(65, 71)))


if __name__ == "__main__":
    unittest.main()
