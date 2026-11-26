"""Checked XD Deoxys assets for appended Colosseum form resources.

Resource creation does not select a form, edit a saved identity or invent an
animation. Portrait callbacks must supply genuine opaque square captures;
whole-body DNA artwork has its own capture/registration path.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import math
from pathlib import Path
import re
import struct

from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, parse_fsys, u32
from .engine.rebuild_iso import align, decoded_member
from .engine.shadow_lugia_face import make_colosseum_shadow_lugia_face

VERSION = "colosseum-appended-deoxys-forms-v1"
FORMS = ("attack", "defense", "speed")
FORM_MEMBERS = {"attack": "face410atk", "defense": "face410def", "speed": "face410sp"}
_SUFFIXES = {"attack": "atk", "defense": "def", "speed": "sp"}
MODEL_RESOURCES = {(form, shiny): (0x7DB1 + index * 2 + int(shiny)) << 16 | 0x1E00
                   for index, form in enumerate(FORMS) for shiny in (False, True)}
FACE_RESOURCES = {form: (0x7DB1 + index) << 16 | 0x1200 for index, form in enumerate(FORMS)}
DANCE_GROUP = 0x825
DANCE_RESOURCES = {
    ("attack", False): 0x1BF63200, ("attack", True): 0x1BF73200,
    ("defense", False): 0x1BF93200, ("defense", True): 0x1BFA3200,
    ("speed", False): 0x1BFB3200, ("speed", True): 0x1BFC3200,
}
NORMAL_DANCE_RESOURCES = {False: 0x1BF53200, True: 0x1BF83200}
MODEL_GROUPS = {False: 0x386, True: 0x77E}
_NATIVE = {False: ("pkx_deoxys.fsys", "deoxys", 0x070A1E00),
           True: ("pkx_rare_deoxys.fsys", "rare_deoxys", 0x128B1E00)}
_FACE_DONOR = 0x0F821200
_SLOTS, _ROW, _XD_METADATA, _XD_DAT = 17, 0xD0, 0x84, 0xE60


def _form(form: str) -> str:
    if type(form) is not str or form not in FORMS:
        raise FormatError("unknown imported Deoxys form")
    return form


def verify_xd_deoxys_model(source: bytes, form: str, shiny: bool) -> str:
    """Bind a donor to the original model identity used by the HD captures."""
    from .hd_extra_portrait_catalog import MODEL_IDENTITIES
    _form(form)
    if type(shiny) is not bool or type(source) is not bytes:
        raise FormatError("Deoxys model requires bytes and an explicit shiny flag")
    digest = hashlib.sha256(source).hexdigest()
    if digest != MODEL_IDENTITIES[FORM_MEMBERS[form]][shiny]["model_sha256"]:
        raise FormatError("Deoxys donor differs from its checked original XD form")
    return digest


def extract_xd_deoxys_models(read_archive: Callable[[str], bytes]) -> dict:
    """Read only the six requested donors, never change their source archives."""
    result = {}
    for form in FORMS:
        for shiny in (False, True):
            name = "deoxys_" + _SUFFIXES[form] + ("_c" if shiny else "")
            payload = read_archive("pkx_" + name + ".fsys")
            rows = [r for r in parse_fsys(payload)["members"]
                    if r["name"] == name and r["identifier_raw"].endswith("1e00")]
            if len(rows) != 1:
                raise FormatError("expected one original XD Deoxys form resource")
            source = decoded_member(payload, rows[0])
            verify_xd_deoxys_model(source, form, shiny)
            result[form, shiny] = source
    return result


def _convert_pkx(source: bytes, template: bytes, *, schedule_flags=None) -> bytes:
    """Convert known 17-slot scheduling units while preserving the entire DAT.

    Both native loaders copy the opaque row+8 word. Colosseum's original
    schedules even contain uninitialized-looking words there. Preserve the
    donor value, including Speed Forme's first-row 0x30; never copy a template
    value over it. An explicit mapping may only attest these unchanged words.
    """
    if (type(source) is not bytes or type(template) is not bytes
            or len(source) < _XD_DAT or len(template) < 0x40
            or u32(source, 8) != 0 or u32(source, 0x10) != _SLOTS
            or u32(source, 0x20) != 0xFFFFFFFF or u32(template, 4) != 0
            or u32(template, 8) != _SLOTS or u32(template, 0x10) != 5
            or u32(template, 0x20) != 0xFFFFFFFF):
        raise FormatError("unexpected XD or Colosseum Deoxys PKX container")
    size, native_size = u32(source, 0), u32(template, 0)
    end, native_metadata = _XD_DAT + align(size), 0x40 + align(native_size)
    if (size < 0x20 or end != len(source) or u32(source, _XD_DAT) != size
            or native_size < 0x20 or native_metadata + _SLOTS * _ROW > len(template)
            or u32(template, 0x40) != native_size
            or any(source[_XD_DAT + size:end])):
        raise FormatError("truncated or overlong Deoxys model DAT")
    flags = tuple(u32(source, _XD_METADATA + i * _ROW + 8) for i in range(_SLOTS))
    if schedule_flags is not None:
        if (not isinstance(schedule_flags, tuple) or len(schedule_flags) != _SLOTS
                or any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in schedule_flags)):
            raise FormatError("expected 17 qualified Colosseum scheduling flags")
        if schedule_flags != flags:
            raise FormatError("Deoxys opaque scheduling words must be preserved")
    metadata = bytearray(source[_XD_METADATA:_XD_METADATA + _SLOTS * _ROW])
    for i in range(_SLOTS):
        row = i * _ROW
        count, tracks = struct.unpack_from(">II", metadata, row)
        if not 1 <= count <= 16 or not 1 <= tracks <= 8:
            raise FormatError("unsupported Deoxys animation schedule")
        for field in range(count):
            at = row + 0x0C + field * 4
            seconds = struct.unpack_from(">f", metadata, at)[0]
            if not math.isfinite(seconds) or not 0 <= seconds <= 3600:
                raise FormatError("invalid Deoxys animation duration")
            struct.pack_into(">I", metadata, at, round(seconds * 60))
        for track in range(tracks):
            at = row + 0x8C + track * 8
            kind = u32(metadata, at)
            if kind not in (0, 1, 2):
                raise FormatError("unsupported XD Deoxys animation track kind")
            struct.pack_into(">I", metadata, at, 1 if kind == 0 else 0)
        struct.pack_into(">I", metadata, row + 8, flags[i])
    header = bytearray(template[:0x40])
    struct.pack_into(">I", header, 0, size)
    result = bytes(header) + source[_XD_DAT:end] + bytes(metadata)
    return result + bytes(-len(result) % 32)


def convert_deoxys_model(source: bytes, template: bytes, *, form: str, shiny: bool,
                         schedule_flags=None) -> bytes:
    """Convert an authenticated XD form; never recolor the ordinary Deoxys mesh."""
    verify_xd_deoxys_model(source, form, shiny)
    return _convert_pkx(source, template, schedule_flags=schedule_flags)


def _member(payload: bytes, resource: int, name: str, group: int):
    directory = parse_fsys(payload)
    rows = [r for r in directory["members"]
            if int(r["identifier_raw"], 16) == resource and r["name"] == name
            and r["compression"] == "LZSS"]
    if directory["version_raw"] != "0x00000102" or directory["group_id"] != group or len(rows) != 1:
        raise FormatError("unexpected original Colosseum Deoxys resource")
    return rows[0]


def append_deoxys_resources(game_id: str, read_archive: Callable[[str], bytes],
                            pending_updates: dict[str, bytes], *, xd_models: Mapping,
                            portrait_pixels: Callable[[str, bool], bytes],
                            schedule_flags: Mapping | None = None) -> dict:
    """Stage all native models and portraits atomically in existing archives.

    The normal/shiny model groups remain separate, bounding a single FSYS read.
    Portrait callbacks supply native 42px opaque square RGBA captures. No DNA
    artwork, missing animation or HD readiness is inferred from those portraits.
    """
    if (game_id not in ("GC6P01", "GC6E01", "GC6J01") or type(pending_updates) is not dict
            or not callable(read_archive) or not callable(portrait_pixels)
            or not isinstance(xd_models, Mapping) or set(xd_models) != set(MODEL_RESOURCES)
            or schedule_flags is not None and (not isinstance(schedule_flags, Mapping)
                                               or set(schedule_flags) - set(FORMS))):
        raise FormatError("invalid Colosseum Deoxys resource request")
    original_models = {shiny: read_archive(_NATIVE[shiny][0]) for shiny in (False, True)}
    donors = {shiny: _member(original_models[shiny], _NATIVE[shiny][2], _NATIVE[shiny][1],
                            MODEL_GROUPS[shiny]) for shiny in (False, True)}
    template = decoded_member(original_models[False], donors[False])
    prepared, models, faces = {}, [], []
    for shiny in (False, True):
        additions = {}
        for form in FORMS:
            source = xd_models[form, shiny]
            converted = convert_deoxys_model(source, template, form=form, shiny=shiny,
                schedule_flags=None if schedule_flags is None else schedule_flags.get(form))
            resource = MODEL_RESOURCES[form, shiny]
            additions[resource] = ("orre_deoxys_" + _SUFFIXES[form] + ("_c" if shiny else ""), converted)
            models.append({"form": form, "shiny": shiny, "archive": _NATIVE[shiny][0],
                "group": MODEL_GROUPS[shiny], "resource": resource, "bytes": len(converted),
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "converted_sha256": hashlib.sha256(converted).hexdigest(),
                "dat_sha256": hashlib.sha256(source[_XD_DAT:_XD_DAT + u32(source, 0)]).hexdigest(),
                "xd_dat_and_animation_tracks_preserved": True})
        name = _NATIVE[shiny][0]
        current = pending_updates.get(name, original_models[shiny])
        _member(current, _NATIVE[shiny][2], _NATIVE[shiny][1], MODEL_GROUPS[shiny])
        prepared[name] = append_actor_models(current, {}, original_models[shiny], _NATIVE[shiny][2],
                                             additions, resource_type=0x1E00)
        members = {int(r["identifier_raw"], 16): r for r in parse_fsys(prepared[name])["members"]}
        for report in models:
            if report["shiny"] is shiny:
                report["stored_bytes"] = members[report["resource"]]["stored_size"]
    original_faces = read_archive("poke_face.fsys")
    face_member = _member(original_faces, _FACE_DONOR, "face410", 0x5C0)
    face_template = decoded_member(original_faces, face_member)
    additions = {}
    for form in FORMS:
        pixels = [portrait_pixels(form, shiny) for shiny in (False, True)]
        if any(type(p) is not bytes or len(p) != 42 * 42 * 4 or any(a != 255 for a in p[3::4]) for p in pixels):
            raise FormatError("Deoxys portraits require complete opaque 42px square captures")
        atlas = make_colosseum_shadow_lugia_face(face_template, *pixels)
        additions[FACE_RESOURCES[form]] = ("face410_" + _SUFFIXES[form] + "_orre", atlas)
        faces.append({"form": form, "resource": FACE_RESOURCES[form], "bytes": len(atlas),
                      "atlas_sha256": hashlib.sha256(atlas).hexdigest(), "native_format": "RGBA8 / 42x84"})
    current_faces = pending_updates.get("poke_face.fsys", original_faces)
    _member(current_faces, _FACE_DONOR, "face410", 0x5C0)
    prepared["poke_face.fsys"] = append_actor_models(
        current_faces, {}, original_faces, _FACE_DONOR, additions, resource_type=0x1200)
    originals = {_NATIVE[shiny][0]: original_models[shiny] for shiny in (False, True)}
    originals["poke_face.fsys"] = original_faces
    sizes = {name: {"original_bytes": len(originals[name]), "updated_bytes": len(payload)}
             for name, payload in prepared.items()}
    pending_updates.update(prepared)
    return {"version": VERSION, "game_id": game_id, "models": models, "faces": faces,
            "archive_sizes": sizes, "normal_and_shiny_groups_separate": True,
            "original_member_payloads_preserved": True, "updates_committed_together": True,
            "artwork_qualification": "explicit caller-supplied square capture callbacks",
            "dna_body_artwork_included": False}


def deoxys_hd_material_coverage() -> dict:
    """Resolve all genuine x4 donors for the imported byte-identical DATs."""
    from .hd_extra_portrait_catalog import MODEL_IDENTITIES, HD_MATERIAL_SOURCE_PINS
    from .hd_form_materials import material_recipes
    authored = material_recipes("GXXP01")
    pins = HD_MATERIAL_SOURCE_PINS["xd"]
    keys = {key for form in FORMS for row in MODEL_IDENTITIES[FORM_MEMBERS[form]].values()
            for key in row["material_keys"]}
    rows = {}
    for key in sorted(keys):
        if key in authored:
            rows[key] = {"kind": "authored-pack-derived-material", **authored[key]}
        elif key in pins:
            rows[key] = {"kind": "exact-pack-material", "sha256": pins[key]}
        else:
            raise FormatError("missing genuine HD Deoxys model material")
    return {"version": VERSION, "required_packs": ["xd"], "materials": rows,
            "native_texture_keys_preserved": True, "native_bitmap_upscaled_for_hd": False}


def prepare_deoxys_hd_materials(pack_roots: Mapping, destination: Path) -> dict:
    """Publish all imported-form maps without writing into the source HD pack."""
    import json
    from PySide6.QtCore import Qt
    from .artwork import _png
    from .hd_images import load_texture, resolve_texture
    from .hd_menu_catalog import _asset_bytes
    from .hd_packs import PACKS
    coverage = deoxys_hd_material_coverage()
    if "xd" not in pack_roots:
        raise ValueError("The pinned XD pack is required for imported Deoxys forms")
    folder = Path(pack_roots["xd"])
    if folder.name == "Textures":
        folder = folder.parent
    if folder.is_symlink() or folder.is_junction() or Path(destination).is_symlink() or Path(destination).is_junction():
        raise ValueError("Deoxys HD paths cannot be linked")
    folder, target = folder.resolve(), Path(destination).resolve()
    if target == folder or target.is_relative_to(folder):
        raise ValueError("Deoxys HD overlays cannot change the source pack")
    pack = PACKS["xd"]
    marker = json.loads((folder / "installed.json").read_text("utf8"))
    if marker.get("key") != pack.key or marker.get("archives") != [p.sha256 for p in pack.parts]:
        raise ValueError("The Deoxys HD pack differs from the release-pinned version")
    prepared, assets = [], []
    for key, recipe in coverage["materials"].items():
        match = re.fullmatch(r"tex1_(\d+)x(\d+)_[0-9a-f]+_\d+\.png", key)
        if match is None:
            raise ValueError("Invalid Deoxys material texture key")
        width, height = map(int, match.groups())
        if recipe["kind"] == "authored-pack-derived-material":
            payload, digest = _asset_bytes("form-materials/" + key)
            if digest != recipe["sha256"] or len(payload) != recipe["bytes"]:
                raise ValueError("Registered Deoxys material changed")
            if len(payload) < 24 or payload[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" or struct.unpack_from(">II", payload, 16) != (width * 4, height * 4):
                raise ValueError("Registered Deoxys material must be native x4")
            source = {"registered_file": key, "sha256": digest, "source_scale": 4}
        else:
            path = resolve_texture(folder / "Textures", key)
            loaded = load_texture(path, expected_native_size=(width, height), max_scale=16)
            if loaded.metadata["sha256"] != recipe["sha256"] or loaded.metadata["source_scale"] not in (4, 8, 16):
                raise ValueError("Deoxys material differs from the genuine pinned HD source")
            image = loaded.image.scaled(width * 4, height * 4,
                Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            payload = _png((width * 4, height * 4), bytes(image.constBits()))
            source = loaded.metadata
        path = target / key
        if path.is_symlink() or path.is_junction() or (path.exists() and path.read_bytes() != payload):
            raise ValueError("Conflicting imported Deoxys HD material")
        prepared.append((path, payload))
        assets.append({"file": key, "sha256": hashlib.sha256(payload).hexdigest(),
                       "kind": recipe["kind"], "origin": source, "output_scale": 4})
    target.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for path, payload in prepared:
            if not path.exists():
                with path.open("xb") as stream:
                    created.append(path)
                    stream.write(payload)
    except Exception:
        for path in created:
            path.unlink()
        raise
    return {**coverage, "assets": assets, "files": {r["file"]: r["sha256"] for r in assets},
            "active": True, "native_rom_changed": False}
