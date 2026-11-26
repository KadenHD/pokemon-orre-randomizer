"""Verified card snapshots and transactional restore inside one isolated run."""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import Event
import uuid

from .play_folders import PlayLock, load_game, validate_profile_root, _publish_folder
from .run_safety import assert_dolphin_idle
from .service import UserError

CARD_NAME = re.compile(r"MemoryCard[AB]\.(EUR|USA|JAP)\.raw")
SNAPSHOT_NAME = re.compile(r"\d{8}T\d{12}Z-[a-f0-9]{8}")
MAX_CARD_BYTES = 128 * 1024**2
MAX_BACKUP_BYTES = 256 * 1024**2
KEEP = 5


def checked_tree(path, root):
    """Refuse reparse-point traversal before reading or removing owned trees."""
    root, path = Path(root).absolute(), Path(path).absolute()
    if path == root or not path.is_relative_to(root) or not path.resolve().is_relative_to(root.resolve()):
        raise UserError("Le dossier contient un lien externe. Opération refusée.")
    for entry in (path, *path.parents):
        if entry.is_symlink() or entry.is_junction():
            raise UserError("Le dossier contient un lien externe. Opération refusée.")
        if entry == root:
            break
    if path.is_dir():
        for parent, dirs, files in os.walk(path, followlinks=False):
            for name in (*dirs, *files):
                entry = Path(parent) / name
                if entry.is_symlink() or entry.is_junction():
                    raise UserError("Le dossier contient un lien externe. Opération refusée.")
    return path


