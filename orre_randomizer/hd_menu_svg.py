"""Offline menu authoring from explicit real SVG sources, without raster guides.

This module is used by the distributed author tool, not by game launch. Source
image/text layer removals are explicit and recorded. Only self-contained vector
geometry remains; external files, fonts, scripts and native bitmaps cannot render.
"""
from __future__ import annotations

import hashlib
import re
from xml.etree import ElementTree as ET

from PySide6.QtCore import QRectF, qVersion
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SVG = "http://www.w3.org/2000/svg"
ALLOWED = frozenset(("svg", "g", "defs", "path", "rect", "circle", "ellipse", "line",
    "polygon", "polyline", "linearGradient", "radialGradient", "stop", "clipPath", "mask", "use"))
_URL = re.compile(r"url\(\s*['\"]?([^)'\"]+)", re.IGNORECASE)


def _integer_straight_alpha(image: QImage) -> QImage:
    """Export native premultiplied RGBA with exact integer half-up rounding.

    Qt's straight-alpha stores use a CPU-selected approximate reciprocal, even
    in their one-pixel tail (QTBUG-150796). Read the premultiplied bytes directly;
    pixelColor() and convertToFormat() would reintroduce that conversion.
    https://github.com/qt/qtbase/blob/v6.11.2/src/gui/painting/qpixellayout.cpp
    """
    if (image.isNull() or image.format() != QImage.Format.Format_RGBA8888_Premultiplied
            or image.bytesPerLine() != image.width() * 4):
        raise ValueError("Expected tightly packed native premultiplied RGBA artwork")
    pixels = bytes(image.constBits())[:image.sizeInBytes()]
    if pixels[3::4] != b"\xff" * (image.width() * image.height()):
        result = bytearray(pixels)
        for offset in range(0, len(result), 4):
            alpha = pixels[offset + 3]
            if alpha == 0:
                result[offset:offset + 3] = b"\0\0\0"
            elif alpha != 255:
                half = alpha // 2
                for channel in range(3):
                    result[offset + channel] = min(255, (pixels[offset + channel] * 255 + half) // alpha)
        pixels = bytes(result)
    # Copy owns the bytes without invoking a premultiplied/straight conversion.
    return QImage(pixels, image.width(), image.height(), image.width() * 4,
                  QImage.Format.Format_RGBA8888).copy()


def render_background(payload: bytes, *, expected_sha256: str,
                      native_size: tuple[int, int], remove_ids: tuple[str, ...],
                      integer_alpha: bool = False):
    """Render x4 original author geometry after removing declared guide nodes."""
    if (not isinstance(payload, bytes) or not 1 <= len(payload) <= 12 * 1024 * 1024
            or hashlib.sha256(payload).hexdigest() != expected_sha256
            or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper()):
        raise ValueError("Unexpected or unsafe original menu SVG")
    if (len(native_size) != 2 or any(type(v) is not int or not 1 <= v <= 2048 for v in native_size)
            or native_size[0] * native_size[1] > 1024 * 1024
            or len(remove_ids) > 128 or len(set(remove_ids)) != len(remove_ids)):
        raise ValueError("Invalid bounded menu SVG layout/removal recipe")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise ValueError("Cannot parse the original menu SVG") from None
    if root.tag != "{" + SVG + "}svg":
        raise ValueError("Menu author source is not an SVG document")
    try:
        viewbox = tuple(float(v) for v in re.split(r"[\s,]+", root.attrib["viewBox"].strip()))
    except (KeyError, ValueError):
        raise ValueError("Menu author SVG has no declared native viewBox") from None
    if viewbox != (0., 0., float(native_size[0]), float(native_size[1])):
        raise ValueError("Menu author SVG canvas differs from its registered native guide")
    elements = list(root.iter())
    if len(elements) > 20000:
        raise ValueError("Menu author SVG exceeds its bounded vector complexity")
    ids = [node.get("id") for node in elements if node.get("id")]
    if len(ids) != len(set(ids)) or set(remove_ids) - set(ids):
        raise ValueError("Menu SVG removal identity is missing or duplicated")
    removed = []
    def clean(parent):
        for node in list(parent):
            local = node.tag.split("}")[-1]
            if (node.get("id") in remove_ids or local in ("metadata", "namedview", "title", "desc", "text", "flowRoot")):
                removed.append({"id": node.get("id"), "kind": local})
                parent.remove(node)
                continue
            clean(node)
    clean(root)
    for node in root.iter():
        local = node.tag.split("}")[-1]
        if node.tag != "{" + SVG + "}" + local or local not in ALLOWED:
            raise ValueError("Non-vector menu SVG element remains: " + local)
        for key, value in list(node.attrib.items()):
            if key.startswith("{") and not key.startswith("{http://www.w3.org/1999/xlink}"):
                del node.attrib[key]
                continue
            local_key = key.split("}")[-1]
            if local_key.startswith("on") or "@import" in value.lower():
                raise ValueError("Executable or imported SVG content is forbidden")
            if local_key == "href" and not value.startswith("#"):
                raise ValueError("External SVG references are forbidden")
            if any(not target.strip().startswith("#") for target in _URL.findall(value)):
                raise ValueError("External SVG paint resources are forbidden")
            if local_key == "style" and "font" in value.lower():
                # No text survives, so font declarations are inert; removing
                # them also makes the no-system-font authoring contract clear.
                node.attrib[key] = ";".join(part for part in value.split(";") if "font" not in part.lower())
        if node.text and node.text.strip():
            raise ValueError("Unconverted text remains in menu SVG geometry")
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    vectors = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    renderer = QSvgRenderer(vectors)
    if not renderer.isValid():
        raise ValueError("Qt cannot render the declared vector menu source")
    pixel_format = (QImage.Format.Format_RGBA8888_Premultiplied if integer_alpha
                    else QImage.Format.Format_RGBA8888)
    output = QImage(native_size[0] * 4, native_size[1] * 4, pixel_format)
    output.fill(0)
    painter = QPainter(output)
    try:
        bounds = QRectF(0, 0, output.width(), output.height())
        renderer.render(painter, bounds)
    finally:
        painter.end()
    premultiplied_sha256 = (hashlib.sha256(bytes(output.constBits())[:output.sizeInBytes()]).hexdigest()
                            if integer_alpha else None)
    if integer_alpha:
        output = _integer_straight_alpha(output)
    metadata = {"kind": "real-author-svg-background", "version": 2 if integer_alpha else 1,
        "source_sha256": expected_sha256, "native_dimensions": list(native_size),
        "source_scale": 4, "remove_ids": list(remove_ids), "removed_nodes": removed,
        "sanitized_svg_sha256": hashlib.sha256(vectors).hexdigest(),
        "sanitized_vector_elements": sum(1 for _ in root.iter()),
        "native_bitmap_resampled": False, "raster_images_remaining": 0,
        "font_rendering_remaining": False, "qt_version": qVersion(),
        "rasterization": "integer-premultiplied-alpha" if integer_alpha else "native-qt"}
    if integer_alpha:
        metadata["alpha_conversion"] = "rgba8888-pm-integer-half-up-v1"
        metadata["premultiplied_rgba_sha256"] = premultiplied_sha256
    return output, metadata
