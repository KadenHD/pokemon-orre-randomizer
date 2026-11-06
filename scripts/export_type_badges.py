"""Export the original localized type badges from retail Colosseum and XD discs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orre_randomizer.artwork import _atomic_write, _digest, _disc_files, _member, _png, _texture
from orre_randomizer.engine.analyze_game import parse_fsys


PAL_SUFFIXES = {"en": "", "fr": "_fr", "de": "_ge", "it": "_it", "es": "_sp"}
ATLAS_IDS = {
    "colosseum": {"en": 0x02081200, "fr": 0x15511200, "de": 0x154D1200,
                  "it": 0x15551200, "es": 0x15591200, "ja": 0x02081200},
    "xd": {"en": 0x16C01200, "fr": 0x22191200, "de": 0x221D1200,
           "it": 0x22211200, "es": 0x22251200, "ja": 0x16C01200},
}
# Native type IDs in atlas column order, including the mystery type (9).
TYPE_COLUMNS = {
    "colosseum": ((12, 11, 4, 10, 1, 17, 0, 6), (2, 14, 7, 5, 8, 13, 16, 15), (3, 9)),
    "xd": ((12, 11, 4, 10, 1, 17, 0, 6, 2), (14, 7, 5, 8, 13, 16, 15, 3, 9)),
}
ATLAS_DIMENSIONS = {"colosseum": (258, 258), "xd": (152, 200)}
BADGE_DIMENSIONS = {"colosseum": (79, 27), "xd": (72, 18)}


def archive_for(language: str) -> str:
    return "common.fsys" if language == "ja" else f"fight_common{PAL_SUFFIXES[language]}.fsys"


def read_archives(source: Path, disc_id: str, languages: tuple[str, ...], dolphin_tool: Path | None):
    archives = {archive_for(language) for language in languages}
    if source.suffix.lower() == ".iso":
        with source.open("rb") as stream:
            if stream.read(8) != disc_id.encode("ascii") + b"\0\0":
                raise ValueError(f"Expected revision 0 of {disc_id}.")
        return _disc_files(source, archives, is_xd=disc_id.startswith("GXX"))
    if source.suffix.lower() != ".rvz" or dolphin_tool is None:
        raise ValueError("Supply an ISO or pass --dolphin-tool for RVZ inputs.")
    tool = str(dolphin_tool.resolve(strict=True))
    header = json.loads(subprocess.check_output([tool, "header", "-i", str(source), "--json"], timeout=30))
    if header["game_id"] != disc_id or header["revision"] != 0:
        raise ValueError(f"Expected revision 0 of {disc_id}.")
    with TemporaryDirectory(prefix="orre-type-badges-") as folder:
        for name in sorted(archives):
            subprocess.run([tool, "extract", "-i", str(source), "-o", folder, "-s", name, "-q"],
                           check=True, timeout=30)
        return {name: (Path(folder) / "files" / name).read_bytes() for name in archives}


def atlas_badges(game: str, atlas: bytes):
    atlas_width, _ = ATLAS_DIMENSIONS[game]
    width, height = BADGE_DIMENSIONS[game]
    pixels = _texture(atlas, ATLAS_DIMENSIONS[game])
    for column, identifiers in enumerate(TYPE_COLUMNS[game]):
        for row, type_id in enumerate(identifiers):
            if game == "xd":
                left, top = 3 + 75 * column, 2 + 20 * row
            else:
                left = (6, 90, 173)[column]
                top = 6 if column == 2 and row == 0 else 7 + 31 * row
            offsets = ((y * atlas_width + left) * 4 for y in range(top, top + height))
            crop = b"".join(pixels[offset:offset + width * 4] for offset in offsets)
            if not any(crop[3::4]):
                raise ValueError(f"Empty badge for {game} type {type_id}.")
            yield type_id, (left, top, width, height), _png((width, height), crop)


def export_badges(discs, output: Path, dolphin_tool: Path | None):
    manifest = {"version": 1, "sources": {}}
    files = {}
    for game, disc_id, languages, source in discs:
        archives = read_archives(source, disc_id, languages, dolphin_tool)
        for language in languages:
            name = archive_for(language)
            archive = archives[name]
            identifier = f"0x{ATLAS_IDS[game][language]:08x}"
            matches = [member for member in parse_fsys(archive)["members"] if member["identifier_raw"] == identifier]
            if len(matches) != 1:
                raise ValueError(f"Expected one texture member {identifier} in {disc_id}/{name}.")
            entry, = matches
            atlas = _member(archive, matches, entry["name"])
            prefix = f"{game}-{language}"
            badges = {}
            manifest["sources"][prefix] = {
                "disc_id": disc_id, "disc_revision": 0, "archive": name, "archive_sha256": _digest(archive),
                "member": entry["name"], "member_id": identifier, "member_offset": entry["offset"],
                "member_sha256": _digest(atlas), "atlas_dimensions": list(struct.unpack_from(">HH", atlas)),
                "badges": badges,
            }
            for type_id, rect, png in atlas_badges(game, atlas):
                filename = f"{prefix}-{type_id}.png"
                files[filename] = png
                badges[str(type_id)] = {"file": filename, "crop_xywh": rect, "sha256": _digest(png)}
    output.mkdir(parents=True, exist_ok=True)
    for filename, png in files.items():
        _atomic_write(output / filename, png)
    _atomic_write(output / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for game in ("colosseum", "xd"):
        for region in ("pal", "jp"):
            parser.add_argument(f"--{game}-{region}", type=Path, required=True)
    parser.add_argument("--dolphin-tool", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "orre_randomizer/assets/game/types")
    args = parser.parse_args()
    discs = (("colosseum", "GC6P01", tuple(PAL_SUFFIXES), args.colosseum_pal),
             ("colosseum", "GC6J01", ("ja",), args.colosseum_jp),
             ("xd", "GXXP01", tuple(PAL_SUFFIXES), args.xd_pal),
             ("xd", "GXXJ01", ("ja",), args.xd_jp))
    count = export_badges(discs, args.output, args.dolphin_tool)
    print(f"Exported {count} type badges to {args.output}")


if __name__ == "__main__":
    main()
