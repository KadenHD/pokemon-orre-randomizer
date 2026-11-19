"""Authenticated native identities and vector recipes for menu atlas additions."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import PurePosixPath
import struct

CATALOGUE = "menu-atlases/catalog.json"
VECTORS = "menu-atlases/vector-outlines.json"
CONTRACT = "orre-menu-atlas-vector-derivatives-v1"
# Included in hud_recipes/cache identity independently of data-file hashes.
RENDERER_REVISION = 11
SUPPORTED = frozenset(("GC6E01", "GC6P01", "GC6J01", "GXXE01", "GXXP01", "GXXJ01"))


def _asset_bytes(name):
    from .resources import bundle_root
    root = bundle_root()
    path = root / name
    if (path.is_symlink() or path.is_junction() or path.parent.is_symlink()
            or path.parent.is_junction() or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError("Linked or external menu recipe is unavailable")
    data = path.read_bytes()
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("Menu recipe exceeds its bounded size")
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf8"))
    expected = provenance.get("files", {}).get(name, {})
    if (expected.get("bytes") != len(data)
            or expected.get("sha256") != hashlib.sha256(data).hexdigest()):
        raise ValueError("Menu recipe differs from registered artwork")
    return data, hashlib.sha256(data).hexdigest()


def _asset(name):
    data, digest = _asset_bytes(name)
    return json.loads(data), digest


def menu_image(name: str, native_size: tuple[int, int]):
    """Load registered high-resolution author artwork with its exact digest."""
    from .hd_images import LoadedTexture
    from PySide6.QtGui import QImage
    logical = PurePosixPath(name)
    if (len(logical.parts) != 2 or logical.parts[0] != "menu-atlases"
            or logical.suffix != ".png" or ":" in name or "\\" in name):
        raise ValueError("Unknown registered menu background")
    payload, digest = _asset_bytes(name)
    dimensions = tuple(int(v) * 4 for v in native_size)
    if (len(dimensions) != 2 or any(not 1 <= value <= 8192 for value in dimensions)
            or dimensions[0] * dimensions[1] > 16 * 1024 * 1024
            or len(payload) < 33 or payload[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            or struct.unpack_from(">II", payload, 16) != dimensions):
        raise ValueError("Registered menu background dimensions changed")
    image = QImage.fromData(payload, "PNG").convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull() or (image.width(), image.height()) != dimensions:
        raise ValueError("Cannot decode registered menu background")
    return LoadedTexture(image=image, metadata={"file": name, "physical_file": name,
        "sha256": digest, "width": image.width(), "height": image.height(),
        "source_scale": 4, "format": "PNG", "mip_levels": 1,
        "kind": "registered-authored-menu-artwork"})


def menu_artwork_metadata(name: str, expected_sha256: str) -> dict:
    logical = PurePosixPath(name)
    if (len(logical.parts) != 2 or logical.parts[0] != "menu-atlases"
            or logical.suffix != ".json" or ":" in name or "\\" in name):
        raise ValueError("Unknown registered menu artwork provenance")
    data, digest = _asset(name)
    if digest != expected_sha256 or data.get("review_only") is not False:
        raise ValueError("Menu artwork provenance is unreviewed or changed")
    return data


@lru_cache(maxsize=1)
def _catalogue():
    data, digest = _asset(CATALOGUE)
    if (data.get("schema") != 1 or data.get("contract") != CONTRACT
            or data.get("review_only") is not False or not isinstance(data.get("records"), list)
            or not 1 <= len(data["records"]) <= 1024):
        raise ValueError("Menu atlas catalogue is not reviewed")
    records = {}
    for row in data["records"]:
        key = row.get("target")
        groups = row.get("game_ids")
        if (not isinstance(key, str) or key in records or not key.startswith("tex1_")
                or not key.endswith(".png") or "/" in key or "\\" in key or ":" in key
                or not isinstance(groups, list) or not groups or set(groups) - SUPPORTED
                or row.get("game") not in ("colosseum", "xd")
                or row.get("transform", {}).get("target") != key
                or row["transform"].get("vectors_sha256") != data.get("vectors_sha256")):
            raise ValueError("Menu atlas identity or dependency differs")
        records[key] = row
    return records, data["vectors_sha256"], digest


def menu_recipes(game_id: str) -> dict:
    """Return only keys actually observed on this original game/revision."""
    if game_id not in SUPPORTED:
        raise ValueError("Unknown menu game identity")
    records, _, _ = _catalogue()
    return {key: dict(deepcopy({field: value for field, value in row.items()
                               if field not in ("target", "game_ids")}),
                      renderer_revision=RENDERER_REVISION)
            for key, row in records.items() if game_id in row["game_ids"]}


def menu_origin(game_id: str, native_key: str, native_size: tuple[int, int]):
    recipe = menu_recipes(game_id).get(native_key)
    if recipe is not None and tuple(native_size) != tuple(recipe["transform"]["native_dimensions"]):
        raise ValueError("Menu atlas native dimensions changed")
    return recipe


@lru_cache(maxsize=1)
def _vectors() -> dict:
    data, digest = _asset(VECTORS)
    _, expected, _ = _catalogue()
    if (digest != expected or data.get("schema") != 1
            or data.get("kind") != "captured-vector-font-outlines"
            or not {"latin", "japanese"} <= set(data.get("families", {}))
            or set(data.get("families", {})) - {"latin", "latin_bold", "japanese"}):
        raise ValueError("Menu font outline provenance differs")
    for family in data["families"].values():
        glyphs = family.get("glyphs")
        if not isinstance(glyphs, dict) or not 1 <= len(glyphs) <= 1500:
            raise ValueError("Invalid menu font corpus")
        for char, glyph in glyphs.items():
            if (not isinstance(char, str) or len(char) != 1
                    or not 0 <= glyph.get("advance", -1) <= 4000
                    or not isinstance(glyph.get("path"), list) or len(glyph["path"]) > 6000):
                raise ValueError("Invalid captured menu glyph")
            for command in glyph["path"]:
                if (not command or command[0] not in ("M", "L", "C")
                        or len(command) != (7 if command[0] == "C" else 3)
                        or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 4000
                               for v in command[1:])):
                    raise ValueError("Invalid menu vector coordinates")
    palettes = data.get("palettes", {})
    if not isinstance(palettes, dict) or len(palettes) > 128:
        raise ValueError("Invalid menu HD palette corpus")
    for palette in palettes.values():
        rows = palette.get("rows")
        if (not isinstance(rows, list) or not 1 <= len(rows) <= 4096
                or any(not isinstance(color, (tuple, list)) or len(color) != 4
                       or any(type(value) is not int or not 0 <= value <= 255 for value in color)
                       for color in rows)):
            raise ValueError("Invalid menu HD gradient samples")
    return data


def menu_vectors() -> dict:
    """Return an independent copy; callers cannot mutate another preparation."""
    return deepcopy(_vectors())
