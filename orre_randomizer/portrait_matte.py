"""Opaque black matting for Shadow Lugia's native and interface face tiles.

The original face includes a purple backdrop connected to the tile boundary.
The model's blue-gray head and red eye/mouth colors are outside that hue band.
The source portrait remains intact. Derived native faces and interface tiles
share this transformation so a transparent corner cannot reveal a violet plate.
"""
from collections import deque

SIZE = 42


def shadow_lugia_background_mask(pixels: bytes) -> frozenset[int]:
    """Find only transparent/violet backdrop pixels connected to the boundary."""
    if len(pixels) != SIZE*SIZE*4:
        raise ValueError('expected one 42×42 RGBA face')

    def backdrop(index):
        r, g, b, alpha = pixels[index*4:index*4+4]
        # The baked disk has a dark antialiased outline (49, 16, 57).
        # Its blue/red difference is only eight, unlike the bright violet
        # center; keep it in the background while excluding gray anatomy.
        return not alpha or (r >= g+15 and b >= r+6)

    edge = {y*SIZE+x for y in range(SIZE) for x in range(SIZE)
            if x in (0, SIZE-1) or y in (0, SIZE-1)}
    selected = {index for index in edge if backdrop(index)}
    pending = deque(selected)
    while pending:
        index = pending.popleft()
        x, y = index % SIZE, index // SIZE
        # Eight neighbors retain the diagonal connection of native 1px
        # antialiased backdrop edges. Blue-gray anatomy is never traversable.
        for nx, ny in ((x+dx, y+dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy):
            if 0 <= nx < SIZE and 0 <= ny < SIZE:
                neighbor = ny*SIZE+nx
                if neighbor not in selected and backdrop(neighbor):
                    selected.add(neighbor)
                    pending.append(neighbor)
    return frozenset(selected)


def matte_shadow_lugia_portrait(pixels: bytes, *, reference: bytes) -> bytes:
    """Matte the selected backdrop to black; retain foreground over black."""
    if len(pixels) != SIZE*SIZE*4:
        raise ValueError('expected one 42×42 RGBA face')
    mask = shadow_lugia_background_mask(reference)
    output = bytearray(len(pixels))
    for index in range(SIZE*SIZE):
        at = index*4
        r, g, b, alpha = pixels[at:at+4]
        if index not in mask:
            output[at:at+3] = bytes((channel*alpha+127)//255 for channel in (r, g, b))
        output[at+3] = 255
    return bytes(output)


def make_shadow_lugia_ui_portrait(pixels: bytes, *, reference: bytes) -> bytes:
    """Compatibility entry point for the interface's existing matted assets."""
    return matte_shadow_lugia_portrait(pixels, reference=reference)
