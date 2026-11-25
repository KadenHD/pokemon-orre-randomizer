"""Audit local release assets and test the sources away from the game dump."""
import hashlib
import argparse
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import signal
import subprocess
import sys
import tempfile
import types
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME
from scripts.release_media import (BINGO_AUTHORING_ROOT, bingo_authoring_media,
                                  documentation_media, game_asset_name_allowed)
from scripts.build_desktop import REQUIRED_RUNTIME_MODULES, REQUIRED_IMAGE_DECODERS, RUNTIME_BUILD_RECORD
from scripts.release_checksums import load_manifest, verify_checksum, verify_installer

FORBIDDEN = {".iso", ".rvz", ".gcm", ".fsys", ".dol", ".rel", ".raw", ".gci", ".sav"}
SOURCE_ROOT = f"{REPOSITORY_NAME}/"
BINARY_ROOT = f"{APP_EXECUTABLE}/_internal/"
SOURCE_TEST_TIMEOUT = 13 * 60


def reject_private_build_paths(payload: bytes, name: str):
    lowered = payload.lower()
    for directory in (ROOT, Path.home()):
        for spelling in {str(directory), directory.as_posix()}:
            for encoding in ("utf-8", "utf-16le"):
                if spelling.encode(encoding).lower() in lowered:
                    raise RuntimeError("Private build path in release file: " + name)


def verify_frozen_code(executable: Path) -> dict:
    """Read bytecode from our hashed executable without executing any module."""
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(executable))
    embedded = [name for name, entry in archive.toc.items() if entry[-1] == "z"]
    if len(embedded) != 1:
        raise RuntimeError("Expected one embedded Python module archive")
    modules = archive.open_embedded_archive(embedded[0])
    missing = (REQUIRED_RUNTIME_MODULES | REQUIRED_IMAGE_DECODERS) - set(modules.toc)
    if missing:
        raise RuntimeError("Missing frozen game-folder modules: " + ", ".join(sorted(missing)))
    names = [name for name in modules.toc if name == "orre_randomizer" or name.startswith("orre_randomizer.")]
    def inspect_code(code):
        if not isinstance(code, types.CodeType):
            return
        if PureWindowsPath(code.co_filename).drive or PurePosixPath(code.co_filename).is_absolute():
            raise RuntimeError("Absolute source path in frozen application bytecode")
        for value in code.co_consts:
            if isinstance(value, str):
                reject_private_build_paths(value.encode("utf-8"), "frozen application bytecode")
            elif isinstance(value, types.CodeType):
                inspect_code(value)
    for name in names:
        inspect_code(modules.extract(name))
    return {"application_modules": len(names), "required_runtime_modules": len(REQUIRED_RUNTIME_MODULES),
            "required_image_decoders": len(REQUIRED_IMAGE_DECODERS),
            "private_source_paths_absent": True}


def verify_runtime_inputs(archive: zipfile.ZipFile, release: Path, manifest: dict):
    source_names = [name for name in manifest if name.endswith("-source.zip")]
    if len(source_names) != 1:
        raise RuntimeError("Expected one corresponding source archive")
    source_name = source_names[0]
    source_copy = archive.read(f"{APP_EXECUTABLE}/" + source_name)
    if hashlib.sha256(source_copy).hexdigest() != manifest[source_name]["sha256"]:
        raise RuntimeError("The binary package contains a different source archive")
    record = json.loads(archive.read(f"{APP_EXECUTABLE}/" + RUNTIME_BUILD_RECORD))
    if record.get("schema") != 1 or not isinstance(record.get("files"), dict) or not record["files"]:
        raise RuntimeError("Invalid runtime build input manifest")
    binary_names = set(archive.namelist())
    with zipfile.ZipFile(release / source_name) as sources:
        for name, digest in record["files"].items():
            if (not isinstance(name, str) or PureWindowsPath(name).drive or "\\" in name
                    or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts):
                raise RuntimeError("Invalid runtime build input path")
            if name.startswith("orre_randomizer/_native/"):
                payload = archive.read(BINARY_ROOT + name)
            else:
                payload = sources.read(SOURCE_ROOT + name)
            if hashlib.sha256(payload).hexdigest() != digest:
                raise RuntimeError("Packaged runtime input differs from its source: " + name)
            if BINARY_ROOT + name in binary_names and hashlib.sha256(archive.read(BINARY_ROOT + name)).hexdigest() != digest:
                raise RuntimeError("Packaged runtime data differs from its source: " + name)
    return {"runtime_inputs": len(record["files"]), "corresponding_source_archive_verified": True}


