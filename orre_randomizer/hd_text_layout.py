"""Shared vertical metrics and native-canvas references in line coordinates."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
import unicodedata

from .engine.analyze_game import FormatError

LAYOUT_RECIPE = "shared-y-native-advance-centered-common-x-v5"
BODY_FACTOR = .95
_CAPS = frozenset(map(ord, "AEFHINXZT"))
_CJK_REFS = frozenset(map(ord, "田日国漢あアカ水人"))
_ADVANCE_REFS = frozenset(map(ord, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"))


def typography_script(text: str) -> str:
    return "cjk" if ord(text) >= 0x2E80 and unicodedata.east_asian_width(text) in ("W", "F") else "latin"


def typographic_letter(kind: str, text: str, code: int) -> bool:
    # GSchar aliases, pictograms, punctuation and composites retain dedicated
    # native-region graphic recipes. They cannot alter alphabet metrics.
    return kind == "unicode" and text == chr(code) and unicodedata.category(text)[0] in "LN"


def typographic_character(kind: str, text: str, code: int) -> bool:
    """Letters/digits share proportions; other glyphs keep native graphic slots."""
    return typographic_letter(kind, text, code)


def _horizontal_metrics(rows, script, fallback_scale):
    by_code = defaultdict(list)
    for record in rows:
        if script != "latin" or record["row"]["code"] in _ADVANCE_REFS:
            by_code[record["row"]["code"]].append(record)
    # One weight per character: duplicate banks must not bias the face.
    pairs = [(median(r["vector_advance"] for r in variants),
              median(r["row"]["width"] for r in variants)) for variants in by_code.values()]
    if not pairs:
        return fallback_scale, 0., [], None, None
    if script == "cjk":
        # Full-width CJK keeps its existing common body proportion. There are
        # no Latin A-Z metrics in this script group to invent a calibration.
        return fallback_scale, median(y - fallback_scale * x for x, y in pairs), sorted(by_code), None, None
    # Near-fixed native banks cannot explain their cell widths through an
    # unconstrained slope: that would put nearly everything into tracking and
    # collapse the outlines. Bound this shared intercept by the native face's
    # actual median blank width, then solve the one remaining scale globally.
    budget = max(1., median(median(r["row"]["width"] - (r["ink"][2] - r["ink"][0])
                                  for r in variants) for variants in by_code.values()))
    mx, my = (sum(p[i] for p in pairs) / len(pairs) for i in (0, 1))
    variance = sum((x - mx) ** 2 for x, _ in pairs)
    if variance:
        scale = sum((x - mx) * (y - my) for x, y in pairs) / variance
        tracking = my - scale * mx
    else:
        scale, tracking = 0., my
    fixed_cell_fit = tracking > budget
    bounded_tracking = max(0., min(budget, tracking))
    if bounded_tracking != tracking or scale <= 0:
        tracking = bounded_tracking
        scale = sum(x * (y - tracking) for x, y in pairs) / sum(x * x for x, _ in pairs)
    if scale <= 0:
        raise FormatError("Native font has no positive common shape scale")
    shape_cap = None
    if fixed_cell_fit:
        # The same constrained scale applies to every outline. A quarter of
        # a native pixel reserves one4x sample at the cell edge for the pinned
        # antialias filter; wide W/m may not merge across fixed cells.
        limits = []
        for variants in by_code.values():
            for record in variants:
                half = record["vector_advance"] / 2
                bounds = record["vector_bounds"]
                extent = max(half - bounds[0], bounds[2] - half)
                if extent > 0:
                    limits.append((record["row"]["width"] - .25) / (2 * extent))
        shape_cap = min(limits)
        scale = min(scale, shape_cap)
    return float(scale), float(tracking), sorted(by_code), budget, shape_cap


def centered_style(record: dict, style: dict) -> dict:
    """Balance the native-cell residual around unchanged donor side bearings.

    Only translation varies per cell. Shape scale and tracking are shared;
    the real game continues to use its original advance and wrapping.
    """
    natural = style["scale_x"] * record["vector_advance"] + style["tracking"]
    origin = style["tracking"] / 2 + (record["row"]["width"] - natural) / 2
    return dict(style, origin_x=origin)


def map_font_y(value: float, style: dict) -> float:
    knots = style["y_knots"]
    index = next((i for i in range(len(knots) - 1) if value <= knots[i + 1][0]), len(knots) - 2)
    a, b = knots[index], knots[index + 1]
    return a[1] + (value - a[0]) * (b[1] - a[1]) / (b[0] - a[0])


def common_metric_styles(records: list[dict]) -> dict[str, dict]:
    """One size/baseline/grid per verified native font and script style.

    y_offset is a native quad position, not a font-size classification. Its
    value is used only to express original ink in line coordinates. Capitals
    with accents therefore retain the very same base cap height as H/E/N.
    """
    groups = defaultdict(list)
    for r in records:
        row = r["row"]
        if type(row.get("y_offset")) is not int or not -128 <= row["y_offset"] <= 127:
            raise FormatError("Invalid native line offset")
        key = f'{row["font_id"]}:{typography_script(r["text"])}'
        groups[key].append(r)
    styles = {}
    for key, rows in sorted(groups.items()):
        script = key.split(":")[1]
        if script == "cjk":
            refs = [r for r in rows if r["row"]["code"] in _CJK_REFS] or rows
            sx = BODY_FACTOR * median((r["ink"][2] - r["ink"][0]) /
                                     (r["vector_bounds"][2] - r["vector_bounds"][0]) for r in refs)
            sy = BODY_FACTOR * median((r["ink"][3] - r["ink"][1]) /
                                     (r["vector_bounds"][3] - r["vector_bounds"][1]) for r in refs)
            center = median(r["row"]["y_offset"] + (r["ink"][1] + r["ink"][3]) / 2 for r in refs)
            source_center = median((r["vector_bounds"][1] + r["vector_bounds"][3]) / 2 for r in refs)
            baseline = center - sy * source_center
            knots = [(-600., baseline - 600 * sy), (300., baseline + 300 * sy)]
            cap_codes = sorted({r["row"]["code"] for r in refs})
        else:
            caps = [r for r in rows if r["row"]["code"] in _CAPS] or rows
            # Do not merge truly different cap sizes that happen to reuse an ID.
            by_code = defaultdict(list)
            for r in caps:
                by_code[r["row"]["code"]].append(r)
            for variants in by_code.values():
                heights = [r["ink"][3] - r["ink"][1] for r in variants]
                boxes = [r["row"]["height"] for r in variants]
                if max(heights) - min(heights) > 2 and max(boxes) - min(boxes) > 2:
                    raise FormatError("Native font ID has distinct cap sizes; explicit bank styles required")
            baseline = median(r["row"]["y_offset"] + r["ink"][3]
                              - r["vector_bounds"][3] * (r["ink"][3] - r["ink"][1]) /
                              (r["vector_bounds"][3] - r["vector_bounds"][1]) for r in caps)
            cap_height = median(r["ink"][3] - r["ink"][1] for r in caps)
            cap_source = median(r["vector_bounds"][1] for r in caps)
            if cap_source >= 0:
                cap_source = -median(r["vector_bounds"][3] - r["vector_bounds"][1] for r in caps)
            xrefs = [r for r in rows if r["text"] == "x"]
            x_source = median(r["vector_bounds"][1] for r in xrefs) if xrefs else cap_source * .7
            x_height = median(r["ink"][3] - r["ink"][1] for r in xrefs) if xrefs else cap_height * .7
            accents = [r for r in rows if unicodedata.normalize("NFD", r["text"]) != r["text"]
                       and r["vector_bounds"][1] < cap_source]
            asc_source = min(r["vector_bounds"][1] for r in accents) if accents else cap_source - 100
            cap_target = baseline - BODY_FACTOR * cap_height
            asc_target = min(r["row"]["y_offset"] + r["ink"][1] for r in accents) if accents else cap_target - cap_height * .25
            asc_target = min(asc_target, cap_target - .25)
            desc = [r for r in rows if r["text"] in "gypqj" and r["vector_bounds"][3] > 0]
            desc_source = max(r["vector_bounds"][3] for r in desc) if desc else 125.
            desc_depth = median(r["row"]["y_offset"] + r["ink"][3] - baseline for r in desc) if desc else cap_height * .2
            knots = [(float(asc_source), float(asc_target)), (float(cap_source), float(cap_target)),
                     (float(x_source), float(baseline - BODY_FACTOR * x_height)), (0., float(baseline)),
                     (float(desc_source), float(baseline + max(.25, BODY_FACTOR * desc_depth)))]
            sx = BODY_FACTOR * median((r["ink"][2] - r["ink"][0]) /
                                     (r["vector_bounds"][2] - r["vector_bounds"][0]) for r in caps)
            refs, cap_codes = caps, sorted({r["row"]["code"] for r in caps})
        if (sx <= 0 or any(a[0] >= b[0] or a[1] >= b[1] for a, b in zip(knots, knots[1:]))):
            raise FormatError("Native font has no monotonic shared metric grid")
        sx, tracking, advance_codes, tracking_budget, shape_cap = _horizontal_metrics(rows, script, sx)
        styles[key] = {"key": key, "font_id": rows[0]["row"]["font_id"], "script": script,
            "nominal_native_height": max(r["row"]["height"] for r in rows),
            "scale_x": float(sx), "tracking": tracking, "baseline": float(baseline),
            "y_knots": knots, "body_factor": BODY_FACTOR, "reference_codes": cap_codes,
            "advance_calibration_codes": advance_codes,
            "advance_calibration": "A-Z-a-z-0-9" if script == "latin" else "fullwidth-common-body",
            "advance_fit_policy": "least-squares-with-native-blank-tracking-budget",
            "tracking_budget_native_pixels": tracking_budget,
            "native_cell_shape_cap": shape_cap,
            "glyphs": len(rows), "shared_transform": True, "shared_vertical_transform": True,
            "horizontal_render_policy": "common-scale-centered-in-native-advance",
            "horizontal_scale_role": "shared-shape-scale",
            "per_glyph_horizontal_projection": False, "per_glyph_vertical_fit": False,
            "original_advance_preserved": True,
            "native_y_offset_is_not_a_size": True}
    return styles
