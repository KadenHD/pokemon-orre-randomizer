"""The UI matte removes only border-connected backdrop, never native anatomy."""
from pathlib import Path
import unittest

from orre_randomizer.artwork import _png_pixels
from orre_randomizer.portrait_matte import shadow_lugia_background_mask, make_shadow_lugia_ui_portrait


class PortraitMatteTests(unittest.TestCase):
    def test_spatial_mask_keeps_enclosed_color_islands_and_blue_gray_red_foreground(self):
        pixels = bytearray(bytes((0, 0, 0, 255))*(42*42))

        def put(x, y, color):
            at=(y*42+x)*4
            pixels[at:at+4]=bytes(color)

        purple=(82,24,107,255)
        for x,y in ((0,10),(1,11),(2,12),(3,13),(20,20)):
            put(x,y,purple)
        put(4,13,(33,33,49,255))
        put(4,14,(230,35,49,255))
        put(0,8,(49,16,57,255))  # native baked-disk dark outline
        put(0,0,(119,119,153,0))
        mask=shadow_lugia_background_mask(bytes(pixels))
        self.assertTrue({0,10*42,11*42+1,12*42+2,13*42+3} <= mask)
        self.assertIn(8*42,mask)
        self.assertNotIn(20*42+20,mask)
        self.assertNotIn(13*42+4,mask)
        self.assertNotIn(14*42+4,mask)
        output=make_shadow_lugia_ui_portrait(bytes(pixels),reference=bytes(pixels))
        self.assertEqual(output[(20*42+20)*4:(20*42+21)*4],bytes(purple))
        for index in mask:
            self.assertEqual(output[index*4:index*4+4],bytes((0,0,0,255)))

    def test_native_ui_assets_preserve_foreground_over_black_and_game_textures(self):
        pack=Path(__file__).resolve().parents[1]/'orre_randomizer/assets/game/models'
        if not (pack/'dark-lugia.png').exists():
            self.skipTest('optional game resource pack is not present')
        reference=_png_pixels((pack/'dark-lugia.png').read_bytes(),(42,42))
        mask=shadow_lugia_background_mask(reference)
        self.assertGreater(len(mask),500)
        self.assertLess(len(mask),1200)
        for native_name,ui_name in (('dark-lugia.png','dark-lugia-ui.png'),
                                    ('dark-lugia-shiny.png','dark-lugia-shiny-ui.png')):
            native=(pack/native_name).read_bytes()
            source=_png_pixels(native,(42,42))
            ui=_png_pixels((pack/ui_name).read_bytes(),(42,42))
            self.assertEqual(ui,make_shadow_lugia_ui_portrait(source,reference=reference))
            self.assertEqual(ui[3::4],bytes((255,))*(42*42))
            for index in range(42*42):
                at=index*4
                if index in mask:
                    self.assertEqual(ui[at:at+4],bytes((0,0,0,255)))
                else:
                    r,g,b,alpha=source[at:at+4]
                    self.assertEqual(ui[at:at+3],bytes((v*alpha+127)//255 for v in (r,g,b)))
                r,g,b,alpha=reference[at:at+4]
                if alpha==255 and (abs(r-g)<=12 or r>b):
                    self.assertNotIn(index,mask)  # all blue-gray/navy anatomy and red eye/tongue
            self.assertEqual((pack/native_name).read_bytes(),native)

    def test_ui_resource_loader_uses_the_separate_matted_tiles(self):
        from orre_randomizer.resources import bundle_root,shadow_lugia_portrait
        if not (bundle_root()/'models/dark-lugia-ui.png').exists():
            self.skipTest('optional game resource pack is not present')
        shadow_lugia_portrait.cache_clear()
        for shiny,name in ((False,'dark-lugia-ui.png'),(True,'dark-lugia-shiny-ui.png')):
            from orre_randomizer.model_portraits import registered_portrait
            registered = registered_portrait(bundle_root()/'models', game='colosseum', shiny=shiny)
            expected = registered if registered is not None else (bundle_root()/'models'/name).read_bytes()
            self.assertEqual(shadow_lugia_portrait(shiny=shiny), expected)

    def test_wrong_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            shadow_lugia_background_mask(bytes(4))
        with self.assertRaises(ValueError):
            make_shadow_lugia_ui_portrait(bytes(4),reference=bytes(4))


if __name__=='__main__':
    unittest.main()
