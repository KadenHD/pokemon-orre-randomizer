"""Live Castform HUD portraits using native models, texture loading and rarity.

MenuStatus is copied as 0x30 bytes by both games. Its three padding bytes carry
an aligned MEM1 pointer; byte 0x2d remains the game's own animation flag. Only
the battle converter installs this transient pointer, never Pokemon/save data.
The HUD follows the currently loaded model, including suppressed weather and
the return to normal. Native asynchronous loading keeps disc IO off the draw
thread's wait path. The original face remains visible while a request is pending.
"""
from __future__ import annotations

import hashlib
import struct
from collections.abc import Mapping

from .castform_layouts import LAYOUTS
from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .engine.shiny_rules import _Code

VERSION = "castform-live-hud-v2"
NORMAL_FACE, SHINY_FACE = 360, 746
FIRST_FACE = 0x7F10
# Loaded PKX IDs, not weather/type assumptions. Order: sun, rain, hail.
MODELS = (415, 414, 416)
RESOURCES = {"colosseum": (0x0F671200, 0x0F691200, 0x0F681200),
             "xd": (0x0E9D1200, 0x0E9F1200, 0x0E9E1200)}


def _load(code, register, value):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | value & 0xFFFF)


def _status_stub(address, continuation, displaced, *, fight, xd):
    code = _Code(address)
    if xd:
        code.emit(displaced)  # Native item store or animation-flag store.
    status, pokemon = ((29, 28) if xd else (31, 30)) if fight else (30, 0)
    if fight:
        # (pointer >> 2) & 0xffffff; MEM1's 0x80000000 prefix is implicit.
        code.emit(0x54000000 | pokemon << 21 | 11 << 16 | 30 << 11 | 8 << 6 | 31 << 1,
                  0x5560843E,                       # srwi r0,r11,16
                  0x9800002C | status << 16,         # stb r0,0x2c(status)
                  0xB160002E | status << 16)         # sth r11,0x2e(status)
    else:
        code.emit(0x38000000, 0x9800002C | status << 16,
                  0xB000002E | status << 16)
    if not xd:
        code.emit(displaced)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return code.finish()


def _draw_stub(address, native, layout, *, xd):
    code = _Code(address)
    status = 28 if xd else 30
    code.emit(0x9421FFD0, 0x7C0802A6, 0x90010034,
              0x90610008, 0x9081000C, 0x90A10010)  # Save the three native draw args.
    for face in (NORMAL_FACE, SHINY_FACE):
        code.emit(0x28050000 | face)
        code.conditional(0x41820000, "castform")
    code.jump("native")
    code.label("castform")
    code.emit(0x8960002C | status << 16, 0x556B803E,  # lbz; slwi r11,16
              0xA000002E | status << 16, 0x7D6B0378, 0x280B0000)
    code.conditional(0x41820000, "native")
    code.emit(0x556B103A, 0x656B8000)  # slwi r11,2; oris r11,0x8000
    _load(code, 0, 0x80010000)
    code.emit(0x7C0B0040)  # cmplw r11,r0
    code.conditional(0x41800000, "native")
    _load(code, 0, 0x817FF800)  # Leave room for either native FightOut structure.
    code.emit(0x7C0B0040)
    code.conditional(0x40800000, "native")
    code.emit(0x7D635B78)  # mr r3,r11
    code.call(layout["sequence_get"])
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    code.call(layout["sequence_id"])
    for index, model in enumerate(MODELS):
        code.emit(0x28030000 | model)
        code.conditional(0x41820000, f"form{index}")
    code.jump("native")
    for index in range(3):
        code.label(f"form{index}")
        code.emit(0x38600000 | FIRST_FACE + 2 * index)
        code.jump("rarity")
    code.label("rarity")
    code.emit(0x80010010, 0x28000000 | SHINY_FACE)
    code.conditional(0x40820000, "request")
    code.emit(0x38630001)
    code.label("request")
    code.emit(0x90610014)
    code.call(layout["ready"])
    code.emit(0x2C030001)
    code.conditional(0x41820000, "ready")
    code.emit(0x2C030000)
    code.conditional(0x40800000, "native")  # Already pending: no duplicate request.
    code.emit(0x80610014, 0x38800000, 0x38A00000)
    code.call(layout["load"])
    code.jump("native")
    code.label("ready")
    code.emit(0x80010014, 0x90010010)
    code.label("native")
    code.emit(0x80610008, 0x8081000C, 0x80A10010)
    code.call(native)
    code.emit(0x80010034, 0x7C0803A6, 0x38210030, 0x4E800020)
    return code.finish()


