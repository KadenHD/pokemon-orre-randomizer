"""Versioned external face bridge for exact Colosseum revision-0 profiles.

Only the verified Spinda face factory and HSD texture setup are wrapped. The
native five-map chain is retained. HD pixels never belong to the disc image:
an owned launcher companion fills one inactive arena buffer, and native code
publishes its complete ImageDesc after a GPU fence. Direct ROM use stays native.
Patch availability and runtime qualification are separate; unqualified profiles
cannot start the companion through its normal API.
"""
from __future__ import annotations

import hashlib
import struct
from copy import deepcopy

from .analyze_game import FormatError, parse_dol, u32
from .gift_move_hooks import _arena_guard, branch
from .shiny_rules import _Code

CONTRACT = "dna-spinda-precomposed-face-v1"
MAGIC, ABI = 0x4F534648, 1  # OSFH
NATIVE_SIZE, HD_SIZE = 128, 512
BUFFER_BYTES, CONTROL_BYTES, LEASE_TICKS = 512 * 512 * 2, 512, 30
REGISTRY_OFFSET, REGISTRY_COUNT, REGISTRY_STRIDE = 128, 8, 16
DESCRIPTOR_OFFSET = 256
NONE = 0xFFFFFFFF

# Byte offsets and ownership in the shared control record. Publishing uses a
# final aligned word; neither side writes the other's fields.
FIELDS = {
    "magic": 0, "abi": 4, "enabled": 8, "heartbeat": 12,
    "native_vi": 16, "active_bank": 20, "active_epoch": 24,
    "request_serial": 28, "request_epoch": 32, "request_pixels": 36,
    "request_pid": 40, "request_tobj": 44,
    "ready_bank": 52, "ready_epoch": 56, "ready_pixels": 60,
    "ready_pid": 64, "ready_serial": 68, "ready_commit": 72,
    "ack_serial": 76, "fallbacks": 80, "displays": 84,
    "factory_serial": 88, "request_counter": 92,
}
HOST_FIELDS = frozenset((8, 12, 52, 56, 60, 64, 68, 72))

_PROFILE = {
    "game_id": "GC6P01", "revision": 0,
    "source_dol_sha256": "a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5",
    "base": 0x804E3CC0, "arena_setter": 0x8009E4F0, "arena_store": 0x906D8168,
    "vi": 0x804C7CFC, "factory": 0x80144620, "setup": 0x801C0358,
    "analyzer": 0x804C7AC0,
    "draw_done": 0x800BC3F4, "dc_invalidate": 0x8009E7CC, "gx_invalidate": 0x800BE89C,
    "factory_window": "9421ffb07c0802a690010054bec100287c761b787c9e23787cbf2b783b6000004bfae53d7c7a07347ec3b3784bfae5297c7907347ec3b3784bfae50d7c7c1b78",
    "setup_window": "9421ff807c0802a690010084bf0100607c781b793be000003bc000003ba00010930dab6c418203207f03c3784800032d2c030000408103083803ffff28000007",
}
_PROFILES = {
    "GC6P01": _PROFILE,
    "GC6E01": {
        "game_id": "GC6E01", "revision": 0,
        "source_dol_sha256": "7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4",
        "base": 0x80496740, "arena_setter": 0x8009AFC8, "arena_store": 0x906D8168,
        "vi": 0x8047A84C, "analyzer": 0x8047A610,
        "factory": 0x801402AC, "setup": 0x801BBFE4,
        "draw_done": 0x800B8DF4, "dc_invalidate": 0x8009B2A4, "gx_invalidate": 0x800BB29C,
        "factory_window": "9421ffb07c0802a690010054bec100287c761b787c9e23787cbf2b783b6000004bfaf2317c7a07347ec3b3784bfaf21d7c7907347ec3b3784bfaf2017c7c1b78",
        "setup_window": "9421ff807c0802a690010084bf0100607c781b793be000003bc000003ba00010930dab5c418203207f03c3784800032d2c030000408103083803ffff28000007",
    },
    "GC6J01": {
        "game_id": "GC6J01", "revision": 0,
        "source_dol_sha256": "64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2",
        "base": 0x80481D40, "arena_setter": 0x80098C74, "arena_store": 0x906D8160,
        "vi": 0x80465F14, "analyzer": 0x80465CD8,
        "factory": 0x8013D384, "setup": 0x801B7C10,
        "draw_done": 0x800B6AA0, "dc_invalidate": 0x80098F50, "gx_invalidate": 0x800B8D10,
        "factory_window": "9421ffb07c0802a690010054bec100287c761b787c9e23787cbf2b783b6000004bfafe217c7a07347ec3b3784bfafe0d7c7907347ec3b3784bfafdf17c7c1b78",
        "setup_window": "9421ff807c0802a690010084bf0100607c781b793be000003bc000003ba00010930dab2c418203207f03c3784800032d2c030000408103083803ffff28000007",
    },
}
PATCHABLE_GAME_IDS = tuple(_PROFILES)
# Exact static profiles are not automatically permission to launch the helper.
# Only observed runtime scopes belong here after qualification is complete.
# EU/USA revision0: owned Dolphin2609b, full pack, dual core/internal3x,
# two native PID/colour variants, actual512-square dumps and native recovery.
# JP retains its native face: the extra arena reservation stalls its lab load.
VALIDATED_GAME_IDS = frozenset(("GC6P01", "GC6E01", "GC6J01"))


