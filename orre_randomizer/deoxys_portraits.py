"""Per-specimen Colosseum Deoxys faces, composed with existing appearance hooks."""
from __future__ import annotations

import struct

from .castform_portraits import _reservation
from .deoxys_resources import FACE_RESOURCES, FORMS
from .deoxys_identity import FORM_OFFSETS, FORM_TAG
from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .engine.postgame_lugia_face import _LAYOUTS
from .engine.shiny_rules import _Code

VERSION = "colosseum-saved-deoxys-portraits-v1"
FIRST_KEY = 0x7FC0


def _identity_stub(address, fallback, record_register):
    if record_register not in (27, 28, 30):
        raise FormatError("unknown native Deoxys face context")
    code = _Code(address)
    # These are full native CK3 contexts, not copied 0x30-byte MenuStatus rows.
    code.emit(0x3D608000, 0x7C005840 | record_register << 16)
    code.conditional(0x41800000, "native")
    code.emit(0x3D60817F, 0x616BFEC8, 0x7C005840 | record_register << 16)
    code.conditional(0x41810000, "native")
    code.emit(0x540007BE | record_register << 21, 0x28000000)
    code.conditional(0x40820000, "native")
    code.emit(0xA0000000 | record_register << 16, 0x2800019A)
    code.conditional(0x40820000, "native")
    code.emit(0xA1600000 | record_register << 16 | FORM_OFFSETS['colosseum'],
              0x5560003A, 0x28000000 | FORM_TAG)
    code.conditional(0x40820000, "native")
    code.emit(0x556B07BE)  # validated saved form tag & 3; the PID stays untouched
    for index in range(1, 4):
        code.emit(0x280B0000 | index)
        code.conditional(0x41820000, "form" + str(index))
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, fallback))
    for index in range(1, 4):
        code.label("form" + str(index))
        code.emit(0x38600000 | (FIRST_KEY + 2 * (index - 1)),
                  0x7C633214, 0x4E800020)  # add rare atlas row, preserving native r6
    return code.finish()


def _descriptor_stub(address, fallback, *, crop=False, replay=False):
    code = _Code(address)
    for index, form in enumerate(FORMS):
        for shiny in (False, True):
            key = FIRST_KEY + 2 * index + shiny
            code.emit(0x28030000 | key)
            code.conditional(0x41820000, "key" + str(key))
    if replay:
        code.emit(0x9421FFF0)
    code.emit(branch(address + len(code.words) * 4, fallback))
    for index, form in enumerate(FORMS):
        for shiny in (False, True):
            code.label("key" + str(FIRST_KEY + 2 * index + shiny))
            if crop:
                code.emit(0x38600000 | int(shiny))
            else:
                resource = FACE_RESOURCES[form]
                code.emit(0x3C600000 | resource >> 16, 0x60630000 | resource & 0xFFFF)
            code.emit(0x4E800020)
    return code.finish()


def _previous_target(word, original_word, address, native_target, ram, size, *, link):
    if word == original_word:
        return native_target
    if word & 0xFC000003 != 0x48000000 | int(link):
        raise FormatError("modified native Deoxys portrait hook")
    displacement = word & 0x03FFFFFC
    target = address + displacement - (0x4000000 if displacement & 0x2000000 else 0)
    if not ram + 32 <= target < ram + size:
        raise FormatError("unowned native Deoxys portrait hook")
    return target


def install_deoxys_portraits(original, current, game_id):
    """Route native instance-face requests by stored form without editing PIDs."""
    region = dol_layout(original)
    if region.game_id != game_id or game_id not in _LAYOUTS:
        raise FormatError("unknown Colosseum Deoxys portrait executable")
    offset, ram, setter, store, code = _reservation(original, current, game_id)
    calls, descriptor, crop, getter = _LAYOUTS[game_id]
    builders = []
    for index, call in enumerate(calls):
        species_register = (31, 29, 31, 26, 29)[index // 2]
        result = (0x5463043E, 0x5460043E, 0x5463043E, 0x547E043E, 0x547D043E)[index // 2]
        expected = (0x7C040378 | species_register << 21 | species_register << 11,
                    0x38600000, 0x38A0005B, 0x38C00000 | index % 2,
                    branch(call, getter, link=True), result)
        pos = call - TEXT_TO_RAM
        if (struct.unpack_from(">6I", original, pos - 16) != expected
                or struct.unpack_from(">4I", current, pos - 16) != expected[:4]
                or u32(current, pos + 4) != result):
            raise FormatError("unexpected native Deoxys instance-face request")
        fallback = _previous_target(u32(current, pos), expected[4], call, getter,
                                    ram, len(code), link=True)
        register = (28, 28, 30, 27, 28)[index // 2]
        builders.append((call, True, lambda a, f=fallback, r=register: _identity_stub(a, f, r)))
    prefix = bytes.fromhex("9421fff07c0802a690010014808d8650")
    for hook, is_crop in ((descriptor, False), (crop, True)):
        pos = hook - TEXT_TO_RAM
        if (original[pos:pos + len(prefix)] != prefix
                or current[pos + 4:pos + len(prefix)] != prefix[4:]):
            raise FormatError("unexpected native Deoxys face descriptor")
        original_word = u32(original, pos)
        replay = u32(current, pos) == original_word
        fallback = _previous_target(u32(current, pos), original_word, hook, hook + 4,
                                    ram, len(code), link=False)
        builders.append((hook, False, lambda a, f=fallback, c=is_crop, r=replay:
                         _descriptor_stub(a, f, crop=c, replay=r)))
    output = bytearray(current[:offset])
    hooks = []
    for hook, link, builder in builders:
        stub = ram + len(code)
        payload = builder(stub)
        code.extend(payload)
        struct.pack_into(">I", output, hook - TEXT_TO_RAM, branch(hook, stub, link=link))
        hooks.append({"address": hook, "stub": stub, "bytes": len(payload)})
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Deoxys portrait adapters exceed the owned arena")
    code[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                       (setter - TEXT_TO_RAM, branch(setter, ram))):
        struct.pack_into(">I", output, pos, value)
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (offset, offset + 32),
               (setter - TEXT_TO_RAM, setter - TEXT_TO_RAM + 4)]
    allowed.extend((h["address"] - TEXT_TO_RAM, h["address"] - TEXT_TO_RAM + 4) for h in hooks)
    if any(a != b and not any(lo <= at < hi for lo, hi in allowed)
           for at, (a, b) in enumerate(zip(current, output))):
        raise FormatError("Deoxys face patch modified unrelated executable bytes")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if (section["offset"], section["ram_address"], section["size"]) != (offset, ram, len(code)):
        raise FormatError("Deoxys face adapter readback failed")
    return bytes(output), {"version": VERSION, "game_id": game_id, "hooks": hooks,
        "form_source": "saved reserved form tag", "first_virtual_key": FIRST_KEY,
        "resources": dict(FACE_RESOURCES), "saved_identity_unchanged": True,
        "normal_form_unchanged": True, "unrelated_executable_bytes_preserved": True}
