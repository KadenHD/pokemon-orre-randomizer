"""XD's original dark model for Colosseum's actual Shadow Lugia specimens.

The Pokémon keeps its native species, Shadow ID and saved personality. Only
display requests select additional resources. A cosmetic option may retain
the dark model after purification; a never-Shadow Lugia always stays ordinary.
"""
from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

from .actor_archive import append_actor_models
from .analyze_game import FormatError, parse_dol, parse_fsys, u32
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .rebuild_iso import align
from .shiny_rules import _Code

VERSION = "xd-shadow-lugia-colosseum-model-v3"
ASSET = "models/dark-lugia-colosseum-v1.pkx"
RESOURCE_ID = 0x7DF31E00
SHINY_RESOURCE_ID = 0x7DF41E00
MODEL_MARKER = 0x7FF0
NATIVE_LUGIA_MARKER = 0x7FEF
ARCHIVE = "pkx_lugia.fsys"
_LAYOUTS = {
    # Native loader, Pokémon menu call, battle call, model table file offset.
    "GC6P01": (0x801E2A04, 0x80125EC4, 0x8020C814, 0x3BACC8),
    "GC6E01": (0x801DE190, 0x80121D50, 0x80207EC4, 0x36DBD0),
    "GC6J01": (0x801D9B04, 0x8011F4FC, 0x80203784, 0x35A338),
}
_MENU_GETTERS = {
    "GC6P01": (0x8010D308, 0x8010D500, 0x8012A580),
    "GC6E01": (0x80109CF0, 0x80109EE8, 0x8012640C),
    "GC6J01": (0x801076CC, 0x801078C4, 0x80123BAC),
}
_CEREMONY_GETTERS = {
    # Model-ID request inside the purification display's loadSequence. Its
    # r31 still holds the full CK3; the model is cached before purification.
    "GC6P01": 0x80262C28,
    "GC6E01": 0x8025E100,
    "GC6J01": 0x80259898,
}
_SAVED_IDENTITIES = {
    # Native saved PID, generated flag and purified flag readers for a Shadow ID.
    "GC6P01": (0x801F2FC4, 0x801F3168, 0x801F34E8),
    "GC6E01": (0x801EE750, 0x801EE8F4, 0x801EEC74),
    "GC6J01": (0x801EA010, 0x801EA1B4, 0x801EA534),
}
_LOADER_PREFIX = bytes.fromhex(
    "9421ffd0 7c0802a6 90010034 bee1000c 7c7a1b78 5463043f 7c9b2378 7cbc2b78 3ba00000")


