"""Reproduce reviewed PAL and Japanese CB atlases from bundled author inputs.

Use the artwork environment with Pillow13 and PySide6. The source JSON, vector
outlines and approved model PNGs are registered game assets. Native guides,
ROMs, private saves, Blender, Dolphin and system font files are not required.
The Colosseum texture pack is required for the six Japanese donor operations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "cb_menu_artwork"))
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_catalog import _asset, _asset_bytes
from compose_cb_pal import compose
from author_jp_link import build

SOURCE = "menu-atlases/cb-composition-source.json"


def reproduce(mode: str, output: Path, pack_textures: Path | None = None):
    """Validate pinned inputs and reproduce one approved composition family."""
    data, _ = _asset(SOURCE)
    if data.get("review_only") is not False or mode not in ("pal", "jp"):
        raise ValueError("Choose an approved PAL or Japanese composition")
    if output.exists() or output.is_symlink():
        raise ValueError("The output directory must be new")
    if mode == "jp" and pack_textures is None:
        raise ValueError("Japanese donor operations require --pack-textures")
    app = QGuiApplication.instance() or QGuiApplication([])
    with TemporaryDirectory(prefix="orre-cb-author-") as temporary:
        inputs = Path(temporary)
        for filename, source in data["binary_inputs"].items():
            if Path(filename).name != filename:
                raise ValueError("Invalid author input basename")
            payload, digest = _asset_bytes(source["asset"])
            if digest != source["sha256"]:
                raise ValueError("Approved CB author input changed")
            (inputs / filename).write_bytes(payload)
        if mode == "pal":
            records = compose(data["pal_recipe"], inputs, output, ROOT)
            actual = {r["file"]: r["sha256"] for r in records}
            expected = data["pal_recipe"]["approved_outputs"]
        else:
            for filename, text in data["jp_input_text"].items():
                if Path(filename).name != filename:
                    raise ValueError("Invalid Japanese vector input basename")
                (inputs / filename).write_bytes(text.encode("utf8"))
            portraits = data["portrait_manifest"]
            portraits["directory"] = str(inputs)
            report = build(inputs, pack_textures, inputs / "jp-vector-fragment.json", output, portraits)
            actual = {r["file"]: r["sha256"] for r in report["records"]}
            expected = {r["file"]: r["sha256"] for r in data["jp_receipt"]["records"]}
        if actual != expected:
            raise ValueError("Reproduction differs from the approved CB compositions")
    return {"mode": mode, "byte_exact_outputs": len(actual), "ROM_required": False,
            "native_bitmap_resampled": False, "Dolphin_started": False,
            "outputs": actual}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("pal", "jp"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pack-textures", type=Path)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.mode, args.output, args.pack_textures)))


if __name__ == "__main__":
    main()
