"""Deterministic XD Spinda personality generation at known reward calls."""

import struct

from .engine.analyze_game import FormatError, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import _Code
from .engine.spinda import SPINDA
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_shiny_rules import GIFT_KEYS, _LAYOUTS


def emit_spinda_pid_fit(code):
    """Fit candidate r3 to owner r7 and shiny mode r6, leaving native mode alone."""
    code.emit(0x2C060000)  # cmpwi r6,0
    code.conditional(0x41800000, "spinda_pid_ready")
    code.emit(0x54E4843E, 0x7C843A78, 0x5465843E, 0x7C842A78,
              0x7C841A78, 0x5484043E)  # r4 = owner high ^ owner low ^ PID high ^ PID low
    code.conditional(0x41820000, "spinda_pid_normal")
    code.emit(0x54848018, 0x7C632278)  # clear all but the lowest 3 shiny XOR bits
    code.jump("spinda_pid_ready")
    code.label("spinda_pid_normal")
    code.emit(0x28040008)
    code.conditional(0x40800000, "spinda_pid_ready")
    code.emit(0x6C630008)  # xoris r3,r3,8: guarantees ordinary colors
    code.label("spinda_pid_ready")


def _load_address(code, register, address):
    code.emit(0x3C000000 | register << 21 | address >> 16,
              0x60000000 | register << 21 | register << 16 | (address & 0xFFFF))


def _tail_call(code, target):
    code.emit(branch(code.address + len(code.words) * 4, target))


def _pid_hook(address, native, state):
    code = _Code(address)
    _load_address(code, 12, state)
    code.emit(0x800C0000, 0x28000000)  # active Spinda reward marker
    code.conditional(0x41820000, "native")
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,
              0x90C10008, 0x90E1000C, 0x800C0004, 0x90010010)
    code.call(native)  # keep native RNG consumption and ABI effects
    code.emit(0x80610010, 0x80C10008, 0x80E1000C)
    emit_spinda_pid_fit(code)
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    code.label("native")
    _tail_call(code, native)
    payload = code.finish()
    if len(payload) > state - address:
        raise FormatError("XD Spinda PID wrapper overlaps its state")
    return payload + bytes(state - address - len(payload) + 32)


def _reward_hook(address, hero, state, *, starter=None, gifts=None):
    code = _Code(address)
    code.emit(0xA0040002, 0x28000000 | SPINDA)  # lhz r0,2(r4): actual reward species
    code.conditional(0x40820000, "native")
    if gifts is None:
        _load_address(code, 11, starter)
    else:
        table = address + 0xC0
        code.emit(0x381EFFF8, 0x28000006)  # gift dispatch indices 8..14
        code.conditional(0x41810000, "native")
        _load_address(code, 12, table)
        code.emit(0x54001838, 0x7D8C0214, 0x800C0000, 0x28000000)
        code.conditional(0x41820000, "native")
        code.emit(0x816C0004)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024)
    _load_address(code, 12, state)
    code.emit(0x800C0000, 0x90010008, 0x800C0004, 0x9001000C,
              0x38000001, 0x916C0004, 0x900C0000)
    code.call(hero)
    _load_address(code, 12, state)
    code.emit(0x8001000C, 0x900C0004, 0x80010008, 0x900C0000,
              0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    code.label("native")
    _tail_call(code, hero)
    payload = code.finish()
    if gifts is None:
        return payload
    if len(payload) > table - address:
        raise FormatError("XD Spinda reward wrapper overlaps its table")
    rows = b"".join(struct.pack(">II", int(value is not None), value or 0) for value in gifts)
    return payload + bytes(table - address - len(payload)) + rows + bytes(-len(rows) % 32)


def apply_spinda_pids(original, current, game_id, pids):
    """Install only the starter and ordinary reward paths that can produce Spinda."""
    if not pids:
        return current, []
    if set(pids) - {"starter", *GIFT_KEYS} or any(type(pid) is not int or not 0 <= pid <= 0xFFFFFFFF
                                                  for pid in pids.values()):
        raise ValueError("invalid XD Spinda reward PID candidates")
    layout = _LAYOUTS[game_id]
    hero_offset = layout.hero_policy - 0x138
    hero = hero_offset + TEXT1_TO_RAM
    normal_call = layout.hero_policy + 4
    raw_branch = layout.pid_call & 0x03FFFFFC
    native = normal_call + raw_branch - (0x4000000 if raw_branch & 0x2000000 else 0) + TEXT1_TO_RAM
    # The normal branch has unrestricted gender and nature. The gift/hero
    # hooks pass that exact native mode and owner through to PID fitting.
    if (u32(original, normal_call) != layout.pid_call
            or (u32(original, normal_call - 12), u32(original, normal_call - 8)) != (0x3880FFFF, 0x38A0FFFF)
            or u32(original, hero_offset + 0x34) != 0xA09D0002):
        raise FormatError("unexpected XD Spinda reward constructor")

    def pid_hook(address, _continuation):
        state[0] = address + 0xA0
        return _pid_hook(address, native, state[0])

    state = [0]
    hooks = [(normal_call + TEXT1_TO_RAM, layout.pid_call, pid_hook)]
    if "starter" in pids:
        call = layout.starter_policy + 0x20 + TEXT1_TO_RAM
        hooks.append((call, branch(call, hero, link=True), lambda address, _continuation:
                      _reward_hook(address, hero, state[0], starter=pids["starter"])))
    gifts = [pids.get(key) for key in GIFT_KEYS]
    if any(pid is not None for pid in gifts):
        call = layout.gift_setup + 0x28 + TEXT1_TO_RAM
        hooks.append((call, branch(call, hero, link=True), lambda address, _continuation:
                      _reward_hook(address, hero, state[0], gifts=gifts)))
    return append_xd_dol_text(original, current, game_id, hooks, link=True)
