"""Reproduce a registered XD sheet background using the pinned real HD PNG.

The regional recipe records the changed caption interiors and Japan's separate
370-pixel footer. Text is rendered separately by render_hd_menu_atlases.py.
No native bitmap, ROM, emulator or external font is used by this authoring step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from orre_randomizer.hd_menu_catalog import SUPPORTED, menu_recipes


def reproduce(pack: Path, language: str, output: Path, *, auxiliary: bool = False) -> dict:
    records = {key: row for game in SUPPORTED for key, row in menu_recipes(game).items()}
    family = "xd-pokemon-sheet-aux" if auxiliary else "xd-pokemon-sheet"
    candidates = [row for row in records.values()
                  if row["transform"]["family"] == family
                  and row["transform"]["language"] == language]
    if len(candidates) != 1 or output.exists():
        raise ValueError("Use one registered language and a new output path")
    record = candidates[0]
    recipe = record["transform"]
    source = recipe["author_source"]
    name = source["donor"]
    if Path(name).name != name:
        raise ValueError("The registered donor filename is invalid")
    donor = pack / name
    if hashlib.sha256(donor.read_bytes()).hexdigest() != source["donor_sha256"]:
        raise ValueError("The HD sheet donor differs from its pinned source")
    image = Image.open(donor).convert("RGBA")
    expected_size = (1272, 468) if auxiliary else (1912, 1600)
    if image.size != expected_size:
        raise ValueError("Unexpected source sheet dimensions")
    clears = source["clear_regions_native"] if auxiliary else source["background_clear_regions_native"]
    fills = [(0, 0, 0, 0)] * len(clears) if auxiliary else source["background_clear_fills_rgba"]
    original = image.copy() if auxiliary else None
    for box, fill in zip(clears, fills, strict=True):
        image.paste(tuple(fill), tuple(value * 4 for value in box))
    for old, new in source.get("placements_native", []):
        if (old[2] - old[0], old[3] - old[1]) != (new[2] - new[0], new[3] - new[1]):
            raise ValueError("The registered auxiliary artwork must keep its exact HD scale")
        image.paste(original.crop(tuple(value * 4 for value in old)), (new[0] * 4, new[1] * 4))
    japanese = source.get("japanese_background")
    if japanese is not None:
        width, height = japanese["native_dimensions"]
        image = image.crop((0, 0, width * 4, height * 4))
        for box in japanese["extra_clear_regions_native"]:
            image.paste((0, 0, 0, 0), tuple(value * 4 for value in box))
        draw = ImageDraw.Draw(image)
        for box, color in japanese["rectangles_native"]:
            draw.rectangle(tuple(value * 4 for value in box), fill=color)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    if digest != record["source_sha256"]:
        raise RuntimeError("Reproduced sheet differs from the registered background")
    return {"language": language, "dimensions": list(image.size), "sha256": digest,
            "native_raster_enlarged": False, "rom_used": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path, help="Pinned XD HD Textures directory")
    parser.add_argument("--language", required=True, choices=("en", "fr", "de", "it", "es", "ja"))
    parser.add_argument("--output", required=True, type=Path, help="New PNG destination")
    parser.add_argument("--auxiliary", action="store_true", help="Reproduce Japan's separate 318x117 atlas")
    args = parser.parse_args()
    print(json.dumps(reproduce(args.pack, args.language, args.output, auxiliary=args.auxiliary), indent=2))


if __name__ == "__main__":
    main()
