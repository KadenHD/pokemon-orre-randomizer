"""Paint live XD Spinda field actors from their encounter's exact PID."""

from dataclasses import dataclass
import struct

from .engine.actor_palette import pkx_recipe
from .engine.analyze_game import FormatError, parse_fsys, u32
from .engine.rebuild_iso import decoded_member
from .engine.shiny_rules import _Code
from .engine.spinda import SPINDA
from .engine.spinda_runtime import spinda_face_writer
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_field_actors import GATEON_SHADOW, _ZANGOOSE_RESOURCE
from .xd_spinda import _load_address, _tail_call, emit_spinda_pid_fit


@dataclass(frozen=True)
class _Layout:
    people_epilogue: int
    open_epilogue: int
    spot_species: int
    spot_pid: int
    get_part: int
    get_material: int
    free_part: int
    store_cache: int
    invalidate_texture: int
    player_lookup: int
    shadow_seen: int
    shadow_pid: int


_LAYOUTS = {
    "GXXP01": _Layout(0x802A0700, 0x802A1000, 0x80296C88, 0x80296C58, 0x800FDF78,
                       0x80101CE0, 0x80101E44, 0x800AC1E8, 0x800CD290,
                       0x801D0A8C, 0x8014DA9C, 0x8014D990),
    "GXXE01": _Layout(0x8029E7AC, 0x8029F0AC, 0x80294D4C, 0x80294D1C, 0x800FC918,
                       0x80100680, 0x801007E4, 0x800AACA0, 0x800CBC74,
                       0x801CEFB4, 0x8014C1D8, 0x8014C0CC),
    "GXXJ01": _Layout(0x8029908C, 0x8029998C, 0x8028F774, 0x8028F744, 0x800F8CA4,
                       0x800FCA04, 0x800FCB68, 0x800A7134, 0x800C8198,
                       0x801C9E54, 0x80147520, 0x80147414),
}
_EPILOGUE = (0xBB210024, 0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
_OPEN_EPILOGUE = (0xBB61000C, 0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
_SPOT_INDEX = {"rock": 0, "oasis": 1, "cave": 2}
_GATEON_ACTOR = 0xFFFF  # distinct from the three live Poké Spot indices


def _select_pixel_buffer(code):
    # GSpartGetMaterial returns a wrapper for the original MObj. Its first
    # TObj's HSD_ImageDesc at +0x58 points into the actor's own loaded DAT.
    for offset in (8, 8, 0x58):
        code.emit(0x28030000)
        code.conditional(0x41820000, "free_part")
        code.emit(0x80630000 | offset)
    code.emit(0x28030000)
    code.conditional(0x41820000, "free_part")
    code.emit(0x80030004, 0x3D800080, 0x618C0080, 0x7C006040)  # 128 × 128
    code.conditional(0x40820000, "free_part")
    code.emit(0x80030008, 0x28000004)  # GX_TF_RGB565
    code.conditional(0x40820000, "free_part")
    code.emit(0x80030000, 0x90010014)


def _load_gateon_pid(code, layout, candidate, shiny):
    code.emit(0x38600000 | GATEON_SHADOW)
    code.call(layout.shadow_seen)
    code.emit(0x28030000)
    code.conditional(0x41820000, "first_gateon_encounter")
    code.emit(0x38600000 | GATEON_SHADOW)
    code.call(layout.shadow_pid)
    code.jump("pid_ready")
    code.label("first_gateon_encounter")
    code.emit(0x38600000, 0x38800002)
    code.call(layout.player_lookup)
    code.emit(0x28030000)
    code.conditional(0x41820000, "restore")
    code.emit(0x80E3002C, 0x38C00000 | int(shiny))  # exact owner and mode used for the first fight
    _load_address(code, 3, candidate)
    emit_spinda_pid_fit(code)


def _field_hook(address, continuation, layout, resources, face, spot, recipe, *, startup=False, gateon=None):
    writer = address + 0x300
    code = _Code(address)
    code.emit(0x28030001)  # native model load returned success
    code.conditional(0x40820000, "native")
    for index, (resource, _spot_index, _shiny) in enumerate(resources):
        _load_address(code, 12, resource)
        code.emit(0x7C1E6040 if startup else 0x7C1B6040)  # model resource in r30 or r27
        code.conditional(0x41820000, f"resource_{index}")
    code.jump("native")
    for index, (_resource, spot_index, shiny) in enumerate(resources):
        code.label(f"resource_{index}")
        code.emit(0x39600000 | spot_index, 0x39800000 | int(shiny))
        code.jump("paint")
    code.label("paint")
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x91610008, 0x9181000C)
    if gateon is not None:
        code.emit(0x2C0BFFFF)  # the Gateon alias is only installed for a Spinda
        code.conditional(0x41820000, "actor")
    code.emit(0x7D635B78)  # mr r3,r11: zero-based Poké Spot index
    code.call(layout.spot_species)
    code.emit(0x28030000 | SPINDA)
    code.conditional(0x40820000, "restore")
    code.label("actor")
    code.emit(0x807B0008 if startup else 0x807D0008, 0x28030000)  # actor in r27 or r29
    code.conditional(0x41820000, "restore")
    code.emit(0x38800002)  # native Spinda face is on the third model part
    code.call(layout.get_part)
    code.emit(0x28030000)
    code.conditional(0x41820000, "restore")
    code.emit(0x90610010, 0x38000000, 0x90010014, 0x38800000)
    code.call(layout.get_material)
    _select_pixel_buffer(code)
    code.label("free_part")
    code.emit(0x80610010)
    code.call(layout.free_part)
    code.emit(0x80010014, 0x28000000)
    code.conditional(0x41820000, "restore")
    code.emit(0x80610008)
    if gateon is not None:
        code.emit(0x2C03FFFF)
        code.conditional(0x41820000, "gateon_pid")
    code.call(layout.spot_pid)
    if gateon is not None:
        code.jump("pid_ready")
        code.label("gateon_pid")
        _load_gateon_pid(code, layout, *gateon)
        code.label("pid_ready")
    code.emit(0x7C641B78, 0x80610014, 0x80A1000C)
    code.call(writer)
    code.emit(0x80610014, 0x38807FFF, 0x38840001)  # DCStoreRange(pixels, 0x8000)
    code.call(layout.store_cache)
    code.call(layout.invalidate_texture)
    code.label("restore")
    code.emit(0x38600001, 0x80010024, 0x7C0803A6, 0x38210020)
    code.label("native")
    code.emit(_OPEN_EPILOGUE[0] if startup else _EPILOGUE[0])
    _tail_call(code, continuation)
    body = code.finish()
    if len(body) > writer - address:
        raise FormatError("XD Spinda field hook overlaps its face writer")
    payload = body + bytes(writer - address - len(body)) + spinda_face_writer(writer, face, spot, recipe)
    return payload + bytes(-len(payload) % 32)


def apply_spinda_poke_spots(original, current, game_id, rows, read_archive, *, gateon_pid=None, gateon_shiny=False):
    """Install the Poké Spot bridge and, if selected, the Gateon Shadow actor."""
    resources = [
        (row[key], _SPOT_INDEX[row["spot"]], shiny)
        for row in rows if row["species"] == SPINDA
        for key, shiny in (("model_resource", False), ("shiny_model_resource", True))
    ]
    gateon = None
    if gateon_pid is not None:
        if type(gateon_pid) is not int or not 0 <= gateon_pid <= 0xFFFFFFFF or type(gateon_shiny) is not bool:
            raise ValueError("invalid XD Gateon Spinda personality candidate")
        gateon = gateon_pid, gateon_shiny
        resources.append((int(_ZANGOOSE_RESOURCE, 16), _GATEON_ACTOR, gateon_shiny))
    if not resources:
        return current, []
    if len({resource for resource, _, _ in resources}) != len(resources) or len(resources) > 7:
        raise FormatError("unexpected XD Spinda field resources")
    layout = _LAYOUTS[game_id]
    signatures = {
        layout.people_epilogue: _EPILOGUE,
        layout.open_epilogue: _OPEN_EPILOGUE,
        layout.spot_species + 0x18: (0x8063000C,),
        layout.spot_pid + 0x18: (0x80630010,),
        layout.get_part: (0x9421FFE0, 0x7C0802A6, 0x90010024, 0x93E1001C),
        layout.get_material: (0x80A30008, 0x80050014, 0x70004020, 0x7C000034),
        layout.free_part: (0x38000000, 0x98030000, 0x4E800020),
        layout.store_cache: (0x28040000, 0x4C810020, 0x546506FE),
        layout.invalidate_texture: (0x7C0802A6, 0x90010004, 0x9421FFF8),
    }
    if gateon is not None:
        signatures[layout.player_lookup] = (0x9421FFF0, 0x7C0802A6, 0x90010014, 0x5480043E)
        for address in (layout.shadow_seen, layout.shadow_pid):
            signatures[address] = (0x9421FFF0, 0x7C0802A6, 0x5463043E, 0x90010014)
    for address, words in signatures.items():
        offset = address - TEXT1_TO_RAM
        if tuple(u32(original, offset + i * 4) for i in range(len(words))) != words:
            raise FormatError(f"unexpected XD Spinda field instruction at {address:#x}")
    archive = read_archive("pkx_patcheel.fsys")
    members = {row["name"]: row for row in parse_fsys(archive)["members"]}
    face, spot, model = (decoded_member(archive, members[name]) for name in ("face", "buti_a", "patcheel"))
    recipe = pkx_recipe(model, xd=True)
    return append_xd_dol_text(original, current, game_id, (
        (layout.people_epilogue, _EPILOGUE[0], lambda address, continuation:
         _field_hook(address, continuation, layout, resources, face, spot, recipe, gateon=gateon)),
        (layout.open_epilogue, _OPEN_EPILOGUE[0], lambda address, continuation:
         _field_hook(address, continuation, layout, resources, face, spot, recipe, startup=True, gateon=gateon)),
    ))
