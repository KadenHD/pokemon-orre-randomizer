"""Exact, independently identified retail disc revisions accepted by the pipeline.

Headers select a candidate only. The complete decoded ISO must match its SHA-256
before any transformation; a region code alone never authorizes patching.
"""
from __future__ import annotations

from dataclasses import dataclass

from .analyze_game import FormatError

DISC_SIZE = 1_459_978_240


@dataclass(frozen=True)
class Region:
    game_id: str
    name: str
    iso_sha256: str
    dol_size: int
    languages: tuple[str, ...]
    revision: int = 0

    def profile_identity(self) -> dict:
        return {"id": self.game_id, "revision": self.revision,
                "iso_sha256": self.iso_sha256}


REGIONS = (
    Region("GC6P01", "Europe",
           "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9",
           4_096_576, ("en", "de", "fr", "it", "es")),
    Region("GC6E01", "USA",
           "78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5",
           3_779_808, ("en",)),
    Region("GC6J01", "Japan",
           "17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f",
           3_699_680, ("ja",)),
)


def region_for_id(game_id: str) -> Region:
    for region in REGIONS:
        if region.game_id == game_id:
            return region
    raise FormatError("unsupported Colosseum region")


def region_for_boot(boot: bytes) -> Region:
    if (len(boot) < 0x440 or boot[6:8] != b"\0\0"
            or boot[0x1C:0x20] != bytes.fromhex("c2339f3d")):
        raise FormatError("unsupported Colosseum disc header or revision")
    try:
        return region_for_id(boot[:6].decode("ascii"))
    except UnicodeError:
        raise FormatError("invalid Colosseum game identifier") from None


def validate_disc_hash(boot: bytes, digest: str) -> Region:
    region = region_for_boot(boot)
    if digest != region.iso_sha256:
        raise FormatError("disc differs from the exact validated original revision")
    return region
