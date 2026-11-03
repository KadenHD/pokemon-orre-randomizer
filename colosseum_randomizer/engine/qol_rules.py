"""Qualified battle-EXP and heart-gauge reductions for the three rev-0 DOLs.

The battle hook scales the final award once, before the native normal/Shadow
split. The purification hook scales negative deltas immediately before the
native addition and zero clamp. Initial EXP, saves, flags and evolution are
not rewritten. Appended code uses the gift/shiny text2 arena reservation.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import struct

from .analyze_game import FormatError, parse_dol
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .shiny_rules import _Code

VERSION = "battle-exp-and-purification-v1"
EXPERIENCE_DIVISOR = 10000
MAX_NATIVE_AWARD = 65535
# Function identities were independently matched as complete normalized
# instruction sequences, then hashed without normalization in each retail DOL.
CONTRACTS = {
    "GC6P01": {
        "purification": (0x80123A84, 0x2BC, "81e75614940b8048207f69f3bbb2fccb3f79e5ce605bdd2106bd5fa6a5af8c95"),
        "experience": (0x80227DF4, 0x730, "24aa1154bd62a948805a7048e75483d0da61b7246b571cbbb80df1629b014da4"),
    },
    "GC6E01": {
        "purification": (0x8011F910, 0x2BC, "7215e042a8d62ba664c8bbf9c8e5267b5f1b2c8ab4248082c09d071af331f06a"),
        "experience": (0x802232F4, 0x730, "2f031d3530e79470e06b10f9e7bfd49a3ae7216439fc16e5d26a10325bcada6d"),
    },
    "GC6J01": {
        "purification": (0x8011D0C8, 0x2BC, "026818ceb2452d170098a3ccccad61f9381153a693d5b5b35fe81ffe5f1e4d52"),
        "experience": (0x8021EA8C, 0x730, "cf0967e54606c0bc3890e724be9790fe6c90210e5fcb985a220e7b5c2878ebb3"),
    },
}
HOOKS = {"experience": (0x35C, 0x7EE3BB78), "purification": (0x25C, 0xEC20F82A)}


def _word(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def experience_numerator(multiplier) -> int:
    if type(multiplier) not in (int, float):
        raise ValueError("experience multiplier must be a finite number from 0.25 to 5")
    try:
        value = Decimal(str(multiplier))
        if not value.is_finite() or not Decimal("0.25") <= value <= 5:
            raise ValueError("experience multiplier must be a finite number from 0.25 to 5")
        return int((value * EXPERIENCE_DIVISOR).to_integral_value(rounding=ROUND_HALF_UP))
    except InvalidOperation as error:
        raise ValueError("invalid experience multiplier") from error


def _experience_stub(address: int, continuation: int, numerator: int) -> bytes:
    """Inline trampoline: live r16 award, displaced mr r3,r23, no call/LR write.

    Native rev-0 species yield at most 255 base EXP. Even at level 100 and
    three 1.5x native bonuses the per-recipient award is below 65535. The
    defensive cap therefore has no effect on supported native awards, and
    guarantees multiplication/rounding cannot overflow u32 at the 5x maximum.
    r11/r12 and CR0 are dead across the following native call; all other live
    registers, FPRs, the stack and LR remain untouched except intended r16/r3.
    """
    c = _Code(address)
    c.emit(0x2810FFFF)  # cmplwi r16,65535
    c.conditional(0x40810000, "bounded")  # ble
    c.emit(0x3A000000, 0x6210FFFF)  # li r16,0; ori r16,r16,65535
    c.label("bounded")
    c.emit(0x3D600000 | (numerator >> 16), 0x616B0000 | (numerator & 0xFFFF),
           0x7D7059D6,  # mullw r11,r16,r11
           0x396B1388,  # addi r11,r11,5000 (nearest integer, ties upward)
           0x39802710,  # li r12,10000
           0x7E0B6396,  # divwu r16,r11,r12
           0x2C100000)  # cmpwi r16,0
    c.conditional(0x40820000, "positive")
    c.emit(0x3A000001)  # native positive award remains at least 1
    c.label("positive")
    c.emit(0x7EE3BB78)  # displaced mr r3,r23
    c.emit(branch(address + len(c.words) * 4, continuation))
    return c.finish()


def _purification_stub(address: int, continuation: int, multiplier: int) -> bytes:
    """Scale only a negative f31 delta; retain positive deltas and zero.

    Native f31 save/restore surrounds this point. f0 is the old gauge; f1 is
    the destination and already volatile. r12 has no live use before return.
    The subsequent native fcmpo overwrites CR0 before any conditional branch.
    """
    constants = address + 64
    c = _Code(address)
    c.emit(0x3D800000 | (constants >> 16), 0x618C0000 | (constants & 0xFFFF),
           0xC02C0000,  # lfs f1,0(r12): zero
           0xFC1F0800)  # fcmpu cr0,f31,f1
    c.conditional(0x40800000, "add")  # bge: no acceleration of gauge increases
    c.emit(0xC02C0004, 0xEFFF0072)  # load multiplier; fmuls f31,f31,f1
    c.label("add")
    c.emit(0xEC20F82A)  # displaced fadds f1,f0,f31
    c.emit(branch(address + len(c.words) * 4, continuation))
    payload = c.finish()
    if len(payload) != 64:
        raise AssertionError("purification constant relocation changed")
    return payload + struct.pack(">ff", 0.0, float(multiplier)) + bytes(24)


def apply_qol_rules(original: bytes, current: bytes, options) -> tuple[bytes, dict]:
    requested_exp = getattr(options, "experience_multiplier", 1.0)
    numerator = experience_numerator(requested_exp)
    purification = getattr(options, "purification_multiplier", 1)
    if type(purification) is not int or not 1 <= purification <= 10:
        raise ValueError("purification multiplier must be an integer from 1 to 10")
    enabled = [key for key, active in (("experience", numerator != EXPERIENCE_DIVISOR),
                                       ("purification", purification != 1)) if active]
    report = {"version": VERSION, "enabled": bool(enabled),
              "experience_multiplier": requested_exp, "purification_multiplier": purification}
    if not enabled:
        return current, report
    region = dol_layout(original)
    if len(current) < len(original):
        raise FormatError("quality-of-life hooks received a truncated DOL")
    for offset in range(0, 0x100, 4):
        if offset not in (0x08, 0x50, 0x98) and current[offset:offset + 4] != original[offset:offset + 4]:
            raise FormatError("quality-of-life hooks received an unsupported DOL header")
    if any(_word(original, offset) for offset in (0x08, 0x50, 0x98)):
        raise FormatError("original DOL text2 slot is occupied")
    section_offset = (len(original) + 31) // 32 * 32
    previous_size = _word(current, 0x98)
    if previous_size:
        if ((_word(current, 0x08), _word(current, 0x50)) != (section_offset, region.section_ram)
                or section_offset + previous_size != len(current) or previous_size % 32
                or current[section_offset:section_offset + 32] != _arena_guard(region.section_ram + previous_size, region.arena_lo_store)
                or _word(current, region.set_arena_lo - TEXT_TO_RAM) != branch(region.set_arena_lo, region.section_ram)):
            raise FormatError("unsupported existing DOL reservation before quality-of-life hooks")
        code = bytearray(current[section_offset:])
    else:
        if (len(current) != len(original) or any(_word(current, o) for o in (0x08, 0x50))
                or _word(current, region.set_arena_lo - TEXT_TO_RAM) != region.arena_lo_store):
            raise FormatError("unexpected DOL layout before quality-of-life reservation")
        code = bytearray(32)
    original_descriptor = parse_dol(original)
    if original_descriptor["bss_ram_address"] + original_descriptor["bss_size"] >= region.section_ram:
        raise FormatError("native BSS overlaps quality-of-life code reservation")
    hooks = []
    for key in enabled:
        base, size, expected_hash = CONTRACTS[region.game_id][key]
        offset = base - TEXT_TO_RAM
        for data in (original, current):
            if hashlib.sha256(data[offset:offset + size]).hexdigest() != expected_hash:
                raise FormatError(f"native {key} function signature changed")
        delta, word = HOOKS[key]
        address = base + delta
        if _word(current, address - TEXT_TO_RAM) != word:
            raise FormatError(f"native {key} hook preimage changed")
        stub = region.section_ram + len(code)
        payload = (_experience_stub(stub, address + 4, numerator) if key == "experience"
                   else _purification_stub(stub, address + 4, purification))
        code.extend(payload)
        hooks.append({"key": key, "native_function": base, "function_size": size,
                      "native_function_sha256": expected_hash, "hook_address": address,
                      "original_word": word, "stub_address": stub, "stub_size": len(payload),
                      "continuation": address + 4})
    reserved_end = region.section_ram + len(code)
    if reserved_end % 32 or reserved_end >= 0x81700000:
        raise FormatError("quality-of-life code exceeds the supported arena reservation")
    code[:32] = _arena_guard(reserved_end, region.arena_lo_store)
    output = bytearray(current[:section_offset])
    output.extend(bytes(section_offset - len(output)))
    output.extend(code)
    ranges = [(0x08, 0x0C), (0x50, 0x54), (0x98, 0x9C),
              (region.set_arena_lo - TEXT_TO_RAM, region.set_arena_lo - TEXT_TO_RAM + 4),
              (section_offset, section_offset + 32), (len(current), len(output))]
    for offset, value in ((0x08, section_offset), (0x50, region.section_ram), (0x98, len(code)),
                          (region.set_arena_lo - TEXT_TO_RAM, branch(region.set_arena_lo, region.section_ram))):
        struct.pack_into(">I", output, offset, value)
    for hook in hooks:
        offset = hook["hook_address"] - TEXT_TO_RAM
        struct.pack_into(">I", output, offset, branch(hook["hook_address"], hook["stub_address"]))
        ranges.append((offset, offset + 4))
    if any(a != b and not any(lo <= index < hi for lo, hi in ranges)
           for index, (a, b) in enumerate(zip(current, output))):
        raise FormatError("quality-of-life patch exceeded its exact whitelist")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if (section["offset"], section["ram_address"], section["size"]) != (section_offset, region.section_ram, len(code)):
        raise FormatError("quality-of-life code section failed readback")
    report.update(game_id=region.game_id, hooks=hooks,
        experience_fixed_point={"numerator": numerator, "denominator": EXPERIENCE_DIVISOR,
            "rounding": "nearest integer, ties upward; positive awards remain at least 1",
            "defensive_native_award_cap": MAX_NATIVE_AWARD},
        code_section={"offset": section_offset, "address": region.section_ram,
                      "size": len(code), "previous_size": previous_size, "reserved_end": reserved_end},
        allowed_changed_ranges=ranges, outside_whitelist_unchanged=True,
        native_level_up_and_purification_zero_clamp_preserved=True,
        initial_exp_rare_candy_and_stored_exp_release_unchanged=True,
        purification_only_negative_deltas_scaled=True,
        runtime_validation="Requires actual battle EXP and heart-gauge reduction under Dolphin.")
    return bytes(output), report
