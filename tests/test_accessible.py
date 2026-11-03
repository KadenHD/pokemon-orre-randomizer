"""Optional integration checks against the user's fingerprinted local dump."""
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from randomize_accessible import (MOON_STONE_PRICE_OFFSET, randomize_accessible_dol,
                                  randomize_accessible_rel)
from randomize_story import randomize_specials
from randomize_trainers import layout, original_common, randomize_rel
from evolution_rules import evolution_families

GAME = Path(__file__).resolve().parents[1] / "game"


@unittest.skipUnless((GAME / "files/common.fsys").exists(), "requires original local game dump")
class AccessibleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.original = original_common(GAME)
        cls.seed = "qa-colosseum-v1"

    def test_unique_families_json_stability_and_ordinary_draws(self):
        base, _ = randomize_rel(self.original, self.seed)
        result, plan = randomize_accessible_rel(self.original, self.seed)
        self.assertEqual(json.loads(json.dumps(plan)), plan)
        tables, _ = layout(self.original)
        family, _ = evolution_families(result, tables)
        picks = plan["trainers"]["shadow_changes"]
        self.assertEqual(len({family[c["new_species_index"]] for c in picks}), 48)
        self.assertEqual(plan["shadow_families"]["rerolled_shadow_ids"], [23, 31, 35, 38, 43, 44, 56])
        for c in plan["trainers"]["trainer_pokemon_changes"]:
            if not c["shadow_id"]:
                pos = c["offset"]
                self.assertEqual(result[pos:pos + 80], base[pos:pos + 80])
        self.assertTrue(plan["all_evolution_families_preserved"])

    def test_starter_draws_preserved_and_moon_stone_price_set(self):
        source = (GAME / "sys/main.dol").read_bytes()
        v2, _ = randomize_specials(source, self.original, self.seed)
        result, plan = randomize_accessible_dol(source, self.original, self.seed)
        self.assertEqual(struct.unpack_from(">H", result, MOON_STONE_PRICE_OFFSET)[0], 2100)
        restored = bytearray(result)
        restored[MOON_STONE_PRICE_OFFSET:MOON_STONE_PRICE_OFFSET + 2] = v2[MOON_STONE_PRICE_OFFSET:MOON_STONE_PRICE_OFFSET + 2]
        self.assertEqual(bytes(restored), v2)
        self.assertEqual(json.loads(json.dumps(plan)), plan)


if __name__ == "__main__":
    unittest.main()
