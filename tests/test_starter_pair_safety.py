"""Natural starter pair safety preserves species and all non-harmless moves."""
from dataclasses import dataclass, replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.species_rules import species_catalog
from orre_randomizer.engine.starter_rules import (
    DRAW_VERSION, NATURAL_DRAW_VERSION, STARTERS, _harmless_natural_pools,
    apply_starter_rules, apply_starter_tables, starter_rules_active,
)
from orre_randomizer.move_modes import natural_moves
from tests.test_starter_rules import StageRules, fixture


ROOT = Path(__file__).resolve().parents[1]
ERROR = "Les deux starters n’auraient que des capacités sans effet offensif. Élargissez les Pokémon autorisés ou choisissez un partenaire différent."


@dataclass(frozen=True)
class NaturalRules(StageRules):
    randomize_starter_moves: str = "natural"
    starter_umbreon_species: int = 0
    starter_espeon_species: int = 0
    excluded_species: tuple[int, ...] = ()


def natural_fixture():
    dol, native, tables = fixture()
    rel = bytearray(native)
    catalog = species_catalog(native, tables)
    for index, row in catalog.items():
        at = row["offset"]
        # Ordinary attacks for every fixture species except two passive forms.
        move = {1: 100, 4: 106}.get(index, 33)
        rel[at + 0xBA] = 1
        struct.pack_into(">H", rel, at + 0xBC, move)
    moves = {100: {"power": 0, "effect": 153}, 106: {"power": 0, "effect": 11},
             150: {"power": 0, "effect": 85}, 33: {"power": 35, "effect": 0}}
    return dol, bytes(rel), tables, moves


class NaturalStarterPairSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dol, cls.rel, cls.tables, cls.moves = natural_fixture()
        cls.catalog = species_catalog(cls.rel, cls.tables)

    def apply(self, rules, seed="pair-safety", *, select_pair=None, rel=None, moves=None):
        return apply_starter_tables(self.dol, self.dol, self.rel, self.rel if rel is None else rel,
            seed, rules, self.tables, select_pair=select_pair,
            native_moves=self.moves if moves is None else moves)

    def test_automatic_natural_pairs_cannot_both_have_only_certified_harmless_moves(self):
        rules = NaturalRules()
        self.assertTrue(starter_rules_active(rules))
        pairs = set()
        for i in range(32):
            result, report = self.apply(rules, str(i))
            pair = tuple(row["species_index"] for row in report["pair"])
            pairs.add(pair)
            self.assertFalse(set(pair) <= {1, 4})
            self.assertTrue(report["natural_pair_safety"]["automatic_draw_protected"])
            self.assertGreater(report["natural_pair_safety"]["excluded_pair_count"], 0)
            self.assertEqual(report["draw_domain"], NATURAL_DRAW_VERSION)
            self.assertEqual((result, report), self.apply(rules, str(i)))
        self.assertGreater(len(pairs), 1)

    def test_one_manual_passive_partner_is_kept_and_only_automatic_partner_is_constrained(self):
        for field in ("starter_umbreon_species", "starter_espeon_species"):
            rules = replace(NaturalRules(), **{field: 1})
            slot = 0 if field == "starter_umbreon_species" else 1
            for seed in ("one-manual-a", "one-manual-b"):
                _, report = self.apply(rules, seed)
                pair = report["pair"]
                self.assertEqual(pair[slot]["species_index"], 1)
                self.assertNotIn(pair[1-slot]["species_index"], {1, 4})

    def test_two_explicit_passive_choices_are_preserved_and_reported(self):
        for first, second in ((1, 4), (1, 1)):
            rules = replace(NaturalRules(), starter_umbreon_species=first, starter_espeon_species=second)
            _, report = self.apply(rules)
            self.assertEqual(tuple(row["species_index"] for row in report["pair"]), (first, second))
            self.assertTrue(report["natural_pair_safety"]["both_known_harmless"])
            self.assertFalse(report["natural_pair_safety"]["automatic_draw_protected"])
            self.assertEqual(report["natural_pair_safety"]["excluded_pair_count"], 0)
            self.assertEqual(report["draw_domain"], DRAW_VERSION)

    def test_filters_are_not_relaxed_when_only_harmless_automatic_pairs_remain(self):
        excluded = tuple(row["national_dex"] for index, row in self.catalog.items() if index not in {1, 4})
        rules = replace(NaturalRules(), excluded_species=excluded)
        with self.assertRaisesRegex(FormatError, "capacités sans effet offensif"):
            self.apply(rules)
        _, report = self.apply(replace(rules, starter_umbreon_species=1, starter_espeon_species=4))
        self.assertEqual([row["species_index"] for row in report["pair"]], [1, 4])

    def test_existing_family_type_and_power_constraints_remain_in_effect(self):
        rules = replace(NaturalRules(), starter_distinct_families=True,
                        starter_complementary_types=True, starter_balance_pair=True)
        for seed in ("rules-a", "rules-b", "rules-c"):
            _, report = self.apply(rules, seed)
            a, b = report["pair"]
            self.assertNotEqual(a["family"], b["family"])
            self.assertFalse(set(a["types"]) & set(b["types"]))
            self.assertLessEqual(report["pair_bst_difference"], report["pair_bst_tolerance"])
            self.assertFalse(report["natural_pair_safety"]["both_known_harmless"])

    def test_power_one_counter_transform_sketch_and_other_effects_are_not_called_harmless(self):
        # The proof is an allowlist of harmless native effects, not !damaging().
        for move, power in ((49, 1), (67, 1), (68, 1), (82, 1), (101, 1), (117, 1),
                            (144, 0), (149, 1), (166, 0), (216, 1), (217, 1),
                            (237, 1), (243, 1), (92, 0), (73, 0)):
            current = bytearray(self.rel)
            at = self.catalog[1]["offset"]
            struct.pack_into(">H", current, at + 0xBC, move)
            catalog = species_catalog(bytes(current), self.tables)
            moves = self.moves | {move: {"power": power, "effect": 999}}
            passive = _harmless_natural_pools(catalog, ([1], [1]), STARTERS, moves)
            with self.subTest(move=move):
                self.assertEqual(passive, (set(), set()))

    def test_actual_final_learns_and_each_slot_level_determine_the_passive_proof(self):
        current = bytearray(self.rel)
        at = self.catalog[1]["offset"]
        current[at + 0xBE] = 26
        struct.pack_into(">H", current, at + 0xC0, 33)
        catalog = species_catalog(bytes(current), self.tables)
        passive = _harmless_natural_pools(catalog, ([1], [1]), STARTERS, self.moves)
        self.assertEqual(passive, (set(), {1}))

    def test_unqualified_native_effects_are_refused_before_pair_publication(self):
        for move in (100, 106, 150):
            moves = self.moves | {move: {"power": 0, "effect": 999}}
            with self.subTest(move=move), self.assertRaisesRegex(FormatError, "native harmless-move"):
                self.apply(NaturalRules(), moves=moves)

    def test_story_allocator_receives_safe_pairs_and_cannot_reintroduce_the_unsafe_pair(self):
        seen = []
        def choose(pair, pairings):
            seen.extend((first, second) for first, seconds in pairings.items() for second in seconds)
            return pair
        self.apply(NaturalRules(), select_pair=choose)
        self.assertTrue(seen)
        self.assertFalse(any(first in {1, 4} and second in {1, 4} for first, second in seen))
        with self.assertRaisesRegex(FormatError, "unsafe passive"):
            self.apply(NaturalRules(), select_pair=lambda *args: (1, 4))

    def test_error_is_localized_in_all_six_interface_languages(self):
        from orre_randomizer.i18n import translate
        for language in ("en", "de", "es", "it", "ja"):
            with self.subTest(language=language):
                self.assertNotEqual(translate(ERROR, language), ERROR)
        self.assertEqual(translate(ERROR, "fr"), ERROR)


