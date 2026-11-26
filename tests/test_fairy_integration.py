from dataclasses import replace
from collections import Counter
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.tm_rules import ORIGINAL_TM_MOVES
from orre_randomizer.fairy_data import compatibility
from orre_randomizer.fairy_gameplay import content_from_rows, fairy_gameplay_context, _layouts
from orre_randomizer.fairy_integration import apply_tm_gameplay, add_tm_shop_stock
from orre_randomizer.fairy_tms import ITEM_IDS, MOVE_IDS, prepare_candidate_moves, permute_compatibility
from orre_randomizer.options import Options
from tests.test_fairy_gameplay import fixture
from tests.test_fairy_tms import PATHS, ROOT


def source(game):
    original, tables, symbols, species, families, old_content = fixture(game)
    data = bytearray(original); stride = tables['species']['stride']; start = tables['species']['offset']
    for index in species:
        data[start + index * stride + 52:start + index * stride + 110] = bytes(i % 2 for i in range(58))
    original = bytes(data)
    content = content_from_rows(game, old_content.move_rows, original_rel=original,
        original_dol=old_content.original_dol, tables=tables)
    # Pure fixtures use the same move fields and counts, without pretending to
    # contain a retail REL relocation directory.
    symbols[62] = symbols[124]; symbols[63] = symbols[125]
    return original, tables, symbols, species, content


def apply(game, original, current, tables, symbols, content, options, seed='fairy-integration', **kwargs):
    with fairy_gameplay_context(content), patch('orre_randomizer.fairy_integration.parse_rel', return_value={}), \
            patch('orre_randomizer.fairy_integration.rel_symbols', return_value=symbols):
        return apply_tm_gameplay(original, current, content.original_dol, content.original_dol,
            seed, options, game, species_table=tables['species'], **kwargs)


class FairyTMGameplayContracts(unittest.TestCase):
    def test_original_mode_keeps_each_moves_compatibility_after_the_complete_permutation(self):
        for game in ('GC6P01', 'GXXP01'):
            original, tables, symbols, species, content = source(game)
            options = replace(Options.none(), randomize_tm_moves=True, tm_compatibility_mode='original')
            final, dol, report = apply(game, original, content.baseline_rel, tables, symbols, content, options)
            self.assertEqual(dol, content.original_dol)
            self.assertEqual(report['tm_count'], 57)
            self.assertEqual(set(report['tm_moves']), {*ORIGINAL_TM_MOVES, *MOVE_IDS})
            self.assertTrue(set(MOVE_IDS) & set(report['tm_moves'][:50]))
            for index, (national, *_rest) in species.items():
                pos = tables['species']['offset'] + index * tables['species']['stride'] + 52
                expected = permute_compatibility(original[pos:pos + 50], compatibility(national, method='learnable'), report['tm_plan'])
                self.assertEqual(final[pos:pos + 50], bytes(expected[:50]))
                self.assertEqual(report['extra_compatibility'][national], expected[50:])
                self.assertEqual(final[pos + 50:pos + 58], original[pos + 50:pos + 58])
            allowed = {tables['species']['offset'] + index * tables['species']['stride'] + 52 + column
                for index in species for column in range(50)}
            self.assertTrue(all(a == b or index in allowed for index, (a, b) in enumerate(zip(content.baseline_rel, final))))
            self.assertFalse(report['offensive_guarantee']['applied'])
            with self.assertRaises(FormatError):
                apply(game, original, final, tables, symbols, content, options)

    def test_universal_mode_preserves_retained_and_unselected_species_by_move(self):
        game = 'GXXP01'
        original, tables, symbols, species, content = source(game)
        options = replace(Options.none(), randomize_tm_moves=True, tm_compatibility_mode='universal')
        final, _, report = apply(game, original, content.baseline_rel, tables, symbols, content, options,
            preserve_species={35}, selected_species={35, 394})
        for index, (national, *_rest) in species.items():
            pos = tables['species']['offset'] + index * tables['species']['stride'] + 52
            columns = (*final[pos:pos + 50], *report['extra_compatibility'][national])
            if index == 394:
                self.assertEqual(columns, (1,) * 57)
            else:
                self.assertEqual(columns, permute_compatibility(original[pos:pos + 50],
                    compatibility(national, method='learnable'), report['tm_plan']))

    def test_type_mode_uses_final_types_and_guarantees_offense_without_overriding_retained(self):
        for game in ('GC6P01', 'GXXP01'):
            original, tables, symbols, species, content = source(game)
            current = bytearray(content.baseline_rel)
            for index in species:
                pos = tables['species']['offset'] + index * tables['species']['stride']
                current[pos + 48:pos + 50] = bytes((10, 10))
            options = replace(Options.none(), tm_compatibility_mode='type', tm_ensure_offensive=True)
            final, _, report = apply(game, original, bytes(current), tables, symbols, content, options,
                preserve_species={35})
            self.assertEqual(len(report['offensive_guarantee']['added']), 385)
            self.assertTrue(all(not row['matches_type'] for row in report['offensive_guarantee']['added']))
            self.assertTrue(all(row['types'] == [10, 10] for row in report['compatibility']))
            for index, (national, *_rest) in species.items():
                pos = tables['species']['offset'] + index * tables['species']['stride'] + 52
                columns = (*final[pos:pos + 50], *report['extra_compatibility'][national])
                if index != 35: self.assertEqual(sum(columns), 1)

    def test_random_mode_is_reproducible_and_respects_boolean_options(self):
        original, tables, symbols, _, content = source('GC6P01')
        options = replace(Options.none(), randomize_tm_moves=True, tm_compatibility_mode='random')
        args = ('GC6P01', original, content.baseline_rel, tables, symbols, content, options)
        first = apply(*args)
        self.assertEqual(first, apply(*args))
        self.assertNotEqual(first[0], apply(*args, seed='another-seed')[0])
        with self.assertRaises(ValueError): apply(*args, preserve_species={9999})
        with self.assertRaises(FormatError):
            apply('GXXP01', original, content.baseline_rel, tables, symbols, content, options)
        with self.assertRaises(FormatError):
            apply_tm_gameplay(original, original, content.original_dol, content.original_dol,
                'seed', options, 'GC6P01', species_table=tables['species'])


