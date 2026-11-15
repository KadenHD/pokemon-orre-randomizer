"""Postgame eligibility, native receipt semantics and lossless REL expansion."""
import struct
import unittest
from dataclasses import replace
from unittest.mock import patch

from orre_randomizer.engine import postgame_lugia as lugia, postgame_boss as boss
from orre_randomizer.engine.analyze_game import FormatError, parse_rel, u32
from orre_randomizer.engine.event_gifts import SHADOW_IDS, STORY_FLAGS
from orre_randomizer.engine.inspect_tables import rel_symbols
from orre_randomizer.options import Options
from orre_randomizer.engine import postgame_scene as scene, postgame_scene_text as scene_text
try:
    from tests.test_event_gifts import bank, execute, flags_for_count as _flags_for_count
except ModuleNotFoundError:
    from test_event_gifts import bank, execute, flags_for_count as _flags_for_count


def flags_for_count(count):
    return _flags_for_count(count) | {scene.INTRO_STATE_FLAG: scene.PHASE_AVAILABLE}


class LugiaEligibilityTests(unittest.TestCase):
    def run_interaction(self, flags, *, caught=False, won=True):
        calls = []

        def battle(args, current_flags):
            calls.append(args)
            if caught:
                current_flags[lugia.CAPTURE_FLAG] = 1
            return 0

        flags = {**dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1), **flags}
        code = boss._interaction(0)
        native = {n: lambda *_: 0 for n in (36, 40, 41, 59, 61, 62, 68, 69, 165, 179)}
        result = execute(code, 0, flags, builtins=native | {152: battle, 103: lambda *_: 2 if won else 1}, talk_resources=(88, 1, 4))
        return calls, result

    def test_every_original_shadow_must_be_purified(self):
        for count in range(49):
            calls, result = self.run_interaction(flags_for_count(count))
            self.assertEqual(calls, [[lugia.BATTLE_ID, 1, 0]] if count == 48 else [])
            self.assertLessEqual(result['depth'], 8)
        for missing in SHADOW_IDS:
            flags = flags_for_count(48)
            flags[1261 + missing] = 0
            flags[lugia.PURIFICATION_FLAG] = 1
            calls, _ = self.run_interaction(flags)
            self.assertEqual(calls, [], 'The bonus must not substitute for a missing original Shadow')

    def test_each_original_capture_is_required_independently_of_purification(self):
        for missing in SHADOW_IDS:
            flags = flags_for_count(48) | {2125 + missing: 0, lugia.PURIFICATION_FLAG: 1}
            calls, _ = self.run_interaction(flags)
            self.assertEqual(calls, [])

    def test_original_story_scenes_remain_gated(self):
        for mask in range(1 << len(STORY_FLAGS)):
            flags = flags_for_count(48)
            flags.update({flag: int(bool(mask & 1 << i)) for i, flag in enumerate(STORY_FLAGS)})
            calls, _ = self.run_interaction(flags)
            self.assertEqual(bool(calls), mask == (1 << len(STORY_FLAGS)) - 1)

    def test_capture_is_native_and_failed_attempt_can_be_retried(self):
        flags = flags_for_count(48)
        _, failed = self.run_interaction(flags)
        self.assertNotIn(lugia.CAPTURE_FLAG, failed['flags'])
        self.assertEqual(failed['messages'][1:], [scene_text.MESSAGE_IDS[k] for k in scene_text.RETRY_KEYS])
        self.assertEqual(failed['visibility'], [[77, 4, 1], [77, 5, 1]])
        calls, success = self.run_interaction(failed['flags'], caught=True)
        self.assertEqual(calls, [[lugia.BATTLE_ID, 1, 0]])
        self.assertEqual(success['flags'][lugia.CAPTURE_FLAG], 1)
        self.assertNotIn(lugia.PURIFICATION_FLAG, success['flags'])
        self.assertEqual(success['messages'], [scene_text.MESSAGE_IDS[k] for k in ('arrival_challenge', *scene_text.CAPTURE_KEYS)])
        self.assertEqual(success['visibility'], [[77, 4, 1], [77, 5, 0], [77, 4, 0]])
        self.assertEqual(success['globals'][scene.SCENE_GLOBAL], 0)
        actual = [args[3:] for n, args in success['calls'] if n == 61]
        for observed, expected in zip(actual, scene.DEPARTURE_PATH, strict=True):
            for value, target in zip(observed, expected, strict=True):
                self.assertAlmostEqual(value, target, places=4)
        calls, repeated = self.run_interaction(success['flags'])
        self.assertEqual(calls, [])
        self.assertEqual(repeated['flags'], success['flags'])

    def test_loss_has_no_receipt_and_commander_can_be_retried(self):
        flags = flags_for_count(48)
        calls, failed = self.run_interaction(flags, won=False)
        self.assertTrue(calls)
        self.assertEqual(failed['messages'], [scene_text.MESSAGE_IDS[k] for k in ('arrival_challenge', *scene_text.LOSS_KEYS)])
        self.assertEqual(failed['visibility'], [[77, 4, 1], [77, 5, 1]])
        self.assertNotIn(lugia.CAPTURE_FLAG, failed['flags'])
        self.assertTrue(self.run_interaction(failed['flags'])[0])

    def test_eagun_distinguishes_waiting_threat_and_rescue(self):
        captured_flags = dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        for count, captured, index in ((47, 0, 9), (48, 0, 12), (48, 1, 8)):
            flags = flags_for_count(count) | captured_flags | {lugia.CAPTURE_FLAG: captured}
            result = execute(boss._eagun_interaction(0), 0, flags)
            self.assertEqual(result['messages'], [lugia.MESSAGE_IDS[index]])
            self.assertEqual(result['flags'], flags)
            self.assertEqual(result['gifts'], [])

    def test_eagun_defers_gifts_during_threat_and_preserves_them_before_and_after(self):
        from orre_randomizer.engine import event_gifts as events
        fallback = 0x4000
        wrapper = boss._eagun_interaction(0, fallback)
        code = wrapper + bytes(fallback - len(wrapper)) + events._interaction(fallback, 10, 25)
        captures = dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        for count, caught, gifts, prefix in ((25, 0, [5], []), (48, 0, [], [lugia.MESSAGE_IDS[12]]),
                                            (48, 1, [5], [])):
            flags = flags_for_count(count) | captures | {lugia.CAPTURE_FLAG: caught}
            result = execute(code, 0, flags)
            self.assertEqual(result['gifts'], gifts)
            self.assertEqual(result['messages'][:len(prefix)], prefix)
            self.assertEqual(result['flags'].get(2740, 0), int(bool(gifts)))

    def test_after_capture_repeat_visits_go_directly_to_remaining_rewards(self):
        from orre_randomizer.engine import event_gifts as events
        fallback = 0x4000
        wrapper = boss._eagun_interaction(0, fallback)
        code = wrapper + bytes(fallback - len(wrapper)) + events._interaction(fallback, 10, 25)
        flags = flags_for_count(48) | {lugia.CAPTURE_FLAG: 1}
        received = []
        for _visit in range(4):
            # Each call starts with fresh room/thread locals, like re-entry.
            result = execute(code, 0, flags)
            self.assertNotIn(lugia.MESSAGE_IDS[10], result['messages'])
            self.assertNotIn(lugia.MESSAGE_IDS[12], result['messages'])
            self.assertTrue(result['messages'])
            received.extend(result['gifts'])
            self.assertEqual(result['flags'][lugia.CAPTURE_FLAG], 1)
            flags = result['flags']
        self.assertEqual(received, [events.GIFT_IDS['pikachu-event'], events.GIFT_IDS['celebi-event']])

    def test_disabled_rule_never_reads_or_mutates_artifacts(self):
        source = b'not a native ROM'
        output, report = lugia.apply_postgame_lugia(b'', source, Options.none())
        self.assertIs(output, source)
        self.assertFalse(report['enabled'])
        updates = {}
        report = lugia.patch_postgame_lugia_archives(b'', lambda _: self.fail('Unexpected source read'), updates, Options.none())
        self.assertEqual(updates, {})
        self.assertFalse(report['enabled'])

    def test_native_master_ball_handoff_blocks_bonus_until_it_is_received(self):
        from orre_randomizer.engine import event_gifts as events
        flags = flags_for_count(48) | {events.MASTER_BALL_NOTICE_FLAG: 1,
                                      events.MASTER_BALL_RECEIPT_FLAG: 0}
        self.assertEqual(self.run_interaction(flags)[0], [])
        flags[events.MASTER_BALL_RECEIPT_FLAG] = 1
        self.assertEqual(self.run_interaction(flags)[0], [[lugia.BATTLE_ID, 1, 0]])

    def test_battle_room_reload_cannot_restart_the_intro_after_a_failed_snag(self):
        globals_ = {0: 7, 1: 9, scene.SCENE_GLOBAL: 1, scene.ARRIVAL_GLOBAL: 1}
        def battle(*_):
            globals_.clear()
            globals_.update({0: 7, 1: 9})
            return 0
        native = {n: lambda *_: 0 for n in (36, 40, 41, 59, 61, 62, 68, 69, 165, 179)}
        flags = flags_for_count(48) | dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        state = execute(boss._interaction(0), 0, flags, globals_=globals_,
                        builtins=native | {152: battle, 103: lambda *_: 2}, talk_resources=(1, 4))
        self.assertEqual(state['globals'], {0: 7, 1: 9, 2: 0, 3: 1})
        refresh = scene.refresh_guard(0, b'', resume=0x10000, arrival_ready=boss._ready(),
                                      captured=boss.events._call(81, boss.CAPTURE_FLAG), battle_id=boss.BATTLE_ID)
        result = execute(refresh, 0, state['flags'], globals_=globals_, stop_at=0x10000)
        self.assertEqual(result['messages'], [])
        self.assertNotIn(152, [n for n, _ in result['calls']])


