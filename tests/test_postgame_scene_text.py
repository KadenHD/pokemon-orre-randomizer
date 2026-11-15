"""Native name controls and localization boundaries for the Lugia scene."""
import unittest
import re

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine import postgame_scene_text as scene


def caption_lines(payload):
    """Decode only this scene's text/name/newline controls independently."""
    lines, current, position = [], "", 0
    while position < len(payload):
        if payload[position:position + 2] == b"\xff\xff":
            control = payload[position + 2]
            position += 3
            if control == 0:
                lines.append(current)
                current = ""
            elif control == 0x2B:
                current += "{hero}"
            elif control == 0x2C:
                current += "{partner}"
            elif control == 2:
                if payload[position:] != b"\0\0":
                    raise AssertionError("invalid scene message terminator")
                break
            else:
                raise AssertionError(f"unexpected scene control{control:#x}")
        else:
            current += payload[position:position + 2].decode("utf-16-be")
            position += 2
    lines.append(current)
    return lines


class PostgameSceneTextTests(unittest.TestCase):
    def setUp(self):
        self.names = {scene.BOSS_NAME_ID: "JAKYLLA", scene.EAGUN_NAME_ID: "ADELBERT"}

    def test_all_native_languages_cover_the_entire_scene(self):
        expected = set(scene.MESSAGE_IDS.values())
        self.assertEqual(len(expected), len(scene.ORDERED_KEYS))
        self.assertEqual(min(expected), 0xF0050)
        self.assertEqual(set(scene.SPEAKERS), set(scene.ORDERED_KEYS))
        self.assertEqual(scene.CAPTURE_KEYS, scene.CAPTURE_BEFORE_EXIT_KEYS + scene.CAPTURE_AFTER_EXIT_KEYS)
        for language in ("UK", "US", "FR", "GE", "SP", "IT", "JP"):
            with self.subTest(language=language):
                payloads = scene.dialogue_payloads(language, self.names)
                self.assertEqual(set(payloads), expected)
                self.assertTrue(all(payload.endswith(scene.MESSAGE_END) for payload in payloads.values()))
        self.assertEqual(scene.dialogue_payloads("UK", self.names), scene.dialogue_payloads("US", self.names))

    def test_partner_and_hero_names_are_save_resolved_controls(self):
        for language in scene.TEXTS:
            with self.subTest(language=language):
                payloads = scene.dialogue_payloads(language, self.names)
                partner = payloads[scene.MESSAGE_IDS["arrival_snag"]]
                self.assertTrue(partner.startswith(b"\xff\xff\x2c"))
                self.assertIn(b"\xff\xff\x2b", partner)
                for key, speaker in scene.SPEAKERS.items():
                    if speaker == "partner":
                        self.assertTrue(payloads[scene.MESSAGE_IDS[key]].startswith(scene.NAME_CONTROLS["partner"]))
                for default_name in ("WES", "RUI", "EMILIE", "ÉMILIE", "レオ", "リュイ"):
                    self.assertTrue(all(default_name.encode("utf-16-be") not in payload for payload in payloads.values()))

    def test_named_speakers_and_native_punctuation(self):
        for language, separator, ending in (("UK", ": ", ""), ("FR", " : ", ""), ("JP", "「", "」")):
            with self.subTest(language=language):
                payloads = scene.dialogue_payloads(language, self.names)
                boss = payloads[scene.MESSAGE_IDS["arrival_return"]]
                eagun = payloads[scene.MESSAGE_IDS["arrival_warning"]]
                self.assertTrue(boss.startswith(("JAKYLLA" + separator).encode("utf-16-be")))
                self.assertTrue(eagun.startswith(("ADELBERT" + separator).encode("utf-16-be")))
                self.assertTrue(boss.endswith(ending.encode("utf-16-be") + scene.MESSAGE_END))

    def test_short_bubbles_have_no_manual_layout_or_placeholder_names(self):
        for language, bodies in scene.TEXTS.items():
            self.assertEqual(len(bodies), len(scene.ORDERED_KEYS))
            for key, body in zip(scene.ORDERED_KEYS, bodies, strict=True):
                with self.subTest(language=language, key=key):
                    self.assertLessEqual(len(body.replace("{hero}", "ABCDEFGHIJ")), 65 if language != "JP" else 36)
                    self.assertFalse(any(char in body for char in ("\n", "\r", "\0", "\uffff", "\u2013", "\u2014")))
                    payload = scene.dialogue_payloads(language, self.names)[scene.MESSAGE_IDS[key]]
                    lines = caption_lines(payload)
                    self.assertLessEqual(len(lines), 3)
                    for line in lines:
                        self.assertTrue(line and line == line.strip())
                        self.assertLessEqual(scene.text_advance(line), 420)
                    speaker = scene.SPEAKERS[key]
                    prefix = "{" + speaker + "}" if speaker in scene.NAME_CONTROLS else self.names[
                        scene.BOSS_NAME_ID if speaker == "boss" else scene.EAGUN_NAME_ID]
                    separator = "「" if language == "JP" else " : " if language == "FR" else ": "
                    suffix = "」" if language == "JP" else ""
                    original = prefix + separator + body + suffix
                    self.assertEqual(re.sub(r"\s+", "", "".join(lines)), re.sub(r"\s+", "", original))
                    if language != "JP":
                        self.assertEqual(" ".join(lines).split(), original.split())
                    self.assertNotIn("{hero}".encode("utf-16-be"), payload)
        self.assertEqual(scene.SPEAKERS[scene.CAPTURE_BEFORE_EXIT_KEYS[-1]], "boss")
        self.assertEqual(scene.SPEAKERS[scene.CAPTURE_AFTER_EXIT_KEYS[0]], "partner")

    def test_encoder_uses_native_accent_advances_and_atomic_saved_name_reservation(self):
        self.assertEqual(len(scene.FONT0_ADVANCES), 408)
        self.assertEqual(scene.text_advance("é"), 12)
        self.assertEqual(scene.text_advance("i"), 6)
        self.assertEqual(scene.text_advance("m"), 17)
        self.assertEqual(scene.text_advance(" "), 11)
        self.assertEqual(scene.text_advance("漢"), 24)
        self.assertEqual(scene.text_advance("{hero}"), 220)
        self.assertEqual(scene.text_advance("{partner}"), 220)
        payload = scene.dialogue_payloads("FR", self.names)[scene.MESSAGE_IDS["arrival_snag"]]
        self.assertIn(scene.LINE_BREAK, payload)
        self.assertEqual(payload.count(scene.NAME_CONTROLS["hero"]), 1)
        self.assertEqual(payload.count(scene.NAME_CONTROLS["partner"]), 1)
        self.assertLessEqual(len(caption_lines(payload)), 3)
        self.assertEqual(scene.ARRIVAL_KEYS[scene.ARRIVAL_KEYS.index("arrival_return") + 1], "arrival_escape")
        self.assertEqual(scene.SPEAKERS["arrival_escape"], "boss")
        for invalid in ("A\nB", "A\rB", "A\uffffB", "A\u2013B"):
            with self.assertRaises(FormatError):
                scene.NewSceneCaptionWriter("FR").encode(invalid)

    def test_unknown_language_and_missing_names_fail_before_patching(self):
        with self.assertRaises(FormatError):
            scene.dialogue_payloads("NL", self.names)
        with self.assertRaises(FormatError):
            scene.dialogue_payloads("UK", {})
        with self.assertRaises(FormatError):
            scene.dialogue_payloads("FR", {**self.names, scene.BOSS_NAME_ID: "A\nB"})


if __name__ == "__main__":
    unittest.main()
