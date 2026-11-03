"""Read-only Colosseum disc-tree analysis using Python's standard library.

No original game bytes are modified. Derived files go to a separate output tree.
All offsets in JSON are file offsets unless explicitly labelled as RAM addresses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path


class FormatError(ValueError):
    """A declared binary structure is outside the available bytes."""


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise FormatError(f"u32 outside file: {offset:#x}")
    return struct.unpack_from(">I", data, offset)[0]


def check_range(data: bytes, offset: int, size: int, label: str) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise FormatError(f"{label}: range {offset:#x}+{size:#x} outside {len(data):#x}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstring(data: bytes, offset: int, limit: int = 4096) -> str:
    if not 0 <= offset < len(data):
        raise FormatError(f"string pointer outside file: {offset:#x}")
    end = data.find(b"\0", offset, min(len(data), offset + limit))
    if end < 0:
        raise FormatError(f"unterminated string at {offset:#x}")
    return data[offset:end].decode("shift_jis", errors="replace")


def parse_dol(data: bytes) -> dict:
    check_range(data, 0, 0x100, "DOL header")
    sections = []
    for i in range(18):
        offset = u32(data, 4 * i)
        address = u32(data, 0x48 + 4 * i)
        size = u32(data, 0x90 + 4 * i)
        if not size:
            continue
        if offset < 0x100:
            raise FormatError("DOL section overlaps header")
        if address + size > 0x100000000:
            raise FormatError("DOL section exceeds 32-bit address space")
        check_range(data, offset, size, "DOL section")
        sections.append({"name": f"text{i}" if i < 7 else f"data{i - 7}",
                         "offset": offset, "ram_address": address, "size": size,
                         "sha256": sha256(data[offset:offset + size])})
    for i, left in enumerate(sections):
        for right in sections[i + 1:]:
            if max(left["offset"], right["offset"]) < min(
                    left["offset"] + left["size"], right["offset"] + right["size"]):
                raise FormatError("overlapping DOL file sections")
            if max(left["ram_address"], right["ram_address"]) < min(
                    left["ram_address"] + left["size"], right["ram_address"] + right["size"]):
                raise FormatError("overlapping DOL RAM sections")
    entry = u32(data, 0xE0)
    if not any(s["name"].startswith("text") and s["ram_address"] <= entry <
               s["ram_address"] + s["size"] for s in sections):
        raise FormatError("DOL entry is outside text sections")
    return {"format": "gamecube-dol", "byte_order": "big", "architecture": "powerpc",
            "sha256": sha256(data), "entry_ram_address": entry,
            "bss_ram_address": u32(data, 0xD8), "bss_size": u32(data, 0xDC),
            "sections": sections}


def parse_fsys(data: bytes) -> dict:
    check_range(data, 0, 0x60, "FSYS header")
    if data[:4] != b"FSYS":
        raise FormatError("missing FSYS magic")
    count, table = u32(data, 0xC), u32(data, 0x40)
    check_range(data, table, count * 4, "FSYS member pointer table")
    declared = u32(data, 0x20)
    if declared != len(data):
        raise FormatError(f"FSYS declared size {declared} != file size {len(data)}")
    members = []
    for i in range(count):
        header = u32(data, table + 4 * i)
        check_range(data, header, 0x30, "FSYS member header")
        offset, unpacked, stored = (u32(data, header + o) for o in (4, 8, 0x14))
        check_range(data, offset, stored, "FSYS member data")
        name_ptr = u32(data, header + 0x24)
        name = cstring(data, name_ptr) if name_ptr else ""
        is_lzss = stored >= 4 and data[offset:offset + 4] == b"LZSS"
        member = {"index": i, "name": name, "header_offset": header,
                  "identifier_raw": f"0x{u32(data, header):08x}",
                  "offset": offset, "stored_size": stored, "unpacked_size": unpacked,
                  "compression": "LZSS" if is_lzss else "none",
                  "sha256_stored": sha256(data[offset:offset + stored])}
        if is_lzss:
            if stored < 16:
                raise FormatError("LZSS member is shorter than its header")
            check_range(data, offset, 16, "LZSS header")
            if u32(data, offset + 4) != unpacked or u32(data, offset + 8) != stored:
                raise FormatError("FSYS and LZSS sizes disagree")
        elif stored != unpacked:
            raise FormatError("uncompressed FSYS member sizes disagree")
        members.append(member)
    return {"version_raw": f"0x{u32(data, 4):08x}", "group_id": u32(data, 8),
            "size": len(data), "member_count": count, "members": members}


def decompress_lzss(data: bytes, max_output: int = 64 * 1024 * 1024) -> bytes:
    from ..native_codec import decompress
    try:
        result = decompress(data, max_output)
    except ValueError as error:
        raise FormatError(str(error)) from error
    return result if result is not None else decompress_lzss_python(data, max_output)


def decompress_lzss_python(data: bytes, max_output: int = 64 * 1024 * 1024) -> bytes:
    """Decode the game's zero-filled 4 KiB ring, LSB-first LZSS stream.

    The stored-size word includes the 16-byte header. Reject overruns and
    truncated references rather than returning plausible partial game data.
    """
    check_range(data, 0, 16, "LZSS header")
    if data[:4] != b"LZSS":
        raise FormatError("missing LZSS magic")
    expected, stored = u32(data, 4), u32(data, 8)
    if expected > max_output:
        raise FormatError("LZSS output exceeds configured bound")
    if stored != len(data):
        raise FormatError("LZSS stored size mismatch")
    window, cursor, pos = bytearray(4096), 0xFEE, 16
    output = bytearray()
    while len(output) < expected:
        check_range(data, pos, 1, "LZSS flag")
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(output) == expected:
                break
            if flags & (1 << bit):
                check_range(data, pos, 1, "LZSS literal")
                values = [data[pos]]
                pos += 1
                length = 1
            else:
                check_range(data, pos, 2, "LZSS reference")
                a, b = data[pos:pos + 2]
                pos += 2
                source, length = a | ((b & 0xF0) << 4), (b & 0x0F) + 3
                values = None
            if len(output) + length > expected:
                raise FormatError("LZSS reference exceeds declared output")
            for k in range(length):
                value = values[0] if values is not None else window[(source + k) & 0xFFF]
                output.append(value)
                window[cursor] = value
                cursor = (cursor + 1) & 0xFFF
    if pos != stored:
        raise FormatError(f"unconsumed LZSS bytes: {stored - pos}")
    return bytes(output)


def parse_rel(data: bytes) -> dict:
    check_range(data, 0, 0x20, "REL version field")
    count, table, version = u32(data, 0xC), u32(data, 0x10), u32(data, 0x1C)
    if version != 3:
        raise FormatError(f"unsupported REL version {version}")
    check_range(data, 0, 0x4C, "REL v3 header")
    check_range(data, table, count * 8, "REL section table")
    sections = []
    for i in range(count):
        raw, size = u32(data, table + i * 8), u32(data, table + i * 8 + 4)
        offset = raw & ~3
        if offset:
            check_range(data, offset, size, "REL section")
        sections.append({"index": i, "offset": offset, "size": size,
                         "executable": bool(raw & 1), "bss": not offset and bool(size)})
    imp_offset, imp_size = u32(data, 0x28), u32(data, 0x2C)
    if imp_size % 8:
        raise FormatError("REL import table not aligned to 8 bytes")
    check_range(data, imp_offset, imp_size, "REL imports")
    imports = [{"module_id": u32(data, p), "relocations_offset": u32(data, p + 4)}
               for p in range(imp_offset, imp_offset + imp_size, 8)]
    for imported in imports:
        check_range(data, imported["relocations_offset"], 8, "REL relocation stream")
    for section_field, offset_field in ((0x30, 0x34), (0x31, 0x38), (0x32, 0x3C)):
        index, entry = data[section_field], u32(data, offset_field)
        if index >= count:
            raise FormatError("REL callback section outside section table")
        if index and (not sections[index]["executable"] or entry >= sections[index]["size"]):
            raise FormatError("REL callback outside executable section")
    # No relocations are applied: offsets remain source-file coordinates.
    return {"sha256": sha256(data), "size": len(data), "module_id": u32(data, 0),
            "version": version, "sections": sections, "imports": imports,
            "bss_size": u32(data, 0x20), "relocations_offset": u32(data, 0x24),
            "prolog_section": data[0x30], "prolog_section_offset": u32(data, 0x34),
            "epilog_section": data[0x31], "epilog_section_offset": u32(data, 0x38),
            "unresolved_section": data[0x32], "unresolved_section_offset": u32(data, 0x3C)}


def find_ascii(data: bytes, min_length: int = 6) -> list[dict]:
    import re
    return [{"offset": m.start(), "text": m.group().decode("ascii")}
            for m in re.finditer(rb"[\x20-\x7e]{" + str(min_length).encode() + rb",}", data)]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def analyze(game: Path, output: Path, extract: bool = False) -> dict:
    game, output = game.resolve(), output.resolve()
    if output == game or game in output.parents or output in game.parents:
        raise ValueError("output and game trees must be disjoint")
    manifest, archives, failures, extracted = [], [], [], []
    for path in sorted(game.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        relative = path.relative_to(game).as_posix()
        manifest.append({"path": relative, "size": len(data), "sha256": sha256(data)})
        if path.suffix.lower() == ".fsys":
            try:
                parsed = parse_fsys(data)
                archives.append({"path": relative, "sha256": sha256(data), **parsed})
                if path.name == "common.fsys":
                    # Trusted output names are generated from member indices;
                    # embedded filenames never become filesystem paths.
                    for member in parsed["members"]:
                        start, size = member["offset"], member["stored_size"]
                        raw = data[start:start + size]
                        decoded = decompress_lzss(raw) if member["compression"] == "LZSS" else raw
                        item = {"archive": relative, "member_index": member["index"],
                                "name": member["name"], "size": len(decoded), "sha256": sha256(decoded)}
                        if member["name"] == "common_rel":
                            write_json(output / "common-rel.json", parse_rel(decoded))
                            write_json(output / "common-rel-ascii.json", find_ascii(decoded))
                        if extract:
                            dest = output / "extracted" / "common" / f"{member['index']:03d}.bin"
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(decoded)
                            item["output_path"] = dest.relative_to(output).as_posix()
                        extracted.append(item)
            except (FormatError, UnicodeError) as exc:
                failures.append({"path": relative, "error": str(exc)})
        elif path.suffix.lower() == ".dol":
            write_json(output / "dol.json", parse_dol(data))
            write_json(output / "dol-ascii.json", find_ascii(data))
    compression = Counter(m["compression"] for a in archives for m in a["members"])
    summary = {"evidence_id": "LOCAL-STRUCTURE-001", "scope": "all regular files under game",
               "file_count": len(manifest), "total_bytes": sum(f["size"] for f in manifest),
               "fsys_count": len(archives), "fsys_member_count": sum(a["member_count"] for a in archives),
               "member_compression_counts": dict(compression), "failures": failures,
               "common_decoded": extracted,
               "limitations": ["Static parsing only; no game code executed.",
                               "Only common.fsys members are decompressed; other LZSS streams are header-validated.",
                               "REL relocation records are not applied.",
                               "ASCII runs are byte observations, not decoded localized string tables."]}
    write_json(output / "manifest.json", manifest)
    write_json(output / "fsys.json", archives)
    write_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--output", type=Path, default=Path("analysis/generated"))
    parser.add_argument("--extract-common", action="store_true", help="write decoded common members locally")
    args = parser.parse_args()
    result = analyze(args.game, args.output, args.extract_common)
    print(json.dumps({k: v for k, v in result.items() if k != "common_decoded"}, indent=2))
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
