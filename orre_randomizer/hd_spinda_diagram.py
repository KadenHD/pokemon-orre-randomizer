"""Authored DNA spot layers using actual independent-pack Spinda paint.

The stamp is an analytic ellipse in the native stamp's coordinate system. Its
colour/shading is sampled from the genuine HD body material, never obtained by
filtering the native 32-pixel stamp. PID placement retains native linear carry.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage

from .engine.spinda_diagram import RECIPE, spot_rows
from .hd_images import load_texture, resolve_texture


DONOR = "tex1_128x128_a1443261174f684e_4.png"
_PAINT_CROP = (128, 80, 176, 144)  # Interior red ear paint, in a512-square.
_ELLIPSE = (14.5, 16.0, 12.5, 14.0)  # cx,cy,rx,ry in native stamp coordinates.


def _tint(rgb, shiny):
    if not shiny:
        return rgb
    route, gain = RECIPE
    return tuple(min(255, (rgb[route[i]] * (gain[i] + 1) + 64) // 128) for i in range(3))


@lru_cache(maxsize=4)
def _paint(path: str, modified_ns: int):
    loaded = load_texture(Path(path), expected_native_size=(128, 128))
    if loaded.metadata["source_scale"] < 4:
        raise ValueError("Spinda diagram needs a genuine x4 body-material donor")
    qimage = loaded.image.convertToFormat(QImage.Format.Format_RGBA8888)
    raw = bytes(qimage.constBits())[:qimage.height() * qimage.bytesPerLine()]
    image = Image.frombytes("RGBA", (qimage.width(), qimage.height()), raw, "raw", "RGBA", qimage.bytesPerLine())
    scale = qimage.width() / 512
    crop = image.crop(tuple(round(v * scale) for v in _PAINT_CROP))
    skin = image.getpixel((0, 0))[:3]
    # Supersample the vector boundary; the painted colour comes from the pack.
    stamp = []
    cx, cy, rx, ry = _ELLIPSE
    for y in range(32):
        for x in range(32):
            coverage = sum(((x + (sx + .5) / 4 - cx) / rx) ** 2
                           + ((y + (sy + .5) / 4 - cy) / ry) ** 2 <= 1
                           for sy in range(4) for sx in range(4))
            color = crop.getpixel((min(crop.width - 1, x * crop.width // 32),
                                   min(crop.height - 1, y * crop.height // 32)))[:3]
            stamp.append((*color, round(coverage * 255 / 16)))
    return stamp, skin, loaded.metadata


def render_spinda_diagram_layer(transform: dict, pack_roots) -> tuple[QImage, list[dict]]:
    kind = transform.get("layer")
    shiny = transform.get("shiny")
    if kind not in {"empty", "background", "spot"} or type(shiny) is not bool:
        raise ValueError("Unknown Spinda diagram HD recipe")
    if kind == "spot" and (type(transform.get("spot")) is not int or not 0 <= transform["spot"] < 4
                            or type(transform.get("pid_byte")) is not int or not 0 <= transform["pid_byte"] <= 255):
        raise ValueError("Unknown Spinda diagram PID byte")
    root = Path(pack_roots["colosseum"])
    donor = resolve_texture(root, DONOR)
    stamp, skin, metadata = _paint(str(donor), donor.stat().st_mtime_ns)
    result = Image.new("RGBA", (160, 160))
    if kind == "background":
        result.paste((*_tint(skin, shiny), 255), (16, 16, 144, 144))
    elif kind == "spot":
        pixels = result.load()
        for row, start, count in spot_rows(transform["spot"], transform["pid_byte"]):
            for column in range(count):
                target = start + column
                rgba = stamp[row * 32 + column]
                pixels[16 + target % 128, 16 + target // 128] = (*_tint(rgba[:3], shiny), rgba[3])
    raw = result.tobytes()
    image = QImage(raw, 160, 160, 640, QImage.Format.Format_RGBA8888).copy()
    return image, [{"game": "colosseum", "file": DONOR, **metadata,
        "kind": "pack-paint-with-analytic-spinda-ellipse", "paint_crop_at512": list(_PAINT_CROP),
        "ellipse_native_stamp": list(_ELLIPSE), "source_native_stamp_size": 32,
        "output_native_size": 40, "output_hd_size": 160,
        "native_stamp_bitmap_filtered": False, "shiny": shiny,
        "pid_policy": "one-byte-per-layer-native-linear-row-start-and-carry"}]
