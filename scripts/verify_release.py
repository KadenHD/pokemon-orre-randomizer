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
from colosseum_randomizer import APP_EXECUTABLE, REPOSITORY_NAME

FORBIDDEN = {".iso", ".rvz", ".gcm", ".fsys", ".dol", ".rel", ".raw", ".gci", ".sav"}
SOURCE_ROOT = f"{REPOSITORY_NAME}/"
BINARY_ROOT = f"{APP_EXECUTABLE}/_internal/"


def application_media_allowed(name: str, binary: bool) -> bool:
    prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "colosseum_randomizer/assets/app/"
    allowed = {prefix + "icon.ico"}
    if not binary:
        allowed.add(prefix + "icon.png")
    return name in allowed


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
            for item in archive.infolist():
                name = Path(item.filename)
                if (PurePosixPath(item.filename).is_absolute() or PureWindowsPath(item.filename).drive or
                        "\\" in item.filename or ".." in name.parts or name.suffix.lower() in FORBIDDEN):
                    raise RuntimeError(f"Forbidden release path: {item.filename}")
                if "dolphin" in name.name.lower() and name.suffix.lower() == ".exe":
                    raise RuntimeError("Dolphin was bundled")
                parts = [part.lower() for part in name.parts]
                if any(part in {"build", "analysis", "dolphin-x64"} or
                       part == "game" and not (index > 1 and parts[index-2:index] == ["colosseum_randomizer", "assets"])
                       for index, part in enumerate(parts)):
                    raise RuntimeError(f"Local data folder in release: {name}")
                if public and ("assets/game/" in item.filename.lower() or
                               name.suffix.lower() in {".wav", ".png", ".jpg", ".jpeg", ".mp3", ".ogg", ".flac", ".ico"}
                               and not application_media_allowed(item.filename, binary)):
                    raise RuntimeError("Game media in public release: " + item.filename)
            if archive.testzip() is not None:
                raise RuntimeError("ZIP integrity check failed")
            app_prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "colosseum_randomizer/assets/app/"
            icon = json.loads(archive.read(app_prefix + "provenance.json"))
            for relative in (("icon.ico",) if binary else ("icon.ico", "icon.png")):
                payload = archive.read(app_prefix + relative)
                expected_icon = icon["files"][relative]
                if (len(payload) != expected_icon["bytes"] or
                        hashlib.sha256(payload).hexdigest() != expected_icon["sha256"]):
                    raise RuntimeError("Invalid application icon: " + relative)
            prefix = (BINARY_ROOT if binary else SOURCE_ROOT) + "colosseum_randomizer/assets/game/"
            if not public:
                pack = json.loads(archive.read(prefix + "provenance.json"))
                for relative, record in pack["files"].items():
                    if PureWindowsPath(relative).drive or "\\" in relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
                        raise RuntimeError("Unsafe interface asset name")
                    payload = archive.read(prefix + relative)
                    if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
                        raise RuntimeError("Invalid packaged interface asset: " + relative)
            checks.append({"archive": filename, "entries": len(archive.infolist()), "integrity_ok": True,
                           "no_rom_saves_or_emulator_files": True,
                           "application_icon_verified": True,
                           "game_assets_included": not public})
            if not public:
                checks[-1]["interface_pack_at_runtime_location"] = True
            if filename.endswith("-source.zip"):
                # A fresh owned directory, with paths verified above.
                with tempfile.TemporaryDirectory(prefix="source-test-", dir=ROOT / "build") as temp:
                    archive.extractall(temp)
                    clean = Path(temp) / REPOSITORY_NAME
                    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                                            cwd=clean, capture_output=True, text=True)
                    if result.returncode:
                        raise RuntimeError(result.stdout + result.stderr)
                    checks[-1]["tests_without_rom"] = result.stderr.strip()
    target = ROOT / "build" / ("desktop-release-public-audit.json" if public else "desktop-release-audit.json")
    target.write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
