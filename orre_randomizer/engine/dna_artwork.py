"""The DNA keypad outlines new body renders; retail body art keeps its own ink."""
from collections import deque
from functools import lru_cache


def _expanded_alpha(alpha, size, radius):
    """Separable maximum filter, linear in image area rather than stroke width."""
    for stride, starts in ((1, range(0, size * size, size)), (size, range(size))):
        result = bytearray(size * size)
        for start in starts:
            window = deque()
            for index in range(size + radius):
                if index < size:
                    value = alpha[start + index * stride]
                    while window and alpha[start + window[-1] * stride] <= value:
                        window.pop()
                    window.append(index)
                while window and window[0] < index - radius * 2:
                    window.popleft()
                if index >= radius:
                    result[start + (index - radius) * stride] = alpha[start + window[0] * stride]
        alpha = result
    return alpha


@lru_cache(maxsize=16)
def outline_dna_body(pixels: bytes, size: int) -> bytes:
    """Add black behind the silhouette at one native pixel or four HD pixels.

    Opaque material colors stay exact. Only the transparent contour and its
    antialiased edge change; the image is never mirrored, moved or rescaled.
    This operation is for new transparent GPU captures, not retail portraits.
    """
    if type(size) is not int or size not in (64, 256) or len(pixels) != size * size * 4:
        raise ValueError("expected a native or x4 RGBA DNA body")
    alpha = pixels[3::4]
    expanded = _expanded_alpha(alpha, size, size // 64)
    result = bytearray(len(pixels))
    for index, (inside, outside) in enumerate(zip(alpha, expanded)):
        combined = inside + outside - (inside * outside + 127) // 255
        at = index * 4
        if combined:
            for channel in range(3):
                result[at + channel] = (pixels[at + channel] * inside + combined // 2) // combined
        result[at + 3] = combined
    return bytes(result)