def convert_xd_model(source: bytes, colosseum_template: bytes) -> bytes:
    """Adapt PKX scheduling units; retain XD's mesh, textures and DAT animations."""
    if (len(source) < 0xE60 or u32(source, 0x20) != 0xFFFFFFFF
            or u32(source, 8) != 0 or u32(source, 0x10) != 17
            or u32(colosseum_template, 8) != 17 or u32(colosseum_template, 0x10) != 5
            or u32(colosseum_template, 4) != 0):
        raise FormatError("unexpected original Lugia PKX containers")
    size = u32(source, 0)
    dat = source[0xE60:0xE60 + align(size)]
    metadata = bytearray(source[0x84:0x84 + 17 * 0xD0])
    native_metadata = 0x40 + align(u32(colosseum_template, 0))
    if len(dat) != align(size) or u32(dat, 0) != size or len(metadata) != 17 * 0xD0:
        raise FormatError("truncated XD Shadow Lugia model")
    if len(colosseum_template) < native_metadata + len(metadata):
        raise FormatError("truncated Colosseum Lugia metadata")
    for index in range(17):
        row = index * 0xD0
        count, tracks = struct.unpack_from(">II", metadata, row)
        if not 1 <= count <= 16 or not 1 <= tracks <= 8:
            raise FormatError("unsupported XD Lugia animation schedule")
        # XD stores seconds as floats; Colosseum's loader expects integer
        # ticks at 60 Hz. Copying the float bits causes billion-frame waits.
        for field in range(count):
            pos = row + 0x0C + field * 4
            seconds, = struct.unpack_from(">f", metadata, pos)
            if not math.isfinite(seconds) or not 0 <= seconds <= 3600:
                raise FormatError("invalid XD Lugia animation duration")
            struct.pack_into(">I", metadata, pos, round(seconds * 60))
        # XD 1/2 select one-shot/looping animation tracks; Colosseum uses 0
        # for DAT clip indices and nonzero for a wait/idle continuation.
        for track in range(tracks):
            pos = row + 0x8C + track * 8
            kind = u32(metadata, pos)
            if kind not in (0, 1, 2):
                raise FormatError("unsupported XD Lugia animation track kind")
            struct.pack_into(">I", metadata, pos, 1 if kind == 0 else 0)
        struct.pack_into(">I", metadata, row + 8, u32(colosseum_template, native_metadata + row + 8))
    header = bytearray(colosseum_template[:0x40])
    struct.pack_into(">I", header, 0, size)
    # Keep the original dark asset here. A separately generated white variant
    # is selected from the saved shiny identity by the runtime hooks.
    result = bytes(header) + dat + bytes(metadata)
    return result + bytes(-len(result) % 32)


def _identity_selector(address, loader, *, return_marker=False, keep_after_purification=False,
                       force_ordinary=False):
    code = _Code(address)
    code.emit(0x7FEBFB78)  # the menu caller's original CK3 in r31
    code.emit(0x280B0000)
    code.conditional(0x41820000, "native")
    code.emit(0xA00B0000, 0x280000F9)
    code.conditional(0x40820000, "native")
    if force_ordinary:
        # The purification renderer creates its model before the native
        # ceremony sets the purified flag. Select the final visual appearance
        # in that display only; never change the Pokemon or ceremony timing.
        code.jump("ordinary")
    else:
        code.emit(0xA00B00D8, 0x28000000)
        code.conditional(0x41820000, "ordinary")
        code.emit(0x28000061)
        code.conditional(0x40800000, "ordinary")
        if not keep_after_purification:
            code.emit(0x800B00DC, 0x2C00FF9C)
            code.conditional(0x41820000, "ordinary")
    code.emit(0x38600000 | MODEL_MARKER)
    code.jump("selected")
    code.label("ordinary")
    # A definite ordinary specimen must not enter the reduced-record PID
    # fallback, even if a copied ordinary Lugia has a Shadow Lugia's PID.
    code.emit(0x38600000 | NATIVE_LUGIA_MARKER)
    code.label("selected")
    if return_marker:
        code.emit(0x4E800020)
    code.label("native")
    code.emit(branch(address + len(code.words) * 4, loader))
    return code.finish()


def _battle_identity_selector(address, loader, getter, *, keep_after_purification=False):
    """Read the original battle Pokémon; its stack BIOS copy omits Shadow fields."""
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,
              0x90610008, 0x9081000C, 0x90A10010, 0x280300F9)
    code.conditional(0x40820000, "restore")  # preserve Substitute/other model overrides
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
    code.emit(0xA0030000, 0x280000F9)
    code.conditional(0x40820000, "restore")
    code.emit(0xA00300D8, 0x28000000)
    code.conditional(0x41820000, "ordinary")
    code.emit(0x28000061)
    code.conditional(0x40800000, "ordinary")
    if not keep_after_purification:
        code.emit(0x800300DC, 0x2C00FF9C)
        code.conditional(0x41820000, "ordinary")
    code.emit(0x38000000 | MODEL_MARKER, 0x90010008)
    code.jump("restore")
    code.label("ordinary")
    code.emit(0x38000000 | NATIVE_LUGIA_MARKER, 0x90010008)
    code.label("restore")
    code.emit(0x80610008, 0x8081000C, 0x80A10010,
              0x80010024, 0x7C0803A6, 0x38210020)
    code.emit(branch(address + 4 * len(code.words), loader))
    return code.finish()


