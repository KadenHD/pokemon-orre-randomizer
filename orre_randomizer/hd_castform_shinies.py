"""Separate, authenticated x4 artwork for the custom shiny weather resources.

Retail weather atlases and the 43 stock form paints retain their identities.
Only exact registered custom texture keys are published into a party's staged
HD view; source packs and the embedded native model data are never rewritten.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct

from .hd_extra_portrait_catalog import HD_MATERIAL_SOURCE_PINS
from .hd_images import resolve_texture
from .hd_menu_catalog import SUPPORTED, _asset_bytes
from .hd_packs import PACKS
from .resources import bundle_root


CATALOGUE = "castform-shinies/catalog.json"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,125}\.png\Z")
_KEY = re.compile(r"tex1_(\d+)x(\d+)(?:_m)?_[0-9a-f]{16}(?:_[0-9a-f]{16})?_(\d+)\.png\Z")
_FORMATS = frozenset((0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 14))


def _source_records(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 128:
        raise ValueError("Custom Castform paint sources are absent or invalid")
    for identifier, source in value.items():
        if (not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9_-]{1,96}", identifier)
                or not isinstance(source, dict) or not isinstance(source.get("pack"), str)
                or source["pack"] not in PACKS):
            raise ValueError("Invalid custom Castform paint source")
        key, physical, digest = source.get("native_key"), source.get("physical_file"), source.get("sha256")
        if (not isinstance(key, str) or _KEY.fullmatch(key) is None
                or not isinstance(physical, str) or Path(physical).name != physical
                or ":" in physical or "\\" in physical or "/" in physical
                or Path(physical).suffix.lower() not in (".png", ".dds")
                or not isinstance(digest, str) or _SHA.fullmatch(digest) is None):
            raise ValueError("Invalid custom Castform source identity")
        logical = re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", Path(physical).stem + ".png")
        base = re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", key)
        if logical != base or HD_MATERIAL_SOURCE_PINS[source["pack"]].get(base) != digest:
            raise ValueError("Custom Castform paint differs from its pinned HD source")
    return value


def castform_shiny_recipes(game_id: str) -> dict:
    """Return the reviewed selected keys and an identity for the immutable cache.

    Absence supports older builds without the optional authored resources. A
    present but unregistered or malformed catalogue always fails closed.
    """
    if game_id not in SUPPORTED:
        raise ValueError("Unknown custom Castform game identity")
    path = bundle_root() / CATALOGUE
    if path.is_symlink() or path.is_junction():
        raise ValueError("Custom Castform catalogue cannot be linked")
    if not path.exists():
        return {"game_id": game_id, "active": False, "catalogue_sha256": None, "files": []}
    raw, digest = _asset_bytes(CATALOGUE)
    catalogue = json.loads(raw)
    if (not isinstance(catalogue, dict) or catalogue.get("schema") != 1
            or catalogue.get("kind") != "castform-shiny-native-and-hd"
            or catalogue.get("review_only") is not False
            or not isinstance(catalogue.get("source_models"), dict) or not catalogue["source_models"]
            or not isinstance(catalogue.get("faces"), dict) or not catalogue["faces"]
            or not isinstance(catalogue.get("files"), list) or not 1 <= len(catalogue["files"]) <= 256):
        raise ValueError("Custom Castform native/HD artwork is unreviewed")
    sources = _source_records(catalogue.get("material_sources"))
    selected, names, file_identities = [], set(), {}
    for item in catalogue["files"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid custom Castform artwork record")
        name, key, role = item.get("file"), item.get("native_key"), item.get("role")
        match = _KEY.fullmatch(key) if isinstance(key, str) else None
        size = item.get("native_dimensions")
        games, references, pack = item.get("game_ids"), item.get("material_sources"), item.get("required_pack")
        if (not isinstance(name, str) or _FILE.fullmatch(name) is None or match is None
                or role not in ("material", "portrait") or not isinstance(pack, str) or pack not in PACKS
                or not isinstance(games, list) or not games or any(not isinstance(v, str) for v in games)
                or len(games) != len(set(games))
                or set(games) - SUPPORTED
                or not isinstance(size, list) or len(size) != 2
                or any(type(v) is not int or not 1 <= v <= 1024 for v in size)
                or size != list(map(int, match.groups()[:2])) or int(match.group(3)) not in _FORMATS
                or not isinstance(item.get("dimensions"), list) or len(item["dimensions"]) != 2
                or any(type(v) is not int for v in item["dimensions"])
                or item["dimensions"] != [v * 4 for v in size]
                or not isinstance(item.get("sha256"), str) or _SHA.fullmatch(item["sha256"]) is None
                or not isinstance(item.get("native_rgba_sha256"), str)
                or _SHA.fullmatch(item["native_rgba_sha256"]) is None
                or type(item.get("bytes")) is not int or not 1 <= item["bytes"] <= 12 * 1024 * 1024
                or not isinstance(references, list) or not references
                or any(not isinstance(v, str) for v in references) or len(references) != len(set(references))
                or any(identifier not in sources or sources[identifier]["pack"] != pack for identifier in references)):
            raise ValueError("Custom Castform artwork identity or dimensions differ")
        if role == "portrait" and (size != [42, 84] or
                len({game.startswith("GC6") for game in games}) != 1):
            raise ValueError("Custom Castform portraits require one native square or round game frame")
        identity = item["sha256"], item["bytes"]
        if file_identities.setdefault(name, identity) != identity:
            raise ValueError("Conflicting custom Castform source filenames")
        for game in games:
            if (game, key) in names:
                raise ValueError("Duplicate custom Castform native texture key")
            names.add((game, key))
        if game_id in games:
            selected.append(deepcopy(item))
    if selected and {item["role"] for item in selected} != {"material", "portrait"}:
        raise ValueError("Custom Castform HD requires both model paint and portrait artwork")
    used = {identifier for item in selected for identifier in item["material_sources"]}
    return {"game_id": game_id, "active": bool(selected), "catalogue_sha256": digest,
            "files": selected, "material_sources": {name: deepcopy(sources[name]) for name in sorted(used)}}


def _checked_pack(game, pack_roots, destination=None):
    if game not in pack_roots:
        raise ValueError("Required custom Castform source pack is absent")
    source = Path(pack_roots[game]).resolve()
    source = source.parent if source.name == "Textures" else source
    if destination is not None and (destination == source or destination.is_relative_to(source)):
        raise ValueError("Custom Castform artwork cannot write inside a source pack")
    pack = PACKS[game]
    marker = source / "installed.json"
    if marker.is_symlink() or marker.is_junction():
        raise ValueError("Custom Castform source-pack marker cannot be linked")
    data = json.loads(marker.read_bytes())
    if (not isinstance(data, dict) or data.get("key") != pack.key
            or data.get("archives") != [p.sha256 for p in pack.parts]):
        raise ValueError("Custom Castform source pack differs from its pinned release")
    return source


def _checked_image(payload, item, game_id):
    from PySide6.QtGui import QImage
    if (len(payload) < 33 or payload[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            or list(struct.unpack_from(">II", payload, 16)) != item["dimensions"]):
        raise ValueError("Custom Castform x4 image header dimensions changed")
    image = QImage.fromData(payload, "PNG").convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull() or [image.width(), image.height()] != item["dimensions"]:
        raise ValueError("Custom Castform x4 image dimensions changed")
    if item["role"] != "portrait":
        return image
    pixels = bytes(image.constBits())
    alpha = pixels[3::4]
    if game_id.startswith("GC6"):
        if any(value != 255 for value in alpha):
            raise ValueError("Custom Colosseum Castform portraits require an opaque square")
    else:
        first, second = alpha[:168 * 168], alpha[168 * 168:]
        corners = (0, 167, 168 * 167, 168 * 168 - 1)
        if (first != second or any(first[at] for at in corners)
                or not 1300 * 16 <= sum(value > 127 for value in first) <= 1580 * 16
                or any(pixels[at:at + 3] != b"\0\0\0" for at in range(0, len(pixels), 4) if not pixels[at + 3])):
            raise ValueError("Custom XD Castform portraits require the shared native round frame")
    return image


def _checked_source_paints(recipes, pack_roots, destination=None):
    required = sorted({item["required_pack"] for item in recipes["files"]})
    packs = {game: _checked_pack(game, pack_roots, destination) for game in required}
    for source in recipes["material_sources"].values():
        root = packs[source["pack"]]
        path = resolve_texture(root / "Textures", source["native_key"])
        if (path is None or path.is_symlink() or path.is_junction()
                or not path.resolve().is_relative_to(root) or path.name != source["physical_file"]
                or path.stat().st_size > 32 * 1024 * 1024):
            raise ValueError("Custom Castform pinned HD paint is absent or linked")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != source["sha256"]:
            raise ValueError("Custom Castform pinned HD paint integrity check failed")
    return required


def _checked_asset(item, game_id):
    payload, digest = _asset_bytes("castform-shinies/" + item["file"])
    if digest != item["sha256"] or len(payload) != item["bytes"]:
        raise ValueError("Custom Castform registered x4 artwork changed")
    image = _checked_image(payload, item, game_id)
    return payload, image


def _origin(game_id, item):
    return {"game": item["required_pack"], "required_packs": [item["required_pack"]],
        "native_source": "registered custom shiny Castform weather resource",
        "transform": {"type": "custom-castform-shiny", "version": 1,
            "game_id": game_id, "native_key": item["native_key"], "role": item["role"],
            "native_size": item["native_dimensions"], "native_rgba_sha256": item["native_rgba_sha256"]}}


def castform_shiny_origin(game_id: str, native_key: str, native_size, native_rgba_sha256: str,
                          *, role: str) -> dict | None:
    """Bind a captured custom resource to its exact native pixels and x4 route."""
    recipes = castform_shiny_recipes(game_id)
    item = next((row for row in recipes["files"] if row["native_key"] == native_key), None)
    if item is None:
        return None
    if (list(native_size) != item["native_dimensions"] or native_rgba_sha256 != item["native_rgba_sha256"]
            or role != item["role"]):
        raise ValueError("Captured custom Castform native pixels or resource role differ")
    return _origin(game_id, item)


def render_castform_shiny_overlay(origin: dict, *, native_image, pack_roots: dict):
    """Read exact registered PNG bytes; never resample the captured native image."""
    from PySide6.QtGui import QImage
    transform = origin.get("transform", {})
    if transform.get("type") != "custom-castform-shiny" or transform.get("version") != 1:
        raise ValueError("Unknown custom Castform HD transform")
    native = native_image.convertToFormat(QImage.Format.Format_RGBA8888)
    rgba = hashlib.sha256(bytes(native.constBits())).hexdigest()
    expected = castform_shiny_origin(transform.get("game_id", ""), transform.get("native_key", ""),
        (native.width(), native.height()), rgba, role=transform.get("role", ""))
    if expected is None or origin != expected:
        raise ValueError("Captured custom Castform HD recipe changed")
    recipes = castform_shiny_recipes(transform["game_id"])
    _checked_source_paints(recipes, pack_roots)
    item = next(row for row in recipes["files"] if row["native_key"] == transform["native_key"])
    payload, _ = _checked_asset(item, transform["game_id"])
    return payload, {"kind": "registered-custom-castform-shiny", "role": item["role"],
        "catalogue_sha256": recipes["catalogue_sha256"], "native_rgba_sha256": rgba,
        "native_key": item["native_key"], "sha256": item["sha256"],
        "source_paints": recipes["material_sources"], "native_bitmap_resampled": False}


def prepare_castform_shiny_overlays(game_id: str, pack_roots: dict, destination: Path) -> dict:
    """Validate all selected inputs before publishing exact reviewed x4 PNGs."""
    recipes = castform_shiny_recipes(game_id)
    report = {"game_id": game_id, "active": recipes["active"], "files": {}, "assets": [],
              "required_packs": [], "native_rom_changed": False,
              "catalogue_sha256": recipes["catalogue_sha256"],
              "source_paints": recipes.get("material_sources", {})}
    if not recipes["active"]:
        return report
    destination = Path(destination)
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Custom Castform output cannot be linked")
    target = destination.resolve()
    if target == bundle_root().resolve() or target.is_relative_to(bundle_root().resolve()):
        raise ValueError("Custom Castform output cannot write inside bundled artwork")
    required = _checked_source_paints(recipes, pack_roots, target)
    staged = []
    for item in recipes["files"]:
        payload, _ = _checked_asset(item, game_id)
        digest = item["sha256"]
        path = target / item["native_key"]
        if path.is_symlink() or path.is_junction() or (path.exists() and path.read_bytes() != payload):
            raise ValueError("Conflicting custom Castform HD output")
        staged.append((path, payload))
        report["files"][item["native_key"]] = digest
        report["assets"].append({"file": item["native_key"], "sha256": digest, "role": item["role"],
            "catalogue_sha256": recipes["catalogue_sha256"], "origin": item})
    target.mkdir(parents=True, exist_ok=True)
    for path, payload in staged:
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(payload)
    return dict(report, required_packs=required)
