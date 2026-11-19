"""Reproduce registered regional menus from real HD donors and vector artwork.

No source ROM or native raster guide is required. Original pack installations
and bundled artwork are opened read-only; the requested output must be new.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from PySide6.QtGui import QGuiApplication

from orre_randomizer.hd_menu_atlases import _pixel_bytes, _render_vector_text
from orre_randomizer.hd_menu_catalog import _asset, _asset_bytes
from orre_randomizer.hd_menu_svg import render_background

SOURCE = "menu-atlases/solo-menu-source.json"


def pixel_box(rectangle):
    return tuple(round(value * 4) for value in rectangle)


def read_source(source, pack_textures: Path):
    if source["kind"] == "pack":
        name = source["file"]
        if Path(name).name != name:
            raise ValueError("The HD donor must use its recorded basename")
        root = Path(pack_textures).resolve(strict=True)
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("External HD donor refused")
        payload = path.read_bytes()
    elif source["kind"] == "registered-authored-HD-component":
        payload, _ = _asset_bytes(source["file"])
    else:
        raise ValueError("Unrecognized menu donor role")
    if hashlib.sha256(payload).hexdigest() != source["sha256"]:
        raise ValueError("The source HD artwork differs from the approved donor")
    from io import BytesIO
    with Image.open(BytesIO(payload)) as image:
        output = image.convert("RGBA")
    return output


def source_image(record, pack_textures: Path):
    if record["source"]["kind"] == "transparent-vector-canvas":
        return Image.new("RGBA", tuple(value * 4 for value in record["native_dimensions"]))
    output = read_source(record["source"], pack_textures)
    if output.size != tuple(value * 4 for value in record["native_dimensions"]):
        raise ValueError("The HD source dimensions differ from the regional menu")
    return output


def vector_labels(size, labels, vectors):
    if not labels:
        return Image.new("RGBA", (size[0] * 4, size[1] * 4))
    recipe = {"native_dimensions": list(size), "family": "regional-solo-menus",
              "language": "ja", "font_family": "latin_bold",
              "native_guide": {}, "labels": labels}
    image, _ = _render_vector_text(recipe, vectors)
    return Image.frombytes("RGBA", (image.width(), image.height()), _pixel_bytes(image))


def reproduce(record, vectors, pack_textures: Path):
    """Replay one recorded composition without inferring labels or geometry."""
    size = record["native_dimensions"]
    if (len(size) != 2 or any(type(value) is not int or not 1 <= value <= 2048 for value in size)
            or size[0] * size[1] > 1024 * 1024):
        raise ValueError("Menu dimensions exceed the bounded authoring canvas")
    output = source_image(record, pack_textures)
    original = output.copy()
    for rectangle in record.get("clear", []):
        output.paste((0, 0, 0, 0), pixel_box(rectangle))
    if record.get("svg"):
        payload = record["svg"].encode("utf-8")
        image, _ = render_background(payload, expected_sha256=hashlib.sha256(payload).hexdigest(),
                                     native_size=tuple(size), remove_ids=())
        output.alpha_composite(Image.frombytes("RGBA", (image.width(), image.height()), _pixel_bytes(image)))
    for component in record.get("components", []):
        donor = read_source(component["source"], pack_textures)
        crop = pixel_box(component["crop"])
        destination = pixel_box(component["destination"])
        if (not 0 <= crop[0] < crop[2] <= donor.width
                or not 0 <= crop[1] < crop[3] <= donor.height
                or not 0 <= destination[0] < destination[2] <= output.width
                or not 0 <= destination[1] < destination[3] <= output.height):
            raise ValueError("The recorded component exceeds its source or canvas")
        piece = donor.crop(crop)
        if component.get("circular_crop", False):
            # A currency icon can share an atlas cell with an attached bar.
            # Mask only that recorded edge; keep the donor's visible RGB.
            mask = Image.new("L", (piece.width * 2, piece.height * 2))
            ImageDraw.Draw(mask).ellipse((0, 0, mask.width - 1, mask.height - 1), fill=255)
            mask = mask.resize(piece.size, Image.Resampling.LANCZOS)
            piece.putalpha(ImageChops.multiply(piece.getchannel("A"), mask))
        if component.get("mirror_horizontal", False):
            piece = piece.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        target_size = (destination[2] - destination[0], destination[3] - destination[1])
        if piece.size != target_size:
            piece = piece.resize(target_size, Image.Resampling.LANCZOS)
        output.alpha_composite(piece, (destination[0], destination[1]))
    for rectangle in record.get("preserve_source_cells", []):
        box = pixel_box(rectangle)
        output.paste(original.crop(box), (box[0], box[1]))
    output.alpha_composite(vector_labels(size, record["labels"], vectors))
    for entry in record.get("blurred_labels", []):
        radius = entry["radius_native"]
        if not 0 < radius <= 8:
            raise ValueError("Menu blur exceeds its recorded bounded effect")
        mask = vector_labels(size, [entry["label"]], vectors).getchannel("A")
        mask = mask.filter(ImageFilter.GaussianBlur(radius * 4))
        effect = Image.new("RGBA", output.size, entry["color"])
        effect.putalpha(mask)
        box = pixel_box(entry["clip"])
        output.alpha_composite(effect.crop(box), (box[0], box[1]))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Exact registered native texture key")
    parser.add_argument("--pack-textures", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-json", type=Path, help="Explicit authoring candidate; default uses the authenticated bundled recipe")
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("Choose a new output file; previous artwork is preserved")
    data = json.loads(args.source_json.read_bytes()) if args.source_json else _asset(SOURCE)[0]
    if data.get("schema") != 1 or data.get("native_bitmap_upscaled_for_art") is not False:
        raise ValueError("The menu authoring recipe differs from the registered contract")
    record = next(row for row in data["records"] if row["target"] == args.target)
    app = QGuiApplication.instance() or QGuiApplication([])
    image = reproduce(record, data["vectors"], args.pack_textures)
    with args.output.open("xb") as stream:
        image.save(stream, format="PNG")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise ValueError("The reproduced menu differs from the approved PNG")
    print(json.dumps({"target": args.target, "dimensions": list(image.size), "sha256": digest,
                      "source_ROM_opened": False, "native_raster_used_for_HD": False}))


if __name__ == "__main__":
    main()
