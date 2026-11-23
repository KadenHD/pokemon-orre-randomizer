"""Explicit launcher upgrades, independent of a run's ROM and frozen pack pins."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading

from . import __version__
from .hd_packs import PACKS
from .service import Cancelled, UserError
from .update_service import _version_key

RECEIPT = "launcher-version.json"


def native_launcher_path():
    return Path(__file__).parent / "_native" / ("OrreLauncher.exe" if os.name == "nt" else "OrreLauncher")


def _read(path: Path, limit: int):
    if path.is_symlink() or path.is_junction():
        raise UserError("Les fichiers du lanceur doivent rester dans le dossier de partie.")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > limit:
        raise UserError("Les fichiers du lanceur sont invalides.")
    return path.read_bytes()


def launcher_version(folder: Path, manifest):
    """A separate receipt survives saves by launchers predating this feature."""
    raw = _read(folder / RECEIPT, 16384)
    if raw is None:
        return manifest.get("orre_version", __version__)
    try:
        receipt = json.loads(raw)
        descriptor = _read(folder / "launcher-runtime.txt", 16384)
        if (receipt["schema"] != 1 or _version_key(receipt["version"]) is None
                or receipt["creation_version"] != manifest.get("orre_version", __version__)
                or descriptor is None):
            raise ValueError("Invalid launcher upgrade receipt")
        digest = hashlib.sha256(descriptor).hexdigest()
        if digest != receipt["descriptor_sha256"]:
            previous = receipt.get("previous", {})
            if digest != previous.get("descriptor_sha256") or _version_key(previous.get("version")) is None:
                raise ValueError("Launcher descriptor differs from its receipt")
            return previous["version"]
        return receipt["version"]
    except (ValueError, KeyError, TypeError) as error:
        raise UserError("Les fichiers du lanceur sont invalides.") from error


def upgrade_status(path: Path):
    from .play_folders import load_game, hd_game_requirements
    manifest = load_game(path)
    previous = launcher_version(path.parent, manifest)
    before, after = _version_key(previous), _version_key(__version__)
    if before is None or after is None:
        raise UserError("La version de ce lanceur est inconnue.")
    if before > after:
        raise UserError("Ce lanceur utilise une version plus récente de l’outil.")
    pins = manifest.get("packs", {manifest["game"]: manifest["pack"]})
    if (not isinstance(pins, dict) or pins.get(manifest["game"]) != manifest["pack"]
            or any(pins.get(game) != PACKS[game].key for game in hd_game_requirements(manifest))):
        raise UserError("Cette version de l’outil ne prend pas en charge les packs figés de cette partie.")
    return {"previous_version": previous, "version": __version__, "available": before < after}


def refresh_receipt(folder: Path, manifest):
    """Keep an existing upgrade receipt consistent after a runtime-cache repair."""
    if _read(folder / RECEIPT, 16384) is not None:
        descriptor = _read(folder / "launcher-runtime.txt", 16384)
        if descriptor is None:
            raise UserError("Les fichiers du lanceur sont invalides.")
        record = {"schema": 1, "version": __version__,
            "creation_version": manifest.get("orre_version", __version__),
            "descriptor_sha256": hashlib.sha256(descriptor).hexdigest()}
        _replace(folder / RECEIPT, json.dumps(record, indent=2).encode("utf-8") + b"\n")


def _replace(path: Path, payload: bytes):
    handle, temporary = tempfile.mkstemp(prefix=".launcher-update-", dir=path.parent)
    pending = Path(temporary)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def upgrade_launcher(path: Path, *, cancel=None):
    """Publish three small launcher files, retaining a backup and rolling back errors.

    game.json, Game/, DolphinUser/ settings/cards and Textures/ are never edited.
    The existing per-run OS lock prevents upgrading a game currently being played.
    """
    from .play_folders import PlayLock, load_game, _runtime
    path = Path(path).expanduser().resolve()
    folder = path.parent
    cancel = cancel if cancel is not None else threading.Event()
    load_game(path)  # Validate the selected folder before creating its lock.
    if cancel.is_set():
        raise Cancelled("Opération annulée.")
    lock = PlayLock(folder)
    try:
        # Another process may have upgraded the run since the dialog opened.
        # Resolve its version and pins only after holding the run's lock.
        status = upgrade_status(path)
        if not status["available"]:
            return {**status, "changed": False}
        original_manifest = path.read_bytes()
        manifest = load_game(path)
        launcher = "Launcher.exe" if os.name == "nt" else "Launcher"
        names = (launcher, "launcher-runtime.txt", RECEIPT)
        original = {name: _read(folder / name, 8 * 1024 * 1024 if name == launcher else 16384)
                    for name in names}
        command = _runtime(Path(manifest["shared"]), cancel=cancel)
        if any("\n" in part or "\r" in part for part in command):
            raise UserError("Les fichiers du lanceur sont invalides.")
        payload = _read(native_launcher_path(), 8 * 1024 * 1024)
        if payload is None:
            raise UserError("Le lanceur est absent. Réinstallez l’application complète.")
        descriptor = ("\n".join(["ORRE-LAUNCHER-1", *command]) + "\n").encode("utf-8")
        record = {"schema": 1, "version": __version__,
            "creation_version": manifest.get("orre_version", __version__),
            "descriptor_sha256": hashlib.sha256(descriptor).hexdigest()}
        if original["launcher-runtime.txt"] is not None:
            record["previous"] = {"version": status["previous_version"],
                "descriptor_sha256": hashlib.sha256(original["launcher-runtime.txt"]).hexdigest()}
        receipt = json.dumps(record, indent=2).encode("utf-8") + b"\n"
        # The descriptor is the commit point. The receipt accepts its prior
        # bytes too, so an interrupted publication still opens the old runtime.
        replacements = {launcher: payload, RECEIPT: receipt, "launcher-runtime.txt": descriptor}
        if cancel.is_set():
            raise Cancelled("Opération annulée.")
        if path.read_bytes() != original_manifest or any(
                _read(folder / name, 8 * 1024 * 1024) != original[name] for name in names):
            raise UserError("Les fichiers de cette partie ont changé. Réessayez après avoir fermé son lanceur.")
        backups = folder / "LauncherBackups"
        if backups.is_symlink() or backups.is_junction():
            raise UserError("Les fichiers du lanceur doivent rester dans le dossier de partie.")
        backups.mkdir(exist_ok=True)
        if backups.resolve().parent != folder.resolve():
            raise UserError("Les fichiers du lanceur doivent rester dans le dossier de partie.")
        backup = Path(tempfile.mkdtemp(prefix="launcher-", dir=backups))
        for name, raw in original.items():
            if raw is not None:
                (backup / name).write_bytes(raw)
        (backup / "backup.json").write_text(json.dumps({"schema": 1,
            "previous_version": status["previous_version"],
            "files": {name: hashlib.sha256(raw).hexdigest() if raw is not None else None
                      for name, raw in original.items()}}, indent=2) + "\n", encoding="utf-8")
        published = []
        try:
            for name, raw in replacements.items():
                _replace(folder / name, raw)
                published.append(name)
            if os.name != "nt":
                (folder / launcher).chmod(0o755)
        except BaseException:
            for name in reversed(published):
                if original[name] is None:
                    (folder / name).unlink(missing_ok=True)
                else:
                    _replace(folder / name, original[name])
            raise
        return {**status, "changed": True, "backup_directory": str(backup)}
    finally:
        lock.close()
