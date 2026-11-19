"""Reproduce the three reviewed Bingo backgrounds without native bitmap input.

Run in the release Pillow13/Qt environment. Inputs are the real author's SVG
archive/extracted SVG folder and the pinned installed XD pack, supplied as paths.
The two SVG guide layers and captions are removed by hd_menu_svg. Genuine HD
pixels are retained outside the exact cleanup/relayout rectangles below. No ROM,
save, font, emulator, Blender, network request or installed addon is involved.
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
ARCHIVE_SHA = "c575a04cb5044a41df620e92557cd6bd5d72fb9c3ad4e726dacf972def262616"
SOURCE_PNG = "tex1_344x388_ee5c992f1a89c78e_ed41aa007b9c0d1f_9.png"
SOURCE_PNG_SHA = "81005a2962556a9db4a7389d7a20ee7dbe6384367da776c9670e1c19b199e725"
SVG_SOURCES = {
    "cards": ("tex1_578x212_96759d22a973e22a_1b98ad8730ad4fd3_9.svg",
              "e1fa53e34270363eccb1e703d5f364d424995a2eb651b53af8ad05af29eb2ec3", (578, 212)),
    "tools": ("tex1_344x388_ee5c992f1a89c78e_ed41aa007b9c0d1f_9.svg",
              "d8b4a3b1784994aa26dac0b5ace1959c2e98206a91b189efeafc3f0abe7d76c5", (344, 388)),
}
EXPECTED = {
    "bingo-type-cards-background-x4.png": "b52cef93320387577b22aad4638f69456e53536332db7cddf1d04f159f61a783",
    "bingo-tools-388-captionless-x4-v2.png": "dd2ba1d92fbf93ef5fc5897ee2491e4b244431c95c8c58832e90ad8a5765d243",
    "bingo-tools-342-captionless-x4-v2.png": "2b9fb433df6a3e0db3c3f59c61a8deaca8a212da37c9e5524f7107ee67a107df",
}


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    from PIL import Image, __version__ as pillow_version
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QGuiApplication
    from orre_randomizer.hd_images import resolve_texture
    from orre_randomizer.hd_menu_atlases import _pixel_bytes
    from orre_randomizer.hd_menu_svg import render_background
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-root", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--xd-pack", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    roots = (args.svg_root.resolve(strict=True), args.xd_pack.resolve(strict=True))
    if output.exists() or any(output == root or root in output.parents for root in roots):
        parser.error("Use a new output folder outside the read-only source SVG/pack trees")
    if sha(args.source_archive) != ARCHIVE_SHA:
        raise ValueError("Original author SVG archive differs")
    pack = args.xd_pack / "Textures" if (args.xd_pack / "Textures").is_dir() else args.xd_pack
    donor = resolve_texture(pack, SOURCE_PNG)
    if sha(donor) != SOURCE_PNG_SHA:
        raise ValueError("Real HD Bingo background differs from the reviewed source")
    app = QGuiApplication.instance() or QGuiApplication([])
    rendered, proofs = {}, {}
    for kind, (filename, digest, size) in SVG_SOURCES.items():
        rendered[kind], proofs[kind] = render_background((args.svg_root / filename).read_bytes(),
            expected_sha256=digest, native_size=size, remove_ids=("g8",))
        proofs[kind]["source_member"] = "svg/" + filename
    output.mkdir(parents=True, exist_ok=False)
    if not rendered["cards"].save(str(output / "bingo-type-cards-background-x4.png"), "PNG"):
        raise ValueError("Cannot encode real vector Bingo cards")
    with Image.open(donor) as source:
        original = source.convert("RGBA")
    if original.size != (1376, 1552):
        raise ValueError("Unexpected real HD Bingo source dimensions")
    svg = Image.frombytes("RGBA", (1376, 1552), _pixel_bytes(rendered["tools"]))
    clean = original.copy()
    cleanup = ((144, 214, 184, 255), (16, 357, 155, 387))
    scaled = lambda box: tuple(value * 4 for value in box)
    for box in cleanup:
        clean.paste(svg.crop(scaled(box)), scaled(box)[:2])
    for height in (388, 342):
        image = clean.crop((0, 0, 1376, height * 4))
        if height == 342:
            # Genuine HD component reduction; no native image is sampled.
            source_box, destination = (12, 348, 164, 388), (72, 76, 220, 114)
            patch = clean.crop(scaled(source_box)).resize((592, 152), Image.Resampling.LANCZOS)
            image.paste(patch, scaled(destination)[:2])
        image.save(output / f"bingo-tools-{height}-captionless-x4-v2.png")
    files = {name: sha(output / name) for name in EXPECTED}
    if files != EXPECTED:
        raise ValueError("Reproduced artwork differs; preserve outputs and inspect the renderer environment")
    report = {"schema": 1, "files": files, "source_archive_sha256": ARCHIVE_SHA,
        "source_pack_png_sha256": SOURCE_PNG_SHA, "SVG_sources": proofs,
        "cleanup_rectangles_native": cleanup, "source_scale": 4,
        "native_raster_resampled": False, "pillow": pillow_version, "qt": qVersion(),
        "runtime_validated": False}
    (output / "reproduction.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("Reproduced three Bingo backgrounds byte-identical to the reviewed artwork")


if __name__ == "__main__":
    main()
