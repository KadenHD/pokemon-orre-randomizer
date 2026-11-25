"""Transactional game folders and isolated Dolphin profiles.

A small launcher references a shared, versioned Orre runtime. ROMs, memory cards
and state files are never copied from a personal Dolphin profile implicitly.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time

from . import __version__, APP_EXECUTABLE
from .disc_images import SUFFIXES
from .hd_packs import PACKS, PackStore, shared_root, checkpoint, required_pack_games
from .i18n import Message, LANGUAGES
from .service import Cancelled, UserError, randomize, file_hash
from .play_display import acceleration_target, display_mode, configure_projection


class PlayLock:
    """An OS lock releases automatically after a launcher crash; no stale PID file."""
    def __init__(self, folder):
        validate_profile_root(Path(folder))
        path = Path(folder) / "DolphinUser/.launcher.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("a+b")
        if os.fstat(self.handle.fileno()).st_size == 0:
            self.handle.write(b"\0"); self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.handle.close(); self.handle = None
            raise UserError("Cette partie est déjà ouverte dans un autre lanceur.") from error

    def close(self):
        if self.handle is not None:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close(); self.handle = None


@dataclass(frozen=True)
class PlayFolderRequest:
    folder: Path
    dolphin: Path
    graphics: str = "original"
    shared: Path | None = None
    language: str = "en"


def find_dolphin(preferred="") -> Path | None:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    candidates = [preferred, os.environ.get("DOLPHIN_PATH", "")]
    candidates += [shutil.which(name) or "" for name in ("Dolphin.exe", "dolphin-emu", "dolphin")]
    candidates += [base / "Dolphin-x64/Dolphin.exe", base / "Dolphin/Dolphin.exe"]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(env):
            parent = Path(os.environ[env])
            candidates += [parent / "Dolphin Emulator/Dolphin.exe", parent / "Dolphin/Dolphin.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def validate_dolphin(path: Path):
    path = path.expanduser().resolve()
    if not path.is_file() or path.name.lower() not in ("dolphin.exe", "dolphin-emu", "dolphin"):
        raise UserError("Choisissez l’exécutable Dolphin pour lancer cette partie.")
    return path


def validate_request(request, source: Path, suffix: str, seed: str):
    folder = request.folder.expanduser().absolute()
    if os.path.lexists(folder) or not folder.parent.is_dir():
        raise UserError("Choisissez un nouveau dossier de partie dans un dossier existant.")
    if folder.resolve() == source.resolve() or source.suffix.lower() not in SUFFIXES or not source.is_file():
        raise UserError("Sélectionnez un fichier ISO, GCM ou RVZ existant.")
    if suffix.lower() not in SUFFIXES or not seed.strip() or len(seed.encode("utf-8")) > 256:
        raise UserError("Choisissez un format de ROM et une seed valides.")
    validate_dolphin(request.dolphin)
    if request.graphics not in ("original", "hd") or request.language not in LANGUAGES:
        raise UserError("Les réglages du lanceur sont invalides.")
    return folder


def _runtime(root: Path, *, cancel=None):
    if not getattr(sys, "frozen", False):
        python = Path(sys.executable)
        if sys.platform == "win32" and python.with_name("pythonw.exe").is_file():
            python = python.with_name("pythonw.exe")
        return [str(python), str(Path(__file__).resolve().parents[1]), "-m", "orre_randomizer.gui"]
    source = Path(sys.executable).resolve().parent
    fingerprint = hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
    target = root / "Runtimes" / (__version__ + "-" + fingerprint[:16])
    executable = target / Path(sys.executable).name
    if executable.is_file():
        if hashlib.sha256(executable.read_bytes()).hexdigest() != fingerprint:
            raise UserError("Le runtime partagé a changé. Réinstallez le lanceur de cette partie.")
        return [str(executable), str(target)]
    try:
        owned = json.loads((source / "update-files.json").read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise UserError("Le runtime du lanceur est incomplet. Réinstallez l’application complète.") from error
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".runtime-", dir=target.parent) as temporary:
        stage = Path(temporary) / "runtime"
        stage.mkdir()
        for name in owned:
            if cancel is not None and cancel.is_set():
                raise Cancelled("Opération annulée.")
            relative = Path(name)
            path = source / relative
            if (relative.is_absolute() or ".." in relative.parts or path.is_symlink()
                    or not path.resolve().is_relative_to(source) or not path.is_file()):
                raise UserError("Le runtime du lanceur contient un fichier invalide.")
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        if not (stage / executable.name).is_file():
            raise UserError("L’exécutable du lanceur partagé est absent.")
        if cancel is not None and cancel.is_set():
            raise Cancelled("Opération annulée.")
        try:
            stage.rename(target)
        except FileExistsError:
            if not executable.is_file():
                raise
    return [str(executable), str(target)]


def install_launcher(folder: Path, shared: Path):
    native = Path(__file__).resolve().parent / "_native" / ("OrreLauncher.exe" if os.name == "nt" else "OrreLauncher")
    if not native.is_file():
        raise UserError("Le lanceur est absent. Réinstallez l’application complète.")
    command = _runtime(shared)
    if any("\n" in part or "\r" in part for part in command):
        raise UserError("Le chemin du runtime du lanceur est invalide.")
    shutil.copyfile(native, folder / ("Launcher.exe" if os.name == "nt" else "Launcher"))
    if os.name != "nt":
        (folder / "Launcher").chmod(0o755)
    (folder / "launcher-runtime.txt").write_text("\n".join(["ORRE-LAUNCHER-1", *command]) + "\n", encoding="utf-8")


def launcher_command(path: Path):
    """Retain a verified cached runtime; repair a missing current-version launcher."""
    data = load_game(path)
    from .launcher_updates import launcher_version
    version = launcher_version(path.parent, data)
    shared = Path(data["shared"])
    runtime = None
    descriptor = path.parent / "launcher-runtime.txt"
    if descriptor.is_file() and descriptor.stat().st_size <= 16384:
        lines = descriptor.read_text("utf-8").splitlines()
        if len(lines) == 3 and lines[0] == "ORRE-LAUNCHER-1":
            executable, directory = Path(lines[1]), Path(lines[2])
            match = re.fullmatch(re.escape(version) + r"-([a-f0-9]{16})", directory.name) if version else None
            if (match and executable.is_file() and executable.name == APP_EXECUTABLE + ".exe"
                    and not executable.is_symlink() and not directory.is_symlink() and not directory.is_junction()
                    and directory.resolve().parent == (shared / "Runtimes").resolve()
                    and executable.resolve().parent == directory.resolve()
                    and file_hash(executable, threading.Event()).startswith(match[1])):
                runtime = [str(executable), str(directory)]
    if runtime is None:
        if version != __version__:
            raise UserError("Réinstallez la version Orre utilisée pour créer cette partie.")
        install_launcher(path.parent, shared)
        from .launcher_updates import refresh_receipt
        refresh_receipt(path.parent, data)
        runtime = _runtime(shared)
    return [runtime[0], *runtime[2:], "--play-folder", str(path.resolve())], runtime[1]


def _write_ini(path: Path, values):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    if path.is_file():
        parser.read(path, encoding="utf-8")
    for section, entries in values.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in entries.items():
            parser.set(section, key, str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".ini.tmp")
    with pending.open("w", encoding="utf-8") as output:
        parser.write(output, space_around_delimiters=True)
    pending.replace(path)


def validate_profile_root(folder):
    profile = folder / "DolphinUser"
    directories = [profile, *(profile / part for part in ("Config", "GameSettings", "GC", "StateSaves", "Logs"))]
    for path in directories:
        if path.is_symlink() or path.is_junction():
            raise UserError("Le profil Dolphin de cette partie doit rester dans son propre dossier.")
    if (profile / "GC").is_dir():
        for path in (profile / "GC").glob("MemoryCard*.*"):
            if path.is_symlink() or path.is_junction():
                raise UserError("Le profil Dolphin de cette partie doit rester dans son propre dossier.")


def configure_profile(folder: Path, manifest, *, load_path=None, muted=False, paths_for=None):
    validate_profile_root(folder)
    profile = folder / "DolphinUser"
    referenced = (paths_for or folder) / "DolphinUser"
    region = {"P": "EUR", "E": "USA", "J": "JAP"}[manifest["game_id"][3]]
    mode = display_mode(manifest["settings"])
    configure_projection(profile, manifest["game_id"], mode)
    (profile / "GC").mkdir(parents=True, exist_ok=True)
    from .play_music import native_music_enabled
    music_enabled = native_music_enabled(manifest)
    native_volume = 100
    if music_enabled:
        from .native_music_volume import NATIVE_MUSIC_OUTPUT_GAIN
        native_volume = round(100 * NATIVE_MUSIC_OUTPUT_GAIN)
    values = {"Core": {"SlotA": 1, "SlotB": 255,
        "MemcardAPath": (referenced / "GC" / f"MemoryCardA.{region}.raw").as_posix(),
        "EmulationSpeed": 1, "SIDevice0": 6},
        "Display": {"Fullscreen": True, "FullscreenDisplayRes": "Auto", "RenderToMain": False},
        "General": {"HotkeysRequireFocus": True, "LoadPath": str(load_path or referenced / "Load")},
        "Analytics": {"Enabled": False, "PermissionAsked": True},
        "DSP": {"Volume": 0 if muted else native_volume,
                "Mute": muted, "Muted": muted},
        "AutoUpdate": {"UpdateTrack": ""}}
    _write_ini(profile / "Config/Dolphin.ini", values)
    if music_enabled:
        _write_ini(profile / "Config/Dolphin.ini", {"DSP": {"Backend": "Cubeb"}})
    hd = manifest["settings"]["graphics"] == "hd"
    _write_ini(profile / "Config/GFX.ini", {"Settings": {"HiresTextures": hd, "CacheHiresTextures": False,
        "InternalResolution": 3 if hd else 1, "BorderlessFullscreen": True,
        "AspectRatio": 1 if mode == "16:9" else 2, "wideScreenHack": False,
        "Crop": False, "CropCustom": False},
        "Enhancements": {"ForceTextureFiltering": 2 if hd else 0}})
    controls = profile / "Config/GCPadNew.ini"
    marker = profile / "Config/OrreControls.json"
    desired = manifest["settings"].get("controller", "keyboard")
    try:
        previous = json.loads(marker.read_text("utf-8"))["preset"]
    except (OSError, ValueError, KeyError):
        previous = None
    changed = previous != desired
    if (not controls.exists() or changed) and desired == "keyboard":
        _write_ini(controls, {"GCPad1": {"Device": "DInput/0/Keyboard Mouse" if os.name == "nt" else "XInput2/0/Virtual core pointer",
            "Buttons/A": "`X`", "Buttons/B": "`Z`", "Buttons/X": "`S`", "Buttons/Y": "`A`",
            "Buttons/Start": "`RETURN`" if os.name == "nt" else "`Return`", "Triggers/L": "`Q`", "Triggers/R": "`W`",
            "Buttons/Z": "`D`", "Main Stick/Up": "`UP`", "Main Stick/Down": "`DOWN`",
            "Main Stick/Left": "`LEFT`", "Main Stick/Right": "`RIGHT`",
            "C-Stick/Up": "`I`", "C-Stick/Down": "`K`", "C-Stick/Left": "`J`", "C-Stick/Right": "`L`"}})
    if (not controls.exists() or changed) and desired == "controller":
        _write_ini(controls, {"GCPad1": {"Device": "XInput/0/Gamepad",
            "Buttons/A": "`Button A`", "Buttons/B": "`Button B`", "Buttons/X": "`Button X`", "Buttons/Y": "`Button Y`",
            "Buttons/Start": "`Start`", "Buttons/Z": "`Shoulder R`",
            "Triggers/L": "`Trigger L`", "Triggers/R": "`Trigger R`",
            "Main Stick/Up": "`Left Y+`", "Main Stick/Down": "`Left Y-`",
            "Main Stick/Left": "`Left X-`", "Main Stick/Right": "`Left X+`",
            "C-Stick/Up": "`Right Y+`", "C-Stick/Down": "`Right Y-`",
            "C-Stick/Left": "`Right X-`", "C-Stick/Right": "`Right X+`"}})
    if changed:
        marker.write_text(json.dumps({"preset": desired}) + "\n", encoding="utf-8")
    return profile


def load_game(path: Path):
    path = path.expanduser().resolve()
    if not path.is_file() or path.stat().st_size > 128 * 1024:
        raise UserError("Ce dossier ne contient pas de partie Orre valide.")
    try:
        data = json.loads(path.read_text("utf-8"))
        relative = Path(data["rom"])
        rom = path.parent / relative
        if (data["schema"] != 1 or data["game"] not in PACKS or relative.is_absolute()
                or ".." in relative.parts or rom.is_symlink() or not rom.resolve().is_relative_to(path.parent)
                or not rom.is_file() or rom.suffix.lower() not in SUFFIXES
                or data["game_id"][:3] != ("GXX" if data["game"] == "xd" else "GC6")
                or data["game_id"][3:] not in ("P01", "E01", "J01")
                or data["settings"]["graphics"] not in ("original", "hd")
                or data["settings"]["speed"] not in (1, 2)
                or acceleration_target(data["settings"]) not in (1, 2, 3)
                or display_mode(data["settings"]) not in ("16:9", "4:3")
                or type(data["settings"].get("save_backups", True)) is not bool
                or type(data["settings"].get("native_music", True)) is not bool
                or not isinstance(data["seed"], str) or not 0 < len(data["seed"].encode("utf-8")) <= 256
                or not isinstance(data["shared"], str) or not Path(data["shared"]).is_absolute()
                or not isinstance(data["dolphin"], str) or not isinstance(data["pack"], str)):
            raise ValueError("Invalid play-folder schema")
        validate_profile_root(path.parent)
        return data
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise UserError("Ce dossier ne contient pas de partie Orre valide.") from error


def save_game(path: Path, data):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def hd_game_requirements(manifest):
    return required_pack_games(manifest["game"],
        manifest.get("features", {}).get("overlays", {}).get("required_packs", []))


def missing_hd_packs(manifest):
    store = PackStore(Path(manifest["shared"]))
    return [game for game in hd_game_requirements(manifest) if not store.installed(PACKS[game])]


HD_CACHE_REVISION = 7


def _checked_cache_file(root, name, digest, cancel):
    """Keep auxiliary guides inside their cache, including on Windows."""
    if not isinstance(name, str):
        return False
    relative = Path(name)
    if (relative.is_absolute() or relative.drive
            or not relative.parts or ".." in relative.parts or ":" in name):
        return False
    path = root / relative
    if any((root.joinpath(*relative.parts[:index])).is_symlink()
           or (root.joinpath(*relative.parts[:index])).is_junction()
           for index in range(len(relative.parts) + 1)):
        return False
    try:
        return path.resolve().is_relative_to(root.resolve()) and file_hash(path, cancel) == digest
    except (OSError, ValueError):
        return False


def _prepare_text_hd(source_iso, output_iso, stage, game_id, cancel):
    from .hd_text_capture import collect_source_glyphs
    from .hd_text_runtime import prepare_text_bridge
    from .hd_text_assets import capture_text_assets
    from .hd_text import select_runtime_glyphs
    from .hd_text_vectors import native_padding
    from .play_rom import read_executable, update_staged_disc
    original, glyphs, audit = collect_source_glyphs(source_iso, game_id=game_id, cancel=cancel)
    resident, _ = select_runtime_glyphs(glyphs, game_id)
    try:
        margins, layout = native_padding(resident, cancel=cancel)
    except InterruptedError as error:
        raise Cancelled("Opération annulée.") from error
    modified, plan = prepare_text_bridge(original, read_executable(output_iso), game_id, glyphs,
                                         padding_by_identity=margins)
    plan["typography_layout"] = {key: layout[key] for key in ("layout_recipe", "source", "styles")}
    checkpoint(cancel)
    try:
        captured = capture_text_assets(modified, plan, stage / "Textures", cancel=cancel)
    except InterruptedError as error:
        raise Cancelled("Opération annulée.") from error
    placement = update_staged_disc(output_iso, modified)
    return dict(captured, native_memory_added=plan["native_memory_added"],
                state_address=plan["state_address"], source_font_members=audit["font_members"],
                source_dol_sha256=hashlib.sha256(original).hexdigest(), **placement)


def prepare_custom_hd(folder, manifest, *, cancel=None):
    """Build only authenticated pack-derived assets, into an immutable per-party view."""
    from .hd_overlays import VERSION, OverlayError, native_asset_manifest, prepare_hd_overlays
    from .hd_hud import hud_recipes, prepare_hud_overlays
    from .hd_extra_portraits import prepare_extra_portrait_overlays
    from .hd_form_materials import material_recipes, prepare_form_materials
    from .hd_castform_shinies import castform_shiny_recipes, prepare_castform_shiny_overlays
    from .hd_text_assets import MANIFEST as TEXT_MANIFEST, text_recipe, prepare_text_overlays
    from .resources import bundle_root
    cancel = cancel or threading.Event()
    root = Path(folder) / "Textures"
    if any(path.is_symlink() or path.is_junction() for path in (root, root / "HD")):
        raise UserError("Les réglages du lanceur sont invalides.")
    try:
        native = native_asset_manifest(root)
    except (OSError, ValueError) as error:
        raise UserError("Recréez ce dossier de partie pour préparer les nouveaux visuels HD.") from error
    has_castform_shinies = bool(native.get("castform_shinies") or
        any(row.get("role") in ("castform_battle", "castform_portrait") for row in native.get("resources", [])) or
        any(row.get("castform_roles") for row in native.get("assets", [])))
    castform_recipes = (castform_shiny_recipes(manifest["game_id"]) if has_castform_shinies else
                        {"active": False, "files": [], "catalogue_sha256": None})
    if has_castform_shinies and not castform_recipes["active"]:
        raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.")
    required = hd_game_requirements({**manifest, "features": {"overlays": native}})
    store = PackStore(Path(manifest["shared"]))
    for game in required:
        expected = manifest.get("packs", {}).get(game, PACKS[game].key)
        if expected != PACKS[game].key:
            raise UserError("Réinstallez la version Orre utilisée pour créer cette partie.")
        if not store.installed(PACKS[game]):
            raise UserError(Message("Installez le pack HD de {game} pour utiliser ces visuels.",
                game="Pokémon XD" if game == "xd" else "Pokémon Colosseum"))
    identity = hashlib.sha256((root / "orre-overlays-v2.json").read_bytes())
    identity.update(f"{__version__}:{VERSION}:{HD_CACHE_REVISION}".encode())
    identity.update(json.dumps(hud_recipes(manifest["game_id"]), sort_keys=True,
                               separators=(",", ":")).encode("ascii"))
    identity.update(json.dumps(material_recipes(manifest["game_id"]), sort_keys=True,
                               separators=(",", ":")).encode("ascii"))
    identity.update(json.dumps(castform_recipes, sort_keys=True,
                               separators=(",", ":")).encode("ascii"))
    text_manifest = root / TEXT_MANIFEST
    text_feature = manifest.get("features", {}).get("text_hd_bridge")
    if text_feature and (not text_manifest.is_file()
            or any(not _checked_cache_file(root, name, digest, cancel)
                   for name, digest in text_feature.get("auxiliary_files", {}).items())):
        raise UserError("Recréez ce dossier de partie pour préparer les nouveaux visuels HD.")
    if text_manifest.is_file():
        if (text_manifest.is_symlink() or text_manifest.is_junction()
                or text_manifest.parent.is_symlink() or text_manifest.parent.is_junction()):
            raise UserError("Les réglages du lanceur sont invalides.")
        identity.update(text_manifest.read_bytes())
        identity.update(json.dumps(text_recipe(), sort_keys=True, separators=(",", ":")).encode("ascii"))
    face_references = root / "NativeReferences/SpindaFace"
    face_manifest = face_references / "native-face-assets.json"
    if manifest.get("features", {}).get("spinda_face"):
        if not _checked_cache_file(root, "NativeReferences/SpindaFace/native-face-assets.json",
                                   manifest["features"]["spinda_face"].get("reference_manifest_sha256"), cancel):
            raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.")
        identity.update(face_manifest.read_bytes())
    for filename in ("hd-fullbody-manifest.json", "portrait-variants.json",
                     "extra-portraits/extra-portraits.json"):
        registry = bundle_root() / "models" / filename
        if registry.is_file():
            identity.update(filename.encode("ascii"))
            identity.update(registry.read_bytes())
    for game in required:
        identity.update((store.location(PACKS[game]) / "installed.json").read_bytes())
    target = root / "HD" / identity.hexdigest()[:24]
    receipt = target / "cache.json"
    if receipt.is_file():
        try:
            cached = json.loads(receipt.read_text("utf-8"))
            if (cached["hd_ready"] and cached["schema"] == 2
                    and cached.get("generator_revision") == HD_CACHE_REVISION
                    and all(Path(item["file"]).name == item["file"]
                            and _checked_cache_file(target, item["file"], item["sha256"], cancel)
                            for item in cached["files"])
                    and all(_checked_cache_file(target, name, digest, cancel)
                            for name, digest in cached.get("auxiliary_files", {}).items())):
                return dict(cached, directory=str(target))
        except (OSError, KeyError, ValueError):
            pass
        raise UserError("Les visuels HD de cette partie sont incomplets. Recréez son dossier.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hd-", dir=target.parent) as temporary:
        stage = Path(temporary) / "assets"
        try:
            result = prepare_hd_overlays(root, stage,
                pack_roots={game: store.location(PACKS[game]) for game in required}, cancel=cancel)
        except InterruptedError as error:
            raise Cancelled("Opération annulée.") from error
        except OverlayError as error:
            raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.") from error
        if not result["hd_ready"]:
            (root / "hd-diagnostics.json").write_text(json.dumps(result.get("missing_assets", []), indent=2) + "\n", encoding="utf-8")
            raise UserError("Certains visuels HD personnalisés sont indisponibles. Le mode Origine reste disponible.")
        checkpoint(cancel)
        try:
            hud = prepare_hud_overlays(manifest["game_id"],
                {game: store.location(PACKS[game]) for game in required}, stage)
        except (OSError, ValueError) as error:
            raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.") from error
        result["localized_hud"] = hud
        result["files"].extend({"file": name, "sha256": digest, "hd_source": {"kind": "localized-hud"}}
                               for name, digest in hud["files"].items())
        checkpoint(cancel)
        try:
            forms = prepare_extra_portrait_overlays(manifest["game_id"],
                {game: store.location(PACKS[game]) for game in required}, stage)
            materials = prepare_form_materials(manifest["game_id"],
                {game: store.location(PACKS[game]) for game in required}, stage)
            castform = (prepare_castform_shiny_overlays(manifest["game_id"],
                {game: store.location(PACKS[game]) for game in required}, stage) if has_castform_shinies else
                {"game_id": manifest["game_id"], "active": False, "files": {}, "assets": [], "required_packs": []})
        except (OSError, ValueError) as error:
            raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.") from error
        result["extra_form_portraits"] = forms
        result["extra_form_materials"] = materials
        result["castform_shiny_artwork"] = castform
        known = {item["file"]: item["sha256"] for item in result["files"]}
        for name, digest in (*forms["files"].items(), *materials["files"].items(), *castform["files"].items()):
            if name in known:
                if known[name] != digest:
                    raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.")
                continue
            result["files"].append({"file": name, "sha256": digest,
                                    "hd_source": {"kind": "custom-castform-shiny-artwork" if name in castform["files"]
                                                  else "catalogued-extra-form-material" if name in materials["files"]
                                                  else "catalogued-extra-form-portrait"}})
            known[name] = digest
        if text_manifest.is_file():
            checkpoint(cancel)
            try:
                text = prepare_text_overlays(root, stage, cancel=cancel)
            except InterruptedError as error:
                raise Cancelled("Opération annulée.") from error
            except (OSError, ValueError) as error:
                raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.") from error
            result["vector_text"] = text
            result["files"].extend({"file": name, "sha256": digest, "hd_source": {"kind": "vector-text"}}
                                   for name, digest in text["files"].items())
            result.setdefault("auxiliary_files", {}).update(text["auxiliary_files"])
        if manifest.get("features", {}).get("spinda_face"):
            from .hd_spinda_face import prepare_face_assets_from_references
            checkpoint(cancel)
            try:
                face = prepare_face_assets_from_references(face_references,
                    store.location(PACKS["colosseum"]), stage / "SpindaFace")
            except (OSError, ValueError) as error:
                raise UserError("Les visuels HD personnalisés n’ont pas pu être préparés.") from error
            result["spinda_face"] = face
            face_files = {str(path.relative_to(stage).as_posix()): file_hash(path, cancel)
                          for path in (stage / "SpindaFace").iterdir() if path.is_file()}
            result.setdefault("auxiliary_files", {}).update(face_files)
        result["texture_count"] = len(result["files"])
        result["generator_revision"] = HD_CACHE_REVISION
        (stage / "orre-overlays-v2.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (stage / "cache.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        checkpoint(cancel)
        _publish_folder(stage, target, cancel)
    return dict(result, directory=str(target))


def _prepare_extras(source_iso, output_iso, boot, stage, shared, progress, cancel, *, asset_context=None, hd_requested=False):
    from .hd_overlays import capture_native_assets
    from .play_rom import read_executable, update_staged_disc
    asset_context = dict(asset_context or {})
    features = {}
    spinda_samples = []
    if boot[:3] == b"GC6" and asset_context.get("dna_lab"):
        from .artwork import _disc_files
        from .engine.dna_hd_tiles import split_keypad_archive, install_dna_hd_tile_bridge
        from .engine.regions import region_for_boot
        checkpoint(cancel)
        original = _disc_files(output_iso, {"DNA_key.fsys"})["DNA_key.fsys"]
        keypad, layout = split_keypad_archive(original)
        from .engine.dna_keypad import DNA_KEYPAD_SPECIES
        from .engine.dna_lab import _MIGHTYENA
        from .engine.spinda import SPINDA
        spinda_samples = sorted(int(old) for old, sample in asset_context["dna_lab"].items()
                                if sample["species"] == SPINDA
                                and int(old) in DNA_KEYPAD_SPECIES and int(old) != _MIGHTYENA)
        if spinda_samples:
            from .engine.actor_palette import pkx_recipe
            from .engine.analyze_game import parse_fsys
            from .engine.rebuild_iso import decoded_member
            from .engine.dna_spinda_hd import extend_spinda_keypad_archive
            references = _disc_files(source_iso, {"DNA_key.fsys", "poke_body.fsys", "pkx_patcheel.fsys"})
            spinda_archive = references["pkx_patcheel.fsys"]
            members = {row["name"]: row for row in parse_fsys(spinda_archive)["members"]}
            face, spot, model = (decoded_member(spinda_archive, members[name])
                                 for name in ("face", "buti_a", "patcheel"))
            keypad, layout = extend_spinda_keypad_archive(
                keypad, layout, spinda_samples, face, spot, pkx_recipe(model, xd=False),
                original_keypad=references["DNA_key.fsys"], bodies_archive=references["poke_body.fsys"])
            checkpoint(cancel)
        region = region_for_boot(boot)
        with source_iso.open("rb") as source:
            source.seek(struct.unpack_from(">I", boot, 0x420)[0])
            original_dol = source.read(region.dol_size)
        modified, bridge = install_dna_hd_tile_bridge(original_dol, read_executable(output_iso), layout)
        checkpoint(cancel)
        bridge.update(update_staged_disc(output_iso, modified, {"DNA_key.fsys": keypad}))
        asset_context["dna_hd_layout"] = layout
        features["dna_hd_tiles"] = bridge
    progress(79, "Préparation des textures personnalisées…")
    features["text_hd_bridge"] = _prepare_text_hd(source_iso, output_iso, stage, boot[:6].decode("ascii"), cancel)
    game_id = boot[:6].decode("ascii")
    from .engine.play_music_bridge import SUPPORTED_GAME_IDS, patch_music_bridge
    if game_id in SUPPORTED_GAME_IDS:
        from .native_music_resources import prepare_music_assets
        from .engine.regions import region_for_boot
        from .xd import region_for_boot as xd_region
        region = (xd_region if game_id.startswith("GXX") else region_for_boot)(boot)
        with source_iso.open("rb") as source:
            source.seek(struct.unpack_from(">I", boot, 0x420)[0])
            original_dol = source.read(region.dol_size)
        modified, metadata = patch_music_bridge(original_dol, read_executable(output_iso), game_id)
        metadata.update(update_staged_disc(output_iso, modified))
        assets = shared / "AudioBanks" / (game_id + "-" + metadata["source_dol_sha256"][:16])
        checkpoint(cancel)
        prepare_music_assets(source_iso, assets, game_id=game_id, cancel=cancel)
        features["music"] = dict(metadata, assets=str(assets.resolve()))
    # Keep the face bridge last: Japan reserves its pixel bank beyond the
    # loaded DOL. Later executable additions must not occupy that bank.
    if spinda_samples:
        from .engine.dna_spinda_face_hd import face_runtime_validated, patch_spinda_face_bridge
        if face_runtime_validated(game_id, boot[7]):
            modified, metadata = patch_spinda_face_bridge(original_dol, read_executable(output_iso),
                                                          game_id=game_id, revision=boot[7])
            checkpoint(cancel)
            metadata.update(update_staged_disc(output_iso, modified))
            features["spinda_face"] = metadata
    try:
        overlays = capture_native_assets(output_iso, stage / "Textures", is_xd=boot[:3] == b"GXX",
            reference_iso=source_iso, asset_context=asset_context, cancel=cancel)
    except InterruptedError as error:
        raise Cancelled("Opération annulée.") from error
    features["overlays"] = {"schema": 2, "count": overlays["texture_count"],
        "required_packs": overlays.get("required_packs", []), "hd_ready": False}
    if features.get("spinda_face"):
        from .hd_spinda_face import capture_native_face_assets
        references = stage / "Textures/NativeReferences/SpindaFace"
        references.parent.mkdir(parents=True, exist_ok=True)
        capture_native_face_assets(source_iso, references)
        features["spinda_face"]["reference_manifest_sha256"] = file_hash(
            references / "native-face-assets.json", cancel)
    if hd_requested:
        progress(81, "Préparation des textures HD personnalisées…")
        hd = prepare_custom_hd(stage, {"game": "xd" if boot[:3] == b"GXX" else "colosseum",
            "game_id": boot[:6].decode("ascii"),
            "shared": str(shared), "features": features}, cancel=cancel)
        features["overlays"].update(hd_ready=True, hd_count=hd["texture_count"])
    return features


def _publish_folder(stage, folder, cancel):
    if os.name == "nt":
        # Virus scanners may briefly open newly generated files without delete
        # sharing. Keep the final publication atomic and cancellable while they
        # release those handles; never merge into or replace an existing folder.
        deadline = time.monotonic() + 5
        while True:
            checkpoint(cancel)
            if os.path.lexists(folder):
                raise UserError("Ce dossier existe déjà. Choisissez un autre nom pour conserver ses fichiers.")
            try:
                stage.rename(folder)
                return
            except PermissionError as error:
                if getattr(error, "winerror", None) not in (5, 32) or time.monotonic() >= deadline:
                    raise
                cancel.wait(.1)
    else:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        if not hasattr(libc, "renameat2") or libc.renameat2(-100, os.fsencode(stage), -100, os.fsencode(folder), 1):
            raise OSError(ctypes.get_errno(), "Cannot publish a game folder without replacing files")


def create_game_folder(*, request: PlayFolderRequest, source: Path, destination: Path, seed: str,
                       progress=None, cancel=None, **arguments):
    cancel = cancel or threading.Event()
    progress = progress or (lambda percent, message: None)
    folder = validate_request(request, source, destination.suffix.lower(), seed)
    shared = request.shared or shared_root()
    game = "xd" if arguments.get("xd_options") is not None else "colosseum"
    pack = PACKS[game]
    if request.graphics == "hd":
        missing = missing_hd_packs({"game": game, "shared": str(shared)})
        if missing:
            raise UserError(Message("Installez le pack HD de {game} pour utiliser ces visuels.",
                game="Pokémon XD" if missing[0] == "xd" else "Pokémon Colosseum"))
    with tempfile.TemporaryDirectory(prefix=".orre-play-", dir=folder.parent) as temporary:
        stage = Path(temporary) / "play"
        (stage / "Game").mkdir(parents=True)
        staged_rom = stage / "Game" / ("game" + destination.suffix.lower())
        install_launcher(stage, shared)
        last_progress = [0]
        def staging_progress(percent, message):
            value = max(last_progress[0], min(97, int(percent * .97)))
            last_progress[0] = value
            progress(value, message)
        report = randomize(source=source, destination=staged_rom, seed=seed,
            progress=staging_progress, cancel=cancel,
            postprocess=lambda original, result, boot, context: _prepare_extras(original, result, boot, stage, shared,
                staging_progress, cancel, asset_context=context, hd_requested=request.graphics == "hd"),
            **arguments)
        manifest = {"schema": 1, "orre_version": __version__, "game": game, "game_id": report["game_id"],
            "seed": seed, "rom": staged_rom.relative_to(stage).as_posix(), "rom_sha256": report["output_sha256"],
            "dolphin": str(request.dolphin.resolve()), "shared": str(shared.resolve()),
            "pack": pack.key, "language": request.language,
            "packs": {key: PACKS[key].key for key in hd_game_requirements({
                "game": game, "features": report.get("play_features", {})})},
            "settings": {"graphics": request.graphics, "speed": 1, "acceleration": 2,
                         "display": "16:9"},
            "features": report.get("play_features", {})}
        from .play_music import native_music_enabled
        manifest["settings"]["native_music"] = native_music_enabled(manifest)
        final_rom = folder / manifest["rom"]
        report.update(output=str(final_rom), journal=str(final_rom.with_suffix(final_rom.suffix + ".html")),
                      play_folder=str(folder), launcher=str(folder / ("Launcher.exe" if os.name == "nt" else "Launcher")))
        from .journal import render_journal
        staged_rom.with_suffix(staged_rom.suffix + ".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staged_rom.with_suffix(staged_rom.suffix + ".html").write_text(render_journal(report, arguments.get("journal_language", "en")), encoding="utf-8")
        save_game(stage / "game.json", manifest)
        configure_profile(stage, manifest, paths_for=folder)
        (stage / "README.txt").write_text("Pokémon Orre Randomizer\n\nOpen Launcher.exe to play. Keep all files together.\n"
            "Game/ contains the generated ROM and its reports.\nDolphinUser/ contains this game's saves and settings.\n"
            "Textures/ contains custom replacement textures.\nDolphin and pinned HD packs are shared.\n"
            "Do not replace your original ROM or memory card.\n", encoding="utf-8")
        checkpoint(cancel)
        if os.path.lexists(folder):
            raise UserError("Ce dossier existe déjà. Choisissez un autre nom pour conserver ses fichiers.")
        _publish_folder(stage, folder, cancel)
        progress(100, "Dossier de partie créé et vérifié.")
        return report


def launch_command(folder: Path, manifest, *, muted=False, cancel=None, session_context=None):
    if session_context is not None:
        session_context.clear()
    dolphin = validate_dolphin(Path(manifest["dolphin"]))
    load_path = None
    if manifest["settings"]["graphics"] == "hd":
        store = PackStore(Path(manifest["shared"]))
        pack = PACKS[manifest["game"]]
        if pack.key != manifest["pack"]:
            raise UserError("Cette partie nécessite une autre version du pack HD. Réinstallez son runtime Orre.")
        hd = prepare_custom_hd(folder, manifest, cancel=cancel)
        fallback = tuple(PACKS[game] for game in hd_game_requirements(manifest) if game != pack.game)
        load_path = store.texture_view(pack, manifest["game_id"], Path(hd["directory"]),
                                       fallback_packs=fallback)
        face = manifest.get("features", {}).get("spinda_face")
        if session_context is not None and face and hd.get("spinda_face"):
            session_context["spinda_face"] = {"assets": str(Path(hd["directory"]) / "SpindaFace"),
                                             "metadata": face}
    profile = configure_profile(folder, manifest, load_path=load_path, muted=muted)
    return [str(dolphin), "-b", "-u", str(profile), "-e", str(folder / manifest["rom"]),
            *(["-C", "Dolphin.DSP.Volume=0", "-C", "Dolphin.DSP.Mute=True"] if muted else [])]
