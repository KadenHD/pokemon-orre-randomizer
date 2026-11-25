"""Record a tested Windows installer without replacing existing release assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile


MANIFEST = "SHA256SUMS.json"
_NAME = re.compile(r"pokemon-orre-randomizer-(\d+\.\d+\.\d+(?:rc\d+)?)-(source\.zip|windows-x64\.zip|windows-x64-setup\.exe)\Z")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError("Duplicate release manifest entry")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(manifest, dict) or not manifest:
        raise RuntimeError("Invalid release manifest")
    versions, kinds = set(), set()
    for name, record in manifest.items():
        match = _NAME.fullmatch(name)
        if not match:
            raise RuntimeError("Unsafe release asset name")
        versions.add(match[1])
        kinds.add(match[2])
        if (not isinstance(record, dict) or set(record) != {"bytes", "sha256"}
                or type(record["bytes"]) is not int or record["bytes"] <= 0
                or not isinstance(record["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None):
            raise RuntimeError("Invalid release checksum record")
    if (len(versions) != 1 or "source.zip" not in kinds
            or "windows-x64-setup.exe" in kinds and "windows-x64.zip" not in kinds):
        raise RuntimeError("Release asset versions or archives differ")
    return manifest


def checksum(path: Path) -> dict:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def verify_checksum(path: Path, expected: dict) -> None:
    if not path.is_file() or path.is_symlink() or checksum(path) != expected:
        raise RuntimeError("Release asset hash mismatch: " + path.name)


def verify_installer(path: Path, expected: dict) -> dict:
    verify_checksum(path, expected)
    # Inno Setup's bootstrap is x86 even when its payload and target are x64.
    # Inspect the header without loading or executing an untrusted installer.
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            raise RuntimeError("Invalid Windows installer PE header")
        offset = struct.unpack_from("<I", header, 60)[0]
        if not 64 <= offset <= expected["bytes"] - 24:
            raise RuntimeError("Invalid Windows installer PE header")
        stream.seek(offset)
        signature = stream.read(6)
        if signature[:4] != b"PE\0\0" or signature[4:] not in (b"L\x01", b"d\x86"):
            raise RuntimeError("Invalid Windows installer PE header")
    return {"asset": path.name, **expected, "windows_installer_pe_verified": True}


def _publish_exclusive(staged: Path, destination: Path) -> None:
    if os.name == "nt":
        # Windows rename refuses an existing destination. Unlike a hard link,
        # it also works in restricted Windows directories and on FAT volumes.
        os.rename(staged, destination)
    else:
        # POSIX rename would replace an existing destination; link does not.
        os.link(staged, destination)


def publish_installer(release: Path, installer: Path) -> dict:
    """Publish the installer first, then atomically add its checksum record.

    Existing ZIP records are retained verbatim as JSON values. A failed manifest
    publication removes only the new installer owned by this call.
    Neither a previous installer nor a changed manifest is overwritten.
    """
    release = release.resolve(strict=True)
    manifest_path = release / MANIFEST
    original = manifest_path.read_bytes()
    manifest = load_manifest(manifest_path)
    windows = [name for name in manifest if name.endswith("-windows-x64.zip")]
    if len(windows) != 1:
        raise RuntimeError("Expected one corresponding Windows archive")
    name = windows[0].replace(".zip", "-setup.exe")
    if name in manifest or installer.name != name:
        raise RuntimeError("Installer already recorded or version differs")
    destination = release / name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Installer already exists: " + name)
    if not (release / windows[0]).is_file():
        raise RuntimeError("The corresponding Windows archive is missing")
    # The legacy installer-only workflow downloads just the Windows ZIP; keep
    # its published source record unchanged, checking the source when present.
    for archive, record in manifest.items():
        if (release / archive).exists():
            verify_checksum(release / archive, record)
    if installer.is_symlink():
        raise RuntimeError("The installer input must be a regular file")
    record = checksum(installer)
    verify_installer(installer, record)
    result = {**manifest, name: record}
    manifest_bytes = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    staged_installer = staged_manifest = None
    linked = False
    owned_identity = None
    try:
        descriptor, filename = tempfile.mkstemp(prefix=".installer-", suffix=".tmp", dir=release)
        staged_installer = Path(filename)
        with os.fdopen(descriptor, "wb") as output, installer.open("rb") as source:
            shutil.copyfileobj(source, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        verify_installer(staged_installer, record)
        staged_stat = staged_installer.stat()
        owned_identity = (staged_stat.st_dev, staged_stat.st_ino)
        descriptor, filename = tempfile.mkstemp(prefix=".checksums-", suffix=".tmp", dir=release)
        staged_manifest = Path(filename)
        with os.fdopen(descriptor, "wb") as output:
            output.write(manifest_bytes)
            output.flush()
            os.fsync(output.fileno())
        if manifest_path.read_bytes() != original:
            raise RuntimeError("Release manifest changed during installer publication")
        # Both platform primitives publish atomically without overwriting a
        # concurrently created asset, on this same release filesystem.
        _publish_exclusive(staged_installer, destination)
        linked = True
        if manifest_path.read_bytes() != original:
            raise RuntimeError("Release manifest changed during installer publication")
        os.replace(staged_manifest, manifest_path)
        return result
    except BaseException:
        # A signal can arrive just after the atomic replace. Never remove an
        # installer if its new manifest is already visible to consumers.
        try:
            published = manifest_path.read_bytes() == manifest_bytes
        except FileNotFoundError:
            published = False
        except OSError:
            # If the manifest cannot be inspected, keep the installer rather
            # than risk leaving a committed manifest pointing at a missing file.
            published = True
        if not published and linked:
            try:
                destination_stat = destination.lstat()
            except FileNotFoundError:
                pass
            else:
                if (destination_stat.st_dev, destination_stat.st_ino) == owned_identity:
                    destination.unlink()
        raise
    finally:
        for path in (staged_installer, staged_manifest):
            if path is not None:
                path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", required=True, type=Path)
    parser.add_argument("--installer", required=True, type=Path,
                        help="Compiled and smoke-tested installer to publish")
    args = parser.parse_args()
    manifest = publish_installer(args.release_dir, args.installer)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
