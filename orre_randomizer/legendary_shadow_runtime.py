"""Specimen model and face routing for the verified retail executables."""
from __future__ import annotations

from hashlib import sha256
import struct

from .castform_layouts import LAYOUTS as RETAIL
from .castform_portraits import _reservation
from .deoxys import DEOXYS
from .deoxys_identity import FORM_OFFSETS, FORM_TAG, RECORD_SIZES, _bounds
from .engine.analyze_game import FormatError, u32
from .engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, _branch_target, branch
from .engine.postgame_lugia_face import _LAYOUTS as COLO_FACE
from .engine.postgame_lugia_model import _CEREMONY_GETTERS, _LAYOUTS as COLO_MODEL, _MENU_GETTERS
from .engine.shadow_lugia_face import _XD_GETTERS
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM
from .xd_deoxys_runtime import LAYOUTS as XD_RECORD
from .xd_shadow_lugia_model import _DISPLAY_CALLS, _HOOKS as XD_MODEL


def _tail(code, target):
    code.emit(branch(code.address + len(code.words) * 4, target))


def _load(code, register, word):
    code.emit(0x3C000000 | register << 21 | word >> 16,
              0x60000000 | register << 21 | register << 16 | word & 0xFFFF)


def _mr(source, dest):
    return 0x7C000378 | source << 21 | dest << 16 | source << 11


def _save(code):
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044, 0x7C000026, 0x90010034)
    for register in range(3, 13):
        code.emit(0x90010000 | register << 21 | (8 + (register - 3) * 4))


def _restore(code):
    for register in range(3, 13):
        code.emit(0x80010000 | register << 21 | (8 + (register - 3) * 4))
    code.emit(0x80010034, 0x7C0FF120, 0x80010044, 0x7C0803A6, 0x38210040)


def _record_selector(address, routes, *, xd, keep, predicate=None):
    """Read a full record. Return its allocated model marker, or zero."""
    family = 'xd' if xd else 'colosseum'
    code = _Code(address)
    _bounds(code, 3, RECORD_SIZES[family], 'ordinary')
    code.emit((0xA00300BA if xd else 0xA00300D8), 0x28000000)
    code.conditional(0x41820000, 'ordinary')
    code.emit(0x28000000 | (83 if xd else 96))
    code.conditional(0x41810000, 'ordinary')
    if not xd and not keep:
        code.emit(0x800300DC, 0x2C00FF9C)
        code.conditional(0x41820000, 'ordinary')
    code.emit(0xA0030000)
    for route in routes:
        if not route.form:
            code.emit(0x28000000 | route.species)
            code.conditional(0x41820000, f'species_{route.species}')
    code.jump('ordinary')
    for route in routes:
        if route.form:
            continue
        code.label(f'species_{route.species}')
        if route.species == DEOXYS:
            code.emit(0xA1630000 | FORM_OFFSETS[family], 0x5560003A, 0x28000000 | FORM_TAG)
            code.conditional(0x40820000, 'default_form')
            code.emit(0x556007BE)
            for variant in routes:
                if variant.species == DEOXYS and variant.form:
                    code.emit(0x28000000 | variant.form)
                    code.conditional(0x41820000, f'form_{variant.form}')
            code.label('default_form')
        code.emit(0x39600000 | route.model_key)
        code.jump('selected')
    for route in routes:
        if route.form:
            code.label(f'form_{route.form}')
            code.emit(0x39600000 | route.model_key)
            code.jump('selected')
    code.label('selected')
    if xd and not keep:
        code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x91610008)
        code.call(predicate)
        code.emit(0x81610008, 0x80010024, 0x7C0803A6, 0x38210020,
                  0x5460063E, 0x28000000)
        code.conditional(0x41820000, 'ordinary')
    code.emit(_mr(11, 3), 0x4E800020)
    code.label('ordinary')
    code.emit(0x38600000, 0x4E800020)
    return code.finish()


def _model_resource(address, fallback, continuation, routes, *, xd, replay=None):
    code = _Code(address)
    for route in routes:
        code.emit((0x281B0000 if xd else 0x28030000) | route.model_key)
        code.conditional(0x41820000, f'custom_{route.index}')
    if replay is not None:
        code.emit(replay)
    _tail(code, fallback)
    for route in routes:
        code.label(f'custom_{route.index}')
        code.emit(0x3BE00000 | route.group)
        register = 4 if xd else 30
        _load(code, register, route.model_resource(False))
        code.emit(0x281D0000 if xd else 0x281C0000)
        code.conditional(0x41820000, f'ready_{route.index}')
        _load(code, register, route.model_resource(True))
        code.label(f'ready_{route.index}')
        if xd:
            code.emit(0x3B600000 | route.species, 0x3BC00001, _mr(31, 3))
        else:
            code.emit(0x3B400000 | route.species, 0x3BA00001)
        _tail(code, continuation)
    return code.finish()