def application_media_allowed(name: str, binary: bool) -> bool:
    prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/assets/app/"
    allowed = {prefix + "icon.ico", prefix + "logo.png", prefix + "controller.png"}
    if not binary:
        allowed.add(prefix + "icon.png")
    return name in allowed


def verify_source_tests(directory: Path) -> str:
    runner = directory / "scripts/run_tests.py"
    if not runner.is_file():
        raise RuntimeError("The source archive is missing its test runner")
    command = [sys.executable, "-X", "utf8", str(runner)]
    print("Running tests from the extracted source archive.", flush=True)
    with subprocess.Popen(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=os.name != "nt") as process:
        try:
            stdout, stderr_bytes = process.communicate(timeout=SOURCE_TEST_TIMEOUT)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                # The runner owns a kill-on-close Windows job. Terminating it
                # closes the last non-inherited handle and kills its workers.
                process.kill()
            else:
                # Workers inherit the private session, never the caller's group.
                os.killpg(process.pid, signal.SIGKILL)
            _, stderr_bytes = process.communicate(timeout=5)
            progress = stderr_bytes.decode("utf-8", errors="replace").splitlines()
            tail = "\n".join(progress[-25:])
            raise RuntimeError(f"Source archive tests exceeded {SOURCE_TEST_TIMEOUT} seconds.\n{tail}") from None
    stderr = stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if process.returncode:
        raise RuntimeError(stdout.decode("utf-8", errors="replace") + stderr)
    return stderr.rsplit("\n" + "-" * 70 + "\n", 1)[-1].strip()


