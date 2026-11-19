"""Guarded GSmsg static-page bridge for the six verified retail executables.

Pages are DOL-owned, never registered in GSres or the GStexture allocation pool.
GStextureLoad initializes each page in place once. Only the texture selection is
borrowed during a glyph draw, then the original dynamic texture and UV cursor
are restored. Transparent margins extend only the draw quad, after the native
bitmap copy; original advances, visible samples, colour and outline stay native.
The temporary task origin is restored before returning. No phrase hash
enumeration or host-side process watcher is involved.
"""
from __future__ import annotations

import hashlib
import struct

from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code
from .hd_text import CONTRACT, build_native_pages, select_runtime_glyphs

BRIDGE_CONTRACT = "orre-gsmsg-borrowed-static-pages-v2"
COUNTER_LAYOUT = {
    "version": 2,
    "state_bytes": 64,
    "offsets": {"hits": 20, "fallbacks_total": 24, "lookup_calls": 28,
                "zero_area_native_calls": 44, "nonzero_area_native_fallbacks": 48},
    "fallbacks_total_includes_zero_area": True,
    "zero_area_policy": "native draw width or height is zero; no glyph pixels missing",
    "nonzero_area_policy": "nondegenerate native quad; opacity and missing HD artwork are not inferred",
    "unit": "draw calls, not unique glyphs",
}
_MARKER = b"ORRE_STATIC_GSMSG_PAGES_V2\0".ljust(32, b"\0")
# Original SHA, MakeTexture, size, pre/post drawing, manager SDA,
# GStextureLoad, gfxLoadTexture / GSgfxSelectTexture, GetCodeInfo.
_REGIONS = {
 "GC6E01": ("7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4", 0x800FD69C, 0x880, 0x800FDA60, 0x800FDECC, 0x82E8, 0x800EFD3C, 0x800D85D4, 0x800FDF1C),
 "GC6P01": ("a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5", 0x80100BB0, 0x880, 0x80100F74, 0x801013E0, 0x82E8, 0x800F33BC, 0x800DBC24, 0x80101430),
 "GC6J01": ("64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2", 0x800FB038, 0x8D8, 0x800FB458, 0x800FB8C4, 0x82D8, 0x800EDA04, 0x800D5D54, 0x800FB910),
 "GXXE01": ("c8659341c252d1b088753d508769344eb6f092b5da5cc7cc0ce1560b32478c15", 0x8010A3F8, 0x9A0, 0x8010A7BC, 0x8010AD48, 0x8528, 0x80102BCC, 0x802B777C, 0x8010AD98),
 "GXXP01": ("2aac980e639d813172986c2987baae9285a3bf607ef8e64e76cba9a140ea4406", 0x8010BA84, 0x9A0, 0x8010BE48, 0x8010C3D4, 0x8528, 0x8010422C, 0x802B96DC, 0x8010C424),
 "GXXJ01": ("8be82e82509a2a1662b2ab04ad2f7166f9bcd2ac0e7056acc34b83daaefd4ca1", 0x80105E34, 0x9A0, 0x801061F8, 0x80106784, 0x8524, 0x800FEF50, 0x802B21A4, 0x801067D4),
}
_EXACT_DOL_VARIANTS = {
    # XD's FST-declared retail image includes a verified224-byte trailing pad.
    "GXXP01": {"a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd"},
    "GXXJ01": {"14c129cc0f79682574f635290b09e37fa2a652ac5aa5565281bd583c31c5d702"},
}


def _offset(data, address):
    for section in parse_dol(data)["sections"]:
        if section["ram_address"] <= address < section["ram_address"] + section["size"]:
            return section["offset"] + address - section["ram_address"]
    raise FormatError("Text bridge address leaves the original DOL")


def _d(op, reg, base, displacement=0):
    return op << 26 | reg << 21 | base << 16 | (displacement & 65535)


def _x(op, target, a, b, *, record=False):
    if op == 444:  # or: RS/RA are reversed relative to integer arithmetic.
        target, a = a, target
    return 31 << 26 | target << 21 | a << 16 | b << 11 | op << 1 | int(record)


