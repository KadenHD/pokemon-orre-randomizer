"""Menu atlas derivatives from pinned HD pixels and captured vector outlines.

The source game's pixels supply only identities, cell coordinates and labels.
Background colour and detail come from the genuine HD donor. Letter shapes are
vector paths; no native bitmap is enlarged, filtered or used as the HD image.
This module does not touch a disc, save, Dolphin profile or installed pack.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QTransform


RECIPE_VERSION = 1
RECIPE_TYPE = "menu_atlas_badge_labels"


def _word_path(text: str, family: str, vectors: dict) -> QPainterPath:
    try:
        glyphs = vectors["families"][family]["glyphs"]
    except (KeyError, TypeError):
        raise ValueError("Menu vector font family is unavailable") from None
    result = QPainterPath()
    result.setFillRule(Qt.FillRule.WindingFill)
    cursor = 0.0
    for char in text:
        glyph = glyphs.get(char)
        if glyph is None:
            raise ValueError("Menu vector outline is unavailable: " + repr(char))
        part = QPainterPath()
        part.setFillRule(Qt.FillRule.WindingFill)
        for command in glyph["path"]:
            kind, *values = command
            if kind == "M" and len(values) == 2:
                part.moveTo(*values)
            elif kind == "L" and len(values) == 2:
                part.lineTo(*values)
            elif kind == "C" and len(values) == 6:
                part.cubicTo(*values)
            else:
                raise ValueError("Invalid captured menu vector command")
        result.addPath(QTransform.fromTranslate(cursor, 0).map(part))
        cursor += glyph["advance"]
    return result


def _pixel_bytes(image: QImage) -> bytes:
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if image.bytesPerLine() != image.width() * 4:
        raise ValueError("Unexpected menu atlas row alignment")
    return bytes(image.constBits())[:image.sizeInBytes()]


def _gradient_rows(source, width, box):
    rows = []
    for y in range(box[1], box[3]):
        colors = Counter(tuple(source[(y * width + x) * 4:(y * width + x) * 4 + 4])
                         for x in range(box[0], box[2])
                         if source[(y * width + x) * 4 + 3] >= 128
                         and max(source[(y * width + x) * 4:(y * width + x) * 4 + 3]) > 8)
        rows.append(colors.most_common(1)[0][0] if colors else None)
    good = [i for i, color in enumerate(rows) if color is not None]
    if not good:
        raise ValueError("HD badge gradient has no registered colour samples")
    return [color if color is not None else rows[min(good, key=lambda i: abs(i - index))]
            for index, color in enumerate(rows)]


def _roundrect_background(source, pixels, authored, width, height, cell, vectors):
    recipe = cell["background"]
    if recipe.get("type") != "rounded-rectangle":
        raise ValueError("Unknown menu background reconstruction")
    box = cell["bounds"]
    radius = recipe.get("radius_native")
    if type(radius) not in (float, int) or not 0 < radius <= min(box[2] - box[0], box[3] - box[1]) / 2:
        raise ValueError("Invalid menu capsule radius")
    source_box = cell["donor_bounds"]
    if recipe.get("palette"):
        palette = vectors.get("palettes", {}).get(recipe["palette"])
        if not palette or not palette.get("rows"):
            raise ValueError("Menu capsule palette is not registered")
        colors = palette["rows"]
    else:
        colors = _gradient_rows(source, width, source_box)
    mask = QImage(width, height, QImage.Format.Format_RGBA8888)
    mask.fill(Qt.GlobalColor.transparent)
    painter = QPainter(mask)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRoundedRect(QRectF(box[0] * 4, box[1] * 4,
                                      (box[2] - box[0]) * 4, (box[3] - box[1]) * 4),
                                radius * 4, radius * 4)
    finally:
        painter.end()
    alpha = _pixel_bytes(mask)
    clear = (max(0, min(source_box[0] - 3, box[0] * 4 - 1)),
             max(0, min(source_box[1] - 3, box[1] * 4 - 1)),
             min(width, max(source_box[2] + 3, box[2] * 4 + 1)),
             min(height, max(source_box[3] + 3, box[3] * 4 + 1)))
    for y in range(clear[1], clear[3]):
        for x in range(clear[0], clear[2]):
            at = (y * width + x) * 4
            pixels[at:at + 4] = bytes(4)
            authored[y * width + x] = 1
    top, bottom = box[1] * 4, box[3] * 4
    for y in range(top, bottom):
        position = (y - top + .5) * len(colors) / (bottom - top) - .5
        a = max(0, min(len(colors) - 1, int(position)))
        b = min(len(colors) - 1, a + 1)
        fraction = max(0., min(1., position - a))
        color = [round(colors[a][i] * (1 - fraction) + colors[b][i] * fraction) for i in range(4)]
        for x in range(box[0] * 4, box[2] * 4):
            at = (y * width + x) * 4
            coverage = alpha[at + 3]
            if coverage:
                pixels[at:at + 4] = bytes((*color[:3], (color[3] * coverage + 127) // 255))


def _render_badges(image: QImage, recipe: dict, vectors: dict):
    """Continue the donor's vertical fill under its replaced letter shapes.

    These capsule/rectangle donors have a uniform horizontal interior at each
    row. A modal nonblack opaque donor sample supplies that row's real HD fill.
    All antialiased silhouette pixels are retained, including rounded corners.
    This is an authored continuation of the donor gradient, not native scaling.
    """
    width, height = image.width(), image.height()
    native = recipe["native_dimensions"]
    if ((width, height) != (native[0] * 4, native[1] * 4)
            or not isinstance(recipe.get("cells"), list) or not recipe["cells"]):
        raise ValueError("Menu badge dimensions or cell layout differ")
    source = _pixel_bytes(image)
    pixels = bytearray(source)
    authored = bytearray(width * height)
    occupied = []
    for cell in recipe["cells"]:
        box, text_box = cell["bounds"], cell["text_bounds"]
        if (len(box) != 4 or len(text_box) != 4
                or any(type(v) is not int for v in (*box, *text_box))
                or not 0 <= box[0] < box[2] <= native[0]
                or not 0 <= box[1] < box[3] <= native[1]
                or not box[0] <= text_box[0] < text_box[2] <= box[2]
                or not box[1] <= text_box[1] < text_box[3] <= box[3]
                or any(max(box[0], p[0]) < min(box[2], p[2])
                       and max(box[1], p[1]) < min(box[3], p[3]) for p in occupied)):
            raise ValueError("Menu badge cells overlap or leave their atlas")
        occupied.append(box)
        if not cell.get("replace", True):
            continue
        donor_box = cell.get("donor_bounds", [v * 4 for v in box])
        if (len(donor_box) != 4 or any(type(v) is not int for v in donor_box)
                or not 0 <= donor_box[0] < donor_box[2] <= width
                or not 0 <= donor_box[1] < donor_box[3] <= height):
            raise ValueError("Menu donor cell leaves its HD atlas")
        left, top, right, bottom = donor_box
        samples = cell.get("gradient_sample_bounds", [donor_box])
        if (not isinstance(samples, list) or not 1 <= len(samples) <= 8
                or any(len(part) != 4 or any(type(v) is not int for v in part)
                       or not left <= part[0] < part[2] <= right
                       or not top <= part[1] < part[3] <= bottom for part in samples)):
            raise ValueError("Menu gradient samples leave the genuine donor cell")
        if cell.get("background"):
            _roundrect_background(source, pixels, authored, width, height, cell, vectors)
            continue
        for y in range(top, bottom):
            colors = Counter()
            sample_columns = sorted({x for part in samples if part[1] <= y < part[3]
                                     for x in range(part[0], part[2])})
            for x in sample_columns:
                at = (y * width + x) * 4
                r, g, b, a = source[at:at + 4]
                if a >= 128 and max(r, g, b) > 8:
                    colors[(r, g, b, a)] += 1
            if cell.get("gradient_sample_bounds") and (not colors or max(colors.values()) < 2):
                # The declared side strips can fall outside a rounded tip.
                # Reuse the original whole-row rule there, retaining its
                # uniform-fill validation rather than synthesizing an edge.
                colors = Counter(tuple(source[(y * width + x) * 4:(y * width + x) * 4 + 4])
                                 for x in range(left, right)
                                 if source[(y * width + x) * 4 + 3] >= 128
                                 and max(source[(y * width + x) * 4:(y * width + x) * 4 + 3]) > 8)
            if not colors:
                continue  # The antialiased outline is never synthesized.
            color, count = colors.most_common(1)[0]
            if count < 2:
                black = any(source[(y * width + x) * 4 + 3] == 255
                            and max(source[(y * width + x) * 4:(y * width + x) * 4 + 3]) <= 8
                            for x in range(left, right))
                if black:
                    raise ValueError(f"HD donor lacks the declared uniform badge fill: {box}, row {y}")
                continue  # Subpixel rounded tip; no old lettering to erase.
            matching = [x for x in range(left, right)
                        if tuple(source[(y * width + x) * 4:(y * width + x) * 4 + 4]) == color]
            if cell.get("gradient_sample_bounds"):
                # A glossy capsule can shade its left and right margins
                # differently. Exact equality to a side sample therefore does
                # not bracket all of the old glyph. Continue the sampled HD
                # material across its opaque interior, retaining the source
                # outline and its antialiasing rather than copying letter ink.
                matching = [x for x in range(left, right)
                            if source[(y * width + x) * 4 + 3] == 255
                            and max(source[(y * width + x) * 4:(y * width + x) * 4 + 3]) > 8]
                if not matching:
                    continue
            interior_left, interior_right = min(matching), max(matching) + 1
            for x in range(interior_left, interior_right):
                at = (y * width + x) * 4
                if cell.get("gradient_sample_bounds") and source[at + 3] != 255:
                    continue
                pixels[at:at + 4] = bytes(color)
                authored[y * width + x] = 1
    output = QImage(bytes(pixels), width, height, width * 4,
                    QImage.Format.Format_RGBA8888).copy()
    painter = QPainter(output)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 255))
        for cell in recipe["cells"]:
            if not cell.get("replace", True):
                continue
            word = _word_path(cell["text"], cell.get("font_family", recipe["font_family"]), vectors)
            bounds = word.boundingRect()
            if bounds.isEmpty():
                raise ValueError("A menu label has no visible vector outline")
            left, top, right, bottom = cell["text_bounds"]
            stroke = cell.get("stroke_native", recipe.get("stroke_native", 0))
            if (type(stroke) not in (int, float) or not math.isfinite(stroke) or not 0 <= stroke <= 2
                    or min(right - left, bottom - top) <= stroke * 2):
                raise ValueError("Invalid localized badge caption stroke")
            target_w, target_h = (right - left) * 4, (bottom - top) * 4
            transform = QTransform()
            transform.translate((left + stroke) * 4, (top + stroke) * 4)
            transform.scale((target_w - stroke * 8) / bounds.width(), (target_h - stroke * 8) / bounds.height())
            transform.translate(-bounds.left(), -bounds.top())
            path = transform.map(word)
            if stroke:
                outline = QPainterPathStroker()
                outline.setWidth(stroke * 8)
                outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.fillPath(outline.createStroke(path), QColor(cell.get("outline", recipe.get("outline", "#000000"))))
            painter.setBrush(QColor(cell.get("fill", recipe.get("fill", "#000000"))))
            painter.drawPath(path)
    finally:
        painter.end()
    # Retain the donor's genuine antialiased outline outside the reconstructed
    # interior. Inside it, replacing opaque letters legitimately changes alpha
    # over a translucent gradient; preserving old letter alpha would ghost it.
    result = bytearray(_pixel_bytes(output))
    for at in range(0, len(result), 4):
        if not authored[at // 4]:
            result[at:at + 4] = source[at:at + 4]
    output = QImage(bytes(result), width, height, width * 4,
                    QImage.Format.Format_RGBA8888).copy()
    return output, {
        "kind": "pack-derived-menu-vector-labels", "version": RECIPE_VERSION,
        "language": recipe["language"], "family": recipe["family"],
        "labels": [cell["text"] for cell in recipe["cells"]],
        "native_raster_used_for_HD_art": False,
        "native_guide": deepcopy(recipe["native_guide"]),
        "vector_source": deepcopy(vectors["families"][recipe["font_family"]]["source"]),
        "hd_background": "original donor alpha and modal horizontal interior gradient",
        "unmodified_pixels": "outside registered donor/background regions",
        "authored_backgrounds": [deepcopy(c["background"]) for c in recipe["cells"] if c.get("background")],
        "alpha_policy": "genuine donor gradient under new opaque vector labels",
        "runtime_validated": False,
        "output_rgba_sha256": hashlib.sha256(result).hexdigest(),
    }


def _render_vector_text(recipe: dict, vectors: dict):
    """Rebuild a text-only atlas from real font outlines and native positions."""
    dimensions = recipe.get("native_dimensions", ())
    if (len(dimensions) != 2 or any(type(v) is not int or not 1 <= v <= 2048 for v in dimensions)
            or dimensions[0] * dimensions[1] > 1024 * 1024
            or not 1 <= len(recipe.get("labels", ())) <= 64):
        raise ValueError("Menu text atlas exceeds its bounded layout")
    output = QImage(dimensions[0] * 4, dimensions[1] * 4, QImage.Format.Format_RGBA8888)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for label in recipe["labels"]:
            box = label["bounds"]
            stroke = label.get("stroke_native", 1.)
            if (len(box) != 4 or any(type(v) is not int for v in box)
                    or not 0 <= box[0] < box[2] <= dimensions[0]
                    or not 0 <= box[1] < box[3] <= dimensions[1]
                    or type(stroke) not in (int, float) or not 0 <= stroke <= 2
                    or min(box[2] - box[0], box[3] - box[1]) <= stroke * 2):
                raise ValueError("Menu vector label leaves its registered rectangle")
            word = _word_path(label["text"], label.get("font_family", recipe["font_family"]), vectors)
            bounds = word.boundingRect()
            if bounds.isEmpty():
                raise ValueError("Menu vector label has no outline")
            transform = QTransform()
            transform.translate((box[0] + stroke) * 4, (box[1] + stroke) * 4)
            transform.scale((box[2] - box[0] - stroke * 2) * 4 / bounds.width(),
                            (box[3] - box[1] - stroke * 2) * 4 / bounds.height())
            transform.translate(-bounds.left(), -bounds.top())
            path = transform.map(word)
            if stroke:
                outlines = label.get("outline_layers", [{"width_native": stroke,
                    "color": label.get("outline", "#000000")}])
                if not isinstance(outlines, list) or not 1 <= len(outlines) <= 4:
                    raise ValueError("Invalid menu outline layer count")
                previous = stroke + 1
                for layer in outlines:
                    thickness = layer.get("width_native")
                    color = QColor(layer.get("color", ""))
                    if (type(thickness) not in (int, float) or not math.isfinite(thickness)
                            or not 0 < thickness <= stroke or thickness >= previous or not color.isValid()):
                        raise ValueError("Menu outline layers must narrow within the native rectangle")
                    outline = QPainterPathStroker()
                    outline.setWidth(thickness * 8)
                    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.fillPath(outline.createStroke(path), color)
                    previous = thickness
            elif "outline_layers" in label:
                raise ValueError("Layered menu outlines require bounded native stroke space")
            brush = QColor(label.get("fill", "#ffffff"))
            gradient = label.get("fill_gradient")
            if gradient is not None:
                axis, stops = gradient.get("axis", ()), gradient.get("stops", ())
                if (len(axis) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in axis)
                        or not 0 <= axis[0] <= dimensions[0] or not 0 <= axis[2] <= dimensions[0]
                        or not 0 <= axis[1] <= dimensions[1] or not 0 <= axis[3] <= dimensions[1]
                        or axis[:2] == axis[2:] or not 2 <= len(stops) <= 32):
                    raise ValueError("Invalid native menu fill ramp")
                brush = QLinearGradient(*(v * 4 for v in axis))
                previous = -1.
                for position, rgba in stops:
                    if (type(position) not in (int, float) or not math.isfinite(position)
                            or not 0 <= position <= 1 or position <= previous
                            or len(rgba) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in rgba)):
                        raise ValueError("Invalid native menu fill stop")
                    brush.setColorAt(position, QColor(*rgba))
                    previous = position
            painter.fillPath(path, brush)
    finally:
        painter.end()
    return output, {"kind": "authored-menu-vector-text", "version": 1,
        "language": recipe["language"], "family": recipe["family"],
        "labels": [label["text"] for label in recipe["labels"]],
        "native_guide": deepcopy(recipe["native_guide"]),
        "native_raster_used_for_HD_art": False,
        "vector_source": deepcopy(vectors["families"][recipe["font_family"]]["source"]),
        "source_donor_role": "author typography and black/white label style reference",
        "runtime_validated": False,
        "output_rgba_sha256": hashlib.sha256(_pixel_bytes(output)).hexdigest()}


def _render_pack_labels(image: QImage, recipe: dict, vectors: dict):
    """Keep genuine HD frame/icon pixels and replace bounded locale captions."""
    width, height = recipe["native_dimensions"]
    if (image.width(), image.height()) != (width * 4, height * 4):
        raise ValueError("Localized menu captions require the original HD canvas")
    clears = recipe.get("clear_rects", ())
    if not 1 <= len(clears) <= 64:
        raise ValueError("Localized menu has no bounded caption replacement")
    output = image.convertToFormat(QImage.Format.Format_RGBA8888).copy()
    painter = QPainter(output)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        for box in clears:
            if (len(box) != 4 or any(type(v) is not int for v in box)
                    or not 0 <= box[0] < box[2] <= width
                    or not 0 <= box[1] < box[3] <= height):
                raise ValueError("Localized menu caption clear leaves its registered canvas")
            if not recipe.get("background_has_no_captions", False):
                painter.fillRect(box[0] * 4, box[1] * 4, (box[2] - box[0]) * 4,
                                 (box[3] - box[1]) * 4, QColor(0, 0, 0, 0))
    finally:
        painter.end()
    for label in recipe["labels"]:
        box = label["bounds"]
        if not any(clear[0] <= box[0] < box[2] <= clear[2]
                   and clear[1] <= box[1] < box[3] <= clear[3] for clear in clears):
            raise ValueError("New menu caption leaves its replacement region")
    lettering, label_report = _render_vector_text(recipe, vectors)
    painter = QPainter(output)
    try:
        painter.drawImage(0, 0, lettering)
    finally:
        painter.end()
    # QPainter can canonicalize RGB under alpha0 while converting its backing
    # store. Exact preservation includes those invisible donor bytes as well.
    original, result = _pixel_bytes(image), bytearray(_pixel_bytes(output))
    for y in range(height * 4):
        spans = sorted((box[0] * 4, box[2] * 4) for box in clears
                       if box[1] * 4 <= y < box[3] * 4)
        row, previous = y * width * 16, 0
        for left, right in (*spans, (width * 4, width * 4)):
            if left > previous:
                start, end = row + previous * 4, row + left * 4
                result[start:end] = original[start:end]
            previous = max(previous, right)
    output = QImage(bytes(result), width * 4, height * 4, width * 16,
                    QImage.Format.Format_RGBA8888).copy()
    return output, {**label_report, "kind": "pack-derived-menu-caption-localization",
        "caption_regions": deepcopy(clears),
        "clear_rects": [] if recipe.get("background_has_no_captions", False) else deepcopy(clears),
        "background_has_no_captions": recipe.get("background_has_no_captions", False),
        "source_donor_role": "genuine HD menu frame and icons preserved outside caption rectangles",
        "unchanged_donor_pixels": "all pixels outside registered caption_regions",
        "output_rgba_sha256": hashlib.sha256(result).hexdigest()}


def _render_vector_geometry(recipe: dict):
    """Render declared analytic shapes, never a scaled native pixel mask."""
    dimensions = recipe.get("native_dimensions", ())
    layers = recipe.get("layers", ())
    if (len(dimensions) != 2 or any(type(v) is not int or not 1 <= v <= 2048 for v in dimensions)
            or dimensions[0] * dimensions[1] > 1024 * 1024
            or not 1 <= len(layers) <= 128):
        raise ValueError("Menu vector geometry exceeds its bounded canvas")
    output = QImage(dimensions[0] * 4, dimensions[1] * 4, QImage.Format.Format_RGBA8888)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for layer in layers:
            color = layer.get("color", ())
            commands = layer.get("operations", ())
            if (len(color) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in color)
                    or not 1 <= len(commands) <= 2048):
                raise ValueError("Invalid menu vector palette or operation count")
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.WindingFill)
            for command in commands:
                box = command.get("bounds", ())
                if (len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                        or not 0 <= box[0] < box[2] <= dimensions[0]
                        or not 0 <= box[1] < box[3] <= dimensions[1]):
                    raise ValueError("Menu vector operation leaves its native canvas")
                part = QPainterPath()
                rect = QRectF(box[0], box[1], box[2] - box[0], box[3] - box[1])
                if command["shape"] == "ellipse":
                    part.addEllipse(rect)
                elif command["shape"] == "rectangle":
                    part.addRect(rect)
                elif command["shape"] == "rounded-rectangle":
                    radius = command.get("radius", -1)
                    if type(radius) not in (int, float) or not math.isfinite(radius) or not 0 <= radius <= min(rect.width(), rect.height()) / 2:
                        raise ValueError("Invalid analytic menu corner radius")
                    part.addRoundedRect(rect, radius, radius)
                else:
                    raise ValueError("Unknown analytic menu primitive")
                if command.get("operation", "union") == "union":
                    path = path.united(part)
                elif command["operation"] == "subtract":
                    path = path.subtracted(part)
                else:
                    raise ValueError("Unknown analytic menu boolean operation")
            brush = QColor(*color)
            gradient = layer.get("gradient")
            if gradient is not None:
                axis, stops = gradient.get("axis", ()), gradient.get("stops", ())
                if (len(axis) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in axis)
                        or not 0 <= axis[0] <= dimensions[0] or not 0 <= axis[2] <= dimensions[0]
                        or not 0 <= axis[1] <= dimensions[1] or not 0 <= axis[3] <= dimensions[1]
                        or axis[:2] == axis[2:] or not 2 <= len(stops) <= 32):
                    raise ValueError("Invalid authored menu gradient")
                brush = QLinearGradient(*[v * 4 for v in axis])
                previous = -1
                for position, rgba in stops:
                    if (type(position) not in (int, float) or not math.isfinite(position)
                            or not previous < position <= 1 or position < 0
                            or len(rgba) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in rgba)):
                        raise ValueError("Invalid authored menu gradient stop")
                    brush.setColorAt(position, QColor(*rgba))
                    previous = position
            transformed = QTransform.fromScale(4, 4).map(path)
            stroke = layer.get("stroke")
            if stroke is not None:
                thickness, rgba = stroke.get("width", -1), stroke.get("color", ())
                if (type(thickness) not in (int, float) or not math.isfinite(thickness) or not 0 < thickness <= 4
                        or len(rgba) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in rgba)):
                    raise ValueError("Invalid authored menu outline")
                outline = QPainterPathStroker()
                outline.setWidth(thickness * 4)
                painter.fillPath(outline.createStroke(transformed), QColor(*rgba))
            painter.fillPath(transformed, brush)
    finally:
        painter.end()
    return output, {"kind": "authored-analytic-menu-vectors", "version": 1,
        "family": recipe["family"], "native_guide": deepcopy(recipe["native_guide"]),
        "construction": deepcopy(layers), "native_raster_resampled_for_HD_art": False,
        "palette_policy": "declared flat colours or traced author SVG gradients; analytically reconstructed geometry",
        "source_donor_role": "no image donor; genuine vector reconstruction",
        "runtime_validated": False,
        "output_rgba_sha256": hashlib.sha256(_pixel_bytes(output)).hexdigest()}


def _render_authored_panel(recipe: dict, vectors: dict):
    output, geometry = _render_vector_geometry(recipe)
    letters, typography = _render_vector_text(recipe, vectors)
    painter = QPainter(output)
    try:
        painter.drawImage(0, 0, letters)
    finally:
        painter.end()
    return output, dict(geometry, kind="source-vector-menu-panel",
        author_source=deepcopy(recipe["author_source"]), typography=typography,
        source_donor_role="actual author SVG geometry/gradient plus captured font vectors; no bitmap enlargement",
        output_rgba_sha256=hashlib.sha256(_pixel_bytes(output)).hexdigest())


def _render_registered_composition(recipe: dict, vectors: dict):
    """Place approved real renders/photos in their exact original UV windows."""
    from .hd_menu_catalog import menu_artwork_metadata, menu_image
    provenance = menu_artwork_metadata(recipe["provenance_file"], recipe["provenance_sha256"])
    output, geometry = _render_vector_geometry(recipe)
    sources = recipe.get("images", ())
    if not 1 <= len(sources) <= 32:
        raise ValueError("A menu composition needs its registered real artwork")
    components = []
    painter = QPainter(output)
    try:
        for source in sources:
            box, native_size = source["bounds"], source["native_dimensions"]
            if (len(box) != 4 or any(type(v) is not int for v in box)
                    or not 0 <= box[0] < box[2] <= recipe["native_dimensions"][0]
                    or not 0 <= box[1] < box[3] <= recipe["native_dimensions"][1]
                    or native_size != [box[2] - box[0], box[3] - box[1]]):
                raise ValueError("Menu artwork does not fit its registered original UV window")
            image = menu_image(source["file"], tuple(native_size))
            entry = provenance.get("files", {}).get(source["manifest_file"], {})
            if (image.metadata["sha256"] != source["sha256"]
                    or entry.get("sha256") != source["sha256"]
                    or entry.get("dimensions") != [native_size[0] * 4, native_size[1] * 4]):
                raise ValueError("Menu artwork differs from its approved capture/photo receipt")
            painter.drawImage(box[0] * 4, box[1] * 4, image.image)
            components.append(dict(image.metadata, native_window=deepcopy(box)))
    finally:
        painter.end()
    if recipe.get("foreground_layers"):
        foreground, _ = _render_vector_geometry(dict(recipe, layers=recipe["foreground_layers"]))
        painter = QPainter(output)
        try:
            painter.drawImage(0, 0, foreground)
        finally:
            painter.end()
    if recipe.get("labels"):
        lettering, _ = _render_vector_text(recipe, vectors)
        painter = QPainter(output)
        try:
            painter.drawImage(0, 0, lettering)
        finally:
            painter.end()
    return output, {"kind": "registered-native-mesh-and-authentic-photo-menu-composition", "version": 1,
        "native_guide": deepcopy(recipe["native_guide"]), "geometry": geometry,
        "images": components, "source": provenance, "runtime_validated": False,
        "native_raster_used_as_output": False,
        "output_rgba_sha256": hashlib.sha256(_pixel_bytes(output)).hexdigest()}


def render_menu_atlas(image: QImage, transform: dict, *, source_metadata: dict):
    """Render only a catalogued, pinned donor/target transformation."""
    from .hd_menu_catalog import menu_recipes, menu_vectors
    target = transform.get("target")
    catalog = {}
    for game_id in ("GC6E01", "GC6P01", "GC6J01", "GXXE01", "GXXP01", "GXXJ01"):
        catalog.update(menu_recipes(game_id))
    expected = catalog.get(target)
    if expected is None or transform != expected["transform"]:
        raise ValueError("Unknown or altered menu atlas recipe")
    if expected.get("file") is None and not expected.get("bundled_donor"):
        if (transform.get("type") not in ("menu_atlas_vector_geometry", "menu_atlas_vector_text",
                                         "menu_atlas_authored_panel", "menu_atlas_registered_composition")
                or transform.get("version") != RECIPE_VERSION
                or not image.isNull() or source_metadata not in (
                    {"kind": "authored-vector-artwork"}, {"kind": "authored-vector-geometry"})):
            raise ValueError("Unexpected image donor for authored menu vectors")
        if transform["type"] == "menu_atlas_vector_geometry":
            return _render_vector_geometry(transform)
        if transform["type"] == "menu_atlas_authored_panel":
            return _render_authored_panel(transform, menu_vectors())
        if transform["type"] == "menu_atlas_registered_composition":
            return _render_registered_composition(transform, menu_vectors())
        output, metadata = _render_vector_text(transform, menu_vectors())
        return output, dict(metadata,
            source_donor_role="captured true font vectors; original native caption layout and flat palette guide")
    if (source_metadata.get("sha256") != expected["source_sha256"]
            or source_metadata.get("source_scale") != 4
            or (image.width(), image.height()) != tuple(v * 4 for v in expected["source_native_dimensions"])):
        raise ValueError("Menu atlas requires its exact genuine x4 HD donor")
    if transform.get("background_has_no_captions") and not expected.get("bundled_donor"):
        raise ValueError("Caption-free source must be registered author artwork")
    if transform["version"] != RECIPE_VERSION:
        raise ValueError("Unsupported menu atlas transform")
    if transform["type"] == RECIPE_TYPE:
        output, metadata = _render_badges(image, transform, menu_vectors())
    elif transform["type"] == "menu_atlas_vector_text":
        output, metadata = _render_vector_text(transform, menu_vectors())
    elif transform["type"] == "menu_atlas_hd_patch_labels":
        output, metadata = _render_pack_labels(image, transform, menu_vectors())
    elif transform["type"] == "menu_atlas_registered_image":
        if (not expected.get("bundled_donor")
                or source_metadata.get("kind") != "registered-authored-menu-artwork"
                or transform.get("author_source", {}).get("native_bitmap_resampled") is not False):
            raise ValueError("Image-only menu artwork must be registered and genuinely authored")
        author = transform["author_source"]
        if author.get("manifest"):
            from .hd_menu_catalog import menu_artwork_metadata
            manifest = menu_artwork_metadata(author["manifest"], author["manifest_sha256"])
            entry = manifest.get("files", {}).get(author.get("artwork_file"), {})
            if (entry.get("sha256") != expected["source_sha256"]
                    or entry.get("dimensions") != [image.width(), image.height()]):
                raise ValueError("Registered menu capture differs from its approved manifest")
        output = image.convertToFormat(QImage.Format.Format_RGBA8888).copy()
        metadata = {"kind": "registered-authored-menu-image", "version": 1,
            "family": transform["family"], "native_guide": deepcopy(transform["native_guide"]),
            "author_source": deepcopy(transform["author_source"]),
            "native_raster_used_for_HD_art": False, "runtime_validated": False,
            "output_rgba_sha256": hashlib.sha256(_pixel_bytes(output)).hexdigest()}
    elif transform["type"] == "menu_atlas_upstream_name_alias":
        filename = expected.get("file", "")
        if (expected.get("bundled_donor") or not filename.endswith("_nope.png")
                or filename.removesuffix("_nope.png") + ".png" != target):
            raise ValueError("Upstream menu alias must retain its exact native texture identity")
        output = image.convertToFormat(QImage.Format.Format_RGBA8888).copy()
        metadata = {"kind": "pinned-upstream-HD-name-alias", "version": 1,
            "native_guide": deepcopy(transform["native_guide"]),
            "author_source": deepcopy(transform["author_source"]),
            "unchanged_pixels": "entire genuine x4 upstream image",
            "native_raster_used_for_HD_art": False, "runtime_validated": False,
            "output_rgba_sha256": hashlib.sha256(_pixel_bytes(output)).hexdigest()}
    else:
        raise ValueError("Unsupported menu atlas transform")
    if expected.get("bundled_donor") and transform["type"] != "menu_atlas_registered_image":
        metadata = dict(metadata, kind="source-vector-menu-caption-localization",
            author_source=deepcopy(transform["author_source"]),
            source_donor_role="registered real author-vector background with newly localized vector captions")
    return output, dict(metadata, source=deepcopy(source_metadata))
