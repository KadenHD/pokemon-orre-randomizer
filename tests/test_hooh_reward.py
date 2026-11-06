"""Keep the Mt. Battle gift presentation coherent with its native constructor."""

from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.dol_regions import PAL
from orre_randomizer.engine.hooh_reward import (
    _BANKS, _END, _MESSAGE_IDS, _NEXT_MESSAGE, _PREFIX, _SCENE, _SUCCESS, _patch_bank,
    patch_hooh_reward_scene,
)
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.randomize_trainers import original_common


def _synthetic_bank(*, alias=False):
    identifiers = (*_MESSAGE_IDS, _NEXT_MESSAGE)
    if alias:
        identifiers += (0x4500,)
    header = bytearray(16 + len(identifiers) * 8)
    struct.pack_into(">H", header, 4, len(identifiers))
    payload = bytearray()
    for index, identifier in enumerate(identifiers):
        offset = len(header) + len(payload)
        if identifier == 0x4500:
            offset = len(header)
        struct.pack_into(">II", header, 16 + 8 * index, identifier, offset)
        if index < 4:
            body = "HO-OH " + "original line " * 12
            payload.extend(_PREFIX + body.encode("utf-16-be") + (_END if index < 2 else _SUCCESS))
    return bytes(header + payload + b"unrelated message\x00\x00")


def _messages(data, base):
    rows = dict(struct.iter_unpack(">II", data[base + 16:base + 16 + 8 * u16(data, base + 4)]))
    offsets = [base + rows[identifier] for identifier in (*_MESSAGE_IDS, _NEXT_MESSAGE)]
    return [data[start:end] for start, end in zip(offsets, offsets[1:])], offsets[-1]


class HoOhRewardDialogueTests(unittest.TestCase):
    def test_four_messages_fit_in_place_and_keep_native_fanfare(self):
        original = _synthetic_bank()
        patched = bytearray(original)
        _patch_bank(original, patched, 0, "UK", "MISDREAVUS")
        messages, end = _messages(patched, 0)
        self.assertEqual(len(patched), len(original))
        self.assertEqual(patched[end:], original[end:])
        for message in messages:
            self.assertIn("MISDREAVUS".encode("utf-16-be"), message)
            self.assertNotIn("HO-OH".encode("utf-16-be"), message)
        self.assertTrue(messages[2].endswith(_SUCCESS))
        self.assertTrue(messages[3].rstrip(b"\x00").endswith(_SUCCESS.rstrip(b"\x00")))

    def test_rejects_storage_shared_with_unrelated_messages(self):
        original = _synthetic_bank(alias=True)
        patched = bytearray(original)
        with self.assertRaisesRegex(FormatError, "shares Ho-Oh dialogue"):
            _patch_bank(original, patched, 0, "UK", "PIKACHU")
        self.assertEqual(patched, original)


@unittest.skipUnless(Path("game/sys/main.dol").is_file() and Path("game/files/common.fsys").is_file(),
                     "requires the local original PAL Colosseum files")
class HoOhRewardDiscTests(unittest.TestCase):
    def test_model_cry_and_native_dialogue_use_the_final_gift(self):
        original = Path("game/sys/main.dol").read_bytes()
        rel = original_common(Path("game"))[2]
        self.assertEqual(patch_hooh_reward_scene(original, original, rel, rel),
                         (original, rel, {"applied": False}))
        gift = bytearray(original)
        struct.pack_into(">H", gift, PAL.special_offsets[3] + 2, 25)
        dol, patched_rel, report = patch_hooh_reward_scene(original, bytes(gift), rel, rel)
        self.assertEqual(len(dol), len(original))
        self.assertEqual(len(patched_rel), len(rel))
        self.assertEqual(report, {"applied": True, "species": 25, "languages": ["UK", "GE", "FR", "IT", "SP"]})
        model, cry = _SCENE[PAL.game_id]
        self.assertEqual(u32(dol, model), 0x38800019)
        self.assertEqual(u32(dol, cry), 0x38600019)
        for _, dol_base, rel_base in _BANKS[PAL.game_id]:
            dol_messages, _ = _messages(dol, dol_base)
            rel_messages, _ = _messages(patched_rel, rel_base)
            self.assertEqual(dol_messages, rel_messages)
            self.assertTrue(all("PIKACHU".encode("utf-16-be") in message for message in dol_messages))
