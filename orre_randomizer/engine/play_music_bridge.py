"""Lease-controlled native music gain hooks for verified Europe revision 0 DOLs.

This adapter only transforms bytes supplied by its caller. It extends the same
arena-reserved text2 section as the randomizer's other runtime hooks. Native
sequencers, stream completion and movie playback keep their original clocks.
The companion owns a 64-byte mailbox; without a fresh lease the gain hooks run
the native path. No process, disc image, save or emulator is opened here.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, parse_dol, u32
from .gift_move_hooks import _arena_guard, branch
from .shiny_rules import _Code


BRIDGE_ABI = 1
MAILBOX_MAGIC = 0x4F4D5553  # OMUS
MAILBOX_BYTES = 64
LEASE_VI_TICKS = 30
SUPPORTED_GAME_IDS = ("GC6P01", "GXXP01")
_TEXT2_HEADER = (0x08, 0x50, 0x98)

# Addresses and complete hook windows belong to these exact retail builds.
# They are deliberately not shifted heuristically to other regions/revisions.
_PROFILES = {
    "GC6P01": {
        "kind": "colosseum", "game_id": "GC6P01",
        "source_dol_sha256": "a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5",
        "base": 0x804E3CC0, "arena_setter": 0x8009E4F0, "arena_store": 0x906D8168,
        "hooks": (0x80150418,),
        "hook_windows": (
            "9421ffb07c0802a690010054396100504bf779953c8080487c791b783be41e90389f02408004000428000000418204cc4800a671880da7093bdf0a943b4000ff",
        ),
        "fader": 0x804822E4, "seq_active_global": 0x804C83C4,
        "sound_params_global": 0x804C644C, "reverb_parameters": 0x8049FB48,
        "movie_player": 0x804B80E0, "vi": 0x804C7CFC, "bgm": 0x804C855C,
        "synth_flags": 0x804C83F4, "runtime_sram_flags": 0x80448CD3,
    },
    "GXXP01": {
        "kind": "xd", "game_id": "GXXP01",
        "source_dol_sha256": "a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd",
        "base": 0x805423A0, "arena_setter": 0x800ABEB0, "arena_store": 0x906D82F0,
        "hooks": (0x8016C51C, 0x8016CA84),
        "hook_windows": (
            "9421ffb07c0802a690010054396100504bf6f25d7c7d1b787c9823787cb92b787cda33787cfb3b787d1c4378480174213c608049380000083bc3192838600000",
            "9421ffc07c0802a690010044396100404bf6ecfd7c7d1b787c9a23787cbb2b787cdc337848016ec13c608049380000083bc31928386000007fc4f3787c0903a6",
        ),
        "fader": 0, "streams_global": 0x80525AC8,
        "stream_count_global": 0x80525ACC, "sound_params_global": 0x80523004,
        "stream_files_global": 0x80522E24, "movie_slots_global": 0x80525D44,
        "movie_count_global": 0x80525D40, "vi": 0x80525234, "bgm": 0x80525ABC,
    },
}


def music_bridge_profile(game_id: str, *, revision: int = 0) -> dict:
    """Return trusted fixed addresses for host-side metadata verification.

    Dynamic section, stub and mailbox addresses are deliberately absent. A
    detached dictionary prevents a caller from changing the adapter's contract.
    """
    if game_id not in _PROFILES or type(revision) is not int or revision != 0:
        raise FormatError("native-speed music supports Europe revision 0 only")
    return {key: value for key, value in _PROFILES[game_id].items() if key != "hook_windows"}


def _load(code, register, value):
    code.emit(0x3C000000 | (register << 21) | (value >> 16),
              0x60000000 | (register << 21) | (register << 16) | (value & 0xFFFF))


def _lw(register, base, offset):
    return 0x80000000 | (register << 21) | (base << 16) | (offset & 0xFFFF)


def _st(register, base, offset):
    return 0x90000000 | (register << 21) | (base << 16) | (offset & 0xFFFF)


def _cmp(register, value):
    return 0x28000000 | (register << 16) | (value & 0xFFFF)


def _compare(left, right):
    return 0x7C000040 | (left << 16) | (right << 11)


def _increment(code, control_offset):
    # addic changes XER.CA. Use a saved nonzero RA with addi instead.
    code.emit(_lw(11, 12, control_offset), 0x396B0001, _st(11, 12, control_offset))


def _movie_bypass(code, profile):
    """Return to native gain immediately while the native movie player runs."""
    if profile["kind"] == "colosseum":
        _load(code, 9, profile["movie_player"])
        _load(code, 10, 0x54485000)  # THP header magic
        code.emit(_lw(0, 9, 0x3C), _compare(0, 10))
        code.conditional(0x40820000, "no_movie")
        code.emit(_lw(0, 9, 0xA0), _cmp(0, 1))
        code.conditional(0x40820000, "no_movie")
        code.emit(0x880900A4, _cmp(0, 1))  # lbz r0,0xa4(r9)
        code.conditional(0x41820000, "inactive")
        code.emit(_cmp(0, 2))
        code.conditional(0x41820000, "inactive")
    else:
        _load(code, 11, profile["movie_count_global"])
        code.emit(_lw(11, 11, 0), _cmp(11, 32))
        code.conditional(0x41810000, "inactive")
        code.emit(_cmp(11, 0))
        code.conditional(0x41820000, "no_movie")
        _load(code, 9, profile["movie_slots_global"])
        code.emit(_lw(9, 9, 0), 0x71200003)  # andi. r0,r9,3
        code.conditional(0x40820000, "inactive")
        _load(code, 10, 0x80000000)
        code.emit(_compare(9, 10))
        code.conditional(0x41800000, "inactive")
        _load(code, 10, 0x817FFC00)  # bounds the entire largest table in MEM1
        code.emit(_compare(9, 10))
        code.conditional(0x41810000, "inactive")
        code.label("movie_slot")
        code.emit(_lw(0, 9, 0), _cmp(0, 0))
        code.conditional(0x41820000, "next_movie_slot")
        code.emit(_cmp(0, 16))
        code.conditional(0x40810000, "inactive")
        code.label("next_movie_slot")
        code.emit(0x39290020, 0x396BFFFF, _cmp(11, 0))
        code.conditional(0x40820000, "movie_slot")
    code.label("no_movie")


def _gain_stub(address, control, profile, original, continuation):
    code = _Code(address)
    stream = profile["kind"] == "xd"
    # Save every temporary and all CR fields; LR, CTR, XER and FPRs stay intact.
    code.emit(0x9421FFC0, _st(0, 1, 8))
    for register in range(7, 13):
        code.emit(_st(register, 1, 12 + 4 * (register - 7)))
    code.emit(0x7C000026, _st(0, 1, 36))  # mfcr r0
    _load(code, 12, control)
    code.emit(_lw(0, 12, 24))
    _load(code, 11, MAILBOX_MAGIC)
    code.emit(_compare(0, 11))
    code.conditional(0x40820000, "inactive")
    code.emit(_lw(0, 12, 28), _cmp(0, BRIDGE_ABI))
    code.conditional(0x40820000, "inactive")
    code.emit(_lw(0, 12, 0), _cmp(0, 1))
    code.conditional(0x40820000, "inactive")
    _load(code, 11, profile["vi"])
    code.emit(_lw(11, 11, 0), _lw(0, 12, 4), 0x7C005850, _cmp(0, LEASE_VI_TICKS))
    code.conditional(0x41810000, "inactive")  # unsigned VI subtraction wraps
    _movie_bypass(code, profile)
    if stream:
        for index in range(8):
            code.emit(_lw(0, 12, 32 + 4 * index), _compare(3, 0))
            code.conditional(0x41820000, "mute")
        code.jump("inactive")
        code.label("mute")
        code.emit(0x38800000)  # r4 = native stream-volume argument
        _increment(code, 16)
        code.jump("end")
        code.label("inactive")
        _increment(code, 20)
    else:
        code.emit(_lw(8, 12, 8))
        code.jump("switch")
        code.label("inactive")
        code.emit(0x39000000)  # desired mask = none; restore prior native gains
        code.label("switch")
        code.emit(_lw(7, 12, 12))
        for index in range(8):
            bit = 1 << index
            _load(code, 9, profile["fader"] + (23 + index) * 48 + 20)
            code.emit(0x71000000 | bit)
            code.conditional(0x41820000, f"off{index}")
            code.emit(0x70E00000 | bit)
            code.conditional(0x40820000, f"zero{index}")
            code.emit(_lw(0, 9, 0), _st(0, 12, 32 + 4 * index), 0x60E70000 | bit)
            code.label(f"zero{index}")
            code.emit(0x38000000, _st(0, 9, 0))
            _increment(code, 16)
            code.jump(f"next{index}")
            code.label(f"off{index}")
            code.emit(0x70E00000 | bit)
            code.conditional(0x41820000, f"next{index}")
            code.emit(_lw(0, 12, 32 + 4 * index), _st(0, 9, 0),
                      0x70E70000 | ((~bit) & 0xFFFF))
            _increment(code, 20)
            code.label(f"next{index}")
        code.emit(_st(7, 12, 12))
    code.label("end")
    code.emit(_lw(0, 1, 36), 0x7C0FF120)  # mtcrf 255,r0
    for register in range(7, 13):
        code.emit(_lw(register, 1, 12 + 4 * (register - 7)))
    code.emit(_lw(0, 1, 8), 0x38210040, original)
    code.emit(branch(address + 4 * len(code.words), continuation))
    return code.finish()


def _offset(descriptor, address, size=4):
    for section in descriptor["sections"]:
        if section["ram_address"] <= address and address + size <= section["ram_address"] + section["size"]:
            return section["offset"] + address - section["ram_address"]
    raise FormatError(f"music bridge address {address:#x} is outside DOL sections")


def _reservation(original, current, profile):
    descriptor = parse_dol(original)
    parse_dol(current)
    if (len(current) < len(original) or any(u32(original, pos) for pos in _TEXT2_HEADER)
            or any(current[pos:pos + 4] != original[pos:pos + 4]
                   for pos in range(0, 0x100, 4) if pos not in _TEXT2_HEADER)):
        raise FormatError("unsupported music bridge DOL section layout")
    base = profile["base"]
    if (descriptor["bss_ram_address"] + descriptor["bss_size"] >= base
            or any(section["ram_address"] + section["size"] > base for section in descriptor["sections"])):
        raise FormatError("native memory overlaps music bridge reservation")
    offset = (len(original) + 31) & ~31
    arena = _offset(descriptor, profile["arena_setter"], 8)
    if original[arena:arena + 8] != struct.pack(">II", profile["arena_store"], 0x4E800020):
        raise FormatError("unexpected native music bridge arena setter")
    if current[arena + 4:arena + 8] != original[arena + 4:arena + 8]:
        raise FormatError("music bridge arena setter return changed")
    header = tuple(u32(current, pos) for pos in _TEXT2_HEADER)
    previous_size = header[2]
    if previous_size:
        if (header != (offset, base, previous_size) or previous_size < 32 or previous_size % 32
                or offset + previous_size != len(current)
                or current[offset:offset + 32] != _arena_guard(base + previous_size, profile["arena_store"])
                or u32(current, arena) != branch(profile["arena_setter"], base)):
            raise FormatError("invalid existing music bridge text2 arena reservation")
        code = bytearray(current[offset:])
    else:
        if any(header) or len(current) != len(original) or u32(current, arena) != profile["arena_store"]:
            raise FormatError("invalid unpatched music bridge reservation")
        code = bytearray(32)
    return descriptor, offset, arena, code


def patch_music_bridge(original_dol: bytes, current_dol: bytes, game_id: str,
                       *, revision: int = 0) -> tuple[bytes, dict]:
    """Patch a generated DOL against an exact retail baseline; reject ambiguity.

    Existing randomizer data and guarded runtime stubs are retained. The caller
    is responsible for putting the returned DOL in its independent output ROM
    and updating the disc filesystem before publishing that output.
    """
    if game_id not in _PROFILES or type(revision) is not int or revision != 0:
        raise FormatError("native-speed music supports Europe revision 0 only")
    profile = _PROFILES[game_id]
    source_hash = hashlib.sha256(original_dol).hexdigest()
    if source_hash != profile["source_dol_sha256"]:
        raise FormatError("native-speed music requires the exact verified retail DOL")
    descriptor, section_offset, arena_offset, code = _reservation(original_dol, current_dol, profile)
    previous_size = u32(current_dol, 0x98)
    hooks = []
    for address, window in zip(profile["hooks"], profile["hook_windows"], strict=True):
        expected = bytes.fromhex(window)
        pos = _offset(descriptor, address, len(expected))
        if any(data[pos:pos + len(expected)] != expected for data in (original_dol, current_dol)):
            raise FormatError(f"native music gain hook context changed at {address:#x}")
        hooks.append({"address": address, "offset": pos, "original": u32(original_dol, pos),
                      "stub_address": profile["base"] + len(code)})
        code.extend(_gain_stub(hooks[-1]["stub_address"], 0, profile,
                               hooks[-1]["original"], address + 4))
    control = profile["base"] + len(code)
    for hook in hooks:
        start = hook["stub_address"] - profile["base"]
        payload = _gain_stub(hook["stub_address"], control, profile, hook["original"], hook["address"] + 4)
        code[start:start + len(payload)] = payload
        hook["stub_size"] = len(payload)
    header = [0, 0, 0, 0, 0, 0, MAILBOX_MAGIC, BRIDGE_ABI]
    header += [0x3F800000] * 8 if profile["kind"] == "colosseum" else [0xFFFFFFFF] * 8
    code.extend(struct.pack(">16I", *header))
    end = profile["base"] + len(code)
    if end >= 0x81700000 or end % 32:
        raise FormatError("native music bridge exceeds supported arena")
    code[:32] = _arena_guard(end, profile["arena_store"])
    output = bytearray(current_dol[:section_offset])
    output.extend(bytes(section_offset - len(output)))
    output.extend(code)
    ranges = [(pos, pos + 4) for pos in _TEXT2_HEADER]
    ranges += [(arena_offset, arena_offset + 4), (len(current_dol), len(output))]
    if previous_size:
        ranges.append((section_offset, section_offset + 32))
    for pos, value in zip(_TEXT2_HEADER, (section_offset, profile["base"], len(code)), strict=True):
        struct.pack_into(">I", output, pos, value)
    struct.pack_into(">I", output, arena_offset, branch(profile["arena_setter"], profile["base"]))
    for hook in hooks:
        struct.pack_into(">I", output, hook["offset"], branch(hook["address"], hook["stub_address"]))
        ranges.append((hook["offset"], hook["offset"] + 4))
    cursor = 0
    for start, stop in sorted(ranges):
        if output[cursor:start] != current_dol[cursor:start]:
            raise FormatError("native music bridge changed unrelated DOL bytes")
        cursor = max(cursor, stop)
    if output[cursor:len(current_dol)] != current_dol[cursor:]:
        raise FormatError("native music bridge changed unrelated trailing DOL bytes")
    parse_dol(bytes(output))
    metadata = {key: value for key, value in profile.items() if key != "hook_windows"}
    metadata.update({
        "enabled": True, "bridge_abi": BRIDGE_ABI, "revision": revision,
        "source_dol_sha256": source_hash,
        "dol_sha256_before": hashlib.sha256(current_dol).hexdigest(),
        "dol_sha256_after": hashlib.sha256(output).hexdigest(),
        "control": control, "mailbox_bytes": MAILBOX_BYTES, "mailbox_magic": MAILBOX_MAGIC,
        "lease_vi_ticks": LEASE_VI_TICKS, "section_bytes": len(code),
        "section": {"name": "text2", "offset": section_offset, "address": profile["base"], "size": len(code)},
        "previous_section_bytes": previous_size, "reserved_end": end,
        "gain_hooks": hooks, "allowed_changed_ranges": [list(pair) for pair in sorted(ranges)],
        "native_movie_bypass": True, "native_completion_preserved": True,
    })
    return bytes(output), metadata
