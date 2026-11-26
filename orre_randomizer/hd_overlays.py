"""Two-source native/HD contracts for the randomizer's authored resources.

Run on a worker thread against the generated, uncompressed ISO. Only the
destination is written; meshes, material colours, gameplay and saves stay in
the ISO. Native assets come from the game. HD assets must come from a pinned
pack, with explicit donor keys and deterministic custom recolouring. Filtering
a native image never satisfies the HD contract.

Dolphin names follow VideoCommon/TextureInfo.cpp::CalculateTextureName (and
5.0 HiresTextures.cpp::GenBaseName): XXH64 of the tiled *base level*, and of
the used TLUT interval, including indices in the tile padding. Sources:
https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/TextureInfo.cpp
https://github.com/dolphin-emu/dolphin/blob/5.0/Source/Core/VideoCommon/HiresTextures.cpp
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
import colorsys
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
from threading import Event

from .artwork import ArtworkError, _decode_pixels, _png, _read_range, _rgb565, _rgb5a3
from .engine.actor_palette import _walk_materials
from .engine.analyze_game import FormatError, check_range, cstring, decompress_lzss, parse_fsys, u32
from .engine.survey_assets import fst_inventory


class OverlayError(ValueError):
    """A generated resource could not be safely represented as an overlay."""


class _MissingHDAsset(OverlayError):
    """Native mode remains usable while this genuine HD source is absent."""


VERSION = 2
_MANIFEST = "orre-overlays-v2.json"
_MASK = (1 << 64) - 1
_PRIMES = (11400714785074694791, 14029467366897019727, 1609587929392839161,
           9650029242287828579, 2870177450012600261)
_BLOCKS = {0: (8, 8, 32), 1: (8, 4, 32), 2: (8, 4, 32), 3: (4, 4, 32),
           4: (4, 4, 32), 5: (4, 4, 32), 6: (4, 4, 64), 8: (8, 8, 32),
           9: (8, 4, 32), 10: (4, 4, 32), 14: (8, 8, 32)}
_MAX_ARCHIVE = 64 * 1024 * 1024
_MAX_MEMBER = 8 * 1024 * 1024
_MAX_TEXTURES = 4096
_CASTFORM_ARCHIVES = {"pkx_powalen_w.fsys": 0x7DA11E00,
                      "pkx_powalen_f.fsys": 0x7DA21E00,
                      "pkx_powalen_i.fsys": 0x7DA31E00}
_CASTFORM_FACES = frozenset((0x7DA11200, 0x7DA21200, 0x7DA31200))
_CASTFORM_ROLES = frozenset(("castform_battle", "castform_portrait"))
_DEOXYS_ROLES = frozenset(("deoxys_battle", "deoxys_portrait", "deoxys_field"))
_LUGIA_RECONSTRUCTED_MATERIALS = {
    "tex1_32x32_f135b3b243a3e441_14.png": (32, 0x6E50, 0x6EC0, 0x40081, "reflection-environment"),
    "tex1_16x16_a70005786d19905c_14.png": (16, 0x6F9C, 0x700C, 0x30010, "mouth-interior"),
    "tex1_16x16_50629643191a1a90_14.png": (16, 0x703C, 0x70AC, 0x30010, "tongue-and-teeth"),
}

# Explicit native actors replaced by the existing generators. Appended orre_*
# aliases are included as well. Never enumerate ordinary battle Lugia as a
# surrogate for a Shadow specimen.
_COLO_ACTORS = {
    "S1_out.fsys": set(),
    "M2_guild_1F_1.fsys": {0x06F90400},
    "M2_cave_1F_2.fsys": {0x06F90400, 0x012E0400, 0x11060400, 0x10D20400, 0x10D10400},
    "M3_shrine_1F.fsys": {0x012B0400},
    "M3_houseC_1F.fsys": {0x012B0400},
    "D4_casino_colo.fsys": {0x012B0400},
}
_SPOT_IDS = {0x16600400, 0x165A0400, 0x165F0400, 0x165C0400, 0x165B0400,
             0x187A0400, 0x20560400, 0x161D0400, 0x16610400}
_XD_ACTORS = {
    "M6_tower_top.fsys": {0x166E0400, 0x18820400, 0x18560400, 0x18570400},
    "D3_out.fsys": {0x166B0400}, "D5_out.fsys": {0x166B0400},
    "esaba_A.fsys": _SPOT_IDS, "esaba_B.fsys": _SPOT_IDS, "esaba_C.fsys": _SPOT_IDS,
    "people_archive.fsys": _SPOT_IDS | {0x18490400, 0x166C0400, 0x1F540400, 0x220E0400},
}


def _rot(value: int, bits: int) -> int:
    value &= _MASK
    return ((value << bits) | (value >> (64 - bits))) & _MASK


def xxhash64(data: bytes) -> int:
    """Portable XXH64(seed=0); no optional native hashing dependency."""
    p1, p2, p3, p4, p5 = _PRIMES

    def lane(acc, value):
        return _rot(acc + value * p2, 31) * p1 & _MASK

    at, size = 0, len(data)
    if size >= 32:
        accumulators = [(p1 + p2) & _MASK, p2, 0, (-p1) & _MASK]
        while at <= size - 32:
            for index, word in enumerate(struct.unpack_from("<4Q", data, at)):
                accumulators[index] = lane(accumulators[index], word)
            at += 32
        value = sum(_rot(acc, bits) for acc, bits in zip(accumulators, (1, 7, 12, 18))) & _MASK
        for acc in accumulators:
            value = ((value ^ lane(0, acc)) * p1 + p4) & _MASK
    else:
        value = p5
    value = (value + size) & _MASK
    while at <= size - 8:
        value = (_rot(value ^ lane(0, struct.unpack_from("<Q", data, at)[0]), 27) * p1 + p4) & _MASK
        at += 8
    if at <= size - 4:
        value = (_rot(value ^ (struct.unpack_from("<I", data, at)[0] * p1), 23) * p2 + p3) & _MASK
        at += 4
    for byte in data[at:]:
        value = _rot(value ^ (byte * p5), 11) * p1 & _MASK
    value ^= value >> 33
    value = value * p2 & _MASK
    value ^= value >> 29
    value = value * p3 & _MASK
    return value ^ (value >> 32)


def _size(width: int, height: int, fmt: int) -> int:
    if (type(width) is not int or type(height) is not int or not 1 <= width <= 1024
            or not 1 <= height <= 1024 or fmt not in _BLOCKS):
        raise OverlayError("Unsupported native texture dimensions or format.")
    x, y, stride = _BLOCKS[fmt]
    return ((width + x - 1) // x) * ((height + y - 1) // y) * stride


def dolphin_texture_name(width: int, height: int, fmt: int, data: bytes, *,
                         palette: bytes = b"", mipmaps: bool = False) -> str:
    """Return the exact tex1 basename, without an extension or mip suffix."""
    if len(data) != _size(width, height, fmt):
        raise OverlayError("Texture hash requires exactly one tiled base level.")
    tlut = ""
    if fmt in (8, 9, 10):
        count = {8: 16, 9: 256, 10: 16384}[fmt]
        if len(palette) < count * 2:
            raise OverlayError("Texture palette is incomplete.")
        indices = ([value for byte in data for value in (byte >> 4, byte & 15)] if fmt == 8 else
                   list(data) if fmt == 9 else
                   [value[0] & 0x3FFF for value in struct.iter_unpack(">H", data)])
        used = palette[min(indices) * 2:(max(indices) + 1) * 2]
        tlut = f"_{xxhash64(used):016x}"
    elif palette:
        raise OverlayError("A direct texture cannot have a palette hash.")
    return f"tex1_{width}x{height}{'_m' if mipmaps else ''}_{xxhash64(data):016x}{tlut}_{fmt}"


@dataclass(frozen=True)
class _Texture:
    width: int
    height: int
    fmt: int
    data: bytes
    palette: bytes = b""
    palette_format: int = 2
    mipmaps: bool = False


def _pixels(texture: _Texture) -> bytes:
    width, height, fmt, data = texture.width, texture.height, texture.fmt, texture.data
    if len(data) != _size(width, height, fmt):
        raise OverlayError("Truncated native texture.")
    if fmt in (5, 6, 14):
        return _decode_pixels(width, height, {5: 16, 6: 32, 14: 4}[fmt], data)
    pixels = bytearray(width * height * 4)
    bw, bh, stride = _BLOCKS[fmt]

    def color(word, kind):
        if kind == 2:
            return _rgb5a3(word)
        if kind == 1:
            return _rgb565(word)
        if kind == 0:
            return (word & 255,) * 3 + (word >> 8,)
        raise OverlayError("Unsupported native palette format.")

    for y in range(height):
        for x in range(width):
            block = ((y // bh) * ((width + bw - 1) // bw) + x // bw) * stride
            index = (y % bh) * bw + x % bw
            if fmt in (0, 8):
                sample = data[block + index // 2] >> (4 if index % 2 == 0 else 0) & 15
            elif fmt in (1, 2, 9):
                sample = data[block + index]
            else:
                sample = struct.unpack_from(">H", data, block + index * 2)[0]
            if fmt in (8, 9, 10):
                sample &= 0x3FFF if fmt == 10 else 255
                if (sample + 1) * 2 > len(texture.palette):
                    raise OverlayError("Native texture references a missing palette entry.")
                rgba = color(struct.unpack_from(">H", texture.palette, sample * 2)[0], texture.palette_format)
            elif fmt == 4:
                rgba = _rgb565(sample)
            elif fmt in (0, 1):
                rgba = (sample * 17 if fmt == 0 else sample,) * 4
            elif fmt == 2:
                rgba = ((sample & 15) * 17,) * 3 + ((sample >> 4) * 17,)
            else:  # IA8: alpha followed by intensity in GameCube byte order.
                rgba = (sample & 255,) * 3 + (sample >> 8,)
            at = (y * width + x) * 4
            pixels[at:at + 4] = bytes(rgba)
    return bytes(pixels)


def _face(raw: bytes) -> _Texture:
    check_range(raw, 0, 128, "custom face header")
    width, height = struct.unpack_from(">HH", raw)
    fmt = {4: 14, 8: 9, 16: 5, 32: 6}.get(raw[4])
    if fmt is None or width not in (42, 84) or height != 84 or raw[5] != 1 or u32(raw, 0x28) != 128:
        raise OverlayError("Unexpected custom face atlas.")
    size = _size(width, height, fmt)
    check_range(raw, 128, size, "custom face samples")
    palette = b""
    if fmt == 9:
        if u32(raw, 0xC) != 3 or u32(raw, 0x48) != 128 + size:
            raise OverlayError("Unexpected custom face palette.")
        check_range(raw, 128 + size, 512, "custom face palette")
        palette = raw[128 + size:128 + size + 512]
    return _Texture(width, height, fmt, raw[128:128 + size], palette)


def _dat_textures(dat: bytes) -> Iterator[_Texture]:
    check_range(dat, 0, 32, "custom DAT header")
    length, size, count, exports, imports = struct.unpack_from(">5I", dat)
    reloc_start = 32 + size
    symbols = reloc_start + count * 4
    names = symbols + exports * 8
    if (imports or not 0 < exports <= 64 or count > _MAX_MEMBER // 4 or
            not names < length <= len(dat)):
        raise OverlayError("Unexpected custom DAT layout.")
    check_range(dat, reloc_start, count * 4 + exports * 8, "custom DAT directory")
    data = dat[32:reloc_start]
    relocations = set(struct.unpack_from(f">{count}I", dat, reloc_start))
    if any(slot % 4 or slot + 4 > len(data) or u32(data, slot) >= len(data) for slot in relocations):
        raise OverlayError("Invalid custom DAT relocation.")
    scenes = [pointer for pointer, name in struct.iter_unpack(">II", dat[symbols:names])
              if names + name < length and cstring(dat[:length], names + name) == "scene_data"]
    if len(scenes) != 1:
        raise OverlayError("Custom model has no unique native scene.")
    check_range(data, scenes[0], 4, "custom scene")
    table = u32(data, scenes[0])
    check_range(data, table, 4, "custom model table")
    images, palettes = set(), set()
    for index in range(64):
        slot = table + index * 4
        check_range(data, slot, 4, "custom model table slot")
        model = u32(data, slot)
        if not model:
            break
        if slot not in relocations:
            raise OverlayError("Custom model table has an invalid pointer.")
        check_range(data, model, 16, "custom model set")
        model_images, model_palettes, _ = _walk_materials(data, relocations, model)
        images.update(model_images)
        palettes.update(model_palettes)
    else:
        raise OverlayError("Custom model table exceeds limits.")
    if len(images) > 256 or len(palettes) > 256:
        raise OverlayError("Custom material graph exceeds limits.")
    for image in sorted(images):
        check_range(data, image, 24, "custom image descriptor")
        start, width, height, fmt, mipmap, _, max_lod = struct.unpack_from(">IHHIIff", data, image)
        size = _size(width, height, fmt)
        if mipmap not in (0, 1) or not math.isfinite(max_lod) or (mipmap and not 0 <= max_lod <= 10):
            raise OverlayError("Unsupported custom mipmap descriptor.")
        check_range(data, start, size, "custom image samples")
        samples = data[start:start + size]
        if fmt not in (8, 9, 10):
            yield _Texture(width, height, fmt, samples, mipmaps=bool(mipmap))
            continue
        # Direct TObj pointers establish image/TLUT pairing. Animated palettes
        # can refer through separate tables; retain every authored candidate.
        direct = {u32(data, slot + 4) for slot in relocations if u32(data, slot) == image
                  and slot + 4 in relocations and u32(data, slot + 4) in palettes}
        candidates = direct or palettes
        for palette in sorted(candidates):
            check_range(data, palette, 14, "custom palette descriptor")
            pointer, kind, _, entries = struct.unpack_from(">IIIH", data, palette)
            required = {8: 16, 9: 256, 10: 16384}[fmt]
            if kind not in (0, 1, 2) or not 0 < entries <= required:
                raise OverlayError("Unsupported custom palette descriptor.")
            check_range(data, pointer, entries * 2, "custom palette samples")
            # GX loads full palette banks; unused entries are zero-padded.
            # Hash trimming excludes those entries when no sample uses them.
            used = ([v for byte in samples for v in (byte >> 4, byte & 15)] if fmt == 8 else
                    list(samples) if fmt == 9 else
                    [word[0] & 0x3FFF for word in struct.iter_unpack(">H", samples)])
            if max(used) >= entries:
                raise OverlayError("Indexed custom texture uses an unauthored palette entry.")
            words = data[pointer:pointer + entries * 2] + bytes((required - entries) * 2)
            yield _Texture(width, height, fmt, samples, words, kind, bool(mipmap))
        if not candidates:
            raise OverlayError("Custom indexed image has no authored palette.")


def _disc_archives(iso: Path, *, is_xd: bool, include_pkx: bool = False,
                   extra_names: set[str] | None = None) -> Iterator[tuple[str, bytes]]:
    actors = _XD_ACTORS if is_xd else _COLO_ACTORS
    selected = set(actors) | set(_CASTFORM_ARCHIVES) | (extra_names or set()) | {
        "poke_face.fsys", "pkx_darklugia.fsys" if is_xd else "pkx_lugia.fsys"}
    if not is_xd:
        selected.add("DNA_key.fsys")
    with iso.open("rb") as stream:
        length = os.fstat(stream.fileno()).st_size
        boot = _read_range(stream, 0, 0x440, length)
        prefix = b"GXX" if is_xd else b"GC6"
        if (boot[:3] != prefix or boot[3:6] not in (b"P01", b"E01", b"J01") or
                boot[6:8] != bytes(2) or boot[0x1C:0x20] != bytes.fromhex("c2339f3d")):
            raise OverlayError("Expected a supported generated uncompressed ISO.")
        offset, size = struct.unpack_from(">II", boot, 0x424)
        if not 12 <= size <= 1024 * 1024:
            raise OverlayError("Invalid generated ISO filesystem.")
        entries, _ = fst_inventory(_read_range(stream, offset, size, length))
        seen = set()
        for entry in entries:
            name = entry["path"]
            if name not in selected and not (include_pkx and name.startswith("pkx_") and name.endswith(".fsys")):
                continue
            if name in seen or not 0x60 <= entry["size"] <= _MAX_ARCHIVE:
                raise OverlayError("Invalid custom resource archive.")
            seen.add(name)
            yield name, _read_range(stream, entry["disc_offset"], entry["size"], length)


def _raw_member(archive: bytes, member: dict) -> bytes:
    if not 0 < member["unpacked_size"] <= _MAX_MEMBER:
        raise OverlayError("Custom resource exceeds limits.")
    stored = archive[member["offset"]:member["offset"] + member["stored_size"]]
    raw = decompress_lzss(stored, max_output=_MAX_MEMBER) if member["compression"] == "LZSS" else stored
    if len(raw) != member["unpacked_size"]:
        raise OverlayError("Custom resource is truncated.")
    return raw


def _selected(name: str, member: dict, is_xd: bool) -> str | None:
    ident = int(member["identifier_raw"], 16)
    if not is_xd and name in ("poke_face.fsys", "pkx_deoxys.fsys", "pkx_rare_deoxys.fsys"):
        from .deoxys_resources import FACE_RESOURCES, MODEL_RESOURCES
        if name == "poke_face.fsys" and ident in FACE_RESOURCES.values():
            return "deoxys_portrait"
        if name != "poke_face.fsys" and ident in MODEL_RESOURCES.values():
            return "deoxys_battle"
    if _CASTFORM_ARCHIVES.get(name) == ident:
        return "castform_battle"
    if name == "poke_face.fsys":
        if ident in _CASTFORM_FACES:
            return "castform_portrait"
        if ident in (0x7DF51200, 0x7DF61200, 0x7DF71200):
            return "portrait"
        from .hd_extra_portraits import is_extra_portrait_member, extra_portraits_registered
        if (ident & 0xFF00 == 0x1200 and
                is_extra_portrait_member(member["name"], "xd" if is_xd else "colosseum") and
                extra_portraits_registered()):
            return "retail_form"
        if is_xd:
            from .hd_portraits import is_ordinary_portrait_member
            if ident & 0xFF00 == 0x1200 and is_ordinary_portrait_member(member["name"]):
                return "retail_portrait"
        return None
    if name == "pkx_lugia.fsys":
        return "battle" if ident in (0x7DF31E00, 0x7DF41E00) else None
    if name == "pkx_darklugia.fsys":
        return "battle" if ident in (0x19661E00, 0x7DF41E00) else None
    if name == "DNA_key.fsys":
        return "dna" if ident == 0x107E0200 else None
    targets = (_XD_ACTORS if is_xd else _COLO_ACTORS).get(name, set())
    if ident & 0xFF00 == 0x0400 and (ident in targets or member["name"].startswith("orre_")
                                    or member["name"].startswith("miror_dancer_")):
        return "field"
    return None


def _write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise OverlayError("Overlay files cannot be symbolic links.")
    descriptor, filename = tempfile.mkstemp(prefix=".orre-overlay-", suffix=".tmp", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _checkpoint(cancel):
    if cancel is not None and cancel.is_set():
        raise InterruptedError("Custom texture generation cancelled.")


def _texture_key(texture):
    return dolphin_texture_name(texture.width, texture.height, texture.fmt, texture.data,
                                palette=texture.palette) + ".png"


def _mipmap_alias(filename: str) -> str:
    """Only the sampler flag changes; dimensions, native hashes and GX format stay exact."""
    return re.sub(r"^(tex1_\d+x\d+)_", r"\1_m_", filename, count=1) if "_m_" not in filename else filename.replace("_m_", "_", 1)


def _rgba_png(data: bytes, width: int, height: int) -> bytes:
    return _png((width, height), data)


def _native_reference(folder: Path, pixels: bytes, width: int, height: int) -> dict:
    png = _rgba_png(pixels, width, height)
    digest = hashlib.sha256(png).hexdigest()
    relative = "NativeReferences/" + digest + ".png"
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write(path, png)
    return {"file": relative, "sha256": digest, "width": width, "height": height}


def _castform_game_id(source: Path, is_xd: bool) -> str:
    from .hd_menu_catalog import SUPPORTED
    with source.open("rb") as stream:
        identity = stream.read(6).decode("ascii")
    if identity not in SUPPORTED or not identity.startswith("GXX" if is_xd else "GC6"):
        raise OverlayError("Custom Castform resource has an invalid regional disc identity.")
    return identity


def deoxys_hd_contract() -> dict:
    """Qualify the complete imported appearance set without any source ROM."""
    from .deoxys_assets import asset_manifest, artwork_png, hd_face_recipes, xd_models
    from .deoxys_resources import FORMS, deoxys_hd_material_coverage
    directory, _ = asset_manifest()
    xd_models(directory)
    for form in FORMS:
        for shiny in (False, True):
            for hd in (False, True):
                for role in ('head', 'body'):
                    artwork_png(form, shiny=shiny, hd=hd, role=role, directory=directory)
    coverage = deoxys_hd_material_coverage()
    recipes = json.dumps(coverage, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {'version': 1, 'enabled': True, 'game': 'colosseum',
            'asset_registry_sha256': hashlib.sha256((directory / 'deoxys-assets.json').read_bytes()).hexdigest(),
            'material_recipes_sha256': hashlib.sha256(recipes).hexdigest(),
            'material_keys': sorted(coverage['materials']),
            'portrait_keys': sorted(hd_face_recipes(directory)), 'required_packs': ['xd'],
            'native_bitmap_upscaled_for_hd': False}


def _deoxys_origin(asset, contract, pixels):
    key = asset['base_key']
    if key in contract['portrait_keys']:
        from .deoxys_assets import hd_face_recipes
        recipe = hd_face_recipes()[key]
        if (hashlib.sha256(pixels).hexdigest() != recipe['native_rgba_sha256']
                or (asset['native']['width'], asset['native']['height']) != (42, 84)):
            raise OverlayError('Imported Deoxys portrait changed its qualified native pixels')
        role = 'portrait'
    elif key in contract['material_keys']:
        role = 'material'
    else:
        return None
    return {'game': 'xd', 'file': key, 'native_source': 'Original XD Deoxys form imported into Colosseum',
            'transform': {'type': 'imported-deoxys', 'role': role, 'native_key': key,
                          'asset_registry_sha256': contract['asset_registry_sha256'],
                          'material_recipes_sha256': contract['material_recipes_sha256'],
                          'native_rgba_sha256': hashlib.sha256(pixels).hexdigest()}}


def prepare_deoxys_hd(contract, pack_roots, destination):
    """Generate authenticated imported maps and square face atlases together."""
    from .deoxys_assets import prepare_hd_faces
    from .deoxys_resources import prepare_deoxys_hd_materials
    expected = deoxys_hd_contract()
    if not isinstance(contract, dict) or any(contract.get(key) != value for key, value in expected.items()):
        raise OverlayError('Imported Deoxys native/HD registry changed; recreate this game folder')
    materials = prepare_deoxys_hd_materials(pack_roots, Path(destination))
    portraits = prepare_hd_faces(destination)
    files = dict(materials['files'])
    for name, digest in portraits['files'].items():
        if name in files and files[name] != digest:
            raise OverlayError('Conflicting imported Deoxys HD texture identities')
        files[name] = digest
    return {'active': True, 'contract': expected, 'materials': materials, 'portraits': portraits, 'files': files}


def _castform_hd_origin(game_id, asset, pixels):
    """Custom weather resources have no identity or constant-colour fallback."""
    from .hd_castform_shinies import castform_shiny_origin, castform_shiny_recipes
    from .hd_form_materials import material_recipes
    role = "portrait" if "castform_portrait" in asset["castform_roles"] else "material"
    size = asset["native"]["width"], asset["native"]["height"]
    try:
        if not castform_shiny_recipes(game_id)["active"]:
            return None, "Registered custom Castform native/x4 catalogue is unavailable"
        origin = castform_shiny_origin(game_id, asset["base_key"], size,
            hashlib.sha256(pixels).hexdigest(), role=role)
    except ValueError as error:
        return None, str(error)
    if origin is not None:
        return origin, None
    if role == "material":
        row = material_recipes(game_id).get(asset["base_key"])
        if row is not None and row["native_dimensions"] == list(size):
            return {"game": row["pack"], "required_packs": [row["pack"]],
                "native_source": "exact reviewed stock form-material texture key",
                "transform": {"type": "castform-stock-material", "version": 1,
                    "game_id": game_id, "native_key": asset["base_key"], "native_size": list(size)}}, None
    return None, "No registered native/x4 pair for this custom Castform resource"


def _render_castform_stock(origin, native_image):
    from .hd_form_materials import material_recipes
    from .hd_menu_catalog import _asset_bytes
    from PySide6.QtGui import QImage
    transform = origin.get("transform", {})
    row = material_recipes(transform.get("game_id", "")).get(transform.get("native_key", ""))
    size = [native_image.width(), native_image.height()]
    if (transform.get("version") != 1 or row is None or row["native_dimensions"] != size
            or transform.get("native_size") != size or origin.get("game") != row["pack"]):
        raise ValueError("Captured Castform stock-material identity changed")
    payload, digest = _asset_bytes("form-materials/" + row["file"])
    if digest != row["sha256"] or len(payload) != row["bytes"]:
        raise ValueError("Registered Castform stock-material PNG changed")
    image = QImage.fromData(payload, "PNG")
    if image.isNull() or [image.width(), image.height()] != [v * 4 for v in size]:
        raise ValueError("Registered Castform stock material is not x4")
    return payload, {"kind": "reviewed-stock-castform-material", "native_key": row["file"],
        "catalogue_sha256": row["catalogue_sha256"], "sha256": digest,
        "native_rgba_sha256": hashlib.sha256(bytes(native_image.constBits())).hexdigest(),
        "native_bitmap_resampled": False}


def _pkx_dat(raw: bytes, xd: bool) -> bytes:
    start = (len(raw) - u32(raw, 0)) & ~31 if xd else 0x40
    if start < 0x40 or start >= len(raw) or u32(raw, start) != u32(raw, 0):
        raise OverlayError("Unexpected native Pokémon model container.")
    return raw[start:]


def _tinted_dat(dat: bytes, recipe) -> bytes:
    from .engine.actor_palette import tint_field_model
    _, size, count, exports, _ = struct.unpack_from(">5I", dat)
    start = 32 + size
    symbols, names = start + count * 4, start + count * 4 + exports * 8
    scenes = [p for p, n in struct.iter_unpack(">II", dat[symbols:names])
              if cstring(dat, names + n) == "scene_data"]
    if len(scenes) != 1:
        raise OverlayError("Native shiny donor has no unique scene.")
    data = bytearray(dat[32:start])
    relocations = set(struct.unpack_from(f">{count}I", dat, start))
    tint_field_model(data, relocations, u32(data, u32(data, scenes[0])), recipe)
    return dat[:32] + bytes(data) + dat[start:]


def _dark_origins() -> dict[str, dict]:
    """Verified bundled XD donor, including the authored white variant."""
    from .engine.postgame_lugia_model import verified_model_asset
    from .engine.shadow_lugia_palette import make_shadow_lugia_shiny
    raw, metadata = verified_model_asset()
    normal = list(_dat_textures(raw[0x40:]))
    shiny = list(_dat_textures(make_shadow_lugia_shiny(raw, xd=False)[0x40:]))
    origins = {}
    for source, target in zip(normal, shiny, strict=True):
        donor = {"game": "xd", "file": _texture_key(source),
                 "native_source": "verified pkx_darklugia.fsys/darklugia",
                 "native_model_sha256": metadata["source"]["model_sha256"],
                 "native_texture_sha256": hashlib.sha256(source.data + source.palette).hexdigest(),
                 "transform": {"type": "identity"}}
        origins[_texture_key(source)] = donor
        if _texture_key(target) != _texture_key(source):
            origins[_texture_key(target)] = dict(donor, transform={"type": "shadow_lugia_belly",
                                                                  "factors": [0.18, 0.18, 0.20]})
    return origins


def _field_origins(iso: Path, xd: bool, wanted: set[str], cancel, progress) -> tuple[dict, list]:
    """Match exact native bytes, including deterministic retail shiny recipes.

    There is no visual-nearest-neighbour lookup: a changed texture must equal
    the existing native tint implementation byte for byte before it can use
    that donor's HD texture.
    """
    from .engine.actor_palette import pkx_recipe
    origins, failures, field_references = {}, [], None
    for archive_name, archive in _disc_archives(iso, is_xd=xd, include_pkx=True):
        if xd and archive_name == "people_archive.fsys":
            field_references = archive
        if not archive_name.startswith("pkx_"):
            continue
        _checkpoint(cancel)
        if progress:
            progress("Native HD origins: " + archive_name)
        for member in parse_fsys(archive)["members"]:
            if not member["identifier_raw"].endswith("1e00") or member["name"].endswith("_bonus"):
                continue
            try:
                raw = _raw_member(archive, member)
                dat = _pkx_dat(raw, xd)
                normal = list(_dat_textures(dat))
                recipe = pkx_recipe(raw, xd=xd)
                tinted = list(_dat_textures(_tinted_dat(dat, recipe)))
                for source, target in zip(normal, tinted, strict=True):
                    donor = {"game": "xd" if xd else "colosseum", "file": _texture_key(source),
                             "native_source": archive_name + "/" + member["name"],
                             "native_model_sha256": hashlib.sha256(raw).hexdigest(),
                             "native_texture_sha256": hashlib.sha256(source.data + source.palette).hexdigest(),
                             "transform": {"type": "identity"}}
                    if _texture_key(source) in wanted:
                        origins[_texture_key(source)] = donor
                    if _texture_key(target) in wanted:
                        transform = {"type": "pkx_recipe", "route": list(recipe[0]), "gain": list(recipe[1])}
                        origins.setdefault(_texture_key(target), dict(donor, transform=transform))
            except (FormatError, OverlayError, struct.error, ValueError) as error:
                failures.append({"archive": archive_name, "member": member["name"], "reason": str(error)})
        if wanted <= origins.keys():
            break
    if xd and wanted - origins.keys() and field_references is not None:
        from .xd_shadow_lugia_model import FIELD_RESOURCES, _FIELD_SHA256
        from .engine.shadow_lugia_palette import make_shadow_lugia_shiny_dat
        members = {int(m["identifier_raw"], 16): m for m in parse_fsys(field_references)["members"]}
        for resource, _ in FIELD_RESOURCES:
            _checkpoint(cancel)
            try:
                member = members[resource]
                dat = _raw_member(field_references, member)
                if hashlib.sha256(dat).hexdigest() != _FIELD_SHA256[resource]:
                    raise OverlayError("XD Shadow Lugia field donor differs from the verified original.")
                normal = list(_dat_textures(dat))
                shiny = list(_dat_textures(make_shadow_lugia_shiny_dat(dat)))
                for source, target in zip(normal, shiny, strict=True):
                    donor = {"game": "xd", "file": _texture_key(source),
                             "native_source": "people_archive.fsys/" + member["name"] + " (authored field model)",
                             "native_model_sha256": _FIELD_SHA256[resource],
                             "native_texture_sha256": hashlib.sha256(source.data + source.palette).hexdigest(),
                             "transform": {"type": "identity"}}
                    if _texture_key(source) in wanted:
                        origins[_texture_key(source)] = donor
                    if _texture_key(target) in wanted and _texture_key(target) != _texture_key(source):
                        origins.setdefault(_texture_key(target), dict(donor, transform={
                            "type": "shadow_lugia_belly", "factors": [.18, .18, .20]}))
            except (KeyError, FormatError, OverlayError, struct.error, ValueError) as error:
                failures.append({"archive": "people_archive.fsys", "resource": f"0x{resource:08x}", "reason": str(error)})
    if not xd and wanted - origins.keys():
        # Plusle's handover/rescue model deliberately keeps its original field
        # choreography and texture frames. Its battle DAT is not the donor.
        # load_actor_model applies the battle PKX's colour recipe to this
        # dedicated field DAT; reconstruct that exact supported route here.
        from .artwork import _disc_files
        try:
            files = _disc_files(iso, {"M2_guild_1F_1.fsys", "pkx_prasle.fsys"})
            room, battle = files["M2_guild_1F_1.fsys"], files["pkx_prasle.fsys"]
            field = next(m for m in parse_fsys(room)["members"] if m["identifier_raw"] == "0x06f90400")
            model = next(m for m in parse_fsys(battle)["members"] if m["identifier_raw"].endswith("1e00"))
            dat = _raw_member(room, field)
            recipe = pkx_recipe(_raw_member(battle, model), xd=False)
            normal = list(_dat_textures(dat))
            tinted = list(_dat_textures(_tinted_dat(dat, recipe)))
            for source, target in zip(normal, tinted, strict=True):
                donor = {"game": "colosseum", "file": _texture_key(source),
                         "native_source": "M2_guild_1F_1.fsys/prasle_b1 (dedicated field model)",
                         "native_model_sha256": hashlib.sha256(dat).hexdigest(),
                         "native_texture_sha256": hashlib.sha256(source.data + source.palette).hexdigest(),
                         "transform": {"type": "identity"}}
                if _texture_key(source) in wanted:
                    origins[_texture_key(source)] = donor
                if _texture_key(target) in wanted:
                    origins.setdefault(_texture_key(target), dict(donor, transform={"type": "pkx_recipe",
                        "route": list(recipe[0]), "gain": list(recipe[1])}))
        except (ArtworkError, FormatError, OverlayError, struct.error, ValueError, StopIteration) as error:
            failures.append({"archive": "M2_guild_1F_1.fsys", "member": "prasle_b1", "reason": str(error)})
    return origins, failures


def _body_donor(raw: bytes) -> dict:
    width, height = struct.unpack_from(">HH", raw)
    fmt = {4: 14, 8: 9, 16: 5, 32: 6}.get(raw[4])
    if fmt is None or u32(raw, 0x28) != 128:
        raise OverlayError("Unsupported native whole-body donor.")
    size = _size(width, height, fmt)
    check_range(raw, 128, size, "whole-body source")
    palette = raw[128 + size:128 + size + 512] if fmt == 9 else b""
    texture = _Texture(width, height, fmt, raw[128:128 + size], palette)
    return {"kind": "pack", "game": "colosseum", "file": _texture_key(texture),
            "native_width": width, "native_height": height,
            "native_sha256": hashlib.sha256(raw).hexdigest()}


def _dna_variants(texture: _Texture, reference_iso: Path, context: Mapping | None, cancel) -> tuple[list, dict]:
    """Reconstruct exact native runtime keys and separate HD compositions."""
    if not context or not context.get("dna_lab"):
        return [texture], {}
    from collections import Counter
    from itertools import product
    from .artwork import _disc_files
    from .engine.dna_keypad import (DNA_KEYPAD_SPECIES, _TILE_ORIGINS, _tile_rows, _BODY_ART_RECT, _CUSTOM_BODY_ART_RECT,
                                    _body_pixels, _tile_art, patch_dna_keypad)
    from .engine.shadow_lugia_body import shadow_lugia_body_pixels
    from .engine.spinda import SPINDA
    from .engine.unown_form import unown_suffix
    mapping = {int(old): (row["species"], row["shiny"]) for old, row in context["dna_lab"].items()}
    deoxys = {int(old): tuple(row) for old, row in context.get('dna_deoxys_samples', {}).items()}
    if set(mapping) != set(DNA_KEYPAD_SPECIES):
        raise OverlayError("Incomplete DNA dual-version asset context.")
    form = int(context.get("unown_form", 0))
    files = _disc_files(reference_iso, {"DNA_key.fsys", "poke_body.fsys"})
    original, bodies = files["DNA_key.fsys"], files["poke_body.fsys"]
    original_members = parse_fsys(original)["members"]
    member = next(m for m in original_members if m["identifier_raw"] == "0x107e0200")
    dat = _raw_member(original, member)
    template = _decode_pixels(128, 128, 4, b"".join(dat[a:b] for a, b in _tile_rows(896, 512)))
    generated = patch_dna_keypad(original, bodies, mapping, unown_form_index=form,
                                 deoxys_samples=deoxys)
    generated_dat = _raw_member(generated, next(m for m in parse_fsys(generated)["members"]
                                               if m["identifier_raw"] == "0x107e0200"))
    if generated_dat[0x7820:0x87820] != texture.data:
        # A differing native composition must have its own explicit recipe;
        # similarity of images is not evidence of resource identity.
        return [texture], {}
    body_members = {m["name"]: m for m in parse_fsys(bodies)["members"]}
    counts = Counter(species for species, _ in mapping.values())
    tiles = []
    lugia = []
    for position, old in enumerate(DNA_KEYPAD_SPECIES):
        species, shiny = mapping[old]
        number = position + 1 if counts[species] > 1 else 0
        if species == old and not shiny and not number:
            continue
        name = "body201" + unown_suffix(form) if species == 201 else f"body{species:03d}"
        name += "_c" if shiny else ""
        deoxys_form = deoxys.get(old, (None, 0))[1] if species == 410 else 0
        donor = (_deoxys_body_origin(deoxys_form, shiny) if deoxys_form
                 else _body_donor(_raw_member(bodies, body_members[name])))
        tiles.append({"position": position, "species": species, "shiny": shiny,
                      "number": number, "body": donor})
        if old in deoxys:
            tiles[-1]['deoxys_form'] = deoxys_form
        if species == 249:
            lugia.append((position, old, number))
    transform = {"type": "dna", "tiles": tiles}
    if any(species == SPINDA for species, _ in mapping.values()):
        transform["runtime_gap"] = "Spinda DNA buffers use specimen PID spot patterns; runtime HD variant is not registered."
    origin = {"game": "colosseum", "file": "tex1_1024x1024_57c039ae574254a7_14.png",
              "native_source": "verified original DNA keypad UI",
              "transform": transform}
    recipes = {_texture_key(texture): origin}
    textures = [texture]
    options = context.get("asset_options", {})
    predictable = options.get("custom_shinies", False) and (
        options.get("seeded_shinies", False) or options.get("shiny_chance_percent") in (0, 100))
    retained = options.get("keep_shadow_lugia_after_purification", False)
    allowed = []
    for _, old, _ in lugia:
        modes = (int(mapping[old][1]),) if predictable else (0, 1)
        allowed.append(modes if retained else modes + tuple(mode + 2 for mode in modes))
    transform["native_runtime_policy"] = {"predictable_shiny": bool(predictable), "retain_dark": bool(retained)}
    if math.prod(len(states) for states in allowed) > 16:
        transform["runtime_gap"] = "More than sixteen independent native Lugia DNA atlas combinations require an explicit runtime HD registry."
        return textures, recipes
    variants = (shadow_lugia_body_pixels(False), shadow_lugia_body_pixels(True),
                _body_pixels(bodies, body_members, 249, False), _body_pixels(bodies, body_members, 249, True))
    for combination in product(*allowed) if lugia else ():
        _checkpoint(cancel)
        samples = bytearray(texture.data)
        runtime_tiles = [dict(tile) for tile in tiles]
        for (position, old, number), variant in zip(lugia, combination, strict=True):
            encoded = _tile_art(template, variants[variant], 64, 64, number,
                rect=_CUSTOM_BODY_ART_RECT if variant < 2 else _BODY_ART_RECT)
            for row, (start, end) in enumerate(_tile_rows(*_TILE_ORIGINS[position])):
                samples[start - 0x7820:end - 0x7820] = encoded[row * 512:(row + 1) * 512]
            tile = next(tile for tile in runtime_tiles if tile["position"] == position)
            if variant < 2:
                tile["body"] = {"kind": "rendered-dark-lugia", "shiny": bool(variant),
                                "native_width": 64, "native_height": 64,
                                "native_rgba_sha256": hashlib.sha256(variants[variant]).hexdigest(),
                                "native_art_rect": list(_CUSTOM_BODY_ART_RECT)}
            else:
                native = _raw_member(bodies, body_members["body249_c" if variant == 3 else "body249"])
                tile["body"] = _body_donor(native)
        runtime = _Texture(1024, 1024, 14, bytes(samples))
        key = _texture_key(runtime)
        if key not in recipes:
            textures.append(runtime)
            runtime_transform = dict(transform, tiles=runtime_tiles, runtime_lugia_states=list(combination))
            recipes[key] = dict(origin, transform=runtime_transform)
    return textures, recipes


def _dna_cell_variants(raw: bytes, layout_report: dict, reference_iso: Path, context: Mapping, cancel):
    """Register each independent native cell; variant counts are additive."""
    from .engine.dna_hd_tiles import _validated_layout
    from .engine.dna_keypad import _tile_art, _tile_rows, _body_pixels, _BODY_ART_RECT, _CUSTOM_BODY_ART_RECT
    from .engine.shadow_lugia_body import shadow_lugia_body_pixels
    from .engine.spinda import SPINDA
    from .artwork import _disc_files
    layout = _validated_layout(layout_report)
    if (len(raw) != layout["new_dat_size"] or u32(raw, 0x1C) != layout["magic"] or
            struct.unpack_from(">II", raw) != (layout["new_dat_size"], layout["new_data_size"])):
        raise OverlayError("Independent DNA texture buffers do not match their native contract.")
    atlas = _Texture(1024, 1024, 14, raw[0x7820:0x87820])
    _, atlas_recipes = _dna_variants(atlas, reference_iso, context, cancel)
    base_recipe = atlas_recipes.get(_texture_key(atlas))
    mapping = context.get("dna_lab", {})
    if base_recipe is None and mapping:
        raise OverlayError("Independent DNA cells lack an exact native composition recipe.")
    tiles = base_recipe["transform"]["tiles"] if base_recipe else []
    native_lugia_variants = template = None
    if any(tile["species"] == 249 for tile in tiles):
        files = _disc_files(reference_iso, {"DNA_key.fsys", "poke_body.fsys"})
        original = files["DNA_key.fsys"]
        dat = _raw_member(original, next(m for m in parse_fsys(original)["members"]
                                        if m["identifier_raw"] == "0x107e0200"))
        template = _decode_pixels(128, 128, 4, b"".join(dat[a:b] for a, b in _tile_rows(896, 512)))
        bodies = files["poke_body.fsys"]
        members = {m["name"]: m for m in parse_fsys(bodies)["members"]}
        native_lugia_variants = (shadow_lugia_body_pixels(False), shadow_lugia_body_pixels(True),
                                _body_pixels(bodies, members, 249, False), _body_pixels(bodies, members, 249, True))
        retail_lugia = (_body_donor(_raw_member(bodies, members["body249"])),
                        _body_donor(_raw_member(bodies, members["body249_c"])))
    textures, recipes = [], {}
    for cell in layout["cells"]:
        _checkpoint(cancel)
        descriptor = struct.unpack_from(">IHHII", raw, cell["image_descriptor_file_offset"])
        if descriptor != (cell["data_offset"], cell["width"], cell["height"], 14, 0):
            raise OverlayError("Independent DNA image descriptor changed.")
        samples = raw[cell["file_offset"]:cell["file_offset"] + cell["bytes"]]
        tile = next((tile for tile in tiles if tile["position"] == cell["screen_index"]), None)

        def register(data, selected, variant=None):
            texture = _Texture(cell["width"], cell["height"], 14, bytes(data))
            transform = {"type": "dna_cell", "cell": {name: cell[name] for name in
                ("screen_index", "crop_x", "crop_y", "width", "height", "art_x", "art_y", "art_size")},
                "tile": selected, "runtime_lugia_state": variant}
            if (selected and selected["species"] == SPINDA
                    and (not layout.get("spinda_diagram") or
                         cell["original_species"] not in layout["spinda_diagram"]["samples"])):
                transform["runtime_gap"] = "The independent Spinda cell still requires specimen PID HD spot rendering."
            key = _texture_key(texture)
            if key not in recipes:
                textures.append(texture)
                recipes[key] = {"game": "colosseum", "file": "tex1_1024x1024_57c039ae574254a7_14.png",
                                "source_native_dimensions": [1024, 1024],
                                "native_source": "verified original DNA keypad UI with independent native UV cell",
                                "transform": transform}

        register(samples, tile)
        if tile and tile["species"] == SPINDA and layout.get("spinda_diagram"):
            from .engine.dna_spinda_hd import body_variants
            selected_cell = next((row for row in layout["spinda_diagram"]["cells"]
                                  if row["screen_index"] == cell["screen_index"]), None)
            if selected_cell is None:
                raise OverlayError("Spinda body has no qualified saved-identity cell.")
            references = _disc_files(reference_iso, {"DNA_key.fsys", "poke_body.fsys"})
            expected_bodies = body_variants(raw, cell, references["DNA_key.fsys"], references["poke_body.fsys"], tile["number"])
            body_members = {m["name"]: m for m in parse_fsys(references["poke_body.fsys"])["members"]}
            for shiny, (offset, expected_body) in enumerate(zip(selected_cell["body_data_offsets"], expected_bodies)):
                native_body = raw[offset + 32:offset + 32 + cell["bytes"]]
                if native_body != expected_body:
                    raise OverlayError("Spinda body variant differs from its exact original body artwork.")
                donor = _body_donor(_raw_member(references["poke_body.fsys"], body_members["body308_c" if shiny else "body308"]))
                register(native_body, dict(tile, shiny=bool(shiny), body=donor), variant=f"spinda-body-{shiny}")
        if tile and tile["species"] == 249:
            # All four actual appearances have finite independent keys. Saved
            # state combinations across other cells no longer multiply them.
            for variant, body in enumerate(native_lugia_variants):
                encoded = _tile_art(template, body, 64, 64, tile["number"],
                    rect=_CUSTOM_BODY_ART_RECT if variant < 2 else _BODY_ART_RECT)
                changed = bytearray(samples)
                for row in range(16):
                    start = (cell["art_y"] // 8 + row) * cell["row_bytes"] + cell["art_x"] // 8 * 32
                    changed[start:start + 512] = encoded[row * 512:(row + 1) * 512]
                selected = dict(tile)
                selected["body"] = ({"kind": "rendered-dark-lugia", "shiny": bool(variant),
                                      "native_width": 64, "native_height": 64,
                                      "native_rgba_sha256": hashlib.sha256(body).hexdigest(),
                                      "native_art_rect": list(_CUSTOM_BODY_ART_RECT)} if variant < 2 else retail_lugia[variant - 2])
                register(changed, selected, variant)
        if tile and tile['species'] == 410 and 'deoxys_form' in tile:
            from .engine.dna_deoxys_keypad import native_tile_variants
            references = _disc_files(reference_iso, {'DNA_key.fsys', 'poke_body.fsys'})
            old = cell['original_species']
            appearance_map = {int(key): (row['species'], row['shiny']) for key, row in mapping.items()}
            all_tiles = native_tile_variants(references.__getitem__, appearance_map, {old: None})[old]
            bodies = references['poke_body.fsys']
            members = {m['name']: m for m in parse_fsys(bodies)['members']}
            for variant, encoded in enumerate(all_tiles):
                changed = bytearray(samples)
                for row in range(16):
                    start = (cell['art_y'] // 8 + row) * cell['row_bytes'] + cell['art_x'] // 8 * 32
                    changed[start:start + 512] = encoded[row * 512:(row + 1) * 512]
                selected_form, shiny = variant // 2, bool(variant & 1)
                donor = (_deoxys_body_origin(selected_form, shiny) if selected_form else
                         _body_donor(_raw_member(bodies, members['body410_c' if shiny else 'body410'])))
                register(changed, dict(tile, shiny=shiny, deoxys_form=selected_form, body=donor),
                         variant=f'deoxys-{selected_form}-{int(shiny)}')
    if layout.get("spinda_diagram"):
        extra_textures, extra_recipes = _spinda_diagram_variants(raw, layout, reference_iso, cancel)
        textures.extend(extra_textures)
        recipes.update(extra_recipes)
        spec = layout["spinda_diagram"]
        frozen = spec["frozen_case_atlas_data_offset"] + 32
        pixels = raw[frozen:frozen + spec["frozen_case_atlas_bytes"]]
        if pixels != raw[0x7820:0x87820]:
            raise OverlayError("Frozen DNA case pixels differ from the initial native atlas.")
        ui = _Texture(1024, 1024, 14, pixels)
        key = _texture_key(ui)
        textures.append(ui)
        recipes[key] = {"game": "colosseum", "file": "tex1_1024x1024_57c039ae574254a7_14.png",
            "source_native_dimensions": [1024, 1024],
            "native_source": "immutable DNA case atlas; all nine key ART materials use separate buffers",
            "uv_contract": {"case_max_u": 0.6845703125, "art_min_u": 736 / 1024,
                            "descriptors": spec["frozen_case_image_descriptor_file_offsets"]},
            "transform": {"type": "identity"}}
    return textures, recipes


def _spinda_diagram_variants(raw: bytes, layout: dict, reference_iso: Path, cancel):
    """Bind every finite per-byte layer to audited native bank bytes."""
    from .artwork import _disc_files
    from .engine.actor_palette import pkx_recipe
    from .engine.spinda_diagram import native_bank, TEXTURE_BYTES, TEXTURE_SIZE
    from .hd_spinda_diagram import DONOR
    spec = layout["spinda_diagram"]
    source = _disc_files(reference_iso, {"pkx_patcheel.fsys"})["pkx_patcheel.fsys"]
    members = {m["name"]: m for m in parse_fsys(source)["members"]}
    face, spot, model = (_raw_member(source, members[name]) for name in ("face", "buti_a", "patcheel"))
    bank, info = native_bank(face, spot, pkx_recipe(model, xd=False))
    start = spec["bank_data_offset"] + 32
    if (len(raw) != layout["new_dat_size"] or spec["bank_bytes"] != len(bank)
            or raw[start:start + len(bank)] != bank):
        raise OverlayError("The independent Spinda mask bank differs from verified ROM sources.")
    for selected in spec["cells"]:
        for desc in selected["image_descriptors"]:
            if struct.unpack_from(">IHHII", raw, desc + 32) != (spec["empty_data_offset"], 40, 40, 14, 0):
                raise OverlayError("Unexpected initial Spinda diagram texture binding.")
    textures, recipes = [], {}
    variants = [(spec["empty_data_offset"], {"layer": "empty", "shiny": False})]
    for shiny in range(2):
        variants.append((spec["background_data_offsets"][shiny], {"layer": "background", "shiny": bool(shiny)}))
        for index in range(4):
            for value in range(256):
                variants.append((spec["spot_data_offsets"][shiny][index] + value * TEXTURE_BYTES,
                    {"layer": "spot", "shiny": bool(shiny), "spot": index, "pid_byte": value}))
    for offset, transform in variants:
        _checkpoint(cancel)
        samples = raw[offset + 32:offset + 32 + TEXTURE_BYTES]
        texture = _Texture(TEXTURE_SIZE, TEXTURE_SIZE, 14, samples)
        key = _texture_key(texture)
        if key in recipes:
            raise OverlayError("Two distinct Spinda byte layers share one native texture identity.")
        textures.append(texture)
        recipes[key] = {"game": "colosseum", "file": DONOR,
            "source_native_dimensions": [128, 128],
            "native_source": "verified Spinda per-byte diagram mask with invisible clamp-rim identity",
            "native_bank_sha256": info["sha256"],
            "transform": {"type": "spinda_diagram_layer", **transform}}
    return textures, recipes


def capture_native_assets(iso: Path, destination: Path, *, is_xd: bool = False,
                           reference_iso: Path | None = None, asset_context: Mapping | None = None,
                           cancel: Event | None = None,
                           progress: Callable[[str], None] | None = None) -> dict:
    """Persist compact native references while the generated ISO is available.

    Works offline without HD packs. The ROM already contains the normal
    version. This manifest is the mandatory second-version contract: every
    asset either declares its actual HD donor recipe or has a blocking gap.
    Later preparation needs these references and packs, never the source ISO.
    """
    source, target = Path(iso).resolve(), Path(destination)
    if target.is_symlink():
        raise OverlayError("Overlay destination cannot be a symbolic link.")
    target = target.resolve()
    if source == target or source.is_relative_to(target):
        raise OverlayError("Overlay destination overlaps the source ISO.")
    report = {"version": VERSION, "schema": 2, "scale": 4, "game": "xd" if is_xd else "colosseum",
              "contract": "native-game-and-pack-derived-hd-v2", "kind": "native asset references",
              "contract_requirements": {
                  "mandatory_for_new_models": True,
                  "native": "ROM-derived mesh, materials, portrait and separate whole-body artwork",
                  "hd": "Pinned-pack images with registered native keys, authored HD material recipes and mesh renders",
                  "new_routes": "Register every new model/portrait/body/runtime texture route before enabling HD",
                  "missing_donor": "Block HD readiness; never substitute a filtered native image"},
              "mesh_geometry_changed": False, "hd_ready": False, "resources": [], "assets": [],
              "files": [], "texture_count": 0, "required_packs": [], "missing_assets": [],
              "limitations": [],
              "conditional_limitations": ["PID-specific Spinda DNA requires a registered HD spot-pattern recipe when selected."]}
    assets, dna_recipes, castform_game = {}, {}, None
    context_forms = (asset_context or {}).get('deoxys_forms', {})
    imported_deoxys = (not is_xd and isinstance(context_forms, Mapping)
                       and context_forms.get('enabled') is True)
    deoxys = None
    try:
        _checkpoint(cancel)
        if imported_deoxys:
            deoxys = deoxys_hd_contract()
            report['deoxys_forms'] = dict(deoxys)
            report['required_packs'].append('xd')
        extra = {'pkx_deoxys.fsys', 'pkx_rare_deoxys.fsys'} if imported_deoxys else None
        for archive_name, archive in _disc_archives(source, is_xd=is_xd, extra_names=extra):
            _checkpoint(cancel)
            if progress:
                progress(archive_name)
            if u32(archive, 0xC) > 4096:
                raise OverlayError("Custom archive directory exceeds limits.")
            for member in parse_fsys(archive)["members"]:
                role = _selected(archive_name, member, is_xd)
                if role is None:
                    continue
                if role in _DEOXYS_ROLES and deoxys is None:
                    raise OverlayError('Imported Deoxys resources require their native/HD contract')
                _checkpoint(cancel)
                raw = _raw_member(archive, member)
                if role in ("portrait", "retail_portrait", "retail_form", "castform_portrait", "deoxys_portrait"):
                    textures = (_face(raw),)
                elif role in ("battle", "castform_battle", "deoxys_battle"):
                    textures = _dat_textures(_pkx_dat(raw, is_xd))
                elif role == "dna":
                    # The complete atlas preserves all nine full-body tiles,
                    # including static custom dark/shiny Lugia compositions.
                    if len(raw) < 0x87820 or struct.unpack_from(">III", raw, 0x45B0) != (0x7800, 0x04000400, 14):
                        raise OverlayError("Unexpected native DNA atlas.")
                    if asset_context and asset_context.get("dna_hd_layout"):
                        textures, recipes = _dna_cell_variants(raw, asset_context["dna_hd_layout"],
                            Path(reference_iso or source), asset_context, cancel)
                    else:
                        atlas = _Texture(1024, 1024, 14, raw[0x7820:0x87820])
                        textures, recipes = _dna_variants(atlas, Path(reference_iso or source), asset_context, cancel)
                    dna_recipes.update(recipes)
                else:
                    textures = _dat_textures(raw)
                record = {"archive": archive_name, "member": member["name"],
                          "resource": member["identifier_raw"], "role": role,
                          "source_sha256": hashlib.sha256(raw).hexdigest(), "textures": []}
                for texture in textures:
                    _checkpoint(cancel)
                    pixels = _pixels(texture)
                    reference = _native_reference(target, pixels, texture.width, texture.height)
                    for mipmaps in ((False, True) if texture.mipmaps else (False,)):
                        name = dolphin_texture_name(texture.width, texture.height, texture.fmt, texture.data,
                                                    palette=texture.palette, mipmaps=mipmaps) + ".png"
                        if name not in assets:
                            if len(assets) >= _MAX_TEXTURES:
                                raise OverlayError("Custom texture output exceeds limits.")
                            assets[name] = {"file": name, "native": reference, "role": role,
                                            "native_format": texture.fmt, "base_key": _texture_key(texture)}
                        elif assets[name]["native"]["sha256"] != reference["sha256"]:
                            raise OverlayError("One Dolphin texture name has conflicting native palette interpretations.")
                        if role in _CASTFORM_ROLES:
                            castform_game = castform_game or _castform_game_id(source, is_xd)
                            roles = assets[name].setdefault("castform_roles", [])
                            if role not in roles:
                                roles.append(role)
                        if role in _DEOXYS_ROLES:
                            roles = assets[name].setdefault('deoxys_roles', [])
                            if role not in roles:
                                roles.append(role)
                        record["textures"].append(name)
                report["resources"].append(record)
        _checkpoint(cancel)
        origins = _dark_origins()
        wanted = ({a["base_key"] for a in assets.values() if a["role"] == "field"} - origins.keys()
                  - set(deoxys['material_keys'] if deoxys else []))
        field, failures = _field_origins(Path(reference_iso or source), is_xd, wanted, cancel, progress) if wanted else ({}, [])
        origins.update(field)
        report["origin_scan_failures"] = failures
        from .artwork import _png_pixels
        bundle = Path(__file__).resolve().parent / "assets/game/models/dark-lugia.png"
        portrait_reference = None
        for asset in assets.values():
            base = asset["base_key"]
            if asset.get("castform_roles"):
                native_image = _load_reference(target, asset["native"])
                asset["hd"], gap = _castform_hd_origin(castform_game, asset, bytes(native_image.constBits()))
                if gap:
                    report["missing_assets"].append({"file": asset["file"], "reason": gap})
                # The custom route is explicit even when one white/grey texture
                # also appeared in another captured resource earlier.
                if "colosseum" not in report["required_packs"]:
                    report["required_packs"].append("colosseum")
            elif deoxys and (asset.get('deoxys_roles') or base in deoxys['material_keys']):
                native_image = _load_reference(target, asset['native'])
                asset['hd'] = _deoxys_origin(asset, deoxys, bytes(native_image.constBits()))
                if asset['hd'] is None:
                    raise OverlayError('An imported Deoxys texture has no complete registered HD route')
                if asset['role'] == 'field':
                    asset.setdefault('deoxys_roles', []).append('deoxys_field')
            elif asset["role"] == "retail_form":
                from .hd_extra_portraits import portrait_origin
                asset["hd"] = portrait_origin(report["game"], base,
                    (asset["native"]["width"], asset["native"]["height"]))
                if asset["hd"] is None:
                    raise OverlayError("The additional portrait has an unknown or changed native identity.")
            elif asset["role"] == "retail_portrait":
                from .hd_portraits import ordinary_portrait_origin
                resource = next(r for r in report["resources"] if asset["file"] in r["textures"])
                asset["hd"] = ordinary_portrait_origin(resource["member"], base,
                    (asset["native"]["width"], asset["native"]["height"]))
            elif asset["role"] == "portrait":
                if portrait_reference is None:
                    pixels = _png_pixels(bundle.read_bytes(), (42, 42))
                    portrait_reference = _native_reference(target, pixels, 42, 42)
                resource = next(r["resource"] for r in report["resources"] if asset["file"] in r["textures"])
                asset["hd"] = {"game": "xd", "file": "tex1_64x64_830778f52c6de2c0_44fccd7f7f60660f_9.png",
                               "source_native_dimensions": [64, 64],
                               "native_source": "accepted head render from original XD001 model and complete HD material set",
                               "transform": {"type": "shadow_lugia_portrait", "game": report["game"],
                                             "shiny": resource == "0x7df51200", "reference": portrait_reference}}
            elif base in dna_recipes:
                asset["hd"] = dna_recipes[base]
            elif asset["role"] == "dna" and base == "tex1_1024x1024_57c039ae574254a7_14.png":
                asset["hd"] = {"game": "colosseum", "file": base,
                               "native_source": "original DNA keypad atlas",
                               "transform": {"type": "identity"}}
            elif base in origins:
                asset["hd"] = origins[base]
                if (asset["role"] in ("field", "battle") and origins[base]["file"] == base and
                        origins[base]["transform"]["type"] == "identity"):
                    asset["classification"] = "inherited_stock"
            elif asset["role"] in ("field", "battle"):
                # Exact key lookup remains trustworthy even if its native
                # archive route was not one of the indexed battle donors.
                native_image = _load_reference(target, asset["native"])
                colors = bytes(native_image.constBits())
                if colors == colors[:4] * (len(colors) // 4):
                    asset["hd"] = {"transform": {"type": "constant-color", "rgba": list(colors[:4])}}
                    report["assets"].append(asset)
                    continue
                asset["hd"] = {"game": report["game"], "file": base,
                               "native_source": "exact target texture identity",
                               "transform": {"type": "identity"}}
            else:
                asset["hd"] = None
                report["missing_assets"].append({"file": asset["file"], "reason": "No registered pack-derived DNA composition"})
            if not asset.get("castform_roles") and not asset.get('deoxys_roles') and asset["role"] in ("field", "battle"):
                native_image = _load_reference(target, asset["native"])
                colors = bytes(native_image.constBits())
                if colors == colors[:4] * (len(colors) // 4):
                    asset["hd"] = {"transform": {"type": "constant-color", "rgba": list(colors[:4])}}
            if asset["hd"]:
                game = asset["hd"].get("game")
                if game and game not in report["required_packs"]:
                    report["required_packs"].append(game)
                if asset["hd"]["transform"]["type"] in ("dna", "dna_cell"):
                    transform = asset["hd"]["transform"]
                    nested = transform["tiles"] if transform["type"] == "dna" else [transform["tile"]] if transform["tile"] else []
                    for tile in nested:
                        body = tile["body"]
                        game = "xd" if body["kind"] in ('rendered-dark-lugia', 'rendered-deoxys') else body["game"]
                        if game not in report["required_packs"]:
                            report["required_packs"].append(game)
            report["assets"].append(asset)
        report["asset_count"] = len(assets)
        report["texture_count"] = len(assets)
        if castform_game:
            report["castform_shinies"] = {"version": 1, "game_id": castform_game,
                "resources": sum(row["role"] in _CASTFORM_ROLES for row in report["resources"]),
                "texture_keys": sorted(row["file"] for row in report["assets"] if row.get("castform_roles")),
                "native_rgba_bound": True}
        if deoxys:
            from .deoxys_resources import MODEL_RESOURCES, FACE_RESOURCES
            found = {int(row['resource'], 16) for row in report['resources'] if row['role'] in _DEOXYS_ROLES}
            if found != set(MODEL_RESOURCES.values()) | set(FACE_RESOURCES.values()):
                raise OverlayError('The imported Deoxys model/portrait resource set is incomplete')
            report['deoxys_forms'].update(resources=len(found),
                texture_keys=sorted(row['file'] for row in report['assets'] if row.get('deoxys_roles')))
        if any(row["role"] == "retail_form" for row in report["resources"]):
            from .hd_extra_portraits import portrait_coverage_report
            report["additional_portraits"] = {**portrait_coverage_report(),
                "captured_atlases": sum(row["role"] == "retail_form" for row in report["resources"])}
        if is_xd:
            from .hd_portraits import portrait_coverage_report
            report["portrait_transfer"] = {**portrait_coverage_report(),
                "captured_atlases": sum(row["role"] == "retail_portrait" for row in report["resources"])}
        report["limitations"] = _runtime_limitations(report["assets"])
        target.mkdir(parents=True, exist_ok=True)
        _write(target / _MANIFEST, (json.dumps(report, indent=2, ensure_ascii=True) + "\n").encode())
        return report
    except (OverlayError, InterruptedError):
        raise
    except (OSError, ArtworkError, FormatError, ValueError, struct.error, RuntimeError) as error:
        raise OverlayError("Custom native texture extraction failed.") from error


def _load_reference(root: Path, record: dict):
    from PySide6.QtGui import QImage
    path = root / record["file"]
    if (path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or
            hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]):
        raise OverlayError("Native asset reference changed.")
    image = QImage(str(path))
    if image.isNull() or (image.width(), image.height()) != (record["width"], record["height"]):
        raise OverlayError("Invalid native asset reference.")
    return image.convertToFormat(QImage.Format.Format_RGBA8888)


def _runtime_limitations(assets: list[dict]) -> list[str]:
    return sorted({gap for asset in assets if asset.get("hd")
                   if isinstance(gap := asset["hd"]["transform"].get("runtime_gap"), str) and gap})


def _resolve_hd(pack: Path, logical_name: str) -> Path | None:
    """Resolve a native logical key independently of the pack's container."""
    from .hd_images import resolve_texture
    try:
        return resolve_texture(pack / "Textures", logical_name)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise OverlayError("The HD donor identity is invalid or ambiguous.") from error


