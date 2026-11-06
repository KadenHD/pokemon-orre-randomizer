import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.plusle_dialogue import _patch_bank, patch_dialogue


_GUILD = "M2_guild_1F_1.fsys"


def _french_guild_bank() -> tuple[bytes, dict[int, tuple[int, bytes]]]:
    lines = {
        0x5A8A: "Si POSIPI avait été blessé…",
        0x5A8B: "Qu'est-ce qu'il y a, POSIPI ?",
        0x5B04: "Peux-tu prendre POSIPI ?\uffffPOSIPI veut t'aider.",
        0x5B18: "POSIPI a été envoyé au PC.",
        0x5B1D: "Et POSIPI !",
        0x5B1E: "Prends soin de POSIPI !",
        0x5B1F: "Une autre ligne.",
        0x5AF5: "‱: Posi posiii piiii!",
        0x5AF6: "‱: Popiiii!",
    }
    header = bytearray(16 + 8 * len(lines))
    struct.pack_into(">H2s", header, 4, len(lines), b"FR")
    data = bytearray(header)
    original = {}
    for position, (identifier, text) in enumerate(lines.items(), start=2):
        suffix = b"\xff\xff\x02\0\0" if text.startswith("‱") else b"\0\0"
        entry = text.encode("utf-16-be").replace(b"\xff\xff", b"\xff\xff\x03") + suffix
        struct.pack_into(">II", data, position * 8, identifier, len(data))
        original[identifier] = (len(data), entry)
        data.extend(entry)
    return bytes(data), original


class PlusleDialogueTests(unittest.TestCase):
    def test_retargets_only_expected_messages_and_preserves_controls(self):
        bank, original = _french_guild_bank()
        output = _patch_bank(bank, _GUILD, "fr", "ÉVOLI")
        self.assertEqual(output[16 + 8 * len(original):len(bank)], bank[16 + 8 * len(original):])
        for index, (identifier, (old_pointer, message)) in enumerate(original.items(), start=2):
            actual_id, pointer = struct.unpack_from(">II", output, index * 8)
            self.assertEqual(actual_id, identifier)
            if identifier == 0x5B1F:
                self.assertEqual(pointer, old_pointer)
            else:
                self.assertGreaterEqual(pointer, len(bank))
                if identifier == 0x5B1E:
                    self.assertTrue(output[pointer:].startswith("Prends soin d'ÉVOLI !".encode("utf-16-be")))
                elif identifier in (0x5AF5, 0x5AF6):
                    expected = "‱: ÉVOLI!".encode("utf-16-be") + b"\xff\xff\x02\0\0"
                    self.assertEqual(output[pointer:pointer + len(expected)], expected)
                else:
                    replacement = message.replace("POSIPI".encode("utf-16-be"), "ÉVOLI".encode("utf-16-be"))
                    self.assertEqual(output[pointer:pointer + len(replacement)], replacement)

    def test_rejects_wrong_original_and_keeps_native_plusle_exact(self):
        bank, _ = _french_guild_bank()
        corrupt = bank.replace("POSIPI".encode("utf-16-be"), "AUTRES".encode("utf-16-be"), 1)
        with self.assertRaises(FormatError):
            _patch_bank(corrupt, _GUILD, "fr", "MALOSSE")
        self.assertIs(patch_dialogue(bank, _GUILD, "GC6P01", 311), bank)


if __name__ == "__main__":
    unittest.main()
