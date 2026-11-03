import copy
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_game import FormatError
from evolution_rules import (EVOLUTION_FIXES, evolution_families,
                             patch_evolutions, unique_shadow_picks)
from randomize_trainers import choose_species


def fixture(count=413):
    tables = {"species": {"offset": 0x100, "count": count, "stride": 0x11C},
              "shadow": {"offset": 0x100 + count * 0x11C, "count": 97, "stride": 0x38}}
    data = bytearray(tables["shadow"]["offset"] + 97 * 0x38)
    # A compact synthetic pool can contain real species at sparse internal IDs.
    return data, tables


def add_species(data, tables, indices):
    for national, index in enumerate(sorted(indices), start=1):
        if national > 386:
            raise ValueError("synthetic pool exceeds real national range")
        position = tables["species"]["offset"] + index * tables["species"]["stride"]
        struct.pack_into(">H", data, position + 0x10, national)


def add_evolution(data, tables, source, target, method=4, condition=20, slot=0):
    position = tables["species"]["offset"] + source * tables["species"]["stride"] + 0x9C + slot * 6
    struct.pack_into(">BBHH", data, position, method, 0xA5, condition, target)
    return position


class EvolutionFamilyTests(unittest.TestCase):
    def test_forks_and_shared_ancestors_include_every_stage(self):
        data, tables = fixture()
        indices = {133, 134, 135, 136, 196, 197, 106, 107, 236, 237,
                   290, 291, 292, 293, 294, 400}
        add_species(data, tables, indices)
        for slot, target in enumerate((134, 135, 136, 196, 197)):
            add_evolution(data, tables, 133, target, slot=slot)
        for slot, target in enumerate((106, 107, 237)):
            add_evolution(data, tables, 236, target, method=8 + slot, slot=slot)
        for slot, target in enumerate((291, 293)):
            add_evolution(data, tables, 290, target, method=11 + slot, slot=slot)
        add_evolution(data, tables, 291, 292)
        add_evolution(data, tables, 293, 294)
        mapping, families = evolution_families(bytes(data), tables)
        self.assertEqual(families[133], [133, 134, 135, 136, 196, 197])
        self.assertEqual(families[106], [106, 107, 236, 237])
        self.assertEqual(families[290], [290, 291, 292, 293, 294])
        self.assertEqual(mapping[134], mapping[197])  # Siblings do not reach each other directly.
        self.assertEqual(mapping[106], mapping[107])  # Ancestor index need not be smallest.
        self.assertEqual(families[400], [400])
        self.assertEqual(list(mapping), sorted(indices))

    def test_invalid_targets_and_unknown_methods_are_rejected(self):
        for target, method in ((9, 4), (2, 16)):
            data, tables = fixture(10)
            add_species(data, tables, (1, 2))
            add_evolution(data, tables, 1, target, method=method)
            with self.subTest(target=target, method=method), self.assertRaises(FormatError):
                evolution_families(bytes(data), tables)


