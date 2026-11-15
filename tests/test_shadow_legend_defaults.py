"""Native species preservation and independent bonus-encounter controls."""
from dataclasses import replace
from collections import Counter
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import parse_rel, parse_fsys
from orre_randomizer.engine.gameplay_rules import apply_rel_rules, apply_story_rules, expanded_layout
from orre_randomizer.engine.inspect_tables import localized_names, rel_symbols, u16
from orre_randomizer.engine.postgame_boss import DEFAULT_TEAM, apply_common, plan_team, _append_boss_asset
from orre_randomizer.engine.postgame_boss import bonus_shadow_species
from orre_randomizer.engine.postgame_mail import mail_texts
from orre_randomizer.engine.postgame_scene_model import append_field_model, RESOURCE
from orre_randomizer.engine.postgame_scene_text import dialogue_payloads
from orre_randomizer.engine.randomize_trainers import original_common
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL, species_catalog
from orre_randomizer.options import Options
from orre_randomizer.presets import recommended_preset, species_preset
from orre_randomizer.service import transform_dol, transform_rel

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"


@unittest.skipUnless((GAME / "files/common.fsys").is_file(), "requires original local Colosseum files")
class NativeLegendAndEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_common(GAME)[2]
        cls.dol = (GAME / "sys/main.dol").read_bytes()
        cls.tables = expanded_layout(cls.original)
        cls.catalog = species_catalog(cls.original, cls.tables)
        table = cls.tables["shadow"]
        cls.shadows = {sid: u16(cls.original, table["offset"] + sid * table["stride"] + 2)
                       for sid in range(1, table["count"])
                       if u16(cls.original, table["offset"] + sid * table["stride"] + 2)}
        cls.legends = {sid: old for sid, old in cls.shadows.items()
                       if cls.catalog[old]["national_dex"] in LEGENDARY_NATIONAL}

    def final_rel(self, seed, options):
        base = transform_rel(self.original, seed, options)[0]
        if options.diverse_story_families:
            dol = transform_dol(self.dol, self.original, seed, options)[0]
            return apply_story_rules(self.original, base, self.dol, dol, seed, options)[0]
        return apply_rel_rules(self.original, base, seed, options)[0]

    def test_both_presets_preserve_native_beasts_across_aliases_and_boss_filters(self):
        self.assertEqual({self.catalog[old]["national_dex"] for old in self.legends.values()}, {243, 244, 245})
        for preset in (recommended_preset(), species_preset()):
            for mode in ("any", "exclude"):
                options = replace(preset, boss_shadow_legendary_mode=mode)
                with self.subTest(preset=preset.randomize_trainer_moves, mode=mode):
                    final = self.final_rel("protected-beasts", options)
                    table, party = self.tables["shadow"], self.tables["trainer_pokemon"]
                    for sid, old in self.legends.items():
                        self.assertEqual(u16(final, table["offset"] + sid * table["stride"] + 2), old)
                        aliases = [party["offset"] + slot * party["stride"] for slot in range(party["count"])
                                   if self.original[party["offset"] + slot * party["stride"] + 3] == sid]
                        self.assertTrue(aliases)
                        self.assertTrue(all(u16(final, pos + 0xA) == old for pos in aliases))

    def test_enabling_the_advanced_choice_replaces_all_three_beasts(self):
        options = replace(species_preset(), randomize_legendary_shadows=True)
        final = self.final_rel("replace-beasts", options)
        table = self.tables["shadow"]
        for sid, old in self.legends.items():
            self.assertNotEqual(u16(final, table["offset"] + sid * table["stride"] + 2), old)

    def test_default_bonus_keeps_authored_species_moves_and_items_after_general_randomization(self):
        options = recommended_preset()
        final = self.final_rel("authored-event", options)
        expanded, event = apply_common(self.original, final, options, seed="authored-event")
        self.assertEqual([row["species"] for row in event["team"]], [*DEFAULT_TEAM, 249])
        party = self.tables["trainer_pokemon"]
        for row in event["team"][:-1]:
            old = party["offset"] + row["source_slot"] * party["stride"]
            self.assertEqual(row["moves"], [u16(self.original, old + pos) for pos in (0x36, 0x3E, 0x46, 0x4E)])
            self.assertEqual(row["held_item"], u16(self.original, old + 0x12))
        self.assertEqual(event["team"][-1]["moves"], [177, 94, 105, 56])
        self.assertEqual([row["level"] for row in event["team"]], list(range(65, 71)))

    def test_bonus_replacement_reaches_shadow_metadata_without_changing_native_roster(self):
        options = replace(species_preset(), postgame_randomize_lugia=True)
        output, event = apply_common(self.original, self.original, options, seed="new-shadow")
        self.assertNotEqual(event["species"], 249)
        self.assertEqual(event["species"], event["team"][-1]["species"])
        table = self.tables["shadow"]
        self.assertEqual(u16(output, table["offset"] + 96 * table["stride"] + 2), event["species"])
        for sid, old in self.shadows.items():
            self.assertEqual(u16(output, table["offset"] + sid * table["stride"] + 2), old)

    def test_bonus_replacement_avoids_protected_shadow_families(self):
        options = replace(recommended_preset(), postgame_randomize_lugia=True)
        chosen = bonus_shadow_species(self.original, "74", options)
        self.assertNotIn(chosen, self.legends.values())

    def test_oversized_shiny_replacement_loads_a_room_local_model(self):
        source = (GAME / "files/M3_shrine_1F.fsys").read_bytes()
        donor = (GAME / "files/D4_casino_colo.fsys").read_bytes()
        source = _append_boss_asset(source, donor)
        wailord = next(index for index, row in self.catalog.items() if row["national_dex"] == 321)
        variants = []
        for shiny in (False, True):
            output, report = append_field_model(source, self.original, shiny=shiny, species=wailord,
                original_dol=self.dol, read_archive=lambda name: (GAME / "files" / name).read_bytes())
            member = next(row for row in parse_fsys(output)["members"] if int(row["identifier_raw"], 16) == RESOURCE)
            variants.append(decoded_member(output, member))
            self.assertEqual(report["scale"], 0.12)
            self.assertEqual(report["species"], wailord)
            self.assertTrue(report["native_pikachu_resource_preserved"])
        self.assertNotEqual(*variants)


class LocalizedReplacementTextTests(unittest.TestCase):
    def test_every_local_species_name_fits_the_scene_and_mail(self):
        failures, count = [], 0
        for tag in ("pal", "usa", "japan"):
            path = ROOT / "build/region-compat-2026-11-02/rel-research" / tag / "common.fsys-common_rel.rel"
            if not path.is_file():
                continue
            original = path.read_bytes()
            catalog = species_catalog(original, expanded_layout(original))
            banks = localized_names(original, rel_symbols(original, parse_rel(original)))[0]
            for language, bank in banks.items():
                if not bank:
                    continue
                for index, row in catalog.items():
                    name_id = struct.unpack_from(">I", original, row["offset"] + 0x18)[0]
                    name = bank[name_id]
                    try:
                        dialogue_payloads(language, bank, species_name=name)
                        _, body = mail_texts(language, name)
                        limit = 14 if language == "JP" else 29
                        self.assertTrue(all(len(line) <= limit for line in body.splitlines()))
                    except Exception as error:
                        failures.append((language, index, name, str(error)))
                    count += 1
        if not count:
            self.skipTest("requires original local regional message banks")
        summary = Counter((language, error) for language, _, _, error in failures)
        self.assertEqual(len(failures), 0, f"Failures by caption: {dict(summary)}; samples: {failures[:3]}")


if __name__ == "__main__":
    unittest.main()