def _load_hd(path: Path, native_size: tuple[int, int]):
    from .hd_images import load_texture
    try:
        loaded = load_texture(path, expected_native_size=native_size, max_scale=16)
    except (OSError, ValueError) as error:
        raise OverlayError("The HD donor image cannot be decoded safely.") from error
    if loaded.metadata["source_scale"] not in (2, 4, 8, 16):
        raise OverlayError("The HD donor has no supported genuine high-resolution source.")
    return loaded


def _inherited_stock(asset: dict, origin: dict) -> bool:
    if origin["file"] in _LUGIA_RECONSTRUCTED_MATERIALS:
        return False  # These authored HD materials are mandatory, never a stock fallback.
    if (origin["transform"]["type"] != "identity" or origin["file"] != asset["base_key"]
            or not origin.get("native_model_sha256") or not origin.get("native_texture_sha256")):
        return False
    if asset["role"] == "field":
        from .xd_shadow_lugia_model import _FIELD_SHA256
        from .engine.postgame_lugia_model import verified_model_asset
        _, model = verified_model_asset()
        if origin["native_model_sha256"] in (*_FIELD_SHA256.values(), model["source"]["model_sha256"]):
            return False  # Custom field Lugia requires all maps, including unchanged eyes.
        return asset.get("native_classification", asset.get("classification")) == "inherited_stock"
    if asset["role"] == "battle":
        return False  # Every material of the authored battle model needs HD.
    return False


