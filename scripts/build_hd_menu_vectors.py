"""Capture reproducible menu-letter geometry without shipping a system font.

Inputs are two explicitly supplied, pinned font files and a JSON mapping of
family names to strings. Output is vector outlines only, with source credits.
Run with the release's Python/Qt environment. No ROM, emulator or save is used.
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

LATIN_SHA256 = "eaad201da94cb323401fdb8cc760650803ddf8fd704cb9fa56317e6c69bc6fd6"
JAPANESE_SHA256 = "c2f3b4d463500a2ddcd3849cded1fceeb9fd6d1c32e6cbecd568453ba50fc68f"


def capture_outlines(latin_font: Path, japanese_font: Path, strings: dict) -> dict:
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QRawFont
    app = QGuiApplication.instance() or QGuiApplication([])
    if not {"latin", "japanese"} <= set(strings) or set(strings) - {"latin", "latin_bold", "japanese"}:
        raise ValueError("Supply both declared menu typography families")
    fonts = {}
    sources = [("latin", Path(latin_font), LATIN_SHA256),
               ("japanese", Path(japanese_font), JAPANESE_SHA256)]
    if "latin_bold" in strings:
        sources.append(("latin_bold", Path(latin_font), LATIN_SHA256))
    for family, path, digest in sources:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Menu outline font differs from its pinned source: " + family)
        if family == "latin":
            font = QRawFont(str(path), 1000)
            expected_family = "Bahnschrift"
        else:
            handle = QFontDatabase.addApplicationFont(str(path))
            families = QFontDatabase.applicationFontFamilies(handle)
            if not families:
                raise ValueError("Cannot load the pinned Japanese vector font")
            selected = QFont(families[0])
            selected.setPixelSize(1000)
            selected.setWeight(QFont.Weight.Bold)
            font = QRawFont.fromFont(selected)
            expected_family = "Bahnschrift" if family == "latin_bold" else "Noto Sans JP"
        if not font.isValid() or font.familyName() != expected_family:
            raise ValueError("Menu vector font silently substituted another family")
        glyphs = {}
        for char in sorted(set("".join(strings[family]))):
            index = font.glyphIndexesForString(char)[0]
            if not index or not font.supportsCharacter(ord(char)):
                raise ValueError("Menu vector font lacks a required character: " + repr(char))
            path = font.pathForGlyph(index)
            commands, position = [], 0
            while position < path.elementCount():
                element = path.elementAt(position)
                if element.isMoveTo():
                    commands.append(["M", round(element.x, 5), round(element.y, 5)])
                elif element.isLineTo():
                    commands.append(["L", round(element.x, 5), round(element.y, 5)])
                elif element.type.value == 2:
                    b, c = path.elementAt(position + 1), path.elementAt(position + 2)
                    commands.append(["C", *[round(v, 5) for v in
                        (element.x, element.y, b.x, b.y, c.x, c.y)]])
                    position += 2
                else:
                    raise ValueError("Unexpected vector contour element")
                position += 1
            glyphs[char] = {"advance": round(font.advancesForGlyphIndexes([index])[0].x(), 5),
                            "path": commands}
        source = {"font": expected_family, "font_sha256": digest,
                  "size_design_pixels": 1000, "weight": font.weight(),
                  "outline_engine": "QRawFont", "qt_version": qVersion(),
                  "native_bitmap_used": False}
        if family in ("latin", "latin_bold"):
            source.update(author="Microsoft", role="mikeyX's original SVG typography",
                distribution="captured artwork geometry only; system font file not bundled",
                artwork_credit="mikeyX, Pokemon XD UI SVGs V1.0, CC BY-NC-SA 4.0 with Pokemon-mod exception")
        else:
            source.update(author="Google / Adobe", license="SIL Open Font License 1.1",
                role="Japanese labels, same pinned 700-weight source as Orre's V5 lettering")
        fonts[family] = {"source": source, "glyphs": glyphs}
    return {"schema": 1, "kind": "captured-vector-font-outlines", "families": fonts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latin-font", required=True, type=Path)
    parser.add_argument("--japanese-font", required=True, type=Path)
    parser.add_argument("--strings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    strings = json.loads(args.strings.read_text(encoding="utf8"))
    data = capture_outlines(args.latin_font, args.japanese_font, strings)
    with args.output.open("x", encoding="utf8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")


if __name__ == "__main__":
    main()
