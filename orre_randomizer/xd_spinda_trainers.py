"""Share exact per-DPKM Spinda personalities between XD battles and scenes."""

from dataclasses import dataclass
from itertools import count
import struct

from .engine.analyze_game import FormatError, u32
from .engine.gift_move_hooks import branch
from .engine.inspect_tables import u16
from .engine.shiny_rules import _Code
from .engine.spinda import SPINDA, spinda_pid_seed
from .xd_battle_rules import DPKM_STRIDE, TEXT1_TO_RAM, _deck_teams, append_xd_dol_text
from .xd_spinda import _load_address, _tail_call


@dataclass(frozen=True)
class _Layout:
    register: int
    register_store: int
    slot_lookup: int
    native_lookup: int
    ordinary: tuple[int, int]
    native_pid: int


_LAYOUTS = {
    "GXXP01": _Layout(0x8028D1E4, 0x900DBD3C, 0x801FD9C4, 0x8028CE44,
                       (0x801FDC2C, 0x801FDCF0), 0x80142E04),
    "GXXE01": _Layout(0x8028B2A8, 0x900DBD3C, 0x801FBC90, 0x8028AF08,
                       (0x801FBEF8, 0x801FBFBC), 0x80141540),
    "GXXJ01": _Layout(0x80285CD0, 0x900DBCEC, 0x801F6954, 0x80285930,
                       (0x801F6BBC, 0x801F6C80), 0x8013C94C),
}


def spinda_deck_pids(deck, shadow_slots, seed, deck_name):
    """Build exact normal opponent PIDs for each referenced Spinda row."""
    start, _, ordinary = _deck_teams(deck, shadow_slots)
    pids, used = {}, set()
    for index in sorted(ordinary):
        position = start + DPKM_STRIDE * index
        if u16(deck, position) != SPINDA:
            continue
        key = f"xd:{deck_name}:trainer:{index}"
        encoded, random_traits = deck[position + 0x1E:position + 0x20]
        gender, nature = (encoded >> 1) & 3, encoded >> 3
        if random_traits & 0x80:
            gender, nature = None, None
        elif gender > 2 or nature >= 25:
            raise FormatError("unexpected XD Spinda opponent personality constraint")
        elif gender == 2:
            # Retail keeps the gender from its initial random personality.
            # Choose that otherwise random value reproducibly per encounter.
            gender = spinda_pid_seed(seed, key) >> 31
        for attempt in count():
            pid = spinda_pid_seed(seed, f"{key}:{attempt}")
            if pid and pid not in used and (gender is None or int((pid & 0xFF) < 127) == gender) and (
                    nature is None or pid % 25 == nature):
                pids[index] = pid
                used.add(pid)
                break
    return pids


def _deck_hook(address, continuation, instruction, state):
    code = _Code(address)
    code.emit(instruction)
    _load_address(code, 12, state)
    code.emit(0x93EC0000)  # r31 is the resource ID whose DPKM pointer is installed
    _tail_call(code, continuation)
    return code.finish() + bytes(32)


def _slot_hook(address, lookup):
    code = _Code(address)
    # The constructor's audited frame keeps 0x38 as padding between its IV
    # table and its saved nonvolatile registers. Save the active DPKM index.
    code.emit(0x90610038)
    _tail_call(code, lookup)
    return code.finish()


def _trainer_pid_hook(address, native, state, rows):
    data = address + 0xA0
    code = _Code(address)
    code.emit(0x28120000 | SPINDA)  # r18 is the constructed Pokémon species
    code.conditional(0x40820000, "native")
    _load_address(code, 12, state)
    code.emit(0x818C0000, 0x81610038)  # active deck resource and DPKM index
    _load_address(code, 10, data)
    code.emit(0x39200000 | len(rows))
    code.label("search")
    code.emit(0x810A0000, 0x7C086040)
    code.conditional(0x40820000, "next")
    code.emit(0x810A0004, 0x7C085840)
    code.conditional(0x41820000, "match")
    code.label("next")
    code.emit(0x394A000C, 0x3529FFFF)
    code.conditional(0x40820000, "search")
    code.label("native")
    _tail_call(code, native)
    code.label("match")
    code.emit(0x812A0008, 0x9421FFE0, 0x7C0802A6, 0x90010024, 0x91210008)
    code.call(native)  # preserve unrelated RNG effects
    # The native fight setup checks the full party and chooses a nonshiny
    # enemy OT before the model is shown. It never changes the prepared PID.
    code.emit(0x80610008, 0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    payload = code.finish()
    if len(payload) > data - address:
        raise FormatError("XD Spinda trainer hook overlaps its PID table")
    encoded = b"".join(struct.pack(">III", *row) for row in rows)
    return payload + bytes(data - address - len(payload)) + encoded + bytes(-len(encoded) % 32)


def apply_spinda_trainer_pids(original, current, game_id, decks):
    rows = [(resource, slot, pid) for resource, pids in sorted(decks.items())
            for slot, pid in sorted(pids.items())]
    if not rows:
        return current, []
    if len(rows) > 0x7FFF or any(not 0 < resource <= 0xFFFFFFFF or not 0 < slot <= 0xFFFF
                                or not 0 < pid <= 0xFFFFFFFF for resource, slot, pid in rows):
        raise ValueError("invalid XD Spinda opponent personality table")
    layout = _LAYOUTS[game_id]
    lookup = branch(layout.slot_lookup, layout.native_lookup, link=True)
    signatures = {
        layout.register - 8: (0x38030010, layout.register_store + 0x00800010,
                              layout.register_store, 0x38610008),
        layout.slot_lookup - 8: (0x90810024, 0x90010028, lookup, 0x7C7A1B78),
        **{call - 4: (0x38C00000, branch(call, layout.native_pid, link=True), 0x7C641B78)
           for call in layout.ordinary},
    }
    for address, words in signatures.items():
        offset = address - TEXT1_TO_RAM
        if tuple(u32(original, offset + i * 4) for i in range(len(words))) != words:
            raise FormatError(f"unexpected XD Spinda opponent instruction at {address:#x}")

    def register_hook(address, continuation):
        return _deck_hook(address, continuation, layout.register_store, address + 0x20)

    patched, register = append_xd_dol_text(original, current, game_id, (
        (layout.register, layout.register_store, register_hook),
    ))
    state = register[0]["stub_address"] + 0x20
    patched, calls = append_xd_dol_text(original, patched, game_id, (
        (layout.slot_lookup, lookup, lambda address, _continuation: _slot_hook(address, layout.native_lookup)),
        *((call, branch(call, layout.native_pid, link=True), lambda address, _continuation:
           _trainer_pid_hook(address, layout.native_pid, state, rows)) for call in layout.ordinary),
    ), link=True)
    return patched, [*register, *calls]
