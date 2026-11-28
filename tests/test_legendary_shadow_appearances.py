"""Test the derived artwork and specimen-only preview routes."""
from io import BytesIO
import re
import struct
import unittest

from PIL import Image

from orre_randomizer.artwork import _png_pixels
from orre_randomizer.deoxys import DEOXYS
from orre_randomizer.deoxys_identity import FORM_OFFSETS, FORM_TAG
from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL
from orre_randomizer.legendary_shadow_assets import (PACK, SPECIES, STEMS, decorate_preview, dna,
                                                    face, hd_material, hd_materials, manifest, portrait, stem_for)
from orre_randomizer.legendary_shadow_rom import MODEL_KEY, FACE_KEY, Route
from orre_randomizer.legendary_shadow_runtime import _record_selector
from orre_randomizer.model_portraits import violet_backdrop
from tests.test_xd_shadow_shinies import ADDRESS, WrapperMachine


class LegendaryShadowSelectorTests(unittest.TestCase):
    def test_every_registered_form_follows_both_purification_policies(self):
        routes = tuple(Route(species, form, STEMS.index(stem_for(species, form)), 1)
                       for species in SPECIES for form in range(4 if species == DEOXYS else 1))
        self.assertEqual(len(routes), len(STEMS))
        record, predicate = 0x80600000, 0x80144400
        for family in ('colosseum', 'xd'):
            xd = family == 'xd'
            for keep in (False, True):
                selector = _record_selector(ADDRESS, routes, xd=xd, keep=keep, predicate=predicate)
                for route in routes:
                    for purified in (False, True):
                        with self.subTest(game=family, keep=keep, route=route.index, purified=purified):
                            machine = WrapperMachine(selector)
                            machine.reg[3] = record
                            machine.store(record, route.species, 2)
                            machine.store(record + FORM_OFFSETS[family], FORM_TAG | route.form, 2)
                            machine.store(record + (0xBA if xd else 0xD8), 11, 2)
                            if not xd:
                                machine.store(record + 0xDC, 0xFFFFFF9C if purified else 2000, 4)

                            def status(guest):
                                self.assertEqual(guest.reg[3], record)
                                guest.clobber_volatile()
                                guest.reg[3] = int(not purified)

                            machine.callbacks = {predicate: status}
                            machine.run(max_steps=250)
                            self.assertEqual(machine.reg[3], route.model_key if keep or not purified else 0)

    def test_display_selection_is_per_record_and_keeps_deoxys_form(self):
        routes = (Route(243, 0, 2, 1), *(Route(DEOXYS, form, 3 + form, 2) for form in range(4)))
        record, predicate = 0x80600000, 0x80144400
        for xd in (False, True):
            for keep, shadow_id, purified, expected in (
                (False, 0, False, 0), (True, 0, False, 0), (False, 8, False, MODEL_KEY + 6),
                (False, 8, True, 0), (True, 8, True, MODEL_KEY + 6), (True, 97, False, 0),
            ):
                with self.subTest(xd=xd, keep=keep, shadow_id=shadow_id, purified=purified):
                    machine = WrapperMachine(_record_selector(ADDRESS, routes, xd=xd, keep=keep,
                                                              predicate=predicate))
                    machine.reg[3] = record
                    machine.store(record, DEOXYS, 2)
                    machine.store(record + (0x0C if xd else 0xD2), 0xDEC3, 2)
                    machine.store(record + (0xBA if xd else 0xD8), shadow_id, 2)
                    if not xd:
                        machine.store(record + 0xDC, 0xFFFFFF9C if purified else 2000, 4)

                    def status(guest):
                        self.assertEqual(guest.reg[3], record)
                        guest.clobber_volatile()
                        guest.reg[3] = int(not purified)

                    machine.callbacks = {predicate: status}
                    before = {address: byte for address, byte in machine.memory.items()
                              if record <= address < record + 0x138}
                    machine.run()
                    self.assertEqual(machine.reg[3], expected)
                    self.assertEqual(before, {address: byte for address, byte in machine.memory.items()
                                              if record <= address < record + 0x138})


