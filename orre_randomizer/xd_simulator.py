"""Use original species traits in XD's fixed rental encounters."""

import struct

from .engine.analyze_game import FormatError, check_range, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_species_gameplay import SPECIES_STRIDE


_FIXED_RENTAL_BATTLES = (12, 13, 14)
# Species getter, encounter setter, r13 displacement, battle record stride.
_CONTRACTS = {
    "GXXP01": (0x8014793C, 0x8020F660, 0xBAF0, 0x4C),
    "GXXE01": (0x80146078, 0x8020D81C, 0xBAF0, 0x3C),
    "GXXJ01": (0x80141484, 0x80208278, 0xBAB0, 0x3C),
}
_RETURN_SPECIES_POINTER = 0x7C630214  # add r3,r3,r0
# Floor-manager SDA pointer and the four retail getters defining its layout.
_FLOOR_CONTRACTS = {
    "GXXP01": (0xB338, 0x80127BB8, 0x80128CF0, 0x801292F8, 0x801294C0),
    "GXXE01": (0xB330, 0x801262FC, 0x80127434, 0x80127A3C, 0x80127C04),
    "GXXJ01": (0xB300, 0x8012171C, 0x80122840, 0x80122E48, 0x80123010),
}
_BINGO_MENU_FLOORS = (0x388, 0x38B)
_OBJECT_GETTERS = {"GXXP01": 0x8014D228, "GXXE01": 0x8014B964, "GXXJ01": 0x80146CC0}


def _simulator_species_stub(address, continuation, encounter, native_table,
                            floor_pointer, species_pointer, *, native_table_address=None):
    code = _Code(address)
    code.emit(0xA08D0000 | encounter,  # lhz r4,current encounter(r13)
              0x3884FFF4,             # addi r4,r4,-12
              0x28040002)             # cmplwi r4,2
    code.conditional(0x40810000, "native")  # ble: Bingo, CD or training battle
    code.emit(0x3884000C, 0x28040000)  # restore encounter; cmplwi r4,0
    code.conditional(0x40820000, "randomized")
    # Bingo builds and displays its rentals before encounter12 is active.
    # Read the current overlay without calling native routines or changing it.
    code.emit(0x806D0000 | floor_pointer, 0x28030000)
    code.conditional(0x41820000, "randomized")  # uninitialized manager
    code.emit(0x80630004, 0x28030000)  # manager->stack list
    code.conditional(0x41820000, "randomized")
    code.emit(0x80830004, 0x2C040000)  # signed current index
    code.conditional(0x41800000, "randomized")
    code.emit(0x80630008, 0x7C041840)  # capacity; cmplw r4,r3
    code.conditional(0x40800000, "randomized")  # index >= capacity
    # Reload the stable list after comparing capacity, using only r3/r4.
    code.emit(0x1C840224, 0x806D0000 | floor_pointer,
              0x80630004, 0x80630000, 0x28030000)
    code.conditional(0x41820000, "randomized")
    code.emit(0x7C632214, 0x80830004, 0x28040388)
    code.conditional(0x41820000, "native")
    code.emit(0x2804038B)
    code.conditional(0x41820000, "native")
    code.label("randomized")
    code.emit(0x806D0000 | species_pointer)
    code.jump("return_pointer")
    code.label("native")
    table_fixup = len(code.words)
    code.emit(0, 0)
    code.label("return_pointer")
    code.emit(_RETURN_SPECIES_POINTER)
    code.emit(branch(address + len(code.words) * 4, continuation))
    table_address = (native_table_address if native_table_address is not None
                     else address + len(code.finish()))
    code.words[table_fixup] = 0x3C600000 | (table_address >> 16)
    code.words[table_fixup + 1] = 0x60630000 | (table_address & 0xFFFF)
    stub = code.finish()
    if native_table_address is not None:
        return stub
    padding = -len(native_table) % 32
    return stub + native_table + bytes(padding)