@contextmanager
def exclusive_card(path):
    """Deny concurrent file reads/writes on Windows, retaining rename support."""
    if os.name != "nt":
        with path.open("rb") as source:
            import fcntl
            fcntl.flock(source, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield source
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 4, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise UserError("La carte mémoire est utilisée ou inaccessible. Fermez Dolphin puis réessayez.")
    descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    with os.fdopen(descriptor, "rb") as source:
        yield source


def _hash(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _identity(data):
    return {"game_id": data["game_id"], "seed": data["seed"], "rom_sha256": data.get("rom_sha256")}


def _root(folder):
    root = Path(folder) / "SaveBackups"
    checked_tree(root, folder)
    return root


def list_backups(folder):
    root = _root(Path(folder))
    if not root.exists():
        return []
    result = []
    for entry in sorted(root.iterdir(), reverse=True):
        if not entry.is_dir() or not SNAPSHOT_NAME.fullmatch(entry.name):
            continue
        try:
            checked_tree(entry, root)
            path = entry / "snapshot.json"
            if path.stat().st_size > 16384:
                continue
            data = json.loads(path.read_text("utf-8"))
            if data.get("schema") != 1 or not isinstance(data.get("cards"), dict):
                continue
            cards = data["cards"]
            if not 1 <= len(cards) <= 6 or any(not CARD_NAME.fullmatch(name) for name in cards):
                continue
            datetime.fromisoformat(data["created"])
            if any(type(value.get("size")) is not int or not 0 < value["size"] <= MAX_CARD_BYTES
                   or not re.fullmatch(r"[a-f0-9]{64}", value.get("sha256", "")) for value in cards.values()):
                continue
            size = sum(value["size"] for value in cards.values())
            if not 0 < size <= MAX_BACKUP_BYTES:
                continue
            result.append(dict(data, name=entry.name, bytes=size))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    return result


def _copy_cards(folder, manifest, *, reason):
    validate_profile_root(folder)
    assert_dolphin_idle(folder, manifest)
    cards = sorted((folder / "DolphinUser/GC").glob("MemoryCard*.*"))
    cards = [p for p in cards if CARD_NAME.fullmatch(p.name)]
    if not cards:
        return None
    root = _root(folder)
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=root) as temporary, ExitStack() as opened:
        stage = Path(temporary)
        total, values = 0, {}
        for card in cards:
            checked_tree(card, folder)
            stream = opened.enter_context(exclusive_card(card))
            before = os.fstat(stream.fileno())
            if not 0 < before.st_size <= MAX_CARD_BYTES:
                raise UserError("La carte mémoire est invalide ou trop volumineuse.")
            total += before.st_size
            if total > MAX_BACKUP_BYTES:
                raise UserError("La carte mémoire est invalide ou trop volumineuse.")
            target = stage / card.name
            with target.open("xb") as output:
                shutil.copyfileobj(stream, output, 1024**2)
                output.flush(); os.fsync(output.fileno())
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise UserError("La carte mémoire a changé pendant la copie. Fermez Dolphin puis réessayez.")
            values[card.name] = {"size": before.st_size, "sha256": _hash(target)}
        existing = list_backups(folder)
        identity = _identity(manifest)
        if existing and existing[0].get("identity") == identity and existing[0]["cards"] == values:
            # Do not reuse an entry whose on-disk contents have been damaged.
            try:
                intact = all(_hash(root / existing[0]["name"] / name) == value["sha256"] for name, value in values.items())
            except OSError:
                intact = False
            if intact:
                return existing[0]["name"]
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
        metadata = {"schema": 1, "identity": identity, "created": datetime.now(timezone.utc).isoformat(),
                    "reason": reason, "cards": values}
        (stage / "snapshot.json").write_text(json.dumps(metadata, indent=2), "utf-8")
        assert_dolphin_idle(folder, manifest)
        destination = root / name
        if os.name == "nt":
            # Reuse the bounded atomic publication used by game folders:
            # Windows scanners may briefly retain newly written files.
            _publish_folder(stage, destination, Event())
        else:
            stage.rename(destination)
    retained, size = 0, 0
    for snapshot in list_backups(folder):
        size += snapshot["bytes"]
        if retained < KEEP and (size <= MAX_BACKUP_BYTES or retained == 0):
            retained += 1
        else:
            path = checked_tree(root / snapshot["name"], root)
            shutil.rmtree(path)
    return name


def backup_cards(folder, manifest=None, *, locked=False, reason="before-launch"):
    folder = Path(folder).resolve()
    manifest = load_game(folder / "game.json") if manifest is None else manifest
    with ExitStack() as stack:
        if not locked:
            lock = PlayLock(folder); stack.callback(lock.close)
        return _copy_cards(folder, manifest, reason=reason)


def restore_backup(folder, name):
    folder = Path(folder).resolve()
    manifest = load_game(folder / "game.json")
    if not isinstance(name, str) or not SNAPSHOT_NAME.fullmatch(name):
        raise UserError("Cette copie de sauvegarde est invalide ou endommagée.")
    lock = PlayLock(folder)
    try:
        assert_dolphin_idle(folder, manifest)
        root = _root(folder)
        snapshot = next((item for item in list_backups(folder) if item["name"] == name), None)
        if snapshot is None or snapshot.get("identity") != _identity(manifest):
            raise UserError("Cette copie ne correspond pas à cette partie.")
        directory = checked_tree(root / name, root)
        for card, details in snapshot["cards"].items():
            source = directory / card
            if (not source.is_file() or source.stat().st_size != details["size"]
                    or _hash(source) != details["sha256"]):
                raise UserError("Cette copie de sauvegarde est invalide ou endommagée.")
        # Preserve current data before replacement; retention is applied only after
        # the requested snapshot has already been copied into the restore stage.
        gc = folder / "DolphinUser/GC"
        gc.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".restore-", dir=gc) as temporary:
            stage = Path(temporary)
            for card in snapshot["cards"]:
                shutil.copyfile(directory / card, stage / card)
                if _hash(stage / card) != snapshot["cards"][card]["sha256"]:
                    raise UserError("Cette copie de sauvegarde est invalide ou endommagée.")
            _copy_cards(folder, manifest, reason="before-restore")
            committed = []
            rollback = stage / "previous"; rollback.mkdir()
            with ExitStack() as handles:
                for card in snapshot["cards"]:
                    current = gc / card
                    checked_tree(current, folder)
                    if current.exists():
                        stream = handles.enter_context(exclusive_card(current))
                        with (rollback / card).open("xb") as output:
                            shutil.copyfileobj(stream, output)
                # Windows replacement opens the destination internally. Finish
                # exclusive snapshot reads first, retain PlayLock, then recheck
                # external emulator use immediately before atomic publication.
                handles.close()
                assert_dolphin_idle(folder, manifest)
                try:
                    for card in snapshot["cards"]:
                        os.replace(stage / card, gc / card)
                        committed.append(card)
                except OSError:
                    for card in reversed(committed):
                        previous = rollback / card
                        if previous.exists():
                            os.replace(previous, gc / card)
                        else:
                            (gc / card).unlink()
                    raise
    finally:
        lock.close()
