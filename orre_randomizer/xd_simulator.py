"""Use the original species data in XD's fixed virtual battles."""

import struct

from .engine.analyze_game import FormatError, check_range, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_species_gameplay import SPECIES_STRIDE


_VIRTUAL_BATTLES = (13, 14)
# Species getter, encounter setter, r13 displacement, battle record stride.
_CONTRACTS = {
    "GXXP01": (0x8014793C, 0x8020F660, 0xBAF0, 0x4C),
    "GXXE01": (0x80146078, 0x8020D81C, 0xBAF0, 0x3C),
    "GXXJ01": (0x80141484, 0x80208278, 0xBAB0, 0x3C),
}
_RETURN_SPECIES_POINTER = 0x7C630214  # add r3,r3,r0


def _simulator_species_stub(address, continuation, encounter, native_table):
    code = _Code(address)
    table_address = address + 32
    code.emit(0xA08D0000 | encounter,  # lhz r4,current encounter(r13)
              0x3884FFF3,             # addi r4,r4,-13
              0x28040001)             # cmplwi r4,1
    code.conditional(0x41810000, "return_pointer")
    code.emit(0x3C600000 | (table_address >> 16), 0x60630000 | (table_address & 0xFFFF))
    code.label("return_pointer")
    code.emit(_RETURN_SPECIES_POINTER, branch(address + 28, continuation))
    stub = code.finish()
    if len(stub) != 32:
        raise AssertionError("unexpected XD simulator table alignment")
    padding = -len(native_table) % 32
    return stub + native_table + bytes(padding)


def protect_simulator_species(original_dol, current_dol, original_rel, symbols, game_id):
    """Keep the opening simulation, training lessons and Battle CDs native.

    The native encounter ID is set before the teams are constructed and cleared
    when the battle ends. The ordinary species pointer stays live for all other
    contexts. Neither the REL table nor the player's stored party is swapped.
    """
    getter, setter, encounter, stride = _CONTRACTS[game_id]
    getter_offset, setter_offset = getter - TEXT1_TO_RAM, setter - TEXT1_TO_RAM
    species_pointer = 0xA810 if game_id == "GXXJ01" else 0xA818
    getter_words = (0x808D0000 | (species_pointer - 4), 0x5463043E, 0x80040000,
                    0x7C030040, 0x4180000C, 0x38600000, 0x4E800020, 0x1C030124,
                    0x806D0000 | species_pointer, _RETURN_SPECIES_POINTER, 0x4E800020)
    state_words = (0xB06D0000 | encounter, 0x4E800020, 0xA06D0000 | encounter, 0x4E800020)
    for dol in (original_dol, current_dol):
        if (struct.unpack_from(">11I", dol, getter_offset) != getter_words
                or struct.unpack_from(">4I", dol, setter_offset) != state_words):
            raise FormatError("unexpected XD simulator species or encounter routine")
    battles = symbols[26]["offset"]
    battle_count = u32(original_rel, symbols[27]["offset"])
    if (battle_count != 442 or battles + battle_count * stride != symbols[28]["offset"]
            or tuple(original_rel[battles + battle * stride] for battle in _VIRTUAL_BATTLES) != (14, 15)):
        raise FormatError("unexpected XD virtual battle records")
    count = u32(original_rel, symbols[89]["offset"])
    start = symbols[88]["offset"]
    if count != 415:
        raise FormatError("unexpected XD simulator species count")
    check_range(original_rel, start, count * SPECIES_STRIDE, "XD simulator species data")
    native_table = original_rel[start:start + count * SPECIES_STRIDE]

    def build_stub(address, continuation):
        return _simulator_species_stub(address, continuation, encounter, native_table)

    patched, hooks = append_xd_dol_text(original_dol, current_dol, game_id, (
        (getter + 0x24, _RETURN_SPECIES_POINTER, build_stub),
    ))
    return patched, {"native_species_battles": list(_VIRTUAL_BATTLES), "hooks": hooks}
