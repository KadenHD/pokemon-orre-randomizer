"""Execute Deoxys keypad selection against saved PID and owned form changes."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.deoxys_identity import FORM_TAG
from orre_randomizer.engine.dna_deoxys_keypad import _keypad_hook, apply_deoxys_keypad_runtime
from orre_randomizer.engine.dna_keypad import (
    DNA_KEYPAD_SPECIES, _ATLAS_DESCRIPTOR, _ATLAS_OFFSET, _ATLAS_SIGNATURE,
    _KEYPAD_DAT_SIZE, _SPINDA_KEYPAD_MARKER, _TILE_ORIGINS, _atlas_block_offset)
from orre_randomizer.engine.dna_keypad_runtime import _ATLAS_BYTES
from orre_randomizer.engine.dol_regions import PAL
from orre_randomizer.engine.gift_move_hooks import branch
from orre_randomizer.engine.postgame_lugia_model import _SAVED_IDENTITIES
from tests.test_lugia_dna import DAT, PLAYER, OWNER, personality
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


READER = 0x80400000
READERS = _SAVED_IDENTITIES[PAL.game_id]


class DeoxysKeypadTests(unittest.TestCase):
    def execute(self, *, generated, form, shiny, marker=_SPINDA_KEYPAD_MARKER, chained=False):
        parser, flush, invalidate = 0x801962D8, 0x8009E7F8, 0x800BE89C
        tiles = {153: tuple(bytes((variant + 1,)) * 8192 for variant in range(8))}
        payload = _keypad_hook(ADDRESS, parser, ADDRESS - 0x100 if chained else None,
            flush, invalidate, PAL, {153: (19, 3)}, {153: (410, not shiny)}, tiles, READER)
        machine = WrapperMachine(payload)
        machine.reg[3:6] = [0x80700000, DAT, _KEYPAD_DAT_SIZE]
        machine.store(DAT + 0x18, marker, 4)
        for offset, value in enumerate(_ATLAS_SIGNATURE):
            machine.store(DAT + _ATLAS_DESCRIPTOR + offset * 4, value, 4)
        machine.store(PAL.player_pointer, PLAYER, 4)
        machine.store(PLAYER + 0x9C, OWNER, 4)
        machine.store(parser + 4, branch(parser + 4, RETURN), 4)
        if chained:
            machine.store(ADDRESS - 0x100, branch(ADDRESS - 0x100, RETURN), 4)

        def getter(value):
            def call(m):
                self.assertEqual(m.reg[3], 19)
                m.clobber_volatile()
                m.reg[3] = value
            return call

        def owned(m):
            pointer = m.reg[3]
            self.assertEqual(m.load(pointer, 2), 410)
            self.assertEqual(m.load(pointer + 0xD8, 2), 19)
            self.assertEqual(m.load(pointer + 0xD2, 2), FORM_TAG | 3)
            self.assertEqual(m.load(pointer + 4, 4), personality(shiny) if generated else 0)
            self.assertEqual(m.load(pointer + 0x14, 4), OWNER if generated else 0)
            m.clobber_volatile()
            m.reg[3] = form

        def cache_flush(m):
            self.assertEqual(m.reg[3:5], [DAT + _ATLAS_OFFSET, _ATLAS_BYTES])
            m.clobber_volatile()

        machine.callbacks = {READERS[0]: getter(personality(shiny)), READERS[1]: getter(int(generated)),
            READER: owned, flush: cache_flush, invalidate: lambda m: m.clobber_volatile()}
        before = machine.reg.copy()
        saved = {p: machine.memory.get(p) for p in range(PLAYER, PLAYER + 0x100)}
        machine.run(max_steps=22000)
        self.assertEqual(machine.reg[3:6], before[3:6])
        self.assertEqual(machine.reg[13:], before[13:])
        self.assertEqual(machine.reg[1], before[1] if chained else before[1] - 0x20)
        self.assertEqual(saved, {p: machine.memory.get(p) for p in saved})
        return machine, tiles

    def test_all_eight_saved_forms_and_palettes_replace_only_the_requested_native_cell(self):
        for form in range(4):
            for shiny in (False, True):
                for generated in (False, True):
                    with self.subTest(form=form, shiny=shiny, generated=generated):
                        machine, tiles = self.execute(generated=generated, form=form, shiny=shiny)
                        origin = DAT + _atlas_block_offset(*_TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(153)])
                        image = b''.join(bytes(machine.memory[origin + row * 4096 + col]
                            for col in range(512)) for row in range(16))
                        self.assertEqual(image, tiles[153][form * 2 + int(shiny if generated else not shiny)])
                        for row in range(16):
                            self.assertNotIn(origin + row * 4096 - 1, machine.memory)
                            self.assertNotIn(origin + row * 4096 + 512, machine.memory)

    def test_changed_form_is_bounded_and_parser_can_chain_without_replaying_the_prologue(self):
        machine, tiles = self.execute(generated=True, form=99, shiny=False, chained=True)
        origin = DAT + _atlas_block_offset(*_TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(153)])
        self.assertEqual(machine.load(origin, 1), tiles[153][6][0])

    def test_unrelated_dat_never_reads_saved_data_or_writes_a_tile(self):
        machine, _ = self.execute(generated=True, form=1, shiny=True, marker=0)
        self.assertFalse(machine.calls)

    def test_empty_mapping_is_an_exact_noop_without_reading_any_input(self):
        current = b'caller owned current executable'
        output, report = apply_deoxys_keypad_runtime(None, current, None, {}, None, deoxys_reader=None)
        self.assertIs(output, current)
        self.assertFalse(report['active'])


class NativeDeoxysKeypadAssetsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.folder = self.root / 'game/files'
        if not all((self.folder / name).is_file() for name in ('DNA_key.fsys', 'poke_body.fsys')):
            self.skipTest('requires local original keypad and full-body archives')
        self.read = lambda name: (self.folder / name).read_bytes()
        self.appearances = {old: (410 if old == 153 else old, False) for old in DNA_KEYPAD_SPECIES}

    def test_all_eight_authentic_tiles_and_initial_extra_form_share_the_exact_native_composition(self):
        from orre_randomizer.engine.dna_deoxys_keypad import native_tile_variants
        from orre_randomizer.engine.dna_keypad import patch_dna_keypad, _tile_rows
        from orre_randomizer.engine.analyze_game import parse_fsys
        from orre_randomizer.engine.rebuild_iso import decoded_member
        source, bodies = self.read('DNA_key.fsys'), self.read('poke_body.fsys')
        variants = native_tile_variants(self.read, self.appearances, {153: (19, 2)})[153]
        self.assertEqual(len({hashlib.sha256(tile).digest() for tile in variants}), 8)
        for form in range(4):
            appearances = dict(self.appearances)
            for shiny in (False, True):
                appearances[153] = (410, shiny)
                output = patch_dna_keypad(source, bodies, appearances, deoxys_samples={153: (19, form)})
                member = next(r for r in parse_fsys(output)['members'] if r['identifier_raw'] == '0x107e0200')
                dat = decoded_member(output, member)
                self.assertEqual(int.from_bytes(dat[0x18:0x1C], 'big'), _SPINDA_KEYPAD_MARKER)
                encoded = b''.join(dat[a:b] for a, b in _tile_rows(*_TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(153)]))
                self.assertEqual(encoded, variants[form * 2 + int(shiny)])
        self.assertEqual(source, self.read('DNA_key.fsys'))
        self.assertEqual(bodies, self.read('poke_body.fsys'))

    def test_all_three_region_dols_chain_readers_and_reserve_all_eight_variants(self):
        from orre_randomizer.deoxys_display import install_display_reader
        from orre_randomizer.engine.dol_regions import dol_layout
        from orre_randomizer.engine.analyze_game import parse_dol
        sources = [self.root / 'game/sys/main.dol'] + [
            self.root / 'build/region-compat-2026-11-02/dol-research' / (name + '-main.dol')
            for name in ('usa', 'japan')]
        if not all(path.is_file() for path in sources):
            self.skipTest('requires local three-region original DOL extracts')
        for path in sources:
            original = path.read_bytes()
            game = dol_layout(original).game_id
            reader_dol, reader = install_display_reader(original, original, game)
            output, report = apply_deoxys_keypad_runtime(original, reader_dol, self.read,
                {153: (19, 2)}, self.appearances, deoxys_reader=reader['address'])
            self.assertEqual(report['variants_per_cell'], 8)
            self.assertGreater(len(output) - len(reader_dol), 8 * 8192)
            parse_dol(output)
            self.assertEqual(original, path.read_bytes())

    def test_hd_cells_register_eight_additive_forms_without_enumerating_cross_products(self):
        from orre_randomizer import hd_overlays as hd
        from orre_randomizer.engine.dna_hd_tiles import split_keypad_archive
        from orre_randomizer.engine.dna_keypad import patch_dna_keypad
        from orre_randomizer.engine.analyze_game import parse_fsys
        from orre_randomizer.engine.rebuild_iso import decoded_member
        source = patch_dna_keypad(self.read('DNA_key.fsys'), self.read('poke_body.fsys'),
            self.appearances, deoxys_samples={153: (19, 2)})
        split, layout = split_keypad_archive(source)
        dat = decoded_member(split, next(r for r in parse_fsys(split)['members'] if r['identifier_raw'] == '0x107e0200'))
        context = {'dna_lab': {str(old): {'species': species, 'shiny': shiny}
                              for old, (species, shiny) in self.appearances.items()},
                   'dna_deoxys_samples': {'153': [19, 2]}}
        with patch('orre_randomizer.artwork._disc_files', side_effect=lambda _, wanted:
                   {name: self.read(name) for name in wanted}):
            textures, recipes = hd._dna_cell_variants(dat, layout, Path('unused.iso'), context, None)
        self.assertEqual(len(textures), 16)  # eight unchanged keys + eight variants of one cell
        deoxys = [r for r in recipes.values() if (r['transform'].get('tile') or {}).get('species') == 410]
        self.assertEqual(len(deoxys), 8)
        self.assertEqual({r['transform']['tile']['deoxys_form'] for r in deoxys}, {0, 1, 2, 3})
        self.assertEqual(sum(r['transform']['tile']['body']['kind'] == 'rendered-deoxys' for r in deoxys), 6)

        # The collector must recognize the custom bodies' XD source dependency;
        # they intentionally do not pretend to be a retail full-body texture.
        with tempfile.TemporaryDirectory() as temporary:
            iso = Path(temporary) / 'fixture.iso'
            iso.write_bytes(b'GC6P01' + bytes(256))
            with patch.object(hd, '_disc_archives', return_value=[('DNA_key.fsys', split)]), \
                 patch('orre_randomizer.artwork._disc_files', side_effect=lambda _, wanted:
                       {name: self.read(name) for name in wanted}):
                report = hd.capture_native_assets(iso, Path(temporary) / 'Textures',
                    reference_iso=iso, asset_context=dict(context, dna_hd_layout=layout))
            self.assertIn('xd', report['required_packs'])


class RegisteredDeoxysDnaHdTests(unittest.TestCase):
    def test_hd_bodies_use_the_256px_capture_and_reject_an_older_registry(self):
        from orre_randomizer import hd_overlays as hd
        from orre_randomizer.deoxys_assets import body_pixels
        from orre_randomizer.engine.dna_artwork import outline_dna_body
        for form, label in enumerate(('attack', 'defense', 'speed'), 1):
            for shiny in (False, True):
                source = hd._deoxys_body_origin(form, shiny)
                image, provenance = hd._rendered_deoxys_body(source)
                self.assertEqual((image.width(), image.height()), (256, 256))
                self.assertEqual(bytes(image.constBits()), outline_dna_body(body_pixels(label, shiny, hd=True), 256))
                self.assertFalse(provenance['native_bitmap_upscaled_for_hd'])
                with self.assertRaises(hd.OverlayError):
                    hd._rendered_deoxys_body(dict(source, asset_registry_sha256='0' * 64))


if __name__ == '__main__':
    unittest.main()
