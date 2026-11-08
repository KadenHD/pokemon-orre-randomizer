"""Small PowerPC equivalent of the Spinda face baker for live wild encounters."""

import struct

from .actor_palette import remap_rgb565
from .analyze_game import FormatError
from .shiny_rules import _Code
from .spinda_art import _FACE_ORDER, _FACE_SIZE, _SPOT_ORDER, _SPOT_ORIGINS, _SPOT_SIZE, _linear_rgb565


def _registers(instruction, first, second, third):
    return instruction | first << 21 | second << 16 | third << 11


def _mask(first, second, shift, left, right):
    return _registers(0x54000000, first, second, shift) | left << 6 | right << 1


def spinda_face_writer(address: int, face: bytes, spot: bytes, recipe) -> bytes:
    """Write a tiled RGB565 face in place (r3 pixels, r4 PID, r5 shiny).

    Callers synchronize the data cache and invalidate the GX texture cache.
    Pixel data is derived from the user's ROM, including the shiny recipe.
    """
    base = _linear_rgb565(face, _FACE_SIZE, _FACE_ORDER)
    stamp = _linear_rgb565(spot, _SPOT_SIZE, _SPOT_ORDER)
    background = base[0]
    if any(color != background for color in base):
        raise FormatError("unexpected non-uniform retail Spinda face")
    route, gain = recipe
    code = _Code(address)
    code.emit(0x9421FFA0, 0xBDC10008,                  # preserve r14–r31
              0x3C000000 | background, 0x60000000 | background,
              0x39402000, 0x7D4903A6, 0x3963FFFC)  # fill 8192 packed pairs
    code.label("fill")
    code.emit(0x940B0004)                            # stwu r0, 4(r11)
    code.conditional(0x42000000, "fill")             # bdnz
    stamp_load = len(code.words)
    code.emit(0, 0, 0x38E60800, 0x39000004)           # r6 stamp, r7 centers, r8 four spots
    code.label("spot")
    code.emit(0x7089000F, _mask(4, 10, 28, 28, 31),
              0x3929FFF8, 0x394AFFF8, 0x1D290011, 0x1D4A0011, 0x39C00005,
              _registers(0x7C0003D6, 9, 9, 14), _registers(0x7C0003D6, 10, 10, 14),
              0x88070000, _registers(0x7C000214, 9, 9, 0),
              0x88070001, _registers(0x7C000214, 10, 10, 0), _mask(10, 10, 7, 0, 24),
              _registers(0x7C000214, 10, 10, 9), 0x7CCE3378, 0x39600020)  # r10 linear index, r14 stamp row
    code.label("row")
    code.emit(0x2C0A0000)
    code.conditional(0x41800000, "next_row")
    code.emit(0x2C0A4000)
    code.conditional(0x40800000, "next_row")
    code.emit(0x7D4F5378, 0x39800000)               # r15 linear pixel, r12 stamp column in bytes
    code.label("pixel")
    code.emit(0x2C0F4000)
    code.conditional(0x40800000, "next_row")
    # Map the linear position to its RGB565 4×4 tile and in-tile position.
    code.emit(_mask(15, 16, 0, 0, 22), _mask(15, 19, 2, 23, 27),
              _registers(0x7C000378, 16, 16, 19), _mask(15, 19, 27, 28, 29),
              _registers(0x7C000378, 16, 16, 19), _mask(15, 19, 0, 30, 31),
              _registers(0x7C000378, 16, 16, 19), _mask(16, 16, 1, 0, 30),
              _registers(0x7C00022E, 17, 3, 16), _registers(0x7C00022E, 18, 14, 12),
              0x7C128840)                         # unsigned stamp and destination comparison
    code.conditional(0x40810000, "next_pixel")
    code.emit(_registers(0x7C00032E, 18, 3, 16))
    code.label("next_pixel")
    code.emit(0x39EF0001, 0x398C0002, 0x2C0C0040)
    code.conditional(0x41800000, "pixel")
    code.label("next_row")
    code.emit(0x394A0080, 0x39CE0040, 0x356BFFFF)
    code.conditional(0x40820000, "row")
    code.emit(_mask(4, 4, 24, 8, 31), 0x38E70002, 0x3508FFFF)
    code.conditional(0x40820000, "spot")
    code.emit(0x2C050000)
    code.conditional(0x41820000, "done")
    code.emit(0x39404000, 0x7D4903A6, 0x7C6B1B78)  # r7 now points to palette
    code.label("recolor")
    code.emit(0xA22B0000, 0x7CF23B78)               # r17 source RGB565, r18 palette cursor
    code.label("lookup")
    code.emit(0xA2720000, 0x3A520004, 0x7C119840)
    code.conditional(0x40820000, "lookup")
    code.emit(0xA232FFFE, 0xB22B0000, 0x396B0002)
    code.conditional(0x42000000, "recolor")
    code.label("done")
    code.emit(0xB9C10008, 0x38210060, 0x4E800020)
    stamp_address = address + ((len(code.words) * 4 + 31) & ~31)
    code.words[stamp_load:stamp_load + 2] = [0x3CC00000 | (stamp_address >> 16),
                                            0x60C60000 | (stamp_address & 0xFFFF)]
    colors = [background, *sorted(color for color in set(stamp) if color > background)]
    return (code.finish() + struct.pack(f">{len(stamp)}H", *stamp)
            + bytes(component for origin in _SPOT_ORIGINS for component in origin)
            + b"".join(struct.pack(">HH", color, remap_rgb565(color, route, gain)) for color in colors))