class EvolutionPatchTests(unittest.TestCase):
    def setup_patch_fixture(self):
        data, tables = fixture()
        indices = {index for rule in EVOLUTION_FIXES for index in rule[:2]}
        indices.update((42, 169, 133, 134, 135, 136, 79, 80, 61, 62,
                        236, 106, 107, 237, 290, 291, 293, 301, 302, 303))
        add_species(data, tables, indices)
        next_slot = {}
        positions = {}
        # Put native branches before edited branches to exercise mixed records.
        native = ((133, 135, 7, 96), (133, 134, 7, 97), (133, 136, 7, 95),
                  (79, 80, 4, 37), (61, 62, 7, 97), (42, 169, 1, 0),
                  (236, 106, 8, 20), (236, 237, 9, 20), (236, 107, 10, 20),
                  (290, 291, 11, 7), (290, 293, 12, 7),
                  (301, 302, 4, 20), (301, 303, 14, 20))
        native_positions = []
        for source, target, method, condition in native:
            slot = next_slot.get(source, 0)
            native_positions.append(add_evolution(data, tables, source, target, method, condition, slot))
            next_slot[source] = slot + 1
        for source, target, old_method, old_condition, *_ in EVOLUTION_FIXES:
            slot = next_slot.get(source, 0)
            positions[(source, target)] = add_evolution(data, tables, source, target, old_method, old_condition, slot)
            next_slot[source] = slot + 1
        return bytes(data), tables, positions, native_positions

    def test_exact_fifteen_edits_preserve_targets_padding_and_native_branches(self):
        original, tables, positions, native = self.setup_patch_fixture()
        patched, plan = patch_evolutions(original, tables)
        self.assertEqual(plan["edit_count"], 15)
        self.assertEqual(plan["changed_rel_bytes"], 30)
        allowed = set()
        for source, target, _, _, method, condition in EVOLUTION_FIXES:
            p = positions[(source, target)]
            self.assertEqual(struct.unpack_from(">BBHH", patched, p), (method, 0xA5, condition, target))
            allowed.update((p, p + 2, p + 3))
        for p in native:
            self.assertEqual(original[p:p + 6], patched[p:p + 6])
        self.assertTrue(all(a == b for i, (a, b) in enumerate(zip(original, patched, strict=True)) if i not in allowed))
        self.assertEqual(evolution_families(original, tables), evolution_families(patched, tables))
        self.assertEqual(patch_evolutions(original, tables), (patched, plan))
        # All five Eevee branches have distinct item triggers, retaining targets.
        base = tables["species"]["offset"] + 133 * tables["species"]["stride"] + 0x9C
        conditions = [struct.unpack_from(">H", patched, base + slot * 6 + 2)[0] for slot in range(5)]
        self.assertEqual(len(set(conditions)), 5)

    def test_missing_changed_and_unrecognized_blocked_rules_are_rejected(self):
        original, tables, positions, _ = self.setup_patch_fixture()
        for kind in ("method", "condition", "target", "missing", "extra"):
            bad = bytearray(original)
            p = positions[(64, 65)]
            if kind == "method":
                bad[p] = 4
            elif kind == "condition":
                struct.pack_into(">H", bad, p + 2, 1)
            elif kind == "target":
                struct.pack_into(">H", bad, p + 4, 67)
            elif kind == "missing":
                bad[p:p + 6] = bytes(6)
            else:
                add_evolution(bad, tables, 65, 64, method=5, condition=0)
            with self.subTest(kind=kind), self.assertRaises(FormatError):
                patch_evolutions(bytes(bad), tables)


class UniqueShadowTests(unittest.TestCase):
    def setup_picks(self):
        data, tables = fixture(120)
        add_species(data, tables, range(1, 101))
        add_evolution(data, tables, 1, 2)
        add_evolution(data, tables, 1, 3, slot=1)
        # IDs 1 and 2 collide through siblings; every later winning family
        # must already be reserved when ID 2 is rerolled.
        picks = {1: 2, 2: 3, **{sid: sid + 1 for sid in range(3, 49)}}
        for sid in picks:
            p = tables["shadow"]["offset"] + sid * tables["shadow"]["stride"]
            struct.pack_into(">H", data, p + 2, 100)
        return bytes(data), tables, picks

    def test_reserves_later_winners_and_keeps_lowest_id(self):
        data, tables, picks = self.setup_picks()
        final, plan = unique_shadow_picks(data, tables, "family-seed", picks)
        mapping, _ = evolution_families(data, tables)
        used = {mapping[index] for sid, index in picks.items() if sid != 2}
        pool = [index for index in mapping if mapping[index] not in used]
        expected = choose_species("family-seed", "shadow-family-v3:2", pool, 100)
        self.assertEqual(final[1], 2)  # Evolved form is kept; no base-only filter.
        self.assertEqual(final[2], expected)
        self.assertEqual(plan["rerolled_shadow_ids"], [2])
        self.assertEqual(len({mapping[index] for index in final.values()}), 48)
        self.assertTrue(all(final[sid] == selected for sid, selected in picks.items() if sid != 2))
        self.assertEqual(picks[2], 3)  # Input mapping was not mutated.

    def test_seed_order_independence_and_repeatability(self):
        data, tables, picks = self.setup_picks()
        first = unique_shadow_picks(data, tables, "family-seed", picks)
        reverse = dict(reversed(list(picks.items())))
        self.assertEqual(first, unique_shadow_picks(data, tables, "family-seed", reverse))
        self.assertEqual(first, unique_shadow_picks(data, copy.deepcopy(tables), "family-seed", picks.copy()))
        self.assertNotEqual(first[0][2], unique_shadow_picks(data, tables, "another-seed", picks)[0][2])

    def test_fewer_than_48_families_and_invalid_picks_are_rejected(self):
        data, tables, picks = self.setup_picks()
        limited = copy.deepcopy(tables)
        limited["species"]["count"] = 49  # 48 nodes, one three-member family => 46 families.
        with self.assertRaises(FormatError):
            unique_shadow_picks(data, limited, "family-seed", picks)
        for bad in ({**picks, 1: 110}, {**picks, 1: 100}, {**picks, 1: 0},
                    {sid: species for sid, species in picks.items() if sid != 48}):
            with self.subTest(picks=bad.get(1)), self.assertRaises(FormatError):
                unique_shadow_picks(data, tables, "family-seed", bad)


if __name__ == "__main__":
    unittest.main()
