"""Reproduce four approved Japanese menus from genuine HD donors and vectors.

All source geometry, captured lettering and final hashes are bundled in the
registered authoring packet. Run in the artwork environment with Pillow13 and
PySide6. A read-only Colosseum pack is required; no ROM, native guide image,
save, system font, NumPy or graphical game process is used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "colosseum_menu_artwork"))
from PySide6.QtGui import QGuiApplication
from orre_randomizer.hd_menu_catalog import _asset
from author_extra_four import build


def reproduce(pack_textures: Path, output: Path):
    data, _ = _asset("menu-atlases/colosseum-extra-four-source.json")
    if data.get("review_only") is not False or output.exists() or output.is_symlink():
        raise ValueError("Reviewed artwork and a new output directory are required")
    app = QGuiApplication.instance() or QGuiApplication([])
    with TemporaryDirectory(prefix="orre-colo-ui-author-") as temporary:
        inputs = Path(temporary)
        for filename, text in data["inputs_text"].items():
            if Path(filename).name != filename:
                raise ValueError("Expected a flat authoring source basename")
            (inputs / filename).write_bytes(text.encode("utf8"))
        actual = build(inputs, pack_textures, output)
    expected = {r["file"]: r["sha256"] for r in data["receipt"]["records"]}
    hashes = {r["file"]: r["sha256"] for r in actual["records"]}
    if hashes != expected:
        raise ValueError("Reproduction differs from the four reviewed outputs")
    return {"byte_exact_outputs": len(hashes), "files": hashes,
            "native_bitmap_or_ROM_used": False, "Dolphin_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-textures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.pack_textures, args.output)))


if __name__ == "__main__":
    main()
