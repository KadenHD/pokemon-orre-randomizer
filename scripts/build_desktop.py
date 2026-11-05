"""Build an offline Windows app and an allowlisted source archive. No ROMs."""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME, __version__
from scripts.release_media import documentation_media


def source_files(*, include_game_assets: bool = True) -> list[Path]:
    files = [ROOT / name for name in ("README.md", "CHANGELOG.md", "RESEARCH.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
             "CONTRIBUTING.md", "PRODUCT.md", "DESIGN.md", "pyproject.toml", "requirements-build.txt", ".gitignore", ".gitattributes",
             "lancer-randomizer.ps1")]
    for directory, extensions in (("orre_randomizer", {".py"}), ("tests", {".py"}),
                                  ("scripts", {".py", ".ps1", ".spec", ".iss"}), ("docs", {".md"}),
                                  ("licenses", {".txt", ".json", ".md"}), (".github", {".yml", ".md"})):
        files += [p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in extensions]
    files += [ROOT / "native/Cargo.toml", ROOT / "native/Cargo.lock", ROOT / "native/src/lib.rs"]
    files.append(ROOT / "docs/reverse-engineering/baseline.json")
    documentation = ROOT / "docs/images"
    for name in documentation_media(lambda name: (documentation / name).read_bytes()):
        files.append(documentation / name)
    files += [ROOT / "tests/fixtures/presets" / f"rc2-{game}-{mode}.json"
              for game in ("colosseum", "xd") for mode in ("moves", "species")]
    files += [ROOT / "orre_randomizer/assets/app" / name
              for name in ("icon.png", "icon.ico", "provenance.json", "logo.png", "logo.json", "README.md")]
    # Explicit local interface pack exported once from the supplied game. Never
    # sweep game/, build/, user caches or arbitrary assets into a distribution.
    if include_game_assets:
        pack = ROOT / "orre_randomizer/assets/game"
        manifest = json.loads((pack / "provenance.json").read_text("utf-8"))
        for name, expected in manifest["files"].items():
            path = pack / name
            if (not path.resolve().is_relative_to(pack.resolve()) or path.is_symlink() or
                    path.suffix not in {".png", ".wav", ".json", ".md"} or
                    path.stat().st_size != expected["bytes"] or
                    hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]):
                raise RuntimeError("Invalid interface asset: " + name)
            files.append(path)
        if set(pack.rglob("*")) - {path for path in pack.rglob("*") if path.is_dir()} != set(
                pack / name for name in manifest["files"]) | {pack / "provenance.json"}:
            raise RuntimeError("Unlisted files in interface pack")
        files.append(pack / "provenance.json")
    sidecar = ROOT / ".impeccable/design.json"
    if sidecar.is_file():
        files.append(sidecar)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("Linked or external source file refused: " + str(path))
    return sorted(set(files))


