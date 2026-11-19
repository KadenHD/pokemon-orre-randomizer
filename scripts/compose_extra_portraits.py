"""Recompose reviewed form portraits from raw GPU frames, without a new capture.

Only the declared square crop, premultiplied reduction and native frame geometry
are applied. This offline tool does not qualify a model or approve a capture;
the application registry separately checks model, material, camera and pose
receipts. No original portrait colour bitmap supplies any output colour.

Install tool dependencies with: pip install -e ".[artwork]"
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import platform
import zlib

import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orre_randomizer.artwork import _png
from orre_randomizer.hd_extra_portraits import portrait_origin


NATIVE_SIDE = 42
OUTPUT_SIDE = 168
CIRCLE_CENTER = (21, 21)
CIRCLE_RADIUS = 22.5


@lru_cache(maxsize=1)
def _smooth_circle_alpha() -> bytes:
    """Evaluate the actual native disk with 8x8 coverage per HD output pixel.

    Filtering the low resolution binary mask rings around its staircase edge.
    The geometric disk has no ringing, disconnected dots or enlarged pixels.
    """
    scale, samples = 4, 8
    center = CIRCLE_CENTER[0] * scale
    radius_squared = (CIRCLE_RADIUS * scale) ** 2
    values = []
    for y in range(OUTPUT_SIDE):
        vertical = [(y + (step + .5) / samples - center) ** 2 for step in range(samples)]
        for x in range(OUTPUT_SIDE):
            horizontal = [(x + (step + .5) / samples - center) ** 2 for step in range(samples)]
            inside = sum(dx + dy < radius_squared for dx in horizontal for dy in vertical)
            values.append((255 * inside + samples ** 2 // 2) // samples ** 2)
    return bytes(values)


def native_circle_alpha(native: Image.Image) -> bytes:
    """Verify both native cells, then rebuild their shared geometric HD frame."""
    if native.size != (NATIVE_SIDE, NATIVE_SIDE * 2):
        raise ValueError("The native portrait guide must be a 42x84 atlas.")
    alpha = native.convert("RGBA").getchannel("A").tobytes()
    expected = bytes(255 if (x + .5 - CIRCLE_CENTER[0]) ** 2 +
                     (y + .5 - CIRCLE_CENTER[1]) ** 2 < CIRCLE_RADIUS ** 2 else 0
                     for y in range(NATIVE_SIDE) for x in range(NATIVE_SIDE))
    if alpha != expected * 2:
        raise ValueError("The native portrait does not use the verified shared XD disk.")
    return _smooth_circle_alpha()


def compose_atlas(normal: Image.Image, shiny: Image.Image, roi, native: Image.Image, *, game: str) -> Image.Image:
    """Keep the same framing and proportions in the normal and shiny cells."""
    if normal.size != (1024, 1024) or shiny.size != (1024, 1024):
        raise ValueError("HD portraits require actual GPU1024 render targets.")
    if (len(roi) != 4 or any(type(value) is not int for value in roi) or
            not 0 <= roi[0] < roi[2] <= 1024 or not 0 <= roi[1] < roi[3] <= 1024 or
            roi[2] - roi[0] != roi[3] - roi[1] or roi[2] - roi[0] < OUTPUT_SIDE):
        raise ValueError("The portrait ROI must reduce a square actual GPU region.")
    if native.size != (42, 84):
        raise ValueError("The native portrait guide must be a 42x84 atlas.")
    if game == "xd":
        alpha = native_circle_alpha(native)
    elif game == "colosseum":
        alpha = bytes([255]) * OUTPUT_SIDE ** 2
    else:
        raise ValueError("Unknown portrait frame game.")
    atlas = Image.new("RGBA", (OUTPUT_SIDE, OUTPUT_SIDE * 2))
    for row, raw in enumerate((normal, shiny)):
        tile = raw.convert("RGBa").crop(tuple(roi)).resize(
            (OUTPUT_SIDE, OUTPUT_SIDE), Image.Resampling.LANCZOS).convert("RGBA")
        canvas = Image.new("RGBA", (OUTPUT_SIDE, OUTPUT_SIDE), (0, 0, 0, 255))
        canvas.alpha_composite(tile)
        rgba = bytearray(canvas.tobytes())
        rgba[3::4] = alpha
        for offset in range(0, len(rgba), 4):
            if rgba[offset + 3] == 0:
                rgba[offset:offset + 3] = b"\0\0\0"
        atlas.paste(Image.frombytes("RGBA", canvas.size, bytes(rgba)), (0, row * OUTPUT_SIDE))
    return atlas


def build(args) -> dict:
    """Write a private, review-only atlas and a portable composition receipt."""
    images, hashes = [], []
    for path, expected in ((args.normal, args.normal_sha256), (args.shiny, args.shiny_sha256)):
        if path.is_symlink():
            raise ValueError("Raw capture inputs cannot be symbolic links.")
        payload = path.read_bytes()
        sha = hashlib.sha256(payload).hexdigest()
        if sha != expected:
            raise ValueError("Raw GPU capture integrity check failed.")
        images.append(Image.open(path).convert("RGBA"))
        hashes.append(sha)
    native = Image.open(args.native_atlas).convert("RGBA")
    origin = portrait_origin(args.game, args.native_key, native.size)
    native_sha = hashlib.sha256(native.tobytes()).hexdigest()
    if origin is None or native_sha != origin["transform"]["native_rgba_sha256"]:
        raise ValueError("The original portrait guide is not its catalogued native identity.")
    result = compose_atlas(*images, args.roi, native, game=args.game)
    payload = _png(result.size, result.tobytes())
    receipt = {"schema": 1, "kind": "extra-portrait-atlas-composition", "review_only": True,
        "tool": "scripts/compose_extra_portraits.py", "version": 1,
        "environment": {"python": platform.python_version(), "pillow": PIL.__version__,
                        "stdlib_zlib": zlib.ZLIB_RUNTIME_VERSION, "freetype_used": False},
        "game": args.game, "native_key": args.native_key, "native_rgba_sha256": native_sha,
        "source_dimensions": [1024, 1024], "source_sha256": hashes, "source_crop": args.roi,
        "output_dimensions": [168, 336], "output_sha256": hashlib.sha256(payload).hexdigest(),
        "native_bitmap_upscaled_for_hd": False,
        "frame": ({"kind": "native geometric disk", "native_center": [21, 21],
                   "native_radius": 22.5, "coverage_samples_per_output_pixel": 64}
                  if args.game == "xd" else {"kind": "opaque native square"}),
        "colour_transform": "premultiplied reduction of actual GPU crop; black behind transparent model",
        "capture_qualification": "separate original model, HD materials and frozen pose receipts required"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(payload)
    args.output.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal", type=Path, required=True)
    parser.add_argument("--normal-sha256", required=True)
    parser.add_argument("--shiny", type=Path, required=True)
    parser.add_argument("--shiny-sha256", required=True)
    parser.add_argument("--native-atlas", type=Path, required=True)
    parser.add_argument("--native-key", required=True)
    parser.add_argument("--game", choices=("colosseum", "xd"), required=True)
    parser.add_argument("--roi", nargs=4, type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = build(parser.parse_args())
    print("Composed review atlas", result["output_sha256"])


if __name__ == "__main__":
    main()
