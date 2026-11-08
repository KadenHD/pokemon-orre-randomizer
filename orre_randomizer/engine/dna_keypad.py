"""Replace the DNA door's baked portraits without changing its nine answers."""

from collections import Counter
from collections.abc import Mapping
import struct

from ..artwork import ArtworkError, _decode_pixels, _rgb565, _texture
from .analyze_game import FormatError, parse_fsys, sha256
from .rebuild_iso import decoded_member, repack_fsys
from .spinda import SPINDA
from .unown_form import unown_suffix


DNA_KEYPAD_SPECIES = (185, 200, 244, 287, 156, 243, 153, 245, 159)
# In screen order. The nine tile textures are scattered across the atlas.
_TILE_ORIGINS = ((896, 0), (896, 128), (736, 128), (736, 0), (896, 512),
                 (736, 384), (896, 256), (736, 256), (896, 384))
_DAT_SHA256 = "8d02a7d9f286ba069a9d0f2d35e91a5f07bb7460226ae3d0beac87ea1ed8b1bf"
_ATLAS_OFFSET = 0x7820
_ATLAS_WIDTH = 1024
_ATLAS_DESCRIPTOR = 0x45B0
_ATLAS_SIGNATURE = (0x7800, 0x04000400, 14)
_KEYPAD_DAT_SIZE = 0x886AF
_SPINDA_KEYPAD_MARKER = 0x53504B44
_TILE_SIZE = 128
_BLOCK_SIZE = 8
_BLOCK_BYTES = 32
_TILE_ROW_BYTES = _TILE_SIZE // _BLOCK_SIZE * _BLOCK_BYTES
_SPINDA_ART_RECT = (24, 16, 80)
_DIGITS = (
    (4, 12, 4, 4, 4, 4, 14),
    (14, 17, 1, 2, 4, 8, 31),
    (30, 1, 1, 14, 1, 1, 30),
    (2, 6, 10, 18, 31, 2, 2),
    (31, 16, 16, 30, 1, 17, 14),
    (6, 8, 16, 30, 17, 17, 14),
    (31, 1, 2, 4, 8, 8, 8),
    (14, 17, 17, 14, 17, 17, 14),
    (14, 17, 17, 15, 1, 2, 12),
)


def _tile_rows(x: int, y: int):
    for row in range(y, y + _TILE_SIZE, _BLOCK_SIZE):
        start = _atlas_block_offset(x, row)
        yield start, start + _TILE_ROW_BYTES


