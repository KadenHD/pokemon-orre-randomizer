"""Optional Fairy type lookups over qualified generation-III native engines.

Type 19 is separate from Mystery (9) and Shadow (18). New getters intercept
only Fairy requests; every native request resumes the original instructions.
The native type tables, Pokémon/save layouts and prerecorded videos stay intact.
Sprite descriptors reference separately supplied native texture resources.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import struct

from .castform_portraits import _reservation
from .deoxys_meteorite import _QUALIFIED as MESSAGE_FUNCTIONS, _bank_refresh
from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code

VERSION = "fairy-native-type-lookups-v1"
FAIRY_TYPE = 19
FAIRY_NAME_ID = 0xF0300
FAIRY_SPRITE = 0x7F50
FAIRY_SMALL_SPRITE = 0x7F51
NATIVE_NEUTRAL, NATIVE_SUPER, NATIVE_RESIST, NATIVE_IMMUNE = 0x3F, 0x41, 0x42, 0x43
LANGUAGES = ("en", "de", "fr", "it", "es", "ja")
TYPE_NAMES = {"en": "FAIRY", "de": "FEE", "fr": "FÉE", "it": "FOLLETTO",
              "es": "HADA", "ja": "フェアリー"}
_LANG_TAGS = {"en": b"UK", "de": b"GE", "fr": b"FR", "it": b"IT", "es": b"SP", "ja": b"JP"}
DEFAULT_BADGE_RESOURCES = dict(zip(LANGUAGES, (0x7F851200, 0x7F861200, 0x7F871200,
                                             0x7F881200, 0x7F891200, 0x7F8A1200), strict=True))
DEFAULT_SMALL_BADGE_RESOURCES = dict(zip(LANGUAGES, (0x7F8B1200, 0x7F8C1200, 0x7F8D1200,
                                                   0x7F8E1200, 0x7F8F1200, 0x7F901200), strict=True))

# The original Japanese game has no zokuseiBiosGetSpriteID function. Its two
# independent UI controllers read these 18 native IDs inline. Do not infer an
# entry point by subtracting a western getter's size from the category getter.
_COLO_JP_NATIVE_SPRITES = (86, 88, 84, 76, 90, 81, 85, 82, 80, 93,
                           89, 91, 92, 79, 83, 77, 78, 87)
_DIRECT_SPRITE_READS = {'GC6J01': (
    {'site': 0x80040EB8, 'address': 0x80040E94, 'size': 64,
     'sha256': '97b1a0b9395a50cfc9dcc4ec76f1b75a1cd4934f4a7d58139fb1b4b879565672',
     'word': '7cc3022e', 'table': 0x802D2E2C},
    {'site': 0x80040F2C, 'address': 0x80040F08, 'size': 64,
     'sha256': 'f0e3ff343b5c8c39c3a9e07d139f0565c0b315818fbebe71caa0a3da0e3a5530',
     'word': '7cc3022e', 'table': 0x802D2E2C},
    {'site': 0x8006440C, 'address': 0x800643E8, 'size': 64,
     'sha256': '382e2f57d592ce8799fd45a1b27620e74e6c228d95e7747a8f1a34491a2b7c1f',
     'word': '7cc4022e', 'table': 0x802DA9CC},
    {'site': 0x800644A4, 'address': 0x80064480, 'size': 64,
     'sha256': '2471a33c6342dbbdf84f0cf0fb35dfcd9fa3a7f06494da22ca312bf9e036e0a8',
     'word': '7cc3022e', 'table': 0x802DA9CC},
)}


def fairy_effectiveness(attacker: int, defender: int) -> int | None:
    """Native single-type code, or None when the original lookup owns the pair.

    Shadow remains outside the ordinary type matrix, as in both originals.
    This helper does not change XD's separate Shadow-versus-Shadow rule.
    """
    if type(attacker) is not int or type(defender) is not int:
        raise ValueError("type identifiers must be integers")
    if FAIRY_TYPE not in (attacker, defender):
        return None
    other = defender if attacker == FAIRY_TYPE else attacker
    if other == FAIRY_TYPE:
        return NATIVE_NEUTRAL
    if not 0 <= other < 18:
        return 0
    if attacker == FAIRY_TYPE:
        return (NATIVE_SUPER if other in (1, 16, 17) else
                NATIVE_RESIST if other in (3, 8, 10) else NATIVE_NEUTRAL)
    return (NATIVE_IMMUNE if other == 16 else
            NATIVE_SUPER if other in (3, 8) else
            NATIVE_RESIST if other in (1, 6, 17) else NATIVE_NEUTRAL)


def _offset(data, address, length=4):
    section = next((s for s in parse_dol(data)["sections"] if
                    s["ram_address"] <= address and
                    address + length <= s["ram_address"] + s["size"]), None)
    if section is None:
        raise FormatError("Fairy native address is outside executable sections")
    return section["offset"] + address - section["ram_address"]


def _read(data, address, length):
    position = _offset(data, address, length)
    return data[position:position + length]


def _load(code, register, value):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | value & 0xFFFF)


def _fallback(code, continuation, displaced):
    code.label("native")
    code.emit(displaced, branch(code.address + len(code.words) * 4 + 4, continuation))


def _value_stub(address, continuation, displaced, value):
    code = _Code(address)
    # These native property getters explicitly narrow their input to u16.
    code.emit(0x5460043E, 0x28000000 | FAIRY_TYPE)
    code.conditional(0x40820000, "native")
    _load(code, 3, value)
    code.emit(0x4E800020)
    _fallback(code, continuation, displaced)
    return code.finish()


def _matchup_stub(address, continuation, displaced):
    code = _Code(address)
    # Unlike property getters, native pair lookups check full-width inputs.
    code.emit(0x28030000 | FAIRY_TYPE)
    code.conditional(0x41820000, "attack")
    code.emit(0x28040000 | FAIRY_TYPE)
    code.conditional(0x41820000, "defend")
    code.jump("native")
    for label, register, supers, resists, immunes in (
            ("attack", 4, (1, 16, 17), (3, 8, 10), ()),
            ("defend", 3, (3, 8), (1, 6, 17), (16,))):
        code.label(label)
        code.emit(0x28000000 | register << 16 | FAIRY_TYPE)
        code.conditional(0x41820000, "neutral")
        code.emit(0x28000000 | register << 16 | 18)
        code.conditional(0x40800000, "invalid")
        for identifiers, target in ((supers, "super"), (resists, "resist"), (immunes, "immune")):
            for identifier in identifiers:
                code.emit(0x28000000 | register << 16 | identifier)
                code.conditional(0x41820000, target)
        code.jump("neutral")
    for label, value in (("neutral", NATIVE_NEUTRAL), ("super", NATIVE_SUPER),
                         ("resist", NATIVE_RESIST), ("immune", NATIVE_IMMUNE), ("invalid", 0)):
        code.label(label)
        code.emit(0x38600000 | value, 0x4E800020)
    _fallback(code, continuation, displaced)
    return code.finish()


def _name_bank(language, game_id=None):
    # All six retail type-name banks use font1. Japanese Colosseum stores that
    # font as u16+6; its zero byte3 is reserved, not a font0 selector.
    font_id = 1 if game_id is not None else int(language != "ja")
    # Japanese Colosseum reads a u16 font at +6, rather than the western
    # font byte at +3. Writing a language tag there selects a nonexistent font.
    header = (struct.pack(">HHHHII", 0, 0, 1, font_id, 0, 0)
              if game_id == "GC6J01" else
              struct.pack(">HBBH2sII", 0, 0, font_id, 1, _LANG_TAGS[language], 0, 0))
    output = bytearray(header)
    output.extend(struct.pack(">II", FAIRY_NAME_ID, 24))
    output.extend(TYPE_NAMES[language].encode("utf-16-be") + b"\0\0")
    output.extend(bytes(-len(output) % 32))
    return bytes(output)


def _name_stub(address, continuation, displaced, refresh):
    code = _Code(address)
    code.emit(0x5460043E, 0x28000000 | FAIRY_TYPE)
    code.conditional(0x40820000, "native")
    code.emit(0x9421FFF0, 0x7C0802A6, 0x90010014)
    code.call(refresh)
    _load(code, 3, FAIRY_NAME_ID)
    code.emit(0x80010014, 0x7C0803A6, 0x38210010, 0x4E800020)
    _fallback(code, continuation, displaced)
    return code.finish()


def _resources(value, role):
    if (not isinstance(value, Mapping) or set(value) != set(LANGUAGES)
            or any(type(v) is not int or not 0 < v <= 0xFFFFFFFF or v & 0xFFFF != 0x1200
                   for v in value.values()) or len(set(value.values())) != 6):
        raise FormatError(f"Six distinct native {role} texture resources are required")
    return dict(value)


def _descriptor(template, resources, game_id, *, small=False):
    """Clone native sprite ABI; the caller supplies actual loaded TEX resources.

    PAL records and XD US records contain five language cells in EN/DE/FR/IT/ES
    order. The Japanese records, and Colosseum US, contain one native cell.
    """
    if len(template) not in (24, 72):
        raise FormatError("unknown native Fairy sprite descriptor size")
    output = bytearray(template)
    if output[:8] not in (bytes.fromhex("90000000000000ff"), bytes.fromhex("9000000000ff0000")):
        raise FormatError("unexpected native textured-sprite descriptor")
    width, height = ((21, 18) if small else (72, 18) if game_id.startswith("GXX") else (79, 27))
    languages = LANGUAGES[:5] if len(output) == 72 else ("ja" if game_id[3] == "J" else "en",)
    for index, language in enumerate(languages):
        struct.pack_into(">HHHHI", output, 8 + index * 12, 0, 0, width, height, resources[language])
    struct.pack_into(">H", output, len(output) - 4, (FAIRY_SMALL_SPRITE if small else FAIRY_SPRITE) + 1)
    return bytes(output)


def _descriptor_stub(address, continuation, displaced, descriptors):
    code = _Code(address)
    for index in descriptors:
        code.emit(0x28030000 | index)
        code.conditional(0x41820000, f"sprite_{index}")
    code.jump("native")
    for index, pointer in descriptors.items():
        code.label(f"sprite_{index}")
        _load(code, 3, pointer)
        code.emit(0x4E800020)
    _fallback(code, continuation, displaced)
    return code.finish()


def _direct_sprite_stub(address, continuation, displaced):
    """Japanese Colosseum indexes native badge arrays directly, not a getter.

    r0 is the native type's already-computed halfword offset. Intercept Fairy's
    offset only; replay every other original lhzx exactly, including Mystery.
    No base pointer, table count, other GPR, LR, SP or nonvolatile CR changes.
    """
    code = _Code(address)
    code.emit(0x28000000 | (FAIRY_TYPE * 2))
    code.conditional(0x40820000, "native")
    code.emit(0x38C00000 | FAIRY_SPRITE)
    code.emit(branch(address + len(code.words) * 4, continuation))
    _fallback(code, continuation, displaced)
    return code.finish()


def _text_sprite_stub(address, continuation, displaced, fairy_text, compare):
    """Extend GC6J's native GSchar-name-to-badge converter by one name.

    Its summary/move menus turn a localized type-name pointer into a sprite;
    other Japanese screens use the direct arrays handled separately. Compare
    with the game's own GSchar routine so copied strings work too. Native names
    and null inputs resume the untouched original 18-name conversion.
    """
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x90610008)
    _load(code, 4, fairy_text)
    code.call(compare)
    code.emit(0x28030000)
    code.conditional(0x40820000, "restore_native")
    _load(code, 3, FAIRY_SPRITE)
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    code.label("restore_native")
    code.emit(0x80610008, 0x80010024, 0x7C0803A6, 0x38210020)
    _fallback(code, continuation, displaced)
    return code.finish()


def _grid_stub(address, row):
    """Add Fairy in XD's unused last chart cell after the native Dark cell.

    Native fixed/status-move compatibility modes retain their existing marker
    rules. Ordinary attacks use the same intercepted affinity getter as battle.
    The displaced epilogue restores all caller nonvolatile registers afterwards.
    """
    code = _Code(address)
    code.emit(0x281A0011)
    code.conditional(0x40820000, "native")
    code.emit(0xA01F0006, 0x280001E8)
    code.conditional(0x40820000, "native")
    code.emit(0x9421FFE0, 0x3B200000, 0x7F63DB78)
    code.call(row["compatible"])
    code.emit(0x5460043E, 0x28000001)
    code.conditional(0x41820000, "chart")
    # Dragon Rage's native fixed-damage mode predates the Fairy immunity and
    # marks every original type neutral. Only its immunity follows the chart;
    # retain fixed damage for resistance and the status-move mode15 markers.
    code.emit(0x2800000F)
    code.conditional(0x40820000, "ordinary_mode")
    code.emit(0x281B0052)
    code.conditional(0x41820000, "fixed_damage_chart")
    code.label("ordinary_mode")
    for mode in (10, 11, 14):
        code.emit(0x28000000 | mode)
        code.conditional(0x41820000, "dash")
    code.emit(0x28000004)
    code.conditional(0x41800000, "label")
    code.emit(0x2800000F)
    code.conditional(0x41810000, "label")
    code.emit(0x3B20035D)
    code.jump("label")
    code.label("dash")
    code.emit(0x3B200376)
    code.jump("label")
    code.label("fixed_damage_chart")
    code.emit(0x38600000, 0x7F64DB78, 0x38A00003, 0x38C00000)
    code.call(row["move_status"])
    code.emit(0x5463043E, 0x38800000 | FAIRY_TYPE)
    code.call(row["affinity"])
    code.emit(0x3B20035D, 0x28030043)
    code.conditional(0x40820000, "label")
    code.emit(0x3B20035E)
    code.jump("label")
    code.label("chart")
    code.emit(0x38600000, 0x7F64DB78, 0x38A00003, 0x38C00000)
    code.call(row["move_status"])
    code.emit(0x5463043E, 0x38800000 | FAIRY_TYPE)
    code.call(row["affinity"])
    for effect, sprite in ((0x3F, 0x35D), (0x41, 0x35F),
                           (0x42, 0x360), (0x43, 0x35E)):
        code.emit(0x28030000 | effect)
        code.conditional(0x40820000, f"after_{effect}")
        code.emit(0x3B200000 | sprite)
        code.jump("label")
        code.label(f"after_{effect}")
    code.label("label")
    code.emit(0x7FC3F378, 0x7FE4FB78)
    code.call(row["layer"])
    code.emit(0x7C7D1B78, 0x3860FFA8, 0x3880000C, 0x7FC5F378,
              0x38C00000 | FAIRY_SPRITE, 0x38E00000, 0x7FA8EB78)
    code.call(row["draw_sprite"])
    code.emit(0x28190000)
    code.conditional(0x41820000, "restore")
    code.emit(0x38600000, 0x3880000E, 0x7FC5F378, 0x7F26CB78,
              0x38E00000, 0x7FA8EB78)
    code.call(row["draw_sprite"])
    code.label("restore")
    code.emit(0x38210020)
    code.label("native")
    code.emit(row["epilogue_word"])
    code.emit(branch(address + len(code.words) * 4, row["epilogue_address"] + 4))
    return code.finish()


def _move_category_stub(address, native, move_register, move_categories):
    code = _Code(address)
    code.emit(0x5400043E | move_register << 21)  # clrlwi r0,rMove,16
    for identifier in move_categories:
        code.emit(0x28000000 | identifier)
        code.conditional(0x41820000, f"move_{identifier}")
    code.emit(branch(address + len(code.words) * 4, native))
    for identifier, category in move_categories.items():
        code.label(f"move_{identifier}")
        code.emit(0x38600000 | category, 0x4E800020)
    return code.finish()


def _helping_hand_iterator_stub(address, site, iterator):
    """Extend one scalar AI iterator, skipping Colosseum's absent358..374.

    r0 remains the original record count. Native IDs retain the exact native
    comparison; added ordinary IDs continue only through381. All reads in the
    qualified loop go through bounded native/new-row getters, never a table
    indexed here. There are no memory, stack, LR or unrelated GPR changes.
    """
    code = _Code(address)
    code.emit(0x7C040040)  # cmplw r4,r0
    code.conditional(0x41800000, "resume")
    code.emit(0x28040177)
    code.conditional(0x40800000, "added")
    code.emit(0x38000177 | iterator << 21, 0x38800177)
    code.label("added")
    code.emit(0x2804017E)
    code.conditional(0x41800000, "resume")
    code.emit(0x7C040040)
    code.label("resume")
    code.emit(branch(address + len(code.words)*4, site+4))
    return code.finish()


def install_move_category_callers(original_dol: bytes, current_dol: bytes,
                                 game_id: str, move_categories: Mapping[int, int]):
    """Extend bookkeeping, Hustle and Counter/Mirror Coat AI for added moves.

    The two core damage-calculator call sites are installed by the new-move
    runtime separately. Existing moves resume the shared native type category
    getter, which may already have its Fairy-only type interceptor installed.
    """
    layout = qualify_fairy_runtime(original_dol, game_id)
    if (not isinstance(move_categories, Mapping) or not 1 <= len(move_categories) <= 32
            or any(type(k) is not int or not 375 <= k < 0x7F00 or
                   type(v) is not int or v not in (0, 1, 2) for k, v in move_categories.items())):
        raise FormatError("added ordinary move categories require distinct new move IDs")
    categories = dict(sorted(move_categories.items()))
    offset, ram, setter, store, code = _reservation(original_dol, current_dol, game_id)
    output = bytearray(current_dol[:offset])
    hooks = []
    native = layout["qualifications"]["category"]["address"]
    for role, row in layout["category_callers"].items():
        window = _read(original_dol, row["window_address"], row["window_size"])
        if hashlib.sha256(window).hexdigest() != row["window_sha256"]:
            raise FormatError("unqualified native move-category caller")
        site = row["address"]
        position = _offset(original_dol, site)
        if current_dol[position:position + 4] != bytes.fromhex(row["word"]):
            raise FormatError("native move-category caller is already modified")
        stub = ram + len(code)
        payload = _move_category_stub(stub, native, row["move_register"], categories)
        code.extend(payload)
        struct.pack_into(">I", output, position, branch(site, stub, link=True))
        hooks.append({"role": role, "address": site, "move_register": row["move_register"],
                      "stub": stub, "bytes": len(payload)})
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Fairy move-category code exceeds owned memory")
    code[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    setter_pos = _offset(original_dol, setter)
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)), (setter_pos, branch(setter, ram))):
        struct.pack_into(">I", output, pos, value)
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (setter_pos, setter_pos + 4),
               (offset, offset + 32)]
    allowed += [(_offset(original_dol, h["address"]), _offset(original_dol, h["address"]) + 4) for h in hooks]
    if any(a != b and not any(lo <= i < hi for lo, hi in allowed)
           for i, (a, b) in enumerate(zip(current_dol, output))):
        raise FormatError("Fairy move-category patch changed unrelated bytes")
    return bytes(output), {"version": VERSION, "move_categories": categories,
                           "hooks": hooks, "existing_moves_keep_native_category": True,
                           "bytes_appended": len(output) - len(current_dol)}


def install_colosseum_category_callers(original_dol: bytes, current_dol: bytes,
                                     game_id: str, move_categories: Mapping[int, int]):
    """Compatibility entry point; new composition uses the shared installer."""
    if not game_id.startswith("GC6"):
        raise FormatError("these move-category callers belong to Colosseum")
    return install_move_category_callers(original_dol,current_dol,game_id,move_categories)


def qualify_fairy_runtime(original_dol: bytes, game_id: str) -> dict:
    layout = _LAYOUTS.get(game_id)
    if not layout or hashlib.sha256(original_dol).hexdigest() != layout["sha256"]:
        raise FormatError("unknown original Fairy-type executable")
    for role, row in layout["qualifications"].items():
        observed = _read(original_dol, row["address"], row["size"])
        if hashlib.sha256(observed).hexdigest() != row["sha256"]:
            raise FormatError(f"unqualified native Fairy {role} code")
    for row in _DIRECT_SPRITE_READS.get(game_id, ()):
        if (hashlib.sha256(_read(original_dol, row["address"], row["size"])).hexdigest() != row["sha256"]
                or _read(original_dol, row["site"] , 4) != bytes.fromhex(row["word"])
                or _read(original_dol, row["table"], 36) != struct.pack(">18H", *_COLO_JP_NATIVE_SPRITES)):
            raise FormatError("unqualified native Japanese type badge lookup")
    return layout


def install_fairy_type(original_dol: bytes, current_dol: bytes, game_id: str, *,
                      original_rel=None, current_rel=None, enabled=True,
                      badge_resources=None, small_badge_resources=None):
    """Return (DOL, REL, report), composing with the existing owned code arena.

    With no badge maps this installs battle lookups and native names only,
    for development qualification. Production callers must supply the real
    appended localized badge texture maps, including XD's separate small set.
    No sprite identity is redirected to an unregistered arbitrary descriptor.
    """
    if type(enabled) is not bool:
        raise ValueError("Fairy type enablement must be a boolean")
    if not enabled:
        return current_dol, current_rel, {"version": VERSION, "enabled": False}
    layout = qualify_fairy_runtime(original_dol, game_id)
    xd = game_id.startswith("GXX")
    if (original_rel is None) != (current_rel is None):
        raise FormatError("Fairy native REL inputs must be supplied together")
    if original_rel is not None and (not isinstance(original_rel, bytes) or not isinstance(current_rel, bytes)):
        raise FormatError("Fairy native REL inputs must be immutable bytes")
    badges = _resources(badge_resources, "Fairy badge") if badge_resources is not None else None
    small = _resources(small_badge_resources, "small Fairy badge") if small_badge_resources is not None else None
    if xd and bool(badges) != bool(small) or not xd and small is not None:
        raise FormatError("XD requires both native Fairy badge sizes")
    all_resources = list((badges or {}).values()) + list((small or {}).values())
    if len(set(all_resources)) != len(all_resources) or any(struct.pack(">I", resource) in original_dol for resource in all_resources):
        raise FormatError("Fairy texture resource identity collides with native data")
    offset, ram, setter, store, code = _reservation(original_dol, current_dol, game_id)
    output = bytearray(current_dol[:offset])
    hooks = []

    def append(payload):
        pointer = ram + len(code)
        code.extend(payload)
        code.extend(bytes(-len(code) % 32))
        return pointer

    banks = {language: append(_name_bank(language, game_id)) for language in LANGUAGES}
    functions = {key: value[0] for key, value in MESSAGE_FUNCTIONS[game_id][1].items()
                 if key in ("bank_open", "bank_close", "language")}
    refresh = append(_bank_refresh(ram + len(code), functions, banks, game_id))
    descriptors = {}
    if badges:
        for small_flag, resource_map in ((False, badges), (True, small)) if xd else ((False, badges),):
            key = "small_template" if small_flag else "sprite_template"
            template = _read(original_dol, layout["sprite_table"] +
                             layout["sprite_stride"] * layout[key + "_id"], layout["sprite_stride"])
            if hashlib.sha256(template).hexdigest() != layout[key + "_sha256"]:
                raise FormatError("native Fairy sprite template changed")
            identifier = FAIRY_SMALL_SPRITE if small_flag else FAIRY_SPRITE
            descriptors[identifier] = append(_descriptor(template, resource_map, game_id, small=small_flag))

    roles = ["category", "matchup", "name"]
    if badges:
        roles += (["sprite"] if "sprite" in layout["qualifications"] else [])
        roles += (["text_sprite"] if "text_sprite" in layout["qualifications"] else [])
        roles += ["sprite_descriptor"] + (["small_sprite"] if xd else [])
    for role in roles:
        row = layout["qualifications"][role]
        site, length = row["address"], row["size"]
        position = _offset(original_dol, site, length)
        if current_dol[position:position + length] != original_dol[position:position + length]:
            raise FormatError(f"native Fairy {role} hook is already modified")
        displaced = u32(original_dol, position)
        stub = ram + len(code)
        if role == "matchup":
            payload = _matchup_stub(stub, site + 4, displaced)
        elif role == "name":
            payload = _name_stub(stub, site + 4, displaced, refresh)
        elif role == "sprite_descriptor":
            payload = _descriptor_stub(stub, site + 4, displaced, descriptors)
        elif role == "text_sprite":
            payload = _text_sprite_stub(stub, site + 4, displaced,
                banks["ja"] + 24, layout["qualifications"]["sprite_text_compare"]["address"])
        else:
            value = {"category": 2, "sprite": FAIRY_SPRITE, "small_sprite": FAIRY_SMALL_SPRITE}[role]
            payload = _value_stub(stub, site + 4, displaced, value)
        append(payload)
        struct.pack_into(">I", output, position, branch(site, stub))
        hooks.append({"role": role, "address": site, "stub": stub, "bytes": len(payload)})
    if badges:
        for row in _DIRECT_SPRITE_READS.get(game_id, ()):
            site = row["site"]
            position = _offset(original_dol, site)
            displaced = int(row["word"], 16)
            if u32(current_dol, position) != displaced:
                raise FormatError("native Japanese type badge lookup is already modified")
            stub = ram + len(code)
            payload = _direct_sprite_stub(stub, site + 4, displaced)
            append(payload)
            struct.pack_into(">I", output, position, branch(site, stub))
            hooks.append({"role": "direct_type_sprite", "address": site,
                          "stub": stub, "bytes": len(payload), "native_table": row["table"]})
    if xd and badges:
        grid = _GRID_LAYOUTS[game_id]
        raw = _read(original_dol, grid["address"], grid["size"])
        if hashlib.sha256(raw).hexdigest() != grid["sha256"]:
            raise FormatError("unqualified native move effectiveness grid")
        site = grid["epilogue_address"]
        position = _offset(original_dol, site)
        if u32(current_dol, position) != grid["epilogue_word"]:
            raise FormatError("native move effectiveness grid is already modified")
        stub = ram + len(code)
        payload = _grid_stub(stub, grid)
        append(payload)
        struct.pack_into(">I", output, position, branch(site, stub))
        hooks.append({"role": "effectiveness_grid", "address": site,
                      "stub": stub, "bytes": len(payload)})

    helping = _HELPING_HAND_LAYOUTS[game_id]
    raw = _read(original_dol, helping["address"], helping["size"])
    if hashlib.sha256(raw).hexdigest() != helping["sha256"]:
        raise FormatError("unqualified native Helping Hand move scan")
    site = helping["compare_address"]
    position = _offset(original_dol, site)
    if u32(current_dol, position) != 0x7C040040:
        raise FormatError("native Helping Hand move scan is already modified")
    stub = ram+len(code)
    payload = _helping_hand_iterator_stub(stub, site, helping["iterator_register"])
    append(payload)
    struct.pack_into(">I", output, position, branch(site, stub))
    hooks.append({"role":"helping_hand_move_scan", "address":site,
                  "stub":stub, "bytes":len(payload)})

    # Include Fairy in the existing native AI's scan. Its Shadow(18) request
    # retains the native invalid/zero result and contributes no score.
    score = layout["qualifications"]["score"]
    score_site = score["address"] + layout["score_limit_offset"]
    score_pos = _offset(original_dol, score_site)
    if current_dol[score_pos:score_pos + 4] != bytes.fromhex(layout["score_limit_word"]):
        raise FormatError("native Fairy AI scan bound is already modified")
    struct.pack_into(">I", output, score_pos, 0x38000014)
    switch = _AI_SWITCH_LAYOUTS[game_id]
    raw = _read(original_dol, switch["address"], switch["size"])
    if hashlib.sha256(raw).hexdigest() != switch["sha256"]:
        raise FormatError("unqualified native AI switch type scan")
    switch_pos = _offset(original_dol, switch["bound_address"])
    if u32(current_dol, switch_pos) != switch["old_word"]:
        raise FormatError("native AI switch type scan is already modified")
    struct.pack_into(">I", output, switch_pos, 0x38000014)
    # Conversion2 writes by the count of resistant candidates, not by type ID.
    # Its native output allocation stays at 18 slots. The ordinary chart
    # has no Mystery 9 resistance, and the reserved Shadow 18 lookup returns 0;
    # including Fairy 19 therefore yields at most 18 eligible ordinary types.
    conversion = _CONVERSION_LAYOUTS[game_id]
    if hashlib.sha256(_read(original_dol, conversion["address"], conversion["size"])).hexdigest() != conversion["sha256"]:
        raise FormatError("unqualified native Conversion2 candidate collector")
    conversion_pos = _offset(original_dol, conversion["bound_address"])
    if u32(current_dol, conversion_pos) != conversion["old_word"]:
        raise FormatError("native Conversion2 collector bound is already modified")
    struct.pack_into(">I", output, conversion_pos, 0x28000014)
    purification_sites = []
    if xd:
        uniqueness = _PURIFICATION_LAYOUTS[game_id]
        raw = _read(original_dol, uniqueness["address"], uniqueness["size"])
        if hashlib.sha256(raw).hexdigest() != uniqueness["sha256"]:
            raise FormatError("unqualified native Purify Chamber type collection")
        # This one routine directly indexes a temporary byte array by type ID.
        # Reserve 32 stack bytes (including its 8-byte linkage area), clear the
        # 20 usable type entries, and leave the global count/table unchanged.
        for role, new_word in (("allocation", 0x38600020),
                               ("initialization", 0x38A00014)):
            site = uniqueness[role + "_address"]
            position = _offset(original_dol, site)
            if u32(current_dol, position) != uniqueness[role + "_word"]:
                raise FormatError("native Purify Chamber allocation is already modified")
            struct.pack_into(">I", output, position, new_word)
            purification_sites.append(site)
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Fairy type code exceeds the owned memory arena")
    code[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    setter_pos = _offset(original_dol, setter)
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)), (setter_pos, branch(setter, ram))):
        struct.pack_into(">I", output, pos, value)
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (setter_pos, setter_pos + 4),
               (offset, offset + 32), (score_pos, score_pos + 4),
               (switch_pos, switch_pos + 4), (conversion_pos, conversion_pos + 4)]
    allowed += [(_offset(original_dol, hook["address"]), _offset(original_dol, hook["address"]) + 4) for hook in hooks]
    allowed += [(_offset(original_dol, site), _offset(original_dol, site) + 4)
                for site in purification_sites]
    if any(before != after and not any(lo <= pos < hi for lo, hi in allowed)
           for pos, (before, after) in enumerate(zip(current_dol, output))):
        raise FormatError("Fairy patch changed an unrelated executable byte")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if (section["offset"], section["ram_address"], section["size"]) != (offset, ram, len(code)):
        raise FormatError("invalid final Fairy code reservation")
    return bytes(output), current_rel, {
        "version": VERSION, "enabled": True, "type_id": FAIRY_TYPE,
        "native_special_category": 2, "reserved_native_types_preserved": [9, 18],
        "native_type_tables_unchanged": True, "native_rel_unchanged": True,
        "native_name_id": FAIRY_NAME_ID, "native_name_languages": list(LANGUAGES),
        "native_badges_installed": bool(badges), "badge_resources": badges,
        "small_badge_resources": small, "sprite_descriptors": descriptors,
        "native_effectiveness_grid_includes_fairy": bool(xd and badges),
        "message_banks": banks, "hooks": hooks, "ai_scan_bound": 20,
        "ai_scan_site": score_site, "bytes_appended": len(output) - len(current_dol),
        "ai_switch_scan_bound": 20, "ai_switch_scan_site": switch["bound_address"],
        "ai_helping_hand_added_move_ids": list(range(375,382)),
        "ai_helping_hand_skips_absent_move_ids": list(range(358,375)) if not xd else [],
        "native_move_count_unchanged": True,
        "conversion2_includes_fairy": True, "conversion2_native_output_slots": 18,
        "conversion2_bound_site": conversion["bound_address"],
        "purification_type_buffer_slots": 20 if xd else None,
        "purification_type_buffer_stack_bytes": 32 if xd else None,
        "purification_type_buffer_sites": purification_sites,
        "qualified_original_sha256": layout["sha256"],
    }

# Exact six-region revision-0 fingerprints and narrow native qualifications.
_LAYOUTS = {'GC6P01': {'sha256': 'a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5',
            'sprite_stride': 72,
            'sprite_table': 2150798704,
            'sprite_template_id': 67,
            'sprite_template_sha256': '535c877f0086facf255f872c6dd865b56cbce61ad5e6da162ee77ad5b13e32f5',
            'score_limit_offset': 220,
            'score_limit_word': '800d8318',
            'qualifications': {'category': {'address': 2148596408,
                                            'size': 52,
                                            'sha256': 'fc7ac5d4c8585831ab7fd88a851473beb30ce7b95a93c1f473299496ae1a7355',
                                            'first_word': '800d8318'},
                               'sprite': {'address': 2148596356,
                                          'size': 52,
                                          'sha256': '20d4e4e81f4313429ea3d66edb64c97085b3f7032984b2a618593619770dd909',
                                          'first_word': '800d8318'},
                               'name': {'address': 2148596460,
                                        'size': 52,
                                        'sha256': 'ecaf6344dc405a83c9ff672353269f2a5ecd0a08d7a08fb988232031bf1d14a3',
                                        'first_word': '800d8318'},
                               'matchup': {'address': 2148596512,
                                           'size': 68,
                                           'sha256': '142550bb09e5b1c73bd025f78ff42ce306a0a590c36640ec27e1d100c22bb673',
                                           'first_word': '800d8318'},
                               'score': {'address': 2148596580,
                                         'size': 260,
                                         'sha256': 'f9d820c5a5118132234a304202e8a26cd6b0078c0d275325fb1775d46226c266',
                                         'first_word': '9421ffd0'},
                               'dual': {'address': 2148596840,
                                        'size': 252,
                                        'sha256': '492d7343f5e45d72563df3d14381102ded36c71f68ea077ed07feaa10eb54049',
                                        'first_word': '9421ffd0'},
                               'sprite_descriptor': {'address': 2147876916,
                                                     'size': 40,
                                                     'sha256': '1400f46d0d7a31069d74235d433746655907cbd22a05bfbec880b426b0046b42',
                                                     'first_word': '800d80e8'}},
            'category_callers': {'damage_bookkeeping': {'address': 2149758748,
                                                        'move_register': 30,
                                                        'window_address': 2149758732,
                                                        'window_size': 36,
                                                        'window_sha256': 'f00d26b2953aff661cd62c3169decd63608d491300b652707e76985f2d036ea1',
                                                        'word': '4bee439d'},
                                 'hustle_accuracy': {'address': 2149766752,
                                                     'move_register': 31,
                                                     'window_address': 2149766736,
                                                     'window_size': 36,
                                                     'window_sha256': '1986c121d84c273fcdf2c6f6d8e9ce82cded1abcb43ceec36a35088a27889f90',
                                                     'word': '4bee2459'},
                                 'mirror_coat_ai': {'address': 2149880152,
                                                    'move_register': 23,
                                                    'window_address': 2149880136,
                                                    'window_size': 36,
                                                    'window_sha256': '32c490aeaeef7e78bfcbfe45c83d9657881d6cbe5479173e15b239f109bb14db',
                                                    'word': '4bec6961'},
                                 'counter_ai': {'address': 2149880548,
                                                'move_register': 23,
                                                'window_address': 2149880532,
                                                'window_size': 36,
                                                'window_sha256': '894cfb9388d5832096c3a4ce4d4cdb0636b94e48525527f1d6014a1adba7283c',
                                                'word': '4bec67d5'}}},
 'GC6E01': {'sha256': '7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4',
            'sprite_stride': 24,
            'sprite_table': 2150530280,
            'sprite_template_id': 86,
            'sprite_template_sha256': '39b796c0179ecca2e86d1463e1620497032c674023f430e4c4977c3cfe802d69',
            'score_limit_offset': 220,
            'score_limit_word': '800d8318',
            'qualifications': {'category': {'address': 2148582560,
                                            'size': 52,
                                            'sha256': '5f8917809b3b925d4415b0cdd3859a36413b815a41ede2d755c4bdd0e9a045f9',
                                            'first_word': '800d8318'},
                               'sprite': {'address': 2148582508,
                                          'size': 52,
                                          'sha256': '542243cd677ad0de4299bcb7ffe148118408997edb7f3185628d00711feaec9a',
                                          'first_word': '800d8318'},
                               'name': {'address': 2148582612,
                                        'size': 52,
                                        'sha256': 'e5ba767a38853aa9dfce5c71b5380e44b24b13a77c648572200354217e0c02c6',
                                        'first_word': '800d8318'},
                               'matchup': {'address': 2148582664,
                                           'size': 68,
                                           'sha256': 'df5ec27c0b877cbf23ae46b5f03992e0d4d4d6e21d4707bdc353bbbdef8272b8',
                                           'first_word': '800d8318'},
                               'score': {'address': 2148582732,
                                         'size': 260,
                                         'sha256': 'f9d820c5a5118132234a304202e8a26cd6b0078c0d275325fb1775d46226c266',
                                         'first_word': '9421ffd0'},
                               'dual': {'address': 2148582992,
                                        'size': 252,
                                        'sha256': '492d7343f5e45d72563df3d14381102ded36c71f68ea077ed07feaa10eb54049',
                                        'first_word': '9421ffd0'},
                               'sprite_descriptor': {'address': 2147866712,
                                                     'size': 40,
                                                     'sha256': '5c1f13752b4eb085aa4d0703805639d30b3b24b57f9a8ecda429a06cef32ce43',
                                                     'first_word': '800d80e8'}},
            'category_callers': {'damage_bookkeeping': {'address': 2149739548,
                                                        'move_register': 30,
                                                        'window_address': 2149739532,
                                                        'window_size': 36,
                                                        'window_sha256': 'bf0a91767cd7c45c82663c32687a0165bc91375bb76a7e2de88db5a20dec630b',
                                                        'word': '4bee5885'},
                                 'hustle_accuracy': {'address': 2149747552,
                                                     'move_register': 31,
                                                     'window_address': 2149747536,
                                                     'window_size': 36,
                                                     'window_sha256': '1b7690f01cd1a5590821f3c271d079d576faaee41457cec5447b38a6ec7255e3',
                                                     'word': '4bee3941'},
                                 'mirror_coat_ai': {'address': 2149860912,
                                                    'move_register': 23,
                                                    'window_address': 2149860896,
                                                    'window_size': 36,
                                                    'window_sha256': '98218580951f0bbcd999fe7ac01c91342da7852d4c31e84c1db8120f65a8360b',
                                                    'word': '4bec7e71'},
                                 'counter_ai': {'address': 2149861308,
                                                'move_register': 23,
                                                'window_address': 2149861292,
                                                'window_size': 36,
                                                'window_sha256': 'e9ef78cfa930805d3376341d9545b0d3678ee7944b9ddc59a02fd2c9a8c42833',
                                                'word': '4bec7ce5'}}},
 'GC6J01': {'sha256': '64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2',
            'sprite_stride': 24,
            'sprite_table': 2150452408,
            'sprite_template_id': 86,
            'sprite_template_sha256': '39b796c0179ecca2e86d1463e1620497032c674023f430e4c4977c3cfe802d69',
            'score_limit_offset': 220,
            'score_limit_word': '800d8308',
            'qualifications': {'category': {'address': 2148572744,
                                            'size': 52,
                                            'sha256': 'cddc2f9482f1c1947294aa54b4c3eaf63afc5a229d8b71cd12d4bcca22aeb153',
                                            'first_word': '800d8308'},
                               'name': {'address': 2148572796,
                                        'size': 52,
                                        'sha256': '800e1ea4b1fba4748e05e222af02f7a6a680bb7b672739ecd6d9f93c22378410',
                                        'first_word': '800d8308'},
                               'matchup': {'address': 2148572848,
                                           'size': 68,
                                           'sha256': '60e57bb6da500834dcf95bed8a21b6f149e4067cebf756782dd230124563d8c0',
                                           'first_word': '800d8308'},
                               'score': {'address': 2148572916,
                                         'size': 260,
                                         'sha256': '85bfe4eff55f7ad0aad7ed79283f43cb149073d316f00f875be80852bd3de0f3',
                                         'first_word': '9421ffd0'},
                               'dual': {'address': 2148573176,
                                        'size': 252,
                                        'sha256': '492d7343f5e45d72563df3d14381102ded36c71f68ea077ed07feaa10eb54049',
                                        'first_word': '9421ffd0'},
                               'sprite_descriptor': {'address': 2147863092,
                                                     'size': 40,
                                                     'sha256': '006a16d1cd5c9f754f9c32e8439184744a177258354b2b1011695488c50d15a7',
                                                     'first_word': '800d80e0'},
                               'text_sprite': {'address': 0x8001E130, 'size': 0x90,
                                               'sha256': '4df7315b811756e08aea9c466aa531ca3a51432c2bd5219598f08d3dd240a83c',
                                               'first_word': '9421ffd0'},
                               'sprite_text_compare': {'address': 0x800F7AEC, 'size': 0x180,
                                               'sha256': '9f9b44ebff1fcf0bc8c3c8305cfc25161e022241860d969a968000b7ff33521a',
                                               'first_word': '9421ffe0'}},
            'category_callers': {'damage_bookkeeping': {'address': 2149721012,
                                                        'move_register': 30,
                                                        'window_address': 2149720996,
                                                        'window_size': 36,
                                                        'window_sha256': '0c84d95153557920e7a6f1ed41075fd3e41b3b177bad2bfe059e188e2ff057c2',
                                                        'word': '4bee7a95'},
                                 'hustle_accuracy': {'address': 2149729016,
                                                     'move_register': 31,
                                                     'window_address': 2149729000,
                                                     'window_size': 36,
                                                     'window_sha256': '25a880075efe4190cff68aa71d136533d1ffdaecbd84543178efcf60be53d5bc',
                                                     'word': '4bee5b51'},
                                 'mirror_coat_ai': {'address': 2149842376,
                                                    'move_register': 23,
                                                    'window_address': 2149842360,
                                                    'window_size': 36,
                                                    'window_sha256': 'f4d4c5a2f7c83fed63988cbc5a368cf5022f8a0d6317a8e1cb87a7c14748d681',
                                                    'word': '4beca081'},
                                 'counter_ai': {'address': 2149842772,
                                                'move_register': 23,
                                                'window_address': 2149842756,
                                                'window_size': 36,
                                                'window_sha256': 'd4abc350f58fd2875fb3eac8d2e0d88faa8a5af97377b06f7f5ca9ee6b63efc0',
                                                'word': '4bec9ef5'}}},
 'GXXP01': {'sha256': 'a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd',
            'sprite_stride': 72,
            'sprite_table': 2150635736,
            'sprite_template_id': 116,
            'sprite_template_sha256': 'bfdf481b3167d5db386fe5f3e40dfd72d6dfde631227a4c339c823e91eadc921',
            'small_template_id': 414,
            'small_template_sha256': '37f2cae92a319c6f9044c6c9b229556930f246ff7dcef1b1b64fd9b98e53e0d8',
            'score_limit_offset': 304,
            'score_limit_word': '80030000',
            'qualifications': {'category': {'address': 2148635144,
                                            'size': 48,
                                            'sha256': 'ca28e96cdaee36502a8b34f2d6755c9b7b71332ab5aec54d262f3f408d1f1a2c',
                                            'first_word': '808d89a8'},
                               'sprite': {'address': 2148635092,
                                          'size': 52,
                                          'sha256': '2b92ffaf540ad1ace079bd60fc907dcb9a54a8fe21e7dfba7d9deadc5a3ff920',
                                          'first_word': '808d89a8'},
                               'name': {'address': 2148635192,
                                        'size': 52,
                                        'sha256': 'ee065423128c7c0f5b2d34ec1e68f116575ba6288ef9c1c0d8ee32bb2239822b',
                                        'first_word': '808d89a8'},
                               'matchup': {'address': 2148635244,
                                           'size': 68,
                                           'sha256': 'd2a3c6b2c947fb7caab46d94b91f151235c0d34d8f41ef4782c330d1b9111fad',
                                           'first_word': '80ad89a8'},
                               'score': {'address': 2148634028,
                                         'size': 340,
                                         'sha256': '0804c48c3e3c08879052fcc31f934467d34ca67d10e39dc13068472c328c7ed3',
                                         'first_word': '9421ffd0'},
                               'dual': {'address': 2148634368,
                                        'size': 256,
                                        'sha256': '3915598ddc428bff70b64de32073d111e5b9152850cd8aeef8a4766250b2b5da',
                                        'first_word': '9421ffd0'},
                               'sprite_descriptor': {'address': 2147996204,
                                                     'size': 40,
                                                     'sha256': 'fce85f0d6f612c74c1105e78ac1a9739f5e3580c1e39cb176fe9a5c337ee28da',
                                                     'first_word': '800d8038'},
                               'small_sprite': {'address': 2148635040,
                                                'size': 52,
                                                'sha256': '218e74a24e6bc93a51bac4fca0aba2cf2a689a1fa2227cf13c0f8c97e584a18f',
                                                'first_word': '808d89a8'}}},
 'GXXE01': {'sha256': 'c8659341c252d1b088753d508769344eb6f092b5da5cc7cc0ce1560b32478c15',
            'sprite_stride': 72,
            'sprite_table': 2150629800,
            'sprite_template_id': 116,
            'sprite_template_sha256': 'bfdf481b3167d5db386fe5f3e40dfd72d6dfde631227a4c339c823e91eadc921',
            'small_template_id': 414,
            'small_template_sha256': '37f2cae92a319c6f9044c6c9b229556930f246ff7dcef1b1b64fd9b98e53e0d8',
            'score_limit_offset': 304,
            'score_limit_word': '80030000',
            'qualifications': {'category': {'address': 2148629188,
                                            'size': 48,
                                            'sha256': 'ca28e96cdaee36502a8b34f2d6755c9b7b71332ab5aec54d262f3f408d1f1a2c',
                                            'first_word': '808d89a8'},
                               'sprite': {'address': 2148629136,
                                          'size': 52,
                                          'sha256': '2b92ffaf540ad1ace079bd60fc907dcb9a54a8fe21e7dfba7d9deadc5a3ff920',
                                          'first_word': '808d89a8'},
                               'name': {'address': 2148629236,
                                        'size': 52,
                                        'sha256': 'ee065423128c7c0f5b2d34ec1e68f116575ba6288ef9c1c0d8ee32bb2239822b',
                                        'first_word': '808d89a8'},
                               'matchup': {'address': 2148629288,
                                           'size': 68,
                                           'sha256': 'd2a3c6b2c947fb7caab46d94b91f151235c0d34d8f41ef4782c330d1b9111fad',
                                           'first_word': '80ad89a8'},
                               'score': {'address': 2148628072,
                                         'size': 340,
                                         'sha256': '0804c48c3e3c08879052fcc31f934467d34ca67d10e39dc13068472c328c7ed3',
                                         'first_word': '9421ffd0'},
                               'dual': {'address': 2148628412,
                                        'size': 256,
                                        'sha256': '3915598ddc428bff70b64de32073d111e5b9152850cd8aeef8a4766250b2b5da',
                                        'first_word': '9421ffd0'},
                               'sprite_descriptor': {'address': 2147994184,
                                                     'size': 40,
                                                     'sha256': '45db66133b300fa45a0a4f50db4f0cb9ec1b92d53321fbd2c95d033863a42e04',
                                                     'first_word': '800d8038'},
                               'small_sprite': {'address': 2148629084,
                                                'size': 52,
                                                'sha256': '218e74a24e6bc93a51bac4fca0aba2cf2a689a1fa2227cf13c0f8c97e584a18f',
                                                'first_word': '808d89a8'}}},
 'GXXJ01': {'sha256': '14c129cc0f79682574f635290b09e37fa2a652ac5aa5565281bd583c31c5d702',
            'sprite_stride': 24,
            'sprite_table': 2150605920,
            'sprite_template_id': 119,
            'sprite_template_sha256': 'b6be99bfb88e17c0c7d070c8e75788c5943462b17304ef6cb5b5eb85fa0a13f5',
            'small_template_id': 417,
            'small_template_sha256': '727a78a27d0b5deb16b67bce085dc115f8b6f1f0424f3941beced7fac680cd8e',
            'score_limit_offset': 304,
            'score_limit_word': '80030000',
            'qualifications': {'category': {'address': 2148610400,
                                            'size': 48,
                                            'sha256': 'ca28e96cdaee36502a8b34f2d6755c9b7b71332ab5aec54d262f3f408d1f1a2c',
                                            'first_word': '808d89a8'},
                               'sprite': {'address': 2148610348,
                                          'size': 52,
                                          'sha256': '2b92ffaf540ad1ace079bd60fc907dcb9a54a8fe21e7dfba7d9deadc5a3ff920',
                                          'first_word': '808d89a8'},
                               'name': {'address': 2148610448,
                                        'size': 52,
                                        'sha256': 'ee065423128c7c0f5b2d34ec1e68f116575ba6288ef9c1c0d8ee32bb2239822b',
                                        'first_word': '808d89a8'},
                               'matchup': {'address': 2148610500,
                                           'size': 68,
                                           'sha256': 'd2a3c6b2c947fb7caab46d94b91f151235c0d34d8f41ef4782c330d1b9111fad',
                                           'first_word': '80ad89a8'},
                               'score': {'address': 2148609284,
                                         'size': 340,
                                         'sha256': '0804c48c3e3c08879052fcc31f934467d34ca67d10e39dc13068472c328c7ed3',
                                         'first_word': '9421ffd0'},
                               'dual': {'address': 2148609624,
                                        'size': 256,
                                        'sha256': '3915598ddc428bff70b64de32073d111e5b9152850cd8aeef8a4766250b2b5da',
                                        'first_word': '9421ffd0'},
                               'sprite_descriptor': {'address': 2147986992,
                                                     'size': 40,
                                                     'sha256': '824f38b55b5997034d101369d0edbc3e4665add63c217b139da3e001aed7e7a3',
                                                     'first_word': '800d8038'},
                               'small_sprite': {'address': 2148610296,
                                                'size': 52,
                                                'sha256': '218e74a24e6bc93a51bac4fca0aba2cf2a689a1fa2227cf13c0f8c97e584a18f',
                                                'first_word': '808d89a8'}}}}


# Qualified ordinary XD category callers; the native Shadow path already uses
# the separate move-aware getter. Core active/bench damage sites live in the
# move-runtime installer, while these keep bookkeeping, accuracy and AI aligned.
_XD_CATEGORY_CALLERS = {'GXXP01': {'damage_bookkeeping': {'address': 2149676620,
                                   'move_register': 25,
                                   'window_address': 2149676604,
                                   'window_size': 36,
                                   'window_sha256': '41fcc4066886eb57154440a38939578f7fc36b0ae901c87cd8cd47202882bf32',
                                   'word': '4bf01bbd'},
            'hustle_accuracy': {'address': 2149684796,
                                'move_register': 20,
                                'window_address': 2149684780,
                                'window_size': 36,
                                'window_sha256': '81e222f22007951f55fbb51e187fb8aa07bdc257b06e481c4af7fc2ac786f2cd',
                                'word': '4beffbcd'},
            'mirror_coat_ai': {'address': 2150517952,
                               'move_register': 27,
                               'window_address': 2150517936,
                               'window_size': 36,
                               'window_sha256': '594c1d06ac237a48099ee78665122ba78cfee8b7a7767844034c4c17b3f7f7db',
                               'word': '4be34549'},
            'counter_ai': {'address': 2150518236,
                           'move_register': 27,
                           'window_address': 2150518220,
                           'window_size': 36,
                           'window_sha256': 'e69b066e2dca6c7d6759cd9fa29929dd689fbe9b9d6069ce2f7b938669222290',
                           'word': '4be3442d'}},
 'GXXE01': {'damage_bookkeeping': {'address': 2149668872,
                                   'move_register': 25,
                                   'window_address': 2149668856,
                                   'window_size': 36,
                                   'window_sha256': 'ab592e98f95db67511a64a0d2233facf6f926c554c533f3186e45d7798cadede',
                                   'word': '4bf022bd'},
            'hustle_accuracy': {'address': 2149677048,
                                'move_register': 20,
                                'window_address': 2149677032,
                                'window_size': 36,
                                'window_sha256': 'a45421b38009e52b47aac927d8a390e59cd6f258b06cca48c85256a1a8c0d0a3',
                                'word': '4bf002cd'},
            'mirror_coat_ai': {'address': 2150509920,
                               'move_register': 27,
                               'window_address': 2150509904,
                               'window_size': 36,
                               'window_sha256': '0309e53c921e18391a9053508c123adeeb3bdbb9765bf2dbf60c9cf695f189ed',
                               'word': '4be34d65'},
            'counter_ai': {'address': 2150510204,
                           'move_register': 27,
                           'window_address': 2150510188,
                           'window_size': 36,
                           'window_sha256': '2d5581e214afc5370558c3df605b744a29765d60cba6ae3437f9d50a2054c5fb',
                           'word': '4be34c49'}},
 'GXXJ01': {'damage_bookkeeping': {'address': 2149646852,
                                   'move_register': 25,
                                   'window_address': 2149646836,
                                   'window_size': 36,
                                   'window_sha256': '11c5d3aa59a1b998ba004ebba6818e43c91ed041923de99dfe805c3e275f2aa9',
                                   'word': '4bf02f5d'},
            'hustle_accuracy': {'address': 2149655004,
                                'move_register': 20,
                                'window_address': 2149654988,
                                'window_size': 36,
                                'window_sha256': '5b687586be3e61c3fb26201849c1e633bf6555c233887910c5540022cc183656',
                                'word': '4bf00f85'},
            'mirror_coat_ai': {'address': 2150487584,
                               'move_register': 27,
                               'window_address': 2150487568,
                               'window_size': 36,
                               'window_sha256': 'd340090916d4041a995e66cfb8364235bd5fb5cac373bdc862a1d49ebbb55ad6',
                               'word': '4be35b41'},
            'counter_ai': {'address': 2150487868,
                           'move_register': 27,
                           'window_address': 2150487852,
                           'window_size': 36,
                           'window_sha256': '0aaa5efaf34f2f25ff10d118cf413e546604cc1c7a9199bd1ae369dfdef5848b',
                           'word': '4be35a25'}}}
for _game, _callers in _XD_CATEGORY_CALLERS.items():
    _LAYOUTS[_game]["category_callers"] = _callers


_HELPING_HAND_LAYOUTS = {
 'GC6P01': {'address':2149867972,'size':128,'sha256':'4bccce5aef26446f12739df470d9b688abd8ec494d2f9db3f40e0a0670507f38','compare_address':2149868092,'iterator_register':22,'native_count':358},
 'GC6E01': {'address':2149848732,'size':128,'sha256':'52223f88d936efad912e9ab9a65f1f4dcb9b1855e848a89a00603b1d32d01ce7','compare_address':2149848852,'iterator_register':22,'native_count':358},
 'GC6J01': {'address':2149830196,'size':128,'sha256':'8dcf5945e877290b1b9993a4ea96baa951cc61dcb3fa5667b596732b8bd5a7d5','compare_address':2149830316,'iterator_register':22,'native_count':358},
 'GXXP01': {'address':2150509652,'size':128,'sha256':'3f82a84f1fd47a807db40aaddf07f403469c685175b7c9fa40a5e295c3c3fa12','compare_address':2150509772,'iterator_register':23,'native_count':375},
 'GXXE01': {'address':2150501620,'size':128,'sha256':'1a2716aa3b293f254e599b805d5e26e39ebf377b6c5a6486b356352f956f59eb','compare_address':2150501740,'iterator_register':23,'native_count':375},
 'GXXJ01': {'address':2150479284,'size':128,'sha256':'9e5660178ac92c7bc4bcbd16f2e4aaa8fd5e494b4ca5205a0fe2a1acd2cff00b','compare_address':2150479404,'iterator_register':23,'native_count':375},
}


_CONVERSION_LAYOUTS = {'GC6P01': {'address': 2149630764,
            'size': 260,
            'sha256': 'a0dc98d053cb3ffced8f6042f14c90205b3e777a2814ec33648a84d89312062a',
            'bound_address': 2149630992,
            'old_word': 671088658},
 'GC6E01': {'address': 2149611996,
            'size': 260,
            'sha256': '4c2d3fe351ade0cc184281992f3ea61d506159ffd7d75d1c22d2efdc021ae6bb',
            'bound_address': 2149612224,
            'old_word': 671088658},
 'GC6J01': {'address': 2149593756,
            'size': 260,
            'sha256': '9da2351bea66242e9722a8744a7f776d838aff77c20336e2a20585a6e9167ac7',
            'bound_address': 2149593984,
            'old_word': 671088658},
 'GXXP01': {'address': 2149609844,
            'size': 188,
            'sha256': '398776ac6714b56694e945b7285df16eeb7392ed9424e22694f9ae9a043b0cd1',
            'bound_address': 2149610000,
            'old_word': 671088658},
 'GXXE01': {'address': 2149602368,
            'size': 188,
            'sha256': 'a8ecd8e3d57efc7ceee9496a39d8eaa9976d5f8d4be80781955702c1d43fbc1c',
            'bound_address': 2149602524,
            'old_word': 671088658},
 'GXXJ01': {'address': 2149581036,
            'size': 188,
            'sha256': '082b0f0357331ec055ec14800d03489aabab5a02b331805a375bc52a43ada1db',
            'bound_address': 2149581192,
            'old_word': 671088658}}


_PURIFICATION_LAYOUTS = {'GXXP01': {'address': 2150168904,
            'size': 364,
            'sha256': '6538fc1d72b3674f4675aeaad22c713085bb2f8378d927aca33c363180f40d51',
            'allocation_address': 2150168940,
            'initialization_address': 2150168972,
            'allocation_word': 2154102784,
            'initialization_word': 2158297088},
 'GXXE01': {'address': 2150160908,
            'size': 364,
            'sha256': 'e45f37d4fba807ed05b29a9d6ab25061ef63a40a14e09f4d80543b01a901d79e',
            'allocation_address': 2150160944,
            'initialization_address': 2150160976,
            'allocation_word': 2154102784,
            'initialization_word': 2158297088},
 'GXXJ01': {'address': 2150138932,
            'size': 364,
            'sha256': 'd4566e90871d723447b405ee559944143e76115e350907a60751a748cd6f049d',
            'allocation_address': 2150138968,
            'initialization_address': 2150139000,
            'allocation_word': 2154102784,
            'initialization_word': 2158297088}}


_GRID_LAYOUTS = {'GXXP01': {'address': 2147695660,
            'size': 4148,
            'sha256': '9da6fe5b6e97b032e3073d74d29c8e1966258e3c78adeb114c16ee53ba184f6e',
            'epilogue_address': 2147699788,
            'epilogue_word': 3137404944,
            'compatible': 2148793572,
            'move_status': 2148789664,
            'affinity': 2148635244,
            'layer': 2148597572,
            'draw_sprite': 2148623728},
 'GXXE01': {'address': 2147696284,
            'size': 4084,
            'sha256': 'c6c610fea74cf0c8a509e103686d53f47ca2968e53a5e1f99c09f85e3d14ead9',
            'epilogue_address': 2147700348,
            'epilogue_word': 3139502100,
            'compatible': 2148787232,
            'move_status': 2148783324,
            'affinity': 2148629288,
            'layer': 2148591648,
            'draw_sprite': 2148617772},
 'GXXJ01': {'address': 2147694240,
            'size': 4084,
            'sha256': '2052acb4c521d2a789c86294992685b6e63d714d5ab454c7797a618a8c1d632c',
            'epilogue_address': 2147698304,
            'epilogue_word': 3139502100,
            'compatible': 2148767788,
            'move_status': 2148763880,
            'affinity': 2148610500,
            'layer': 2148573264,
            'draw_sprite': 2148599052}}


_AI_SWITCH_LAYOUTS = {'GC6P01': {'address': 2149924488,
            'size': 280,
            'sha256': 'b4c14100cc15537ef555ad912259ec63906ce901f938c782cbda1cc639f95b2b',
            'bound_address': 2149924752,
            'old_word': 2148369176},
 'GC6E01': {'address': 2149905248,
            'size': 280,
            'sha256': 'c9192d476cc40f8e4335b2ab0ef33e86c081fc939fcb5a814e5470d2c5a29744',
            'bound_address': 2149905512,
            'old_word': 2148369176},
 'GC6J01': {'address': 2149886712,
            'size': 280,
            'sha256': '0f3bedef5874e42eb824c89d35900457e4aba89d7563e0950062f6809dfa6667',
            'bound_address': 2149886976,
            'old_word': 2148369160},
 'GXXP01': {'address': 2150423020,
            'size': 232,
            'sha256': 'df92954811f5e5566e29aec46f6fcd86092a4ad22f45bb0cbc2a49ed1766571f',
            'bound_address': 2150423240,
            'old_word': 2147680256},
 'GXXE01': {'address': 2150414988,
            'size': 232,
            'sha256': 'ff6c6caa60d107d6528c37d4fe265513cc0c20dc686afe25161dd34e0567f656',
            'bound_address': 2150415208,
            'old_word': 2147680256},
 'GXXJ01': {'address': 2150393012,
            'size': 232,
            'sha256': 'ce9448565c041ec9fe0cf368501b4ca3a02cce20f9cb0e386af6a2dd398be354',
            'bound_address': 2150393232,
            'old_word': 2147680256}}
