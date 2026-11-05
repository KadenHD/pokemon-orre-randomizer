"""Event reward conditions, one-time persistence and lossless native text banks.

The small CMS model covers emitted control flow, not native Dolphin execution.
ROM-dependent archive checks are optional; all semantic/format tests are local.
"""
from dataclasses import replace
from pathlib import Path
import struct
import unittest
import os

from orre_randomizer.engine import event_gifts as events
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.options import Options


def execute(code, entry, flags, *, gift_result=0, stop_at=None):
    """Model only the qualified opcodes emitted by the reward patch."""
    pc, stack = entry, []
    flags = dict(flags)
    gifts, messages, visibility = [], [], []
    locals_ = {0: 0x12345678, 1: 77, 2: 88}
    locked, depth = False, 0
    for _ in range(10000):
        if pc == stop_at:
            break
        op = code[pc]
        pc += 1
        if op == 5:
            break
        if op == 8:
            assert code[pc] == 2
            stack.append(struct.unpack_from(">i", code, pc + 1)[0])
            pc += 5
        elif op == 16:
            assert code[pc:pc + 3] == b"\x42\x00\x01"
            pc += 3
            stack.append(locals_[stack.pop()])
        elif op == 3:
            assert code[pc:pc + 3] == b"\x82\x00\x01"
            pc += 3
            stack.pop()
        elif op == 37:
            returns, count = struct.unpack_from(">HH", code, pc)
            pc += 4
            args = [stack.pop() for _ in range(count - 1)][::-1]
            function = stack.pop()
            assert stack.pop() == locals_[0]
            value = 0
            if function == 81:
                value = flags.get(args[0], 0)
            elif function == 80:
                flags[args[0]] = args[1]
            elif function == 217:
                gifts.append(args[0])
                value = gift_result
            elif function == 54:
                assert args[:2] == [77, 88]
                messages.append(args[2])
            elif function == 55:
                assert args == [77, 88]
            elif function == 50:
                visibility.append(args)
            elif function == 32:
                locked = True
            elif function == 33:
                locked = False
            else:
                raise AssertionError(f"unqualified standard function {function}")
            assert returns == 1
            stack.append(value)
        elif op in (23, 28, 33):
            assert code[pc:pc + 2] == b"\x82\x82"
            pc += 2
            second, first = stack.pop(), stack.pop()
            stack.append(first + second if op == 23 else
                         int(first >= second) if op == 28 else int(bool(first) and bool(second)))
        elif op == 17:
            assert code[pc] == 0x82
            pc += 1
            stack.append(int(not stack.pop()))
        elif op == 7:
            target = u32(code, pc)
            pc += 4
            if not stack.pop():
                pc = target
        elif op == 6:
            pc = u32(code, pc)
        elif op == 31:
            assert code[pc:pc + 2] == b"\x82\x42"
            pc += 2
            value, index = stack.pop(), stack.pop()
            locals_[index] = value
            stack.append(value)
        else:
            raise AssertionError(f"unqualified opcode {op:#x} at {pc - 1:#x}")
        depth = max(depth, len(stack))
    else:
        raise AssertionError("reward script did not terminate")
    assert not stack and not locked
    return {"flags": flags, "gifts": gifts, "messages": messages, "visibility": visibility, "depth": depth}


def story_flags():
    return dict.fromkeys(events.STORY_FLAGS, 1)


def flags_for_count(count):
    return {**story_flags(), **{1261 + sid: 1 for sid in events.SHADOW_IDS[:count]}}


def bank(language="FR"):
    # IDs1/3 share storage. Rich records have byte parameters, embedded zeros
    # and odd lengths: none may be normalized, decoded or truncated.
    count = 4
    header = struct.pack(">IH2sII", 0, count, language.encode("ascii"), 0x11223344, 0)
    first = "Native dialogue".encode("utf-16-be") + b"\0\0"
    rich = bytes.fromhex("ffff070000410000ffff020000")
    opaque = bytes.fromhex("ffff08000100020000420000ff")
    directory_end = 16 + count * 8
    offsets = (directory_end, directory_end + len(first), directory_end,
               directory_end + len(first) + len(rich))
    directory = b"".join(struct.pack(">II", index + 1, offset) for index, offset in enumerate(offsets))
    return header + directory + first + rich + opaque


