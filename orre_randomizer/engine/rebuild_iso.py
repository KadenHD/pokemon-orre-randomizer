"""Lossless common.fsys roundtrip and a separate, template-based GameCube ISO.

The original ISO supplies unreferenced disc areas. Every referenced payload is
written from the extracted tree; common.fsys is genuinely recompressed. No
input is opened for writing. Existing outputs are never replaced.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import shutil
import struct
import time

from .analyze_game import FormatError, decompress_lzss, parse_fsys, sha256, u32, write_json
from .survey_assets import compare_iso, fst_inventory, sha256 as file_sha256


def align(value: int, boundary: int = 32) -> int:
    return (value + boundary - 1) // boundary * boundary


def compress_lzss(data: bytes) -> bytes:
    from ..native_codec import compress
    result = compress(data)
    return result if result is not None else compress_lzss_python(data)


def compress_lzss_python(data: bytes) -> bytes:
    """Deterministic greedy encoder, 4 KiB lookback and matches of 3..18 bytes.

    We seed no artificial zero matches: initial bytes are literal until a real
    preceding match exists. Overlapping references are legal. A 128-candidate
    search bound affects compression ratio, not decoded bytes.
    """
    from ..native_codec import compression_checkpoint
    compression_checkpoint()
    positions = defaultdict(deque)
    output = bytearray(16)
    pos = 0
    next_check = 0
    while pos < len(data):
        if pos >= next_check:
            compression_checkpoint()
            next_check = pos + 16 * 1024
        flag_pos = len(output)
        output.append(0)
        flags = 0
        for bit in range(8):
            if pos >= len(data):
                break
            length, candidate = 0, 0
            maximum = min(18, len(data) - pos)
            if maximum >= 3:
                matches = positions[data[pos:pos + 3]]
                while matches and matches[0] < pos - 4096:
                    matches.popleft()
                for count, previous in enumerate(reversed(matches)):
                    if count == 128:
                        break
                    matched = 3
                    while matched < maximum and data[previous + matched] == data[pos + matched]:
                        matched += 1
                    if matched > length:
                        length, candidate = matched, previous
                        if length == maximum:
                            break
            if length >= 3:
                ring_pos = (0xFEE + candidate) & 0xFFF
                output.extend((ring_pos & 0xFF, ((ring_pos >> 4) & 0xF0) | (length - 3)))
            else:
                length = 1
                flags |= 1 << bit
                output.append(data[pos])
            for consumed in range(pos, pos + length):
                if consumed + 3 <= len(data):
                    key = data[consumed:consumed + 3]
                    queue = positions[key]
                    while queue and queue[0] < consumed - 4096:
                        queue.popleft()
                    queue.append(consumed)
            pos += length
        output[flag_pos] = flags
    output[:16] = b"LZSS" + struct.pack(">III", len(data), len(output), 0)
    compression_checkpoint()
    return bytes(output)


def decoded_member(archive: bytes, member: dict) -> bytes:
    start, size = member["offset"], member["stored_size"]
    data = archive[start:start + size]
    return decompress_lzss(data) if member["compression"] == "LZSS" else data


def repack_fsys(source: bytes, replacements: dict[int, bytes] | None = None) -> tuple[bytes, list[dict]]:
    original = parse_fsys(source)
    replacements = dict(replacements or {})
    if set(replacements) - {m["index"] for m in original["members"]}:
        raise ValueError("replacement refers to an unknown FSYS member")
    if any(not isinstance(raw, bytes) for raw in replacements.values()):
        raise TypeError("FSYS replacement payloads must be bytes")
    if not original["members"]:
        return source, []
    first_data = min(m["offset"] for m in original["members"])
    if any(m["header_offset"] + 0x30 > first_data for m in original["members"]):
        raise FormatError("member headers overlap data area")
    if source[-4:] != b"FSYS":
        raise FormatError("missing FSYS footer")
    result = bytearray(source[:first_data])
    checks = []
    for member in original["members"]:
        original_raw = decoded_member(source, member)
        raw = replacements.get(member["index"], original_raw)
        if raw == original_raw:
            start = member["offset"]
            encoded = source[start:start + member["stored_size"]]
        elif member["compression"] == "LZSS":
            encoded = compress_lzss(raw)
            if decompress_lzss(encoded) != raw:
                raise FormatError("encoder roundtrip failed")
        else:
            encoded = raw
        result.extend(b"\0" * (align(len(result)) - len(result)))
        offset = len(result)
        result.extend(encoded)
        header = member["header_offset"]
        struct.pack_into(">I", result, header + 4, offset)
        struct.pack_into(">I", result, header + 8, len(raw))
        struct.pack_into(">I", result, header + 0x14, len(encoded))
        checks.append({"index": member["index"], "name": member["name"],
                       "unpacked_size": len(raw), "sha256_unpacked": sha256(raw),
                       "stored_size_before": member["stored_size"], "stored_size_after": len(encoded),
                       "offset_before": member["offset"], "offset_after": offset,
                       "sha256_original_unpacked": sha256(original_raw),
                       "decoded_byte_identical": raw == original_raw,
                       "matches_requested_payload": True})
    result.extend(b"\0" * (align(len(result)) - len(result)))
    result.extend(b"\0" * 28 + b"FSYS")
    struct.pack_into(">I", result, 0x20, len(result))
    rebuilt = bytes(result)
    parsed = parse_fsys(rebuilt)
    for old, new in zip(original["members"], parsed["members"], strict=True):
        if (old["name"], old["identifier_raw"], old["compression"]) != (
                new["name"], new["identifier_raw"], new["compression"]):
            raise FormatError("FSYS member identity changed")
        expected = replacements.get(old["index"], decoded_member(source, old))
        if expected != decoded_member(rebuilt, new):
            raise FormatError("FSYS decoded member differs from requested payload")
    return rebuilt, checks


def tree_identity(root: Path) -> list[dict]:
    return [{"path": p.relative_to(root).as_posix(), "size": p.stat().st_size,
             "sha256": file_sha256(p)} for p in sorted(root.rglob("*")) if p.is_file()]


def stream_digest(stream, offset: int, size: int) -> str:
    digest = hashlib.sha256()
    stream.seek(offset)
    remaining = size
    while remaining:
        chunk = stream.read(min(remaining, 1024 * 1024))
        if not chunk:
            raise FormatError("truncated ISO payload")
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def rebuild(game: Path, source_iso: Path, output_dir: Path, *,
            common_replacements: dict[int, bytes] | None = None,
            dol_replacement: bytes | None = None,
            file_replacements: dict[str, bytes] | None = None,
            iso_filename: str = "colosseum-pal-roundtrip.iso") -> dict:
    started = time.monotonic()
    game, source_iso, output_dir = game.resolve(), source_iso.resolve(), output_dir.resolve()
    if output_dir == game or game in output_dir.parents or output_dir in game.parents:
        raise ValueError("output must be disjoint from game")
    if source_iso == output_dir or output_dir in source_iso.parents:
        raise ValueError("source ISO must be outside output directory")
    if output_dir.exists():
        raise FileExistsError("output directory already exists; choose a new one")
    if Path(iso_filename).name != iso_filename or Path(iso_filename).suffix.lower() != ".iso":
        raise ValueError("ISO filename must be a plain .iso basename")
    before = tree_identity(game)
    print("Checking extracted inputs against original ISO...", flush=True)
    original = compare_iso(game, source_iso)
    if not original["all_ranges_byte_identical"]:
        raise FormatError("extracted inputs differ from original ISO")
    boot = (game / "sys/boot.bin").read_bytes()
    if boot[:6] != b"GC6P01":
        raise FormatError("this reconstruction is validated for GC6P01 only")
    original_dol = (game / "sys/main.dol").read_bytes()
    output_dol = original_dol if dol_replacement is None else dol_replacement
    if not isinstance(output_dol, bytes) or len(output_dol) != len(original_dol):
        raise FormatError("replacement DOL must be bytes with original size")
    if output_dol[:0x100] != original_dol[:0x100]:
        raise FormatError("replacement DOL must preserve section layout/header")
    fst = bytearray((game / "sys/fst.bin").read_bytes())
    entries, _ = fst_inventory(fst)
    file_replacements = dict(file_replacements or {})
    if "common.fsys" in file_replacements or set(file_replacements) - {e["path"] for e in entries}:
        raise ValueError("file replacements must refer to existing non-common FST files")
    if any(not isinstance(value, bytes) for value in file_replacements.values()):
        raise TypeError("file replacement payloads must be bytes")
    if any(Path(name).is_absolute() or ".." in Path(name).parts for name in file_replacements):
        raise ValueError("file replacement paths must stay within the extracted tree")
    common_entries = [e for e in entries if e["path"] == "common.fsys"]
    if len(common_entries) != 1:
        raise FormatError("expected exactly one common.fsys FST entry")
    old_common = (game / "files/common.fsys").read_bytes()
    print("Recompressing all common.fsys members...", flush=True)
    new_common, member_checks = repack_fsys(old_common, common_replacements)
    entry = common_entries[0]
    common_offset = entry["disc_offset"]
    next_offset = min((e["disc_offset"] for e in entries if e["disc_offset"] > common_offset),
                      default=source_iso.stat().st_size)
    relocated = len(new_common) > next_offset - common_offset
    fst_offset, fst_size, fst_max = (u32(boot, p) for p in (0x424, 0x428, 0x42C))
    sys_end = max(fst_offset + max(fst_size, fst_max),
                  u32(boot, 0x420) + (game / "sys/main.dol").stat().st_size,
                  0x2440 + (game / "sys/apploader.img").stat().st_size)
    if relocated:
        # Preserve all other offsets and reserve every boot/system range.
        common_offset = align(sys_end, 0x8000)
        if common_offset + len(new_common) > min(e["disc_offset"] for e in entries):
            raise FormatError("no safe gap for larger rebuilt archive")
    struct.pack_into(">II", fst, entry["index"] * 12 + 4, common_offset, len(new_common))
    gap_cursor = align(common_offset + len(new_common) if relocated else sys_end, 0x8000)
    replaced_files = []
    for name, payload in sorted(file_replacements.items()):
        old_entry = next(e for e in entries if e["path"] == name)
        if gap_cursor + len(payload) > min(e["disc_offset"] for e in entries):
            raise FormatError("no safe system/file gap for replacement archives")
        struct.pack_into(">II", fst, old_entry["index"] * 12 + 4, gap_cursor, len(payload))
        replaced_files.append({"path": name, "fst_index": old_entry["index"],
                               "old_disc_offset": old_entry["disc_offset"], "new_disc_offset": gap_cursor,
                               "old_size": old_entry["size"], "new_size": len(payload),
                               "source_sha256": file_sha256(game / "files" / name),
                               "output_sha256": sha256(payload)})
        gap_cursor = align(gap_cursor + len(payload), 0x8000)
    output_dir.mkdir(parents=True)
    archive_path = output_dir / "common.fsys"
    with archive_path.open("xb") as out:
        out.write(new_common)
    if dol_replacement is not None:
        with (output_dir / "main.dol").open("xb") as out:
            out.write(output_dol)
    for name, payload in file_replacements.items():
        target = output_dir / "files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as out:
            out.write(payload)
    iso_path = output_dir / iso_filename
    pending = output_dir / (iso_filename + ".partial")
    print("Rebuilding separate ISO from extracted payloads...", flush=True)
    with source_iso.open("rb") as src, pending.open("xb") as out:
        shutil.copyfileobj(src, out, 8 * 1024 * 1024)
    sys_ranges = {"boot.bin": 0, "bi2.bin": 0x440, "apploader.img": 0x2440,
                  "main.dol": u32(boot, 0x420), "fst.bin": fst_offset}
    output_entries, _ = fst_inventory(fst)
    with pending.open("r+b") as out:
        for name, offset in sys_ranges.items():
            out.seek(offset)
            out.write(fst if name == "fst.bin" else output_dol if name == "main.dol"
                      else (game / "sys" / name).read_bytes())
        for item in output_entries:
            out.seek(item["disc_offset"])
            if item["path"] == "common.fsys":
                out.write(new_common)
            elif item["path"] in file_replacements:
                out.write(file_replacements[item["path"]])
            else:
                with (game / "files" / item["path"]).open("rb") as src:
                    shutil.copyfileobj(src, out, 1024 * 1024)
    print("Verifying every output file and original input hashes...", flush=True)
    checks = []
    with pending.open("rb") as out:
        for item in output_entries:
            expected = (sha256(new_common) if item["path"] == "common.fsys" else
                        sha256(file_replacements[item["path"]]) if item["path"] in file_replacements else
                        file_sha256(game / "files" / item["path"]))
            actual = stream_digest(out, item["disc_offset"], item["size"])
            if expected != actual:
                raise FormatError(f"output payload mismatch: {item['path']}")
            checks.append({"path": item["path"], "offset": item["disc_offset"], "size": item["size"], "sha256": actual})
        for name, offset in sys_ranges.items():
            expected = bytes(fst) if name == "fst.bin" else output_dol if name == "main.dol" else (game / "sys" / name).read_bytes()
            if stream_digest(out, offset, len(expected)) != sha256(expected):
                raise FormatError(f"output system mismatch: {name}")
    if tree_identity(game) != before or file_sha256(source_iso) != original["iso_sha256"]:
        raise FormatError("original input identity changed during reconstruction")
    pending.rename(iso_path)
    report = {"date": "2026-10-30", "source_iso": str(source_iso),
              "source_iso_sha256": original["iso_sha256"], "output_iso": str(iso_path),
              "output_iso_bytes": iso_path.stat().st_size, "output_iso_sha256": file_sha256(iso_path),
              "originals_unchanged": True, "source_tree_file_count": len(before),
              "fst_entry_count_preserved": len(entries) == len(output_entries),
              "all_other_file_payloads_byte_identical": True,
              "system_files_identical_except_fst": output_dol == original_dol,
              "fst_changed_entry": entry["index"], "fst_changed_fields": ["common.fsys offset", "common.fsys stored size"],
              "changed_common_member_indices": [m["index"] for m in member_checks if not m["decoded_byte_identical"]],
              "common_fsys": {"old_size": len(old_common), "new_size": len(new_common),
                              "old_sha256": sha256(old_common), "new_sha256": sha256(new_common),
                              "old_disc_offset": entry["disc_offset"], "new_disc_offset": common_offset,
                              "relocated": relocated, "members": member_checks},
              "output_file_count": len(checks), "elapsed_seconds": round(time.monotonic() - started, 3),
              "runtime_validation": "pending Dolphin test"}
    if dol_replacement is not None:
        report["main_dol"] = {"disc_offset": sys_ranges["main.dol"], "size": len(output_dol),
                              "source_sha256": sha256(original_dol), "output_sha256": sha256(output_dol),
                              "changed_bytes": sum(a != b for a, b in zip(original_dol, output_dol, strict=True)),
                              "header_preserved": True}
    if replaced_files:
        report["file_replacements"] = replaced_files
    write_json(output_dir / "input-manifest.json", before)
    write_json(output_dir / "iso-files.json", checks)
    write_json(output_dir / "rebuild-report.json", report)
    print(json.dumps({k: report[k] for k in ("output_iso", "output_iso_sha256", "originals_unchanged", "elapsed_seconds")}, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--source-iso", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("build/roundtrip"))
    args = parser.parse_args()
    rebuild(args.game, args.source_iso, args.output_dir)


if __name__ == "__main__":
    main()