def _resource_selector(address, loader, native_word, group, saved_identity=None, *,
                       keep_after_purification=False, shadow_ids=(96,)):
    code = _Code(address)
    code.emit(0x28030000 | MODEL_MARKER)
    code.conditional(0x41820000, "variant")
    code.emit(0x28030000 | NATIVE_LUGIA_MARKER)
    code.conditional(0x41820000, "ordinary")
    if saved_identity is not None:
        saved_pid, generated, purified = saved_identity
        # The native loader has already preserved its LR and nonvolatile
        # registers. Target/capture views can omit the Shadow fields from
        # their transient BIOS, but retain this specimen's original PID. The
        # candidates are the final ROM's Lugia Shadow slots, never other species.
        code.emit(0x281A00F9)
        code.conditional(0x40820000, "native")
        for index, shadow_id in enumerate(shadow_ids):
            next_candidate = f"candidate_{index + 1}"
            code.emit(0x38600000 | shadow_id)
            code.call(generated)
            code.emit(0x5460063E, 0x28000001)
            code.conditional(0x40820000, next_candidate)
            if not keep_after_purification:
                code.emit(0x38600000 | shadow_id)
                code.call(purified)
                code.emit(0x5460063E, 0x28000000)
                code.conditional(0x40820000, next_candidate)
            code.emit(0x38600000 | shadow_id)
            code.call(saved_pid)
            code.emit(0x7C03D840)  # cmplw r3, r27: the requested native PID
            code.conditional(0x40820000, next_candidate)
            code.jump("variant")
            code.label(next_candidate)
        code.label("restore_native")
        code.emit(0x7F43D378)
    code.jump("native")
    code.label("variant")
    code.emit(0x3BE00000 | group,
              0x3FC00000 | (RESOURCE_ID >> 16), 0x63DE0000 | (RESOURCE_ID & 0xFFFF),
              0x281C0000)
    code.conditional(0x41820000, "resource_ready")
    code.emit(0x3FC00000 | (SHINY_RESOURCE_ID >> 16), 0x63DE0000 | (SHINY_RESOURCE_ID & 0xFFFF))
    code.label("resource_ready")
    code.emit(0x3B4000F9, 0x3BA00001)  # normal model ID; dedicated dark palette
    code.emit(branch(address + len(code.words) * 4, loader + 0x14C))
    code.label("ordinary")
    code.emit(0x386000F9, 0x3B4000F9)
    code.label("native")
    code.emit(native_word)
    code.emit(branch(address + len(code.words) * 4, loader + 0x2C))
    return code.finish()


