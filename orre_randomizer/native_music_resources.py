"""Private, verified music resources extracted from the user's own disc.

No game assets are bundled with the program. All source reads are read-only;
the cache records content hashes, not local source paths.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import tempfile
import threading

from .engine.analyze_game import parse_fsys
from .engine.rebuild_iso import decoded_member
from .engine.survey_assets import fst_inventory

MAX_ASSET = 128 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024


def selected_resource(game_id: str, name: str) -> bool:
    if game_id.startswith("GC6"):
        return name in {"common.fsys", "bgm_archive.fsys", "sound/snd_music.samp"}
    if game_id.startswith("GXX"):
        return "/" not in name and name.startswith(("stm_bgm_", "stm_me_")) and name.endswith(".fsys")
    return False


def _safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(part in ("..", ".") for part in path.parts) or "\\" in name or ":" in name:
        raise ValueError("Unsafe music resource path")
    return path


class MusicDisc:
    """Bounded read-only ISO/GCM reader; RVZ conversion happens while staging."""

    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        with self.path.open("rb") as source:
            self.boot = source.read(0x440)
            if len(self.boot) != 0x440 or self.boot[0x1c:0x20] != b"\xc2\x33\x9f\x3d":
                raise ValueError("Music source must be a GameCube ISO/GCM")
            offset, size = struct.unpack_from(">II", self.boot, 0x424)
            if not 12 <= size <= 16 * 1024 * 1024 or offset + size > self.size:
                raise ValueError("Invalid music source FST bounds")
            source.seek(offset)
            self.entries = {entry["path"]: entry for entry in fst_inventory(source.read(size))[0]}
        self.game_id = self.boot[:6].decode("ascii")
        self.revision = self.boot[7]

    def file(self, name):
        entry = self.entries[name]
        size, offset = entry["size"], entry["disc_offset"]
        if not 0 < size <= MAX_ASSET or offset < 0x440 or offset + size > self.size:
            raise ValueError("Music resource outside disc bounds")
        with self.path.open("rb") as source:
            source.seek(offset)
            data = source.read(size)
        if len(data) != size:
            raise ValueError("Truncated music resource")
        return data

    def archive(self, name):
        data = self.file(name)
        return parse_fsys(data), data

    def member(self, name, member):
        archive, data = self.archive(name)
        row = next(row for row in archive['members'] if row['name'] == member)
        if not 0 < row['unpacked_size'] <= MAX_ASSET:
            raise ValueError('Decoded music member exceeds bounds')
        return decoded_member(data, row)


def prepare_music_assets(source, destination, *, game_id, cancel=None, progress=None):
    """Atomically create or verify a shared source-specific original-bank cache."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        assets = MusicAssets(destination)
        if assets.game_id != game_id or assets.revision != 0:
            raise ValueError('Shared music cache belongs to another game')
        for name in assets.entries:
            assets.file(name)
        return assets.manifest
    with tempfile.TemporaryDirectory(prefix='orre-music-cache-', dir=destination.parent) as temporary:
        pending = Path(temporary) / 'Audio'
        manifest = _stage_music_assets(source, pending, game_id=game_id, cancel=cancel, progress=progress)
        try:
            pending.rename(destination)
        except FileExistsError:
            # Another concurrent folder creation may have published the same cache.
            winner = MusicAssets(destination)
            if winner.manifest != manifest:
                raise ValueError('Concurrent shared music cache differs')
        return manifest


def _stage_music_assets(source, destination, *, game_id, cancel=None, progress=None):
    """Create a new cache from ISO/GCM/RVZ; never overwrite an existing cache.

    Call during play-folder creation, before publication. ``destination`` must
    be a nonexistent directory in the caller's temporary play folder. Failed
    staging is left inside that temporary folder for its owner to clean up.
    """
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError("Music asset destination already exists")
    cancel = cancel or threading.Event()
    if source.suffix.lower() == ".rvz":
        from .disc_images import convert
        with tempfile.TemporaryDirectory(prefix="orre-music-", dir=destination.parent) as temporary:
            raw = Path(temporary) / "source.iso"
            convert(source, raw, cancel)
            return _stage_music_assets(raw, destination, game_id=game_id, cancel=cancel, progress=progress)
    disc = MusicDisc(source)
    if disc.game_id != game_id or disc.revision != 0 or game_id not in ("GC6P01", "GXXP01"):
        raise ValueError("Music resources require the matching supported revision-0 disc")
    names = sorted(name for name in disc.entries if selected_resource(game_id, name))
    if (game_id.startswith("GC6") and len(names) != 3) or not names:
        raise ValueError("Required original music resources are missing")
    if sum(disc.entries[name]["size"] for name in names) > MAX_TOTAL:
        raise ValueError("Music resources exceed cache bounds")
    destination.mkdir()
    files = []
    for index, name in enumerate(names):
        if cancel.is_set():
            raise InterruptedError("Music preparation cancelled")
        data = disc.file(name)
        path = destination.joinpath(*_safe_name(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as target:
            target.write(data)
        files.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        if progress:
            progress(index + 1, len(names))
    manifest = {"schema_version": 1, "game_id": game_id, "revision": disc.revision, "files": files}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["resource_sha256"] = hashlib.sha256(encoded).hexdigest()
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


class MusicAssets:
    """Cache reader with per-read hash verification and no arbitrary file access."""

    def __init__(self, directory):
        self.path = Path(directory).resolve()
        manifest_path = self.path / "manifest.json"
        if manifest_path.stat().st_size > 256 * 1024:
            raise ValueError("Music manifest exceeds bounds")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        canonical = dict(self.manifest)
        digest = canonical.pop("resource_sha256", None)
        if hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != digest:
            raise ValueError("Music manifest digest mismatch")
        self.game_id = self.manifest["game_id"]
        self.revision = self.manifest["revision"]
        rows = self.manifest["files"]
        if self.manifest.get("schema_version") != 1 or len(rows) > 1024:
            raise ValueError("Unsupported music manifest")
        self.entries = {}
        for row in rows:
            name = row["path"]
            _safe_name(name)
            if name in self.entries or not selected_resource(self.game_id, name) or not 0 < row["bytes"] <= MAX_ASSET:
                raise ValueError("Invalid music manifest entry")
            self.entries[name] = row
        if sum(row["bytes"] for row in rows) > MAX_TOTAL:
            raise ValueError("Music cache exceeds bounds")

    def file(self, name):
        row = self.entries[name]
        path = self.path.joinpath(*_safe_name(name).parts).resolve()
        if not path.is_relative_to(self.path) or path.stat().st_size != row["bytes"]:
            raise ValueError("Music asset path or size differs")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("Music asset hash differs")
        return data

    def archive(self, name):
        data = self.file(name)
        return parse_fsys(data), data

    def member(self, name, member):
        archive, data = self.archive(name)
        row = next(row for row in archive["members"] if row["name"] == member)
        if not 0 < row["unpacked_size"] <= MAX_ASSET:
            raise ValueError("Decoded music member exceeds bounds")
        return decoded_member(data, row)