def _rl(target, source, shift, begin, end):
    return 21 << 26 | source << 21 | target << 16 | shift << 11 | begin << 6 | end << 1


def _load(c, reg, value):
    c.emit(_d(15, reg, 0, value >> 16), 24 << 26 | reg << 21 | reg << 16 | (value & 65535))


def _save(c, floating=False):
    frame = 0x1C0 if floating else 0xB0
    c.emit(_d(37, 1, 1, -frame), _d(36, 0, 1, 8))
    for reg in range(2, 32):
        c.emit(_d(36, reg, 1, 0x10 + (reg - 2) * 4))
    for instruction, slot in ((0x7C0802A6, 0x90), (0x7C000026, 0x94),
                              (0x7C0902A6, 0x98), (0x7C0102A6, 0x9C)):
        c.emit(instruction, _d(36, 0, 1, slot))
    if floating:
        for reg in range(14):
            at = 0xB0 + reg * 16
            c.emit(_d(54, reg, 1, at), 60 << 26 | reg << 21 | 1 << 16 | at + 8)
        c.emit(0xFC00048E, _d(54, 0, 1, 0x1A0))  # mffs; stfd FPSCR


def _restore(c, floating=False):
    if floating:
        c.emit(_d(50, 0, 1, 0x1A0), 0xFDFE058E)  # lfd; mtfsf 255,f0
        for reg in range(14):
            at = 0xB0 + reg * 16
            c.emit(56 << 26 | reg << 21 | 1 << 16 | at + 8, _d(50, reg, 1, at))
    for slot, instruction in ((0x9C, 0x7C0103A6), (0x98, 0x7C0903A6),
                              (0x94, 0x7C0FF120), (0x90, 0x7C0803A6)):
        c.emit(_d(32, 0, 1, slot), instruction)
    for reg in range(2, 32):
        c.emit(_d(32, reg, 1, 0x10 + (reg - 2) * 4))
    c.emit(_d(32, 0, 1, 8), _d(14, 1, 1, 0x1C0 if floating else 0xB0))


def _return(c, native, instruction):
    c.emit(instruction, branch(c.address + (len(c.words) + 1) * 4, native + 4))
    return c.finish()


def _remember_code(address, native, instruction, state):
    c = _Code(address)
    _save(c)
    _load(c, 11, state)
    c.emit(_d(36, 3, 11), _d(36, 4, 11, 4))
    _restore(c)
    return _return(c, native, instruction)