def _install_hooks(original, current, group, *, keep_after_purification=False, shadow_ids=(96,)):
    region = dol_layout(original)
    loader, menu, battle, _ = _LAYOUTS[region.game_id]
    request_first, request_second, getter = _MENU_GETTERS[region.game_id]
    ceremony_getter = _CEREMONY_GETTERS[region.game_id]
    saved_identity = _SAVED_IDENTITIES[region.game_id]
    for index, reader in enumerate(saved_identity):
        prefix = bytes.fromhex("9421fff07c0802a65463043f90010014")
        for data in (original, current):
            if data[reader-TEXT_TO_RAM:reader-TEXT_TO_RAM+len(prefix)] != prefix:
                raise FormatError("unexpected native Shadow Lugia identity reader")
            if index and u32(data, reader-TEXT_TO_RAM+0x34) != 0xA0640000 | (0x16 if index == 1 else 0x14):
                raise FormatError("unexpected native Shadow Lugia progress flag")
    start = loader - TEXT_TO_RAM
    for data in (original, current):
        if (data[start:start + len(_LOADER_PREFIX)] != _LOADER_PREFIX
                or u32(data, start + 0x28) != (0x800D84A0 if region.game_id == "GC6J01" else 0x800D84B0)
                or u32(data, start + 0x2C) != 0x7C030040
                or u32(data, start + 0x14C) != 0x7FF7FB78):
            raise FormatError("unexpected native Colosseum model loader")
        for call, prefix, suffix in (
                (menu, bytes.fromhex("7fc4f3785783043e"), bytes.fromhex("7c601b7838600008")),
                (battle, bytes.fromhex("7c651b7857e3043e"), bytes.fromhex("7c601b7838610010"))):
            pos = call - TEXT_TO_RAM
            if (data[pos-8:pos] != prefix or u32(data, pos) != branch(call, loader, link=True)
                    or data[pos+4:pos+12] != suffix):
                raise FormatError("unexpected Colosseum model identity call")
        for call, store in ((request_first, 0xB0810014), (request_second, 0xB09E0010)):
            expected = (0x38600000, store, 0x38A00066, 0x38C00000,
                        branch(call, getter, link=True), 0x5460043E, 0x7FE3FB78)
            if struct.unpack_from(">7I", data, call - TEXT_TO_RAM - 16) != expected:
                raise FormatError("unexpected native menu model request")
        if (struct.unpack_from(">5I", data, ceremony_getter - TEXT_TO_RAM - 12) != (
                0x38600000, 0x38A00066, 0x38C00000,
                branch(ceremony_getter, getter, link=True), 0x547E043F)
                or struct.unpack_from(">8I", data, ceremony_getter - TEXT_TO_RAM - 0x50) != (
                    0x9421FFE0, 0x7C0802A6, 0x90010024, 0xBF61000C,
                    0x7C9F2378, 0x7C7B1B78, 0x7CBC2B78, 0x7CDD3378)):
            raise FormatError("unexpected native purification model request")
    offset = align(len(original))
    size = u32(current, 0x98)
    arena = region.set_arena_lo - TEXT_TO_RAM
    if size:
        if ((u32(current, 8), u32(current, 0x50)) != (offset, region.section_ram)
                or size % 32 or offset + size != len(current)
                or current[offset:offset+32] != _arena_guard(region.section_ram + size, region.arena_lo_store)
                or u32(current, arena) != branch(region.set_arena_lo, region.section_ram)):
            raise FormatError("invalid model hook arena")
        payload = bytearray(current[offset:])
    else:
        if (len(current) != len(original) or u32(current, 8) or u32(current, 0x50)
                or u32(current, arena) != region.arena_lo_store):
            raise FormatError("invalid original model hook arena")
        payload = bytearray(32)
    from .postgame_lugia_face import native_face_hooks
    builders = (
            (menu, lambda a: _identity_selector(a, loader, keep_after_purification=keep_after_purification), True),
            (battle, lambda a: _battle_identity_selector(a, loader, getter, keep_after_purification=keep_after_purification), True),
            (request_first, lambda a: _identity_selector(a, getter, return_marker=True, keep_after_purification=keep_after_purification), True),
            (request_second, lambda a: _identity_selector(a, getter, return_marker=True, keep_after_purification=keep_after_purification), True),
            (ceremony_getter, lambda a: _identity_selector(a, getter, return_marker=True,
                keep_after_purification=keep_after_purification,
                force_ordinary=not keep_after_purification), True),
            (loader + 0x28, lambda a: _resource_selector(a, loader, u32(original, start + 0x28), group, saved_identity,
                                                       keep_after_purification=keep_after_purification, shadow_ids=shadow_ids), False))
    hooks = []
    for call, build, link in (*builders, *native_face_hooks(original, current, region.game_id,
                                                         keep_after_purification=keep_after_purification)):
        address = region.section_ram + len(payload)
        body = build(address)
        payload.extend(body)
        hooks.append({"address": call, "target": address, "bytes": len(body), "link": link})
    payload.extend(bytes(-len(payload) % 32))
    end = region.section_ram + len(payload)
    descriptor = parse_dol(original)
    if descriptor["bss_ram_address"] + descriptor["bss_size"] >= region.section_ram or end >= 0x81700000:
        raise FormatError("model hooks exceed the native arena")
    payload[:32] = _arena_guard(end, region.arena_lo_store)
    output = bytearray(current[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(payload)
    for pos, value in ((8, offset), (0x50, region.section_ram), (0x98, len(payload)),
                       (arena, branch(region.set_arena_lo, region.section_ram))):
        struct.pack_into(">I", output, pos, value)
    for hook in hooks:
        struct.pack_into(">I", output, hook["address"] - TEXT_TO_RAM,
                         branch(hook["address"], hook["target"], link=hook["link"]))
    return bytes(output), hooks


def verified_model_asset():
    """Load the audited port shared by battle and room-local field resources."""
    pack = Path(__file__).resolve().parents[1] / "assets/game"
    model = (pack / ASSET).read_bytes()
    from json import loads
    manifest = loads((pack / "models/manifest.json").read_text("utf-8"))
    if (len(model), hashlib.sha256(model).hexdigest()) != (manifest["converted_bytes"], manifest["converted_sha256"]):
        raise FormatError("the verified Shadow Lugia model asset is missing or modified")
    return model, manifest


def install_postgame_lugia_model(original, current, read_archive, updates, *,
                                keep_after_purification=False, shadow_ids=(96,)):
    """Install dedicated models and faces without changing ordinary Lugia."""
    shadow_ids = tuple(shadow_ids)
    if (not isinstance(keep_after_purification, bool)
            or any(type(sid) is not int or not 1 <= sid <= 96 for sid in shadow_ids)):
        raise FormatError("invalid Shadow Lugia display policy")
    shadow_ids = tuple(sorted(set(shadow_ids)))
    model, manifest = verified_model_asset()
    region = dol_layout(original)
    _, _, _, table = _LAYOUTS[region.game_id]
    group, member_id = struct.unpack_from(">II", original, table + 249 * 12)
    source = read_archive(ARCHIVE)
    if not 0 < group < 0x8000 or not any(int(m["identifier_raw"], 16) == member_id
                                       for m in parse_fsys(source)["members"]):
        raise FormatError("unexpected native Lugia resource")
    if ARCHIVE in updates:
        raise FormatError("the bonus model would overwrite another Lugia archive patch")
    from .shadow_lugia_palette import make_shadow_lugia_shiny
    shiny_model = make_shadow_lugia_shiny(model, xd=False)
    updates[ARCHIVE] = append_actor_models(source, {}, source, member_id,
        {RESOURCE_ID: ("darklugia_bonus", model),
         SHINY_RESOURCE_ID: ("rare_darklugia_bonus", shiny_model)}, resource_type=0x1E00)
    from .shadow_lugia_face import ARCHIVE as FACE_ARCHIVE, append_colosseum_shadow_lugia_face
    face_source = updates.get(FACE_ARCHIVE)
    if face_source is None:
        face_source = read_archive(FACE_ARCHIVE)
    updates[FACE_ARCHIVE], face_report = append_colosseum_shadow_lugia_face(face_source)
    output, hooks = _install_hooks(original, current, group,
                                   keep_after_purification=keep_after_purification, shadow_ids=shadow_ids)
    return output, {"version": VERSION, "archive": ARCHIVE, "resource": RESOURCE_ID,
                    "shiny_resource": SHINY_RESOURCE_ID,
                    "shiny_model_sha256": hashlib.sha256(shiny_model).hexdigest(),
                    "source_game": "Pokémon XD", "model_sha256": manifest["converted_sha256"],
                    "purified_model": "shadow-lugia" if keep_after_purification else "native-lugia",
                    "shadow_ids": list(shadow_ids), "face": face_report, "hooks": hooks}
