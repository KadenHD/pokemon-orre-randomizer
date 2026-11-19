"""Transfer genuine Colosseum HD portraits at full size into XD's round frames."""
from __future__ import annotations

from collections import Counter
import math
import re
from collections.abc import Mapping

from .hd_portrait_catalog import CATALOG_ROWS


_CATALOG = {}
for _row in CATALOG_ROWS.splitlines():
    if not _row:
        continue
    _name, _dex, _width, _source, _format, _target, _palette, _sha = _row.split()
    _CATALOG[_name] = (int(_dex), int(_width),
        f"tex1_{_width}x84_{_source}_{_format}.png", f"tex1_{_width}x84_{_target}_{_palette}_9.png", _sha)

_MISSING_FORMS = {
    "face385f": "Castform sunny", "face385w": "Castform rainy", "face385i": "Castform snowy",
    "face410atk": "Deoxys attack", "face410def": "Deoxys defence", "face410sp": "Deoxys speed",
}


def is_ordinary_portrait_member(name: str) -> bool:
    return name in _CATALOG


def ordinary_portrait_origin(member: str, native_key: str, native_size: tuple[int, int]) -> dict | None:
    """Register one exact retail face; never substitute another form or a custom face."""
    donor = _CATALOG.get(member)
    if donor is None:
        return None
    national, width, source, expected_target, sha = donor
    normalized = re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", native_key)
    if normalized != expected_target or tuple(native_size) != (width, 84):
        raise ValueError("The ordinary XD portrait has an unknown or changed native identity: " + member)
    return {"game": "colosseum", "file": source, "source_native_dimensions": [width, 84],
            "native_source": "verified Colosseum poke_face.fsys/" + member,
            "transform": {"type": "colosseum_portrait_to_xd", "version": 1,
                "member": member, "national_dex": national,
                "native_size": [width, 84], "source_native_key": source,
                "target_native_key": expected_target, "source_sha256": sha,
                "layout": {"columns": width // 42, "rows": 2, "cell_size": 42}}}


def portrait_coverage_report() -> dict:
    from .hd_extra_portraits import portrait_coverage_report as extra_coverage
    extra = extra_coverage()
    absent_upstream = [{"member": name, "form": form} for name, form in _MISSING_FORMS.items()]
    return {"kind": "ordinary Colosseum HD portraits ported to XD", "native_rom_changed": False,
            "required_packs": ["colosseum"], "texture_atlases": len(_CATALOG),
            "base_species": len({row[0] for row in _CATALOG.values()}),
            "unown_forms": sum(name.startswith("face201") for name in _CATALOG),
            "normal_and_shiny": True, "native_cell_size": 42,
            "missing_forms": ([] if extra["registered"] else
                [{**form, "policy": "unchanged retail base fallback"} for form in absent_upstream]),
            "forms_absent_from_upstream_portrait_donors": absent_upstream,
            "additional_portraits": extra,
            "custom_shadow_lugia": "separate authored asset contract"}


def _background(native_tile) -> tuple[tuple[int, int, int, int] | None, dict]:
    """Accept only a uniform colour shared by at least three exposed corners.

    A majority over the whole rim would confuse a large head with background.
    The native artwork supplies a flat colour only, never enlarged pixels.
    """
    samples = []
    for right, bottom in ((False, False), (True, False), (False, True), (True, True)):
        for distance in range(21):
            x = 41 - distance if right else distance
            y = 41 - distance if bottom else distance
            color = native_tile.pixelColor(x, y).getRgb()
            if color[3] >= 128:
                samples.append(color)
                break
    candidate, count = Counter(samples).most_common(1)[0] if samples else (None, 0)
    if count >= 3:
        return candidate, {"kind": "native uniform background", "rgba": list(candidate),
                           "method": "same opaque colour at three or four native circular-frame corners"}
    return None, {"kind": "upstream background retained", "reason": "no unambiguous flat native background"}


def render_xd_portrait(image, transform: Mapping, *, native_image, source_metadata: Mapping):
    """Keep every atlas cell at its original full framing in the round frame.

    All coloured image pixels come from the genuine HD donor. The native atlas
    supplies only its verified shared round alpha and, when unambiguous, a flat
    background colour. Its species silhouette never clips the donor.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter, QColor
    if transform.get("version") != 1 or transform.get("type") != "colosseum_portrait_to_xd":
        raise ValueError("Unsupported ordinary portrait transfer recipe.")
    member = transform["member"]
    donor = _CATALOG.get(member)
    if donor is None or source_metadata.get("sha256") != donor[4]:
        raise ValueError("The portrait donor does not match its release-pinned HD file.")
    _, width, source_key, target_key, _ = donor
    if (transform.get("source_native_key") != source_key or transform.get("target_native_key") != target_key or
            transform.get("native_size") != [width, 84] or
            transform.get("layout") != {"columns": width // 42, "rows": 2, "cell_size": 42} or
            (native_image.width(), native_image.height()) != (width, 84)):
        raise ValueError("Ordinary portrait atlas geometry or identity changed.")
    scale = source_metadata.get("source_scale")
    if scale not in (2, 4, 8, 16) or (image.width(), image.height()) != (width * 4, 336):
        raise ValueError("Ordinary portrait input must derive from a genuine HD atlas at output scale4.")
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    native_image = native_image.convertToFormat(QImage.Format.Format_RGBA8888)
    columns = width // 42
    tiles, native_tiles = [], []
    alphas = []
    for y in range(2):
        for x in range(columns):
            tiles.append(image.copy(x * 168, y * 168, 168, 168))
            native = native_image.copy(x * 42, y * 42, 42, 42)
            native_tiles.append(native)
            alphas.append(bytes(native.constBits())[3::4])
    # Retail XD's frame is normally binary; Tentacool has an antialiased circle
    # with four palette-quantisation differences at its shiny edge. Share the
    # first cell's geometric circle, never holes from a character silhouette.
    alpha = alphas[0]
    inner = [y * 42 + x for y in range(42) for x in range(42)
             if math.hypot(x + .5 - 21, y + .5 - 21) < 18]
    alpha_differences = [sum(a != b for a, b in zip(alpha, part, strict=True)) for part in alphas]
    if (any(difference > 16 for difference in alpha_differences) or
            any(part[at] != 255 for part in alphas for at in inner) or
            not 1300 <= sum(value > 0 for value in alpha) <= 1580 or
            any(alpha[y * 42:(y + 1) * 42] != alpha[y * 42:(y + 1) * 42][::-1] for y in range(42)) or
            any(alpha[y * 42:(y + 1) * 42] != alpha[(41 - y) * 42:(42 - y) * 42] for y in range(42)) or
            any(list(row[:21]) != sorted(row[:21]) for y in range(42)
                for row in (alpha[y * 42:(y + 1) * 42],))):
        raise ValueError("Native portrait alpha is not the shared XD round frame.")
    mask_rgba = bytes(channel for value in alpha for channel in (0, 0, 0, value))
    mask = QImage(mask_rgba, 42, 42, 168, QImage.Format.Format_RGBA8888).copy()
    mask = mask.scaled(168, 168, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    mask_alpha = bytes(mask.constBits())[3::4]
    # Preserve the pack's framing exactly. The native round boundary clips
    # outer corners, as the game does, without shrinking the head into a square.
    output = QImage(width * 4, 336, QImage.Format.Format_RGBA8888)
    output.fill(0)
    backgrounds = []
    for index, (tile, native) in enumerate(zip(tiles, native_tiles, strict=True)):
        color, background = _background(native)
        background["visible_only_where_donor_transparent"] = True
        backgrounds.append(background)
        if color is None:
            # The real donor's border is preserved; this is not a forced black
            # policy for a native portrait with an established coloured frame.
            color = tile.pixelColor(0, 0).getRgb()
        canvas = QImage(168, 168, QImage.Format.Format_RGBA8888)
        canvas.fill(QColor(*color[:3], 255))
        painter = QPainter(canvas)
        painter.drawImage(0, 0, tile)
        painter.end()
        rgba = bytearray(canvas.constBits())
        rgba[3::4] = mask_alpha
        for at in range(0, len(rgba), 4):
            if not rgba[at + 3]:
                rgba[at:at + 3] = bytes(3)
        rounded = QImage(bytes(rgba), 168, 168, 672, QImage.Format.Format_RGBA8888).copy()
        painter = QPainter(output)
        painter.drawImage((index % columns) * 168, (index // columns) * 168, rounded)
        painter.end()
    return output, {"kind": "upstream-hd-portrait-native-round-frame", "version": 1,
                    "source_member": member, "source_native_key": source_key,
                    "target_native_key": target_key, "source_sha256": donor[4],
                    "source_scale": scale, "output_scale": 4,
                    "cells": {"columns": columns, "rows": 2, "normal_shiny_and_sides_preserved": True},
                    "round_alpha": {"source": "first native cell geometric circle",
                                    "edge_palette_differences_normalized": alpha_differences},
                    "framing": {"uniform_scale": 1, "source_cell": [0, 0, 168, 168],
                                "destination_cell": [0, 0, 168, 168],
                                "edge_policy": "native round boundary only; original full framing",
                                "native_species_silhouette_used": False},
                    "backgrounds": backgrounds, "native_colour_bitmap_resampled": False}
