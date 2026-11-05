"""Seeded PID policies for XD's starter and seven ordinary rewards."""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .engine.analyze_game import FormatError, check_range, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import seeded_status
from .xd_gifts import GIFT_BASELINES

VERSION = "xd-seeded-shiny-status-v1"
GIFT_KEYS = tuple(row[0] for row in GIFT_BASELINES)


@dataclass(frozen=True)
class _Layout:
    starter_policy: int
    gift_setup: int
    hero_policy: int
    pid_call: int
    gift_dispatch: int
    tutorial_setup: int = 0
    tutorial_templates: int = 0


_LAYOUTS = {
    "GXXP01": _Layout(0x1CD784, 0x1C7324, 0x15143C, 0x4BFEE925, 0x1C702C, 0x1CD5B8, 0x2F7608),
    "GXXE01": _Layout(0x1CBCB0, 0x1C5A28, 0x14FB78, 0x4BFEE925, 0x1C5730, 0x1CBAE4, 0x2F5770),
    "GXXJ01": _Layout(0x1C6B54, 0x1C0EBC, 0x14AEA0, 0x4BFEEA09, 0x1C0C40),
}


def encounter_shiny(seed: str, options, key: str) -> bool | None:
    if not options.custom_shinies or key not in ("starter", *GIFT_KEYS):
        return None
    return seeded_status(seed, f"{VERSION}:{key}", options.shiny_chance_percent)


def apply_shiny_rules(original: bytes, current: bytes, game_id: str, seed: str, options) -> tuple[bytes, dict]:
    report = {"version": VERSION, "enabled": options.custom_shinies}
    if not options.custom_shinies:
        return current, report
    layout = _LAYOUTS[game_id]
    hero = layout.hero_policy - 0x138
    starter = layout.starter_policy
    gift = layout.gift_setup
    pid_call = layout.pid_call
    tutorial = layout.tutorial_setup
    if len(current) < len(original):
        raise FormatError("XD shiny rules received a truncated executable")

    # Hero::pokemonGet uses the lower half of param+0x1C as the catch floor.
    # Carry the shiny mode in the upper half, ignored by the retail routine.
    # The OT SID/TID at param+0x10 is both saved and passed to the PID generator.
    signatures = {
        hero + 0x54: (0x801D001C, 0x38610008, 0x5404043E),
        hero + 0x6A0: (0x8063002C, 0x4E800020),  # getHeroRnd reads a word, then returns.
        layout.hero_policy - 0x20: (0x38A0FFFF, 0x38C00000, pid_call + 0x1C, 0x4800001C,
                                   0x80FD0010, 0x38610008, 0x3880FFFF, 0x38A0FFFF, 0x38C0FFFF, pid_call),
        starter: (0x38C00000, 0x380004E2, 0x90610030, 0x7FE3FB78 if tutorial else 0x7FC3F378,
                  0x3881001C, 0x38A00001, 0x90C10038, 0x9001003C, branch(starter + 0x20, hero, link=True)),
        layout.gift_dispatch: (0x389EFFF9, 0x38000000, 0x28040007),
        gift: (0x7FE3FB78, branch(gift + 4, hero + 0x6A0, link=True), 0x8001001C, 0x5466001E,
               0x7FE3FB78, 0x3881000C, 0x5400043E, 0x38A00001, 0x7C003378, 0x9001001C,
               branch(gift + 0x28, hero, link=True)),
    }
    if tutorial:
        signatures[tutorial] = (0x80DD0010, 0x3881001C, 0x801D0014, 0x38A00001, 0x90610030,
                                0x7FE3FB78, 0x3BBD001C, 0x90C10038, 0x9001003C,
                                branch(tutorial + 0x24, hero, link=True))
        for slot in range(4):
            signatures[layout.tutorial_templates + slot * 0x1C + 0x10] = (0,)
    for offset, words in signatures.items():
        check_range(original, offset, 4 * len(words), "XD shiny policy")
        if any(u32(data, offset + i * 4) != word for data in (original, current) for i, word in enumerate(words)):
            raise FormatError(f"unexpected XD shiny policy instructions at {offset:#x}")

    statuses = {key: encounter_shiny(seed, options, key) for key in ("starter", *GIFT_KEYS)}
    # Reward switch indices 8..14 correspond to Hordel, Duking's three
    # trades and the three Mt. Battle prizes. Index 7 is Shadow Togepi.
    # Reuse the instructions that used to copy getHeroRnd into the discarded
    # high half. Neither the low half nor the separate OT field is touched.
    mask = sum(int(statuses[key]) << (8 + slot) for slot, key in enumerate(GIFT_KEYS))
    patches = {
        layout.hero_policy: 0xA8DD001C,  # lha r6,0x1c(r29)
        starter: 0x3CC00000 | int(statuses["starter"]),  # lis r6,mode
        gift: 0x38600000 | mask,  # li r3,mask
        gift + 4: 0x7C63F430,  # srw r3,r3,r30
        gift + 0xC: 0x546683DE,  # rlwinm r6,r3,16,15,15
    }
    if tutorial:
        patches[tutorial] = 0x3CC0FFFF  # lis r6,-1 keeps the native policy and the zero catch floor.
    output = bytearray(current)
    for offset, word in patches.items():
        struct.pack_into(">I", output, offset, word)
    report["chance_percent"] = options.shiny_chance_percent
    report["statuses"] = statuses
    return bytes(output), report
