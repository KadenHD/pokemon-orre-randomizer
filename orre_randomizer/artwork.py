"""Bounded, read-only ROM artwork previews and a verified local PNG cache.

No game artwork is distributed with this module. Preview extraction checks
format and bounds; the service still validates the complete ROM before building.
"""
from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import zlib

from .engine.actor_palette import pkx_recipe, remap_rgb565
from .engine.analyze_game import decompress_lzss, parse_fsys
from .engine.spinda_art import _FACE_ORDER, _FACE_SIZE, spinda_face_texture
from .engine.survey_assets import fst_inventory
from .engine.unown_form import unown_suffix


class ArtworkError(ValueError):
    """Artwork is unavailable; callers can retain their ordinary UI fallback."""


_VERSION = 1
_MANIFEST = "artwork-v1.json"
_MAX_FST = 1024 * 1024
_MAX_ARCHIVE = 16 * 1024 * 1024
_MAX_MEMBER = 4 * 1024 * 1024
_MAX_PNG = 512 * 1024
_MAX_CACHE = 1024 * 1024
_MAX_MANIFEST = 16 * 1024
_DIMENSIONS = {"background": (640, 480), "logo": (96, 32),
               "espeon": (42, 42), "umbreon": (42, 42), "pikachu": (42, 42)}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_range(stream, offset: int, size: int, file_size: int) -> bytes:
    if offset < 0 or size < 0 or offset > file_size or size > file_size - offset:
        raise ArtworkError("Invalid artwork range.")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ArtworkError("Truncated artwork source.")
    return data


def _disc_files(iso: Path, names=None, *, is_xd: bool = False) -> dict[str, bytes]:
    names = {"title.fsys", "poke_face.fsys", "opening.bnr"} if names is None else names
    with iso.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        boot = _read_range(stream, 0, 0x440, size)
        game_ids = (b"GXXP01", b"GXXE01", b"GXXJ01") if is_xd else (b"GC6P01", b"GC6E01", b"GC6J01")
        if (boot[:6] not in game_ids or boot[6:8] != b"\0\0"
                or boot[0x1c:0x20] != bytes.fromhex("c2339f3d")):
            raise ArtworkError("Unsupported artwork source.")
        fst_offset, fst_size = struct.unpack_from(">II", boot, 0x424)
        if not 12 <= fst_size <= _MAX_FST:
            raise ArtworkError("Invalid artwork filesystem.")
        entries, _ = fst_inventory(_read_range(stream, fst_offset, fst_size, size))
        files = {entry["path"]: entry for entry in entries}
        if not names <= files.keys():
            raise ArtworkError("Missing artwork files.")
        for entry in entries:
            if entry["disc_offset"] > size or entry["size"] > size - entry["disc_offset"]:
                raise ArtworkError("Invalid artwork filesystem range.")
        result = {}
        for name in sorted(names):
            entry = files[name]
            if not 0x60 <= entry["size"] <= _MAX_ARCHIVE:
                raise ArtworkError("Artwork archive exceeds limits.")
            data = _read_range(stream, entry["disc_offset"], entry["size"], size)
            if name == "opening.bnr":
                if (len(data), data[:4]) not in ((8096, b"BNR2"), (6496, b"BNR1")):
                    raise ArtworkError("Unsupported artwork banner.")
            elif struct.unpack_from(">I", data, 0xc)[0] > 2048:
                raise ArtworkError("Artwork archive exceeds limits.")
            result[name] = data
        return result


def _member(archive: bytes, members: list[dict], name: str) -> bytes:
    matches = [member for member in members if member["name"] == name]
    if len(matches) != 1:
        raise ArtworkError("Missing artwork member.")
    member = matches[0]
    if not 0 < member["unpacked_size"] <= _MAX_MEMBER:
        raise ArtworkError("Artwork member exceeds limits.")
    stored = archive[member["offset"]:member["offset"] + member["stored_size"]]
    raw = (decompress_lzss(stored, max_output=_MAX_MEMBER)
           if member["compression"] == "LZSS" else stored)
    if len(raw) != member["unpacked_size"]:
        raise ArtworkError("Invalid artwork member size.")
    return raw


