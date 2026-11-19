"""Release-pinned texture downloads and immutable shared installations.

Only PNG/DDS replacement textures are installed. Packs never modify a game image.
Original author archives are pinned independently of other launchers.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlsplit
import uuid
import zipfile

from .i18n import Message
from .service import Cancelled, UserError

# Optional whole-archive mirror override. The default uses the reviewed release
# assets pinned below. A local distribution folder may also contain packs/.
DOWNLOAD_SOURCE = ""


def _validate_archive_metadata(url, sha256, size, filename):
    if not isinstance(sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("Invalid pinned archive SHA-256")
    if type(size) is not int or size <= 0:
        raise ValueError("Invalid pinned archive size")
    if not isinstance(filename, str) or (filename and (
            filename in (".", "..") or filename.rstrip(". ") != filename
            or any(character in '/\\:<>"|?*' or ord(character) < 32
                   for character in filename))):
        raise ValueError("Invalid archive filename")
    if not isinstance(url, str):
        raise ValueError("Invalid archive URL")
    if url:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or "\\" in url
                or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url)):
            raise ValueError("Archive downloads require a valid HTTPS URL")
        # Accessing port also rejects malformed authorities before any request.
        parsed.port


@dataclass(frozen=True)
class ArchiveFragment:
    """A pinned byte range distributed as an independent HTTPS object."""

    url: str
    sha256: str
    size: int
    filename: str = ""

    def __post_init__(self):
        _validate_archive_metadata(self.url, self.sha256, self.size, self.filename)


@dataclass(frozen=True)
class Part:
    url: str
    sha256: str
    size: int
    filename: str = ""
    fragments: tuple[ArchiveFragment, ...] = ()

    def __post_init__(self):
        _validate_archive_metadata(self.url, self.sha256, self.size, self.filename)
        if (not isinstance(self.fragments, tuple)
                or any(not isinstance(fragment, ArchiveFragment) for fragment in self.fragments)):
            raise ValueError("Invalid archive fragments")
        if self.fragments and sum(fragment.size for fragment in self.fragments) != self.size:
            raise ValueError("Archive fragment sizes do not match the pinned ZIP")


@dataclass(frozen=True)
class Pack:
    game: str
    version: str
    unpacked: int
    parts: tuple[Part, ...]
    excluded: tuple[str, ...] = ()
    author: str = ""
    source: str = ""
    archive_source: str = ""
    excluded_paths: tuple[str, ...] = ()

    @property
    def key(self):
        return f"{self.game}-{self.version}"


# Original community releases. Downloads are not silently upgraded.
_PACK_RELEASE_URL = "https://github.com/KadenHD/pokemon-orre-hd-packs/releases/download/packs-2026-11-18/"
PACKS = {
    "colosseum": Pack("colosseum", "2.00", 1609063880, (
        Part(_PACK_RELEASE_URL + "colosseum-2.00-4cac6314d8b3.zip",
             "4cac6314d8b3fed18743dc0db844b64651c3845668037912d8ed216053af0e33", 722522130,
             "Pokemon Colosseum HD Pack.zip"),), author="Sephie",
        source="https://www.reddit.com/r/DolphinEmulator/comments/sxzxi2/",
        archive_source="https://drive.google.com/file/d/1FwGSM1TJfIrAKNfy7BTrTF850JccSwkt/view",
        excluded_paths=(
            "textures/GC6/Battle/Tower/tex1_128x128_29e0ee2a2a2b7b1f_14.dds",
            "textures/GC6/Battle/Tower/tex1_128x128_8b540a3e113a83d4_14.dds",
            "textures/GC6/Battle/Tower/tex1_128x128_bc9d64315eb27870_14.dds",
            "textures/GC6/Chara/NPCs/tex1_128x128_1003ad874987835c_14.dds",
            "textures/GC6/Locations/The Under/tex1_128x128_b0878d88c66b4cc6_14.dds",
            "textures/GC6/PKMN/tex1_10x10_415492578a3b319a_497b4155226bc4aa_9.dds",
            "textures/GC6/UI/PKMN Battle Icons/tex1_64x64_6eec2ccae8e1c744_5.dds",
            "textures/GC6/UI/PKMN Battle Icons/tex1_64x64_6fcb1de7c34de16f_14.dds",
            "textures/GC6/UI/PKMN Battle Icons/tex1_64x64_7a0ef68213d0c30c_14.dds")),
    "xd": Pack("xd", "1.0", 3296572631, (
        Part("", "56bbf26551f26b7bdb1d0d7d4a6eb7073cf4f8fef72130648bd97abde8851cf2", 3295188617,
             "Pokemon XD-XG HD V1.0 PNG Texture Pack.zip", fragments=(
                 ArchiveFragment(_PACK_RELEASE_URL + "xd-1.0-56bbf26551f2.zip.001", "c79d409370286de0ea54efc2d76bac088bcb7506c27032a2906ca0715a59b9da",
                                 1900000000, "xd-1.0-56bbf26551f2.zip.001"),
                 ArchiveFragment(_PACK_RELEASE_URL + "xd-1.0-56bbf26551f2.zip.002", "2f0be080df96ba6274c9ed784bc4f90c50f0c2a5556b58f23dc3178dd1d985fe",
                                 1395188617, "xd-1.0-56bbf26551f2.zip.002"))),), author="mikeyX",
        source="https://forums.dolphin-emu.org/Thread-pokemon-xg-xd-hd-texture-pack-v1-0",
        archive_source="https://mega.nz/folder/kA4WFZ7D#cd66IQr-2AM_PeYd8hFd3Q/file/QZgmWYIZ"),
}


def required_pack_games(game, extra=()):
    """XD portraits always need Colosseum; imported models can add donors."""
    games = (game, *(("colosseum",) if game == "xd" else ()), *extra)
    if any(not isinstance(key, str) or key not in PACKS for key in games):
        raise UserError("Les réglages du lanceur sont invalides.")
    return tuple(dict.fromkeys(games))


def shared_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local/share") / "OrreRandomizer/Shared"


def checkpoint(cancel):
    if cancel.is_set():
        raise Cancelled("Opération annulée.")


def digest(path: Path, cancel=None):
    result = hashlib.sha256()
    with path.open("rb") as source:
        while data := source.read(4 * 1024**2):
            if cancel is not None:
                checkpoint(cancel)
            result.update(data)
    return result.hexdigest()


def remove_owned(path: Path, root: Path):
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.resolve() == root.resolve():
        raise ValueError("Refusing cleanup outside the owned cache")
    if path.exists():
        shutil.rmtree(path)


def texture_identity(path: Path) -> str:
    return re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", path.stem.lower())


class PackStore:
    def __init__(self, root: Path | None = None, *, source: str | Path | None = None):
        self.root = Path(root) if root is not None else shared_root()
        self.source = DOWNLOAD_SOURCE if source is None else source

    def downloads_available(self, pack: Pack):
        return bool(self.source) or all(
            part.url or (part.fragments and all(fragment.url for fragment in part.fragments))
            for part in pack.parts)

    def archive_source(self, pack: Pack, part: Part) -> str | Path:
        """Resolve one immutable object from the approved URL or folder."""
        if not self.source:
            return part.url
        relative = PurePosixPath("packs", pack.game, pack.version, part.sha256[:12] + ".zip")
        if (not re.fullmatch(r"[a-z0-9.-]+", pack.game)
                or not re.fullmatch(r"[a-z0-9.-]+", pack.version)
                or not re.fullmatch(r"[a-f0-9]{64}", part.sha256)):
            raise ValueError("Invalid pinned archive identity")
        source = str(self.source)
        if source.startswith("https://"):
            parsed = urlsplit(source)
            if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or "\\" in source or any(character.isspace() for character in source)):
                raise ValueError("Invalid pack download source")
            return source.rstrip("/") + "/" + relative.as_posix()
        if "://" in source:
            raise ValueError("Pack downloads require HTTPS")
        folder = Path(source).resolve()
        path = folder.joinpath(*relative.parts)
        if not path.resolve().is_relative_to(folder) or path.is_symlink():
            raise ValueError("Archive is outside the distribution folder")
        return path

    def location(self, pack: Pack):
        if not re.fullmatch(r"[a-z0-9.-]+", pack.key):
            raise ValueError("Invalid pack identity")
        return self.root / "TexturePacks" / pack.key

    def installed(self, pack: Pack):
        folder = self.location(pack)
        try:
            marker = json.loads((folder / "installed.json").read_text("utf-8"))
            return (not folder.is_symlink() and marker["archives"] == [p.sha256 for p in pack.parts]
                    and marker["key"] == pack.key and marker["textures"] > 0
                    and (folder / "Textures").is_dir())
        except (OSError, KeyError, ValueError, TypeError):
            return False

    def install_game(self, game, *, cancel=None, progress=None, force=False):
        """Install missing dependencies once; repair only the selected pack."""
        cancel = cancel or threading.Event()
        progress = progress or (lambda percent, message: None)
        required = [PACKS[key] for key in required_pack_games(game)]
        pending = [pack for pack in required
                   if not self.installed(pack) or (force and pack.game == game)]
        total = sum(pack.unpacked + sum(part.size for part in pack.parts) for pack in pending)
        offset = 0
        results = []
        for pack in pending:
            checkpoint(cancel)
            weight = pack.unpacked + sum(part.size for part in pack.parts)
            def advance(percent, message):
                progress(min(100, (offset * 100 + weight * percent) // max(1, total)), message)
            results.append(self.install(pack, cancel=cancel, progress=advance,
                                        force=force and pack.game == game))
            offset += weight
        checkpoint(cancel)
        if any(not self.installed(pack) for pack in required):
            raise UserError("Le pack HD n’a pas pu être installé. Réessayez.")
        progress(100, "Packs HD installés et vérifiés.")
        return {"game": game, "packs": results}

    def _download(self, part, cancel, progress, offset, total, *, source=None):
        downloads = self.root / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        archive = downloads / (part.sha256 + ".zip")
        if archive.is_file() and archive.stat().st_size == part.size and digest(archive, cancel) == part.sha256:
            progress(70 * (offset + part.size) // total, "Téléchargement vérifié.")
            return archive
        source = part.url if source is None else source
        if not source and part.fragments:
            return self._download_fragments(part, pending=downloads / (part.sha256 + ".part"),
                                            archive=archive, cancel=cancel, progress=progress,
                                            offset=offset, total=total)
        if not source:
            raise UserError("La source des packs HD n’est pas encore configurée.")
        if isinstance(source, Path):
            if source.is_symlink() or not source.is_file() or source.stat().st_size != part.size:
                raise UserError("Le pack HD est introuvable dans le dossier de distribution.")
            pending = downloads / (part.sha256 + ".part")
            with source.open("rb") as incoming, pending.open("wb") as outgoing:
                count = 0
                while data := incoming.read(1024**2):
                    checkpoint(cancel)
                    count += len(data)
                    if count > part.size:
                        raise UserError("Le téléchargement dépasse la taille attendue.")
                    outgoing.write(data)
                    progress(70 * (offset + count) // total, "Téléchargement du pack HD…")
            if count != part.size or digest(pending, cancel) != part.sha256:
                pending.unlink(missing_ok=True)
                raise UserError("Le pack téléchargé ne correspond pas à la version attendue. Réessayez.")
            pending.replace(archive)
            return archive
        pending = downloads / (part.sha256 + ".part")
        start = pending.stat().st_size if pending.is_file() else 0
        checkpoint(cancel)
        if start == part.size:
            if digest(pending, cancel) == part.sha256:
                pending.replace(archive)
                progress(70 * (offset + part.size) // total, "Téléchargement vérifié.")
                return archive
            start = 0
        if start > part.size:
            start = 0
        headers = {"User-Agent": "Pokemon-Orre-Randomizer", "Accept-Encoding": "identity"}
        if start:
            headers["Range"] = f"bytes={start}-"
        checkpoint(cancel)
        try:
            request = urllib.request.Request(source, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                resumed = (start and response.status == 206
                           and response.headers.get("Content-Range", "").startswith(f"bytes {start}-"))
                if response.status == 206 and not resumed:
                    raise UserError("Réponse de téléchargement invalide. Réessayez.")
                if not resumed:
                    start = 0
                with pending.open("ab" if resumed else "wb") as output:
                    count = start
                    while data := response.read(1024**2):
                        checkpoint(cancel)
                        count += len(data)
                        if count > part.size:
                            raise UserError("Le téléchargement dépasse la taille attendue.")
                        output.write(data)
                        progress(70 * (offset + count) // total, "Téléchargement du pack HD…")
            if count != part.size:
                raise UserError("Téléchargement impossible. Vérifiez la connexion, puis réessayez.")
            if digest(pending, cancel) != part.sha256:
                pending.unlink(missing_ok=True)
                raise UserError("Le pack téléchargé ne correspond pas à la version attendue. Réessayez.")
            pending.replace(archive)
            return archive
        except Cancelled:
            raise
        except OSError as error:
            raise UserError("Téléchargement impossible. Vérifiez la connexion, puis réessayez.") from error

    def _download_fragments(self, part, *, pending, archive, cancel, progress, offset, total):
        """Assemble verified fragments directly in the one resumable ZIP file."""
        try:
            with pending.open("r+b" if pending.exists() else "w+b") as output:
                output.seek(0, os.SEEK_END)
                available = output.tell()
                if available > part.size:
                    output.truncate(part.size)
                    available = part.size
                begin = 0
                for fragment in part.fragments:
                    checkpoint(cancel)
                    count = min(fragment.size, max(0, available - begin))
                    checksum = hashlib.sha256()
                    output.seek(begin)
                    remaining = count
                    while remaining:
                        checkpoint(cancel)
                        data = output.read(min(4 * 1024**2, remaining))
                        if not data:
                            raise OSError("Incomplete pending archive")
                        checksum.update(data)
                        remaining -= len(data)
                    if count == fragment.size:
                        if checksum.hexdigest() == fragment.sha256:
                            begin += fragment.size
                            progress(70 * (offset + begin) // total, "Téléchargement vérifié.")
                            continue
                        # A corrupt fragment also invalidates every byte after it.
                        output.truncate(begin)
                        available = begin
                        count = 0
                        checksum = hashlib.sha256()
                    if not fragment.url:
                        raise UserError("La source des packs HD n’est pas encore configurée.")
                    headers = {"User-Agent": "Pokemon-Orre-Randomizer", "Accept-Encoding": "identity"}
                    if count:
                        headers["Range"] = f"bytes={count}-"
                    checkpoint(cancel)
                    request = urllib.request.Request(fragment.url, headers=headers)
                    with urllib.request.urlopen(request, timeout=30) as response:
                        if response.status == 206:
                            content_range = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",
                                                        response.headers.get("Content-Range", ""))
                            if (not count or not content_range
                                    or int(content_range[1]) != count
                                    or not count <= int(content_range[2]) < fragment.size
                                    or int(content_range[3]) != fragment.size):
                                raise UserError("Réponse de téléchargement invalide. Réessayez.")
                        elif response.status == 200:
                            # An ignored Range restarts this fragment, never its predecessors.
                            output.truncate(begin)
                            count = 0
                            checksum = hashlib.sha256()
                        else:
                            raise UserError("Réponse de téléchargement invalide. Réessayez.")
                        output.seek(begin + count)
                        while data := response.read(1024**2):
                            checkpoint(cancel)
                            if count + len(data) > fragment.size:
                                output.truncate(begin)
                                raise UserError("Le téléchargement dépasse la taille attendue.")
                            output.write(data)
                            checksum.update(data)
                            count += len(data)
                            progress(70 * (offset + begin + count) // total, "Téléchargement du pack HD…")
                    if count != fragment.size:
                        raise UserError("Téléchargement impossible. Vérifiez la connexion, puis réessayez.")
                    if checksum.hexdigest() != fragment.sha256:
                        output.truncate(begin)
                        raise UserError("Le pack téléchargé ne correspond pas à la version attendue. Réessayez.")
                    begin += fragment.size
                    available = begin
            checkpoint(cancel)
            if digest(pending, cancel) != part.sha256:
                raise UserError("Le pack téléchargé ne correspond pas à la version attendue. Réessayez.")
            pending.replace(archive)
            progress(70 * (offset + part.size) // total, "Téléchargement vérifié.")
            return archive
        except Cancelled:
            raise
        except OSError as error:
            raise UserError("Téléchargement impossible. Vérifiez la connexion, puis réessayez.") from error

    def install(self, pack: Pack, *, cancel=None, progress=None, force=False, local_archives=None):
        cancel = cancel or threading.Event()
        progress = progress or (lambda percent, message: None)
        ready = self.installed(pack)
        if ready and not force:
            return {"pack": pack.key, "path": str(self.location(pack)), "already_installed": True}
        destination = self.location(pack)
        destination.parent.mkdir(parents=True, exist_ok=True)
        lock = destination.with_suffix(destination.suffix + ".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise UserError("Ce pack est déjà en cours d’installation.") from error
        os.close(fd)
        stage = None
        try:
            local_archives = tuple(map(Path, local_archives)) if local_archives is not None else None
            if local_archives is not None and len(local_archives) != len(pack.parts):
                raise UserError("Sélectionnez toutes les archives de cette version du pack HD.")
            required = pack.unpacked + sum(p.size for p in pack.parts) + 256 * 1024**2
            if shutil.disk_usage(destination.parent).free < required:
                raise UserError("Espace disque insuffisant pour installer ce pack HD.")
            archives = []
            total = sum(p.size for p in pack.parts)
            offset = 0
            for index, part in enumerate(pack.parts):
                if local_archives is None:
                    archive = self._download(part, cancel, progress, offset, total,
                                             source=self.archive_source(pack, part))
                else:
                    archive = local_archives[index]
                    if (archive.is_symlink() or not archive.is_file() or archive.stat().st_size != part.size
                            or digest(archive, cancel) != part.sha256):
                        raise UserError("L’archive ne correspond pas à la version attendue du pack HD.")
                archives.append(archive)
                offset += part.size
            stage = Path(tempfile.mkdtemp(prefix=".install-", dir=destination.parent))
            textures = stage / "Textures"
            textures.mkdir()
            written = 0
            names = set()
            for archive in archives:
                with zipfile.ZipFile(archive) as source:
                    for entry in source.infolist():
                        checkpoint(cancel)
                        relative = PurePosixPath(entry.filename.replace("\\", "/"))
                        if (relative.is_absolute() or ".." in relative.parts or ":" in entry.filename
                                or stat.S_ISLNK(entry.external_attr >> 16)):
                            raise UserError("Le pack contient un chemin invalide.")
                        if entry.is_dir() or relative.suffix.lower() not in {".png", ".dds"}:
                            continue
                        if relative.as_posix() in pack.excluded_paths:
                            continue
                        name = relative.name.lower()
                        if not re.fullmatch(r"tex1_[a-z0-9_]+\.(?:png|dds)", name) or name in pack.excluded:
                            continue
                        if Path(name).stem in names or entry.file_size > 64 * 1024**2:
                            raise UserError("Le pack contient une texture invalide ou en double.")
                        written += entry.file_size
                        if written > pack.unpacked + 16 * 1024**2:
                            raise UserError("Le pack dépasse la taille décompressée attendue.")
                        with source.open(entry) as incoming, (textures / name).open("xb") as outgoing:
                            signature = incoming.read(8)
                            if (relative.suffix.lower() == ".png" and signature != b"\x89PNG\r\n\x1a\n"
                                    or relative.suffix.lower() == ".dds" and signature != b"DDS |\x00\x00\x00"):
                                raise UserError("Le pack contient une texture invalide.")
                            outgoing.write(signature)
                            while data := incoming.read(1024**2):
                                checkpoint(cancel)
                                outgoing.write(data)
                        names.add(Path(name).stem)
                        progress(70 + min(28, 28 * written // max(pack.unpacked, 1)), "Installation des textures HD…")
            if not names:
                raise UserError("Aucune texture compatible n’a été trouvée dans le pack.")
            (stage / "installed.json").write_text(json.dumps({"key": pack.key,
                "archives": [p.sha256 for p in pack.parts], "textures": len(names),
                "bytes": written, "generation": uuid.uuid4().hex,
                "source": pack.source, "author": pack.author, "archive_source": pack.archive_source},
                indent=2) + "\n", encoding="utf-8")
            checkpoint(cancel)
            previous = None
            if destination.exists():
                if not force or not ready:
                    raise UserError("Ce dossier de pack existe déjà. Choisissez un autre dossier partagé.")
                previous = destination.with_name(".previous-" + uuid.uuid4().hex)
                destination.rename(previous)
            try:
                stage.rename(destination)
            except BaseException:
                if previous is not None and not destination.exists():
                    previous.rename(destination)
                raise
            stage = None
            if previous is not None:
                remove_owned(previous, destination.parent)
            for part, archive in zip(pack.parts, archives, strict=True):
                expected = self.root / "Downloads" / (part.sha256 + ".zip")
                if local_archives is None and archive == expected and not archive.is_symlink():
                    archive.unlink(missing_ok=True)
            progress(100, "Pack HD installé et vérifié.")
            return {"pack": pack.key, "path": str(destination), "textures": len(names)}
        finally:
            if stage is not None:
                remove_owned(stage, destination.parent)
            lock.unlink(missing_ok=True)

    def texture_view(self, pack: Pack, game_id: str, overlays: Path | None = None,
                     *, fallback_packs: tuple[Pack, ...] = ()):
        """Primary art, then exact missing keys from dependencies, then custom art."""
        if not self.installed(pack) or not re.fullmatch(r"(?:GC6|GXX)[EPJ]01", game_id):
            raise UserError("Installez le pack HD validé avant de lancer cette partie en HD.")
        layers = []
        for candidate in (pack, *fallback_packs):
            if not isinstance(candidate, Pack) or not self.installed(candidate):
                raise UserError("Installez le pack HD validé avant de lancer cette partie en HD.")
            if any(layer[0].key == candidate.key for layer in layers):
                continue
            receipt = json.loads((self.location(candidate) / "installed.json").read_text("utf-8"))
            generation = receipt.get("generation", "initial")
            if generation != "initial" and not re.fullmatch(r"[a-f0-9]{32}", generation):
                raise UserError("Le pack HD n’a pas pu être installé. Réessayez.")
            layers.append((candidate, generation))
        custom = sorted(overlays.glob("tex1_*.png")) if overlays is not None and overlays.is_dir() else []
        stamp = hashlib.sha256()
        stamp.update(b"orre-texture-view-union-2\0")
        for candidate, generation in layers[1:]:
            stamp.update((candidate.key + "\0" + generation + "\0").encode("ascii"))
        for path in custom:
            if path.is_symlink():
                raise UserError("Une texture personnalisée pointe vers un fichier externe.")
            stamp.update(path.name.encode()); stamp.update(bytes.fromhex(digest(path)))
        generation = layers[0][1]
        view = self.root / "TextureViews" / (pack.key + "-" + game_id + "-" + generation + "-" + stamp.hexdigest()[:24])
        if (view / "complete.json").is_file():
            return view / "Load"
        view.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".view-", dir=view.parent))
        try:
            target = stage / "Load/Textures" / game_id
            target.mkdir(parents=True)
            overrides = {texture_identity(p): p for p in custom}
            occupied = set(overrides)
            contributions = {}
            for candidate, _ in layers:
                supplied = set()
                linked = 0
                for source in sorted((self.location(candidate) / "Textures").iterdir()):
                    if source.suffix.lower() not in {".png", ".dds"}:
                        continue
                    identity = texture_identity(source)
                    if identity in occupied:
                        continue
                    if source.is_symlink() or not source.is_file():
                        raise UserError("Une texture personnalisée pointe vers un fichier externe.")
                    try:
                        os.link(source, target / source.name)
                    except OSError as error:
                        raise UserError("Le dossier partagé doit être sur un disque permettant les liens de fichiers.") from error
                    supplied.add(identity)
                    linked += 1
                occupied.update(supplied)
                contributions[candidate.key] = linked
            for path in overrides.values():
                shutil.copyfile(path, target / path.name)
            (stage / "complete.json").write_text(json.dumps({"pack": pack.key,
                "game_id": game_id, "overlays": len(custom),
                "packs": [{"key": item.key, "generation": generation} for item, generation in layers],
                "stock_files_by_pack": contributions,
                "priority": "custom > game pack > required fallback packs"}), encoding="utf-8")
            for attempt in range(10):
                try:
                    stage.rename(view)
                    break
                except (FileExistsError, PermissionError):
                    # Windows can briefly retain a directory handle after a
                    # scanner visits the freshly linked textures. Another
                    # builder may also have published this exact immutable view.
                    if (view / "complete.json").is_file():
                        break
                    if attempt == 9:
                        raise
                    time.sleep(.05 * (attempt + 1))
            return view / "Load"
        finally:
            if stage.exists():
                remove_owned(stage, view.parent)
