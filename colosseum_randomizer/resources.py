"""Application icon and optional game pack; startup never needs a ROM or cache."""
from pathlib import Path
import hashlib
import json
import wave
from .artwork import ArtworkError, load_cached_artwork
from .menu_sounds import MenuSoundError, load_cached_menu_sounds


def application_icon() -> Path | None:
    path = Path(__file__).resolve().parent / "assets/app/icon.ico"
    return path if path.is_file() else None


def bundle_root() -> Path:
    # Sources, installed wheels and PyInstaller share the same package-relative path.
    return Path(__file__).resolve().parent / "assets" / "game"


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


def music_track() -> Path | None:
    root = bundle_root() / "music"
    try:
        metadata = root / "track.json"
        if metadata.stat().st_size > 16 * 1024:
            return None
        manifest = json.loads(metadata.read_text("utf-8"))
        path = root / "title.wav"
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
