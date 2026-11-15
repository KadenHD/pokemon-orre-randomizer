"""Shared image formats for added models, independent of species and Qt.

Portraits and whole-body artwork are separate inputs. Never enlarge a face
into a DNA image or crop artwork just to fit a game's portrait frame.
"""

PORTRAIT_SIZE = 42
XD_ARTWORK_SIZE = 36
BODY_SIZE = 64


def format_model_portrait(pixels: bytes, *, game: str, alpha_mask: bytes | None = None,
                          artwork_size: int = 28) -> bytes:
    """Fit an opaque 42px face to Colosseum's square or XD's round frame.

    An audited native alpha mask can replace the default antialiased circle.
    The default fits the whole square inside the circle. Audited artwork may
    request a larger size after checking that its silhouette remains inside.
    Area averaging includes every source pixel, retaining the complete face.
    Transparent output pixels always have zero RGB.
    """
    size = PORTRAIT_SIZE
    if game not in ("colosseum", "xd"):
        raise ValueError("unsupported portrait game")
    if len(pixels) != size * size * 4 or any(alpha != 255 for alpha in pixels[3::4]):
        raise ValueError("expected an opaque 42x42 RGBA portrait")
    if alpha_mask is not None and (game != "xd" or len(alpha_mask) != size * size):
        raise ValueError("expected one XD portrait alpha mask")
    if type(artwork_size) is not int or not 1 <= artwork_size <= size:
        raise ValueError("invalid fitted portrait dimensions")
    if game == "colosseum":
        return pixels
    if alpha_mask is None:
        # Supersample only the silhouette. Artwork uses integer area filtering.
        samples = 4
        diameter = size * samples
        alpha_mask = bytes(round(255 * sum(
            (2 * (x * samples + dx) + 1 - diameter) ** 2
            + (2 * (y * samples + dy) + 1 - diameter) ** 2 <= diameter ** 2
            for dy in range(samples) for dx in range(samples)) / (samples * samples))
            for y in range(size) for x in range(size))
    output = bytearray(size * size * 4)
    output[3::4] = alpha_mask
    fitted = artwork_size
    padding = (size - fitted) // 2
    spans = []
    for destination in range(fitted):
        left, right = destination * size, (destination + 1) * size
        spans.append([(sample, min((sample + 1) * fitted, right) - max(sample * fitted, left))
                      for sample in range(left // fitted, (right - 1) // fitted + 1)])
    for y, vertical in enumerate(spans):
        for x, horizontal in enumerate(spans):
            at = ((y + padding) * size + x + padding) * 4
            if not output[at + 3]:
                continue
            for channel in range(3):
                total = sum(pixels[(sy * size + sx) * 4 + channel] * wx * wy
                            for sy, wy in vertical for sx, wx in horizontal)
                output[at + channel] = (total + size * size // 2) // (size * size)
    return bytes(output)


def validate_model_body(pixels: bytes) -> bytes:
    """Require separate whole-body RGBA64 artwork with an unclipped margin.

    Dimensions cannot prove an image contains the whole model. Its capture
    provenance and a visual silhouette check remain part of adding an asset.
    """
    size = BODY_SIZE
    if len(pixels) != size * size * 4 or not any(pixels[3::4]):
        raise ValueError("expected visible 64x64 RGBA whole-body artwork")
    if any(pixels[(y * size + x) * 4 + 3] for y in range(size) for x in range(size)
           if x in (0, size - 1) or y in (0, size - 1)):
        raise ValueError("whole-body artwork must have a transparent margin")
    return pixels
