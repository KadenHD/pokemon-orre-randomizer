"""Exact retail retry qualification and bounded VM traces, without Dolphin."""
from pathlib import Path
import unittest

from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.message_bank import message_directory, patch_messages
from orre_randomizer.engine.rebuild_iso import decoded_member, repack_fsys
from orre_randomizer import xd_starter_progression as rule

ROOT = Path(__file__).resolve().parents[1]


class Blackout(Exception):
    """Observed native loss exits the caller before its post-battle scene."""


def first_encounter_trace(script, *, previous_attempt, outcome="win", stage=30):
    """Interpret the actual retail first-encounter control flow, not native C.

    Character/map calls are deterministic stubs for entering Chobin's trigger.
    The blackout exit is a runtime-observed premise, not inferred from a bool.
    Script calls remain opaque events; native scene bytes are checked separately.
    """
    code = 0x290
    cursor = 0x2A34
    stack, events, flags, variables = [], [], {964: stage, 969: previous_attempt}, {}
    last = None
    for _ in range(3000):
        word = u32(script, cursor)
        op, sub, parameter = word >> 24, (word >> 16) & 255, word & 65535
        following = cursor + 4
        if op == 2:
            if sub in (3, 4):
                stack.append(("constant", sub, parameter))
            else:
                stack.append(u32(script, following))
                following += 4
        elif op in (3, 17):
            level = sub & 15
            if level == 2:
                stack.append(last)
            elif level == 3:
                stack.append(("object", parameter))
            else:
                stack.append(variables.get((level, parameter), 0))
        elif op == 4:
            variables[(sub & 15, parameter)] = stack.pop()
        elif op == 1:
            right, left = stack.pop(), stack.pop()
            operations = {48: lambda: left == right, 49: lambda: left > right,
                          50: lambda: left >= right, 51: lambda: left < right,
                          52: lambda: left <= right, 53: lambda: left != right,
                          33: lambda: left | right, 34: lambda: left & right}
            if sub not in operations:
                raise AssertionError(f"Unsupported first-encounter operator {sub}")
            stack.append(operations[sub]())
        elif op == 9:
            cleanup = u32(script, following)
            if cleanup >> 24 != 6:
                raise AssertionError("Native call lacks explicit stack cleanup")
            count = (cleanup >> 16) & 255
            args = list(reversed(stack[-count:])) if count else []
            if sub == 0 and parameter in (132, 133):
                last = flags.get(args[0], 0)
            elif sub == 0 and parameter == 131:
                flags[args[0]] = args[1]
                events.append(("setFlag", *args))
            elif sub == 42 and parameter == 16:
                events.append(("battle", args[1]))
                if outcome == "loss":
                    raise Blackout((events, flags))
                last = None
            elif sub == 38 and parameter == 16:
                last = 173
            else:
                # Native geometry places the player inside the encounter area.
                last = 1
        elif op == 6:
            if sub:
                del stack[-sub:]
        elif op == 7:
            events.append(("scene", word & 0xFFFFFF))
            last = None
        elif op in (10, 11):
            value = bool(stack.pop())
            if value == (op == 10):
                following = code + 4 * (word & 0xFFFFFF)
        elif op == 12:
            following = code + 4 * (word & 0xFFFFFF)
        elif op == 8:
            if stack:
                raise AssertionError(f"Native stack imbalance after retry: {stack}")
            return events, flags
        elif op not in (0, 13, 14, 16):
            raise AssertionError(f"Unsupported first-encounter opcode {op}")
        cursor = following
    raise AssertionError("Unbounded first-encounter script trace")