def bridge_profile(game_id="GC6P01", revision=0):
    if game_id not in _PROFILES or type(revision) is not int or revision != 0:
        raise FormatError("Spinda HD face bridge requires a verified Colosseum revision 0 profile")
    return deepcopy({k: v for k, v in _PROFILES[game_id].items() if not k.endswith("_window")})


def face_runtime_validated(game_id, revision=0):
    return type(revision) is int and revision == 0 and game_id in VALIDATED_GAME_IDS


def _load(c, r, value):
    c.emit(0x3C000000 | r << 21 | value >> 16,
           0x60000000 | r << 21 | r << 16 | (value & 65535))


def _lw(r, base, offset):
    return 0x80000000 | r << 21 | base << 16 | (offset & 65535)


def _st(r, base, offset):
    return 0x90000000 | r << 21 | base << 16 | (offset & 65535)


def _cmp(r, value):
    return 0x28000000 | r << 16 | (value & 65535)


def _eq(a, b):
    return 0x7C000040 | a << 16 | b << 11


def _mr(dst, src):
    return 0x7C000378 | src << 21 | dst << 16 | src << 11


def _prologue(c):
    c.emit(0x9421FF00, 0x7C0802A6, 0x90010104, 0xBDC10020)


def _result(c):
    c.emit(0x9061000C, 0x7C000026, 0x90010010, 0x7C0102A6, 0x90010014)


def _return(c):
    c.emit(0x80010014, 0x7C0103A6, 0x80010010, 0x7C0FF120,
           0x8061000C, 0xB9C10020, 0x80010104, 0x7C0803A6,
           0x38210100, 0x4E800020)


def _native_call(c, target, original):
    # The first instruction is the verified stack allocation, so this small
    # trampoline can run it and resume +4 with the wrapper's return LR intact.
    call = len(c.words)
    c.emit(0)
    return call, target, original


def _finish(c, trampoline):
    call, target, original = trampoline
    at = c.address + len(c.words) * 4
    c.words[call] = branch(c.address + call * 4, at, link=True)
    c.emit(original, branch(at + 4, target + 4))
    return c.finish()