class LugiaVisibilityRefreshTests(unittest.TestCase):
    @staticmethod
    def shrine_script():
        # A format-only carrier; proprietary native script bytes are not needed
        # to exercise the appended visibility path and its loop-tail guards.
        from orre_randomizer.engine import event_gifts as events
        data = bytearray(0x2900)
        struct.pack_into('>H', data, 4, 12)
        struct.pack_into('>II', data, 12, 0x48, 0x48)
        loop = (events._statement(31) + events._push(1) + b'\x24\x00\x00\x00\x01\x03\x81\x00\x00'
                + b'\x06\x00\x00\x20\x56')
        data[0x2583:0x25B0] = loop
        data[0x40F:0x414] = bytes.fromhex('0382000105')
        return bytes(data)

    def patch_script(self, source, current=None):
        with patch.object(boss.events, '_fingerprint'):
            return boss._patch_script(source, source if current is None else current)

    def test_idle_loop_refreshes_only_bonus_actor_after_last_purification(self):
        source = self.shrine_script()
        output, report = self.patch_script(source)
        entry = report['visibility_refresh_entry']
        self.assertEqual(output[0x25AB:0x25B0], b'\x06' + struct.pack('>I', entry))
        # Native player event processing and its yield remain byte-for-byte.
        self.assertEqual(output[0x2583:0x25AB], source[0x2583:0x25AB])
        captures = dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        before = flags_for_count(47) | captures
        for flags, expected in ((before, 0), (flags_for_count(48) | captures, 1),
                                (flags_for_count(48) | captures | {lugia.CAPTURE_FLAG: 1}, 0)):
            result = execute(output, 0x25AB, flags, stop_at=0x2056, globals_={scene.ARRIVAL_GLOBAL: 1})
            self.assertEqual(result['visibility'], [[77, 4, expected], [77, 5, expected]])
            self.assertEqual(result['flags'], flags)
            self.assertEqual(result['messages'], [])
            self.assertEqual(result['gifts'], [])
            self.assertLessEqual(result['depth'], 9)

    def test_missing_native_capture_or_story_flag_keeps_actor_hidden(self):
        output, _ = self.patch_script(self.shrine_script())
        ready = flags_for_count(48) | dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        for missing in (*STORY_FLAGS, *(2125 + sid for sid in SHADOW_IDS),
                        *(1261 + sid for sid in SHADOW_IDS)):
            flags = ready | {missing: 0}
            result = execute(output, 0x25AB, flags, stop_at=0x2056,
                             builtins={103: lambda *_: 0})
            self.assertEqual(result['visibility'], [[77, 4, 0], [77, 5, 0]])

    def test_final_purification_does_not_activate_the_encounter_before_mail(self):
        output, _ = self.patch_script(self.shrine_script())
        ready = flags_for_count(48) | dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        globals_ = {scene.SCENE_GLOBAL: 0, scene.ARRIVAL_GLOBAL: 0}
        dormant = ready | {scene.INTRO_STATE_FLAG: 0}
        first = execute(output, 0x25AB, dormant, stop_at=0x2056, globals_=globals_)
        self.assertEqual(first['visibility'], [[77, 4, 0], [77, 5, 0]])
        self.assertEqual(first['messages'], [])
        self.assertEqual(first['flags'], dormant)
        self.assertNotIn(152, [n for n, _ in first['calls']])
        # Even a newly available mission waits for a fresh room visit, leaving
        # the current purification ceremony and its controls undisturbed.
        available = ready | {scene.INTRO_STATE_FLAG: scene.PHASE_AVAILABLE}
        still_here = execute(output, 0x25AB, available, stop_at=0x2056, globals_=globals_)
        self.assertEqual(still_here['messages'], [])
        self.assertEqual(still_here['flags'], available)

    def test_shared_latch_prevents_idle_task_from_interrupting_departure(self):
        output, _ = self.patch_script(self.shrine_script())
        flags = flags_for_count(48) | {lugia.CAPTURE_FLAG: 1}
        result = execute(output, 0x25AB, flags, stop_at=0x2056, globals_={scene.SCENE_GLOBAL: 1})
        self.assertEqual(result['visibility'], [])
        self.assertEqual(result['globals'][scene.SCENE_GLOBAL], 1)

    def test_scene_global_is_appended_without_reusing_native_two(self):
        source = bytearray(self.shrine_script())
        source[0x48:0x50] = bytes.fromhex('1234567887654321')
        output, report = self.patch_script(bytes(source))
        at = report['globals_offset']
        self.assertEqual(output[at:at + 16], bytes(source[0x48:0x50]) + bytes(8))
        self.assertEqual(u32(output, 12), u32(source, 12))

    def test_first_arrival_continues_into_battle_without_a_repeated_challenge(self):
        output, _ = self.patch_script(self.shrine_script())
        flags = flags_for_count(48) | dict.fromkeys((2125 + sid for sid in SHADOW_IDS), 1)
        native = {n: lambda *_: 0 for n in (36, 40, 41, 59, 61, 62, 68, 69, 165, 179, 152)}
        state = execute(output, 0x25AB, flags, stop_at=0x2056,
                        builtins=native | {103: lambda *_: 2}, talk_resources=(1, 4))
        self.assertEqual(state['messages'], [scene_text.MESSAGE_IDS[k]
                         for k in (*scene_text.ARRIVAL_KEYS, *scene_text.RETRY_KEYS)])
        self.assertEqual([args for n, args in state['calls'] if n == 152], [[boss.BATTLE_ID, 1, 0]])
        self.assertEqual(state['globals'], {scene.ARRIVAL_GLOBAL: 1, scene.SCENE_GLOBAL: 0})
        self.assertEqual(state['flags'], flags | {scene.INTRO_STATE_FLAG: scene.PHASE_INTRODUCED})

    def test_unknown_native_or_prepatched_idle_loop_is_rejected(self):
        source = self.shrine_script()
        original_changed = bytearray(source)
        original_changed[0x25AF] ^= 1
        with self.assertRaisesRegex(FormatError, 'idle-loop signature'):
            self.patch_script(bytes(original_changed))
        current_changed = bytearray(source)
        current_changed[0x259C] ^= 1
        with self.assertRaisesRegex(FormatError, 'idle-loop signature'):
            self.patch_script(source, bytes(current_changed))


