"""Render the retail GameCube Spinda face texture for a personality value."""

import struct

from .analyze_game import FormatError, check_range, u32


_FACE_SIZE = 128
_SPOT_SIZE = 32
_SPOT_ORIGINS = ((6, 7), (91, 6), (30, 65), (68, 65))


def _gx_order(size):
    return tuple(
        (y + dy) * size + x + dx
        for y in range(0, size, 4) for x in range(0, size, 4)
        for dy in range(4) for dx in range(4)
    )


_FACE_ORDER = _gx_order(_FACE_SIZE)
_SPOT_ORDER = _gx_order(_SPOT_SIZE)


def _linear_rgb565(raw, size, order):
    if (len(raw) != 128 + size * size * 2 or raw[:12] != struct.pack(
            ">HHBBHI", size, size, 16, 1, 0, 0x44) or u32(raw, 0x28) != 128):
        raise FormatError("unexpected retail Spinda texture")
    linear = [0] * (size * size)
    for position, (color,) in zip(order, struct.iter_unpack(">H", raw[128:]), strict=True):
        linear[position] = color
    return linear


def spinda_face_texture(face: bytes, spot: bytes, pid: int) -> bytes:
    """Return the tiled 128×128 RGB565 image used by the native 3D renderer."""
    if type(pid) is not int or not 0 <= pid <= 0xFFFFFFFF:
        raise ValueError("Spinda PID must be an unsigned 32-bit integer")
    destination = _linear_rgb565(face, _FACE_SIZE, _FACE_ORDER)
    stamp = _linear_rgb565(spot, _SPOT_SIZE, _SPOT_ORDER)
    for origin_x, origin_y in _SPOT_ORIGINS:
        x = origin_x + int(((pid & 15) - 8) * 3.4)
        y = origin_y + int((((pid >> 4) & 15) - 8) * 3.4)
        pid >>= 8
        for row in range(_SPOT_SIZE):
            start = (y + row) * _FACE_SIZE + x
            # Retail bounds-checks the linear address, skipping out-of-range
            # rows and allowing a spot to wrap across the edge of a row.
            if not 0 <= start < len(destination):
                continue
            for col in range(min(_SPOT_SIZE, len(destination) - start)):
                index = start + col
                destination[index] = max(destination[index], stamp[row * _SPOT_SIZE + col])
    return struct.pack(f">{len(destination)}H", *(destination[position] for position in _FACE_ORDER))


def replace_spinda_field_face(data: bytearray, relocations: set[int], model: int, texture: bytes) -> None:
    """Replace the face on the first mesh of Spinda's third root joint."""
    if len(texture) != _FACE_SIZE * _FACE_SIZE * 2:
        raise FormatError("invalid Spinda field face size")

    def pointer(slot):
        if slot not in relocations:
            raise FormatError("unexpected Spinda field model pointer")
        target = u32(data, slot)
        check_range(data, target, 4, "Spinda field model pointer")
        return target

    first_root = pointer(model)
    second_root = pointer(first_root + 8)
    head = pointer(second_root + 8)
    mesh = pointer(head + 16)
    material = pointer(mesh + 8)
    texture_object = pointer(material + 8)
    image = pointer(texture_object + 0x4C)
    check_range(data, image, 24, "Spinda field face descriptor")
    if struct.unpack_from(">HHIIff", data, image + 4) != (128, 128, 4, 0, 0.0, 0.0):
        raise FormatError("unexpected Spinda field face descriptor")
    start = pointer(image)
    check_range(data, start, len(texture), "Spinda field face texture")
    data[start:start + len(texture)] = texture
