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
    encoded = (json.dumps(provenance, indent=2, ensure_ascii=False) + "\n").encode("utf8")
    previous = {name: (destination / name).read_bytes() if (destination / name).exists() else None
                for name in payloads}
    destination.mkdir(parents=True, exist_ok=True)
    if provenance_path.read_bytes() != provenance_bytes:
        raise RuntimeError("The global provenance changed during portrait validation; retry without overwriting it.")
    try:
        for name, payload in payloads.items():
            (destination / name).write_bytes(payload)
        provenance_path.write_bytes(encoded)
    except BaseException:
        for name, payload in previous.items():
            path = destination / name
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
