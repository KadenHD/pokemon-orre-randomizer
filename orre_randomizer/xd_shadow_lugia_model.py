"""Display any Shadow Lugia without changing its saved identity or mechanics.

The original dark model stays intact. A color-only alternate PKX is appended
to its existing archive, and the native ModelSequence constructor selects it
for each specimen's native PID/OT shiny decision. An opt-in display rule can
retain that appearance after purification; never-Shadow Lugia stays ordinary.
Authored field DAT variants use the same encounter identity before actor loading.
"""
from __future__ import annotations

import hashlib
import struct

from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, parse_fsys, u32
from .engine.gift_move_hooks import branch
from .engine.plusle_actor import _XD_MODEL_TABLE
from .engine.rebuild_iso import decoded_member
from .engine.shadow_lugia_palette import make_shadow_lugia_shiny, make_shadow_lugia_shiny_dat
from .engine.shadow_lugia_face import append_shadow_lugia_shiny_face, install_xd_shadow_lugia_face
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_shadow_shinies import _LAYOUTS as IDENTITIES, shadow_statuses
from .xd_spinda import _load_address
from .xd_spinda_field import _LAYOUTS as SHADOW_STATE

VERSION = "xd-any-shadow-lugia-model-v3"
ARCHIVE = "pkx_darklugia.fsys"
DARK_MODEL, SHADOW_ID = 417, 73
RESOURCE = 0x7DF41E00
FIELD_ARCHIVE = "people_archive.fsys"
FIELD_RESOURCES = ((0x166C0400, 0x7DF60400), (0x1F540400, 0x7DF70400), (0x220E0400, 0x7DF80400))
_FIELD_SHA256 = {
    0x166C0400: "7ca2b475f94dc732ad7d63fd18e2582a62aa4b595ae9714a576cd1e38b9d099a",
    0x1F540400: "dcf5130a1dfbae575783971c0dfc21ba8b324bbb83daf7cc5da1d5d8eb8e4b21",
    0x220E0400: "a89fe0f90974014961167a4ea8c40c2ef2b7c40e39c138dd0bd8f05a74118750",
}
FACE_ALIAS = (0x5C0, 0x21581200, 0x7DF51200)
# Exact resource-load boundary in each native ModelSequence constructor.
_HOOKS = {"GXXP01": (0x801DABDC, 0x801D5D74, 0x80145A20),
          "GXXE01": (0x801D908C, 0x801D426C, 0x8014415C),
          "GXXJ01": (0x801D3F2C, 0x801CF10C, 0x8013F568)}
_RARE_CHECK = bytes.fromhex(
    "5465843e5460043e5486843e5484043e7ca30278380000087cc31a787c831a78"
    "7c0018107c0001107c6000d04e800020")

# Independently matched retail call windows. These are display requests only;
# the shared isShadow predicate used by battle mechanics remains untouched.
_DISPLAY_CALLS = {
    "GXXP01": (0x801418C8, 0x80207478, 0x80112FE0, 0x801139D8, 0x80050B48),
    "GXXE01": (0x80140004, 0x80205744, 0x8011189C, 0x80112294, 0x800509F8),
    "GXXJ01": (0x8013B410, 0x802003F0, 0x8010D0BC, 0x8010DAB4, 0x8004F5D0),
}
_DISPLAY_WINDOWS = (
    (0x7FC3F378, 0x5460063E, 0x28000001, 0x40820008, 0x3BE001A1),
    (0x7FA3EB78, 0x5460063E, 0x28000001, 0x40820008, 0x3BC001A1),
    (0x7F83E378, 0x5460063E, 0x28000000, 0x4182000C, 0x38600345),
    (0x7FE3FB78, 0x5460063E, 0x28000000, 0x4182000C, 0x380001A1),
)
# The Purify Chamber separately loads the post-purification model. Retail code
# hardcodes ordinary Lugia here instead of using the menu/battle display getter.
# r31 still owns the full specimen; r4/r5 already contain its native PID/rarity.
_CEREMONY_MODELS = {"GXXP01": 0x80234E3C, "GXXE01": 0x80232FF8, "GXXJ01": 0x8022D994}
_MODEL_LOADERS = {"GXXP01": 0x801D4400, "GXXE01": 0x801D28F8, "GXXJ01": 0x801CD798}


def _retained_display_stub(address):
    """Cosmetic predicate: only a real Lugia carrying a former Shadow ID."""
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "ordinary")
    code.emit(0xA0030000, 0x280000F9)
    code.conditional(0x40820000, "ordinary")
    code.emit(0xA00300BA, 0x28000000)
    code.conditional(0x41820000, "ordinary")
    code.emit(0x28000053)
    code.conditional(0x41810000, "ordinary")
    code.emit(0x38600001, 0x4E800020)
    code.label("ordinary")
    code.emit(0x38600000, 0x4E800020)
    return code.finish()


