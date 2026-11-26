"""Initialize XD Deoxys form tags after native construction, without PID edits.

These hooks precede the existing Spinda installers and occupy adjacent inline
instructions, never their native PID or reward-call branches. Existing party
records are not reinitialized when viewed, moved, purified or loaded.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import struct

from .castform_layouts import LAYOUTS as ORIGINALS
from .deoxys_identity import DEOXYS, FORM_TAG
from .deoxys_runtime import _unchanged_outside
from .engine.analyze_game import FormatError, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import _Code
from .xd_battle_rules import ARENA, TEXT1_TO_RAM, append_xd_dol_text
from .xd_deoxys_runtime import _padded
from .xd_shiny_rules import _LAYOUTS as REWARDS, GIFT_KEYS
from .xd_spinda import _load_address
from .xd_spinda_trainers import _LAYOUTS as TRAINERS

VERSION = "xd-seeded-persistent-deoxys-forms-v1"
WILD = {"GXXP01": 0x801FCB14, "GXXE01": 0x801FADE0, "GXXJ01": 0x801F5AA4}
RECALCULATE = {"GXXP01": 0x80143598, "GXXE01": 0x80141CD4, "GXXJ01": 0x8013D0E0}
_SPOTS = {"rock": 0, "oasis": 1, "cave": 2}


def _token(value):
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise ValueError("A Deoxys form token must be a nonzero unsigned 32-bit integer")
    return FORM_TAG | value >> 30


def _rows(rewards, shadows, decks, poke_spots):
    for mapping in (rewards, shadows, decks, poke_spots):
        if not isinstance(mapping, Mapping):
            raise ValueError("Deoxys form plans must be mappings")
    if set(rewards) - {"starter", *GIFT_KEYS}:
        raise ValueError("Unknown XD Deoxys reward")
    reward_tags = {key: _token(value) for key, value in rewards.items()}
    shadow_rows = []
    for shadow, value in sorted(shadows.items()):
        if type(shadow) is not int or not 1 <= shadow <= 83:
            raise ValueError("Invalid XD Deoxys Shadow ID")
        shadow_rows.append((0, shadow, _token(value)))
    trainer_rows = list(shadow_rows)
    for resource, slots in sorted(decks.items()):
        if type(resource) is not int or not 1 <= resource <= 0xFFFFFFFF or not isinstance(slots, Mapping):
            raise ValueError("Invalid XD Deoxys trainer deck")
        for slot, value in sorted(slots.items()):
            if type(slot) is not int or not 1 <= slot <= 0xFFFF:
                raise ValueError("Invalid XD Deoxys trainer slot")
            trainer_rows.append((resource, slot, _token(value)))
    wild_rows = []
    for key, value in poke_spots.items():
        if (not isinstance(key, tuple) or len(key) != 2 or key[0] not in _SPOTS
                or type(key[1]) is not int or not 1 <= key[1] <= 3):
            raise ValueError("Invalid XD Deoxys Poke Spot slot")
        wild_rows.append((_SPOTS[key[0]], key[1] - 1, _token(value)))
    if len(trainer_rows) > 0x7FFF or len(wild_rows) > 9:
        raise ValueError("XD Deoxys plan exceeds native hook bounds")
    return reward_tags, tuple(shadow_rows), tuple(trainer_rows), tuple(sorted(wild_rows))


def _lookup(code, rows, table, *, key_a=7, key_b=8):
    """Bounded (u32 source, u32 slot, u32 tag) lookup; result r11 or zero."""
    if not rows:
        code.emit(0x39600000)
        return
    _load_address(code, 10, table)
    code.emit(0x39200000 | len(rows))
    code.label("search")
    code.emit(0x800A0000, 0x7C000040 | key_a << 11)
    code.conditional(0x40820000, "next")
    code.emit(0x800A0004, 0x7C000040 | key_b << 11)
    code.conditional(0x40820000, "next")
    code.emit(0x816A0008)
    code.jump("found")
    code.label("next")
    code.emit(0x394A000C, 0x3529FFFF)
    code.conditional(0x40820000, "search")
    code.emit(0x39600000)
    code.label("found")


def _initialize(code, record):
    code.emit(0xA0000000 | record << 16, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "done")
    code.emit(0xA000000C | record << 16, 0x28000000)
    code.conditional(0x40820000, "done")  # Never replace a stored/user-changed or foreign value.
    code.emit(0x5560003A, 0x28000000 | FORM_TAG)
    code.conditional(0x40820000, "done")
    code.emit(0xB160000C | record << 16)


def _finish_rows(code, rows, table):
    body = code.finish()
    if len(body) > table - code.address:
        raise FormatError("XD Deoxys initializer overlaps its bounded table")
    encoded = b"".join(struct.pack(">III", *row) for row in rows)
    payload = body + bytes(table - code.address - len(body)) + encoded
    return payload + bytes(-len(payload) % 32)


def _capture_slot(address, continuation):
    code = _Code(address)
    code.emit(0x90610038, 0x7C9F2378)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _deck_state(address, continuation, state):
    code = _Code(address)
    _load_address(code, 12, state + 4)
    code.emit(0x93EC0000, 0x38610008)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _trainer(address, continuation, state, rows):
    table = address + 0x200
    code = _Code(address)
    code.emit(0xA11F00BA, 0x28080000)
    code.conditional(0x41820000, "ordinary")
    code.emit(0x38E00000)
    code.jump("lookup")
    code.label("ordinary")
    _load_address(code, 12, state + 4)
    code.emit(0x80EC0000, 0x81010038)
    code.label("lookup")
    _lookup(code, rows, table)
    _initialize(code, 31)
    code.label("done")
    code.emit(0x7FE3FB78)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _finish_rows(code, rows, table)


def _reward_pre(address, continuation, displaced, state, reward_tags, *, starter):
    code = _Code(address)
    code.emit(displaced)  # Preserve the native parameter-store value before using r0.
    _load_address(code, 12, state)
    code.emit(0x39600000, 0x916C0000, 0xA0040002, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "done")
    if starter:
        code.emit(0x39600000, 0x616B0000 | reward_tags["starter"])
    else:
        for index, key in enumerate(GIFT_KEYS, 8):
            if key in reward_tags:
                code.emit(0x281E0000 | index)
                code.conditional(0x41820000, f"gift_{index}")
        code.jump("done")
        for index, key in enumerate(GIFT_KEYS, 8):
            if key in reward_tags:
                code.label(f"gift_{index}")
                code.emit(0x39600000, 0x616B0000 | reward_tags[key])
                code.jump("store")
    code.label("store")
    code.emit(0x916C0000)
    code.label("done")
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _reward_clear(address, continuation, displaced, state):
    code = _Code(address)
    _load_address(code, 12, state)
    code.emit(0x39600000, 0x916C0000, displaced)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _hero(address, continuation, state, rows):
    table = address + 0x200
    code = _Code(address)
    _load_address(code, 12, state)
    code.emit(0x816C0000, 0x38000000, 0x900C0000, 0x280B0000)
    code.conditional(0x40820000, "initialize")
    code.emit(0x38E00000, 0xA11D0004)
    _lookup(code, rows, table)
    code.label("initialize")
    code.emit(0x39810008)
    _initialize(code, 12)
    code.label("done")
    code.emit(0x38610008)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _finish_rows(code, rows, table)


def _wild_capture(address, continuation, *, slot):
    code = _Code(address)
    code.emit(*( (0x93E100D4, 0x7C1F0378) if slot else (0x936100D0, 0x1C7B001C) ))
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _wild(address, continuation, rows, recalculate):
    table = address + 0x200
    code = _Code(address)
    code.emit(0x80E100D0, 0x810100D4)
    _lookup(code, rows, table)
    code.emit(0x39810008)
    _initialize(code, 12)
    # This is a new encounter, before either native full-record copy. Native
    # recalc sees the tag and keeps its PID, IVs, EVs, nature and shiny decision.
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x38610028)
    code.call(recalculate)
    code.emit(0x80010024, 0x7C0803A6, 0x38210020)
    code.label("done")
    code.emit(0x7FE3FB78)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _finish_rows(code, rows, table)


def install_xd_deoxys_generation(original, current, game_id, *, rewards, shadows, decks, poke_spots):
    reward_tags, shadow_rows, trainer_rows, wild_rows = _rows(rewards, shadows, decks, poke_spots)
    if not (reward_tags or shadow_rows or trainer_rows or wild_rows):
        return current, {"version": VERSION, "enabled": False, "hooks": []}
    if (game_id not in WILD or type(original) is not bytes or type(current) is not bytes
            or hashlib.sha256(original).hexdigest() != ORIGINALS[game_id]["sha256"]):
        raise FormatError("unknown original XD Deoxys generation executable")
    reward, trainer = REWARDS[game_id], TRAINERS[game_id]
    hero = reward.hero_policy - 0x138 + TEXT1_TO_RAM
    creator, wild = trainer.slot_lookup - 0x60, WILD[game_id]
    state = [None]
    definitions = []
    if trainer_rows:
        definitions += [(trainer.register + 4, 0x38610008, lambda a, c: _deck_state(a, c, state[0]), "deck"),
                        (creator + 0x24, 0x7C9F2378, _capture_slot, "trainer_slot"),
                        (creator + 0x700, 0x7FE3FB78, lambda a, c: _trainer(a, c, state[0], trainer_rows), "trainer_tag")]
    if reward_tags or shadow_rows:
        definitions.append((hero + 0x16C, 0x38610008, lambda a, c: _hero(a, c, state[0], shadow_rows), "reward_tag"))
    if "starter" in reward_tags:
        call = reward.starter_policy + TEXT1_TO_RAM + 0x20
        if any(u32(d, call - TEXT1_TO_RAM) != branch(call, hero, link=True) for d in (original, current)):
            raise FormatError("install Deoxys generation before XD Spinda reward hooks")
        after = 0x7FC3F378 if game_id == "GXXJ01" else 0x7FE3FB78
        definitions += [(call - 4, 0x9001003C, lambda a, c: _reward_pre(a, c, 0x9001003C, state[0], reward_tags, starter=True), "starter_activate"),
                        (call + 4, after, lambda a, c: _reward_clear(a, c, after, state[0]), "starter_clear")]
    if set(reward_tags) & set(GIFT_KEYS):
        call = reward.gift_setup + TEXT1_TO_RAM + 0x28
        if any(u32(d, call - TEXT1_TO_RAM) != branch(call, hero, link=True) for d in (original, current)):
            raise FormatError("install Deoxys generation before XD Spinda gift hooks")
        definitions += [(call - 4, 0x9001001C, lambda a, c: _reward_pre(a, c, 0x9001001C, state[0], reward_tags, starter=False), "gift_activate"),
                        (call + 4, 0xA0010010, lambda a, c: _reward_clear(a, c, 0xA0010010, state[0]), "gift_clear")]
    if wild_rows:
        definitions += [(wild + 0xF8, 0x1C7B001C, lambda a, c: _wild_capture(a, c, slot=False), "wild_spot"),
                        (wild + 0x214, 0x7C1F0378, lambda a, c: _wild_capture(a, c, slot=True), "wild_slot"),
                        (wild + 0x2EC, 0x7FE3FB78, lambda a, c: _wild(a, c, wild_rows, RECALCULATE[game_id]), "wild_tag")]
    for call, expected, _, _ in definitions:
        pos = call - TEXT1_TO_RAM
        if any(u32(d, pos) != expected for d in (original, current)):
            raise FormatError(f"unexpected XD Deoxys generation instruction at {call:#x}")
    first = definitions[0]
    def bootstrap(address, continuation):
        state[0] = 0
        provisional = first[2](address, continuation)
        state[0] = address + len(provisional)
        payload = first[2](address, continuation)
        if len(payload) != len(provisional):
            raise FormatError("XD Deoxys state reservation changed builder size")
        return payload + bytes(32)
    hooks = [(first[0], first[1], bootstrap)]
    hooks += [(call, word, build) for call, word, build, _ in definitions[1:]]
    output, report = append_xd_dol_text(original, current, game_id, hooks)
    offset, arena = (len(original) + 31) & ~31, ARENA[game_id][1] - TEXT1_TO_RAM
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (offset, offset + 32), (arena, arena + 4)]
    allowed += [(call - TEXT1_TO_RAM, call - TEXT1_TO_RAM + 4) for call, *_ in definitions]
    if not _unchanged_outside(current, output, allowed):
        raise FormatError("XD Deoxys generation changed unrelated executable bytes")
    return output, {"version": VERSION, "enabled": True, "state": state[0],
                    "hooks": [dict(entry, kind=definition[3]) for entry, definition in zip(report, definitions, strict=True)],
                    "rewards": len(reward_tags), "shadows": len(shadow_rows),
                    "trainer_rows": len(trainer_rows) - len(shadow_rows), "poke_spots": len(wild_rows),
                    "form_tag": FORM_TAG, "native_pid_generation_and_rng_unchanged": True,
                    "unrelated_executable_bytes_preserved": True,
                    "record_writes": "One reserved u16 only on freshly constructed genuine Deoxys with an empty reservation"}