class BoundedRetryContract(unittest.TestCase):
    def test_localized_reply_keeps_native_controls_and_removes_outcome_assumptions(self):
        self.assertEqual(set(rule._DIALOGUE), {"UK", "US", "FR", "GE", "SP", "IT", "JP"})
        for language, (before, after) in rule._DIALOGUE.items():
            with self.subTest(language=language):
                self.assertNotEqual(before, after)
                self.assertTrue(rule._dialogue_controls_preserved(before, after, language))
                self.assertEqual(after.count(bytes.fromhex("ffff00")), 2 if language == "JP" else 1)
                self.assertTrue(after.startswith(bytes.fromhex("ffff59")))
                self.assertTrue(after.endswith(bytes.fromhex("ffff030000")))
                for damaged in (after.replace(bytes.fromhex("ffff59"), b""),
                                after.replace(bytes.fromhex("ffff03"), bytes.fromhex("ffff02")),
                                after.replace(bytes.fromhex("ffff00"), b"")):
                    self.assertFalse(rule._dialogue_controls_preserved(before, damaged, language))
        for language, words in (("UK", "CHOBIN lost"), ("US", "CHOBIN lost"),
                                ("FR", "DARIUS a perdu"), ("GE", "besiegt hast"),
                                ("SP", "hayas ganado"), ("IT", "UGO ha perso")):
            with self.subTest(language=language):
                self.assertIn(words.encode("utf-16-be"), rule._DIALOGUE[language][0])
                self.assertNotIn(words.encode("utf-16-be"), rule._DIALOGUE[language][1])

    def test_single_call_is_neutralized_with_identical_native_pop_and_continuation(self):
        output = rule._retry_window(rule.RETRY_WINDOW)
        relative = rule.RETRY_CALL - rule.WINDOW_START
        self.assertEqual(output[:relative], rule.RETRY_WINDOW[:relative])
        self.assertEqual(output[relative:relative + 4], bytes(4))
        self.assertEqual(output[relative + 4:], rule.RETRY_WINDOW[relative + 4:])
        self.assertEqual(output[relative + 4:relative + 8], bytes.fromhex("06040000"))
        self.assertEqual(rule._retry_window(output, patched=True), output)

    def test_unknown_window_bytes_including_stack_cleanup_are_all_rejected(self):
        for offset in range(len(rule.RETRY_WINDOW)):
            changed = bytearray(rule.RETRY_WINDOW)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(FormatError):
                rule._retry_window(bytes(changed))

    def test_unknown_original_or_region_cannot_bypass_whole_archive_identity(self):
        for game in ("GC6P01", "GXXP01", "GXXE01", "GXXJ01", "GXXA01"):
            with self.subTest(game=game), self.assertRaises(FormatError):
                rule.patch_starter_progression(b"not a retail archive", game)


