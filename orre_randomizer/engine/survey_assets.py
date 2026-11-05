#!/usr/bin/env python3
"""Read-only inventory and GameCube FST/extracted-tree consistency survey."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fst_inventory(data: bytes) -> tuple[list[dict], list[dict]]:
    """Parse the big-endian FST, retaining source entry indices and offsets."""
    if len(data) < 12:
        raise ValueError("Truncated FST root")
    root, parent, count = struct.unpack_from(">III", data)
    if root != 0x01000000 or parent != 0 or not 0 < count <= len(data) // 12:
        raise ValueError("Invalid FST root or entry count")
    strings_offset = count * 12
    directories = []
    files = []
    stack = [("", count, 0)]
    for index in range(1, count):
        name_word, offset_or_parent, size_or_end = struct.unpack_from(
            ">III", data, index * 12
        )
        kind = name_word >> 24
        start = strings_offset + (name_word & 0xFFFFFF)
        if kind not in (0, 1) or start >= len(data):
            raise ValueError(f"Invalid FST entry {index}")
        end = data.find(b"\0", start)
        if end < 0:
            raise ValueError(f"Unterminated FST name at entry {index}")
        name = data[start:end].decode("ascii")
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError(f"Unsafe FST name at entry {index}")
        while stack and index >= stack[-1][1]:
            stack.pop()
        if not stack:
            raise ValueError(f"Entry outside root: {index}")
        path = str(PurePosixPath(stack[-1][0]) / name)
        if kind == 1:
            if offset_or_parent != stack[-1][2] or not index < size_or_end <= stack[-1][1]:
                raise ValueError(f"Invalid directory bounds/parent at entry {index}")
            directories.append({"index": index, "path": path, "end_index": size_or_end})
            stack.append((path, size_or_end, index))
        else:
            files.append({"index": index, "path": path, "disc_offset": offset_or_parent,
                          "size": size_or_end})
    paths = [entry["path"] for entry in files]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate FST file paths")
    return files, directories


def survey(root: Path) -> dict:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    directories = defaultdict(lambda: {"files": 0, "bytes": 0})
    for path in files:
        group = path.parent.relative_to(root).as_posix()
        directories[group]["files"] += 1
        directories[group]["bytes"] += path.stat().st_size

    boot_path = root / "sys/boot.bin"
    boot = boot_path.read_bytes()
    boot_fields = {
        "path": "sys/boot.bin", "sha256": sha256(boot_path),
        "disc_id_hex": boot[:6].hex(), "disc_id_ascii": boot[:6].decode("ascii"),
        "disc_number": boot[6], "revision": boot[7],
        "magic_at_0x1c": boot[0x1C:0x20].hex(),
        "title_at_0x20": boot[0x20:0x400].split(b"\0", 1)[0].decode("ascii"),
        "dol_disc_offset_at_0x420": struct.unpack_from(">I", boot, 0x420)[0],
        "fst_disc_offset_at_0x424": struct.unpack_from(">I", boot, 0x424)[0],
        "fst_size_at_0x428": struct.unpack_from(">I", boot, 0x428)[0],
        "bi2_country_word_at_0x18": struct.unpack_from(
            ">I", (root / "sys/bi2.bin").read_bytes(), 0x18
        )[0],
    }
    fst_path = root / "sys/fst.bin"
    fst_data = fst_path.read_bytes()
    fst_files, fst_dirs = fst_inventory(fst_data)
    expected = {entry["path"]: entry["size"] for entry in fst_files}
    actual = {path.relative_to(root / "files").as_posix(): path.stat().st_size
              for path in (root / "files").rglob("*") if path.is_file()}
    mismatches = [{"path": path, "fst_size": size, "actual_size": actual[path]}
                  for path, size in expected.items() if path in actual and actual[path] != size]

    fsys = [path for path in files if path.suffix == ".fsys"]
    signatures = Counter()
    for path in fsys:
        with path.open("rb") as stream:
            signatures[stream.read(4).hex()] += 1
    locale_groups = defaultdict(list)
    for path in fsys:
        base, _, suffix = path.stem.rpartition("_")
        if suffix in ("fr", "ge", "it", "sp"):
            locale_groups[base].append(suffix)

    banner_path = root / "files/opening.bnr"
    banner = banner_path.read_bytes()
    banner_records = [banner[offset:offset + 0x140]
                      for offset in range(0x1820, len(banner), 0x140)]
    videos = []
    for path in files:
        if path.suffix != ".thp":
            continue
        with path.open("rb") as stream:
            header = stream.read(48)
        videos.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                       "magic_hex": header[:4].hex(),
                       "version_hex": header[4:8].hex(),
                       "fps_at_0x10": struct.unpack_from(">f", header, 0x10)[0],
                       "frame_count_at_0x14": struct.unpack_from(">I", header, 0x14)[0]})

    return {
        "scope": "Static local files only; no target execution or ISO payload equality test",
        "file_count": len(files), "total_bytes": sum(path.stat().st_size for path in files),
        "extensions": dict(sorted(Counter(path.suffix for path in files).items())),
        "directories": dict(sorted(directories.items())), "boot": boot_fields,
        "fst": {"sha256": sha256(fst_path), "bytes": len(fst_data),
                "entry_count": len(fst_files) + len(fst_dirs) + 1,
                "file_count": len(fst_files), "directories": fst_dirs,
                "missing_files": sorted(set(expected) - set(actual)),
                "extra_files": sorted(set(actual) - set(expected)), "size_mismatches": mismatches,
                "disc_payload_range": [min(entry["disc_offset"] for entry in fst_files),
                                       max(entry["disc_offset"] + entry["size"] for entry in fst_files)]},
        "fsys": {"count": len(fsys), "magic_hex_counts": dict(signatures),
                 "name_prefix_counts": dict(Counter(path.stem.split("_")[0] for path in fsys).most_common()),
                 "locale_suffix_groups": dict(sorted(locale_groups.items())),
                 "locale_groups_with_unlabelled_peer": sorted(
                     base for base in locale_groups if (root / "files" / (base + ".fsys")).is_file())},
        "banner": {"sha256": sha256(banner_path), "bytes": len(banner),
                   "magic_ascii": banner[:4].decode("ascii"), "text_records": len(banner_records),
                   "text_record_bytes": 0x140, "text_records_identical": len(set(banner_records)) == 1,
                   "record_offsets": list(range(0x1820, len(banner), 0x140))},
        "videos": videos,
    }


def compare_iso(root: Path, iso_path: Path) -> dict:
    """Compare every extracted payload to the original FST-selected ISO range."""
    mismatches = []
    bytes_compared = 0
    iso_size = iso_path.stat().st_size
    with iso_path.open("rb") as source:
        def read_iso(offset: int, size: int) -> bytes:
            if offset < 0 or size < 0 or offset + size > iso_size:
                raise ValueError(f"ISO range out of bounds: {offset:#x}+{size:#x}")
            source.seek(offset)
            data = source.read(size)
            if len(data) != size:
                raise ValueError("Truncated ISO range")
            return data

        # Derive authoritative paths, offsets and complete sizes from the ISO,
        # rather than allowing shortened extracted sys files to validate a prefix.
        boot = read_iso(0, 0x440)
        if boot[0x1C:0x20] != bytes.fromhex("c2339f3d"):
            raise ValueError("Missing GameCube ISO magic")
        dol_offset, fst_offset, fst_size = struct.unpack_from(">III", boot, 0x420)
        fst_files, _ = fst_inventory(read_iso(fst_offset, fst_size))
        dol_header = read_iso(dol_offset, 0x100)
        dol_size = 0x100
        for index in range(18):
            section_offset = struct.unpack_from(">I", dol_header, index * 4)[0]
            section_size = struct.unpack_from(">I", dol_header, 0x90 + index * 4)[0]
            if section_size:
                if section_offset < 0x100:
                    raise ValueError("ISO DOL section overlaps its header")
                dol_size = max(dol_size, section_offset + section_size)
        apploader_header = read_iso(0x2440, 0x20)
        app_body, app_trailer = struct.unpack_from(">II", apploader_header, 0x14)
        sys_ranges = {"boot.bin": (0, 0x440), "bi2.bin": (0x440, 0x2000),
                      "apploader.img": (0x2440, 0x20 + app_body + app_trailer),
                      "main.dol": (dol_offset, dol_size), "fst.bin": (fst_offset, fst_size)}
        mappings = [(root / "files" / entry["path"], entry["disc_offset"], entry["size"])
                    for entry in fst_files]
        mappings.extend((root / "sys" / name, offset, size)
                        for name, (offset, size) in sys_ranges.items())
        for path, offset, size in sorted(mappings, key=lambda item: item[1]):
            if offset < 0 or offset + size > iso_size:
                raise ValueError(f"ISO range out of bounds for {path}")
            source.seek(offset)
            extracted_digest, iso_digest = hashlib.sha256(), hashlib.sha256()
            bytes_remaining = size
            actual_size = path.stat().st_size
            same_bytes = actual_size == size
            with path.open("rb") as extracted:
                while bytes_remaining:
                    length = min(bytes_remaining, 1024 * 1024)
                    actual = extracted.read(length)
                    expected = source.read(length)
                    if len(expected) != length:
                        raise ValueError(f"Truncated ISO data for {path}")
                    extracted_digest.update(actual)
                    iso_digest.update(expected)
                    same_bytes = same_bytes and actual == expected
                    bytes_remaining -= length
                for extra in iter(lambda: extracted.read(1024 * 1024), b""):
                    extracted_digest.update(extra)
                    same_bytes = False
            if not same_bytes:
                mismatches.append({"path": path.relative_to(root).as_posix(),
                                   "disc_offset": offset, "size": size,
                                   "actual_size": actual_size,
                                   "extracted_sha256": extracted_digest.hexdigest(),
                                   "iso_range_sha256": iso_digest.hexdigest()})
            bytes_compared += size
    return {"iso_name": iso_path.name, "iso_bytes": iso_size, "iso_sha256": sha256(iso_path),
            "fst_files_compared": len(fst_files), "sys_files_compared": 5,
            "sys_expected_sizes": {name: size for name, (_, size) in sys_ranges.items()},
            "bytes_compared": bytes_compared, "mismatches": mismatches,
            "all_ranges_byte_identical": not mismatches,
            "scope": "Exact byte comparison of FST payloads and five sys ranges; unused disc bytes not compared"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--iso", type=Path, help="Also compare every file to its ISO byte range")
    args = parser.parse_args()
    result = survey(args.game.resolve())
    if args.iso:
        result["iso_comparison"] = compare_iso(args.game.resolve(), args.iso.resolve())
        result["scope"] = "Static local files and exact ISO range comparison; no target execution"
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