@unittest.skipUnless(all(p.is_file() for p in PATHS.values()), 'requires private regional DOLs')
class FairyTMGameplayRetail(unittest.TestCase):
    def test_guaranteed_extra_tms_preserve_stock_and_fit_all_six_retails_with_stones_and_randomization(self):
        from orre_randomizer.engine.analyze_game import parse_fsys
        from orre_randomizer.engine.rebuild_iso import decoded_member
        from orre_randomizer.engine.item_rules import patch_cash_shops, patch_item_archive, SHOP_LAYOUT
        from orre_randomizer.engine.shop_stones import patch_rel, read_shops
        from orre_randomizer.xd_shops import patch_stone_stock, shop_layout
        from orre_randomizer.xd_item_rules import apply_shop_items
        for game, dp in PATHS.items():
            with self.subTest(game=game):
                xd = game.startswith('GXX'); region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
                tag = {'eu': 'pal', 'us': 'usa', 'jp': 'japan'}[region]
                sp = ROOT / (f'build/xd-shop-research/{region}/files/pocket_menu.fsys' if xd else
                    f'build/region-compat-2026-11-02/rel-research/{tag}/pocket_menu.fsys')
                rp = ROOT / (f'build/xd-validation/{region}/common_rel' if xd else
                    f'build/region-compat-2026-11-02/rel-research/{tag}/common.fsys-common_rel.rel')
                if not sp.is_file() or not rp.is_file(): self.skipTest('requires private regional shop/common archives')
                archive = sp.read_bytes(); native = decoded_member(archive, parse_fsys(archive)['members'][0])
                rel, dol = rp.read_bytes(), dp.read_bytes()
                candidate = prepare_candidate_moves(rel, game,
                    move_message_ids={move: (0xF0440 + 2 * i, 0xF0441 + 2 * i) for i, move in enumerate(MOVE_IDS)})
                content = content_from_rows(game, candidate['move_rows'], original_rel=rel, original_dol=dol)
                layout = shop_layout(native, game) if xd else SHOP_LAYOUT
                targets = (6, 14, 15) if xd else (3,)
                for stones in (False, True):
                    base = (patch_stone_stock(native, game)[0] if xd else patch_rel(native)[0]) if stones else native
                    for randomize in (False, True):
                        for seed in ('fairy-shop-a', 'fairy-shop-b', 'étoile'):
                            options = replace(Options.none(), enable_fairy_type=True,
                                randomize_shop_items=randomize, shop_keep_capture_items=True)
                            with fairy_gameplay_context(content):
                                current = (apply_shop_items(rel, base, game, seed, options)[0] if xd else
                                    patch_cash_shops(base, dol, seed, options)[0]) if randomize else base
                                final, report = add_tm_shop_stock(native, current, game)
                                self.assertEqual(add_tm_shop_stock(native, final, game)[0], final)
                                if not xd:
                                    patched, archive_report = patch_item_archive(archive, dol, seed,
                                        replace(options, stones_phenac=stones, stones_pyrite=stones))
                                    self.assertEqual(decoded_member(patched, parse_fsys(patched)['members'][0]), final)
                                    self.assertTrue(archive_report['fairy_tms']['original_stock_preserved'])
                            self.assertLessEqual(report['packed_entries'], layout['item_count'])
                            self.assertEqual(len(final), len(native))
                            before, after = read_shops(current, layout), read_shops(final, layout)
                            for index, (old, new) in enumerate(zip(before, after)):
                                self.assertEqual((old['type'], old['subtype']), (new['type'], new['subtype']))
                                expected = Counter(old['items'])
                                if index in targets:
                                    for item in ITEM_IDS: expected[item] = max(1, expected[item])
                                    self.assertTrue(set(ITEM_IDS) <= set(new['items']))
                                else:
                                    self.assertEqual(old['items'], new['items'])
                                self.assertEqual(Counter(new['items']), expected)
                with self.assertRaises(FormatError): add_tm_shop_stock(b'foreign source', native, game)
                self.assertEqual(sp.read_bytes(), archive)

    def test_all_six_retail_baselines_keep_hms_and_defer_dol_move_writes(self):
        for game, dp in PATHS.items():
            with self.subTest(game=game):
                xd = game.startswith('GXX'); region = {'P': 'eu', 'E': 'us', 'J': 'jp'}[game[3]]
                rp = ROOT / (f'build/xd-validation/{region}/common_rel' if xd else
                    f'build/region-compat-2026-11-02/rel-research/{ {"eu":"pal", "us":"usa", "jp":"japan"}[region] }/common.fsys-common_rel.rel')
                if not rp.is_file(): self.skipTest('requires private regional RELs')
                original, dol = rp.read_bytes(), dp.read_bytes()
                candidates = prepare_candidate_moves(original, game,
                    move_message_ids={move: (0xF0440 + 2 * i, 0xF0441 + 2 * i) for i, move in enumerate(MOVE_IDS)})
                content = content_from_rows(game, candidates['move_rows'], original_rel=original, original_dol=dol)
                tables = _layouts(original, game)
                options = replace(Options.none(), randomize_tm_moves=True, tm_compatibility_mode='universal')
                with fairy_gameplay_context(content):
                    final, unchanged_dol, report = apply_tm_gameplay(original, content.baseline_rel, dol, dol,
                        'retail-integration', options, game, species_table=tables['species'])
                self.assertEqual(unchanged_dol, dol)
                self.assertEqual(len(report['extra_compatibility']), 386)
                self.assertTrue(all(values == (1,) * 7 for values in report['extra_compatibility'].values()))
                for row in report['compatibility']:
                    pos = tables['species']['offset'] + row['species'] * tables['species']['stride'] + 52
                    self.assertEqual(final[pos:pos + 50], bytes([1] * 50))
                    self.assertEqual(final[pos + 50:pos + 58], original[pos + 50:pos + 58])
                self.assertEqual(rp.read_bytes(), original); self.assertEqual(dp.read_bytes(), dol)


if __name__ == '__main__':
    unittest.main()
