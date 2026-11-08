import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.colo_unown import (
    _FORM_RESOLVER_OFFSETS, _NATIVE_RESOLVER, patch_unown_form,
)
from orre_randomizer.engine.dol_regions import LAYOUTS


class ColosseumUnownTests(unittest.TestCase):
    def test_all_forms_replace_only_the_guarded_return(self):
        for layout in LAYOUTS:
            offset = _FORM_RESOLVER_OFFSETS[layout.game_id]
            original = bytes(offset) + _NATIVE_RESOLVER + b"native data"
            current = original + b"other patches"
            with patch("orre_randomizer.engine.colo_unown.dol_layout", return_value=layout):
                for form in range(28):
                    with self.subTest(game=layout.game_id, form=form):
                        result = patch_unown_form(original, current, form)
                        self.assertEqual(struct.unpack_from(">II", result, offset),
                                         (0x38600000 | form, 0x4E800020))
                        self.assertEqual(result[:offset], current[:offset])
                        self.assertEqual(result[offset + 8:], current[offset + 8:])

                changed = current[:offset + 12] + b"\0" + current[offset + 13:]
                with self.assertRaises(FormatError):
                    patch_unown_form(original, changed, 0)

    def test_invalid_form_is_rejected(self):
        for form in (-1, 28, True, 0.5):
            with self.subTest(form=form), self.assertRaises(ValueError):
                patch_unown_form(b"", b"", form)
