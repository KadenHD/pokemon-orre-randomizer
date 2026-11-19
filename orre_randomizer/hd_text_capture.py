"""Collect original GSmsg fonts with bounded reads from a verified raw disc.

The creation pipeline verifies the complete source image before calling this
reader. Only original DOL bytes and FSYS font members are retained in memory;
model archives are not decoded or accumulated. No input file is ever written.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import threading

from .engine.analyze_game import FormatError, decompress_lzss, u32
from .engine.survey_assets import fst_inventory
from .hd_text import font_banks_from_dol, font_banks_from_file

MAX_FONT_BYTES = 8 * 1024 * 1024


def collect_source_glyphs(source_iso: Path, *, game_id: str, cancel=None):
    """Return the declared retail DOL extent, all native glyphs and provenance.

    XD Europe/Japan deliberately use the declared regional executable size,
    including verified trailing padding, to match existing arena reservations.
    Cancellation is checked between every archive and member read.
    """
    from .engine.regions import region_for_boot
    from .service import checkpoint

    cancel = cancel or threading.Event()
    source_iso = Path(source_iso)
    if source_iso.is_symlink():
        raise FormatError("Original font source cannot be a symbolic link")
    size = source_iso.stat().st_size
    with source_iso.open("rb") as stream:
        def read(offset, length, label):
            checkpoint(cancel)
            if (offset < 0 or length < 0 or offset + length > size
                    or length > 16 * 1024 * 1024):
                raise FormatError("Original font source range is invalid: " + label)
            stream.seek(offset)
            payload = stream.read(length)
            if len(payload) != length:
                raise FormatError("Original font source is truncated: " + label)
            return payload

        boot = read(0, 0x440, "boot")
        if boot[:6] != game_id.encode("ascii"):
            raise FormatError("Original font source has another game identity")
        if game_id.startswith("GXX"):
            from .xd import region_for_boot as xd_region
            region = xd_region(boot)
        else:
            region = region_for_boot(boot)
        original = read(u32(boot, 0x420), region.dol_size, "DOL")
        banks, glyphs = font_banks_from_dol(original, source="original DOL")
        sources = [{"file": "main.dol", "sha256": hashlib.sha256(original).hexdigest(),
                    "banks": len(banks), "glyphs": len(glyphs)}]
        fst = read(u32(boot, 0x424), u32(boot, 0x428), "FST")
        entries, _ = fst_inventory(fst)
        archives = [entry for entry in entries
                    if "disc_offset" in entry and entry["path"].lower().endswith(".fsys")]
        font_members = 0
        for entry in archives:
            checkpoint(cancel)
            name, base, extent = entry["path"], entry["disc_offset"], entry["size"]
            if extent < 0x60 or base < 0 or base + extent > size:
                raise FormatError("Original font archive exceeds its disc range")
            header = read(base, 0x60, "FSYS header")
            if header[:4] != b"FSYS" or u32(header, 0x20) != extent:
                raise FormatError("Original font archive header differs")
            count, table = u32(header, 0xC), u32(header, 0x40)
            if count > 2048:
                raise FormatError("Original font member directory is invalid")
            if not count:
                continue
            if table < 0x60 or table + count * 4 > extent:
                raise FormatError("Original font member directory is invalid")
            pointers = read(base + table, count * 4, "FSYS member pointers")
            for index, (pointer,) in enumerate(struct.iter_unpack(">I", pointers)):
                if pointer < 0x60 or pointer + 0x30 > extent:
                    raise FormatError("Original font member header exceeds its archive")
                member = read(base + pointer, 0x30, "FSYS member header")
                identity = u32(member, 0)
                if identity & 0xFFFF != 0x0C00:
                    continue
                offset, expected, stored = u32(member, 4), u32(member, 8), u32(member, 0x14)
                if (not 0 < expected <= MAX_FONT_BYTES or not 0 < stored <= MAX_FONT_BYTES
                        or offset < 0x60 or offset + stored > extent):
                    raise FormatError("Original font member exceeds its bounded allocation")
                encoded = read(base + offset, stored, "FSYS font data")
                raw = decompress_lzss(encoded, MAX_FONT_BYTES) if encoded[:4] == b"LZSS" else encoded
                if len(raw) != expected:
                    raise FormatError("Original font member decoded size differs")
                logical = f"{name}/{index}:{identity:08x}"
                found_banks, found = font_banks_from_file(raw, source=logical)
                glyphs.extend(found)
                sources.append({"file": logical, "sha256": hashlib.sha256(raw).hexdigest(),
                                "banks": len(found_banks), "glyphs": len(found)})
                font_members += 1
    checkpoint(cancel)
    return original, glyphs, {"schema": 1, "game_id": game_id,
        "source_DOL_bytes": len(original), "archives_examined": len(archives),
        "font_members": font_members, "glyph_records": len(glyphs), "sources": sources,
        "input_modified": False, "reader": "bounded raw-disc font-only range reads"}