def _face_descriptor(address, fallback, routes, *, xd, kind, replay=None):
    code = _Code(address)
    for route in routes:
        for shiny in (False, True):
            code.emit(0x28030000 | route.face_key(shiny))
            code.conditional(0x41820000, f'custom_{route.index}_{int(shiny)}')
    if replay is not None:
        code.emit(replay)
    _tail(code, fallback)
    for route in routes:
        for shiny in (False, True):
            code.label(f'custom_{route.index}_{int(shiny)}')
            if kind == 'xd_crop':
                code.emit(0x38600345)
                if replay is not None:
                    code.emit(replay)
                _tail(code, fallback)
            else:
                if kind == 'crop':
                    code.emit(0x38600000 | int(shiny))
                else:
                    _load(code, 3, route.face_resource(shiny, xd=xd))
                code.emit(0x4E800020)
    return code.finish()


def _model_request(address, selector, fallback, owner, *, immediate=False, battle_getter=None):
    code = _Code(address)
    _save(code)
    code.emit(_mr(owner, 3))
    if battle_getter is not None:
        code.emit(0x28030000)
        code.conditional(0x41820000, 'native')
        code.emit(0x38800000, 0x38A000D6, 0x38C00000)
        code.call(battle_getter)
        code.emit(0x28030000)
        code.conditional(0x41820000, 'native')
        code.emit(0x38800000, 0x38A000CC, 0x38C00000)
        code.call(battle_getter)
    if not immediate:
        code.emit(0x28030000)
        code.conditional(0x41820000, 'native')
        code.emit(0xA0030000, 0x81610008, 0x7C005840)
        code.conditional(0x40820000, 'native')
    code.call(selector)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'native')
    code.emit(0x90610008)
    _restore(code)
    if immediate:
        code.emit(0x4E800020)
    else:
        _tail(code, fallback)
    code.label('native')
    _restore(code)
    _tail(code, fallback)
    return code.finish()


def _face_request(address, selector, fallback, owner, *, xd, end=None):
    code = _Code(address)
    _save(code)
    code.emit(_mr(owner, 3))
    code.call(selector)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'native')
    # Marker to face key: twice the route index, plus the native rarity flag.
    code.emit(0x38638C00, 0x5463083C, 0x38637500,
              (0x57C0063E if xd else 0x80C10014), 0x28000000 if xd else 0x28060000)
    code.conditional(0x41820000, 'ready')
    code.emit(0x38630001)
    code.label('ready')
    code.emit(0x90610008)
    _restore(code)
    if xd:
        _tail(code, end)
    else:
        code.emit(0x4E800020)
    code.label('native')
    _restore(code)
    if xd:
        code.emit(0x281F019A)
    _tail(code, fallback)
    return code.finish()


def _xd_menu_request(address, selector, continuation):
    code = _Code(address)
    _save(code)
    code.emit(_mr(31, 3))
    code.call(selector)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'native')
    code.emit(0xB07E0000)
    code.label('native')
    _restore(code)
    code.emit(0x80010024)
    _tail(code, continuation)
    return code.finish()


def _xd_ceremony_identity(address, selector, native, fallback):
    code = _Code(address)
    _save(code)
    code.call(selector)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'native')
    code.emit(0x90610048)  # Existing display-form cache in the ceremony frame.
    _restore(code)
    _tail(code, native)
    code.label('native')
    _restore(code)
    _tail(code, fallback)
    return code.finish()


def _xd_ceremony_model(address, native, fallback, routes):
    code = _Code(address)
    code.emit(0x80010008)
    for route in routes:
        code.emit(0x28000000 | route.model_key)
        code.conditional(0x41820000, f'custom_{route.index}')
    _tail(code, fallback)
    for route in routes:
        code.label(f'custom_{route.index}')
        code.emit(0x38600000 | route.model_key, 0x38800000 | route.form)
        _tail(code, native)
    return code.finish()


def _xd_snag_copy(address, fallback, routes):
    code = _Code(address)
    _bounds(code, 3, RECORD_SIZES['xd'], 'native')
    code.emit(0x281E0001)
    code.conditional(0x41800000, 'native')
    code.emit(0x281E0053)
    code.conditional(0x41810000, 'native')
    code.emit(0xA0030000)
    for species in sorted({route.species for route in routes}):
        code.emit(0x28000000 | species)
        code.conditional(0x41820000, 'preserve')
    code.jump('native')
    code.label('preserve')
    code.emit(_mr(30, 4))
    code.label('native')
    _tail(code, fallback)
    return code.finish()


