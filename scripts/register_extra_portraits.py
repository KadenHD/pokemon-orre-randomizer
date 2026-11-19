"""Validate and register the complete reviewed set of nine form portrait atlases.

The runtime loader checks every model, source pack, material, pose, crop and PNG
before any asset is written. Original portraits and existing font/model assets
are preserved. Use --check-only for a complete review without publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orre_randomizer.hd_extra_portraits import (
    _CATALOG, _registered_extra_portrait, extra_portraits_registered, portrait_origin,
)


MANIFEST = "extra-portraits.json"
MATERIAL_CATALOGUE = "form-materials/catalog.json"


def _linked_material_catalogue(pack_root: Path, metadata: dict, portrait_bytes: bytes):
    """Refresh a framing-only registry link after authenticating every material.

    A portrait registration must not silently bless changed stock paint. An
    existing catalogue and its PNGs must still match both their global
    provenance and the incoming, independently validated capture recipes.
    """
    path = pack_root / MATERIAL_CATALOGUE
    if path.is_symlink() or path.is_junction() or path.parent.is_symlink() or path.parent.is_junction():
        raise ValueError("Linked stock form-material assets cannot be symbolic links.")
    if not path.exists():
        return None
    from orre_randomizer.hd_menu_catalog import SUPPORTED
    from orre_randomizer.hd_packs import PACKS

    before = path.read_bytes()
    provenance = json.loads((pack_root / "provenance.json").read_bytes())
    expected = provenance.get("files", {}).get(MATERIAL_CATALOGUE, {})
    if (expected.get("bytes") != len(before) or
            expected.get("sha256") != hashlib.sha256(before).hexdigest()):
        raise ValueError("Linked stock form-material catalogue integrity check failed.")
    catalogue = json.loads(before)
    if (catalogue.get("schema") != 1 or catalogue.get("kind") != "reviewed-extra-form-stock-materials"
            or catalogue.get("review_only") is not False or catalogue.get("native_bitmap_resampled") is not False
            or not isinstance(catalogue.get("records"), list) or len(catalogue["records"]) != 43):
        raise ValueError("Linked stock form-material catalogue is unreviewed.")
    reviewed = {}
    for capture in metadata["captures"].values():
        for row in capture["material_recipes"]:
            if "sha256" not in row:
                continue
            identity = row["sha256"], capture["pack"]
            if reviewed.setdefault(row["target"], identity) != identity:
                raise ValueError("Incoming portraits contain conflicting stock material identities.")
    seen = set()
    for row in catalogue["records"]:
        name = row.get("file", "")
        match = re.fullmatch(r"tex1_(\d+)x(\d+)_[0-9a-f]+(?:_[0-9a-f]+)?_\d+\.png", name)
        if (match is None or name in seen or row.get("pack") not in PACKS
                or reviewed.get(name) != (row.get("sha256"), PACKS[row["pack"]].key)
                or row.get("native_bitmap_resampled") is not False
                or not isinstance(row.get("game_ids"), list) or not row["game_ids"]
                or set(row["game_ids"]) - SUPPORTED):
            raise ValueError("Portrait and linked stock form-material identities differ.")
        native = list(map(int, match.groups()))
        if row.get("native_dimensions") != native or row.get("dimensions") != [v * 4 for v in native]:
            raise ValueError("Linked stock form-material dimensions differ.")
        material = path.parent / name
        if material.is_symlink() or material.is_junction():
            raise ValueError("Linked stock form-material assets cannot be symbolic links.")
        payload = material.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        record = provenance.get("files", {}).get("form-materials/" + name, {})
        if (len(payload) != row.get("bytes") or digest != row["sha256"]
                or record.get("bytes") != len(payload) or record.get("sha256") != digest):
            raise ValueError("Linked stock form-material PNG integrity check failed.")
        seen.add(name)
    catalogue["portrait_registry_sha256"] = hashlib.sha256(portrait_bytes).hexdigest()
    after = (json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n").encode("utf8")
    return path, before, after


def register(source: Path, pack_root: Path, *, check_only: bool = False) -> dict:
    """Check the full set first, then publish it without replacing other assets."""
    source, pack_root = Path(source), Path(pack_root)
    if source.is_symlink() or pack_root.is_symlink():
        raise ValueError("Portrait source and asset root cannot be symbolic links.")
    source, pack_root = source.resolve(), pack_root.resolve()
    if not extra_portraits_registered(source):
        raise ValueError("All nine atlas entries must have passed review before registration.")
    manifest_path = source / MANIFEST
    metadata = json.loads(manifest_path.read_text("utf8"))
    targets = {game + "/" + member for (game, _), (member, _) in _CATALOG.items()}
    if (set(metadata["files"]) != targets or metadata.get("native_bitmap_upscaled_for_hd") is not False):
        raise ValueError("The reviewed registry must contain exactly the nine native form atlases.")
    text = json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
    if (re.search(r"[A-Za-z]:[\\/]", text) or
            any(token in text for token in ('"pid"', '"creation_time"', '"source_card"', '"profile_path"'))):
        raise ValueError("Private capture paths or process details cannot enter the public registry.")
    payloads = {MANIFEST: text.encode("utf8")}
    for (game, key), (member, _) in _CATALOG.items():
        origin = portrait_origin(game, key, (42, 84))
        _registered_extra_portrait(origin, asset_directory=source)
        name = metadata["files"][game + "/" + member]["file"]
        if name in payloads:
            raise ValueError("Every form atlas requires its own registered asset filename.")
        payloads[name] = (source / name).read_bytes()
    linked_catalogue = _linked_material_catalogue(pack_root, metadata, payloads[MANIFEST])
    if check_only:
        return metadata
    destination = pack_root / "models/extra-portraits"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError("The extra portrait destination must be an ordinary directory.")
    if destination.exists() and any(path.name not in payloads for path in destination.iterdir()):
        raise ValueError("The destination contains an unregistered extra portrait file.")
    if any((destination / name).is_symlink() for name in payloads):
        raise ValueError("Registered portrait files cannot be symbolic links.")
    provenance_path = pack_root / "provenance.json"
    provenance_bytes = provenance_path.read_bytes()
    provenance = json.loads(provenance_bytes)
    for name, payload in payloads.items():
        provenance["files"]["models/extra-portraits/" + name] = {
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    provenance["extra_portrait_metadata"] = "models/extra-portraits/" + MANIFEST
    if linked_catalogue is not None:
        _, _, linked_payload = linked_catalogue
        provenance["files"][MATERIAL_CATALOGUE] = dict(provenance["files"][MATERIAL_CATALOGUE],
            bytes=len(linked_payload), sha256=hashlib.sha256(linked_payload).hexdigest())
    encoded = (json.dumps(provenance, indent=2, ensure_ascii=False) + "\n").encode("utf8")
    publication = {destination / name: payload for name, payload in payloads.items()}
    if linked_catalogue is not None:
        linked_path, linked_before, linked_payload = linked_catalogue
        publication[linked_path] = linked_payload
    previous = {path: path.read_bytes() if path.exists() else None for path in publication}
    destination.mkdir(parents=True, exist_ok=True)
    if provenance_path.read_bytes() != provenance_bytes:
        raise RuntimeError("The global provenance changed during portrait validation; retry without overwriting it.")
    if linked_catalogue is not None and linked_path.read_bytes() != linked_before:
        raise RuntimeError("The linked stock form-material catalogue changed during portrait validation.")
    try:
        for path, payload in publication.items():
            path.write_bytes(payload)
        provenance_path.write_bytes(encoded)
    except BaseException:
        for path, payload in previous.items():
            if payload is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(payload)
        provenance_path.write_bytes(provenance_bytes)
        raise
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--pack-root", type=Path, default=ROOT / "orre_randomizer/assets/game")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    result = register(args.source, args.pack_root, check_only=args.check_only)
    print("Validated" if args.check_only else "Registered", len(result["files"]), "additional portrait atlases.")


if __name__ == "__main__":
    main()