@unittest.skipUnless((ROOT / "game/sys/main.dol").is_file(), "requires local original Colosseum data")
class NativeNaturalStarterPairTests(unittest.TestCase):
    def test_story_diversity_checks_randomized_final_learns_instead_of_native_passive_moves(self):
        from orre_randomizer.engine.randomize_trainers import original_common
        from orre_randomizer.engine.gameplay_rules import apply_story_rules, apply_dol_rules, expanded_layout, move_catalog
        from orre_randomizer.options import Options
        rel = original_common(ROOT / "game")[2]
        dol = (ROOT / "game/sys/main.dol").read_bytes()
        # Abra and Silcoon are both passive at the starter levels natively. This
        # advanced configuration replaces their learns with real damaging moves.
        options = replace(Options.none(), starter_umbreon=True, starter_espeon=True,
            allow_gen1=True, allow_gen3=True, starter_stage="any", randomize_starter_moves="natural",
            diverse_story_families=True, randomize_learnsets=True, randomize_preserved_properties=True,
            ensure_damaging_move=True, ensure_stab_move=False,
            excluded_species=tuple(n for n in range(1, 387) if n not in (63, 266)))
        seed = "v211-final-learns"
        final_rel, _, starters, gifts = apply_story_rules(rel, rel, dol, dol, seed, options)
        _, report = apply_dol_rules(dol, dol, rel, final_rel, seed, options,
                                   starter_result=starters, gift_picks=gifts)
        catalog = species_catalog(final_rel, expanded_layout(rel))
        moves = move_catalog(rel, expanded_layout(rel))
        self.assertTrue(starters[1]["natural_pair_safety"]["automatic_draw_protected"])
        self.assertFalse(starters[1]["natural_pair_safety"]["both_known_harmless"])
        actual = [natural_moves(catalog[row["species_index"]]["learnset"], row["level"], [0]*4, moves)
                  for row in starters[1]["pair"]]
        self.assertTrue(all(any(moves[move]["power"] > 0 for move in row if move) for row in actual))
        self.assertEqual([row["moves"] for row in report["specials"]
                          if row["key"] in ("umbreon", "espeon")], actual)

    def test_confirmed_default_passive_pair_seed_now_draws_a_partner_with_another_move(self):
        from orre_randomizer.engine.randomize_trainers import original_common
        from orre_randomizer.engine.gameplay_rules import expanded_layout, move_catalog
        from orre_randomizer.presets import species_preset
        rel = original_common(ROOT / "game")[2]
        dol = (ROOT / "game/sys/main.dol").read_bytes()
        seed, options = "v211-start-pair-5534", species_preset()
        _, report = apply_starter_rules(dol, dol, rel, rel, seed, options)
        catalog = species_catalog(rel, expanded_layout(rel))
        moves = move_catalog(rel, expanded_layout(rel))
        actual = [natural_moves(catalog[row["species_index"]]["learnset"], row["level"], [0]*4, moves)
                  for row in report["pair"]]
        self.assertFalse(all(set(row) <= {0, 100, 106, 150} for row in actual))
        self.assertFalse(report["natural_pair_safety"]["both_known_harmless"])
        self.assertGreater(report["natural_pair_safety"]["excluded_pair_count"], 0)
        self.assertEqual(report, apply_starter_rules(dol, dol, rel, rel, seed, options)[1])


if __name__ == "__main__":
    unittest.main()
