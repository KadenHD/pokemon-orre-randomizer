"""Exact regional REL identities and observed table allocations.

Indices are derived from each file's self-relocation stream. All three builds
use the same data schemas, while their offsets and native text banks differ.
No layout is guessed for an unrecognized input or for an already patched REL.
"""
from __future__ import annotations

from dataclasses import dataclass

from .analyze_game import FormatError, sha256


COMMON_SCHEMAS = {
    "trainers": (44, 45, 0x34), "trainer_pokemon": (48, 49, 0x50),
    "moves": (62, 63, 0x38), "species": (68, 69, 0x11C), "shadow": (80, 81, 0x38),
}
COMMON_COUNTS = {"trainers": 820, "trainer_pokemon": 5510, "moves": 358,
                 "species": 413, "shadow": 97}


@dataclass(frozen=True)
class RelRegion:
    game_id: str
    common_sha256: str
    common_size: int
    name_bank_indices: tuple[int, ...]
    native_languages: tuple[str, ...]
    treasure_offset: int
    shop_sha256: str

    @property
    def shop_archives(self) -> tuple[str, ...]:
        if self.game_id == "GC6P01":
            return tuple(f"pocket_menu{suffix}.fsys" for suffix in ("", "_fr", "_ge", "_it", "_sp"))
        return ("pocket_menu.fsys",)


REGIONS = (
    RelRegion("GC6P01", "ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b",
              2210420, (99, 100, 101, 102, 103), ("UK", "GE", "FR", "IT", "SP"), 0x1EAB74,
              "524ad778c3618d0c675e69f6a6bd6fab2e4e929d5a2e6981c1a8c25a555f9f20"),
    RelRegion("GC6E01", "0c89e679305f5e84eff3c774b542120c727ff350a0841cfc516235b3556df69e",
              1369520, (98,), ("US",), 0x11D7F8,
              "b1da5e636775cbcfd42979693f780d868fe03c2046f913ffab3b304864078d8a"),
    RelRegion("GC6J01", "62744eba0b4ba39e1019d15d550c35768903952a69f45673c0af31cee4658c42",
              856576, (95,), ("JP",), 0xA04D4,
              "23d388add709ff9975697105b1e471f228d1491b1ea8b6e7f36d84952bb51f4b"),
)


def region_for_rel(data: bytes) -> RelRegion:
    digest = sha256(data)
    match = next((r for r in REGIONS if r.common_sha256 == digest and r.common_size == len(data)), None)
    if match is None:
        raise FormatError("common.rel differs from the exact fingerprinted Europe, USA or Japan revision-0 originals")
    return match


def region_for_shop_rel(data: bytes) -> RelRegion:
    digest = sha256(data)
    match = next((r for r in REGIONS if r.shop_sha256 == digest), None)
    if match is None:
        raise FormatError("shop REL differs from the exact validated regional originals")
    return match


def shop_archive_names(original_common_rel: bytes) -> tuple[str, ...]:
    return region_for_rel(original_common_rel).shop_archives