def verify_manifest_assets(release: Path) -> tuple[dict, dict]:
    """Check every download before the more expensive ZIP and source audits."""
    manifest = load_manifest(release / "SHA256SUMS.json")
    installers = {}
    for filename, expected in manifest.items():
        if filename.endswith("-setup.exe"):
            installers[filename] = verify_installer(release / filename, expected)
        else:
            verify_checksum(release / filename, expected)
    return manifest, installers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("local", "public"), default="local")
    parser.add_argument("--release-dir", type=Path, help="Audit a separate local candidate directory")
    args = parser.parse_args()
    (ROOT / "build").mkdir(exist_ok=True)
    public = args.edition == "public"
    release = args.release_dir.resolve() if args.release_dir else ROOT / "dist" / ("public" if public else "")
    manifest, installers = verify_manifest_assets(release)
    checks = []
    for filename in manifest:
        path = release / filename
        if filename in installers:
            checks.append(installers[filename])
            continue
        with zipfile.ZipFile(path) as archive:
            binary = filename.endswith("-windows-x64.zip")
            prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/assets/game/"
            pack = json.loads(archive.read(prefix + "provenance.json"))
            game_assets = {prefix + relative for relative in pack["files"]}
            doc_prefix = (f"{APP_EXECUTABLE}/" if binary else SOURCE_ROOT) + "docs/images/"
            doc_assets = {doc_prefix + name for name in documentation_media(
                lambda name: archive.read(doc_prefix + name))}
            authoring_prefix = SOURCE_ROOT + BINGO_AUTHORING_ROOT
            authoring_assets = (set() if binary else {authoring_prefix + name
                for name in bingo_authoring_media(lambda name: archive.read(authoring_prefix + name))})
            for item in archive.infolist():
                name = Path(item.filename)
                if (PurePosixPath(item.filename).is_absolute() or PureWindowsPath(item.filename).drive or
                        "\\" in item.filename or ".." in name.parts or name.suffix.lower() in FORBIDDEN):
                    raise RuntimeError(f"Forbidden release path: {item.filename}")
                if "dolphin" in name.name.lower() and name.suffix.lower() == ".exe":
                    raise RuntimeError("Dolphin was bundled")
                parts = [part.lower() for part in name.parts]
                if any(part in {"build", "analysis", "dolphin-x64"} or
                       part == "game" and not (index > 1 and parts[index-2:index] == ["orre_randomizer", "assets"])
                       for index, part in enumerate(parts)):
                    raise RuntimeError(f"Local data folder in release: {name}")
                if item.filename.startswith(prefix) and item.filename not in game_assets | {prefix + "provenance.json"}:
                    raise RuntimeError("Unlisted interface asset: " + item.filename)
                if (name.suffix.lower() in {".wav", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".ogg", ".flac", ".ico", ".pkx"}
                        and not application_media_allowed(item.filename, binary)
                        and item.filename not in game_assets | doc_assets | authoring_assets):
                    raise RuntimeError("Unlisted release media: " + item.filename)
                if name.suffix.lower() in {".py", ".ps1", ".md", ".json", ".txt", ".toml", ".rs", ".c", ".spec", ".exe", ".dll", ".pyd"}:
                    reject_private_build_paths(archive.read(item), item.filename)
            if archive.testzip() is not None:
                raise RuntimeError("ZIP integrity check failed")
            helper_name = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/windows_update.ps1"
            if helper_name not in archive.namelist():
                raise RuntimeError("Windows update helper is missing")
            if binary:
                runtime_verification = verify_runtime_inputs(archive, release, manifest)
                with tempfile.TemporaryDirectory(prefix="frozen-code-audit-", dir=ROOT / "build") as temporary:
                    executable = Path(temporary) / f"{APP_EXECUTABLE}.exe"
                    executable.write_bytes(archive.read(f"{APP_EXECUTABLE}/{APP_EXECUTABLE}.exe"))
                    runtime_verification.update(verify_frozen_code(executable))
                if BINARY_ROOT + "orre_randomizer/_native/orre_disc.dll" not in archive.namelist():
                    raise RuntimeError("The integrated disc converter is missing")
                if f"{APP_EXECUTABLE}/licenses/disc/dependencies.json" not in archive.namelist():
                    raise RuntimeError("Disc converter dependency notices are missing")
                for name in ("OrreLauncher.exe", "orre_musyx.dll", "orre_musyx.json"):
                    if BINARY_ROOT + "orre_randomizer/_native/" + name not in archive.namelist():
                        raise RuntimeError("The game-folder runtime is incomplete: " + name)
                if f"{APP_EXECUTABLE}/licenses/music/musyx-CC0.txt" not in archive.namelist():
                    raise RuntimeError("Music renderer notices are missing")
                if f"{APP_EXECUTABLE}/licenses/images/Pillow-LICENSE.txt" not in archive.namelist():
                    raise RuntimeError("HD image decoder notices are missing")
                root = f"{APP_EXECUTABLE}/"
                owned = json.loads(archive.read(root + "update-files.json"))
                entries = [name[len(root):] for name in archive.namelist()]
                if (not isinstance(owned, list) or not all(isinstance(name, str) for name in owned)
                        or len(owned) != len(set(owned)) or set(owned) != set(entries)):
                    raise RuntimeError("Portable update file manifest differs from the archive")
            app_prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/assets/app/"
            for asset_manifest_name, assets in (("provenance.json", ("icon.ico",) if binary else ("icon.ico", "icon.png")),
                                     ("logo.json", ("logo.png",)), ("controller.json", ("controller.png",))):
                manifest_assets = json.loads(archive.read(app_prefix + asset_manifest_name))
                for relative in assets:
                    payload = archive.read(app_prefix + relative)
                    expected_asset = manifest_assets["files"][relative]
                    if (len(payload) != expected_asset["bytes"] or
                            hashlib.sha256(payload).hexdigest() != expected_asset["sha256"]):
                        raise RuntimeError("Invalid application asset: " + relative)
            for relative, record in pack["files"].items():
                if not game_asset_name_allowed(relative):
                    raise RuntimeError("Unsafe interface asset name")
                payload = archive.read(prefix + relative)
                if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
                    raise RuntimeError("Invalid packaged interface asset: " + relative)
            checks.append({"archive": filename, "entries": len(archive.infolist()), "integrity_ok": True,
                           "no_rom_saves_or_emulator_files": True,
                           "application_icon_verified": True,
                           "application_logo_verified": True,
                           "documentation_screenshots_verified": True,
                           "game_assets_included": True,
                           "interface_pack_at_runtime_location": True})
            if binary:
                checks[-1].update(runtime_verification)
            if filename.endswith("-source.zip"):
                # A fresh owned directory, with paths verified above.
                with tempfile.TemporaryDirectory(prefix="source-test-", dir=ROOT / "build") as temp:
                    archive.extractall(temp)
                    checks[-1]["tests_without_rom"] = verify_source_tests(Path(temp) / REPOSITORY_NAME)
    target = ROOT / "build" / ("desktop-release-public-audit.json" if public else "desktop-release-audit.json")
    target.write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
