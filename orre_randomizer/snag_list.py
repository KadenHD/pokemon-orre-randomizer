"""Display saved Shadow identities in the games' Snag List model panels.

Retail lists build throwaway Pokémon with an unrelated never-shiny PID. These
display-only hooks reuse the already generated Shadow PID and the player's OT.
They never regenerate a Shadow Pokémon or write its saved record.
"""
from __future__ import annotations

import hashlib
import struct

from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, _branch_target, branch
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_shadow_shinies import _LAYOUTS as XD_IDENTITIES
from .xd_spinda import _load_address
from .xd_spinda_field import _LAYOUTS as XD_SHADOW_STATE

VERSION = "saved-shadow-snag-list-v3"

# Checked call windows in the six revision-0 DOLs. The Colosseum caller keeps
# the selected Shadow ID in r20; XD keeps its ID in r30 and DarkPokemon* in r31.
_COLO_HOOKS = {"GC6P01": 0x8003ED64, "GC6E01": 0x8003CA90, "GC6J01": 0x8003BDF0}
# The D-pad redraw is a separate retail constructor. Its selected ID and
# purification mode live in r28/r27, rather than the opening path's r20/r21.
_COLO_NAVIGATION = {"GC6P01": (0x8003E13C, 0x3BC8),
                    "GC6E01": (0x8003BE68, 0x6748),
                    "GC6J01": (0x8003B1D0, 0x2E40)}
_XD_HOOKS = {"GXXP01": 0x80050B08, "GXXE01": 0x800509B8, "GXXJ01": 0x8004F590}
_COLO_CACHE_HOOKS = {"GC6P01": 0x8003F2D8, "GC6E01": 0x8003D004, "GC6J01": 0x8003C364}
_COLO_COUNTERS = {"GC6P01": (0x801F3A88, 0x801F3AE8),
                  "GC6E01": (0x801EF214, 0x801EF274),
                  "GC6J01": (0x801EAAD4, 0x801EAB34)}
_COUNTER_PREFIX = bytes.fromhex('9421fff07c0802a690010014bfc100083bc000003be000014800001c7fe3fb78')
_COUNTER_SUFFIX = bytes.fromhex(
    '5460063f418200083bde00013bff0001806d874857e4043e800300007c040040'
    '4180ffd87fc3f378bbc10008800100147c0803a6382100104e800020')
_BONUS_SHADOW = 96
_LUGIA = 249


def _original_completion_stub(address, getter):
    """Exclude bonus96 only within original-roster completion counters."""
    code = _Code(address)
    code.emit(0x28030000 | _BONUS_SHADOW)
    code.conditional(0x40820000, 'native')
    code.emit(0x38600000, 0x4E800020)
    code.label('native')
    code.emit(branch(address+len(code.words)*4, getter))
    return code.finish()


def _colo_identity_stub(address, setter, saved_pid, generated, player_pointer, captured,
                        *, custom_shadow_shinies=False, shadow_register=20, deoxys_forms=None,
                        deoxys_reader=None, game_id='GC6P01'):
    if shadow_register not in (20, 28):
        raise FormatError("invalid native Snag List identity register")
    selected = 0x7C030378 | shadow_register << 21 | shadow_register << 11  # mr r3, selected
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native_tail")
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x90610008, 0x9081000C)
    _load_address(code, 11, player_pointer)
    code.emit(0x816B0000, 0x280B0000)
    code.conditional(0x41820000, "assign")
    code.emit(0x816B009C, 0x91610010)  # current player OT
    if not custom_shadow_shinies:
        code.emit(selected)
        code.call(captured)
        code.emit(0x5460063E, 0x28000001)
        code.conditional(0x40820000, "assign")
    code.emit(selected)
    code.call(generated)
    code.emit(0x5460063E, 0x28000001)
    code.conditional(0x40820000, "assign")
    code.emit(selected)
    code.call(saved_pid)
    code.emit(0x9061000C, 0x80610008, 0x81610010, 0x91630014)
    code.label("assign")
    code.emit(0x80610008, 0x8081000C)
    code.call(setter)
    if deoxys_forms:
        from .deoxys_display import emit_fake_form
        emit_fake_form(code, game_id, deoxys_forms, deoxys_reader, shadow_register=shadow_register)
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    code.label("native_tail")
    code.emit(branch(address + len(code.words) * 4, setter))
    return code.finish()


