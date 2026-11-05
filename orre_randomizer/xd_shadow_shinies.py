"""Seeded XD Shadow PID modes with stable player ownership before capture."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct

from .engine.analyze_game import FormatError, check_range, u32
from .engine.shiny_rules import _Code, seeded_status
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text


VERSION = "xd-shadow-shiny-status-v1"
SHADOW_COUNT = 83


@dataclass(frozen=True)
class _Layout:
    pid_generator: int
    shadow_pid: int
    hero_shadow_pid: int
    trainer_owner: int
    player_lookup: int
    owner_setter: int
    original_sha256: str


_LAYOUTS = {
    "GXXP01": _Layout(0x80142E04, 0x801FDFE8, 0x801544C4, 0x801FC768, 0x801D0A8C, 0x80149DB0,
        "a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd"),
    "GXXE01": _Layout(0x80141540, 0x801FC2B4, 0x80152C00, 0x801FAA34, 0x801CEFB4, 0x801484EC,
        "c8659341c252d1b088753d508769344eb6f092b5da5cc7cc0ce1560b32478c15"),
    "GXXJ01": _Layout(0x8013C94C, 0x801F6F78, 0x8014DF28, 0x801F56F8, 0x801C9E54, 0x801438E8,
        "14c129cc0f79682574f635290b09e37fa2a652ac5aa5565281bd583c31c5d702"),
}


def shadow_statuses(seed, options):
    if not options.custom_shinies or not options.custom_shadow_shinies:
        return {}
    return {str(index): seeded_status(seed, f"{VERSION}:{index}", options.shiny_chance_percent)
            for index in range(1, SHADOW_COUNT + 1)}


def _pid_stub(address, pid_generator, flags, *, hero=False):
    if len(flags) != SHADOW_COUNT + 1 or any(flag not in (0, 1) for flag in flags):
        raise ValueError("invalid XD Shadow shiny flags")
    table = address + 0x100
    code = _Code(address)
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044,
              0x90610008, 0x9081000C, 0x90A10010, 0x90E10014)
    code.emit(0xA17D0004 if hero else 0x57CB043E)  # param+4 or caller r30: Shadow ID
    code.emit(0x280B0000 | SHADOW_COUNT)
    code.conditional(0x41810000, "invalid")
    code.emit(0x3D800000 | (table >> 16), 0x618C0000 | (table & 0xFFFF), 0x7CCC58AE)
    code.jump("ready")
    code.label("invalid")
    code.emit(0x38C00000)
    code.label("ready")
    code.emit(0x80610008, 0x8081000C, 0x80A10010, 0x80E10014)
    code.call(pid_generator)
    code.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    body = code.finish()
    if len(body) > 0x100:
        raise FormatError("XD Shadow shiny wrapper overlaps its flags")
    return body + bytes(0x100 - len(body)) + flags + bytes((-len(flags)) % 32)


def _owner_stub(address, player_lookup, owner_setter):
    code = _Code(address)
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044, 0x90610008, 0x9081000C,
              0x28030000)
    code.conditional(0x41820000, "native_owner")
    code.emit(0xA16300BA, 0x280B0000)  # Pokemon Shadow ID
    code.conditional(0x41820000, "native_owner")
    code.emit(0x280B0000 | SHADOW_COUNT)
    code.conditional(0x41810000, "native_owner")
    code.emit(0x38600000, 0x38800002)
    code.call(player_lookup)  # savedataGetStatus(NULL, 2): principal Hero
    code.emit(0x28030000)
    code.conditional(0x41820000, "native_owner")
    code.emit(0x8083002C)  # player's whole SID/TID word
    code.jump("assign")
    code.label("native_owner")
    code.emit(0x8081000C)
    code.label("assign")
    code.emit(0x80610008)
    code.call(owner_setter)
    code.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    return code.finish()


def apply_shadow_shiny_rules(original, current, game_id, seed, options):
    statuses = shadow_statuses(seed, options)
    report = {"version": VERSION, "enabled": bool(statuses)}
    if not statuses:
        return current, report
    layout = _LAYOUTS[game_id]
    if hashlib.sha256(original).hexdigest() != layout.original_sha256:
        raise FormatError("unexpected original XD Shadow shiny executable")
    flags = bytes([0] + [int(statuses[str(index)]) for index in range(1, SHADOW_COUNT + 1)])
    from .engine.gift_move_hooks import branch
    definitions = (
        (layout.shadow_pid, layout.pid_generator,
         lambda address, _continuation: _pid_stub(address, layout.pid_generator, flags)),
        (layout.hero_shadow_pid, layout.pid_generator,
         lambda address, _continuation: _pid_stub(address, layout.pid_generator, flags, hero=True)),
        (layout.trainer_owner, layout.owner_setter,
         lambda address, _continuation: _owner_stub(address, layout.player_lookup, layout.owner_setter)),
    )
    hooks = []
    for address, target, builder in definitions:
        offset = address - TEXT1_TO_RAM
        check_range(original, offset, 4, "XD Shadow shiny call")
        expected = branch(address, target, link=True)
        if u32(original, offset) != expected or u32(current, offset) != expected:
            raise FormatError("unexpected XD Shadow shiny call instruction")
        hooks.append((address, expected, builder))
    output, report["hooks"] = append_xd_dol_text(original, current, game_id, hooks, link=True)
    report.update(chance_percent=options.shiny_chance_percent, statuses=statuses)
    return output, report