class RewardScriptTests(unittest.TestCase):
    def test_native_result_and_receipt_conditions_across_every_purification_count(self):
        code = events._interaction(0, 10, 25)
        cases = 0
        for count in range(49):
            for pikachu_received in (0, 1):
                for celebi_received in (0, 1):
                    for result in (-2, -1, 0, 5):
                        flags = {**flags_for_count(count), 2740: pikachu_received, 2737: celebi_received}
                        observed = execute(code, 0, flags, gift_result=result)
                        expected = ([5] if not pikachu_received and count >= 10 else
                                    [6] if not celebi_received and count >= 25 else [])
                        with self.subTest(count=count, pikachu=pikachu_received, celebi=celebi_received, result=result):
                            self.assertEqual(observed["gifts"], expected)
                            for gift, flag in ((5, 2740), (6, 2737)):
                                self.assertEqual(observed["flags"][flag],
                                    int(bool(flags[flag]) or gift in expected and result >= -1))
                            self.assertLessEqual(observed["depth"], 8)
                        cases += 1
        self.assertEqual(cases, 784)
        self.assertEqual(execute(code, 0, {})["gifts"], [])

    def test_all_story_gates_are_required_and_thresholds_are_independent(self):
        code = events._interaction(0, 0, 1)
        for mask in range(64):
            flags = {flag: int(bool(mask & (1 << index))) for index, flag in enumerate(events.STORY_FLAGS)}
            result = execute(code, 0, flags)
            self.assertEqual(result["gifts"], [5] if mask == 63 else [])
        reversed_code = events._interaction(0, 48, 1)
        self.assertEqual(execute(reversed_code, 0, flags_for_count(1))["gifts"], [6])
        self.assertEqual(execute(reversed_code, 0, {**flags_for_count(48), 2737: 1})["gifts"], [5])

    def test_delivery_is_once_per_save_and_failure_can_be_retried(self):
        code = events._interaction(0, 0, 0)
        failed = execute(code, 0, story_flags(), gift_result=-2)
        first = execute(code, 0, failed["flags"], gift_result=-1)
        second = execute(code, 0, first["flags"])
        third = execute(code, 0, second["flags"])
        self.assertEqual([first["gifts"], second["gifts"], third["gifts"]], [[5], [6], []])
        self.assertIn(events.MESSAGE_IDS[2], failed["messages"])
        self.assertIn(events.MESSAGE_IDS[4], third["messages"])

    def test_disabled_feature_is_identity_and_enabled_unknown_archives_are_refused(self):
        source = b"unrelated untouched bytes"
        output, report = events.patch_event_archive(source, "any.fsys", Options.none())
        self.assertIs(output, source)
        self.assertFalse(report["enabled"])
        with self.assertRaises(FormatError):
            events.patch_event_archive(source, "unknown.fsys", Options.recommended())
        with self.assertRaises(FormatError):
            events.patch_event_archive(source, events.ARCHIVE_NAMES[0], Options.recommended())
        for value in (True, -1, 49, 1.0):
            with self.subTest(value=value), self.assertRaises(FormatError):
                events.patch_event_archive(source, events.ARCHIVE_NAMES[0],
                    replace(Options.recommended(), event_pikachu_purifications=value))


