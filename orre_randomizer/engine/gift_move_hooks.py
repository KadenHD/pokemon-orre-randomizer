"""Regional gift-only move hooks in an appended, arena-reserved DOL text section.

No code cave is reused. The native arena-low setter is clamped before OSInit's
ClearArena call, reserving the added code above the original stacks and BSS.
The original constructor, move setter, gift flags and event gates stay native.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, parse_dol
from .dol_regions import DolLayout, PAL, dol_layout, special_targets

ORIGINAL_DOL_SHA256 = "a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5"
TEXT_TO_RAM = 0x80003000
SECTION_RAM = 0x804E3CC0
ORIGINAL_STACK_TOP = 0x804DBCB8
ORIGINAL_BSS_END = 0x804CBCB8
NATIVE_CONSTRUCTOR = 0x80128238
NATIVE_SET_MOVE = 0x80127ECC
SET_ARENA_LO = 0x8009E4F0
GET_ARENA_LO = 0x8009E4E0
ARENA_LO_STORE = 0x906D8168
GIFT_BASES = {"plusle": 0x131BF4, "ho-oh": 0x131B10,
              "celebi-event": 0x1318E0, "pikachu-event": 0x1319F0}


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def branch(source: int, target: int, *, link: bool = False) -> int:
    displacement = target - source
    if displacement % 4 or not -(1 << 25) <= displacement < (1 << 25):
        raise FormatError("PowerPC hook branch target is out of range or unaligned")
    return 0x48000000 | (displacement & 0x03FFFFFC) | int(link)


def _branch_target(source: int, instruction: int) -> int:
    if instruction & 0xFC000003 != 0x48000001:
        raise FormatError("expected relative PowerPC bl")
    displacement = instruction & 0x03FFFFFC
    if displacement & (1 << 25):
        displacement -= 1 << 26
    return source + displacement


def _words(instructions: list[int]) -> bytes:
    return struct.pack(f">{len(instructions)}I", *instructions)


def _arena_guard(reserved_end: int, arena_lo_store: int = ARENA_LO_STORE) -> bytes:
    # r3 is preserved, r0 and CR0 are caller-volatile. Store max(r3, end).
    return _words([
        0x3C000000 | (reserved_end >> 16),        # lis r0, end@h
        0x60000000 | (reserved_end & 0xFFFF),     # ori r0, r0, end@l
        0x7C030040,                             # cmplw r3, r0
        0x4080000C,                             # bge store_argument
        arena_lo_store & ~(31 << 21),            # stw r0, arenaLo(r13)
        0x4E800020,                             # blr
        arena_lo_store,                         # stw r3, arenaLo(r13)
        0x4E800020,                             # blr
    ])


def _gift_stub(address: int, moves: list[int], *, region: DolLayout = PAL) -> bytes:
    instructions = [
        0x9421FFD0,             # stwu sp, -0x30(sp)
        0x7C0802A6,             # mflr r0
        0x90010034,             # stw r0, 0x34(sp)
        0x93C10028,             # stw r30, 0x28(sp)
        0x93E1002C,             # stw r31, 0x2c(sp)
        0x7C7F1B78,             # mr r31, r3 (original object argument)
    ]
    instructions.append(branch(address + len(instructions) * 4, region.native_constructor, link=True))
    instructions.append(0x7C7E1B78)  # mr r30, r3 (preserve constructor result)
    for slot, move in enumerate(moves):
        instructions.extend([
            0x7FE3FB78,         # mr r3, r31
            0x38800000 | slot,  # li r4, slot
            0x38A00000 | move,  # li r5, move
        ])
        instructions.append(branch(address + len(instructions) * 4, region.native_set_move, link=True))
    instructions.extend([
        0x7FC3F378,             # mr r3, r30
        0x83C10028,             # lwz r30, 0x28(sp)
        0x83E1002C,             # lwz r31, 0x2c(sp)
        0x80010034,             # lwz r0, 0x34(sp)
        0x7C0803A6,             # mtlr r0
        0x38210030,             # addi sp, sp, 0x30
        0x4E800020,             # blr
    ])
    payload = _words(instructions)
    return payload + _words([0x60000000] * ((-len(payload) % 32) // 4))


def _validate_original(original: bytes, current: bytes) -> DolLayout:
    region = dol_layout(original)
    if len(current) != len(original) or current[:0x100] != original[:0x100]:
        raise FormatError("gift hooks expect unchanged original DOL section layout before insertion")
    for offset in (0x08, 0x50, 0x98):  # unused text2 offset/address/size header slots
        if _u32(original, offset):
            raise FormatError("DOL text2 section slot is already occupied")
    descriptor = parse_dol(original)
    if descriptor["bss_ram_address"] + descriptor["bss_size"] != region.bss_end:
        raise FormatError("unexpected regional BSS boundary")
    if any(s["ram_address"] + s["size"] > region.bss_end for s in descriptor["sections"]):
        raise FormatError("native section overlaps proposed reserved code")
    # Each exact build has its own startup stack and default arena boundary.
    expected = {
        0x80003324: 0x3C200000 | (region.stack_top >> 16),
        0x80003328: 0x60210000 | (region.stack_top & 0xFFFF),
        region.arena_initialize: 0x3C600000 | (region.section_ram >> 16),
        region.arena_initialize + 4: 0x38630000 | (region.section_ram & 0xFFFF),
        region.set_arena_lo: region.arena_lo_store, region.set_arena_lo + 4: 0x4E800020,
        region.get_arena_lo: region.arena_lo_store - 0x10000000,
        region.get_arena_lo + 4: 0x4E800020,
        region.native_constructor: 0x9421FFD0, region.native_set_move: 0x9421FFE0,
    }
    for address, word in expected.items():
        offset = address - TEXT_TO_RAM
        if _u32(original, offset) != word or _u32(current, offset) != word:
            raise FormatError(f"native gift/arena hook signature changed at {address:#x}")
    # OSInit calls the setter before ClearArena; ClearArena reads the arena getter.
    checks = ((region.arena_initialize + 0xC, region.set_arena_lo),
              (region.arena_initialize + 0x48, region.set_arena_lo),
              (region.arena_initialize + 0x254, region.clear_arena),
              (region.clear_arena + 0x34, region.get_arena_lo),
              (region.clear_arena + 0x3C, region.get_arena_lo))
    for address, target in checks:
        if _branch_target(address, _u32(original, address - TEXT_TO_RAM)) != target:
            raise FormatError("OS arena initialization/clear control flow changed")
    return region


def patch_gift_moves(original_dol: bytes, current_dol: bytes,
                     moves_by_key: dict[str, list[int]]) -> tuple[bytes, dict]:
    if not moves_by_key:
        return current_dol, {"enabled": False, "gift_hooks": []}
    if set(moves_by_key) - set(GIFT_BASES):
        raise FormatError("unrecognized gift routine requested")
    for moves in moves_by_key.values():
        if (not isinstance(moves, (list, tuple)) or len(moves) != 4 or
                any(type(move) is not int or not 0 <= move <= 354 or move == 165 for move in moves)):
            raise FormatError("gift hooks require four ordinary move IDs or empty slots, excluding Struggle/shadow moves")
    region = _validate_original(original_dol, current_dol)
    gift_bases = {target['key']: target['base'] for target in special_targets(original_dol)}
    code_offset = (len(original_dol) + 31) // 32 * 32
    code = bytearray(32)  # arena guard is populated after all gift stubs are laid out
    hooks = []
    for key in GIFT_BASES:  # stable layout independent of dict insertion order
        if key not in moves_by_key:
            continue
        call_offset = gift_bases[key] + 8
        call_address = call_offset + TEXT_TO_RAM
        for data in (original_dol, current_dol):
            if _branch_target(call_address, _u32(data, call_offset)) != region.native_constructor:
                raise FormatError(f"gift constructor call changed: {key}")
        stub_address = region.section_ram + len(code)
        payload = _gift_stub(stub_address, list(moves_by_key[key]), region=region)
        hooks.append({"key": key, "call_offset": call_offset,
                      "original_call": _u32(original_dol, call_offset),
                      "patched_call": branch(call_address, stub_address, link=True),
                      "stub_address": stub_address, "stub_offset": code_offset + len(code),
                      "stub_size": len(payload), "moves": list(moves_by_key[key])})
        code.extend(payload)
    reserved_end = region.section_ram + len(code)
    if reserved_end % 32 or reserved_end >= 0x81700000:
        raise FormatError("gift code reservation exceeds the supported arena")
    code[:32] = _arena_guard(reserved_end, region.arena_lo_store)
    output = bytearray(current_dol)
    output.extend(bytes(code_offset - len(output)))
    output.extend(code)
    ranges = []
    def put(offset: int, value: int):
        struct.pack_into(">I", output, offset, value)
        ranges.append((offset, offset + 4))
    put(0x08, code_offset)
    put(0x50, region.section_ram)
    put(0x98, len(code))
    put(region.set_arena_lo - TEXT_TO_RAM, branch(region.set_arena_lo, region.section_ram))
    for hook in hooks:
        put(hook["call_offset"], hook["patched_call"])
    ranges.append((len(current_dol), len(output)))
    for index, (before, after) in enumerate(zip(current_dol, output)):
        if before != after and not any(lo <= index < hi for lo, hi in ranges):
            raise FormatError("gift hook changed a byte outside its exact whitelist")
    parsed = parse_dol(bytes(output))
    added = next((s for s in parsed["sections"] if s["name"] == "text2"), None)
    if added is None or (added["offset"], added["ram_address"], added["size"]) != (code_offset, region.section_ram, len(code)):
        raise FormatError("appended gift section does not parse as expected")
    return bytes(output), {
        "enabled": True, "original_dol_sha256": region.sha256,
        "dol_sha256_before_hooks": hashlib.sha256(current_dol).hexdigest(),
        "dol_sha256_after_hooks": hashlib.sha256(output).hexdigest(),
        "original_dol_size": len(original_dol), "new_dol_size": len(output),
        "section": {"name": "text2", "offset": code_offset, "address": region.section_ram, "size": len(code)},
        "reservation": {"original_bss_end": region.bss_end,
                        "original_stack_top": region.stack_top,
                        "native_default_arena_low": region.section_ram,
                        "reserved_start": region.section_ram, "reserved_end": reserved_end,
                        "arena_setter_address": region.set_arena_lo,
                        "arena_guard_address": region.section_ram,
                        "original_arena_store": region.arena_lo_store,
                        "source_of_reservation": "OSSetArenaLo clamp before native OSInit ClearArena"},
        "gift_hooks": hooks, "native_constructor": region.native_constructor, "native_set_move": region.native_set_move,
        "allowed_changed_ranges": [list(pair) for pair in ranges],
        "unrelated_original_bytes_preserved": True,
        "gift_flags_and_event_gates_preserved": True,
        "runtime_validation": "requires cold boot and actual gift inspection under Dolphin",
    }
