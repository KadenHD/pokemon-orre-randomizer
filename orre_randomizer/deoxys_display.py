"""Resolve temporary Snag/DNA Deoxys displays against owned party/PC records."""
from __future__ import annotations

import struct

from .castform_portraits import _reservation
from .deoxys_identity import FORM_TAG, form_offset, owned_form_reader
from .engine.analyze_game import FormatError
from .engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch


def install_display_reader(original, current, game_id):
    offset, ram, setter, store, code = _reservation(original, current, game_id)
    address = ram + len(code)
    code.extend(owned_form_reader(address, game_id=game_id))
    code.extend(bytes(-len(code) % 32))
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError('Deoxys display resolver exceeds the reserved arena')
    code[:32] = _arena_guard(end, store)
    output = bytearray(current[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    base = 0x800030A0 if game_id.startswith('GXX') else TEXT_TO_RAM
    for position, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                            (setter - base, branch(setter, ram))):
        struct.pack_into('>I', output, position, value)
    return bytes(output), {'address': address, 'bytes': len(code) - (address - ram),
        'owned_lookup': 'party, PC, Day Care and XD Purify Chamber; exact Shadow ID and PID',
        'writes_saved_data': False}


def emit_fake_form(code, game_id, forms, reader, *, shadow_register, pointer_stack=8,
                   result_stack=0x18, write_pid=False, label='deoxys_display'):
    """After a native constructor/setter, tag only its temporary display record.

    A valid current owned tag takes precedence over the original seeded form.
    Preserve the enclosing native call's r3 return value in unused caller space.
    """
    if not forms:
        return
    if type(reader) is not int or not 0x80000000 <= reader < 0x81800000:
        raise FormatError('Missing Deoxys display resolver')
    if any(type(sid) is not int or not 1 <= sid <= 96 or type(form) is not int or not 0 <= form < 4
           for sid, form in forms.items()):
        raise FormatError('Invalid Deoxys display form metadata')
    xd = game_id.startswith('GXX')
    form_at, shadow_at, pid_at = form_offset(game_id), (0xBA if xd else 0xD8), (0x28 if xd else 4)
    done = label + '_done'
    code.emit(0x90610000 | result_stack, 0x81610000 | pointer_stack,
              0xA00B0000, 0x2800019A)
    code.conditional(0x40820000, done)
    for sid in sorted(forms):
        code.emit(0x28000000 | shadow_register << 16 | sid)
        code.conditional(0x41820000, label + '_' + str(sid))
    code.jump(done)
    for sid, form in sorted(forms.items()):
        code.label(label + '_' + str(sid))
        code.emit(0x38000000 | FORM_TAG | form, 0xB00B0000 | form_at,
                  0x38000000 | sid, 0xB00B0000 | shadow_at)
        if write_pid:
            code.emit(0x906B0000 | pid_at)
        code.emit(0x7D635B78)
        code.call(reader)
        code.emit(0x60630000 | FORM_TAG, 0x81610000 | pointer_stack,
                  0xB06B0000 | form_at)
        code.jump(done)
    code.label(done)
    code.emit(0x80610000 | result_stack)
