"""Place game-folder runtime additions inside an already staged disc image."""
from __future__ import annotations

import struct
from pathlib import Path

from .engine.analyze_game import FormatError, u32
from .engine.survey_assets import fst_inventory


def executable_size(header: bytes) -> int:
    if len(header) != 0x100:
        raise FormatError("Truncated staged DOL header")
    return max([0x100] + [u32(header, i * 4) + u32(header, 0x90 + i * 4)
                         for i in range(18)])


def read_executable(image: Path) -> bytes:
    with Path(image).open("rb") as stream:
        boot = stream.read(0x440)
        if len(boot) != 0x440:
            raise FormatError("Truncated staged disc header")
        offset = u32(boot, 0x420)
        stream.seek(offset)
        size = executable_size(stream.read(0x100))
        if offset + size > Path(image).stat().st_size:
            raise FormatError("Staged executable exceeds disc bounds")
        stream.seek(offset)
        payload = stream.read(size)
        if len(payload) != size:
            raise FormatError("Truncated staged executable")
        return payload


def _free_offset(size, occupied, limit, alignment):
    cursor = 0
    for start, end in sorted([*occupied, (limit, limit)]):
        aligned = (cursor + alignment - 1) & -alignment
        if aligned + size <= start:
            return aligned
        cursor = max(cursor, end)
    raise FormatError("No safe disc gap for the game-folder runtime")


def update_staged_disc(image: Path, executable: bytes, archives=None) -> dict:
    """Write only checked payloads/FST/boot pointers; never grow or rebuild a disc.

    The caller owns the temporary output. Existing non-replaced files, boot
    data, apploader and FST reservation are occupied ranges, even if a replacement
    executable or archive is larger than its previous location.
    """
    image, archives = Path(image), dict(archives or {})
    if (not isinstance(executable, bytes) or len(executable) < 0x100
            or executable_size(executable[:0x100]) != len(executable)):
        raise FormatError("Invalid game-folder executable extent")
    if any(not isinstance(value, bytes) or not value for value in archives.values()):
        raise FormatError("Invalid game-folder archive payload")
    limit = image.stat().st_size
    with image.open("r+b") as stream:
        boot = stream.read(0x440)
        if len(boot) != 0x440:
            raise FormatError("Truncated staged disc header")
        old_dol = u32(boot, 0x420)
        stream.seek(old_dol)
        old_size = executable_size(stream.read(0x100))
        fst_offset, fst_size, fst_max = (u32(boot, at) for at in (0x424, 0x428, 0x42C))
        if not (0x440 <= fst_offset <= limit - max(fst_size, fst_max)
                and 0x440 <= old_dol <= limit - old_size):
            raise FormatError("Staged system ranges exceed disc bounds")
        stream.seek(fst_offset)
        fst = bytearray(stream.read(fst_size))
        entries, _ = fst_inventory(fst)
        files = {entry["path"]: entry for entry in entries if "disc_offset" in entry}
        if archives.keys() - files.keys():
            raise FormatError("Game-folder archive is absent from the staged FST")
        stream.seek(0x2440)
        app = stream.read(0x20)
        if len(app) != 0x20:
            raise FormatError("Truncated staged apploader")
        app_end = 0x2460 + u32(app, 0x14) + u32(app, 0x18)
        occupied = [(0, app_end), (fst_offset, fst_offset + max(fst_size, fst_max))]
        occupied += [(e["disc_offset"], e["disc_offset"] + e["size"])
                     for name, e in files.items() if name not in archives and e["size"]]
        if any(start < 0 or end > limit or start > end for start, end in occupied):
            raise FormatError("Staged file ranges exceed disc bounds")
        placements = []
        for name, payload in sorted(archives.items()):
            entry = files[name]
            offset = _free_offset(len(payload), occupied, limit, 32)
            occupied.append((offset, offset + len(payload)))
            placements.append((offset, payload))
            struct.pack_into(">II", fst, entry["index"] * 12 + 4, offset, len(payload))
        if (old_dol + len(executable) <= limit and
                all(old_dol >= end or old_dol + len(executable) <= start for start, end in occupied)):
            dol_offset = old_dol
        else:
            dol_offset = _free_offset(len(executable), occupied, limit, 32)
        if dol_offset + len(executable) > limit:
            raise FormatError("Game-folder executable exceeds disc bounds")
        placements.extend(((dol_offset, executable), (fst_offset, bytes(fst)),
                           (0x420, struct.pack(">I", dol_offset))))
        # Every extent and placement is validated before the first write.
        for offset, payload in placements:
            stream.seek(offset)
            stream.write(payload)
        stream.flush()
        for offset, payload in placements:
            stream.seek(offset)
            if stream.read(len(payload)) != payload:
                raise OSError("Game-folder disc write verification failed")
    return {"dol_disc_offset": dol_offset,
            "archives": {name: {"disc_offset": u32(fst, files[name]["index"] * 12 + 4),
                                 "size": len(payload)} for name, payload in archives.items()}}