class LugiaMessageTests(unittest.TestCase):
    def test_all_six_languages_preserve_existing_opaque_payloads(self):
        for language in ('UK', 'US', 'FR', 'GE', 'IT', 'SP', 'JP'):
            original = bank(language)
            names = {boss.BOSS_NAME_ID: boss.NAMES[language], 0x10E1: 'Native elder'}
            texts = boss.localized_dialogue(language, names)
            output = boss._append_strings(original, lugia.MESSAGE_IDS, texts)
            count = struct.unpack_from('>H', original, 4)[0]
            growth = len(lugia.MESSAGE_IDS) * 8
            self.assertEqual(output[16 + count * 8 + growth:len(original) + growth], original[16 + count * 8:])
            for index in range(count):
                self.assertEqual(u32(output, 16 + index * 8), u32(original, 16 + index * 8))
                self.assertEqual(u32(output, 20 + index * 8), u32(original, 20 + index * 8) + growth)
            key = 'UK' if language == 'US' else language
            for text in texts:
                self.assertNotIn('\n', text)
                self.assertIn(text.encode('utf-16-be'), output)
            with self.assertRaises(FormatError):
                boss._append_strings(output, lugia.MESSAGE_IDS, texts)


class LugiaTeamTests(unittest.TestCase):
    def test_disabled_event_does_not_resolve_a_dormant_shadow_choice(self):
        options = replace(Options.none(), postgame_randomize_lugia=True, custom_shinies=True)
        self.assertEqual(boss.bonus_shadow_species(b"not a ROM", "dormant", options), 249)

    def plan(self, options):
        data = bytearray(0x60000)
        natives = {394: 282, 178: 178, 362: 356, 343: 365, 282: 257, 249: 249}
        dex = {**{i: i for i in range(1, 7)}, **natives}
        catalog = {i: {"offset": i * 0x200, "total": 500, "national_dex": national,
                       "types": (0, 0), "abilities": (1, 1), "stats": (80,) * 6}
                   for i, national in dex.items()}
        tables = {"trainer_pokemon": {"offset": 0, "stride": 0x50},
                  "shadow": {"offset": 0x58000, "stride": 0x38, "count": 97}}
        for index in range(6):
            for number, field in enumerate((0x36, 0x3E, 0x46, 0x4E)):
                struct.pack_into(">H", data, (4110 + index) * 0x50 + field, index * 10 + number + 1)
        with (patch.object(boss, "expanded_layout", return_value=tables),
              patch.object(boss, "species_catalog", return_value=catalog),
              patch.object(boss, "evolution_families", return_value=({i: i for i in catalog}, {})),
              patch.object(boss, "move_catalog", return_value={}),
              patch.object(boss, "choose_moves", return_value=[1, 2, 3, 4])):
            return boss.plan_team(data, data, "commander-test", options)

    def test_bonus_only_copy_profile_reuses_native_five_without_changing_dormant_filters(self):
        options = replace(Options.none(), postgame_shadow_lugia=True)
        first = self.plan(options)
        self.assertEqual(first, self.plan(options))
        self.assertEqual([row["species"] for row in first], [394, 178, 362, 343, 282, 249])
        self.assertEqual([row["source_slot"] for row in first], [4111, 4112, 4113, 4114, 4115, 4110])
        self.assertEqual(first[0]["moves"], [11, 12, 13, 14])
        self.assertEqual([row["level"] for row in first], list(range(65, 71)))
        self.assertEqual(len({row["family"] for row in first}), 6)
        self.assertEqual(first[-1]["shadow_id"], 96)
        self.assertEqual(first[-1]["moves"], [177, 94, 105, 56])
        self.assertNotIn(356, first[-1]["moves"])
        self.assertFalse(options.allow_gen1 or options.allow_gen2 or options.allow_gen3)

    def test_replacement_filters_do_not_remove_an_unchanged_native_roster(self):
        options = replace(Options.none(), postgame_shadow_lugia=True, excluded_species=(282,), excluded_types=(0,))
        self.assertEqual([row["species"] for row in self.plan(options)], [394, 178, 362, 343, 282, 249])

    def test_randomized_ordinary_members_honor_filters_and_distinct_families(self):
        options = replace(Options.none(), postgame_shadow_lugia=True, randomize_trainers=True,
                          postgame_randomize_team=True, allow_gen1=True, excluded_species=(1,))
        team = self.plan(options)
        self.assertEqual({row["species"] for row in team[:-1]}, {2, 3, 4, 5, 6})
        self.assertEqual(team[-1]["species"], 249)
        self.assertEqual(len({row["family"] for row in team}), 6)

    def test_randomized_shadow_restoration_contains_four_regular_moves(self):
        options = replace(Options.none(), postgame_shadow_lugia=True, randomize_trainer_moves=True,
                          postgame_randomize_lugia=True, allow_gen1=True)
        shadow = self.plan(options)[-1]
        self.assertEqual(shadow["moves"], [1, 2, 3, 4])
        self.assertNotIn(356, shadow["moves"])

    def test_an_active_randomizer_does_not_silently_reenable_excluded_generations(self):
        options = replace(Options.none(), postgame_shadow_lugia=True, randomize_trainers=True,
                          postgame_randomize_team=True)
        with self.assertRaises(FormatError):
            self.plan(options)

    def test_general_randomization_does_not_replace_the_authored_quest_team(self):
        team = self.plan(replace(Options.recommended(), postgame_shadow_lugia=True))
        self.assertEqual([row["species"] for row in team], [*boss.DEFAULT_TEAM, 249])
        self.assertEqual(team[0]["moves"], [11, 12, 13, 14])
        self.assertEqual(team[-1]["moves"], [177, 94, 105, 56])
        self.assertTrue(all(not row["randomized"] for row in team))

    def test_the_two_event_choices_are_independent_of_general_trainer_and_shadow_switches(self):
        for regular in (False, True):
            for final in (False, True):
                with self.subTest(regular=regular, final=final):
                    options = replace(Options.none(), postgame_shadow_lugia=True,
                                      allow_gen1=True, postgame_randomize_team=regular,
                                      postgame_randomize_lugia=final)
                    team = self.plan(options)
                    self.assertEqual(team[-1]["species"] != 249, final)
                    self.assertEqual([row["species"] for row in team[:-1]] != list(boss.DEFAULT_TEAM), regular)
                    self.assertEqual(len({row["family"] for row in team}), 6)
                    self.assertEqual([row["shadow_id"] for row in team], [0, 0, 0, 0, 0, 96])