def _retained_snag_copy_stub(address, setter):
    """Keep provenance on a purified Snag List display copy, never a saved row."""
    code = _Code(address)
    code.emit(0x28030000)
    code.conditional(0x41820000, "native")
    code.emit(0xA0030000, 0x280000F9)
    code.conditional(0x40820000, "native")
    code.emit(0x281E0000)
    code.conditional(0x41820000, "native")
    code.emit(0x281E0053)
    code.conditional(0x41810000, "native")
    code.emit(0x7FC4F378)  # native selected Shadow ID in r30
    code.label("native")
    code.emit(branch(address + len(code.words)*4, setter))
    return code.finish()


def _retained_ceremony_stub(address, continuation):
    """Retain the real former Shadow's model in the ceremony's second load."""
    code = _Code(address)
    code.emit(0x386000F9, 0x281F0000)  # displaced ordinary model; full specimen r31
    code.conditional(0x41820000, "native")
    code.emit(0xA01F0000, 0x280000F9)
    code.conditional(0x40820000, "native")
    code.emit(0xA01F00BA, 0x28000000)
    code.conditional(0x41820000, "native")
    code.emit(0x28000053)
    code.conditional(0x41810000, "native")
    code.emit(0x386001A1)
    code.label("native")
    code.emit(branch(address + 4*len(code.words), continuation))
    return code.finish()


def _install_retained_ceremony(original, current, game_id):
    hook = _CEREMONY_MODELS[game_id]
    pos = hook - TEXT1_TO_RAM
    expected = bytes.fromhex("7c641b787f45d378386000f9")
    expected += struct.pack(">I", branch(hook+4, _MODEL_LOADERS[game_id], link=True))
    expected += bytes.fromhex("388001047c7d1b7838a00004")
    for data in (original, current):
        if data[pos-8:pos+20] != expected:
            raise FormatError("unexpected XD post-purification Lugia model load")
    return append_xd_dol_text(original, current, game_id, (
        (hook, 0x386000F9, _retained_ceremony_stub),
    ))


def _install_retained_displays(original, current, game_id):
    from .engine.gift_move_hooks import _branch_target
    definitions = []
    calls = _DISPLAY_CALLS[game_id]
    for call, words in zip(calls[:4], _DISPLAY_WINDOWS, strict=True):
        pos = call - TEXT1_TO_RAM
        for data in (original, current):
            window = struct.unpack_from(">6I", data, pos-4)
            if (window[0], *window[2:]) != words or window[1] >> 26 != 18 or window[1] & 3 != 1:
                raise FormatError("unexpected XD Lugia display predicate")
        definitions.append((call, u32(original, pos),
                            lambda address, _continuation: _retained_display_stub(address)))
    call = calls[4]
    pos = call - TEXT1_TO_RAM
    for data in (original, current):
        window = struct.unpack_from(">6I", data, pos-8)
        if (window[0:2], window[3:]) != ((0x387D0004, 0x38800000),
                                                      (0x387D0004, 0x80010024, 0x83E1001C)):
            raise FormatError("unexpected XD purified Snag List display copy")
    setter = _branch_target(call, u32(original, pos))
    if original[setter-TEXT1_TO_RAM:setter-TEXT1_TO_RAM+16] != bytes.fromhex(
            "280300004d820020b08300ba4e800020"):
        raise FormatError("unexpected XD Shadow ID display-copy setter")
    definitions.append((call, u32(original, pos), lambda address, _continuation:
                        _retained_snag_copy_stub(address, setter)))
    return append_xd_dol_text(original, current, game_id, definitions, link=True)


def _model_stub(address, continuation):
    """The native dark-model request already carries this specimen's shiny flag.

    Do not substitute XD001's saved PID or seed status for another Lugia.
    Authored XD001 field actors have their own identity-aware DAT selector.
    """
    code = _Code(address)
    code.emit(0x281B0000 | DARK_MODEL)  # r27: native model index
    code.conditional(0x40820000, "native")
    code.emit(0x281D0000)  # r29: native PID/OT shiny decision
    code.conditional(0x41820000, "native")
    _load_address(code, 4, RESOURCE)
    code.emit(0x3BC00001, 0x3BA00001)  # real rare resource; skip generic tint
    code.label("native")
    code.emit(0x7FE3FB78)  # displaced mr r3,r31: original archive group
    code.emit(branch(address + 4 * len(code.words), continuation))
    return code.finish()


