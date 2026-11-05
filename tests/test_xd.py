from dataclasses import replace
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from orre_randomizer import xd
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.journal import render_journal
from orre_randomizer.preview import preview_xd
from orre_randomizer.profiles import LEGACY_XD_ENGINE, PREVIOUS_XD_ENGINE, load_profile, parse_xd_profile, save_profile
from orre_randomizer.service import UserError, check_disc_identity
from orre_randomizer.xd_shops import STONE_PRICE, patch_stone_price


def boot_for(game_id):
    data = bytearray(0x440)
    data[:6] = game_id.encode("ascii")
    data[0x1C:0x20] = bytes.fromhex("c2339f3d")
    return bytes(data)


class XDTests(unittest.TestCase):
    def test_v7_profiles_keep_full_spots_without_enabling_shadow_shinies(self):
        from dataclasses import asdict
        from orre_randomizer.profiles import PREVIOUS_XD_FULL_SPOT_ENGINE
        region = xd.REGIONS["GXXP01"]
        options = replace(xd.XDOptions.recommended(), custom_shadow_shinies=False)
        payload = {"engine_version": PREVIOUS_XD_FULL_SPOT_ENGINE, "game_id": region.game_id,
                   "revision": 0, "source_iso_sha256": region.iso_sha256,
                   "seed": "v7-full-pool", "options": asdict(options)}
        payload["options"].pop("custom_shadow_shinies")
        profile = parse_xd_profile(json.dumps(payload).encode(), report=True)
        self.assertEqual(profile.options, options)
        self.assertTrue(profile.options.poke_spots_full_pokedex)
        self.assertFalse(profile.options.custom_shadow_shinies)

    def test_rc1_profile_keeps_all_options_after_runtime_hook_fix(self):
        from dataclasses import asdict
        from orre_randomizer.profiles import PREVIOUS_XD_QOL_ENGINE
        region = xd.REGIONS["GXXP01"]
        options = replace(xd.XDOptions.recommended(), poke_spots_full_pokedex=False, custom_shadow_shinies=False, randomize_hordel_gift=True,
                          experience_multiplier=1.5, purification_multiplier=3)
        data = {"engine_version": PREVIOUS_XD_QOL_ENGINE, "game_id": region.game_id,
                "revision": 0, "source_iso_sha256": region.iso_sha256,
                "seed": "old-runtime", "options": asdict(options)}
        data["options"].pop("poke_spots_full_pokedex")
        data["options"].pop("custom_shadow_shinies")
        profile = parse_xd_profile(json.dumps(data).encode(), report=True)
        self.assertEqual(profile.options, options)
        self.assertFalse(profile.xd_spot_migration)
        with TemporaryDirectory() as folder:
            import hashlib
            path = Path(folder) / "rc1-profile.json"
            save_profile(path, "old-runtime", options)
            payload = json.loads(path.read_text("utf-8"))
            payload.pop("configuration_sha256")
            payload["engine_version"] = PREVIOUS_XD_QOL_ENGINE
            payload["options"].pop("poke_spots_full_pokedex")
            payload["options"].pop("custom_shadow_shinies")
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            payload["configuration_sha256"] = hashlib.sha256(canonical).hexdigest()
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_profile(path, is_xd=True).options, options)

    def test_xd_profile_preserves_typed_options_and_rejects_colosseum_import(self):
        options = replace(xd.XDOptions.recommended(), excluded_species=(25, 133), randomize_hordel_gift=True,
                          starter_stage="first", trainer_level_multiplier=1.25)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "xd-profile.json"
            save_profile(path, "seed-évolutions", options)
            profile = load_profile(path, is_xd=True)
            self.assertEqual((profile.seed, profile.options), ("seed-évolutions", options))
            with self.assertRaises(UserError):
                load_profile(path)

    def test_copy_accepts_exact_xd_identity_and_has_no_patches(self):
        for game_id, region in xd.REGIONS.items():
            with self.subTest(game_id=game_id):
                boot = boot_for(game_id)
                self.assertEqual(check_disc_identity(boot, region.iso_sha256, is_xd=True), region)
                self.assertEqual(xd.build_patches(
                    Path("unopened.iso"), boot, "copy", xd.XDOptions.unchanged(),
                    lambda *_: None, threading.Event(),
                ), ([], {}))
                with self.assertRaises(UserError):
                    check_disc_identity(boot, region.iso_sha256, is_xd=False)
                with self.assertRaises(UserError):
                    check_disc_identity(boot, "0" * 64, is_xd=True)

    def test_poke_spot_randomization_reorders_only_supported_species_and_preserves_slot_metadata(self):
        data = bytearray(128)
        symbols = [{} for _ in range(20)]
        species = {index: (index, 0, 200, ()) for roster in xd.SPOT_SPECIES.values() for index in roster}
        for index, (symbol, roster) in enumerate(zip((12, 15, 18), xd.SPOT_SPECIES.values(), strict=True)):
            start = index * 36
            count = 108 + index * 4
            symbols[symbol] = {"offset": start}
            symbols[symbol + 1] = {"offset": count}
            struct.pack_into(">I", data, count, 3)
            for slot, identifier in enumerate(roster):
                struct.pack_into(">BBHBB", data, start + slot * 12, 10, 20, identifier, 17, 50)
        original = bytes(data)
        patched, spots, changes = xd._rel(original, "seed", species, {}, symbols, xd.XDOptions())
        self.assertEqual(len(spots), 9)
        self.assertEqual(changes, [])
        for spot, native in xd.SPOT_SPECIES.items():
            choices = [row for row in spots if row["spot"] == spot]
            self.assertEqual({row["species"] for row in choices}, set(native))
            self.assertNotEqual(choices[2]["species"], native[2])
        self.assertEqual(xd._rel(original, "seed", species, {}, symbols, xd.XDOptions())[0], patched)
        restricted, _, _ = xd._rel(original, "seed", species, {}, symbols, xd.XDOptions(), {27})
        self.assertEqual(restricted, original)
        for index in range(9):
            self.assertEqual(patched[index * 12:index * 12 + 2], original[index * 12:index * 12 + 2])
            self.assertEqual(patched[index * 12 + 4:(index + 1) * 12], original[index * 12 + 4:(index + 1) * 12])

    def test_xd_journal_shows_one_starter_using_national_dex_names(self):
        report = {"game": "xd", "summary": {
            "starter": {"species": 283, "level": 10}, "national_ids": {"283": 258},
            "gifts": [{"species": 283, "level": 20, "required_species": 283}],
            "poke_spots": [{"spot": "rock", "slot": 1, "species": 283, "levels": [10, 20], "chance": 50}],
        }}
        english = render_journal(report, "en")
        french = render_journal(report, "fr")
        self.assertIn("Mudkip", english)
        self.assertIn("Poké Spots (1)", english)
        self.assertIn("Gobou", french)
        self.assertIn("Échange contre Gobou", french)
        self.assertIn("Roche · 1", french)
        self.assertNotIn("Umbreon", english)

    def test_legacy_xd_report_imports_with_poke_spot_migration_notice(self):
        from dataclasses import asdict

        region = xd.REGIONS["GXXP01"]
        options = asdict(xd.XDOptions())
        options.pop("poke_spots_full_pokedex")
        options.pop("custom_shadow_shinies")
        options.pop("randomize_hordel_gift")
        options.pop("randomize_tutorial_shadow")
        data = {"engine_version": LEGACY_XD_ENGINE, "game_id": region.game_id, "revision": region.revision,
                "source_iso_sha256": region.iso_sha256, "seed": "legacy", "options": options}
        profile = parse_xd_profile(json.dumps(data).encode(), report=True)
        self.assertTrue(profile.xd_spot_migration)
        self.assertTrue(profile.options.randomize_poke_spots)
        self.assertFalse(profile.options.randomize_tutorial_shadow)
        self.assertFalse(profile.options.randomize_hordel_gift)

    def test_v4_report_keeps_the_tutorial_option_and_defaults_hordel_off(self):
        from dataclasses import asdict

        region = xd.REGIONS["GXXP01"]
        options = asdict(replace(xd.XDOptions(), randomize_tutorial_shadow=True))
        options.pop("poke_spots_full_pokedex")
        options.pop("custom_shadow_shinies")
        options.pop("randomize_hordel_gift")
        data = {"engine_version": PREVIOUS_XD_ENGINE, "game_id": region.game_id, "revision": region.revision,
                "source_iso_sha256": region.iso_sha256, "seed": "previous", "options": options}
        profile = parse_xd_profile(json.dumps(data).encode(), report=True)
        self.assertFalse(profile.xd_spot_migration)
        self.assertTrue(profile.options.randomize_tutorial_shadow)
        self.assertFalse(profile.options.randomize_hordel_gift)

    def test_invalid_xd_revision_is_rejected(self):
        data = bytearray(boot_for("GXXP01"))
        data[7] = 1
        with self.assertRaises(FormatError):
            xd.region_for_boot(bytes(data))

    def test_preview_uses_creation_patch_plan_without_writing_an_output(self):
        options = xd.XDOptions()
        region = xd.REGIONS["GXXP01"]
        boot = boot_for(region.game_id)
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.iso"
            source.write_bytes(boot)
            with (patch("orre_randomizer.service.check_header", return_value=boot),
                  patch("orre_randomizer.service.check_disc_identity", return_value=region),
                  patch("orre_randomizer.service.build_xd_patches",
                        return_value=([], {"gifts": [{"species": 25}]})) as build):
                result = preview_xd(source, "seed", options)
            self.assertEqual(result["gifts"], [{"species": 25}])
            self.assertEqual(build.call_args.args[:4], (source.resolve(), boot, "seed", options))
            self.assertEqual(list(Path(directory).iterdir()), [source])
            self.assertEqual(source.read_bytes(), boot)

    def test_moon_stone_uses_the_other_stones_cash_price(self):
        rel = bytearray(99 * 0x28)
        for index in range(93, 99):
            position = index * 0x28
            rel[position] = 2
            struct.pack_into(">H", rel, position + 6, 0 if index == 94 else STONE_PRICE)
            struct.pack_into(">I", rel, position + 0x10, 5074 + index - 93)
        symbols = [{} for _ in range(70)] + [{"offset": 0}]
        patched = patch_stone_price(rel, symbols)
        position = 94 * 0x28 + 6
        self.assertEqual(patched, bytes(rel[:position]) + struct.pack(">H", STONE_PRICE) + bytes(rel[position + 2:]))
