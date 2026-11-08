"""Use the ROM's seed-selected Unown form in Colosseum's native renderers."""

import struct

from .analyze_game import FormatError
from .dol_regions import dol_layout


_FORM_RESOLVER_OFFSETS = {
    "GC6P01": 0x1234A8,
    "GC6E01": 0x11F334,
    "GC6J01": 0x11CAE0,
}
# pokemonGetAnnonKatati: extract four two-bit PID fields and reduce modulo 28.
# The model and portrait loaders call it after checking for Unown.
_NATIVE_RESOLVER = bytes.fromhex(
    "3c802492 5465a6b6 50657632 5065d73a 38044925 506507be 7c602816 7c032850 "
    "5400f87e 7c001a14 5400e13e 1c00001c 7c002850 5403063e 4e800020"
)


def patch_unown_form(original_dol: bytes, current_dol: bytes, form: int) -> bytes:
    """Return a fixed form from the native resolver while retaining Pokémon data."""
    if type(form) is not int or not 0 <= form < 28:
        raise ValueError("Unown form must be an index from 0 through 27")
    offset = _FORM_RESOLVER_OFFSETS[dol_layout(original_dol).game_id]
    end = offset + len(_NATIVE_RESOLVER)
    if original_dol[offset:end] != _NATIVE_RESOLVER or current_dol[offset:end] != _NATIVE_RESOLVER:
        raise FormatError("unexpected Colosseum Unown form resolver")

    # li r3, form; blr. The native shiny checks remain independent of this
    # display lookup, and Pokémon keep their original personality values.
    return current_dol[:offset] + struct.pack(">II", 0x38600000 | form, 0x4E800020) + current_dol[offset + 8:]
