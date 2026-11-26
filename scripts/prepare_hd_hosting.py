"""Prepare both pinned HD author archives for review, entirely offline."""
from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orre_randomizer.hd_packs import PACKS, checkpoint, digest, remove_owned
from orre_randomizer.service import Cancelled

_CHUNK_BYTES = 4 * 1024**2


def _reject_links(path: Path):
    for current in (path, *path.parents):
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError(f"Symbolic links and junctions are not accepted: {current}")


def _base_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if (not value or any(character.isspace() for character in value)
            or parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or "?" in value or "#" in value or "\\" in value):
        raise ValueError("The proposed base URL must be HTTPS, without credentials, query or fragment")
    parsed.port  # Validate a supplied port without performing a network request.
    return value.rstrip("/")


def _verify(path: Path, part, cancel):
    checkpoint(cancel)
    _reject_links(path)
    if not path.is_file():
        raise ValueError(f"Archive is not a regular file: {path}")
    before = path.stat()
    if before.st_size != part.size:
        raise ValueError(f"Archive size differs from the pinned release: {path.name}")
    if digest(path, cancel) != part.sha256:
        raise ValueError(f"Archive SHA-256 differs from the pinned release: {path.name}")
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError(f"Archive changed while being verified: {path.name}")
    checkpoint(cancel)


def _copy_archive(source: Path, destination: Path, cancel):
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        while True:
            checkpoint(cancel)
            data = incoming.read(_CHUNK_BYTES)
            if not data:
                break
            outgoing.write(data)
        checkpoint(cancel)


def _publish(stage: Path, output: Path):
    """Atomically rename a directory while refusing even a concurrent empty target."""
    if os.name == "nt":
        deadline = time.monotonic() + 5
        while True:
            try:
                os.rename(stage, output)  # Never replace an existing target.
                return
            except PermissionError as error:
                # Windows reports an existing directory as ACCESS_DENIED on
                # some filesystems; scanners can also briefly lock new files.
                if getattr(error, "winerror", None) in (5, 32) and os.path.lexists(output):
                    raise FileExistsError(errno.EEXIST, "Destination already exists", str(output)) from error
                if getattr(error, "winerror", None) not in (5, 32) or time.monotonic() >= deadline:
                    raise
                time.sleep(.1)
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        rename = getattr(library, "renameat2", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "Atomic no-replace directory rename is unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(stage), -100, os.fsencode(output), 1)  # RENAME_NOREPLACE
    elif sys.platform == "darwin":
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(stage), os.fsencode(output), 4)  # RENAME_EXCL
    else:
        raise OSError(errno.ENOTSUP, "Atomic no-replace directory rename is unavailable")
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(output))


def _readme(manifest: dict) -> str:
    lines = ["# HD hosting preparation - both original author packs", "",
             "This is a private, offline preparation bundle. No production hosting is configured.",
             "Nothing was uploaded and no application catalog or download setting was changed.", "",
             "Both original ZIPs are included unchanged. Treat them as immutable: a hardlinked",
             "archive shares its data with the supplied source. This tool changes neither archive",
             "contents nor permissions. Keep manifest.json with the archives.", ""]
    for item in manifest["packs"]:
        lines.extend([f"## {item['game']} {item['version']}", "",
                      f"Author credit: {item['author']}",
                      f"Author publication: {item['source']}",
                      f"Original archive source: {item['archive_source']}",
                      f"Original filename: {item['archive_filename']}",
                      f"Prepared path: {item['relative_path']}",
                      f"Bytes: {item['size']}", f"SHA-256: {item['sha256']}", ""])
        if "proposed_download_url" in item:
            lines.extend([f"Proposed URL, not deployed: {item['proposed_download_url']}", ""])
    lines.extend([
        "## Credits and terms", "",
        "Colosseum V2: the archive manifest credits Sephie; the announcement was posted by",
        "u/Bun-bun45. These credits do not assert that the two names identify the same person.",
        "No explicit redistribution license was found in the inspected author announcement",
        "or original archive. The original archive remains intact; its excluded_paths are",
        "application installation choices, not changes to the author ZIP.", "",
        "XD/XG v1.0: mikeyX. The author's separate Inkscape UI vector files have an explicit",
        "CC BY-NC-SA 4.0 statement. That statement does not establish a blanket license for",
        "the complete texture pack. The author credits these ESRGAN models:", "",
        "- CC BY-NC-SA 4.0: 4x-UltraSharp, 4x-Fabric and Fabric-Alt (Kim2091);",
        "  Misc (Alsa); 4x_PocketMonsters-Alpha (Joey).",
        "- CC BY-NC 4.0: FuzzyBox / 4x_FuzzyBox (BlueAmulet); SpongeBob (Joey).",
        "- WTFPL: 1x_BCGone-DetailedV2_40-60_115000_G,",
        "  1x_DitherDeleter-Smooth_104000_G, 1x_NoiseToner_Uniform_100000_G",
        "  (Mutin_Choler); 4x_muy4_035_1.pth (katoumegumi_).",
        "- License unclear or unknown in the author's credits: 4x_Training4Melozard_Anime",
        "  (Joey); Ground (ZaphodBreeblebox); 4x_ThiefGold_110000 (Akven).", "",
        "Special thanks in the XD author's credits: NGC/WII Pokemon ROM hacking Discord.",
        "Original game artwork rights remain separate from this project's code license.",
        "Neither pack is relicensed by preparing this bundle. Public mirroring requires",
        "appropriate permissions. A hosting proposal covering BOTH packs must be reviewed",
        "and approved before any production deployment.", "",
        "## Review before deployment", "",
        "Confirm permissions, storage/transfer costs, fixed HTTPS URLs, resumable downloads,",
        "availability, exact SHA-256 verification and an explicit version/update policy.",
        "Any proposed URLs in this manifest are review data only.", ""])
    return "\n".join(lines)


