"""Reproduce the approved blue Japanese Nintendo logo from its true HD donor.

The source alpha and geometry remain byte-identical. Only the registered red
foreground calibration is mapped to the original Japanese blue. This is not
an exact RGBA alias. No native raster or ROM is used to create the HD artwork.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from orre_randomizer.hd_menu_catalog import _asset


def reproduce(pack_textures: Path):
    data, _ = _asset("menu-atlases/nontext-five-source.json")
    recipe = data["nintendo_color_adaptation"]
    name = recipe["source_file"]
    if Path(name).name != name:
        raise ValueError("Expected a flat source texture basename")
    root = pack_textures.resolve(strict=True)
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("External HD donor refused")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != recipe["source_sha256"]:
        raise ValueError("Authentic HD Nintendo donor changed")
    with Image.open(BytesIO(payload)) as source:
        image = source.convert("RGBA")
    if list(image.size) != recipe["source_dimensions"]:
        raise ValueError("Authentic HD Nintendo dimensions changed")
    pixels = bytearray(image.tobytes())
    for at in range(0, len(pixels), 4):
        blue = min(255, round(pixels[at] * 255 / recipe["source_red_foreground_mode"]))
        pixels[at:at + 3] = bytes((0, round(blue * 70 / 255), blue))
    image = Image.frombytes("RGBA", image.size, bytes(pixels))
    output = BytesIO()
    image.save(output, format="PNG")
    result = output.getvalue()
    if hashlib.sha256(result).hexdigest() != recipe["sha256"]:
        raise ValueError("Color adaptation differs from the approved output")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xd-pack-textures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("Choose a new output path")
    payload = reproduce(args.xd_pack_textures)
    with args.output.open("xb") as stream:
        stream.write(payload)
    print(json.dumps({"sha256": hashlib.sha256(payload).hexdigest(),
                      "native_bitmap_resampled": False, "alpha_and_geometry_preserved": True}))


if __name__ == "__main__":
    main()
