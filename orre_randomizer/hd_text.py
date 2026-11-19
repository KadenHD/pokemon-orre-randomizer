"""Immutable native glyph pages for a bounded, dual-resolution GSmsg bridge.

This module only transforms caller-supplied font bytes. It does not install a
runtime hook or claim an HD donor. Visible native samples are copied exactly;
odd-width unused nibbles are retained separately when transparent margins need
them cleared. Advances and source offsets stay in the glyph records. The runtime
bridge and genuine vector renderer must qualify separately.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct

from .engine.analyze_game import FormatError, check_range, parse_dol

PAGE_SIZE = 512
PAGE_BYTES = PAGE_SIZE * PAGE_SIZE // 2
FIRST_RESOURCE = 0x7B001200
CONTRACT = "orre-gsmsg-static-glyph-pages-v1"
CORPUS_POLICY = "regional-native-message-alphabet-v2"
WESTERN_UI_PUNCTUATION = frozenset((0x3010, 0x3011))


@dataclass(frozen=True)
class Glyph:
    font_id: int
    code: int
    width: int
    height: int
    y_offset: int
    samples: bytes
    source: str
    source_offset: int

    @property
    def identity(self):
        return (self.font_id, self.code, self.width, self.height, self.y_offset, self.samples)


def select_runtime_glyphs(glyphs: list[Glyph], game_id: str) -> tuple[list[Glyph], dict]:
    """Bound Western residency; imported out-of-alphabet names stay native.

    All original banks remain in the game. This selection only limits the
    additional immutable pages. Japanese discs retain their declared banks;
    their memory/runtime qualification is separate from Western witnesses.
    """
    from .hd_text_symbols import SPECIAL_CODES
    if game_id not in ("GC6P01", "GC6E01", "GC6J01", "GXXP01", "GXXE01", "GXXJ01"):
        raise FormatError("Unknown regional native-message alphabet")
    japanese = game_id.endswith("J01")
    selected = list(glyphs) if japanese else [g for g in glyphs if
        g.code < 0x300 or g.code in SPECIAL_CODES or g.code in WESTERN_UI_PUNCTUATION
        or 0x2000 <= g.code <= 0x27FF]
    original_codes = {g.code for g in glyphs}
    selected_codes = {g.code for g in selected}
    return selected, {"version": CORPUS_POLICY,
        "scope": "Japanese declared font banks" if japanese else "Western Latin and native GSchar UI symbols",
        "languages": ["ja"] if japanese else ["en", "fr", "de", "es", "it"] if game_id.endswith("P01") else ["en"],
        "input_records": len(glyphs), "resident_records": len(selected),
        "resident_codes": sorted(selected_codes), "fallback_codes": sorted(original_codes - selected_codes),
        "outside_corpus": "untouched native dynamic glyph renderer; includes imported Japanese names on Western discs",
        "all_original_font_banks_preserved": True,
        "runtime_coverage_validated": False}


def parse_font_bank(data: bytes, offset: int = 0, *, limit: int | None = None,
                    source: str = "caller font") -> tuple[dict, list[Glyph]]:
    """Parse one original eight-byte font header and its bank, without mutation."""
    if limit is None:
        limit = len(data)
    if not 0 <= offset <= limit <= len(data):
        raise FormatError("Invalid font bank bounds")
    check_range(data[:limit], offset, 24, "font header and bank")
    font_id, maximum_width, maximum_height, following = struct.unpack_from(">HBBI", data, offset)
    count, flags, samples_at, next_bank, previous_bank = struct.unpack_from(">HHIII", data, offset + 8)
    if (font_id > 8 or not 1 <= maximum_width <= 40 or not 1 <= maximum_height <= 40
            or not 1 <= count <= 12000 or flags not in (0, 1) or next_bank or previous_bank
            or samples_at != 16 + count * 8):
        raise FormatError("Unsupported original GSmsg font bank")
    check_range(data[:limit], offset + 24, count * 8, "font glyph directory")
    pixels_base = offset + 8 + samples_at
    glyphs = []
    last_code = -1
    extent = pixels_base
    for index in range(count):
        code, width, height, descriptor = struct.unpack_from(">HBBI", data, offset + 24 + index * 8)
        # Several Japanese glyphs exceed the nominal maximum width by one.
        if code <= last_code or width > 40 or not 0 <= height <= 40:
            raise FormatError("Invalid or unsorted native font glyph")
        last_code = code
        position = pixels_base + (descriptor & 0xFFFFFF)
        size = ((width + 1) // 2) * height
        check_range(data[:limit], position, size, "font glyph samples")
        bias = descriptor >> 24
        if bias >= 128:
            bias -= 256
        glyphs.append(Glyph(font_id, code, width, height, bias,
                            bytes(data[position:position + size]), source, position))
        extent = max(extent, position + size)
    if following and (following < extent - offset or offset + following > limit):
        raise FormatError("Font successor overlaps its glyph samples")
    return {"source": source, "offset": offset, "font_id": font_id,
            "maximum_width": maximum_width, "maximum_height": maximum_height,
            "following": following, "count": count, "flags": flags, "extent": extent - offset,
            "sha256": hashlib.sha256(data[offset:extent]).hexdigest()}, glyphs


def font_banks_from_dol(dol: bytes, *, source: str = "caller DOL") -> tuple[list[dict], list[Glyph]]:
    """Locate structurally verified original banks in DOL data sections only."""
    banks, glyphs = [], []
    for section in parse_dol(dol)["sections"]:
        if not section["name"].startswith("data"):
            continue
        start, end = section["offset"], section["offset"] + section["size"]
        for offset in range(start, end - 24, 4):
            key, width, height, _, count, flags, size, first, previous = struct.unpack_from(">HBBIHHIII", dol, offset)
            if (key > 8 or not 10 <= width <= 32 or not 10 <= height <= 32
                    or not 1 <= count <= 12000 or flags not in (0, 1) or first or previous
                    or size != 16 + count * 8):
                continue
            try:
                bank, found = parse_font_bank(dol, offset, limit=end, source=source)
            except FormatError:
                continue
            bank["ram_address"] = section["ram_address"] + offset - start
            # Retail also registers small supplement banks (currency, stars,
            # punctuation). Structure is fully checked; discovery alone does
            # not claim that a bank is drawn. Runtime matching remains exact.
            banks.append(bank)
            glyphs.extend(found)
    return banks, glyphs


def font_banks_from_file(data: bytes, *, source: str = "caller font resource") -> tuple[list[dict], list[Glyph]]:
    """Follow the same eight-byte successor chain as original GSmsgFontOpen."""
    banks, glyphs = [], []
    offset = 0
    for _ in range(64):
        check_range(data, offset, 8, "font chain header")
        if struct.unpack_from(">H", data, offset)[0] == 0xFFFF:
            return banks, glyphs
        bank, found = parse_font_bank(data, offset, source=source)
        banks.append(bank)
        glyphs.extend(found)
        if not bank["following"]:
            return banks, glyphs
        offset += bank["following"]
    raise FormatError("Original font chain exceeds the supported bound")


def _sample_offset(x: int, y: int) -> tuple[int, int]:
    return ((y // 8 * (PAGE_SIZE // 8) + x // 8) * 32 + (y % 8 * 8 + x % 8) // 2,
            4 if x % 2 == 0 else 0)


def _put(samples: bytearray, x: int, y: int, value: int):
    at, shift = _sample_offset(x, y)
    samples[at] = (samples[at] & ~(15 << shift)) | (value << shift)


def native_page_file(samples: bytes) -> bytes:
    """A standard GStexture I4 file; texture loader resolves the sample offset."""
    if len(samples) != PAGE_BYTES:
        raise FormatError("Invalid static text page size")
    header = bytearray(128)
    struct.pack_into(">HHBB", header, 0, PAGE_SIZE, PAGE_SIZE, 4, 1)
    struct.pack_into(">I", header, 8, 0x40)
    struct.pack_into(">I", header, 0x28, 128)
    return bytes(header) + samples


def build_native_pages(glyphs: list[Glyph], *, padding_by_identity=None) -> tuple[list[bytes], dict]:
    """Shelf-pack native glyphs once, with deterministic UVs and bounded pages."""
    # Retail msgSetChar returns early for0x20: advance=maxWidth/2, no glyph quad.
    # Some unused font-bank space entries contain nonempty placeholder samples.
    unique = {g.identity: g for g in glyphs if g.width and g.height and g.code != 0x20}
    if not unique:
        raise FormatError("No native glyphs to register")
    ordered = sorted(unique.values(), key=lambda g: (g.font_id, g.code, g.width, g.height,
                     g.y_offset, hashlib.sha256(g.samples).digest()))
    pages: list[bytearray] = []
    records = []
    page = -1
    x, y, row_height = 2, 8, 0
    for glyph in ordered:
        padding = (padding_by_identity or {}).get(glyph.identity, (0, 0, 0, 0))
        if (not isinstance(padding, (tuple, list)) or len(padding) != 4
                or any(type(value) is not int or not 0 <= value <= 16 for value in padding)):
            raise FormatError("Invalid transparent glyph margins")
        left, top, right, bottom = padding
        left = (left + 1) & ~1  # I4 source comparisons must remain byte-aligned.
        draw_width = left + glyph.width + right
        draw_height = top + glyph.height + bottom
        rounded_width = (glyph.width + 1) & ~1
        canvas_width = (draw_width + 1) & ~1
        if len(glyph.samples) != rounded_width // 2 * glyph.height:
            raise FormatError("Native glyph byte count differs from its metrics")
        if x + canvas_width + 2 > PAGE_SIZE:
            x, y, row_height = 2, y + row_height + 2, 0
        if page == -1 or y + draw_height + 1 > PAGE_SIZE:
            page += 1
            if page >= 128:
                raise FormatError("Static font pages exceed the reserved resource namespace")
            pages.append(bytearray(PAGE_BYTES))
            x, y, row_height = 2, 8, 0
            # Metadata lives in an unused guard row, outside every glyph UV.
            marker = b"ORRETEXT" + struct.pack(">I", page)
            for index, byte in enumerate(marker):
                _put(pages[page], index * 2, 0, byte >> 4)
                _put(pages[page], index * 2 + 1, 0, byte & 15)
        for row in range(glyph.height):
            for column in range(rounded_width):
                value = glyph.samples[row * (rounded_width // 2) + column // 2]
                value = (value >> (4 if column % 2 == 0 else 0)) & 15
                if any((left, top, right, bottom)) and column >= glyph.width:
                    value = 0
                _put(pages[page], x + left + column, y + top + row, value)
        records.append({"font_id": glyph.font_id, "code": glyph.code,
                        "width": glyph.width, "height": glyph.height, "y_offset": glyph.y_offset,
                        "samples_sha256": hashlib.sha256(glyph.samples).hexdigest(),
                        "source": glyph.source, "source_offset": glyph.source_offset,
                        "page": page, "resource": FIRST_RESOURCE + page * 0x10000,
                        "x": x + left, "y": y + top,
                        "draw_x": x, "draw_y": y, "draw_width": draw_width,
                        "draw_height": draw_height, "padding_ltrb": [left, top, right, bottom],
                        "source_padding_nibbles_hex": bytes(
                            glyph.samples[(row + 1) * (rounded_width // 2) - 1] & 15
                            for row in range(glyph.height)).hex()
                        if glyph.width % 2 and any((left, top, right, bottom)) else ""})
        row_height = max(row_height, draw_height)
        x += canvas_width + 2
    output = [native_page_file(bytes(page)) for page in pages]
    return output, {"contract": CONTRACT, "page_size": PAGE_SIZE,
            "resource_start": FIRST_RESOURCE, "pages": len(output), "glyphs": records,
            "non_drawn_codes": sorted({0x20} | {g.code for g in glyphs if not g.width or not g.height}),
            "space_rule": "retail msgSetChar early advance; no quad",
            "native_samples_unchanged": not any(any(bytes.fromhex(g["source_padding_nibbles_hex"])) for g in records),
            "native_visible_samples_unchanged": True,
            "native_samples_losslessly_recoverable": True,
            "quad_geometry": "transparent-margins-native-advance-v1",
            "runtime_installed": False,
            "hd_ready": False, "hd_reason": "A qualified vector donor and runtime bridge are required",
            "page_sha256": [hashlib.sha256(page).hexdigest() for page in output]}