class NativeFirstChobinProgression(unittest.TestCase):
    def archives(self):
        files = [(game, ROOT / "build/v212-validation/starter-progression-native" / game / "S3_out.fsys")
                 for game in ("GXXP01", "GXXE01", "GXXJ01")]
        if not all(path.is_file() for _, path in files):
            self.skipTest("requires the three locally retained, qualified retail S3_out archives")
        return [(game, path.read_bytes()) for game, path in files]

    def test_patch_and_final_validation_cover_all_three_original_regions(self):
        for game, original in self.archives():
            with self.subTest(game=game):
                updated, report = rule.patch_starter_progression(original, game)
                self.assertTrue(report["other_archive_payloads_identical"])
                self.assertTrue(rule.validate_starter_progression(original, updated, game)["validated"])
                _, before = rule._script(original)
                _, after = rule._script(updated)
                self.assertEqual(before[:rule.RETRY_CALL], after[:rule.RETRY_CALL])
                self.assertEqual(before[rule.RETRY_CALL + 4:], after[rule.RETRY_CALL + 4:])
                self.assertEqual(after[rule.FIRST_CALL:rule.FIRST_CALL + 4], rule.CALL)
                self.assertEqual(len(before), len(after))
                # Later ordinary/Mecha encounters are outside this patch. Their
                # complete native script bytes above, including these calls,
                # must survive; the bounded VM does not model Mecha geometry.
                for offset in (0x356C, 0x3958, 0x3C50, 0x7020):
                    self.assertEqual(before[offset:offset + 4], rule.CALL)
                    self.assertEqual(after[offset:offset + 4], rule.CALL)

    def test_first_victory_control_flow_is_identical_and_loss_retry_plays_native_scene(self):
        for game, original in self.archives():
            updated, _ = rule.patch_starter_progression(original, game)
            _, before = rule._script(original)
            _, after = rule._script(updated)
            with self.subTest(game=game, path="first victory"):
                native = first_encounter_trace(before, previous_attempt=0)
                final = first_encounter_trace(after, previous_attempt=0)
                self.assertEqual(native, final)
                self.assertIn(("battle", 222), final[0])
                self.assertIn(("scene", 0x1274), final[0])
                self.assertEqual(final[1][964], 40)
            with self.subTest(game=game, path="first loss"):
                for script in (before, after):
                    with self.assertRaises(Blackout) as caught:
                        first_encounter_trace(script, previous_attempt=0, outcome="loss")
                    events, flags = caught.exception.args[0]
                    self.assertEqual(flags[969], 1)
                    self.assertEqual(flags[964], 30)
                    self.assertNotIn(("scene", 0x1274), events)
            with self.subTest(game=game, path="retry after native loss"):
                with self.assertRaises(Blackout):
                    first_encounter_trace(before, previous_attempt=1, outcome="loss")
                final = first_encounter_trace(after, previous_attempt=1, outcome="loss")
                self.assertNotIn(("battle", 222), final[0])
                self.assertEqual(final[0].count(("scene", 0x1274)), 1)
                self.assertEqual(final[1][964], 40)
            for stage in (40, 50, 191, 670, 680, 870):
                with self.subTest(game=game, stage=stage):
                    self.assertEqual(first_encounter_trace(before, previous_attempt=1, stage=stage),
                                     first_encounter_trace(after, previous_attempt=1, stage=stage))

    def test_current_archive_message_edits_survive_the_patch_and_final_validator(self):
        for game, original in self.archives():
            message = next(member for member in parse_fsys(original)["members"]
                           if int(member["identifier_raw"], 16) & 0xFF00 == 0x0A00)
            bank = decoded_member(original, message)
            identifier = next(value for value in message_directory(bank) if value != rule.MESSAGE_ID)
            changed_bank = patch_messages(bank, {identifier: lambda _before: "QA text".encode("utf-16-be") + bytes(2)})
            current, _ = repack_fsys(original, {message["index"]: changed_bank})
            with self.subTest(game=game):
                updated, report = rule.patch_starter_progression(original, game, current_archive=current)
                self.assertEqual(report["archive_payload_preservation_basis"], "current_archive")
                final_message = next(member for member in parse_fsys(updated)["members"]
                                     if member["index"] == message["index"])
                final_bank = decoded_member(updated, final_message)
                pointer = message_directory(final_bank)[identifier][1]
                self.assertTrue(final_bank[pointer:].startswith("QA text".encode("utf-16-be") + bytes(2)))
                self.assertTrue(rule.validate_starter_progression(original, updated, game)["validated"])

    def test_only_the_reviewed_message_changes_and_final_validation_requires_its_translation(self):
        from orre_randomizer.engine.message_bank import _CONTROL_ARGUMENTS

        def record(bank, pointer):
            cursor = pointer
            while cursor + 1 < len(bank):
                if bank[cursor:cursor + 2] == bytes(2):
                    return bank[pointer:cursor + 2]
                if bank[cursor:cursor + 2] == b"\xff\xff":
                    cursor += 3 + _CONTROL_ARGUMENTS.get(bank[cursor + 2], 0)
                else:
                    cursor += 2
            raise AssertionError("Unterminated native message")

        for game, original in self.archives():
            updated, report = rule.patch_starter_progression(original, game)
            self.assertTrue(report["shared_reply_neutralized"])
            original_banks = rule._dialogue_banks(original, game)
            final_banks = rule._dialogue_banks(updated, game)
            for language, (_, bank) in original_banks.items():
                member, final_bank = final_banks[language]
                before_directory, after_directory = message_directory(bank), message_directory(final_bank)
                with self.subTest(game=game, language=language):
                    self.assertEqual(before_directory.keys(), after_directory.keys())
                    for identifier, (_, pointer) in before_directory.items():
                        after = record(final_bank, after_directory[identifier][1])
                        self.assertEqual(after, rule._DIALOGUE[language][1] if identifier == rule.MESSAGE_ID else record(bank, pointer))
                    corrupted = bytearray(final_bank)
                    corrupted[after_directory[rule.MESSAGE_ID][1] + 5] ^= 1
                    wrong, _ = repack_fsys(updated, {member["index"]: bytes(corrupted)})
                    with self.assertRaises(FormatError):
                        rule.validate_starter_progression(original, wrong, game)

    def test_existing_script_edits_or_final_payload_corruption_are_rejected(self):
        for game, original in self.archives():
            member, script = rule._script(original)
            updated, _ = rule.patch_starter_progression(original, game)
            with self.subTest(game=game, error="already patched"):
                with self.assertRaises(FormatError):
                    rule.patch_starter_progression(original, game, current_archive=updated)
            for offset in (rule.FIRST_CALL, 0x4C60, 0x4C30, rule.RETRY_CALL + 4):
                modified = bytearray(script)
                modified[offset] ^= 1
                corrupted, _ = repack_fsys(original, {member["index"]: bytes(modified)})
                with self.subTest(game=game, offset=offset):
                    with self.assertRaises(FormatError):
                        rule.patch_starter_progression(original, game, current_archive=corrupted)
                    with self.assertRaises(FormatError):
                        rule.validate_starter_progression(original, corrupted, game)


if __name__ == "__main__":
    unittest.main()
