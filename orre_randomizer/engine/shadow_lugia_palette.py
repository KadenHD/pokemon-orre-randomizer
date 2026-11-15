"""A white-body, dark-belly shiny palette for XD's original Shadow Lugia.

The native mesh has separate body and belly materials. Swap their authored
lighting colors and shade the belly texture, retaining the original eyes,
alpha, skeleton and animations. This is specific to the verified model.
"""
from __future__ import annotations

import struct

from .actor_palette import _walk_materials, _cmpr_endpoints
from .analyze_game import FormatError, check_range, cstring, u32

VERSION = "shadow-lugia-white-body-v2"
PORTRAIT_VERSION = "shadow-lugia-white-head-neck-dark-eye-mask-v3"
_DARK = bytes.fromhex("191933ff666680ff595973ff")
_PALE = bytes.fromhex("b3b3b3ffffffffffffffffff")


def _shade_belly_texture(data, relocations, color):
    refs = [slot for slot in relocations if slot >= 12 and u32(data, slot) == color
            and slot-4 in relocations]
    if len(refs) != 1:
        raise FormatError("unexpected Shadow Lugia belly material link")
    texture = u32(data, refs[0]-4)
    check_range(data, texture, 0x50, "Shadow Lugia belly texture")
    if texture+0x4C not in relocations:
        raise FormatError("missing Shadow Lugia belly image")
    image = u32(data, texture+0x4C)
    check_range(data, image, 24, "Shadow Lugia belly image")
    start, width, height, fmt, mipmap = struct.unpack_from(">IHHII", data, image)
    if (width, height, fmt, mipmap) != (32, 32, 14, 0) or image not in relocations:
        raise FormatError("unexpected Shadow Lugia belly texture format")
    check_range(data, start, 512, "Shadow Lugia belly CMPR samples")

    def shade(value):
        # Retain the authored light/shadow gradient, with a charcoal blue tint.
        r = round((value >> 11) * 0.18)
        g = round(((value >> 5) & 63) * 0.18)
        b = round((value & 31) * 0.20)
        return r << 11 | g << 5 | b

    for at in range(start, start+512, 8):
        a, b, indices = struct.unpack_from(">HH4s", data, at)
        c, d = shade(a), shade(b)
        c, d, indices = _cmpr_endpoints(a, b, indices, c, d)
        struct.pack_into(">HH4s", data, at, c, d, indices)


def make_shadow_lugia_portrait(pixels: bytes) -> bytes:
    """Color the source portrait; final face builders apply the black matte.

    This intermediate retains the original backdrop/alpha as provenance.
    """
    if not pixels or len(pixels) % 4:
        raise ValueError("expected RGBA portrait pixels")
    result = bytearray(pixels)
    for at in range(0, len(pixels), 4):
        r, g, b, alpha = pixels[at:at+4]
        # The head's blue-gray midtones have near-equal red/green channels.
        # The native backdrop is magenta or deep blue: never brighten it,
        # black outlines, neutral eye whites, red irises or transparent samples.
        if alpha and abs(r-g) <= 12 and b >= r + 12 and b >= g + 12 and 80 < b < 220:
            shade = round(255 * (max(r, g, b) / 255) ** 0.38)
            result[at:at+3] = bytes((shade, shade, shade))
    if len(pixels) == 42*42*4:
        # The deep navy neck and thin lower jaw are also body material. They
        # need their own spatial mask: brightening every dark blue pixel would
        # wash out the baked backdrop and black mouth contours. Preserve the
        # violet gaps between the neck and jaw in the original crop.
        neck = {
            17: ((37, 41),), 18: ((35, 41),), 19: ((32, 41),),
            20: ((30, 41),), 21: ((29, 41),), 22: ((28, 41),),
            23: ((30, 41),), 24: ((28, 41),), 25: ((27, 41),),
            26: ((26, 41),), 27: ((25, 41),), 28: ((25, 41),),
            29: ((24, 41),), 30: ((24, 40),), 31: ((23, 26), (30, 40)),
            32: ((23, 26), (33, 39)), 33: ((22, 25), (37, 39)),
            34: ((22, 24),), 35: ((21, 23),), 36: ((20, 22),),
            37: ((19, 21),), 38: ((18, 20),), 39: ((14, 17),),
        }
        for y, runs in neck.items():
            for left, right in runs:
                for x in range(left, right+1):
                    at = (y*42+x)*4
                    r, g, b, alpha = pixels[at:at+4]
                    if alpha and abs(r-g) <= 12 and b >= max(r, g)+4 and b >= 24:
                        shade = max(b, round(175+60*(b/255)**0.38))
                        result[at:at+3] = bytes((shade, shade, shade))
        # Native pale eye-mask material becomes dark in the shiny, while the
        # forehead's body material becomes white. These source-pixel runs follow
        # that triangle; shared white teeth/highlights must stay unchanged.
        spans = ((31, 38), (28, 39), (25, 39), (23, 40), (22, 40),
                 (21, 41), (20, 41), (19, 41), (18, 41), (16, 41),
                 (15, 36), (14, 34), (13, 31))
        for y, (left, right) in enumerate(spans, start=7):
            for x in range(left, right+1):
                at = (y*42+x)*4
                r, g, b, alpha = pixels[at:at+4]
                if alpha and abs(r-g) <= 12 and b >= max(r, g) and b >= 80:
                    shade = round(max(r, g, b)*0.14)
                    result[at:at+3] = bytes((shade, shade, shade+4))
    return bytes(result)