def protect_simulator_species(original_dol, current_dol, original_rel, symbols, game_id):
    """Keep Battle Bingo, the opening simulation, lessons and Battle CDs native.

    Battle IDs protect the fixed encounters. The two Bingo overlays also need
    native traits while constructing rentals and displaying the grid between
    battles, when the encounter ID is zero. Other menus and battles use the
    randomized table. Neither the REL nor stored Pokemon are swapped.
    """
    getter, setter, encounter, stride = _CONTRACTS[game_id]
    getter_offset, setter_offset = getter - TEXT1_TO_RAM, setter - TEXT1_TO_RAM
    species_pointer = 0xA810 if game_id == "GXXJ01" else 0xA818
    floor_pointer, floor_getter, manager_getter, stack_getter, id_getter = _FLOOR_CONTRACTS[game_id]
    object_getter = _OBJECT_GETTERS[game_id]
    object_words = (0x9421FFF0, 0x7C0802A6, 0x90010014, 0x4BFFFF0D,
                    0x808D0000 | (species_pointer - 4), 0x5463043E, 0x80040000,
                    0x7C030040, 0x4180000C, 0x38600000, 0x48000010,
                    0x1C030124, 0x806D0000 | species_pointer, _RETURN_SPECIES_POINTER,
                    0x80010014, 0x7C0803A6, 0x38210010, 0x4E800020)
    floor_windows = (
        (floor_getter, (0x9421FFF0, 0x7C0802A6, 0x90010014, 0x806D0000 | floor_pointer)),
        (manager_getter, (0x9421FFF0, 0x7C0802A6, 0x90010014, 0x80630004)),
        (stack_getter, (0x80030004, 0x80630000, 0x1C000224, 0x7C630214, 0x4E800020)),
        (id_getter, (0x80630004, 0x4E800020)),
    )
    getter_words = (0x808D0000 | (species_pointer - 4), 0x5463043E, 0x80040000,
                    0x7C030040, 0x4180000C, 0x38600000, 0x4E800020, 0x1C030124,
                    0x806D0000 | species_pointer, _RETURN_SPECIES_POINTER, 0x4E800020)
    state_words = (0xB06D0000 | encounter, 0x4E800020, 0xA06D0000 | encounter, 0x4E800020)
    for dol in (original_dol, current_dol):
        if (struct.unpack_from(">18I", dol, object_getter - TEXT1_TO_RAM) != object_words
                or struct.unpack_from(">2I", dol, object_getter - 0xE8 - TEXT1_TO_RAM)
                != (0xA0630000, 0x4E800020)):
            raise FormatError("unexpected XD Pokemon object species routine")
        for location, words in floor_windows:
            if struct.unpack_from(f">{len(words)}I", dol, location - TEXT1_TO_RAM) != words:
                raise FormatError("unexpected XD Bingo floor-manager routine")
        if (struct.unpack_from(">11I", dol, getter_offset) != getter_words
                or struct.unpack_from(">4I", dol, setter_offset) != state_words):
            raise FormatError("unexpected XD simulator species or encounter routine")
    battles = symbols[26]["offset"]
    battle_count = u32(original_rel, symbols[27]["offset"])
    if (battle_count != 442 or battles + battle_count * stride != symbols[28]["offset"]
            or tuple(original_rel[battles + battle * stride]
                     for battle in _FIXED_RENTAL_BATTLES) != (13, 14, 15)):
        raise FormatError("unexpected XD fixed rental battle records")
    count = u32(original_rel, symbols[89]["offset"])
    start = symbols[88]["offset"]
    if count != 415:
        raise FormatError("unexpected XD simulator species count")
    check_range(original_rel, start, count * SPECIES_STRIDE, "XD simulator species data")
    native_table = original_rel[start:start + count * SPECIES_STRIDE]
    padded_table_size = (len(native_table) + 31) & ~31

    shared_table = []

    def build_stub(address, continuation):
        payload = _simulator_species_stub(address, continuation, encounter, native_table,
                                          floor_pointer, species_pointer)
        shared_table.append(address + len(payload) - padded_table_size)
        return payload

    def build_object_stub(address, continuation):
        # This accessor inlines the species lookup, bypassing the first hook.
        # Keep its own stack/LR epilogue; share only the immutable native data.
        return _simulator_species_stub(address, continuation, encounter, b"",
                                       floor_pointer, species_pointer,
                                       native_table_address=shared_table[0])

    patched, hooks = append_xd_dol_text(original_dol, current_dol, game_id, (
        (getter + 0x24, _RETURN_SPECIES_POINTER, build_stub),
        (object_getter + 0x34, _RETURN_SPECIES_POINTER, build_object_stub),
    ))
    header_size = hooks[0]["stub_size"] - padded_table_size
    return patched, {"native_species_battles": list(_FIXED_RENTAL_BATTLES),
                     "native_species_floors": list(_BINGO_MENU_FLOORS),
                     "native_species_table_offset": header_size, "hooks": hooks}
