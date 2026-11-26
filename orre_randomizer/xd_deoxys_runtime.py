"""XD's four original Deoxys forms selected from the saved reserved form tag.

Native model/portrait archives, shiny checks, animation dispatch, stat formulae
and GBA selectors remain intact. Qualified full-record views override only a
tagged Deoxys's form argument. No personality or save field is written here.
"""
from __future__ import annotations

import hashlib
import struct

from .castform_layouts import LAYOUTS as ORIGINALS
from .deoxys_identity import DEOXYS, FORM_TAG, _bounds, transform_tag_copy
from .deoxys_runtime import _stats, _unchanged_outside
from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM, ARENA, append_xd_dol_text

VERSION = "xd-saved-tag-deoxys-forms-v3"
# Native function boundaries independently matched against all three originals.
# stat(one stat), menu form helper, central face, battle creator, switch-in,
# two purification model loaders, GBA stat customizer, GBA selector, stat table.
LAYOUTS = {
    "GXXP01": (0x801457F0, 0x8011392C, 0x80112E74, 0x80141820, 0x80207358,
                 0x802359D0, 0x8023721C, 0x8004A0FC, 0x8004A490, 0x80330470,
                 0x80144740, 0x801419BC, 0x801D4400, 0x80148970),
    "GXXE01": (0x80143F2C, 0x801121E8, 0x80111730, 0x8013FF5C, 0x80205624,
                 0x80233B7C, 0x8023539C, 0x8004A0A8, 0x8004A43C, 0x8032EB88,
                 0x80142E7C, 0x801400F8, 0x801D28F8, 0x801470AC),
    "GXXJ01": (0x8013F338, 0x8010DA08, 0x8010CF50, 0x8013B368, 0x802002D0,
                 0x8022E4B4, 0x8022FCD4, 0x80048E48, 0x800491DC, 0x8031CE88,
                 0x8013E288, 0x8013B504, 0x801CD798, 0x801424B8),
}
_BASE_COLUMNS = ((4, 1), (5, 2), (6, 3), (7, 4), (8, 5))
TRANSFORM_FUNCTIONS = {"GXXP01": 0x8020292C, "GXXE01": 0x80200BF8, "GXXJ01": 0x801FB8BC}
ANT_LAYOUTS = {
    "GXXP01": (0x80292740, 0x80292B54, 0x80292F68, 0x8014AFE0),
    "GXXE01": (0x80290804, 0x80290C18, 0x8029102C, 0x8014971C),
    "GXXJ01": (0x8028B22C, 0x8028B640, 0x8028BA54, 0x80144B00),
}


def emit_tag(code, register, fallback):
    """Leave a valid stored form in r11; otherwise branch before record reads."""
    _bounds(code, register, 0xC4, fallback)
    code.emit(0xA0000000 | register << 16, 0x28000000 | DEOXYS)
    code.conditional(0x40820000, fallback)
    code.emit(0xA160000C | register << 16, 0x5560003A, 0x28000000 | FORM_TAG)
    code.conditional(0x40820000, fallback)
    code.emit(0x556B07BE)


def _padded(code):
    payload = code.finish()
    return payload + bytes(-len(payload) % 32)


def _selector(address, native, record):
    code = _Code(address)
    emit_tag(code, record, "native")
    code.emit(0x7D635B78, 0x4E800020)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, native))
    return _padded(code)


def _menu_form(address, continuation):
    code = _Code(address)
    code.emit(0x38000000)  # displaced retail Normal Forme
    emit_tag(code, 31, "native")
    code.emit(0x7D605B78)  # mr r0,r11
    code.jump("done")
    code.label("native")
    code.emit(0x38000000)
    code.label("done")
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _face_form(address, continuation):
    code = _Code(address)
    code.emit(0x7C9D2378)  # displaced mr r29,r4
    emit_tag(code, 28, "native")
    code.emit(0x7D7D5B78)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, continuation))
    return _padded(code)


def _pid_cache(address, native):
    code = _Code(address)
    # Both independently audited 0x20-byte native frames leave +8 unused.
    # Cache only display form; the actual native saved PID is returned intact.
    code.emit(0x3800FFFF, 0x90010008)
    emit_tag(code, 3, "native")
    code.emit(0x91610008)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, native))
    return _padded(code)


def _cached_model(address, native):
    code = _Code(address)
    code.emit(0x28030000 | DEOXYS)
    code.conditional(0x40820000, "native")
    code.emit(0x80010008, 0x28000003)
    code.conditional(0x41810000, "native")
    code.emit(0x7C040378)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, native))
    return _padded(code)


def _bodies(values):
    if values is None:
        from .deoxys_resources import DANCE_RESOURCES
        values = DANCE_RESOURCES
    keys = {(form, shiny) for form in ("attack", "defense", "speed") for shiny in (False, True)}
    if (not isinstance(values, dict) or set(values) != keys
            or any(type(value) is not int or not 0 < value <= 0xFFFFFFFF
                   or value & 0xFFFF != 0x3200 for value in values.values())
            or len(set(values.values())) != 6
            or set(values.values()) & {0x1BF53200, 0x1BF83200}):
        raise FormatError("Invalid XD Deoxys native body resource map")
    return dict(values)