def make_shadow_lugia_shiny(pkx: bytes, *, xd: bool) -> bytes:
    """Return a length-preserving color-only variant; never change identity."""
    start = 0xE60 if xd else 0x40
    check_range(pkx, start, 0x20, "Shadow Lugia DAT header")
    dat = pkx[start:]
    if u32(pkx, 0) != u32(dat, 0):
        raise FormatError("unexpected Shadow Lugia PKX model length")
    return pkx[:start] + make_shadow_lugia_shiny_dat(dat)


def make_shadow_lugia_shiny_dat(dat: bytes) -> bytes:
    """Recolor the native battle or authored field DAT without changing motion."""
    check_range(dat, 0, 0x20, "Shadow Lugia DAT header")
    length, size, count, exports, imports = struct.unpack_from(">5I", dat)
    reloc_start = 0x20 + size
    exports_start = reloc_start + count * 4
    names_start = exports_start + exports * 8
    if (imports or not 0 < exports <= 64
            or not names_start < length <= len(dat)):
        raise FormatError("unexpected Shadow Lugia DAT layout")
    check_range(dat, reloc_start, count * 4, "Shadow Lugia relocation table")
    public = struct.iter_unpack(">II", dat[exports_start:names_start])
    scenes = [pointer for pointer, name in public
              if names_start + name < length and cstring(dat[:length], names_start + name) == "scene_data"]
    if len(scenes) != 1:
        raise FormatError("expected one Shadow Lugia model scene")
    data = bytearray(dat[0x20:reloc_start])
    relocations = set(struct.unpack_from(f">{count}I", dat, reloc_start))
    check_range(data, scenes[0], 4, "Shadow Lugia scene pointer")
    model_list = u32(data, scenes[0])
    check_range(data, model_list, 4, "Shadow Lugia model list")
    model = u32(data, model_list)
    check_range(data, model, 16, "Shadow Lugia model set")
    _, _, colors = _walk_materials(data, relocations, model, include_textured_colors=True)
    dark = [at for at in colors if data[at:at+12] == _DARK]
    pale = [at for at in colors if data[at:at+12] == _PALE]
    if len(dark) != 1 or len(pale) != 1:
        raise FormatError("unexpected original Shadow Lugia body/belly materials")
    # Each record is ambient, diffuse and specular RGBA. Swapping the native
    # triplets preserves material lighting and every alpha byte; the red-eye
    # texture and its separate material are deliberately untouched.
    data[dark[0]:dark[0]+12] = _PALE
    data[pale[0]:pale[0]+12] = _DARK
    # Native material animation can restore the belly's diffuse value. Tint
    # its own grayscale map as well; eye, mouth and body maps remain untouched.
    _shade_belly_texture(data, relocations, pale[0])
    result = bytearray(dat)
    result[0x20:reloc_start] = data
    assert len(result) == len(dat)
    return bytes(result)
