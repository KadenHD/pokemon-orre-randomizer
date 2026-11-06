"""Application icon and optional game pack; startup never needs a ROM or cache."""
from pathlib import Path
import hashlib
import json
import struct
import wave
import zlib
from .artwork import ArtworkError, _png_pixels, load_cached_artwork
from .i18n import LANGUAGES
from .menu_sounds import MenuSoundError, load_cached_menu_sounds


def application_icon() -> Path | None:
    path = Path(__file__).resolve().parent / "assets/app/icon.ico"
    return path if path.is_file() else None


def application_logo() -> Path | None:
    path = Path(__file__).resolve().parent / "assets/app/logo.png"
    return path if path.is_file() else None


def bundle_root() -> Path:
    # Sources, installed wheels and PyInstaller share the same package-relative path.
    return Path(__file__).resolve().parent / "assets" / "game"


def type_badge(game: str, language: str, type_id: int) -> Path | None:
    """Find the game's localized type badge in the offline interface pack."""
    if (game not in ("colosseum", "xd") or language not in LANGUAGES
            or type(type_id) is not int or not 0 <= type_id <= 255):
        return None
    path = bundle_root() / "types" / f"{game}-{language}-{type_id}.png"
    return path if path.is_file() and not path.is_symlink() else None


def interface_assets() -> tuple[dict[str, Path], dict[str, Path]]:
    root = bundle_root()
    try:
        images = load_cached_artwork(root / "images")
    except ArtworkError:
        images = {}
    try:
        sounds = load_cached_menu_sounds(root / "audio")
    except MenuSoundError:
        sounds = {}
    return images, sounds


def home_logos() -> dict[str, Path]:
    """Verified English artwork for the large home choices, entirely offline."""
    root = bundle_root() / "interface"
    try:
        metadata = root / "home-logos.json"
        if metadata.stat().st_size > 16 * 1024:
            return {}
        manifest = json.loads(metadata.read_text("utf-8"))
        if manifest["language"] != "en" or manifest["version"] != 1:
            return {}
        records = manifest["logos"]
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return {}
    result = {}
    for game, dimensions in (("colosseum", (1280, 543)), ("xd", (1280, 565))):
        try:
            record = records[game]
            path = root / f"{game}-logo-en-hd.png"
            if path.is_symlink() or not 33 <= path.stat().st_size <= 2 * 1024**2:
                continue
            data = path.read_bytes()
            if (len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]
                    or data[:16] != b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"
                    or struct.unpack(">II", data[16:24]) != dimensions
                    or data[24:29] != bytes((8, 6, 0, 0, 0))):
                continue
            result[game] = path
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            continue
    return result


def xd_logo() -> Path | None:
    """Read the verified English XD banner exported into the local game pack."""
    root = bundle_root() / "interface"
    try:
        metadata = root / "xd-logo-en.json"
        if metadata.stat().st_size > 16 * 1024:
            return None
        manifest = json.loads(metadata.read_text("utf-8"))
        path = root / "xd-logo-en.png"
        if (manifest["language"] != "en" or path.is_symlink()
                or not 32 <= path.stat().st_size <= 64 * 1024):
            return None
        data = path.read_bytes()
        if len(data) != manifest["bytes"] or hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            return None
        _png_pixels(data, (96, 32))
        return path
    except (OSError, ValueError, TypeError, KeyError, RecursionError, zlib.error):
        return None


MUSIC_FILES = {
    "home": ("pyrite.wav", "pyrite.json"),
    "colosseum": ("title.wav", "track.json"),
    "xd": ("xd-title.wav", "xd-title.json"),
}


def music_track(scene: str = "colosseum") -> Path | None:
    root = bundle_root() / "music"
    try:
        filename, metadata_name = MUSIC_FILES[scene]
        metadata = root / metadata_name
        if metadata.stat().st_size > 16 * 1024:
            return None
        manifest = json.loads(metadata.read_text("utf-8"))
        path = root / filename
        size = path.stat().st_size
        if path.is_symlink() or not 44 <= size <= 48 * 1024**2 or size != manifest["bytes"]:
            return None
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != manifest["sha256"]:
            return None
        with wave.open(str(path), "rb") as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (2, 2, 44100, "NONE"):
                return None
            if not 0 < stream.getnframes() <= 44100 * 180:
                return None
        return path
    except (OSError, ValueError, TypeError, KeyError, RecursionError, wave.Error, EOFError):
        return None


def menu_icon() -> Path | None:
    root = bundle_root() / "interface"
    try:
        metadata = root / "icon.json"
        if metadata.stat().st_size > 16 * 1024:
            return None
        manifest = json.loads(metadata.read_text("utf-8"))
        path = root / "pokeball.png"
        if path.is_symlink() or not 32 <= path.stat().st_size <= 16 * 1024:
            return None
        return path if hashlib.sha256(path.read_bytes()).hexdigest() == manifest["sha256"] else None
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return None
