"""Authenticated x4 paint for stock weather/Deoxys models, separate from portraits."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

from .hd_menu_catalog import SUPPORTED, _asset, _asset_bytes
from .hd_packs import PACKS

CATALOGUE = "form-materials/catalog.json"


def material_recipes(game_id: str) -> dict:
    if game_id not in SUPPORTED:
        raise ValueError("Unknown extra-form material game identity")
    data, digest = _asset(CATALOGUE)
    if (data.get("schema") != 1 or data.get("kind") != "reviewed-extra-form-stock-materials"
            or data.get("review_only") is not False or data.get("native_bitmap_resampled") is not False
            or not isinstance(data.get("records"), list) or len(data["records"]) != 43):
        raise ValueError("Extra-form model materials are unreviewed")
    portrait, portrait_digest = _asset("models/extra-portraits/extra-portraits.json")
    if portrait_digest != data.get("portrait_registry_sha256"):
        raise ValueError("Portrait and stock form-material sources differ")
    reviewed = {row["target"]: row["sha256"] for capture in portrait["captures"].values()
                for row in capture["material_recipes"] if "sha256" in row}
    result, seen = {}, set()
    for row in data["records"]:
        name = row.get("file", "")
        match = re.fullmatch(r"tex1_(\d+)x(\d+)_[0-9a-f]+(?:_[0-9a-f]+)?_\d+\.png", name)
        if (match is None or name in seen or row.get("native_bitmap_resampled") is not False
                or not isinstance(row.get("game_ids"), list) or not row["game_ids"]
                or set(row["game_ids"]) - SUPPORTED or row.get("pack") not in PACKS
                or reviewed.get(name) != row.get("sha256")):
            raise ValueError("Stock form-material identity differs")
        native = list(map(int, match.groups()))
        if row.get("native_dimensions") != native or row.get("dimensions") != [v * 4 for v in native]:
            raise ValueError("Stock form-material dimensions differ")
        seen.add(name)
        if game_id in row["game_ids"]:
            result[name] = dict(deepcopy(row), catalogue_sha256=digest)
    return result


def prepare_form_materials(game_id: str, pack_roots: dict, destination: Path) -> dict:
    """Publish exact reviewed bytes; never write into either installed pack."""
    rows = material_recipes(game_id)
    report = {"game_id": game_id, "files": {}, "assets": [], "native_rom_changed": False}
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Stock form-material output cannot be linked")
    target = destination.resolve()
    required = sorted({row["pack"] for row in rows.values()})
    for game in required:
        pack = PACKS[game]
        if game not in pack_roots:
            raise ValueError("Required stock form-material source pack is absent")
        folder = Path(pack_roots[game]).resolve()
        folder = folder.parent if folder.name == "Textures" else folder
        if target == folder or target.is_relative_to(folder):
            raise ValueError("Stock form materials cannot write inside a source pack")
        marker = json.loads((folder / "installed.json").read_text("utf8"))
        if marker.get("key") != pack.key or marker.get("archives") != [p.sha256 for p in pack.parts]:
            raise ValueError("Stock form-material source pack differs from the pinned release")
    generated = []
    for name, row in rows.items():
        payload, digest = _asset_bytes("form-materials/" + name)
        if digest != row["sha256"] or len(payload) != row["bytes"]:
            raise ValueError("Stock form-material artwork changed")
        path = target / name
        if path.is_symlink() or path.is_junction() or (path.exists() and path.read_bytes() != payload):
            raise ValueError("Conflicting stock form-material output")
        report["files"][name] = digest
        report["assets"].append({"file": name, "sha256": digest, "origin": row})
        generated.append((path, payload))
    target.mkdir(parents=True, exist_ok=True)
    for path, payload in generated:
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(payload)
    return dict(report, required_packs=required, active=True)
