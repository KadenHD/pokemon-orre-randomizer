"""Encode the approved PNG as a multi-resolution Windows ICO using Qt only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "colosseum_randomizer/assets/app"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def encode_icon(source: Path) -> bytes:
    image = QImage(str(source))
    if image.isNull() or image.width() != image.height() or not 256 <= image.width() <= 4096:
        raise ValueError("The icon master must be a square PNG between 256 and 4096 pixels.")
    if not image.hasAlphaChannel():
        raise ValueError("The icon master must have a transparent alpha channel.")
    frames = []
    for size in SIZES:
        padding = max(1, size // 16)
        scaled = image.scaled(size - 2*padding, size - 2*padding,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        frame = QImage(size, size, QImage.Format.Format_RGBA8888)
        frame.fill(Qt.GlobalColor.transparent)
        painter = QPainter(frame)
        painter.drawImage((size-scaled.width())//2, (size-scaled.height())//2, scaled)
        painter.end()
        payload = QByteArray()
        buffer = QBuffer(payload)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not frame.save(buffer, "PNG"):
            raise RuntimeError("Could not encode an icon frame.")
        buffer.close()
        frames.append(bytes(payload))
    directory = bytearray(struct.pack("<HHH", 0, 1, len(SIZES)))
    offset = 6 + 16*len(SIZES)
    for size, payload in zip(SIZES, frames, strict=True):
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                                     1, 32, len(payload), offset))
        offset += len(payload)
    return bytes(directory) + b"".join(frames)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ASSETS / "icon.png")
    parser.add_argument("--output", type=Path, default=ASSETS / "icon.ico")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.suffix.lower() != ".ico":
        parser.error("Choose a separate .ico output path.")
    args.output.write_bytes(encode_icon(args.source))
    records = {path.name: {"bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in (args.source, args.output)}
    provenance = {"name": "Éclipse", "selection": "B", "date": "2026-11-01",
                  "origin": "Original abstract icon generated with built-in image_gen; not extracted from a ROM.",
                  "license": "MIT", "sizes": list(SIZES),
                  "encoding": "RGBA PNG frames in an ICO container, transparent padding of 1/16 per side",
                  "generator": "scripts/build_app_icon.py", "files": records}
    args.output.with_name("provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2)+"\n", "utf-8")
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
