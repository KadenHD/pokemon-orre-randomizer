"""Pinned vector-font artwork for GSmsg pages; no native bitmap enlargement.

The caller supplies the original I4 pages solely for ink bounds and provenance.
All HD ink is rasterized from Noto Sans JP's TrueType outlines. Missing Unicode
characters fail closed rather than drawing a font's .notdef rectangle.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict
import math
from pathlib import Path
import struct
from PIL import __version__ as PILLOW_VERSION, features as PIL_FEATURES

from .engine.analyze_game import FormatError, check_range
from .hd_text import CONTRACT, PAGE_BYTES, PAGE_SIZE, _sample_offset
from .hd_text_symbols import symbol_recipe
from .hd_text_layout import (common_metric_styles, centered_style, map_font_y, typography_script,
                             typographic_letter, typographic_character, LAYOUT_RECIPE)

FONT_SHA256 = "c2f3b4d463500a2ddcd3849cded1fceeb9fd6d1c32e6cbecd568453ba50fc68f"
LICENSE_SHA256 = "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9"
RECIPE = "noto-sans-jp-700-common-x-native-advance-v5"
MAX_CACHED_MASKS = 64
SOURCE = {"name": "Noto Sans JP", "author": "Google / Adobe",
          "license": "SIL Open Font License 1.1",
          "font_sha256": FONT_SHA256, "license_sha256": LICENSE_SHA256,
          "url": "https://github.com/google/fonts/tree/main/ofl/notosansjp",
          "upstream_commit": "523d033d6cb47f4a80c58a35753646f5c3608a78",
          "weight": 700, "recipe": RECIPE, "layout_recipe": LAYOUT_RECIPE,
          "style": "adapted vector typography; shared shape proportions, balanced native advance cells, common vertical metrics",
          "glyph_policy": "letters-digits-common-shape; other-glyphs-native-graphic-regions",
          "rasterizer": {"pillow": PILLOW_VERSION, "freetype": PIL_FEATURES.version("freetype2"),
                         "vertical": "common-grid-bicubic-2x-lanczos",
                         "horizontal": "bounded-advance-fit-fixed-cell-shape-cap-v5"}}


def unicode_cmap(data: bytes) -> set[int]:
    """Read Unicode cmap formats 4/12 and exclude glyph zero explicitly."""
    check_range(data, 0, 12, "TrueType header")
    count = struct.unpack_from(">H", data, 4)[0]
    check_range(data, 12, count * 16, "TrueType directory")
    tables = {}
    for at in range(12, 12 + count * 16, 16):
        name, _, start, size = struct.unpack_from(">4sIII", data, at)
        check_range(data, start, size, "TrueType table")
        tables[name] = (start, size)
    if b"cmap" not in tables:
        raise FormatError("Vector donor has no Unicode cmap")
    base, size = tables[b"cmap"]
    sub = data[base:base + size]
    check_range(sub, 0, 4, "Unicode cmap header")
    n = struct.unpack_from(">H", sub, 2)[0]
    check_range(sub, 4, n * 8, "Unicode cmap records")
    codes = set()
    for pos in range(4, 4 + n * 8, 8):
        platform, encoding, start = struct.unpack_from(">HHI", sub, pos)
        if platform != 0 and (platform, encoding) not in ((3, 1), (3, 10)):
            continue
        check_range(sub, start, 4, "Unicode cmap subtable")
        fmt = struct.unpack_from(">H", sub, start)[0]
        if fmt == 4:
            length, _, twice = struct.unpack_from(">HHH", sub, start + 2)
            check_range(sub, start, length, "cmap format 4")
            end = start + length
            segments = twice // 2
            ends = start + 14
            begins = ends + segments * 2 + 2
            deltas = begins + segments * 2
            ranges = deltas + segments * 2
            if not segments or twice % 2 or ranges + 2 * segments > end:
                raise FormatError("Invalid cmap segment directory")
            for i in range(segments):
                hi = struct.unpack_from(">H", sub, ends + i * 2)[0]
                lo = struct.unpack_from(">H", sub, begins + i * 2)[0]
                delta = struct.unpack_from(">h", sub, deltas + i * 2)[0]
                distance = struct.unpack_from(">H", sub, ranges + i * 2)[0]
                if lo > hi:
                    raise FormatError("Invalid Unicode cmap range")
                for code in range(lo, min(hi, 0xFFFE) + 1):
                    if distance:
                        at = ranges + i * 2 + distance + (code - lo) * 2
                        if at + 2 > end:
                            raise FormatError("Unicode cmap glyph leaves its subtable")
                        glyph = struct.unpack_from(">H", sub, at)[0]
                        glyph = ((glyph + delta) & 65535) if glyph else 0
                    else:
                        glyph = (code + delta) & 65535
                    if glyph:
                        codes.add(code)
        elif fmt == 12:
            check_range(sub, start, 16, "cmap format 12 header")
            length, _, groups = struct.unpack_from(">III", sub, start + 4)
            check_range(sub, start, length, "cmap format 12")
            if 16 + groups * 12 > length:
                raise FormatError("Invalid Unicode cmap groups")
            for i in range(groups):
                lo, hi, glyph = struct.unpack_from(">III", sub, start + 16 + i * 12)
                if not lo <= hi <= 0x10FFFF:
                    raise FormatError("Invalid Unicode cmap group")
                codes.update(range(lo + (glyph == 0), hi + 1))
    if not codes:
        raise FormatError("Vector donor has no supported Unicode characters")
    return codes


def ink_bounds(page: bytes, row: dict) -> tuple[int, int, int, int] | None:
    """Native glyph ink bounds, excluding padding outside its visible quad."""
    if len(page) != 128 + PAGE_BYTES:
        raise FormatError("Invalid native glyph page")
    if (any(type(row.get(key)) is not int for key in ("x", "y", "width", "height", "code", "font_id"))
            or not 1 <= row["width"] <= 40 or not 1 <= row["height"] <= 40
            or row["x"] < 2 or row["x"] % 2 or row["y"] < 8
            or row["x"] + ((row["width"] + 1) & ~1) + 2 > PAGE_SIZE
            or row["y"] + row["height"] >= PAGE_SIZE
            or not 0 <= row["font_id"] <= 8 or not 0 <= row["code"] <= 65535):
        raise FormatError("Native glyph slot leaves its verified page")
    packed = bytearray()
    for y in range(row["height"]):
        for x in range(0, (row["width"] + 1) & ~1, 2):
            at, shift = _sample_offset(row["x"] + x, row["y"] + y)
            if shift != 4:
                raise FormatError("Native glyph slot is not byte-aligned")
            packed.append(page[128 + at])
    padding = row.get("source_padding_nibbles_hex")
    if padding not in (None, ""):
        try:
            nibbles = bytes.fromhex(padding)
        except (ValueError, TypeError):
            raise FormatError("Invalid original odd-width padding nibbles") from None
        stride = (row["width"] + 1) // 2
        if row["width"] % 2 != 1 or len(nibbles) != row["height"] or any(n > 15 for n in nibbles):
            raise FormatError("Original odd-width nibble directory differs")
        for y, nibble in enumerate(nibbles):
            at = y * stride + stride - 1
            if packed[at] & 15:
                raise FormatError("Transparent draw-canvas padding contains native ink")
            # Only checksum reconstruction sees the original unused nibble.
            packed[at] |= nibble
    if hashlib.sha256(packed).hexdigest() != row["samples_sha256"]:
        raise FormatError("Native glyph slot differs from its sampled bitmap")
    points = []
    for y in range(row["height"]):
        for x in range(row["width"]):
            at, shift = _sample_offset(row["x"] + x, row["y"] + y)
            if (page[128 + at] >> shift) & 15:
                points.append((x, y))
    if not points:
        return None
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points) + 1, max(y for _, y in points) + 1)


def _vector_mask(font, kind, text, cmap):
    from PIL import Image, ImageDraw

    def word(value):
        if any(ord(c) not in cmap for c in value):
            raise FormatError("A vector GSchar component is absent from the donor cmap")
        box = font.getbbox(value)
        mask = Image.new("L", (max(1, box[2] - box[0]), max(1, box[3] - box[1])))
        ImageDraw.Draw(mask).text((-box[0], -box[1]), value, font=font, fill=255)
        actual = mask.getbbox()
        return mask.crop(actual) if actual else None

    if kind == "unicode":
        return word(text)
    mask = Image.new("L", (512, 512))
    draw = ImageDraw.Draw(mask)
    if kind == "pokedollar":
        mask.paste(word("P").resize((480, 512), Image.Resampling.LANCZOS), (16, 0))
        draw.rectangle((0, 340, 340, 375), fill=255)
        draw.rectangle((0, 425, 340, 460), fill=255)
    elif kind == "boxed-s":
        draw.rectangle((0, 0, 511, 511), outline=255, width=28)
        mask.paste(word("S").resize((310, 370), Image.Resampling.LANCZOS), (101, 71))
    elif kind == "eplus":
        mask.paste(word("e").resize((370, 512), Image.Resampling.LANCZOS), (0, 0))
        mask.paste(word("+").resize((190, 190), Image.Resampling.LANCZOS), (322, 60))
    elif kind == "speech-bubble":
        draw.ellipse((0, 0, 511, 405), fill=255)
        draw.polygon(((280, 340), (465, 511), (415, 320)), fill=255)
    elif kind in ("three-dots", "two-dots", "single-dot"):
        positions = {"three-dots": ((256, 70), (70, 442), (442, 442)),
                     "two-dots": ((70, 256), (442, 256)), "single-dot": ((256, 256),)}[kind]
        radius = 70 if kind != "single-dot" else 255
        for x, y in positions:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    else:
        raise FormatError("Unknown vector GSchar primitive")
    actual = mask.getbbox()
    return mask.crop(actual) if actual else None


def _font_mask(font, text):
    from PIL import Image
    core, origin = font.getmask2(text, mode="L", anchor="ls")
    mask = Image.frombytes("L", core.size, bytes(core))
    bounds = mask.getbbox()
    if bounds is None:
        return None, (0, 0)
    return mask.crop(bounds), (origin[0] + bounds[0], origin[1] + bounds[1])


def _sources(font_file, license_file):
    from PIL import ImageFont
    if PILLOW_VERSION.split(".", 1)[0] != "13":
        raise FormatError("Vector typography requires the supported Pillow13 renderer")
    data = Path(font_file).read_bytes()
    if hashlib.sha256(data).hexdigest() != FONT_SHA256:
        raise FormatError("Unexpected vector-font donor")
    if hashlib.sha256(Path(license_file).read_bytes()).hexdigest() != LICENSE_SHA256:
        raise FormatError("Vector-font license differs from its pinned source")
    font = ImageFont.truetype(str(font_file), 512)
    font.set_variation_by_axes([700])
    return font, unicode_cmap(data)


def _layout(native_pages, plan, font_file, license_file, cancel):
    _checkpoint(cancel)
    if (plan.get("contract") != CONTRACT or not 1 <= len(native_pages) <= 128
            or plan.get("pages") != len(native_pages) or not 1 <= len(plan.get("glyphs", ())) <= 30000
            or plan.get("page_sha256") != [hashlib.sha256(p).hexdigest() for p in native_pages]):
        raise FormatError("Glyph vector recipe differs from its native pages")
    font, cmap = _sources(font_file, license_file)
    masks, stats = OrderedDict(), {"peak": 0, "evictions": 0}

    def get_mask(typographic, kind, text):
        key = typographic, kind, text
        if key not in masks:
            masks[key] = (_font_mask(font, text) if typographic else
                          (_vector_mask(font, kind, text, cmap), (0, 0)))
            if len(masks) > MAX_CACHED_MASKS:
                masks.popitem(last=False)
                stats["evictions"] += 1
            stats["peak"] = max(stats["peak"], len(masks))
        else:
            masks.move_to_end(key)
        return masks[key]

    records, letters, missing = [], [], set()
    for row in plan["glyphs"]:
        _checkpoint(cancel)
        if type(row.get("page")) is not int or not 0 <= row["page"] < len(native_pages):
            raise FormatError("Native glyph selects an unknown page")
        bounds = ink_bounds(native_pages[row["page"]], row)
        record = {"row": row, "ink": bounds}
        records.append(record)
        if bounds is None:
            continue
        kind, text = symbol_recipe(row)
        typographic = typographic_character(kind, text, row["code"])
        record.update(kind=kind, text=text, typographic=typographic)
        if kind == "unicode" and any(ord(c) not in cmap for c in text):
            missing.add(row["code"])
            continue
        if typographic:
            mask, origin = get_mask(True, kind, text)
            if mask is None:
                missing.add(row["code"])
                continue
            record["vector_bounds"] = (origin[0], origin[1], origin[0] + mask.width, origin[1] + mask.height)
            record["vector_advance"] = font.getlength(text)
            record["style_key"] = f'{row["font_id"]}:{typography_script(text)}'
            if typographic_letter(kind, text, row["code"]):
                letters.append(record)
    styles = common_metric_styles(letters)
    for record in records:
        if record.get("typographic") and record["style_key"] not in styles:
            raise FormatError("Text punctuation has no verified alphabet style")
    return records, styles, get_mask, stats, missing


def _raster_letter(mask, origin, style, left, top, width, height):
    """Apply the vertical grid and supplied X projection with2x supersampling."""
    from PIL import Image
    scale = 8  # 4x target, sampled twice from the genuine512px outline raster.
    output = Image.new("L", (width * scale, height * scale))
    knots = style["y_knots"]
    # Extend the outer style bands; no per-letter resizing or baseline fitting.
    ranges = [(float("-inf"), knots[0][1], 0),
              *[(a[1], b[1], i) for i, (a, b) in enumerate(zip(knots, knots[1:]))],
              (knots[-1][1], float("inf"), len(knots) - 2)]
    for low, high, index in ranges:
        start = 0 if not math.isfinite(low) else max(0, math.floor((low - top) * scale))
        end = height * scale if not math.isfinite(high) else min(height * scale, math.ceil((high - top) * scale))
        if end <= start:
            continue
        a, b = knots[index], knots[index + 1]
        ratio = (b[0] - a[0]) / (b[1] - a[1])
        affine = (1 / (scale * style["scale_x"]), 0,
                  (left - style["origin_x"]) / style["scale_x"] - origin[0],
                  0, ratio / scale, (top + start / scale - a[1]) * ratio + a[0] - origin[1])
        band = mask.transform((width * scale, end - start), Image.Transform.AFFINE,
                              affine, Image.Resampling.BICUBIC)
        output.paste(band, (0, start))
    return output.resize((width * 4, height * 4), Image.Resampling.LANCZOS)


def _padding(record, style, get_mask):
    style = centered_style(record, style)
    row = record["row"]
    mask, origin = get_mask(True, record["kind"], record["text"])
    box = record["vector_bounds"]
    raw = (style["origin_x"] + box[0] * style["scale_x"], map_font_y(box[1], style),
           style["origin_x"] + box[2] * style["scale_x"], map_font_y(box[3], style))
    # A temporary1px border measures actual4x antialias coverage, then shrinks
    # to the exact integral native-pixel margins required by that coverage.
    probe = (math.ceil(max(0, -raw[0])) + 1, math.ceil(max(0, row["y_offset"] - raw[1])) + 1,
             math.ceil(max(0, raw[2] - row["width"])) + 1,
             math.ceil(max(0, raw[3] - row["y_offset"] - row["height"])) + 1)
    if max(probe) > 17:
        raise FormatError("Common vector font requires an excessive glyph canvas")
    l, t, r, b = probe
    coverage = _raster_letter(mask, origin, style, -l, row["y_offset"] - t,
                              row["width"] + l + r, row["height"] + t + b)
    bounds = coverage.getbbox()
    if bounds is None:
        raise FormatError("Common vector font lost a nonempty glyph")
    ink = (bounds[0] / 4 - l, bounds[1] / 4 + row["y_offset"] - t,
           bounds[2] / 4 - l, bounds[3] / 4 + row["y_offset"] - t)
    required = (math.ceil(max(0, -ink[0])), math.ceil(max(0, row["y_offset"] - ink[1])),
                math.ceil(max(0, ink[2] - row["width"])),
                math.ceil(max(0, ink[3] - row["y_offset"] - row["height"])))
    return required, ink


def _raster_centered(record, style, get_mask, left, top, width, height):
    """One shape scale per style; center its advance within the native cell."""
    mask, origin = get_mask(True, record["kind"], record["text"])
    return _raster_letter(mask, origin, centered_style(record, style), left, top, width, height)


def measure_vector_layout(native_pages, plan, font_file=None, license_file=None, *, cancel=None):
    """Return shared styles and exact margins; never allocate full HD pages."""
    assets = Path(__file__).resolve().parent / "assets/game/fonts"
    font_file = Path(font_file) if font_file is not None else assets / "NotoSansJP.ttf"
    license_file = Path(license_file) if license_file is not None else assets / "OFL-NotoSansJP.txt"
    records, styles, get_mask, stats, missing = _layout(native_pages, plan, font_file, license_file, cancel)
    glyphs = []
    for record in records:
        _checkpoint(cancel)
        row = record["row"]
        padding, ink = (0, 0, 0, 0), None
        if record["ink"] is not None and record.get("typographic") and row["code"] not in missing:
            padding, ink = _padding(record, styles[record["style_key"]], get_mask)
        glyphs.append({key: row[key] for key in ("font_id", "code", "width", "height", "y_offset", "samples_sha256")} |
                      {"padding_ltrb": list(padding), "vector_ink_line_bounds": ink,
                       "style_key": record.get("style_key")})
    return {"source": dict(SOURCE), "layout_recipe": LAYOUT_RECIPE,
            "styles": styles, "glyphs": glyphs, "missing_codes": sorted(missing),
            "hd_ready": not missing, "per_glyph_horizontal_projection": False,
            "per_glyph_vertical_fit": False,
            "canvas_policy": "borrowed-static-pages-v2-centered-common-shape",
            "max_cached_vector_masks": MAX_CACHED_MASKS, "peak_cached_vector_masks": stats["peak"]}


def native_padding(glyphs, *, cancel=None):
    """Bridge API: original Glyph.identity -> required native L/T/R/B margins.

    Only original I4 metrics and the bundled OFL vector donor are needed. No HD
    pack, RGB artwork, source ISO or running emulator is involved.
    """
    from .hd_text import build_native_pages
    _checkpoint(cancel)
    pages, plan = build_native_pages(glyphs)
    report = measure_vector_layout(pages, plan, cancel=cancel)
    if not report["hd_ready"]:
        raise FormatError("Bundled font does not cover the native glyph corpus")
    rows = {(r["font_id"], r["code"], r["width"], r["height"], r["y_offset"], r["samples_sha256"]): r
            for r in report["glyphs"]}
    padding = {}
    for glyph in glyphs:
        _checkpoint(cancel)
        key = (glyph.font_id, glyph.code, glyph.width, glyph.height, glyph.y_offset,
               hashlib.sha256(glyph.samples).hexdigest())
        if key in rows:
            padding[glyph.identity] = tuple(rows[key]["padding_ltrb"])
    return padding, report


def _checkpoint(cancel):
    if cancel is not None and cancel.is_set():
        raise InterruptedError("Text vector layout cancelled")


def render_vector_pages(native_pages: list[bytes], plan: dict, font_file: Path,
                        license_file: Path, *, cancel=None) -> tuple[list, dict]:
    """Render common shape metrics, centered within unchanged native advances."""
    from PIL import Image
    records, styles, get_mask, stats, missing = _layout(native_pages, plan, font_file, license_file, cancel)
    output = [Image.new("RGBA", (PAGE_SIZE * 4, PAGE_SIZE * 4)) for _ in native_pages]
    drawn, blank, symbols, clipped = 0, 0, 0, []
    for record in records:
        _checkpoint(cancel)
        row, bounds = record["row"], record["ink"]
        if bounds is None:
            blank += 1
            continue
        if row["code"] in missing:
            continue
        kind, text = record["kind"], record["text"]
        if record["typographic"]:
            style = styles[record["style_key"]]
            required, _ = _padding(record, style, get_mask)
            x, y, width, height, padding = _draw_canvas(row)
            if any(need > available for need, available in zip(required, padding, strict=True)):
                clipped.append({"font_id": row["font_id"], "code": row["code"],
                                "required_ltrb": list(required), "available_ltrb": list(padding)})
                continue
            coverage = _raster_centered(record, style, get_mask, -padding[0],
                                        row["y_offset"] - padding[1], width, height)
        else:
            # Graphic GSchar recipes have no alphabetic cap/x-height. Their
            # original icon region remains authoritative, outside font metrics.
            mask, _ = get_mask(False, kind, text)
            if mask is None:
                missing.add(row["code"])
                continue
            x0, y0, x1, y1 = bounds
            coverage = mask.resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.Resampling.LANCZOS)
            x, y = row["x"] + x0, row["y"] + y0
        # I4's RGB and alpha both carry intensity. Retain that convention.
        rgba = Image.merge("RGBA", (coverage, coverage, coverage, coverage))
        output[row["page"]].paste(rgba, (x * 4, y * 4))
        drawn += 1
        symbols += not record["typographic"]
    return output, {"source": dict(SOURCE), "drawn_glyphs": drawn, "blank_glyphs": blank,
                    "semantic_symbol_glyphs": symbols, "styles": styles,
                    "layout_recipe": LAYOUT_RECIPE,
                    "horizontal_render_policy": "common-scale-centered-in-native-advance",
                    "per_glyph_horizontal_projection": False, "per_glyph_vertical_fit": False,
                    "max_cached_vector_masks": MAX_CACHED_MASKS,
                    "peak_cached_vector_masks": stats["peak"],
                    "vector_mask_cache_evictions": stats["evictions"],
                    "missing_codes": sorted(missing), "clipped_glyphs": clipped,
                    "requires_native_canvas_update": bool(clipped), "hd_ready": not missing and not clipped,
                    "native_bitmap_used_as_artwork": False,
                    "native_metrics_unchanged": True, "scale": 4}


def _draw_canvas(row):
    names = ("draw_x", "draw_y", "draw_width", "draw_height")
    if not any(name in row for name in names):
        return row["x"], row["y"], row["width"], row["height"], (0, 0, 0, 0)
    padding = row.get("padding_ltrb")
    if (any(type(row.get(name)) is not int for name in names) or not isinstance(padding, (tuple, list))
            or len(padding) != 4 or any(type(n) is not int or not 0 <= n <= 32 for n in padding)):
        raise FormatError("Invalid captured native draw canvas")
    l, t, r, b = padding
    x, y, width, height = (row[name] for name in names)
    if (x != row["x"] - l or y != row["y"] - t or width != row["width"] + l + r
            or height != row["height"] + t + b or x < 2 or y < 8
            or x + ((width + 1) & ~1) + 2 > PAGE_SIZE or y + height >= PAGE_SIZE):
        raise FormatError("Native draw canvas leaves its captured page")
    return x, y, width, height, tuple(padding)