def _xd_identity_stub(address, generator, player_lookup, generated, *, custom_shadow_shinies=False,
                       deoxys_forms=None, deoxys_reader=None, game_id='GXXP01'):
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native_tail")
    code.emit(0x281F0000)  # a missing native record keeps the original generator
    code.conditional(0x41820000, "native_tail")
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044,
              0x90610008, 0x9081000C, 0x90A10010, 0x90C10014, 0x90E10018,
              0x7FC3F378)
    code.call(generated)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    if not custom_shadow_shinies:
        # DarkPokemon::isSnach tests status >= 3. Its native status getter
        # extracts the top three bits of byte zero, independently of its PID.
        code.emit(0x881F0000, 0x5400DEFE, 0x28000003)
        code.conditional(0x41800000, "native")
    code.emit(0x38600000, 0x38800002)
    code.call(player_lookup)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    code.emit(0x8083002C, 0x80610008, 0x90830024, 0x807F001C)
    code.jump("return")
    code.label("native")
    code.emit(0x80610008, 0x8081000C, 0x80A10010, 0x80C10014, 0x80E10018)
    code.call(generator)
    code.label("return")
    if deoxys_forms:
        from .deoxys_display import emit_fake_form
        emit_fake_form(code, game_id, deoxys_forms, deoxys_reader, shadow_register=30,
                       result_stack=0x1C, write_pid=True)
    code.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    code.label("native_tail")
    code.emit(branch(address + len(code.words) * 4, generator))
    return code.finish()


def _bonus_cache_stub(address, reader, species=_LUGIA):
    """Let an old save discover new Shadow 96 through native seen-state filtering."""
    if type(species) is not int or not 1 <= species <= 411:
        raise FormatError("invalid bonus Shadow species for the Snag List")
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x90610008)
    code.call(reader)
    code.emit(0x28030000)
    code.conditional(0x40820000, "return")
    code.emit(0x80010008, 0x28000000 | _BONUS_SHADOW)
    code.conditional(0x40820000, "return")
    code.emit(0x38600000 | species)
    code.label("return")
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    return code.finish()


def _bonus_model_stub(address, request, *, shadow_register=20, mode_register=21):
    """Give every temporary Lugia its selected Shadow ID and purified state."""
    if (shadow_register, mode_register) not in ((20, 21), (28, 27)):
        raise FormatError("invalid native Snag List display registers")
    code = _Code(address)
    code.emit(0x28000000 | shadow_register << 16)
    code.conditional(0x41820000, "native")
    code.emit(0x28000061 | shadow_register << 16)
    code.conditional(0x40800000, "native")
    code.emit(0x28040000)
    code.conditional(0x41820000, "native")
    code.emit(0xA0040000, 0x28000000 | _LUGIA)
    code.conditional(0x40820000, "native")
    code.emit(0xB00400D8 | shadow_register << 21,
              0x2C000001 | mode_register << 16)
    code.conditional(0x40820000, "native")
    code.emit(0x3800FF9C, 0x900400DC)  # native fully purified gauge: -100
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, request))
    return code.finish()