class NativeMessageTests(unittest.TestCase):
    def test_us_bank_keeps_native_tag_and_uses_english_messages(self):
        original = bank("US")
        output, report = events._patch_message_bank(original, "US", 10, 25)
        self.assertEqual(output[6:8], b"US")
        self.assertEqual(report["texts"], events._messages("UK", 10, 25))
        self.assertEqual(report["language"], "US")
        with self.assertRaises(FormatError):
            events._patch_message_bank(original, "UK", 10, 25)

    def test_japanese_bank_preserves_zero_tag_and_adds_real_japanese_utf16(self):
        original = bytearray(bank("JP"))
        original[6:8] = bytes(2)
        original = bytes(original)
        output, report = events._patch_message_bank(original, "JP", 0, 25)
        self.assertEqual(output[6:8], bytes(2))
        self.assertEqual(report["language"], "JP")
        self.assertIn("もうひとつ", events._messages("JP", 10, 0)[3])
        self.assertIn("２５ひき", report["texts"][3])
        self.assertNotIn("０ひき", report["texts"][3])
        self.assertTrue(all(" " not in text for text in report["texts"]))
        self.assertLessEqual(max(len(line) for text in events._messages("JP", 48, 48)
                                 for line in text.splitlines()), 19)
        self.assertIn("ポケモン".encode("utf-16-be"), output)
        count = u32(output, 4) >> 16
        added = [struct.unpack_from(">II", output, 16 + (count - 5 + index) * 8)
                 for index in range(5)]
        for (identifier, offset), text in zip(added, report["texts"]):
            self.assertIn(identifier, events.MESSAGE_IDS)
            encoded = events._encode_text(text)
            self.assertEqual(output[offset:offset + len(encoded)], encoded)
        growth = len(events.MESSAGE_IDS) * 8
        payload_start = 16 + 4 * 8
        self.assertEqual(output[payload_start + growth:len(original) + growth], original[payload_start:])
        with self.assertRaises(FormatError):
            events._patch_message_bank(bank("JP"), "JP", 10, 25)

    def test_every_original_allocation_alias_and_opaque_byte_survives(self):
        for language in events.MESSAGE_BANKS:
            original = bank(language)
            output, report = events._patch_message_bank(original, language, 0, 1)
            growth = len(events.MESSAGE_IDS) * 8
            count = struct.unpack_from(">H", original, 4)[0]
            payload_start = 16 + count * 8
            self.assertEqual(output[payload_start + growth:len(original) + growth], original[payload_start:])
            self.assertEqual(output[:4], original[:4])
            self.assertEqual(output[6:16], original[6:16])
            for index in range(count):
                identifier, offset = struct.unpack_from(">II", original, 16 + index * 8)
                self.assertEqual(struct.unpack_from(">II", output, 16 + index * 8), (identifier, offset + growth))
                self.assertEqual(output[offset + growth:len(original) + growth], original[offset:])
            self.assertEqual(u32(output, 20), u32(output, 36))
            self.assertTrue(report["opaque_allocations_and_aliases_preserved"])
            self.assertEqual(len(report["texts"]), 5)
            self.assertIn(b"\xff\xff\x00", output[len(original) + growth:])
            self.assertEqual((output, report), events._patch_message_bank(original, language, 0, 1))

    def test_zero_one_plural_and_reversed_thresholds_have_localized_independent_text(self):
        singular = {"FR": "1 purification.", "UK": "1 purification.", "GE": "1 Erlösung.",
                    "SP": "1 purificación.", "IT": "1 purificazione."}
        for language in events.MESSAGE_BANKS:
            self.assertIn(singular[language], events._messages(language, 0, 1)[3])
            self.assertNotIn("0 ", events._messages(language, 0, 1)[3])
            reversed_text = events._messages(language, 48, 1)[3]
            self.assertIn("48", reversed_text)
            self.assertIn("1", reversed_text)
        self.assertNotIn("puis", events._messages("FR", 25, 10)[3])

    def test_collision_duplicate_pointer_header_and_count_errors_are_refused(self):
        original = bank()
        corruptions = []
        for offset, value in ((16, events.MESSAGE_IDS[0]), (24, 1), (20, 0), (20, len(original)),
                              (20, 0xFFFFFFFF)):
            current = bytearray(original)
            struct.pack_into(">I", current, offset, value)
            corruptions.append(bytes(current))
        corruptions += [original[:10], b"BAD!" + original[4:], original[:6] + b"UK" + original[8:]]
        current = bytearray(original)
        struct.pack_into(">H", current, 4, 65535)
        corruptions.append(bytes(current))
        for current in corruptions:
            with self.subTest(sample=current[:30]), self.assertRaises(FormatError):
                events._patch_message_bank(current, "FR", 10, 25)

    def test_byte_whitelist_refuses_unrelated_mutations(self):
        original = bytes(range(16))
        output = bytearray(original)
        output[2] = 99
        events._only_changes(original, bytes(output) + b"new code", ((2, 3),))
        output[9] = 99
        with self.assertRaises(FormatError):
            events._only_changes(original, bytes(output), ((2, 3),))
        with self.assertRaises(FormatError):
            events._only_changes(original, original[:-1], ())


GAME = Path(__file__).resolve().parents[1] / "game/files"