def _shiny_resources(resources):
    if resources is None:
        return None
    native = {value for values in RESOURCES.values() for value in values}
    if (not isinstance(resources, Mapping) or set(resources) != set(MODELS)
            or any(type(value) is not int or not 0 < value <= 0xFFFFFFFF
                   or value & 0xFFFF != 0x1200 or value in native for value in resources.values())
            or len(set(resources.values())) != 3):
        raise FormatError("three distinct authored Castform shiny face resources are required")
    return dict(resources)


def _descriptor_stub(address, fallback, *, game, replay, crop=False, shiny_resources=None):
    shiny_resources = _shiny_resources(shiny_resources)
    def resource(index):
        return (shiny_resources[MODELS[index // 2]] if shiny_resources is not None and index % 2
                else RESOURCES[game][index // 2])

    code = _Code(address)
    for index in range(6):
        code.emit(0x28030000 | FIRST_FACE + index)
        code.conditional(0x41820000, f"face{index}")
    if replay:
        code.emit(0x9421FFF0)
    code.emit(branch(address + len(code.words) * 4, fallback))
    references = []
    for index in range(6):
        code.label(f"face{index}")
        if game == "xd":
            references.append((len(code.words), index))
            _load(code, 3, 0)  # Filled with the immutable native-format record below.
        else:
            _load(code, 3, index % 2 if crop else resource(index))
        code.emit(0x4E800020)
    payload = bytearray(code.finish())
    if game == "xd":
        table = address + len(payload)
        for word, index in references:
            value = table + index * 8
            struct.pack_into(">II", payload, word * 4, 0x3C600000 | value >> 16,
                             0x60630000 | value & 0xFFFF)
        payload.extend(b"".join(struct.pack(">II", 0xC0000000 if i % 2 else 0x40000000,
                                          resource(i)) for i in range(6)))
        payload.extend(bytes(-len(payload) % 32))
    return bytes(payload)


def _reservation(original, current, game_id):
    text_base = 0x800030A0 if game_id.startswith("GXX") else TEXT_TO_RAM
    if game_id.startswith("GC6"):
        region = dol_layout(original)
        ram, setter, store = region.section_ram, region.set_arena_lo, region.arena_lo_store
    else:
        from .xd_battle_rules import ARENA
        ram, setter, store = ARENA[game_id]
    offset = (len(original) + 31) & ~31
    size = u32(current, 0x98)
    header = (8, 0x50, 0x98)
    if (len(current) < len(original) or any(u32(original, p) for p in header)
            or any(current[p:p + 4] != original[p:p + 4]
                   for p in range(0, 0x100, 4) if p not in header)
            or u32(original, setter - text_base) != store):
        raise FormatError("unexpected Castform DOL reservation")
    if size:
        if ((u32(current, 8), u32(current, 0x50)) != (offset, ram)
                or size % 32 or offset + size != len(current)
                or current[offset:offset + 32] != _arena_guard(ram + size, store)
                or u32(current, setter - text_base) != branch(setter, ram)):
            raise FormatError("invalid existing Castform DOL reservation")
        code = bytearray(current[offset:])
    else:
        if (len(current) != len(original) or u32(current, 8) or u32(current, 0x50)
                or u32(current, setter - text_base) != store):
            raise FormatError("invalid initial Castform DOL reservation")
        code = bytearray(32)
    descriptor = parse_dol(original)
    if (descriptor["bss_ram_address"] + descriptor["bss_size"] > ram
            or any(s["ram_address"] + s["size"] > ram for s in descriptor["sections"])):
        raise FormatError("Castform code overlaps native memory")
    return offset, ram, setter, store, code


def install_castform_portraits(original: bytes, current: bytes, game_id: str, *, shiny_resources=None):
    """Install against exact regional originals; compose with existing Lugia hooks."""
    layout = LAYOUTS.get(game_id)
    if not layout or hashlib.sha256(original).hexdigest() != layout["sha256"]:
        raise FormatError("unknown original Castform executable")
    shiny_resources = _shiny_resources(shiny_resources)
    offset, ram, setter, store, code = _reservation(original, current, game_id)
    xd = game_id.startswith("GXX")
    text_base = 0x800030A0 if xd else TEXT_TO_RAM
    game = "xd" if xd else "colosseum"
    descriptor_keys = {"descriptor", "crop"}
    previous = {}
    for key, signature in layout["signatures"].items():
        address = layout[key]
        pos = address - text_base
        expected = bytes.fromhex(signature)
        if original[pos:pos + len(expected)] != expected:
            raise FormatError("unexpected original Castform instruction window")
        observed = current[pos:pos + len(expected)]
        if observed == expected:
            previous[key] = (address + 4, True)
        elif key in descriptor_keys and observed[4:] == expected[4:]:
            word = u32(current, pos)
            delta = word & 0x3FFFFFC
            if delta & 0x2000000:
                delta -= 0x4000000
            target = address + delta
            if word & 0xFC000003 != 0x48000000 or not ram + 32 <= target < ram + len(code):
                raise FormatError("unowned Castform portrait hook chain")
            previous[key] = (target, False)
        else:
            raise FormatError("modified Castform instruction window")
    hooks = []
    output = bytearray(current[:offset])
    for key in ("generic_hook", "fight_hook", "draw_hook", "descriptor", "crop"):
        if not layout.get(key):
            continue
        address = layout[key]
        stub = ram + len(code)
        displaced = u32(original, address - text_base)
        if key in ("generic_hook", "fight_hook"):
            payload = _status_stub(stub, address + 4, displaced, fight=key == "fight_hook", xd=xd)
        elif key == "draw_hook":
            payload = _draw_stub(stub, layout["draw_native"], layout, xd=xd)
        else:
            fallback, replay = previous[key]
            payload = _descriptor_stub(stub, fallback, game=game, replay=replay, crop=key == "crop",
                                       shiny_resources=shiny_resources)
        code.extend(payload)
        struct.pack_into(">I", output, address - text_base,
                         branch(address, stub, link=key == "draw_hook"))
        hooks.append({"role": key, "address": address, "stub": stub, "bytes": len(payload)})
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Castform portrait code exceeds reserved memory")
    code[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                       (setter - text_base, branch(setter, ram))):
        struct.pack_into(">I", output, pos, value)
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C),
               (setter - text_base, setter - text_base + 4), (offset, offset + 32)]
    allowed.extend((hook['address'] - text_base, hook['address'] - text_base + 4) for hook in hooks)
    if any(before != after and not any(lo <= pos < hi for lo, hi in allowed)
           for pos, (before, after) in enumerate(zip(current, output))):
        raise FormatError("Castform patch changed an unrelated executable byte")
    added = next(s for s in parse_dol(output)['sections'] if s['name'] == 'text2')
    if (added['offset'], added['ram_address'], added['size']) != (offset, ram, len(code)):
        raise FormatError("Castform code section failed readback")
    return bytes(output), {"version": VERSION, "game_id": game_id, "hooks": hooks,
        "form_source": "currently loaded battle model", "native_async_loading": True,
        "native_animation_flag_preserved": True, "save_data_unchanged": True,
        "unrelated_executable_bytes_preserved": True,
        "authored_shiny_weather": shiny_resources is not None,
        "shiny_face_resources": {} if shiny_resources is None else {str(k): v for k, v in shiny_resources.items()}}
