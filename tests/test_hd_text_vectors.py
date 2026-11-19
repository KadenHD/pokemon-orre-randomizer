import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.hd_text import Glyph, build_native_pages
from orre_randomizer.hd_text_symbols import _RECIPES, symbol_recipe
from orre_randomizer.hd_text_vectors import (FONT_SHA256, LICENSE_SHA256, ink_bounds, render_vector_pages,
                                           unicode_cmap, native_padding, measure_vector_layout)

FONTS = Path(__file__).resolve().parents[1] / "orre_randomizer/assets/game/fonts"


class VectorGlyphs(unittest.TestCase):
    def test_exact_fullwidth_currency_aliases_keep_pokedollar_semantics(self):
        entries = {key: value for key, value in _RECIPES.items() if value[0] == 0xFF04}
        self.assertEqual(len(entries), 4)
        for sha in entries:
            self.assertEqual(symbol_recipe({"code": 0xFF04, "samples_sha256": sha}), ("pokedollar", ""))
        with self.assertRaises(FormatError):
            symbol_recipe({"code": 0xFF04, "samples_sha256": "0" * 64})

    def test_unsupported_pillow_is_rejected_before_native_padding(self):
        glyph=self.glyph('A',5,5,0,(0,0,5,5))
        with patch('orre_randomizer.hd_text_vectors.PILLOW_VERSION','11.2.1'):
            with self.assertRaisesRegex(FormatError,'Pillow13'):
                native_padding([glyph])

    def test_bundled_source_license_and_real_cmap_latin_japanese_are_pinned(self):
        data = (FONTS / "NotoSansJP.ttf").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), FONT_SHA256)
        self.assertEqual(hashlib.sha256((FONTS / "OFL-NotoSansJP.txt").read_bytes()).hexdigest(), LICENSE_SHA256)
        codes = unicode_cmap(data)
        self.assertTrue({ord(c) for c in "AÉèßñ漢字あカ♀♂♪"} <= codes)
        self.assertNotIn(0xFFFF, codes)
        with self.assertRaises(FormatError):
            unicode_cmap(data[:100])

    def test_native_bitmap_is_only_a_metric_guide_not_artwork(self):
        outputs = []
        for samples in (b"\xFF\xFF\xF0" * 5,
                        b"\xF0\x00\xF0" + b"\x00\x00\x00" * 3 + b"\xF0\x00\xF0"):
            glyph = Glyph(0, ord("A"), 5, 5, 0, samples, "math", 0)
            margins, _ = native_padding([glyph])
            pages, plan = build_native_pages([glyph], padding_by_identity=margins)
            self.assertEqual(ink_bounds(pages[0], plan["glyphs"][0]), (0, 0, 5, 5))
            images, report = render_vector_pages(pages, plan, FONTS / "NotoSansJP.ttf", FONTS / "OFL-NotoSansJP.txt")
            self.assertTrue(report["hd_ready"])
            self.assertFalse(report["native_bitmap_used_as_artwork"])
            outputs.append(images[0].tobytes())
            bad = dict(plan["glyphs"][0], x=3)
            with self.assertRaises(FormatError):
                ink_bounds(pages[0], bad)
            bad = dict(plan["glyphs"][0], samples_sha256="0" * 64)
            with self.assertRaises(FormatError):
                ink_bounds(pages[0], bad)
        self.assertEqual(outputs[0], outputs[1])

    def test_game_symbols_are_sha_qualified_and_do_not_become_unicode_boxes(self):
        sha = next(sha for sha, row in _RECIPES.items() if row[:2] == [0x25A1, "boxed-s"])
        self.assertEqual(symbol_recipe({"code": 0x25A1, "samples_sha256": sha}), ("boxed-s", ""))
        with self.assertRaises(FormatError):
            symbol_recipe({"code": 0x25A1, "samples_sha256": "0" * 64})
        greek = next(sha for sha, row in _RECIPES.items() if row[0] == 0x3B1 and row[1] == "unicode")
        custom = next(sha for sha, row in _RECIPES.items() if row[0] == 0x3B1 and row[1] == "eplus")
        self.assertEqual(symbol_recipe({"code": 0x3B1, "samples_sha256": greek}), ("unicode", "α"))
        self.assertEqual(symbol_recipe({"code": 0x3B1, "samples_sha256": custom}), ("eplus", ""))

    def test_vector_source_mask_cache_has_a_fixed_residency_limit(self):
        glyphs = [Glyph(0, code, 3, 3, 0, b"\xFF\xF0" * 3, "math", 0) for code in (65, 66, 67)]
        margins, _ = native_padding(glyphs)
        pages, plan = build_native_pages(glyphs, padding_by_identity=margins)
        with patch("orre_randomizer.hd_text_vectors.MAX_CACHED_MASKS", 2):
            _, report = render_vector_pages(pages, plan, FONTS / "NotoSansJP.ttf", FONTS / "OFL-NotoSansJP.txt")
        self.assertEqual(report["peak_cached_vector_masks"], 2)
        self.assertGreaterEqual(report["vector_mask_cache_evictions"], 1)

    @staticmethod
    def glyph(code, width, height, offset, bounds, font_id=0):
        data = bytearray(((width + 1) // 2) * height)
        for y in range(bounds[1], bounds[3]):
            for x in range(bounds[0], bounds[2]):
                data[y * ((width + 1) // 2) + x // 2] |= 15 << (4 if x % 2 == 0 else 0)
        return Glyph(font_id, ord(code), width, height, offset, bytes(data), "metric-only fixture", 0)

    def alphabet(self):
        return [self.glyph('H',15,22,7,(1,0,13,15)),self.glyph('E',13,22,7,(1,0,12,16)),
                self.glyph('I',6,22,7,(0,0,5,15)),self.glyph('x',11,22,12,(0,0,10,10)),
                self.glyph('g',11,22,11,(0,0,11,14)),self.glyph('p',12,22,11,(0,1,10,14)),
                self.glyph('É',13,22,3,(1,0,12,20))]

    def test_shared_grid_aligns_cap_xheight_descenders_and_accented_base(self):
        from PIL import Image
        glyphs = self.alphabet()
        margins, layout = native_padding(glyphs)
        self.assertEqual(set(layout["styles"]), {"0:latin"})
        self.assertTrue(layout["styles"]["0:latin"]["native_y_offset_is_not_a_size"])
        pages, plan = build_native_pages(glyphs, padding_by_identity=margins)
        output, report = render_vector_pages(pages, plan, FONTS/"NotoSansJP.ttf", FONTS/"OFL-NotoSansJP.txt")
        self.assertTrue(report["hd_ready"])
        self.assertFalse(report["per_glyph_horizontal_projection"])
        self.assertFalse(report["per_glyph_vertical_fit"])
        lines = {}
        for row in plan["glyphs"]:
            box=(row['draw_x']*4,row['draw_y']*4,(row['draw_x']+row['draw_width'])*4,
                 (row['draw_y']+row['draw_height'])*4)
            alpha=output[row['page']].getchannel('A').crop(box)
            line=Image.new('L',(120,180))
            l,t,_,_=row['padding_ltrb']
            line.paste(alpha,((12-l)*4,(row['y_offset']-t)*4))
            lines[chr(row['code'])]=line
        self.assertLessEqual(abs(lines['H'].getbbox()[3]-lines['x'].getbbox()[3]),1)
        self.assertGreater(lines['g'].getbbox()[3],lines['H'].getbbox()[3]+4)
        self.assertLess(lines['É'].getbbox()[1],lines['E'].getbbox()[1])
        # E and É keep the same actual base letter, not a separately shrunk E.
        baseline=report['styles']['0:latin']['baseline']
        captop=report['styles']['0:latin']['y_knots'][1][1]
        region=(0,int(captop*4)+3,120,int(baseline*4)-2)
        self.assertEqual(lines['E'].crop(region).tobytes(),lines['É'].crop(region).tobytes())
        # Compare the opaque shape, rather than the Lanczos1/255 support
        # fringe which adds the same few pixels to narrow and wide outlines.
        core_i=lines['I'].point(lambda value:255 if value>=128 else 0).getbbox()
        core_h=lines['H'].point(lambda value:255 if value>=128 else 0).getbbox()
        # Shapes follow one Noto X scale, not the native I/H paint ratio5/12.
        from PIL import ImageFont
        font=ImageFont.truetype(str(FONTS/'NotoSansJP.ttf'),512)
        font.set_variation_by_axes([700])
        ibox,hbox=font.getmask('I').getbbox(),font.getmask('H').getbbox()
        expected=(ibox[2]-ibox[0])/(hbox[2]-hbox[0])
        self.assertAlmostEqual((core_i[2]-core_i[0])/(core_h[2]-core_h[0]),expected,delta=.08)
        self.assertTrue(report['styles']['0:latin']['shared_vertical_transform'])
        self.assertTrue(report['styles']['0:latin']['shared_transform'])

    def test_common_shape_scale_centers_cells_and_keeps_native_advance(self):
        from orre_randomizer.hd_text_vectors import _layout, _raster_letter
        from orre_randomizer.hd_text_layout import centered_style
        glyphs=self.alphabet()
        margins,_=native_padding(glyphs)
        pages,plan=build_native_pages(glyphs,padding_by_identity=margins)
        with patch('orre_randomizer.hd_text_vectors._raster_letter',wraps=_raster_letter) as raster:
            outputs,report=render_vector_pages(pages,plan,FONTS/'NotoSansJP.ttf',FONTS/'OFL-NotoSansJP.txt')
        self.assertTrue(report['hd_ready'])
        self.assertFalse(report['per_glyph_horizontal_projection'])
        self.assertEqual({call.args[2]['scale_x'] for call in raster.call_args_list},
                         {report['styles']['0:latin']['scale_x']})
        records,styles,_,_,_=_layout(pages,plan,FONTS/'NotoSansJP.ttf',FONTS/'OFL-NotoSansJP.txt',None)
        for record in records:
            style=styles[record['style_key']]
            actual=centered_style(record,style)
            self.assertEqual(actual['y_knots'],style['y_knots'])
            self.assertEqual(actual['scale_x'],style['scale_x'])
            natural=style['scale_x']*record['vector_advance']
            self.assertAlmostEqual(actual['origin_x'],(record['row']['width']-natural)/2)
        for row in plan['glyphs']:
            x0,y0=row['draw_x']*4,row['draw_y']*4
            alpha=outputs[row['page']].getchannel('A').crop(
                (x0,y0,x0+row['draw_width']*4,y0+row['draw_height']*4))
            self.assertIsNotNone(alpha.getbbox())
            self.assertEqual(row['width'],next(g.width for g in glyphs if g.code==row['code']))

    def test_advance_fit_has_one_weight_per_character_and_punctuation_is_not_a_reference(self):
        from orre_randomizer.hd_text_layout import _horizontal_metrics
        rows=[{'row':{'code':ord(c),'width':w},'vector_advance':a,'ink':(0,0,w-2,10)}
              for c,w,a in [('A',5,100),('B',8,200),('C',11,300),('.',40,50)]]
        a=_horizontal_metrics(rows,'latin',.04)
        b=_horizontal_metrics([*rows,rows[0],rows[0]],'latin',.04)
        self.assertEqual(a,b)
        self.assertAlmostEqual(a[0],.03)
        self.assertAlmostEqual(a[1],2.)
        self.assertEqual(a[2],list(map(ord,'ABC')))

    def test_quasi_fixed_cells_do_not_collapse_shapes_into_tracking(self):
        from orre_randomizer.hd_text_layout import _horizontal_metrics
        for widths in ((8,8,8),(7,8,9)):
            rows=[{'row':{'code':ord(c),'width':w},'vector_advance':a,'vector_bounds':(0,-380,a,0),'ink':(0,0,w-1,12)}
                  for c,w,a in zip('ABC',widths,(100,300,500))]
            scale,tracking,codes,budget,cap=_horizontal_metrics(rows,'latin',.02)
            self.assertEqual(budget,1.)
            self.assertLessEqual(tracking,budget)
            self.assertGreater(scale,.015)
            self.assertLessEqual(scale,cap)
            self.assertEqual(codes,list(map(ord,'ABC')))

    def test_fixed_cells_keep_wide_letters_separate_without_individual_shape_fits(self):
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        glyphs=[]
        for c in alphabet:
            if c in 'gjpqy':offset,ink_height=4,12
            elif c.islower() and c not in 'bdfhklt':offset,ink_height=4,9
            else:offset,ink_height=0,13
            glyphs.append(self.glyph(c,8,16,offset,(0,0,7,ink_height)))
        margins,_=native_padding(glyphs)
        pages,plan=build_native_pages(glyphs,padding_by_identity=margins)
        output,report=render_vector_pages(pages,plan,FONTS/'NotoSansJP.ttf',FONTS/'OFL-NotoSansJP.txt')
        self.assertTrue(report['hd_ready'])
        self.assertIsNotNone(report['styles']['0:latin']['native_cell_shape_cap'])
        for c in 'Wm':
            row=next(r for r in plan['glyphs'] if r['code']==ord(c))
            image=output[row['page']].getchannel('A').crop((row['draw_x']*4,row['draw_y']*4,
                (row['draw_x']+row['draw_width'])*4,(row['draw_y']+row['draw_height'])*4))
            left,top,_,_=row['padding_ltrb']
            ink={(x-left*4,y+(row['y_offset']-top)*4) for y in range(image.height)
                 for x in range(image.width) if image.getpixel((x,y))>=128}
            adjacent={(x+row['width']*4,y) for x,y in ink}
            self.assertFalse(ink & adjacent,c)

    def test_nonletters_keep_native_graphic_regions_and_cannot_change_letter_calibration(self):
        glyphs=self.alphabet()
        pages,plan=build_native_pages(glyphs)
        base=measure_vector_layout(pages,plan)
        pages,plan=build_native_pages([*glyphs,self.glyph('.',3,3,20,(0,0,2,2))])
        with_punctuation=measure_vector_layout(pages,plan)
        self.assertEqual(base['styles'],with_punctuation['styles'])
        dot=next(row for row in with_punctuation['glyphs'] if row['code']==ord('.'))
        self.assertIsNone(dot['style_key'])
        self.assertEqual(dot['padding_ltrb'],[0,0,0,0])

    def test_missing_native_canvas_is_rejected_instead_of_clipping_letters(self):
        glyphs=self.alphabet()
        pages,plan=build_native_pages(glyphs)
        _,report=render_vector_pages(pages,plan,FONTS/"NotoSansJP.ttf",FONTS/"OFL-NotoSansJP.txt")
        self.assertFalse(report['hd_ready'])
        self.assertTrue(report['requires_native_canvas_update'])
        self.assertTrue(report['clipped_glyphs'])

    def test_original_unused_odd_nibbles_only_reconstruct_checksum(self):
        from copy import deepcopy
        glyph=Glyph(0,65,3,3,0,b'\xff\xf7\xff\xf9\xff\xf3','odd-native',0)
        pages,plan=build_native_pages([glyph],padding_by_identity={glyph.identity:(2,1,1,1)})
        row=plan['glyphs'][0]
        self.assertEqual(row['source_padding_nibbles_hex'],'070903')
        self.assertEqual(ink_bounds(pages[0],row),(0,0,3,3))
        altered=dict(row,source_padding_nibbles_hex='070904')
        with self.assertRaises(FormatError):ink_bounds(pages[0],altered)

    def test_graphic_gschar_cannot_change_alphabet_metrics(self):
        glyphs=self.alphabet()
        pages,plan=build_native_pages(glyphs)
        base=measure_vector_layout(pages,plan)
        icon=Glyph(0,0xe000,40,1,100,b'\xff'*20,'graphic',0)
        pages,plan=build_native_pages([*glyphs,icon])
        from orre_randomizer.hd_text_symbols import symbol_recipe as real_recipe
        with patch('orre_randomizer.hd_text_vectors.symbol_recipe',side_effect=lambda row:
                   ('speech-bubble','') if row['code']==0xe000 else real_recipe(row)):
            with_icon=measure_vector_layout(pages,plan)
        self.assertEqual(base['styles'],with_icon['styles'])
