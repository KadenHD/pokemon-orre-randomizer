"""Pure CMS ABI and control-flow checks for the optional shrine staging."""
import struct
import unittest

from orre_randomizer.engine import event_gifts as events, postgame_scene as scene
from orre_randomizer.engine import postgame_scene_text as text


def native_calls(code):
    """Decode literal/native-local call sites, without running game functions."""
    prefix = events._local(0)
    result = []
    for start in range(len(code)):
        if not code.startswith(prefix, start):
            continue
        cursor = start + len(prefix)
        arguments = []
        while code[cursor:cursor + 2] in (b"\x08\x02", b"\x08\x03"):
            kind = code[cursor + 1]
            value = struct.unpack_from(">f" if kind == 3 else ">i", code, cursor + 2)[0]
            cursor += 6
            if code[cursor:cursor + 4] == b"\x10\x42\x00\x01":
                value = ("local", value)
                cursor += 4
            arguments.append(value)
        if not arguments or code[cursor:cursor + 1] != b"\x25":
            continue
        returns, count = struct.unpack_from(">HH", code, cursor + 1)
        if count != len(arguments):
            raise AssertionError("native CMS argument count mismatch")
        result.append((start, arguments[0], arguments[1:], returns))
    return result


def instruction_boundaries(code, base):
    sizes = {3: 4, 5: 1, 6: 5, 7: 5, 8: 6, 16: 4, 17: 2,
             29: 3, 31: 3, 36: 5, 37: 5}
    cursor = 0
    boundaries, branches = set(), []
    while cursor < len(code):
        boundaries.add(base + cursor)
        opcode = code[cursor]
        if opcode not in sizes:
            raise AssertionError(f"unexpected scene opcode {opcode:#x} at {cursor:#x}")
        if opcode in (6, 7):
            branches.append(struct.unpack_from(">I", code, cursor + 1)[0])
        cursor += sizes[opcode]
    if cursor != len(code):
        raise AssertionError("scene instruction is truncated")
    return boundaries, branches


