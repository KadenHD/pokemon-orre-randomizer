"""Native facing calls and a departure route inside the original shrine CCD."""
from pathlib import Path
import math
import struct
import unittest

from orre_randomizer.engine import event_gifts as events, postgame_scene as scene
from orre_randomizer.engine import postgame_boss as boss, postgame_scene_text as text
from orre_randomizer.engine import postgame_scene_model as field
from orre_randomizer.engine.analyze_game import parse_fsys, u32
from orre_randomizer.engine.rebuild_iso import decoded_member
from tests.test_event_gifts import execute


ROOT = Path(__file__).resolve().parents[1]


class NativeStagingCallsTests(unittest.TestCase):
    def test_lugia_faces_eagun_before_his_live_dialogue_only(self):
        for key in text.ORDERED_KEYS:
            with self.subTest(key=key):
                state = execute(scene.talk(key) + b"\x05", 0, {}, talk_resources=(1, 4),
                                builtins={165: lambda *_: 0, 62: lambda *_: 0})
                calls = state["calls"]
                facing = [(number, arguments) for number, arguments in calls if number == 165]
                if key in ("arrival_warning", "arrival_stand"):
                    self.assertEqual(facing, [(165, [77, 5, 77, 1, 1.0])])
                    self.assertEqual(calls[:2], [(165, [77, 5, 77, 1, 1.0]), (62, [77, 5, 1])])
                else:
                    self.assertEqual(facing, [])
                self.assertEqual(state["messages"], [text.MESSAGE_IDS[key]])
                self.assertEqual(state["flags"], {})

    def test_capture_walk_finishes_every_central_leg_before_hiding_the_commander(self):
        flags = (dict.fromkeys(events.STORY_FLAGS, 1)
                 | dict.fromkeys((2125 + sid for sid in events.SHADOW_IDS), 1)
                 | dict.fromkeys((1261 + sid for sid in events.SHADOW_IDS), 1)
                 | {scene.INTRO_STATE_FLAG: scene.PHASE_AVAILABLE})

        def capture(arguments, current):
            current[boss.CAPTURE_FLAG] = 1
            return 0

        builtins = {number: lambda *_: 0 for number in (36, 40, 41, 59, 61, 62, 68, 69, 103, 165, 179)}
        builtins[152] = capture
        state = execute(scene.interaction(0, ready=boss._ready(), captured=events._call(81, boss.CAPTURE_FLAG),
                                          battle_id=566), 0, flags, builtins=builtins, talk_resources=(1, 4))
        calls = state["calls"]
        hidden = next(index for index, (number, args) in enumerate(calls)
                      if number == 50 and args == [77, 4, 0])
        moves = [(index, args) for index, (number, args) in enumerate(calls) if number == 61]
        self.assertEqual([tuple(args[3:]) for _, args in moves], list(scene.DEPARTURE_PATH))
        self.assertEqual(len(moves), 5)
        for index, arguments in moves:
            self.assertEqual(arguments[:3], [77, 4, 1])
            self.assertEqual(calls[index + 1:index + 3], [(69, [77, 4, 1.0]), (62, [77, 4, 1])])
            self.assertLess(index + 2, hidden)
        self.assertEqual(tuple(moves[-1][1][3:]), (0.0, 0.0, 125.0))
        self.assertEqual(calls[hidden + 1][0], 36)
        final_dialogue = [text.MESSAGE_IDS[key] for key in text.CAPTURE_AFTER_EXIT_KEYS]
        self.assertEqual(state["messages"][-3:], final_dialogue)
        for identifier in final_dialogue:
            speech = next(index for index, (number, args) in enumerate(calls)
                          if number == 54 and args[-1] == identifier)
            self.assertGreater(speech, hidden)
        self.assertEqual(state["globals"][scene.SCENE_GLOBAL], 0)
        facing = [(index, args) for index, (number, args) in enumerate(calls)
                  if number == 165]
        self.assertEqual([args[:4] for _, args in facing], [
            [77, 1, 0, 100], [0, 100, 77, 1], [0, 101, 77, 1]])
        self.assertTrue(all(index > hidden for index, _ in facing))

    def test_capture_restages_both_heroes_before_the_first_camera_yield(self):
        from tests.test_postgame_scene import native_calls
        code = scene.interaction(0, ready=events._push(1),
                                 captured=events._call(81, boss.CAPTURE_FLAG), battle_id=566)
        captured_branch = code.index(scene.visibility(4, True) + scene.visibility(5, False))
        first_camera = code.index(scene.camera(*scene.POST_BATTLE_CAMERA), captured_branch)
        setup = native_calls(code[captured_branch:first_camera])
        placements = [args for _, number, args, _ in setup if number == 59]
        self.assertEqual(len(placements), 2)
        for arguments, actor, position in zip(placements, (100, 101),
                                              (scene.HERO_APPROACH, scene.PARTNER_APPROACH), strict=True):
            self.assertEqual(arguments[:2], [0, actor])
            for actual, expected in zip(arguments[2:], position, strict=True):
                self.assertAlmostEqual(actual, expected, places=5)
        self.assertFalse({61, 62} & {number for _, number, _, _ in setup})


class OriginalShrineCollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "game/files/M3_shrine_1F.fsys"
        if not path.exists():
            raise unittest.SkipTest("requires the local original shrine CCD; no ROM or save is written")
        archive = path.read_bytes()
        member = next(row for row in parse_fsys(archive)["members"]
                      if int(row["identifier_raw"], 16) == 0x030D0600)
        source = decoded_member(archive, member)
        cls.triangles = []
        for index in range(u32(source, 4)):
            object_ = u32(source, 0) + index * 0x40
            block = u32(source, object_ + 0x24)
            if not block:
                continue
            if struct.unpack_from(">9f", source, object_) != (0.0,) * 6 + (1.0,) * 3:
                raise AssertionError("unexpected transformed native walk object")
            first, count = struct.unpack_from(">II", source, block)
            for triangle in range(count):
                values = struct.unpack_from(">9f", source, first + triangle * 0x34)
                cls.triangles.append(tuple(tuple(values[start:start + 3]) for start in (0, 3, 6)))

    @staticmethod
    def inside(point, triangle):
        x, z = point
        sides = [(x - first[0]) * (second[2] - first[2]) - (z - first[2]) * (second[0] - first[0])
                 for first, second in zip(triangle, (triangle[1], triangle[2], triangle[0]))]
        return all(value >= -1e-5 for value in sides) or all(value <= 1e-5 for value in sides)

    def test_departure_has_four_units_of_walkable_clearance_including_the_narrow_steps(self):
        self.assertEqual(len(self.triangles), 58)
        self.assertLess(max(abs(vertex[1]) for triangle in self.triangles for vertex in triangle), 0.00001)
        self.assertAlmostEqual(max(vertex[2] for triangle in self.triangles for vertex in triangle), 130.0, places=3)
        path = ((-14.0, 0.0, 15.0), *scene.DEPARTURE_PATH)
        for first, last in zip(path, path[1:]):
            count = math.ceil(math.dist(first, last))
            for step in range(count + 1):
                x, _, z = (a + (b - a) * step / count for a, b in zip(first, last))
                for angle in range(0, 360, 45):
                    point = (x + 4 * math.sin(math.radians(angle)), z + 4 * math.cos(math.radians(angle)))
                    self.assertTrue(any(self.inside(point, triangle) for triangle in self.triangles),
                                    f"departure leaves native walk floor near {point}")
        # This witness regresses the former route's collision/snap risk.
        self.assertFalse(any(self.inside((-15.9, 72.0), triangle) for triangle in self.triangles))

    def test_lugia_has_space_behind_the_commander_and_stays_on_the_native_floor(self):
        self.assertGreater(math.dist(field.POSITION, (-14.0, 0.0, 15.0)), 22.0)
        for angle in range(0, 360, 15):
            point = (field.POSITION[0] + 4 * math.sin(math.radians(angle)),
                     field.POSITION[2] + 4 * math.cos(math.radians(angle)))
            self.assertTrue(any(self.inside(point, triangle) for triangle in self.triangles))

    def test_departure_clears_the_lectern_and_the_restaged_heroes(self):
        def distance(point, first, last):
            delta = tuple(b - a for a, b in zip(first, last))
            length = sum(value * value for value in delta)
            t = max(0.0, min(1.0, sum((p - a) * d for p, a, d in zip(point, first, delta)) / length))
            return math.dist(point, tuple(a + t * d for a, d in zip(first, delta)))

        start = (-14.0, 0.0, 15.0)
        lectern = (-4.0, 0.0, 20.05)
        path = (start, *scene.DEPARTURE_PATH)
        for obstacle in (lectern, scene.HERO_APPROACH, scene.PARTNER_APPROACH, (9.0, 0.0, 15.0)):
            self.assertGreaterEqual(min(distance(obstacle, a, b) for a, b in zip(path, path[1:])), 8.0)
        # The native trace exposed this straight first leg's sixty-frame snap.
        self.assertLess(distance(lectern, start, (0.0, 0.0, 45.0)), 8.0)


if __name__ == "__main__":
    unittest.main()