def _lugia_material_reconstruction(origin: dict, pack: Path):
    """Render native UV symbols and the reflection environment analytically.

    The original 16/32px images provide topology/UV landmarks only. Output
    pixels are evaluated at x4 from continuous functions and colours sampled
    from the selected pack's actual belly/eye images. The HSD reflection
    projection, UVs, alpha, material colours and specular state stay native.
    HSD TEX_COORD_REFLECTION=1 is documented in doldecomp/melee tobj.h/c.
    """
    from PySide6.QtGui import QImage
    from .engine.postgame_lugia_model import verified_model_asset
    specification = _LUGIA_RECONSTRUCTED_MATERIALS.get(origin["file"])
    if specification is None:
        return None
    native_size, tobj, material, flags, role = specification
    model, native_provenance = verified_model_asset()
    dat = model[0x40:]
    data = dat[32:32 + u32(dat, 4)]
    if u32(data, tobj + 0x40) != flags:
        raise OverlayError("Shadow Lugia material projection changed.")
    color_pointer = u32(data, material + 12)
    color = data[color_pointer:color_pointer + 12]
    expected = (bytes.fromhex("191933ff666680ff595973ff") if role == "reflection-environment" else
                bytes.fromhex("808080ffffffffff000000ff") if role == "tongue-and-teeth" else
                bytes.fromhex("808080ffffffffffffffffff"))
    if color != expected:
        raise OverlayError("Shadow Lugia native lighting/specular material changed.")
    keys = ("tex1_32x32_afade9df5d7d12c3_14.png", "tex1_64x64_830778f52c6de2c0_44fccd7f7f60660f_9.png")
    references = []
    loaded = []
    for key, dimensions in zip(keys, ((32, 32), (64, 64)), strict=True):
        path = _resolve_hd(pack, key)
        if path is None:
            raise _MissingHDAsset("A required independent HD palette donor for Lugia is absent.")
        source = _load_hd(path, dimensions)
        loaded.append(source)
        references.append({"file": key, **source.metadata})
    anchors = {}

    def pick(source, label, quantile, predicate=lambda r, g, b: True):
        image = source.image
        rgba = bytes(image.constBits())
        candidates = [(tuple(rgba[i:i + 3]), i // 4) for i in range(0, len(rgba), 4)
                      if rgba[i + 3] >= 230 and predicate(*rgba[i:i + 3])]
        if len(candidates) < 8:
            raise _MissingHDAsset("The independent HD Lugia donor lacks its material palette.")
        candidates.sort(key=lambda item: 2126 * item[0][0] + 7152 * item[0][1] + 722 * item[0][2])
        rgb, index = candidates[round(quantile * (len(candidates) - 1))]
        anchors[label] = {"rgb": list(rgb), "pixel": [index % image.width(), index // image.width()],
                          "physical_file": source.metadata["physical_file"], "quantile": quantile}
        return rgb

    ivory = pick(loaded[0], "ivory", .96)
    mid = pick(loaded[0], "neutral-mid", .35)
    red = lambda r, g, b: r > 90 and r > g + 35 and r > b + 25
    iris = pick(loaded[1], "iris-red", .55, red)
    dark_iris = pick(loaded[1], "iris-shadow", .12, red)
    bright_iris = pick(loaded[1], "iris-light", .88, red)

    def oral(rgb, saturation, value):
        _, s, v = colorsys.rgb_to_hsv(*(component / 255 for component in rgb))
        return tuple(round(component * 255) for component in colorsys.hsv_to_rgb(.92, s * saturation, v * value))

    mouth, cavity, tongue = oral(iris, .70, .46), oral(dark_iris, .70, .25), oral(bright_iris, .40, .60)

    def smooth(first, last, value):
        t = max(0., min(1., (value - first) / (last - first)))
        return t * t * (3 - 2 * t)

    def blend(first, second, amount):
        return tuple(a + (b - a) * amount for a, b in zip(first, second))

    width = height = native_size * 4
    pixels = bytearray(width * height * 4)
    for y in range(height):
        v = (y + .5) / height
        for x in range(width):
            u = (x + .5) / width
            if role == "reflection-environment":
                sky = (.72 - .48 * math.exp(-.5 * ((v - .72) / .09) ** 2)
                       - .18 * smooth(.84, 1., v) + .06 * math.exp(-.5 * ((v - .30) / .18) ** 2))
                base = tuple(channel * sky for channel in ivory)
                left = math.exp(-.5 * (((u - .21) / .105) ** 4 + ((v - .26) / .065) ** 4))
                right = math.exp(-.5 * (((u - .75 + .15 * (v - .28)) / .085) ** 2 + ((v - .28) / .12) ** 4))
                rgb = blend(base, ivory, min(1., .92 * left + .88 * right))
            elif role == "mouth-interior":
                if u < 1 / 16 or u > 15 / 16 or v < 1 / 16:
                    rgb = ivory  # Exact UV gutters/frame; no altered polygon or alpha.
                else:
                    arch = .035 + .27 * smooth(.35, 1., v)
                    depth = smooth(-.02, .025, arch - abs(u - .5)) * smooth(.30, .70, v)
                    palate = .18 * math.exp(-.5 * (((u - .5) / .30) ** 2 + ((v - .30) / .18) ** 2))
                    rgb = blend(blend(mouth, tongue, palate), cavity, depth)
            else:
                glow = .75 * math.exp(-.5 * (((u - .74) / .14) ** 2 + ((v - .34) / .40) ** 2))
                rgb = blend(mouth, tongue, glow)
                shade = .65 * math.exp(-.5 * (((u - .43) / .19) ** 2 + ((v - .97) / .12) ** 2))
                rgb = blend(rgb, cavity, shade)
                tooth = (1 - smooth(.285, .325, u)) * (1 - smooth(.74, .96, v))
                tooth_color = blend(ivory, mid, .80 * smooth(0., .82, v))
                rgb = blend(rgb, tooth_color, tooth)
            at = (y * width + x) * 4
            pixels[at:at + 4] = bytes((*[max(0, min(255, round(c))) for c in rgb], 255))
    image = QImage(bytes(pixels), width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
    return image, {"kind": "authored-hd-lugia-material", "hd_art_revision": 2, "recipe_version": 1,
                   "reference": references[0], "references": references, "palette": anchors,
                   "native_uv_guide": origin["file"], "native_model_sha256": native_provenance["source"]["model_sha256"],
                   "material": {"role": role, "tobj_flags": f"0x{flags:08x}", "native_colors": color.hex(),
                                "projection": "HSD normal-vector reflection" if flags & 15 == 1 else "native UV0",
                                "specular_unchanged": True, "alpha": "opaque native material retained"},
                   "construction": "continuous environment/UV vector functions; no native pixel grid is enlarged",
                   "oral_tint": {"native_hue": .92, "source": "independent same-model HD iris palette"},
                   "native_bitmap_resampled": False}


def native_asset_manifest(directory: Path) -> dict:
    """Load the persisted v2 dual-version contract without a source ROM."""
    path = Path(directory) / _MANIFEST
    if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise OverlayError("Invalid native/HD asset manifest.")
    report = json.loads(path.read_text("utf-8"))
    if (report.get("schema") != 2 or report.get("version") != VERSION or
            report.get("contract") != "native-game-and-pack-derived-hd-v2" or
            not isinstance(report.get("assets"), list) or len(report["assets"]) > _MAX_TEXTURES):
        raise OverlayError("Native/HD asset contract is missing or obsolete.")
    for asset in report["assets"]:
        if (not isinstance(asset, dict) or not isinstance(asset.get("file"), str) or
                not re.fullmatch(r"tex1_\d+x\d+(?:_m)?_[0-9a-f]{16}(?:_[0-9a-f]{16})?_\d+\.png", asset["file"])):
            raise OverlayError("Invalid dual-version texture filename.")
        native = asset.get("native", {})
        if (not isinstance(native, dict) or
                not isinstance(native.get("file"), str) or not isinstance(native.get("sha256"), str) or
                not re.fullmatch(r"NativeReferences/[0-9a-f]{64}\.png", native.get("file", "")) or
                not re.fullmatch(r"[0-9a-f]{64}", native.get("sha256", "")) or
                any(type(native.get(axis)) is not int or not 1 <= native[axis] <= 1024 for axis in ("width", "height"))):
            raise OverlayError("Invalid native asset reference record.")
    return report


def _recolor_hd(image, transform):
    from PySide6.QtGui import QImage
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if transform["type"] == "identity":
        return image
    pixels = bytearray(image.constBits())
    for at in range(0, len(pixels), 4):
        rgba = tuple(pixels[at:at + 4])
        if transform["type"] == "shadow_lugia_belly":
            pixels[at:at + 3] = bytes(round(rgba[i] * transform["factors"][i]) for i in range(3))
        elif transform["type"] == "pkx_recipe":
            pixels[at:at + 3] = bytes(min(255, (rgba[transform["route"][i]] * (transform["gain"][i] + 1) + 64) // 128)
                                          for i in range(3))
        else:
            raise OverlayError("Unknown pack-derived recolouring recipe.")
    return QImage(bytes(pixels), image.width(), image.height(), image.width() * 4,
                  QImage.Format.Format_RGBA8888).copy()


def _authored_material_retouch(origin: dict, pack: Path):
    """Paint two missing material ramps from actual HD material colours.

    These are explicitly authored replacements, not upstream replacements or
    enlarged native bitmaps. Only the native UV axis/profile guides the new
    vector ramp. Every colour anchor is an observed pixel in that Pokémon's
    real pinned HD full-body reference. The later retail shiny recipe still
    performs the native channel routing and gain.
    """
    from PySide6.QtGui import QImage
    sources = {
        "tex1_64x2_d3688e7d5cede59d_1a3985ee4c048206_9.png":
            ("umbreon", "tex1_64x64_48fd3f1e8b93d316_5.png", 256, 8),
        "tex1_4x128_36d63a98aaf32ef5_4e7976d58c0ec12c_9.png":
            ("espeon", "tex1_64x64_6cc4941878e8e47c_5.png", 16, 512),
    }
    specification = sources.get(origin["file"])
    if specification is None:
        return None
    species, reference_name, width, height = specification
    path = _resolve_hd(pack, reference_name)
    if path is None:
        return None
    loaded = _load_hd(path, (64, 64))
    reference = loaded.image
    rgba = bytes(reference.constBits())
    available = [(tuple(rgba[at:at + 3]), (at // 4 % reference.width(), at // 4 // reference.width()))
                 for at in range(0, len(rgba), 4) if rgba[at + 3] >= 230]
    palette = {}

    def pick(label, predicate, quantile):
        candidates = [(color, xy) for color, xy in available if predicate(*color)]
        if len(candidates) < 8:
            raise _MissingHDAsset("The HD material reference lacks the reviewed palette anchors.")
        candidates.sort(key=lambda item: 2126 * item[0][0] + 7152 * item[0][1] + 722 * item[0][2])
        color, xy = candidates[round((len(candidates) - 1) * quantile)]
        palette[label] = {"rgb": list(color), "pixel": list(xy), "quantile": quantile,
                          "eligible_pixels": len(candidates)}
        return color

    highlight = pick("highlight", lambda r, g, b: min(r, g, b) >= 200 and max(r, g, b) - min(r, g, b) <= 25, .65)
    if species == "umbreon":
        shadow = pick("body_shadow", lambda r, g, b: 15 < min(r, g, b) and max(r, g, b) < 90
                      and max(r, g, b) - min(r, g, b) <= 18, .65)
        gold = pick("gold_rings", lambda r, g, b: r >= 100 and g >= 75 and r > b * 1.5 and g > b * 1.3, .65)
        axis = "u"
        stops = [(0., shadow), (.38, gold), (.515, highlight), (.65, gold), (1., shadow)]
    else:
        purple = lambda r, g, b: r > g + 5 and b > g + 10 and r + g + b > 240
        shadow = pick("purple_shadow", purple, .12)
        body = pick("purple_body", purple, .65)
        light = pick("purple_light", purple, .85)
        axis = "v"
        stops = [(0., light), (.34, shadow), (.73, body), (1., highlight)]
    pixels = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            coordinate = x / (width - 1) if axis == "u" else y / (height - 1)
            for (first, start), (last, end) in zip(stops, stops[1:]):
                if first <= coordinate <= last:
                    amount = (coordinate - first) / (last - first)
                    amount = amount * amount * (3 - 2 * amount)
                    color = tuple(round(a + (b - a) * amount) for a, b in zip(start, end))
                    break
            at = (y * width + x) * 4
            pixels[at:at + 4] = bytes((*color, 255))
    image = QImage(bytes(pixels), width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
    return image, {"kind": "authored-hd-material-retouch", "recipe_version": 1,
                   "reference": {"file": reference_name, **loaded.metadata,
                                 "dimensions": [reference.width(), reference.height()],
                                 "role": "HD material colour reference"},
                   "native_uv_guide": origin["file"], "axis": axis,
                   "profile": [{"uv": at, "rgb": list(color)} for at, color in stops],
                   "palette": palette, "construction": "analytic cubic colour ramp from HD pixel anchors",
                   "native_bitmap_resampled": False}


def _portrait_hd(_donor, transform: dict, _native_root: Path):
    """Assemble accepted native-mesh head captures, never recolour a baked face."""
    from PySide6.QtGui import QImage
    from .hd_packs import PACKS
    from .model_portraits import registered_portrait, portrait_filename
    folder = Path(__file__).resolve().parent / "assets/game/models"
    try:
        frames = [registered_portrait(folder, game=transform["game"], shiny=shiny, scale=4)
                  for shiny in (False, True)]
        if any(frame is None for frame in frames):
            raise ValueError("No accepted portrait set")
        registry = folder / "portrait-variants.json"
        manifest = json.loads(registry.read_text("utf-8"))
        source = manifest["source"]["hd"]
        parent = folder / "hd-fullbody-manifest.json"
        if (manifest.get("kind") != "native-mesh-render-portrait"
                or source.get("pack") != PACKS["xd"].key
                or source.get("archives") != [part.sha256 for part in PACKS["xd"].parts]
                or source.get("material_manifest_sha256") != hashlib.sha256(parent.read_bytes()).hexdigest()
                or manifest.get("native_bitmap_upscaled_for_hd") is not False):
            raise ValueError("Portrait and model material provenance differ")
        _complete_lugia_hd_capture(json.loads(parent.read_text("utf-8")))
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise _MissingHDAsset("The rebuilt Shadow Lugia portraits have not passed visual validation.") from error
    variants = (False, True) if transform["game"] == "colosseum" else (transform["shiny"],) * 2
    from .artwork import _png_pixels
    rgba = b"".join(_png_pixels(frames[int(shiny)], (168, 168)) for shiny in variants)
    image = QImage(rgba, 168, 336, 168 * 4, QImage.Format.Format_RGBA8888).copy()
    return image, {"kind": "registered-model-render-portrait", "source": manifest["source"],
        "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
        "frames": [{"file": portrait_filename(transform["game"], shiny, 4),
                    **manifest["files"][portrait_filename(transform["game"], shiny, 4)]}
                   for shiny in variants],
        "native_colour_bitmap_resampled": False}


def _complete_lugia_hd_capture(manifest: dict) -> None:
    source = manifest.get("source", {})
    coverage = source.get("hd_material_coverage", {})
    if (source.get("hd_art_revision") != 2 or
            coverage.get("total_native_materials") != 5 or
            coverage.get("exact_pack_materials") != 2 or
            coverage.get("authored_pack_derived") != 3 or
            coverage.get("derived_shiny_materials") != 1 or
            coverage.get("inherited_stock") != []):
        raise _MissingHDAsset("Shadow Lugia needs the complete revision-2 HD capture: two pack materials and three authored HD materials.")


def _rendered_body(shiny: bool):
    from PySide6.QtGui import QImage
    from .hd_packs import PACKS
    folder = Path(__file__).resolve().parent / "assets/game/models"
    filename = "dark-lugia-shiny-body-x4.png" if shiny else "dark-lugia-body-x4.png"
    manifest_path = folder / "hd-fullbody-manifest.json"
    if not manifest_path.is_file() or not (folder / filename).is_file():
        raise _MissingHDAsset("The real HD-textured Shadow Lugia whole-body capture is not installed.")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    _complete_lugia_hd_capture(manifest)
    if "common_capture" in manifest or "paired_native" in manifest:
        try:
            native_bytes = (folder / "fullbody-manifest.json").read_bytes()
            native = json.loads(native_bytes)
            common, paired = manifest["common_capture"], manifest["paired_native"]
            native_name = "dark-lugia-shiny-body.png" if shiny else "dark-lugia-body.png"
            entry = paired["files"][native_name]
            actual_native = (folder / native_name).read_bytes()
            if (manifest.get("review_only") is True or native.get("review_only") is True
                    or common != native.get("common_capture")
                    or common.get("schema") != 1 or common.get("matrix_count") != 86
                    or not re.fullmatch(r"[a-f0-9]{64}", common.get("pose_signature_sha256", ""))
                    or hashlib.sha256(native_bytes).hexdigest() != paired["manifest_sha256"]
                    or hashlib.sha256(actual_native).hexdigest() != entry["sha256"]
                    or entry["sha256"] != native["files"][native_name]["sha256"]
                    or entry["source_capture_sha256"] != native["files"][native_name]["source_capture_sha256"]
                    or manifest["files"][filename]["pose_signature_sha256"] != common["pose_signature_sha256"]):
                raise ValueError("Native and HD body pose records differ")
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise OverlayError("The native and HD DNA body poses do not match. Register the paired captures again.") from error
    record = manifest["files"][filename]
    data = (folder / filename).read_bytes()
    from .engine.postgame_lugia_model import verified_model_asset
    _, native_provenance = verified_model_asset()
    if (manifest["source"]["pack"] != PACKS["xd"].key or
            manifest["source"].get("archives") != [part.sha256 for part in PACKS["xd"].parts] or
            manifest["source"].get("model", {}).get("original_sha256") != native_provenance["source"]["model_sha256"] or
            record.get("shiny") is not shiny or
            hashlib.sha256(data).hexdigest() != record["sha256"] or
            manifest.get("kind") != "native-mesh-render-with-pack-hd-textures"):
        raise OverlayError("The HD whole-body capture has invalid source provenance.")
    image = QImage(str(folder / filename))
    if image.isNull() or (image.width(), image.height()) != (256, 256):
        raise OverlayError("The HD whole-body capture must be a separate 256px full silhouette.")
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    rgba = bytes(image.constBits())
    if (not any(rgba[3::4]) or any(rgba[(y * 256 + x) * 4 + 3]
            for y in range(256) for x in range(256) if x in (0, 255) or y in (0, 255))):
        raise OverlayError("The HD whole-body silhouette has no transparent safety margin.")
    from .engine.dna_artwork import outline_dna_body
    outlined = outline_dna_body(rgba, 256)
    image = QImage(outlined, 256, 256, QImage.Format.Format_RGBA8888).copy()
    return image, {"kind": manifest["kind"], "file": filename, "sha256": record["sha256"],
                   "dna_outline": {"color": "black", "native_pixels": 1, "output_pixels": 4},
                   "source": manifest["source"], "capture": {
                       "method": manifest.get("capture"),
                       "source_capture_sha256": record.get("source_capture_sha256"),
                       "source_dimensions": record.get("source_dimensions"),
                       "source_alpha_bbox": record.get("source_alpha_bbox"),
                       "fitted_dimensions": record.get("fitted_dimensions")}}


def _rendered_portrait(transform: dict, native_root: Path):
    """Frame newly captured real model heads when no pack portrait exists."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter, QColor
    from .hd_packs import PACKS
    from .engine.postgame_lugia_model import verified_model_asset
    folder = Path(__file__).resolve().parent / "assets/game/models"
    manifest_path = folder / "hd-fullbody-manifest.json"
    if not manifest_path.is_file():
        raise _MissingHDAsset("The independently rendered HD head portraits are not installed.")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    _complete_lugia_hd_capture(manifest)
    _, model = verified_model_asset()
    if (manifest.get("kind") != "native-mesh-render-with-pack-hd-textures" or
            manifest["source"]["pack"] != PACKS["xd"].key or
            manifest["source"].get("archives") != [p.sha256 for p in PACKS["xd"].parts] or
            manifest["source"].get("model", {}).get("original_sha256") != model["source"]["model_sha256"]):
        raise _MissingHDAsset("The rendered head portraits do not belong to the selected independent pack.")
    images, records = {}, []
    for shiny in (False, True):
        filename = "dark-lugia-shiny-head-x4.png" if shiny else "dark-lugia-head-x4.png"
        body_name = "dark-lugia-shiny-body-x4.png" if shiny else "dark-lugia-body-x4.png"
        record = manifest.get("files", {}).get(filename)
        path = folder / filename
        if not record or not path.is_file() or path.is_symlink():
            raise _MissingHDAsset("A genuine HD model head capture is not installed.")
        crop = record.get("source_crop_box", [])
        if (record.get("shiny") is not shiny or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"] or
                len(crop) != 4 or crop[2] - crop[0] < 168 or crop[3] - crop[1] < 168 or
                record.get("source_capture_sha256") != manifest["files"][body_name].get("source_capture_sha256")):
            raise OverlayError("The HD head crop integrity or source capture does not match its model.")
        image = QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
        if image.isNull() or (image.width(), image.height()) != (168, 168):
            raise OverlayError("A captured HD head must be a separate 168px portrait.")
        images[shiny] = image
        records.append({"file": filename, "sha256": record["sha256"], "shiny": shiny,
                        "source_capture_sha256": record["source_capture_sha256"], "source_crop_box": crop})
    if bytes(images[False].constBits())[3::4] != bytes(images[True].constBits())[3::4]:
        raise OverlayError("Normal and shiny HD portraits have inconsistent framing.")
    output = QImage(168, 336, QImage.Format.Format_RGBA8888)
    output.fill(0)
    mask = None
    if transform["game"] == "xd":
        native = _load_reference(native_root, transform["reference"])
        alpha = bytes(native.constBits())[3::4]
        rgba = bytes(channel for value in alpha for channel in (0, 0, 0, value))
        mask = QImage(rgba, 42, 42, 168, QImage.Format.Format_RGBA8888).copy()
        mask = mask.scaled(168, 168, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        mask = bytes(mask.constBits())[3::4]
    variants = (False, True) if transform["game"] == "colosseum" else (transform["shiny"],) * 2
    for frame, shiny in enumerate(variants):
        tile = QImage(168, 168, QImage.Format.Format_RGBA8888)
        tile.fill(QColor(0, 0, 0, 255))
        painter = QPainter(tile)
        if mask is None:
            painter.drawImage(0, 0, images[shiny])
        else:
            # Keep the complete head/back spine inside the circle; only its
            # lower neck meets the frame, as in the native portrait format.
            fitted = images[shiny].scaled(144, 144, Qt.AspectRatioMode.IgnoreAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(12, 36, fitted)
        painter.end()
        if mask is not None:
            pixels = bytearray(tile.constBits())
            pixels[3::4] = mask
            for index, alpha in enumerate(mask):
                if not alpha:
                    pixels[index * 4:index * 4 + 3] = bytes(3)
            tile = QImage(bytes(pixels), 168, 168, 672, QImage.Format.Format_RGBA8888).copy()
        painter = QPainter(output)
        painter.drawImage(0, frame * 168, tile)
        painter.end()
    return output, {"kind": "native-mesh-render-head-crop", "source": manifest["source"],
                    "heads": records, "native_colour_bitmap_resampled": False,
                    "framing": "opaque square" if mask is None else "native round alpha, black interior; head fitted144 at12,36"}


def _deoxys_body_origin(form, shiny):
    from .deoxys_assets import asset_directory, body_pixels
    from .engine.dna_artwork import outline_dna_body
    from .engine.dna_keypad import _CUSTOM_BODY_ART_RECT
    if type(form) is not int or form not in (1, 2, 3) or type(shiny) is not bool:
        raise OverlayError('Invalid imported Deoxys DNA body')
    native = outline_dna_body(body_pixels(('attack', 'defense', 'speed')[form - 1], shiny), 64)
    return {'kind': 'rendered-deoxys', 'form': form, 'shiny': shiny,
            'native_width': 64, 'native_height': 64,
            'native_rgba_sha256': hashlib.sha256(native).hexdigest(),
            'native_art_rect': list(_CUSTOM_BODY_ART_RECT),
            'asset_registry_sha256': hashlib.sha256((asset_directory() / 'deoxys-assets.json').read_bytes()).hexdigest()}


def _rendered_deoxys_body(source):
    from PySide6.QtGui import QImage
    from .deoxys_assets import body_pixels
    from .engine.dna_artwork import outline_dna_body
    expected = _deoxys_body_origin(source.get('form'), source.get('shiny'))
    if any(source.get(key) != value for key, value in expected.items()):
        raise _MissingHDAsset('The imported Deoxys DNA artwork registry changed; recreate this game folder.')
    form = ('attack', 'defense', 'speed')[source['form'] - 1]
    pixels = outline_dna_body(body_pixels(form, source['shiny'], hd=True), 256)
    image = QImage(pixels, 256, 256, QImage.Format.Format_RGBA8888).copy()
    return image, {'kind': 'registered-imported-deoxys-body', 'form': form, 'shiny': source['shiny'],
                   'asset_registry_sha256': source['asset_registry_sha256'],
                   'native_bitmap_upscaled_for_hd': False, 'output_scale': 4,
                   'sha256': hashlib.sha256(pixels).hexdigest()}


def _dna_hd(image, transform: dict, pack_roots: Mapping[str, Path]):
    from PySide6.QtCore import Qt, QRect
    from PySide6.QtGui import QImage, QPainter, QColor
    from .hd_packs import PACKS
    from .engine.dna_keypad import _TILE_ORIGINS, _DIGITS, _CUSTOM_BODY_ART_RECT, _BODY_ART_RECT
    if transform.get("runtime_gap"):
        raise _MissingHDAsset(transform["runtime_gap"])
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    template = image.copy(896 * 4, 512 * 4, 512, 512)
    blank = template.pixelColor(8 * 4, 64 * 4)
    sources = []
    for tile in transform["tiles"]:
        source = tile["body"]
        if source["kind"] == "rendered-dark-lugia":
            body, provenance = _rendered_body(source["shiny"])
            from .engine.shadow_lugia_body import shadow_lugia_body_pixels
            if (source.get("native_rgba_sha256") != hashlib.sha256(shadow_lugia_body_pixels(source["shiny"])).hexdigest()
                    or source.get("native_art_rect") != list(_CUSTOM_BODY_ART_RECT)):
                raise _MissingHDAsset("The native DNA body uses an older pose or outline. Recreate this game folder to match native and HD artwork.")
        elif source['kind'] == 'rendered-deoxys':
            body, provenance = _rendered_deoxys_body(source)
        else:
            game = source["game"]
            if game not in pack_roots:
                raise _MissingHDAsset("The whole-body source pack is not installed.")
            folder = Path(pack_roots[game]).resolve()
            folder = folder.parent if folder.name == "Textures" else folder
            marker = json.loads((folder / "installed.json").read_text("utf-8"))
            if (marker.get("key") != PACKS[game].key or
                    marker.get("archives") != [part.sha256 for part in PACKS[game].parts]):
                raise OverlayError("Whole-body source pack does not match the pinned version.")
            path = _resolve_hd(folder, source["file"])
            if path is None:
                raise _MissingHDAsset("An exact HD whole-body donor is absent: " + source["file"])
            loaded = _load_hd(path, (source["native_width"], source["native_height"]))
            body = loaded.image
            provenance = {"pack": PACKS[game].key, "file": source["file"],
                          **loaded.metadata, "output_scale": 4}
            working_size = source["native_width"] * 4, source["native_height"] * 4
            if (body.width(), body.height()) != working_size:
                body = body.scaled(*working_size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                provenance["resample"] = {"source": "actual HD donor", "from_scale": loaded.metadata["source_scale"],
                                           "to_scale": 4}
        sources.append(provenance)
        # Non-square retail silhouettes receive the same complete-image fit
        # as the native body builder, preserving their actual proportions.
        if body.width() != 256 or body.height() != 256:
            scale = min(1, 256 / max(body.width(), body.height()))
            width, height = max(1, round(body.width() * scale)), max(1, round(body.height() * scale))
            canvas = QImage(256, 256, QImage.Format.Format_RGBA8888)
            canvas.fill(0)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage((256 - width) // 2, (256 - height) // 2,
                              body.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
            painter.end()
            body = canvas
        canvas = QImage(512, 512, QImage.Format.Format_RGBA8888)
        canvas.fill(blank)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for rect in (QRect(0, 0, 512, 16), QRect(0, 496, 512, 16), QRect(0, 16, 16, 480), QRect(496, 16, 16, 480)):
            painter.drawImage(rect, template, rect)
        left, top, size = _CUSTOM_BODY_ART_RECT if source["kind"] in ('rendered-dark-lugia', 'rendered-deoxys') else _BODY_ART_RECT
        painter.drawImage(QRect(left * 4, top * 4, size * 4, size * 4), body)
        number = tile["number"]
        if number:
            painter.fillRect(408, 384, 84, 108, QColor(18, 33, 25))
            for y, row in enumerate(_DIGITS[number - 1]):
                for x in range(5):
                    if row & (16 >> x):
                        painter.fillRect(420 + x * 12, 396 + y * 12, 12, 12, QColor(255, 255, 255))
        painter.end()
        x, y = _TILE_ORIGINS[tile["position"]]
        painter = QPainter(image)
        painter.drawImage(x * 4, y * 4, canvas)
        painter.end()
    return image, sources


def _dna_cell_hd(image, transform: dict, pack_roots: Mapping[str, Path]):
    cell = transform["cell"]
    atlas, sources = _dna_hd(image, {"tiles": [transform["tile"]] if transform["tile"] else [],
                                    **({"runtime_gap": transform["runtime_gap"]} if transform.get("runtime_gap") else {})},
                             pack_roots)
    return atlas.copy(cell["crop_x"] * 4, cell["crop_y"] * 4, cell["width"] * 4, cell["height"] * 4), sources


def prepare_hd_overlays(native_directory: Path, destination: Path, *, pack_roots: Mapping[str, Path],
                        cancel: Event | None = None, progress: Callable[[str], None] | None = None) -> dict:
    """Build x4 only from authenticated pinned pack donors and saved recipes.

    A partial report is useful for diagnostics, but hd_ready is false whenever
    any required donor/variant is absent. The caller must gate HD activation
    on that flag and publish the staging output only after successful review.
    """
    from PySide6.QtGui import QImage
    from .hd_packs import PACKS
    if Path(destination).is_symlink():
        raise OverlayError("HD output cannot be a symbolic link.")
    root, target = Path(native_directory).resolve(), Path(destination).resolve()
    report = native_asset_manifest(root)
    report["files"], report["missing_assets"], report["inherited_stock"] = [], [], []
    report["limitations"] = _runtime_limitations(report["assets"])
    report["conditional_limitations"] = ["PID-specific Spinda DNA requires a registered HD spot-pattern recipe when selected."]
    castform_roles, deoxys_roles = {}, {}
    for resource in report.get("resources", []):
        if resource.get("role") in _CASTFORM_ROLES:
            for key in resource.get("textures", []):
                castform_roles.setdefault(key, set()).add(resource["role"])
        if resource.get('role') in _DEOXYS_ROLES:
            for key in resource.get('textures', []):
                deoxys_roles.setdefault(key, set()).add(resource['role'])
    deoxys_generated = None
    deoxys_error = None
    cache = {}
    for asset in report["assets"]:
        _checkpoint(cancel)
        if progress:
            progress(asset["file"])
        _load_reference(root, asset["native"])
        origin = asset.get("hd")
        if not origin:
            report["missing_assets"].append({"file": asset["file"], "reason": "No registered pack-derived HD asset"})
            continue
        custom_roles = set(asset.get("castform_roles", [])) | castform_roles.get(asset["file"], set())
        if asset.get("role") in _CASTFORM_ROLES:
            custom_roles.add(asset["role"])
        imported_roles = set(asset.get('deoxys_roles', [])) | deoxys_roles.get(asset['file'], set())
        if asset.get('role') in _DEOXYS_ROLES:
            imported_roles.add(asset['role'])
        if ((imported_roles and not custom_roles) or
                origin.get('transform', {}).get('type') == 'imported-deoxys'):
            try:
                contract = report.get('deoxys_forms')
                transform = origin.get('transform', {})
                native_image = _load_reference(root, asset['native'])
                if (not isinstance(contract, dict) or contract.get('enabled') is not True
                        or report.get('game') != 'colosseum'
                        or transform.get('type') != 'imported-deoxys'
                        or transform.get('role') not in ('portrait', 'material')
                        or transform.get('native_key') != asset['base_key']
                        or transform.get('asset_registry_sha256') != contract.get('asset_registry_sha256')
                        or transform.get('material_recipes_sha256') != contract.get('material_recipes_sha256')
                        or transform.get('native_rgba_sha256') != hashlib.sha256(bytes(native_image.constBits())).hexdigest()
                        or asset['base_key'] not in contract.get('portrait_keys' if transform.get('role') == 'portrait'
                                                                else 'material_keys', [])):
                    raise OverlayError('Imported Deoxys source/HD route is unqualified')
                if deoxys_generated is None and deoxys_error is None:
                    try:
                        deoxys_generated = prepare_deoxys_hd(contract, pack_roots, target)
                    except (OSError, ValueError) as error:
                        deoxys_error = str(error)
                if deoxys_error is not None:
                    raise OverlayError(deoxys_error)
                name = asset['base_key']
                payload = (target / name).read_bytes()
                if hashlib.sha256(payload).hexdigest() != deoxys_generated['files'].get(name):
                    raise OverlayError('Prepared Deoxys HD file changed')
                expected = asset['native']['width'] * 4, asset['native']['height'] * 4
                image = QImage.fromData(payload, 'PNG')
                if image.isNull() or (image.width(), image.height()) != expected:
                    raise OverlayError('Prepared Deoxys HD image has invalid dimensions')
                _write(target / asset['file'], payload)
                report['files'].append({'file': asset['file'], 'sha256': hashlib.sha256(payload).hexdigest(),
                    'width': expected[0], 'height': expected[1], 'bytes': len(payload),
                    'native_format': asset['native_format'], 'hd_source': {
                        'kind': 'registered-imported-deoxys', 'pack': PACKS['xd'].key,
                        'source_scale': 4, 'output_scale': 4,
                        'asset_registry_sha256': contract['asset_registry_sha256'],
                        'material_recipes_sha256': contract['material_recipes_sha256'],
                        'native_reference': asset['native'], 'transform': transform}})
            except (OSError, ValueError) as error:
                report['missing_assets'].append({'file': asset['file'], 'reason': str(error)})
            continue
        if custom_roles:
            transform = origin.get("transform", {})
            expected_game = report.get("castform_shinies", {}).get("game_id", transform.get("game_id"))
            try:
                from .hd_castform_shinies import castform_shiny_recipes
                if (transform.get("type") not in ("custom-castform-shiny", "castform-stock-material")
                        or transform.get("game_id") != expected_game
                        or transform.get("native_key") != asset["base_key"]
                        or ("castform_portrait" in custom_roles and (
                            transform.get("type") != "custom-castform-shiny" or transform.get("role") != "portrait"))
                        or not castform_shiny_recipes(expected_game)["active"]):
                    raise ValueError("Custom Castform route or native/x4 catalogue is unavailable")
            except ValueError as error:
                report["missing_assets"].append({"file": asset["file"], "reason": str(error)})
                continue
        if origin["transform"]["type"] == "constant-color":
            width, height = asset["native"]["width"] * 4, asset["native"]["height"] * 4
            png = _png((width, height), bytes(origin["transform"]["rgba"]) * (width * height))
            target.mkdir(parents=True, exist_ok=True)
            _write(target / asset["file"], png)
            report["files"].append({"file": asset["file"], "sha256": hashlib.sha256(png).hexdigest(),
                                   "width": width, "height": height, "bytes": len(png),
                                   "native_format": asset["native_format"], "hd_source": {
                                       "kind": "constant-color", "rgba": origin["transform"]["rgba"],
                                       "native_sha256": asset["native"]["sha256"]}})
            continue
        game = origin["game"]
        if game not in pack_roots:
            report["missing_assets"].append({"file": asset["file"], "reason": "Required pinned pack is not installed", "pack": game})
            continue
        folder = Path(pack_roots[game]).resolve()
        folder = folder.parent if folder.name == "Textures" else folder
        if game not in cache:
            marker = json.loads((folder / "installed.json").read_text("utf-8"))
            pack = PACKS[game]
            if marker.get("key") != pack.key or marker.get("archives") != [part.sha256 for part in pack.parts]:
                raise OverlayError("HD donor pack does not match the pinned release.")
            cache[game] = folder
        if origin["transform"]["type"] in ("custom-castform-shiny", "castform-stock-material"):
            try:
                native_image = _load_reference(root, asset["native"])
                if origin["transform"]["type"] == "custom-castform-shiny":
                    from .hd_castform_shinies import render_castform_shiny_overlay
                    png, components = render_castform_shiny_overlay(origin,
                        native_image=native_image, pack_roots=pack_roots)
                else:
                    png, components = _render_castform_stock(origin, native_image)
            except (OSError, ValueError) as error:
                report["missing_assets"].append({"file": asset["file"], "reason": str(error)})
                continue
            target.mkdir(parents=True, exist_ok=True)
            _write(target / asset["file"], png)
            report["files"].append({"file": asset["file"], "sha256": hashlib.sha256(png).hexdigest(),
                "width": native_image.width() * 4, "height": native_image.height() * 4,
                "bytes": len(png), "native_format": asset["native_format"],
                "hd_source": {"kind": components["kind"], "pack": PACKS[game].key,
                    "sha256": components["sha256"], "source_scale": 4, "output_scale": 4,
                    "native_reference": asset["native"], "transform": origin["transform"],
                    "components": components}})
            continue
        if origin["transform"]["type"] == "captured-extra-portrait":
            from .hd_extra_portraits import render_extra_portrait
            try:
                image, components = render_extra_portrait(origin,
                    native_image=_load_reference(root, asset["native"]))
            except (OSError, ValueError) as error:
                report["missing_assets"].append({"file": asset["file"], "reason": str(error)})
                continue
            expected = asset["native"]["width"] * 4, asset["native"]["height"] * 4
            if (image.width(), image.height()) != expected:
                raise OverlayError("The registered additional portrait has changed atlas dimensions.")
            png = _png(expected, bytes(image.constBits()))
            target.mkdir(parents=True, exist_ok=True)
            _write(target / asset["file"], png)
            report["files"].append({"file": asset["file"], "sha256": hashlib.sha256(png).hexdigest(),
                "width": expected[0], "height": expected[1], "bytes": len(png),
                "native_format": asset["native_format"], "hd_source": {
                    "kind": "native-form-mesh-render-portrait", "pack": PACKS[game].key,
                    "file": "extra-portraits/extra-portraits.json",
                    "sha256": components["manifest_sha256"], "source_scale": 4, "output_scale": 4,
                    "transform": origin["transform"], "components": components}})
            continue
        exact_target = _resolve_hd(folder, asset["base_key"])
        if (origin["file"] != asset["base_key"] and exact_target is not None and
                origin["transform"]["type"] in ("identity", "pkx_recipe")):
            # An exact upstream replacement for the target's native bytes is
            # stronger evidence than a colour-recipe reconstruction.
            origin = dict(origin, file=asset["base_key"], transform={"type": "identity"},
                          native_source="exact target texture key in the pinned pack")
        donor = _resolve_hd(folder, origin["file"])
        retouch = rendered = None
        if donor is None:
            if origin["transform"]["type"] == "shadow_lugia_portrait":
                report["missing_assets"].append({"file": asset["file"],
                    "reason": "The pinned Shadow Lugia HD eye material is absent"})
                continue
            if origin["transform"]["type"] in ("identity", "pkx_recipe"):
                try:
                    retouch = (_lugia_material_reconstruction(origin, folder) or
                               _authored_material_retouch(origin, folder))
                except _MissingHDAsset as error:
                    report["missing_assets"].append({"file": asset["file"], "reason": str(error)})
                    continue
            if retouch is None and rendered is None:
                from .hd_lugia_field import render_lugia_field_material
                retouch = render_lugia_field_material(folder, native_key=origin["file"], target_key=asset["base_key"])
            if rendered is None and retouch is None and _inherited_stock(asset, origin):
                report["inherited_stock"].append({"file": asset["file"], "policy": "base_pack_fallback",
                    "reason": "Byte-identical stock model texture; the selected pack does not replace it",
                    "native_source": origin["native_source"],
                    "native_model_sha256": origin["native_model_sha256"],
                    "native_texture_sha256": origin["native_texture_sha256"]})
                continue
            if rendered is None and retouch is None:
                report["missing_assets"].append({"file": asset["file"], "reason": "Exact native donor key is absent from the pack", "donor": origin["file"]})
                continue
        expected = asset["native"]["width"] * 4, asset["native"]["height"] * 4
        source_native = origin.get("source_native_dimensions", [asset["native"]["width"], asset["native"]["height"]])
        if rendered:
            image = rendered[0]
            manifest = Path(__file__).resolve().parent / "assets/game/models/hd-fullbody-manifest.json"
            source_metadata = {"physical_file": manifest.name, "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                               "format": "PNG", "mip_levels": 1, "width": 168, "height": 168, "source_scale": 4}
            source_scale = 4
        elif retouch:
            image = retouch[0]
            source_metadata = retouch[1]["reference"]
            source_scale = 4  # Newly authored vector ramp is rendered directly at x4.
        else:
            loaded = _load_hd(donor, tuple(source_native))
            image = loaded.image
            source_metadata = loaded.metadata
            source_scale = loaded.metadata["source_scale"]
        if source_scale != 4:
            from PySide6.QtCore import Qt
            image = image.scaled(source_native[0] * 4, source_native[1] * 4, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        transform = origin["transform"]
        components = None
        try:
            if rendered:
                components = rendered[1]
            elif transform["type"] == "shadow_lugia_portrait":
                from .hd_lugia_field import _EYE_HD_SOURCE_SHA256
                if source_metadata["sha256"] != _EYE_HD_SOURCE_SHA256:
                    raise OverlayError("The Shadow Lugia eye material differs from the pinned HD source.")
                image, components = _portrait_hd(image, transform, root)
            elif transform["type"] == "dna":
                image, components = _dna_hd(image, transform, pack_roots)
            elif transform["type"] == "dna_cell":
                image, components = _dna_cell_hd(image, transform, pack_roots)
            elif transform["type"] == "spinda_diagram_layer":
                from .hd_spinda_diagram import render_spinda_diagram_layer
                image, components = render_spinda_diagram_layer(transform,
                    {game: cache[game] / "Textures"})
            elif transform["type"] == "colosseum_portrait_to_xd":
                from .hd_portraits import render_xd_portrait
                image, components = render_xd_portrait(image, transform,
                    native_image=_load_reference(root, asset["native"]), source_metadata=source_metadata)
            else:
                image = _recolor_hd(image, transform)
        except _MissingHDAsset as error:
            report["missing_assets"].append({"file": asset["file"], "reason": str(error)})
            continue
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        png = _png(expected, bytes(image.constBits()))
        target.mkdir(parents=True, exist_ok=True)
        _write(target / asset["file"], png)
        if asset.get("classification") == "inherited_stock":
            asset["native_classification"] = "inherited_stock"
            asset["classification"] = "authored_pack_derived" if retouch else "exact_pack"
        report["files"].append({"file": asset["file"], "sha256": hashlib.sha256(png).hexdigest(),
                               "width": expected[0], "height": expected[1], "bytes": len(png),
                               "native_format": asset["native_format"], "hd_source": {
                                   "kind": "registered-model-render-portrait" if transform["type"] == "shadow_lugia_portrait" else "native-mesh-render-head-crop" if rendered else retouch[1]["kind"] if retouch else "upstream-hd-texture",
                                   "pack": PACKS[game].key,
                                   "file": source_metadata["physical_file"] if rendered else retouch[1]["reference"]["file"] if retouch else origin["file"],
                                   "logical_file": retouch[1]["reference"]["file"] if retouch else origin["file"],
                                   "physical_file": source_metadata["physical_file"],
                                   "sha256": source_metadata["sha256"],
                                   "format": source_metadata["format"], "mip_levels": source_metadata["mip_levels"],
                                   "source_dimensions": [source_metadata["width"], source_metadata["height"]],
                                   "native_donor_key": origin["file"], "retouch": retouch[1] if retouch else None,
                                   "source_scale": source_metadata["source_scale"],
                                   "output_scale": 4,
                                   "resample": ({"source": "actual upstream HD texture", "from_scale": source_scale,
                                                 "to_scale": 4} if source_scale != 4 else None),
                                   "transform": transform, "components": components}})
    report["texture_count"] = len(report["files"])
    report["hd_ready"] = not report["missing_assets"]
    report["kind"] = "pack-derived HD custom assets"
    target.mkdir(parents=True, exist_ok=True)
    _write(target / _MANIFEST, (json.dumps(report, indent=2, ensure_ascii=True) + "\n").encode())
    return report


def generate_custom_overlays(iso: Path, destination: Path, *, is_xd: bool = False,
                             reference_iso: Path | None = None, pack_roots: Mapping[str, Path] | None = None,
                             asset_context: Mapping | None = None,
                             cancel: Event | None = None, progress: Callable[[str], None] | None = None) -> dict:
    """Capture native contracts, optionally preparing real pack-derived HD."""
    capture = capture_native_assets(iso, destination, is_xd=is_xd, reference_iso=reference_iso,
                                    asset_context=asset_context, cancel=cancel, progress=progress)
    if pack_roots is None:
        return capture
    return prepare_hd_overlays(destination, destination, pack_roots=pack_roots, cancel=cancel, progress=progress)
