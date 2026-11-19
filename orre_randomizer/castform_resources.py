"""Append authored rare weather models/faces without replacing native members.

Artwork is supplied by explicit, uncached callbacks. The three ordinary PKXs
and faces, any already appended Lugia resources, and unrelated pending patches
remain intact. The caller qualifies color-only PKX changes and rendered faces.
"""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import struct

from .artwork import _texture
from .castform_layouts import LAYOUTS
from .castform_portraits import MODELS, RESOURCES
from .castform_shiny_models import SHINY_RESOURCES
from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, parse_fsys
from .engine.rebuild_iso import decoded_member
from .engine.shadow_lugia_face import make_colosseum_shadow_lugia_face

VERSION = "castform-appended-weather-resources-v2"
SHINY_FACE_RESOURCES = {414: 0x7DA11200, 415: 0x7DA21200, 416: 0x7DA31200}
_FORMS = {414: ("w", 446), 415: ("f", 443), 416: ("i", 445)}
_MODEL_IDS = {
    "colosseum": {414: 0x045E1E00, 415: 0x045B1E00, 416: 0x045D1E00},
    "xd": {414: 0x03DD1E00, 415: 0x03DA1E00, 416: 0x03DC1E00},
}
_FACE_IDS = {game: dict(zip(MODELS, resources, strict=True)) for game, resources in RESOURCES.items()}
_FACE_BYTES = 42 * 42 * 4


def _game(game_id: str) -> str:
    if game_id not in LAYOUTS:
        raise FormatError("unknown Castform weather-resource game identity")
    return "xd" if game_id.startswith("GXX") else "colosseum"


def _face_header(*, indexed: bool) -> bytes:
    # Exact 128-byte headers observed in the retail 42x84 Castform atlases.
    # XD's GStextureGetGXformat explicitly maps flag 0x45 to GX_TF_RGBA8 (6).
    # Its GStextureCreateFromMemory also assigns 32 bpp for that same flag.
    header = bytearray(128)
    struct.pack_into(">HHBBHI", header, 0, 42, 84, 8 if indexed else 32, 1, 0, 1 if indexed else 0x45)
    struct.pack_into(">I", header, 0x28, 128)
    if indexed:
        struct.pack_into(">I", header, 0xC, 3)
        struct.pack_into(">I", header, 0x48, 4160)
    return bytes(header)


def _native_face(source: bytes, game_id: str) -> bytes:
    game = _game(game_id)
    indexed = game == "xd"
    if (type(source) is not bytes or len(source) != (4672 if indexed else 14912)
            or source[:128] != _face_header(indexed=indexed)):
        raise FormatError("unexpected native Castform weather face header")
    pixels = _texture(source, (42, 84))
    normal = pixels[:_FACE_BYTES]
    # XD's pre-baked cells have a few small RGB differences despite sharing
    # the same weather palette. Preserve the original normal cell exactly;
    # only require their independently stored frame alpha to agree.
    if pixels[_FACE_BYTES + 3::4] != normal[3::4]:
        raise FormatError("native Castform weather cells no longer share their alpha frame")
    expected_alpha = (bytes(255 if (x + .5 - 21) ** 2 + (y + .5 - 21) ** 2 < 22.5 ** 2 else 0
                            for y in range(42) for x in range(42)) if indexed
                      else bytes([255]) * (42 * 42))
    if normal[3::4] != expected_alpha:
        raise FormatError("native Castform weather portrait frame changed")
    return normal