@unittest.skipUnless(PACK.is_file(), 'bundled original-scale legendary appearance pack')
class LegendaryShadowAssetsTests(unittest.TestCase):
    def test_all_generations_and_deoxys_forms_are_registered(self):
        self.assertEqual(set(SPECIES.values()) | {249}, LEGENDARY_NATIONAL)
        self.assertEqual([stem_for(DEOXYS, i) for i in range(4)], ['386', '386-attack', '386-defense', '386-speed'])
        self.assertEqual(len(manifest()), 92)
        keys = {base for i, _ in enumerate(STEMS)
                for base in (Route(0, 0, i, 1).model_key, Route(0, 0, i, 1).face_key(False),
                             Route(0, 0, i, 1).face_key(True))}
        self.assertEqual(len(keys), len(STEMS) * 3)
        self.assertIn(MODEL_KEY, keys)
        self.assertIn(FACE_KEY, keys)

    def test_native_portrait_masks_and_hd_sizes(self):
        for game in ('colosseum', 'xd'):
            backdrops = {hd: violet_backdrop(game=game, scale=4 if hd else 1)
                         for hd in (False, True)}
            for stem in STEMS:
                self.assertNotEqual(face(game, stem), b'')
                for hd in (False, True):
                    self.assertNotEqual(portrait(game, stem, False, hd=hd), portrait(game, stem, True, hd=hd))
                    for shiny in (False, True):
                        with Image.open(BytesIO(portrait(game, stem, shiny, hd=hd))) as png:
                            self.assertEqual(png.size, (168, 168) if hd else (42, 42))
                            pixels = png.convert('RGBA').tobytes()
                            same_backdrop = backdrops[hd]
                            self.assertEqual(pixels[3::4], same_backdrop[3::4])
                            self.assertTrue(any(
                                pixels[at:at + 4] == same_backdrop[at:at + 4]
                                for at in range(0, len(pixels), 4) if same_backdrop[at + 3] == 255
                            ), (game, stem, shiny, hd))
        for stem in STEMS:
            for shiny in (False, True):
                self.assertEqual(len(_png_pixels(dna(stem, shiny), (64, 64))), 64 * 64 * 4)
                with Image.open(BytesIO(dna(stem, shiny, hd=True))) as png:
                    self.assertEqual(png.size, (256, 256))

    def test_revised_portraits_keep_the_red_iris_in_both_palettes(self):
        for game in ('colosseum', 'xd'):
            moltres_eye = (34, 18) if game == 'colosseum' else (30, 20)
            for stem, (x, y) in (('144', (25, 21)), ('146', moltres_eye), ('151', (24, 20))):
                for scale in (1, 4):
                    with self.subTest(game=game, stem=stem, scale=scale):
                        center = (x * scale + scale // 2, y * scale + scale // 2)
                        colors = []
                        for shiny in (False, True):
                            artwork = portrait(game, stem, shiny, hd=scale == 4)
                            with Image.open(BytesIO(artwork)) as png:
                                colors.append(png.convert('RGBA').getpixel(center))
                        self.assertEqual(*colors)
                        red, green, blue, alpha = colors[0]
                        self.assertEqual(alpha, 255)
                        self.assertGreater(red - max(green, blue), 120)

    def test_preview_uses_the_saved_form_and_only_decorates_shadow_rows(self):
        pure_species = {'species': DEOXYS, 'deoxys_form': 3, 'shiny': True, 'portrait_png': b'native'}
        shadow = dict(pure_species, shadow_id=7)
        decorate_preview(pure_species, 'xd', STEMS)
        decorate_preview(shadow, 'xd', ())
        self.assertEqual(pure_species['portrait_png'], b'native')
        self.assertEqual(shadow['portrait_png'], b'native')
        decorate_preview(shadow, 'xd', STEMS)
        self.assertEqual(shadow['portrait_png'], portrait('xd', '386-speed', True))

    def test_model_materials_include_validated_four_times_artwork_for_each_game(self):
        for game in ('colosseum', 'xd'):
            materials = hd_materials(game)
            self.assertTrue(materials)
            for key in materials:
                width, height = map(int, re.match(r'tex1_(\d+)x(\d+)_', key).groups())
                png, source = hd_material(game, key)
                self.assertEqual(struct.unpack_from('>II', png, 16), (width * 4, height * 4))
                self.assertEqual(len(source['donor_sha256']), 64)