def _atlas_block_offset(x: int, y: int) -> int:
    return _ATLAS_OFFSET + (y // _BLOCK_SIZE * _ATLAS_WIDTH + x) // _BLOCK_SIZE * _BLOCK_BYTES


def _rgb_word(color) -> int:
    red, green, blue = color
    return (red >> 3) << 11 | (green >> 2) << 5 | (blue >> 3)


def _encode_cmpr(rgb: bytes) -> bytes:
    """Encode the opaque 128×128 tile as GameCube 8×8 CMPR macroblocks."""
    result = bytearray()
    image = list(struct.iter_unpack("BBB", rgb))
    for y in range(0, _TILE_SIZE, 8):
        for x in range(0, _TILE_SIZE, 8):
            for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4)):
                pixels = [
                    image[row * _TILE_SIZE + col]
                    for row in range(y + dy, y + dy + 4)
                    for col in range(x + dx, x + dx + 4)
                ]
                # Choose endpoint colors along the dominant RGB axis.
                lows = [min(pixels, key=lambda pixel: pixel[channel]) for channel in range(3)]
                highs = [max(pixels, key=lambda pixel: pixel[channel]) for channel in range(3)]
                axis = max(range(3), key=lambda channel: highs[channel][channel] - lows[channel][channel])
                first, second = sorted((_rgb_word(lows[axis]), _rgb_word(highs[axis])), reverse=True)
                result.extend(struct.pack(">HH", first, second))
                if first == second:
                    result.extend(bytes(4))
                    continue
                a, b = _rgb565(first)[:3], _rgb565(second)[:3]
                colors = (a, b, tuple((5 * v + 3 * w) // 8 for v, w in zip(a, b)),
                          tuple((3 * v + 5 * w) // 8 for v, w in zip(a, b)))
                indices = 0
                for pixel in pixels:
                    nearest = min(range(4), key=lambda index: sum(
                        (v - w) ** 2 for v, w in zip(pixel, colors[index])))
                    indices = indices << 2 | nearest
                result.extend(struct.pack(">I", indices))
    return bytes(result)


def _tile_art(template: bytes, portrait: bytes, width: int, shiny: bool, number: int,
              *, rect=(22, 22, 84)) -> bytes:
    # The narrow Quilava art leaves the original bevel clear.
    # Keep that bevel and place the 42 px native portrait on the tile.
    background = (64 * _TILE_SIZE + 8) * 4
    blank = template[background:background + 3]
    tile = bytearray(blank * (_TILE_SIZE * _TILE_SIZE))
    for y in range(_TILE_SIZE):
        for x in range(_TILE_SIZE):
            if min(x, y, _TILE_SIZE - 1 - x, _TILE_SIZE - 1 - y) < 4:
                index = y * _TILE_SIZE + x
                tile[3 * index:3 * index + 3] = template[4 * index:4 * index + 3]
    left, top, size = rect
    for y in range(size):
        row = y * 42 // size + (42 if shiny else 0)
        for x in range(size):
            old = (row * width + x * 42 // size) * 4
            new = ((y + top) * _TILE_SIZE + x + left) * 3
            tile[new:new + 3] = portrait[old:old + 3]
    if number:
        for y in range(27):
            for x in range(21):
                lit = 3 <= x < 18 and 3 <= y < 24 and (
                    _DIGITS[number - 1][(y - 3) // 3] & (16 >> ((x - 3) // 3)))
                pos = ((96 + y) * _TILE_SIZE + 102 + x) * 3
                tile[pos:pos + 3] = b"\xff\xff\xff" if lit else b"\x12\x21\x19"
    return _encode_cmpr(tile)


def patch_dna_keypad(source: bytes, faces_archive: bytes,
                     mapping: Mapping[int, tuple[int, bool]], *, unown_form_index: int = 0,
                     spinda_samples=()) -> bytes:
    """Update the tiles' images while retaining their native comparison keys."""
    if set(mapping) != set(DNA_KEYPAD_SPECIES):
        raise FormatError("unexpected DNA keypad species mapping")
    counts = Counter(species for species, _ in mapping.values())
    changes = [
        (position, species, shiny, counts[species] > 1)
        for position, original in enumerate(DNA_KEYPAD_SPECIES)
        for species, shiny in (mapping[original],)
        if species != original or shiny or counts[species] > 1
    ]
    if not changes:
        return source

    members = parse_fsys(source)["members"]
    model = next((member for member in members if member["identifier_raw"] == "0x107e0200"), None)
    if model is None:
        raise FormatError("DNA keypad model not found")
    original_dat = decoded_member(source, model)
    if sha256(original_dat) != _DAT_SHA256:
        raise FormatError("unexpected original DNA keypad model")
    updated = bytearray(original_dat)
    if spinda_samples:
        if (len(original_dat) != _KEYPAD_DAT_SIZE or any(original_dat[0x18:0x20])
                or struct.unpack_from(">III", original_dat, _ATLAS_DESCRIPTOR) != _ATLAS_SIGNATURE):
            raise FormatError("unexpected DNA keypad atlas")
        struct.pack_into(">I", updated, 0x18, _SPINDA_KEYPAD_MARKER)
    template = _decode_pixels(_TILE_SIZE, _TILE_SIZE, 4, b"".join(
        original_dat[start:end] for start, end in _tile_rows(896, 512)))
    faces = {member["name"]: member for member in parse_fsys(faces_archive)["members"]}
    for position, species, shiny, duplicate in changes:
        name = f"face201{unown_suffix(unown_form_index)}" if species == 201 else f"face{species:03d}"
        try:
            raw = decoded_member(faces_archive, faces[name])
            width, height = struct.unpack_from(">HH", raw)
            if width not in (42, 84) or height != 84:
                raise FormatError("unexpected DNA keypad portrait dimensions")
            portrait = _texture(raw, (width, height))
        except (ArtworkError, KeyError, struct.error) as error:
            raise FormatError("DNA keypad portrait not available") from error
        rect = _SPINDA_ART_RECT if species == SPINDA and DNA_KEYPAD_SPECIES[position] in spinda_samples else (22, 22, 84)
        image = _tile_art(template, portrait, width, shiny, position + 1 if duplicate else 0, rect=rect)
        for row, (start, end) in enumerate(_tile_rows(*_TILE_ORIGINS[position])):
            offset = row * _TILE_ROW_BYTES
            updated[start:end] = image[offset:offset + _TILE_ROW_BYTES]
    return repack_fsys(source, {model["index"]: bytes(updated)})[0]