def _factory_stub(address, control, profile, *, guard_reuse=True):
    c = _Code(address)
    _prologue(c)
    c.emit(0x90A10008)  # original pattern/PID, no shiny guess
    trampoline = _native_call(c, profile["factory"], 0x9421FFB0)
    _result(c)
    # GStextureHandle: dimensions +0, mip0 pointer +0x28. Reject malformed
    # factory results rather than registering arbitrary textures.
    _load(c, 4, 0x80003000)
    c.emit(_eq(3, 4)); c.conditional(0x41800000, "done")
    _load(c, 4, 0x817FFF80)
    c.emit(_eq(3, 4)); c.conditional(0x41810000, "done")
    c.emit(_lw(4, 3, 0)); _load(c, 5, 0x00800080)
    c.emit(_eq(4, 5)); c.conditional(0x40820000, "done")
    c.emit(_lw(6, 3, 0x28)); _load(c, 4, 0x80003000)
    c.emit(_eq(6, 4)); c.conditional(0x41800000, "done")
    _load(c, 4, 0x817F8000)
    c.emit(_eq(6, 4)); c.conditional(0x41810000, "done")
    c.emit(0x70C0001F); c.conditional(0x40820000, "done")
    _load(c, 12, control)
    c.emit(_lw(7, 12, 88), 0x38E70001)
    c.emit(_cmp(7, 0)); c.conditional(0x40820000, "serial")
    c.emit(0x38E00001)
    c.label("serial")
    c.emit(_st(7, 12, 88))
    if guard_reuse:
        # Native texture allocation may reuse a previous face's pixel pointer.
        # Retire every older match before publishing its new PID/epoch; the
        # setup search must never bind a new face to the first stale ring slot.
        _load(c, 4, control + 128)
        c.emit(0x38A00008)
        c.label("retire_reused_pixels")
        c.emit(_lw(0, 4, 4), _eq(0, 6))
        c.conditional(0x40820000, "next_registry_slot")
        c.emit(0x38000000, _st(0, 4, 0))
        c.label("next_registry_slot")
        c.emit(0x38840010, 0x38A5FFFF, _cmp(5, 0))
        c.conditional(0x40820000, "retire_reused_pixels")
        c.emit(0x7C0004AC)
    c.emit(0x70E00007, 0x54002036, 0x398C0080,
           0x7D8C0214, 0x38000000, _st(0, 12, 0), _st(6, 12, 4),
           _lw(4, 1, 8), _st(4, 12, 8), _st(3, 12, 12),
           0x7C0004AC, _st(7, 12, 0))
    c.label("done")
    _return(c)
    return _finish(c, trampoline)


