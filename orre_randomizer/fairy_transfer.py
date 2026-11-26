"""Reject GBA trade selection only for the seven GameCube-only Fairy moves.

Pokémon records remain valid locally. No ability, species, save flag or move is
rewritten, and eligible trades retain the retail flow. Colosseum uses the retail
selection refusal UI with an explicitly provided localized native XD message.
"""
from __future__ import annotations

import hashlib
import struct

from .castform_portraits import _reservation
from .engine.analyze_game import FormatError, parse_dol
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code
from .fairy_runtime import _offset, _read, qualify_fairy_runtime

VERSION = "fairy-gba-trade-selection-guard-v1"
FIRST_MOVE, LAST_MOVE = 375, 381


def _load(code, register, value):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | value & 65535)


def _scan(code, offset, *, side=False):
    if side:
        code.emit(0x2C040000)
        code.conditional(0x40820000, "native")
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    for slot in range(4):
        code.emit(0xA0030000 | offset + 4 * slot, 0x28000000 | FIRST_MOVE)
        code.conditional(0x41800000, f"slot{slot}")
        code.emit(0x28000000 | LAST_MOVE)
        code.conditional(0x40810000, "refuse")
        code.label(f"slot{slot}")


def _xd_guard(address, row):
    code = _Code(address)
    _scan(code, 0x80, side=True)
    code.label("native")
    code.emit(row["first_word"], branch(address + (len(code.words) + 1) * 4, row["address"] + 4))
    code.label("refuse")
    code.emit(0x38600000 | row["refusal_state"], 0x4E800020)
    return code.finish()


def _colo_guard(address, native, flag, refresh):
    code = _Code(address)
    code.emit(0x9421FFF0, 0x7C0802A6, 0x90010014, 0x90610008)
    _load(code, 12, flag)
    code.emit(0x39600000, 0x916C0000)  # reset only this menu's transient message flag
    _scan(code, 0x78)
    code.label("native")
    code.emit(0x80610008, 0x80010014, 0x7C0803A6, 0x38210010)
    code.emit(branch(address + len(code.words) * 4, native))
    code.label("refuse")
    code.emit(0x39600001, 0x916C0000)
    code.call(refresh)
    code.emit(0x38600001, 0x80010014, 0x7C0803A6, 0x38210010, 0x4E800020)
    return code.finish()


def _refusal_message(address, continuation, flag, original_word, identifier):
    code = _Code(address)
    # This is an inline instruction replacement, not a function-call boundary.
    # Keep every original register except r0 and restore the condition register.
    code.emit(0x9421FFF0, 0x91610008, 0x7D600026, 0x9161000C)
    _load(code, 11, flag)
    code.emit(0x816B0000, 0x280B0000)
    code.conditional(0x41820000, "native")
    _load(code, 0, identifier)
    code.jump("done")
    code.label("native")
    code.emit(original_word)
    code.label("done")
    code.emit(0x8161000C, 0x7D6FF120, 0x81610008, 0x38210010)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return code.finish()