def numeric_rel():
    """A small real REL v3 carrier with duplicated base-pointer relocations."""
    data = bytearray(0x190)
    struct.pack_into('>I', data, 0, 125)
    struct.pack_into('>II', data, 0xC, 5, 0x4C)
    struct.pack_into('>I', data, 0x1C, 3)
    struct.pack_into('>II', data, 0x24, 0x128, 0x120)
    struct.pack_into('>I', data, 0x2C, 8)
    struct.pack_into('>I', data, 0x48, 0x128)
    struct.pack_into('>II', data, 0x4C + 4 * 8, 0x80, 0xA0)
    data[0xA0:0xB0] = bytes(range(16))
    struct.pack_into('>I', data, 0xB0, 4)
    struct.pack_into('>II', data, 0x120, 125, 0x128)
    # The relocation stream writes two pointers to the table and one to count.
    rows = ((0, 202, 4, 0), (0, 1, 4, 0x20), (4, 1, 4, 0x20),
            (4, 1, 4, 0x30), (0, 203, 0, 0))
    for index, row in enumerate(rows):
        struct.pack_into('>HBBI', data, 0x128 + index * 8, *row)
    return bytes(data)


class LugiaRelocationTests(unittest.TestCase):
    def test_runtime_pointers_follow_extended_numeric_table_and_counts(self):
        original = numeric_rel()
        symbols = rel_symbols(original, parse_rel(original))
        current = bytearray(original)
        current[0xA5] = 240  # An earlier randomization must survive the clone.
        output, report = lugia._extend_tables(original, bytes(current), symbols,
                                              (('numbers', 0, 1, 4, 4, b'ABCD'),))
        table = report['tables']['numbers']
        self.assertEqual(table['count'], 5)
        self.assertEqual(output[table['offset']:table['offset'] + 20], bytes(current[0xA0:0xB0]) + b'ABCD')
        self.assertEqual(output[0xA0:0xB0], current[0xA0:0xB0])
        self.assertEqual(u32(output, 0xB0), 5)
        self.assertEqual(len(report['retargeted']), 2)
        after = parse_rel(output)
        new_symbols = rel_symbols(output, after)
        self.assertEqual(new_symbols[0]['offset'], table['offset'])
        self.assertEqual(new_symbols[1]['offset'], 0xB0)
        self.assertEqual(after['sections'][4]['size'], 0xA0 + report['growth'])

    def test_pointer_bearing_records_are_rejected_before_relocation(self):
        original = bytearray(numeric_rel())
        # Move a pointer write into the table payload itself.
        struct.pack_into('>H', original, 0x130, 0x20)
        symbols = rel_symbols(original, parse_rel(original))
        with self.assertRaises(FormatError):
            lugia._extend_tables(bytes(original), bytes(original), symbols,
                                  (('numbers', 0, 1, 4, 4, b'ABCD'),))


if __name__ == '__main__':
    unittest.main()
