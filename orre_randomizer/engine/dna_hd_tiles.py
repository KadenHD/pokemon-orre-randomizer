"""Independent native keypad textures and a guarded, composable parser bridge.

This module transforms caller-supplied bytes only. The original full atlas stays
present so the existing saved-Lugia and Spinda writers can finish normally. A
second parser hook copies their final artwork into nine independent image buffers,
then gives the retail HSD parser the true extended DAT size. Splitting removes
cross-products between cells; it does not enumerate arbitrary Spinda PIDs.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, parse_dol, parse_fsys, u32
from .colo_spinda_field import _LAYOUTS, _PARSE_SIGNATURE, _PARSE_WORD
from .dna_keypad import DNA_KEYPAD_SPECIES, _TILE_ORIGINS
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .rebuild_iso import decoded_member, repack_fsys
from .shiny_rules import _Code


CONTRACT = "dna-hd-independent-tiles-v1"
MAGIC = 0x444E4148  # DNAH, unused original DAT header word at0x1c.
_ACTIVE_MAGIC = 0x444E4149  # DNAI, per-buffer entry qualification until sync.
OLD_DAT_SIZE = 0x886AF
OLD_DATA_SIZE = 0x87BA4
ATLAS_OFFSET = 0x7820
ATLAS_SIZE = 0x80000
STRUCTURAL_SHA256 = "15d61b4e6a0bbb36309b2217be136f58ec624f5f6836aaed9934cbf32550635f"
_DIRECTORY_BYTES = OLD_DAT_SIZE - 32 - OLD_DATA_SIZE
_KEY_ORIGINS = ((896, 0), (896, 128), (896, 256), (896, 384), (896, 512),
                (736, 0), (736, 128), (736, 256), (736, 384))
_MARKER = b"ORRE_DNA_HD_TILES_V1\0".ljust(32, b"\0")
_FRAME = 0xB0
_REG_BASE = 0x10
_SPECIAL = {"lr": 0x88, "cr": 0x8C, "ctr": 0x90, "xer": 0x94}


def _layout() -> dict:
    data_at = (OLD_DATA_SIZE + 31) & ~31
    first = data_at + 32
    cells = []
    for model_index, (x, y) in enumerate(_KEY_ORIGINS):
        crop_x, crop_y = x - 40, max(0, y - 8)
        width = 1024 - crop_x if x == 896 else 176
        height = 136 if y == 0 else 144
        size = width * height // 2
        screen = _TILE_ORIGINS.index((x, y))
        cells.append({
            "model_index": model_index, "screen_index": screen,
            "original_species": DNA_KEYPAD_SPECIES[screen],
            "crop_x": crop_x, "crop_y": crop_y, "width": width, "height": height,
            "art_x": x - crop_x, "art_y": y - crop_y, "art_size": 128,
            "source_file_offset": ATLAS_OFFSET + (crop_y // 8 * 128 + crop_x // 8) * 32,
            "data_offset": data_at, "file_offset": data_at + 32,
            "bytes": size, "row_bytes": width // 8 * 32, "rows": height // 8,
            "image_descriptor_file_offset": 32 + 0x46D0 + model_index * 0xA0,
            "uv_indices": list(range(84 + model_index * 8, 92 + model_index * 8)),
        })
        data_at += size
    return {"contract": CONTRACT, "magic": MAGIC, "old_dat_size": OLD_DAT_SIZE,
            "old_data_size": OLD_DATA_SIZE, "new_data_size": data_at,
            "relocation_count": 694,
            "new_dat_size": 32 + data_at + _DIRECTORY_BYTES,
            "atlas_file_offset": ATLAS_OFFSET, "atlas_bytes": ATLAS_SIZE,
            "buffer_file_offset": first, "buffer_bytes": data_at + 32 - first,
            "cells": cells}


def _validated_layout(report: dict) -> dict:
    expected = _layout()
    from .dna_spinda_hd import CONTRACT as SPINDA_CONTRACT, expanded_layout
    if isinstance(report, dict) and report.get("contract") == SPINDA_CONTRACT:
        spec = report.get("spinda_diagram")
        if not isinstance(spec, dict):
            raise FormatError("Missing independent Spinda diagram layout")
        expected = expanded_layout(expected, spec.get("samples"))
    if not isinstance(report, dict) or any(report.get(key) != value for key, value in expected.items()):
        raise FormatError("unexpected independent DNA tile layout contract")
    # Use fresh trusted constants, never addresses recovered from external JSON.
    return expected


def split_keypad_dat(dat: bytes) -> tuple[bytes, dict]:
    """Split verified native geometry, preserving existing atlas writers' input.

    The fingerprint permits the existing atlas replacements and marker at0x18;
    every other native byte must match the audited original. Appended buffers are
    exact CMPR macroblock crops, including the filtering neighborhood. Coordinates
    are remapped only for the eight UV entries exclusively owned by each cell.
    """
    if not isinstance(dat, bytes) or len(dat) != OLD_DAT_SIZE:
        raise FormatError("unexpected native DNA keypad DAT size")
    if u32(dat, 0x18) not in (0, 0x53504B44) or u32(dat, 0x1C):
        raise FormatError("unexpected or already split DNA keypad marker")
    canonical = bytearray(dat)
    canonical[0x18:0x1C] = bytes(4)
    canonical[ATLAS_OFFSET:ATLAS_OFFSET + ATLAS_SIZE] = bytes(ATLAS_SIZE)
    if hashlib.sha256(canonical).hexdigest() != STRUCTURAL_SHA256:
        raise FormatError("DNA keypad geometry or directory differs from the verified original")
    if struct.unpack_from(">5I", dat) != (OLD_DAT_SIZE, OLD_DATA_SIZE, 694, 1, 0):
        raise FormatError("unexpected native DNA keypad directory")
    report = _layout()
    data = bytearray(dat[32:32 + OLD_DATA_SIZE])
    data.extend(bytes(((OLD_DATA_SIZE + 31) & ~31) - len(data)))
    for cell in report["cells"]:
        assert len(data) == cell["data_offset"]
        for row in range(cell["rows"]):
            start = cell["source_file_offset"] + row * 4096
            data.extend(dat[start:start + cell["row_bytes"]])
        desc = cell["image_descriptor_file_offset"] - 32
        if struct.unpack_from(">IHHII", data, desc) != (0x7800, 1024, 1024, 14, 0):
            raise FormatError("unexpected DNA tile image descriptor")
        struct.pack_into(">IHH", data, desc, cell["data_offset"], cell["width"], cell["height"])
        for index in cell["uv_indices"]:
            at = 0x3E60 + index * 8
            u, v = struct.unpack_from(">ff", data, at)
            struct.pack_into(">ff", data, at,
                             (u * 1024 - cell["crop_x"]) / cell["width"],
                             (v * 1024 - cell["crop_y"]) / cell["height"])
    header = bytearray(dat[:32])
    struct.pack_into(">II", header, 0, report["new_dat_size"], report["new_data_size"])
    struct.pack_into(">I", header, 0x1C, MAGIC)
    result = bytes(header) + bytes(data) + dat[32 + OLD_DATA_SIZE:]
    if len(result) != report["new_dat_size"]:
        raise FormatError("independent DNA tile serialization changed its expected bounds")
    return result, report | {"source_sha256": hashlib.sha256(dat).hexdigest(),
                             "generated_sha256": hashlib.sha256(result).hexdigest(),
                             "runtime_padding_policy": "initial-padding-fixed-own-art-128-only",
                             "dynamic_spinda_pids_enumerated": False}


def split_keypad_archive(archive: bytes) -> tuple[bytes, dict]:
    """Replace only the unique native dnakey member in caller-owned FSYS bytes."""
    members = parse_fsys(archive)["members"]
    matches = [row for row in members if row["identifier_raw"] == "0x107e0200"]
    if len(matches) != 1:
        raise FormatError("expected one native DNA keypad model")
    member = matches[0]
    dat, report = split_keypad_dat(decoded_member(archive, member))
    output, _ = repack_fsys(archive, {member["index"]: dat})
    return output, report | {"archive": "DNA_key.fsys", "member": member["name"],
                             "resource": member["identifier_raw"]}


def _load(c: _Code, register: int, value: int) -> None:
    c.emit(0x3C000000 | register << 21 | value >> 16,
           0x60000000 | register << 21 | register << 16 | (value & 65535))


def _lw(register, base, displacement):
    return 0x80000000 | register << 21 | base << 16 | (displacement & 65535)


def _st(register, base, displacement):
    return 0x90000000 | register << 21 | base << 16 | (displacement & 65535)


def _reg_slot(register):
    return _REG_BASE + (register - 2) * 4


def _save(c):
    c.emit(0x94210000 | ((-_FRAME) & 65535), _st(0, 1, 8))
    for register in range(2, 32):
        c.emit(_st(register, 1, _reg_slot(register)))
    for instruction, name in ((0x7C0802A6, "lr"), (0x7C000026, "cr"),
                              (0x7C0902A6, "ctr"), (0x7C0102A6, "xer")):
        c.emit(instruction, _st(0, 1, _SPECIAL[name]))


def _restore(c):
    for name, instruction in (("xer", 0x7C0103A6), ("ctr", 0x7C0903A6),
                              ("cr", 0x7C0FF120), ("lr", 0x7C0803A6)):
        c.emit(_lw(0, 1, _SPECIAL[name]), instruction)
    for register in range(2, 32):
        c.emit(_lw(register, 1, _reg_slot(register)))
    c.emit(_lw(0, 1, 8), 0x38210000 | _FRAME)


def _guards(c, layout, *, entry):
    # No DAT dereference before all arguments and its entire MEM1 range pass.
    for register in (3, 4):
        c.emit(0x28000000 | register << 16)
        c.conditional(0x41820000, "restore")
    if entry:
        _load(c, 0, layout["new_dat_size"])
        c.emit(0x7C050040)  # cmplw r5,r0
        c.conditional(0x40820000, "restore")
    else:
        _load(c, 0, OLD_DAT_SIZE)
        c.emit(0x7C050040)
        c.conditional(0x40820000, "restore")
    c.emit(0x70800003)  # andi. r0,r4,3
    c.conditional(0x40820000, "restore")
    _load(c, 0, 0x80000000)
    c.emit(0x7C040040)
    c.conditional(0x41800000, "restore")
    _load(c, 0, 0x81800000 - layout["new_dat_size"])
    c.emit(0x7C040040)
    c.conditional(0x41810000, "restore")
    for offset, expected in ((0, layout["new_dat_size"]), (4, layout["new_data_size"]),
                             (8, layout["relocation_count"]), (12, 1), (16, 0),
                             (28, MAGIC if entry else _ACTIVE_MAGIC)):
        c.emit(_lw(6, 4, offset))
        _load(c, 0, expected)
        c.emit(0x7C060040)
        c.conditional(0x40820000, "restore")


def _entry_stub(address, parser, chained, layout):
    c = _Code(address)
    _save(c)
    _guards(c, layout, entry=True)
    # This per-buffer marker proves the entry saw its true caller-supplied
    # length. No global flag or borrowed argument register crosses old hooks.
    _load(c, 0, _ACTIVE_MAGIC)
    c.emit(_st(0, 4, 28))
    _load(c, 0, OLD_DAT_SIZE)
    c.emit(_st(0, 1, _reg_slot(5)))
    c.label("restore")
    _restore(c)
    if chained is None:
        c.emit(_PARSE_WORD)
    c.emit(branch(address + len(c.words) * 4, chained if chained is not None else parser + 4))
    return c.finish()


def _sync_stub(address, parser, flush, invalidate, layout):
    c = _Code(address)
    _save(c)
    _guards(c, layout, entry=False)
    _load(c, 0, MAGIC)
    c.emit(_st(0, 4, 28))
    _load(c, 0, layout["new_dat_size"])
    c.emit(_st(0, 1, _reg_slot(5)))
    for index, cell in enumerate(layout["cells"]):
        # The filtering border remains the initial crop. The native footprint
        # reaches at most the first two pixels of the next tile's four-pixel
        # invariant bevel. Copying all eight padding rows would additionally
        # hash its unseen, appearance-dependent artwork and recouple the cells.
        source = (cell["source_file_offset"] + cell["art_y"] // 8 * 4096
                  + cell["art_x"] // 8 * 32)
        destination = (cell["file_offset"] + cell["art_y"] // 8 * cell["row_bytes"]
                       + cell["art_x"] // 8 * 32)
        _load(c, 6, source)
        c.emit(0x7CC43214)  # add r6,r4,r6
        _load(c, 7, destination)
        c.emit(0x7CE43A14, 0x39000010)  # add r7,r4,r7; li r8,16
        c.label(f"row_{index}")
        c.emit(0x39200080, 0x7D2903A6)  # 512-byte CMPR artwork row / four.
        c.label(f"word_{index}")
        c.emit(_lw(0, 6, 0), _st(0, 7, 0), 0x38C60004, 0x38E70004)
        c.conditional(0x42000000, f"word_{index}")  # bdnz
        c.emit(0x38C60E00, 0x38E70000 | (cell["row_bytes"] - 512),
               0x3908FFFF, 0x28080000)
        c.conditional(0x40820000, f"row_{index}")
    for selected in layout.get("spinda_diagram", {}).get("cells", []):
        cell = layout["cells"][selected["model_index"]]
        left, top, _ = selected["diagram_in_cell"]
        tag = str(selected["original_species"])
        # The old full atlas also serves the case/buttons. Its UVs do not use
        # the diagram, but hashing the invisible dynamic pixels would still
        # create a PID-dependent full-atlas key. Restore both static resources.
        targets = ((cell["file_offset"] + top // 8 * cell["row_bytes"] + left // 8 * 32, cell["row_bytes"]),
                   (cell["source_file_offset"] + top // 8 * 4096 + left // 8 * 32, 4096))
        for target_index, (destination, stride) in enumerate(targets):
            label = f"{tag}_{target_index}"
            _load(c, 6, selected["frozen_diagram_data_offset"] + 32)
            c.emit(0x7CC43214)
            _load(c, 7, destination)
            c.emit(0x7CE43A14, 0x39000004)
            c.label(f"spinda_restore_row_{label}")
            c.emit(0x39200020, 0x7D2903A6)
            c.label(f"spinda_restore_word_{label}")
            c.emit(_lw(0, 6, 0), _st(0, 7, 0), 0x38C60004, 0x38E70004)
            c.conditional(0x42000000, f"spinda_restore_word_{label}")
            c.emit(0x38E70000 | (stride - 128), 0x3908FFFF, 0x28080000)
            c.conditional(0x40820000, f"spinda_restore_row_{label}")
        # Select independent spot textures using the SAME resolved PID/shiny
        # record already used by the old native diagram writer. No RNG reroll.
        record = layout.get("_spinda_pid_records", {}).get(selected["original_species"])
        if record is None:
            raise FormatError("Spinda diagram bridge has no qualified native PID record")
        _load(c, 6, record["address"])
        c.emit(_lw(7, 6, 4), 0x28070001)
        c.conditional(0x40820000, f"spinda_done_{tag}")
        c.emit(_lw(8, 6, 8), _lw(9, 6, 12), 0x28090001)
        c.conditional(0x41810000, f"spinda_done_{tag}")
        _load(c, 10, selected["body_data_offsets"][0])
        c.emit(0x28090000)
        c.conditional(0x41820000, f"spinda_body_{tag}")
        _load(c, 10, selected["body_data_offsets"][1])
        c.label(f"spinda_body_{tag}")
        _load(c, 12, selected["body_image_descriptor_file_offset"])
        c.emit(0x7D846214, _st(10, 12, 0))
        spec = layout["spinda_diagram"]
        offsets = [spec["background_data_offsets"], *[
            [spec["spot_data_offsets"][shiny][spot] for shiny in range(2)] for spot in range(4)]]
        for index, (desc, choices) in enumerate(zip(selected["image_descriptors"], offsets)):
            _load(c, 10, choices[0])
            c.emit(0x28090000)
            c.conditional(0x41820000, f"spinda_color_{tag}_{index}")
            _load(c, 10, choices[1])
            c.label(f"spinda_color_{tag}_{index}")
            if index:
                c.emit(0x5507063E, 0x1CE70320, 0x7D4A3A14, 0x5508C23E)
                # clrlwi r7,r8,24; mulli r7,r7,800; add r10,r10,r7; srwi r8,r8,8
            _load(c, 12, desc + 32)
            c.emit(0x7D846214, _st(10, 12, 0))
        c.label(f"spinda_done_{tag}")
    if layout.get("spinda_diagram"):
        # The remaining nine ImageDesc belong only to case/display/bolts/code
        # lights (verified UV u<=0.684571; key ART starts at736/1024). Keep their
        # entire atlas immutable, including invisible Lugia/Spinda key pixels.
        spec = layout["spinda_diagram"]
        _load(c, 6, spec["frozen_case_atlas_data_offset"])
        for desc in spec["frozen_case_image_descriptor_file_offsets"]:
            _load(c, 7, desc)
            c.emit(0x7CE43A14, _st(6, 7, 0))
    _load(c, 3, layout["buffer_file_offset"])
    c.emit(0x7C641A14)  # add r3,r4,r3
    _load(c, 4, layout["buffer_bytes"])
    c.call(flush)
    if layout.get("spinda_diagram"):
        c.emit(0x80610000 | _reg_slot(4), 0x38630000 | ATLAS_OFFSET)
        _load(c, 4, ATLAS_SIZE)
        c.call(flush)
        c.emit(0x80610000 | _reg_slot(4), 0x38634500)
        _load(c, 4, 0xD00)
        c.call(flush)
    c.call(invalidate)
    c.label("restore")
    _restore(c)
    c.emit(0x7C0802A6, branch(address + (len(c.words) + 1) * 4, parser + 8))
    return c.finish()


def install_dna_hd_tile_bridge(original_dol: bytes, current_dol: bytes,
                               layout_report: dict) -> tuple[bytes, dict]:
    """Append entry/sync shims after validated existing text2 hooks.

    The entry temporarily passes the old size through existing native writers.
    The sync shim runs after their displaced stwu but before native mflr, restores
    the true size, copies only each cell's own128px artwork and preserves all
    GPRs/CR/XER/LR/CTR. Its initial filtering padding stays fixed so invisible
    neighboring artwork cannot multiply the cell's texture hashes.
    Cache helpers are the existing regional integer-only OS/GX routines. FPRs
    are untouched by this bridge. No process, path or save is accessed.
    """
    layout = _validated_layout(layout_report)
    region = dol_layout(original_dol)
    if layout.get("spinda_diagram"):
        from .dna_keypad_runtime import spinda_diagram_pid_records
        records = spinda_diagram_pid_records(current_dol)
        required = set(layout["spinda_diagram"]["samples"])
        if not required <= records.keys():
            raise FormatError("Independent Spinda diagrams lack the existing native identity writer")
        layout = dict(layout, _spinda_pid_records={old: records[old] for old in required})
    parser, flush, invalidate = _LAYOUTS[region.game_id]
    offset = parser - TEXT_TO_RAM
    if len(current_dol) < len(original_dol) or any(u32(original_dol, p) for p in (8, 0x50, 0x98)):
        raise FormatError("unexpected original/current DOL layout for DNA tile bridge")
    for index, expected in enumerate(_PARSE_SIGNATURE):
        if u32(original_dol, offset + index * 4) != expected:
            raise FormatError("unexpected original native HSD parser")
        if index and u32(current_dol, offset + index * 4) != expected:
            raise FormatError("native HSD parser continuation is already modified")
    section = (len(original_dol) + 31) & ~31
    size = u32(current_dol, 0x98)
    arena = region.set_arena_lo - TEXT_TO_RAM
    chained = None
    if size:
        end = region.section_ram + size
        if (size < 32 or size % 32 or section + size != len(current_dol)
                or (u32(current_dol, 8), u32(current_dol, 0x50)) != (section, region.section_ram)
                or current_dol[section:section + 32] != _arena_guard(end, region.arena_lo_store)
                or u32(current_dol, arena) != branch(region.set_arena_lo, region.section_ram)):
            raise FormatError("invalid existing DNA tile arena reservation")
        code = bytearray(current_dol[section:])
    else:
        if (len(current_dol) != len(original_dol) or u32(current_dol, 8) or u32(current_dol, 0x50)
                or u32(current_dol, arena) != region.arena_lo_store):
            raise FormatError("unexpected DOL section before DNA tile reservation")
        code = bytearray(32)
    if u32(current_dol, arena + 4) != 0x4E800020:
        raise FormatError("unexpected native arena setter continuation")
    first = u32(current_dol, offset)
    if first != _PARSE_WORD:
        if first & 0xFC000003 != 0x48000000:
            raise FormatError("unexpected existing native HSD parser entry hook")
        displacement = first & 0x03FFFFFC
        if displacement & (1 << 25):
            displacement -= 1 << 26
        chained = parser + displacement
        if not region.section_ram + 32 <= chained < region.section_ram + len(code):
            raise FormatError("existing HSD parser hook is outside its reserved text section")
    code.extend(_MARKER)
    entry = region.section_ram + len(code)
    entry_code = _entry_stub(entry, parser, chained, layout)
    code.extend(entry_code)
    sync = region.section_ram + len(code)
    sync_code = _sync_stub(sync, parser, flush, invalidate, layout)
    code.extend(sync_code)
    end = region.section_ram + len(code)
    if end >= 0x81700000:
        raise FormatError("DNA tile bridge exceeds the native arena reservation")
    code[:32] = _arena_guard(end, region.arena_lo_store)
    output = bytearray(current_dol[:section])
    output.extend(bytes(section - len(output)))
    output.extend(code)
    for position, value in ((8, section), (0x50, region.section_ram), (0x98, len(code)),
                            (arena, branch(region.set_arena_lo, region.section_ram)),
                            (offset, branch(parser, entry)), (offset + 4, branch(parser + 4, sync))):
        struct.pack_into(">I", output, position, value)
    parse_dol(bytes(output))
    return bytes(output), {"contract": CONTRACT, "game_id": region.game_id,
                           "entry": entry, "sync": sync, "parser": parser,
                           "chained_entry": chained, "flush": flush, "invalidate": invalidate,
                           "section_file_offset": section, "section_ram": region.section_ram,
                           "section_bytes": len(code), "reserved_end": end,
                           "entry_bytes": len(entry_code), "sync_bytes": len(sync_code),
                           "old_dat_size": OLD_DAT_SIZE, "new_dat_size": layout["new_dat_size"],
                           "layout": layout,
                           "runtime_padding_policy": "initial-padding-fixed-own-art-128-only",
                           "dynamic_spinda_pids_enumerated": False}