class NativeSceneHelperTests(unittest.TestCase):
    def test_float_move_turn_wait_and_camera_match_verified_native_signatures(self):
        calls = native_calls(scene.move(0, 100, (10.0, 0.0, 28.06))
                             + scene.wait_for_movement(0, 100)
                             + scene.turn(0, 101, 150.0)
                             + scene.camera(*scene.SHRINE_CAMERA))
        self.assertEqual([row[1] for row in calls], [61, 69, 62, 68, 62, 36, 40, 41])
        self.assertEqual(calls[0][2][:3], [0, 100, 1])
        self.assertEqual(len(calls[0][2]), 6)
        self.assertAlmostEqual(calls[0][2][-1], 28.06, places=4)
        self.assertEqual(calls[1][2], [0, 100, 1.0])
        self.assertEqual(calls[2][2], [0, 100, 1])
        self.assertEqual(calls[3][2], [0, 101, 150.0])
        for _, _, _, returns in calls:
            self.assertEqual(returns, 1)
        self.assertEqual(scene.floating(1.0), b"\x08\x03\x3f\x80\x00\x00")

    def test_pause_matches_original_shrine_and_home_bytes(self):
        self.assertEqual(scene.pause(60).hex(), "08020000003c240000000103810000")
        self.assertEqual(scene.pause(30).hex(), "08020000001e240000000103810000")
        for value in (-1, 0.5):
            with self.assertRaises(ValueError):
                scene.pause(value)
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                scene.floating(value)

    def test_latch_uses_new_shared_global_two_and_not_local_or_save_flags(self):
        self.assertEqual(scene.SCENE_GLOBAL, 2)
        self.assertEqual(scene.global_get().hex(), "08020000000210020001")
        self.assertEqual(scene.global_set(1).hex(), "0802000000020802000000011f820203820001")
        self.assertEqual(native_calls(scene.global_get() + scene.global_set(0)), [])
        for function in (scene.global_get, lambda index: scene.global_set(0, index)):
            with self.assertRaises(ValueError):
                function(-1)

    def test_refresh_guard_skips_visibility_while_scene_latch_is_active(self):
        base, resume = 0x9000, 0x2056
        refresh = scene.visibility(scene.BOSS_ACTOR, True)
        code = scene.refresh_guard(base, refresh, resume=resume)
        boundaries, branches = instruction_boundaries(code, base)
        self.assertEqual(code[:12], scene.global_get() + b"\x11\x82")
        self.assertEqual(branches[-1], resume)
        self.assertIn(branches[0], boundaries)
        self.assertEqual(code[branches[0] - base:], b"\x06" + struct.pack(">I", resume))
        self.assertIn(refresh, code)

    def test_idle_refresh_marks_first_visit_before_testing_arrival_eligibility(self):
        base, resume = 0x9000, 0x2056
        ready, captured = events._call(81, 4242), events._call(81, 2221)
        refresh = scene.visibility(scene.BOSS_ACTOR, True)
        code = scene.refresh_guard(base, refresh, resume=resume,
                                   arrival_ready=ready, captured=captured)
        boundaries, branches = instruction_boundaries(code, base)
        self.assertEqual(scene.ARRIVAL_GLOBAL, 3)
        self.assertTrue(set(branches) <= boundaries | {resume})
        self.assertEqual(code.count(scene.global_set(1, scene.ARRIVAL_GLOBAL)), 1)
        self.assertLess(code.index(refresh), code.index(scene.global_get(scene.ARRIVAL_GLOBAL)))
        self.assertLess(code.index(scene.global_set(1, scene.ARRIVAL_GLOBAL)), code.index(ready))
        self.assertTrue(code.endswith(b"\x06" + struct.pack(">I", resume)))
        with self.assertRaises(ValueError):
            scene.refresh_guard(base, refresh, resume=resume, arrival_ready=ready)