def _lookup(address, native, instruction, state, table, count):
    c = _Code(address)
    _save(c)
    _load(c, 31, state)
    c.emit(_d(14, 0, 0, 0), _d(36, 0, 31, 8), _d(32, 11, 31), _x(32, 0, 11, 3))
    c.conditional(0x40820000, "done")  # this work must immediately consume GetCodeInfo
    c.emit(_d(36, 0, 31), _d(32, 11, 31, 28), _d(14, 11, 11, 1), _d(36, 11, 31, 28))
    for reg in (5, 6):
        c.emit(_d(11, 0, reg, 1))
        c.conditional(0x41800000, "done")
        c.emit(_d(11, 0, reg, 40))
        c.conditional(0x41810000, "done")
    c.emit(_d(40, 30, 3, 0x20), _rl(30, 30, 16, 0, 15),
           _d(32, 11, 31, 4), _rl(11, 11, 0, 16, 31), _x(444, 30, 30, 11))
    # Metrics retain the signed byte's original representation.
    c.emit(_rl(28, 5, 24, 0, 7), _rl(11, 6, 16, 8, 15), _x(444, 28, 28, 11),
           _rl(11, 7, 8, 16, 23), _x(444, 28, 28, 11),
           _x(444, 24, 4, 4), _d(14, 23, 5, 1), _rl(23, 23, 31, 1, 31),
           _x(444, 22, 6, 6), _d(14, 20, 0, 0), _d(14, 21, 0, count))
    _load(c, 27, table)
    # Lower-bound binary search by font id + Unicode code.
    c.label("search")
    c.emit(_x(32, 0, 20, 21))
    c.conditional(0x40800000, "candidate")
    c.emit(_x(266, 19, 20, 21), _rl(19, 19, 31, 1, 31), _rl(18, 19, 5, 0, 26),
           _x(266, 29, 27, 18), _d(32, 0, 29), _x(32, 0, 0, 30))
    c.conditional(0x40800000, "lower")
    c.emit(_d(14, 20, 19, 1))
    c.jump("search")
    c.label("lower")
    c.emit(_x(444, 21, 19, 19))
    c.jump("search")
    c.label("candidate")
    c.emit(_d(10, 0, 20, count))
    c.conditional(0x40800000, "done")
    c.emit(_rl(18, 20, 5, 0, 26), _x(266, 29, 27, 18),
           _d(32, 0, 29), _x(32, 0, 0, 30))
    c.conditional(0x40820000, "done")
    c.emit(_d(32, 0, 29, 4), _x(32, 0, 0, 28))
    c.conditional(0x40820000, "next")
    c.emit(_d(32, 17, 29, 8), _d(14, 17, 17, 128),
           _d(40, 16, 29, 12), _d(40, 15, 29, 14), _d(14, 14, 0, 0),
           _x(444, 25, 24, 24))
    # Exact native bitmap comparison, directly against the tiled immutable page.
    # SDA r2/r13 stay valid at every instruction, including interrupt boundaries.
    c.label("row")
    c.emit(_x(266, 12, 15, 14), _rl(11, 12, 29, 3, 31), _rl(11, 11, 11, 0, 20),
           _rl(12, 12, 2, 27, 29), _x(266, 11, 11, 12), _d(14, 10, 0, 0))
    c.label("column")
    c.emit(_rl(9, 10, 1, 0, 30), _x(266, 9, 16, 9),
           _rl(8, 9, 29, 3, 31), _rl(8, 8, 5, 0, 26),
           _rl(9, 9, 31, 30, 31), _x(266, 8, 8, 9), _x(266, 8, 8, 11),
           _x(87, 7, 17, 8), _x(87, 6, 25, 10),
           _d(32, 5, 29, 28), _d(11, 0, 5, 0))
    c.conditional(0x41820000, "compare")
    c.emit(_d(14, 0, 10, 1), _x(32, 0, 0, 23))
    c.conditional(0x40820000, "compare")
    c.emit(_x(87, 5, 5, 14), _x(444, 7, 7, 5))
    c.label("compare")
    c.emit(_x(32, 0, 7, 6))
    c.conditional(0x40820000, "next")
    c.emit(_d(14, 10, 10, 1), _x(32, 0, 10, 23))
    c.conditional(0x41800000, "column")
    c.emit(_x(266, 25, 25, 23), _d(14, 14, 14, 1), _x(32, 0, 14, 22))
    c.conditional(0x41800000, "row")
    c.emit(_d(36, 29, 31, 8))
    c.jump("done")
    c.label("next")
    c.emit(_d(14, 20, 20, 1))
    c.jump("candidate")
    c.label("done")
    _restore(c)
    return _return(c, native, instruction)


