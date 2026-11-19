"""Select authored rare weather PKXs using the native specimen's shiny flag.

The normal resource, species/model IDs, animation sequence and saved Pokemon
records are unchanged. Each caller appends three color-only PKXs to the native
weather archives before installing these guarded resource-selection hooks.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import struct

from .castform_layouts import LAYOUTS
from .castform_portraits import _reservation
from .engine.analyze_game import FormatError, parse_dol, u32
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code

VERSION = "castform-native-shiny-weather-v1"
# Native loaded model IDs remain visible to the live HUD portrait patch.
WEATHER_MODELS = (414, 415, 416)  # rain, sun, hail
SHINY_RESOURCES = {414: 0x7DA11E00, 415: 0x7DA21E00, 416: 0x7DA31E00}
_HOOKS = {
    # Colosseum: model-loader native rare lookup exit (loader + 0x14c).
    "GC6P01": (0x801E2B50, "7ff7fb787fe3fb784bf9cae92c030000"),
    "GC6E01": (0x801DE2DC, "7ff7fb787fe3fb784bf9cfe92c030000"),
    "GC6J01": (0x801D9C50, "7ff7fb787fe3fb784bf9def92c030000"),
    # XD: the rare-table result check, before its native register assignment.
    # Existing Shadow Lugia hooks are 0x1c bytes later and remain untouched.
    "GXXP01": (0x801DABC0, "28060000418200182807000041820010"),
    "GXXE01": (0x801D9070, "28060000418200182807000041820010"),
    "GXXJ01": (0x801D3F10, "28060000418200182807000041820010"),
}


def _resources(resources: Mapping[int, int], original: bytes) -> dict[int, int]:
    if (not isinstance(resources, Mapping) or set(resources) != set(WEATHER_MODELS)
            or any(type(value) is not int or not 0 < value <= 0xFFFFFFFF
                   or value & 0xFFFF != 0x1E00 for value in resources.values())
            or len(set(resources.values())) != 3):
        raise FormatError("three distinct Castform weather PKX resources are required")
    if any(struct.pack(">I", value) in original for value in resources.values()):
        raise FormatError("Castform shiny resource collides with a native executable identity")
    return dict(resources)


def _load(code: _Code, register: int, value: int):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | value & 0xFFFF)


def _model_selector(address: int, continuation: int, resources: Mapping[int, int], *, xd: bool) -> bytes:
    code = _Code(address)
    model, rare = (27, 29) if xd else (26, 28)
    # The native decision is byte-sized; preserve unrelated high argument bits.
    code.emit(0x5400063E | rare << 21, 0x28000000)  # clrlwi r0,rare,24; cmplwi r0,0
    code.conditional(0x41820000, "native")
    code.emit(0x5400043E | model << 21)  # clrlwi r0,model,16
    for index in WEATHER_MODELS:
        code.emit(0x28000000 | index)
        code.conditional(0x41820000, f"model{index}")
    code.jump("native")
    for index in WEATHER_MODELS:
        code.label(f"model{index}")
        if xd:
            code.emit(0x7FE6FB78)  # mr r6,r31: keep this form's native archive group.
            _load(code, 7, resources[index])
            # Native cmplwi checks below set r4 and r30=1: real rare resource,
            # no generic tint. r27 and the specimen's rare decision stay native.
        else:
            _load(code, 30, resources[index])
            code.emit(0x3BA00001)  # li r29,1: an actual rare PKX, skip retail tint.
        code.jump("native")
    code.label("native")
    code.emit(0x28060000 if xd else 0x7FF7FB78)  # displaced cmplwi / mr r23,r31
    code.emit(branch(address + len(code.words) * 4, continuation))
    return code.finish()


def install_castform_shiny_models(original: bytes, current: bytes, game_id: str,
                                  resources: Mapping[int, int] = SHINY_RESOURCES):
    """Install color-only resource selection against one exact retail executable.

    This does not append PKX resources itself. The caller owns archive edits and
    must supply those same three resource IDs, keyed by native loaded model ID.
    """
    layout = LAYOUTS.get(game_id)
    if not layout or hashlib.sha256(original).hexdigest() != layout["sha256"]:
        raise FormatError("unknown original Castform shiny-model executable")
    resources = _resources(resources, original)
    xd = game_id.startswith("GXX")
    text_base = 0x800030A0 if xd else 0x80003000
    hook, signature = _HOOKS[game_id]
    pos = hook - text_base
    expected = bytes.fromhex(signature)
    if any(data[pos:pos + len(expected)] != expected for data in (original, current)):
        raise FormatError("unexpected Castform shiny-model instruction window")
    offset, ram, setter, store, code = _reservation(original, current, game_id)
    stub = ram + len(code)
    payload = _model_selector(stub, hook + 4, resources, xd=xd)
    code.extend(payload)
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Castform shiny-model code exceeds reserved memory")
    code[:32] = _arena_guard(end, store)
    output = bytearray(current[:offset])
    struct.pack_into(">I", output, pos, branch(hook, stub))
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    for at, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                      (setter - text_base, branch(setter, ram))):
        struct.pack_into(">I", output, at, value)
    allowed = ((8, 12), (0x50, 0x54), (0x98, 0x9C),
               (setter - text_base, setter - text_base + 4), (pos, pos + 4), (offset, offset + 32))
    if any(before != after and not any(lo <= at < hi for lo, hi in allowed)
           for at, (before, after) in enumerate(zip(current, output))):
        raise FormatError("Castform shiny-model patch changed unrelated executable bytes")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if (section["offset"], section["ram_address"], section["size"]) != (offset, ram, len(code)):
        raise FormatError("Castform shiny-model section failed readback")
    return bytes(output), {
        "version": VERSION, "game_id": game_id, "hook": hook, "stub": stub,
        "code_bytes": len(payload), "resources": {str(k): v for k, v in resources.items()},
        "shiny_source": "native per-specimen rare flag", "resource_selection_only": True,
        "native_model_ids_preserved": True, "generic_rare_tint_skipped": True,
        "normal_resources_unchanged": True, "save_data_unchanged": True,
        "unrelated_executable_bytes_preserved": True,
    }