def load_shadow_lugia_field_model(dol, game_id, read_archive, *, scale=1.0, shiny=False):
    """Convert the real dark model for a proven Shadow actor, never ordinary NPCs."""
    from .engine.plusle_actor import _field_model, _pkx_idle_motion
    group, resource = struct.unpack_from(">II", dol, _XD_MODEL_TABLE[game_id] + DARK_MODEL*8)
    if (group, resource) != (2263, 0x19661E00):
        raise FormatError("unexpected original XD dark field model entry")
    archive = read_archive(ARCHIVE)
    members = [m for m in parse_fsys(archive)["members"]
               if int(m["identifier_raw"], 16) == resource]
    if len(members) != 1:
        raise FormatError("expected one native dark Lugia field source")
    pkx = decoded_member(archive, members[0])
    if shiny:
        pkx = make_shadow_lugia_shiny(pkx, xd=True)
    idle = _pkx_idle_motion(pkx, xd=True)
    return _field_model(pkx, header_size=0xE60, scale=scale, motion_indices=(idle,)*12)


def _field_actor_stub(address, continuation, layout, identity, rare_check, *, startup,
                      fallback=False, routes=None):
    """Select an authored field DAT before the native actor resource load."""
    code = _Code(address)
    register = 30 if startup else 27
    if routes is None:
        routes = tuple((source, target, SHADOW_ID, fallback) for source, target in FIELD_RESOURCES)
    for index, (source, _target, _shadow, _default) in enumerate(routes):
        _load_address(code, 0, source)
        code.emit(0x7C000040 | register << 16)
        code.conditional(0x41820000, f"matched_{index}")
    code.jump("native")
    for index, (_source, target, shadow, default) in enumerate(routes):
        code.label(f"matched_{index}")
        code.emit(0x9421FFD0, 0x7C0802A6, 0x90010034,
                  0x90610008, 0x9081000C, 0x90A10010, 0x90C10014)
        _load_address(code, 0, target)
        code.emit(0x90010018, 0x38000000 | shadow, 0x9001001C,
                  0x38000000 | int(default), 0x90010020)
        code.jump("identity")
    code.label("identity")
    code.emit(0x8061001C)
    code.call(layout.shadow_seen)
    code.emit(0x28030000)
    code.conditional(0x41820000, "not_generated")
    code.emit(0x8061001C)
    code.call(layout.shadow_pid)
    code.emit(0x9061001C, 0x38600000, 0x38800002)
    code.call(identity.player_lookup)
    code.emit(0x28030000)
    code.conditional(0x41820000, "restore")
    code.emit(0x8063002C, 0x8081001C)
    code.call(rare_check)
    code.emit(0x28030000)
    code.conditional(0x41820000, "restore")
    code.jump("variant")
    code.label("not_generated")
    code.emit(0x80010020, 0x28000000)
    code.conditional(0x41820000, "restore")
    code.label("variant")
    code.emit(0x80010018, 0x7C000378 | register << 16)  # mr resource,r0
    code.label("restore")
    code.emit(0x80610008, 0x8081000C, 0x80A10010, 0x80C10014,
              0x80010034, 0x7C0803A6, 0x38210030)
    code.label("native")
    code.emit(0x7C7B1B78 if startup else 0x28030000)
    code.emit(branch(address + 4 * len(code.words), continuation))
    return code.finish()


