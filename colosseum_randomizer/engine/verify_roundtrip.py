"""Independent post-test checks of source preservation and allowed ISO changes."""

import argparse
import json
from pathlib import Path
import struct

from .analyze_game import write_json
from .rebuild_iso import tree_identity
from .survey_assets import fst_inventory, sha256


def verify(game: Path, build: Path, *, expected_dol: bytes | None = None,
           expected_files: dict[str, bytes] | None = None) -> dict:
    game, build = game.resolve(), build.resolve()
    load = lambda name: json.loads((build / name).read_text(encoding="utf-8"))
    report = load("rebuild-report.json")
    profile = load("dolphin-user-preparation.json")
    manifest = load("input-manifest.json")
    source, target = Path(report["source_iso"]), Path(report["output_iso"])
    if source.stat().st_size != target.stat().st_size:
        raise ValueError("source/output ISO sizes differ")
    boot = (game / "sys/boot.bin").read_bytes()
    fst = (game / "sys/fst.bin").read_bytes()
    entries, _ = fst_inventory(fst)
    common = next(e for e in entries if e["path"] == "common.fsys")
    fst_offset = struct.unpack_from(">I", boot, 0x424)[0]
    fst_start = fst_offset + common["index"] * 12 + 4
    archive = report["common_fsys"]
    ranges = [(fst_start, fst_start + 8),
              (archive["new_disc_offset"], archive["new_disc_offset"] + archive["new_size"])]
    expected_files = dict(expected_files or {})
    replacements = {item["path"]: item for item in report.get("file_replacements", [])}
    if set(expected_files) != set(replacements):
        raise ValueError("replacement archives require caller-computed exact expected bytes")
    for name, payload in expected_files.items():
        selected = next(e for e in entries if e["path"] == name)
        replacement = replacements[name]
        if len(payload) != replacement["new_size"]:
            raise ValueError("replacement archive length differs from expected bytes")
        start = fst_offset + selected["index"] * 12 + 4
        ranges.extend(((start, start + 8),
                       (replacement["new_disc_offset"], replacement["new_disc_offset"] + len(payload))))
    original_dol = (game / "sys/main.dol").read_bytes()
    dol_offset = struct.unpack_from(">I", boot, 0x420)[0]
    if expected_dol is not None:
        if len(expected_dol) != len(original_dol) or expected_dol[:0x100] != original_dol[:0x100]:
            raise ValueError("expected DOL must preserve original size/header")
        ranges.extend((dol_offset + i, dol_offset + i + 1)
                      for i, (a, b) in enumerate(zip(original_dol, expected_dol, strict=True)) if a != b)
    elif "main_dol" in report:
        raise ValueError("DOL changes require a caller-computed exact expected DOL")
    ranges.sort()
    if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])) or ranges[-1][1] > source.stat().st_size:
        raise ValueError("invalid declared differing ranges")
    cursor, identical = 0, 0
    with source.open("rb") as a, target.open("rb") as b:
        for start, end in ranges + [(source.stat().st_size, source.stat().st_size)]:
            a.seek(cursor)
            b.seek(cursor)
            remaining = start - cursor
            while remaining:
                length = min(remaining, 4 * 1024 * 1024)
                if a.read(length) != b.read(length):
                    raise ValueError("unexpected ISO changes outside declared ranges")
                identical += length
                remaining -= length
            cursor = end
        b.seek(fst_offset)
        rebuilt_entries, _ = fst_inventory(b.read(len(fst)))
        if expected_dol is not None:
            b.seek(dol_offset)
            if b.read(len(expected_dol)) != expected_dol:
                raise ValueError("ISO DOL differs from exact seeded expected bytes")
        for name, payload in expected_files.items():
            b.seek(replacements[name]["new_disc_offset"])
            if b.read(len(payload)) != payload:
                raise ValueError(f"ISO archive differs from expected bytes: {name}")
    if len(entries) != len(rebuilt_entries):
        raise ValueError("FST entry count differs")
    for old, new in zip(entries, rebuilt_entries, strict=True):
        expected = dict(old)
        if old["path"] == "common.fsys":
            expected.update(disc_offset=archive["new_disc_offset"], size=archive["new_size"])
        elif old["path"] in replacements:
            item = replacements[old["path"]]
            expected.update(disc_offset=item["new_disc_offset"], size=item["new_size"])
        if new != expected:
            raise ValueError("unexpected FST entry change")
    changed = [f["path"] for f in profile["source_originals"] if not Path(f["path"]).is_file()
               or sha256(Path(f["path"])) != f["sha256"]]
    result = {"source_iso_unchanged": sha256(source) == report["source_iso_sha256"],
              "output_iso_hash_matches_build": sha256(target) == report["output_iso_sha256"],
              "extracted_tree_unchanged": tree_identity(game) == manifest,
              "original_dolphin_profile_files_unchanged": not changed,
              "original_dolphin_files_checked": len(profile["source_originals"]),
              "changed_original_profile_files": changed,
              "iso_bytes_identical_outside_allowed_ranges": identical,
              "allowed_differing_ranges": [{"start": s, "end_exclusive": e, "size": e - s} for s, e in ranges],
              "fst_changes_match_exactly": True,
              "source_iso_sha256": report["source_iso_sha256"],
              "output_iso_sha256": report["output_iso_sha256"]}
    if expected_dol is not None:
        result["main_dol_matches_expected"] = True
    if expected_files:
        result["replacement_archives_match_expected"] = sorted(expected_files)
    for key in ("source_iso_unchanged", "output_iso_hash_matches_build", "extracted_tree_unchanged",
                "original_dolphin_profile_files_unchanged"):
        if not result[key]:
            raise ValueError(f"post-test integrity check failed: {key}")
    write_json(build / "final-integrity.json", result)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--build-dir", type=Path, default=Path("build/roundtrip"))
    args = parser.parse_args()
    verify(args.game, args.build_dir)
