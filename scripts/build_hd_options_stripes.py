"""Reproduce Options stripes from measured geometry and pinned HD donors.

Only the shared scanline band is redrawn. Every other donor RGBA pixel stays
unchanged. No ROM, native bitmap, system font or network access is needed.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = "menu-atlases/options-stripes-source.json"


def compose(base, packet):
    """Replace the measured band with vectors; do not resample either input."""
    from PIL import Image
    from PySide6.QtGui import QGuiApplication
    from orre_randomizer.hd_menu_atlases import _pixel_bytes
    from orre_randomizer.hd_menu_svg import render_background

    if (packet.get("native_dimensions") != [640, 256]
            or packet.get("replacement_bounds") != [0, 200, 640, 256]
            or base.size != (2560, 1024)):
        raise ValueError("Options band geometry differs from the qualified native layout")
    app = QGuiApplication.instance() or QGuiApplication([])
    payload = packet["svg"].encode("utf8")
    image, _ = render_background(payload, expected_sha256=packet["svg_sha256"],
                                 native_size=(640, 256), remove_ids=())
    geometry = Image.frombytes("RGBA", image.size().toTuple(), _pixel_bytes(image))
    result = base.convert("RGBA").copy()
    box = tuple(value * 4 for value in packet["replacement_bounds"])
    result.paste(geometry.crop(box), box)
    return result


def _base(record, pack_root):
    from PIL import Image
    from orre_randomizer.hd_menu_catalog import _asset_bytes
    source = record["source"]
    if source["kind"] == "bundled-reviewed-HD":
        payload, digest = _asset_bytes(source["file"])
    elif source["kind"] == "pinned-upstream-HD":
        if pack_root is None:
            raise ValueError("Supply the pinned Colosseum pack for the European donors")
        root = Path(pack_root).resolve(strict=True)
        if (root / "Textures").is_dir():
            root = root / "Textures"
        name = source["file"]
        if Path(name).name != name:
            raise ValueError("Expected a flat pinned donor filename")
        path = root / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("External Options donor refused")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
    else:
        raise ValueError("Unknown Options donor")
    if digest != source["sha256"]:
        raise ValueError("Options donor differs from its pinned HD source")
    with Image.open(BytesIO(payload)) as image:
        if image.size != (2560, 1024):
            raise ValueError("Options HD donor dimensions changed")
        result = image.convert("RGBA")
    if hashlib.sha256(result.crop((0, 0, 2560, 800)).tobytes()).hexdigest() != record["preserved_hd_rgba_sha256"]:
        raise ValueError("Options donor pixels outside the correction changed")
    return result


def _reviewed_png(record, rendered):
    """Verify exact decoded pixels, then retain the authenticated PNG bytes.

    PNG compressors can produce different byte streams across operating
    systems without changing one pixel. Neither that variation nor a genuine
    rendering difference may replace the reviewed distribution artwork.
    """
    from PIL import Image
    from orre_randomizer.hd_menu_catalog import _asset_bytes

    name = record["file"]
    if Path(name).name != name or not name.endswith(".png"):
        raise ValueError("Expected a flat Options artwork filename")
    payload, digest = _asset_bytes("menu-atlases/" + name)
    if digest != record["sha256"]:
        raise ValueError("Options canonical PNG differs from its pinned source: " + record["target"])
    with Image.open(BytesIO(payload)) as canonical:
        expected = canonical.convert("RGBA")
    actual = rendered.convert("RGBA")
    expected_pixels, actual_pixels = expected.tobytes(), actual.tobytes()
    expected_digest = hashlib.sha256(expected_pixels).hexdigest()
    actual_digest = hashlib.sha256(actual_pixels).hexdigest()
    if (list(expected.size) != record["dimensions"] or actual.size != expected.size
            or actual_pixels != expected_pixels):
        raise ValueError(f"Options RGBA differs for {record['target']}: "
                         f"expected {expected.size} {expected_digest}; "
                         f"got {actual.size} {actual_digest}")
    return payload, actual_digest


def reproduce(output: Path, *, pack_root: Path | None = None):
    from orre_randomizer.hd_menu_catalog import _asset
    packet, _ = _asset(SOURCE)
    if (packet.get("schema") != 1 or packet.get("review_only") is not False
            or packet.get("native_bitmap_upscaled_for_art") is not False
            or len(packet.get("records", [])) != 7):
        raise ValueError("Options geometry is not reviewed")
    if output.exists() or output.is_symlink():
        raise ValueError("Use a new output directory")
    outputs = []
    output.mkdir(parents=True)
    for record in packet["records"]:
        name = record["file"]
        if Path(name).name != name or not name.endswith(".png"):
            raise ValueError("Expected a flat Options artwork filename")
        image = compose(_base(record, pack_root), packet)
        payload, rgba_digest = _reviewed_png(record, image)
        path = output / name
        with path.open("xb") as stream:
            stream.write(payload)
        outputs.append({"target": record["target"], "sha256": record["sha256"],
                        "rgba_sha256": rgba_digest,
                        "preserved_hd_rgba_sha256": record["preserved_hd_rgba_sha256"]})
    return {"outputs": outputs, "native_raster_used": False,
            "source_ROM_opened": False, "Dolphin_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True, help="Pinned Colosseum 2.00 pack or its Textures directory")
    args = parser.parse_args()
    print(json.dumps(reproduce(args.output, pack_root=args.pack)))


if __name__ == "__main__":
    main()