def install_fairy_transfer(original_dol, current_dol, game_id, *,
                           message_refresh_address=None, refusal_message_id=None,
                           enabled=True):
    if type(enabled) is not bool:
        raise ValueError("Fairy transfer enablement must be a boolean")
    if not enabled:
        return current_dol, {"enabled": False, "version": VERSION}
    qualify_fairy_runtime(original_dol, game_id)
    xd = game_id.startswith("GXX")
    row = _QUALIFIED[game_id]
    if hashlib.sha256(_read(original_dol, row["address"], row["size"])).hexdigest() != row["sha256"]:
        raise FormatError("Unqualified native GBA trade selection")
    if not xd:
        if (type(message_refresh_address) is not int or not 0x80000000 <= message_refresh_address < 0x81800000
                or message_refresh_address & 3 or type(refusal_message_id) is not int
                or not 0xF0000 <= refusal_message_id <= 0xFFFFF):
            raise FormatError("Colosseum GBA refusal requires its localized message refresh and private ID")
        if hashlib.sha256(_read(original_dol, row["native_getter"], 24)).hexdigest() != row["native_getter_sha256"]:
            raise FormatError("Unqualified native Pokémon selection getter")
        sites = ((row["call_address"], row["call_word"]), (row["message_address"], row["message_word"]))
    else:
        sites = ((row["address"], row["first_word"]),)
    for address, word in sites:
        if _read(current_dol, address, 4) != struct.pack(">I", word):
            raise FormatError("GBA trade guard instruction window is already modified")
    offset, ram, setter, store, arena = _reservation(original_dol, current_dol, game_id)
    output, hooks = bytearray(current_dol[:offset]), []
    flag = None
    if not xd:
        flag = ram + len(arena)
        arena.extend(bytes(32))
    for index, (address, _word) in enumerate(sites):
        stub = ram + len(arena)
        if xd:
            payload = _xd_guard(stub, row)
        elif index == 0:
            payload = _colo_guard(stub, row["native_getter"], flag, message_refresh_address)
        else:
            payload = _refusal_message(stub, address + 4, flag, row["message_word"], refusal_message_id)
        arena.extend(payload)
        struct.pack_into(">I", output, _offset(original_dol, address), branch(address, stub, link=not xd and index == 0))
        hooks.append({"address": address, "stub": stub, "bytes": len(payload)})
    end = ram + len(arena)
    if end >= 0x81700000:
        raise FormatError("GBA trade guard exceeds owned memory")
    arena[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(arena)
    setter_offset = _offset(original_dol, setter)
    for position, value in ((8, offset), (0x50, ram), (0x98, len(arena)), (setter_offset, branch(setter, ram))):
        struct.pack_into(">I", output, position, value)
    permitted = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (offset, offset + 32), (setter_offset, setter_offset + 4)]
    permitted += [(_offset(original_dol, address), _offset(original_dol, address) + 4) for address, _ in sites]
    if any(a != b and not any(lo <= i < hi for lo, hi in permitted)
           for i, (a, b) in enumerate(zip(current_dol, output))):
        raise FormatError("GBA trade guard changed an unrelated executable byte")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if section["offset"] + section["size"] != len(output):
        raise FormatError("GBA trade guard reservation failed readback")
    return bytes(output), {"version": VERSION, "enabled": True, "hooks": hooks,
        "rejected_move_ids": list(range(FIRST_MOVE, LAST_MOVE + 1)),
        "native_refusal_state": row["refusal_state"] if xd else 7,
        "refusal_message_id": None if xd else refusal_message_id,
        "eligible_trades_use_original_flow": True, "local_pokemon_unchanged": True,
        "no_bad_egg_shadow_or_item_flags_written": True,
        "native_selection_cancel_and_return_preserved": True,
        "runtime_gba_link_validation": "not performed"}


_QUALIFIED = {'GC6P01': {'address': 2147683048,
            'size': 1040,
            'sha256': '4767b3daa951b66c9913b98d00e8223a4677bee9660606d58146151a7bd34b64',
            'call_address': 2147683440,
            'native_getter': 2148673580,
            'native_getter_sha256': '5159397dfc7eb851802f8ffed95601d1c7043938ede0acb27ffe356a9043dfc9',
            'message_address': 2147683504,
            'message_word': 939541694,
            'call_word': 1208949693},
 'GC6E01': {'address': 2147675764,
            'size': 1040,
            'sha256': '632c1bee05fe4f0a071e8ea5c6472aec9dc90d102c2a1f8de4366e37ad7b3f27',
            'call_address': 2147676156,
            'native_getter': 2148657232,
            'native_getter_sha256': '5159397dfc7eb851802f8ffed95601d1c7043938ede0acb27ffe356a9043dfc9',
            'message_address': 2147676220,
            'message_word': 939541694,
            'call_word': 1208940629},
 'GC6J01': {'address': 2147674108,
            'size': 956,
            'sha256': 'a1dacdeeb23128e6577701340021f4aa29b6bc5668f453f6303bb9c89f253a51',
            'call_address': 2147674448,
            'native_getter': 2148646920,
            'native_getter_sha256': '5159397dfc7eb851802f8ffed95601d1c7043938ede0acb27ffe356a9043dfc9',
            'message_address': 2147674512,
            'message_word': 939541694,
            'call_word': 1208932025},
 'GXXP01': {'address': 2148131404,
            'size': 272,
            'sha256': '591ef79dae881d2b849ddd647910b55bc5f3dcb396d80ecc75cb99a8a7468944',
            'first_word': 2485256176,
            'refusal_state': 5},
 'GXXE01': {'address': 2148127636,
            'size': 272,
            'sha256': '52de01a7e73d0b4c1c708b23739e6e716a5bb4785e97604dbbca12bacddc00e6',
            'first_word': 2485256176,
            'refusal_state': 5},
 'GXXJ01': {'address': 2148115336,
            'size': 272,
            'sha256': '8a026290dccc7317bc775ca37ce2518f82a9574a3ef3a446d2192477e7df468d',
            'first_word': 2485256176,
            'refusal_state': 5}}
