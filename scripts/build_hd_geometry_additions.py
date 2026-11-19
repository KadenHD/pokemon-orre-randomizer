"""Reproduce measured x4 menu geometry without ROMs, native PNGs or fonts.

Only registered vector paths and analytic gradients reach the output. The
native resource digests in the packet identify the measured sprite layout;
they are not raster artwork inputs. Runtime visibility is qualified separately.
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
SOURCE = "menu-atlases/geometry-additions-source.json"
SOURCES = {"geometry": SOURCE, "warnings": "menu-atlases/xd-warning-pages-source.json"}


def reproduce(output: Path, *, source: str = SOURCE):
    from PySide6.QtGui import QGuiApplication
    from orre_randomizer.hd_menu_atlases import _pixel_bytes
    from orre_randomizer.hd_menu_catalog import _asset
    from orre_randomizer.hd_menu_svg import render_background
    from PIL import Image

    if source not in SOURCES.values():
        raise ValueError("Unknown registered vector artwork packet")
    packet, _ = _asset(source)
    if (packet.get("schema") != 1 or packet.get("review_only") is not False
            or packet.get("native_bitmap_upscaled_for_art") is not False):
        raise ValueError("Measured geometry has not been reviewed")
    if output.exists() or output.is_symlink():
        raise ValueError("Use a new output directory; previous artwork is retained")
    app = QGuiApplication.instance() or QGuiApplication([])
    output.mkdir(parents=True)
    receipts = []
    for record in packet["records"]:
        name = record["file"]
        if Path(name).name != name or not name.endswith(".png"):
            raise ValueError("Expected a flat artwork filename")
        payload = record["svg"].encode("utf8")
        image, metadata = render_background(payload,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            native_size=tuple(record["native_dimensions"]), remove_ids=())
        rendered = Image.frombytes("RGBA", (image.width(), image.height()), _pixel_bytes(image))
        path = output / name
        with path.open("xb") as stream:
            rendered.save(stream, format="PNG")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError("Geometry differs from the reviewed x4 output")
        receipts.append({"target": record["target"], "sha256": digest, **metadata})
    return {"outputs": receipts, "source_ROM_opened": False,
            "native_raster_used": False, "Dolphin_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", choices=sorted(SOURCES), default="geometry")
    args = parser.parse_args()
    print(json.dumps(reproduce(args.output, source=SOURCES[args.source])))


if __name__ == "__main__":
    main()
