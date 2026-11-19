"""Real author geometry survives; native raster guides cannot reach the output."""
import hashlib
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QGuiApplication
from orre_randomizer.hd_menu_svg import render_background


class MenuSvgAuthoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def render(self, source, **kwargs):
        return render_background(source, expected_sha256=hashlib.sha256(source).hexdigest(),
                                 native_size=(8, 4), **kwargs)

    def test_only_real_vector_geometry_survives_explicit_guide_removal(self):
        source = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">
          <g id="native-guide"><image href="data:image/png;base64,AAA" width="8" height="4"/></g>
          <rect id="real-shape" x="1" y="1" width="6" height="2" fill="#10a0f0"/>
          <text x="1" y="2" font-family="Missing System Font">Caption removed</text>
        </svg>'''
        output, receipt = self.render(source, remove_ids=("native-guide",))
        self.assertEqual((output.width(), output.height()), (32, 16))
        self.assertEqual(output.pixelColor(8, 8), QColor(16, 160, 240))
        self.assertEqual(output.pixelColor(0, 0).alpha(), 0)
        self.assertFalse(receipt["native_bitmap_resampled"])
        self.assertFalse(receipt["font_rendering_remaining"])
        self.assertEqual(receipt["raster_images_remaining"], 0)
        with self.assertRaisesRegex(ValueError, "Non-vector.*image"):
            self.render(source, remove_ids=())

    def test_external_references_unreviewed_layout_and_unknown_removal_fail_closed(self):
        for element in (b'<use href="file:///private.png"/>',
                        b'<rect width="8" height="4" fill="url(https://external/image)"/>',
                        b'<filter id="unsupported"/>', b'<script>untrusted()</script>'):
            source = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">' + element + b'</svg>'
            with self.assertRaises(ValueError):
                self.render(source, remove_ids=())
        source = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4"/>'
        with self.assertRaisesRegex(ValueError, "missing"):
            self.render(source, remove_ids=("unknown",))
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            render_background(source, expected_sha256="altered", native_size=(8, 4), remove_ids=())
        with self.assertRaisesRegex(ValueError, "canvas"):
            render_background(source, expected_sha256=hashlib.sha256(source).hexdigest(),
                              native_size=(4, 8), remove_ids=())


if __name__ == "__main__":
    unittest.main()