def _body_resource(address, native, owner, resources):
    """Native CAnt body lookup: actual full record, independent shiny argument."""
    code = _Code(address)
    code.emit(0x28030000 | DEOXYS)
    code.conditional(0x40820000, "native")
    emit_tag(code, owner, "native")
    for form, name in enumerate(("attack", "defense", "speed"), 1):
        code.emit(0x280B0000 | form)
        code.conditional(0x41820000, name)
    code.jump("native")
    for name in ("attack", "defense", "speed"):
        code.label(name)
        code.emit(0x28040000)
        code.conditional(0x40820000, name + "_shiny")
        for shiny in (False, True):
            if shiny:
                code.label(name + "_shiny")
            value = resources[name, shiny]
            code.emit(0x3C600000 | value >> 16, 0x60630000 | value & 0xFFFF, 0x4E800020)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, native))
    return _padded(code)


def _stat(address, getter, base_stats):
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x40820000, "native")
    code.emit(0x28040000 | DEOXYS)
    code.conditional(0x40820000, "native")
    emit_tag(code, 23, "native")
    code.emit(0x280B0000)
    code.conditional(0x41820000, "native")
    for form, name in enumerate(("attack", "defense", "speed"), 1):
        code.emit(0x280B0000 | form)
        code.conditional(0x41820000, name)
    code.jump("native")
    for name in ("attack", "defense", "speed"):
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
    return _padded(code)