def install_runtime(original, current, game_id, routes, *, keep=False):
    if not routes:
        return current, []
    if sha256(original).hexdigest() != RETAIL[game_id]['sha256']:
        raise FormatError('unrecognized regional legendary Shadow executable')
    xd = game_id in XD_MODEL
    base = TEXT1_TO_RAM if xd else TEXT_TO_RAM
    offset, ram, setter, store, code = _reservation(original, current, game_id)
    prior_size = len(code)
    output = bytearray(current[:offset])
    hooks = []

    def previous(hook, *, link=False):
        word = u32(current, hook - base)
        original_word = u32(original, hook - base)
        if word == original_word and not link:
            return hook + 4, word
        if word & 0xFC000003 != 0x48000000 | int(link):
            raise FormatError('unrecognized legendary Shadow hook chain')
        displacement = word & 0x03FFFFFC
        target = hook + displacement - (0x04000000 if displacement & 0x02000000 else 0)
        if word != original_word and not ram + 32 <= target < ram + prior_size:
            raise FormatError('legendary Shadow hook leaves the staged executable')
        return target, None

    def add(hook, builder, *, link=False):
        addr = ram + len(code)
        code.extend(builder(addr))
        struct.pack_into('>I', output, hook - base, branch(hook, addr, link=link))
        hooks.append({'address': hook, 'target': addr})

    selector = ram + len(code)
    predicate = None
    if xd:
        call = _DISPLAY_CALLS[game_id][0]
        predicate = _branch_target(call, u32(original, call - base))
    code.extend(_record_selector(selector, routes, xd=xd, keep=keep, predicate=predicate))
    if xd:
        member_load = XD_MODEL[game_id][0]
        early = member_load - 0x170
        target, replay = previous(early)
        if replay is None or replay & 0xFFFF0000 != 0x800D0000:
            raise FormatError('unexpected XD model bounds check')
        add(early, lambda a: _model_resource(a, target, member_load + 4, routes, xd=True, replay=replay))
        _, menu, face, battle, switch, ceremony, *_, native_pid, _, native_loader, _ = XD_RECORD[game_id]
        for call, owner in ((battle + 0xD0, 30), (switch + 0x154, 29)):
            target, _ = previous(call, link=True)
            if target != XD_RECORD[game_id][12]:
                raise FormatError('unexpected XD legendary battle model request')
            add(call, lambda a, n=target, r=owner: _model_request(a, selector, n, r), link=True)
        end = menu + 0xCC
        if u32(current, end - base) != 0x80010024:
            raise FormatError('unexpected XD legendary menu model request')
        add(end, lambda a: _xd_menu_request(a, selector, end + 4))
        face_call = face + 0xAC
        if u32(current, face_call - base) != 0x281F019A:
            raise FormatError('unexpected XD legendary specimen portrait request')
        add(face_call, lambda a: _face_request(a, selector, face_call + 4, 28, xd=True, end=face + 0x258))
        texture = _XD_GETTERS[game_id][0]
        descriptors = ((texture, 'texture'), (texture + 52, 'xd_crop'))
        pid_call, model_call = ceremony + 0x68, ceremony + 0x9C
        pid_fallback, _ = previous(pid_call, link=True)
        model_fallback, _ = previous(model_call, link=True)
        add(pid_call, lambda a: _xd_ceremony_identity(a, selector, native_pid, pid_fallback), link=True)
        add(model_call, lambda a: _xd_ceremony_model(a, native_loader, model_fallback, routes), link=True)
        if keep:
            snag_copy = _DISPLAY_CALLS[game_id][4]
            previous_snag, _ = previous(snag_copy, link=True)
            add(snag_copy, lambda a: _xd_snag_copy(a, previous_snag, routes), link=True)
    else:
        loader, _, battle, _ = COLO_MODEL[game_id]
        target, replay = previous(loader + 0x28)
        add(loader + 0x28, lambda a: _model_resource(a, target, loader + 0x14C, routes, xd=False, replay=replay))
        target, _ = previous(battle, link=True)
        first, second, getter = _MENU_GETTERS[game_id]
        add(battle, lambda a: _model_request(a, selector, target, 30, battle_getter=getter), link=True)
        for call in (first, second, *((_CEREMONY_GETTERS[game_id],) if keep else ())):
            target, _ = previous(call, link=True)
            add(call, lambda a, n=target: _model_request(a, selector, n, 31, immediate=True), link=True)
        faces, texture, crop, _ = COLO_FACE[game_id]
        for index, call in enumerate(faces):
            target, _ = previous(call, link=True)
            owner = (28, 28, 30, 27, 28)[index // 2]
            add(call, lambda a, n=target, r=owner: _face_request(a, selector, n, r, xd=False), link=True)
        descriptors = ((texture, 'texture'), (crop, 'crop'))
    for hook, kind in descriptors:
        target, replay = previous(hook)
        add(hook, lambda a: _face_descriptor(a, target, routes, xd=xd, kind=kind, replay=replay))
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError('legendary Shadow appearance hooks exceed the native arena')
    code[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    for position, word in ((8, offset), (0x50, ram), (0x98, len(code)), (setter - base, branch(setter, ram))):
        struct.pack_into('>I', output, position, word)
    return bytes(output), hooks
