"""Original menu samples read from the user's PAL ROM into a local WAV cache.

No audio is distributed. The bounded DSP decoder is an independent stdlib
implementation. Samples follow the native menu sound table and fixed key; the
game's MusyX routing/reverb is not emulated. PCM gain is fixed at 25% for quiet
interface feedback; system volume is never changed. Extraction never writes the source.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

from .engine.analyze_game import decompress_lzss, parse_fsys
from .engine.survey_assets import fst_inventory


class MenuSoundError(ValueError):
    """Original menu sounds are unavailable; the interface can remain silent."""


_VERSION = 1
_MANIFEST = "menu-sounds-v1.json"
_MAX_FST = 1024 * 1024
_MAX_ARCHIVE = 16 * 1024 * 1024
_MAX_MEMBER = 3 * 1024 * 1024
_MAX_BANK = 2 * 1024 * 1024
_MAX_WAV = 192044
_MAX_MANIFEST = 8192
_MAX_SAMPLES = 96000
_SOURCE_HASHES = {
    "common.fsys": "88d3bf0f5623fe9c4e02d1d43b93333ca9f56b699173c7e58f4e878781174161",
    "sound/snd_se.samp": "85e4eb31ae001f72719f683634ff9917cbb31e8974ed69b97dc582465762345b",
}
_MEMBER_HASHES = {
    "common_rel": "ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b",
    "snd_se_proj": "c913b2c456106de1c54f1927fd4b37ed78af1679e0f9542f48518a5060cf595c",
    "snd_se_pool": "4562cb4e332bd58ba184bcb41c61264ede07f16478378858d1829b6ca96a1615",
    "snd_se_sdir": "aa0ac50c0d3ad6e8af7c8a87fb92881e3fa34cdccd28b186dae8579aec7ccaac",
}
# menu set 1: cursor/accept/back -> game ID -> MusyX FX -> macro -> sample.
# The cursor macro sets key 72, one octave above its sample's native key 60.
_SOUNDS = {"move": (35, 0x359, 0x1B7, 48, 88200, 5636),
           "confirm": (36, 0x35A, 0x1B3, 1, 44100, 9792),
           "back": (37, 0x35B, 0x1BB, 52, 44100, 7917)}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _range(stream, offset: int, size: int, total: int) -> bytes:
    if offset < 0 or size < 0 or offset > total or size > total - offset:
        raise MenuSoundError("Menu audio range exceeds the source.")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise MenuSoundError("Truncated menu audio source.")
    return data


def _disc_files(iso: Path) -> dict[str, bytes]:
    with iso.open("rb") as stream:
        total = os.fstat(stream.fileno()).st_size
        boot = _range(stream, 0, 0x440, total)
        if boot[:8] != b"GC6P01\0\0" or boot[0x1C:0x20] != bytes.fromhex("c2339f3d"):
            raise MenuSoundError("Unsupported menu audio source.")
        fst_offset, fst_size = struct.unpack_from(">II", boot, 0x424)
        if not 12 <= fst_size <= _MAX_FST:
            raise MenuSoundError("Invalid menu audio filesystem.")
        entries, _ = fst_inventory(_range(stream, fst_offset, fst_size, total))
        files = {entry["path"]: entry for entry in entries}
        if not _SOURCE_HASHES.keys() <= files.keys():
            raise MenuSoundError("Missing menu audio files.")
        for entry in entries:
            if entry["disc_offset"] > total or entry["size"] > total - entry["disc_offset"]:
                raise MenuSoundError("Invalid menu audio filesystem range.")
        result = {}
        for name, digest in _SOURCE_HASHES.items():
            entry = files[name]
            limit = _MAX_BANK if name.endswith(".samp") else _MAX_ARCHIVE
            if not 4 <= entry["size"] <= limit:
                raise MenuSoundError("Menu audio file exceeds limits.")
            raw = _range(stream, entry["disc_offset"], entry["size"], total)
            if _sha(raw) != digest:
                raise MenuSoundError("Menu audio differs from the original PAL game.")
            result[name] = raw
        return result


def _member(archive: bytes, members: list[dict], name: str) -> bytes:
    matches = [member for member in members if member["name"] == name]
    if len(matches) != 1:
        raise MenuSoundError("Missing native menu audio member.")
    row = matches[0]
    limit = _MAX_MEMBER if name == "common_rel" else 64 * 1024
    if not 0 < row["unpacked_size"] <= limit:
        raise MenuSoundError("Menu audio member exceeds limits.")
    start, size = row["offset"], row["stored_size"]
    if start < 0 or size < 0 or start > len(archive) or size > len(archive) - start:
        raise MenuSoundError("Invalid menu audio member range.")
    stored = archive[start:start + size]
    raw = decompress_lzss(stored, max_output=limit) if row["compression"] == "LZSS" else stored
    if len(raw) != row["unpacked_size"] or _sha(raw) != _MEMBER_HASHES[name]:
        raise MenuSoundError("Menu audio member differs from the original.")
    return raw


def _decode_dsp(data: bytes, coefficients: tuple[int, ...], samples: int) -> bytes:
    """Decode 8-byte DSP frames (14 signed nibbles) to little-endian PCM16."""
    if (type(samples) is not int or not 0 < samples <= _MAX_SAMPLES or len(coefficients) != 16
            or any(type(value) is not int or not -32768 <= value <= 32767 for value in coefficients)
            or len(data) != (samples + 13) // 14 * 8):
        raise MenuSoundError("Invalid menu audio DSP parameters.")
    pcm = bytearray(samples * 2)
    history, previous, index = 0, 0, 0
    for offset in range(0, len(data), 8):
        header = data[offset]
        predictor, shift = header >> 4, header & 15
        if predictor > 7:
            raise MenuSoundError("Invalid menu audio DSP predictor.")
        first, second = coefficients[predictor * 2:predictor * 2 + 2]
        for sample_index in range(min(14, samples - index)):
            packed = data[offset + 1 + sample_index // 2]
            value = (packed >> 4 if sample_index % 2 == 0 else packed & 15)
            if value >= 8:
                value -= 16
            value = ((value << shift) * 2048 + first * history + second * previous + 1024) >> 11
            value = max(-32768, min(32767, value))
            struct.pack_into("<h", pcm, index * 2, value)
            previous, history = history, value
            index += 1
    return bytes(pcm)


def _wav(pcm: bytes, rate: int) -> bytes:
    if type(rate) is not int or not 8000 <= rate <= 96000 or not pcm or len(pcm) % 2 or len(pcm) > _MAX_SAMPLES * 2:
        raise MenuSoundError("Invalid menu audio PCM parameters.")
    return (struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", len(pcm) + 36, b"WAVE", b"fmt ", 16,
                        1, 1, rate, rate * 2, 2, 16, b"data", len(pcm)) + pcm)


def _quiet_pcm(pcm: bytes) -> bytes:
    """Apply a deterministic 1/4 amplitude gain, rounding towards zero."""
    if not pcm or len(pcm) % 2 or len(pcm) > _MAX_SAMPLES * 2:
        raise MenuSoundError("Invalid menu audio gain input.")
    result = bytearray(len(pcm))
    for index, (value,) in enumerate(struct.iter_unpack("<h", pcm)):
        quiet = value // 4 if value >= 0 else -((-value) // 4)
        struct.pack_into("<h", result, index * 2, quiet)
    return bytes(result)


def _native_wavs(files: dict[str, bytes]) -> dict[str, bytes]:
    archive = files["common.fsys"]
    if len(archive) < 0x60 or struct.unpack_from(">I", archive, 0xC)[0] > 64:
        raise MenuSoundError("Invalid menu audio archive.")
    members = parse_fsys(archive)["members"]
    decoded = {name: _member(archive, members, name) for name in _MEMBER_HASHES}
    rel, proj, pool, sdir = (decoded[name] for name in _MEMBER_HASHES)
    if (struct.unpack_from(">5H", rel, 0x2191CA + 10) != (39, 40, 35, 36, 37) or
            struct.unpack_from(">I", rel, 0x2192D8)[0] != 8):
        raise MenuSoundError("Unverified native menu sound table.")
    # Project SFX records: ID, macro, priority/max/velocity/pan/key/reserved.
    sfx_base = struct.unpack_from(">I", proj, 0x1C)[0]
    count = struct.unpack_from(">H", proj, sfx_base)[0]
    if not 0 < count <= 512 or sfx_base + 4 + count * 10 > len(proj):
        raise MenuSoundError("Invalid menu audio project.")
    effects = {}
    for offset in range(sfx_base + 4, sfx_base + 4 + count * 10, 10):
        identifier, macro = struct.unpack_from(">HH", proj, offset)
        if identifier in effects:
            raise MenuSoundError("Duplicate menu audio effect ID.")
        effects[identifier] = (macro, proj[offset + 8])
    macros, position = {}, struct.unpack_from(">I", pool)[0]
    for _ in range(1024):
        if position + 4 > len(pool):
            raise MenuSoundError("Truncated menu audio macro table.")
        length = struct.unpack_from(">I", pool, position)[0]
        if length == 0xFFFFFFFF:
            break
        if length < 16 or length % 8 or position + length > len(pool):
            raise MenuSoundError("Invalid menu audio macro range.")
        identifier = struct.unpack_from(">H", pool, position + 4)[0]
        if identifier in macros:
            raise MenuSoundError("Duplicate menu audio macro ID.")
        macros[identifier] = list(struct.iter_unpack(">II", pool[position + 8:position + length]))
        position += length
    else:
        raise MenuSoundError("Menu audio macro count exceeds limits.")
    samples, position = {}, 0
    for _ in range(256):
        if position + 4 > len(sdir):
            raise MenuSoundError("Truncated menu sample directory.")
        if sdir[position:position + 4] == b"\xff" * 4:
            break
        if position + 32 > len(sdir):
            raise MenuSoundError("Truncated menu sample record.")
        identifier = struct.unpack_from(">H", sdir, position)[0]
        if identifier in samples:
            raise MenuSoundError("Duplicate menu sample ID.")
        samples[identifier] = position
        position += 32
    else:
        raise MenuSoundError("Menu sample count exceeds limits.")
    result = {}
    for key, (sound_id, fx, macro_id, sample_id, expected_rate, expected_frames) in _SOUNDS.items():
        native = rel[0x20E9D0 + sound_id * 12:0x20E9D0 + sound_id * 12 + 6]
        if native != b"\xc0\x06\x01\x0a" + struct.pack(">H", fx) or effects.get(fx, (None,))[0] != macro_id:
            raise MenuSoundError("Unverified menu sound to effect mapping.")
        commands = macros.get(macro_id, [])
        starts = [(word >> 8 & 0xFFFF, argument) for word, argument in commands if word & 255 == 0x10]
        notes = [word >> 8 & 127 for word, _ in commands if word & 255 == 0x19]
        if starts != [(sample_id, 0)] or len(notes) > 1 or sample_id not in samples:
            raise MenuSoundError("Unverified native menu sample command.")
        pos = samples[sample_id]
        start = struct.unpack_from(">I", sdir, pos + 4)[0]
        pitch, rate = sdir[pos + 12], struct.unpack_from(">H", sdir, pos + 14)[0]
        frames, loop_start, loop_length, parameters = struct.unpack_from(">IIII", sdir, pos + 16)
        if frames != expected_frames or loop_start or loop_length or parameters + 40 > len(sdir):
            raise MenuSoundError("Unverified native menu sample parameters.")
        note = notes[0] if notes else effects[fx][1]
        if note - pitch not in (0, 12):
            raise MenuSoundError("Unsupported native menu sample pitch.")
        playback_rate = rate * (2 if note - pitch == 12 else 1)
        size = (frames + 13) // 14 * 8
        bank = files["sound/snd_se.samp"]
        if playback_rate != expected_rate or start + size > len(bank):
            raise MenuSoundError("Invalid menu sample data range.")
        coefficients = struct.unpack_from(">16h", sdir, parameters + 8)
        pcm = _decode_dsp(bank[start:start + size], coefficients, frames)
        result[key] = _wav(_quiet_pcm(pcm), playback_rate)
    return result


def _cache_path(cache: Path, name: str) -> Path:
    target = cache / name
    if target.is_symlink() or target.resolve().parent != cache:
        raise MenuSoundError("Invalid menu sound cache path.")
    return target


def _atomic_write(target: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".menu-sound-", suffix=".tmp", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_wav(data: bytes, key: str) -> None:
    _, _, _, _, rate, frames = _SOUNDS[key]
    if len(data) != frames * 2 + 44 or len(data) > _MAX_WAV or data[:44] != _wav(bytes(frames * 2), rate)[:44]:
        raise MenuSoundError("Invalid cached menu sound format.")


def load_cached_menu_sounds(cache_dir: Path) -> dict[str, Path]:
    """Return an empty mapping for a missing or damaged cache; never play it."""
    try:
        if cache_dir.is_symlink():
            return {}
        cache = cache_dir.resolve()
        manifest = _cache_path(cache, _MANIFEST)
        if not manifest.is_file():
            return {}
        with manifest.open("rb") as stream:
            raw = stream.read(_MAX_MANIFEST + 1)
        if len(raw) > _MAX_MANIFEST:
            return {}
        document = json.loads(raw)
        if (not isinstance(document, dict) or set(document) != {"version", "gain", "assets"} or
                type(document["version"]) is not int or document["version"] != _VERSION or
                not isinstance(document["gain"], list) or len(document["gain"]) != 2 or
                any(type(value) is not int for value in document["gain"]) or document["gain"] != [1, 4] or
                not isinstance(document["assets"], dict) or set(document["assets"]) != set(_SOUNDS)):
            return {}
        result = {}
        for key, definition in _SOUNDS.items():
            _, _, _, _, rate, frames = definition
            row = document["assets"][key]
            if (not isinstance(row, dict) or set(row) != {"file", "sha256", "bytes", "sample_rate", "frames"} or
                    type(row["bytes"]) is not int or row["bytes"] != frames * 2 + 44 or
                    type(row["sample_rate"]) is not int or row["sample_rate"] != rate or
                    type(row["frames"]) is not int or row["frames"] != frames or
                    not isinstance(row["sha256"], str) or len(row["sha256"]) != 64 or
                    any(char not in "0123456789abcdef" for char in row["sha256"])):
                return {}
            filename = f"menu-{key}-v{_VERSION}-{row['sha256']}.wav"
            if row["file"] != filename:
                return {}
            target = _cache_path(cache, filename)
            with target.open("rb") as stream:
                data = stream.read(_MAX_WAV + 1)
            _validate_wav(data, key)
            if _sha(data) != row["sha256"]:
                return {}
            result[key] = target
        return result
    except (OSError, ValueError, TypeError, KeyError, RecursionError, struct.error):
        return {}


def extract_menu_sounds(iso: Path, cache_dir: Path) -> dict[str, Path]:
    """Read verified native sound resources; atomically publish three local WAVs."""
    try:
        files = _disc_files(iso)
        waves = _native_wavs(files)
        if cache_dir.is_symlink():
            raise MenuSoundError("Invalid menu sound cache directory.")
        cache = cache_dir.resolve()
        cache.mkdir(parents=True, exist_ok=True)
        assets = {}
        for key, data in waves.items():
            _validate_wav(data, key)
            digest = _sha(data)
            filename = f"menu-{key}-v{_VERSION}-{digest}.wav"
            _atomic_write(_cache_path(cache, filename), data)
            _, _, _, _, rate, frames = _SOUNDS[key]
            assets[key] = {"file": filename, "sha256": digest, "bytes": len(data),
                           "sample_rate": rate, "frames": frames}
        manifest = json.dumps({"version": _VERSION, "gain": [1, 4], "assets": assets}, sort_keys=True).encode("utf-8")
        _atomic_write(_cache_path(cache, _MANIFEST), manifest)
        result = load_cached_menu_sounds(cache)
        if set(result) != set(_SOUNDS):
            raise MenuSoundError("Menu sound cache verification failed.")
        return result
    except MenuSoundError:
        raise
    except (OSError, ValueError, TypeError, KeyError, struct.error) as error:
        raise MenuSoundError("Original menu sounds could not be loaded.") from error