def install_shadow_lugia_model(original, current, game_id, read_archive, updates, *, seed, options):
    """Add native display variants without generating or modifying a Pokemon PID."""
    identity = IDENTITIES[game_id]
    if hashlib.sha256(original).hexdigest() != identity.original_sha256:
        raise FormatError("unexpected original XD Shadow Lugia executable")
    hook, loader, rare_check = _HOOKS[game_id]
    layout = SHADOW_STATE[game_id]
    # Adjacent to the earlier Gateon/Spinda selectors, before resource loading.
    field_read, field_open = layout.people_epilogue - 0x148, layout.open_epilogue - 0x54
    window = bytes.fromhex("418200107cdf33787ce43b783bc000017fe3fb78")
    window += struct.pack(">I", branch(hook + 4, loader, link=True))
    window += bytes.fromhex("7c641b79b3fa004440820014380000017f43d378981a0007")
    position = hook - TEXT1_TO_RAM
    for data in (original, current):
        if (data[position - 16:position + 32] != window
                or data[rare_check - TEXT1_TO_RAM:rare_check - TEXT1_TO_RAM + len(_RARE_CHECK)] != _RARE_CHECK
                or data[field_read - TEXT1_TO_RAM:field_read - TEXT1_TO_RAM + 8] != bytes.fromhex("280300004082000c")
                or data[field_open - TEXT1_TO_RAM:field_open - TEXT1_TO_RAM + 12] != bytes.fromhex("7c7b1b787c9c23787cbd2b78")):
            raise FormatError("unexpected native XD Shadow Lugia display window")
    group, resource = struct.unpack_from(">II", original, _XD_MODEL_TABLE[game_id] + DARK_MODEL * 8)
    source = read_archive(ARCHIVE)
    members = parse_fsys(source)["members"]
    selected = [m for m in members if int(m["identifier_raw"], 16) == resource]
    if (group != 2263 or resource != 0x19661E00 or len(selected) != 1
            or ARCHIVE in updates):
        raise FormatError("unexpected original XD Shadow Lugia resource")
    native = decoded_member(source, selected[0])
    variant = make_shadow_lugia_shiny(native, xd=True)
    output_archive = append_actor_models(source, {}, source, resource,
        {RESOURCE: ("darklugia_shiny", variant)}, resource_type=0x1E00)
    if "poke_face.fsys" in updates:
        raise FormatError("overlapping XD Shadow Lugia face edits")
    face, face_report = append_shadow_lugia_shiny_face(read_archive("poke_face.fsys"))
    if (face_report["group"], face_report["source_resource"], face_report["shiny_resource"]) != FACE_ALIAS:
        raise FormatError("unexpected XD Shadow Lugia face alias")
    status = shadow_statuses(seed, options).get(str(SHADOW_ID), False)
    field_source = updates[FIELD_ARCHIVE] if FIELD_ARCHIVE in updates else read_archive(FIELD_ARCHIVE)
    field_members = parse_fsys(field_source)["members"]
    from .xd_field_actors import GATEON_LUGIA_SHINY_RESOURCE, GATEON_SHADOW, _ZANGOOSE_RESOURCE
    choices = [(source, target, SHADOW_ID, status) for source, target in FIELD_RESOURCES]
    gateon = [m for m in field_members if int(m["identifier_raw"], 16) == GATEON_LUGIA_SHINY_RESOURCE]
    if gateon:
        if len(gateon) != 1 or gateon[0]["name"] != "orre_gateon_lugia_shiny":
            raise FormatError("unexpected Gateon Shadow Lugia field alias")
        choices.append((int(_ZANGOOSE_RESOURCE, 16), GATEON_LUGIA_SHINY_RESOURCE,
                        GATEON_SHADOW, shadow_statuses(seed, options).get(str(GATEON_SHADOW), False)))
    field_models, field_report = {}, []
    for source_id, target_id in FIELD_RESOURCES:
        selected_field = [m for m in field_members if int(m["identifier_raw"], 16) == source_id]
        if len(selected_field) != 1:
            raise FormatError("missing native XD Shadow Lugia field model")
        dat = decoded_member(field_source, selected_field[0])
        if hashlib.sha256(dat).hexdigest() != _FIELD_SHA256[source_id]:
            raise FormatError("unexpected native XD Shadow Lugia field DAT")
        rare_dat = make_shadow_lugia_shiny_dat(dat)
        field_models[target_id] = (f"orre_{selected_field[0]['name']}_shiny", rare_dat)
        field_report.append({"source_resource": source_id, "shiny_resource": target_id,
                             "source_sha256": hashlib.sha256(dat).hexdigest(),
                             "variant_sha256": hashlib.sha256(rare_dat).hexdigest()})
    field_archive = append_actor_models(field_source, {}, field_source, FIELD_RESOURCES[0][0], field_models)
    output, hooks = append_xd_dol_text(original, current, game_id, (
        (hook, 0x7FE3FB78, _model_stub),
        (field_read, 0x28030000, lambda address, continuation: _field_actor_stub(
            address, continuation, layout, identity, rare_check, startup=False, routes=choices)),
        (field_open, 0x7C7B1B78, lambda address, continuation: _field_actor_stub(
            address, continuation, layout, identity, rare_check, startup=True, routes=choices)),
    ))
    keep = bool(getattr(options, "keep_shadow_lugia_after_purification", False))
    retained_hooks = []
    if keep:
        output, retained_hooks = _install_retained_displays(original, output, game_id)
        output, ceremony_hooks = _install_retained_ceremony(original, output, game_id)
        retained_hooks += ceremony_hooks
    output, face_hooks = install_xd_shadow_lugia_face(original, output, game_id, fallback=status)
    face_report["routing"] = face_hooks
    updates[ARCHIVE] = output_archive
    updates["poke_face.fsys"] = face
    updates[FIELD_ARCHIVE] = field_archive
    return output, {"version": VERSION, "archive": ARCHIVE, "group": group,
        "native_resource": resource, "shiny_resource": RESOURCE, "shadow_id": SHADOW_ID,
        "model_id": DARK_MODEL, "material_variant_sha256": hashlib.sha256(variant).hexdigest(),
        "saved_identity": True, "ungenerated_seeded_fallback": status, "hooks": hooks,
        "all_shadow_lugia": True, "keep_after_purification": keep,
        "retained_display_hooks": retained_hooks,
        "shadow_field_routes": [{"source_resource": source, "shiny_resource": target,
                                 "shadow_id": shadow, "ungenerated_seeded_fallback": default}
                                for source, target, shadow, default in choices],
        "face": face_report, "field_models": field_report}