def _drawing(address, native, instruction, state, spec, *, after):
    _, _, _, _, _, manager, load, select, _ = spec
    cursor, textures, tex_index = (0x14, 8, 0x19) if cursor_is_xd(spec) else (0x18, 12, 0x1D)
    scale_x = 0x64 if cursor_is_xd(spec) else 0x60
    c = _Code(address)
    _save(c, True)
    _load(c, 31, state)
    c.emit(_d(32, 30, 13, manager))
    if after:
        c.emit(_d(32, 0, 31, 16), _d(11, 0, 0, 0))
        c.conditional(0x41820000, "done")
        c.emit(_d(32, 11, 31, 36), _d(11, 0, 11, 0))
        c.conditional(0x41820000, "position_restored")
        c.emit(_d(32, 0, 31, 40), _d(36, 0, 11, 0x0C),
               _d(14, 0, 0, 0), _d(36, 0, 31, 36))
        c.label("position_restored")
        c.emit(_d(32, 0, 31, 12), _d(36, 0, 30, cursor),
               _d(32, 4, 31, 32), _d(14, 3, 0, 0))
        c.call(select)
        c.emit(_d(14, 0, 0, 0), _d(36, 0, 31, 16))
    else:
        c.emit(_d(14, 0, 0, 0), _d(36, 0, 31, 36))
        c.emit(_d(32, 0, 30, cursor), _d(36, 0, 31, 12),
               _d(34, 3, 30, tex_index), _rl(3, 3, 2, 0, 29),
               _x(266, 3, 30, 3), _d(32, 29, 3, textures), _d(36, 29, 31, 32),
               _d(32, 28, 31, 8), _d(11, 0, 28, 0))
        c.conditional(0x41820000, "fallback")
        c.emit(_d(32, 27, 28, 8), _d(32, 0, 27, 0x28), _d(10, 0, 0, 128))
        c.conditional(0x40820000, "initialized")
        c.emit(_x(444, 3, 27, 27))
        c.call(load)
        c.label("initialized")
        # The retail handle's sampling settings remain authoritative.
        for at in range(0x10, 0x24, 4):
            c.emit(_d(32, 0, 29, at), _d(36, 0, 27, at))
        c.emit(_d(40, 0, 28, 12), _d(34, 11, 28, 16), _x(40, 0, 11, 0),
               _d(44, 0, 30, cursor),
               _d(40, 0, 28, 14), _d(34, 11, 28, 17), _x(40, 0, 11, 0),
               _d(44, 0, 30, cursor + 2),
               _d(14, 0, 0, 1), _d(36, 0, 31, 16),
               _d(32, 11, 31, 20), _d(14, 11, 11, 1), _d(36, 11, 31, 20),
               _x(444, 4, 27, 27), _d(14, 3, 0, 0))
        c.call(select)
        # The six exact pre-sites are after source copying and before XY/UV.
        # Modify only the saved volatile dimensions and temporary task origin.
        # r30 (retail copy stride/cursor advance) stays untouched.
        c.emit(_d(40, 11, 28, 20), _d(11, 0, 11, 0))
        c.conditional(0x41820000, "geometry_done")
        for register in (5, 8):
            c.emit(_d(36, 11, 1, 0x10 + (register - 2) * 4))
        c.emit(_d(40, 11, 28, 22))
        for register in (6, 9):
            c.emit(_d(36, 11, 1, 0x10 + (register - 2) * 4))
        c.emit(_d(32, 11, 1, 0x24), _d(34, 0, 28, 17),
               _x(40, 11, 0, 11), _d(36, 11, 1, 0x24),
               _d(32, 11, 1, 0x84), _d(36, 11, 31, 36),
               _d(32, 0, 11, 0x0C), _d(36, 0, 31, 40),
               _d(48, 0, 11, 0x0C), _d(48, 1, 11, scale_x), _d(48, 2, 28, 24),
               59 << 26 | 1 << 21 | 1 << 16 | 2 << 6 | 25 << 1,
               59 << 26 | 0 << 21 | 0 << 16 | 1 << 11 | 20 << 1,
               _d(52, 0, 11, 0x0C))
        c.label("geometry_done")
        c.jump("done")
        c.label("fallback")
        c.emit(_d(14, 0, 0, 0), _d(36, 0, 31, 16),
               _d(32, 11, 31, 24), _d(14, 11, 11, 1), _d(36, 11, 31, 24))
        # Japanese U+3000 can have a native height of zero. Its degenerate
        # quad uses the original advance but contains no pixels to replace.
        # Keep the legacy aggregate and classify using the actual draw size;
        # do not infer visibility from Unicode or change native drawing.
        for register in (5, 6):
            c.emit(_rl(11, register, 0, 16, 31), _d(11, 0, 11, 0))
            c.conditional(0x41820000, "fallback_zero_area")
        c.emit(_d(32, 11, 31, 48), _d(14, 11, 11, 1), _d(36, 11, 31, 48))
        c.jump("fallback_counted")
        c.label("fallback_zero_area")
        c.emit(_d(32, 11, 31, 44), _d(14, 11, 11, 1), _d(36, 11, 31, 44))
        c.label("fallback_counted")
        c.emit(_x(444, 4, 29, 29), _d(14, 3, 0, 0))
        c.call(select)
    c.label("done")
    _restore(c, True)
    return _return(c, native, instruction)


def cursor_is_xd(spec):
    return spec[7] >= 0x80200000


