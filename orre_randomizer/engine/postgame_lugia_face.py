"""Native two-dimensional faces for Colosseum's actual Shadow Lugia specimens.

Virtual display keys keep the original Lugia face and save data unchanged.
Both keys resolve to one native atlas, whose bottom frame is the white shiny.
Both derived frames use an opaque black matte behind the original silhouette;
the native outer Shadow-status frame is unchanged.
"""
from __future__ import annotations

import struct

from .analyze_game import FormatError
from .gift_move_hooks import TEXT_TO_RAM, branch
from .shadow_lugia_face import COLOSSEUM_RESOURCE
from .shiny_rules import _Code

NORMAL_KEY, SHINY_KEY = 0x7FF1, 0x7FF2
_LAYOUTS = {
    # Five ordinary/shiny pairs: requests, callback, sprite, draw and battle.
    "GC6P01": ((0x8010E734, 0x8010E750, 0x8010E8B8, 0x8010E8D4,
                 0x8010F2C0, 0x8010F2DC, 0x8010EE28, 0x8010EE44,
                 0x8010E554, 0x8010E570), 0x8010FA14, 0x8010F9A0, 0x8012A580),
    "GC6E01": ((0x8010B11C, 0x8010B138, 0x8010B2A0, 0x8010B2BC,
                 0x8010BCA8, 0x8010BCC4, 0x8010B810, 0x8010B82C,
                 0x8010AF3C, 0x8010AF58), 0x8010C3FC, 0x8010C388, 0x8012640C),
    "GC6J01": ((0x80108AF8, 0x80108B14, 0x80108C7C, 0x80108C98,
                 0x80109684, 0x801096A0, 0x801091EC, 0x80109208,
                 0x80108918, 0x80108934), 0x80109DD8, 0x80109D64, 0x80123BAC),
}


def _identity(address, native, register, *, keep_after_purification=False):
    code = _Code(address)
    code.emit(0x28000000 | register << 16)  # cmplwi original CK3, 0
    code.conditional(0x41820000, "native")
    code.emit(0xA0000000 | register << 16, 0x280000F9)
    code.conditional(0x40820000, "native")
    code.emit(0xA00000D8 | register << 16, 0x28000000)
    code.conditional(0x41820000, "native")
    code.emit(0x28000061)
    code.conditional(0x40800000, "native")
    if not keep_after_purification:
        code.emit(0x800000DC | register << 16, 0x2C00FF9C)
        code.conditional(0x41820000, "native")
    code.emit(0x38600000 | NORMAL_KEY, 0x28060000)
    code.conditional(0x41820000, "return")
    code.emit(0x38600000 | SHINY_KEY)
    code.label("return")
    code.emit(0x4E800020)
    code.label("native")
    code.emit(branch(address + len(code.words)*4, native))
    return code.finish()


def _descriptor(address, continuation, *, crop=False):
    code = _Code(address)
    for key in (NORMAL_KEY, SHINY_KEY):
        code.emit(0x28030000 | key)
        code.conditional(0x41820000, "variant" + str(key))
    code.emit(0x9421FFF0)  # replay native prologue, preserving the caller's LR
    code.emit(branch(address + len(code.words)*4, continuation))
    for key in (NORMAL_KEY, SHINY_KEY):
        code.label("variant" + str(key))
        if crop:
            code.emit(0x38600000 | int(key == SHINY_KEY))
        else:
            code.emit(0x3C600000 | COLOSSEUM_RESOURCE >> 16,
                      0x60630000 | COLOSSEUM_RESOURCE & 0xFFFF)
        code.emit(0x4E800020)
    return code.finish()


def native_face_hooks(original, current, game_id, *, keep_after_purification=False):
    """Check retail call windows before returning narrowly scoped hook builders."""
    calls, texture, crop, getter = _LAYOUTS[game_id]
    hooks = []
    for index, call in enumerate(calls):
        species_register = (31, 29, 31, 26, 29)[index // 2]
        result = (0x5463043E, 0x5460043E, 0x5463043E, 0x547E043E, 0x547D043E)[index // 2]
        expected = (0x7C040378 | species_register << 21 | species_register << 11, 0x38600000, 0x38A0005B,
                    0x38C00000 | index % 2, branch(call, getter, link=True), result)
        for data in (original, current):
            if struct.unpack_from(">6I", data, call-TEXT_TO_RAM-16) != expected:
                raise FormatError("unexpected native Colosseum face-key call")
        register = (28, 28, 30, 27, 28)[index // 2]
        hooks.append((call, lambda address, reg=register: _identity(address, getter, reg,
                           keep_after_purification=keep_after_purification), True))
    prefix = bytes.fromhex("9421fff07c0802a690010014808d8650")
    for hook, is_crop in ((texture, False), (crop, True)):
        for data in (original, current):
            if data[hook-TEXT_TO_RAM:hook-TEXT_TO_RAM+len(prefix)] != prefix:
                raise FormatError("unexpected native Colosseum face descriptor")
        hooks.append((hook, lambda address, h=hook, c=is_crop: _descriptor(address, h+4, crop=c), False))
    return hooks
