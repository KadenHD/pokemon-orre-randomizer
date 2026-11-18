"""Register reviewed native/HD model portraits and their source provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orre_randomizer.artwork import _png_pixels
from orre_randomizer.hd_overlays import _complete_lugia_hd_capture
from orre_randomizer.hd_packs import PACKS
from orre_randomizer.model_portraits import MANIFEST, portrait_filename, registered_portrait, violet_backdrop


def register(source: Path, pack_root: Path, *, check_only: bool = False) -> dict:
    """Check all eight variants before writing any application asset."""
    source, pack_root = Path(source).resolve(), Path(pack_root).resolve()
    models = pack_root / "models"
    metadata = json.loads((source / MANIFEST).read_text("utf-8"))
    expected = {portrait_filename(game, shiny, scale) for game in ("colosseum", "xd")
                for shiny in (False, True) for scale in (1, 4)}
    if (metadata.get("kind") != "native-mesh-render-portrait"
            or metadata.get("review_only") is not False
            or metadata.get("native_bitmap_upscaled_for_hd") is not False
            or set(metadata.get("files", {})) != expected):
        raise ValueError("A complete, reviewed native/HD portrait set is required")
    parent = (models / "hd-fullbody-manifest.json").read_bytes()
    _complete_lugia_hd_capture(json.loads(parent))
    hd = metadata["source"]["hd"]
    if (hd.get("pack") != PACKS["xd"].key
            or hd.get("archives") != [part.sha256 for part in PACKS["xd"].parts]
            or hd.get("material_manifest_sha256") != hashlib.sha256(parent).hexdigest()):
        raise ValueError("Portrait renders do not match the pinned model materials")
    text = json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
    if re.search(r"[A-Za-z]:[\\/]", text) or any(token in text for token in ('"private_pid"', '"source_card"', '"profile_path"')):
        raise ValueError("Private capture details cannot enter the portrait registry")
    payloads = {}
    for game in ("colosseum", "xd"):
        for shiny in (False, True):
            for scale in (1, 4):
                name = portrait_filename(game, shiny, scale)
                payload = registered_portrait(source, game=game, shiny=shiny, scale=scale)
                if payload is None:
                    raise ValueError("Missing portrait file")
                size = 42 * scale
                pixels = _png_pixels(payload, (size, size))
                expected_alpha = violet_backdrop(game=game, scale=scale)[3::4]
                if (pixels[3::4] != expected_alpha
                        or any(any(pixels[at:at + 3]) for at in range(0, len(pixels), 4) if not pixels[at + 3])):
                    raise ValueError("Portrait alpha does not match the native game frame")
                if game == "xd" and scale == 1:
                    # The native XD writer has one 256-entry RGB5A3 palette.
                    # Check the real representable colours before publishing;
                    # never discover an overflow while creating a user's ROM.
                    palette = {0}
                    for at in range(0, len(pixels), 4):
                        r, g, b, alpha = pixels[at:at + 4]
                        if alpha:
                            r, g, b = ((value * 31 + 127) // 255 for value in (r, g, b))
                            palette.add(0x8000 | r << 10 | g << 5 | b)
                    if len(palette) > 256:
                        raise ValueError("The native XD portrait exceeds its CI8 palette")
                payloads[name] = payload
    if check_only:
        return metadata
    provenance = pack_root / "provenance.json"
    catalogue = json.loads(provenance.read_text("utf-8"))
    for name, payload in payloads.items():
        catalogue["files"]["models/" + name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    encoded = text.encode("utf-8")
    catalogue["files"]["models/" + MANIFEST] = {"bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}
    catalogue["shadow_lugia_portrait_metadata"] = "models/" + MANIFEST
    # All file, format, source and privacy checks precede publication.
    for name, payload in payloads.items():
        (models / name).write_bytes(payload)
    (models / MANIFEST).write_bytes(encoded)
    provenance.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--pack-root", type=Path, default=ROOT / "orre_randomizer/assets/game")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    result = register(args.source, args.pack_root, check_only=args.check_only)
    print("Validated" if args.check_only else "Registered", len(result["files"]), "model portraits.")


if __name__ == "__main__":
    main()
