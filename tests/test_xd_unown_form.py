import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.xd_unown_form import _FORM_RESOLVER, _RETAIL_RESOLVER, patch_xd_unown_form


class XDUnownFormTests(unittest.TestCase):
    def test_seeded_result_only_replaces_the_resolver_entry(self):
        for game_id, offset in _FORM_RESOLVER.items():
            with self.subTest(game_id=game_id):
                original = bytes(offset) + _RETAIL_RESOLVER
                current = b"prior edit" + original[10:] + b"existing appended code"
                for form in range(28):
                    result = patch_xd_unown_form(original, current, game_id, form)
                    self.assertEqual(result[:offset], current[:offset])
                    self.assertEqual(result[offset + 8:], current[offset + 8:])
                    self.assertEqual(struct.unpack_from(">II", result, offset),
                                     (0x38600000 | form, 0x4E800020))

    def test_refuses_unexpected_or_truncated_resolver(self):
        game_id = "GXXE01"
        offset = _FORM_RESOLVER[game_id]
        original = bytes(offset) + _RETAIL_RESOLVER
        changed = original[:-1]
        for source, current in ((original, changed), (changed, original)):
            with self.assertRaisesRegex(FormatError, "unexpected XD Unown form resolver"):
                patch_xd_unown_form(source, current, game_id, 27)


if __name__ == "__main__":
    unittest.main()