class CompiledSceneTests(unittest.TestCase):
    def setUp(self):
        self.base = 0xA000
        self.ready = events._push(1)
        self.captured = events._call(81, 2221)

    def assert_valid_scene(self, code):
        boundaries, branches = instruction_boundaries(code, self.base)
        self.assertTrue(set(branches) <= boundaries)
        self.assertTrue(code.endswith(b"\x05"))
        calls = native_calls(code)
        self.assertFalse({78, 79} & {row[1] for row in calls})
        self.assertTrue(all(row[2] == [scene.INTRO_STATE_FLAG, scene.PHASE_INTRODUCED]
                            for row in calls if row[1] == 80))
        self.assertEqual([row[1] for row in calls][-2:], [179, 33])
        self.assertEqual([row for row in calls if row[1] == 179][0][2][1], 1)
        return calls

    def test_arrival_consumes_native_tail_then_guards_before_taking_control(self):
        code = scene.arrival(self.base, ready=self.ready, captured=self.captured)
        calls = self.assert_valid_scene(code)
        self.assertTrue(code.startswith(events._POP + self.ready))
        boundaries, branches = instruction_boundaries(code, self.base)
        self.assertEqual(branches[:2], [self.base + len(code) - 1] * 2)
        self.assertNotIn(59, [row[1] for row in calls])
        moves = [row for row in calls if row[1] == 61]
        self.assertEqual([row[2][:3] for row in moves], [[0, 100, 1], [0, 101, 1]])
        self.assertLess(moves[-1][0], next(row[0] for row in calls if row[1] == 62))
        self.assertEqual([row[2][-1] for row in calls if row[1] == 54],
                         [text.MESSAGE_IDS[key] for key in text.ARRIVAL_KEYS])
        marker = next(row for row in calls if row[1] == 80)
        self.assertGreater(marker[0], max(row[0] for row in calls if row[1] == 54))

    def test_first_intro_records_only_its_new_flag_before_native_battle(self):
        code = scene.arrival(self.base, ready=self.ready, captured=self.captured,
                             battle_id=566)
        calls = native_calls(code)
        last_arrival_message = max(row[0] for row in calls if row[1] == 54 and
                                   row[2][-1] in {text.MESSAGE_IDS[k] for k in text.ARRIVAL_KEYS})
        writes = [row for row in calls if row[1] == 80]
        self.assertEqual([row[2] for row in writes], [[scene.INTRO_STATE_FLAG, scene.PHASE_INTRODUCED]])
        self.assertLess(last_arrival_message, writes[0][0])
        self.assertLess(writes[0][0], next(row[0] for row in calls if row[1] == 152))

    def test_dynamic_speakers_use_native_partner_and_map_actor_groups(self):
        for key in text.ARRIVAL_KEYS + text.CAPTURE_KEYS:
            calls = [row for row in native_calls(scene.talk(key)) if row[1] in (54, 55)]
            speaker = text.SPEAKERS[key]
            group = 0 if speaker in ("hero", "partner") else ("local", 1)
            actor = text.ACTOR_IDS[speaker]
            self.assertEqual(calls[0][1:3], (54, [group, actor, text.MESSAGE_IDS[key]]))
            self.assertEqual(calls[1][1:3], (55, [group, actor]))

    def test_idle_arrival_waits_for_fade_and_resumes_without_popping_a_return(self):
        resume = 0x2056
        code = scene.arrival(self.base, ready=self.ready, captured=self.captured,
                             entry_pop=False, resume=resume)
        self.assertTrue(code.startswith(self.ready))
        self.assertFalse(code.startswith(events._POP))
        boundaries, branches = instruction_boundaries(code, self.base)
        self.assertTrue(set(branches) <= boundaries | {resume})
        self.assertTrue(code.endswith(b"\x06" + struct.pack(">I", resume)))
        calls = native_calls(code)
        first_camera = next(row[0] for row in calls if row[1] == 36)
        first_control = next(row[0] for row in calls if row[1] == 32)
        fade_pause = code.index(scene.pause(60))
        self.assertLess(first_control, fade_pause)
        self.assertLess(fade_pause, first_camera)

    def test_capture_reasserts_latch_and_walks_out_before_final_dialogue(self):
        code = scene.interaction(self.base, ready=self.ready,
                                 captured=self.captured, battle_id=566)
        calls = self.assert_valid_scene(code)
        battle = next(row for row in calls if row[1] == 152)
        self.assertEqual(battle[2], [566, 1, 0])
        battle_end = battle[0] + len(events._statement(152, 566, 1, 0))
        self.assertTrue(code[battle_end:].startswith(scene.global_set(1)))
        moves = [row for row in calls if row[1] == 61]
        self.assertEqual(len(moves), 5)
        for row, point in zip(moves, scene.DEPARTURE_PATH, strict=True):
            self.assertEqual(row[2][:3], [("local", 1), 4, 1])
            for actual, expected in zip(row[2][3:], point, strict=True):
                self.assertAlmostEqual(actual, expected, places=4)
        before = [row[0] for row in calls if row[1] == 54 and
                  row[2][-1] in {text.MESSAGE_IDS[key] for key in text.CAPTURE_BEFORE_EXIT_KEYS}]
        after = [row[0] for row in calls if row[1] == 54 and
                 row[2][-1] in {text.MESSAGE_IDS[key] for key in text.CAPTURE_AFTER_EXIT_KEYS}]
        self.assertLess(max(before), moves[0][0])
        self.assertGreater(min(after), moves[-1][0])
        self.assertIn(scene.visibility(4, True) + scene.visibility(5, False), code)
        self.assertIn(scene.visibility(4, True) + scene.visibility(5, True), code)
        self.assertLess(code.index(scene.visibility(4, False)), min(after))


if __name__ == "__main__":
    unittest.main()
