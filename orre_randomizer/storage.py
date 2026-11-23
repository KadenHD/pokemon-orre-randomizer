"""Read-only disk accounting and explicit cleanup of old, rebuildable texture views.

ROMs, saves, backups, pack installations and runtimes are never cleanup targets.
Hard-linked images are counted once; their displayed logical size is not a
promise that deleting a texture view will recover that much disk space.
"""
from __future__ import annotations

from contextlib import ExitStack
import configparser
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time

from .play_folders import PlayLock, load_game
from .run_safety import assert_dolphin_idle
from .save_backups import checked_tree
from .service import Cancelled, UserError


@dataclass(frozen=True)
class CacheCandidate:
    path: Path
    logical_bytes: int
    reclaimable_bytes: int
    fingerprint: str


@dataclass
class StoragePlan:
    root: Path
    runs: tuple[Path, ...]
    categories: dict[str, int]
    candidates: list[CacheCandidate]
    physical_bytes: int
    free_bytes: int


def _files(path, cancel=None):
    if not path.exists():
        return []
    checked_tree(path, path.parent)
    result = []
    for parent, dirs, files in os.walk(path, followlinks=False):
        if cancel is not None and cancel.is_set():
            raise Cancelled("Opération annulée.")
        for name in (*dirs, *files):
            entry = Path(parent) / name
            if entry.is_symlink() or entry.is_junction():
                raise UserError("Le dossier contient un lien externe. Opération refusée.")
        result.extend(Path(parent) / name for name in files)
    return result


def _fingerprint(path, cancel=None):
    stamp = hashlib.sha256()
    for item in sorted(_files(path, cancel)):
        info = item.stat()
        stamp.update(json.dumps((item.relative_to(path).as_posix(), info.st_dev, info.st_ino,
                                info.st_size, info.st_mtime_ns, info.st_nlink)).encode())
    return stamp.hexdigest()


def scan_storage(root, entries, *, cancel=None, now=None):
    root = Path(root).expanduser().absolute()
    if root.is_symlink() or root.is_junction():
        raise UserError("Le dossier contient un lien externe. Opération refusée.")
    root = root.resolve()
    protected = set()
    runs = []
    categories = {"roms": 0, "saves": 0, "backups": 0, "packs": 0,
                  "runtimes": 0, "views": 0, "audio": 0, "downloads": 0}
    all_files = {}

    def account(category, files):
        seen = set()
        for path in files:
            info = path.stat()
            key = (info.st_dev, info.st_ino)
            if key not in seen:
                categories[category] += info.st_size
                seen.add(key)
            all_files[key] = info.st_size

    for entry in entries:
        path = Path(entry["path"])
        try:
            data = load_game(path)
        except (OSError, ValueError, UserError) as error:
            raise UserError("Une partie est introuvable. Retirez sa référence de la bibliothèque avant le nettoyage.") from error
        runs.append(path.parent)
        checked_tree(path.parent / data["rom"], path.parent)
        account("roms", [path.parent / data["rom"]])
        account("saves", _files(path.parent / "DolphinUser/GC", cancel)
                + _files(path.parent / "DolphinUser/StateSaves", cancel))
        account("backups", _files(path.parent / "SaveBackups", cancel))
        config = configparser.ConfigParser(interpolation=None)
        config.read(path.parent / "DolphinUser/Config/Dolphin.ini", encoding="utf-8")
        value = config.get("General", "LoadPath", fallback="")
        if value:
            load = Path(value).resolve()
            for parent in (load, *load.parents):
                if parent.parent == root / "TextureViews":
                    protected.add(parent)
    for category, directory in (("packs", "TexturePacks"), ("runtimes", "Runtimes"),
                                ("views", "TextureViews"), ("audio", "AudioBanks"),
                                ("downloads", "Downloads")):
        account(category, _files(root / directory, cancel))
    candidates = []
    views = root / "TextureViews"
    now = time.time() if now is None else now
    for path in sorted(views.iterdir()) if views.is_dir() else ():
        if (not path.is_dir() or path in protected or path.name.startswith(".")
                or not re.fullmatch(r"(colosseum|xd)-[A-Za-z0-9.-]+", path.name)):
            continue
        marker = path / "complete.json"
        if not marker.is_file() or marker.stat().st_size > 65536 or now - marker.stat().st_mtime < 86400:
            continue
        try:
            metadata = json.loads(marker.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(metadata, dict) or not isinstance(metadata.get("pack"), str):
            continue
        files = _files(path, cancel)
        inodes = {}
        for item in files:
            info = item.stat()
            key = info.st_dev, info.st_ino
            count, _, _ = inodes.get(key, (0, info.st_nlink, info.st_size))
            inodes[key] = count + 1, info.st_nlink, info.st_size
        logical = sum(size for _, _, size in inodes.values())
        freed = sum(size for count, links, size in inodes.values() if count == links)
        candidates.append(CacheCandidate(path, logical, freed, _fingerprint(path, cancel)))
    existing = next((p for p in (root, *root.parents) if p.exists()), root)
    return StoragePlan(root, tuple(runs), categories, candidates, sum(all_files.values()), shutil.disk_usage(existing).free)


def cleanup_caches(plan, selected, *, cancel=None, current_entries=None):
    requested = {Path(path).resolve() for path in selected}
    candidates = {item.path: item for item in plan.candidates}
    if not requested or requested - candidates.keys():
        raise UserError("Sélectionnez un cache proposé par cette analyse.")
    with ExitStack() as locks:
        if current_entries is not None:
            paths = {Path(row["path"]).resolve() for row in current_entries()}
            if paths != {folder / "game.json" for folder in plan.runs}:
                raise UserError("Le cache a changé depuis l’analyse. Relancez l’analyse.")
        for folder in sorted(plan.runs):
            lock = PlayLock(folder); locks.callback(lock.close)
        assert_dolphin_idle()
        root = plan.root
        if root.is_symlink() or root.is_junction() or root.resolve() != root:
            raise UserError("Le dossier contient un lien externe. Opération refusée.")
        if any((root / "TexturePacks").glob("*.lock")):
            raise UserError("Attendez la fin de l’installation des packs HD avant le nettoyage.")
        # Re-scan registered references and fingerprints before removing anything.
        fresh = scan_storage(root, [{"path": str(folder / "game.json")} for folder in plan.runs], cancel=cancel)
        fresh_candidates = {item.path: item for item in fresh.candidates}
        for key in requested:
            item = candidates[key]
            if (key not in fresh_candidates or item.fingerprint != fresh_candidates[key].fingerprint
                    or item.path.parent != root / "TextureViews"):
                raise UserError("Le cache a changé depuis l’analyse. Relancez l’analyse.")
            checked_tree(item.path, root)
        removed = []
        for key in sorted(requested):
            if cancel is not None and cancel.is_set():
                break
            assert_dolphin_idle()
            item = candidates[key]
            checked_tree(item.path, root)
            if _fingerprint(item.path) != item.fingerprint:
                raise UserError("Le cache a changé depuis l’analyse. Relancez l’analyse.")
            shutil.rmtree(item.path)
            removed.append(str(key))
        return removed
