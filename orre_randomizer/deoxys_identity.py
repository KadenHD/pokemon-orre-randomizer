"""Persistent Deoxys form in the games' native reserved Para1Amari field.

The marker changes neither the saved personality nor any gameplay identity.
Unmarked retail/imported records retain Normal Forme. Native initialization,
PC copies and save payloads preserve the reservation's normal lifecycle.
"""
from __future__ import annotations

import struct

from .engine.shiny_rules import _Code

DEOXYS = 410
FORM_TAG = 0xDEC0
FORM_MASK = 0xFFFC
FORM_OFFSETS = {"colosseum": 0xD2, "xd": 0x0C}
RECORD_SIZES = {"colosseum": 0x138, "xd": 0xC4}
MODEL_MARKERS = tuple(0x7FB0 + form for form in range(4))
SAVEDATA_GETTERS = {"GC6P01": 0x8012D448, "GC6E01": 0x80129280, "GC6J01": 0x801269BC,
                    "GXXP01": 0x801D0A8C, "GXXE01": 0x801CEFB4, "GXXJ01": 0x801C9E54}
_GAME_IDS = {"GC6P01": "colosseum", "GC6E01": "colosseum", "GC6J01": "colosseum",
             "GXXP01": "xd", "GXXE01": "xd", "GXXJ01": "xd"}


def game_family(game_id: str) -> str:
    if type(game_id) is not str:
        raise ValueError("Unknown Deoxys record game")
    if game_id in FORM_OFFSETS:
        return game_id
    try:
        return _GAME_IDS[game_id]
    except (KeyError, TypeError):
        raise ValueError("Unknown Deoxys record game") from None


def form_offset(game_id: str) -> int:
    return FORM_OFFSETS[game_family(game_id)]


def form_from_tag(tag: int) -> int:
    if type(tag) is not int or not 0 <= tag <= 0xFFFF:
        raise ValueError("Deoxys form tag must be an unsigned 16-bit integer")
    return tag & 3 if tag & FORM_MASK == FORM_TAG else 0


def _record(record: bytes | bytearray, game_id: str):
    family = game_family(game_id)
    if not isinstance(record, (bytes, bytearray)) or len(record) != RECORD_SIZES[family]:
        raise ValueError("A complete native Pokemon record is required")
    return family, struct.unpack_from(">H", record, 0)[0]


def saved_form(record: bytes | bytearray, game_id: str) -> int:
    family, species = _record(record, game_id)
    if species != DEOXYS:
        return 0
    return form_from_tag(struct.unpack_from(">H", record, FORM_OFFSETS[family])[0])


def with_saved_form(record: bytes | bytearray, game_id: str, form: int) -> bytes:
    """Copy one actual Deoxys record; write only its reserved form halfword."""
    family, species = _record(record, game_id)
    if species != DEOXYS or type(form) is not int or not 0 <= form < 4:
        raise ValueError("A Deoxys record and a valid form are required")
    offset = FORM_OFFSETS[family]
    previous = struct.unpack_from(">H", record, offset)[0]
    if previous and previous & FORM_MASK != FORM_TAG:
        raise ValueError("The native form reservation is already in use")
    output = bytearray(record)
    struct.pack_into(">H", output, offset, FORM_TAG | form)
    return bytes(output)


