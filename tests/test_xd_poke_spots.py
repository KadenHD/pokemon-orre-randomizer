"""Full-Pokédex encounters preserve slot data and keep Duking's requests distinct."""
from dataclasses import asdict, replace
import json
import struct
import unittest

from orre_randomizer import xd
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.profiles import PREVIOUS_XD_SHUFFLE_ENGINE, parse_xd_profile
from orre_randomizer.service import UserError
from orre_randomizer.xd_poke_spot_actors import _patch_species_checks


def fixture():
    data = bytearray(128)
    symbols = [{} for _ in range(20)]
    roster = {index for native in xd.SPOT_SPECIES.values() for index in native}
    roster.update((1, 4, 7, 25, 88, 133, 150, 155, 158, 170, 249, 251))
    species = {index: (index, 0, 200, ()) for index in roster}
    for index, (symbol, native) in enumerate(zip((12, 15, 18), xd.SPOT_SPECIES.values(), strict=True)):
        start, count = index * 36, 108 + index * 4
        symbols[symbol] = {"offset": start}
        symbols[symbol + 1] = {"offset": count}
        struct.pack_into(">I", data, count, 3)
        for slot, identifier in enumerate(native):
            struct.pack_into(">BBHBB", data, start + slot * 12, 10 + slot, 20 + slot, identifier, 17, 50 - slot)
    return bytes(data), symbols, species


class XDSpotTests(unittest.TestCase):
    def test_appearance_preserves_the_native_shiny_check_and_selects_the_shiny_model(self):
        model = 0x16600400
        shiny_model = 0x23000400
        branch = bytearray(0x68)
        struct.pack_into(">9I", branch, 0, 0x02010000, 27, 0x01300000, 0x0B00005B, 0x10000081,
                         0x02010000, model, 0x03030087, 0x09230046)
        struct.pack_into(">I", branch, 0x40, 0x093C0014)
        struct.pack_into(">4I", branch, 0x58, 0x02010000, 0, 0x03030087, 0x09230070)
        unrelated_species_check = struct.pack(">3I", 0x02010000, 27, 0x01300000)
        original = unrelated_species_check + branch
        edit = [(27, 314, model, shiny_model, 0)]
        updated = _patch_species_checks(original, branches=edit)
        expected = bytearray(original)
        for offset, word in ((4, 314), (0x5C, shiny_model), (0x64, 0x09230046)):
            struct.pack_into(">I", expected, len(unrelated_species_check) + offset, word)
        self.assertEqual(updated, expected)
        with self.assertRaisesRegex(FormatError, "appearance branch"):
            _patch_species_checks(branch + branch, branches=edit)

    def test_full_draw_uses_filtered_non_native_species_and_preserves_every_other_byte(self):
        original, symbols, species = fixture()
        allowed = {1, 4, 7, 25, 88, 133, 150, 155, 158}
        options = xd.XDOptions.recommended()
        patched, spots, _ = xd._rel(original, "full-pool", species, {}, symbols, options, allowed)
        self.assertEqual({row["species"] for row in spots}, allowed)
        self.assertEqual(len({row["species"] for row in spots if row["slot"] == 3}), 3)
        for spot in xd.SPOT_SPECIES:
            self.assertEqual(len({row["species"] for row in spots if row["spot"] == spot}), 3)
        for index in range(9):
            self.assertEqual(patched[index * 12:index * 12 + 2], original[index * 12:index * 12 + 2])
            self.assertEqual(patched[index * 12 + 4:(index + 1) * 12], original[index * 12 + 4:(index + 1) * 12])
        self.assertEqual(patched[108:], original[108:])
        self.assertEqual(xd._rel(original, "full-pool", species, {}, symbols, options, allowed)[0], patched)

    def test_narrow_pool_still_produces_three_different_obtainable_trade_requests(self):
        original, symbols, species = fixture()
        allowed = {27, 207, 332}
        for seed in ("one", "two", "three", "four"):
            _, spots, _ = xd._rel(original, seed, species, {}, symbols, xd.XDOptions.recommended(), allowed)
            self.assertEqual({row["species"] for row in spots if row["slot"] == 3}, allowed)
            for spot in xd.SPOT_SPECIES:
                self.assertEqual({row["species"] for row in spots if row["spot"] == spot}, allowed)

    def test_impossible_filters_fail_instead_of_adding_excluded_species(self):
        original, symbols, species = fixture()
        with self.assertRaisesRegex(FormatError, "trois Pokémon"):
            xd._rel(original, "too-few", species, {}, symbols, xd.XDOptions.recommended(), {1, 4})

    def test_disabling_spots_preserves_encounters_even_with_full_pool_selected(self):
        original, symbols, species = fixture()
        options = replace(xd.XDOptions.unchanged(), poke_spots_full_pokedex=True)
        patched, spots, _ = xd._rel(original, "off", species, {}, symbols, options, {1})
        self.assertEqual(patched, original)
        self.assertEqual([row["species"] for row in spots],
                         [index for native in xd.SPOT_SPECIES.values() for index in native])

    def test_v6_reports_keep_native_shuffle_and_current_reports_require_explicit_pool(self):
        options = asdict(replace(xd.XDOptions.recommended(), poke_spots_full_pokedex=False, custom_shadow_shinies=False))
        options.pop("poke_spots_full_pokedex")
        options.pop("custom_shadow_shinies")
        region = xd.REGIONS["GXXP01"]
        payload = {"engine_version": PREVIOUS_XD_SHUFFLE_ENGINE, "game_id": region.game_id,
                   "revision": 0, "source_iso_sha256": region.iso_sha256, "seed": "old-native", "options": options}
        profile = parse_xd_profile(json.dumps(payload).encode(), report=True)
        self.assertFalse(profile.options.poke_spots_full_pokedex)
        self.assertFalse(profile.xd_spot_migration)
        self.assertEqual({key: asdict(profile.options)[key] for key in options}, options)
        payload["engine_version"] = xd.VERSION
        with self.assertRaises(UserError):
            parse_xd_profile(json.dumps(payload).encode(), report=True)
