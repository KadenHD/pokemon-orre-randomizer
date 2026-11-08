"""Audit local release archives and test the sources away from the game dump."""
import hashlib
import argparse
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME
from scripts.release_media import documentation_media

FORBIDDEN = {".iso", ".rvz", ".gcm", ".fsys", ".dol", ".rel", ".raw", ".gci", ".sav"}
SOURCE_ROOT = f"{REPOSITORY_NAME}/"
BINARY_ROOT = f"{APP_EXECUTABLE}/_internal/"
SOURCE_TEST_TIMEOUT = 600


def application_media_allowed(name: str, binary: bool) -> bool:
    prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/assets/app/"
    allowed = {prefix + "icon.ico", prefix + "logo.png"}
    if not binary:
        allowed.add(prefix + "icon.png")
    return name in allowed


def verify_source_tests(directory: Path) -> str:
    command = [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-v"]
    print("Running tests from the extracted source archive.", flush=True)
    try:
        result = subprocess.run(command, cwd=directory, capture_output=True, timeout=SOURCE_TEST_TIMEOUT)
    except subprocess.TimeoutExpired as error:
        progress = (error.stderr or b"").decode("utf-8", errors="replace").splitlines()
        tail = "\n".join(progress[-25:])
        raise RuntimeError(f"Source archive tests exceeded {SOURCE_TEST_TIMEOUT} seconds.\n{tail}") from None
    stderr = result.stderr.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if result.returncode:
        raise RuntimeError(result.stdout.decode("utf-8", errors="replace") + stderr)
    return stderr.rsplit("\n" + "-" * 70 + "\n", 1)[-1].strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("local", "public"), default="local")
    args = parser.parse_args()
    (ROOT / "build").mkdir(exist_ok=True)
    public = args.edition == "public"
    release = ROOT / "dist" / ("public" if public else "")
    manifest = json.loads((release / "SHA256SUMS.json").read_text())
    checks = []
    for filename, expected in manifest.items():
        path = release / filename
        if path.name != filename or path.suffix != ".zip":
            raise RuntimeError("Unsafe archive name")
        if path.stat().st_size != expected["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise RuntimeError("Archive hash mismatch")
        with zipfile.ZipFile(path) as archive:
            binary = filename.endswith("-windows-x64.zip")
            prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/assets/game/"
            pack = json.loads(archive.read(prefix + "provenance.json"))
            game_assets = {prefix + relative for relative in pack["files"]}
            doc_prefix = (f"{APP_EXECUTABLE}/" if binary else SOURCE_ROOT) + "docs/images/"
            doc_assets = {doc_prefix + name for name in documentation_media(
                lambda name: archive.read(doc_prefix + name))}
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
                if (name.suffix.lower() in {".wav", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".ogg", ".flac", ".ico"}
                        and not application_media_allowed(item.filename, binary)
                        and item.filename not in game_assets | doc_assets):
                    raise RuntimeError("Unlisted release media: " + item.filename)
            if archive.testzip() is not None:
                raise RuntimeError("ZIP integrity check failed")
            app_prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "orre_randomizer/assets/app/"
            for asset_manifest_name, assets in (("provenance.json", ("icon.ico",) if binary else ("icon.ico", "icon.png")),
                                     ("logo.json", ("logo.png",))):
                manifest_assets = json.loads(archive.read(app_prefix + asset_manifest_name))
                for relative in assets:
                    payload = archive.read(app_prefix + relative)
                    expected_asset = manifest_assets["files"][relative]
                    if (len(payload) != expected_asset["bytes"] or
                            hashlib.sha256(payload).hexdigest() != expected_asset["sha256"]):
                        raise RuntimeError("Invalid application asset: " + relative)
            for relative, record in pack["files"].items():
                if (PureWindowsPath(relative).drive or "\\" in relative or Path(relative).is_absolute()
                        or ".." in Path(relative).parts or Path(relative).suffix not in {".png", ".wav", ".json", ".md"}):
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
