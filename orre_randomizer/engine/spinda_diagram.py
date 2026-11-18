"""Finite, independent layers for the native PID-specific DNA diagram.

The game compares packed RGB565 words, not separate RGB components. Its DNA
swatch subsequently reduces that result to background versus any other colour.
That binary diagram is the union of four masks, each dependent on one PID byte.
No save, personality value or species identity is changed by this module.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import struct

from .actor_palette import remap_rgb565
from .analyze_game import FormatError
from .spinda_art import _FACE_ORDER, _SPOT_ORDER, _SPOT_ORIGINS, _linear_rgb565


SIZE = 32
PAD = 4
TEXTURE_SIZE = SIZE + PAD * 2
TEXTURE_BYTES = TEXTURE_SIZE * TEXTURE_SIZE // 2
FACE_SHA256 = "4da656b80e83bafa0fd2705c95dc9cb65e7b09996e6a15a050c921437130a408"
SPOT_SHA256 = "9483c3ad95cd3a0e27dcb2b6adb6bb637f1284d980b28947e3f2d1d163f8a6e2"
RECIPE = ((1, 0, 2, 3), (171, 158, 137, 127))


def _arguments(index, value):
    if type(index) is not int or not 0 <= index < 4 or type(value) is not int or not 0 <= value < 256:
        raise ValueError("Spinda layer requires a spot index and one PID byte")


def spot_origin(index: int, value: int) -> tuple[int, int]:
    _arguments(index, value)
    ox, oy = _SPOT_ORIGINS[index]
    # Integer division must truncate toward zero, matching native fctiwz.
    def shift(nibble):
        delta = (nibble - 8) * 17
        return abs(delta) // 5 * (-1 if delta < 0 else 1)
    return ox + shift(value & 15), oy + shift(value >> 4)


def spot_rows(index: int, value: int):
    """Yield source row/column and native linear destination spans.

    This deliberately keeps the native row-start check and horizontal carry.
    Clipping each stamp to an ordinary 128-square would lose these semantics.
    """
    x, y = spot_origin(index, value)
    for row in range(32):
        start = (y + row) * 128 + x
        if 0 <= start < 16384:
            yield row, start, min(32, 16384 - start)


def diagram_layer(spot: bytes, background: int, index: int, value: int) -> bytes:
    """Return 32² binary samples for one byte, in linear order."""
    _arguments(index, value)
    if type(background) is not int or not 0 <= background <= 65535:
        raise ValueError("Invalid native RGB565 background")
    source = _linear_rgb565(spot, 32, _SPOT_ORDER)
    result = bytearray(1024)
    for row, start, count in spot_rows(index, value):
        for column in range(count):
            target = start + column
            if target % 128 % 4 == 0 and target // 128 % 4 == 0:
                if source[row * 32 + column] > background:
                    result[target // 128 // 4 * 32 + target % 128 // 4] = 1
    return bytes(result)


def cmpr_layer(mask: bytes, color: int, *, identity: int = 0) -> bytes:
    """Encode a binary native layer with a transparent four-pixel clamp rim."""
    if len(mask) != 1024 or any(value not in (0, 1) for value in mask) or not 0 < color <= 65535:
        raise FormatError("Invalid Spinda diagram layer")
    if type(identity) is not int or not 0 <= identity <= 0x7FFF:
        raise FormatError("Invalid invisible Spinda diagram layer identity")
    result = bytearray()
    for y in range(0, TEXTURE_SIZE, 8):
        for x in range(0, TEXTURE_SIZE, 8):
            for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4)):
                selectors = 0
                for py in range(y + dy, y + dy + 4):
                    for px in range(x + dx, x + dx + 4):
                        lit = PAD <= px < PAD + SIZE and PAD <= py < PAD + SIZE and mask[(py - PAD) * SIZE + px - PAD]
                        selectors = selectors << 2 | (1 if lit else 3)
                result.extend(struct.pack(">HHI", 0, color, selectors))
    # The first4×4 quadrant is entirely outside the visible32-square. Distinct
    # byte identities retain distinct Dolphin keys even for identical masks.
    # Complementary RGB565 endpoints keep their expanded average exactly
    # (127,127,127,0), independently of ID. Alpha0 alone is insufficient: linear
    # filtering can mix hidden RGB into the adjacent opaque diagram corner.
    if identity:
        struct.pack_into(">HH", result, 0, identity, 0xFFFF - identity)
    assert len(result) == TEXTURE_BYTES
    return bytes(result)


def native_sources(face: bytes, spot: bytes, recipe) -> tuple[int, int]:
    if (hashlib.sha256(face).hexdigest() != FACE_SHA256
            or hashlib.sha256(spot).hexdigest() != SPOT_SHA256
            or tuple(map(tuple, recipe)) != RECIPE):
        raise FormatError("Unknown Spinda source textures or native shiny recipe")
    background = _linear_rgb565(face, 128, _FACE_ORDER)[0]
    counts = Counter(v for v in _linear_rgb565(spot, 32, _SPOT_ORDER) if v > background)
    return background, counts.most_common(1)[0][0]


@lru_cache(maxsize=2)
def native_bank(face: bytes, spot: bytes, recipe=RECIPE) -> tuple[bytes, dict]:
    """Build a bounded bank: empty, two backgrounds, 4×256×2 spot masks."""
    background, ink = native_sources(face, spot, recipe)
    empty = cmpr_layer(bytes(1024), ink)
    data = bytearray(empty)
    backgrounds = []
    layers = []
    for shiny in (False, True):
        colors = tuple(remap_rgb565(c, *recipe) if shiny else c for c in (background, ink))
        backgrounds.append(len(data))
        data.extend(cmpr_layer(bytes([1]) * 1024, colors[0], identity=4096 + int(shiny)))
        groups = []
        for index in range(4):
            groups.append(len(data))
            for value in range(256):
                data.extend(cmpr_layer(diagram_layer(spot, background, index, value), colors[1],
                                       identity=1 + int(shiny) * 1024 + index * 256 + value))
        layers.append(groups)
    return bytes(data), {"empty": 0, "backgrounds": backgrounds, "layers": layers,
        "texture_size": TEXTURE_SIZE, "texture_bytes": TEXTURE_BYTES,
        "variants_per_spot": 256, "spots": 4, "shiny_states": 2,
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "native_face_sha256": FACE_SHA256, "native_spot_sha256": SPOT_SHA256,
        "recipe": [list(RECIPE[0]), list(RECIPE[1])]}