def install_xd_deoxys_forms(original: bytes, current: bytes, game_id: str, *, base_stats=None,
                            body_resources=None):
    """Install saved-form presentation/stat routing using XD's retail assets."""
    if (type(original) is not bytes or type(current) is not bytes or game_id not in LAYOUTS
            or hashlib.sha256(original).hexdigest() != ORIGINALS[game_id]["sha256"]):
        raise FormatError("unknown original XD Deoxys executable")
    stats = _stats(base_stats)
    bodies = _bodies(body_resources)
    stat, menu, face, battle, switch, ceremony, evolve, gba, gba_sel, table, getter, fight_sel, loader, pid_getter = LAYOUTS[game_id]
    # The entire shared native stat calculator must still be unchanged. All
    # overrides stay in its one qualified base-table request; HP is untouched.
    at = stat - TEXT1_TO_RAM
    if (original[at:at + 0x1C] != bytes.fromhex("9421ffd07c0802a690010034bee1000c7c771b787c9823787cb92b78")
            or current[at:at + 0xE4] != original[at:at + 0xE4]):
        raise FormatError("unexpected XD Deoxys native stat calculator")
    stat_call = stat + 0x54
    if original[stat_call - TEXT1_TO_RAM - 16:stat_call - TEXT1_TO_RAM] != bytes.fromhex(
            "7fe4fb787f45d3783860000038c00000"):
        raise FormatError("unexpected XD Deoxys scoped base-stat request")
    # These source registers are native full records, not controller IDs.
    call_recipes = [(stat_call, getter, lambda a, n=getter: _stat(a, n, stats), "base_stats"),
                    (battle + 0x98, fight_sel, lambda a, n=fight_sel: _selector(a, n, 30), "battle"),
                    (switch + 0x110, fight_sel, lambda a, n=fight_sel: _selector(a, n, 29), "switch_in")]
    # GBA-entry stat correction calls its native selector once per non-HP
    # stat. Tagged specimens use the saved form; untagged GBA rules survive.
    for relative in (0x134, 0x188, 0x1E0, 0x238, 0x290):
        call_recipes.append((gba + relative, gba_sel,
                             lambda a, n=gba_sel: _selector(a, n, 19), "gba_stat_form"))
    for base, pid_relative, load_relative in ((ceremony, 0x68, 0x9C), (evolve, 0x44, 0x78)):
        call_recipes.extend(((base + pid_relative, pid_getter,
                              lambda a, n=pid_getter: _pid_cache(a, n), "ceremony_form_cache"),
                             (base + load_relative, loader,
                              lambda a, n=loader: _cached_model(a, n), "ceremony_model")))
    visitor, any_body, generic, body_getter = ANT_LAYOUTS[game_id]
    for base, length, relative, owner in ((visitor, 0x414, 0x114, 30),
                                         (any_body, 0x414, 0x114, 30),
                                         (generic, 0x3F4, 0x120, 29)):
        start = base - TEXT1_TO_RAM
        prefix = ("9421ff007c0802a638a0003490010104bf6100ec7c9e23787c7d1b7838800000"
                  if owner == 30 else
                  "9421ff007c0802a638a000349001010493e100fc7c7f1b7893c100f893a100f47c9d237838800000938100f0")
        if (original[start:start + len(bytes.fromhex(prefix))] != bytes.fromhex(prefix)
                or current[start:start + length] != original[start:start + length]):
            raise FormatError("Unexpected or foreign XD native Pokemon body constructor")
        call_recipes.append((base + relative, body_getter,
                             lambda a, n=body_getter, r=owner: _body_resource(a, n, r, bodies),
                             "chamber_body"))
    transform = TRANSFORM_FUNCTIONS[game_id]
    transform_pos = transform - TEXT1_TO_RAM
    if (original[transform_pos:transform_pos + 8] != bytes.fromhex("9421ffa07c0802a6")
            or current[transform_pos:transform_pos + 0x21C] != original[transform_pos:transform_pos + 0x21C]):
        raise FormatError("unexpected XD native Transform copy")
    def transform_builder(a, c):
        payload = transform_tag_copy(a, c, game_id=game_id, source=26, destination=25, displaced=0x3B600000)
        return payload + bytes(-len(payload) % 32)
    inline = ((menu + 0x9C, 0x38000000, _menu_form, "menu_model"),
              (face + 0x20, 0x7C9D2378, _face_form, "portrait"),
              (transform + 0xF4, 0x3B600000, transform_builder, "transform"))
    for call, native, _, _ in call_recipes:
        pos = call - TEXT1_TO_RAM
        expected = branch(call, native, link=True)
        if u32(original, pos) != expected or u32(current, pos) != expected:
            raise FormatError(f"unexpected or owned-by-another-patch XD Deoxys call at {call:#x}")
        if current[pos - 8:pos] != original[pos - 8:pos] or current[pos + 4:pos + 12] != original[pos + 4:pos + 12]:
            raise FormatError("unexpected XD Deoxys native caller window")
    for call, word, _, _ in inline:
        pos = call - TEXT1_TO_RAM
        if (u32(original, pos) != word or u32(current, pos) != word
                or current[pos - 8:pos] != original[pos - 8:pos]
                or current[pos + 4:pos + 12] != original[pos + 4:pos + 12]):
            raise FormatError("unexpected or foreign XD Deoxys form dispatch")
    # Verify the complete retail table before replacing its five non-HP values.
    native_stats = {"normal": (50, 150, 50, 150, 50, 150), "attack": (50, 180, 20, 180, 20, 150),
                    "defense": (50, 70, 160, 70, 160, 90), "speed": (50, 95, 90, 95, 90, 180)}
    section = next((s for s in parse_dol(original)["sections"]
                    if s["ram_address"] <= table and table + 80 <= s["ram_address"] + s["size"]), None)
    if section is None:
        raise FormatError("XD Deoxys stat table is outside the native executable")
    position = section["offset"] + table - section["ram_address"]
    native = b"".join(struct.pack(">5I", *native_stats[name][1:]) for name in native_stats)
    if original[position:position + 80] != native or current[position:position + 80] != native:
        raise FormatError("unexpected XD native Deoxys form stat table")
    hooks = [(call, branch(call, target, link=True), lambda a, _c, build=build: build(a))
             for call, target, build, _ in call_recipes]
    output, calls = append_xd_dol_text(original, current, game_id, hooks, link=True)
    output, direct = append_xd_dol_text(original, output, game_id,
                                      [(call, word, build) for call, word, build, _ in inline])
    patched = bytearray(output)
    patched[position:position + 80] = b"".join(struct.pack(">5I", *stats[name][1:]) for name in native_stats)
    offset = (len(original) + 31) & ~31
    arena = ARENA[game_id][1] - TEXT1_TO_RAM
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (arena, arena + 4),
               (offset, offset + 32), (position, position + 80)]
    allowed += [(call - TEXT1_TO_RAM, call - TEXT1_TO_RAM + 4) for call, *_ in (*call_recipes, *inline)]
    if not _unchanged_outside(current, patched, allowed):
        raise FormatError("XD Deoxys forms changed unrelated executable bytes")
    return bytes(patched), {
        "version": VERSION, "game_id": game_id, "form_source": "reserved Para1Amari u16 tag at 0x0C",
        "hooks": [dict(entry, kind=recipe[3]) for entry, recipe in zip(calls, call_recipes, strict=True)]
                 + [dict(entry, kind=recipe[3]) for entry, recipe in zip(direct, inline, strict=True)],
        "native_models_shiny_assets_and_animations_preserved": True,
        "native_portrait_shiny_selection_preserved": True,
        "native_hp_iv_ev_nature_and_level_formulas_preserved": True,
        "untagged_gba_form_rules_preserved": True, "saved_personality_unchanged": True,
        "transform_target_form_copied_to_native_temporary_buffer": True,
        "native_chamber_body_forms_and_shiny_selection": True,
        "body_resources": {f"{name}:{'shiny' if shiny else 'normal'}": value
                           for (name, shiny), value in bodies.items()},
        "base_stats": {name: list(row) for name, row in stats.items()},
        "unrelated_executable_bytes_preserved": True,
        "limits": "Reduced display-record tagging is installed separately from native full-record routing.",
    }
