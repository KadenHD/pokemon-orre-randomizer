"""Colosseum Deoxys models and base stats selected from its saved form tag.

Only the five non-HP base-stat requests inside pokemonSetLevelBasisStatus are
redirected. Native level, IV/EV, nature, current-HP and level-up calculations
remain intact. Only full records of the genuine species select transient
model markers; cloned species sharing its original model remain unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
import struct

from .castform_portraits import _reservation
from .castform_shiny_models import (
    SHINY_RESOURCES as WEATHER_RESOURCES, _HOOKS as WEATHER_HOOKS,
    _model_selector as weather_selector,
)
from .deoxys_resources import FORMS, MODEL_GROUPS, MODEL_RESOURCES
from .deoxys_identity import (
    FORM_TAG, FORM_MASK, FORM_OFFSETS, RECORD_SIZES, MODEL_MARKERS, form_reader, transform_tag_copy,
)
from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .engine.postgame_lugia_model import (
    _LAYOUTS as MODEL_LAYOUTS, _LOADER_PREFIX, _MENU_GETTERS, _CEREMONY_GETTERS,
    _SAVED_IDENTITIES, _identity_selector as lugia_identity,
    _battle_identity_selector as lugia_battle, _resource_selector as lugia_resources,
)
from .engine.shiny_rules import _Code

VERSION = "colosseum-saved-tag-deoxys-forms-v2"
DEOXYS = 410
FORM_ORDER = ("normal", *FORMS)
STAT_FUNCTIONS = {"GC6P01": 0x8012BAD0, "GC6E01": 0x8012795C, "GC6J01": 0x801250FC}
STAT_GETTERS = {"GC6P01": 0x8012A580, "GC6E01": 0x8012640C, "GC6J01": 0x80123BAC}
STAT_FUNCTION_SIZE = 0x700
TRANSFORM_FUNCTIONS = {"GC6P01": 0x802031D0, "GC6E01": 0x801FE91C, "GC6J01": 0x801FA1DC}
# Independently matched retail windows: li r3,0; li r5,selector; li r6,0;
# BL pokemonGetStatus; native narrowing into the calculator's saved register.
STAT_WINDOWS = (
    (0x198, 4, "3860000038a0000438c000004bffe9195478043e"),
    (0x2A8, 5, "3860000038a0000538c000004bffe809547a043e"),
    (0x3B4, 8, "3860000038a0000838c000004bffe6fd547a043e"),
    (0x4C0, 6, "3860000038a0000638c000004bffe5f1547a043e"),
    (0x5CC, 7, "3860000038a0000738c000004bffe4e5547a043e"),
)
_STAT_PREFIX = bytes.fromhex(
    "9421ffd07c0802a638a0006e38c0000090010034bf0100107c9b23787c7e1b7838800000"
)
_MEM1_START, _LAST_RECORD = 0x80000000, 0x81800000 - RECORD_SIZES["colosseum"]
_BASE_COLUMNS = ((4, 1), (5, 2), (6, 3), (7, 4), (8, 5))


def _load(code, register, value):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | value & 0xFFFF)


def _resources(resources, groups, original):
    expected = {(name, shiny) for name in FORMS for shiny in (False, True)}
    if (not isinstance(resources, Mapping) or set(resources) != expected
            or any(type(k) is not tuple or len(k) != 2 or type(k[0]) is not str
                   or type(k[1]) is not bool for k in resources)
            or any(type(v) is not int or not 0 < v <= 0xFFFFFFFF
                   or v & 0xFFFF != 0x1E00 for v in resources.values())
            or len(set(resources.values())) != 6):
        raise FormatError("six distinct Deoxys form model resources are required")
    if (not isinstance(groups, Mapping) or set(groups) != {False, True}
            or any(type(k) is not bool for k in groups)
            or any(type(v) is not int or not 0 < v <= 0xFFFF for v in groups.values())):
        raise FormatError("Deoxys standard and shiny archive groups are required")
    if any(struct.pack(">I", value) in original for value in resources.values()):
        raise FormatError("Deoxys model resource collides with a native executable identity")
    return dict(resources), dict(groups)


def _stats(base_stats):
    if base_stats is None:
        from .deoxys import BASE_STATS
        base_stats = BASE_STATS
    if (not isinstance(base_stats, Mapping) or set(base_stats) != set(FORM_ORDER)
            or any(not isinstance(row, (tuple, list)) or len(row) != 6
                   or any(type(v) is not int or not 1 <= v <= 255 for v in row)
                   for row in base_stats.values())):
        raise FormatError("Deoxys requires six valid base stats for each of its four forms")
    return {name: tuple(base_stats[name]) for name in FORM_ORDER}


def _model_selector(address, loader, fallback, resources, groups, native_word=0x800D84B0):
    """Resolve explicit form markers before native model-table bounds checking."""
    code = _Code(address)
    for form, marker in enumerate(MODEL_MARKERS):
        code.emit(0x28030000 | marker)
        code.conditional(0x41820000, f"form_{form}")
    code.jump("native")
    code.label("form_0")
    code.emit(0x38600000 | DEOXYS, 0x3B400000 | DEOXYS, native_word)
    code.emit(branch(address + len(code.words) * 4, loader + 0x2C))
    for form in range(1, 4):
        code.label(f"form_{form}")
        code.emit(0x39600000 | form)
        code.jump("variant")
    code.label("variant")
    code.emit(0x281C0000)  # native rare decision is already qualified by caller
    code.conditional(0x40820000, "shiny")
    for shiny in (False, True):
        if shiny:
            code.label("shiny")
        for form, name in enumerate(FORMS, 1):
            code.emit(0x280B0000 | form)
            code.conditional(0x41820000, name + ("_shiny" if shiny else "_normal"))
        code.jump("native")
    for shiny in (False, True):
        for name in FORMS:
            code.label(name + ("_shiny" if shiny else "_normal"))
            _load(code, 31, groups[shiny])
            _load(code, 30, resources[name, shiny])
            code.emit(0x3BA00001)  # actual normal/rare PKX: no generic rare tint
            code.jump("selected")
    code.label("selected")
    code.emit(0x3B400000 | DEOXYS)
    code.emit(branch(address + len(code.words) * 4, loader + 0x14C))
    code.label("native")
    if fallback is None:
        code.emit(native_word)
        code.emit(branch(address + len(code.words) * 4, loader + 0x2C))
    else:
        # Preserve the existing owned Lugia early resource resolver.
        code.emit(branch(address + len(code.words) * 4, fallback))
    return code.finish()


def _stat_selector(address, getter, base_stats):
    """Override one native base-stat request; r30 still holds its real CK3."""
    code = _Code(address)
    code.emit(0x28030000)  # only the qualified species-table request (r3==NULL)
    code.conditional(0x40820000, "native")
    code.emit(0x28040000 | DEOXYS)
    code.conditional(0x40820000, "native")
    _load(code, 0, _MEM1_START)
    code.emit(0x7C1E0040)  # cmplw r30,r0
    code.conditional(0x41800000, "native")
    _load(code, 0, _LAST_RECORD)
    code.emit(0x7C1E0040)
    code.conditional(0x41810000, "native")  # bgt: complete species/PID in MEM1
    code.emit(0x57C007BE, 0x28000000)  # word-aligned record
    code.conditional(0x40820000, "native")
    code.emit(0xA01E0000, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "native")
    code.emit(0xA01E0000 | FORM_OFFSETS["colosseum"], 0x540B003A,
              0x280B0000 | FORM_TAG)
    code.conditional(0x40820000, "native")
    code.emit(0x540007BE, 0x28000000)
    code.conditional(0x41820000, "native")
    for form, name in enumerate(FORMS, 1):
        code.emit(0x28000000 | form)
        code.conditional(0x41820000, name)
    code.jump("native")
    for name in FORMS:
        code.label(name)
        for selector, column in _BASE_COLUMNS:
            code.emit(0x28050000 | selector)
            code.conditional(0x41820000, f"{name}_{selector}")
        code.jump("native")
        for selector, column in _BASE_COLUMNS:
            code.label(f"{name}_{selector}")
            code.emit(0x38600000 | base_stats[name][column], 0x4E800020)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, getter))
    return code.finish()


def _previous_weather(current, original, hook, ram, code, offset):
    pos = hook - TEXT_TO_RAM
    signature = bytes.fromhex(WEATHER_HOOKS[dol_layout(original).game_id][1])
    if (original[pos:pos + len(signature)] != signature
            or current[pos + 4:pos + len(signature)] != signature[4:]):
        raise FormatError("unexpected Deoxys model-loader instruction window")
    word = u32(current, pos)
    if word == 0x7FF7FB78:
        return None
    if word & 0xFC000003 != 0x48000000:
        raise FormatError("unowned Deoxys model-loader hook")
    displacement = word & 0x3FFFFFC
    if displacement & 0x2000000:
        displacement -= 0x4000000
    target = hook + displacement
    expected = weather_selector(target, hook + 4, WEATHER_RESOURCES, xd=False)
    start = target - ram
    if (not 32 <= start or start + len(expected) > len(code)
            or current[offset + start:offset + start + len(expected)] != expected):
        raise FormatError("unowned Deoxys model-loader hook chain")
    return target


def _owned_target(current, call, native, *, link, ram, code, offset, recipes):
    word = u32(current, call - TEXT_TO_RAM)
    if word == branch(call, native, link=link):
        return native
    if word & 0xFC000003 != 0x48000000 | int(link):
        raise FormatError("unowned Deoxys model identity hook")
    displacement = word & 0x3FFFFFC
    if displacement & 0x2000000:
        displacement -= 0x4000000
    target = call + displacement
    start = target - ram
    if start < 32 or start >= len(code):
        raise FormatError("unowned Deoxys model identity target")
    for recipe in recipes:
        expected = recipe(target)
        if start + len(expected) <= len(code) and code[start:start + len(expected)] == expected:
            return target
    raise FormatError("unowned Deoxys model identity chain")


def _previous_lugia(current, original, game_id, loader, ram, code, offset):
    hook = loader + 0x28
    native_word = 0x800D84A0 if game_id == "GC6J01" else 0x800D84B0
    if u32(original, hook - TEXT_TO_RAM) != native_word:
        raise FormatError("unexpected Deoxys early model-loader window")
    if u32(current, hook - TEXT_TO_RAM) == native_word:
        return None
    word = u32(current, hook - TEXT_TO_RAM)
    if word & 0xFC000003 != 0x48000000:
        raise FormatError("unowned Deoxys early model-loader hook")
    displacement = word & 0x3FFFFFC
    if displacement & 0x2000000:
        displacement -= 0x4000000
    target = hook + displacement
    start = target - ram
    if start < 32 or start >= len(code):
        raise FormatError("unowned Deoxys early model-loader target")
    # Extract only exact native saved-Shadow reader calls. Rebuilding the full
    # previous recipe then qualifies every instruction and its complete policy.
    saved = _SAVED_IDENTITIES[game_id]
    shadow_ids = []
    # The first conditional branch targets this very recipe's variant block.
    # Stop there, so later independent face hooks cannot contribute candidates.
    first_branch = u32(code, start + 4)
    if u32(code, start) != 0x28037FF0 or first_branch & 0xFFFF0003 != 0x41820000:
        raise FormatError("unowned Deoxys early model-loader recipe")
    delta = first_branch & 0xFFFC
    if delta & 0x8000:
        delta -= 0x10000
    variant = start + 4 + delta
    if not start < variant < len(code):
        raise FormatError("invalid owned Lugia variant boundary")
    for pos in range(start, variant - 4, 4):
        first, second = struct.unpack_from(">II", code, pos)
        if first & 0xFFFF0000 == 0x38600000 and second == branch(ram + pos + 4, saved[1], link=True):
            sid = first & 0xFFFF
            if not 1 <= sid <= 96 or sid in shadow_ids:
                break
            shadow_ids.append(sid)
    table = MODEL_LAYOUTS[game_id][3]
    group = u32(original, table + 249 * 12)
    for keep in (False, True):
        for identities in (saved, None):
            expected = lugia_resources(target, loader, native_word, group, identities,
                                       keep_after_purification=keep, shadow_ids=tuple(shadow_ids))
            if code[start:start + len(expected)] == expected:
                return target
    raise FormatError("unowned Deoxys early model-loader chain")


def _record_identity(address, native, reader, *, load_model):
    """The qualified menu/ceremony callers keep the full CK3 in r31."""
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,
              0x90610008, 0x9081000C, 0x90A10010,
              0xA01F0000, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "native")
    if load_model:
        code.emit(0x28030000 | DEOXYS)
        code.conditional(0x40820000, "native")
    code.emit(0x7FE3FB78)
    code.call(reader)
    code.emit(0x38630000 | MODEL_MARKERS[0], 0x90610008)
    code.emit(0x80610008, 0x8081000C, 0x80A10010,
              0x80010024, 0x7C0803A6, 0x38210020)
    if load_model:
        code.emit(branch(address + len(code.words) * 4, native))
    else:
        code.emit(0x4E800020)
    code.label("native")
    code.emit(0x80610008, 0x8081000C, 0x80A10010,
              0x80010024, 0x7C0803A6, 0x38210020)
    code.emit(branch(address + len(code.words) * 4, native))
    return code.finish()


def _battle_identity(address, native, reader, getter):
    """Read full native battle identity; retain Substitute/model overrides."""
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,
              0x90610008, 0x9081000C, 0x90A10010, 0x28030000 | DEOXYS)
    code.conditional(0x40820000, "restore")
    code.emit(0x281E0000)
    code.conditional(0x41820000, "restore")
    code.emit(0x7FC3F378, 0x38800000, 0x38A000D6, 0x38C00000)
    code.call(getter)
    code.emit(0x28030000)
    code.conditional(0x41820000, "restore")
    code.emit(0x38800000, 0x38A000CC, 0x38C00000)
    code.call(getter)
    code.emit(0x28030000)
    code.conditional(0x41820000, "restore")
    code.emit(0xA0030000, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, "restore")
    code.call(reader)
    code.emit(0x38630000 | MODEL_MARKERS[0], 0x90610008)
    code.label("restore")
    code.emit(0x80610008, 0x8081000C, 0x80A10010,
              0x80010024, 0x7C0803A6, 0x38210020)
    code.emit(branch(address + len(code.words) * 4, native))
    return code.finish()


def _unchanged_outside(before, after, allowed):
    cursor = 0
    for lo, hi in sorted(allowed):
        lo, hi = min(lo, len(before)), min(hi, len(before))
        if before[cursor:lo] != after[cursor:lo]:
            return False
        cursor = max(cursor, hi)
    return before[cursor:] == after[cursor:len(before)]


def install_deoxys_forms(original: bytes, current: bytes, game_id: str, *,
                         resources=MODEL_RESOURCES, groups=MODEL_GROUPS, base_stats=None):
    """Install scoped native form hooks after archive resources have been staged.

    Normal Forme keeps the ordinary resources and species-table stats. The five
    other stat values may be supplied for an advanced randomized-stat policy.
    No saved PID, species, move, HP, EV, IV or nature field is written here.
    """
    if type(original) is not bytes or type(current) is not bytes:
        raise FormatError("Deoxys form hooks require immutable executable bytes")
    region = dol_layout(original)
    if game_id not in STAT_FUNCTIONS or region.game_id != game_id:
        raise FormatError("unknown original Colosseum Deoxys executable")
    resources, groups = _resources(resources, groups, original)
    base_stats = _stats(base_stats)
    function, getter = STAT_FUNCTIONS[game_id], STAT_GETTERS[game_id]
    first = function - TEXT_TO_RAM
    if (original[first:first + len(_STAT_PREFIX)] != _STAT_PREFIX
            or current[first:first + STAT_FUNCTION_SIZE] != original[first:first + STAT_FUNCTION_SIZE]
            or current[getter - TEXT_TO_RAM:getter - TEXT_TO_RAM + 16]
                != original[getter - TEXT_TO_RAM:getter - TEXT_TO_RAM + 16]):
        raise FormatError("unexpected Deoxys native stat calculator")
    loader = MODEL_LAYOUTS[game_id][0]
    start = loader - TEXT_TO_RAM
    if any(data[start:start + len(_LOADER_PREFIX)] != _LOADER_PREFIX for data in (original, current)):
        raise FormatError("unexpected Deoxys native model-loader identity arguments")
    hook = loader + 0x28
    offset, ram, setter, store, code = _reservation(original, current, game_id)
    if ram + len(code) >= 0x81700000:
        raise FormatError("Deoxys form code exceeds reserved memory")
    weather = _previous_weather(current, original, loader + 0x14C, ram, code, offset)
    previous = _previous_lugia(current, original, game_id, loader, ram, code, offset)
    model_calls = []
    _, menu, battle, _ = MODEL_LAYOUTS[game_id]
    for call, prefix, suffix in (
            (menu, bytes.fromhex("7fc4f3785783043e"), bytes.fromhex("7c601b7838600008")),
            (battle, bytes.fromhex("7c651b7857e3043e"), bytes.fromhex("7c601b7838610010"))):
        pos = call - TEXT_TO_RAM
        if (original[pos - 8:pos] != prefix or original[pos + 4:pos + 12] != suffix
                or u32(original, pos) != branch(call, loader, link=True)
                or current[pos - 8:pos] != prefix or current[pos + 4:pos + 12] != suffix):
            raise FormatError("unexpected Deoxys full-record model call")
        if call == menu:
            recipes = [lambda a, keep=keep: lugia_identity(a, loader, keep_after_purification=keep)
                       for keep in (False, True)]
        else:
            recipes = [lambda a, keep=keep: lugia_battle(a, loader, getter, keep_after_purification=keep)
                       for keep in (False, True)]
        target = _owned_target(current, call, loader, link=True, ram=ram, code=code,
                               offset=offset, recipes=recipes)
        model_calls.append((call, target, "battle" if call == battle else "menu"))
    requests = (*_MENU_GETTERS[game_id][:2], _CEREMONY_GETTERS[game_id])
    for index, call in enumerate(requests):
        pos = call - TEXT_TO_RAM
        if index < 2:
            field_store = (0xB0810014, 0xB09E0010)[index]
            expected = struct.pack(">7I", 0x38600000, field_store, 0x38A00066, 0x38C00000,
                                   branch(call, getter, link=True), 0x5460043E, 0x7FE3FB78)
            first, stop = pos - 16, pos + 12
        else:
            expected = struct.pack(">5I", 0x38600000, 0x38A00066, 0x38C00000,
                                   branch(call, getter, link=True), 0x547E043F)
            first, stop = pos - 12, pos + 8
        if (original[first:stop] != expected
                or current[first:pos] != original[first:pos]
                or current[pos + 4:stop] != original[pos + 4:stop]):
            raise FormatError("unexpected Deoxys full-record model request")
        recipes = [lambda a, keep=keep: lugia_identity(a, getter, return_marker=True,
                        keep_after_purification=keep, force_ordinary=index == 2 and not keep)
                   for keep in (False, True)]
        target = _owned_target(current, call, getter, link=True, ram=ram, code=code,
                               offset=offset, recipes=recipes)
        model_calls.append((call, target, "request"))
    calls = []
    for relative, selector, window in STAT_WINDOWS:
        address = function + relative
        pos = address - TEXT_TO_RAM
        if (original[pos - 12:pos + 8] != bytes.fromhex(window)
                or u32(original, pos) != branch(address, getter, link=True)):
            raise FormatError("unexpected Deoxys scoped base-stat request")
        calls.append((address, selector))
    transform = TRANSFORM_FUNCTIONS[game_id]
    transform_pos = transform - TEXT_TO_RAM
    if (original[transform_pos:transform_pos + 8] != bytes.fromhex("9421ffa07c0802a6")
            or current[transform_pos:transform_pos + 0x2F4] != original[transform_pos:transform_pos + 0x2F4]
            or u32(original, transform_pos + 0x168) != 0x3BA00000):
        raise FormatError("unexpected Colosseum native Transform copy")
    model_address = ram + len(code)
    model_code = _model_selector(model_address, loader, previous, resources, groups,
                                  u32(original, hook - TEXT_TO_RAM))
    code.extend(model_code)
    stat_address = ram + len(code)
    stat_code = _stat_selector(stat_address, getter, base_stats)
    code.extend(stat_code)
    reader_address = ram + len(code)
    reader_code = form_reader(reader_address, game_id=game_id)
    code.extend(reader_code)
    identities = []
    for call, target, kind in model_calls:
        address = ram + len(code)
        body = (_battle_identity(address, target, reader_address, getter) if kind == "battle"
                else _record_identity(address, target, reader_address, load_model=kind == "menu"))
        code.extend(body)
        identities.append({"address": call, "target": address, "bytes": len(body), "kind": kind,
                           "previous": target})
    transform_hook = transform + 0x168
    transform_address = ram + len(code)
    transform_code = transform_tag_copy(transform_address, transform_hook + 4, game_id=game_id,
                                        source=28, destination=27, displaced=0x3BA00000)
    code.extend(transform_code)
    code.extend(bytes(-len(code) % 32))
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Deoxys form code exceeds reserved memory")
    code[:32] = _arena_guard(end, store)
    output = bytearray(current[:offset])
    struct.pack_into(">I", output, hook - TEXT_TO_RAM, branch(hook, model_address))
    for address, _ in calls:
        struct.pack_into(">I", output, address - TEXT_TO_RAM, branch(address, stat_address, link=True))
    for entry in identities:
        struct.pack_into(">I", output, entry["address"] - TEXT_TO_RAM,
                         branch(entry["address"], entry["target"], link=True))
    struct.pack_into(">I", output, transform_hook - TEXT_TO_RAM, branch(transform_hook, transform_address))
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                       (setter - TEXT_TO_RAM, branch(setter, ram))):
        struct.pack_into(">I", output, pos, value)
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C),
               (setter - TEXT_TO_RAM, setter - TEXT_TO_RAM + 4),
               (hook - TEXT_TO_RAM, hook - TEXT_TO_RAM + 4), (offset, offset + 32)]
    allowed.extend((a - TEXT_TO_RAM, a - TEXT_TO_RAM + 4) for a, _ in calls)
    allowed.extend((e["address"] - TEXT_TO_RAM, e["address"] - TEXT_TO_RAM + 4) for e in identities)
    allowed.append((transform_hook - TEXT_TO_RAM, transform_hook - TEXT_TO_RAM + 4))
    if not _unchanged_outside(current, output, allowed):
        raise FormatError("Deoxys form hooks changed unrelated executable bytes")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if (section["offset"], section["ram_address"], section["size"]) != (offset, ram, len(code)):
        raise FormatError("Deoxys form section failed readback")
    return bytes(output), {
        "version": VERSION, "game_id": game_id, "form_source": "native reserved Para1Amari u16 tag",
        "form_order": list(FORM_ORDER), "model_hook": hook, "model_stub": model_address,
        "previous_weather_stub": weather, "previous_lugia_stub": previous,
        "form_reader": reader_address, "identity_hooks": identities,
        "transform_hook": transform_hook, "transform_stub": transform_address,
        "stat_function": function, "stat_stub": stat_address,
        "base_stat_calls": [{"address": a, "selector": s} for a, s in calls],
        "resources": {name: {"standard": resources[name, False], "shiny": resources[name, True]}
                      for name in FORMS},
        "archive_groups": {"standard": groups[False], "shiny": groups[True]},
        "base_stats": {name: list(base_stats[name]) for name in FORM_ORDER},
        "code_bytes": len(model_code) + len(stat_code) + len(reader_code) + len(transform_code) + sum(e["bytes"] for e in identities),
        "save_data_unchanged": True,
        "native_hp_iv_ev_nature_and_level_formulas_preserved": True,
        "normal_form_resources_preserved": True, "generic_stat_requests_unchanged": True,
        "generic_rare_tint_skipped_for_added_models": True,
        "unrelated_executable_bytes_preserved": True,
        "transform_target_form_copied_to_native_temporary_buffer": True,
        "model_identity_limit": "Reduced Snag/DNA display records require their separately installed saved-identity reader.",
    }
