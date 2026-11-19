"""Reproduce the registered Japanese Colosseum HUD background from its HD donor.

Requires the pinned, separately obtained Colosseum HD pack and the release's
Python/Qt dependencies. No ROM, native bitmap enlargement or emulator is used.
The registered recipe contains the regional positions and analytic UI shapes.
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

from PIL import Image
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_images import load_texture
from orre_randomizer.hd_menu_atlases import _pixel_bytes, _render_vector_geometry

TARGET = "tex1_256x239_b3d97994db34448e_5.png"


def reproduce(pack: Path, output: Path) -> dict:
    app = QGuiApplication.instance() or QGuiApplication([])
    catalogue = ROOT / "orre_randomizer/assets/game/menu-atlases/catalog.json"
    rows = json.loads(catalogue.read_text(encoding="utf-8"))["records"]
    matches = [row for row in rows if row["target"] == TARGET]
    if len(matches) != 1:
        raise ValueError("The registered Japanese common-HUD recipe is unavailable")
    record = matches[0]
    recipe = record["transform"]
    source = recipe["author_source"]
    donor = source["donor"]
    name = donor["physical_file"]
    if Path(name).name != name or output.exists():
        raise ValueError("Use the registered donor and a new output path")
    native_size = tuple(recipe["native_dimensions"])
    loaded = load_texture(pack / name, expected_native_size=native_size)
    if loaded.metadata["sha256"] != donor["sha256"]:
        raise ValueError("The HD donor differs from the pinned source")
    image = Image.frombytes("RGBA", (loaded.image.width(), loaded.image.height()), _pixel_bytes(loaded.image))
    background = image.copy()
    for box in source["clear_regions_native"]:
        background.paste((0, 0, 0, 0), tuple(value * 4 for value in box))
    for old, new in source["placements_native"]:
        tile = image.crop(tuple(value * 4 for value in old))
        size = ((new[2] - new[0]) * 4, (new[3] - new[1]) * 4)
        if tile.size != size:
            tile = tile.resize(size, Image.Resampling.LANCZOS)
        background.paste(tile, (new[0] * 4, new[1] * 4))
    geometry, _ = _render_vector_geometry({"native_dimensions": list(native_size),
        "family": recipe["family"], "native_guide": recipe["native_guide"],
        "layers": source["geometry"]["construction"]})
    background.alpha_composite(Image.frombytes("RGBA", (geometry.width(), geometry.height()), _pixel_bytes(geometry)))
    output.parent.mkdir(parents=True, exist_ok=True)
    background.save(output, format="PNG")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    if digest != record["source_sha256"]:
        raise RuntimeError("Reproduced background differs from the registered artwork")
    return {"target": TARGET, "sha256": digest, "dimensions": list(background.size),
            "native_raster_enlarged": False, "rom_used": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True, help="Pinned Colosseum HD Textures directory")
    parser.add_argument("--output", type=Path, required=True, help="New PNG destination")
    args = parser.parse_args()
    print(json.dumps(reproduce(args.pack, args.output), indent=2))


if __name__ == "__main__":
    main()
