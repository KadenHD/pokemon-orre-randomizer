"""Legacy gift gating recovery uses archive bytes, never a save or emulator."""
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from orre_randomizer.engine import event_gifts as events, event_story_recovery as recovery
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.rebuild_iso import decoded_member
try:
    from tests.test_event_gifts import execute, flags_for_count
except ModuleNotFoundError:
    from test_event_gifts import execute, flags_for_count


def native_home():
    data = bytearray(0x4160)
    struct.pack_into('>I', data, 0x38, 0x3561)
    data[0x649:0x678] = events._statement(50, events._local(1), 0, 0)
    data[0x678:0x68C] = events._push(0) + events._push(1) + b'\x1f\x82\x42' + events._POP + b'\x05'
    return bytes(data)


def native_shrine():
    data = bytearray(0x28E0)
    struct.pack_into('>H', data, 4, 12)
    struct.pack_into('>II', data, 12, 0x48, 0x48)
    data[0x24A:0x279] = events._statement(50, events._local(1), 1, 0)
    return bytes(data)


def legacy_shrine(original, pikachu=10, celebi=25):
    data = bytearray(original + events._interaction(len(original), pikachu, celebi,
                                                   story_predicate=recovery._legacy_predicate()))
    visibility = len(data)
    data.extend(original[0x24A:0x26A] + recovery._legacy_predicate() + original[0x270:0x279]
                + b'\x06' + struct.pack('>I', 0x279))
    data.extend(bytes(-len(data) % 4))
    globals_ = len(data)
    data.extend(original[0x48:0x50])
    struct.pack_into('>H', data, 4, 13)
    struct.pack_into('>I', data, 0x48, len(original))
    struct.pack_into('>II', data, 12, globals_, globals_)
    data[0x24A:0x24F] = b'\x06' + struct.pack('>I', visibility)
    return bytes(data)


class StoryRecoveryTests(unittest.TestCase):
    def test_native_home_route_is_independent_of_every_purification_count(self):
        original = native_home()
        with patch.object(events, '_fingerprint'):
            output, _ = events._patch_home_cms(original)
        self.assertEqual(output, original)
        for count in range(49):
            flags = flags_for_count(count) | {events.PHONE_EXCHANGE_FLAG: 0}
            state = execute(output, u32(output, 0x38), flags, stop_at=0x3561)
            self.assertEqual(state['flags'], flags)
            self.assertEqual(state['gifts'], [])
            self.assertEqual(state['messages'], [])

    def test_home_restores_native_route_and_preserves_all_other_bytes(self):
        original = native_home()
        current = bytearray(recovery._legacy_home(original))
        current[0x2000:0x2004] = b'KEEP'  # An unrelated earlier randomizer patch.
        with patch.object(events, '_fingerprint'):
            output, report = recovery.restore_native_home(original, bytes(current))
        self.assertEqual(u32(output, 0x38), 0x3561)
        self.assertEqual(output[0x678:0x68C], original[0x678:0x68C])
        self.assertEqual(output[0x2000:0x2004], b'KEEP')
        self.assertEqual(output[len(original):], current[len(original):])
        self.assertFalse(report['saved_progression_modified'])
        for i, (a, b) in enumerate(zip(output, current)):
            if a != b:
                self.assertTrue(0x38 <= i < 0x3C or 0x678 <= i < 0x68C)

    def test_legacy_early_gift_is_blocked_until_native_phone_exchange(self):
        original = native_shrine()
        current = legacy_shrine(original)
        flags = flags_for_count(48)
        flags[events.PHONE_EXCHANGE_FLAG] = 0
        self.assertEqual(execute(current, len(original), flags)['gifts'], [5])
        with patch.object(events, '_fingerprint'):
            output, report = recovery.gate_legacy_shrine(original, current)
        result = execute(output, report['guard_entry'], flags)
        self.assertEqual(result['flags'], flags)
        self.assertEqual(result['gifts'], [])
        self.assertEqual(result['messages'], [])
        flags[events.PHONE_EXCHANGE_FLAG] = 1
        self.assertEqual(execute(output, report['guard_entry'], flags)['gifts'], [5])

    def test_receipts_thresholds_and_native_master_ball_priority_are_preserved(self):
        original = native_shrine()
        for thresholds in ((0, 48), (25, 10), (1, 0)):
            current = legacy_shrine(original, *thresholds)
            with patch.object(events, '_fingerprint'):
                output, report = recovery.gate_legacy_shrine(original, current)
            self.assertEqual(report['thresholds'], list(thresholds))
            flags = flags_for_count(48) | {events.RECEIPT_FLAGS['pikachu-event']: 1,
                                          events.MASTER_BALL_NOTICE_FLAG: 1}
            blocked = execute(output, report['guard_entry'], flags)
            self.assertEqual(blocked['flags'], flags)
            self.assertEqual(blocked['gifts'], [])
            flags[events.MASTER_BALL_RECEIPT_FLAG] = 1
            result = execute(output, report['guard_entry'], flags)
            self.assertEqual(result['gifts'], [6])
            self.assertEqual(result['flags'][events.RECEIPT_FLAGS['pikachu-event']], 1)

    def test_unknown_legacy_appends_or_interactions_are_refused(self):
        home = native_home()
        current = bytearray(recovery._legacy_home(home))
        current[-2] ^= 1
        with patch.object(events, '_fingerprint'), self.assertRaises(FormatError):
            recovery.restore_native_home(home, bytes(current))
        shrine = native_shrine()
        current = bytearray(legacy_shrine(shrine))
        current[len(shrine) + 4] ^= 1
        with patch.object(events, '_fingerprint'), self.assertRaises(FormatError):
            recovery.gate_legacy_shrine(shrine, bytes(current))


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'game/files'
QA = ROOT / 'build/v1220-story-recovery-qa'