def prepare_hosting(colosseum: Path, xd: Path, output: Path, *, base_url: str | None = None,
                    cancel=None) -> dict:
    """Verify both sources before staging; publish one complete directory or leave none."""
    cancel = cancel if cancel is not None else threading.Event()
    checkpoint(cancel)
    proposed_base = _base_url(base_url)
    output = Path(os.path.abspath(output))
    _reject_links(output)
    if os.path.lexists(output):
        raise FileExistsError(f"Output already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError("The output parent directory must already exist")
    prepared = []
    for game, supplied in (("colosseum", colosseum), ("xd", xd)):
        pack = PACKS[game]
        if (pack.game != game or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", pack.version)
                or len(pack.parts) != 1):
            raise ValueError("Expected one pinned author archive per game and a safe version")
        part = pack.parts[0]
        if not re.fullmatch(r"[0-9a-f]{64}", part.sha256) or part.size <= 0:
            raise ValueError("Invalid pinned archive digest or size")
        source = Path(os.path.abspath(supplied))
        filename = part.filename or source.name
        if (not filename or Path(filename).name != filename or filename in (".", "..")
                or any(character in filename for character in '<>:"/\\|?*')):
            raise ValueError("Invalid original archive filename")
        _verify(source, part, cancel)
        relative = PurePosixPath("packs", game, pack.version, part.sha256[:12] + ".zip").as_posix()
        item = {"game": game, "version": pack.version, "archive_filename": filename,
                "relative_path": relative, "sha256": part.sha256, "size": part.size,
                "author": pack.author, "source": pack.source, "archive_source": pack.archive_source,
                "excluded_paths": list(pack.excluded_paths)}
        if proposed_base is not None:
            item["proposed_download_url"] = proposed_base + "/" + relative
        prepared.append((source, part, item))
    checkpoint(cancel)
    _reject_links(output)
    if os.path.lexists(output):
        raise FileExistsError(f"Output already exists: {output}")
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    try:
        for source, part, item in prepared:
            checkpoint(cancel)
            _reject_links(source)
            destination = stage / item["relative_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, destination, follow_symlinks=False)
                item["storage"] = "hardlink"
            except OSError:
                _copy_archive(source, destination, cancel)
                item["storage"] = "copy"
            _verify(destination, part, cancel)
        manifest = {"schema": 1, "production_configured": False, "published": False,
                    "proposed_base_url": proposed_base,
                    "packs": [item for _, _, item in prepared]}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
        (stage / "README.md").write_text(_readme(manifest), encoding="utf-8")
        checkpoint(cancel)
        _reject_links(output)
        _publish(stage, output)
        return manifest
    finally:
        if os.path.lexists(stage):
            _reject_links(stage)
            remove_owned(stage, output.parent)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--colosseum", required=True, type=Path, help="Original pinned Colosseum ZIP")
    parser.add_argument("--xd", required=True, type=Path, help="Original pinned XD PNG Texture Pack ZIP")
    parser.add_argument("--output", required=True, type=Path, help="New output directory; parent must exist")
    parser.add_argument("--base-url", help="Optional proposed HTTPS base URL; configures no service")
    args = parser.parse_args(argv)
    try:
        manifest = prepare_hosting(args.colosseum, args.xd, args.output, base_url=args.base_url)
    except KeyboardInterrupt:
        parser.exit(130, "Preparation cancelled.\n")
    except (OSError, ValueError, Cancelled) as error:
        parser.exit(1, f"Preparation failed: {error}\n")
    print(f"Prepared both packs: {Path(args.output).absolute() / 'manifest.json'}")
    print(f"Archive bytes: {sum(item['size'] for item in manifest['packs'])}; production configured: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