def _setup_stub(address, control, buffers, profile):
    if len(buffers) not in (1, 2):
        raise FormatError("Spinda face requires one or two fenced pixel banks")
    maximum_bank = len(buffers) - 1
    c = _Code(address)
    _prologue(c)
    c.emit(_mr(31, 3), 0x3BC00000)  # head TObj, saved native ImageDesc
    _load(c, 29, control)
    _load(c, 4, profile["vi"])
    c.emit(_lw(4, 4, 0), _st(4, 29, 16), _lw(5, 29, 8), _cmp(5, 1))
    c.conditional(0x40820000, "fallback")
    c.emit(_lw(5, 29, 12), 0x7CA52050, _cmp(5, LEASE_TICKS))  # unsigned VI-heartbeat
    c.conditional(0x41810000, "fallback")
    # One active lab hologram owns the shared pool. Field/battle Spinda do not
    # opt in merely because the launcher has enabled HD textures.
    _load(c, 5, profile["analyzer"])
    c.emit(_lw(5, 5, 0))
    _load(c, 6, 0x80003000)
    c.emit(_eq(5, 6)); c.conditional(0x41800000, "native")
    _load(c, 6, 0x817FFE00)
    c.emit(_eq(5, 6)); c.conditional(0x41810000, "native")
    c.emit(0xA0C5000C, _cmp(6, 308)); c.conditional(0x40820000, "native")
    c.emit(_lw(5, 5, 0x168))
    _load(c, 6, 0x80003000)
    c.emit(_eq(5, 6)); c.conditional(0x41800000, "native")
    _load(c, 6, 0x817FFF80)
    c.emit(_eq(5, 6)); c.conditional(0x41810000, "native")
    # Validate the TObj and descriptor before dereferencing their fields.
    _load(c, 5, 0x80003000); c.emit(_eq(31, 5)); c.conditional(0x41800000, "native")
    _load(c, 5, 0x817FFF54); c.emit(_eq(31, 5)); c.conditional(0x41810000, "native")
    c.emit(_lw(28, 31, 0x58)); _load(c, 5, 0x80003000)
    c.emit(_eq(28, 5)); c.conditional(0x41800000, "native")
    _load(c, 5, 0x817FFFE8); c.emit(_eq(28, 5)); c.conditional(0x41810000, "native")
    c.emit(_lw(5, 28, 4)); _load(c, 6, 0x00800080)
    c.emit(_eq(5, 6)); c.conditional(0x40820000, "native")
    c.emit(_lw(5, 28, 8), _cmp(5, 4)); c.conditional(0x40820000, "native")
    c.emit(_lw(27, 28, 0), 0x38DD0080, 0x38E00008)
    c.label("search")
    c.emit(_lw(26, 6, 0), _cmp(26, 0)); c.conditional(0x41820000, "next")
    c.emit(_lw(5, 6, 4), _eq(27, 5)); c.conditional(0x41820000, "found")
    c.label("next")
    c.emit(0x38C60010, 0x38E7FFFF, _cmp(7, 0)); c.conditional(0x40820000, "search")
    c.jump("native")
    c.label("found")
    c.emit(_lw(25, 6, 8), _lw(5, 29, 32), _eq(26, 5))
    c.conditional(0x41820000, "request_ready")
    c.emit(0x38000000, _st(0, 29, 28), _st(26, 29, 32), _st(27, 29, 36),
           _st(25, 29, 40), _st(31, 29, 44), _lw(5, 29, 92), 0x38A50001)
    c.emit(_cmp(5, 0)); c.conditional(0x40820000, "request_serial")
    c.emit(0x38A00001)
    c.label("request_serial")
    c.emit(_st(5, 29, 92), 0x7C0004AC, _st(5, 29, 28))
    c.label("request_ready")
    c.emit(_lw(5, 29, 72), _cmp(5, 0)); c.conditional(0x41820000, "active")
    c.emit(_lw(24, 29, 68), _lw(6, 29, 76), _eq(24, 6))
    c.conditional(0x40820000, "validate_ready")
    # A lease fallback releases the active bank but keeps the last complete
    # packet and its acknowledgement. Reaccept that packet after recovery;
    # an already active packet must not repeat the GPU fence every draw.
    c.emit(_lw(6, 29, 20), _cmp(6, maximum_bank))
    c.conditional(0x40810000, "active")  # ble: an active bank already exists
    c.label("validate_ready")
    # Always acknowledge a rejected old publication; otherwise a new request
    # could leave the companion waiting forever for an unconsumable bank.
    for offset, register in ((56, 26), (60, 27), (64, 25)):
        c.emit(_lw(6, 29, offset), _eq(6, register)); c.conditional(0x40820000, "reject")
    c.emit(_eq(5, 26)); c.conditional(0x40820000, "reject")
    c.emit(_lw(6, 29, 28), _eq(24, 6)); c.conditional(0x40820000, "reject")
    c.emit(_lw(23, 29, 52), _cmp(23, maximum_bank)); c.conditional(0x41810000, "reject")
    c.emit(_lw(6, 29, 20), _eq(23, 6)); c.conditional(0x41820000, "reject")
    c.emit(_lw(6, 29, 72), _eq(5, 6)); c.conditional(0x40820000, "reject")
    c.call(profile["draw_done"])
    _load(c, 3, buffers[0])
    if len(buffers) == 2:
        c.emit(_cmp(23, 0)); c.conditional(0x41820000, "invalidate")
        _load(c, 3, buffers[1])
    c.label("invalidate")
    _load(c, 4, BUFFER_BYTES)
    c.call(profile["dc_invalidate"])
    c.call(profile["gx_invalidate"])
    c.emit(_st(23, 29, 20), _st(26, 29, 24))
    c.label("reject")
    c.emit(0x7C0004AC, _st(24, 29, 76))
    c.label("active")
    c.emit(_lw(5, 29, 24), _eq(5, 26)); c.conditional(0x40820000, "native")
    c.emit(_lw(5, 29, 20), _cmp(5, maximum_bank)); c.conditional(0x41810000, "native")
    # Immutable descriptors, each 32-byte aligned. Only this TObj's pointer
    # changes, and only for the original HSD_TObjSetup call below.
    c.emit(0x54A52834, 0x38DD0100, 0x7CA62A14, _mr(30, 28), _st(5, 31, 0x58),
           _lw(5, 29, 84), 0x38A50001, _st(5, 29, 84))
    c.jump("native")
    c.label("fallback")
    c.emit(_lw(5, 29, 20), _cmp(5, maximum_bank)); c.conditional(0x41810000, "fallback_ack")
    c.call(profile["draw_done"])
    c.emit(0x38A0FFFF, _st(5, 29, 20), 0x38A00000, _st(5, 29, 24),
           _lw(5, 29, 80), 0x38A50001, _st(5, 29, 80))
    c.label("fallback_ack")
    c.emit(_lw(5, 29, 68), _st(5, 29, 76))
    c.label("native")
    c.emit(_mr(3, 31))
    trampoline = _native_call(c, profile["setup"], 0x9421FF80)
    _result(c)
    c.emit(_cmp(30, 0)); c.conditional(0x41820000, "restored")
    c.emit(_st(30, 31, 0x58))
    c.label("restored")
    _return(c)
    return _finish(c, trampoline)