def form_reader(address: int, *, game_id: str) -> bytes:
    """PPC leaf ABI: r3=full native record -> r3=form; no memory writes.

    Only r0, r3, r11 and CR0 may change. An aligned complete record must fit
    inside MEM1 before any read. Foreign species and unmarked records return 0.
    """
    family = game_family(game_id)
    last = 0x81800000 - RECORD_SIZES[family]
    code = _Code(address)
    code.emit(0x7C6B1B78, 0x3C008000, 0x7C0B0040)  # mr r11,r3; lower bound
    code.conditional(0x41800000, "normal")
    code.emit(0x3C000000 | last >> 16, 0x60000000 | last & 0xFFFF,
              0x7C0B0040)
    code.conditional(0x41810000, "normal")
    code.emit(0x556007BE, 0x28000000)  # record alignment
    code.conditional(0x40820000, "normal")
    code.emit(0xA00B0000, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "normal")
    code.emit(0xA06B0000 | FORM_OFFSETS[family], 0x5460003A,
              0x28000000 | FORM_TAG)  # rlwinm r0,r3,0,0,29
    code.conditional(0x40820000, "normal")
    code.emit(0x546307BE, 0x4E800020)
    code.label("normal")
    code.emit(0x38600000, 0x4E800020)
    return code.finish()


def _bounds(code, register, size, fallback):
    last = 0x81800000 - size
    code.emit(0x3C008000, 0x7C000040 | register << 16)
    code.conditional(0x41800000, fallback)
    code.emit(0x3C000000 | last >> 16, 0x60000000 | last & 0xFFFF,
              0x7C000040 | register << 16)
    code.conditional(0x41810000, fallback)
    code.emit(0x540007BE | register << 21, 0x28000000)
    code.conditional(0x40820000, fallback)


