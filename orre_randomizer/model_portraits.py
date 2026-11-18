"""Integrity-checked portrait variants shared by the app and native face writers.

The original XD extraction remains a reference. Registered derivatives carry
their own source metadata and both games' native/x4 framing in a separate file.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
import json
from pathlib import Path
import struct


MANIFEST = "portrait-variants.json"

# Quadratic UV fit of 559 opaque backdrop pixels from XD face249dark.
# These coefficients reproduce its violet palette without enlarging a native
# bitmap. The square extension stays within the original purple palette.
_VIOLET = (
    (114.4031302836, 16.3491360606, 5.6948824610, -27.2329528892, -25.0713133142, -43.1607376738),
    (49.2768819202, 9.1130895256, -.0296383116, -15.6927866570, -14.4338476020, -26.2007360451),
    (149.2696478582, 22.7412475205, 7.1898613299, -34.8165418504, -33.6302489342, -56.3150445866),
)


@lru_cache(maxsize=4)
def violet_backdrop(*, game: str, scale: int) -> bytes:
    """Render the native violet palette with square or native circular alpha."""
    # Validate using the same dimensions accepted by the registered files.
    portrait_filename(game, False, scale)
    size = 42 * scale
    output = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            u, v = ((x + .5) / scale - 21) / 21, ((y + .5) / scale - 21) / 21
            terms = (1, u, v, u * u, u * v, v * v)
            rgb = [max(floor, min(255, int(sum(a * b for a, b in zip(row, terms)) + .5)))
                   for floor, row in zip((41, 16, 57), _VIOLET)]
            if game == "colosseum":
                alpha = 255
            elif scale == 1:
                alpha = 255 if (x + .5 - 21) ** 2 + (y + .5 - 21) ** 2 <= 22.5 ** 2 else 0
            else:
                samples = sum(((x + (sx + .5) / 4) / scale - 21) ** 2
                              + ((y + (sy + .5) / 4) / scale - 21) ** 2 <= 22.5 ** 2
                              for sy in range(4) for sx in range(4))
                alpha = (samples * 255 + 8) // 16
            if alpha:
                at = (y * size + x) * 4
                output[at:at + 4] = bytes((*rgb, alpha))
    return bytes(output)


def portrait_filename(game: str, shiny: bool, scale: int) -> str:
    if (game not in ("colosseum", "xd") or type(shiny) is not bool
            or type(scale) is not int or scale not in (1, 4)):
        raise ValueError("Invalid registered portrait variant")
    return f"shadow-lugia-{game}-{'shiny' if shiny else 'normal'}-{'native' if scale == 1 else 'x4'}.png"


def registered_portrait(models: Path, *, game: str, shiny: bool = False,
                        scale: int = 1) -> bytes | None:
    """Return an authenticated PNG, or None when this optional set is absent.

    An installed but corrupt set raises instead of silently selecting old art.
    Paths are fixed by code; the manifest cannot redirect a reader elsewhere.
    """
    name = portrait_filename(game, shiny, scale)
    models = Path(models)
    manifest = models / MANIFEST
    if not manifest.exists():
        return None
    if (models.is_symlink() or models.is_junction() or manifest.is_symlink()
            or not manifest.is_file() or not 1 <= manifest.stat().st_size <= 128 * 1024):
        raise ValueError("Invalid portrait manifest")
    try:
        metadata = json.loads(manifest.read_text("utf-8"))
        if metadata.get("schema") != 1:
            raise ValueError("Unsupported portrait manifest")
        if metadata.get("review_only") is True:
            raise ValueError("These portrait candidates have not passed visual review")
        record = metadata["files"][name]
        path = models / name
        size = 42 * scale
        if (not path.is_file() or path.is_symlink() or not 1 <= path.stat().st_size <= 1024 * 1024
                or record.get("game") != game or record.get("shiny") is not shiny
                or record.get("scale") != scale or record.get("dimensions") != [size, size]):
            raise ValueError("Invalid portrait asset metadata")
        payload = path.read_bytes()
        if (record.get("bytes") != len(payload)
                or record.get("sha256") != hashlib.sha256(payload).hexdigest()
                or payload[:16] != b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"
                or struct.unpack_from(">II", payload, 16) != (size, size)):
            raise ValueError("Portrait asset integrity check failed")
        return payload
    except (OSError, TypeError, KeyError, json.JSONDecodeError, struct.error) as error:
        raise ValueError("Invalid registered portrait set") from error