def _offset(layout, address, size=4):
    matches = [s["offset"] + address - s["ram_address"] for s in layout["sections"]
               if s["ram_address"] <= address and address + size <= s["ram_address"] + s["size"]]
    if len(matches) != 1:
        raise FormatError("Spinda bridge address is not uniquely mapped")
    return matches[0]


def patch_spinda_face_bridge(original: bytes, current: bytes, game_id="GC6P01", *, revision=0):
    """Return a patched caller-owned DOL and metadata; perform no file/process IO."""
    profile = bridge_profile(game_id, revision)
    if not isinstance(original, bytes) or not isinstance(current, bytes) or min(len(original), len(current)) < 0x100:
        raise FormatError("Spinda bridge requires complete immutable DOL byte strings")
    if hashlib.sha256(original).hexdigest() != profile["source_dol_sha256"]:
        raise FormatError("Spinda bridge requires the exact verified retail DOL")
    layout = parse_dol(original)
    allowed_header = {byte for field in (8, 0x50, 0x98) for byte in range(field, field + 4)}
    if any(current[i] != original[i] for i in range(0x100) if i not in allowed_header):
        raise FormatError("Spinda bridge found incompatible DOL section headers")
    section_offset = (len(original) + 31) & ~31
    previous = u32(current, 0x98)
    arena = _offset(layout, profile["arena_setter"])
    if previous:
        if (u32(current, 8) != section_offset or u32(current, 0x50) != profile["base"]
                or previous % 32 or section_offset + previous != len(current)
                or u32(current, arena) != branch(profile["arena_setter"], profile["base"])
                or current[section_offset:section_offset + 32] != _arena_guard(profile["base"] + previous, profile["arena_store"])):
            raise FormatError("Spinda bridge requires a valid existing arena guard")
        code = bytearray(current[section_offset:])
    else:
        if len(current) != len(original) or u32(current, arena) != profile["arena_store"]:
            raise FormatError("Spinda bridge found an invalid initial arena")
        code = bytearray(32)
    hook_offsets = []
    for kind in ("factory", "setup"):
        offset = _offset(layout, profile[kind], 64)
        expected = bytes.fromhex(_PROFILES[game_id][kind + "_window"])
        if any(data[offset:offset + 64] != expected for data in (original, current)):
            raise FormatError("Spinda bridge native hook context changed: " + kind)
        hook_offsets.append(offset)
    factory_address = profile["base"] + len(code)
    dummy_factory = _factory_stub(factory_address, 0, profile)
    setup_address = factory_address + len(dummy_factory)
    bank_count = 1 if game_id == "GC6J01" else 2
    dummy_setup = _setup_stub(setup_address, 0, (0,) * bank_count, profile)
    control = setup_address + len(dummy_setup)
    buffers = tuple(control + CONTROL_BYTES + index * BUFFER_BYTES for index in range(bank_count))
    code.extend(_factory_stub(factory_address, control, profile))
    code.extend(_setup_stub(setup_address, control, buffers, profile))
    header = bytearray(CONTROL_BYTES)
    for name, value in (("magic", MAGIC), ("abi", ABI), ("active_bank", NONE), ("ready_bank", NONE)):
        struct.pack_into(">I", header, FIELDS[name], value)
    for index, buffer in enumerate(buffers):
        struct.pack_into(">IHHIIff", header, DESCRIPTOR_OFFSET + index * 32, buffer, HD_SIZE, HD_SIZE, 4, 0, 0., 0.)
    code.extend(header)
    # Japan's apploader also bounds loaded section addresses. Pixel banks need
    # an arena reservation, not file-backed zeroes: the companion writes a
    # complete inactive bank before the native code can publish it. Install
    # this bridge last when using the reservation-only layout.
    embedded_banks = game_id != "GC6J01"
    load_end = profile["base"] + len(code)
    if embedded_banks:
        code.extend(bytes(BUFFER_BYTES * bank_count))
    end = load_end + BUFFER_BYTES * bank_count
    if end >= 0x81700000 or end % 32:
        raise FormatError("Spinda bridge exceeds the supported native arena")
    code[:32] = _arena_guard(end, profile["arena_store"])
    output = bytearray(current[:section_offset])
    output.extend(bytes(section_offset - len(output)))
    output.extend(code)
    for at, value in ((8, section_offset), (0x50, profile["base"]), (0x98, len(code)),
                      (arena, branch(profile["arena_setter"], profile["base"]))):
        struct.pack_into(">I", output, at, value)
    hooks = []
    for kind, at, stub, size in zip(("factory", "setup"), hook_offsets,
                                    (factory_address, setup_address), (len(dummy_factory), len(dummy_setup)), strict=True):
        struct.pack_into(">I", output, at, branch(profile[kind], stub))
        hooks.append({"kind": kind, "address": profile[kind], "stub_address": stub, "stub_size": size})
    parse_dol(bytes(output))
    metadata = {**profile, "contract": CONTRACT, "bridge_abi": ABI, "control": control,
                "control_bytes": CONTROL_BYTES, "buffers": list(buffers), "buffer_bytes": BUFFER_BYTES,
                "pixel_banks_in_executable": embedded_banks, "pixel_banks_begin": load_end,
                "buffer_count": bank_count, "registry_reuse_guard": True,
                "registry_count": REGISTRY_COUNT, "native_texture_maps": 5, "hd_texture_maps": 5,
                "native_width": 128, "hd_width": 512, "lease_vi_ticks": LEASE_TICKS,
                "hooks": hooks, "section_offset": section_offset, "section_bytes": len(code),
                "reserved_end": end, "native_fallback": True,
                "production_validated": face_runtime_validated(game_id, revision),
                "hd_materials_embedded": False,
                "scope": "colosseum-dna-hologram-only",
                "dol_sha256_before": hashlib.sha256(current).hexdigest(),
                "dol_sha256_after": hashlib.sha256(output).hexdigest()}
    return bytes(output), metadata