@unittest.skipUnless(all((GAME / name).is_file() for name in events.ARCHIVE_NAMES), "requires original PAL game dump")
class PalArchiveTests(unittest.TestCase):
    def test_rebuilt_archives_preserve_every_untargeted_member_and_original_source(self):
        options = replace(Options.recommended(), event_pikachu_purifications=0, event_celebi_purifications=1)
        for name in events.ARCHIVE_NAMES:
            source = (GAME / name).read_bytes()
            output, report = events.patch_event_archive(source, name, options)
            self.assertTrue(report["untargeted_decoded_members_unchanged"])
            self.assertTrue(report["no_actor_added"])
            self.assertEqual(source, (GAME / name).read_bytes())
            after = parse_fsys(output)
            if name == events.ARCHIVE_NAMES[0]:
                cms = decoded_member(output, after["members"][1])
                self.assertEqual(u32(cms, 24 + 12 * 4), 10464)
                self.assertEqual(cms[u32(cms, 16):u32(cms, 16) + 8], bytes(8))
                for index, language in enumerate(events.MESSAGE_BANKS):
                    self.assertEqual(len(report["native_texts"][index]["texts"]), 5)
            with self.assertRaises(FormatError):
                events.patch_event_archive(output, name, options)

    def test_original_story_gates_select_one_location_and_keep_home_dialogue_before_unlock(self):
        shrine = (GAME / events.ARCHIVE_NAMES[0]).read_bytes()
        home = (GAME / events.ARCHIVE_NAMES[1]).read_bytes()
        original_shrine = decoded_member(shrine, parse_fsys(shrine)["members"][1])
        original_home = decoded_member(home, parse_fsys(home)["members"][1])
        shrine_cms, shrine_report = events._patch_shrine_cms(original_shrine, 10, 25)
        home_cms, home_report = events._patch_home_cms(original_home)
        for mask in range(64):
            flags = {flag: int(bool(mask & (1 << index))) for index, flag in enumerate(events.STORY_FLAGS)}
            complete = mask == 63
            shrine_state = execute(shrine_cms, shrine_report["visibility_offset"], flags, stop_at=0x279)
            self.assertEqual(shrine_state["visibility"], [[77, 1, int(complete)]])
            home_state = execute(home_cms, home_report["setup_detour"], flags)
            self.assertEqual(home_state["visibility"], [[77, 0, 0]] if complete else [])
            talk_state = execute(home_cms, home_report["talk_guard"], flags, stop_at=0x3561)
            self.assertEqual(talk_state["messages"], [])
        actor = decoded_member(shrine, parse_fsys(shrine)["members"][0])
        patched_actor, _ = events._patch_actor(actor)
        self.assertEqual([i for i, (a, b) in enumerate(zip(actor, patched_actor)) if a != b], [0x240, 0x243])


REGIONAL = Path(os.environ.get("COLOSSEUM_REGION_EVENT_FIXTURES", str(
    Path(__file__).resolve().parents[1] / "build/region-compat-2026-11-02/event-research/v2")))


@unittest.skipUnless(all((REGIONAL / region / name).is_file()
                        for region in ("usa", "japan") for name in events.ARCHIVE_NAMES),
                     "requires original USA/Japan event archives; no game data is distributed")
class RegionalArchiveTests(unittest.TestCase):
    def test_real_regional_archives_are_lossless_guarded_and_use_the_native_language(self):
        for region, game_id, language in (("usa", "GC6E01", "US"), ("japan", "GC6J01", "JP")):
            for name in events.ARCHIVE_NAMES:
                source = (REGIONAL / region / name).read_bytes()
                output, report = events.patch_event_archive(source, name, Options.recommended(), region=game_id)
                self.assertEqual(source, (REGIONAL / region / name).read_bytes())
                self.assertTrue(report["untargeted_decoded_members_unchanged"])
                self.assertTrue(report["original_story_scenes_preserved"])
                before, after = parse_fsys(source)["members"], parse_fsys(output)["members"]
                for old, new in zip(before, after):
                    if old["index"] not in ({0, 1, 2} if name == events.ARCHIVE_NAMES[0] else {1}):
                        self.assertEqual(decoded_member(source, old), decoded_member(output, new))
                if name == events.ARCHIVE_NAMES[0]:
                    self.assertEqual([r["language"] for r in report["native_texts"]], [language])
                    actor_before = decoded_member(source, before[0])
                    actor_after = decoded_member(output, after[0])
                    self.assertEqual([i for i, (a, b) in enumerate(zip(actor_before, actor_after)) if a != b],
                                     [0x240, 0x243])
                with self.assertRaises(FormatError):
                    events.patch_event_archive(source, name, Options.recommended(), region="GC6P01")
                with self.assertRaises(FormatError):
                    events.patch_event_archive(output, name, Options.recommended())

    def test_original_regional_scripts_enforce_all_64_story_combinations(self):
        for region, game_id in (("usa", "GC6E01"), ("japan", "GC6J01")):
            source = (REGIONAL / region / events.ARCHIVE_NAMES[1]).read_bytes()
            original = decoded_member(source, parse_fsys(source)["members"][1])
            cms, report = events._patch_home_cms(original, events._REGIONAL_LAYOUTS[game_id]["home_cms"])
            for mask in range(64):
                flags = {flag: int(bool(mask & (1 << index))) for index, flag in enumerate(events.STORY_FLAGS)}
                state = execute(cms, report["setup_detour"], flags)
                self.assertEqual(state["visibility"], [[77, 0, 0]] if mask == 63 else [])
            # Original regional constants, including Japanese camera values,
            # are kept byte-for-byte outside the two declared patch ranges.
            self.assertEqual(original[0x258:0x260], cms[0x258:0x260])
            self.assertEqual(original[0x462:0x46A], cms[0x462:0x46A])


if __name__ == "__main__":
    unittest.main()