def _append_colo(original, current, region, hook, expected, builder):
    """Extend the same guarded text2 arena used by Colosseum's other hooks."""
    offset = (len(original) + 31) & ~31
    arena_offset = region.set_arena_lo - TEXT_TO_RAM
    previous_size = u32(current, 0x98)
    if previous_size:
        if ((u32(current, 0x08), u32(current, 0x50)) != (offset, region.section_ram)
                or previous_size % 32 or offset + previous_size != len(current)
                or u32(current, arena_offset) != branch(region.set_arena_lo, region.section_ram)
                or current[offset:offset + 32] != _arena_guard(
                    region.section_ram + previous_size, region.arena_lo_store)):
            raise FormatError("invalid Colosseum reservation before Snag List hook")
        payload = bytearray(current[offset:])
    else:
        if (len(current) != len(original) or any(u32(current, p) for p in (0x08, 0x50))
                or u32(current, arena_offset) != region.arena_lo_store):
            raise FormatError("invalid Colosseum layout before Snag List hook")
        payload = bytearray(32)
    position = hook - TEXT_TO_RAM
    if any(u32(data, position) != expected for data in (original, current)):
        raise FormatError("unexpected Colosseum Snag List PID call")
    address = region.section_ram + len(payload)
    code = builder(address)
    payload.extend(code)
    end = region.section_ram + len(payload)
    descriptor = parse_dol(original)
    if descriptor["bss_ram_address"] + descriptor["bss_size"] >= region.section_ram or end >= 0x81700000:
        raise FormatError("Snag List hook exceeds Colosseum's available arena")
    payload[:32] = _arena_guard(end, region.arena_lo_store)
    output = bytearray(current[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(payload)
    for pos, value in ((0x08, offset), (0x50, region.section_ram), (0x98, len(payload)),
                       (arena_offset, branch(region.set_arena_lo, region.section_ram)),
                       (position, branch(hook, address, link=True))):
        struct.pack_into(">I", output, pos, value)
    return bytes(output), [{"hook_address": hook, "stub_address": address, "stub_size": len(code)}]


def apply_snag_list_identities(original, current, game_id, *, custom_shadow_shinies=False,
                               postgame_shadow_lugia=False, bonus_species=_LUGIA,
                               deoxys_forms=None, deoxys_reader=None):
    """Patch temporary list models only; a missing/generated-false record stays native."""
    if game_id in _COLO_HOOKS:
        region = dol_layout(original)
        if region.game_id != game_id:
            raise FormatError("Colosseum Snag List region does not match its executable")
        hook = _COLO_HOOKS[game_id]
        position = hook - TEXT_TO_RAM
        # These are the actual native getter and setter selected by this caller,
        # not addresses inferred by shifting another region's functions.
        saved_pid = _branch_target(hook - 12, u32(original, position - 12))
        setter = _branch_target(hook, u32(original, position))
        generated_call = region.trainer_function + 0x42C
        generated = _branch_target(generated_call, u32(original, generated_call - TEXT_TO_RAM))
        captured_call = hook - 0x70
        captured = _branch_target(captured_call, u32(original, captured_call - TEXT_TO_RAM))
        expected = (0x82FD0098, 0x7E83A378, branch(hook - 12, saved_pid, link=True),
                    0x7F63DB78, 0x7EE4BB78, branch(hook, setter, link=True), 0x2C150001)
        for data in (original, current):
            if struct.unpack_from(">7I", data, position - 20) != expected:
                raise FormatError("unexpected Colosseum Snag List display window")
        output, hooks = _append_colo(original, current, region, hook, expected[5],
            lambda address: _colo_identity_stub(address, setter, saved_pid, generated, region.player_pointer,
                                                captured, custom_shadow_shinies=custom_shadow_shinies,
                                                deoxys_forms=deoxys_forms, deoxys_reader=deoxys_reader, game_id=game_id))
        if postgame_shadow_lugia:
            cache_hook = _COLO_CACHE_HOOKS[game_id]
            cache_position = cache_hook - TEXT_TO_RAM
            reader = _branch_target(cache_hook, u32(original, cache_position))
            cache_expected = (0x381D0001, 0x5403043E, branch(cache_hook, reader, link=True),
                              0x7C7B1B78, 0x5760043E, 0x28000000, 0x41820094)
            for data in (original, output):
                if (struct.unpack_from(">7I", data, cache_position - 8) != cache_expected
                        or u32(data, cache_position - 0xBC) != 0x38600060):
                    raise FormatError("unexpected native Colosseum Snag List allocation or builder")
            output, bonus_hooks = _append_colo(original, output, region, cache_hook, cache_expected[2],
                                               lambda address: _bonus_cache_stub(address, reader, bonus_species))
            hooks.extend(bonus_hooks)
            # Native title/PC/save totals scan all96 slots. The bonus keeps its
            # actual flags and list entry, but must not turn original48 into49.
            for counter, flag_field in zip(_COLO_COUNTERS[game_id], (0x14, 0x12), strict=True):
                counter_hook = counter+0x20
                getter = _branch_target(counter_hook, u32(original, counter_hook-TEXT_TO_RAM))
                expected_call = branch(counter_hook, getter, link=True)
                expected_body = _COUNTER_PREFIX+struct.pack('>I', expected_call)+_COUNTER_SUFFIX
                if u32(original, getter-TEXT_TO_RAM+0x34) != 0xA0640000 | flag_field:
                    raise FormatError('unexpected native completion-counter flag reader')
                for data in (original, output):
                    if data[counter-TEXT_TO_RAM:counter-TEXT_TO_RAM+96] != expected_body:
                        raise FormatError('unexpected native original-roster completion counter')
                output, counter_hooks = _append_colo(original, output, region, counter_hook, expected_call,
                    lambda address, reader=getter: _original_completion_stub(address, reader))
                hooks.extend(counter_hooks)
        # Retail uses placeholder ID1 before purification and clears it after.
        # Only this throwaway Lugia display receives the actual selected ID.
        model_hook = hook + 0x60
        model_position = model_hook - TEXT_TO_RAM
        request = _branch_target(model_hook, u32(original, model_position))
        model_window = struct.unpack_from(">3I", original, model_position - 8)
        if (model_window[0] & 0xFFFF0000 != 0x808D0000
                or model_window[1:] != (0x7F43D378, branch(model_hook, request, link=True))
                or struct.unpack_from(">3I", output, model_position - 8) != model_window):
            raise FormatError("unexpected native Colosseum Snag List model request")
        output, model_hooks = _append_colo(original, output, region, model_hook, model_window[2],
                                          lambda address: _bonus_model_stub(address, request))
        hooks.extend(model_hooks)
        navigation, view_low = _COLO_NAVIGATION[game_id]
        navigation_position = navigation - TEXT_TO_RAM
        navigation_window = (
            0x38840000 | view_low, 0x83040098,
            branch(navigation - 12, saved_pid, link=True),
            0x7F23CB78, 0x7F04C378, branch(navigation, setter, link=True), 0x2C1B0001)
        for data in (original, output):
            if (struct.unpack_from(">7I", data, navigation_position - 20) != navigation_window
                    or u32(data, navigation_position - 24) != 0x7F83E378):
                raise FormatError("unexpected native Colosseum Snag List navigation identity")
        output, navigation_hooks = _append_colo(original, output, region, navigation, navigation_window[5],
            lambda address: _colo_identity_stub(address, setter, saved_pid, generated, region.player_pointer,
                captured, custom_shadow_shinies=custom_shadow_shinies, shadow_register=28,
                deoxys_forms=deoxys_forms, deoxys_reader=deoxys_reader, game_id=game_id))
        hooks.extend(navigation_hooks)
        navigation_model = navigation + 0x68
        navigation_model_position = navigation_model - TEXT_TO_RAM
        navigation_model_window = (model_window[0], 0x38630000 | view_low,
                                   0x3863004C, branch(navigation_model, request, link=True))
        for data in (original, output):
            if struct.unpack_from(">4I", data, navigation_model_position - 12) != navigation_model_window:
                raise FormatError("unexpected native Colosseum Snag List navigation model")
        output, navigation_model_hooks = _append_colo(original, output, region,
            navigation_model, navigation_model_window[3],
            lambda address: _bonus_model_stub(address, request, shadow_register=28, mode_register=27))
        hooks.extend(navigation_model_hooks)
    elif game_id in _XD_HOOKS:
        layout = XD_IDENTITIES[game_id]
        if hashlib.sha256(original).hexdigest() != layout.original_sha256:
            raise FormatError("unexpected original XD Snag List executable")
        hook = _XD_HOOKS[game_id]
        expected = (0x387D0004, 0x3880FFFF, 0x38A0FFFF, 0x38C00000, 0x38E00000,
                    branch(hook, layout.pid_generator, link=True), 0x907D0000, 0x387D0004, 0x809D0000)
        position = hook - TEXT1_TO_RAM
        for data in (original, current):
            if struct.unpack_from(">9I", data, position - 20) != expected:
                raise FormatError("unexpected XD Snag List display window")
        output, hooks = append_xd_dol_text(original, current, game_id, (
            (hook, expected[5], lambda address, _continuation: _xd_identity_stub(
                address, layout.pid_generator, layout.player_lookup, XD_SHADOW_STATE[game_id].shadow_seen,
                custom_shadow_shinies=custom_shadow_shinies,
                deoxys_forms=deoxys_forms, deoxys_reader=deoxys_reader, game_id=game_id)),
        ), link=True)
    else:
        raise FormatError("unsupported Snag List game")
    return output, {"version": VERSION, "hooks": hooks, "saved_pids_preserved": True,
                    "custom_shadow_ownership": custom_shadow_shinies,
                    "postgame_shadow_lugia": bool(postgame_shadow_lugia and game_id in _COLO_HOOKS),
                    "native_shadow_ids_unchanged": True,
                    "native_completion_excludes_bonus": bool(postgame_shadow_lugia and game_id in _COLO_HOOKS),
                    "scope": "generated Shadow identities in temporary Snag List display models"}
