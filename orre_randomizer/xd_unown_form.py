"""Use the seed's Unown form in XD's native model and portrait resolver."""

import struct

from .engine.analyze_game import FormatError


# DOL file offsets of pokemonGetAnnonKatati, shared by battle and field models and menu portraits.
_FORM_RESOLVER = {"GXXP01": 0x13EA04, "GXXE01": 0x13D140, "GXXJ01": 0x13854C}
_RETAIL_RESOLVER = bytes.fromhex(
    "5465a6b6 3880001c 50657632 5065d73a 506507be "
    "7c052396 7c0021d6 7c002850 5403063e 4e800020"
)


def patch_xd_unown_form(original: bytes, current: bytes, game_id: str, form: int) -> bytes:
    """Replace the native form result without modifying PID or shiny checks."""
    if type(form) is not int or not 0 <= form < 28:
        raise FormatError("invalid XD Unown form")
    offset = _FORM_RESOLVER[game_id]
    end = offset + len(_RETAIL_RESOLVER)
    if any(data[offset:end] != _RETAIL_RESOLVER for data in (original, current)):
        raise FormatError("unexpected XD Unown form resolver")
    output = bytearray(current)
    struct.pack_into(">II", output, offset, 0x38600000 | form, 0x4E800020)  # li r3,form; blr
    return bytes(output)