@unittest.skipUnless(all((GAME / name).is_file() and (QA / name).is_file()
                        for name in events.ARCHIVE_NAMES), 'requires private original and affected archive extracts')
class AffectedArchiveTests(unittest.TestCase):
    def test_native_phone_handoff_has_no_purification_count_requirement(self):
        original = (GAME/events.ARCHIVE_NAMES[1]).read_bytes()
        cms = decoded_member(original, parse_fsys(original)['members'][1])
        def set_true(args, flags):
            flags[args[0]] = 1
            return 0
        for count in range(49):
            flags = flags_for_count(count) | {events.PHONE_EXCHANGE_FLAG: 0, 2499: 0}
            state = execute(cms, 0x337C, flags, stop_at=0x350C,
                            builtins={7: lambda *_: 0, 8: lambda *_: 0, 78: set_true},
                            talk_resources=(0,))
            self.assertEqual(state['flags'], flags | {events.PHONE_EXCHANGE_FLAG: 1, 2499: 1})
            self.assertEqual(state['gifts'], [])

    def test_real_affected_archives_change_only_the_known_cms_member_in_memory(self):
        for name in events.ARCHIVE_NAMES:
            original, current = (GAME / name).read_bytes(), (QA / name).read_bytes()
            output, report = recovery.repair_legacy_event_archive(original, current, name, region='GC6P01')
            before, after = parse_fsys(current)['members'], parse_fsys(output)['members']
            for a, b in zip(before, after):
                if a['index'] != 1:
                    self.assertEqual(decoded_member(current, a), decoded_member(output, b))
            self.assertTrue(report['only_cms_changed'])
            if name == events.ARCHIVE_NAMES[1]:
                source_cms = decoded_member(original, parse_fsys(original)['members'][1])
                repaired_cms = decoded_member(output, after[1])
                self.assertEqual(repaired_cms[0x312A:0x351F], source_cms[0x312A:0x351F])
                # Model the unchanged native handoff once its native scene has
                # started. Its std78 calls set3535 and2499 to1; no save is read.
                def set_true(args, flags):
                    flags[args[0]] = 1
                    return 0
                state = execute(repaired_cms, 0x337C, {}, stop_at=0x350C,
                                builtins={7: lambda *_: 0, 8: lambda *_: 0, 78: set_true},
                                talk_resources=(0,))
                self.assertEqual(state['flags'], {events.PHONE_EXCHANGE_FLAG: 1, 2499: 1})
            self.assertEqual(current, (QA / name).read_bytes())


if __name__ == '__main__':
    unittest.main()