def _rgb565(value: int) -> tuple[int, int, int, int]:
    r, g, b = value >> 11 & 31, value >> 5 & 63, value & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255)


def _rgb5a3(value: int) -> tuple[int, int, int, int]:
    if value & 0x8000:
        r, g, b = value >> 10 & 31, value >> 5 & 31, value & 31
        return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255)
    a = value >> 12 & 7
    return ((value >> 8 & 15) * 17, (value >> 4 & 15) * 17,
            (value & 15) * 17, a << 5 | a << 2 | a >> 1)


def _decode_pixels(width: int, height: int, fmt: int, data: bytes) -> bytes:
    """Decode GX tiled RGB5A3, RGBA8 or CMPR; no external decoder code used."""
    if not 0 < width <= 2048 or not 0 < height <= 2048 or fmt not in (4, 16, 32):
        raise ArtworkError("Unsupported artwork texture.")
    tile, stride = (8, 32) if fmt == 4 else (4, 32 if fmt == 16 else 64)
    expected = ((width + tile - 1) // tile) * ((height + tile - 1) // tile) * stride
    if expected != len(data) or expected > _MAX_MEMBER:
        raise ArtworkError("Invalid artwork pixel range.")
    pixels = bytearray(width * height * 4)

    def put(x, y, color):
        if x < width and y < height:
            position = (y * width + x) * 4
            pixels[position:position + 4] = bytes(color)

    position = 0
    for by in range(0, height, tile):
        for bx in range(0, width, tile):
            block = data[position:position + stride]
            position += stride
            if fmt == 16:
                for index in range(16):
                    put(bx + index % 4, by + index // 4,
                        _rgb5a3(struct.unpack_from(">H", block, index * 2)[0]))
            elif fmt == 32:
                for index in range(16):
                    put(bx + index % 4, by + index // 4,
                        (block[index * 2 + 1], block[32 + index * 2],
                         block[33 + index * 2], block[index * 2]))
            else:
                for quadrant in range(4):
                    part = block[quadrant * 8:quadrant * 8 + 8]
                    first, second = struct.unpack_from(">HH", part)
                    a, b = _rgb565(first), _rgb565(second)
                    if first > second:
                        colors = [a, b, tuple((5 * a[k] + 3 * b[k]) >> 3 for k in range(3)) + (255,),
                                  tuple((3 * a[k] + 5 * b[k]) >> 3 for k in range(3)) + (255,)]
                    else:
                        middle = tuple((a[k] + b[k]) // 2 for k in range(3))
                        colors = [a, b, middle + (255,), middle + (0,)]
                    for y in range(4):
                        for x in range(4):
                            put(bx + quadrant % 2 * 4 + x, by + quadrant // 2 * 4 + y,
                                colors[part[4 + y] >> (6 - 2 * x) & 3])
    return bytes(pixels)


def _indexed_pixels(width: int, height: int, data: bytes) -> bytes:
    """Decode XD's 8×4 indexed tiles followed by a 256-entry RGB5A3 palette."""
    tiles_wide = (width + 7) // 8
    size = tiles_wide * ((height + 3) // 4) * 32
    if not 0 < width <= 2048 or not 0 < height <= 2048 or len(data) != size + 512 or size > _MAX_MEMBER:
        raise ArtworkError("Invalid indexed artwork pixel range.")
    palette = [bytes(_rgb5a3(value)) for value in struct.unpack_from(">256H", data, size)]
    pixels = bytearray()
    for y in range(height):
        row = (y // 4) * tiles_wide * 32 + (y % 4) * 8
        for x in range(width):
            index = data[row + (x // 8) * 32 + (x % 8)]
            pixels.extend(palette[index])
    return bytes(pixels)


def _texture(raw: bytes, dimensions: tuple[int, int]) -> bytes:
    if len(raw) < 128:
        raise ArtworkError("Truncated artwork texture.")
    width, height = struct.unpack_from(">HH", raw)
    formats = {4: 0xb0, 8: 1, 16: 0x90, 32: 0x45}
    fmt = raw[4]
    if ((width, height) != dimensions or fmt not in formats or raw[5] != 1 or
            struct.unpack_from(">I", raw, 8)[0] != formats[fmt] or
            struct.unpack_from(">I", raw, 0x28)[0] != 128):
        raise ArtworkError("Unsupported artwork texture.")
    if fmt == 8:
        if struct.unpack_from(">I", raw, 0xC)[0] != 3:
            raise ArtworkError("Unsupported indexed artwork palette.")
        return _indexed_pixels(width, height, raw[128:])
    return _decode_pixels(width, height, fmt, raw[128:])


def _png(dimensions: tuple[int, int], pixels: bytes) -> bytes:
    width, height = dimensions
    if len(pixels) != width * height * 4:
        raise ArtworkError("Invalid artwork pixels.")

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data +
                struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff))

    lines = b"".join(b"\0" + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (_PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(lines, 9)) + chunk(b"IEND", b""))


def _png_pixels(data: bytes, dimensions: tuple[int, int]) -> bytes:
    """Validate our deliberately minimal PNG format with a bounded inflation."""
    if len(data) > _MAX_PNG or data[:8] != _PNG_SIGNATURE:
        raise ArtworkError("Invalid cached artwork image.")
    position, chunks = 8, []
    for kind in (b"IHDR", b"IDAT", b"IEND"):
        if position + 12 > len(data):
            raise ArtworkError("Truncated cached artwork image.")
        size = struct.unpack_from(">I", data, position)[0]
        end = position + 12 + size
        if end > len(data) or data[position + 4:position + 8] != kind:
            raise ArtworkError("Invalid cached artwork chunks.")
        payload = data[position + 8:end - 4]
        if binascii.crc32(kind + payload) & 0xffffffff != struct.unpack_from(">I", data, end - 4)[0]:
            raise ArtworkError("Corrupted cached artwork image.")
        chunks.append(payload)
        position = end
    width, height = dimensions
    if (position != len(data) or chunks[0] != struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
            or chunks[2]):
        raise ArtworkError("Invalid cached artwork dimensions.")
    expected = height * (width * 4 + 1)
    decoder = zlib.decompressobj()
    lines = decoder.decompress(chunks[1], expected + 1)
    if (len(lines) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or
            any(lines[y * (width * 4 + 1)] for y in range(height))):
        raise ArtworkError("Invalid cached artwork pixels.")
    return b"".join(lines[y * (width * 4 + 1) + 1:(y + 1) * (width * 4 + 1)]
                    for y in range(height))


def _cache_path(cache: Path, name: str) -> Path:
    candidate = cache / name
    if candidate.is_symlink() or candidate.resolve().parent != cache:
        raise ArtworkError("Invalid artwork cache path.")
    return candidate


def _atomic_write(target: Path, data: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".artwork-", suffix=".tmp", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _load_cache(cache: Path) -> dict[str, Path]:
    manifest = _cache_path(cache, _MANIFEST)
    if not manifest.exists():
        return {}
    with manifest.open("rb") as stream:
        raw = stream.read(_MAX_MANIFEST + 1)
    if len(raw) > _MAX_MANIFEST:
        raise ArtworkError("Artwork cache exceeds limits.")
    document = json.loads(raw)
    if (not isinstance(document, dict) or set(document) != {"version", "assets"} or
            type(document["version"]) is not int or document["version"] != _VERSION or
            not isinstance(document["assets"], dict) or set(document["assets"]) != set(_DIMENSIONS)):
        raise ArtworkError("Invalid artwork cache manifest.")
    result, total = {}, 0
    for key, dimensions in _DIMENSIONS.items():
        record = document["assets"][key]
        if (not isinstance(record, dict) or set(record) != {"file", "sha256", "bytes", "width", "height"} or
                type(record["bytes"]) is not int or not 0 < record["bytes"] <= _MAX_PNG or
                type(record["width"]) is not int or type(record["height"]) is not int or
                (record["width"], record["height"]) != dimensions or
                not isinstance(record["sha256"], str) or len(record["sha256"]) != 64 or
                any(char not in "0123456789abcdef" for char in record["sha256"])):
            raise ArtworkError("Invalid artwork cache record.")
        filename = f"{key}-v{_VERSION}-{record['sha256']}.png"
        if record["file"] != filename:
            raise ArtworkError("Invalid artwork cache path.")
        target = _cache_path(cache, filename)
        with target.open("rb") as stream:
            data = stream.read(_MAX_PNG + 1)
        total += len(data)
        if (len(data) != record["bytes"] or total > _MAX_CACHE or _digest(data) != record["sha256"]):
            raise ArtworkError("Corrupted artwork cache.")
        _png_pixels(data, dimensions)
        result[key] = target
    return result


def load_cached_artwork(cache_dir: Path) -> dict[str, Path]:
    """Return verified cache paths; missing cache is empty, invalid cache raises."""
    try:
        return _load_cache(Path(cache_dir).resolve())
    except ArtworkError:
        raise
    except (OSError, ValueError, RuntimeError, struct.error, zlib.error) as error:
        raise ArtworkError("Artwork cache is unavailable.") from error


def extract_portraits(iso: Path, species_ids: tuple[int, ...], *, shiny: bool = False,
                      is_xd: bool = False, unown_form_index: int = 0) -> dict[int, bytes]:
    """Read up to 64 42px faces in one archive pass, indexed by internal ID.

    Gen III internal IDs differ from national Pokédex numbers. The face archive
    uses the internal ID (e.g. face277 is national #252), as does the final DOL.
    No cache, bundle, source file or user configuration is written.
    """
    if type(shiny) is not bool or not 1 <= len(species_ids) <= 64 or any(type(i) is not int or not 1 <= i <= 412 for i in species_ids):
        raise ArtworkError("Invalid portrait species IDs.")
    try:
        archive = _disc_files(Path(iso), {"poke_face.fsys"}, is_xd=is_xd)["poke_face.fsys"]
        members = parse_fsys(archive)["members"]
        return {i: _portrait_png(archive, members, i, shiny=shiny, unown_form_index=unown_form_index)
                for i in set(species_ids)}
    except ArtworkError:
        raise
    except (OSError, ValueError, RuntimeError, struct.error, zlib.error) as error:
        raise ArtworkError("Portrait extraction is unavailable.") from error


def _portrait_png(archive: bytes, members: list[dict], index: int, *, shiny=False, unown_form_index=0) -> bytes:
    # Some species have two facing variants per row: 84x84 rather than 42x84.
    # The upper-left frame is ordinary; the lower row holds shiny variants.
    name = f"face201{unown_suffix(unown_form_index)}" if index == 201 else f"face{index:03d}"
    raw = _member(archive, members, name)
    if len(raw) < 4:
        raise ArtworkError("Truncated portrait texture.")
    width, height = struct.unpack_from(">HH", raw)
    if width not in (42, 84) or height != 84:
        raise ArtworkError("Unsupported portrait frames.")
    pixels = _texture(raw, (width, height))
    first = 42 if shiny else 0
    face = b"".join(pixels[y * width * 4:(y * width + 42) * 4] for y in range(first, first + 42))
    return _png((42, 42), face)


def extract_spinda_patterns(iso: Path, requests: set[tuple[int, bool]], *,
                            is_xd: bool = False) -> dict[tuple[int, bool], bytes]:
    """Show the exact native face texture, separate from the fixed portrait."""
    try:
        archive = _disc_files(Path(iso), {"pkx_patcheel.fsys"}, is_xd=is_xd)["pkx_patcheel.fsys"]
        members = parse_fsys(archive)["members"]
        face, spot = (_member(archive, members, name) for name in ("face", "buti_a"))
        recipe = pkx_recipe(_member(archive, members, "patcheel"), xd=is_xd) if any(
            shiny for _, shiny in requests) else None
        patterns = {}
        for pid, shiny in sorted(requests):
            words = struct.iter_unpack(">H", spinda_face_texture(face, spot, pid))
            colors = {}
            pixels = bytearray(4 * _FACE_SIZE ** 2)
            for index, (color,) in zip(_FACE_ORDER, words, strict=True):
                if color not in colors:
                    tinted = remap_rgb565(color, *recipe) if shiny else color
                    colors[color] = bytes(_rgb565(tinted))
                pixels[index * 4:index * 4 + 4] = colors[color]
            patterns[pid, shiny] = _png((_FACE_SIZE, _FACE_SIZE), bytes(pixels))
        return patterns
    except ArtworkError:
        raise
    except (OSError, ValueError, RuntimeError, struct.error, zlib.error) as error:
        raise ArtworkError("Spinda pattern extraction is unavailable.") from error


def extract_artwork(iso: Path, cache_dir: Path) -> dict[str, Path]:
    """Extract five small previews from a PAL ISO and atomically publish cache.

    Run off the UI thread. RVZ conversion belongs to the existing service.
    No source path or user filename is recorded in the versioned manifest.
    """
    try:
        source, cache = Path(iso).resolve(), Path(cache_dir).resolve()
        files = _disc_files(source)
        title, faces = files["title.fsys"], files["poke_face.fsys"]
        title_members, face_members = parse_fsys(title)["members"], parse_fsys(faces)["members"]
        images = {"background": _texture(_member(title, title_members, "menu_042"), (640, 480)),
                  "logo": _decode_pixels(96, 32, 16, files["opening.bnr"][0x20:0x1820])}
        for key, member_name in (("espeon", "face196"), ("umbreon", "face197"), ("pikachu", "face025")):
            # This verified layout has the ordinary face above its shiny variant.
            images[key] = _texture(_member(faces, face_members, member_name), (42, 84))[:42 * 42 * 4]
        rendered = {key: _png(_DIMENSIONS[key], pixels) for key, pixels in images.items()}
        if sum(map(len, rendered.values())) > _MAX_CACHE or any(len(data) > _MAX_PNG for data in rendered.values()):
            raise ArtworkError("Artwork cache exceeds limits.")
        cache.mkdir(parents=True, exist_ok=True)
        records = {}
        for key, data in rendered.items():
            digest = _digest(data)
            filename = f"{key}-v{_VERSION}-{digest}.png"
            records[key] = {"file": filename, "sha256": digest, "bytes": len(data),
                            "width": _DIMENSIONS[key][0], "height": _DIMENSIONS[key][1]}
        targets = [_cache_path(cache, record["file"]) for record in records.values()]
        manifest = _cache_path(cache, _MANIFEST)
        if source in [*targets, manifest]:
            raise ArtworkError("Artwork cache overlaps source.")
        # Content-addressed blobs first; the manifest is the final atomic commit.
        for target, data in zip(targets, rendered.values(), strict=True):
            _atomic_write(target, data)
        encoded = json.dumps({"version": _VERSION, "assets": records}, separators=(",", ":")).encode("utf-8")
        _atomic_write(manifest, encoded)
        return _load_cache(cache)
    except ArtworkError:
        raise
    except (OSError, ValueError, RuntimeError, struct.error, zlib.error) as error:
        raise ArtworkError("Artwork extraction is unavailable.") from error