def owned_form_reader(address: int, *, game_id: str, savedata_getter: int | None = None) -> bytes:
    """Read the latest captured form for a reduced Snag/DNA display record.

    ABI: r3=complete display record -> r3=form; preserve r4-r10/r12-r31/LR.
    Bounded party, PC, daycare and XD purification chamber scans require
    real species, saved Shadow ID and PID to
    match. A tagged owned record wins over the display's initial seed tag.
    Without a matching owned record, the display's own tag is the fallback.
    No owned or display record is written. External GBA storage is not scanned.
    """
    family = game_family(game_id)
    if savedata_getter is None:
        try:
            savedata_getter = SAVEDATA_GETTERS[game_id]
        except KeyError:
            raise ValueError("A regional native savedata accessor is required") from None
    if type(savedata_getter) is not int or not 0x80000000 <= savedata_getter < 0x81800000 or savedata_getter & 3:
        raise ValueError("Invalid native savedata accessor")
    size, offset = RECORD_SIZES[family], FORM_OFFSETS[family]
    pid, shadow, boxes = (4, 0xD8, 3) if family == "colosseum" else (0x28, 0xBA, 8)
    code = _Code(address)
    code.emit(0x9421FF90, 0x7C0802A6, 0x90010074)
    for register, slot in ((*((r, 0x10 + (r - 4) * 4) for r in range(4, 11)),
                           (12, 0x2C), *((r, 0x40 + (r - 26) * 4) for r in range(26, 32)))):
        code.emit(0x90010000 | register << 21 | slot)
    code.emit(0x7C7A1B78)
    _bounds(code, 26, size, "normal")
    code.emit(0xA01A0000, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "normal")
    code.emit(0xA39A0000 | shadow, 0x281C0000)
    code.conditional(0x41820000, "fallback")
    code.emit(0x281C0000 | (96 if family == "colosseum" else 83))
    code.conditional(0x41810000, "fallback")
    code.emit(0x837A0000 | pid, 0x38600000, 0x38800002)
    code.call(savedata_getter)
    _bounds(code, 3, 0x30 + 6 * size, "pc")
    code.emit(0x3BE30030, 0x3BA00006)
    code.label("party")
    code.jump("match_party")
    code.label("party_next")
    code.emit(0x3BFF0000 | size, 0x37BDFFFF)
    code.conditional(0x40820000, "party")
    code.label("pc")
    code.emit(0x38600000, 0x38800003)
    code.call(savedata_getter)
    _bounds(code, 3, boxes * (0x14 + 30 * size), "daycare")
    code.emit(0x3BE30014, 0x3BC00000 | boxes, 0x3BA0001E)
    code.label("box")
    code.jump("match_box")
    code.label("box_next")
    code.emit(0x3BFF0000 | size, 0x37BDFFFF)
    code.conditional(0x40820000, "box")
    code.emit(0x3BFF0014, 0x3BA0001E, 0x37DEFFFF)
    code.conditional(0x40820000, "box")
    code.label("daycare")
    code.emit(0x38600000, 0x3880000B)
    code.call(savedata_getter)
    _bounds(code, 3, 8 + size, "chamber" if family == "xd" else "fallback")
    code.emit(0x88030000, 0x28000000)
    code.conditional(0x41820000, "chamber" if family == "xd" else "fallback")
    code.emit(0x3BE30008)
    code.jump("match_daycare")
    if family == "xd":
        code.label("chamber")
        code.emit(0x38600000, 0x38800015)
        code.call(savedata_getter)
        _bounds(code, 3, 9 * 0x3D8, "fallback")
        code.emit(0x7C7F1B78, 0x3BC00009, 0x3BA00005)
        code.label("stage")
        code.jump("match_chamber")
        code.label("chamber_next")
        code.emit(0x3BFF00C4, 0x37BDFFFF)
        code.conditional(0x40820000, "stage")
        code.emit(0x3BFF0004, 0x3BA00005, 0x37DEFFFF)
        code.conditional(0x40820000, "stage")
        code.jump("fallback")
    matches = [("match_party", "party_next"), ("match_box", "box_next"),
               ("match_daycare", "chamber" if family == "xd" else "fallback")]
    if family == "xd":
        matches.append(("match_chamber", "chamber_next"))
    for label, next_label in matches:
        code.label(label)
        code.emit(0xA01F0000, 0x28000000 | DEOXYS)
        code.conditional(0x40820000, next_label)
        code.emit(0x801F0000 | pid, 0x7C00D840)
        code.conditional(0x40820000, next_label)
        code.emit(0xA01F0000 | shadow, 0x7C00E040)
        code.conditional(0x40820000, next_label)
        code.emit(0xA07F0000 | offset, 0x5460003A, 0x28000000 | FORM_TAG)
        code.conditional(0x40820000, next_label)
        code.emit(0x546307BE)
        code.jump("return")
    code.label("fallback")
    code.emit(0xA07A0000 | offset, 0x5460003A, 0x28000000 | FORM_TAG)
    code.conditional(0x40820000, "normal")
    code.emit(0x546307BE)
    code.jump("return")
    code.label("normal")
    code.emit(0x38600000)
    code.label("return")
    for register, slot in ((*((r, 0x10 + (r - 4) * 4) for r in range(4, 11)),
                           (12, 0x2C), *((r, 0x40 + (r - 26) * 4) for r in range(26, 32)))):
        code.emit(0x80010000 | register << 21 | slot)
    code.emit(0x80010074, 0x7C0803A6, 0x38210070, 0x4E800020)
    return code.finish()


def transform_tag_copy(address: int, continuation: int, *, game_id: str,
                       source: int, destination: int, displaced: int) -> bytes:
    """Propagate form only into the native temporary Transform Pokemon buffer.

    Call sites are after native species/stat field copying and before moves.
    The original party record is retained by the game's Hensin buffer swap.
    """
    family = game_family(game_id)
    size, offset = RECORD_SIZES[family], FORM_OFFSETS[family]
    code = _Code(address)
    _bounds(code, source, size, "native")
    _bounds(code, destination, size, "native")
    code.emit(0xA0000000 | source << 16, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "native")
    code.emit(0xA0000000 | destination << 16, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "native")
    code.emit(0xA1600000 | source << 16 | offset, 0x5560003A, 0x28000000 | FORM_TAG)
    code.conditional(0x41820000, "store")
    code.emit(0x39600000)
    code.label("store")
    code.emit(0xB1600000 | destination << 16 | offset)
    code.label("native")
    code.emit(displaced)
    from .engine.gift_move_hooks import branch
    code.emit(branch(address + len(code.words) * 4, continuation))
    return code.finish()