def _normalize_current(original: bytes, current: bytes, game_id: str) -> tuple[bytes, int]:
    """Restore only the verified XD zero tail omitted by canonical DOL readers."""
    if len(current) >= len(original):
        return current, 0
    spec = _REGIONS.get(game_id)
    variants = _EXACT_DOL_VARIANTS.get(game_id, ())
    missing = len(original) - len(current)
    if (spec is None or game_id not in ("GXXP01", "GXXJ01") or missing != 224
            or hashlib.sha256(original).hexdigest() not in variants
            or hashlib.sha256(original[:-224]).hexdigest() != spec[0]
            or original[-224:] != bytes(224) or current[:256] != original[:256]
            or any(u32(current, at) for at in (8, 0x50, 0x98))):
        raise FormatError("Current executable is truncated or has an unknown padding variant")
    # The caller's authorized code patches remain intact. All section geometry,
    # original identity and the exact omitted zero padding were checked above.
    parse_dol(current)
    return current + original[-224:], 224


def prepare_text_bridge(original_dol: bytes, current_dol: bytes, game_id: str,
                        glyphs: list, *, padding_by_identity=None) -> tuple[bytes, dict]:
    """Append pages and four qualified hooks; caller must still validate visuals.

    The original executable fingerprint gates all six regional layouts. Existing
    text2 reservations (including Spinda/music) are extended, never replaced.
    This routine has no filesystem, save, disc, or process access.
    """
    spec = _REGIONS.get(game_id)
    if spec is None or hashlib.sha256(original_dol).hexdigest() not in {spec[0], *_EXACT_DOL_VARIANTS.get(game_id, ())}:
        raise FormatError("Unverified original executable for GSmsg bridge")
    current_dol, padding_added = _normalize_current(original_dol, current_dol, game_id)
    if _MARKER in current_dol:
        raise FormatError("Invalid or already installed GSmsg bridge")
    _, make, size, pre, post, _, load, select, get = spec
    if any(u32(original_dol, at) for at in (8, 0x50, 0x98)):
        raise FormatError("Unexpected original text2 section")
    for address, length in ((make, size), (get, 0xC8),
                            (load, 0x48C if game_id.startswith("GXX") else 0x284),
                            (select, 0x68 if game_id.startswith("GXX") else 0x1D8)):
        at = _offset(original_dol, address)
        if current_dol[at:at + length] != original_dol[at:at + length]:
            raise FormatError("GSmsg bridge conflicts with an existing native function patch")
    if game_id.startswith("GC6"):
        region = dol_layout(original_dol)
        base, setter, store = region.section_ram, region.set_arena_lo, region.arena_lo_store
    else:
        from .xd_battle_rules import ARENA
        base, setter, store = ARENA[game_id]
    section = (len(original_dol) + 31) & ~31
    previous = u32(current_dol, 0x98)
    arena = _offset(original_dol, setter)
    if previous:
        if ((u32(current_dol, 8), u32(current_dol, 0x50)) != (section, base)
                or previous % 32 or section + previous != len(current_dol)
                or current_dol[section:section + 32] != _arena_guard(base + previous, store)
                or u32(current_dol, arena) != branch(setter, base)):
            raise FormatError("Unexpected existing GSmsg arena reservation")
        code = bytearray(current_dol[section:])
    else:
        if (len(current_dol) != len(original_dol) or u32(current_dol, arena) != store
                or any(u32(current_dol, at) for at in (8, 0x50))):
            raise FormatError("Unexpected DOL arena before GSmsg reservation")
        code = bytearray(32)
    if u32(current_dol, arena + 4) != 0x4E800020:
        raise FormatError("Unexpected native arena setter continuation")
    glyphs, corpus = select_runtime_glyphs(glyphs, game_id)
    pages, plan = build_native_pages(glyphs, padding_by_identity=padding_by_identity)
    code.extend(_MARKER)
    state = base + len(code)
    code.extend(bytes(64))
    page_addresses, page_records = [], []
    for index, page in enumerate(pages):
        address = base + len(code)
        if address % 32:
            raise FormatError("Static GSmsg sample buffer is not GX-aligned")
        page_addresses.append(address)
        page_records.append({"index": index, "file_offset": section + len(code),
                             "address": address, "bytes": len(page),
                             "sha256": hashlib.sha256(page).hexdigest()})
        code.extend(page)
    records = sorted(plan["glyphs"], key=lambda g: (g["font_id"], g["code"], g["samples_sha256"]))
    padding_pointers = {}
    for index, row in enumerate(records):
        nibbles = bytes.fromhex(row.get("source_padding_nibbles_hex", ""))
        if nibbles:
            padding_pointers[index] = base + len(code)
            code.extend(nibbles)
    code.extend(bytes((-len(code)) % 32))
    table = base + len(code)
    for index, row in enumerate(records):
        key = row["font_id"] << 16 | row["code"]
        metrics = row["width"] << 24 | row["height"] << 16 | (row["y_offset"] & 255) << 8
        left, top, right, bottom = row["padding_ltrb"]
        code.extend(struct.pack(">IIIHH4BHHfI", key, metrics, page_addresses[row["page"]],
                                row["x"], row["y"], left, top, right, bottom,
                                row["draw_width"], row["draw_height"], float(left),
                                padding_pointers.get(index, 0)))
    hooks = []
    for kind, native in (("remember", get), ("lookup", make), ("select", pre), ("restore", post)):
        address = base + len(code)
        at = _offset(original_dol, native)
        displaced = u32(original_dol, at)
        if kind == "remember":
            payload = _remember_code(address, native, displaced, state)
        elif kind == "lookup":
            payload = _lookup(address, native, displaced, state, table, len(records))
        else:
            payload = _drawing(address, native, displaced, state, spec, after=kind == "restore")
        code.extend(payload)
        hooks.append({"kind": kind, "native": native, "entry": address,
                      "file_offset": at, "bytes": len(payload), "displaced": displaced})
    end = base + len(code)
    if end >= 0x81700000 or len(code) - previous > 2 * 1024 * 1024:
        raise FormatError("GSmsg pages exceed their bounded MEM1 reservation")
    code[:32] = _arena_guard(end, store)
    output = bytearray(current_dol[:section])
    output.extend(bytes(section - len(output)))
    output.extend(code)
    for at, value in ((8, section), (0x50, base), (0x98, len(code)),
                      (arena, branch(setter, base))):
        struct.pack_into(">I", output, at, value)
    for hook in hooks:
        struct.pack_into(">I", output, hook["file_offset"], branch(hook["native"], hook["entry"]))
    parse_dol(bytes(output))
    return bytes(output), plan | {"bridge_contract": BRIDGE_CONTRACT, "game_id": game_id,
        "runtime_installed": True, "runtime_validated": False, "state_address": state,
        "counter_layout": {**COUNTER_LAYOUT, "offsets": dict(COUNTER_LAYOUT["offsets"])},
        "page_records": page_records, "table_address": table, "hooks": hooks,
        "section_address": base, "section_file_offset": section, "section_bytes": len(code),
        "native_memory_added": len(code) - previous, "reserved_end": end,
        "verified_current_padding_added": padding_added,
        "corpus_policy": corpus,
        "ownership": "DOL static lifetime; borrowed texture binding; never GSres/pool-owned",
        "fallback": "unknown code or different bitmap uses the untouched native dynamic atlas",
        "page_initialization": "lazy in-place GStextureLoad; no allocation or destructor",
        "restore_after_every_glyph": True}


def native_text_pages(dol: bytes, plan: dict) -> list[bytes]:
    """Extract immutable samples; initialized runtime header bytes are not accepted."""
    if plan.get("bridge_contract") != BRIDGE_CONTRACT:
        raise FormatError("Unknown GSmsg page contract")
    pages = []
    for row in plan["page_records"]:
        at, size = row["file_offset"], row["bytes"]
        if at < 0 or at + size > len(dol) or row["address"] % 32:
            raise FormatError("GSmsg page leaves its DOL reservation")
        page = bytes(dol[at:at + size])
        if hashlib.sha256(page).hexdigest() != row["sha256"]:
            raise FormatError("GSmsg page differs from its source recipe")
        pages.append(page)
    return pages