def zip_sources(destination: Path, *, include_game_assets: bool = True):
    # A positive list, not a blacklist: game/, build/, disc images and emulator
    # files can never be accidentally picked up by a new root file or folder.
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(include_game_assets=include_game_assets):
            archive.write(path, f"{REPOSITORY_NAME}/" + path.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--edition", choices=("local", "public"), default="local",
                        help="Choose the output directory; both editions include the verified interface pack")
    parser.add_argument("--skip-freeze", action="store_true", help="Repackage the already tested executable without recompiling it")
    args = parser.parse_args()
    include_game_assets = True
    app_assets = ROOT / "orre_randomizer/assets/app"
    for filename, allowed in (("provenance.json", {"icon.png", "icon.ico"}), ("logo.json", {"logo.png"})):
        manifest = json.loads((app_assets / filename).read_text("utf-8"))
        if set(manifest["files"]) != allowed:
            raise SystemExit("Unexpected application assets in " + filename)
        for name, expected in manifest["files"].items():
            path = app_assets / name
            if (path.is_symlink() or not path.resolve().is_relative_to(app_assets.resolve()) or
                    path.stat().st_size != expected["bytes"] or
                    hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]):
                raise SystemExit("Invalid application asset: " + name)
    if include_game_assets:
        from orre_randomizer.resources import interface_assets, music_track, menu_icon
        images, sounds = interface_assets()
        if len(images) != 5 or len(sounds) != 3 or music_track() is None or menu_icon() is None:
            raise SystemExit("The exported interface pack is incomplete.")
    source_files(include_game_assets=include_game_assets)
    release = ROOT / "dist" / ("public" if args.edition == "public" else "")
    release.mkdir(parents=True, exist_ok=True)
    source_zip = release / f"{REPOSITORY_NAME}-{__version__}-source.zip"
    if source_zip.exists():
        raise SystemExit(f"Release already exists: {source_zip}; move it aside before rebuilding.")
    if not args.source_only:
        if sys.platform != "win32":
            raise SystemExit("Build the Windows executable on Windows; use --source-only elsewhere.")
        work = ROOT / "build" / ("pyinstaller-public" if args.edition == "public" else "pyinstaller")
        app = release / "windows" / f"{APP_EXECUTABLE}-{__version__}"
        for folder in (app, work):
            if not folder.resolve().is_relative_to(ROOT) or folder.resolve() == ROOT:
                raise SystemExit("Build directory escaped the project; refusing cleanup.")
        command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                   "--distpath", str(release / "windows"), "--workpath", str(work),
                   str(ROOT / "scripts/desktop.spec")]
        # Other developer tools on PATH can have incompatible DLLs named icuuc.dll,
        # libcrypto, or Windows API shims. Resolve against Python/Qt and the OS only.
        environment = os.environ.copy()
        environment["ORRE_BUNDLE_GAME_ASSETS"] = "1" if include_game_assets else "0"
        windows = Path(environment.get("SystemRoot", r"C:\Windows"))
        environment["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent,
            Path(sys.base_prefix), Path(sys.base_prefix) / "Scripts", windows / "System32", windows)))
        if not args.skip_freeze:
            subprocess.run([sys.executable, str(ROOT / "scripts/build_native.py")], cwd=ROOT, check=True)
            subprocess.run(command, cwd=ROOT, env=environment, check=True)
        elif not (app / f"{APP_EXECUTABLE}.exe").is_file():
            raise SystemExit("No executable to repackage; build it first.")
        elif json.loads((app / "build-edition.json").read_text("utf-8"))["game_assets"] != include_game_assets:
            raise SystemExit("Executable edition mismatch; rebuild it before packaging.")
        (app / "build-edition.json").write_text(json.dumps({"edition": args.edition,
            "game_assets": include_game_assets}, indent=2) + "\n", encoding="utf-8")
        for name in ("README.md", "CHANGELOG.md", "RESEARCH.md", "CONTRIBUTING.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "requirements-build.txt"):
            shutil.copyfile(ROOT / name, app / name)
        for path in (ROOT / "docs").rglob("*.md"):
            target = app / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        for name in documentation_media(lambda name: (ROOT / "docs/images" / name).read_bytes()):
            target = app / "docs/images" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "docs/images" / name, target)
        shutil.copytree(ROOT / "licenses", app / "licenses", dirs_exist_ok=True)
        sources = ROOT / "dist/third-party-sources"
        if not sources.is_dir():
            raise SystemExit("Run python scripts/fetch_qt_notices.py before packaging Qt binaries.")
        shutil.copytree(sources, app / "third-party-sources", dirs_exist_ok=True)
        (app / "build-versions.json").write_text(json.dumps({name: version(name) for name in
            ("PySide6-Essentials", "shiboken6", "pyinstaller")}, indent=2) + "\n", encoding="utf-8")
    zip_sources(source_zip, include_game_assets=include_game_assets)
    if not args.source_only:
        # Include the full application source beside replaceable Qt DLLs.
        shutil.copyfile(source_zip, app / source_zip.name)
        binary_zip = release / f"{REPOSITORY_NAME}-{__version__}-windows-x64.zip"
        if binary_zip.exists():
            raise SystemExit(f"Release already exists: {binary_zip}")
        with zipfile.ZipFile(binary_zip, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(app.rglob("*")):
                if path.is_file():
                    archive.write(path, f"{APP_EXECUTABLE}/" + path.relative_to(app).as_posix())
    paths = [source_zip] + ([] if args.source_only else [binary_zip])
    manifest = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
    (release / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