def _xd_direct_face(source: bytes, pixels: bytes) -> bytes:
    # XD's native face cache allocates/copies exactly 0x1f60 bytes per slot
    # (_menuFaceLoadCallBack / menuFaceInit). RGBA8 is supported by GX but its
    # 14912-byte atlas gets truncated there. Direct RGB5A3 needs only 7520 bytes.
    # Retain each original upper cell's palette word, including opaque A3RGB4
    # words, so switching from indexed to direct data does not alter its RGB.
    header = bytearray(128)
    struct.pack_into(">HHBBHI", header, 0, 42, 84, 16, 1, 0, 0x90)
    struct.pack_into(">I", header, 0x28, 128)
    output = bytearray(header)
    for by in range(0, 84, 4):
        for bx in range(0, 42, 4):
            for dy in range(4):
                for dx in range(4):
                    x, y = bx + dx, by + dy
                    if x >= 42:
                        word = 0
                    elif y < 42:
                        index = source[128 + (y // 4) * 192 + (x // 8) * 32 + (y % 4) * 8 + x % 8]
                        word = struct.unpack_from(">H", source, 4160 + index * 2)[0]
                    else:
                        r, g, b, alpha = pixels[(y * 42 + x) * 4:(y * 42 + x + 1) * 4]
                        if alpha == 255:
                            r, g, b = ((value * 31 + 127) // 255 for value in (r, g, b))
                            word = 0x8000 | r << 10 | g << 5 | b
                        else:
                            r, g, b = ((value * 15 + 127) // 255 for value in (r, g, b))
                            word = ((alpha * 7 + 127) // 255) << 12 | r << 8 | g << 4 | b
                    output.extend(struct.pack(">H", word))
    if len(output) != 7520 or len(output) > 0x1F60:
        raise FormatError("XD Castform face exceeds its native cache slot")
    # The callback always copies the complete fixed slot. Supply its padding
    # ourselves rather than relying on bytes beyond this appended resource.
    return bytes(output) + bytes(0x1F60 - len(output))


def make_weather_face_atlas(source: bytes, shiny_pixels: bytes, *, game_id: str) -> bytes:
    """Preserve the original normal cell and encode a cache-safe rare cell.

    Colosseum retains its exact RGBA8 atlas. XD uses direct RGB5A3 within its
    fixed native face-cache size, keeping original upper-cell colors exact and
    encoding the new portrait with native five-bit RGB and its circular alpha.
    Retail indexed faces and the authored HD artwork remain unchanged.
    """
    normal = _native_face(source, game_id)
    if type(shiny_pixels) is not bytes or len(shiny_pixels) != _FACE_BYTES:
        raise FormatError("Castform shiny portrait must be exactly one 42px RGBA cell")
    if shiny_pixels[3::4] != normal[3::4]:
        raise FormatError("Castform shiny portrait must retain the native alpha frame")
    if _game(game_id) == "xd":
        output = _xd_direct_face(source, normal + shiny_pixels)
        pixels = _texture(output[:7520], (42, 84))
        if pixels[:_FACE_BYTES] != normal or pixels[_FACE_BYTES + 3::4] != shiny_pixels[3::4]:
            raise FormatError("XD Castform face changed its normal cell or alpha frame")
    else:
        template = _face_header(indexed=False) + bytes(14912 - 128)
        output = make_colosseum_shadow_lugia_face(template, normal, shiny_pixels)
        if _texture(output, (42, 84)) != normal + shiny_pixels:
            raise FormatError("Castform weather face RGBA8 roundtrip failed")
    return output


def _archive(source: bytes, *, group: int):
    if type(source) is not bytes or len(source) < 128:
        raise FormatError("truncated Castform weather archive")
    data = parse_fsys(source)
    if data["group_id"] != group:
        raise FormatError("unexpected Castform weather archive group")
    return data


def _member(archive: bytes, data: dict, resource: int, name: str) -> dict:
    rows = [row for row in data["members"] if int(row["identifier_raw"], 16) == resource
            and row["name"] == name and row["compression"] == "LZSS"]
    if len(rows) != 1:
        raise FormatError("expected one native Castform weather resource")
    return rows[0]


def append_castform_resources(game_id: str, read_archive: Callable[[str], bytes],
                              pending_updates: dict[str, bytes], *,
                              model_builder: Callable[[str, int, bytes], bytes],
                              shiny_face_pixels: Callable[[str, int, bytes], bytes]) -> dict:
    """Stage all four FSYS outputs atomically into the caller's pending mapping.

    model_builder(game_id, model_id, original_pkx) returns its qualified rare
    PKX. shiny_face_pixels(game_id, model_id, original_normal_rgba42) returns
    a qualified 42x42 RGBA portrait with the exact original frame alpha.
    The returned resource maps have integer native model IDs as keys.
    """
    game = _game(game_id)
    if type(pending_updates) is not dict or not callable(model_builder) or not callable(shiny_face_pixels):
        raise FormatError("Castform resource staging requires a dictionary and explicit artwork callbacks")
    original_faces = read_archive("poke_face.fsys")
    face_directory = _archive(original_faces, group=0x5C0)
    current_faces = pending_updates.get("poke_face.fsys", original_faces)
    _archive(current_faces, group=0x5C0)
    faces = {}
    prepared, model_report, face_report = {}, [], []
    for model in (414, 415, 416):
        suffix, group = _FORMS[model]
        filename = f"pkx_powalen_{suffix}.fsys"
        resource = _MODEL_IDS[game][model]
        original = read_archive(filename)
        directory = _archive(original, group=group)
        source_member = _member(original, directory, resource, f"powalen_{suffix}")
        native = decoded_member(original, source_member)
        variant = model_builder(game_id, model, native)
        if type(variant) is not bytes or not variant or variant == native:
            raise FormatError("Castform rare model builder must provide a distinct qualified PKX")
        current = pending_updates.get(filename, original)
        _archive(current, group=group)
        prepared[filename] = append_actor_models(
            current, {}, original, resource,
            {SHINY_RESOURCES[model]: (f"rare_powalen_{suffix}_orre", variant)}, resource_type=0x1E00)
        model_report.append({"model_id": model, "archive": filename, "group": group,
            "native_resource": resource, "shiny_resource": SHINY_RESOURCES[model],
            "native_pkx_sha256": hashlib.sha256(native).hexdigest(),
            "shiny_pkx_sha256": hashlib.sha256(variant).hexdigest()})
        face_member = _member(original_faces, face_directory, _FACE_IDS[game][model], f"face385{suffix}")
        native_face = decoded_member(original_faces, face_member)
        normal_pixels = _native_face(native_face, game_id)
        shiny = shiny_face_pixels(game_id, model, normal_pixels)
        atlas = make_weather_face_atlas(native_face, shiny, game_id=game_id)
        faces[SHINY_FACE_RESOURCES[model]] = (f"face385{suffix}_shiny_orre", atlas)
        face_report.append({"model_id": model, "native_resource": _FACE_IDS[game][model],
            "shiny_resource": SHINY_FACE_RESOURCES[model], "normal_cell_unchanged": True,
            "native_alpha_frame_preserved": True,
            "native_format": "RGB5A3 / 42x84" if game == "xd" else "RGBA8 / 42x84",
            "native_cache_bytes": 0x1F60 if game == "xd" else None,
            "encoded_bytes": len(atlas),
            "atlas_sha256": hashlib.sha256(atlas).hexdigest()})
    donor = _FACE_IDS[game][415]
    prepared["poke_face.fsys"] = append_actor_models(
        current_faces, {}, original_faces, donor, faces, resource_type=0x1200)
    pending_updates.update(prepared)
    return {"version": VERSION, "game_id": game_id,
        "model_resources": dict(SHINY_RESOURCES), "shiny_face_resources": dict(SHINY_FACE_RESOURCES),
        "models": model_report, "faces": face_report,
        "existing_member_payloads_preserved": True, "pending_updates_committed_together": True,
        "artwork_qualification": "explicit caller-supplied model and native render callbacks"}
