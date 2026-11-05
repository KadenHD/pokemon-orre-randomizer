"""Native stone-name spacing, opaque text preservation and bounded storage."""
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine import item_text


def bank_fixture(*, donor_text="Duplicate native description", alias_donor=False, alias_stone=False):
    base = 32
    records = [(1, "SUNSTONE".encode("utf-16-be") + b"\0\0"),
               (2, donor_text.encode("utf-16-be") + b"\0\0"),
               (3, "Duplicate native description".encode("utf-16-be") + b"\0\0"),
               # A native-style opaque control record with a byte parameter.
               (4, bytes.fromhex("ffff030000410000ff")),
               (5, "Untouched".encode("utf-16-be") + b"\0\0")]
    if alias_donor or alias_stone:
        records.append((6, b""))
    data = bytearray(b"\xa5" * base)
    data += struct.pack(">I H 2s II", 1, len(records), b"FR", 0, 0)
    directory = len(data)
    data += bytes(8 * len(records))
    starts = {}
    for index, (identifier, payload) in enumerate(records):
        if identifier == 6:
            start = starts[2 if alias_donor else 1]
        else:
            start = len(data)
            starts[identifier] = start
            data += payload
        struct.pack_into(">II", data, directory + index * 8, identifier, start - base)
    # The rich record makes the final address odd; bank extents may be padded.
    if len(data) % 2:
        data += b"\x00"
    end = len(data)
    data += b"\x5a" * 24
    return bytes(data), base, end, starts


def patch_fixture(data, base, end, *, replacement="SUN STONE"):
    return item_text._patch_bank(data, data, base, end, "FR",
                                 {1: ("SUNSTONE", replacement)}, ((2, 3),))


class NameBankTests(unittest.TestCase):
    def test_only_selected_name_changes_and_opaque_allocations_survive(self):
        original, base, end, starts = bank_fixture()
        output, report = patch_fixture(original, base, end)
        self.assertEqual(len(output), len(original))
        self.assertEqual(output[:base], original[:base])
        self.assertEqual(output[end:], original[end:])
        before = item_text._directory(original, base, end, "FR")
        for identifier, row in before.items():
            start = base + u32(output, row["pointer_offset"])
            expected = ("SUN STONE".encode("utf-16-be") + b"\0\0" if identifier == 1
                        else original[row["start"]:row["end"]])
            self.assertEqual(output[start:start + len(expected)], expected)
        self.assertEqual(output[starts[1]:starts[1] + 18], original[starts[1]:starts[1] + 18])
        self.assertTrue(report["all_other_ids_resolve_to_identical_bytes"])
        self.assertEqual((output, report), patch_fixture(original, base, end))

    def test_target_alias_survives_but_a_donor_alias_is_refused(self):
        original, base, end, _ = bank_fixture(alias_stone=True)
        output, _ = patch_fixture(original, base, end)
        rows = item_text._directory(original, base, end, "FR")
        self.assertNotEqual(u32(output, rows[1]["pointer_offset"]), u32(output, rows[6]["pointer_offset"]))
        self.assertEqual(u32(output, rows[6]["pointer_offset"]), u32(original, rows[6]["pointer_offset"]))
        original, base, end, _ = bank_fixture(alias_donor=True)
        with self.assertRaisesRegex(FormatError, "aliases"):
            patch_fixture(original, base, end)

    def test_mismatching_duplicate_and_insufficient_storage_are_refused(self):
        original, base, end, _ = bank_fixture(donor_text="Not the same")
        with self.assertRaisesRegex(FormatError, "byte-identical"):
            patch_fixture(original, base, end)
        original, base, end, _ = bank_fixture()
        with self.assertRaisesRegex(FormatError, "insufficient"):
            patch_fixture(original, base, end, replacement="A" * 100)

    def test_bad_pointers_headers_lengths_and_preexisting_edits_are_refused(self):
        original, base, end, starts = bank_fixture()
        for relative in (0, 16, end - base, 0xFFFFFFFF):
            data = bytearray(original)
            struct.pack_into(">I", data, base + 20, relative)
            with self.subTest(pointer=relative), self.assertRaises(FormatError):
                patch_fixture(bytes(data), base, end)
        data = bytearray(original)
        data[base + 6:base + 8] = b"UK"
        with self.assertRaises(FormatError):
            patch_fixture(bytes(data), base, end)
        data = bytearray(original)
        data[starts[5]] ^= 1
        with self.assertRaisesRegex(FormatError, "differs"):
            item_text._patch_bank(original, bytes(data), base, end, "FR", {1: ("SUNSTONE", "SUN STONE")}, ((2, 3),))
        with self.assertRaises(FormatError):
            item_text._patch_bank(original, original[:-1], base, end, "FR", {1: ("SUNSTONE", "SUN STONE")}, ((2, 3),))

    def test_invalid_plain_storage_and_conflicting_donors_are_refused(self):
        original, base, end, starts = bank_fixture()
        for changed in (b"\0\0", b"\xff\xff"):
            data = bytearray(original)
            data[starts[2]:starts[2] + 2] = changed
            with self.subTest(changed=changed), self.assertRaises(FormatError):
                patch_fixture(bytes(data), base, end)
        for donors in (((2, 2),), ((1, 3),), ((2, 3), (2, 3)), ((20, 3),)):
            with self.subTest(donors=donors), self.assertRaises(FormatError):
                item_text._patch_bank(original, original, base, end, "FR", {1: ("SUNSTONE", "SUN STONE")}, donors)

    def test_fingerprint_is_mandatory(self):
        with self.assertRaisesRegex(FormatError, "fingerprinted"):
            item_text.apply_item_name_spacing(b"an unrelated REL", b"an unrelated REL")


class RelocationBoundaryTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(0x300)
        records = ((0, 202, 1, 0), (20, 1, 1, 0x60), (4, 201, 0, 0), (0, 203, 0, 0))
        for index, record in enumerate(records):
            struct.pack_into(">HBBI", data, index * 8, *record)
        parsed = {"sections": [{"offset": 0, "size": 0}, {"offset": 0x100, "size": 0x100}],
                  "imports": [{"module_id": 125, "relocations_offset": 0}], "module_id": 125}
        return data, parsed

    def test_sources_and_self_targets_are_tracked_in_file_coordinates(self):
        data, parsed = self.fixture()
        self.assertEqual(item_text._relocation_ranges(bytes(data), parsed),
                         ([(0x114, 0x118)], [(0x160, 0x161)]))
        parsed["imports"][0]["module_id"] = 0
        self.assertEqual(item_text._relocation_ranges(bytes(data), parsed)[1], [])

    def test_invalid_relocation_ranges_and_commands_are_refused(self):
        for offset, value in ((2, 254), (3, 8), (8, 0xFF), (14, 0xFF)):
            data, parsed = self.fixture()
            data[offset] = value
            with self.subTest(offset=offset), self.assertRaises(FormatError):
                item_text._relocation_ranges(bytes(data), parsed)


@unittest.skipUnless(Path("game/files/common.fsys").is_file(), "local original PAL game is unavailable")
class LocalPALNameTests(unittest.TestCase):
    def test_native_languages_every_other_plain_id_and_exact_whitelist(self):
        from orre_randomizer.engine.randomize_trainers import original_common, layout
        from orre_randomizer.engine.inspect_tables import localized_names
        original = original_common(Path("game"))[2]
        current = bytearray(original)
        # An unrelated upstream engine edit must survive byte-for-byte.
        current[layout(original)[0]["trainer_pokemon"]["offset"] + 4] ^= 1
        output, report = item_text.apply_item_name_spacing(original, bytes(current))
        self.assertEqual(len(output), len(original))
        self.assertEqual(report["changed_names"], 11)
        self.assertEqual(sum(len(bank["donors"]) for bank in report["banks"]), 12)
        symbols = layout(original)[1]
        before, _ = localized_names(original, symbols)
        after, _ = localized_names(output, symbols)
        # Every bank stays in its native language; GUI preferences never enter this patch.
        stones = {
            "UK": ("SUN STONE", "MOON STONE", "FIRE STONE", "THUNDER STONE", "WATER STONE", "LEAF STONE"),
            "FR": ("PIERRE SOLEIL", "PIERRE LUNE", "PIERRE FEU", "PIERRE FOUDRE", "PIERRE EAU", "PIERRE PLANTE"),
            "GE": ("SONNENSTEIN", "MONDSTEIN", "FEUERSTEIN", "DONNERSTEIN", "WASSERSTEIN", "BLATTSTEIN"),
            "IT": ("PIETRA SOLARE", "PIETRA LUNARE", "PIETRA FOCAIA", "PIETRA TUONO", "PIETRA IDRICA", "PIETRA FOGLIA"),
            "SP": ("PIEDRA SOLAR", "PIEDRA LUNAR", "PIEDRA FUEGO", "PIEDRA TRUENO", "PIEDRA AGUA", "PIEDRA HOJA"),
        }
        for language, expected in stones.items():
            self.assertEqual(tuple(after[language][identifier] for identifier in range(5074, 5080)), expected)
        for language in before:
            self.assertEqual(set(before[language]), set(after[language]))
            for identifier, text in before[language].items():
                expected = item_text.REPLACEMENTS.get(language, {}).get(identifier, (text, text))[1]
                self.assertEqual(after[language][identifier], expected)
        self.assertEqual(before["GE"], after["GE"])
        whitelist = {index for start, end in report["allowed_ranges"] for index in range(start, end)}
        self.assertTrue(all(a == b or index in whitelist for index, (a, b) in enumerate(zip(current, output))))
        with self.assertRaisesRegex(FormatError, "already been changed"):
            item_text.apply_item_name_spacing(original, output)
        changed_original = bytearray(original)
        changed_original[-1] ^= 1
        with self.assertRaises(FormatError):
            item_text.apply_item_name_spacing(bytes(changed_original), original)


if __name__ == "__main__":
    unittest.main()
