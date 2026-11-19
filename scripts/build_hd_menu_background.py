"""Reproduce a registered x4 vector menu background from its real author SVG.

Supply the exact SHA recorded in the catalogue and every original image/guide
layer ID to remove. Caption <text> nodes are also removed. The tool rejects any
remaining image, external reference, font-dependent text, filter or script. It
renders only actual author vector geometry; no native bitmap can be enlarged.
Use the release Python/Qt environment, and preserve the generated receipt.
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


def main():
    from PySide6.QtGui import QGuiApplication
    from orre_randomizer.hd_menu_svg import render_background
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--native-size", type=int, nargs=2, required=True)
    parser.add_argument("--remove-id", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if any(path.exists() or path.is_symlink() for path in (args.output, args.receipt)):
        parser.error("Use new output paths; earlier artwork and evidence are preserved")
    app = QGuiApplication.instance() or QGuiApplication([])
    image, report = render_background(args.svg.read_bytes(), expected_sha256=args.sha256,
        native_size=tuple(args.native_size), remove_ids=tuple(args.remove_id))
    from PySide6.QtCore import QBuffer, QIODevice
    encoded = QBuffer()
    encoded.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(encoded, "PNG"):
        raise ValueError("Cannot encode the authored menu background")
    payload = bytes(encoded.data())
    report.update(source_file=args.svg.name, file=args.output.name,
                  bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(payload)
    with args.receipt.open("x", encoding="utf8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print("Reproduced genuine SVG background x4 with zero raster/image/font nodes")


if __name__ == "__main__":
    main()
